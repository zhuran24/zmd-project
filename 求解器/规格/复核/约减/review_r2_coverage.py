#!/usr/bin/env python3
"""第二轮覆盖复核：独立重建样例几何、冲突图、独立块划分与完整分支映射。"""
import hashlib
import itertools
import json
import math
import re
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAMES = ("混做粉碎机两下游", "分流器三路轮询")
READS = {}


def read(path):
    raw = path.read_bytes()
    READS[str(path)] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def load(path):
    return json.loads(read(path))


def number(value):
    return int(value["value"])


def owner(port):
    return port.split(":")[0]


def geometry(data, kinds):
    """旋转格坐标与法向；完全重合共边且角色互补才成边。"""
    ports = []
    cells = set()
    for unit in data["layout"]["units"]:
        kind = kinds[unit["kind"]]
        width = number(kind["dimensions"]["width"])
        height = number(kind["dimensions"]["height"])
        turns = int(unit["rotation"][1:]) // 90
        ox, oy = map(number, unit["origin"])

        def rotate(x, y, dx, dy):
            w, h = width, height
            for _ in range(turns):
                x, y, dx, dy = h - 1 - y, x, -dy, dx
                w, h = h, w
            return x + ox, y + oy, dx, dy

        occupied = {rotate(x, y, 0, 0)[:2] for x in range(width) for y in range(height)}
        assert not cells & occupied
        assert all(0 <= x < 70 and 0 <= y < 70 for x, y in occupied)
        cells |= occupied
        # 两份受核样例无桥；不把这个工具冒称一般桥定向解释器。
        assert unit["bridge_axes"] is None
        for group in kind["ports"]["layouts"][unit["port_layout"]]:
            side = group["side"]
            for position in group["positions"]:
                p = number(position)
                local = {"south": (p, 0, 0, -1), "north": (p, height - 1, 0, 1),
                         "west": (0, p, -1, 0), "east": (width - 1, p, 1, 0)}[side]
                ports.append((f"{unit['id']}:{side}:{p}", group["role"],
                              kind["family"], rotate(*local)))
    channels = {}
    for source in ports:
        for target in ports:
            if source[1] != "output" or target[1] != "input":
                continue
            if "transport" not in (source[2], target[2]):
                continue
            x, y, dx, dy = source[3]
            if target[3] == (x + dx, y + dy, -dx, -dy):
                label = f"PC|{source[0]}|{target[0]}"
                channels[label] = {"id": label, "source_port": source[0], "target_port": target[0]}
    declared = {row["id"]: row for row in data["layout"]["physical_channels"]}
    assert len(declared) == len(data["layout"]["physical_channels"])
    assert channels == declared
    return channels, len(cells)


def graphs(data, channels, kinds):
    """由端点库存及同侧竞争关系直接构图，不调用被复核读写集生成器。"""
    units = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    params = {axis: decision["value"] for group in
              ("fixed", "offline_mutable", "fixedness_unproven")
              for axis, decision in data["parameters"][group].items()}
    templates = params["judgment.order"]["template_order"]
    expected = {("move", label) for label in channels}
    expected |= {("manufacture", uid) for uid, kind in units.items()
                 if kinds[kind]["family"] == "manufacturing"}
    expected |= {("transfer", uid) for uid, kind in units.items() if kind == "协议储存箱"}
    assert {(x["operation"], x["target"]) for x in templates} == expected
    assert len(templates) == len(expected)
    assert all(not row["enabled"] for row in data["settings"]["switches"]
               if row["function"] == "transfer")

    def inventory(uid):
        return "warehouse" if units[uid] in ("仓库取货口", "协议核心") else uid

    ends = {cid: (owner(c["source_port"]), owner(c["target_port"])) for cid, c in channels.items()}
    watched = {inventory(src) for src, dst in ends.values() if units[dst] == "物品准入口"}
    effects, observations, barriers = [], [], []
    all_inventory = {inventory(uid) for pair in ends.values() for uid in pair}
    for template in templates:
        operation, target = template["operation"], template["target"]
        if operation == "move":
            src, dst = ends[target]
            effect = {inventory(src), inventory(dst)}
            observe = {inventory(uid) for a, b in ends.values() if a == src or b == dst for uid in (a, b)}
            barrier = bool(effect & watched) or units[dst] == "物品准入口"
        elif operation == "manufacture":
            effect = observe = {inventory(target)}
            barrier = bool(effect & watched)
        else:
            effect, observe, barrier = set(), set(), False
        effects.append(effect)
        observations.append(observe)
        barriers.append(barrier)
    semantic, operational = [], []
    for a, b in itertools.combinations(range(len(templates)), 2):
        conflict = (barriers[a] or barriers[b] or bool(effects[a] & observations[b])
                    or bool(effects[b] & observations[a]) or bool(effects[a] & effects[b]))
        if conflict:
            semantic.append((a, b))
        opa, opb = templates[a]["operation"], templates[b]["operation"]
        extra = (opa == opb == "move" or opa == opb == "manufacture"
                 or opa == "move" and bool(effects[b] & all_inventory)
                 or opb == "move" and bool(effects[a] & all_inventory))
        if conflict or extra:
            operational.append((a, b))
    return templates, semantic, operational, [i for i, flag in enumerate(barriers) if flag]


