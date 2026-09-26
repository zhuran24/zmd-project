#!/usr/bin/env python3
"""复核85：存货首件死锁与停机态的独立枚举（两套编码）。

编码甲：从前提快照的游戏规则文本解析配方，按「集合 + 规则判拒」枚举。
编码乙：配方手抄，按「有序两格 + 逐件试放」枚举，再规范化去重。
误料在枚举里合成一个符号 MIS（任何不在本机配方输入中的物品）。
输出 deadlock_enum.json。
"""
import itertools, json, re, sys, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = HERE.parent / "前提快照" / "《明日方舟：终末地》游戏规则.txt"
CAP = 50

# ---------------- 编码甲：解析规则文本 ----------------
def parse_recipes(text):
    sec = text.split("\n配方\n", 1)[1]
    machines = {}
    cur = None
    for line in sec.splitlines():
        s = line.strip()
        if not s:
            continue
        if "→" not in s:
            cur = s
            machines[cur] = []
            continue
        lhs, rhs = s.split("→")
        rhs, dur = rhs.rsplit("，", 1)
        def items(part):
            out = {}
            for tok in part.split("＋"):
                tok = tok.strip()
                m = re.match(r"(\d+)\s*(\S+)", tok)
                out[m.group(2)] = int(m.group(1))
            return out
        machines[cur].append((items(lhs), items(rhs), int(re.match(r"(\d+)", dur.strip()).group(1))))
    return machines

def grid_count_from_rules(text):
    # 小、中制造单位 1 个存货格；大制造单位 2 个
    size = {}
    block = text.split("制造单位：", 1)[1].split("运输单位", 1)[0]
    cur = None
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("小制造单位"):
            cur = 1
        elif s.startswith("中制造单位"):
            cur = 1
        elif s.startswith("大制造单位"):
            cur = 2
        elif s and cur is not None and "：" not in s and "，" not in s:
            size[s] = cur
    return size

text = RULES.read_text(encoding="utf-8")
REC_A = parse_recipes(text)
GRIDS_A = grid_count_from_rules(text)

MAINS = {"蓝铁粉末", "源石粉末", "荞花粉末"}

def kinds_of(recipes):
    ks = []
    for lhs, _, _ in recipes:
        for k in lhs:
            if k not in ks:
                ks.append(k)
    return ks

def states_A(kinds, ngrid):
    """集合编码：状态 = frozenset{(kind,count)}，同种一格，至多 ngrid 格。"""
    out = [frozenset()]
    for r in range(1, ngrid + 1):
        for combo in itertools.combinations(kinds, r):
            for counts in itertools.product(range(1, CAP + 1), repeat=r):
                out.append(frozenset(zip(combo, counts)))
    return out

def can_form_A(state, recipes):
    d = dict(state)
    for lhs, _, _ in recipes:
        if all(d.get(k, 0) >= q for k, q in lhs.items()):
            return True
    return False

def accept_A(state, kind, ngrid):
    d = dict(state)
    if kind in d:
        return d[kind] < CAP
    return len(d) < ngrid

def run_A(machine):
    recipes = REC_A[machine]
    ngrid = GRIDS_A[machine]
    ins = kinds_of(recipes)
    kinds = ins + ["MIS"]
    res = {"no_mis_first": 0, "mis_first_allowed": 0, "states": 0,
           "classify_fail": [], "extra_shape": {}}
    sts = states_A(kinds, ngrid)
    res["states"] = len(sts)
    subsets = [frozenset(c) for r in range(1, len(kinds) + 1) for c in itertools.combinations(kinds, r)]
    for st in sts:
        d = dict(st)
        if "MIS" in d:
            continue
        if machine == "研磨机" and len(MAINS & set(d)) >= 2:
            continue
        if can_form_A(st, recipes):
            continue
        refused = frozenset(k for k in kinds if not accept_A(st, k, ngrid))
        for S in subsets:
            if not S <= refused:
                continue
            res["mis_first_allowed"] += 1
            if "MIS" not in S:
                res["no_mis_first"] += 1
                # 83 版分类核对（首件与格都无误料）
                occ = len(d)
                ok = False
                if occ == 1:
                    (k, c), = d.items()
                    ok = (c == CAP and S == frozenset([k]))
                elif occ == 2:
                    full = {k for k, c in d.items() if c == CAP}
                    absent = set(ins) - set(d)
                    ok = S <= (full | absent)
                    if machine == "研磨机":
                        mains_in = [k for k in d if k in MAINS]
                        ok = ok and len(mains_in) == 1 and d[mains_in[0]] == 1
                        ok = ok and (absent <= MAINS)
                    elif machine == "封装机":
                        ok = ok and (d.get("钢制零件", 0) < 10 or d.get("致密源石粉末", 0) < 15) and not (S & absent)
                    elif machine == "灌装机":
                        ok = ok and (d.get("钢质瓶", 0) < 10 or d.get("细磨荞花粉末", 0) < 10) and not (S & absent)
                if not ok:
                    res["classify_fail"].append([sorted(d.items()), sorted(S)])
            else:
                occ = len(d)
                shape = "both_occupied" if occ == ngrid else "not_all_occupied"
                res["extra_shape"][shape] = res["extra_shape"].get(shape, 0) + 1
                if machine == "塑形机":
                    res.setdefault("small_examples", []).append([sorted(d.items()), sorted(S)])
    res["classify_fail"] = res["classify_fail"][:5]
    return res

