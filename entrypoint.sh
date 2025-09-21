#!/bin/bash
set -e

# Start Redis in background
redis-server --daemonize yes --port 6379

# Wait for Redis to be ready
until redis-cli ping; do
  echo "Waiting for Redis..."
  sleep 1
done

echo "Redis is ready!"

# Start the application
exec gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 300 --worker-connections 1000 --max-requests 1000 --max-requests-jitter 100 --preload