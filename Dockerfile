FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# The index digest includes Linux amd64 and arm64. Wolfi's signed packages
# supply maintained Python 3.11 and FFmpeg 9 without mixing distributions.
FROM cgr.dev/chainguard/wolfi-base@sha256:88a20e2d017bd20cdc0cb3910de603e7bea9512a6c351a8dd3c9df212ab03d73 AS runtime-base
RUN apk add --no-cache python-3.11 ffmpeg-9.0 libgomp

FROM runtime-base AS dependencies
RUN apk add --no-cache build-base python-3.11-dev && python3.11 -m venv /opt/venv
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements-build.lock requirements-web.lock ./
RUN /opt/venv/bin/python -m pip install --require-hashes --no-deps -r requirements-build.lock && /opt/venv/bin/python -m pip install --no-build-isolation --require-hashes -r requirements-web.lock

FROM runtime-base
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    AIMS_EXECUTION_PROVIDER=cpu \
    MPLCONFIGDIR=/app/.cache/matplotlib \
    HOME=/home/nonroot
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
RUN python -m pip uninstall -y pip setuptools wheel
COPY . .
COPY --from=frontend /web/dist /app/frontend/dist
ARG DOWNLOAD_MODELS=1
RUN if [ "$DOWNLOAD_MODELS" = "1" ]; then python scripts/download_models.py; fi
RUN mkdir -p /app/outputs /app/.cache /app/models && chown -R 65532:65532 /app
USER 65532:65532
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/api/system', timeout=5)"
CMD ["python", "app.py", "--host", "0.0.0.0"]
