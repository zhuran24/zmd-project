# 层数（规则第 28 行 + 临时规则第 2 条）在随机小元件图上的读法核对。
# 模型：元件 0..k-1；E→F 表示 E 往 F 所在单位送货；sink[E] 表示 E 还往机器等非元件送货。
# 「合资格的下游元件」：E 送往的元件里还往下送货的（出度>0 或 sink）。没有合资格下游的元件层数为 1（终点）。
# 一种「数法」= 给每个有合资格下游的元件选一个；层数沿所选链计。
# 读法 A（链读法）：链回到链上已走过的元件就是「绕回」；允许的数法 = 每个能走到终点的元件，链都走到终点。
# 核对：
#  1. 元件层数「在所有允许数法下都未定」⇔ 不能沿合资格边走到终点 ⇔ 从它出发的每条走法都会回到走过的元件。
#  2. 读法 B（「自己」只指被数的这个元件）：存在不能走到终点、但也不是每条走法都回到它自己的元件
#     （它在一个纯环的上游），这样的元件按 B 既不算「无法确定」又数不出数，所以只能按 A 读。
#  3. 每个元件各自可取的层数集合 = {1 + 从它到终点的简单路径的边数}。
#  4. 各元件可取层数的笛卡儿积比相容数法给出的层数向量多：「每一种数层选择」须按整套相容的数法取。
import random, json, itertools


def eligible(k, out, sink):
    sends = [bool(out[e]) or sink[e] for e in range(k)]
    return [[f for f in out[e] if sends[f]] for e in range(k)]


def can_reach_terminal(k, el):
    term = {e for e in range(k) if not el[e]}
    good = set(term)
    changed = True
    while changed:
        changed = False
        for e in range(k):
            if e not in good and any(f in good for f in el[e]):
                good.add(e)
                changed = True
    return good


def walks_all_revisit(e, el):
    """从 e 出发沿合资格边的每条走法是否都回到走过的元件（不能停在终点）。"""
    def dfs(v, seen):
        if not el[v]:
            return False  # 到终点，没有绕回
        for f in el[v]:
            if f in seen:
                continue  # 这条走法绕回
            if not dfs(f, seen | {f}):
                return False
        return True
    return dfs(e, {e})


def walks_all_return_to_self(e, el):
    """读法 B：从 e 出发的每条走法都回到 e 本身（不是回到别的元件）。"""
    def dfs(v, seen):
        if not el[v]:
            return False
        ok_any = False
        for f in el[v]:
            if f == e:
                continue  # 回到 e：这条算「绕回自己」
            if f in seen:
                return False  # 进了不含 e 的环：既不到终点也不回到 e
            if not dfs(f, seen | {f}):
                return False
        return True
    return dfs(e, {e})


def simple_path_layers(e, el):
    res = set()

    def dfs(v, seen, d):
        if not el[v]:
            res.add(d + 1)
            return
        for f in el[v]:
            if f not in seen:
                dfs(f, seen | {f}, d + 1)
    dfs(e, {e}, 0)
    return res


def consistent(k, el):
    good = can_reach_terminal(k, el)
    choosers = [e for e in range(k) if el[e]]
    vecs = set()
    per = [set() for _ in range(k)]
    for ch in itertools.product(*[el[e] for e in choosers]):
        c = dict(zip(choosers, ch))
        lay = {}
        ok = True
        for e in range(k):
            seen = []
            v = e
            while v in c and v not in seen:
                seen.append(v)
                v = c[v]
            if v in c:  # 绕回
                lay[e] = None
                if e in good:
                    ok = False
            else:
                lay[e] = len(seen) + 1
        if not ok:
            continue
        vecs.add(tuple(lay[e] for e in range(k)))
        for e in range(k):
            per[e].add(lay[e])
    return vecs, per, good


if __name__ == '__main__':
    rng = random.Random(1062)
    stats = {'graphs': 0, 'claim1_ok': 0, 'claim3_ok': 0, 'graphs_with_readingB_gap': 0,
             'graphs_product_gt_vectors': 0, 'graphs_with_undetermined': 0}
    example_gap = example_prod = None
    for t in range(3000):
        k = rng.randint(2, 7)
        out = [sorted(set(rng.sample(range(k), rng.randint(0, min(3, k - 1)))) - {e}) for e in range(k)]
        sink = [rng.random() < 0.4 for _ in range(k)]
        el = eligible(k, out, sink)
        if sum(len(x) for x in el) and max(len(x) for x in el) > 3:
            continue
        stats['graphs'] += 1
        vecs, per, good = consistent(k, el)
        c1 = True
        c3 = True
        gap = False
        for e in range(k):
            und_all = all(v[e] is None for v in vecs)
            if und_all != (e not in good) or und_all != walks_all_revisit(e, el):
                c1 = False
            if e in good and per[e] != simple_path_layers(e, el):
                c3 = False
            if e not in good and not walks_all_return_to_self(e, el):
                gap = True
        stats['claim1_ok'] += c1
        stats['claim3_ok'] += c3
        if gap:
            stats['graphs_with_readingB_gap'] += 1
            if example_gap is None or k < example_gap['k']:
                example_gap = {'k': k, 'eligible': el}
        if len(good) < k:
            stats['graphs_with_undetermined'] += 1
        prod = 1
        for e in range(k):
            prod *= len(per[e])
        if prod > len(vecs):
            stats['graphs_product_gt_vectors'] += 1
            if example_prod is None or k < example_prod['k']:
                example_prod = {'k': k, 'eligible': el, 'per_element': [sorted(x, key=lambda y: (y is None, y)) for x in per],
                                'vectors': sorted(vecs, key=str)}
    # 手写的两个小例
    hand = {}
    # E→{F,H}，F↔G 纯环，H 往机器送货
    el = [[1, 3], [2], [1], []]  # 0=E 1=F 2=G 3=H
    vecs, per, good = consistent(4, el)
    hand['E_upstream_of_pure_loop'] = {'eligible': el, 'vectors': sorted(vecs, key=str),
                                       'E_all_ways_return_to_E': walks_all_return_to_self(0, el),
                                       'F_all_ways_revisit': walks_all_revisit(1, el)}
    # A→{B,TA}，B→{A,TB}
    el = [[1, 2], [0, 3], [], []]
    vecs, per, good = consistent(4, el)
    hand['A_B_mutual_with_exits'] = {'eligible': el, 'vectors': sorted(vecs, key=str),
                                     'per_element': [sorted(x) for x in per]}
    res = {'stats': stats, 'example_readingB_gap': example_gap, 'example_product_gt_vectors': example_prod,
           'hand': hand}
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    json.dump(res, open('layers.json', 'w'), ensure_ascii=False, indent=1, default=str)
