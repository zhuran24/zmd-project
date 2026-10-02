#!/usr/bin/env python3
"""复核94A：「密集结点」见证（推导92A 第4节）的两套独立复算。

编码一：本文件自写的逐步递推（不导入任何已有脚本）。
编码二：本文件自写的驱动，调用规则修订目录下的 sim2/simulator.py（只用其 Belt/Gate/
        Splitter/Merger/Source/Warehouse/World，自加 5 tick 收下上限的物品准入口）。
拓扑（与推导92A 第4节一致，坐标核对见 witness_geometry.py）：
  取货口甲→带A(16格)→准入口甲(每5tick上限1)→分流器P→{汇流器甲J1, 汇流器乙J2}
  取货口乙→带B(16格)→准入口乙(每5tick上限1)→未设条件准入口U→汇流器甲J1
  J1→回库带R1(1格)→协议核心；J2→回库带R2(2格)→协议核心
层数：R1=R2=1，J1=J2=2，P=U=3，两准入口=4，两长带=5。
两种同层先后：情形 U先（U 的送货通道先接通）、情形 P先。
分流器两出口接通先后：→J1 先、→J2 后，故第一次从 →J2 开始。
"""
import json, sys, pathlib

# ---------------- 编码一 ----------------
class S1:
    def __init__(self, u_first):
        self.t = 0
        self.u_first = u_first
        # 每个物品格: None 或 进入步
        self.A = [None] * 16; self.B = [None] * 16
        self.gA = None; self.gB = None      # 准入口物品格
        self.gA_win = None; self.gB_win = None  # 当前 5tick 窗口起点（收下第一件的步）
        self.P = None; self.U = None
        self.J1 = None; self.J2 = None
        self.R1 = [None]; self.R2 = [None, None]
        self.p_next = 1     # 分流器下一次从哪条开始：0=→J1, 1=→J2（第一次从第二条接通的开始）
        self.stock = 80000
        self.minstock = 80000
        self.log = []       # (t, 'P->J1'/'P->J2'/'U->J1')

    def ok(self, e):  # 滞留满 8 步
        return e is not None and self.t - e >= 8

    def settle(self, belt):
        moved = True
        while moved:
            moved = False
            for j in range(len(belt) - 2, -1, -1):
                if belt[j] is not None and belt[j + 1] is None and self.ok(belt[j]):
                    belt[j + 1], belt[j] = belt[j], None   # 内部前挪，进入新格重新计滞留
                    belt[j + 1] = self.t
                    moved = True

    def settle_all(self):
        for b in (self.A, self.B, self.R1, self.R2):
            self.settle(b)

    def gate_can(self, win):
        return win is None or self.t - win >= 40

    def step(self):
        t = self.t
        self.settle_all()
        # 层1：R1、R2 共同的收货单位是协议核心，R1 判定时一起判定（核心都收得下）
        for R in (self.R1, self.R2):
            if self.ok(R[-1]):
                R[-1] = None; self.stock += 1
        self.settle_all()
        # 层2：J1 先（→R1 先接通），再 J2
        if self.ok(self.J1) and self.R1[0] is None:
            self.J1 = None; self.R1[0] = t
        if self.ok(self.J2) and self.R2[0] is None:
            self.J2 = None; self.R2[0] = t
        self.settle_all()
        # 层3：P 与 U
        def judge_U():
            if self.ok(self.U) and self.J1 is None:
                self.U = None; self.J1 = t; self.log.append((t, 'U->J1'))
        def judge_P():
            if self.ok(self.P):
                for i in range(2):
                    c = (self.p_next + i) % 2
                    if c == 0 and self.J1 is None:
                        self.P = None; self.J1 = t; self.p_next = 1; self.log.append((t, 'P->J1')); break
                    if c == 1 and self.J2 is None:
                        self.P = None; self.J2 = t; self.p_next = 0; self.log.append((t, 'P->J2')); break
        if self.u_first:
            judge_U(); judge_P()
        else:
            judge_P(); judge_U()
        # 层4：准入口甲（→P 先接通），准入口乙
        if self.ok(self.gA) and self.P is None:
            self.gA = None; self.P = t
        if self.ok(self.gB) and self.U is None:
            self.gB = None; self.U = t
        # 层5：带A、带B 送进准入口（阻断时不收货）
        if self.ok(self.A[-1]) and self.gA is None and self.gate_can(self.gA_win):
            self.A[-1] = None; self.gA = t; self.gA_win = t
        if self.ok(self.B[-1]) and self.gB is None and self.gate_can(self.gB_win):
            self.B[-1] = None; self.gB = t; self.gB_win = t
        self.settle_all()
        # 非运输单位：两个仓库取货口
        for belt in (self.A, self.B):
            if belt[0] is None:
                belt[0] = t; self.stock -= 1
        self.minstock = min(self.minstock, self.stock)
        self.settle_all()
        self.t += 1

    def key(self):
        t = self.t
        def age(e):
            return None if e is None else min(8, t - e)
        def win(w):
            return None if w is None else min(40, t - w)
        return (tuple(map(age, self.A)), tuple(map(age, self.B)), age(self.gA), age(self.gB),
                win(self.gA_win), win(self.gB_win), age(self.P), age(self.U), age(self.J1), age(self.J2),
                tuple(map(age, self.R1)), tuple(map(age, self.R2)), self.p_next, self.stock)

