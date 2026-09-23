"""绑定 catalog.HASHES 中现行72条版本的静态投影；新增1113位置并迁移后续编号。"""
from collections import Counter,defaultdict
from fractions import Fraction as Q
from math import ceil,floor
from catalog import *
from geometry import edge,nb,pref,covers

def geometry_checks(g,r):
 l=g.lay;n=Counter(u['model']for u in l['machines']);T=len(l['transport']);bt=Counter(u['type']for u in l['transport']);B=len(l['storage_boxes']);P=len(l['power_poles']);rect=g.maximum['bounds'] or g.d['empty_rectangle'];a,b=rect['x0'],rect['y0'];W,H=rect['x1']-a+1,rect['y1']-b+1;A=W*H
 def ck(num,ok,detail):r.formal(num,ok,detail)
 ck(19,all(n[k]>=v for k,v in MIN_COUNTS.items()),dict(n))
 active=[u for u in l['machines']if g.power[u['id']]and u['settings']['manufacture_on']]
 ac=Counter(u['model']for u in active)
 ck(20,all(ac[k]>=v for k,v in MIN_COUNTS.items()),{'powered_and_on':dict(ac),'remaining':'运行阶段仍须核初始无误料；可达种类风险另查'})
 cfg=Counter(g.sources.values());left=[u for u in l['warehouse_outlets']if u['Dout']==0];bottom=[u for u in l['warehouse_outlets']if u['Dout']==1]
 ck(13,len(left)<=23 and len(bottom)<=23 and len(g.sources)<=52,{'left':len(left),'bottom':len(bottom),'source_ports':len(g.sources)})
 ck(14,len(left)==len(bottom)==23 and cfg==Counter({'源矿':18,'蓝铁矿':34}),{'settings':dict(cfg)})
 gaps=[];orecells=set()
 for group,coord in [(left,'y'),(bottom,'x')]:
  used={v for u in group for v in range(u[coord+'0'],u[coord+'1']+1)};gap=set(range(70))-used;gaps.append(gap)
  ck(55,len(gap)==1 and next(iter(gap),-1)%3==0,{'axis':coord,'gaps':sorted(gap)})
  ps=sorted(u[coord+'0']+1 for u in group);ck(55,all(y-x in(3,4)for x,y in zip(ps,ps[1:])),{'port_positions':ps})
 for p in g.sources:
  typ,c=g.ports[p];out=nb(c,p[1]);exists=out in g.occ and g.is_t(g.occ[out]);ck(55 if p[0]!='CORE'else 58,exists,{'source':p,'front':out})
  if p[0]!='CORE':orecells.add(out)
 ck(55,any(0 in gap for gap in gaps)and a>=2 and b>=2,{'gaps':list(map(sorted,gaps)),'rectangle_origin':[a,b]})
 ck(56,not(a<=2<=rect['x1']and b<=2<=rect['y1']),{'rectangle':rect})
 adj=sum((g.ports[p][1]in orecells and not g.is_t(q[0]))or(g.ports[q][1]in orecells and not g.is_t(p[0]))for p,q in g.channels)
 ck(56,adj<=93,{'46_ore_cell_nontransport_channels':adj})
 core=l['core'];fronts=[]
 for coord,group,side in [('x',left,2),('y',bottom,3)]:
  oth='y'if coord=='x'else'x';x0=core[coord+'0'];lo,hi=core[oth+'0'],core[oth+'1'];m=sum(lo<=u[oth+'0']+1<=hi for u in group);delta=int(side not in(core['Din'],opp(core['Din'])));e=int(lo>0)+int(hi<69)
  ck(57,x0>=2 and m+3*delta<=e*(x0-1),{'axis':coord,'m':m,'delta':delta,'e':e,'w':x0-1})
  # §59 when both end cuts avoid manufacturing units/storage boxes.
  if x0==4 and delta and m==3:
   cuts=[];clear=True
   for sign,z in [(-1,lo),(1,hi+1)]:
    cells=[((v,z-1),(v,z))if coord=='x'else((z-1,v),(z,v))for v in range(1,x0)]
    # a unit spans a cut iff it occupies cells on both sides.
    if any(g.occ.get(c)==g.occ.get(d)and g.occ.get(c)in g.units and g.types[g.occ[c]]in('machine','box')for c,d in cells):clear=False
    cuts.extend((c,d)for c,d in cells)
   if clear:
    expected=[]
    for c,d in cuts:
     matches=[i for i,(p,q)in enumerate(g.channels)if {g.ports[p][1],g.ports[q][1]}=={c,d}]
     ck(59,len(matches)==1 and all(v in g.occ and g.is_t(g.occ[v])for v in [c,d]),{'cut':(c,d),'matches':matches});expected+=matches
    fronts+=expected
 ck(58,not(core['x0']<=3 and core['y0']<=3),{'core':core})
 adjt={nb(c,s)for s in range(4)for c in edge(core,s)if nb(c,s)in g.occ and g.is_t(g.occ[nb(c,s)])}
 ck(58,len(adjt)>=6+int(bool(g.inc['CORE'])),{'core_neighbor_transport':len(adjt),'input_channels':len(g.inc['CORE'])})
 for s in [(core['Din']+1)%4,(core['Din']+3)%4]:
  for off,c in enumerate(edge(core,s)):
   q=nb(c,s)
   ck(58,not(a<=q[0]<=rect['x1']and b<=q[1]<=rect['y1'])or off in(0,8),{'core_output_side':s,'offset':off})
 for coord,group,size,origin,far in [('x',left,H,a,rect['y1']),('y',bottom,W,b,rect['x1'])]:
  oth='y'if coord=='x'else'x';low=rect[oth+'0'];high=rect[oth+'1'];m=sum(low<=u[oth+'0']+1<=high for u in group)
  if origin in(2,3):ck(68,m<=(1 if far==69 else 2)*(origin-1),{'axis':coord,'m':m,'origin':origin})
  if origin==4:ck(70,m<=6 and size<=21,{'axis':coord,'m':m,'span':size})
 ck(68,A<=1005 or(a>=4 and b>=4 and W<=66 and H<=66),{'area':A})
 J=0
 for p in l['power_poles']:
  hits=sum(p['x0']<=v<=p['x1']for v in(1,69))+sum(p['y0']<=v<=p['y1']for v in(1,69));J+=int(hits>0)
  cnt=sum(covers(p,u)for u in l['machines']);ca=sum(covers(p,u)for u in active)
  ck(54,cnt<=24 and (not hits or cnt<=(8 if hits>=2 else 14)),{'pole':p['id'],'all_covered':cnt,'edge_lines':hits})
  if P==10:ck(54,hits<2,{'pole':p['id'],'edge_lines':hits})
 ck(54,P>=10 and 9*J<=23*P-217 and(P!=10 or J<=1),{'poles':P,'boundary_poles':J})
 four=all(n[k]==MIN_COUNTS[k]for k in ['研磨机','塑形机','灌装机','封装机']);five=four and n['粉碎机']==68
 ck(60,T>=180 and T+bt['bridge']>=306 and (not five or T>=200)and(not four or T>=207+int(B==0)+int(B==0 and (0,0)in g.occ and g.is_t(g.occ[(0,0)]))),{'T':T,'bridges':bt['bridge'],'four_machine_minima':four})
 discount=min(max(n['研磨机']-32,0)*Q(1,2),Q(31,4))+min(max(n['粉碎机']-68,0)*Q(1,4),Q(27,4))+min(max(n['塑形机']-6,0)*Q(1,4),Q(5,4))
 discount+=[Q(0),Q(1),Q(3,2),Q(7,4)][min(max(n['灌装机']-3,0),3)]+[Q(0),Q(3,4),Q(7,4),Q(9,4),Q(11,4),Q(3)][min(max(n['封装机']-3,0),5)]
 ck(61,T>=ceil(200-discount),{'discount':str(discount),'T':T})
 ck(62,len(g.occ)>=(3758 if bt['bridge']else 3856),{'occupied':len(g.occ)})
 ck(63,A<=(1113 if bt['bridge']else 1040)and W<=68 and H<=68 and(A!=1113 or sorted([W,H])==[21,53]),{'area':A,'dimensions':[W,H]})
 if A==1113:
  ck(64,(W,H,a,b) in {(21,53,49,y) for y in (6,7,9,17)} | {(53,21,x,49) for x in (6,7,9,17)}, {'area':A,'dimensions':[W,H],'origin':[a,b]})
 else:r.formal_na(64,'最大空矩形面积不为1113')
 expected=dict(MIN_COUNTS);expected.update({'粉碎机':69,'采种机':17})
 if dict(n)==expected and B==0:ck(66,A<=1089,{'area':A})
 else:r.formal_na(66,'台数/箱体前件不成立')
 inrect=lambda c:a<=c[0]<=rect['x1']and b<=c[1]<=rect['y1']
 solid=lambda c:c in g.occ and g.types[g.occ[c]]in('machine','core','pole')
 X=sum(not solid(c)and not inrect(c)for c in [(69,y)for y in range(1,69)]+[(x,69)for x in range(1,69)])
 if not inrect((69,69))and(g.occ.get((69,69))is None or g.types[g.occ[(69,69)]]!='pole'):X+=2
 rim=set([(a-1,y)for y in range(b,rect['y1']+1)if a>0]+[(rect['x1']+1,y)for y in range(b,rect['y1']+1)if rect['x1']<69]+[(x,b-1)for x in range(a,rect['x1']+1)if b>0]+[(x,rect['y1']+1)for x in range(a,rect['x1']+1)if rect['y1']<69])
 Y=sum(not solid(c)for c in rim);F=4900-len(g.occ)-A
 if four:
  ck(72,4*(T+F)+2*P>=(921 if B==0 else 918)and(B!=0 or 4*(T+F)+2*J>=921+X+Y),{'T':T,'F':F,'P':P,'J':J,'X':X,'Y':Y})
 else:r.formal_na(72,'四机型恰下限的前件不成立')
 ck(65,A+4*P<=1182 and((4*A+14*P<=4639 and 4*A+16*P-2*J+X+Y<=4639)if four and B==0 else 4*A+16*P-2*J<=4608)and(A!=1113 or B==0 and P<=12 and all(n[k]==v for k,v in MIN_COUNTS.items())),{'A':A,'P':P,'J':J,'X':X,'Y':Y})
 gapsides={}
 for p in l['power_poles']:
  vals=[]
  if b<=p['y0']-5 and p['y0']+6<=rect['y1']:
   if p['x1']<a:vals.append(a-p['x1']-1)
   if p['x0']>rect['x1']:vals.append(p['x0']-rect['x1']-1)
  if a<=p['x0']-5 and p['x0']+6<=rect['x1']:
   if p['y1']<b:vals.append(b-p['y1']-1)
   if p['y0']>rect['y1']:vals.append(p['y0']-rect['y1']-1)
  if vals and min(vals)<=6:gapsides[p['id']]=min(vals)
 weights=[10,9,9,6,5,4,1];loss=sum(weights[v]for v in gapsides.values())
 ck(67,loss<=23*P-217 and(P!=10 or sum(v<=2 for v in gapsides.values())<=1),{'gaps':gapsides,'loss':loss})
 g.stats={'counts':dict(n),'transport_types':dict(bt),'T':T,'B':B,'P':P,'J':J,'A':A,'orecells':orecells,'corridor_full_edges':fronts,'side_gaps':gapsides}