def partition_count(n, edges):
    """数无标号独立块划分，求色多项式的下降阶乘系数；不使用删缩或源点容斥。"""
    adjacency = [0] * n
    for a, b in edges:
        adjacency[a] |= 1 << b
        adjacency[b] |= 1 << a

    @lru_cache(None)
    def independent(mask):
        if not mask:
            return True
        bit = mask & -mask
        index = bit.bit_length() - 1
        return not adjacency[index] & mask and independent(mask ^ bit)

    @lru_cache(None)
    def partitions(mask):
        if not mask:
            return (1,)
        # 包含最小顶点的块唯一，消除了块标签造成的重复计数。
        pivot = mask & -mask
        index = pivot.bit_length() - 1
        eligible = (mask ^ pivot) & ~adjacency[index]
        result = [0] * (mask.bit_count() + 1)
        subset = eligible
        while True:
            if independent(subset):
                for k, value in enumerate(partitions(mask ^ subset ^ pivot)):
                    result[k + 1] += value
            if not subset:
                break
            subset = (subset - 1) & eligible
        return tuple(result)

    coefficients = partitions((1 << n) - 1)
    result = sum((-1) ** (n + k) * math.factorial(k) * value
                 for k, value in enumerate(coefficients))
    return {"classes": result, "independent_partition_coefficients": coefficients,
            "memoized_subproblems": partitions.cache_info().currsize}


def table_values(table, rows):
    assert table["schema"] == "damping-branch-v2"
    assert table["fixedness"] == "by_available_set"
    assert table["evaluations"] == [] and table["on_missing"] == "unresolved"
    lookup = {(row["fork_unit"], tuple(row["available_channels"])): row["outgoing_channel"]
              for row in table["choices"]}
    assert len(lookup) == len(table["choices"]) == len(rows)
    assert set(lookup) == {(uid, domain) for uid, domain, _ in rows}
    assert all(lookup[uid, domain] in domain for uid, domain, _ in rows)
    return tuple(lookup[uid, domain] for uid, domain, _ in rows)


