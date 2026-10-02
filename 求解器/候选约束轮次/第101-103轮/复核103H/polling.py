#!/usr/bin/env python3
"""复核103H：H03 轮询均分、H04 混料轮询分料、H05 整批k件配k条取货通道的均分。自写。

非运输单位取货侧 k 条同级通道，规则第32行：先试上次成功最早的，从未成功的按接通先后排在最前。
首格独占、空着总收、每次收件恰 8 步后、本机判定前腾空。
离线在两步之间：keep=成功记录保留（接通先后可换，只影响从未成功者）；clear=全部变成从未成功，按新接通先后。
编码甲：时间戳排序；编码乙：显式队列。两者逐步比较选路。
"""
import itertools, json, random, sys
from fractions import Fraction
from math import gcd
from collections import deque

# ---------------- 逐步模拟，两种编码 ----------------
def run(k, horizon, supply, offl, conn0, last0, busy0, rng=None):
    """supply[t] = 第 t 步判定前新进入取货格的件数（整批或单件）；offl: {x: (mode, conn)} 离线在第 x 步前。
    last0: 初始成功记录（None=从未成功，否则负数步号，越小越早）；busy0: 初始首格腾空步号。
    返回 (word[(t,route)], 两编码是否一致)。"""
    # 编码甲
    last = list(last0); conn = list(conn0); busy = list(busy0)
    # 编码乙
    q = sorted([i for i in range(k) if last0[i] is None], key=lambda i: conn0.index(i)) + \
        sorted([i for i in range(k) if last0[i] is not None], key=lambda i: last0[i])
    never = set(i for i in range(k) if last0[i] is None)
    busyB = list(busy0)
    inv = 0; invB = 0
    word = []; ok = True
    for t in range(horizon):
        if t in offl:
            mode, nc = offl[t]
            conn = list(nc)
            if mode == 'clear':
                last = [None] * k
                q = list(nc); never = set(range(k))
            else:
                nv = [i for i in q if i in never]
                rest = [i for i in q if i not in never]
                q = sorted(nv, key=lambda i: nc.index(i)) + rest
        inv += supply[t]; invB += supply[t]
        # 甲
        chA = None
        if inv > 0:
            order = sorted(range(k), key=lambda i: (0, conn.index(i)) if last[i] is None else (1, last[i]))
            for i in order:
                if busy[i] <= t:
                    chA = i; break
            if chA is not None:
                inv -= 1; last[chA] = t; busy[chA] = t + 8
        # 乙
        chB = None
        if invB > 0:
            for i in q:
                if busyB[i] <= t:
                    chB = i; break
            if chB is not None:
                invB -= 1; q.remove(chB); q.append(chB); never.discard(chB); busyB[chB] = t + 8
        if chA != chB:
            ok = False
        if chA is not None:
            word.append((t, chA))
    return word, ok

def interval_maxdiff(word, k, horizon, offl_steps):
    """成功事件按时间排成词；时间段内的成功是连续子词。对每个连续子词 i..j-1，
    取包含它的最短时间段 [t_i, t_{j-1}+1)，其中切开它的离线数 m = #{x: t_i < x <= t_{j-1}}。
    返回 (子词两路差的最大值, 差-m 的最大值)。"""
    xs = sorted(offl_steps)
    import bisect
    W = len(word)
    best = 0; bm = -10**9
    for i in range(W):
        cnt = [0] * k
        for j in range(i, W):
            cnt[word[j][1]] += 1
            d = max(cnt) - min(cnt)
            m = bisect.bisect_right(xs, word[j][0]) - bisect.bisect_right(xs, word[i][0])
            if d > best: best = d
            if d - m > bm: bm = d - m
    return best, bm

def segment_prefix_ok(word, k, offl_steps):
    """每个无离线段内，成功词是某排列 π 的反复（前 k 个互异，此后 w[i]=w[i-k]）。"""
    cuts = sorted(offl_steps)
    segs = []
    cur = []; ci = 0
    for (t, r) in word:
        while ci < len(cuts) and cuts[ci] <= t:
            segs.append(cur); cur = []; ci += 1
        cur.append(r)
    segs.append(cur)
    for s in segs:
        if len(set(s[:k])) != len(s[:k]): return False
        for i in range(k, len(s)):
            if s[i] != s[i - k]: return False
    return True

