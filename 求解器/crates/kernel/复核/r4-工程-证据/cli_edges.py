"""公开入口边界复核：预算、数值及结构错误不得变成成功或panic。"""
import copy
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent / 'cli-edges'
ROOT = OUT.parents[4]
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'


def call(args):
    p = subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True, timeout=30)
    assert 'panicked' not in p.stderr, p.stderr
    return dict(command=[str(BIN), *map(str, args), '--config', str(CFG)], exit_code=p.returncode,
                stdout=p.stdout, stderr=p.stderr)


def main():
    OUT.mkdir(exist_ok=True)
    source = ROOT / '数据/样例/生产循环环带.json'
    result = call(['run', source, '--ticks', 2, '--max-sweeps', 1, '--no-output'])
    obj = json.loads(result['stdout'])
    assert result['exit_code'] == 2 and obj['status'] == 'inconclusive'
    assert obj['statistics']['inconclusive'] == 1 and obj['completed_ticks'] == 0
    reports = [result]
    for budget in ['0', '-1', 'not-integer']:
        row = call(['run', source, '--ticks', 2, '--max-sweeps', budget, '--no-output'])
        assert row['exit_code'] == 2 and 'max_sweeps' in row['stderr']
        reports.append(row)
    row = call(['run', source, '--ticks', 2, '--max-sweeps', 100000, '--no-output'])
    assert row['exit_code'] == 0 and json.loads(row['stdout'])['status'] == 'completed'
    reports.append(row)
    source = ROOT / '数据/样例/混做粉碎机两下游.json'
    original = json.loads(source.read_text())
    for ref in [original['catalog'], original['parameters']['axis_registry']]:
        ref['path'] = str((source.parent / ref['path']).resolve())
    # 对每类复合字段只选首个数组元素，避免组合爆炸；本探针检查异常退出，不将未拒收元数据误判为规则错误。
    pointers = []
    def visit(value, pointer):
        if isinstance(value, dict):
            pointers.append(pointer)
            for key, child in value.items():
                visit(child, pointer + [key])
        elif isinstance(value, list):
            pointers.append(pointer)
            if value:
                visit(value[0], pointer + [0])
    for key in ['layout', 'initial_state', 'settings', 'timeline', 'construction']:
        visit(original[key], [key])
    mutations = []
    for i, pointer in enumerate(pointers):
        data = copy.deepcopy(original)
        node = data
        for key in pointer[:-1]:
            node = node[key]
        node[pointer[-1]] = True
        path = OUT / f'structure-{i}.json'
        path.write_text(json.dumps(data, ensure_ascii=False) + '\n')
        row = call(['seed', path])
        obj = json.loads(row['stdout'])
        assert row['exit_code'] in (0, 2)
        mutations.append(dict(pointer=pointer, exit_code=row['exit_code'], status=obj.get('status', obj.get('schema')),
                              input=str(path), result=obj if row['exit_code'] else {'schema': obj.get('schema')}))
    result = dict(status='pass', budgets=reports, structural_mutations=mutations,
                  scope='结构变异只查无panic和可解析响应；接受不参与机制的元数据不据此判错')
    (OUT / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'pass', 'budget_cases': len(reports), 'structural_cases': len(mutations)}))


if __name__ == '__main__':
    main()
