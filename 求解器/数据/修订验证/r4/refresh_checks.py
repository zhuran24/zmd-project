#!/usr/bin/env python3
"""记录并行依赖快照并复验；其它线的生成报告重定向到本轮目录。"""
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SAMPLES = ROOT/'数据/样例'


def fingerprints():
    paths = [ROOT/'数据/正式静态目录.json']
    paths += [p for folder in [ROOT/'规格', SAMPLES] for p in folder.iterdir()
              if p.suffix in {'.py', '.md', '.json'} and p.is_file()
              and p.name not in {'检查结果.json', '混做粉碎机两下游-运行记录.json'}]
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def command(name, args):
    result = subprocess.run([sys.executable, '-B', *map(str, args)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (HERE/name).write_bytes(result.stdout)
    if result.returncode:
        raise AssertionError(f'{name} 失败：退出 {result.returncode}')


def main():
    before = fingerprints()
    command('目录回源.log', [ROOT/'数据/工具/formal_catalog.py'])
    command('规格自查.log', [ROOT/'规格/check_revision.py'])
    command('样例检查.log', [SAMPLES/'check_examples.py', '--self-test', '--report', HERE/'样例检查.json'])
    sys.path.insert(0, str(SAMPLES))
    golden = importlib.import_module('check_golden_trace')
    golden.OUTPUT = HERE/'黄金轨迹运行记录.json'
    with contextlib.redirect_stdout(io.StringIO()) as output:
        golden.main()
    (HERE/'黄金轨迹.log').write_text(output.getvalue())
    runtime = importlib.import_module('test_runtime_input')
    original_write = Path.write_text
    original_target = ROOT/'规格/内核输入修订验证-r3/运行回归结果.json'

    def redirected_write(path, data, *args, **kwargs):
        if path != original_target:
            raise AssertionError(f'运行输入检查出现意外写入：{path}')
        return original_write(HERE/'运行输入回归结果.json', data, *args, **kwargs)

    try:
        Path.write_text = redirected_write
        with contextlib.redirect_stdout(io.StringIO()) as output:
            runtime.main()
    finally:
        Path.write_text = original_write
    (HERE/'运行输入回归.log').write_text(output.getvalue() +
        f'本轮写入已重定向至 {HERE / "运行输入回归结果.json"}；未覆盖原脚本显示的路径。\n')
    command('契约自查.log', [ROOT/'数据/工具/check_revision.py', '--output-dir', HERE])
    after = fingerprints()
    if before != after:
        raise AssertionError('验证期间依赖发生并行改动，须重新运行')
    (HERE/'验证依赖指纹.json').write_text(json.dumps({
        'status': '通过', 'unchanged_during_checks': True, 'fingerprints': after,
        'scope': '本次实际读取的生产依赖；不把并行线改动记为本席修改'}, ensure_ascii=False, indent=2)+'\n')
    print('当前依赖快照稳定；目录、规格、覆盖表、样例、黄金轨迹、输入输出回归均通过。')


if __name__ == '__main__':
    main()
