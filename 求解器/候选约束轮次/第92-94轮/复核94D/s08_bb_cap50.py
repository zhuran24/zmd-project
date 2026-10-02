# 容量 50 下的「相邻两个 B」局部界：A存货、A取货、C存货取 {0,1,2,25,47,48,49,50}，C取货取 {0,1,2,3,24,25,47,48,49,50}，
# 其余维度（缓存 10 种、CA/AC 各格 9 种、两种轮询先后）全取。编码甲。与 s08_bb_exhaustive.py 同一搜索，只换取值集合。
import sys, itertools, json, time
from multiprocessing import Pool
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as S
from s08_bb_exhaustive import caches, cells, S0

V3 = [0, 1, 2, 25, 47, 48, 49, 50]
VC = [0, 1, 2, 3, 24, 25, 47, 48, 49, 50]


def work(ain):
    cap, L1, L2, G = 50, 1, 1, 32
    cfg = S.Cfg(k=3, cap=cap, has_b=False, has_k=False)
    best = None
    nbb = 0
    for aout, cin, cout in itertools.product(V3, V3, VC):
        for ac_, cc_ in itertools.product(caches(), repeat=2):
            for ca in cells(L1):
                for acc in cells(L2):
                    for poll in ((50, 60), (60, 50)):
                        st = ((ain, aout, ac_), None, (cin, cout, cc_), None, ca, acc, (-1,), None, (), poll, ())
                        st, sent, _, _ = S.step(st, S0 + 1, cfg)
                        if sent != 'B':
                            continue
                        t = S0 + 2
                        while t <= S0 + 1 + 8 + G:
                            if t >= S0 + 9:
                                st2, s2, _, _ = S.step(st, t, cfg, rel_cb=True)
                                if s2 == 'B':
                                    nbb += 1
                                    v = S.phi2(st2) - 2 * (L1 + L2)
                                    if best is None or v < best[0]:
                                        best = (v, st, t, st2)
                            st, s1, _, _ = S.step(st, t, cfg, rel_cb=False)
                            if s1 is not None:
                                break
                            t += 1
    return nbb, best


if __name__ == '__main__':
    t0 = time.time()
    with Pool(3) as p:
        res = p.map(work, V3)
    nbb = sum(r[0] for r in res)
    best = min((r[1] for r in res if r[1]), key=lambda b: b[0])
    out = {'BB轨迹数': nbb, '最小Φ−L1−L2': best[0] / 2, 'b2−1步末状态': best[1], 'b2': best[2], 'b2步末': best[3],
           '秒': round(time.time() - t0, 1)}
    print(json.dumps(out, ensure_ascii=False, default=str))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + '/s08_bb_cap50.json', 'w'), ensure_ascii=False, indent=1, default=str)
