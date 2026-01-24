# Video Compressor User Guide

## Usage
Run the tool on a directory containing videos:
```bash
video-compress /path/to/videos
```

## Output Format
Files are always renamed to match their original creation timestamp:

**Format:** `YYYYMMDD-HHMMSS-Offset_OriginalName.mp4`

**Examples:**
- `20240124-143000-0800_Holiday.mp4` (Recorded Jan 24, 2024 at 2:30 PM PST)
- `20231225-090000+0530_Family.mp4` (Recorded Dec 25, 2023 at 9:00 AM IST)

## Settings Explained

### Codec (`--codec`)
Determines the video format.
- **h264**: Standard compatibility. Plays on everything (older TVs, Windows, Mac).
- **h265**: High efficiency. Smaller files (30-50% smaller than h264) but requires modern hardware to play smoothly.

### Quality CRF (`--crf`)
**Constant Rate Factor**. Controls the balance between quality and file size.
- **Range**: 0-51 (Lower is better quality, higher is smaller size).
- **Recommended**: 
  - **23** (Default for h264): Visually lossless.
  - **28** (Default for h265): Good balance for archiving.
  - **18**: Archival quality (very large files).

### Preset (`--preset`)
Controls compression speed vs efficiency.
- **fast**: Quicker processing, slightly larger files.
- **medium**: (Default) Best balance.
- **slow**: Takes longer, produces slightly smaller files.

## Organization Only Mode (`--no-compress`)
Use this flag to **rename and organize only**, without compressing the video.

```bash
video-compress /path/to/videos --no-compress
```

**What it does:**
1. **Renames** file to `YYYYMMDD-HHMMSS-Offset_OriginalName.mp4`.
   - Example: `20240124-163000+0530_MyVideo.mp4`
   - Represents: Year Month Day - Hour Minute Second TimezoneOffset
2. **Updates** "Created" and "Modified" timestamps to match the original recording time.
3. **Does NOT** move the file to an `originals` folder.
