"""2026-09-22g 目录同步与审计；从 run.sh 以 bash 显式执行。"""
import ast
import copy
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from guard import OUT, ROOT, REPO, SOURCES, HISTORY, save, digest, guard, difference, run

CATALOG = ROOT / '数据/正式静态目录.json'
OLD_SHA = 'bfbee742587e8e9a08c8231483bef578ee4494450447d0d783466cc28b29dd7a'
OLD_SOURCE_SHA = 'a67c18dec5f6ae59c41e8620d270007f20c2d3e5b202521d0cca12f616bca3df'
VERSION = '2026-09-22-r24-constraints-72'
PREVIOUS = ROOT / '内核维护/2026-09-22e'
sys.path.insert(0, str(ROOT / '数据/工具'))
from formal_catalog import source_snapshot, formal_projection, verify

def load(path):
    return json.loads(path.read_text())

def previous_paths():
    return {Path(row['path']) for row in load(PREVIOUS / 'resume/changed-files.json')['business_files']}

def scan(label):
    argv = ['rg', '--hidden', '--no-ignore', '-l', '-0', '-F',
            '-e', OLD_SHA, '-e', OLD_SOURCE_SHA,
            '-g', '!.git/**', '-g', '!**/target/**', '-g', '!**/__pycache__/**',
            '-g', '!**/.cargo-home/**', '-g', '!求解器/几何/1113流量层/**',
            '-g', '!求解器/构造/**', '-g', '!scratchpad/**', '-g', '!**/scratchpad/**', '.']
    result = subprocess.run(argv, cwd=REPO, capture_output=True)
    assert result.returncode in (0, 1), result.stderr.decode()
    paths = sorted(Path(p).as_posix().removeprefix('./') for p in result.stdout.decode().split('\0') if p)
    rows = []
    prior = previous_paths()
    for relative in paths:
        if any(relative.startswith('求解器/' + p + '/') for p in HISTORY):
            category = 'protected_history'
        elif relative.startswith('求解器/内核维护/2026-09-22g/'):
            category = 'this_run_record_or_negative'
        elif relative.startswith(('求解器/内核维护/', '求解器/规格/复核/')):
            category = 'archived_record'
        elif (REPO / relative) in prior:
            category = 'previous_scope'
        elif relative.startswith('求解器/crates/kernel/tests/fixtures/'):
            category = 'additional_active_fixture'
        else:
            category = 'review_needed'
        rows.append({'path': relative, 'category': category})
    value = {'argv': argv, 'exit_code': result.returncode, 'excluded': ['.git', 'target', '__pycache__', '.cargo-home',
             '求解器/几何/1113流量层', '求解器/构造', 'scratchpad'],
             'counts': dict(Counter(r['category'] for r in rows)), 'files': rows}
    save(label + '-old-sha-inventory.json', value)
    return value

