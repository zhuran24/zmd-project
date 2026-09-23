#!/usr/bin/env python3
"""合成内核输入的静态检查；不执行游戏运行或证明起动可达。"""

import argparse
import copy
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
CATEGORIES = {"条文直引", "算术推论", "候选", "启发式", "实测"}
ROTATIONS = {"r0": 0, "r90": 1, "r180": 2, "r270": 3}
DIRECTIONS = {"south": (0, -1), "north": (0, 1), "west": (-1, 0), "east": (1, 0)}
INITIAL_ITEMS = {"源矿", "蓝铁矿", "荞花", "砂叶", "荞花种子", "砂叶种子"}
AXIS_PATH = ROOT / "求解器/规格/选择点参数轴.md"
KNOWN_VALUES = {'polling.direct_peer': 'physical_peer', 'connection.port_meeting': 'shared_edge_opposite', 'initialization.rotation_stage': 'build_and_debug', 'gate.window_recovery': 'on_expiry_if_other_guards', 'transfer.judgment': 'unit', 'manufacturing.port_slot_relation': 'distributed', 'manufacturing.output_blocked': 'retain_whole_batch', 'gate.limit_requires_identity': True, 'warehouse.capacity': {'value': '80000', 'category': '条文直引'}, 'warehouse.delivery_count': 'actual_inbound', 'bridge.inventory_scope': 'two_independent_axis_slots', 'bridge.scheduling_scope': 'unit', 'judgment.order_scope': 'fixed_run_order', 'polling.both_failure': 'advance_authorized', 'transfer.cooldown_scope': 'box', 'transfer.failure_cooldown': 'every_attempt', 'transfer.partial_acceptance': 'max_receivable', 'gate.identity_recovery': 'current_conditions', 'gate.total_recovery': 'current_conditions', 'gate.window_clock': 'wall_clock', 'warehouse.acceptance': 'receivable_products', 'warehouse.acceptance_quantifier': 'all_candidate_and_actual_checks'}


def axis_registry():
    """轴表是字段真源；只读取第二节，拒绝不认识的已定值。"""
    text = AXIS_PATH.read_text().split("## 2.", 1)[1].split("## 3.", 1)[0]
    rows = {}
    for line in text.splitlines():
        if not line.startswith("| `"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        name, point, lifetime, description = parts
        name = name.strip("`")
        if lifetime == "F" or lifetime.startswith("F（"):
            group = "fixed"
        elif lifetime == "O":
            group = "offline_mutable"
        else:
            group = "fixedness_unproven"
        state = description.split("：", 1)[0]
        rows[name] = {"group": group, "state": state, "point": point, "lifetime": lifetime, "description": description}
    require(rows and {name for name, row in rows.items() if row["state"] == "known"} == set(KNOWN_VALUES), "轴表已定值集合变化，须更新编码后再检查")
    return rows


NAMES = ["桥接器双通路.json", "分流器三路轮询.json", "混做粉碎机两下游.json"]
SOURCE_HASHES = {
    "《明日方舟：终末地》游戏规则.txt": "52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3",
    "求解任务.txt": "1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac",
    "求解约束.txt": "0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f"
}


class CheckError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CheckError(message)


def fields(value, expected, where):
    require(isinstance(value, dict) and set(value) == set(expected.split()), f"{where}: 字段缺失或未知")


def validate_slot_identity(warehouse, inventory_ids=()):
    """仓库自由标签不能占用单位槽位语法，也不能与当前普通格重名。"""
    fields(warehouse, 'slots unlisted', 'warehouse')
    require(isinstance(warehouse['slots'], list), '仓库格表须为数组')
    seen = set()
    for row in warehouse['slots']:
        fields(row, 'slot item quantity empty_identity', 'warehouse_slot')
        sid = row['slot']
        require(isinstance(sid, str) and sid and sid not in seen, '仓库格 id 重复或非法')
        require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*:[a-z_]+:[0-9]+', sid) is None
                and sid not in inventory_ids, '仓库格占用单位槽位命名域: '+sid)
        seen.add(sid)


def quantity(value, integer=True):
    fields(value, "value category", "Quantity")
    require(value["category"] in CATEGORIES, "数字类别非法")
    raw = value["value"]
    require(isinstance(raw, str) and re.fullmatch(r"-?\d+(?:/[1-9]\d*)?", raw), "数值必须为整数/正分母有理数字符串")
    number = Fraction(raw)
    require(not integer or number.denominator == 1, "应为整数")
    return int(number) if integer else number


def decision(value, allowed=None, nullable=False):
    fields(value, "status value basis", "Decision")
    require(value["status"] in {"unresolved", "specified", "derived", "not_applicable"}, "Decision 状态非法")
    require(isinstance(value["basis"], list) and value["basis"] and all(isinstance(x, str) and x for x in value["basis"]), "Decision 缺依据")
    if value["status"] in {"unresolved", "not_applicable"}:
        require(value["value"] is None, "未解/不适用不能偷填值")
    else:
        require(nullable or value["value"] is not None, "已填/派生必须有值")
    if allowed:
        require(value["status"] in allowed, "unsupported: 此检查子集不解释该 Decision 状态")


def load_json(path):
    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, f"JSON 重复键: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def rotate_cell(x, y, width, height, turns):
    for _ in range(turns):
        x, y, width, height = height - 1 - y, x, height, width
    return x, y


