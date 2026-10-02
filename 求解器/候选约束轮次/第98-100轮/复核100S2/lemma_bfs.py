#!/usr/bin/env python3
"""复核100S2：第5节「固定偏移消费轮次的共享补货」穷举核对（逐格模型，对手任意）。

一个始终有货的非运输单位有 n 条独占出口，各接一条长 L_i 的纯带，带尾进各自接收格
（成对的两路进同一格时共用缺额，一次用2件）。对手可以：
  * 任选每轮基本步号 x_j（与上一轮相距 ≥8，可无限期不开新轮）；
  * 每轮任选哪些路这一轮消费（允许跳过，比报告要求的更宽）；
  * 源每步在首格空着的出口里任选一条补货（覆盖任意轮询、接通先后、离线重排、成功记录清空）；
  * 同一格两路都有成熟货而缺额只剩1时，任选谁先进。
一步：带内成熟货前移 → 带尾送进有缺额的接收格（随即带内前移）→ 源补一个空首格 → 步末按偏移消费。
检查：（1）每次消费之前该接收格缺额为0（库存满）；（2）每轮在 x_j+D+n 步末各打开位置补完、首格全满。
全部可达状态都检查，输出状态数。
"""
import itertools, json, sys, time

CAP_AGE = 8      # 货龄 ≥8 即成熟，封顶
CAP_T = 16       # 距上一轮基本步号的步数封顶（≥16 后与更久等价：窗口 ≤7、成熟 8）


def check(lengths, deltas, pairs=(), allow_skip=True, control=False, deadline=None, min_gap=8):
    n = len(lengths)
    D = max(deltas)
    assert control or D + n < 8
    # 共用一格的路：组号
    grp = list(range(n))
    for a, b in pairs:
        grp[b] = grp[a]
        assert deltas[a] == deltas[b]
    groups = sorted(set(grp))
    # 状态：(cells tuple of tuples, deficits tuple per group, tsb, active mask, pend_fill mask)
    #   tsb: 距本轮基本步号的步数（封顶）；active: 本轮要消费的路
    init_cells = tuple(tuple([CAP_AGE] * L) for L in lengths)
    init = (init_cells, tuple(0 for _ in groups), CAP_T, 0)
    gidx = {g: k for k, g in enumerate(groups)}
    DL = D + n if deadline is None else deadline
    seen = {init}
    frontier = [init]
    viol = []
    while frontier:
        nxt = []
        for st in frontier:
            for succ, bad in expand(st, lengths, deltas, grp, gidx, n, D, allow_skip, DL, min_gap):
                if bad:
                    viol.append((st, bad))
                    if len(viol) > 5:
                        return dict(ok=False, states=len(seen), viol=[str(v) for v in viol])
                if succ not in seen:
                    seen.add(succ)
                    nxt.append(succ)
        frontier = nxt
    return dict(ok=not viol, states=len(seen), viol=[str(v) for v in viol])


def settle(cells):
    cells = list(cells)
    for j in range(len(cells) - 2, -1, -1):
        if cells[j] >= CAP_AGE and cells[j + 1] < 0:
            cells[j + 1] = 0
            cells[j] = -1
    return cells


