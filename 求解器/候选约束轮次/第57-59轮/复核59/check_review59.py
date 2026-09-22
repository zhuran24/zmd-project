#!/usr/bin/env python3
"""第 59 轮异源复核（Claude 源）的独立复算脚本。

只读三份正式文件与第 57、58 轮报告的哈希，结果写到本脚本同目录的 results.json。
从项目根目录运行：python3 -B 求解器/候选约束轮次/第57-59轮/复核59/check_review59.py
"""
import hashlib
import itertools
import json
import math
import random
import re
import sys
from collections import defaultdict
from fractions import Fraction as Fr
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RESULTS = {}
FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
    return cond


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- 输入版本
FILES = {
    "rules": ROOT / "《明日方舟：终末地》游戏规则.txt",
    "task": ROOT / "求解任务.txt",
    "constraints": ROOT / "求解约束.txt",
    "candidates": ROOT / "候选约束.txt",
    "idea": ROOT / "思路.txt",
}
# 规则文件在本轮复核期间改过一处：第 21 行「开关」由「可同时打开或关闭多个开关」改为
# 「可一次把多个开关都打开或都关闭」。两个版本都接受，结果里记下读到的是哪一版。
EXPECTED = {
    "rules": {"4f04de50b2f743aec1da903f00f0f89f92f1aeba60eb4513320b71d0ee0a57fd": "第 57 轮推导所读版本",
              "52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3": "第 21 行开关改写后的版本"},
    "task": {"1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac": "第 57 轮推导所读版本"},
    "constraints": {"f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6": "第 57 轮推导所读版本"},
}
hashes = {k: sha(v) for k, v in FILES.items()}
for k, v in EXPECTED.items():
    check(hashes[k] in v, f"正式文件 {k} 的哈希不是已知版本")
RESULTS["input_sha256"] = hashes
RESULTS["input_version_note"] = {k: v.get(hashes[k], "未知版本") for k, v in EXPECTED.items()}
_rule_lines = FILES["rules"].read_text(encoding="utf-8").splitlines()
check(_rule_lines[20].startswith("开关："), "规则第 21 行不是开关条")
RESULTS["rules_line21"] = _rule_lines[20]


# ---------------------------------------------------------------- 配方
def parse_recipes():
    lines = FILES["rules"].read_text(encoding="utf-8").splitlines()
    start = lines.index("配方")
    machines = {}
    cur = None
    for ln in lines[start + 1:]:
        s = ln.strip()
        if not s:
            continue
        if "→" not in s:
            cur = s
            machines[cur] = []
            continue
        left, right = s.split("→")
        right, t = right.split("，")
        ticks = int(re.match(r"\s*(\d+)\s*tick", t).group(1))
        def parts(x):
            out = {}
            for p in x.split("＋"):
                m = re.match(r"\s*(\d+)\s*(\S+)\s*", p)
                out[m.group(2)] = int(m.group(1))
            return out
        machines[cur].append({"in": parts(left), "out": parts(right), "ticks": ticks})
    return machines


RECIPES = parse_recipes()
STOCK_CELLS = {  # 游戏规则 44—57 行
    "粉碎机": 1, "精炼炉": 1, "配件机": 1, "塑形机": 1,
    "采种机": 1, "种植机": 1,
    "研磨机": 2, "封装机": 2, "灌装机": 2,
}
check(set(RECIPES) == set(STOCK_CELLS), "配方表的机型与存货格表不一致")
check(sum(len(v) for v in RECIPES.values()) == 18, "配方条数不是 18")


# ================================================================ G1
def g1_mixed_round_robin():
    """混料轮询分料：逐件计数与公式 Fh·c(a,j mod h)/(Lk) 比较。"""
    n_cases = 0
    n_timed = 0
    rng = random.Random(59)
    lists = []
    for L in range(1, 9):
        lists += [tuple(p) for p in itertools.product("XY", repeat=L)]
    for L in range(1, 6):
        lists += [tuple(p) for p in itertools.product("XYZ", repeat=L)]
    for _ in range(300):
        L = rng.randint(9, 14)
        lists.append(tuple(rng.choice("XYZ") for _ in range(L)))

    def formula(lst, k):
        L = len(lst)
        h = math.gcd(L, k)
        res = {}
        for j in range(k):
            for a in set(lst):
                c = sum(1 for s in range(L) if s % h == j % h and lst[s] == a)
                res[(j, a)] = Fr(h * c, L * k)
        return res

    for lst in lists:
        L = len(lst)
        for k in range(1, 8):
            N = L * k // math.gcd(L, k)
            cnt = defaultdict(int)
            for n in range(N):
                cnt[(n % k, lst[n % L])] += 1
            f = formula(lst, k)
            for (j, a), v in f.items():
                n_cases += 1
                check(Fr(cnt[(j, a)], N) == v, f"混料公式不符 {lst} k={k} j={j} a={a}")
            # 非最短清单：写两遍、三遍
            for r in (2, 3):
                f2 = formula(lst * r, k)
                for key, v in f.items():
                    check(f2[key] == v, f"重复清单改变结果 {lst} r={r} k={k}")
    # 按 tick 成组出货：组大小周期序列，相邻两组之和 ≤k，按成功次序轮到通道
    for _ in range(400):
        k = rng.randint(2, 6)
        G = rng.randint(1, 5)
        groups = []
        for i in range(G):
            groups.append(rng.randint(0, k))
        ok = all(groups[i] + groups[(i + 1) % G] <= k for i in range(G)) and sum(groups) > 0
        if not ok:
            continue
        lst = lists[rng.randrange(len(lists))]
        L = len(lst)
        # 从 0 号件开始，模拟到 (tick mod G, n mod L, n mod k) 复原
        seen = {}
        n = 0
        t = 0
        per = defaultdict(int)
        hist = []
        while True:
            key = (t % G, n % L, n % k)
            if key in seen:
                t0, idx0 = seen[key]
                break
            seen[key] = (t, len(hist))
            for _g in range(groups[t % G]):
                hist.append((t, n % k, lst[n % L]))
                n += 1
            t += 1
        seg = hist[idx0:]
        T = t - t0
        total = len(seg)
        F = Fr(total, T)
        cnt = defaultdict(int)
        for (_, j, a) in seg:
            cnt[(j, a)] += 1
        # 清单首件所在通道：公式里的 j 以 n≡0 (mod L) 的那件为 0 号通道；这里 n=0 在通道 0
        f = formula(lst, k)
        for (j, a), v in f.items():
            n_timed += 1
            check(Fr(cnt[(j, a)], T) == F * v, f"成组出货流量不符 groups={groups} lst={lst} k={k}")
    return {"formula_cases": n_cases, "timed_cases": n_timed}


