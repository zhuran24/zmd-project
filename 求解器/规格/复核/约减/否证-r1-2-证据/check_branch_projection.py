#!/usr/bin/env python3
"""独立否证实验：永久出边投影、所有门控子图与完整表实跑。"""
import copy
import hashlib
import importlib.util
import itertools
import json
import math
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[3]
REPO = WORK.parent
SAMPLES = WORK / "数据/样例"
NAMES = ("混做粉碎机两下游", "分流器三路轮询")
TRANSPORT = {"传送带", "物品准入口", "桥接器", "分流器", "汇流器"}
CONFIG = WORK / "规格/内核配置-v1.json"
BINARY = WORK / "target/debug/kernel"
EXECUTABLE = None


def read(path):
    return json.loads(path.read_text())


def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def subsets(values):
    return [tuple(x) for n in range(len(values) + 1)
            for x in itertools.combinations(sorted(values), n)]


def inspect_structure(data):
    # 直接枚举所有准入口入边的开闭，不采用复核席的图或级数作为输入。
    kinds = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    edges = {c["id"]: (c["source_port"].split(":")[0],
                       c["target_port"].split(":")[0])
             for c in data["layout"]["physical_channels"]}
    mutable = sorted(c for c, (_, dst) in edges.items() if kinds[dst] == "物品准入口")
    permanent = set(edges) - set(mutable)
    graphs = [permanent | set(s) for s in subsets(mutable)]
    graph_results = []
    for active in graphs:
        levels = {u: set() for u in kinds if kinds[u] not in TRANSPORT}
        for c in active:
            src, dst = edges[c]
            if src in levels:
                levels[src].add(c if kinds[dst] == "汇流器" else "other")
        graph_results.append({"active_channels": sorted(active),
                              "nontransport_output_levels": {u: sorted(v) for u, v in levels.items()},
                              "damping_query_sides": [u for u, v in levels.items() if len(v) >= 2]})
    forks = []
    all_rows = []
    for unit in sorted(u for u in kinds if kinds[u] == "分流器"):
        outgoing = sorted(c for c, (src, _) in edges.items() if src == unit)
        rows = subsets(outgoing)[1:]
        keep = {tuple(c for c in outgoing if c in active) for active in graphs} - {()}
        permanent_outgoing = set(outgoing) & permanent
        assert all(permanent_outgoing <= set(s) for s in keep)
        expected_keep = {s for s in rows if permanent_outgoing <= set(s)}
        assert keep == expected_keep
        tables = list(itertools.product(*rows))
        signatures = {tuple((s, table[i]) for i, s in enumerate(rows) if s in keep)
                      for table in tables}
        checks = 0
        for table in tables:
            # 不可读行选择该行最小编码元素；原行与代表行都完整保留。
            representative = tuple(table[i] if s in keep else s[0] for i, s in enumerate(rows))
            assert all(representative[i] in s for i, s in enumerate(rows))
            for active in graphs:
                current = tuple(c for c in outgoing if c in active)
                if current:
                    index = rows.index(current)
                    assert table[index] == representative[index]
                    checks += 1
        full_formula = math.prod(k ** math.comb(len(outgoing), k)
                                 for k in range(1, len(outgoing) + 1))
        p, m = len(permanent_outgoing), len(outgoing) - len(permanent_outgoing)
        projected_formula = math.prod((p + k) ** math.comb(m, k)
                                      for k in range(m + 1) if p + k > 0)
        assert len(tables) == full_formula
        assert len(signatures) == projected_formula
        forks.append({"unit": unit, "outgoing": outgoing,
                      "targets": {c: {"unit": edges[c][1], "kind": kinds[edges[c][1]]} for c in outgoing},
                      "permanent_outgoing": sorted(permanent_outgoing),
                      "rows": rows, "kept_rows": sorted(keep),
                      "complete_tables": len(tables), "projected_tables": len(signatures),
                      "representative_queries_checked": checks})
        all_rows.extend((unit, s) for s in rows)
    no_queries = all(not g["damping_query_sides"] for g in graph_results)
    return {"gate_input_edges": mutable, "gate_subgraphs": graph_results,
            "forks": forks, "complete_table_product": math.prod(f["complete_tables"] for f in forks),
            "projected_table_product": math.prod(f["projected_tables"] for f in forks),
            "no_damping_queries_in_all_gate_subgraphs": no_queries,
            "behavior_representatives_under_kq04": 1 if no_queries else None}, all_rows


def normalize_trace(node):
    # 仅除去正在扫描的参数值；保留所有库存、指针、门、事件、台账与顺序。
    if isinstance(node, list):
        return [normalize_trace(x) for x in node]
    if isinstance(node, dict):
        out = {k: normalize_trace(v) for k, v in node.items()}
        if out.get("axis") == "damping.branch":
            out["value"] = "SCANNED_PARAMETER"
        if "damping.branch" in out:
            out["damping.branch"] = "SCANNED_PARAMETER"
        return out
    return node


