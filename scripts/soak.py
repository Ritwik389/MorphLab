#!/usr/bin/env python3
"""Native backend longevity + repeated camera lifecycle test; browser lifecycle is separate."""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import psutil
from modules.evaluation import fingerprint
from modules.runtime import registry
from modules.studio_live import LiveSession


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=float, default=3600)
    p.add_argument("--cycles", type=int, default=100)
    p.add_argument("--output", type=Path, default=ROOT / "outputs/benchmarks/soak.json")
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = cv2.imread(str(ROOT / "assets/examples/source.png"))
    frame = cv2.imread(str(ROOT / "assets/examples/target.jpg"))
    frame = cv2.resize(frame, (409, 480))
    identity = registry.live_source(source)
    profile = fingerprint()
    memory = []
    cycles = []
    process = psutil.Process()
    session = LiveSession()
    session.set_source(identity)
    for i in range(20):
        session.process(
            {"frame_id": i, "revision": session.revision, "captured_at": 0}, frame
        )
    session.reset_camera()
    started = time.monotonic()
    frames = 0
    # The same source-specialized model is reused: this measures lifecycle, not enrollment cost.
    for cycle in range(args.cycles):
        session.set_source(identity)
        for i in range(3):
            session.process(
                {"frame_id": i, "revision": session.revision, "captured_at": 0}, frame
            )
        session.reset_camera()
        cycles.append(
            not session.tracker.tracks
            and session.latest is None
            and not session.thumbnails
        )
    session.set_source(identity)
    frame_id = 0
    last_sample = -10
    while time.monotonic() - started < args.seconds:
        now = time.monotonic() - started
        session.process(
            {"frame_id": frame_id, "revision": session.revision, "captured_at": 0},
            frame,
        )
        frame_id += 1
        frames += 1
        if now - last_sample >= 10:
            memory.append({"elapsed": now, "rss": process.memory_info().rss})
            last_sample = now
            report = {
                "schema_version": 1,
                "complete": False,
                "duration_seconds": now,
                "frames": frames,
                "scope": "Static-portrait backend longevity; not physical camera, browser track or worker lifecycle",
                "manifest": profile,
                "runtime": registry.status(),
                "cycles_completed": len(cycles),
                "cycles_passed": all(cycles),
                "memory": memory,
            }
            args.output.with_suffix(".partial.json").write_text(
                json.dumps(report, indent=2)
            )
            print(
                f"{now:.0f}s: {frames} frames, {memory[-1]['rss'] / 1024**2:.1f} MiB",
                flush=True,
            )
        time.sleep(max(0, 1 / 24 - (time.monotonic() - started - now)))
    session.set_source(None)
    session.reset_camera()
    first = [x["rss"] for x in memory if 60 <= x["elapsed"] < 660]
    last = [x["rss"] for x in memory if x["elapsed"] > args.seconds - 600]
    baseline = sum(first) / len(first) if first else memory[0]["rss"]
    tail = sum(last) / len(last) if last else memory[-1]["rss"]
    report.update(
        complete=True,
        duration_seconds=time.monotonic() - started,
        frames=frames,
        memory=memory,
        rss_growth_bytes=tail - baseline,
        memory_gate_passed=tail - baseline <= max(baseline * 0.1, 128 * 1024**2),
        cleanup_passed=session.latest is None and not session.tracker.tracks,
    )
    args.output.write_text(json.dumps(report, indent=2))
    print(args.output, flush=True)


if __name__ == "__main__":
    main()
