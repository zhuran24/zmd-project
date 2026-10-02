"""复核97M：抽查正式「专用进路下缓存格不空的传递」（含桥接器一轴）在临时收货下按整单位读法的反例，补跑 R2 正常速度。
只读调用本席 stepsim / dyn_checks 中的 crossing 构型（复制构造，不改原文件）。"""
import json
from fractions import Fraction as Fr
from pathlib import Path
from stepsim import Elem, Source, Sink, Machine, World
OUT = Path(__file__).resolve().parent

def crossing(mode, slow, steps=6000):
    Y1 = Source('Y1', 'o'); Y2 = Source('Y2', 'q')
    E1 = Elem('E1', 2); Kh = Elem('K.h', 1, unit='K'); E2 = Elem('E2', 2); K2h = Elem('K2.h', 1, unit='K2'); E3 = Elem('E3', 2)
    F1 = Elem('F1', 2); Kv = Elem('K.v', 1, unit='K'); F2 = Elem('F2', 2)
    X1 = Machine('X1', [({'o': 1}, 'p', 1, 8)]); ob = Elem('ob', 1); k1 = Sink('k1')
    X2 = Machine('X2', [({'q': 1}, 'r', 1, 8 * slow)]); ob2 = Elem('ob2', 1); k2 = Sink('k2')
    units = [Y1, Y2, E1, Kh, E2, K2h, E3, F1, Kv, F2, X1, ob, k1, X2, ob2, k2]
    w = World(units, unit_mode=mode)
    w.connect(Y1, E1); w.connect(E1, Kh); w.connect(Kh, E2); w.connect(E2, K2h); w.connect(K2h, E3); w.connect(E3, X1)
    w.connect(X1, ob); w.connect(ob, k1)
    w.connect(Y2, F1); w.connect(F1, Kv); w.connect(Kv, F2); w.connect(F2, X2); w.connect(X2, ob2); w.connect(ob2, k2)
    for _ in range(steps): w.step()
    ce = X1.cache_empty_steps[1000:]
    got = [t for t, _ in k1.got if t >= 1000]
    return dict(cache_empty_steps=sum(ce), steps=len(ce), X1每tick=str(Fr(len(got) * 8, steps - 1000)))

res = {}
for mode in ('axis', 'unit'):
    for d in (1, 2, 5):   # X2 为配方 d tick、每批 1 件原料的真实制造单位
        res[f'{mode},X2配方{d}tick'] = crossing(mode, d)
(OUT / 'cross_extra.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n')
print(json.dumps(res, ensure_ascii=False))