def sim_dense_node(pat, perm, ptr0, variant, horizon=3000):
    """分流器 D →{汇流器 M, 传送带 B}；上游 U→D；外来 E→M；M、B 各接一个按周期收货的下游。
    每个运输格容量 1、至少滞留 1 tick；每 tick 按固定次序 perm 做一遍判定。
    variant 0：D 在自己的判定里从持有权限的通道起逐条尝试直到成功，每次尝试后传给下一条；
    variant 1：D 每次判定只有持有权限的那条尝试一次，尝试后传给下一条。
    返回一个完整周期内各计数。"""
    injU, injE, accM, accB = pat
    cells = {"U": None, "D": None, "E": None, "M": None, "B": None}
    ptr = ptr0
    cnt = defaultdict(int)
    seen = {}
    snaps = []
    per = math.lcm(len(injU), len(injE), len(accM), len(accB))
    for t in range(horizon):
        for act in perm:
            if act == "injU":
                if injU[t % len(injU)] and cells["U"] is None:
                    cells["U"] = t
            elif act == "injE":
                if injE[t % len(injE)] and cells["E"] is None:
                    cells["E"] = t
            elif act == "UD":
                if cells["U"] is not None and cells["U"] < t and cells["D"] is None:
                    cells["U"] = None; cells["D"] = t; cnt["F"] += 1; cnt["dep_U"] += 1
            elif act == "EM":
                if cells["E"] is not None and cells["E"] < t and cells["M"] is None:
                    cells["E"] = None; cells["M"] = t; cnt["b"] += 1; cnt["dep_E"] += 1
            elif act == "Dout":
                if cells["D"] is not None and cells["D"] < t:
                    tries = 2 if variant == 0 else 1
                    for _ in range(tries):
                        tgt = "M" if ptr == 0 else "B"
                        ptr = 1 - ptr
                        if cells[tgt] is None:
                            cells["D"] = None; cells[tgt] = t
                            cnt["x" if tgt == "M" else "z"] += 1; cnt["dep_D"] += 1
                            break
            elif act == "Mout":
                if cells["M"] is not None and cells["M"] < t and accM[t % len(accM)]:
                    cells["M"] = None; cnt["y"] += 1; cnt["dep_M"] += 1
            elif act == "Bout":
                if cells["B"] is not None and cells["B"] < t and accB[t % len(accB)]:
                    cells["B"] = None; cnt["dep_B"] += 1
        # 周期末状态：每格是否有物品（本 tick 进的下一 tick 都已可走），权限位置，外部相位
        state = (t % per, ptr) + tuple(cells[c] is not None for c in "UDEMB")
        snaps.append(dict(cnt))
        if state in seen:
            t0 = seen[state]
            P = t - t0
            a, b_ = snaps[t0], snaps[t]
            return P, {key: b_.get(key, 0) - a.get(key, 0) for key in set(a) | set(b_)}
        seen[state] = t
    return None, None


