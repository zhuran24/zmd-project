#!/usr/bin/env python3
"""异源核查：独立重做 1113 位置清单，并用 strip_model 对全部位置做可行性判定。

1) 从零枚举 21x53 两个朝向的全部左下角 (a,b)；
2) 矩形离带（面积>1005 ⇒ a>=4 且 b>=4）；
3) 矿石走廊按实际端口数 m<=6（a=4 看左带、b=4 看下带），47 种边带逐一数；
4) 其余位置跑 strip_model（端口对接格不得在第 0 行/列；P∈{10,11,12}；不用区间 DP）；
5) 与报告 positions.json 的分类逐项比较。
"""
import json, sys, time
from pathlib import Path
from strip_model import run, HERE

ROOT = HERE.parent


def warehouse_patterns():
    """47 种联合边带：返回 (gl,gb, 左带端口行集合, 下带端口列集合)。"""
    out = []
    for gl, gb in [(0, k) for k in range(24)] + [(k, 0) for k in range(1, 24)]:
        left_cells = set(range(70)) - {3 * gl}
        bot_cells = set(range(70)) - {3 * gb}
        # 角格 (0,0)：两带都声称时只归一侧；gl=0 表示左带让出角格
        if gl == 0 and gb == 0:
            bot_cells.discard(0)
        elif gl == 0:
            pass  # 左带不含 0 行；下带含 0 列（若 gb>=1）
        else:
            bot_cells.discard(0)  # gb=0：下带让出 (0,0)，由左带占
        def starts(cs):
            cs = sorted(cs)
            st = []
            i = 0
            while i < len(cs):
                assert cs[i + 1] == cs[i] + 1 and cs[i + 2] == cs[i] + 2, (gl, gb, cs[i])
                st.append(cs[i])
                i += 3
            return st
        ls, bs = starts(left_cells), starts(bot_cells)
        assert len(ls) == 23 and len(bs) == 23, (gl, gb, len(ls), len(bs))
        occupied = {(0, s + t) for s in ls for t in range(3)} | {(s + t, 0) for s in bs for t in range(3)}
        assert len(occupied) == 138
        out.append((gl, gb, {s + 1 for s in ls}, {s + 1 for s in bs}))
    return out


PATS = warehouse_patterns()


def corridor_ok(a, b, W, H):
    """矿石走廊：存在某种边带使 a=4 时左带 m<=6、b=4 时下带 m<=6。"""
    for gl, gb, lp, bp in PATS:
        if a == 4 and sum(b <= y < b + H for y in lp) > 6:
            continue
        if b == 4 and sum(a <= x < a + W for x in bp) > 6:
            continue
        return True
    return False


def main():
    rep = json.loads((ROOT / 'positions.json').read_text())
    rep_class = {}
    for p in rep['positions']:
        key = tuple(p['rect'])
        if not p['patterns']:
            rep_class[key] = 'corridor'
        elif any(br['keep'] for br in p['branches']):
            rep_class[key] = 'candidate'
        else:
            rep_class[key] = 'dp'
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    rows = []
    total = 0
    t0 = time.monotonic()
    for W, H in [(21, 53), (53, 21)]:
        for a in range(0, 70 - W + 1):
            for b in range(0, 70 - H + 1):
                total += 1
                if a < 4 or b < 4:
                    continue
                key = (a, b, W, H)
                if (a == 4 and H > 21) or (b == 4 and W > 21):
                    rows.append(dict(rect=key, mine='corridor_len', report=rep_class.get(key)))
                    continue
                if not corridor_ok(a, b, W, H):
                    rows.append(dict(rect=key, mine='corridor_m', report=rep_class.get(key)))
                    continue
                out = run(key, [10, 11, 12], seconds, 4, forbid_edge0=True, minimize=None)
                rows.append(dict(rect=key, mine=out['status'], report=rep_class.get(key), wall=out['wall'],
                                 P=out.get('P'), J=out.get('J'), X=out.get('X'), Y=out.get('Y')))
                if len(rows) % 50 == 0:
                    print(len(rows), round(time.monotonic() - t0, 1), flush=True)
    summary = dict(total_raw=total, after_ab4=len(rows))
    from collections import Counter
    summary['cross'] = {f'{m}|{r}': n for (m, r), n in Counter((x['mine'], x['report']) for x in rows).items()}
    (HERE / 'results' / 'scan_all.json').write_text(json.dumps(dict(summary=summary, rows=rows), ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
