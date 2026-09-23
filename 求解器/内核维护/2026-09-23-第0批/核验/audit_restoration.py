import hashlib,json
from pathlib import Path
from audit_files import ROOT,OUT,IMPL,sha,save
from read_objects import obj,commit
MAINT=IMPL.parent
manifest=json.loads((MAINT/'2026-09-22d/R3-测试写历史/restore_manifest.json').read_text())['files']
drift=json.loads((MAINT/'2026-09-22d/R3-测试写历史/pre_day_hash_drift.json').read_text())
journal=json.loads((MAINT/'2026-09-22f/restore-journal.json').read_text())
oldtrees={c:commit(c)[2] for c in ['f8f6129','7da52a7','a7539f5','220f7b6']}
def blob_sha(c,p):return hashlib.sha256(obj(oldtrees[c][p]['oid'])[1]).hexdigest()
restored=[]
for r in manifest:
 p=r['path'];expected=r['expected_sha256'];now=sha(ROOT/p)
 sources={c:blob_sha(c,p) for c in ['f8f6129','7da52a7']}
 restored.append({'path':p,'expected':expected,'current':now,'source_blobs':sources,'passed':now==expected and all(s==expected for s in sources.values())})
known='crates/kernel/evidence/round6/revision-r5/cli/分流器三路轮询-absolute.json'
k=next(r for r in drift if r['path']==known and not r['tracked'])
known_source='求解器/数据/样例/分流器三路轮询-运行记录-v3-kernel.json'
restored.append({'path':'求解器/'+known,'expected':k['before_sha256'],'current':sha(ROOT/'求解器'/known),'source_current':sha(ROOT/known_source),'passed':sha(ROOT/'求解器'/known)==k['before_sha256']})
early=[]
for r in json.loads((MAINT/'2026-09-22/early-test-output-restoration.json').read_text()):
 p='求解器/'+r['path'];early.append({'path':p,'expected':r['expected_sha256'],'current':sha(ROOT/p),'passed':sha(ROOT/p)==r['expected_sha256']})
relocated=[]
for r in journal['relocated']:
 versions=[];first_dest=None
 for v in r['versions']:
  dest=v.get('dest',first_dest);first_dest=first_dest or dest
  expected=blob_sha(v['commit'],r['path']);actual=sha(ROOT/dest)
  versions.append({'commit':v['commit'],'dest':dest,'alias':not bool(v.get('dest')),'blob_sha256':expected,'current_sha256':actual,'passed':actual==expected})
 relocated.append({'old_path':r['path'],'old_path_absent':not (ROOT/r['path']).exists(),'versions':versions})
lost=[]
for r in drift:
 if r['tracked'] or r['path']==known:continue
 p=ROOT/'求解器'/r['path'];j=next(x for x in journal['untouched_lost'] if x['path']=='求解器/'+r['path']);marker=p.parent/'原字节缺失.json'
 lost.append({'path':'求解器/'+r['path'],'original_sha256':r['before_sha256'],'current_sha256':sha(p),'unchanged_since_restoration':sha(p)==j['current'],'original_missing_from_current':sha(p)!=r['before_sha256'],'required_marker':str(marker.relative_to(ROOT)),'marker_exists':marker.is_file()})
recovery_oid,recovery_raw,recovery_tree=commit('8ab232419c0e9e1702a14c4881a173f15fdade84')
parent=next(l.split()[1].decode() for l in recovery_raw.splitlines() if l.startswith(b'parent '));parent_tree=commit(parent)[2]
commit_changes=[p for p in sorted(recovery_tree.keys()|parent_tree.keys()) if recovery_tree.get(p)!=parent_tree.get(p)]
lineage=[];cursor='aec2a30d945e21a492d4b05639d67a63abacb5b3'
while True:
 lineage.append(cursor)
 if cursor==recovery_oid:break
 kind,data=obj(cursor);parents=[l.split()[1].decode() for l in data.splitlines() if l.startswith(b'parent ')]
 if not parents:break
 cursor=parents[0]
res={'restored':restored,'early_round5':early,'relocated':relocated,'lost_originals':lost,'required_marker_paths':sorted({r['required_marker'] for r in lost}),'recovery_commit':recovery_oid,'recovery_in_baseline_first_parent_ancestry':recovery_oid in lineage,'ancestry':lineage,'recovery_commit_changed_paths':commit_changes,'recovery_commit_changes_production':any('/src/' in p or p.endswith(('Cargo.toml','Cargo.lock')) for p in commit_changes),'counts':{'restored_match':sum(r['passed'] for r in restored),'early_match':sum(r['passed'] for r in early),'old_paths_absent':sum(r['old_path_absent'] for r in relocated),'versions_match':sum(v['passed'] for r in relocated for v in r['versions']),'lost_unchanged':sum(r['unchanged_since_restoration'] for r in lost),'missing_markers':len({r['required_marker'] for r in lost if not r['marker_exists']})}}
save('restoration-audit.json',res);print(json.dumps(res['counts'],ensure_ascii=False))
