import sys,json
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'生成/代码'))
from 目录与流量 import *
BASE=Path(__file__).resolve().parent
from 检查器甲 import maxrect
src=Path(sys.argv[1]);data=load(src);paths={int(k):v for k,v in data['paths'].items()};nets=data['nets'];occpaths=defaultdict(list)
for i,route in paths.items():
 for c,di,do in route:occpaths[tuple(c)].append((i,di,do))
transport=[]
for (x,y),uses in sorted(occpaths.items()):
 t=dict(id=f'T{x}_{y}',x=x,y=y)
 if len(uses)==1:t.update(type='belt',in_side=(uses[0][1]+2)%4,out_side=uses[0][2])
 else:
  assert len(uses)==2 and all(di==do for i,di,do in uses)
  t.update(type='bridge',H_in=next((di+2)%4 for i,di,do in uses if di%2==0),V_in=next((di+2)%4 for i,di,do in uses if di%2==1))
 transport.append(t)
def pr(uid,s,o=0):return dict(unit=uid,side=s,offset=o)
bind={b['logical_source_id']:b['port'] for b in data['bindings']};chs=[];completed=[]
for i,route in sorted(paths.items()):
 n=nets[i];first=route[0];last=route[-1];start=next(p for p in n['starts'] if p[0]==first[0] and p[1]==first[1]);goal=next(p for p in n['goals'] if p[0]==last[0] and (p[1]+2)%4==last[2]);a=bind[n['source']] if n['source'] in bind else pr(n['source'],start[1],start[2]);b=pr(n['target'],goal[1],goal[2]);chain=[]
 def emit(x,y):
  cid=f'PC{len(chs):06}';chs.append(dict(id=cid,**{'from':x,'to':y},allowed_items=[n['item']]));chain.append(cid)
 emit(a,pr(f'T{first[0][0]}_{first[0][1]}',(first[1]+2)%4))
 for p,q in zip(route,route[1:]):emit(pr(f'T{p[0][0]}_{p[0][1]}',p[2]),pr(f'T{q[0][0]}_{q[0][1]}',(q[1]+2)%4))
 emit(pr(f'T{last[0][0]}_{last[0][1]}',last[2]),b)
 completed.append(dict(id=n['id'],**{'from':a,'to':b},item=n['item'],rate=n['rate'],path=chain))
l=dict(W=70,H=70,machines=data['machines'],warehouse_outlets=data['warehouse_outlets'],core=data['core'],power_poles=data['power_poles'],storage_boxes=[],transport=transport,vin=[],vout=[])
occupied={}
for cat in ['machines','warehouse_outlets','core','power_poles']:
 for u in [l[cat]] if cat=='core' else l[cat]:
  for x in range(u['x0'],u['x1']+1):
   for y in range(u['y0'],u['y1']+1):assert (x,y) not in occupied;occupied[x,y]=u['id']
for t in transport:assert (t['x'],t['y']) not in occupied;occupied[t['x'],t['y']]=t['id']
def covered(m,p):return m['x0']<=p['x0']+6 and m['x1']>=p['x0']-5 and m['y0']<=p['y0']+6 and m['y1']>=p['y0']-5
extra=[]
while True:
 un=[m for m in l['machines'] if not any(covered(m,p) for p in l['power_poles'])]
 if not un:break
 best=None;score=0
 for x in range(1,69):
  for y in range(1,69):
   if any((x+i,y+j) in occupied or (x+i>=64 and y+j>=64) for i in range(2) for j in range(2)):continue
   p=dict(id=f'P{len(l["power_poles"]):03}',x0=x,y0=y,x1=x+1,y1=y+1,orientation=0);q=sum(covered(m,p) for m in un)
   if q>score:score=q;best=p
 if best is None:break
 l['power_poles'].append(best);extra.append(best)
 for x in range(best['x0'],best['x1']+1):
  for y in range(best['y0'],best['y1']+1):occupied[x,y]=best['id']
rect,score=maxrect(occupied);assert rect is not None
restr=[]
def restriction(i,src,statement,loss,release):
 restr.append(dict(id=i,source=src,statement=statement,coverage_loss=loss,release_obligations=release,failure_scope='只覆盖本候选字节固定的占格、朝向、设定、配方和通道；LP仍放开允许物品的连续流与批率。生成器的有限搜索失败不排除其他摆放或指派。初态、调试、全部合法先后和可达循环态未覆盖，不降低U，也不更新L。'))
