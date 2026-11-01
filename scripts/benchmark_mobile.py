"""Validate and benchmark the released MobileFaceSwap weights on this Mac."""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.mobile_model import MobileRuntime
from modules.runtime import registry, paste_face

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=float, default=10)
args = parser.parse_args()
if not torch.backends.mps.is_available():
    raise RuntimeError('MPS is unavailable on this machine.')
directory = ROOT / 'models/mobilefaceswap'
engine = MobileRuntime(directory, 'mps')
source = cv2.imread(str(ROOT / 'assets/examples/source.png'))
target = cv2.imread(str(ROOT / 'assets/examples/target.jpg'))
source_face = registry.detect(source)[0]
face = registry.detect(target)[0]
identity = engine.source(source, source_face)
for _ in range(4):
    fake, transform, mask = engine.predict(target, face, identity)
cpu_identity = engine.source(source, source_face).cpu()
engine.device = 'cpu'
reference, _, _ = engine.predict(target, face, cpu_identity)
engine.device = 'mps'
mae = float(np.abs(fake.astype(float)-reference.astype(float)).mean())
start = time.perf_counter()
timings = []
while time.perf_counter()-start < args.seconds:
    at = time.perf_counter()
    fake, transform, mask = engine.predict(target, face, identity)
    result = paste_face(target, fake, transform, mask)
    timings.append((time.perf_counter()-at)*1000)
cv2.imwrite(str(ROOT / 'outputs/mobile-demo.jpg'), result)
weights = {}
for filename in ['arcface.pdparams', 'MobileFaceSwap_224.pdparams']:
    with (directory/filename).open('rb') as stream:
        weights[filename] = hashlib.file_digest(stream, 'sha256').hexdigest()
manifest = {'model':'MobileFaceSwap_224', 'runtime':'PyTorch MPS', 'port_version':1,
    'torch':torch.__version__, 'macos':platform.mac_ver()[0], 'weights':weights,
    'duration_seconds':time.perf_counter()-start, 'samples':len(timings),
    'mean_ms':float(np.mean(timings)), 'p95_ms':float(np.percentile(timings,95)),
    'mps_cpu_pixel_mae_0_255':mae, 'validated':mae<=2 and np.isfinite(fake).all().item(),
    'scope':'alignment, new model inference, mask and compositing; fixed detected face; not webcam FPS'}
previous = directory/'manifest.json'
if previous.exists():
    old = json.loads(previous.read_text())
    if old.get('weights') == weights and old.get('port_version') == 1:
        manifest['paddle_reference_parity'] = old.get('paddle_reference_parity', [])
(directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
