#!/usr/bin/env python3
"""第四轮只读复核：独立回源、候选复算及隔离目录变异。"""
import ast
import copy
import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOLVER = ROOT / '求解器'
DATA = SOLVER / '数据'
CATALOG = json.loads((DATA / '正式静态目录.json').read_text())
CONTRACT = json.loads((DATA / '候选B/contract.json').read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def quantity(value, category='条文直引'):
    return {'value': str(F(value)), 'category': category}


def formal_module():
    spec = importlib.util.spec_from_file_location('formal_catalog', DATA / '工具/formal_catalog.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command(args, name, env=None, cwd=ROOT):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True)
    (OUT / (name + '.stdout')).write_bytes(result.stdout)
    (OUT / (name + '.stderr')).write_bytes(result.stderr)
    return result


def independent_check():
    # 配方逐条从正式配方节读出，不从候选或 Rust 常量反推。
    formal = []
    for line in (ROOT / '《明日方舟：终末地》游戏规则.txt').read_text().split('配方\n\n', 1)[1].splitlines():
        if not line:
            continue
        if '→' not in line:
            kind = line
            continue
        left, right, duration = re.fullmatch(r'(.+) → (.+)，(\d+) tick', line).groups()
        def terms(text):
            return {item: quantity(n) for n, item in (part.split(' ', 1) for part in text.split(' ＋ '))}
        formal.append({'kind': kind, 'inputs': terms(left), 'outputs': terms(right), 'duration': quantity(duration)})
    projected = [{k: r[k] for k in ['kind', 'inputs', 'outputs', 'duration']} for r in CATALOG['recipes']]
    assert formal == projected
    recipes = {r['id']: r for r in CATALOG['recipes']}
    units = {u['id']: u for u in CATALOG['units']}
    feeds = CONTRACT['logical_feeds']
    incoming, outgoing = defaultdict(dict), defaultdict(dict)
    flows = defaultdict(F)
    for e in feeds:
        rate = F(e['planned_rate']['value'])
        flows[e['item']] += rate
        for mapping, side in [(incoming, 'target'), (outgoing, 'source')]:
            ports = mapping[e[side]]
            key = e[side + '_port']
            ports[key] = ports.get(key, F(0)) + rate
    assert all(rate <= 1 for mapping in [incoming, outgoing] for ports in mapping.values() for rate in ports.values())
    loads = {}
    for m in CONTRACT['machines']:
        loads[m['id']] = str(sum(F(p['planned_batch_rate']['value']) * F(recipes[p['recipe']]['duration']['value']) for p in m['recipes']))
        for plan in m['recipes']:
            rec = recipes[plan['recipe']]
            for side, key in [('target', 'inputs'), ('source', 'outputs')]:
                for item, q in rec[key].items():
                    observed = sum(F(e['planned_rate']['value']) for e in feeds if e[side] == m['id'] and e[side + '_recipe'] == plan['recipe'] and e['item'] == item)
                    assert observed == F(plan['planned_batch_rate']['value']) * F(q['value'])
        assert len(incoming[m['id']]) <= F(units[m['kind']]['ports']['input_count']['value'])
        assert len(outgoing[m['id']]) <= F(units[m['kind']]['ports']['output_count']['value'])
    assert all(F(x) <= 1 for x in loads.values())
    for item, q in CATALOG['static_checks']['material_flow'].items():
        assert flows[item] >= F(q['value'])
    # 逐机静态下限直接与正式约束对应，不依靠旧常量表。
    constraints = (ROOT / '求解约束.txt').read_text()
    machine_line = re.search(r'^机型下限：(.*)$', constraints, re.M).group(1)
    channel_line = re.search(r'^通道下限：(.*)$', constraints, re.M).group(1)
    input_text, output_text = channel_line.split('；取货通道至少')
    for u in CATALOG['units']:
        if u['family'] != 'manufacturing':
            continue
        kind = u['id']
        for field, text, pattern in [('machines', machine_line, kind + r' ≥(\d+)'), ('input_channels', input_text, kind + r' (\d+)'), ('output_channels', output_text, kind + r' (\d+)')]:
            expected = re.search(pattern, text).group(1)
            assert u['static_lower_bounds'][field] == quantity(expected)
    source = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
    rows = list(csv.DictReader((source / 'channels.csv').open()))
    assert len(rows) == len(feeds)
    for row, e in zip(rows, feeds):
        assert F(row['件每20tick']) / 20 == F(e['planned_rate']['value'])
        assert row['物品'] == e['item']
        assert row['是否满速'] == ('是' if e['planned_full_speed'] else '否')
        assert e['source_recipe'] == (row['源配方'] or None)
        assert e['target_recipe'] == (row['目标配方'] or None)
        if row['源机器id'] != '仓库出矿口':
            assert e['source'] == row['源机器id']
        assert e['target'] == ('CORE' if row['目标机器id'] == '协议核心' else row['目标机器id'])
    # 对整份报告逐行解析，避免把截取的标题当作运行证据。
    baseline = command([str(OUT / 'target/debug/topology'), str(DATA / '候选B/contract.json')], '候选B校验')
    assert baseline.returncode == 0
    assert baseline.stdout == (DATA / '候选B/校验报告.md').read_bytes()
    report = baseline.stdout.decode()
    section_counts = {name: int(n) for name, n in re.findall(r'^## (能检且通过|能检且不通过|不能静态检)（(\d+) 项', report, re.M)}
    sections = re.split(r'^## ', report, flags=re.M)[1:]
    for section in sections:
        expected = int(re.search(r'（(\d+) 项', section).group(1))
        actual = sum(line.startswith('| ') for line in section.splitlines()) - (1 if expected else 0)
        assert actual == expected
    metrics = {'status': '通过', 'formal_recipes': len(formal), 'formal_lower_bound_values': 27,
               'machines': len(CONTRACT['machines']), 'machine_counts': dict(Counter(m['kind'] for m in CONTRACT['machines'])),
               'area': str(sum(F(m['area']['value']) for m in CONTRACT['machines'])), 'logical_feeds': len(feeds),
               'S': sum(len(v) for v in outgoing.values()), 'R': sum(len(v) for v in incoming.values()),
               'full_speed_rows': sum(e['planned_full_speed'] for e in feeds), 'flow': {k: str(v) for k, v in flows.items()},
               'loads': loads, 'cli_exit_code': baseline.returncode, 'report_counts': section_counts,
               'report_byte_identical': True, 'report_sha256': hashlib.sha256(baseline.stdout).hexdigest()}
    save('独立核验.json', metrics)
    return metrics


def catalog_mutations():
    module = formal_module()
    module.verify(CATALOG)
    variants = {}
    def add(name, change):
        c = copy.deepcopy(CATALOG)
        change(c)
        try:
            module.verify(c)
        except AssertionError as exc:
            result = {'accepted': False, 'error': str(exc)}
        else:
            result = {'accepted': True}
        variants[name] = result
        save(name + '.json', c)
    def recipe(c):
        next(r for r in c['recipes'] if r['id'] == '研磨-致密蓝铁')['duration']['value'] = '1/2'
    def coverage(c):
        next(u for u in c['units'] if u['id'] == '供电桩')['coverage']['width']['value'] = '13'
    def lower(c):
        next(u for u in c['units'] if u['id'] == '粉碎机')['static_lower_bounds']['machines']['value'] = '1'
    def threshold(c):
        c['static_checks']['constants']['transport_s']['quantity']['value'] = '1'
    add('变异-研磨耗时', recipe)
    add('变异-供电宽度', coverage)
    add('变异-机型下限', lower)
    add('对照-运输阈值', threshold)
    save('目录变异结果.json', variants)
    return variants


def copied_workspace(variant='变异-研磨耗时'):
    # 原源码和三份正式文件仅复制；变异只落在复核目录中的目录副本。
    repo = OUT / '隔离副本'
    solver = repo / '求解器'
    for name in formal_module().SOURCE_NAMES:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    for rel in ['Cargo.toml', 'Cargo.lock', 'crates/topology/Cargo.toml', 'crates/topology/src/lib.rs', 'crates/topology/src/main.rs', 'crates/topology/tests/validation.rs', '数据/工具/formal_catalog.py', '数据/候选B/contract.json']:
        target = solver / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOLVER / rel, target)
    shutil.copy2(OUT / (variant + '.json'), solver / '数据/正式静态目录.json')
    # 防止复制旧时间戳导致 Cargo 复用上一次内置目录。
    (solver / '数据/正式静态目录.json').touch()
    env = dict(os.environ, CARGO_HOME=str(OUT / 'cargo-home'), CARGO_TARGET_DIR=str(OUT / 'mutated-target'), TMPDIR=str(OUT), PYTHONDONTWRITEBYTECODE='1')
    result = command(['cargo', 'test', '--offline', '--locked'], variant + '-cargo-test', env, solver)
    cli = command([str(OUT / 'mutated-target/debug/topology'), str(solver / '数据/候选B/contract.json')], variant + '-候选B校验', env, solver)
    name = '隔离变异运行.json' if variant == '变异-研磨耗时' else '供电宽度变异运行.json'
    mutation = '研磨-致密蓝铁.duration.value: 1 → 1/2' if variant == '变异-研磨耗时' else '供电桩.coverage.width.value: 12 → 13'
    save(name, {'mutation': mutation, 'cargo_test_exit_code': result.returncode,
                              'cargo_test_summaries': re.findall(r'^test result:.*$', result.stdout.decode(), re.M),
                              'cli_exit_code': cli.returncode,
                              'cli_counts': dict(re.findall(r'^## (能检且通过|能检且不通过|不能静态检)（(\d+) 项', cli.stdout.decode(), re.M))})


if __name__ == '__main__':
    metrics = independent_check()
    mutations = catalog_mutations()
    copied_workspace()
    copied_workspace('变异-供电宽度')
    print(json.dumps({'baseline': {k: v for k, v in metrics.items() if k not in ['loads', 'flow']}, 'mutations': mutations}, ensure_ascii=False))
