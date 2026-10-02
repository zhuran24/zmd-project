#!/usr/bin/env python3
"""两个按读法构造的局部算例（只说明 D 组 150 下界依赖哪些离线读法）：
甲：离线清空 C 取货侧成功记录时，Φ 降到 Φ(s)−1，低于 min(Φ(s)−1/2, L1+L2+150)。
乙：离线清空物品来源记录时，同轴相邻桥中的货倒回上游桥并永久卡死，Φ 远低于下界。
两例都同时给出“不清空”（推导席读法）的对照。"""
from __future__ import annotations
import json, random
from seedunit import Unit, SEED, PLANT, POWDER
from engine import Item


def case_reset_poll(reset):
    rng = random.Random(1)
    segs = {p: [('belt', 1)] for p in ('CA', 'AC', 'CB', 'BK')}
    u = Unit(rng, k=2, n_out=0, segs=segs)
    w = u.w
    C, A, B, K = u.C, u.A, u.B, u.K
    C.slots[0] = [None, 0]; C.cache = None; C.out_kind, C.out_n = SEED, 2
    A.slots[0] = [SEED, 50]; A.out_kind, A.out_n = PLANT, 49; A.cache = ('run', 8)
    B.slots[0] = [None, 0]; B.out_kind, B.out_n = None, 0; B.cache = None
    K.slots[0] = [None, 0]; K.cache = None
    ca = u.paths['CA'][0][0]
    ca.cells[0] = Item(SEED, -1, 'C')
    phi_s = u.phi2()
    bound = min(phi_s - 1, 2 * (u.L1 + u.L2 + 150))
    units = w.build_units()
    order = ['C', 'CB.b0#0', 'CA.b0#0'] + [x for x in units if x not in ('C', 'CB.b0#0', 'CA.b0#0')]
    w.offline_build(order=order)
    trace = []
    for t in range(40):
        if t == 4:
            w.offline_build(order=order, reset_poll=reset)
        before = C.last_success.copy()
        w.step()
        trace.append(u.phi2())
    return dict(reset_poll=reset, phi_s2=phi_s, bound2=bound, min_phi2=min(trace),
                first_violation_step=next((i for i, x in enumerate(trace) if x < bound), None),
                phi2_trace=trace[:12])


def case_reset_prev(reset):
    rng = random.Random(2)
    segs = {'CA': [('belt', 1), ('br', 2)], 'AC': [('belt', 2)], 'CB': [('belt', 2)], 'BK': [('belt', 2)]}
    u = Unit(rng, k=2, n_out=2, segs=segs)
    w = u.w
    C, A, B, K = u.C, u.A, u.B, u.K
    els = u.paths['CA'][0]
    U, P, Q = els
    Q.item = Item(SEED, -20, P.unit)          # Q 中的货正向来自 P
    P.item = None
    U.cells[0] = None
    A.slots[0] = [SEED, 50]; A.out_kind, A.out_n = PLANT, 50; A.cache = ('done',)
    for e in u.paths['AC'][0]:
        e.cells = [Item(PLANT, -20, None) for _ in e.cells]
    C.slots[0] = [PLANT, 50]; C.cache = None; C.out_kind, C.out_n = None, 0
    B.slots[0] = [None, 0]; B.out_kind, B.out_n = None, 0; B.cache = None
    phi_s = u.phi2()
    bound = min(phi_s - 1, 2 * (u.L1 + u.L2 + 150))
    units = w.build_units()
    # P、Q 先于 A 建成：Q 的两条送货通道中 Q→P 先接通，轮询从它开始
    head = ['C', 'CA.b0#0', P.unit, Q.unit, 'A']
    order = head + [x for x in units if x not in head]
    w.offline_build(order=order, reset_prev=reset)
    trace = []
    for t in range(4000):
        w.step()
        trace.append(u.phi2())
    return dict(reset_prev=reset, L1=u.L1, L2=u.L2, phi_s2=phi_s, bound2=bound, min_phi2=min(trace),
                final_phi2=trace[-1],
                first_violation_step=next((i for i, x in enumerate(trace) if x < bound), None),
                P_item_prev=(P.item.prev if P.item else None), Q_item=(Q.item is not None))


if __name__ == '__main__':
    out = dict(甲=[case_reset_poll(False), case_reset_poll(True)],
               乙=[case_reset_prev(False), case_reset_prev(True)])
    print(json.dumps(out, ensure_ascii=False, indent=1))
