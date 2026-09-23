#!/usr/bin/env python3
"""The six signed control cases executed before the main solver campaign.
Run separately, so its one CP-SAT worker does not overlap an eight-worker job.
"""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
from ortools.sat.python import cp_model
from flow_model import add_cell_conservation

CASES=[
 ('normal_turn',0,[1,0,0,0],[0,1,0,0],'OPTIMAL'),
 ('bridge_turn_forbidden',1,[1,0,0,0],[0,1,0,0],'INFEASIBLE'),
 ('bridge_cross',1,[1,1,0,0],[0,0,1,1],'OPTIMAL'),
 ('normal_cross_overload',0,[1,1,0,0],[0,0,1,1],'INFEASIBLE'),
 ('bridge_axis_overload',1,[1,0,1,0],[1,0,1,0],'INFEASIBLE'),
 ('unbalanced',0,[1,0,0,0],[0,0,0,0],'INFEASIBLE')]

def main():
    results=[]
    for name,bridge,ins,outs,expected in CASES:
        model=cp_model.CpModel();t=model.new_bool_var('t');b=model.new_bool_var('b')
        model.add(t==1);model.add(b==bridge)
        add_cell_conservation(model,[[i] for i in ins],[[o] for o in outs],t,b,1)
        solver=cp_model.CpSolver();solver.parameters.num_search_workers=1
        status=solver.status_name(solver.solve(model))
        assert status==expected,(name,status,expected)
        results.append(dict(test=name,status=status,expected=expected))
    target=Path(__file__).resolve().parent/'unit_checks.json'
    target.write_text(json.dumps(results,indent=2));print(json.dumps(results))

if __name__=='__main__':main()
