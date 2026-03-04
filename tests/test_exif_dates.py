"""
Tests for EXIF date reading and camera date preference in get_file_dates().
"""
import pytest
import os
import time
from pathlib import Path
from PIL import Image
from datetime import datetime

from organising_tools import utils


def _create_jpeg_with_exif(path: Path, date_str: str = "2020:06:15 14:30:00"):
    """Create a minimal JPEG with DateTimeOriginal set in the Exif sub-IFD."""
    import piexif

    exif_dict = {
        "0th": {},
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: date_str.encode(),
            piexif.ExifIFD.DateTimeDigitized: date_str.encode(),
        },
        "1st": {},
    }
    exif_bytes = piexif.dump(exif_dict)

    img = Image.new("RGB", (100, 100), "red")
    img.save(str(path), format="JPEG", exif=exif_bytes)


class TestExifDateReading:
    """Tests for the EXIF metadata date extraction."""

    def test_get_metadata_date_reads_exif_datetime_original(self, tmp_path):
        """DateTimeOriginal in Exif sub-IFD should be correctly read."""
        img_path = tmp_path / "photo.jpg"
        _create_jpeg_with_exif(img_path, "2020:06:15 14:30:00")

        result = utils.get_metadata_date(img_path)
        assert result is not None
        dt = datetime.fromtimestamp(result)
        assert dt.year == 2020
        assert dt.month == 6
        assert dt.day == 15
        assert dt.hour == 14
        assert dt.minute == 30

    def test_get_file_dates_prefers_exif_over_filesystem(self, tmp_path):
        """For images with EXIF, camera date should be used as 'created'
        even when filesystem dates are earlier."""
        img_path = tmp_path / "photo.jpg"
        _create_jpeg_with_exif(img_path, "2022:01:01 12:00:00")

        # Set filesystem dates to something EARLIER than the EXIF date
        earlier_ts = datetime(2019, 1, 1, 0, 0, 0).timestamp()
        os.utime(img_path, (earlier_ts, earlier_ts))

        dates = utils.get_file_dates(img_path)
        # 'created' should be the EXIF date, not the earlier filesystem date
        expected = datetime(2022, 1, 1, 12, 0, 0).timestamp()
        assert abs(dates['created'] - expected) < 2.0, (
            f"Expected EXIF date ~{expected}, got {dates['created']}"
        )
        assert dates['metadata'] is not None

    def test_get_file_dates_falls_back_for_no_exif_image(self, tmp_path):
        """For images without EXIF, should fall back to filesystem dates."""
        img_path = tmp_path / "no_exif.jpg"
        img = Image.new("RGB", (50, 50), "blue")
        img.save(str(img_path), format="JPEG")

        old_ts = time.time() - 86400
        os.utime(img_path, (old_ts, old_ts))

        dates = utils.get_file_dates(img_path)
        assert dates['metadata'] is None
        # Should use filesystem dates via min()
        assert dates['created'] <= old_ts + 2.0

    def test_get_file_dates_non_image_uses_min(self, tmp_path):
        """Non-image files should still use min() of all available dates."""
        txt_path = tmp_path / "notes.txt"
        txt_path.write_text("hello")

        old_ts = time.time() - 86400
        os.utime(txt_path, (old_ts, old_ts))

        dates = utils.get_file_dates(txt_path)
        assert dates['metadata'] is None
        assert dates['created'] <= old_ts + 2.0
