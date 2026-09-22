#!/usr/bin/env python3
"""只读重验原函数；原检查产物的写入显式转到本席新文件。"""
import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

import count_classes as subject
import verify_reduction as verify
from review_r2_coverage import partition_count

HERE = Path(__file__).resolve().parent


def main():
    process = subprocess.run([sys.executable, "-B", str(HERE / "count_classes.py"), "--check"],
                             capture_output=True, text=True, check=False)
    (HERE / "复核-r2-覆盖-原脚本check.log").write_text(process.stdout + process.stderr + f"\n退出码：{process.returncode}\n")
    old = subject.read_json(HERE / "等价类计数.json")
    fresh = subject.calculate()
    # 当前计算结果与历史结果逐字段比；来源指纹独立列出，绝不覆盖原件。
    assert {k: v for k, v in old.items() if k != "sources"} == json.loads(json.dumps({
        k: v for k, v in fresh.items() if k != "sources"}))
    report = {"original_check_exit_code": process.returncode,
              "fresh_payload_equals_stored_except_sources": True,
              "current_calculation_sources": fresh["sources"]}
    original_write = Path.write_text
    destinations = {HERE / "分支表约减验证.json": HERE / "复核-r2-覆盖-原函数分支验证.json",
                    HERE / "事件对清单.md": HERE / "复核-r2-覆盖-原函数事件对.md"}

    def redirect_write(path, text, *args, **kwargs):
        if path not in destinations:
            raise AssertionError(f"拒绝原函数写入未授权路径：{path}")
        return original_write(destinations[path], text, *args, **kwargs)

    Path.write_text = redirect_write
    try:
        report["branch_function_recheck"] = verify.verify_branch_projection(fresh)
        subject.write_pairs(fresh)
    finally:
        Path.write_text = original_write
    report["branch_function_recheck"]["evidence"] = str(destinations[HERE / "分支表约减验证.json"])
    assert (HERE / "事件对清单.md").read_bytes() == destinations[HERE / "事件对清单.md"].read_bytes()
    old_branch = subject.read_json(HERE / "分支表约减验证.json")
    fresh_branch = subject.read_json(destinations[HERE / "分支表约减验证.json"])
    assert {k: v for k, v in old_branch.items() if k != "sources"} == {
        k: v for k, v in fresh_branch.items() if k != "sources"}
    report["branch_payload_equals_stored_except_sources"] = True
    report["all_event_pair_markdown_bytes_match"] = True
    report["original_combinatorial_checks"] = verify.brute_checks()
    report["original_recipe_checks"] = verify.recipe_checks()
    report["current_unmodified_runtime_probes"] = verify.runtime_probes()
    tested = 0
    for n in range(6):
        all_edges = list(itertools.combinations(range(n), 2))
        for mask in range(1 << len(all_edges)):
            edges = [edge for i, edge in enumerate(all_edges) if mask >> i & 1]
            signatures = set()
            for order in itertools.permutations(range(n)):
                positions = {v: i for i, v in enumerate(order)}
                signatures.add(tuple(positions[a] < positions[b] for a, b in edges))
            assert partition_count(n, edges)["classes"] == len(signatures)
            tested += 1
    report["independent_partition_algorithm_bruteforce_graphs"] = tested
    # 每种p/m组合直接生成完整函数，投影成保留行，验证边界及空积。
    projections = []
    for degree in range(4):
        domains = [d for size in range(1, degree + 1) for d in itertools.combinations(range(degree), size)]
        tables = list(itertools.product(*domains))
        for permanent_count in range(degree + 1):
            permanent = set(range(permanent_count))
            retained = [i for i, d in enumerate(domains) if permanent <= set(d)]
            signatures = {tuple(table[i] for i in retained) for table in tables}
            mutable_count = degree - permanent_count
            expected = math.prod((permanent_count + k) ** math.comb(mutable_count, k)
                                 for k in range(mutable_count + 1) if permanent_count + k)
            assert len(signatures) == expected
            projections.append({"degree": degree, "permanent": permanent_count,
                                "full_tables": len(tables), "projection": len(signatures)})
    report["branch_projection_formula_exhaustive"] = projections
    report["status"] = "current_mathematics_passed_original_snapshot_check_failed"
    (HERE / "复核-r2-覆盖-原函数重验.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "original_check_exit_code": process.returncode,
                      "independent_small_graphs": tested,
                      "runtime": report["current_unmodified_runtime_probes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
