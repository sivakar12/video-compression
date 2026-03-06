import click
import os
import shutil
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
from .. import utils

console = Console()

@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--dry-run', is_flag=True, help="Show what would happen without moving files.")
def group_by_month(directory, dry_run):
    """
    Groups files by their creation month and moves them into folders like '01 January'.
    """
    base_dir = Path(directory)
    console.print(f"[bold blue]Scanning {base_dir} to group files by month...[/bold blue]")
    
    files_to_move = []
    
    for file_path in base_dir.iterdir():
        # Skip directories and hidden files
        if file_path.name.startswith('.') or not file_path.is_file():
            continue
            
        # Skip state file
        if file_path.name == utils.STATE_FILE_NAME:
            continue
            
        dates = utils.get_file_dates(file_path)
        earliest_ts = dates['created']
        
        # Get datetime from timestamp
        dt = datetime.fromtimestamp(earliest_ts)
        
        # Format folder name as "01 January"
        folder_name = dt.strftime("%m %B")
        target_dir = base_dir / folder_name
        target_path = target_dir / file_path.name
        
        # Only move if not already in the target folder
        # (Since iterating over base_dir, it's not in target_dir yet, but just to be safe)
        if file_path.parent != target_dir:
            files_to_move.append({
                'file_path': file_path,
                'target_dir': target_dir,
                'target_path': target_path,
                'folder_name': folder_name
            })
            
    if not files_to_move:
        console.print("[green]No files to move.[/green]")
        return
        
    table = Table(title=f"Proposed Moves ({len(files_to_move)} files)")
    table.add_column("File", style="cyan")
    table.add_column("Target Folder", style="green")
    
    for item in sorted(files_to_move, key=lambda x: x['file_path'].name):
        table.add_row(item['file_path'].name, item['folder_name'])
        
    console.print(table)
    
    if dry_run:
        console.print("[yellow]Dry run. No files moved.[/yellow]")
        return
        
    if Confirm.ask("Group these files?"):
        with console.status("Moving files..."):
            count = 0
            for item in files_to_move:
                src = item['file_path']
                dest_dir = item['target_dir']
                dest_path = item['target_path']
                
                # Create folder if it doesn't exist
                dest_dir.mkdir(exist_ok=True)
                
                # Handle filename collisions
                if dest_path.exists():
                    # Append timestamp or simple counter to avoid overwrite
                    base = src.stem
                    ext = src.suffix
                    counter = 1
                    while dest_path.exists():
                        dest_path = dest_dir / f"{base}_{counter}{ext}"
                        counter += 1
                
                try:
                    shutil.move(str(src), str(dest_path))
                    count += 1
                except Exception as e:
                    console.print(f"[red]Error moving {src.name}: {e}[/red]")
                    
        console.print(f"[green]Successfully moved {count} files.[/green]")
    else:
        console.print("[dim]Cancelled.[/dim]")
