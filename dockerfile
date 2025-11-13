# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_WORKERS=2 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

WORKDIR /app

# System deps (certs, curl for healthcheck, build essentials if needed)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Install deps first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy app (with ownership set to non-root user)
COPY --chown=appuser:appuser . .
USER appuser

# Expose
EXPOSE 8000

# Healthcheck (uses /v1/health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/v1/health || exit 1

# Env hints (override at runtime)
ENV CONTACT_EMAIL=not-provided

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]