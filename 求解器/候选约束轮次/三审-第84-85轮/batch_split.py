#!/usr/bin/env python3
"""三审自写：整批 k 件配 k 条取货通道的均分，在任意相位下的随机对抗核对。

模型（按规则，时间取 1/q tick 的格点，相位任意）：
- 取货物品格 g 件，只由整批 k 件进入，放得下（g+k≤50）才进；批次完成时刻两两至少相隔 1 tick
  （上一批全部进格才开下一批，制造 1 tick），对手可以让下一批晚开（断料）。
- k 条取货通道的首运输物品格只从本格收货；收下的物品至少停 1 tick，之后何时被下游取走由对手定。
- 同一时刻的判定做到没有可动为止，先后由对手随机定（进格与各通道取货交错）。
- 「刻」：从对手选的起点 θ 起每 1 tick 一段。某条通道在某刻「就绪」＝首格在这一刻里某个时点是空的
  （含同一时刻内先被取走、再收货之间的时点）。
核对：每刻每条至多取 1 件；在每一段各刻都全部就绪的连续刻里，「有的取、有的没取」的刻至多 1 个，
任两条累计件数差至多 1；段首件数是 k 的倍数时这样的刻为 0 个。
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = 50


def trial(rng, k, q, horizon_ticks, foreign=False):
    T = horizon_ticks * q
    theta = rng.randrange(q)
    g = rng.randrange(CAP + 1)
    cell_arr = [None if rng.random() < 0.5 else -rng.randrange(0, 2 * q) for _ in range(k)]  # 物品进首格的时刻
    p_free = rng.choice([0.3, 0.6, 0.9, 1.0])
    p_starve = rng.choice([0.0, 0.1, 0.4])
    next_done = rng.randrange(0, q + 1)  # 当前一批的完成时刻（子步）
    pending = False
    nke = (T - theta) // q + 2
    ready = [[False] * k for _ in range(nke)]
    takes = [[0] * k for _ in range(nke)]
    g_start = [None] * nke

    def ke(t):
        return (t - theta) // q + 1  # 刻编号，θ 之前的算第 0 刻

    for t in range(T):
        kk = ke(t)
        if g_start[kk] is None:
            g_start[kk] = g
        # 下游取走首格旧物（至少停满 1 tick）
        for j in range(k):
            if cell_arr[j] is not None and t - cell_arr[j] >= q and rng.random() < p_free:
                cell_arr[j] = None
        for j in range(k):
            if cell_arr[j] is None:
                ready[kk][j] = True
        if foreign and cell_arr[0] is None and rng.random() < 0.7:
            cell_arr[0] = t  # 对照：通道 0 的首格另有来路抢先填入（违反独占接收）
        if next_done is not None and t == next_done:
            pending = True
            next_done = None
        # 同一时刻做到没有可动为止，先后随机
        entered_at = None
        while True:
            acts = []
            if pending and g + k <= CAP:
                acts.append(('进', None))
            if g > 0:
                acts += [('取', j) for j in range(k) if cell_arr[j] is None]
            if not acts:
                break
            a, j = rng.choice(acts)
            if a == '进':
                g += k
                pending = False
                entered_at = t
            else:
                g -= 1
                cell_arr[j] = t
                takes[kk][j] += 1
        if entered_at is not None:
            start = t
            while rng.random() < p_starve:
                start += 1
            next_done = start + q
    # 核对
    bad = []
    for kk in range(nke):
        if any(x > 1 for x in takes[kk]):
            bad.append(('一刻多取', kk))
    kk = 1
    last = ke(T - 1)  # 最后一刻可能不完整，不计
    segs = 0
    seg_partial = 0
    seg_long = 0
    while kk < last:
        if not all(ready[kk]):
            kk += 1
            continue
        s = kk
        while kk < last and all(ready[kk]):
            kk += 1
        e = kk  # [s, e)
        segs += 1
        partial = [x for x in range(s, e) if 0 < sum(takes[x]) < k]
        cum = [sum(takes[x][j] for x in range(s, e)) for j in range(k)]
        seg_partial += len(partial) == 1
        seg_long += e - s >= 10
        if len(partial) > 1:
            bad.append(('部分取多于一刻', s, e, partial))
        if max(cum) - min(cum) > 1:
            bad.append(('累计差大于1', s, e, cum))
        if g_start[s] % k == 0 and partial:
            bad.append(('段首为k倍数仍有部分取', s, e, partial))
    return bad, (segs, seg_partial, seg_long)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'control':
        rng = random.Random(7)
        hit = sum(1 for _ in range(500) if trial(rng, 2, 1, 80, foreign=True)[0])
        print({'对照（通道 0 首格另有来路）出现违例的试验数': hit, '共': 500})
        (HERE / 'out' / 'batch_split_control.json').write_text(json.dumps({'对照违例试验数': hit, '共': 500}, ensure_ascii=False))
        return
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
    rng = random.Random(seed)
    stats = {'试验': 0, '全就绪段': 0, '其中恰有一个部分取刻的段': 0, '其中长至少10刻的段': 0, '违例': 0, '例': []}
    for _ in range(n):
        k = rng.choice([2, 3, 4])
        q = rng.choice([1, 2, 3, 4, 6])
        bad, segs = trial(rng, k, q, rng.choice([30, 80, 200]))
        stats['试验'] += 1
        stats['全就绪段'] += segs[0]
        stats['其中恰有一个部分取刻的段'] += segs[1]
        stats['其中长至少10刻的段'] += segs[2]
        if bad:
            stats['违例'] += 1
            if len(stats['例']) < 5:
                stats['例'].append({'k': k, 'q': q, 'bad': bad[:3]})
    (HERE / 'out' / f'batch_split_{seed}.json').write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(stats)


if __name__ == '__main__':
    main()
