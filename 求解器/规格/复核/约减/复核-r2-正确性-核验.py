#!/usr/bin/env python3
"""第2轮正确性复核：只读被审产物，另存复核证据；不调用其写入入口。"""
import hashlib
import importlib.util
import itertools
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import count_classes as counted
import verify_reduction as verified

TARGETS = [ROOT / "规格/参数扫描约减.md"] + [HERE / name for name in (
    "count_classes.py", "verify_reduction.py", "verify_branch_projection.py",
    "等价类计数.json", "事件对清单.md", "验证结果.json", "分支表约减验证.json",
    "修订记录.md", "修订-r1-自查.log")]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def oracle_edges(data, strict):
    """从库存所属者和侧关系重建依赖，不使用被审的资源字符串或相交函数。"""
    kinds = {row["id"]: row["kind"] for row in data["layout"]["units"]}
    channels = {row["id"]: (row["source_port"].split(":")[0],
                              row["target_port"].split(":")[0])
                for row in data["layout"]["physical_channels"]}
    switches = {(row["unit"], row["function"]): row["enabled"]
                for row in data["settings"]["switches"]}

    def owner(uid):
        return "shared_warehouse" if kinds[uid] in ("仓库取货口", "协议核心") else uid

    gate_sources = {owner(source) for source, target in channels.values()
                    if kinds[target] == "物品准入口"}
    all_physical = {owner(uid) for ends in channels.values() for uid in ends}
    rows = []
    for template in counted.parameters(data)["judgment.order"]["template_order"]:
        operation, target = template["operation"], template["target"]
        reads, writes, sides = set(), set(), set()
        graph_change = False
        if operation == "move":
            source, dest = channels[target]
            peers = [ends for ends in channels.values() if ends[0] == source or ends[1] == dest]
            reads = {owner(uid) for ends in peers for uid in ends}
            if strict:
                reads |= all_physical
            writes = {owner(source), owner(dest)}
            sides = {(source, "output"), (dest, "input")}
            graph_change = kinds[dest] == "物品准入口"
        elif operation == "manufacture":
            reads = writes = {owner(target)}
        elif operation == "transfer" and switches[target, "transfer"]:
            reads = writes = {owner(target), "shared_warehouse"}
        rows.append((operation, reads, writes, sides,
                     graph_change or bool(writes & gate_sources)))
    edges = set()
    for i, j in itertools.combinations(range(len(rows)), 2):
        a, ar, aw, ac, ab = rows[i]
        b, br, bw, bc, bb = rows[j]
        if (ab or bb or aw & (br | bw) or bw & (ar | aw) or ac & bc
                or (strict and a == b and a in ("move", "manufacture"))):
            edges.add((i, j))
    return edges


def check_pairs(example, data):
    stats = {}
    for mode, strict in (("semantic_sweep", False), ("operational_conservative", True)):
        value = example["modes"][mode]
        expected = oracle_edges(data, strict)
        assert expected == set(map(tuple, value["edges"]))
        footprints = value["templates"]
        pair_types = Counter()
        allowed_types = Counter()
        for pair in value["pairs"]:
            i, j = pair["left"], pair["right"]
            left, right = footprints[i], footprints[j]
            lr, lw = set(left["reads"]), set(left["writes"])
            rr, rw = set(right["reads"]), set(right["writes"])
            forward = (lw & (rr | rw)) | (rw & (lr | lw))
            reverse = (rw & (lr | lw)) | (lw & (rr | rw))
            assert forward == reverse == set(pair["resources"])
            assert bool(forward) == pair["conflict"] == ((i, j) in expected)
            kind = "/".join(sorted((left["template"]["operation"], right["template"]["operation"])))
            pair_types[kind] += 1
            allowed_types[kind] += not pair["conflict"]
        assert len(value["pairs"]) == len(footprints) * (len(footprints) - 1) // 2
        stats[mode] = {"pairs": len(value["pairs"]), "edges": len(expected),
                       "allowed": len(value["pairs"]) - len(expected),
                       "classes": value["classes"], "pair_types": dict(pair_types),
                       "allowed_types": dict(allowed_types)}
    return stats


def check_markdown(results):
    sections = (HERE / "事件对清单.md").read_text().split("\n## ")[1:]
    total = 0
    for section, example in zip(sections, results["examples"], strict=True):
        assert section.splitlines()[0] == example["name"]
        rows = [line for line in section.splitlines() if line.startswith("| ")]
        actual = [line for line in rows if len(line.split("|")) == 7
                  and line.split("|")[1].strip().isdigit()]
        expected = []
        semantic = example["modes"]["semantic_sweep"]
        operational = example["modes"]["operational_conservative"]
        for i, footprint in enumerate(semantic["templates"]):
            template = footprint["template"]
            label = (template["operation"] + "(" + template["target"] + ")").replace("|", "\\|")
            assert f"| {i} | `{label}` |" in rows
        for left, right in zip(semantic["pairs"], operational["pairs"], strict=True):
            expected.append(f"| {left['left']} | {left['right']} | "
                            f"{'保留' if left['conflict'] else '可换'} | "
                            f"{'保留' if right['conflict'] else '可换'} | "
                            f"{', '.join(left['resources']) or '∅'} |")
        assert actual == expected
        total += len(actual)
    return total


