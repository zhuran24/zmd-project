#!/usr/bin/env python3
"""Independent integral network layers on the 1113 geometric relaxation.

Ore layer K=1; all-item layer K=20. These are integral substitute flows,
not an assumption about the period or denominator of actual factory flows.
All writes are confined to this directory. Run with python -B.
"""
import argparse
from collections import defaultdict, Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time

sys.dont_write_bytecode = True
from ortools.sat.python import cp_model
import ortools
import psutil
from geometry import build as build_geometry
from filter_positions import PATTERNS, port_sides

ROOT = Path(__file__).resolve().parent
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
OPP = (2, 3, 0, 1)
TYPES = {'small': {'crush': 68, 'refine': 51, 'parts': 6, 'mold': 6},
         'medium': {'plant': 32, 'seed': 16},
         'large': {'grind': 32, 'pack': 3, 'fill': 3}}
# Bounds in units of 1/20 item/tick. No per-machine input/output ratios.
BOUNDS = {'crush': (20, 20, 20, 60), 'refine': (20, 20, 20, 20),
          'parts': (20, 20, 20, 20), 'mold': (0, 40, 0, 20),
          'plant': (20, 20, 20, 20), 'seed': (20, 20, 40, 40),
          'grind': (0, 60, 0, 20), 'pack': (100, 100, 4, 4),
          'fill': (0, 80, 0, 4)}
TOTAL_LO = {'crush': (1360, 1890), 'refine': (1020, 1020),
            'parts': (120, 120), 'mold': (220, 110),
            'plant': (640, 640), 'seed': (320, 640),
            'grind': (1890, 630), 'pack': (300, 12), 'fill': (220, 11)}


def ports(rect, axis, ts, core=False):
    """Pairs (transport cell, direction from transport cell towards body)."""
    return [[(c, axis if j == 0 else axis + 2)
             for c in edge if c in ts and min(c) >= 1]
            for j, edge in enumerate(port_sides(rect, axis, core))]


def add_cell_conservation(model, incoming, outgoing, t, b, K):
    """For fixed t,b these rows are exactly a split-node capacity network.

    Ordinary cell: one node of capacity K, permits arbitrary turns/splits.
    Bridge: independent H,V nodes of capacity K each; no cross-axis arcs.
    Port direction and automatic adjacency are deliberately relaxed.
    """
    model.add(sum(sum(q) for q in incoming) == sum(sum(q) for q in outgoing))
    model.add(sum(sum(q) for q in incoming) <= K * (t + b))
    for ax in (0, 1):
        ii = sum(incoming[ax] + incoming[ax + 2])
        oo = sum(outgoing[ax] + outgoing[ax + 2])
        model.add(ii == oo).only_enforce_if(b)
        model.add(ii <= K).only_enforce_if(b)


