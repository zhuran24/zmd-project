"""关键已修行为的正负对照，全部结果写入本次复核目录。"""
from copy import deepcopy
from pathlib import Path
import json
from probe import ROOT, OUT, RESULTS, call, source, save, load

def set_axis(data, name, value):
    for group in ('fixed', 'offline_mutable', 'fixedness_unproven'):
        if name in data['parameters'][group]:
            data['parameters'][group][name]['value'] = deepcopy(value)
    for row in data['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
        if row['axis'] == name:
            row['value']['value'] = deepcopy(value)

def main():
    for name, ticks in [('阻尼切支恢复核验', 16), ('桥接器双通路', 12), ('研磨混做核验', 12)]:
        record = call('positive-'+name, 'run', ROOT/'数据/样例'/(name+'.json'), '--ticks', ticks)
        assert record['status'] == 'completed'
        checked = call('positive-verify-'+name, 'verify-record', OUT/('positive-'+name+'.json'))
        assert checked['status'] == 'input_checked'
    cycle = call('positive-ring-cycle', 'cycle', ROOT/'数据/样例/生产循环环带.json', '--max-ticks', 50)
    assert cycle['cycle'] is not None
    check = call('positive-ring-verification', 'verify-cycle', OUT/'positive-ring-cycle.json')
    assert check['cycle_replayed'] is True
    for quantity in (79999, 80000):
        path = ROOT/'crates/kernel/tests/fixtures/core_inbound.json'
        data = load(path)
        for obj in (data['catalog'], data['parameters']['axis_registry']):
            obj['path'] = str((path.parent/obj['path']).resolve())
        set_axis(data, 'warehouse.external_supply', {'kind': 'sufficient'})
        state = data['initial_state']['nonwarehouse']['value']
        next(r for r in state['warehouse']['slots'] if r['item'] == '源矿')['quantity']['value'] = str(quantity)
        next(r for r in state['inventory'] if r['slot'] == 'belt:transport:0')['contents'] = [dict(item='源矿', quantity={'value':'1','category':'候选'}, entered_at={'kind':'rational','value':{'value':'0','category':'候选'}})]
        initial = save(f'ore-return-{quantity}-input', data)
        seed = call(f'ore-return-{quantity}-seed', 'seed', initial)
        assert seed['schema'] == 'kernel-input-v3'
        canonical = OUT/f'ore-return-{quantity}-seed.json'
        result = call(f'ore-return-{quantity}-cycle', 'cycle', canonical, '--max-ticks', 2)
        assert result['status'] == 'stopped' and result['stop']['axis'] == 'cycle.domain.D2'
        concrete = call(f'ore-return-{quantity}-concrete', 'run', canonical, '--ticks', 2)
        assert concrete['status'] == 'completed'
        inbound = sum(int(r['quantity']['value']) for t in concrete['trace']['ticks'] for r in t['warehouse_ledger']['core_inbound'])
        assert inbound == (1 if quantity == 79999 else 0)
    result = call('zero-ore-runtime-rejection', 'run', OUT/'zero-ore-sufficient-seed.json', '--ticks', 1)
    assert result['status'] == 'invalid_input'
    save('positive-check-results', {'status':'通过', 'cases':RESULTS})
    print(json.dumps({'status':'通过', 'cases':len(RESULTS)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
