from probe_common import *
import shutil
for name,args in [('rustc',['rustc','-Vv']),('cargo',['cargo','-V']),('git-head',['git','rev-parse','HEAD']),('git-history',['git','show','--stat','7da52a7','a7539f5','220f7b6'])]:run(name,args)
args=['cargo','build','--locked','--offline','--workspace','--bins','--profile','r2audit','--config','profile.r2audit.inherits="dev"','--config','profile.r2audit.codegen-units=1','--config','profile.r2audit.debug=0','-j','1']
r=run('build-baseline',args,timeout=300)
assert r.returncode==0,r.stderr.decode()
BINS=TARGET/'r2-source-timing-20260922';BINS.mkdir(exist_ok=True)
for name in ['kernel','topology']:shutil.copy2(TARGET/'r2audit'/name,BINS/(name+'-baseline'))
dump(OUT/'baseline.json',{'build_argv':args,'profile':'r2audit','binaries':{name:{'path':str(BINS/(name+'-baseline')),'sha256':sha(BINS/(name+'-baseline'))} for name in ['kernel','topology']},'env':{k:ENV[k] for k in ['CARGO_TARGET_DIR','CARGO_BUILD_JOBS','RAYON_NUM_THREADS','OMP_NUM_THREADS','UV_THREADPOOL_SIZE','NODE_OPTIONS']},'cpu_affinity':CPUS,'inputs':{str(p):sha(p) for p in [ROOT/'数据/样例/生产循环环带.json',ROOT/'数据/样例/混做粉碎机两下游.json',ROOT/'数据/样例/分流器三路轮询.json',ROOT/'规格/内核配置-v1.json',ROOT/'数据/候选B/contract.json']}})
print('build successful; baseline binaries saved in shared target')