def build(position, layer='ore', cut_mode='formal'):
    begin = time.monotonic()
    # Keep all P branches, and all 47 warehouse patterns. No DP bounds.
    position = dict(position, allowed_P=[10, 11, 12], patterns=list(range(47)))
    model, meta = build_geometry(position, False, cut_mode)
    ts = meta['ts']
    bridges = {c: model.new_bool_var(f'bridge_{c[0]}_{c[1]}') for c in ts}
    for c in ts:
        model.add(bridges[c] <= ts[c])
    model.add(sum(ts.values()) + sum(bridges.values()) >= 306)
    # Unoriented geometric placements are refined into selected type/input side.
    typed, typevars = [], defaultdict(list)
    for idx, (kind, rect, axis, geo) in enumerate(meta['placements']):
        if kind not in TYPES or (layer == 'ore' and kind != 'small'):
            continue
        edges = ports(rect, axis, ts)
        alternatives = []
        types = TYPES[kind] if layer == 'all' else {'crush': 68, 'refine': 51}
        for name in types:
            for side in (0, 1):
                v = model.new_bool_var(f'type_{idx}_{name}_{side}')
                alternatives.append(v)
                typevars[name].append(v)
                typed.append(dict(kind=name, rect=rect, axis=axis, side=side,
                                  var=v, geo=geo, inports=edges[side], outports=edges[1-side]))
        if layer == 'ore':
            v = model.new_bool_var(f'other_small_{idx}')
            alternatives.append(v)
            typevars['other_small'].append(v)
        model.add(sum(alternatives) == geo)
    counts = {k: n for group in TYPES.values() for k, n in group.items()}
    counts['other_small'] = 12
    for k, vs in typevars.items():
        model.add(sum(vs) == counts[k])

    # Machine-port support, where at most one selected body can own a port.
    supports = {'ore_in': defaultdict(list), 'all_in': defaultdict(list),
                'all_out': defaultdict(list), 'core_out': defaultdict(list),
                'core_in': defaultdict(list)}
    cores = []
    for p in typed:
        if p['kind'] in ('crush', 'refine'):
            for e in p['inports']:
                supports['ore_in'][e].append(p['var'])
        if layer == 'all':
            for e in p['inports']:
                supports['all_in'][e].append(p['var'])
            for e in p['outports']:
                supports['all_out'][e].append(p['var'])
    for kind, rect, axis, v in meta['placements']:
        if kind != 'core':
            continue
        outp = [e for edge in ports(rect, axis, ts, True) for e in edge]
        raw = port_sides(rect, 1-axis)
        inp = [(edge[i], (1-axis) if j == 0 else (3-axis))
               for j, edge in enumerate(raw) for i in range(1, 8)
               if edge[i] in ts and min(edge[i]) >= 1]
        for e in outp:
            supports['core_out'][e].append(v)
        for e in inp:
            supports['core_in'][e].append(v)
        cores.append(dict(rect=rect, axis=axis, var=v, inports=inp, outports=outp))
    warehouse = defaultdict(list)
    for i, v in meta['choices'].items():
        for c in PATTERNS[i]['ports']:
            c = tuple(c)
            # direction from cell towards source: west or south.
            warehouse[(c, 2 if c[0] == 1 else 3)].append(v)
    # The (1,1) port can belong to left OR bottom patterns. Use origins to
    # distinguish it: reconstruct each pattern's independent left/bottom lists.
    warehouse.clear()
    for i, v in meta['choices'].items():
        for j, c in enumerate(PATTERNS[i]['ports']):
            warehouse[(tuple(c), 2 if j < 23 else 3)].append(v)

    layers = {}
    for name, K in [('ore', 1)] + ([('all', 20)] if layer == 'all' else []):
        edgeflow, machine_in, machine_out, core_src, core_sink = {}, {}, {}, {}, {}
        incoming = {c: [[] for _ in DIRS] for c in ts}
        outgoing = {c: [[] for _ in DIRS] for c in ts}
        for c in ts:
            for d, (dx, dy) in enumerate(DIRS):
                n = c[0] + dx, c[1] + dy
                if n not in ts:
                    continue
                f = model.new_int_var(0, K, f'{name}_edge_{c[0]}_{c[1]}_{d}')
                model.add(f <= K * ts[c])
                model.add(f <= K * ts[n])
                edgeflow[c, d] = f
                outgoing[c][d].append(f)
                incoming[n][OPP[d]].append(f)
        def portflows(support, prefix, table, is_source, exact=False):
            for (c, d), vs in support.items():
                f = model.new_int_var(0, K, f'{name}_{prefix}_{c[0]}_{c[1]}_{d}')
                if exact:
                    model.add(f == K * sum(vs))
                else:
                    model.add(f <= K * sum(vs))
                model.add(f <= K * ts[c])
                table[c, d] = f
                (incoming if is_source else outgoing)[c][d].append(f)
        portflows(supports[name + '_in'], 'mi', machine_in, False)
        if name == 'all':
            portflows(supports['all_out'], 'mo', machine_out, True)
            portflows(supports['core_in'], 'ci', core_sink, False)
        portflows(supports['core_out'], 'co', core_src, True, True)
        src = {}
        portflows(warehouse, 'wh', src, True, True)
        for c in ts:
            add_cell_conservation(model, incoming[c], outgoing[c], ts[c], bridges[c], K)
        rates = defaultdict(list)
        for p in typed:
            k, v = p['kind'], p['var']
            if name == 'ore':
                if k not in ('crush', 'refine'):
                    continue
                r = model.new_int_var(0, 1, f'ore_recv_{v.index}')
                model.add(r <= v)
                model.add(r == sum(machine_in[e] for e in p['inports'])).only_enforce_if(v)
                rates[k, 'in'].append(r)
            else:
                il, ih, ol, oh = BOUNDS[k]
                for label, lo, hi, es, table in [('in', il, ih, p['inports'], machine_in),
                                                ('out', ol, oh, p['outports'], machine_out)]:
                    expr = sum(table[e] for e in es)
                    if lo == hi:
                        model.add(expr == lo).only_enforce_if(v)
                    else:
                        r = model.new_int_var(0, hi, f'all_rate_{label}_{v.index}')
                        model.add(r >= lo * v)
                        model.add(r <= hi * v)
                        model.add(r == expr).only_enforce_if(v)
                        rates[k, label].append(r)
        if name == 'ore':
            # Raw ore is neither produced by a machine nor deposited in core.
            # All 52 sources are equalities. Consumption is exactly 18+34.
            model.add(sum(rates['crush', 'in']) == 18)
            model.add(sum(rates['refine', 'in']) == 34)
        else:
            for (k, label), vs in rates.items():
                model.add(sum(vs) >= TOTAL_LO[k][0 if label == 'in' else 1])
            for p in cores:
                model.add(sum(core_sink[e] for e in p['inports']) >= 23).only_enforce_if(p['var'])
        layers[name] = dict(K=K, edgeflow=edgeflow, machine_in=machine_in,
                            machine_out=machine_out, core_src=core_src,
                            core_sink=core_sink, warehouse=src)
    meta.update(bridges=bridges, typed=typed, layers=layers, cores=cores,
                build_seconds=time.monotonic()-begin)
    return model, meta


