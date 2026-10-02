"""Serial reproduction; at most one calculation process at a time."""
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
for script in ['check_arithmetic.py','check_interfaces.py','check_plants.py',
               'check_bridges_geometry.py','check_bound_edges.py','check_examples.py',
               'check_mixed_cycle.py','check_unaffected.py']:
    done=subprocess.run([sys.executable,'-B',str(HERE/script)],capture_output=True,text=True)
    (HERE/(script[:-3]+'.log')).write_text(done.stdout+done.stderr)
    print(script,done.returncode,flush=True)
    if done.returncode: raise SystemExit(done.returncode)
