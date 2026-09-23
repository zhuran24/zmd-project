#!/usr/bin/env python3
"""Independent, read-only r24 audit; durable output restricted to this directory."""
import ast
import collections
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
ROOT = REPO / '求解器'
HISTORY = ['求解器/crates/kernel/evidence', '求解器/crates/kernel/复核', '求解器/数据/复核']
PARALLEL = ['求解器/几何/1113流量层', '求解器/构造', 'scratchpad']
MAINT = '求解器/内核维护/2026-09-22g'
CAT = '求解器/数据/正式静态目录.json'
SOURCES = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']

def now():
    return datetime.datetime.now().astimezone().isoformat()

def inside(path, roots):
    return any(path == p or path.startswith(p + '/') for p in roots)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def load(name):
    return json.loads((OUT / name).read_text())

def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotePath=false', *args], cwd=REPO)

def head_bytes(path):
    return git('show', load('baseline.json')['head'] + ':' + path)

def status(name):
    raw = git('status', '--porcelain=v1', '-z', '--untracked-files=all')
    (OUT / (name + '-status.z')).write_bytes(raw)
    rows = []
    parts = iter(raw.split(b'\0'))
    for part in parts:
        if not part:
            continue
        code, path = part[:2].decode(), part[3:].decode()
        row = {'status': code, 'path': path}
        if 'R' in code or 'C' in code:
            row['original_path'] = next(parts).decode()
        rows.append(row)
    save(name + '-status.json', rows)
    (OUT / (name + '-status.txt')).write_text(''.join(f"{r['status']} {r['path']}\n" for r in rows))
    return rows

def history_snapshot(name):
    files = {}
    for directory in HISTORY:
        for p in sorted((REPO / directory).rglob('*')):
            if p.is_symlink():
                files[str(p.relative_to(REPO))] = {'kind': 'symlink', 'target': os.readlink(p)}
            elif p.is_file():
                files[str(p.relative_to(REPO))] = {'bytes': p.stat().st_size, 'sha256': digest(p)}
    result = {'time': now(), 'files': files,
              'counts': {p: sum(inside(k, [p]) for k in files) for p in HISTORY},
              'bytes': sum(v.get('bytes', 0) for v in files.values())}
    save(name + '-history.json', result)
    return result

def diff_maps(a, b):
    return {'added': sorted(b.keys() - a.keys()), 'deleted': sorted(a.keys() - b.keys()),
            'modified': sorted(k for k in a.keys() & b.keys() if a[k] != b[k])}

def active_snapshot(name):
    paths = git('ls-files', '-z').decode().split('\0')
    files = {}
    for path in paths:
        if not path or inside(path, HISTORY + PARALLEL + ['求解器/内核维护']):
            continue
        p = REPO / path
        if p.is_file():
            files[path] = digest(p)
        else:
            files[path] = None
    save(name + '-active.json', files)
    return files

def baseline():
    assert not (OUT / 'baseline.json').exists(), 'Baseline already exists'
    rows = status('initial')
    save('baseline.json', {'time': now(), 'head': git('rev-parse', 'HEAD').decode().strip(),
                          'index_sha256': digest(REPO / '.git/index')})
    history_snapshot('initial')
    active_snapshot('initial')
    (OUT / 'initial.patch').write_bytes(git('diff', 'HEAD', '--', '.',
        *[':(exclude)' + p for p in PARALLEL]))
    ignored = git('ls-files', '--others', '--ignored', '--exclude-standard', '-z', '--', *HISTORY)
    save('history-ignored.json', [x for x in ignored.decode().split('\0') if x])
    print(json.dumps({'head': load('baseline.json')['head'], 'history': load('initial-history.json')['counts'],
                      'status_entries': len(rows)}, ensure_ascii=False), flush=True)

