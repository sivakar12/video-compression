import json
import os
import shutil
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import shlex

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

from PIL import Image, UnidentifiedImageError
try:
    from PIL.ExifTags import TAGS
except ImportError:
    TAGS = {}

def get_metadata_date(file_path: Path) -> Optional[float]:
    """
    Try to extract creation date from file metadata (EXIF for images, FFmpeg for videos).
    Returns timestamp or None.
    """
    ext = file_path.suffix.lower()
    
    # 1. Images (EXIF)
    if ext in {'.jpg', '.jpeg', '.png', '.tiff', '.heic', '.webp'}:
        try:
            with Image.open(file_path) as img:
                exif = img.getexif()
                if exif:
                    # Look for DateTimeOriginal (36867) or DateTime (306)
                    # 36867 = DateTimeOriginal
                    # 36868 = DateTimeDigitized
                    # 306 = DateTime
                    for tag_id in [36867, 36868, 306]:
                        date_str = exif.get(tag_id)
                        if date_str:
                            try:
                                # Format: "YYYY:MM:DD HH:MM:SS"
                                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                                return dt.timestamp()
                            except ValueError:
                                continue
        except (UnidentifiedImageError, OSError, Exception):
            pass

    # 2. Videos (FFmpeg)
    # Using ffprobe to get creation_time tag
    if ext in {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.webm'}:
        try:
            cmd = [
                "ffprobe", "-v", "quiet", 
                "-select_streams", "v:0", 
                "-show_entries", "stream_tags=creation_time:format_tags=creation_time", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            date_str = result.stdout.strip()
            if date_str:
                # FFmpeg returns ISO format usually: 2023-01-01T12:00:00.000000Z
                try:
                    # Handle Z or offset
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    return dt.timestamp()
                except ValueError:
                    pass
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
    
    candidates = [fs_created, fs_modified]
    if meta_date:
        candidates.append(meta_date)
    
    # Use the earliest of all available dates
    earliest = min(candidates)
    
    return {'created': earliest, 'modified': fs_modified, 'fs_created': fs_created, 'metadata': meta_date}

def format_date_for_filename(timestamp: float) -> str:
    """Format timestamp into YYYYMMDD-HHMMSS string."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y%m%d-%H%M%S")

def generate_output_filename(original_path: Path, created_ts: float) -> str:
    """
    Generate new filename: YYYYMMDD-HHMMSS[-0700]_{OriginalName}.mp4
    """
    # Use localized time for filename to include offset if available/relevant
    dt = datetime.fromtimestamp(created_ts).astimezone()
    date_str = dt.strftime("%Y%m%d-%H%M%S%z")
    stem = original_path.stem
    # Replace spaces with underscores or keep as is? User didn't specify, keeping safe.
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
    os.utime(file_path, (datetime.now().timestamp(), modified))
    
    # 2. Try to set birthtime (macOS specific via setfile if available)
    if platform.system() == 'Darwin':
        try:
            # SetFile expects format "MM/DD/YYYY HH:MM:SS"
            # It interprets the string in LOCAL time.
            # We must convert our timestamp to local system string representation.
            dt_local = datetime.fromtimestamp(created)
            date_str = dt_local.strftime("%m/%d/%Y %H:%M:%S")
            
            subprocess.run(
                ["SetFile", "-d", date_str, str(file_path)], 
                check=True, 
                capture_output=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Command failed or SetFile not found (requires Xcode command line tools)
            # Fallback is to do nothing for birthtime, as we already set mtime.
            pass
