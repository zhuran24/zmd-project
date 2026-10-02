"""Small independent certificates for the review's auxiliary conclusions."""
import itertools
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


def history_word(erase, implementation):
    word, times = [], []
    output = 0
    if implementation == 'timestamps':
        last = [None]*3
        available = [0]*3
        for t in range(60):
            if t in (0, 40):
                output += 3
            if erase and t == 30:
                last = [None]*3
            construction_order = [0, 1, 2] if t < 30 else [2, 1, 0]
            channels = sorted(range(3), key=lambda j: (
                last[j] is not None, last[j] if last[j] is not None else construction_order.index(j)))
            if output:
                for j in channels:
                    if available[j] <= t:
                        last[j], available[j] = t, t+8
                        output -= 1
                        word.append(j)
                        times.append(t)
                        break
    else:
        unseen = {0, 1, 2}
        visited = []
        waits = [0, 0, 0]
        for t in range(60):
            waits = [max(0, x-1) for x in waits]
            if t == 0 or t == 40:
                output += 3
            if t == 30 and erase:
                unseen, visited = {0, 1, 2}, []
            ports = [0, 1, 2] if t < 30 else [2, 1, 0]
            queue = [x for x in ports if x in unseen]+visited
            candidate = next((x for x in queue if waits[x] == 0), None)
            if candidate is not None and output:
                if candidate in unseen:
                    unseen.remove(candidate)
                else:
                    visited.remove(candidate)
                visited.append(candidate)
                waits[candidate] = 8
                output -= 1
                word.append(candidate)
                times.append(t)
    return dict(word=word, send_steps=times)


def capacity_cycle(n, encoding):
    if encoding == 'absolute':
        cells = [-8]*n
        splitter = -8
    else:
        cells = [0]*n
        splitter = 0
    seen, output_steps = {}, []
    for t in range(2000):
        if encoding == 'absolute':
            # Internal belt motion is not another external judgement. Mature
            # items with an already empty next cell can move before the splitter.
            for i in range(n-2, -1, -1):
                if cells[i] is not None and t-cells[i] >= 8 and cells[i+1] is None:
                    cells[i+1], cells[i] = t, None
            if splitter is not None and t-splitter >= 8 and cells[0] is None:
                cells[0], splitter = t, None
            for i in range(n-1, -1, -1):
                if cells[i] is not None and t-cells[i] >= 8:
                    if i == n-1:
                        output_steps.append(t)
                        cells[i] = None
                    elif cells[i+1] is None:
                        cells[i+1], cells[i] = t, None
            if splitter is None:
                splitter = t
            state = (min(8, t-splitter), tuple(None if v is None else min(8, t-v) for v in cells))
        else:
            splitter = max(0, splitter-1) if splitter is not None else None
            cells = [max(0, x-1) if x is not None else None for x in cells]
            for i in reversed(range(n-1)):
                if cells[i] == 0 and cells[i+1] is None:
                    cells[i+1], cells[i] = 8, None
            if splitter == 0 and cells[0] is None:
                splitter, cells[0] = None, 8
            for i in reversed(range(n)):
                if cells[i] == 0:
                    if i+1 == n:
                        output_steps.append(t)
                        cells[i] = None
                    elif cells[i+1] is None:
                        cells[i+1], cells[i] = 8, None
            if splitter is None:
                splitter = 8
            state = (8-splitter, tuple(None if v is None else 8-v for v in cells))
        if state in seen:
            start, end = seen[state], t
            delivered = sum(start < u <= end for u in output_steps)
            return dict(first=start, second=end, period=end-start, items=delivered,
                        rate=str(Fraction(8*delivered, end-start)))
        seen[state] = t
    raise AssertionError('no repeated state')


def pair_poll_example():
    # Both axes of a single physical bridge are mature. East and north receiving
    # belts are empty. Rule 29 permits both components to judge in the same step.
    source = {'bridge_horizontal': {'previous_unit': 'west_belt', 'age': 8},
              'bridge_vertical': {'previous_unit': 'south_belt', 'age': 8}}
    targets = {'east_belt': None, 'north_belt': None}
    events = []
    for axis, dest in [('bridge_horizontal', 'east_belt'), ('bridge_vertical', 'north_belt')]:
        item = source[axis]
        assert item['previous_unit'] != dest and targets[dest] is None
        targets[dest] = dict(previous_unit='bridge', age=0)
        source[axis] = None
        events.append([axis, dest])
    # A second encoding counts two independent one-slot channels.
    empty_dest, mature_source = [True, True], [True, True]
    independently = sum(a and b for a, b in zip(empty_dest, mature_source))
    assert len(events) == independently == 2
    return dict(events=events, physical_bridge_successes=2)


def run():
    history = {}
    for erase in [False, True]:
        a, b = history_word(erase, 'timestamps'), history_word(erase, 'queue')
        assert a == b
        history['erased' if erase else 'preserved'] = a
    assert history['preserved']['word'] == [0, 1, 2, 0, 1, 2]
    assert history['erased']['word'] == [0, 1, 2, 2, 1, 0]
    capacity = []
    for n in range(1, 9):
        a, b = capacity_cycle(n, 'absolute'), capacity_cycle(n, 'timers')
        assert a == b
        assert Fraction(a['rate']) == Fraction(8*n, 8*n+1)
        capacity.append(dict(n=n, **a))
    result = dict(history_sensitivity=history,
                  history_scope='erasure is an extra semantics diagnostic, not an asserted rule transition',
                  capacity=capacity,
                  capacity_scope='saturated local service model; bound proof applies generally',
                  bridge_components=pair_poll_example())
    (HERE/'local_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
