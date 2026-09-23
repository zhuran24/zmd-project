#!/usr/bin/env python3
"""R75 independently written exact cell, port, actual power, union, subset checker.
No solver or solver-building module is imported. Coordinates are authoritative.
"""
from pathlib import Path
from collections import Counter
import json,hashlib,argparse
OUT=Path(__file__).resolve().parent
ROUNDS=OUT.parents[1]
def rect(x,y,w,h):return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
def footprint(b):return rect(*(b[k] for k in ('x','y','w','h')))
def transpose(d):
    z=json.loads(json.dumps(d));z['warehouse_gaps']=list(reversed(z['warehouse_gaps']))
    for b in z['chosen']:
        b['x'],b['y']=b['y'],b['x'];b['w'],b['h']=b['h'],b['w'];b['axis']={'h':'v','v':'h','-':'-'}[b['axis']]
        for k in ('ports','needs'):b.pop(k,None)
    return z
def matching(groups,caps):
    # Independent Kuhn search on expanded integer capacity slots.
    slots=[i for i,c in enumerate(caps) for _ in range(c)];assigned={}
    def augment(slot,seen):
        for group in sorted(groups[slots[slot]]):
            if group in seen:continue
            seen.add(group)
            if group not in assigned or augment(assigned[group],seen):assigned[group]=slot;return True
        return False
    for slot in range(len(slots)):augment(slot,set())
    certificate=[[slots[slot],list(g)] for g,slot in sorted(assigned.items())]
    assert len({tuple(g) for _,g in certificate})==len(certificate)
    assert all(tuple(g) in groups[i] for i,g in certificate)
    assert all(sum(j==i for j,_ in certificate)<=caps[i] for i in range(len(caps)))
    return certificate
