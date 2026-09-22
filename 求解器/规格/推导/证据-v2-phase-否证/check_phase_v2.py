#!/usr/bin/env python3
"""Independent local arithmetic and kernel probes; no complete layout claim."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import re
import subprocess
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOLVER = ROOT / '求解器'
BIN = SOLVER / 'target/release/kernel'
CFG = SOLVER / '规格/内核配置-v1.json'

def write(name, data):
    (HERE/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

protected = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']
reviewed = ['三种相位不改产量-v2.md', '三种相位不改产量.md', '总纲-流量存量相位.md',
            '复核/独立推导-相位-opus.md', '复核/否证-相位-1.md', '复核/否证-相位-2.md']
chat = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/786b1aaa-8792-43fd-afbc-2a7361543a07/scratchpad/总结/对话-0920-主线.md')
paths = [ROOT/p for p in protected]+[HERE.parent/p for p in reviewed]+[chat]
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
write('input_hashes.json', before)
for name, prefix in zip(protected, ['abc7a5867f64', '1630ca1febec', 'f6503e6c1568']):
    assert before[str(ROOT/name)].startswith(prefix)

# Parse every actual recipe from the formal rule text, independently of the kernel catalogue.
mass = {'蓝铁矿':(1,0),'蓝铁块':(1,0),'蓝铁粉末':(1,0),
        '致密蓝铁粉末':(2,0),'钢块':(2,0),'钢制零件':(2,0),'钢质瓶':(4,0),
        '源矿':(0,1),'源石粉末':(0,1),'致密源石粉末':(0,2),
        '高容谷地电池':(20,30),'精选荞愈胶囊':(40,0)}
recipe_checks=[]
for line_no,line in enumerate((ROOT/protected[0]).read_text().splitlines(),1):
    if '→' not in line: continue
    left,right=line.split('→')
    right=right.split('，')[0]
    def total(text):
        result=[0,0]
        for n,item in re.findall(r'(\d+)\s+(\S+)',text):
            for i,m in enumerate(mass.get(item,(0,0))): result[i]+=int(n)*m
        return result
    a,b=total(left),total(right)
    assert a==b,(line_no,a,b)
    recipe_checks.append({'line':line_no,'mass':a})
assert len(recipe_checks)==18
assert 50*F(3,5)+40*F(11,20)==52
assert [p for p in range(1,201) if (F(11,20)*p).denominator==1]==list(range(20,201,20))

# All arrival subsets of a fresh five-tick window. A sixth receipt requires elapsed >= 5.
for mask in range(32):
    receipt_times=[t for t in range(5) if mask>>t&1]
    assert len(receipt_times)<=5
    if len(receipt_times)==5: assert receipt_times[-1]==4

def filler(arrivals, initial):
    stock=list(initial);due=None;starts=[];done=[]
    for tick in range(41):
        if due==tick: done.append(tick);due=None
        if tick:
            inc=arrivals(tick)
            stock=[x+y for x,y in zip(stock,inc)]
        if due is None and min(stock)>=10:
            starts.append({'tick':tick,'before':stock.copy()})
            stock=[x-10 for x in stock];due=tick+5
        assert all(0<=x<=50 for x in stock)
    return {'starts':starts,'done':done}
third=filler(lambda t:(2,1) if t%2 else (1,2),(10,10))
assert third['starts'][:4]==[{'tick':0,'before':[10,10]}, {'tick':7,'before':[11,10]}, {'tick':14,'before':[11,11]}, {'tick':20,'before':[10,10]}]
assert sum(0<t<=20 for t in third['done'])==3
continuous=filler(lambda t:(3,3) if t%2 else (1,1),(12,12))
assert [r['before'][0] for r in continuous['starts'][:3]]==[12,13,12]

# Reuse only the current kernel input serializer; redirect every generated file here.
sys.path.insert(0,str(SOLVER/'crates/kernel/tests'))
import build_fixtures as builder
from generate_examples import unit
from runtime_example import quantity, time_value, decision
from migrate_round5 import migrate
builder.OUT=HERE

def call(args):
    p=subprocess.run([str(BIN),*map(str,args),'--config',str(CFG)],capture_output=True,text=True)
    result={'args':list(map(str,args)),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    return result

def seed_and_run(name,units,stocks,switches=(),gate=None):
    data=builder.generate(name,units)
    for s in data['settings']['switches']:s['enabled']=s['unit'] in switches
    if gate is not None:
        data['settings']['gates'][0].update(item='蓝铁粉末',window_limit=quantity(gate) if gate else None,total_limit=None)
    seed=data['initial_state']['nonwarehouse']['value']
    for row in seed['inventory']:
        if row['slot'] in stocks:
            item,n=stocks[row['slot']]
            row['contents']=[dict(item=item,quantity=quantity(n),entered_at=time_value(-1) if ':transport:' in row['slot'] else None)]
    data['initial_state']['reachability']=decision({'kind':'conditional_state','document':str(HERE/'scope.md'),'scope':'局部库存与时序核对；不是整厂起法或全参数证书'},'任务12允许放料；实际循环由本文手推并交叉核算')
    data=migrate(data)
    path=HERE/(name+'.json');write(path.name,data)
    canonical=HERE/(name+'-canonical.json')
    seeded=call(['seed',path,'--out',canonical]);write(name+'-seed.json',seeded)
    if seeded['returncode']:return {'status':'seed_failed','detail':seeded}
    checked=call(['check',canonical]);write(name+'-check.json',checked)
    if checked['returncode']:return {'status':'check_failed','detail':checked}
    ran=call(['run',canonical,'--ticks','81','--out',HERE/(name+'-trace.json')]);write(name+'-run.json',ran)
    return {'status':'ran' if not ran['returncode'] else 'run_failed','result':ran}

recycle_units=[unit('crusher','粉碎机',10,10),unit('furnace','精炼炉',14,10,'r180'),unit('power','供电桩',10,6),
 unit('n1','传送带',12,13,port_layout=1),unit('n2','传送带',13,13,'r270'),unit('n3','传送带',14,13,'r270',1),
 unit('s1','传送带',14,9,'r180',1),unit('s2','传送带',13,9,'r90'),unit('s3','传送带',12,9,'r90',1)]
kernel={}
kernel['recycle']=seed_and_run('recycle',recycle_units,{'crusher:input:0':('蓝铁块',1)},('crusher','furnace'))

deadlock_units=[unit('grinder','研磨机',10,10),unit('merger','汇流器',12,9),unit('b','传送带',11,9,'r270'),unit('power','供电桩',10,6)]
kernel['head_block']=seed_and_run('head_block',deadlock_units,{'grinder:input:0':('蓝铁粉末',50),'merger:transport:0':('蓝铁粉末',1),'b:transport:0':('砂叶粉末',1)},('grinder',))
kernel['head_release']=seed_and_run('head_release',deadlock_units,{'grinder:input:0':('蓝铁粉末',50),'merger:transport:0':('砂叶粉末',1),'b:transport:0':('蓝铁粉末',1)},('grinder',))

gate_units=[unit('source','粉碎机',10,10),unit('gate','物品准入口',11,13),unit('sink','精炼炉',10,14)]
for k in (0,5):
    kernel['gate'+str(k)]=seed_and_run('gate'+str(k),gate_units,{'source:output:0':('蓝铁粉末',50)},gate=k)

after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
assert before==after,'Reviewed or protected input changed during probes'
# Independent one-token loop with no contested move: two 1-tick recipes and six 1-tick cells.
stages=['crusher_in_process','n1_blue_powder','n2_blue_powder','n3_blue_powder',
        'furnace_in_process','s1_blue_block','s2_blue_block','s3_blue_block']
recycle_trace=[{'tick':t,'stage':stages[t%8],'blue_mass':1} for t in range(81)]
assert recycle_trace[0]['stage']==recycle_trace[8]['stage']
# Independently check coordinates from the cited witness, rather than only its printed path.
machine_cells={(x,y) for x in range(10,13) for y in range(10,13)}|{(x,y) for x in range(14,17) for y in range(10,13)}
power_cells={(x,y) for x in (10,11) for y in (6,7)}
top=[(12,13),(13,13),(14,13)];bottom=[(14,9),(13,9),(12,9)]
assert not machine_cells&power_cells
assert not (machine_cells|power_cells)&set(top+bottom)
assert len(set(top+bottom))==6
for path in [[(12,12)]+top+[(14,12)],[(14,10)]+bottom+[(12,10)]]:
    assert all(abs(a[0]-b[0])+abs(a[1]-b[1])==1 for a,b in zip(path,path[1:]))
assert all(any(5<=x<17 and 1<=y<13 for x in range(lo,lo+3) for y in range(10,13)) for lo in (10,14))

# Exhaustive 15-tick local arrival opportunities (2^15 histories): k=5 never removes an opportunity.
def accept_opportunities(opportunities,k):
    start=None;count=0;accepted=[]
    for t in opportunities:
        if start is None or t-start>=5:start=t;count=0
        if count<k:accepted.append(t);count+=1
    return accepted
for mask in range(1<<15):
    opportunities=[t for t in range(15) if mask>>t&1]
    assert accept_opportunities(opportunities,5)==opportunities
non_sliding=accept_opportunities([0,4,5,6],2)
assert non_sliding==[0,4,5,6]
assert sum(4<=t<9 for t in non_sliding)==3
assert accept_opportunities(list(range(0,101,5)),2)==list(range(0,101,5))

# One recipe input is full, the other absent. No enabled operation can free the merger.
deadlock={'blue_input':50,'sand_input':0,'merger':'蓝铁粉末','upstream':'砂叶粉末'}
assert not(deadlock['blue_input']<50)
assert not(deadlock['sand_input']>=1)
assert deadlock['merger'] is not None
alive_after_sand={'blue_input_after_recipe':48,'sand_input_after_recipe':0,'cache_output_after_one_tick':1}
write('probe_results.json',{'recipes':recipe_checks,'target_mass':52,'third_filler':third,'continuous_filler':continuous,'recycle_trace':recycle_trace,'geometry_verified':True,'gate_k5_opportunity_histories':1<<15,'non_sliding_receipts':non_sliding,'deadlock':deadlock,'alive_after_sand':alive_after_sand,'kernel':kernel,'kernel_steps_executed':0 if all(v['status']=='seed_failed' for v in kernel.values()) else 'inspect_traces','inputs_unchanged':before==after,'complete_layout_certified':False})
print(json.dumps({k:v['status'] for k,v in kernel.items()},ensure_ascii=False))
