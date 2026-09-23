"""本轮命令记录与历史全量 SHA-256 守卫；只能写本轮记录目录。"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
REPO = ROOT.parent
HISTORY = ['crates/kernel/evidence', 'crates/kernel/复核', '数据/复核']
SOURCES = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def snapshot():
    files, counts = {}, {}
    for relative in HISTORY:
        base = ROOT / relative
        assert base.is_dir(), base
        count = 0
        for directory, dirs, names in os.walk(base):
            dirs.sort()
            for name in dirs:
                assert not (Path(directory) / name).is_symlink(), '目录符号链接须单独核查'
            for name in sorted(names):
                path = Path(directory) / name
                stat = path.stat()
                entry = {'bytes': stat.st_size, 'sha256': digest(path)}
                assert stat.st_size == path.stat().st_size and stat.st_mtime_ns == path.stat().st_mtime_ns, path
                if path.is_symlink():
                    entry['symlink'] = os.readlink(path)
                files[str(path.relative_to(ROOT))] = entry
                count += 1
        counts[relative] = count
    return {'algorithm': 'sha256', 'counts': counts, 'files': dict(sorted(files.items()))}

def difference(before, after):
    return {'added': sorted(after.keys() - before.keys()), 'deleted': sorted(before.keys() - after.keys()),
            'changed': [p for p in sorted(before.keys() & after.keys()) if before[p] != after[p]]}

def guard(label):
    assert not (OUT / 'STOP.json').exists(), '历史守卫已停止本轮'
    current = snapshot()
    save(label + '-history.json', current)
    delta = difference(json.loads((OUT / 'initial-history.json').read_text())['files'], current['files'])
    save(label + '-history-diff.json', delta)
    if any(delta.values()):
        save('STOP.json', {'label': label, 'diff': delta})
        raise RuntimeError('历史目录发生变化，立即停止且不还原：' + str(delta))
    return current

def active_snapshot():
    paths = set(REPO / p for p in SOURCES)
    for relative in ['crates/kernel/src', 'crates/topology/src', 'crates/kernel/tests',
                     'crates/topology/tests', '数据/工具', '数据/样例', '数据/候选B']:
        paths.update(p for p in (ROOT / relative).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for relative in ['规格', '数据']:
        paths.update(p for p in (ROOT / relative).iterdir() if p.is_file())
    paths.update(ROOT / p for p in ['Cargo.toml', 'Cargo.lock'])
    return {str(p.relative_to(REPO)): digest(p) for p in sorted(paths)}

def run(name, argv):
    assert name.replace('-', '').isalnum()
    assert not (OUT / (name + '.log')).exists()
    forbidden = {'revision_cli', 'revision_r2_cli', 'revision_r3_cli', 'revision_r4_cli', 'revision_r5_cli', 'round5_cli', 'round6_cli'}
    assert not forbidden.intersection(argv)
    if argv[0] == 'cargo':
        assert argv in [
            ['cargo', command, '--workspace', '-j', '4'] for command in ['build', 'check', 'clippy']
        ] + [
            ['cargo', 'test', '-p', package, flag, *target, '-j', '4', '--', '--test-threads=1']
            for package, flag, target in [('kernel', '--lib', []), ('topology', '--lib', []),
                ('kernel', '--test', ['reference']), ('topology', '--test', ['validation']),
                ('kernel', '--doc', []), ('topology', '--doc', [])]
        ]
    elif argv[0] == 'python3':
        assert argv in [['python3', '数据/工具/formal_catalog.py'], ['python3', '数据/工具/test_formal_catalog.py']]
    else:
        assert Path(argv[0]) == ROOT / 'target/debug/kernel'
        assert argv[1] in ['seed', 'check', 'run', 'verify-record']
        assert Path(argv[2]).is_relative_to(OUT / 'positive')
        if '--out' in argv:
            assert Path(argv[argv.index('--out') + 1]).is_relative_to(OUT / 'positive')
    guard(name + '-before')
    before = active_snapshot()
    save(name + '-active-before.json', before)
    env = {'CARGO_TARGET_DIR': str(ROOT / 'target'), 'CARGO_BUILD_JOBS': '4',
           'RUST_TEST_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    started = time.monotonic()
    with (OUT / (name + '.log')).open('w') as stream:
        result = subprocess.run(argv, cwd=ROOT, env={**os.environ, **env}, stdout=stream, stderr=subprocess.STDOUT)
    row = {'name': name, 'argv': argv, 'cwd': str(ROOT), 'environment': env, 'exit_code': result.returncode,
           'seconds': round(time.monotonic() - started, 3), 'finished_utc': datetime.now(timezone.utc).isoformat()}
    after = active_snapshot()
    save(name + '-active-after.json', after)
    row['active_diff'] = difference(before, after)
    with (OUT / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    guard(name + '-after')
    print(json.dumps(row, ensure_ascii=False), flush=True)
    print('\n'.join((OUT / (name + '.log')).read_text().splitlines()[-16:]), flush=True)
    if any(row['active_diff'].values()):
        save('ACTIVE_STOP.json', row)
        raise RuntimeError('命令运行期间活动文件发生变化')
    return result.returncode

if __name__ == '__main__':
    mode, *args = sys.argv[1:]
    if mode == 'init':
        assert not args and not (OUT / 'initial-history.json').exists()
        initial = snapshot()
        save('initial-history.json', initial)
        save('initial-active.json', active_snapshot())
        save('formal-sources.json', {p: digest(REPO / p) for p in SOURCES})
        (OUT / 'initial-status.txt').write_bytes(subprocess.check_output(['git', '-c', 'core.quotepath=false', 'status', '--short', '--untracked-files=normal'], cwd=REPO))
        (OUT / 'initial-diff.patch').write_bytes(subprocess.check_output(['git', 'diff'], cwd=REPO))
        (OUT / 'initial-head.txt').write_bytes(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO))
        raw = b'\0'.join(('求解器/' + p).encode() for p in initial['files']) + b'\0'
        ignored = subprocess.run(['git', 'check-ignore', '--stdin', '-z'], input=raw, cwd=REPO, capture_output=True)
        assert ignored.returncode in (0, 1)
        save('ignored-history-files.json', sorted(p for p in ignored.stdout.decode().split('\0') if p))
        print(json.dumps({'counts': initial['counts'], 'bytes': sum(p['bytes'] for p in initial['files'].values()),
                          'ignored': len([p for p in ignored.stdout.split(b'\0') if p])}, ensure_ascii=False))
    elif mode == 'snapshot':
        print(json.dumps(guard(args[0])['counts'], ensure_ascii=False))
    elif mode == 'run':
        sys.exit(run(args[0], args[1:]))
    elif mode in ['inspect', 'sync', 'audit', 'positive', 'report']:
        import work
        getattr(work, mode)()
    else:
        raise ValueError(mode)
