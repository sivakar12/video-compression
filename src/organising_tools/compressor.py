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
    hw_accel: bool = False,
    progress_callback: Optional[callable] = None
) -> bool:
    """
    Compress video using ffmpeg.
    
    Args:
        input_path: Source video file
        output_path: Destination file
        codec: 'libx264'/'libx265' (software) OR 'h264'/'h265' (abstract, triggers conversion if hw_accel=True)
        crf: Constant Rate Factor (software) or base for Quality conversion (hardware)
        preset: Encoding speed (software only)
        hw_accel: Use VideoToolbox hardware acceleration if available
    
    Returns:
        True if successful, False otherwise.
    """
    # Determine Codec and Quality Settings
    ffmpeg_codec = codec
    ffmpeg_args = []

    if hw_accel:
        # Hardware Acceleration (VideoToolbox)
        if "h265" in codec or "hevc" in codec or "libx265" in codec:
            ffmpeg_codec = "hevc_videotoolbox"
            tag = "hvc1"
        else: # Default to h264
            ffmpeg_codec = "h264_videotoolbox"
            tag = None

        # Map CRF to VideoToolbox Quality (0-100)
        # CRF 23 (approx default) -> ~65
        # Formula: 100 - (crf * 1.5)
        # 18 -> 73 (High Qual)
        # 23 -> 65.5 (Medium)
        # 28 -> 58 (Lower Qual)
        quality_score = max(1, min(100, int(100 - (crf * 1.5))))
        
        ffmpeg_args.extend([
            "-c:v", ffmpeg_codec,
            "-q:v", str(quality_score)
             # Note: VideoToolbox doesn't use -preset typically, or uses -realtime
             # We rely on -q:v for quality/size tradeoff
        ])
        
        if tag:
             ffmpeg_args.extend(["-vtag", tag])

    else:
        # Software Encoding (CPU)
        # Normalize input codec string if needed
        if "h265" in codec or "hevc" in codec:
             ffmpeg_codec = "libx265"
             tag = "hvc1"
        elif "h264" in codec:
             ffmpeg_codec = "libx264"
             tag = None
        else:
             ffmpeg_codec = codec # Assume it's already a valid ffmpeg codec name like libx264
             tag = None # Unknown
             if codec == "libx265": tag = "hvc1"

        ffmpeg_args.extend([
            "-c:v", ffmpeg_codec,
            "-crf", str(crf),
            "-preset", preset
        ])
        
        if tag and ffmpeg_codec == "libx265":
             ffmpeg_args.extend(["-vtag", tag])

    # Base command construction
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path)
    ]
    
    cmd.extend(ffmpeg_args)
    
    cmd.extend([
        "-map_metadata", "0",
        "-pix_fmt", "yuv420p",  # Compatibility
        "-c:a", "copy",
        "-movflags", "+faststart+use_metadata_tags",
        str(output_path)
    ])

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
            # We can't print stderr here easily as it was consumed. 
            # Ideally we'd log it or accumulate last few lines.
            return False
            
        return True

    except Exception as e:
        print(f"Exception during compression: {e}")
        return False
