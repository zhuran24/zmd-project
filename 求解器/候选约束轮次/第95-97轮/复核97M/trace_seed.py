"""复核97M：追踪 spot_seed 按轴读法、慢下游每 9 步收一件时 A 缓存为空的来由（只读调用 stepsim）。"""
import sys, json
from pathlib import Path
res = {}
from stepsim import Elem, Sink, Machine, World
def build(slow, mode='axis', with_bridges=True):
    C = Machine('C', [({'P': 1}, 'S', 2, 8)]); A = Machine('A', [({'S': 1}, 'P', 1, 8)])
    B = Machine('B', [({'S': 1}, 'P', 1, 8)]); K = Machine('K', [({'P': 1}, 'D', 2, 8)])
    CA = Elem('CA', 4); CB = Elem('CB', 3); BK = Elem('BK', 3)
    F1 = Elem('F1', 2); F2 = Elem('F2', 2); K2 = Elem('K2', 2)
    sink_slow = Sink('slow', lambda t: t % slow == 0); sink = Sink('fast')
    if with_bridges:
        E1 = Elem('E1', 3); Xh = Elem('X.h', 1, unit='X'); E2 = Elem('E2', 3); Yh = Elem('Y.h', 1, unit='Y'); E3 = Elem('E3', 3)
        Xv = Elem('X.v', 1, unit='X')
        AC = [E1, Xh, E2, Yh, E3]; Fp = [F1, Xv, F2]
    else:
        AC = [Elem('AC', 11)]; Fp = [Elem('F', 5)]
    units = [C, A, B, K, CA, CB, BK, *AC, *Fp, K2, sink_slow, sink]
    w = World(units, unit_mode=mode)
    w.connect(C, CA); w.connect(CA, A); w.connect(C, CB); w.connect(CB, B)
    prev = A
    for e in AC: w.connect(prev, e); prev = e
    w.connect(prev, C)
    w.connect(B, BK); w.connect(BK, K)
    prev = K
    for e in Fp: w.connect(prev, e); prev = e
    w.connect(prev, sink_slow)
    w.connect(K, K2); w.connect(K2, sink)
    A.slots[0] = ['S']*50; C.slots[0] = ['P']*50
    return w, dict(A=A, B=B, C=C, K=K)
for wb in (True, False):
  for slow in (9, 10, 8):
    w, m = build(slow, with_bridges=wb)
    for _ in range(40000): w.step()
    lo = 32000
    emp = {k: sum(v.cache_empty_steps[lo:]) for k, v in m.items()}
    st = {k: (len(v.slots[0]), len(v.out)) for k, v in m.items()}
    row = dict(缓存空的步末数=emp, 统计步数=40000-lo, 存货与取货件数=st, C开批数=sum(1 for t,_ in m['C'].starts if t>=lo))
    res[f"{'AC与K出路含桥接器' if wb else '全为传送带'},K另一出路每{slow}步收一件"] = row
    print(row)
Path(__file__).with_name('trace_seed.json').write_text(json.dumps(res, ensure_ascii=False, indent=1)+'\n')
