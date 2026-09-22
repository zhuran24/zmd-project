#!/usr/bin/env python3
"""复跑共享证据并锁定指纹；所有报告只写本复核目录。"""
import contextlib
import hashlib
import importlib
import io
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
SOLVER = OUT.parents[2]
DATA = SOLVER/'数据'
SAMPLES = DATA/'样例'


def main():
    records = []
    for name, args in [
        ('规格自查.log',[SOLVER/'规格/check_revision.py']),
        ('样例检查.log',[SAMPLES/'check_examples.py','--self-test','--report',OUT/'样例检查.json']),
    ]:
        result=subprocess.run([sys.executable,'-B',*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (OUT/name).write_bytes(result.stdout)
        records.append({'check':name,'exit_code':result.returncode})
        assert result.returncode==0,name
    sys.path.insert(0,str(SAMPLES))
    golden=importlib.import_module('check_golden_trace')
    golden.OUTPUT=OUT/'黄金轨迹运行记录.json'
    with contextlib.redirect_stdout(io.StringIO()) as log:
        golden.main()
    (OUT/'黄金轨迹.log').write_text(log.getvalue())
    runtime=importlib.import_module('test_runtime_input')
    original=Path.write_text
    runtime_target=SOLVER/'规格/内核输入修订验证-r3/运行回归结果.json'
    def redirect(path,data,*args,**kwargs):
        assert path==runtime_target,path
        return original(OUT/'运行输入回归结果.json',data,*args,**kwargs)
    try:
        Path.write_text=redirect
        with contextlib.redirect_stdout(io.StringIO()) as log:
            runtime.main()
    finally:
        Path.write_text=original
    (OUT/'运行输入回归.log').write_text(log.getvalue()+'本次输出已重定向到复核目录。\n')
    for name in ['黄金轨迹运行记录.json','运行输入回归结果.json']:
        assert (OUT/name).read_bytes()==(DATA/'修订验证/r4'/name).read_bytes(),name
        records.append({'check':name,'byte_equal_to_r4':True})
    snapshot=json.loads((OUT/'复核开工指纹.json').read_text())
    changed=[p for p,h in snapshot.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    assert not changed,changed
    (OUT/'收尾核对.json').write_text(json.dumps({'status':'通过','checks':records,'protected_count':len(snapshot),'changed':changed},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'通过','checks':records,'protected_count':len(snapshot)},ensure_ascii=False))


if __name__=='__main__':
    main()
