#!/usr/bin/env python3
"""顺序执行一个验证步骤，保存完整输出、命令、环境、耗时与退出码。"""
from pathlib import Path
import datetime, json, os, subprocess, sys, time

O = Path(__file__).resolve().parent
R = O.parents[1]
name, *argv = sys.argv[1:]
env = dict(os.environ)
settings = {'CARGO_TARGET_DIR': str(R/'target'), 'CARGO_BUILD_JOBS': '6',
            'RUST_TEST_THREADS': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
            'MKL_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1',
            'KERNEL_TEST_EVIDENCE_DIR': str(O/'test-evidence-tmp')}
env.update(settings)
if name == 'cargo-test-workspace-isolated':
    env['PATH'] = str(O/'bin') + os.pathsep + env['PATH']
    settings['PATH_prefix'] = str(O/'bin')
(O/'test-evidence-tmp').mkdir(exist_ok=True)
start = time.monotonic()
with (O/(name+'.log')).open('w') as log:
    result = subprocess.run(argv, cwd=R, env=env, stdout=log, stderr=subprocess.STDOUT)
row = {'name': name, 'argv': argv, 'cwd': str(R), 'environment': settings,
       'exit_code': result.returncode, 'seconds': round(time.monotonic()-start, 3),
       'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'log': name+'.log'}
with (O/'commands.jsonl').open('a') as log:
    log.write(json.dumps(row, ensure_ascii=False)+'\n')
print(json.dumps(row, ensure_ascii=False), flush=True)
if result.returncode:
    print((O/(name+'.log')).read_text()[-8000:])
raise SystemExit(result.returncode)
