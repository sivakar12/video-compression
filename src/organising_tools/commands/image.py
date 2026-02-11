import click
import shutil
import time
from pathlib import Path
from datetime import timedelta
from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm
from .. import utils

console = Console()

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'} # Add heic support later if needed (requires pillow-heif)

@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--quality', type=int, default=85, help="Quality for JPEG/WebP (1-100). Default 85.")
@click.option('--dry-run', is_flag=True, help="Simulate compression without changes.")
def compress_image(directory, quality, dry_run):
    """
    Compresses images in the directory.
    Moves originals to 'originals/' folder. Preserves metadata/dates.
    """
    base_dir = Path(directory)
    originals_dir = base_dir / "originals"
    
    files = [
        f for f in base_dir.iterdir() 
        if f.suffix.lower() in IMAGE_EXTENSIONS and not f.name.startswith('.')
    ]
    
    if not files:
        console.print("[yellow]No supported images found.[/yellow]")
        return
        
    console.print(f"[bold blue]Found {len(files)} images to compress.[/bold blue]")
    
    if dry_run:
        console.print("[yellow]Dry run. No changes will be made.[/yellow]")
        return

    if not Confirm.ask(f"Process {len(files)} images?"):
        console.print("Aborted.")
        return

    originals_dir.mkdir(exist_ok=True)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Compressing images...", total=len(files))
        
        success_count = 0
        saved_size = 0
        
        for img_path in files:
            progress.update(task, description=f"Processing {img_path.name}")
            
            try:
                original_size = img_path.stat().st_size
                dates = utils.get_file_dates(img_path)
                
                # We want to compress in-place (or rather, replace).
                # But to be safe, we move original FIRST or write to temp then move original?
                # Safer: Move original to originals/ first (copy), then overwrite source.
                # Actually, standard flow in video-compress was: write new file, then move original.
                # Here we are "replacing".
                # Let's write to a temp file first.
                
                temp_path = base_dir / f".tmp_{img_path.name}"
                
                with Image.open(img_path) as img:
                    # Preserve EXIF
                    exif_data = img.getexif()
                    kwargs = {'optimize': True}
                    
                    if img.format == 'JPEG':
                         kwargs['quality'] = quality
                         if exif_data:
                             kwargs['exif'] = exif_data
                    elif img.format == 'PNG':
                         kwargs['optimize'] = True
                         # PNG metadata preservation in Pillow is tricky with 'exif' param, 
                         # usually handles it via info dictionary but optimize might strip chunks.
                         # explicit exif param works for some formats.
                         if 'exif' in img.info:
                             kwargs['exif'] = img.info['exif']
                    elif img.format == 'WEBP':
                         kwargs['quality'] = quality
                         if 'exif' in img.info:
                             kwargs['exif'] = img.info['exif']
                    
                    img.save(temp_path, **kwargs)
                
                new_size = temp_path.stat().st_size
                
                # Check if compression actually happened
                if new_size >= original_size:
                    # If new file is bigger or same, discard it and keep original?
                    # Or keep it if user wants "uniformity"?
                    # Usually we only want to keep if smaller.
                    # But if we want to "organise", maybe we keep it?
                    # The prompt says "If possible compress. No loss in quality."
                    # If it grows, we should probably skip replacing.
                    temp_path.unlink()
                    progress.console.print(f"[dim]Skipped {img_path.name}: No size reduction ({original_size} -> {new_size})[/dim]")
                    # Move original? No, we didn't compress.
                    progress.advance(task)
                    continue
                
                saved_size += (original_size - new_size)
                
                # Apply Dates to New File
                utils.apply_dates_to_file(temp_path, dates['created'], dates['created'])
                
                # Move Original (Copy first to ensure safety, then delete source if needed, or just move)
                # utils.move_original performs a shutil.move.
                # But we are overwriting `img_path`.
                # So we should move `img_path` to `originals/`.
                utils.move_original(img_path, originals_dir)
                
                # Rename temp to original name
                temp_path.rename(img_path)
                
                success_count += 1
                
            except Exception as e:
                console.print(f"[red]Error processing {img_path.name}: {e}[/red]")
                if temp_path.exists():
                    temp_path.unlink()
            
            progress.advance(task)
            
    mb_saved = saved_size / (1024 * 1024)
    console.print(f"[green]Compressed {success_count} images. Saved {mb_saved:.2f} MB.[/green]")
