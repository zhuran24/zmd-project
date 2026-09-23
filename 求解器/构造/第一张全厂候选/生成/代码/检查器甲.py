"""甲：以 (格,边) 端口字典重建。桥仅在读取全部非桥端口后定向。
本实现的证明边界见报告；未实现条目禁止全静态通过。
"""
import json,sys
from pathlib import Path
from collections import defaultdict,Counter
from 目录与流量 import *

def reconstruct(c):
 l=c['layout'];occ={};units={};ports={};errs=[];trids=set();bridges=[]
 def put(u,cat,cells):
  units[u['id']]=u
  for p in cells:
   if p in occ:errs.append(f'重叠 {p}: {occ[p]}/{u["id"]}')
   if not(0<=p[0]<70 and 0<=p[1]<70):errs.append('出界 '+u['id'])
   occ[p]=u['id']
 def port(u,s,o,ty):
  xy=[(u['x1'],u['y0']+o),(u['x0']+o,u['y1']),(u['x0'],u['y0']+o),(u['x0']+o,u['y0'])][s]
  ports[(xy,s)]=(ty,(u['id'],s,o))
 for cat in ['machines','warehouse_outlets','power_poles','storage_boxes','core']:
  for u in [l[cat]] if cat=='core' else l[cat]:
   put(u,cat,[(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)])
   w,h=u['x1']-u['x0']+1,u['y1']-u['y0']+1
   if cat=='machines':
    expected=(3,3) if u['kind']=='小' else (5,5) if u['kind']=='中' else (4,6) if u['Din']%2==0 else (6,4)
    if (w,h)!=expected:errs.append('机型尺寸 '+u['id'])
   if cat=='power_poles':
    if (w,h)!=(2,2):errs.append('桩尺寸 '+u['id'])
    continue
   if cat in ['machines','storage_boxes']:
    for s,ty in [(u['Din'],'in'),((u['Din']+2)%4,'out')]:
     for o in range(h if s%2==0 else w):port(u,s,o,ty)
   if cat=='warehouse_outlets':
    if u['Dout']==0 and (u['x0']!=0 or (w,h)!=(1,3)):errs.append('左矿口几何 '+u['id'])
    if u['Dout']==1 and (u['y0']!=0 or (w,h)!=(3,1)):errs.append('下矿口几何 '+u['id'])
    port(u,u['Dout'],1,'out')
   if cat=='core':
    if (w,h)!=(9,9):errs.append('核心尺寸')
    expected={(s,o) for s in [(u['Din']+1)%4,(u['Din']+3)%4] for o in [1,4,7]}
    if {(q['side'],q['offset']) for q in u['output_items']}!=expected or len(u['output_items'])!=6:errs.append('核心六口配置')
    for s in [u['Din'],(u['Din']+2)%4]:
     for o in range(1,8):port(u,s,o,'in')
    for s,o in expected:port(u,s,o,'out')
 for t in l['transport']:
  p=(t['x'],t['y']);put(t,'transport',[p]);trids.add(t['id'])
  if t['type']=='bridge':bridges.append(t);continue
  for s,ty in [(t['in_side'],'in'),(t['out_side'],'out')]:ports[(p,s)]=(ty,(t['id'],s,0))
 for t in bridges:
  p=(t['x'],t['y'])
  for dx,dy in D:
   n=occ.get((p[0]+dx,p[1]+dy))
   if n and units[n].get('type')=='bridge':errs.append('N4b桥相邻 '+t['id']+' '+n)
  for ax,ends in [('H_in',(0,2)),('V_in',(1,3))]:
   facing={s:ports.get(((p[0]+D[s][0],p[1]+D[s][1]),(s+2)%4)) for s in ends}
   fs={s:v for s,v in facing.items() if v}
   got=None
   if len(fs)==2 and len({v[0] for v in fs.values()})==2:
    got=next(s for s,v in fs.items() if v[0]=='out')
   elif fs:errs.append('N4a桥邻端不成一取一存 '+t['id']+' '+ax+' '+repr(fs))
   if got!=t[ax]:errs.append('桥声明方向不符 '+t['id']+' '+ax)
   if got is not None:
    ports[(p,got)]=('in',(t['id'],got,0));ports[(p,(got+2)%4)]=('out',(t['id'],(got+2)%4,0))
 edges=[]
 for (p,s),(ty,r) in ports.items():
  if ty!='out':continue
  q=(p[0]+D[s][0],p[1]+D[s][1]);v=ports.get((q,(s+2)%4))
  if v and v[0]=='in' and (r[0] in trids or v[1][0] in trids):edges.append((r,v[1]))
 powered=set()
 for u in l['machines']+l['storage_boxes']:
  if any(u['x0']<=p['x0']+6 and u['x1']>=p['x0']-5 and u['y0']<=p['y0']+6 and u['y1']>=p['y0']-5 for p in l['power_poles']):powered.add(u['id'])
 return dict(occ=occ,units=units,ports=ports,edges=sorted(edges),errors=errs,powered=powered)

