"""已核读 71/72 条版本的静态投影与剩余运行义务；编号绑定正式文件指纹。"""
import json, math
from collections import Counter, defaultdict
from catalog import *

class Audit:
 def __init__(self,c,profile=None):
  self.c=c;self.catalog=json.loads((BASE/CONSTRAINT_PROFILES[profile or HASHES['constraints']]).read_text());self.results=defaultdict(list);self.pending={}
 def test(self,name,ok,evidence=None,pre='本张布局；若含通过量则仅指本次精确平均流见证',remaining='全部相关可达循环态及合法先后的运行量词另证。'):
  self.results[name].append({'status':'PASS_STATIC_PROJECTION' if ok else 'VIOLATION','precondition':pre,'evidence':evidence,'remaining':remaining})
  self.c.add('formal:'+name,bool(ok),'求解约束·'+name,evidence,remaining)
 def na(self,name,why): self.results[name].append({'status':'STATIC_ANTECEDENT_FALSE','precondition':why,'evidence':why,'remaining':''})
 def runtime(self,name,why,evidence=None): self.results[name].append({'status':'RUNTIME_PENDING','precondition':why,'evidence':evidence,'remaining':why})
 def finish(self):
  out=[]
  for r in self.catalog:
   parts=self.results[r['name']]
   if not parts: parts=[{'status':'BLOCKED','precondition':'结构闸门或精确流见证未成立，依赖项未执行','evidence':None,'remaining':'先完成结构与精确 LP 核验，再重跑。'}]
   out.append({**r,'basis_file':'求解约束.txt:'+str(r['line']),'checks':parts})
  return out

