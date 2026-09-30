"""只汇总包三实际回执，不运行测试，不改业务文件。"""
import json
from guard import OUT,ROOT,REPO,digest,save,active_snapshot,difference

def summary():
 commands=[json.loads(l) for l in (OUT/'commands.jsonl').read_text().splitlines() if json.loads(l)['name'].startswith('p3-')]
 assert len(commands)==13
 assert all(c['exit_code']==(1 if c['name']=='p3-legacy-check' else 0) and not any(c['active_diff'].values()) for c in commands)
 baseline=json.loads((OUT/'initial-history.json').read_text())
 receipts=[]
 for c in commands:
  for edge in ['before','after']:
   name=c['name']+'-'+edge+'-history.json';value=json.loads((OUT/name).read_text())
   assert value==baseline,name
   assert not any(json.loads((OUT/name.replace('.json','-diff.json')).read_text()).values())
   receipts.append({'command':c['name'],'edge':edge,'path':name,'sha256':digest(OUT/name),'equal_initial':True})
 audits=[]
 for p in sorted(OUT.glob('p3-audit[0-9][0-9].json')):
  a=json.loads(p.read_text());audits.append({'path':p.name,'status':a['status'],'sha256':digest(p)})
  for edge in ['before','after']:
   n=p.stem+'-'+edge+'-history.json';assert json.loads((OUT/n).read_text())==baseline,n
 assert audits[-1]['status']=='pass'
 before=json.loads((OUT/'package3-active-before.json').read_text());after=active_snapshot()
 for r in ['crates/kernel/README.md','crates/kernel/修订记录.md','crates/kernel/周期键读取审计.md']:after['求解器/'+r]=digest(ROOT/r)
 changes=difference(before,after);assert not changes['added'] and not changes['deleted']
 changed=[{'path':p,'before':before[p],'after':after[p]} for p in changes['changed']]
 save('package3-changed-paths.json',changed);save('package3-active-final.json',after)
 checks=[]
 for p in sorted(OUT.glob('p3-*-history-diff.json')):
  assert not any(json.loads(p.read_text()).values()),p.name
  checks.append(p.name)
 value={'package':3,'status':'complete','commands':commands,'command_count':13,'command_history_comparisons':len(receipts),'receipts':receipts,'audit_attempts':audits,'audit_history_comparisons':2*len(audits),'all_package3_guard_comparisons':len(checks),'all_package3_guard_diff_paths':checks,'history_counts':baseline['counts'],'history_bytes':sum(v['bytes'] for v in baseline['files'].values()),'history_manifest_sha256':digest(OUT/'initial-history.json'),'changed_business_files':len(changed),'changed_paths':'package3-changed-paths.json','final_audit':audits[-1]['path'],'source_hashes':{p:digest(REPO/p) for p in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']},'catalog_sha256':digest(ROOT/'数据/正式静态目录.json'),'config_sha256':digest(ROOT/'规格/内核配置-v2.json'),'blockers':[]}
 save('package3-summary.json',value)
 return value
if __name__=='__main__':
 s=summary();print(json.dumps({k:s[k] for k in ['status','command_count','command_history_comparisons','audit_history_comparisons','all_package3_guard_comparisons','changed_business_files','final_audit']},ensure_ascii=False))
