import json
import os
import shutil
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import shlex
import exifread

STATE_FILE_NAME = ".compression_state.json"

def parse_duration_to_seconds(time_str: str) -> float:
    """
    Parse FFmpeg duration string (HH:MM:SS.mm) to seconds.
    Example: '00:05:20.45' -> 320.45
    """
    try:
        if not time_str:
            return 0.0
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except ValueError:
        return 0.0

def format_size(size_in_bytes: float) -> str:
    """Format size in bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} PB"

from PIL import Image, UnidentifiedImageError

def get_metadata_date(file_path: Path) -> Optional[float]:
    """
    Try to extract creation date from file metadata (EXIF for images, FFmpeg for videos).
    Returns timestamp or None.
    """
    ext = file_path.suffix.lower()
    
    # 1. Images (EXIF) — using exifread for robust support across
    #    JPEG, PNG, WebP, HEIC, TIFF, and RAW formats.
    image_exts = {
        '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.heic', '.heif', '.webp',
        # RAW formats
        '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2', '.raf', '.srw',
    }
    if ext in image_exts:
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, stop_tag='DateTimeDigitized', details=False)
            
            # Try tags in priority order: camera date > digitized date > general date
            for tag_name in ['EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime']:
                tag_val = tags.get(tag_name)
                if tag_val:
                    try:
                        dt = datetime.strptime(str(tag_val), "%Y:%m:%d %H:%M:%S")
                        return dt.timestamp()
                    except ValueError:
                        continue
        except Exception:
            pass

    # 2. Videos (FFmpeg)
    # Using ffprobe to get creation_time and apple-specific creationdate
    if ext in {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.webm'}:
        try:
            cmd = [
                "ffprobe", "-v", "quiet", 
                "-show_entries", "format_tags=creation_time,com.apple.quicktime.creationdate:stream_tags=creation_time", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            # ffprobe might return multiple lines if both tags exist
            date_lines = result.stdout.strip().split('\n')
            timestamps = []
            
            for date_str in date_lines:
                date_str = date_str.strip()
                if not date_str: continue
                
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    timestamps.append(dt.timestamp())
                except ValueError:
                    continue
            
            if timestamps:
                return min(timestamps)
        except Exception:
            pass
            
    return None

def get_file_dates(file_path: Path) -> Dict[str, float]:
    """
    Get created (birthtime) and modified times of a file.
    Also checks metadata content for earliest date.
    Returns dictionary with 'created' being the absolute earliest found.
    """
    stat = file_path.stat()
    fs_created = stat.st_ctime
    fs_modified = stat.st_mtime
    
    # On Mac/BSD/Windows, st_birthtime might be available for creation time
    if hasattr(stat, 'st_birthtime'):
        fs_created = stat.st_birthtime
    
    # Check metadata
    meta_date = get_metadata_date(file_path)
    
    # For images with camera EXIF data, the camera date is the authoritative source.
    # Filesystem dates can be wrong due to copying, syncing, etc.
    ext = file_path.suffix.lower()
    image_extensions = {
        '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.heic', '.heif', '.webp',
        '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2', '.raf', '.srw',
    }
    
    if ext in image_extensions and meta_date is not None:
        earliest = meta_date
    else:
        candidates = [fs_created, fs_modified]
        if meta_date:
            candidates.append(meta_date)
        earliest = min(candidates)
    
    return {'created': earliest, 'modified': fs_modified, 'fs_created': fs_created, 'metadata': meta_date}

def format_date_for_filename(timestamp: float) -> str:
    """Format timestamp into YYYYMMDD-HHMMSS string."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y%m%d-%H%M%S")