def maxrect(occ):
 best=(-1,-1);ans=None
 for y0 in range(65):
  valid=[True]*70
  for y1 in range(y0,70):
   for x in range(70):valid[x]=valid[x] and (x,y1) not in occ
   if y1-y0+1<6:continue
   start=0
   for x in range(71):
    if x==70 or not valid[x]:
     w=x-start;h=y1-y0+1
     if w>=6 and (w*h,min(w,h))>best:best=(w*h,min(w,h));ans=dict(x0=start,y0=y0,x1=x-1,y1=y1)
     start=x+1
 return ans,best

def analyze(c,g):
 errors=[];edges=g['edges'];units=g['units'];tr={t['id'] for t in c['layout']['transport']};ms={m['id']:m for m in c['layout']['machines']};slots=set()
 def slot(p):return (p[0],p[1]%2 if units[p[0]].get('type')=='bridge' else 0)
 inc=defaultdict(list);out=defaultdict(list)
 for k,(a,b) in enumerate(edges):out[slot(a)].append(k);inc[slot(b)].append(k)
 for t in c['layout']['transport']:
  for ax in ([i for i,k in enumerate(['H_in','V_in']) if t[k] is not None] if t['type']=='bridge' else [0]):
   s=(t['id'],ax);slots.add(s)
   if len(inc[s])!=1 or len(out[s])!=1:errors.append(f'运输断头或多接 {s}: in={len(inc[s])}, out={len(out[s])}')
 decl=c['design']['physical_channels'];ds={edgekey(e) for e in decl};es=set(edges)
 if ds!=es:errors.append(f'N5a声明差异: 缺{len(es-ds)} 多{len(ds-es)}')
 if len(ds)!=len(decl):errors.append('重复物理端点')
 paths=[];seen=set();candidates={edgekey(e):e['allowed_items'] for e in decl};sourceitems={(u['id'],u['Dout'],1):{u['item']} for u in c['layout']['warehouse_outlets']}
 sourceitems.update({('CORE',q['side'],q['offset']):{q['item']} for q in c['layout']['core']['output_items']})
 possible_in=defaultdict(set);possible_out={m:set(i for r in u['recipe_ids'] for i in REC[r][2]) for m,u in ms.items()}
 for k,(a,b) in enumerate(edges):
  if a[0] in tr:continue
  route=[];cur=k;local=set();target=None
  while cur not in local:
   local.add(cur);seen.add(cur);route.append(cur);dst=edges[cur][1]
   if dst[0] not in tr:target=dst;break
   nxt=out[slot(dst)]
   if len(nxt)!=1:break
   cur=nxt[0]
  if target is None:errors.append('P2源路径未到达非运输存货口 '+repr(a))
  else:paths.append((a,target,route))
 if len(seen)!=len(edges):errors.append(f'无非运输源的运输支撑 {len(edges)-len(seen)} 条')
 # The fixed point never uses allowed_items as a filter.
 changed=True
 while changed:
  changed=False
  for a,b,route in paths:
   its=sourceitems.get(a,possible_out.get(a[0],set()))
   if b[0] in ms and not its<=possible_in[b[0]]:possible_in[b[0]]|=its;changed=True
  for mid,m in ms.items():
   for r,(model,inputs,outputs,t) in REC.items():
    if model==m['model'] and set(inputs)<=possible_in[mid] and not set(outputs)<=possible_out[mid]:possible_out[mid]|=set(outputs);changed=True
 for mid,m in ms.items():
  allowed=set(i for r in m['recipe_ids'] for i in REC[r][1]);allallowed=set(i for r in REC.values() if r[0]==m['model'] for i in r[1])
  if possible_in[mid]-allallowed:errors.append(f'误料 {mid}: {sorted(possible_in[mid]-allallowed)}')
  if possible_in[mid]-allowed:errors.append(f'设计外配方原料 {mid}: {sorted(possible_in[mid]-allowed)}')
 for a,b,route in paths:
  its=sourceitems.get(a,possible_out.get(a[0],set()))
  for k in route:
   if len(candidates.get(edges[k],[]))!=1 or not its<=set(candidates.get(edges[k],[])):errors.append('P2通道声明不能挡货 '+str(k))
  if b[0]=='CORE' and its-set(PRODUCTS):errors.append('非成品进入核心 '+repr(a))
 if any(len(m['recipe_ids'])!=1 for m in ms.values() if m['model'] in ['粉碎机','采种机']):errors.append('P6违反')
 # B-source bindings must preserve every logical source identity and item.
 source_definition={s['id']:s['item'] for s in load(ROOT/'求解器/数据/候选B/contract.json')['sources']}
 bindings=c['design'].get('source_bindings',[])
 mapped=[key(z['port']) for z in bindings]
 if len(bindings)!=52 or {z['logical_source_id'] for z in bindings}!=set(source_definition) or len(set(mapped))!=52 or set(mapped)!=set(sourceitems):errors.append('52矿源映射不完整')
 for z in bindings:
  if sourceitems.get(key(z['port']))!={source_definition.get(z['logical_source_id'])}:errors.append('矿源身份物品不符 '+z['logical_source_id'])
 return dict(errors=errors,paths=[dict(source=ref(a),target=ref(b),edges=route) for a,b,route in paths],possible_input={k:sorted(v) for k,v in possible_in.items()},unseen_edges=sorted(set(range(len(edges)))-seen))

