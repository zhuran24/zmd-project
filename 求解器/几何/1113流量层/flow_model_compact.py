#!/usr/bin/env python3
"""Compact K=1 ore network: recover type and input direction after solving.

Projection-equivalent to the typed ore-only model on geometry/transport/flow:
52 unit sources and per-small-machine capacity one yield 52 active receivers.
Assign 18 to crush, 34 to refine, then label 50/17 inactive receivers plus 12
other small machines. No actual-flow integrality or dedicated-machine premise.
"""
from collections import defaultdict
import json
import sys
import time
sys.dont_write_bytecode=True
import flow_model as base
from filter_positions import PATTERNS,port_sides
from geometry import build as build_geometry

original_run=base.run
original_export=base.export_solution


def build(position,layer='ore',cut_mode='formal'):
    if layer!='ore':raise ValueError('compact version is ore-only')
    start=time.monotonic()
    pos=dict(position,allowed_P=[10,11,12],patterns=list(range(47)))
    model,meta=build_geometry(pos,False,cut_mode);ts=meta['ts']
    bridges={c:model.new_bool_var(f'bridge_{c[0]}_{c[1]}') for c in ts}
    for c in ts:model.add(bridges[c]<=ts[c])
    model.add(sum(ts.values())+sum(bridges.values())>=306)
    sink_support=defaultdict(list);core_support=defaultdict(list);warehouse=defaultdict(list)
    machines=[]
    for kind,rect,axis,v in meta['placements']:
        if kind=='small':
            edges=base.ports(rect,axis,ts);ps=[e for edge in edges for e in edge]
            machines.append((v,ps))
            for e in ps:sink_support[e].append(v)
        elif kind=='core':
            for edge in base.ports(rect,axis,ts,True):
                for e in edge:core_support[e].append(v)
    for i,v in meta['choices'].items():
        for j,c in enumerate(PATTERNS[i]['ports']):warehouse[tuple(c),2 if j<23 else 3].append(v)
    incoming={c:[[] for _ in range(4)] for c in ts};outgoing={c:[[] for _ in range(4)] for c in ts}
    edgeflow={};machine_in={};core_src={};wh={}
    for c in ts:
        for d,(dx,dy) in enumerate(base.DIRS):
            n=c[0]+dx,c[1]+dy
            if n not in ts:continue
            f=model.new_bool_var(f'ore_edge_{c[0]}_{c[1]}_{d}')
            model.add(f<=ts[c]);model.add(f<=ts[n]);edgeflow[c,d]=f
            outgoing[c][d].append(f);incoming[n][base.OPP[d]].append(f)
    for support,target,prefix,source in [(sink_support,machine_in,'mi',False),
            (core_support,core_src,'co',True),(warehouse,wh,'wh',True)]:
        for (c,d),vs in support.items():
            f=model.new_bool_var(f'ore_{prefix}_{c[0]}_{c[1]}_{d}')
            if source:model.add(f==sum(vs))
            else:model.add(f<=sum(vs))
            model.add(f<=ts[c]);target[c,d]=f
            (incoming if source else outgoing)[c][d].append(f)
    for v,ps in machines:model.add(sum(machine_in[e] for e in ps)<=1).only_enforce_if(v)
    for c in ts:base.add_cell_conservation(model,incoming[c],outgoing[c],ts[c],bridges[c],1)
    # Redundant by conservation; useful as explicit total demand.
    model.add(sum(machine_in.values())==52)
    meta.update(bridges=bridges,typed=[],cores=[],layers={'ore':dict(K=1,edgeflow=edgeflow,
        machine_in=machine_in,machine_out={},core_src=core_src,core_sink={},warehouse=wh)},
        build_seconds=time.monotonic()-start)
    return model,meta


def export(solver,meta):
    solution=original_export(solver,meta)
    flow=meta['layers']['ore']['machine_in'];active=[];inactive=[]
    for kind,rect,axis,v in meta['placements']:
        if kind!='small' or not solver.value(v):continue
        edges=base.ports(rect,axis,meta['ts'])
        amounts=[sum(solver.value(flow[e]) for e in edge) for edge in edges]
        assert sum(amounts) in (0,1),(rect,amounts)
        obj=dict(rect=rect,axis=axis,input_side=amounts.index(1) if sum(amounts) else 0)
        (active if sum(amounts) else inactive).append(obj)
    assert len(active)==52 and len(inactive)==79,(len(active),len(inactive))
    ass=[]
    for i,p in enumerate(active):ass.append(dict(p,kind='crush' if i<18 else 'refine'))
    for i,p in enumerate(inactive[:67]):ass.append(dict(p,kind='crush' if i<50 else 'refine'))
    solution['assignments']=ass
    solution['recovered_labels']=dict(active_crush=18,active_refine=34,inactive_crush=50,
        inactive_refine=17,other_small=12,note='Labels belong to an integral substitute flow, not actual operating roles.')
    return solution


def run(args):
    res=original_run(args);res['variant']='compact_ore_with_recovered_labels'
    res['variant_file']='flow_model_compact.py'
    (base.ROOT/'results'/f'{res["tag"]}.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
    return res


base.build=build;base.export_solution=export;base.run=run
if __name__=='__main__':base.main()
