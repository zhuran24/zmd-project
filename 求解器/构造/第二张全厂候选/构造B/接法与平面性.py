#!/usr/bin/env python3
"""逐项展开推导98S2第2节；检查所有边界来源同在外面的平面性必要条件。

不是布局生成器。EXT 只是基地外侧的证明辅助顶点，不是游戏单位。
只在本文件目录写结果。使用 python3 -B，单线程。
"""
import hashlib
import json
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
SNAP = ROOT / '求解器/候选约束轮次/第98-100轮/前提快照'
S2 = ROOT / '求解器/候选约束轮次/第98-100轮/推导98S2.md'


def dump(name, obj):
    path = BASE / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_contract():
    machines, sources, feeds = [], [], []

    def machine(uid, model, recipe, rate, label):
        machines.append(dict(id=uid, model=model, recipe_id=recipe,
                             batch_rate=str(Q(rate)), label=label))

    def feed(a, b, item, rate=1, source_port=None):
        row = dict(id=f'L{len(feeds)+1:03d}', source=a, target=b,
                   item=item, rate=str(Q(rate)))
        if source_port is not None:
            row['source_port_index'] = source_port
        feeds.append(row)

    for j in range(1, 35):
        sources.append(dict(id=f'OB{j}', kind='仓库取货口', item='蓝铁矿'))
        machine(f'T{j}', '精炼炉', '精炼-蓝铁矿', 1, f'第{j}台蓝铁矿精炼炉')
        machine(f'KB{j}', '粉碎机', '粉碎-蓝铁块', 1, f'第{j}台蓝铁块粉碎机')
        feed(f'OB{j}', f'T{j}', '蓝铁矿')
        feed(f'T{j}', f'KB{j}', '蓝铁块')
        feed(f'KB{j}', f'B{(j+1)//2}', '蓝铁粉末')
    for j in range(1, 19):
        machine(f'U{j}', '粉碎机', '粉碎-源矿', 1, f'第{j}台源矿粉碎机')
        if j <= 6:
            feed('CORE', f'U{j}', '源矿', source_port=j-1)
        else:
            sources.append(dict(id=f'OO{j}', kind='仓库取货口', item='源矿'))
            feed(f'OO{j}', f'U{j}', '源矿')
        feed(f'U{j}', f'O{(j+1)//2}', '源石粉末')
    for j in range(1, 18):
        machine(f'B{j}', '研磨机', '研磨-致密蓝铁', 1, f'B{j}：蓝铁粉末研磨机')
        machine(f'R{j}', '精炼炉', '精炼-致密蓝铁', 1, f'R{j}：致密蓝铁粉末精炼炉')
        feed(f'B{j}', f'R{j}', '致密蓝铁粉末')
        target = f'P{j}' if j <= 6 else f'H{(j-7)//2+1}'
        feed(f'R{j}', target, '钢块')
    for j in range(1, 10):
        machine(f'O{j}', '研磨机', '研磨-致密源石', 1, f'O{j}：源石粉末研磨机')
        feed(f'O{j}', f'E{(j-1)//3+1}', '致密源石粉末')
    for j in range(1, 7):
        machine(f'P{j}', '配件机', '配件-钢制零件', 1, f'P{j}：配件机')
        machine(f'H{j}', '塑形机', '塑形-钢质瓶', Q(1, 2) if j == 6 else 1,
                f'H{j}：塑形机')
        machine(f'Q{j}', '研磨机', '研磨-细磨荞花', Q(1, 2) if j == 6 else 1,
                f'Q{j}：荞花粉末研磨机')
        feed(f'P{j}', f'E{(j-1)//2+1}', '钢制零件')
        f = (j-1)//2+1 if j <= 4 else j-2
        feed(f'H{j}', f'F{f}', '钢质瓶', Q(1, 2) if j == 6 else 1)
        feed(f'Q{j}', f'F{f}', '细磨荞花粉末', Q(1, 2) if j == 6 else 1)
    for j in range(1, 4):
        machine(f'E{j}', '封装机', '封装-电池', Q(1, 5), f'E{j}：封装机')
        feed(f'E{j}', 'CORE', '高容谷地电池', Q(1, 5))
    for j, rate in enumerate([Q(1, 5), Q(1, 5), Q(1, 10), Q(1, 20)], 1):
        machine(f'F{j}', '灌装机', '灌装-胶囊', rate, f'F{j}：灌装机')
        feed(f'F{j}', 'CORE', '精选荞愈胶囊', rate)
    sand = [
        ['B1', 'B2', 'O1'], ['O2', 'O3'],
        ['B3', 'B4', 'O4'], ['O5', 'O6'],
        ['B5', 'B6', 'O7'], ['O8', 'O9'],
        ['B7', 'B8', 'B9'], ['B10', 'Q1', 'Q2'],
        ['B11', 'B12', 'B13'], ['B14', 'Q3', 'Q4'],
        ['B15', 'B16', 'Q5'], ['B17'], ['Q6'],
    ]
    for species, prefix, count in [('砂叶', 'S', 13), ('荞花', 'Q', 6)]:
        for j in range(1, count+1):
            crusher = f'S{j}' if species == '砂叶' else f'KQ{j}'
            if species == '砂叶':
                amount = sum(Q(1, 2) if t == 'Q6' else Q(1) for t in sand[j-1])
                rate = amount / 3
            else:
                rate = Q(1, 2) if j == 6 else Q(1)
            a, b, c = f'{prefix}A{j}', f'{prefix}B{j}', f'{prefix}C{j}'
            for uid in (a, b):
                machine(uid, '种植机', '种植-'+species, rate, f'{species}单元{j}的种植机{uid}')
            machine(c, '采种机', '采种-'+species, rate, f'{species}单元{j}的采种机')
            machine(crusher, '粉碎机', '粉碎-'+species, rate, f'{species}单元{j}的粉碎机')
            feed(c, a, species+'种子', rate)
            feed(c, b, species+'种子', rate)
            feed(a, c, species, rate)
            feed(b, crusher, species, rate)
            if species == '砂叶':
                for t in sand[j-1]:
                    feed(crusher, t, '砂叶粉末', Q(1, 2) if t == 'Q6' else 1)
            else:
                for _ in range(1 if j == 6 else 2):
                    feed(crusher, f'Q{j}', '荞花粉末')
    counts = dict(Counter(m['model'] for m in machines))
    assert len(machines) == 230 and len(feeds) == 325 and len(sources) == 46
    assert counts == {'粉碎机':71, '精炼炉':51, '研磨机':32, '配件机':6,
                      '塑形机':6, '封装机':3, '灌装机':4, '种植机':38, '采种机':19}
    assert len({m['id'] for m in machines}) == 230
    return dict(schema='s2-logical-contract-v1', is_layout=False,
                source=str(S2.relative_to(ROOT)), machines=machines,
                boundary_sources=sources, core=dict(id='CORE', kind='协议核心'),
                feeds=feeds, machine_counts=counts,
                geometry_requirements=dict(W=70, H=70, pure_belts=True,
                                           minimum_transport_cells_per_feed=1,
                                           disjoint_transport_cells=True,
                                           no_extra_channels=True,
                                           equal_lengths=[['H6', 'F4'], ['Q6', 'F4']]))


