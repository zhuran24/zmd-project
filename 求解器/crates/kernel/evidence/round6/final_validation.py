"""第六轮收尾顺序：构建、从源重生成、独立核验、性能与只读批量闸。"""
from pathlib import Path
import json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[4];E=Path(__file__).resolve().parent
ENV=dict(os.environ,CARGO_HOME=str(ROOT/'.cargo-home'),CARGO_TARGET_DIR=str(ROOT/'target'),PYTHONDONTWRITEBYTECODE='1')
steps=[]
def run(name,args):
 start=time.monotonic()
 with (E/(name+'.log')).open('w') as log:p=subprocess.run(list(map(str,args)),cwd=ROOT,env=ENV,stdout=log,stderr=subprocess.STDOUT)
 row=dict(name=name,command=list(map(str,args)),exit_code=p.returncode,seconds=time.monotonic()-start,log=str(E/(name+'.log')));steps.append(row)
 (E/'validation-commands.json').write_text(json.dumps(steps,ensure_ascii=False,indent=2)+'\n')
 print(name,p.returncode,flush=True);assert p.returncode==0,row
run('clippy',['cargo','clippy','--locked','--offline','--all-targets','--','-D','warnings'])
run('build',['cargo','build','--release','--locked','--offline','-p','kernel'])
run('migration-final',[sys.executable,'-B',ROOT/'crates/kernel/tests/refresh_round6.py','--certificates','--records'])
run('K6',[sys.executable,'-B',ROOT/'crates/kernel/tests/production_attempt_round6.py'])
run('benchmark-final',[sys.executable,'-B',ROOT/'crates/kernel/tests/benchmark_round6.py','final'])
run('cli',[sys.executable,'-B',ROOT/'crates/kernel/tests/round6_cli.py'])
run('verify-readonly',[sys.executable,'-B',E/'verify_readonly.py'])
for name,ticks in [('桥接器双通路',120),('研磨混做核验',120),('生产循环环带',50)]:
 dest=E/(name+'-cycle.json')
 run(name+'-cycle',[ROOT/'target/release/kernel','cycle',ROOT/'数据/样例'/(name+'.json'),'--config',ROOT/'规格/内核配置-v1.json','--max-ticks',ticks,'--no-record','--out',dest])
 run(name+'-verify',[ROOT/'target/release/kernel','verify-cycle',dest,'--config',ROOT/'规格/内核配置-v1.json'])
run('reduction-after',[sys.executable,'-B',ROOT/'规格/复核/约减/count_classes.py','--check'])
