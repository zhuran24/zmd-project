#!/usr/bin/env python3
"""独立组合核验、目录配方支持集核验及当前运行入口探针。"""
import copy
import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

from count_classes import (AXES, HERE, NAMES, ROOT, count_by_sources,
                           orientation_count, read_json)
from verify_branch_projection import verify_branch_projection


def signature(order, edges):
    positions = {v: i for i, v in enumerate(order)}
    return tuple(positions[a] < positions[b] for a, b in edges)


def brute_checks():
    graph_count = 0
    permutation_count = 0
    adjacency_component_checks = 0
    for n in range(6):
        possible = tuple(itertools.combinations(range(n), 2))
        permutations = list(itertools.permutations(range(n)))
        for bits in range(1 << len(possible)):
            edges = tuple(e for i, e in enumerate(possible) if bits & (1 << i))
            classes = {signature(order, edges) for order in permutations}
            assert orientation_count(n, edges) == len(classes)
            assert count_by_sources(n, edges) == len(classes)
            graph_count += 1
            permutation_count += len(permutations)
            if n <= 4:
                unseen = set(permutations)
                found = []
                edge_set = set(edges)
                while unseen:
                    first = min(unseen)
                    stack = [first]
                    members = set()
                    while stack:
                        order = stack.pop()
                        if order not in unseen:
                            continue
                        unseen.remove(order)
                        members.add(order)
                        for i in range(n - 1):
                            if tuple(sorted(order[i:i + 2])) not in edge_set:
                                swapped = order[:i] + (order[i + 1], order[i]) + order[i + 2:]
                                stack.append(swapped)
                    signatures = {signature(order, edges) for order in members}
                    assert len(signatures) == 1
                    found.append(next(iter(signatures)))
                assert len(found) == len(set(found)) == len(classes)
                adjacency_component_checks += 1
    return {"graphs": graph_count, "permutations": permutation_count,
            "adjacent_swap_component_graphs": adjacency_component_checks, "status": "passed"}


def recipe_checks():
    catalog = read_json(ROOT / "数据/正式静态目录.json")
    rows, product = [], 1
    for unit in catalog["units"]:
        if unit["family"] != "manufacturing":
            continue
        recipes = [r for r in catalog["recipes"] if r["kind"] == unit["id"]]
        slots = sum(int(x["count"]["value"]) for x in unit["inventory"] if x["role"] == "input")
        species = sorted(set().union(*(set(r["inputs"]) for r in recipes)))
        maximum = tested = 0
        for size in range(slots + 1):
            for support in itertools.combinations(species, size):
                # 原料种类已齐是数量满足的必要条件，故此检查给候选数的上界。
                matches = sum(set(r["inputs"]) <= set(support) for r in recipes)
                maximum = max(maximum, matches)
                tested += 1
        assert maximum <= 1
        product *= math.factorial(len(recipes))
        rows.append({"kind": unit["id"], "input_slots": slots, "recipe_count": len(recipes),
                     "support_sets": tested, "max_simultaneous_candidates": maximum})
    assert product == 3456
    return {"status": "passed", "rows": rows, "per_kind_order_product": product,
            "reduced_classes": 1,
            "scope": "当前目录、单种格、输入并集、全部原料物种齐备；非输入物种不能新增候选"}


def runtime_probes():
    sys.path.insert(0, str(ROOT / "数据/样例"))
    from check_golden_trace import run
    rows = []
    for name in NAMES:
        data = read_json(ROOT / ("数据/样例/" + name + ".json"))
        try:
            ticks = run(copy.deepcopy(data))
        except Exception as error:
            rows.append({"name": name, "status": "not_executed",
                         "error_type": type(error).__name__, "reason": str(error),
                         "interpretation": "原样输入未通过参考入口；未绕过校验，不作换序运行通过声明"})
        else:
            rows.append({"name": name, "status": "baseline_only", "ticks": len(ticks),
                         "interpretation": "仅参考原样例基线；入口逐轴要求固定样例值，未声称任意排序差分通过"})
    return rows


def main():
    results = read_json(HERE / "等价类计数.json")
    changed = [row["path"] for row in results["sources"]
               if hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() != row["sha256"]]
    config = read_json(ROOT / "规格/内核配置-v1.json")
    actual = sorted(a for a, row in config["axes"].items() if row["disposition"] == "由输入全称量化")
    declaration = (ROOT / "规格/受限模型声明.md").read_text()
    doc = (ROOT / "规格/参数扫描约减.md").read_text()
    table_axes = [line.split("`")[1] for line in declaration.splitlines()
                  if line.startswith("| `") and "| 由输入全称量化 |" in line]
    assert actual == sorted(AXES) == sorted(table_axes)
    assert all(f"`{axis}`" in doc for axis in AXES)
    brute = brute_checks()
    recipe = recipe_checks()
    branch_counts = {str(d): math.prod(k ** math.comb(d, k) for k in range(1, d + 1))
                     for d in range(1, 4)}
    assert branch_counts == {"1": 1, "2": 2, "3": 24}
    assert not changed, "源指纹变化，先重跑count_classes并核论证，不能沿用旧计数"
    branch = verify_branch_projection(results)
    report = {"schema": "reduction-validation-v2", "axes_count": len(actual),
              "axis_declaration_config_document": "passed", "source_fingerprint_changes": changed,
              "combinatorial_bruteforce": brute, "recipe_uniqueness": recipe,
              "branch_table_counts": branch_counts,
              "branch_projection": branch,
              "runtime_probes": runtime_probes(),
              "scope": "证明稿自查和组合算法验证；不是Rust内核参数族的穷举运行"}
    changed = [row["path"] for row in results["sources"]
               if hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() != row["sha256"]]
    assert not changed, "自查期间源文件变化，须重跑"
    report["status"] = "passed_with_runtime_limitations" if not changed else "source_changed_recheck_required"
    (HERE / "验证结果.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "graphs": brute["graphs"],
                      "permutations": brute["permutations"], "source_changes": len(changed),
                      "branch_projection": branch,
                      "runtime": report["runtime_probes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
