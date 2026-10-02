# 两条显式轨迹（容量 50，L1=L2=1，CB 一格），甲、乙两套编码各算一遍：
#  例一：原条目常数 176 的反例（调试期结束时的起态，按下文玩家操作调出）。
#  例二：Φ 在第二个 B 后取到 L1+L2+151.5，说明候选常数 150 成立但不紧，紧值为 151.5。
# 玩家操作（调试期内，两步之间）：先让整个单元塞满（A 回路满、C 取货 50 且一批完成卡在缓存），
# 再从 C 取货物品格拿走种子（例一留 1 粒、例二留 0 粒），此时卡住的一批 2 粒立即进格；
# 下一步 C 开新批（存货 50→49）；这一步之后玩家往 C 存货补 1 件植株（49→50）
# 例二另外再拿走 1 粒种子。调试期就此结束，记为 s。之后 CB 末端（B 一侧）在 s+1、s+9 两步收货。
import sys, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as SA
import sim_b as SB

L1 = L2 = 1
L3 = 1


def run_a(take_left, extra_take):
    cfg = SA.Cfg(k=3, cap=50, has_b=False, has_k=False)
    t = 100
    # 塞满状态 J：A、C 存取货 50、缓存完成卡住；CA、AC、CB 满且早已成熟；CA 上次成功早于 CB
    st = ((50, 50, -2), None, (50, 50, -2), None, (0,), (0,), (0,), None, (), (40, 60), ())
    # 玩家拿走种子
    A, B, C, K, CA, AC, CB, BK, KCH, pc, pk = st
    C = SA.settle((C[0], take_left, C[2]), 2, 50)
    st = (A, B, C, K, CA, AC, CB, BK, KCH, pc, pk)
    st, s1, _, _ = SA.step(st, t + 1, cfg, rel_cb=False)   # 本步 C 开新批，不送货
    A, B, C, K, CA, AC, CB, BK, KCH, pc, pk = st
    C = (C[0] + 1, C[1] - extra_take, C[2])                 # 玩家补 1 件植株、可能再拿 1 粒
    st = (A, B, C, K, CA, AC, CB, BK, KCH, pc, pk)
    s = t + 1
    rows = [{'步': s, '2Φ': SA.phi2(st), 'C送': None, 'A': st[0], 'C': st[2]}]
    phis = SA.phi2(st)
    for tt in range(s + 1, s + 41):
        rel = tt in (s + 1, s + 9)
        st, sc, _, _ = SA.step(st, tt, cfg, rel_cb=rel)
        rows.append({'步': tt, '2Φ': SA.phi2(st), 'C送': sc, 'A': st[0], 'C': st[2]})
    return phis, rows


def run_b(take_left, extra_take):
    net = SB.Net('cur')
    Cm = SB.Machine('C', 'plant', 'seed', 2)
    Am = SB.Machine('A', 'seed', 'plant', 1)
    rel = set()
    sinkB = SB.Sink('Bside', lambda t: t in rel)
    net.machines = [Am, Cm]
    ca = SB.path(net, 'CA', L1, Cm, Am)
    cb = SB.path(net, 'CB', L3, Cm, sinkB)
    ac = SB.path(net, 'AC', L2, Am, Cm)
    net.order = SB.chain_order([ca, cb, ac])
    net.A, net.C, net.CA, net.CB, net.AC = Am, Cm, ca, cb, ac
    net.t = 100
    for m in (Am, Cm):
        m.inp, m.out, m.busy, m.done = 50, 50, None, m.batch
    for c, it in ((ca[0], 'seed'), (ac[0], 'plant'), (cb[0], 'seed')):
        c.item, c.age, c.frm = it, 100, 'prev'
    Cm.queue = [ca[0], cb[0]]
    Cm.never = set()
    Cm.out = take_left
    Cm.flow()
    net.step()
    Cm.inp += 1
    Cm.out -= extra_take
    s = net.t
    rel.update({s + 1, s + 9})
    rows = [{'步': s, '2Φ': SB.phi2(net)}]
    phis = SB.phi2(net)
    for tt in range(s + 1, s + 41):
        before = (Cm.out, ca[0].item, cb[0].item, ca[0].age, cb[0].age)
        net.step()
        rows.append({'步': net.t, '2Φ': SB.phi2(net)})
    return phis, rows


def analyse(name, take_left, extra_take):
    pa, ra = run_a(take_left, extra_take)
    pb, rb = run_b(take_left, extra_take)
    same = pa == pb and [r['2Φ'] for r in ra] == [r['2Φ'] for r in rb]
    L = L1 + L2
    s = ra[0]['步']
    mn = min(ra[1:], key=lambda r: r['2Φ'])
    sends = [(r['步'], r['C送']) for r in ra[1:] if r['C送']]
    return {
        '例': name,
        's 步号': s,
        'Φ(s)−L1−L2': (pa - 2 * L) / 2,
        'C 的成功发送（步, 去向）': sends[:6],
        '之后最小 Φ−L1−L2': (mn['2Φ'] - 2 * L) / 2,
        '取到最小的步': mn['步'],
        '原条目下界 min(Φ(s)−1/2, L+176)−L': min((pa - 1) / 2 - L, 176),
        '候选下界 min(Φ(s)−1/2, L+150)−L': min((pa - 1) / 2 - L, 150),
        '原条目是否被违反': (mn['2Φ'] - 2 * L) / 2 < min((pa - 1) / 2 - L, 176),
        '候选是否被违反': (mn['2Φ'] - 2 * L) / 2 < min((pa - 1) / 2 - L, 150),
        '甲乙逐步 2Φ 一致': same,
        '逐步2Φ(甲)': [r['2Φ'] for r in ra[:16]],
    }


if __name__ == '__main__':
    out = [analyse('例一（原 176 反例）', 1, 0), analyse('例二（151.5 取到）', 0, 1)]
    for o in out:
        print(json.dumps({k: v for k, v in o.items() if k != '逐步2Φ(甲)'}, ensure_ascii=False))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + '/s08_examples.json', 'w'), ensure_ascii=False, indent=1)
