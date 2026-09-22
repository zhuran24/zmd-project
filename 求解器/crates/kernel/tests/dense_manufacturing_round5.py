"""密集结点的真实原料起动：矿→蓝铁块/粉末的1:1制造闭环；只改变D三个模板顺序。"""
import copy,json,subprocess,collections
from pathlib import Path
import round5_scenarios as s
from generate_examples import unit
from runtime_example import quantity as q,decision
from migrate_round5 import save,migrate
ROOT=s.ROOT;BASE=s.OUT;BIN=s.BIN;CFG=s.CONFIG
units=[unit('refine_d','精炼炉',9,2),unit('refine_e','精炼炉',11,8,'r180'),unit('crusher_loop','粉碎机',14,3,'r270'),unit('mine_source','仓库取货口',9,0),unit('startup_gate','物品准入口',10,1),unit('split_d','分流器',11,5),unit('split_e','分流器',12,6,'r180'),unit('merge','汇流器',12,5,'r180'),unit('power','供电桩',8,7),unit('observer_box','协议储存箱',22,7),unit('observer_power','供电桩',20,7)]
# 单格运输路径及两端相邻格，交叉处按独立轴合成桥。
paths=[
 [(12,4),(13,4)],
 [(17,3),(18,3),(18,2),(18,1)]+[(x,1)for x in range(17,10,-1)],
 [(17,5),(18,5)]+[(18,y)for y in range(6,12)]+[(x,11)for x in range(17,11,-1)],
 [(11,6),(11,7),(12,7),(13,7),(13,6),(13,5)],
 [(10,5),(9,5),(8,5),(7,5)]+[(7,y)for y in range(6,13)]+[(x,12)for x in range(8,20)]+[(19,y)for y in range(11,-1,-1)]+[(x,0)for x in range(18,12,-1)]+[(13,1),(13,2),(13,3)],
 [(12,7)]
]
ends=[((12,5),(14,4)),((16,3),(11,2)),((16,5),(12,10)),((11,5),(14,5)),((11,5),(14,3)),((12,8),(12,6))]
sides={(0,-1):'south',(1,0):'east',(0,1):'north',(-1,0):'west'};roles={}
for path,(start,end) in zip(paths,ends):
 for a,b,c in zip([start]+path,path,path[1:]+[end]):roles.setdefault(b,[]).append((sides[(a[0]-b[0],a[1]-b[1])],sides[(c[0]-b[0],c[1]-b[1])]))
for (x,y),pairs in roles.items():
 uid=f't{x}_{y}'
 if len(pairs)==2:
  u=unit(uid,'桥接器',x,y)
  for incoming,_ in pairs:u['bridge_axes']['vertical'if incoming in ('south','north')else'horizontal']['input_side']=incoming
 else:
  incoming,outgoing=pairs[0];seq=['south','east','north','west'];i=seq.index(incoming);delta=(seq.index(outgoing)-i)%4
  u=unit(uid,'传送带',x,y,['r0','r90','r180','r270'][i],{1:1,2:0,3:2}[delta])
 units.append(u)
# 先建桥，再逐端接入；避免两非运输邻居均已建成时的先接并列。
units.sort(key=lambda u:u['kind']!='桥接器')
data=s.b.generate('密集制造闭环基础',units)
ore=next(r['slot']for r in data['initial_state']['warehouse']['slots']if r['item']=='蓝铁矿')
data['settings']['warehouse_assignments'].append(dict(port='mine_source:north:1',slot=ore))
for row in data['settings']['switches']:row['enabled']=True
for row in data['settings']['gates']:row.update(item='蓝铁矿',total_limit=q(4),window_limit=None)
s.b.set_axis(data,'warehouse.external_supply',{'kind':'sufficient'})
data['initial_state']['reachability']=decision({'kind':'conditional_state','document':str(BASE/'第五轮样例说明-kernel.md'),'scope':'采用与既有空起点样例相同的条件空种子；此后全部循环物料实际由仓库4件蓝铁矿起动，未预置非仓库物品；未证明全部建造/调试历史'},'第五轮S4；有限自动累计限额只用于起动，不靠玩家精确定时')
channels={r['id']:r for r in data['layout']['physical_channels']};kinds={u['id']:u['kind']for u in data['layout']['units']};transport={'传送带','桥接器','分流器','汇流器','物品准入口'}
def distance(cid,seen=frozenset()):
 if cid in seen:raise ValueError('运输路径有环')
 c=channels[cid];target=c['target_port'].split(':');uid,side=target[:2]
 if kinds[uid]not in transport:return 0
 axis='vertical'if side in ('north','south')else'horizontal'
 outgoing=[d for d,x in channels.items()if x['source_port'].split(':')[0]==uid and (kinds[uid]!='桥接器'or ('vertical'if x['source_port'].split(':')[1]in ('north','south')else'horizontal')==axis)]
 if not outgoing:return 10000
 return 1+min(distance(d,seen|{cid})for d in outgoing)
