FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies in a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from the build stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app/src

# Make sure the credentials file has the right permissions
RUN if [ -f "regal-autonomy-454806-d1-edf68610c57a.json" ]; then chmod 600 regal-autonomy-454806-d1-edf68610c57a.json; fi

EXPOSE 8050

# Run Alembic migrations, then start the uvicorn application server
CMD alembic upgrade head && uvicorn healthnavi.main:app --host 0.0.0.0 --port 8050
