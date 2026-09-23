#!/usr/bin/env python3
"""Integer, cell-by-cell witness validation independent of both optimizers."""
from pathlib import Path
import json,sys,hashlib
from collections import Counter
OUT=Path(__file__).resolve().parent;ROUNDS=OUT.parents[1]
def rect(b):return {(x,y) for x in range(b['x'],b['x']+b['w']) for y in range(b['y'],b['y']+b['h'])}
def legal(c):return 1<=c[0]<=69 and 1<=c[1]<=69 and not(c[0]>=49 and c[1]>=17)
def check(data,strict_score=True,exact_p=True):
    chosen=data['chosen'];occupied={};ports=[];large=[];counts=Counter();poles=[];machines=[]
    for i,b in enumerate(chosen):
        counts[b['kind']]+=1;body=rect(b)
        assert all(map(legal,body))
        for c in body:assert c not in occupied,(c,i,occupied.get(c));occupied[c]=i
        x,y,w,h=(b[k] for k in ('x','y','w','h'));k=b['kind'];a=b['axis']
        assert (k,w,h,a) in [('s',3,3,'h'),('s',3,3,'v'),('m',5,5,'h'),('m',5,5,'v'),('l',6,4,'v'),('l',4,6,'h'),('c',9,9,'h'),('c',9,9,'v'),('p',2,2,'-')]
        if k=='p':poles.append((i,b));continue
        if a=='h':edges=[[(x-1,t) for t in range(y,y+h)],[(x+w,t) for t in range(y,y+h)]]
        else:edges=[[(t,y-1) for t in range(x,x+w)],[(t,y+h) for t in range(x,x+w)]]
        if k=='c':
            assert x>=2 and y>=2 and not(x<=3 and y<=3)
            assert not(x<=3 and a=='h') and not(y<=3 and a=='v')
            assert not(y==61 and x<=6 and a=='h') and not(x==61 and y<=6 and a=='v')
            takes=[s[t] for s in edges for t in (1,4,7)];assert all(map(legal,takes))
            if a=='h':put=[(t,z) for t in range(x+1,x+8) for z in (y-1,y+9)]
            else:put=[(z,t) for z in (x-1,x+9) for t in range(y+1,y+8)]
            edges=[[c] for c in takes]+[[c for c in put if legal(c)]];need=[1]*6+[2]
        else:
            edges=[[c for c in e if legal(c)] for e in edges];need=[1,1];machines.append((i,b))
        ports.append((i,edges,need))
        if k=='l':large.append((i,edges))
    for k,n in [('s',131),('m',48),('l',38),('c',1)]:assert counts[k]<=n
    assert len(poles)==10 if exact_p else len(poles)<=10
    freeports=[]
    for i,edges,needs in ports:
        free=[[c for c in e if c not in occupied] for e in edges]
        assert all(len(e)>=n for e,n in zip(free,needs)),('port',i)
        freeports.append({'unit':i,'free_neighbor_cells':free})
    low=0
    for i,edges in large:
        lengths=[sum(c not in occupied for c in e) for e in edges]
        assert max(lengths)>=2;low+=max(lengths)<3
    assert low<=1
    gap_pair=data.get('warehouse_gaps')
    if gap_pair is not None:
        assert len(gap_pair)==2 and 0 in gap_pair and all(g%3==0 and 0<=g<=69 for g in gap_pair)
        for axis,g in enumerate(gap_pair):
            intervals=[];at=0
            while at<70:
                if at==g:at+=1;continue
                intervals.append((at,at+3));at+=3
            assert len(intervals)==23 and at==70
            for a,z in intervals:assert ((1,a+1) if axis==0 else (a+1,1)) not in occupied
    group={(d['x'],d['y']):d['cap'] for d in json.loads((ROUNDS/'第66-68轮/推导66/power_certificates.json').read_text())['17']}
    local={tuple(p):d['integer_upper'] for d in json.loads((ROUNDS/'第69-71轮/推导69/supply_strip_certificates.json').read_text()) for p in d['positions']}
    loss=0;J=0;power=[]
    for i,p in poles:
        x,y=p['x'],p['y'];e=int(x in (1,68))+int(y in (1,68));J+=e>0
        c=min(23,group[x,y],local.get((x,y),23),8 if e==2 else 13 if e else 23)
        if y-5>=17 and y+6<=69:
            g=49-(x+2)
            if 0<=g<=6:c=min(c,[13,14,14,17,18,19,22][g])
        if x-5>=49 and x+6<=69:
            g=17-(y+2)
            if 0<=g<=6:c=min(c,[13,14,14,17,18,19,22][g])
        loss+=23-c;power.append({'unit':i,'position':[x,y],'cap':c,'loss':23-c,'selected_machines':[]})
    repeat=0;coverage=[]
    for i,b in machines:
        hit=[]
        for pi,(j,p) in enumerate(poles):
            region={(x,y) for x in range(p['x']-5,p['x']+7) for y in range(p['y']-5,p['y']+7)}
            if region&rect(b):hit.append(j);power[pi]['selected_machines'].append(i)
        assert hit,('unpowered',i);repeat+=len(hit)-1;coverage.append({'unit':i,'poles':hit,'repeats':len(hit)-1})
    assert loss+repeat<=13,('budget',loss,repeat)
    for p in power:assert len(p['selected_machines'])<=p['cap']
    lines=[[(69,y) for y in range(1,17)],[(x,69) for x in range(1,49)],[(48,y) for y in range(17,70)],[(x,16) for x in range(49,70)]]
    gaps=[[c for c in line if c not in occupied] for line in lines];n=list(map(len,gaps));S=160-2*J+sum(n)
    if strict_score:assert S==data['S'],('S',S,data['S'])
    return dict(status='PASS',S=S,X=sum(n[:2]),Y=sum(n[2:]),line_gaps=n,gap_cells=gaps,J=J,P=len(poles),counts=dict(counts),loss=loss,repeated_coverage=repeat,total_charge=loss+repeat,charge_remaining=13-loss-repeat,low_input_large=low,coverage=coverage,power=power,port_checks=freeports,warehouse_gaps=gap_pair,omitted_manufacturing=217-len(machines),origin='来源不明，当线索；仅为几何与供电放宽点')
if __name__=='__main__':
    path=Path(sys.argv[1]);data=json.loads(path.read_text());r=check(data,'--repair-score' not in sys.argv,'--partial-poles' not in sys.argv)
    r['source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();(OUT/(path.stem+'_checked.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in r.items() if k not in ('gap_cells','coverage','power','port_checks')})
