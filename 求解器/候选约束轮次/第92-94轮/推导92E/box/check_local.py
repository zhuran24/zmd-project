#!/usr/bin/env python3
"""Independent small state encodings for local ordering lemmas, not layouts.

Only one-way actual item motion is represented. Reverse bridge channels affect
the old grouping order but cannot carry an item back to its previous unit.
"""
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).parent


def absolute_clock(order, steps=1000):
    entered = [-8, -8, -8]  # U, A, B; always-supplied U, always-open sink
    transfers = [[] for _ in range(3)]
    for t in range(steps):
        for i in order:
            if entered[i] is None or t - entered[i] < 8:
                continue
            if i < 2 and entered[i + 1] is not None:
                continue
            entered[i] = None
            if i < 2:
                entered[i + 1] = t
            transfers[i].append(t)
        if entered[0] is None:
            entered[0] = t  # warehouse pickup judges after components
    return transfers


def countdown_clock(order, steps=1000):
    # -1 empty; 0 ready; positive number of future step beginnings until ready.
    cells = [0, 0, 0]
    result = [[], [], []]
    for t in range(steps):
        cells = [max(0, c-1) if c >= 0 else -1 for c in cells]
        for origin in order:
            if cells[origin] != 0:
                continue
            destination = origin+1
            if destination != 3 and cells[destination] >= 0:
                continue
            cells[origin] = -1
            if destination != 3:
                cells[destination] = 8
            result[origin].append(t)
        if cells[0] == -1:
            cells[0] = 8
    return result


def box_absolute(steps=1000):
    incoming, outgoing, stock = -8, -8, 300
    receipts, shipments = [], []
    for t in range(steps):
        if outgoing is not None and t-outgoing >= 8:
            outgoing = None
        if incoming is not None and t-incoming >= 8 and stock < 300:
            incoming = None
            stock += 1
            receipts.append(t)
        if stock and outgoing is None:
            stock -= 1
            outgoing = t
            shipments.append(t)
        if incoming is None:
            incoming = t
    return receipts, shipments


def box_countdown(steps=1000):
    before, after, content = 0, 0, 300
    accepted, exported = [], []
    for step in range(steps):
        before = max(0,before-1) if before >= 0 else -1
        after = max(0,after-1) if after >= 0 else -1
        if after == 0:
            after = -1
        if before == 0 and content != 300:
            content += 1
            before = -1
            accepted.append(step)
        if after == -1 and content:
            after = 8
            content -= 1
            exported.append(step)
        if before == -1:
            before = 8
    return accepted, exported


def main():
    rows = []
    for order in ((2,0,1),(0,2,1),(1,2,0),(1,0,2),(2,1,0)):
        a, b = absolute_clock(order), countdown_clock(order)
        assert a == b
        gaps = [v-u for u,v in zip(a[1],a[1][1:])]
        assert len(set(gaps[2:])) == 1
        gap = gaps[-1]
        rows.append(dict(order=list(order),
                         reading='amended' if order == (2,1,0) else 'current',
                         A_to_B_first=a[1][:12], steady_gap=gap,
                         exact_rate=str(Fraction(8,gap)),
                         independent_encodings_equal=True))
    assert all(row['exact_rate']=='8/9' for row in rows[:-1])
    assert rows[-1]['exact_rate']=='1'
    a,b=box_absolute(),box_countdown()
    assert a==b
    assert all(v-u==8 for seq in a for u,v in zip(seq,seq[1:]))
    result=dict(bridge_group_cases=rows,
                full_box=dict(receipts_first=a[0][:10],shipments_first=a[1][:10],
                              exact_rate='1', one_step_phase_difference=True,
                              independent_encodings_equal=True),
                scope='Local order certificates; no complete layout or reachability claim.')
    (HERE/'local_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
