#!/usr/bin/env python3
"""任务书5§0.2：只清理内核证据树中的编译文件/仓库快照，保留删除清单与源码。"""
import hashlib
import json
from pathlib import Path
import shutil

KERNEL = Path(__file__).resolve().parents[1]
OUT = KERNEL / 'evidence/revision-r3'


def describe(path):
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def scan():
    binaries, forbidden, manifests = [], [], []
    for root in (KERNEL / 'evidence', KERNEL / '复核'):
        for path in root.rglob('*'):
            if path.is_symlink():
                raise AssertionError(('证据符号链接须单独核验', str(path)))
            if path.is_dir() and path.name in ('target', '.cargo-home', 'registry', 'snapshot', '__pycache__'):
                forbidden.append(str(path))
            if path.is_file():
                with path.open('rb') as stream:
                    header = stream.read(8)
                if header.startswith((b'\x7fELF', b'!<arch>\n')):
                    binaries.append(describe(path))
                if path.name in ('Cargo.toml', 'Cargo.lock'):
                    manifests.append(str(path))
    return dict(binaries=binaries, forbidden_directories=forbidden, cargo_manifests=manifests)


def main():
    report_path = OUT / 'cleanup.json'
    if report_path.exists():
        assert not any(scan().values()), scan()
        print('证据清理已完成，保留原删除清单。')
        return
    before = scan()
    snapshot = KERNEL / '复核/r2-测试与证据/snapshot'
    snapshot_files = [describe(p) for p in sorted(snapshot.rglob('*')) if p.is_file()]
    moves = []
    for source, name in [
        ('r1-测试与证据/record-probe', 'r1_record'),
        ('r2-测试与证据/probe', 'r2_records'),
        ('r2-工程证据/library-probe', 'r2_engineering'),
        ('复核-r2-规格保真-证据/probe', 'r2_spec'),
    ]:
        old = KERNEL / '复核' / source
        new = KERNEL / 'tests/legacy_probes' / name
        assert old.is_dir() and not new.exists()
        assert all(p.suffix in ('.rs', '.toml', '.lock') for p in old.rglob('*') if p.is_file())
        originals = [describe(p) for p in old.rglob('*') if p.is_file()]
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        manifest = new / 'Cargo.toml'
        text = manifest.read_text().replace('../snapshot/求解器/crates/kernel', '../../..')
        manifest.write_text(text)
        moves.append(dict(source=str(old), destination=str(new), original_files=originals,
                          note='探针源码移出证据树；相对依赖指向当前内核，不重建历史仓库。'))
    for row in before['binaries']:
        path = Path(row['path'])
        assert path.is_relative_to(KERNEL / '复核') or path.is_relative_to(KERNEL / 'evidence')
        path.unlink()
    assert snapshot.is_relative_to(KERNEL / '复核') and not snapshot.is_symlink()
    shutil.rmtree(snapshot)
    after = scan()
    assert not any(after.values()), after
    report = dict(status='pass', before=before, after=after, moved_probes=moves,
                  removed_snapshot=dict(path=str(snapshot), files=snapshot_files),
                  removed_bytes=sum(r['bytes'] for r in before['binaries']) + sum(r['bytes'] for r in snapshot_files),
                  scope='保留脚本、文本日志（含.txt）、JSON与Markdown；没有复制编译缓存或仓库。')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status='pass', binaries=len(before['binaries']), snapshot_files=len(snapshot_files),
                         moved_probes=len(moves), removed_bytes=report['removed_bytes']), ensure_ascii=False))


if __name__ == '__main__':
    main()