def inspect():
    assert digest(CATALOG) == OLD_SHA
    inventory = scan('before')
    catalog = load(CATALOG)
    snapshot = source_snapshot()
    projection = formal_projection(snapshot)
    changes = [{'index': i, 'before': old, 'after': new} for i, (old, new) in
               enumerate(zip(catalog['constraints'], projection['constraints'])) if old != new]
    prior = previous_paths()
    summary = {'catalog_version': catalog['version'], 'old_catalog_sha256': OLD_SHA,
               'current_sources': {s['path']: s['sha256'] for s in snapshot},
               'constraints': len(projection['constraints']), 'constraint_changes': changes,
               'old_sha_inventory_counts': inventory['counts'],
               'needs_review': [r['path'] for r in inventory['files'] if r['category'] == 'review_needed'],
               'previous_scope_matches': [r['path'] for r in inventory['files'] if r['category'] in ['previous_scope', 'additional_active_fixture']]}
    save('inspection.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def serialized(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()

def sync():
    guard('sync-before')
    assert not (OUT / 'sync-changes.json').exists()
    assert digest(CATALOG) == OLD_SHA
    before = load(CATALOG)
    current = copy.deepcopy(before)
    current['sources'] = source_snapshot()
    projection = formal_projection(current['sources'])
    current.update(projection)
    current['version'] = VERSION
    verify(current)
    assert len(before['constraints']) == len(current['constraints']) == 72
    assert [i for i, (a, b) in enumerate(zip(before['constraints'], current['constraints'])) if a != b] == [32]
    old_rule, new_rule = before['constraints'][32], current['constraints'][32]
    assert old_rule['name'] == new_rule['name'] == '传输按仓库余量判定'
    removed = '；仓库已经满格且不会再出库的非成品，不因开启传输而被禁止经箱子的物理端口中转'
    assert new_rule['text'] == old_rule['text'].replace(removed, '')
    assert {k: v for k, v in old_rule.items() if k != 'text'} == {k: v for k, v in new_rule.items() if k != 'text'}
    for key in ['task', 'units', 'recipes', 'static_checks']:
        assert before[key] == current[key], key
    plan = {CATALOG: serialized(current)}
    import hashlib
    new_sha = hashlib.sha256(plan[CATALOG]).hexdigest()
    source_sha = current['sources'][2]['sha256']
    inputs = []
    for base in [ROOT / '数据/样例', ROOT / 'crates/kernel/tests/fixtures']:
        for path in sorted(base.rglob('*.json')):
            obj = load(path)
            if isinstance(obj, dict) and obj.get('schema') in ['kernel-input-v2', 'kernel-input-v3']:
                assert obj['catalog']['sha256'] == OLD_SHA, path
                assert (path.parent / obj['catalog']['path']).resolve() == CATALOG, path
                updated = copy.deepcopy(obj)
                updated['catalog']['sha256'] = new_sha
                # Preserve all bytes except this exact fingerprint.
                data = path.read_bytes().replace(OLD_SHA.encode(), new_sha.encode())
                assert json.loads(data) == updated, path
                plan[path] = data
                inputs.append(str(path.relative_to(ROOT)))
    assert len(inputs) == 54
    sources_path = ROOT / '数据/候选B/来源清单.json'
    sources = load(sources_path)
    new_sources = copy.deepcopy(sources)
    for ref in new_sources:
        if Path(ref['path']) == CATALOG:
            ref['sha256'] = new_sha
        elif Path(ref['path']) == REPO / '求解约束.txt':
            ref['sha256'] = source_sha
        else:
            assert digest(Path(ref['path'])) == ref['sha256'], ref
    assert len(sources) == 16
    plan[sources_path] = serialized(new_sources)

    def replace(path, pairs):
        text = path.read_text()
        for old, new in pairs:
            assert text.count(old) == 1, (path, old, text.count(old))
            text = text.replace(old, new)
        plan[path] = text.encode()

    replace(ROOT / '数据/样例/check_examples.py', [(OLD_SOURCE_SHA, source_sha)])
    replace(ROOT / '规格/运行语义.md', [(OLD_SOURCE_SHA, source_sha)])
    replace(ROOT / '规格/check_revision.py', [('内核维护/2026-09-22e/只读文件指纹.json', '内核维护/2026-09-22g/只读文件指纹.json')])
    replace(ROOT / '数据/候选B/校验报告.md', [(before['version'], VERSION), (old_rule['text'], new_rule['text'])])
    replace(ROOT / '数据/候选B/验证记录.md', [(before['version'], VERSION),
        ('当前执行与限制见[2026-09-22e 记录](../../内核维护/2026-09-22e/记录.md)',
         '目录重锁与本轮安全验证见[2026-09-22g 记录](../../内核维护/2026-09-22g/记录.md)；报告本輪仅同步目录版本和条文原文，检查计数沿用[2026-09-22e 执行记录](../../内核维护/2026-09-22e/记录.md)'.replace('本輪', '本轮'))])
    revisions = ROOT / '规格/修订记录.md'
    addition = f'''\n## 2026-09-22 r24：传输按仓库余量判定措辞同步\n\n依据提交 `dfc35cd` 的现行三份正式文件，使用 `数据/工具/formal_catalog.py` 的回源投影重建目录。目录版本 `{VERSION}`，SHA-256 `{new_sha}`；约束仍为 72 条。\n\n| 文件 | SHA-256 |\n|---|---|\n'''
    addition += ''.join(f"| {s['path']} | `{s['sha256']}` |\n" for s in current['sources'])
    addition += '''\n「传输按仓库余量判定」删去末尾关于满格非成品经箱子物理端口中转的半句，句末改为句号。目录的约束正文及正式来源全文两处同步；任务、18 类单位、18 条配方、32 项常量和 19 项物料流量均不变。54 份内核输入（45 个样例、9 个 fixture）只重锁目录 SHA；候选 B 来源清单的正式约束与目录两项、样例来源校验、运行语义来源 SHA、规格自查的只读快照入口同步。候选 B 当前报告只更新目录版本及原文，未另跑 topology CLI；计数沿用 r23 执行记录。\n\n本轮执行记录及最终安全测试结果见[2026-09-22g 记录](../内核维护/2026-09-22g/记录.md)。本节不修改旧轮记录与历史证据，不登记为规格总自查通过；T12 断言、桥轴 Decision 结构与两处实现状态文字问题保留。\n'''
    assert '\n## 2026-09-22 r24' not in revisions.read_text()
    plan[revisions] = revisions.read_bytes() + addition.encode()
    allowed = previous_paths() | {ROOT / 'crates/kernel/tests/fixtures/benchmark_candidate_b.json'}
    assert set(plan) <= allowed
    initial = load(OUT / 'initial-active.json')
    rows = []
    for path, content in plan.items():
        relative = str(path.relative_to(REPO))
        assert digest(path) == initial[relative], '活动文件已经发生并发变动：' + relative
        backup = OUT / 'before' / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(path.read_bytes())
        rows.append({'path': relative, 'before_sha256': digest(path),
                     'after_sha256': hashlib.sha256(content).hexdigest(),
                     'previous_scope': path in previous_paths()})
    save('sync-plan.json', rows)
    save('只读文件指纹.json', {str(REPO / p): digest(REPO / p) for p in [*SOURCES, '候选约束.txt']})
    # All content and authorization checks above precede the first business write.
    for path, content in plan.items():
        path.write_bytes(content)
    save('sync-changes.json', {'version': VERSION, 'catalog_sha256': new_sha, 'input_count': len(inputs),
                             'inputs': inputs, 'business_file_count': len(rows), 'files': rows})
    guard('sync-after')
    print(json.dumps({'version': VERSION, 'catalog_sha256': new_sha, 'input_count': len(inputs),
                      'business_file_count': len(rows)}, ensure_ascii=False))

def leaf_diff(a, b, prefix=''):
    if type(a) is not type(b):
        return [prefix]
    if isinstance(a, dict):
        assert a.keys() == b.keys(), prefix
        return [p for k in a for p in leaf_diff(a[k], b[k], prefix + '.' + k)]
    if isinstance(a, list):
        assert len(a) == len(b), prefix
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in leaf_diff(x, y, prefix + f'[{i}]')]
    return [prefix] if a != b else []

