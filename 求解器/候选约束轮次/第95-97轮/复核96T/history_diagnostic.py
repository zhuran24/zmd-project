"""Sensitivity check, NOT a rule-certified offline counterexample.

The temporary rules do not explicitly say to erase last-success records. This
file deliberately tests that additional transition, and labels its output so.
It does not change the authoritative preserve-history runs.
"""
import json
import random
from pathlib import Path
from plant_models import AbsolutePlant, CountdownPlant, NAMES

HERE = Path(__file__).resolve().parent
rng = random.Random(96964)
result = {'scope': 'extra history-erasure semantics only; not a certified offline trace',
          'cases_checked': 0, 'found': None}
for case in range(3000):
    k, n = 2, 2
    lengths = [rng.randrange(1, 6) for _ in range(4)]+[1, 1]
    nums = [0, 1, 2, 3, 25, 48, 49, 50]
    init = dict(k=k, n=n, ins=[rng.choice(nums) for _ in NAMES],
                outs=[rng.choice(nums) for _ in NAMES],
                remaining=[rng.choice([None, 0, 1, 7, 8]) for _ in NAMES],
                ages=[[rng.choice([None, 0, 1, 7, 8]) for _ in range(m)] for m in lengths],
                lastC=[None, None], lastK=[None, None])
    if case % 2 == 0:
        init['ins'][0] = init['ins'][1] = init['outs'][1] = 50
        init['outs'][0] = rng.randrange(5)
        for i in (0, 1):
            init['remaining'][i] = rng.randrange(9)
            init['ages'][i] = [rng.randrange(9) for _ in range(lengths[i])]
    a, b = AbsolutePlant(init), CountdownPlant(init)
    initial, bound = None, None
    trace = []
    for t in range(400):
        erased = t % 8 == 0
        if erased:
            a.last['C'] = [None, None]
            b.never[0], b.queue[0] = {0, 1}, []
        build = {'C': [1, 0], 'K': [0, 1]}
        order = ['C', 'A', 'B', 'K']
        enabled = dict.fromkeys(NAMES, True)
        a.step(t, [True, True], order, build, enabled)
        b.step(t, [True, True], order, build, enabled)
        assert a.state(t) == b.state(t)
        assert a.phi2() == b.phi2()
        trace.append(dict(step=t, erased=erased, phi2=a.phi2(), events=a.events[:],
                          state=a.state(t)))
        if t == 0:
            # Observe only after a complete powered/enabled step has run.
            initial = a.phi2()
            bound = min(initial-1, 2*(lengths[0]+lengths[1]+150))
            continue
        if a.phi2() < bound:
            result['found'] = dict(case=case, init=init, initial_phi2=initial,
                                   observation_step=0, lower_bound2=bound, failing_step=t,
                                   actual_phi2=a.phi2(), trace=trace)
            break
    result['cases_checked'] += 1
    if result['found']:
        break
if result['found']:
    witness = result['found']
    trials = []
    for erasure_at in [None]+list(range(8, witness['failing_step']+1, 8)):
        a, b = AbsolutePlant(witness['init']), CountdownPlant(witness['init'])
        trace = []
        for t in range(witness['failing_step']+1):
            if t == erasure_at:
                a.last['C'] = [None, None]
                b.never[0], b.queue[0] = {0, 1}, []
            build = {'C': [1, 0], 'K': [0, 1]}
            enabled = dict.fromkeys(NAMES, True)
            a.step(t, [True, True], NAMES, build, enabled)
            b.step(t, [True, True], NAMES, build, enabled)
            assert a.state(t) == b.state(t)
            if t == 0:
                start = a.phi2()
            trace.append(dict(step=t, phi2=a.phi2(), events=a.events[:]))
        trials.append(dict(erasure_at=erasure_at, initial_phi2=start,
                           final_phi2=a.phi2(), trace=trace))
    result['single_erasure_replays'] = trials
(HERE/'history_diagnostic.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: v for k, v in result.items() if k != 'found'}, ensure_ascii=False))
print('found', None if result['found'] is None else {
    k: result['found'][k] for k in ['case', 'initial_phi2', 'lower_bound2', 'failing_step', 'actual_phi2']})