def history_head():
    listing = git('ls-tree', '-r', '-z', load('baseline.json')['head'], '--', *HISTORY)
    rows = [x.split(b'\t', 1) for x in listing.split(b'\0') if x]
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    expected = {}
    modes = {}
    for meta, path in rows:
        mode, kind, oid = meta.split()
        proc.stdin.write(oid + b'\n')
        proc.stdin.flush()
        header = proc.stdout.readline().split()
        size = int(header[2])
        data = proc.stdout.read(size)
        assert proc.stdout.read(1) == b'\n'
        expected[path.decode()] = {'bytes': size, 'sha256': sha(data)}
        modes[path.decode()] = mode.decode()
    proc.stdin.close()
    assert proc.wait() == 0
    actual = load('initial-history.json')['files']
    mismatch = [p for p, v in expected.items() if actual.get(p) != v]
    extra = sorted(actual.keys() - expected.keys())
    save('history-head.json', {'head': load('baseline.json')['head'], 'tracked_count': len(expected),
                             'mismatches': mismatch, 'extra_untracked_or_ignored': extra,
                             'files': expected, 'modes': modes,
                             'git_diff': git('diff', 'HEAD', '--name-status', '--', *HISTORY).decode()})
    print(json.dumps({'history_head_tracked': len(expected), 'mismatches': mismatch, 'extra': extra}, ensure_ascii=False), flush=True)

def leaf_diff(a, b, prefix=''):
    if type(a) != type(b):
        return [prefix]
    if isinstance(a, dict):
        keys = list(a) + [k for k in b if k not in a]
        return [p for k in keys for p in ([prefix + '.' + k] if k not in a or k not in b else leaf_diff(a[k], b[k], prefix + '.' + k))]
    if isinstance(a, list):
        if len(a) != len(b):
            return [prefix + '.length']
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in leaf_diff(x, y, prefix + f'[{i}]')]
    return [] if a == b else [prefix]

def order_like(value, template):
    # Preserve the HEAD serialization key order, never its generated values.
    if isinstance(value, dict):
        assert set(value) == set(template)
        return {k: order_like(value[k], template[k]) for k in template}
    if isinstance(value, list):
        assert len(value) == len(template)
        return [order_like(v, t) for v, t in zip(value, template)]
    return value

