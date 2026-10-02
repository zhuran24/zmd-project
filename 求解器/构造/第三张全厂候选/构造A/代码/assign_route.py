#!/usr/bin/env python3
"""Identity assignment and legal bridge-aware rerouting of an anonymous packing.

This is a heuristic. Missing routes stay explicit; a partial result is not a layout.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import argparse,json,time,random,math,heapq
from pathlib import Path
from collections import defaultdict,Counter,deque
from scipy.optimize import linear_sum_assignment
from joint_cp import BASE,save,D

def run(inp,out,seed,steps,rounds):
    raw=json.loads(inp.read_text());c=json.loads((BASE/'逻辑接法.json').read_text());rng=random.Random(seed);t0=time.monotonic()
    if 'units' not in raw:raise ValueError('无匿名坐标解')
    poses=raw['units'];spec={u['id']:u for u in c['machines']};ids=list(spec);edges=c['logical_feeds'];posidx={uid:i for i,uid in enumerate(ids)}
    occ=set()
    def body(u):return {(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)}
    for u in poses+[raw['core']]:occ|=body(u)
    for x,y in raw['poles']:occ|={(x+i,y+j) for i in range(2) for j in range(2)}
    occ|={(0,y) for y in range(1,70)}|{(x,0) for x in range(1,70)}
    rect=raw.get('rect')
    if rect:occ|={(x,y) for x in range(rect[0],rect[0]+rect[2]) for y in range(rect[1],rect[1]+rect[3])}
    free={(x,y) for x in range(70) for y in range(70)}-occ
    def ports(u,side,offsets=None):
        ans=[]
        for z in (range(u['y1']-u['y0']+1 if side%2==0 else u['x1']-u['x0']+1) if offsets is None else offsets):
            x,y=[(u['x1']+1,u['y0']+z),(u['x0']+z,u['y1']+1),(u['x0']-1,u['y0']+z),(u['x0']+z,u['y0']-1)][side]
            if (x,y) in free:ans.append(((x,y),side,z))
        return ans
    def bfs(starts):
        ds={p[0]:0 for p in starts};q=deque(ds)
        while q:
            x,y=q.popleft();v=ds[x,y]+1
            for dx,dy in D:
                cc=x+dx,y+dy
                if cc in free and cc not in ds:ds[cc]=v;q.append(cc)
        return ds
    ps=[];po=[];states=[];pose_states=[]
    for pi,p in enumerate(poses):
        ss=[]
        for di in (range(4) if p['kind']!='大' else [p['Din'],(p['Din']+2)%4]):
            ss.append(len(states));states.append((pi,di));ps.append(ports(p,di));po.append(ports(p,(di+2)%4))
        pose_states.append(ss)
    distances=[]
    for pp in po:
        ds=bfs(pp);distances.append([min((ds.get(q[0],10000) for q in target),default=10000) for target in ps])
    oreports=[((1,2+3*j),0,1) for j in range(23)]+[((2+3*j,1),1,1) for j in range(23)]
    core=raw['core'];cd=core['Din'];coreout=[p for s in ((cd+1)%4,(cd+3)%4) for p in ports(core,s,[1,4,7])];corein=[p for s in (cd,(cd+2)%4) for p in ports(core,s,range(1,8))]
    dsore=bfs(oreports);dscore=bfs(coreout);to_core=[]
    targetds=bfs(corein)
    for pp in po:to_core.append(min((targetds.get(x[0],10000) for x in pp),default=10000))
    nin=Counter(e['target'] for e in edges);nout=Counter(e['source'] for e in edges);sources={e['target']:e['source'] for e in edges if e['source']=='CORE' or e['source'].startswith('W')};finals={e['source'] for e in edges if e['target']=='CORE'}
    unary=[]
    for uid in ids:
        vals=[]
        for st in range(len(ps)):
            v=20000*(max(0,nin[uid]-len(ps[st]))+max(0,nout[uid]-len(po[st])))
            if uid in sources:v+=min(((dscore if sources[uid]=='CORE' else dsore).get(q[0],10000) for q in ps[st]),default=10000)
            if uid in finals:v+=to_core[st]
            vals.append(v)
        unary.append(vals)
    assign=[None]*len(ids);groups=[]
    for kind in ('小','中','大'):
        nodes=[i for i,u in enumerate(ids) if spec[u]['kind']==kind];pp=[j for j,p in enumerate(poses) if p['kind']==kind];groups.append(nodes)
        cost=[[min(unary[i][st] for st in pose_states[j])+rng.random() for j in pp] for i in nodes];aa,bb=linear_sum_assignment(cost)
        for a,b in zip(aa,bb):
            i,j=nodes[a],pp[b];assign[i]=min(pose_states[j],key=lambda st:unary[i][st])
    internal=[(posidx[e['source']],posidx[e['target']]) for e in edges if e['source'] in spec and e['target'] in spec];incident=defaultdict(set)
    for k,(u,v) in enumerate(internal):incident[u].add(k);incident[v].add(k)
    def affected(ns):return set().union(*(incident[n] for n in ns))
    def score(ns,es):return sum(unary[i][assign[i]] for i in ns)+sum(distances[assign[internal[k][0]]][assign[internal[k][1]]] for k in es)
    best=score(range(len(ids)),range(len(internal)));bestassign=assign[:]
    for step in range(steps):
        flip=rng.random()<.25
        if flip:
            ns=[rng.randrange(len(ids))];es=incident[ns[0]];old=assign[ns[0]];before=score(ns,es);assign[ns[0]]=rng.choice(pose_states[states[old][0]])
        else:
            ns=rng.sample(rng.choice(groups),2);es=affected(ns);old=[assign[i] for i in ns];before=score(ns,es);assign[ns[0]],assign[ns[1]]=assign[ns[1]],assign[ns[0]]
        after=score(ns,es);phase=(step%max(1,steps//5))/max(1,steps//5);temp=max(.1,120*(1-phase)**3)
        if after>before and rng.random()>math.exp(max(-700,(before-after)/temp)):
            if flip:assign[ns[0]]=old
            else:
                for i,v in zip(ns,old):assign[i]=v
        if step%1000==0:
            total=score(range(len(ids)),range(len(internal)))
            if total<best:best=total;bestassign=assign[:]
    assign=bestassign;placed={}
    for i,uid in enumerate(ids):
        pi,di=states[assign[i]];p=dict(poses[pi]);p.update(Din=di,kind='machine');placed[uid]=p
    placed['CORE']=dict(core,kind='core')
    for i,(x,y) in enumerate(raw['poles']):placed['POWER'+str(i)]=dict(x0=x,y0=y,x1=x+1,y1=y+1,Din=0,kind='pole')
    # Reassign the configurable boundary outlet identities using exact free-grid distances.
    ore_edges=[e for e in edges if e['source'].startswith('W')];ore_ds=[bfs([p]) for p in oreports]
    cost=[[min((ds.get(q[0],10000) for q in ps[assign[posidx[e['target']]]]),default=10000) for ds in ore_ds] for e in ore_edges];aa,bb=linear_sum_assignment(cost);op={}
    for a,b in zip(aa,bb):
        b=int(b);uid=ore_edges[a]['source'];j=b%23;di=0 if b<23 else 1;op[uid]=[oreports[b]];placed[uid]=dict(x0=0 if di==0 else 1+3*j,y0=1+3*j if di==0 else 0,x1=0 if di==0 else 3+3*j,y1=3+3*j if di==0 else 0,Din=di,kind='outlet')
    def ends(uid,inbound):
        if uid in op:return op[uid]
        if uid=='CORE':return corein if inbound else coreout
        st=assign[posidx[uid]];return ps[st] if inbound else po[st]
    nets=[dict(e,starts=ends(e['source'],False),goals=ends(e['target'],True)) for e in edges]
    lower=[]
    for n in nets:
        ds=bfs(n['starts']);lower.append(min((ds.get(q[0],10000) for q in n['goals']),default=10000)+1)
    occupancy=defaultdict(dict);paths={};history=Counter()
    def can(c,di,do,net):
        other=occupancy.get(c,{})
        if not other:return True
        if len(other)!=1 or di!=do:return False
        _,(a,b)=next(iter(other.items()));return a==b and a%2!=di%2
    def route(n,i):
        goals=defaultdict(list)
        for c,s,z in n['goals']:goals[c].append((s+2)%4)
        if not goals:return None
        targets=list(goals);q=[];dist={};prev={};seq=0
        def h(c):return min(abs(c[0]-t[0])+abs(c[1]-t[1]) for t in targets)
        for c,s,z in n['starts']:
            state=(c,s);dist[state]=0;heapq.heappush(q,(h(c),0,seq,state));seq+=1
        while q:
            _,g,_,state=heapq.heappop(q)
            if g!=dist.get(state):continue
            cc,di=state
            for do in goals.get(cc,[]):
                if do!=(di+2)%4 and can(cc,di,do,i):
                    p=[(cc,di,do)];at=state
                    while at in prev:old,od=prev[at];p.append((old[0],old[1],od));at=old
                    p.reverse()
                    if len({t[0] for t in p})==len(p):return p
            for do,(dx,dy) in enumerate(D):
                if do==(di+2)%4 or not can(cc,di,do,i):continue
                nxt=(cc[0]+dx,cc[1]+dy)
                if nxt not in free:continue
                ng=g+1+.04*(di!=do)+.02*history[cc]+.05*bool(occupancy.get(cc));stt=(nxt,do)
                if ng<dist.get(stt,1e100):dist[stt]=ng;prev[stt]=(state,do);heapq.heappush(q,(ng+h(nxt),ng,seq,stt));seq+=1
        return None
    def add(i,p):
        paths[i]=p
        for cc,di,do in p:occupancy[cc][i]=(di,do)
    def rip(i):
        for cc,di,do in paths.pop(i,[]):occupancy[cc].pop(i,None)
    bestn=-1;bestcost=10**9
    info=dict(schema='s2-heuristic-routes-v1',is_layout=False,status='FEASIBLE',W=70,H=70,seed=seed,placements=placed,routes_count=len(nets),assignment_score=best,independent_route_lower_sum=sum(lower) if all(d<10000 for d in lower) else None,finite_individual_shortest_sum=sum(d for d in lower if d<10000),individually_unreachable=[n['id'] for n,d in zip(nets,lower) if d>=10000],max_transport_slots=2*len(free),reserved_empty_rectangle=rect)
    for rnd in range(rounds):
        if rnd==0:order=sorted(range(len(nets)),key=lambda i:lower[i])
        else:
            missing=[i for i in range(len(nets)) if i not in paths];remove=rng.sample(list(paths),max(1,len(paths)//(4 if rnd%4==0 else 8)))
            for i in remove:rip(i)
            rng.shuffle(missing);rng.shuffle(remove);order=missing+remove
        for i in order:
            if i in paths:continue
            p=route(nets[i],i)
            if p:add(i,p)
        cost=sum(len(p) for p in paths.values())
        if len(paths)>bestn or (len(paths)==bestn and cost<bestcost):
            bestn=len(paths);bestcost=cost;outpaths=[]
            for i,p in sorted(paths.items()):
                e=edges[i];outpaths.append(dict(e,cells=[list(c) for c,di,do in p],start=[*p[0][0],(p[0][1]+2)%4],end=[*p[-1][0],p[-1][2]]))
            save(out,{**info,'routed':bestn,'missing_routes':[e['id'] for i,e in enumerate(edges) if i not in paths],'paths':outpaths,'transport_slot_count':cost,'occupied_transport_cells':sum(bool(v) for v in occupancy.values()),'round':rnd,'elapsed':time.monotonic()-t0})
        print('round',rnd,'routed',len(paths),'best',bestn,'slots',cost,'seconds',round(time.monotonic()-t0,2),flush=True)
        if bestn==len(nets):break
    return bestn

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('input');a.add_argument('--out',required=True);a.add_argument('--seed',type=int,default=1);a.add_argument('--steps',type=int,default=250000);a.add_argument('--rounds',type=int,default=50);p=a.parse_args();run(Path(p.input),BASE/p.out,p.seed,p.steps,p.rounds)
