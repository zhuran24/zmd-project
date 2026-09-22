"""内核否证第5轮第2席：独立构造对照材料，只写本目录和共享target。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
CASES = []


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    path = HERE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def execute(name, args, cwd=ROOT):
    command = list(map(str, args))
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    metadata = {'name': name, 'command': command, 'cwd': str(cwd), 'exit': result.returncode}
    (HERE / (name + '.log')).write_text(
        json.dumps(metadata, ensure_ascii=False) + '\nSTDOUT\n' + result.stdout
        + '\nSTDERR\n' + result.stderr)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None
    CASES.append(dict(metadata, result=payload, stderr=result.stderr, log=name + '.log'))
    save('commands.json', CASES)
    return result.returncode, payload


def kernel(name, *args, cwd=ROOT):
    return execute(name, [BIN, *args, '--config', CFG], cwd)


def schema_check(paths):
    source = """const fs=require('fs'),Ajv=require(process.argv[1]);
const request=JSON.parse(fs.readFileSync(0,'utf8'));
const check=new Ajv({strict:false,allErrors:true}).compile(JSON.parse(fs.readFileSync(request.schema,'utf8')));
console.log(JSON.stringify(request.paths.map(path=>{const valid=check(JSON.parse(fs.readFileSync(path,'utf8')));return {path,valid,errors:check.errors};})));"""
    result = subprocess.run(
        ['node', '-e', source, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'],
        input=json.dumps({'schema': str(ROOT/'规格/内核输出.schema.json'), 'paths': list(map(str, paths))}),
        capture_output=True, text=True, check=True)
    rows = json.loads(result.stdout)
    save('schema-results.json', rows)
    assert all(row['valid'] for row in rows)


def path_differences(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        return sum((path_differences(left[key], right[key], prefix+'/'+key) for key in left), [])
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return sum((path_differences(a, b, prefix+'/'+str(i)) for i, (a, b) in enumerate(zip(left, right))), [])
    return [] if left == right and type(left) is type(right) else [prefix]


def test_domain():
    # 直接链接当前库，探针程序仅输出观察值，不改被审实现。
    dependency = ROOT/'target/release/deps'
    serde = sorted(dependency.glob('libserde_json-*.rlib'), key=lambda p: p.stat().st_mtime_ns)[-1]
    probe = ROOT/'target/kr_r5_2_inspect_engine'
    assert execute('compile-api-probe', [
        'rustc', '--edition=2021', HERE/'inspect_engine.rs',
        '--extern', 'kernel='+str(ROOT/'target/release/libkernel.rlib'),
        '--extern', 'serde_json='+str(serde), '-L', 'dependency='+str(dependency), '-o', probe])[0] == 0
    raw = read(ROOT/'crates/kernel/tests/fixtures/core_inbound.json')
    for group in ('fixed', 'offline_mutable', 'fixedness_unproven'):
        if 'warehouse.external_supply' in raw['parameters'][group]:
            raw['parameters'][group]['warehouse.external_supply']['value'] = {'kind': 'sufficient'}
    state = raw['initial_state']['nonwarehouse']['value']
    next(row for row in state['inventory'] if row['slot'] == 'belt:transport:0')['contents'] = [{
        'item': '源矿', 'quantity': {'value': '1', 'category': '候选'},
        'entered_at': {'kind': 'rational', 'value': {'value': '-1', 'category': '候选'}}}]
    observations = []
    seeds = []
    for quantity in (79999, 80000):
        case = copy.deepcopy(raw)
        ore = next(row for row in case['initial_state']['nonwarehouse']['value']['warehouse']['slots'] if row['item'] == '源矿')
        ore['quantity']['value'] = str(quantity)
        source = save(f'ore-{quantity}-raw.json', case)
        seed = HERE/f'ore-{quantity}-seed.json'
        assert kernel(f'ore-{quantity}-seed', 'seed', source, '--out', seed)[0] == 0
        assert kernel(f'ore-{quantity}-finite-check', 'check', seed)[0] == 0
        code, observed = execute(f'ore-{quantity}-api', [probe, CFG, seed])
        assert code == 0
        observations.append(dict(quantity=quantity, **observed))
        assert kernel(f'ore-{quantity}-finite-run', 'run', seed, '--ticks', 1, '--no-output')[0] == 0
        code, report = kernel(f'ore-{quantity}-domain', 'check', seed, '--cycle-domain')
        assert code == 2 and report['domain_report'][1]['status'] == 'fail'
        certificate = HERE/f'ore-{quantity}-cycle.json'
        assert kernel(f'ore-{quantity}-cycle', 'cycle', seed, '--max-ticks', 2, '--no-record', '--out', certificate)[0] == 2
        stopped = read(certificate)
        assert stopped['stop']['axis'] == 'cycle.domain.D2' and stopped['cycle'] is None
        seeds.append(read(seed))
    # 合法的两份种子作为主证据；不同步记忆的交叉材料只用于辨别校验先后。
    crossed = copy.deepcopy(seeds[0])
    next(row for row in crossed['initial_state']['nonwarehouse']['value']['warehouse']['slots'] if row['item'] == '源矿')['quantity']['value'] = '80000'
    crossed_path = save('ore-crossed-invalid-memory.json', crossed)
    code, crossed_report = kernel('ore-crossed-domain', 'check', crossed_path, '--cycle-domain')
    assert code == 2
    save('domain-observations.json', {'legal_seed_observations': observations,
        'legal_seed_differences': path_differences(*seeds),
        'crossed_is_not_a_legal_seed': True, 'crossed_result': crossed_report})


def test_paths():
    # 新跑一份引用式周期证书，不复用复核席已经生成的记录。
    certificate = HERE/'fresh-cycle.json'
    assert kernel('fresh-cycle', 'cycle', ROOT/'数据/样例/生产循环环带.json',
                  '--max-ticks', 50, '--search-checkpoint-interval', 7, '--out', certificate)[0] == 0
    assert kernel('fresh-cycle-verify', 'verify-cycle', certificate)[0] == 0
    assert kernel('fresh-cycle-checkpoint', 'checkpoint', certificate,
                  '--out', HERE/'fresh-cycle-checkpoint.json')[0] == 0
    original = read(certificate)
    record = read(original['run_record_ref']['path'])
    documents = [certificate, Path(original['run_record_ref']['path'])]
    summary = {}
    for mode in ('absolute', 'relative'):
        folder = HERE/(mode+'-package')
        folder.mkdir(exist_ok=True)
        delivered = copy.deepcopy(record)
        if mode == 'relative':
            for row in delivered['fingerprints']:
                row['path'] = os.path.relpath(row['path'], folder)
            delivered['producer']['path'] = os.path.relpath(delivered['producer']['path'], folder)
        record_path = save(f'{mode}-package/record.json', delivered)
        cert = copy.deepcopy(original)
        cert['run_record_ref'].update(path=record_path.name, sha256=digest(record_path), producer=copy.deepcopy(delivered['producer']))
        cert_path = save(f'{mode}-package/certificate.json', cert)
        assert kernel(mode+'-cycle-verify', 'verify-cycle', cert_path)[0] == 0
        expected = 0 if mode == 'absolute' else 2
        root_code, _ = kernel(mode+'-record-root', 'verify-record', record_path)
        local_code, _ = kernel(mode+'-record-local', 'verify-record', record_path, cwd=folder)
        checkpoint_code, _ = kernel(mode+'-record-checkpoint', 'checkpoint', record_path,
                                   '--out', HERE/(mode+'-record-checkpoint.json'))
        batch_code, _ = kernel(mode+'-batch', 'verify-batch', folder)
        assert [root_code, local_code, checkpoint_code, batch_code] == [expected]*4
        normalized = copy.deepcopy(delivered)
        for row in normalized['fingerprints']:
            path = (folder/row['path']).resolve()
            assert digest(path) == row['sha256']
            row['path'] = str(path)
        normalized['producer']['path'] = str((folder/normalized['producer']['path']).resolve())
        assert normalized == record
        summary[mode] = {'normalized_equals_original': True, 'all_dependency_hashes_match': True,
                         'changed_fields': path_differences(record, delivered),
                         'record_root_exit': root_code, 'record_local_exit': local_code,
                         'record_checkpoint_exit': checkpoint_code, 'batch_exit': batch_code}
        documents.extend([record_path, cert_path])
    save('path-observations.json', summary)
    return documents


def test_load_shell():
    shell = ROOT/'crates/kernel/evidence/round6/cli/overflow.json'
    data = read(shell)
    assert data['replay_input_ref'] is None and data['last_state'] is None and data['cycle'] is None
    code, verified = kernel('load-shell-verify', 'verify-cycle', shell)
    assert code == 0 and verified['diagnostic_replayed'] and not verified['cycle_replayed']
    output = HERE/'load-shell-checkpoint-output.json'
    code, result = kernel('load-shell-checkpoint', 'checkpoint', shell, '--out', output)
    save('load-shell-observations.json', {'source': str(shell), 'source_sha256': digest(shell),
        'schema': data['schema'], 'replay_input_ref': data['replay_input_ref'], 'last_state': data['last_state'],
        'verification': verified, 'checkpoint_exit': code, 'checkpoint_stdout_json': result,
        'checkpoint_file_exists': output.exists()})
    assert code == 101 and result is None and not output.exists()
    return shell


def main():
    test_domain()
    documents = test_paths()
    documents.append(test_load_shell())
    schema_check(documents)
    save('run-summary.json', {'status': 'reproduced', 'commands': len(CASES),
        'schema_documents': len(documents), 'finding_ids': ['KR-r5-L2-01', 'KR-r5-L2-02', 'KR-r5-L2-03'],
        'build_output': str(ROOT/'target'), 'binary_sha256': digest(BIN)})
    print(json.dumps(read(HERE/'run-summary.json'), ensure_ascii=False))


if __name__ == '__main__':
    main()
