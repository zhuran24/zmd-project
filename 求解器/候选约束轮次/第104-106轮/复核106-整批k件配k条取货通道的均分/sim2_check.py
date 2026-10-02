#!/usr/bin/env python3
"""用独立模拟器 sim2（只读导入，不写字节码）在具体单位上重放：

W1  砂叶粉碎机式的 k=3：取货格起点 3 件，1 株原料经四格带第 32 步到机，第 40 步出 3 件；
    三条出口各接独占长带到总能收的终点。第 30 步前离线：清空记录、按 3、2、1 重接 -> 123321；
    保留记录 -> 123123。
W2  k=2，第 1 路首单位是汇流器（另外两条存货边没有通道），直接送进总能收的终点，接通更早；
    第 2 路是传送带。起点 1 件，第 3、16 步各进一批 -> 汇、带、汇、汇、带（无离线段内差 2）。
R   随机具体运行：出口是独占传送带（长 2—5）或汇流器，原料按固定周期到机，随机离线
    （保留、清空、部分清空，接通名次随机重排）。在本机每次判定前检查前件：
    首格里的件停留不超过 7 步（即恰在 8 步后、本机判定前移出）。
sim2 的收货按现行第 31 行；这里每个首单位只有本机这一个上游（非运输单位），
临时规则第 1 条与第 31 行在这些构型里没有差别。sim2 两处已知错（flush 同种唯一、
按元件判断不移回）在这些构型里不触发：本机只有一种原料、物品不会回到本机。
"""
import json, os, random, sys
sys.dont_write_bytecode = True
SIM = '/home/zhuran24/zmd-research-fresh/求解器/规则修订/2026-09-30-迟滞/sim2'
sys.path.insert(0, SIM)
import simulator as S  # noqa: E402

from timeline import max_pair_diff, is_rotation  # noqa: E402


class Probe(S.Machine):
    """本机：判定前记录各首格里件的停留步数。"""
    firsts = ()
    premise_bad = 0

    def judge(self, w):
        for f in self.firsts:
            item = f.cells[0]
            if item is not None and w.t - item.entered >= 8:
                Probe.premise_bad += 1
        super().judge(w)


def machine(k, out0=0, running=None):
    r = S.Recipe('r', (('raw', 1),), 'P', k, 8)
    m = Probe('M', recipes=[r])
    m.output = [S.Item('P', -100) for _ in range(out0)]
    if running is not None:
        m.running, m.remaining = r, running
    return m


def build(k, kinds, lens, ranks, feed):
    """kinds[i] in ('belt','merge','merge_belt')；ranks[i] 是本机到第 i 个首单位通道的接通名次。"""
    m = machine(k, *feed['m'])
    nodes, firsts, chans = [m], [], []
    for i in range(k):
        if kinds[i] == 'belt':
            f = S.Belt('E%d' % i, lens[i]); nodes.append(f)
            sk = S.Sink('K%d' % i); nodes.append(sk); f.connect(sk, 1000 + i)
        else:
            f = S.Merger('J%d' % i); nodes.append(f)
            if kinds[i] == 'merge':
                sk = S.Sink('K%d' % i); nodes.append(sk); f.connect(sk, 1000 + i)
            else:
                b = S.Belt('JB%d' % i, lens[i]); nodes.append(b); f.connect(b, 1000 + i)
                sk = S.Sink('K%d' % i); nodes.append(sk); b.connect(sk, 2000 + i)
        firsts.append(f)
        m.connect(f, ranks[i])
        chans.append(m.output_channels[-1])
    sources = []
    if feed.get('belt') is not None:           # 预放在带上的原料
        b = S.Belt('F', feed['belt'][0]); b.cells[0] = S.Item('raw', feed['belt'][1])
        nodes.append(b); b.connect(m, 3000)
    if feed.get('period') is not None:
        src = S.Source('SRC', kinds=('raw',), period=feed['period'], phase=feed['phase'])
        b = S.Belt('F', 2); nodes += [src, b]; src.connect(b, 3001); b.connect(m, 3000)
        sources.append(src)
    m.firsts = firsts
    w = S.World(nodes, sources)
    return w, m, chans


def word_of(m, chans):
    name2i = {c.dst.name: i for i, c in enumerate(chans)}
    return [(t, name2i[d]) for t, _, d in m.sent]


