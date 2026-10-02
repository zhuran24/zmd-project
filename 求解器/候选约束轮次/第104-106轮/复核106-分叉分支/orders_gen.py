# 编码一：通道按手写的「单位对」列出，不读几何。
# 对每个单位建造次序 π，通道接通时刻 = 两端单位建成序号的较大者；同一时刻的一批通道把每种排法都展开。
# 输出：单位次序数、有同刻接通的单位次序数、（单位次序，同刻排法）组合数、去重后的通道全序数、
#       通道全排列中做不出来的个数、严格（无同刻）可实现的全序数。
import itertools, json, sys

ABSTRACT = {
    # 名字与 geom.py 的单位名一致，但边是手写的，不由几何求出
    'G1_triangle': (['M', 'X', 'Y'], [('M', 'X'), ('M', 'Y'), ('Y', 'X')]),
    'G2_ring': (['b1', 'b2', 'b3', 'b4'], [('b1', 'b2'), ('b2', 'b3'), ('b3', 'b4'), ('b4', 'b1')]),
    'G5_bridges': (['w', 'X', 'Y', 'e'], [('w', 'X'), ('X', 'Y'), ('Y', 'X'), ('Y', 'e')]),
    'G6_split3': (['in', 'S', 'bw', 'bw2', 'bw3', 'bn', 'be', 'be2', 'be3', 'X'],
                  [('in', 'S'), ('S', 'bw'), ('S', 'bn'), ('S', 'be'), ('bw', 'bw2'), ('bw2', 'bw3'),
                   ('bw3', 'X'), ('bn', 'X'), ('be', 'be2'), ('be2', 'be3'), ('be3', 'X')]),
}


def batches(order, edges):
    pos = {u: i for i, u in enumerate(order)}
    t = [max(pos[a], pos[b]) for (a, b) in edges]
    groups = {}
    for i, ti in enumerate(t):
        groups.setdefault(ti, []).append(i)
    return [groups[k] for k in sorted(groups)]


def expand(bs):
    for parts in itertools.product(*[itertools.permutations(b) for b in bs]):
        yield tuple(x for p in parts for x in p)


def run(name, project=None):
    units, edges = ABSTRACT[name]
    n_orders = n_tie = n_combo = 0
    sigmas = set()
    strict = set()
    proj = set()
    batch_shapes = {}
    for order in itertools.permutations(units):
        n_orders += 1
        bs = batches(order, edges)
        shape = tuple(len(b) for b in bs)
        batch_shapes[str(shape)] = batch_shapes.get(str(shape), 0) + 1
        if any(len(b) > 1 for b in bs):
            n_tie += 1
        else:
            strict.add(tuple(x for b in bs for x in b))
        if project is None:
            for s in expand(bs):
                n_combo += 1
                sigmas.add(s)
        else:
            # 只看 project 里几条通道的相对次序
            sub = [[x for x in b if x in project] for b in bs]
            sub = [b for b in sub if b]
            for s in expand(sub):
                proj.add(s)
    res = {'units': len(units), 'channels': len(edges), 'unit_orders': n_orders,
           'unit_orders_with_tie': n_tie, 'strict_realizable': len(strict),
           'batch_shapes': batch_shapes}
    if project is None:
        m = len(edges)
        allp = 1
        for k in range(2, m + 1):
            allp *= k
        res.update({'order_x_arrangement': n_combo, 'distinct_channel_orders': len(sigmas),
                    'channel_permutations': allp, 'unrealizable': allp - len(sigmas),
                    'orders': sorted(['<'.join('%s%s' % edges[i] for i in s) for s in sigmas])})
    else:
        res.update({'projected_on': ['%s%s' % edges[i] for i in project],
                    'projected_orders': sorted(['<'.join('%s%s' % edges[i] for i in s) for s in proj])})
    return res


if __name__ == '__main__':
    out = {}
    for nm in ['G1_triangle', 'G2_ring', 'G5_bridges']:
        out[nm] = run(nm)
        r = out[nm]
        print(nm, {k: v for k, v in r.items() if k != 'orders'})
    # G6：10 个单位，只看分流器 S 三条取货通道的相对次序
    out['G6_split3'] = run('G6_split3', project=[1, 2, 3])
    print('G6_split3', out['G6_split3'])
    json.dump(out, open('orders_gen.json', 'w'), ensure_ascii=False, indent=1)
