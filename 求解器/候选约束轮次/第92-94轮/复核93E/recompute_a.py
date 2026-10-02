#!/usr/bin/env python3
"""93E 第一套独立编码。只读冻结快照；不导入推导席或项目模拟器。

产物仅写本脚本所在目录。局部运输采用绝对入格步数；边界供货、
接收日历是放宽接口，不表示一张达标的 70x70 布局。
"""
from collections import Counter
from fractions import Fraction as F
from hashlib import sha256
from itertools import product, combinations
from pathlib import Path
import json

OUT = Path(__file__).resolve().parent
SNAP = OUT.parent / '前提快照'


def frac(x):
    return str(F(x))


def solve(rows, n):
    a = [[F(x) for x in row] for row in rows]
    pivots = []
    r = 0
    for c in range(n):
        p = next((p for p in range(r, len(a)) if a[p][c]), None)
        if p is None:
            continue
        a[r], a[p] = a[p], a[r]
        d = a[r][c]
        a[r] = [x / d for x in a[r]]
        for k in range(len(a)):
            if k != r and a[k][c]:
                d = a[k][c]
                a[k] = [x-d*y for x, y in zip(a[k], a[r])]
        pivots.append(c)
        r += 1
    assert all(any(row[:-1]) or row[-1] == 0 for row in a)
    assert len(pivots) == n
    answer = [F(0)] * n
    for row, c in zip(a, pivots):
        answer[c] = row[-1]
    assert all(sum(F(row[i])*answer[i] for i in range(n)) == row[-1] for row in rows)
    return answer


