# Architecture decisions

## ADR001: retain native backend inference

Chosen: FastAPI binary streaming with native Apple MPS/CoreML, plus CPU compatibility. Browser workers handle resizing/encoding/decoding with a fallback. Deferred: browser-only ONNX/WebGPU generation. Reason: the confirmed motion bug is tracking-state/frame ordering, and browser model/operator compatibility is not established. The worker design avoids unnecessary JS buffer clones without claiming every GPU transfer is zero-copy. Reconsider after matched browser-GPU quality/performance evidence exists.

## ADR002: recover identities instead of latching ambiguity

Chosen: time-based automatic selection, appearance retention, ordered current-frame detection, dense landmark refinement and a two-second absence window. Rejected: permanent ambiguity on a single miss or arbitrary box overlap. Evidence: the original state sequence reproduced selected->missing->detected but permanently unselected; focused tests now require recovery without a click. Frame-consistent processing also removes stale asynchronous detection geometry.

## ADR003: quality constrained by a live floor

Chosen: provisionally retain MobileFaceSwap/MPS for Live and standard INSwapper for exports; compare native INT8 under complete browser gates. Historical evidence in STUDIO_VALIDATION.md showed substantial Mobile identity-fidelity loss and standard-model speed limitations. New development screening is recorded separately. No final held-out winner is claimed until reviewed data and complete gates are available. Reconsider when a candidate improves identity fidelity and passes every performance/tracking gate.

## ADR004: measured guidance and explicit privacy

Chosen: source resolution/blur/clipping/approximate pose advice, continuous masks and bounded colour correction; ephemeral sessions with explicit clearing. Rejected: uncalibrated success percentages, universal mug occlusion claims and automatic biometric persistence. Source warnings are advisory; session clearing is best effort and is not physical memory zeroization.

## ADR005: security-patched maintained dependency path

Chosen: ONNX1.22/Pillow13 in the hash-locked FastAPI runtime. Legacy Gradio is not a maintained production dependency because its Pillow upper bound prevents the patched version. The historical file/optional test remains available; no dependency override is used to conceal the conflict. Post-update dependency audit has zero known matches at its recorded timestamp.

## ADR006: reject raw-alpha double blending

The first three-repeat development screen found mean per-clip AdaFace cosine approximately0.299 for applying the raw learned generator gate as external alpha, versus0.539 for the previous binary-coverage blend, at equal87.5% sparse sample swap coverage. The generator already applies its gate internally; applying that gate again weakened the identity contribution.

Rejected: raw soft alpha as the default. Chosen candidate: a continuous smooth transition around the existing .001 coverage boundary, with morphological cleanup, edge feathering and bounded colour matching. In a separate three-repeat matched comparison, its mean per-clip cosine was0.538 versus0.539 for the old binary blend (delta approximately-0.0012), within the predeclared0.02 development tolerance. This supports the boundary implementation, not a held-out or universal quality claim. Raw runs, clipped failures and per-clip bootstrap intervals remain in the local experiment reports.

## ADR007: use lightweight live analysis models

Five complete browser trials of the first candidate failed: roughly2.7–7.4 newly displayed swaps/s with p95 software latency342–640ms. The stage profiler identified SCRFD10GF detection around72ms and R50 recognition around130ms, repeatedly triggered during motion. Generation itself took about16–18ms. This invalidated the earlier assumption that the generator remained the primary live bottleneck.

Chosen revision: verified SCRFD500MF plus MobileFaceNet for live detection/appearance association, retaining106-point refinement and the stronger R50/10GF models for exports and source analysis. A short diagnostic measured detection around9ms and displayed swaps around21–22FPS, with rolling p95 approximately108–115ms. These diagnostics justify full acceptance reruns; they are not a substituted two-minute pass. A registry selects one appearance feature space per runtime so MBF and R50 embeddings cannot mix within a tracker. `AIMS_LIVE_TRACKING=standard` reproduces the heavier analysis path. The light weights are pinned by immutable mirror revision and SHA-256, with author/model provenance recorded.

Temporary overlap uncertainty retains selection and resumes automatically after separation; it never requests another click. General object occlusion remains outside the supported claim.

## ADR008: preserve media duration and display orientation

Real codec tests reproduced sideways exports and a two-second video truncated to its half-second audio track. Studio now enables decoder orientation, writes the decoded display dimensions, records coded/display sizes, and removes the muxer's `-shortest` termination rule. Tests cover 90/180/270-degree rotations, decoded pixels, EXIF rotation and shorter audio. The export remains a constant-frame-rate workflow; exact variable-frame-rate presentation timestamps are not claimed.

## ADR009: separate test artefacts and fail closed

The first full-hour browser body passed its progress, cleanup and RSS assertions, but Playwright teardown failed after parallel commands deleted shared trace files. Each invocation now uses a unique timestamp/process artifact directory. The original error and measured data remain available; the corrected run is a separate experiment. No retry flag conceals the first result. Product and verification fingerprints prevent unrelated scripts/tests from being confused with a new model, while product changes require fresh release evidence.

## ADR010: retain a conservative release boundary

The patched Python lock and compiler-free runtime eliminate the reported Python package advisories. At the time of ADR010, unresolved Debian/FFmpeg dependency findings failed the container gate; the later runtime remediation is recorded in ADR011. Human review, physical webcam and native Safari remain explicitly pending at the author's request. This is a useful local research candidate with professional assurance practices; a public multi-tenant enterprise release requires additional security, access-control and device evidence.

## ADR011: remediate the container runtime without relaxing its gate

Trigger: all platform setup defects were repaired, but the deployment scan still rejected the Debian 13 media/OS packages (209 HIGH, one CRITICAL; scan supplied no fixed versions). Chosen: a multi-architecture, digest-pinned Wolfi base, native Python 3.11, and signed FFmpeg 9.0 packages. Preserve the model/Python dependency locks and compile InsightFace against the same NumPy ABI in a separate build stage. Keep the original HIGH/CRITICAL threshold.

The full ARM64 image passes the local scan with zero HIGH/CRITICAL findings, actual CPU model smoke and six real-codec/media regressions. CI repeats these checks on amd64. A zero advisory match is not a universal security claim. OS packages update at build time, so image hashes/inventories are required evidence. Reconsider when Python 3.11 support, Linux wheel compatibility, package availability or the scan/codec/model checks change. [Validation](CONTAINER_VALIDATION.json).
