#!/usr/bin/env python3
"""乙席独立复算。只读指定材料，不导入、执行其他席位的程序。

所有运行是局部计数/接口核验，不是70x70全厂可行性证书。
Python标准库；一个进程；结果仅写入本文件所在目录。
"""
from collections import Counter
from fractions import Fraction as Q
from itertools import combinations, permutations, product
from math import ceil, gcd, lcm
from pathlib import Path
import hashlib
import json
import random
import re
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
SNAP = ROOT / "第107-109轮/前提快照"


def rational_linear_solve(rows, rhs, n):
    a = [[Q(x) for x in r] + [Q(b)] for r, b in zip(rows, rhs)]
    pivots = []
    row = 0
    for col in range(n):
        p = next((i for i in range(row, len(a)) if a[i][col]), None)
        if p is None:
            continue
        a[row], a[p] = a[p], a[row]
        v = a[row][col]
        a[row] = [x/v for x in a[row]]
        for i in range(len(a)):
            if i != row and a[i][col]:
                v = a[i][col]
                a[i] = [x-v*y for x, y in zip(a[i], a[row])]
        pivots.append(col)
        row += 1
    assert all(any(r[:-1]) or r[-1] == 0 for r in a)
    assert len(pivots) == n, (len(pivots), n)
    ans = [Q(0)]*n
    for i, col in enumerate(pivots):
        ans[col] = a[i][-1]
    return ans