def catalog_audit():
    source_dir = OUT / 'head-sources'
    source_dir.mkdir(exist_ok=True)
    source_rows = []
    snapshot = []
    for name in SOURCES:
        data = head_bytes(name)
        (source_dir / name).write_bytes(data)
        snapshot.append({'path': name, 'sha256': sha(data), 'lines': data.decode().splitlines()})
        source_rows.append({'path': name, 'head_sha256': sha(data), 'working_sha256': digest(REPO / name),
                            'working_equals_head': data == (REPO / name).read_bytes()})
    tools_dir = ROOT / '数据/工具'
    for name in ['formal_catalog.py', 'formal_units.py']:
        assert (tools_dir / name).read_bytes() == head_bytes('求解器/数据/工具/' + name)
    sys.path.insert(0, str(tools_dir))
    import formal_catalog as fc
    old = json.loads(head_bytes(CAT))
    live = json.loads((REPO / CAT).read_bytes())
    projection = fc.formal_projection(snapshot)
    rules = '\n'.join(snapshot[0]['lines'])
    units = fc.unit_projection(rules, projection['constraints'], fc.quantity)
    rebuilt = {'recipes': fc.recipe_projection(rules),
               'units': [units[u['id']] for u in old['units']],
               'schema': 'static-catalog-v2', 'source_root': '../..',
               'version': '2026-09-22-r24-constraints-72', 'sources': snapshot,
               'conventions': old['conventions'], 'transcribed_at': old['transcribed_at'], **projection}
    rebuilt = order_like(rebuilt, old)
    data = (json.dumps(rebuilt, ensure_ascii=False, indent=2) + '\n').encode()
    (OUT / 'rebuilt-catalog.json').write_bytes(data)
    fc.verify(rebuilt, source_dir)
    result = {'head': load('baseline.json')['head'], 'sources': source_rows,
              'old_sha256': sha(head_bytes(CAT)), 'new_sha256': digest(REPO / CAT),
              'rebuilt_sha256': sha(data), 'byte_equal': data == (REPO / CAT).read_bytes(),
              'semantic_differences': leaf_diff(rebuilt, live), 'head_changed_leaves': leaf_diff(old, live),
              'constraints': len(rebuilt['constraints']), 'units': len(rebuilt['units']),
              'recipes': len(rebuilt['recipes']), 'constants': len(rebuilt['static_checks']['constants']),
              'material_flow': len(rebuilt['static_checks']['material_flow']),
              'method': 'HEAD formal source bytes; full projection of constraints/task/constants/flow/recipes/units; HEAD supplies serialization order, unit order, conventions, and transcription timestamp; explicit r24 version',
              'generator_hashes': {n: digest(tools_dir / n) for n in ['formal_catalog.py', 'formal_units.py']}}
    save('catalog-audit.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)

def references_audit():
    rows, mismatches, input_changes = [], [], []
    for base in [ROOT / '数据/样例', ROOT / 'crates/kernel/tests/fixtures']:
        for p in sorted(base.rglob('*.json')):
            doc = json.loads(p.read_bytes())
            if not isinstance(doc, dict):
                continue
            schema = doc.get('schema')
            if schema in ['kernel-input-v2', 'kernel-input-v3']:
                refs = [('catalog', doc['catalog']), ('parameters.axis_registry', doc['parameters']['axis_registry'])]
                old = json.loads(head_bytes(str(p.relative_to(REPO))))
                leaves = leaf_diff(old, doc)
                input_changes.append({'path': str(p.relative_to(REPO)), 'changed_leaves': leaves,
                                      'bytes_only_sha_replaced': head_bytes(str(p.relative_to(REPO))).replace(load('catalog-audit.json')['old_sha256'].encode(), load('catalog-audit.json')['new_sha256'].encode()) == p.read_bytes()})
            elif schema == 'profile-assignment-v2':
                refs = [(key, doc[key]) for key in ['profile_source', 'configuration_source', 'axis_source']]
            else:
                continue
            result = {'path': str(p.relative_to(REPO)), 'schema': schema, 'references': []}
            for field, ref in refs:
                target = (p.parent / ref['path']).resolve()
                actual = digest(target) if target.is_file() else None
                item = {'field': field, 'target': str(target), 'declared_sha256': ref['sha256'], 'actual_sha256': actual, 'matches': ref['sha256'] == actual}
                result['references'].append(item)
                if not item['matches']:
                    mismatches.append({'path': str(p.relative_to(REPO)), **item})
            rows.append(result)
    candidate = []
    for ref in json.loads((ROOT / '数据/候选B/来源清单.json').read_text()):
        target = Path(ref['path'])
        candidate.append({**ref, 'actual_sha256': digest(target), 'matches': ref['sha256'] == digest(target)})
    tree = ast.parse((ROOT / '数据/样例/check_examples.py').read_text())
    declared = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SOURCE_HASHES' for t in n.targets))
    source_check = {n: declared[n] == digest(REPO / n) for n in SOURCES}
    snapshot = json.loads((OUT.parent / '只读文件指纹.json').read_text())
    snapshot_check = {p: digest(Path(p)) == v for p, v in snapshot.items()}
    save('references-audit.json', {'documents': len(rows), 'reference_fields': sum(len(r['references']) for r in rows),
          'kernel_inputs': len(input_changes), 'samples': sum(r['path'].startswith('求解器/数据/样例/') for r in input_changes),
          'fixtures': sum(r['path'].startswith('求解器/crates/') for r in input_changes),
          'mismatches': mismatches, 'documents_detail': rows, 'input_changes': input_changes,
          'candidate_sources': candidate, 'source_hashes_check': source_check, 'readonly_snapshot_check': snapshot_check})
    print(json.dumps({'documents': len(rows), 'fields': sum(len(r['references']) for r in rows), 'inputs': len(input_changes), 'mismatches': mismatches}, ensure_ascii=False), flush=True)

def old_sha_scan():
    old = load('catalog-audit.json')['old_sha256']
    # Include hidden/ignored text and protected parallel paths in a read-only search.
    # Never exclude historical archives before searching; classify each hit afterward.
    argv = ['rg', '--hidden', '--no-ignore', '-l', '-0', '-F', old, '.',
            '-g', '!.git/**', '-g', '!**/target/**', '-g', '!**/__pycache__/**',
            '-g', '!**/.pytest_cache/**', '-g', '!**/.cache/**', '-g', '!' + str(OUT.relative_to(REPO)) + '/**']
    proc = subprocess.run(argv, cwd=REPO, capture_output=True)
    (OUT / 'old-sha-scan.stderr.log').write_bytes(proc.stderr)
    rows = []
    for raw in proc.stdout.split(b'\0'):
        if not raw:
            continue
        path = raw.decode().removeprefix('./')
        if inside(path, HISTORY):
            category = 'three_protected_history_dirs'
        elif inside(path, PARALLEL):
            category = 'parallel_work_read_only'
        elif inside(path, [MAINT]):
            category = 'this_relock_records_backups_and_negative'
        elif inside(path, ['求解器/内核维护']):
            category = 'older_maintenance_archive'
        elif path == '求解器/规格/修订记录.md':
            category = 'revision_history'
        else:
            category = 'other_review_required'
        content = (REPO / path).read_bytes()
        occurrences = content.count(old.encode())
        lines = [i for i, line in enumerate(content.splitlines(), 1) if old.encode() in line]
        rows.append({'path': path, 'category': category, 'occurrences': occurrences, 'lines': lines})
    counts = collections.Counter(r['category'] for r in rows)
    save('old-sha-scan.json', {'time': now(), 'argv': argv, 'returncode': proc.returncode,
         'excluded_audit_output': str(OUT.relative_to(REPO)), 'files': rows, 'file_count': len(rows),
         'occurrences': sum(r['occurrences'] for r in rows), 'category_counts': dict(counts),
         'outside_three_history_file_count': sum(r['category'] != 'three_protected_history_dirs' for r in rows),
         'outside_three_history_occurrences': sum(r['occurrences'] for r in rows if r['category'] != 'three_protected_history_dirs')})
    print(json.dumps({'old_sha_category_file_counts': dict(counts), 'rg_exit': proc.returncode}, ensure_ascii=False), flush=True)

def scope_audit(name):
    rows = status(name)
    refs = load('references-audit.json')
    expected = {r['path'] for r in refs['input_changes']} | {CAT,
        '求解器/数据/候选B/来源清单.json', '求解器/数据/候选B/校验报告.md', '求解器/数据/候选B/验证记录.md',
        '求解器/数据/样例/check_examples.py', '求解器/规格/check_revision.py',
        '求解器/规格/修订记录.md', '求解器/规格/运行语义.md'}
    groups = {'business': [], 'maintenance': [], 'parallel': [], 'out_of_scope': []}
    for row in rows:
        p = row['path']
        category = 'business' if p in expected else 'maintenance' if inside(p, [MAINT]) else 'parallel' if inside(p, PARALLEL) else 'out_of_scope'
        groups[category].append(row)
    changed_business = {r['path'] for r in groups['business']}
    save(name + '-scope.json', {'counts': {k: len(v) for k, v in groups.items()}, **groups,
         'missing_expected': sorted(expected - changed_business),
         'staged': [r for r in rows if r['status'][0] not in [' ', '?']],
         'head': git('rev-parse', 'HEAD').decode().strip()})
    print(json.dumps({'scope_counts': {k: len(v) for k, v in groups.items()}, 'out_of_scope': groups['out_of_scope']}, ensure_ascii=False), flush=True)

def extra_audit():
    # Search all JSON input documents, not merely the relock seat's file list.
    argv = ['rg', '--hidden', '--no-ignore', '-l', '-0', '-g', '*.json',
            '-g', '!.git/**', '-g', '!**/target/**', '-g', '!**/__pycache__/**',
            '-g', '!' + str(OUT.relative_to(REPO)) + '/**', '"catalog"', '.']
    scan = subprocess.run(argv, cwd=REPO, capture_output=True)
    rows, errors = [], []
    known = {r['path'] for r in load('references-audit.json')['input_changes']}
    for raw in scan.stdout.split(b'\0'):
        if not raw:
            continue
        path = raw.decode().removeprefix('./')
        try:
            doc = json.loads((REPO / path).read_bytes())
        except (ValueError, OSError) as error:
            errors.append({'path': path, 'error': str(error)})
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get('catalog'), dict):
            continue
        ref = doc['catalog']
        if not ('path' in ref and 'sha256' in ref):
            continue
        if path in known:
            category = 'active_sample_or_fixture'
        elif inside(path, HISTORY):
            category = 'three_protected_history_dirs'
        elif inside(path, PARALLEL):
            category = 'parallel_work'
        elif inside(path, ['求解器/内核维护']):
            category = 'maintenance_archive'
        elif inside(path, ['求解器/规格/复核', '求解器/会议成果', '求解器/规格/第7轮修订验证/迁移前样例',
                           '求解器/规格/推导/证据-v2-loop-否证', '求解器/规格/推导/证据-v2-phase-否证']):
            category = 'spec_review_or_meeting_archive'
        else:
            category = 'other_review_required'
        rows.append({'path': path, 'schema': doc.get('schema'), 'category': category, 'catalog': ref,
                     'current_sha': ref['sha256'] == load('catalog-audit.json')['new_sha256']})
    save('all-catalog-inputs.json', {'argv': argv, 'returncode': scan.returncode,
        'stderr': scan.stderr.decode(), 'count': len(rows), 'category_counts': dict(collections.Counter(r['category'] for r in rows)),
        'files': rows, 'parse_errors': errors})
    initial = load('initial-history.json')['files']
    history_comparisons = {}
    for name in ['initial-history.json', 'delivery-history.json']:
        original = json.loads((OUT.parent / name).read_text())
        mapped = {'求解器/' + p: v for p, v in original['files'].items()}
        history_comparisons[name] = diff_maps(initial, mapped)
    save('relock-history-crosscheck.json', history_comparisons)
    save('head-context.json', {
        'independent_head': load('baseline.json')['head'],
        'relock_head': (OUT.parent / 'initial-head.txt').read_text().strip(),
        'intervening_commits': git('log', '--format=%H %s', '8ab2324..' + load('baseline.json')['head']).decode(),
        'intervening_paths': git('diff', '--name-status', '8ab2324', load('baseline.json')['head']).decode(),
        'dfc35cd_in_head': subprocess.run(['git', 'merge-base', '--is-ancestor', 'dfc35cd', load('baseline.json')['head']], cwd=REPO).returncode == 0})
    print(json.dumps({'input_inventory': dict(collections.Counter(r['category'] for r in rows)),
                      'input_parse_errors': errors, 'history_crosscheck': history_comparisons}, ensure_ascii=False), flush=True)

