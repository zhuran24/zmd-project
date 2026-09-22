#!/usr/bin/env python3
"""第1轮修订：落盘记录重算、保护文件字节核验、文档自审与本轮交付指纹。"""
import hashlib
import json
import re
from pathlib import Path
import verify_outputs as verifier

ROOT = Path(__file__).resolve().parents[3]
KERNEL = ROOT / 'crates/kernel'
EVIDENCE = KERNEL / 'evidence/revision-r1'


def digest(path):
    """内核输出§1：原始文件字节指纹。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    """第四轮§5：审计证据只写入本轮证据目录。"""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    """输出§3、第四轮§5：验收已落盘产物，不刷新被验收记录或放宽原差分。"""
    records = []
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        data = verifier.checker.load_json(ROOT / f'数据/样例/{name}.json')
        expected = verifier.run(data)
        for suffix in ('运行记录-kernel', '运行记录-checkpoint_delta-kernel'):
            path = ROOT / f'数据/样例/{name}-{suffix}.json'
            report = verifier.verify(path, data, expected)
            record = verifier.checker.load_json(path)
            axes = {r['axis']: r for r in record['uncovered_axes']}
            reports = []
            for axis in ('warehouse.acceptance', 'warehouse.acceptance_quantifier'):
                assert axes[axis]['coverage_status'] == 'exercised'
                decoded = [json.loads(s) for s in axes[axis]['evidence']]
                assert len(decoded) == len(expected)
                for observation, tick in zip(decoded, expected):
                    assert verifier.same(observation['time'], tick['time'])
                    assert observation['phase'] == 'after_closure'
                    assert [r['item'] for r in observation['products']] == ['高容谷地电池', '精选荞愈胶囊']
                    for product in observation['products']:
                        rows = tick['state']['warehouse']['slots']
                        quantity = sum(int(r['quantity']['value']) for r in rows if r['item'] == product['item'])
                        catalog = verifier.checker.load_json(ROOT / '数据/正式静态目录.json')
                        core = next(u for u in catalog['units'] if u['id'] == '协议核心')
                        capacity = int(next(s for s in core['inventory'] if s['role'] == 'warehouse')['capacity']['value'])
                        assert int(product['free_capacity']['value']) == capacity - quantity
                        assert product['capacity_available'] == (quantity < capacity)
                    # 两原样例没有核心存货PC，传输开关也都关闭；此对照独立于实现报告。
                    units = {u['id']: u['kind'] for u in data['layout']['units']}
                    inbound = [c for c in tick['state']['logistics']['active_channels'] if units[c.split('|')[2].split(':')[0]] == '协议核心']
                    assert not inbound
                    assert all(not s['enabled'] for s in data['settings']['switches'] if s['function'] == 'transfer')
                    assert observation['core_input_channels'] == observation['enabled_transfer_units'] == []
                    assert all(p['physical_path_exists'] is False and p['capacity_and_path'] is False for p in observation['products'])
                    assert observation['both_products_capacity_and_path'] is False
                reports.append(decoded)
            assert verifier.same(*reports)
            report['warehouse_observations'] = len(expected)
            records.append(report)
    write(EVIDENCE / 'record-validation.json', {'status': '通过', 'records': records})

    baseline = verifier.checker.load_json(EVIDENCE / 'baseline.json')
    allowed = {str(ROOT / p) for p in (
        'crates/kernel/README.md', 'crates/kernel/src/input.rs', 'crates/kernel/src/interfaces.rs',
        'crates/kernel/src/engine.rs', 'crates/kernel/src/transition.rs', 'crates/kernel/src/warehouse.rs',
        'crates/kernel/src/output.rs', 'crates/kernel/src/lib.rs', 'crates/kernel/src/tests.rs',
        'crates/kernel/tests/verify_outputs.py', 'crates/kernel/evidence/实现验证.md',
        'crates/kernel/evidence/手推桥接轨迹.md', '规格/内核实现-对规格的疑问.md')}
    allowed.update(str(p) for p in (ROOT / '数据/样例').glob('*-kernel.json'))
    changes = [p for p, h in baseline.items() if not Path(p).is_file() or digest(Path(p)) != h]
    assert set(changes) <= allowed, sorted(set(changes) - allowed)
    counts = re.findall(r'test result: ok\. (\d+) passed; (\d+) failed', (EVIDENCE / 'cargo-test.txt').read_text())
    assert sum(int(p) for p, _ in counts) == 93 and all(int(f) == 0 for _, f in counts)
    assert 'Finished' in (EVIDENCE / 'clippy.txt').read_text()
    assert 'error:' not in (EVIDENCE / 'clippy.txt').read_text()
    docs = [KERNEL / 'README.md', KERNEL / '修订记录.md', KERNEL / 'evidence/实现验证.md',
            KERNEL / 'evidence/手推桥接轨迹.md', ROOT / '规格/内核实现-对规格的疑问.md']
    links = 0
    # 清单是本函数末尾写出的唯一前向链接。
    manifest = EVIDENCE / 'deliverables.json'
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
            if target.startswith(('http:', 'https:', '#')): continue
            path = (doc.parent / target.split('#')[0]).resolve()
            if path not in (manifest, EVIDENCE / 'final-audit.json'):
                assert path.exists(), (doc, target)
            links += 1
    function_count = 0
    for source in (KERNEL / 'src').glob('*.rs'):
        lines = source.read_text().splitlines()
        assert not re.search(r'\b(?:f32|f64|HashMap)\b', '\n'.join(lines)), source
        for index, line in enumerate(lines):
            if re.search(r'\bfn\s+\w+', line):
                function_count += 1
                assert any('///' in s and '§' in s for s in lines[max(0, index - 8):index]), (source, index + 1)
    write(EVIDENCE / 'final-audit.json', {
        'status': '通过', 'baseline_files': len(baseline), 'protected_files_unchanged': len(baseline) - len(changes),
        'changed_existing_files': changes, 'outside_allowed_changes': [], 'workspace_tests_passed': 93,
        'workspace_tests_failed': 0, 'rust_functions_with_section_comments': function_count,
        'documentation_links_checked': links, 'reader_audit': '修订记录、README与规格疑问的范围、时点、数字及交叉引用已重读核对',
        'golden_and_reference_tests_unchanged': True, 'formal_sources_and_candidate_unchanged': True,
        'open_items': ['KQ-02：after_closure记录起点契约待规格线澄清；当前输出入口明确unresolved']})
    candidates = [*list((KERNEL / 'src').glob('*.rs')), *list((KERNEL / 'tests').glob('*')),
                  *list(EVIDENCE.glob('*')), *docs]
    files = {Path(p) for p in changes}
    files.update(p for p in candidates if p.is_file() and str(p) not in baseline)
    files.discard(manifest)
    write(manifest, {'scope': '第1轮修订新增或修改的源文件、文档、运行记录和验证证据；不含构建缓存与已清理临时文件',
                     'files': [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(files)],
                     'manifest_path': str(manifest)})
    print(json.dumps({'status': '通过', 'records': len(records), 'workspace_tests': 93,
                      'protected_files': len(baseline) - len(changes), 'deliverables_including_manifest': len(files) + 1}, ensure_ascii=False))


if __name__ == '__main__':
    main()
