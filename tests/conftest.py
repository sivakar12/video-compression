import pytest
import subprocess
from pathlib import Path
import os
import time
import sys
import datetime

@pytest.fixture
def dummy_files_dir(tmp_path):
    """Creates a temporary directory with dummy files for testing."""
    # Use deterministic older timestamps so rename logic triggers reliably
    # but don't hardcode a specific date as requested
    old_time = time.time() - 3600
    
    # Create a dummy image for general rename testing
    img_path = tmp_path / "TEST_IMG_001.JPG"
    img_path.write_text("dummy image content")
    os.utime(img_path, (old_time, old_time))
    
    # Generate a tiny 1-second real video using ffmpeg so the compressor doesn't fail on invalid data
    vid_path = tmp_path / "TEST_VID_002.mp4"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=128x128:d=1", 
            "-vcodec", "libx264", "-t", "1", str(vid_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        os.utime(vid_path, (old_time - 7200, old_time - 7200))
    except Exception as e:
        print(f"Warning: could not generate valid test video using ffmpeg: {e}", file=sys.stderr)
        # Create a dummy file anyway for pure metadata tests
        vid_path.write_text("fake video content")
        os.utime(vid_path, (old_time - 7200, old_time - 7200))

    yield tmp_path
    
    # Pytest's tmp_path fixture is automatically deleted post-session,
    # ensuring complete cleanup of everything inside.
