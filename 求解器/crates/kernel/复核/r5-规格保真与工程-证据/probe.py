"""第五轮规格与工程复核：只向本证据目录写入，保留每个CLI调用的原始结果。"""
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
    return json.loads(path.read_text())


def save(name, value):
    path = HERE / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def call(name, *args, cwd=ROOT):
    command = [str(BIN), *map(str, args), '--config', str(CFG)]
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    (HERE / (name + '.log')).write_text(
        json.dumps({'command': command, 'cwd': str(cwd), 'exit': result.returncode}, ensure_ascii=False)
        + '\nSTDOUT\n' + result.stdout + '\nSTDERR\n' + result.stderr)
    data = None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        pass
    CASES.append({'name': name, 'exit': result.returncode, 'result': data,
                  'stderr': result.stderr, 'log': name + '.log'})
    return result.returncode, data


def set_axis(raw, name, value):
    for group in ('fixed', 'offline_mutable', 'fixedness_unproven'):
        if name in raw['parameters'][group]:
            raw['parameters'][group][name]['value'] = value
    for row in raw['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
        if row['axis'] == name:
            row['value']['value'] = value


def schema(paths):
    source = '''const fs=require('fs'),Ajv=require(process.argv[1]);
const p=JSON.parse(fs.readFileSync(0,'utf8'));
const v=new Ajv({strict:false,allErrors:true}).compile(JSON.parse(fs.readFileSync(p.schema,'utf8')));
console.log(JSON.stringify(p.paths.map(path=>({path,valid:v(JSON.parse(fs.readFileSync(path,'utf8'))),errors:v.errors}))))'''
    p = subprocess.run(['node', '-e', source, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'],
                       input=json.dumps({'schema': str(ROOT/'规格/内核输出.schema.json'), 'paths': list(map(str, paths))}),
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def main():
    base = ROOT/'数据/样例/生产循环环带.json'
    documents = []
    certificates = []
    for mode, interval in [('none', 1), ('none', 7), ('referenced', 7)]:
        name = f'{mode}-{interval}'
        path = HERE/(name+'.json')
        flags = ['--no-record'] if mode == 'none' else []
        assert call(name, 'cycle', base, '--max-ticks', 50, '--search-checkpoint-interval', interval, '--out', path, *flags)[0] == 0
        assert call(name+'-verify', 'verify-cycle', path, cwd=ROOT.parent)[0] == 0
        documents.append(path)
        certificates.append(read(path))
    assert certificates[0] == certificates[1]
    save('interval-comparison.json', {'intervals':[1,7], 'identical_result': True})
    cp = HERE/'checkpoint.json'
    assert call('checkpoint-valid', 'checkpoint', HERE/'none-7.json', '--out', cp)[0] == 0
    continued = HERE/'continued.json'
    assert call('continued', 'cycle', cp, '--max-ticks', 25, '--no-record', '--out', continued)[0] == 0
    assert call('continued-verify', 'verify-cycle', continued)[0] == 0
    state = certificates[1]['cycle']['end_state']
    assert read(cp)['initial_state']['nonwarehouse']['value'] == state
    assert read(continued)['cycle']['start_state'] == state
    documents.append(continued)

    # 被核诊断没有可恢复输入；checkpoint必须有结构化拒收而非解引用null。
    shell = ROOT/'crates/kernel/evidence/round6/cli/overflow.json'
    assert call('load-shell-verify', 'verify-cycle', shell)[0] == 0
    call('load-shell-checkpoint', 'checkpoint', shell, '--out', HERE/'invalid-checkpoint.json')

    # 同一引用式周期、同一记录，只改变合法相对路径的表示。
    ref = copy.deepcopy(certificates[2])
    record = read(Path(ref['run_record_ref']['path']))
    for row in record['fingerprints']:
        row['path'] = os.path.relpath(row['path'], HERE)
    record['producer']['path'] = os.path.relpath(record['producer']['path'], HERE)
    relative_record = save('relative.record.json', record)
    ref['run_record_ref']['path'] = relative_record.name
    ref['run_record_ref']['sha256'] = hashlib.sha256(relative_record.read_bytes()).hexdigest()
    ref['run_record_ref']['producer'] = record['producer']
    relative_cert = save('relative-cycle.json', ref)
    assert call('relative-cycle-verify', 'verify-cycle', relative_cert)[0] == 0
    call('relative-record-verify-root', 'verify-record', relative_record)
    call('relative-record-verify-local', 'verify-record', relative_record, cwd=HERE)
    call('relative-record-checkpoint', 'checkpoint', relative_record, '--out', HERE/'relative-checkpoint.json')
    documents.extend([relative_record, relative_cert])

    # 矿量只改容量，回矿候选物种和图均不变；观察静态命令进入D.2之前的装载路径。
    raw = read(ROOT/'crates/kernel/tests/fixtures/core_inbound.json')
    set_axis(raw, 'warehouse.external_supply', {'kind':'sufficient'})
    inventory = raw['initial_state']['nonwarehouse']['value']['inventory']
    next(row for row in inventory if row['slot']=='belt:transport:0')['contents'] = [
        {'item':'源矿', 'quantity':{'value':'1','category':'候选'},
         'entered_at':{'kind':'rational','value':{'value':'-1','category':'候选'}}}]
    seeds = []
    for quantity in (79999, 80000):
        current = copy.deepcopy(raw)
        next(row for row in current['initial_state']['nonwarehouse']['value']['warehouse']['slots'] if row['item']=='源矿')['quantity']['value']=str(quantity)
        source = save(f'ore-{quantity}-raw.json', current)
        seeded = HERE/f'ore-{quantity}-seed.json'
        assert call(f'ore-{quantity}-seed', 'seed', source, '--out', seeded)[0] == 0
        assert call(f'ore-{quantity}-finite-check', 'check', seeded)[0] == 0
        call(f'ore-{quantity}-domain', 'check', seeded, '--cycle-domain')
        seeds.append(read(seeded))
    a,b = [x['initial_state']['nonwarehouse']['value']['logistics']['poll_memory']['value'] for x in seeds]
    save('ore-dependent-memory.json', {'memory_equal': a==b, 'at_79999': a, 'at_80000': b})
    crossed=copy.deepcopy(seeds[0])
    next(row for row in crossed['initial_state']['nonwarehouse']['value']['warehouse']['slots'] if row['item']=='源矿')['quantity']['value']='80000'
    source=save('ore-capacity-changed-only.json', crossed)
    call('ore-capacity-changed-domain', 'check', source, '--cycle-domain')

    save('schema-results.json', schema(documents))
    save('results.json', CASES)
    print(json.dumps({'cases': len(CASES), 'schema_documents':len(documents), 'outputs': str(HERE)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
