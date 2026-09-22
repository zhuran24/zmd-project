#!/usr/bin/env python3
"""覆盖席独立复算：重建样例图，用独立集分块计数，并核十五轴。"""
import hashlib
import itertools
import json
import math
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAMES = ("混做粉碎机两下游", "分流器三路轮询")


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_partitions(n, edges):
    """按最小顶点所在独立块划分；不同于删缩边和源点容斥。"""
    adjacent = [0] * n
    for a, b in edges:
        adjacent[a] |= 1 << b
        adjacent[b] |= 1 << a

    @lru_cache(None)
    def independent(mask):
        if mask == 0:
            return (0,)
        bit = mask & -mask
        vertex = bit.bit_length() - 1
        rest = mask ^ bit
        return independent(rest) + tuple(bit | s for s in independent(rest & ~adjacent[vertex]))

    @lru_cache(None)
    def partitions(mask):
        if not mask:
            return (1,)
        bit = mask & -mask
        vertex = bit.bit_length() - 1
        result = [0] * (mask.bit_count() + 1)
        for subset in independent((mask ^ bit) & ~adjacent[vertex]):
            block = subset | bit
            for k, value in enumerate(partitions(mask ^ block)):
                result[k + 1] += value
        return tuple(result)

    coefficients = partitions((1 << n) - 1)
    # 每个独立分块给色多项式一个下降阶乘；在负一求值为带符号阶乘。
    answer = sum((-1) ** (n + k) * math.factorial(k) * v for k, v in enumerate(coefficients))
    return {"count": answer, "independent_partition_coefficients": coefficients,
            "memo_states": partitions.cache_info().currsize}


def build_graph(data, strict):
    """直接按单位接触关系重建被审稿的保守图，不读被审脚本或资源表。"""
    kinds = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    channels = data["layout"]["physical_channels"]
    endpoints = {c["id"]: (c["source_port"].split(":")[0], c["target_port"].split(":")[0])
                 for c in channels}
    params = {k: v["value"] for group in ("fixed", "offline_mutable", "fixedness_unproven")
              for k, v in data["parameters"][group].items()}
    templates = params["judgment.order"]["template_order"]
    enabled = {s["unit"]: s["enabled"] for s in data["settings"]["switches"]}

    def resource(unit):
        return "warehouse" if kinds[unit] in ("协议核心", "仓库取货口") else unit

    gate_sources = {resource(a) for a, b in endpoints.values() if kinds[b] == "物品准入口"}
    accesses = []
    for row in templates:
        op, target = row["operation"], row["target"]
        if op == "move":
            source, dest = endpoints[target]
            touched = {resource(source), resource(dest)}
            observed = set(touched)
            for a, b in endpoints.values():
                if a == source or b == dest:
                    observed |= {resource(a), resource(b)}
            barrier = kinds[dest] == "物品准入口" or bool(touched & gate_sources)
        elif op == "manufacture":
            touched = observed = {target}
            barrier = target in gate_sources
        elif op == "transfer":
            touched = observed = {target, "warehouse"} if enabled[target] else set()
            barrier = bool(touched & gate_sources)
        else:
            raise AssertionError(op)
        accesses.append((op, touched, observed, barrier))
    edges = []
    for i, j in itertools.combinations(range(len(templates)), 2):
        a, b = accesses[i], accesses[j]
        conflict = a[3] or b[3] or bool(a[1] & b[2]) or bool(b[1] & a[2])
        if strict:
            # 两样例的全部制造机均被PC读到；关箱体无写、全局刷新把所有move相连。
            if a[0] == b[0] == "move" or a[0] == b[0] == "manufacture":
                conflict = True
            if {a[0], b[0]} == {"move", "manufacture"}:
                machine = a if a[0] == "manufacture" else b
                if any(machine[1] & z[2] for z in accesses if z[0] == "move"):
                    conflict = True
        if conflict:
            edges.append((i, j))
    return templates, edges, [i for i, row in enumerate(accesses) if row[3]]


def make_tie_graph(data):
    event_times = {e["id"]: Fraction(e["time"]["value"]["value"])
                   for e in data["timeline"]["events"] if e["time"] is not None}
    built = {b["unit"]: event_times[b["event"]] for b in data["construction"]["moments"]}
    channels = data["layout"]["physical_channels"]
    endpoints = [(c["source_port"].split(":")[0], c["target_port"].split(":")[0]) for c in channels]
    connected = [max(built[a], built[b]) for a, b in endpoints]
    edges = [(i, j) for i, j in itertools.combinations(range(len(channels)), 2)
             if connected[i] == connected[j] and
             (endpoints[i][0] == endpoints[j][0] or endpoints[i][1] == endpoints[j][1])]
    return edges, count_partitions(len(channels), edges)