def recipe_account():
    recipes = []
    for line in (SNAP / "《明日方舟：终末地》游戏规则.txt").read_text().splitlines():
        if "→" not in line:
            continue
        left, right = line.split("→")
        ins = {name: int(n) for n, name in re.findall(r"(\d+)\s+(\S+)", left)}
        m = re.fullmatch(r"\s*(\d+)\s+(\S+)，(\d+) tick", right)
        assert m, right
        recipes.append((ins, {m[2]: int(m[1])}, line.strip()))
    all_items = set().union(*(set(i) | set(o) for i, o, _ in recipes))
    minerals = {"源矿", "蓝铁矿"}
    ends = {"高容谷地电池": Q(3, 5), "精选荞愈胶囊": Q(11, 20)}
    rows, rhs = [], []
    for item in sorted(all_items - minerals):
        rows.append([o.get(item, 0)-i.get(item, 0) for i, o, _ in recipes])
        rhs.append(ends.get(item, 0))
    recycle = next(j for j, (i, o, _) in enumerate(recipes)
                   if i == {"蓝铁粉末": 1} and o == {"蓝铁块": 1})
    row = [int(j == recycle) for j in range(len(recipes))]
    solutions = [rational_linear_solve(rows+[row], rhs+[r], len(recipes))
                 for r in [0, 1]]
    data = []
    for vals in solutions:
        inflow = {m: sum(vals[j]*i.get(m, 0) for j, (i, o, _) in enumerate(recipes))
                  for m in minerals}
        plant = {name: sum(vals[j]*o.get(name, 0)
                          for j, (i, o, _) in enumerate(recipes))
                 for name in ["荞花", "砂叶"]}
        assert inflow == {"源矿": 18, "蓝铁矿": 34}
        assert plant == {"荞花": 11, "砂叶": 21}
        data.append({"ore": inflow, "plant_birth_rate": plant})
    # With recycle rate fixed the linear system is full rank. The two solutions
    # therefore determine its affine dependence on the free recycle variable.
    return {"recipe_count": len(recipes), "rank_with_recycle_fixed": len(recipes),
            "at_recycle_0_and_1": data,
            "rates_at_recycle_0": {r[2]: str(v) for r, v in zip(recipes, solutions[0])},
            "average_stock_lower_bounds": {"荞花种子及植株各": 22, "砂叶种子及植株各": 42},
            "ore_port_capacity": 2*(70//3)+6}


def interval_capacity():
    # Independent-set recurrence for event positions, not a rate formula.
    dp = [0]*130
    for length in range(1, 130):
        dp[length] = max(dp[length-1], 1+dp[max(0, length-8)])
        assert dp[length] == ceil(Q(length, 8))
    cyclic_cases = 0
    for period in [8, 16, 24, 32]:
        good = []
        for events in combinations(range(period), period//8):
            gaps = [b-a for a, b in zip(events, events[1:]+(events[0]+period,))]
            if min(gaps) >= 8:
                assert set(gaps) == {8}
                good.append(events)
        assert len(good) == 8
        cyclic_cases += len(good)
    windows = []
    for phase in range(8):
        for t in range(64):
            future = [s for s in range(t+1, t+17) if s % 8 == phase]
            past = [s for s in range(t-15, t+1) if s % 8 == phase]
            assert len(future) == len(past) == 2
            assert all(s-16 <= t for s in future)
            assert all(s+16 > t for s in past)
            windows.append((phase, t, len(future), len(past)))
    return {"window_8_positions": dp[8], "window_40_positions": dp[40],
            "window_41_positions": dp[41], "box_bounds_40_41": [3*dp[40], 3*dp[41]],
            "cyclic_saturation_cases": cyclic_cases,
            "lifetime_window_cases": len(windows), "per_machine_batches_each_window": 2,
            "32_machines_stock_each": 32*2,
            "alternating_channel_bounds": {str(pair): ceil(Q(sum(pair), 2))
                for pair in [(3, 2), (3, 1), (2, 1), (2, 2)]}}


def mixed_clearing_trace():
    # Local two-port timing witness. Correct next input is assumed available;
    # this checks completion/flush/send/start order, not an upstream layout.
    releases = [-100, -100]
    history = [-2, -1]
    stock_kind, stock = None, 0
    batch = ("X", 3, 0)
    next_kind = "Y"
    starts, sends, rows = [], [], []
    for t in range(64):
        def flush():
            nonlocal batch, stock_kind, stock
            if batch is not None and batch[2] <= t:
                kind, num, _ = batch
                if stock == 0 or (kind == stock_kind and stock+num <= 50):
                    stock_kind, stock = kind, stock+num
                    batch = None
        flush()
        port = next((p for p in sorted(range(2), key=lambda x: history[x])
                     if releases[p] <= t), None)
        sent = None
        if stock and port is not None:
            sent = [t, port, stock_kind]
            sends.append(sent)
            stock -= 1
            history[port], releases[port] = t, t+8
        flush()
        started = None
        if batch is None:
            started = next_kind
            starts.append(t)
            batch = (next_kind, 3 if next_kind == "X" else 1, t+8)
            next_kind = "Y" if next_kind == "X" else "X"
        if t in [0, 1, 7, 8, 9, 16, 17, 24, 25]:
            rows.append({"step": t, "send": sent, "output": [stock_kind, stock],
                         "new_batch": started, "cache": batch})
    assert starts == list(range(0, 64, 8))
    assert [(t, k) for t, p, k in sends[:4]] == [(0, "X"), (1, "X"), (8, "X"), (9, "Y")]
    return {"scope": "局部接口时序，输入及时可得；不认证全厂", "trace": rows,
            "batch_starts": starts, "sends": sends}


def saturated_box_head():
    cases = 0
    for c in range(1, 4):
        for phases in product(range(8), repeat=c):
            for mask in range((1 << c)-1):
                accepting = [p for p in range(c) if mask >> p & 1]
                refusing = [p for p in range(c) if not (mask >> p & 1)]
                for s in range(8):
                    take = [sum(t % 8 == phases[p] for t in range(s+1, s+9))
                            for p in range(c)]
                    assert take == [1]*c
                    x = len(accepting)+1
                    for t in range(s+1, s+9):
                        for p in accepting:
                            if t % 8 == phases[p]:
                                x -= 1
                        assert x >= 1
                    assert refusing
                    cases += 1
    return {"phase_acceptance_observation_cases": cases,
            "allow_coincident_phases": True,
            "result": "最小违规库存c_x+1仍无法在随后8步清空；全部拒绝x的口均丢掉应有成功"}


def box_cooling():
    counts, peak = 0, 0
    # Keep plus three reset patterns, independently of output-before-transfer.
    for phases in product(range(8), repeat=3):
        for resets in [(), (17,), tuple(range(7, 192, 7)), (1, 39, 40, 79, 120, 155)]:
            for order in ["no_physical", "send_first", "transfer_first"]:
                slots = [None]*6  # [species, count]
                ready = [0]*3
                due = 0
                ins = out = wireless = 0
                max_species_slots = 0
                for t in range(192):
                    if t in resets:
                        due = t
                    for p, phase in enumerate(phases):
                        if t % 8 != phase:
                            continue
                        kind = (t//8+p) % 6
                        i = next((i for i, s in enumerate(slots)
                                  if s is None or (s[0] == kind and s[1] < 50)), None)
                        if i is None:
                            assert order != "no_physical"
                            continue
                        if slots[i] is None:
                            slots[i] = [kind, 1]
                        else:
                            slots[i][1] += 1
                        ins += 1
                    size = lambda: sum(s[1] for s in slots if s)
                    peak = max(peak, size())
                    assert size() <= 15
                    def transmit():
                        nonlocal due, wireless, slots
                        if t >= due:
                            wireless += size()
                            slots = [None]*6
                            due = t+40
                    def ship():
                        nonlocal out
                        p = next((p for p in range(3) if ready[p] <= t), None)
                        i = next((i for i, s in enumerate(slots) if s), None)
                        if p is not None and i is not None:
                            slots[i][1] -= 1
                            if slots[i][1] == 0:
                                slots[i] = None
                            ready[p] = t+8
                            out += 1
                    if order == "send_first":
                        ship()
                    transmit()
                    if order == "transfer_first":
                        ship()
                    assert ins == out+wireless+size()
                    if order == "no_physical":
                        species = [s[0] for s in slots if s]
                        assert len(set(species)) == len(species)
                        max_species_slots = max(max_species_slots, len(species))
                counts += 1
    # Exact expiry table uses elapsed integer step time, no old simulator.
    tables = {}
    for reset in [False, True]:
        due, times = 0, []
        for t in range(101):
            if reset and t == 17:
                due = t
            if t >= due:
                times.append(t)
                due = t+40
        tables["clear" if reset else "keep"] = times
    assert tables == {"keep": [0, 40, 80], "clear": [0, 17, 57, 97]}
    return {"cases": counts, "steps_per_case": 192, "maximum_inventory": peak,
            "reset_and_physical_orders_checked": True, "expiry_example": tables,
            "expiry_convention": "第s步传输后，第s+40步本箱判定时冷却已到期"}


def transfer_order_witness():
    result = {}
    for order in permutations(["wireless", "physical"]):
        stock, wh_free, sent_w, sent_p = 1, 1, 0, 0
        for action in order:
            if action == "wireless":
                q = min(stock, wh_free)
                stock -= q
                wh_free -= q
                sent_w += q
            else:
                q = min(stock, 1)
                stock -= q
                sent_p += q
        result[" then ".join(order)] = {"wireless": sent_w, "physical": sent_p, "stock": stock}
    assert len({(x["wireless"], x["physical"]) for x in result.values()}) == 2
    return {"scope": "局部单次判定，箱头1件且两去处均可收", "branches": result}


def expiry_boundary_sensitivity():
    """Do not claim the late-check convention is licensed by the rules.

    This reproduces the open wording point in review 94A. It shows exactly
    which bound depends on the decision, instead of silently fixing it.
    """
    result = {}
    for interval in [40, 41]:
        stock, peak = 0, 0
        peak_at = None
        for t in range(83):
            # Three independent full-rate input channels, all at residue 1.
            if t % 8 == 1:
                stock += 3
            if stock > peak:
                peak, peak_at = stock, t
            if t % interval == 0:
                stock = 0
        result[str(interval)] = {"maximum_before_transfer": peak, "first_peak_step": peak_at}
    assert result["40"]["maximum_before_transfer"] == 15
    assert result["41"]["maximum_before_transfer"] == 18
    return {"readings": result,
            "scope": "只检验40/41步到期读法对数值的影响；41步读法是否被规则允许留待主会话裁定"}


def word_is_rotation(word, k):
    initial = word[:k]
    assert len(initial) == len(set(initial)), word
    if len(word) > k:
        assert all(x == initial[i % k] for i, x in enumerate(word)), word


def polling_groups():
    # Exhaustive 4-group schedules, delay 0/1, release on either side of source
    # judgment. Transport k<=3 is physically available; k=4..6 is a relaxation.
    cases, successes = 0, 0
    for k in range(1, 7):
        words = [g for g in product(range(k+1), repeat=4)
                 if all(g[i]+g[i+1] <= k for i in range(3))]
        for groups in words:
            for delays in product([0, 1], repeat=4):
                for after_bits in range(1 << k):
                    last = [-100]*k
                    pointer, queue = 0, 0
                    word = []
                    arrivals = {8*i+delays[i]: g for i, g in enumerate(groups)}
                    for t in range(40):
                        queue += arrivals.get(t, 0)
                        if not queue:
                            continue
                        p = next((p for d in range(k)
                                  if (p := (pointer+d) % k) >= 0
                                  and t >= last[p]+8+((after_bits >> p) & 1)), None)
                        if p is not None:
                            word.append(p)
                            pointer, last[p] = (p+1) % k, t
                            queue -= 1
                    assert queue == 0
                    assert word == [i % k for i in range(len(word))]
                    cases += 1
                    successes += len(word)
    return {"four_group_exhaustive_cases": cases, "success_events": successes,
            "k_range": [1, 6], "source_first_opportunity_delay": [0, 1],
            "head_release_before_or_after_source": True,
            "result": "成功词均保持固定轮转"}


def polling_subset_random():
    rng = random.Random(926101)
    cases, selected_events = 0, 0
    for kind in ["transport", "nontransport"]:
        for _ in range(1500):
            total = rng.randint(1, 3 if kind == "transport" else 6)
            k = rng.randint(1, total)
            selected = set(rng.sample(range(total), k))
            order = list(range(total))
            rng.shuffle(order)
            last = {p: -100+i for i, p in enumerate(order)}
            entered = [-100]*total
            pointer = 0
            initial = [p for p in (range(total) if kind == "transport" else order) if p in selected]
            word, queue, prev = [], 0, 0
            for t in range(256):
                if t % 8 == 0:
                    cur = rng.randint(0, k-prev)
                    queue += cur
                    prev = cur
                if not queue:
                    continue
                # An external higher-priority success only removes a group item.
                if rng.randrange(5) == 0:
                    queue -= 1
                    continue
                scan = ([(pointer+d) % total for d in range(total)] if kind == "transport"
                        else sorted(range(total), key=lambda p: last[p]))
                outsiders_ready = {p: bool(rng.randrange(2)) for p in range(total) if p not in selected}
                p = next((p for p in scan if (t-entered[p] >= 8 if p in selected else outsiders_ready[p])), None)
                if p is not None:
                    queue -= 1
                    entered[p], last[p] = t, t
                    pointer = (p+1) % total
                    if p in selected:
                        word.append(p)
            assert all(p == initial[i % k] for i, p in enumerate(word))
            cases += 1
            selected_events += len(word)
    return {"cases": cases, "selected_successes": selected_events,
            "includes_same_level_outside_and_higher_priority_successes": True,
            "scope": "局部接口放宽；外通道服务按对手选择，不声称全厂几何"}


def polling_resets():
    rng = random.Random(107109)
    cases, checks, largest_excess = 0, 0, -999
    for _ in range(1500):
        k = rng.randint(1, 6)
        order = list(range(k))
        rng.shuffle(order)
        last = [None]*k
        entered = [-100]*k
        segments = [[]]
        events, boundaries = [], []
        for t in range(256):
            if t and rng.randrange(20) == 0:
                rng.shuffle(order)
                if rng.randrange(2):
                    last = [None]*k
                segments.append([])
                boundaries.append(t)
            if rng.randrange(3) == 0:
                continue
            rank = {p: i for i, p in enumerate(order)}
            scan = sorted(range(k), key=lambda p: (0, rank[p]) if last[p] is None else (1, last[p]))
            p = next((p for p in scan if t-entered[p] >= 8), None)
            if p is not None:
                last[p], entered[p] = t, t
                segments[-1].append(p)
                events.append((t, p))
        for word in segments:
            word_is_rotation(word, k)
        for _ in range(30):
            a, b = sorted(rng.sample(range(257), 2))
            amounts = Counter(p for t, p in events if a <= t < b)
            spread = max(amounts[p] for p in range(k))-min(amounts[p] for p in range(k))
            m = sum(a < t < b for t in boundaries)
            assert spread <= m+1
            largest_excess = max(largest_excess, spread-m)
            assert all(amounts[p] <= ceil(Q(b-a, 8)) for p in range(k))
            checks += 1
        cases += 1
    witness = {}
    for clear in [False, True]:
        last = [None]*3
        counts = [0]*3
        for t in range(0, 160, 8):
            if clear:
                last = [None]*3
            p = min(range(3), key=lambda p: (0, p) if last[p] is None else (1, last[p]))
            last[p] = t
            counts[p] += 1
        witness["clear" if clear else "keep"] = counts
    assert witness == {"keep": [7, 7, 6], "clear": [20, 0, 0]}
    return {"cases": cases, "time_interval_checks": checks,
            "maximum_spread_minus_internal_offlines": largest_excess,
            "one_item_each_8_steps_160_steps": witness,
            "scope": "非运输单位局部接口；首格独占、恰8步前移持续成立"}


def mixed_formula():
    equations = 0
    parameter_pairs = 0
    for L in range(1, 61):
        for k in range(1, 7):
            period = lcm(L, k)
            tally = Counter((n % k, n % L) for n in range(period))
            h = gcd(L, k)
            for marker in range(L):
                for j in range(k):
                    actual = Q(tally[j, marker], period)
                    formula = Q(h*int(marker % h == j % h), L*k)
                    assert actual == formula
                    equations += 1
            parameter_pairs += 1
    # A concrete sequence split within its material list, without restarting it.
    material = ["A", "B", "A", "C", "B"]
    permutations_by_segment = [[0, 1, 2], [2, 0, 1], [1, 2, 0]]
    lengths, offset = [4, 7, 8], 0
    events, sum_by_segments = [], Counter()
    segment_details = []
    for length, perm in zip(lengths, permutations_by_segment):
        part = []
        for n in range(length):
            event = (material[(offset+n) % len(material)], perm[n % 3])
            events.append(event)
            part.append(event)
            sum_by_segments[event] += 1
        segment_details.append(part)
        offset += length
    assert Counter(events) == sum_by_segments
    wrong_reset = Counter((material[n % 5], perm[n % 3])
                          for length, perm in zip(lengths, permutations_by_segment)
                          for n in range(length))
    assert wrong_reset != Counter(events)
    return {"parameter_pairs": parameter_pairs, "indicator_equalities": equations,
            "L_range": [1, 60], "k_range": [1, 6],
            "tail_splice_example": segment_details,
            "correct_counts": {str(k): v for k, v in sorted(sum_by_segments.items())},
            "incorrect_material_restart_counts": {str(k): v for k, v in sorted(wrong_reset.items())}}


def core_geometry():
    bands = []
    for gap in range(0, 70, 3):
        blocks = [tuple(range(s, s+3)) for s in range(0, gap, 3)]
        blocks += [tuple(range(s, s+3)) for s in range(gap+1, 70, 3)]
        assert len(blocks) == 23
        assert set().union(*map(set, blocks)) == set(range(70))-{gap}
        mouths = [b[1] for b in blocks]
        # All intervals of length >=6 in the first inward column hit a source.
        assert all(any(a <= p < a+6 for p in mouths) for a in range(65))
        bands.append((gap, mouths))
    valid_pair_count = sum(a == 0 or b == 0 for a, _ in bands for b, _ in bands)
    assert valid_pair_count == 47
    min_m, max_m, spans = 99, 0, 0
    for gap, mouths in bands:
        for y in range(2, 62):
            m = sum(y <= p <= y+8 for p in mouths)
            min_m, max_m = min(min_m, m), max(max_m, m)
            assert m in [2, 3]
            for x in [2, 3]:
                width = x-1
                assert m+3 > 2*width
            spans += 1
    touching_cases, touched = 0, set()
    # Every core coordinate and every legal axis interval length >=6.
    for origin in range(62):
        blocked = {origin+p for p in [1, 4, 7]}
        for lo in range(70):
            for hi in range(lo+5, 70):
                if any(lo <= p <= hi for p in blocked):
                    continue
                overlap = set(range(max(lo, origin), min(hi, origin+8)+1))
                assert len(overlap) <= 1
                if overlap:
                    rel = next(iter(overlap))-origin
                    assert rel in [0, 8]
                    touched.add(rel)
                    touching_cases += 1
    min_x_for_west_rectangle = min(x for x in range(62) for a in range(2, x)
                                  if x-a >= 6)
    assert min_x_for_west_rectangle == 8
    ore_neighbours = {(p, -1) for p in [1, 4, 7]} | {(p, 9) for p in [1, 4, 7]}
    product_neighbours = {(-1, p) for p in range(1, 8)} | {(9, p) for p in range(1, 8)}
    assert len(ore_neighbours) == 6 and ore_neighbours.isdisjoint(product_neighbours)
    return {"single_edge_arrangements": len(bands), "two_edge_arrangements": valid_pair_count,
            "nine_row_span_checks": spans, "source_m_min_max": [min_m, max_m],
            "legal_interval_core_touch_cases": touching_cases, "only_touch_offsets": sorted(touched),
            "minimum_x_for_west_adjacent_width_6": min_x_for_west_rectangle,
            "forced_ore_neighbours": len(ore_neighbours),
            "with_direct_finished_product": len(ore_neighbours)+1,
            "corner_argument": "x0,y0均<=3各自迫使朝带边为存货边，但相邻边不可能都是同一对平行存货边"}


def manifest():
    inputs = [SNAP / n for n in ["《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt", "求解充分条件.txt"]]
    inputs += [ROOT / p for p in [
        "第107-109轮/临时规则.md", "第92-94轮/推导92A.md", "第92-94轮/推导92B.md",
        "第92-94轮/复核93A.md", "第92-94轮/复核94A.md", "第92-94轮/复核93B.md", "第92-94轮/复核94B.md",
        "第95-97轮/推导95T.md", "第95-97轮/复核96T.md", "第95-97轮/复核97T.md",
        "第101-103轮/推导101H.md", "第101-103轮/复核102H.md", "第101-103轮/复核103H.md",
        "三审-第92-106轮/三审报告.md"]]
    return {str(p.relative_to(ROOT)): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
             "lines": len(p.read_text().splitlines())} for p in inputs}


def main():
    start = time.monotonic()
    result = {"scope": "乙席三审准备材料；数学与局部接口独立复算；非主会话三审结论", "inputs": manifest()}
    for fn in [recipe_account, interval_capacity, mixed_clearing_trace, saturated_box_head,
               box_cooling, transfer_order_witness, expiry_boundary_sensitivity, polling_groups, polling_subset_random,
               polling_resets, mixed_formula, core_geometry]:
        then = time.monotonic()
        result[fn.__name__] = fn()
        print(fn.__name__, "PASS", round(time.monotonic()-then, 3), flush=True)
    result["elapsed_seconds"] = round(time.monotonic()-start, 3)
    result["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["all_checks_passed"] = True
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str)+"\n")
    print("ALL PASS", result["elapsed_seconds"], flush=True)


if __name__ == "__main__":
    main()
