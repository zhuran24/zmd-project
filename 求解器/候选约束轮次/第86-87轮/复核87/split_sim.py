"""第 87 轮复核：「一批 k 件配 k 条取货通道的均分」任意相位核对（本席自写）。

模型：一个取货格 P（上限 50），只由整批 k 件补入；补入时刻由上游随机给出，相邻两批至少隔 1 tick，
且只有 P+k<=50 时才能进格（进不去就等）。k 条取货通道，首运输格只从 P 收货、空着就收，
货至少停 1 tick，之后在下游开放的时点离开（下游开放时段随机，相位任意有理数）。
同一时刻做到没有可动为止，每步随机挑一个可行动作（覆盖一切轮询、接通先后与判定次序）。
检查：取任意起点 theta 的单位时段「刻」；在一段每刻各首格都至少一度为空的连续刻中，
  (a) 任两条通道取件数之差 <= 1；(b) 段首 P 为 k 的倍数时，每刻各口取件数相等。
用法：python3 -B split_sim.py <seed> <runs>
"""
import json
import random
import sys
from fractions import Fraction as F


def one(rng, st):
    q = rng.choice([1, 2, 3, 4, 5, 7, 12])
    k = rng.randint(2, 5)
    T = rng.randint(20, 80)
    P = rng.randint(0, 50)
    # 上游：下一批可进格的最早时刻
    nxt_batch = F(rng.randint(0, 2 * q), q)
    # 首格：None 或进格时刻
    cells = [(-F(rng.randint(0, 2 * q), q) if rng.random() < 0.5 else None) for _ in range(k)]
    # 下游开放：每条一组随机开关
    tog = [sorted(F(rng.randint(0, T * q), q) for _ in range(rng.randint(0, T))) for _ in range(k)]
    init = [rng.random() < 0.7 for _ in range(k)]
    burst = rng.random() < 0.3  # 一部分运行让下游一直开，逼出「每刻都就绪」

    def opened(j, t):
        if burst:
            return True
        return init[j] ^ (sum(1 for x in tog[j] if x <= t) % 2 == 1)

    t = F(0)
    events = []  # (t, 本时刻闭合后状态, 本时刻各口取件, 本时刻中曾空的口)
    pending_batch = False
    while t <= T:
        took = [0] * k
        empty_seen = set(j for j in range(k) if cells[j] is None)
        while True:
            mv = []
            if nxt_batch <= t and P + k <= 50:
                mv.append(('batch',))
            for j in range(k):
                if cells[j] is None and P > 0:
                    mv.append(('take', j))
                if cells[j] is not None and cells[j] + 1 <= t and opened(j, t):
                    mv.append(('leave', j))
            if not mv:
                break
            x = rng.choice(mv)
            if x[0] == 'batch':
                P += k
                # 下一批至少隔 1 tick，另加随机延迟
                nxt_batch = t + 1 + (F(rng.randint(0, 3 * q), q) if rng.random() < 0.4 else 0)
            elif x[0] == 'take':
                cells[x[1]] = t
                P -= 1
                took[x[1]] += 1
            else:
                cells[x[1]] = None
            for j in range(k):
                if cells[j] is None:
                    empty_seen.add(j)
        events.append((t, P, [c is None for c in cells], took, empty_seen))
        cand = [c + 1 for c in cells if c is not None and c + 1 > t]
        if nxt_batch > t:
            cand.append(nxt_batch)
        cand += [x for tg in tog for x in tg if x > t]
        cand = [c for c in cand if c > t]
        if not cand:
            break
        t = min(cand)
    # 按不同起点划刻
    for th in (F(0), F(1, 2), F(1, 3), F(rng.randint(0, q - 1), q) if q > 1 else F(0)):
        n = 0
        rows = []
        while th + n + 1 <= T:
            a, b = th + n, th + n + 1
            ins = [e for e in events if a <= e[0] < b]
            bef = [e for e in events if e[0] < a]
            if not bef:
                n += 1
                rows.append(None)
                continue
            startP = bef[-1][1]
            start_empty = bef[-1][2]
            ready = [start_empty[j] or any(j in e[4] for e in ins) for j in range(k)]
            took = [sum(e[3][j] for e in ins) for j in range(k)]
            rows.append((all(ready), startP, took))
            if max(took) > 1:
                st['rate_viol'] += 1
            n += 1
        # 取极大的「每刻都就绪」连续段
        i = 0
        while i < len(rows):
            if rows[i] is None or not rows[i][0]:
                i += 1
                continue
            j = i
            while j < len(rows) and rows[j] is not None and rows[j][0]:
                j += 1
            seg = rows[i:j]
            st['segments'] += 1
            st['seg_intervals'] += len(seg)
            tot = [sum(r[2][c] for r in seg) for c in range(k)]
            if max(tot) - min(tot) > 1:
                st['diff_viol'] += 1
            if seg[0][1] % k == 0:
                st['aligned_segments'] += 1
                for r in seg:
                    if len(set(r[2])) > 1:
                        st['aligned_viol'] += 1
                        break
            partial = sum(1 for r in seg if len(set(r[2])) > 1)
            if partial > 1:
                st['multi_partial'] += 1
            i = j


def main():
    seed, runs = int(sys.argv[1]), int(sys.argv[2])
    rng = random.Random(seed)
    st = {'runs': runs, 'segments': 0, 'seg_intervals': 0, 'aligned_segments': 0,
          'diff_viol': 0, 'aligned_viol': 0, 'multi_partial': 0, 'rate_viol': 0}
    for _ in range(runs):
        one(rng, st)
    print(json.dumps(st, ensure_ascii=False))


if __name__ == '__main__':
    main()
