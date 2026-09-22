#!/usr/bin/env python3
"""用报告自己的 boundary_joint.build（只在内存中建模，不写报告目录）对指定位置去掉
区间 DP 切割、放开 P=10..12 求解，结果写到本目录 results/。

用法：python their_boundary_nocut.py W21H53_x49y14 [秒数] [worker]
"""
import copy, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ortools.sat.python import cp_model
from boundary_joint import build  # noqa: E402

tag = sys.argv[1]
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 300
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
pos = {p['id']: p for p in json.loads((HERE.parent / 'positions.json').read_text())['candidates']}
p = copy.deepcopy(pos[tag])
p['allowed_P'] = [10, 11, 12]
p['branches'] = []
m, meta = build(p)
s = cp_model.CpSolver()
s.parameters.max_time_in_seconds = seconds
s.parameters.num_workers = workers
s.parameters.random_seed = 1
t0 = time.monotonic()
st = s.solve(m)
out = dict(id=tag, model='report boundary_joint.build, allowed_P=[10,11,12], branches=[] (no DP cuts)',
           status=s.status_name(st), wall=round(s.wall_time, 2), workers=workers, seed=1,
           fingerprint=m.model_stats().splitlines()[0])
(HERE / 'results' / f'their_boundary_nocut_{tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False))
