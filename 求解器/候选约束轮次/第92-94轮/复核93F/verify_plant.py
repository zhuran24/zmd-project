#!/usr/bin/env python3
"""Cross-check ONLY the two fresh review implementations, never author code."""
import copy
import hashlib
import itertools
import json
from pathlib import Path

from plant_a import Plant
from plant_b import fresh, tick, describe

OUT = Path(__file__).resolve().parent
PATHS = ('CA','CB','AC','BK','K0','K1')
LABELS = 'ABCK'


def assert_equal(a,b):
    # JSON normalizes tuple/list representation. Exact quantities, ongoing
    # batch completion times, every physical cell's entry time, and history.
    assert json.loads(json.dumps(a.state())) == json.loads(json.dumps(describe(b)))
    for i,x in enumerate(LABELS):
        assert a.machines[x].started == b['starts'][i]
        assert a.machines[x].finished == b['finishes'][i]
    for i,r in enumerate(PATHS):
        translated = [None if v < 0 else b['clock']-1-v for v in b['ages'][i]]
        assert [c.enter for c in a.routes[r]] == translated
        assert a.last[r] == b['picked'][i]
    actual_cursor = 4 if a.receive_last in (None,'K1') else 5
    assert actual_cursor == b['cursor']


def main():
    lengths = (7,13,31,5,5,5)
    a,b = Plant(lengths),fresh(lengths)
    a.add('A',50)
    b['machines'][0][0] = 50
    samples = []
    checkpoints = {8,2464,3248,5000}
    sha = hashlib.sha256()
    trace = []
    for n in range(6001):
        assert_equal(a,b)
        sha.update(json.dumps(a.state(),sort_keys=True).encode())
        if n in checkpoints:
            samples.append((copy.deepcopy(a),copy.deepcopy(b)))
        if n < 18 or n in (2464,2465,3248,3249,4000,4500,5000,6000):
            trace.append(a.state())
        if n != 6000:
            a.step()
            tick(b)
    # Inventory is completely motionless after saturation; clocks and ages
    # continue, but stock, finished batches, output and route counts do not.
    fixed = a.state()
    core_keys = ('phi2','stock','output','batch','route_counts','sink','sent','arrivals')
    for _ in range(80):
        a.step(); tick(b)
        assert_equal(a,b)
        now = a.state()
        assert all(now[k] == fixed[k] for k in core_keys)
    checked = 0
    # Fixed connection ranks and success records: vary judgments only.
    for sample_a,sample_b in samples:
        ref = copy.deepcopy(sample_a)
        ref.step()
        expected = ref.canonical()
        for component_perm in itertools.permutations(range(6)):
            for machine_perm in itertools.permutations(range(4)):
                aa,bb = copy.deepcopy(sample_a),copy.deepcopy(sample_b)
                aa.route_order = tuple(PATHS[j] for j in component_perm)
                aa.order = tuple(LABELS[j] for j in machine_perm)
                aa.step()
                tick(bb,machine_perm,component_perm)
                assert aa.canonical() == expected
                assert_equal(aa,bb)
                checked += 1
    result = {'cross_checked_states': 6081,
              'state_trace_sha256': sha.hexdigest(),
              'checkpoints': sorted(checkpoints), 'orders_per_checkpoint': 720*24,
              'checked_order_cases': checked, 'differences': 0,
              'permanent_saturation_state': fixed, 'trace': trace}
    (OUT/'verify_plant.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('cross_checked_states','checked_order_cases','differences')},ensure_ascii=False))


if __name__ == '__main__':
    main()
