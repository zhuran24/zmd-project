# 抽查推导席报告第 8.1 节：一台每步只送 1 件的机器两条取货通道，一条下游总能收，另一条外部每 9 步才收一件，
# 总能收的那条长期是否只有 8/9 件/tick。用修订版「采种单元不断料」的满库存起态（K 为砂叶粉碎机，n=2≤k=3）。
# 甲、乙两套编码各算一遍，比较总能收那条通道在循环里的件数/步数。
import sys, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as SA
import sim_b as SB
from s09_check import norm


def run_a(ph):
    cfg = SA.Cfg(k=3, cap=50)
    S0 = 100
    st = ((50, 50, S0 + 8), (50, 50, S0 + 8), (50, 50, S0 + 8), (50, 50, S0 + 8), (S0 - 8,), (S0 - 8,), (S0 - 8,), (S0 - 8,),
          ((-1,), (S0 - ph,)), (40, 60), (SA.NEVER, SA.NEVER + 1))
    last1 = None
    seen = {}
    cnt0 = []
    t = S0
    while t < S0 + 20000:
        t += 1
        e1 = st[8][1][-1]
        ok1 = e1 >= 0 and t - e1 >= 8 and (last1 is None or t - last1 >= 9)
        st, sc, sk, left = SA.step(st, t, cfg, rel_k=(True, ok1))
        if left[1]:
            last1 = t
        cnt0.append(1 if left[0] else 0)
        key = norm(st, t) + ((None if last1 is None else min(t - last1, 9)),)
        if key in seen:
            j = seen[key]
            return {'周期': t - j, '通道0件数': sum(cnt0[j - S0:])}
        seen[key] = t
    return None


def run_b(ph):
    last = {'v': None}
    def rule1(t):
        return last['v'] is None or t - last['v'] >= 9
    s0 = SB.Sink('free', lambda t: True)
    s1 = SB.Sink('nine', rule1)
    net = SB.plant_unit(1, 1, 1, 1, 3, [(1, s0), (1, s1)])
    for m in (net.A, net.B, net.C, net.K):
        m.inp, m.out, m.busy, m.done = 50, 50, 8, 0
    for p, it in ((net.CA, 'seed'), (net.CB, 'seed'), (net.AC, 'plant'), (net.BK, 'plant')):
        p[0].item, p[0].age, p[0].frm = it, 8, 'prev'
    c1 = net.KP[1][0]
    c1.item, c1.age, c1.frm = 'powder', ph, 'K'
    net.C.queue = [net.CA[0], net.CB[0]]
    net.C.never = set()
    rec = []
    seen = {}
    for i in range(20000):
        g0, g1 = s0.got, s1.got
        net.step()
        if s1.got > g1:
            last['v'] = net.t
        rec.append(s0.got - g0)
        from s09_orig import sig
        key = sig(net, ((None if last['v'] is None else min(net.t - last['v'], 9)),))
        if key in seen:
            j = seen[key]
            return {'周期': i - j, '通道0件数': sum(rec[j + 1:i + 1])}
        seen[key] = i
    return None


if __name__ == '__main__':
    out = {}
    for ph in range(0, 9):
        a = run_a(ph)
        b = run_b(ph)
        out[f'通道1初货年龄{ph}'] = {'甲': a, '乙': b}
    print(json.dumps(out, ensure_ascii=False))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + '/shared_send.json', 'w'), ensure_ascii=False, indent=1)
