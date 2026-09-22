#!/usr/bin/env python3
"""Read-only Git evidence audit; writes only sibling JSON/Markdown/log files."""
import collections, hashlib, json, subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
SOLVER = REPO / '求解器'
COMMITS = ['7da52a7', 'a7539f5', '220f7b6']
BASE = 'f8f6129'

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), '-c', 'core.quotePath=false', *args])

def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')

def content(rev, path):
    p = subprocess.run(['git', '-C', str(REPO), 'show', f'{rev}:{path}'], capture_output=True)
    return p.stdout if p.returncode == 0 else None

def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None

def diffs(a,b,p=''):
    if type(a) != type(b): return [p]
    if isinstance(a,dict):
        return [p+'/'+k for k in a.keys()^b.keys()] + sum((diffs(a[k],b[k],p+'/'+k) for k in a.keys()&b.keys()),[])
    if isinstance(a,list):
        if len(a)!=len(b): return [p+'/#length']
        return sum((diffs(x,y,p+'/'+str(i)) for i,(x,y) in enumerate(zip(a,b))),[])
    return [p] if a!=b else []

all_changes={}
evidence={}
for c in COMMITS:
    parts=git('diff-tree','--no-commit-id','--name-status','-r','-z',c).decode().split('\0')
    changes=[{'status':parts[i], 'path':parts[i+1]} for i in range(0,len(parts)-1,2)]
    all_changes[c]=changes
    (OUT/f'{c}-names.log').write_text(''.join(f"{r['status']}\t{r['path']}\n" for r in changes))
    for row in changes:
        p=row['path']
        if '/evidence/' not in p and '/复核/' not in p and '/证据/' not in p and '/内核维护/' not in p and '参考运行记录' not in p: continue
        old,new=content(c+'^',p),content(c,p)
        entry=dict(row, commit=c, before_sha256=digest(old), after_sha256=digest(new))
        if old is not None and p.endswith('.json'):
            try:
                a,b=json.loads(old),json.loads(new)
                ds=diffs(a,b)
                entry.update(json_diff_count=len(ds),json_diff_paths=sorted(ds),old_status=a.get('status') if isinstance(a,dict) else None,new_status=b.get('status') if isinstance(b,dict) else None)
            except (ValueError,TypeError): pass
        evidence.setdefault(p,[]).append(entry)
rows=[]
for p,changes in sorted(evidence.items()):
    base,pre,head=content(BASE,p),content('7da52a7',p),content('HEAD',p)
    history=git('log','--format=%h %s',BASE+'..HEAD','--',p).decode().splitlines()
    rows.append(dict(path=p,base_sha256=digest(base),pre_relock_b_sha256=digest(pre),head_sha256=digest(head),base_equals_pre=base is not None and base==pre,history=history,changes=changes))
save('all_commit_changes.json',all_changes)
save('file_audit.json',rows)
summary={c:dict(total_paths=len(all_changes[c]),kernel_evidence=collections.Counter(r['status'] for r in all_changes[c] if '/crates/kernel/evidence/' in r['path']),other_historical=[r for r in all_changes[c] if '/复核/' in r['path'] or '/证据/' in r['path']],maintenance=collections.Counter(r['status'] for r in all_changes[c] if '/内核维护/' in r['path'])) for c in COMMITS}
summary['head']=git('rev-parse','HEAD').decode().strip()
summary['unique_kernel_evidence']=sum('/crates/kernel/evidence/' in r['path'] for r in rows)
save('git_summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
