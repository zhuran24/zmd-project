#!/usr/bin/env python3
"""抽象状态图穷举（编码 A：剩余步数倒计时）。

状态取在两步之间：
  cells[i]  第 i 个首格还要几步才空（0=本机判定时可收；收件当步置 8，每步开头减 1，
            所以第 t 步收的件在第 t+8 步、本机判定之前腾空，正是候选的前件）
  inv       本机取货格件数（放宽：任一步开头都可整批进 k 件，只要不超过 cap）
  order     第 32 行非运输单位取货侧的试探次序：从未成功的（按接通先后）在前，
            其余按上次成功由早到晚；never 位标出哪些从未成功
  mfirst    汇流器情形：汇流器那一级是否排在普通级之前（离线可改接通先后，两种都允许）
跟踪量：
  每对路 (i,j) 的前缀差 D 相对历史最小、最大值的 (D-minD, maxD-D)；二者之和就是从起点起
  任一时间段内这两路件数差的最大值。g=从指定起点起；s=当前无离线段内（离线时清零）。
  rotation：段内成功词是否是某个含全部 k 路的固定顺序的循环（前 k 个互异，此后与 k 个
  之前的相同）；grot 同样的检查但离线不清零（检验“整个成功词同一固定轮转”）。
离线（在两步之间）：
  none     不离线
  retain   保留成功记录：只重排从未成功者的接通先后
  clear    清空：全部变成从未成功，按任意新接通先后
  partial  任意一部分通道清空、其余保留（比两种读法更宽，用来看段内结论对混合读法也成立）
选路：
  any      本机在空首格中任选（覆盖任何级别、次序）
  lru      第 32、33 行，k 路同级
  merge    第 0 路首单位是汇流器（自成一级），其余同级 LRU
"""
import itertools, json, sys, time
from collections import deque

CAPV = 3   # 跟踪量封顶，超过 2 就已经是违例


def pairs(k):
    return [(i, j) for i in range(k) for j in range(i + 1, k)]


def upd(tr, x, prs):
    out = []
    for (i, j), (a, b) in zip(prs, tr):
        d = 1 if x == i else (-1 if x == j else 0)
        a2 = max(a + d, 0); b2 = max(b - d, 0)
        out.append((min(a2, CAPV), min(b2, CAPV)))
    return tuple(out)


def rot_ok(tail, x, k):
    if len(tail) < k:
        return x not in tail
    return x == tail[0]


