# Audit of the original project and local corrections

Scope: the complete source tree cloned from `shauryasuyal/Deepfake_Project`, upstream HEAD `2bf2728`, plus the revised local implementation. This is a source audit and targeted runtime validation, not proof that every possible defect has been eliminated.

## Confirmed issues addressed

| Priority | Original trigger and consequence | Correction |
|---|---|---|
| P1 | Downloading models on macOS disabled TLS certificate checks, and an interrupted download remained at the final path and was trusted on restart | Verified TLS, temporary download files, length checks, atomic replacement, pinned SHA-256 checks for core models |
| P1 | Re-encoding every input frame at a fixed 30 FPS changed duration for 24/60 FPS inputs, causing audio/video drift | Preserve native FPS by default; explicitly resample when changing FPS |
| P1 | The pipe pipeline used the preceding frame's face coordinates, so motion or cuts could swap in the wrong place | Current-frame detection in the legacy pipe path; verified current-frame motion prediction in the research modes |
| P1 | Image copying/processing failures could leave original content at the output and still report success; output could coincide with an input | Validate paths and source/target faces, stage outputs, propagate image inference/write failures, preserve existing output on failed jobs |
| P1 | Long desktop exports and mapper analysis ran on the Qt event thread, freezing controls | Background export/analysis worker, queued status, error reporting, prevent closing during active export |
| P2 | Headless CLI imported the entire Qt UI and startup imported TensorFlow even for ordinary ONNX inference | Lazy desktop/classifier imports; separate core, desktop, browser and optional classifier requirements |
| P2 | macOS Intel had no matching ONNX Runtime requirement; Apple Silicon was pinned to an obsolete separate silicon wheel while code used newer provider settings | Standard ONNX Runtime wheel, tested CPU baseline, no automatic CUDA package on non-NVIDIA hosts |
| P2 | Both OpenCV wheel variants could install into the same `cv2` namespace | One headless OpenCV wheel; Qt UI uses PySide, not OpenCV HighGUI |
| P2 | Missing `-o` could call `os.path.isdir(None)`; partial CLI arguments reached processing with missing paths; audio could not be disabled | Validate CLI combinations and thread/memory values, handle optional paths, BooleanOptionalAction flags |
| P2 | FFmpeg stderr pipes could fill while parent waited on frame I/O; decoder failures were not checked | File-backed diagnostics, check both processes, close/reap subprocesses |
| P2 | Worker exceptions were swallowed; ordered temporal state could be mutated by parallel frames | Propagate dispatcher failures; serialize legacy temporal interpolation |
| P2 | Processor-module cache ignored subsequent selection changes | Reconcile selected modules on each call |
| P2 | Audio mapping required an audio stream, causing silent videos to fail the mux attempt | Optional audio mapping with explicit video/audio selection |
| P2 | Temp paths collided between same-name input containers; frame paths were not numerically ordered | Include resolved input-path hash; sort frame numbers numerically |
| P2 | Automatic hardware decoding and a forced BT.601→BT.709 transformation could fail or alter colors independent of source metadata | Portable software decode and normal encoder color handling; even-dimension padding |
| P2 | Source video rotation metadata could disagree with raw-frame dimensions | Probe rotation and use display dimensions |
| P2 | GIF/BMP/WebP selections bypassed the image route; preview used negative/previous frame indexes | Consistent extensions and zero-based clamped indexing; static-image preview decoding |
| P2 | A hard macOS memory limit could abort native model allocations; FFprobe was required but not checked | No default hard resource limit, check FFmpeg and FFprobe |
| P2 | The optional frame classifier converted BGR to RGB only when an unrelated display toggle was enabled | Always convert OpenCV frames before PIL/classifier preprocessing |
| P3 | Camera release skipped partially initialized captures; webcam processing errors left a stalled preview | Release allocated capture regardless of running state; signal stop on processing failure |
| P2 | Original README claimed verified automatic model downloads, universal pinned setup, broad performance and strong content-safety guarantees without supporting artifacts | Replace claims with actual architecture, tested environment, setup, research limits and deployment guidance |

## Important remaining limits

- The old desktop face mapper uses a heuristic K-means cluster-count selection. It has not been validated against labelled identity tracks; it is separate from the new appearance-gated offline tracker.
- Webcam hardware behavior and CUDA/DirectML/CoreML inference were not validated on this CPU build. The Qt window was created in an offscreen smoke test, not exercised end to end with a physical camera.
- GFPGAN/GPEN enhancers and the optional TensorFlow classifier were not exercised with their model weights. The base swapper and browser experiments were verified with real weights.
- Some legacy frame processors still intentionally fall back to original pixels on errors. Research-report jobs refuse to silently switch to the legacy disk pipeline, so their measurements do not describe an unrequested fallback.
- Tracking, shot detection, quality thresholds and recognition are imperfect. Appearance matching cannot guarantee correct identity under severe occlusion or similar-looking subjects.
- Browser rendering automation did not complete. Local HTTP/config and backend/API validation are separate from full visual/mobile QA.
- Source redistribution licensing is not declared in upstream. Pretrained model terms are separate. Docker files are supplied; a cloud deployment is not implied by a local build.

See [validation evidence](VALIDATION.md), [research methodology](RESEARCH.md), and [deployment](DEPLOYMENT.md).

## Studio implementation audit — 1 November 2026

Confirmed and addressed: CPU-only web defaults; misleading provider badges; InsightFace get_model silently dropping sess_options; shared globals and whole-export locks coupling live to offline; unbounded/stale transport behavior; leftmost-face switching; source-revision races; missing WebSocket runtime dependency; cache collisions across input shapes; lost results on navigation; unfriendly FFprobe errors; and potential finalization stderr backpressure.

The new API isolates sessions and runtime configuration, bounds the pending frame queue, propagates source revisions, specializes the lightweight generator per identity in memory, and exposes separate live/export runtimes. Appearance-gated tracks are refreshed asynchronously. Exports pause between frames while Live is connected; cancellation still works. Invalid target/source fixtures and lifecycle checks have regression coverage.

Graphify's code-only graph traced shared runtime dependencies during planning (670 nodes, 1,732 edges). No code graph or semantic data was sent to an external LLM. This audit is not a claim that every possible bug has been eliminated. Controlled validation and remaining hardware/browser gaps are documented in STUDIO_VALIDATION.md.

The final disconnect stress test exposed and fixed a reservation leak: re-awaiting a failed WebSocket send worker could raise WebSocketDisconnect inside cleanup before decrementing the live-session count. Cleanup now runs unconditionally, and both the unit regression and browser Stop test verify reservation release.
