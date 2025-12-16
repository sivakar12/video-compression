# Video Compression CLI tool

The problem
- Video filess coming from cameras are very big
- Video compression software are expensive
- GUI software needs many steps for each file. I need to do in batch.
- Video files have no metadata support. I need to track date somehow. Files name looks like the right place.

The requirements for the tool
- One command to run it in a folder with video files
- Keep the resolution but compress to a smaller size
- Output to widely supported format
- Use open source tools
- Keep move original files to a folder in the current folder. After checking the output, I will manually delete.
- Maintain created date and modified date of the orignials. Add them to file name as well.
- Maybe a separate command to add date to the original video file itself. Without changing other metadata dates.
- Stop and resume and crash tracking so big directories can be handled