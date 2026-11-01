#!/usr/bin/env python3
"""Create a deterministic fake camera. Prefer genuine development clips; label fallback."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from modules.runtime import registry


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=ROOT / ".cache/camera.y4m")
    p.add_argument("--static", action="store_true")
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    corpus = ROOT / "experiments/corpus.json"
    clips = []
    if corpus.exists() and not args.static:
        clips = [
            ROOT / c["path"]
            for c in json.loads(corpus.read_text())["clips"]
            if c["split"] == "development"
            and c["identity"] == "ravdess-01"
            and (ROOT / c["path"]).is_file()
        ]
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        "640x480",
        "-r",
        "24",
        "-i",
        "-",
        "-an",
        "-pix_fmt",
        "yuv420p",
        str(args.output),
    ]
    with subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
    ) as process:
        count = 0
        if clips:
            for path in clips:
                cap = cv2.VideoCapture(str(path))
                ok, frame = cap.read()
                if not ok:
                    raise ValueError("Unreadable camera fixture clip")
                faces = registry.detect(frame)
                if not faces:
                    raise ValueError("Fixture face not detected")
                box = faces[0].bbox
                centre = (box[:2] + box[2:]) / 2
                height = min(frame.shape[0], (box[3] - box[1]) * 2.2)
                width = height * 4 / 3
                x = max(0, min(frame.shape[1] - width, centre[0] - width / 2))
                y = max(0, min(frame.shape[0] - height, centre[1] - height * 0.45))
                source_fps = cap.get(cv2.CAP_PROP_FPS) or 30
                index = 0
                last = -1
                while ok:
                    target_index = int(index * 24 / source_fps)
                    if target_index != last:
                        crop = frame[int(y) : int(y + height), int(x) : int(x + width)]
                        process.stdin.write(cv2.resize(crop, (640, 480)).tobytes())
                        count += 1
                        last = target_index
                    index += 1
                    ok, frame = cap.read()
                cap.release()
            scope = "Genuine RAVDESS actor 01 development speech/expression; fixed crop; loop boundaries are scene cuts. Not broad head-turn or crossing coverage."
        else:
            frame = cv2.imread(str(ROOT / "assets/examples/target.jpg"))
            frame = cv2.resize(frame, (409, 480))
            for i in range(120):
                canvas = np.full((480, 640, 3), 30, np.uint8)
                matrix = cv2.getRotationMatrix2D((204, 240), 4 * np.sin(i / 20), 1)
                canvas[:, 115:524] = cv2.warpAffine(frame, matrix, (409, 480))
                process.stdin.write(canvas.tobytes())
                count += 1
            scope = (
                "Synthetic gentle 2D portrait rotation only; not genuine head motion."
            )
        process.stdin.close()
        code = process.wait()
        if code:
            raise RuntimeError("FFmpeg fixture encoding failed")
    from modules.evaluation import sha256

    manifest = {
        "schema_version": 1,
        "scope": scope,
        "frames": count,
        "fps": 24,
        "sha256": sha256(args.output),
        "sources": [str(p.relative_to(ROOT)) for p in clips],
    }
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
