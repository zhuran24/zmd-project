"""连续分物品 LP；所有认证均逐行 Fraction 精确复核，浮点结果只供找证书。"""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']: os.environ[key]='1'
import warnings
from collections import defaultdict
from catalog import *

class LP:
 def __init__(self): self.keys=[];self.index={};self.rows=[]
 def var(self,key):
  if key not in self.index: self.index[key]=len(self.keys);self.keys.append(key)
  return self.index[key]
 def row(self,name,co,rel,rhs,basis):
  co={i:F(v) for i,v in co.items() if v};self.rows.append((name,co,rel,F(rhs),basis))
 def exact(self,x,positive=False):
  bad=[]
  if len(x)!=len(self.keys): return ['vector length']
  for i,v in enumerate(x):
   if v<0: bad.append('negative '+repr(self.keys[i]))
  for name,co,rel,rhs,basis in self.rows:
   val=sum((a*x[j] for j,a in co.items()),F(0))
   if (val!=rhs if rel=='eq' else val>rhs): bad.append({'row':name,'lhs':str(val),'relation':rel,'rhs':str(rhs),'basis':basis})
  if positive and x[self.index[('delta',)]]<=0: bad.append('delta must be strictly positive')
  return bad
 def matrix(self,rows=None):
  import numpy as np
  from scipy.sparse import coo_matrix
  eq=[];ub=[]
  for r in self.rows if rows is None else rows: (eq if r[2]=='eq' else ub).append(r)
  def mat(rs):
   rr=[];cc=[];vv=[]
   for i,(_,co,_,_,_) in enumerate(rs):
    for j,v in co.items(): rr.append(i);cc.append(j);vv.append(float(v))
   return coo_matrix((vv,(rr,cc)),shape=(len(rs),len(self.keys))).tocsr(),np.array([float(r[3]) for r in rs])
  A,b=mat(eq);C,d=mat(ub);return A,b,C,d,eq,ub
 def dual_certificate(self,ys,rs,objective,positive_rhs=False):
  if any(y>0 for y,r in zip(ys,rs) if r[2]=='le'): return None
  lhs=defaultdict(F)
  for y,r in zip(ys,rs):
   for j,a in r[1].items(): lhs[j]+=y*a
  if any(lhs[j]>objective.get(j,F(0)) for j in range(len(self.keys))): return None
  bound=sum((y*r[3] for y,r in zip(ys,rs)),F(0))
  if positive_rhs and bound<=0: return None
  return {'bound':str(bound),'multipliers':[{'row':r[0],'value':str(y)} for y,r in zip(ys,rs) if y], 'verified':'exact rational row signs, all columns, RHS'}
 def solve(self,time_limit=120):
  import numpy as np
  from scipy.optimize import linprog, OptimizeWarning
  from scipy.sparse import hstack, eye, vstack, csr_matrix
  A,b,C,d,eq,ub=self.matrix();n=len(self.keys);delta=self.index[('delta',)]
  opts={'threads':1,'time_limit':time_limit,'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}
  def run(obj,ae,be,au,bu,bounds=(0,None)):
   with warnings.catch_warnings():
    warnings.simplefilter('ignore',OptimizeWarning)
    return linprog(obj,A_ub=au,b_ub=bu,A_eq=ae,b_eq=be,bounds=bounds,method='highs',options=opts)
  # Exact trivial contradictions, valid even without a floating solver.
  for name,co,rel,rhs,basis in self.rows:
   if not co and (rhs!=0 if rel=='eq' else rhs<0):
    return {'status':'INFEASIBLE_EXACT','certificate':{'zero_row':name,'rhs':str(rhs),'relation':rel,'basis':basis}},None
  bd=[(0,None)]*n;bd[delta]=(0,0)
  base=run(np.zeros(n),A,b,C,d,bd)
  info={'base_solver_status':int(base.status),'base_message':base.message,'variables':n,'rows':len(self.rows),'threads':1,'time_limit_seconds':time_limit}
  if base.status==2:
   # Phase I: equality residual +/- and <= residual, objective total residual.
   ne,nu=len(eq),len(ub)
   ae=hstack([A,eye(ne),-eye(ne),csr_matrix((ne,nu))]).tocsr()
   au=hstack([C,csr_matrix((nu,2*ne)),-eye(nu)]).tocsr()
   phase=run(np.r_[np.zeros(n),np.ones(2*ne+nu)],ae,b,au,d)
   if phase.status==0:
    for den in [1000,10**6,10**9]:
     ys=[F(float(v)).limit_denominator(den) for v in list(phase.eqlin.marginals)+list(phase.ineqlin.marginals)]
     cert=self.dual_certificate(ys,eq+ub,{},True)
     if cert: return dict(info,status='INFEASIBLE_EXACT',certificate=cert),None
   return dict(info,status='NUMERICAL_UNRESOLVED',reason='浮点 infeasible；未取得精确 Farkas 证书'),None
  if base.status!=0: return dict(info,status='NUMERICAL_UNRESOLVED'),None
  objective=np.zeros(n);objective[delta]=-1
  res=run(objective,A,b,C,d);info.update(delta_solver_status=int(res.status),delta_message=res.message)
  if res.status!=0: return dict(info,status='NUMERICAL_UNRESOLVED'),None
  info['floating_delta']=float(res.x[delta])
  for den in [1000,10**6,10**9,10**12]:
   x=[F(float(v)).limit_denominator(den) for v in res.x]
   bad=self.exact(x,positive=True)
   if not bad: return dict(info,status='FEASIBLE_EXACT',certificate_denominator_limit=den,delta=str(x[delta]),exact_rows=len(self.rows)),x
  for den in [1000,10**6,10**9]:
   ys=[F(float(v)).limit_denominator(den) for v in list(res.eqlin.marginals)+list(res.ineqlin.marginals)]
   cert=self.dual_certificate(ys,eq+ub,{delta:F(-1)})
   if cert and F(cert['bound'])>=0:
    return dict(info,status='ZERO_SUPPORT_EXACT',certificate=cert),None
  return dict(info,status='NUMERICAL_UNRESOLVED',reason='浮点正数/残差未获精确正流见证',rational_failures=bad[:10]),None

def build(d,g):
 lp=LP();channels=d['design']['physical_channels'];byedge={(ref(e['from']),ref(e['to'])):e for e in channels}
 edge_ids={i:byedge[e]['id'] for i,e in enumerate(g.edges)}
 f={}
 for i,e in enumerate(g.edges):
  for it in byedge[e]['allowed_items']: f[i,it]=lp.var(('flow',edge_ids[i],it))
 batch={}
 for u in g.l['machines']:
  for r in u['recipe_ids']: batch[u['id'],r]=lp.var(('batch',u['id'],r))
 wireless={}
 for u in g.l['storage_boxes']:
  for it in ITEMS: wireless[u['id'],it]=lp.var(('wireless',u['id'],it))
 delta=lp.var(('delta',));lp.row('delta-cap',{delta:1},'le',1,'格式 §9 N5b')
 def terms(indices,it=None): return {j:1 for (i,a),j in f.items() if i in indices and (it is None or it==a)}
 def addto(co,more,mult=1):
  for j,a in more.items(): co[j]=co.get(j,F(0))+mult*a
 def row(name,co,rel,rhs,basis): lp.row(name,co,rel,rhs,basis)
 for i,(p,q) in enumerate(g.edges):
  co=terms([i]);row('channel-cap:'+edge_ids[i],co,'le',1,'约束·端口速率')
  row('positive:'+edge_ids[i],{delta:1,**{j:-a for j,a in co.items()}},'le',0,'格式 §9 N5b')
  for it in byedge[(p,q)]['allowed_items']:
   allowed=True
   if p in g.source_items: allowed &= it==g.source_items[p]
   if g.kind[q[0]]=='core': allowed &= it in TARGETS
   for port in [p,q]:
    u=g.units[port[0]]
    if g.kind[port[0]]=='gate': allowed &= u['filter'] in [None,it]
   if not allowed: row('forbidden:'+edge_ids[i]+':'+it,{f[i,it]:1},'eq',0,'规则·出库物品/物品准入口；约束·非成品零入库')
 for s in sorted(g.slots):
  for it in ITEMS:
   co=terms(g.sin[s],it);addto(co,terms(g.sout[s],it),-1);row('slot:'+repr(s)+':'+it,co,'eq',0,'规则·运输物品格/桥接器；约束·共用接货格余量')
  row('slot-cap:'+repr(s),terms(g.sout[s]),'le',1,'规则·滞留/运输单位；约束·端口速率')
 for u in g.l['transport']:
  if u['type']=='gate':
   cap=F(0) if u['cum'] is not None else F(u['k5'],5) if u['k5'] is not None else F(1)
   row('gate-cap:'+u['id'],terms(g.ins[u['id']]),'le',cap,'约束·准入累计')
 for u in g.l['machines']:
  uid=u['id'];co={batch[uid,r]:RECIPES[r][3] for r in u['recipe_ids']}
  row('machine-time:'+uid,co,'le',int(bool(g.powered[uid]) and u['settings']['manufacture_on']),'规则·制造/需电功能/开关/配方')
  for it in ITEMS:
   for side,indices,rindex in [('in',g.ins[uid],1),('out',g.outs[uid],2)]:
    co=terms(indices,it)
    for r in u['recipe_ids']: co[batch[uid,r]]=-RECIPES[r][rindex].get(it,0)
    row('machine:'+uid+':'+side+':'+it,co,'eq',0,'约束·双料逐机收支与存货界；规则·配方')
 for p,it in g.source_items.items():
  ix=[i for i in g.outs[p[0]] if g.edges[i][0]==p]
  row('source:'+repr(p),terms(ix,it),'eq',1,'约束·取货口配置/矿石需求；格式 §9.2')
 for u in g.l['storage_boxes']:
  uid=u['id']
  for it in ITEMS:
   co=terms(g.ins[uid],it);addto(co,terms(g.outs[uid],it),-1);co[wireless[uid,it]]=-1
   row('box:'+uid+':'+it,co,'eq',0,'规则·协议储存箱/传输；约束·传输箱不满')
   if it not in TARGETS or not g.powered[uid] or not u['settings']['transfer_on']:
    row('box-wireless-off:'+uid+':'+it,{wireless[uid,it]:1},'eq',0,'规则·需电功能/开关；约束·非成品零入库')
 for it,target in TARGETS.items():
  co=terms(g.ins['CORE'],it)
  for u in g.l['storage_boxes']: co[wireless[u['id'],it]]=1
  row('target:'+it,{j:-a for j,a in co.items()},'le',-F(target),'任务·目标；约束·入库途径')
 for feed in d['design'].get('logical_feeds',[]):
  for eid in feed['path']:
   row('logical-rate:'+feed['id']+':'+eid,{lp.index[('flow',eid,feed['item'])]:1},'eq',F(feed['rate']),'格式 §8.4 固定逻辑送料速率')
 # Nonempty full-factory support required independently of the LP's vacuous delta.
 lp.edge_ids=edge_ids;lp.f=f;lp.batch=batch;lp.wireless=wireless;return lp

def vector_from_witness(w,lp,d):
 expected={e['id'] for e in d['design']['physical_channels']}
 if {r['channel_id'] for r in w['channel_flows']}!=expected: raise ValueError('channel_flows 未逐条覆盖')
 if {(r['machine_id'],r['recipe_id']) for r in w['batch_rates']}!=set(lp.batch): raise ValueError('batch_rates 未逐配方覆盖')
 if {r['box_id'] for r in w['box_transfers']}!={u['id'] for u in d['layout']['storage_boxes']}: raise ValueError('box_transfers 未逐箱覆盖')
 x=[F(0)]*len(lp.keys)
 for row in w['channel_flows']:
  for it,v in row['rates'].items():
   key=('flow',row['channel_id'],it)
   if key not in lp.index: raise ValueError('见证物品不在 allowed_items: '+repr(key))
   x[lp.index[key]]=F(v)
 for row in w['batch_rates']: x[lp.index[('batch',row['machine_id'],row['recipe_id'])]]=F(row['rate'])
 for row in w['box_transfers']:
  for it,v in row['rates'].items(): x[lp.index[('wireless',row['box_id'],it)]]=F(v)
 x[lp.index[('delta',)]]=F(w['delta']);return x

def witness(lp,x,d):
 w={'channel_flows':[],'batch_rates':[],'box_transfers':[],'delta':str(x[lp.index[('delta',)]])}
 for e in d['design']['physical_channels']:
  w['channel_flows'].append({'channel_id':e['id'],'rates':{it:str(x[lp.index['flow',e['id'],it]]) for it in e['allowed_items'] if x[lp.index['flow',e['id'],it]]}})
 for u in d['layout']['machines']:
  for r in u['recipe_ids']: w['batch_rates'].append({'machine_id':u['id'],'recipe_id':r,'rate':str(x[lp.index['batch',u['id'],r]])})
 for u in d['layout']['storage_boxes']: w['box_transfers'].append({'box_id':u['id'],'rates':{it:str(x[lp.index['wireless',u['id'],it]]) for it in ITEMS if x[lp.index['wireless',u['id'],it]]}})
 return w
