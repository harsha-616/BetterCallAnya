import os
import shutil

# 1. Delete corrupted .git tracking
git_dir = ".git"
if os.path.exists(git_dir):
    shutil.rmtree(git_dir)

# 2. Move incorrectly placed files out of .gitignore directory
ignore_dir = ".gitignore"
if os.path.exists(ignore_dir) and os.path.isdir(ignore_dir):
    for item in os.listdir(ignore_dir):
        src = os.path.join(ignore_dir, item)
        dst = os.path.join(".", item)
        
        # If destination already exists, remove it first
        if os.path.exists(dst):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)
                
        shutil.move(src, dst)
    os.rmdir(ignore_dir)
    print("Successfully moved files out of the .gitignore directory!")

