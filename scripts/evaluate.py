#!/usr/bin/env python3
"""Matched sampled-frame screening, isolated runtimes and independent offline quality."""

import argparse
import json
import os
from pathlib import Path
import random
import statistics
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import fingerprint, validate_corpus, write_report


def run_candidate(config, candidate, corpus, split, repetition, out):
    import cv2
    import numpy as np
    from modules.runtime import ModelRegistry, RuntimeConfig
    from modules import studio_live

    os.environ["AIMS_LIVE_MODEL"] = (
        "inswapper" if candidate["runtime"] != "mobile" else "auto"
    )
    os.environ["AIMS_MASK_MODE"] = candidate["mask"]
    registry = ModelRegistry(
        RuntimeConfig(
            device="auto" if candidate["runtime"] == "mobile" else candidate["runtime"],
            precision=candidate.get("precision"),
        )
    )
    studio_live.registry = registry
    clips = [
        c for c in corpus["clips"] if c["split"] == split and not c.get("synthetic")
    ]
    evaluator = None
    evaluator_error = None
    try:
        from modules.identity_evaluator import AdaFaceEvaluator

        evaluator = AdaFaceEvaluator()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        evaluator_error = str(exc)
    rows = []
    for clip in clips:
        source_clip = next(c for c in clips if c["identity"] != clip["identity"])
        source_cap = cv2.VideoCapture(str(ROOT / source_clip["path"]))
        ok, source = source_cap.read()
        source_cap.release()
        if not ok:
            raise ValueError("Could not read source clip.")
        cap = cv2.VideoCapture(str(ROOT / clip["path"]))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        session = studio_live.LiveSession(
            dense_geometry=candidate["dense"],
            detection_interval=candidate["interval_ms"] / 1000,
        )
        session.tracker.smooth = candidate["smooth"]
        session.profile = True
        started = time.perf_counter()
        identity = (
            registry.live_source(source)
            if candidate["runtime"] == "mobile"
            else registry.source(source)
        )
        source_ms = (time.perf_counter() - started) * 1000
        session.set_source(identity)
        source_face = registry.detect(source)[0]
        source_vector = evaluator.embedding(source, source_face) if evaluator else None
        runtime = registry.status()
        if candidate["runtime"] == "mobile" and "MobileFaceSwap" not in (
            runtime["live_runtime"] or ""
        ):
            raise RuntimeError(
                "Requested MPS candidate fell back; refusing to label CPU results as mobile GPU."
            )
        if candidate["runtime"] == "coreml" and not (
            runtime["active_runtime"] or ""
        ).startswith("Native CoreML"):
            raise RuntimeError(
                "Requested native CoreML candidate unavailable; no silent substitution."
            )
        for frame_id, position in enumerate(
            np.linspace(0, max(0, count - 1), config["frames_per_clip"], dtype=int)
        ):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(position))
            ok, frame = cap.read()
            if not ok:
                rows.append(
                    {"clip": clip["id"], "failure": "decode", "repetition": repetition}
                )
                continue
            scale = min(
                candidate["resolution"][0] / frame.shape[1],
                candidate["resolution"][1] / frame.shape[0],
            )
            frame = cv2.resize(
                frame, (round(frame.shape[1] * scale), round(frame.shape[0] * scale))
            )
            packet = session.process(
                {
                    "frame_id": frame_id,
                    "revision": 1,
                    "captured_at": position / max(fps, 1) * 1000,
                },
                frame,
            )
            size = struct.unpack("!I", packet[:4])[0]
            header = json.loads(packet[4 : 4 + size])
            result = cv2.imdecode(
                np.frombuffer(packet[4 + size :], np.uint8), cv2.IMREAD_COLOR
            )
            row = {
                "clip": clip["id"],
                "identity": clip["identity"],
                "repetition": repetition,
                "frame": int(position),
                "swapped": header["swapped"],
                "processing_ms": header["processing_ms"],
                "source_enrollment_ms": source_ms,
                "stages": header.get("stages", {}),
                "identity_cosine": None,
                "recognition_failed": False,
            }
            if evaluator and header["swapped"]:
                faces = registry.detect(result)
                if faces:
                    row["identity_cosine"] = float(
                        np.dot(source_vector, evaluator.embedding(result, faces[0]))
                    )
                else:
                    row["recognition_failed"] = True
            rows.append(row)
        cap.release()
        session.set_source(None)
        session.reset_camera()
    costs = [r["processing_ms"] for r in rows if "processing_ms" in r]
    scores = [
        r["identity_cosine"] for r in rows if r.get("identity_cosine") is not None
    ]
    data = {
        "schema_version": 1,
        "candidate": candidate,
        "repetition": repetition,
        "split": split,
        "scope": config["scope"],
        "manifest": fingerprint(),
        "runtime": registry.status(),
        "evaluator": evaluator.manifest if evaluator else None,
        "evaluator_error": evaluator_error,
        "rows": rows,
        "summary": {
            "samples": len(rows),
            "processing_p50_ms": float(np.percentile(costs, 50)) if costs else None,
            "processing_p95_ms": float(np.percentile(costs, 95)) if costs else None,
            "median_identity_cosine": statistics.median(scores) if scores else None,
            "swapped_samples": sum(r.get("swapped", False) for r in rows),
        },
    }
    out.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=ROOT / "experiments/screening.json")
    p.add_argument(
        "--split",
        choices=["development", "validation", "heldout"],
        default="development",
    )
    p.add_argument("--output", type=Path)
    p.add_argument("--candidate")
    p.add_argument("--repetition", type=int, default=0)
    args = p.parse_args()
    config = json.loads(args.config.read_text())
    corpus = json.loads((ROOT / "experiments/corpus.json").read_text())
    errors = validate_corpus(corpus, True)
    if errors:
        raise ValueError("; ".join(errors))
    if args.split == "heldout" and (
        not corpus.get("frozen")
        or not all(c.get("annotations_reviewed") for c in corpus["clips"])
    ):
        raise ValueError("Freeze and review the held-out corpus before evaluating it.")
    directory = (
        args.output
        or ROOT / "outputs/evaluations" / f"screening-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    if args.candidate:
        candidate = next(c for c in config["candidates"] if c["name"] == args.candidate)
        run_candidate(
            config,
            candidate,
            corpus,
            args.split,
            args.repetition,
            directory / f"{args.candidate}-{args.repetition}.json",
        )
        return
    checks = []
    results = []
    order = [(c, r) for r in range(config["repetitions"]) for c in config["candidates"]]
    random.Random(config["seed"]).shuffle(order)
    for candidate, repetition in order:
        name = f"{candidate['name']}-{repetition}"
        file = directory / (name + ".json")
        with (directory / (name + ".log")).open("w") as log:
            run = subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--config",
                    str(args.config),
                    "--split",
                    args.split,
                    "--output",
                    str(directory),
                    "--candidate",
                    candidate["name"],
                    "--repetition",
                    str(repetition),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        checks.append(
            {
                "name": name,
                "required": True,
                "status": "Passed" if run.returncode == 0 else "Failed",
                "detail": file.name if file.exists() else name + ".log",
            }
        )
        if file.exists():
            data = json.loads(file.read_text())
            results.append(
                {
                    "candidate": candidate["name"],
                    "repetition": repetition,
                    **data["summary"],
                }
            )
        print(f"{name}: {checks[-1]['status']}", flush=True)
    write_report(directory, fingerprint(), checks, results)
    print(directory / "report.html")


if __name__ == "__main__":
    main()
