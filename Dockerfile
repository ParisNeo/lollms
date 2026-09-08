# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11
ARG NODE_VERSION=20

FROM node:${NODE_VERSION}-bookworm-slim AS frontend-builder
WORKDIR /build/frontend/webui

COPY frontend/webui/package*.json ./
RUN npm ci

COPY frontend/webui/ ./
RUN npm run build && mkdir -p /build/frontend/dist && cp -a dist/. /build/frontend/dist/

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

EXPOSE 9642

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS http://127.0.0.1:9642/api/welcome-info >/dev/null || exit 1

CMD ["python", "main.py"]
