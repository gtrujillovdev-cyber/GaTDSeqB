import glob
import os
import shutil

# Restore backup states
if os.path.exists("backup_states"):
    for f in glob.glob("backup_states/state_*.json"):
        shutil.copy(f, os.path.basename(f))
    shutil.rmtree("backup_states")
    print("States restored perfectly.")
else:
    print("No backup found.")
