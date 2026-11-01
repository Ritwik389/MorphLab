#!/usr/bin/env python3
"""Bind existing measured artefacts to the current product; never invent manual passes."""

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.evaluation import fingerprint, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/local-evidence.json"
    )
    args = parser.parse_args()
    current = fingerprint()
    audit = ROOT / "outputs/evaluations/dependency-audit-patched.json"
    scan = ROOT / "outputs/evaluations/container-finalized-trivy.json"
    junit = ROOT / "outputs/evaluations/finalized-regression/pytest.xml"
    if audit.exists() and scan.exists() and junit.exists():
        tests = list(ET.parse(junit).iter("testcase"))
        passed = {
            t.get("name", "").split("[")[0]
            for t in tests
            if t.find("skipped") is None
            and t.find("failure") is None
            and t.find("error") is None
        }
        controls = json.loads(
            (ROOT / "experiments/security-controls.json").read_text()
        )["controls"]
        for control in controls:
            control["passed"] = all(test in passed for test in control["tests"])
        container = json.loads(scan.read_text())
        findings = [
            v
            for result in container.get("Results", [])
            for v in result.get("Vulnerabilities", [])
            if v.get("Severity") in {"HIGH", "CRITICAL"}
        ]
        security = {
            **json.loads(audit.read_text()),
            "manifest": current,
            "controls": controls,
            "container": {
                "completed": True,
                "unresolved_high_critical": len(findings),
                "unique_advisories": len({v["VulnerabilityID"] for v in findings}),
                "artifact": str(scan.relative_to(ROOT)),
                "sha256": sha256(scan),
                "note": "Conservative gate: unresolved scanner findings remain failures; reachability review is pending.",
            },
        }
        (ROOT / "outputs/evaluations/security-evidence.json").write_text(
            json.dumps(security, indent=2) + "\n"
        )
    candidates = {
        "m4-browser-performance": ROOT
        / "outputs/evaluations/finalized-m4-performance/report.json",
        "one-hour-soak": ROOT
        / "outputs/evaluations/finalized-longevity/browser-soak.json",
        "100-start-stop": ROOT
        / "outputs/evaluations/finalized-longevity/lifecycle-100.json",
        "security-audit": ROOT / "outputs/evaluations/security-evidence.json",
    }
    evidence = {}
    for name, path in candidates.items():
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        if (
            data.get("manifest", {}).get("source_tree_sha256")
            != current["source_tree_sha256"]
        ):
            print(f"Not binding stale {name}")
            continue
        evidence[name] = {
            "artifact": str(path.resolve()),
            "sha256": sha256(path),
            "source_tree_sha256": current["source_tree_sha256"],
        }
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(args.output)
    print(
        "Human and reviewed held-out gates remain Not Run until their own evidence exists."
    )


if __name__ == "__main__":
    main()
