#!/usr/bin/env python3
"""第1轮修订：公开CLI负例与Python落盘验收变异；所有文件写入本crate证据目录。"""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import verify_outputs as verifier

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'crates/kernel/evidence/revision-r2'
OUT = EVIDENCE / 'tmp'
CONFIG = ROOT / '规格/内核配置-v1.json'
BIN = Path(sys.argv[1]).resolve()


def write(path, value):
    """内核输出§1：稳定、可复查的原始JSON。"""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def invoke(source, name, ticks=4, format_name='full_state_each_instant'):
    """第四轮§4.6：真实CLI返回码与输出记录同时核查。"""
    path = OUT / (name + '-record.json')
    command = [str(BIN), 'run', str(source), '--config', str(CONFIG), '--ticks', str(ticks),
               '--format', format_name, '--checkpoint-interval', '3', '--out', str(path)]
    process = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert path.exists(), (command, process.returncode, process.stderr)
    record = verifier.checker.load_json(path)
    schema = verifier.checker.load_json(ROOT / '规格/内核输出.schema.json')
    verifier.validate_schema(record, schema, schema)
    return path, record, process.returncode


def main():
    """内核输入§2–§6、输出§3：正例先通过，同一记录逐字段变异随后必须拒绝。"""
    OUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for sample, ticks in [('混做粉碎机两下游', 4), ('分流器三路轮询', 12)]:
        source = ROOT / f'数据/样例/{sample}.json'
        data = verifier.checker.load_json(source)
        expected = verifier.run(data)
        for format_name in ['full_state_each_instant', 'checkpoint_delta']:
            name = sample + '-' + format_name
            path, record, code = invoke(source, name, ticks, format_name)
            assert code == 0 and record['status'] == 'completed'
            verifier.verify(path, data, expected)
            reports.append({'case': name, 'kind': '有效对照', 'status': '通过'})
            for mutation in ['remove_all', 'remove_formal', 'remove_checker', 'fake_count', 'fake_from',
                             'fake_through', 'fake_golden', 'fake_initial_history', 'true_certified', 'bad_summary']:
                bad = copy.deepcopy(record)
                scope = bad['validation_scope']
                if mutation == 'remove_all': bad['fingerprints'] = []
                elif mutation.startswith('remove_'):
                    role = 'formal_source' if mutation == 'remove_formal' else 'checker'
                    bad['fingerprints'] = [r for r in bad['fingerprints'] if r['role'] != role]
                elif mutation == 'fake_count': scope['manufacturing_cycles_completed']['value'] = '999'
                elif mutation in ('fake_from', 'fake_through'): scope[mutation[5:]]['value']['value'] = '99'
                elif mutation == 'fake_golden': scope['golden_match'] = not scope['golden_match']
                elif mutation == 'fake_initial_history': scope['initial_history'] = 'unproved'
                elif mutation == 'true_certified': scope['target_certified'] = True
                else: bad['trace']['ticks'][0]['summary']['warehouse_ore'] = '123'
                bad_path = OUT / (name + '-' + mutation + '.json')
                write(bad_path, bad)
                try:
                    verifier.verify(bad_path, data, expected)
                except (AssertionError, ValueError) as error:
                    reports.append({'case': name + '-' + mutation, 'kind': '篡改拒收', 'status': '通过', 'reason': str(error)})
                else:
                    raise AssertionError('篡改仍通过：' + name + '-' + mutation)

    source = ROOT / '数据/样例/混做粉碎机两下游.json'
    for name in ['snapshot_bool', 'initial_duplicate_slot', 'ore_shortage', 'gate_numeric', 'after_closure', 'pending_alias']:
        origin = source if name != 'gate_numeric' else ROOT / '数据/样例/分流器三路轮询.json'
        data = verifier.checker.load_json(origin)
        if name == 'snapshot_bool': data['layout']['snapshots'] = [False]
        elif name == 'initial_duplicate_slot': data['initial_state']['warehouse']['slots'][1]['slot'] = data['initial_state']['warehouse']['slots'][0]['slot']
        elif name == 'ore_shortage': data['initial_state']['nonwarehouse']['value']['warehouse']['slots'][0]['quantity']['value'] = '1'
        elif name == 'gate_numeric': data['settings']['gates'][0]['item'] = 7
        else:
            _, control, code = invoke(source, 'restart-source', 2)
            assert code == 0
            data['initial_state']['nonwarehouse']['value'] = control['trace']['ticks'][-1]['state']
            if name == 'pending_alias': data['initial_state']['nonwarehouse']['value']['semantic_context']['pending_events']['value'][0]['event'] = 'build_0'
        data['catalog']['path'] = str((origin.parent / data['catalog']['path']).resolve())
        data['parameters']['axis_registry']['path'] = str((origin.parent / data['parameters']['axis_registry']['path']).resolve())
        input_path = OUT / (name + '-input.json')
        write(input_path, data)
        _, record, code = invoke(input_path, name, 2)
        assert code == (0 if name=='after_closure' else 2), (name, code)
        assert record['status'] == ('completed' if name == 'after_closure' else 'invalid_input'), (name, record)
        reports.append({'case': name, 'kind': 'CLI拒收', 'status': '通过', 'exit_code': code, 'stop': record['open_items'][-1]})
    result = {'status': '通过', 'controls': 4, 'metadata_negatives': 40, 'cli_negatives': 5, 'checkpoint_resume_controls': 1, 'cases': reports}
    write(EVIDENCE / 'prior-regression-results.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, ensure_ascii=False))


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cli-', dir=OUT) as directory:
        OUT = Path(directory)
        main()