def export_solution(solver, meta):
    selected = [dict(kind=k, rect=rect, axis=axis) for k, rect, axis, v in meta['placements'] if solver.value(v)]
    assignments = [dict(kind=p['kind'], rect=p['rect'], axis=p['axis'], input_side=p['side'])
                   for p in meta['typed'] if solver.value(p['var'])]
    flows = {}
    for name, data in meta['layers'].items():
        flows[name] = {'K': data['K']}
        for key, table in data.items():
            if key == 'K':
                continue
            flows[name][key] = [[c[0], c[1], d, solver.value(v)]
                                for (c, d), v in table.items() if solver.value(v)]
    return dict(placements=selected, assignments=assignments,
                transport=[c for c, v in meta['ts'].items() if solver.value(v)],
                bridges=[c for c, v in meta['bridges'].items() if solver.value(v)],
                warehouse_pattern=next(i for i, v in meta['choices'].items() if solver.value(v)),
                P=solver.value(meta['P']), J=solver.value(meta['J']),
                X=solver.value(meta['X']), Y=solver.value(meta['Y']), flows=flows)


def load_sample():
    p = psutil.Process()
    return dict(utc=datetime.now(timezone.utc).isoformat(), load=os.getloadavg(),
                rss_bytes=p.memory_info().rss, cpu_seconds=sum(p.cpu_times()[:2]),
                available_bytes=psutil.virtual_memory().available)


