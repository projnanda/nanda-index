# -----------------------------------------------------------------------------
# 🐍 Nanda Index Dockerfile
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=6900 \
    WORKERS=2 \
    THREADS=2

# -----------------------------------------------------------------------------
# System Setup
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Working Directory
# -----------------------------------------------------------------------------
WORKDIR /app

# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------
COPY pyproject.toml uv.lock ./
RUN pip install uv && \
    uv pip compile --generate-hashes pyproject.toml -o requirements.txt && \
    uv pip install --system -r requirements.txt

# Explicitly install Gunicorn for index serving
RUN pip install gunicorn

# -----------------------------------------------------------------------------
# Copy Source Code
# -----------------------------------------------------------------------------
COPY . .

# -----------------------------------------------------------------------------
# Runtime Configuration
# -----------------------------------------------------------------------------
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
ENTRYPOINT ["sh", "-c", "gunicorn --workers=${WORKERS} --threads=${THREADS} --bind 0.0.0.0:${PORT} registry:app"]