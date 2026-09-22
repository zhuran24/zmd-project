#!/usr/bin/env python3
"""第二轮独立结构复算；只写本席 JSON，禁止覆盖被审产物。"""
import hashlib
import importlib.util
import itertools
import json
import math
import sys
from collections import Counter
from functools import cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subsets(items):
    return [tuple(group) for size in range(1, len(items) + 1)
            for group in itertools.combinations(sorted(items), size)]


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def geometry(data, kinds):
    """从格边中点和法向独立重建共边端口，整数使用半格坐标。"""
    ports = []
    units = {u["id"]: u for u in data["layout"]["units"]}
    for uid, unit in units.items():
        kind = kinds[unit["kind"]]
        width = int(kind["dimensions"]["width"]["value"])
        height = int(kind["dimensions"]["height"]["value"])
        turns = int(unit["rotation"][1:]) // 90
        origin = [int(x["value"]) for x in unit["origin"]]
        layouts = kind["ports"]["layouts"]
        if not layouts:
            continue
        for group in layouts[unit["port_layout"]]:
            side = group["side"]
            for position in group["positions"]:
                pos = int(position["value"])
                point, normal = {
                    "south": ((2 * pos + 1, 0), (0, -1)),
                    "north": ((2 * pos + 1, 2 * height), (0, 1)),
                    "west": ((0, 2 * pos + 1), (-1, 0)),
                    "east": ((2 * width, 2 * pos + 1), (1, 0)),
                }[side]
                x, y = point
                nx, ny = normal
                w, h = width, height
                for _ in range(turns):
                    x, y = 2 * h - y, x
                    nx, ny = -ny, nx
                    w, h = h, w
                ports.append((f"{uid}:{side}:{pos}", uid, group["role"],
                              (x + 2 * origin[0], y + 2 * origin[1]), (nx, ny)))
    channels = {}
    for left in ports:
        for right in ports:
            if left[1] == right[1] or left[2] != "output" or right[2] != "input":
                continue
            if left[3] != right[3] or left[4] != tuple(-x for x in right[4]):
                continue
            if not any(kinds[units[u]["kind"]]["family"] == "transport" for u in (left[1], right[1])):
                continue
            channels[f"PC|{left[0]}|{right[0]}"] = (left[0], right[0])
    declared = {c["id"]: (c["source_port"], c["target_port"])
                for c in data["layout"]["physical_channels"]}
    assert channels == declared, (channels.keys() - declared.keys(), declared.keys() - channels.keys())
    return channels


def independent_footprints(data, channels, templates, strict):
    """由独立文档资源定义重建，未调用被审读写集函数。"""
    units = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    switches = {x["unit"]: x["enabled"] for x in data["settings"]["switches"]}
    owner = lambda port: port.split(":")[0]
    inventory = lambda uid: "warehouse" if units[uid] in ("协议核心", "仓库取货口") else "inventory:" + uid
    physical = {}
    for channel, ports in channels.items():
        src, dst = map(owner, ports)
        resources = {inventory(src), inventory(dst), "graph", "constants"}
        resources.update("usage:" + port for port in ports)
        resources.update("gate:" + uid for uid in (src, dst) if units[uid] == "物品准入口")
        if units[dst] == "协议核心":
            resources.add("empty_order")
        physical[channel] = resources
    watched = {"graph"}
    for src, dst in channels.values():
        if units[owner(dst)] == "物品准入口":
            watched.update((inventory(owner(src)), "gate:" + owner(dst)))
    all_reads = set().union(*physical.values())
    answer = []
    for template in templates:
        op, target = template["operation"], template["target"]
        reads, writes = {"constants", "maintenance_barrier"}, set()
        if op == "move":
            source_port, target_port = channels[target]
            src, dst = owner(source_port), owner(target_port)
            reads.update(("poll:" + src + ":output", "poll:" + dst + ":input"))
            writes.update(reads - {"constants", "maintenance_barrier"})
            for channel, (other_src, other_dst) in channels.items():
                if owner(other_src) == src or owner(other_dst) == dst:
                    reads.update(physical[channel])
            writes.update((inventory(src), inventory(dst), "usage:" + source_port, "usage:" + target_port))
            if units[dst] == "物品准入口":
                writes.update(("graph", "gate:" + dst, "pending:" + dst))
            if units[dst] == "协议核心":
                reads.update(("warehouse", "empty_order", "ledger"))
                writes.update(("warehouse", "empty_order", "ledger"))
            if strict:
                reads.update(all_reads | {"derived_levels"})
                writes.add("derived_levels")
        elif op == "manufacture":
            writes.update((inventory(target), "progress:" + target, "pending:" + target))
            if strict:
                writes.add("pending_array")
            reads.update(writes)
        elif op == "transfer":
            if switches[target]:
                writes.update((inventory(target), "progress:" + target, "warehouse", "empty_order", "ledger"))
                reads.update(writes)
        else:
            raise AssertionError(op)
        if any(kind == "物品准入口" for kind in units.values()) and writes & watched:
            writes.add("maintenance_barrier")
        answer.append((reads, writes))
    return answer


