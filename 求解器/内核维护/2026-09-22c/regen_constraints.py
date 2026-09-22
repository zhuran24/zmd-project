#!/usr/bin/env python3
"""求解约束增为 71 条后，从现行正式源重建目录的 constraints 投影；其余字段交 verify 核对。"""
from pathlib import Path
import json,sys
R=Path.cwd();sys.path.insert(0,str(R/'数据/工具'))
from formal_catalog import source_snapshot,formal_projection,verify
p=R/'数据/正式静态目录.json';d=json.loads(p.read_text())
d['sources']=source_snapshot();proj=formal_projection(d['sources'])
before=len(d['constraints']);d['constraints']=proj['constraints']
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
verify(json.loads(p.read_text()))
print(json.dumps({'constraints_before':before,'constraints_after':len(d['constraints']),'verify':'pass'},ensure_ascii=False))
