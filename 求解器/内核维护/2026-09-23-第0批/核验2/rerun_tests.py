import json,os,re,sys
from audit_guard import *
R=module('reviewed_runner',REPO/'数据/工具/kernel_regression.py')
a=json.loads((IMPL/'isolation-accepted.json').read_text());S=Path(a['source_root'])
def binding():return R.check_isolation(IMPL/'isolation-accepted.json',S,a['profile'])
binding();save('isolation-binding.json',dict(passed=True,source=str(S),profile=a['profile'],receipt_sha256=sha(IMPL/'isolation-accepted.json')))
profile='healthaudit2safe'+str(os.getpid())
args=['--locked','--offline','-j','2','--profile',profile,'--config',f'profile.{profile}.inherits="dev"','--config',f'profile.{profile}.codegen-units=1']
steps=[('build',['build','--workspace']),('check',['check','--workspace','--all-targets']),('clippy',['clippy','--workspace','--all-targets','--message-format=json']),('kernel-lib',['test','-p','kernel','--lib']),('topology-lib',['test','-p','topology','--lib']),('reference',['test','-p','kernel','--test','reference']),('validation',['test','-p','topology','--test','validation']),('kernel-doc',['test','-p','kernel','--doc']),('topology-doc',['test','-p','topology','--doc'])]
results=[]
for round_ in [1,2]:
    for name,step in steps:
        binding();label=f'safe-{round_}-{name}';argv=['cargo',*step,*args]
        if step[0]=='test':argv+=['--','--test-threads=1']
        row=command(label,argv,S);binding()
        stdout=(OUT/(label+'.stdout.log')).read_text()
        if name=='clippy':
            warnings=[json.loads(x) for x in stdout.splitlines() if x.startswith('{') and json.loads(x).get('reason')=='compiler-message' and json.loads(x)['message']['level']=='warning']
            row['warnings']=len(warnings);assert not warnings
        row['test_results']=re.findall(r'test result: (\w+)\. (\d+) passed; (\d+) failed;',stdout)
        results.append(row);save('safe-results.json',results)
save('safe-passed.json',dict(passed=True,rounds=2,commands=len(results),profile=profile))
(OUT/'cargo-test-evidence').mkdir(exist_ok=True)
results=[]
for i,h in enumerate(a['harnesses']):
    binding();row=command(f'list-{i}',[h['executable'],'--list'],S)
    listing=(OUT/f'list-{i}.stdout.log').read_text();count=re.search(r'(\d+) tests?, (\d+) benchmarks?',listing);assert count and int(count[1])==h['listed_tests']
for round_ in [1,2]:
    for i,h in enumerate(a['harnesses']):
        binding();label=f'suite-{round_}-{i}-{h["target"]["name"]}'
        row=command(label,[h['executable'],'--test-threads=1','--nocapture'],S if round_==1 else S.parent,env={'HEALTH_RUN':str(OUT),'KERNEL_TEST_EVIDENCE_DIR':str(OUT/'cargo-test-evidence')})
        binding();stdout=(OUT/(label+'.stdout.log')).read_text();m=re.search(r'test result: ok\. (\d+) passed; (\d+) failed;',stdout)
        assert m and int(m[1])==h['listed_tests'] and int(m[2])==0
        row.update(round=round_,target=h['target'],passed_tests=int(m[1]));results.append(row);save('suite-results.json',results)
save('suite-passed.json',dict(passed=True,rounds=2,per_round=[sum(x['passed_tests'] for x in results if x['round']==r) for r in [1,2]],harnesses=len(a['harnesses'])))
