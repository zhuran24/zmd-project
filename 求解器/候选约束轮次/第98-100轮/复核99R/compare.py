#!/usr/bin/env python3
"""逐项比较两份独立编码的结果，并留存输入与程序哈希。"""
from pathlib import Path
from hashlib import sha256
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    a = json.loads((HERE / "result_a.json").read_text())
    b = json.loads((HERE / "result_b.json").read_text())
    common = ("vertices", "edges", "unit_order_count", "unit_orders_with_ties",
              "batch_size_histogram", "order_refinement_pairs", "refinement_count",
              "missing_count", "refinements", "missing", "directed_channels")
    result = {"status": "PASS", "cases": {}}
    for name in a["cases"]:
        x, y = a["cases"][name], b["cases"][name]
        for key in common:
            assert x[key] == y[key], (name, key)
        for sx, sy in zip(x["schedules"], y["schedules"]):
            for key in ("unit_order", "times", "refinements"):
                assert sx[key] == sy[key], (name, key, sx["unit_order"])
        result["cases"][name] = {k: x[k] for k in common if k not in ("refinements",)}
    assert a["graph_family"] == b["graph_family"]
    assert a["graph_family_count"] == b["graph_family_count"]
    assert a["first_send"] == b["first_send"]
    assert a["first_send_histogram"] == b["first_send_histogram"]
    assert a["layers"]["ring_with_exits"]["arcs"] == b["layer_channels"]
    assert a["fed_star"]["directed_channels"] == b["fed_star_channels"]
    assert a["layers"]["ring_with_exits"]["vertices"] == b["layers"]["vertices"]
    assert a["layers"]["ring_with_exits"]["vectors"] == b["layers"]["vectors"]
    assert a["layers"]["ring_with_exits"]["acyclic_choice_count"] == b["layers"]["acyclic_choice_count"]
    assert not a["layers"]["ring_without_exit"]["vectors"]
    assert not b["layers"]["pure_ring_bounded_solutions"]
    result["graph_family_count"] = a["graph_family_count"]
    result["first_send_histogram"] = a["first_send_histogram"]
    result["fed_star_channels"] = a["fed_star"]["directed_channels"]
    result["layers"] = {k: a["layers"]["ring_with_exits"][k] for k in (
        "raw_choice_count", "acyclic_choice_count", "cyclic_choice_count", "vertices", "vectors")}
    result["pure_ring_sum_gap"] = b["layers"]["pure_ring_sum_gap"]
    star_last = next(s for s in a["cases"]["star"]["schedules"]
                     if s["unit_order"] == ["B", "C", "D", "A"])
    assert len(set(star_last["times"].values())) == 1
    result["star_same_actual_time"] = star_last
    result["scope"] = "接通时刻和并列顺序的有限复算；非全厂交付率、非完整状态图、非游戏实现证书。"
    inputs = [ROOT / "求解器/候选约束轮次/第98-100轮/前提快照" / n for n in (
        "《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt", "求解充分条件.txt", "不补的设定.txt")]
    inputs += [ROOT / "求解器/候选约束轮次/第98-100轮/临时规则.md",
               ROOT / "求解器/候选约束轮次/第95-97轮/推导95M.md",
               ROOT / "求解器/候选约束轮次/第95-97轮/复核97M.md"]
    manifest = []
    for p in inputs + [HERE / n for n in ("check_a.py", "check_b.py", "compare.py", "result_a.json", "result_b.json")]:
        raw = p.read_bytes()
        manifest.append({"path": str(p.relative_to(ROOT)), "bytes": len(raw),
                         "lines": len(raw.splitlines()), "sha256": sha256(raw).hexdigest()})
    result["manifest"] = manifest
    (HERE / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "cases": result["cases"],
                      "graph_family_count": result["graph_family_count"],
                      "layers": {k: result["layers"][k] for k in (
                          "raw_choice_count", "acyclic_choice_count", "cyclic_choice_count")},
                      "first_send_histogram": result["first_send_histogram"]},
                     ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
