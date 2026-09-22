#!/usr/bin/env python3
"""对报告中 22 个候选位置逐一求 S=16P-2J+X+Y 的最小值（弱版与 forbid_edge0 版）。"""
import json, sys
from pathlib import Path
from strip_model import run, HERE
cands = [(49, b, 21, 53) for b in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17)]
cands += [(a, 49, 53, 21) for a in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17)]
mode = sys.argv[1] if len(sys.argv) > 1 else 'weak'
rows = []
for R in cands:
    tag = f"minS_{mode}_W{R[2]}H{R[3]}_x{R[0]}y{R[1]}"
    out = run(R, [10, 11, 12], 300, 6, forbid_edge0=(mode == 'edge0'), minimize='S', tag=tag)
    S = 16 * out['P'] - 2 * out['J'] + out['X'] + out['Y'] if 'X' in out else None
    row = dict(rect=R, status=out['status'], S_min=S, bound=out.get('bound'), P=out.get('P'), J=out.get('J'),
               X=out.get('X'), Y=out.get('Y'), wall=out['wall'])
    rows.append(row)
    print(json.dumps(row), flush=True)
(HERE / 'results' / f'scan_{mode}.json').write_text(json.dumps(rows, indent=1))
