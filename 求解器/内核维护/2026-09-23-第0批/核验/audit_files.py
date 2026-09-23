#!/usr/bin/env python3
"""Independent, read-only file inventory. Writes only in this audit directory."""
import datetime, hashlib, json, os, stat, sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
IMPL=OUT.parent
ROOT=IMPL.parents[2]

def sha(p):
 with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def save(name,d): (OUT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def scan(root, excludes):
 rows={}; errors=[]
 def visit(p):
  rel=p.relative_to(root).as_posix()
  if any(rel==e or rel.startswith(e+'/') for e in excludes): return
  try:
   s=p.lstat(); row={'mode':stat.S_IMODE(s.st_mode)}
   if stat.S_ISLNK(s.st_mode): row.update(kind='symlink',target=os.readlink(p),size=s.st_size)
   elif stat.S_ISDIR(s.st_mode):
    row['kind']='directory'
    with os.scandir(p) as it: children=sorted(x.name for x in it)
    for name in children: visit(p/name)
   elif stat.S_ISREG(s.st_mode):
    row.update(kind='file',size=s.st_size,sha256=sha(p))
    s2=p.lstat()
    if (s.st_ino,s.st_size,s.st_mtime_ns)!=(s2.st_ino,s2.st_size,s2.st_mtime_ns): errors.append({'path':rel,'error':'changed while hashing'})
   else: row['kind']='special'
   rows[rel]=row
  except OSError as e: errors.append({'path':rel,'error':str(e)})
 visit(root)
 return {'root':str(root),'excludes':excludes,'entries':rows,'errors':errors,'at':datetime.datetime.now().astimezone().isoformat()}
def diff(a,b):
 return [{'path':p,'before':a.get(p),'after':b.get(p)} for p in sorted(a.keys()|b.keys()) if a.get(p)!=b.get(p)]
def main(label):
 base=json.loads((IMPL/'initial-protection.json').read_text())
 # Unlike the implementation, include all implementation records. Only our new audit root is excluded.
 excludes=[x for x in base['excludes'] if x!=str(IMPL.relative_to(ROOT))]+[str(OUT.relative_to(ROOT))]
 now=scan(ROOT,excludes);save(label+'-snapshot.json',now)
 scope=str(IMPL.relative_to(ROOT))
 against_impl=diff(base['entries'],{p:r for p,r in now['entries'].items() if not(p==scope or p.startswith(scope+'/'))})
 save(label+'-vs-implementation-start.json',against_impl)
 history_roots=['求解器/crates/kernel/evidence','求解器/crates/kernel/复核','求解器/数据/复核','求解器/规格/复核']
 history=[d for d in against_impl if any(d['path']==r or d['path'].startswith(r+'/') for r in history_roots)]
 old_maintenance=[d for d in against_impl if d['path'].startswith('求解器/内核维护/')]
 save(label+'-history.json',{'history_roots':history_roots,'history_changes':history,'old_maintenance_changes':old_maintenance,'coverage':[{'root':r,'entries':sum(p==r or p.startswith(r+'/') for p in now['entries']),'files':sum(v['kind']=='file' and (p==r or p.startswith(r+'/')) for p,v in now['entries'].items())} for r in history_roots]})
 audit_delta=None
 if label!='start':
  audit_delta=diff(json.loads((OUT/'start-snapshot.json').read_text())['entries'],now['entries']);save(label+'-vs-audit-start.json',audit_delta)
 print(json.dumps({'label':label,'entries':len(now['entries']),'files':sum(v['kind']=='file' for v in now['entries'].values()),'errors':now['errors'],'implementation_delta':len(against_impl),'history_changes':len(history),'old_maintenance_changes':len(old_maintenance),'audit_delta':None if audit_delta is None else len(audit_delta)},ensure_ascii=False))
if __name__=='__main__':main(sys.argv[1])
