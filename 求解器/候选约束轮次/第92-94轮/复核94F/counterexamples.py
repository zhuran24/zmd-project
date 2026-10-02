#!/usr/bin/env python3
"""复核 94F：候选一的两个读法反例，两套编码各跑一遍。

反例甲（带内前挪按「这一段自己被判定时」读）：仓库取货口 S -> 物品准入口 G -> 两格传送带段 D（末端没有通道）。
  G 送往 D，D 不往下送货，所以 G、D 都是层 1。D 的末格有一件已停满 1 tick 的物品、首格空；G 有一件已停满的物品。
  同层先后 D 先：D 前挪，G 送进 D；G 先：D 首格占着，G 送不出。
反例乙（第 31 行的「一个单位」对桥接器按整个单位读）：S1 -> 带 e1 -> 桥接器 R 的横轴 X -> 核心收货侧 K1；
  S2 -> 带 e2 -> R 的竖轴 Y -> 带 s -> 核心收货侧 K2。层数：X=1、e1=2；s=1、Y=2、e2=3。
  R 的收货组 {e1,e2} 在 e1（层 2）判定时一起判定；同在层 2 的 Y 先判定时 e2 能送进 Y，后判定时送不进。
"""
import json
import sys

from simp import Net, World
from simq import Q, canon_p


def ce_a():
    units = {
        'S': {'type': 'src', 'kinds': ['o1']},
        'G': {'type': 'gate', 'allow': None, 'q5': None},
        'D': {'type': 'seg', 'len': 2},
    }
    chans = [['S', 'G', 0], ['G', 'D', 1]]
    init = {'cell': {'G': [['o1', -8, None]], 'D': [['o1', -8, None], None]}}
    return {'units': units, 'chans': chans, 'init': init}, [['D', 'G'], ['G', 'D']], ['S']


def ce_b():
    units = {
        'S1': {'type': 'src', 'kinds': ['o1']},
        'S2': {'type': 'src', 'kinds': ['o2']},
        'e1': {'type': 'seg', 'len': 1},
        'e2': {'type': 'seg', 'len': 1},
        'X': {'type': 'bax', 'bridge': 'R'},
        'Y': {'type': 'bax', 'bridge': 'R'},
        's': {'type': 'seg', 'len': 1},
        'K1': {'type': 'sink', 'open': ('always',)},
        'K2': {'type': 'sink', 'open': ('always',)},
    }
    chans = [['S1', 'e1', 0], ['e1', 'X', 1], ['X', 'K1', 2], ['S2', 'e2', 3], ['e2', 'Y', 4], ['Y', 's', 5],
             ['s', 'K2', 6]]
    full = lambda k: [[k, -8, None]]
    init = {'cell': {'e1': full('o1'), 'e2': full('o2'), 'X': full('o1'), 'Y': full('o2'), 's': full('o2')}}
    return {'units': units, 'chans': chans, 'init': init}, [['s', 'X', 'e1', 'Y', 'e2'], ['s', 'X', 'Y', 'e1', 'e2']], ['S1', 'S2']


def run(desc, eorders, norder, settle, bg, steps=40):
    out = []
    for eo in eorders:
        net = Net(desc['units'], desc['chans'], bridge_group=bg)
        lays = {e: net.layer[e] for e in net.elems}
        w = World(net, desc['init'], settle=settle)
        q = Q(desc, settle=settle, bridge_group=bg)
        tr, agree = [], True
        for _ in range(steps):
            w.step(eo, norder)
            q.step(eo, norder)
            agree &= canon_p(w) == q.canon()
            tr.append(canon_p(w))
        out.append({'order': eo, 'layers': lays, 'two_codings_agree': agree,
                    'after_step0': repr(tr[0][1]), 'trace': tr})
    first_diff = next((k for k, (a, b) in enumerate(zip(out[0]['trace'], out[1]['trace'])) if a != b), None)
    for o in out:
        o.pop('trace')
    return {'first_diff_step': first_diff, 'runs': out}


def main():
    res = {}
    d, eos, no = ce_a()
    res['反例甲 eager'] = run(d, eos, no, 'eager', 'axis')
    res['反例甲 judge'] = run(d, eos, no, 'judge', 'axis')
    d, eos, no = ce_b()
    res['反例乙 axis'] = run(d, eos, no, 'eager', 'axis')
    res['反例乙 unit'] = run(d, eos, no, 'eager', 'unit')
    json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
    for k, v in res.items():
        print(k, '第一处不同的步:', v['first_diff_step'], '两套编码一致:', [r['two_codings_agree'] for r in v['runs']],
              '层数:', v['runs'][0]['layers'])
        for r in v['runs']:
            print('   ', r['order'], r['after_step0'])


if __name__ == '__main__':
    main()
