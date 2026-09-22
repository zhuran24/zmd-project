"""第四轮覆盖复核：只读原产物，写入严格限于本证据目录。"""
import contextlib
import hashlib
import io
import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
SPEC = ROOT / '求解器/规格'
EXAMPLES = ROOT / '求解器/数据/样例'
REVISION = SPEC / '内核输入修订验证-r3'
TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
sys.path.insert(0, str(EXAMPLES))
import check_examples as checker
import check_golden_trace as golden
import runtime_example as runtime
import runtime_record as record
import test_runtime_input as tests


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    files = [SPEC / name for name in ('内核输入.md', '内核输出.md', '内核输出.schema.json',
             '内核输入-修订记录.md', '内核输入-对参数轴的修改请求.md', '运行语义.md', '受限模型声明.md',
             '受限转移定义.md', '内核配置-v1.json', '选择点参数轴.md', '选择点清单.md', '规则覆盖表.md',
             '参数轴-对内核输入请求的答复.md')]
    files += [p for p in EXAMPLES.iterdir() if p.is_file()]
    files += [p for p in REVISION.iterdir() if p.is_file()]
    files += [ROOT / name for name in checker.SOURCE_HASHES]
    files += [ROOT / '求解器/数据/正式静态目录.json', ROOT / '求解器/数据/送料契约.md']
    files += [TASKS / name for name in ('任务书3.md', '任务书.md', '任务书2.md')]
    files = sorted(set(files))
    before = {str(p): digest(p) for p in files}
    write_json(BASE / '复核起点指纹.json', before)
    summaries = []
    for path in files:
        raw = path.read_bytes()
        relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else Path('任务依据') / path.name
        target = BASE / '被审快照' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row = {'path': str(path), 'bytes': len(raw), 'lines': len(raw.splitlines())}
        if path.suffix == '.json':
            parsed = json.loads(raw)
            row['keys'] = list(parsed) if isinstance(parsed, dict) else None
        summaries.append(row)

    redirected = []
    original = Path.write_text
    def redirected_write(path, text, *args, **kwargs):
        path = path.resolve()
        if path.is_relative_to(BASE):
            return original(path, text, *args, **kwargs)
        if not path.is_relative_to(ROOT / '求解器'):
            raise AssertionError('拒绝复核目录外写入: ' + str(path))
        target = BASE / '重定向输出' / path.relative_to(ROOT / '求解器')
        target.parent.mkdir(parents=True, exist_ok=True)
        redirected.append({'requested': str(path), 'actual': str(target)})
        return original(target, text, *args, **kwargs)

    output = io.StringIO()
    with patch.object(Path, 'write_text', redirected_write), contextlib.redirect_stdout(output):
        docs = [checker.load_json(EXAMPLES / name) for name in checker.NAMES]
        examples = [checker.check(data, EXAMPLES / name) for data, name in zip(docs, checker.NAMES)]
        negatives = checker.negative_tests(docs)
        representations = checker.representation_tests(docs)
        tests.main()
        runpy.run_path(str(REVISION / 'build_output_schema.py'), run_name='__main__')
        runpy.run_path(str(REVISION / 'check_current_coverage.py'), run_name='__main__')
        data = checker.load_json(golden.INPUT)
        ticks = golden.run(data)
        actual = checker.load_json(golden.OUTPUT)
        assert record.validate_record(actual, data, ticks)
        assert record.validate_checkpoint(data, checker.load_json(REVISION / '中途种子.json'), 'J|2|0|1')
        sys.path.insert(0, str(ROOT / '求解器/数据/工具'))
        import formal_catalog
        formal_catalog.verify(checker.load_json(EXAMPLES.parent / '正式静态目录.json'))

    (BASE / '隔离复验.log').write_text(output.getvalue())
    assert (BASE / '重定向输出/规格/内核输出.schema.json').read_bytes() == (SPEC / '内核输出.schema.json').read_bytes()
    run_result = checker.load_json(BASE / '重定向输出/规格/内核输入修订验证-r3/运行回归结果.json')
    manifest = checker.load_json(REVISION / '交付清单.json')
    drift = [{'path': p, 'expected': sha, 'actual': digest(Path(p))} for p, sha in manifest['sha256'].items() if digest(Path(p)) != sha]
    values = runtime.axis_values(data)
    seed = data['initial_state']['nonwarehouse']['value']
    catalog = checker.load_json(EXAMPLES.parent / '正式静态目录.json')
    after = {str(p): digest(p) for p in files}
    assert before == after, '复核前后被审产物变化'
    write_json(BASE / '核验结果.json', {
        'status': '通过', 'files_read_and_snapshotted': len(files), 'file_inventory': summaries,
        'examples': examples, 'static_negatives': len(negatives), 'representation_regressions': len(representations),
        'runtime_regressions': len(run_result['tests']), 'axes': len(values),
        'all_axis_values_present': all(v['status'] in ('specified','derived') and v['value'] is not None for v in values.values()),
        'seed_inventory_rows': len(seed['inventory']), 'seed_progress_rows': len(seed['progress']),
        'seed_poll_sides': len(seed['logistics']['poll_memory']['value']['sides']),
        'catalog_units': len(catalog['units']), 'catalog_recipes': len(catalog['recipes']),
        'trace_full_replay_matches': True, 'schema_regeneration_matches': True,
        'completed_batches': actual['validation_scope']['manufacturing_cycles_completed'],
        'event_records_per_instant': [len(t['events']) for t in ticks],
        'source_assignment': next(r for r in data['settings']['warehouse_assignments'] if r['port'].startswith('ore_source:')),
        'warehouse_ore_per_instant': [t['summary']['warehouse_ore'] for t in ticks],
        'redirected_writes': redirected, 'delivery_manifest_drift': drift,
        'audited_files_unchanged': before == after,
        'scope': '独立调用现有检查器、记录完整比对及目录回源；不是独立规则执行器，也未重跑Cargo或候选B。'
    })
    print(json.dumps({'status': '通过', 'axes': len(values), 'runtime_tests': len(run_result['tests']), 'manifest_drift': len(drift), 'files': len(files)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