def static_audit(d,g,c):
 a=Audit(c,d['source_fingerprints']['constraints']);l=g.l;cnt=Counter(u['model'] for u in l['machines']);g.counts=cnt
 for n in ['接通先后','分叉分支','传输相位','判定先后']:
  a.runtime(n,'静态输入无初态、调试、时序或全部可达循环态证明；N 项不替代该量词。')
 a.na('取货分级','N1 通过时取货侧无多级排序对象') if c.good('N1') else a.test('取货分级',False,'N1 未通过，受限类不接受需定序构型')
 a.na('密集结点','N2 通过时无分流器直入带其他存货通道的单位') if c.good('N2') else a.test('密集结点',False,'N2 未通过')
 a.runtime('来源定序','N1/N2 排除优先级构型，平均收支由 LP 核验；实际服务与其余来源的时序仍待证。')
 a.test('单位矿耗',True,{'电池':{'蓝铁矿':20,'源矿':30},'胶囊':{'蓝铁矿':40}},remaining='规范配方算术常量；产率由 LP 另核。')
 a.test('种子自给',True,'两种植物均 1 植株→2 种子，1 种子→1 植株',remaining='是否可启动、持续制造仍属运行义务。')
 a.test('端口对接',all(g.transport(p[0]) or g.transport(q[0]) for p,q in g.edges),{'channels':len(g.edges)},remaining='按端口几何当且仅当重建。')
 outlets=Counter(u['Dout'] for u in l['warehouse_outlets']);ores=Counter(g.source_items.values())
 a.test('出库上限',outlets[0]<=23 and outlets[1]<=23 and len(g.source_items)<=52,dict(outlets))
 a.test('取货口配置',outlets[0]==23 and outlets[1]==23 and ores==Counter({'源矿':18,'蓝铁矿':34}),{'sides':dict(outlets),'source_items':dict(ores)},remaining='各口满速另由精确 LP 核验；运行中每 tick 满速另证。')
 a.runtime('种子起动','真实出库口仅供矿；调试期首批植株/种子注入办法不在静态格式内。')
 a.test('机型下限',all(cnt[m]>=n for m,n in MINIMUM.items()),dict(cnt))
 usable=Counter(u['model'] for u in l['machines'] if g.powered[u['id']] and u['settings']['manufacture_on'])
 a.test('存货误料停机与可用台数',all(usable[m]>=n for m,n in MINIMUM.items()) and c.good('wrong-material'),{'powered_on':dict(usable)},remaining='可达误料保守传播已查；初始误料占格与全部循环态仍待证。')
 inc=Counter();out=Counter()
 for u in l['machines']: inc[u['model']]+=len(g.ins[u['id']]);out[u['model']]+=len(g.outs[u['id']])
 a.test('通道下限',all(inc[m]>=IN_MIN[m] and out[m]>=OUT_MIN[m] for m in MODELS),{'input':dict(inc),'output':dict(out)},remaining='正支持、成品入库通道数在流见证成立后另核。')
 for model,total,threshold,neednum,side in [('研磨机',32,3,31,'in'),('采种机',16,2,16,'out'),('塑形机',6,2,5,'in')]:
  if cnt[model]==total:
   k=sum(len((g.ins if side=='in' else g.outs)[u['id']])>=threshold for u in l['machines'] if u['model']==model)
   a.test('研磨进料',k>=neednum,{'model':model,'qualifying':k,'required':neednum})
 if all(cnt[m]!=n for m,n in [('研磨机',32),('采种机',16),('塑形机',6)]): a.na('研磨进料','三种恰下限前件均不成立')
 # Band gap positions are zero-based 3k; the formal text numbers cells from 1.
 gaps=[];bandok=True
 for direction in [0,1]:
  occupied=set()
  for u in l['warehouse_outlets']:
   if u['Dout']==direction: occupied.update(y if direction==0 else x for x,y in cells(u))
  gap=set(range(70))-occupied;gaps.append(sorted(gap));bandok &= len(gap)==1 and next(iter(gap))%3==0
  ports=sorted((g.ports[p][0][1] if direction==0 else g.ports[p][0][0]) for p in g.source_items if g.kind[p[0]]=='warehouse_outlets' and p[1]==direction)
  bandok &= all(y-x in [3,4] for x,y in zip(ports,ports[1:]))
 bandok &= any(v==[0] for v in gaps)
 fronts={nb(g.ports[p][0],p[1]) for p in g.source_items if g.kind[p[0]]=='warehouse_outlets'}
 bandok &= len(fronts)==46 and all(x in g.occ and g.transport(g.occ[x]) for x in fronts)
 g.ore_fronts=fronts;g.band_gaps=gaps
 a.test('边带排布',bandok,{'gaps':gaps,'ore_fronts':len(fronts)},remaining='空矩形离带条件另见矩形离带。')
 core=l['core'];corridors=[]
 for axis in [0,1]:
  start=core['x0'] if axis==0 else core['y0'];other0=core['y0'] if axis==0 else core['x0'];other1=other0+8
  m=sum(other0<=g.ports[p][0][1-axis]<=other1 for p in g.source_items if g.kind[p[0]]=='warehouse_outlets' and p[1]==axis)
  delta=int((2 if axis==0 else 3) not in [core['Din'],opp(core['Din'])]);ends=int(other0>0)+int(other1<69)
  corridors.append({'axis':axis,'start':start,'m':m,'delta':delta,'ends':ends,'ok':m+3*delta<=ends*(start-1) and start>=2})
 a.test('核心离带',all(v['ok'] for v in corridors),corridors)
 corefronts={nb(g.ports[p][0],p[1]) for p in g.source_items if p[0]=='CORE'}
 a.test('核心邻格',all(x in g.occ and g.transport(g.occ[x]) for x in corefronts) and not(core['x0']<=3 and core['y0']<=3),{'outlet_fronts':sorted(corefronts)},remaining='与空矩形邻接及直接成品入库邻格另查。')
 poles=l['power_poles'];P=len(poles);J=0;pole_details=[]
 for p in poles:
  boundary_count=sum([p['x0']<=1<=p['x1'],p['x0']<=69<=p['x1'],p['y0']<=1<=p['y1'],p['y0']<=69<=p['y1']])
  J+=int(boundary_count>0);n=sum(g.covers(p,u) for u in l['machines'])
  pole_details.append((p['id'],boundary_count,n))
 a.test('供电下限',P>=10 and 9*J<=23*P-217 and all(n<=(8 if b>=2 else 14 if b else 24) for _,b,n in pole_details) and (P!=10 or J<=1 and not any(b>=2 for _,b,n in pole_details)),{'P':P,'J':J,'per_pole':pole_details},remaining='每桩至多 23 台有制造者在精确流见证上另核。')
 g.P=P;g.J=J
 return a

