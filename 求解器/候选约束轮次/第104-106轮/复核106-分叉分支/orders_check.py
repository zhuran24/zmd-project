# 编码二：通道由 geom.py 从格子和端口求出；不枚举单位排列，而是对每个通道全序 σ 逐个检验能否由某个建造次序做出。
# 检验办法：在「已建单位集合 B、σ 已用掉的前 i 条」上做记忆化搜索；新建单位 u 时，
# 用几何重新求 B∪{u} 的通道，新出现的那几条必须恰好是 σ[i:i+k]（同刻的几条之间次序任意）。
import itertools, json
from functools import lru_cache
import geom


def chan_key(c):
    return (c[0], c[1], c[2], c[3])


def setup(name):
    units = geom.EXAMPLES[name]()
    byname = {u.name: u for u in units}
    allch = geom.channels(units)
    idx = {chan_key(c): i for i, c in enumerate(allch)}
    cache = {}

    def formed(bset):
        if bset not in cache:
            us = [byname[n] for n in bset]
            cache[bset] = frozenset(idx[chan_key(c)] for c in geom.channels(us))
        return cache[bset]
    names = tuple(u.name for u in units)
    return names, allch, formed


def realizable(sigma, names, formed, strict=False):
    m = len(sigma)

    @lru_cache(maxsize=None)
    def go(bset, i):
        if i == m:
            return True
        have = formed(bset)
        for n in names:
            if n in bset:
                continue
            nb = frozenset(bset | {n})
            new = formed(nb) - have
            k = len(new)
            if strict and k > 1:
                continue
            if k == 0:
                # 建一个暂时不接通任何通道的单位；只有它以后还能接通才有用，搜索照样展开
                if go(nb, i):
                    return True
                continue
            if set(sigma[i:i + k]) == new and go(nb, i + k):
                return True
        return False
    return go(frozenset(), 0)


def run_full(name):
    names, allch, formed = setup(name)
    m = len(allch)
    ok, strict_ok = [], []
    for sigma in itertools.permutations(range(m)):
        if realizable(sigma, names, formed):
            ok.append(sigma)
            if realizable(sigma, names, formed, strict=True):
                strict_ok.append(sigma)
    lab = ['%s%s' % (c[0], c[1]) for c in allch]
    return {'channels': lab, 'channel_permutations': len(list(itertools.permutations(range(m)))),
            'realizable': len(ok), 'unrealizable': len(list(itertools.permutations(range(m)))) - len(ok),
            'strict_realizable': len(strict_ok),
            'orders': sorted(['<'.join(lab[i] for i in s) for s in ok])}


def run_projection(name, proj_labels):
    """只看几条通道的相对次序 τ：搜索是否有某个建造次序（同刻任意排）使它们按 τ 接通。"""
    names, allch, formed = setup(name)
    lab = ['%s%s' % (c[0], c[1]) for c in allch]
    proj = [lab.index(p) for p in proj_labels]
    res = []
    for tau in itertools.permutations(proj):
        @lru_cache(maxsize=None)
        def go(bset, j):
            if j == len(tau):
                return True
            have = formed(bset)
            for n in names:
                if n in bset:
                    continue
                nb = frozenset(bset | {n})
                new = [x for x in (formed(nb) - have) if x in proj]
                k = len(new)
                if k == 0:
                    if go(nb, j):
                        return True
                    continue
                if set(tau[j:j + k]) == set(new) and go(nb, j + k):
                    return True
            return False
        if go(frozenset(), 0):
            res.append('<'.join(lab[i] for i in tau))
    return {'projected_on': proj_labels, 'projected_orders': sorted(res)}


if __name__ == '__main__':
    out = {}
    for nm in ['G1_triangle', 'G2_ring', 'G5_bridges']:
        out[nm] = run_full(nm)
        print(nm, {k: v for k, v in out[nm].items() if k != 'orders'})
    out['G6_split3'] = run_projection('G6_split3', ['Sbw', 'Sbn', 'Sbe'])
    print('G6_split3', out['G6_split3'])
    # 与编码一逐项比对（通道名都写成「起点终点」）
    gen = json.load(open('orders_gen.json'))
    cmp = {}
    for nm in ['G1_triangle', 'G2_ring', 'G5_bridges']:
        a = set(gen[nm]['orders'])
        b = set(out[nm]['orders'])
        cmp[nm] = {'same_set': a == b, 'enc1': len(a), 'enc2': len(b),
                   'unrealizable_enc1': gen[nm]['unrealizable'], 'unrealizable_enc2': out[nm]['unrealizable'],
                   'strict_enc1': gen[nm]['strict_realizable'], 'strict_enc2': out[nm]['strict_realizable']}
    cmp['G6_split3'] = {'same_set': set(gen['G6_split3']['projected_orders']) == set(out['G6_split3']['projected_orders']),
                        'n': len(out['G6_split3']['projected_orders'])}
    out['compare_with_enc1'] = cmp
    print(json.dumps(cmp, ensure_ascii=False))
    json.dump(out, open('orders_check.json', 'w'), ensure_ascii=False, indent=1)
