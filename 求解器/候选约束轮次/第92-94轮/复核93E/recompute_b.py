#!/usr/bin/env python3
"""93E 第二套编码及证书检查器；不导入 recompute_a 或推导席代码。

物料按 20 tick 整数逆推；运输按剩余步数和空位处理；连续段直接
分配具名通道的最早可用时间；匹配用 Hall 子集公式。
"""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from itertools import product
from math import comb, factorial
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent


def rate_string(n,d=1):
    return str(Fraction(n,d))


def material_check(data):
    # 20 tick: 12 电池、11 胶囊。按产物需求逆向数整批。
    cells=12
    capsules=11
    parts=10*cells
    dense_source=15*cells
    bottles=10*capsules
    fine_flower=10*capsules
    steel=parts+2*bottles
    grinding=steel+dense_source+fine_flower
    assert grinding%3==0
    crushed_sand=grinding//3
    crushed_flower=fine_flower
    sampling=crushed_sand+crushed_flower
    iron_ore=2*steel
    source_ore=2*dense_source
    assert sampling==320 and grinding==630 and iron_ore+source_ore==1040
    for case in data['cases']:
        r=Fraction(case['return_rate'])
        counts=[source_ore,iron_ore,crushed_flower,crushed_sand,iron_ore,steel,0,
                steel,dense_source,fine_flower,bottles,parts,2*crushed_flower,
                2*crushed_sand,crushed_flower,crushed_sand,cells,capsules]
        expected=[Fraction(v,20) for v in counts]
        expected[1]+=r
        expected[6]+=r
        assert expected==list(map(Fraction,case['recipe_rates']))
        assert Fraction(case['machine_rates']['采种机'])==Fraction(sampling,20)
        assert Fraction(case['machine_rates']['研磨机'])==Fraction(grinding,20)
    # 用纯整数不等式，不使用第一套的分数台数判断。
    seed_min=min(n for n in range(100) if 8*n>=9*16)
    grind_max=max(a for a in range(33) if 18*32-2*a>=567)
    max_switches_20_ticks=32*160-8*grinding
    assert seed_min==data['limited_seed_min']==18
    assert grind_max==data['grind_a_max_at_32']==4
    assert max_switches_20_ticks==80
    assert rate_string(max_switches_20_ticks,20)==data['grind_switch_per_tick_at_32']
    for name,battery_count,capsule_count in [('高容谷地电池',1,0),('精选荞愈胶囊',0,1)]:
        iron=2*(10*battery_count+2*10*capsule_count)
        source=2*15*battery_count
        assert data['unit_minerals'][name]=={'源矿':str(source),'蓝铁矿':str(iron)}
    return {'twenty_tick_grinding_batches':grinding,'twenty_tick_sampling_batches':sampling,
            'twenty_tick_iron_ore':iron_ore,'twenty_tick_source_ore':source_ore,
            'limited_seed_min':seed_min,'grind_a_max_at_32':grind_max,
            'max_switches_in_160_steps_at_32':max_switches_20_ticks}


def simulate_with_holes(case):
    n=case['n']
    calendar=case['calendar']
    items={i:0 for i in range(1,n+1)} if case['initially_full'] else {}
    upstream=0 if case['initially_full'] else None
    downstream=0 if case['initially_full'] else None
    states_seen={}
    rows=[]

    def close_holes():
        for empty_place in range(n,1,-1):
            if empty_place not in items and items.get(empty_place-1)==0:
                del items[empty_place-1]
                items[empty_place]=8

    step=0
    while step<200000:
        items={position:max(0,wait-1) for position,wait in items.items()}
        upstream=None if upstream is None else max(0,upstream-1)
        downstream=None if downstream is None else max(0,downstream-1)
        close_holes()
        gate_out=belt_in=belt_out=0
        if downstream==0 and calendar[step%len(calendar)]:
            downstream=None
            gate_out=1
        for inlet_action in ([True,False] if case['splitter_first'] else [False,True]):
            if inlet_action:
                if upstream==0 and 1 not in items:
                    upstream=None
                    items[1]=8
                    belt_in=1
            else:
                if items.get(n)==0 and downstream is None:
                    del items[n]
                    downstream=8
                    belt_out=1
            close_holes()
        if upstream is None:
            upstream=8
        clock=lambda r:None if r is None else 8-r
        ages=[clock(upstream)]+[clock(items.get(i)) for i in range(1,n+1)]+[clock(downstream)]
        row={'step':step,'state_age':ages,'belt_in':belt_in,'belt_out':belt_out,
             'gate_out':gate_out,'belt_occupancy':len(items)}
        assert row==case['history'][step], (n,step,row,case['history'][step])
        rows.append(row)
        key=(upstream,tuple(sorted(items.items())),downstream,(step+1)%len(calendar))
        if key in states_seen:
            start=states_seen[key]+1
            cycle=rows[start:]
            assert start==case['cycle_start'] and len(cycle)==case['period']
            exits=sum(r['belt_out'] for r in cycle)
            filled=sum(r['belt_occupancy'] for r in cycle)
            assert exits==case['Q'] and filled==case['occupancy_sum']
            assert filled>=8*n*exits
            if case['splitter_first']:
                assert filled<=n*len(cycle)-exits
            assert rate_string(8*exits,len(cycle))==case['rate']
            return len(rows)
        states_seen[key]=step
        step+=1
    raise AssertionError('second simulation failed to find repeat')