# ---------------- 编码乙：手抄配方、有序两格、逐件试放 ----------------
REC_B = {
    "粉碎机": [{"源矿": 1}, {"蓝铁块": 1}, {"荞花": 1}, {"砂叶": 1}],
    "精炼炉": [{"蓝铁矿": 1}, {"致密蓝铁粉末": 1}, {"蓝铁粉末": 1}],
    "配件机": [{"钢块": 1}],
    "塑形机": [{"钢块": 2}],
    "种植机": [{"荞花种子": 1}, {"砂叶种子": 1}],
    "采种机": [{"荞花": 1}, {"砂叶": 1}],
    "研磨机": [{"蓝铁粉末": 2, "砂叶粉末": 1}, {"源石粉末": 2, "砂叶粉末": 1}, {"荞花粉末": 2, "砂叶粉末": 1}],
    "封装机": [{"钢制零件": 10, "致密源石粉末": 15}],
    "灌装机": [{"钢质瓶": 10, "细磨荞花粉末": 10}],
}
NG_B = {m: (2 if m in ("研磨机", "封装机", "灌装机") else 1) for m in REC_B}

def try_put(grids, kind):
    for g in grids:
        if g is not None and g[0] == kind:
            return g[1] < CAP
    return any(g is None for g in grids)

def formable(grids, recipes):
    tot = {}
    for g in grids:
        if g is not None:
            tot[g[0]] = tot.get(g[0], 0) + g[1]
    return any(all(tot.get(k, 0) >= q for k, q in r.items()) for r in recipes)

def run_B(machine):
    recipes = REC_B[machine]
    ng = NG_B[machine]
    ins = sorted({k for r in recipes for k in r})
    kinds = ins + ["MIS"]
    cells = [None] + [(k, c) for k in kinds for c in range(1, CAP + 1)]
    seen = set()
    cnt_no, cnt_all = 0, 0
    for grids in itertools.product(cells, repeat=ng):
        ks = [g[0] for g in grids if g is not None]
        if len(ks) != len(set(ks)):
            continue
        key = tuple(sorted((g for g in grids if g is not None)))
        if key in seen:
            continue
        seen.add(key)
        if "MIS" in ks:
            continue
        if machine == "研磨机" and sum(1 for k in ks if k in MAINS) >= 2:
            continue
        if formable(grids, recipes):
            continue
        refused = [k for k in kinds if not try_put(list(grids), k)]
        n = len(refused)
        # 首件种类集合 = refused 的非空子集
        cnt_all += 2 ** n - 1
        nm = len([k for k in refused if k != "MIS"])
        cnt_no += 2 ** nm - 1
    return {"states": len(seen), "no_mis_first": cnt_no, "mis_first_allowed": cnt_all}

# ---------------- 研磨机进入双主料的转移 ----------------
def grinder_transitions():
    recipes = REC_B["研磨机"]
    kinds = ["蓝铁粉末", "源石粉末", "荞花粉末", "砂叶粉末", "MIS"]
    cells = [None] + [(k, c) for k in kinds for c in range(1, CAP + 1)]
    def stopped(gr):
        ks = [g[0] for g in gr if g is not None]
        return "MIS" in ks or sum(1 for k in ks if k in MAINS) >= 2
    seen = set(); into_two = []; into_mis = 0; bad_entry = 0
    for grids in itertools.product(cells, repeat=2):
        ks = [g[0] for g in grids if g is not None]
        if len(ks) != len(set(ks)):
            continue
        key = tuple(sorted(g for g in grids if g is not None))
        if key in seen:
            continue
        seen.add(key)
        if stopped(grids):
            continue
        # 到件
        for k in kinds:
            if not try_put(list(grids), k):
                continue
            new = []
            placed = False
            for g in grids:
                if g is not None and g[0] == k:
                    new.append((k, g[1] + 1)); placed = True
                else:
                    new.append(g)
            if not placed:
                i = new.index(None); new[i] = (k, 1)
            if stopped(new):
                nks = [g[0] for g in new if g is not None]
                if "MIS" in nks:
                    into_mis += 1
                else:
                    # 应当恰是：一格是主料、另一格空，另一种主料进空格
                    ok = (k in MAINS and placed is False and
                          sum(1 for g in grids if g is None) == 1 and
                          [g[0] for g in grids if g is not None][0] in MAINS)
                    into_two.append(ok)
        # 开批不会进入停机态（只减件数）；逐个核
        for r in recipes:
            tot = {g[0]: g[1] for g in grids if g is not None}
            if all(tot.get(a, 0) >= q for a, q in r.items()):
                new = []
                for g in grids:
                    if g is None:
                        new.append(None); continue
                    c = g[1] - r.get(g[0], 0)
                    new.append((g[0], c) if c > 0 else None)
                if stopped(new):
                    bad_entry += 1
    return {"into_two_mains": len(into_two), "into_two_mains_all_one_step_form": all(into_two),
            "into_misfeed": into_mis, "into_stop_by_batch_start": bad_entry}

def main():
    out = {"rules_file": str(RULES), "recipes_parsed": {m: [[l, r, d] for l, r, d in v] for m, v in REC_A.items()},
           "grids_parsed": GRIDS_A, "A": {}, "B": {}}
    for m in REC_B:
        assert sorted(map(lambda x: sorted(x.items()), REC_B[m])) == sorted(map(lambda x: sorted(x[0].items()), REC_A[m])), m
        assert NG_B[m] == GRIDS_A[m], m
        out["A"][m] = run_A(m)
        out["B"][m] = run_B(m)
        print(m, out["A"][m]["states"], out["A"][m]["no_mis_first"], out["A"][m]["mis_first_allowed"],
              "| B", out["B"][m]["states"], out["B"][m]["no_mis_first"], out["B"][m]["mis_first_allowed"],
              "| classify_fail", len(out["A"][m]["classify_fail"]), out["A"][m]["extra_shape"], flush=True)
    out["grinder_transitions"] = grinder_transitions()
    print(out["grinder_transitions"])
    (HERE / "deadlock_enum.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
