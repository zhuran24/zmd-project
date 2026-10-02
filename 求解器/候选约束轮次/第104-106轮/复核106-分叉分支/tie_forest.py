# 「存在没有同刻接通的建造次序 ⇔ 通道图（不计方向，同一对单位之间的两条来回通道算两条边）没有圈」
# 算法一：在已建单位集合上做动态规划，每建一个单位，新接通的通道（与已建单位之间的边数，含重边）不超过 1。
# 算法二：并查集判圈（重边即圈）。
# 两者在随机小多重图上逐例比对；再用于 geom.py 里的种植机—采种机回路（16 个单位，从几何求通道）。
import random, json, itertools
import geom


def alg_dp(n, edges):
    adj = [[0] * n for _ in range(n)]
    for a, b in edges:
        adj[a][b] += 1
        adj[b][a] += 1
    full = (1 << n) - 1
    reach = bytearray(1 << n)
    reach[0] = 1
    for s in range(1 << n):
        if not reach[s]:
            continue
        for u in range(n):
            if s >> u & 1:
                continue
            k = 0
            for v in range(n):
                if s >> v & 1:
                    k += adj[u][v]
            if k <= 1:
                reach[s | 1 << u] = 1
    return bool(reach[full])


def alg_uf(n, edges):
    p = list(range(n))

    def f(x):
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x
    for a, b in edges:
        ra, rb = f(a), f(b)
        if ra == rb:
            return False  # 有圈 ⇒ 没有无同刻的次序
        p[ra] = rb
    return True


def alg_perm(n, edges):
    """第三种，暴力：枚举全部单位排列，看有没有一种每次建成至多接通一条。只用于 n≤7。"""
    for order in itertools.permutations(range(n)):
        pos = {u: i for i, u in enumerate(order)}
        t = [max(pos[a], pos[b]) for a, b in edges]
        if len(set(t)) == len(t):
            return True
    return False


def rand_graph(rng):
    n = rng.randint(2, 8)
    m = rng.randint(0, n + 2)
    edges = []
    for _ in range(m):
        a, b = rng.sample(range(n), 2)
        edges.append((a, b))
    return n, edges


if __name__ == '__main__':
    rng = random.Random(106)
    N = 4000
    agree = 0
    perm_checked = perm_agree = 0
    forest = cyc = 0
    bad = []
    for t in range(N):
        n, edges = rand_graph(rng)
        a, b = alg_dp(n, edges), alg_uf(n, edges)
        if a == b:
            agree += 1
        else:
            bad.append((n, edges, a, b))
        if b:
            forest += 1
        else:
            cyc += 1
        if n <= 6:
            perm_checked += 1
            if alg_perm(n, edges) == a:
                perm_agree += 1
    res = {'random_graphs': N, 'dp_vs_uf_agree': agree, 'forest': forest, 'with_cycle': cyc,
           'perm_checked': perm_checked, 'perm_agree': perm_agree, 'disagreements': bad[:5]}
    # 几何构型
    geo = {}
    for nm in ['G1_triangle', 'G2_ring', 'G5_bridges', 'G6_split3', 'G3_seedloop']:
        units = geom.EXAMPLES[nm]()
        names = [u.name for u in units]
        ix = {x: i for i, x in enumerate(names)}
        ch = geom.channels(units)
        edges = [(ix[c[0]], ix[c[1]]) for c in ch]
        geo[nm] = {'units': len(names), 'channels': len(edges),
                   'tie_free_order_exists_dp': alg_dp(len(names), edges),
                   'tie_free_order_exists_uf': alg_uf(len(names), edges)}
    # 去掉回路中的一格带，种植机—采种机之间就不成圈：对照
    units = [u for u in geom.G3_seedloop() if u.name != 'r6']
    names = [u.name for u in units]
    ix = {x: i for i, x in enumerate(names)}
    ch = geom.channels(units)
    edges = [(ix[c[0]], ix[c[1]]) for c in ch]
    geo['G3_seedloop_minus_r6'] = {'units': len(names), 'channels': len(edges),
                                   'tie_free_order_exists_dp': alg_dp(len(names), edges),
                                   'tie_free_order_exists_uf': alg_uf(len(names), edges)}
    res['geometric'] = geo
    # 复核100R 举的不可实现例：A-B-D-C-A 环上 AB<DC<CA<BD（对应 G2：b1=A b2=B b3=D b4=C）
    chk = json.load(open('orders_check.json'))
    res['AB<DC<CA<BD_realizable'] = 'b1b2<b3b4<b4b1<b2b3' in chk['G2_ring']['orders']
    print(json.dumps(res, ensure_ascii=False, indent=1))
    json.dump(res, open('tie_forest.json', 'w'), ensure_ascii=False, indent=1)
