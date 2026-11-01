#!/usr/bin/env python3
"""Run matched video ablations; save actual media, raw reports, JSON and CSV."""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--source', required=True)
    parser.add_argument('-t', '--target', required=True)
    parser.add_argument('--output-dir', default=str(ROOT/'outputs'/'benchmarks'/str(int(time.time()))))
    parser.add_argument('--provider', default='cpu')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--interval', type=int, default=3, choices=range(1, 11))
    parser.add_argument('--variants', nargs='+', choices=['baseline', 'tracked', 'adaptive'],
                        default=['baseline', 'tracked', 'adaptive'])
    args = parser.parse_args()
    directory = Path(args.output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for strategy in dict.fromkeys(args.variants):
        output, report = directory/f'{strategy}.mp4', directory/f'{strategy}.json'
        print(f'Running {strategy}...', flush=True)
        # Preserve logs for diagnosis and avoid keeping the whole encoder log in RAM.
        with (directory/f'{strategy}.log').open('w') as log:
            subprocess.run([sys.executable, str(ROOT/'run.py'),
                '-s', str(Path(args.source).resolve()), '-t', str(Path(args.target).resolve()),
                '-o', str(output), '--execution-provider', args.provider,
                '--execution-threads', str(args.threads), '--max-memory', '0',
                '--temporal-strategy', strategy, '--detection-interval', str(args.interval),
                '--research-report', str(report)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=1800)
        data = json.loads(report.read_text())
        rows.append({'strategy': strategy, 'frames': data['frames_processed'],
                     'face_edits': data['face_edits'], 'detector_calls': data['detector_calls'],
                     'processing_fps_excluding_io': data['processing_fps_excluding_io'],
                     'latency_p95_ms': data['latency']['total_ms']['p95'],
                     'identity_cosine': data['source_output_embedding_cosine_mean'],
                     'temporal_residual_change': data['aligned_edit_residual_change_mean_0_255'],
                     'end_to_end_seconds': data['end_to_end_seconds']})
    with (directory/'comparison.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (directory/'comparison.json').write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))
    print(f'Results: {directory}', flush=True)


if __name__ == '__main__':
    main()