def material():
    # (机器, 输入, 输出)，逐项从冻结配方独立录入。
    recipes = [
        ('粉碎机', {'源矿':1}, {'源石粉末':1}),
        ('粉碎机', {'蓝铁块':1}, {'蓝铁粉末':1}),
        ('粉碎机', {'荞花':1}, {'荞花粉末':2}),
        ('粉碎机', {'砂叶':1}, {'砂叶粉末':3}),
        ('精炼炉', {'蓝铁矿':1}, {'蓝铁块':1}),
        ('精炼炉', {'致密蓝铁粉末':1}, {'钢块':1}),
        ('精炼炉', {'蓝铁粉末':1}, {'蓝铁块':1}),
        ('研磨机', {'蓝铁粉末':2, '砂叶粉末':1}, {'致密蓝铁粉末':1}),
        ('研磨机', {'源石粉末':2, '砂叶粉末':1}, {'致密源石粉末':1}),
        ('研磨机', {'荞花粉末':2, '砂叶粉末':1}, {'细磨荞花粉末':1}),
        ('塑形机', {'钢块':2}, {'钢质瓶':1}),
        ('配件机', {'钢块':1}, {'钢制零件':1}),
        ('种植机', {'荞花种子':1}, {'荞花':1}),
        ('种植机', {'砂叶种子':1}, {'砂叶':1}),
        ('采种机', {'荞花':1}, {'荞花种子':2}),
        ('采种机', {'砂叶':1}, {'砂叶种子':2}),
        ('封装机', {'钢制零件':10, '致密源石粉末':15}, {'高容谷地电池':1}),
        ('灌装机', {'钢质瓶':10, '细磨荞花粉末':10}, {'精选荞愈胶囊':1}),
    ]
    items = sorted(set().union(*(set(i)|set(o) for _, i, o in recipes)))
    demand = {'高容谷地电池': F(3,5), '精选荞愈胶囊': F(11,20)}
    cases = []
    for return_rate in (F(0), F(1,7), F(2)):
        rows = []
        for x in items:
            if x in ('源矿', '蓝铁矿'):
                continue
            rows.append([o.get(x,0)-i.get(x,0) for _, i, o in recipes] + [demand.get(x,F(0))])
        rows.append([int(j == 6) for j in range(len(recipes))] + [return_rate])
        rates = solve(rows, len(recipes))
        assert all(x >= 0 for x in rates)
        totals = Counter()
        for (machine, _, _), q in zip(recipes, rates):
            totals[machine] += q
        minerals = {x: sum(q*(i.get(x,0)-o.get(x,0)) for (_,i,o),q in zip(recipes,rates))
                    for x in ('源矿','蓝铁矿')}
        assert totals['采种机'] == 16 and totals['研磨机'] == F(63,2)
        assert sum(minerals.values()) == 52
        cases.append({'return_rate':frac(return_rate), 'recipe_rates':[frac(x) for x in rates],
                      'machine_rates':{k:frac(v) for k,v in totals.items()},
                      'mineral_rates':{k:frac(v) for k,v in minerals.items()}})
    seed_min = next(n for n in range(100) if F(8*n,9) >= 16)
    grind_a_max = max(a for a in range(33) if 32-F(a,9) >= F(63,2))
    unit_minerals={}
    for finished in ('高容谷地电池','精选荞愈胶囊'):
        rows=[]
        for x in items:
            if x not in ('源矿','蓝铁矿'):
                rows.append([o.get(x,0)-i.get(x,0) for _,i,o in recipes]+[int(x==finished)])
        rows.append([int(j==6) for j in range(len(recipes))]+[0])
        amounts=solve(rows,len(recipes))
        unit_minerals[finished]={x:frac(sum(q*(i.get(x,0)-o.get(x,0))
                                    for (_,i,o),q in zip(recipes,amounts)))
                                 for x in ('源矿','蓝铁矿')}
    return {'cases':cases, 'limited_seed_min':seed_min, 'grind_a_max_at_32':grind_a_max,
            'unit_minerals':unit_minerals,
            'grind_switch_per_tick_at_32':frac(8*(32-F(63,2))),
            'mineral_port_capacity':2*(70//3)+6,
            'seed_integer_inequality':'9N-a >= 144',
            'grind_integer_inequality':'18N-2a >= 567'}


def transport_graph():
    # 状态为步末的入格后年龄；8 表示成熟（更老的状态折叠）。
    nodes = ['empty'] + list(range(9))
    edges = []
    for u in nodes:
        if u == 'empty':
            edges += [{'u':u,'v':'empty','out':0,'h':0}, {'u':u,'v':0,'out':0,'h':0}]
        elif u < 7:
            edges.append({'u':u,'v':u+1,'out':0,'h':0})
        else:
            edges += [{'u':u,'v':8,'out':0,'h':1},
                      {'u':u,'v':'empty','out':1,'h':0},
                      {'u':u,'v':0,'out':1,'h':0}]
    potential = {str(u): (0 if u == 'empty' else -min(u,7)) for u in nodes}
    for e in edges:
        assert 8*e['out']+e['h']-1 <= potential[str(e['v'])]-potential[str(e['u'])]
    cycles = []
    adjacency = {u:[e for e in edges if e['u']==u] for u in nodes}
    rank = {u:i for i,u in enumerate(nodes)}
    for start in nodes:
        def visit(u, visited, path):
            for e in adjacency[u]:
                v = e['v']
                if v == start:
                    walk = path+[e]
                    n, h, p = sum(e['out'] for e in walk), sum(e['h'] for e in walk), len(walk)
                    assert 8*n+h <= p
                    cycles.append({'states':[e['u'] for e in walk], 'P':p,'N':n,'H_max':h,
                                   'rate':frac(F(8*n,p))})
                elif rank[v] > rank[start] and v not in visited:
                    visit(v, visited|{v}, path+[e])
        visit(start, {start}, [])
    full = [c for c in cycles if c['rate']=='1']
    assert len(full)==1 and full[0]['P']==8 and full[0]['H_max']==0
    return {'edges':edges, 'potential':potential, 'simple_cycles':cycles}


def phase_checks():
    result = []
    for period in (8,16,24,32):
        valid = []
        for times in combinations(range(period), period//8):
            gaps = [b-a for a,b in zip(times,times[1:])]+[period+times[0]-times[-1]]
            if min(gaps) >= 8:
                assert set(gaps)=={8}
                valid.append(list(times))
        assert len(valid)==8
        result.append({'period':period,'full_schedules':valid})
    assignments = sum(len(set(t)) == 6 for t in product(range(8), repeat=6))
    assert assignments == 20160
    return {'periods':result, 'six_port_phase_assignments':assignments}


def segment_dp():
    # 仅记前七步是否送货，穷举下一步送/不送；任意八步最多 c 件。
    output = []
    for c in range(1,7):
        states = {1:1}  # 第 0 步发首件。
        found = {1:1}
        length = 1
        while len(found)<64:
            following = {}
            for mask, count in states.items():
                for send in (0,1):
                    if mask.bit_count()+send > c:
                        continue
                    new_mask = ((mask<<1)|send)&127
                    following[new_mask] = max(following.get(new_mask,-1), count+send)
            states = following
            length += 1
            attained = max(states.values())
            for q in range(1,min(64,attained)+1):
                found.setdefault(q,length)
        for q, length in sorted(found.items()):
            formula = 8*((q-1)//c)+(q-1)%c+1
            assert length == formula
            output.append({'c':c,'q':q,'min_steps':length})
    # 两种种子按整批输出；切周期或改变两路起点都不改变逐种计数。
    n_cases = 0
    for batches in range(1,11):
        for kinds in product(('荞花种子','砂叶种子'), repeat=batches):
            sequence = [kind for kind in kinds for _ in range(2)]
            for initial_port in (0,1):
                counts = Counter((kind,(j+initial_port)%2) for j,kind in enumerate(sequence))
                assert all(counts[(kind,0)]==counts[(kind,1)] for kind in set(sequence))
                n_cases += 1
    return {'rows':output,'equal_seed_sequence_cases':n_cases}


def belt_case(n, splitter_first, initially_full, calendar):
    belt = [-100 if initially_full else None for _ in range(n)]
    x = -100 if initially_full else None
    gate = -100 if initially_full else None
    seen, history, event_rows = {}, [], []

    def shift(t):
        for k in range(n-2,-1,-1):
            if belt[k] is not None and t-belt[k]>=8 and belt[k+1] is None:
                belt[k+1],belt[k] = t,None

    for t in range(200000):
        shift(t)
        sent = received = left_gate = 0
        if gate is not None and t-gate >= 8 and calendar[t%len(calendar)]:
            gate, left_gate = None,1
        for actor in (('X','B') if splitter_first else ('B','X')):
            if actor=='X' and x is not None and t-x>=8 and belt[0] is None:
                belt[0],x,received = t,None,1
            if actor=='B' and belt[-1] is not None and t-belt[-1]>=8 and gate is None:
                gate,belt[-1],sent = t,None,1
            shift(t)
        if x is None:
            x=t
        age = lambda u: None if u is None else min(8,t-u)
        state = [age(x)]+[age(u) for u in belt]+[age(gate)]
        row = {'step':t,'state_age':state,'belt_in':received,'belt_out':sent,
               'gate_out':left_gate,'belt_occupancy':sum(u is not None for u in belt)}
        history.append(row)
        state_key = (tuple(state),(t+1)%len(calendar))
        if state_key in seen:
            begin = seen[state_key]+1
            cycle = history[begin:]
            p = len(cycle)
            q = sum(z['belt_out'] for z in cycle)
            occ = sum(z['belt_occupancy'] for z in cycle)
            assert q == sum(z['belt_in'] for z in cycle)
            assert occ >= 8*n*q
            if splitter_first:
                assert occ <= n*p-q
            rate = F(8*q,p)
            if all(calendar):
                assert rate == (F(8*n,8*n+1) if splitter_first else F(1))
            return {'n':n,'splitter_first':splitter_first,'initially_full':initially_full,
                    'calendar':calendar,'cycle_start':begin,'period':p,'Q':q,'occupancy_sum':occ,
                    'rate':frac(rate),'history':history}
        seen[state_key]=t
    raise AssertionError('no repeat before local bound')


def grinding_calendar():
    rows=[]
    # 开工在第 0 步末；下一种主料尚未入格。穷举一条输入的两次到货。
    for manufacture_end in (8,):
        candidates=[]
        for first in range(1,33):
            for second in range(first+8,41):
                candidates.append(max(manufacture_end,second))
        earliest=min(candidates)
        assert earliest==9
        rows.append({'input_channels':1,'earliest_next_start':earliest})
    return rows


def branch_layers():
    rows=[]
    for live in range(1,25):
        for dead in range(1,25):
            # 所有结点均是元件；非运输末端 M 不参与元件层数递归。
            edges={('live',i): [('live',i+1)] if i+1<live else [('M',0)]
                   for i in range(live)}
            edges.update({('dead',i):[('dead',i+1)] if i+1<dead else []
                          for i in range(dead)})
            def layer(node):
                counted=[v for v in edges[node] if v in edges and edges[v]]
                assert len(counted)<=1
                return 1+layer(counted[0]) if counted else 1
            active_layer=layer(('live',0))
            dead_layer=layer(('dead',0))
            eligible=bool(edges[('dead',0)])
            x_layer=dead_layer+1 if eligible else None
            assert active_layer==live
            assert dead_layer==max(1,dead-1)
            assert x_layer==(dead if dead>=2 else None)
            rows.append({'m':live,'k':dead,'live_first_layer':active_layer,
                         'dead_first_layer':dead_layer,'X_via_dead_layer':x_layer})
    return rows


def old_s06_counterexample():
    # 合法起动：荞花经累计上限 1 的准入口进采种机，做第一批；
    # 两条取货通道的首格此前一直为空。0 为第一批结束之步。
    output_count=0
    born=[None,None]
    last_success=[-100,-99]
    rows=[]
    for t in range(-7,2):
        if t==0:
            output_count+=2
        send=None
        if output_count:
            eligible=[j for j in range(2) if born[j] is None]
            if eligible:
                send=min(eligible,key=lambda j:last_success[j])
                born[send]=t
                last_success[send]=t
                output_count-=1
        rows.append({'step':t,'output_count_after':output_count,
                     'first_belt_birth':born[:],'sent_port':send})
    in_window=[z for z in rows if -7<=z['step']<1]
    counts=[sum(z['sent_port']==j for z in in_window) for j in range(2)]
    assert counts==[1,0]
    return {'window_steps':[-7,1], 'both_ports_ready':True, 'initial_output_count':0,
            'counts':counts,'trace':rows,
            'scope':'局部规则反例，只否定旧 S06 的逐刻同时均分断言；不是七条候选的全厂反例'}


def auxiliary_cases():
    box=300
    incoming=-100
    outgoing=None
    trace=[]
    for t in range(100):
        entered=sent=failed=0
        if incoming is not None and t-incoming>=8:
            if box<300:
                incoming=None
                box+=1
                entered=1
            else:
                failed=1
        if outgoing is not None and t-outgoing>=8:
            outgoing=None
        if box and outgoing is None:
            box-=1
            outgoing=t
            sent=1
        if incoming is None:
            incoming=t
        trace.append({'step':t,'box_after':box,'enter':entered,'send':sent,'H':failed,
                      'incoming_age':min(8,t-incoming),
                      'outgoing_age':None if outgoing is None else min(8,t-outgoing)})
    assert [r['step'] for r in trace if r['H']]==[0]
    assert [r['step'] for r in trace if r['enter']]==list(range(1,100,8))
    assert [r['step'] for r in trace if r['send']]==list(range(0,100,8))
    bridges=[]
    for order in ((0,2,1),(2,0,1),(1,0,2),(1,2,0),(2,1,0)):
        born=[None,None,None]
        times=[]
        for t in range(600):
            for j in order:
                if born[j] is not None and t-born[j]>=8:
                    if j==2:
                        born[j]=None
                    elif born[j+1] is None:
                        born[j],born[j+1]=None,t
                        if j==1:
                            times.append(t)
            if born[0] is None:
                born[0]=t
        differences=[b-a for a,b in zip(times,times[1:])]
        expected=8 if order==(2,1,0) else 9
        assert set(differences)=={expected}
        bridges.append({'order':list(order),'A_to_B_times':times,'gap':expected,
                        'rate':frac(F(8,expected))})
    matching=[]
    for mask in range(512):
        graph=[[bool(mask&(1<<(3*i+j))) for j in range(3)] for i in range(3)]
        best=0
        for assignment in product(range(-1,3),repeat=3):
            chosen=[j for j in assignment if j>=0]
            if len(chosen)!=len(set(chosen)):
                continue
            if any(j>=0 and not graph[i][j] for i,j in enumerate(assignment)):
                continue
            best=max(best,len(chosen))
        matching.append(best)
    return {'full_box':trace,'bridge_orders':bridges,'three_by_three_matching':matching,
            'bridge_scope':'只检查报告写明的固定有效判定次序，不替现行条文解决重叠收货组'}


def main():
    snapshots={p.name:{'sha256':sha256(p.read_bytes()).hexdigest(),
                       'line_count':len(p.read_text().splitlines())} for p in sorted(SNAP.glob('*.txt'))}
    ns=list(range(1,17))+[23,31,47,64]
    calendars=[[1],[1,1,0,1,0],[1]*7+[0]*6]
    simulations=[belt_case(n,early,full,cal) for n in ns
                 for early in (True,False) for full in (False,True) for cal in calendars]
    assert len(simulations)==240
    result={'status':'PASS', 'snapshot_files':snapshots, 'material':material(),
            'single_cell':transport_graph(),'phases':phase_checks(),'segments':segment_dp(),
            'grinding':grinding_calendar(), 'branch_layers':branch_layers(),
            'old_s06':old_s06_counterexample(),
            'auxiliary':auxiliary_cases(),
            'belt_cases':simulations}
    (OUT/'results_a.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','belt_cases':len(simulations),
                      'segment_pairs':len(result['segments']['rows']),
                      'seed_sequences':result['segments']['equal_seed_sequence_cases'],
                      'simple_cycles':len(result['single_cell']['simple_cycles'])},ensure_ascii=False))


if __name__=='__main__':
    main()
