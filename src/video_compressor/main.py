import click
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from . import utils, compressor

console = Console()

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.webm'}

@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--codec', type=click.Choice(['h264', 'h265']), help='Video codec to use')
@click.option('--crf', type=int, help='Constant Rate Factor (Quality). Lower is better. 18-28 recommended.')
@click.option('--preset', type=click.Choice(['fast', 'medium', 'slow']), default='medium', help='Compression speed preset')
def cli(directory, codec, crf, preset):
    """
    Batch compress videos in DIRECTORY.
    
    Preserves metadata and organizes original files.
    """
    base_dir = Path(directory)
    
    # 0. Check dependencies
    try:
        compressor.check_ffmpeg()
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    console.rule("[bold blue]Video Compressor Tool[/bold blue]")
    
    # 1. Interactive Prompts if options not provided
    if not codec:
        choice = Prompt.ask(
            "Choose Codec", 
            choices=["h264", "h265"], 
            default="h264"
        )
        codec = choice

    if not crf:
        default_crf = 23 if codec == 'h264' else 28 # h265 can tolerate higher CRF for same quality
        crf = IntPrompt.ask(
            "Choose Quality (CRF)", 
            default=default_crf
        )
        
    ffmpeg_codec = "libx264" if codec == "h264" else "libx265"
    
    console.print(f"\n[green]Settings:[/green] Codec=[bold]{ffmpeg_codec}[/bold], CRF=[bold]{crf}[/bold], Preset=[bold]{preset}[/bold]\n")

    # 2. Scan Files
    files = [f for f in base_dir.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS]
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
            
            # Compress
            success = compressor.compress_video(
                video_file, 
                output_path, 
                codec=ffmpeg_codec, 
                crf=crf, 
                preset=preset
            )
            
            if success:
                # Apply Dates
                utils.apply_dates_to_file(output_path, dates['created'], dates['modified'])
                
                # Move Original
                try:
                    utils.move_original(video_file, originals_dir)
                    utils.update_file_state(base_dir, video_file.name, 'done')
                except Exception as e:
                    console.print(f"[red]Error moving file {video_file.name}: {e}[/red]")
                    utils.update_file_state(base_dir, video_file.name, 'done_move_failed', str(e))
            else:
                utils.update_file_state(base_dir, video_file.name, 'failed')
                console.print(f"[red]Failed to compress {video_file.name}[/red]")
            
            progress.advance(main_task)
            
    console.print("\n[bold green]Processing Complete![/bold green]")
