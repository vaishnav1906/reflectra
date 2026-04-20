import subprocess
import os
from pathlib import Path

with open("git_log_timetable.txt", "w") as f:
    result = subprocess.run(["git", "log", "-S", "Timetable", "--oneline", "-p", "frontend/src/"], cwd=Path(__file__).resolve().parent.parent.parent, capture_output=True, text=True)
    f.write(result.stdout)
