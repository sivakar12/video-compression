# Organising Tools User Guide

A collection of CLI tools to help organize, compress, and managing your digital files (videos, images).

## Installation

```bash
pip install -e .
```

The main command is `organising-tools`.

## Commands

### 1. Video Compression
Batch compress and organize video files.

```bash
organising-tools compress /path/to/videos
```

**Options:**
- `--codec [h264|h265]`: Choose video codec.
- `--crf [0-51]`: Constant Rate Factor (Quality). Lower is better. Recommended: 23 (h264), 28 (h265).
- `--preset [fast|medium|slow]`: Compression speed.
- `--hw-accel`: Use hardware acceleration (VideoToolbox on macOS).
- `--no-compress`: Rename and fix timestamps only.

### 2. Image Compression
Optimize images (JPEG/PNG/WebP) without visual quality loss.

```bash
organising-tools compress-image /path/to/images
```

**Features:**
- Preserves EXIF metadata.
- Optimizes file size using best available settings.
- Moves originals to `originals/` folder.

### 3. Date Fixing
Tools to synchronize file timestamps (Created/Modified) with metadata.

**Sync Modified Date:**
Sets the file's "Modified" timestamp to the earliest valid date found (Metadata or Creation time).
```bash
organising-tools fix-modified-dates /path/to/files
```

**Sync Created Date:**
Sets the file's "Created" timestamp (Birthtime) to the earliest valid date found.
```bash
organising-tools fix-created-dates /path/to/files
```

**Add Timestamp to Filename:**
Renames files to include `YYYYMMDD-HHMMSS` prefix based on creation time.
```bash
organising-tools add-timestamp-to-filename /path/to/files
```

### 4. Folder Favorites
Quickly navigate to frequently used directories.

**Add Current Folder:**
```bash
organising-tools add-folder-to-favourites
```

**Go To Favorite:**
Select a favorite folder interactively.
```bash
organising-tools go-to-favourite-folder
```
*Note: To actually change your shell directory, add this alias to your `.zshrc` or `.bashrc`:*
```bash
alias fav='cd "$(organising-tools go-to-favourite-folder --print-only)"'
```
Then use `fav` command.
