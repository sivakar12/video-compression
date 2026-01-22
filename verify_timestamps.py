import os
import time
import shutil
from pathlib import Path
from datetime import datetime

# Import the utils module from the project
# We need to add the src directory to sys.path
import sys
sys.path.append("/Users/sivakar/Desktop/video-compression/src")
from video_compressor import utils

def verify_timestamp_logic():
    print("Starting verification...")
    
    # 1. Setup test file
    test_dir = Path("test_verification_tmp")
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / "test_file.txt"
    with open(test_file, "w") as f:
        f.write("test content")
        
    # Set arbitrary creation and modification times
    # Let's say Created: 2020-01-01 12:00:00
    # Modified: 2021-01-01 12:00:00
    
    created_ts = datetime(2020, 1, 1, 12, 0, 0).timestamp()
    modified_ts = datetime(2021, 1, 1, 12, 0, 0).timestamp()
    
    # Verify we can set distinct times first (sanity check)
    os.utime(test_file, (time.time(), modified_ts))
    
    # Note: On macOS, setting birthtime is tricky reliably without SetFile or specific syscalls,
    # but utils.apply_dates_to_file tries to handle it. 
    # For this test, we care that the FINAL modification time matches the TARGET creation time.
    
    print(f"Target Creation Time: {datetime.fromtimestamp(created_ts)}")
    print(f"Target Modified Time (Original): {datetime.fromtimestamp(modified_ts)}")
    
    # 2. Simulate the logic in main.py
    # We pass 'created_ts' as the third argument (modified time)
    print("Applying dates (simulating main.py change)...")
    utils.apply_dates_to_file(test_file, created_ts, created_ts)
    
    # 3. Verify
    stat = test_file.stat()
    final_mtime = stat.st_mtime
    
    print(f"Final Modified Time: {datetime.fromtimestamp(final_mtime)}")
    
    # Allow a small epsilon for float precision, though typically exact
    if abs(final_mtime - created_ts) < 1.0:
        print("SUCCESS: Final modification time matches the creation timestamp.")
    else:
        print("FAILURE: Final modification time does NOT match creation timestamp.")
        print(f"Expected: {created_ts}, Got: {final_mtime}")

    # Clean up
    shutil.rmtree(test_dir)

if __name__ == "__main__":
    verify_timestamp_logic()
