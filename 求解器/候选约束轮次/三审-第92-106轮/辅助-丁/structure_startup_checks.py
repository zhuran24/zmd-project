#!/usr/bin/env python3
"""第32、33项的独立结构、交换与起态数字核算；无外部依赖。"""
from collections import Counter, defaultdict, deque
from fractions import Fraction as F
from itertools import permutations, product
from pathlib import Path
import json
import re
import time

OUT = Path(__file__).resolve().parent
ROUNDS = OUT.parent.parent
RULES = ROUNDS / "第107-109轮/前提快照/《明日方舟：终末地》游戏规则.txt"


def order_checks():
    # 四个同层发送元件；0、1向运输格R0，2、3向双存货格机器R1。
    # 状态编码: 0空，1未成熟A，2成熟A，3成熟B，4成熟但不能回送A，5未成熟B。
    orders = tuple(permutations(range(4)))
    recipient0 = ((), (("A", 1),), (("B", 1),))
    recipient1 = ((), (("A", 49),), (("A", 50),), (("A", 50), ("B", 49)), (("A", 50), ("B", 50)))
    def step(initial, inventory, wheels, order):
        packets = list(initial)
        stores = [dict(inventory[0]), dict(inventory[1])]
        pointers = list(wheels)
        handled = set()
        receipts = [[], []]
        for u in order:
            if u in handled:
                continue
            g = u // 2
            if packets[u] not in (2, 3):
                handled.add(u)
                continue
            members = [2 * g + pointers[g], 2 * g + 1 - pointers[g]]
            for v in members:
                if v in handled:
                    continue
                handled.add(v)
                if packets[v] not in (2, 3):
                    continue
                kind = "A" if packets[v] == 2 else "B"
                allowed = not stores[g] if g == 0 else (stores[g].get(kind, 0) < 50 and (kind in stores[g] or len(stores[g]) < 2))
                if allowed:
                    stores[g][kind] = stores[g].get(kind, 0) + 1
                    packets[v] = 0
                    pointers[g] = 1 - (v % 2)
                    receipts[g].append((kind, v))
        return tuple(packets), tuple(tuple(sorted(s.items())) for s in stores), tuple(pointers), tuple(tuple(x) for x in receipts)
    states = comparisons = 0
    for packets, r0, r1, wheels in product(product(range(6), repeat=4), recipient0, recipient1, product(range(2), repeat=2)):
        inventory = (r0, r1)
        expected = step(packets, inventory, wheels, orders[0])
        states += 1
        for order in orders:
            assert step(packets, inventory, wheels, order) == expected
            comparisons += 1
    # 独占首格下的非运输判定交换，包括本次成功记录和来源记录。
    nontransport = 0
    for occupied, has_goods, wheels in product(product((False, True), repeat=4), product((False, True), repeat=2), product((0, 1), repeat=2)):
        def send(order):
            cells = ["old" if x else None for x in occupied]
            remaining = list(has_goods)
            history = list(wheels)
            for u in order:
                if remaining[u]:
                    for offset in (wheels[u], 1 - wheels[u]):
                        j = 2 * u + offset
                        if cells[j] is None:
                            cells[j] = ("ore", u)
                            history[u] = offset
                            remaining[u] = False
                            break
            return cells, remaining, history
        assert send((0, 1)) == send((1, 0))
        nontransport += 1
    # 删掉独占非运输来源前提时，两种顺序实际给出不同来源。
    def shared_send(order):
        cell = None
        source_items = {0: "A", 1: "B"}
        for u in order:
            if cell is None:
                cell = (source_items[u], u)
        return cell
    shared_negative = {"order_01_first_cell": shared_send((0, 1)), "order_10_first_cell": shared_send((1, 0))}
    assert shared_negative["order_01_first_cell"] != shared_negative["order_10_first_cell"]
    return dict(complete_local_states=states, order_comparisons=comparisons, permutations_per_state=len(orders), nontransport_cases=nontransport, shared_nontransport_source_negative_control=shared_negative, scope="局部交换引理；不是所有70x70几何的枚举。两种初始轮询位置均覆盖，未把不同历史合并。")


