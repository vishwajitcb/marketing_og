#!/usr/bin/env python3
"""
FastAPI Video Processing Server
High-performance, async video processing with bulletproof design
"""

import os
import re
import logging
import uuid
import threading
import time
import json
from datetime import datetime, date
from typing import Tuple, Optional, Dict
from concurrent.futures import ThreadPoolExecutor
import traceback

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel

# Import our video processor
from video_processor_overlay import VideoProcessorOverlay

# Import cleanup service
from cleanup_scheduler import start_cleanup_service

# Redis imports
import redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Bulletproof Video Processor",
    description="High-performance video processing with async support",
    version="2.0.0"
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add rate limiting middleware
app.add_middleware(SlowAPIMiddleware)

# Configuration
INPUT_VIDEO = 'test.mp4'
OUTPUT_DIR = os.getenv('SSD_MOUNT_PATH', '/data/outputs')
ALLOWED_EXTENSIONS = {'mp4'}

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Redis connection
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'), decode_responses=True)

# Fallback dictionaries (for backwards compatibility during transition)
video_jobs: Dict[str, Dict] = {}
user_sessions: Dict[str, Dict] = {}

# Concurrent processing setup for 20 simultaneous videos
MAX_CONCURRENT_VIDEOS = 20
video_processing_semaphore = threading.Semaphore(MAX_CONCURRENT_VIDEOS)
video_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_VIDEOS, thread_name_prefix="VideoWorker")

# Active jobs tracking for monitoring
active_jobs = {}

# Redis helper functions
def set_job_status(job_id: str, job_data: dict):
    """Set job status in Redis"""
    try:
        redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))  # 1 hour expiry
    except:
        # Fallback to memory
        video_jobs[job_id] = job_data

def get_job_status(job_id: str) -> dict:
    """Get job status from Redis"""
    try:
        data = redis_client.get(f"job:{job_id}")
        if data:
            return json.loads(data)
    except:
        pass
    # Fallback to memory
    return video_jobs.get(job_id, {})

# Setup static files and templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic models for request/response
class PreviewRequest(BaseModel):
    name: str
    birthday: str

class GenerateRequest(BaseModel):
    name: str
    birthday: str

class CleanupRequest(BaseModel):
    session_id: str

class JobStatusResponse(BaseModel):
    status: str
    message: str
    download_url: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None

# Japanese translation mappings
JAPANESE_FALLBACK = {
    # Common letter combinations
    'JO': 'ジョ', 'TA': 'タ', 'AR': 'アル', 'LE': 'レ', 'CA': 'カ', 'GE': 'ゲ',
    'AN': 'アン', 'IN': 'イン', 'ON': 'オン', 'EN': 'エン', 'UN': 'ウン',
    'ER': 'エル', 'OR': 'オル', 'IR': 'イル', 'UR': 'ウル', 'AR': 'アル',

    # Numbers (correct Japanese)
    '0': '零', '1': '一', '2': '二', '3': '三', '4': '四', '5': '五',
    '6': '六', '7': '七', '8': '八', '9': '九',
    '10': '十', '11': '十一', '12': '十二', '13': '十三', '14': '十四', '15': '十五',
    '16': '十六', '17': '十七', '18': '十八', '19': '十九', '20': '二十',
    '21': '二十一', '22': '二十二', '23': '二十三', '24': '二十四', '25': '二十五',
    '26': '二十六', '27': '二十七', '28': '二十八', '29': '二十九', '30': '三十',
    '31': '三十一',

    # Individual letters (basic katakana)
    'A': 'ア', 'B': 'ビ', 'C': 'シ', 'D': 'ド', 'E': 'エ', 'F': 'フ', 'G': 'ジ', 'H': 'ハ',
    'I': 'イ', 'J': 'ジ', 'K': 'ケ', 'L': 'ル', 'M': 'ム', 'N': 'ン', 'O': 'オ', 'P': 'ピ',
    'Q': 'ク', 'R': 'ル', 'S': 'ス', 'T': 'ト', 'U': 'ウ', 'V': 'ブ', 'W': 'ウ', 'X': 'クス',
    'Y': 'イ', 'Z': 'ズ'
}

