#!/usr/bin/env python3
"""独立编码 A：逐单位建造、同批排列、选支后沿图求层数。

只写 stdout；不导入任何项目脚本。坐标为单位左下角格。
"""
from itertools import combinations, permutations, product
from collections import Counter
import json

DIR = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
OPP = {"N": "S", "E": "W", "S": "N", "W": "E"}
NON_TRANSPORT = {"粉碎机", "仓库取货口"}


def unit(name, kind, x, y, incoming, outgoing=None):
    if kind == "粉碎机":
        w = h = 3
        outgoing = OPP[incoming]
    else:
        w = h = 1
    ins = set(incoming)
    outs = set(outgoing or ())
    if kind == "分流器":
        outs = set(DIR) - ins
    if kind == "汇流器":
        ins = set(DIR) - outs
    return dict(name=name, kind=kind, x=x, y=y, w=w, h=h,
                incoming=sorted(ins), outgoing=sorted(outs))


def contacts(units):
    occupied = {}
    inports = {}
    outports = []
    for u in units:
        x, y, w, h = (u[k] for k in ("x", "y", "w", "h"))
        for xx in range(x, x + w):
            for yy in range(y, y + h):
                assert 0 <= xx < 70 and 0 <= yy < 70
                assert (xx, yy) not in occupied
                occupied[xx, yy] = u["name"]
        for side, dxdy in DIR.items():
            cells = [(xx, y + h - 1) for xx in range(x, x + w)] if side == "N" else \
                    [(xx, y) for xx in range(x, x + w)] if side == "S" else \
                    [(x + w - 1, yy) for yy in range(y, y + h)] if side == "E" else \
                    [(x, yy) for yy in range(y, y + h)]
            for p in cells:
                if u["kind"] == "仓库取货口" and p != (x, y + 1):
                    continue
                if side in u["incoming"]:
                    inports[p, side] = u["name"]
                if side in u["outgoing"]:
                    outports.append((p, side, u["name"], u["kind"]))
    kinds = {u["name"]: u["kind"] for u in units}
    result = []
    for (x, y), side, src, kind in outports:
        dx, dy = DIR[side]
        dst = inports.get(((x + dx, y + dy), OPP[side]))
        if dst is not None and (kind not in NON_TRANSPORT or kinds[dst] not in NON_TRANSPORT):
            result.append([src, dst])
    return sorted(result)


TRIANGLE = [unit("A", "粉碎机", 20, 20, "W"),
            unit("B", "分流器", 23, 20, "W"),
            unit("C", "汇流器", 23, 21, "", "E")]
SQUARE = [unit("A", "分流器", 30, 30, "N"),
          unit("B", "分流器", 31, 30, "W"),
          unit("C", "分流器", 30, 31, "E"),
          unit("D", "分流器", 31, 31, "S")]
STAR = [unit("A", "分流器", 10, 10, "W"),
        unit("B", "传送带", 11, 10, "W", "E"),
        unit("C", "传送带", 10, 11, "S", "N"),
        unit("D", "传送带", 10, 9, "N", "S")]
FED_STAR = STAR + [unit("F" + str(x), "传送带", x, 10, "W", "E") for x in range(1, 10)] + [
    dict(name="W", kind="仓库取货口", x=0, y=9, w=1, h=3, incoming=[], outgoing=["E"])]
EXITS = [unit("PA", "传送带", 30, 29, "N", "S"),
         unit("PB", "传送带", 32, 30, "W", "E"),
         unit("PC", "传送带", 29, 31, "E", "W"),
         unit("PD", "传送带", 31, 32, "S", "N"),
         unit("MA", "粉碎机", 29, 26, "N"),
         unit("MB", "粉碎机", 33, 29, "W"),
         unit("MC", "粉碎机", 26, 30, "E"),
         unit("MD", "粉碎机", 30, 33, "S")]


