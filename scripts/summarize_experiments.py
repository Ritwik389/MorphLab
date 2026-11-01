#!/usr/bin/env python3
"""Aggregate repeated screens, bootstrap by clip and plot quality/latency trade-offs."""

import argparse
import json
import os
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import fingerprint, write_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    grouped = {}
    for file in args.directory.glob("*.json"):
        data = json.loads(file.read_text())
        if "candidate" not in data:
            continue
        grouped.setdefault(data["candidate"]["name"], []).append(data)
    summaries = []
    rng = random.Random(2401)
    for name, runs in grouped.items():
        rows = [row for run in runs for row in run["rows"]]
        clips = {}
        for row in rows:
            if row.get("identity_cosine") is not None:
                clips.setdefault(row["clip"], []).append(row["identity_cosine"])
        values = [statistics.mean(v) for v in clips.values()]
        boot = []
        if values:
            boot = sorted(
                statistics.mean(rng.choices(values, k=len(values))) for _ in range(2000)
            )
        summaries.append(
            {
                "candidate": name,
                "runs": len(runs),
                "samples": len(rows),
                "swapped_samples": sum(r.get("swapped", False) for r in rows),
                "coverage": sum(r.get("swapped", False) for r in rows)
                / max(1, len(rows)),
                "median_p95_backend_ms": statistics.median(
                    run["summary"]["processing_p95_ms"]
                    for run in runs
                    if run["summary"]["processing_p95_ms"] is not None
                ),
                "mean_clip_identity_cosine": statistics.mean(values)
                if values
                else None,
                "clip_bootstrap_95_ci": [boot[49], boot[1949]] if boot else None,
                "full_live_acceptance": "Not Run",
                "split": runs[0]["split"],
                "quality_scope": runs[0]["scope"],
                "measurement_source_trees": sorted({run["manifest"]["source_tree_sha256"] for run in runs}),
            }
        )
    checks = [
        {
            "name": s["candidate"] + "-required-repeats",
            "status": "Passed" if s["runs"] >= (5 if s["split"] == "validation" else 3) else "Failed",
            "required": True,
            "detail": f"{s['runs']} isolated runs; {s['swapped_samples']}/{s['samples']} samples swapped",
        }
        for s in summaries
    ]
    checks.append(
        {
            "name": "heldout-release-acceptance",
            "status": "Not Run",
            "required": True,
            "detail": "Reviewed frozen annotations, physical camera and full release evidence remain separate.",
        }
    )
    manifest = fingerprint()
    split = next(iter(grouped.values()))[0]["split"] if grouped else "unknown"
    manifest["suite"] = split + "-screening-summary"
    write_report(args.directory, manifest, checks, summaries)
    (args.directory / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 7))
    for row in summaries:
        x = row["median_p95_backend_ms"]
        y = row["mean_clip_identity_cosine"]
        if y is None:
            continue
        ci = row["clip_bootstrap_95_ci"]
        ax.errorbar(x, y, yerr=[[y - ci[0]], [ci[1] - y]], fmt="o", capsize=4)
        ax.annotate(
            row["candidate"],
            (x, y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set(
        xlabel="Median repeated backend p95 (ms; sparse frames, not browser latency)",
        ylabel="Mean per-clip AdaFace cosine (heuristic)",
        title=f"MorphLab {split} trade-offs · full live acceptance evaluated separately",
    )
    ax.set_xscale("log")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.directory / "quality-latency.png", dpi=160)
    fig.savefig(args.directory / "quality-latency.svg")
    import base64

    report = args.directory / "report.html"
    embedded = base64.b64encode(
        (args.directory / "quality-latency.png").read_bytes()
    ).decode()
    figure = f'<figure><img style="max-width:100%" alt="Measured identity-quality and backend-latency tradeoffs" src="data:image/png;base64,{embedded}"><figcaption>{split.capitalize()} screening; full live acceptance is separate. Intervals bootstrap clips, not video frames.</figcaption></figure>'
    report.write_text(
        report.read_text().replace(
            "<h2>Experiment results</h2>", figure + "<h2>Experiment results</h2>"
        )
    )
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
