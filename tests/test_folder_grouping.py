import pytest
import os
import time
from pathlib import Path
from click.testing import CliRunner
from organising_tools.commands.folder import group_by_month, group_by_year

def test_group_by_month(tmp_path):
    runner = CliRunner()
    
    # Create test files with different months
    # January 2023
    jan_file = tmp_path / "jan.txt"
    jan_file.write_text("january")
    jan_time = time.mktime(time.strptime("2023-01-15 12:00:00", "%Y-%m-%d %H:%M:%S"))
    os.utime(jan_file, (jan_time, jan_time))
    
    # February 2023
    feb_file = tmp_path / "feb.txt"
    feb_file.write_text("february")
    feb_time = time.mktime(time.strptime("2023-02-15 12:00:00", "%Y-%m-%d %H:%M:%S"))
    os.utime(feb_file, (feb_time, feb_time))
    
    # Run group-by-month
    result = runner.invoke(group_by_month, [str(tmp_path)], input="y\n", catch_exceptions=False)
    assert result.exit_code == 0
    
    # Verify folders and files
    assert (tmp_path / "01 January").is_dir()
    assert (tmp_path / "02 February").is_dir()
    assert (tmp_path / "01 January" / "jan.txt").exists()
    assert (tmp_path / "02 February" / "feb.txt").exists()

def test_group_by_year(tmp_path):
    runner = CliRunner()
    
    # Create test files with different years
    # 2022
    y2022_file = tmp_path / "2022.txt"
    y2022_file.write_text("2022 content")
    t2022 = time.mktime(time.strptime("2022-06-15 12:00:00", "%Y-%m-%d %H:%M:%S"))
    os.utime(y2022_file, (t2022, t2022))
    
    # 2023
    y2023_file = tmp_path / "2023.txt"
    y2023_file.write_text("2023 content")
    t2023 = time.mktime(time.strptime("2023-06-15 12:00:00", "%Y-%m-%d %H:%M:%S"))
    os.utime(y2023_file, (t2023, t2023))
    
    # Run group-by-year
    result = runner.invoke(group_by_year, [str(tmp_path)], input="y\n")
    assert result.exit_code == 0
    
    # Verify folders and files
    assert (tmp_path / "2022").is_dir()
    assert (tmp_path / "2023").is_dir()
    assert (tmp_path / "2022" / "2022.txt").exists()
    assert (tmp_path / "2023" / "2023.txt").exists()

def test_group_by_year_dry_run(tmp_path):
    runner = CliRunner()
    
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    t2021 = time.mktime(time.strptime("2021-06-15 12:00:00", "%Y-%m-%d %H:%M:%S"))
    os.utime(test_file, (t2021, t2021))
    
    # Run group-by-year with dry-run
    result = runner.invoke(group_by_year, [str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run. No files moved." in result.output
    
    # Verify no changes made
    assert not (tmp_path / "2021").exists()
    assert (tmp_path / "test.txt").exists()
