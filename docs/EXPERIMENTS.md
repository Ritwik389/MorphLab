# Experiment register and selection protocol

## Baselines

`experiments/baselines.json` identifies the pinned upstream commit and the archived pre-flagship working copy. The archive includes hashes and is retained locally under `.cache/evaluation/pre-flagship/`. Historical measurements in STUDIO_VALIDATION.md keep their original scope. They are not relabelled as runs of this release.

Upstream's original requirements include an obsolete Mac ONNX runtime and optional TensorFlow/desktop dependencies. A full original-environment rerun is separate from a matched model/kernel comparison; unsupported installation must be reported rather than silently modernised and called original.

## Execute

```text
python scripts/fetch_corpus.py
python scripts/build_stress_corpus.py
python scripts/fetch_adaface.py
python scripts/evaluate.py --config experiments/screening.json --output outputs/evaluations/development-screening
```

The screening matrix has eleven candidate configurations, three repetitions and seed 2401. Each candidate runs in a fresh process. Each genuine development clip contributes the same two deterministic sample positions. Model selection, source input, actual provider, timings, failed detections and independent-evaluator scores are recorded. These sparse, potentially discontinuous frames are a screening test, not a continuous tracking/FPS benchmark. Slow CPU/precision alternatives are retained as comparison points.

Compare Mobile/MPS with standard CPU, native FP16 and native INT8; remove dense geometry, smoothing and soft masks; vary detection intervals and preview sizes. The main-thread/worker and HUD comparisons use the same browser fixture and actual displayed-frame benchmark, not this backend screening runner.

Do not run quality evaluation inside the live timing loop. AdaFace IR50 WebFace4M is used offline with authors' BGR preprocessing, safe weight loading and checksum verification. It is a separate evaluator, not proof of independently sampled pretraining identities. Retain missing detections in coverage/failure denominators. Pixel parity is meaningful between precision variants of the same generator, not unrelated generators.

## Decision rule

Reject candidates that fail correctness, privacy or tracking. Among those that pass, require every ten-second window >=15 unique newly displayed swaps/s and p95 software capture-to-display <200ms over two minutes. Rank surviving candidates by independently measured identity/visual fidelity; then prefer lower resource use and complexity. Quality differences within uncertainty do not justify a more complex pipeline. Report failed targets and trade-offs rather than an arbitrary combined score.

Use five repetitions for finalists. Report per-clip summaries, median/spread and clip-level bootstrap intervals; video frames from the same clip are not independent observations. Freeze parameters before held-out evaluation. If annotations are not reviewed or a test condition is unavailable, keep the corresponding gate Not Run.

## Experiment record

For every run retain hypothesis, candidate configuration, controlled variables, source/model/input hashes, runtime/provider, warmup, repetitions, raw samples, failure counts, confidence intervals, and the resulting decision. Each architecture decision must link to actual run artifacts. Development exploration, a frozen validation comparison, and final held-out acceptance are different milestones.

## Recorded validation result

The frozen validation screen runs five repetitions per alternative, six positions per genuine clip from actors 05–08: 360 samples per configuration. Calibrated Mobile and its binary-mask baseline both edit 345/360 samples; missed edits remain in the coverage denominator. Mean per-clip AdaFace cosine is 0.5800 versus 0.5807. The paired median clip difference is -0.00051, with a clip-bootstrap 95% interval approximately [-0.00125,0.00001], inside the engineering 0.02 tolerance. These are validation diagnostics, not held-out accuracy percentages. Native CoreML INT8 scores approximately 0.8788 on the same validation inputs. Its full-browser performance screen is evaluated separately.

Raw data: `outputs/evaluations/frozen-validation/`; paired analysis: `python scripts/paired_quality.py outputs/evaluations/frozen-validation`. API/export-only fixes occurred during the screen, so individual whole-product fingerprints are retained rather than replaced with one invented revision; generation/tracking/evaluator implementations and model weights were unchanged. Backend timing during this screen had concurrent research/soak workloads and is not used as an uncontended speed claim.

The matched CPU photo comparison uses three repetitions for upstream, archived AIMS and candidate AIMS, fixed two execution threads, identical sample inputs and verified weights. Upstream retains its isolated onnxruntime-silicon1.16.3 environment; archived/candidate runs use the recorded patched environment. Candidate and archived JPEG outputs match exactly on this fixture. Process/startup timings include the concurrent soak condition and do not establish a general CPU speedup. A first reporting failure incorrectly looked for the upstream runtime under the `onnxruntime` distribution name; the corrected rerun and original failure are both retained.

Commands: `python scripts/compare_photo_baselines.py`; `python scripts/reproduce_recovery.py`. The recovery comparison uses identical mocked observations against the archived/current state machines. It proves the ambiguity-latch control defect and its correction; it does not prove real-camera recognition or generator quality.

## Final browser comparison

Five exact-candidate Mobile/MPS trials all pass the full two-minute replay gate: 19.64–21.30 new displayed swaps/s, p95 software latency 76.5–115 ms, and minimum ten-second throughput 16 FPS. The actual M4 runs on battery power. The matched current-code CoreML INT8 screen produces 12.16 swaps/s, p95 143.3 ms and minimum-window 11.4 FPS: latency passes, throughput fails. It is rejected for Live despite higher validation similarity, and retained for offline editing. The CoreML result is one screening repetition, not five finalist repetitions; the predeclared fail-fast rule does not promote a failed screen.

Worker/HUD screens use three 20-second repetitions per configuration. Median throughput is 21.04 FPS with main-thread fallback, 21.08 with workers/HUD off, and21.29 with workers/HUD on. Median per-trial p95 is 78.9/85.9/77.6 ms respectively. This small study does not establish a throughput or jank improvement from workers; only one >50 ms long task appeared across all nine screens. Worker support is retained for media-task isolation and compatibility testing; no zero-copy GPU pipeline is claimed. These short screens do not replace the five complete live acceptance trials.
