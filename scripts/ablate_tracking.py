#!/usr/bin/env python3
"""Continuous development-clip ablations, distinct from sparse model quality screening."""

import json
import argparse
from pathlib import Path
import random
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from modules.evaluation import fingerprint
from modules.runtime import registry
from modules.studio_live import LiveSession, unpack_frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/evaluations/continuous-ablations"
    )
    parser.add_argument("--context", default="Unspecified background load")
    args = parser.parse_args()
    corpus = json.loads((ROOT / "experiments/corpus.json").read_text())
    clips = [
        c
        for c in corpus["clips"]
        if c["identity"] == "ravdess-01" and not c.get("synthetic")
    ]
    source_clip = next(c for c in corpus["clips"] if c["identity"] == "ravdess-02")
    cap = cv2.VideoCapture(str(ROOT / source_clip["path"]))
    ok, source = cap.read()
    cap.release()
    if not ok:
        raise ValueError("Source decode failed")
    identity = registry.live_source(source)
    if "MobileFaceSwap" not in (registry.live_runtime or ""):
        raise RuntimeError("MPS ablation requires the actual mobile GPU runtime.")
    variants = [
        {"name": "dense-150", "dense": True, "interval": 0.15, "smooth": True},
        {"name": "five-point", "dense": False, "interval": 0.15, "smooth": True},
        {"name": "no-smoothing", "dense": True, "interval": 0.15, "smooth": False},
        {"name": "detect-100", "dense": True, "interval": 0.1, "smooth": True},
        {"name": "detect-250", "dense": True, "interval": 0.25, "smooth": True},
        {"name": "detect-every-frame", "dense": True, "interval": 0, "smooth": True},
    ]
    variants += [
        dict(variants[0], name="no-appearance-association", appearance=False),
        dict(variants[0], name="no-optical-flow", flow=False),
    ]
    frames = []
    for clip in clips:
        cap = cv2.VideoCapture(str(ROOT / clip["path"]))
        local = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            local.append(cv2.resize(frame, (640, 360)))
        cap.release()
        frames.append((clip["id"], local))
    directory = args.output
    directory.mkdir(parents=True, exist_ok=True)
    manifest = fingerprint()
    manifest["background_condition"] = args.context
    rows = []
    order = [(v, r) for r in range(3) for v in variants]
    random.Random(2401).shuffle(order)
    for variant, repeat in order:
        costs = []
        swaps = 0
        detector_calls = 0
        statuses = {}
        residual_changes = []
        for clip_id, sequence in frames:
            previous_edit = None
            clock = [0.0]
            session = LiveSession(
                dense_geometry=variant["dense"],
                detection_interval=variant["interval"],
                clock=lambda: clock[0],
            )
            session.tracker.smooth = variant["smooth"]
            session.tracker.appearance_enabled = variant.get("appearance", True)
            session.motion_prediction = variant.get("flow", True)
            session.set_source(identity)
            session.profile = True
            # Eight warmup frames are reported separately and are not measured.
            for index, frame in enumerate(sequence):
                clock[0] = index / 30
                packet = session.process(
                    {
                        "frame_id": index,
                        "revision": session.revision,
                        "captured_at": clock[0] * 1000,
                    },
                    frame,
                )
                header = json.loads(packet[4 : 4 + struct.unpack("!I", packet[:4])[0]])
                if index < 8:
                    continue
                costs.append(header["processing_ms"])
                swaps += int(header["swapped"])
                detector_calls += int("detection_ms" in header.get("stages", {}))
                status = header["target_status"]
                statuses[status] = statuses.get(status, 0) + 1
                # Offline proxy is outside the timed process() interval. Coverage
                # and missing edits remain explicit; gaps never count as stability.
                if header["swapped"]:
                    from insightface.utils.face_align import norm_crop

                    _, output = unpack_frame(packet)
                    target = next(
                        t for t in session.tracker.tracks if t.id == session.selected
                    )
                    edit = (
                        norm_crop(output, target.face.kps, 112).astype(np.float32)
                        - norm_crop(frame, target.face.kps, 112).astype(np.float32)
                    ) / 255
                    if previous_edit is not None:
                        residual_changes.append(
                            float(np.abs(edit - previous_edit).mean())
                        )
                    previous_edit = edit
                else:
                    previous_edit = None
            session.reset_camera()
        row = {
            "variant": variant,
            "repetition": repeat,
            "frames": len(costs),
            "swapped": swaps,
            "coverage": swaps / max(1, len(costs)),
            "p50_ms": float(np.percentile(costs, 50)),
            "p95_ms": float(np.percentile(costs, 95)),
            "processing_fps_excluding_io": len(costs) / (sum(costs) / 1000),
            "detector_calls": detector_calls,
            "statuses": statuses,
            "temporal_edit_residual_change_mean_0_1": float(np.mean(residual_changes))
            if residual_changes
            else None,
            "temporal_adjacent_swapped_pairs": len(residual_changes),
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
        (directory / "results.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "manifest": manifest,
                    "scope": "Continuous genuine development speech; backend timing excludes IO and evaluation, not browser FPS; no held-out identity-switch ground truth",
                    "runtime": registry.status(),
                    "rows": rows,
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
