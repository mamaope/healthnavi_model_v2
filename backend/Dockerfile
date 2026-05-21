# Build stage: install production deps only (no pytest, black, mypy, etc.)
FROM python:3.11-slim as builder
WORKDIR /backend

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" VIRTUAL_ENV="/opt/venv"

COPY requirements-prod.txt .
RUN uv pip install --no-cache -r requirements-prod.txt

# Production stage
FROM python:3.11-slim
WORKDIR /backend

# Minimal system deps: ffmpeg (Whisper), curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv" \
    PYTHONPATH="/backend/src:$PYTHONPATH" \
    PLAYWRIGHT_BROWSERS_PATH="/ms-playwright"

RUN python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY . .

# Single RUN for permissions
RUN chmod +x scripts/startup.sh scripts/startup_prod.sh scripts/seed_admin_user.py scripts/check_migrations.py \
    && ([ ! -f /backend/regal-autonomy-454806-d1-edf68610c57a.json ] || chmod 600 /backend/regal-autonomy-454806-d1-edf68610c57a.json)

EXPOSE 8050
CMD ["scripts/startup_prod.sh"]
