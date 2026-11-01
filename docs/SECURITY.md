# Security verification scope

The maintained production app is FastAPI/React, local-first and bound to loopback by default. Review relevant OWASP ASVS 5.0 categories for input validation, file handling, origin boundaries, process execution, configuration, resource limits and sensitive-data handling. This is a documented verification subset, not ASVS certification.

Implemented checks include bounded WebSocket/header/media dimensions, strict control types, same-origin writes/WebSockets, sample-path allowlists, safe FFmpeg argument lists, upload size limits and file closing on rejection, hash-verified model downloads, no-store session responses, no raw biometrics in telemetry, admission limits, cancellation cleanup and source/session revision invalidation.

Live frames, source-dependent tensors, thumbnails and appearance references remain in local server/browser memory during the session. Stop/purge clears references and best-effort overwrites owned NumPy arrays. Python, Torch, browser and driver allocators may retain physical copies; physical memory erasure and compliance certification are not claimed. Generic model weights stay warm independently of session identity.

The initial production dependency audit matched advisories for ONNX1.18 and Pillow12.1.1. The maintained lock upgrades to ONNX1.22 and Pillow13.0 and excludes unused Gradio, whose upper Pillow bound prevented the security update. The post-update audit reported no known vulnerabilities at execution time; save the timestamped raw JSON. Optional legacy code is retained as historical compatibility code and is not shipped as a supported production dependency path.

The local app has no enterprise login, SSO or tenant authorization boundary. Its random IDs are bearer capabilities. Never expose a public multi-user upload service merely because local regression tests pass. Container/host configuration and access control require their own deployment evidence. Model code licences and pretrained-weight/data restrictions are separate from vulnerability scans.

## Recorded verification subset

The mapping in `experiments/security-controls.json` identifies exact regression tests for selected requirements from [ASVS 5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/en): WebSocket origins (V4.4.2), bounded upload/pixel sizes (V5.2.1/V5.2.6), trusted file paths (V5.3.2), and resource cleanup (V1.4.3). These are application-specific subsets, not a claim that every clause or ASVS level is satisfied. Host-header allowlisting also prevents arbitrary hosts reaching the local service. Set `AIMS_ALLOWED_HOSTS` explicitly for a deployment domain.

The final runtime image separates build tools from production, uses Debian 13, and removes bundled pip/setuptools from the runtime. Trivy found zero Python-package advisories in that image, but reported 207 high and one critical OS-library findings across 42 advisory IDs at the recorded scan time. Its database supplied no fixed package versions for those findings. The critical report concerns libxml2 (CVE-2026-6653). These are scanner findings, not a completed application-reachability assessment. They are retained without an `ignore-unfixed` exemption, and the conservative container-security gate fails until resolved or properly triaged.

The maintained `scripts/smoke_container.py` checks actual CPU inference with read-only models, source-fingerprint agreement, downloads and session cleanup. An initial ten-second cold-start poll timed out; its log is preserved. The rerun uses a documented sixty-second request timeout and records individual polling durations. A passing model smoke check does not turn the separate vulnerability gate green.
