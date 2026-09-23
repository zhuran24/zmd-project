#!/usr/bin/env python3
"""Change search guidance only: minimize all-layer grid flow, stop at first solution.

No route-length threshold or additional constraint is introduced. INFEASIBLE
still refers to exactly the same feasible set as the global-total variant.
"""
import json
import sys
sys.dont_write_bytecode=True
import flow_model_global
import flow_model as base

original_build=base.build
original_run=base.run
OriginalSolver=base.cp_model.CpSolver


class FirstSolutionSolver(OriginalSolver):
    def __init__(self):
        super().__init__()
        self.parameters.stop_after_first_solution=True


def build(position,layer='all',cut_mode='formal'):
    if layer!='all':raise ValueError('minimum-edge search is for the all-item model')
    model,meta=original_build(position,layer,cut_mode)
    model.minimize(sum(meta['layers']['all']['edgeflow'].values()))
    return model,meta


def run(args):
    res=original_run(args)
    res['variant']='global_min_edges_first_solution'
    res['variant_file']='flow_model_min_edges.py'
    res['search_objective']='Minimize all-item transport-to-transport arc flow in units of 1/20; stop at first feasible solution. Feasible set unchanged.'
    (base.ROOT/'results'/f'{res["tag"]}.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
    return res


base.build=build;base.run=run;base.cp_model.CpSolver=FirstSolutionSolver
if __name__=='__main__':base.main()
