#!/usr/bin/env python3
"""Run isolated browser lifecycle checks, optionally including a real one-hour soak."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import artifact_gate, fingerprint, write_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--soak", action="store_true", help="Enable the full one-hour browser test"
    )
    parser.add_argument("--port", type=int, default=7863)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    directory = (
        args.output
        or ROOT / "outputs/evaluations" / f"longevity-{time.strftime('%Y%m%d-%H%M%S')}"
    ).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest = fingerprint()
    manifest.update(
        suite="browser-longevity", model_setting=os.getenv("AIMS_LIVE_MODEL", "auto")
    )
    url = f"http://127.0.0.1:{args.port}"
    # Refuse to attach to or terminate an unrelated server.
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    checks = []
    with (directory / "server.log").open("w") as server_log:
        server = subprocess.Popen(
            [sys.executable, "app.py", "--port", str(args.port)],
            cwd=ROOT,
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError(
                        "Test server stopped during startup; inspect server.log"
                    )
                try:
                    with urllib.request.urlopen(
                        url + "/api/system", timeout=2
                    ) as response:
                        status = json.load(response)
                    if (
                        status.get("source_tree_sha256")
                        != manifest["source_tree_sha256"]
                    ):
                        raise RuntimeError(
                            "Server source snapshot does not match the test manifest"
                        )
                    break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(1)
            else:
                raise RuntimeError("Test server did not become ready")
            npm = shutil.which("npm") or "npm.cmd"
            env = {
                **os.environ,
                "AIMS_TEST_URL": url,
                "AIMS_RUN_SOAK": "1" if args.soak else "0",
                "AIMS_LONGEVITY_OUTPUT": str(directory),
            }
            with (directory / "browser.log").open("w") as log:
                run = subprocess.run(
                    [
                        npm,
                        "exec",
                        "--",
                        "playwright",
                        "test",
                        "--config",
                        "playwright.longevity.config.ts",
                    ],
                    cwd=ROOT / "frontend",
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=3900,
                )
            for gate, name in [
                ("100-start-stop", "lifecycle-100.json"),
                ("one-hour-soak", "browser-soak.json"),
            ]:
                path = directory / name
                result = "Not Run"
                if path.is_file():
                    data = json.loads(path.read_text())
                    data["manifest"] = manifest
                    path.write_text(json.dumps(data, indent=2) + "\n")
                    result = artifact_gate(gate, data)
                checks.append(
                    {
                        "name": gate,
                        "status": result,
                        "required": gate != "one-hour-soak" or args.soak,
                        "detail": name,
                    }
                )
            checks.append(
                {
                    "name": "browser-process",
                    "status": "Passed" if run.returncode == 0 else "Failed",
                    "required": True,
                    "detail": "browser.log; first failures retained",
                }
            )
            if fingerprint()["source_tree_sha256"] != manifest["source_tree_sha256"]:
                checks.append(
                    {
                        "name": "source-unchanged",
                        "status": "Failed",
                        "required": True,
                        "detail": "Source changed during the test. Rerun the frozen candidate.",
                    }
                )
        finally:
            server.terminate()
            try:
                server.wait(15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
    report = write_report(directory, manifest, checks)
    print(directory / "report.html", flush=True)
    return 0 if report["overall"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