def g1_shared_cells():
    rng = random.Random(5901)
    acts = ["injU", "injE", "UD", "EM", "Dout", "Mout", "Bout"]
    runs = 0
    ratio_sets = {"invariant": 0, "varies": 0, "invariant_with_external_and_both_branches_positive": 0}
    for _ in range(250):
        pat = tuple(tuple(rng.randint(0, 1) for _ in range(rng.randint(1, 6))) for _ in range(4))
        ratios = set()
        all_pos = True
        for _p in range(24):
            perm = acts[:]
            rng.shuffle(perm)
            for ptr0 in (0, 1):
                for variant in (0, 1):
                    P, c = sim_dense_node(pat, perm, ptr0, variant)
                    if P is None:
                        continue
                    runs += 1
                    F, x, z, b, y = (c.get(k, 0) for k in ("F", "x", "z", "b", "y"))
                    check(x + b == y, "汇流器进出不守恒")
                    check(x + z == F, "分流器进出不守恒")
                    check(y <= P, "汇流器出量超过周期长")
                    check(z >= max(0, F + b - P), f"z≥max(0,F+b−1) 不成立 {pat}")
                    for cell in "UDEMB":
                        check(c.get("dep_" + cell, 0) <= P, "运输格离格量超过周期长")
                    if variant == 0 and F:
                        ratios.add(Fr(x, F))
                    if variant == 0 and not (b > 0 and x > 0 and z > 0):
                        all_pos = False
        if len(ratios) > 1:
            ratio_sets["varies"] += 1
        elif len(ratios) == 1:
            ratio_sets["invariant"] += 1
            if all_pos:
                ratio_sets["invariant_with_external_and_both_branches_positive"] += 1
    # 第 57 轮第四节两例：D 在 5n 收件、外来件在 5n+3 或 5n 进入 M，下游随时收货；枚举全部 5040 种次序
    example = {}
    for phase in (3, 0):
        # U 在 5n−1 注入，保证 5n 能进 D（若次序允许）；这里直接让 D 每 5 tick 最多进一件，
        # 外来件每 5 tick 一件；统计全部次序下 20 tick 的 D→M:D→B
        injU = tuple(1 if i == 4 else 0 for i in range(5))
        injE = tuple(1 if i == (phase - 1) % 5 else 0 for i in range(5))
        res = set()
        for perm in itertools.permutations(acts):
            for ptr0 in (0, 1):
                P, c = sim_dense_node((injU, injE, (1,), (1,)), list(perm), ptr0, 0)
                if P is None:
                    continue
                res.add((Fr(c.get("x", 0), P), Fr(c.get("z", 0), P), Fr(c.get("b", 0), P)))
        example[f"外来件注入相位 {phase}"] = sorted([f"D→M {a}, D→B {b}, 外来 {e}" for a, b, e in res])
    return {"random_runs": runs, "pattern_sets": ratio_sets, "g57_section4_examples": example}


# ================================================================ G2
def g2_zero_inbound_and_transfer():
    # 成品含矿：沿配方递归（每种物品取第一条产它的配方）
    produce = {}
    for m, rs in RECIPES.items():
        for r in rs:
            for item, q in r["out"].items():
                produce.setdefault(item, (r, q))

    def ore(item, memo={}):
        if item in ("蓝铁矿", "源矿"):
            return {item: Fr(1)}
        if item in ("荞花", "砂叶", "荞花种子", "砂叶种子"):
            return {}
        if item in memo:
            return memo[item]
        r, q = produce[item]
        tot = defaultdict(Fr)
        for i, n in r["in"].items():
            for o, v in ore(i).items():
                tot[o] += n * v / q
        memo[item] = dict(tot)
        return memo[item]
    bat, cap = ore("高容谷地电池"), ore("精选荞愈胶囊")
    check(bat == {"蓝铁矿": 20, "源矿": 30}, f"电池含矿 {bat}")
    check(cap == {"蓝铁矿": 40}, f"胶囊含矿 {cap}")
    ore_out = Fr(6, 10) * sum(bat.values()) + Fr(55, 100) * sum(cap.values())
    check(ore_out == 52, "成品带走的矿不是 52")
    # 回路：z=a+f+w，2a=z+s ⇒ a=f+w+s；w=s=0 ⇒ a=f、z=2a（对若干整数取值复算）
    for f in range(0, 30):
        for w in range(0, 4):
            for s in range(0, 4):
                a = f + w + s
                z = a + f + w
                check(2 * a == z + s, "回路守恒消元不符")
                if w == 0 and s == 0:
                    check(a == f and z == 2 * a, "零入库时 a=f、z=2a 不成立")
    # 传输：发送量 min(n,f)=0 ⇔ n=0 或 f=0
    for n in range(0, 61):
        for f in range(0, 61):
            check((min(n, f) == 0) == (n == 0 or f == 0), "min 分支不符")
    # 满仓钢块：箱子每 tick 物理进一件出一件，传输每 5 tick 一次；仓库钢块 80000 与 79999 两种
    out = {}
    for W0 in (80000, 79999):
        wireless_total = 0
        phys_total = 0
        for order in itertools.permutations(["in", "out", "tx"]):
            for phase in range(5):
                W = W0
                box = 1
                wl = ph = 0
                for t in range(40):
                    for ev in order:
                        if ev == "in":
                            box += 1
                        elif ev == "out" and box > 0:
                            box -= 1; ph += 1
                        elif ev == "tx" and t % 5 == phase:
                            send = min(box, 80000 - W)
                            W += send; box -= send; wl += send
                wireless_total += wl
                phys_total += ph
        out[str(W0)] = {"wireless_sent_total": wireless_total, "physical_out_total": phys_total}
    check(out["80000"]["wireless_sent_total"] == 0, "满仓时仍有无线发送")
    check(out["79999"]["wireless_sent_total"] > 0, "留一空位时没有无线发送")
    return {"battery_ore": {k: str(v) for k, v in bat.items()}, "capsule_ore": {k: str(v) for k, v in cap.items()},
            "steel_example": out}


def window_run(recv_times, k, init_start, init_cnt):
    """按规则第 64 行：窗口从收下第一件起算 5 tick，走完后由下一件重新起算。"""
    start, cnt = init_start, init_cnt
    windows = []
    for r in recv_times:
        if start is None or r >= start + 5:
            if start is not None:
                windows.append((start, cnt))
            start, cnt = r, 1
        else:
            cnt += 1
        if cnt > k:
            return None
    windows.append((start, cnt))
    return windows


