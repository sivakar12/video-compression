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

def _group_files(directory, dry_run, format_str, description):
    """
    Helper function to group files by a datetime format.
    """
    base_dir = Path(directory)
    console.print(f"[bold blue]Scanning {base_dir} to group files by {description}...[/bold blue]")
    
    files_to_move = []
    
    for file_path in base_dir.iterdir():
        # Skip directories and hidden files
        if file_path.name.startswith('.') or not file_path.is_file():
            continue
            
        # Skip state file
        if file_path.name == utils.STATE_FILE_NAME:
            continue
            
        dates = utils.get_file_dates(file_path)
        created_ts = dates['created']
        modified_ts = dates['modified']
        
        # Get datetime from timestamp (using created time for grouping)
        dt = datetime.fromtimestamp(created_ts)
        
        # Format folder name based on format_str
        folder_name = dt.strftime(format_str)
        target_dir = base_dir / folder_name
        target_path = target_dir / file_path.name
        
        # Check if created and modified dates differ
        warning = ""
        if abs(created_ts - modified_ts) > 2.0:
            warning = "[yellow]Modified date differs[/yellow]"
            
        # Only move if not already in the target folder
        if file_path.parent != target_dir:
            files_to_move.append({
                'file_path': file_path,
                'target_dir': target_dir,
                'target_path': target_path,
                'folder_name': folder_name,
                'warning': warning
            })
            
    if not files_to_move:
        console.print("[green]No files to move.[/green]")
        return
        
    table = Table(title=f"Proposed Moves ({len(files_to_move)} files)")
    table.add_column("File", style="cyan")
    table.add_column("Target Folder", style="green")
    table.add_column("Status", style="yellow")
    
    for item in sorted(files_to_move, key=lambda x: x['file_path'].name):
        table.add_row(item['file_path'].name, item['folder_name'], item['warning'])
        
    console.print(table)
    
    if dry_run:
        console.print("[yellow]Dry run. No files moved.[/yellow]")
        return
        
    if Confirm.ask(f"Group these files by {description}?"):
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

@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--dry-run', is_flag=True, help="Show what would happen without moving files.")
def group_by_month(directory, dry_run):
    """
    Groups files by their creation month and moves them into folders like '01 January'.
    """
    _group_files(directory, dry_run, "%m %B", "month")

@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--dry-run', is_flag=True, help="Show what would happen without moving files.")
def group_by_year(directory, dry_run):
    """
    Groups files by their creation year and moves them into folders like '2023'.
    """
    _group_files(directory, dry_run, "%Y", "year")

