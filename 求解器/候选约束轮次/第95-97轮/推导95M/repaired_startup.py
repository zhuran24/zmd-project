#!/usr/bin/env python3
"""Checks of the switch-off, load, switch-on-and-end repair, in both models."""
from pathlib import Path
import json
import random
from plant_a import Plant
from plant_b import fresh,tick
from verify_plant import assert_equal

OUT=Path(__file__).resolve().parent


def trial(seed,lengths):
    rng=random.Random(seed)
    a,b=Plant(lengths),fresh(lengths)
    a.machines['A'].enabled=a.machines['C'].enabled=False
    b['enabled'][0]=b['enabled'][2]=False
    a.add('A',50); b['machines'][0][0]=50
    waits=[]
    def wait():
        n=rng.randrange(0,129)
        waits.append(n)
        for _ in range(n):
            a.step(); tick(b)
            assert_equal(a,b)
    wait()
    assert a.add('C',50)
    b['machines'][2][0]=50
    wait()
    total=lengths[0]+lengths[2]
    if total>97:
        for i,r in ((0,'CA'),(2,'AC')):
            # Fill from the last cell backwards. Both destination storage
            # slots are already full, so no inserted item can leave a route.
            for j in reversed(range(lengths[i])):
                assert a.routes[r][j].enter is None
                assert b['ages'][i][j]<0
                a.routes[r][j].enter=a.t-1
                b['ages'][i][j]=0
                wait()
    wait()
    expected=2*(100+(total if total>97 else 0))
    assert a.phi2()==expected
    assert a.phi2()>=2*total+5
    # One allowed multi-switch operation; debug end is this operation's
    # completion, before the next simulation step.
    a.machines['A'].enabled=a.machines['C'].enabled=True
    b['enabled'][0]=b['enabled'][2]=True
    assert_equal(a,b)
    return {'seed':seed,'L':total,'wait_steps':sum(waits),'operations':len(waits),
            'debug_end_phi2':expected,'required_phi2':2*total+5}


def main():
    cases=[]
    for n in range(12):
        lengths=(7,13,31,5,5,5) if n<4 else (48,7,49,5,3,3) if n<8 else (51,7,49,5,3,3)
        cases.append(trial(9300+n,lengths))
    result={'cases':cases,'differences':0,
            'note':'数量界由关机期间无制造、满存货格不收货证明；有限模拟仅核对实施。'}
    (OUT/'repaired_startup.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'differences':0,'L_values':sorted({x['L'] for x in cases})}))


if __name__ == '__main__':
    main()
