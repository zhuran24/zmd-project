#!/usr/bin/env python3
"""Independent 7..0 phase interpreter plus checks of stored numerical evidence."""
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path

from run_checks import lag_case, make_machine_case

HERE=Path(__file__).resolve().parent


def phase_run(n,order,steps=160):
    # [remaining phase, last movement step]; deliberately no entered timestamps.
    cells={'X':[[0,-1]],'S':[[0,-1] for _ in range(n)],'D':[[0,-1]]}
    deliveries=[]; states=[]; micro=[]

    def state():
        return {name:['x' if p is None else p[0] for p in cells[name]] for name in ('X','S')}

    def move(name,t):
        arr=cells[name]
        for j in range(len(arr)-1,-1,-1):
            p=arr[j]
            if p is None or p[1]==t:
                continue
            if p[0]>0:
                p[0]-=1; p[1]=t
            elif j+1<len(arr) and arr[j+1] is None:
                arr[j]=None; arr[j+1]=[7,t]

    def send(name,dest,t):
        p=cells[name][-1]
        if p is None or p[0]!=0 or p[1]==t:
            return
        if dest is None:
            cells[name][-1]=None; deliveries.append(t)
        elif cells[dest][0] is None:
            cells[name][-1]=None; cells[dest][0]=[7,t]

    for t in range(steps):
        for name in order:
            if name=='X':
                move('S',t); move('D',t)
                micro.append(dict(t=t,stage='X:使动后',**state()))
                send('X','S',t)
                micro.append(dict(t=t,stage='X:转移后',**state()))
                move('X',t)
                micro.append(dict(t=t,stage='X:自身移动后',**state()))
            elif name=='S':
                send('S',None,t)
                micro.append(dict(t=t,stage='S:转移后',**state()))
                move('S',t)
                micro.append(dict(t=t,stage='S:自身移动后',**state()))
            else:
                move('D',t)
        if cells['X'][0] is None:
            cells['X'][0]=[7,t]
        states.append(dict(t=t,**state()))
    return deliveries,states,micro


def check_invariants():
    # Tests constraints through alternating recipes, output backpressure, slots
    # and repeated internal pre-motion, rather than just the final mean rate.
    count=0
    for scope,inner in itertools.product(('logistics','all_channels'),('flush_send','send_flush')):
        w,m,sink=make_machine_case(3,scope,inner)
        for _ in range(600):
            w.step()
            seen=set()
            for u in w.order:
                arrays=[]
                if hasattr(u,'cells'):
                    arrays.append([p for p in u.cells if p is not None])
                if hasattr(u,'slots'):
                    arrays.extend(u.slots)
                    assert all(len(s)<=50 and len({p.kind for p in s})<=1 for s in u.slots)
                if hasattr(u,'cache'):
                    arrays.extend([u.cache,u.output])
                    assert len(u.output)<=50
                for a in arrays:
                    for p in a:
                        assert id(p) not in seen, 'duplicated item'
                        assert p.moved<w.t
                        seen.add(id(p))
            count+=1
    return count


def main():
    result=json.loads((HERE/'results.json').read_text())
    phase_cases=0
    for n,order in itertools.product(range(1,5),itertools.permutations(('X','S','D'))):
        _,sink,_,_=lag_case(n,order,steps=160)
        deliveries,states,micro=phase_run(n,order)
        assert [t for t,_ in sink.received]==deliveries,(n,order)
        phase_cases+=1
    deliveries,states,micro=phase_run(2,('X','S','D'),steps=45)
    assert states==result['b']['phase_trace_n2']
    (HERE/'b_n2_microphase.json').write_text(json.dumps(micro,ensure_ascii=False,indent=2)+'\n')
    for row in result['b']['baseline']:
        expected=Fraction(8*row['n'],8*row['n']+1) if row['order'].index('X')<row['order'].index('S') else Fraction(1)
        assert Fraction(row['rate_fraction'])==expected
    for row in result['c']['cases']:
        expected=16 if row['case']<3 else 18 if row['scope']=='logistics' else 20
        assert row['AB_period']==[expected],row
    for row in result['e']:
        assert row['rate_fraction']==dict(skip='1',rotate='14/15',hold='2/5',rotate_busy='1')[row['policy']]
    for row in result['f_insert']:
        if row['ore_first']:
            seq=row['sequence']
            assert all(seq[i:i+row['n']+2].count('blue')==1 for i in range(len(seq)-row['n']-1))
    assert result['f_overflow']['top']['rate_fraction']=='3/4'
    assert result['f_overflow']['lower']['rate_fraction']=='1/4'
    invariant_steps=check_invariants()
    originals=json.loads((HERE/'inputs.sha256.json').read_text())
    assert all(hashlib.sha256((HERE.parents[3]/p).read_bytes()).hexdigest()==h for p,h in originals.items())
    evidence=dict(phase_comparison_cases=phase_cases,phase_comparison_steps=160,
                  invariant_steps=invariant_steps,original_inputs_unchanged=True,status='PASS')
    (HERE/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence))


if __name__=='__main__':
    main()
