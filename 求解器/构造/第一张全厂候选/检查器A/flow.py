"""联合连续 LP；所有接受结论由 Fraction 逐行复算，浮点求解器只提供候选证书。
规则：配方、制造、滞留、物品格、协议储存箱、物品准入口。
格式§9；约束#9,12,14,17,18,25,29,31,32,35,36,47。
"""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import warnings
from collections import defaultdict
from fractions import Fraction as Q
from catalog import *

class Linear:
 def __init__(self):self.keys=[];self.index={};self.rows=[]
 def var(self,k):
  if k not in self.index:self.index[k]=len(self.keys);self.keys.append(k)
  return self.index[k]
 def le(self,terms,b,tag):
  d=defaultdict(Q)
  for j,c in terms:d[j]+=Q(c)
  self.rows.append(({j:c for j,c in d.items()if c},Q(b),tag))
 def eq(self,terms,b,tag):
  terms=list(terms);self.le(terms,b,tag);self.le([(j,-c)for j,c in terms],-Q(b),tag)
 def exact(self,x):
  if len(x)!=len(self.keys):return ['变量数错误']
  bad=[{'negative_variable':self.keys[j],'value':str(v)}for j,v in enumerate(x)if v<0]
  for i,(a,b,tag)in enumerate(self.rows):
   v=sum((c*x[j]for j,c in a.items()),Q())
   if v>b:bad.append({'row':i,'tag':tag,'lhs':str(v),'rhs':str(b)})
  return bad
 def dual(self,y,c):
  if len(y)!=len(self.rows)or any(v>0 for v in y):return None
  col=[Q()for _ in self.keys]
  for v,(a,b,t)in zip(y,self.rows):
   for j,k in a.items():col[j]+=v*k
  if any(a>Q(b)for a,b in zip(col,c)):return None
  return sum((y[i]*row[1]for i,row in enumerate(self.rows)),Q())
 def solve(self,c,time_limit=60,phase=False):
  from scipy.optimize import linprog
  from scipy.sparse import coo_matrix,hstack,eye
  import numpy as np
  rr=[];cc=[];vv=[]
  for i,(a,b,t)in enumerate(self.rows):
   for j,k in a.items():rr.append(i);cc.append(j);vv.append(float(k))
  A=coo_matrix((vv,(rr,cc)),shape=(len(self.rows),len(self.keys))).tocsr();b=np.array([float(row[1])for row in self.rows]);cost=np.array(c,dtype=float)
  if phase:A=hstack([A,-eye(len(self.rows),format='csr')],format='csr');cost=np.r_[np.zeros(len(self.keys)),np.ones(len(self.rows))]
  with warnings.catch_warnings():
   warnings.filterwarnings('ignore',message='Unrecognized options detected')
   res=linprog(cost,A_ub=A,b_ub=b,bounds=(0,None),method='highs',options={'time_limit':time_limit,'threads':1,'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
  meta={'solver_status':int(res.status),'message':res.message,'rows':len(self.rows),'variables':len(self.keys),'threads':1}
  if not res.success:return None,None,meta
  for den in [1000,1000000,1000000000,1000000000000]:
   x=[Q(float(v)).limit_denominator(den)for v in res.x[:len(self.keys)]]
   if not self.exact(x):
    y=[Q(float(v)).limit_denominator(1000000000)for v in res.ineqlin.marginals]
    bound=self.dual(y,[0]*len(self.keys)if phase else c)
    cert=None if bound is None else {'bound':str(bound),'multipliers':[{'row':i,'value':str(v)}for i,v in enumerate(y)if v],'inequality':'A^T y <= c, y <= 0; c*x >= b*y'}
    return x,cert,meta
  y=[Q(float(v)).limit_denominator(1000000000)for v in res.ineqlin.marginals]
  bound=self.dual(y,[0]*len(self.keys)if phase else c)
  if bound is not None and (not phase or bound>0):return None,{'bound':str(bound),'multipliers':[{'row':i,'value':str(v)}for i,v in enumerate(y)if v],'inequality':'A^T y <= c, y <= 0; c*x >= b*y'},meta
  return None,None,meta

class Flow:
 def __init__(self,g):
  self.g=g;self.d=g.d;self.m=Linear();self.f={};self.batch={};self.wire={};self.delta=None
 def terms(self,edges,item=None):return [(j,1)for(i,k),j in self.f.items()if i in edges and(item is None or item==k)]
 def build(self):
  g=self.g;m=self.m
  for i,c in enumerate(g.cd):
   for it in c['allowed_items']:self.f[i,it]=m.var(('flow',c['id'],it))
  for u in g.lay['machines']:
   for rid in u['recipe_ids']:self.batch[u['id'],rid]=m.var(('batch',u['id'],rid))
  for u in g.lay['storage_boxes']:
   for it in ITEMS:self.wire[u['id'],it]=m.var(('wire',u['id'],it))
  # Capacities apply to real channels and shared item slots, not to declared logical edges.
  for i in range(len(g.channels)):m.le(self.terms([i]),1,'端口速率')
  for uid,u in g.units.items():
   typ=g.types[uid];ii=g.inc[uid];oo=g.out[uid]
   if g.is_t(uid):
    slots=[(uid,'H'),(uid,'V')]if typ=='bridge'else[(uid,)]
    for s in slots:
     for it in ITEMS:m.eq(self.terms(g.si[s],it)+[(j,-v)for j,v in self.terms(g.so[s],it)],0,'运输物品格分物品守恒')
     m.le(self.terms(g.so[s]),1,'运输格共享容量；桥按轴')
    if typ=='gate':
     if u['filter']is not None:
      for it in ITEMS:
       if it!=u['filter']:m.eq(self.terms(ii,it),0,'准入口身份')
     if u['k5']is not None:m.le(self.terms(ii),Q(u['k5'],5),'准入累计·k/5')
     if u['cum']is not None:m.eq(self.terms(ii),0,'准入累计·长期零流')
   elif typ=='machine':
    for it in ITEMS:
     m.eq(self.terms(ii,it)+[(self.batch[uid,r],-RECIPES[r][1].get(it,0))for r in u['recipe_ids']],0,'逐机输入配方守恒')
     m.eq(self.terms(oo,it)+[(self.batch[uid,r],-RECIPES[r][2].get(it,0))for r in u['recipe_ids']],0,'逐机输出配方守恒')
    m.le([(self.batch[uid,r],RECIPES[r][3])for r in u['recipe_ids']],1 if g.power[uid]and u['settings']['manufacture_on']else 0,'制造时间/供电/开关')
   elif typ=='box':
    for it in ITEMS:
     j=self.wire[uid,it];m.eq(self.terms(ii,it)+[(j,-1)]+[(j,-v)for j,v in self.terms(oo,it)],0,'箱体逐物品入=物理出+无线')
     if it not in TARGETS or not g.power[uid]or not u['settings']['transfer_on']:m.eq([(j,1)],0,'非成品零入库/无线开关及供电')
   elif typ=='core':
    for it in ITEMS:
     if it not in TARGETS:m.eq(self.terms(ii,it),0,'非成品零入库')
  for p,it in g.sources.items():
   es=[i for i in g.out[p[0]]if g.channels[i][0]==p]
   for k in ITEMS:m.eq(self.terms(es,k),1 if k==it else 0,'52个真实矿口逐口满速')
  for it,v in TARGETS.items():
   terms=self.terms(g.inc['CORE'],it)+[(j,1)for(u,k),j in self.wire.items()if k==it]
   m.le([(j,-a)for j,a in terms],-Q(v),'目标成品入库')
  for feed in self.d['design'].get('logical_feeds',[]):
   byid={c['id']:i for i,c in enumerate(g.cd)}
   for cid in feed['path']:
    i=byid[cid];m.eq(self.terms([i],feed['item']),Q(feed['rate']),'固定逻辑路径速率')
  return self
 def add_delta(self):
  self.delta=self.m.var(('delta',));self.m.le([(self.delta,1)],1,'delta<=1')
  for i in range(len(self.g.channels)):self.m.le([(self.delta,1)]+[(j,-a)for j,a in self.terms([i])],0,'N5b 共同正流下界')
 def from_witness(self,w):
  x=[Q()for _ in self.m.keys];seen=set()
  def put(k,v):
   if k not in self.m.index:raise ValueError('见证未知变量 '+str(k))
   if k in seen:raise ValueError('见证重复变量 '+str(k))
   seen.add(k);x[self.m.index[k]]=Q(v)
  channel_ids=[v['channel_id']for v in w['channel_flows']]
  if len(channel_ids)!=len(set(channel_ids))or set(channel_ids)!={c['id']for c in self.g.cd}:raise ValueError('见证通道须恰覆盖')
  for v in w['channel_flows']:
   for k,a in v['rates'].items():put(('flow',v['channel_id'],k),a)
  for v in w['batch_rates']:put(('batch',v['machine_id'],v['recipe_id']),v['rate'])
  if {k for k in seen if k[0]=='batch'}!={k for k in self.m.keys if k[0]=='batch'}:raise ValueError('见证配方须恰覆盖')
  bids=[v['box_id']for v in w['box_transfers']]
  if len(bids)!=len(set(bids))or set(bids)!={u['id']for u in self.g.lay['storage_boxes']}:raise ValueError('见证箱体须恰覆盖')
  for v in w['box_transfers']:
   for k,a in v['rates'].items():put(('wire',v['box_id'],k),a)
  put(('delta',),w['delta']);return x
 def witness(self,x):
  g=self.g
  return {'channel_flows':[{'channel_id':c['id'],'rates':{it:str(x[j])for(i2,it),j in self.f.items()if i2==i and x[j]>0}}for i,c in enumerate(g.cd)],'batch_rates':[{'machine_id':u,'recipe_id':r,'rate':str(x[j])}for(u,r),j in self.batch.items()],'box_transfers':[{'box_id':u['id'],'rates':{it:str(x[j])for(u2,it),j in self.wire.items()if u2==u['id']and x[j]>0}}for u in g.lay['storage_boxes']],'delta':str(x[self.delta])}
 def run(self,time_limit=60):
  self.add_delta();m=self.m
  if not self.g.channels:return {'status':'violation','reason':'全厂空支持不能真空通过'},None
  w=self.d['flow_witness']
  if w is not None:
   try:x=self.from_witness(w)
   except ValueError as e:return {'status':'violation','reason':str(e)},None
   bad=m.exact(x)
   if bad or x[self.delta]<=0:return {'status':'violation','reason':'附带见证精确核验失败','rows':bad},None
   return {'status':'checked','method':'supplied rational witness','delta':str(x[self.delta]),'exact_rows':len(m.rows),'witness':self.witness(x)},x
  # Base feasibility first (delta forced 0), then maximize common delta on fixed support.
  base=Linear();base.keys=list(m.keys);base.index=dict(m.index);base.rows=list(m.rows);base.le([(self.delta,1)],0,'基础可行性 delta=0')
  xb,dual,meta=base.solve([0]*len(m.keys),time_limit)
  if xb is None:
   xp,cert,pm=base.solve([0]*len(m.keys),time_limit,phase=True)
   if cert:return {'status':'violation','reason':'精确 Farkas 证书：固定布局/设置/设计物品/配方的基础平均流不可行','certificate':cert,'base':meta,'phase1':pm},None
   if xp is None:return {'status':'unresolved','reason':'基础 LP 未获精确可行点或不可行证书','base':meta,'phase1':pm},None
  c=[0]*len(m.keys);c[self.delta]=-1
  x,dual,meta=m.solve(c,time_limit)
  if x is not None and x[self.delta]>0:return {'status':'checked','method':'LP proposal + exact rational primal verification','delta':str(x[self.delta]),'exact_rows':len(m.rows),'solver':meta,'witness':self.witness(x),'optimal_delta_certified':False},x
  # Rational dual bound certifies delta <= 0; otherwise a floating zero is inconclusive.
  if dual and Q(dual['bound'])>=0:return {'status':'violation','reason':'精确对偶界 delta<=0，仅否定固定支持','certificate':dual,'solver':meta},None
  return {'status':'unresolved','reason':'未获得严格正有理见证；浮点零不作否证','solver':meta},None
