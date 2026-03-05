import hashlib
import click
from pathlib import Path
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

console = Console()

PARTIAL_HASH_SIZE = 4096  # 4KB for initial partial hash


def _hash_file(file_path: Path, max_bytes: int = None) -> str:
    """Compute SHA-256 hash of a file, optionally reading only max_bytes."""
    sha = hashlib.sha256()
    with open(file_path, 'rb') as f:
        if max_bytes is not None:
            data = f.read(max_bytes)
            sha.update(data)
        else:
            for chunk in iter(lambda: f.read(65536), b''):
                sha.update(chunk)
    return sha.hexdigest()


def _find_duplicate_groups(directory: Path, recursive: bool) -> list[list[Path]]:
    """
    Find duplicate files using a 3-tier approach:
    1. Group by file size
    2. Partial hash (first 4KB) for size-matched groups
    3. Full hash for partial-hash-matched groups

    Returns a list of groups, where each group is a list of duplicate file paths.
    """
    # Step 1: Group by file size
    if recursive:
        all_files = [f for f in directory.rglob('*') if f.is_file() and not f.name.startswith('.')]
    else:
        all_files = [f for f in directory.iterdir() if f.is_file() and not f.name.startswith('.')]

    size_groups = defaultdict(list)
    for f in all_files:
        try:
            size_groups[f.stat().st_size].append(f)
        except OSError:
            continue

    # Keep only groups with 2+ files (potential duplicates)
    size_candidates = [files for files in size_groups.values() if len(files) >= 2]

    # Step 2: Partial hash within each size group
    partial_candidates = []
    for group in size_candidates:
        partial_groups = defaultdict(list)
        for f in group:
            try:
                h = _hash_file(f, max_bytes=PARTIAL_HASH_SIZE)
                partial_groups[h].append(f)
            except OSError:
                continue
        partial_candidates.extend(
            files for files in partial_groups.values() if len(files) >= 2
        )

    # Step 3: Full hash within each partial-hash group
    duplicate_groups = []
    for group in partial_candidates:
        full_groups = defaultdict(list)
        for f in group:
            try:
                h = _hash_file(f)
                full_groups[h].append(f)
            except OSError:
                continue
        duplicate_groups.extend(
            files for files in full_groups.values() if len(files) >= 2
        )

    return duplicate_groups


def _pick_original(group: list[Path]) -> Path:
    """Pick the file with the shortest filename as the 'original'."""
    return min(group, key=lambda p: len(p.name))


@click.command('find-duplicates')
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--recursive', '-r', is_flag=True, help="Scan subdirectories recursively.")
@click.option('--dry-run', is_flag=True, help="Report duplicates without deleting anything.")
def find_duplicates(directory, recursive, dry_run):
    """
    Find duplicate files in a directory.

    Uses a fast 3-tier algorithm: file size → partial hash → full hash.
    Offers to delete copies with longer filenames.
    """
    base_dir = Path(directory)

    console.print(f"[bold blue]Scanning for duplicates in {base_dir}{'  (recursive)' if recursive else ''}...[/bold blue]")

    duplicate_groups = _find_duplicate_groups(base_dir, recursive)

    if not duplicate_groups:
        console.print("[green]No duplicates found.[/green]")
        return

    # Display results
    total_duplicates = sum(len(g) - 1 for g in duplicate_groups)
    total_wasted = sum(
        sum(f.stat().st_size for f in g[1:])  # all except the "original"
        for g in duplicate_groups
    )

    console.print(f"\n[bold yellow]Found {len(duplicate_groups)} duplicate group(s), "
                  f"{total_duplicates} duplicate file(s), "
                  f"wasting {total_wasted / (1024 * 1024):.2f} MB.[/bold yellow]\n")

    files_to_delete = []

    for i, group in enumerate(duplicate_groups, 1):
        original = _pick_original(group)
        copies = [f for f in group if f != original]

        table = Table(title=f"Group {i}", show_header=True, header_style="bold cyan")
        table.add_column("Status", style="bold", width=8)
        table.add_column("File", style="white")
        table.add_column("Size", justify="right")

        size_str = f"{original.stat().st_size / 1024:.1f} KB"
        table.add_row("KEEP", str(original.relative_to(base_dir)), size_str)

        for copy in copies:
            table.add_row("[red]DELETE[/red]", str(copy.relative_to(base_dir)), size_str)
            files_to_delete.append(copy)

        console.print(table)
        console.print()

    if dry_run:
        console.print("[yellow]Dry run — no files were deleted.[/yellow]")
        return

    if not files_to_delete:
        return

    if not Confirm.ask(f"Delete {len(files_to_delete)} duplicate file(s)?"):
        console.print("Aborted.")
        return

    deleted_count = 0
    freed_bytes = 0
    for f in files_to_delete:
        try:
            size = f.stat().st_size
            f.unlink()
            deleted_count += 1
            freed_bytes += size
        except OSError as e:
            console.print(f"[red]Error deleting {f}: {e}[/red]")

    console.print(f"[green]Deleted {deleted_count} file(s), freed {freed_bytes / (1024 * 1024):.2f} MB.[/green]")