def audit():
    guard('audit-before')
    catalog = load(CATALOG)
    verify(catalog)
    saved = load(OUT / 'sync-changes.json')
    assert digest(CATALOG) == saved['catalog_sha256']
    before_path = OUT / 'before/求解器/数据/正式静态目录.json'
    before = load(before_path)
    expected = copy.deepcopy(before)
    expected['sources'] = source_snapshot()
    expected.update(formal_projection(expected['sources']))
    expected['version'] = VERSION
    assert serialized(expected) == CATALOG.read_bytes()
    changed_leaves = leaf_diff(before, catalog)
    assert changed_leaves == ['.constraints[32].text', '.sources[2].sha256', '.sources[2].lines[75]', '.version'], changed_leaves
    removed = '仓库已经满格且不会再出库的非成品'
    assert removed not in CATALOG.read_text()
    assert CATALOG.read_text().count(catalog['constraints'][32]['text']) == 2
    assert len(catalog['constraints']) == 72
    inputs, mismatches = [], []
    for base in [ROOT / '数据/样例', ROOT / 'crates/kernel/tests/fixtures']:
        for path in sorted(base.rglob('*.json')):
            obj = load(path)
            if not isinstance(obj, dict):
                continue
            schema = obj.get('schema')
            if schema in ['kernel-input-v2', 'kernel-input-v3']:
                refs = [('catalog', obj['catalog']), ('axis_registry', obj['parameters']['axis_registry'])]
                original = load(OUT / 'before' / path.relative_to(REPO))
                assert leaf_diff(original, obj) == ['.catalog.sha256'], path
            elif schema == 'profile-assignment-v2':
                refs = [(key, obj[key]) for key in ['profile_source', 'configuration_source', 'axis_source']]
            else:
                continue
            row = {'path': str(path.relative_to(ROOT)), 'schema': schema, 'references': []}
            for key, ref in refs:
                target = (path.parent / ref['path']).resolve()
                actual = digest(target)
                match = actual == ref['sha256']
                row['references'].append({'field': key, 'path': str(target), 'sha256': actual, 'matches': match})
                if not match:
                    mismatches.append({'path': str(path), 'field': key, 'expected': actual, 'actual': ref['sha256']})
            inputs.append(row)
    sources = load(ROOT / '数据/候选B/来源清单.json')
    for ref in sources:
        if digest(Path(ref['path'])) != ref['sha256']:
            mismatches.append(ref)
    assert len(inputs) == 56 and len(sources) == 16
    assert not mismatches, mismatches
    source_hashes = {s['path']: s['sha256'] for s in catalog['sources']}
    tree = ast.parse((ROOT / '数据/样例/check_examples.py').read_text())
    pinned = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'SOURCE_HASHES' for target in node.targets))
    assert pinned == source_hashes
    for ref in catalog['sources']:
        assert ref['sha256'] in (ROOT / '规格/运行语义.md').read_text()
    protected = load(OUT / '只读文件指纹.json')
    assert len(protected) == 4 and all(digest(Path(p)) == sha for p, sha in protected.items())
    original_checker = (OUT / 'before/求解器/规格/check_revision.py').read_text()
    assert original_checker.replace('2026-09-22e/只读文件指纹.json', '2026-09-22g/只读文件指纹.json') == (ROOT / '规格/check_revision.py').read_text()
    assert original_checker.splitlines()[114] == (ROOT / '规格/check_revision.py').read_text().splitlines()[114]
    for relative in ['求解器/数据/样例/runtime_example.py', '求解器/规格/内核配置-v1.json', '求解器/规格/受限模型声明.md']:
        assert digest(REPO / relative) == load(OUT / 'initial-active.json')[relative]
    import re
    for relative in ['数据/规则覆盖表.md', '规格/规则覆盖表.md']:
        sections = (ROOT / relative).read_text().split('## ')
        for i, source in enumerate(catalog['sources'][:2], 1):
            rows = [line.split('|')[1:-1] for line in sections[i].splitlines() if re.match(r'^\| \d+ \|', line)]
            assert len(rows) == len(source['lines'])
            for number, (row, line) in enumerate(zip(rows, source['lines']), 1):
                assert int(row[0]) == number and row[1].strip() == (line.strip() or '（空行）')
        if relative.startswith('数据'):
            rows = [line for line in sections[3].splitlines() if '`constraints[' in line]
            assert len(rows) == 72
            for i, (row, rule) in enumerate(zip(rows, catalog['constraints'])):
                assert f'`constraints[{i}]`' in row and rule['name'] in row and f"据行 {rule['basis_line']} 完整转录" in row
        else:
            rows = [line.split('|')[1:-1] for line in sections[3].splitlines() if re.match(r'^\| \d+ \|', line)]
            assert len(rows) == 72
            for i, (row, rule) in enumerate(zip(rows, catalog['constraints']), 1):
                assert int(row[0]) == i and row[1].strip() == rule['source_line'] and row[2].strip() == '约束·' + rule['name']
    # This report was transcribed, not regenerated by an extra CLI invocation.
    original_report = (OUT / 'before/求解器/数据/候选B/校验报告.md').read_text()
    report = (ROOT / '数据/候选B/校验报告.md').read_text()
    assert report == original_report.replace(before['version'], VERSION).replace(before['constraints'][32]['text'], catalog['constraints'][32]['text'])
    assert removed not in report
    inventory = scan('after')
    unresolved = [row for row in inventory['files'] if row['category'] in ['review_needed', 'additional_active_fixture'] or
                  (row['category'] == 'previous_scope' and row['path'] != '求解器/规格/修订记录.md')]
    assert not unresolved, unresolved
    from guard import active_snapshot
    current_active = active_snapshot()
    changes = difference(load(OUT / 'initial-active.json'), current_active)
    assert not changes['added'] and not changes['deleted']
    assert set(changes['changed']) == {r['path'] for r in saved['files']}
    for row in saved['files']:
        assert digest(REPO / row['path']) == row['after_sha256']
    save('audit.json', {'status': 'pass', 'catalog_sha256': digest(CATALOG), 'version': VERSION,
                       'catalog_changed_leaves': changed_leaves, 'constraints': 72, 'constants': 32,
                       'units': 18, 'recipes': 18, 'material_flow': 19, 'input_references': inputs,
                       'reference_document_count': len(inputs), 'candidate_source_count': len(sources),
                       'source_hashes': source_hashes, 'mismatches': mismatches,
                       'coverage_tables': '114/16/72 source lines and constraint rows agree',
                       'candidate_report': 'only version and quoted formal text changed; counts not rerun',
                       'old_sha_inventory_counts': inventory['counts'], 'unresolved_old_sha': unresolved,
                       'business_files': changes['changed'], 'out_of_scope_issue_files_unchanged': True})
    guard('audit-after')
    print(json.dumps({'status': 'pass', 'reference_document_count': len(inputs), 'candidate_source_count': len(sources),
                      'mismatches': mismatches, 'old_sha_inventory_counts': inventory['counts']}, ensure_ascii=False))

