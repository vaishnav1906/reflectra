import subprocess
import os

with open("git_log_timetable.txt", "w") as f:
    result = subprocess.run(["git", "log", "-S", "Timetable", "--oneline", "-p", "frontend/src/"], cwd="/workspaces/reflectra", capture_output=True, text=True)
    f.write(result.stdout)
