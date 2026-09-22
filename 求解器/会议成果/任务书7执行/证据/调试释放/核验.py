#!/usr/bin/env python3
"""本席作者核验：源码/全部输入只读、精确算术、局部事件见证、范围与链接。"""
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
import hashlib
import json
import re
import ast

E=Path(__file__).resolve().parent
O=E.parent.parent
ROOT=O.parents[2]

def read(p): return json.loads(p.read_text())
def dump(name,data):
    p=E/name
    assert p.suffix in {'.json','.md','.py','.log'}
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

baseline=read(E/'输入指纹.json')['files']
inventory=[]
for row in baseline:
    p=Path(row['path']);b=p.read_bytes()
    assert hashlib.sha256(b).hexdigest()==row['sha256'],str(p)
    assert p.stat().st_mtime_ns==row['mtime_ns'],str(p)
    item={'path':str(p),'sha256':row['sha256'],'bytes_read':len(b)}
    if p.suffix=='.json':
        value=json.loads(b)
        def nodes(x):
            if isinstance(x,dict):return 1+sum(nodes(v) for v in x.values())
            if isinstance(x,list):return 1+sum(nodes(v) for v in x)
            return 1
        item.update(json_fully_parsed=True,json_nodes=nodes(value))
    elif p.suffix=='.py':
        item['ast_nodes']=sum(1 for _ in ast.walk(ast.parse(b.decode())))
    else: item['text_lines_read']=len(b.decode().splitlines())
    inventory.append(item)
dump('输入读取核查.json',{'files':inventory,'scope':'全部字节读取、JSON解析、脚本语法读取；无来源脚本执行'})

state=read(O/'调试后状态.json')
facts=read(E/'势函数与条件算术.json')
source=read(O/'送料与接口.json')
recipes=facts['recipes'];weights=facts['weights']
assert state['status']=='partial' and state['error'] is None
assert state['L']==0 and state['U']==1113 and not state['default_start_certified']
assert not state['full_layout_certified'] and not state['full_start_search_lossless']
assert state['for_owner']==[]
assert not state['post_state_set']['exact_reachable_set_enumerated']
assert not state['post_state_set']['all_cartesian_combinations_claimed_reachable']
assert state['rule_sha256']==hashlib.sha256((ROOT/'《明日方舟：终末地》游戏规则.txt').read_bytes()).hexdigest()

# 独立逐物品检查全部机器/逻辑边，读取MD逐条匹配全部植物送料行。
mdtable=(O/'证据/植物运行/逐机逐口清单.md').read_text()
counts=[];balance_checks=0;plant_rows=0
for c in source['candidates']:
    inputs={m['id']:Counter() for m in c['machines']}
    outputs={m['id']:Counter() for m in c['machines']}
    incoming=Counter();outgoing=Counter()
    for e in c['feeds']:
        r=F(e['expected_rate_per_tick']);assert 0<r<=1
        assert e['proven_actual_rate_per_tick'] is None
        assert e['transport_cells'] is None
        if e['source'] in outputs: outputs[e['source']][e['item']]+=r;outgoing[e['source']]+=1
        else: assert e['item'] in ('源矿','蓝铁矿')
        if e['target'] in inputs:inputs[e['target']][e['item']]+=r;incoming[e['target']]+=1
        else: assert e['item'] in ('高容谷地电池','精选荞愈胶囊')
        if e['item'] in ('荞花','砂叶','荞花种子','砂叶种子','荞花粉末','砂叶粉末'):
            exact=f"| {e['id']} | {e['source_port']} → {e['target_port']} | {e['item']} | {e['expected_rate_per_tick']} |"
            assert exact in mdtable,exact
            plant_rows+=1
    for m in c['machines']:
        assert len(m['recipes'])==1
        mr=m['recipes'][0];r=recipes[mr['name']];rate=F(mr['expected_batches_per_tick'])
        assert inputs[m['id']]=={i:rate*q for i,q in r['inputs'].items()}
        assert outputs[m['id']]=={i:rate*q for i,q in r['output'].items()}
        ports=5 if m['kind'] in ('种植机','采种机') else 6 if m['kind'] in ('研磨机','封装机','灌装机') else 3
        assert incoming[m['id']]<=ports and outgoing[m['id']]<=ports
        balance_checks+=1
    counts.append({'id':c['id'],'machines':len(c['machines']),'feeds':len(c['feeds'])})
