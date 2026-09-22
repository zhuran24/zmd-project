"""分16段复算K6的512刻有限账；保留逐笔账与续跑输入，删除大体量临时记录。"""
import copy
import hashlib
from collections import Counter
from review_probe import OUT, BASE, read, save, call, number, PRODUCTS

source = BASE / '双成品满仓起动试作.json'
all_rows = []
segments = []
totals = Counter()
completion_count = 0
last_state = None


def warehouse(state):
    counts = Counter()
    for row in state['warehouse']['slots']:
        if row['item'] is not None:
            counts[row['item']] += number(row['quantity'])
    return counts


for segment in range(16):
    path = OUT / 'K6-temporary-record.json'
    call(f'K6-segment-{segment:02d}-run', ['run', source, '--ticks', 32, '--format', 'checkpoint_delta', '--checkpoint-interval', 16, '--out', path])
    data = read(path)
    previous = data['trace']['start_state']
    assert last_state is None or previous == last_state
    for row in data['trace']['ticks']:
        if 'state' in row:
            current = row['state']
        else:
            current = copy.deepcopy(previous)
            for change in row['delta']:
                assert change['op'] == 'replace'
                obj = current
                for key in change['path'][:-1]:
                    obj = obj[key]
                obj[change['path'][-1]] = change['value']
        time = number(row['time'])
        assert time == segment * 32 + len(all_rows) % 32
        ledger = row['warehouse_ledger']
        by_item = {}
        events = {e['event']: e for e in row['events']}
        for route in ('core_inbound', 'wireless_inbound', 'port_outbound', 'external_supply', 'player_withdrawal', 'representative_adjustment'):
            for entry in ledger[route]:
                amount = number(entry['quantity'])
                assert amount > 0
                by_item.setdefault(entry['item'], Counter())[route] += amount
                if route in ('core_inbound', 'wireless_inbound'):
                    event = events[entry['event']]
                    assert event['outcome'] == 'success'
                    assert event['operation'] == ('move' if route == 'core_inbound' else 'transfer')
        old_w, new_w = warehouse(previous), warehouse(current)
        for entry in ledger['totals']:
            item = entry['item']
            counts = by_item.get(item, Counter())
            for key in ('core_inbound', 'wireless_inbound', 'port_outbound', 'external_supply', 'player_withdrawal', 'representative_adjustment'):
                assert counts[key] == number(entry[key])
            actual = counts['core_inbound'] + counts['wireless_inbound']
            assert actual == number(entry['actual_inbound'])
            totals[item] += actual
        for item in set(old_w) | set(new_w) | set(by_item):
            counts = by_item.get(item, Counter())
            expected = counts['core_inbound'] + counts['wireless_inbound'] + counts['external_supply'] - counts['port_outbound'] - counts['player_withdrawal'] - counts['representative_adjustment']
            assert new_w[item] - old_w[item] == expected, (time, item)
        completion_count += sum(e['operation'] == 'manufacture_complete' and e['outcome'] == 'success' for e in row['events'])
        all_rows.append(dict(time=str(time), warehouse_ledger=ledger))
        previous = current
    last_state = previous
    next_source = OUT / f'K6-checkpoint-{segment + 1:02d}.json'
    call(f'K6-segment-{segment:02d}-checkpoint', ['checkpoint', path, '--out', next_source])
    segments.append(dict(segment=segment, input=str(source), from_time=str(number(data['trace']['ticks'][0]['time'])), through_time=str(number(data['trace']['ticks'][-1]['time'])), transient_record_bytes=path.stat().st_size, transient_record_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), checkpoint=str(next_source)))
    path.unlink()
    source = next_source
    print('完成段', segment, flush=True)

compact = read(OUT / 'K6-finite-run.json')
import json
baseline = json.loads(compact['stdout'])
assert {k: int(v) for k, v in totals.items() if v} == baseline['actual_inbound']
assert completion_count == baseline['completed_batches']
save('K6-finite-ledger.json', dict(scope='finite_concrete有限前缀，非周期账', rows=all_rows))
save('K6-ledger-audit.json', dict(status='pass', segments=segments, completed_ticks=len(all_rows), completed_batches=completion_count,
    totals={k: str(v) for k, v in sorted(totals.items())},
    product_transactions={item:[dict(time=r['time'], route=route, entry=e) for r in all_rows for route in ('core_inbound','wireless_inbound') for e in r['warehouse_ledger'][route] if e['item']==item] for item in PRODUCTS},
    final_state=last_state, scope='每笔入库对应成功事件；独立求和并核512刻全物种仓库守恒，续跑首刻无重复；没有周期，不能据此计算周期率。'))
