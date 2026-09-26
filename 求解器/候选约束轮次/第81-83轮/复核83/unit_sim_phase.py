#!/usr/bin/env python3
"""复核83：unit_sim.py 的非整数相位版。时间以 1/q tick 为格点，滞留与 1 tick 制造各为 q 个格点；
起态的在途货到达时刻与在制批次开工时刻随机落在 (-1,0] 的格点上（调试期操作不能精确到 tick）。
用于检验 81D 第2、3条在“事件时刻可带小数相位”读法下是否仍成立。
以下为原说明：
复核83：采种双出口专线单元（81D 第2、3条）的独立逐刻模拟，整数 tick 读法。
不导入推导席脚本。每刻：先把上一刻开工的批次置为完成；然后把全部判定按随机次序反复扫，
直到一整遍没有任何变化（“同一刻做到底”）。判定：机器整批入取货格、机器开工、各通道一次移动。
物品格一格一种；机器上限 m；运输格上限 1、滞留 >=1 tick。
K 的下游用 k 条“首格”，由对手每刻决定是否把首格的货收走（整刻开始时）。
用法：unit_sim.py <mode> <seed> <runs>
  mode=check：正确物品起态，查 81D 第2条下界与第3条循环态结论；
  mode=wrong：C 存货格放 1 件误料（种子），演示第2、3条缺“无误料”前提时的失败。"""
import sys, random, json

