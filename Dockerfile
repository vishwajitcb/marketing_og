# Use Python 3.11 slim base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including FFmpeg and Redis
RUN apt-get update && apt-get install -y \
    ffmpeg \
    redis-server \
    redis-tools \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgthread-2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /data/outputs outputs

# Expose port
EXPOSE 8000

# Start Redis and application with embedded commands
CMD ["sh", "-c", "redis-server --daemonize yes --port 6379 && sleep 2 && until redis-cli ping >/dev/null 2>&1; do echo 'Waiting for Redis...'; sleep 1; done && echo 'Redis is ready!' && exec gunicorn app:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 300 --worker-connections 1000 --max-requests 1000 --max-requests-jitter 100 --preload"]