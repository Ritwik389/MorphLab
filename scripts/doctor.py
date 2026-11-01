#!/usr/bin/env python3
"""Check local readiness, optionally hashing every model file."""
import argparse
import importlib.util
import json
import hashlib
import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-models', action='store_true')
    args = parser.parse_args()
    checks = {'python_3_11': sys.version_info[:2] == (3, 11),
              'ffmpeg': bool(shutil.which('ffmpeg')), 'ffprobe': bool(shutil.which('ffprobe'))}
    for name in ['numpy', 'cv2', 'onnxruntime', 'onnx', 'insightface', 'PIL', 'fastapi', 'uvicorn', 'websockets', 'multipart']:
        checks[name] = importlib.util.find_spec(name) is not None
    providers = []
    if checks['onnxruntime']:
        import onnxruntime
        providers = onnxruntime.get_available_providers()
    models_dir = Path(os.environ.get('AIMS_MODELS_DIR', str(ROOT/'models')))
    models = json.loads((ROOT/'models-manifest.json').read_text())['models']
    for model in models:
        path = models_dir/model['path']
        good = path.is_file() and path.stat().st_size == model['bytes']
        if good and args.verify_models:
            with path.open('rb') as stream:
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
                good = digest.hexdigest() == model['sha256']
        checks[model['path']] = good
    checks['frontend_build'] = (ROOT/'frontend/dist/index.html').is_file()
    optional = {'native_coreml_variants': len(list((ROOT/'.cache/coreml').glob('*/manifest.json'))),
                'mobile_weights': (models_dir/'mobilefaceswap/manifest.json').is_file(),
                'legacy_gradio': importlib.util.find_spec('gradio') is not None}
    print(json.dumps({'python': sys.version.split()[0], 'platform': platform.platform(),
                      'providers': providers, 'checks': checks,
                      'optional_acceleration': optional,
                      'ready': all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