def validate_small():
    graphs = permutations = 0
    for n in range(6):
        possible = list(itertools.combinations(range(n), 2))
        orders = list(itertools.permutations(range(n)))
        positions = [{v: i for i, v in enumerate(order)} for order in orders]
        for mask in range(1 << len(possible)):
            edges = [e for i, e in enumerate(possible) if mask & (1 << i)]
            signatures = {tuple(pos[a] < pos[b] for a, b in edges) for pos in positions}
            assert count_partitions(n, edges)["count"] == len(signatures)
            graphs += 1
            permutations += len(orders)
    return {"graphs": graphs, "permutations": permutations, "status": "passed"}


def validate_domain_formulas():
    # 全预序以连续非空组号编码，与有序分块数逐项对照。
    weak_orders = []
    for n in range(6):
        stirling = [[0] * (n + 1) for _ in range(n + 1)]
        stirling[0][0] = 1
        for a in range(1, n + 1):
            for b in range(1, a + 1):
                stirling[a][b] = stirling[a - 1][b - 1] + b * stirling[a - 1][b]
        formula = sum(math.factorial(k) * stirling[n][k] for k in range(n + 1))
        brute = 1 if n == 0 else sum(1 for labels in itertools.product(range(n), repeat=n)
                                     if set(labels) == set(range(max(labels) + 1)))
        assert formula == brute
        weak_orders.append(formula)
    timing_cases = 0
    for horizon in range(1, 5):
        for events in range(6):
            brute = len(list(itertools.combinations_with_replacement(range(horizon), events)))
            assert brute == math.comb(horizon + events - 1, events)
            timing_cases += 1
    shapes = {(a, b) for a in range(4) for b in range(4) if a != b}
    orbits = {frozenset(((a + r) % 4, (b + r) % 4) for r in range(4)) for a, b in shapes}
    assert len(shapes) == 12 and len(orbits) == 3 and all(len(o) == 4 for o in orbits)
    return {"weak_order_counts_n_0_to_5": weak_orders,
            "integer_build_timing_cases": timing_cases,
            "belt_ordered_pairs": len(shapes), "belt_rotation_orbits": len(orbits)}


def branch_projection(data):
    kinds = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    transport = {"传送带", "物品准入口", "桥接器", "分流器", "汇流器"}
    channels = data["layout"]["physical_channels"]
    ends = [(c["id"], c["source_port"].split(":")[0], c["target_port"].split(":")[0]) for c in channels]
    levels = {u: set() for u in kinds if kinds[u] not in transport}
    for cid, src, dst in ends:
        if src in levels:
            levels[src].add(cid if kinds[dst] == "汇流器" else "other")
    gates = [(cid, src, dst) for cid, src, dst in ends if kinds[dst] == "物品准入口"]
    forks = []
    for uid, kind in kinds.items():
        if kind != "分流器":
            continue
        outgoing = [(cid, dst) for cid, src, dst in ends if src == uid]
        count = len(outgoing)
        constant = {cid for cid, dst in outgoing if kinds[dst] != "物品准入口"}
        mutable = {cid for cid, dst in outgoing if kinds[dst] == "物品准入口"}
        full = math.prod(k ** math.comb(count, k) for k in range(1, count + 1))
        reachable_domain = [set(constant) | set(s) for k in range(len(mutable) + 1)
                            for s in itertools.combinations(sorted(mutable), k)]
        projected = math.prod(len(s) for s in reachable_domain if s)
        subsets = [tuple(s) for k in range(1, count + 1)
                   for s in itertools.combinations(sorted(cid for cid, _ in outgoing), k)]
        kept = [i for i, subset in enumerate(subsets) if constant <= set(subset)]
        tables = list(itertools.product(*subsets))
        signatures = {tuple(table[i] for i in kept) for table in tables}
        assert len(tables) == full and len(signatures) == projected
        forks.append({"unit": uid, "degree": count, "full_tables": full,
                      "permanent_outgoing": sorted(constant), "mutable_outgoing": sorted(mutable),
                      "static_subset_projection_tables": projected,
                      "exhaustive_projection_checks": len(tables)})
    no_query = all(len(v) <= 1 for v in levels.values())
    return {"nontransport_output_max_levels": {u: len(v) for u, v in levels.items()},
            "gate_input_edges": gates, "forks": forks,
            "full_geometric_table_product": math.prod(f["full_tables"] for f in forks),
            "no_damping_query_in_any_gate_subgraph": no_query,
            "behavior_representatives_if_no_query": 1 if no_query else None}