def formal(c,g,a,lp,rect,score):
 text=(ROOT/FILES['constraints']).read_text();items=[];lines=text.splitlines()
 for i,line in enumerate(lines):
  if line.startswith('    据：'):
   items.append(lines[i-1].split('：',1)[0])
 assert len(items)==72,len(items)
 records={n:dict(name=n,status='运行阶段待证',premise='正式条文的循环态、可达性或时序前件未由静态数据提供',evidence=[],remaining='须对调试后全部相关可达循环态和允许的先后取值证明') for n in items}
 def setr(n,ok,evidence,remaining='本项静态必要条件不证明运行达标'):
  records[n]=dict(name=n,status='已核静态投影' if ok else '违反静态必要条件',premise='由实体布局重算；涉及正流的计数仅在精确平均流见证存在时生效',evidence=evidence,remaining=remaining)
 l=c['layout'];cnt=Counter(m['model'] for m in l['machines']);T=len(l['transport']);b=sum(t['type']=='bridge' for t in l['transport']);P=len(l['power_poles']);A=score[0];core=l['core'];outlets=l['warehouse_outlets']
 counts=Counter(u['Dout'] for u in outlets);ore=Counter(u['item'] for u in outlets);ore.update(q['item'] for q in core['output_items'])
 setr('端口对接',all('type' in g['units'][x[0]] or 'type' in g['units'][y[0]] for x,y in g['edges']),[len(g['edges'])])
 setr('机型下限',all(cnt[k]>=v for k,v in MIN.items()),[dict(cnt)])
 setr('出库上限',counts=={0:23,1:23},[dict(counts)])
 source={(u['id'],u['Dout'],1) for u in outlets}|{('CORE',q['side'],q['offset']) for q in core['output_items']}
 active={p for p,q in g['edges']};miss=sorted(source-active)
 setr('取货口配置',counts=={0:23,1:23} and ore=={'源矿':18,'蓝铁矿':34} and not miss,[dict(ore),{'missing_physical_outputs':[ref(p) for p in miss]}],'全部满速另由联合 LP 核验；真实循环态满速仍待证')
 gaps={d:[i for i in range(70) if ((0,i) if d==0 else (i,0)) not in g['occ']] for d in [0,1]}
 setr('边带排布',all(len(gaps[d])==1 and gaps[d][0]%3==0 for d in [0,1]) and (0 in gaps[0] or 0 in gaps[1]) and not miss,[gaps,{'source_output_missing':len(miss)}])
 setr('供电下限',P>=10 and len(g['powered'])==len(l['machines']),[{'poles':P,'powered':len(g['powered']),'unpowered':sorted(set(m['id'] for m in l['machines'])-g['powered'])}],'覆盖和桩数已查；每桩24/23/14/8台几何上限及J预算另属未实现静态细项')
 setr('核心邻格',not [p for p in source if p[0]=='CORE' and p not in active],[{'connected_output_ports':sum(p[0]=='CORE' for p in source&active)}],'核心周围空矩形接触细项未实现')
 setr('占地下界',len(g['occ'])>=(3856 if b==0 else 3758),[{'occupied':len(g['occ']),'bridges':b}])
 setr('空矩形上界',A<=(1040 if b==0 else 1113) and min(rect['x1']-rect['x0']+1,rect['y1']-rect['y0']+1)>=6,[rect,{'area':A}])
 setr('增机面积界',not(cnt=={'粉碎机':69,'精炼炉':51,'研磨机':32,'塑形机':6,'配件机':6,'种植机':32,'采种机':17,'封装机':3,'灌装机':3}) or A<=1089,[{'area':A}])
 setr('运输下限',T>=180 and T+b>=306,[{'T':T,'b':b}],'一般下限已查；附条件207/208/209与200的细分另属未实现静态细项')
 setr('准入累计',True,['没有准入口'],'静态可证触发对象为空')
 for n in ['密集结点','准入满额窗口','传输按仓库余量判定','传输箱不满','箱内滞货封住后格','满速箱头限存','混做清空','混做连续批次出货','灌装混线']:
  no=not l['storage_boxes'] if ('箱' in n or n=='传输按仓库余量判定') else all(len(m['recipe_ids'])==1 for m in l['machines']) if n.startswith('混做') else n!='灌装混线'
  if n=='灌装混线':no=sum(sum(1 for aa,bb in g['edges'] if bb[0]==m['id'])>=4 for m in l['machines'] if m['model']=='灌装机')!=2
  if no:records[n]=dict(name=n,status='静态可证前件不成立',premise='本候选无相应单位/单配方限制，或所查通道数前件不成立',evidence=[],remaining='解除限制时须重审前件')
 static_missing=['核心离带','核心取货边朝带','角区','运输降幅','面积预算','侧旁供电','矩形离带','矿石走廊','内带缺口']
 for n in static_missing:records[n]=dict(name=n,status='未实现静态细项',premise='本版本未实现该条全部几何公式',evidence=[],remaining='阻止全静态通过；不能列为运行范围外')
 # Average-flow consequences are not asserted after an infeasible LP.
 for n in ['矿石需求','物料流量','端口速率','满载配置','研磨进料','封装进料','双料逐机收支与存货界','满速独占','矿线专机','非成品零入库','矿系不入库','成品汇入','回路守恒','植物分区收支','植物再生来路','植株半分','运输端口收支','矿石分流与专机','共用接货格余量','箱体接口','箱体预算','箱体过站','回路转弯','四通结点','通道下限','入库途径','存货误料停机与可用台数']:
  records[n]=dict(name=n,status='平均流前置检查失败' if not lp.get('base_feasible') else '未实现完整静态投影',premise='联合LP必须先有精确正流见证，之后按见证判定条文前件',evidence=[{'lp_status':lp['status'],'certified':lp['certified']}],remaining='即使LP可行仍须逐条补计数、再生路径与运行剩余义务')
 # Structural counts are upper bounds on counts of positive-flow channels. If even
 # these upper bounds miss an unconditional minimum, no LP witness is needed to reject.
 trids={t['id'] for t in l['transport']};S=sum(a[0] not in trids for a,b in g['edges']);R=sum(b[0] not in trids for a,b in g['edges']);E=len(g['edges'])-S-R
 setr('运输端口收支',S>=312 and R>=307,[{'structural_S_upper':S,'structural_R_upper':R,'E':E,'required_S':312,'required_R':307}],'物理通道数是正流支撑数的上界；上界已低于必要下界，故此固定候选失败')
 machine_by={m['id']:m for m in l['machines']};ci=Counter();co=Counter()
 for aa,bb in g['edges']:
  if bb[0] in machine_by:ci[machine_by[bb[0]]['model']]+=1
  if aa[0] in machine_by:co[machine_by[aa[0]]['model']]+=1
 minin={'粉碎机':68,'精炼炉':51,'研磨机':95,'塑形机':11,'配件机':6,'种植机':32,'采种机':16,'封装机':15,'灌装机':11}
 minout={'粉碎机':95,'精炼炉':51,'研磨机':32,'塑形机':6,'配件机':6,'种植机':32,'采种机':32,'封装机':1,'灌装机':1}
 setr('通道下限',all(ci[k]>=v for k,v in minin.items()) and all(co[k]>=v for k,v in minout.items()),[{'structural_in_upper':dict(ci),'required_in':minin,'structural_out_upper':dict(co),'required_out':minout}],'结构通道上界不足即拒绝；更少的实际正流通道不能修复')
 coreinputs=sum(bb[0]=='CORE' for aa,bb in g['edges'])
 setr('成品汇入',coreinputs>=6,[{'K_upper':coreinputs,'B':0,'C':0,'required_K_plus_3B_plus_2C':6}],'无箱、无汇流，核心物理存货通道上界不足6即拒绝')
 records['1113 位置']=dict(name='1113 位置',status='静态可证前件不成立',premise='重算空矩形面积为'+str(A)+'，不等于1113',evidence=[rect],remaining='面积达到1113时须核八个允许锚点')
 return list(records.values())

