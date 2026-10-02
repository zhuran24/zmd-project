"""95G encoding B: exact interval scheduling with corner subset enumeration.

No solver, no imports of A or of previous scripts. The left-normal bodies
are in columns 2..4; bottom-normal bodies in rows 2..4. Only bottom bodies
starting at x<=4 can cross a left body. Enumerate those few bodies, then
solve two unweighted interval scheduling problems exactly by earliest end.
"""
import argparse
import itertools
import json
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent


def centers(k):
    return tuple(3*i+1+(i >= k) for i in range(23))


def overlaps(r, s):
    return r[0] < s[0]+s[2] and s[0] < r[0]+r[2] and r[1] < s[1]+s[3] and s[1] < r[1]+r[3]


def contains(r, p):
    return r[0] <= p[0] < r[0]+r[2] and r[1] <= p[1] < r[1]+r[3]


def intervals(items, axis):
    selected = []
    next_start = -1
    for r in sorted(items, key=lambda r: r[axis]+3):
        if r[axis] >= next_start:
            selected.append(r)
            next_start = r[axis]+3
    return selected


def pack(options, kl, kb):
    left = [r for r in options if r[4] == 'L']
    bottom = [r for r in options if r[4] == 'B']
    crossing = [r for r in bottom if r[0] <= 4]
    distant = [r for r in bottom if r[0] > 4]
    best, witness = -1, None
    for bits in itertools.product([False, True], repeat=len(crossing)):
        chosen = [r for r, yes in zip(crossing, bits) if yes]
        if any(overlaps(x, y) for x, y in itertools.combinations(chosen, 2)):
            continue
        l_ok = [r for r in left if not any(overlaps(r, s) for s in chosen)]
        b_ok = [r for r in distant if not any(overlaps(r, s) for s in chosen)]
        l_sel = intervals(l_ok, 1)
        b_sel = intervals(b_ok, 0)
        if kb == 1:
            l_sel = l_sel[:22]
        if kl == 1:
            b_sel = b_sel[:max(0, 22-len(chosen))]
        all_selected = chosen+l_sel+b_sel
        if len(all_selected) > best:
            best, witness = len(all_selected), all_selected
    assert best >= 0
    return best, witness


def optimize(kl, kb, mode, b=0, h=0):
    left, bottom = centers(kl), centers(kb)
    ore = [(1, y) for y in left]+[(x, 1) for x in bottom]
    g = 3*max(kl, kb)
    vertical = kl > 0
    fixed = (1, g-1, 3, 3) if vertical else (g-1, 1, 3, 3)
    if mode == 0:
        fixed = None
    rect = (2, b, 6, h) if h else None
    if fixed and rect and overlaps(fixed, rect):
        return None
    options = []
    # Scan possible body positions instead of scanning ports and offsets.
    for axis in ['L', 'B']:
        port_positions = left if axis == 'L' else bottom
        for start in range(1, 68):
            relevant = [v for v in port_positions if start <= v < start+3]
            if len(relevant) != 1:
                continue
            body = (2, start, 3, 3, axis) if axis == 'L' else (start, 2, 3, 3, axis)
            if any(contains(body, p) for p in ore):
                continue
            if fixed and overlaps(body, fixed) or rect and overlaps(body, rect):
                continue
            options.append(body)
    tangent = [0, 2, 1 if g == 3 else 2][mode]
    count, witness = pack(options, kl, kb)
    score, weight = 46+tangent+count, 0
    if mode == 2:
        for edge in [g-2, g+2]:
            if g == 3 and edge == 1:
                continue
            for coordinate in [2, 3]:
                free = (coordinate, edge) if vertical else (edge, coordinate)
                if free in ore or contains(fixed, free) or rect and contains(rect, free):
                    continue
                normal, selected = pack([r for r in options if not contains(r, free)], kl, kb)
                if 46+tangent+normal+1 > score:
                    score, witness, weight = 46+tangent+normal+1, selected, 1
    assert all(not overlaps(x, y) for x, y in itertools.combinations(witness, 2))
    return {'bound': score, 'options': len(options), 'status': 'EXACT',
            'selected': [list(r) for r in witness], 'tangent': tangent, 'weight': weight}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-only', action='store_true')
    args = parser.parse_args()
    start = time.monotonic()
    baseline, scope, incompatible = [], [], []
    for kl in range(24):
        for kb in range(24):
            if kl and kb:
                continue
            modes = [0, 1, 2] if 0 < max(kl, kb) < 23 else [0]
            for mode in modes:
                baseline.append({'key': [kl*3, kb*3, mode], **optimize(kl, kb, mode)})
            if args.base_only:
                continue
            for h in range(6, 10):
                for b in range(3, 70-h):
                    d = len(set(centers(kl)) & set(range(b, b+h)))
                    if d > 2:
                        continue
                    for mode in modes:
                        ans = optimize(kl, kb, mode, b, h)
                        key = [3*kl, 3*kb, mode, b, h]
                        if ans is None:
                            incompatible.append(key)
                        else:
                            scope.append(key+[ans['bound'], d, ans['bound']+d])
            print(json.dumps({'left_gap': kl*3, 'bottom_gap': kb*3, 'completed': len(scope),
                              'seconds': round(time.monotonic()-start, 3)}), flush=True)
    result = {'encoding': 'exact interval scheduling and corner subsets; no solver',
              'base_only': args.base_only, 'baseline': baseline, 'near': scope,
              'incompatible': incompatible, 'seconds': time.monotonic()-start,
              'baseline_maximum': max(r['bound'] for r in baseline),
              'near_maximum': max((r[-1] for r in scope), default=None)}
    path = OUT / ('geometry_b_base.json' if args.base_only else 'geometry_b.json')
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'baseline': len(baseline), 'near': len(scope), 'incompatible': len(incompatible),
                      'maxima': [result['baseline_maximum'], result['near_maximum']]}))


if __name__ == '__main__':
    main()