def g2_admission_windows():
    stats = {}
    n_legal = n_full = 0
    for k in range(1, 6):
        for P in range(1, 21):
            if P <= 12:
                sets = (s for r in range(0, P + 1) for s in itertools.combinations(range(P), r))
            else:
                # 大周期只看恰好取到 k/5 的集合与再多一件的集合；组合太多时随机抽 3000 个
                target = Fr(k * P, 5)
                if target.denominator != 1:
                    continue
                m = int(target)
                if math.comb(P, m) + math.comb(P, min(P, m + 1)) <= 30000:
                    sets = itertools.chain(itertools.combinations(range(P), m),
                                           itertools.combinations(range(P), min(P, m + 1)))
                else:
                    rr = random.Random(P * 10 + k)
                    sets = [tuple(sorted(rr.sample(range(P), m + rr.randint(0, 1)))) for _ in range(3000)]
            for R in sets:
                if not R:
                    continue
                times = [p * P + r for p in range(8) for r in R]
                for init in [(None, 0)] + [(s, c) for s in range(-4, 0) for c in range(1, k + 1)]:
                    w = window_run(times, k, *init)
                    if w is None:
                        continue
                    n_legal += 1
                    check(5 * len(R) <= k * P, f"合法序列超过 k/5：k={k} P={P} R={R}")
                    if 5 * len(R) == k * P:
                        n_full += 1
                        steady = [x for x in w if x[0] >= 3 * P][:-1]
                        for (s1, c1), (s2, _c2) in zip(steady, steady[1:]):
                            check(c1 == k and s2 - s1 == 5, f"取到 k/5 但窗口未满或未准时：k={k} P={P} R={R}")
    # 自起窗与滑动窗的区别
    ex = window_run([0, 4, 5, 6], 2, None, 0)
    sliding_max = max(sum(1 for r in [0, 4, 5, 6] if s <= r < s + 5) for s in range(0, 7))
    check(ex is not None and sliding_max == 3, "0、4、5、6 例子不符")
    return {"legal_sequences": n_legal, "full_rate_sequences": n_full, "k2_0456_selfstart_legal": ex is not None,
            "k2_0456_sliding_max": sliding_max}


def box_put(cells, kind):
    for i, c in enumerate(cells):
        if c is None:
            cells[i] = [kind, 1]
            return True
        if c[0] == kind and c[1] < 50:
            c[1] += 1
            return True
    return False


def box_take(cells, accept):
    for i, c in enumerate(cells):
        if c is not None:
            if c[0] in accept:
                c[1] -= 1
                if c[1] == 0:
                    cells[i] = None
                return c[0]
            return None
    return None


def g2_box_head():
    """满速箱头限存：1 号格 x 多于 c_x 件时，任意进箱与出箱的次序下拒绝 x 的通道这 1 tick 都取不到货。"""
    cases = 0
    tight = 0
    others = [
        [None] * 5,
        [["y", 3], None, None, None, None],
        [["x", 1], ["y", 50], None, None, None],
        [["y", 1], ["x", 50], ["y", 2], None, None],
        [["z", 4], ["y", 4], ["x", 4], ["y", 50], ["z", 50]],
    ]
    for c in range(1, 4):
        for cx in range(0, c):
            chans = [{"x", "y", "z"}] * cx + [{"y", "z"}] * (c - cx)
            for q in sorted({cx + 1, cx + 2, 50}):
                for rest in others:
                    for ins in itertools.product(["x", "y", None], repeat=3):
                        events = [("out", i) for i in range(c)] + [("in", i) for i in range(3)]
                        for order in itertools.permutations(events):
                            cells = [["x", q]] + [None if r is None else list(r) for r in rest]
                            ok = [False] * c
                            for ev, i in order:
                                if ev == "in":
                                    if ins[i] is not None:
                                        box_put(cells, ins[i])
                                else:
                                    got = box_take(cells, chans[i])
                                    ok[i] = got is not None
                            cases += 1
                            check(not any(ok[cx:]), f"拒绝 x 的通道取到了货 c={c} cx={cx} q={q}")
            # 取等：1 号格恰 c_x 件 x、2 号格有 y 时，存在全部通道都成功的次序
            if cx < c:
                found = False
                for order in itertools.permutations(range(c)):
                    cells = ([["x", cx]] if cx else []) + [["y", 5]]
                    cells += [None] * (6 - len(cells))
                    oks = [box_take(cells, chans[i]) is not None for i in order]
                    if all(oks):
                        found = True
                        break
                tight += found
                check(found, f"c_x 件时找不到全通道成功的次序 c={c} cx={cx}")
    return {"cases": cases, "tight_cases_found": tight}


