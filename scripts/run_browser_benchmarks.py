#!/usr/bin/env python3
"""Sequential, fingerprint-bound browser trials; never run competing inference tests."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import browser_gate, fingerprint, write_report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--url", default="http://127.0.0.1:7860")
    p.add_argument("--worker", choices=["on", "off"], default="on")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    directory = (
        args.output
        or ROOT / "outputs/evaluations" / f"browser-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    manifest = fingerprint()
    with urllib.request.urlopen(args.url + "/api/system", timeout=10) as response:
        server = json.load(response)
    if server.get("source_tree_sha256") != manifest["source_tree_sha256"]:
        raise SystemExit(
            "Server is running a different source snapshot. Restart it before benchmarking."
        )
    manifest.update(suite="browser-performance", url=args.url, worker=args.worker)
    fixture = ROOT / ".cache/camera.json"
    manifest["fixture"] = (
        json.loads(fixture.read_text())
        if fixture.exists()
        else {"scope": "Unknown fixture; acceptance incomplete"}
    )
    checks = []
    results = []
    npm = shutil.which("npm") or "npm"
    for repeat in range(args.runs):
        output = (directory / f"browser-{repeat}.json").resolve()
        with (directory / f"browser-{repeat}.log").open("w") as stream:
            run = subprocess.run(
                [npm, "run", "benchmark"],
                cwd=ROOT / "frontend",
                stdout=stream,
                stderr=subprocess.STDOUT,
                env={
                    **os.environ,
                    "AIMS_TEST_URL": args.url,
                    "AIMS_WORKER": args.worker,
                    "AIMS_BENCHMARK_OUTPUT": str(output),
                },
            )
        if output.exists():
            data = json.loads(output.read_text())
            data["manifest"] = manifest
            output.write_text(json.dumps(data, indent=2) + "\n")
            status = browser_gate(data) if run.returncode == 0 else "Failed"
            results.append(
                {k: v for k, v in data.items() if k not in {"runtime", "manifest"}}
            )
        else:
            status = "Failed"
        checks.append(
            {
                "name": f"browser-{repeat}",
                "status": status,
                "required": True,
                "detail": output.name,
            }
        )
        write_report(directory, manifest, checks, results)
        print(f"Run {repeat + 1}: {status}", flush=True)
    if fingerprint()["source_tree_sha256"] != manifest["source_tree_sha256"]:
        checks.append(
            {
                "name": "source-unchanged",
                "status": "Failed",
                "required": True,
                "detail": "Source changed during benchmark; rerun frozen candidate.",
            }
        )
    write_report(directory, manifest, checks, results)
    print(directory / "report.html", flush=True)
    return 0 if all(c["status"] == "Passed" for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
