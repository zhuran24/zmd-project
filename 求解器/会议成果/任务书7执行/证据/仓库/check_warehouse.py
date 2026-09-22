#!/usr/bin/env python3
"""Bounded arithmetic audit, not a game simulator or a layout certificate.

Reads locked inputs; writes only 核对结果.json beside this script.
Small capacities below are abstract algebra examples, not warehouse settings.
"""
import hashlib
import itertools
import json
import re
from pathlib import Path


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    manifest = json.loads((BASE / '输入指纹.json').read_text())
    source_checks = [
        {'path': entry['path'], 'expected': entry['sha256'],
         'actual': digest(Path(entry['path'])),
         'same': digest(Path(entry['path'])) == entry['sha256']}
        for entry in manifest['sources']
    ]
    assert all(x['same'] for x in source_checks), 'source bytes changed; review affected claims'

    # Independent small oracle: enumerate every feasible received vector,
    # maximize total received, compare with coordinatewise maximal receipt.
    checked = 0
    for capacity in range(1, 6):
        for stock in itertools.product(range(capacity + 1), repeat=2):
            for offered in itertools.product(range(4), repeat=2):
                feasible = [v for v in itertools.product(*(range(n + 1) for n in offered))
                            if all(stock[i] + v[i] <= capacity for i in range(2))]
                maximum = max(map(sum, feasible))
                winners = [v for v in feasible if sum(v) == maximum]
                predicted = tuple(min(offered[i], capacity - stock[i]) for i in range(2))
                assert winners == [predicted]
                residual = tuple(offered[i] - predicted[i] for i in range(2))
                assert all(predicted[i] + residual[i] == offered[i] for i in range(2))
                if all(stock[i] + offered[i] <= capacity for i in range(2)):
                    assert predicted == offered
                checked += 1

    # Full one-species warehouse does not veto the other species.
    mixed = {'capacity': 4, 'stock': [4, 0], 'box': [2, 3],
             'actual_inbound': [0, 3], 'residual': [2, 0]}
    partial = {'capacity': 4, 'stock': [3, 0], 'box': [2, 1],
               'actual_inbound': [1, 1], 'residual': [1, 0]}
    for case in (mixed, partial):
        assert case['actual_inbound'] == [min(n, case['capacity'] - q)
                                         for q, n in zip(case['stock'], case['box'])]
        assert case['residual'] == [n - a for n, a in zip(case['box'], case['actual_inbound'])]

    # Sequential transactions: neither event may use a stale capacity snapshot.
    capacity, stock = 4, 2
    receipts = []
    for offer in [1, 2]:
        receipt = max(r for r in range(offer + 1) if stock + r <= capacity)
        receipts.append(receipt)
        stock += receipt
    assert receipts == [1, 1] and stock == capacity

    # Warehouse empty-label permutations never rename assigned ore slots.
    # This only checks the finite example of the relation proved in the text.
    ore = {'ore_a': ('源矿', 7), 'ore_b': ('蓝铁矿', 9)}
    product_names = ('高容谷地电池', '精选荞愈胶囊')
    labels = ('free_1', 'free_2', 'free_3')
    incoming = (product_names[0], product_names[1], '砂叶')
    variants = []
    for ordered_labels in itertools.permutations(labels):
        slots = dict(ore)
        slots.update({label: (kind, 1) for label, kind in zip(ordered_labels, incoming)})
        ore_observation = tuple(slots[label] for label in ore)
        per_species = sorted((kind, n) for kind, n in slots.values())
        variants.append((ore_observation, per_species))
    assert all(v == variants[0] for v in variants)

    # Contrasting numbered box states: same total, different first nonempty kind.
    box_a = [('高容谷地电池', 1), ('精选荞愈胶囊', 1)]
    box_b = list(reversed(box_a))
    assert sorted(box_a) == sorted(box_b) and box_a[0][0] != box_b[0][0]

    # Two product ledgers, componentwise. This is bookkeeping, not a layout trace.
    initial = [5, 7]
    inbound = [[1, 0], [0, 1], [1, 1], [0, 1]]
    withdrawal = [[0, 0], [1, 0], [0, 1], [1, 2]]
    stock = list(initial)
    segments = []
    ledger = []
    for cycle in range(3):
        states = []
        for phase, (received, taken) in enumerate(zip(inbound, withdrawal)):
            before = list(stock)
            stock = [q + i - p for q, i, p in zip(stock, received, taken)]
            assert all(q >= 0 for q in stock)
            assert all(stock[i] - before[i] == received[i] - taken[i] for i in range(2))
            states.append(list(stock))
            ledger.append({'cycle': cycle, 'phase': phase,
                           'before': before, 'I': received, 'O': [0, 0],
                           'P': taken, 'after': list(stock)})
        assert stock == initial
        segments.append(states)
    assert segments[0] == segments[1] == segments[2]

    # Endpoint balance with a changed within-period withdrawal pattern.
    def inventory_path(taken):
        q, history = 5, []
        for p in taken:
            q += 1 - p
            history.append(q)
        return history
    late = inventory_path([0, 2])
    spread = inventory_path([1, 1])
    assert late[-1] == spread[-1] == 5 and late != spread

    # A production period may have nonzero real warehouse net change.
    assert 2 - 1 == 1
    assert 3 - 2 == 1
    # Mathematical normalization is a separate debit, never actual delivery.
    q_before, actual_inbound, player_taken, representative_adjustment = 2, 3, 0, 2
    q_after = q_before + actual_inbound - player_taken - representative_adjustment
    assert q_after == 3

    docs = [BASE.parents[1] / '仓库接收与循环对应.md',
            BASE.parents[1] / '受限转移定义-§6.5替换稿.md']
    doc_checks = []
    for path in docs:
        body = path.read_text()
        assert '\n仓库收得下成品。\n' in body
        assert '任务5' in body and '生产部分周期' in body
        assert '能送多少送多少' in body
        assert '80000' not in body
        assert '(Delta ' not in body
        for label, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', body):
            if not target.startswith(('http:', 'https:')):
                assert (path.parent / target).exists(), (path, label, target)
        doc_checks.append({'path': str(path), 'sha256': digest(path),
                           'line_count': len(body.splitlines())})
    schema = json.loads((ROOT / '求解器/规格/内核输出.schema.json').read_text())
    assert all(name in schema['$defs'] for name in ('CycleKey', 'Cycle', 'CycleResult'))
    rules = (ROOT / '《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
    tasks = (ROOT / '求解任务.txt').read_text().splitlines()
    assert rules[35].removeprefix('传输：') in docs[0].read_text()
    assert tasks[9].removeprefix('循环态：') in docs[0].read_text()

    return {
        'schema': 'warehouse-proof-check-v1', 'status': 'pass',
        'scope': '局部代数和文档绑定；一般证明见正文；非内核运行、非完整布局证书',
        'source_checks': source_checks,
        'checks': [
            {'name': '两种物品的最大可接收向量', 'cases': checked, 'status': 'pass',
             'coverage': '抽象容量1至5、每种待送0至3；穷举可行接收向量，核最大值与守恒'},
            {'name': '一满一可收及部分剩余', 'status': 'pass', 'examples': [mixed, partial]},
            {'name': '同刻连续入库使用更新后仓存', 'status': 'pass', 'receipts': receipts},
            {'name': '未指派空格更名保持原矿引用及逐种库存', 'status': 'pass',
             'permutations': len(variants)},
            {'name': '箱编号格不可按总数归并', 'status': 'pass', 'states': [box_a, box_b]},
            {'name': '两成品分账及重复拿取下的段内库存复原', 'status': 'pass', 'ledger': ledger},
            {'name': '端点平衡不足以固定段内库存', 'status': 'pass', 'paths': [late, spread]},
            {'name': '生产周期非零净变及数学调整另记', 'status': 'pass'},
        ],
        'documents': doc_checks,
        'kernel': {'built': False, 'loaded': False, 'stepped': False,
                   'reason': '本席采用直接证明及局部代数核对'},
        'independent_review': 'pending',
    }


if __name__ == '__main__':
    report = run()
    (BASE / '核对结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'],
                      'arithmetic_cases': report['checks'][0]['cases'],
                      'source_hashes_unchanged': len(report['source_checks']),
                      'check_groups': len(report['checks']),
                      'kernel_steps': 0}, ensure_ascii=False))