def g2_box_blocked_tail():
    """箱内滞货封住后格：第 j 格放全部通道都拒绝的 A，随机进出，后格计数只增不减，j=1 时整箱不出货。"""
    rng = random.Random(5904)
    steps = 0
    cycled_front = 0
    for j in range(1, 7):
        for run in range(200):
            cells = [None] * 6
            for i in range(j - 1):
                cells[i] = [rng.choice("BC"), rng.randint(1, 50)] if rng.random() < 0.6 else None
            cells[j - 1] = ["A", rng.randint(1, 50)]
            for i in range(j, 6):
                cells[i] = [rng.choice("ABC"), rng.randint(1, 50)] if rng.random() < 0.5 else None
            accept = [{"B", "C"}, {"B"}, {"C"}][: rng.randint(1, 3)]
            tail0 = [None if c is None else tuple(c) for c in cells[j - 1:]]
            first_state = [None if c is None else tuple(c) for c in cells]
            returned = False
            outs = 0
            for s in range(400):
                if rng.random() < 0.5:
                    box_put(cells, rng.choice("ABC"))
                else:
                    if box_take(cells, rng.choice(accept)) is not None:
                        outs += 1
                steps += 1
                tail = [None if c is None else tuple(c) for c in cells[j - 1:]]
                for a, b in zip(tail0, tail):
                    if a is not None:
                        check(b is not None and b[0] == a[0] and b[1] >= a[1], "后格计数减少")
                check(cells[j - 1] is not None and cells[j - 1][0] == "A", "被拒绝格变空")
                tail0 = tail
                if [None if c is None else tuple(c) for c in cells] == first_state and s > 0:
                    returned = True
            if j == 1:
                check(outs == 0, "j=1 时仍有出货")
            cycled_front += returned
    # 第 2 格被 A 占住时第 1 格 B 可反复取空补入
    cells = [["B", 1], ["A", 1]] + [None] * 4
    loop_ok = True
    for _ in range(100):
        loop_ok &= box_take(cells, {"B"}) == "B"
        loop_ok &= box_put(cells, "B")
        loop_ok &= cells == [["B", 1], ["A", 1]] + [None] * 4
    check(loop_ok, "第 2 格堵住时第 1 格不能周转")
    return {"random_steps": steps, "runs_returning_to_start": cycled_front, "j2_front_cycles": loop_ok}


# ================================================================ G3
def g3_dual_feed():
    rng = random.Random(5905)
    events = 0
    for (a, b) in [(2, 1), (10, 15), (10, 10)]:
        for run in range(300):
            sA, sB = rng.randint(0, 50), rng.randint(0, 50)
            Z0 = b * sA - a * sB
            IA = IB = 0
            Ds = [0]
            for _ in range(500):
                r = rng.random()
                if r < 0.4 and sA < 50:
                    sA += 1; IA += 1
                elif r < 0.8 and sB < 50:
                    sB += 1; IB += 1
                elif sA >= a and sB >= b:
                    sA -= a; sB -= b
                D = b * IA - a * IB
                events += 1
                check(b * sA - a * sB == Z0 + D, "Z≠Z0+D")
                check(-50 * a <= Z0 + D <= 50 * b, "Z 越界")
                Ds.append(D)
            check(max(Ds) - min(Ds) <= 50 * (a + b), "前缀差超过 50(a+b)")
    # 两条 ABAB 混线加一条纯 A 线供研磨（2A+B），逐带偏差无界而整机周期复原
    sA, sB = 20, 20
    lane = [0, 0]
    for t in range(400):
        sA -= 2; sB -= 1  # 开工
        # 混线 1、2 本 tick 各送 A 或 B，纯 A 线送 A
        m1 = "A" if t % 2 == 0 else "B"
        m2 = "A" if t % 2 == 0 else "B"
        for i, m in enumerate((m1, m2)):
            if m == "A":
                sA += 1; lane[i] += 1
            else:
                sB += 1; lane[i] -= 2
        sA += 1
        check(0 <= sA <= 50 and 0 <= sB <= 50, "混线例库存越界")
    check((sA, sB) == (20, 20), "混线例整机库存未复原")
    return {"random_events": events, "per_lane_bias_after_400": lane}


def g3_mixed_output():
    """混做连续批次出货：每 tick 一批的机器、c 条取货通道、下游每 tick 都收（放宽），
    判断产物循环词能否持续，并与 k_X m ≤ c(m+1) 对照。"""
    words_checked = 0
    feasible_words = 0
    violations = []
    runs_ok = 0
    for kinds in [((3,), (1,)), ((3,), (2,)), ((2,), (1,)), ((3,), (1, 2))]:
        kx = kinds[0][0]
        others = kinds[1]
        alphabet = [("X", kx)] + [(f"Y{v}", v) for v in others]
        for L in range(2, 9 if len(alphabet) == 2 else 7):
            for w in itertools.product(range(len(alphabet)), repeat=L):
                if len(set(w)) < 2:
                    continue
                # 只保留循环最小代表
                if w != min(w[i:] + w[:i] for i in range(L)):
                    continue
                word = [alphabet[i] for i in w]
                for c in range(1, 4):
                    words_checked += 1
                    feas = mixed_feasible(word, c)
                    # 取出所有前后都接其他产物的最长同种段
                    bound_ok = True
                    for i in range(L):
                        if word[i][0] == word[i - 1][0]:
                            continue
                        m = 1
                        while word[(i + m) % L][0] == word[i][0]:
                            m += 1
                        k = word[i][1]
                        if k * m > c * (m + 1):
                            bound_ok = False
                    if feas:
                        feasible_words += 1
                        if not bound_ok:
                            violations.append(("".join(a for a, _ in word), c))
    check(not violations, f"可持续却违反 k_X m ≤ c(m+1)：{violations[:5]}")
    # 两口粉碎机：砂叶三连批不能持续，两连批存在能持续的词
    s = ("X", 3)
    y = ("Y1", 1)
    three = mixed_feasible([s, s, s, y, y, y], 2)
    two = mixed_feasible([s, s, y, y], 2)
    check(not three and two, "两口砂叶连续批次例子不符")
    return {"words_checked": words_checked, "feasible": feasible_words, "violations": len(violations),
            "two_port_sand_3run_feasible": three, "two_port_sand_2run_feasible": two}