def business_audit():
    cat = load('catalog-audit.json')
    old = json.loads(head_bytes(CAT))
    current = json.loads((REPO / CAT).read_text())
    old_source = old['sources'][2]['sha256']
    new_source = current['sources'][2]['sha256']
    checks = []
    for entry in load('references-audit.json')['input_changes']:
        checks.append({'path': entry['path'], 'check': 'Only catalog SHA bytes replaced',
                       'passed': entry['bytes_only_sha_replaced'] and entry['changed_leaves'] == ['.catalog.sha256']})
    replacements = {
        '求解器/数据/候选B/来源清单.json': [(old_source, new_source), (cat['old_sha256'], cat['new_sha256'])],
        '求解器/数据/候选B/校验报告.md': [(old['version'], current['version']), (old['constraints'][32]['text'], current['constraints'][32]['text'])],
        '求解器/数据/样例/check_examples.py': [(old_source, new_source)],
        '求解器/规格/运行语义.md': [(old_source, new_source)],
        '求解器/规格/check_revision.py': [('内核维护/2026-09-22e/只读文件指纹.json', '内核维护/2026-09-22g/只读文件指纹.json')]}
    for path, replacements_for_path in replacements.items():
        data = head_bytes(path)
        for before, after in replacements_for_path:
            data = data.replace(before.encode(), after.encode())
        checks.append({'path': path, 'check': 'Exact reviewed replacements', 'passed': data == (REPO / path).read_bytes()})
    path = '求解器/数据/候选B/验证记录.md'
    old_lines, new_lines = head_bytes(path).decode().splitlines(), (REPO / path).read_text().splitlines()
    checks.append({'path': path, 'check': 'Only current-status line changed; r24 version and retained r23 count explicitly attributed',
                   'passed': len(old_lines) == len(new_lines) and [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b] == [2]
                   and current['version'] in new_lines[2] and '检查计数沿用' in new_lines[2]})
    path = '求解器/规格/修订记录.md'
    data = head_bytes(path)
    live = (REPO / path).read_bytes()
    checks.append({'path': path, 'check': 'Existing revision history preserved, r24 section appended',
                   'passed': live.startswith(data) and live[len(data):].decode().startswith('\n## 2026-09-22 r24：')})
    checks.append({'path': CAT, 'check': 'Independent full reconstruction equals live bytes; four expected leaf changes',
                   'passed': cat['byte_equal'] and cat['head_changed_leaves'] == ['.constraints[32].text', '.sources[2].sha256', '.sources[2].lines[75]', '.version']})
    save('business-audit.json', {'count': len(checks), 'checks': checks, 'failures': [c for c in checks if not c['passed']]})
    print(json.dumps({'business_count': len(checks), 'failures': [c for c in checks if not c['passed']]}, ensure_ascii=False), flush=True)

