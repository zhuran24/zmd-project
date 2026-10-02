#!/usr/bin/env python3
"""Independent checks for a capacity-one cell and full-rate outlet phases.

Only a relaxation of one transport cell is enumerated, not a base layout.
All files are written next to this script. Standard library, one CPU.
"""
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE.parent / '前提快照'


def state_graph():
    # State at the END of a step: -1 empty; 0..8 age, capped at 8.
    graph = {}
    for state in range(-1, 9):
        edges = set()
        if state == -1:
            edges.update([(-1, 0), (0, 1)])
        else:
            age = min(8, state + 1)
            edges.add((age, 0))
            if age == 8:
                edges.update([(-1, 0), (0, 1)])
        graph[state] = sorted(edges)
    return graph


def elementary_cycles(graph):
    cycles = []
    for start in graph:
        def visit(node, path, rewards):
            for nxt, reward in graph[node]:
                if nxt == start:
                    cycles.append((path, rewards + [reward]))
                elif nxt > start and nxt not in path:
                    visit(nxt, path + [nxt], rewards + [reward])
        visit(start, [start], [])
    return cycles


def timestamp_schedules(period, count):
    # A second encoding: occupied cyclic intervals start at reception times.
    # An exact full-rate count can only fit if every cyclic gap is >= 8.
    found = []
    for times in itertools.combinations(range(period), count):
        gaps = [times[i + 1] - times[i] for i in range(count - 1)]
        gaps.append(period + times[0] - times[-1])
        if min(gaps) >= 8:
            found.append({'times': times, 'gaps': gaps})
    return found


def distinct_phase_counts():
    result = []
    for count in range(1, 7):
        # Encoding A: count all injective assignments directly.
        count_a = sum(1 for phases in itertools.product(range(8), repeat=count)
                      if len(set(phases)) == count)
        # Encoding B: choose occupied slots, then label them.
        count_b = sum(1 for chosen in itertools.combinations(range(8), count)
                      for _ in itertools.permutations(chosen))
        assert count_a == count_b
        result.append({'outlets': count, 'encoding_a': count_a,
                       'encoding_b': count_b})
    return result


def main():
    graph = state_graph()
    cycles = elementary_cycles(graph)
    maximum = max(Fraction(sum(rewards), len(path)) for path, rewards in cycles)
    best = [(path, rewards) for path, rewards in cycles
            if Fraction(sum(rewards), len(path)) == maximum]
    assert maximum == Fraction(1, 8)
    assert len(best) == 1 and best[0][0] == list(range(8))
    timestamp_checks = []
    for count in range(1, 5):
        period = 8 * count
        schedules = timestamp_schedules(period, count)
        assert len(schedules) == 8
        assert all(all(gap == 8 for gap in x['gaps']) for x in schedules)
        timestamp_checks.append({'period_steps': period, 'receipts': count,
                                 'schedules': schedules})
    hashes = {}
    for name in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt',
                 '求解约束.txt', '求解充分条件.txt', '不补的设定.txt']:
        content = (SNAP / name).read_bytes()
        hashes[name] = {'sha256': hashlib.sha256(content).hexdigest(),
                        'lines': len(content.splitlines())}
    result = {
        'scope': 'One transport cell relaxation and outlet phase arithmetic; not a layout certificate.',
        'snapshots': hashes,
        'cell_graph': {str(k): v for k, v in graph.items()},
        'elementary_cycles': [{'states': p, 'reception_rewards': r,
                               'rate_per_step': str(Fraction(sum(r), len(p)))}
                              for p, r in cycles],
        'max_rate_per_step': str(maximum),
        'unique_max_cycle': best[0][0],
        'timestamp_encoding': timestamp_checks,
        'phase_counts_two_encodings': distinct_phase_counts(),
        'pass': True,
    }
    (HERE / 'full_rate_checks.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'pass': True, 'max_rate_per_step': str(maximum),
                      'unique_max_cycle': best[0][0]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
