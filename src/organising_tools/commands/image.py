import click
import shutil
import time
from pathlib import Path
from datetime import timedelta
from PIL import Image, PngImagePlugin
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm
from .. import utils

console = Console()

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'} # Add heic support later if needed (requires pillow-heif)

@click.command('compress-photos')
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--quality', type=int, default=85, help="Quality for JPEG/WebP (1-100). Default 85.")
@click.option('--dry-run', is_flag=True, help="Simulate compression without changes.")
def compress_photos(directory, quality, dry_run):
    """
    Compresses images in the directory.
    Originals go to 'originals/', compressed files go to 'compressed/'. Preserves metadata/dates.
    """
    base_dir = Path(directory)
    originals_dir = base_dir / "originals"
    compressed_dir = base_dir / "compressed"

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
    compressed_dir.mkdir(exist_ok=True)

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
                output_path = compressed_dir / img_path.name

                with Image.open(img_path) as img:
                    raw_exif = img.info.get('exif')
                    icc_profile = img.info.get('icc_profile')
                    xmp = img.info.get('xmp')
                    src_format = img.format

                    kwargs = {'optimize': True}
                    if raw_exif:
                        kwargs['exif'] = raw_exif
                    if icc_profile:
                        kwargs['icc_profile'] = icc_profile
                    if xmp:
                        kwargs['xmp'] = xmp

                    if src_format in ('JPEG', 'WEBP'):
                        kwargs['quality'] = quality
                    elif src_format == 'PNG':
                        png_info = PngImagePlugin.PngInfo()
                        for key, val in img.info.items():
                            if isinstance(key, str) and isinstance(val, str):
                                png_info.add_text(key, val)
                        kwargs['pnginfo'] = png_info

                    img.save(output_path, **kwargs)

                utils.copy_metadata_tags(img_path, output_path)

                new_size = output_path.stat().st_size

                if new_size >= original_size:
                    output_path.unlink()
                    progress.console.print(f"[dim]Skipped {img_path.name}: No size reduction ({original_size} -> {new_size})[/dim]")
                    progress.advance(task)
                    continue

                saved_size += (original_size - new_size)
                utils.apply_dates_to_file(output_path, dates['created'], dates['modified'])
                utils.move_original(img_path, originals_dir)
                
                success_count += 1
                
            except Exception as e:
                console.print(f"[red]Error processing {img_path.name}: {e}[/red]")
                output_path = compressed_dir / img_path.name
                if output_path.exists():
                    output_path.unlink()
            
            progress.advance(task)
            
    mb_saved = saved_size / (1024 * 1024)
    console.print(f"[green]Compressed {success_count} images. Saved {mb_saved:.2f} MB.[/green]")