def run1(u_first, steps=2000):
    s = S1(u_first)
    seen = {}
    while s.t < steps:
        k = s.key()
        if k in seen:
            start, period = seen[k], s.t - seen[k]
            break
        seen[k] = s.t
        s.step()
    else:
        raise RuntimeError('no cycle')
    # 再跑一个周期计数
    t0 = s.t
    n0 = len(s.log)
    for _ in range(period):
        s.step()
    cnt = {'P->J1': 0, 'P->J2': 0, 'U->J1': 0}
    for t, e in s.log[n0:]:
        cnt[e] += 1
    rate = {e: f'{c}/{period//8}' if period % 8 == 0 else f'{c*8}/{period}' for e, c in cnt.items()}
    return dict(first_repeat_start=start, period_steps=period, counts_per_period=cnt,
                rates_per_tick=rate, min_stock=s.minstock)

# ---------------- 编码二（sim2） ----------------
def run2(u_first, steps=6000, warm=2000):
    sim2 = pathlib.Path(__file__).resolve().parents[3] / '规则修订' / '2026-09-30-迟滞' / 'sim2'
    sys.path.insert(0, str(sim2))
    import simulator as S

    class WinGate(S.Gate):
        def __init__(self, name):
            super().__init__(name); self.win = None
        def can_accept(self, item, w):
            return self.cells[0] is None and (self.win is None or w.t - self.win >= 40)
        def receive(self, item, w):
            super().receive(item, w); self.win = w.t

    src1, src2 = S.Source('take1'), S.Source('take2')
    A, B = S.Belt('A', 16), S.Belt('B', 16)
    gA, gB = WinGate('gA'), WinGate('gB')
    P, U = S.Splitter('P'), S.Gate('U')
    J1, J2 = S.Merger('J1'), S.Merger('J2')
    R1, R2 = S.Belt('R1', 1), S.Belt('R2', 2)
    core = S.Warehouse('core', limit=10**9)
    # 接通时刻（推导92A 第4节的建造时刻；同一 rank 表示同时）
    if u_first:
        b = dict(J1=1, U=2, P=3, J2=4, gA=5, gB=6)
    else:
        b = dict(J1=1, P=2, J2=3, U=4, gA=5, gB=6)
    src1.connect(A, 110); src2.connect(B, 130)
    A.connect(gA, 125); B.connect(gB, 145)
    gA.connect(P, max(b['gA'], b['P'])); gB.connect(U, max(b['gB'], b['U']))
    P.connect(J1, max(b['P'], b['J1'])); P.connect(J2, max(b['P'], b['J2']))
    U.connect(J1, max(b['U'], b['J1']))
    J1.connect(R1, 100); J2.connect(R2, 101)
    R1.connect(core, 100); R2.connect(core, 102)
    nodes = [src1, src2, A, B, gA, gB, P, U, J1, J2, R1, R2, core]
    l3 = ['U', 'P'] if u_first else ['P', 'U']
    order = ['R1', 'R2', 'J1', 'J2'] + l3 + ['gA', 'gB', 'A', 'B']
    sched = dict(choices={'P': 'J1'}, order=order)
    w = S.World(nodes, sources=[src1, src2], schedule=sched)
    w.run(steps)
    cnt = {'P->J1': 0, 'P->J2': 0, 'U->J1': 0}
    for (t, kind, dst) in P.sent:
        if t >= warm:
            cnt['P->' + dst] += 1
    for (t, kind, dst) in U.sent:
        if t >= warm:
            cnt['U->' + dst] += 1
    span = steps - warm
    return dict(window_steps=span, counts=cnt,
                rates_per_tick={k: f'{v*8}/{span}' for k, v in cnt.items()}, layers=w.layers)

if __name__ == '__main__':
    res = {}
    for name, uf in (('U先', True), ('P先', False)):
        r1 = run1(uf)
        r2 = run2(uf)
        # 比对：编码二窗口 4000 步 = 50 个 80 步周期
        span = r2['window_steps']
        agree = all(r2['counts'][k] * r1['period_steps'] == r1['counts_per_period'][k] * span for k in r2['counts'])
        res[name] = dict(encoding1=r1, encoding2=r2, rates_agree=agree)
    pathlib.Path('witness_n06.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))
