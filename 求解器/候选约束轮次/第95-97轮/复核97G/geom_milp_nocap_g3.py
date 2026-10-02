#!/usr/bin/env python3
"""编码甲补算：g=3 两种边带的放缺格机分支，不加“封住条带”限制（较松模型），只在矩形离带允许的近边域内。"""
import json, os, geom_milp as A
out = []
mx = 0
for gl, gb in [(3, 0), (0, 3)]:
    ol, ob, q = A.border_layout(gl, gb); O = set(ol) | set(ob)
    opts = A.normal_options(ol, ob, O)
    G, side, g = A.gap_unit(gl, gb)
    lys = set(y for _, y in ol)
    v, _ = A.solve_count(opts, G)
    out.append({'gl': gl, 'gb': gb, 'base_unit_nocap': 46 + v + 2})
    mx = max(mx, 46 + v + 2)
    for H in range(6, 10):
        for b in range(3, 70 - H):
            d = sum(1 for y in range(b, b + H) if y in lys)
            if d > 2:
                continue
            R = A.body(2, b, 6, H)
            if G & R:
                continue
            v, _ = A.solve_count(opts, G | R)
            val = 46 + v + 2 + d
            out.append({'gl': gl, 'gb': gb, 'b': b, 'H': H, 'd': d, 'unit_nocap': val})
            mx = max(mx, val)
json.dump({'max': mx, 'rows': out}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geom_milp_nocap_g3.json'), 'w'))
print('max', mx, 'rows', len(out))
