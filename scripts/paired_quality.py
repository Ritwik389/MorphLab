#!/usr/bin/env python3
"""Paired clip-level identity differences; keep missed edits in coverage denominators."""

import argparse
import json
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    grouped = {}
    for path in args.directory.glob("*.json"):
        data = json.loads(path.read_text())
        if "candidate" in data:
            grouped.setdefault(data["candidate"]["name"], []).append(data)
    baseline, candidate = grouped["mobile-binary"], grouped["mobile-calibrated"]

    def positions(runs):
        result = {}
        for run in runs:
            for row in run["rows"]:
                if row.get("identity_cosine") is not None:
                    result.setdefault((row["clip"], row["frame"]), []).append(
                        row["identity_cosine"]
                    )
        return {key: statistics.mean(value) for key, value in result.items()}

    left, right = positions(baseline), positions(candidate)
    common = left.keys() & right.keys()
    clips = {}
    for key in common:
        clips.setdefault(key[0], []).append((left[key], right[key]))
    rows = [
        {
            "clip": clip,
            "positions": len(values),
            "baseline_median": statistics.median(x[0] for x in values),
            "candidate_median": statistics.median(x[1] for x in values),
            "paired_median_delta": statistics.median(x[1] - x[0] for x in values),
        }
        for clip, values in sorted(clips.items())
    ]
    deltas = [row["paired_median_delta"] for row in rows]
    rng = random.Random(2401)
    boot = sorted(
        statistics.median(rng.choices(deltas, k=len(deltas))) for _ in range(2000)
    )
    result = {
        "schema_version": 1,
        "manifest": fingerprint(),
        "split": "validation",
        "scope": "Five-repeat validation comparison; repeats/frames aggregated within clips, not treated as independent subjects. Not held-out acceptance.",
        "independent_evaluator": candidate[0]["evaluator"],
        "paired_eligible_samples": len(common),
        "candidate_median": statistics.median(row["candidate_median"] for row in rows),
        "baseline_median": statistics.median(row["baseline_median"] for row in rows),
        "paired_median_delta": statistics.median(deltas),
        "clip_bootstrap_95_ci": [boot[49], boot[1949]],
        "engineering_tolerance": 0.02,
        "engineering_tolerance_met": statistics.median(deltas) >= -0.02,
        "candidate_samples": sum(len(run["rows"]) for run in candidate),
        "candidate_swapped_samples": sum(
            row.get("swapped", False) for run in candidate for row in run["rows"]
        ),
        "recognition_failures": sum(
            row.get("recognition_failed", False)
            for run in candidate
            for row in run["rows"]
        ),
        "clips": rows,
        "heldout_acceptance": "Not Run",
    }
    path = args.directory / "paired-quality.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"manifest", "clips", "independent_evaluator"}
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
