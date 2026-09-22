"""修订r5全量验收命令台账；所有编译只写共享target。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

E = Path(__file__).resolve().parent
ROOT = E.parents[4]
ENV = dict(os.environ, CARGO_HOME=str(ROOT / '.cargo-home'), CARGO_TARGET_DIR=str(ROOT / 'target'),
    PYTHONDONTWRITEBYTECODE='1')
FINISH_ONLY = '--finish-only' in sys.argv[1:]
STEPS = json.loads((E / 'validation-commands.json').read_text()) if FINISH_ONLY else []


def run(name, args):
    print('开始', name, flush=True)
    start = time.monotonic()
    with (E / (name + '.log')).open('w') as log:
        result = subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)
    row = dict(name=name, command=list(map(str, args)), exit_code=result.returncode,
        seconds=time.monotonic() - start, log=str(E / (name + '.log')))
    STEPS.append(row)
    (E / 'validation-commands.json').write_text(json.dumps(STEPS, ensure_ascii=False, indent=2) + '\n')
    print('完成', name, result.returncode, flush=True)
    assert result.returncode == 0, row


if not FINISH_ONLY:
    run('cargo-test', ['cargo', 'test', '--locked', '--offline'])
    run('clippy', ['cargo', 'clippy', '--locked', '--offline', '--all-targets', '--', '-D', 'warnings'])
    run('build', ['cargo', 'build', '--release', '--locked', '--offline', '-p', 'kernel'])
    run('release-cli', [sys.executable, '-B', ROOT / 'crates/kernel/tests/revision_r5_cli.py'])
    run('regenerate', [sys.executable, '-B', E / 'refresh_samples.py'])
    run('benchmark', [sys.executable, '-B', ROOT / 'crates/kernel/tests/benchmark_round6.py', 'final', '--out-dir', E / 'benchmark'])
run('verify-readonly', [sys.executable, '-B', E / 'verify_readonly.py'])
run('spec-selfcheck', [sys.executable, '-B', E / 'spec_selfcheck.py'])
run('reduction-lock', [sys.executable, '-B', E / 'relock_reduction.py'])
