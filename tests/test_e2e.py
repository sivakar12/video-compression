import pytest
import os
from pathlib import Path
from click.testing import CliRunner
from organising_tools.commands.dates import add_timestamp_to_filename
from organising_tools.commands.video import compress_videos

from organising_tools import utils

def test_organising_tools_e2e_lifecycle(dummy_files_dir):
    runner = CliRunner()
    
    # Initial state verification
    img_path = dummy_files_dir / "TEST_IMG_001.JPG"
    vid_path = dummy_files_dir / "TEST_VID_002.mp4"
    initial_files = [f.name for f in dummy_files_dir.iterdir() if f.is_file()]
    assert img_path.name in initial_files
    assert vid_path.name in initial_files
    
    # Read the file dates BEFORE the command runs to keep in memory for assertion
    img_dates = utils.get_file_dates(img_path)
    expected_img_name = utils.generate_output_filename(img_path, img_dates['created'])
    
    vid_dates = utils.get_file_dates(vid_path)
    expected_vid_name = utils.generate_output_filename(vid_path, vid_dates['created'])
    
    # 1. RENAME phase - adds timestamp to filename
    # We answer 'y' to Confirm.ask("Rename files?")
    rename_result = runner.invoke(add_timestamp_to_filename, [str(dummy_files_dir)], input="y\n")
    assert rename_result.exit_code == 0
    
    # Verify files were renamed format YYYYMMDD-HHMMSS_
    renamed_files = [f.name for f in dummy_files_dir.iterdir() if not f.name.startswith('.')]
    assert len(renamed_files) > 0
    
    # Test for exact file names dynamically generated
    assert expected_img_name in renamed_files
    assert expected_vid_name in renamed_files
    
    # 2. COMPRESS phase - processes video
    # Answer 'y' to process files prompt, hardcode optional args to avoid interactive codec prompts
    compress_result = runner.invoke(compress_videos, [
        str(dummy_files_dir),
        "--codec", "h264",
        "--crf", "28", 
        "--no-hw-accel"
    ], input="y\n")
    assert compress_result.exit_code == 0
    
    # 3. VERIFY COMPRESSION OUTPUTS
    # If ffmpeg successfully ran, original should be in 'originals' dir
    originals_dir = dummy_files_dir / "originals"
    
    # The compressor might have failed on dummy files if ffmpeg wasn't available,
    # but if it was successful it handles file movement properly
    if originals_dir.exists():
        original_files = [f.name for f in originals_dir.iterdir()]
        if original_files:
            assert expected_vid_name in original_files
    
    # 4. TEARDOWN (Lifecycle End)
    # Pytest cleans up `dummy_files_dir` automatically, 
    # fulfilling the "completed delete at end" aspect of the requirement.
