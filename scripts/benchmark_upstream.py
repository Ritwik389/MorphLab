#!/usr/bin/env python3
"""Run pinned upstream code in its own resolved environment, redirecting only model cache."""

import functools
import hashlib
import json
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
checkout = ROOT / ".cache/evaluation/upstream"
sys.path.insert(0, str(checkout))
import insightface

insightface.app.FaceAnalysis = functools.partial(
    insightface.app.FaceAnalysis, root=str(ROOT / "models/insightface")
)
output = ROOT / "outputs/evaluations/upstream-result.jpg"
sys.argv = [
    str(checkout / "run.py"),
    "-s",
    str(ROOT / "assets/examples/source.png"),
    "-t",
    str(ROOT / "assets/examples/target.jpg"),
    "-o",
    str(output),
    "--execution-provider",
    "cpu",
    "--frame-processor",
    "face_swapper",
    "--max-memory",
    "0",
]
started = time.perf_counter()
error = None
try:
    runpy.run_path(str(checkout / "run.py"), run_name="__main__")
except SystemExit as exc:
    if exc.code not in (None, 0):
        error = f"Exit {exc.code}"
except Exception as exc:
    error = f"{type(exc).__name__}: {exc}"
report = {
    "schema_version": 1,
    "repository_revision": "2bf2728c6d3e2df1086fa2dc3e25de3944532a10",
    "scope": "Original CLI one-photo CPU end-to-end run in its isolated, currently resolved declared environment; includes startup/warmup and is not live FPS",
    "override": "Only the default InsightFace cache root is redirected to the same verified model weights; source code is unchanged.",
    "duration_seconds": time.perf_counter() - started,
    "output_exists": output.exists(),
    "error": error,
    "dependency_lock_sha256": hashlib.sha256(
        (ROOT / ".cache/evaluation/upstream-requirements.lock").read_bytes()
    ).hexdigest(),
}
(ROOT / "outputs/evaluations/upstream-run.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(json.dumps(report), flush=True)
if error:
    raise SystemExit(1)