def geometry(data, catalog, complete=True):
    """由共享目录推占格和端口；输入不能覆盖单位属性。"""
    # 本函数仅实现显式共边读法；其它谓词未审且未实现，不能默取几何默认。
    meeting = data.get("parameters", {}).get("fixed", {}).get("connection.port_meeting")
    require(meeting is not None, "unsupported: connection.port_meeting 须显式选择本版读法")
    decision(meeting)
    require(meeting["status"] == "specified" and meeting["value"] == "shared_edge_opposite",
            "unsupported: connection.port_meeting 未解或未实现；角点相遇仍待审")
    kinds = {row["id"]: row for row in catalog["units"]}
    units, ports, occupied = {}, {}, {}
    layout = data["layout"]
    fields(layout, "base id anchor units physical_channels buffer_channels snapshots post_debug", "layout")
    fields(layout["base"], "width height", "base")
    require(quantity(layout["base"]["width"]) == 70 and quantity(layout["base"]["height"]) == 70, "基地须为规则的70×70")
    for unit in layout["units"]:
        fields(unit, "id kind origin rotation port_layout bridge_axes occupied_cells", "unit")
        uid = unit["id"]
        require(isinstance(uid, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", uid), "实例 id 编码非法")
        require(uid not in units, "实例 id 重复")
        require(unit["kind"] in kinds, "未知目录单位 id")
        kind = kinds[unit["kind"]]
        require(unit["rotation"] in ROTATIONS, "旋转码非法")
        turns = ROTATIONS[unit["rotation"]]
        width, height = (quantity(kind["dimensions"][x]) for x in ("width", "height"))
        require(isinstance(unit["origin"], list) and len(unit["origin"]) == 2, "origin 必须为二维坐标")
        ox, oy = map(quantity, unit["origin"])
        cells = set()
        for x in range(width):
            for y in range(height):
                rx, ry = rotate_cell(x, y, width, height, turns)
                cell = ox + rx, oy + ry
                require(all(0 <= n < 70 for n in cell), f"越界: {uid}")
                require(cell not in occupied, f"占格重叠: {uid} 与 {occupied.get(cell)}")
                cells.add(cell)
                occupied[cell] = uid
        if unit["occupied_cells"] is not None:
            declared = [tuple(map(quantity, cell)) for cell in unit["occupied_cells"]]
            require(len(declared) == len(cells) and set(declared) == cells, "占格声明与类型朝向不符")
        index = unit["port_layout"]
        if unit["kind"] == "桥接器":
            require(index is None, "桥接器不能任选双轴端口型索引")
            fields(unit["bridge_axes"], "vertical horizontal", "bridge_axes")
            bridge_roles = {}
            for axis, sides in (("vertical", ("south", "north")), ("horizontal", ("west", "east"))):
                state = unit["bridge_axes"][axis]
                fields(state, "status input_side basis", "bridge_axis")
                require(state["status"] in {"pending", "resolved", "unresolved"} and state["basis"], "桥轴状态非法")
                if state["status"] == "resolved":
                    require(state["input_side"] in sides, "桥轴输入边非法")
                    bridge_roles.update({side: "input" if side == state["input_side"] else "output" for side in sides})
                else:
                    require(state["input_side"] is None, "待定桥轴不能偷填方向")
                    bridge_roles.update({side: None for side in sides})
            # 取全部型的位置并集，不借目录首型定向。
            edges = {edge["side"]: edge for variant in kind["ports"]["layouts"] for edge in variant}
            edges = [dict(edge, role=bridge_roles[side]) for side, edge in edges.items()]
        else:
            require(unit["bridge_axes"] is None, "非桥接器不应有桥轴状态")
            require(type(index) is int and 0 <= index < len(kind["ports"]["layouts"]), "端口型索引非法")
            edges = kind["ports"]["layouts"][index]
        if unit["kind"] == "仓库取货口":
            require((turns == 0 and oy == 0) or (turns == 3 and ox == 0), "仓库取货口必须长边贴左/下边且向内")
        units[uid] = unit
        for edge in edges:
            for pos in edge["positions"]:
                p, side = quantity(pos), edge["side"]
                x, y = {"south": (p, 0), "north": (p, height - 1), "west": (0, p), "east": (width - 1, p)}[side]
                x, y = rotate_cell(x, y, width, height, turns)
                dx, dy = DIRECTIONS[side]
                for _ in range(turns):
                    dx, dy = -dy, dx
                pid = f"{uid}:{side}:{p}"
                ports[pid] = {"unit": uid, "cell": (ox + x, oy + y), "normal": (dx, dy), "role": edge["role"], "axis": edge["axis"], "family": kind["family"]}
    core_count = sum(u["kind"] == "协议核心" for u in units.values())
    require(core_count == 1 if complete else core_count <= 1, "完整快照须有且仅有一个协议核心")
    channels = []
    by_face = {(p["cell"], p["normal"]): pid for pid, p in ports.items()}
    require(len(by_face) == len(ports), "多个端口占同一格边")
    for pid, port in ports.items():
        if port["role"] != "output":
            continue
        x, y = port["cell"]
        dx, dy = port["normal"]
        other = by_face.get(((x + dx, y + dy), (-dx, -dy)))
        if other and ports[other]["role"] == "input" and "transport" in {port["family"], ports[other]["family"]}:
            channels.append({"id": f"PC|{pid}|{other}", "source_port": pid, "target_port": other})
    buffers = []
    for uid, unit in units.items():
        kind = kinds[unit["kind"]]
        if kind["family"] != "manufacturing":
            continue
        counts = {row["role"]: quantity(row["count"]) for row in kind["inventory"]}
        for role in ("input", "output"):
            for index in range(counts[role]):
                ordinary, buffer = f"{uid}:{role}:{index}", f"{uid}:buffer:0"
                source, target = (ordinary, buffer) if role == "input" else (buffer, ordinary)
                buffers.append({"id": f"BC|{source}|{target}", "source_slot": source, "target_slot": target})
    return kinds, units, ports, channels, buffers, len(occupied)


def validate_timeline(timeline):
    """只检查事件身份和偏序可满足性，不认证事件后效。"""
    fields(timeline, "events relations connection_events", "timeline")
    events = {}
    kinds = {"build", "debug_operation", "offline", "blueprint_complete", "debug_end", "unit_removed", "unit_rebuilt", "connection_open", "connection_close", "withdraw_product", "runtime"}
    for event in timeline["events"]:
        fields(event, "id kind time", "event")
        identifier = event["id"]
        require(isinstance(identifier, str) and identifier and identifier not in events, "全局事件 id 重复或非法")
        require(event["kind"] in kinds, "未知事件种类")
        require(event['kind'] == 'runtime' or not identifier.startswith(('J|', 'C|', 'W|')),
                '非运行事件占用运行事件保留前缀: '+identifier)
        time = event["time"]
        if time is not None:
            fields(time, "kind value", "Time")
            require(time["kind"] in {"symbol", "rational"}, "时间类型非法")
            if time["kind"] == "rational":
                quantity(time["value"], integer=False)
            else:
                require(isinstance(time["value"], str) and time["value"], "时刻符号非法")
        events[identifier] = event
    parent = {identifier: identifier for identifier in events}

    def root(identifier):
        while parent[identifier] != identifier:
            identifier = parent[identifier]
        return identifier

    def unite(a, b):
        parent[root(a)] = root(b)

    times = {}
    for identifier, event in events.items():
        time = event["time"]
        if time is not None:
            key = (time["kind"], time["value"] if time["kind"] == "symbol" else quantity(time["value"], integer=False))
            if key in times:
                unite(identifier, times[key])
            times[key] = identifier
    relations = []
    for relation in timeline["relations"]:
        fields(relation, "before after relation basis", "relation")
        a, b, kind = (relation[key] for key in ("before", "after", "relation"))
        require(a in events and b in events, "时间关系引用悬空")
        require(kind in {"strict", "same_time", "occurs_before"} and relation["basis"], "时间关系种类或依据非法")
        if kind == "same_time":
            unite(a, b)
        relations.append((a, b, kind))
    # 含严格边的非负先后闭环无解；执行先后本身也不能成环。
    execution = {identifier: set() for identifier in events}
    order = {root(identifier): {} for identifier in events}
    for a, b, kind in relations:
        if kind == "same_time":
            continue
        execution[a].add(b)
        ra, rb = root(a), root(b)
        if ra == rb:
            require(kind != "strict", "等时事件不能严格先后")
        else:
            order[ra][rb] = order[ra].get(rb, False) or kind == "strict"
    pending = set(execution)
    while pending:
        sources = {x for x in pending if not any(x in execution[y] for y in pending)}
        require(sources, "事件执行先后成环")
        pending -= sources
    for start in order:
        todo = [(start, False)]
        seen = set()
        while todo:
            current, strict = todo.pop()
            if (current, strict) in seen:
                continue
            seen.add((current, strict))
            require(not (current == start and strict), "事件时刻关系矛盾")
            todo.extend((other, strict or edge) for other, edge in order[current].items())
    constants = {}
    for identifier, event in events.items():
        time = event["time"]
        if time is not None and time["kind"] == "rational":
            value = quantity(time["value"], integer=False)
            group = root(identifier)
            require(group not in constants or constants[group] == value, "等时类数值冲突")
            constants[group] = value
    for start, value in constants.items():
        todo, seen = [(start, False)], set()
        while todo:
            current, strict = todo.pop()
            if (current, strict) in seen:
                continue
            seen.add((current, strict))
            if current in constants:
                require(value < constants[current] if strict else value <= constants[current], "数值时刻与先后矛盾")
            todo.extend((other, strict or edge) for other, edge in order[current].items())
    return events


def check(data, path):
    fields(data, "schema purpose catalog timeline layout construction settings parameters initial_state debug_operations environment contract_binding scenario", "root")
    require(data["schema"] in {"kernel-input-v2", "kernel-input-v3"}, "输入版本非法")
    runtime = data["schema"] == "kernel-input-v3" and data["purpose"] == "synthetic_execution"
    require(data["purpose"] in {"synthetic_geometry", "synthetic_execution"}, "unsupported: 本程序只检查合成布局子集")
    fields(data["catalog"], "path sha256", "catalog")
    catalog_path = (path.parent / data["catalog"]["path"]).resolve()
    require(catalog_path == BASE.parent / "正式静态目录.json", "须引用共享目录")
    require(hashlib.sha256(catalog_path.read_bytes()).hexdigest() == data["catalog"]["sha256"], "共享目录哈希不匹配，须重新核对")
    catalog = load_json(catalog_path)
    require(catalog["schema"] == "static-catalog-v2", "目录版本不支持")
    events = validate_timeline(data["timeline"])
    layout = data["layout"]
    fields(layout["anchor"], "event side", "layout.anchor")
    require(layout["anchor"]["event"] in events and layout["anchor"]["side"] in {"before", "after"}, "几何快照锚点非法")
    require(isinstance(layout["id"], str) and layout["id"], "快照 id 非法")
    require(layout["snapshots"] == [], "unsupported: 最小程序不回放多阶段快照")
    decision(layout["post_debug"], {"specified"} if runtime else {"unresolved"})
    if runtime:
        require(layout["post_debug"]["value"] == layout["id"], "unsupported: 运行例只支持无结构调试")
    require(data["debug_operations"] == [], "unsupported: 此子集不检查非空调试程序")
    require(data["environment"]["offline"]["selected_events"] == [], "unsupported: 此子集不检查具体离线见证")
    require(data["environment"]["product_withdrawal"]["selected_events"] == [], "unsupported: 此子集不执行成品拿取历史")
    kinds, units, ports, channels, buffers, area = geometry(data, catalog)
    construction = data["construction"]
    fields(construction, "mode order_domain selected_order moments complete_event", "construction")
    require(construction["mode"] == "blueprint_once" and construction["order_domain"] == "all_rule_consistent_orders", "蓝图历史域非法")
    order = construction["selected_order"]
    require(order is not None, "unsupported: 最小程序要求完整 selected_order 见证")
    require(isinstance(order, list) and len(order) == len(units) and set(order) == set(units), "建造见证必须每单位恰一次")
    rank = {uid: i for i, uid in enumerate(order)}
    seen_belt = False
    for uid in order:
        if units[uid]["kind"] == "传送带":
            seen_belt = True
        else:
            require(not seen_belt, "蓝图传送带必须最后建造")
    moments = construction["moments"]
    require(len(moments) == len(order), "建成时刻缺项")
    build_events, symbols, by_unit = [], set(), {}
    for uid, moment in zip(order, moments):
        fields(moment, "event unit placement", "moment")
        require(moment["unit"] == uid, "建成记录与建造序不符")
        event_id = moment["event"]
        require(event_id in events and events[event_id]["kind"] == "build", "建造事件引用非法")
        time = events[event_id]["time"]
        require(time is not None and time["kind"] == ("rational" if runtime else "symbol"), "unsupported: 建成时刻类型不在检查子集")
        symbol = quantity(time["value"], integer=False) if runtime else time["value"]
        require(runtime or symbol not in symbols, "静态符号建成时刻须互异")
        placement = {key: units[uid][key] for key in ("kind", "origin", "rotation", "port_layout", "occupied_cells")}
        fields(moment["placement"], "kind origin rotation port_layout occupied_cells", "placement")
        require(moment["placement"] == placement, "unsupported: 最小程序不回放几何变化")
        symbols.add(symbol)
        build_events.append(event_id)
        by_unit[uid] = event_id
    complete = construction["complete_event"]
    end = data["environment"]["debug_end_event"]
    require(complete in events and events[complete]["kind"] == "blueprint_complete", "蓝图完成事件非法")
    require(end in events and events[end]["kind"] == "debug_end", "调试结束事件非法")
    require(layout["anchor"] == {"event": complete, "side": "after"}, "unsupported: 此子集只检蓝图完成快照")
    # 把结构隐含关系加入交集，不能仅核用户显式写下的一半关系。
    merged = copy.deepcopy(data["timeline"])
    for before, after in zip(build_events, build_events[1:]):
        merged["relations"].append({"before": before, "after": after, "relation": "occurs_before" if runtime else "strict", "basis": ["蓝图见证"]})
    for before, after in [(event, complete) for event in build_events] + [(complete, end)]:
        merged["relations"].append({"before": before, "after": after, "relation": "occurs_before", "basis": ["阶段边界"]})
    bridge_evidence = []
    for uid, unit in units.items():
        if unit["kind"] != "桥接器":
            continue
        for axis in ("vertical", "horizontal"):
            state = unit["bridge_axes"][axis]
            peers = []
            for pid, port in ports.items():
                if port["unit"] != uid or port["axis"] != axis:
                    continue
                x, y = port["cell"]
                dx, dy = port["normal"]
                for other, peer in ports.items():
                    if peer["cell"] == (x + dx, y + dy) and peer["normal"] == (-dx, -dy):
                        peers.append((max(rank[uid], rank[peer["unit"]]), pid, other))
            if not peers:
                require(state["status"] == "pending", "unsupported: 无接触桥轴须给未定向状态及历史")
                bridge_evidence.append({"unit": uid, "axis": axis, "status": "pending"})
                continue
            require(state["status"] == "resolved", "unsupported: 有邻口但桥轴方向未解决")
            first_rank = min(row[0] for row in peers)
            first = [row for row in peers if row[0] == first_rank]
            require(len(first) == 1, "unsupported: 桥接器首次平局")
            _, pid, other = first[0]
            require(units[ports[other]["unit"]]["kind"] != "桥接器", "unsupported: 桥定向互依赖")
            require(ports[pid]["role"] != ports[other]["role"], "unsupported: 桥先接读法分歧，不能无条件判桥方向非法")
            directed = [row for row in peers if ports[row[1]]["role"] != ports[row[2]]["role"]]
            require(directed and min(row[0] for row in directed) == first_rank, "unsupported: 桥先接读法分歧")
            bridge_evidence.append({"unit": uid, "axis": axis, "first_peer": other, "scope": "两种已登记先接读法的一致唯一非桥见证"})
    for field, derived in (("physical_channels", channels), ("buffer_channels", buffers)):
        declared = layout[field]
        if declared is not None:
            require(isinstance(declared, list) and sorted(declared, key=lambda x: x["id"]) == sorted(derived, key=lambda x: x["id"]), f"{field}: 必须等于全部导出通道，不能遗漏/伪造")
    channel_map = {row["id"]: row for row in channels}
    connected, owned = set(), set(build_events) | {complete, end}
    for record in data["timeline"]["connection_events"]:
        fields(record, "event channel action cause geometry_snapshot construction_basis", "connection_event")
        event_id, channel_id = record["event"], record["channel"]
        require(event_id in events and event_id not in owned, "接通事件重复或悬空")
        require(record["action"] == "open" and events[event_id]["kind"] == "connection_open", "unsupported: 此子集只核首次接通")
        require(channel_id in channel_map and channel_id not in connected, "首次接通通道重复或悬空")
        require(record["geometry_snapshot"] == layout["id"], "接通几何快照引用不符")
        channel = channel_map[channel_id]
        source, target = [ports[channel[key]]["unit"] for key in ("source_port", "target_port")]
        later = by_unit[max((source, target), key=rank.get)]
        decision(record["construction_basis"], {"specified"})
        require(record["construction_basis"]["value"] == {"source_build": by_unit[source], "target_build": by_unit[target], "later_build": later}, "接通必须引用两端最近建成及较晚端")
        require(record["cause"] == later, "首次接通原因不是较晚建成端")
        merged["relations"].extend([
            {"before": later, "after": event_id, "relation": "same_time", "basis": ["接通"]},
            {"before": later, "after": event_id, "relation": "occurs_before", "basis": ["原因到接通后效"]},
            {"before": event_id, "after": complete, "relation": "occurs_before", "basis": ["完成包含接通后效"]},
        ])
        connected.add(channel_id)
        owned.add(event_id)
    require(connected == set(channel_map), "首次接通事件记录缺边")
    require(set(events) == owned, "unsupported: 此子集不解释额外事件或其归属")
    validate_timeline(merged)
    settings = data["settings"]
    fields(settings, "anchor switches gates warehouse_assignments", "settings")
    require(settings["anchor"] == layout["anchor"], "unsupported: 最小程序要求设定与几何同锚点")
    switch_pairs = []
    for switch in settings["switches"]:
        fields(switch, "unit function enabled", "switch")
        require(switch["unit"] in units, "开关引用不存在单位")
        require(type(switch["enabled"]) is bool, "unsupported: 此子集要求显式候选开关")
        switch_pairs.append((switch["unit"], switch["function"]))
    expected_switches = {(uid, fn) for uid, unit in units.items() for fn in kinds[unit["kind"]]["powered_functions"]}
    require(len(switch_pairs) == len(expected_switches) and set(switch_pairs) == expected_switches, "需电功能开关缺失/重复/越权")
    recipes = {row["id"]: row for row in catalog["recipes"]}
    items = {item for row in recipes.values() for side in ("inputs", "outputs") for item in row[side]}
    gates = []
    for gate in settings["gates"]:
        fields(gate, "unit item total_limit window_limit", "gate")
        gates.append(gate["unit"])
        require(gate["item"] is None or gate["item"] in items, "unsupported: 准入口物种不在当前目录子集")
        for name, upper in (("total_limit", 5000), ("window_limit", 5)):
            if gate[name] is not None:
                require(gate["item"] is not None and 1 <= quantity(gate[name]) <= upper, "准入口限额非法")
    expected_gates = {uid for uid, unit in units.items() if unit["kind"] == "物品准入口"}
    require(len(gates) == len(expected_gates) and set(gates) == expected_gates, "准入口设定缺失/重复")
    slots = {}
    warehouse_counts = {}
    validate_slot_identity(data['initial_state']['warehouse'])
    for slot in data["initial_state"]["warehouse"]["slots"]:
        fields(slot, "slot item quantity empty_identity", "warehouse_slot")
        sid, item = slot["slot"], slot["item"]
        require(isinstance(sid, str) and sid and sid not in slots, "仓库格 id 重复或非法")
        require(item is None or item in items, "unsupported: 仓库物种不在当前目录子集")
        count = quantity(slot["quantity"])
        require(count >= 0 and ((item is None) == (count == 0)), "仓库数量与实际物种不符")
        decision(slot["empty_identity"], {"unresolved", "specified", "derived"} if item is None else {"not_applicable"}, nullable=True)
        if item is None and slot["empty_identity"]["status"] == "specified":
            require(slot["empty_identity"]["value"] is None or slot["empty_identity"]["value"] in items, "空格历史身份非法")
        slots[sid], warehouse_counts[sid] = item, count
    named = [item for item in slots.values() if item is not None]
    require(len(set(named)) == len(named), "仓库同一种物品不能多格")
    assignments = []
    for assignment in settings["warehouse_assignments"]:
        fields(assignment, "port slot", "assignment")
        require(assignment["slot"] in slots, "仓库指派悬空")
        if slots[assignment["slot"]] is None:
            empty = next(x["empty_identity"] for x in data["initial_state"]["warehouse"]["slots"] if x["slot"] == assignment["slot"])
            require(empty["status"] in {"specified", "derived"}, "指派空仓库格必须给 empty_identity 决策")
            require(empty["status"] != "derived", "unsupported: 空格身份派生表达式尚未求值")
        assignments.append(assignment["port"])
    expected_assignments = {pid for pid, port in ports.items() if port["role"] == "output" and units[port["unit"]]["kind"] in {"协议核心", "仓库取货口"}}
    require(len(assignments) == len(expected_assignments) and set(assignments) == expected_assignments, "须逐一指派核心及全部仓库取货口")
    parameters = data["parameters"]
    fields(parameters, "axis_registry profile_id fixed offline_mutable fixedness_unproven", "parameters")
    fields(parameters["axis_registry"], "path sha256", "axis_registry")
    require((path.parent / parameters["axis_registry"]["path"]).resolve() == AXIS_PATH, "参数须引用正式轴表")
    require(hashlib.sha256(AXIS_PATH.read_bytes()).hexdigest() == parameters["axis_registry"]["sha256"], "参数轴表哈希变化，须重新对齐")
    require(parameters["profile_id"] == ("kernel_profile_v1" if runtime else None), "unsupported: 未支持的受限语义配置")
    registry = axis_registry()
    for group in ("fixed", "offline_mutable", "fixedness_unproven"):
        fields(parameters[group], " ".join(name for name, row in registry.items() if ("fixed" if runtime and name == "judgment.order" else row["group"]) == group), group)
        for name, value in parameters[group].items():
            if name in KNOWN_VALUES:
                decision(value, {"specified"})
                require(type(value["value"]) is type(KNOWN_VALUES[name]) and value["value"] == KNOWN_VALUES[name], f"已定轴值不符: {name}")
            elif name in {"connection.build_order", "connection.order"}:
                decision(value, {"derived"})
                expected = "construction.selected_order" if name == "connection.build_order" else "timeline_connection_history"
                require(value["value"] == expected, "接通先后/建造史必须从历史导出")
            elif name == 'connection.port_meeting':
                decision(value, {'specified'})
                require(value['value'] == 'shared_edge_opposite', 'unsupported: 未实现的相遇读法')
            elif name == "transfer.phase" and value["status"] == "not_applicable":
                decision(value, {"not_applicable"})
                require(all(u["kind"] != "协议储存箱" for u in units.values()), "有箱体不能无据消去相位")
            else:
                decision(value, {"specified", "derived"} if runtime else {"unresolved"})
    initial = data["initial_state"]
    fields(initial, "anchor warehouse nonwarehouse reachability", "initial_state")
    for name in ("anchor", "nonwarehouse", "reachability"):
        decision(initial[name], {"specified"} if runtime else {"unresolved"})
    fields(initial["warehouse"], "slots unlisted", "warehouse_initial")
    require(initial["warehouse"]["unlisted"] == "empty", "未列物品仍须服从其他为空")
    require(INITIAL_ITEMS <= set(slots.values()), "缺初始满的六类物品")
    core_capacity = quantity(kinds["协议核心"]["inventory"][0]["capacity"])
    for sid, item in slots.items():
        require(warehouse_counts[sid] == (core_capacity if item in INITIAL_ITEMS else 0), "任务仓库初态不符")
    require(data["debug_operations"] == [], "unsupported: 此子集不检查非空调试程序")
    environment = data["environment"]
    fields(environment, "ore_supply offline product_withdrawal debug_end_event zero_intervention_after_debug", "environment")
    require(environment["ore_supply"] == "task_continuous_sufficient" and environment["zero_intervention_after_debug"] is True, "任务环境不符")
    fields(environment["product_withdrawal"], "policy selected_events", "product_withdrawal")
    decision(environment["product_withdrawal"]["policy"], {"specified"} if runtime else {"unresolved"})
    fields(environment["offline"], "event_domain selected_events", "offline")
    decision(environment["offline"]["event_domain"], {"specified"} if runtime else {"unresolved"})
    require(environment["offline"]["selected_events"] == [], "unsupported: 此子集不检查具体离线见证")
    require(data["contract_binding"] is None, "unsupported: 此子集不检查外部契约映射")
    scenario = data["scenario"]
    fields(scenario, "name recipe_intents expected_paths assertions", "scenario")
    require(isinstance(scenario["name"], str) and scenario["name"], "场景需有中文名称")
    intents = {}
    for intent in scenario["recipe_intents"]:
        fields(intent, "unit recipes", "recipe_intent")
        uid = intent["unit"]
        require(uid in units and uid not in intents, "配方意图的单位引用非法/重复")
        require(intent["recipes"] and len(set(intent["recipes"])) == len(intent["recipes"]), "配方意图为空或重复")
        for rid in intent["recipes"]:
            require(rid in recipes and recipes[rid]["kind"] == units[uid]["kind"], "配方 id 与机型不匹配")
        intents[uid] = intent["recipes"]
    path_endpoints = []
    path_names = set()
    for route in scenario["expected_paths"]:
        fields(route, "name physical_channels", "expected_path")
        require(route["name"] not in path_names, "路径名重复")
        path_names.add(route["name"])
        ids = route["physical_channels"]
        require(ids and all(cid in channel_map for cid in ids), "路径包含不存在的实体通道")
        edges = [channel_map[cid] for cid in ids]
        for left, right in zip(edges, edges[1:]):
            a, b = ports[left["target_port"]], ports[right["source_port"]]
            require(a["unit"] == b["unit"] and a["family"] == "transport", "路径不连续或穿越非运输端点")
            if units[a["unit"]]["kind"] == "桥接器":
                require(a["axis"] == b["axis"], "桥接器路径跨轴")
        path_endpoints.append((ports[edges[0]["source_port"]]["unit"], ports[edges[-1]["target_port"]]["unit"]))
    require(isinstance(scenario["assertions"], list), "结构断言必须为数组")
    for assertion in scenario["assertions"]:
        fields(assertion, "kind unit", "assertion")
        uid, name = assertion["unit"], assertion["kind"]
        require(uid in units, "断言引用单位不存在")
        incoming = [c for c in channels if ports[c["target_port"]]["unit"] == uid]
        outgoing = [c for c in channels if ports[c["source_port"]]["unit"] == uid]
        if name == "bridge_two_lanes":
            require(units[uid]["kind"] == "桥接器" and len(incoming) == len(outgoing) == 2, "桥须两进两出")
            require({ports[c["source_port"]]["axis"] for c in outgoing} == {"vertical", "horizontal"}, "桥缺一轴")
            require(len(scenario["expected_paths"]) == 2, "桥须列两条完整路径")
        elif name == "splitter_three_outputs":
            require(units[uid]["kind"] == "分流器" and len(incoming) == 1 and len(outgoing) == 3, "分流器须一进三出")
            require(len({max(rank[ports[c["source_port"]]["unit"]], rank[ports[c["target_port"]]["unit"]]) for c in outgoing}) == 3, "样例要求三出口接通见证无平局")
        elif name == "mixed_two_downstreams":
            require(units[uid]["kind"] == "粉碎机" and len(intents.get(uid, [])) >= 2, "须同一粉碎机有多配方意图")
            targets = {target for source, target in path_endpoints if source == uid}
            require(len(targets) == 2 and all(kinds[units[t]["kind"]]["family"] == "manufacturing" for t in targets), "混做机须连两台制造下游")
            outputs = {item for rid in intents[uid] for item in recipes[rid]["outputs"]}
            target_inputs = {item for target in targets for rid in intents.get(target, []) for item in recipes[rid]["inputs"]}
            require(outputs <= target_inputs, "下游配方未覆盖混做产物")
        else:
            raise CheckError("unsupported: 未实现的结构断言")
    if runtime:
        from runtime_example import validate_runtime
        validate_runtime(data, catalog, ports, channels, buffers)
    return {"file": str(path.resolve()), "status": "完整运行输入检查通过（有限合成子集）" if runtime else "指定快照静态结构通过", "snapshot": layout["id"], "anchor": layout["anchor"], "units": len(units), "occupied_cells": area, "physical_channels": len(channels), "buffer_channels": len(buffers), "bridge_first_peers": bridge_evidence, "counts_category": "算术推论（候选布局）", "validation_category": "实测（工具）"}


def negative_tests(documents):
    """关键不变量的破坏性内存副本；不写回样例。"""
    tests = []

    def reject(name, index, mutate, expected):
        data = copy.deepcopy(documents[index])
        mutate(data)
        try:
            check(data, BASE / NAMES[index])
        except CheckError as error:
            require(expected in str(error), f"负例未命中预期检查: {name}: {error}")
            tests.append({"name": name, "status": "正确拒绝", "reason": str(error)})
        else:
            raise CheckError(f"负例被放过: {name}")

    reject("占格重叠", 0, lambda d: d["layout"]["units"][1].update(origin=copy.deepcopy(d["layout"]["units"][0]["origin"])), "占格重叠")
    reject("基地越界", 0, lambda d: d["layout"]["units"][0]["origin"][0].update(value="69"), "越界")
    reject("伪造或遗漏实体通道", 0, lambda d: d["layout"]["physical_channels"].pop(), "physical_channels")
    reject("核心指派遗漏", 0, lambda d: d["settings"]["warehouse_assignments"].pop(), "逐一指派")
    reject("错误配方机型", 2, lambda d: d["scenario"]["recipe_intents"][0].update(recipes=["封装-电池"]), "配方 id 与机型")
    reject("传送带抢先建造", 2, lambda d: d["construction"]["selected_order"].insert(0, d["construction"]["selected_order"].pop()), "传送带必须最后")
    reject("未知参数轴", 0, lambda d: d["parameters"]["fixedness_unproven"].update(invented_axis={}), "fixedness_unproven")
    reject("未知顶层字段", 0, lambda d: d.update(powered=True), "root")
    reject("桥接器按轴调度", 0, lambda d: d["parameters"]["fixed"]["bridge.scheduling_scope"].update(value="per_axis"), "已定轴值不符")
    reject("仓库非六类满", 0, lambda d: d["initial_state"]["warehouse"]["slots"][0]["quantity"].update(value="1"), "仓库初态不符")
    reject("桥接器路径跨轴", 0, lambda d: d["scenario"]["expected_paths"][0]["physical_channels"].__setitem__(1, d["scenario"]["expected_paths"][1]["physical_channels"][1]), "跨轴")
    reject("未给完整建造见证属于超子集", 0, lambda d: d["construction"].update(selected_order=None), "unsupported:")
    reject("全局事件身份冲突", 0, lambda d: d["timeline"]["events"].append(copy.deepcopy(d["timeline"]["events"][0])), "全局事件 id 重复")
    reject("接通记录不可省略", 0, lambda d: d["timeline"]["connection_events"].pop(), "接通事件记录缺边")
    reject("接通原因不能沿用无关建成", 0, lambda d: d["timeline"]["connection_events"][0].update(cause="build_0"), "较晚建成端")
    reject("隐含蓝图序与显式关系冲突", 0, lambda d: d["timeline"]["relations"].append({"before": "build_2", "after": "build_0", "relation": "strict", "basis": ["反例"]}), "成环")
    reject("调试前快照不得冒充最终验收", 0, lambda d: d["layout"]["post_debug"].update(status="specified", value="built_layout"), "unsupported:")
    reject("未知桥轴不能静默缺边", 0, lambda d: d["layout"]["units"][2]["bridge_axes"]["horizontal"].update(status="unresolved", input_side=None), "unsupported:")
    def ambiguous_bridge(data):
        next(u for u in data["layout"]["units"] if u["id"] == "west_box")["rotation"] = "r90"
        next(m for m in data["construction"]["moments"] if m["unit"] == "west_box")["placement"]["rotation"] = "r90"
    reject("最早邻接与最早有向边分歧", 0, ambiguous_bridge, "unsupported: 桥先接读法分歧")
    return tests


def representation_tests(documents):
    """复核所指合法语法边界；不把表示试验写成运行见证。"""
    results = []
    base = documents[0]
    redundant = copy.deepcopy(base)
    redundant["timeline"]["relations"].append({"before": "build_0", "after": "build_2", "relation": "strict", "basis": ["已有关系的传递结果"]})
    check(redundant, BASE / NAMES[0])
    results.append("一致的冗余时刻关系通过")
    empty = copy.deepcopy(base)
    for index in range(2):
        empty["initial_state"]["warehouse"]["slots"].append({"slot": f"empty_{index}", "item": None, "quantity": {"value": "0", "category": "候选"}, "empty_identity": {"status": "unresolved", "value": None, "basis": ["仓库空格历史未定"]}})
        check(empty, BASE / NAMES[0])
    results.append("一个及两个无物种空格均通过，不按 null 判同物种")
    idle_axis = copy.deepcopy(base)
    for uid, x in (("west_box", 2), ("east_box", 25)):
        unit = next(u for u in idle_axis["layout"]["units"] if u["id"] == uid)
        unit["origin"][0]["value"] = str(x)
        next(m for m in idle_axis["construction"]["moments"] if m["unit"] == uid)["placement"]["origin"] = copy.deepcopy(unit["origin"])
    bridge = next(u for u in idle_axis["layout"]["units"] if u["kind"] == "桥接器")
    bridge["bridge_axes"]["horizontal"] = {"status": "pending", "input_side": None, "basis": ["该轴未有相邻端口"]}
    catalog = load_json(BASE.parent / "正式静态目录.json")
    channels = geometry(idle_axis, catalog)[3]
    idle_axis["layout"]["physical_channels"] = channels
    channel_ids = {c["id"] for c in channels}
    records = [r for r in idle_axis["timeline"]["connection_events"] if r["channel"] in channel_ids]
    removed = {r["event"] for r in idle_axis["timeline"]["connection_events"] if r["channel"] not in channel_ids}
    idle_axis["timeline"]["connection_events"] = records
    idle_axis["timeline"]["events"] = [e for e in idle_axis["timeline"]["events"] if e["id"] not in removed]
    idle_axis["scenario"]["expected_paths"] = idle_axis["scenario"]["expected_paths"][:1]
    idle_axis["scenario"]["assertions"] = []
    check(idle_axis, BASE / NAMES[0])
    results.append("只接一轴的桥保留另一轴 pending 并通过结构检查")
    # 时间线语法能区分离线与操作的两个方向；两者都不冒充后效合法。
    def relation(a, b, kind="occurs_before"):
        return {"before": a, "after": b, "relation": kind, "basis": ["表示回归"]}
    def event(identifier, kind):
        return {"id": identifier, "kind": kind, "time": None}
    for a, b in (("offline_a", "set_gate_a"), ("set_gate_a", "offline_a")):
        timeline = {"events": [event("build_a", "build"), event("set_gate_a", "debug_operation"), event("offline_a", "offline")], "relations": [relation("build_a", a), relation(a, b)], "connection_events": []}
        validate_timeline(timeline)
    results.append("建成、离线、改设定共用引用域且两种相反次序可分别保存")
    equal = {"events": [event("offline_a", "offline"), event("set_gate_a", "debug_operation")], "relations": [relation("offline_a", "set_gate_a", "same_time"), relation("offline_a", "set_gate_a")], "connection_events": []}
    validate_timeline(equal)
    equal["relations"].append(relation("offline_a", "set_gate_a", "strict"))
    try:
        validate_timeline(equal)
    except CheckError as error:
        require("等时" in str(error), "等时冲突诊断错误")
    else:
        raise CheckError("同刻严格先后矛盾未被拒绝")
    results.append("同刻交织可保存，等时与严格先后冲突会拒绝")
    rotated = copy.deepcopy(base)
    rotated["layout"]["id"] = "after_rotation"
    rotated["layout"]["anchor"] = {"event": "rotate_a", "side": "after"}
    next(u for u in rotated["layout"]["units"] if u["id"] == "south_box")["rotation"] = "r180"
    new_geometry = geometry(rotated, catalog)
    require(new_geometry[3] != geometry(base, catalog)[3], "旋转后端口相遇表未重新导出")
    require(rotated["construction"]["moments"] == base["construction"]["moments"], "新快照不应覆盖首次建成几何")
    results.append("新旋转快照可独立重算 PC，首次 placement 保持独立；未认证动作可达性")
    reconnect = {"events": [event(identifier, kind) for identifier, kind in (("build_a", "build"), ("build_b", "build"), ("open_1", "connection_open"), ("rebuild_a", "debug_operation"), ("remove_a", "unit_removed"), ("close_1", "connection_close"), ("built_again", "unit_rebuilt"), ("open_2", "connection_open"))], "relations": [], "connection_events": []}
    chain = [e["id"] for e in reconnect["events"]]
    reconnect["relations"] = [relation(a, b) for a, b in zip(chain, chain[1:])]
    reconnect["relations"] += [relation("build_b", "open_1", "same_time"), relation("built_again", "open_2", "same_time")]
    channel = base["layout"]["physical_channels"][0]["id"]
    for identifier, action, cause, snapshot, left, right, later in (("open_1", "open", "build_b", "before_rebuild", "build_a", "build_b", "build_b"), ("close_1", "close", "remove_a", "before_rebuild", "build_a", "build_b", "build_b"), ("open_2", "open", "built_again", "after_rebuild", "built_again", "build_b", "built_again")):
        reconnect["connection_events"].append({"event": identifier, "channel": channel, "action": action, "cause": cause, "geometry_snapshot": snapshot, "construction_basis": {"status": "specified", "value": {"source_build": left, "target_build": right, "later_build": later}, "basis": ["重建表示片段，非运行证据"]}})
    validate_timeline(reconnect)
    require(len({row["event"] for row in reconnect["connection_events"]}) == 3 and len({row["channel"] for row in reconnect["connection_events"]}) == 1, "通道身份与接通实例混同")
    results.append("同一 PC 的开闭再开保留三个独立事件及新的建成依据；仅表示测试")
    # 拦截候选文件读取并使其抛错，证明整个样例自查不再依赖它。
    from unittest.mock import patch
    original = Path.read_bytes
    def read_bytes(path):
        if path.name == "候选约束.txt":
            raise AssertionError("样例检查不应读取候选约束")
        return original(path)
    with patch.object(Path, "read_bytes", read_bytes):
        for data, name in zip(documents, NAMES):
            check(data, BASE / name)
        require({name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_HASHES} == SOURCE_HASHES, "正式来源变化")
    results.append("候选文件不可读时样例及正式来源检查仍通过")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="运行关键不变量负例")
    parser.add_argument("--report", type=Path, help="将报告写入求解器内")
    parser.add_argument("files", nargs="*", type=Path, help="默认检查三个交付样例")
    args = parser.parse_args()
    paths = args.files or [BASE / name for name in NAMES]
    documents = [load_json(path) for path in paths]
    results = [check(data, path) for data, path in zip(documents, paths)]
    fingerprints = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_HASHES}
    require(fingerprints == SOURCE_HASHES, "正式文件指纹与读取快照不同，须人工重新核对")
    negatives = negative_tests([load_json(BASE / name) for name in NAMES]) if args.self_test else []
    regressions = representation_tests([load_json(BASE / name) for name in NAMES]) if args.self_test else []
    specification = ROOT / "求解器/规格/内核输入.md"
    document = specification.read_text()
    document_axes = re.findall(r"^\| `([^`]+)` \| `(?:fixed|offline_mutable|fixedness_unproven)`", document, re.M)
    require(len(document_axes) == len(set(document_axes)) and set(document_axes) == set(axis_registry()), "文档参数字段与轴表不一致")
    links = re.findall(r"\]\(([^)]+)\)", document)
    require(all((specification.parent / link.split("#")[0]).exists() for link in links if not link.endswith("检查结果.json")), "文档存在悬空本地引用")
    artifacts = paths + [specification, Path(__file__).resolve(), BASE / "generate_examples.py"]
    report = {
        "status": "通过", "scope": "静态结构及指定运行种子检查，不是全称运行认证", "results": results,
        "negative_tests": negatives, "representation_tests": regressions, "readonly_source_hashes": fingerprints,
        "axis_registry_sha256": hashlib.sha256(AXIS_PATH.read_bytes()).hexdigest(),
        "axis_count": len(axis_registry()), "axis_alignment": "全部字段名、已定值和生命周期逐项检查",
        "document_checks": {"axis_names_match": True, "local_links_resolve": True},
        "artifact_sha256": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},
        "unverified": ["供电覆盖格集合", "实际库存与进度", "调试可达性", "轮询与均分", "实际混做及物流分配", "离线接续", "吞吐及全部可达循环达标", "外部契约绑定与非空调试程序"],
    }
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        target = args.report.resolve()
        require(target.is_relative_to(ROOT / "求解器"), "报告只能写入求解器")
        require(target not in [p.resolve() for p in paths] and target.suffix == ".json", "报告不能覆盖输入且须为 JSON")
        target.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    try:
        main()
    except (CheckError, KeyError, TypeError, ValueError, OSError) as error:
        print(json.dumps({"status": "unsupported" if str(error).startswith("unsupported:") else "invalid", "reason": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
