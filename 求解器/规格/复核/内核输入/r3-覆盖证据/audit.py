#!/usr/bin/env python3
"""只读复核原产物；所有派生写入重定向到本复核目录。"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
EXAMPLES = ROOT / '求解器/数据/样例'
VALIDATION = ROOT / '求解器/规格/内核输入修订验证-r3'
sys.dont_write_bytecode = True
sys.path.insert(0, str(EXAMPLES))
import check_examples as checker
import check_golden_trace as golden
import generate_examples as generator
import test_runtime_input as runtime_tests


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    manifest = checker.load_json(VALIDATION / '交付清单.json')
    targets = [Path(p) for p in manifest['files']]
    sources = [ROOT / n for n in checker.SOURCE_HASHES]
    shared = [ROOT / '求解器/规格' / n for n in ('受限模型声明.md', '受限转移定义.md', '选择点参数轴.md', '选择点清单.md', '内核配置-v1.json', '运行语义.md')]
    shared.append(ROOT / '求解器/数据/正式静态目录.json')
    before = {str(p): digest(p) for p in targets + sources + shared}
    dump('复核起点指纹.json', before)
    manifest_changes = [p for p, h in manifest['artifact_sha256'].items() if digest(Path(p)) != h]
    documents = [checker.load_json(EXAMPLES / name) for name in checker.NAMES]
    checks = [checker.check(d, EXAMPLES / n) for d, n in zip(documents, checker.NAMES)]
    negatives = checker.negative_tests(documents)
    representations = checker.representation_tests(documents)
    actual = golden.run(documents[2])
    expected = checker.load_json(golden.GOLDEN)
    old_output = checker.load_json(golden.OUTPUT)
    assert [r['summary'] for r in actual] == expected['ticks']
    assert actual == old_output['trace']['ticks']
    schema = checker.load_json(ROOT / '求解器/规格/内核输出.schema.json')
    runtime_tests.validate_schema(old_output, schema, schema)
    dump('重算完整轨迹.json', actual)

    # 不改写生成器和测试；拦截其现有写函数，保留逐字生成结果。
    original_write = Path.write_text
    redirected = []
    def capture_write(path, content, *args, **kwargs):
        path = path.resolve()
        assert path in targets, '意外写路径：' + str(path)
        destination = HERE / ('重生-' + path.name)
        redirected.append({'source': str(path), 'saved': str(destination), 'identical_bytes': content.encode('utf-8') == path.read_bytes()})
        return original_write(destination, content, *args, **kwargs)
    console = io.StringIO()
    with patch.object(Path, 'write_text', capture_write), contextlib.redirect_stdout(console):
        generator.main()
        golden.main()
        runtime_tests.main()
        runpy.run_path(str(VALIDATION / 'build_output_schema.py'))
    (HERE / '隔离重跑.log').write_text(console.getvalue())

    catalog = checker.load_json(ROOT / '求解器/数据/正式静态目录.json')
    sys.path.insert(0, str(ROOT / '求解器/数据/工具'))
    import formal_catalog
    formal_catalog.verify(catalog, ROOT)

    params = {k: v for g in ('fixed', 'offline_mutable', 'fixedness_unproven') for k, v in documents[2]['parameters'][g].items()}
    added = {'polling.split_merge_scope', 'polling.split_merge_singleton', 'polling.both_failure', 'connection.belt_shape', 'initialization.belt_shape_lifecycle'}
    assert len(params) == 96 and len(set(params) - added) == 91
    assert all(v['status'] in ('specified', 'derived') and v['value'] is not None for v in params.values())
    projection = checker.load_json(EXAMPLES / 'kernel_profile_v1参数赋值.json')
    assert {r['axis']: r['decision'] for r in projection['axes']} == params
    seed = documents[2]['initial_state']['nonwarehouse']['value']
    source_row = next(r for r in documents[2]['settings']['warehouse_assignments'] if r['port'] == 'ore_source:north:1')
    source_slot = next(r for r in seed['warehouse']['slots'] if r['slot'] == source_row['slot'])
    assert source_slot['item'] == '源矿' and checker.quantity(source_slot['quantity']) == 80000

    # 从目录边对独立检查三种形状乘四朝向，避免沿用生成器的形状名字。
    belt = next(u for u in catalog['units'] if u['id'] == '传送带')
    direction = {'east': 0, 'north': 1, 'west': 2, 'south': 3}
    pairs = set()
    shape_orbits = []
    for layout in belt['ports']['layouts']:
        a = direction[next(e['side'] for e in layout if e['role'] == 'input')]
        b = direction[next(e['side'] for e in layout if e['role'] == 'output')]
        shape_orbits.append((b - a) % 4)
        pairs.update(((a + r) % 4, (b + r) % 4) for r in range(4))
    assert pairs == {(a, b) for a in range(4) for b in range(4) if a != b}

    protected = checker.load_json(VALIDATION / '只读指纹.json')
    protected_changes = [p for p, h in protected.items() if not Path(p).is_file() or digest(Path(p)) != h]
    parsed = []
    for path in targets:
        if path.suffix == '.json':
            value = checker.load_json(path)
            parsed.append({'path': str(path), 'top_type': type(value).__name__, 'top_size': len(value)})
    changes = [p for p, h in before.items() if digest(Path(p)) != h]
    assert not changes
    result = {
        'status': '通过', 'manifest_fingerprint_changes': manifest_changes,
        'checks': checks, 'negative_count': len(negatives), 'representation_count': len(representations),
        'negatives': negatives, 'representations': representations,
        'runtime_regression': checker.load_json(HERE / '重生-运行回归结果.json'),
        'redirected_writes': redirected, 'golden_summary_match': True, 'full_trace_match': True,
        'axis_count': len(params), 'original_axis_count': len(set(params) - added),
        'decision_status_counts': {s: sum(v['status'] == s for v in params.values()) for s in ('specified', 'derived')},
        'seed_inventory_slots': len(seed['inventory']), 'seed_progress_count': len(seed['progress']),
        'seed_poll_sides': len(seed['logistics']['poll_memory']['value']['sides']),
        'source_slot': source_slot, 'belt_relative_directions': shape_orbits, 'belt_directed_pair_count': len(pairs),
        'formal_catalog': '当前工具回源核验通过', 'parsed_json': parsed,
        'protected_manifest_count': len(protected), 'protected_manifest_changes': protected_changes,
        'reviewed_file_changes_during_run': changes,
        'scope': '当前样例和有限轨迹复验；非一般语义、全部初态或全称认证'
    }
    dump('核验结果.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'axis_count', 'original_axis_count', 'negative_count', 'representation_count', 'golden_summary_match', 'full_trace_match', 'protected_manifest_count', 'protected_manifest_changes', 'reviewed_file_changes_during_run')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