def translate_to_japanese(text: str) -> str:
    """Translate text to Japanese characters"""
    if not text or not text.strip():
        return ""

    text = text.strip()

    # Try exact match first
    if text in JAPANESE_FALLBACK:
        return JAPANESE_FALLBACK[text]

    # Character-by-character fallback
    result = ""
    for char in text:
        result += JAPANESE_FALLBACK.get(char, char)
    return result

# Helper functions (copied from Flask app)
def is_valid_name(name: str) -> bool:
    """Validate name input"""
    try:
        if not name or len(name.strip()) == 0:
            return False
        if len(name.strip()) > 10:
            return False
        if re.search(r'[<>"/\\|?*:\x00-\x1f]', name):
            return False
        return True
    except:
        return False

def is_valid_birthday(birthday: str) -> bool:
    """Validate birthday input with multiple format support"""
    try:
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}$',
            r'^\d{2}/\d{2}/\d{4}$',
            r'^\d{1,2}/\d{1,2}/\d{4}$',
            r'^\d{4}/\d{2}/\d{2}$'
        ]

        for pattern in date_patterns:
            if re.match(pattern, birthday.strip()):
                try:
                    if '/' in birthday:
                        if birthday.count('/') == 2:
                            parts = birthday.split('/')
                            if len(parts[2]) == 4:
                                parsed_date = datetime.strptime(birthday, '%m/%d/%Y').date()
                            else:
                                parsed_date = datetime.strptime(birthday, '%Y/%m/%d').date()
                    else:
                        parsed_date = datetime.strptime(birthday, '%Y-%m-%d').date()

                    today = date.today()
                    if parsed_date > today:
                        return False
                    if parsed_date.year < 1900:
                        return False
                    return True
                except ValueError:
                    continue
        return False
    except:
        return False

def normalize_birthday(birthday: str) -> str:
    """Normalize birthday to YYYY-MM-DD format"""
    birthday = birthday.strip()

    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']:
        try:
            parsed_date = datetime.strptime(birthday, fmt)
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            continue

    raise ValueError(f"Could not parse birthday: {birthday}")

def get_extracted_data(name: str, birthday: str) -> Tuple[str, str, str, str, str, str]:
    """Extract and translate data with bulletproof error handling"""
    try:
        # Extract x, y, z
        x = name[:2].upper().strip()

        # Extract day from birthday (y = day)
        normalized_birthday = normalize_birthday(birthday)
        try:
            if '/' in normalized_birthday:
                _, day = map(int, normalized_birthday.split('/')[:2])
            elif '-' in normalized_birthday:
                parts = normalized_birthday.split('-')
                if len(parts) == 3:
                    day = int(parts[2])
                else:
                    _, day = map(int, parts)
            else:
                day = int(str(normalized_birthday)[-2:])
        except:
            day = len(name)

        y = str(day).zfill(2)

        # Extract z from star sign
        star_sign = get_star_sign(normalized_birthday)
        z = star_sign[:2].upper()

        # Japanese translations using proper mappings
        m = translate_to_japanese(x)  # Katakana for name letters
        n = translate_to_japanese(y)  # Japanese for day number
        o = translate_to_japanese(z)  # Katakana for star sign letters

        return x, y, z, m, n, o

    except Exception as e:
        logger.error(f"Data extraction error: {e}")
        # Return safe defaults
        return "XX", "01", "01", "XX", "十", "XX"

def get_star_sign(birthday: str) -> str:
    """Get star sign from birthday with bulletproof error handling"""
    try:
        if '/' in birthday:
            month, day = map(int, birthday.split('/')[:2])
        elif '-' in birthday:
            parts = birthday.split('-')
            if len(parts) == 3:
                month, day = int(parts[1]), int(parts[2])
            else:
                month, day = map(int, parts)
        else:
            return "Unknown"

        # Zodiac logic
        if (month == 3 and day >= 21) or (month == 4 and day <= 19):
            return "Aries"
        elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
            return "Taurus"
        elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
            return "Gemini"
        elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
            return "Cancer"
        elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
            return "Leo"
        elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
            return "Virgo"
        elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
            return "Libra"
        elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
            return "Scorpio"
        elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
            return "Sagittarius"
        elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
            return "Capricorn"
        elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
            return "Aquarius"
        elif (month == 2 and day >= 19) or (month == 3 and day <= 20):
            return "Pisces"
        else:
            return "Unknown"

    except Exception as e:
        logger.error(f"Star sign error: {e}")
        return "Unknown"

