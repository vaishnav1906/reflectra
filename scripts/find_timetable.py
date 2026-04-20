import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
output_file = ROOT / "data" / "git_log_timetable.txt"

result = subprocess.run(
    ["git", "log", "-S", "Timetable", "--oneline", "-p", "frontend/src/"],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
)

output_file.parent.mkdir(parents=True, exist_ok=True)
output_file.write_text(result.stdout)