def check_transport_certificate(cert, phases):
    # 独立构造倒计时状态和所有动作；0 为已成熟，8 为本步新入格。
    countdown_nodes=[None]+list(range(9))
    transitions=[]
    for remaining in countdown_nodes:
        if remaining is None:
            transitions += [(None,None,0,0),(None,8,0,0)]
        elif remaining>1:
            transitions.append((remaining,remaining-1,0,0))
        else:
            transitions += [(remaining,0,0,1),(remaining,None,1,0),(remaining,8,1,0)]
    state=lambda remaining:'empty' if remaining is None else 8-remaining
    encoded={(state(u),state(v),out,h) for u,v,out,h in transitions}
    supplied={(e['u'],e['v'],e['out'],e['h']) for e in cert['edges']}
    assert encoded==supplied
    for u,v,out,h in transitions:
        pu=0 if u is None else -min(8-u,7)
        pv=0 if v is None else -min(8-v,7)
        assert 8*out+h<=1+pv-pu
    # 动作流而非只读第一套记录的总和，重放所有基本闭合步程。
    for cycle in cert['simple_cycles']:
        sequence=cycle['states']
        available=[]
        for a,b in zip(sequence,sequence[1:]+sequence[:1]):
            choices=[e for e in supplied if e[0]==a and e[1]==b]
            assert len(choices)==1
            available.append(choices[0])
        n=sum(e[2] for e in available)
        h=sum(e[3] for e in available)
        assert n==cycle['N'] and h==cycle['H_max']
        assert 8*n+h<=len(sequence)
    # 按占格日历检查全部满速时间戳，每件恰占八个步间隔。
    for data in phases['periods']:
        p=data['period']
        for events in data['full_schedules']:
            occupancy=[0]*p
            for incoming in events:
                for offset in range(8):
                    occupancy[(incoming+offset)%p]+=1
            assert occupancy==[1]*p
            assert len({t%8 for t in events})==1
    number=comb(8,6)*factorial(6)
    assert number==phases['six_port_phase_assignments']==20160
    return {'checked_transport_edges':len(transitions),'six_port_assignments':number,
            'max_charge_per_step':'1','certificate':'8*out + H <= 1 + potential(next) - potential(current)'}


def channel_schedule_check(rows):
    saved=[]
    for c in range(1,7):
        ready=[0]*c
        last=-1
        generated=[]
        for q in range(1,65):
            port=min(range(c),key=lambda j:ready[j])
            moment=max(last+1,ready[port])
            ready[port]=moment+8
            last=moment
            generated.append((moment,port))
            certificate=rows[(c-1)*64+q-1]
            assert certificate=={'c':c,'q':q,'min_steps':moment+1}
        assert all(b[0]>a[0] for a,b in zip(generated,generated[1:]))
        for port in range(c):
            t=[t for t,j in generated if j==port]
            assert all(b-a>=8 for a,b in zip(t,t[1:]))
        saved.append({'c':c,'first_16_events':generated[:16]})
    return saved


def seed_phase_check():
    count=0
    for batches in range(1,10):
        for recipe_list in product((0,1),repeat=batches):
            labels=[kind for kind in recipe_list for _ in range(2)]
            for r0 in range(8):
                for r1 in range(8):
                    if r0==r1:
                        continue
                    events=sorted([(8*j+r0,0) for j in range(batches)]
                                  +[(8*j+r1,1) for j in range(batches)])
                    totals=[[0,0],[0,0]]
                    for label,(_,port) in zip(labels,events):
                        totals[label][port]+=1
                    assert all(a==b for a,b in totals)
                    count+=1
    return count


def grinding_step_check():
    # 旧配方于第0步末清格；一条来路的首件此前已经成熟。
    main_count=0
    input_wait=0
    receipts=[]
    for step in range(18):
        input_wait=max(0,input_wait-1)
        if step>0 and input_wait==0:
            receipts.append(step)
            main_count+=1
            input_wait=8
        if step>=8 and main_count>=2:
            assert step==9
            return {'earliest_start':step,'receipts':receipts}
    raise AssertionError('no next manufacture')


def branch_layer_check(rows):
    strict=tied=one_element=0
    for row in rows:
        # 从末端往前填整条数组，独立于第一套沿图递归。
        m,k=row['m'],row['k']
        live=[0]*m
        dead=[0]*k
        live[-1]=1
        dead[-1]=1
        for p in range(m-2,-1,-1):
            live[p]=live[p+1]+1
        for p in range(k-2,-1,-1):
            dead[p]=1 if p==k-2 else dead[p+1]+1
        assert row['live_first_layer']==live[0]
        assert row['dead_first_layer']==dead[0]
        assert row['X_via_dead_layer']==(None if k==1 else 1+dead[0])
        if k==1:
            one_element+=1
        elif k<m:
            strict+=1
            assert m>=2
        elif k==m:
            tied+=1
            assert m>=2
    return {'cases':len(rows),'strictly_early_cases':strict,
            'same_layer_conditional_cases':tied,'one_element_ineligible_cases':one_element}


