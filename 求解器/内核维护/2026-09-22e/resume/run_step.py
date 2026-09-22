#!/usr/bin/env python3
"""本次接续验证日志及只读历史守卫；发现历史变化立即停止，不恢复文件。"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
HISTORY = ['crates/kernel/evidence', 'crates/kernel/复核', '数据/复核']

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def snapshot():
    files = {}
    counts = {}
    for relative in HISTORY:
        count = 0
        for directory, dirs, names in os.walk(ROOT / relative):
            for name in sorted(names):
                path = Path(directory) / name
                entry = {'sha256': digest(path), 'bytes': path.stat().st_size}
                if path.is_symlink():
                    entry['symlink'] = os.readlink(path)
                files[str(path.relative_to(ROOT))] = entry
                count += 1
            for name in dirs:
                path = Path(directory) / name
                if path.is_symlink():
                    raise RuntimeError(f'历史目录含未展开目录符号链接：{path}')
        counts[relative] = count
    return {'algorithm': 'sha256', 'counts': counts, 'files': dict(sorted(files.items()))}

def compare(before, after):
    a, b = before['files'], after['files']
    return {'added': sorted(b.keys() - a.keys()), 'deleted': sorted(a.keys() - b.keys()),
            'changed': [p for p in sorted(a.keys() & b.keys()) if a[p] != b[p]]}

def active_snapshot():
    paths = set()
    for base in ['crates/kernel/src', 'crates/topology/src', 'crates/kernel/tests',
                 'crates/topology/tests', '数据/工具', '数据/样例', '数据/候选B']:
        paths.update(p for p in (ROOT / base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.update(p for p in (ROOT / '规格').iterdir() if p.is_file())
    paths.update(p for p in (ROOT / '数据').iterdir() if p.is_file())
    paths.update(ROOT / p for p in ['Cargo.toml', 'Cargo.lock'])
    paths.update(ROOT.parent / p for p in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt'])
    return {str(p): digest(p) for p in sorted(paths)}

def guard(label):
    current = snapshot()
    save(OUT / (label + '-history.json'), current)
    delta = compare(json.loads((OUT / 'initial-history.json').read_text()), current)
    save(OUT / (label + '-history-diff.json'), delta)
    if any(delta.values()):
        raise RuntimeError(f'历史变化，停止且不覆盖：{delta}')
    return current['counts']

if __name__ == '__main__':
    name, *argv = sys.argv[1:]
    assert re.fullmatch(r'[a-z0-9-]+', name)
    if name == 'init':
        assert not argv and not (OUT / 'initial-history.json').exists()
        initial = snapshot()
        save(OUT / 'initial-history.json', initial)
        paths = subprocess.check_output(['git', 'diff', '--name-only', '-z'], cwd=ROOT).decode().split('\0')
        repo = ROOT.parent
        save(OUT / 'initial-worktree.json', {p: digest(repo / p) for p in paths if p})
        (OUT / 'initial-worktree.patch').write_bytes(subprocess.check_output(['git', 'diff'], cwd=ROOT))
        (OUT / 'initial-status.txt').write_bytes(subprocess.check_output(['git', '-c', 'core.quotepath=false', 'status', '--short', '--untracked-files=all'], cwd=ROOT))
        protected = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']
        save(OUT / 'protected-sources.json', {str(repo / p): digest(repo / p) for p in protected})
        print(json.dumps(initial['counts'], ensure_ascii=False))
        sys.exit(0)
    if name == 'final':
        assert not argv
        print(json.dumps(guard('final'), ensure_ascii=False))
        sys.exit(0)
    forbidden = {'revision_cli', 'revision_r2_cli', 'revision_r3_cli', 'revision_r4_cli', 'revision_r5_cli', 'round5_cli', 'round6_cli'}
    assert not forbidden.intersection(argv)
    if argv[0] == 'cargo':
        assert '-j' in argv and int(argv[argv.index('-j') + 1]) <= 4
        if argv[1] == 'test':
            assert '--workspace' not in argv and '--test-threads=1' in argv
            package = argv[argv.index('-p') + 1]
            assert package in {'kernel', 'topology'}
            if '--test' in argv:
                assert (package, argv[argv.index('--test') + 1]) in {('kernel', 'reference'), ('topology', 'validation')}
            else:
                assert '--lib' in argv or '--doc' in argv
        else:
            assert argv[1] in {'build', 'check', 'clippy'} and '--workspace' in argv
    assert not (OUT / (name + '.log')).exists(), '日志不得覆盖'
    counts = guard(name + '-before')
    active_before = active_snapshot()
    save(OUT / (name + '-active-before.json'), active_before)
    environment = {'CARGO_TARGET_DIR': str(ROOT / 'target'), 'CARGO_BUILD_JOBS': '4',
                   'RUST_TEST_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    start = time.monotonic()
    with (OUT / (name + '.log')).open('w') as stream:
        result = subprocess.run(argv, cwd=ROOT, env={**os.environ, **environment}, stdout=stream, stderr=subprocess.STDOUT)
    row = {'name': name, 'argv': argv, 'cwd': str(ROOT), 'environment': environment,
           'exit_code': result.returncode, 'seconds': round(time.monotonic() - start, 3),
           'finished_utc': datetime.now(timezone.utc).isoformat(), 'log': str(OUT / (name + '.log'))}
    active_after = active_snapshot()
    save(OUT / (name + '-active-after.json'), active_after)
    row['active_changes'] = [p for p in sorted(active_before.keys() | active_after.keys())
                             if active_before.get(p) != active_after.get(p)]
    with (OUT / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    guard(name + '-after')
    print(json.dumps(row, ensure_ascii=False))
    print('\n'.join((OUT / (name + '.log')).read_text().splitlines()[-12:]))
    if row['active_changes']:
        raise RuntimeError('活动源码或输入在本命令中发生变化，本次结果不能作为最终验收')
    sys.exit(result.returncode)
