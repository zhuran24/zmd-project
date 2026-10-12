"""按规则 L17、L58、L74、L77 核验局部删行反例；不模拟 tick 或全厂。"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
RULE = Path('/home/zhuran24/zmd-research-fresh/《明日方舟：终末地》游戏规则.txt')
OPP = {'N': 'S', 'S': 'N', 'W': 'E', 'E': 'W'}
STEP = {'N': (0, -1), 'S': (0, 1), 'W': (-1, 0), 'E': (1, 0)}
units = [
    dict(id='A', type='machine', x=10, y=10, w=3, h=3),
    dict(id='B', type='machine', x=10, y=16, w=3, h=3),
    dict(id='C', type='machine', x=13, y=16, w=3, h=3),
    dict(id='power', type='power', x=7, y=11, w=2, h=2),
    dict(id='warehouse_port', type='source', x=0, y=14, w=1, h=3),
    dict(id='b', type='bridge', x=11, y=14, w=1, h=1),
]


def belt(name, x, y, incoming, outgoing):
    units.append(dict(id=name, type='belt', x=x, y=y, w=1, h=1,
                      incoming=incoming, outgoing=outgoing))


belt('t', 10, 13, 'N', 'S')
belt('c', 10, 14, 'N', 'E')
belt('steel12', 12, 14, 'W', 'E')
belt('steel13', 13, 14, 'W', 'E')
belt('steel_turn', 14, 14, 'W', 'S')
belt('steel_feed', 14, 15, 'N', 'S')
belt('d', 11, 15, 'N', 'S')
for x in range(1, 10):
    belt(f'ore{x}', x, 15, 'W', 'E')
belt('ore_turn', 10, 15, 'W', 'S')


def ports(u):
    x, y, name, kind = u['x'], u['y'], u['id'], u['type']
    result = []
    transport = kind in ('belt', 'bridge')

    def add(px, py, side, mode, storage):
        result.append((px, py, side, mode, storage, name, transport))

    if kind == 'machine':
        for dx in range(u['w']):
            add(x + dx, y, 'N', 'in', f'{name}.input')
            add(x + dx, y + u['h'] - 1, 'S', 'out', f'{name}.output')
    elif kind == 'belt':
        add(x, y, u['incoming'], 'in', name)
        add(x, y, u['outgoing'], 'out', name)
    elif kind == 'bridge':
        for side in OPP:
            storage = f'{name}.{side}_to_{OPP[side]}'
            add(x, y, side, 'in', storage)
            add(x, y, OPP[side], 'out', storage)
    elif kind == 'source':
        add(x, y + 1, 'E', 'out', name)
    return result


def geometry(us):
    occupied = {}
    for u in us:
        for x in range(u['x'], u['x'] + u['w']):
            for y in range(u['y'], u['y'] + u['h']):
                assert 0 <= x < 70 and 0 <= y < 70
                assert (x, y) not in occupied, ((x, y), u['id'], occupied.get((x, y)))
                occupied[x, y] = u['id']
    return occupied


def channels(us):
    all_ports = [p for u in us for p in ports(u)]
    ins = {(p[0], p[1], p[2]): p for p in all_ports if p[3] == 'in'}
    edges = set()
    for p in all_ports:
        if p[3] != 'out':
            continue
        dx, dy = STEP[p[2]]
        q = ins.get((p[0] + dx, p[1] + dy, OPP[p[2]]))
        if q and p[5] != q[5] and (p[6] or q[6]):
            edges.add((p[4], q[4]))
    return edges


def powered(us):
    p = next(u for u in us if u['type'] == 'power')
    cx, cy = p['x'] + 1, p['y'] + 1
    for u in us:
        if u['type'] == 'machine':
            assert max(u['x'], cx - 6) < min(u['x'] + u['w'], cx + 6)
            assert max(u['y'], cy - 6) < min(u['y'] + u['h'], cy + 6)


before = deepcopy(units)
grid_before = geometry(before)
assert {u for (x, y), u in grid_before.items() if y == 13} == {'t'}
assert next(u for u in before if u['id'] == 't')['incoming'] == 'N'
assert next(u for u in before if u['id'] == 't')['outgoing'] == 'S'
after = [dict(u, y=u['y'] - (u['y'] > 13)) for u in before if u['id'] != 't']
geometry(after)
powered(before)
powered(after)
edges_before, edges_after = channels(before), channels(after)
assert ('A.output', 'b.N_to_S') not in edges_before
assert ('A.output', 'b.N_to_S') in edges_after
for edges in (edges_before, edges_after):
    assert ('b.W_to_E', 'steel12') in edges
    assert ('b.N_to_S', 'd') in edges
    assert ('d', 'B.input') in edges
    assert ('ore_turn', 'B.input') in edges
expected_after = (edges_before - {('A.output', 't'), ('t', 'c')}) | {('A.output', 'c')}
assert edges_after - expected_after == {('A.output', 'b.N_to_S')}
result = dict(
    evidence_type='static_rule17_port_geometry_only_not_runtime_simulation',
    rule_file=str(RULE), rule_sha256=hashlib.sha256(RULE.read_bytes()).hexdigest(),
    deleted_row=13, row_contents={'10,13': 'N-to-S straight belt t', 'all_other_cells': 'empty'},
    no_overlap_and_within_70x70=True, machines_powered_before_and_after=True,
    before_units=before, after_units=after,
    channels_before=sorted(edges_before), channels_after=sorted(edges_after),
    new_channels_beyond_expected_contraction=sorted(edges_after - expected_after),
    unintended_path=['A.output', 'b.N_to_S', 'd', 'B.input'],
)
(HERE / '删行端口核验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('evidence_type', 'new_channels_beyond_expected_contraction',
                                      'no_overlap_and_within_70x70', 'machines_powered_before_and_after')}, ensure_ascii=False))
