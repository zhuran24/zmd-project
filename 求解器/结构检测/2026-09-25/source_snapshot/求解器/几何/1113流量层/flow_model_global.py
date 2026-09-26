#!/usr/bin/env python3
"""Same integer feasible set, with explicit redundant global flow bounds.

These rows are implied after fixing the layout. They expose aggregate demand
to the LP relaxation without summing a shared port once per candidate body.
"""
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
import flow_model as base

original_build=base.build
original_run=base.run


def build(position,layer='ore',cut_mode='formal'):
    model,meta=original_build(position,layer,cut_mode)
    if layer=='all':
        f=meta['layers']['all'];K=f['K']
        # 304.5 items/tick consumed by machines, 253.65 produced by them.
        # Fixed selected bodies have unique ownership of each used port.
        model.add(sum(f['machine_in'].values())>=6090)
        model.add(sum(f['machine_out'].values())>=5073)
        model.add(sum(f['core_sink'].values())>=23)
        # Every transport entry is either a nontransport source or a grid edge.
        model.add(sum(f['edgeflow'].values())+6113 <=
                  K*(sum(meta['ts'].values())+sum(meta['bridges'].values())))
    return model,meta


def run(args):
    res=original_run(args)
    res['variant']='explicit_global_totals'
    res['variant_file']='flow_model_global.py'
    p=base.ROOT/'results'/f'{res["tag"]}.json'
    p.write_text(json.dumps(res,ensure_ascii=False,indent=2))
    return res


base.build=build
base.run=run
if __name__=='__main__':base.main()