@cache
def count_orientations(vertices, edges):
    """按删边缩边和单纯点插入独立计数，不调用被审计数器。"""
    if not edges:
        return 1
    neighbors = {v: set() for v in vertices}
    edge_set = set(edges)
    for u, v in edges:
        neighbors[u].add(v)
        neighbors[v].add(u)
    for v in vertices:
        adj = sorted(neighbors[v])
        if all((a, b) in edge_set for a, b in itertools.combinations(adj, 2)):
            return (len(adj) + 1) * count_orientations(
                tuple(u for u in vertices if u != v), tuple(e for e in edges if v not in e))
    u, v = edges[0]
    deleted = edges[1:]
    contracted = set()
    for a, b in deleted:
        a, b = (u if a == v else a), (u if b == v else b)
        if a != b:
            contracted.add(tuple(sorted((a, b))))
    return count_orientations(vertices, deleted) + count_orientations(
        tuple(x for x in vertices if x != v), tuple(sorted(contracted)))


def branch_checks(data, channels, kinds, stored, mapping, target_module):
    units = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    endpoints = {c: (s.split(":")[0], d.split(":")[0]) for c, (s, d) in channels.items()}
    cuttable = sorted(c for c, (_, dst) in endpoints.items() if units[dst] == "物品准入口")
    forks = {u: sorted(c for c, (src, _) in endpoints.items() if src == u)
             for u, kind in units.items() if kind == "分流器"}
    domains, keep = [], []
    for fork in sorted(forks):
        permanent = set(forks[fork]) - set(cuttable)
        for domain in subsets(forks[fork]):
            domains.append((fork, domain))
            keep.append(permanent <= set(domain))
    full_count = math.prod(len(domain) for _, domain in domains)
    graph_count = 0
    levels_max = {}
    for bits in range(1 << len(cuttable)):
        active = set(channels) - {c for i, c in enumerate(cuttable) if bits >> i & 1}
        graph_count += 1
        for uid, kind in units.items():
            if kinds[kind]["family"] in ("transport", "power"):
                continue
            levels = {c if units[dst] == "汇流器" else "other"
                      for c, (src, dst) in endpoints.items() if c in active and src == uid}
            levels_max[uid] = max(levels_max.get(uid, 0), len(levels))
    assert all(n <= 1 for n in levels_max.values())
    assert levels_max == stored["output_level_upper_bounds"]
    signatures = Counter()
    points = list(itertools.product(*(domain for _, domain in domains)))
    assert len(points) == len(mapping["original_to_representative"]) == full_count
    query_count = 0
    for original, saved in zip(points, mapping["original_to_representative"]):
        projected = tuple(value if retained else domain[0]
                          for value, (_, domain), retained in zip(original, domains, keep))
        behavior = tuple(domain[0] for _, domain in domains)
        signatures[projected] += 1
        assert list(original) == saved["original_choices"]
        representative = mapping["projected_representatives"][saved["projected_representative"]]
        actual = {(r["fork_unit"], tuple(r["available_channels"])): r["outgoing_channel"]
                  for r in representative["choices"]}
        assert tuple(actual[key] for key in domains) == projected
        assert saved["behavior_representative"] == 0
        behavior_table = mapping["behavior_representatives"][0]
        assert tuple(r["outgoing_channel"] for r in behavior_table["choices"]) == behavior
        table = {**behavior_table, "choices": [
            {"fork_unit": fork, "available_channels": list(domain), "outgoing_channel": value}
            for (fork, domain), value in zip(domains, original)]}
        assert target_module.normalize_branch_table(table, stored) == representative
        assert target_module.normalize_branch_table(table, stored, "no_queries") == behavior_table
        lookup, normalized = dict(zip(domains, original)), dict(zip(domains, projected))
        for bits in range(1 << len(cuttable)):
            active = set(channels) - {c for i, c in enumerate(cuttable) if bits >> i & 1}
            for fork, outgoing in forks.items():
                available = tuple(c for c in outgoing if c in active)
                if available:
                    assert lookup[fork, available] == normalized[fork, available]
                    query_count += 1
    assert len(signatures) == stored["projected_tables"]
    assert sorted(signatures.values()) == mapping["projection_class_sizes"]
    assert full_count == stored["full_tables"]
    assert query_count == mapping["hypothetical_local_query_comparisons"]
    generated = list(target_module.branch_representatives(stored))
    assert generated == mapping["projected_representatives"]
    return {"full_tables": full_count, "projected_tables": len(signatures),
            "behavior_tables": 1, "gate_subgraphs": graph_count,
            "hypothetical_queries": query_count, "maximum_output_levels": levels_max}


