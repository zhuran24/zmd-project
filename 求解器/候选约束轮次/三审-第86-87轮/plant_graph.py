#!/usr/bin/env python3
"""三审第 86—87 轮：采种单元回路存量下界的小容量全状态图核对（本目录自写，不导入推导席、复核席的脚本）。

模型（只保留下界用到的部分，其余交给对手）：
  C 的取货物品格 g 粒种子，两条取货通道：CA（L1 格）进 A 的存货物品格，CB 只建它的首运输物品格 cb；
  cb 里的货满 1 tick 以后什么时候被下游拿走由对手定（也可以一直不拿），这包含 B、K、仓库停收与恢复的一切历史。
  A 存货 a_in、缓存 a_c、取货 a_out；AC（L2 格）进 C 的存货 c_in、缓存 c_c。
  物品格上限 cap（真实为 50），配方 1 tick。
时间取 1/q tick 的格点，每个单位的事件可以落在不同的格点余数上（即不同相位）；
一个时刻里全部能成功的移动、开批、整批进格按对手选的任意先后做到没有可动为止（比真实轮询、判定次序更宽）。
运输物品格的货记已停留的子步数（封顶 q，q 即已满 1 tick）；缓存格记还差的子步数（0 即已做好）。

核三件事：
  (1) 每个闭合状态 s（都可以当调试期结束的起态）此后能到的最小 Φ ≥ min(Φ(s)−1/2, L1+L2+3cap+2+(cap−1)/2−1/2)；
  (2) 起态后至少 1 tick 的每个闭合状态里，CA 首格是已满 1 tick 的旧货时 Φ ≥ L1+L2+3cap+2+(cap−1)/2（「卡住」界）；
  (3) Φ 在一个时刻里的每一步只因 A 取、B 取变 +1/2、−1/2。
对照：给 C 的取货物品格加第三条（对手放行的）取货通道，(1) 应当失败。
Φ 一律乘 2 存成整数。用法：python3 -B plant_graph.py cap L1 L2 q [leak]
"""
import json
import sys
import time
from itertools import product


