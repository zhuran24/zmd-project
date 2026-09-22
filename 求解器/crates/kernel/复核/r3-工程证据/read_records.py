"""全量读取交付记录，调用纯验收函数；原生成脚本的main不执行。"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = ROOT / 'crates/kernel/复核/r3-工程证据'
sys.path.insert(0, str(ROOT / 'crates/kernel/tests'))
import audit_round5 as audit
import verify_outputs as verify

reports = []
for name in ['混做粉碎机两下游', '分流器三路轮询']:
    data = verify.checker.load_json(ROOT / '数据/样例' / (name + '.json'))
    ticks = verify.run(data)
    for suffix in ['运行记录-v3-kernel', '运行记录-checkpoint_delta-v3-kernel']:
        path = ROOT / '数据/样例' / (name + '-' + suffix + '.json')
        reports.append(verify.verify(path, data, ticks))
(OUT / '双参考完整验收.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')

source = json.loads((ROOT / 'crates/kernel/evidence/round5/audit-results.json').read_text())
checks = []
fingerprints = {}
for entry in source['records']:
    path = Path(entry['path'])
    record = json.loads(path.read_text())
    data_path = next(Path(r['path']) for r in record['fingerprints'] if r['role'] == 'input')
    data = json.loads(data_path.read_text())
    for r in record['fingerprints']:
        p = Path(r['path'])
        if p not in fingerprints:
            fingerprints[p] = hashlib.sha256(p.read_bytes()).hexdigest()
        assert fingerprints[p] == r['sha256'], p
    count = audit.audit_ledger(record, data)
    checks.append({'path': str(path), 'ticks': count, 'status': 'pass',
                   'checks': ['全量JSON读取', '来源指纹', '逐事件箱账和出入库账', '逐物种仓库守恒', '时刻连续']})
    print(path.name, count, flush=True)
(OUT / '全部记录台账重核.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')

# 全部循环结果的键、端点、区间与入量用Python参考和精确整数另算。
cycles = []
for entry in source['cycles']:
    path = Path(entry['path'])
    result = json.loads(path.read_text())
    cycle = result['cycle']
    report = {'path': str(path), 'status': result['status'], 'has_cycle': cycle is not None}
    if cycle:
        assert audit.reference_key(cycle['start_state']) == cycle['start_key']
        assert audit.reference_key(cycle['end_state']) == cycle['end_key']
        assert cycle['start_key'] == cycle['end_key']
        start, end = audit.time(cycle['start_time']), audit.time(cycle['end_time'])
        assert end - start == audit.n(cycle['period']) > 0
        rows = [r for r in result['run_record']['trace']['ticks'] if start < audit.time(r['time']) <= end]
        assert len(rows) == end - start
        assert [{'time':r['time'],'warehouse_ledger':r['warehouse_ledger']} for r in rows] == cycle['ledger']
        for rate in cycle['rates']:
            inbound = sum(audit.n(r['quantity']) for tick in rows for field in ['core_inbound','wireless_inbound'] for r in tick['warehouse_ledger'][field] if r['item'] == rate['item'])
            average = audit.Fraction(inbound, end-start)
            target = audit.Fraction(rate['target']['value'])
            assert audit.n(rate['inbound']) == inbound
            assert audit.Fraction(rate['average']['value']) == average
            assert rate['comparison'] == ('lt' if average < target else 'eq' if average == target else 'gt')
        report['period'] = end-start
        report['endpoint_key_and_ledger_checks'] = 'pass'
    cycles.append(report)
    print(path.name, result['status'], flush=True)
(OUT / '全部周期结果重核.json').write_text(json.dumps(cycles, ensure_ascii=False, indent=2) + '\n')