def random_runs(rng, nrun, mode):
    stats = dict(runs=0, enc_mismatch=0, seg_prefix_fail=0, max_diff=0, max_diff_minus_m=-99,
                 max_diff_batch_clear=0, max_diff_batch_keep=0, viol=0)
    for it in range(nrun):
        k = rng.choice([2, 3, 4, 5, 6])
        horizon = rng.choice([120, 200])
        batch = (mode == 'batch')
        supply = [0] * horizon
        if batch:
            # 整批 k 件；初始库存 q 任意；容量 50
            q0 = rng.randrange(0, 51)
            supply[0] = q0
            stock = q0
            t = rng.randrange(1, 12)
            while t < horizon:
                supply[t] += k
                t += rng.choice([1, 2, 5, 8, 8, 8, 9, 13, 20, 40])
            # 容量约束由下游实际取走决定，这里放宽（只多给货），不影响条文前件
        else:
            for t in range(horizon):
                supply[t] = 1 if rng.random() < rng.choice([0.1, 0.13, 0.3, 0.6]) else 0
        offl = {}
        rate = rng.choice([0.0, 0.02, 0.1, 0.3])
        for x in range(1, horizon):
            if rng.random() < rate:
                md = rng.choice(['keep', 'clear']) if mode != 'batch_keep' else 'keep'
                if mode == 'batch_keep': md = 'keep'
                offl[x] = (md, rng.sample(range(k), k))
        conn0 = rng.sample(range(k), k)
        if batch:
            busy0 = [0] * k   # H05 前件：起点首格全空
        else:
            busy0 = [rng.randrange(-3, 8) for _ in range(k)]
        last0 = []
        for i in range(k):
            last0.append(None if rng.random() < 0.4 else -rng.randrange(1, 100) - i * 0.001)
        word, ok = run(k, horizon, supply, offl, conn0, last0, busy0)
        stats['runs'] += 1
        if not ok: stats['enc_mismatch'] += 1
        if not segment_prefix_ok(word, k, set(offl.keys())): stats['seg_prefix_fail'] += 1
        d, dm = interval_maxdiff(word, k, horizon, set(offl.keys()))
        stats['max_diff'] = max(stats['max_diff'], d)
        stats['max_diff_minus_m'] = max(stats['max_diff_minus_m'], dm)
        if dm > 1: stats['viol'] += 1
        if batch:
            if any(m == 'clear' for m, _ in offl.values()):
                stats['max_diff_batch_clear'] = max(stats['max_diff_batch_clear'], d)
            else:
                stats['max_diff_batch_keep'] = max(stats['max_diff_batch_keep'], d)
    return stats

# ---------------- H05 穷举（抽象状态，放宽库存） ----------------
def bfs_h05(k, allow_clear, single_items=False, limit=2):
    """状态：(首格剩余步 r_i∈0..7, 优先队列 perm, 从未成功前缀长 nn, 库存类, e)。
    e = D - min D，D = 路0件数 - 路1件数（路的标号对称，固定一对即可）。
    库存：0..3k-1 精确，>=3k 记 ('big', 余数)，放宽（不设 50 上限）。
    每步：离线（无 / 保留并重排从未成功前缀 / 清空任意排列）→ 可选进一批 → 判定 → 可选进一批 → 首格计时。
    single_items=True 时每次只进 1 件（非整批，作对照）。返回 (状态数, 是否出现 e>limit, 最大 e)。"""
    add = 1 if single_items else k
    E = 3 * k
    def inv_add(c):
        if c[0] == 'x':
            v = c[1] + add
            return ('x', v) if v < E else ('b', v % k)
        return ('b', (c[1] + add) % k)
    def inv_sub(c):
        if c[0] == 'x':
            return [('x', c[1] - 1)]
        r = c[1]
        if r == 0:
            return [('b', k - 1), ('x', E - 1)]
        return [('b', r - 1)]
    perms = list(itertools.permutations(range(k)))
    init = []
    invs = [('x', v) for v in range(E)] + [('b', r) for r in range(k)]
    for p in perms:
        for nn in range(k + 1):
            for c in invs:
                init.append(((0,) * k, p, nn, c, 0))
    seen = set(init); dq = deque(init); maxe = 0; bad = None
    while dq:
        st = dq.popleft()
        r, p, nn, c, e = st
        # 离线选项
        opts = [(p, nn)]
        if nn >= 2:
            for np_ in itertools.permutations(p[:nn]):
                opts.append((tuple(np_) + p[nn:], nn))
        if allow_clear:
            for pp in perms:
                opts.append((pp, k))
        for (p1, nn1) in set(opts):
            for when in (0, 1, 2):  # 0 不进批，1 判定前进批，2 判定后进批
                cs = [c]
                if when == 1:
                    cs = [inv_add(c)]
                for c1 in cs:
                    has = not (c1[0] == 'x' and c1[1] == 0)
                    ch = None
                    if has:
                        for i in p1:
                            if r[i] == 0:
                                ch = i; break
                    if ch is None:
                        nexts = [(r, p1, nn1, c1, e)]
                    else:
                        rr = list(r); rr[ch] = 8
                        pos = p1.index(ch)
                        p2 = p1[:pos] + p1[pos + 1:] + (ch,)
                        nn2 = nn1 - 1 if pos < nn1 else nn1
                        d = 1 if ch == 0 else (-1 if ch == 1 else 0)
                        e2 = max(0, e + d)
                        nexts = [(tuple(rr), p2, nn2, c2, e2) for c2 in inv_sub(c1)]
                    for (r3, p3, nn3, c3, e3) in nexts:
                        if when == 2:
                            c3 = inv_add(c3)
                        r4 = tuple(max(0, x - 1) for x in r3)
                        ns = (r4, p3, nn3, c3, e3)
                        if e3 > maxe: maxe = e3
                        if e3 > limit:
                            if bad is None: bad = st
                            continue
                        if ns not in seen:
                            seen.add(ns); dq.append(ns)
    return len(seen), bad is not None, maxe

