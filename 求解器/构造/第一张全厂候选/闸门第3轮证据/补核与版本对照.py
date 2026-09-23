#!/usr/bin/env python3
"""按历史证据哈希核对变更；齐次守恒消元只是辅助证据，不替代LP证书。"""
from pathlib import Path
import json,hashlib
from fractions import Fraction as Q
E=Path(__file__).resolve().parent;B=E.parent
read=lambda p:json.loads(p.read_text())
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda n,d:(E/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
out={}
for num in [1,2]:
    p=B/f'闸门第{num}轮证据';old=read(p/'候选只读快照.json');new=read(E/'候选只读快照.json')
    diff={'candidate_sha256':h(p/'候选只读快照.json'),'different_from_current':h(p/'候选只读快照.json')!=h(E/'候选只读快照.json'),'groups':{}}
    for group in ['machines','warehouse_outlets','power_poles','storage_boxes','transport']:
        x={u['id']:u for u in old['layout'][group]};y={u['id']:u for u in new['layout'][group]}
        diff['groups'][group]={'before':len(x),'current':len(y),'added':sorted(y.keys()-x.keys()),'removed':sorted(x.keys()-y.keys()),'modified':sorted(k for k in x.keys()&y.keys() if x[k]!=y[k])}
    diff['core_changed']=old['layout']['core']!=new['layout']['core']
    diff['channels']={'before':len(old['design']['physical_channels']),'current':len(new['design']['physical_channels'])}
    for name,file,key in [('A','A原始.json' if num==1 else 'A初次.json','implementation_sha256'),('B','B原始.json' if num==1 else 'B初次.json','checker_files_sha256')]:
        hashes=read(p/file)[key]
        diff['checker'+name]={'report':file,'changed_production_files':[n for n,s in hashes.items() if h(E/('检查器'+name)/n)!=s]}
    out[str(num)]=diff
write('历轮字节与候选差异.json',out)
m=read(E/'独立LP矩阵.json');zero=set();steps=[];layers=[]
while True:
    before=len(zero)
    for r in m['rows']:
        if r['relation']!='eq' or Q(r['rhs'])!=0:continue
        left=[(j,Q(v)) for j,v in r['terms'] if j not in zero]
        if left and (all(v>0 for j,v in left) or all(v<0 for j,v in left)):
            newly=[j for j,v in left];zero.update(newly);steps.append({'row':r['name'],'new_zero_columns':newly})
    layers.append(len(zero)-before)
    if len(zero)==before:break
write('齐次守恒零流证书.json',{'matrix_sha256':h(E/'独立LP矩阵.json'),'variables':len(m['variables']),'forced_zero':len(zero),'all_zero':len(zero)==len(m['variables']),'new_zero_counts_per_scan':layers,'steps':steps,'remaining':[m['variables'][j] for j in range(len(m['variables'])) if j not in zero]})
print(json.dumps({'historical_rounds_compared':2,'homogeneous_elimination_forced_zero':len(zero),'total_variables':len(m['variables']),'note':'剩余变量由独立对偶证书判定；本消元不单独声称全部为零。'},ensure_ascii=False))
