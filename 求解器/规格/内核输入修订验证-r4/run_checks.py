#!/usr/bin/env python3
"""第四轮验证入口；命令、日志、构建缓存均限求解器内。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
SOLVER = ROOT/'求解器'
EXAMPLES = SOLVER/'数据/样例'
SHARED = [SOLVER/'规格'/name for name in ('选择点参数轴.md','选择点清单.md','规则覆盖表.md','运行语义.md','受限模型声明.md','受限转移定义.md','内核配置-v1.json')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    shared_start = {str(p):digest(p) for p in SHARED}
    commands = [
        ('输出schema生成',[sys.executable,'-B',str(BASE.parent/'内核输入修订验证-r3/build_output_schema.py')]),
        ('生成样例',[sys.executable,'-B',str(EXAMPLES/'generate_examples.py')]),
        ('黄金重算',[sys.executable,'-B',str(EXAMPLES/'check_golden_trace.py')]),
        ('运行回归',[sys.executable,'-B',str(EXAMPLES/'test_runtime_input.py')]),
        ('修订回归',[sys.executable,'-B',str(BASE/'test_revision.py')]),
        ('样例检查',[sys.executable,'-B',str(EXAMPLES/'check_examples.py'),'--self-test','--report',str(EXAMPLES/'检查结果.json')]),
        ('正式目录回源',[sys.executable,'-B',str(SOLVER/'数据/工具/formal_catalog.py')]),
        ('规则覆盖自查',[sys.executable,'-B',str(BASE/'check_current_coverage.py')]),
        ('规格线自查',[sys.executable,'-B',str(SOLVER/'规格/check_revision.py')]),
        ('cargo-test',['cargo','test','--offline','--locked','--manifest-path',str(SOLVER/'Cargo.toml')]),
        ('候选B校验',['cargo','run','--offline','--locked','--manifest-path',str(SOLVER/'Cargo.toml'),'-p','topology','--',str(SOLVER/'数据/候选B/contract.json')]),
    ]
    env = {**os.environ,'PYTHONDONTWRITEBYTECODE':'1','CARGO_HOME':str(SOLVER/'.cargo-home'),'CARGO_TARGET_DIR':str(SOLVER/'target')}
    results = []
    for name, command in commands:
        process = subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True)
        log = BASE/(name+'.log'); log.write_text(process.stdout+process.stderr)
        if name == '候选B校验': (BASE/'候选B校验报告.md').write_text(process.stdout)
        results.append({'name':name,'command':command,'exit_code':process.returncode,'log':str(log)})
        print(json.dumps({'name':name,'exit_code':process.returncode},ensure_ascii=False),flush=True)
    if results[-1]['exit_code'] == 0:
        report = (BASE/'候选B校验报告.md').read_text()
        assert '能检且不通过（0 项' in report
        for row in json.loads((SOLVER/'数据/正式静态目录.json').read_text())['constraints']:
            assert '正式条目/'+row['name'] in report
    before = json.loads((BASE/'只读指纹.json').read_text())
    # 共享三表由规格线并行维护；不将其正常迁移冒称本席保护失败或本席修改。
    shared_names = {str(p) for p in SHARED}
    protected = {p:h for p,h in before.items() if p not in shared_names}
    changes = [p for p,h in protected.items() if not Path(p).is_file() or digest(Path(p)) != h]
    sim_before = {p for p in protected if p.startswith(str(ROOT/'模拟器')+'/')}
    sim_after = {str(p) for p in (ROOT/'模拟器').rglob('*') if p.is_file()}
    drift = [p for p,h in shared_start.items() if digest(Path(p)) != h]
    parallel = [p for p,h in before.items() if p in shared_names and digest(Path(p)) != h]
    success = all(r['exit_code']==0 for r in results) and not changes and sim_before==sim_after and not drift
    result = {'status':'通过' if success else '未全通过','commands':results,
              'protected_file_count':len(protected),'protected_changes':changes,
              'simulator_file_set_unchanged':sim_before==sim_after,
              'shared_start_sha256':shared_start,'shared_drift_during_checks':drift,
              'parallel_shared_changes_since_start':parallel,
              'scope':'规则逐行与输入/有限轨迹核验；不是全称语义、完整循环或达标认证。新§7请求并入状态另列。'}
    (BASE/'自查结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
