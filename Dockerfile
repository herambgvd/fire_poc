# Fire & Smoke Detection — Web POC (CPU-only).
#   docker compose up -d --build   →   http://localhost:8080
FROM python:3.11-slim

# System libs: ffmpeg (RTSP/video decode) + OpenCV runtime deps.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 curl \
 && rm -rf /var/lib/apt/lists/*

# uv — fast installer (drop-in for pip).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_SYSTEM_PYTHON=1 UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# CPU-only torch first, from the CPU wheel index — avoids the multi-GB CUDA
# build that the default index would pull (this POC is CPU-only by design).
RUN uv pip install --system --index-url https://download.pytorch.org/whl/cpu \
      torch torchvision

# Remaining Python deps (torch/torchvision already satisfied above).
COPY requirements-web.txt .
RUN uv pip install --system -r requirements-web.txt

# App source (models included). See .dockerignore for exclusions.
COPY . .

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://localhost:8080/api/status || exit 1

CMD ["python", "-m", "server.main"]
