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

# Copy and setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create data directories
RUN mkdir -p /data/outputs outputs

# Expose port
EXPOSE 8000

# Use entrypoint script to start Redis and app
ENTRYPOINT ["/entrypoint.sh"]