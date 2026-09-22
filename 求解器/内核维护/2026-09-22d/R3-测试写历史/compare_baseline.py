#!/usr/bin/env python3
import hashlib,json,subprocess,collections
from pathlib import Path
OUT=Path(__file__).resolve().parent; ROOT=OUT.parents[2]
baseline=json.loads((ROOT/'内核维护/2026-09-22/before.json').read_text())['files']
tracked=set(subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z']).decode().split('\0'))
rows=[]
for p,old in baseline.items():
    if not p.startswith(('crates/kernel/evidence/','crates/kernel/复核/','数据/复核/','规格/复核/')): continue
    file=ROOT/p
    new=hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None
    if new!=old['sha256']:
        matches=[]
        if p not in tracked:
            for candidate,info in baseline.items():
                f=ROOT/candidate
                if info['sha256']==old['sha256'] and f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest()==old['sha256']:
                    matches.append(candidate)
        rows.append(dict(path=p,tracked=p in tracked,before_sha256=old['sha256'],after_sha256=new,bytes=file.stat().st_size if file.exists() else None,existing_exact_copy_candidates=matches))
(OUT/'pre_day_hash_drift.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print('Historical paths differing from pre-day baseline:',len(rows))
print('Tracked:',sum(r['tracked'] for r in rows),'Untracked:',sum(not r['tracked'] for r in rows))
for r in rows:
    if not r['tracked']: print(r['path'],r['before_sha256'],r['after_sha256'])
restored=json.loads((ROOT/'内核维护/2026-09-22/early-test-output-restoration.json').read_text())
for r in restored:
    actual=hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()
    r.update(actual_sha256=actual,still_matches=actual==r['expected_sha256'])
(OUT/'restoration_verified.json').write_text(json.dumps(restored,ensure_ascii=False,indent=2)+'\n')
print('Three restored files still match:',all(r['still_matches'] for r in restored))
