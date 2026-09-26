"""2026-09-26 第 81 轮三审同步：求解约束 71 条→75 条后的目录重建、引用重锁与审计；由 guard.py 调用。

改动来源：主会话三审第 81 轮候选，新增「封闭植物分区次数界」「剩余供电格组界」「贴边条带切线」「方向预算」四条，
并进式改写 12 条正文或据。做法沿用 2026-09-26-三审同步（r26）：所有内容与授权检查先于第一次业务写入；写入前备份原字节到 before/。
"""
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from guard import OUT, ROOT, REPO, SOURCES, HISTORY, save, digest, guard, difference

CATALOG = ROOT / '数据/正式静态目录.json'
OLD_SHA = '630ab63d053d99f4d5621e3172d4cd1d6c86be6bfd84d1c8bc45b57819e7c72c'
OLD_SOURCE_SHA = 'fb073baa70562daf5d44f519a29e4b201d709074d96642add4f930a189bda7b6'
OLD_VERSION = '2026-09-26-r26-constraints-71'
VERSION = '2026-09-26-r27-constraints-75'
OLD_COUNT, NEW_COUNT = 71, 75
ADDED = ['封闭植物分区次数界', '剩余供电格组界', '贴边条带切线', '方向预算']
CHANGED = ['供电下限', '内带缺口', '回路存量', '回路守恒', '存货误料停机与可用台数', '封装进料', '植物再生来路',
           '物料流量', '研磨进料', '箱体过站', '箱内滞货封住后格', '面积预算']
STATIC = '§6：静态核验；本步不求几何、布线、台数优化或全厂流量配置，不改写为动态机制'
NEW_DESTINATION = {'封闭植物分区次数界': '§6：达标必要条件，保持原文前件；未作运行认证',
                   '剩余供电格组界': STATIC, '贴边条带切线': STATIC, '方向预算': STATIC}
THIS_RUN = '求解器/内核维护/2026-09-26-第81轮三审同步/'
FORMAL_TOOL = ROOT / '数据/工具/formal_catalog.py'


def load(path):
    return json.loads(path.read_text())


