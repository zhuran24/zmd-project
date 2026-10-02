#!/usr/bin/env python3
"""Read-only snapshot audit: independent arithmetic and a stepwise S02 witness."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE.parent / '前提快照'
SIM = HERE.parents[2] / '规则修订/2026-09-30-迟滞/sim2/simulator.py'
spec = importlib.util.spec_from_file_location('sim2_92c_root', SIM)
s = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = s
spec.loader.exec_module(s)

def simulate_wrong_material():
    box = s.Box('协议储存箱', wireless=False)
    box.slots[0] = [s.Item('荞花种子') for _ in range(50)]
    box.slots[1] = [s.Item('荞花种子')]
    belt = s.Belt('传送带')
    machine = s.Machine('研磨机', auxiliary=True, recipes=[
        s.Recipe('致密蓝铁粉末', (('蓝铁粉末', 2), ('砂叶粉末', 1)), '致密蓝铁粉末')])
    machine.slots = [[], []]
    box.connect(belt, 0)
    belt.connect(machine, 1)
    world = s.World([box, belt, machine], trace=True)
    actual = []
    for t in range(425):
        world.step()
        item = belt.cells[0]
        actual.append([t, sum(map(len, box.slots)), [len(x) for x in machine.slots],
                       None if item is None else min(t-item.entered, 8)])

    # Independent integer transition system, no simulator classes or methods.
    pending, stock, entered = 51, 0, None
    expected = []
    for t in range(425):
        if entered is not None and t-entered >= 8 and stock < 50:
            stock += 1
            entered = None
        if pending and entered is None:
            pending -= 1
            entered = t
        expected.append([t, pending, [stock, 0],
                         None if entered is None else min(t-entered, 8)])
    assert actual == expected
    assert len(machine.received) == 50 and not machine.starts
    assert actual[-1][1:] == [0, [50, 0], 8]
    (HERE/'s02_wrong_material_trace.json').write_text(json.dumps(
        {'states': actual, 'events': world.events}, ensure_ascii=False, indent=2))
    return {'steps_compared': len(actual), 'received': len(machine.received),
            'last_receive_step': machine.received[-1][0],
            'permanently_blocked_from_step': 408,
            'independent_encodings_equal': True,
            'scope': 'Literal missing-alphabet premise only; not a whole-factory layout.'}

def arithmetic():
    rows = []
    for name, a, b, m in [('研磨机', 2, 1, 6), ('封装机', 10, 15, 5), ('灌装机', 10, 10, 6)]:
        g = math.gcd(a,b)
        z0 = 50*(b-a)
        lo = b*(a-1)-50*a
        hi = 50*b-a*(b-1)
        c = min(z0-lo, hi-z0)
        # Independent: enumerate all full-one-kind/short-the-other stocks.
        lower_bad = [b*x-a*50 for x in range(a)]
        upper_bad = [b*50-a*y for y in range(b)]
        c2 = min(z0-max(lower_bad), min(upper_bad)-z0)
        # Enumerate every attainable prefix of one balanced block.
        prefix_values = [b*x-a*y for x in range(a//g+1) for y in range(b//g+1)]
        deviation = max(prefix_values)-min(prefix_values)
        assert (lo, hi, c) == (max(lower_bad), min(upper_bad), c2)
        assert deviation == 2*a*b//g
        assert m*deviation < c
        rows.append(dict(machine=name,a=a,b=b,g=g,m=m,Z0=z0,L=lo,U=hi,C=c,
                         arbitrary_origin_bound=m*deviation,passes=True))
    # S01: 3 inlet channels, minimum 8 steps between arrivals, 40-step half-open window.
    count1 = [sum(0 <= phase+8*j < 40 for j in range(6)) for phase in range(8)]
    # Independent recurrence choosing as early an arrival as possible.
    count2=[]
    for phase in range(8):
        t, n = phase, 0
        while t < 40:
            n += 1
            t += 8
        count2.append(n)
    assert count1 == count2 == [5]*8
    return {'S03': rows, 'S01_max_arrivals_between_transmissions': 3*max(count1),
            'two_independent_encodings_equal': True}

result = {'snapshot_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(SNAP.glob('*.txt'))}, 'S02': simulate_wrong_material(),
          'arithmetic': arithmetic()}
(HERE/'s01_s05_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False, indent=2))
