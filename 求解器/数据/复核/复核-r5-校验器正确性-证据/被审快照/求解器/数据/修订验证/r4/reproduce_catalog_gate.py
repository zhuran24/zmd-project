#!/usr/bin/env python3
"""隔离复现已报告的漏检：修改副本，核独立命令和 Rust 内置字节门禁。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPO = ROOT.parent
SOURCE_NAMES = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']
CASES = [
    ('unused_recipe_duration', 'recipes', '精炼-蓝铁粉末', ['duration', 'value'], '2'),
    ('used_recipe_input', 'recipes', '研磨-致密蓝铁', ['inputs', '蓝铁粉末', 'value'], '3'),
    ('power_coverage_width', 'units', '供电桩', ['coverage', 'width', 'value'], '13'),
    ('core_port_category', 'units', '协议核心', ['ports', 'input_count', 'category'], '候选'),
]


def main():
    original = (ROOT/'数据/正式静态目录.json').read_bytes()
    results = []
    with tempfile.TemporaryDirectory(prefix='catalog-gate-', dir=ROOT/'target') as directory:
        repo = Path(directory)
        solver = repo/'求解器'
        (solver/'数据/工具').mkdir(parents=True)
        for name in SOURCE_NAMES:
            shutil.copyfile(REPO/name, repo/name)
        for name in ['Cargo.toml', 'Cargo.lock']:
            shutil.copyfile(ROOT/name, solver/name)
        shutil.copytree(ROOT/'crates', solver/'crates')
        shutil.copytree(ROOT/'数据/候选B', solver/'数据/候选B')
        for name in ['formal_catalog.py', 'formal_units.py', 'test_formal_catalog.py']:
            shutil.copyfile(ROOT/'数据/工具'/name, solver/'数据/工具'/name)
        target = solver/'数据/正式静态目录.json'
        env = {**os.environ, 'CARGO_HOME': str(ROOT/'.cargo-home'),
               'CARGO_TARGET_DIR': str(ROOT/'target/r4-isolated-catalog'),
               'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(repo)}
        cargo = ['cargo', 'test', '--offline', '--locked', '--manifest-path', str(solver/'Cargo.toml'),
                 'catalog_is_checked_against_live_formal_sources', '--', '--exact']
        for name, section, identity, fields, replacement in [
                ('baseline', None, None, [], None), *CASES, ('restored', None, None, [], None)]:
            changed = json.loads(original)
            if section:
                field = next(row for row in changed[section] if row['id'] == identity)
                for key in fields[:-1]:
                    field = field[key]
                field[fields[-1]] = replacement
            target.write_text(json.dumps(changed, ensure_ascii=False, indent=2)+'\n')
            direct = subprocess.run(['python', '-B', str(ROOT/'数据/工具/formal_catalog.py'),
                                     '--catalog', str(target)], capture_output=True, env=env)
            compiled = subprocess.run(cargo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            (HERE/f'{name}-cargo-gate.log').write_bytes(compiled.stdout)
            expected = section is None
            if (direct.returncode == 0) != expected or (compiled.returncode == 0) != expected:
                raise AssertionError(f'{name} 门禁结果不符')
            diagnostic = f'{section}.{identity}.' + '.'.join(fields) if section else None
            if diagnostic:
                if diagnostic not in direct.stderr.decode() or diagnostic not in compiled.stdout.decode():
                    raise AssertionError(f'{name} 没有给出对应字段诊断')
            results.append({'case': name, 'expected': '接受' if expected else '拒绝',
                            'direct_exit_code': direct.returncode, 'cargo_exit_code': compiled.returncode,
                            'diagnostic': direct.stderr.decode().strip(),
                            'catalog_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                            'log': f'{name}-cargo-gate.log'})
    if (ROOT/'数据/正式静态目录.json').read_bytes() != original:
        raise AssertionError('生产目录被改动')
    (HERE/'隔离门禁结果.json').write_text(json.dumps({
        'status': '通过', 'scope': '独立命令及 cargo 实时回源单项；完整正常目录测试另见候选B/cargo-test.log',
        'production_catalog_unchanged': True, 'results': results}, ensure_ascii=False, indent=2)+'\n')
    print('隔离门禁：正常及还原目录接受；四个已报告变异均被独立命令及 cargo 拒绝。')


if __name__ == '__main__':
    main()
