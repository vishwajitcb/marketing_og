#!/usr/bin/env python3
"""
FastAPI Video Processing Server
High-performance, async video processing with bulletproof design
"""

import os
import re
import logging
import tempfile
import uuid
import threading
import time
import json
from datetime import datetime, date
from typing import Tuple, Optional, Dict, Union
import traceback

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel
import aiofiles

# Import our video processor
from video_processor_overlay import VideoProcessorOverlay

# Import cleanup service
from cleanup_scheduler import start_cleanup_service

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
OUTPUT_DIR = 'outputs'
ALLOWED_EXTENSIONS = {'mp4'}

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Global dictionaries to track jobs and sessions
video_jobs: Dict[str, Dict] = {}
user_sessions: Dict[str, Dict] = {}

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
        if len(name.strip()) > 50:
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

    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y', '%d-%m-%Y']:
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
                month, day = map(int, normalized_birthday.split('/')[:2])
            elif '-' in normalized_birthday:
                parts = normalized_birthday.split('-')
                if len(parts) == 3:
                    month, day = int(parts[1]), int(parts[2])
                else:
                    month, day = map(int, parts)
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

async def generate_video_async(job_id: str, name: str, birthday: str, output_path: str):
    """Generate video asynchronously"""
    try:
        logger.info(f"Starting async video generation for job {job_id}")
        video_jobs[job_id]['status'] = 'processing'
        video_jobs[job_id]['message'] = 'Processing video...'

        processor = VideoProcessorOverlay(font_size=120)
        success = processor.process_video(INPUT_VIDEO, output_path, name, birthday)

        if success and os.path.exists(output_path):
            video_jobs[job_id]['status'] = 'completed'
            video_jobs[job_id]['message'] = 'Video generation completed!'
            video_jobs[job_id]['download_url'] = f"/download/{os.path.basename(output_path)}"
            video_jobs[job_id]['video_url'] = f"/video/{os.path.basename(output_path)}"
            logger.info(f"Video generation completed for job {job_id}: {output_path}")
        else:
            video_jobs[job_id]['status'] = 'failed'
            video_jobs[job_id]['error'] = 'Video could not be generated due to high demand. Please try again after 10 minutes.'
            video_jobs[job_id]['message'] = 'Generation failed - high server load'
            logger.error(f"Video generation failed for job {job_id}")

    except Exception as e:
        video_jobs[job_id]['status'] = 'failed'
        # Provide user-friendly error message for high demand scenarios
        if "timeout" in str(e).lower() or "memory" in str(e).lower():
            video_jobs[job_id]['error'] = 'Video could not be generated due to high demand. Please try again after 10 minutes.'
            video_jobs[job_id]['message'] = 'Generation failed - high server load'
        else:
            video_jobs[job_id]['error'] = 'Video could not be generated due to high demand. Please try again after 10 minutes.'
            video_jobs[job_id]['message'] = 'Generation failed - please retry'
        logger.error(f"Async video generation error for job {job_id}: {e}")

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
@limiter.limit("3/hour")
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
        video_jobs[job_id] = {
            'name': data.name,
            'birthday': data.birthday,
            'output_path': output_path,
            'session_id': session_id,
            'created_at': time.time()
        }

        user_sessions[session_id]['files'].append({
            'filename': output_filename,
            'job_id': job_id,
            'created_at': time.time()
        })

        video_jobs[job_id].update({
            'job_id': job_id,
            'session_id': session_id,
            'status': 'queued',
            'message': 'Video generation started. Please wait...',
            'download_url': None
        })

        # Extract and translate data for preview
        x, y, z, m, n, o = get_extracted_data(data.name, data.birthday)
        star_sign = get_star_sign(normalize_birthday(data.birthday))

        # Start async video generation
        background_tasks.add_task(generate_video_async, job_id, data.name, data.birthday, output_path)

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
async def get_job_status(job_id: str):
    """Get video generation job status"""
    if job_id not in video_jobs:
        # Job was lost due to worker crash - return user-friendly error
        return JobStatusResponse(
            status='failed',
            message='Generation failed - high server load',
            download_url=None,
            error='Video could not be generated due to high demand. Please try again after 10 minutes.'
        )

    job = video_jobs[job_id]
    return JobStatusResponse(
        status=job.get('status', 'unknown'),
        message=job.get('message', ''),
        download_url=job.get('download_url'),
        video_url=job.get('video_url'),
        error=job.get('error')
    )

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

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting FastAPI video processor web server...")
    logger.info(f"Input video: {INPUT_VIDEO}")
    logger.info(f"Output directory: {OUTPUT_DIR}")

    # Start the cleanup service
    start_cleanup_service()
    logger.info("Automatic cleanup service started")

    # Ensure input video exists
    if not os.path.exists(INPUT_VIDEO):
        logger.warning(f"Input video not found: {INPUT_VIDEO}")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8000,
        log_level='info'
    )