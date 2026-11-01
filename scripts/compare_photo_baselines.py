#!/usr/bin/env python3
"""Matched CPU photo comparison; keep GPU/live gains outside this experiment."""

import argparse
from pathlib import Path
import json
import os
import random
import subprocess
import sys
import tarfile
import time
import io

ROOT = Path(__file__).resolve().parents[1]


def execute(checkout, output):
    sys.path.insert(0, str(checkout))
    import functools
    import runpy
    import insightface

    insightface.app.FaceAnalysis = functools.partial(
        insightface.app.FaceAnalysis, root=str(ROOT / "models/insightface")
    )
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
        "--execution-threads",
        "2",
        "--frame-processor",
        "face_swapper",
        "--max-memory",
        "0",
    ]
    started = time.perf_counter()
    try:
        runpy.run_path(str(checkout / "run.py"), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise
    result = {
        "duration_seconds": time.perf_counter() - started,
        "output_exists": output.is_file(),
    }
    import importlib.metadata

    result["packages"] = {}
    for package in [
        "numpy",
        "onnxruntime",
        "onnxruntime-silicon",
        "onnx",
        "pillow",
        "insightface",
    ]:
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    output.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/evaluations/photo-baselines"
    )
    args = parser.parse_args()
    if args.worker:
        execute(args.worker, args.output)
        return
    old = ROOT / ".cache/evaluation/pre-flagship/complete-checkout"
    old.mkdir(parents=True, exist_ok=True)
    revision = json.loads((ROOT / "experiments/baselines.json").read_text())[
        "upstream"
    ]["git_revision"]
    archive = subprocess.check_output(["git", "archive", revision], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        tree.extractall(old, filter="data")
    snapshot = ROOT / ".cache/evaluation/pre-flagship/source.tar.gz"
    with tarfile.open(snapshot) as tree:
        tree.extractall(old, filter="data")
    if not (old / "models").exists():
        (old / "models").symlink_to(ROOT / "models", target_is_directory=True)
    args.output.mkdir(parents=True, exist_ok=True)
    setups = [
        (
            "upstream",
            ROOT / ".cache/evaluation/upstream",
            ROOT / ".cache/evaluation/upstream-venv/bin/python",
        ),
        ("pre-flagship", old, Path(sys.executable)),
        ("candidate", ROOT, Path(sys.executable)),
    ]
    order = [(setup, repeat) for repeat in range(3) for setup in setups]
    random.Random(2401).shuffle(order)
    sys.path.insert(0, str(ROOT))
    from modules.evaluation import fingerprint, sha256, write_report

    manifest = fingerprint()
    manifest.update(
        suite="matched-cpu-photo-baselines",
        archived_source_sha256=sha256(snapshot),
        source_sha256=sha256(ROOT / "assets/examples/source.png"),
        target_sha256=sha256(ROOT / "assets/examples/target.jpg"),
        scope="Fresh-process one-photo CPU runs, fixed two execution threads; startup/warmup included, no webcam FPS. Original dependencies isolated; pre-flagship/candidate share the recorded patched environment.",
    )
    checks, results = [], []
    for (name, checkout, python), repeat in order:
        output = args.output / f"{name}-{repeat}.jpg"
        started = time.perf_counter()
        with output.with_suffix(".log").open("w") as log:
            run = subprocess.run(
                [
                    str(python),
                    __file__,
                    "--worker",
                    str(checkout),
                    "--output",
                    str(output.resolve()),
                ],
                cwd=checkout,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=120,
                env={**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"},
            )
        passed = (
            run.returncode == 0
            and output.is_file()
            and output.with_suffix(".json").is_file()
        )
        row = {
            "baseline": name,
            "repeat": repeat,
            "process_seconds": time.perf_counter() - started,
            "status": "Passed" if passed else "Failed",
        }
        if passed:
            row.update(
                json.loads(output.with_suffix(".json").read_text()),
                output_sha256=sha256(output),
            )
        results.append(row)
        checks.append(
            {
                "name": f"{name}-{repeat}",
                "status": row["status"],
                "required": True,
                "detail": output.with_suffix(".log").name,
            }
        )
        write_report(args.output, manifest, checks, results)
        print(json.dumps(row), flush=True)
    return 0 if all(c["status"] == "Passed" for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
