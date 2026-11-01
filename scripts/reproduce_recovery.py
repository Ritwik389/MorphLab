#!/usr/bin/env python3
"""Compare the archived and current state machines under identical known observations.

This deliberately mocks detection/generation. It proves a control-state defect,
not model quality, recognition accuracy or physical-camera performance.
"""

import argparse
from pathlib import Path
import json
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def worker(root, output):
    sys.path.insert(0, str(root))
    import concurrent.futures
    import inspect
    from types import SimpleNamespace
    import cv2
    import numpy as np
    from modules import studio_live

    def observe(frame):
        value = int(frame[0, 0, 0])
        face = SimpleNamespace(
            bbox=np.array([20, 20, 90, 120], np.float32),
            kps=np.array(
                [[35, 45], [75, 45], [55, 65], [40, 90], [70, 90]], np.float32
            ),
            embedding=np.ones(512, np.float32),
        )
        return (
            [] if value in {1, 2} else [face],
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
        )

    class ImmediateExecutor:
        def submit(self, fn, *args):
            result = concurrent.futures.Future()
            result.set_result(fn(*args))
            return result

    studio_live.observe = observe
    studio_live.scene_changed = lambda *args: False
    studio_live.DETECTIONS = ImmediateExecutor()
    studio_live.registry.live_swap = lambda frame, *args: frame.copy()
    kwargs = (
        {"dense_geometry": False}
        if "dense_geometry" in inspect.signature(studio_live.LiveSession).parameters
        else {}
    )
    session = studio_live.LiveSession(**kwargs)
    session.mode, session.latent = "swap", object()
    session.tracker.predict = lambda *args: False
    clock = [0.0]
    session.clock = lambda: clock[0]
    rows = []
    for index in range(6):
        clock[0] = index / 10
        frame = np.full((160, 240, 3), index, np.uint8)
        packet = session.process(
            {"frame_id": index, "revision": 0, "captured_at": index * 100}, frame
        )
        header, _ = studio_live.unpack_frame(packet)
        rows.append(
            {
                "frame_id": index,
                "face_present": index not in {1, 2},
                "selected": header["selected_face"],
                "swapped": header["swapped"],
                "message": header["message"],
            }
        )
    output.write_text(
        json.dumps(
            {
                "observations": rows,
                "recovered": rows[-1]["swapped"],
                "scope": "Mocked observation/inference control-state reproduction only",
            },
            indent=2,
        )
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.output)
        return
    archive = ROOT / ".cache/evaluation/pre-flagship/source.tar.gz"
    checkout = ROOT / ".cache/evaluation/pre-flagship/checkout"
    checkout.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as source:
        source.extractall(checkout, filter="data")
    directory = ROOT / "outputs/evaluations/recovery-comparison"
    directory.mkdir(parents=True, exist_ok=True)
    for name, root in [("pre-flagship", checkout), ("candidate", ROOT)]:
        with (directory / (name + ".log")).open("w") as log:
            subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--worker",
                    str(root),
                    "--output",
                    str(directory / (name + ".json")),
                ],
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
    sys.path.insert(0, str(ROOT))
    from modules.evaluation import fingerprint, sha256, write_report

    old = json.loads((directory / "pre-flagship.json").read_text())
    new = json.loads((directory / "candidate.json").read_text())
    manifest = fingerprint()
    manifest.update(suite="baseline-state-reproduction", archive_sha256=sha256(archive))
    write_report(
        directory,
        manifest,
        [
            {
                "name": "old-defect-reproduced",
                "status": "Passed" if not old["recovered"] else "Failed",
                "detail": "pre-flagship.json; mocked observations",
                "required": True,
            },
            {
                "name": "candidate-recovers",
                "status": "Passed" if new["recovered"] else "Failed",
                "detail": "candidate.json; same observations",
                "required": True,
            },
        ],
        [old, new],
    )
    print(directory / "report.html")


if __name__ == "__main__":
    main()
