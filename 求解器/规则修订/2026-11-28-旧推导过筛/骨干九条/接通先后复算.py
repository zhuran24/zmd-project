"""按规则第 22、25—28、81、86—87 行，对两处局部接法枚举单位建成次序。"""
from dataclasses import dataclass
from itertools import combinations, permutations

# 北、东、南、西，序号沿顺时针增加。端口同时标明朝向和存取。
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))


@dataclass(frozen=True)
class Unit:
    x: int
    y: int
    ports: tuple
    belt: bool = False


def splitter(x, y, inlet):
    outlets = tuple(((inlet + offset) % 4, "取") for offset in (1, 2, 3))
    return Unit(x, y, ((inlet, "存"),) + outlets)


def merger(x, y, outlet):
    inlets = tuple(((outlet + offset) % 4, "存") for offset in (1, 2, 3))
    return Unit(x, y, inlets + ((outlet, "取"),))


def belt(x, y, inlet, outlet):
    return Unit(x, y, ((inlet, "存"), (outlet, "取")), belt=True)


def contacts(layout, unit_name, present):
    """在当前已建的邻格中，按新单位端口顺序逐一找对向异类端口。"""
    unit = layout[unit_name]
    for side, role in unit.ports:
        dx, dy = DIRECTIONS[side]
        neighbor = present.get((unit.x + dx, unit.y + dy))
        if neighbor is None:
            continue
        other_role = "存" if role == "取" else "取"
        if ((side + 2) % 4, other_role) in layout[neighbor].ports:
            yield unit_name + neighbor if role == "取" else neighbor + unit_name


def replay(layout, build_order):
    present = {}
    history = []
    for name in build_order:
        history.extend(contacts(layout, name, present))
        unit = layout[name]
        present[unit.x, unit.y] = name
    return tuple(history)


def sorted_by_later_end(layout, build_order):
    """在终局静态接法上独立算排序键，对照逐个建成时产生的事件。"""
    keys = {}
    for left, right in combinations(layout, 2):
        a, b = layout[left], layout[right]
        delta = b.x - a.x, b.y - a.y
        if delta not in DIRECTIONS:
            continue
        side = DIRECTIONS.index(delta)
        for i, (sa, ra) in enumerate(a.ports):
            for j, (sb, rb) in enumerate(b.ports):
                if sa != side or sb != (side + 2) % 4 or ra == rb:
                    continue
                edge = left + right if ra == "取" else right + left
                later = max(build_order.index(left), build_order.index(right))
                local_index = i if build_order[later] == left else j
                keys[edge] = later, local_index
    return tuple(sorted(keys, key=keys.__getitem__))


def enumerate_orders(layout):
    result = {}
    for order in permutations(layout):
        sequence = replay(layout, order)
        assert sequence == sorted_by_later_end(layout, order)
        result[order] = sequence
    return result


def obeys_blueprint(layout, order):
    belt_flags = [layout[name].belt for name in order]
    return belt_flags == sorted(belt_flags)


def main():
    # P 存北，东邻 E 是分流器，南邻 S、西邻 W 各是一格带。
    star = {"P": splitter(0, 0, 0), "E": splitter(1, 0, 3),
            "S": belt(0, 1, 0, 2), "W": belt(-1, 0, 1, 3)}
    histories = enumerate_orders(star)
    for label, orders in (
        ("同张蓝图", [o for o in histories if obeys_blueprint(star, o)]),
        ("离线重建", list(histories)),
        ("离线且 P 最后", [o for o in histories if o[-1] == "P"]),
    ):
        outcomes = {histories[o] for o in orders}
        words = ["→".join(word) for word in sorted(outcomes)]
        print(f"三出口，{label}：单位序 {len(orders)}，出口序 {len(outcomes)}，{' / '.join(words)}")

    # A B    A、B、D 是分流器，C 是汇流器，只比较这四条单位间通道。
    # D C    A→B→C 及 A→D→C。
    diamond = {"A": splitter(0, 0, 0), "B": splitter(1, 0, 3),
               "D": splitter(0, 1, 0), "C": merger(1, 1, 1)}
    histories = enumerate_orders(diamond)
    words = set(histories.values())
    edges = sorted(next(iter(words)))
    assert edges == ["AB", "AD", "BC", "DC"]
    assert all(sorted(word) == edges for word in words)
    pairs = list(combinations(edges, 2))
    reversible = sum({word.index(a) < word.index(b) for word in words}
                     == {False, True} for a, b in pairs)
    disjoint_ends = sum(set(word[-2:]) == {"AB", "DC"} for word in words)
    assert all(order[-1] in edge for order, seq in histories.items() for edge in seq[-2:])
    print(f"两支汇合：单位序 {len(histories)}，实际通道序 {len(words)}，"
          f"无约束的通道全排列 {len(list(permutations(edges)))}，"
          f"两向均出现的通道对 {reversible}/{len(pairs)}，"
          f"AB、DC 占末两位的实际通道序 {disjoint_ends}")


if __name__ == "__main__":
    main()
