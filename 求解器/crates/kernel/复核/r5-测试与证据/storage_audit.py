"""独立核体量、替换/删除清单及证据目录纪律，不改写被审材料。"""
from collections import Counter
import hashlib
from pathlib import Path
from review_probe import ROOT, OUT, BASE, read, save

evidence = ROOT / 'crates/kernel/evidence/round6'
before = read(evidence / 'before.json')
declared = read(evidence / 'storage-final.json')
listing = read(evidence / 'files.json')
files = [p for p in BASE.rglob('*') if p.is_file()]
size = sum(p.stat().st_size for p in files)
assert size == declared['after_bytes']
old_size = sum(v['bytes'] for p, v in before['files'].items() if Path(p).is_relative_to(BASE))
assert old_size == declared['before_bytes'] == before['samples_bytes']
assert abs(declared['reduction_percent'] - 100 * (old_size - size) / old_size) < 1e-10
oversize = [dict(path=str(p), bytes=p.stat().st_size) for p in files if p.stat().st_size > 20_000_000]
assert oversize == declared['oversize_files'] == []
replacement_results = []
for row in declared['replaced']:
    p = Path(row['path'])
    assert before['files'][str(p)]['sha256'] == row['old_sha256']
    assert before['files'][str(p)]['bytes'] == row['old_bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest() == row['new_sha256']
    assert p.stat().st_size == row['new_bytes']
    data = read(p)
    if row['retained_ticks'] is not None:
        assert len(data['trace']['ticks']) == row['retained_ticks']
    else:
        assert data['schema'] == 'kernel-cycle-v2'
        assert 'run_record' not in data and 'replay_input' not in data
    replacement_results.append(dict(path=str(p), verified=True, schema=data['schema']))
missing = sorted(p for p in before['files'] if not Path(p).exists())
assert missing == sorted(declared['deleted']) == sorted(listing['deleted'])
assert set(listing['files']) == set(listing['modified'] + listing['added'] + listing['deleted'])
assert len(listing['files']) == len(set(listing['files']))
assert all(Path(p).is_file() or p in listing['deleted'] for p in listing['files'])
extensions = Counter()
for p in evidence.rglob('*'):
    assert not p.is_symlink(), p
    if p.is_dir():
        assert p.name not in ('target', '.cargo-home', 'registry', '__pycache__', 'snapshot'), p
    else:
        extensions[p.suffix] += 1
        assert p.suffix in ('.py', '.log', '.json', '.md'), p
        with p.open('rb') as f:
            start = f.read(8)
        assert not start.startswith((b'\x7fELF', b'!<arch>')), p
        if p.suffix == '.json':
            read(p)
protected = read(ROOT / 'crates/kernel/evidence/round5/protected-baseline.json')
assert len(protected) == 12
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in protected.items())
scope = read(evidence / 'protection-scope.json')
assert len(scope['retained_from_old']) + len(scope['no_longer_byte_protected']) == scope['old_count'] == 1250
assert set(scope['retained_from_old'] + scope['added']) == set(protected)
save('storage-audit.json', dict(status='pass', samples_files=len(files), before_bytes=old_size,
    after_bytes=size, reduction_percent=100 * (old_size - size) / old_size, oversize_files=oversize,
    replacement_results=replacement_results, deleted=missing, listing_paths=len(listing['files']),
    evidence_extensions=dict(extensions), evidence_bytes=sum(p.stat().st_size for p in evidence.rglob('*') if p.is_file()),
    protected_files=len(protected), protection_scope_counts={k:len(scope[k]) for k in ('retained_from_old','added','no_longer_byte_protected')},
    largest_samples=sorted([dict(path=str(p), bytes=p.stat().st_size) for p in files], key=lambda r:r['bytes'], reverse=True)[:5],
    limitation='旧大文件已替换，本席不能独立读取已删除旧字节；旧体量由开工清单求和并与迁移清单交叉核，当前体量/字节/文件存在性为现场复算。'))
print('体量、36项替换、删除、288项清单及round6证据纪律全部通过')
