#!/usr/bin/env python3
"""Replay reported cycles and compare full tuples, not only SHA-256 keys."""
import argparse
import hashlib
import json
from pathlib import Path

from factory_probe import EngineB, rebuild_order, setup, state_b

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--part', type=int, default=0)
    ap.add_argument('--parts', type=int, default=1)
    args = ap.parse_args()
    rows = json.loads((HERE / 'factory_summary.json').read_text())['results']
    records = []
    for pos, row in enumerate(rows):
        if pos % args.parts != args.part:
            continue
        f, rng = setup(row['seed'], row['maxlen'], row['initial'], row['grouping'], row.get('core_blue_outlets', 6))
        b = EngineB(f)
        before_a = before_b = counts = None
        for t in range(row['cycle_end']):
            if t == row['cycle_start']:
                before_a, before_b = f.state(), state_b(b)
                counts = (dict(f.delivered), [r.count for r in f.ore_routes])
            f.open = not any(lo <= t < hi for lo, hi in row['closed'])
            b.open = f.open
            if t in row['rebuild_steps']:
                rebuild_order(f, rng, reset=True)
                b.copy_order(f, reset=True)
            f.step()
            b.step()
            b.compare(f)
        assert before_a is not None and before_b is not None
        assert before_a == f.state(), (row['seed'], 'raw state A closure')
        assert before_b == state_b(b), (row['seed'], 'raw state B closure')
        delta = {k: f.delivered[k] - counts[0].get(k, 0) for k in f.delivered}
        minerals = [r.count - old for r, old in zip(f.ore_routes, counts[1])]
        assert delta == row['deliveries'] and minerals == row['mineral_counts']
        certificate = dict(seed=row['seed'], start=row['cycle_start'], end=row['cycle_end'],
                           equal_raw_states_a=True, equal_raw_states_b=True,
                           deliveries=delta, mineral_counts=minerals,
                           state_a=before_a, state_b=before_b)
        path = HERE / ('cycle_' + str(row['seed']) + '.json')
        path.write_text(json.dumps(certificate, ensure_ascii=False, separators=(',', ':')) + '\n')
        records.append(dict(seed=row['seed'], steps=f.t, certificate=path.name,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            equal_raw_states_a=True, equal_raw_states_b=True))
        print(json.dumps(records[-1], ensure_ascii=False), flush=True)
    (HERE / ('cycle_verification_' + str(args.part) + '.json')).write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
