import json
import os
import shutil
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

STATE_FILE_NAME = ".compression_state.json"

def get_file_dates(file_path: Path) -> Dict[str, float]:
    """
    Get created (birthtime) and modified times of a file.
    On macOS, explicitly tries to get creation time.
    """
    stat = file_path.stat()
    created = stat.st_ctime
    modified = stat.st_mtime
    
    # On Mac/BSD/Windows, st_birthtime might be available for creation time
    # On Linux st_birthtime is often not available, falls back to st_ctime (metadata change)
    if hasattr(stat, 'st_birthtime'):
        created = stat.st_birthtime
    
    return {'created': created, 'modified': modified}

def format_date_for_filename(timestamp: float) -> str:
    """Format timestamp into YYYYMMDD-HHMMSS string."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y%m%d-%H%M%S")

def generate_output_filename(original_path: Path, created_ts: float) -> str:
    """
    Generate new filename: YYYYMMDD-HHMMSS_{OriginalName}.mp4
    """
    date_str = format_date_for_filename(created_ts)
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
    
    # 2. Try to set birthtime (macOS specific via setfile if available or simple utime fallback)
    # Python doesn't have a cross-platform way to set birthtime easily.
    # We will mainly rely on mtime which is the most visible "Date Modified".
    
    # On macOS we can try 'SetFile' if available, but os.utime handles 'Modified'.
    # For 'Created', it's harder to spoof without calling system APIs.
    # However, copying a file usually resets creation time to now.
    pass
