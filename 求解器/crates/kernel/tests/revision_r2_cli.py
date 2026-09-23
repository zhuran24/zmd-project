"""第2轮修订：双样例双编码元数据篡改及真实CLI输入反例，临时文件只在独占测试目录内。"""
import copy
import json
import subprocess
import sys
from evidence_paths import instance_dir
from pathlib import Path
import verify_outputs as verifier

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = None
CONFIG = ROOT / '规格/内核配置-v1.json'
BIN = None


def write(path, data):
    """第四轮§5：可复跑的JSON证据。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def invoke(source, out, ticks=2, format_name='full_state_each_instant', no_output=False):
    """内核输出§3：公开进程退出码与schema均参与验收。"""
    command = [str(BIN), 'run', str(source), '--config', str(CONFIG), '--ticks', str(ticks)]
    if no_output:
        command.append('--no-output')
    else:
        command += ['--format', format_name, '--checkpoint-interval', '5', '--out', str(out)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    record = json.loads(result.stdout) if no_output else verifier.checker.load_json(out)
    if not no_output:
        schema = verifier.checker.load_json(ROOT / '规格/内核输出.schema.json')
        verifier.validate_schema(record, schema, schema)
    return result.returncode, record


def relocated(data, source):
    """内核输入§1：测试复制输入时保留来源身份，未更改正式来源。"""
    data = copy.deepcopy(data)
    for ref in (data['catalog'], data['parameters']['axis_registry']):
        ref['path'] = str((source.parent / ref['path']).resolve())
    return data


def main(out):
    """KR-r2全部发现：有效对照先通过，变异逐项拒收，退出101不能充当成功拒收。"""
    reports, controls = [], []
    for name, ticks in [('混做粉碎机两下游', 4), ('分流器三路轮询', 12)]:
        source = ROOT / f'数据/样例/{name}.json'
        data = verifier.checker.load_json(source)
        expected = verifier.run(data)
        for format_name in ('full_state_each_instant', 'checkpoint_delta'):
            path = out / f'{name}-{format_name}.json'
            code, record = invoke(source, path, ticks, format_name)
            assert code == 0 and record['status'] == 'completed'
            controls.append(verifier.verify(path, data, expected))
            for mutation in ('unknown_axis', 'missing_axis', 'duplicate_axis', 'wrong_disposition', 'wrong_reason',
                             'wrong_other_values', 'missing_evidence', 'fake_evidence', 'exercised_with_existing_event',
                             'wrong_status', 'wrong_profile', 'wrong_producer_path', 'wrong_producer_claim',
                             'wrong_run_id', 'missing_open_items', 'bad_summary_control'):
                bad = copy.deepcopy(record)
                rows = bad['uncovered_axes']
                if mutation == 'unknown_axis': rows[0]['axis'] = 'forged.axis'
                elif mutation == 'missing_axis': rows.pop()
                elif mutation == 'duplicate_axis': rows[-1] = copy.deepcopy(rows[0])
                elif mutation == 'wrong_disposition': rows[0]['disposition'] = '本版选值'
                elif mutation == 'wrong_reason': rows[0]['reason'] = '伪造损失'
                elif mutation == 'wrong_other_values': rows[0]['other_values'] = '伪造覆盖'
                elif mutation == 'missing_evidence': rows[0]['evidence'] = []
                elif mutation == 'fake_evidence': rows[0]['evidence'] = ['missing_event']
                elif mutation == 'exercised_with_existing_event':
                    row = next(r for r in rows if r['axis'] == 'transfer.cooldown_scope')
                    row.update(coverage_status='exercised', evidence=[expected[0]['events'][0]['event']])
                elif mutation == 'wrong_status': rows[0]['coverage_status'] = 'exercised'
                elif mutation == 'wrong_profile': bad['profile_id'] = 'fake'
                elif mutation == 'wrong_producer_path': bad['producer']['path'] = 'fake.rs'
                elif mutation == 'wrong_producer_claim': bad['producer']['claim'] = '伪造生产者'
                elif mutation == 'wrong_run_id': bad['run_id'] = 'fake'
                elif mutation == 'missing_open_items': bad['open_items'] = []
                else: bad['trace']['ticks'][0]['summary']['warehouse_ore'] = '123'
                assert not verifier.same(bad, record)
                bad_path = out / 'mutation.json'
                write(bad_path, bad)
                try:
                    verifier.verify(bad_path, data, expected)
                except (ValueError, AssertionError) as error:
                    reports.append({'sample': name, 'format': format_name, 'mutation': mutation,
                                    'accepted': False, 'reason': str(error)})
                else:
                    raise AssertionError(f'篡改被接受：{name}/{format_name}/{mutation}')

    source = ROOT / '数据/样例/混做粉碎机两下游.json'
    original = relocated(verifier.checker.load_json(source), source)
    code, restart = invoke(source, out / 'restart.json', 2)
    assert code == 0
    cases = []
    for value in (None, 7, {}, 'proof', False, []):
        data = copy.deepcopy(original)
        data['initial_state']['reachability'] = value
        cases.append((f'reachability-{type(value).__name__}', data, 'invalid_input', False))
    for value in ('missing', 'filled'):
        data = copy.deepcopy(original)
        if value == 'missing': del data['initial_state']['warehouse']['unlisted']
        else: data['initial_state']['warehouse']['unlisted'] = value
        cases.append((f'unlisted-{value}', data, 'invalid_input', False))
    for kind in ('runtime', 'connection_close'):
        data = copy.deepcopy(original)
        data['timeline']['events'].append({'id': 'unowned_probe', 'kind': kind, 'time': expected[1]['time']})
        cases.append((f'unowned-{kind}', data, 'invalid_input', False))
    for event in ('build_0', 'J|2|0|0', None, 'valid'):
        data = copy.deepcopy(original)
        data['initial_state']['nonwarehouse']['value'] = copy.deepcopy(restart['trace']['ticks'][-1]['state'])
        if event != 'valid':
            data['initial_state']['nonwarehouse']['value']['semantic_context']['tick_context']['value']['movements'][0]['event'] = event
        cases.append((f'movement-{event}', data, 'completed' if event == 'valid' else 'invalid_input', True))
    fixture_dir = ROOT / 'crates/kernel/tests/fixtures'
    phase = verifier.checker.load_json(fixture_dir / 'revision_r2_phase_control.json')
    cases.append(('phase-control', phase, 'completed', False))
    bad = copy.deepcopy(phase)
    relation = next(r for r in bad['timeline']['relations'] if r['before'] == 'completion_probe')
    relation['before'], relation['after'] = relation['after'], relation['before']
    cases.append(('phase-conflict', bad, 'invalid_input', False))
    branch = verifier.checker.load_json(fixture_dir / 'revision_r2_branch_cut.json')
    cases.append(('branch-cut', branch, 'completed', False))
    good = copy.deepcopy(branch)
    good['settings']['gates'][0]['total_limit'] = None
    cases.append(('branch-retained', good, 'completed', False))
    inputs = []
    for name, data, status, no_output in cases:
        path = out / f'{name}-input.json'
        write(path, data)
        code, record = invoke(path, out / f'{name}-record.json', 2, no_output=no_output)
        assert code == (0 if status == 'completed' else 2), (name, code, record)
        assert record['status'] == status, (name, record)
        if name == 'branch-cut': assert record['trace']['ticks']
        inputs.append({'case': name, 'status': status, 'exit_code': code,
                       'stop': record.get('open_items', [])[-1:] if status != 'completed' else []})
    result = {'status': '通过', 'controls': controls, 'metadata_mutations': reports, 'input_cases': inputs,
              'metadata_rejected': len(reports), 'input_case_count': len(inputs)}
    write(EVIDENCE / 'regression-results.json', result)
    print(json.dumps({'status': '通过', 'controls': len(controls), 'metadata_rejected': len(reports),
                      'input_cases': len(inputs)}, ensure_ascii=False))


if __name__ == '__main__':
    EVIDENCE = instance_dir('revision_r2_cli')
    BIN = Path(sys.argv[1]).resolve()
    directory = EVIDENCE / 'tmp'
    directory.mkdir()
    main(directory)
