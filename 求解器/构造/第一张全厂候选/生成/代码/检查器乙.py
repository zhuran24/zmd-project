"""乙：逐对相邻格查询单位边界，重建过程不导入检查器甲。
LP独立使用GLOP，按唯一运输路径消元，不导入甲的LP建模代码。
共享部分仅为规范配方数据、文件指纹和严格JSON/语法解析。
"""
import sys,json
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction
from 目录与流量 import REC,KINDS,MIN,ITEMS,PRODUCTS,FILES,ROOT,sha,strict,load

def audit(c):
 l=c['layout'];grid=[[None]*70 for _ in range(70)];units={};kinds={};errors=[]
 for cat in ('machines','warehouse_outlets','core','power_poles','storage_boxes','transport'):
  for u in [l[cat]] if cat=='core' else l[cat]:
   uid=u['id'];units[uid]=u;kinds[uid]=cat
   if cat=='transport':x0=x1=u['x'];y0=y1=u['y']
   else:x0,x1,y0,y1=(u[z] for z in ['x0','x1','y0','y1'])
   for y in range(y0,y1+1):
    for x in range(x0,x1+1):
     if grid[y][x] is not None:errors.append(f'实体冲突 {x},{y}')
     grid[y][x]=uid
   if cat=='machines':
    w,h=(3,3) if u['kind']=='小' else (5,5) if u['kind']=='中' else (6,4) if u['Din'] in (1,3) else (4,6)
    if (x1-x0+1,y1-y0+1)!=(w,h):errors.append('制造尺寸 '+uid)
   if cat=='core' and (x1-x0!=8 or y1-y0!=8):errors.append('核心尺寸')
   if cat=='power_poles' and (x1-x0!=1 or y1-y0!=1):errors.append('供电桩尺寸')
 def uidat(x,y):return grid[y][x] if 0<=x<70 and 0<=y<70 else None
 def base(x,y,s):
  uid=uidat(x,y)
  if uid is None:return None
  u=units[uid];cat=kinds[uid]
  if cat=='transport':
   if u['type']=='bridge':return None
   if s==u['in_side']:return 'i',(uid,s,0)
   if s==u['out_side']:return 'o',(uid,s,0)
   return None
  if cat=='power_poles':return None
  boundary=(x==u['x1'],y==u['y1'],x==u['x0'],y==u['y0'])[s]
  if not boundary:return None
  off=y-u['y0'] if s in (0,2) else x-u['x0'];p=(uid,s,off)
  if cat in ('machines','storage_boxes'):
   if s==u['Din']:return 'i',p
   if (s+2)%4==u['Din']:return 'o',p
  elif cat=='warehouse_outlets':
   if s==u['Dout'] and off==1:return 'o',p
  else:
   if s%2==u['Din']%2 and 1<=off<=7:return 'i',p
   if s%2!=u['Din']%2 and off in (1,4,7):return 'o',p
  return None
 moves=((1,0),(0,1),(-1,0),(0,-1));bdirs={}
 for t in l['transport']:
  if t['type']!='bridge':continue
  x,y=t['x'],t['y'];uid=t['id']
  for s,(dx,dy) in enumerate(moves):
   other=uidat(x+dx,y+dy)
   if other and units[other].get('type')=='bridge':errors.append('相邻桥 '+uid+' '+other)
  for sides,field in [((0,2),'H_in'),((1,3),'V_in')]:
   facing=[]
   for s in sides:
    dx,dy=moves[s];p=base(x+dx,y+dy,(s+2)%4)
    if p:facing.append((s,p[0]))
   direction=None
   if len(facing)==2 and facing[0][1]!=facing[1][1]:direction=next(s for s,k in facing if k=='o')
   elif facing:errors.append(f'桥轴不能由邻端固定 {uid} {field}')
   if direction!=t[field]:errors.append('桥方向声明错误 '+uid+' '+field)
   bdirs[uid,sides[0]%2]=direction
 def port(x,y,s):
  uid=uidat(x,y)
  if uid and units[uid].get('type')=='bridge':
   d=bdirs[uid,s%2]
   if d is not None:return ('i' if s==d else 'o'),(uid,s,0)
   return None
  return base(x,y,s)
 edges=[]
 for y in range(70):
  for x in range(70):
   for s in (0,1):
    dx,dy=moves[s];a=port(x,y,s);b=port(x+dx,y+dy,s+2)
    if not a or not b or a[0]==b[0]:continue
    if kinds[a[1][0]]!='transport' and kinds[b[1][0]]!='transport':continue
    edges.append((a[1],b[1]) if a[0]=='o' else (b[1],a[1]))
 edges.sort();decl={(tuple(e['from'][k] for k in ('unit','side','offset')),tuple(e['to'][k] for k in ('unit','side','offset'))):e for e in c['design']['physical_channels']}
 if set(edges)!=set(decl):errors.append(f'声明通道不是当且仅当集合:漏{len(set(edges)-set(decl))}/多{len(set(decl)-set(edges))}')
 # Columns expanded independently, no histogram implementation shared with A.
 best=(-1,-1);rect=None
 for x0 in range(65):
  free=[True]*70
  for x1 in range(x0,70):
   free=[old and grid[y][x1] is None for y,old in enumerate(free)]
   if x1-x0+1<6:continue
   y0=0
   for y in range(71):
    if y==70 or not free[y]:
     h=y-y0;w=x1-x0+1
     if h>=6 and (w*h,min(w,h))>best:best=(w*h,min(w,h));rect=dict(x0=x0,x1=x1,y0=y0,y1=y-1)
     y0=y+1
 powered=[]
 for m in l['machines']:
  if any(max(m['x0'],p['x0']-5)<=min(m['x1'],p['x0']+6) and max(m['y0'],p['y0']-5)<=min(m['y1'],p['y0']+6) for p in l['power_poles']):powered.append(m['id'])
 # Independent path decomposition: incoming edge map indexed by transport buffer identity.
 def node(p):return (p[0],p[1]%2) if units[p[0]].get('type')=='bridge' else (p[0],-1)
 starts=[];successor=defaultdict(list);incoming=defaultdict(list)
 for i,(p,q) in enumerate(edges):
  successor[node(p)].append(i);incoming[node(q)].append(i)
  if kinds[p[0]]!='transport':starts.append(i)
 for t in l['transport']:
  slots=[0,1] if t['type']=='bridge' else [-1]
  for ax in slots:
   if ax>=0 and bdirs[t['id'],ax] is None:continue
   if len(successor[t['id'],ax])!=1 or len(incoming[t['id'],ax])!=1:errors.append('运输物品格非一进一出 '+t['id'])
 paths=[];seen=set();srcitems={(u['id'],u['Dout'],1):u['item'] for u in l['warehouse_outlets']};srcitems.update({('CORE',p['side'],p['offset']):p['item'] for p in l['core']['output_items']})
 for st in starts:
  s=edges[st][0];route=[];j=st;local=set()
  while j not in local:
   local.add(j);route.append(j);seen.add(j);t=edges[j][1]
   if kinds[t[0]]!='transport':
    its=set([srcitems[s]]) if s in srcitems else {v for r in units[s[0]]['recipe_ids'] for v in REC[r][2]}
    if len(its)!=1:errors.append('非单物品源 '+repr(s));break
    item=next(iter(its));paths.append(dict(source=s,target=t,item=item,edges=route))
    if kinds[t[0]]=='machines':
     wanted={it for r in units[t[0]]['recipe_ids'] for it in REC[r][1]}
     if item not in wanted:errors.append('配方外来料 '+t[0]+' '+item)
    elif t[0]=='CORE' and item not in PRODUCTS:errors.append('非成品入库 '+item)
    for ei in route:
     if set(decl.get(edges[ei],{}).get('allowed_items',[]))!={item}:errors.append('声明物品不符 '+str(ei))
    break
   nxt=successor[node(t)]
   if len(nxt)!=1:errors.append('路径断头 '+repr(s));break
   j=nxt[0]
  else:errors.append('运输环 '+repr(s))
 if len(seen)!=len(edges):errors.append('无源运输通道 '+str(len(edges)-len(seen)))
 # Species propagation for design-outside recipes: this p2p single-source/path case reduces to inputs.
 reached=defaultdict(set)
 for p in paths:reached[p['target'][0]].add(p['item'])
 extra=[]
 for m in l['machines']:
  for r,(model,ins,outs,tt) in REC.items():
   if model==m['model'] and r not in m['recipe_ids'] and set(ins)<=reached[m['id']]:extra.append((m['id'],r))
 if extra:errors.append('设计外配方可触发 '+repr(extra))
 return dict(errors=errors,edges=edges,grid=grid,units=units,kinds=kinds,paths=paths,powered=powered,maximum_rectangle=rect,score=best,sources=srcitems)

