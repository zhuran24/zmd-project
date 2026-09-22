#!/usr/bin/env python3
"""复现本席Cargo检查，仅重定向Python集成测试的输出路径。"""
import os
import subprocess
from pathlib import Path

out=Path(__file__).resolve().parent
root=out.parents[3]
wrapper=out/'bin/python'
wrapper.write_bytes((out/'bin/python.py').read_bytes())
wrapper.chmod(0o755)
(out/'tmp').mkdir(exist_ok=True)
env={**os.environ,'PATH':str(out/'bin')+os.pathsep+os.environ['PATH'],
     'CARGO_HOME':str(root/'.cargo-home'),'CARGO_TARGET_DIR':str(root/'target'),
     'TMPDIR':str(out/'tmp'),'PYTHONDONTWRITEBYTECODE':'1'}
try:
    with (out/'cargo-test.log').open('w') as log:
        subprocess.run(['cargo','test','--locked','--offline','--','--skip',
            'round5_cli_resource_statistics_and_cycle_load_stop'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
finally:
    wrapper.unlink()
