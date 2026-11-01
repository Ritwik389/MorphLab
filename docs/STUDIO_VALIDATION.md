# AIMS Studio validation — 1 November 2026

Hardware: Apple M4, 16 GiB RAM, macOS 27.0.1 arm64. Python 3.11.15, ONNX Runtime 1.23.2, coremltools 9.0, PyTorch 2.15.0. The original upstream base remains commit 2bf2728c6d3e2df1086fa2dc3e25de3944532a10.

## Performance measurements

| Measurement | Result | Scope |
| --- | --- | --- |
| Original live CPU swap inference | approximately 2.3 seconds/frame | Original loader ignored requested ONNX thread options |
| Native CoreML FP16 | 169.4 ms mean | Warm model inference only, fixed 128 × 128 input |
| Native CoreML INT8 | 59.0 ms mean, 61.2 ms p95 | Warm model inference only |
| MobileFaceSwap / MPS | 11.0 ms mean, 11.8 ms p95 | Alignment, new inference, learned mask and compositing, fixed detection |
| Two-minute lightweight backend replay | 5,204 new swaps, 43.36 FPS, 31.96 ms p95 | Static portrait replay; includes tracking, detection refresh and JPEG encoding |
| Two-minute Chrome camera replay | 2,549 unique new displayed swaps, 21.23 FPS, 54.3 ms p95 capture-to-display | Test webcam; includes input encoding, WebSocket transport, inference, decode, and next animation frame |

The browser replay uses a gently rotated public-domain portrait at 640 × 480 through Chrome's fake camera. It does not duplicate one generated swap to inflate FPS. The final browser run also asserts that the backend live-session reservation returns to zero after Stop. A video queued during that run resumed automatically, with audio, frame rate, duration, and intermediate-file cleanup verified. Capture-to-display is measured from software canvas capture, not the physical sensor exposure. The first and second minute produced 1,270 and 1,279 swaps, respectively. The acceptance targets are at least 15 new displayed swaps/second and p95 below 200 ms over two minutes after warmup. Physical webcam motion, speech, profile views, and low-light performance still require human validation; no physical-camera result is claimed.

The latest raw measurements are in `outputs/benchmarks/browser-120s.json`, `mobile-studio-120s.json`, and the runtime manifests under `.cache/coreml` and `models/mobilefaceswap`. Re-run `npm run benchmark` from frontend with the server running and the fake webcam fixture available. Run browser regressions and the performance gate sequentially: live camera priority intentionally pauses offline jobs.

## Quality and fidelity

The standard export model and lightweight live model serve different quality/performance tradeoffs. On the three bundled pairs, source-to-output ArcFace cosine similarity was:

| Pair | CPU FP32 standard model | Native INT8 standard model | Lightweight live model |
| --- | --- | --- | --- |
| Eileen → Grace | 0.8114 | 0.8101 | 0.4734 |
| Sally → Katherine | 0.9075 | 0.9066 | 0.4636 |
| Katherine → Sally | 0.8167 | 0.8186 | 0.3844 |

These are heuristics on three examples, not independent identity accuracy or probabilities. They demonstrate why the standard model remains the export default. The live model trades substantial identity fidelity for speed; it is not presented as quality-equivalent. Inspect its results, particularly glasses and boundaries. Standard-model live comparison is available with `AIMS_LIVE_MODEL=inswapper`, below the measured live FPS target.

FP16's mean raw pixel error relative to CPU FP32 ranged from 0.00165 to 0.00207 on the 0–1 scale; INT8 ranged from 0.00357 to 0.00488. Both passed the chosen 2/255 mean-error smoke threshold on the bundled pairs. Outputs and metrics are in `outputs/quality` and `outputs/benchmarks/quality-comparison.json`. This small fixture set does not establish generalization across identities or conditions.

The MobileFaceSwap PyTorch port matches the unmodified authors' Paddle implementation across all three pairs: mean image error approximately 1.1e-7 on the 0–1 scale. Its GPU-versus-CPU pixel error was approximately 2e-5 on the 0–255 scale. Paddle/PyTorch run in isolated processes for this comparison to avoid a native symbol conflict observed on macOS. The server does not import Paddle.

## Functional checks

- Existing 53 regression tests retained; the current Python suite has 70 tests, all passing. new tests cover binary protocol limits, revision rejection, isolated sessions, pending-frame replacement, scheduling priority, paused-job cancellation, disconnect-during-send cleanup, CPU fallback after failed accelerator warmup, invalid media, and shape-separated CoreML caches.
- Browser workflows cover landing navigation, keyboard image comparison, responsive overflow, sample photo processing/report download, invalid source errors, capture without upload, sample identity swaps, Stop/restart, navigation cleanup, permission denial, source-loading races, and restoring results after navigation.
- Short-video API export verified with 48 frames at 24 FPS, two-second duration, restored audio, and a downloadable report. It queued while Live was active and resumed after Stop.
- Container built from the locked dependencies; CPU landing, system API, actual photo swap, result and report passed with read-only model mounts. A cold initial model load briefly exceeded a five-second test request timeout; warmed requests passed.
- Landing inspector: zero failures at 1440, 768 and 390 px; no broken images or horizontal overflow. Material typography, restrained motion and a static actual-result comparison account for the remaining advisory warnings.
- Safari automation could not start because Allow Remote Automation is disabled. This setting was not changed. Native Safari interaction and physical webcam tests remain unverified.
- CUDA selection/fallback is implemented, but no NVIDIA hardware was available for a real CUDA test.

## Reproduce and inspect

```bash
.venv/bin/python -m pytest -q
(cd frontend && npm test)
(cd frontend && npm run benchmark)
.venv/bin/python scripts/validate_quality.py
.venv/bin/python scripts/validate_mobile.py
```

The optional Paddle validation requires `requirements-research-validation.txt`. The original research strategy ablation runner and tests remain available. No dataset training, new model architecture claim, public deployment, or comparative state-of-the-art claim is made.
