"""包三安装：复用初始历史基线；备份包三前字节，不改前两包产物。"""
from pathlib import Path
import sys
from guard import OUT, ROOT, guard, save, digest
from work import write

def install(label):
    guard(label+'-write-before')
    rows=[]
    try:
        for p in sorted((OUT/'package3-staging').rglob('*')):
            if not p.is_file(): continue
            rel=p.relative_to(OUT/'package3-staging')
            dest=ROOT/rel
            if dest.exists() and dest.read_bytes()==p.read_bytes(): continue
            backup=OUT/'package3-before'/rel
            if dest.exists() and not backup.exists():
                backup.parent.mkdir(parents=True,exist_ok=True)
                backup.write_bytes(dest.read_bytes())
            old=digest(dest) if dest.exists() else None
            write(str(rel),p.read_bytes())
            rows.append({'path':str(rel),'before':old,'after':digest(dest)})
        save(label+'-writes.json',rows)
    finally: guard(label+'-write-after')
    print({'label':label,'written':len(rows)})
if __name__=='__main__': install(sys.argv[1])
