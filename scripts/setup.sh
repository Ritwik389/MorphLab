#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${AIMS_PYTHON:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null; then PYTHON_BIN=python3; fi
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python scripts/install_runtime.py
.venv/bin/python scripts/download_models.py
(cd frontend && npm ci && npm run build)
if [ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] && [ "${AIMS_SKIP_ACCELERATION:-0}" != 1 ]; then
  bash scripts/setup_mac_acceleration.sh
fi
.venv/bin/python scripts/doctor.py --verify-models
