import pytest
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from click.testing import CliRunner

from organising_tools.utils import parse_timezone_offset, generate_output_filename
from organising_tools.commands.dates import add_timestamp_to_filename


# ── parse_timezone_offset tests ──

class TestParseTimezoneOffset:
    def test_plus_hours_single_digit(self):
        tz = parse_timezone_offset("+2")
        assert tz == timezone(timedelta(hours=2))

    def test_plus_hours_double_digit(self):
        tz = parse_timezone_offset("+10")
        assert tz == timezone(timedelta(hours=10))

    def test_plus_hours_and_minutes(self):
        tz = parse_timezone_offset("+530")
        assert tz == timezone(timedelta(hours=5, minutes=30))

    def test_plus_hours_and_minutes_four_digits(self):
        tz = parse_timezone_offset("+1245")
        assert tz == timezone(timedelta(hours=12, minutes=45))

    def test_minus_hours(self):
        tz = parse_timezone_offset("-4")
        assert tz == timezone(timedelta(hours=-4))

    def test_minus_hours_and_minutes(self):
        tz = parse_timezone_offset("-930")
        assert tz == timezone(timedelta(hours=-9, minutes=-30))

    def test_zero(self):
        tz = parse_timezone_offset("+0")
        assert tz == timezone.utc

    def test_whitespace_stripped(self):
        tz = parse_timezone_offset("  +530  ")
        assert tz == timezone(timedelta(hours=5, minutes=30))

    def test_invalid_empty(self):
        with pytest.raises(ValueError, match="Empty timezone"):
            parse_timezone_offset("")

    def test_invalid_no_sign(self):
        with pytest.raises(ValueError, match="must start with"):
            parse_timezone_offset("530")

    def test_invalid_non_numeric(self):
        with pytest.raises(ValueError, match="Invalid timezone"):
            parse_timezone_offset("+abc")

    def test_invalid_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            parse_timezone_offset("+12345")

    def test_invalid_hours_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            parse_timezone_offset("+15")

    def test_invalid_minutes_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            parse_timezone_offset("+560")


# ── generate_output_filename with timezone tests ──

class TestGenerateOutputFilenameTimezone:
    """Test that the timezone flag correctly shifts the displayed time in the filename."""

    def test_utc_timezone(self):
        # 2024-01-15 12:30:00 UTC
        ts = datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc).timestamp()
        tz = timezone.utc
        name = generate_output_filename(Path("video.mp4"), ts, tz=tz)
        assert name.startswith("20240115-123000+0000_video.mp4")

    def test_plus_530_timezone(self):
        # 2024-01-15 12:30:00 UTC → in +05:30 = 18:00:00
        ts = datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc).timestamp()
        tz = parse_timezone_offset("+530")
        name = generate_output_filename(Path("video.mp4"), ts, tz=tz)
        assert name.startswith("20240115-180000+0530_video.mp4")

    def test_minus_4_timezone(self):
        # 2024-01-15 12:30:00 UTC → in -04:00 = 08:30:00
        ts = datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc).timestamp()
        tz = parse_timezone_offset("-4")
        name = generate_output_filename(Path("video.mp4"), ts, tz=tz)
        assert name.startswith("20240115-083000-0400_video.mp4")

    def test_date_rolls_over_day(self):
        # 2024-01-15 23:00:00 UTC → in +05:30 = 2024-01-16 04:30:00
        ts = datetime(2024, 1, 15, 23, 0, 0, tzinfo=timezone.utc).timestamp()
        tz = parse_timezone_offset("+530")
        name = generate_output_filename(Path("sunset.mov"), ts, tz=tz)
        assert name.startswith("20240116-043000+0530_sunset.mov")

    def test_spaces_replaced_with_underscores(self):
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        tz = timezone.utc
        name = generate_output_filename(Path("my holiday video.mp4"), ts, tz=tz)
        assert "my_holiday_video" in name

    def test_no_timezone_uses_system_local(self):
        """When no tz is passed, filename should still be generated with system local tz."""
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        name = generate_output_filename(Path("test.mp4"), ts)
        # Just check it generates a valid name with some offset
        assert name.endswith("_test.mp4")
        assert len(name) > len("_test.mp4")


# ── CLI command tests ──

class TestAddTimestampToFilenameTimezone:
    """Test the add_timestamp_to_filename command with --timezone flag."""

    @pytest.fixture
    def files_dir(self, tmp_path):
        """Create temp files with a known UTC timestamp."""
        # Use a fixed old time so rename always triggers
        old_time = time.time() - 3600
        f1 = tmp_path / "photo.jpg"
        f1.write_text("dummy")
        os.utime(f1, (old_time, old_time))
        return tmp_path

    def test_dry_run_with_timezone(self, files_dir):
        runner = CliRunner()
        result = runner.invoke(add_timestamp_to_filename, [
            str(files_dir), "--dry-run", "--timezone", "+2"
        ])
        assert result.exit_code == 0
        assert "Using timezone offset" in result.output
        assert "+0200" in result.output
        assert "Dry run" in result.output

    def test_dry_run_with_timezone_530(self, files_dir):
        runner = CliRunner()
        result = runner.invoke(add_timestamp_to_filename, [
            str(files_dir), "--dry-run", "--timezone", "+530"
        ])
        assert result.exit_code == 0
        assert "+0530" in result.output

    def test_dry_run_with_negative_timezone(self, files_dir):
        runner = CliRunner()
        result = runner.invoke(add_timestamp_to_filename, [
            str(files_dir), "--dry-run", "--timezone", "-4"
        ])
        assert result.exit_code == 0
        assert "-0400" in result.output

    def test_invalid_timezone_shows_error(self, files_dir):
        runner = CliRunner()
        result = runner.invoke(add_timestamp_to_filename, [
            str(files_dir), "--timezone", "abc"
        ])
        assert result.exit_code == 0  # click doesn't error, our code handles it
        assert "Invalid timezone" in result.output

    def test_actual_rename_with_timezone(self, files_dir):
        runner = CliRunner()
        result = runner.invoke(add_timestamp_to_filename, [
            str(files_dir), "--timezone", "+0"
        ], input="y\n")
        assert result.exit_code == 0
        
        renamed = [f.name for f in files_dir.iterdir() if not f.name.startswith('.')]
        assert len(renamed) == 1
        name = renamed[0]
        # Should have UTC offset +0000 in filename
        assert "+0000" in name
        assert "photo" in name

    def test_without_timezone_still_works(self, files_dir):
        runner = CliRunner()
        result = runner.invoke(add_timestamp_to_filename, [
            str(files_dir), "--dry-run"
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.output