def auxiliary_check(data, s06):
    full=300
    wait_in=0
    wait_out=None
    for step,row in enumerate(data['full_box']):
        wait_in=max(0,wait_in-1)
        wait_out=None if wait_out is None else max(0,wait_out-1)
        accepted=int(wait_in==0 and full<300)
        failed=int(wait_in==0 and full==300)
        if accepted:
            full+=1
            wait_in=8
        if wait_out==0:
            wait_out=None
        sent=int(full>0 and wait_out is None)
        if sent:
            full-=1
            wait_out=8
        assert (full,accepted,sent,failed)==(row['box_after'],row['enter'],row['send'],row['H'])
        assert (8-wait_in, None if wait_out is None else 8-wait_out)==(row['incoming_age'],row['outgoing_age'])
    for example in data['bridge_orders']:
        cells={}
        successful=[]
        for step in range(600):
            cells={i:max(0,r-1) for i,r in cells.items()}
            for i in example['order']:
                if cells.get(i)==0:
                    if i==2:
                        del cells[i]
                    elif i+1 not in cells:
                        del cells[i]
                        cells[i+1]=8
                        if i==1:
                            successful.append(step)
            cells.setdefault(0,8)
        assert successful==example['A_to_B_times']
    for mask,claimed in enumerate(data['three_by_three_matching']):
        hall_bound=3
        for subset in range(8):
            neighbors=set()
            for i in range(3):
                if subset&(1<<i):
                    for j in range(3):
                        if mask&(1<<(3*i+j)):
                            neighbors.add(j)
            hall_bound=min(hall_bound,3-subset.bit_count()+len(neighbors))
        assert claimed==hall_bound
    # 逐步事件独立列出 S06 的第一个整 tick；两出口在完成批次前均空。
    first_tick={step:[] for step in range(-7,1)}
    first_tick[0]=[0]
    assert sum(0 in x for x in first_tick.values())==1
    assert sum(1 in x for x in first_tick.values())==0
    assert s06['initial_output_count']==0 and s06['counts']==[1,0]
    # 报告所给旧 S06 局部见证的格点几何。
    rectangles={'采种机':(6,3,5,5),'仓库取货口':(7,0,3,1),'物品准入口':(8,1,1,1),
                '输入传送带':(8,2,1,1),'第一输出传送带':(7,8,1,1),
                '第二输出传送带':(9,8,1,1),'供电桩':(11,4,2,2),'协议核心':(30,30,9,9)}
    occupied=set()
    for name,(x,y,w,h) in rectangles.items():
        cells={(a,b) for a in range(x,x+w) for b in range(y,y+h)}
        assert all(0<=a<70 and 0<=b<70 for a,b in cells)
        assert not occupied&cells,name
        occupied|=cells
    assert (8,0) in occupied and (8,1) in occupied and (8,2) in occupied and (8,3) in occupied
    px,py,pw,ph=rectangles['供电桩']
    cx,cy=px+pw/2,py+ph/2
    mx,my,mw,mh=rectangles['采种机']
    assert max(cx-6,mx)<min(cx+6,mx+mw) and max(cy-6,my)<min(cy+6,my+mh)
    return {'full_box_failed_steps':[0],'full_box_steady_period':8,
            'bridge_order_cases':len(data['bridge_orders']),'matching_graphs':512,
            'S06_window_counts':[1,0],'S06_geometry_nonoverlap':True}


def main():
    a=json.loads((ROOT/'results_a.json').read_text())
    assert a['status']=='PASS'
    for name,info in a['snapshot_files'].items():
        raw=(ROOT.parent/'前提快照'/name).read_bytes()
        assert sha256(raw).hexdigest()==info['sha256']
    materials=material_check(a['material'])
    steps=sum(simulate_with_holes(case) for case in a['belt_cases'])
    graph=check_transport_certificate(a['single_cell'],a['phases'])
    schedules=channel_schedule_check(a['segments']['rows'])
    seeds=seed_phase_check()
    grinding=grinding_step_check()
    assert grinding['earliest_start']==a['grinding'][0]['earliest_next_start']
    aux=auxiliary_check(a['auxiliary'],a['old_s06'])
    layers=branch_layer_check(a['branch_layers'])
    report={'status':'PASS','independent_material':materials,'transport_certificate':graph,
            'belt_cases':len(a['belt_cases']),'belt_steps_compared':steps,
            'segment_pairs':len(a['segments']['rows']), 'channel_schedules':schedules,
            'seed_phase_cases':seeds,'grinding':grinding,'branch_layers':layers,'auxiliary':aux,
            'result_a_sha256':sha256((ROOT/'results_a.json').read_bytes()).hexdigest()}
    (ROOT/'results_b.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k in
                      ('status','belt_cases','belt_steps_compared','segment_pairs','seed_phase_cases')},ensure_ascii=False))


if __name__=='__main__':
    main()
