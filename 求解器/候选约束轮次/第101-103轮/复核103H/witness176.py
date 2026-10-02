#!/usr/bin/env python3
"""复核103H：176 加强只能用于实际运行过的完整步末——准备截面反例（两套编码）。
L1=2、L2=5；准备截面：CA、AC 满（货已成熟），A 存 50、取 50、缓存已做好；C 存 50、取 48、缓存刚放进一批（还要 8 步）。
Φ(s)=L+176。CA 因 A 存货满而不动，C 两次只能送 CB（第 1、9 步），Φ 降到 L+175。
若 s 是实际运行过的步末，C 不可能存货 50 而缓存还剩 8 步，这一例就不出现。不需要离线。"""
import json, sys
from fractions import Fraction as Fr
import plant

cfg = dict(k=2, n=0, L=[2, 5, 1, 1], Bmode='adv')
st = {'belts': {'CA': [-5, -5], 'AC': [-7, -10, -2, -2, -6], 'CB': [None]},
      'm': {'C': {'inp': 50, 'out': 48, 'cache': 8}, 'A': {'inp': 50, 'out': 50, 'cache': 'done'}},
      'connC': [1, 0], 'lastC': [None, -15.1], 'connK': [], 'lastK': []}
A = plant.EngA(cfg, st)
B = plant.EngB(cfg, {'belts': A.belts, 'm': A.m, 'connC': A.connC, 'lastC': A.lastC, 'connK': [], 'lastK': []}, 0)
L = 7
phis = A.phi()
traj = []; ok = True
for t in range(1, 30):
    B.tick_clock()
    s = A.step(t, {'sinkB': True}); B.step({'sinkB': True})
    if A.snapshot(t) != B.snapshot(): ok = False
    traj.append((t, s.get('C'), str(A.phi())))
out = dict(phi_s=str(phis), L=L, L_plus_176=L + 176, sends=[(t, c) for t, c, _ in traj if c is not None],
           phi_min=str(min(Fr(p) for _, _, p in traj)), bound150=str(min(phis - Fr(1, 2), L + 150)),
           bound176_if_misused=str(min(phis - Fr(1, 2), L + 176)), dual_ok=ok)
json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
print(out)
