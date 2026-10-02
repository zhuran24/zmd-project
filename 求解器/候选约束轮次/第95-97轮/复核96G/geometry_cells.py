"""Independent review: generate physical cells, optimize their conflicts (one worker).

No derivation or historical program is imported. This is a necessary local
relaxation, not a factory simulator. All writes stay beside this file.
"""
from pathlib import Path
import hashlib
import json
import time
from collections import Counter, defaultdict
from functools import cache
from ortools.sat.python import cp_model

OUT = Path(__file__).resolve().parent


def tiles_for_gap(gap, vertical):
    tiles = []
    for start in list(range(0, gap, 3)) + list(range(gap + 1, 70, 3)):
        tiles.append({(0, t) if vertical else (t, 0) for t in range(start, start + 3)})
    assert len(tiles) == 23
    return tiles


def cells(x, y, w=3, h=3):
    return {(i, j) for i in range(x, x + w) for j in range(y, y + h)}


@cache
def prepare(gl, gb, mode):
    warehouse = tiles_for_gap(gl, True) + tiles_for_gap(gb, False)
    occupied = set().union(*warehouse)
    assert len(occupied) == 138
    sources = []
    for side, ts in enumerate((warehouse[:23], warehouse[23:])):
        for t in ts:
            if side == 0:
                p = (1, sorted(y for x, y in t)[1])
            else:
                p = (sorted(x for x, y in t)[1], 1)
            sources.append((side, p))
    ore = {p for side, p in sources}
    assert len(ore) == 46
    fixed = set()
    extra = []
    tangent = 0
    if mode:
        if 0 < gl < 69:
            fixed = cells(1, gl - 1)
            faces = (gl + 2,) if gl == 3 else (gl - 2, gl + 2)
            extra = [(x, y) for y in faces for x in (2, 3)]
        else:
            fixed = cells(gb - 1, 1)
            faces = (gb + 2,) if gb == 3 else (gb - 2, gb + 2)
            extra = [(x, y) for x in faces for y in (2, 3)]
        tangent = 1 if mode == 2 and 3 in (gl, gb) else 2
    options = []
    for source_index, (side, (x, y)) in enumerate(sources):
        for offset in range(3):
            bx, by = (2, y - offset) if side == 0 else (x - offset, 2)
            shape = cells(bx, by)
            if min(bx, by) < 0 or bx + 3 > 70 or by + 3 > 70:
                continue
            if shape & (occupied | ore | fixed):
                continue
            options.append((source_index, side, bx, by, shape))
    return sources, fixed, extra, tangent, options


def solve(gl, gb, mode, b=0, h=0):
    sources, fixed, extra, tangent, opts = prepare(gl, gb, mode)
    rect = cells(2, b, 6, h) if h else set()
    d = sum(b <= y < b + h for side, (x, y) in sources if side == 0) if h else 0
    key = [gl, gb, mode, b, h]
    if rect & fixed:
        return dict(key=key, compatible=False, d=d)
    opts = [o for o in opts if not (o[4] & rect)]
    m = cp_model.CpModel()
    v = [m.new_bool_var(f"c{i}") for i in range(len(opts))]
    cover, by_source, by_side = defaultdict(list), defaultdict(list), defaultdict(list)
    for i, (src, side, x, y, shape) in enumerate(opts):
        by_source[src].append(v[i])
        by_side[side].append(v[i])
        for p in shape:
            cover[p].append(v[i])
    for group in list(cover.values()) + list(by_source.values()):
        if len(group) > 1:
            m.add(sum(group) <= 1)
    if gl == 3:
        m.add(sum(by_side[1]) <= 22)
    if gb == 3:
        m.add(sum(by_side[0]) <= 22)
    bonus = m.new_bool_var("weighted_direction")
    usable = []
    if mode == 2:
        for p in extra:
            if p in rect:
                continue
            z = m.new_bool_var(f"free_{p}")
            for machine in cover[p]:
                m.add(z + machine <= 1)
            usable.append(z)
    m.add(bonus <= sum(usable))
    m.maximize(sum(v) + bonus)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 1
    s.parameters.max_time_in_seconds = 10
    status = s.solve(m)
    if status != cp_model.OPTIMAL:
        raise RuntimeError((key, s.status_name(status)))
    chosen = [[o[1], o[2], o[3]] for i, o in enumerate(opts) if s.value(v[i])]
    value = 46 + tangent + round(s.objective_value)
    return dict(key=key, compatible=True, d=d, value=value,
                tangent=tangent, bonus=s.value(bonus), options=len(opts),
                bound=46+tangent+round(s.best_objective_bound),
                chosen=chosen)


def run():
    begin = time.monotonic()
    base, close = [], []
    pairs = [(l, b) for l in range(0, 70, 3) for b in range(0, 70, 3) if min(l, b) == 0]
    for gl, gb in pairs:
        modes = (0, 1, 2) if 0 < max(gl, gb) < 69 else (0,)
        for mode in modes:
            base.append(solve(gl, gb, mode))
            for h in range(6, 10):
                for b in range(3, 70 - h):
                    ore_rows = [p[1] for side, p in prepare(gl, gb, mode)[0] if side == 0]
                    if sum(b <= y < b+h for y in ore_rows) <= 2:
                        close.append(solve(gl, gb, mode, b, h))
        print(f"cell encoding gaps=({gl},{gb}) finished", flush=True)
    compatible = [r for r in close if r['compatible']]
    summary = dict(boundary_patterns=len(pairs), base_cases=len(base),
                   base_values=dict(Counter(r['value'] for r in base)),
                   close_total=len(close), close_compatible=len(compatible),
                   close_invalid=len(close)-len(compatible),
                   close_d=dict(Counter(r['d'] for r in compatible)),
                   max_base=max(r['value'] for r in base),
                   max_close=max(r['value']+r['d'] for r in compatible),
                   close_violations=[r['key'] for r in compatible if r['value']+r['d']>91],
                   seconds=time.monotonic()-begin)
    payload = dict(summary=summary, base=base, close=close)
    (OUT/'geometry_cells.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))+'\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run()