# ---------------- k 件块引理：首格可收偏移的全部模式 ----------------
def block_lemma(kmax=6):
    out = {}
    for k in range(2, kmax + 1):
        worst = 0; npat = 0; nstates = 0; formula_mismatch = 0
        # z 个 0（z>=1），其余为 1..7 中互异正数
        for z in range(1, k + 1):
            for pos in itertools.combinations(range(1, 8), k - z):
                rel = [0] * z + list(pos)
                npat += 1
                # 编码甲：公式 max(r_i + k - i)，i 从 1 起、按升序
                rs = sorted(rel)
                fA = max(rs[i] + (k - 1 - i) for i in range(k))
                # 编码乙：穷举每步在可收位置中任选一个服务的全部次序（不闲置）
                fB_max = -1
                def dfs(t, remaining, cnt):
                    nonlocal fB_max, nstates
                    nstates += 1
                    if not remaining:
                        fB_max = max(fB_max, t - 1); return
                    avail = [x for x in remaining if rel[x] <= t]
                    if not avail:
                        dfs(t + 1, remaining, cnt); return
                    for x in set(avail):
                        rem = list(remaining); rem.remove(x)
                        dfs(t + 1, tuple(rem), cnt + 1)
                dfs(0, tuple(range(k)), 0)
                if fA != fB_max: formula_mismatch += 1
                worst = max(worst, fB_max)
        out[k] = dict(patterns=npat, worst_last_offset=worst, formula_mismatch=formula_mismatch, dfs_states=nstates)
    return out

# ---------------- H04 同余公式 ----------------
def h04_check(rng, n=300):
    mism = 0; cases = 0
    for _ in range(n):
        k = rng.randrange(2, 7); L = rng.randrange(1, 13)
        items = [rng.choice('abc') for _ in range(L)]
        h = gcd(L, k)
        # 编码甲：公式（每个成功一件，F 取 1 件/单位时间时，流量比 = 件数/总件数）
        # 编码乙：显式数 L*k 个成功
        N = L * k
        cnt = {}
        for n_ in range(N):
            j = n_ % k; a = items[n_ % L]
            cnt[(j, a)] = cnt.get((j, a), 0) + 1
        for j in range(k):
            for a in 'abc':
                c = sum(1 for s in range(L) if s % h == j % h and items[s] == a)
                fA = Fraction(h * c, L * k)
                fB = Fraction(cnt.get((j, a), 0), N)
                cases += 1
                if fA != fB: mism += 1
    return dict(cases=cases, mismatch=mism)

def main():
    rng = random.Random(10301)
    res = {}
    res['block_lemma'] = block_lemma(6)
    res['h04'] = h04_check(rng)
    res['random_single'] = random_runs(rng, 1500, 'single')
    res['random_batch'] = random_runs(rng, 1500, 'batch')
    # H03 反例：每次出货前离线清空、接通先后不变
    k = 3; horizon = 160
    supply = [1 if t % 8 == 0 else 0 for t in range(horizon)]
    offl = {x: ('clear', [0, 1, 2]) for x in range(1, horizon) if x % 8 == 0}
    word, ok = run(k, horizon, supply, offl, [0, 1, 2], [None] * 3, [0] * 3)
    res['H03_counterexample'] = dict(counts=[sum(1 for _, r in word if r == i) for i in range(3)], enc_ok=ok)
    word, ok = run(k, horizon, supply, {x: ('keep', [0, 1, 2]) for x in offl}, [0, 1, 2], [None] * 3, [0] * 3)
    res['H03_counterexample_keep'] = dict(counts=[sum(1 for _, r in word if r == i) for i in range(3)], enc_ok=ok)
    # H05 「2 不能改回 1」：第 0、40 步各一批 3 件，第 30 步前离线清空，新接通 3,2,1
    supply = [0] * 60; supply[0] = 3; supply[40] = 3
    word, ok = run(3, 60, supply, {30: ('clear', [2, 1, 0])}, [0, 1, 2], [None] * 3, [0] * 3)
    res['H05_diff2_witness'] = dict(word=word, enc_ok=ok,
                                    interval_2_41=[sum(1 for t, r in word if 2 <= t < 41 and r == i) for i in range(3)])
    # 穷举
    for kk in (2, 3):
        for clr in (False, True):
            n, bad, me = bfs_h05(kk, clr, False, limit=(2 if clr else 1))
            res[f'bfs_k{kk}_{"clear" if clr else "keep"}'] = dict(states=n, violation=bad, max_e=me)
        n, bad, me = bfs_h05(kk, True, True, limit=2)
        res[f'bfs_k{kk}_clear_single_items_control'] = dict(states=n, violation=bad, max_e=me)
    json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else 'polling.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k_: v for k_, v in res.items() if k_ != 'H05_diff2_witness'}, ensure_ascii=False, default=str))
    print(res['H05_diff2_witness'])

if __name__ == '__main__':
    main()
