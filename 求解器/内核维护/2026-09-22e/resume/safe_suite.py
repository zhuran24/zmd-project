#!/usr/bin/env python3
"""仅执行本次授权的八项 Cargo 检查；每项由 run_step 前后核历史快照。"""
import subprocess
import sys
from run_step import OUT, ROOT, guard

commands = [
    ('cargo-check', ['cargo', 'check', '--workspace', '--all-targets', '-j', '4']),
    ('cargo-clippy', ['cargo', 'clippy', '--workspace', '--all-targets', '-j', '4']),
    ('kernel-lib', ['cargo', 'test', '-p', 'kernel', '--lib', '-j', '4', '--', '--test-threads=1']),
    ('topology-lib', ['cargo', 'test', '-p', 'topology', '--lib', '-j', '4', '--', '--test-threads=1']),
    ('kernel-reference', ['cargo', 'test', '-p', 'kernel', '--test', 'reference', '-j', '4', '--', '--test-threads=1']),
    ('topology-validation', ['cargo', 'test', '-p', 'topology', '--test', 'validation', '-j', '4', '--', '--test-threads=1']),
    ('kernel-doc', ['cargo', 'test', '-p', 'kernel', '--doc', '-j', '4', '--', '--test-threads=1']),
    ('topology-doc', ['cargo', 'test', '-p', 'topology', '--doc', '-j', '4', '--', '--test-threads=1']),
]
failures = []
final = sys.argv[1:] == ['final']
for name, argv in commands:
    if final:
        if name == 'kernel-lib':
            continue  # 已单独完成带活动文件前后指纹的 kernel-lib-final。
        name += '-final'
    result = subprocess.run([sys.executable, '-B', str(OUT / 'run_step.py'), name, *argv], cwd=ROOT)
    guard('suite-' + name)
    if result.returncode:
        failures.append(name)
print('failed commands:', failures, flush=True)
sys.exit(bool(failures))
