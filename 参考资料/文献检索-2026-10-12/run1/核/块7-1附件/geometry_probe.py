"""只核离散几何和结构通道；不调用运行内核，不写仓库。

运行：PYTHONDONTWRITEBYTECODE=1 python3 geometry_probe.py
坐标中 y 向下，矩形两端都包含。E/S/W/N 分别为右/下/左/上。
"""
from itertools import product

D = {"E": (1, 0), "S": (0, 1), "W": (-1, 0), "N": (0, -1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


def cells(rect):
    x0, y0, x1, y1 = rect
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def port_cells(rect, side):
    x0, y0, x1, y1 = rect
    if side == "E":
        return {(x1, y) for y in range(y0, y1 + 1)}
    if side == "W":
        return {(x0, y) for y in range(y0, y1 + 1)}
    if side == "S":
        return {(x, y1) for x in range(x0, x1 + 1)}
    return {(x, y0) for x in range(x0, x1 + 1)}


def outside(rect, side):
    dx, dy = D[side]
    return {(x + dx, y + dy) for x, y in port_cells(rect, side)}


def direct_cycle():
    # 两个 5×5 正方形；共同一格外侧格意味着相对锚点坐标必在 [-6,6]。
    cr = (0, 0, 4, 4)
    cb = cells(cr)
    tested = one = both = 0
    for co, ao, x, y in product(D, D, range(-6, 7), range(-6, 7)):
        ar = (x, y, x + 4, y + 4)
        ab = cells(ar)
        if cb & ab:
            continue
        tested += 1
        ca = (outside(cr, co) & outside(ar, OPP[ao])) - cb - ab
        ac = (outside(ar, ao) & outside(cr, OPP[co])) - cb - ab
        one += bool(ca)
        both += bool(ca and ac)
    print(f"two_5x5: tested={tested}, C_to_A={one}, both_directions={both}")
    assert both == 0


def actual_channels(machines, belts):
    # 每个端口是 (所属单位, 所在格, 面朝方向, in/out)。逐条按规则17重建。
    ports = []
    for name, rect, incoming, outgoing in machines:
        ports.extend((name, p, incoming, "in") for p in port_cells(rect, incoming))
        ports.extend((name, p, outgoing, "out") for p in port_cells(rect, outgoing))
    for name, cell, incoming, outgoing in belts:
        ports.extend([(name, cell, incoming, "in"), (name, cell, outgoing, "out")])
    transport = {b[0] for b in belts}
    channels = []
    for a, p, s, mode in ports:
        if mode != "out":
            continue
        dx, dy = D[s]
        for b, q, t, target_mode in ports:
            if a != b and target_mode == "in" and q == (p[0] + dx, p[1] + dy) and t == OPP[s] and ({a, b} & transport):
                channels.append((a, b))
    return sorted(channels)


def corner_example():
    machines = [
        ("P1", (10, 10, 12, 12), "N", "S"),
        ("P2", (13, 10, 15, 12), "N", "S"),
        ("S", (7, 12, 9, 14), "W", "E"),
        ("G", (10, 14, 15, 17), "N", "S"),
    ]
    belts = [
        ("b1", (11, 13), "N", "S"),
        ("b2", (14, 13), "N", "S"),
        ("bs", (10, 13), "W", "S"),
    ]
    occupied = set()
    for name, rect, incoming, outgoing in machines:
        assert not (occupied & cells(rect)), name
        occupied |= cells(rect)
    for name, c, incoming, outgoing in belts:
        assert c not in occupied, name
        occupied.add(c)
    got = actual_channels(machines, belts)
    want = sorted([("P1", "b1"), ("P2", "b2"), ("S", "bs"), ("b1", "G"), ("b2", "G"), ("bs", "G")])
    assert got == want, got
    print("corner_example: no_overlap=True, actual_channels=" + repr(got))


def shared_turn_example():
    machines = [
        ("W", (17, 18, 19, 20), "W", "E"),
        ("N", (20, 16, 25, 19), "S", "N"),
        ("E", (21, 20, 23, 22), "E", "W"),
        ("S", (15, 21, 20, 24), "N", "S"),
    ]
    occupied = set()
    for name, rect, incoming, outgoing in machines:
        assert not (occupied & cells(rect)), name
        occupied |= cells(rect)
    c = (20, 20)
    assert c not in occupied
    blue = actual_channels(machines, [("c", c, "W", "N")])
    sand = actual_channels(machines, [("c", c, "E", "S")])
    assert blue == sorted([("W", "c"), ("c", "N")]), blue
    assert sand == sorted([("E", "c"), ("c", "S")]), sand
    print("shared_turn_example: no_overlap=True, blue=" + repr(blue) + ", sand=" + repr(sand))


if __name__ == "__main__":
    direct_cycle()
    corner_example()
    shared_turn_example()
