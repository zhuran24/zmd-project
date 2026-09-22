#!/usr/bin/env python3
"""第4轮独立执行入口：只在本复核目录保存产物，不改被审来源。"""
import copy
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = ROOT / '数据/样例'
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
sys.path.insert(0, str(ROOT / 'crates/kernel/tests'))
sys.path.insert(0, str(BASE))
COMMANDS = json.loads((OUT/'commands.json').read_text()) if (OUT/'commands.json').exists() else []

def read(path):
    return json.loads(Path(path).read_text())

def save(path, value):
    path = Path(path)
    assert path.is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path

def invoke(args, expected=0):
    command = [str(BIN), *map(str, args), '--config', str(CFG)]
    start = time.perf_counter_ns()
    p = subprocess.run(command, capture_output=True, text=True, timeout=240)
    COMMANDS.append(dict(command=command, exit_code=p.returncode, elapsed_ns=time.perf_counter_ns()-start,
                         stdout=p.stdout, stderr=p.stderr))
    save(OUT/'commands.json', COMMANDS)
    assert p.returncode == expected, COMMANDS[-1]
    return json.loads(p.stdout) if p.stdout.strip() else None

def redirected_rust_cli_test():
    # 原Rust集成测试写死旧证据目录；用相同公开调用与断言在授权目录重做。
    seed = OUT/'relocated-seed.json'
    invoke(['seed', BASE/'混做粉碎机两下游.json', '--out', seed])
    r = invoke(['run', seed, '--ticks', '4', '--no-output'])
    assert r['status'] == 'completed'
    r = invoke(['run', BASE/'生产循环环带.json', '--ticks', '2', '--max-sweeps', '1', '--no-output'], 2)
    assert r['status'] == 'inconclusive' and r['statistics']['inconclusive'] == 1 and r['completed_ticks'] == 0
    save(OUT/'resource-statistics.json', r)
    path = save(OUT/'invalid-cycle-input.json', {'schema':'kernel-input-v3'})
    result = OUT/'invalid-cycle-result.json'
    invoke(['cycle', path, '--max-ticks', '2', '--out', result], 2)
    r = read(result)
    assert r['schema'] == 'kernel-cycle-v1' and r['status'] == 'invalid_input' and r['cycle'] is None
    save(OUT/'redirected-rust-cli.json', dict(status='pass', original='crates/kernel/tests/round5_cli.rs',
          note='原测试全部4次CLI调用和全部断言；仅输出位置改为本目录。'))

def benchmarks():
    cases=[]
    for name, limit in [('benchmark_brick_60',1), ('benchmark_candidate_b',20), ('benchmark_brick',None)]:
        path = ROOT/'crates/kernel/tests/fixtures'/(name+'.json')
        data = read(path)
        runs=[]
        for _ in range(3):
            r = invoke(['run', path, '--ticks', '12', '--no-output'])
            assert r['status']=='completed' and r['ticks']==12
            runs.append(dict(ms_per_tick=int(r['elapsed_ns'])/1e6/12, engine=r))
        values=[r['ms_per_tick'] for r in runs]
        cases.append(dict(name=name, units=len(data['layout']['units']), pc=len(data['layout']['physical_channels']),
            input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), runs=runs, median_ms=statistics.median(values),
            threshold_ms=limit, all_within_target=all(v<=limit for v in values) if limit else None))
    save(OUT/'benchmark.json',dict(binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), cases=cases,
         scope='相同已锁定合成输入，release，3次各12 tick；引擎推进时间，不含装载和序列化。'))
    print('benchmark',[(r['name'],r['median_ms']) for r in cases],flush=True)

def references():
    # 原main仅最后一个输出目的地重定向；基线与全部验收逻辑不变。
    path=ROOT/'crates/kernel/tests/verify_outputs.py'
    source=path.read_text()
    old="(ROOT / 'crates/kernel/evidence/round5/record-validation.json').write_text"
    assert source.count(old)==1
    source=source.replace(old,"(Path("+repr(str(OUT/'record-validation.json'))+")).write_text")
    exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})

def audits():
    import audit_round5 as audit
    import audit_dense_round5 as dense
    audit.E=OUT
    dense.E=OUT
    audit.main()

def cycles():
    results=[]
    for name, budget in [('生产循环环带',50),('密集制造闭环序0核验',1000)]:
        path=OUT/(name+'-fresh-cycle.json')
        invoke(['cycle', BASE/(name+'.json'), '--max-ticks', budget, '--out', path])
        verified=invoke(['verify-cycle',path])
        r=read(path)
        assert verified['cycle_replayed']
        results.append(dict(name=name, output=str(path), status=r['status'], period=r['cycle']['period'], verification=verified))
    save(OUT/'fresh-cycles.json',results)

def main():
    action=sys.argv[1]
    {'cli':redirected_rust_cli_test,'benchmark':benchmarks,'reference':references,'audit':audits,'cycle':cycles}[action]()

if __name__=='__main__':
    main()
