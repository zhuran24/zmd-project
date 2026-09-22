#!/usr/bin/python3
# 仅重定向原 CLI 测试的证据目录；断言与调用逻辑保持原样。
import os,sys
from pathlib import Path
args=sys.argv[1:]
script=next((a for a in args if a.endswith('.py')),None)
names={'revision_cli.py','revision_r2_cli.py','revision_r3_cli.py'}
if script and Path(script).name in names:
    path=Path(script).resolve()
    source=path.read_text()
    out=Path(__file__).resolve().parents[1]
    name=path.stem
    dest=out/name
    dest.mkdir(parents=True,exist_ok=True)
    replacements={"ROOT / 'crates/kernel/evidence/revision-r2'":repr(str(dest)),"ROOT / 'crates/kernel/evidence/revision-r3/cli'":repr(str(dest))}
    count=0
    for old,new in replacements.items():
        if old in source:
            source=source.replace(old,'Path('+new+')');count+=1
    assert count==1,(path,count)
    sys.argv=args[args.index(script):]
    sys.path.insert(0,str(path.parent))
    exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
else:
    os.execv('/usr/bin/python3',['/usr/bin/python3']+args)