def connection_orders(vertices, edges):
    # 编码 A 真的逐个加入单位，扫描本次新出现的通道。
    edges = sorted("".join(sorted(e)) for e in edges)
    assert len(set(edges)) == len(edges)
    witnesses = {}
    schedules = []
    shape_histogram = Counter()
    refinements_total = 0
    tied_orders = 0
    for order in permutations(vertices):
        made = set()
        present = set()
        batches = []
        times = {}
        for step, v in enumerate(order, 1):
            made.add(v)
            new = [e for e in edges if e not in present and set(e) <= made]
            present.update(new)
            for e in new:
                times[e] = step
            if new:
                batches.append(new)
        tied = any(len(g) > 1 for g in batches)
        tied_orders += tied
        shape_histogram[",".join(str(len(g)) for g in batches)] += 1
        linear = set()
        for picks in product(*(list(permutations(g)) for g in batches)):
            seq = tuple(e for group in picks for e in group)
            linear.add(seq)
            witnesses.setdefault(seq, {"unit_order": list(order), "batches": batches})
        refinements_total += len(linear)
        schedules.append({"unit_order": list(order), "times": times,
                          "batches": batches, "refinements": [list(s) for s in sorted(linear)]})
    all_orders = set(permutations(edges))
    return {"vertices": list(vertices), "edges": edges,
            "unit_order_count": len(schedules), "unit_orders_with_ties": tied_orders,
            "batch_size_histogram": dict(sorted(shape_histogram.items())),
            "order_refinement_pairs": refinements_total,
            "refinement_count": len(witnesses), "missing_count": len(all_orders - witnesses.keys()),
            "refinements": [list(s) for s in sorted(witnesses)],
            "missing": [list(s) for s in sorted(all_orders - witnesses.keys())],
            "witnesses": {"/".join(k): v for k, v in sorted(witnesses.items())},
            "schedules": schedules}


def layer_assignments(units):
    arcs = contacts(units)
    vertices = sorted(u["name"] for u in units if u["kind"] != "粉碎机")
    sending = {a for a, _ in arcs}
    downstream = {u: sorted(v for a, v in arcs if a == u and v in vertices and v in sending)
                  for u in vertices}
    choices = [downstream[u] or [None] for u in vertices]
    valid, invalid = [], []
    for picks in product(*choices):
        selected = dict(zip(vertices, picks))
        heights = {}

        def depth(u, path):
            if u in path:
                raise ValueError("绕回自身")
            if u in heights:
                return heights[u]
            heights[u] = 1 if selected[u] is None else 1 + depth(selected[u], path | {u})
            return heights[u]

        try:
            for v in vertices:
                depth(v, set())
        except ValueError:
            invalid.append(selected)
        else:
            valid.append({"selected": selected, "layers": heights})
    layer_vectors = sorted({tuple(row["layers"][v] for v in vertices) for row in valid})
    return {"vertices": vertices, "arcs": arcs, "qualified_downstream": downstream,
            "raw_choice_count": len(valid) + len(invalid), "acyclic_choice_count": len(valid),
            "cyclic_choice_count": len(invalid), "vectors": [list(v) for v in layer_vectors],
            "valid": valid, "invalid": invalid}


def main():
    out = {"method": "A: cell ports; incremental construction; chosen-successor DFS", "cases": {}}
    for name, units in (("triangle", TRIANGLE), ("square", SQUARE), ("star", STAR)):
        arcs = contacts(units)
        case = connection_orders(sorted(u["name"] for u in units), arcs)
        case["units"] = units
        case["directed_channels"] = arcs
        out["cases"][name] = case
    out["layers"] = {"ring_with_exits": layer_assignments(SQUARE + EXITS),
                     "ring_without_exit": layer_assignments(SQUARE)}
    out["layers"]["ring_with_exits"]["units"] = SQUARE + EXITS
    out["fed_star"] = {"units": FED_STAR, "directed_channels": contacts(FED_STAR)}
    # 仅模拟分流器第一次送出已停留满 1 tick 的一件源矿。
    # 三个下游传送带都空着、输入不拒收；这是局部单步，不是循环态证书。
    rr = []
    for order in permutations(("AB", "AC", "AD")):
        items = {e: None for e in order}
        source = "源矿"
        for e in order[1:] + order[:1]:
            if source is not None and items[e] is None:
                items[e], source = source, None
        winner = next(e for e in items if items[e] is not None)
        rr.append({"tie_order": list(order), "first_success": winner})
    out["first_send"] = rr
    out["first_send_histogram"] = dict(sorted(Counter(r["first_success"] for r in rr).items()))
    # 小规模全图核对是算法检查；这些抽象图不被称为全部可摆布局。
    family = []
    for n in range(1, 5):
        vertices = "ABCD"[:n]
        pairs = list(combinations(vertices, 2))
        for mask in range(1 << len(pairs)):
            edges = [p for i, p in enumerate(pairs) if mask >> i & 1]
            r = connection_orders(vertices, edges)
            family.append({"n": n, "edges": r["edges"], "refinements": r["refinements"],
                           "unit_orders_with_ties": r["unit_orders_with_ties"],
                           "order_refinement_pairs": r["order_refinement_pairs"]})
    out["graph_family"] = family
    out["graph_family_count"] = len(family)
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
