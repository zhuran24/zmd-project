#!/usr/bin/env python3
"""将粗坐标转为整厂联合调整的初值；硬固定已有四个模块和矿口。"""
import json,random,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
c=json.loads((BASE/'逻辑接法.json').read_text())
p=json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv)>1 else json.loads((BASE/'依据快照/粗坐标.json').read_text())
sp={m['id']:m for m in c['machines']}
poses={m['id']:(m['x0'],m['y0'],m['Din'],1) for m in p['machines']}
# 已定模块的矿口 id 来自逐路起点；其余按规划的角区和端区顺序分配。
out={}
for r in p['routes_fixed']:
    if r['source'] and (r['source'].startswith('WFE') or r['source'].startswith('WO')):
        x,y=r['cells'][0]
        out[r['source']]=(x-1,0,1,1) if y==1 else (0,y-1,0,1)
corner=[int(u[2:]) for u in next(iter(p['blocks'].values())) if u.startswith('RF')]
for idx,k in enumerate(corner):
    if idx<6:out[f'WFE{k}']=(1+3*idx,0,1,1)
    else:out[f'WFE{k}']=(0,1+3*(idx-6),0,1)
for k,slot in zip([int(u[2:]) for u in list(p['blocks'].values())[1] if u.startswith('RF')],range(18,23)):out[f'WFE{k}']=(1+3*slot,0,1,1)
for k,slot in zip([int(u[2:]) for u in list(p['blocks'].values())[2] if u.startswith('RF')],range(18,23)):out[f'WFE{k}']=(0,1+3*slot,0,1)
assert len(out)==46
rng=random.Random(19)
regions=[(1,1,18,18),(55,2,69,18),(2,55,18,69),(37,10,56,23),(10,37,23,54),(35,19,58,40),(19,19,38,39),(19,37,69,69)]
for (name,ids),(x0,y0,x1,y1) in zip(p['blocks'].items(),regions):
    for uid in ids:
        k=sp[uid]['kind'];w,h=(3,3) if k=='小' else (5,5) if k=='中' else (6,4)
        poses[uid]=(rng.randint(x0,x1-w+1),rng.randint(y0,y1-h+1),3,0)
# 采种回路使用已核过的双单元骨架作为初值，后续允许随布线挪动。
names=[('S',k) for k in range(1,14)]+[('Q',k) for k in range(1,7)]
pair=[(0,'B',0,10,1),(0,'A',6,6,2),(0,'C',6,11,0),(1,'C',1,0,2),(1,'A',1,5,0),(1,'B',7,1,3)]
for z in range(8):
    ox,oy=18+13*(z%4),38+16*(z//4)
    for wh,role,x,y,d in pair:
        typ,k=names[2*z+wh];poses[f'{typ}{role}{k}']=(ox+x,oy+y,d,0)
for z,(typ,k) in enumerate(names[16:]):
    for a,role in enumerate(['C','A','B']):poses[f'{typ}{role}{k}']=(55+5*z,20+6*a,[3,1,3][a],0)
poses['CORE']=(43,26,0,0)
poses.update(out)
for i,q in enumerate(p['power_stalls'][:8]):poses[f'POWER{i}']=(q['x0'],q['y0'],0,1)
# 留够供电桩的位置参与摆放，数量可在后续覆盖求解时减少。
for i in range(8,26):
    j=i-8;poses[f'POWER{i}']=(8+12*(j%5),17+12*(j//5),0,0)
for i,q in enumerate(p['power_stalls'][8:],26):poses[f'POWER{i}']=(q['x0'],q['y0'],0,1)
units=[(m['id'],{'小':0,'中':1,'大':2}[m['kind']]) for m in c['machines']]+[('CORE',3)]+[(u['id'],4) for u in c['warehouse_outlets']]+[(f'POWER{i}',5) for i in range(26+max(0,len(p['power_stalls'])-8))]
idx={u:i for i,(u,t) in enumerate(units)}
fixedcells=sorted({tuple(xy) for r in p['routes_fixed'] for xy in r['cells']})
with (Path(sys.argv[2]) if len(sys.argv)>2 else BASE/'实验/规划初值.txt').open('w') as f:
    print(len(units),len(c['logical_feeds']),len(fixedcells),file=f)
    for u,t in units:print(u,t,*poses[u],file=f)
    for e in c['logical_feeds']:print(idx[e['source']],idx[e['target']],file=f)
    for x,y in fixedcells:print(x,y,file=f)
(BASE/'实验/初值身份.json').write_text(json.dumps(dict(units=units,poses=poses),ensure_ascii=False,indent=1))
print('已写入',len(units),'个非运输单位及',len(fixedcells),'个模块运输预留格')
