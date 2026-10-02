#!/usr/bin/env python3
"""逐格整数模型的必要拓扑子问题：穷尽循环次序，要求欧拉面数。

这不是打包启发式，也不把UNKNOWN当作不可行。所有合法逐格布局必然
给出本模型的一个解；本模型INFEASIBLE并由check_topology.py独立证书核验。
完整摆放/布线整数约束见../整数模型.md；本例在展开坐标变量前即被否掉。
"""
import hashlib
import json
import os
import time
from pathlib import Path

os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
if hasattr(os,'sched_setaffinity'):
    available=sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0,available[:6])
from ortools.sat.python import cp_model
import ortools

BASE=Path(__file__).resolve().parents[1]


def solve(require_planar, output):
    raw=(BASE/'证据/全部64种旋转系统.json').read_bytes()
    data=json.loads(raw)
    model=cp_model.CpModel()
    rotations=[model.new_bool_var(f'rotation_at_{i}') for i in range(6)]
    faces=model.new_int_var(1,9,'face_count')
    table=[r['rotations']+[r['face_count']] for r in data['rows']]
    model.add_allowed_assignments(rotations+[faces],table)
    if require_planar:
        # V-E+F=2，对任意球面/平面上的连通嵌入必要。
        model.add(6-9+faces==2)
    else:
        model.maximize(faces)
    path=BASE/f'证据/{output}.pbtxt'
    model.export_to_file(str(path))
    solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=6
    solver.parameters.max_time_in_seconds=60
    solver.parameters.random_seed=98100
    solver.parameters.log_search_progress=True
    solver.parameters.log_to_stdout=False
    logs=[]
    solver.log_callback=logs.append
    started=time.monotonic()
    status=solver.solve(model)
    elapsed=time.monotonic()-started
    result=dict(model='固定S2逐格整数模型的平面性必要子问题',require_planar=require_planar,
                status=solver.status_name(status),workers=6,wall_seconds=elapsed,
                max_seconds=60,ortools_version=ortools.__version__,
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                rotation_table_sha256=hashlib.sha256(raw).hexdigest(),
                response_stats=solver.response_stats(),
                exhaustive_rotation_rows=len(table),required_planar_faces=5,
                permitted_face_counts=sorted({r[-1] for r in table}),
                grid_model_expanded=False,
                reason='必要子问题已不可行，未生成坐标或路格变量；不是70×70全模型已运行的声称。')
    if status in [cp_model.OPTIMAL,cp_model.FEASIBLE]:
        result['solution']=dict(rotations=[solver.value(v) for v in rotations],faces=solver.value(faces))
    (BASE/f'证据/{output}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (BASE/f'证据/{output}.log').write_text('\n'.join(logs)+'\n')
    return result


def main():
    negative=solve(True,'CP-SAT-不要求空矩形')
    control=solve(False,'CP-SAT-撤去平面条件对照')
    assert negative['status']=='INFEASIBLE'
    assert control['status']=='OPTIMAL' and control['solution']['faces']==3
    print(json.dumps(dict(no_rectangle=negative['status'],relaxed_control=control['status'],
                         largest_face_count=control['solution']['faces'],
                         required_planar_face_count=5),ensure_ascii=False))


if __name__=='__main__':main()
