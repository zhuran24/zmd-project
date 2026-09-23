#!/usr/bin/env python3
"""All strip body anchors, all types, continuous recipe rates and multi-item cuts.
Finite numerical search. Feasible points and status do not certify a game layout.
"""
import argparse,re,json,time,warnings
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from boundary_power import build,OUT,ROOT,cells
KINDS=['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']
COUNTS=dict(zip(KINDS,[68,51,32,6,6,32,16,3,3]))
SHAPE={k:('s' if k in ('粉碎机','精炼炉','塑形机','配件机') else 'm' if k in ('种植机','采种机') else 'l') for k in KINDS}
RATES=[18,34,5.5,10.5,34,17,0,17,9,5.5,5.5,6,11,21,5.5,10.5,.6,.55]
def recipes():
 kind=None;rr=[]
 for s in (ROOT/'《明日方舟：终末地》游戏规则.txt').read_text().split('\n配方\n')[1].splitlines():
  s=s.strip()
  if s in KINDS:kind=s
  if '→' not in s:continue
  a,b=s.split('→');b,t=b.split('，')
  def terms(s):return {m[1]:int(m[0]) for part in s.split('＋') for m in [re.fullmatch(r'\s*(\d+)\s+(.+?)\s*',part).groups()]}
  rr.append(dict(kind=kind,inputs=terms(a),outputs=terms(b),ticks=int(t.strip().split()[0])))
 assert len(rr)==18;return rr

def construct(b,P,cuts=(49,56,63),strengthened=True):
 m,bodies,sv,occ,cost,constant=build(b,P,True)
 m.row(list(cost.items()),hi=187-constant,label='area budget')
 if strengthened and b==17 and P==11:
  poles=[i for i,d in enumerate(bodies) if d['kind']=='p']
  m.row([(sv[i],bodies[i]['j']) for i in poles],4,4,'certified J=4')
  m.row([(sv[i],bodies[i]['loss']) for i in poles],36,36,'certified full power loss')
  m.row(list(cost.items()),187-constant,187-constant,'certified exact boundary cost')
  for i in poles:
   d=bodies[i]
   if d['loss']!=9*d['j']:m.ub[sv[i]]=0
  for i,d in enumerate(bodies):
   if d['kind'] not in ('s','m','l'):continue
   eligible=[j for j in poles if m.ub[sv[j]] and d['x']-6<=bodies[j]['x']<=d['x']+d['w']+4 and d['y']-6<=bodies[j]['y']<=d['y']+d['h']+4]
   m.row([(sv[j],1) for j in eligible]+[(sv[i],11)],hi=12,label='certified unique supplying pole')
 rr=recipes();items=sorted(set().union(*(set(r['inputs'])|set(r['outputs']) for r in rr)))
 regions=[(1,b)] + ([(b+53,70)] if b+53<70 else [])
 local=[i for i,d in enumerate(bodies) if d['x']+d['w']>49 and d['kind'] in ('s','m','l')]
 tv={};rv={}
 for i in local:
  d=bodies[i]
  for k in KINDS:
   if SHAPE[k]!=d['kind']:continue
   v=m.var('type:'+str(i)+':'+k,0,1,True);tv[i,k]=v
   pairs=[]
   for j,r in enumerate(rr):
    if r['kind']!=k:continue
    f=m.var(f'rate:{i}:{j}',0,min(RATES[j],1/r['ticks']));rv[i,j]=f;pairs.append((f,r['ticks']))
   m.row(pairs+[(v,-1)],hi=0,label='per machine capacity')
   # Total global idle time also imposed below. This individual bound is redundant.
   slack=COUNTS[k]-sum(RATES[j]*r['ticks'] for j,r in enumerate(rr) if r['kind']==k)
   m.row(pairs+[(v,-(1-slack))],lo=0,label='per machine minimum')
  m.row([(v,1) for (ii,k),v in tv.items() if ii==i]+[(sv[i],-1)],0,0,'type sum')
 for k in KINDS:
  ns=[(v,1) for (i,kk),v in tv.items() if kk==k]
  m.row(ns,hi=COUNTS[k],label='typed inventory')
  slack=COUNTS[k]-sum(RATES[j]*r['ticks'] for j,r in enumerate(rr) if r['kind']==k)
  m.row([(v,r['ticks']) for (i,j),v in rv.items() if (r:=rr[j])['kind']==k]+[(v,-1) for (i,kk),v in tv.items() if kk==k],lo=-slack,hi=0,label='global idle budget')
 for j,r in enumerate(rr):m.row([(v,1) for (i,jj),v in rv.items() if jj==j],hi=RATES[j],label='global recipe')
 # All 24 distinct bottom edge patterns. The other edge only relaxes this model.
 gp=[m.var('bottom_gap:'+str(g),0,1,True) for g in range(0,70,3)]
 ores=[]
 for g in range(0,70,3):
  starts=list(range(0,g,3))+list(range(g+1,70,3));assert len(starts)==23
  ores.append([x+1 for x in starts])
 m.row([(v,1) for v in gp],1,1,'one bottom pattern')
 for x in range(1,70):
  if (x,1) in occ:m.row([(occ[x,1],1)]+[(gp[g],1) for g,ps in enumerate(ores) if x in ps],hi=1,label='ore source transport')
 # Source identities may be fractionally assigned to their physical outlets;
 # each selected outlet still totals 1. This enlarges the real integer choice.
 blue={}
 for g,ps in enumerate(ores):
  for x in ps:
   v=m.var(f'blue:{g}:{x}',0,1);blue[g,x]=v;m.row([(v,1),(gp[g],-1)],hi=0,label='source identity')
 coreblue={}
 for i,d in enumerate(bodies):
  if d['kind']=='c' and d['x']+9>49:
   v=m.var(f'core blue:{i}',0,6);coreblue[i]=v;m.row([(v,1),(sv[i],-6)],hi=0,label='core ore')
 cut_info=[]
 for low,high in regions:
  for a in cuts:
   net={s:[] for s in items};cross=[]
   for i,d in enumerate(bodies):
    if d['x']+d['w']<=a or d['y']>=high or d['y']+d['h']<=low:continue
    assert low<=d['y'] and d['y']+d['h']<=high
    whole=d['x']>=a
    if not whole:cross.append((sv[i],d['h']))
    if d['kind']=='p':continue
    if d['kind']=='c':
     if whole:
      net['蓝铁矿'].append((coreblue[i],1));net['源矿'] += [(sv[i],6),(coreblue[i],-1)]
      net['高容谷地电池'].append((sv[i],-.6));net['精选荞愈胶囊'].append((sv[i],-.55))
     else:
      for s,lim,sign in [('蓝铁矿',6,1),('源矿',6,1),('高容谷地电池',.6,-1),('精选荞愈胶囊',.55,-1)]:
       v=m.var(f'crosscore:{low}:{a}:{i}:{s}',0,lim);m.row([(v,1),(sv[i],-lim)],hi=0,label='core interface');net[s].append((v,sign))
      # ore outputs combined at most six
      vv=[(len(m.names)-4,1),(len(m.names)-3,1),(sv[i],-6)];m.row(vv,hi=0,label='core sum')
     continue
    localrates=[(j,v) for (ii,j),v in rv.items() if ii==i]
    assert localrates
    if whole:
     for s in items:
      net[s]+=[(v,rr[j]['outputs'].get(s,0)-rr[j]['inputs'].get(s,0)) for j,v in localrates]
    else:
     for side,sgn in [('inputs',-1),('outputs',1)]:
      for s in items:
       expr=[(v,rr[j][side].get(s,0)) for j,v in localrates if rr[j][side].get(s,0)]
       if not expr:continue
       f=m.var(f'interface:{low}:{a}:{i}:{side}:{s}')
       m.row([(f,1)]+[(v,-coef) for v,coef in expr],hi=0,label='cross body commodity')
       net[s].append((f,sgn))
   if low==1:
    for g,ps in enumerate(ores):
     for x in ps:
      if x>=a:
       net['蓝铁矿'].append((blue[g,x],1));net['源矿'] += [(gp[g],1),(blue[g,x],-1)]
   tabs=[]
   for s in items:
    t=m.var(f'absolute:{low}:{a}:{s}');tabs.append(t)
    m.row(net[s]+[(t,-1)],hi=0,label='positive net')
    m.row([(i,-v) for i,v in net[s]]+[(t,-1)],hi=0,label='negative net')
   m.row([(v,1) for v in tabs]+cross,hi=high-low,label='cut capacity')
   cut_info.append(dict(first_column=a,rows=[low,high-1],capacity=high-low))
 return m,bodies,sv,dict(cuts=cut_info,recipe_count=len(rr),items=items,local_anchors=len(local),rate_vars=len(rv),typed_vars=len(tv),recipes=rr)

