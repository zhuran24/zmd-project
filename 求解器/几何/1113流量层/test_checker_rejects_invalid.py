#!/usr/bin/env python3
"""Whole-checker negative control; deliberately not a factory candidate.

One machine, no poles, and zero source flow must be rejected. This exercises
both flow-layer readers and statistics without claiming a positive layout.
"""
from pathlib import Path
import json
import check_solution as checker


def fixture():
    _,warehouse=checker.pattern(0)
    core=(10,10,9,9);machine=(2,2,3,3)
    transport={pt for pt,d in warehouse}
    for side in (0,1):
        transport.update(pt for pt,d in checker.face(core,0,side,[1,4,7]))
        transport.update(pt for pt,d in checker.face(core,1,side,range(1,8)))
        transport.update(pt for pt,d in checker.face(machine,1,side))
    flows={}
    for name,K in [('ore',1),('all',20)]:
        flows[name]=dict(K=K,edgeflow=[],machine_in=[],machine_out=[],core_src=[],core_sink=[],warehouse=[])
    return dict(rect=[49,6,21,53],layer='all',cut_mode='none',solution=dict(
        placements=[dict(kind='core',rect=core,axis=0),dict(kind='small',rect=machine,axis=1)],
        assignments=[dict(kind='crush',rect=machine,axis=1,input_side=0)],
        transport=sorted(transport),bridges=[],warehouse_pattern=0,P=0,J=0,X=0,Y=0,flows=flows))


if __name__=='__main__':
    result=checker.check(fixture())
    assert not result['ok'] and result['errors']
    assert 'ore warehouse equalities' in result['errors'] and 'all warehouse equalities' in result['errors']
    assert all(len(s['source_cell_examples'])==12 for s in result['flow_statistics'].values())
    assert all(tuple(s['source_cell_examples'][0]['cell'])==(1,2) for s in result['flow_statistics'].values())
    out=dict(test='deliberately invalid whole-checker input',expected_ok=False,actual_ok=result['ok'],
             errors_count=len(result['errors']),errors=result['errors'],source_probes_per_layer=12,
             no_solver_called=True,not_a_candidate=True)
    (Path(__file__).resolve().parent/'checker_negative_control.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps(out,ensure_ascii=False,indent=2))