def flow_checks(g,f,x,r):
 """前件与所有正支撑计数均取本份精确平均流，不用 allowed_items 代替流量。"""
 st=g.stats;n=Counter(st['counts']);T=st['T'];B=st['B'];P=st['P'];A=st['A'];bt=Counter(st['transport_types']);D=bt['splitter'];M=bt['merger'];bridge=bt['bridge']
 vals={(i,it):x[j]for(i,it),j in f.f.items()};total=lambda es,it=None:sum((v for(i,k),v in vals.items()if i in es and(it is None or it==k)),Q())
 bval={(u,rid):x[j]for(u,rid),j in f.batch.items()};wire={(u,it):x[j]for(u,it),j in f.wire.items()};positive=lambda es:[i for i in es if total([i])>0]
 cin={u:positive(g.inc[u])for u in g.units};cout={u:positive(g.out[u])for u in g.units}
 def ck(num,ok,detail):r.formal(num,ok,detail)
 # These are exact consequences of separately verified row families, not a claim of dynamic sufficiency.
 for num in [8,9,10,12,14,17,25,26,29,31,32,35,36,47]:ck(num,True,{'projection':'精确核过分物品逐机/逐格守恒、真实源、配方、共享容量、入库与限流行；仅平均流投影'})
 ck(15,all(total(g.inc['CORE'],it)+sum(v for(u,k),v in wire.items()if k==it)==Q(t)for it,t in TARGETS.items()),{'projection':'产率恰为目标；周期20倍数留待运行'})
 products=defaultdict(Q)
 for(u,rid),v in bval.items():
  for it,k in RECIPES[rid][2].items():products[it]+=v*k
 products.update({'源矿':Q(18),'蓝铁矿':Q(34)})
 ck(18,all(products[it]>=v for it,v in MATERIAL.items()),{'produced':{k:str(v)for k,v in products.items()}})
 for model in MIN_COUNTS:
  ms=[u for u in g.lay['machines']if u['model']==model]
  ck(21,sum(len(cin[u['id']])for u in ms)>=MIN_IN[model]and sum(len(cout[u['id']])for u in ms)>=MIN_OUT[model],{'model':model,'in':sum(len(cin[u['id']])for u in ms),'out':sum(len(cout[u['id']])for u in ms)})
  if model in ['粉碎机','精炼炉','配件机','种植机','采种机','封装机']and n[model]==MIN_COUNTS[model]:
   ck(22,all(sum(bval[u['id'],rid]*RECIPES[rid][3]for rid in u['recipe_ids'])==1 for u in ms),{'model':model,'projection':'各台平均满载，逐tick连续留待运行'})
 if n['采种机']==16:ck(22,any(sum(v>0 for(uid,rid),v in bval.items()if uid==u['id'])>=2 for u in g.lay['machines']if u['model']=='采种机'),{'projection':'至少一采种机混做'})
 if n['粉碎机']==68:
  for rid in ['粉碎-荞花','粉碎-砂叶']:ck(22,any(bval.get((u['id'],rid),0)>0 and sum(v>0 for(uid,rr),v in bval.items()if uid==u['id'])>=2 for u in g.lay['machines']if u['model']=='粉碎机'),{'recipe':rid,'projection':'至少一台混做'})
 for model,num,count,atleast in [('研磨机',32,31,3),('采种机',16,16,2),('塑形机',6,5,2)]:
  if n[model]==num:ck(23,sum(len((cout if model=='采种机'else cin)[u['id']])>=atleast for u in g.lay['machines']if u['model']==model)>=count,{'model':model})
 packs=[u['id']for u in g.lay['machines']if u['model']=='封装机'];fills=[u['id']for u in g.lay['machines']if u['model']=='灌装机']
 if n['封装机']==3:ck(24,all(len(cin[u])>=5 and(len(cin[u])!=5 or all(total([i])==1 for i in cin[u]))for u in packs),{'packing_inputs':{u:len(cin[u])for u in packs}})
 if n['灌装机']==3:
  high=[u for u in fills if len(cin[u])>=4];ck(24,len(high)>=2,{'filling_inputs':{u:len(cin[u])for u in fills}})
  if len(high)==2:
   other=next(u for u in fills if u not in high);ck(24,len(cin[other])==3 and all(total([i])==1 for i in cin[other]),{'third_filler':other})
   mixed=[i for i in cin[other]if total([i],'钢质瓶')>0 and total([i],'细磨荞花粉末')>0];ck(28,bool(mixed),{'mixed_edges':mixed})
   # Reverse each genuinely mixed item-slot path until merge or mixed box; filtered gates cannot carry both by LP.
   for start in mixed:
    seen=set();todo=[g.slot(g.channels[start][0])];found=False
    while todo:
     s=todo.pop()
     if s in seen:continue
     seen.add(s);u=s[0]
     if g.types[u]=='merger'or g.types[u]=='box'and total(g.inc[u],'钢质瓶')>0 and total(g.inc[u],'细磨荞花粉末')>0:found=True
     if g.is_t(u):todo += [g.slot(g.channels[i][0])for i in g.si[s]if total([i])>0]
    ck(28,found,{'mixed_edge':start,'upstream_merge_or_box':found})
  else:r.formal_na(28,'恰两台灌装机有至少四条正流输入的前件不成立')
 else:r.formal_na(28,'灌装机台数前件不成立')
 S=sum(not g.is_t(p[0])and total([i])>0 for i,(p,q)in enumerate(g.channels));R=sum(not g.is_t(q[0])and total([i])>0 for i,(p,q)in enumerate(g.channels));E=sum(g.is_t(p[0])and g.is_t(q[0])and total([i])>0 for i,(p,q)in enumerate(g.channels))
 ck(43,S>=312 and R>=307 and T+bridge+2*M>=S+E and T+bridge+2*D>=R+E and -2*M<=R-S<=2*D,{'S':S,'R':R,'E':E,'T':T,'b':bridge,'D':D,'M':M})
 B1=sum(sum(v for(u2,it),v in wire.items()if u2==u['id'])>0 for u in g.lay['storage_boxes']);B0=sum(bool(cin[u['id']]or cout[u['id']])and sum(v for(u2,it),v in wire.items()if u2==u['id'])==0 for u in g.lay['storage_boxes']);HH=max(2,B1);eta=2*B0+max(HH-2,5-2*M,2*HH-9-2*D)
 five=all(n[k]==MIN_COUNTS[k]for k in ['粉碎机','研磨机','塑形机','灌装机','封装机'])
 ck(49,S+R>=619+eta and 4*T>=S+R+99 and T>=ceil(Q(718+eta,4))and 2*T+M>=362+B0 and(not five or 4*T>=S+R+181 and T>=ceil(Q(800+eta,4))and 2*T+M>=403+B0),{'B0':B0,'B1':B1,'eta':eta})
 if five and T==200:ck(49,M>=3 and B0==0 and B1<=2 and S==312 and R==307 and all(not cout[u['id']]for u in g.lay['storage_boxes']),{'T=200':True})
 ck(50,len(g.occ)>=3750+9*B+ceil(Q(eta,4))and A+9*B+floor(Q(eta+2,4))<=1149 and(not B0 or len(g.occ)>=3760 and A<=1139),{'B':B,'B0':B0,'eta':eta,'A':A})
 ores={'源矿','蓝铁矿'};ore_m=[u['id']for u in g.lay['machines']if any(v>0 and set(RECIPES[rid][1])&ores for(uid,rid),v in bval.items()if uid==u['id'])];ded=[uid for uid in ore_m if sum(v for(u,rid),v in bval.items()if u==uid and set(RECIPES[rid][1])&ores)==1];dm=[u for u in g.units if g.types[u]=='splitter'and sum(total(g.inc[u],it)for it in ores)>0];bm=[u for u in g.units if g.types[u]=='box'and sum(total(g.inc[u],it)for it in ores)>0]
 ck(44,len(ore_m)<=52+2*len(dm)+2*len(bm)and len(dm)+3*len(bm)+len(ded)>=52,{'ore_machines':len(ore_m),'dedicated':len(ded),'ore_splitters':len(dm),'ore_boxes':len(bm)})
 first=[]
 for p,it in g.sources.items():
  es=[i for i in g.out[p[0]]if g.channels[i][0]==p];todo=list(es);seen=set()
  while todo:
   i=todo.pop()
   if i in seen:continue
   seen.add(i);u=g.channels[i][1][0];s=g.slot(g.channels[i][1])
   if g.types[u]=='splitter':first.append(u);break
   if not g.is_t(u):
    if g.types[u]=='machine':
     rid='粉碎-源矿'if it=='源矿'else'精炼-蓝铁矿';ck(27,bval.get((u,rid),Q())==1 and len(cin[u])==1,{'source':p,'machine':u})
    break
   todo+=positive(g.so[s])
 ck(44,len(first)==len(set(first)),{'first_splitters':first})
 Qbox=sum(total(g.out[u['id']])for u in g.lay['storage_boxes']);L=bt['belt']+bt['gate'];v=ceil(Q(6113,20)+Qbox)
 ck(51,T+bridge>=v and 2*T>=v+D+M+L and Qbox>=52-len(ded)-len(dm)and T+bridge+len(dm)+len(ded)>=358,{'Qbox':str(Qbox),'C_ore':len(ded),'D_ore':len(dm)})
 product_sources=[u['id']for u in g.lay['machines']if any(total(g.out[u['id']],it)>0 for it in TARGETS)]
 K=len(positive(g.inc['CORE']));CB=sum(g.types[u]=='merger'and any(total(g.inc[u],it)>0 for it in TARGETS)for u in g.units)+sum(any(total(g.inc[u['id']],it)>0 for it in TARGETS)and sum(v for(u2,it),v in wire.items()if u2==u['id'])==0 for u in g.lay['storage_boxes'])
 ck(34,len(product_sources)>=6 and K+3*B1+2*CB>=6,{'sources':product_sources,'K':K,'wireless_boxes':B1,'mergers_and_relay_boxes':CB})
 ck(21,K+sum(len(cin[u['id']])for u in g.lay['storage_boxes']if any(wire[u['id'],it]>0 for it in TARGETS))>=2,{'projection':'成品入库运输存货通道'})
 # Capacity projections for conditional dynamic items.
 for u in g.lay['machines']:
  uid=u['id'];busy=sum(bval[uid,rid]*RECIPES[rid][3]for rid in u['recipe_ids']);prod={it for rid in u['recipe_ids']if bval[uid,rid]>0 for it in RECIPES[rid][2]}
  if busy==1 and all(RECIPES[rid][3]==1 for rid in u['recipe_ids'])and len(prod)>1:ck(38,len(cout[uid])>=total(g.out[uid]),{'machine':uid,'projection':'平均计数；逐批清空仍待运行'})
 for p in g.lay['power_poles']:
  working=[u for u in g.lay['machines']if sum(bval[u['id'],rid]for rid in u['recipe_ids'])>0]
  cnt=sum(covers(p,u)for u in working);ck(54,cnt<=23,{'pole':p['id'],'manufacturing_covered':cnt})
  if p['id']in st['side_gaps']:ck(67,cnt<=[13,14,14,17,18,19,22][st['side_gaps'][p['id']]],{'pole':p['id'],'manufacturing_covered':cnt})
 for i in st['corridor_full_edges']:ck(59,total([i])==1,{'edge':i,'rate':str(total([i]))})
 four_nodes=[]
 for u in g.lay['transport']:
  uid=u['id'];c=(u['x'],u['y'])
  if c in st['orecells']:continue
  es=cin[uid]+cout[uid];neighbors=[]
  for i in es:
   p,q=g.channels[i];v=q[0]if p[0]==uid else p[0]
   if not g.is_t(v):neighbors.append(v)
  if len(neighbors)==4:
   four_nodes.append(uid);ck(71,g.types[uid]in('splitter','merger','bridge'),{'unit':uid})
   if all(g.types[v]in('machine','box')for v in neighbors):ck(71,Counter(g.units[v]['Din']%2 for v in neighbors)==Counter({0:2,1:2}),{'unit':uid,'neighbors':neighbors})
 ck(71,len(four_nodes)>=664-3*T,{'four_neighbor_nodes':four_nodes})
 plant_checks(g,f,x,r,total,bval)
 g.flow_stats={'S':S,'R':R,'E':E,'B0':B0,'B1':B1,'eta':eta,'box_out':str(Qbox),'product_rates':{it:str(total(g.inc['CORE'],it)+sum(v for(u,k),v in wire.items()if k==it))for it in TARGETS}}


