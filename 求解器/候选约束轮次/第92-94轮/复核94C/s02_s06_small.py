#!/usr/bin/env python3
"""S02 判据的抽象穷举核对；S06 旧条文“整倍数则各取一件或都不取”的反例在自写模拟器上重现。"""
import json, itertools, random
from stepsim import World, Machine, Sink


def s02_check(a, b, maxlen):
    """双格机器，只做 aA+bB。料序 w 逐件到达；机器能开批就开（产物总能清出）。
    判据成立的料序：验证每件都能进格；判据不成立的第一处：验证该件确实永久收不下（作对照）。"""
    ok_pass = ok_fail = bad = 0
    for xa in range(0, 51, 7):
        for xb in range(0, 51, 7):
            for L in range(1, maxlen + 1):
                for w in itertools.product('AB', repeat=L):
                    # 判据
                    IA = IB = 0
                    crit = True
                    for kk in range(L):
                        m = min((xa + IA) // a, (xb + IB) // b)
                        rA = xa + IA - a * m; rB = xb + IB - b * m
                        if (w[kk] == 'A' and rA >= 50) or (w[kk] == 'B' and rB >= 50):
                            crit = False
                            break
                        if w[kk] == 'A':
                            IA += 1
                        else:
                            IB += 1
                    # 模拟：库存，能开就开（开批用量离开存货格），否则收下一件，收不下且开不了 -> 卡死
                    A, B = xa, xb
                    stuck = False
                    for item in w:
                        while True:
                            if (item == 'A' and A < 50) or (item == 'B' and B < 50):
                                if item == 'A':
                                    A += 1
                                else:
                                    B += 1
                                break
                            if A >= a and B >= b:
                                A -= a; B -= b
                                continue
                            stuck = True
                            break
                        if stuck:
                            break
                    if crit and stuck:
                        bad += 1
                    elif crit:
                        ok_pass += 1
                    elif stuck:
                        ok_fail += 1
    return dict(a=a, b=b, maxlen=maxlen, crit_and_ok=ok_pass, crit_violated_and_stuck=ok_fail,
                crit_but_stuck=bad)


def s06_old_counterexample():
    """K：荞花粉碎机，取货格空，缓存一批第 7 步完成；两条单格带进一个总能收的终点。
    以第 0—7 步为一刻：刻首件数 0（是 2 的倍数），两条首格都曾空着，但这一刻两路件数是 (1,0)。"""
    res = []
    for r0, r1, kr in itertools.product(range(2), range(2), range(2)):
        w = World()
        K = Machine('K', [({'荞花': 1}, '荞花粉末', 2, 8)], 1, rank=kr)
        Z = Sink('Z')
        w.nts = [K]
        e0 = w.chain(K, Z, [1], ranks=[r0], out_rank=r0, name='a')
        e1 = w.chain(K, Z, [1], ranks=[r1], out_rank=1 - r0, name='b')
        w.finalize()
        K.cache = ('run', 8, '荞花粉末', 2)  # 第 7 步完成
        got = {'a': 0, 'b': 0}
        for t in range(8):
            w.step()
        for t, nm in K.sent:
            if t < 8:
                got[nm.split('.')[0]] += 1
        res.append(dict(ranks=(r0, r1, kr), first_tick=(got['a'], got['b']), sends=K.sent))
    return res


if __name__ == '__main__':
    out = dict(s02=[s02_check(2, 1, 9), s02_check(1, 2, 9), s02_check(3, 2, 8)],
               s06_old=s06_old_counterexample())
    json.dump(out, open('s02_s06_small.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, default=str)[:2500])
