#!/usr/bin/env python3
"""Small independent geometric probes and deliberate invalid mutations."""
import copy,json,random
from static_check import BASE,read,audit,rectangle_rows,rectangle_columns_bitsets
from export_candidate import make
c=read(BASE/'逻辑接法.json');keep={'RF1','KF1','RF2','KF2'};c['machines']=[u for u in c['machines'] if u['id'] in keep];c['warehouse_outlets']=[]
poses={'RF1':dict(x0=0,y0=4,x1=2,y1=6,Din=2,kind='machine'),'KF1':dict(x0=10,y0=4,x1=12,y1=6,Din=2,kind='machine'),'RF2':dict(x0=4,y0=0,x1=6,y1=2,Din=3,kind='machine'),'KF2':dict(x0=4,y0=10,x1=6,y1=12,Din=3,kind='machine')}
results=[]
for adjacent in (False,True):
    ys=[4,5,6] if adjacent else [5];paths=[]
    for y in ys:paths.append(dict(id='LF'+str(len(paths)),source='RF1',target='KF1',item='蓝铁块',rate='1',start=[3,y,2],end=[9,y,0],cells=[[x,y] for x in range(3,10)]))
    paths.append(dict(id='LF'+str(len(paths)),source='RF2',target='KF2',item='蓝铁块',rate='1',start=[5,3,3],end=[5,9,1],cells=[[5,y] for y in range(3,10)]))
    c['logical_feeds']=[{k:p[k] for k in ('id','source','target','item','rate')} for p in paths]
    raw=dict(status='FEASIBLE',W=13,H=13,placements=poses,paths=paths);data=make(raw,c,True);r=audit(data,c,False)
    expected={'transport_units':25 if adjacent else 13,'transport_slots':28 if adjacent else 14,'bridges':3 if adjacent else 1,'adjacent_bridge_pairs':2 if adjacent else 0,'reverse_bridge_channels':2 if adjacent else 0}
    assert r['local_checks_pass'],r['checks'];assert all(r['statistics'][k]==v for k,v in expected.items())
    base='三桥相邻' if adjacent else '单桥交叉';(BASE/'实验'/f'{base}-非全厂.json').write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n');(BASE/'证据'/f'{base}-局部检查.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    mutations=[]
    for mode in ['delete_belt','wrong_axis','unlisted_channel']:
        broken=copy.deepcopy(data)
        if mode=='delete_belt':broken['layout']['transport']=[u for u in broken['layout']['transport'] if (u['x'],u['y'])!=(4,ys[0])]
        elif mode=='wrong_axis':
            u=next(u for u in broken['layout']['transport'] if u['type']=='bridge');u['H_in']=(u['H_in']+2)%4
        else:broken['design']['physical_channels'].pop()
        reject=audit(broken,c,False);assert not reject['local_checks_pass'];mutations.append(dict(mutation=mode,rejected=True,failed_checks=[k for k,v in reject['checks'].items() if v['status']=='FAIL']))
    results.append(dict(example=base,statistics=r['statistics'],expected=expected,mutations=mutations))
# Brute force every rectangle on small grids; two optimized implementations are
# compared against an independently enumerated coordinate quadruple oracle.
rng=random.Random(107);n=0
for W,H in [(6,6),(7,8),(9,7)]:
    for _ in range(20):
        occ={(x,y) for x in range(W) for y in range(H) if rng.random()<.15};best=(0,0)
        for x0 in range(W):
            for x1 in range(x0+1,W):
                for y0 in range(H):
                    for y1 in range(y0+1,H):
                        if all((x,y) not in occ for x in range(x0,x1+1) for y in range(y0,y1+1)):
                            w=x1-x0+1;h=y1-y0+1;best=max(best,(w*h,min(w,h)))
        for func in [rectangle_rows,rectangle_columns_bitsets]:
            r=func(occ,W,H,2)
            got=(r['area'],r['short_side']) if r else (0,0);assert got==best,(got,best)
        n+=1
(BASE/'证据/静态检查组件对照.json').write_text(json.dumps(dict(local_geometry=results,rectangle_bruteforce_cases=n,all_pass=True,not_a_full_factory=True),ensure_ascii=False,indent=2)+'\n');print('component checks pass',n)
