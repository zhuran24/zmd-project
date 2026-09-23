#!/usr/bin/env python3
"""Read-only final checks; write one audit record beside this script."""
from pathlib import Path
import hashlib
import json
import re

here=Path(__file__).resolve().parent
root=here.parents[3]
report=here.parent/'复核68.md'
manifest=json.loads((here/'input_manifest.json').read_text())
for name,old in manifest.items():
    data=(root/name).read_bytes()
    assert len(data)==old['bytes']
    assert hashlib.sha256(data).hexdigest()==old['sha256'],name
text=report.read_text()
links=re.findall(r'\]\(([^)]+)\)',text)
for target in links:
    assert (report.parent/target).is_file(),target
verdicts=json.loads((here/'verdicts.json').read_text())
names=['窄条矿物切线（修，第64轮）','矩形旁供电分组上限',
       '1113位置与桩数（条带补充）','十七位置的十一桩取等条件','条带全物料切线']
assert [v['name'] for v in verdicts]==names
assert all(set(v)=={'name','verdict','reason','revised_text'} for v in verdicts)
assert all(v['verdict']=='未否证' and v['revised_text']=='' and v['reason'] for v in verdicts)
assert all('| '+name+' | 未否证 |' in text for name in names)
results=json.loads((here/'results.json').read_text())
assert results['status']=='PASS'
assert results['power']['center_checks']==1047210
assert results['certificate_counts']=={'option_sets':3030,'frontiers':21,'adjacency_pairs':3451}
assert results['joint']['checked_frontiers']==32
assert results['cut_geometry_summary']['all_material_cut_count']==63
assert '正式空矩形上界仍为 1113' in text
assert len(re.findall(r'^    据：',(root/'求解约束.txt').read_text(),re.M))==72
areas={a*b for a in range(6,69) for b in range(a,69) if a*b<1113}
assert max(areas)==1110
artifacts={}
for p in [report]+sorted(here.iterdir()):
    if p.is_file() and p.name!='delivery_audit.json':
        artifacts[str(p.relative_to(report.parent))]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
audit={'status':'PASS','input_hashes_unchanged':True,'report_links_checked':len(links),
       'verdicts':len(verdicts),'formal_constraints':72,'next_integer_area_below_1113':1110,
       'artifacts':artifacts}
(here/'delivery_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in audit.items() if k!='artifacts'},ensure_ascii=False))
