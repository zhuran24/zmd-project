"""编码二：逐个检验通道排列能否实现（子集动态规划，不生成单位排列）。
状态 = (已建单位集合, 排列里已接通的条数)。新建一个单位 u 时，它与已建单位之间的通道同刻接通，
这些通道必须恰好是排列里接下来的那几条（同刻的几条之间次序任意）。
另求严格可实现：要求每次新接通的通道至多 1 条。
"""
import itertools, json, sys
from functools import lru_cache

def check(units, chans, perm, strict):
    idx = {u: i for i, u in enumerate(units)}
    n = len(units)
    adj = {}
    for c in chans:
        adj.setdefault(c[0], []).append(c); adj.setdefault(c[1], []).append(c)
    full = (1 << n) - 1
    @lru_cache(None)
    def ok(mask, k):
        if mask == full:
            return k == len(perm)
        for u in units:
            b = 1 << idx[u]
            if mask & b:
                continue
            new = [c for c in adj.get(u, []) if (mask >> idx[c[0] if c[1] == u else c[1]]) & 1]
            if strict and len(new) > 1:
                continue
            m = len(new)
            if set(perm[k:k + m]) == set(new) and ok(mask | b, k + m):
                return True
        return False
    return ok(0, 0)

CASES = {
    "triangle": (["M", "b", "J"], [("M", "b"), ("M", "J"), ("b", "J")]),
    "cycle4": (["A", "B", "C", "D"], [("A", "B"), ("B", "D"), ("D", "C"), ("C", "A")]),
    "S3X": (["S", "a", "b", "c", "X"], [("S", "a"), ("S", "b"), ("S", "c"), ("a", "X"), ("b", "X"), ("c", "X")]),
}

if __name__ == "__main__":
    out = {}
    for k, (u, ch) in CASES.items():
        perms = list(itertools.permutations(ch))
        fullr = [p for p in perms if check(u, ch, p, False)]
        strictr = [p for p in perms if check(u, ch, p, True)]
        rec = {"all_permutations": len(perms), "realizable_with_ties": len(fullr), "strict_realizable": len(strictr),
               "unrealizable": sorted(["<".join(c[0] + c[1] for c in p) for p in perms if p not in set(fullr)])}
        if k == "S3X":
            def proj(p):
                return tuple(c[1] for c in p if c[0] == "S"), tuple(c[0] for c in p if c[1] == "X")
            def cyc(o):
                i = o.index("a"); return o[i:] + o[:i]
            fj = {proj(p) for p in fullr}; sj = {proj(p) for p in strictr}
            rec["joint_S_X_strict"] = len(sj); rec["joint_S_X_with_ties"] = len(fj)
            rec["joint_S_X_cyc_orientation_differs_strict"] = sum(1 for s, x in sj if cyc(s) != cyc(x))
            rec["joint_S_X_cyc_orientation_differs_with_ties"] = sum(1 for s, x in fj if cyc(s) != cyc(x))
        out[k] = rec
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "orders_dp.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "unrealizable"} for k, v in out.items()}, ensure_ascii=False, indent=1))
    print("cycle4 unrealizable:", out["cycle4"]["unrealizable"])