def run_variants(name, source, all_rows):
    data = copy.deepcopy(source)
    # 移至证据目录的受控输入仅将两个外部引用改为绝对路径，哈希保持原值。
    for ref in (data["catalog"], data["parameters"]["axis_registry"]):
        ref["path"] = str((SAMPLES / ref["path"]).resolve())
    branch_decision = data["parameters"]["fixedness_unproven"]["damping.branch"]
    branch_parameter = next(x for x in data["initial_state"]["nonwarehouse"]["value"]
                            ["semantic_context"]["parameter_values"] if x["axis"] == "damping.branch")
    values = itertools.product(*(s for _, s in all_rows))
    ticks = 4 if name == NAMES[0] else 12
    runs = []
    for index, chosen in enumerate(values):
        branch_decision["value"]["choices"] = [
            {"fork_unit": unit, "available_channels": list(s), "outgoing_channel": choice}
            for (unit, s), choice in zip(all_rows, chosen)]
        branch_parameter["value"] = copy.deepcopy(branch_decision)
        path = HERE / "current-input.json"
        output = HERE / "current-record.json"
        save(path.name, data)
        command = [f"/proc/self/fd/{EXECUTABLE.fileno()}", "run", str(path), "--config", str(CONFIG),
                   "--ticks", str(ticks), "--out", str(output)]
        proc = subprocess.run(command, text=True, capture_output=True, timeout=60,
                              pass_fds=(EXECUTABLE.fileno(),))
        record = read(output) if output.exists() else {}
        row = {"index": index, "choices": list(chosen), "input_sha256": digest(path),
               "exit_code": proc.returncode, "status": record.get("status"),
               "stdout": proc.stdout, "stderr": proc.stderr}
        if record.get("status") == "completed":
            row["trace_sha256_except_scanned_parameter"] = value_digest(normalize_trace(record["trace"]))
            row["ticks_recorded"] = len(record["trace"]["ticks"])
        else:
            row["stop_record"] = record
        runs.append(row)
        if index == 0:
            save(name + "-representative-input.json", data)
            save(name + "-representative-record.json", record)
        if proc.returncode or record.get("status") != "completed":
            break
    signatures = {r.get("trace_sha256_except_scanned_parameter") for r in runs}
    return {"requested_ticks_each": ticks, "runs": runs,
            "variants_planned": math.prod(len(s) for _, s in all_rows),
            "variants_completed": sum(r["status"] == "completed" for r in runs),
            "trace_classes_except_scanned_parameter": len(signatures - {None}),
            "all_completed_and_equal": len(runs) == math.prod(len(s) for _, s in all_rows)
            and None not in signatures and len(signatures) == 1}


def main():
    global EXECUTABLE
    # 共享target可被并行cargo替换；持有原inode执行，绝不复制二进制。
    EXECUTABLE = BINARY.open("rb")
    binary_before = hashlib.sha256(os.pread(EXECUTABLE.fileno(), os.fstat(EXECUTABLE.fileno()).st_size, 0)).hexdigest()
    cited = HERE.parent / "review_r1_coverage.py"
    paths = [REPO / "《明日方舟：终末地》游戏规则.txt", REPO / "求解任务.txt", REPO / "求解约束.txt",
             WORK / "规格/参数扫描约减.md", WORK / "规格/受限转移定义.md", WORK / "规格/内核输入.md",
             WORK / "规格/选择点参数轴.md", WORK / "规格/受限模型声明.md", CONFIG,
             WORK / "数据/正式静态目录.json", cited, Path(__file__).resolve(), BINARY]
    paths += list((WORK / "crates/kernel/src").glob("*.rs"))
    paths += [SAMPLES / (n + ".json") for n in NAMES]
    before = {str(p): digest(p) for p in paths}
    result = {"scope": "固定布局及本版单级不请求阻尼；有限实跑不替代结构归纳", "sources_before": before,
              "normalization": "仅把trace内axis=damping.branch的value替换成同一外部参数标记",
              "examples": []}
    spec = importlib.util.spec_from_file_location("coverage_review", cited)
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    for name in NAMES:
        data = read(SAMPLES / (name + ".json"))
        independent, rows = inspect_structure(data)
        # 只调用被指脚本的纯函数，不运行会覆盖复核席文件的main。
        reproduced = review.branch_projection(data)
        assert independent["complete_table_product"] == reproduced["full_geometric_table_product"]
        assert independent["no_damping_queries_in_all_gate_subgraphs"] == reproduced["no_damping_query_in_any_gate_subgraph"]
        for fork in independent["forks"]:
            other = next(f for f in reproduced["forks"] if f["unit"] == fork["unit"])
            assert fork["projected_tables"] == other["static_subset_projection_tables"]
        runtime = run_variants(name, data, rows)
        result["examples"].append({"name": name, "independent": independent,
                                   "cited_function_reproduced": reproduced, "kernel": runtime})
        print(name, "完整/投影/行为代表", independent["complete_table_product"],
              independent["projected_table_product"], independent["behavior_representatives_under_kq04"],
              "实跑通过", runtime["variants_completed"], "/", runtime["variants_planned"], flush=True)
        save("results.json", result)
    after = {str(p): digest(p) for p in paths}
    result["sources_after"] = after
    result["sources_stable"] = all(v == after[k] for k, v in before.items() if k != str(BINARY))
    binary_after = hashlib.sha256(os.pread(EXECUTABLE.fileno(), os.fstat(EXECUTABLE.fileno()).st_size, 0)).hexdigest()
    result["executable"] = {"method": "持有共享target可执行文件inode，通过/proc/self/fd执行",
                            "sha256_before": binary_before, "sha256_after": binary_after,
                            "stable": binary_before == binary_after,
                            "shared_path_unchanged": before[str(BINARY)] == after[str(BINARY)]}
    result["all_runtime_checks_passed"] = all(x["kernel"]["all_completed_and_equal"] for x in result["examples"])
    save("results.json", result)
    print("文件稳定", result["sources_stable"], "实跑同轨迹", result["all_runtime_checks_passed"], flush=True)
    EXECUTABLE.close()


if __name__ == "__main__":
    main()
