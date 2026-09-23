import difflib,hashlib,json
from pathlib import Path
from audit_files import ROOT,OUT,IMPL,save,sha
from read_objects import obj,index,commit,head
initial=json.loads((IMPL/'initial-protection.json').read_text())['entries']
baseline,_,base=commit('aec2a30d945e21a492d4b05639d67a63abacb5b3')
idx=index();current_head=head();_,_,headtree=commit(current_head)
changes=json.loads((OUT/'start-vs-implementation-start.json').read_text())
active=[d for d in changes if not d['path'].startswith('求解器/候选约束轮次/第63-65轮/')]
patch=[];rows=[]
for d in active:
 p=d['path']
 if d['after'] and d['after']['kind']=='directory':continue
 before=obj(base[p]['oid'])[1] if p in base else b''
 after=(ROOT/p).read_bytes() if (ROOT/p).is_file() else b''
 index_bytes=obj(idx[p]['oid'])[1] if p in idx else None
 rows.append({'path':p,'baseline_sha256':hashlib.sha256(before).hexdigest() if p in base else None,'initial_sha256':initial.get(p,{}).get('sha256'),'current_sha256':hashlib.sha256(after).hexdigest(),'index_matches_baseline':index_bytes==before if p in idx else p not in base,'head_matches_index':headtree.get(p)==idx.get(p),'initial_matches_baseline':initial.get(p,{}).get('sha256')==(hashlib.sha256(before).hexdigest() if p in base else None)})
 patch.extend(difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),fromfile='a/'+p,tofile='b/'+p))
(OUT/'workspace-changes.diff').write_text(''.join(patch))
staged=[p for p in sorted(idx.keys()|headtree.keys()) if idx.get(p)!=headtree.get(p)]
head_since=[p for p in sorted(base.keys()|headtree.keys()) if base.get(p)!=headtree.get(p)]
protected=[p for p in initial if p.startswith(('求解器/crates/kernel/src/','求解器/crates/topology/src/')) or p in ['求解器/crates/kernel/tests/verify_all.py','求解器/crates/kernel/tests/audit_task7.py'] or p.startswith('求解器/数据/样例/') and p.endswith('.py')]
current=json.loads((OUT/'start-snapshot.json').read_text())['entries']
production_mismatch=[p for p in protected if initial[p]!=current.get(p)]
freeze=json.loads((IMPL/'freeze.json').read_text()); frozen=Path(freeze['root']); frozen_rows=[]
for r in freeze['files']:
 p=frozen/r['path'];frozen_rows.append({'path':r['path'],'expected':r['sha256'],'actual':sha(p) if p.is_file() else None,'size':p.stat().st_size if p.is_file() else None,'symlink':any(q.is_symlink() for q in [p,*p.parents])})
save('source-diff.json',{'method':'Python read-only Git index and hash-verified object decoding; no Git commands','baseline':baseline,'head':current_head,'active_changed_files':rows,'staged_paths':staged,'head_changes_since_implementation_start':head_since,'protected_source_count':len(protected),'protected_source_mismatches':production_mismatch})
save('freeze-readback.json',{'files':frozen_rows,'count':len(frozen_rows),'mismatches':[r for r in frozen_rows if r['actual']!=r['expected'] or r['symlink']],'unlisted_files':[str(p.relative_to(frozen)) for p in frozen.rglob('*') if p.is_file() and str(p.relative_to(frozen)) not in {r['path'] for r in frozen_rows}]})
print(json.dumps({'active_changed_files':len(rows),'staged':len(staged),'initial_baseline_mismatches':sum(not r['initial_matches_baseline'] for r in rows),'production_mismatches':production_mismatch,'freeze_count':len(frozen_rows),'freeze_mismatches':sum(r['actual']!=r['expected'] or r['symlink'] for r in frozen_rows),'head_changes':len(head_since)},ensure_ascii=False))