def positive():
    directory = OUT / 'positive'
    directory.mkdir()
    source = ROOT / '数据/样例/任务7内核/无线多格全收.json'
    document = load(source)
    for ref in [document['catalog'], document['parameters']['axis_registry']]:
        ref['path'] = str((source.parent / ref['path']).resolve())
    (directory / 'positive-input.json').write_bytes(serialized(document))
    binary = ROOT / 'target/debug/kernel'
    config = ROOT / '规格/内核配置-v1.json'
    rows = []
    for name, args, status in [
        ('positive-seed', ['seed', str(directory / 'positive-input.json'), '--out', str(directory / 'seed-output.json')], None),
        ('positive-check', ['check', str(directory / 'seed-output.json')], 'input_checked'),
        ('positive-run', ['run', str(directory / 'seed-output.json'), '--ticks', '6', '--out', str(directory / 'positive-run.json')], 'completed'),
        ('positive-verify-record', ['verify-record', str(directory / 'positive-run.json')], 'input_checked')]:
        argv = [str(binary), *args, '--config', str(config)]
        code = run(name, argv)
        response = json.loads((OUT / (name + '.log')).read_text())
        rows.append({'name': name, 'exit_code': code, 'status': response.get('status')})
        assert code == 0 and response.get('status') == status, rows[-1]
    assert load(directory / 'seed-output.json')['schema'] == 'kernel-input-v3'
    assert load(directory / 'positive-run.json')['status'] == 'completed'
    document['catalog']['sha256'] = OLD_SHA
    (directory / 'stale-catalog-input.json').write_bytes(serialized(document))
    argv = [str(binary), 'seed', str(directory / 'stale-catalog-input.json'), '--config', str(config)]
    code = run('stale-catalog-negative', argv)
    response = json.loads((OUT / 'stale-catalog-negative.log').read_text())
    reason = next((p for p in response.get('open_items', []) if str(CATALOG) in p and '源文件指纹不符' in p), None)
    assert code == 2 and response['status'] == 'invalid_input' and reason, response
    rows.append({'name': 'stale-catalog-negative', 'exit_code': code, 'status': response['status'], 'reason': reason})
    save('positive-validation.json', {'status': 'pass', 'binary_path': str(binary), 'binary_sha256': digest(binary),
                                    'commands': rows, 'ticks': 6, 'scope': 'finite run and record replay; no target-cycle certification'})