def main():
 p=argparse.ArgumentParser();p.add_argument('b',type=int);p.add_argument('P',type=int);p.add_argument('--seconds',type=float,default=60);p.add_argument('--base',action='store_true');a=p.parse_args()
 start=time.monotonic();m,bs,sv,info=construct(a.b,a.P,strengthened=not a.base);A=m.matrix();built=time.monotonic()-start
 print(json.dumps(dict(stage='built',seconds=built,vars=len(m.names),rows=len(m.rows)),ensure_ascii=False),flush=True)
 with warnings.catch_warnings():
  warnings.simplefilter('ignore');r=milp(np.zeros(len(m.names)),integrality=m.integ,bounds=Bounds(m.lb,m.ub),constraints=LinearConstraint(A,m.lo,m.hi),options={'time_limit':a.seconds,'threads':1,'disp':False})
 out=dict(b=a.b,P=a.P,strengthened=not a.base,status=int(r.status),message=r.message,elapsed=time.monotonic()-start,build_seconds=built,vars=len(m.names),rows=len(m.rows),model_info=info,certificate=False)
 if r.x is not None:
  out['chosen']=[d for i,d in enumerate(bs) if r.x[sv[i]]>.5];out['nonzero_values']={n:float(v) for n,v in zip(m.names,r.x) if abs(v)>1e-9}
 (OUT/(f'strip_flow_b{a.b}_P{a.P}'+('' if a.base else '_strengthened')+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in out.items() if k not in ('model_info','chosen','nonzero_values')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