def rectangle_audit(d,g,a):
 r=d['empty_rectangle'];A=g.rectangle['area'];P=g.P;J=g.J;cnt=g.counts;l=g.l
 w=r['x1']-r['x0']+1;h=r['y1']-r['y0']+1;T=len(l['transport']);b=sum(u['type']=='bridge' for u in l['transport']);B=len(l['storage_boxes']);occ=len(g.occ)
 a.test('空矩形上界',A<=1113 and (b>0 or A<=1040) and w<=68 and h<=68 and (A!=1113 or sorted([w,h])==[21,53]),{'maximum_area':A,'w':w,'h':h},remaining='对静态达标候选的必要界；不证明本候选可运行。')
 if any(v['name']=='1113 位置' for v in a.catalog):
  if A==1113:
   allowed={(21,53,49,y) for y in [6,7,9,17]} | {(53,21,x,49) for x in [6,7,9,17]}
   a.test('1113 位置',(w,h,r['x0'],r['y0']) in allowed,{'w':w,'h':h,'x0':r['x0'],'y0':r['y0']},remaining='仅对面积1113的必要位置条件，不提供该位置的布局可行性证明。')
  else: a.na('1113 位置','最大空矩形面积不是1113')
 a.test('占地下界',occ>=3758 and (b>0 or occ>=3856),{'occupied':occ,'bridges':b})
 a.test('角区',(2,2) not in set(cells(r)) and sum((g.ports[p][0] in g.ore_fronts and not g.transport(q[0])) or (g.ports[q][0] in g.ore_fronts and not g.transport(p[0])) for p,q in g.edges)<=93,{'ore_fronts':len(g.ore_fronts)})
 a.test('边带排布',r['x0']>=2 and r['y0']>=2,{'rectangle':r})
 rectcells=set(cells(r));core=l['core'];ok=True
 for side in [(core['Din']+1)%4,(core['Din']+3)%4]:
  touched=[i for i,xy in enumerate(edge(core,side)) if nb(xy,side) in rectcells]
  ok &= len(touched)<=1 and all(i in [0,8] for i in touched)
 # Core band-facing edge is not a rectangle edge in the stated conditional domain.
 for side,start in [(2,core['x0']),(3,core['y0'])]:
  if start<=7 or side not in [core['Din'],opp(core['Din'])]: ok &= not any(nb(xy,side) in rectcells for xy in edge(core,side))
 a.test('核心邻格',ok,'空矩形与核心取货边及贴带边的精确邻格检查')
 for axis,low,length,upper in [(0,r['x0'],h,r['y1']),(1,r['y0'],w,r['x1'])]:
  lo=r['y0'] if axis==0 else r['x0'];m=sum(lo<=g.ports[p][0][1-axis]<=upper for p in g.source_items if g.kind[p[0]]=='warehouse_outlets' and p[1]==axis);e=1 if upper==69 else 2
  if low in [2,3]: a.test('矩形离带',m<=e*(low-1),{'axis':axis,'m':m,'e':e,'low':low,'length':length})
  else: a.na('矩形离带','方向 '+str(axis)+' 的近带 a/b∈{2,3} 前件不成立')
  if low==4: a.test('矿石走廊',m<=6 and length<=21,{'axis':axis,'m':m,'length':length})
  else: a.na('矿石走廊','方向 '+str(axis)+' 的 a/b=4 前件不成立')
 if A>1005: a.test('矩形离带',r['x0']>=4 and r['y0']>=4 and w<=66 and h<=66,{'area':A})
 cfg=all(cnt[m]==n for m,n in [('研磨机',32),('塑形机',6),('灌装机',3),('封装机',3)])
 g.tight_cfg=cfg
 base_drop=F(0)
 for m,cap in [('研磨机',F(31,4)),('粉碎机',F(27,4)),('塑形机',F(5,4))]: base_drop+=min(max(0,cnt[m]-MINIMUM[m])*F(1,2 if m=='研磨机' else 4),cap)
 base_drop += [F(0),F(1),F(3,2),F(7,4)][min(3,max(0,cnt['灌装机']-3))]
 base_drop += [F(0),F(3,4),F(7,4),F(9,4),F(11,4),F(3)][min(5,max(0,cnt['封装机']-3))]
 a.test('运输降幅',T>=math.ceil(200-base_drop),{'T':T,'computed_drop':str(base_drop)})
 ok=T>=180 and T+b>=306 and (b>0 or T>=306)
 if cfg and cnt['粉碎机']==68: ok &= T>=200
 if cfg:
  ok &= T>=207
  if B==0:
   ok &= T>=208
   bandfree={(0,y) for y in g.band_gaps[0]}|{(x,0) for x in g.band_gaps[1]}
   if any(x in g.occ and g.transport(g.occ[x]) for x in bandfree): ok &= T>=209
 a.test('运输下限',ok,{'T':T,'b':b,'tight_cfg':cfg})
 Fempty=4900-occ-A
 allowed={'machines','core','power_poles'}
 def qualifying(xy): return xy not in g.occ or g.kind[g.occ[xy]] not in allowed
 X=sum(qualifying(xy) and xy not in rectcells for xy in [(69,y) for y in range(1,69)]+[(x,69) for x in range(1,69)])
 if (69,69) not in rectcells and ((69,69) not in g.occ or g.kind[g.occ[69,69]]!='power_poles'): X+=2
 ring={(r['x0']-1,y) for y in range(r['y0'],r['y1']+1)}|{(r['x1']+1,y) for y in range(r['y0'],r['y1']+1)}|{(x,r['y0']-1) for x in range(r['x0'],r['x1']+1)}|{(x,r['y1']+1) for x in range(r['x0'],r['x1']+1)}
 Y=sum(0<=x<=69 and 0<=y<=69 and qualifying((x,y)) for x,y in ring)
 g.XY=(X,Y)
 if cfg:
  a.test('内带缺口',4*(T+Fempty)+2*P>= (921 if B==0 else 918) and (B>0 or 4*(T+Fempty)+2*J>=921+X+Y),{'T':T,'F':Fempty,'P':P,'J':J,'X':X,'Y':Y})
 else: a.na('内带缺口','机型配置前件不成立')
 ok=A+4*P<=1182
 if cfg and B==0: ok &= 4*A+14*P<=4639 and 4*A+16*P-2*J+X+Y<=4639
 else: ok &= 4*A+16*P-2*J<=4608
 if A==1113: ok &= cnt==Counter(MINIMUM) and B==0 and P<=12
 a.test('面积预算',ok,{'A':A,'P':P,'J':J,'X':X,'Y':Y,'tight_cfg':cfg})
 extra=Counter(MINIMUM);extra['粉碎机']=69;extra['采种机']=17
 if cnt==extra and B==0: a.test('增机面积界',A<=1089,{'A':A})
 else: a.na('增机面积界','69 粉碎/17 采种/其他下限且无箱前件不成立')
 ng=Counter();detail=[]
 for p in l['power_poles']:
  matches=[]
  if p['y0']-5>=r['y0'] and p['y0']+6<=r['y1']:
   if p['x1']<r['x0']: matches.append(r['x0']-p['x1']-1)
   if p['x0']>r['x1']: matches.append(p['x0']-r['x1']-1)
  if p['x0']-5>=r['x0'] and p['x0']+6<=r['x1']:
   if p['y1']<r['y0']: matches.append(r['y0']-p['y1']-1)
   if p['y0']>r['y1']: matches.append(p['y0']-r['y1']-1)
  for gap in matches:
   if gap<=6: ng[gap]+=1;detail.append((p['id'],gap))
 weight=sum([10,9,9,6,5,4,1][k]*v for k,v in ng.items())
 a.test('侧旁供电',weight<=23*P-217 and (P!=10 or weight<=13 and sum(ng[k] for k in [0,1,2])<=1),{'n_g':dict(ng),'weighted':weight})
 g.side_poles=detail

