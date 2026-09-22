#!/usr/bin/env python3
"""复现内核输入第三轮交付检查，全部输出限定在求解器内。"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
EXAMPLES=ROOT/'求解器/数据/样例'

def main():
    commands=[
      ('生成样例',[sys.executable,'-B',str(EXAMPLES/'generate_examples.py')]),
      ('样例检查',[sys.executable,'-B',str(EXAMPLES/'check_examples.py'),'--self-test','--report',str(EXAMPLES/'检查结果.json')]),
      ('黄金重算',[sys.executable,'-B',str(EXAMPLES/'check_golden_trace.py')]),
      ('运行回归',[sys.executable,'-B',str(EXAMPLES/'test_runtime_input.py')]),
      ('正式目录回源',[sys.executable,'-B',str(ROOT/'求解器/数据/工具/formal_catalog.py')]),
    ]
    results=[]
    for name,cmd in commands:
        p=subprocess.run(cmd,cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},text=True,capture_output=True)
        log=BASE/(name+'.log');log.write_text(p.stdout+p.stderr)
        results.append({'name':name,'command':cmd,'exit_code':p.returncode,'log':str(log)})
        if p.returncode:break
    protected=json.loads((BASE/'只读指纹.json').read_text())
    changed=[p for p,h in protected.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    old_sim={p for p in protected if str(ROOT/'模拟器')+'/' in p}
    current_sim={str(p) for p in (ROOT/'模拟器').rglob('*') if p.is_file()}
    links=[]
    docs=[ROOT/'求解器/规格/内核输入.md',ROOT/'求解器/规格/内核输出.md',EXAMPLES/'混做粉碎机两下游-黄金轨迹.md',BASE/'自查报告.md']
    for p in docs:
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' not in link and not (p.parent/link.split('#')[0]).exists():links.append({'file':str(p),'link':link})
    result={'status':'通过' if len(results)==len(commands) and all(r['exit_code']==0 for r in results) and not changed and old_sim==current_sim and not links else '失败','commands':results,'protected_file_count':len(protected),'protected_changes':changed,'simulator_file_set_unchanged':old_sim==current_sim,'broken_links':links,'shared_tables':'A线拥有写权，本席仅提交修改请求；不把并行文件变化列为本席违规','scope':'有限输入与轨迹检查，不是全部运行族/目标认证'}
    (BASE/'自查结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('commands',)},ensure_ascii=False))
    return 0 if result['status']=='通过' else 1

if __name__=='__main__':raise SystemExit(main())
