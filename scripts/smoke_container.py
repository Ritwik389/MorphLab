#!/usr/bin/env python3
"""Smoke-test a local image with actual CPU inference, then remove the owned container."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="morphlab-studio:flagship")
    parser.add_argument("--models", type=Path, default=ROOT / "models")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "outputs/evaluations"
        / f"container-{time.strftime('%Y%m%d-%H%M%S')}",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = fingerprint()
    name = "aims-smoke-" + uuid.uuid4().hex[:12]
    created = False
    report = {
        "complete": False,
        "manifest": manifest,
        "scope": "Linux CPU container, two CPUs/four GiB, read-only models, real photo inference; no Mac GPU claim",
    }
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                name,
                "--cpus",
                "2",
                "--memory",
                "4g",
                "-p",
                "127.0.0.1::7860",
                "-v",
                f"{args.models.resolve()}:/app/models:ro",
                args.image,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        created = True
        address = (
            subprocess.check_output(["docker", "port", name, "7860/tcp"], text=True)
            .strip()
            .splitlines()[0]
        )
        url = "http://" + address
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                system = requests.get(url + "/api/system", timeout=5)
                if system.ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Container did not become ready in 120 seconds")
        if system.json().get("source_tree_sha256") != manifest["source_tree_sha256"]:
            raise RuntimeError(
                "Container and host source snapshots differ; rebuild the image"
            )
        session = requests.post(url + "/api/sessions", timeout=10).json()["id"]
        assert requests.delete(url + "/api/sessions/" + session, timeout=10).json()[
            "deleted"
        ]
        started = time.monotonic()
        with (
            (ROOT / "assets/examples/source.png").open("rb") as source,
            (ROOT / "assets/examples/target.jpg").open("rb") as target,
        ):
            response = requests.post(
                url + "/api/jobs",
                data={"kind": "photo", "mode": "swap", "consent": "true"},
                files={
                    "source": ("source.png", source, "image/png"),
                    "target": ("target.jpg", target, "image/jpeg"),
                },
                timeout=60,
            )
        response.raise_for_status()
        job = response.json()
        polls = []
        while time.monotonic() - started < 240:
            tick = time.monotonic()
            status = requests.get(url + "/api/jobs/" + job["id"], timeout=60)
            status.raise_for_status()
            job = status.json()
            polls.append(
                {
                    "elapsed_seconds": time.monotonic() - started,
                    "request_seconds": time.monotonic() - tick,
                    "state": job["state"],
                }
            )
            if job["state"] in {"complete", "error", "cancelled"}:
                break
            time.sleep(1)
        if job["state"] != "complete":
            # Preserve server diagnostics before the owned container is removed.
            # This smoke test only submits the bundled public example pair.
            diagnostic = args.output / "processing.log"
            subprocess.run(
                ["docker", "cp", f"{name}:/app/outputs/web/{job['id']}/processing.log", str(diagnostic)],
                check=False,
                capture_output=True,
            )
            if diagnostic.exists():
                report["diagnostic"] = diagnostic.name
            raise RuntimeError(job.get("message", "Photo job did not complete"))
        result = requests.get(url + job["result"], timeout=60)
        result.raise_for_status()
        assert (
            result.headers["content-type"].startswith("image/png")
            and len(result.content) > 1000
        )
        assert job["report"]["mean_absolute_pixel_change_0_255"] > 0.1
        system = requests.get(url + "/api/system", timeout=10).json()
        assert "CPUExecutionProvider" in system["active_runtime"]
        image = json.loads(
            subprocess.check_output(
                ["docker", "image", "inspect", args.image], text=True
            )
        )[0]
        report.update(
            complete=True,
            runtime=system,
            image_id=image["Id"],
            duration_seconds=time.monotonic() - started,
            result_sha256=hashlib.sha256(result.content).hexdigest(),
            result_bytes=len(result.content),
            pixel_change_mean_0_255=job["report"]["mean_absolute_pixel_change_0_255"],
            polls=polls,
            session_cleanup_passed=True,
        )
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if created:
            with (args.output / "container.log").open("w") as stream:
                subprocess.run(
                    ["docker", "logs", name],
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            subprocess.run(["docker", "stop", name], check=False, capture_output=True)
        (args.output / "smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    print(args.output / "smoke.json")
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
