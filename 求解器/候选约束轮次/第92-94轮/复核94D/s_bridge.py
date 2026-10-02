# 采种单元内部进路含「同一轴相邻两个桥接器」时，两条候选在两种读法下的表现（编码乙）。
# CA（或 CB）= 传送带U → 桥接器P ⇄ 桥接器Q → 传送带D；其余进路各一格传送带。
# 现行读法：次序 D、Q、P、U（层数无法确定时的一种），Q 判定时把 P 的另一上游 U 一起判定。
# 拟改读法：同一次序，Q 的物品来自 P 不能回 P，不算往 P 送货，不带动 U。
# 测一：满库存起态（修订版不断料的前提），K 三口末端成熟就收、或随机；核修订版不断料各条与回路存量下界。
# 测二：现行读法下 CA 含相邻桥时回路存量能否跌破 L1+L2+150（检验修订版排除相邻桥是否必要）。
import sys, json, random
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_b as SB


def build(reading, where, k=3, n=3, adv=None):
    net = SB.Net(reading)
    C = SB.Machine('C', 'plant', 'seed', 2)
    A = SB.Machine('A', 'seed', 'plant', 1)
    B = SB.Machine('B', 'seed', 'plant', 1)
    K = SB.Machine('K', 'plant', 'powder', k)
    net.machines = [A, B, C, K]
    orders = []

    def mk(name, src, dst, bridged):
        if not bridged:
            cs = SB.path(net, name, 1, src, dst)
            orders.append([cs[0]])
            return cs
        U, P, Q, D = (SB.Cell(name + x) for x in 'UPQD')
        U.outs = [P]
        P.outs = [Q]
        Q.outs = [D, P]
        D.outs = [dst]
        net.cells += [U, P, Q, D]
        src.outs.append(U)
        src.queue.append(U)
        src.never.add(id(U))
        orders.append([D, Q, P, U])
        return [U, P, Q, D]

    CA = mk('CA', C, A, where == 'CA')
    CB = mk('CB', C, B, where == 'CB')
    AC = mk('AC', A, C, where == 'AC')
    BK = mk('BK', B, K, where == 'BK')
    KP = []
    for i in range(n):
        sink = SB.Sink(f'S{i}', (lambda i: (lambda t: adv(t, i)))(i))
        KP.append(mk(f'K{i}', K, sink, False))
    order = []
    for lay in range(4):
        for o in orders:
            if lay < len(o):
                order.append(o[lay])
    net.order = order
    net.A, net.B, net.C, net.K = A, B, C, K
    net.CA, net.CB, net.AC, net.BK, net.KP = CA, CB, AC, BK, KP
    for m in (A, B, C, K):
        m.inp, m.out, m.busy, m.done = 50, 50, 8, 0
    for p, it in ((CA, 'seed'), (CB, 'seed'), (AC, 'plant'), (BK, 'plant')):
        prev = 'C' if p is CA or p is CB else ('A' if p is AC else 'B')
        for c in p:
            c.item, c.age, c.frm = it, 8, prev
            prev = c.unit
    return net


def run(reading, where, adv, steps, k=3, n=3):
    net = build(reading, where, k, n, adv)
    L = len(net.CA) + len(net.AC)
    p0 = SB.phi2(net)
    bound = min(p0 - 1, 2 * (L + 150))
    viol = {}
    minphi = 10**9
    maxwait = 0
    wait = [0] * n
    for _ in range(steps):
        net.step()
        v = SB.phi2(net)
        minphi = min(minphi, v)
        if v < bound:
            viol['Φ<下界'] = viol.get('Φ<下界', 0) + 1
        for nm, m in (('A', net.A), ('B', net.B), ('C', net.C), ('K', net.K)):
            if not m.cache_nonempty():
                viol[nm + '缓存空'] = viol.get(nm + '缓存空', 0) + 1
        if net.B.inp < 49 or net.K.inp < 49 or net.B.out < 49 or net.K.out < 50 - k:
            viol['库存界'] = viol.get('库存界', 0) + 1
        if net.CB[0].item is None or net.BK[0].item is None:
            viol['CB/BK首格步末空'] = viol.get('CB/BK首格步末空', 0) + 1
        for i in range(n):
            if net.KP[i][0].item is None:
                wait[i] += 1
                maxwait = max(maxwait, wait[i])
            else:
                wait[i] = 0
    return {'读法': reading, '相邻桥位置': where, '违例计数': viol, '最小Φ−L1−L2': minphi / 2 - L,
            'K口最长连续空步末': maxwait}


if __name__ == '__main__':
    rnd = random.Random(7)
    advs = {'成熟就收': lambda t, i: True,
            '随机0.3': lambda t, i: rnd.random() < 0.3,
            '每9步': lambda t, i: t % 9 == i}
    out = []
    for reading in ('cur', 'new'):
        for where in ('CA', 'CB', 'AC', 'BK'):
            for an, adv in advs.items():
                r = run(reading, where, adv, 6000)
                r['对手'] = an
                out.append(r)
                print(json.dumps(r, ensure_ascii=False))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + '/s_bridge.json', 'w'), ensure_ascii=False, indent=1)