def run(seed, m, L, k, phi_extra, adv_ticks, wrong=None, fixed_order_seed=None, init=None, q=2):
    rnd = random.Random(seed)
    L1, L2, L3, L4 = L
    # 机器：store=(kind,count) or None; cache=None|('prog',kind)|('done',kind); take=(kind,count) or None
    M = {n: {'store': None, 'cache': None, 'take': None} for n in 'CABK'}
    recipe = {'C': ('plant', 'seed', 2), 'A': ('seed', 'plant', 1), 'B': ('seed', 'plant', 1), 'K': ('plant', 'powder', k)}
    paths = {'CA': [None] * L1, 'AC': [None] * L2, 'CB': [None] * L3, 'BK': [None] * L4}
    down = [None] * k  # K 下游首格
    # 起态：随机放正确物品
    def put(slot_owner, key, kind, cnt):
        if cnt > 0:
            M[slot_owner][key] = (kind, cnt)
    put('A', 'store', 'seed', rnd.randint(0, m)); put('B', 'store', 'seed', rnd.randint(0, m))
    put('C', 'store', 'plant', rnd.randint(0, m)); put('K', 'store', 'plant', rnd.randint(0, m))
    put('A', 'take', 'plant', rnd.randint(0, m)); put('B', 'take', 'plant', rnd.randint(0, m))
    put('C', 'take', 'seed', rnd.randint(0, m)); put('K', 'take', 'powder', rnd.randint(0, m))
    for pn, kind in (('CA', 'seed'), ('AC', 'plant'), ('CB', 'seed'), ('BK', 'plant')):
        for i in range(len(paths[pn])):
            if rnd.random() < 0.5:
                paths[pn][i] = (kind, -rnd.randint(0, q - 1))
    for n in 'CABK':
        if rnd.random() < 0.5:
            M[n]['cache'] = ('prog', -rnd.randint(0, q - 1))
    if wrong:
        M['C']['store'] = ('seed', 1)  # 误料：采种机存货格里是种子
    if init:
        init(M, paths, m)
    def cnt(slot):
        return 0 if slot is None else slot[1]
    def phi():
        s = sum(1 for c in paths['CA'] if c) + sum(1 for c in paths['AC'] if c)
        s += cnt(M['A']['store']) + (1 if M['A']['cache'] else 0) + cnt(M['A']['take'])
        s += (cnt(M['C']['store']) if M['C']['store'] and M['C']['store'][0] == 'plant' else 0)
        s += (1 if M['C']['cache'] else 0)
        return s + cnt(M['C']['take']) / 2
    S = L1 + L2 + 2
    # 补种到 phi >= S + 1/2 + phi_extra（往 A 存货格加种子，不超过 m）
    target = S + 0.5 + phi_extra
    while phi() < target and not wrong:
        if cnt(M['A']['store']) < m:
            M['A']['store'] = ('seed', cnt(M['A']['store']) + 1)
        elif cnt(M['C']['store']) < m:
            M['C']['store'] = ('plant', cnt(M['C']['store']) + 1)
        else:
            return None
    phi0 = phi()
    # 判定列表
    def judgments():
        J = []
        for n in 'CABK':
            J.append(('enter', n)); J.append(('start', n))
        J.append(('take', 'C', 'CA')); J.append(('take', 'C', 'CB')); J.append(('take', 'A', 'AC'))
        J.append(('take', 'B', 'BK'))
        for i in range(k):
            J.append(('takeK', i))
        for pn, dst in (('CA', 'A'), ('AC', 'C'), ('CB', 'B'), ('BK', 'K')):
            for i in range(len(paths[pn]) - 1):
                J.append(('shift', pn, i))
            J.append(('last', pn, dst))
        return J
    JL = judgments()
    def do(j, t):
        typ = j[0]
        if typ == 'enter':
            n = j[1]; c = M[n]['cache']
            if c and c[0] == 'done':
                _, outk, qq = recipe[n]
                tk = M[n]['take']
                if tk is None or (tk[0] == outk and tk[1] + qq <= m):
                    M[n]['take'] = (outk, cnt(tk) + qq); M[n]['cache'] = None
                    return True
            return False
        if typ == 'start':
            n = j[1]
            if M[n]['cache'] is None and M[n]['store'] and M[n]['store'][0] == recipe[n][0]:
                s = M[n]['store']
                M[n]['store'] = (s[0], s[1] - 1) if s[1] > 1 else None
                M[n]['cache'] = ('prog', t)
                return True
            return False
        if typ == 'take':
            n, pn = j[1], j[2]
            if paths[pn] and paths[pn][0] is None and M[n]['take']:
                tk = M[n]['take']
                paths[pn][0] = (tk[0], t)
                M[n]['take'] = (tk[0], tk[1] - 1) if tk[1] > 1 else None
                took.append((n, pn))
                return True
            return False
        if typ == 'takeK':
            i = j[1]
            if down[i] is None and M['K']['take']:
                tk = M['K']['take']
                down[i] = (tk[0], t)
                M['K']['take'] = (tk[0], tk[1] - 1) if tk[1] > 1 else None
                return True
            return False
        if typ == 'shift':
            pn, i = j[1], j[2]
            p = paths[pn]
            if p[i] and p[i][1] <= t - q and p[i + 1] is None:
                p[i + 1] = (p[i][0], t); p[i] = None
                return True
            return False
        if typ == 'last':
            pn, dst = j[1], j[2]
            p = paths[pn]
            if p and p[-1] and p[-1][1] <= t - q:
                s = M[dst]['store']
                if s is None or (s[0] == p[-1][0] and s[1] < m):
                    M[dst]['store'] = (p[-1][0], cnt(s) + 1); p[-1] = None
                    return True
            return False
    viol = []
    order_rnd = random.Random(fixed_order_seed if fixed_order_seed is not None else seed + 7)
    fixed = JL[:]
    order_rnd.shuffle(fixed)
    bound_block = L1 + L2 + 3 * m + 2 + (m - 1) / 2 - 0.5
    seen = {}
    hist = []
    t = 0
    pattern = [rnd.random() < 0.7 for _ in range(k * 3)]
    period_k = 3
    while True:
        t += 1
        adv = t <= adv_ticks * q
        # 完成上一刻开工的批次
        for n in 'CABK':
            c = M[n]['cache']
            if c and c[0] == 'prog' and c[1] <= t - q:
                M[n]['cache'] = ('done', None)
        # 下游收货（对手）
        for i in range(k):
            if down[i] and down[i][1] <= t - q:
                acc = (rnd.random() < 0.5) if adv else (t % q == 0 and pattern[(i * period_k) + ((t // q) % period_k)])
                if acc:
                    down[i] = None
        took = []
        order = JL[:] if not adv else JL[:]
        if adv:
            rnd.shuffle(order)
        else:
            order = fixed
        changed = True
        while changed:
            changed = False
            for j in order:
                if do(j, t):
                    changed = True
            if adv:
                rnd.shuffle(order)
        ph = phi()
        if not wrong and ph < min(phi0 - 0.5, bound_block) - 1e-9:
            viol.append(('phi', t, ph, phi0))
            break
        if wrong and ph < min(phi0 - 0.5, bound_block) - 1e-9:
            viol.append(('phi_wrong', t, ph, phi0))
            if init and t >= 300:
                return {'phi0': phi0, 'first_viol': viol[0], 'phi_at_300': ph, 'cycle_len': None, 'ticks': t, 'bound': min(phi0 - 0.5, bound_block)}
        if not adv:
            key = (tuple((n, M[n]['store'], M[n]['cache'] and (M[n]['cache'][0], min(q, t - (M[n]['cache'][1] or 0)) if M[n]['cache'][0] == 'prog' else 'd'), M[n]['take']) for n in 'CABK'),
                   tuple(tuple(None if c is None else (c[0], min(q, t - c[1])) for c in paths[pn]) for pn in ('CA', 'AC', 'CB', 'BK')),
                   tuple(None if c is None else min(q, t - c[1]) for c in down), t % (period_k * q))
            idle = tuple(n for n in 'CBK' if M[n]['cache'] is None)
            hist.append((key, idle))
            if key in seen:
                start = seen[key]
                cyc = hist[start:-1]
                idles = [x for _, i in cyc for x in i]
                return {'phi0': phi0, 'viol': viol, 'cycle_len': len(cyc), 'idle_in_cycle': sorted(set(idles)), 'ticks': t}
            seen[key] = len(hist) - 1
        if t > (adv_ticks + 20000) * q:
            return {'phi0': phi0, 'viol': viol, 'cycle_len': None, 'ticks': t}

def full_init(M, paths, m):
    # 调试期结束时：C 存货格 1 件误料（种子），C 取货格满种子，A 一侧整圈堵满
    M['C']['store'] = ('seed', 1)
    M['C']['take'] = ('seed', m)
    M['A']['store'] = ('seed', m); M['A']['cache'] = ('done', None); M['A']['take'] = ('plant', m)
    for i in range(len(paths['CA'])):
        paths['CA'][i] = ('seed', -1)
    for i in range(len(paths['AC'])):
        paths['AC'][i] = ('plant', -1)
    M['B']['store'] = None; M['B']['take'] = None; M['K']['store'] = None; M['K']['take'] = None
    for pn in ('CB', 'BK'):
        for i in range(len(paths[pn])):
            paths[pn][i] = None

if False:
    m = int(sys.argv[2])
    r = run(5, m, (2, 2, 2, 2), 3, 0, 400, wrong=True, init=full_init)
    print(json.dumps({'m': m, 'L': [2, 2, 2, 2], **r}, ensure_ascii=False))
    sys.exit()

if __name__ == '__main__':
    mode, seed0, runs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    rnd = random.Random(seed0)
    agg = {'runs': 0, 'phi_viol': 0, 'cycles': 0, 'idle_cycles': 0, 'examples': []}
    for r in range(runs):
        m = rnd.choice([3, 4, 5, 6, 8])
        L = tuple(rnd.randint(1, 4) for _ in range(4))
        k = rnd.choice([2, 3])
        res = run(seed0 * 100000 + r, m, L, k, rnd.choice([0, 0, 1, 3]), rnd.choice([30, 100, 300]), wrong=(mode == 'wrong'), q=int(sys.argv[4]) if len(sys.argv) > 4 else 2)
        if res is None:
            continue
        agg['runs'] += 1
        if res['viol']:
            agg['phi_viol'] += 1
            if len(agg['examples']) < 3:
                agg['examples'].append({'m': m, 'L': L, 'k': k, **{kk: res[kk] for kk in ('phi0',)}, 'viol': res['viol'][:2]})
        if res.get('cycle_len'):
            agg['cycles'] += 1
            if res['idle_in_cycle']:
                agg['idle_cycles'] += 1
                if len(agg['examples']) < 6:
                    agg['examples'].append({'m': m, 'L': L, 'k': k, 'phi0': res['phi0'], 'idle': res['idle_in_cycle']})
    print(json.dumps(agg, ensure_ascii=False))
