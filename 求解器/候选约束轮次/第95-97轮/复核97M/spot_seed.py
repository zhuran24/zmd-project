"""复核97M 抽查：正式「采种单元不断料」（进路可含桥接器一轴）在临时收货规则下，
桥接器“按整个单位”带动时的反例构型；按轴读时作对照。只写 spot_seed.json。
构型：C 采种(1 株->2 种子)、A/B 种植(1 种子->1 株)、K 粉碎(1 株->2 粉末)，均 1 tick。
CA、CB、BK 为传送带；AC = E1 -> 桥接器 X 的横轴 -> E2 -> 单轴桥接器 Y -> E3 -> C。
K 的一条取货通道 F1 -> X 的纵轴 -> F2 -> 收货很慢的下游（K 下游怎样运行与该条无关）。
"""
import json
from pathlib import Path
from fractions import Fraction as Fr
from stepsim import Elem, Source, Sink, Machine, World, Item
OUT = Path(__file__).resolve().parent

def run(mode, slow, steps=12000, cap=False):
    C = Machine('C', [({'P': 1}, 'S', 2, 8)])
    A = Machine('A', [({'S': 1}, 'P', 1, 8)])
    B = Machine('B', [({'S': 1}, 'P', 1, 8)])
    K = Machine('K', [({'P': 1}, 'D', 2, 8)])
    CA = Elem('CA', 4); CB = Elem('CB', 3); BK = Elem('BK', 3)
    E1 = Elem('E1', 3); Xh = Elem('X.h', 1, unit='X'); E2 = Elem('E2', 3); Yh = Elem('Y.h', 1, unit='Y'); E3 = Elem('E3', 3)
    F1 = Elem('F1', 2); Xv = Elem('X.v', 1, unit='X'); F2 = Elem('F2', 2)
    K2 = Elem('K2', 2)
    sink_slow = Sink('slow', lambda t: t % slow == 0); sink = Sink('fast')
    units = [C, A, B, K, CA, CB, BK, E1, Xh, E2, Yh, E3, F1, Xv, F2, K2, sink_slow, sink]
    w = World(units, unit_mode=mode); w.trigger_capacity = cap
    w.connect(C, CA); w.connect(CA, A); w.connect(C, CB); w.connect(CB, B)
    w.connect(A, E1); w.connect(E1, Xh); w.connect(Xh, E2); w.connect(E2, Yh); w.connect(Yh, E3); w.connect(E3, C)
    w.connect(B, BK); w.connect(BK, K)
    w.connect(K, F1); w.connect(F1, Xv); w.connect(Xv, F2); w.connect(F2, sink_slow)
    w.connect(K, K2); w.connect(K2, sink)
    # 起态：A 存货 50 种子、C 存货 50 株，其余空（Φ=100 >= L1+L2+5/2）
    A.slots[0] = ['S']*50; C.slots[0] = ['P']*50
    L = w.layers()
    for _ in range(steps): w.step()
    lo = 32000
    def empties(m): return sum(m.cache_empty_steps[lo:])
    return dict(layers={e.name: L[e] for e in w.elems},
                C缓存空步=empties(C), A缓存空步=empties(A), B缓存空步=empties(B), K缓存空步=empties(K),
                C开批率=str(Fr(sum(1 for t, _ in C.starts if t >= lo)*8, steps-lo)),
                C存货=len(C.slots[0]))

res = {}
for cap in (False, True):
    for mode in ('axis', 'unit'):
        for slow in (9, 10**9):
            res[f'{mode},慢下游每{slow}步收一件,触发{"要求收得下" if cap else "只要成熟"}'] = run(mode, slow, 40000, cap)
(OUT/'spot_seed.json').write_text(json.dumps(res, ensure_ascii=False, indent=1)+'\n')
print(json.dumps(res, ensure_ascii=False))
