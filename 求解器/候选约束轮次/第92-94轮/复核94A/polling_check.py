#!/usr/bin/env python3
"""复核94A：「轮询均分」步进版的有限枚举核验，两套独立实现逐例比对。

模型（只取候选前提里写到的东西）：
- 一个单位有 k 条同级取货通道（k=1..6），起点全部首物品格为空。
- 首物品格每次收件后恰 8 步腾空：收件步 r，第 r+8 步它自己判定时送走。
  非运输单位：首格（元件）总在本单位之前判定，第 r+8 步本单位就能再送；
  运输单位：首格可能层数比本单位高（数层数时选了别的支），在本单位之后判定，
  这时第 r+9 步才见空。每条通道的 before 标志全枚举。
- 组：第 n 组名义步 T_n=8n，件数 g_n，相邻组和 ≤k；可用延迟 d_n∈{0,1}
  （组形成在本单位本步判定之后时，下一步才能送）。
- 本单位每步至多判定一次、至多送出一件。
- 轮询：运输单位按接通先后循环、从上次成功的下一条开始（起点指针任意，枚举）；
  非运输单位先试从未成功的（按接通先后），再按上次成功由早到晚。
  非运输单位的起点历史：全部 k! 种排列 × 前若干条从未成功。
- 另有可选的「外通道」：更高一级（直接接汇流器的一级），每步可由对手决定它空不空
  （随机抽样部分）；以及同级外通道（非运输单位的 LRU 里与 k 条混排）。
检查：k 条通道内的成功序列严格按起点规定的固定顺序循环。
"""
import itertools, json, random, hashlib, sys

def group_words(k, N):
    out = []
    def rec(prefix):
        if len(prefix) == N:
            out.append(tuple(prefix)); return
        for g in range(0, k + 1):
            if prefix and prefix[-1] + g > k:
                continue
            rec(prefix + [g])
    rec([])
    return out

# ---------- 实现 A：逐步模拟，首格用剩余步数倒计时 ----------
def sim_A(k, kind, before, words, delays, init, steal=None, same_level_out=None):
    """kind: 'T' 运输 / 'N' 非运输。init: T 时为起点指针; N 时为 (perm, never_count)。
    steal: 函数 step->bool，更高级外通道这一步是否空（空则先被它取走）。
    same_level_out: N 时同级外通道的初始 LRU 位置与空闲函数 (pos, freefn)。
    返回 k 条内的成功通道序列。"""
    busy_until = [None] * k   # 首格收件步
    pending = []              # (可用步, 组号)
    for n, g in enumerate(words):
        for _ in range(g):
            pending.append((8 * n + delays[n], n))
    pending.sort()
    seq = []
    if kind == 'T':
        ptr = init  # 下一次从 ptr 开始
    else:
        perm, never = init
        # LRU 列表：前 never 个视为从未成功（按接通先后=编号升序排），其余按 perm 顺序为上次成功由早到晚
        nev = sorted(perm[:never])
        succ = list(perm[never:])
        lru = [('k', c) for c in nev] + [('k', c) for c in succ]
        if same_level_out is not None:
            pos, _ = same_level_out
            lru.insert(pos, ('o', 0))
    last = 8 * len(words) + 20
    for t in range(last):
        avail = [p for p in pending if p[0] <= t]
        if not avail:
            continue
        # 本步判定一次
        if steal is not None and steal(t):
            pending.remove(avail[0]);  # 更高级外通道取走一件
            continue
        def free(c):
            r = busy_until[c]
            if r is None: return True
            return t >= r + 8 if before[c] else t >= r + 9
        sent = False
        if kind == 'T':
            for i in range(k):
                c = (ptr + i) % k
                if free(c):
                    busy_until[c] = t; seq.append(c); ptr = (c + 1) % k; sent = True; break
        else:
            for idx, (typ, c) in enumerate(lru):
                if typ == 'o':
                    if same_level_out[1](t):
                        lru.pop(idx); lru.append(('o', 0)); sent = True; break
                    continue
                if free(c):
                    busy_until[c] = t; seq.append(c); lru.pop(idx); lru.append(('k', c)); sent = True; break
        if sent:
            pending.remove(avail[0])
    assert not pending, ('未送完', k, kind, words)
    return seq