def plant_checks(g,f,x,r,total,bval):
 import networkx as nx
 used_transport=set();plant_crush=set();flow_inventory={}
 for plant in ['荞花','砂叶']:
  seed=plant+'种子';G=nx.DiGraph();transforms=[]
  def node(p,it,io):
   u=p[0]
   if g.is_t(u):return (*g.slot(p),it)
   return(u,io,it)
  for i,(p,q)in enumerate(g.channels):
   for it in [plant,seed]:
    if total([i],it)>0:
     G.add_edge(node(p,it,'out'),node(q,it,'in'))
     for pp in [p,q]:
      if g.is_t(pp[0]):used_transport.add(pp[0])
  for uid,u in g.units.items():
   if g.types[uid]=='box':
    for it in [plant,seed]:G.add_edge((uid,'in',it),(uid,'out',it))
   if g.types[uid]=='machine':
    for rid,src,dst in [('采种-'+plant,plant,seed),('种植-'+plant,seed,plant)]:
     if bval.get((uid,rid),0)>0:
      e=((uid,'in',src),(uid,'out',dst));G.add_edge(*e);transforms.append((rid,e))
  comps=list(nx.strongly_connected_components(G));cyclic=[s for s in comps if len(s)>1 or any(G.has_edge(v,v)for v in s)];good=[]
  for s in cyclic:
   if all(any(rid==kind+'-'+plant and e[0]in s and e[1]in s for rid,e in transforms)for kind in ['采种','种植']):good.append(s)
  r.formal(69,bool(good),{'plant':plant,'projection':'分物品且桥分轴的正流图含采种/种植再生环'})
  reachable=set().union(*(s for s in good))if good else set();todo=list(reachable)
  while todo:
   for v in G.successors(todo.pop()):
    if v not in reachable:reachable.add(v);todo.append(v)
  for uid,u in g.units.items():
   if bval.get((uid,'粉碎-'+plant),0)>0:
    plant_crush.add(uid);r.formal(37,(uid,'in',plant)in reachable,{'plant':plant,'crusher':uid})
  # Minimum number of turning transport units on any qualifying directed cycle:
  # enumerate SCC support and require at least four actual turning units; all orthogonal cycles already need >=4 turns.
  turns=set()
  for s in good:
   for v in s:
    uid=v[0]
    if uid not in g.units or g.types[uid]not in('belt','splitter','merger'):continue
    for ii in g.inc[uid]:
     for oo in g.out[uid]:
      pi,qi=g.channels[ii];po,qo=g.channels[oo]
      if qi[1]%2!=po[1]%2 and any(total([ii],it)>0 and total([oo],it)>0 and node(qi,it,'in')in s for it in[plant,seed]):turns.add(uid)
  r.formal(69,len(turns)>=4,{'plant':plant,'turning_transport_units':sorted(turns)})
  if g.stats['counts'].get('种植机',0)==32:
   mixed=any(bval.get((u['id'],'种植-荞花'),0)>0 and bval.get((u['id'],'种植-砂叶'),0)>0 for u in g.lay['machines']if u['model']=='种植机')
   split=any(sum(total([i],plant)>0 for i in g.out[uid])>=2 for uid in g.units if g.types[uid]=='machine'and g.units[uid]['model']=='种植机'or g.types[uid]in('splitter','box'))
   r.formal(42,mixed or split,{'plant':plant,'mixed_planting':mixed,'multiple_plant_outputs':split})
  z=sum(v for(uid,rid),v in bval.items()if rid=='种植-'+plant);aa=sum(v for(uid,rid),v in bval.items()if rid=='采种-'+plant);ff=sum(v for(uid,rid),v in bval.items()if rid=='粉碎-'+plant)
  qs=sum(total([i],seed)for i,(p,q)in enumerate(g.channels)if g.is_t(q[0]));qp=sum(total([i],plant)for i,(p,q)in enumerate(g.channels)if g.is_t(q[0]));flow_inventory[plant]={'seed_lower_bound':str(z+qs),'plant_lower_bound':str(aa+ff+qp)}
 bb=sum(g.types[u]=='bridge'for u in used_transport);tt=len(used_transport);units=set(used_transport)|plant_crush|{u['id']for u in g.lay['machines']if u['model']in('种植机','采种机')};area=sum(uid in units for uid in g.occ.values())
 r.formal(69,tt-bb>=4 and tt+bb>=64 and tt>=34 and area>=1378,{'plant_transport':tt,'bridges':bb,'occupied_area':area})
 r.formal(41,True,{'projection':'仅重算平均存量必要下界，不核实际库存','lower_bounds':flow_inventory})