def blue(j, b):
    return ['EXT', f'OB{j}', f'T{j}', f'KB{j}', b]


def witnesses():
    result = []
    for s, e, a, b, o, p, q, u in [
        (3, 2, 3, 4, 4, 3, 4, 7), (5, 3, 5, 6, 7, 5, 6, 13)
    ]:
        left, right = ['EXT', f'S{s}', f'E{e}'], [f'B{a}', f'B{b}', f'O{o}']
        paths = [blue(2*a-1, right[0]), blue(2*b-1, right[1]),
                 ['EXT', f'OO{u}', f'U{u}', right[2]]]
        paths += [[left[1], v] for v in right]
        paths += [[left[2], f'P{p}', f'R{a}', right[0]],
                  [left[2], f'P{q}', f'R{b}', right[1]], [left[2], right[2]]]
        result.append(dict(id=f'封装机{e}_砂叶粉碎机{s}', left=left, right=right, paths=paths))
    for s, f, a, h in [(7, 1, 7, 1), (9, 2, 11, 3)]:
        left = ['EXT', f'S{s}', f'H{h}']
        right = [f'B{a+j}' for j in range(3)]
        paths = [blue(2*(a+j)-1, right[j]) for j in range(3)]
        paths += [[left[1], v] for v in right]
        paths += [[left[2], f'R{a}', right[0]], [left[2], f'R{a+1}', right[1]],
                  [left[2], f'F{f}', f'H{h+1}', f'R{a+2}', right[2]]]
        result.append(dict(id=f'灌装机{f}_砂叶粉碎机{s}', left=left, right=right, paths=paths))
    return result


def run():
    import networkx as nx
    contract = make_contract()
    digest = dump('S2接法.json', contract)
    certs = witnesses()
    dump('不可平面布线证书.json', dict(schema='s2-boundary-k33-v1',
         contract_sha256=digest, exterior_vertex='EXT',
         exterior_edges=[['EXT', s['id']] for s in contract['boundary_sources']],
         witnesses=certs))
    graph = nx.Graph()
    graph.add_nodes_from(m['id'] for m in contract['machines'])
    graph.add_nodes_from(s['id'] for s in contract['boundary_sources'])
    graph.add_node('CORE')
    graph.add_edges_from((f['source'], f['target']) for f in contract['feeds'])
    internal = nx.check_planarity(graph)[0]
    augmented = graph.copy()
    augmented.add_edges_from(('EXT', s['id']) for s in contract['boundary_sources'])
    exterior = nx.check_planarity(augmented)[0]
    individual = []
    for c in certs:
        g = nx.Graph()
        g.add_edges_from((a, b) for p in c['paths'] for a, b in zip(p, p[1:]))
        assert all(augmented.has_edge(a, b) for a, b in g.edges())
        planar, _ = nx.check_planarity(g)
        individual.append(dict(id=c['id'], vertices=len(g), edges=g.number_of_edges(),
                               planar=planar, subgraph_of_augmented=True))
    result = dict(checker='networkx-planarity', version=nx.__version__,
                  contract_sha256=digest, machine_count=230, feed_count=325,
                  boundary_outlet_count=46, internal_graph_planar=internal,
                  graph_with_exterior_planar=exterior,
                  graph_vertices=len(augmented), graph_edges=augmented.number_of_edges(),
                  witnesses=individual, all_four_nonplanar=all(not c['planar'] for c in individual),
                  static_pass=False, layout_exists=False,
                  conclusion='S2纯带接法违反边界平面性必要条件，无几何候选。')
    dump('平面性复核.json', result)
    paths = [SNAP / n for n in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']]
    paths += [S2, ROOT / '求解器/构造/第一张全厂候选/格式.md']
    dump('输入指纹.json', [dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