# ---------- 实现 B：不逐步，按「下一次可送的最早步」事件推进，指针/队列用不同数据结构 ----------
def sim_B(k, kind, before, words, delays, init):
    ready_at = [0] * k      # 该通道首格最早见空的步（相对本单位判定）
    items = []
    for n, g in enumerate(words):
        items += [8 * n + delays[n]] * g
    items.sort()
    seq = []
    if kind == 'T':
        order = list(range(init, k)) + list(range(0, init))   # 当前尝试次序
    else:
        perm, never = init
        order = sorted(perm[:never]) + list(perm[never:])
    t = 0
    i = 0
    while i < len(items):
        t = max(t, items[i])
        # 找本步 order 中第一个可用者；若无则下一步
        cand = [c for c in order if ready_at[c] <= t]
        if not cand:
            t = min(ready_at[c] for c in order)
            continue
        c = cand[0]
        seq.append(c)
        ready_at[c] = t + (8 if before[c] else 9)
        if kind == 'T':
            j = order.index(c)
            order = order[j + 1:] + order[:j + 1]
        else:
            order.remove(c); order.append(c)
        i += 1
        t += 1
    return seq

def expected_order(k, kind, init):
    if kind == 'T':
        return [(init + i) % k for i in range(k)]
    perm, never = init
    return sorted(perm[:never]) + list(perm[never:])

def is_cyclic(seq, order):
    k = len(order)
    return all(seq[i] == order[i % k] for i in range(len(seq)))

def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    stats = {}
    h = hashlib.sha256()
    bad = []
    for k in range(1, 7):
        words = group_words(k, N)
        cnt = 0
        for kind in ('T', 'N'):
            befores = list(itertools.product([True, False], repeat=k)) if kind == 'T' else [tuple([True] * k)]
            # 同级通道对称：非运输单位的起点顺序只是一张排列，换名后等价，取恒等及两种
            # 「从未成功」的划分；运输单位的指针旋转与 before 标志旋转等价，取指针 0。
            if kind == 'T':
                inits = [0]
            else:
                inits = [(tuple(range(k)), 0), (tuple(range(k)), k), (tuple(reversed(range(k))), k // 2)]
            for before in befores:
                for init in inits:
                    exp = expected_order(k, kind, init)
                    for w in words:
                        for d in itertools.product([0, 1], repeat=N):
                            a = sim_A(k, kind, before, w, d, init)
                            b = sim_B(k, kind, before, w, d, init)
                            cnt += 1
                            h.update(repr((k, kind, before, init, w, d, a)).encode())
                            if a != b or not is_cyclic(a, exp):
                                bad.append((k, kind, before, init, w, d, a, b))
        stats[k] = cnt
        print('k', k, 'cases', cnt, 'bad', len(bad), flush=True)
    # 随机：更高级外通道与同级外通道的对手
    rng = random.Random(9401)
    rnd = 0
    for _ in range(40000):
        k = rng.randint(1, 6)
        kind = 'N'
        w = rng.choice(group_words(k, N + 2))
        d = tuple(rng.randint(0, 1) for _ in range(N + 2))
        perm = tuple(rng.sample(range(k), k)); never = rng.randint(0, k)
        init = (perm, never)
        steal_set = {t for t in range(8 * (N + 2) + 20) if rng.random() < 0.3}
        out_set = {t for t in range(8 * (N + 2) + 20) if rng.random() < 0.3}
        pos = rng.randint(0, k)
        a = sim_A(k, kind, tuple([True] * k), w, d, init,
                  steal=(lambda t: t in steal_set) if rng.random() < 0.5 else None,
                  same_level_out=(pos, lambda t: t in out_set) if rng.random() < 0.5 else None)
        if not is_cyclic(a, expected_order(k, kind, init)):
            bad.append(('rand', k, w, d, init, a))
        rnd += 1
    for _ in range(20000):
        k = rng.randint(2, 6)
        w = rng.choice(group_words(k, N + 2))
        d = tuple(rng.randint(0, 1) for _ in range(N + 2))
        steal_set = {t for t in range(8 * (N + 2) + 20) if rng.random() < 0.3}
        before = tuple(rng.random() < 0.5 for _ in range(k))
        init = rng.randrange(k)
        a = sim_A(k, 'T', before, w, d, init, steal=lambda t: t in steal_set)
        if not is_cyclic(a, expected_order(k, 'T', init)):
            bad.append(('randT', k, w, d, init, a))
        rnd += 1
    res = dict(N_groups=N, exhaustive_cases_per_k=stats, random_cases=rnd, bad=len(bad),
               bad_examples=[repr(x) for x in bad[:5]], trace_sha256=h.hexdigest())
    json.dump(res, open('polling_check.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))

if __name__ == '__main__':
    main()
