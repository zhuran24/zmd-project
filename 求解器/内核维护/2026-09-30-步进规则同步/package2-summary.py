"""包二收尾：读已完成回执、比对旧文件和新来源锁，不执行测试/内核/Git。"""
import json
from guard import OUT,ROOT,REPO,SOURCES,save,digest,active_snapshot,difference,guard
current=guard('package2-final-v3')
start=json.loads((OUT/'package2-active-start.json').read_text());initial=json.loads((OUT/'initial-active.json').read_text());active=active_snapshot()
# guard 的通用活动清单不含 crate 根部审计文档，以首次写入前的原字节备份补列。
extra='求解器/crates/kernel/周期键读取审计.md'
backup=OUT/'before/crates/kernel/周期键读取审计.md'
assert extra not in start and backup.is_file()
start[extra]=digest(backup);active[extra]=digest(REPO/extra)
save('package2-extra-baseline.json',{'path':extra,'sha256':start[extra],'source':str(backup.relative_to(OUT)),'note':'首次包二写入前由 work.write 保存原字节；不改既有开工快照'})
save('package2-active-final.json',active)
delta=difference(start,active)
changed=[{'path':p,'change':kind,'before':start.get(p),'after':active.get(p)} for kind,paths in delta.items() for p in paths]
save('package2-changed-paths.json',changed)
legacy=[p for p in initial if p.startswith(('求解器/数据/样例/','求解器/crates/kernel/tests/fixtures/'))]
assert len(legacy)==124
for p in legacy:assert active[p]==initial[p],p
protected=[*SOURCES,'求解器/规格/内核配置-v1.json','求解器/规格/内核配置-v2.json','求解器/数据/正式静态目录.json','求解器/数据/工具/step_inputs.py','求解器/crates/kernel/tests/fixtures/step/base.json','求解器/crates/kernel/src/ledger.rs','求解器/crates/kernel/src/digest.rs']
protected += [p for p in start if p.startswith(('求解器/crates/topology/','求解器/数据/候选B/'))]
protected += [p for p in start if p.startswith('求解器/规格/') and p!='求解器/规格/内核输出.schema.json']
for p in protected:assert active[p]==start[p],p
commands=[json.loads(line) for line in (OUT/'commands.jsonl').read_text().splitlines() if json.loads(line)['name'].startswith('p2-')]
receipts=[]
for c in commands:
 assert not any(c['active_diff'].values()),c
 for side in ['before','after']:
  p=OUT/(c['name']+'-'+side+'-history.json');snap=json.loads(p.read_text())
  assert snap['files']==current['files'];assert not any(json.loads(p.with_name(p.stem+'-diff.json').read_text()).values())
  receipts.append({'command':c['name'],'side':side,'manifest':p.name,'sha256':digest(p),'unchanged':True})
final=[c for c in commands if c['name'].startswith('p2-final-')]
assert len(final)==11 and all(c['exit_code']==0 for c in final)
all_guards=[]
for p in sorted(OUT.glob('p2*-history-diff.json')):
 d=json.loads(p.read_text());assert not any(d.values()),p
 all_guards.append(p.name)
refs={}
for base in ['数据/样例/步进','crates/kernel/tests/fixtures/step']:
 for p in sorted((ROOT/base).rglob('*.json')):
  raw=json.loads(p.read_text());assert raw['schema']=='kernel-input-v4'
  for r in [raw['catalog'],raw['parameters']['axis_registry']]:assert digest((p.parent/r['path']).resolve())==r['sha256'],p
  refs[str(p.relative_to(ROOT))]=digest(p)
assert len(refs)==30
sim=ROOT/'规则修订/2026-09-30-迟滞/sim2/simulator.py'
summary={'package':'包二','status':'complete','changed_counts':{k:len(v) for k,v in delta.items()},'command_count':len(commands),'command_history_comparisons':len(receipts),'history_files':current['counts'],'history_bytes':sum(r['bytes'] for r in current['files'].values()),'history_manifest_sha256':digest(OUT/'package2-final-v3-history.json'),'history_changes':difference(json.loads((OUT/'initial-history.json').read_text())['files'],current['files']),'legacy_samples_and_fixtures_unchanged':len(legacy),'additional_protected_paths':len(set(protected)),'new_input_refs_verified':refs,'catalog_sha256':digest(ROOT/'数据/正式静态目录.json'),'config_sha256':digest(ROOT/'规格/内核配置-v2.json'),'schema_sha256':digest(ROOT/'规格/内核输出.schema.json'),'sim2_sha256':digest(sim),'rust_tests':{'kernel_lib':66,'topology_lib':1,'reference':13,'topology_validation':30,'kernel_doc':0,'topology_doc':0},'catalog_tests':9,'differential':{'cases':9,'steps':4000,'mismatches':0,'phenomenon_assertions':'passed'},'final_suite':final,'receipts':receipts,'all_package2_guard_diffs':all_guards,'blockers':[]}
save('package2-summary.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k not in ['new_input_refs_verified','receipts','final_suite','all_package2_guard_diffs']},ensure_ascii=False,indent=2))
