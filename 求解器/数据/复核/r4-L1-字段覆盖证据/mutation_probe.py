#!/usr/bin/env python3
"""只改复核目录中的隔离目录副本，核验既有回源程序和测试的漏检范围。"""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / 'snapshot'
TEST_REPO = HERE / 'testrepo'
if not TEST_REPO.exists():
    shutil.copytree(SNAPSHOT, TEST_REPO)
if not (HERE / 'cargo-home').exists():
    # 原缓存只读复制；cargo 的锁文件和构建产物留在复核目录。
    shutil.copytree(HERE.parents[2] / '.cargo-home', HERE / 'cargo-home')
TARGET = TEST_REPO / '求解器/数据/正式静态目录.json'
original = (SNAPSHOT / '求解器/数据/正式静态目录.json').read_bytes()
catalog = json.loads(original)
spec = importlib.util.spec_from_file_location('formal_catalog', SNAPSHOT / '求解器/数据/工具/formal_catalog.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
env = os.environ.copy()
env.update(CARGO_HOME=str(HERE/'cargo-home'), CARGO_TARGET_DIR=str(HERE/'target'),
           TMPDIR=str(HERE), PYTHONDONTWRITEBYTECODE='1')
results = []
cases = [
    ('unused_recipe_duration', '配方 精炼-蓝铁粉末 的 duration.value：1 → 2', True),
    ('unit_width', '粉碎机 dimensions.width.value：3 → 4', False),
    ('unit_capacity', '协议核心库存 capacity.value：80000 → 80001', False),
    ('power_coverage', '供电桩 coverage.width.value：12 → 13', True),
    ('port_category', '协议核心 ports.input_count.category：条文直引 → 候选', True),
    ('lower_bound', '粉碎机 static_lower_bounds.machines.value：68 → 67', False),
    ('cooldown_control', '对照：箱体 transfer.cooldown_ticks.value：5 → 4', False),
]
try:
    for name, description, cargo in cases:
        changed = copy.deepcopy(catalog)
        units = {u['id']:u for u in changed['units']}
        if name == 'unused_recipe_duration':
            next(r for r in changed['recipes'] if r['id']=='精炼-蓝铁粉末')['duration']['value']='2'
        elif name == 'unit_width': units['粉碎机']['dimensions']['width']['value']='4'
        elif name == 'unit_capacity': units['协议核心']['inventory'][0]['capacity']['value']='80001'
        elif name == 'power_coverage': units['供电桩']['coverage']['width']['value']='13'
        elif name == 'port_category': units['协议核心']['ports']['input_count']['category']='候选'
        elif name == 'lower_bound': units['粉碎机']['static_lower_bounds']['machines']['value']='67'
        else: units['协议储存箱']['transfer']['cooldown_ticks']['value']='4'
        row = dict(case=name,description=description)
        try:
            module.verify(changed, SNAPSHOT)
            row['formal_verify']='accepted'
        except AssertionError:
            row['formal_verify']='rejected'
        if cargo:
            TARGET.write_text(json.dumps(changed,ensure_ascii=False,indent=2)+'\n')
            result = subprocess.run(['cargo','test','--offline','--locked','--manifest-path',
                                     str(TEST_REPO/'求解器/Cargo.toml')], env=env,
                                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False)
            (HERE/(name+'-cargo-test.log')).write_bytes(result.stdout)
            row['cargo_exit_code']=result.returncode
            row['cargo_reported_pass_counts']=[line.strip() for line in result.stdout.decode().splitlines() if line.startswith('test result:')]
        results.append(row)
finally:
    TARGET.write_bytes(original)
(HERE/'回源变异结果.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False,indent=2))