def guard(name):
    h = history_snapshot(name)
    delta = diff_maps(load('initial-history.json')['files'], h['files'])
    save(name + '-history-diff.json', delta)
    a = active_snapshot(name)
    ad = diff_maps(load('initial-active.json'), a)
    save(name + '-active-diff.json', ad)
    assert not any(delta.values()), 'Historical bytes changed; stop, do not restore'
    # Concurrent unrelated research may advance HEAD. Never hide its diff, but
    # continue only when all audited sources, build inputs and fixtures are stable.
    source_rows = load('references-audit.json')['candidate_sources']
    candidate_sources = {str(Path(r['path']).relative_to(REPO)) for r in source_rows if Path(r['path']).is_relative_to(REPO)}
    assert all(digest(Path(r['path'])) == r['actual_sha256'] for r in source_rows), 'Candidate source bytes changed'
    def relevant(p):
        return p in set(SOURCES) | candidate_sources | {'求解器/Cargo.toml', '求解器/Cargo.lock'} or inside(p, ['求解器/crates', '求解器/数据', '求解器/规格'])
    relevant_delta = {k: [p for p in v if relevant(p)] for k, v in ad.items()}
    current_head = git('rev-parse', 'HEAD').decode().strip()
    head_paths = git('diff', '--name-only', '-z', load('baseline.json')['head'], current_head).decode().split('\0')
    save(name + '-concurrency.json', {'head': current_head, 'active_delta': ad,
         'relevant_active_delta': relevant_delta, 'head_changed_paths': [p for p in head_paths if p],
         'relevant_head_changes': [p for p in head_paths if p and relevant(p)]})
    assert not any(relevant_delta.values()), 'Audited dependency bytes changed; stop, do not restore'
    assert not any(p and relevant(p) for p in head_paths), 'HEAD changed audited dependencies'

