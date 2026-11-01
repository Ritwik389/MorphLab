#!/usr/bin/env python3
"""Cross-platform verification with explicit evidence status and reproducible artefacts."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import fingerprint, validate_corpus, write_report


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--suite",
        choices=["smoke", "regression", "evaluation", "release"],
        default="smoke",
    )
    p.add_argument("--output")
    p.add_argument("--evidence", type=Path)
    p.add_argument("--url", default="http://127.0.0.1:7860")
    args = p.parse_args()
    directory = Path(
        args.output
        or ROOT
        / "outputs/evaluations"
        / f"{args.suite}-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    checks = []
    manifest = fingerprint()
    manifest["suite"] = args.suite

    def run(name, cmd, cwd=ROOT, timeout=600):
        log = directory / (name + ".log")
        try:
            with log.open("w") as stream:
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    env={
                        **os.environ,
                        "AIMS_TEST_URL": args.url,
                        "PYTHONHASHSEED": "0",
                    },
                )
            status = "Passed" if result.returncode == 0 else "Failed"
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.write_text(str(exc))
            status = "Failed"
        checks.append(
            {"name": name, "status": status, "required": True, "detail": log.name}
        )
        print(f"{name}: {status}", flush=True)

    npm = shutil.which("npm") or ("npm.cmd" if os.name == "nt" else "npm")
    if args.suite in {"smoke", "regression", "release"}:
        run(
            "backend-static",
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "modules/studio_live.py",
                "modules/source_checks.py",
                "modules/evaluation.py",
                "scripts/verify.py",
            ],
        )
        tests = (
            ["tests/test_studio.py", "tests/test_flagship.py"]
            if args.suite == "smoke"
            else ["tests"]
        )
        run(
            "backend",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--basetemp=" + str((directory / "pytest-temp").resolve()),
                "--cov=modules",
                "--cov-report=json:" + str((directory / "coverage.json").resolve()),
                *tests,
                "--junitxml=" + str((directory / "pytest.xml").resolve()),
            ],
        )
        if args.suite != "smoke":
            model_tests = []
            junit = directory / "pytest.xml"
            if junit.exists():
                model_tests = [
                    t
                    for t in ET.parse(junit).iter("testcase")
                    if "test_model_integration" in t.get("classname", "")
                ]
            model_status = "Not Run"
            if model_tests:
                model_status = (
                    "Failed"
                    if any(
                        t.find("failure") is not None or t.find("error") is not None
                        for t in model_tests
                    )
                    else (
                        "Not Run"
                        if any(t.find("skipped") is not None for t in model_tests)
                        else "Passed"
                    )
                )
            checks.append(
                {
                    "name": "actual-cpu-model-integration",
                    "status": model_status,
                    "required": True,
                    "detail": f"{len(model_tests)} model tests in pytest.xml; mocked tests cannot satisfy this check",
                }
            )
        junit = directory / "pytest.xml"
        if junit.exists():
            skipped = [
                t.get("name", "")
                for t in ET.parse(junit).iter("testcase")
                if t.find("skipped") is not None
                and t.get("name")
                != "test_model_provenance_does_not_become_a_gradio_file_download"
            ]
            checks.append(
                {
                    "name": "required-backend-checks-executed",
                    "status": "Not Run" if skipped else "Passed",
                    "required": True,
                    "detail": "Skipped: " + ", ".join(skipped)
                    if skipped
                    else "No required tests skipped; legacy Gradio is explicitly optional",
                }
            )
        run("frontend-build", [npm, "run", "build"], ROOT / "frontend")
        run("frontend-unit", [npm, "run", "test:unit"], ROOT / "frontend")
        if args.suite != "smoke":
            run("browser", [npm, "test"], ROOT / "frontend")
    if args.suite in {"evaluation", "release"}:
        corpus_file = ROOT / "experiments/corpus.json"
        errors = (
            validate_corpus(json.loads(corpus_file.read_text()), True)
            if corpus_file.exists()
            else ["Corpus missing"]
        )
        checks.append(
            {
                "name": "corpus-integrity",
                "status": "Failed" if errors else "Passed",
                "required": True,
                "detail": "; ".join(errors)
                or "30+ clips, 12+ identity-disjoint identities; hashes verified",
            }
        )
        evidence = (
            json.loads(args.evidence.read_text())
            if args.evidence and args.evidence.exists()
            else {}
        )
        required = [
            "heldout-tracking",
            "m4-browser-performance",
            "identity-quality",
            "visual-author-review",
            "one-hour-soak",
            "100-start-stop",
            "native-safari",
            "physical-webcam",
            "security-audit",
        ]
        corpus = json.loads(corpus_file.read_text()) if corpus_file.exists() else {}
        checks.append(
            {
                "name": "corpus-reviewed-frozen",
                "status": "Passed"
                if corpus.get("frozen")
                and all(c.get("annotations_reviewed") for c in corpus.get("clips", []))
                else "Not Run",
                "required": True,
                "detail": "Held-out annotations and freeze must be reviewed before selection.",
            }
        )
        for name in required:
            entry = evidence.get(name)
            # Imported claims must bind to this exact source digest and have an actual artefact.
            valid = (
                entry
                and entry.get("source_tree_sha256") == manifest["source_tree_sha256"]
                and entry.get("artifact")
                and Path(entry["artifact"]).is_file()
                and entry.get("sha256")
            )
            if valid:
                from modules.evaluation import sha256, artifact_gate

                valid = sha256(entry["artifact"]) == entry["sha256"]
            status = "Not Run"
            if valid:
                try:
                    status = artifact_gate(
                        name, json.loads(Path(entry["artifact"]).read_text())
                    )
                except (ValueError, TypeError, KeyError):
                    status = "Failed"
            checks.append(
                {
                    "name": name,
                    "status": status,
                    "required": True,
                    "detail": entry.get("artifact", "")
                    if valid
                    else "No current, hash-verified evidence supplied.",
                }
            )
    data = write_report(directory, manifest, checks)
    print(f"Report: {directory.resolve() / 'report.html'}")
    return 0 if data["overall"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
