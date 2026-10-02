"""Reproduce numerical artifacts serially, only in this output directory."""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
JOBS = [
    ("verify_polling.py", "polling.log"),
    ("verify_plant.py", "plant.log"),
    ("verify_bridges.py", "bridges.log"),
    ("verify_cooldown.py", "cooldown.log"),
    ("verify_combined.py", "combined.log"),
    ("verify_arithmetic.py", "arithmetic.log"),
    ("build_audit.py", "audit.log"),
]

for script, log in JOBS:
    with (HERE/log).open("w") as out:
        result = subprocess.run([sys.executable, "-B", str(HERE/script)],
                                cwd=HERE.parents[3], stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(f"{script} failed; see {HERE/log}")
    print(f"{script}: passed")
