#!/usr/bin/env python3
"""独立重推复核：自行建依赖图，复用被审计数器仅作数值交叉验证。"""
import copy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def independent_edges(data, templates, strict):
    # 按独立稿的“可能读写”重新构造，未调用被审make_footprints/conflict_graph。
    kinds = {row['id']: row['kind'] for row in data['layout']['units']}
    endpoints = {row['id']: (row['source_port'], row['target_port'])
                 for row in data['layout']['physical_channels']}
    switches = {row['unit']: row['enabled'] for row in data['settings']['switches']
                if row['function'] == 'transfer'}

    def owner(port):
        return port.split(':')[0]

    def inventory(unit):
        return ('warehouse',) if kinds[unit] in ('协议核心', '仓库取货口') else ('inventory', unit)

    candidates = {inventory(owner(source)) for source, target in endpoints.values()
                  if kinds[owner(target)] == '物品准入口'}
    all_inventories = {inventory(owner(port)) for ports in endpoints.values() for port in ports}
    all_budgets = {('budget', port) for ports in endpoints.values() for port in ports}
    accesses = []
    for row in templates:
        action, target = row['operation'], row['target']
        reads, writes = set(), set()
        barrier = False
        if action == 'move':
            source_port, target_port = endpoints[target]
            source, destination = owner(source_port), owner(target_port)
            peers = [ports for ports in endpoints.values()
                     if owner(ports[0]) == source or owner(ports[1]) == destination]
            for ports in peers:
                reads.update(inventory(owner(port)) for port in ports)
                reads.update(('budget', port) for port in ports)
            sides = {('poll', source, 'output'), ('poll', destination, 'input')}
            reads.update(sides)
            writes.update(sides)
            writes.update((inventory(source), inventory(destination)))
            writes.update((('budget', source_port), ('budget', target_port)))
            barrier = kinds[destination] == '物品准入口'
            if strict:
                reads.update(all_inventories | all_budgets | {('derived',)})
                writes.add(('derived',))
        elif action == 'manufacture':
            reads.update((inventory(target), ('progress', target), ('pending', target)))
            writes.update(reads)
            if strict:
                reads.add(('pending_array',))
                writes.add(('pending_array',))
        elif action == 'transfer' and switches[target]:
            reads.update((inventory(target), ('progress', target), ('warehouse',)))
            writes.update(reads)
        barrier = barrier or bool(writes & candidates)
        accesses.append((reads, writes, barrier))

    edges = set()
    for left, right in itertools.combinations(range(len(accesses)), 2):
        lr, lw, lb = accesses[left]
        rr, rw, rb = accesses[right]
        if lb or rb or lw & (rr | rw) or rw & (lr | lw):
            edges.add((left, right))
    return edges


def stopped_pair():
    # 转移§4.2与§4.3第2步的局部投影；不是完整布局运行或可达性证据。
    initial = {'machine_input': 1, 'machine_phase': 'idle', 'machine_cache': 0,
               'box': {'高容谷地电池': 1, '精选荞愈胶囊': 1},
               'warehouse_species': [], 'empty_order': ['W0'], 'assigned_slots': ['W0']}

    def run(order):
        state = copy.deepcopy(initial)
        for action in order:
            if action == 'manufacture':
                state.update(machine_input=0, machine_phase='working', machine_cache=1)
            else:
                unknown = set(state['box']) - set(state['warehouse_species'])
                if len(unknown) >= 2 and set(state['empty_order']) & set(state['assigned_slots']):
                    return {'stop': 'unsupported(warehouse.empty_slot_identity, competing_new_species)',
                            'state': state}
        return {'state': state}

    left, right = run(['manufacture', 'transfer']), run(['transfer', 'manufacture'])
    return {'scope': '模板本体有停止时，停止前状态不交换；非完整输入验证',
            'left': left, 'right': right, 'same_state': left['state'] == right['state']}


def main():
    import sys
    sys.path.insert(0, str(HERE))
    counter = load_module('count_classes', HERE / 'count_classes.py')
    verifier = load_module('verify_reduction', HERE / 'verify_reduction.py')
    recorded = read_json(HERE / '等价类计数.json')
    current = counter.calculate()
    config = read_json(ROOT / '规格/内核配置-v1.json')
    config_axes = sorted(axis for axis, row in config['axes'].items()
                         if row['disposition'] == '由输入全称量化')
    declaration_axes = sorted(line.split('`')[1]
                              for line in (ROOT / '规格/受限模型声明.md').read_text().splitlines()
                              if line.startswith('| `') and '| 由输入全称量化 |' in line)
    document = (ROOT / '规格/参数扫描约减.md').read_text()
    assert config_axes == declaration_axes == sorted(counter.AXES)
    assert all('`' + axis + '`' in document for axis in config_axes)
    differences = []
    for source in recorded['sources']:
        actual = digest(Path(source['path']))
        if actual != source['sha256']:
            differences.append({**source, 'current_sha256': actual})
    without_sources_recorded = {k: v for k, v in recorded.items() if k != 'sources'}
    without_sources_current = {k: v for k, v in current.items() if k != 'sources'}
    same_counts = json.dumps(without_sources_recorded, sort_keys=True) == json.dumps(without_sources_current, sort_keys=True)
    assert same_counts
    rows = []
    for example in recorded['examples']:
        data = read_json(ROOT / '数据/样例' / (example['name'] + '.json'))
        for mode, graph in example['modes'].items():
            derived = independent_edges(data, [t['template'] for t in graph['templates']],
                                        mode == 'operational_conservative')
            expected = {tuple(edge) for edge in graph['edges']}
            assert derived == expected, (example['name'], mode, derived ^ expected)
            rows.append({'name': example['name'], 'mode': mode, 'edge_count': len(derived),
                         'pairs_checked': len(graph['pairs']), 'classes': graph['classes'],
                         'independent_graph_matches': True})
    brute = verifier.brute_checks()
    recipes = verifier.recipe_checks()
    probes = verifier.runtime_probes()
    lines = []
    original_write_text = Path.write_text

    def capture(self, data, *args, **kwargs):
        # 捕获生成清单到内存，绝不覆盖被审文件。
        assert self == HERE / '事件对清单.md'
        lines.append(data)
        return len(data)

    Path.write_text = capture
    try:
        counter.write_pairs(recorded)
    finally:
        Path.write_text = original_write_text
    assert lines == [(HERE / '事件对清单.md').read_text()]
    report = {'schema': 'independent-review-r1-v1', 'sources': current['sources'],
              'axis_registry_check': {'count': len(config_axes), 'axes': config_axes, 'status': 'passed'},
              'recorded_source_changes': differences, 'non_source_results_unchanged': same_counts,
              'independent_graphs': rows, 'pair_list_exact': True,
              'combinatorial_checks': brute, 'recipe_checks': recipes,
              'runtime_probes': probes, 'stop_prefix_probe': stopped_pair(),
              'scope': '依赖图独立重建；组合算法复跑；停止前缀为规格局部演算，未绕过完整输入校验'}
    path = HERE / '独立重推-r1-核验结果.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'graphs': rows, 'source_changes': len(differences),
                      'brute': brute, 'runtime': probes, 'result': str(path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