def check_branch(results):
    path = HERE / "否证-r1-1-证据/check_branch_projection.py"
    spec = importlib.util.spec_from_file_location("branch_geometry_r2", path)
    independent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(independent)
    catalog = counted.read_json(ROOT / "数据/正式静态目录.json")
    kinds = {row["id"]: row for row in catalog["units"]}
    stored = counted.read_json(HERE / "分支表约减验证.json")
    summary = []
    for source, record in zip(results["examples"], stored["examples"], strict=True):
        data = counted.read_json(ROOT / "数据/样例" / (source["name"] + ".json"))
        own = independent.evaluate_example(data, kinds)
        assert encode(own) == encode(record["independent_geometry_and_subgraphs"])
        projection = counted.branch_projection(data, catalog)
        domains = counted.branch_domains(projection)
        assert record["row_order"] == [{"fork_unit": uid, "available_channels": list(domain)}
                                       for uid, domain, _ in domains]
        reps = list(counted.branch_representatives(projection))
        behavior = list(counted.branch_representatives(projection, "no_queries"))
        assert reps == record["projected_representatives"]
        assert behavior == record["behavior_representatives"]
        indexes = {encode(table): i for i, table in enumerate(reps)}
        mapping, queries = [], 0
        for values in itertools.product(*(domain for _, domain, _ in domains)):
            table = counted.branch_table(domains, values)
            normalized = counted.normalize_branch_table(table, projection)
            assert counted.normalize_branch_table(normalized, projection) == normalized
            assert counted.normalize_branch_table(table, projection, "no_queries") == behavior[0]
            normal = {(row["fork_unit"], tuple(row["available_channels"])): row["outgoing_channel"]
                      for row in normalized["choices"]}
            original = {(uid, domain): value for (uid, domain, _), value in zip(domains, values)}
            for graph in own["gate_subgraphs"]:
                for fork in own["forks"]:
                    available = tuple(cid for cid in fork["outgoing"] if cid not in graph["cut"])
                    if available:
                        assert original[fork["unit"], available] == normal[fork["unit"], available]
                        queries += 1
            mapping.append({"original_choices": list(values),
                            "projected_representative": indexes[encode(normalized)],
                            "behavior_representative": 0})
        assert mapping == record["original_to_representative"]
        assert queries == record["hypothetical_local_query_comparisons"]
        assert sorted(Counter(row["projected_representative"] for row in mapping).values()) == record["projection_class_sizes"]
        summary.append({"name": source["name"], "original_tables": len(mapping),
                        "projected_tables": len(reps), "behavior_tables": len(behavior),
                        "subgraphs": len(own["gate_subgraphs"]), "local_queries": queries,
                        "status": "passed"})
    return summary


def main():
    before = {str(path): digest(path) for path in TARGETS}
    existing = counted.read_json(HERE / "等价类计数.json")
    calculated = counted.calculate()
    assert encode({k: v for k, v in calculated.items() if k != "sources"}) == encode(
        {k: v for k, v in existing.items() if k != "sources"})
    changed = [{"path": row["path"], "stored": row["sha256"], "current": digest(Path(row["path"]))}
               for row in existing["sources"] if digest(Path(row["path"])) != row["sha256"]]
    examples = []
    for example in calculated["examples"]:
        data = counted.read_json(ROOT / "数据/样例" / (example["name"] + ".json"))
        examples.append({"name": example["name"], "modes": check_pairs(example, data)})
    command = [sys.executable, "-B", str(HERE / "count_classes.py"), "--check"]
    process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    (HERE / "复核-r2-正确性-check.log").write_text(
        "命令：" + " ".join(command) + "\n退出码：" + str(process.returncode) + "\n" + process.stdout + process.stderr)
    report = {"schema": "reduction-correctness-review-r2", "findings": [],
              "reviewed_files": before, "current_sources": calculated["sources"],
              "stored_source_changes": changed, "content_equal_excluding_sources": True,
              "check_command": {"argv": command, "exit_code": process.returncode},
              "examples": examples, "markdown_pairs": check_markdown(calculated),
              "branch": check_branch(calculated),
              "combination_checks": verified.brute_checks(), "recipe_checks": verified.recipe_checks(),
              "runtime_probes": verified.runtime_probes(),
              "scope": "图、字段及有限表核验；没有执行Rust异序差分或全称周期认证"}
    report["reviewed_files_unchanged"] = all(digest(Path(path)) == value for path, value in before.items())
    assert report["reviewed_files_unchanged"]
    report["source_changes_during_review"] = [row["path"] for row in calculated["sources"]
                                             if digest(Path(row["path"])) != row["sha256"]]
    report["status"] = "review_completed_with_declared_runtime_and_fingerprint_limits"
    (HERE / "复核-r2-正确性-核验.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in (
        "status", "stored_source_changes", "content_equal_excluding_sources", "markdown_pairs",
        "examples", "branch", "runtime_probes", "reviewed_files_unchanged", "source_changes_during_review")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
