"""第2轮交付审计：重读真实产物、核保护字节与测试日志，登记本轮全部源交付文件。"""
import hashlib
import json
import re
from pathlib import Path
import verify_outputs as verifier

ROOT = Path(__file__).resolve().parents[3]
KERNEL = ROOT / 'crates/kernel'
OUT = KERNEL / 'evidence/revision-r2'


def digest(path):
    """内核输出§1：原始字节SHA-256，不对文本归一化。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    """第四轮§5：本轮证据独立于旧版本档案。"""
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def source_files():
    """第四轮§4–§5：构建缓存与临时文件不计为源交付物。"""
    return {p for p in ROOT.rglob('*') if p.is_file() and not any(
        part in ('target', '__pycache__', '.git') for part in p.relative_to(ROOT).parts)}


def main():
    """内核输出§3：所有校验必须通过才生成最终清单，不更新被核验记录。"""
    baseline = json.loads((OUT / 'baseline.json').read_text())
    allowed = {ROOT / name for name in (
        'crates/kernel/README.md', 'crates/kernel/修订记录.md',
        'crates/kernel/src/input.rs', 'crates/kernel/src/interfaces.rs',
        'crates/kernel/src/engine.rs', 'crates/kernel/src/event_identity.rs',
        'crates/kernel/src/polling.rs', 'crates/kernel/src/transition.rs',
        'crates/kernel/src/tests.rs', 'crates/kernel/src/tests_revision.rs',
        'crates/kernel/tests/verify_outputs.py', 'crates/kernel/tests/revision_cli.py',
        '规格/内核实现-对规格的疑问.md')}
    allowed.update((ROOT / '数据/样例').glob('*-kernel.json'))
    changed = {Path(p) for p, old in baseline.items() if not Path(p).is_file() or digest(Path(p)) != old}
    assert changed <= allowed, sorted(changed - allowed)
    new = {p for p in source_files() if str(p) not in baseline}
    assert all(p.is_relative_to(KERNEL) for p in new), sorted(p for p in new if not p.is_relative_to(KERNEL))
    protected = {Path(p) for p in baseline} - allowed
    assert all(p.is_file() and digest(p) == baseline[str(p)] for p in protected)
    assert digest(KERNEL / 'tests/reference.rs') == baseline[str(KERNEL / 'tests/reference.rs')]

    records = []
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        data = verifier.checker.load_json(ROOT / f'数据/样例/{name}.json')
        expected = verifier.run(data)
        for suffix in ('运行记录-kernel', '运行记录-checkpoint_delta-kernel'):
            records.append(verifier.verify(ROOT / f'数据/样例/{name}-{suffix}.json', data, expected))
    validation = json.loads((OUT / 'record-validation.json').read_text())
    assert verifier.same(records, validation['records'])
    generated = json.loads((OUT / 'regeneration.json').read_text())
    assert generated['binary_sha256'] == digest(Path(generated['binary']))
    assert {r['sha256'] for r in records} == {r['sha256'] for r in generated['records']}

    counts = re.findall(r'test result: ok\. (\d+) passed; (\d+) failed', (OUT / 'cargo-test.txt').read_text())
    assert sum(int(p) for p, _ in counts) == 102 and all(int(f) == 0 for _, f in counts)
    assert 'test result: FAILED' not in (OUT / 'cargo-test.txt').read_text()
    for name in ('clippy.txt', 'release-build.txt'):
        log = (OUT / name).read_text()
        assert 'Finished' in log and 'error:' not in log
    regression = json.loads((OUT / 'regression-results.json').read_text())
    assert regression['metadata_rejected'] == 64 and regression['input_case_count'] == 18
    assert all(not r['accepted'] for r in regression['metadata_mutations'])
    prior = json.loads((OUT / 'prior-regression-results.json').read_text())
    assert prior['metadata_negatives'] == 40 and prior['cli_negatives'] == 6 and prior['status'] == '通过'

    docs = [KERNEL / 'README.md', KERNEL / '修订记录.md', ROOT / '规格/内核实现-对规格的疑问.md']
    future = {OUT / 'final-audit.json', OUT / 'deliverables.json'}
    links = 0
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
            if target.startswith(('https:', 'http:', '#')):
                continue
            path = (doc.parent / target.split('#')[0]).resolve()
            assert path.exists() or path in future, (doc, target)
            links += 1
    findings = ['KR-r2-L1-01', 'KR-r2-L1-02', 'KR-r2-L1-03', 'KR-r2-L2-01',
                'KR-r2-L3-01', 'KR-r2-L3-02', 'KR-r2-L3-03', 'KR-r2-L3-04']
    revision = (KERNEL / '修订记录.md').read_text()
    assert all(f'| {name} |' in revision for name in findings)
    functions = 0
    for path in (KERNEL / 'src').glob('*.rs'):
        lines = path.read_text().splitlines()
        assert not re.search(r'\b(?:f32|f64|HashMap)\b', '\n'.join(lines)), path
        for index, line in enumerate(lines):
            if re.search(r'\bfn\s+\w+', line):
                functions += 1
                assert any('///' in s and '§' in s for s in lines[max(0, index - 8):index]), (path, index + 1)
    write('final-audit.json', {
        'status': '通过', 'baseline_files': len(baseline), 'protected_files_unchanged': len(protected),
        'changed_existing_files': [str(p) for p in sorted(changed)], 'outside_allowed_changes': [],
        'workspace_tests_passed': 102, 'workspace_tests_failed': 0,
        'original_golden_and_reference_bytes_unchanged': True,
        'formal_sources_and_candidate_bytes_unchanged': True,
        'prior_review_and_evidence_bytes_unchanged': True,
        'records_recomputed_and_verified': len(records), 'python_metadata_negatives': 60,
        'python_summary_controls': 4, 'rust_metadata_negatives': 32,
        'findings_addressed': findings, 'rust_functions_with_section_comments': functions,
        'documentation_links_checked': links,
        'reader_audit': '已重读README、按轮追记的修订记录与规格疑问；现行数字、历史时点、条件论证、停止范围及交叉引用一致。',
        'open_items': ['KQ-06：固定分支失活后的绑定及后继机制未定；当前明确unresolved，不交付不闭合后态。',
                       '既有KQ-01至KQ-05继续保留；尤其KQ-02的after_closure输出仍unresolved。']})
    manifest = OUT / 'deliverables.json'
    deliverables = changed | {p for p in source_files() if str(p) not in baseline}
    deliverables.discard(manifest)
    write('deliverables.json', {
        'scope': '第2轮新增/修改的源码、测试、夹具、文档、运行记录与证据；不含构建缓存、已清理临时文件，清单不自哈希。',
        'files': [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(deliverables)],
        'manifest_path': str(manifest)})
    print(json.dumps({'status': '通过', 'workspace_tests': 102, 'records': len(records),
                      'protected_files': len(protected), 'deliverables_including_manifest': len(deliverables) + 1}, ensure_ascii=False))


if __name__ == '__main__':
    main()
