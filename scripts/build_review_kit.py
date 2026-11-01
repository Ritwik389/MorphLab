#!/usr/bin/env python3
"""Generate local, model-blinded excerpts and a blank fixed-rubric rating sheet."""

import argparse
import csv
import json
import os
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import fingerprint, sha256


def main():
    import cv2
    from modules.runtime import ModelRegistry, RuntimeConfig
    from modules import studio_live

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/review-kit")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(
            "Use an empty output directory so existing ratings are never overwritten."
        )
    args.output.mkdir(parents=True, exist_ok=True)
    corpus = json.loads((ROOT / "experiments/corpus.json").read_text())
    clips = [
        c
        for c in corpus["clips"]
        if c["split"] == "validation" and not c.get("synthetic")
    ][:6]
    variants = ["binary", "soft"]
    assignments = [(index, mode) for index in range(len(clips)) for mode in variants]
    random.Random(2401).shuffle(assignments)
    identifiers = {
        pair: f"excerpt-{index + 1:02d}" for index, pair in enumerate(assignments)
    }
    mapping, records = {}, {}
    os.environ["AIMS_LIVE_MODEL"] = "auto"
    for mode in variants:
        os.environ["AIMS_MASK_MODE"] = mode
        registry = ModelRegistry(RuntimeConfig("auto"))
        studio_live.registry = registry
        for index, clip in enumerate(clips):
            identifier = identifiers[index, mode]
            folder = args.output / identifier
            folder.mkdir()
            source_clip = next(c for c in clips if c["identity"] != clip["identity"])
            source_capture = cv2.VideoCapture(str(ROOT / source_clip["path"]))
            ok, source = source_capture.read()
            source_capture.release()
            if not ok:
                raise ValueError("Unreadable source")
            source_face = registry.detect(source)[0]
            box = source_face.bbox.astype(int)
            x1, y1, x2, y2 = box
            cv2.imwrite(
                str(folder / "source.jpg"), source[max(0, y1) : y2, max(0, x1) : x2]
            )
            identity = registry.live_source(source)
            if "MobileFaceSwap" not in (registry.live_runtime or ""):
                raise RuntimeError(
                    "Requested MPS model unavailable; refusing silent substitution"
                )
            capture = cv2.VideoCapture(str(ROOT / clip["path"]))
            fps = capture.get(cv2.CAP_PROP_FPS) or 30
            ok, frame = capture.read()
            if not ok:
                raise ValueError("Unreadable target")
            face = registry.detect(frame)[0]
            centre = (face.bbox[:2] + face.bbox[2:]) / 2
            height = min(frame.shape[0], (face.bbox[3] - face.bbox[1]) * 2.2)
            width = height * 4 / 3
            x = max(0, min(frame.shape[1] - width, centre[0] - width / 2))
            y = max(0, min(frame.shape[0] - height, centre[1] - height * 0.45))
            clock = [0.0]
            session = studio_live.LiveSession(clock=lambda: clock[0])
            session.set_source(identity)
            writers = [
                cv2.VideoWriter(
                    str(folder / name), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 480)
                )
                for name in ["original.work.mp4", "edited.work.mp4"]
            ]
            if not all(writer.isOpened() for writer in writers):
                raise RuntimeError("Review encoder unavailable")
            swapped, count = 0, 0
            try:
                while ok and count < round(fps * 3):
                    current = cv2.resize(
                        frame[int(y) : int(y + height), int(x) : int(x + width)],
                        (640, 480),
                    )
                    clock[0] = count / fps
                    packet = session.process(
                        {
                            "frame_id": count,
                            "revision": session.revision,
                            "captured_at": clock[0] * 1000,
                        },
                        current,
                    )
                    header, result = studio_live.unpack_frame(packet)
                    swapped += int(header["swapped"])
                    writers[0].write(current)
                    writers[1].write(result)
                    count += 1
                    ok, frame = capture.read()
            finally:
                capture.release()
                for writer in writers:
                    writer.release()
                session.set_source(None)
                session.reset_camera()
            for name in ["original", "edited"]:
                temporary = folder / f"{name}.work.mp4"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-y",
                        "-i",
                        str(temporary),
                        "-an",
                        "-c:v",
                        "libx264",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        "-movflags",
                        "+faststart",
                        str(folder / f"{name}.mp4"),
                    ],
                    check=True,
                )
                temporary.unlink()
            mapping[identifier] = {
                "mask": mode,
                "target_clip": clip["id"],
                "source_clip": source_clip["id"],
                "swapped_frames": swapped,
                "frames": count,
                "runtime": registry.status(),
            }
            records[identifier] = {p.name: sha256(p) for p in folder.iterdir()}
            print(identifier + " generated", flush=True)
    with (args.output / "ratings.csv").open("w", newline="") as stream:
        fields = [
            "reviewer",
            "excerpt_id",
            "identity_defect",
            "expression_defect",
            "flicker_defect",
            "boundary_defect",
            "lighting_defect",
            "abstention_reason",
            "notes",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({"excerpt_id": identifier} for identifier in sorted(records))
    (args.output / "README.md").write_text("""# Blinded MorphLab author review — pending

Open each excerpt's source.jpg, original.mp4 and edited.mp4. Rate every dimension in ratings.csv before opening the separate reveal key. Use 0=no defect, 1=minor, 2=noticeable, 3=severe. For identity, rate mismatch with the source; for expression, compare the original target. Leave an explicit abstention reason when you cannot judge. Enter a reviewer name/identifier; do not invent independent reviewers.

These are three-second, fixed face-centred crops from validation speech/expression clips. They do not cover broad 3D turns or real crossings. Results are generated edits, labelled by MorphLab. The candidates share generator weights and differ in boundary compositing; no completed human review is implied by generation.

RAVDESS: Livingstone & Russo (2018), https://zenodo.org/records/1188976, CC BY-NC-SA 4.0. This local research derivative retains attribution/non-commercial/share-alike conditions. Do not publish private review material or source embeddings. No embeddings are included.
""")
    manifest = fingerprint()
    manifest.update(
        scope="Blinded validation visual review kit, not completed ratings",
        completed=False,
        reviewer_count=0,
        files=records,
    )
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    key = ROOT / ".cache/evaluation/review-reveal.json"
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps(mapping, indent=2) + "\n")
    print("Blank rating sheet: " + str(args.output / "ratings.csv"))


if __name__ == "__main__":
    main()
