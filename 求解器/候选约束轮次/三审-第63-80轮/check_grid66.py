"""三审：直接核对第 66 轮「矩形旁供电分组上限」的格组覆盖证书（只读其 tiles 与 cap，自己重建中心域）。

中心 (x,y) 合法：3x3 小块 x-1..x+1、y-1..y+1 全在列行 1..69、不碰空矩形、不碰桩身，且与供电范围相交。
每个 tile [x0,y0,w,h] 覆盖中心 x0..x0+w-1、y0..y0+h-1，要求 w,h<=3；所有合法中心须被覆盖；cap<=min(23,tile 数) 即成立。
"""
import json
import field as S
from geo import pole_body, pole_range

d = json.load(open('../第66-68轮/推导66/power_certificates.json'))
out = {}
for b in (9, 17):
    bad = []
    n_centers = 0
    for e in d[str(b)]:
        p, q, cap, tiles = e['x'], e['y'], e['cap'], e['tiles']
        pb = set(pole_body(p, q))
        x0, x1, y0, y1 = pole_range(p, q)
        centers = []
        for x in range(x0 - 1, x1 + 2):
            for y in range(y0 - 1, y1 + 2):
                blk = [(x + i, y + j) for i in (-1, 0, 1) for j in (-1, 0, 1)]
                if not all(S.usable(c, b) and c not in pb for c in blk):
                    continue
                if not (x - 1 <= x1 and x + 1 >= x0 and y - 1 <= y1 and y + 1 >= y0):
                    continue
                centers.append((x, y))
        n_centers += len(centers)
        ok_dims = all(t[2] <= 3 and t[3] <= 3 and t[2] >= 1 and t[3] >= 1 for t in tiles)
        covered = all(any(t[0] <= x < t[0] + t[2] and t[1] <= y < t[1] + t[3] for t in tiles) for (x, y) in centers)
        if not (ok_dims and covered and cap <= min(23, len(tiles))):
            bad.append((p, q, cap, len(tiles), ok_dims, covered))
    out[b] = dict(positions=len(d[str(b)]), centers=n_centers, bad=bad)
    print(b, len(d[str(b)]), n_centers, 'bad', len(bad), bad[:5])
json.dump(out, open('out/check_grid66.json', 'w'), indent=1)
