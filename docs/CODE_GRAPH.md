# Queryable architecture with Graphify

MorphLab ships a portable graph of authored code and technical documentation, built with Graphify 0.9.95. The interactive view is `graphify-out/graph.html`, the machine-readable representation is `graphify-out/graph.json`, and the analysis is `graphify-out/GRAPH_REPORT.md`.

## Scope

The scan respects `.gitignore` and excludes `graphify-out`, `assets`, `third_party`, `locales`, and `docs/images`. Model weights, research footage, build outputs, private session data, screenshots, translations, and vendored reference implementations are outside the graph. This is a code-and-documentation map, not a claim to index every byte in the checkout.

Code is extracted structurally without an API key. Documentation is extracted semantically using the Graphify skill and its extraction schema, with provenance/confidence retained. Inferences aid navigation and are not runtime evidence. The graph does not certify correctness, performance, or test coverage. A referenced API call can be an unresolved external node.

## Query locally

```bash
uv tool install graphifyy==0.9.95
graphify query "tracking source revision" --seed modules_studio_live_livesession --budget 1500
graphify query "backend model warmup" --seed modules_runtime_modelregistry --budget 1500
graphify explain "LiveSession"
graphify export html
```

Run commands from the repository root. The committed graph can be queried without model weights, a server, or an API key. Open the HTML locally; GitHub displays its source rather than executing it. Query output is graph context, not an authoritative natural-language answer. Follow source paths and verify claims against implementation/tests.

## Refresh

`graphify update .` refreshes structural code relationships. For a complete documentation-semantic refresh, invoke the installed Graphify skill with `--update` in a supported coding agent. Persist the same exclusions in local `graphify-out/.graphify_build.json`:

```json
{"excludes":["graphify-out","assets","third_party","locales","docs/images"],"gitignore":true}
```

Local absolute interpreter/root paths, extraction intermediates, and caches are ignored. Only portable graph outputs and a build audit are published. Refresh the graph when implementation changes; generated edges may collapse into one undirected relationship, so consult the diagnostic report rather than treating the visualisation as a lossless call graph. Host-agent token usage is unavailable in this extraction environment; placeholder zero counters are not a claim of zero token cost.

## README overview

The README uses two self-contained SVGs: a wide map for desktop and a narrow map below a 600-pixel viewport. Both use the existing MorphLab platinum, graphite and cobalt palette, carry accessible title/description text, and require no external fonts or JavaScript. The overview groups files by responsibility; it is not a claim that Graphify generated exactly six communities.

`scripts/render_code_map.py` validates the source coverage of every group against `graphify-out/graph.json`, writes both SVG layouts, and exports their node/file membership to `graphify-out/OVERVIEW.json`. Solid arrows are source-reviewed processing flow; the dashed relationship represents tests/evaluation rather than per-frame traffic. The diagram omits the return path for clarity; edited media returns to Studio.

After refreshing the graph, regenerate the overview with:

```bash
python scripts/render_code_map.py
```

Review both layouts at desktop and mobile widths before publishing. The full interactive graph remains a local HTML download and the CLI remains available for deeper exploration. Graphify extraction can leave dynamic references unresolved or combine same-endpoint edges; the audit records these limitations.
