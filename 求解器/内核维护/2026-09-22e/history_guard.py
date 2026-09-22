#!/usr/bin/env python3
"""历史目录快照与测试后精确还原；只恢复基线为 HEAD 的已跟踪文件。"""
from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys

O = Path(__file__).resolve().parent
R = O.parents[2]
BASES = [R / p for p in ['求解器/crates/kernel/evidence', '求解器/crates/kernel/复核', '求解器/数据/复核', '求解器/规格']]

def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotePath=false', *args], cwd=R)

def save(name, value):
    (O / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def sha(p):
    return hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()

def snapshot():
    # 规格根目录是活动文档；其各子目录纳入保护。其余三棵树全部保护。
    roots = BASES[:3] + sorted(p for p in BASES[3].iterdir() if p.is_dir())
    files = {}
    for base in roots:
        for directory, _, names in os.walk(base):
            for name in names:
                p = Path(directory) / name
                if p.is_file():
                    files[str(p.relative_to(R))] = sha(p)
    statuses = {}
    for base in BASES:
        for p in [base, *sorted(c for c in base.iterdir() if c.is_dir())]:
            statuses[str(p.relative_to(R))] = git('status', '--short', '--untracked-files=all', '--', str(p)).decode()
    return {'head': git('rev-parse', 'HEAD').decode().strip(), 'files': files, 'git_status': statuses}

mode = sys.argv[1]
if mode in ('initial', 'before-tests'):
    data = snapshot()
    save(mode + '-history.json', data)
    if mode == 'before-tests':
        tracked = set(git('ls-files', '-z').decode().split('\0'))
        for path in data['files']:
            if path not in tracked:
                destination = O/'history-untracked-backup'/path
                destination.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(['cp', '--reflink=auto', '--', str(R/path), str(destination)], check=True)
    if mode == 'initial':
        (O / 'initial-git-status.txt').write_bytes(git('status', '--short', '--untracked-files=all'))
        names = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']
        save('只读文件指纹.json', {str(R / name): sha(R / name) for name in names})
    print(mode, len(data['files']), 'files snapshotted')
elif mode == 'restore':
    before = json.loads((O / 'before-tests-history.json').read_text())
    after = snapshot()
    save('after-tests-history.json', after)
    assert before['head'] == after['head'], 'HEAD changed during validation'
    tracked = set(git('ls-files', '-z').decode().split('\0'))
    changed = [p for p, h in before['files'].items() if after['files'].get(p) != h]
    created = sorted(set(after['files']) - set(before['files']))
    # 全部前置核验通过后才进行恢复，避免中途发现既有脏文件。
    for p in changed:
        original = git('show', 'HEAD:' + p) if p in tracked else (O/'history-untracked-backup'/p).read_bytes()
        assert hashlib.sha256(original).hexdigest() == before['files'][p], ('baseline not HEAD', p)
    assert not (set(created) & tracked)
    rows = []
    for p in changed:
        if p in tracked:
            subprocess.run(['git', 'restore', '--source=HEAD', '--worktree', '--', p], cwd=R, check=True)
        else:
            shutil.copy2(O/'history-untracked-backup'/p, R/p)
        rows.append({'path': p, 'action': 'git restore --source=HEAD --worktree' if p in tracked else 'restore pre-existing untracked bytes from backup', 'before_sha256': before['files'][p], 'test_sha256': after['files'].get(p)})
    for p in created:
        (R / p).unlink()
        rows.append({'path': p, 'action': 'delete test-created untracked file', 'test_sha256': after['files'][p]})
    final = snapshot()
    save('history-restoration.json', {'restored_tracked': sum(p in tracked for p in changed), 'restored_preexisting_untracked': sum(p not in tracked for p in changed), 'deleted_untracked': len(created), 'files': rows, 'baseline_byte_equality': before['files'] == final['files']})
    save('after-restore-history.json', final)
    assert before['files'] == final['files']
    print('history restored:', len(changed), 'tracked;', len(created), 'new untracked; byte equality PASS')
else:
    raise SystemExit('expected initial, before-tests or restore')