def expand(st, lengths, deltas, grp, gidx, n, D, allow_skip, DL, min_gap=8):
    cells0, defs0, tsb, active = st
    # 1. 本步开始：时间推进，货龄+1（状态里存的是上一步末的货龄）
    cells = [settle([min(CAP_AGE, a + 1) if a >= 0 else -1 for a in c]) for c in cells0]
    tsb1 = min(CAP_T, tsb + 1)
    # 2. 带尾送货：同一缺额组若成熟路多于缺额，对手选谁进
    defs = list(defs0)
    ready = [i for i in range(n) if cells[i][-1] >= CAP_AGE]
    options = []
    by_g = {}
    for i in ready:
        by_g.setdefault(gidx[grp[i]], []).append(i)
    choice_lists = []
    for g, idxs in by_g.items():
        k = min(defs[g], len(idxs))
        choice_lists.append([(g, comb) for comb in itertools.combinations(idxs, k)])
    for combo in itertools.product(*choice_lists) if choice_lists else [()]:
        c2 = [list(c) for c in cells]
        d2 = list(defs)
        for g, comb in combo:
            for i in comb:
                c2[i][-1] = -1
                c2[i] = settle(c2[i])
                d2[g] -= 1
        # 3. 源补首格（对手任选；有空首格就必须补一个）
        empties = [i for i in range(n) if c2[i][0] < 0]
        fills = empties if empties else [None]
        for fsel in fills:
            c3 = [list(c) for c in c2]
            if fsel is not None:
                c3[fsel][0] = 0
            # 3b. 补货期限检查：本轮 x_j+D+n 步末，本轮全部打开位置补完
            bad = None
            # tsb1 是本步距基本步号的步数；基本步号那一步 tsb=0
            if active and DL >= 0 and tsb1 == DL:
                if any(x > 0 for x in d2) or any(c3[i][0] < 0 for i in range(n)):
                    bad = ('deadline', tsb1, tuple(d2), tuple(tuple(c) for c in c3))
            # 4. 步末消费：是否本步开新轮（距上一轮基本步号 ≥8）
            starts = [False]
            if tsb1 >= min_gap:
                starts.append(True)
            for new in starts:
                if new:
                    masks = range(1, 1 << n) if allow_skip else [(1 << n) - 1]
                    t_now = 0
                else:
                    masks = [active]
                    t_now = tsb1
                for mask in masks:
                    # 成对的两路要么都消费要么都不（同格一次用2件）
                    okm = True
                    for i in range(n):
                        for j in range(n):
                            if i != j and grp[i] == grp[j] and ((mask >> i) & 1) != ((mask >> j) & 1):
                                okm = False
                    if not okm:
                        continue
                    d4 = list(d2)
                    bad2 = bad
                    cons = [i for i in range(n) if (mask >> i) & 1 and deltas[i] == t_now]
                    for g in {gidx[grp[i]] for i in cons}:
                        if d2[g] > 0 and bad2 is None:
                            bad2 = ('consume_before_refill', g, t_now, tuple(d2))
                    for i in cons:
                        d4[gidx[grp[i]]] += 1
                    cells_t = tuple(tuple(c) for c in c3)
                    yield (cells_t, tuple(d4), t_now, mask), bad2


def main():
    res = []
    t0 = time.time()
    cases = []
    # 协议核心六口：D=0,n=6，路长多重集（源任选出口，路彼此对称）
    for ls in list(itertools.combinations_with_replacement([1, 2], 6)) + [(1, 1, 2, 2, 3, 3), (1, 2, 3, 3, 3, 3), (3,) * 6]:
        cases.append(('core6', ls, (0,) * 6, ()))
    # 砂叶三出口 2,2,0 与 2,0,0
    for ls in itertools.product([1, 2, 3], repeat=3):
        cases.append(('sand220', ls, (2, 2, 0), ()))
        cases.append(('sand200', ls, (2, 0, 0), ()))
        cases.append(('sand222', ls, (2, 2, 2), ()))
    # 两出口同刻（O2、O3 型）与荞花两路同进一格
    for ls in itertools.product([1, 2, 3, 4], repeat=2):
        cases.append(('two00', ls, (0, 0), ()))
        cases.append(('pair', ls, (0, 0), ((0, 1),)))
    for name, ls, de, pr in cases:
        r = check(ls, de, pr, allow_skip=(name != 'core6'))
        r.update(case=name, lengths=ls, deltas=de, pairs=pr)
        res.append(r)
        if not r['ok']:
            print(json.dumps(r, ensure_ascii=False), flush=True)
    # 六口也跑允许跳过的版本（少量路长）
    for ls in [(1,) * 6, (1, 1, 1, 2, 2, 2)]:
        r = check(ls, (0,) * 6, (), allow_skip=True)
        r.update(case='core6_skip', lengths=ls, deltas=(0,) * 6, pairs=())
        res.append(r)
    # 反向对照（证明检查本身有效）：期限提前一步必须报违例；九路同刻、每轮间隔8步必须出现补货前消费
    controls = []
    for ls, de, dl, mg in [((1,) * 6, (0,) * 6, 5, 8), ((1,) * 6, (0,) * 6, -1, 5)]:
        r = check(ls, de, (), allow_skip=False, control=True, deadline=dl, min_gap=mg)
        controls.append(dict(lengths=ls, deltas=de, deadline=dl, ok=r['ok'], states=r['states'], first=r['viol'][:1]))
    summary = dict(cases=len(res), all_ok=all(r['ok'] for r in res),
                   controls=[(c['lengths'], c['deadline'], c['ok']) for c in controls],
                   max_states=max(r['states'] for r in res),
                   total_states=sum(r['states'] for r in res), secs=round(time.time() - t0, 1))
    json.dump(dict(summary=summary, controls=controls, cases=res), open('lemma_bfs.json', 'w'), ensure_ascii=False, indent=0)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
