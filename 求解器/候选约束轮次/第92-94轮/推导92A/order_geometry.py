#!/usr/bin/env python3
import json,pathlib
first=[(x,10) for x in range(1,5)]+[(4,y) for y in range(11,15)]+[(x,14) for x in range(5,9)]+[(8,y) for y in range(13,9,-1)]
second=[(x,2) for x in range(1,12)]+[(11,y) for y in range(3,8)]
units={'仓库取货口甲':[(0,y) for y in range(9,12)],'仓库取货口乙':[(0,y) for y in range(1,4)],'长带甲':first,'长带乙':second,'准入口甲':[(9,10)],'准入口乙':[(11,8)],'分流器':[(10,10)],'未设条件准入口':[(11,9)],'汇流器甲':[(11,10)],'汇流器乙':[(10,11)],'回库带甲':[(12,10)],'回库带乙':[(11,11),(12,11)],'协议核心':[(x,y) for x in range(13,22) for y in range(9,18)]}
occupied={}
for name,cells in units.items():
    for cell in cells:
        assert cell not in occupied,(cell,name,occupied.get(cell))
        assert all(0<=v<70 for v in cell)
        occupied[cell]=name
for belt in [first,second,units['回库带乙']]:
    assert all(abs(a[0]-b[0])+abs(a[1]-b[1])==1 for a,b in zip(belt,belt[1:]))
assert len(first)==len(second)==16
edges=[((0,10),first[0]),((0,2),second[0]),(first[-1],(9,10)),(second[-1],(11,8)),((9,10),(10,10)),((11,8),(11,9)),((11,9),(11,10)),((10,10),(11,10)),((10,10),(10,11)),((11,10),(12,10)),((10,11),(11,11)),((12,10),(13,10)),((12,11),(13,11))]
assert all(abs(a[0]-b[0])+abs(a[1]-b[1])==1 for a,b in edges)
assert all(2<=y-9+1<=8 for x,y in [(13,10),(13,11)])
# Derive formation times from actual endpoint construction, independently of sim2.
reference=json.loads(pathlib.Path(__file__).with_name('order_reference.json').read_text())
blueprints=[]
for row in reference:
    times={}
    for n,base in [('协议核心',-3),('仓库取货口甲',-2),('仓库取货口乙',-1)]:
        times.update({cell:base for cell in units[n]})
    for n,key in [('汇流器甲','汇流器'),('汇流器乙','分流另一支'),('分流器','分流器'),('未设条件准入口','另一上游')]:
        times[units[n][0]]=row['special_build_order'][key]
    times[(9,10)]=5;times[(11,8)]=6;times[(12,10)]=100
    times[(11,11)]=101;times[(12,11)]=102
    times.update({cell:110+i for i,cell in enumerate(first)})
    times.update({cell:130+i for i,cell in enumerate(second)})
    nonbelt=[p for n,ps in units.items() if n not in ['长带甲','长带乙','回库带甲','回库带乙'] for p in ps]
    belt=[p for n in ['长带甲','长带乙','回库带甲','回库带乙'] for p in units[n]]
    assert max(times[p] for p in nonbelt)<min(times[p] for p in belt)
    named_edges=['仓库取货口甲→上游带甲','仓库取货口乙→上游带乙','上游带甲→准入口甲','上游带乙→准入口乙','准入口甲→分流器','准入口乙→另一上游','另一上游→汇流器','分流器→汇流器','分流器→分流另一支','汇流器→汇流后带','分流另一支→另一支后带','汇流后带→协议核心','另一支后带→协议核心']
    derived={n:max(times[a],times[b]) for n,(a,b) in zip(named_edges,edges)}
    assert derived==row['channel_formation_times']
    blueprints.append({'first':row['early'],'channel_formation_times':derived})
result={'verified':True,'blueprints_compatible':True,'long_belt_lengths':[len(first),len(second)],'occupied_cells':len(occupied),'units':units,'external_edges':edges,'blueprints':blueprints}
pathlib.Path(__file__).with_name('order_geometry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['units','external_edges','blueprints']},ensure_ascii=False))
