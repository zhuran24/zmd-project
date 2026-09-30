"""整理包一已有命令回执与文件哈希；不执行内核、测试或 Git。"""
import hashlib
import json
from pathlib import Path
from guard import OUT, ROOT, REPO, HISTORY, SOURCES, save, digest, active_snapshot, difference, guard

current = guard('package1-final')
initial = json.loads((OUT/'initial-active.json').read_text())
active = active_snapshot()
save('package1-active-final.json',active)
delta = difference(initial,active)
rows=[]
for kind,paths in delta.items():
    for path in paths: rows.append({'path':path,'change':kind,'before':initial.get(path),'after':active.get(path)})
save('package1-changed-paths.json',rows)
commands=[json.loads(s) for s in (OUT/'commands.jsonl').read_text().splitlines()]
receipts=[]
for c in commands:
    for side in ['before','after']:
        p=OUT/(c['name']+'-'+side+'-history.json')
        evidence=json.loads(p.read_text())
        assert evidence['files']==current['files'],p
        assert not any(json.loads((OUT/(c['name']+'-'+side+'-history-diff.json')).read_text()).values())
        receipts.append({'command':c['name'],'side':side,'manifest':p.name,'sha256':digest(p),'unchanged':True})
protected = [p for p in initial if p.startswith(('求解器/数据/样例/','求解器/crates/kernel/tests/fixtures/'))]
protected += ['求解器/规格/内核配置-v1.json', *SOURCES]
protected += ['求解器/crates/kernel/src/'+f for f in ['output.rs','cycle.rs','cycle_io.rs','event_identity.rs','seed.rs','ledger.rs','digest.rs']]
assert all(initial[p]==active[p] for p in protected)
assert not (OUT/'STOP.json').exists()
# 指纹基线覆盖所有旧文件；不把本轮新建文件的早期版本冒称原字节备份。
for p in (OUT/'before').rglob('*'):
    if p.is_file() and '求解器/'+p.relative_to(OUT/'before').as_posix() not in initial:
        p.unlink()
summary={'package':'包一','status':'complete','command_count':len(commands),'command_history_comparisons':len(receipts),'history_files':current['counts'],'history_bytes':sum(r['bytes'] for r in current['files'].values()),'history_manifest_sha256':digest(OUT/'package1-final-history.json'),'history_changes':difference(json.loads((OUT/'initial-history.json').read_text())['files'],current['files']),'changed_counts':{k:len(v) for k,v in delta.items()},'unchanged_history_inputs_and_detached_modules':len(protected),'catalog_sha256':digest(ROOT/'数据/正式静态目录.json'),'config_sha256':digest(ROOT/'规格/内核配置-v2.json'),'fixture_sha256':digest(ROOT/'crates/kernel/tests/fixtures/step/base.json'),'final_suite':[{'name':c['name'],'argv':c['argv'],'exit_code':c['exit_code']} for c in commands if c['name'].startswith('final-')],'rust_tests':{'kernel_lib':54,'topology_lib':1,'reference':1,'topology_validation':30,'kernel_doc':0,'topology_doc':0},'catalog_tests':9,'unit_leaf_mutations':1173,'recipe_leaf_mutations':154,'receipts':receipts}
assert all(c['exit_code']==0 for c in summary['final_suite']) and len(summary['final_suite'])==11
save('package1-summary.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k not in ['receipts','final_suite']},ensure_ascii=False,indent=2))
