#!/usr/bin/env python3
"""两个见证在按时刻记账的编码里重放（与 sim2_check.py 互核）。

W1：k=3，取货格第 0 步有 3 件，第 40 步再进一批 3 件；第 30 步前离线。
W2：k=2，第 0 路首单位是汇流器、级别高；第 0 步有 1 件，第 3、16 步各进一批 2 件。
首格都在收件 8 步后、本机判定前腾空。
"""
import json, sys
from timeline import max_pair_diff


def replay(k, inv0, batches, steps, offline=None, merge=False):
    inv = inv0
    recv = [-10 ** 6] * k
    last = [None] * k
    conn = list(range(k))
    word = []
    for t in range(steps):
        if offline and t == offline['t']:
            conn = offline['conn']
            if offline['clear']:
                last = [None] * k
        inv += k * batches.count(t)
        free = [i for i in range(k) if t >= recv[i] + 8]
        if inv and free:
            key = lambda i: (0, conn[i], 0) if last[i] is None else (1, 0, last[i])
            if merge and 0 in free:
                x = 0
            else:
                x = min([i for i in free if not (merge and i == 0)] or free, key=key)
            inv -= 1; recv[x] = t; last[x] = t; word.append((t, x))
    return word


def main(out):
    res = {}
    for mode in ('retain', 'clear'):
        wd = replay(3, 3, [40], 60, dict(t=30, conn=[2, 1, 0], clear=(mode == 'clear')))
        res['W1-' + mode] = dict(word=[x + 1 for _, x in wd], times=[t for t, _ in wd],
                                 interval_2_41=[sum(1 for t, x in wd if 2 <= t < 41 and x == j)
                                                for j in range(3)])
    wd = replay(2, 1, [3, 16], 30, merge=True)
    res['W2'] = dict(word=['汇' if x == 0 else '带' for _, x in wd], times=[t for t, _ in wd],
                     max_diff=max_pair_diff([x for _, x in wd], 2))
    print(json.dumps(res, ensure_ascii=False))
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'witness.json')
