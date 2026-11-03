#!/usr/bin/env python3
"""Render a curated README overview backed by the exported Graphify source nodes."""

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "studio": (
        "Studio",
        ["Camera · photos · video"],
        "frontend/src/",
        [
            "frontend/src/main.tsx",
            "frontend/src/useLive.ts",
            "frontend/src/mediaBridge.ts",
            "frontend/src/media.worker.ts",
            "frontend/src/api.ts",
            "frontend/src/liveProtocol.ts",
        ],
    ),
    "api": (
        "API & sessions",
        ["HTTP + binary WebSocket"],
        "studio_api.py",
        ["modules/studio_api.py"],
    ),
    "live": (
        "Live processing",
        ["Latest-frame queue · face tracking"],
        "studio_live.py · temporal.py",
        ["modules/studio_live.py", "modules/temporal.py"],
    ),
    "exports": (
        "Photo & video exports",
        ["Cancellable jobs · live gets priority"],
        "studio_jobs.py",
        ["modules/studio_jobs.py"],
    ),
    "models": (
        "Model runtimes",
        ["Live: MobileFaceSwap / MPS", "Exports: INSwapper / CoreML or CPU"],
        "runtime.py · mobile_model.py",
        ["modules/runtime.py", "modules/mobile_model.py", "modules/onnx_optimize.py"],
    ),
    "checks": (
        "Verification",
        ["Tests · comparisons · release gates"],
        "tests/ · scripts/ · CI",
        ["tests/", "scripts/", ".github/workflows/"],
    ),
}
COLORS = {
    "background": "#f5f6f8",
    "surface": "#ffffff",
    "ink": "#1f242c",
    "muted": "#525c6b",
    "line": "#dde1e8",
    "primary": "#244ce8",
    "tonal": "#e0e7ff",
}


def text(x, y, content, size=18, weight=400, color="ink", mono=False):
    font = (
        "ui-monospace, SFMono-Regular, Consolas, monospace"
        if mono
        else "Arial, Helvetica, sans-serif"
    )
    return f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{COLORS[color]}">{escape(content)}</text>'


def node(key, x, y, w, h, *, mobile=False):
    title, body, filename, _ = GROUPS[key]
    branch = mobile and key in {"live", "exports"}
    if branch:
        title = "Live" if key == "live" else "Exports"
        body = ["Face tracking"] if key == "live" else ["Photos + video"]
        filename = "studio_live.py" if key == "live" else "studio_jobs.py"
    pad = 18 if branch else 22
    title_size = 25 if mobile else 26
    if not mobile and key in {"live", "exports"}:
        title_size = 25
    svg = [
        f'<g id="{key}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{COLORS["surface"]}" stroke="{COLORS["line"]}"/>',
        f'<rect x="{x + pad}" y="{y + 19}" width="24" height="3" rx="1.5" fill="{COLORS["primary"]}"/>',
        text(x + pad, y + 52, title, title_size, 700),
    ]
    lines = body
    if mobile and key == "api":
        lines = ["HTTP + WebSocket"]
    if mobile and key == "models":
        lines = ["Live: MPS + CPU fallback", "Exports: CoreML or CPU"]
    if not mobile and key == "studio":
        lines = ["Camera · photos · video"]
    if not mobile and key == "checks":
        lines = ["Tests + benchmarks"]
    for i, line in enumerate(lines):
        svg.append(
            text(x + pad, y + 78 + i * 24, line, 16 if branch else 18, color="muted")
        )
    svg.append(
        text(
            x + pad,
            y + h - 18,
            filename,
            14 if branch or key == "checks" else 16,
            color="muted",
            mono=True,
        )
    )
    svg.append("</g>")
    return "\n".join(svg)


def path(d, dashed=False):
    extra = ' stroke-dasharray="6 6"' if dashed else ' marker-end="url(#arrow)"'
    return f'<path d="{d}" fill="none" stroke="{COLORS["muted"] if dashed else COLORS["primary"]}" stroke-width="2.5" stroke-linejoin="round"{extra}/>'