def run(cap, L1, L2, q, leak=False):
    E = -1
    cell_vals = [E] + list(range(q + 1))      # 运输物品格：空或已停留子步数
    cache_vals = [E] + list(range(q + 1))     # 缓存格：空或还差子步数
    cnt = list(range(cap + 1))

    # 状态：(ca 元组, a_in, a_c, a_out, ac 元组, c_in, c_c, g, cb, lk)
    def phi2(s):
        ca, a_in, a_c, a_out, ac, c_in, c_c, g, cb, lk = s
        n = sum(1 for x in ca if x != E) + a_in + (a_c != E) + a_out
        n += sum(1 for x in ac if x != E) + c_in + (c_c != E)
        return 2 * n + g

    def mandatory(s):
        """一个时刻里必然发生的移动（能成功就一定会做）；返回 (后继, 名字)。"""
        ca, a_in, a_c, a_out, ac, c_in, c_c, g, cb, lk = s
        out = []
        if g > 0 and ca[0] == E:
            out.append(((((0,) + ca[1:]), a_in, a_c, a_out, ac, c_in, c_c, g - 1, cb, lk), 'A取'))
        if g > 0 and cb == E:
            out.append(((ca, a_in, a_c, a_out, ac, c_in, c_c, g - 1, 0, lk), 'B取'))
        if leak and g > 0 and lk == E:
            out.append(((ca, a_in, a_c, a_out, ac, c_in, c_c, g - 1, cb, 0), '漏'))
        for j in range(L1 - 1):
            if ca[j] == q and ca[j + 1] == E:
                l = list(ca); l[j] = E; l[j + 1] = 0
                out.append(((tuple(l), a_in, a_c, a_out, ac, c_in, c_c, g, cb, lk), '前移'))
        if ca[-1] == q and a_in < cap:
            l = list(ca); l[-1] = E
            out.append(((tuple(l), a_in + 1, a_c, a_out, ac, c_in, c_c, g, cb, lk), '进A'))
        if a_c == E and a_in >= 1:
            out.append(((ca, a_in - 1, q, a_out, ac, c_in, c_c, g, cb, lk), 'A开批'))
        if a_c == 0 and a_out < cap:
            out.append(((ca, a_in, E, a_out + 1, ac, c_in, c_c, g, cb, lk), 'A出批'))
        if a_out > 0 and ac[0] == E:
            out.append(((ca, a_in, a_c, a_out - 1, (0,) + ac[1:], c_in, c_c, g, cb, lk), '进AC'))
        for j in range(L2 - 1):
            if ac[j] == q and ac[j + 1] == E:
                l = list(ac); l[j] = E; l[j + 1] = 0
                out.append(((ca, a_in, a_c, a_out, tuple(l), c_in, c_c, g, cb, lk), '前移'))
        if ac[-1] == q and c_in < cap:
            l = list(ac); l[-1] = E
            out.append(((ca, a_in, a_c, a_out, tuple(l), c_in + 1, c_c, g, cb, lk), '进C'))
        if c_c == E and c_in >= 1:
            out.append(((ca, a_in, a_c, a_out, ac, c_in - 1, q, g, cb, lk), 'C开批'))
        if c_c == 0 and g <= cap - 2:
            out.append(((ca, a_in, a_c, a_out, ac, c_in, E, g + 2, cb, lk), 'C出批'))
        return out

    def optional(s):
        """对手可做可不做：cb（及对照里的第三条通道）里已满 1 tick 的货被下游拿走。"""
        ca, a_in, a_c, a_out, ac, c_in, c_c, g, cb, lk = s
        out = []
        if cb == q:
            out.append((ca, a_in, a_c, a_out, ac, c_in, c_c, g, E, lk))
        if leak and lk == q:
            out.append((ca, a_in, a_c, a_out, ac, c_in, c_c, g, cb, E))
        return out

    dphi_bad = [0]

    def closures(pre):
        stack = [pre]
        seen = {pre}
        res = []
        while stack:
            s = stack.pop()
            m = mandatory(s)
            if not m:
                res.append(s)
            p = phi2(s)
            for t, name in m:
                d = phi2(t) - p
                want = 1 if name == 'A取' else (-1 if name in ('B取', '漏') else 0)
                if d != want:
                    dphi_bad[0] += 1
                if t not in seen:
                    seen.add(t); stack.append(t)
            for t in optional(s):
                if phi2(t) != p:
                    dphi_bad[0] += 1
                if t not in seen:
                    seen.add(t); stack.append(t)
        return res

    def age(s):
        ca, a_in, a_c, a_out, ac, c_in, c_c, g, cb, lk = s
        f = lambda x: x if x == E else min(x + 1, q)
        h = lambda x: x if x == E else max(x - 1, 0)
        return (tuple(f(x) for x in ca), a_in, h(a_c), a_out, tuple(f(x) for x in ac),
                c_in, h(c_c), g, f(cb), f(lk))

    t_start = time.time()
    lk_vals = cell_vals if leak else [E]
    nodes = []
    for ca in product(cell_vals, repeat=L1):
        for ac in product(cell_vals, repeat=L2):
            for a_in, a_c, a_out, c_in, c_c, g, cb, lk in product(cnt, cache_vals, cnt, cnt, cache_vals, cnt, cell_vals, lk_vals):
                s = (ca, a_in, a_c, a_out, ac, c_in, c_c, g, cb, lk)
                if not mandatory(s):
                    nodes.append(s)
    index = {s: i for i, s in enumerate(nodes)}
    n = len(nodes)
    succ = [None] * n
    nedges = 0
    for i, s in enumerate(nodes):
        outs = {index[t] for t in closures(age(s))}
        succ[i] = outs
        nedges += len(outs)
    phis = [phi2(s) for s in nodes]

    # (1) 能到的最小 Φ：按 Φ 从小到大沿前驱回溯
    pred = [[] for _ in range(n)]
    for i in range(n):
        for j in succ[i]:
            pred[j].append(i)
    minphi = [None] * n
    for v in sorted(range(n), key=lambda i: phis[i]):
        if minphi[v] is not None:
            continue
        minphi[v] = phis[v]
        stack = [v]
        while stack:
            x = stack.pop()
            for y in pred[x]:
                if minphi[y] is None:
                    minphi[y] = phis[v]
                    stack.append(y)
    stuck2 = 2 * (L1 + L2 + 3 * cap + 2) + (cap - 1)
    bound2 = stuck2 - 1
    viol = [i for i in range(n) if minphi[i] < min(phis[i] - 1, bound2)]
    slack_used = sum(1 for i in range(n) if minphi[i] == phis[i] - 1 and phis[i] - 1 < bound2)
    cap_tight = sum(1 for i in range(n) if minphi[i] == bound2 and bound2 < phis[i] - 1)
    worst = min(minphi[i] - min(phis[i] - 1, bound2) for i in range(n))

    # (2) 卡住界：起态后满 q 个子步（1 tick）的状态集合 R_q
    R = set(range(n))
    for step in range(q):
        # 循环后 R 是起态后恰好 step+1 个子步能到的状态
        R = {j for i in R for j in succ[i]}
    # 对照：只在第一个 tick 里出现的「首格旧货却低于卡住界」的状态（说明 m ≥ t0+1 这一限定是需要的）
    first_tick_low = sum(1 for i in range(n) if i not in R and nodes[i][0][0] == q and phis[i] < stuck2)
    stuck_states = [i for i in R if nodes[i][0][0] == q]
    stuck_viol = [i for i in stuck_states if phis[i] < stuck2]
    stuck_min = min((phis[i] for i in stuck_states), default=None)

    res = {
        'cap': cap, 'L1': L1, 'L2': L2, 'q': q, 'leak': leak,
        'closed_states': n, 'edges': nedges,
        'bound_x2': bound2, 'stuck_bound_x2': stuck2,
        'violations': len(viol),
        'violation_examples': [[str(nodes[i]), phis[i], minphi[i]] for i in viol[:3]],
        'min_of_minphi_minus_bound_x2': worst,
        'states_needing_half_slack': slack_used,
        'states_where_constant_is_attained': cap_tight,
        'dphi_step_mismatch': dphi_bad[0],
        'stuck_states_after_1tick': len(stuck_states),
        'stuck_violations': len(stuck_viol),
        'stuck_min_phi_x2': stuck_min,
        'first_tick_old_head_below_stuck_bound': first_tick_low,
        'seconds': round(time.time() - t_start, 1),
    }
    return res