def explore(k, choice, offline, cap, bsize=None):
    bsize = k if bsize is None else bsize
    prs = pairs(k)
    zero = tuple((0, 0) for _ in prs)
    perms = list(itertools.permutations(range(k)))
    init = []
    for inv in range(cap + 1):
        if choice == 'any':
            init.append(((0,) * k, inv, None, 0, None, zero, zero, (), (), True, True))
        else:
            for p in perms:
                for nlen in range(k + 1):
                    never = frozenset(p[:nlen])
                    for mf in ((True, False) if choice == 'merge' else (None,)):
                        init.append(((0,) * k, inv, p, never, mf, zero, zero, (), (), True, True))
    seen = set(init)
    dq = deque(init)
    stats = dict(states=0, max_g=0, max_s=0, seg_rot_viol=0, glob_rot_viol=0)
    examples = {}

    def offl(st):
        cells, inv, order, never, mf, g, s, stail, gtail, srok, grok = st
        res = [st]
        if offline == 'none':
            return res
        mfs = (True, False) if choice == 'merge' else (mf,)
        if choice == 'any':
            res.append((cells, inv, order, never, mf, g, zero, (), gtail, srok, grok))
            return res
        outs = set()
        if offline in ('retain',):
            pre = [c for c in order if c in never]
            post = [c for c in order if c not in never]
            for q in itertools.permutations(pre):
                for m in mfs:
                    outs.add((cells, inv, tuple(q) + tuple(post), never, m, g, zero, (), gtail, srok, grok))
        if offline in ('clear',):
            for q in perms:
                for m in mfs:
                    outs.add((cells, inv, q, frozenset(range(k)), m, g, zero, (), gtail, srok, grok))
        if offline in ('partial',):
            for r in range(k + 1):
                for sub in itertools.combinations(range(k), r):
                    nv = never | frozenset(sub)
                    post = [c for c in order if c not in nv]
                    for q in itertools.permutations(sorted(nv)):
                        for m in mfs:
                            outs.add((cells, inv, tuple(q) + tuple(post), frozenset(nv), m, g, zero, (), gtail, srok, grok))
        res.extend(outs)
        return res

    def trypick(cells, order, never, mf):
        free = [i for i in range(k) if cells[i] == 0]
        if not free:
            return []
        if choice == 'any':
            return free
        if choice == 'lru':
            return [next(c for c in order if cells[c] == 0)]
        # merge: channel 0 own level
        ordinary = [c for c in order if c != 0]
        lv = ([0], ordinary) if mf else (ordinary, [0])
        for level in lv:
            for c in level:
                if cells[c] == 0:
                    return [c]
        return []

    while dq:
        st = dq.popleft()
        stats['states'] += 1
        for st1 in offl(st):
            cells, inv, order, never, mf, g, s, stail, gtail, srok, grok = st1
            c2 = tuple(max(c - 1, 0) for c in cells)
            for add in (0, bsize):
                if inv + add > cap:
                    continue
                inv2 = inv + add
                picks = trypick(c2, order, never, mf) if inv2 > 0 else []
                if not picks:
                    nxt = [(c2, inv2, order, never, mf, g, s, stail, gtail, srok, grok)]
                else:
                    nxt = []
                    for x in picks:
                        c3 = list(c2); c3[x] = 8
                        if order is not None:
                            o2 = tuple(c for c in order if c != x) + (x,)
                            n2 = never - {x}
                        else:
                            o2, n2 = None, never
                        g2 = upd(g, x, prs); s2 = upd(s, x, prs)
                        sr = srok and rot_ok(stail, x, k)
                        gr = grok and rot_ok(gtail, x, k)
                        st2 = (tuple(c3), inv2 - 1, o2, n2, mf, g2, s2,
                               (stail + (x,))[-k:], (gtail + (x,))[-k:], sr, gr)
                        nxt.append(st2)
                for st2 in nxt:
                    if st2 in seen:
                        continue
                    seen.add(st2)
                    ge = max(a + b for a, b in st2[5]); se = max(a + b for a, b in st2[6])
                    if ge > stats['max_g']:
                        stats['max_g'] = ge
                    if se > stats['max_s']:
                        stats['max_s'] = se
                    if not st2[9] and st[9]:
                        stats['seg_rot_viol'] += 1
                    if not st2[10] and st[10]:
                        stats['glob_rot_viol'] += 1
                    dq.append(st2)
    return stats


def main(out):
    jobs = [
        # (k, choice, offline, cap)
        (2, 'any', 'clear', 50), (3, 'any', 'clear', 9), (4, 'any', 'clear', 8),
        (2, 'lru', 'none', 50), (3, 'lru', 'none', 9),
        (2, 'lru', 'retain', 50), (3, 'lru', 'retain', 9), (4, 'lru', 'retain', 8),
        (2, 'lru', 'clear', 50), (3, 'lru', 'clear', 9),
        (2, 'lru', 'partial', 20), (3, 'lru', 'partial', 9),
        (2, 'merge', 'none', 20), (3, 'merge', 'none', 9),
        (2, 'merge', 'clear', 20), (3, 'merge', 'clear', 9),
        (3, 'lru', 'retain', 15), (3, 'any', 'clear', 15),
        # 对照：每次只进 1 件（不是整批），穷举应能越过 2
        (3, 'any', 'none', 9, 1), (3, 'lru', 'clear', 9, 1),
    ]
    sel = sys.argv[2] if len(sys.argv) > 2 else None
    res = {}
    for job in jobs:
        key = '%d-%s-%s-cap%d' % job[:4] + ('-batch%d' % job[4] if len(job) > 4 else '')
        if sel and sel not in key:
            continue
        t0 = time.time()
        st = explore(*job)
        st['sec'] = round(time.time() - t0, 1)
        res[key] = st
        print(key, st, flush=True)
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'graph.json')
