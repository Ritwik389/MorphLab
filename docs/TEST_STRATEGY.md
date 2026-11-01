# MorphLab verification strategy

This is a local-first research product with explicit release evidence. Passing regression tests is distinct from satisfying motion, quality and physical-device acceptance.

## Entry points

Use the virtual environment's Python (`.venv/bin/python` on Mac/Linux, `.venv/Scripts/python.exe` on Windows):

```text
python scripts/verify.py --suite smoke
python scripts/verify.py --suite regression
python scripts/verify.py --suite evaluation
python scripts/verify.py --suite release --evidence experiments/local-evidence.json
```

Smoke runs protocol/session regressions, frontend type/build checks and frontend unit tests. Regression adds all backend tests and browser workflows against a running app. Evaluation validates data integrity and release evidence. Release combines these and fails closed if any required evidence is missing, stale, failed or unsupported. Exit status is nonzero when required gates are incomplete. JSON, CSV, HTML, JUnit and command logs are saved below `outputs/evaluations/`.

Use `AIMS_TEST_URL` or `--url` for the target server. Browser tests need Chrome; install with `npx playwright install chrome` from frontend. `scripts/build_camera_fixture.py` builds a repeatable 24 FPS fake camera from genuine development speech clips, or an explicitly labelled synthetic fallback if the corpus is absent. Physical camera exposure-to-display is not measured by this fixture.

## Test layers

| Requirement | Risk | Tests/evidence | Gate |
|---|---|---|---|
| Automatic target acquisition | No initial selection | Largest/centre state tests, browser thumbnails | <=500 ms on labelled events |
| Motion recovery | Permanent ambiguity latch | Motion-loss regression and genuine clip replay | <=500 ms reacquisition |
| Stable person identity | Wrong-person edit during crossing | Appearance association, overlap regression; annotated held-out clips | Zero wrong-person edits |
| Temporary absence | Premature target switch | Fake monotonic clock state transitions | Two-second retention, no return oscillation |
| Bounded latency | Queues accumulate old frames | Latest-only queue regression and unique frame IDs | 15 unique swaps/s in every 10s window; p95 <200ms |
| Frame/source ordering | Old identity painted after change | Revision, duplicate-frame and enrollment-race tests | No stale display |
| Source suitability | Invalid/poor inputs silently accepted | No-face/multiple-face input checks, crop size/blur/exposure/approximate pose | Invalid inputs rejected; warnings advisory |
| Export correctness | Wrong duration/audio or leftover files | Existing video regressions and actual short-video integration | Preserved rate/duration/audio; cleanup |
| Stop/cancel/reconnect | Reservations, tracks, tensors retained | Disconnect fault tests; 100 browser cycles; one-hour soak | No active resources after Stop |
| Accelerator failure | Claimed GPU is actually CPU | Warmup fallback and runtime checks; real CPU integration | Actual runtime recorded |
| Model integrity | Corrupt/unverified weights loaded | SHA-256 download verification and parity checks | No unverified model accepted |
| Input security | Oversized media, path traversal, cross-origin writes | Protocol properties, upload limits, origin/path tests | Controlled rejection; no trace disclosure |
| Session privacy | Source survives expiry/purge | Buffer clearing, expiration and session isolation tests | Session references cleared |
| Interface | Unreadable/keyboard-inaccessible controls | Axe serious/critical rules, responsive browser checks | No serious/critical findings in tested states |
| Portability | Mac-only imports break CPU installs | Linux/Windows/macOS CI and CPU model test | Actual matrix result, no inferred pass |

Generated property tests exercise protocol framing and data types. Mocks are used for fault scheduling; real model tests are marked `model` and explicitly separated from mocked evidence. Optional legacy Gradio checks only run when that optional package is installed. Legacy Gradio is excluded from the maintained production dependency lock because its Pillow upper bound prevents the security update.

## Performance and resources

