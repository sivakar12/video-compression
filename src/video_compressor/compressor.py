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
    preset: str = "medium",
    progress_callback: Optional[callable] = None
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
        "-pix_fmt", "yuv420p",  # Ensure compatibility with QuickTime/macOS
        "-c:a", "copy",
        "-movflags", "+faststart",
    ]
    
    # If H.265, need to specify tag for compatibility (must be before output path)
    if codec == "libx265":
         cmd.extend(["-vtag", "hvc1"])

    cmd.append(str(output_path))

    try:
        # Run ffmpeg with Popen to capture output in real-time
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Read stderr line by line
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            
            if line and progress_callback:
                progress_callback(line)

        if process.returncode != 0:
            print(f"Error compressing {input_path.name}:")
            # process.stderr is already consumed, so we might not have the full error log easily available 
            # unless we stored it or the user saw it via callback. 
            # For simplicity, we assume the callback (if any) or existing console handled visibility, 
            # but we can print a generic error or return False.
            return False
            
        return True

        
    except Exception as e:
        print(f"Exception during compression: {e}")
        return False
