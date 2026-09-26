"""Fresh native Boolean model of the entire B projection. No producer imports."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,set(range(10)))
import json,time,argparse,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from ortools.sat.python import cp_model

OUT=Path(__file__).resolve().parent
R={(x,y) for x in range(49,70) for y in range(17,70)}
LINES=[[(69,y) for y in range(1,17)],[(x,69) for x in range(1,49)],[(48,y) for y in range(17,70)],[(x,16) for x in range(49,70)]]
COUNTS=Counter(c for line in LINES for c in line)
def body(x,y,w,h):return {(x+i,y+j) for i in range(w) for j in range(h)}
def allowed(c):return 1<=c[0]<=69 and 1<=c[1]<=69 and c not in R
def sides(x,y,w,h,axis):
    return [[(x-1,t) for t in range(y,y+h)],[(x+w,t) for t in range(y,y+h)]] if axis==0 else [[(t,y-1) for t in range(x,x+w)],[(t,y+h) for t in range(x,x+w)]]

def generate():
    units=[]
    for kind,w,h,axis in [('s',3,3,0),('s',3,3,1),('m',5,5,0),('m',5,5,1),('l',6,4,1),('l',4,6,0),('c',9,9,0),('c',9,9,1)]:
        anchors={(cx-dx,cy-dy) for cx,cy in COUNTS for dx in range(w) for dy in range(h)}
        for x,y in sorted(anchors):
            b=body(x,y,w,h)
            if not all(allowed(c) for c in b):continue
            sides0=sides(x,y,w,h,axis)
            if kind=='c':
                if min(x,y)<2 or (x<=3 and y<=3):continue
                if axis==0 and (x<=3 or (y+9==70 and x<7)):continue
                if axis==1 and (y<=3 or (x+9==70 and y<7)):continue
                ports=[([s[i]],1) for s in sides0 for i in (1,4,7)]
                if any(not allowed(ps[0]) for ps,n in ports):continue
                ps=[s[i] for s in sides(x,y,w,h,1-axis) for i in range(1,8) if allowed(s[i])]
                ports.append((ps,2))
            else:ports=[([c for c in s if allowed(c)],1) for s in sides0]
            if any(len(ps)<n for ps,n in ports):continue
            units.append(dict(kind=kind,r=[x,y,w,h],axis=axis,body=sorted(b),ports=ports,loss=0,j=0))
    machines=[u for u in units if u['kind']!='c']
    allp=[]
    for rec in json.loads((OUT/'capacities.json').read_text()):
        if rec['cap']<10:continue
        x,y=rec['p'];b=body(x,y,2,2);j=int(x in (1,68) or y in (1,68))
        u=dict(kind='p',r=[x,y,2,2],axis=-1,body=sorted(b),ports=[],loss=23-rec['cap'],j=j)
        allp.append(u)
        reach=body(x-5,y-5,12,12)
        if j or b&COUNTS.keys() or any(reach&set(map(tuple,m['body'])) for m in machines):units.append(u)
    return units,len(allp)

def build(cap,exact):
    units,fullp=generate();m=cp_model.CpModel();v=[m.new_bool_var('unit_'+str(i)) for i in range(len(units))]
    inc=defaultdict(list)
    for i,u in enumerate(units):
        for c in u['body']:inc[tuple(c)].append(v[i])
    oc={c:m.new_bool_var('occupied_'+str(c)) for c in sorted(inc)}
    for c,iv in inc.items():m.add(oc[c]==sum(iv))
    for i,u in enumerate(units):
        for ps,n in u['ports']:m.add(sum(oc.get(tuple(c),0) for c in ps)<=len(ps)-n).only_enforce_if(v[i])
    # Joint boundary pattern variables; no pre-selected gap.
    patterns=[(0,k) for k in range(0,70,3)]+[(k,0) for k in range(3,70,3)]
    pat=[m.new_bool_var('warehouse_'+str(k)) for k in range(47)];m.add_exactly_one(pat)
    for j,(g,h) in enumerate(patterns):
        sources={(1,3*k+1+int(3*k>=g)) for k in range(23)}|{(3*k+1+int(3*k>=h),1) for k in range(23)}
        for c in sources:
            if c in oc:m.add(oc[c]==0).only_enforce_if(pat[j])
    exceptions=[]
    for i,u in enumerate(units):
        if u['kind']!='l':continue
        which=m.new_bool_var('input_'+str(i));ex=m.new_bool_var('exception_'+str(i));exceptions.append(ex);m.add(ex<=v[i])
        for side,(ps,_) in enumerate(u['ports']):
            m.add(sum(oc.get(tuple(c),0) for c in ps)<=len(ps)-3+ex).only_enforce_if([v[i],which if side==0 else which.Not()])
    m.add(sum(exceptions)<=1)
    poles=[i for i,u in enumerate(units) if u['kind']=='p']
    machines=[i for i,u in enumerate(units) if u['kind'] in ('s','m','l')]
    m.add(sum(v[i] for i in poles)<=10)
    m.add(sum(v[i]*units[i]['j'] for i in poles)==1)
    m.add(sum(v[i] for i in poles if units[i]['r'][0]==1 or units[i]['r'][1]==1)==1)
    for kind,limit in [('s',131),('m',48),('l',38),('c',1)]:m.add(sum(v[i] for i,u in enumerate(units) if u['kind']==kind)<=limit)
    repeats=[];supplies={i:body(units[i]['r'][0]-5,units[i]['r'][1]-5,12,12) for i in poles}
    for i in machines:
        b=set(map(tuple,units[i]['body']));cover=[v[j] for j in poles if b&supplies[j]]
        m.add(sum(cover)>=1).only_enforce_if(v[i]);z=m.new_int_var(0,9,'repeat_'+str(i));repeats.append(z)
        m.add(z==sum(cover)-1).only_enforce_if(v[i]);m.add(z==0).only_enforce_if(v[i].Not())
    m.add(sum(repeats)+sum(units[i]['loss']*v[i] for i in poles)<=13)
    reward=sum(sum(COUNTS[c] for c in map(tuple,u['body']))*v[i] for i,u in enumerate(units))
    score=296-reward # 160 - 2*J + 138; J=1.
    m.add(score<=cap)
    if exact:m.add(score==cap)
    m.minimize(score)
    return m,units,v,score,fullp

def main():
    p=argparse.ArgumentParser();p.add_argument('--cap',type=int,default=186);p.add_argument('--exact',action='store_true');p.add_argument('--seconds',type=float,default=300);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    t=time.monotonic();m,units,v,score,fullp=build(a.cap,a.exact);label='boundary_'+('eq' if a.exact else 'le')+str(a.cap)+'_cp'
    (OUT/(label+'_domain.json')).write_text(json.dumps(units,separators=(',',':')))
    raw=str(m.proto);(OUT/(label+'_model.txt')).write_text(raw)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=a.workers;solver.parameters.max_time_in_seconds=a.seconds
    solver.parameters.linearization_level=2;solver.parameters.log_search_progress=True;solver.parameters.log_to_stdout=False
    with (OUT/(label+'.log')).open('w') as log:
        solver.log_callback=lambda x:log.write(x+'\n')
        status=solver.solve(m)
    out=dict(status=solver.status_name(status),cap=a.cap,exact=a.exact,domain=dict(Counter(u['kind'] for u in units)),full_poles=fullp,units=len(units),seconds=time.monotonic()-t,solver_seconds=solver.wall_time,model_sha256=hashlib.sha256(raw.encode()).hexdigest(),stats=solver.response_stats())
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):out.update(S=solver.value(score),chosen=[u for u,x in zip(units,v) if solver.value(x)])
    (OUT/(label+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ('stats','chosen')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
