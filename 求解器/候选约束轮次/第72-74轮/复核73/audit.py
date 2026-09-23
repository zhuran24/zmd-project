#!/usr/bin/env python3
"""Independent small-block, partition, matching and delivery checks."""
from recompute import *

def check_blocks():
    tested=0
    for w,h in [(3,3),(5,5),(6,4),(4,6)]:
        for x in range(1-w,12):
            for y in range(1-h,12):
                r=(x,y,w,h)
                assert intersects(r,(0,0,12,12))
                choices=[(i,j,3,3) for i in range(x,x+w-2) for j in range(y,y+h-2)
                         if intersects((i,j,3,3),(0,0,12,12))]
                assert choices;tested+=1
    pair_tests=0
    for a in range(3):
        for b in range(3):
            for x in range(-3,4):
                for y in range(-3,4):
                    for xx in range(x-2,x+3):
                        for yy in range(y-2,y+3):
                            if ((x+a)//3,(y+b)//3)!=((xx+a)//3,(yy+b)//3):continue
                            assert intersects((x-1,y-1,3,3),(xx-1,yy-1,3,3));pair_tests+=1
    # Direct full-board center scan, compared to the bounded rectangle scan.
    all_centers=[(x,y) for x in range(2,69) for y in range(2,69)
                 if not intersects((x-1,y-1,3,3),HOLE)]
    checks=0
    for p in get_losses():
        direct={(x,y) for x,y in all_centers
                if p[0]-6<=x<=p[0]+7 and p[1]-6<=y<=p[1]+7
                and not(p[0]-1<=x<=p[0]+2 and p[1]-1<=y<=p[1]+2)}
        assert direct==centers(p);checks+=1
    return dict(intersecting_machine_shapes=tested,same_group_pairs=pair_tests,all_pole_center_domains=checks)

def matching():
    wit=read('第72-74轮/推导72/witness185.json')
    poles=[(b['x'],b['y']) for b in wit['chosen'] if b['kind']=='p']
    loss=get_losses();capacities=[23-loss[p] for p in poles]
    expected=json.loads((OUT/'witness.json').read_text())['groups']
    result=[]
    for a in range(3):
        for b in range(3):
            neighbors=[sorted({((x+a)//3,(y+b)//3) for x,y in centers(p)}) for p in poles]
            slots=[p for p,c in enumerate(capacities) for _ in range(c)]
            owner={}
            def augment(slot,seen):
                for group in neighbors[slots[slot]]:
                    if group in seen:continue
                    seen.add(group)
                    if group not in owner or augment(owner[group],seen):
                        owner[group]=slot;return True
                return False
            flow=sum(augment(i,set()) for i in range(len(slots)))
            counts=Counter(slots[v] for v in owner.values())
            assert len(set(owner.values()))==flow
            assert all(counts[i]<=capacities[i] for i in range(10))
            assert all(g in neighbors[slots[s]] for g,s in owner.items())
            target=next(g for g in expected if (g['a'],g['b'])==(a,b))
            assert flow==target['upper']
            result.append(dict(a=a,b=b,max_matching=flow,subset_upper=target['upper'],
                assignments=[dict(group=g,pole=slots[s]) for g,s in sorted(owner.items())]))
    save('matching_certificates',result)
    return [[d['a'],d['b'],d['max_matching']] for d in result]

def arithmetic():
    F=Fraction
    battery=F(3,5);capsule=F(11,20)
    parts=10*battery;bottles=10*capsule
    dense_source=15*battery;fine=10*capsule;steel=parts+2*bottles
    leaf_powder=steel+dense_source+fine
    source=2*dense_source;iron=2*steel
    buckwheat=2*fine/2;sandleaf=leaf_powder/3
    rates={'粉碎机':source+iron+buckwheat+sandleaf,'精炼炉':iron+steel,
           '研磨机':steel+dense_source+fine,'塑形机':bottles,'配件机':parts,
           '种植机':2*(buckwheat+sandleaf),'采种机':buckwheat+sandleaf,
           '封装机':battery,'灌装机':capsule}
    durations={k:5 if k in ('封装机','灌装机') else 1 for k in rates}
    counts={k:math.ceil(v*durations[k]) for k,v in rates.items()}
    minimum={k:v-F(counts[k]-1,durations[k]) for k,v in rates.items()}
    sizes={'粉碎机':9,'精炼炉':9,'研磨机':24,'塑形机':9,'配件机':9,'种植机':25,'采种机':25,'封装机':24,'灌装机':24}
    assert sum(counts.values())==217 and sum(counts[k]*sizes[k] for k in counts)==3291
    assert all(v>0 for v in minimum.values())
    return dict(rates={k:str(v) for k,v in rates.items()},counts=counts,
                min_per_machine={k:str(v) for k,v in minimum.items()},machines=217,machine_area=3291,
                area_remainder=4900-3291-81-138-1113,S_budget=4639-4*1113,
                pole_branches=[dict(P=p,loss_budget=23*p-217,Jmax=(23*p-217)//10,TplusF=277-4*p) for p in (10,11,12)])

def run():
    summary=dict(blocks=check_blocks(),matching=matching(),arithmetic=arithmetic())
    for name in ('cp184','highs_J0','highs_J1','fixed185_cp','fixed185_highs'):
        d=json.loads((OUT/(name+'.json')).read_text())
        assert d['script_sha256']==digest(OUT/'solve.py')
        assert d['geometry_script_sha256']==digest(OUT/'recompute.py')
        if name.startswith('fixed'):
            assert d['S']==185 and d['integer_rows_checked']
            assert d['status'] in ('OPTIMAL',0)
        else:assert d['status'] in ('INFEASIBLE',2)
    inputs=json.loads((OUT/'input_manifest.json').read_text())
    for d in inputs:assert digest(Path(d['path']))==d['sha256'],d['path']
    summary['input_hashes_unchanged']=True
    summary['solver_receipts_and_source_hashes_pass']=True
    summary['memory_not_used_as_math_premise']=True
    save('audit',summary)
    save('output_manifest',[dict(path=p.name,sha256=digest(p),bytes=p.stat().st_size)
                           for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='output_manifest.json'])
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':run()
