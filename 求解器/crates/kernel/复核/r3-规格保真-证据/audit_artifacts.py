"""第3轮逐字段证据检查：只读既有产物，证据只写本目录。"""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import gc
import hashlib
import json
import sys

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'规格/第五轮规格修订'))
from cycle_key_reference import cycle_key
sys.path.insert(0, str(ROOT/'数据/样例'))
from checkpoint_delta import decode_trace
from test_runtime_input import validate_schema

PRODUCTS = ('高容谷地电池', '精选荞愈胶囊')
FLOWS = ('core_inbound', 'wireless_inbound', 'port_outbound', 'external_supply', 'player_withdrawal', 'representative_adjustment')
SCHEMA = json.loads((ROOT/'规格/内核输出.schema.json').read_text())
HASHES = {}

def number(value):
    if value.get('kind') == 'rational':
        value = value['value']
    return Fraction(value['value'])

def counts(state):
    return Counter({r['item']: number(r['quantity']) for r in state['warehouse']['slots'] if r['item']})

def fingerprint(row):
    path = Path(row['path'])
    if path not in HASHES:
        HASHES[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert HASHES[path] == row['sha256'], str(path)

def ledger_check(record):
    trace = decode_trace(record['trace'])
    previous = trace['start_state']
    checked = 0
    for tick in trace['ticks']:
        moment = number(tick['time'])
        assert moment == number(previous['environment']['time']) + (0 if previous['semantic_context']['judgment_context']['value']['phase'] == 'before_boundary' else 1)
        actual = {p: dict.fromkeys(FLOWS, Fraction(0)) for p in PRODUCTS}
        ledger = tick['warehouse_ledger']
        for flow in FLOWS:
            for row in ledger[flow]:
                quantity = number(row['quantity'])
                assert quantity > 0 and quantity.denominator == 1
                actual.setdefault(row['item'], dict.fromkeys(FLOWS, Fraction(0)))[flow] += quantity
        assert [r['item'] for r in ledger['totals']] == sorted(actual)
        after = counts(previous)
        for row in ledger['totals']:
            item = row['item']
            for flow in FLOWS:
                assert number(row[flow]) == actual[item][flow]
            inbound = actual[item]['core_inbound'] + actual[item]['wireless_inbound']
            assert number(row['actual_inbound']) == inbound
            after[item] += inbound + actual[item]['external_supply'] - actual[item]['port_outbound'] - actual[item]['player_withdrawal'] - actual[item]['representative_adjustment']
        assert +after == +counts(tick['state'])
        assert ledger['player_withdrawal'] == []
        if record['execution_mode'] == 'finite_concrete':
            assert ledger['representative_adjustment'] == []
        else:
            assert {r['item']: number(r['quantity']) for r in ledger['representative_adjustment']} == {p: counts(previous)[p] for p in PRODUCTS if counts(previous)[p]}
        previous = tick['state']
        checked += 1
    return checked

def main():
    reports = []
    samples = ROOT/'数据/样例'
    for path in sorted(samples.glob('*周期证书-kernel.json')):
        result = json.loads(path.read_text())
        validate_schema(result, SCHEMA, SCHEMA)
        record = result['run_record']
        for row in record['fingerprints']:
            fingerprint(row)
        ticks = ledger_check(record)
        cycle = result['cycle']
        period = None
        if cycle:
            a, b = number(cycle['start_time']), number(cycle['end_time'])
            period = number(cycle['period'])
            assert b-a == period and period > 0
            assert cycle_key(cycle['start_state']) == cycle['start_key']
            assert cycle_key(cycle['end_state']) == cycle['end_key']
            assert cycle['start_key'] == cycle['end_key']
            segment = [r for r in record['trace']['ticks'] if a < number(r['time']) <= b]
            assert len(segment) == period
            assert cycle['ledger'] == [dict(time=r['time'], warehouse_ledger=r['warehouse_ledger']) for r in segment]
            inbound = Counter()
            for tick in segment:
                for row in tick['warehouse_ledger']['totals']:
                    inbound[row['item']] += number(row['actual_inbound'])
            assert [r['item'] for r in cycle['rates']] == list(PRODUCTS)
            for row, target in zip(cycle['rates'], (Fraction(3,5), Fraction(11,20))):
                average = inbound[row['item']] / period
                assert number(row['average']) == average and number(row['target']) == target
                assert row['comparison'] == ('lt' if average < target else 'eq' if average == target else 'gt')
            assert all(r['status'] == 'pass' for r in result['support_domain']['checks'])
        reports.append(dict(path=str(path), status=result['status'], ticks=ticks, period=str(period) if period else None, key_fields_match=bool(cycle)))
        print(json.dumps(reports[-1], ensure_ascii=False), flush=True)
        del result, record, cycle
        gc.collect()
    # 有限记录按仓库收支、代表量和格式核对；逐事件重跑另用明确选择的CLI正例。
    records = []
    for path in sorted(samples.glob('*运行记录*v3-kernel.json')):
        record = json.loads(path.read_text())
        validate_schema(record, SCHEMA, SCHEMA)
        for row in record['fingerprints']:
            fingerprint(row)
        records.append(dict(path=str(path), ticks=ledger_check(record)))
        del record
        gc.collect()
    output = dict(status='通过', cycle_results=reports, finite_records=records, fingerprint_paths=len(HASHES),
                  scope='规范字段键、schema、来源原始字节、首刻规则、逐物种仓库守恒、逐笔周期账及有理率；不代替D动态准入和任意种子合法性')
    (OUT/'既有产物字段与台账复核.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status='通过', cycles=len(reports), records=len(records)), ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
