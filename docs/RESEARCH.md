# Technical contribution and evaluation plan

## Defensible project framing

**Identity-consistent face editing with motion-aware stabilization and measured adaptive inference.**

This build combines established recognition, assignment, optical flow, and alignment methods. It does not claim a new generative model, state-of-the-art quality, or a research-first method. Its contribution is the integrated pipeline and a reproducible way to test its tradeoffs.

## Implemented experiment dimensions

| Component | Implementation | What to measure |
|---|---|---|
| Identity continuity | Cosine-gated face embeddings, box overlap, global linear assignment; select the initial target identity instead of whichever face is currently leftmost | Identity switches against manually annotated tracks, correct-target edit rate |
| Temporal alignment | Predict five landmarks on the current frame, stabilize small detector jitter, follow large changes immediately | Aligned edit-residual change, visual assessment of eyes/mouth and fast turns |
| Adaptive inference | Full detection every N frames; refresh immediately on failed flow or scene cut | Detector-call count, p50/p95 latency, quality and missed-face tradeoffs |
| Scene boundaries | Luminance/histogram cut heuristic clears geometry and temporal history; target identity reference is retained | False resets, reset delay, incorrect re-identification after cuts |
| Evaluation | Same input/model/provider/thread count across baseline, tracked, adaptive variants; JSON and CSV results | Identity cosine, temporal proxy, latency, detection calls, edited frame count |
| Quality diagnostics | Luminance, face crop size, Laplacian variance, raw source/output identity cosine | Correlation with independently assessed output quality |
| Privacy and provenance | Model-free face blur/pixelation; visible labels; output SHA-256 and model manifest | Missed anonymization regions and provenance integrity, without claiming robust anonymity or C2PA signing |

The modes below describe the retained offline CLI research pipeline in `modules/temporal.py`, `modules/research.py`, and `scripts/benchmark_video.py`. Studio Live now has its own ordered session state machine, 106-point refinement, automatic target selection and binary streaming. Its results must be read under the separate flagship verification scope.

## Exact experimental modes

- **baseline:** detect and recognize on every frame, use current leftmost face, no landmark smoothing. Association is still used to identify consecutive samples for metrics.
- **tracked:** detect every frame, associate identities, use motion prediction and stabilize small alignment jitter. The initial identity remains selected when people cross.
- **adaptive:** the same tracked mode, with periodic detection. A flow failure, new scene, empty track set, or interval expiry triggers full detection.

All three use the same pretrained swapper, encoding settings and sampled identity evaluation. Reports include model hashes, input/output hashes, software versions, thresholds and device providers. The default appearance-distance gate is 0.55, flow forward/backward error is 1.5 px, and detection confidence threshold is 0.5. These thresholds are heuristics and need calibration on a validation set.

## Metrics and their limits

- **Identity cosine:** recognize the edited face using its target alignment, compare with source embedding, sample every ten frames. This shares the pipeline's recognition model and is not an independent proof of identity fidelity.
- **Temporal residual change:** align target and edited faces to 112×112. Let R(t) = edited_crop(t) − target_crop(t). Record mean absolute R(t) − R(t−1) for the same visible track on consecutive frames. Lower can mean less induced flicker, but can also result from weak/no editing. Always report face edits and identity similarity alongside it. Frame gaps and scene cuts reset comparisons.
- **Latency:** mean/p50/p95 per-frame tracking, detection/association, swapping, evaluation and total time. Processing FPS excludes decoding, encoding and model loading. End-to-end time is reported separately. First-inference warmup can affect these numbers.
- **Detector calls:** reduced calls do not imply a proportional FPS increase when swapping is the bottleneck.
- **Identity switches / recall:** deliberately not fabricated in automatic reports. They require labelled ground truth.

## Evaluation needed for a strong college submission

1. Assemble authorized videos spanning one person, crossing people, occlusion, fast turns, low light, motion blur and scene cuts. Keep source identities and near-duplicate videos separated between development and test sets.
2. Annotate the intended target and visible face count per frame on a small held-out subset. Measure correct-target edit rate, identity switches and missed edits.
3. Run baseline, tracked and adaptive with intervals 2, 3 and 5. Repeat runs on the same machine; report medians and spread, not a single best run. Keep image resolution, encoder, provider and thread count fixed.
4. Add ablations for appearance matching, motion prediction, smoothing and cut reset individually before attributing a gain to one component. The current runner ablates complete strategies, not every component independently.
5. Have reviewers compare randomized output pairs for flicker, identity resemblance and expression preservation. Do not equate a numerical proxy with human quality.
6. Publish failed cases and resource consumption alongside results. CPU timing on a short fixture does not establish real-time webcam performance.

## Next research extensions, not implemented or claimed

- **Occlusion-aware compositing:** segment hands, glasses and foreground objects so they stay in front of the swapped face. Evaluate an occlusion-labelled set; a generic face mask is not enough.
- **Joint generation/detection lab:** train a small authenticity classifier on an authorized labelled dataset, then test across manipulation methods and compression levels. [FaceForensics++](https://github.com/ondyari/FaceForensics) supplies an official access process and prescribed splits. Dataset access and GPU training are separate work. Use video/identity-separated splits, AUROC, F1, calibration and unseen-method tests; never report a heuristic as a trained detector.
- **Broader perceptual evaluation:** independent AdaFace diagnostics are now implemented offline. Pose/expression evaluation and completed human assessment remain pending.
- **Quality-aware abstention:** learn thresholds on validation data to skip unreliable edits, then measure coverage versus accepted-result quality. Current image diagnostics are descriptive heuristics, not a learned confidence model.
- **Signed provenance:** sign report manifests or use a proper content-credentials implementation. A visible label and SHA-256 alone do not establish authorship or prevent removal.

## Method references

- [SORT](https://arxiv.org/abs/1602.00763) and [Deep SORT](https://arxiv.org/abs/1703.07402) motivate tracking-by-detection and appearance association. This code is a smaller, task-specific tracker, not a reimplementation of either paper.
- [OpenCV optical-flow documentation](https://github.com/opencv/opencv/blob/5.x/doc/tutorials/others/optical_flow.markdown) describes pyramidal Lucas–Kanade tracking.
- [SciPy linear assignment](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html) supplies the assignment solver.

## Studio engineering evaluation

The current web build adds bounded binary streaming, source revisions, session-local appearance tracking, live-priority export scheduling, native CoreML conversion, and a checkpoint-compatible MobileFaceSwap/PyTorch MPS port. These are engineering contributions, not a newly trained model or a claim of algorithmic novelty.

Use scripts/validate_quality.py for standard-model precision comparisons and identity similarity across the three bundled pairs; use scripts/validate_mobile.py for a numerical comparison against the unmodified Paddle implementation; use frontend's npm run benchmark for actual new displayed swaps and latency. The lighter model is faster but has substantially weaker identity similarity on these examples. See STUDIO_VALIDATION.md for measured results and evaluation limits.