def render(mobile=False):
    w, h = (420, 1060) if mobile else (1120, 740)
    items = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title description">',
        '<title id="title">MorphLab architecture: six connected parts</title>',
        '<desc id="description">Studio sends media to the API. Live processing and offline export jobs use the model runtimes. Verification checks the pipeline. Solid arrows show processing; the dashed line shows a test relationship. Edited results return to Studio. This is a curated overview, not the complete dependency graph.</desc>',
        f'<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 Z" fill="{COLORS["primary"]}"/></marker></defs>',
        f'<rect width="{w}" height="{h}" rx="20" fill="{COLORS["background"]}"/>',
    ]
    if mobile:
        items += [
            text(24, 43, "MorphLab architecture", 28, 700),
            text(24, 74, "Six parts. One editing pipeline.", 18, color="muted"),
        ]
        positions = {
            "studio": (24, 112, 372, 128),
            "api": (24, 274, 372, 128),
            "live": (24, 440, 176, 124),
            "exports": (220, 440, 176, 124),
            "models": (24, 620, 372, 156),
            "checks": (24, 844, 372, 128),
        }
        items += [
            path("M210 240 V274"),
            path("M112 402 V440"),
            path("M308 402 V440"),
            path("M112 564 V592 H160 V620"),
            path("M308 564 V592 H260 V620"),
            path("M210 776 V844", True),
        ]
        for key, pos in positions.items():
            items.append(node(key, *pos, mobile=True))
        items += [
            text(24, 1012, "Arrows: processing flow", 17, color="muted"),
            text(24, 1040, "Dashed line: verification", 17, color="muted"),
        ]
    else:
        items += [
            text(48, 62, "MorphLab architecture", 36, 700),
            text(
                48,
                98,
                "Capture, process, and inspect an edit — with verification around the pipeline.",
                20,
                color="muted",
            ),
        ]
        positions = {
            "studio": (48, 204, 238, 138),
            "api": (348, 204, 270, 138),
            "live": (680, 142, 370, 138),
            "exports": (680, 326, 370, 138),
            "models": (348, 520, 702, 156),
            "checks": (48, 520, 238, 156),
        }
        items += [
            path("M286 273 H348"),
            path("M618 242 H648 V211 H680"),
            path("M618 305 H648 V395 H680"),
            path("M1050 211 H1080 V598 H1050"),
            path("M865 464 V520"),
            path("M286 598 H348", True),
        ]
        for key, pos in positions.items():
            items.append(node(key, *pos))
        items += [
            text(
                48,
                716,
                "Solid arrows: processing flow. Dashed line: verification. Edited media returns to Studio.",
                17,
                color="muted",
            )
        ]
    items.append("</svg>")
    return "\n".join(items) + "\n"


def main():
    graph = json.loads((ROOT / "graphify-out/graph.json").read_text())
    nodes = graph["nodes"]
    sources = {n["source_file"] for n in nodes if n.get("source_file")}
    mapping = {}
    for key, (label, _, _, files) in GROUPS.items():
        matches = [
            n["id"]
            for n in nodes
            if n.get("source_file")
            and any(
                n["source_file"].startswith(f)
                if f.endswith("/")
                else n["source_file"] == f
                for f in files
            )
        ]
        if not matches:
            raise ValueError(f"No Graphify source nodes for {label}")
        for file in files:
            if not file.endswith("/") and file not in sources:
                raise ValueError(f"Missing graph source: {file}")
        mapping[key] = {"label": label, "source_files": files, "node_ids": matches}
    out = ROOT / "docs/images"
    out.mkdir(exist_ok=True, parents=True)
    for mobile in (False, True):
        file = out / (
            "morphlab-code-map-mobile.svg" if mobile else "morphlab-code-map.svg"
        )
        file.write_text(render(mobile))
    overview = {
        "scope": "Curated responsibility groups, not Graphify community partitions",
        "groups": mapping,
        "processing_connections": [
            ["studio", "api"],
            ["api", "live"],
            ["api", "exports"],
            ["live", "models"],
            ["exports", "models"],
        ],
        "verification_relationship": ["checks", "models"],
        "note": "Arrows are source-reviewed processing flow. Dashed link represents verification, not per-frame production traffic.",
    }
    (ROOT / "graphify-out/OVERVIEW.json").write_text(
        json.dumps(overview, indent=2) + "\n"
    )
    print(
        f"Rendered desktop/mobile maps from {len(nodes)} graph nodes; all six groups have source coverage."
    )


if __name__ == "__main__":
    main()
