# All in One Organising Tool

- First this was a video compressing CLI. Now I want to make it to run a variety of commands in the working directory
- I changed the folder name from video-compress to organising-tools. The package name has to be changes and editable mode install has to be made
- video-compress will be a sub command and many more sub commands will be added one by one.
- Need to separate timestamping in file and fixing modified dates into separate commands as well.
- So make video compress lean. It has to do that to all the files in the folder. While still maintaining the tracking file like before. It will rename and put hte originals in the original folder
- Need two new commands. 'fix-modified-dates' and 'fix-created-dates'.
    - Each checks the other date and in the case of photos metadata inside the file to find the earliest date and set the others to that.
    - Do an analysis and report how many are going to be changed and confirm with y/n and do it
- Then we need another command to compress image files. Same format. If possible compress. No loss in quality. Ask the right questions like in video compress and compress. And put the originals in the original folder
- We have filename timestamping code. Same format we have to use. Export that pattern as a separate module. Use that in video and photo. 'add-timestamp-to-filename' command will do the work.
    - It has to check all filenames and check how many actually have the timestamp and offer to do just them. On confirmation only renames have to happen. Use the same old logic.
    - Renaming must not affect modified or created time
- New command to track the favourite folders. go-to-favourite folder should list available favorite. Navigate with arrow keys. Then go to the folder. Command ends after taking the terminal to the folder. And another command called 'add-folder-to-favourites'. That adds to the set if not already there. This is managed in home directory file. 
- Need to make all of this modular. Simple components but as few as possible.
