#!/usr/bin/env python3
"""Pin the authors' AdaFace IR50 evaluator and download its public checkpoint."""

import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "models/evaluation/adaface"
SOURCE = ROOT / "third_party/adaface"
FILE_ID = "1BmDRrhPsHSbXcWZoYFPJg2KJn1sd3QpN"


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    pin = ROOT / "experiments/adaface.json"
    pinned = json.loads(pin.read_text()) if pin.exists() else None
    if pinned:
        revision = pinned["revision"]
    else:
        response = s.get(
            "https://api.github.com/repos/mk-minchul/AdaFace/commits/master", timeout=45
        )
        response.raise_for_status()
        revision = response.json()["sha"]
    files = {}
    for name in ["net.py", "LICENSE"]:
        r = s.get(
            f"https://raw.githubusercontent.com/mk-minchul/AdaFace/{revision}/{name}",
            timeout=45,
        )
        r.raise_for_status()
        files[name] = hashlib.sha256(r.content).hexdigest()
        if pinned and files[name] != pinned["source_sha256"][name]:
            raise ValueError("Pinned AdaFace source checksum mismatch.")
        (SOURCE / name).write_bytes(r.content)
    checkpoint = DIRECTORY / "adaface_ir50_webface4m.ckpt"
    if not checkpoint.exists():
        url = f"https://drive.usercontent.google.com/download?id={FILE_ID}&export=download&confirm=t"
        with s.get(url, timeout=120, stream=True) as r:
            r.raise_for_status()
            if "text/html" in r.headers.get("Content-Type", ""):
                raise RuntimeError(
                    "Checkpoint download needs interactive confirmation; no HTML was saved as weights."
                )
            tmp = checkpoint.with_suffix(".part")
            with tmp.open("wb") as output:
                for chunk in r.iter_content(1024 * 1024):
                    output.write(chunk)
            tmp.replace(checkpoint)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if pinned and digest != pinned["sha256"]:
        raise ValueError(
            "Pinned AdaFace checkpoint checksum mismatch. Remove the damaged local checkpoint and retry."
        )
    manifest = {
        "schema_version": 1,
        "model": "AdaFace IR50 WebFace4M",
        "revision": revision,
        "source": "https://github.com/mk-minchul/AdaFace",
        "download": f"https://drive.google.com/file/d/{FILE_ID}/view",
        "sha256": digest,
        "source_sha256": files,
        "preprocessing": "112x112 BGR, float [-1,1]; authors backbone, not the live recognizer",
        "scope": "Offline evaluation only; shared training data may still overlap other pretrained models.",
    }
    (DIRECTORY / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "experiments/adaface.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