def generate_video_with_semaphore(job_id: str, name: str, birthday: str, output_path: str):
    """Generate video with semaphore control for memory management"""
    try:
        # Acquire semaphore to limit concurrent processing
        logger.info(f"🚦 Job {job_id} waiting for processing slot (active: {MAX_CONCURRENT_VIDEOS - video_processing_semaphore._value})")
        with video_processing_semaphore:
            logger.info(f"🎬 Job {job_id} acquired processing slot, starting generation")

            # Track active job
            active_jobs[job_id] = {
                'start_time': time.time(),
                'name': name,
                'birthday': birthday
            }

            # Update job status
            job_data = get_job_status(job_id)
            job_data['status'] = 'processing'
            job_data['message'] = 'Processing video with memory optimization...'
            set_job_status(job_id, job_data)

            # Process video with memory-optimized settings
            processor = VideoProcessorOverlay(font_size=120)
            success = processor.process_video(INPUT_VIDEO, output_path, name, birthday)

            # Explicitly clean up processor to free memory
            del processor

            logger.info(f"Video processing result - success: {success}, file exists: {os.path.exists(output_path)}, path: {output_path}")

            if success and os.path.exists(output_path):
                job_data['status'] = 'completed'
                job_data['message'] = 'Video generation completed!'
                job_data['download_url'] = f"/download/{os.path.basename(output_path)}"
                job_data['video_url'] = f"/video/{os.path.basename(output_path)}"
                set_job_status(job_id, job_data)

                # Increment video counter for successful generation
                try:
                    redis_client.incr("total_videos_generated")
                    logger.info(f"📊 Incremented video counter")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to increment video counter: {e}")

                logger.info(f"✅ Job {job_id} completed successfully: {output_path}")
            else:
                job_data['status'] = 'failed'
                job_data['error'] = 'Video generation failed. Please try again.'
                job_data['message'] = 'Generation failed'
                set_job_status(job_id, job_data)
                logger.error(f"❌ Job {job_id} failed - success: {success}, exists: {os.path.exists(output_path)}")

    except Exception as e:
        job_data = get_job_status(job_id)
        job_data['status'] = 'failed'
        job_data['error'] = 'Video generation failed. Please try again.'
        job_data['message'] = 'Generation failed - internal error'
        set_job_status(job_id, job_data)
        logger.error(f"Video generation error for job {job_id}: {e}")
    finally:
        # Remove from active jobs
        active_jobs.pop(job_id, None)
        logger.info(f"🏁 Job {job_id} released processing slot")

def generate_video_async_task(job_id: str, name: str, birthday: str, output_path: str):
    """Submit video generation to thread pool executor as background task"""
    video_executor.submit(generate_video_with_semaphore, job_id, name, birthday, output_path)