def check(data,transposed=False,require_m1=True):
    hole=rect(17,49,53,21) if transposed else rect(49,17,21,53)
    legal=lambda c:1<=c[0]<=69 and 1<=c[1]<=69 and c not in hole
    units=data['chosen'];count=Counter(b['kind'] for b in units);bodies=[footprint(b) for b in units]
    assert count['p']==10 and count['c']<=1 and count['s']<=131 and count['m']<=48 and count['l']<=38
    occupancy={}
    specs={('s',3,3,'h'),('s',3,3,'v'),('m',5,5,'h'),('m',5,5,'v'),('l',6,4,'v'),('l',4,6,'h'),('c',9,9,'h'),('c',9,9,'v'),('p',2,2,'-')}
    for i,(b,body) in enumerate(zip(units,bodies)):
        assert (b['kind'],b['w'],b['h'],b['axis']) in specs
        assert all(legal(c) for c in body)
        for c in body:assert c not in occupancy,('overlap',c);occupancy[c]=i
    port_records=[];weak=0
    for i,b in enumerate(units):
        x,y,w,h=(b[k] for k in ('x','y','w','h'));axis=b['axis'];kind=b['kind']
        if kind=='p':continue
        horizontal=[[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
        vertical=[[(j,y-1) for j in range(x,x+w)],[(j,y+h) for j in range(x,x+w)]]
        sides=horizontal if axis=='h' else vertical
        if kind=='c':
            assert x>=2 and y>=2 and not(x<=3 and y<=3)
            assert not(x<=3 and axis=='h') and not(y<=3 and axis=='v')
            assert not(y==61 and x<=6 and axis=='h') and not(x==61 and y<=6 and axis=='v')
            take=[s[k] for s in sides for k in (1,4,7)]
            put=[s[k] for s in (vertical if axis=='h' else horizontal) for k in range(1,8)]
            assert all(legal(c) and c not in occupancy for c in take)
            free_put=[c for c in put if legal(c) and c not in occupancy];assert len(free_put)>=2
            port_records.append(dict(unit=i,take=take,free_put=free_put))
        else:
            free=[[c for c in side if legal(c) and c not in occupancy] for side in sides]
            assert all(free),('blocked ports',i)
            if kind=='l':assert max(map(len,free))>=2;weak+=max(map(len,free))<3
            port_records.append(dict(unit=i,free_sides=free))
    assert weak<=1
    wg=data['warehouse_gaps'];assert len(wg)==2 and 0 in wg and all(v in range(0,70,3) for v in wg)
    first=[]
    for axis,gap in enumerate(wg):
        covered=set();source=[]
        for t in range(23):
            anchor=3*t+int(3*t>=gap);covered.update(range(anchor,anchor+3));source.append(anchor+1)
        assert covered==set(range(70))-{gap}
        for z in source:
            c=(1,z) if axis==0 else (z,1);assert c not in occupancy;first.append(c)
    groups_caps={(g['x'],g['y']):g['cap'] for g in json.loads((ROUNDS/'第66-68轮/推导66/power_certificates.json').read_text())['17']}
    local_caps={tuple(xy):g['integer_upper'] for g in json.loads((ROUNDS/'第69-71轮/推导69/supply_strip_certificates.json').read_text()) for xy in g['positions']}
    pp=[i for i,b in enumerate(units) if b['kind']=='p'];mm=[i for i,b in enumerate(units) if b['kind'] in ('s','m','l')]
    capacities=[];power=[];J=0
    for pi in pp:
        b=units[pi];p,q=b['x'],b['y'];x,y=(q,p) if transposed else (p,q)
        e=int(x in (1,68))+int(y in (1,68));J+=bool(e)
        cap=min(23,groups_caps[x,y],local_caps.get((x,y),23),8 if e==2 else 13 if e else 23)
        if 22<=y<=63 and 41<=x<=47:cap=min(cap,(13,14,14,17,18,19,22)[47-x])
        if 54<=x<=63 and 9<=y<=15:cap=min(cap,(13,14,14,17,18,19,22)[15-y])
        capacities.append(cap);power.append(rect(p-5,q-5,12,12))
    coverage=[];repeated=0
    for mi in mm:
        hit=[k for k,p in enumerate(power) if p&bodies[mi]];assert hit,('unpowered',mi)
        repeated+=len(hit)-1;coverage.append(dict(unit=mi,poles=hit))
    loss=sum(23-c for c in capacities);assert loss+repeated<=13
    assert all(sum(p in r['poles'] for r in coverage)<=c for p,c in enumerate(capacities))
    Xlines=[{(69,y) for y in range(1,69)}-hole,{(x,69) for x in range(1,69)}-hole]
    a,b,W,H=(17,49,53,21) if transposed else (49,17,21,53)
    Ylines=[{(a-1,y) for y in range(b,b+H)},{(x,b-1) for x in range(a,a+W)}]
    gapcells=[sorted(line-occupancy.keys()) for line in Xlines+Ylines];gaps=list(map(len,gapcells));X=sum(gaps[:2]);Y=sum(gaps[2:]);S=160-2*J+X+Y
    assert S==data['S'],('wrong S',S,data['S'])
    if not transposed:
        tables=json.loads((ROUNDS/'第69-71轮/推导69/new_edge_local_certificate.json').read_text())['cases'][0]['lines']
        for no,(line,tab) in enumerate(zip(Xlines+Ylines,tables)):
            ids=[i for i,cells in enumerate(bodies) if cells&line];cs=sum(units[i]['kind']=='c' for i in ids);ps=[p for p,pi in enumerate(pp) if pi in ids]
            total_loss=sum(23-capacities[p] for p in ps);edge_poles=sum(units[pp[p]]['x'] in (1,68) or units[pp[p]]['y'] in (1,68) for p in ps)
            actual=gaps[no]-2*edge_poles
            assert any(st[0]==cs and st[1]==len(ps) and st[2]<=total_loss and val<=actual for st,val in tab['frontier'])
    centers=[]
    for k,pi in enumerate(pp):
        cs=[]
        for x in range(2,69):
            for y in range(2,69):
                square=rect(x-1,y-1,3,3)
                if not square&hole and not square&bodies[pi] and square&power[k]:cs.append((x,y))
        centers.append(cs)
    partitions=[]
    for a in range(3):
        for b in range(3):
            gs=[{((x+a)//3,(y+b)//3) for x,y in cs} for cs in centers];all_union=set().union(*gs)
            if require_m1:assert len(all_union)>=217,('M1 union fails',a,b,len(all_union))
            cuts=[];best=(10000,0,0,0)
            for mask in range(1<<10):
                inside=set();outside=0
                for i in range(10):
                    if mask>>i&1:inside.update(gs[i])
                    else:outside+=capacities[i]
                value=outside+len(inside);cuts.append(value)
                if value<best[0]:best=(value,mask,outside,len(inside))
            mat=matching(gs,capacities);assert len(mat)==best[0]
            partitions.append(dict(shift=[a,b],union=len(all_union),upper=best[0],mask=best[1],outside_capacity=best[2],inside_union=best[3],matching=mat,subset_bounds=cuts))
    return dict(status='PASS',model='M1' if require_m1 else 'M0',transposed=transposed,S=S,J=J,X=X,Y=Y,line_gaps=gaps,gap_cells=gapcells,counts=dict(count),missing_machines=217-len(mm),warehouse_first_cells=first,
                pole_positions=[[units[i]['x'],units[i]['y']] for i in pp],capacities=capacities,loss=loss,repeats=repeated,coverage=coverage,ports=port_records,partitions=partitions,all_subset_upper=min(r['upper'] for r in partitions))
def main():
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--transpose',action='store_true');p.add_argument('--m0',action='store_true');p.add_argument('--name');a=p.parse_args()
    data=json.loads(Path(a.file).read_text())
    if a.transpose:data=transpose(data)
    r=check(data,a.transpose,not a.m0);r['source_sha256']=hashlib.sha256(Path(a.file).read_bytes()).hexdigest();r['checker_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    name=a.name or Path(a.file).stem+('_transpose' if a.transpose else '')+'_audit'
    (OUT/(name+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    if a.transpose:(OUT/(name+'_witness.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print({k:r[k] for k in ('status','S','J','X','Y','line_gaps','loss','repeats','all_subset_upper')});print('unions',[t['union'] for t in r['partitions']])
if __name__=='__main__':main()
