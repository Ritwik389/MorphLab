#!/usr/bin/env python3
"""Characterise shared-server overload; not a multi-client 15 FPS claim."""

import argparse
import asyncio
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import fingerprint, write_report


async def measure(url, count, seconds, repeat):
    import cv2
    import httpx
    import numpy as np
    from websockets.asyncio.client import connect

    frames = []
    capture = cv2.VideoCapture(str(ROOT / ".cache/camera.y4m"))
    for _ in range(48):
        ok, frame = capture.read()
        if not ok:
            break
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if success:
            frames.append(encoded.tobytes())
    capture.release()
    if not frames:
        raise ValueError("Build the fake camera fixture first")
    source = (ROOT / "assets/examples/source.png").read_bytes()
    sessions, sockets, readers = [], [], []
    rows = [
        {"new_swaps": 0, "processed": 0, "latencies_ms": [], "dropped": 0}
        for _ in range(count)
    ]
    async with httpx.AsyncClient(base_url=url, timeout=90) as client:

        async def receive(index, socket):
            async for packet in socket:
                if not isinstance(packet, bytes):
                    data = json.loads(packet)
                    if data.get("error"):
                        raise RuntimeError(data["error"])
                    continue
                length = struct.unpack("!I", packet[:4])[0]
                header = json.loads(packet[4 : 4 + length])
                row = rows[index]
                row["processed"] += 1
                row["new_swaps"] += int(header["swapped"])
                row["dropped"] = header.get("dropped_frames", 0)
                row["latencies_ms"].append(
                    time.perf_counter() * 1000 - header["captured_at"]
                )

        try:
            for index in range(count):
                response = await client.post("/api/sessions")
                response.raise_for_status()
                session = response.json()["id"]
                sessions.append(session)
                response = await client.put(
                    f"/api/sessions/{session}/source",
                    files={"file": ("source.png", source, "image/png")},
                )
                response.raise_for_status()
                revision = response.json()["revision"]
                socket = await connect(
                    url.replace("http", "ws", 1) + f"/api/live/{session}",
                    origin=url,
                    max_size=2_100_000,
                )
                sockets.append((socket, revision))
                readers.append(asyncio.create_task(receive(index, socket)))
            started = time.perf_counter()
            frame_id = 0
            while time.perf_counter() - started < seconds:
                for reader in readers:
                    if reader.done():
                        reader.result()
                        raise RuntimeError("Stream ended during load test")
                for socket, revision in sockets:
                    metadata = json.dumps(
                        {
                            "frame_id": frame_id,
                            "revision": revision,
                            "captured_at": time.perf_counter() * 1000,
                        }
                    ).encode()
                    await socket.send(
                        struct.pack("!I", len(metadata))
                        + metadata
                        + frames[frame_id % len(frames)]
                    )
                frame_id += 1
                await asyncio.sleep(
                    max(0, started + frame_id / 24 - time.perf_counter())
                )
            elapsed = time.perf_counter() - started
            for reader in readers:
                reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)
            for row in rows:
                costs = row.pop("latencies_ms")
                row.update(
                    displayed_fps=None,
                    backend_swap_fps=row["new_swaps"] / elapsed,
                    p95_roundtrip_ms=float(np.percentile(costs, 95)) if costs else None,
                )
            return {
                "sessions": count,
                "repetition": repeat,
                "duration_seconds": elapsed,
                "per_client": rows,
                "scope": "24 Hz pre-encoded JPEG WebSocket clients; no browser rendering/capture; not the single-browser acceptance gate",
            }
        finally:
            for socket, _ in sockets:
                await socket.close()
            for reader in readers:
                reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)
            for session in sessions:
                await client.delete(f"/api/sessions/{session}")


async def main():
    import httpx

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/evaluations/concurrency"
    )
    args = parser.parse_args()
    manifest = fingerprint()
    manifest["suite"] = "concurrency-characterisation"
    async with httpx.AsyncClient() as client:
        before = (await client.get(args.url + "/api/system")).json()
    if (
        before.get("active_live_sessions")
        or before.get("source_tree_sha256") != manifest["source_tree_sha256"]
    ):
        raise SystemExit("Use an idle server running the exact source snapshot")
    checks, results = [], []
    for repeat in range(args.repetitions):
        for count in [1, 4, 2] if repeat % 2 == 0 else [2, 4, 1]:
            data = await measure(args.url, count, args.seconds, repeat)
            results.append(data)
            checks.append(
                {
                    "name": f"clients-{count}-repeat-{repeat}",
                    "status": "Passed"
                    if all(r["new_swaps"] > 0 for r in data["per_client"])
                    else "Failed",
                    "required": True,
                    "detail": "Throughput characterisation; no multi-client FPS SLA",
                }
            )
            write_report(args.output, manifest, checks, results)
            print(json.dumps(data), flush=True)
    async with httpx.AsyncClient() as client:
        after = (await client.get(args.url + "/api/system")).json()
    checks.append(
        {
            "name": "sessions-cleaned",
            "status": "Passed" if after["active_live_sessions"] == 0 else "Failed",
            "required": True,
            "detail": "All owned WebSockets and sessions closed",
        }
    )
    checks.append(
        {
            "name": "source-unchanged",
            "status": "Passed"
            if fingerprint()["source_tree_sha256"] == manifest["source_tree_sha256"]
            else "Failed",
            "required": True,
            "detail": "Exact candidate snapshot",
        }
    )
    report = write_report(args.output, manifest, checks, results)
    return 0 if report["overall"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
