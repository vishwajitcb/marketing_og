#!/usr/bin/env python3
"""
Automatic cleanup scheduler for video files
Runs as a background service to clean up old videos and sessions
"""

import os
import time
import threading
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = 'outputs'
CLEANUP_INTERVAL = 300  # 5 minutes
MAX_FILE_AGE = 900  # 15 minutes

def cleanup_old_videos():
    """Clean up videos older than MAX_FILE_AGE seconds"""
    try:
        current_time = time.time()
        cleaned_count = 0

        if not os.path.exists(OUTPUT_DIR):
            return

        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith('.mp4'):
                file_path = os.path.join(OUTPUT_DIR, filename)
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > MAX_FILE_AGE:
                        os.remove(file_path)
                        cleaned_count += 1
                        logger.info(f"Cleaned up old video: {filename} (age: {file_age:.0f}s)")
                except Exception as e:
                    logger.error(f"Error cleaning {filename}: {e}")

        if cleaned_count > 0:
            logger.info(f"Cleanup complete: removed {cleaned_count} old videos")

    except Exception as e:
        logger.error(f"Cleanup error: {e}")

def cleanup_scheduler():
    """Background thread that runs cleanup periodically"""
    while True:
        try:
            cleanup_old_videos()
            time.sleep(CLEANUP_INTERVAL)
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            time.sleep(CLEANUP_INTERVAL)

def start_cleanup_service():
    """Start the cleanup service in a background thread"""
    cleanup_thread = threading.Thread(target=cleanup_scheduler, daemon=True)
    cleanup_thread.start()
    logger.info(f"Cleanup service started (interval: {CLEANUP_INTERVAL}s, max age: {MAX_FILE_AGE}s)")

if __name__ == "__main__":
    # Run as standalone service
    logger.info("Starting video cleanup service...")
    cleanup_scheduler()