def main():
    reviewed_paths = [ROOT / "规格/参数扫描约减.md"] + [HERE / f for f in
                     ("count_classes.py", "verify_reduction.py", "等价类计数.json", "事件对清单.md", "验证结果.json")]
    source_paths = reviewed_paths + [ROOT / p for p in (
        "规格/受限转移定义.md", "规格/内核输入.md", "规格/内核配置-v1.json", "规格/选择点参数轴.md",
        "规格/受限模型声明.md", "数据/正式静态目录.json")] + [ROOT.parent / f for f in
        ("《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt")]
    source_paths += [ROOT / "数据/样例" / (name + ".json") for name in NAMES]
    source_paths.append(Path(__file__).resolve())
    before = {str(p): digest(p) for p in source_paths}
    claimed = read(HERE / "等价类计数.json")
    config = read(ROOT / "规格/内核配置-v1.json")
    document = (ROOT / "规格/参数扫描约减.md").read_text()
    table_axes = [s.split("`")[1] for s in document.splitlines()
                  if s.startswith("| ") and s.split("|")[1].strip().isdigit()]
    config_axes = sorted(k for k, v in config["axes"].items() if v["disposition"] == "由输入全称量化")
    assert sorted(table_axes) == config_axes == sorted(claimed["axes"])
    catalog = read(ROOT / "数据/正式静态目录.json")
    kinds = {u["id"]: u for u in catalog["units"]}
    recipe_rows = []
    for kind, unit in kinds.items():
        if unit["family"] != "manufacturing":
            continue
        recipes = [r for r in catalog["recipes"] if r["kind"] == kind]
        slots = sum(int(i["count"]["value"]) for i in unit["inventory"] if i["role"] == "input")
        # 任两配方并存所需种类数超过格数，即排除了任何数量足够的双候选。
        unions = [len(set(a["inputs"]) | set(b["inputs"])) for a, b in itertools.combinations(recipes, 2)]
        assert all(k > slots for k in unions)
        recipe_rows.append({"kind": kind, "recipes": len(recipes), "input_slots": slots,
                            "pair_support_unions": unions})
    results = {"schema": "review-r1-coverage-v1", "sources": before,
               "axis_count": len(config_axes), "axes": config_axes,
               "recipe_audit": recipe_rows,
               "recipe_raw_orders": math.factorial(sum(r["recipes"] for r in recipe_rows)),
               "recipe_local_orders": math.prod(math.factorial(r["recipes"]) for r in recipe_rows),
               "recipe_representatives": 1, "small_graph_validation": validate_small(),
               "domain_formula_checks": validate_domain_formulas(), "examples": []}
    for name in NAMES:
        data = read(ROOT / "数据/样例" / (name + ".json"))
        original = next(e for e in claimed["examples"] if e["name"] == name)
        row = {"name": name, "graphs": {}}
        for mode in ("semantic_sweep", "operational_conservative"):
            templates, edges, barriers = build_graph(data, mode == "operational_conservative")
            assert edges == [tuple(e) for e in original["modes"][mode]["edges"]]
            counted = count_partitions(len(templates), edges)
            assert counted["count"] == original["modes"][mode]["classes"]
            assert len(edges) == original["modes"][mode]["edge_count"]
            for pair in original["modes"][mode]["pairs"]:
                assert pair["conflict"] == ((pair["left"], pair["right"]) in edges)
            row["graphs"][mode] = {"n": len(templates), "edges": edges, "barriers": barriers,
                                    "raw_orders": math.factorial(len(templates)), **counted}
        tie_edges, tie_count = make_tie_graph(data)
        assert tie_edges == [tuple(e) for e in original["connection_tie"]["edges"]]
        assert tie_count["count"] == original["connection_tie"]["classes"]
        row["tie"] = {"edges": tie_edges, **tie_count}
        counts = Counter(u["kind"] for u in data["layout"]["units"])
        slot_counts = [r["input_slots"] for u in data["layout"]["units"]
                       for r in recipe_rows if r["kind"] == u["kind"]]
        switches = len(data["settings"]["switches"])
        belts = counts["传送带"]
        others = len(data["layout"]["units"]) - belts
        row["axis_numbers"] = {"A": others, "L": belts, "B": counts["协议储存箱"], "F": switches,
            "unconstrained_build_orders": math.factorial(others) * math.factorial(belts),
            "phase_raw_domain": 6 ** counts["协议储存箱"], "switch_raw_domain": 2 ** switches,
            "input_slots": sum(slot_counts), "slot_raw_orders": math.factorial(sum(slot_counts)),
            "slot_projected_orders": math.prod(math.factorial(s) for s in slot_counts),
            "belt_shape_domain": 3 ** belts, "belt_shape_with_direction": 12 ** belts}
        row["branch_projection"] = branch_projection(data)
        results["examples"].append(row)
    results["reviewed_fingerprint_stable"] = before == {str(p): digest(p) for p in source_paths}
    assert results["reviewed_fingerprint_stable"]
    results["upstream_fingerprint_changes"] = [r["path"] for r in claimed["sources"]
                                               if digest(Path(r["path"])) != r["sha256"]]
    results["status"] = "passed"
    (HERE / "复核-r1-覆盖-独立复算.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": results["status"], "axes": len(config_axes),
        "small_graph_validation": results["small_graph_validation"],
        "counts": [{"name": r["name"], "counts": {k: v["count"] for k, v in r["graphs"].items()},
                    "tie": r["tie"]["count"], "branch": r["branch_projection"]} for r in results["examples"]],
        "upstream_fingerprint_changes": results["upstream_fingerprint_changes"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
