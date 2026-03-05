import pytest
from pathlib import Path
from click.testing import CliRunner
from organising_tools.commands.duplicates import find_duplicates


@pytest.fixture
def duplicates_dir(tmp_path):
    """Creates a temp directory with known duplicate and unique files."""
    # Duplicate pair: same content, different name lengths
    content_a = b"hello world duplicate content here"
    (tmp_path / "photo.jpg").write_bytes(content_a)
    (tmp_path / "photo copy.jpg").write_bytes(content_a)

    # Another duplicate group (3 files)
    content_b = b"another piece of duplicate data 1234567890"
    (tmp_path / "doc.txt").write_bytes(content_b)
    (tmp_path / "doc (1).txt").write_bytes(content_b)
    (tmp_path / "doc - Copy.txt").write_bytes(content_b)

    # Unique file (same size as content_a but different content — tests partial hash)
    unique_same_size = b"x" * len(content_a)
    (tmp_path / "unique.dat").write_bytes(unique_same_size)

    # Completely unique file
    (tmp_path / "notes.md").write_bytes(b"some unique notes")

    return tmp_path


def test_find_duplicates_detects_groups(duplicates_dir):
    """Command should detect the two duplicate groups."""
    runner = CliRunner()
    result = runner.invoke(find_duplicates, [str(duplicates_dir), "--dry-run"])

    assert result.exit_code == 0
    assert "2 duplicate group(s)" in result.output
    assert "3 duplicate file(s)" in result.output
    assert "Dry run" in result.output


def test_find_duplicates_dry_run_keeps_all_files(duplicates_dir):
    """Dry run should not delete anything."""
    runner = CliRunner()
    runner.invoke(find_duplicates, [str(duplicates_dir), "--dry-run"])

    files = [f.name for f in duplicates_dir.iterdir() if f.is_file()]
    assert len(files) == 7  # All original files still present


def test_find_duplicates_deletes_longer_names(duplicates_dir):
    """When confirmed, should delete copies with longer filenames."""
    runner = CliRunner()
    result = runner.invoke(find_duplicates, [str(duplicates_dir)], input="y\n")

    assert result.exit_code == 0
    assert "Deleted 3 file(s)" in result.output

    remaining = sorted(f.name for f in duplicates_dir.iterdir() if f.is_file())
    # Should keep: photo.jpg, doc.txt, unique.dat, notes.md
    assert "photo.jpg" in remaining
    assert "photo copy.jpg" not in remaining
    assert "doc.txt" in remaining
    assert "doc (1).txt" not in remaining
    assert "doc - Copy.txt" not in remaining
    assert "unique.dat" in remaining
    assert "notes.md" in remaining


def test_find_duplicates_no_duplicates(tmp_path):
    """When no duplicates exist, should report cleanly."""
    (tmp_path / "a.txt").write_bytes(b"unique content 1")
    (tmp_path / "b.txt").write_bytes(b"unique content 2")

    runner = CliRunner()
    result = runner.invoke(find_duplicates, [str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    assert "No duplicates found" in result.output


def test_find_duplicates_recursive(tmp_path):
    """Recursive flag should find duplicates across subdirectories."""
    sub = tmp_path / "subdir"
    sub.mkdir()

    content = b"recursive duplicate content"
    (tmp_path / "file.txt").write_bytes(content)
    (sub / "file copy.txt").write_bytes(content)

    runner = CliRunner()
    result = runner.invoke(find_duplicates, [str(tmp_path), "--recursive", "--dry-run"])

    assert result.exit_code == 0
    assert "1 duplicate group(s)" in result.output
