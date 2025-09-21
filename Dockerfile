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

# Copy Japanese font to system fonts directory
COPY HiraginoSans.ttc /usr/share/fonts/truetype/
RUN fc-cache -fv

# Create data directories
RUN mkdir -p /data/outputs outputs

# Expose port
EXPOSE 8000

# Set environment variable for output directory
ENV SSD_MOUNT_PATH=/data/outputs

# Start Redis and application optimized for 20 concurrent video processing
CMD ["sh", "-c", "redis-server --daemonize yes --port 6379 && sleep 2 && until redis-cli ping >/dev/null 2>&1; do echo 'Waiting for Redis...'; sleep 1; done && echo 'Redis is ready!' && exec gunicorn app:app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 600 --worker-connections 100 --max-requests 500 --max-requests-jitter 50 --worker-tmp-dir /dev/shm --preload"]