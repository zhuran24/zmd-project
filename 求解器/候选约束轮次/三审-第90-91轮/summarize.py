#!/usr/bin/env python3
"""把 out/ 下 exhaust.py、phase_sim.py 的输出汇总成 out/summary.json。"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'out'


def main():
    ex = {}
    for f in sorted(OUT.glob('ex_*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        ex[d['组']] = {k: d[k] for k in ('说明', 'Q', '存货上限', '随机起态', '状态数', '前提成立的状态',
                                         '前提子图中在环上的状态', '违反', '见证环长')}
    normal = [json.loads(f.read_text(encoding='utf-8')) for f in sorted(OUT.glob('phase_normal_*.json'))]
    keys = ['runs', 'cycles', 'premise_cycles', 'multi_phase', 'five_tick', 'with_Y', 'input_full',
            'x_empty_cycles', 'line_empty_cycles', 'yfirst_empty_cycles', 'mojv_cycles', 'xfirst_empty_cycles',
            'windows', 'window_viol']
    ph = {k: sum(d[k] for d in normal) for k in keys}
    ph['batches'] = len(normal)
    ph['violating_seeds'] = sum((d['violating_seeds'] for d in normal), [])
    ctrl = {}
    for f in sorted(OUT.glob('phase_control_*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        ctrl[d['mode']] = d
    main_ok = all(sum(v['违反'].values()) == 0 for k, v in ex.items() if k.startswith('C'))
    ctrl_ok = all(sum(v['违反'].values()) > 0 for k, v in ex.items() if k.startswith('K'))
    res = dict(exhaust=ex, exhaust_main_all_zero=main_ok, exhaust_controls_all_caught=ctrl_ok,
               phase_normal=ph, phase_controls=ctrl)
    (OUT / 'summary.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
