from probe_common import *
import sys
REPO=ROOT.parent
EXCLUDED={'target','.git','.codegraph','.cargo-home','__pycache__','.pytest_cache','node_modules'}
def inventory():
 rows={}
 for directory,dirs,files in os.walk(REPO):
  dirs[:]=[d for d in dirs if d not in EXCLUDED and not (Path(directory)/d).is_symlink() and Path(directory)/d!=OUT]
  for f in files:
   p=Path(directory)/f
   if p==OUT.parent/'R2-来源与计时.md':continue
   if p.is_symlink():rows[str(p.relative_to(REPO))]={'symlink':os.readlink(p)}
   elif p.is_file():rows[str(p.relative_to(REPO))]={'bytes':p.stat().st_size,'sha256':sha(p)}
 return rows
mode=sys.argv[1];rows=inventory();dump(OUT/f'protected-{mode}.json',rows)
if mode=='after':
 before=json.loads((OUT/'protected-before.json').read_text()); delta=changes(before,rows)
 dump(OUT/'protected-diff.json',delta);print(json.dumps({'files_before':len(before),'files_after':len(rows),'differences':len(delta)},ensure_ascii=False))
else:print('protected files',len(rows))
run('git-'+mode,['git','-c','core.quotePath=false','status','--short','--untracked-files=all'])
