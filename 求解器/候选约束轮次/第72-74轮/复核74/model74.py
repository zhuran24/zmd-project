"""Independent linear integer model and independently computed interval cuts.

All mathematics/geometry rebuilt locally. Reads only capacities checked by
certificates74.py. Optional original witness is used only for fixed replay.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from geometry74 import *
from collections import defaultdict
import argparse,time,hashlib

def get_units(project=True):
    machines=boundary_domain(); units=list(machines)
    for cap in json.loads((OUT/'capacities.json').read_text()):
        if cap['loss']>13: continue
        x,y=cap['p']; r=[x,y,2,2]
        useful=(cap['j'] or not rect(*r).isdisjoint(WEIGHT) or
                any(u['kind']!='c' and overlap(u['r'],(x-5,y-5,12,12)) for u in machines))
        if not project or useful: units.append(dict(kind='p',r=r,axis=-1,ports=[],needs=[],**cap))
    return units

FORBID={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}

def interval_table(units,line,limit=13):
    ordered=sorted(line); index={c:i for i,c in enumerate(ordered)}
    options=defaultdict(set); representatives=defaultdict(list)
    for u in units:
        common=rect(*u['r'])&line
        if not common: continue
        ids=sorted(index[c] for c in common); a=ids[0]; b=ids[-1]+1
        assert ids==list(range(a,b))
        full=(len(common)==(u['r'][3] if len({x for x,y in line})==1 else u['r'][2]))
        typ=('C' if u['kind']=='c' else 'P' if u['kind']=='p' else 'M') if full else 'T'
        option=(b,typ,int(u['kind']=='c'),int(u['kind']=='p'),u.get('loss',0),-2*u.get('j',0))
        options[a].add(option); representatives[(a,b,typ)].append(u)
    # Check every prohibited complete-projection adjacency using actual cells.
    checked=0
    for (a,b,t),ls in representatives.items():
        for (c,d,v),rs in representatives.items():
            if b!=c or (t,v) not in FORBID: continue
            for u in ls:
                for w in rs:
                    checked+=1; bodies=rect(*u['r'])|rect(*w['r'])
                    clash=overlap(u['r'],w['r']) or any(sum(p not in bodies for p in port)<n
                        for z in (u,w) for port,n in zip(z['ports'],z['needs']))
                    assert clash,('invalid adjacency ban',u,w)
    states=[{} for _ in range(len(line)+1)];states[0][('',0,0,0)]=0
    def relax(pos,key,val):
        if val<states[pos].get(key,10000): states[pos][key]=val
    for a in range(len(line)):
        for (prev,c,p,l),cost in list(states[a].items()):
            relax(a+1,('',c,p,l),cost+1)
            for b,t,dc,dp,dl,score in options[a]:
                if (prev,t) in FORBID or c+dc>1 or p+dp>12 or l+dl>limit: continue
                relax(b,(t,c+dc,p+dp,l+dl),cost+score)
    tab={}
    for (prev,c,p,l),cost in states[-1].items():
        tab[c,p,l]=min(tab.get((c,p,l),10000),cost)
    return sorted([*k,v] for k,v in tab.items()),checked

class Linear:
    def __init__(self): self.bounds=[];self.rows=[]
    def var(self,lo=0,hi=1):
        n=len(self.bounds);self.bounds.append((lo,hi));return n
    def row(self,pairs,lo=None,hi=None):
        coef=Counter()
        for i,v in pairs: coef[i]+=v
        self.rows.append((dict((i,v) for i,v in coef.items() if v),lo,hi))

def build(j,cap,project=True,fixed=None,cuts=True):
    units=get_units(project); m=Linear(); choose=[m.var() for _ in units]
    inc=defaultdict(list)
    for i,u in enumerate(units):
        for c in rect(*u['r']):inc[c].append(i)
    occupied={c:m.var() for c in sorted(inc)}
    for c,v in occupied.items(): m.row([(v,1)]+[(i,-1) for i in inc[c]],0,0)
    for i,u in enumerate(units):
        for port,n in zip(u['ports'],u['needs']):
            m.row([(i,n)]+[(occupied[c],1) for c in port if c in occupied],hi=len(port))
    # Two one-hot selections, joined only by the actual common corner.
    warehouse=[[m.var() for k in range(24)] for axis in range(2)]
    for axis,vs in enumerate(warehouse):
        m.row([(v,1) for v in vs],1,1)
        for k,v in enumerate(vs):
            for n in range(23):
                a=3*n+(n>=k); t=a+1
                c=(1,t) if axis==0 else (t,1)
                if c in occupied: m.row([(v,1),(occupied[c],1)],hi=1)
    m.row([(warehouse[0][0],1),(warehouse[1][0],1)],lo=1)
    weak=[]
    for i,u in enumerate(units):
        if u['kind']!='l': continue
        # If selected, choose exactly one input side with >=3-ex free cells.
        side=[m.var(),m.var()]; ex=m.var();weak.append(ex)
        m.row([(v,1) for v in side]+[(i,-1)],0,0);m.row([(ex,1),(i,-1)],hi=0)
        for port,v in zip(u['ports'],side):
            m.row([(occupied[c],1) for c in port if c in occupied]+[(v,3),(ex,-1)],hi=len(port))
    m.row([(i,1) for i in weak],hi=1)
    poles=[i for i,u in enumerate(units) if u['kind']=='p']
    m.row([(i,1) for i in poles],0 if project else 10,10)
    if j is not None: m.row([(i,units[i]['j']) for i in poles],j,j)
    for kind,count in [('s',131),('m',48),('l',38),('c',1)]:
        m.row([(i,1) for i,u in enumerate(units) if u['kind']==kind],hi=count)
    fees=[(i,units[i]['loss']) for i in poles]
    for i,u in enumerate(units):
        if u['kind'] not in ('s','m','l'): continue
        cover=[p for p in poles if overlap(u['r'],(units[p]['r'][0]-5,units[p]['r'][1]-5,12,12))]
        z=m.var(0,9); fees.append((z,1))
        m.row([(p,1) for p in cover]+[(i,-1)],lo=0)
        m.row([(z,1),(i,-9)],hi=0)
        # selected: z=n-1; absent: z=0 and 0<=n<=10 remains free.
        m.row([(z,1)]+[(p,-1) for p in cover]+[(i,-10)],lo=-11)
        m.row([(z,1)]+[(p,-1) for p in cover]+[(i,1)],hi=0)
    m.row(fees,hi=13)
    score=m.var(-100,500)
    gains=[sum(WEIGHT[c] for c in rect(*u['r']))+2*u.get('j',0) for u in units]
    m.row([(score,1)]+[(i,g) for i,g in enumerate(gains)],298,298)
    m.row([(score,1)],hi=cap)
    cut_stats=[]
    if cuts:
        for line in LINES:
            tab,n=interval_table(units,line)
            vs=[m.var() for _ in tab];m.row([(v,1) for v in vs],1,1)
            touched=[i for i,u in enumerate(units) if not rect(*u['r']).isdisjoint(line)]
            for col,coeff in [(0,lambda u:int(u['kind']=='c')),(1,lambda u:int(u['kind']=='p')),(2,lambda u:u.get('loss',0))]:
                m.row([(i,coeff(units[i])) for i in touched]+[(v,-t[col]) for t,v in zip(tab,vs)],0,0)
            m.row([(i,len(rect(*units[i]['r'])&line)+2*units[i].get('j',0)) for i in touched]+
                  [(v,t[3]) for t,v in zip(tab,vs)],hi=len(line))
            cut_stats.append(dict(states=len(tab),adjacencies=n,table=tab))
    if fixed:
        keys={(b['kind'],(b['x'],b['y'],b['w'],b['h']),{'h':0,'v':1,'-':-1}[b['axis']]) for b in fixed['chosen']}
        actual={(u['kind'],tuple(u['r']),u['axis']) for u in units}
        assert keys<=actual
        for i,u in enumerate(units):m.row([(i,1)],int((u['kind'],tuple(u['r']),u['axis']) in keys),int((u['kind'],tuple(u['r']),u['axis']) in keys))
    return m,units,score,cut_stats

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--j',type=int);ap.add_argument('--cap',type=int,default=184)
    ap.add_argument('--engine',choices=['cp','highs'],default='highs');ap.add_argument('--seconds',type=int,default=420)
    ap.add_argument('--full',action='store_true');ap.add_argument('--fixed',action='store_true');ap.add_argument('--no-cuts',action='store_true');ap.add_argument('--name',required=True)
    args=ap.parse_args();start=time.monotonic()
    witness=json.loads((ROUNDS/'第72-74轮/推导72/witness185.json').read_text()) if args.fixed else None
    m,units,score,tabs=build(args.j,args.cap,not args.full,witness,not args.no_cuts)
    print('built',len(units),len(m.bounds),len(m.rows),'seconds',time.monotonic()-start,flush=True)
    fingerprint=hashlib.sha256(json.dumps([m.bounds,m.rows],sort_keys=True).encode()).hexdigest()
    data=dict(arguments=vars(args),units=len(units),variables=len(m.bounds),constraints=len(m.rows),matrix_sha256=fingerprint,
              source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cuts=tabs)
    values=None
    if args.engine=='cp':
        import ortools
        from ortools.sat.python import cp_model
        model=cp_model.CpModel();vs=[model.new_int_var(a,b,str(i)) for i,(a,b) in enumerate(m.bounds)]
        for row,lo,hi in m.rows:
            expr=sum(vs[i]*c for i,c in row.items())
            if lo is not None:model.add(expr>=lo)
            if hi is not None:model.add(expr<=hi)
        solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.max_time_in_seconds=args.seconds
        solver.parameters.random_seed=74;solver.parameters.log_search_progress=True;solver.parameters.linearization_level=2
        st=solver.solve(model);data.update(status=solver.status_name(st),version=ortools.__version__,stats=solver.response_stats())
        if st in (cp_model.FEASIBLE,cp_model.OPTIMAL): values=[solver.value(v) for v in vs]
    else:
        import scipy,numpy as np
        from scipy.optimize import milp,Bounds,LinearConstraint
        from scipy.sparse import coo_matrix
        rr=[];cc=[];vv=[]
        for j,(row,_,_) in enumerate(m.rows):
            for i,c in row.items():rr.append(j);cc.append(i);vv.append(c)
        A=coo_matrix((np.array(vv,dtype=float),(rr,cc)),shape=(len(m.rows),len(m.bounds))).tocsc()
        res=milp(np.zeros(len(m.bounds)),integrality=np.ones(len(m.bounds)),bounds=Bounds(*zip(*m.bounds)),
                 constraints=LinearConstraint(A,[-np.inf if a is None else a for _,a,b in m.rows],[np.inf if b is None else b for _,a,b in m.rows]),
                 options={'time_limit':args.seconds,'disp':True,'mip_rel_gap':0.0,'threads':1})
        data.update(status=int(res.status),message=res.message,version=scipy.__version__)
        if res.x is not None: values=[int(round(x)) for x in res.x]
    if values is not None:
        for row,lo,hi in m.rows:
            v=sum(values[i]*c for i,c in row.items()); assert (lo is None or v>=lo) and (hi is None or v<=hi)
        assert all(a<=v<=b for v,(a,b) in zip(values,m.bounds))
        data.update(S=values[score],chosen=[u for i,u in enumerate(units) if values[i]])
    data['seconds']=time.monotonic()-start;dump(args.name+'.json',data)
    print({k:v for k,v in data.items() if k not in ('cuts','stats','chosen')},flush=True)

if __name__=='__main__':main()