def main():
    results = read(HERE / "等价类计数.json")
    branch_report = read(HERE / "分支表约减验证.json")
    before = {row["path"]: digest(Path(row["path"])) for row in branch_report["sources"]}
    target = load_module("count_classes")
    checks = load_module("verify_reduction")
    current = target.calculate()
    # 单列并行源漂移，绝不覆写旧报告或给旧报告补新指纹。
    source_changes = [p for p, value in before.items()
                      if value != next(r["sha256"] for r in branch_report["sources"] if r["path"] == p)]
    assert json.loads(json.dumps(current["examples"])) == results["examples"]
    catalog = read(ROOT / "数据/正式静态目录.json")
    kinds = {u["id"]: u for u in catalog["units"]}
    report = {"status": "结构复算通过；源漂移及运行限制单列", "source_changes_since_reviewed_evidence": source_changes,
              "examples": [], "brute_checks": checks.brute_checks(), "recipe_checks": checks.recipe_checks()}
    for row in results["examples"]:
        data = read(ROOT / "数据/样例" / (row["name"] + ".json"))
        channels = geometry(data, kinds)
        example = {"name": row["name"], "geometry_pc_count": len(channels), "modes": {}}
        for mode, saved in row["modes"].items():
            footprints = independent_footprints(data, channels, [t["template"] for t in saved["templates"]],
                                               mode == "operational_conservative")
            edges = []
            for i, (reads, writes) in enumerate(footprints):
                assert reads == set(saved["templates"][i]["reads"])
                assert writes == set(saved["templates"][i]["writes"])
            for i, j in itertools.combinations(range(len(footprints)), 2):
                ri, wi = footprints[i]
                rj, wj = footprints[j]
                if wi & (rj | wj) or wj & (ri | wi):
                    edges.append((i, j))
            assert [list(e) for e in edges] == saved["edges"]
            count = count_orientations(tuple(range(len(footprints))), tuple(edges))
            assert count == saved["classes"]
            example["modes"][mode] = {"pairs_checked": math.comb(len(footprints), 2),
                                       "conflicts": len(edges), "classes": count}
        mapping = next(e for e in branch_report["examples"] if e["name"] == row["name"])
        example["branch"] = branch_checks(data, channels, kinds, row["damping_branch"], mapping, target)
        report["examples"].append(example)
    report["runtime_probes"] = checks.runtime_probes()
    report["sources"] = before
    report["source_changes_during_check"] = [p for p, value in before.items() if digest(Path(p)) != value]
    assert not report["source_changes_during_check"]
    path = HERE / "独立重推-r2-核验结果.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "examples": report["examples"],
                      "source_changes": source_changes, "runtime": report["runtime_probes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
