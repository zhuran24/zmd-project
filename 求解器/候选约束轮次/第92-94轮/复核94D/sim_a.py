# 编码甲：函数式、绝对步号。复核94D 自写，不导入推导席脚本与 sim2。
# 规则读法（快照第 13、17、18、23—27、31—33、36 行）：
#   一步 = 结束到时的制造 → 元件判定（每条纯链下游先）→ 非运输单位判定（每台至多送 1 件，
#   取货侧按「从未成功的按接通先后在前，其余按上次成功最早在前」）→ 开始能开始的制造。
#   运输格物品停留满 8 步才能离开；制造 8 步；完成的一批在取货格放得下整批时立即进入。
# 机器状态 (inp, out, cache)：cache = -1 空，-2 已完成未进，>=0 为结束步号。
# 运输格：-1 空，否则为进入步号。
NEVER = -10**9
DW = 8
RT = 8


def settle(m, batch, cap):
    inp, out, c = m
    if c == -2 and out + batch <= cap:
        return (inp, out + batch, -1)
    return m


def phase1(m, t, batch, cap):
    if m is None:
        return None
    inp, out, c = m
    if c >= 0 and c == t:
        c = -2
    return settle((inp, out, c), batch, cap)


def chain(cells, t, dest_inp, dest_cap, release):
    """纯链下游先判定。dest_inp 为 None 时末格交给对手/外部，release 为真才放走。"""
    cells = list(cells)
    n = len(cells)
    e = cells[-1]
    if e >= 0 and t - e >= DW:
        if dest_inp is None:
            if release:
                cells[-1] = -1
        elif dest_inp < dest_cap:
            dest_inp += 1
            cells[-1] = -1
    for i in range(n - 2, -1, -1):
        e = cells[i]
        if e >= 0 and t - e >= DW and cells[i + 1] < 0:
            cells[i + 1] = t
            cells[i] = -1
    return tuple(cells), dest_inp


def pick(lasts, empties):
    order = sorted(range(len(lasts)), key=lambda i: lasts[i])
    for i in order:
        if empties[i]:
            return i
    return -1


def start(m, t):
    if m is None:
        return None
    inp, out, c = m
    if c == -1 and inp >= 1:
        return (inp - 1, out, t + RT)
    return m


class Cfg:
    def __init__(self, k=3, cap=50, has_b=True, has_k=True):
        self.k = k
        self.cap = cap
        self.has_b = has_b
        self.has_k = has_k


def step(st, t, cfg, rel_cb=False, rel_k=()):
    """st = (A, B, C, K, CA, AC, CB, BK, KCH, pollC, pollK)。
    has_b 为假时 CB 末格交给对手（rel_cb）；KCH 为 K 的各取货通道（每条一串格，末格交给对手 rel_k[i]）。
    返回 (新状态, C 送往 'A'/'B'/None, K 送往的通道号或 -1, K 各通道末格是否离开)。"""
    A, B, C, K, CA, AC, CB, BK, KCH, pollC, pollK = st
    cap = cfg.cap
    k = cfg.k
    # 1 结束到时的制造
    A = phase1(A, t, 1, cap)
    B = phase1(B, t, 1, cap)
    C = phase1(C, t, 2, cap)
    K = phase1(K, t, k, cap)
    # 2 元件判定（各链互不相干，链内下游先）
    CA, ai = chain(CA, t, A[0], cap, False)
    A = (ai, A[1], A[2])
    AC, ci = chain(AC, t, C[0], cap, False)
    C = (ci, C[1], C[2])
    if cfg.has_b:
        CB, bi = chain(CB, t, B[0], cap, False)
        B = (bi, B[1], B[2])
    else:
        CB, _ = chain(CB, t, None, cap, rel_cb)
    left = []
    if cfg.has_k:
        BK, ki = chain(BK, t, K[0], cap, False)
        K = (ki, K[1], K[2])
        newk = []
        for i, p in enumerate(KCH):
            before = p[-1]
            q, _ = chain(p, t, None, cap, rel_k[i] if i < len(rel_k) else False)
            left.append(before >= 0 and q[-1] < 0)
            newk.append(q)
        KCH = tuple(newk)
    # 3 非运输单位判定（相互之间无直接通道，先后不影响）
    sentC = None
    if C[1] > 0:
        i = pick(pollC, (CA[0] < 0, CB[0] < 0))
        if i == 0:
            CA = (t,) + CA[1:]
            sentC = 'A'
        elif i == 1:
            CB = (t,) + CB[1:]
            sentC = 'B'
        if i >= 0:
            pollC = tuple(t if j == i else pollC[j] for j in range(2))
            C = settle((C[0], C[1] - 1, C[2]), 2, cap)
    if A[1] > 0 and AC[0] < 0:
        AC = (t,) + AC[1:]
        A = settle((A[0], A[1] - 1, A[2]), 1, cap)
    if cfg.has_b and B[1] > 0 and BK[0] < 0:
        BK = (t,) + BK[1:]
        B = settle((B[0], B[1] - 1, B[2]), 1, cap)
    sentK = -1
    if cfg.has_k and K[1] > 0 and len(KCH) > 0:
        i = pick(pollK, tuple(p[0] < 0 for p in KCH))
        if i >= 0:
            KCH = tuple(((t,) + p[1:]) if j == i else p for j, p in enumerate(KCH))
            pollK = tuple(t if j == i else pollK[j] for j in range(len(KCH)))
            K = settle((K[0], K[1] - 1, K[2]), k, cap)
            sentK = i
    # 4 开始能开始的制造
    A = start(A, t)
    C = start(C, t)
    if cfg.has_b:
        B = start(B, t)
    if cfg.has_k:
        K = start(K, t)
    return (A, B, C, K, CA, AC, CB, BK, KCH, pollC, pollK), sentC, sentK, left


def phi2(st):
    """2Φ（整数）。"""
    A, B, C, K, CA, AC, CB, BK, KCH, pollC, pollK = st
    v = 2 * sum(1 for e in CA if e >= 0) + 2 * A[0] + 2 * A[1]
    v += 2 * sum(1 for e in AC if e >= 0) + 2 * C[0]
    v += 2 * (A[2] != -1) + 2 * (C[2] != -1) + C[1]
    return v


def offline(poll, rnd):
    """离线：只重排从未成功的通道的接通先后（快照求解任务第 14 行），成功记录保留。rnd 为 random.Random。"""
    nev = sorted((i for i in range(len(poll)) if poll[i] < NEVER // 2), key=lambda i: poll[i])
    rnd.shuffle(nev)
    new = list(poll)
    for r, i in enumerate(nev):
        new[i] = NEVER + r
    return tuple(new)
