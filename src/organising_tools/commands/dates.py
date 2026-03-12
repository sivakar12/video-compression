import click
import os
import re
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
from .. import utils

console = Console()

@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--dry-run', is_flag=True, help="Show what would happen without applying changes.")
def fix_modified_dates(directory, dry_run):
    """
    Syncs modified date to the earliest found date (metadata or created).
    """
    base_dir = Path(directory)
    console.print(f"[bold blue]Scanning {base_dir} for Modified Date fixes...[/bold blue]")
    
    files_to_change = []
    
    for file_path in base_dir.iterdir():
        if file_path.name.startswith('.') or not file_path.is_file():
            continue
            
        dates = utils.get_file_dates(file_path)
        earliest = dates['created'] # This is the min of all dates found by utils
        current_mtime = dates['modified']
        
        # Check if difference is significant (e.g. > 1 second)
        if abs(earliest - current_mtime) > 2.0:
            files_to_change.append({
                'path': file_path,
                'current': current_mtime,
                'new': earliest
            })
            
    if not files_to_change:
        console.print("[green]All files have correct Modified dates (consistent with earliest found).[/green]")
        return
        
    table = Table(title=f"Proposed Modified Date Fixes ({len(files_to_change)} files)")
    table.add_column("File", style="cyan")
    table.add_column("Current Modified", style="red")
    table.add_column("Earliest (New)", style="green")
    
    for item in sorted(files_to_change, key=lambda x: x['path'].name):
        curr_str = datetime.fromtimestamp(item['current']).strftime("%Y-%m-%d %H:%M:%S")
        new_str = datetime.fromtimestamp(item['new']).strftime("%Y-%m-%d %H:%M:%S")
        table.add_row(item['path'].name, curr_str, new_str)
        
    console.print(table)
    
    if dry_run:
        console.print("[yellow]Dry run. No changes made.[/yellow]")
        return
        
    if Confirm.ask("Apply these changes?"):
        with console.status("Applying fixes..."):
            for item in files_to_change:
                # We want to change modified time, but keep created time (if possible)
                # utils.apply_dates_to_file sets birthtime=first arg, mtime=second arg
                # We should get the current birthtime to preserve it, OR set birthtime to earliest too?
                # The user said "set the others to that" (earliest). 
                # So mostly we want both to match earliest.
                # But strict interpretation of 'fix-modified-dates' might mean only modify mtime.
                # However, updating mtime is done via os.utime. 
                # Let's use utils.apply_dates_to_file with consistent dates.
                
                # We need to know what to pass for 'created' param of apply_dates_to_file.
                # If we pass dates['fs_created'], it preserves current birthtime (if accurate).
                # But earliest is likely the 'correct' birthtime too.
                # If earliest < fs_created, definitely set birthtime too if possible.
                
                utils.apply_dates_to_file(item['path'], created=item['new'], modified=item['new'])
                
        console.print("[green]Done![/green]")
    else:
        console.print("[dim]Cancelled.[/dim]")


@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--dry-run', is_flag=True, help="Show what would happen without applying changes.")
def fix_created_dates(directory, dry_run):
    """
    Syncs created date (birthtime) to the earliest found date (metadata or modified).
    """
    base_dir = Path(directory)
    console.print(f"[bold blue]Scanning {base_dir} for Created Date information...[/bold blue]")
    
    files_to_change = []
    
    for file_path in base_dir.iterdir():
        if file_path.name.startswith('.') or not file_path.is_file():
            continue
            
        dates = utils.get_file_dates(file_path)
        earliest = dates['created']
        current_birth = dates.get('fs_created', dates['modified']) # Fallback if no birthtime
        
        # Check diff
        if abs(earliest - current_birth) > 2.0:
             files_to_change.append({
                'path': file_path,
                'current': current_birth,
                'new': earliest
            })
            
    if not files_to_change:
        console.print("[green]All files have consistent Created dates.[/green]")
        return

    table = Table(title=f"Proposed Created Date Fixes ({len(files_to_change)} files)")
    table.add_column("File", style="cyan")
    table.add_column("Current Created", style="red")
    table.add_column("Earliest (New)", style="green")

    for item in sorted(files_to_change, key=lambda x: x['path'].name):
        curr_str = datetime.fromtimestamp(item['current']).strftime("%Y-%m-%d %H:%M:%S")
        new_str = datetime.fromtimestamp(item['new']).strftime("%Y-%m-%d %H:%M:%S")
        table.add_row(item['path'].name, curr_str, new_str)
        
    console.print(table)
    
    if dry_run:
        console.print("[yellow]Dry run. No changes made.[/yellow]")
        return
        
    if Confirm.ask("Apply these changes?"):
        with console.status("Applying fixes..."):
            for item in files_to_change:
                # Set birthtime to earliest. Keep modified as is? 
                # If modified is LATER than earliest, it's fine.
                # If modified is EARLIER than earliest, that's impossible if earliest is min.
                # But actually earliest IS min(modified, created, meta).
                # So earliest <= modified.
                # So modified is >= earliest.
                # We can keep modified as is, or sync it.
                # "set the others to that".
                # I'll sync both to be safe and consistent.
                utils.apply_dates_to_file(item['path'], created=item['new'], modified=item['new'])
                
        console.print("[green]Done![/green]")
    else:
        console.print("[dim]Cancelled.[/dim]")


