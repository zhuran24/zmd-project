#!/usr/bin/env python3
"""复核94A：见证的稳健性——准入口窗口按 40 步或 41 步走完、两取货口起送相差 0..39 步。
用 witness_n06.py 的编码一（本席自写），只改两处参数。"""
import json
from witness_n06 import S1

def run(u_first, win, offset, steps=3000):
    s = S1(u_first)
    s.gate_can = lambda w, s=s: w is None or s.t - w >= win
    # 取货口乙晚 offset 步开始送：前 offset 步不让它送
    orig_step = s.step
    seen = {}
    while s.t < steps:
        k = s.key() + ((s.t if s.t < offset else -1),)
        if k in seen:
            period = s.t - seen[k]; break
        seen[k] = s.t
        if s.t < offset:
            # 暂时让带B首格看似被占，阻止取货口乙送
            hold = s.B[0]
            s.B[0] = s.t if hold is None else hold
            orig_step()
            if hold is None and s.B[0] is not None and s.B[0] == s.t - 1:
                pass
            if hold is None:
                s.B[0] = None if s.B[0] == s.t - 1 else s.B[0]
                s.stock += 0
        else:
            orig_step()
    n0 = len(s.log)
    for _ in range(period):
        s.step()
    cnt = {'P->J1': 0, 'P->J2': 0, 'U->J1': 0}
    for t, e in s.log[n0:]:
        cnt[e] += 1
    return period, cnt

out = {}
for win in (40, 41):
    for uf in (True, False):
        rows = {}
        for off in range(0, 40):
            p, c = run(uf, win, off)
            rows[off] = (p, c['P->J1'], c['P->J2'], c['U->J1'])
        out[f'win{win}_{"U先" if uf else "P先"}'] = rows
summary = {}
for k, rows in out.items():
    zero = [o for o, r in rows.items() if r[1] == 0]
    summary[k] = dict(offsets_with_P_to_J1_zero=zero,
                      distinct_patterns=sorted({(r[0], r[1], r[2], r[3]) for r in rows.values()}))
json.dump(dict(summary=summary, rows=out), open('witness_n06_variants.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
