#!/usr/bin/env python3
"""Install the pinned production environment with a compatible native build ABI."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("Use Python 3.11 for this locked and validated runtime.")
    os.environ.setdefault("PIP_CACHE_DIR", str(ROOT / ".cache/pip"))
    pip = [sys.executable, "-m", "pip", "install"]
    subprocess.run(
        pip + ["--require-hashes", "--no-deps", "-r", "requirements-build.lock"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        pip
        + ["--require-hashes", "--no-build-isolation", "-r", "requirements-web.lock"],
        cwd=ROOT,
        check=True,
    )
    if args.dev:
        subprocess.run(pip + ["-r", "requirements-dev.txt"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