def run(path,out):
 c=load(path);se=strict(c)
 if se:result={'schema_errors':se,'all_static_pass':False}
 else:
  g=reconstruct(c);a=analyze(c,g);rect,score=maxrect(g['occ']);decl=c['empty_rectangle'];de=(decl['x1']-decl['x0']+1)*(decl['y1']-decl['y0']+1);ds=min(decl['x1']-decl['x0']+1,decl['y1']-decl['y0']+1)
  re=[(x,y) for x in range(decl['x0'],decl['x1']+1) for y in range(decl['y0'],decl['y1']+1) if (x,y) in g['occ']]
  lp=solve_lp(c,g['edges'],g['units'],g['powered'],'甲');fr=formal(c,g,a,lp,rect,score)
  result=dict(schema_errors=[],geometry_errors=g['errors'],structural_errors=a['errors'],channels=len(g['edges']),paths=len(a['paths']),maximum_rectangle=rect,area=score[0],short_side=score[1],rectangle_pass=not re and (de,ds)==score,powered=len(g['powered']),occupied=len(g['occ']),lp=lp,formal_constraints=fr,all_static_pass=False)
  result['unimplemented_static']=[x['name'] for x in fr if x['status'].startswith('未实现')]
  (Path(out).parent/'甲-重建通道.json').write_text(json.dumps([{'from':ref(x),'to':ref(y)} for x,y in g['edges']],ensure_ascii=False,indent=1))
 result.update(candidate_sha256=sha(path),checker_sha256=sha(__file__),common_lp_sha256=sha(Path(__file__).with_name('目录与流量.py')),scope='p2p；几何/通道/物品传播和LP已实现，正式约束覆盖见逐项状态；缺项阻止全静态通过')
 Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k in ['candidate_sha256','schema_errors','channels','paths','area','all_static_pass']},ensure_ascii=False))
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
