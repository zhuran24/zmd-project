"""复核97M 抽查：正式「采种单元不断料」在步进规则下、不含桥接器的纯带构型。只写 spot_seed2.json。
C 采种(1 株->2 种子)、A/B 种植、K 粉碎(1 株->2 粉末)，均 1 tick；CA、CB、AC、BK 都是传送带。
K 两条取货通道：一条接常收的下游，一条接每 slow 步才收一件的下游（K 下游怎样运行与该条无关）。
"""
import json, itertools
from pathlib import Path
from fractions import Fraction as Fr
from stepsim import Elem, Source, Sink, Machine, World, Item
OUT = Path(__file__).resolve().parent

def run(slow, L1=4, Lcb=3, L2=5, Lbk=3, steps=40000, nt_rule='earliest', conn=None):
    C = Machine('C', [({'P': 1}, 'S', 2, 8)])
    A = Machine('A', [({'S': 1}, 'P', 1, 8)])
    B = Machine('B', [({'S': 1}, 'P', 1, 8)])
    K = Machine('K', [({'P': 1}, 'D', 2, 8)])
    CA = Elem('CA', L1); CB = Elem('CB', Lcb); AC = Elem('AC', L2); BK = Elem('BK', Lbk)
    K1 = Elem('K1', 2); K2 = Elem('K2', 2)
    s1 = Sink('fast'); s2 = Sink('slow', lambda t: t % slow == 0)
    w = World([C, A, B, K, CA, CB, AC, BK, K1, K2, s1, s2]); w.nt_rule = nt_rule
    order = conn or ['CA', 'CB']
    for name in order:
        if name == 'CA': w.connect(C, CA)
        else: w.connect(C, CB)
    w.connect(CA, A); w.connect(CB, B); w.connect(A, AC); w.connect(AC, C); w.connect(B, BK); w.connect(BK, K)
    w.connect(K, K1); w.connect(K1, s1); w.connect(K, K2); w.connect(K2, s2)
    A.slots[0] = ['S']*50; C.slots[0] = ['P']*50
    for _ in range(steps): w.step()
    lo = steps - 8000
    e = {m.name: sum(m.cache_empty_steps[lo:]) for m in (C, A, B, K)}
    rate = {m.name: str(Fr(sum(1 for t, _ in m.starts if t >= lo)*8, 8000)) for m in (C, A, B, K)}
    # 周期性：最后 4000 步与前 4000 步的空缓存步数一致
    e2 = {m.name: sum(m.cache_empty_steps[lo-8000:lo]) for m in (C, A, B, K)}
    return dict(缓存空步=e, 前一窗缓存空步=e2, 开批率=rate, Phi起=100, L1加L2=L1+L2)

res = {}
for slow in (9, 10, 12, 16, 10**9):
    for conn in (['CA', 'CB'], ['CB', 'CA']):
        for rule in ('earliest', 'cyclic'):
            res[f'slow={slow},接通先={conn[0]},非运输出口={rule}'] = run(slow, conn=conn, nt_rule=rule)
res['对照:K两路都常收'] = run(1)
(OUT/'spot_seed2.json').write_text(json.dumps(res, ensure_ascii=False, indent=1)+'\n')
for k, v in res.items(): print(k, v['缓存空步'], v['开批率'])
