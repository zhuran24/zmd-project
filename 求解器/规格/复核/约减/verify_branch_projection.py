#!/usr/bin/env python3
"""修订自查：独立重建几何、穷举表与门控子图，核代表生成及映射。"""
import copy
import importlib.util
import itertools
import json
from collections import Counter
from pathlib import Path

from count_classes import (HERE, NAMES, ROOT, branch_domains, branch_projection,
                           branch_representatives, branch_table, fingerprint,
                           normalize_branch_table, parameters, read_json)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def expect_rejection(action):
    try:
        action()
    except AssertionError:
        return
    raise AssertionError("应拒绝的缺行或不满足前件输入未被拒绝")


def verify_branch_projection(results):
    independent_path = HERE / "否证-r1-1-证据/check_branch_projection.py"
    sources = [Path(row["path"]) for row in results["sources"]]
    sources += [Path(__file__).resolve(), HERE / "verify_reduction.py", independent_path]
    before = [fingerprint(path) for path in sources]
    # 只复用已审脚本的纯函数，不调用其main，不覆盖否证历史证据。
    spec = importlib.util.spec_from_file_location("independent_branch_geometry", independent_path)
    independent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(independent)
    catalog = read_json(ROOT / "数据/正式静态目录.json")
    kinds = {u["id"]: u for u in catalog["units"]}
    examples = []
    for name in NAMES:
        data = read_json(ROOT / "数据/样例" / (name + ".json"))
        projection = branch_projection(data, catalog)
        stored = next(row["damping_branch"] for row in results["examples"] if row["name"] == name)
        assert all(stored[key] == value for key, value in projection.items())
        own = independent.evaluate_example(data, kinds)
        assert projection["full_tables"] == own["full_tables"]
        assert projection["projected_tables"] == own["projected_tables"]
        assert projection["output_level_upper_bounds"] == own["max_output_levels"]
        assert projection["no_damping_queries"] == own["no_damping_query_in_all_gate_subgraphs"]
        domains = branch_domains(projection)
        representatives = list(branch_representatives(projection))
        indexes = {encoded(table): i for i, table in enumerate(representatives)}
        assert len(indexes) == len(representatives) == projection["projected_tables"]
        behavior = list(branch_representatives(projection, "no_queries"))
        assert len(behavior) == 1
        assert stored["canonical_behavior_table"] == behavior[0]
        assert normalize_branch_table(parameters(data)["damping.branch"], projection, "no_queries") == behavior[0]
        mapping, query_checks = [], 0
        channels = set(c["id"] for c in data["layout"]["physical_channels"])
        for values in itertools.product(*(domain for _, domain, _ in domains)):
            table = branch_table(domains, values)
            normalized = normalize_branch_table(table, projection)
            assert normalize_branch_table(normalized, projection) == normalized
            assert normalize_branch_table(table, projection, "no_queries") == behavior[0]
            lookup = {(uid, domain): value for (uid, domain, _), value in zip(domains, values)}
            normalized_lookup = {(row["fork_unit"], tuple(row["available_channels"])): row["outgoing_channel"]
                                 for row in normalized["choices"]}
            for graph in own["gate_subgraphs"]:
                active = channels - set(graph["cut"])
                for fork in own["forks"]:
                    current = tuple(c for c in fork["outgoing"] if c in active)
                    if current:
                        key = fork["unit"], current
                        assert lookup[key] == normalized_lookup[key]
                        query_checks += 1
            mapping.append({"original_choices": list(values),
                            "projected_representative": indexes[encoded(normalized)],
                            "behavior_representative": 0})
        assert len(mapping) == projection["full_tables"]
        sizes = sorted(Counter(row["projected_representative"] for row in mapping).values())
        assert sizes == own["projection_class_sizes"]
        if domains:
            missing = copy.deepcopy(behavior[0])
            missing["choices"].pop()
            expect_rejection(lambda: normalize_branch_table(missing, projection))
        examples.append({"name": name, "independent_geometry_and_subgraphs": own,
                         "row_order": [{"fork_unit": uid, "available_channels": list(domain)}
                                       for uid, domain, _ in domains],
                         "projected_representatives": representatives,
                         "behavior_representatives": behavior, "original_to_representative": mapping,
                         "projection_class_sizes": sizes,
                         "hypothetical_local_query_comparisons": query_checks})

    # 仅为分级/投影算法的抽象端点夹具，不冒充合法几何或游戏运行样例。
    fixture = {"layout": {"units": [{"id": uid, "kind": kind} for uid, kind in
                                   (("source", "协议储存箱"), ("fork", "分流器"),
                                    ("merge_a", "汇流器"), ("merge_b", "汇流器"),
                                    ("gate_a", "物品准入口"), ("gate_b", "物品准入口"),
                                    ("gate_c", "物品准入口"))], "physical_channels": []}}
    edges = [("source", "merge_a"), ("source", "merge_b"),
             ("fork", "gate_a"), ("fork", "gate_b"), ("fork", "gate_c")]
    fixture["layout"]["physical_channels"] = [
        {"id": f"test_{i}", "source_port": f"{src}:out:{i}", "target_port": f"{dst}:in:0"}
        for i, (src, dst) in enumerate(edges)]
    guarded = branch_projection(fixture, catalog)
    assert guarded["output_level_upper_bounds"]["source"] == 2
    assert guarded["full_tables"] == guarded["projected_tables"] == 24
    assert guarded["no_query_behavior_representatives"] is None
    expect_rejection(lambda: list(branch_representatives(guarded, "no_queries")))
    expect_rejection(lambda: normalize_branch_table(next(branch_representatives(guarded)), guarded, "no_queries"))
    assert len(list(branch_representatives(guarded))) == 24
    assert before == [fingerprint(path) for path in sources], "核验期间源文件变化，须重跑"
    report = {"schema": "branch-projection-validation-v1", "status": "passed", "sources": before,
              "scope": "固定几何结构及有限表核验；未执行Rust，不由门控超图宣称种子可达",
              "examples": examples,
              "negative_checks": {"multi_level_no_query_rejected": True,
                                  "all_mutable_rows_retained": 24,
                                  "incomplete_table_rejected": True}}
    (HERE / "分支表约减验证.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return {"status": "passed", "evidence": str(HERE / "分支表约减验证.json"),
            "examples": [{"name": row["name"], "full_tables": len(row["original_to_representative"]),
                          "projected_tables": len(row["projected_representatives"]),
                          "behavior_representatives": len(row["behavior_representatives"]),
                          "gate_subgraphs": len(row["independent_geometry_and_subgraphs"]["gate_subgraphs"]),
                          "hypothetical_local_query_comparisons": row["hypothetical_local_query_comparisons"]}
                         for row in examples], "negative_checks": report["negative_checks"]}


if __name__ == "__main__":
    print(json.dumps(verify_branch_projection(read_json(HERE / "等价类计数.json")), ensure_ascii=False))
