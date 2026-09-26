"""Pole-position partition relaxation: full boundary bodies + residual groups.

All machines are assigned once to a genuinely covering pole for this bound.
Boundary machines keep full bodies; other machines keep a powered 3x3 subblock.
Different fragments ignore each other's objects.  This only enlarges feasibility.
"""
from geometry_a import *
from collections import defaultdict
from ortools.sat.python import cp_model
import argparse,time,hashlib,math

def build(region,mode='two',group=(0,1),exact_blocks=False,flow=False):
    model=cp_model.CpModel()
    caps=[z for z in read(OUT/'capacities.json') if z['cap']>=10 and 23-z['cap']-10*z['j']<=3 and piece(z['p'],mode)==region]
    machines=boundary_machines()
    machines=[z for z in machines if any(hit(z['r'],supply(p['p'])) and not hit(z['r'],(*p['p'],2,2)) for p in caps)]
    us=[model.new_bool_var('m%d'%i) for i in range(len(machines))]
    ps=[model.new_bool_var('p%d'%i) for i in range(len(caps))]
    n_p=sum(ps);n_j=sum(p['j']*v for p,v in zip(caps,ps))
    model.add(n_p<=10);model.add(n_j<=1)
    model.add(sum((23-p['cap']-10*p['j'])*v for p,v in zip(caps,ps))<=3)
    incidence=defaultdict(list)
    for z,v in list(zip(machines,us))+[(dict(r=(*p['p'],2,2)),v) for p,v in zip(caps,ps)]:
        for c in cells(z['r']):incidence[c].append(v)
    occ={c:model.new_bool_var('o%d_%d'%c) for c in incidence}
    for c,vs in incidence.items():model.add(occ[c]==sum(vs))
    def occupied(cs):return sum(occ[c] for c in cs if c in occ)
    exceptions=[]
    for z,v in zip(machines,us):
        for side in z['ports']:model.add(v+occupied(side)<=len(side))
        if z['kind']=='l':
            ex=model.new_bool_var('exception');directions=[model.new_bool_var('in0'),model.new_bool_var('in1')]
            exceptions.append(ex);model.add(ex<=v);model.add(sum(directions)==v)
            for side,d in zip(z['ports'],directions):model.add(occupied(side)+3*d-ex<=len(side))
    model.add(sum(exceptions)<=1)
    repeats=[]
    for z,v in zip(machines,us):
        cover=[pv for p,pv in zip(caps,ps) if hit(z['r'],supply(p['p']))]
        model.add(sum(cover)>=v)
        repeat=model.new_int_var(0,9,'repeat');repeats.append(repeat)
        model.add(repeat==sum(cover)-1).only_enforce_if(v)
        model.add(repeat==0).only_enforce_if(v.Not())
    centers=[];zs=[];groups=defaultdict(list);block_incidence=defaultdict(list)
    pg_centers=defaultdict(list)
    for x in range(2,69):
        for y in range(2,69):
            r=(x-1,y-1,3,3)
            # A machine touching a counted edge is always represented in full.
            if not legal(r) or weight(r):continue
            covering=[pi for pi,p in enumerate(caps) if hit(r,supply(p['p'])) and not hit(r,(*p['p'],2,2))]
            cover=[ps[pi] for pi in covering]
            if not cover:continue
            v=model.new_bool_var('z%d_%d'%(x,y));zs.append(v);centers.append((x,y))
            model.add(v<=sum(cover));model.add(9*v+occupied(cells(r))<=9)
            g=((x+group[0])//3,(y+group[1])//3);groups[g].append(v)
            if flow:
                for pi in covering:pg_centers[pi,g].append(v)
            if exact_blocks:
                for c in cells(r):block_incidence[c].append(v)
    for vs in groups.values():model.add(sum(vs)<=1)
    if exact_blocks:
        for c,vs in block_incidence.items():model.add(sum(vs)+(occ[c] if c in occ else 0)<=1)
    if flow:
        by_p=defaultdict(list);by_g=defaultdict(list)
        for (pi,g),vs in pg_centers.items():
            f=model.new_bool_var('flow%d_%d_%d'%(pi,*g))
            model.add(f<=ps[pi]);model.add(f<=sum(vs));by_p[pi].append(f);by_g[g].append(f)
        for g,vs in groups.items():model.add(sum(vs)==sum(by_g[g]))
        for pi,p in enumerate(caps):
            actual=[v for z,v in zip(machines,us) if hit(z['r'],supply(p['p']))]
            model.add(sum(by_p[pi])+sum(actual)<=p['cap']).only_enforce_if(ps[pi])
    n=sum(us)+sum(zs)
    t=sum(z['t']*v for z,v in zip(machines,us))+sum(p['t']*v for p,v in zip(caps,ps))
    model.add(n+sum(repeats)<=sum(p['cap']*v for p,v in zip(caps,ps)))
    info=dict(poles=len(caps),machines=len(machines),centers=len(centers),groups=len(groups),flow_edges=len(pg_centers))
    return model,dict(n=n,t=t,p=n_p,j=n_j),dict(caps=caps,machines=machines,ps=ps,us=us,zs=zs,centers=centers),info

def main():
    a=argparse.ArgumentParser();a.add_argument('--region',required=True);a.add_argument('--mode',default='two')
    a.add_argument('--a',type=int,default=2);a.add_argument('--b',type=int,default=1)
    a.add_argument('--mu',type=int);a.add_argument('--nu',type=int)
    a.add_argument('--seconds',type=int,default=60);a.add_argument('--workers',type=int,default=4)
    a.add_argument('--name',required=True);a.add_argument('--gx',type=int,default=0);a.add_argument('--gy',type=int,default=1)
    a.add_argument('--exact-blocks',action='store_true');a.add_argument('--flow',action='store_true');a.add_argument('--p',type=int);a.add_argument('--j',type=int)
    a.add_argument('--tmin',type=int);a.add_argument('--cap',type=int)
    args=a.parse_args();start=time.monotonic()
    mu=23*args.a if args.mu is None else args.mu;nu=10*args.a if args.nu is None else args.nu
    model,expr,vars,info=build(args.region,args.mode,(args.gx,args.gy),args.exact_blocks,args.flow)
    if args.p is not None:model.add(expr['p']==args.p)
    if args.j is not None:model.add(expr['j']==args.j)
    if args.tmin is not None:model.add(expr['t']>=args.tmin)
    objective=args.a*expr['n']+args.b*expr['t']-mu*expr['p']+nu*expr['j']
    if args.cap is not None:model.add(objective>=args.cap)
    else:model.maximize(objective)
    digest=hashlib.sha256(str(model.proto).encode()).hexdigest()
    print('built',info,'build_seconds',time.monotonic()-start,'objective',args.a,args.b,mu,nu,flush=True)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=args.workers
    solver.parameters.max_time_in_seconds=args.seconds;solver.parameters.log_search_progress=True
    solver.parameters.linearization_level=2;solver.parameters.random_seed=7801
    status=solver.solve(model)
    out=dict(args=varsafe(args),mu=mu,nu=nu,info=info,status=solver.status_name(status),
             objective=solver.objective_value,bound=solver.best_objective_bound,
             seconds=time.monotonic()-start,model_sha256=digest,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             stats=solver.response_stats())
    if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):
        out['counts']={k:solver.value(v) for k,v in expr.items()}
        out['selected_poles']=[p for p,v in zip(vars['caps'],vars['ps']) if solver.value(v)]
        out['selected_machines']=[p for p,v in zip(vars['machines'],vars['us']) if solver.value(v)]
        out['selected_centers']=[p for p,v in zip(vars['centers'],vars['zs']) if solver.value(v)]
    dump(args.name+'.json',out);print({k:v for k,v in out.items() if k not in ('stats','selected_poles','selected_machines','selected_centers')},flush=True)
def varsafe(args):return dict(vars(args))
if __name__=='__main__':main()
