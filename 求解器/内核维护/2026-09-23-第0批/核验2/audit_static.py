import json,hashlib,difflib,ast
from audit_files import *
M=IMPL.parent;R=ROOT/'求解器'
initial=json.loads((IMPL/'initial-protection.json').read_text())['entries'];start=json.loads((OUT/'start-snapshot.json').read_text())['entries']
changes=json.loads((OUT/'start-vs-implementation-start.json').read_text())
protected=[p for p in initial if p.startswith(('求解器/crates/kernel/src/','求解器/crates/topology/src/')) or p in ['求解器/crates/kernel/tests/verify_all.py','求解器/crates/kernel/tests/audit_task7.py'] or p.startswith('求解器/数据/样例/') and p.endswith('.py') or p.endswith(('Cargo.toml','Cargo.lock')) or p in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']]
assert all(initial[p]==start.get(p) for p in protected)
seal=R/'target/health-capture/continuation-20260923/production-a-test-sources'
patch=[];source_rows=[]
for row in changes:
    p=row['path']
    if not p.startswith(('求解器/crates/kernel/tests/','求解器/数据/工具/')) or row['after']['kind']!='file':continue
    before=row['before'];rel=str(Path(p).relative_to('求解器'));old=b''
    if before:
        q=seal/rel;assert q.is_file() and sha(q)==before['sha256'];old=q.read_bytes()
    now=(ROOT/p).read_bytes();patch.extend(difflib.unified_diff(old.decode().splitlines(True),now.decode().splitlines(True),fromfile='A/'+p,tofile='B/'+p))
    source_rows.append(dict(path=p,before=before,after=row['after'],baseline_bytes=str(seal/rel) if before else None))
(OUT/'scope.diff').write_text(''.join(patch))
save('scope.json',dict(protected_source_files=len(protected),protected_source_mismatches=[],changed_infrastructure=source_rows,other_changes=[x for x in changes if x not in [z for z in changes if z['path'] in [r['path'] for r in source_rows]]]))
manifest=json.loads((M/'2026-09-22d/R3-测试写历史/restore_manifest.json').read_text())['files']
drift=json.loads((M/'2026-09-22d/R3-测试写历史/pre_day_hash_drift.json').read_text());journal=json.loads((M/'2026-09-22f/restore-journal.json').read_text())
restored=[]
for row in manifest:
    p=row['path'];actual=sha(ROOT/p);restored.append(dict(path=p,expected=row['expected_sha256'],actual=actual,passed=actual==row['expected_sha256']))
known='crates/kernel/evidence/round6/revision-r5/cli/分流器三路轮询-absolute.json';expected=next(x['before_sha256'] for x in drift if x['path']==known and not x['tracked'])
restored.append(dict(path='求解器/'+known,expected=expected,actual=sha(R/known),passed=sha(R/known)==expected))
early=[]
for row in json.loads((M/'2026-09-22/early-test-output-restoration.json').read_text()):
    early.append(dict(path=row['path'],expected=row['expected_sha256'],actual=sha(R/row['path']),passed=sha(R/row['path'])==row['expected_sha256']))
relocated=[]
for row in journal['relocated']:
    versions=[];prev=None
    for v in row['versions']:
        if 'dest' in v:prev=v
        actual=sha(ROOT/prev['dest']);versions.append(dict(commit=v['commit'],dest=prev['dest'],expected=prev['sha256'],actual=actual,passed=actual==prev['sha256']))
    relocated.append(dict(path=row['path'],absent=not (ROOT/row['path']).exists(),versions=versions))
before=json.loads((M/'2026-09-22/before.json').read_text())['files'];targets={r['path']:r for r in json.loads((M/'2026-09-22d/审查-opus/unresolved_targets.json').read_text())}
lost=[];markers={}
for row in drift:
    if row['tracked'] or row['path']==known:continue
    p=R/row['path'];marker=p.parent/'原字节缺失.json';d=json.loads(marker.read_text());markers[str(marker)]=d
    hits=[x for x in d['files'] if x['path']==row['path']];assert len(hits)==1;m=hits[0]
    original_size=before[row['path']]['bytes'];actual=sha(p);j=next(x for x in journal['untouched_lost'] if x['path']=='求解器/'+row['path'])
    passed=m['original_sha256']==row['before_sha256']==targets[row['path']]['before_sha256'] and m['original_bytes']==original_size==targets[row['path']]['before_bytes'] and m['current_sha256']==actual==j['current'] and m['current_bytes']==p.stat().st_size and m['disposition_path']==row['path'] and bool(d['search_basis']) and all((R/x).is_file() for x in d['search_basis'])
    lost.append(dict(path=row['path'],original_sha256=row['before_sha256'],original_bytes=original_size,current=actual,marker=str(marker),original_missing=actual!=row['before_sha256'],passed=passed))
assert all(r['passed'] for r in restored+early+lost) and all(r['absent'] and all(v['passed'] for v in r['versions']) for r in relocated)
assert sum(len(d['files']) for d in markers.values())==len(lost)
save('restoration.json',dict(passed=True,restored=restored,early=early,relocated=relocated,lost=lost,counts=dict(restored=len(restored),early=len(early),relocated=len(relocated),versions=sum(len(x['versions']) for x in relocated),missing_originals=len(lost),markers=len(markers)),provenance_limit='No Git access. Original digests from historical restoration manifest and journal; independently recomputed all current and archived bytes. Prior object-level audit retained unchanged.'))
old=ast.parse((seal/'crates/kernel/tests/revision_r3_cli.py').read_text());new=ast.parse((R/'crates/kernel/tests/revision_r3_cli.py').read_text())
old_assertions=[ast.dump(n.test) for n in ast.walk(old) if isinstance(n,ast.Assert)];new_assertions=[ast.dump(n.test) for n in ast.walk(new) if isinstance(n,ast.Assert)]
removed=[x for x in old_assertions if x not in new_assertions];assert not removed
save('r3-assertions.json',dict(old_assertions=len(old_assertions),new_assertions=len(new_assertions),removed=removed))
print('restoration',len(restored),len(early),len(relocated),len(lost),len(markers),'protected sources',len(protected),'R3 assertions',len(old_assertions),len(new_assertions))
