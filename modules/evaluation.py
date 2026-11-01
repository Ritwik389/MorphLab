"""Versioned experiment evidence, integrity checks and fail-closed release decisions."""

from __future__ import annotations
import csv
import hashlib
import html
import json
import platform
import subprocess
import sys
from pathlib import Path
import time
import importlib.metadata

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"Passed", "Failed", "Not Run", "Unsupported"}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fingerprint():
    files = sorted(
        p
        for base in ["modules", "frontend/src", "scripts", "tests", "experiments"]
        for p in (ROOT / base).rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".ts", ".tsx", ".css", ".json"}
        and "__pycache__" not in p.parts
    )
    files += [
        ROOT / name
        for name in [
            "app.py",
            "models-manifest.json",
            "requirements-core.txt",
            "requirements-web.txt",
            "requirements-web.lock",
            "requirements-dev.txt",
            "frontend/package.json",
            "frontend/package-lock.json",
            "pyproject.toml",
            "Dockerfile",
        ]
        if (ROOT / name).is_file()
    ]
    hashes = {str(p.relative_to(ROOT)): sha256(p) for p in files}
    product = {
        name: digest
        for name, digest in hashes.items()
        if (
            name.startswith("modules/")
            or name.startswith("frontend/src/")
            or name
            in {
                "app.py",
                "models-manifest.json",
                "requirements-core.txt",
                "requirements-web.txt",
                "requirements-web.lock",
                "frontend/package.json",
                "frontend/package-lock.json",
                "Dockerfile",
            }
        )
        and not name.endswith((".test.ts", ".spec.ts"))
    }
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable (source fingerprint retained)"
    versions = {}
    for name in [
        "numpy",
        "onnx",
        "onnxruntime",
        "torch",
        "coremltools",
        "pillow",
        "fastapi",
        "opencv-python-headless",
        "pytest",
        "hypothesis",
    ]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "git_revision": revision,
        "source_tree_sha256": hashlib.sha256(
            json.dumps(product, sort_keys=True).encode()
        ).hexdigest(),
        "verification_tree_sha256": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "source_files": hashes,
        "python": sys.version,
        "os": platform.platform(),
        "machine": platform.machine(),
        "created_at": time.time(),
        "packages": versions,
    }


def validate_corpus(corpus, check_files=False):
    errors = []
    owners = {}
    ids = set()
    for clip in corpus.get("clips", []):
        if clip["id"] in ids:
            errors.append(f"Duplicate clip {clip['id']}")
        ids.add(clip["id"])
        if clip["split"] not in {"development", "validation", "heldout"}:
            errors.append("Unknown dataset split")
        for identity in clip.get("identities", [clip["identity"]]):
            if identity in owners and owners[identity] != clip["split"]:
                errors.append(f"Identity leakage: {identity}")
            owners[identity] = clip["split"]
        for key in ("sha256", "provenance", "licence"):
            if not clip.get(key):
                errors.append(f"Missing {key}: {clip['id']}")
        if check_files:
            path = (ROOT / clip["path"]).resolve()
            if not path.is_relative_to(ROOT):
                errors.append("Corpus path escapes workspace")
                continue
            if not path.is_file() or sha256(path) != clip["sha256"]:
                errors.append(f"Missing/corrupt clip: {clip['id']}")
    if len(corpus.get("clips", [])) < 30:
        errors.append("At least 30 clips are required")
    if len(owners) < 12:
        errors.append("At least 12 identities are required")
    return errors


def browser_gate(report):
    # A whole-run mean cannot hide a bad 10-second window or duplicate displays.
    windows = report.get("ten_second_windows", [])
    if report.get("duration_seconds", 0) < 119 or len(windows) < 12:
        return "Failed"
    if report.get("unique_frame_ids") != report.get("new_displayed_swaps"):
        return "Failed"
    return (
        "Passed"
        if (
            all(x >= 15 for x in windows[:12])
            and report.get("p95_capture_to_display_ms", float("inf")) < 200
        )
        else "Failed"
    )


