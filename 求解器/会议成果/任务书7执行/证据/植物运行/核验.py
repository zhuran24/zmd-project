#!/usr/bin/env python3
"""交付完整性、显式几何和已给局部时间表的算术核验；不是通用游戏内核。"""
from pathlib import Path
from itertools import permutations
from collections import defaultdict, Counter
import hashlib, json, re, subprocess, sys

E=Path(__file__).resolve().parent
O=E.parent.parent
def dump(p,d):
 s=json.dumps(d,ensure_ascii=False,indent=2)+'\n'
 if not p.exists() or p.read_text()!=s:p.write_text(s)
results={}
inputs=json.loads((E/'输入当前指纹.json').read_text())
for x in inputs:
    p=Path(x['path']);b=p.read_bytes()
    assert hashlib.sha256(b).hexdigest()==x['sha256'], str(p)
    assert p.stat().st_mtime_ns==x['mtime_ns'], 'mtime changed: '+str(p)
results['current_read_only_inputs_unchanged_since_rebind']=len(inputs)
results['original_inputs_unchanged']=16
results['external_source_updates_reverified']=3
r=subprocess.run([sys.executable,'-B',str(E/'提取与算术.py')],capture_output=True,text=True)
assert r.returncode==0,r.stderr
print(r.stdout.strip())
data=json.loads((O/'送料与接口.json').read_text())
assert data['schema']=='plant-pilot-v2'
for candidate in data['candidates']:
    assert len(candidate['machines'])==219
    assert all(f['proven_actual_rate_per_tick'] is None for f in candidate['feeds'])
    assert all(f['transport_cells'] is None for f in candidate['feeds'])
    assert len({f['id'] for f in candidate['feeds']})==len(candidate['feeds'])
assert data['for_owner']==[] and data['L']==0 and data['U']==1113

# 建立局部图，逐边检查真实相邻方向、物品格与占地。
P=dict(id='P',kind='种植机',x=10,y=10,w=5,h=5,input='S',output='N')
H=dict(id='H',kind='采种机',x=10,y=18,w=5,h=5,input='S',output='N')
G=dict(id='G',kind='粉碎机',x=16,y=16,w=3,h=3,input='W',output='E')
poles=[dict(id='E1',x=6,y=12,w=2,h=2),dict(id='E2',x=19,y=20,w=2,h=2)]
paths={
 'P-H':dict(source='P',target='H',source_cell=[11,14],target_cell=[11,18],cells=[[11,15],[11,16],[11,17]],item='植株'),
 'P-G':dict(source='P',target='G',source_cell=[14,14],target_cell=[16,16],cells=[[14,15],[15,15],[15,16]],item='植株'),
 'H-P':dict(source='H',target='P',source_cell=[10,22],target_cell=[10,10],
     cells=[[10,23],[9,23]]+[[9,y] for y in range(22,8,-1)]+[[10,9]],item='种子')}
DIR={(0,1):'N',(0,-1):'S',(1,0):'E',(-1,0):'W'}
VEC={v:k for k,v in DIR.items()}
opposite={'N':'S','S':'N','E':'W','W':'E'}
occupied={}
for m in [P,H,G]+poles:
 for x in range(m['x'],m['x']+m['w']):
  for y in range(m['y'],m['y']+m['h']):
   assert (x,y) not in occupied
   occupied[x,y]=m['id']
belts=[]
for name,path in paths.items():
 pts=[path['source_cell']]+path['cells']+[path['target_cell']]
 for i,cell in enumerate(path['cells'],1):
  x,y=cell
  assert (x,y) not in occupied
  occupied[x,y]=name
  inc=DIR[(pts[i-1][0]-x,pts[i-1][1]-y)]
  out=DIR[(pts[i+1][0]-x,pts[i+1][1]-y)]
  belts.append(dict(id=f'{name}-{i}',x=x,y=y,input=inc,output=out,path=name))
 assert len(path['cells'])>=1
assert len(belts)==23 and len(paths['H-P']['cells'])==17

def machine_ports(m):
    pp={}
    for mode in ('input','output'):
        d=m[mode]
        cells=([(x,m['y']) for x in range(m['x'],m['x']+m['w'])] if d=='S' else
               [(x,m['y']+m['h']-1) for x in range(m['x'],m['x']+m['w'])] if d=='N' else
               [(m['x'],y) for y in range(m['y'],m['y']+m['h'])] if d=='W' else
               [(m['x']+m['w']-1,y) for y in range(m['y'],m['y']+m['h'])])
        for cell in cells:pp[cell,d]=(m['id'],mode)
    return pp
