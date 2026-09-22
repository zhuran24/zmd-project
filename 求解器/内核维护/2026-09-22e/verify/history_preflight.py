#!/usr/bin/env python3
"""Independent read-only evidence audit; writes only beside this script."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

OUT = Path(__file__).resolve().parent
SOLVER = OUT.parents[2]
REPO = SOLVER.parent
ROOTS = ('crates/kernel/evidence', 'crates/kernel/复核', '数据/复核')

def save(name, data):
    with (OUT / name).open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotePath=false', *args], cwd=REPO)

def digest(path):
    with path.open('rb') as f:
        before = os.fstat(f.fileno())
        sha = hashlib.file_digest(f, 'sha256').hexdigest()
        after = os.fstat(f.fileno())
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(path)
    return {'sha256': sha, 'bytes': after.st_size}

started = datetime.now(timezone.utc).isoformat()
files = {}
counts = {}
for root in ROOTS:
    count = 0
    for directory, dirs, names in os.walk(SOLVER / root):
        dirs.sort()
        for name in sorted(names):
            path = Path(directory) / name
            assert path.is_file() and not path.is_symlink(), str(path)
            files[str(path.relative_to(SOLVER))] = digest(path)
            count += 1
    counts[root] = count
paths = ['求解器/' + root for root in ROOTS]
ignored = sorted(p.removeprefix('求解器/') for p in git('ls-files', '--others', '--ignored', '--exclude-standard', '-z', '--', *paths).decode().split('\0') if p)
status = git('status', '--short', '--untracked-files=all', '--', *paths).decode()
snapshot = {'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
            'head': git('rev-parse', 'HEAD').decode().strip(), 'algorithm': 'sha256',
            'counts': counts, 'files': files, 'ignored': ignored, 'git_status': status}
save('initial-history.json', snapshot)
comparisons = []
for relative in ['before-tests-history.json', 'resume/initial-history.json', 'resume/delivery-history.json']:
    baseline_path = OUT.parent / relative
    original = json.loads(baseline_path.read_text())['files']
    expected = {}
    for path, entry in original.items():
        path = path.removeprefix('求解器/')
        if not any(path.startswith(root + '/') for root in ROOTS):
            continue
        expected[path] = entry if isinstance(entry, str) else entry['sha256']
    changed = [{'path': path, 'expected_sha256': sha, 'actual_sha256': files[path]['sha256'],
                'bytes': files[path]['bytes'], 'ignored': path in ignored}
               for path, sha in expected.items() if path in files and sha != files[path]['sha256']]
    added = [{'path': path, **files[path], 'ignored': path in ignored} for path in sorted(files.keys() - expected.keys())]
    deleted = sorted(expected.keys() - files.keys())
    comparisons.append({'baseline': str(baseline_path), 'baseline_file_sha256': digest(baseline_path)['sha256'],
                        'baseline_count': len(expected), 'actual_count': len(files),
                        'changed': changed, 'added': added, 'deleted': deleted})
save('baseline-comparisons.json', comparisons)
protected = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']
save('protected-sources.json', {name: digest(REPO / name) for name in protected})
save('preflight-summary.json', {
    'counts': counts, 'total_files': len(files), 'total_bytes': sum(v['bytes'] for v in files.values()),
    'ignored_files': len(ignored), 'history_git_status_clean': not status,
    'comparisons': [{'baseline': x['baseline'], 'changed': len(x['changed']), 'added': len(x['added']), 'deleted': len(x['deleted'])} for x in comparisons],
    'hard_stop': bool(status) or any(x['changed'] or x['added'] or x['deleted'] for x in comparisons),
    'tests_started': False,
})
print((OUT / 'preflight-summary.json').read_text())
print((OUT / 'baseline-comparisons.json').read_text())
