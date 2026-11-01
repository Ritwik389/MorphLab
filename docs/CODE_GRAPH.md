# Queryable architecture with Graphify

MorphLab ships a portable graph of authored code and technical documentation, built with Graphify 0.9.95. The interactive view is `graphify-out/graph.html`, the machine-readable representation is `graphify-out/graph.json`, and the analysis is `graphify-out/GRAPH_REPORT.md`.

## Scope

The scan respects `.gitignore` and excludes `graphify-out`, `assets`, `third_party`, `locales`, and `docs/images`. Model weights, research footage, build outputs, private session data, screenshots, translations, and vendored reference implementations are outside the graph. This is a code-and-documentation map, not a claim to index every byte in the checkout.

Code is extracted structurally without an API key. Documentation is extracted semantically using the Graphify skill and its extraction schema, with provenance/confidence retained. Inferences aid navigation and are not runtime evidence. The graph does not certify correctness, performance, or test coverage. A referenced API call can be an unresolved external node.

## Query locally

```bash
uv tool install graphifyy==0.9.95
graphify query "LiveSession tracking source revision" --budget 1500
graphify query "runtime registry MobileRuntime CoreML" --dfs --budget 1500
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