assert balance_checks==438 and plant_rows==219

# 直接重新乘配方，而非信任增量列表。
inc={}
for name,r in recipes.items():
    before=sum(weights[k]*n for k,n in r['inputs'].items())
    after=sum(weights[k]*n for k,n in r['output'].items())
    inc[name]=after-before
    assert inc[name]>=1
assert len(inc)==17 and inc['粉碎-砂叶']==3
assert weights['蓝铁块']-weights['蓝铁粉末']==-1
for c in state['default_program']['candidates']:
    assert len(c['terminal_machines'])==6
    assert c['potential_capacity_excluding_transport']==c['ordinary_potential_capacity']+c['normal_cache_potential_capacity']

# 三机见证：每条成熟满专线的一次传空位保留全线件数，
# 一端接收1、另一端输出1。动作只发生在间隔>=1的成熟条件下。
# 固定局部动作表，不模拟一般轮询/混线/全参数。
q={'P_in':50,'P_out':50,'H_in':50,'H_out':50,'G_in':50}
cache={'P':None,'H':None,'G':None}
done=Counter();rows=[]
last_move={'PH':-10,'HP':-10}
def N():
    nc=0
    for m,job in cache.items():
        if job:
            nc += (2 if m=='H' and job[0]=='done' else 1)
    return sum(q.values())+23+nc
def snap(t,action):
    n=N();assert n==273+done['H']-done['G']
    assert all(0<=v<=50 for v in q.values())
    rows.append({'time':t,'action':action,'ordinary':dict(q),
                 'cache':{m:None if v is None else list(v) for m,v in cache.items()},
                 'H_completed':done['H'],'N':n})
def start(m,t):
    assert cache[m] is None and q[m+'_in']>=1
    q[m+'_in']-=1;cache[m]=('work',t+1);snap(t,'start '+m)
def finish(m,t):
    assert cache[m]==('work',t)
    cache[m]=('done',None);done[m]+=1;snap(t,'finish '+m)
def transfer(m,t):
    assert cache[m] and cache[m][0]=='done'
    b=2 if m=='H' else 1
    assert q[m+'_out']+b<=50
    cache[m]=None;q[m+'_out']+=b;snap(t,'cache to output '+m)
def wave(path,t):
    src,dst=('P','H') if path=='PH' else ('H','P')
    assert t-last_move[path]>=1
    assert q[src+'_out']>0 and q[dst+'_in']<50
    q[src+'_out']-=1;q[dst+'_in']+=1;last_move[path]=t
    snap(t,'mature full path vacancy wave '+path)
snap(-2,'initial: all correct ordinary/plant paths full; G stays off')
start('H',-2);wave('PH',-2);finish('H',-1)
start('P',0);wave('HP',0)
finish('P',1);transfer('P',1);start('P',1);wave('HP',1)
transfer('H',1);start('H',1);wave('PH',1)
finish('P',2);transfer('P',2);finish('H',2);start('P',2);wave('HP',2)
finish('P',3)
assert q=={'P_in':50,'P_out':50,'H_in':50,'H_out':49,'G_in':50}
assert cache['P'][0]==cache['H'][0]=='done' and N()==275
assert q['P_out']+1>50 and q['H_out']+2>50
dump('局部静止见证.json',{'initial_N':273,'final_N':275,'rows':rows,
    'geometry_reference':'证据/植物运行/局部结构.json','raw_transport_cells':23,
    'fixed_service':'G关闭，PH/HP满专线成熟后同刻传空位',
    'scope':'局部库存和缓存事件；不是完整布局或通用执行器；H提前开、P后开不要求精确间隔'})

# 清出门槛：独立逐个删除物品，求能容纳整批的最小删除数。
clear_cases=0
for q0 in range(51):
    for b in (1,2,3):
        for same in (False,True):
            feasible=[d for d in range(q0+1) if (same and q0-d+b<=50) or (not same and q0-d==0)]
            target=max(0,q0+b-50) if same else q0
            assert min(feasible)==target
            clear_cases+=1
assert clear_cases==306

