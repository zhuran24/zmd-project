"""重跑第7轮规格与共享依赖检查；日志限本目录；黄金重算按既有程序更新C线运行记录，其余依赖只读。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
EXAMPLES = ROOT / '求解器/数据/样例'


def main():
    python = [sys.executable, '-B']
    commands = [
        ('规格自查', python + [str(BASE.parent/'check_revision.py')]),
        ('原转移回归', python + [str(BASE.parent/'第三轮任务验证/核对转移回归.py')]),
        ('前轮修订回归', python + [str(BASE.parent/'第6轮修订验证/核对修订回归.py')]),
        ('修订回归', python + [str(BASE/'核对修订回归.py')]),
        ('正式目录', python + [str(ROOT/'求解器/数据/工具/formal_catalog.py')]),
        ('cargo-test', ['cargo', 'test', '--locked', '--offline', '--manifest-path', str(ROOT/'求解器/Cargo.toml')]),
        ('候选B校验', ['cargo', 'run', '--locked', '--offline', '--quiet', '--manifest-path', str(ROOT/'求解器/Cargo.toml'), '--', str(ROOT/'求解器/数据/候选B/contract.json')]),
    ]
    commands += [
        ('样例检查', python + [str(EXAMPLES/'check_examples.py'), '--self-test']),
        ('黄金记录再生成', python + [str(EXAMPLES/'check_golden_trace.py')]),
        ('样例黄金完整核验', python + [str(BASE/'核对样例兼容.py')]),
    ]
    filenames = {'规格自查': '规格自查结果.json', '原转移回归': '原转移回归结果.json',
                 '修订回归': '修订回归结果.json', '前轮修订回归': '前轮修订回归结果.json', '正式目录': '正式目录.log',
                 'cargo-test': 'cargo-test.log', '候选B校验': '候选B校验报告.md',
                 '样例检查': '样例检查结果.json', '黄金记录再生成': '黄金记录重算结果.json',
                 '样例黄金完整核验': '黄金完整核验结果.json'}
    results = []
    for name, command in commands:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_TARGET_DIR': str(ROOT/'求解器/target-spec-r7')})
        output = BASE/filenames[name]
        output.write_text(result.stdout + (result.stderr if name == 'cargo-test' else ''))
        results.append({'name': name, 'command': command, 'exit_code': result.returncode,
                        'output': str(output), 'stderr': result.stderr})
        print(name, result.returncode, flush=True)
    protected = json.loads((BASE/'开工只读指纹.json').read_text())
    changed = [path for path, value in protected.items() if not Path(path).is_file() or hashlib.sha256(Path(path).read_bytes()).hexdigest() != value]
    initial_sim = {path for path in protected if path.startswith(str(ROOT/'模拟器')+'/')}
    current_sim = {str(path) for path in (ROOT/'模拟器').rglob('*') if path.is_file()}
    essential = results
    status = 'PASS' if all(row['exit_code'] == 0 for row in essential) and not changed and initial_sim == current_sim else 'FAIL'
    report = {'status': status, 'scope': '规格本轮检查与C线原产物均实测；不从有限轨迹外推全称认证',
              'commands': results, 'readonly_count': len(protected), 'readonly_changes': changed,
              'simulator_file_set_unchanged': initial_sim == current_sim}
    (BASE/'检查汇总.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    return 0 if status != 'FAIL' else 1


if __name__ == '__main__':
    raise SystemExit(main())