def cleanup_old_files():
    """Clean up old generated files to prevent disk space issues"""
    try:
        files = []
        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith('.mp4'):
                file_path = os.path.join(OUTPUT_DIR, filename)
                files.append((file_path, os.path.getmtime(file_path)))

        files.sort(key=lambda x: x[1], reverse=True)

        if len(files) > 10:
            for file_path, _ in files[10:]:
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up old file: {file_path}")
                except:
                    pass
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main landing page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/preview")
@limiter.limit("10/minute")
async def preview(request: Request, data: PreviewRequest):
    """Preview extracted data without processing video"""
    try:
        if not is_valid_name(data.name):
            raise HTTPException(status_code=400, detail="Invalid name format")

        if not is_valid_birthday(data.birthday):
            raise HTTPException(status_code=400, detail="Invalid birthday format")

        # Extract data
        x, y, z, m, n, o = get_extracted_data(data.name, data.birthday)
        star_sign = get_star_sign(normalize_birthday(data.birthday))

        return JSONResponse(content={
            'success': True,
            'data': {
                'name': data.name,
                'birthday': data.birthday,
                'extracted': [x, y, z],
                'japanese': [m, n, o],
                'star_sign': star_sign,
                'preview': f"Your characters: {x} → {m}, {y} → {n}, {z} → {o}"
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Preview failed. Please try again.")

@app.post("/generate")
@limiter.limit("100/hour")  # Increased for testing
async def generate_video(request: Request, data: GenerateRequest, background_tasks: BackgroundTasks):
    """Start video generation process"""
    try:
        if not is_valid_name(data.name):
            raise HTTPException(status_code=400, detail="Invalid name format")

        if not is_valid_birthday(data.birthday):
            raise HTTPException(status_code=400, detail="Invalid birthday format")

        safe_name = re.sub(r'[^\w\s-]', '', data.name.strip())[:20]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"{safe_name}_{timestamp}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        session_id = request.headers.get('X-Session-ID', str(uuid.uuid4()))
        if session_id not in user_sessions:
            user_sessions[session_id] = {
                'files': [],
                'created_at': time.time()
            }

        job_id = str(uuid.uuid4())
        job_data = {
            'name': data.name,
            'birthday': data.birthday,
            'output_path': output_path,
            'session_id': session_id,
            'created_at': time.time(),
            'job_id': job_id,
            'status': 'queued',
            'message': 'Video generation started. Please wait...',
            'download_url': None
        }
        set_job_status(job_id, job_data)

        user_sessions[session_id]['files'].append({
            'filename': output_filename,
            'job_id': job_id,
            'created_at': time.time()
        })

        # Extract and translate data for preview
        x, y, z, m, n, o = get_extracted_data(data.name, data.birthday)
        star_sign = get_star_sign(normalize_birthday(data.birthday))

        # Start async video generation
        background_tasks.add_task(generate_video_async_task, job_id, data.name, data.birthday, output_path)

        return JSONResponse(content={
            'success': True,
            'job_id': job_id,
            'session_id': session_id,
            'message': 'Video generation started. Please wait...',
            'data': {
                'name': data.name,
                'birthday': data.birthday,
                'extracted': [x, y, z],
                'japanese': [m, n, o],
                'star_sign': star_sign
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate video error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Video generation failed. Please try again.")

@app.get("/status/{job_id}")
async def get_job_status_endpoint(job_id: str):
    """Get video generation job status"""
    job = get_job_status(job_id)
    if not job:
        # Job not found - return user-friendly error
        return JobStatusResponse(
            status='failed',
            message='Generation failed - high server load',
            download_url=None,
            error='Video could not be generated due to high demand. Please try again after 10 minutes.'
        )

    return JobStatusResponse(
        status=job.get('status', 'unknown'),
        message=job.get('message', ''),
        download_url=job.get('download_url'),
        video_url=job.get('video_url'),
        error=job.get('error')
    )

@app.get("/system/status")
async def get_system_status():
    """Get system and concurrent processing status"""
    available_slots = video_processing_semaphore._value
    active_count = MAX_CONCURRENT_VIDEOS - available_slots

    return JSONResponse(content={
        'success': True,
        'concurrent_processing': {
            'max_slots': MAX_CONCURRENT_VIDEOS,
            'available_slots': available_slots,
            'active_jobs': active_count,
            'active_job_details': [
                {
                    'job_id': job_id,
                    'name': details['name'],
                    'duration': time.time() - details['start_time']
                }
                for job_id, details in active_jobs.items()
            ]
        },
        'memory_optimization': {
            'processing_resolution': '50% of original (540x960 from 1080x1920)',
            'memory_savings': '~75%',
            'ffmpeg_threads': 1,
            'estimated_memory_per_video': '~800MB',
            'total_estimated_memory': f'~{MAX_CONCURRENT_VIDEOS * 0.8:.1f}GB for {MAX_CONCURRENT_VIDEOS} concurrent videos'
        }
    })

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated video file"""
    try:
        # Security: validate filename
        filename = os.path.basename(filename)
        file_path = os.path.join(OUTPUT_DIR, filename)

        if not os.path.exists(file_path):
            logger.error(f"Download file not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")

        if not filename.endswith('.mp4'):
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Clean up old files (keep only last 10)
        cleanup_old_files()

        return FileResponse(
            file_path,
            media_type='video/mp4',
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail="Download failed")

@app.get("/video/{filename}")
@app.head("/video/{filename}")
@app.options("/video/{filename}")
async def stream_video(request: Request, filename: str):
    """Stream video for playback (not download)"""
    try:
        filename = os.path.basename(filename)
        file_path = os.path.join(OUTPUT_DIR, filename)

        if not os.path.exists(file_path):
            logger.error(f"Video file not found: {file_path}")
            raise HTTPException(status_code=404, detail="Video not found")

        if not filename.endswith('.mp4'):
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Get file size for range support
        file_size = os.path.getsize(file_path)

        # Handle range requests for video streaming
        range_header = request.headers.get('range')
        if range_header:
            start, end = 0, file_size - 1
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
        else:
            start, end = 0, file_size - 1

        # Read the file chunk
        chunk_size = end - start + 1

        def iterfile(file_path: str, start: int, chunk_size: int):
            with open(file_path, 'rb') as file:
                file.seek(start)
                remaining = chunk_size
                while remaining:
                    read_size = min(8192, remaining)
                    chunk = file.read(read_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers = {
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(chunk_size),
            'Content-Type': 'video/mp4',
        }

        status_code = 206 if range_header else 200
        return StreamingResponse(
            iterfile(file_path, start, chunk_size),
            status_code=status_code,
            headers=headers,
            media_type='video/mp4'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video streaming error: {e}")
        raise HTTPException(status_code=500, detail="Streaming failed")

@app.post("/cleanup")
@limiter.limit("20/minute")
async def cleanup_session_files(request: Request, data: CleanupRequest):
    """Clean up files associated with a user session"""
    try:
        session_id = data.session_id

        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID required")

        if session_id not in user_sessions:
            return JSONResponse(content={
                'success': True,
                'message': 'No files to clean up'
            })

        files_to_cleanup = user_sessions[session_id]['files']
        cleaned_files = []

        for file_info in files_to_cleanup:
            filename = file_info['filename']
            file_path = os.path.join(OUTPUT_DIR, filename)

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleaned_files.append(filename)
                    logger.info(f"Cleaned up session file: {filename}")
            except Exception as e:
                logger.error(f"Error cleaning up {filename}: {e}")

        # Remove session from tracking
        del user_sessions[session_id]

        return JSONResponse(content={
            'success': True,
            'cleaned_files': cleaned_files,
            'message': f'Cleaned up {len(cleaned_files)} files'
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        raise HTTPException(status_code=500, detail="Cleanup failed")

@app.get("/count")
async def get_video_count():
    """Get total number of videos generated"""
    try:
        count = redis_client.get("total_videos_generated")
        total_count = int(count) if count else 0

        return JSONResponse(content={
            'success': True,
            'total_videos_generated': total_count
        })
    except Exception as e:
        logger.error(f"Failed to get video count: {e}")
        return JSONResponse(content={
            'success': False,
            'total_videos_generated': 0,
            'error': 'Could not retrieve count'
        })

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting FastAPI video processor web server...")
    logger.info(f"Input video: {INPUT_VIDEO}")
    logger.info(f"Output directory: {OUTPUT_DIR}")

    # Test Redis connection
    try:
        redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed, using memory fallback: {e}")

    # Start the cleanup service
    start_cleanup_service()
    logger.info("Automatic cleanup service started")

    # Ensure input video exists
    if not os.path.exists(INPUT_VIDEO):
        logger.warning(f"Input video not found: {INPUT_VIDEO}")

    logger.info(f"🚀 Concurrent video processing initialized: {MAX_CONCURRENT_VIDEOS} slots")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down video processor...")

    # Gracefully shutdown the thread pool
    video_executor.shutdown(wait=True)
    logger.info("✅ ThreadPoolExecutor shutdown complete")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8000,
        log_level='info'
    )