#!/usr/bin/env python3
"""Fetch the research models pinned by URL and SHA-256 in models-manifest.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.paths import MODELS_DIR
from modules.utilities import conditional_download


def main():
    manifest = json.loads((ROOT / 'models-manifest.json').read_text())
    for model in manifest['models']:
        destination = Path(MODELS_DIR) / model['path']
        conditional_download(str(destination.parent), [model['url']],
                             {destination.name: model['sha256']})
        print(f'Verified: {model["path"]}')


if __name__ == '__main__':
    main()
