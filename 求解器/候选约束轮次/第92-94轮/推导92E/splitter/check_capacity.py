#!/usr/bin/env python3
"""Two independent local encodings; no imports from the repository simulator.

Local projection of source -> X(splitter) -> B(n belt cells) -> G -> sink.
X additionally has a full dead branch D1 -> D2 (admission gates). D1 has
layer 1, B has layer 2, X can choose D1 and have layer 2. Thus X before B
is permitted by a same-layer connection order. The dead cells never move.
G judges before X and B, and source replenishes X after every component.
"""
from fractions import Fraction
import json
from pathlib import Path


def timestamp_encoding(n, early, full):
    # Each cell stores the absolute integer step when its item arrived.
    x = -8 if full else None
    b = [-8 if full else None for _ in range(n)]
    g = -8 if full else None
    seen, rows = {}, []
    for t in range(100000):
        def settle():
            for j in reversed(range(n - 1)):
                if b[j] is not None and t - b[j] >= 8 and b[j + 1] is None:
                    b[j + 1], b[j] = t, None

        settle()
        out_b = 0
        if g is not None and t - g >= 8:
            g = None
        for unit in ('X', 'B') if early else ('B', 'X'):
            if unit == 'X':
                if x is not None and t - x >= 8 and b[0] is None:
                    b[0], x = t, None
                    settle()
            elif b[-1] is not None and t - b[-1] >= 8 and g is None:
                g, b[-1], out_b = t, None, 1
                settle()
        if x is None:
            x = t
        state = tuple(-1 if v is None else min(8, t - v) for v in [x, *b, g])
        rows.append((out_b, sum(v is not None for v in b), state))
        if state in seen:
            start = seen[state] + 1
            return rows[start:], start
        seen[state] = t
    raise RuntimeError('cycle not found')


def countdown_encoding(n, early, full):
    # Fixed array and readiness countdowns. No absolute entry timestamps.
    # slots: splitter, belt cells in downstream-to-upstream order, G.
    empty = -1
    slots = [0 if full else empty] * (n + 2)
    history, steps = {}, []
    for step in range(100000):
        for i in range(len(slots)):
            if slots[i] > 0:
                slots[i] -= 1

        def internal_motion():
            # Belt cells are reversed: index 1 is its exit, index n its entry.
            for dest in range(1, n):
                src = dest + 1
                if slots[dest] == empty and slots[src] == 0:
                    slots[dest], slots[src] = 8, empty

        internal_motion()
        if slots[-1] == 0:
            slots[-1] = empty
        sent = 0
        for selector in [0, 1] if early else [1, 0]:
            if selector == 0 and slots[0] == 0 and slots[n] == empty:
                slots[0], slots[n] = empty, 8
                internal_motion()
            if selector == 1 and slots[1] == 0 and slots[-1] == empty:
                slots[1], slots[-1], sent = empty, 8, 1
                internal_motion()
        if slots[0] == empty:
            slots[0] = 8
        canonical = [slots[0], *reversed(slots[1:n + 1]), slots[-1]]
        canonical = tuple(empty if v == empty else 8 - v for v in canonical)
        steps.append((sent, sum(v != empty for v in slots[1:n + 1]), canonical))
        if canonical in history:
            start = history[canonical] + 1
            return steps[start:], start
        history[canonical] = step
    raise RuntimeError('cycle not found')


def main():
    rows = []
    for n in range(1, 33):
        for early in [False, True]:
            for full in [False, True]:
                a, start_a = timestamp_encoding(n, early, full)
                b, start_b = countdown_encoding(n, early, full)
                assert a == b and start_a == start_b
                period = len(a)
                count = sum(row[0] for row in a)
                occupied = sum(row[1] for row in a)
                rate = Fraction(8 * count, period)
                expected = Fraction(8 * n, 8 * n + 1) if early else Fraction(1)
                assert rate == expected
                assert occupied >= 8 * n * count
                if early:
                    assert occupied <= n * period - count
                    assert all(not sent or occ <= n - 1 for sent, occ, _ in a)
                rows.append(dict(n=n, splitter_first=early, initial_full=full,
                                 period_steps=period, belt_out=count,
                                 occupied_step_cells=occupied,
                                 rate_per_tick=str(rate), transient_steps=start_a,
                                 residence_lower_bound=8*n*count,
                                 vacancy_upper_bound=n*period-count if early else n*period,
                                 independent_encodings_agree=True))
    result = dict(status='pass', cases=len(rows), belt_lengths=[1,32],
                  statement='Finite local checks corroborate the analytic all-cycle bound; they do not certify a factory layout.',
                  rows=rows)
    output = Path(__file__).with_name('capacity_checks.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status='pass', cases=len(rows), output=str(output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
