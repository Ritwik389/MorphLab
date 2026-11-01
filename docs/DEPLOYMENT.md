# Running and deploying MorphLab Studio

The primary website is React/Vite served by FastAPI on port 7860. It uses ordinary HTTP for source enrollment and cancellable exports, and binary WebSockets for live camera frames. The same origin serves the frontend and API. The previous Gradio app is retained behind `--legacy`.

## Local Mac

```bash
./scripts/start_local.sh
```

Open http://127.0.0.1:7860. Stop with Ctrl+C. The startup script builds a missing frontend; it does not reinstall Python dependencies. For a fresh installation use `bash scripts/setup.sh`.

Native CoreML and MobileFaceSwap/MPS run in the local Python process. They are unavailable inside the Linux CPU container on macOS. Use the native launcher for the measured Mac live performance.

## Container

```bash
docker compose up --build
```

The multi-stage image builds the React frontend, installs hash-locked Python dependencies, downloads and verifies base ONNX models, and runs as a non-root user. Health uses `/api/system`; this checks service readiness without loading the swapper. Actual model readiness is returned separately.

For a smaller image build followed by a read-only model mount:

```bash
docker build --build-arg DOWNLOAD_MODELS=0 -t morphlab-studio:local .
docker run --rm -p 127.0.0.1:7860:7860 -v "$PWD/models:/app/models:ro" morphlab-studio:local
```

Without mounted/downloaded weights the landing page still works; neural detection and swapping explain that models are missing. The primary Studio's face effects use the neural detector. The retained legacy privacy modes provide the old Haar detector path.

The base image uses CPU ONNX Runtime. It does not ship Torch, CoreML, or Paddle. Use one application worker: sessions, inference scheduling, jobs, and cleanup are in memory. Multiple workers require shared session/job scheduling and are outside this demo's supported deployment.

## Public hosting

The bundle is ready for a Python/container host. Publishing an account-owned endpoint is a separate step; no public service or paid resource is created by this change.

The host must support HTTP upgrade/WebSockets and HTTPS for browser camera access. Forward `/api/live/*` to the same application with a suitable connection timeout. Static hosting cannot run this inference backend. A free CPU host can demonstrate photos and offline clips; it does not inherit this Mac's GPU or the local live performance result.

Set `AIMS_ALLOWED_HOSTS=your-domain.example` on a public host; the default Host allowlist is for loopback/development. The current OS-library vulnerability gate remains failed, so the built container is a local research deployment candidate, not an approved public upload service.

The app binds to localhost by default; Docker uses 0.0.0.0 internally. The Compose port is restricted to host loopback. Choose access controls and resource limits before making a shared classroom endpoint public. Uploads are limited to 100 MB and videos to 30 seconds/720p. Four exports may be queued, one executes at a time, and live camera connections pause exports between frames. Cancellation remains active while paused. Results and orphaned job folders expire after approximately an hour while the app runs, including folders left by a previous run.

Camera frames and source identity weights are in memory. Stop, navigation, disconnect, and session deletion clean camera resources. Source video uploads and intermediate encodes are deleted after success, failure, or cancellation. Files on disk are not securely erased.

## Reproducible dependencies

`requirements-web.lock` includes the API and WebSocket dependencies. Regenerate intentionally using:

```bash
uv pip compile requirements-web.txt --universal --python-version 3.11 --generate-hashes -o requirements-web.lock
```

Frontend dependencies are locked in `frontend/package-lock.json`. Mac acceleration dependencies are in `requirements-mac.txt`; Paddle is optional research validation only. Re-run model conversion/benchmarking after changing relevant runtime versions or macOS.

The universal web lock retains platform markers: Windows receives `colorama`/`pyreadline3` and excludes Unix-only `uvloop`. `tool.uv.environments` restricts compilation to the supported Python 3.11 runtime. Newly downloaded public model weights are published with mode 0644 so a different non-root Linux container user can read a read-only bind mount. Existing weights downloaded by older revisions may still be owner-only; on Linux, run `find models -type f -name '*.onnx' -exec chmod a+r {} +` before mounting those public model files. Do not apply this command to private recordings or biometric data.

Retain the original source and pretrained model terms when distributing or publishing; see README attribution.

For a slow Docker Desktop package network on an Apple Silicon host, `python scripts/build_container.py` downloads hash-checked Linux dependencies through the host and supplies a separate build context. It generates an offline dependency stage from the maintained Dockerfile, builds `morphlab-studio:flagship`, and expects the verified models to be mounted read-only. Use `--arch x86_64` on an x86 Linux Docker host. This helper does not copy research clips or private artifacts into the image.

Verify an image with `python scripts/smoke_container.py --image morphlab-studio:flagship`. The command chooses an unused loopback port, runs a real CPU photo edit under a two-CPU/four-GiB limit, records image/runtime hashes, and removes only its own temporary container. Initial model loading can be slow on CPU; the request timeout is sixty seconds and the complete job deadline is four minutes. Installation uses `scripts/install_runtime.py` to compile InsightFace against the pinned NumPy ABI before the hash-locked production installation.
