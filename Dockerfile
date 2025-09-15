FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

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

# Copy virtual environment from the build stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the application code
COPY . .

# Make sure the credentials file has the right permissions
RUN if [ -f "/regal-autonomy-454806-d1-edf68610c57a.json" ]; then chmod 600 static-athlete-443111-n4-717c9df24355.json; fi
EXPOSE 8050

# Run the uvicorn application server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050"]
