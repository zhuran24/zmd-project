"""规则数据和连续 LP。图重建不得从这里导入；两个检查器各自提交其重建的边。"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import json,re,hashlib,math
from pathlib import Path
from fractions import Fraction as Q
from collections import defaultdict,Counter
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[3]
FILES={'rules':'《明日方舟：终末地》游戏规则.txt','task':'求解任务.txt','constraints':'求解约束.txt'}
FINGERPRINTS={'rules':'52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3','task':'1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac','constraints':'a67c18dec5f6ae59c41e8620d270007f20c2d3e5b202521d0cca12f616bca3df'}
REC={
'粉碎-源矿':('粉碎机',{'源矿':1},{'源石粉末':1},1),'粉碎-蓝铁块':('粉碎机',{'蓝铁块':1},{'蓝铁粉末':1},1),
'粉碎-荞花':('粉碎机',{'荞花':1},{'荞花粉末':2},1),'粉碎-砂叶':('粉碎机',{'砂叶':1},{'砂叶粉末':3},1),
'精炼-蓝铁矿':('精炼炉',{'蓝铁矿':1},{'蓝铁块':1},1),'精炼-致密蓝铁':('精炼炉',{'致密蓝铁粉末':1},{'钢块':1},1),'精炼-蓝铁粉末':('精炼炉',{'蓝铁粉末':1},{'蓝铁块':1},1),
'研磨-致密蓝铁':('研磨机',{'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1},1),'研磨-致密源石':('研磨机',{'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1},1),'研磨-细磨荞花':('研磨机',{'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1},1),
'塑形-钢质瓶':('塑形机',{'钢块':2},{'钢质瓶':1},1),'配件-钢制零件':('配件机',{'钢块':1},{'钢制零件':1},1),
'种植-荞花':('种植机',{'荞花种子':1},{'荞花':1},1),'种植-砂叶':('种植机',{'砂叶种子':1},{'砂叶':1},1),
'采种-荞花':('采种机',{'荞花':1},{'荞花种子':2},1),'采种-砂叶':('采种机',{'砂叶':1},{'砂叶种子':2},1),
'封装-电池':('封装机',{'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1},5),'灌装-胶囊':('灌装机',{'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1},5)}
KINDS={'粉碎机':'小','精炼炉':'小','配件机':'小','塑形机':'小','种植机':'中','采种机':'中','研磨机':'大','封装机':'大','灌装机':'大'}
MIN={'粉碎机':68,'精炼炉':51,'研磨机':32,'塑形机':6,'配件机':6,'种植机':32,'采种机':16,'封装机':3,'灌装机':3}
ITEMS=sorted(set(i for _,a,b,_ in REC.values() for i in list(a)+list(b)));PRODUCTS={'高容谷地电池':Q(3,5),'精选荞愈胶囊':Q(11,20)}
D=[(1,0),(0,1),(-1,0),(0,-1)]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def key(p):return p['unit'],p['side'],p['offset']
def ref(p):return dict(unit=p[0],side=p[1],offset=p[2])
def edgekey(e):return key(e['from']),key(e['to'])
def load(p):
 def hook(ps):
  d={}
  for k,v in ps:
   if k in d:raise ValueError('重复键 '+k)
   d[k]=v
  return d
 return json.loads(Path(p).read_text(),object_pairs_hook=hook)
def strict(c):
 errs=[]
 def keys(x,req,opt=()):
  if not isinstance(x,dict):raise ValueError('应为对象')
  if set(x)-set(req)-set(opt) or set(req)-set(x):raise ValueError(f'字段集合错误 {set(x)} vs {req}')
 def integer(v,lo,hi):
  if type(v)!=int or not lo<=v<=hi:raise ValueError(f'整数越界或类型错误 {v}')
 def enum(v,opts):
  if v not in opts:raise ValueError(f'枚举错误 {v}')
 def ident(v):
  if not isinstance(v,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_.-]{0,63}',v):raise ValueError('Id错误')
 def rate(v,pos=False):
  if not isinstance(v,str) or not re.fullmatch(r'0|[1-9][0-9]*(?:/[1-9][0-9]*)?',v):raise ValueError('Rate错误')
  if str(Q(v))!=v or Q(v)<0 or (pos and Q(v)==0):raise ValueError('Rate非规范')
 def bounds(u):
  for k in ('x0','x1','y0','y1'):integer(u[k],0,69)
  if u['x1']<u['x0'] or u['y1']<u['y0']:raise ValueError('负范围')
 def port(p):
  keys(p,['unit','side','offset']);ident(p['unit']);integer(p['side'],0,3);integer(p['offset'],0,8)
 def texts(xs,opts):
  if type(xs)!=list or not xs or len(xs)!=len(set(xs)) or not set(xs)<=set(opts):raise ValueError('集合错误')
 try:
  keys(c,['schema','candidate_id','source_fingerprints','targets','layout','empty_rectangle','design','flow_witness'],['provenance'])
  enum(c['schema'],['full-factory-static-v1']);ident(c['candidate_id']);keys(c['source_fingerprints'],FILES)
  for k,f in FILES.items():
   if c['source_fingerprints'][k]!=FINGERPRINTS[k] or sha(ROOT/f)!=FINGERPRINTS[k]:raise ValueError('正式文件指纹不符')
  for p in c.get('provenance',[]):
   keys(p,['path','sha256'])
   if not isinstance(p['path'],str) or Path(p['path']).is_absolute() or '..' in Path(p['path']).parts:raise ValueError('来源路径错误')
   if sha(ROOT/p['path'])!=p['sha256']:raise ValueError('来源指纹错误')
  if c['targets']!={i:str(q) for i,q in PRODUCTS.items()}:raise ValueError('目标错误')
  l=c['layout'];keys(l,['W','H','machines','warehouse_outlets','core','power_poles','storage_boxes','transport','vin','vout'])
  for k in ('W','H'):integer(l[k],70,70)
  if l['vin']!=[] or l['vout']!=[]:raise ValueError('虚拟接口禁止')
  ids=[]
  for cat in ('machines','warehouse_outlets','power_poles','storage_boxes','transport'):
   if type(l[cat])!=list or len(l[cat])>4900:raise ValueError('单位数组错误')
   for u in l[cat]:ident(u['id']);ids.append(u['id'])
  ids.append(l['core']['id'])
  if len(set(ids))!=len(ids):raise ValueError('单位Id重复')
  for m in l['machines']:
   keys(m,['id','model','kind','x0','y0','x1','y1','Din','recipe_ids','settings'],['role']);bounds(m);integer(m['Din'],0,3);enum(m['model'],KINDS)
   if m['kind']!=KINDS[m['model']]:raise ValueError('机型尺寸类别不符')
   texts(m['recipe_ids'],[r for r,v in REC.items() if v[0]==m['model']]);keys(m['settings'],['manufacture_on'])
   if type(m['settings']['manufacture_on'])!=bool:raise ValueError('开关错误')
  for u in l['warehouse_outlets']:keys(u,['id','x0','y0','x1','y1','Dout','item']);bounds(u);integer(u['Dout'],0,1);enum(u['item'],ITEMS)
  u=l['core'];keys(u,['id','x0','y0','x1','y1','Din','output_items']);bounds(u);integer(u['Din'],0,3)
  if u['id']!='CORE':raise ValueError('核心身份错误')
  for q in u['output_items']:keys(q,['side','offset','item']);integer(q['side'],0,3);integer(q['offset'],0,8);enum(q['item'],ITEMS)
  for u in l['power_poles']:keys(u,['id','x0','y0','x1','y1','orientation']);bounds(u);integer(u['orientation'],0,0)
  for u in l['storage_boxes']:keys(u,['id','x0','y0','x1','y1','Din','settings']);bounds(u);integer(u['Din'],0,3);keys(u['settings'],['transfer_on'])
  fields={'belt':['in_side','out_side'],'bridge':['H_in','V_in'],'splitter':['in_side'],'merger':['out_side'],'gate':['in_side','filter','k5','cum']}
  for t in l['transport']:
   enum(t['type'],fields);keys(t,['id','x','y','type']+fields[t['type']]);integer(t['x'],0,69);integer(t['y'],0,69)
   for k in ['in_side','out_side']:
    if k in t:integer(t[k],0,3)
   if t['type']=='belt' and t['in_side']==t['out_side']:raise ValueError('同侧带')
   if t['type']=='bridge':
    for k,opts in [('H_in',[None,0,2]),('V_in',[None,1,3])]:enum(t[k],opts)
  bounds(c['empty_rectangle']);keys(c['empty_rectangle'],['x0','y0','x1','y1'])
  ds=c['design'];keys(ds,['class','physical_channels','restrictions'],['source_bindings','logical_feeds']);enum(ds['class'],['p2p','n_restricted'])
  if ds['class']!='p2p' or l['storage_boxes'] or any(t['type'] not in ['belt','bridge'] for t in l['transport']):raise ValueError('本检查器仅实现p2p域，其他域拒绝认证')
  chids=[]
  for e in ds['physical_channels']:keys(e,['id','from','to','allowed_items']);ident(e['id']);chids.append(e['id']);port(e['from']);port(e['to']);texts(e['allowed_items'],ITEMS)
  if len(chids)!=len(set(chids)):raise ValueError('通道id重复')
  rid=[]
  for r in ds['restrictions']:
   keys(r,['id','source','statement','coverage_loss','release_obligations','failure_scope']);ident(r['id']);rid.append(r['id']);texts(r['source'],['dynamic','shape','numeric'])
   for k in ['statement','coverage_loss','release_obligations','failure_scope']:
    if not isinstance(r[k],str) or not r[k].strip():raise ValueError('限制文本缺失')
  if len(rid)!=len(set(rid)) or not set(['N1','N2','N3a','N3b','N4a','N4b','N5a','N5b']+[f'P{i}' for i in range(1,7)])<=set(rid):raise ValueError('限制登记缺失/重复')
  for b in ds.get('source_bindings',[]):keys(b,['logical_source_id','port']);ident(b['logical_source_id']);port(b['port'])
  for f in ds.get('logical_feeds',[]):
   keys(f,['id','from','to','item','rate','path']);ident(f['id']);port(f['from']);port(f['to']);enum(f['item'],ITEMS);rate(f['rate'],True)
   if Q(f['rate'])>1 or not f['path'] or len(set(f['path']))!=len(f['path']) or not set(f['path'])<=set(chids):raise ValueError('逻辑路径格式错误')
  if c['flow_witness'] is not None:raise ValueError('此版要求LP另产精确见证，非null输入见证未实现，拒绝认证')
 except (ValueError,KeyError,TypeError) as e:errs.append(str(e))
 return errs

def solve_lp(c,edges,units,powered,tag):
 """每条重建边按所声明物品建变量；运输桥拆轴；机器输入输出分开。
 浮点LP解后逐行用Fraction精确检查；不可行时输出精确Farkas证书。
 """
 from scipy.optimize import linprog
 from scipy.sparse import coo_matrix
 declared={edgekey(e):e for e in c['design']['physical_channels']}; cols=[];eq=defaultdict(dict);rhs={};ub=defaultdict(dict);ubr={};edgevars=defaultdict(list)
 def put(rows,k,j,v):rows[k][j]=rows[k].get(j,0)+v
 def slot(p):
  u=units[p[0]]
  return (p[0],p[1]%2) if u.get('type')=='bridge' else (p[0],0)
 sources={ (u['id'],u['Dout'],1):u['item'] for u in c['layout']['warehouse_outlets']}
 sources.update({('CORE',q['side'],q['offset']):q['item'] for q in c['layout']['core']['output_items']})
 # Source equality for every physical source, even disconnected ports.
 for p,i in sources.items():rhs[('source',p,i)]=Q(1);eq[('source',p,i)]
 for i,q in PRODUCTS.items():ubr[('target',i)]=-q;ub[('target',i)]
 for k,(a,b) in enumerate(edges):
  for item in declared.get((a,b),{}).get('allowed_items',ITEMS):
   j=len(cols);cols.append(('flow',k,item));edgevars[k].append(j)
   put(ub,('edge',k),j,1);ubr[('edge',k)]=Q(1)
   if 'type' in units[a[0]]:
    put(eq,('transport',slot(a),item),j,-1);put(ub,('slot',slot(a)),j,1);ubr[('slot',slot(a))]=Q(1)
   elif a in sources:
    if sources[a]==item:put(eq,('source',a,item),j,1)
    else:put(eq,('forbidden_source',a,item),j,1)
   elif 'model' in units[a[0]]:put(eq,('machine_out',a[0],item),j,1)
   else:put(eq,('forbidden_from',a,item),j,1)
   if 'type' in units[b[0]]:put(eq,('transport',slot(b),item),j,1)
   elif 'model' in units[b[0]]:put(eq,('machine_in',b[0],item),j,1)
   elif b[0]=='CORE':
    if item in PRODUCTS:put(ub,('target',item),j,-1)
    else:put(eq,('nonproduct_warehouse',item),j,1)
   else:put(eq,('forbidden_to',b,item),j,1)
 for m in c['layout']['machines']:
  for r in m['recipe_ids']:
   _,inputs,outputs,t=REC[r];j=len(cols);cols.append(('batch',m['id'],r))
   for i,v in inputs.items():put(eq,('machine_in',m['id'],i),j,-v)
   for i,v in outputs.items():put(eq,('machine_out',m['id'],i),j,-v)
   put(ub,('time',m['id']),j,t);ubr[('time',m['id'])]=Q(int(m['id'] in powered and m['settings']['manufacture_on']))
 # Optional exact logical-feed equalities (only for physically complete paths).
 edgeidx={edge:k for k,edge in enumerate(edges)};declid={e['id']:edgekey(e) for e in c['design']['physical_channels']}
 for f in c['design'].get('logical_feeds',[]):
  for eid in f['path']:
   k=edgeidx.get(declid[eid]);row=('fixed_feed',f['id'],eid);rhs[row]=Q(f['rate'])
   for j in edgevars.get(k,[]):
    if cols[j][2]==f['item']:put(eq,row,j,1)
   eq[row]
 def matrix(rows,ks,n):
  rr=[];cc=[];vv=[]
  for i,k in enumerate(ks):
   for j,v in rows[k].items():
    if v:rr.append(i);cc.append(j);vv.append(float(v))
  return coo_matrix((vv,(rr,cc)),shape=(len(ks),n)).tocsr()
 ek=list(eq);uk=list(ub);n=len(cols)
 A=matrix(eq,ek,n);b=[float(rhs.get(k,0)) for k in ek];U=matrix(ub,uk,n);v=[float(ubr[k]) for k in uk]
 r=linprog([0]*n,A_ub=U,b_ub=v,A_eq=A,b_eq=b,bounds=(0,None),method='highs',options={'threads':1})
 result=dict(status=int(r.status),message=r.message,variables=n,equalities=len(ek),inequalities=len(uk),base_feasible=r.status==0,certified=False,scope='固定候选的真实结构通道、设计物品集、配方与设定；不覆盖其他布局或运行')
 # Empty nonzero equality gives a direct exact infeasibility witness.
 empty=[dict(row=repr(k),rhs=str(rhs.get(k,0))) for k in ek if not any(eq[k].values()) and rhs.get(k,0)!=0]
 if r.status!=0:
  result['empty_equalities']=empty
  if empty:result.update(certified=True,certificate_kind='精确矛盾 0 = 非零常数')
  else:
   # Auxiliary LP searches a separating multiplier, then all columns checked rationally.
   from scipy.sparse import hstack,vstack,csr_matrix
   ne,nu=len(ek),len(uk);obj=[0.]*(2*ne+nu)
   C=hstack([A.T,-A.T,U.T]).tocsr();zrhs=b+[-q for q in b]+v
   sep=vstack([-C,csr_matrix([zrhs])]).tocsr()
   z=linprog(obj,A_ub=sep,b_ub=[0.]*n+[-1.],bounds=(0,None),method='highs',options={'threads':1})
   if z.status==0:
    zs=[Q(float(x)).limit_denominator(1000000) for x in z.x];yy=[zs[j]-zs[ne+j] for j in range(ne)];zz=zs[2*ne:]
    acc=[Q(0)]*n
    for i,k in enumerate(ek):
     for j,x in eq[k].items():acc[j]+=yy[i]*x
    for i,k in enumerate(uk):
     for j,x in ub[k].items():acc[j]+=zz[i]*x
    bound=sum(yy[i]*rhs.get(k,0) for i,k in enumerate(ek))+sum(zz[i]*ubr[k] for i,k in enumerate(uk))
    if min(acc,default=0)>=0 and bound<0 and min(zz,default=0)>=0:
     cert={'equalities':[{ 'row':repr(k),'multiplier':str(yy[i])} for i,k in enumerate(ek) if yy[i]],'inequalities':[{'row':repr(k),'multiplier':str(zz[i])} for i,k in enumerate(uk) if zz[i]],'rhs':str(bound),'min_column':str(min(acc,default=0))}
     result.update(certified=True,certificate_kind='精确Farkas组合：非负变量线性组合 <= 负数',certificate=cert)
  return result
 # Maximise common positive flow on all actual edges.
 delta=len(cols);cols.append(('delta',));
 for k in range(len(edges)):
  row=('positive',k);ubr[row]=Q(0);ub[row][delta]=1
  for j in edgevars[k]:put(ub,row,j,-1)
 uk=list(ub);r2=linprog([0]*delta+[-1],A_ub=matrix(ub,uk,len(cols)),b_ub=[float(ubr[k]) for k in uk],A_eq=matrix(eq,ek,len(cols)),b_eq=b,bounds=[(0,None)]*delta+[(0,1)],method='highs',options={'threads':1})
 result.update(delta_status=int(r2.status),delta_float=float(r2.x[-1]) if r2.status==0 else None)
 if r2.status!=0:return result
 xx=[Q(float(v)).limit_denominator(1000000) for v in r2.x]
 errors=[]
 for k in ek:
  val=sum(v*xx[j] for j,v in eq[k].items())
  if val!=rhs.get(k,0):errors.append(('eq',repr(k),str(val),str(rhs.get(k,0))))
 for k in uk:
  val=sum(v*xx[j] for j,v in ub[k].items())
  if val>ubr[k]:errors.append(('ub',repr(k),str(val),str(ubr[k])))
 if min(xx)<0:errors.append(('negative',))
 result.update(exact_errors=errors,delta_exact=str(xx[-1]),certified=not errors and xx[-1]>0 and bool(edges))
 result['flows']=[dict(edge=k,item=i,rate=str(xx[j])) for j,(ty,k,i) in enumerate(cols[:-1]) if ty=='flow' and xx[j]]
 result['batches']=[dict(machine=k,recipe=i,rate=str(xx[j])) for j,(ty,k,i) in enumerate(cols[:-1]) if ty=='batch']
 return result
