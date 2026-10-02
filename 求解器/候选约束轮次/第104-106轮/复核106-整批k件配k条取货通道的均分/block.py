#!/usr/bin/env python3
"""k 件块引理的两套独立编码。

情形：本机在第 p 步（本机判定时）手里至少 k 件，k 个首格中，空着的记偏移 0，
占着的物品由本机在互不相同的旧步送入，故腾空偏移是 1..7 中互不相同的数。
本机每步至多送 1 件；首格收件后要到 +8 步才再空。

编码 A：公式 max_i(r_i + k - i)（偏移升序，i 从 1 起）。
编码 B：逐步穷举本机在可收首格中的一切选择（含故意闲置以外的全部不闲置选择），
        记录最后一件的偏移、每路件数；另外穷举「允许闲置」的选择，确认不闲置是本条
        前件（本机有货且有空首格就送）才给出的结论。
检查：A == B 的最大值 == B 的最小值（与选择无关）；全部 <= 7；窗口内每路恰 1 件。
"""
import itertools, json, sys


def patterns(k):
    out = []
    for z in range(1, k + 1):           # p 是一次成功，故至少一个首格可收（偏移 0）
        for pos in itertools.combinations(range(1, 8), k - z):
            out.append(tuple([0] * z + list(pos)))
    return out


def formal(r):
    r = sorted(r)
    k = len(r)
    return max(r[i] + k - (i + 1) for i in range(k))


def brute(r, allow_idle=False):
    """返回 (最后完成偏移集合, 每种结局下每路件数是否全为1)。"""
    k = len(r)
    results = set()
    ok_once = True

    def rec(t, free_at, served, counts):
        nonlocal ok_once
        if served == k:
            results.add(t - 1)
            if any(c != 1 for c in counts):
                ok_once = False
            return
        if t > 40:
            results.add(999)
            return
        avail = [i for i in range(k) if free_at[i] <= t]
        if not avail:
            rec(t + 1, free_at, served, counts)
            return
        choices = list(avail) + ([None] if allow_idle else [])
        for c in choices:
            if c is None:
                rec(t + 1, free_at, served, counts)
                continue
            fa = list(free_at); fa[c] = t + 8
            cc = list(counts); cc[c] += 1
            rec(t + 1, tuple(fa), served + 1, tuple(cc))

    rec(0, tuple(r), 0, tuple([0] * k))
    return results, ok_once


def main(out):
    res = {}
    for k in range(2, 7):
        pats = patterns(k)
        mism = 0; mx = 0; once_bad = 0
        idle_worst = 0
        for r in pats:
            a = formal(r)
            b, once = brute(r)
            if b != {a}:
                mism += 1
            if not once:
                once_bad += 1
            mx = max(mx, a)
            if k <= 4:
                bi, _ = brute(r, allow_idle=True)
                idle_worst = max(idle_worst, max(bi))
        res[k] = dict(patterns=len(pats), mismatch=mism, max_last_offset=mx,
                      not_one_each=once_bad,
                      idle_allowed_worst=(idle_worst if k <= 4 else None))
        print(k, res[k], flush=True)
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'block.json')
