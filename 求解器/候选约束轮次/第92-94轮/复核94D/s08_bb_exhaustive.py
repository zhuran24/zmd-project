# 「相邻两个 B」局部界的穷举（小容量）。编码甲。
# 对 b1−1 步末的一切状态 X（A、C 存取货 0..Cap，缓存空/进行中余 1..8 步/已完成未进，
# CA、AC 各格空或年龄 0..7，CB 首格空，CA、CB 两种轮询先后），令 C 在 b1 送 B，
# 此后 C 不再送货，直到 CB 首格在 b2≥b1+8 被对手放空、C 又送 B；记 b2 步末的 2Φ−2(L1+L2) 最小值。
# 用法: python3 -B s08_bb_exhaustive.py Cap L1 L2 [G]
import sys, itertools, json, time
from multiprocessing import Pool
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as S

S0 = 100  # X 所在步号


def caches():
    return [-1, -2] + [S0 + r for r in range(1, 9)]


def cells(L):
    vals = [-1] + [S0 - a for a in range(8)]
    return list(itertools.product(vals, repeat=L))


def work(args):
    cap, L1, L2, G, ain = args
    cfg = S.Cfg(k=3, cap=cap, has_b=False, has_k=False)
    best = None
    cnt_x = cnt_bb = 0
    hist = {}
    for aout, cin, cout in itertools.product(range(cap + 1), repeat=3):
        for ac_, cc_ in itertools.product(caches(), repeat=2):
            for ca in cells(L1):
                for acc in cells(L2):
                    for poll in ((50, 60), (60, 50)):
                        cnt_x += 1
                        st = ((ain, aout, ac_), None, (cin, cout, cc_), None, ca, acc, (-1,), None, (), poll, ())
                        st, sent, _, _ = S.step(st, S0 + 1, cfg)
                        if sent != 'B':
                            continue
                        t = S0 + 2
                        while t <= S0 + 1 + 8 + G:
                            if t >= S0 + 9:
                                st2, s2, _, _ = S.step(st, t, cfg, rel_cb=True)
                                if s2 == 'B':
                                    cnt_bb += 1
                                    v = S.phi2(st2) - 2 * (L1 + L2)
                                    hist[v] = hist.get(v, 0) + 1
                                    if best is None or v < best[0]:
                                        best = (v, {'X': st, 'b2': t, 'after': st2})
                            st, s1, _, _ = S.step(st, t, cfg, rel_cb=False)
                            if s1 is not None:
                                break
                            t += 1
    return cnt_x, cnt_bb, best, hist


if __name__ == '__main__':
    cap, L1, L2 = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    G = int(sys.argv[4]) if len(sys.argv) > 4 else 32
    t0 = time.time()
    with Pool(3) as pool:
        res = pool.map(work, [(cap, L1, L2, G, ain) for ain in range(cap + 1)])
    nx = sum(r[0] for r in res)
    nbb = sum(r[1] for r in res)
    bests = [r[2] for r in res if r[2] is not None]
    best = min(bests, key=lambda b: b[0])
    hist = {}
    for r in res:
        for k, v in r[3].items():
            hist[k] = hist.get(k, 0) + v
    out = {
        'Cap': cap, 'L1': L1, 'L2': L2, 'G': G,
        'X个数': nx, 'BB轨迹数': nbb,
        '最小2Φ减2(L1+L2)': best[0],
        '候选常数3Cap的2倍': 6 * cap,
        '细化常数3Cap+1.5的2倍': 6 * cap + 3,
        '取到最小值的例': {'b2−1步末状态': best[1]['X'], 'b2': best[1]['b2'], 'b2步末': best[1]['after']},
        '2Φ减2(L1+L2)分布(最小5个)': {str(k): hist[k] for k in sorted(hist)[:5]},
        '秒': round(time.time() - t0, 1),
    }
    fn = __file__.rsplit('/', 1)[0] + f'/s08_bb_exhaustive_cap{cap}_L{L1}{L2}.json'
    json.dump(out, open(fn, 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v for k, v in out.items() if k != '取到最小值的例'}, ensure_ascii=False))
