#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo 'Native Mac acceleration setup requires Apple Silicon.'
  exit 1
fi
if command -v uv >/dev/null; then
  uv --cache-dir .cache/uv pip install --python .venv/bin/python -r requirements-mac.txt
else
  .venv/bin/python -m pip install -r requirements-mac.txt
fi
.venv/bin/python scripts/convert_coreml.py --precision fp16
.venv/bin/python scripts/convert_coreml.py --precision int8
.venv/bin/python scripts/download_mobile.py
.venv/bin/python scripts/benchmark_mobile.py
echo 'Mac runtimes validated. Start MorphLab with ./scripts/start_local.sh'