order=data['parameters']['fixed']['judgment.order']['value']['template_order']
transport_moves=sorted([r for r in order if r['operation']=='move'and kinds[channels[r['target']]['source_port'].split(':')[0]]in transport],key=lambda r:(distance(r['target']),r['target']))
manufacture=[r for r in order if r['operation']=='manufacture'];transfer=[r for r in order if r['operation']=='transfer'];other=[r for r in order if r['operation']=='move'and r not in transport_moves]
base_order=transport_moves+manufacture+other+transfer
a=next(r for r in base_order if r['operation']=='move'and r['target'].startswith('PC|split_d:east:'))
b=next(r for r in base_order if r['operation']=='move'and r['target'].startswith('PC|split_d:north:'))
c=next(r for r in base_order if r['operation']=='move'and r['target'].startswith('PC|split_d:west:'))
positions=sorted(base_order.index(r)for r in (a,b,c))
permutations=[(a,b,c),(b,a,c),(a,c,b),(b,c,a),(c,a,b),(c,b,a)]
reports=[]
for variant,permutation in enumerate(permutations):
 d=copy.deepcopy(data);selected=copy.deepcopy(base_order)
 for index,template in zip(positions,permutation):selected[index]=copy.deepcopy(template)
 s.b.set_axis(d,'judgment.order',{**d['parameters']['fixed']['judgment.order']['value'],'template_order':selected})
 name=f'密集制造闭环序{variant}核验';d['scenario']['name']=name;d=migrate(d)
 source=BASE/(name+'.json');save(source,d)
 normalized=BASE/(name+'-派生临时-kernel.json')
 r=subprocess.run([str(BIN),'seed',str(source),'--config',str(CFG),'--out',str(normalized)],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(normalized.read_text())
 source.write_bytes(normalized.read_bytes());normalized.unlink()
 out=BASE/(name+'-周期证书-kernel.json')
 r=subprocess.run([str(BIN),'cycle',str(source),'--config',str(CFG),'--max-ticks','1000','--out',str(out)],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(out.read_text()[:2000])
 result=json.loads(out.read_text());cycle=result['cycle'];counts=collections.Counter();completions=collections.Counter()
 if cycle:
  start=int(cycle['start_time']['value']['value']);end=int(cycle['end_time']['value']['value'])
  for tick in result['run_record']['trace']['ticks']:
   if not start<int(tick['time']['value']['value'])<=end:continue
   for e in tick['events']:
    if e['operation']=='move'and e['outcome']=='success':counts[e['target']]+=1
    if e['operation']=='manufacture_complete':completions[e['target']]+=1
 report=dict(input=str(source),local_order=[r['target']for r in permutation],status=result['status'],period=cycle and cycle['period'],cycle_movements=dict(counts),manufacturing_completions=dict(completions))
 reports.append(report);print(json.dumps(dict(variant=variant,status=result['status'],period=cycle and cycle['period'],a=counts[a['target']],d_total=sum(n for c,n in counts.items()if c.startswith('PC|split_d:')),other=sum(n for c,n in counts.items()if c.startswith('PC|split_e:')and '|merge:'in c)),ensure_ascii=False),flush=True)
 record=BASE/(name+'-运行记录-v3-kernel.json');record.write_text(json.dumps(result['run_record'],ensure_ascii=False,separators=(',',':'))+'\n');out.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
(ROOT/'crates/kernel/evidence/round5/dense-manufacturing-results.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
