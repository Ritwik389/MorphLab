#!/usr/bin/env python3
"""Build the same deployment image with host-downloaded, hash-checked Linux wheels.

Useful when Docker Desktop's registry network is much slower than the host.
The maintained Dockerfile remains usable without this helper.
"""

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="morphlab-studio:flagship")
    parser.add_argument("--arch", choices=["aarch64", "x86_64"], default="aarch64")
    args = parser.parse_args()
    directory = ROOT / ".cache/wheels-linux"
    directory.mkdir(parents=True, exist_ok=True)
    lock = (ROOT / "requirements-web.lock").read_text()
    groups = re.split(r"(?=^[a-zA-Z0-9][a-zA-Z0-9_.-]*==)", lock, flags=re.M)
    binary = "".join(
        g
        for g in groups
        if not (g.startswith("insightface==") or g.startswith("psutil=="))
    )
    source = "".join(
        g for g in groups if (g.startswith("insightface==") or g.startswith("psutil=="))
    )
    (directory / "binary.lock").write_text(binary)
    (directory / "source.lock").write_text(source)
    pip = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(directory),
        "--no-deps",
    ]
    platforms = [
        f"manylinux_2_28_{args.arch}",
        f"manylinux2014_{args.arch}",
        f"manylinux_2_17_{args.arch}",
    ]
    target = ["--python-version", "311", "--implementation", "cp", "--abi", "cp311"]
    for platform in platforms:
        target += ["--platform", platform]
    subprocess.run(
        pip
        + target
        + [
            "--only-binary=:all:",
            "--require-hashes",
            "-r",
            str(directory / "binary.lock"),
        ],
        check=True,
    )
    subprocess.run(
        pip
        + [
            "--no-binary=:all:",
            "--require-hashes",
            "-r",
            str(directory / "source.lock"),
        ],
        check=True,
    )
    subprocess.run(
        pip
        + target
        + [
            "--only-binary=:all:",
            "pip==26.2.2",
            "setuptools==84.2.1",
            "wheel==0.48.0",
            "cython==3.3.0",
        ],
        check=True,
    )
    original = (ROOT / "Dockerfile").read_text()
    old = "RUN python -m pip install pip==26.2.2 setuptools==84.2.1 wheel==0.48.0 cython==3.3.0 numpy==1.26.4 && python -m pip install --ignore-installed --prefix=/install --no-build-isolation --require-hashes -r requirements-web.lock"
    new = "COPY --from=wheels / /tmp/wheels/\nRUN python -m pip install --no-index --find-links=/tmp/wheels pip==26.2.2 setuptools==84.2.1 wheel==0.48.0 cython==3.3.0 numpy==1.26.4 && python -m pip install --no-index --find-links=/tmp/wheels --ignore-installed --prefix=/install --no-build-isolation --require-hashes -r requirements-web.lock && rm -rf /tmp/wheels"
    if old not in original:
        raise ValueError(
            "Dockerfile dependency stage changed; review the offline builder before use."
        )
    dockerfile = ROOT / ".cache/Dockerfile.offline"
    dockerfile.write_text(original.replace(old, new))
    subprocess.run(
        [
            "docker",
            "build",
            "--build-context",
            f"wheels={directory}",
            "--build-arg",
            "DOWNLOAD_MODELS=0",
            "-f",
            str(dockerfile),
            "-t",
            args.tag,
            str(ROOT),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
