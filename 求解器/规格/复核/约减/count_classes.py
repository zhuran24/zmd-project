#!/usr/bin/env python3
"""按参数扫描约减正文的保守资源集计数；不执行游戏，不把计数当认证。"""
import argparse
import hashlib
import itertools
import json
import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
NAMES = ("混做粉碎机两下游", "分流器三路轮询")
AXES = (
    "judgment.order", "damping.branch", "connection.build_order",
    "connection.order", "connection.tie", "connection.belt_shape",
    "transfer.phase", "manufacturing.recipe_selection",
    "manufacturing.input_slot_selection", "initialization.warehouse_anchor",
    "initialization.other_inventory", "initialization.switches",
    "initialization.build_timing", "initialization.debug_end",
    "warehouse.external_supply",
)


def read_json(path):
    return json.loads(path.read_text())


def fingerprint(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def parameters(data):
    return {axis: row["value"] for group in
            ("fixed", "offline_mutable", "fixedness_unproven")
            for axis, row in data["parameters"][group].items()}


def unit_of(port):
    return port.split(":", 1)[0]


def make_footprints(data, catalog, strict=False):
    """按整单位库存粗分块；门维护影响者与所有模板冲突。"""
    units = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    kinds = {u["id"]: u for u in catalog["units"]}
    channels = {c["id"]: c for c in data["layout"]["physical_channels"]}
    templates = parameters(data)["judgment.order"]["template_order"]
    switches = {(s["unit"], s["function"]): s["enabled"]
                for s in data["settings"]["switches"]}

    def inv(uid):
        return "warehouse" if units[uid] in ("协议核心", "仓库取货口") else "inventory:" + uid

    def physical_reads(channel):
        source, target = unit_of(channel["source_port"]), unit_of(channel["target_port"])
        result = {inv(source), inv(target), "graph", "constants",
                  "usage:" + channel["source_port"], "usage:" + channel["target_port"]}
        for uid in (source, target):
            if units[uid] == "物品准入口":
                result.add("gate:" + uid)
        if units[target] == "协议核心":
            result.add("empty_order")
        return result

    maintenance_reads = {"graph"}
    has_gates = any(kind == "物品准入口" for kind in units.values())
    for channel in channels.values():
        if units[unit_of(channel["target_port"])] == "物品准入口":
            maintenance_reads |= {inv(unit_of(channel["source_port"])),
                                  "gate:" + unit_of(channel["target_port"])}
    all_physical_reads = set().union(*(physical_reads(c) for c in channels.values()))
    result = []
    for template in templates:
        operation, target = template["operation"], template["target"]
        reads, writes = {"constants", "maintenance_barrier"}, set()
        if operation == "move":
            channel = channels[target]
            source, dest = unit_of(channel["source_port"]), unit_of(channel["target_port"])
            sides = {"poll:" + source + ":output", "poll:" + dest + ":input"}
            reads |= sides | physical_reads(channel)
            for other in channels.values():
                if (unit_of(other["source_port"]) == source or
                        unit_of(other["target_port"]) == dest):
                    reads |= physical_reads(other)
            writes |= sides | {inv(source), inv(dest), "usage:" + channel["source_port"],
                               "usage:" + channel["target_port"]}
            if units[dest] == "物品准入口":
                writes |= {"gate:" + dest, "graph", "pending:" + dest}
            if units[dest] == "协议核心":
                reads |= {"warehouse", "empty_order", "ledger"}
                writes |= {"warehouse", "empty_order", "ledger"}
            if strict:
                # 原实现访问PC时全局刷新current_level；不对其做隐式投影。
                reads |= all_physical_reads | {"derived_levels"}
                writes |= {"derived_levels"}
        elif operation == "manufacture":
            reads |= {inv(target), "progress:" + target, "pending:" + target}
            writes |= {inv(target), "progress:" + target, "pending:" + target}
            if strict:
                # 序列化pending保留插入顺序，本模式不把数组改为集合。
                reads.add("pending_array")
                writes.add("pending_array")
        elif operation == "transfer":
            if switches[(target, "transfer")]:
                reads |= {inv(target), "progress:" + target, "warehouse", "empty_order", "ledger"}
                writes |= {inv(target), "progress:" + target, "warehouse", "empty_order", "ledger"}
        else:
            raise ValueError("未知模板：" + operation)
        # 共享维护只在固定点上消去；可能破坏固定点的动作保守视作全局屏障。
        if has_gates and writes & maintenance_reads:
            writes.add("maintenance_barrier")
        result.append({"template": template, "reads": sorted(reads), "writes": sorted(writes)})
    expected = ({("move", c) for c in channels} |
                {("manufacture", u) for u, k in units.items() if kinds[k]["family"] == "manufacturing"} |
                {("transfer", u) for u, k in units.items() if k == "协议储存箱"})
    actual = {(t["operation"], t["target"]) for t in templates}
    assert actual == expected and len(actual) == len(templates)
    return result


def conflict_graph(footprints):
    edges, pairs = [], []
    for i, left in enumerate(footprints):
        lr, lw = set(left["reads"]), set(left["writes"])
        for j in range(i + 1, len(footprints)):
            right = footprints[j]
            rr, rw = set(right["reads"]), set(right["writes"])
            overlap = (lw & (rr | rw)) | (rw & (lr | lw))
            if overlap:
                edges.append((i, j))
            pairs.append({"left": i, "right": j, "conflict": bool(overlap),
                          "resources": sorted(overlap)})
    return tuple(edges), pairs


@lru_cache(None)
def chromatic_at(n, edges, q):
    """删边缩边求色多项式在整数q处的值，含连通分解与单纯顶点消去。"""
    if n == 0:
        return 1
    adjacency = [set() for _ in range(n)]
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    components, unseen = [], set(range(n))
    while unseen:
        stack, comp = [min(unseen)], set()
        while stack:
            v = stack.pop()
            if v not in unseen:
                continue
            unseen.remove(v)
            comp.add(v)
            stack.extend(adjacency[v] & unseen)
        components.append(sorted(comp))
    if len(components) > 1:
        product = 1
        for comp in components:
            labels = {v: i for i, v in enumerate(comp)}
            subedges = tuple(sorted((labels[a], labels[b]) for a, b in edges if a in labels and b in labels))
            product *= chromatic_at(len(comp), subedges, q)
        return product
    for v in range(n):
        neighbors = adjacency[v]
        if all(b in adjacency[a] for a, b in itertools.combinations(neighbors, 2)):
            rest = [x for x in range(n) if x != v]
            labels = {x: i for i, x in enumerate(rest)}
            subedges = tuple(sorted((labels[a], labels[b]) for a, b in edges if v not in (a, b)))
            return (q - len(neighbors)) * chromatic_at(n - 1, subedges, q)
    edge = max(edges, key=lambda e: len(adjacency[e[0]] & adjacency[e[1]]))
    a, b = edge
    deleted = tuple(e for e in edges if e != edge)
    labels = {v: i for i, v in enumerate(x for x in range(n) if x != b)}
    labels[b] = labels[a]
    contracted = tuple(sorted({tuple(sorted((labels[x], labels[y])))
                               for x, y in deleted if labels[x] != labels[y]}))
    return chromatic_at(n, deleted, q) - chromatic_at(n - 1, contracted, q)


def orientation_count(n, edges):
    return (-1) ** n * chromatic_at(n, tuple(sorted(edges)), -1)


def count_by_sources(n, edges):
    """独立校验：对非空独立源点集容斥，不使用色多项式。"""
    adjacency = [0] * n
    for a, b in edges:
        adjacency[a] |= 1 << b
        adjacency[b] |= 1 << a

    @lru_cache(None)
    def independent_subsets(mask):
        if not mask:
            return (0,)
        bit = mask & -mask
        v = bit.bit_length() - 1
        rest = mask ^ bit
        return independent_subsets(rest) + tuple(x | bit for x in independent_subsets(rest & ~adjacency[v]))

    @lru_cache(None)
    def count(mask):
        if not mask:
            return 1
        return sum((1 if subset.bit_count() % 2 else -1) * count(mask ^ subset)
                   for subset in independent_subsets(mask) if subset)
    return count((1 << n) - 1)


def tie_graph(data):
    channels = data["layout"]["physical_channels"]
    from fractions import Fraction
    event_times = {e["id"]: Fraction(e["time"]["value"]["value"])
                   for e in data["timeline"]["events"] if e["time"] is not None}
    built = {row["unit"]: event_times[row["event"]] for row in data["construction"]["moments"]}
    times = [max(built[unit_of(c["source_port"])], built[unit_of(c["target_port"])]) for c in channels]
    edges = tuple((i, j) for i in range(len(channels)) for j in range(i + 1, len(channels))
                  if times[i] == times[j] and
                  (unit_of(channels[i]["source_port"]) == unit_of(channels[j]["source_port"]) or
                   unit_of(channels[i]["target_port"]) == unit_of(channels[j]["target_port"])))
    return {"channel_order": [c["id"] for c in channels], "edges": edges,
            "raw_orders": math.factorial(len(channels)),
            "classes": orientation_count(len(channels), edges)}


def branch_projection(data, catalog):
    """正文§2.1：永久出边投影；全几何级数是所有门控子图的上界。"""
    units = {u["id"]: u["kind"] for u in data["layout"]["units"]}
    families = {u["id"]: u["family"] for u in catalog["units"]}
    channels = data["layout"]["physical_channels"]
    mutable = {c["id"] for c in channels
               if units[unit_of(c["target_port"])] == "物品准入口"}
    groups = {}
    for uid, kind in sorted(units.items()):
        if families[kind] in ("transport", "power"):
            continue
        groups[uid] = sorted({"direct:" + c["id"]
                              if units[unit_of(c["target_port"])] == "汇流器" else "other"
                              for c in channels if unit_of(c["source_port"]) == uid})
    forks = []
    for uid, kind in sorted(units.items()):
        if kind != "分流器":
            continue
        outgoing = sorted(c["id"] for c in channels if unit_of(c["source_port"]) == uid)
        permanent = set(outgoing) - mutable
        rows = [{"available_channels": list(domain), "retained": permanent <= set(domain)}
                for size in range(1, len(outgoing) + 1)
                for domain in itertools.combinations(outgoing, size)]
        p, m = len(permanent), len(outgoing) - len(permanent)
        full = math.prod(k ** math.comb(p + m, k) for k in range(1, p + m + 1))
        projected = math.prod((p + k) ** math.comb(m, k)
                              for k in range(m + 1) if p + k)
        assert full == math.prod(len(row["available_channels"]) for row in rows)
        assert projected == math.prod(len(row["available_channels"]) for row in rows if row["retained"])
        forks.append({"fork_unit": uid, "outgoing_channels": outgoing,
                      "permanent_channels": sorted(permanent),
                      "mutable_channels": sorted(set(outgoing) & mutable), "rows": rows,
                      "full_tables": full, "projected_tables": projected})
    no_queries = all(len(value) <= 1 for value in groups.values())
    return {"scope": "固定合法几何、方向与相遇读法，无结构变化/离线；转移§3.1单级不请求阻尼",
            "forks": forks, "gate_input_channels": sorted(mutable),
            "full_geometry_output_groups": groups,
            "output_level_upper_bounds": {uid: len(value) for uid, value in groups.items()},
            "no_damping_queries": no_queries,
            "full_tables": math.prod(f["full_tables"] for f in forks),
            "projected_tables": math.prod(f["projected_tables"] for f in forks),
            "no_query_behavior_representatives": 1 if no_queries else None}


def branch_domains(projection):
    return [(fork["fork_unit"], tuple(row["available_channels"]), row["retained"])
            for fork in projection["forks"] for row in fork["rows"]]


def branch_table(domains, values):
    """保留完整v2接口，不可读行也必须填入该行合法出支。"""
    assert len(domains) == len(values)
    assert all(value in domain for (_, domain, _), value in zip(domains, values))
    return {"schema": "damping-branch-v2", "fixedness": "by_available_set",
            "choices": [{"fork_unit": uid, "available_channels": list(domain),
                         "outgoing_channel": value}
                        for (uid, domain, _), value in zip(domains, values)],
            "evaluations": [], "on_missing": "unresolved"}


def branch_representatives(projection, mode="permanent_edges"):
    """逐个生成完整表；no_queries模式须先通过全几何级数充分条件。"""
    assert mode in ("permanent_edges", "no_queries")
    if mode == "no_queries":
        assert projection["no_damping_queries"], "不满足单级前件，不能合为一个行为代表"
    domains = branch_domains(projection)
    choices = [domain if keep and mode == "permanent_edges" else (domain[0],)
               for _, domain, keep in domains]
    for values in itertools.product(*choices):
        yield branch_table(domains, values)


def normalize_branch_table(table, projection, mode="permanent_edges"):
    """仅接受完整合法表；返回可审计的规范代表，不能借补齐掩盖缺行。"""
    assert mode in ("permanent_edges", "no_queries")
    assert set(table) == {"schema", "fixedness", "choices", "evaluations", "on_missing"}
    assert table["schema"] == "damping-branch-v2" and table["fixedness"] == "by_available_set"
    assert table["evaluations"] == [] and table["on_missing"] == "unresolved"
    assert all(set(row) == {"fork_unit", "available_channels", "outgoing_channel"}
               for row in table["choices"])
    domains = branch_domains(projection)
    selected = {(row["fork_unit"], tuple(row["available_channels"])): row["outgoing_channel"]
                for row in table["choices"]}
    assert len(selected) == len(table["choices"])
    assert set(selected) == {(uid, domain) for uid, domain, _ in domains}
    assert all(selected[uid, domain] in domain for uid, domain, _ in domains)
    if mode == "no_queries":
        assert projection["no_damping_queries"], "不满足单级前件，不能合为一个行为代表"
    values = [selected[uid, domain] if keep and mode == "permanent_edges" else domain[0]
              for uid, domain, keep in domains]
    return branch_table(domains, values)


def calculate():
    sources = [ROOT / p for p in (
        "规格/受限转移定义.md", "规格/受限模型声明.md", "规格/内核配置-v1.json",
        "规格/内核输入.md", "规格/运行语义.md", "规格/选择点参数轴.md",
        "数据/正式静态目录.json", "crates/kernel/src/transition.rs", "crates/kernel/src/polling.rs",
        "crates/kernel/src/input.rs", "规格/参数扫描约减.md")]
    sources += [ROOT.parent / p for p in ("求解任务.txt", "求解约束.txt", "《明日方舟：终末地》游戏规则.txt")]
    sources += [ROOT / ("数据/样例/" + name + ".json") for name in NAMES]
    sources += [Path(__file__).resolve()]
    before = [fingerprint(p) for p in sources]
    catalog = read_json(ROOT / "数据/正式静态目录.json")
    config = read_json(ROOT / "规格/内核配置-v1.json")
    actual_axes = sorted(a for a, row in config["axes"].items() if row["disposition"] == "由输入全称量化")
    assert actual_axes == sorted(AXES), "15轴处置发生变化，须人工迁移论证和脚本，不能静默继续"
    result = {"schema": "reduction-count-v2", "axes": list(AXES),
              "scope": "固定布局、其它参数、完整种子及支持域；计数是保守冲突商，不是全部物理行为的最小商",
              "sources": before, "examples": []}
    for name in NAMES:
        data = read_json(ROOT / ("数据/样例/" + name + ".json"))
        projection = branch_projection(data, catalog)
        row = {"name": name, "modes": {}, "connection_tie": tie_graph(data),
               "damping_branch": projection}
        if projection["no_damping_queries"]:
            projection["canonical_behavior_table"] = next(branch_representatives(projection, "no_queries"))
        for mode, strict in (("semantic_sweep", False), ("operational_conservative", True)):
            footprints = make_footprints(data, catalog, strict)
            edges, pairs = conflict_graph(footprints)
            n = len(footprints)
            counted = orientation_count(n, edges)
            independent = count_by_sources(n, edges)
            assert counted == independent
            row["modes"][mode] = {"templates": footprints, "template_count": n,
                                  "edge_count": len(edges), "edges": edges, "pairs": pairs,
                                  "raw_orders": math.factorial(n), "classes": counted,
                                  "independent_source_count": independent}
        result["examples"].append(row)
    assert before == [fingerprint(p) for p in sources], "计算期间源文件变化；未写结果，须重跑"
    return result


def write_pairs(result):
    lines = ["# 逐对冲突与未采用交换清单", "", "日期：2026-09-19。状态：由 count_classes.py 生成；语义和保守操作两种口径分列。",
             "", "依据：[参数扫描约减](../../参数扫描约减.md)§3–6。编号只标识输入模板；`保留`表示读写相交、本稿没有证明该对可交换，不表示已证明不交换。`可换`只适用该文限定的状态口径，两列都不承诺原始审计日志相同。", ""]
    for example in result["examples"]:
        lines += ["## " + example["name"], "", "| 编号 | 模板 |", "|---|---|"]
        semantic = example["modes"]["semantic_sweep"]
        for i, row in enumerate(semantic["templates"]):
            name = row["template"]["operation"] + "(" + row["template"]["target"] + ")"
            escaped = name.replace("|", "\\|")
            lines.append(f"| {i} | `{escaped}` |")
        lines += ["", "| 左 | 右 | 语义整轮口径 | 保守操作口径 | 语义冲突资源 |", "|---|---|---|---|---|"]
        operational = example["modes"]["operational_conservative"]
        for left, right in zip(semantic["pairs"], operational["pairs"]):
            lines.append(f"| {left['left']} | {left['right']} | {'保留' if left['conflict'] else '可换'} | {'保留' if right['conflict'] else '可换'} | {', '.join(left['resources']) or '∅'} |")
        lines.append("")
    (HERE / "事件对清单.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = calculate()
    output = HERE / "等价类计数.json"
    if args.check:
        # 图边在内存中是元组，JSON读回是数组；按同一规范JSON比较全部内容。
        assert json.dumps(result, ensure_ascii=False, sort_keys=True) == json.dumps(
            read_json(output), ensure_ascii=False, sort_keys=True), "结果或输入指纹已变化"
    else:
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        write_pairs(result)
    for row in result["examples"]:
        print(json.dumps({"name": row["name"], "counts": {m: v["classes"] for m, v in row["modes"].items()},
                          "tie_classes": row["connection_tie"]["classes"],
                          "branch_counts": {key: row["damping_branch"][key] for key in
                                            ("full_tables", "projected_tables", "no_query_behavior_representatives")}},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
