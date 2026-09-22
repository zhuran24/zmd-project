#!/usr/bin/env python3
"""G3 的局部计数复算；不模拟整座基地，不证明布局达标。"""
from pathlib import Path
import hashlib
import json

BASE = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def fifo_inventory(word, a, b, initial=(50, 50), cap=50, repeats=10):
    """放宽制造用时和出货的库存模型；卡死只可能来自进料互等。"""
    x, y = initial
    accepted = batches = 0
    for item in word * repeats:
        while x >= a and y >= b:
            x -= a
            y -= b
            batches += 1
        if (item == 'A' and x == cap) or (item == 'B' and y == cap):
            return dict(blocked=True, accepted=accepted, batches=batches,
                        inventory=[x, y], head=item)
        x += item == 'A'
        y += item == 'B'
        accepted += 1
    return dict(blocked=False, accepted=accepted, batches=batches,
                inventory=[x, y])


def run_can_clear(k, c, m, cap=50):
    """每批 k 件、间隔 1 tick；可在首末两个端点出货。"""
    possible = {0}
    for _ in range(m):
        nxt = set()
        for old in possible:
            # 当刻先送 old 的一些，再整批入格，再送余下配额。
            for before in range(min(old, c) + 1):
                placed = old - before + k
                if placed > cap:
                    continue
                for after in range(min(placed, c - before) + 1):
                    nxt.add(placed - after)
        possible = nxt
    return any(old <= c for old in possible)


def main():
    out = {'scope': '局部库存恒等式、互等边界、出货时间窗；非整局仿真'}
    out['sources'] = {}
    for name in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt',
                 '求解约束.txt', '候选约束.txt', '思路.txt']:
        raw = (BASE / name).read_bytes()
        out['sources'][name] = hashlib.sha256(raw).hexdigest()

    regions = []
    states_checked = 0
    for name, a, b in [('研磨', 2, 1), ('封装', 10, 15), ('灌装', 10, 10)]:
        low = b * (a - 1) - 50 * a
        high = 50 * b - a * (b - 1)
        blocked = []
        for x in range(51):
            for y in range(51):
                states_checked += 1
                z = b * x - a * y
                assert -50 * a <= z <= 50 * b
                if x == 50 and y < b:
                    assert z >= high
                    blocked.append(('A', z))
                if y == 50 and x < a:
                    assert z <= low
                    blocked.append(('B', z))
        assert min(z for head, z in blocked if head == 'A') == high
        assert max(z for head, z in blocked if head == 'B') == low
        regions.append(dict(recipe=name, a=a, b=b, strict_low=low,
                            strict_high=high, filled_z=50*(b-a)))
    out['inventory_states_checked'] = states_checked
    out['fifo_safe_regions'] = regions

    burst = fifo_inventory('A'*102 + 'B'*51, 2, 1)
    assert burst['blocked'] and burst['accepted'] == 100
    assert burst['inventory'] == [50, 0] and burst['head'] == 'A'
    out['balanced_bounded_burst_from_filled'] = burst
    for word in ['AAB', 'ABA', 'BAA']:
        assert not fifo_inventory(word, 2, 1, repeats=200)['blocked']
    assert fifo_inventory('AAB', 2, 1, initial=(50, 0))['blocked']
    assert not fifo_inventory('BAA', 2, 1, initial=(50, 0), repeats=200)['blocked']
    out['safe_band_is_not_necessary'] = {
        'initial': [50, 0], 'z': 50,
        'word_AAB': '头件 A 卡死', 'word_BAA': '库存模型连续接收 600 件'}

    x = y = 20
    trace = []
    for t in range(200):
        x -= 2
        y -= 1
        x += 1  # 一条纯 A 通道。
        if t % 2 == 0:
            x += 2  # 另外两条各自是 ABAB…。
        else:
            y += 2
        assert 0 <= x <= 50 and 0 <= y <= 50
        if t < 2:
            trace.append([x, y])
    assert (x, y) == (20, 20)
    out['three_channel_grinder'] = {
        'two_mixed_channels': '各 ABAB，比例各 1:1',
        'third_channel': '每 tick 1 A', 'two_tick_inventory': trace,
        'per_mixed_channel_D_after_200_items': -100,
        'total_D_after_200_ticks': 0,
        'batches_per_tick': 1}

    run_cases = 0
    for k in [1, 2, 3]:
        for c in [1, 2, 3]:
            for m in range(1, 21):
                run_cases += 1
                assert run_can_clear(k, c, m) == (k*m <= c*(m+1))
    assert not run_can_clear(3, 2, 3)
    assert run_can_clear(3, 2, 2)
    out['run_window_cases_checked'] = run_cases
    out['sandleaf_3_batches_2_ports'] = {'demand': 9, 'capacity': 8, 'possible': False}

    # 周期边界账：例中子区从邻区收 2 株、外送 4 粒种子，采种 2 批。
    z, a, f = 0, 2, 0
    i_s, i_v, e_s, e_v, w_s, w_v = 0, 2, 4, 0, 0, 0
    assert 2*a+i_s == z+e_s+w_s
    assert z+i_v == a+f+e_v+w_v
    assert a+i_s+i_v == f+e_s+e_v+w_s+w_v
    out['boundary_example'] = {'seed_batches': a, 'incoming_plants': i_v,
                               'outgoing_seeds': e_s, 'internal_crushing': f}
    out['status'] = 'PASS'
    (HERE / 'verification.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
