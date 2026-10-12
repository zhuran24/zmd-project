#!/usr/bin/env python3
"""Only local static constraints; no factory simulation or full layout search."""
import itertools
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from ortools.sat.python import cp_model


def masks():
    states = []
    for ins in itertools.product((0, 1), repeat=4):
        for outs in itertools.product((0, 1), repeat=4):
            by_formula = any(
                all(ins[d] + outs[d] <= 1 for d in range(4))
                and sum(ins) <= 1 + 2 * m
                and sum(outs) <= 3 - 2 * m
                for m in (0, 1)
            )
            # Real conveyor/splitter/merger templates; positive support may
            # use only a subset of the existing physical ports.
            templates = []
            for p in range(4):
                for q in range(4):
                    if p != q:
                        templates.append(({p}, {q}))
                templates.append(({p}, set(range(4)) - {p}))
                templates.append((set(range(4)) - {p}, {p}))
            by_templates = any(
                all(not ins[d] or d in ii for d in range(4))
                and all(not outs[d] or d in oo for d in range(4))
                for ii, oo in templates
            )
            assert by_formula == by_templates, (ins, outs)
            if by_formula:
                states.append([list(ins), list(outs)])
    return dict(total_masks=256, allowed_masks=len(states),
                formula_equals_real_port_support_templates=True)


def solve(inflow, outflow, tightened, fixed_bridge=None):
    # Direction order E, N, W, S; old kernel, transcribed from
    # flow_model.py:59-65. All-item scale K=20.
    K = 20
    model = cp_model.CpModel()
    bridge = model.new_bool_var('bridge')
    if fixed_bridge is not None:
        model.add(bridge == fixed_bridge)
    model.add(sum(inflow) == sum(outflow))
    model.add(sum(inflow) <= K * (1 + bridge))
    for ax in (0, 1):
        ii = inflow[ax] + inflow[ax + 2]
        oo = outflow[ax] + outflow[ax + 2]
        model.add(ii == oo).only_enforce_if(bridge)
        model.add(ii <= K).only_enforce_if(bridge)
    if tightened:
        yin = [model.new_bool_var(f'yin_{d}') for d in range(4)]
        yout = [model.new_bool_var(f'yout_{d}') for d in range(4)]
        merge = model.new_bool_var('merge')
        for d in range(4):
            model.add(inflow[d] <= K * yin[d])
            model.add(outflow[d] <= K * yout[d])
            model.add(yin[d] + yout[d] <= 1).only_enforce_if(bridge.Not())
        model.add(sum(yin) <= 1 + 2 * merge).only_enforce_if(bridge.Not())
        model.add(sum(yout) <= 3 - 2 * merge).only_enforce_if(bridge.Not())
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 5
    result = solver.solve(model)
    return dict(status=solver.status_name(result),
                bridge=solver.value(bridge) if result in
                (cp_model.OPTIMAL, cp_model.FEASIBLE) else None)


def main():
    cases = {
        'W14_S6_to_E10_N10': ([0, 0, 14, 6], [10, 10, 0, 0], None),
        'W10_S10_to_E10_N10': ([0, 0, 10, 10], [10, 10, 0, 0], None),
        'splitter_W20_to_E20_zero_side_flow': ([0, 0, 20, 0], [20, 0, 0, 0], 0),
        'battery_splitter_W4_to_E4_zero_side_flow': ([0, 0, 4, 0], [4, 0, 0, 0], 0),
    }
    report = dict(scope='isolated local static CP-SAT, not runtime validation',
                  mask_enumeration=masks(), cases={})
    for name, (ii, oo, fixed_bridge) in cases.items():
        report['cases'][name] = dict(
            incoming=ii, outgoing=oo,
            fixed_bridge=fixed_bridge,
            old=solve(ii, oo, False, fixed_bridge),
            new=solve(ii, oo, True, fixed_bridge))
    target = Path(__file__).with_name('local_probe.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
