import datetime,hashlib,json,re,subprocess
from pathlib import Path
v=Path(__file__).resolve().parent;r=v.parents[3]
def load(n):return json.loads((v/n).read_text())
def save(n,x):(v/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
before=load('before.json');after=load('after.json')
scope=load('status-scope.json');sync={x['path'] for x in scope if x['in_sync_scope']}
commits=subprocess.check_output(['git','-c','core.quotepath=false','log','--format=%H %s','--name-status',before['head']+'..'+after['head']],cwd=r).decode()
changed=subprocess.check_output(['git','diff','--name-only','-z',before['head'],after['head']],cwd=r).decode().split('\0')
changed=[x for x in changed if x]
sources=['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']
assert not set(changed)&(sync|set(sources))
current_status=[x for x in after['status'] if not x[3:].startswith('求解器/内核维护/2026-09-22h/')]
outside=[x for x in current_status if x[3:] not in sync]
business_drift=[name for name in sync if before['work'].get(name)!=after['work'].get(name)]
save('concurrent-head-result.json',{'before_head':before['head'],'after_head':after['head'],'commits':commits,'changed_paths':changed,'intersection_with_sync':sorted(set(changed)&sync),'business_drift_during_verification':business_drift,'final_outside_scope':outside})
assert not business_drift
testcounts={}
for n in ['kernel-lib','topology-lib','kernel-reference','topology-validation','kernel-doc','topology-doc']:
    logname='topology-validation-final' if n=='topology-validation' else n
    text=(v/'logs'/f'{logname}.log').read_text()
    result=re.search(r'test result: ok\. (\d+) passed; (\d+) failed',text)
    assert result,n
    testcounts[n]=int(result[1]);assert result[2]=='0'
python=(v/'logs/catalog-regressions-final.log').read_text();assert re.search(r'Ran 8 tests.*\n\nOK',python,re.S)
cases=load('case-results.json');assert all(x['pass'] for x in cases)
counts={h:len(files) for h,files in after['history'].items()}
assert before['history']==after['history'] and not after['history_vs_head']
assert all(after['protected_vs_head'].values())
oldhits=load('old-sha-classification.json')
summary={'verdict':'FAIL','reason':'按指定历史目录排除和交付时git状态逐字验收；活动内核行为、目录和输入迁移未发现错误',
    'time':datetime.datetime.now().astimezone().isoformat(),'before_head':before['head'],'final_head':after['head'],
    'counts':{'sync_files':len(sync),'relocked_inputs':54,'verified_source_references':114,'rust_tests':sum(testcounts.values()),'python_tests':8,'independent_layouts':len(cases),'independent_ticks':sum(c['ticks'] for c in cases),'return_guard_failures':sum(c['return_guard_failures'] for c in cases),'return_guard_with_empty_destination':sum(c['return_guard_with_empty_destination'] for c in cases),'negative_controls':3,'historical_files':sum(counts.values()),'historical_bytes':sum(m['size'] for files in after['history'].values() for m in files.values()),'history_changed':0,'protected_texts':7,'active_behavior_inconsistencies':0,'acceptance_scope_inconsistencies':2,'old_sha_text_lines':oldhits['maintenance']['lines']+oldhits['specification']['lines'],'old_sha_text_files':oldhits['maintenance']['file_count']+oldhits['specification']['file_count'],'final_outside_scope_files':len(outside)},
    'test_counts':testcounts,'history_counts':counts,'outside_scope':outside,
    'inconsistencies':[{'id':'V-001','description':'排除三个指定历史目录及本verify后，旧SHA仍见维护档案和规格修订历史；未满足零处文本命中。活动54份输入残留0。','lines':544,'files':158},{'id':'V-002','description':'交付时git status仍有范围外既有未跟踪文件；非同步席或本核验新增。','paths':[x[3:] for x in outside]}]}
save('summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
