#!/usr/bin/env python3
"""Package reports/code/manifests, excluding recordings, embeddings and model weights."""

from pathlib import Path
import argparse
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import sha256


def has_biometric_vectors(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                any(
                    word in key.lower()
                    for word in ["embedding", "latent", "identity_feature"]
                )
                and isinstance(item, list)
                and len(item) > 16
                and all(isinstance(x, (int, float)) for x in item)
            ):
                return True
            if has_biometric_vectors(item):
                return True
    elif isinstance(value, list):
        return any(has_biometric_vectors(item) for item in value)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/aims-flagship-evidence.zip"
    )
    args = parser.parse_args()
    directories = [
        "finalized-regression",
        "finalized-longevity",
        "finalized-m4-performance",
        "finalized-coreml-pilot",
        "finalized-browser-pipeline",
        "finalized-ablations",
        "frozen-validation",
        "development-screening",
        "mask-validation",
        "photo-baselines-verified",
        "recovery-comparison",
        "container-finalized-smoke",
        "flagship-release",
    ]
    files = set()
    for directory in directories:
        for path in (ROOT / "outputs/evaluations" / directory).rglob("*"):
            if "artifacts" in path.parts:
                continue
            if path.is_file() and (
                path.suffix in {".json", ".csv", ".xml", ".html", ".log", ".md", ".svg"}
                or path.name in {"quality-latency.png", "memory-curve.png"}
            ):
                files.add(path)
    for directory in ["docs", "scripts", "tests", "experiments"]:
        files.update(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and path.suffix in {".md", ".py", ".json"}
            and "__pycache__" not in path.parts
            and path.name != "local-evidence.json"
        )
    for directory in [
        "modules",
        "frontend/src",
        "frontend/tests",
        "third_party",
        ".github",
    ]:
        files.update(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and path.suffix
            in {".py", ".ts", ".tsx", ".css", ".json", ".md", ".yml", ".yaml", ".txt"}
            and "__pycache__" not in path.parts
        )
    files.update(
        path
        for path in (ROOT / "third_party").rglob("*")
        if path.is_file() and "LICENSE" in path.name
    )
    files.update(
        path
        for path in (ROOT / "frontend").iterdir()
        if path.is_file() and path.suffix in {".json", ".ts", ".html"}
    )
    for name in [
        "manifest.json",
        "ATTRIBUTION.md",
        "source.png",
        "target.jpg",
        "sally.jpg",
        "katherine.jpg",
        "text-only.png",
        "no-face.png",
        "rotated.jpg",
        "blurred.jpg",
        "multiple-faces.jpg",
        "demo-result.jpg",
    ]:
        path = ROOT / "assets/examples" / name
        if path.is_file():
            files.add(path)
    for name in [
        "models-manifest.json",
        "README.md",
        "requirements-web.lock",
        "requirements-build.lock",
        "requirements-mac.txt",
        "Dockerfile",
        "compose.yaml",
        ".dockerignore",
        ".gitignore",
        "app.py",
        "legacy_app.py",
        "run.py",
        "pyproject.toml",
        "requirements-dev.txt",
        "requirements-core.txt",
        "requirements-web.txt",
        "requirements-build.txt",
    ]:
        files.add(ROOT / name)
    for name in [
        "hardware.json",
        "external-tools.json",
        "readiness-verified.json",
        "verification-source-manifest.json",
        "security-evidence.json",
        "production-sbom.json",
        "dependency-audit-patched.json",
        "container-finalized-trivy.json",
        "clean-model-smoke.json",
        "short-audio-media-check.log",
        "rotated-video-reproduction.log",
    ]:
        path = ROOT / "outputs/evaluations" / name
        if path.is_file():
            files.add(path)
    # Preserve the first complete-hour infrastructure failure without raw camera traces.
    for name in ["browser.log", "report.json", "browser-soak.json"]:
        path = ROOT / "outputs/evaluations/release-longevity" / name
        if path.is_file():
            files.add(path)
    for name in ["source.tar.gz", "manifest.json"]:
        path = ROOT / ".cache/evaluation/pre-flagship" / name
        if path.is_file():
            files.add(path)
    lock = ROOT / ".cache/evaluation/upstream-requirements.lock"
    if lock.is_file():
        files.add(lock)
    for path in files:
        if path.suffix == ".json" and has_biometric_vectors(
            json.loads(path.read_text())
        ):
            raise ValueError(
                "Refusing to package a raw biometric vector: "
                + str(path.relative_to(ROOT))
            )
    inventory = {str(path.relative_to(ROOT)): sha256(path) for path in sorted(files)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, str(path.relative_to(ROOT)))
        archive.writestr("CONTENTS.json", json.dumps(inventory, indent=2) + "\n")
        archive.writestr(
            "PACKAGE.md",
            "# MorphLab evidence package\n\nStart with outputs/evaluations/flagship-release/report.html and docs/FLAGSHIP_CASE_STUDY.md. Required missing/failed checks remain visible. Commands are in docs/TEST_STRATEGY.md. Raw recordings, private thumbnails, embeddings, browser traces and model weights are intentionally excluded. Fetch licensed inputs/models using the maintained scripts; do not infer public deployment approval from this archive.\n",
        )
    args.output.with_suffix(".sha256").write_text(
        sha256(args.output) + "  " + args.output.name + "\n"
    )
    print(args.output)


if __name__ == "__main__":
    main()