def branches(data, channels, kinds, saved, validation):
    units = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    mutable = sorted(cid for cid, c in channels.items() if units[owner(c["target_port"])] == "物品准入口")
    rows, forks = [], []
    for uid in sorted(units):
        if units[uid] != "分流器":
            continue
        outgoing = sorted(cid for cid, c in channels.items() if owner(c["source_port"]) == uid)
        permanent = set(outgoing) - set(mutable)
        local = [(uid, subset, permanent <= set(subset)) for size in range(1, len(outgoing) + 1)
                 for subset in itertools.combinations(outgoing, size)]
        rows.extend(local)
        forks.append({"unit": uid, "outgoing": outgoing, "permanent": sorted(permanent),
                      "full": math.prod(len(d) for _, d, _ in local),
                      "projection": math.prod(len(d) for _, d, keep in local if keep)})
    subgraphs, max_levels = [], {}
    for flags in itertools.product((False, True), repeat=len(mutable)):
        cut = {cid for cid, flag in zip(mutable, flags) if flag}
        levels = {}
        for uid, kind in units.items():
            if kinds[kind]["family"] in ("transport", "power"):
                continue
            categories = {cid if units[owner(c["target_port"])] == "汇流器" else "other"
                          for cid, c in channels.items() if cid not in cut and owner(c["source_port"]) == uid}
            levels[uid] = len(categories)
            max_levels[uid] = max(max_levels.get(uid, 0), len(categories))
        subgraphs.append({"cut": sorted(cut), "levels": levels})
    assert all(n <= 1 for n in max_levels.values())
    representatives = [table_values(table, rows) for table in validation["projected_representatives"]]
    behavior = [table_values(table, rows) for table in validation["behavior_representatives"]]
    assert behavior == [tuple(domain[0] for _, domain, _ in rows)]
    assert table_values(saved["canonical_behavior_table"], rows) == behavior[0]
    originals = list(itertools.product(*(domain for _, domain, _ in rows)))
    assert len(originals) == len(validation["original_to_representative"])
    assert len(set(representatives)) == len(representatives)
    assert validation["row_order"] == [{"fork_unit": uid, "available_channels": list(domain)} for uid, domain, _ in rows]
    counts, query_checks = Counter(), 0
    for values, mapping in zip(originals, validation["original_to_representative"]):
        normalized = tuple(value if keep else domain[0] for value, (_, domain, keep) in zip(values, rows))
        assert mapping["original_choices"] == list(values)
        assert representatives[mapping["projected_representative"]] == normalized
        assert mapping["behavior_representative"] == 0
        counts[normalized] += 1
        lookup = {(uid, domain): value for (uid, domain, _), value in zip(rows, values)}
        reduced = {(uid, domain): value for (uid, domain, _), value in zip(rows, normalized)}
        for graph in subgraphs:
            for fork in forks:
                domain = tuple(cid for cid in fork["outgoing"] if cid not in graph["cut"])
                if domain:
                    assert lookup[fork["unit"], domain] == reduced[fork["unit"], domain]
                    query_checks += 1
    assert len(originals) == saved["full_tables"]
    assert len(counts) == saved["projected_tables"]
    assert saved["output_level_upper_bounds"] == max_levels
    assert saved["no_damping_queries"] and saved["no_query_behavior_representatives"] == 1
    assert sorted(counts.values()) == validation["projection_class_sizes"]
    assert query_checks == validation["hypothetical_local_query_comparisons"]
    return {"forks": forks, "gate_subgraphs": subgraphs, "max_output_levels": max_levels,
            "full_tables": len(originals), "projected_tables": len(counts), "behavior_tables": 1,
            "class_sizes": sorted(counts.values()), "local_query_comparisons": query_checks}


def axis_checks(catalog):
    config = load(ROOT / "规格/内核配置-v1.json")
    declaration = read(ROOT / "规格/受限模型声明.md")
    registry = read(ROOT / "规格/选择点参数轴.md")
    document = read(ROOT / "规格/参数扫描约减.md")
    configured = sorted(axis for axis, row in config["axes"].items() if row["disposition"] == "由输入全称量化")
    declared = sorted(line.split("`")[1] for line in declaration.splitlines()
                      if line.startswith("| `") and "| 由输入全称量化 |" in line)
    numbered = re.findall(r"^\| (\d+) \| `([^`]+)`", document, re.M)
    assert [int(i) for i, _ in numbered] == list(range(1, 16))
    assert configured == declared == sorted(axis for _, axis in numbered)
    assert all(f"| `{axis}` |" in registry for axis in configured)
    recipes = []
    for unit in catalog["units"]:
        if unit["family"] != "manufacturing":
            continue
        domains = [set(recipe["inputs"]) for recipe in catalog["recipes"] if recipe["kind"] == unit["id"]]
        slots = sum(number(row["count"]) for row in unit["inventory"] if row["role"] == "input")
        # 任意两配方的输入种类并集超出格数，则没有任何状态能同时匹配。
        assert all(len(a | b) > slots for a, b in itertools.combinations(domains, 2))
        recipes.append({"kind": unit["id"], "recipes": len(domains), "slots": slots})
    return {"axes": configured, "count": len(configured), "recipes": recipes,
            "recipe_raw": math.factorial(len(catalog["recipes"])),
            "recipe_per_kind": math.prod(math.factorial(row["recipes"]) for row in recipes),
            "recipe_behavior": 1}