def run_step(name, argv, expected=0):
    guard(name + '-before')
    started = now()
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['CARGO_TARGET_DIR'] = str(OUT / 'target')
    env['TMPDIR'] = str(OUT / 'tmp')
    Path(env['TMPDIR']).mkdir(exist_ok=True)
    start = time.monotonic()
    with (OUT / (name + '.stdout.log')).open('wb') as out, (OUT / (name + '.stderr.log')).open('wb') as err:
        process = subprocess.run(argv, cwd=ROOT, env=env, stdout=out, stderr=err)
    result = {'name': name, 'argv': argv, 'cwd': str(ROOT), 'started': started,
              'finished': now(), 'seconds': time.monotonic() - start, 'exit_code': process.returncode,
              'expected_exit_code': expected, 'passed': process.returncode == expected,
              'environment': {k: env[k] for k in ['CARGO_TARGET_DIR', 'PYTHONDONTWRITEBYTECODE', 'TMPDIR']}}
    save(name + '.result.json', result)
    with (OUT / 'commands.jsonl').open('a') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')
    guard(name + '-after')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result

def suite(start_at=None):
    commands = [('cargo-build', ['cargo', 'build', '--workspace', '-j', '4']),
                ('cargo-check', ['cargo', 'check', '--workspace', '-j', '4']),
                ('cargo-clippy', ['cargo', 'clippy', '--workspace', '-j', '4'])]
    for name, package, selection in [('kernel-lib', 'kernel', ['--lib']), ('topology-lib', 'topology', ['--lib']),
            ('kernel-reference', 'kernel', ['--test', 'reference']), ('topology-validation', 'topology', ['--test', 'validation']),
            ('kernel-doc', 'kernel', ['--doc']), ('topology-doc', 'topology', ['--doc'])]:
        commands.append((name, ['cargo', 'test', '-p', package, *selection, '-j', '4', '--', '--test-threads=1']))
    commands.extend([('catalog-verify', ['python3', '-B', '数据/工具/formal_catalog.py']),
                     ('catalog-regressions', ['python3', '-B', '数据/工具/test_formal_catalog.py'])])
    if start_at:
        commands = commands[next(i for i, (n, _) in enumerate(commands) if n == start_at):]
    for name, argv in commands:
        run_step(name, argv)

