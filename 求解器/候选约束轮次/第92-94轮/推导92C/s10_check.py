#!/usr/bin/env python3
"""S10: independent count engine versus sim2, only supported directed paths.

All files emitted under this script's directory; no pycache.  One process/core.
The blue-iron block/powder loop uses actual snapshot recipes and conserves items.
"""
import importlib.util
import json
import sys
from itertools import product
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SIMPATH = ROOT / '求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py'
spec = importlib.util.spec_from_file_location('s10_sim2', SIMPATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
spec.loader.exec_module(sim)


def make_world(lengths, styles, phase, reverse):
    y = sim.Machine('Y', recipes=[sim.Recipe('refine', (('powder', 1),), 'block')])
    x = sim.Machine('X', recipes=[sim.Recipe('crush', (('block', 1),), 'powder')])
    for m, kind, remaining in ((y, 'powder', 1), (x, 'block', phase)):
        m.slots[0] = [sim.Item(kind) for _ in range(49)]
        m.running, m.remaining = m.recipes[0], remaining
    nodes, paths = [y, x], []
    for p, (src, dst, length, style) in enumerate(zip((y, x), (x, y), lengths, styles)):
        route = [sim.Belt(f'b{p}', length)] if style == 'belt' else [sim.Gate(f'g{p}_{i}') for i in range(length)]
        prev = src
        for u in route:
            prev.connect(u)
            prev = u
        prev.connect(dst)
        nodes += route
        paths.append(route)
    layers = sim.layers_for(nodes)
    components = sorted((n for n in nodes if n.component), key=lambda n: (layers[n.name], n.name), reverse=False)
    # Equal-layer order is changed independently of nontransport order.
    if reverse:
        components = sorted(components, key=lambda n: (layers[n.name], ''.join(chr(255-ord(c)) for c in n.name)))
    nts = [x, y] if reverse else [y, x]
    schedule = {'order': [u.name for u in components+nts], 'choices': {}}
    return sim.World(nodes, schedule=schedule), (y, x), paths


def sim_state(w, machines, paths):
    return (
        tuple((len(m.slots[0]), len(m.output), m.remaining or 0, len(m.cache)) for m in machines),
        tuple(tuple(None if i is None else min(8, w.t-1-i.entered) for u in path for i in u.cells) for path in paths),
    )


class CountEngine:
    """No sim2 transfer/judgement/storage implementation is reused."""
    def __init__(self, lengths, phase, reverse):
        self.machines = [[49, 0, 1, 0], [49, 0, phase, 0]]
        self.paths = [[None]*n for n in lengths]
        self.t, self.reverse = 0, reverse

    @staticmethod
    def flush(m):
        if m[3] and m[1]+m[3] <= 50:
            m[1] += m[3]
            m[3] = 0

    def step(self):
        for m in self.machines:
            if m[2]:
                m[2] -= 1
                if not m[2]:
                    m[3] = 1
            self.flush(m)
        # All transport moves are downstream-to-upstream. Different paths
        # commute: they write distinct inventories and have one source each.
        for p in (1, 0) if self.reverse else (0, 1):
            cells, dst = self.paths[p], self.machines[1-p]
            if cells[-1] is not None and self.t-cells[-1] >= 8 and dst[0] < 50:
                dst[0] += 1
                cells[-1] = None
            for j in range(len(cells)-2, -1, -1):
                if cells[j] is not None and cells[j+1] is None and self.t-cells[j] >= 8:
                    cells[j+1], cells[j] = self.t, None
        for p in (1, 0) if self.reverse else (0, 1):
            src, cells = self.machines[p], self.paths[p]
            if src[1] and cells[0] is None:
                src[1] -= 1
                cells[0] = self.t
                self.flush(src)
        for m in self.machines:
            if not m[2] and not m[3] and m[0]:
                m[0] -= 1
                m[2] = 8
        self.t += 1

    def state(self):
        return tuple(tuple(m) for m in self.machines), tuple(tuple(None if t is None else min(8, self.t-1-t) for t in cells) for cells in self.paths)


def verify_loops():
    cases, periods, max_transient = 0, set(), 0
    example = []
    for lengths, styles, phase, reverse in product(product(range(1, 5), repeat=2), product(('belt', 'gate'), repeat=2), range(1, 9), (False, True)):
        w, machines, paths = make_world(lengths, styles, phase, reverse)
        independent = CountEngine(lengths, phase, reverse)
        seen, cycle = {}, None
        for t in range(160):
            w.step()
            independent.step()
            a, b = sim_state(w, machines, paths), independent.state()
            assert a == b, (lengths, styles, phase, reverse, t, a, b)
            assert all(m[2] or m[3] for m in a[0]), ('empty cache', t, a)
            if a in seen:
                cycle = (seen[a], t+1-seen[a])
                break
            seen[a] = t+1
            if lengths == (2, 3) and styles == ('gate', 'belt') and phase == 4 and not reverse and t < 32:
                example.append({'step': t, 'machines': a[0], 'path_ages': a[1]})
        assert cycle is not None
        start, period = cycle
        assert all(all(cell is not None for cell in path) for path in a[1])
        periods.add(period)
        max_transient = max(max_transient, start)
        cases += 1
    return {'cases': cases, 'all_step_states_identical': True, 'cache_empty_steps': 0,
            'cycle_periods_steps': sorted(periods), 'maximum_cycle_entry_step': max_transient,
            'cycle_paths_full_after_every_step': True, 'example': example}


def verify_batch_single_out():
    results = []
    for quantity, consumer_period in product((1, 2, 3), (1, 8, 9, 16, 40)):
        m = sim.Machine('M', recipes=[sim.Recipe('plant', (('plant', 1),), 'powder', quantity)])
        m.slots[0] = [sim.Item('plant') for _ in range(50)]
        m.output = [sim.Item('powder') for _ in range(50)]
        m.cache = [sim.Item('powder') for _ in range(quantity)]
        b, sink = sim.Belt('belt'), sim.Sink('receiver', every=consumer_period)
        m.connect(b).connect(sink)
        w = sim.World([m, b, sink])
        for t in range(200):
            w.step()
            assert m.running is not None or m.cache
            assert b.cells[0] is not None
        times = [e[0] for e in m.sent]
        results.append({'batch': quantity, 'receiver_min_gap_steps': consumer_period,
                        'first_cell_full_all_200_step_ends': True,
                        'deliveries': len(times), 'first_deliveries': times[:8]})
    return results


def simultaneous_outlets():
    """Local timing check only: a scheduled receiver is not a layout certificate."""
    m = sim.Machine('M', recipes=[sim.Recipe('sand', (('sand', 1),), 'powder', 3)])
    m.slots[0] = [sim.Item('sand') for _ in range(50)]
    m.output = [sim.Item('powder') for _ in range(50)]
    m.cache = [sim.Item('powder') for _ in range(3)]
    belts = [sim.Belt(f'b{i}').fill('powder') for i in range(3)]
    sinks = [sim.Sink(f'z{i}', every=16) for i in range(3)]
    for b, z in zip(belts, sinks):
        m.connect(b).connect(z)
    w = sim.World([m]+belts+sinks, trace=True)
    trace = []
    for t in range(3):
        w.step()
        trace.append({'step': t, 'first_cells_full': [b.cells[0] is not None for b in belts],
                      'output': len(m.output), 'cache_complete': len(m.cache),
                      'running': m.remaining})
    # The independent argument has only a queue with service 1 per step.
    pending, serviced, independent = [0, 1, 2], [], []
    for t in range(3):
        serviced.append(pending.pop(0))
        independent.append([i in serviced for i in range(3)])
    assert [x['first_cells_full'] for x in trace] == independent
    return {'scope': 'local reachable transition, not full cyclic-layout witness',
            'two_encodings_agree': True, 'refill_steps': [0, 1, 2], 'trace': trace}


def wrong_slot_fixed_point():
    """Exact rule 13 blocks Y's product flush; baseline sim2 lacks that check."""
    class StrictMachine(sim.Machine):
        def flush(self, w):
            if self.cache and any(s and s[0].kind == self.cache[0].kind for s in self.slots):
                return
            return super().flush(w)

    y = StrictMachine('Y', recipes=[sim.Recipe('crush_block', (('block', 1),), 'powder')])
    x = StrictMachine('X', recipes=[sim.Recipe('refine_powder', (('powder', 1),), 'block')])
    y.slots[0] = [sim.Item('block')]
    loading = sim.Belt('debug_loading').fill('powder')
    loading.connect(y)
    route = sim.Belt('dedicated_route')
    y.connect(route).connect(x)
    w = sim.World([y, x, loading, route])
    trace = []
    independent = []
    for t in range(24):
        w.step()
        state = {'step': t, 'Y_input': [i.kind for i in y.slots[0]],
                 'Y_remaining': y.remaining, 'Y_output': len(y.output),
                 'Y_completed_cache': [i.kind for i in y.cache],
                 'X_running': x.running is not None, 'X_cache': len(x.cache)}
        trace.append(state)
        # Independent transition table: block consumed at 0; powder enters
        # at 1; completion at 8, then the one-kind-one-slot rule blocks flush.
        expected = {'step': t, 'Y_input': [] if t == 0 else ['powder'],
                    'Y_remaining': 8-t if t < 8 else None, 'Y_output': 0,
                    'Y_completed_cache': [] if t < 8 else ['powder'],
                    'X_running': False, 'X_cache': 0}
        independent.append(expected)
        assert state == expected
    return {'two_encodings_agree': True, 'stable_from_step': 8,
            'period_steps': 1, 'Y_cache_nonempty_all_step_ends': True,
            'X_cache_empty_all_step_ends': True,
            'sim2_local_patch': 'enforce rule 13 input/output kind uniqueness in flush',
            'trace': trace}


if __name__ == '__main__':
    result = {'loop': verify_loops(), 'single_out_batch_checks': verify_batch_single_out(),
              'multiple_outlets_local_check': simultaneous_outlets(),
              'wrong_slot_fixed_point': wrong_slot_fixed_point()}
    target = HERE / 's10_results.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'result_path': str(target), 'loop': {k: v for k, v in result['loop'].items() if k != 'example'},
                      'batch_cases': len(result['single_out_batch_checks']),
                      'multiple_outlet_refill_steps': result['multiple_outlets_local_check']['refill_steps']}, ensure_ascii=False))