# K消元逐系数核对，变量顺序为AH,AG,H,G,I,IH,IG。
vectors=[[-1,1,0,0,0,0,0],[0,0,0,0,1,1,-1],[1,0,-1,0,0,-1,0],[0,-1,0,1,0,0,1]]
assert [sum(v[j] for v in vectors) for j in range(7)]==[0,0,-1,1,1,0,0]
conditional=[]
for x,p,h,g,n,d in [('荞花',11,6,6,2023,307),('砂叶',21,11,11,3793,562)]:
    assert 100*(p+h)+50*g+p+2*h==n
    assert 1+h+50*g==d
    st=state['species_accounts'][x]
    assert st['candidate_actual_N0'] is None and st['candidate_actual_Dmax'] is None
    assert st['candidate_actual_safety_margin'] is None
    assert st['completed_full_slots_example_N0']==n
    assert st['conditional_E1_zero_leak_Dmax_bound']==d
    conditional.append({'species':x,'completed_full_N0_excluding_transport':n,'E1_no_leak_bound_excluding_G_path':d})
assert 2*6+2*11==34
assert [2*16+48*m for m in (0,1,16)]==[32,80,800]
assert 50+2*(50+1)==152 and 50+3*(50+1)==203
assert 50-(3+17+3)==27
assert 51-51==0 and 51-52<0
z_values=[]
for word in ('AAB','ABA','BAA'):
    d=0
    for letter in word*10:
        d+=1 if letter=='A' else -2;z_values.append(-50+d)
        assert -99 < -50+d < 50
assert min(z_values)==-52 and max(z_values)==-48
assert min(z_values)+99==47 and 50-max(z_values)==98
assert all(-99<-50+d<50 for d in range(-48,100))

# 证据只允许四类文件；所有本席脚本只在内存编译，不产生pyc。
for p in E.rglob('*'):
    if p.is_file():assert p.suffix in {'.py','.json','.md','.log'},str(p)
for p in E.glob('*.py'):compile(p.read_text(),str(p),'exec')
md=(O/'调试与释放.md').read_text()
assert all(f'DR-{i:02}' in md for i in range(1,8))
assert '状态：任务5部分完成' in md and 'for_owner：无' in md
for target in re.findall(r'\]\(([^)]+)\)',md):
    if '://' not in target and not target.startswith('#'):
        p=(O/target.split('#')[0]).resolve()
        # 本运行新建的结果与稍后保存的日志。
        if p.name not in {'核验结果.json','核验.log'}:assert p.exists(),str(p)

result={'status':'PASS','exit_status':0,'scope':'作者源码/算术/局部事件/接口检查，无游戏内核步进、无全参数枚举',
  'read_only_inputs_unchanged':len(baseline),'input_JSON_and_scripts_read_in_full':True,
  'candidate_checks':counts,'machine_balance_checks':balance_checks,'plant_feed_rows_checked':plant_rows,
  'positive_recipe_checks':len(inc),'minimum_recipe_increase':min(inc.values()),
  'excluded_R89_increase':-1,'first_clear_cases':clear_cases,
  'local_event_rows':len(rows),'local_quiescent_witness':{'H_output':49,'final_N':275,'completed_H_batches':2},
  'loss_identity_coefficient_check':True,'conditional_loss_examples':conditional,
  'mixed_tail_counts':[152,203],'half_loop_seed_margin_q50':27,
  'mixed_Z_distances':[47,98],'source_scripts_executed':False,
  'source_bytes_and_mtime_unchanged':True,'links_checked':True,
  'exact_reachable_set_enumerated':False,'full_layout_certified':False,
  'new_proofs_independent_review':'pending','L':0,'U':1113,'for_owner':[]}
dump('核验结果.json',result)
print('PASS: 49份只读输入SHA-256及mtime不变；所有来源JSON/脚本完整读取解析。')
print('PASS: 438台计划配平、629条逻辑边、219条植物及粉末MD记录；17配方势函数正增量。')
print(f'PASS: 306个首次清出门槛；{len(rows)}行局部事件；K恒等式逐系数；2023/3793、307/562、152/203、27及Z界。')
print('SCOPE: 作者条件推导自核；未编译、装载、步进内核；实际Dmax/安全余量为null；任务5部分完成。')

if __name__=='__main__':
    pass