def blueprint():
    nodes, edges, roots, plants = {}, [], set(), set()
    def add(prefix, count, kind, correct_inputs, correct_output):
        ans = []
        for j in range(count):
            name = f"{prefix}{j}"
            nodes[name] = dict(kind=kind, correct_inputs=set(correct_inputs), correct_output=correct_output)
            ans.append(name)
        return ans
    def link(a, b):
        edges.append((a, b))
    ir = add("矿铁炉", 34, "精炼炉", ["蓝铁矿"], "蓝铁块")
    ic = add("铁块粉碎", 34, "粉碎机", ["蓝铁块"], "蓝铁粉末")
    sc = add("源矿粉碎", 18, "粉碎机", ["源矿"], "源石粉末")
    gi = add("铁研磨", 17, "研磨机", ["蓝铁粉末", "砂叶粉末"], "致密蓝铁粉末")
    gs = add("源研磨", 9, "研磨机", ["源石粉末", "砂叶粉末"], "致密源石粉末")
    gb = add("荞研磨", 6, "研磨机", ["荞花粉末", "砂叶粉末"], "细磨荞花粉末")
    sr = add("钢炉", 17, "精炼炉", ["致密蓝铁粉末"], "钢块")
    p = add("配件", 6, "配件机", ["钢块"], "钢制零件")
    q = add("塑形", 6, "塑形机", ["钢块"], "钢质瓶")
    e = add("封装", 3, "封装机", ["钢制零件", "致密源石粉末"], "高容谷地电池")
    f = add("灌装", 3, "灌装机", ["钢质瓶", "细磨荞花粉末"], "精选荞愈胶囊")
    roots.update(ir + sc)
    for a, b in zip(ir, ic):
        link(a, b)
    for j, a in enumerate(ic):
        link(a, gi[j // 2])
    for j, a in enumerate(sc):
        link(a, gs[j // 2])
    for a, b in zip(gi, sr):
        link(a, b)
    for j, a in enumerate(sr):
        link(a, p[j] if j < 6 else q[(j - 6) // 2])
    for j in range(3):
        for a in p[2*j:2*j+2] + gs[3*j:3*j+3]:
            link(a, e[j])
        for a in q[2*j:2*j+2] + gb[2*j:2*j+2]:
            link(a, f[j])
    for plant, count in [("荞花", 6), ("砂叶", 11)]:
        ks = []
        for j in range(count):
            tag = f"{plant}{j}"
            a = add(tag + "A", 1, "种植机", [plant + "种子"], plant)[0]
            b = add(tag + "B", 1, "种植机", [plant + "种子"], plant)[0]
            c = add(tag + "C", 1, "采种机", [plant], plant + "种子")[0]
            k = add(tag + "K", 1, "粉碎机", [plant], plant + "粉末")[0]
            plants.update((a, b, c, k))
            ks.append(k)
            for u, v in ((c, a), (c, b), (a, c), (b, k)):
                link(u, v)
        if plant == "荞花":
            for k, g in zip(ks, gb):
                link(k, g)
                link(k, g)
        else:
            for j, g in enumerate(gi + gs + gb):
                link(ks[j // 3], g)
    assert len(nodes) == 221
    assert Counter(x["kind"] for x in nodes.values()) == Counter({"粉碎机": 69, "精炼炉": 51, "研磨机": 32, "塑形机": 6, "配件机": 6, "种植机": 34, "采种机": 17, "封装机": 3, "灌装机": 3})
    return nodes, edges, roots, plants


def recipes():
    result = defaultdict(list)
    kind = None
    types = {"粉碎机", "精炼炉", "研磨机", "塑形机", "配件机", "种植机", "采种机", "封装机", "灌装机"}
    for line in RULES.read_text().splitlines():
        s = line.strip()
        if s in types:
            kind = s
        if " → " in s:
            left, right = s.split(" → ")
            right, ticks = re.split(r"[,，]\s*", right)
            inp = {name: int(q) for q, name in (p.split(" ", 1) for p in left.split(" ＋ "))}
            q, name = right.split(" ", 1)
            result[kind].append((inp, {name: int(q)}))
    return result


def startup_structure():
    nodes, edges, roots, plants = blueprint()
    formulas = recipes()
    initial = {"源矿", "蓝铁矿", "荞花", "砂叶", "荞花种子", "砂叶种子"}
    inputs = {u: set(initial) if u in roots else set() for u in nodes}
    outputs = {u: set() for u in nodes}
    enabled = {u: [] for u in nodes}
    # 无视容量与具体数量的可能物种超集。初始无物的植物环不会自生物品。
    changed = True
    rounds = 0
    while changed:
        changed = False
        rounds += 1
        for u, data in nodes.items():
            for inp, out in formulas[data["kind"]]:
                if set(inp) <= inputs[u]:
                    if (inp, out) not in enabled[u]:
                        enabled[u].append((inp, out))
                    old = len(outputs[u])
                    outputs[u].update(out)
                    changed |= len(outputs[u]) != old
        for u, v in edges:
            old = len(inputs[v])
            inputs[v].update(outputs[u])
            changed |= len(inputs[v]) != old
    assert all(not inputs[u] and not outputs[u] for u in plants)
    assert all(not outputs[u] for u, d in nodes.items() if d["kind"] in {"配件机", "塑形机", "封装机", "灌装机"})
    plant_related = {"荞花", "砂叶", "荞花种子", "砂叶种子", "荞花粉末", "砂叶粉末", "细磨荞花粉末", "致密源石粉末", "致密蓝铁粉末", "钢块", "钢制零件", "钢质瓶", "高容谷地电池", "精选荞愈胶囊"}
    stock_nodes = [u for u in nodes if inputs[u] & plant_related]
    output_nodes = [u for u in nodes if outputs[u] & plant_related]
    cache_nodes = [u for u in nodes if any(set(inp) & plant_related for inp, out in enabled[u])]
    assert len(stock_nodes) == 64  # 52第一层 + 9源研磨 + 3封装。
    assert len(output_nodes) == len(cache_nodes) == 27
    stock_capacity = sum(50 * (2 if nodes[u]["kind"] in {"研磨机", "封装机", "灌装机"} else 1) for u in stock_nodes)
    output_capacity = sum(50 for u in output_nodes)
    cache_capacity = sum(3 for u in cache_nodes)
    transport_capacity = 2 * 70 * 70
    bound = stock_capacity + output_capacity + cache_capacity + transport_capacity
    direct = 52 * 50 + 18 * (50 + 3) + 9 * (100 + 50 + 3) + 3 * 100 + 2 * 70 * 70
    assert bound == direct == 15031
    remaining = 80000 - bound
    need = 11 * 50 + transport_capacity
    assert remaining == 64969 and need == 10350 and remaining >= need
    # 可制造的相关配方逐种植物原料当量守恒。每件至多1株，缓存保守<=3株。
    weights = {
        "荞花": {"荞花": F(1), "荞花粉末": F(1, 2), "细磨荞花粉末": F(1)},
        "砂叶": {"砂叶": F(1), "砂叶粉末": F(1, 3), "致密源石粉末": F(1, 3), "细磨荞花粉末": F(1, 3)},
        "荞花种子": {"荞花种子": F(1)},
        "砂叶种子": {"砂叶种子": F(1)},
    }
    for u in nodes:
        for inp, out in enabled[u]:
            for weight in weights.values():
                left = sum(q * weight.get(s, 0) for s, q in inp.items())
                right = sum(q * weight.get(s, 0) for s, q in out.items())
                assert left == right
                assert left <= 3
                assert all(weight.get(s, 0) <= 1 for s in out)
    # 矿石制造子图的拓扑序证实错货后代的制造阶段有限。
    mineral = set(nodes) - plants
    neighbors = defaultdict(list)
    indegree = {u: 0 for u in mineral}
    for u, v in edges:
        if u in mineral and v in mineral:
            neighbors[u].append(v)
            indegree[v] += 1
    queue = deque(sorted(u for u in mineral if indegree[u] == 0))
    topo, depth = [], {u: 1 for u in mineral}
    while queue:
        u = queue.popleft()
        topo.append(u)
        for v in neighbors[u]:
            depth[v] = max(depth[v], depth[u] + 1)
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    assert len(topo) == len(mineral) == 153
    # 清洁输入必须只允许本线配方，不能自发产生错货。
    for u, d in nodes.items():
        correct_recipes = [(i, o) for i, o in formulas[d["kind"]] if set(i) <= d["correct_inputs"]]
        assert len(correct_recipes) == 1
        assert set(correct_recipes[0][1]) == {d["correct_output"]}
    return dict(machine_counts=dict(Counter(d["kind"] for d in nodes.values())), machines=len(nodes), manufacturing_edges=len(edges), reachability_iterations=rounds, plant_network_empty_before_loading=True, no_finished_goods_before_loading=True, relevant_stock_nodes=stock_nodes, relevant_output_nodes=output_nodes, relevant_cache_nodes=cache_nodes, capacity_terms=dict(stock=stock_capacity, output=output_capacity, cache=cache_capacity, transport=transport_capacity), per_species_withdrawal_bound=bound, remaining_per_species=remaining, loading_upper_bound_per_species=need, minimum_remaining_after_loading=remaining-need, mineral_DAG_nodes=len(topo), maximum_manufacturing_stages=max(depth.values()))


def startup_inventory():
    def fill_path(original, movement):
        cells = list(original)
        added = moves = 0
        def advance():
            nonlocal moves
            if movement == "none":
                return
            while True:
                moved = False
                for j in range(len(cells) - 2, -1, -1):
                    if cells[j] and not cells[j + 1]:
                        cells[j], cells[j + 1] = False, True
                        moves += 1
                        moved = True
                if movement == "one_forward_sweep" or not moved:
                    return
        # 末端接满着且关闭的机器；放宽为无需等待成熟也可前移。
        for j in reversed(range(len(cells))):
            advance()
            if not cells[j]:
                cells[j] = True
                added += 1
            advance()
            assert all(cells[j:]), (original, movement, j, cells)
        assert all(cells)
        assert added == len(cells) - sum(original)
        return dict(insertions=added, moves=moves)

    lemma_cases = 0
    for n in range(1, 11):
        for original, movement in product(product((False, True), repeat=n), ("none", "one_forward_sweep", "settle_forward")):
            fill_path(original, movement)
            lemma_cases += 1
    assert lemma_cases == 6138
    cases = []
    for length in (38, 97, 98, 100, 137):
        # A/C关闭、取货和缓存空。先各装50，之后只有封闭两路中的移动。
        a_stock = c_stock = 50
        a_cache = c_cache = 0
        cells = [False] * length
        added = 0
        if length > 97:
            for road_length in (length // 2, length - length // 2):
                filled = fill_path([False] * road_length, "settle_forward")
                added += filled["insertions"]
            cells = [True] * length
        phi = a_stock + c_stock + sum(cells)
        expected = 100 if length <= 97 else 100 + length
        assert phi == expected and F(phi) >= F(length) + F(5, 2)
        # 统一开机后的第一完整步：原料转为一批缓存，尚无产物外送。
        a_stock -= 1
        c_stock -= 1
        a_cache = c_cache = 1
        assert a_stock + c_stock + a_cache + c_cache + sum(cells) == phi
        cases.append(dict(length=length, road_insertions=added, phi=phi))
    assert F(100) >= F(97) + F(5, 2)
    assert F(100) < F(98) + F(5, 2)
    return dict(cases=cases, count=len(cases), directed_path_filling_cases=lemma_cases, last_length_without_road_filling=97, scope="采用被引用专用进路的单向定义；封闭路尾保证已填后缀不再腾空。未模拟轮询重置、后续全厂产率或手放物品来源正确性。")


def main():
    start = time.monotonic()
    result = dict(order=order_checks(), startup_structure=startup_structure(), startup_inventory=startup_inventory())
    result["elapsed_seconds"] = time.monotonic() - start
    result["status"] = "PASS"
    (OUT / "structure_startup_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps(dict(status="PASS", elapsed_seconds=result["elapsed_seconds"], local_states=result["order"]["complete_local_states"], order_comparisons=result["order"]["order_comparisons"], machines=result["startup_structure"]["machines"], withdrawal_bound=result["startup_structure"]["per_species_withdrawal_bound"], startup_cases=result["startup_inventory"]["count"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
