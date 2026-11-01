# Release gates and operating runbook

## Automated release

1. Install from `requirements-web.lock` and `frontend/package-lock.json` on a clean environment. Model downloads must pass the pinned SHA-256 checks.
2. Build the frontend, start `python app.py` on localhost:7860, build the camera fixture, and run `scripts/verify.py --suite regression`.
3. Run the development/validation comparisons from EXPERIMENTS.md. Record failed alternatives and freeze the winning configuration before evaluating held-out identities.
4. Run five two-minute finalist browser trials sequentially. Preserve each raw result; require every ten-second interval >=15 unique new displayed swaps/s and p95 software capture-to-display <200ms. Track skips/dropped frames separately.
5. Run 100 browser Start/Stop cycles and the explicitly enabled one-hour browser soak. Require settled RSS growth <=max(10%,128 MiB) and complete resource cleanup.
6. Run production dependency and container audits. Known advisory matches must be resolved or the security gate remains failed. A dependency audit is not a penetration test or certification.
7. Build and smoke-test the deployment container with read-only model mounts; verify actual photo output, headers, readiness, and controlled failures.
8. Attach evidence to the exact source fingerprint, model/data hashes and tested hardware. `verify.py --suite release` exits nonzero for required missing/failed/stale evidence.

Use `experiments/local-evidence.json` (not committed) to bind each gate to its source digest, artifact and artifact SHA-256. Supported gate names are in scripts/verify.py. Do not mark manual conditions Passed from a replay result.

Run `python scripts/assemble_evidence.py` to build bindings from existing measured artefacts. `python scripts/finish_report.py outputs/evaluations/flagship-release` adds the comparison summaries/figures to the release report, and `python scripts/bundle_evidence.py` packages the permitted evidence. The archive excludes raw recordings, private thumbnails, embeddings, model weights and browser traces. Keep the separate local failure traces for debugging.

Human review, native Safari and physical webcam checks are intentionally pending at the author's request. The reviewed/frozen held-out gate and independent-review claims remain incomplete. Unresolved OS-library scan findings independently prevent public-release approval; see SECURITY.md. A green functional suite does not override these release boundaries.

## Physical M4 webcam checklist

- Cold launch; verify camera remains off before Start. Enroll a clear source and confirm the actual MPS/CoreML runtime.
- Turn approximately +/-45 degrees, nod, speak, smile, translate and change distance. Record failed poses, recovery times, eligible coverage and unique displayed FPS.
- Test a second consenting person crossing, overlap, departure and re-entry. Confirm no wrong-person swaps, two-second retention and stable Person labels/thumbnails.
- Switch source and target while processing. Check that old edits do not flash after the change.
- Deny permission, Stop/restart, navigate away, disconnect and reconnect. Verify camera indicator and server reservations clear.
- Confirm temporary passthrough during unreliable geometry. General mug/phone occlusion segmentation is not implemented and must not be claimed.

## Native Safari checklist

Use the actual Safari application on the Mac. Verify all three pages, theme, file selection, webcam permission/denial, automatic source-to-swap transition, person selection, worker/fallback path, Stop/navigation cleanup, downloads and keyboard focus. Native Safari is distinct from Playwright WebKit. Do not change Safari automation/security settings without user authorization.

## Windows checklist

Run `powershell -File scripts/setup_windows.ps1`, then `powershell -File scripts/start_windows.ps1`. Python 3.11, Node 22, FFmpeg and Microsoft C++ Build Tools may be needed. Verify landing, source checks, actual CPU photo processing, exports and camera lifecycle. No Windows CPU 15 FPS promise is made. CI workflow files alone are not a completed Windows validation run.

## Deployment and rollback

The app binds to 127.0.0.1 by default. For a container, use the provided Dockerfile and expose port7860 through an HTTPS reverse proxy. Hosted models execute on the server, not a visiting Mac. Keep uploads and model weights separate from immutable app code; retain model hashes and the tested container digest.

This local research demo uses unguessable session/job URLs as capabilities; it is not a multi-tenant enterprise identity system. Public deployments need deployment-specific access control, quotas, HTTPS and resource budgeting before accepting unrelated users' private media. Do not publish raw private corpus recordings or embeddings.

Before replacing a deployment, retain the previous tested image tag/digest and compatible model manifest. Smoke-test the candidate on a temporary port, promote it only when required gates pass, and roll back to the previous image if readiness or real inference fails. Existing in-memory live sessions restart on deployment; do not imply seamless session migration.

Troubleshooting: if inference is slow, inspect actual provider and fallback reason before lowering resolution. If no face is detected, improve lighting and framing. If models are corrupt, rerun the checksum-verified downloader. If FFprobe fails, return the user-facing format guidance and retain a sanitized diagnostic log. Keep local logs free of raw frames and embeddings.
