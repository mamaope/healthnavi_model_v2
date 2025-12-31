FROM python:3.11-slim as builder

# Set working directory
WORKDIR /backend

# Install uv 
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# Copy requirements.txt
COPY requirements.txt .

RUN uv pip install --no-cache -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /backend

# Install system dependencies for ffmpeg (required by Whisper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from the build stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"
ENV PYTHONPATH="/backend/src:$PYTHONPATH"

# Copy the application code
COPY . .

# Make sure the credentials file has the right permissions
RUN if [ -f "/backend/regal-autonomy-454806-d1-edf68610c57a.json" ]; then chmod 600 /backend/regal-autonomy-454806-d1-edf68610c57a.json; fi

EXPOSE 8050

# Run Alembic migrations, then start the uvicorn application server
CMD alembic upgrade head && uvicorn healthnavi.main:app --host 0.0.0.0 --port 8050 --timeout-keep-alive 120