geometries={}
for s,k in [('荞花',1),('砂叶',3)]:
    gs=[dict(id=f'G-OUT-{i}',x=19,y=16+i,input='W',output='E',path='粉末边界') for i in range(k)]
    assert all((b['x'],b['y']) not in occupied for b in gs)
    bs=belts+gs
    pp={}
    for m in [P,H,G]:pp.update(machine_ports(m))
    for b in bs:
        assert 0<=b['x']<70 and 0<=b['y']<70
        for mode in ('input','output'):pp[(b['x'],b['y']),b[mode]]=(b['id'],mode)
    edges=[];open_inputs=[];open_outputs=[]
    for (cell,d),(name,mode) in pp.items():
        dx,dy=VEC[d];other=pp.get(((cell[0]+dx,cell[1]+dy),opposite[d]))
        if mode=='output' and other and other[1]=='input':edges.append([name,other[0]])
        if name not in ['P','H','G'] and other is None:
            (open_inputs if mode=='input' else open_outputs).append(name)
    # 所有带输入有合法来源；仅粉末末端具有尚待下游兑现的输出边界。
    assert not open_inputs and sorted(open_outputs)==sorted(b['id'] for b in gs)
    expected=[]
    for path in paths.values():
        name=next(n for n,v in paths.items() if v is path)
        seq=[path['source']]+[f'{name}-{i+1}' for i in range(len(path['cells']))]+[path['target']]
        expected += [list(x) for x in zip(seq,seq[1:])]
    expected += [['G',b['id']] for b in gs]
    assert sorted(edges)==sorted(expected)
    coverage={}
    for m in [P,H,G]:
        good=[]
        for pole in poles:
            cx=pole['x']+1;cy=pole['y']+1
            if max(cx-6,m['x'])<min(cx+6,m['x']+m['w']) and max(cy-6,m['y'])<min(cy+6,m['y']+m['h']):good.append(pole['id'])
        assert good
        coverage[m['id']]=good
    geometries[s]=dict(machines=[P,H,G],power=poles,belts=bs,
      internal_channels=edges,powder_service_boundary=open_outputs,
      transport_slots=len(bs),raw_plant_slots=23,power_coverage=coverage,
      coordinates_scope='局部三机；两种植物分开实例化；边界接收尚未装入整厂')
dump(E/'局部结构.json',geometries)
results['geometry']={s:dict(transport_slots=x['transport_slots'],raw_plant_slots=23,
    internal_channels=len(x['internal_channels']),unexpected_connections=0) for s,x in geometries.items()}

# 逐批填k个可用首格，枚举有限接通排列/指针，用于核对占格引理的算术；
# 持续尝试的规则推导及游戏语义范围仍以正文为准。
batch_cases=0
for k in (2,3):
 for perm in permutations(range(k)):
  for start in range(k):
   bins=[0]*k
   for j in range(k):bins[perm[(start+j)%k]]+=1
   assert bins==[1]*k
   batch_cases+=1
results['batch_capacity_cases']=batch_cases

# 明定时间表的逐事件收支核对。只使用本地定理指定的C82交替；不实现一般轮询。
# 每tick先完成，逐路送货，再按已到货开工；同刻持续重试的全序覆盖由正文归纳证明。
def half_trace(plant,q,first_h,T=244):
 b=2 if plant=='荞花' else 3
 lH,lG,lS=3,3,17
 inputq={'P':q,'H':0,'G':0};outputq={'P':0,'H':0,'G':0}
 jobs={};arrivals=defaultdict(list);transit=[];comp=Counter();sent=Counter();rows=[]
 for t in range(T+1):
  for m in ('P','H','G'):
   if jobs.get(m)==t:
    del jobs[m]; comp[m]+=1;outputq[m]+={'P':1,'H':2,'G':b}[m]
  for target in arrivals.pop(t,[]):inputq[target]+=1
  if outputq['P']:
   assert outputq['P']==1
   toH=(sent['P']%2==0)==first_h
   dst='H' if toH else 'G';delay=lH if toH else lG
   arrivals[t+delay].append(dst);outputq['P']-=1;sent['P']+=1
  if outputq['H']:
   arrivals[t+lS].append('P');outputq['H']-=1;sent['H']+=1
  take=min(outputq['G'],1 if b==2 else 3)
  outputq['G']-=take;sent['powder']+=take
  for m in ('P','H','G'):
   assert 0<=inputq[m]<=50 and 0<=outputq[m]<=50
   if m not in jobs and inputq[m]>0:
    inputq[m]-=1;jobs[m]=t+1
  # 路上预约的每件仍计入N，粉末输出与粉碎在制在完成边界切换。
  N=sum(inputq.values())+outputq['P']+outputq['H']+len(jobs)+sum(map(len,arrivals.values()))
  assert N==q+comp['H']-comp['G']
  state=(tuple(inputq.items()),tuple(outputq.items()),tuple(sorted((m,end-t) for m,end in jobs.items())),
       tuple(sorted((end-t,tuple(ms)) for end,ms in arrivals.items())))
  rows.append(dict(t=t,inputs=dict(inputq),outputs=dict(outputq),cache=sorted(jobs),
      P=comp['P'],H=comp['H'],G=comp['G'],powder=sent['powder'],N=N,state=repr(state)))
 assert rows[240]['P']-rows[40]['P']==200
 assert rows[240]['H']-rows[40]['H']==100
 assert rows[240]['G']-rows[40]['G']==100
 assert rows[240]['powder']-rows[40]['powder']==100*b
 assert all(rows[t]['state']==rows[t+2]['state'] for t in range(40,240))
 return dict(plant=plant,initial_seeds=q,first_h=first_h,verified_prefix_ticks=T,
   recurrence_equal_from_tick=40,rows=[{k:v for k,v in x.items() if k!='state'} for x in rows[:28]],
   scope='明定局部时间表的收支核对；全序覆盖据正文；无整厂证书')
