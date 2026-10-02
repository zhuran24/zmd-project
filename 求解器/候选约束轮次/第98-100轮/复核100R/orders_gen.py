"""编码一：由单位建造次序生成接通先后。
每种单位排列 -> 每条通道的接通时刻 = 两端建成序号的较大者；
同刻的几条通道任意排开（全部线性扩展）。
输出：严格可实现的通道排列（无同刻）集合、含同刻排法后可实现的集合。
"""
import itertools, json, sys

def gen(units, chans):
    strict, full = set(), set()
    no_tie_orders = 0
    for perm in itertools.permutations(units):
        pos = {u: i for i, u in enumerate(perm)}
        t = {c: max(pos[c[0]], pos[c[1]]) for c in chans}
        groups = {}
        for c in chans:
            groups.setdefault(t[c], []).append(c)
        keys = sorted(groups)
        has_tie = any(len(groups[k]) > 1 for k in keys)
        if not has_tie:
            no_tie_orders += 1
            strict.add(tuple(c for k in keys for c in groups[k]))
        # 所有同刻排法
        parts = [list(itertools.permutations(groups[k])) for k in keys]
        for combo in itertools.product(*parts):
            full.add(tuple(c for blk in combo for c in blk))
    return strict, full, no_tie_orders

def name(c):
    return c[0] + c[1]

CASES = {
    # 三个单位两两相连（例：机器 M 出口接传送带 b 与汇流器 J，b 再送进 J）
    "triangle": (["M", "b", "J"], [("M", "b"), ("M", "J"), ("b", "J")]),
    # 复核97M 的四单位环 A-B-D-C-A
    "cycle4": (["A", "B", "C", "D"], [("A", "B"), ("B", "D"), ("D", "C"), ("C", "A")]),
    # 分流器 S 三支各进一个准入口，三个准入口都送进同一个单位 X
    "S3X": (["S", "a", "b", "c", "X"], [("S", "a"), ("S", "b"), ("S", "c"), ("a", "X"), ("b", "X"), ("c", "X")]),
}

if __name__ == "__main__":
    out = {}
    for k, (u, ch) in CASES.items():
        strict, full, nt = gen(u, ch)
        allp = set(itertools.permutations(ch))
        rec = {
            "units": len(u), "channels": len(ch),
            "unit_orders": len(list(itertools.permutations(u))),
            "unit_orders_without_tie": nt,
            "strict_realizable": len(strict),
            "realizable_with_ties": len(full),
            "all_permutations": len(allp),
            "unrealizable": sorted(["<".join(name(c) for c in p) for p in allp - full]),
        }
        if k == "S3X":
            # 分流器 S 的三条送货通道的次序 与 X 的三条收货通道的次序（按 a,b,c 记）
            def proj(p):
                so = tuple(c[1] for c in p if c[0] == "S")
                xo = tuple(c[0] for c in p if c[1] == "X")
                return so, xo
            sj = {proj(p) for p in strict}
            fj = {proj(p) for p in full}
            def cyc(o):  # 循环次序的方向：以 a 起头的旋转
                i = o.index("a"); r = o[i:] + o[:i]; return r
            rec["joint_S_X_strict"] = len(sj)
            rec["joint_S_X_with_ties"] = len(fj)
            rec["joint_S_X_cyc_orientation_differs_strict"] = sum(1 for s, x in sj if cyc(s) != cyc(x))
            rec["joint_S_X_cyc_orientation_differs_with_ties"] = sum(1 for s, x in fj if cyc(s) != cyc(x))
        out[k] = rec
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "orders_gen.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "unrealizable"} for k, v in out.items()}, ensure_ascii=False, indent=1))
    print("cycle4 unrealizable:", out["cycle4"]["unrealizable"])