Run `npm run benchmark` in frontend. It records twelve ten-second windows, unique new display IDs, software capture-to-next-animation-frame p95, warmup and actual runtime. Set `AIMS_BENCHMARK_OUTPUT` to preserve each repetition and `AIMS_WORKER=off` for the fallback comparison. Do not run competing inference benchmarks simultaneously. Record background load and power conditions; a generic cloud macOS runner is not the M4 acceptance device.

Run `npx playwright test --config playwright.longevity.config.ts` for 100 Start/Stop cycles. Add `AIMS_RUN_SOAK=1` to enable the one-hour browser soak. The skipped soak in an ordinary run is not a passed release check. RSS includes model/allocator caches; compare settled post-warmup windows, with growth limited to max(10%,128 MiB).

`python scripts/soak.py` is a separate backend-only longevity tool. Its output cannot substitute for browser camera/worker lifecycle evidence.

## Fault injection and load

Cover malformed headers/media, unavailable codecs/FFprobe, denied camera permissions, worker fallback, delayed enrollment, dropped transport, invalid models and queued-job cancellation. Characterise one, two and four sessions plus an export. Only one M4 live session has the 15 FPS target; other loads establish capacity and overload behaviour, not an equal per-client SLA.

## Manual review and data limitations

The corpus contains 36 RAVDESS clips from 12 actors (development 01–04, validation 05–08, held-out 09–12), plus separately labelled derived stress sequences. RAVDESS supplies genuine expression/speech, not broad natural head turns, diverse lighting or real coffee-mug occlusion. Synthetic translations/crossings are not natural-scene ground truth. Those conditions require additional consented/appropriately licensed footage.

Annotate target identities, eligibility/visibility, onset/loss/re-entry events and wrong-person edits. Review assisted annotations before setting `annotations_reviewed=true`. Freeze the corpus before held-out evaluation; tune only on development/validation identities. No held-out model results are fabricated while these prerequisites are incomplete.

Use `experiments/review-template.json` for blinded author review. Score fixed excerpts for identity, expression, flicker, boundaries and lighting; log reviewer count and reveal model names afterwards. Independent review remains pending until reviewers actually submit ratings.

Native Safari and a physical M4 webcam require the checklist in RELEASE.md. Playwright WebKit is not native Safari. Numerical identity scores, visual review, detection coverage and failure rate must be assessed together.

## Executed release additions

The final regression includes real 90/180/270-degree display-matrix video exports, EXIF orientation, a video longer than its audio track, and creation of the labelled CI camera fallback without downloaded corpus files. The audio regression reproduced a two-second clip being truncated to 0.5 seconds before removing the export muxer's `-shortest` option. Orientation checks compare decoded output pixels/dimensions, not only metadata tags.

`scripts/run_longevity.py --soak` owns an isolated app process and records 100 Start/Stop cycles plus a full-hour browser run. Every minute must show fresh swapped frames and a recent presentation; an idle open socket cannot pass. The first full-hour body's frame, cleanup and RSS checks completed, but its Playwright teardown failed because parallel commands shared a trace folder. This infrastructure failure is retained. Test runs now use unique artifact directories; the corrected run is reported independently, with no automatic test retries.

`scripts/characterize_load.py` records one/two/four-session throughput, dropped pending frames, roundtrip distributions and cleanup. The initial characterised batch ran alongside the one-hour GPU soak and research jobs, so it is a stress-load result and cannot substitute for uncontended single-session acceptance. `playwright.pipeline.config.ts` separately screens worker on/off and HUD overhead in varied order, three twenty-second repetitions each. Short screens are labelled as such.

Each report carries a product fingerprint and a separate verification fingerprint. The Git revision identifies the upstream base while local changes remain uncommitted; the product fingerprint identifies the actual tested runtime/frontend. Benchmark startup refuses a server with a different startup fingerprint. Source changes invalidate the corresponding full-product release evidence.
