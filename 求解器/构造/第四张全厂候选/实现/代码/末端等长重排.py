#!/usr/bin/env python3
"""交换同机型机位的逻辑身份，使已接成的两条1格进路成为H6/Q6到F4。

接法仍取原325条；重命名后不属于接法的旧进路全部显式删除。
"""
import json,sys
from pathlib import Path
from collections import defaultdict,deque
B=Path(__file__).resolve().parents[1];raw=json.loads(Path(sys.argv[1]).read_text());c=json.loads((B/'逻辑接法.json').read_text());es=c['logical_feeds']
pairs=[('H4','H6'),('F2','F4'),('Q4','Q6'),('B13','B17'),('R13','R17')]
pairs += [(f'{p}4',f'{p}6') for p in ['QA','QB','QC','QK']]
pairs += [(f'{p}{a}',f'{p}{z}') for p in ['RF','KF','WFE'] for a,z in [(25,33),(26,34)]]
rename={a:z for a,z in pairs}|{z:a for a,z in pairs}
lookup=defaultdict(deque)
for k,e in enumerate(es):lookup[e['source'],e['target'],e['item']].append(k)
uu={rename.get(u['id'],u['id']):dict(u,id=rename.get(u['id'],u['id'])) for u in raw['units']}
kept=[];dropped=[]
for p in raw['paths']:
    if not p['cells']:continue
    e=es[p['r']];a,z=rename.get(e['source'],e['source']),rename.get(e['target'],e['target']);key=a,z,e['item']
    if lookup[key]:kept.append(dict(p,r=lookup[key].popleft()))
    else:dropped.append(dict(previous_route=e['id'],source_after=a,target_after=z,item=e['item'],reason='重排后源汇不属于固定接法或超过指定重数'))
lines=(B/'实验/改规划4初值.txt').read_text().splitlines();n,ne,nr=map(int,lines[0].split());order=[a.split()[0] for a in lines[1:n+1]];units=[uu[k] for k in order]
paths={p['r']:p for p in kept};equal=[next(k for k,e in enumerate(es) if e['source']==u and e['target']=='F4') for u in ['H6','Q6']]
assert all(k in paths for k in equal), '所选两条末端进路不完整'
assert len(paths[equal[0]]['cells'])==len(paths[equal[1]]['cells']), '两条末端进路不等长'
out=B/'实验/等长重排初值';d=dict(raw,units=units,paths=kept,power_distance=0)
out.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=1))
out.with_suffix('.pos').write_text(''.join(f"{u['x']} {u['y']} {u['d']}\n" for u in units))
with out.with_suffix('.routes').open('w') as f:
    print(len(kept),file=f)
    for p in kept:
        print(p['r'],len(p['cells']),file=f)
        for x,y,*_ in p['cells']:print(x,y,file=f)
reserved={tuple(map(int,a.split())) for a in lines[n+ne+1:]}|{tuple(q[:2]) for k in equal for q in paths[k]['cells']}
with (B/'实验/改规划5初值.txt').open('w') as f:
    print(n,ne,len(reserved),file=f)
    for line,u in zip(lines[1:n+1],units):
        flag=int(line.split()[-1]) or u['id'] in ['H6','Q6','F4']
        print(u['id'],u['type'],u['x'],u['y'],u['d'],int(flag),file=f)
    for line in lines[n+1:n+ne+1]:print(line,file=f)
    for x,y in sorted(reserved):print(x,y,file=f)
pl=(B/'实验/保护进路4.txt').read_text().splitlines();pl[0]=str(int(pl[0])+2)
with (B/'实验/保护进路5.txt').open('w') as f:
    print('\n'.join(pl),file=f)
    for k in equal:
        p=paths[k];print(k,len(p['cells']),file=f)
        for x,y,*_ in p['cells']:print(x,y,file=f)
info=dict(mapping=rename,old_routes=sum(bool(p['cells']) for p in raw['paths']),retained_routes=len(kept),deleted=dropped,equal_lengths=[len(paths[k]['cells']) for k in equal])
(B/'证据/末端等长重排.json').write_text(json.dumps(info,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in info.items() if k not in ['mapping','deleted']},ensure_ascii=False))
