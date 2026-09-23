#!/usr/bin/env python3
"""本候选专用独立固定图核验。仅支持本例的无箱P2P域，绝不充当一般全厂检查器。
不导入A/B/生成器代码。按正式配方和 fulllp.py 的输入/输出分离子问题建连续LP。
"""
import os, sys, json, hashlib, warnings, platform
from pathlib import Path
from collections import defaultdict, Counter
from fractions import Fraction as Q
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[k]='1'
sys.dont_write_bytecode=True
import numpy as np
import scipy
from scipy.optimize import linprog, OptimizeWarning
from scipy.sparse import coo_matrix
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[2]
raw=(HERE/'候选只读快照.json').read_bytes()
d=json.loads(raw);l=d['layout']
assert d['design']['class']=='p2p' and not l['storage_boxes'] and not l['vin'] and not l['vout']
assert all(u['type'] in ['belt','bridge'] for u in l['transport'])
assert 'logical_feeds' not in d['design'] and d['flow_witness'] is None
R={}
def recipe(rid,model,inp,out,t=1): R[rid]=(model,inp,out,t)
recipe('粉碎-源矿','粉碎机',{'源矿':1},{'源石粉末':1})
recipe('粉碎-蓝铁块','粉碎机',{'蓝铁块':1},{'蓝铁粉末':1})
recipe('粉碎-荞花','粉碎机',{'荞花':1},{'荞花粉末':2})
recipe('粉碎-砂叶','粉碎机',{'砂叶':1},{'砂叶粉末':3})
recipe('精炼-蓝铁矿','精炼炉',{'蓝铁矿':1},{'蓝铁块':1})
recipe('精炼-致密蓝铁','精炼炉',{'致密蓝铁粉末':1},{'钢块':1})
recipe('精炼-蓝铁粉末','精炼炉',{'蓝铁粉末':1},{'蓝铁块':1})
for stem,it in [('致密蓝铁','蓝铁粉末'),('致密源石','源石粉末'),('细磨荞花','荞花粉末')]:
    recipe('研磨-'+stem,'研磨机',{it:2,'砂叶粉末':1},{stem+'粉末':1})
recipe('塑形-钢质瓶','塑形机',{'钢块':2},{'钢质瓶':1})
recipe('配件-钢制零件','配件机',{'钢块':1},{'钢制零件':1})
for plant in ['荞花','砂叶']:
    recipe('种植-'+plant,'种植机',{plant+'种子':1},{plant:1})
    recipe('采种-'+plant,'采种机',{plant:1},{plant+'种子':2})
