"""同一种物品的不同入格年龄只改变表示分组，不产生普通格混种。"""
from pathlib import Path
import json,copy,subprocess
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent
raw=json.loads((OUT/'branch-control-input.json').read_text())
def tm(t):return {'kind':'rational','value':{'value':str(t),'category':'候选'}}
def content(n,t):return dict(item='高容谷地电池',quantity={'value':str(n),'category':'候选'},entered_at=tm(t))
reports=[]
for name,contents in [('one-age',[content(2,-2)]),('two-ages',[content(1,-2),content(1,-1)])]:
 data=copy.deepcopy(raw);r=next(r for r in data['initial_state']['nonwarehouse']['value']['inventory'] if r['slot']=='south_box:storage:0');r['contents']=contents
 p=OUT/(name+'-input.json');p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');dest=OUT/(name+'-result.json')
 cmd=[str(ROOT/'target/release/kernel'),'seed',str(p),'--config',str(ROOT/'规格/内核配置-v1.json'),'--out',str(dest)]
 proc=subprocess.run(cmd,capture_output=True,text=True);result=json.loads(dest.read_text())
 reports.append(dict(case=name,command=cmd,exit_code=proc.returncode,status=result.get('status',result['schema']),open_items=result.get('open_items'),contents=contents))
assert reports[0]['exit_code']==0 and reports[1]['status']=='invalid_input'
(OUT/'age-cohort-results.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n');print(json.dumps(reports,ensure_ascii=False,indent=2))