def run(args):
    assert 1 <= args.workers <= 8
    positions = json.loads((ROOT/'inputs/positions.json').read_text())
    pos = next(p for p in positions if p['rect'][1] == args.y)
    tag = f'y{args.y}_{args.layer}_{args.stage}'
    dest = ROOT/'results'/f'{tag}.json'
    if dest.exists():
        raise RuntimeError(f'Refusing to overwrite {dest}')
    begin = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    samples = [load_sample()]
    stop = threading.Event()
    def monitor():
        with (ROOT/'logs'/f'{tag}.load.jsonl').open('w') as f:
            while not stop.is_set():
                s = load_sample(); samples.append(s)
                f.write(json.dumps(s)+'\n'); f.flush()
                stop.wait(15)
    th = threading.Thread(target=monitor, daemon=True); th.start()
    print(f'{tag}: building, load={os.getloadavg()}', flush=True)
    model, meta = build(pos, args.layer, args.cut_mode)
    if args.hint:
        hint = json.loads(Path(args.hint).read_text())
        byname = hint['values_by_name']
        for i, var in enumerate(model.proto.variables):
            if var.name in byname:
                model.add_hint(model.get_int_var_from_proto_index(i), byname[var.name])
    error = model.validate()
    if error:
        raise RuntimeError(error)
    pb = ROOT/'models'/f'{tag}.pb'
    model.export_to_file(str(pb))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.seconds
    solver.parameters.num_search_workers = args.workers
    solver.parameters.random_seed = args.seed
    solver.parameters.cp_model_probing_level = args.probing
    solver.parameters.symmetry_level = args.symmetry
    solver.parameters.linearization_level = args.linearization
    solver.parameters.log_search_progress = True
    solver.parameters.log_to_stdout = False
    print(model.model_stats(), flush=True)
    print(f'{tag}: solve starts; build={meta["build_seconds"]:.3f}s', flush=True)
    with (ROOT/'logs'/f'{tag}.log').open('w') as log:
        def emit(message):
            log.write(message+'\n'); log.flush()
        solver.log_callback = emit
        t0 = time.monotonic(); status = solver.solve(model); wall = time.monotonic()-t0
    samples.append(load_sample()); stop.set(); th.join()
    res = dict(tag=tag, rect=pos['rect'], layer=args.layer, cut_mode=args.cut_mode,
               started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(),
               args=vars(args), parameters=str(solver.parameters),
               status=solver.status_name(status), solve_seconds=wall,
               solver_wall_seconds=solver.wall_time, build_seconds=meta['build_seconds'],
               total_seconds=time.monotonic()-begin, response_stats=solver.response_stats(),
               model_stats=model.model_stats(), model_sha256=hashlib.sha256(pb.read_bytes()).hexdigest(),
               model_file=str(pb), load_samples=samples,
               environment=dict(python=platform.python_version(), ortools=ortools.__version__,
                                cpu_count=os.cpu_count(), platform=platform.platform()),
               code_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')})
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        res['solution'] = export_solution(solver, meta)
        values = {v.name:solver.value(model.get_int_var_from_proto_index(i))
                  for i, v in enumerate(model.proto.variables) if v.name}
        (ROOT/'results'/f'{tag}.assignment.json').write_text(json.dumps(dict(values_by_name=values)))
    dest.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(json.dumps({k:res[k] for k in ['tag','status','solve_seconds','build_seconds','total_seconds']},ensure_ascii=False),flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--y', type=int, required=True, choices=[6,7,9,17])
    ap.add_argument('--layer', choices=['ore','all'], default='ore')
    ap.add_argument('--stage', required=True)
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--seed', type=int, default=20260922)
    ap.add_argument('--probing', type=int, default=0)
    ap.add_argument('--symmetry', type=int, default=2)
    ap.add_argument('--linearization', type=int, default=2)
    ap.add_argument('--cut-mode', choices=['formal','none'], default='formal')
    ap.add_argument('--hint')
    run(ap.parse_args())


if __name__ == '__main__':
    main()
