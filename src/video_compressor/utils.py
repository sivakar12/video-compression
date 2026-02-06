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

def get_file_dates(file_path: Path) -> Dict[str, float]:
    """
    Get created (birthtime) and modified times of a file.
    Returns the earliest of both as the 'created' timestamp.
    On macOS, explicitly tries to get creation time.
    """
    stat = file_path.stat()
    created = stat.st_ctime
    modified = stat.st_mtime
    
    # On Mac/BSD/Windows, st_birthtime might be available for creation time
    # On Linux st_birthtime is often not available, falls back to st_ctime (metadata change)
    if hasattr(stat, 'st_birthtime'):
        created = stat.st_birthtime
    
    # Use the earliest of creation and modification time
    earliest = min(created, modified)
    
    return {'created': earliest, 'modified': modified}

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
    return f"{date_str}_{clean_stem}.mp4"

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
