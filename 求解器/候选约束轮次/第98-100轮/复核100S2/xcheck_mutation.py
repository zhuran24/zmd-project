#!/usr/bin/env python3
"""复核100S2：比对程序的变异自检——人为改动一边，比对必须报不一致。"""
import json
from engine_a import Factory
from engine_sim2 import make_world, sim2_state, a_state

res = []
for mut in ('belt_age', 'machine_take', 'control_no_change'):
    fa = Factory(5, lengths='rand', maxlen=4, check=False)
    w, lookup, belts, sink = make_world(fa)
    found = None
    for step in range(600):
        if step == 100 and mut == 'belt_age':
            b = fa.belts[40]
            b.cells[-1] = fa.t - 3 if b.cells[-1] is not None else None
        if step == 100 and mut == 'machine_take':
            m = fa.mach['P1']
            m.take -= 1
        fa.step(); w.step()
        if a_state(fa) != sim2_state(fa, w, lookup, belts):
            found = fa.t
            break
    res.append(dict(mutation=mut, first_mismatch_step=found))
print(json.dumps(res, ensure_ascii=False))