def lp_independent(c,g):
 from ortools.linear_solver import pywraplp
 S=pywraplp.Solver.CreateSolver('GLOP');S.SetNumThreads(1);nets=g['paths'];flows=[S.NumVar(0,1,f'p{j}') for j in range(len(nets))];batch={}
 for m in c['layout']['machines']:
  vv=[]
  for r in m['recipe_ids']:
   v=S.NumVar(0,1,f'{m["id"]}:{r}');batch[m['id'],r]=v;vv.append(REC[r][3]*v)
  S.Add(sum(vv)<=int(m['id'] in g['powered'] and m['settings']['manufacture_on']))
 missing=[]
 for port,item in g['sources'].items():
  js=[j for j,p in enumerate(nets) if p['source']==port and p['item']==item]
  S.Add(sum(flows[j] for j in js)==1)
  if not js:missing.append(dict(port=list(port),item=item,equation='0 = 1'))
 for m in c['layout']['machines']:
  for item in ITEMS:
   ii=[flows[j] for j,p in enumerate(nets) if p['target'][0]==m['id'] and p['item']==item]
   oo=[flows[j] for j,p in enumerate(nets) if p['source'][0]==m['id'] and p['item']==item]
   use=[REC[r][1].get(item,0)*batch[m['id'],r] for r in m['recipe_ids']];prod=[REC[r][2].get(item,0)*batch[m['id'],r] for r in m['recipe_ids']]
   S.Add(sum(ii)==sum(use));S.Add(sum(oo)==sum(prod))
 for item in ITEMS:
  term=sum(flows[j] for j,p in enumerate(nets) if p['target'][0]=='CORE' and p['item']==item)
  if item in PRODUCTS:S.Add(term>=float(PRODUCTS[item]))
  else:S.Add(term==0)
 # A P2P path occupies each buffer independently, with no transport sharing except bridge axes.
 delta=S.NumVar(0,1,'delta')
 for f in flows:S.Add(f>=delta)
 S.Maximize(delta);status=S.Solve();out=dict(status=status,status_name={0:'OPTIMAL',1:'FEASIBLE',2:'INFEASIBLE',3:'UNBOUNDED',4:'ABNORMAL',6:'NOT_SOLVED'}.get(status,str(status)),paths=len(nets),empty_source_equalities=missing,certified_infeasible=bool(missing),base_feasible=status in (0,1),scope='固定p2p路径图；对每条通道守恒消元后的连续LP；与甲建模独立')
 if status in (0,1):
  ff=[Fraction(f.solution_value()).limit_denominator(1000000) for f in flows];bb={k:Fraction(v.solution_value()).limit_denominator(1000000) for k,v in batch.items()};bad=[]
  for port,item in g['sources'].items():
   if sum(ff[j] for j,p in enumerate(nets) if p['source']==port and p['item']==item)!=1:bad.append(('source',port))
  for m in c['layout']['machines']:
   for item in ITEMS:
    for direction,part in [('source',2),('target',1)]:
     q=sum(ff[j] for j,p in enumerate(nets) if p[direction][0]==m['id'] and p['item']==item);expected=sum(REC[r][part].get(item,0)*bb[m['id'],r] for r in m['recipe_ids'])
     if q!=expected:bad.append((m['id'],item,direction,str(q),str(expected)))
   if sum(REC[r][3]*bb[m['id'],r] for r in m['recipe_ids'])>1:bad.append(('time',m['id']))
  for it,goal in PRODUCTS.items():
   if sum(ff[j] for j,p in enumerate(nets) if p['target'][0]=='CORE' and p['item']==it)<goal:bad.append(('target',it))
  out.update(exact_errors=bad,delta=str(min(ff,default=0)),exact_positive=not bad and bool(ff) and min(ff)>0)
 return out

