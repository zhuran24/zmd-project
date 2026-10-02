"""95G encoding A: cell sets and single-thread CP-SAT.

Only a necessary local relaxation. Selected blocks are not playable layouts.
This file does not import earlier rounds or the independent encoding B.
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
from ortools.sat.python import cp_model

OUT = Path(__file__).resolve().parent


def cells(x, y, w=3, h=3):
    return frozenset((i, j) for i in range(x, x+w) for j in range(y, y+h))


def sources(g):
    # Tile the actual 70-cell edge with 23 three-cell ports and one gap.
    pos, result = 0, []
    while pos < 70:
        if pos == g:
            pos += 1
        else:
            result.append(pos+1)
            pos += 3
    assert pos == 70 and len(result) == 23
    return result


def optimize(gl, gb, mode, b=0, h=0):
    src = [(1, y) for y in sources(gl)] + [(x, 1) for x in sources(gb)]
    ore = set(src)
    assert len(ore) == 46
    g = max(gl, gb)
    on_left = gl != 0
    fixed = cells(1, g-1) if on_left else cells(g-1, 1)
    if mode == 0:
        fixed = frozenset()
    rect = cells(2, b, 6, h) if h else frozenset()
    if fixed & rect:
        return None
    forbidden = ore | fixed | rect
    options = []
    for i, (x, y) in enumerate(src):
        for shift in range(3):
            ax, ay = (2, y-shift) if i < 23 else (x-shift, 2)
            footprint = cells(ax, ay)
            if min(ax, ay) < 1 or max(ax, ay) > 67 or footprint & forbidden:
                continue
            options.append((i, ax, ay, footprint))

    model = cp_model.CpModel()
    z = [model.new_bool_var(f'z{k}') for k in range(len(options))]
    at_cell, at_source = {}, {}
    for k, (src_id, ax, ay, footprint) in enumerate(options):
        at_source.setdefault(src_id, []).append(z[k])
        for point in footprint:
            at_cell.setdefault(point, []).append(z[k])
    for vs in list(at_cell.values()) + list(at_source.values()):
        model.add(sum(vs) <= 1)
    if gl == 3:
        model.add(sum(z[k] for k, opt in enumerate(options) if opt[0] >= 23) <= 22)
    if gb == 3:
        model.add(sum(z[k] for k, opt in enumerate(options) if opt[0] < 23) <= 22)
    tangent = 0 if mode == 0 else (1 if mode == 2 and g == 3 else 2)
    weight = 0
    if mode == 2:
        weight = model.new_bool_var('weight_upper')
        witnesses = []
        for end in [g-2, g+2]:
            if g == 3 and end == 1:
                continue
            for cross in [2, 3]:
                point = (cross, end) if on_left else (end, cross)
                if point in forbidden:
                    continue
                v = model.new_bool_var(f'free{point}')
                for blocker in at_cell.get(point, []):
                    model.add(v + blocker <= 1)
                witnesses.append(v)
        model.add(weight <= sum(witnesses))
    model.maximize(46 + tangent + sum(z) + weight)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 20
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL, (gl, gb, mode, b, h, solver.status_name(status))
    val = round(solver.objective_value)
    assert abs(val-solver.best_objective_bound) < 1e-7
    chosen = [options[k] for k in range(len(options)) if solver.value(z[k])]
    # Check integer primal output without using the solver's constraint matrix.
    used = set()
    for _, ax, ay, footprint in chosen:
        assert not used & footprint and not forbidden & footprint
        used.update(footprint)
    return {'bound': val, 'selected': [list(o[:3]) for o in chosen],
            'options': len(options), 'status': 'OPTIMAL', 'tangent': tangent,
            'weight': solver.value(weight) if mode == 2 else 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-only', action='store_true')
    args = parser.parse_args()
    start = time.monotonic()
    baseline, scope, incompatible = [], [], []
    layouts = [(l, d) for l in range(0, 70, 3) for d in range(0, 70, 3) if not l*d]
    for gl, gb in layouts:
        modes = [0, 1, 2] if 0 < max(gl, gb) < 69 else [0]
        for mode in modes:
            baseline.append({'key': [gl, gb, mode], **optimize(gl, gb, mode)})
        if args.base_only:
            continue
        for h in range(6, 10):
            for b in range(3, 70-h):
                d = sum(b <= y < b+h for y in sources(gl))
                if d > 2:
                    continue
                for mode in modes:
                    ans = optimize(gl, gb, mode, b, h)
                    key = [gl, gb, mode, b, h]
                    if ans is None:
                        incompatible.append(key)
                    else:
                        scope.append(key + [ans['bound'], d, ans['bound']+d])
        print(json.dumps({'left_gap': gl, 'bottom_gap': gb, 'completed': len(scope),
                          'seconds': round(time.monotonic()-start, 3)}), flush=True)
    result = {'encoding': 'cell sets / CP-SAT; one worker', 'base_only': args.base_only,
              'baseline': baseline, 'near_columns': ['left_gap', 'bottom_gap', 'mode',
              'bottom', 'height', 'N_plus_w', 'd', 'N_plus_w_plus_d'],
              'near': scope, 'incompatible': incompatible, 'seconds': time.monotonic()-start,
              'baseline_maximum': max(r['bound'] for r in baseline),
              'near_maximum': max((r[-1] for r in scope), default=None)}
    path = OUT / ('geometry_a_base.json' if args.base_only else 'geometry_a.json')
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'baseline': len(baseline), 'near': len(scope), 'incompatible': len(incompatible),
                      'maxima': [result['baseline_maximum'], result['near_maximum']],
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
