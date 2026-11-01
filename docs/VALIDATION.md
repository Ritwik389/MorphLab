> Historical validation for the earlier Gradio/CLI build. Current Studio, GPU, browser, and container results are in [STUDIO_VALIDATION.md](STUDIO_VALIDATION.md).

# Validation record — 30 October 2026

Environment: macOS on Apple Silicon, Python 3.11.15, ONNX Runtime 1.23.2, CPU provider, two execution threads for video inference. Models were downloaded and verified against `models-manifest.json`.

## Verified

- 40 pytest tests passed, including 13 tracking tests and media/download/output-protection regressions.
- Python compilation and undefined-name/syntax checks passed.
- Desktop Qt UI initialized successfully with `QT_QPA_PLATFORM=offscreen`.
- Real image inference completed for identity swap, face blur, and pixelation with public-domain sample portraits.
- A two-frame video with audio exported with a PNG watermark overlay; output was 0.5 seconds. The overlay works on this FFmpeg build, which lacks drawtext support.
- Baseline, tracked, and adaptive video runs completed with real pretrained models and generated raw JSON, MP4, CSV and comparison JSON artifacts.
- The running Gradio APIs returned an edited image and a two-frame adaptive video with a downloadable report. The video reported two edited frames and one detector call; model metadata remained ordinary JSON rather than being interpreted as downloadable model files.

## Small motion-fixture result

Input: twelve frames, six FPS, 512×600 pixels. A public-domain portrait was translated by a few pixels to provide a deterministic motion smoke test. This is **not a representative test dataset**.

| Strategy | Edited frames | Detector calls | Processing FPS, excluding I/O | Identity cosine, 2 samples | Temporal residual change |
|---|---:|---:|---:|---:|---:|
| Baseline | 12 | 12 | 0.678 | 0.836 | 6.292 |
| Tracked | 12 | 12 | 0.650 | 0.834 | 5.442 |
| Adaptive, interval 3 | 12 | 4 | 0.712 | 0.832 | 3.077 |

Adaptive mode reduced detector calls by 66.7% on this fixture. Swapping remained the dominant cost, so total processing FPS improved only modestly. Tracked mode had a small overhead. Raw results are in `outputs/benchmarks/motion-smoke/` (ignored generated artifacts).

Lower temporal residual change on this single fixture is a useful smoke signal, not proof of improved perceptual quality. Identity cosine is measured with the pipeline's own recognition model; scores are not probabilities. No real-time, accuracy, or state-of-the-art claim follows from these results. Follow the held-out evaluation plan before reporting general improvements.

## Not yet verified

Physical webcam operation; accelerated inference; optional enhancer/classifier weights; Docker image build/runtime; public cloud deployment; full browser visual/mobile interaction. The local service's HTTP/config endpoint was checked separately from its visual presentation.

## Live webcam update — 31 October 2026

- Added a first-tab webcam stream that detects faces without source media, plus live blur/pixelation and camera-based identity capture for swapping.
- The desktop Live handler also accepts an empty source path and opens face detection.
- All 53 tests passed after the live implementation; the 13 live-specific tests also passed after the latest-frame capture wiring. Tests cover source-free detection, no-face behavior, source capture, busy-job fallback, current-frame geometry, browser streaming configuration and the desktop no-photo entry point.
- Real model smoke tests detected one face in sample camera frames, captured an identity from a streamed sample frame and applied it to another frame. The running server's streaming SSE endpoints returned all three results, using session state for the captured identity.
- Warm detector-only processing was about 44–45 ms on the sample frame; this excludes browser/camera/network overhead and does not establish delivered webcam FPS. Cold loading and face swapping took seconds.
- No physical webcam was activated by automated tests. Browser permission handling and hardware capture remain for an interactive check.
- The installed Python Gradio client does not recognize the server's `process_streaming` status message. The streaming transport was therefore verified through the supported SSE call endpoints; ordinary image/video client calls remain separate.