def offline(m, chans, ranks, mode, rng=None):
    for c, r in zip(chans, ranks):
        c.connected = r
    if mode == 'clear':
        for c in chans:
            m.last_output[c] = -1
    elif mode == 'partial':
        for c in chans:
            if rng.random() < 0.5:
                m.last_output[c] = -1


def w1(mode):
    Probe.premise_bad = 0
    w, m, chans = build(3, ['belt'] * 3, [6, 6, 6], [1, 2, 3],
                        dict(m=(3, None), belt=(4, 0)))
    for t in range(60):
        if t == 30 and mode != 'none':
            offline(m, chans, [3, 2, 1], mode)
        w.step()
    wd = word_of(m, chans)
    seq = [i + 1 for _, i in wd]
    # 区间 [2,41) 内各路件数
    cnt = [sum(1 for t, i in wd if 2 <= t < 41 and i == j) for j in range(3)]
    return dict(mode=mode, word=seq, times=[t for t, _ in wd], interval_2_41=cnt,
                premise_bad=Probe.premise_bad)


def w2():
    Probe.premise_bad = 0
    w, m, chans = build(2, ['merge', 'belt'], [1, 4], [1, 2],
                        dict(m=(1, 4), belt=(1, 0)))
    for t in range(30):
        w.step()
    wd = word_of(m, chans)
    return dict(word=['汇' if i == 0 else '带' for _, i in wd], times=[t for t, _ in wd],
                layers={k: v for k, v in w.layers.items()},
                max_diff_no_offline=max_pair_diff([i for _, i in wd], 2),
                premise_bad=Probe.premise_bad)


def rand_run(rng, k, merge, mode, steps):
    Probe.premise_bad = 0
    kinds = ['belt'] * k
    if merge:
        kinds[0] = rng.choice(['merge', 'merge_belt'])
    lens = [rng.randint(2, 5) for _ in range(k)]
    ranks = list(range(1, k + 1)); rng.shuffle(ranks)
    period = rng.choice([8, 9, 10, 12, 16, 20, 24, 40, 64])
    feed = dict(m=(rng.choice([0, 1, k - 1, k, k + 1, 2 * k]), None),
                period=period, phase=rng.randint(0, 40))
    w, m, chans = build(k, kinds, lens, ranks, feed)
    p_off = rng.choice([0.0, 0.02, 0.08])
    segs_bounds = [0]
    for t in range(steps):
        if t > 0 and rng.random() < p_off:
            ranks = list(range(1, k + 1)); rng.shuffle(ranks)
            offline(m, chans, ranks, mode, rng)
            segs_bounds.append(t)
        w.step()
    wd = word_of(m, chans)
    word = [i for _, i in wd]
    segs = []
    bnds = segs_bounds + [10 ** 9]
    for a, b in zip(bnds, bnds[1:]):
        segs.append([i for t, i in wd if a <= t < b])
    return word, segs, Probe.premise_bad


def control():
    """对照：终点每 20 步才收一件，首格会停留超过 8 步，前件检查应当报错。"""
    Probe.premise_bad = 0
    w, m, chans = build(2, ['belt', 'belt'], [1, 1], [1, 2], dict(m=(10, None)))
    for u in w.nodes:
        if isinstance(u, S.Sink):
            u.every = 20
    for t in range(200):
        w.step()
    return dict(premise_bad=Probe.premise_bad)


def main(out, seed, n):
    res = dict(W1={m: w1(m) for m in ('none', 'retain', 'clear')}, W2=w2(), control=control())
    print(json.dumps(res, ensure_ascii=False), flush=True)
    rng = random.Random(seed)
    agg = {}
    for k in (2, 3):
        for merge in (False, True):
            for mode in ('retain', 'clear', 'partial'):
                a = dict(runs=0, premise_bad_runs=0, max_g=0, max_s=0, srot_fail=0,
                         grot_fail=0, items=0)
                for _ in range(n):
                    word, segs, pb = rand_run(rng, k, merge, mode, 400)
                    a['runs'] += 1; a['items'] += len(word)
                    if pb:
                        a['premise_bad_runs'] += 1
                        continue
                    a['max_g'] = max(a['max_g'], max_pair_diff(word, k))
                    a['max_s'] = max(a['max_s'], max(max_pair_diff(s, k) for s in segs))
                    a['srot_fail'] += not all(is_rotation(s, k) for s in segs)
                    a['grot_fail'] += not is_rotation(word, k)
                key = 'k%d-%s-%s' % (k, 'merge' if merge else 'belts', mode)
                agg[key] = a
                print(key, a, flush=True)
    res['random'] = agg
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