def mixed_feasible(word, c):
    L = len(word)
    # 状态：(相位, 取货格种类, 件数)；相位 p 表示下一 tick 完成 word[p]
    states = set()
    edges = defaultdict(set)
    kinds = {a for a, _ in word} | {None}
    for p in range(L):
        for kd in kinds:
            for n in range(0, 51):
                if (kd is None) != (n == 0):
                    continue
                st = (p, kd, n)
                states.add(st)
                bk, bn = word[p]
                for d1 in range(0, min(n, c) + 1):
                    rem = n - d1
                    if rem > 0 and kd != bk:
                        continue
                    cnt = rem + bn
                    if cnt > 50:
                        continue
                    for d2 in range(0, min(cnt, c - d1) + 1):
                        n2 = cnt - d2
                        edges[st].add(((p + 1) % L, bk if n2 else None, n2))
    # 有向图中是否有回路：反复删掉出度为零的点
    outdeg = {st: len(edges[st]) for st in states}
    preds = defaultdict(list)
    for st in states:
        for e in edges[st]:
            preds[e].append(st)
    queue = [st for st in states if outdeg[st] == 0]
    removed = set()
    while queue:
        st = queue.pop()
        if st in removed:
            continue
        removed.add(st)
        for pr in preds[st]:
            outdeg[pr] -= 1
            if outdeg[pr] == 0:
                queue.append(pr)
    return len(removed) < len(states)


def random_plant_network(rng):
    """一种植物的随机收支网络：运输点、采种机、种植机、粉碎机、仓库。返回 LP 解。"""
    from scipy.optimize import linprog
    nT = rng.randint(2, 6)
    nH = rng.randint(1, 3)
    nP = rng.randint(1, 3)
    nG = rng.randint(1, 3)
    units = [("T", i) for i in range(nT)] + [("H", i) for i in range(nH)] + [("P", i) for i in range(nP)] + \
            [("G", i) for i in range(nG)] + [("W", 0)]
    edges = []
    for u in units:
        for v in units:
            if u == v:
                continue
            if u[0] in "GW":
                continue  # 粉碎机与仓库在这张图里只进不出
            if u[0] in "HP" and v[0] != "T":
                continue  # 非运输单位只与运输单位成通道
            if u[0] == "T" and v[0] == "T" or u[0] in "HP" or v[0] in "HPGW":
                if rng.random() < 0.45:
                    edges.append((u, v))
    # 变量：每条边的种子流、植株流；每台机器的批次率
    var = {}
    for e in edges:
        for ty in "sp":
            var[(e, ty)] = len(var)
    for u in units:
        if u[0] in "HPG":
            var[("r", u)] = len(var)
    nv = len(var)
    A_eq, b_eq, A_ub, b_ub = [], [], [], []

    def row():
        return [0.0] * nv
    for u in units:
        for ty in "sp":
            r = row()
            for e in edges:
                if e[1] == u:
                    r[var[(e, ty)]] += 1
                if e[0] == u:
                    r[var[(e, ty)]] -= 1
            if u[0] == "T":
                A_eq.append(r); b_eq.append(0)
            elif u[0] == "H":
                # 进植株 = r，出种子 = 2r，进种子 = 0，出植株 = 0
                if ty == "p":
                    r[var[("r", u)]] -= 1
                else:
                    r[var[("r", u)]] += 2
                A_eq.append(r); b_eq.append(0)
            elif u[0] == "P":
                if ty == "s":
                    r[var[("r", u)]] -= 1
                else:
                    r[var[("r", u)]] += 1
                A_eq.append(r); b_eq.append(0)
            elif u[0] == "G":
                if ty == "p":
                    r[var[("r", u)]] -= 1
                A_eq.append(r); b_eq.append(0)
        if u[0] == "T":
            r = row()
            for e in edges:
                if e[0] == u:
                    r[var[(e, "s")]] += 1; r[var[(e, "p")]] += 1
            A_ub.append(r); b_ub.append(1)
    for e in edges:
        if e[1][0] == "H":
            r = row(); r[var[(e, "s")]] = 1; A_eq.append(r); b_eq.append(0)
        if e[1][0] in "PG":
            r = row(); r[var[(e, "p" if e[1][0] == "P" else "s")]] = 1; A_eq.append(r); b_eq.append(0)
        if e[0][0] == "H":
            r = row(); r[var[(e, "p")]] = 1; A_eq.append(r); b_eq.append(0)
        if e[0][0] == "P":
            r = row(); r[var[(e, "s")]] = 1; A_eq.append(r); b_eq.append(0)
    for u in units:
        if u[0] in "HPG":
            r = row(); r[var[("r", u)]] = 1; A_ub.append(r); b_ub.append(1)
    # 要求总粉碎至少 0.2
    r = row()
    for u in units:
        if u[0] == "G":
            r[var[("r", u)]] = -1
    A_ub.append(r); b_ub.append(-0.2)
    cost = [rng.uniform(-1, 1) for _ in range(nv)]
    res = linprog(cost, A_ub=A_ub or None, b_ub=b_ub or None, A_eq=A_eq or None, b_eq=b_eq or None,
                  bounds=[(0, None)] * nv, method="highs")
    if res.status != 0:
        return None
    x = res.x
    flows = {k: x[i] for k, i in var.items()}
    return units, edges, flows


