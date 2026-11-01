"""Measure real backend swaps, not recycled display frames. Browser latency is separate."""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.runtime import registry
from modules.studio_live import LiveSession

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=float, default=120)
parser.add_argument('--output', default='outputs/benchmarks/studio.json')
parser.add_argument('--live-model', action='store_true')
args = parser.parse_args()
source = cv2.imread(str(ROOT / 'assets/examples/source.png'))
frame = cv2.imread(str(ROOT / 'assets/examples/target.jpg'))
frame = cv2.resize(frame, (409, 480))
session = LiveSession()
session.set_source(registry.live_source(source) if args.live_model else registry.source(source))
session.mode = 'swap'
for i in range(8):
    session.process({'frame_id':i, 'revision':1, 'captured_at':0}, frame)
started = time.perf_counter()
timings = []
frames = swaps = 0
import struct
while time.perf_counter()-started < args.seconds:
    start = time.perf_counter()
    packet = session.process({'frame_id':frames+8, 'revision':1, 'captured_at':0}, frame)
    size = struct.unpack('!I', packet[:4])[0]
    header = json.loads(packet[4:4+size])
    timings.append((time.perf_counter()-start)*1000)
    frames += 1
    swaps += int(header['swapped'])
duration = time.perf_counter()-started
report = {'scope':'backend replay of a static portrait; not physical-camera or browser latency',
          'duration_seconds':duration, 'frames':frames, 'new_swaps':swaps,
          'processed_fps':frames/duration, 'swapped_fps':swaps/duration,
          'p95_processing_ms':float(np.percentile(timings,95)), 'runtime':registry.status(),
          'backend_15fps_passed':swaps/duration>=15,
          'full_acceptance':'Requires browser replay and physical camera verification'}
path = ROOT / args.output
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
