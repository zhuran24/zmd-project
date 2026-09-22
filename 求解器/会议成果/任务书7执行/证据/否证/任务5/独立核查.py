#!/usr/bin/env python3
"""只读被审材料，独立核配方、逐格局部见证、代数和版本。"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import ast
import hashlib
import json
import re

E = Path(__file__).resolve().parent
O = E.parents[2]
ROOT = O.parents[2]
A = O / '证据/调试释放'
def read(p):
    return json.loads(p.read_text())
def write(name, value):
    p = E / name
    assert p.parent == E and p.suffix in {'.json', '.md', '.log', '.py'}
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# 逐一比对全部被审来源与交付清单，完整读取数据，脚本仅解析。
versions = []
for name in ('输入指纹.json', '输入读取核查.json', '交付清单.json'):
    for row in read(A/name)['files']:
        p = Path(row['path'])
        b = p.read_bytes()
        ok = sha(p) == row['sha256']
        assert ok, str(p)
        if 'mtime_ns' in row:
            assert p.stat().st_mtime_ns == row['mtime_ns'], str(p)
        versions.append({'manifest': name, 'path': str(p), 'sha256': sha(p), 'match': ok})
for row in read(E/'审查输入指纹.json')['files']:
    p = Path(row['path'])
    assert p.exists() and sha(p) == row['sha256'], str(p)
    if p.suffix == '.json':
        json.loads(p.read_text())
    if p.suffix == '.py':
        ast.parse(p.read_text())
write('版本逐项核对.json', versions)

# 从正式规则的配方行解析，独立核对手填配方及权重。
rules = (ROOT/'《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
facts = read(A/'势函数与条件算术.json')
state = read(O/'调试后状态.json')
interface = read(O/'送料与接口.json')
weights = facts['weights']
checks = []
parsed = {}
def terms(s):
    result = {}
    for q, name in re.findall(r'(\d+)\s+([^＋]+?)(?=\s*＋|$)', s.strip()):
        result[name.strip()] = int(q)
    return result
for name, rec in facts['recipes'].items():
    line = rec['rule_lines'][0]
    m = re.fullmatch(r'(.+?)\s*→\s*(.+?)，(\d+) tick', rules[line-1])
    assert m, (line, rules[line-1])
    ins, outs, ticks = terms(m[1]), terms(m[2]), int(m[3])
    assert ins == rec['inputs'] and outs == rec['output'] and ticks == rec['ticks']
    delta = sum(weights[k]*v for k,v in outs.items()) - sum(weights[k]*v for k,v in ins.items())
    assert delta >= 1
    parsed[name] = (ins, outs, ticks)
    checks.append({'recipe': name, 'rule_line': line, 'increase': delta})
assert len(checks) == 17
assert weights['蓝铁块'] - weights['蓝铁粉末'] == -1
assert {x['recipe']:x['increase'] for x in facts['recipe_increases']} == {x['recipe']:x['increase'] for x in checks}

candidate_checks = []
for c in interface['candidates']:
    inc = {m['id']:Counter() for m in c['machines']}
    out = {m['id']:Counter() for m in c['machines']}
    ordinary = cache = 0
    terminals = []
    for edge in c['feeds']:
        rate = F(edge['expected_rate_per_tick'])
        assert 0 < rate <= 1
        assert edge['proven_actual_rate_per_tick'] is None and edge['transport_cells'] is None
        if edge['source'] in out:
            out[edge['source']][edge['item']] += rate
        else:
            assert edge['item'] in ('源矿','蓝铁矿')
        if edge['target'] in inc:
            inc[edge['target']][edge['item']] += rate
        else:
            assert edge['item'] in ('高容谷地电池','精选荞愈胶囊')
    for m in c['machines']:
        assert len(m['recipes']) == 1
        r = m['recipes'][0]
        ins, outs, ticks = parsed[r['name']]
        rate = F(r['expected_batches_per_tick'])
        assert inc[m['id']] == {k:rate*v for k,v in ins.items()}
        assert out[m['id']] == {k:rate*v for k,v in outs.items()}
        ordinary += 50 * (sum(weights[k] for k in ins) + sum(weights[k] for k in outs))
        cache += max(sum(weights[k]*v for k,v in ins.items()),sum(weights[k]*v for k,v in outs.items()))
        if ticks == 5:
            terminals.append(m['id'])
    fact = next(x for x in facts['candidates'] if x['id']==c['id'])
    assert ordinary == fact['ordinary_potential_capacity'] == 166150
    assert cache == fact['normal_cache_potential_capacity'] == 2571
    assert ordinary+cache == 168721
    assert terminals == fact['terminal_machines'] and len(terminals)==6
    candidate_checks.append({'id':c['id'],'machines':len(c['machines']),'feeds':len(c['feeds']),
                             'ordinary_capacity':ordinary,'cache_capacity':cache})

# 重新计算局部占格、共边接口与供电，确保逐格见证沿用的几何无额外路径。
geometry_checks=[]
direction={'N':(0,1),'S':(0,-1),'E':(1,0),'W':(-1,0)}
opposite={'N':'S','S':'N','E':'W','W':'E'}
for species,g in read(O/'证据/植物运行/局部结构.json').items():
    occupied={}; ins={}; outs={}
    for u in g['machines']+g['power']+g['belts']:
        w,h=u.get('w',1),u.get('h',1)
        for x in range(u['x'],u['x']+w):
            for y in range(u['y'],u['y']+h):
                assert (x,y) not in occupied and 0<=x<70 and 0<=y<70
                occupied[x,y]=u['id']
        if 'input' not in u: continue
        for key,target in [('input',ins),('output',outs)]:
            side=u[key]
            cells = ([(x,u['y']+h-1 if side=='N' else u['y']) for x in range(u['x'],u['x']+w)]
                     if side in ('N','S') else
                     [(u['x']+w-1 if side=='E' else u['x'],y) for y in range(u['y'],u['y']+h)])
            for x,y in cells: target[x,y,side]=u['id']
    channels=[]
    for (x,y,side),src in outs.items():
        dx,dy=direction[side]
        dst=ins.get((x+dx,y+dy,opposite[side]))
        if dst is not None: channels.append((src,dst))
    assert sorted(channels)==sorted(tuple(x) for x in g['internal_channels'])
    coverage={}
    for m in g['machines']:
        covered=[]
        for p in g['power']:
            cx,cy=p['x']+1,p['y']+1
            if max(m['x'],cx-6)<min(m['x']+m['w'],cx+6) and max(m['y'],cy-6)<min(m['y']+m['h'],cy+6):
                covered.append(p['id'])
        assert covered
        coverage[m['id']]=covered
    assert coverage==g['power_coverage']
    geometry_checks.append({'species':species,'channels':len(channels),'plant_belts':23,
                            'transport_slots':len(g['belts']),'coverage':coverage})

# 独立展开局部见证的每个格，使用同一个固定事件优先序。
# 不执行作者的核验.py，也不把聚合空位传播当成零滞留穿越。
def local_trace(lead):
    q = {'P_in':50,'P_out':50,'H_in':50,'H_out':50,'G_in':50}
    cache = {'P':None,'H':None,'G':None}
    on = {'P':False,'H':True,'G':False}
    paths = {'PH':[-lead-10]*3, 'HP':[-lead-10]*17, 'PG':[-lead-10]*3}
    endpoints = {'PH':('P_out','H_in'),'HP':('H_out','P_in'),'PG':('P_out','G_in')}
    events = []
    done = Counter()
    def total():
        cv = sum((2 if m=='H' and job and job[0]=='done' else 1) for m,job in cache.items() if job)
        return sum(q.values()) + sum(x is not None for p in paths.values() for x in p) + cv
    def perform(kind, m, t, i=None):
        if kind == 'finish':
            if cache[m] != ('work',t): return False
            cache[m] = ('done',None); done[m] += 1
        elif kind == 'transfer':
            n = 2 if m=='H' else 1
            if not cache[m] or cache[m][0]!='done' or q[m+'_out']+n>50: return False
            q[m+'_out'] += n; cache[m] = None
        elif kind == 'start':
            if not on[m] or cache[m] is not None or not q[m+'_in']: return False
            q[m+'_in'] -= 1; cache[m]=('work',t+1)
        else:
            p=paths[m]; src,dst=endpoints[m]
            if i == len(p):
                if p[-1] is None or t-p[-1]<1 or q[dst]==50: return False
                p[-1]=None; q[dst]+=1
            elif i == 0:
                if p[0] is not None or not q[src]: return False
                q[src]-=1; p[0]=t
            else:
                if p[i] is not None or p[i-1] is None or t-p[i-1]<1: return False
                p[i]=t; p[i-1]=None
        assert total() == 273+done['H']-done['G']
        assert all(0<=v<=50 for v in q.values())
        events.append({'time':t,'event':[kind,m,i],'ordinary':dict(q),
                       'cache':dict(cache),'N':total()})
        return True
    priority = [('finish','P',None),('transfer','P',None),('finish','H',None),('start','P',None)]
    priority += [('move','HP',i) for i in range(17,-1,-1)]
    priority += [('transfer','H',None),('start','H',None)]
    priority += [('move','PH',i) for i in range(3,-1,-1)]
    priority += [('move','PG',i) for i in range(3,-1,-1)]
    for t in range(-lead,11):
        if t == 0: on['P']=True
        while True:
            for kind,m,i in priority:
                if perform(kind,m,t,i): break
            else: break
    assert q == {'P_in':50,'P_out':50,'H_in':50,'H_out':49,'G_in':50}
    assert cache == {'P':('done',None),'H':('done',None),'G':None}
    assert total()==275 and done['H']==2 and done['P']==3
    assert all(x is not None and 10-x>=1 for p in paths.values() for x in p)
    return {'opening_lead':lead,'fixed_priority':priority,'events':events,'ordinary_final':q,
            'cache_final':cache,'N_final':total(),'completed_batches':dict(done)}
local = [local_trace(n) for n in (2,3,11)]
write('逐格局部见证.json', {'scope':'一个固定合法次序的局部见证；三个开启间隔；不是全参数执行器',
                           'paths':{'PH':3,'HP':17,'PG':3},'traces':local})

# 核49见证作者每行守恒和缓存状态，不把原脚本执行作为证据。
author = read(A/'局部静止见证.json')
for r in author['rows']:
    nc = sum((2 if m=='H' and job[0]=='done' else 1) for m,job in r['cache'].items() if job)
    assert r['N'] == sum(r['ordinary'].values())+23+nc == 273+r['H_completed']
assert author['rows'][-1]['ordinary'] == local[0]['ordinary_final']

# N/K等式逐事件核：增量顺序 N,BH,BG,AH,AG,I,IH,IG。
event_vectors = {
    'assign_H':(0,1,0,1,0,0,0,0), 'assign_G':(0,0,1,0,1,0,0,0),
    'finish_H':(1,-1,0,0,0,0,0,0), 'finish_G':(-1,0,-1,0,0,0,0,0),
    'leak_H':(-1,-1,0,0,0,1,1,0), 'leak_G':(-1,0,-1,0,0,1,0,1),
    'leak_other':(-1,0,0,0,0,1,0,0), 'planting_or_moving':(0,0,0,0,0,0,0,0),
}
for v in event_vectors.values():
    n,bh,bg,ah,ag,i,ih,ig = v
    assert n+bh-bg == ah-ag-(i+ih-ig)
    assert -n == ag-ah+(i+ih-ig)+bh-bg
clear_count=0
for q in range(51):
    for b in (1,2,3):
        for same in (True,False):
            smallest = next(d for d in range(q+1) if (q-d+b<=50 if same else q-d==0))
            assert smallest == (max(0,q+b-50) if same else q)
            clear_count+=1
numeric=[]
for x,p,h,g in [('荞花',11,6,6),('砂叶',21,11,11)]:
    row=state['species_accounts'][x]
    n=100*(p+h)+50*g+p+2*h
    loss=1+h+50*g
    assert n == row['completed_full_slots_example_N0']
    assert loss == row['conditional_E1_zero_leak_Dmax_bound']
    numeric.append({'species':x,'N0_without_transport':n,'loss_bound_without_G_paths':loss})
assert 50+2*51==152 and 50+3*51==203
assert 9800*281==2753800
assert 50-(3+17+3)==27
safe_D=[d for d in range(-200,201) if -99 < -50+d < 50]
assert safe_D == list(range(-48,100))
prefix={}
for word in ('AAB','ABA','BAA'):
    d=0; vals=[0]
    for c in word:
        d+=1 if c=='A' else -2; vals.append(d)
    prefix[word]=[min(vals),max(vals)]
assert prefix=={'AAB':[0,2],'ABA':[-1,1],'BAA':[-2,0]}

result={'status':'PASS','exit_status':0,'version_checks':len(versions),
        'source_recipes_parsed':checks,'candidates':candidate_checks,
        'local_geometry':geometry_checks,
        'first_clear_cases':clear_count,'event_identity_cases':len(event_vectors),
        'local_opening_delays':[2,3,11],'local_final_N':275,'local_final_H_output':49,
        'local_trace_successful_events':[len(x['events']) for x in local],
        'conditional_arithmetic':numeric,'mixed_tail':[152,203],
        'half_loop_R':23,'half_loop_q50_margin':27,'mixed_prefix_ranges':prefix,
        'source_scripts_executed':False,'kernel_used':False,
        'scope':'版本、规则配方、计划配平、有限算术、局部固定次序逐格见证；不证明完整默认释放达标'}
write('独立核查结果.json',result)
print(json.dumps(result,ensure_ascii=False))
