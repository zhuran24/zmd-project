# 复核80：逐格核对局部取等点（不调用求解器）
import json, sys

POLE = {(5, 5), (5, 6), (6, 5), (6, 6)}
WT = {"S": 2, "M": 3, "L": 3}


def check(sol, wall, cap):
    occ = {}
    for k, d in enumerate(sol):
        for a in range(d["x"], d["x"] + d["w"]):
            for b in range(d["y"], d["y"] + d["h"]):
                assert (a, b) not in POLE, ("压桩身", d)
                assert (a, b) not in occ, ("重叠", d)
                if wall:
                    assert a <= 6, ("越过占边界", d)
                occ[(a, b)] = k
        # 与 [0,11]^2 相交
        assert d["x"] <= 11 and d["x"] + d["w"] - 1 >= 0 and d["y"] <= 11 and d["y"] + d["h"] - 1 >= 0, ("不与供电范围相交", d)
        assert (d["cat"] == "S" and d["w"] == d["h"] == 3) or (d["cat"] == "M" and d["w"] == d["h"] == 5) or \
               (d["cat"] == "L" and ((d["w"], d["h"], d["axis"]) in ((6, 4, "V"), (4, 6, "H"))))
    for k, d in enumerate(sol):
        x, y, w, h = d["x"], d["y"], d["w"], d["h"]
        if d["axis"] == "H":
            sides = [[(x - 1, y + j) for j in range(h)], [(x + w, y + j) for j in range(h)]]
        else:
            sides = [[(x + i, y - 1) for i in range(w)], [(x + i, y + h) for i in range(w)]]
        for sd in sides:
            ok = [g for g in sd if g not in POLE and g not in occ and (not wall or g[0] <= 6)]
            assert ok, ("端口边无空邻格", d)
    assert len(sol) <= cap
    return sum(WT[d["cat"]] for d in sol), len(sol)


if __name__ == "__main__":
    for fn, wall, cap in [("milp_general_max.json", False, 23), ("milp_wall_max.json", True, 14),
                          ("cp_wall_max.json", True, 14)] + [(a, b == "wall", int(c)) for a, b, c in
                                                             (s.split(":") for s in sys.argv[1:])]:
        sol = json.load(open(fn))["solution"]
        print(fn, "加权与台数", check(sol, wall, cap))
