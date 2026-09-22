"""密集制造闭环的独立场景前件核验；证书重跑及键/账核验由audit_round5完成。"""
import collections
import copy
import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '数据/样例'
E = ROOT / 'crates/kernel/evidence/round5'


def read(path):
    return json.loads(path.read_text())


def time(value):
    return int(value['value']['value'])


def family_projection(data):
    """只删本次明确变更的全序及其派生上下文，保留其它种子/轴/布局/史。"""
    value = copy.deepcopy(data)
    value['scenario']['name'] = '密集制造闭环局部序族'
    value['parameters']['fixed']['judgment.order']['value']['template_order'] = []
    seed = value['initial_state']['nonwarehouse']['value']
    for row in seed['semantic_context']['parameter_values']:
        if row['axis'] == 'judgment.order':
            row['value']['value']['template_order'] = []
    return value


def main():
    cases = []
    inputs = []
    for index in range(6):
        name = f'密集制造闭环序{index}核验'
        data = read(BASE / (name + '.json'))
        inputs.append(data)
        seed = data['initial_state']['nonwarehouse']['value']
        assert all(not row['contents'] for row in seed['inventory'])
        assert all(row['phase'] == 'idle' for row in seed['progress'])
        channels = {row['id']: row for row in data['layout']['physical_channels']}
        direct = next(c for c in channels if c.startswith('PC|split_d:east:') and '|merge:' in c)
        competing = next(c for c in channels if c.startswith('PC|split_e:') and '|merge:' in c)
        d_out = [c for c in channels if c.startswith('PC|split_d:')]
        assert len(d_out) == 3
        events = {row['id']: row for row in data['timeline']['events']}
        connection_times = {row['channel']: time(events[row['event']]['time']) for row in data['timeline']['connection_events']}
        assert connection_times[direct] == connection_times[competing]
        levels = seed['semantic_context']['arbitration']['level_order']
        assert 'L|merge|input|direct:' + direct in levels
        assert 'L|merge|input|direct:' + competing in levels
        result = read(BASE / (name + '-周期证书-kernel.json'))
        cycle = result['cycle']
        if cycle is None:
            cases.append(dict(input=str(BASE / (name + '.json')), status='inconclusive', reason='预算内未取得完整键重复'))
            continue
        start, end = time(cycle['start_time']), time(cycle['end_time'])
        flux = collections.Counter()
        completed = collections.Counter()
        stock = {row['slot']: copy.deepcopy(row['contents']) for row in cycle['start_state']['inventory']}
        merger_entry = None
        for cell in stock['merge:transport:0']:
            assert cell['entered_at'] is not None
            merger_entry = time(cell['entered_at'])
        merger_releases = []
        branch_entries = {u: None for u in ('t11_6', 't10_5')}
        for u in branch_entries:
            contents = stock[u + ':transport:0']
            if contents:
                assert len(contents) == 1
                branch_entries[u] = time(contents[0]['entered_at'])
        branch_releases = collections.Counter()
        d_services = 0
        supply = collections.Counter()
        for tick in result['run_record']['trace']['ticks']:
            t = time(tick['time'])
            for row in tick['warehouse_ledger']['port_outbound']:
                supply[row['item']] += int(row['quantity']['value'])
            if not start < t <= end:
                continue
            for event in tick['events']:
                if event['operation'] == 'manufacture_complete':
                    completed[event['target']] += 1
                if event['operation'] != 'move' or event['outcome'] != 'success':
                    continue
                channel = event['target']
                flux[channel] += 1
                src = channels[channel]['source_port'].split(':')[0]
                dst = channels[channel]['target_port'].split(':')[0]
                if src == 'split_d':
                    assert all(entry is None for entry in branch_entries.values()), ('D服务前旁路首格未释放', index, t, branch_entries)
                    d_services += 1
                if src in branch_entries:
                    assert branch_entries[src] is not None and t - branch_entries[src] == 1
                    branch_entries[src] = None
                    branch_releases[src] += 1
                if dst in branch_entries:
                    assert branch_entries[dst] is None
                    branch_entries[dst] = t
                if channel.startswith('PC|merge:'):
                    assert merger_entry is not None and t - merger_entry == 1
                    merger_releases.append(t - merger_entry)
                    merger_entry = None
                if channels[channel]['target_port'].split(':')[0] == 'merge':
                    assert merger_entry is None
                    merger_entry = t
        assert supply == {'蓝铁矿': 4}, supply
        # 规格S4只要求其它竞争边正量和D总量正；a=0是合法待比较的分流比。
        assert flux[competing] > 0
        assert completed['refine_d'] > 0 and completed['refine_e'] > 0 and completed['crusher_loop'] > 0
        total = sum(flux[c] for c in d_out)
        assert total > 0 and merger_releases
        assert all(row['blocked_reasons'] == ['total_exhausted'] for row in cycle['start_state']['logistics']['gate_counters'])
        ratio = Fraction(flux[direct], total)
        cases.append(dict(input=str(BASE / (name + '.json')), status='period_preconditions_pass', interval=[start, end], period=end-start,
                          direct_count=flux[direct], competing_count=flux[competing], d_total=total, ratio=str(ratio),
                          manufacturing_completions=dict(completed), startup_outbound=dict(supply),
                          merger_one_tick_releases=len(merger_releases), branch_one_tick_releases=dict(branch_releases), d_services_with_empty_bypasses=d_services, connection_time=connection_times[direct],
                          reachability='空库存条件种子；全部循环物料来自真实仓库4件矿，未证明任意建造/调试史可达'))
    reference = family_projection(inputs[0])
    assert all(family_projection(data) == reference for data in inputs[1:]), '非全序字段存在变化'
    template_orders = [data['parameters']['fixed']['judgment.order']['value']['template_order'] for data in inputs]
    d_positions = [i for i, row in enumerate(template_orders[0]) if row['operation'] == 'move' and row['target'].startswith('PC|split_d:')]
    assert len({tuple(order[i]['target'] for i in d_positions) for order in template_orders}) == 6
    assert all([row for i, row in enumerate(order) if i not in d_positions] == [row for i, row in enumerate(template_orders[0]) if i not in d_positions] for order in template_orders)
    ratios = sorted({case['ratio'] for case in cases if 'ratio' in case})
    report = dict(status='pass', cases=cases, varied_positions=d_positions, distinct_ratios=ratios,
                  sensitivity='observed' if len(ratios) > 1 else 'inconclusive',
                  scope='只枚举D三条模板在固定三个位置的6种序；非全部事件全序，不作普遍约束证明。相同比例不构成正式约束反例。')
    (E / 'dense-manufacturing-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status='pass', periods=sum('ratio' in case for case in cases), ratios=ratios, sensitivity=report['sensitivity']), ensure_ascii=False))
    return report


if __name__ == '__main__':
    main()