requirements={
'P1':'只用传送带和桥，不用分流器、汇流器、准入口或协议储存箱。',
'P2':'每条非运输端口到非运输端口路径只声明一种物品，桥不换轴，途中不经过其他非运输单位。',
'P3':'要求形成的结构通道均承载严格正设计流；本文件是待验候选，不以登记本项宣告其满足。',
'P4':'要求桥的使用轴双端均在用，未用轴两端没有相向端口。','P5':'两座桥不得正交相邻。','P6':'每台粉碎机与采种机只声明一种配方。',
'N1':'有至少两条取货通道的非运输单位不得直连汇流器。','N2':'有至少两条存货通道的单位不得有来自分流器的通道，桥按物理单位汇总。',
'N3a':'承载正流的准入口累计上限必须为空。','N3b':'限种准入口直接上游被拒物品须有同物品格的另一条不按身份拒绝的结构出口。',
'N4a':'桥轴方向由两端邻端口一取一存推导，与声明相符；未用轴双端均无朝它的端口。','N4b':'不允许两桥正交相邻。','N5a':'全部物理通道由端口相遇当且仅当重算，必须与声明端点集合相等。','N5b':'全部结构通道的物品流之和严格为正，须由共同delta或精确正流见证确认。'}
for i,st in requirements.items():
 restriction(i,['shape'] if i in ['P1','P2','P5','N4b'] else ['dynamic'],st+' 来源：会议3冻结稿§1.3及第三节第3条、格式.md§8.2。','不覆盖违反该受限类条件但可能依靠混料、特殊运输、优先级或动态调试运行的布局。','撤去后须按完整单位语义补表示、物品/容量核验以及相应先后与运行证明。')
restriction('fixed-b-counts',['shape'],'沿用候选B的219台数和逐机单配方：粉碎69、精炼51、研磨32、塑形6、配件6、种植32、采种17、封装3、灌装3。所有制造开关开启。','不覆盖217/218台混做分支、增机以及其他单配方分配。','允许变台数、混做配方后重新核物料平衡、尺寸、误料与全部受限类条件。')
restriction('all-single-recipe',['dynamic'],'P6以外的所有制造单位也各只声明一配方；来源是本轮候选构造选择，不归因于P2。','排除其他机型混做配方的布局。','补逐机多配方连续批率和实际配方触发、清空及误料证明。')
restriction('fixed-border',['shape'],'左、下边均从坐标1起每3格放一口，角格(0,0)空；52个物理矿口与ORE身份一一绑定。来源：会议3测点的一个边带分支。','排除边带唯一空格在其他合法位置的排布与不同矿口身份指派。','开放空格位置与来源映射，并重新按端口和矿石能力布线。')
restriction('fixed-placement',['shape'],'机器、核心及供电桩位置固定为本JSON；搜索预留右上(64,64)至(69,69)六乘六空区。','不覆盖其他实体位置、朝向、供电配置和留白位置。','开放摆放并重新求解全部路径、覆盖和最大空矩形；固定摆放失败不证明全域失败。')
restriction('search-feed-reassignment',['shape','numeric'],'以候选B的物品和精确速率类别作启发式匹配标签，允许同物品同速率记录重指派目标；只导出已布通的完整路径。没有附logical_feeds，故最终LP不固定B速率/315条端点指派。来源：本轮指派与布线.py。','搜索未覆盖跨速率拆并、其他台数/配方及全体指派。未布通路径不充当已兑现接口。','开放指派、速率及布线支持后补完整实体路径；所有缺失供需仍在LP内，不能由省略路径免掉。')
prov=['求解器/数据/候选B/contract.json','求解器/会议成果/会议3/共识稿-v4-7aae9e20.md','求解器/构造/第一张全厂候选/格式.md']
c=dict(schema='full-factory-static-v1',candidate_id='factory-static-repair-0001',source_fingerprints=FINGERPRINTS,provenance=[dict(path=p,sha256=sha(ROOT/p)) for p in prov],targets={i:str(q) for i,q in PRODUCTS.items()},layout=l,empty_rectangle=rect,design={'class':'p2p','physical_channels':chs,'restrictions':restr,'source_bindings':data['bindings']},flow_witness=None)
c['design']['restrictions']=load(BASE.parent/'生成/候选.json')['design']['restrictions']
(BASE/'候选-新摆放.json').write_text(json.dumps(c,ensure_ascii=False,indent=2))
(BASE/'实验/已完成路径.json').write_text(json.dumps(completed,ensure_ascii=False,indent=2))
(BASE/'实验/导出摘要.json').write_text(json.dumps(dict(source=str(src),source_sha256=sha(src),routed=len(paths),total=len(nets),missing=[n['id'] for i,n in enumerate(nets) if i not in paths],transport=len(transport),bridges=sum(t['type']=='bridge' for t in transport),channels=len(chs),occupied=len(occupied),rectangle=rect,area=score[0],short_side=score[1],extra_poles=extra),ensure_ascii=False,indent=2))
print(len(paths),len(transport),len(chs),rect,score)
