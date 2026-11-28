"""独立复核「整批k件配k条取货通道的均分」修正版。
现行步进：步初/第2条首格可能腾空（物品进格满8步后、下游随机放行）；
第4条本机各通道按随机先后判（每条至多判一次，首格空且格里有货就取）；
第5条完工整批进格（格里件数+k<=50 才进）；第6条可开工（上一批已进格、缓存空，随机有料）；
配方 8*L 步（L>=1，另加随机断电延迟）。
检查：
 A. 两步之间切刻（8种起点）：每条极大「每刻都就绪」段的所有子段，差<=1；段首判定前件数为k倍数 => 每刻全取或全不取。
 B. 原条文「任一时刻」下切在第4条本机各判定之间（位置p=1..k-1，判定先后每步固定，否则切点无意义）是否仍成立。
 C. 对照：滞留改 7 步。
"""
import random, sys

def run(k, T, seed, ret=8, fixed_order=False, mode='model'):
    rnd = random.Random(seed)
    S = rnd.randint(0, 50)
    c1 = [None if rnd.random() < 0.5 else -rnd.randint(0, 12) for _ in range(k)]  # entry step or None
    cache_end = None if rnd.random() < 0.5 else rnd.randint(0, 10)  # end step of running batch
    q = rnd.choice([0.2, 0.5, 0.9, 1.0])
    r = rnd.choice([0.3, 0.7, 1.0])
    order0 = list(range(k)); rnd.shuffle(order0)
    log = []  # per step: (S_before_stage4, [empty_at_judgment], [took], order, S_after_each_judgment list)
    for s in range(T):
        # step start / stage 2: vacate
        for c in range(k):
            if c1[c] is not None and s - c1[c] >= ret and rnd.random() < q:
                c1[c] = None
        Sb = S
        order = order0 if fixed_order else rnd.sample(range(k), k)
        emp = [c1[c] is None for c in range(k)]
        took = [False]*k
        Safter = []
        for c in order:
            if S == 0:
                Safter.append(S); continue  # group stops / skipped
            if c1[c] is None:
                c1[c] = s; S -= 1; took[c] = True
            Safter.append(S)
        # stage 5
        if cache_end is not None and s >= cache_end and S + k <= 50:
            S += k; cache_end = None; entered = True
        # stage 6
        if cache_end is None and rnd.random() < r:
            L = 1 if rnd.random() < 0.8 else 2
            delay = 0 if rnd.random() < 0.85 else rnd.randint(1, 5)
            cache_end = s + 8*L + delay
        log.append((Sb, emp, took, order, Safter))
    return log

def check_between(log, k):
    bad_diff = bad_mult = segs = 0
    T = len(log)
    for o in range(8):
        nk = (T - o)//8
        ready = []; takes = []; S0 = []
        for j in range(nk):
            st = log[o+8*j:o+8*j+8]
            ready.append(all(any(x[1][c] for x in st) for c in range(k)))
            takes.append([sum(x[2][c] for x in st) for c in range(k)])
            S0.append(st[0][0])
        j = 0
        while j < nk:
            if not ready[j]: j += 1; continue
            e = j
            while e < nk and ready[e]: e += 1
            for a in range(j, e):
                cum = [0]*k
                allornone = True
                for b in range(a, e):
                    cum = [cum[c]+takes[b][c] for c in range(k)]
                    if len(set(takes[b])) > 1: allornone = False
                    segs += 1
                    if max(cum) - min(cum) > 1: bad_diff += 1
                    if S0[a] % k == 0 and not allornone: bad_mult += 1
            j = e
    return segs, bad_diff, bad_mult

def check_intra(log, k, p):
    """切点在每步第4条本机第p次判定之后（固定先后）。刻 j = 步 o+8j 的第 p+1.. 次判定 ... 步 o+8j+8 的前 p 次判定。"""
    bad_diff = bad_mult = segs = 0
    T = len(log)
    for o in range(8):
        nk = (T - o - 9)//8
        ready = []; takes = []; S0 = []
        for j in range(nk):
            b0 = o + 8*j
            tk = [0]*k; rd = [False]*k
            for s in range(b0, b0+9):
                Sb, emp, took, order, Saf = log[s]
                idxs = range(p, k) if s == b0 else (range(0, k) if s < b0+8 else range(0, p))
                for i in idxs:
                    c = order[i]
                    if emp[c] or not took[c] and False: rd[c] = True
                    if emp[c]: rd[c] = True
                    if took[c]: tk[c] += 1
                # emptiness at cut point / between: a channel judged before cut in b0 and empty after (not filled)
                if s == b0 + 8:  # 切点之前的步初腾空也属本刻
                    for i in range(p, k):
                        if emp[order[i]]: rd[order[i]] = True
                if s == b0:
                    for i in range(0, p):
                        c = order[i]
                        if emp[c] and not took[c]: rd[c] = True
            ready.append(all(rd)); takes.append(tk)
            S0.append(log[b0][4][p-1])
        j = 0
        while j < nk:
            if not ready[j]: j += 1; continue
            e = j
            while e < nk and ready[e]: e += 1
            for a in range(j, e):
                cum = [0]*k; aon = True
                for b in range(a, e):
                    cum = [cum[c]+takes[b][c] for c in range(k)]
                    if len(set(takes[b])) > 1: aon = False
                    segs += 1
                    if max(cum)-min(cum) > 1: bad_diff += 1
                    if S0[a] % k == 0 and not aon: bad_mult += 1
            j = e
    return segs, bad_diff, bad_mult

if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    for k in (2, 3):
        for ret, tag in ((8, '现行'), (7, '对照:滞留7步')):
            tot = [0, 0, 0]
            for sd in range(N):
                lg = run(k, 400, sd*7+k, ret=ret)
                r = check_between(lg, k)
                tot = [a+b for a, b in zip(tot, r)]
            print(f'A k={k} {tag}: 段数={tot[0]} 差>1={tot[1]} 整倍数却部分取={tot[2]}')
        for p in range(1, k):
            tot = [0, 0, 0]
            for sd in range(N):
                lg = run(k, 400, sd*11+k, fixed_order=True)
                r = check_intra(lg, k, p)
                tot = [a+b for a, b in zip(tot, r)]
            print(f'B k={k} 切在本机第{p}次判定后: 段数={tot[0]} 差>1={tot[1]} 整倍数却部分取={tot[2]}')
