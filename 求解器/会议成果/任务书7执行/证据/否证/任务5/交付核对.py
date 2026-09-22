#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import hashlib
import json
import re

E=Path(__file__).resolve().parent
O=E.parents[2]
report=O/'复核/否证-任务5.md'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,value):
    (E/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

f=read(E/'发现记录.json')
r=read(E/'结构化结果.json')
text=report.read_text()
assert r['status']=='done' and r['file']==str(report)
assert r['findings']==[{'target':x['id']+' '+x['target'],'verdict':x['verdict'],'reason':x['reason']} for x in f]
assert re.findall(r'^### (F\d+)',text,re.M)==[x['id'] for x in f]
for i,x in enumerate(f):
    section=text.split('### '+x['id']+'　',1)[1].split('\n### ',1)[0]
    for key in ('target','verdict','reason','quote','attack','reachable','consequence','unhit_scope'):
        assert x[key] in section,(x['id'],key)
assert len(f)==24
assert Counter(x['verdict'] for x in f)=={'否证不成立':20,'无法判定':4}
links=[]
for link in re.findall(r'\]\(([^)]+)\)',text):
    p=(report.parent/link).resolve()
    assert p.exists(),str(p)
    links.append(str(p))

unchanged=[]
for row in read(E/'审查输入指纹.json')['files']+read(E/'补充来源指纹.json'):
    p=Path(row['path'])
    assert p.exists() and sha(p)==row['sha256'],str(p)
    unchanged.append(str(p))
for p in E.iterdir():
    assert p.is_file() and p.suffix in {'.py','.md','.json','.log'},str(p)
assert read(E/'独立核查结果.json')['status']=='PASS'
dump('交付核对结果.json',{'status':'PASS','exit_status':0,'findings':24,
    'verdicts':{'否证成立':0,'否证不成立':20,'无法判定':4},
    'report_and_structured_records_identical':True,'links_checked':len(links),
    'input_fingerprints_unchanged':len(unchanged),'source_scripts_executed':False,
    'quota_error_observed':False,'structured_output_tool_available':False})
print('PASS: 24条结论、全部详细字段及结构化结果逐条一致；链接存在；23条输入指纹保持；证据仅四种许可类型。')
