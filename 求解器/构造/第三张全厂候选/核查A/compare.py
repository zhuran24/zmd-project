#!/usr/bin/env python3
"""互核：比对编码一（结果-主.json）与编码二（结果-副.json）的关键数字，写 互核.json。"""
import json, os, collections, sys
HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.environ.get('A_PATH') or os.path.join(HERE, '结果-主.json')))
B = json.load(open(os.environ.get('B_PATH') or os.path.join(HERE, '结果-副.json')))
norm = lambda s: s.replace('矿口:', 'outlet:').replace('核心:', 'core:')
rows = []
def cmp(name, a, b): rows.append({'项': name, '编码一': a, '编码二': b, '一致': a == b})
cmp('候选SHA-256', A['candidate_sha256'], B['candidate_sha256'])
cmp('占格总数', A['counts']['occupied_cells'], B['occupied'])
cmp('重建通道数', A['channels_rebuilt'], B['channels'])
cmp('声明通道与重建一致', not A['channels_undeclared'] and not A['channels_declared_not_real'], B['decl_equal'])
cmp('完成进路数', A['routes_complete'], B['routes'])
cmp('S2期望进路数', A['S2_expected_routes'], B['spec_total'])
cmp('缺路数', A['routes_missing_count'], B['missing'])
cmp('接法外进路', A['routes_extra'], B['extra'])
ma = sorted([norm(s), d] for s, d, k in A['routes_missing'] for _ in range(k))
cmp('缺路清单（逐条）', ma, B['missing_list'])
ra = sorted([r['src'], r['dst'], len(r['cells']), r['item']] for r in A['routes'])
cmp('完成进路清单（起点、终点、格数、物品）', ra, B['routes_list'])
cmp('进路上运输物品格数', sum(len(r['cells']) for r in A['routes']), B['transport_cells_on_routes'])
cmp('不在进路上的运输节点', A['orphan_transport_nodes'], B['nodes_not_on_route'])
cmp('桥接器数', A['counts']['bridges'], B['bridges'])
cmp('相邻桥对', A['adjacent_bridge_pairs'], B['adjacent_bridges'])
cmp('两轴非两条不同进路的桥', [b['bridge'] for b in A['bridges'] if not (b['H'] and b['V'] and b['H'] != b['V'])], B['bridges_not_two_distinct_routes'])
cmp('H6→F4格数', A['H6_F4_len'], B['H6_F4'])
cmp('Q6→F4格数', A['Q6_F4_len'], B['Q6_F4'])
cmp('无供电制造单位', A['unpowered_machines'], B['unpowered'])
cmp('最大空矩形(面积,短边)', [A['max_empty_rect']['area'], A['max_empty_rect']['short']] if A['max_empty_rect'] else None,
    [B['rect_hist']['area'], B['rect_hist']['short']] if B['rect_hist']['bounds'] else None)
cmp('最优空矩形全部位置', sorted(A['max_empty_rect_all']), sorted(B['rect_prefix_ties']))
cmp('前缀和穷举中更优的空矩形数', 0, B['rect_prefix_better_count'])
ok = all(r['一致'] for r in rows)
json.dump({'全部一致': ok, '项数': len(rows), '比对': rows}, open(os.environ.get('C_PATH') or os.path.join(HERE, '互核.json'), 'w'), ensure_ascii=False, indent=1)
for r in rows:
    if not r['一致'] or len(json.dumps(r['编码一'], ensure_ascii=False)) < 60:
        print(r['一致'], r['项'], json.dumps(r['编码一'], ensure_ascii=False)[:100], json.dumps(r['编码二'], ensure_ascii=False)[:100])
    else:
        print(r['一致'], r['项'], '(长清单)')
print('全部一致', ok, len(rows))