def main():
    stored = load(HERE / "等价类计数.json")
    validation = load(HERE / "分支表约减验证.json")
    load(HERE / "验证结果.json")
    for name in ("count_classes.py", "verify_reduction.py", "verify_branch_projection.py",
                 "事件对清单.md", "修订记录.md", "修订-r1-自查.log"):
        read(HERE / name)
    catalog = load(ROOT / "数据/正式静态目录.json")
    for name in ("《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt"):
        read(ROOT.parent / name)
    for name in ("受限转移定义.md", "内核输入.md", "运行语义.md"):
        read(ROOT / "规格" / name)
    kinds = {unit["id"]: unit for unit in catalog["units"]}
    report = {"schema": "coverage-review-r2", "axes": axis_checks(catalog), "examples": []}
    for name in NAMES:
        data = load(ROOT / "数据/样例" / f"{name}.json")
        reference = next(row for row in stored["examples"] if row["name"] == name)
        branch_reference = next(row for row in validation["examples"] if row["name"] == name)
        channels, area = geometry(data, kinds)
        templates, semantic, operational, barriers = graphs(data, channels, kinds)
        result = {"name": name, "physical_channels": sorted(channels), "occupied_area": area,
                  "template_count": len(templates), "barriers": barriers, "modes": {}}
        for mode, edges in (("semantic_sweep", semantic), ("operational_conservative", operational)):
            expected = reference["modes"][mode]
            assert edges == [tuple(edge) for edge in expected["edges"]]
            assert expected["template_count"] == len(templates)
            assert expected["raw_orders"] == math.factorial(len(templates))
            assert len(expected["pairs"]) == math.comb(len(templates), 2)
            for pair, endpoints in zip(expected["pairs"], itertools.combinations(range(len(templates)), 2)):
                assert (pair["left"], pair["right"]) == endpoints
                assert pair["conflict"] == (endpoints in edges)
                assert bool(pair["resources"]) == pair["conflict"]
            counted = partition_count(len(templates), edges)
            assert counted["classes"] == expected["classes"] == expected["independent_source_count"]
            counted.update({"edges": edges, "edge_count": len(edges), "raw_orders": math.factorial(len(templates))})
            result["modes"][mode] = counted
        times = {event["id"]: Fraction(event["time"]["value"]["value"])
                 for event in data["timeline"]["events"] if event["time"]}
        built = {row["unit"]: times[row["event"]] for row in data["construction"]["moments"]}
        tie_order = reference["connection_tie"]["channel_order"]
        assert set(tie_order) == set(channels)
        ties = []
        for i, j in itertools.combinations(range(len(tie_order)), 2):
            a, b = channels[tie_order[i]], channels[tie_order[j]]
            aa = owner(a["source_port"]), owner(a["target_port"])
            bb = owner(b["source_port"]), owner(b["target_port"])
            if (aa[0] == bb[0] or aa[1] == bb[1]) and max(map(built.get, aa)) == max(map(built.get, bb)):
                ties.append((i, j))
        assert ties == [tuple(edge) for edge in reference["connection_tie"]["edges"]]
        result["connection_tie"] = partition_count(len(channels), ties)
        assert result["connection_tie"]["classes"] == reference["connection_tie"]["classes"]
        result["branches"] = branches(data, channels, kinds, reference["damping_branch"], branch_reference)
        types = Counter(unit["kind"] for unit in data["layout"]["units"])
        slots = [sum(number(row["count"]) for row in kinds[unit["kind"]]["inventory"] if row["role"] == "input")
                 for unit in data["layout"]["units"] if kinds[unit["kind"]]["family"] == "manufacturing"]
        features = sum(len(kinds[unit["kind"]]["powered_functions"]) for unit in data["layout"]["units"])
        result["other_domains"] = {"builds": len(data["layout"]["units"]), "belts": types["传送带"],
                                    "blueprint_orders_without_extra_relations": math.factorial(sum(types.values()) - types["传送带"]) * math.factorial(types["传送带"]),
                                    "switches": 2 ** features, "phase_raw": 6 ** types["协议储存箱"],
                                    "input_slots_raw": math.factorial(sum(slots)),
                                    "input_slots_projected": math.prod(math.factorial(n) for n in slots),
                                    "belt_shape_raw": 3 ** types["传送带"]}
        report["examples"].append(result)
        print(json.dumps({"name": name, "counts": {mode: row["classes"] for mode, row in result["modes"].items()},
                          "branch": {k: result["branches"][k] for k in ("full_tables", "projected_tables", "behavior_tables")}}, ensure_ascii=False), flush=True)
    report["stored_source_drift"] = []
    for filename, artifact in (("等价类计数.json", stored), ("分支表约减验证.json", validation)):
        for source in artifact["sources"]:
            actual = hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest()
            if actual != source["sha256"]:
                report["stored_source_drift"].append({"artifact": filename, "path": source["path"],
                                                       "recorded": source["sha256"], "current": actual})
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in READS.items()), "独立复算期间输入发生变化"
    report["sources"] = [{"path": path, "sha256": digest} for path, digest in sorted(READS.items())]
    report["status"] = "independent_counts_passed"
    (HERE / "复核-r2-覆盖-独立复算.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
