#!/usr/bin/env python3
"""Record each explicitly selected command and stop on evidence byte changes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
HISTORY = ('crates/kernel/evidence', 'crates/kernel/复核', '数据/复核')

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def snapshot():
    result = {}
    for base in HISTORY:
        for directory, dirs, names in os.walk(ROOT / base):
            dirs.sort()
            for name in sorted(names):
                p = Path(directory) / name
                with p.open('rb') as f:
                    before = os.fstat(f.fileno())
                    sha = hashlib.file_digest(f, 'sha256').hexdigest()
                    after = os.fstat(f.fileno())
                assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(p)
                result[str(p.relative_to(ROOT))] = {'sha256': sha, 'bytes': after.st_size}
    return result

def difference(old, new):
    return {'added': sorted(new.keys() - old.keys()), 'deleted': sorted(old.keys() - new.keys()),
            'changed': sorted(k for k in old.keys() & new.keys() if old[k] != new[k])}

def run(name, args):
    if (OUT / 'STOP.json').exists():
        raise RuntimeError('history changed; no more execution')
    assert not (OUT / (name + '.result.json')).exists(), name
    if args[0] == 'cargo':
        allowed = [
            ['build', '--workspace', '-j', '4'], ['build', '--workspace', '--release', '-j', '4'],
            ['check', '--workspace', '--all-targets', '-j', '4'],
            ['clippy', '--workspace', '--all-targets', '-j', '4'],
        ]
        for package, kind in [('kernel', ['--lib']), ('topology', ['--lib']),
                              ('kernel', ['--test', 'reference']), ('topology', ['--test', 'validation']),
                              ('kernel', ['--doc']), ('topology', ['--doc'])]:
            allowed.append(['test', '-p', package, *kind, '-j', '4', '--', '--test-threads=1'])
        assert args[1:] in allowed, args
    else:
        assert (args[:3] == ['python3', '-B', '数据/工具/formal_catalog.py']
                or args[0] in [str(ROOT / 'target/release/kernel'), str(ROOT / 'target/release/topology')]), args
    before = snapshot()
    save(name + '.before-history.json', {'files': before})
    initial = json.loads((OUT / 'initial-history.json').read_text())['files']
    d = difference(initial, before)
    if any(d.values()):
        save('STOP.json', {'command': name, 'phase': 'before', 'diff': d})
        raise RuntimeError('history differs from this audit initial snapshot')
    env = dict(os.environ, CARGO_TARGET_DIR=str(ROOT / 'target'), CARGO_BUILD_JOBS='4',
               RUST_TEST_THREADS='1', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    started = datetime.now(timezone.utc).isoformat()
    with (OUT / (name + '.stdout.log')).open('wb') as stdout, (OUT / (name + '.stderr.log')).open('wb') as stderr:
        completed = subprocess.run(args, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
    after = snapshot()
    d = difference(before, after)
    save(name + '.after-history.json', {'files': after})
    row = {'name': name, 'argv': args, 'cwd': str(ROOT), 'started_utc': started,
           'finished_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': completed.returncode,
           'history_diff': d, 'history_file_count': len(after)}
    save(name + '.result.json', row)
    with (OUT / 'commands.jsonl').open('a') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)
    if any(d.values()):
        save('STOP.json', row)
        raise RuntimeError('history changed; stopped without restoring')
    return completed.returncode

if __name__ == '__main__':
    sys.exit(run(sys.argv[1], sys.argv[2:]))
