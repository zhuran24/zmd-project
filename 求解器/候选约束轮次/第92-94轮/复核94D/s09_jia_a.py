# 例甲、例甲′的编码甲版本（K 两口各一格进研磨机 G；G 每批用 2 件荞花粉末、1 件砂叶粉末，8 步一批，产物总能运走）。
import sys, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as SA
from s09_check import norm


def run(mode):
    cfg = SA.Cfg(k=2, cap=50)
    S0 = 100
    st = ((50, 50, S0 + 8), (50, 50, S0 + 8), (50, 50, S0 + 8), (50, 50, S0 + 8), (S0 - 8,), (S0 - 8,), (S0 - 8,), (S0 - 8,),
          ((-1,), (-1,)), (SA.NEVER, SA.NEVER + 1), (SA.NEVER, SA.NEVER + 1))
    g = {'inp': 50, 'sand': 0, 'end': None}
    seen = {}
    rec = []
    t = S0
    while t < S0 + 20000:
        t += 1
        if g['end'] == t:
            g['end'] = None
        u = t - S0  # 与编码乙同相：乙从第 1 步起算
        if (mode == 'every10' and u % 10 == 0) or (mode == 'gate4' and u % 40 in (0, 8, 16, 24)):
            g['sand'] += 1
        rel = []
        room = 50 - g['inp']
        for p in st[8]:
            e = p[-1]
            ok = e >= 0 and t - e >= 8 and room > 0
            if ok:
                room -= 1
            rel.append(ok)
        st, sc, sk, left = SA.step(st, t, cfg, rel_k=tuple(rel))
        g['inp'] += sum(left)
        if g['end'] is None and g['inp'] >= 2 and g['sand'] >= 1:
            g['inp'] -= 2
            g['sand'] -= 1
            g['end'] = t + 8
        holes = sum(1 for p in st[8] if p[0] < 0)
        rec.append((holes, st[3][2] == t + 8, g['inp']))
        key = norm(st, t) + ((t - S0) % 40, g['inp'], g['sand'], None if g['end'] is None else g['end'] - t)
        if key in seen:
            j = seen[key]
            r = rec[j - S0:]
            return {'周期': t - j, '进入循环的步': j - S0, '周期内K首格「空了当步没补上」的步末次数': sum(x[0] for x in r),
                    '周期内K开批次数': sum(x[1] for x in r), 'G存货范围': [min(x[2] for x in r), max(x[2] for x in r)]}
        seen[key] = t


if __name__ == '__main__':
    out = {'例甲（编码甲）': run('every10'), '例甲′（编码甲）': run('gate4')}
    print(json.dumps(out, ensure_ascii=False))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + '/s09_jia_a.json', 'w'), ensure_ascii=False, indent=1)
