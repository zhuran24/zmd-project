#!/usr/bin/env python3
import hashlib, json, os, subprocess, sys
from pathlib import Path
ROOT=Path('/home/zhuran24/zmd-research-fresh')
OUT=Path(__file__).resolve().parent
ENV={**os.environ, 'GIT_OPTIONAL_LOCKS':'0'}
def git(*args):
 return subprocess.check_output(['git', *args],cwd=ROOT,env=ENV)
def snapshot():
 rows={}
 for name in git('ls-files','-z').decode().split('\0'):
  if not name: continue
  p=ROOT/name
  if p.is_symlink(): rows[name]={'symlink':os.readlink(p)}
  elif p.is_file():
   h=hashlib.sha256()
   with p.open('rb') as f:
    for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
   rows[name]={'sha256':h.hexdigest(),'size':p.stat().st_size}
  else: rows[name]={'missing':True}
 return {'head':git('rev-parse','HEAD').decode().strip(),'status':git('status','--porcelain=v1','--untracked-files=all').decode(),'files':rows}
mode=sys.argv[1]
s=snapshot()
(OUT/(mode+'.json')).write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
if mode=='before': print('baseline tracked files:',len(s['files']), 'HEAD:',s['head'])
else:
 b=json.loads((OUT/'before.json').read_text())
 changes=[p for p in sorted(b['files'].keys()|s['files'].keys()) if b['files'].get(p)!=s['files'].get(p)]
 result={'tracked_count_before':len(b['files']),'tracked_count_after':len(s['files']),'head_unchanged':b['head']==s['head'],'tracked_changes':changes,'status_after':s['status']}
 (OUT/'file-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='status_after'},ensure_ascii=False))
