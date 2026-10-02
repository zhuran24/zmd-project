#!/usr/bin/env python3
"""独立重放 s06_k3_search.json 的例子：用事件表重新走一遍，逐项核对
(1) 每步机器至多送一件，送给“上次成功最早”的可收通道；(2) 首格收件后至少 8 步才移出；
(3) 固定 θ=0 的每个 [8n,8n+8) 内每条首格都有空着的时点；(4) 整批 3 件、两批进格相隔≥8 步、取货格≤50；
并在周期内数各通道件数。"""
import json, math

ex = json.load(open('s06_k3_search.json'))['examples']
out = []
for e in ex:
    D, T, arr, q0 = e['D'], e['T'], set(e['arr']), e['queue0']
    k = 3
    t0, per = e['t0'], e['period']
    N = t0 + 3 * per + 16
    occ = [None] * k          # 收件步号
    last = {c: None for c in range(k)}
    order0 = list(q0)
    o = 0
    last_arr = -100
    sends = []                # (t, ch)
    empty_moment = [[False] * (N // 8 + 2) for _ in range(k)]
    viol = []
    arrivals = []
    for t in range(N):
        if (t % T) in arr and t - last_arr >= 8 and o + k <= 50:
            o += k; last_arr = t; arrivals.append(t)
        for c in range(k):
            if occ[c] is None:
                empty_moment[c][t // 8] = True
            elif t - occ[c] >= D[c][occ[c] % 8]:
                if t - occ[c] < 8:
                    viol.append(('retention', t, c))
                occ[c] = None
                empty_moment[c][t // 8] = True
        if o > 0:
            # 顺序：从未成功的按初始顺序在前，其余按上次成功从早到晚
            never = [c for c in order0 if last[c] is None]
            done = sorted([c for c in range(k) if last[c] is not None], key=lambda c: last[c])
            for c in never + done:
                if occ[c] is None:
                    occ[c] = t; last[c] = t; o -= 1; sends.append((t, c))
                    break
    for c in range(k):
        for n in range(N // 8):
            if not empty_moment[c][n]:
                viol.append(('window', n, c))
    for a, b in zip(arrivals, arrivals[1:]):
        if b - a < 8:
            viol.append(('arrival_gap', a, b))
    cnt = [0] * k
    for t, c in sends:
        if t0 + per <= t < t0 + 2 * per:
            cnt[c] += 1
    cnt2 = [0] * k
    for t, c in sends:
        if t0 + 2 * per <= t < t0 + 3 * per:
            cnt2[c] += 1
    out.append(dict(T=T, period=per, counts_period=cnt, counts_next_period=cnt2,
                    violations=len(viol), first_viol=viol[:3], reported=e['diff']))
json.dump(out, open('s06_k3_verify.json', 'w'), ensure_ascii=False, indent=1)
for x in out:
    print(x)
