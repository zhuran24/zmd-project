"""Independent review, exact interval enumeration, standard library only.

Coordinates are reconstructed algebraically, not read from the cell encoding.
Choose all possible left-axis intervals touching rows 2..4; the rest splits
into two independent equal-length interval scheduling problems.
"""
from pathlib import Path
import itertools
import json
import time
from collections import Counter
from functools import cache

OUT = Path(__file__).resolve().parent


def intersects(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def point_inside(p, r):
    return r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]


def mineral_positions(g):
    # A three-cell tile has its centre at 1 mod 3 before the gap,
    # and 2 mod 3 after it.
    return [t for t in range(1, 70) if (t < g and t % 3 == 1) or (t > g and t % 3 == 2)]


@cache
def build(lgap, bgap, kind):
    left, lower = mineral_positions(lgap), mineral_positions(bgap)
    points = [(1, y) for y in left] + [(x, 1) for x in lower]
    body = None
    bonus_points = []
    tangent = 0
    if kind:
        if lgap:
            body = (1, lgap-1, 3, lgap+1)
            ys = [lgap+2] + ([] if lgap == 3 else [lgap-2])
            bonus_points = [(x, y) for x in (2, 3) for y in ys]
        else:
            body = (bgap-1, 1, bgap+1, 3)
            xs = [bgap+2] + ([] if bgap == 3 else [bgap-2])
            bonus_points = [(x, y) for x in xs for y in (2, 3)]
        tangent = 2 - int(kind == 2 and max(lgap, bgap) == 3)
    options = []
    # Scan all legal 3x3 start coordinates along the two axes; detect the
    # mineral port it covers. This avoids source/offset generation.
    for side in (0, 1):
        for start in range(1, 68):
            r = (2, start, 4, start+2) if side == 0 else (start, 2, start+2, 4)
            vals = left if side == 0 else lower
            touched = [v for v in vals if start <= v <= start+2]
            if not touched or any(point_inside(p, r) for p in points):
                continue
            if body is not None and intersects(body, r):
                continue
            assert len(touched) == 1
            options.append((side, start, r))
    return left, lower, body, bonus_points, tangent, options


def greedy(intervals, limit):
    chosen = []
    last_end = -1
    for o in sorted(intervals, key=lambda p: p[1]):
        if o[1] > last_end:
            chosen.append(o)
            last_end = o[1] + 2
    return chosen[:max(0, limit)]


def packing(options, left_limit, lower_limit):
    near = [o for o in options if o[0] == 0 and o[1] <= 4]
    far = [o for o in options if o[0] == 0 and o[1] >= 5]
    bottom = [o for o in options if o[0] == 1]
    best = []
    # Starts 1..4, length 3: no three mutually disjoint intervals exist.
    for k in range(3):
        for chosen in itertools.combinations(near, k):
            if k > left_limit or any(intersects(u[2],v[2]) for u,v in itertools.combinations(chosen,2)):
                continue
            a = [o for o in far if all(not intersects(o[2],u[2]) for u in chosen)]
            b = [o for o in bottom if all(not intersects(o[2],u[2]) for u in chosen)]
            witness = list(chosen)+greedy(a,left_limit-k)+greedy(b,lower_limit)
            if len(witness) > len(best):
                best = witness
    return best


def calculate(lgap, bgap, kind, start=0, height=0):
    left, lower, body, bonus_points, tangent, candidates = build(lgap,bgap,kind)
    key = [lgap,bgap,kind,start,height]
    rect = (2,start,7,start+height-1) if height else None
    d = sum(start <= t < start+height for t in left) if height else 0
    if body and rect and intersects(body,rect):
        return dict(key=key,compatible=False,d=d)
    candidates = [c for c in candidates if rect is None or not intersects(c[2],rect)]
    cap_l = 22 if bgap == 3 else 23
    cap_b = 22 if lgap == 3 else 23
    witness = packing(candidates,cap_l,cap_b)
    score, chosen_bonus, free_point = len(witness), 0, None
    if kind == 2:
        for p in bonus_points:
            if rect and point_inside(p,rect):
                continue
            available = [c for c in candidates if not point_inside(p,c[2])]
            w = packing(available,cap_l,cap_b)
            if len(w)+1 > score:
                score,witness,chosen_bonus,free_point = len(w)+1,w,1,p
    # Independent geometric checking of the selected witness.
    assert all(not intersects(a[2],b[2]) for a,b in itertools.combinations(witness,2))
    return dict(key=key,compatible=True,d=d,value=46+tangent+score,
                tangent=tangent,bonus=chosen_bonus,free_point=free_point,
                options=len(candidates),chosen=[[c[0],c[2][0],c[2][1]] for c in witness])


def main():
    begin=time.monotonic()
    base,close=[],[]
    gaps=[(0,0)]+[(0,g) for g in range(3,70,3)]+[(g,0) for g in range(3,70,3)]
    for l,b in gaps:
        modes=[0] if max(l,b) in (0,69) else [0,1,2]
        for kind in modes:
            base.append(calculate(l,b,kind))
            for h in (6,7,8,9):
                for st in range(3,70-h):
                    if sum(st<=p<st+h for p in mineral_positions(l))<=2:
                        close.append(calculate(l,b,kind,st,h))
        print(f"interval encoding gaps=({l},{b}) finished",flush=True)
    ok=[r for r in close if r['compatible']]
    summary=dict(boundary_patterns=len(gaps),base_cases=len(base),
                 base_values=dict(Counter(r['value'] for r in base)),
                 close_total=len(close),close_compatible=len(ok),
                 close_invalid=len(close)-len(ok),
                 close_d=dict(Counter(r['d'] for r in ok)),
                 max_base=max(r['value'] for r in base),
                 max_close=max(r['value']+r['d'] for r in ok),
                 close_violations=[r['key'] for r in ok if r['value']+r['d']>91],
                 seconds=time.monotonic()-begin)
    (OUT/'geometry_intervals.json').write_text(json.dumps(dict(summary=summary,base=base,close=close),ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