def run(path,out):
 c=load(path);syntax=strict(c)
 if syntax:result={'syntax_errors':syntax,'all_static_pass':False}
 else:
  g=audit(c);lp=lp_independent(c,g);rect=c['empty_rectangle'];score=((rect['x1']-rect['x0']+1)*(rect['y1']-rect['y0']+1),min(rect['x1']-rect['x0']+1,rect['y1']-rect['y0']+1));empty=all(g['grid'][y][x] is None for x in range(rect['x0'],rect['x1']+1) for y in range(rect['y0'],rect['y1']+1))
  cnt=Counter(m['model'] for m in c['layout']['machines']);sourcecount=Counter(g['sources'].values());bounds_ok=all(cnt[k]>=n for k,n in MIN.items());binding=c['design'].get('source_bindings',[]);bindports=[tuple(b['port'][k] for k in ('unit','side','offset')) for b in binding]
  bindpass=len(binding)==52 and len(set(b['logical_source_id'] for b in binding))==52 and len(set(bindports))==52 and set(bindports)==set(g['sources'])
  bsrc={q['id']:q['item'] for q in load(ROOT/'求解器/数据/候选B/contract.json')['sources']}
  bindpass=bindpass and {b['logical_source_id'] for b in binding}==set(bsrc) and all(g['sources'].get(p)==bsrc.get(z['logical_source_id']) for p,z in zip(bindports,binding))
  formal=[];lines=(ROOT/FILES['constraints']).read_text().splitlines()
  for i,line in enumerate(lines):
   if not line.startswith('    据：'):continue
   n=lines[i-1].split('：',1)[0];state='未实现完整静态投影或运行阶段待证';ev=[]
   if n=='机型下限':state='已核' if bounds_ok else '违反';ev=[dict(cnt)]
   elif n=='取货口配置':state='违反' if lp['empty_source_equalities'] else '已核静态端口配置';ev=[dict(sourcecount),len(lp['empty_source_equalities'])]
   elif n=='端口对接':state='已核';ev=[len(g['edges'])]
   elif n=='1113 位置' and g['score'][0]!=1113:state='静态可证前件不成立';ev=[g['score'][0]]
   elif n in ['接通先后','分叉分支','传输相位','判定先后','种子起动','周期倍数','轮询均分','混料轮询分料','回路存量','植物沿途存量']:state='运行阶段待证'
   formal.append(dict(name=n,status=state,premise='按本候选实体和独立路径图核查；实际循环态未给定',evidence=ev,remaining='此状态不宣告条文的全部运行量词成立'))
  result=dict(syntax_errors=[],errors=g['errors'],channels=len(g['edges']),paths=len(g['paths']),maximum_rectangle=g['maximum_rectangle'],area=g['score'][0],short_side=g['score'][1],rectangle_pass=empty and score==g['score'],powered=len(g['powered']),occupied=sum(v is not None for row in g['grid'] for v in row),model_counts=dict(cnt),minimum_counts_pass=bounds_ok,source_counts=dict(sourcecount),source_bindings_pass=bindpass,lp=lp,formal_constraints=formal,all_static_pass=False,unimplemented_static='正式约束的完整几何/正流支撑/分区再生细项未实现，禁止全静态通过')
  def pr(p):return dict(unit=p[0],side=p[1],offset=p[2])
  (Path(out).parent/'乙-重建通道.json').write_text(json.dumps([{'from':pr(p),'to':pr(q)} for p,q in g['edges']],ensure_ascii=False,indent=1))
 result.update(candidate_sha256=sha(path),checker_sha256=sha(__file__),common_catalog_parser_sha256=sha(Path(__file__).with_name('目录与流量.py')))
 Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k in ['channels','paths','area','all_static_pass','syntax_errors']},ensure_ascii=False))
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