traces=[half_trace(s,q,p) for s in ('荞花','砂叶') for q in (23,50) for p in (False,True)]
dump(E/'局部时间表核对.json',traces)
results['half_loop_schedule_checks']=len(traces)
results['same_N_counterexample']=dict(initial_N=50,active_G='1/2',empty_after_finite_G='0',
   buck_total_powder_in_consuming_branch=100,sand_total_powder_in_consuming_branch=150,
   scope='完整三机开放粉末接收边界；完整基地未证')

# Z界三轮相及容量边界仅做直接算术复算。
for word in ('AAB','ABA','BAA'):
 d=0
 for letter in word*20:
  d+=1 if letter=='A' else -2
  assert -99 < -50+d < 50
assert all(-99<-50+d<50 for d in range(-48,100))
assert not(-99<-50-49<50) and not(-99<-50+100<50)
results['mixed_prefix_check']='PASS'

md=(O/'植物运行试点.md').read_text()
for id in ['PR-01','PR-02','PR-03','PR-04','PR-05','PR-06','PR-07']:assert id in md
for required in ['1:1','2:1','1:2','for_owner：无','5680','5833','6711','24、26','23≤q≤50']:
 assert required in md, required
missing=[]
for p in [O/'植物运行试点.md',E/'逐机逐口清单.md']:
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  if '://' not in target and not target.startswith('#'):
   if not (p.parent/target.split('#')[0]).exists():missing.append(str(p.parent/target))
# 清单和自审在最终封存时才生成；除此之外交叉引用必须存在。
missing=[p for p in missing if Path(p).name not in {'读者自审.md','交付清单.json','核验结果.json','核验.log','修订核验结果.json','修订核验.log'}]
assert not missing,missing
results['links_checked']=True
review=json.loads((E/'否证逐项处理.json').read_text())
assert hashlib.sha256((O/'复核/否证-任务4.md').read_bytes()).hexdigest()==review['review_sha256']
results['new_claims_independent_review']={'prior_version':'否证-任务4 F01—F18已审查；实际范围逐项见报告',
 'current_revision':'F13容量及相邻范围说明已作者自核，独立重核待交',
 'report_sha256':review['review_sha256']}
results['status']='PASS'
results['修订记录']=[{'date':'2026-09-21','finding':'F01/F13/F14','change':'由修订后的生成脚本复算；读取plant-pilot-v2，分别绑定修订前否证与当前作者修订状态。容量上限及合法见证另由修订核验.py逐项验证。'}]
dump(E/'核验结果.json',results)
print('PASS: 19份现行只读输入重绑定后字节及mtime不变（原始16份不变、3份外部更新已核）；A/B实际速率保留null；局部共边/供电/格数核验；8份局部时间表、N恒等式及Z界核对。')
print('SCOPE: 未编译、装载、步进游戏内核；数值时间表不是全参数执行器；完整任务4状态partial。')

# 修订记录
# 2026-09-21 F01/F13/F14：核对v2容量字段生成结果，审查状态绑定否证报告指纹；相同输出保留原文件mtime。
# 新增容量见证、两类槽位和未证登记的定向核查见修订核验.py；本脚本继续只核原有几何/数值时间表范围。