def g3_plant_graphs():
    rng = random.Random(5906)
    solved = 0
    subsets = 0
    grinders = 0
    tries = 0
    while solved < 400 and tries < 20000:
        tries += 1
        out = random_plant_network(rng)
        if out is None:
            continue
        units, edges, fl = out
        solved += 1
        eps = 1e-7
        rate = {u: fl.get(("r", u), 0.0) for u in units}
        # 分区收支：对全部仓库外单位子集复算两式
        inner = [u for u in units if u[0] != "W"]
        masks = range(1, 1 << len(inner)) if len(inner) <= 9 else [rng.randrange(1, 1 << len(inner)) for _ in range(400)]
        for mask in masks:
            S = {inner[i] for i in range(len(inner)) if mask >> i & 1}
            A = sum(rate[u] for u in S if u[0] == "H")
            Z = sum(rate[u] for u in S if u[0] == "P")
            F = sum(rate[u] for u in S if u[0] == "G")
            I = {ty: sum(fl[(e, ty)] for e in edges if e[1] in S and e[0] not in S) for ty in "sp"}
            E = {ty: sum(fl[(e, ty)] for e in edges if e[0] in S and e[1] not in S and e[1][0] != "W") for ty in "sp"}
            W = {ty: sum(fl[(e, ty)] for e in edges if e[0] in S and e[1][0] == "W") for ty in "sp"}
            subsets += 1
            check(abs(2 * A + I["s"] - (Z + E["s"] + W["s"])) < 1e-6, "分区种子收支不符")
            check(abs(Z + I["p"] - (A + F + E["p"] + W["p"])) < 1e-6, "分区植株收支不符")
        # 再生来路：按种类拆点的正流量图
        g = defaultdict(set)
        conv = {}
        for e in edges:
            for ty in "sp":
                if fl[(e, ty)] > eps:
                    g[(e[0], ty)].add((e[1], ty))
        for u in units:
            if u[0] == "H" and rate[u] > eps:
                g[(u, "p")].add((u, "s")); conv[((u, "p"), (u, "s"))] = "harvest"
            if u[0] == "P" and rate[u] > eps:
                g[(u, "s")].add((u, "p")); conv[((u, "s"), (u, "p"))] = "plant"
        nodes = set(g) | {v for vs in g.values() for v in vs}
        rev = defaultdict(set)
        for a, vs in g.items():
            for b in vs:
                rev[b].add(a)

        def reach(src, adj):
            seen = {src}
            st = [src]
            while st:
                a = st.pop()
                for b in adj[a]:
                    if b not in seen:
                        seen.add(b); st.append(b)
            return seen
        for u in units:
            if u[0] == "G" and rate[u] > eps:
                grinders += 1
                anc = reach((u, "p"), rev)
                ok = False
                for (a, b), kind in conv.items():
                    if kind != "harvest" or a not in anc:
                        continue
                    # 采种边在回路上：从 b 能回到 a
                    if a in reach(b, g):
                        # 取一条 b→a 的最短路，检查路上有种植转化
                        prev = {b: None}
                        q = [b]
                        while q and a not in prev:
                            nq = []
                            for x in q:
                                for y in g[x]:
                                    if y not in prev:
                                        prev[y] = x; nq.append(y)
                            q = nq
                        path = []
                        y = a
                        while prev[y] is not None:
                            path.append((prev[y], y)); y = prev[y]
                        has_plant = any(conv.get(ed) == "plant" for ed in path)
                        check(has_plant, "含采种的回路上没有种植转化")
                        ok = True
                        break
                check(ok, "粉碎机上游没有含采种、种植转化的再生回路")
    return {"lp_instances": solved, "subsets_checked": subsets, "positive_grinders_checked": grinders}


def g3_occupancy():
    rng = random.Random(5907)
    cells_checked = 0
    for _ in range(3000):
        P = rng.randint(2, 30)
        # 一个格在周期内的占用段：[in, out)，out−in ≥1，段间不重叠（首尾接起来）
        t = rng.randint(0, P - 1)
        start = t
        segs = []
        while True:
            d = rng.randint(1, 4)
            if t + d > start + P:
                break
            segs.append((t, t + d, rng.choice("sp")))
            t += d + rng.choice([0, 0, 1, 2])
            if t >= start + P:
                break
        receipts = {ty: sum(1 for s in segs if s[2] == ty) for ty in "sp"}
        occ = {ty: sum(s[1] - s[0] for s in segs if s[2] == ty) for ty in "sp"}
        cells_checked += 1
        for ty in "sp":
            check(occ[ty] >= receipts[ty], "占用积分小于收件数")
    return {"cells_checked": cells_checked}