@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--dry-run', is_flag=True, help="Show what would happen without applying changes.")
@click.option('--timezone', 'tz_str', default=None, help="Timezone offset for the filename timestamp, e.g. +2, +530, -4.")
def add_timestamp_to_filename(directory, dry_run, tz_str):
    """
    Renames files to include timestamp prefix (YYYYMMDD-HHMMSS_).
    Preserves existing timestamps in names if present.
    """
    base_dir = Path(directory)

    # Parse timezone if provided
    tz = None
    if tz_str is not None:
        try:
            tz = utils.parse_timezone_offset(tz_str)
            console.print(f"[bold]Using timezone offset: {tz}[/bold]")
        except ValueError as e:
            console.print(f"[red]Invalid timezone: {e}[/red]")
            return

    console.print(f"[bold blue]Scanning {base_dir} for renaming...[/bold blue]")
    
    files_to_rename = []
    
    # Check for existing pattern YYYYMMDD-HHMMSS
    pattern = re.compile(r"^\d{8}-\d{6}.*")
    
    for file_path in base_dir.iterdir():
        if file_path.name.startswith('.') or not file_path.is_file():
            continue
        
        # Skip if state file
        if file_path.name == utils.STATE_FILE_NAME:
            continue
            
        if pattern.match(file_path.name):
            continue
            
        dates = utils.get_file_dates(file_path)
        earliest = dates['created']
        
        new_name = utils.generate_output_filename(file_path, earliest, tz=tz)
        
        # Check if name is actually different (ignore case if needed, but usually exact match)
        if new_name != file_path.name:
            files_to_rename.append({
                'path': file_path,
                'new_name': new_name,
                'earliest': earliest
            })
            
    if not files_to_rename:
        console.print("[green]No files need renaming (or all already have timestamps).[/green]")
        return
        
    table = Table(title=f"Proposed Renames ({len(files_to_rename)} files)")
    table.add_column("Current Name", style="red")
    table.add_column("New Name", style="green")
    
    for item in sorted(files_to_rename, key=lambda x: x['path'].name):
        table.add_row(item['path'].name, item['new_name'])
        
    console.print(table)
    
    if dry_run:
        console.print("[yellow]Dry run. No changes made.[/yellow]")
        return
        
    if Confirm.ask("Rename files?"):
        with console.status("Renaming..."):
            count = 0
            for item in files_to_rename:
                src = item['path']
                dest = base_dir / item['new_name']
                
                if dest.exists():
                    console.print(f"[yellow]Skipping {src.name}: Target {dest.name} exists.[/yellow]")
                    continue
                    
                try:
                    src.rename(dest)
                    # Re-apply dates ensuring consistency
                    utils.apply_dates_to_file(dest, item['earliest'], item['earliest'])
                    count += 1
                except Exception as e:
                    console.print(f"[red]Error renaming {src.name}: {e}[/red]")
                    
        console.print(f"[green]Renamed {count} files.[/green]")
    else:
        console.print("[dim]Cancelled.[/dim]")


@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--dry-run', is_flag=True, help="Show what would happen without applying changes.")
def update_dates_from_filename(directory, dry_run):
    """
    Reads the YYYYMMDD-HHMMSS (and optional timezone) timestamp from filenames
    and updates the file's created and modified dates to match.
    """
    base_dir = Path(directory)
    console.print(f"[bold blue]Scanning {base_dir} to update dates from filenames...[/bold blue]")

    files_to_change = []

    # Regex matches: YYYYMMDD-HHMMSS, optionally followed by +XXXX or -XXXX, then anything
    pattern = re.compile(r"^(\d{8}-\d{6})([+-]\d{2,4})?.*")

    for file_path in base_dir.iterdir():
        if file_path.name.startswith('.') or not file_path.is_file():
            continue

        if file_path.name == utils.STATE_FILE_NAME:
            continue

        match = pattern.match(file_path.name)
        if not match:
            continue

        date_str = match.group(1)
        tz_str = match.group(2)

        try:
            # Parse the basic datetime (YYYYMMDD-HHMMSS)
            dt = datetime.strptime(date_str, "%Y%m%d-%H%M%S")

            if tz_str:
                # If there's a timezone, parse it and attach to datetime
                tz = utils.parse_timezone_offset(tz_str)
                dt = dt.replace(tzinfo=tz)
                new_ts = dt.timestamp()
            else:
                # Assume local time if no timezone is provided
                dt = dt.astimezone()
                new_ts = dt.timestamp()

        except ValueError as e:
            console.print(f"[yellow]Failed to parse date from {file_path.name}: {e}[/yellow]")
            continue

        dates = utils.get_file_dates(file_path)
        current_mtime = dates['modified']

        # If the file's current modified date is off by more than 2 seconds, we update it
        if abs(new_ts - current_mtime) > 2.0:
            files_to_change.append({
                'path': file_path,
                'current': current_mtime,
                'new': new_ts
            })

    if not files_to_change:
        console.print("[green]All files have modified/created dates that match their filename timestamps.[/green]")
        return

    table = Table(title=f"Proposed Date Updates From Filename ({len(files_to_change)} files)")
    table.add_column("File", style="cyan")
    table.add_column("Current Modified Date", style="red")
    table.add_column("New Date (from filename)", style="green")

    for item in sorted(files_to_change, key=lambda x: x['path'].name):
        curr_str = datetime.fromtimestamp(item['current']).strftime("%Y-%m-%d %H:%M:%S")
        new_str = datetime.fromtimestamp(item['new']).strftime("%Y-%m-%d %H:%M:%S")
        table.add_row(item['path'].name, curr_str, new_str)

    console.print(table)

    if dry_run:
        console.print("[yellow]Dry run. No changes made.[/yellow]")
        return

    if Confirm.ask("Apply these changes?"):
        with console.status("Applying date updates..."):
            count = 0
            for item in files_to_change:
                utils.apply_dates_to_file(item['path'], created=item['new'], modified=item['new'])
                count += 1
        console.print(f"[green]Updated dates for {count} files.[/green]")
    else:
        console.print("[dim]Cancelled.[/dim]")
