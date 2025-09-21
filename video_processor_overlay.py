#!/usr/bin/env python3
"""
Video Processor with Transparent Text Overlays
Overlays Japanese text directly onto video frames at specific timestamps
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
import re
from datetime import date
from typing import Tuple, Optional, List
import os
import urllib.request
import tempfile

# FFmpeg availability check
import subprocess
import shutil

def check_ffmpeg_availability():
    """Check if FFmpeg is available - prioritize imageio_ffmpeg for server deployment"""
    try:
        # Try imageio_ffmpeg first (for server deployment)
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    except ImportError:
        pass
    except Exception:
        pass

    try:
        # Fallback to system ffmpeg in PATH
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            return ffmpeg_path

        return None
    except:
        return None

FFMPEG_PATH = check_ffmpeg_availability()
FFMPEG_AVAILABLE = FFMPEG_PATH is not None

# MoviePy import with fallback (keeping as backup)
try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    try:
        from moviepy import VideoFileClip
        MOVIEPY_AVAILABLE = True
    except ImportError:
        MOVIEPY_AVAILABLE = False
        VideoFileClip = None

# Translation fallback (disabled - using hardcoded mappings)
TRANSLATION_AVAILABLE = False

# ASCII mapping for all characters - hardcoded for visibility
ASCII_MAPPING = {
    # Letters A-Z
    'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F', 'G': 'G', 'H': 'H',
    'I': 'I', 'J': 'J', 'K': 'K', 'L': 'L', 'M': 'M', 'N': 'N', 'O': 'O', 'P': 'P',
    'Q': 'Q', 'R': 'R', 'S': 'S', 'T': 'T', 'U': 'U', 'V': 'V', 'W': 'W', 'X': 'X',
    'Y': 'Y', 'Z': 'Z',
    
    # Numbers 0-9
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5',
    '6': '6', '7': '7', '8': '8', '9': '9',
    
    # Star signs (first 2 letters)
    'CA': 'CA', 'AQ': 'AQ', 'PI': 'PI', 'AR': 'AR', 'TA': 'TA', 'GE': 'GE',
    'CA': 'CA', 'LE': 'LE', 'VI': 'VI', 'LI': 'LI', 'SC': 'SC', 'SA': 'SA',
    
    # Common combinations
    'JO': 'JO', '19': '19', 'TA': 'TA'
}

# Japanese fallback translations (for reference only)
JAPANESE_FALLBACK = {
    # Common letter combinations (more accurate)
    'JO': 'ジョ', 'TA': 'タ', 'AR': 'アル', 'LE': 'レ', 'CA': 'カ', 'GE': 'ゲ',
    'AN': 'アン', 'IN': 'イン', 'ON': 'オン', 'EN': 'エン', 'UN': 'ウン',
    'ER': 'エル', 'OR': 'オル', 'IR': 'イル', 'UR': 'ウル', 'AR': 'アル',
    
    # Numbers (correct Japanese)
    '0': '零', '1': '一', '2': '二', '3': '三', '4': '四', '5': '五',
    '6': '六', '7': '七', '8': '八', '9': '九',
    '10': '十', '11': '十一', '12': '十二', '13': '十三', '14': '十四', '15': '十五',
    '16': '十六', '17': '十七', '18': '十八', '19': '十九', '20': '二十',
    
    # Individual letters (basic katakana - context dependent but better than nothing)
    'A': 'ア', 'B': 'ビ', 'C': 'シ', 'D': 'ド', 'E': 'エ', 'F': 'フ', 'G': 'ジ', 'H': 'ハ',
    'I': 'イ', 'J': 'ジ', 'K': 'ケ', 'L': 'ル', 'M': 'ム', 'N': 'ン', 'O': 'オ', 'P': 'ピ',
    'Q': 'ク', 'R': 'ル', 'S': 'ス', 'T': 'ト', 'U': 'ウ', 'V': 'ブ', 'W': 'ウ', 'X': 'クス',
    'Y': 'イ', 'Z': 'ズ'
}

# Comprehensive katakana mapping for foreign names (from romtest.py logic)
KATAKANA_MAP = {
    'a': 'ア', 'i': 'イ', 'u': 'ウ', 'e': 'エ', 'o': 'オ',
    'ka': 'カ', 'ki': 'キ', 'ku': 'ク', 'ke': 'ケ', 'ko': 'コ',
    'sa': 'サ', 'shi': 'シ', 'su': 'ス', 'se': 'セ', 'so': 'ソ',
    'ta': 'タ', 'chi': 'チ', 'tsu': 'ツ', 'te': 'テ', 'to': 'ト',
    'na': 'ナ', 'ni': 'ニ', 'nu': 'ヌ', 'ne': 'ネ', 'no': 'ノ',
    'ha': 'ハ', 'hi': 'ヒ', 'fu': 'フ', 'he': 'ヘ', 'ho': 'ホ',
    'ma': 'マ', 'mi': 'ミ', 'mu': 'ム', 'me': 'メ', 'mo': 'モ',
    'ya': 'ヤ', 'yu': 'ユ', 'yo': 'ヨ',
    'ra': 'ラ', 'ri': 'リ', 'ru': 'ル', 're': 'レ', 'ro': 'ロ',
    'wa': 'ワ', 'wo': 'ヲ', 'n': 'ン',
    'ga': 'ガ', 'gi': 'ギ', 'gu': 'グ', 'ge': 'ゲ', 'go': 'ゴ',
    'za': 'ザ', 'ji': 'ジ', 'zu': 'ズ', 'ze': 'ゼ', 'zo': 'ゾ',
    'da': 'ダ', 'ji': 'ヂ', 'zu': 'ヅ', 'de': 'デ', 'do': 'ド',
    'ba': 'バ', 'bi': 'ビ', 'bu': 'ブ', 'be': 'ベ', 'bo': 'ボ',
    'pa': 'パ', 'pi': 'ピ', 'pu': 'プ', 'pe': 'ペ', 'po': 'ポ',
    'kya': 'キャ', 'kyu': 'キュ', 'kyo': 'キョ',
    'sha': 'シャ', 'shu': 'シュ', 'sho': 'ショ',
    'cha': 'チャ', 'chu': 'チュ', 'cho': 'チョ',
    'nya': 'ニャ', 'nyu': 'ニュ', 'nyo': 'ニョ',
    'hya': 'ヒャ', 'hyu': 'ヒュ', 'hyo': 'ヒョ',
    'mya': 'ミャ', 'myu': 'ミュ', 'myo': 'ミョ',
    'rya': 'リャ', 'ryu': 'リュ', 'ryo': 'リョ',
    'gya': 'ギャ', 'gyu': 'ギュ', 'gyo': 'ギョ',
    'ja': 'ジャ', 'ju': 'ジュ', 'jo': 'ジョ',
    'bya': 'ビャ', 'byu': 'ビュ', 'byo': 'ビョ',
    'pya': 'ピャ', 'pyu': 'ピュ', 'pyo': 'ピョ',
    # Additional sounds for foreign names
    'dh': 'ド', 'th': 'ス', 'v': 'ブ', 'f': 'フ', 'l': 'ル',
    'x': 'クス', 'q': 'ク', 'w': 'ウ', 'y': 'イ'
}

# Extended fallback mapping for sounds not in katakana
KATAKANA_FALLBACK = {
    'b': 'ブ', 'c': 'ク', 'd': 'ド', 'f': 'フ', 'g': 'グ', 'h': 'ハ',
    'j': 'ジ', 'k': 'ク', 'l': 'ル', 'm': 'ム', 'n': 'ン', 'p': 'プ',
    'q': 'ク', 'r': 'ル', 's': 'ス', 't': 'ト', 'v': 'ブ', 'w': 'ウ',
    'x': 'クス', 'y': 'イ', 'z': 'ズ',
    # Special combinations
    'dh': 'ド', 'th': 'ス', 'ph': 'フ', 'ch': 'チ', 'sh': 'シ',
    'ck': 'ック', 'ng': 'ング', 'qu': 'ク', 'gh': 'グ'
}

STAR_SIGNS = [
    ("Capricorn", (12, 22), (1, 19)), ("Aquarius", (1, 20), (2, 18)), ("Pisces", (2, 19), (3, 20)),
    ("Aries", (3, 21), (4, 19)), ("Taurus", (4, 20), (5, 20)), ("Gemini", (5, 21), (6, 20)),
    ("Cancer", (6, 21), (7, 22)), ("Leo", (7, 23), (8, 22)), ("Virgo", (8, 23), (9, 22)),
    ("Libra", (9, 23), (10, 22)), ("Scorpio", (10, 23), (11, 21)), ("Sagittarius", (11, 22), (12, 21))
]


class VideoProcessorOverlay:
    """Video processor with transparent text overlays"""
    
    def __init__(self, font_size: int = 120):
        # Increase font size by 50%
        self.font_size = int(font_size * 1.5)
        self.logger = self._setup_logging()
        self.font = self._load_japan_ramen_font()
        
        # Hardcoded timestamps as requested
        self.overlay_timestamps = [
            (1.435, 2.670),   # Slot A: ジョ
            (4.05, 5.240),    # Slot B: 十五  
            (6.63, 7.730),    # Slot C: タ
            (10.740, 11.635), # Slot D: ジョ 十五 タ (all together)
            (13.240, 15.600), # Slot E: Japanese name
            (15.601, 999.0)   # Slot F: English name (to video end)
        ]
        
        # Verify audio processing tools availability
        self._verify_audio_tools()
    
    def _verify_audio_tools(self):
        """Verify audio processing tools are available"""
        global FFMPEG_AVAILABLE, MOVIEPY_AVAILABLE
        
        # Check FFmpeg first (preferred)
        if FFMPEG_AVAILABLE:
            try:
                # Test FFmpeg functionality
                result = subprocess.run([FFMPEG_PATH, '-version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    pass  # Removed log(f"✅ FFmpeg is available and ready for audio processing: {FFMPEG_PATH}")
                else:
                    self.logger.warning("⚠️ FFmpeg found but not working properly")
                    FFMPEG_AVAILABLE = False
            except Exception as e:
                self.logger.warning(f"⚠️ FFmpeg test failed: {e}")
                FFMPEG_AVAILABLE = False
        
        # Check MoviePy as backup
        if MOVIEPY_AVAILABLE:
            try:
                # Test basic MoviePy functionality
                test_clip = VideoFileClip
                pass  # Removed log("✅ MoviePy is available as backup for audio processing")
            except Exception as e:
                self.logger.warning(f"⚠️ MoviePy import failed: {e}")
                MOVIEPY_AVAILABLE = False
        
        # Final status
        if FFMPEG_AVAILABLE:
            pass  # Removed log("🎵 Audio processing: FFmpeg (primary)")
        elif MOVIEPY_AVAILABLE:
            pass  # Removed log("🎵 Audio processing: MoviePy (backup)")
        else:
            self.logger.warning("⚠️ No audio processing tools available - videos will be processed without audio")
            self.logger.warning("⚠️ Install FFmpeg with: conda install -c conda-forge ffmpeg")
            self.logger.warning("⚠️ Or install MoviePy with: pip install moviepy")
    
    def _setup_logging(self):
        """Setup logging"""
        logger = logging.getLogger('VideoProcessorOverlay')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _download_japan_ramen_font(self) -> Optional[str]:
        """Download Japanese font - EXACT COPY FROM LEAN VERSION"""
        try:
            font_urls = [
                "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJK-Regular.otf",
                "https://fonts.gstatic.com/s/notosanscjk/v36/NotoSansCJK-Regular.otf"
            ]
            
            font_path = os.path.join(tempfile.gettempdir(), "japanese_font.otf")
            if not os.path.exists(font_path):
                for url in font_urls:
                    try:
                        urllib.request.urlretrieve(url, font_path)
                        return font_path
                    except:
                        continue
            return font_path
        except:
            return None
    
    def _load_japan_ramen_font(self, font_size: int = None) -> Optional[ImageFont.FreeTypeFont]:
        """Load HiraginoSans.ttc font with RAQM layout support"""
        font_path = "HiraginoSans.ttc"
        effective_font_size = font_size if font_size is not None else self.font_size

        try:
            # Use RAQM layout engine for proper Japanese text rendering
            font = ImageFont.truetype(font_path, effective_font_size, layout_engine=ImageFont.Layout.RAQM)
            pass  # Removed log(f"# Using HiraginoSans.ttc with RAQM layout (size: {effective_font_size})")
            return font
        except Exception as e:
            self.logger.error(f"❌ Could not load HiraginoSans.ttc: {e}")
            raise RuntimeError("HiraginoSans.ttc font is required but could not be loaded")
        
        # Try system fonts (fallback)
        system_fonts = [
            "C:/Windows/Fonts/msgothic.ttc", "C:/Windows/Fonts/meiryo.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
        ]
        
        for font_path in system_fonts:
            if os.path.exists(font_path):
                try:
                    # Try bold version first, then regular
                    try:
                        font = ImageFont.truetype(font_path, self.font_size, index=1)  # Try bold
                        pass  # Removed log(f"# Using system font (bold): {font_path}")
                        return font
                    except:
                        font = ImageFont.truetype(font_path, self.font_size, index=0)  # Regular
                        pass  # Removed log(f"# Using system font (regular): {font_path}")
                        return font
                except:
                    continue
        
        # Download font if none found (EXACT COPY from lean version)
        downloaded_font = self._download_japan_ramen_font()
        if downloaded_font:
            try:
                # Try bold version first, then regular
                try:
                    font = ImageFont.truetype(downloaded_font, self.font_size, index=1)  # Try bold
                    pass  # Removed log(f"# Using downloaded font (bold): {downloaded_font}")
                    return font
                except:
                    font = ImageFont.truetype(downloaded_font, self.font_size, index=0)  # Regular
                    pass  # Removed log(f"# Using downloaded font (regular): {downloaded_font}")
                    return font
            except:
                pass
        
        # Fallback (EXACT COPY from lean version)
        return ImageFont.load_default()
    
    def _load_geishta_font(self, font_size: int = None) -> Optional[ImageFont.FreeTypeFont]:
        """Load Geishta font for English names with larger size"""
        geishta_fonts = [
            "Geishta.ttf",
            "Geishta.otf",
            "geishta.ttf",
            "geishta.otf",
            "Geishta-Regular.ttf",
            "Geishta-Regular.otf"
        ]

        # Use larger font size for Geishta to match visual size of Japanese font
        base_font_size = font_size if font_size is not None else self.font_size
        geishta_font_size = int(base_font_size * 2)  # 100% larger
        
        for font_path in geishta_fonts:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, geishta_font_size)
                    pass  # Removed log(f"# Using Geishta font: {font_path} (size: {geishta_font_size})")
                    return font
                except Exception as e:
                    self.logger.warning(f"❌ Could not load Geishta font {font_path}: {e}")
                    continue
        
        # Fallback to default font
        self.logger.warning("⚠️ Geishta font not found, using default font")
        return ImageFont.load_default()
    
    def _get_star_sign(self, birthday: str) -> str:
        """Get star sign from birthday"""
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
            
            for sign, (start_month, start_day), (end_month, end_day) in STAR_SIGNS:
                if (month == start_month and day >= start_day) or (month == end_month and day <= end_day):
                    return sign
            return "Capricorn"
        except:
            return "Unknown"
    
    def _convert_name_to_katakana(self, name: str) -> str:
        """
        Convert a name to Japanese katakana using the improved logic from romtest.py
        """
        if not name or not name.strip():
            return ""
        
        name = name.strip()
        romaji_lower = name.lower()
        katakana_name = ""
        
        # Try to match common patterns
        i = 0
        while i < len(romaji_lower):
            # Try 3-character combinations first
            if i + 3 <= len(romaji_lower):
                three_char = romaji_lower[i:i+3]
                if three_char in KATAKANA_MAP:
                    katakana_name += KATAKANA_MAP[three_char]
                    i += 3
                    continue
            
            # Try 2-character combinations
            if i + 2 <= len(romaji_lower):
                two_char = romaji_lower[i:i+2]
                if two_char in KATAKANA_MAP:
                    katakana_name += KATAKANA_MAP[two_char]
                    i += 2
                    continue
                elif two_char in KATAKANA_FALLBACK:
                    katakana_name += KATAKANA_FALLBACK[two_char]
                    i += 2
                    continue
            
            # Try single character
            if i < len(romaji_lower):
                one_char = romaji_lower[i]
                if one_char in KATAKANA_MAP:
                    katakana_name += KATAKANA_MAP[one_char]
                elif one_char in KATAKANA_FALLBACK:
                    katakana_name += KATAKANA_FALLBACK[one_char]
                else:
                    # Last resort: use the character as-is but in uppercase
                    katakana_name += one_char.upper()
                i += 1
        
        return katakana_name

    def _translate_to_japanese(self, text: str) -> str:
        """Translate text to Japanese characters"""
        if not text or not text.strip():
            return ""
        
        text = text.strip()
        
        # Try exact match first
        if text in JAPANESE_FALLBACK:
            return JAPANESE_FALLBACK[text]
        
        # API translation disabled - using hardcoded mappings only
        
        # For names (longer text that looks like a name), use katakana conversion
        if len(text) > 2 and text.replace(' ', '').isalpha():
            return self._convert_name_to_katakana(text)
        
        # Character-by-character fallback
        result = ""
        for char in text:
            result += JAPANESE_FALLBACK.get(char, char)
        return result
    
    def _extract_data(self, name: str, birthday: str) -> Tuple[str, str, str]:
        """Extract x, y, z from user input"""
        x = name[:2].upper()
        
        # Extract day from birthday (y = day)
        try:
            if '/' in birthday:
                month, day = map(int, birthday.split('/')[:2])
            elif '-' in birthday:
                parts = birthday.split('-')
                if len(parts) == 3:
                    day = int(parts[2])  # YYYY-MM-DD format
                else:
                    day = int(parts[1])  # MM-DD format
            else:
                day = 10  # Default fallback
            
            # Format day as 2-digit string (09, 19, etc.)
            y = f"{day:02d}"
        except:
            y = "10"  # Safe fallback
        
        star_sign = self._get_star_sign(birthday)
        z = star_sign[:2].upper()
        return x, y, z
    
    def _create_text_overlay_png(self, text: str, width: int, height: int, filename: str, shift_up: bool = False, use_geishta: bool = False, font_size: int = None, scale_factor: float = 1.0) -> str:
        """Create transparent text overlay as PNG file - EXACT COPY FROM LEAN VERSION"""
        # Create transparent image (RGBA) - modified from lean version for transparency
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))  # Transparent background
        draw = ImageDraw.Draw(img)
        
        # Use provided font size or default to instance font size
        effective_font_size = font_size if font_size is not None else self.font_size

        # Choose the appropriate font with scaled size
        if use_geishta:
            # English text - use Geishta font with scaled size
            font_to_use = self._load_geishta_font(effective_font_size)
        else:
            # Japanese text - use the Japanese font with scaled size
            font_to_use = self._load_japan_ramen_font(effective_font_size)
        
        if font_to_use:
            try:
                # Calculate text bounding box
                bbox = draw.textbbox((0, 0), text, font=font_to_use)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # CRITICAL FIX: Handle invalid bounding box (height=0 issue)
                if text_height <= 0 or text_width <= 0:
                    self.logger.warning(f"⚠️ Invalid textbbox for '{text}': {text_width}x{text_height}, using fallback sizing")
                    # Fallback: estimate size based on font size and character count
                    estimated_char_width = self.font_size * 0.8  # Rough estimate
                    estimated_height = self.font_size * 1.2      # Rough estimate
                    text_width = int(estimated_char_width * len(text))
                    text_height = int(estimated_height)
                    pass  # Removed log(f"📏 Using fallback dimensions: {text_width}x{text_height}")

                x = (width - text_width) // 2
                y = (height - text_height) // 2

                # Apply Y-axis shift if requested (660 pixels up, scaled for resolution)
                if shift_up:
                    scaled_shift = int(660 * scale_factor)
                    y = y - scaled_shift

                # Draw text in bright red with Japanese language support
                if use_geishta:
                    # English text
                    draw.text((x, y), text, fill=(255, 0, 0, 255), font=font_to_use)
                    font_name = "Geishta"
                else:
                    # Japanese text with RAQM layout and language specification
                    draw.text((x, y), text, fill=(255, 0, 0, 255), font=font_to_use, language="ja")
                    font_name = "Japanese"

                # Removed verbose text positioning logs
            except Exception as e:
                self.logger.error(f"❌ Text positioning error for '{text}': {e}")
                # Enhanced fallback with better positioning
                y_pos = height // 4 if height > width else height // 2
                # Apply Y-axis shift if requested (660 pixels up, scaled for resolution)
                if shift_up:
                    scaled_shift = int(660 * scale_factor)
                    y_pos = y_pos - scaled_shift
                draw.text((width // 2 - 100, y_pos - 50), text, fill=(255, 0, 0, 255), font=font_to_use)
                pass  # Removed log(f"⚠️ Used exception fallback positioning for '{text}' at ({width // 2 - 100}, {y_pos - 50})")
        else:
            # EXACT COPY from lean version fallback
            y_pos = height // 4 if height > width else height // 2
            # Apply Y-axis shift if requested (660 pixels up, scaled for resolution)
            if shift_up:
                scaled_shift = int(660 * scale_factor)
                y_pos = y_pos - scaled_shift
            draw.text((width // 2 - 100, y_pos - 50), text, fill=(255, 0, 0, 255))
        
        # Save as PNG file
        img.save(filename, 'PNG')
        # Removed verbose overlay PNG creation logs
        return filename
    
    def _create_text_overlay(self, text: str, width: int, height: int, shift_up: bool = False, use_geishta: bool = False, font_size: int = None, scale_factor: float = 1.0) -> np.ndarray:
        """Create transparent text overlay with red text - using PNG approach"""
        # Create temporary PNG file
        temp_filename = f"temp_overlay_{hash(text)}.png"
        png_file = self._create_text_overlay_png(text, width, height, temp_filename, shift_up, use_geishta, font_size, scale_factor)
        
        # Load the PNG file as numpy array
        img = Image.open(png_file)
        img_array = np.array(img)
        
        # Convert to BGRA for OpenCV
        if img_array.shape[2] == 4:  # RGBA
            return cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGRA)
        else:  # RGB
            return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGRA)
    
    def _overlay_text_on_frame(self, frame: np.ndarray, text_overlay: np.ndarray) -> np.ndarray:
        """Overlay transparent text onto video frame"""
        # Convert frame to BGRA if it's not already
        if frame.shape[2] == 3:
            frame_bgra = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
        else:
            frame_bgra = frame.copy()
        
        # Resize text overlay to match frame size
        text_overlay_resized = cv2.resize(text_overlay, (frame_bgra.shape[1], frame_bgra.shape[0]))
        
        # Alpha blending
        alpha = text_overlay_resized[:, :, 3] / 255.0
        alpha = np.stack([alpha] * 3, axis=2)
        
        # Blend the images
        result = frame_bgra.copy()
        result[:, :, :3] = (1 - alpha) * frame_bgra[:, :, :3] + alpha * text_overlay_resized[:, :, :3]
        
        # Convert back to BGR
        return cv2.cvtColor(result, cv2.COLOR_BGRA2BGR)
    
    def _cleanup_previous_runs(self):
        """Clean up any leftover temporary files from previous runs"""
        try:
            import glob
            leftover_files = glob.glob("temp_overlay_*.png")
            if leftover_files:
                pass  # Removed log(f"🧹 Found {len(leftover_files)} leftover temporary files, cleaning up...")
                for leftover_file in leftover_files:
                    try:
                        os.remove(leftover_file)
                        pass  # Removed log(f"Cleaned up leftover file: {leftover_file}")
                    except Exception as e:
                        self.logger.warning(f"Could not remove leftover file {leftover_file}: {e}")
        except Exception as e:
            self.logger.warning(f"Could not clean up leftover files: {e}")
    
    def process_video(self, input_path: str, output_path: str, name: str, birthday: str) -> bool:
        """Main video processing function with transparent text overlays and audio preservation"""
        temp_audio_path = None
        temp_video_path = None
        
        try:
            # Clean up any leftover files from previous runs
            self._cleanup_previous_runs()
            
            # Extract and translate data
            x, y, z = self._extract_data(name, birthday)
            m, n, o = self._translate_to_japanese(x), self._translate_to_japanese(y), self._translate_to_japanese(z)
            
            # Removed debug logs
            
            # Extract audio first
            temp_audio_path = self._extract_audio(input_path)
            if not temp_audio_path:
                self.logger.warning("⚠️ Audio extraction failed")
            
            # Create temporary video path for processing without audio
            temp_video_path = tempfile.mktemp(suffix='.mp4')
            
            # Open video
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                raise ValueError(f"Could not open video: {input_path}")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps

            # Use half resolution for processing to save memory (75% memory reduction)
            width = original_width // 2
            height = original_height // 2

            self.logger.info(f"🎬 Processing video: {name} ({duration:.1f}s)")

            # Calculate scaled font size based on processing resolution
            # Original font was designed for 1080x1920, scale proportionally
            scale_factor = height / 1920.0  # height ratio for scaling
            scaled_font_size = int(self.font_size * scale_factor)
            # Removed verbose font scaling log

            # Create text overlays for each slot
            japanese_name = self._translate_to_japanese(name)  # Full name in Japanese
            characters = [m, n, o, f"{m} {n} {o}", japanese_name, name]  # ジョ, 十五, タ, ジョ 十五 タ, Japanese name, English name
            text_overlays = []
            for i, char in enumerate(characters):
                shift_up = i >= 4  # Shift up for overlays 5 and 6
                use_geishta = i == 5  # Use Geishta font for overlay 6 (English name)
                overlay = self._create_text_overlay(char, width, height, shift_up, use_geishta, scaled_font_size, scale_factor)
                text_overlays.append(overlay)
                # Removed verbose overlay creation logs
            
            # Setup video writer for temporary video (without audio)
            # Use mp4v for temporary video (will be converted to H.264 by FFmpeg)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                raise ValueError(f"Could not create temporary video: {temp_video_path}")
            
            # Release initial video objects before processing
            cap.release()
            out.release()

            # Process video using FFmpeg optimization
            success = self._process_video_with_ffmpeg_overlays_fixed(input_path, temp_video_path, text_overlays, characters, width, height, original_width, original_height)

            if not success:
                self.logger.error("❌ FFmpeg processing failed")
                return False
            
            # Add audio back to the processed video
            self.logger.info("🎵 Adding audio")
            if temp_audio_path and os.path.exists(temp_audio_path):
                audio_success = self._add_audio_to_video(temp_video_path, temp_audio_path, output_path)
                if not audio_success:
                    self.logger.warning("⚠️ Failed to add audio, copying video without audio")
                    import shutil
                    shutil.copy2(temp_video_path, output_path)
            else:
                pass  # Removed log("⚠️ No audio file available, copying video without audio")
                import shutil
                shutil.copy2(temp_video_path, output_path)
            
            # Clean up temporary files
            self._cleanup_temp_files(characters, temp_audio_path)
            if temp_video_path and os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                    pass  # Removed log(f"Cleaned up temporary video file: {temp_video_path}")
                except Exception as e:
                    self.logger.warning(f"Could not remove temporary video file {temp_video_path}: {e}")
            
            self.logger.info(f"✅ Video completed: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Video processing failed: {e}")
            
            # Cleanup on error
            self._cleanup_temp_files([], temp_audio_path)
            if temp_video_path and os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                except:
                    pass
            
            return False
    
    def _extract_audio(self, input_path: str) -> Optional[str]:
        """Extract audio from video and save to temporary file"""
        # Try FFmpeg first (preferred method)
        if FFMPEG_AVAILABLE:
            return self._extract_audio_ffmpeg(input_path)
        
        # Fallback to MoviePy
        if MOVIEPY_AVAILABLE:
            return self._extract_audio_moviepy(input_path)
        
        self.logger.warning("⚠️ No audio processing tools available, skipping audio extraction")
        return None
    
    def _extract_audio_ffmpeg(self, input_path: str) -> Optional[str]:
        """Extract audio using FFmpeg (preferred method)"""
        try:
            pass  # Removed log(f"Extracting audio with FFmpeg from: {input_path}")
            
            # Create temporary audio file
            temp_audio_path = tempfile.mktemp(suffix='.wav')
            
            # FFmpeg command to extract audio
            cmd = [
                FFMPEG_PATH,
                '-i', input_path,           # Input video
                '-vn',                      # No video
                '-acodec', 'pcm_s16le',     # Audio codec
                '-ar', '44100',             # Sample rate
                '-ac', '2',                 # Stereo
                '-y',                       # Overwrite output file
                temp_audio_path             # Output audio file
            ]
            
            # Removed verbose FFmpeg audio command log
            
            # Run FFmpeg command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # Verify the audio file was created and has content
                if os.path.exists(temp_audio_path) and os.path.getsize(temp_audio_path) > 0:
                    pass  # Removed log(f"Audio extracted")
                    return temp_audio_path
                else:
                    self.logger.warning("⚠️ FFmpeg completed but audio file is empty")
                    return None
            else:
                self.logger.error(f"❌ FFmpeg failed with return code {result.returncode}")
                self.logger.error(f"FFmpeg stderr: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            self.logger.error("❌ FFmpeg audio extraction timed out")
            return None
        except Exception as e:
            self.logger.error(f"❌ FFmpeg audio extraction failed: {e}")
            return None
    
    def _extract_audio_moviepy(self, input_path: str) -> Optional[str]:
        """Extract audio using MoviePy (fallback method)"""
        try:
            pass  # Removed log(f"Extracting audio with MoviePy from: {input_path}")
            # Load video and check for audio
            video_clip = VideoFileClip(input_path)
            
            if video_clip.audio is not None:
                pass  # Removed log("🎵 Audio track found, extracting...")
                # Create temporary audio file
                temp_audio_path = tempfile.mktemp(suffix='.wav')
                
                # Extract audio
                audio_clip = video_clip.audio
                audio_clip.write_audiofile(
                    temp_audio_path, 
                    logger=None,
                    codec='pcm_s16le'  # Ensure compatibility
                )
                
                # Verify the audio file was created and has content
                if os.path.exists(temp_audio_path) and os.path.getsize(temp_audio_path) > 0:
                    pass  # Removed log(f"Audio extracted")
                    audio_clip.close()
                    video_clip.close()
                    return temp_audio_path
                else:
                    self.logger.warning("⚠️ Audio file was created but is empty")
                    audio_clip.close()
                    video_clip.close()
                    return None
            else:
                self.logger.warning("⚠️ No audio track found in video")
                video_clip.close()
                return None
                
        except Exception as e:
            self.logger.error(f"❌ MoviePy audio extraction failed: {e}")
            import traceback
            self.logger.error(f"MoviePy audio extraction traceback: {traceback.format_exc()}")
            return None

    def _process_video_with_ffmpeg_overlays_fixed(self, input_path: str, output_path: str, text_overlays: list, characters: list, width: int, height: int, original_width: int = None, original_height: int = None) -> bool:
        """Process video using FFmpeg overlay filters - 8-10x faster than frame-by-frame"""
        try:
            if not FFMPEG_AVAILABLE:
                self.logger.warning("FFmpeg not available, cannot use fast overlay processing")
                return False

            # Save overlay PNGs to temporary files
            overlay_files = []
            for i, overlay in enumerate(text_overlays):
                temp_overlay = tempfile.mktemp(suffix=f'_overlay_{i}.png')
                success = cv2.imwrite(temp_overlay, overlay)
                if success and os.path.exists(temp_overlay):
                    file_size = os.path.getsize(temp_overlay)
                    # Removed verbose overlay save logs
                    overlay_files.append(temp_overlay)
                else:
                    self.logger.error(f"❌ Failed to save overlay {i+1} to {temp_overlay}")
                    return False

            # Build complex FFmpeg filter with scaling
            filter_complex = self._build_ffmpeg_filter_complex_with_scaling(overlay_files, characters, width, height, original_width or width, original_height or height)
            # Removed verbose FFmpeg filter complex log

            # Build FFmpeg command
            cmd = [
                FFMPEG_PATH, '-y',  # Overwrite output
                '-i', input_path,   # Input video
            ]

            # Add overlay inputs
            for overlay_file in overlay_files:
                cmd.extend(['-i', overlay_file])

            # Add filter complex and output
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[final]',  # Map final output
                '-c:v', 'libx264',  # Video codec
                '-preset', 'ultrafast',   # Fastest encoding
                '-crf', '30',       # Lower quality for speed
                '-threads', '1',    # Single thread to reduce memory usage
                '-tune', 'fastdecode',  # Optimize for speed
                output_path
            ])

            # Removed verbose FFmpeg command logs

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                # Only log FFmpeg errors, not success details
                if result.returncode != 0:
                    self.logger.error(f"❌ FFmpeg failed with return code: {result.returncode}")
                    if result.stderr:
                        self.logger.error(f"FFmpeg stderr: {result.stderr[:500]}")
            except FileNotFoundError as e:
                self.logger.error(f"❌ FFmpeg not found: {e}")
                return False
            except PermissionError as e:
                self.logger.error(f"❌ FFmpeg permission denied: {e}")
                return False
            except subprocess.TimeoutExpired as e:
                self.logger.error(f"❌ FFmpeg timeout after 120 seconds: {e}")
                return False
            except Exception as e:
                self.logger.error(f"❌ FFmpeg subprocess failed: {e}")
                return False

            if result.returncode == 0:
                # Removed verbose FFmpeg success log
                # Verify output file was created
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    pass  # File created successfully
                # Cleanup temporary overlay files
                for overlay_file in overlay_files:
                    try:
                        os.remove(overlay_file)
                    except:
                        pass
                return True
            else:
                self.logger.error(f"❌ FFmpeg overlay failed with return code {result.returncode}")
                self.logger.error(f"FFmpeg stderr: {result.stderr[:1000]}")  # Log first 1000 chars of error
                self.logger.error(f"FFmpeg command was: {' '.join(cmd[:5])}...")  # Log command start
                # Cleanup overlay files even on failure
                for overlay_file in overlay_files:
                    try:
                        os.remove(overlay_file)
                    except:
                        pass
                return False

        except Exception as e:
            self.logger.error(f"FFmpeg overlay processing error: {e}")
            return False

    def _build_ffmpeg_filter_complex(self, overlay_files: list, characters: list, width: int, height: int) -> str:
        """Build FFmpeg filter complex for multiple timed overlays"""
        filter_parts = []
        current_label = "0:v"

        for i, (start_time, end_time) in enumerate(self.overlay_timestamps):
            if i >= len(overlay_files):
                break

            # Create overlay filter with timing
            # Use FFmpeg expressions to center overlays properly
            # (W-w)/2 centers horizontally, (H-h)/2 centers vertically
            # The vertical positioning is handled by the shift_up parameter in overlay creation
            output_label = f"v{i+1}" if i < len(self.overlay_timestamps) - 1 else "final"

            # Center the overlay using FFmpeg's built-in variables
            # W = main video width, w = overlay width
            # H = main video height, h = overlay height
            filter_part = f"[{current_label}][{i+1}:v]overlay=(W-w)/2:(H-h)/2:enable='between(t,{start_time},{end_time})'[{output_label}]"
            filter_parts.append(filter_part)
            current_label = output_label

        return "; ".join(filter_parts)

    def _build_ffmpeg_filter_complex_with_scaling(self, overlay_files: list, characters: list, width: int, height: int, original_width: int, original_height: int) -> str:
        """Build FFmpeg filter complex with memory-efficient scaling: downscale -> overlay -> upscale"""
        filter_parts = []

        # Step 1: Scale input video down to processing resolution (saves 75% memory)
        filter_parts.append(f"[0:v]scale={width}:{height}[scaled_input]")

        current_label = "scaled_input"

        # Step 2: Apply overlays at lower resolution
        for i, (start_time, end_time) in enumerate(self.overlay_timestamps):
            if i >= len(overlay_files):
                break

            output_label = f"v{i+1}" if i < len(self.overlay_timestamps) - 1 else "overlaid"

            # Scale overlay to match processing resolution
            filter_parts.append(f"[{i+1}:v]scale={width}:{height}[overlay_{i}]")

            # Apply overlay with timing
            filter_part = f"[{current_label}][overlay_{i}]overlay=(W-w)/2:(H-h)/2:enable='between(t,{start_time},{end_time})'[{output_label}]"
            filter_parts.append(filter_part)
            current_label = output_label

        # Step 3: Scale final result back to original resolution
        if original_width != width or original_height != height:
            filter_parts.append(f"[{current_label}]scale={original_width}:{original_height}[final]")
        else:
            # If no scaling needed, just rename the final output
            filter_parts.append(f"[{current_label}]copy[final]")

        return "; ".join(filter_parts)

    def _add_audio_to_video(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """Add audio back to processed video"""
        # Try FFmpeg first (preferred method)
        if FFMPEG_AVAILABLE:
            return self._add_audio_ffmpeg(video_path, audio_path, output_path)
        
        # Fallback to MoviePy
        if MOVIEPY_AVAILABLE:
            return self._add_audio_moviepy(video_path, audio_path, output_path)
        
        self.logger.warning("⚠️ No audio processing tools available, copying video without audio")
        import shutil
        shutil.copy2(video_path, output_path)
        return False
    
    def _add_audio_ffmpeg(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """Add audio to video using FFmpeg (preferred method)"""
        try:
            pass  # Removed log(f"Adding audio with FFmpeg to: {output_path}")
            pass  # Removed log(f"🎵 Video: {video_path}")
            pass  # Removed log(f"🎵 Audio: {audio_path}")
            
            # Verify files exist
            if not os.path.exists(video_path):
                self.logger.error(f"❌ Processed video file not found: {video_path}")
                return False
            if not os.path.exists(audio_path):
                self.logger.error(f"❌ Audio file not found: {audio_path}")
                return False
            
            # FFmpeg command to combine video and audio
            cmd = [
                FFMPEG_PATH,
                '-i', video_path,           # Input video (no audio)
                '-i', audio_path,           # Input audio
                '-c:v', 'libx264',          # Use H.264 codec for web compatibility
                '-preset', 'medium',         # Encoding speed vs compression
                '-crf', '23',               # Constant rate factor (quality)
                '-pix_fmt', 'yuv420p',      # Pixel format for compatibility
                '-c:a', 'aac',              # Audio codec
                '-map', '0:v:0',            # Map video from first input
                '-map', '1:a:0',            # Map audio from second input
                '-shortest',                # End when shortest stream ends
                '-y',                       # Overwrite output file
                output_path                 # Output file
            ]
            
            # Removed verbose FFmpeg audio command log
            
            # Run FFmpeg command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # Verify output file was created
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    pass  # Removed log(f"Audio added")
                    return True
                else:
                    self.logger.error("❌ FFmpeg completed but output file is empty")
                    return False
            else:
                self.logger.error(f"❌ FFmpeg failed with return code {result.returncode}")
                self.logger.error(f"FFmpeg stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("❌ FFmpeg audio recombination timed out")
            return False
        except Exception as e:
            self.logger.error(f"❌ FFmpeg audio recombination failed: {e}")
            return False
    
    def _add_audio_moviepy(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """Add audio to video using MoviePy (fallback method)"""
        try:
            pass  # Removed log(f"Adding audio with MoviePy to: {output_path}")
            pass  # Removed log(f"🎵 Loading processed video: {video_path}")
            pass  # Removed log(f"🎵 Loading extracted audio: {audio_path}")
            
            # Verify files exist
            if not os.path.exists(video_path):
                self.logger.error(f"❌ Processed video file not found: {video_path}")
                return False
            if not os.path.exists(audio_path):
                self.logger.error(f"❌ Audio file not found: {audio_path}")
                return False
            
            # Load video and audio
            video_clip = VideoFileClip(video_path)
            audio_clip = VideoFileClip(audio_path).audio
            
            pass  # Removed log(f"🎵 Video duration: {video_clip.duration:.2f}s, Audio duration: {audio_clip.duration:.2f}s")
            
            # Ensure audio matches video duration
            if audio_clip.duration > video_clip.duration:
                pass  # Removed log("🎵 Trimming audio to match video duration")
                audio_clip = audio_clip.subclip(0, video_clip.duration)
            elif audio_clip.duration < video_clip.duration:
                pass  # Removed log("🎵 Audio is shorter than video, will loop if needed")
            
            # Combine video and audio
            final_clip = video_clip.set_audio(audio_clip)
            
            # Write final video with audio
            pass  # Removed log(f"🎵 Writing final video with audio to: {output_path}")
            final_clip.write_videofile(
                output_path, 
                logger=None,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True
            )
            
            # Verify output file was created
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                pass  # Removed log(f"Audio added")
                success = True
            else:
                self.logger.error("❌ Output file was not created or is empty")
                success = False
            
            # Cleanup
            video_clip.close()
            audio_clip.close()
            final_clip.close()
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ MoviePy audio recombination failed: {e}")
            import traceback
            self.logger.error(f"MoviePy audio recombination traceback: {traceback.format_exc()}")
            return False
    
    def _cleanup_temp_files(self, characters: List[str], temp_audio_path: Optional[str] = None):
        """Clean up temporary PNG and audio files"""
        # Clean up PNG files for current characters
        for char in characters:
            temp_filename = f"temp_overlay_{hash(char)}.png"
            try:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                    pass  # Removed log(f"Cleaned up temporary file: {temp_filename}")
            except Exception as e:
                self.logger.warning(f"Could not remove temporary file {temp_filename}: {e}")
        
        # Clean up any leftover temp_overlay PNG files from previous runs
        try:
            import glob
            leftover_files = glob.glob("temp_overlay_*.png")
            for leftover_file in leftover_files:
                try:
                    os.remove(leftover_file)
                    pass  # Removed log(f"Cleaned up leftover temporary file: {leftover_file}")
                except Exception as e:
                    self.logger.warning(f"Could not remove leftover file {leftover_file}: {e}")
        except Exception as e:
            self.logger.warning(f"Could not clean up leftover files: {e}")
        
        # Clean up audio file
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                pass  # Removed log(f"Cleaned up temporary audio file: {temp_audio_path}")
            except Exception as e:
                self.logger.warning(f"Could not remove temporary audio file {temp_audio_path}: {e}")


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process video with transparent Japanese text overlays")
    parser.add_argument("input_video", help="Input MP4 video file")
    parser.add_argument("output_video", help="Output MP4 video file")
    parser.add_argument("--name", required=True, help="User name")
    parser.add_argument("--birthday", required=True, help="Birthday (YYYY-MM-DD, MM/DD/YYYY, or MM-DD)")
    parser.add_argument("--font-size", type=int, default=72, help="Font size")
    
    args = parser.parse_args()
    
    processor = VideoProcessorOverlay(font_size=args.font_size)
    success = processor.process_video(args.input_video, args.output_video, args.name, args.birthday)
    
    if success:
        print("✅ Video processing completed successfully!")
    else:
        print("❌ Video processing failed!")
        exit(1)


if __name__ == "__main__":
    main()
