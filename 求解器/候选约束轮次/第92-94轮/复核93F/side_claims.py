#!/usr/bin/env python3
"""Independent checks of report-side assertions, not additional layout claims."""
import json
from pathlib import Path
from plant_a import Plant
from plant_b import fresh,tick,describe

OUT = Path(__file__).resolve().parent


def branch_order(cb_first):
    a,b=Plant(),fresh((7,13,31,5,5,5))
    a.add('A',50); a.add('C',50)
    b['machines'][0][0]=50; b['machines'][2][0]=50
    if cb_first:
        a.rank['CA'],a.rank['CB']=1,0
        b['priority'][0],b['priority'][1]=1,0
    ca_delivery=None
    history=[]
    minimum=200
    for step in range(100):
        before=a.arrivals['CA']
        a.step(); tick(b)
        assert json.loads(json.dumps(a.state())) == json.loads(json.dumps(describe(b)))
        minimum=min(minimum,a.phi2())
        if a.arrivals['CA']>before and ca_delivery is None:
            ca_delivery=step
        if step in (8,9,63,64,65):
            history.append(a.state())
    return {'C_first_channel':'CB' if cb_first else 'CA',
            'A_first_seed_receipt_step_index':ca_delivery,
            'minimum_phi2':minimum,'states':history}


def input_switch():
    a,b=[],[]
    for arrival in range(1,9):
        # A: explicit three-phase event simulation of a 1-tick machine.
        output,stock,ready,next_start=0,0,False,None
        for t in range(1,10):
            if t==8:
                ready=True
            if t==arrival:
                stock+=1
            if ready:
                output+=1; ready=False
            # The previous product is assumed to fit/clear as in the claim.
            if t>=8 and stock and next_start is None:
                stock-=1; next_start=t
        a.append(next_start)
        # B: max of completion time and availability time, with receipt
        # phase before the step's manufacture-start phase.
        b.append(max(arrival,8))
    assert a==b==[8]*8
    return {'arrival_steps':list(range(1,9)), 'next_start_A':a, 'next_start_B':b,
            'condition':'上一批已整批进入取货物品格，下一种原料确实在所列步的判定阶段收下'}


def negative_control():
    # Two legal crushers touch different intake sides of one merger.
    rect={'左粉碎机':[7,8,3,3],'上粉碎机':[10,11,3,3],
          '研磨机':[13,8,4,6],'供电桩':[8,14,2,2],'协议核心':[40,40,9,9]}
    roads=[(10,10),(11,10),(12,10)]
    grid={}
    for name,(x,y,w,h) in rect.items():
        for a in range(x,x+w):
            for b in range(y,y+h):
                assert (a,b) not in grid
                grid[a,b]=name
    for p in roads:
        assert p not in grid
        grid[p]='运输单位'
    # Independent rectangle intersection check, including 1x1 road cells.
    bounds=list(rect.values())+[[x,y,1,1] for x,y in roads]
    for j,(x,y,w,h) in enumerate(bounds):
        for X,Y,W,H in bounds[j+1:]:
            assert x+w<=X or X+W<=x or y+h<=Y or Y+H<=y
    cases=[]
    for order in ((0,1),(1,0)):
        # A: both crushers consume one manually inserted source ore at step
        # 0, complete at step 8, and send after all transport components.
        production=[0,0]; merger=None; sent=[0,0]
        for t in range(9):
            if t==8:
                production=[1,1]
            for m in order:
                if production[m] and merger is None:
                    merger=m; production[m]-=1; sent[m]+=1
        # B: independent capacity allocation at that completion step.
        free=1
        chosen=[]
        for m in order:
            if free:
                chosen.append(m); free-=1
        reference=[int(i in chosen) for i in range(2)]
        assert sent==reference
        cases.append({'order':order,'sent_by_crusher':sent,'merger_item_previous_unit':merger})
    # The author report's two withdrawal ports at one boundary merger would
    # have to be the left and lower ports feeding (1,1), and overlap (0,0).
    left={(0,0),(0,1),(0,2)}; lower={(0,0),(1,0),(2,0)}
    assert left&lower=={(0,0)}
    return {'legal_replacement_rectangles':rect,'merger':[10,10],
            'belt_cells':[[11,10],[12,10]],'cases':cases,
            'author_two_withdrawal_ports_overlap':[[0,0]],
            'scope':'两个粉碎机的合法局部反面对照；只反对删除唯一非运输来路这一前提'}


def main():
    x,y=branch_order(False),branch_order(True)
    assert x['A_first_seed_receipt_step_index']==64
    assert y['A_first_seed_receipt_step_index']==65
    assert y['minimum_phi2']==199
    result={'receiving_time_is_indirectly_order_dependent':[x,y],
            'input_switch':input_switch(),'negative_control':negative_control()}
    (OUT/'side_claims.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'A_receipt_step_CA_first':64,'A_receipt_step_CB_first':65,
                      'CB_first_minimum_phi2':199,'input_switch_passed':True}))


if __name__ == '__main__':
    main()
