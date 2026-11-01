#!/usr/bin/env python3
"""Retrieve a small, licensed RAVDESS subset using ZIP ranges, not multi-GB archives."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile
import requests

ROOT = Path(__file__).resolve().parents[1]
RECORD = "https://zenodo.org/records/1188976"


class RemoteZip(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
        self.http = requests.Session()

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = (
            offset
            if whence == 0
            else self.pos + offset
            if whence == 1
            else self.size + offset
        )
        return self.pos

    def read(self, n=-1):
        end = self.size - 1 if n < 0 else min(self.size - 1, self.pos + n - 1)
        if end < self.pos:
            return b""
        for attempt in range(4):
            try:
                response = self.http.get(
                    self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=90
                )
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            if response.status_code == 429:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            if response.status_code != 206 or not response.headers.get(
                "Content-Range", ""
            ).startswith(f"bytes {self.pos}-"):
                raise RuntimeError(
                    "Server did not honour byte range; refusing a full archive download."
                )
            data = response.content
            if len(data) != end - self.pos + 1:
                raise RuntimeError("Incomplete ZIP range.")
            self.pos += len(data)
            return data
        raise RuntimeError("Dataset server rate limit; retry later.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--actors", type=int, default=12)
    args = parser.parse_args()
    directory = ROOT / ".cache/evaluation/corpus"
    directory.mkdir(parents=True, exist_ok=True)
    record = ROOT / ".cache/evaluation/ravdess-record.json"
    if not record.exists():
        r = requests.get("https://zenodo.org/api/records/1188976", timeout=60)
        r.raise_for_status()
        record.write_text(json.dumps(r.json()))
    meta = json.loads(record.read_text())
    manifest_file = ROOT / "experiments/corpus.json"
    pinned = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    expected = {
        Path(c["path"]).name: c["sha256"]
        for c in pinned.get("clips", [])
        if not c.get("synthetic")
    }
    entries = []
    for actor in range(1, args.actors + 1):
        file = next(
            x for x in meta["files"] if x["key"] == f"Video_Speech_Actor_{actor:02}.zip"
        )
        selected = [
            f"01-01-{emotion:02}-{intensity:02}-01-01-{actor:02}.mp4"
            for emotion, intensity in [(1, 1), (3, 2), (5, 2)]
        ]
        missing = [name for name in selected if not (directory / name).exists()]
        if missing:
            with zipfile.ZipFile(
                RemoteZip(file["links"]["self"], file["size"])
            ) as archive:
                for name in missing:
                    member = next(x for x in archive.namelist() if Path(x).name == name)
                    data = archive.read(member)
                    tmp = directory / (name + ".part")
                    tmp.write_bytes(data)
                    tmp.replace(directory / name)
                    print(f"Downloaded {name}: {len(data)} bytes", flush=True)
        split = (
            ["development", "validation", "heldout"][(actor - 1) // 4]
            if actor <= 12
            else "development"
        )
        for name in selected:
            path = directory / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if name in expected and digest != expected[name]:
                raise ValueError(
                    f"Pinned corpus checksum changed for {name}. Remove the damaged cache file and retry."
                )
            entries.append(
                {
                    "id": path.stem,
                    "path": str(path.relative_to(ROOT)),
                    "identity": f"ravdess-{actor:02}",
                    "split": split,
                    "sha256": digest,
                    "provenance": RECORD,
                    "licence": "CC-BY-NC-SA-4.0",
                    "redistributable": True,
                    "scenario": "genuine_speech_expression",
                    "annotations_reviewed": False,
                    "synthetic": False,
                    "eligible_intervals": [],
                    "events": [],
                }
            )
        manifest = {
            "schema_version": 1,
            "name": "RAVDESS speech subset",
            "citation": "Livingstone & Russo (2018), doi:10.1371/journal.pone.0196391",
            "licence": "CC-BY-NC-SA-4.0",
            "commercial_use": False,
            "frozen": False,
            "limitations": [
                "Studio speech/expression footage does not establish natural crossings, diverse lighting or large head turns.",
                "Eligible intervals and tracking annotations require review before release gates can pass.",
            ],
            "clips": entries,
        }
        (ROOT / "experiments/corpus.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
    print(
        f"Corpus: {len(entries)} clips / {args.actors} identities. Annotations pending review.",
        flush=True,
    )


if __name__ == "__main__":
    main()
