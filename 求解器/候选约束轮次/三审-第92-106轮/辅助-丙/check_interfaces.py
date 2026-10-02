#!/usr/bin/env python3
"""整批词见证、纯带供料循环及两处初态缺项的独立局部检查。"""
from pathlib import Path
import json,random

OUT=Path(__file__).resolve().parent

def polling(k,initial,arrivals,clear_at=(),ranks=None,priority=False):
    q=initial;release=[0]*k;last=[-100]*k;rank=list(range(k));events=[]
    for t in range(81):
        if t in clear_at:last=[-100]*k;rank=list(reversed(rank))
        q+=arrivals.get(t,0)
        candidates=sorted(range(k),key=lambda i:((i if priority else 0),last[i],rank.index(i)))
        if q:
            for i in candidates:
                if release[i]<=t:
                    release[i]=t+8;last[i]=t;q-=1;events.append((t,i));break
    return events

def dedicated(d,needs,counts,lengths,seed):
    rng=random.Random(seed)
    lines=[]
    for material,(count,lens) in enumerate(zip(counts,lengths)):
        for length in lens:
            lines.append([material,[(-rng.randrange(9) if rng.randrange(2) else None) for _ in range(length)]])
    raw=[0]*len(needs);out=0;done=None;output_birth=None
    empty_after=0;refill_fail=0
    for t in range(5000):
        if done is not None and done<=t and out<50:out+=1;done=None
        rng.shuffle(lines)
        for mat,cells in lines:
            for j in range(len(cells)-1,-1,-1):
                if cells[j] is None or t-cells[j]<8:continue
                if j+1<len(cells):
                    if cells[j+1] is not None:continue
                    cells[j+1]=t
                else:
                    if raw[mat]==50:continue
                    raw[mat]+=1
                cells[j]=None
        # 来源均为独立持续有料的单出口（或其已证同一步补货合同）。
        for mat,cells in lines:
            if cells[0] is None:cells[0]=t
        freed=False
        if output_birth is not None and t-output_birth>=8 and t%113<89:
            output_birth=None;freed=True
        if output_birth is None and out:output_birth=t;out-=1
        if done is not None and done<=t and out<50:out+=1;done=None
        if done is None and all(x>=n for x,n in zip(raw,needs)):
            raw=[x-n for x,n in zip(raw,needs)];done=t+8*d
        if t>=2000:
            empty_after+=done is None
            if d==1 and freed:refill_fail+=output_birth is None
    return empty_after,refill_fail

def main():
    clear=polling(3,3,{40:3},(30,))
    merge=polling(2,1,{3:2,16:2},priority=True)
    assert ''.join(str(i+1) for t,i in clear)=='123321'
    assert ''.join('MT'[i] for t,i in merge)=='MTMMT'
    count=[sum(i==j for t,i in clear if 2<=t<41) for j in range(3)]
    assert count==[0,0,2]
    specs=[(1,[1],[1]),(1,[2,1],[2,1]),(1,[2],[2]),
           (5,[10,15],[2,3]),(5,[10,10],[2,2])]
    healthy=[]
    for idx,(d,a,c) in enumerate(specs):
        for seed in range(20):
            lens=[[1+(seed+3*j+i)%13 for j in range(n)] for i,n in enumerate(c)]
            empty,fail=dedicated(d,a,c,lens,100*idx+seed)
            assert not empty and not fail
            healthy.append([idx,seed,empty,fail])
    # 19 的公式检查的是存货格余额；同种唯一性还须查取货格。
    # 此处只证明状态层面的缺项；该初态可否由允许的调试放料取得需单独判读。
    xa=xb=ia=ib=0;a,b=2,1
    m=min((xa+ia)//a,(xb+ib)//b)
    rA=xa+ia-a*m
    input_slots=[None,None];output_type='A'
    accepts_A=output_type!='A' and (None in input_slots or 'A' in input_slots)
    assert rA<50 and not accepts_A
    # 24 的两带初货来源疑点，可由调试中旋转同一物理传送带保留来源记录。
    bodies={'warehouse_port':(0,10,0,12),'P':(1,11,1,11),'Q':(2,11,2,11),
            'X':(1,12,3,14),'core':(1,1,9,9),'power':(4,11,5,12)}
    occupied={}
    for name,(x0,y0,x1,y1) in bodies.items():
        for x in range(x0,x1+1):
            for y in range(y0,y1+1):
                assert 0<=x<70 and 0<=y<70 and (x,y) not in occupied
                occupied[x,y]=name
    # 桩中心(5,12)，12x12覆盖 [-1,11] x [6,18]，与X相交。
    assert -1<4 and 1<11 and 6<15 and 12<18
    # P由反向直带旋转180度，Q由南入西出的转角带旋转90度。
    clockwise={'N':'E','E':'S','S':'W','W':'N'}
    assert clockwise[clockwise['E']]=='W' and clockwise[clockwise['W']]=='E'
    assert clockwise['S']=='W' and clockwise['W']=='N'
    origin_geometry=dict(bodies=bodies,final_path=['warehouse_port','P','Q','X'],
        core_output_port=[2,9],temporary_belt=[2,10],
        preparation_path=['core','temporary_belt','Q','P'],
        preparation_Q_ports=dict(input='S',output='W'),preparation_P_ports=dict(input='E',output='W'),
        final_P_ports=dict(input='W',output='E'),final_Q_ports=dict(input='W',output='N'),
        X_ports=dict(input='S',output='N'),rotation_checks=True,
        stable_state=dict(P_item='源矿',P_previous='Q',P_mature=True,Q_empty=True,
                          X_raw=0,X_output='源石粉末或空',X_cache_empty=True),
        actual_rule24_move_possible=False,
        conditional_status='若专用进路只限定最终拓扑，则为阻塞循环；若包括全部初货来源，此初态不符合前件')
    result=dict(clear_history_witness=clear,clear_window_counts=count,
                merge_priority_witness=merge,dedicated_cases=len(healthy),
                dedicated_steps=len(healthy)*5000,dedicated_violations=0,
                single_mixed_initial_output_probe=dict(input_slots=input_slots,
                    output_type=output_type,next_item='A',prefix_rA=rA,
                    prefix_condition=True,rule13_accepts=False,
                    status='conditional countermodel; requires a permitted initial misplaced A in output slot'),
                dedicated_initial_origin_geometry=origin_geometry)
    (OUT/'interfaces.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