# ================================================================ G4
def g4_rates_and_streams():
    # 由目标倒推植株需求（精确分数）
    bat, cap = Fr(3, 5), Fr(11, 20)
    fine_qiao = 10 * cap          # 细磨荞花粉末
    qiao_powder = 2 * fine_qiao   # 荞花粉末
    sand_powder = (17 + 9) + fine_qiao  # 致密蓝铁 17、致密源石 9、细磨荞花 5.5 各需 1 砂叶粉末
    check(10 * bat + 2 * 10 * cap == 17, "钢块需求不是 17")
    grind_q = qiao_powder / 2
    grind_s = sand_powder / 3
    check(grind_q == Fr(11, 2) and grind_s == Fr(21, 2), "粉碎植株需求不符")
    # 零入库时 z=2a、a=f；32 台种植满载 ⇒ 等号
    z = 2 * grind_q + 2 * grind_s
    check(z == 32, "32 台种植不恰满")
    # 没有分叉时，每股 1 件/tick 整股进入一台消费者；采种、粉碎各接整数股
    for n, need in ((11, Fr(11, 2)), (21, Fr(21, 2))):
        ok = any(Fr(h) == need for h in range(n + 1))
        check(not ok, "整股划分竟能得到半数")
    # 单出口函数图：随机图上每个中转点只有一条出边，整股流量只能整到消费者
    rng = random.Random(5908)
    graphs = 0
    for _ in range(3000):
        nS, nT, nC = rng.randint(1, 5), rng.randint(0, 6), rng.randint(1, 6)
        succ = {}
        for i in range(nS):
            succ[("S", i)] = rng.choice([("T", j) for j in range(nT)] + [("C", j) for j in range(nC)])
        for i in range(nT):
            succ[("T", i)] = rng.choice([("T", j) for j in range(nT) if j != i] + [("C", j) for j in range(nC)])
        inflow = defaultdict(int)
        feasible = True
        for i in range(nS):
            v = succ[("S", i)]
            steps = 0
            while v[0] == "T":
                inflow[v] += 1
                v = succ[v]
                steps += 1
                if steps > nT + 1:
                    feasible = False  # 进了纯运输闭圈，库存无法复原
                    break
            if feasible:
                inflow[v] += 1
        if feasible and all(q <= 1 for q in inflow.values()):
            graphs += 1
            for j in range(nC):
                check(inflow[("C", j)] in (0, 1), "消费者收到非整股")
    return {"grind_qiao": str(grind_q), "grind_sand": str(grind_s), "planting_total": str(z),
            "feasible_single_exit_graphs": graphs}


def g4_misfeed():
    inputs = {m: set().union(*[set(r["in"]) for r in rs]) for m, rs in RECIPES.items()}
    all_items = set()
    for rs in RECIPES.values():
        for r in rs:
            all_items |= set(r["in"]) | set(r["out"])
    all_items |= {"其他物品"}
    combos = 0
    starts = 0
    for m, rs in RECIPES.items():
        n = STOCK_CELLS[m]
        bad = sorted(all_items - inputs[m])
        good = sorted(inputs[m])
        for b in bad:
            rest_opts = [()] if n == 1 else [(None,)] + [(g,) for g in good] + [(x,) for x in bad]
            for rest in rest_opts:
                combos += 1
                cells = {b: 50}
                for x in rest:
                    if x is not None and x not in cells:
                        cells[x] = 50
                for r in rs:
                    if all(cells.get(i, 0) >= q for i, q in r["in"].items()):
                        starts += 1
    check(starts == 0, "误料占格后仍能开批")
    # 机型下限（精确分数）
    need = {"粉碎机": Fr(68), "精炼炉": Fr(51), "研磨机": Fr(63, 2), "塑形机": Fr(11, 2), "配件机": Fr(6),
            "种植机": Fr(32), "采种机": Fr(16), "封装机": Fr(3, 5), "灌装机": Fr(11, 20)}
    ticks = {m: RECIPES[m][0]["ticks"] for m in RECIPES}
    lower = {m: math.ceil(need[m] * ticks[m]) for m in need}
    check(lower == {"粉碎机": 68, "精炼炉": 51, "研磨机": 32, "塑形机": 6, "配件机": 6, "种植机": 32,
                    "采种机": 16, "封装机": 3, "灌装机": 3}, f"机型下限不符 {lower}")
    # 复算批次需求本身
    fine_q = Fr(11, 20) * 10
    steel = Fr(3, 5) * 10 + 2 * Fr(11, 20) * 10
    dense_fe = steel
    fe_powder = 2 * dense_fe
    src_powder = 2 * Fr(3, 5) * 15
    crush = src_powder + fe_powder + (2 * fine_q) / 2 + (dense_fe + Fr(3, 5) * 15 + fine_q) / 3
    check(crush == 68, f"粉碎批次 {crush}")
    check(Fr(34) + steel == 51, "精炼批次")
    check(dense_fe + Fr(3, 5) * 15 + fine_q == Fr(63, 2), "研磨批次")
    return {"misfeed_combos": combos, "starts_found": starts, "lower_bounds": lower}


def main():
    RESULTS["G1_mixed_round_robin"] = g1_mixed_round_robin()
    RESULTS["G1_shared_cells_dense_node"] = g1_shared_cells()
    RESULTS["G2_zero_inbound_transfer"] = g2_zero_inbound_and_transfer()
    RESULTS["G2_admission_windows"] = g2_admission_windows()
    RESULTS["G2_box_head"] = g2_box_head()
    RESULTS["G2_box_blocked_tail"] = g2_box_blocked_tail()
    RESULTS["G3_dual_feed"] = g3_dual_feed()
    RESULTS["G3_mixed_output"] = g3_mixed_output()
    RESULTS["G3_plant_graphs"] = g3_plant_graphs()
    RESULTS["G3_occupancy"] = g3_occupancy()
    RESULTS["G4_streams"] = g4_rates_and_streams()
    RESULTS["G4_misfeed"] = g4_misfeed()
    RESULTS["fails"] = FAILS[:50]
    RESULTS["status"] = "PASS" if not FAILS else "FAIL"
    (HERE / "results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"status": RESULTS["status"], "n_fails": len(FAILS), "first": FAILS[:5]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