CONFIGS = [  # (cap, L1, L2, q, leak)
    (2, 1, 1, 1, False), (2, 1, 1, 2, False), (2, 1, 1, 3, False), (2, 1, 1, 4, False),
    (3, 1, 1, 1, False), (3, 1, 1, 2, False), (3, 1, 1, 3, False),
    (2, 2, 1, 2, False), (2, 1, 2, 2, False), (2, 2, 1, 3, False), (2, 1, 2, 3, False),
    (2, 2, 2, 2, False), (4, 1, 1, 2, False),
    (3, 1, 1, 4, False), (4, 1, 1, 3, False), (5, 1, 1, 2, False),
    (2, 3, 1, 2, False), (2, 1, 3, 2, False), (3, 2, 1, 2, False), (3, 1, 2, 2, False),
    (2, 1, 1, 2, True), (3, 1, 1, 2, True),
]


def _job(c):
    return run(*c)


if __name__ == '__main__':
    if sys.argv[1] == 'all':
        # 至多 6 个进程，每个单线程
        from multiprocessing import Pool
        with Pool(6) as pool:
            results = pool.map(_job, CONFIGS, chunksize=1)
        out = sys.argv[2]
        with open(out, 'w') as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        for r in results:
            print(r['cap'], r['L1'], r['L2'], r['q'], '对照' if r['leak'] else '', r['closed_states'],
                  '违例', r['violations'], '卡住违例', r['stuck_violations'], '单步Φ不符', r['dphi_step_mismatch'],
                  '用到1/2余量', r['states_needing_half_slack'], '首tick旧货低于卡住界', r['first_tick_old_head_below_stuck_bound'],
                  f"{r['seconds']}s")
    else:
        cap, L1, L2, q = map(int, sys.argv[1:5])
        leak = len(sys.argv) > 5 and sys.argv[5] == 'leak'
        print(json.dumps(run(cap, L1, L2, q, leak), ensure_ascii=False))
