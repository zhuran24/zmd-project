#!/usr/bin/env python3
"""复核94E 编码二：研磨机逐批换主料的确定性逐步模拟（绝对步号记账，不用年龄），检查最快循环是否每批 9 步（8/9 批/tick）。

两种主料 P1、P2 各一条存货通道，砂叶粉末一条存货通道；每条通道的末格由不断供货的上游补满（上游后判定，同步补入），
末格物品进格 8 步后才能送进研磨机。供料只放行下一批要用的主料（这是一种可能的来料时序，用来展示上界可达，不是布局）。
存货物品格两格、一格一种、同种只占一格、上限 50。开工在一步末，8 步后开头结束；上一批产物视作立即进取货格。
对照：新主料有两条通道时最快每批 8 步。
"""
import json
from fractions import Fraction


def run(p_channels=1, steps=2000):
    head = {('P1', i): 0 for i in range(p_channels)}
    head.update({('P2', i): 0 for i in range(p_channels)})
    head[('S', 0)] = 0
    cells = {}
    end = None
    need = 'P1'
    starts = []
    for t in range(8, steps):
        if end is not None and t >= end:
            end = None
        for key in sorted(head):
            kind = key[0]
            if t - head[key] < 8:
                continue
            if kind in ('P1', 'P2') and kind != need:
                continue
            if kind in cells:
                if cells[kind] >= 50:
                    continue
                cells[kind] += 1
            elif len(cells) < 2:
                cells[kind] = 1
            else:
                continue
            head[key] = t  # 上游同步补入新件
        if end is None and cells.get(need, 0) >= 2 and cells.get('S', 0) >= 1:
            cells[need] -= 2; cells['S'] -= 1
            for k in [k for k, v in cells.items() if v == 0]:
                del cells[k]
            end = t + 8
            starts.append(t)
            need = 'P2' if need == 'P1' else 'P1'
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    tail = gaps[len(gaps) // 2:]
    return dict(p_channels=p_channels, steady_gaps=sorted(set(tail)),
                rate_per_tick=str(Fraction(8 * len(tail), sum(tail))))


if __name__ == '__main__':
    out = [run(1), run(2)]
    print(out)
    json.dump(out, open(__file__.replace('.py', '.json'), 'w'), ensure_ascii=False, indent=1)
