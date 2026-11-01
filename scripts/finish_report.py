#!/usr/bin/env python3
"""Add measured experiment summaries and standalone figures to a verification report."""

import argparse
import base64
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import write_report


def read(relative):
    path = ROOT / relative
    return json.loads(path.read_text()) if path.is_file() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = json.loads((args.directory / "report.json").read_text())
    records = []
    quality = read("outputs/evaluations/frozen-validation/summary.json")
    paired = read("outputs/evaluations/frozen-validation/paired-quality.json")
    mobile = read("outputs/evaluations/finalized-m4-performance/report.json")
    coreml = read("outputs/evaluations/finalized-coreml-pilot/report.json")
    soak = read("outputs/evaluations/finalized-longevity/browser-soak.json")
    for label, data in [
        ("Validation quality", quality),
        ("Paired validation difference", paired),
        ("M4 Mobile/MPS trials", mobile),
        ("CoreML screening", coreml),
        ("Browser longevity", soak),
    ]:
        if data is not None:
            if isinstance(data, dict):
                data = {
                    k: v
                    for k, v in data.items()
                    if k not in {"manifest", "memory", "clips", "independent_evaluator"}
                }
            records.append({"experiment": label, "results": data})
    for label, path in [
        ("Clean Mac CPU install", "outputs/evaluations/clean-model-smoke.json"),
        (
            "Linux CPU container",
            "outputs/evaluations/container-finalized-smoke/smoke.json",
        ),
        ("Hardware", "outputs/evaluations/hardware.json"),
        ("Toolchain", "outputs/evaluations/external-tools.json"),
        (
            "CPU baseline comparison",
            "outputs/evaluations/photo-baselines-verified/report.json",
        ),
        (
            "Recovery state reproduction",
            "outputs/evaluations/recovery-comparison/report.json",
        ),
        ("Component removals", "outputs/evaluations/finalized-ablations/summary.json"),
        (
            "Worker and HUD screens",
            "outputs/evaluations/finalized-browser-pipeline/summary.json",
        ),
    ]:
        data = read(path)
        if data:
            records.append(
                {
                    "experiment": label,
                    "results": {k: v for k, v in data.items() if k != "manifest"}
                    if isinstance(data, dict)
                    else data,
                }
            )
    commands = [
        "python scripts/verify.py --suite smoke",
        "python scripts/verify.py --suite regression",
        "python scripts/assemble_evidence.py",
        "python scripts/verify.py --suite release --evidence experiments/local-evidence.json",
        "python scripts/run_longevity.py --soak",
        "python scripts/run_browser_benchmarks.py --runs 5",
        "python scripts/evaluate.py --config experiments/finalist-validation.json --split validation",
        "python scripts/smoke_container.py --image morphlab-studio:flagship",
    ]
    report["manifest"].update(
        reproduction_commands=commands,
        limitations=[
            "Human checks left Not Run at the author’s request",
            "Held-out corpus is not reviewed/frozen",
            "OS-library vulnerability gate remains failed",
            "Replay performance is not physical-camera or Safari validation",
            "Windows/hosted CI workflow definitions have not been executed in this workspace",
        ],
    )
    write_report(args.directory, report["manifest"], report["checks"], records)
    figures = []
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if (
        quality
        and mobile
        and coreml
        and mobile.get("experiments")
        and coreml.get("experiments")
    ):
        lookup = {row["candidate"]: row for row in quality}
        fig, axis = plt.subplots(figsize=(10, 6))
        for key, label, data, color in [
            ("mobile-calibrated", "Mobile/MPS · five trials", mobile, "#244ce8"),
            ("standard-native-int8", "CoreML INT8 weights · screen", coreml, "#ac3838"),
        ]:
            row = lookup[key]
            latency = statistics.median(
                run["p95_capture_to_display_ms"] for run in data["experiments"]
            )
            similarity = row["mean_clip_identity_cosine"]
            interval = row["clip_bootstrap_95_ci"]
            axis.errorbar(
                latency,
                similarity,
                yerr=[[similarity - interval[0]], [interval[1] - similarity]],
                fmt="o",
                color=color,
                capsize=5,
            )
            axis.annotate(
                f"{label}\nBrowser gate: {data['overall']}",
                (latency, similarity),
                xytext=(10, -20),
                textcoords="offset points",
                fontsize=10,
            )
        axis.axvline(
            200,
            color="#68717f",
            linestyle="--",
            label="200 ms latency limit; FPS windows also required",
        )
        axis.set(
            xlabel="Median trial p95 software capture-to-display latency (ms)",
            ylabel="Mean per-clip AdaFace cosine on validation inputs",
            title="MorphLab: measured quality / latency trade-off",
        )
        axis.set_ylim(0.45, 1)
        axis.margins(x=0.35)
        axis.set_xlim(left=0)
        axis.grid(alpha=0.2)
        axis.legend(loc="lower right")
        fig.tight_layout()
        plot = args.directory / "quality-latency.png"
        fig.savefig(plot, dpi=160)
        plt.close(fig)
        figures.append(
            (
                plot,
                "Quality and timing use separate fixed input sets. Intervals resample validation clips; browser pass/fail also checks every ten-second FPS window. Native precision names describe weight compression.",
            )
        )
    if soak and soak.get("memory"):
        fig, axis = plt.subplots(figsize=(10, 5))
        memory = soak["memory"]
        axis.plot(
            [row["elapsed_seconds"] / 60 for row in memory],
            [row["process_rss_mb"] for row in memory],
            color="#244ce8",
        )
        axis.set(
            xlabel="Elapsed live minutes",
            ylabel="Server process RSS (MiB)",
            title="One-hour browser live soak · fresh swaps checked every minute",
        )
        axis.grid(alpha=0.2)
        fig.tight_layout()
        plot = args.directory / "memory-curve.png"
        fig.savefig(plot, dpi=160)
        plt.close(fig)
        figures.append(
            (
                plot,
                "RSS includes shared model caches and OS residency. The gate compares settled windows; no physical memory-erasure claim is made.",
            )
        )
    content = (args.directory / "report.html").read_text()
    content = content.replace('class="status"', 'class="gate-status"')
    css = next((ROOT / "frontend/dist/assets").glob("*.css"), None)
    if css:
        content = content.replace(
            '<html lang="en">', '<html lang="en" data-theme="aims">'
        )
        content = content.replace(
            "<style>",
            "<style>"
            + css.read_text()
            + "</style><style>.gate-status{display:block;font-weight:700;width:auto;height:auto}h1{font-size:32px;font-weight:700;margin-bottom:16px}h2{font-size:22px;font-weight:650;margin:32px 0 12px}p{margin:12px 0}td{overflow-wrap:anywhere}figure{margin:24px 0}figcaption{padding:16px}",
            1,
        )
        content = content.replace("<table>", '<table class="table table-zebra">')
    markup = "".join(
        '<figure class="card bg-base-100"><img style="max-width:100%" alt="'
        + caption
        + '" src="data:image/png;base64,'
        + base64.b64encode(path.read_bytes()).decode()
        + '"><figcaption>'
        + caption
        + "</figcaption></figure>"
        for path, caption in figures
    )
    (args.directory / "report.html").write_text(
        content.replace(
            "<h2>Experiment results</h2>", markup + "<h2>Experiment results</h2>"
        )
    )
    print(args.directory / "report.html")


if __name__ == "__main__":
    main()
