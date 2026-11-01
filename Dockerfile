FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-trixie AS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements-web.lock ./
RUN python -m pip install pip==26.2.2 setuptools==84.2.1 wheel==0.48.0 cython==3.3.0 numpy==1.26.4 && python -m pip install --ignore-installed --prefix=/install --no-build-isolation --require-hashes -r requirements-web.lock

FROM python:3.11-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_ANALYTICS_ENABLED=False \
    AIMS_EXECUTION_PROVIDER=cpu \
    MPLCONFIGDIR=/app/.cache/matplotlib \
    HOME=/home/appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip uninstall -y pip setuptools wheel
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5
WORKDIR /app
COPY --from=dependencies /install/ /usr/local/
COPY . .
COPY --from=frontend /web/dist /app/frontend/dist
ARG DOWNLOAD_MODELS=1
RUN if [ "$DOWNLOAD_MODELS" = "1" ]; then python scripts/download_models.py; fi
RUN useradd --create-home --uid 1000 appuser && \
    mkdir -p /app/outputs /app/.cache /app/models && chown -R appuser:appuser /app
USER appuser
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/api/system', timeout=5)"
CMD ["python", "app.py", "--host", "0.0.0.0"]
