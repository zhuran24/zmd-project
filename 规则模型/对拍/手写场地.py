"""手写场地黄金的输入族。几何边界用显式坐标放样，期望从场地模式取得。"""
from pathlib import Path
import subprocess

from 生成场地 import MACHINES, OPPOSITE, SIDES, core_keys, document, example, piece

DEST = Path(__file__).resolve().parent / "场地黄金"


def orientations():
    yield example([])
    cross = [piece(8*k, x, y, "桥接器", "上") for k, (x, y) in
             enumerate([(30, 29), (31, 30), (30, 31), (29, 30)])]
    for d in SIDES:
        for e in SIDES:
            if d != e:
                yield example(cross + [piece(87, 30, 30, "传送带", d, e)])
        for k in ("分流器", "汇流器", "物品准入口", "桥接器"):
            yield example(cross + [piece(87, 30, 30, k, d)])
        # 机器与箱的两条有口长边各贴满一排普通带，让每种朝向的端口次序出现在历史里。
        for k in (*MACHINES, "协议储存箱"):
            size = 5 if k in MACHINES[4:6] else 3
            w, h = (size, size)
            if k in MACHINES[6:]:
                w, h = (6, 4) if d in "上下" else (4, 6)
            if d in "上下":
                cells = [(30+i, y) for i in range(w) for y in (29, 30+h)]
            else:
                cells = [(x, 30+i) for i in range(h) for x in (29, 30+w)]
            belts = [piece(i, x, y, "传送带", OPPOSITE[d], d) for i, (x, y) in enumerate(cells)]
            kind = [k, d] if k == "协议储存箱" else ["制造", k, d]
            yield example(belts + [piece(87, 30, 30, *kind)])
    yield example([piece(2**80, 68, 68, "供电桩")])
    for a in ("上下", "左右"):
        yield example([piece(0, 61, 61, "协议核心", a)])


# 在同一条竖直缝上让两端口对齐。大件选一个确有端口的边格。
# 在同一端可同时存取的桥接器只摆一次。取货口只能作出口。
def contact(k, u, seam, left, outlet):
    face = "右" if left else "左"
    other = OPPOSITE[face]
    direction = face if outlet else other
    w, offset = 1, 0
    if k == "协议核心":
        kind = [k, "左右" if outlet else "上下"]
        w, offset = 9, 1
    elif k == "仓库取货口":
        kind = [k, face]
        offset = 1
    elif k == "传送带":
        kind = [k, OPPOSITE[direction], direction]
    elif k == "分流器":
        kind = [k, OPPOSITE[direction]]
    elif k in MACHINES:
        kind = ["制造", k, direction]
        w = 3 if k in MACHINES[:4] else 5 if k in MACHINES[4:6] else 4
        offset = 1
    else:
        kind = [k, direction]
        if k == "协议储存箱":
            w, offset = 3, 1
    return piece(u, seam - w if left else seam, 30 - offset, *kind)


def contacts():
    kinds = ["传送带", "分流器", "汇流器", "物品准入口", "桥接器", *MACHINES,
             "协议储存箱", "协议核心", "仓库取货口"]
    for left in kinds:
        for right in kinds:
            if left == right and left in ("协议核心", "仓库取货口"):
                continue
            seam = 1 if left == "仓库取货口" else 69 if right == "仓库取货口" else 30
            for a in ([True] if left in ("仓库取货口", "桥接器") else [True, False]):
                for b in ([True] if right in ("仓库取货口", "桥接器") else [True, False]):
                    p = contact(left, 90, seam, True, a)
                    q = contact(right, 2, seam, False, b)
                    yield example([p, q])
                    yield example([q, p])


def terminals():
    for axis in ("上下", "左右"):
        ring = []
        for i, (d, n) in enumerate(core_keys(axis)):
            x, y = {"上": (30+n, 29), "右": (39, 30+n), "下": (30+n, 39), "左": (29, 30+n)}[d]
            output = d if d in axis else OPPOSITE[d]
            ring.append(piece(99 - 3*i, x, y, "传送带", OPPOSITE[output], output))
        for ranks in ([20-i for i in range(20)], [i % 3 for i in range(20)], [0]*20):
            ex = example(ring + [piece(120, 30, 30, "协议核心", axis)])
            ex["核心先后"] = list(reversed([[k, r] for k, r in zip(core_keys(axis), ranks)]))
            yield ex
    for d, x, y, bx, by in [("上", 40, 69, 41, 68), ("右", 0, 40, 1, 41),
                             ("下", 40, 0, 41, 1), ("左", 69, 40, 68, 41)]:
        yield example([piece(5, bx, by, "传送带", OPPOSITE[d], d), piece(3, x, y, "仓库取货口", d)])
    # 中心最后放，八个端口在一次建成中都有匹配。四个方向的事件次序可直接对照。
    for d in SIDES:
        neighbors = [piece(8*k, x, y, "桥接器", "上") for k, (x, y) in
                     enumerate([(20, 19), (21, 20), (20, 21), (19, 20)])]
        yield example(neighbors + [piece(40, 20, 20, "桥接器", d)])