def report():
    import re
    import shlex
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from guard import active_snapshot
    commands = [json.loads(line) for line in (OUT / 'commands.jsonl').read_text().splitlines()]
    expected_names = {'cargo-build', 'cargo-check', 'cargo-clippy', 'kernel-lib', 'topology-lib', 'kernel-reference',
                      'topology-validation', 'kernel-doc', 'topology-doc', 'catalog-verify', 'catalog-regressions',
                      'positive-seed', 'positive-check', 'positive-run', 'positive-verify-record', 'stale-catalog-negative'}
    assert {c['name'] for c in commands} == expected_names and len(commands) == len(expected_names)
    assert all(not any(c['active_diff'].values()) for c in commands)
    sync_data = load(OUT / 'sync-changes.json')
    audit_data = load(OUT / 'audit.json')
    positive_data = load(OUT / 'positive-validation.json')
    tests, failures = [], []
    for command in commands:
        name = command['name']
        log = (OUT / (name + '.log')).read_text()
        count = re.search(r'test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored', log)
        row = {**command, 'expected_exit_code': 2 if name == 'stale-catalog-negative' else 0}
        if count:
            row.update(passed=int(count[1]), failed=int(count[2]), ignored=int(count[3]))
        if name == 'catalog-regressions':
            pycount = re.search(r'Ran (\d+) tests? in ', log)
            assert pycount
            row.update(passed=int(pycount[1]) if command['exit_code'] == 0 else None,
                       cases=int(pycount[1]))
        row['meets_expectation'] = row['exit_code'] == row['expected_exit_code']
        if not row['meets_expectation']:
            failures.append({'name': name, 'exit_code': row['exit_code'], 'log': name + '.log'})
        tests.append(row)
    rust_rows = [row for row in tests if row['argv'][:2] == ['cargo', 'test']]
    assert len(rust_rows) == 6
    rust_passed = sum(row.get('passed', 0) for row in rust_rows)
    rust_failed = sum(row.get('failed', 0) for row in rust_rows)
    active = active_snapshot()
    for row in sync_data['files']:
        assert active[row['path']] == row['after_sha256']
    assert {s: digest(REPO / s) for s in SOURCES} == load(OUT / 'formal-sources.json')
    diff_check = subprocess.run(['git', 'diff', '--check'], cwd=REPO, capture_output=True)
    (OUT / 'git-diff-check.log').write_bytes(diff_check.stdout + diff_check.stderr)
    assert diff_check.returncode == 0
    staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=REPO)
    assert not staged, '发现暂存区变动，须核查归属'
    (OUT / 'final-status.txt').write_bytes(subprocess.check_output(['git', '-c', 'core.quotepath=false', 'status', '--short', '--untracked-files=normal'], cwd=REPO))
    (OUT / 'business.patch').write_bytes(subprocess.check_output(['git', 'diff', '--', *[r['path'] for r in sync_data['files']]], cwd=REPO))
    (OUT / 'business-diff-stat.txt').write_bytes(subprocess.check_output(['git', '-c', 'core.quotepath=false', 'diff', '--stat', '--', *[r['path'] for r in sync_data['files']]], cwd=REPO))
    history = guard('delivery')
    history_count = sum(history['counts'].values())
    ignored = load(OUT / 'ignored-history-files.json')
    checkpoints = sorted(p.name for p in OUT.glob('*-history-diff.json'))
    assert all(not any(load(OUT / name).values()) for name in checkpoints)
    timestamp = datetime.now(ZoneInfo('America/New_York')).isoformat()
    known_issues = [
        {'issue': '规格/check_revision.py:115 的 T12 旧断言', 'action': '断言未改；该文件仅变更第 44 行的只读快照入口；本轮未运行规格总自查'},
        {'issue': '数据/样例/runtime_example.py 将桥轴对象按 Decision 校验', 'action': '文件原字节未变；本轮未运行 check_examples.py --self-test'},
        {'issue': '内核配置-v1.json 与受限模型声明.md 的两处实现状态文字', 'action': '两个文件原字节未变'}]
    summary = {'status': 'pass' if not failures else 'completed_with_test_failures', 'cutoff': timestamp,
               'catalog_version': VERSION, 'catalog_sha256': digest(CATALOG), 'constraints': 72,
               'business_file_count': sync_data['business_file_count'], 'relocked_inputs': 54,
               'sample_inputs': 45, 'fixture_inputs': 9, 'audited_reference_documents': 56,
               'audited_reference_fields': sum(len(row['references']) for row in audit_data['input_references']),
               'candidate_sources': 16, 'rust_passed': rust_passed, 'rust_failed': rust_failed,
               'python_cases': next(row['cases'] for row in tests if row['name'] == 'catalog-regressions'),
               'tests': tests, 'test_failures': failures, 'sync_mismatches': audit_data['mismatches'],
               'known_out_of_scope_issues': known_issues, 'history_counts': history['counts'],
               'history_total_files': history_count, 'history_ignored_files': len(ignored),
               'history_total_bytes': sum(row['bytes'] for row in history['files'].values()),
               'history_diff': load(OUT / 'delivery-history-diff.json'), 'history_comparison_count': len(checkpoints),
               'history_checkpoints': checkpoints, 'record_path': str(OUT / '记录.md')}
    save('summary.json', summary)
    save('changed-files.json', sync_data['files'])
    file_lines = ['# r24 业务文件清单', '', f'执行记录；截止 {timestamp}。共 {len(sync_data["files"])} 个业务文件，全部修改均未暂存。', '',
                  '| 文件（相对仓库） | 变更 |', '|---|---|']
    for row in sync_data['files']:
        path = row['path']
        if path.removeprefix('求解器/') in sync_data['inputs']:
            description = '仅 catalog.sha256 重锁；其余 JSON 字段及字节保持'
            if not row['previous_scope']:
                description += '；上次未改动，本轮 grep 补获'
        else:
            description = {
                '求解器/数据/正式静态目录.json': '重建投影：两处原文、正式约束 SHA、目录版本，共 4 个叶字段',
                '求解器/数据/候选B/来源清单.json': '16 项中仅正式约束和目录 SHA 两项改变',
                '求解器/数据/候选B/校验报告.md': '仅版本和原文同步；4924/0/75 计数沿用 r23，非本轮 CLI 结果',
                '求解器/数据/候选B/验证记录.md': '更新现行版本及本轮记录链接；标明计数来源',
                '求解器/数据/样例/check_examples.py': '仅 SOURCE_HASHES 中的正式约束 SHA',
                '求解器/规格/check_revision.py': '仅只读指纹入口由 22e 改为 22g；T12 断言未改',
                '求解器/规格/运行语义.md': '仅正式约束来源 SHA',
                '求解器/规格/修订记录.md': '尾部追加 r24 登记；旧节原样保留'}[path]
        file_lines.append(f'| [{path}](../../../{path.removeprefix("求解器/")}) | {description} |')
    # Links above are relative to this maintenance directory, whose grandparent is 求解器.
    file_lines = [line.replace('](../../../', '](../../') for line in file_lines]
    (OUT / 'changed-files.md').write_text('\n'.join(file_lines) + '\n')
    table = ['| 步骤 | 实际命令（cwd：求解器） | 退出码 | 结果 |', '|---|---|---:|---|']
    for row in tests:
        result = '符合预期' if row['meets_expectation'] else '失败，见日志'
        if 'failed' in row:
            result = f"{row['passed']} 通过 / {row['failed']} 失败 / {row['ignored']} 忽略"
        elif row['name'] == 'catalog-regressions':
            result = f"{row['cases']} 项；" + result
        elif row['name'] == 'stale-catalog-negative':
            result = '预期拒收：invalid_input，目录源文件指纹不符'
        argv = [arg.replace(str(ROOT) + '/', '') for arg in row['argv']]
        table.append(f"| [{row['name']}]({row['name']}.log) | `{shlex.join(argv)}` | {row['exit_code']} | {result} |")
    source_table = '\n'.join(f"| {p} | `{sha}` |" for p, sha in audit_data['source_hashes'].items())
    history_table = '\n'.join(f'| {p} | {n} |' for p, n in history['counts'].items())
    status_text = '目录及引用同步完成；指定安全集通过' if not failures else '目录及引用同步完成；安全集存在失败，见不一致清单'
    text = f'''# 正式静态目录 r24 重锁记录

史料／执行记录。执行日期：2026-09-22；截止：{timestamp}。状态：{status_text}；历史文件全量哈希无变化。本记录不构成目标循环、全参数或全厂达标认证。

## 结论与计数

仓库 `/home/zhuran24/zmd-research-fresh`，开工 HEAD `{(OUT / 'initial-head.txt').read_text().strip()}`。该 HEAD 已包含约束措辞提交 `dfc35cd` 与历史证据恢复提交 `8ab2324`。目录版本 `{VERSION}`，SHA-256 `{digest(CATALOG)}`；仍为 **72 条**。共修改 **62 个业务文件**，重锁 **54 份内核输入（45 个样例、9 个 fixture）**；核验 **56 份输入／参数赋值的 114 个引用字段**和候选 B 的 **16 项来源**，同步不一致 **0 项**。

安全 Rust 测试 **{rust_passed} 通过、{rust_failed} 失败**；Python 目录回归 **{summary['python_cases']} 项**。build/check/clippy、目录回源及正向 6 tick seed/check/run/verify-record 链的实际返回码见下表；旧 r23 目录 SHA 负例预期退出 2 并明确拒收。完整机器汇总见 [summary.json](summary.json)，业务文件逐项说明见 [changed-files.md](changed-files.md)，补丁见 [business.patch](business.patch)。

## 正式来源与精确变更

| 来源 | SHA-256 |
|---|---|
{source_table}

三份正式文件全轮字节未变。使用 [formal_catalog.py](../../数据/工具/formal_catalog.py) 的 `source_snapshot()`、`formal_projection()`、`verify()` 重建并审计，未修改生成器。目录恰有四个叶字段改变：`constraints[32].text`、`sources[2].sha256`、`sources[2].lines[75]`、`version`。约束第 33 条「传输按仓库余量判定」正文与来源全文两处删去指定尾句；原文位于 `求解约束.txt:76`。条款名、分节、据、行号不变；任务、18 类单位、18 条配方、32 项常量、19 项物料流量均逐对象不变。独立重建与落盘目录逐字节相等，旧尾句在目录中无残留。

54 份内核输入只替换 `catalog.sha256`，路径及参数轴 SHA 不变；另 2 份 profile-assignment-v2 无需改写，引用已复核。`benchmark_candidate_b.json` 不在上轮“改过”的 8 个 fixture 中，但本轮旧 SHA 检索确认它也是活动输入，故计入第 9 个 fixture。候选 B 来源清单 16 项仅正式约束与目录两项 SHA 改变，其余逐项核实。

样例 `SOURCE_HASHES`、运行语义来源 SHA、规格自查的只读快照入口同步到本轮 [只读文件指纹.json](只读文件指纹.json)。候选 B 校验报告只同步目录版本和原文，4924/0/75 是 r23 已存计数，本轮未单独运行 topology CLI。两张覆盖表的 114 行规则、16 行任务、72 条约束映射经只读核对一致，无需修改。详细字段及引用审计见 [audit.json](audit.json)。

旧 SHA 全仓检索保存于 [before-old-sha-inventory.json](before-old-sha-inventory.json) 与 [after-old-sha-inventory.json](after-old-sha-inventory.json)。检索包含隐藏和忽略文本，排除 `.git`、构建／缓存目录及并行工作的 `求解器/几何/1113流量层/`、`求解器/构造/`、`scratchpad`。剩余命中均为旧轮存档、本轮原字节备份／负例，及 `规格/修订记录.md` 的 r23 历史节；活动输入旧目录 SHA 残留为 0。历史原件中更早的指纹保持原样。

## 实际命令与结果

所有新增脚本落为文件，由 `bash 内核维护/2026-09-22g/run.sh ...` 或 `bash 内核维护/2026-09-22g/safe-suite.sh` 显式启动。共享 `CARGO_TARGET_DIR=/home/zhuran24/zmd-research-fresh/求解器/target`，所有 cargo 命令 `-j 4`，六个 Rust 测试目标均 `-- --test-threads=1`。`PYTHONDONTWRITEBYTECODE=1`；完整 argv、环境、耗时和返回码见 [commands.jsonl](commands.jsonl)。下表命令路径为便于阅读缩写，机器日志保留实际绝对路径。

{chr(10).join(table)}

Rust 两包 doc 各 0 项，未混入 134 项非文档测试计数。Python 8 项包含 1232 个单位叶字段与 154 个配方叶字段的逐叶变异，以及 10 个集合变异；这些是 8 项内的子检查，不能另计为测试用例。topology validation 内部还调用同一 Python 回归，未重复计数。Clippy 日志无警告。所有命令期间活动源码、输入及规格文件前后 SHA 均无变化。

正反链的二进制为 `{positive_data['binary_path']}`，SHA-256 `{positive_data['binary_sha256']}`，由本轮 debug build 构建。产物仅写本轮 [positive/](positive/)，复验结果见 [positive-validation.json](positive-validation.json)。负例仅把新输入的目录指纹换成旧 r23 SHA `{OLD_SHA}`；拒收原因指向实际目录路径及“源文件指纹不符”，不是用其它装载错误充数。有限 6 tick 运行及记录复验不等于循环达标证明。

## 历史证据全量哈希

| 历史目录（相对求解器） | 文件数 |
|---|---:|
{history_table}

共 **{history_count} 个文件**、**{summary['history_total_bytes']} 字节**，含 **{len(ignored)} 个 gitignore 忽略文件**；忽略清单见 [ignored-history-files.json](ignored-history-files.json)。按路径、文件字节数和完整文件 SHA-256 比较，不以 git status 或 mtime 代替内容哈希。每个实际测试／构建／CLI 命令前后均取全量快照；同步与审计也各取前后快照，另有交付快照。共 **{len(checkpoints)} 次**与初始基线比较，新增 0、删除 0、修改 0。

基线：[initial-history.json](initial-history.json)；交付：[delivery-history.json](delivery-history.json)；差异：[delivery-history-diff.json](delivery-history-diff.json)。本轮未运行 `cargo test --workspace`、七个 CLI 测试目标或写历史证据目录的脚本；未进行历史文件还原、覆盖或重锁。未使用 `git add`、`git commit`、`git checkout/restore/stash`。初始与交付状态保留于 [initial-status.txt](initial-status.txt)、[final-status.txt](final-status.txt)；并行目录不纳入本轮改动。

## 不一致清单与既有问题

本轮目录、输入引用与历史哈希不一致：**0 项**。安全测试失败：**{len(failures)} 个命令**。{'未出现安全测试因读取旧历史证据而失败的情况。' if not failures else '失败命令及原始日志见 summary.json 的 test_failures；未改历史文件。'}

下列三类问题来自上一轮记录，本轮不重跑对应总自查，也不登记为已修复：

1. `规格/check_revision.py:115` 的 T12 断言：原样保留，仅第 44 行只读快照入口由 22e 改到 22g。
2. `数据/样例/runtime_example.py` 把桥轴对象按 Decision 校验：文件哈希与开工相同。
3. `规格/内核配置-v1.json` 与 `规格/受限模型声明.md` 的 `transfer.partial_acceptance`、`gate.identity_recovery` 两处实现状态文字：两个文件哈希与开工相同。

本轮新增记录文件均位于 `求解器/内核维护/2026-09-22g/`；其中 `before/` 为被修改业务文件的原字节备份，未用于覆盖工作区。新增产物清单见 [artifacts.json](artifacts.json)。规格修订记录已经追加 r24；未提交，提交由主会话处理。
'''
    (OUT / '记录.md').write_text(text)
    artifacts = [{'path': str(p.relative_to(OUT)), 'bytes': p.stat().st_size, 'sha256': digest(p)}
                 for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['artifacts.json', 'reader-review.json']]
    save('artifacts.json', artifacts)
    print(json.dumps({k: summary[k] for k in ['status', 'business_file_count', 'relocked_inputs', 'rust_passed', 'rust_failed',
                     'python_cases', 'history_total_files', 'history_ignored_files', 'history_diff', 'record_path']}, ensure_ascii=False))
