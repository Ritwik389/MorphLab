#!/usr/bin/env python3
"""Derived stress clips with known composition identity; not natural-scene ground truth."""

import json
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.runtime import registry
from modules.evaluation import sha256


def main():
    path = ROOT / "experiments/corpus.json"
    corpus = json.loads(path.read_text())
    originals = [c for c in corpus["clips"] if not c.get("synthetic")]
    derived = []
    directory = ROOT / ".cache/evaluation/corpus/derived"
    directory.mkdir(parents=True, exist_ok=True)
    for split, actors in [
        ("development", [1, 2]),
        ("validation", [5, 6]),
        ("heldout", [9, 10]),
    ]:
        clips = [
            next(c for c in originals if c["identity"] == f"ravdess-{actor:02}")
            for actor in actors
        ]
        videos = []
        for clip in clips:
            cap = cv2.VideoCapture(str(ROOT / clip["path"]))
            frames = []
            ok, frame = cap.read()
            box = registry.detect(frame)[0].bbox.astype(int)
            x1, y1, x2, y2 = box
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            extent = int(max(x2 - x1, y2 - y1) * 0.75)
            while ok:
                crop = frame[
                    max(0, cy - extent) : min(frame.shape[0], cy + extent),
                    max(0, cx - extent) : min(frame.shape[1], cx + extent),
                ]
                frames.append(cv2.resize(crop, (200, 200)))
                ok, frame = cap.read()
            cap.release()
            videos.append(frames)
        for scenario in ["crossing", "departure", "lighting_blur"]:
            name = f"derived-{split}-{scenario}"
            output = directory / (name + ".mp4")
            writer = cv2.VideoWriter(
                str(output), cv2.VideoWriter_fourcc(*"mp4v"), 24, (640, 480)
            )
            annotations = []
            for i in range(144):
                t = i / 24
                canvas = np.full((480, 640, 3), 80, np.uint8)
                a = int(40 + 360 * i / 143)
                b = int(430 - 340 * i / 143)
                boxes = []
                for person, x, size in [(0, a, 200), (1, b, 170)]:
                    present = not (
                        scenario == "departure" and person == 0 and 1.2 < t < 4
                    )
                    if not present:
                        continue
                    crop = cv2.resize(
                        videos[person][i % len(videos[person])], (size, size)
                    )
                    canvas[130 : 130 + size, x : x + size] = crop
                    boxes.append(
                        {
                            "identity": clips[person]["identity"],
                            "composition_bbox": [x, 130, x + size, 130 + size],
                        }
                    )
                if scenario == "lighting_blur":
                    canvas = np.clip(
                        canvas.astype(float) * (0.6 + 0.4 * np.sin(i / 17)), 0, 255
                    ).astype(np.uint8)
                    if 1.5 < t < 3.5:
                        canvas = cv2.GaussianBlur(canvas, (13, 13), 4)
                writer.write(canvas)
                annotations.append({"frame": i, "people": boxes})
            writer.release()
            annotation_path = directory / (name + ".json")
            annotation_path.write_text(json.dumps(annotations))
            derived.append(
                {
                    "id": name,
                    "path": str(output.relative_to(ROOT)),
                    "identity": clips[0]["identity"],
                    "identities": [c["identity"] for c in clips],
                    "split": split,
                    "sha256": sha256(output),
                    "provenance": "https://zenodo.org/records/1188976",
                    "licence": "CC-BY-NC-SA-4.0",
                    "synthetic": True,
                    "scenario": scenario,
                    "annotations_reviewed": False,
                    "annotation_path": str(annotation_path.relative_to(ROOT)),
                    "annotation_sha256": sha256(annotation_path),
                    "annotation_scope": "Exact composited portrait rectangles/identities; not reviewed anatomical face boxes or natural occlusion masks.",
                    "eligible_intervals": [],
                    "events": [],
                }
            )
    corpus["clips"] = originals + derived
    path.write_text(json.dumps(corpus, indent=2) + "\n")
    print(
        f"{len(originals)} genuine clips + {len(derived)} explicitly synthetic stress clips"
    )


if __name__ == "__main__":
    main()