def belts():
    ends = [piece(3, 10, 20, "协议储存箱", "右"), piece(1, 18, 20, "制造", "精炼炉", "右")]
    for order in ([13, 14, 15, 16, 17], [17, 16, 15, 14, 13], [13, 14, 17, 16, 15]):
        yield example(ends + [piece(x, x, 21, "传送带", "左", "右") for x in order])
    ring = [(20, 20, "下", "右"), (21, 20, "左", "下"),
            (21, 21, "上", "左"), (20, 21, "右", "上")]
    yield example([piece(u, x, y, "传送带", a, b) for u, (x, y, a, b) in enumerate(ring)])
    yield example([piece(1, 20, 20, "传送带", "左", "右"), piece(9, 21, 20, "传送带", "左", "下"),
                   piece(4, 21, 21, "物品准入口", "下")])


def power():
    for k, w, h in [("精炼炉", 3, 3), ("采种机", 5, 5), ("封装机", 6, 4), ("协议储存箱", 3, 3)]:
        for delta in (0, 1):
            # 四角之一是落入闭区间 [25,36] 的唯一格；再沿该边法向外移一格。
            for x, y in [(26-w-delta, 36), (36+delta, 26-h),
                         (36, 26-h-delta), (26-w, 36+delta)]:
                kind = [k, "下"] if k == "协议储存箱" else ["制造", k, "下"]
                yield example([piece(200, 30, 30, "供电桩"), piece(5, x, y, *kind)])


def rejections():
    for x, y in [(70, 0), (0, 70), (10**30, 10)]:
        yield example([piece(0, x, y, "分流器", "上")])
    yield example([piece(7, 65, 65, "协议核心", "上下")])
    yield example([piece(5, 66, 67, "制造", "封装机", "右")])
    yield example([piece(6, 21, 21, "协议储存箱", "上"), piece(7, 23, 23, "供电桩")])
    for k in (["传送带", "左", "右"], ["供电桩"]):
        p, q = piece(1, 10, 10, *k), piece(1, 60, 60, "物品准入口", "上")
        yield example([p, q])
        yield example([q, p])
    for n in range(4):
        for kind in (["供电桩"], ["传送带", "下", "左"]):
            p, q = piece(10, 10, 10, "桥接器", "上"), piece(10+n, 20, 20, *kind)
            yield example([p, q])
            yield example([q, p])
    yield example([piece(10, 10, 10, "桥接器", "右"), piece(8, 40, 40, "桥接器", "下")])
    for a in ("上下", "左右"):
        yield example([piece(1, 10, 10, "协议核心", "上下"), piece(2, 40, 40, "协议核心", a)])
    for d, x, y in [("上", 10, 0), ("下", 10, 69), ("左", 0, 20), ("右", 69, 20)]:
        yield example([piece(7, 10, 10, "仓库取货口", d)])
        yield example([piece(1, x, y, "仓库取货口", d)])
        yield example([piece(0, 20, 20, "传送带", d, d)])
    yield example([piece(3, 20, 20, "传送带", "上", "下"), piece(3, 20, 20, "物品准入口", "下")])
    yield example([])  # 紧跟拒绝，仍从空场地独立运行。


FAMILIES = {"朝向": orientations, "两两贴合": contacts, "核心取货口和桥": terminals,
            "接长补带和环": belts, "供电边界": power, "建造拒绝": rejections}


if __name__ == "__main__":
    root = DEST.parents[1]
    subprocess.run(["lake", "build", "对拍"], cwd=root, check=True)
    DEST.mkdir(exist_ok=True)
    for name, family in FAMILIES.items():
        data = document(family())
        path = DEST / f"手写-{name}.json"
        path.write_text(data)
        path.with_suffix(".jsonl").write_bytes(subprocess.check_output(
            [root / ".lake/build/bin/对拍", path], cwd=root))
