#!/usr/bin/env python3
"""复跑冻结输入的接法证书、CP-SAT与静态程序；输出限定在构造A。"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
CODE=Path(__file__).resolve().parent


def main():
    if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:6])
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    start=time.monotonic();results=[]
    # 不重取外部材料；复跑仅使用本目录内的冻结文件。
    for file,expected in [('check_topology.py',0),('cp_sat_presolve.py',0),('check_components.py',0),('static_check.py',1),('draw_obstruction.py',0)]:
        r=subprocess.run([sys.executable,'-B',str(CODE/file)],cwd=BASE,env=env,capture_output=True,text=True,timeout=60)
        results.append(dict(program=file,exit_code=r.returncode,expected_exit_code=expected,pass_run=r.returncode==expected,
                            stdout=r.stdout,stderr=r.stderr))
    inputs=json.loads((BASE/'证据/输入指纹.json').read_text())
    snapshot_valid=all(hashlib.sha256((BASE/i['copy']).read_bytes()).hexdigest()==i['sha256'] for i in inputs)
    result=dict(all_expected=all(r['pass_run'] for r in results) and snapshot_valid,
                snapshot_hashes_valid=snapshot_valid,elapsed_seconds=time.monotonic()-start,
                cpu_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
                results=results,
                scope='预期的静态检查退出码为1：无布局且拓扑条件失败；不是布局检查通过。')
    (BASE/'证据/复跑结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(all_expected=result['all_expected'],snapshot_hashes_valid=snapshot_valid,elapsed_seconds=result['elapsed_seconds']),ensure_ascii=False))
    return 0 if result['all_expected'] else 1


if __name__=='__main__':raise SystemExit(main())