def positive():
    directory = OUT / 'positive'
    directory.mkdir(exist_ok=True)
    source = ROOT / '数据/样例/任务7内核/无线多格全收.json'
    doc = json.loads(source.read_bytes())
    for ref in [doc['catalog'], doc['parameters']['axis_registry']]:
        ref['path'] = str((source.parent / ref['path']).resolve())
    def put(name, obj):
        (directory / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    put('input.json', doc)
    binary = OUT / 'target/debug/kernel'
    config = ROOT / '规格/内核配置-v1.json'
    rows = []
    for name, argv, expected_status in [
        ('positive-seed', ['seed', str(directory / 'input.json'), '--out', str(directory / 'seed.json')], None),
        ('positive-check', ['check', str(directory / 'seed.json')], 'input_checked'),
        ('positive-run', ['run', str(directory / 'seed.json'), '--ticks', '6', '--out', str(directory / 'run.json')], 'completed'),
        ('positive-verify-record', ['verify-record', str(directory / 'run.json')], 'input_checked')]:
        result = run_step(name, [str(binary), *argv, '--config', str(config)])
        output = json.loads((OUT / (name + '.stdout.log')).read_text())
        rows.append({'name': name, 'exit_code': result['exit_code'], 'status': output.get('status'),
                     'passed': result['passed'] and output.get('status') == expected_status})
    stale = copy.deepcopy(doc)
    stale['catalog']['sha256'] = load('catalog-audit.json')['old_sha256']
    put('stale-catalog.json', stale)
    result = run_step('stale-catalog-negative', [str(binary), 'seed', str(directory / 'stale-catalog.json'), '--config', str(config)], 2)
    output = json.loads((OUT / 'stale-catalog-negative.stdout.log').read_text())
    reasons = [x for x in output.get('open_items', []) if '源文件指纹不符' in x and str(REPO / CAT) in x]
    save('positive-validation.json', {'binary': str(binary), 'binary_sha256': digest(binary),
         'source_input': str(source), 'source_sha256': digest(source), 'positive': rows,
         'seed_schema': json.loads((directory / 'seed.json').read_text())['schema'],
         'run_status': json.loads((directory / 'run.json').read_text())['status'],
         'negative': {'exit_code': result['exit_code'], 'status': output.get('status'), 'reason': reasons,
                      'passed': result['passed'] and output.get('status') == 'invalid_input' and bool(reasons),
                      'only_changed_field': leaf_diff(doc, stale)}, 'ticks': 6})

if __name__ == '__main__':
    command = sys.argv[1]
    if command == 'baseline':
        baseline()
    elif command == 'audit':
        history_head()
        catalog_audit()
        references_audit()
        old_sha_scan()
        scope_audit('audited')
    elif command == 'suite':
        suite(sys.argv[2] if len(sys.argv) > 2 else None)
    elif command == 'references':
        references_audit()
        old_sha_scan()
        scope_audit('audited')
    elif command == 'positive':
        positive()
    elif command == 'extra':
        extra_audit()
        business_audit()
    elif command == 'finish':
        guard('final')
        scope_audit('final')
        save('final-head-check.json', {
            'head': git('rev-parse', 'HEAD').decode().strip(),
            'history_diff': git('diff', 'HEAD', '--name-status', '--', *HISTORY).decode(),
            'head_history_changes_since_baseline': git('diff', '--name-status', load('baseline.json')['head'], 'HEAD', '--', *HISTORY).decode(),
            'formal_sources_equal_current_head': {p: (REPO / p).read_bytes() == git('show', 'HEAD:' + p) for p in SOURCES},
            'commits_since_relock': git('log', '--format=%H %s', '--name-status', '8ab2324..HEAD').decode()})
    else:
        raise SystemExit('Unknown command')
