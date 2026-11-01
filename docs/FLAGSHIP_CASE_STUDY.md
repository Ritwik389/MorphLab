# MorphLab engineering case study

## Problem

A fast-looking face-swap demo could fail after the first tracking miss, force manual reselection, and report model-only speed as if it proved webcam performance. The UI also mixed engineering controls with the basic editing journey.

## Investigation and changes

The tracking-state reproduction showed that a lost face latched permanent ambiguity, even after detection returned. The old asynchronous path could associate observations from an earlier frame with a newer state. The fix makes observations ordered, preserves appearance across short misses, refines current-frame geometry with 106 landmarks, and switches targets only after a two-second absence. Person thumbnails are optional overrides.

The pipeline uses bounded binary WebSocket transport and latest-frame replacement. Worker-based image resizing/encoding/decoding keeps avoidable media work away from React, while final canvas presentation and an honest compatibility fallback remain. Source revisions, target revisions, frame IDs and session generations prevent stale display. The profiler measures actual stages rather than displaying assumed operations.

Full browser profiling changed the bottleneck diagnosis. After accelerating the generator, heavy detection/recognition repeatedly cost about 72/130 ms during motion, while Mobile generation took roughly 16–18 ms. A verified SCRFD-500MF/MobileFaceNet live analyser replaced that repeated work; the stronger analyser remains for source analysis and exports. Five pre-final export-fix replay trials passed at approximately 21 displayed swaps/s. The final exact-source trials are recorded separately in the release report.

Soft generator masks, conservative colour correction and source-input advice address visible quality issues without claiming universal occlusion segmentation. The new platinum/graphite/cobalt palette preserves the Material layout and primary editing flow.

## Evaluation

The pre-change working copy was archived and hashed before edits. The pinned upstream commit remains recorded separately. The study includes eleven configurations x three isolated repetitions on development identities, using a separate offline AdaFace evaluator, plus continuous tracking ablations and actual browser trials. Raw reports, failures, model/data hashes, source fingerprints and repeatable commands are retained.

The RAVDESS subset contains 36 genuine expression/speech clips from 12 actors, with identity-separated development/validation/held-out partitions. Nine derived stress clips add controlled crossing, departure, blur and lighting perturbations. Their synthetic provenance and composition annotations are explicit. Natural head turns, physical camera motion and reviewed held-out tracking are separate validation requirements.

The validation comparison used five repetitions per configuration and 12 clips from four identities. Calibrated soft boundaries and the previous binary mask both swapped 345/360 sampled positions. The independent AdaFace mean per-clip cosine was about 0.580 versus 0.581, with paired median change -0.00051 (clip-bootstrap interval about -0.00125 to 0.00001), inside the declared 0.02 engineering tolerance. Native CoreML INT8 scored about 0.879 on the same validation inputs. These are similarity diagnostics, not accuracy percentages. Expensive quality inference ran outside the throughput timer.

One rejected experiment was particularly informative: applying the raw learned mask again as external alpha reduced development similarity from about 0.539 to 0.299. The generator already gates its output. The selected boundary treatment instead preserves the core and smoothly feathers its perimeter. This is an engineering correction supported by comparative data, not a new generator.

Three CPU photo repetitions per baseline preserve the upstream/pre-flagship/candidate comparison under matched inputs and model weights. The original keeps isolated dependencies. Archived and candidate output JPEGs match exactly on that fixture; runtime-version differences and background soak conditions are recorded. A separate controlled state-machine reproduction demonstrates the old lost-face latch and new automatic recovery, explicitly using mocked observations rather than pretending it is a webcam-quality experiment.

## Decision policy

Correctness and tracking come first; a candidate must then sustain >=15 new displayed swaps/s in every ten-second window with p95 software capture-to-display <200ms. Among passing candidates, prefer independently assessed identity and visual fidelity, then resource use and simpler deployment. Mobile/MPS remains provisional for Live; higher-fidelity standard models remain available for exports. Measured comparison summaries must be read alongside coverage and failures.

## Assurance and limits

The maintained production lock is hash-pinned and patched after a real advisory audit. Unit/state, property, actual-model, API, browser, accessibility, fault, lifecycle and soak checks have separate evidence. A suite that cannot verify a required condition leaves it Not Run; no manual/physical-device pass is inferred from synthetic replay or mocks.

This is an integrated engineering contribution, not a new generator or a state-of-the-art claim. The release report is the authoritative record of which gates are complete. See TEST_STRATEGY.md, EXPERIMENTS.md, RELEASE.md, MODEL_DATA_CARD.md, SECURITY.md and DECISIONS.md for reproducible details and limitations.

The assurance work also found actual media defects: rotation metadata was lost, and `-shortest` truncated longer video to shorter audio. Real FFmpeg/OpenCV tests now cover both. The maintained container smoke command runs genuine CPU inference after a clean build; the clean Mac production environment also runs a real model without development/Mac-GPU packages. Windows and hosted macOS workflow definitions remain unexecuted checks, not compatibility passes.

## Final recorded Mac evidence

The exact product fingerprint 8e838672a8698eb39f24b425b11e03f06ba82ed2b0a455a345e3e646f9d51d64 passed five two-minute, 640×480 Chrome 156 trials on the M4/16 GiB machine, on battery power. New displayed-swap rates ranged 19.64–21.30/s; p95 software capture-to-display latency ranged 76.5–115 ms; the slowest ten-second window was 16 FPS. Source/model warmup is excluded. The fixture contains genuine speech/expression with a fixed face crop, not broad physical head turns.

The corrected full-hour run passed both Playwright tests, with 72,859 newly displayed swaps, fresh-frame checks at all 60 minute samples, released camera/session resources and settled RSS change -3.35 MiB. The first complete-hour trace-collection failure remains a separate failed run. Functional regression records 107 backend tests, seven frontend unit tests and eight browser workflows; model smoke tests are actual CPU inference, not mocks.

CoreML INT8's final current-code browser screen reaches 12.16 swaps/s and 143.3 ms p95, failing the FPS requirement while passing latency. Mobile/MPS is the provisional live operating choice among the tested generators; the standard model remains the higher-fidelity offline path. Complete held-out, visual and physical-device acceptance is still pending. The nine worker/HUD screens show no material throughput benefit at 640×480, which is recorded instead of claiming an unmeasured speedup.
