#!/usr/bin/env python3
"""三审第 86—87 轮：双料机器两种原料各一条专用来路时不入「存货首件死锁」「研磨机两种主料占格」的穷举（本目录自写）。

配方从正式 游戏规则.txt 现读。对每台大制造单位的每个两料配方 aA＋bB：
两个存货物品格里只有 A、B（同种只占一格），件数 0—50 的全部组合；各存货通道上一个运输物品格的首件只可能是 A 或 B
（两条专用来路的首件都在时首件种类恰为 {A,B}，额外通道的首件也只是 A 或 B）；按正式「存货首件死锁」的定义判：凑不齐本机任何配方一批，且每个首件都收不下
（格里已有这种物品且满 50，或没有这种物品而两个格都有货）。预期 0 个。
对照：第 83 轮修正版被否的起态（源石粉末 1、砂叶粉末 50，此后只来蓝铁粉末、砂叶粉末）应判为死锁。
第 85 轮修正版的「它要做的每个配方」：研磨机只有一种主料时，两格里的物品能凑的配方只有一个。
"""
import json
import re
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RULES = (REPO / '《明日方舟：终末地》游戏规则.txt').read_text()


def parse_recipes():
    lines = RULES.split('\n')
    start = lines.index('配方')
    rec = {}
    cur = None
    for ln in lines[start + 1:]:
        ln = ln.strip()
        if not ln:
            continue
        if '→' not in ln:
            cur = ln
            rec[cur] = []
            continue
        lhs, rhs = ln.split('→')
        ins = [(int(n), it) for n, it in re.findall(r'(\d+)\s*([^\s＋+]+)', lhs)]
        rec[cur].append(ins)
    return rec


def rejects(grids, item):
    """grids: {物品: 件数>0}，至多两种。收不下：已有且满 50，或没有而两格都有货。"""
    if item in grids:
        return grids[item] >= 50
    return len(grids) >= 2


def can_batch(grids, recipes):
    return any(all(grids.get(it, 0) >= n for n, it in r) for r in recipes)


def main():
    rec = parse_recipes()
    big = {m: rs for m, rs in rec.items() if m in ('研磨机', '封装机', '灌装机')}
    assert len(big['研磨机']) == 3 and len(big['封装机']) == 1 and len(big['灌装机']) == 1, big
    out = {'recipes': {m: [[f'{n}{it}' for n, it in r] for r in rs] for m, rs in big.items()}, 'per_recipe': []}
    total_dead = 0
    for mach, rs in big.items():
        for r in rs:
            assert len(r) == 2
            (a, A), (b, B) = r
            states = dead = dead_one_type = 0
            for xa in range(51):
                for xb in range(51):
                    grids = {k: v for k, v in ((A, xa), (B, xb)) if v > 0}
                    states += 1
                    # 两条专用来路的首件都在：首件种类恰为 {A,B}（额外通道的首件也只是 A 或 B，不改变集合）
                    if not can_batch(grids, rs) and rejects(grids, A) and rejects(grids, B):
                        dead += 1
                    # 对照：若某种原料没有自己的通道，首件可以全是一种，这时会有死锁
                    for S in ((A,), (B,)):
                        if not can_batch(grids, rs) and all(rejects(grids, it) for it in S):
                            dead_one_type += 1
            makeable_types = sum(1 for rr in rs if {it for _, it in rr} <= {A, B})
            out['per_recipe'].append({'machine': mach, 'recipe': f'{a}{A}+{b}{B}', 'states': states,
                                      'deadlocks': dead,
                                      'control_deadlocks_if_first_items_one_type': dead_one_type,
                                      'recipes_using_only_these_two': makeable_types})
            total_dead += dead
    # 对照：第 83 轮修正版的反例
    g = {'源石粉末': 1, '砂叶粉末': 50}
    ctrl = (not can_batch(g, big['研磨机'])) and rejects(g, '蓝铁粉末') and rejects(g, '砂叶粉末')
    out['total_deadlocks'] = total_dead
    out['control_83_counterexample_is_deadlock'] = ctrl
    print(json.dumps(out, ensure_ascii=False, indent=1))
    assert total_dead == 0 and ctrl


if __name__ == '__main__':
    main()