recipe('封装-电池','封装机',{'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1},5)
recipe('灌装-胶囊','灌装机',{'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1},5)
ITEMS=sorted(set().union(*(set(a)|set(b) for _,a,b,_ in R.values())))
TARGET={'高容谷地电池':Q(3,5),'精选荞愈胶囊':Q(11,20)}
assert len(ITEMS)==19 and len(R)==18
DELTA=[(1,0),(0,1),(-1,0),(0,-1)]
def nb(xy,s): return xy[0]+DELTA[s][0],xy[1]+DELTA[s][1]
def ref(v): return v['unit'],v['side'],v['offset']
def pjson(p): return dict(zip(['unit','side','offset'],p))
def cells(u):
    return [(u['x'],u['y'])] if 'x' in u else [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]
def perimeter(u,s):
    if s in [0,2]: return [(u['x1'] if s==0 else u['x0'],y) for y in range(u['y0'],u['y1']+1)]
    return [(x,u['y1'] if s==1 else u['y0']) for x in range(u['x0'],u['x1']+1)]
units={};kind={};occ={};ports={};at={};sources={}
for group in ['machines','warehouse_outlets','core','power_poles','transport']:
    for u in [l[group]] if group=='core' else l[group]:
        uid=u['id'];assert uid not in units;units[uid]=u;kind[uid]=u.get('type',group)
        for xy in cells(u):
            assert 0<=xy[0]<70 and 0<=xy[1]<70 and xy not in occ
            occ[xy]=uid
def trans(uid): return kind[uid] in ['belt','bridge']
def add_port(uid,s,o,xy,io):
    p=(uid,s,o);assert p not in ports and (xy,s) not in at
    ports[p]=(xy,io);at[xy,s]=p
for uid,u in units.items():
    k=kind[uid]
    if k=='machines':
        assert all(R[r][0]==u['model'] for r in u['recipe_ids'])
        for s,io in [(u['Din'],'in'),((u['Din']+2)%4,'out')]:
            for o,xy in enumerate(perimeter(u,s)):add_port(uid,s,o,xy,io)
    elif k=='warehouse_outlets':
        s=u['Dout'];add_port(uid,s,1,perimeter(u,s)[1],'out');sources[uid,s,1]=u['item']
    elif k=='core':
        for s in [u['Din'],(u['Din']+2)%4]:
            for o in range(1,8):add_port(uid,s,o,perimeter(u,s)[o],'in')
        for v in u['output_items']:
            s,o=v['side'],v['offset'];add_port(uid,s,o,perimeter(u,s)[o],'out');sources[uid,s,o]=v['item']
    elif k=='belt':
        add_port(uid,u['in_side'],0,cells(u)[0],'in');add_port(uid,u['out_side'],0,cells(u)[0],'out')
axes={}
for uid,u in units.items():
    if kind[uid]!='bridge':continue
    xy=cells(u)[0]
    assert all(kind.get(occ.get(nb(xy,s)))!='bridge' for s in range(4))
    for ax,sides,field in [('H',[0,2],'H_in'),('V',[1,3],'V_in')]:
        facing={s:ports[at[nb(xy,s),(s+2)%4]][1] for s in sides if (nb(xy,s),(s+2)%4) in at}
        assert not facing or len(facing)==2 and set(facing.values())=={'in','out'}
        got=next((s for s,io in facing.items() if io=='out'),None)
        assert u[field]==got
        if got is not None:axes[uid,ax]=got
for (uid,ax),s in axes.items():
    xy=cells(units[uid])[0];add_port(uid,s,0,xy,'in');add_port(uid,(s+2)%4,0,xy,'out')
edges=[]
for p,(xy,io) in ports.items():
    if io!='out':continue
    q=at.get((nb(xy,p[1]),(p[1]+2)%4))
    if q and ports[q][1]=='in' and (trans(p[0]) or trans(q[0])):edges.append((p,q))
edges.sort();claimed={(ref(e['from']),ref(e['to'])):e for e in d['design']['physical_channels']}
assert len(claimed)==len(d['design']['physical_channels']) and set(edges)==set(claimed)
def slot(p): return (p[0],'H' if p[1]%2==0 else 'V') if kind[p[0]]=='bridge' else (p[0],'single')
slots={(u['id'],'single') for u in l['transport'] if u['type']=='belt'}|set(axes)
ins=defaultdict(list);outs=defaultdict(list);si=defaultdict(list);so=defaultdict(list)
for i,(p,q) in enumerate(edges):
    outs[p[0]].append(i);ins[q[0]].append(i)
    if trans(p[0]):so[slot(p)].append(i)
    if trans(q[0]):si[slot(q)].append(i)
power={u['id']:[p['id'] for p in l['power_poles'] if u['x0']<=p['x0']+6 and u['x1']>=p['x0']-5 and u['y0']<=p['y0']+6 and u['y1']>=p['y0']-5] for u in l['machines']}
paths=[];covered=[]
for i,(p,q) in enumerate(edges):
    if trans(p[0]):continue
    path=[];j=i
    while True:
        assert j not in path;path.append(j);q=edges[j][1]
        if not trans(q[0]):break
        s=slot(q);assert len(si[s])==len(so[s])==1;j=so[s][0]
    labels=[claimed[edges[ii]]['allowed_items'] for ii in path]
    assert len(labels[0])==1 and all(x==labels[0] for x in labels)
    paths.append(path);covered+=path
assert sorted(covered)==list(range(len(edges)))
# Independent exact-empty rectangle search: enumerate x ranges and scan y runs.
best=(0,0);rects=[]
for x0 in range(65):
    free=[True]*70
    for x1 in range(x0,70):
        free=[ok and (x1,y) not in occ for y,ok in enumerate(free)]
        w=x1-x0+1
        if w<6:continue
        run=0
        for y in range(71):
            if y<70 and free[y]:run+=1;continue
            if run>=6:
                score=w*run,min(w,run);r={'x0':x0,'y0':y-run,'x1':x1,'y1':y-1}
                if score>best:best=score;rects=[r]
                elif score==best:rects.append(r)
            run=0
keys=[];f={};batches={}
def var(k):keys.append(k);return len(keys)-1
for i,e in enumerate(edges):
    for it in claimed[e]['allowed_items']:f[i,it]=var(('flow',claimed[e]['id'],it))
for u in l['machines']:
    for rid in u['recipe_ids']:batches[u['id'],rid]=var(('batch',u['id'],rid))
rows=[]
def terms(ids,it=None):return {j:Q(1) for (i,k),j in f.items() if i in ids and (it is None or k==it)}
def combine(a,b,mult=-1):
    z=dict(a)
    for j,v in b.items():z[j]=z.get(j,Q(0))+mult*v
    return {j:v for j,v in z.items() if v}
def row(name,co,relation,rhs):rows.append((name,{j:Q(v) for j,v in co.items() if v},relation,Q(rhs)))
for i in range(len(edges)):row('channel-cap:'+str(i),terms([i]),'le',1)
for s in sorted(slots):
    for it in ITEMS:row('slot:'+repr(s)+':'+it,combine(terms(si[s],it),terms(so[s],it)),'eq',0)
    row('slot-cap:'+repr(s),terms(so[s]),'le',1)
for u in l['machines']:
    uid=u['id']
    for it in ITEMS:
        for indices,ri,side in [(ins[uid],1,'in'),(outs[uid],2,'out')]:
            co=terms(indices,it)
            for r in u['recipe_ids']:co[batches[uid,r]]=-Q(R[r][ri].get(it,0))
            row('machine:'+uid+':'+side+':'+it,co,'eq',0)
    row('time:'+uid,{batches[uid,r]:R[r][3] for r in u['recipe_ids']},'le',int(bool(power[uid]) and u['settings']['manufacture_on']))
source_rows=[];disconnected=[]
for p,it in sources.items():
    es=[i for i in outs[p[0]] if edges[i][0]==p]
    co=terms(es,it);source_rows.append(('source:'+repr(p),co,'eq',Q(1)))
    for other in ITEMS:
        if other!=it:row('source-forbidden:'+repr(p)+':'+other,terms(es,other),'eq',0)
    if not es:
        front=nb(ports[p][0],p[1]);disconnected.append({'port':pjson(p),'item':it,'front':front,'front_occupant':occ.get(front),'front_kind':kind.get(occ.get(front))})
for it in ITEMS:
    if it not in TARGET:row('warehouse-forbidden:'+it,terms(ins['CORE'],it),'eq',0)
base_rows=list(rows)
target_rows=[('target:'+it,{j:-v for j,v in terms(ins['CORE'],it).items()},'le',-t) for it,t in TARGET.items()]
strict_rows=base_rows+source_rows+target_rows
relaxed_rows=base_rows+[(name,co,'le',rhs) for name,co,_,rhs in source_rows]
def matrices(rs):
    eq=[r for r in rs if r[2]=='eq'];le=[r for r in rs if r[2]=='le']
    def make(rr):
        a=[];b=[];v=[]
        for i,(_,co,_,_) in enumerate(rr):
            for j,k in co.items():a.append(i);b.append(j);v.append(float(k))
        return coo_matrix((v,(a,b)),shape=(len(rr),len(keys))).tocsr(),np.array([float(r[3]) for r in rr])
    A,B=make(eq);C,D=make(le);return A,B,C,D,eq,le
def solve(rs,objective,presolve=True):
    A,B,C,D,eq,le=matrices(rs);cost=np.zeros(len(keys))
    for j,v in objective.items():cost[j]=float(v)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',OptimizeWarning)
        res=linprog(cost,A_eq=A,b_eq=B,A_ub=C,b_ub=D,bounds=(0,None),method='highs',options={'threads':1,'time_limit':60,'presolve':presolve,'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    info={'status':int(res.status),'message':res.message,'variables':len(keys),'rows':len(rs),'equalities':len(eq),'inequalities':len(le),'iterations':int(res.nit),'presolve':presolve}
    if res.success:
        x=[Q(float(v)).limit_denominator(10**9) for v in res.x]
        bad=[]
        for name,co,rel,rhs in rs:
            lhs=sum((v*x[j] for j,v in co.items()),Q(0))
            if (lhs!=rhs if rel=='eq' else lhs>rhs):bad.append(name)
        assert not bad and all(v>=0 for v in x)
        yy=[Q(float(v)).limit_denominator(10**9) for v in list(res.eqlin.marginals)+list(res.ineqlin.marginals)]
        col=defaultdict(Q)
        for y,(_,co,_,_) in zip(yy,eq+le):
            for j,v in co.items():col[j]+=y*v
        bound=sum((y*r[3] for y,r in zip(yy,eq+le)),Q(0))
        primal=sum((Q(v)*x[j] for j,v in objective.items()),Q(0))
        assert all(y<=0 for y in yy[len(eq):]) and all(col[j]<=Q(objective.get(j,0)) for j in range(len(keys))) and bound==primal
        info.update(exact_primal=True,exact_dual=True,objective=str(primal),nonzero_variables=sum(v!=0 for v in x),certificate={'bound':str(bound),'multipliers':[{'row':r[0],'value':str(y)} for y,r in zip(yy,eq+le) if y]})
        return info,x
    return info,None
strict,_=solve(strict_rows,{})
strict_no_presolve,_=solve(strict_rows,{},False)
relaxed_target,_=solve(relaxed_rows+target_rows,{})
# Maximize each item's fresh production (ore=actual extraction) with source<=1 and no targets.
# These 19 independent maxima are diagnostics, not a single attainable joint target witness.
per_item={}
for it in ITEMS:
    obj={j:-Q(R[r][2].get(it,0)) for (uid,r),j in batches.items() if R[r][2].get(it,0)}
    if it in ['源矿','蓝铁矿']:
        obj={j:-v for p,k in sources.items() if k==it for j,v in terms([i for i in outs[p[0]] if edges[i][0]==p],it).items()}
    info,x=solve(relaxed_rows,obj);assert x is not None
    per_item[it]={'strict_target_feasible_flow':None,'source_relaxed_max_production':str(-Q(info['objective'])),'solver':info}
    (HERE/('独立LP-诊断见证-'+it+'.json')).write_text(json.dumps({'item':it,'scope':'sources<=1,no targets; each item separately maximized','nonzero_values':[{'key':keys[j],'value':str(v)} for j,v in enumerate(x) if v],'solver':info},ensure_ascii=False,indent=2)+'\n')
all_flow,x=solve(relaxed_rows,{j:-1 for j in f.values()});assert x is not None
disconnected.sort(key=lambda v:(v['port']['unit'],v['port']['side'],v['port']['offset']))
counts=Counter(u['model'] for u in l['machines']);ic=Counter();oc=Counter()
for u in l['machines']:ic[u['model']]+=len(ins[u['id']]);oc[u['model']]+=len(outs[u['id']])
result={
    'candidate_sha256':hashlib.sha256(raw).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'basis_sha256':hashlib.sha256((ROOT/'求解器/会议成果/会议3/seat-opus-1/fulllp.py').read_bytes()).hexdigest(),
    'source_fingerprints_at_run':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']},
    'environment':{'python':platform.python_version(),'scipy':scipy.__version__,'numpy':np.__version__,'method':'scipy.optimize.linprog(method=highs)','threads':1},
    'pass':strict['status']==0,'strict':strict,'strict_without_presolve':strict_no_presolve,'source_relaxed_with_targets':relaxed_target,
    'exact_contradictions':[{'name':name,'relation':rel,'rhs':str(rhs),'coefficients':{}} for name,co,rel,rhs in strict_rows if not co and (rhs!=0 if rel=='eq' else rhs<0)],
    'geometry':{'units':len(units),'occupied':len(occ),'transport':len(l['transport']),'bridges':sum(kind[u['id']]=='bridge' for u in l['transport']),'active_axes':len(axes),'transport_slots':len(slots),'channels':len(edges),'paths':len(paths),'S':sum(not trans(p[0]) for p,q in edges),'R':sum(not trans(q[0]) for p,q in edges),'E':sum(trans(p[0]) and trans(q[0]) for p,q in edges),'empty_rectangle':{'area':best[0],'short_side':best[1],'rectangles':rects},'power':power,'machine_counts':dict(counts),'machine_input_channels':dict(ic),'machine_output_channels':dict(oc),'source_items':dict(Counter(sources.values())),'connected_sources':len(sources)-len(disconnected),'disconnected_sources':disconnected,'physical_channels_rebuilt':[{'from':pjson(p),'to':pjson(q)} for p,q in edges],'path_details':[{'from':pjson(edges[path[0]][0]),'to':pjson(edges[path[-1]][1]),'item':claimed[edges[path[0]]]['allowed_items'][0],'channels':[claimed[edges[i]]['id'] for i in path]} for path in paths]},
    'per_item':per_item,'source_relaxed_max_total_channel_flow':all_flow,
    'product_paths':[{'source':edges[path[0]][0][0],'target':edges[path[-1]][1][0],'item':claimed[edges[path[0]]]['allowed_items'][0]} for path in paths if edges[path[-1]][1][0]=='CORE'],
    'packaging_inputs':{u['id']:len(ins[u['id']]) for u in l['machines'] if u['model']=='封装机'},
    'filling_inputs':{u['id']:len(ins[u['id']]) for u in l['machines'] if u['model']=='灌装机'},
    'scope':'fixed candidate geometry, recipe_ids, allowed_items; continuous flows and batch rates free; no logical feeds; no runtime or other layouts',
}
(HERE/'独立LP.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(HERE/'独立LP矩阵.json').write_text(json.dumps({'variables':keys,'rows':[{'name':name,'terms':[[j,str(v)] for j,v in co.items()],'relation':rel,'rhs':str(rhs)} for name,co,rel,rhs in strict_rows]},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pass':strict['status']==0,'strict':strict,'relaxed_target':relaxed_target,'disconnected_sources':len(disconnected),'channels':len(edges),'paths':len(paths),'total_relaxed_flow':all_flow['objective'],'per_item_max':{it:v['source_relaxed_max_production'] for it,v in per_item.items()}},ensure_ascii=False))
