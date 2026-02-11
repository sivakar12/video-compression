import click
import json
import os
import questionary
from pathlib import Path
from rich.console import Console

console = Console()

CONFIG_DIR = Path.home() / ".organising-tools"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"

def load_favorites():
    if not FAVORITES_FILE.exists():
        return []
    try:
        with open(FAVORITES_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_favorites(favorites):
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(FAVORITES_FILE, 'w') as f:
        json.dump(favorites, f, indent=2)

@click.command()
def add_folder_to_favourites():
    """Adds the current directory to favorites."""
    current_dir = str(Path.cwd())
    favorites = load_favorites()
    
    if current_dir in favorites:
        console.print(f"[yellow]Current directory is already in favorites:[/yellow] {current_dir}")
        return

    favorites.append(current_dir)
    save_favorites(favorites)
    console.print(f"[green]Added to favorites:[/green] {current_dir}")

@click.command()
@click.option('--print-only', is_flag=True, help="Print path to stdout instead of spawning shell.")
def go_to_favourite_folder(print_only):
    """
    Select a favorite folder and switch to it.
    
    By default, this spawns a new shell in the selected directory.
    Use --print-only to just output the path (useful for aliases).
    """
    favorites = load_favorites()
    
    if not favorites:
        console.print("[yellow]No favorites found. Use 'add-folder-to-favourites' first.[/yellow]")
        return
        
    selected = questionary.select(
        "Select folder:",
        choices=favorites,
        qmark="?"
    ).ask()
    
    if not selected:
        return
        
    if print_only:
        print(selected)
    else:
        # Spawn new shell
        target_path = Path(selected)
        if not target_path.exists():
            console.print(f"[red]Directory not found:[/red] {selected}")
            return
            
        os.chdir(target_path)
        shell = os.environ.get('SHELL', '/bin/bash')
        console.print(f"[dim]Spawning new shell in {selected}... (Type 'exit' to return)[/dim]")
        os.execl(shell, shell)
