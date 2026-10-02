#!/usr/bin/env python3
"""复核100S2：用引擎甲独立执行报告第4.2节的调试循环（清理之后的部分）。

起点：清理已完成——各格只有本线物品，数量、缓存状态（空/在制/已完成）、带上货与货龄随机；
七台成品机关闭、取货与缓存空，成品入库进路空；全部机器关闭。
循环：关闭非成品机 → 各存货格补到50 → 非成品取货格补到50、非成品进路空格补本线物品
→ 若非成品缓存全为已完成的一批则跳出；否则打开全部非成品机，随机运行16—300步，关闭，重复。
跳出后全部关闭静置随机8—60步，再一次打开全部机器。核对此刻恰为报告第3节起态，
然后不加任何扰动跑到循环态，核交付率。玩家操作都放在两步之间，不在某一步抢操作。
用法：startup_a.py START COUNT
"""
import sys, json, random, time
from engine_a import Factory
from net import BAT, CAP


def randomize(f, rng):
    for m in f.mach.values():
        m.on = False
        ks = list(m.inputs)
        for c in m.cells:
            c[0], c[1] = None, 0
        for i, k in enumerate(ks):
            n = rng.randint(0, 50)
            if n:
                m.cells[i][0], m.cells[i][1] = k, n
        if m.role == 'final':
            m.take, m.cache = 0, None
            continue
        m.take = rng.randint(0, 50)
        r = rng.random()
        if r < 0.3:
            m.cache = None
        elif r < 0.65:
            m.cache = ('run', f.t + rng.randint(1, m.dur))
        else:
            m.cache = ('done', m.qty)
        f.flush(m)
    for b in f.belts:
        if b.dst == '核心':
            b.cells = [None] * b.tiles
        else:
            b.cells = [(-rng.randint(0, 12) if rng.random() < 0.6 else None) for _ in range(b.tiles)]


def refill(f):
    for m in f.mach.values():
        for k in m.inputs:
            for c in m.cells:
                if c[0] == k:
                    c[1] = 50
                    break
            else:
                for c in m.cells:
                    if c[1] == 0:
                        c[0], c[1] = k, 50
                        break
        if m.role != 'final':
            m.take = 50
    for b in f.belts:
        if b.dst != '核心':
            b.cells = [f.t if e is None else e for e in b.cells]


def all_done(f):
    return all(m.cache is not None and m.cache[0] == 'done' for m in f.mach.values() if m.role != 'final')


def claimed_start(f):
    bad = []
    for m in f.mach.values():
        for k in m.inputs:
            if sum(c[1] for c in m.cells if c[0] == k) != 50:
                bad.append((m.name, 'stock', k))
        if m.role == 'final':
            if m.take != 0 or m.cache is not None:
                bad.append((m.name, 'final_take_cache'))
        else:
            if m.take != 50 or m.cache != ('done', m.qty):
                bad.append((m.name, 'take_cache', m.take, m.cache))
    for b in f.belts:
        if b.dst == '核心':
            if any(e is not None for e in b.cells):
                bad.append((b.idx, 'product_belt'))
        elif any(e is None or f.t - e < 8 for e in b.cells):
            bad.append((b.idx, 'belt'))
    return bad


def one(seed):
    rng = random.Random(seed)
    f = Factory(seed, lengths='rand', maxlen=[1, 3, 6, 12][seed % 4], check=False)
    randomize(f, rng)
    loops = 0
    steps_on = 0
    while True:
        for m in f.mach.values():
            m.on = False
        refill(f)
        if all_done(f):
            break
        loops += 1
        for m in f.mach.values():
            if m.role != 'final':
                m.on = True
        k = rng.randint(16, 24) if seed % 2 else rng.randint(16, 300)
        for _ in range(k):
            f.step()
        steps_on += k
        if loops > 10000:
            return dict(seed=seed, ok=False, reason='no termination')
    for m in f.mach.values():
        m.on = False
    before = f.state()
    wait = rng.randint(8, 60)
    for _ in range(wait):
        f.step()
    static = all(x == y for x, y in zip(before[:len(f.mach)], f.state()[:len(f.mach)]))
    bad = claimed_start(f)
    for m in f.mach.values():
        m.on = True
    f.violations = []
    f.check = True
    seen = {}
    t_start = f.t
    while f.t < t_start + 200000:
        h = hash(f.state())
        if h in seen:
            p = f.t - seen[h]
            s0 = f.state()
            b0, c0 = f.delivered[BAT], f.delivered[CAP]
            for _ in range(p):
                f.step()
            if f.state() == s0:
                return dict(seed=seed, ok=(not bad and static), loops=loops, steps_on=steps_on,
                            static_wait_unchanged=static, start_mismatch=bad[:5],
                            period=p, battery=f.delivered[BAT] - b0, capsule=f.delivered[CAP] - c0,
                            bat_per_tick=(f.delivered[BAT] - b0) * 8 / p, cap_per_tick=(f.delivered[CAP] - c0) * 8 / p,
                            nviol=len(f.violations))
            seen = {}
        seen[h] = f.t
        f.step()
    return dict(seed=seed, ok=False, reason='no cycle')


if __name__ == '__main__':
    a, n = int(sys.argv[1]), int(sys.argv[2])
    for s in range(a, a + n):
        t0 = time.time()
        r = one(s)
        r['secs'] = round(time.time() - t0, 1)
        print(json.dumps(r, ensure_ascii=False), flush=True)
