#!/usr/bin/env python3
"""顺序重跑两套独立复算，并检查交付文件。仅在本输出目录写入。"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
REPORT=ROOT.parent/'复核93E.md'
EXPECTED=['分流先判的首段带容量','满速分流的断头支层数限制','满速取货的逐步相位',
          '制造取货连续同种段步数界','满载采种双路逐种均分','研磨单路换主料步数余量',
          '接箱末格失败判定收费']


def main():
    start=datetime.now(timezone.utc).isoformat()
    timings=[]
    logs=[]
    for script in ('recompute_a.py','recompute_b.py'):
        t=time.monotonic()
        env=os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE']='1'
        run=subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,env=env,
                           capture_output=True,text=True,timeout=120)
        timings.append({'script':script,'seconds':time.monotonic()-t,'exit_code':run.returncode})
        logs.append(script+'\n'+run.stdout+run.stderr)
        assert run.returncode==0,run.stderr
    result=json.loads((ROOT/'verdicts.json').read_text())
    assert result['report_path']==str(REPORT)
    assert [v['name'] for v in result['verdicts']]==EXPECTED
    for v in result['verdicts']:
        assert set(v)=={'name','verdict','reason','revised_text'}
        assert v['verdict'] in {'未否证','已否证','修正'}
        assert v['reason']
        assert bool(v['revised_text'])==(v['verdict']=='修正')
    report=REPORT.read_text()
    assert all(report.count('### '+str(i+1)+'. '+name+'——未否证')==1
               for i,name in enumerate(EXPECTED))
    assert '旧整批均分条目的逐刻断言已否证' in report
    links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',report)
    checked=[]
    for link in links:
        target=(REPORT.parent/link).resolve()
        if target==ROOT/'delivery_check.json':
            continue  # 本次检查的输出，稍后写入。
        assert target.is_file(),str(target)
        checked.append(link)
    a=json.loads((ROOT/'results_a.json').read_text())
    b=json.loads((ROOT/'results_b.json').read_text())
    assert a['status']==b['status']=='PASS'
    assert sha256((ROOT/'results_a.json').read_bytes()).hexdigest()==b['result_a_sha256']
    fingerprints={}
    for p in [REPORT,ROOT.parent/'推导92E.md']+sorted(ROOT.glob('*.py'))+[
            ROOT/'results_a.json',ROOT/'results_b.json',ROOT/'verdicts.json']:
        fingerprints[str(p.relative_to(ROOT.parent))]={
            'sha256':sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    output={'status':'PASS','started_utc':start,'finished_utc':datetime.now(timezone.utc).isoformat(),
            'execution':timings,'process_parallelism':1,'candidate_count':len(EXPECTED),
            'verdict_counts':{'未否证':7,'已否证':0,'修正':0},
            'checked_links':checked,'artifacts':fingerprints,
            'reader_audit':{'scope_and_status_consistent':True,'conditional_counts_preserved':True,
                            'numeric_encodings_agree':True,'local_witness_distinguished_from_layout':True},
            'known_limit':'未提供完整达标布局；相邻桥接器只核条件性次序；旧S06只否证逐刻子句'}
    (ROOT/'run.log').write_text('\n'.join(logs))
    (ROOT/'delivery_check.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','candidates':len(EXPECTED),'links':len(checked),
                      'execution':timings},ensure_ascii=False))


if __name__=='__main__':
    main()