def serialized(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def formal_module(text):
    """按给定源码文本载入 formal_catalog（写入前用 75 条版本做投影与核验）。"""
    sys.path.insert(0, str(ROOT / '数据/工具'))
    spec = importlib.util.spec_from_loader('formal_catalog_r27', loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(FORMAL_TOOL)
    exec(compile(text, str(FORMAL_TOOL), 'exec'), module.__dict__)
    return module


def replace_once(text, pairs, label):
    for old, new in pairs:
        assert text.count(old) == 1, (label, old, text.count(old))
        text = text.replace(old, new)
    return text


def scan(label, sha_list):
    argv = ['rg', '--hidden', '--no-ignore', '-l', '-0', '-F']
    for sha in sha_list:
        argv += ['-e', sha]
    argv += ['-g', '!.git/**', '-g', '!**/target/**', '-g', '!**/__pycache__/**', '-g', '!**/.cargo-home/**',
             '-g', '!scratchpad/**', '-g', '!**/scratchpad/**', '.']
    result = subprocess.run(argv, cwd=REPO, capture_output=True)
    assert result.returncode in (0, 1), result.stderr.decode()
    paths = sorted(Path(p).as_posix().removeprefix('./') for p in result.stdout.decode().split('\0') if p)
    rows = []
    for relative in paths:
        if any(relative.startswith('求解器/' + p + '/') for p in HISTORY):
            category = 'protected_history'
        elif relative.startswith(THIS_RUN):
            category = 'this_run_record'
        elif relative.startswith(('求解器/内核维护/', '求解器/规格/复核/', '求解器/老项目/', '求解器/候选简化轮次/',
                                  '求解器/规则修订/', '求解器/构造/', '求解器/几何/', '求解器/结构检测/',
                                  '求解器/候选约束轮次/', '求解器/约束修订/', '求解器/会议成果/')):
            category = 'archived_or_parallel'
        elif relative == '求解器/规格/修订记录.md':
            category = 'revision_history'
        else:
            category = 'active'
        rows.append({'path': relative, 'category': category})
    value = {'argv': argv, 'exit_code': result.returncode, 'counts': dict(Counter(r['category'] for r in rows)), 'files': rows}
    save(label + '-old-sha-inventory.json', value)
    return value


def rebuild_semantics_table(text, catalog):
    """规格/规则覆盖表.md 第 3 节：按新目录逐条重排序号与源行，去向文字按条目名沿用。"""
    head, sec3 = text.split('## 3. 正式约束条目登记', 1)
    body, tail = sec3.split('\n## 4.', 1)
    lines = body.split('\n')
    rows = {}
    for line in lines:
        m = re.match(r'^\| (\d+) \| (\d+) \| 约束·([^|]+?) \| (.*) \|$', line)
        if m:
            rows[m.group(3)] = m.group(4)
    assert len(rows) == OLD_COUNT and not set(ADDED) & set(rows)
    out, first = [], None
    for k, line in enumerate(lines):
        if re.match(r'^\| \d+ \| \d+ \| 约束·', line):
            if first is None:
                first = len(out)
            continue
        out.append(line)
    new_rows = [f"| {i} | {r['source_line']} | 约束·{r['name']} | {rows.get(r['name']) or NEW_DESTINATION[r['name']]} |" for i, r in enumerate(catalog['constraints'], 1)]
    out[first:first] = new_rows
    return head + '## 3. 正式约束条目登记' + '\n'.join(out) + '\n## 4.' + tail


def rebuild_contract_table(text, catalog):
    """数据/规则覆盖表.md「正式约束」节：按新目录重写下标与据行，列 2 由目录的分节与义务重算。"""
    lines = text.split('\n')
    idx = [k for k, l in enumerate(lines) if '`constraints[' in l]
    assert len(idx) == OLD_COUNT and idx == list(range(idx[0], idx[0] + OLD_COUNT))
    names = [l.split('|')[1].strip() for l in (lines[k] for k in idx)]
    assert not set(ADDED) & set(names)
    new = []
    for i, r in enumerate(catalog['constraints']):
        col2 = r['section'] + '；' + (r['obligation'] or '按条文前件')
        new.append(f"| {r['name']} | {col2} | `constraints[{i}]`；报告“正式条目/{r['name']}”；据行 {r['basis_line']} 完整转录 |")
    lines[idx[0]:idx[-1] + 1] = new
    return '\n'.join(lines)


def sync():
    guard('sync-before')
    assert not (OUT / 'sync-changes.json').exists()
    assert digest(CATALOG) == OLD_SHA
    initial = load(OUT / 'initial-active.json')
    plan = {}

    # 1. 写死条数：71 → 75
    tool_text = FORMAL_TOOL.read_text()
    new_tool = replace_once(tool_text, [
        ("    assert len(rows) == 71 and all(r.get('basis') for r in rows)", "    assert len(rows) == 75 and all(r.get('basis') for r in rows)"),
        ("三份正式来源指纹与全文、71 条约束上下文", "三份正式来源指纹与全文、75 条约束上下文")], 'formal_catalog.py')
    plan[FORMAL_TOOL] = new_tool.encode()
    p = ROOT / '数据/工具/test_formal_catalog.py'
    plan[p] = replace_once(p.read_text(), [("self.assertEqual(len(projection['constraints']), 71)", "self.assertEqual(len(projection['constraints']), 75)")], p.name).encode()
    p = ROOT / '数据/工具/check_revision.py'
    plan[p] = replace_once(p.read_text(), [("assert len(catalog['constraints']) == 71", "assert len(catalog['constraints']) == 75")], p.name).encode()
    p = ROOT / 'crates/topology/tests/validation.rs'
    plan[p] = replace_once(p.read_text(), [('assert_eq!(cat["constraints"].as_array().unwrap().len(), 71);', 'assert_eq!(cat["constraints"].as_array().unwrap().len(), 75);')], p.name).encode()
    p = ROOT / '规格/check_revision.py'
    plan[p] = replace_once(p.read_text(), [
        ("check(len(expected) == len(rows) == 71, '正式约束 71 条覆盖')", "check(len(expected) == len(rows) == 75, '正式约束 75 条覆盖')"),
        ('内核维护/2026-09-26-三审同步/只读文件指纹.json', '内核维护/2026-09-26-第81轮三审同步/只读文件指纹.json')], p.name).encode()

    # 2. 目录：按 75 条版本的 formal_catalog 回源重建
    fc = formal_module(new_tool)
    before = load(CATALOG)
    assert before['version'] == OLD_VERSION and len(before['constraints']) == OLD_COUNT
    current = copy.deepcopy(before)
    current['sources'] = fc.source_snapshot()
    current.update(fc.formal_projection(current['sources']))
    current['version'] = VERSION
    fc.verify(current)
    assert len(current['constraints']) == NEW_COUNT
    for key in ['task', 'units', 'recipes', 'static_checks']:
        assert before[key] == current[key], key
    assert current['sources'][0] == before['sources'][0] and current['sources'][1] == before['sources'][1]
    old_by = {r['name']: r for r in before['constraints']}
    new_by = {r['name']: r for r in current['constraints']}
    assert not set(old_by) - set(new_by) and set(new_by) - set(old_by) == set(ADDED)
    text_changed = sorted(n for n in old_by if (old_by[n]['text'], old_by[n]['basis']) != (new_by[n]['text'], new_by[n]['basis']))
    assert text_changed == sorted(CHANGED), text_changed
    plan[CATALOG] = serialized(current)
    new_sha = hashlib.sha256(plan[CATALOG]).hexdigest()
    source_sha = current['sources'][2]['sha256']
    assert source_sha == digest(REPO / '求解约束.txt')

    # 3. 54 份内核输入只换目录指纹
    inputs = []
    for base in [ROOT / '数据/样例', ROOT / 'crates/kernel/tests/fixtures']:
        for path in sorted(base.rglob('*.json')):
            obj = load(path)
            if isinstance(obj, dict) and obj.get('schema') in ['kernel-input-v2', 'kernel-input-v3']:
                assert obj['catalog']['sha256'] == OLD_SHA, path
                assert (path.parent / obj['catalog']['path']).resolve() == CATALOG, path
                updated = copy.deepcopy(obj)
                updated['catalog']['sha256'] = new_sha
                data = path.read_bytes()
                assert data.count(OLD_SHA.encode()) == 1, path
                data = data.replace(OLD_SHA.encode(), new_sha.encode())
                assert json.loads(data) == updated, path
                plan[path] = data
                inputs.append(str(path.relative_to(ROOT)))
    assert len(inputs) == 54, len(inputs)

    # 4. 候选 B 来源清单
    sources_path = ROOT / '数据/候选B/来源清单.json'
    sources = load(sources_path)
    new_sources = copy.deepcopy(sources)
    for ref in new_sources:
        if Path(ref['path']) == CATALOG:
            ref['sha256'] = new_sha
        elif Path(ref['path']) == REPO / '求解约束.txt':
            ref['sha256'] = source_sha
        elif Path(ref['path']) == REPO / '候选约束.txt':
            # r26 之后流水线入档第 81—83 轮、本轮三审改状态行与进度段，旧指纹已过期，按现行字节同步
            ref['sha256'] = digest(REPO / '候选约束.txt')
        else:
            assert digest(Path(ref['path'])) == ref['sha256'], ref
    assert len(sources) == 16
    plan[sources_path] = serialized(new_sources)

    # 5. 其余引用正式约束 SHA、目录版本与条数的活动文件
    p = ROOT / '数据/样例/check_examples.py'
    plan[p] = replace_once(p.read_text(), [(OLD_SOURCE_SHA, source_sha)], p.name).encode()
    p = ROOT / '规格/运行语义.md'
    plan[p] = replace_once(p.read_text(), [(OLD_SOURCE_SHA, source_sha),
        ('现行三份正式源与 71 条约束覆盖已同步', '现行三份正式源与 75 条约束覆盖已同步')], p.name).encode()
    p = ROOT / '规格/规则覆盖表.md'
    t = replace_once(p.read_text(), [('登记正式约束全部 71 条', '登记正式约束全部 75 条')], p.name)
    plan[p] = rebuild_semantics_table(t, current).encode()
    p = ROOT / '数据/规则覆盖表.md'
    t = replace_once(p.read_text(), [('任务 16 行与 71 条正式约束逐行/逐项登记', '任务 16 行与 75 条正式约束逐行/逐项登记')], p.name)
    plan[p] = rebuild_contract_table(t, current).encode()
    p = ROOT / '数据/候选B/转换说明.md'
    plan[p] = replace_once(p.read_text(), [('71 条正式约束目录与来源引用已同步', '75 条正式约束目录与来源引用已同步'),
                                           ('（71 条，算术计数）', '（75 条，算术计数）')], p.name).encode()

    # 6. 修订记录追加 r27
    revisions = ROOT / '规格/修订记录.md'
    addition = f'''\n## 2026-09-26 r27：三审采纳第 81 轮候选，正式约束 71 条改为 75 条\n\n依据主会话三审后的现行三份正式文件，使用 `数据/工具/formal_catalog.py` 的回源投影重建目录。目录版本 `{VERSION}`，SHA-256 `{new_sha}`；约束 75 条。\n\n| 文件 | SHA-256 |\n|---|---|\n'''
    addition += ''.join(f"| {s['path']} | `{s['sha256']}` |\n" for s in current['sources'])
    addition += '''\n求解约束新增「封闭植物分区次数界」「剩余供电格组界」「贴边条带切线」「方向预算」四条；「物料流量」「箱体过站」「存货误料停机与可用台数」「研磨进料」「封装进料」「回路守恒」「回路存量」「植物再生来路」「箱内滞货封住后格」「供电下限」「面积预算」「内带缺口」十二条正文或据改写（并进第 81 轮候选；「内带缺口」有箱时的 918 一句与「面积预算」的 4608 一句被「方向预算」覆盖而删去）；正式空矩形上界仍为 1110。目录的约束投影与正式约束来源全文同步；任务、18 类单位、18 条配方、32 项常量和 19 项物料流量均不变（「物料流量」「研磨进料」「封装进料」的新句接在原句之后，目录解析出的数值不变）。formal_catalog.py、test_formal_catalog.py、数据/工具/check_revision.py、规格/check_revision.py、topology 的 validation.rs 中写死的条数改为 75；两张规则覆盖表的正式约束节按新目录重排，新增四条的去向按同类条目登记。54 份内核输入（45 个样例、9 个 fixture）只重锁目录 SHA；候选 B 来源清单、样例来源校验、运行语义来源 SHA、规格自查的只读快照入口同步；候选 B 报告用本轮构建的 topology 重新生成。\n\n本轮执行记录及安全测试结果见[2026-09-26 第 81 轮三审同步记录](../内核维护/2026-09-26-第81轮三审同步/记录.md)。本节不修改旧轮记录与历史证据。\n'''
    assert '\n## 2026-09-26 r27' not in revisions.read_text()
    plan[revisions] = revisions.read_bytes() + addition.encode()

    rows = []
    for path, content in plan.items():
        relative = str(path.relative_to(REPO))
        assert digest(path) == initial[relative], '活动文件已经发生并发变动：' + relative
        backup = OUT / 'before' / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(path.read_bytes())
        rows.append({'path': relative, 'before_sha256': digest(path), 'after_sha256': hashlib.sha256(content).hexdigest()})
    save('sync-plan.json', rows)
    save('只读文件指纹.json', {str(REPO / p): digest(REPO / p) for p in [*SOURCES, '候选约束.txt']})
    for path, content in plan.items():
        path.write_bytes(content)
    save('sync-changes.json', {'version': VERSION, 'catalog_sha256': new_sha, 'constraint_source_sha256': source_sha,
                               'input_count': len(inputs), 'inputs': inputs, 'business_file_count': len(rows), 'files': rows,
                               'added_constraints': ADDED, 'changed_constraints': CHANGED})
    guard('sync-after')
    print(json.dumps({'version': VERSION, 'catalog_sha256': new_sha, 'input_count': len(inputs),
                      'business_file_count': len(rows)}, ensure_ascii=False))


def candidate_report():
    """用本轮 debug 构建的 topology 重新生成候选 B 报告（报告在该命令日志里），写回数据/候选B/校验报告.md。"""
    log = OUT / 'candidate-b-report.log'
    assert log.exists()
    report = log.read_text()
    assert report.startswith('# 候选 B 静态校验报告'), report[:80]
    catalog = load(CATALOG)
    for rule in catalog['constraints']:
        assert '正式条目/' + rule['name'] in report
    for name in ADDED:
        assert '正式条目/' + name in report
    assert VERSION in report
    target = ROOT / '数据/候选B/校验报告.md'
    backup = OUT / 'before' / str(target.relative_to(REPO))
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(target.read_bytes())
    target.write_text(report)
    counts = {k: int(v) for k, v in re.findall(r'## (能检且通过|能检且不通过|不能静态检)（(\d+) 项', report)}
    rec = ROOT / '数据/候选B/验证记录.md'
    text = rec.read_text()
    old_line = text.split('\n')[2]
    assert old_line.startswith('现行目录为 `2026-09-26-r26-constraints-71`'), old_line
    new_line = (f"现行目录为 `{VERSION}`；候选 B 当前报告为 {counts['能检且通过']} 项通过、{counts['能检且不通过']} 项失败、"
                f"{counts['不能静态检']} 项不能静态检，其中 {len(catalog['constraints'])} 项是正式约束运行/几何义务。"
                "目录重锁、报告重新生成与本轮安全验证见[2026-09-26 第 81 轮三审同步记录](../../内核维护/2026-09-26-第81轮三审同步/记录.md)；下文是旧轮史料。")
    backup = OUT / 'before' / str(rec.relative_to(REPO))
    backup.write_bytes(rec.read_bytes())
    rec.write_text(text.replace(old_line, new_line, 1))
    save('candidate-report.json', {'counts': counts, 'report_sha256': digest(target), 'verification_record_line': new_line})
    print(json.dumps(counts, ensure_ascii=False))


def audit():
    guard('audit-before')
    fc = formal_module(FORMAL_TOOL.read_text())
    catalog = load(CATALOG)
    fc.verify(catalog)
    saved = load(OUT / 'sync-changes.json')
    assert digest(CATALOG) == saved['catalog_sha256']
    assert len(catalog['constraints']) == NEW_COUNT and set(ADDED) <= {r['name'] for r in catalog['constraints']}
    mismatches, inputs = [], []
    for base in [ROOT / '数据/样例', ROOT / 'crates/kernel/tests/fixtures']:
        for path in sorted(base.rglob('*.json')):
            obj = load(path)
            if not isinstance(obj, dict):
                continue
            schema = obj.get('schema')
            if schema in ['kernel-input-v2', 'kernel-input-v3']:
                refs = [('catalog', obj['catalog']), ('axis_registry', obj['parameters']['axis_registry'])]
            elif schema == 'profile-assignment-v2':
                refs = [(key, obj[key]) for key in ['profile_source', 'configuration_source', 'axis_source']]
            else:
                continue
            row = {'path': str(path.relative_to(ROOT)), 'schema': schema, 'references': []}
            for key, ref in refs:
                target = (path.parent / ref['path']).resolve()
                actual = digest(target)
                row['references'].append({'field': key, 'matches': actual == ref['sha256']})
                if actual != ref['sha256']:
                    mismatches.append({'path': str(path), 'field': key})
            inputs.append(row)
    sources = load(ROOT / '数据/候选B/来源清单.json')
    for ref in sources:
        if digest(Path(ref['path'])) != ref['sha256']:
            mismatches.append(ref)
    assert len(inputs) == 56 and len(sources) == 16
    assert not mismatches, mismatches
    import ast
    tree = ast.parse((ROOT / '数据/样例/check_examples.py').read_text())
    pinned = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'SOURCE_HASHES' for t in node.targets))
    assert pinned == {s['path']: s['sha256'] for s in catalog['sources']}
    for ref in catalog['sources']:
        assert ref['sha256'] in (ROOT / '规格/运行语义.md').read_text()
    protected = load(OUT / '只读文件指纹.json')
    assert len(protected) == 4
    protected_now = {p: digest(Path(p)) == sha for p, sha in protected.items()}
    for relative in ['数据/规则覆盖表.md', '规格/规则覆盖表.md']:
        sections = (ROOT / relative).read_text().split('## ')
        for i, source in enumerate(catalog['sources'][:2], 1):
            rows = [line.split('|')[1:-1] for line in sections[i].splitlines() if re.match(r'^\| \d+ \|', line)]
            assert len(rows) == len(source['lines'])
        if relative.startswith('数据'):
            rows = [line for line in sections[3].splitlines() if '`constraints[' in line]
            assert len(rows) == NEW_COUNT
            for i, (row, rule) in enumerate(zip(rows, catalog['constraints'])):
                assert f'`constraints[{i}]`' in row and rule['name'] in row and f"据行 {rule['basis_line']} 完整转录" in row
        else:
            rows = [line.split('|')[1:-1] for line in sections[3].splitlines() if re.match(r'^\| \d+ \|', line)]
            assert len(rows) == NEW_COUNT
            for i, (row, rule) in enumerate(zip(rows, catalog['constraints']), 1):
                assert int(row[0]) == i and row[1].strip() == rule['source_line'] and row[2].strip() == '约束·' + rule['name']
    report = (ROOT / '数据/候选B/校验报告.md').read_text()
    for rule in catalog['constraints']:
        assert '正式条目/' + rule['name'] in report and rule['basis'] in report
    inventory = scan('after', [OLD_SHA, OLD_SOURCE_SHA])
    unresolved = [r for r in inventory['files'] if r['category'] == 'active']
    assert not unresolved, unresolved
    from guard import active_snapshot
    changes = difference(load(OUT / 'initial-active.json'), active_snapshot())
    save('audit.json', {'status': 'pass', 'catalog_sha256': digest(CATALOG), 'version': VERSION, 'constraints': NEW_COUNT,
                        'input_references': inputs, 'reference_document_count': len(inputs), 'candidate_source_count': len(sources),
                        'mismatches': mismatches, 'protected_fingerprints_current': protected_now,
                        'old_sha_inventory_counts': inventory['counts'], 'active_changes_since_initial': changes})
    guard('audit-after')
    print(json.dumps({'status': 'pass', 'reference_document_count': len(inputs), 'candidate_source_count': len(sources),
                      'old_sha_inventory_counts': inventory['counts'], 'protected_fingerprints_current': protected_now}, ensure_ascii=False))