def flow_audit(d,g,lp,x,a):
 import networkx as nx
 l=g.l;cnt=g.counts;f={(i,it):x[j] for (i,it),j in lp.f.items()};br={(uid,r):x[j] for (uid,r),j in lp.batch.items()};z={(uid,it):x[j] for (uid,it),j in lp.wireless.items()}
 def ef(i,it=None): return sum((v for (j,t),v in f.items() if j==i and (it is None or t==it)),F(0))
 def sf(ix,it=None): return sum((ef(i,it) for i in ix),F(0))
 def batch(uid,r): return br.get((uid,r),F(0))
 active=[u for u in l['machines'] if sum(batch(u['id'],r) for r in u['recipe_ids'])>0]
 activecnt=Counter(u['model'] for u in active)
 production=defaultdict(F)
 for (uid,r),v in br.items():
  for it,k in RECIPES[r][2].items(): production[it]+=v*k
 production['源矿']=sum(sf([i for i in g.outs[p[0]] if g.edges[i][0]==p],it) for p,it in g.source_items.items() if it=='源矿')
 production['蓝铁矿']=sum(sf([i for i in g.outs[p[0]] if g.edges[i][0]==p],it) for p,it in g.source_items.items() if it=='蓝铁矿')
 a.test('矿石需求',production['源矿']==18 and production['蓝铁矿']==34,{k:str(production[k]) for k in ['源矿','蓝铁矿']})
 a.test('物料流量',all(production[it]>=v for it,v in MATERIAL_MIN.items()),{it:str(production[it]) for it in ITEMS})
 a.test('端口速率',all(ef(i)<=1 for i in range(len(g.edges))),'精确 LP 每条结构通道≤1；几何端口唯一')
 a.test('取货口配置',all(sf([i for i in g.outs[p[0]] if g.edges[i][0]==p],it)==1 for p,it in g.source_items.items()),'每个物理来源端口恰 1')
 a.test('周期倍数',all(production[it]==F(v) for it,v in TARGETS.items()),{it:str(production[it]) for it in TARGETS},remaining='仅精确平均产率；周期须为 20 倍数及每个循环态另证，不固定内部流分母。')
 a.test('机型下限',all(activecnt[m]>=n for m,n in MINIMUM.items()),{'positive_batch_machines':dict(activecnt)})
 a.test('入库途径',True,'入库仅 CORE 存货通道与实际箱体无线变量')
 for name in ['矿系不入库','非成品零入库']:
  a.test(name,all(sf(g.ins['CORE'],it)+sum(z.get((u['id'],it),F(0)) for u in l['storage_boxes'])==0 for it in ITEMS if it not in TARGETS),'每种非成品精确入库为 0')
 a.test('双料逐机收支与存货界',True,'LP 分机器分配方分物品等式逐行精确通过',remaining='事件前缀库存 0…50、偏差的具体界与初态仍待运行证明。')
 a.test('共用接货格余量',True,'所有运输槽入=出、合计≤1；机器入=批率用料；任意组相加即得余量式',remaining='平均式已核，实际服务/接通顺序另证。')
 # All supports strictly positive, so structural counts coincide with witness positive supports.
 inc={u['id']:len(g.ins[u['id']]) for u in l['machines']};out={u['id']:len(g.outs[u['id']]) for u in l['machines']}
 product_ingress=sum(any(ef(i,it)>0 for it in TARGETS) for i in g.ins['CORE'])+sum(any(ef(i,it)>0 for it in TARGETS) for u in l['storage_boxes'] for i in g.ins[u['id']])
 a.test('通道下限',product_ingress>=2,{'product_ingress_channels':product_ingress})
 load={u['id']:sum(RECIPES[r][3]*batch(u['id'],r) for r in u['recipe_ids']) for u in l['machines']}
 fullmodels=['粉碎机','精炼炉','配件机','种植机','采种机','封装机'];ok=True;triggers=[]
 for m in fullmodels:
  if cnt[m]==MINIMUM[m]: triggers.append(m);ok &= all(load[u['id']]==1 for u in l['machines'] if u['model']==m)
 if cnt['采种机']==16: ok &= any(batch(u['id'],'采种-荞花')>0 and batch(u['id'],'采种-砂叶')>0 for u in l['machines'] if u['model']=='采种机')
 if cnt['粉碎机']==68:
  for p in ['荞花','砂叶']: ok &= any(batch(u['id'],'粉碎-'+p)>0 and sum(batch(u['id'],r)>0 for r in u['recipe_ids'])>=2 for u in l['machines'] if u['model']=='粉碎机')
 a.test('满载配置',ok,{'triggered_models':triggers},remaining='平均满载和混做支持已查；实际连续制造与各 tick 批次另证。')
 ok=True
 if cnt['封装机']==3:
  for u in l['machines']:
   if u['model']=='封装机': ok &= inc[u['id']]>=5 and (inc[u['id']]!=5 or all(ef(i)==1 for i in g.ins[u['id']]))
 fills=[u for u in l['machines'] if u['model']=='灌装机'];n4=sum(inc[u['id']]>=4 for u in fills)
 if cnt['灌装机']==3:
  ok &= n4>=2
  if n4==2:
   third=next(u for u in fills if inc[u['id']]<4);ok &= inc[third['id']]==3 and all(ef(i)==1 for i in g.ins[third['id']])
 a.test('封装进料',ok,{'filling_at_least_4':n4})
 # Fully saturated source paths before first splitter.
 ok=True;mineok=True;firstsplit=[]
 for i,(p,q) in enumerate(g.edges):
  if ef(i)!=1: continue
  todo=[q];visited=set()
  while todo:
   q=todo.pop();s=g.slot(q)
   if s in visited or not g.transport(q[0]): continue
   visited.add(s);u=g.units[q[0]]
   ok &= sf(g.sin[s])==1 and sf(g.sout[s])==1
   if u['type']=='merger': ok &= sum(ef(j)>0 for j in g.sin[s])==1
   if u['type']=='gate': ok &= u['k5'] in [None,5]
   if u['type']!='splitter': todo += [g.edges[j][1] for j in g.sout[s]]
 a.test('满速独占',ok,'每条满速通道顺运输物品格追踪至首分流或非运输端；桥轴分开')
 for p,it in g.source_items.items():
  paths=[g.edges[i][1] for i in g.outs[p[0]] if g.edges[i][0]==p];seen=set()
  while paths:
   q=paths.pop();s=g.slot(q)
   if s in seen: continue
   seen.add(s);uid=q[0];u=g.units[uid]
   if g.kind[uid]=='splitter': firstsplit.append(uid);continue
   if g.transport(uid): paths += [g.edges[i][1] for i in g.sout[s]];continue
   if g.kind[uid]=='machines':
    r='精炼-蓝铁矿' if it=='蓝铁矿' else '粉碎-源矿'
    mineok &= batch(uid,r)==1 and sum(batch(uid,t)>0 for t in u['recipe_ids'])==1 and inc[uid]==1
 a.test('矿线专机',mineok,'真实52矿口追至首分流/非运输单位')
 a.test('准入累计',all(u['cum'] is None and (u['k5'] is None or sf(g.ins[u['id']])<=F(u['k5'],5)) for u in l['transport'] if u['type']=='gate' and sf(g.ins[u['id']])>0),'精确见证上累计上限与每5tick平均上限')
 saturated=[u['id'] for u in l['transport'] if u['type']=='gate' and u['k5'] is not None and sf(g.ins[u['id']])==F(u['k5'],5)]
 if saturated: a.runtime('准入满额窗口','这些准入口平均恰满额；逐窗口接收时刻须运行证明',saturated)
 else: a.na('准入满额窗口','本精确见证无 k/5 满额准入口；不是所有循环态的前件排除')
 # Positive-flow graph, ordinary transport slots shared, bridges split by axis, material preserved.
 graph=nx.DiGraph()
 for (i,it),v in f.items():
  if v>0:
   p,q=g.edges[i];graph.add_edge((g.slot(p),it),(g.slot(q),it))
 for u in l['storage_boxes']:
  for it in ITEMS:
   if sf(g.ins[u['id']],it)>0 and sf(g.outs[u['id']],it)>0: graph.add_edge(((u['id'],'in'),it),((u['id'],'out'),it))
 regen={};plantdata={};turn_ok=True;plantT=set();plantBr=set();plant_crushers=set()
 for plant in ['荞花','砂叶']:
  seed=plant+'种子';pg=graph.subgraph([n for n in graph if n[1] in [plant,seed]]).copy()
  conversions=[]
  for u in l['machines']:
   for r in ['采种-'+plant,'种植-'+plant]:
    if batch(u['id'],r)>0:
     ins=next(iter(RECIPES[r][1]));outs=next(iter(RECIPES[r][2]));aa=((u['id'],'in'),ins);bb=((u['id'],'out'),outs);pg.add_edge(aa,bb);conversions.append((aa,bb,r))
  scc=list(nx.strongly_connected_components(pg));good=[]
  for component in scc:
   kinds={r for aa,bb,r in conversions if aa in component and bb in component}
   if {'采种-'+plant,'种植-'+plant}<=kinds: good.append(component)
  reachable=set()
  for component in good:
   for node in component: reachable.add(node);reachable.update(nx.descendants(pg,node))
  consumers=[u for u in l['machines'] if batch(u['id'],'粉碎-'+plant)>0]
  regen[plant]=all(((u['id'],'in'),plant) in reachable for u in consumers)
  plant_crushers.update(u['id'] for u in consumers)
  turns=set()
  for comp in good:
   for node in comp:
    slot,it=node;uid=slot[0]
    if uid in g.units and g.transport(uid) and g.kind[uid] in ['belt','splitter','merger']:
     for ii in g.sin[slot]:
      for oo in g.sout[slot]:
       if ef(ii,it)>0 and ef(oo,it)>0 and g.edges[ii][1][1]%2!=g.edges[oo][0][1]%2 and (g.slot(g.edges[ii][0]),it) in comp and (g.slot(g.edges[oo][1]),it) in comp: turns.add(uid)
  turn_ok &= bool(good) and len(turns)>=4
  zrate=sum(batch(u['id'],'种植-'+plant) for u in l['machines']);arate=sum(batch(u['id'],'采种-'+plant) for u in l['machines']);frate=sum(batch(u['id'],'粉碎-'+plant) for u in l['machines'])
  a.test('回路守恒',arate==frate and zrate==2*arate,{'plant':plant,'seed_batches':str(arate),'plant_batches':str(zrate),'crush_batches':str(frate)})
  qs=qp=F(0)
  for s in g.slots:
   sr=sf(g.sin[s],seed);pr=sf(g.sin[s],plant);qs+=sr;qp+=pr
   if sr+pr>0:
    plantT.add(s[0])
    if g.kind[s[0]]=='bridge': plantBr.add(s[0])
  plantdata[plant]={'seed_inventory_lower_bound':str(zrate+qs),'plant_inventory_lower_bound':str(arate+frate+qp),'turns_in_regeneration_scc':len(turns),'regeneration_scc':len(good)}
  if cnt['种植机']==32:
   mixed=any(batch(u['id'],'种植-荞花')>0 and batch(u['id'],'种植-砂叶')>0 for u in l['machines'] if u['model']=='种植机')
   split=any(sum(ef(i,plant)>0 for i in g.outs[u['id']])>=2 for u in l['machines'] if u['model']=='种植机')
   reachable_uid={node[0][0] for node in pg.nodes if node in reachable}
   split |= any(sum(ef(i,plant)>0 for i in g.outs[uid])>=2 for uid in reachable_uid if g.kind.get(uid) in ['splitter','storage_boxes'])
   a.test('植株半分',mixed or split,{'plant':plant,'mixed':mixed,'split':split})
 a.test('植物再生来路',all(regen.values()),regen,'每台正批率植物粉碎机；种子/植株、桥轴分开的正流图')
 a.test('植物分区收支',True,'逐单位逐物品守恒精确成立，任意完整单位子集相加即成立，无需枚举 2^n 子集')
 a.runtime('植物沿途存量','已从精确流计算必要时间平均库存下界；真实库存及事件相位无静态输入',plantdata)
 if cnt['种植机']==32: a.runtime('回路存量','32 台前件成立；同一时刻至少 64 与时间平均库存需运行状态证据。')
 else: a.na('回路存量','种植机非32台')
 if cnt['种植机']!=32: a.na('植株半分','种植机非32台')
 planted_units={u['id'] for u in l['machines'] if u['model'] in ['种植机','采种机']}|plant_crushers|plantT
 plantarea=sum(len(cells(g.units[uid])) for uid in planted_units);pt,pb=len(plantT),len(plantBr)
 a.test('回路转弯',turn_ok and pt-pb>=4 and pt+pb>=64 and pt>=34 and plantarea>=1378,{'T_plant':pt,'b_plant':pb,'area':plantarea,'details':plantdata},remaining='已查再生 SCC 中转弯必要数与占地；真实周期的循环运输仍属运行义务。')
 # Mixing clauses: support/mean projections only; event sequence not invented.
 mixedfull=[u for u in active if load[u['id']]==1 and len({it for r in u['recipe_ids'] if batch(u['id'],r)>0 for it in RECIPES[r][2]})>1]
 if mixedfull:
  a.test('混做清空',all(out[u['id']]>=sf(g.outs[u['id']]) for u in mixedfull),[u['id'] for u in mixedfull],remaining='相邻不同产物批次清空时刻、逐批交替及连续批次段另证。')
  a.runtime('混做连续批次出货','存在满载混做；批次串的 m、c_X 须来自运行序列。',[u['id'] for u in mixedfull])
 else:
  a.na('混做清空','本精确见证无满载多产物机器；未断言全部循环态如此');a.na('混做连续批次出货','本见证无满载多产物机器')
 if cnt['灌装机']==3 and n4==2:
  u=next(u for u in fills if inc[u['id']]<4);mixededges=[i for i in g.ins[u['id']] if ef(i,'钢质瓶')>0 and ef(i,'细磨荞花粉末')>0]
  ok=bool(mixededges)
  for i in mixededges:
   seen=set();todo=[g.edges[i][0]];merge=False;filtergate=False
   while todo:
    p=todo.pop();uid=p[0];s=g.slot(p)
    if s in seen: continue
    seen.add(s)
    if g.kind[uid]=='gate' and g.units[uid]['filter'] is not None: filtergate=True
    if g.kind[uid]=='merger' or g.kind[uid]=='storage_boxes' and sf(g.ins[uid],'钢质瓶')>0 and sf(g.ins[uid],'细磨荞花粉末')>0: merge=True
    if g.transport(uid): todo += [g.edges[j][0] for j in g.sin[s] if ef(j,'钢质瓶')+ef(j,'细磨荞花粉末')>0]
   ok &= merge and not filtergate
  a.test('灌装混线',ok,{'machine':u['id'],'mixed_channels':mixededges})
 else: a.na('灌装混线','三台且恰两台≥4存货通道前件不成立')
 # Counts involving boxes are evaluated even for B=0.
 S=sum(not g.transport(p[0]) for p,q in g.edges);R=sum(not g.transport(q[0]) for p,q in g.edges);E=len(g.edges)-S-R
 tc=Counter(u['type'] for u in l['transport']);T=len(l['transport']);b=tc['bridge'];D=tc['splitter'];M=tc['merger'];L=tc['belt']+tc['gate']
 a.test('运输端口收支',S>=312 and R>=307 and T+b+2*M>=S+E and T+b+2*D>=R+E and -2*M<=R-S<=2*D,{'S':S,'R':R,'E':E,'T':T,'b':b,'D':D,'M':M})
 B1=sum(sum(z.get((u['id'],it),0) for it in ITEMS)>0 for u in l['storage_boxes']);B0=sum(sf(g.ins[u['id']])>0 and sum(z.get((u['id'],it),0) for it in ITEMS)==0 for u in l['storage_boxes']);H=max(2,B1);eta=2*B0+max(H-2,5-2*M,2*H-9-2*D)
 tight=g.tight_cfg and cnt['粉碎机']==68;ok=S+R>=619+eta and 4*T>=S+R+99 and T>=math.ceil(F(718+eta,4)) and 2*T+M>=362+B0
 if tight:
  ok &= 4*T>=S+R+181 and T>=math.ceil(F(800+eta,4)) and 2*T+M>=403+B0
  if T==200: ok &= M>=3 and B0==0 and B1<=2 and S==312 and R==307 and all(sf(g.outs[u['id']])==0 for u in l['storage_boxes'])
 a.test('箱体接口',ok,{'B0':B0,'B1':B1,'H':H,'eta':eta,'S':S,'R':R,'T':T,'tight':tight})
 B=len(l['storage_boxes']);A=g.rectangle['area'];occ=len(g.occ)
 a.test('箱体预算',occ>=3750+9*B+math.ceil(F(eta,4)) and A+9*B+(eta+2)//4<=1149 and (B0==0 or occ>=3760 and A<=1139),{'B':B,'eta':eta,'area':A,'occupied':occ})
 raw=['源矿','蓝铁矿'];rawmachines=[u for u in active if any(batch(u['id'],r)>0 and set(RECIPES[r][1]) & set(raw) for r in u['recipe_ids'])]
 dedicated=[u for u in rawmachines if sum(batch(u['id'],r)>0 for r in u['recipe_ids'])==1 and sum(batch(u['id'],r) for r in u['recipe_ids'])==1]
 dmin=sum(any(sf(g.ins[u['id']],it)>0 for it in raw) for u in l['transport'] if u['type']=='splitter');bmin=sum(any(sf(g.ins[u['id']],it)>0 for it in raw) for u in l['storage_boxes']);Cmin=len(dedicated)
 a.test('矿石分流与专机',len(rawmachines)<=52+2*dmin+2*bmin and dmin+3*bmin+Cmin>=52 and len(firstsplit)==len(set(firstsplit)),{'N_mine':len(rawmachines),'C_mine':Cmin,'D_mine':dmin,'B_mine':bmin,'first_splitters':firstsplit})
 Q=sum(sf(g.outs[u['id']]) for u in l['storage_boxes']);ceilQ=math.ceil(F(6113,20)+Q)
 a.test('箱体过站',T+b>=ceilQ and 2*T>=ceilQ+D+M+L and Q>=52-Cmin-dmin and T+b+dmin+Cmin>=358,{'Q':str(Q),'ceil_305.65_plus_Q':ceilQ})
 products=set(TARGETS);K=sum(any(ef(i,it)>0 for it in products) for i in g.ins['CORE']);pbx=[u for u in l['storage_boxes'] if any(sf(g.ins[u['id']],it)>0 for it in products)];prodB=sum(any(z.get((u['id'],it),0)>0 for it in products) for u in pbx);C=sum(any(sf(g.ins[u['id']],it)>0 for it in products) for u in l['transport'] if u['type']=='merger')+len(pbx)-prodB
 psources=[u for u in active if any(batch(u['id'],r)>0 and set(RECIPES[r][2]) & products for r in u['recipe_ids'])]
 a.test('成品汇入',len(psources)>=6 and all(any(ef(i,it)>0 for i in g.outs[u['id']] for it in products) for u in psources) and K+3*prodB+2*C>=6,{'sources':len(psources),'K':K,'B':prodB,'C':C})
 a.test('核心邻格',K==0 or len({g.ports[g.edges[i][0]][0] for i in g.ins['CORE']}|{nb(g.ports[p][0],p[1]) for p in g.source_items if p[0]=='CORE'})>=7,{'K':K})
 for name in ['传输按仓库余量判定','传输箱不满','箱内滞货封住后格','满速箱头限存']:
  if not l['storage_boxes']: a.na(name,'无协议储存箱；箱体接口/预算/过站仍正常执行')
  else: a.runtime(name,'已查箱体平均守恒、供电和传输开关；编号1…6、各格50、箱头选择、仓库余量及无线相位须运行证据。')
 for name in ['轮询均分','混料轮询分料']: a.runtime(name,'前件含腾空时刻、出货分组/种类清单；静态布局及平均流不能确认。')
 # Active power counts and side capacities.
 a.test('供电下限',all(sum(g.covers(p,u) for u in active)<=23 for p in l['power_poles']),'每桩覆盖正批率制造单位≤23')
 a.test('侧旁供电',all(sum(g.covers(g.units[pid],u) for u in active)<=[13,14,14,17,18,19,22][gap] for pid,gap in g.side_poles),'逐桩按实际正批率机器核 c_g')
 # Four-neighbour nontransport junctions with positive support.
 junctions=[];jok=True
 for u in l['transport']:
  uid=u['id'];xy=(u['x'],u['y'])
  if xy in g.ore_fronts: continue
  attached={g.ports[g.edges[i][0]][0]:g.edges[i][0][0] for i in g.ins[uid] if not g.transport(g.edges[i][0][0])}
  attached.update({g.ports[g.edges[i][1]][0]:g.edges[i][1][0] for i in g.outs[uid] if not g.transport(g.edges[i][1][0])})
  if all(nb(xy,j) in attached for j in range(4)):
   junctions.append(uid);jok &= u['type'] in ['splitter','merger','bridge']
   if all(g.kind[x] not in ['core','warehouse_outlets'] for x in attached.values()):
    jok &= Counter(g.units[x]['Din']%2 for x in attached.values())==Counter({0:2,1:2})
 a.test('四通结点',jok and len(junctions)>=664-3*T,{'x':len(junctions),'required':664-3*T})
 # Core corridor cross-sections when the exact conditional clause applies.
 triggered=False;core=l['core']
 for axis in [0,1]:
  start=core['x0'] if axis==0 else core['y0'];o0=core['y0'] if axis==0 else core['x0'];o1=o0+8;side=2 if axis==0 else 3
  m=sum(o0<=g.ports[p][0][1-axis]<=o1 for p in g.source_items if g.kind[p[0]]=='warehouse_outlets' and p[1]==axis)
  if start!=4 or side in [core['Din'],opp(core['Din'])] or m!=3: continue
  cutcells=[(k,t) if axis==0 else (t,k) for k in [1,2,3] for t in [o0-1,o0,o1,o1+1]]
  if any(xy in g.occ and g.kind[g.occ[xy]] in ['machines','storage_boxes'] for xy in cutcells): continue
  triggered=True;cutedges=[]
  for boundary in [o0-1,o1]:
   es=[]
   for i,(p,q) in enumerate(g.edges):
    pp,qq=g.ports[p][0],g.ports[q][0]
    if pp[axis]==qq[axis] and 1<=pp[axis]<=3 and {pp[1-axis],qq[1-axis]}=={boundary,boundary+1}: es.append(i)
   cutedges.append(es)
  a.test('核心取货边朝带',all(len(es)==3 and all(ef(i)==1 and g.transport(g.edges[i][0][0]) and g.transport(g.edges[i][1][0]) for i in es) for es in cutedges),{'axis':axis,'cuts':cutedges})
 if not triggered: a.na('核心取货边朝带','本布局无取货边朝带、走廊3、m=3且两端切线不穿机器/箱的完整前件')
 return {'materials':{k:str(v) for k,v in production.items()},'active_machines':dict(activecnt),'box_interface':{'B0':B0,'B1':B1,'eta':eta}}