def parse_timezone_offset(tz_str: str) -> timezone:
    """
    Parse a shorthand timezone offset string into a timezone object.
    Examples:
        '+2'   -> UTC+02:00
        '+530' -> UTC+05:30
        '-4'   -> UTC-04:00
        '+0'   -> UTC+00:00
        '-930' -> UTC-09:30
    """
    tz_str = tz_str.strip()
    if not tz_str:
        raise ValueError("Empty timezone string")
    
    # Determine sign
    if tz_str[0] == '+':
        sign = 1
        num_part = tz_str[1:]
    elif tz_str[0] == '-':
        sign = -1
        num_part = tz_str[1:]
    else:
        raise ValueError(f"Timezone must start with '+' or '-', got: {tz_str}")
    
    if not num_part or not num_part.isdigit():
        raise ValueError(f"Invalid timezone offset: {tz_str}")
    
    # 1-2 digits = hours only, 3-4 digits = hours + minutes
    if len(num_part) <= 2:
        hours = int(num_part)
        minutes = 0
    elif len(num_part) <= 4:
        minutes = int(num_part[-2:])
        hours = int(num_part[:-2])
    else:
        raise ValueError(f"Timezone offset too long: {tz_str}")
    
    if hours > 14 or minutes >= 60:
        raise ValueError(f"Timezone offset out of range: {tz_str}")
    
    total_minutes = sign * (hours * 60 + minutes)
    return timezone(timedelta(minutes=total_minutes))


def generate_output_filename(original_path: Path, created_ts: float, tz=None) -> str:
    """
    Generate new filename: YYYYMMDD-HHMMSS+0530_{OriginalName}.ext
    
    If tz is provided (a timezone object), the timestamp is displayed in that timezone.
    Otherwise, the system local timezone is used.
    """
    dt = datetime.fromtimestamp(created_ts, tz=timezone.utc)
    if tz is not None:
        dt = dt.astimezone(tz)
    else:
        dt = dt.astimezone()  # system local
    date_str = dt.strftime("%Y%m%d-%H%M%S%z")
    stem = original_path.stem
    clean_stem = stem.replace(" ", "_")
    suffix = original_path.suffix
    return f"{date_str}_{clean_stem}{suffix}"

def load_state(directory: Path) -> Dict[str, Any]:
    """Load processing state from the directory."""
    state_path = directory / STATE_FILE_NAME
    if state_path.exists():
        try:
            with open(state_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}

def save_state(directory: Path, state: Dict[str, Any]):
    """Save processing state."""
    state_path = directory / STATE_FILE_NAME
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

def update_file_state(directory: Path, filename: str, status: str, error: str = None):
    """Update state for a single file."""
    state = load_state(directory)
    if 'files' not in state:
        state['files'] = {}
    
    entry = {
        'status': status,
        'timestamp': datetime.now().isoformat()
    }
    if error:
        entry['error'] = error
        
    state['files'][filename] = entry
    save_state(directory, state)

def move_original(file_path: Path, target_dir: Path):
    """Move original file to the target_dir."""
    target_dir.mkdir(exist_ok=True)
    shutil.move(str(file_path), str(target_dir / file_path.name))

def apply_dates_to_file(file_path: Path, created: float, modified: float):
    """
    Apply original creation and modification dates to the new file.
    """
    # 1. Set atime and mtime
    # Use original modification time for mtime. access time can be 'now'
    os.utime(str(file_path), (datetime.now().timestamp(), modified))
    
    # 2. Try to set birthtime (macOS specific via SetFile if available)
    if platform.system() == 'Darwin' and shutil.which("SetFile"):
        try:
            # SetFile expects format "MM/DD/YYYY HH:MM:SS"
            dt_local = datetime.fromtimestamp(created)
            date_str = dt_local.strftime("%m/%d/%Y %H:%M:%S")
            
            result = subprocess.run(
                ["SetFile", "-d", date_str, str(file_path)], 
                check=True, 
                capture_output=True,
                text=True
            )
            
            # Also set the modification date in SetFile to be sure Finder sees it
            subprocess.run(
                ["SetFile", "-m", date_str, str(file_path)], 
                check=True, 
                capture_output=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

def copy_metadata_tags(source_path: Path, target_path: Path):
    """
    Attempt to copy all metadata tags using exiftool if available.
    This is the gold standard for preserving GPS, camera info, etc.
    """
    if shutil.which("exiftool"):
        try:
            subprocess.run([
                "exiftool", 
                "-tagsFromFile", str(source_path), 
                "-all:all", 
                "-overwrite_original", 
                str(target_path)
            ], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    return False
