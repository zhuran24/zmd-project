#!/usr/bin/env python3
"""否证席独立核验：重建几何，穷举门控子图和完整分支表。"""
import hashlib
import importlib.util
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3]
REPO = SOLVER.parent
REVIEW = HERE.parent
NAMES = ("混做粉碎机两下游", "分流器三路轮询")
TASKS = Path("/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def subsets(values, nonempty=False):
    return [tuple(row) for size in range(int(nonempty), len(values) + 1)
            for row in itertools.combinations(values, size)]


def rebuild_geometry(data, catalog):
    """直接由目录端口、逆时针旋转及共边相遇重建全部PC。"""
    ports = []
    occupied = set()
    for unit in data["layout"]["units"]:
        kind = catalog[unit["kind"]]
        width = int(kind["dimensions"]["width"]["value"])
        height = int(kind["dimensions"]["height"]["value"])
        origin_x, origin_y = [int(v["value"]) for v in unit["origin"]]
        turns = int(unit["rotation"][1:]) // 90
        assert unit["bridge_axes"] is None, "此独立几何核验只用于无桥两样例"

        def transform(x, y, normal_x=0, normal_y=0):
            w, h = width, height
            for _ in range(turns):
                x, y, w, h = h - 1 - y, x, h, w
                normal_x, normal_y = -normal_y, normal_x
            return x + origin_x, y + origin_y, normal_x, normal_y

        for x in range(width):
            for y in range(height):
                cell = transform(x, y)[:2]
                assert cell not in occupied and all(0 <= z < 70 for z in cell)
                occupied.add(cell)
        for side in kind["ports"]["layouts"][unit["port_layout"]]:
            for position in side["positions"]:
                offset = int(position["value"])
                local = {"south": (offset, 0, 0, -1),
                         "north": (offset, height - 1, 0, 1),
                         "west": (0, offset, -1, 0),
                         "east": (width - 1, offset, 1, 0)}[side["side"]]
                x, y, nx, ny = transform(*local)
                ports.append({"id": f"{unit['id']}:{side['side']}:{offset}",
                              "unit": unit["id"], "role": side["role"],
                              "transport": kind["family"] == "transport",
                              "cell": (x, y), "normal": (nx, ny)})
    channels = []
    for source in ports:
        if source["role"] != "output":
            continue
        for target in ports:
            if target["role"] != "input" or target["unit"] == source["unit"]:
                continue
            if not (source["transport"] or target["transport"]):
                continue
            x, y = source["cell"]
            nx, ny = source["normal"]
            if target["cell"] == (x + nx, y + ny) and target["normal"] == (-nx, -ny):
                channels.append((f"PC|{source['id']}|{target['id']}", source["unit"], target["unit"]))
    actual = {row[0] for row in channels}
    declared = {row["id"] for row in data["layout"]["physical_channels"]}
    assert actual == declared, (actual - declared, declared - actual)
    return sorted(channels)


def evaluate_example(data, catalog):
    kinds = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    channels = rebuild_geometry(data, catalog)
    gate_edges = [cid for cid, _, target in channels if kinds[target] == "物品准入口"]
    full_edges = {cid for cid, _, _ in channels}
    active_graphs = [full_edges - set(cut) for cut in subsets(gate_edges)]
    max_levels = {uid: 0 for uid, kind in kinds.items()
                  if catalog[kind]["family"] not in ("transport", "power")}
    graph_results = []
    for active in active_graphs:
        levels = {}
        for uid in max_levels:
            grouped = {cid if kinds[target] == "汇流器" else "other"
                       for cid, source, target in channels if source == uid and cid in active}
            levels[uid] = sorted(grouped)
            max_levels[uid] = max(max_levels[uid], len(grouped))
        graph_results.append({"cut": sorted(full_edges - active), "levels": levels})
    rows = []
    forks = []
    for uid in sorted(kinds):
        if kinds[uid] != "分流器":
            continue
        outgoing = sorted(cid for cid, source, _ in channels if source == uid)
        permanent = set(outgoing) - set(gate_edges)
        domains = subsets(outgoing, nonempty=True)
        kept = [domain for domain in domains if permanent <= set(domain)]
        actual_domains = {tuple(cid for cid in outgoing if cid in active) for active in active_graphs}
        assert actual_domains - {()} == set(kept)
        local_tables = list(itertools.product(*domains))
        local_signatures = {tuple(value for domain, value in zip(domains, table) if domain in kept)
                            for table in local_tables}
        for domain in domains:
            rows.append((uid, domain, domain in kept))
        forks.append({"unit": uid, "outgoing": outgoing, "permanent": sorted(permanent),
                      "full_tables": len(local_tables), "projected_tables": len(local_signatures),
                      "kept_rows": kept, "unread_rows": [d for d in domains if d not in kept]})
    signatures = {}
    representatives = {}
    normalized_tables = set()
    table_count = 0
    for table in itertools.product(*(domain for _, domain, _ in rows)):
        table_count += 1
        signature = tuple(value for value, (_, _, keep) in zip(table, rows) if keep)
        signatures[signature] = signatures.get(signature, 0) + 1
        normalized = tuple(value if keep else domain[0]
                           for value, (_, domain, keep) in zip(table, rows))
        normalized_tables.add(normalized)
        assert all(value in domain for value, (_, domain, _) in zip(normalized, rows))
        original_map = {(uid, domain): value for (uid, domain, _), value in zip(rows, table)}
        normalized_map = {(uid, domain): value for (uid, domain, _), value in zip(rows, normalized)}
        observed = []
        for active in active_graphs:
            for fork in forks:
                domain = tuple(cid for cid in fork["outgoing"] if cid in active)
                if domain:
                    key = (fork["unit"], domain)
                    assert original_map[key] == normalized_map[key]
                    observed.append(original_map[key])
        representatives.setdefault(signature, tuple(observed))
        assert representatives[signature] == tuple(observed)
    assert len(normalized_tables) == len(signatures)
    no_queries = all(count <= 1 for count in max_levels.values())
    assert no_queries
    return {"geometry_channels": channels, "geometry_matches_declared": True,
            "gate_subgraphs": graph_results, "max_output_levels": max_levels,
            "forks": forks, "full_tables": table_count, "projected_tables": len(signatures),
            "projection_class_sizes": sorted(signatures.values()),
            "full_table_graph_pairs": table_count * len(active_graphs),
            "no_damping_query_in_all_gate_subgraphs": no_queries,
            "behavior_representatives_under_spec_call_guard": 1}


def main():
    sources = [REPO / name for name in ("《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt")]
    sources += [TASKS / f"任务书{suffix}.md" for suffix in ("", "2", "3", "4", "5")]
    sources += [SOLVER / p for p in ("数据/正式静态目录.json", "规格/参数扫描约减.md",
                "规格/受限转移定义.md", "规格/内核输入.md", "规格/受限模型声明.md",
                "规格/内核配置-v1.json", "crates/kernel/src/polling.rs", "crates/kernel/src/input.rs")]
    sources += [SOLVER / "数据/样例" / f"{name}.json" for name in NAMES]
    sources += [REVIEW / name for name in ("review_r1_coverage.py", "复核-r1-覆盖.md", "复核-r1-覆盖-独立复算.json")]
    sources.append(Path(__file__).resolve())
    before = {str(p): digest(p) for p in sources}
    catalog = {u["id"]: u for u in read(SOLVER / "数据/正式静态目录.json")["units"]}
    result = {"time_utc": datetime.now(timezone.utc).isoformat(), "examples": {}}
    # 仅导入并执行发现脚本的纯函数；不调用会覆盖原证据的main。
    spec = importlib.util.spec_from_file_location("coverage_review", REVIEW / "review_r1_coverage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in NAMES:
        data = read(SOLVER / "数据/样例" / f"{name}.json")
        own = evaluate_example(data, catalog)
        prior = module.branch_projection(data)
        assert own["full_tables"] == prior["full_geometric_table_product"]
        assert own["projected_tables"] == math.prod(f["static_subset_projection_tables"] for f in prior["forks"])
        assert own["no_damping_query_in_all_gate_subgraphs"] == prior["no_damping_query_in_any_gate_subgraph"]
        own["review_function_rerun_agrees"] = True
        result["examples"][name] = own
    assert result["examples"][NAMES[1]]["full_tables"] == 96
    assert result["examples"][NAMES[1]]["projected_tables"] == 12
    assert sorted(result["examples"][NAMES[1]]["projection_class_sizes"]) == [8] * 12
    after = {str(p): digest(p) for p in sources}
    result.update({"sources_before": before, "sources_after": after, "sources_stable": before == after,
                   "status": "通过", "scope": "几何、表行投影和所有门控子图的级数；未执行内核轨迹，未证明初态可达"})
    assert before == after, "核验期间源文件改变，须重新核验"
    (HERE / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "sources_stable": result["sources_stable"],
                      "examples": {name: {key: row[key] for key in ("full_tables", "projected_tables",
                         "full_table_graph_pairs", "behavior_representatives_under_spec_call_guard")}
                         for name, row in result["examples"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
