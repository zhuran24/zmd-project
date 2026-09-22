"""原样运行cargo；仅将硬编码的测试输出目录挂载到复核目录。"""
from pathlib import Path
import os,sys,subprocess,json
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent
mode=sys.argv[1]if len(sys.argv)>1 else 'test'
for name in ['cli-r2','cli-r5','tmp']:(OUT/name).mkdir(exist_ok=True)
command=['bwrap','--ro-bind','/','/','--proc','/proc','--dev','/dev','--bind',str(ROOT/'target'),str(ROOT/'target'),'--bind',str(OUT),str(OUT)]
for src,dst in [('cli-r2','revision-r2'),('cli-r5','round5')]:command+=['--bind',str(OUT/src),str(ROOT/'crates/kernel/evidence'/dst)]
command+=['--chdir',str(ROOT)]
for key,value in {'CARGO_HOME':str(ROOT/'.cargo-home'),'CARGO_TARGET_DIR':str(ROOT/'target'),'TMPDIR':str(OUT/'tmp'),'PYTHONDONTWRITEBYTECODE':'1'}.items():command+=['--setenv',key,value]
command+=['cargo','test','--locked','--offline']if mode=='test'else['cargo','clippy','--locked','--offline','--all-targets','--','-D','warnings']
with (OUT/('cargo-test.log'if mode=='test'else'clippy-recheck.log')).open('w') as log:p=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
(OUT/(mode+'-command.json')).write_text(json.dumps({'command':command,'exit_code':p.returncode,'redirected_outputs_only':True},ensure_ascii=False,indent=2)+'\n')
sys.exit(p.returncode)
