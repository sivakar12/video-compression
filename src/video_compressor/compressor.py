import subprocess
import shutil
import sys
from pathlib import Path
from typing import Optional

def check_ffmpeg():
    """Check if ffmpeg is installed and accessible."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not in PATH. Please install it (e.g., 'brew install ffmpeg').")

def compress_video(
    input_path: Path, 
    output_path: Path, 
    codec: str = "libx264", 
    crf: int = 23, 
    preset: str = "medium"
) -> bool:
    """
    Compress video using ffmpeg.
    
    Args:
        input_path: Source video file
        output_path: Destination file
        codec: 'libx264' (default) or 'libx265'
        crf: Constant Rate Factor (18-28 is good range, lower is better quality)
        preset: Encoding speed (faster = larger file/worse quality for same bitrat)
    
    Returns:
        True if successful, False otherwise.
    """
    # Base command
    # -i input
    # -c:v codec -crf X -preset Y
    # -c:a copy (copy audio without re-encoding to save quality/time)
    # -movflags +faststart (optimizes for web/streaming)
    # -y (overwrite output if exists, though our logic handles this outside)
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-c:v", codec,
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    # If H.265, sometimes need to specify tag for compatibility
    if codec == "libx265":
         cmd.extend(["-vtag", "hvc1"])

    try:
        # Run ffmpeg. Capture output to avoid spamming terminal unless error
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        if result.returncode != 0:
            print(f"Error compressing {input_path.name}:")
            print(result.stderr)
            return False
            
        return True
        
    except Exception as e:
        print(f"Exception during compression: {e}")
        return False
