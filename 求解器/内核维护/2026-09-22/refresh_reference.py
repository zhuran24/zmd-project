#!/usr/bin/env python3
"""独立Python重算参考记录；物理轨迹和手工黄金摘要必须与旧记录一致。"""
import json,sys,copy,hashlib
from pathlib import Path
R=Path.cwd();O=R/'内核维护/2026-09-22';sys.path.insert(0,str(R/'数据/样例'))
import check_golden_trace as g
from runtime_record import build_record,validate_record
rows=[]
for n in ['混做粉碎机两下游','分流器三路轮询']:
 p=g.BASE/(n+'-运行记录-v3.json');old=json.loads(p.read_text());data=json.loads((g.BASE/(n+'.json')).read_text());ticks=g.run(data)
 def physical(ticks):
  ticks=copy.deepcopy(ticks)
  for t in ticks:
   t['state']['semantic_context'].pop('parameter_values')
   t['closure'].pop('basis')
  return ticks
 assert physical(ticks)==physical(old['trace']['ticks']),n
 golden=json.loads(g.GOLDEN.read_text()) if n.startswith('混做') else None
 record=build_record(data,ticks,golden);validate_record(record,data,ticks)
 before=hashlib.sha256(p.read_bytes()).hexdigest();p=g.BASE/(n+'-参考运行记录.json');p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 rows.append({'file':str(p.relative_to(R)),'before':before,'after':hashlib.sha256(p.read_bytes()).hexdigest(),'ticks':len(ticks),'physical_trace_unchanged':True,'hand_golden_unchanged':golden is not None})
(O/'reference-refresh.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(rows)
