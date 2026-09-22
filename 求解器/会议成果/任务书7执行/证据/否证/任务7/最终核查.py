#!/usr/bin/env python3
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

E=Path(__file__).resolve().parent
B=E.parents[2]
report=B/'复核/否证-任务7.md'
text=report.read_text()
data=json.loads((E/'结构化结果.json').read_text())
assert set(data)=={'status','file','findings','summary'}
assert data['status']=='done' and data['file']==str(report)
assert isinstance(data['summary'],str)
extracted=[]
for block in re.findall(r'### F\d{2} .*?(?=\n### F\d{2} |\n## 4\.|\Z)',text,re.S):
    extracted.append({k:re.search(r'\*\*'+k+r'：\*\* (.+)',block).group(1) for k in ['target','verdict','reason']})
assert extracted==data['findings'] and len(extracted)==26
for f in data['findings']:
    assert set(f)=={'target','verdict','reason'}
    assert all(isinstance(v,str) and v for v in f.values())
    assert f['verdict'] in {'否证成立','否证不成立','无法判定'}
assert Counter(f['verdict'] for f in extracted)=={'否证不成立':22,'无法判定':4}
input_checks=[];parsed=[]
for manifest in ['输入指纹.json','引用输入指纹.json']:
    for row in json.loads((E/manifest).read_text()):
        p=Path(row['path']);raw=p.read_bytes();same=hashlib.sha256(raw).hexdigest()==row['sha256']
        assert same,(p,'input changed')
        input_checks.append(dict(path=str(p),sha256=row['sha256'],unchanged=same))
        if p.suffix=='.json':json.loads(raw);parsed.append(str(p))
        if p.suffix=='.py':ast.parse(raw)
missing=[];links=[]
for rel in re.findall(r'\]\(([^)]+)\)',text):
    p=(report.parent/rel).resolve()
    links.append(str(p))
    if not p.exists() and p != E/'最终核查.json':missing.append(rel)
assert not missing,missing
for p in E.iterdir():
    assert p.is_file() and p.suffix in {'.py','.json','.md','.log'}
    if p.suffix=='.json':json.loads(p.read_text());parsed.append(str(p))
    if p.suffix=='.py':ast.parse(p.read_text())
result=dict(status='pass',findings_schema_valid=True,report_findings_equal=True,findings_count=26,
            verdict_counts=dict(Counter(f['verdict'] for f in extracted)),input_checks=input_checks,
            all_inputs_unchanged=True,report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
            structured_result_sha256=hashlib.sha256((E/'结构化结果.json').read_bytes()).hexdigest(),
            link_count=len(links),missing_links=missing,json_parse_count=len(parsed),all_evidence_extensions_allowed=True,
            game_simulation_performed=False,kernel_build_or_execution=False,quota_error=False)
(E/'最终核查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
assert all(Path(p).exists() for p in links)
print(json.dumps({k:v for k,v in result.items() if k not in ['input_checks']},ensure_ascii=False))