def artifact_gate(name, data):
    """Validate measured conditions, not a hand-written Passed label."""
    if name == "m4-browser-performance":
        if "ten_second_windows" in data:
            return browser_gate(data)
        trials = data.get("experiments", [])
        return (
            "Passed"
            if len(trials) >= 5 and all(browser_gate(t) == "Passed" for t in trials)
            else "Failed"
        )
    if name == "100-start-stop":
        return (
            "Passed"
            if data.get("complete")
            and data.get("cycles", 0) >= 100
            and data.get("camera_tracks_released")
            and data.get("server_sessions_released")
            else "Failed"
        )
    if name == "one-hour-soak":
        return (
            "Passed"
            if data.get("complete")
            and data.get("duration_seconds", 0) >= 3600
            and data.get("memory_gate_passed")
            and data.get("frame_progress_verified")
            and data.get("new_displayed_swaps", 0) > 0
            and data.get("camera_tracks_released")
            and data.get("server_sessions_released")
            else "Failed"
        )
    if name == "heldout-tracking":
        return (
            "Passed"
            if data.get("annotations_reviewed")
            and data.get("wrong_person_swaps") == 0
            and data.get("eligible_coverage", 0) >= 0.95
            else "Failed"
        )
    if name == "identity-quality":
        return (
            "Passed"
            if data.get("paired_eligible_samples", 0) > 0
            and data.get("independent_evaluator")
            and data.get("candidate_median", -2)
            >= data.get("baseline_median", 2) - 0.02
            else "Failed"
        )
    if name == "visual-author-review":
        return (
            "Passed"
            if data.get("completed")
            and data.get("reviewer_count", 0) >= 1
            and data.get("ratings")
            and data.get("severe_defect_rate_delta", 1) <= 0
            else "Failed"
        )
    if name == "security-audit":
        dependencies = data.get("dependencies")
        container = data.get("container", {})
        controls = data.get("controls", [])
        return (
            "Passed"
            if dependencies
            and all(not d.get("vulns") for d in dependencies)
            and container.get("completed")
            and container.get("unresolved_high_critical") == 0
            and controls
            and all(c.get("passed") is True for c in controls)
            else "Failed"
        )
    if name in {"native-safari", "physical-webcam"}:
        checks = data.get("checklist", [])
        return (
            "Passed"
            if data.get("completed")
            and data.get("reviewer")
            and checks
            and all(c.get("passed") is True for c in checks)
            else "Failed"
        )
    return "Unsupported"


def write_report(directory, manifest, checks, experiments=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for check in checks:
        if check["status"] not in STATUSES:
            raise ValueError("Unknown evidence status")
    overall = (
        "Passed"
        if checks
        and all(c["status"] == "Passed" for c in checks if c.get("required", True))
        else "Failed"
    )
    data = {
        "schema_version": 1,
        "overall": overall,
        "manifest": manifest,
        "checks": checks,
        "experiments": experiments or [],
    }
    (directory / "report.json").write_text(
        json.dumps(data, indent=2, allow_nan=False) + "\n"
    )
    with (directory / "checks.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["name", "status", "required", "detail"]
        )
        writer.writeheader()
        writer.writerows(
            {k: row.get(k, "") for k in writer.fieldnames} for row in checks
        )
    esc = html.escape
    rows = "".join(
        f"<tr><td>{esc(c['name'])}</td><td>{esc(c['status'])}</td><td>{esc(str(c.get('detail', '')))}</td></tr>"
        for c in checks
    )
    # Standalone offline report: no external scripts and no biometric media.
    content = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MorphLab verification report</title><style>body{{font:16px system-ui;max-width:1100px;margin:48px auto;padding:24px;background:#f5f6f8;color:#1f242c}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:14px;border-bottom:1px solid #dde1e8}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}a{{color:#244ce8}}.status{{font-weight:700}}</style>
<h1>MorphLab verification report</h1><p class="status">Required gates: {overall}</p><p>Schema 1 · Only recorded evidence is shown. Not Run and Unsupported do not pass required gates.</p>
<table><thead><tr><th>Check</th><th>Status</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Experiment results</h2><pre>{esc(json.dumps(experiments or [], indent=2))}</pre>
<h2>Reproduction manifest</h2><pre>{esc(json.dumps({k: v for k, v in manifest.items() if k != "source_files"}, indent=2))}</pre>
<p>Full hashes and results: <a href="report.json">JSON</a> · <a href="checks.csv">CSV</a></p></html>"""
    (directory / "report.html").write_text(content)
    return data
