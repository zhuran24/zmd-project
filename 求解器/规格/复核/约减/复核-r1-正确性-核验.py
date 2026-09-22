#!/usr/bin/env python3
"""正确性复核的只读重算；仅将复核结果写在本文件所在目录。"""
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path

import count_classes as subject
import verify_reduction as validation


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_graph(data, strict):
    """从动作类型及资源所属者重建冲突边，不调用被审读写集函数。"""
    kinds = {row["id"]: row["kind"] for row in data["layout"]["units"]}
    channels = data["layout"]["physical_channels"]
    channel_map = {row["id"]: row for row in channels}
    templates = data["parameters"]["fixed"]["judgment.order"]["value"]["template_order"]
    switches = {row["unit"]: row["enabled"] for row in data["settings"]["switches"]
                if row["function"] == "transfer"}

    def owner(port):
        return port.split(":")[0]

    def store(unit):
        return "warehouse" if kinds[unit] in {"协议核心", "仓库取货口"} else unit

    def endpoints(channel):
        return owner(channel["source_port"]), owner(channel["target_port"])

    all_inventory = {store(unit) for channel in channels for unit in endpoints(channel)}
    gate_sources = {store(owner(channel["source_port"])) for channel in channels
                    if kinds[owner(channel["target_port"])] == "物品准入口"}
    rows = []
    for template in templates:
        operation, target = template["operation"], template["target"]
        read_inventory, write_inventory, sides = set(), set(), set()
        graph_change = False
        if operation == "move":
            channel = channel_map[target]
            source, dest = endpoints(channel)
            sides = {(source, "output"), (dest, "input")}
            for peer in channels:
                left, right = endpoints(peer)
                if left == source or right == dest:
                    read_inventory.update((store(left), store(right)))
            write_inventory.update((store(source), store(dest)))
            graph_change = kinds[dest] == "物品准入口"
            if strict:
                read_inventory.update(all_inventory)
        elif operation == "manufacture":
            read_inventory.add(target)
            write_inventory.add(target)
        elif operation == "transfer" and switches[target]:
            read_inventory.update((target, "warehouse"))
            write_inventory.update((target, "warehouse"))
        barrier = graph_change or bool(write_inventory & gate_sources)
        rows.append((operation, read_inventory, write_inventory, sides, barrier))

    edges = set()
    for i, j in itertools.combinations(range(len(rows)), 2):
        a, ar, aw, aside, ab = rows[i]
        b, br, bw, bside, bb = rows[j]
        inventory_conflict = bool(aw & (br | bw) or bw & (ar | aw))
        extra = strict and ((a == b == "move") or (a == b == "manufacture"))
        if ab or bb or inventory_conflict or aside & bside or extra:
            edges.add((i, j))
    return edges, [i for i, row in enumerate(rows) if row[-1]]


def main():
    protected = [ROOT / "规格/参数扫描约减.md"] + [HERE / name for name in (
        "count_classes.py", "verify_reduction.py", "等价类计数.json", "事件对清单.md", "验证结果.json")]
    before = {str(path): digest(path) for path in protected}
    recorded = subject.read_json(HERE / "等价类计数.json")
    current = subject.calculate()
    changed = [{"path": old["path"], "recorded_sha256": old["sha256"], "current_sha256": new["sha256"]}
               for old, new in zip(recorded["sources"], current["sources"])
               if old != new]
    assert json.dumps(recorded["examples"], sort_keys=True) == json.dumps(current["examples"], sort_keys=True)
    pair_text = (HERE / "事件对清单.md").read_text()
    examples = []
    pair_total = 0
    for example in current["examples"]:
        name = example["name"]
        data = subject.read_json(ROOT / "数据/样例" / (name + ".json"))
        section = pair_text.split("## " + name + "\n", 1)[1].split("\n## ", 1)[0]
        listed_pairs = [line for line in section.splitlines()
                        if line.startswith("| ") and (" | 保留 |" in line or " | 可换 |" in line)]
        mode_rows = {}
        for mode, strict in (("semantic_sweep", False), ("operational_conservative", True)):
            actual = example["modes"][mode]
            expected_edges, barriers = pair_graph(data, strict)
            assert expected_edges == set(actual["edges"])
            n = actual["template_count"]
            assert len(actual["pairs"]) == n * (n - 1) // 2
            assert len(listed_pairs) == len(actual["pairs"])
            types = Counter()
            allowed = Counter()
            for pair in actual["pairs"]:
                i, j = pair["left"], pair["right"]
                left, right = actual["templates"][i], actual["templates"][j]
                lr, lw = set(left["reads"]), set(left["writes"])
                rr, rw = set(right["reads"]), set(right["writes"])
                forward = (lw & (rr | rw)) | (rw & (lr | lw))
                reverse = (rw & (lr | lw)) | (lw & (rr | rw))
                assert forward == reverse == set(pair["resources"])
                assert pair["conflict"] == bool(forward)
                key = "/".join(sorted((left["template"]["operation"], right["template"]["operation"])))
                types[key] += 1
                allowed[key] += not pair["conflict"]
            mode_rows[mode] = {"edge_count": len(expected_edges), "classes": actual["classes"],
                               "barrier_indices": barriers, "pairs_by_type": dict(types),
                               "allowed_by_type": dict(allowed), "independent_graph_matches": True,
                               "symmetry_and_resource_intersections": "passed"}
        for pair, op_pair in zip(example["modes"]["semantic_sweep"]["pairs"],
                                 example["modes"]["operational_conservative"]["pairs"]):
            row = (f"| {pair['left']} | {pair['right']} | "
                   f"{'保留' if pair['conflict'] else '可换'} | "
                   f"{'保留' if op_pair['conflict'] else '可换'} | "
                   f"{', '.join(pair['resources']) or '∅'} |")
            assert row in listed_pairs
        pair_total += len(example["modes"]["semantic_sweep"]["pairs"])
        examples.append({"name": name, "modes": mode_rows})
    after = {str(path): digest(path) for path in protected}
    assert before == after
    report = {"schema": "reduction-correctness-review-r1", "review_date": "2026-09-19",
              "protected_file_hashes": before, "protected_files_unchanged": True,
              "source_fingerprint_changes": changed,
              "current_recalculation_matches_recorded_examples": True,
              "current_sources": current["sources"], "examples": examples,
              "unique_pairs_checked": pair_total,
              "recorded_verifier_rerun": {"combinatorial": validation.brute_checks(),
                                         "recipes": validation.recipe_checks(),
                                         "runtime": validation.runtime_probes()},
              "scope": "独立逐类型冲突图对照、全对称性及清单核对；复跑原组合核验；未运行Rust异序差分",
              "status": "static_checks_passed_with_source_drift_and_runtime_limitations"}
    output = HERE / "复核-r1-正确性-核验.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "pairs": pair_total,
                      "source_changes": len(changed), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
