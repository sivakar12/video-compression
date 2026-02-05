import click
import sys
import time
import re
import platform
from datetime import timedelta
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import questionary

from . import utils, compressor

console = Console()

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.webm'}

@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--codec', type=click.Choice(['h264', 'h265']), help='Video codec to use')
@click.option('--crf', type=int, help='Constant Rate Factor (Quality). Lower is better. 18-28 recommended.')
@click.option('--preset', type=click.Choice(['fast', 'medium', 'slow']), default='medium', help='Compression speed preset')
@click.option('--hw-accel/--no-hw-accel', default=None, help='Use Hardware Acceleration (VideoToolbox) if available')
@click.option('--no-compress', is_flag=True, help='Rename and update timestamps ONLY. No compression. Files are NOT moved to originals.')
def cli(directory, codec, crf, preset, hw_accel, no_compress):
    """
    Batch compress videos in DIRECTORY.
    
    Preserves metadata and organizes original files.
    """
    base_dir = Path(directory)
    
    # 0. Check dependencies
    if not no_compress:
        try:
            compressor.check_ffmpeg()
        except RuntimeError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(1)

    console.rule("[bold blue]Video Compressor Tool[/bold blue]")
    
    # 1. Interactive Prompts if options not provided
    if not no_compress and not codec:
        codec = questionary.select(
            "Video Codec:",
            choices=["h264", "h265"],
            default="h264",
            qmark="?"
        ).ask()
        
        if not codec: # Handle cancellation
             sys.exit(0)

    if not no_compress and not crf:
        default_crf = 23 if codec == 'h264' else 28
        
        crf_str = questionary.text(
            "Quality (CRF):",
            default=str(default_crf),
            validate=lambda text: text.isdigit() and 0 <= int(text) <= 51 or "Please enter a valid CRF (0-51)",
            qmark="?"
        ).ask()
        
        if not crf_str:
             sys.exit(0)
        crf = int(crf_str)

    # Determine HW Accel if not specified (Interactive or Default)
    if not no_compress and hw_accel is None:
        is_macos = platform.system() == 'Darwin'
        if is_macos:
             hw_accel = questionary.confirm(
                 "Use Hardware Acceleration (VideoToolbox)?",
                 default=True,
                 qmark="?",
                 auto_enter=False,
             ).ask()
        else:
             hw_accel = False

    ffmpeg_codec_display = "libx264"
    if not no_compress:
        if hw_accel:
             base = "h265" if codec == "h265" else "h264"
             ffmpeg_codec_display = f"{base}_videotoolbox (HW)"
             quality_display = f"Quality ~{int(100 - (crf * 1.5))}"
        else:
             ffmpeg_codec_display = "libx265" if codec == "h265" else "libx264"
             quality_display = f"CRF {crf}"
             
        console.print(f"\n[green]Settings:[/green] Codec=[bold]{ffmpeg_codec_display}[/bold], Quality=[bold]{quality_display}[/bold], Preset=[bold]{preset}[/bold]\n")
    else:
        console.print(f"\n[green]Mode:[/green] [bold]NO COMPRESSION[/bold] (Rename & Timestamp only)\n")

    # 2. Scan Files
    files = [
        f for f in base_dir.iterdir() 
        if f.suffix.lower() in VIDEO_EXTENSIONS and not f.name.startswith('.')
    ]

    # Filter out files that appear to be generated outputs
    # Logic: If a file looks like "Timestamp_Name.mp4" AND "Name.mp4" exists in "originals", skip it.
    originals_dir = base_dir / "originals"
    processed_stems = set()
    if originals_dir.exists():
        for orig in originals_dir.iterdir():
            if not orig.name.startswith('.'):
                # We need to match the clean stem logic from utils.py
                processed_stems.add(orig.stem.replace(" ", "_"))

    valid_files = []
    for f in files:
        # Check if file matches generated pattern: YYYYMMDD-HHMMSS..._Stem
        match = re.match(r"^\d{8}-\d{6}.*?_(.+)$", f.stem)
        is_generated = False
        if match:
             potential_stem = match.group(1)
             if potential_stem in processed_stems:
                 is_generated = True
        
        if not is_generated:
            valid_files.append(f)
    
    files = valid_files

    if not files:
        console.print("[yellow]No video files found in directory.[/yellow]")
        return

    # 3. Load State
    state = utils.load_state(base_dir)
    processed_files = state.get('files', {})
    
    files_to_process = []
    skipped_count = 0
    
    for f in files:
        if f.name in processed_files and processed_files[f.name]['status'] == 'done':
            skipped_count += 1
        else:
            files_to_process.append(f)
            
    if skipped_count > 0:
        console.print(f"[dim]Skipping {skipped_count} already processed files.[/dim]")
    
    if not files_to_process:
        console.print("[green]All files already processed![/green]")
        return
        
    if not Confirm.ask(f"Ready to process {len(files_to_process)} files?"):
        console.print("Aborted.")
        return

    # 4. Processing Loop
    originals_dir = base_dir / "originals"
    start_time = time.time()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        main_task = progress.add_task("[cyan]Batch Processing...", total=len(files_to_process))
        
        for video_file in files_to_process:
            progress.update(main_task, description=f"Processing {video_file.name}")
            
            # Update state to processing
            utils.update_file_state(base_dir, video_file.name, 'processing')
            
            # Get Dates
            dates = utils.get_file_dates(video_file)
            new_filename = utils.generate_output_filename(video_file, dates['created'])
            output_path = base_dir / new_filename
            
            if no_compress:
                try:
                    progress.update(main_task, description=f"Renaming {video_file.name}")
                    
                    if output_path.exists():
                        # Handle collision or skip?
                        # If renamed file exists, maybe we already renamed it?
                        console.print(f"[yellow]Target exists, skipping rename: {new_filename}[/yellow]")
                        utils.update_file_state(base_dir, video_file.name, 'skipped_exists')
                        progress.advance(main_task)
                        continue

                    # Rename
                    video_file.rename(output_path)
                    
                    # Apply Dates
                    try:
                        utils.apply_dates_to_file(output_path, dates['created'], dates['created'])
                    except Exception as e:
                         console.print(f"[yellow]Warning: Could not set dates for {new_filename}: {e}[/yellow]")

                    # Update state
                    # Mark original name as done (so we don't process it if it somehow reappears or we track history)
                    # AND Mark new name as done (so we don't re-rename it on next run)
                    utils.update_file_state(base_dir, video_file.name, 'renamed')
                    utils.update_file_state(base_dir, new_filename, 'done')
                    
                    console.print(f"[dim]Renamed: {video_file.name} -> {new_filename}[/dim]")

                except Exception as e:
                    console.print(f"[red]Error renaming {video_file.name}: {e}[/red]")
                    utils.update_file_state(base_dir, video_file.name, 'error_renaming', str(e))
                
                progress.advance(main_task)
                continue

            # Compress
            video_duration = 0.0
            process_start_time = time.time()
            
            try:
                def update_ffmpeg_progress(line):
                    nonlocal video_duration
                    # Parse Duration if seen (usually at start)
                    # Duration: 00:00:30.04, start: 0.000000, bitrate: 10453 kb/s
                    if "Duration:" in line and video_duration == 0.0:
                        dur_match = re.search(r"Duration:\s+(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                        if dur_match:
                            video_duration = utils.parse_duration_to_seconds(dur_match.group(1))

                    # Parse interesting metrics from ffmpeg output
                    # Example: frame=219 fps=0.0 q=-1.0 Lsize=1903kB time=00:00:07.82 bitrate=1991.6kbits/s speed=14.1x
                    time_match = re.search(r"time=(\S+)", line)
                    speed_match = re.search(r"speed=(\S+)", line)
                    
                    details = []
                    if time_match:
                        details.append(f"time={time_match.group(1)}")
                    if speed_match:
                        details.append(f"speed={speed_match.group(1)}")
                        
                    if details:
                        progress.update(main_task, description=f"Processing {video_file.name} [{' '.join(details)}]")

                success = compressor.compress_video(
                    video_file, 
                    output_path, 
                    codec=codec, # Pass abstract codec directly, compressor handles mapping
                    crf=crf, 
                    preset=preset,
                    hw_accel=bool(hw_accel),
                    progress_callback=update_ffmpeg_progress
                )
                
                if success:
                    # Calculate Stats
                    process_time = time.time() - process_start_time
                    stats_msg = f"[dim]Completed in {str(timedelta(seconds=int(process_time)))}[/dim]"
                    
                    if video_duration > 0:
                        # Efficiency: Time (seconds) to compress 1 minute of video
                        # (process_time / video_duration_mins)
                        video_minutes = video_duration / 60.0
                        if video_minutes > 0:
                            s_per_min = process_time / video_minutes
                            speed_factor = video_duration / process_time if process_time > 0 else 0
                            
                            stats_msg += f"\n  [dim]• Efficiency: {s_per_min:.1f}s / min of video[/dim]"
                            stats_msg += f"\n  [dim]• Speed: {speed_factor:.1f}x[/dim]"
                    
                    console.print(stats_msg)

                    # Apply Dates
                    try:
                        # Use created time for both creation and modification time
                        utils.apply_dates_to_file(output_path, dates['created'], dates['created'])
                    except Exception as e:
                        console.print(f"[red]Error applying dates to {new_filename}: {e}[/red]")
                        console.print("[yellow]Rolling back...[/yellow]")
                        if output_path.exists():
                            output_path.unlink()
                        utils.update_file_state(base_dir, video_file.name, 'failed_metadata', str(e))
                        continue

                    # Move Original
                    try:
                        utils.move_original(video_file, originals_dir)
                        utils.update_file_state(base_dir, video_file.name, 'done')
                    except Exception as e:
                        console.print(f"[red]Error moving original {video_file.name}: {e}[/red]")
                        console.print("[yellow]Rolling back... (Deleting compressed file)[/yellow]")
                        if output_path.exists():
                            output_path.unlink()
                        # If original was moved partially? Unlikely with shutil.move but generally it's atomic-ish on same FS.
                        # If it failed, original should be intact at source or we are in trouble.
                        # We assume original is still at source if move failed.
                        utils.update_file_state(base_dir, video_file.name, 'failed_move', str(e))
                else:
                    utils.update_file_state(base_dir, video_file.name, 'failed_compression')
                    console.print(f"[red]Failed to compress {video_file.name}[/red]")
                    if output_path.exists():
                        output_path.unlink()

            except Exception as e:
                console.print(f"[red]Unexpected error processing {video_file.name}: {e}[/red]")
                if output_path.exists():
                    try:
                        output_path.unlink()
                    except:
                        pass
                utils.update_file_state(base_dir, video_file.name, 'error', str(e))
            
            progress.advance(main_task)
            
    elapsed_time = time.time() - start_time
    console.print("\n[bold green]Processing Complete![/bold green]")
    console.print(f"[dim]Total time: {str(timedelta(seconds=int(elapsed_time)))}[/dim]")
