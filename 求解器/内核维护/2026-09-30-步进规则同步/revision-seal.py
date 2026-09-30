"""交付封存：回执、历史全量哈希、只读参照、追加边界及本地链接复核。"""
import json,re,difflib
from pathlib import Path
from guard import OUT,ROOT,REPO,guard,digest,save,difference

def read(p):return json.loads(p.read_text())
audit=read(OUT/'revision-audit03.json');assert audit['status']=='pass'
assert not (OUT/'STOP.json').exists() and not (OUT/'ACTIVE_STOP.json').exists()
guard('revision-seal-before')
base=read(OUT/'initial-history.json')
commands=[json.loads(l) for l in (OUT/'commands.jsonl').read_text().splitlines() if json.loads(l)['name'].startswith('revision-')]
assert len(commands)==25
assert [(r['name'],r['exit_code']) for r in commands if r['exit_code']]==[('revision-lib01',101)]
for r in commands:
 assert not any(r['active_diff'].values()),r['name']
 for side in ['before','after']:
  assert read(OUT/(r['name']+'-'+side+'-history.json'))==base
for label in ['revision-differential','revision-diagnose','revision-differential-final','revision-diagnose-final']:
 r=read(OUT/'差分'/(label+'.json'))
 assert not any(r['source_changes'].values()) and not any(r['history']['difference'].values())
 for side in ['before','after']:assert read(OUT/(label+'-'+side+'-history.json'))==base
for name in ['crates/kernel/修订记录.md','规格/修订记录.md']:
 assert (ROOT/name).read_bytes().startswith((OUT/'revision-before/求解器'/name).read_bytes())
assert (OUT/'记录.md').read_bytes().startswith((OUT/'revision-record-before.md').read_bytes())
# 两个旧反例保持原字节；旧摘要不被新配置指纹覆盖。
prior=read(OUT/'差分/最终结论.json')
for row in prior['findings']:assert digest(Path(row['witness']))==row['witness_sha256']
sim=ROOT/'规则修订/2026-09-30-迟滞/sim2/simulator.py'
assert digest(sim)=='08a83262a5ca2651a3dc06b4fed83bc3f6e957379e5eec7b63094788f0d0bac8'
# 与最终差分所核对的代码、配置、工具及正式源逐文件再比。
suite=read(OUT/'差分/revision-differential-final.json')
for name,sha in suite['sources'].items():assert digest(Path(name))==sha,name
before=read(OUT/'revision-active-before.json');after=read(OUT/'revision-audit03-active-after.json')
changed=[{'path':p,'before_sha256':before[p],'after_sha256':after[p]} for p in audit['active_diff']['changed']]
# 用普通文本差分保存复核入口，不调用Git。
patch=[]
for row in changed:
 path=row['path'];a=(OUT/'revision-before'/path).read_text().splitlines(keepends=True);b=(REPO/path).read_text().splitlines(keepends=True)
 patch.extend(difflib.unified_diff(a,b,fromfile=path+' (before)',tofile=path+' (after)'))
(OUT/'revision-changes.patch').write_text(''.join(patch))
summary={'status':'completed','report_path':str(OUT/'修订处置.md'),'blockers':[],
 'config_sha256':digest(ROOT/'规格/内核配置-v2.json'),'catalog_sha256':digest(ROOT/'数据/正式静态目录.json'),
 'audit':'revision-audit03.json','commands':commands,'final_safe_suite':[r['name'] for r in commands if r['name'].startswith('revision-final2-')],
 'test_before_after_snapshots':58,'differential':{'suite':'差分/revision-differential-final.json','diagnosis':'差分/revision-diagnose-final.json','cases':len(suite['cases']),'steps':sum(c['steps'] for c in suite['cases']),'known_sim2_mismatches':len(suite['mismatches']),'errors':suite['errors']},
 'changed_files':changed,'changed_file_count':len(changed),'samples_other_than_config_sha_unchanged':True,'old_witnesses_unchanged':True,'original_record_sections_unchanged':True,
 'reader_review':{'date':'2026-09-30','status':'passed','scope':['修订处置.md','记录.md 修订节','设计相关小节','现行规格及轴表'],'corrections':['设计5.1链接锚点按真实标题更正','缓存闸方向与L18核等','覆盖判据按专用事件明确保守回退','失败记录与最终验收按时点分开']}}
save('revision-summary.json',summary)
links=[]
reviewed=[OUT/'修订处置.md',OUT/'设计.md',OUT/'记录.md']
reviewed += [ROOT/'规格'/s for s in ['运行语义.md','内核输入.md','内核输出.md','受限模型声明.md','选择点参数轴.md']]
for p in reviewed:
 text=p.read_text()
 if p.name=='记录.md':text=text.split('\n## 修订\n',1)[1]
 for link in re.findall(r'\]\(([^)]+)\)',text):
  if '://' in link:continue
  target,_,anchor=link.partition('#');dest=(p.parent/target).resolve()
  assert dest.exists(),(p,link)
  if anchor and dest.suffix=='.md':
   headings=re.findall(r'^#{1,6} (.+)$',dest.read_text(),re.M)
   def slug(s):return re.sub(r'[^\w\- ]','',s.lower()).replace(' ','-')
   assert anchor in [slug(h) for h in headings],(p,link,headings)
  links.append({'from':str(p.relative_to(ROOT)),'target':link})
summary['reader_review']['links_checked']=len(links)
summary['reader_review']['links']=links
guard('revision-seal-after')
snapshots=sorted(OUT.glob('revision*-history.json'))
for p in snapshots:assert read(p)==base,p
summary['history']={'counts':base['counts'],'files':len(base['files']),'bytes':sum(v['bytes'] for v in base['files'].values()),'baseline_sha256':digest(OUT/'initial-history.json'),'all_snapshots_equal':True,'snapshots':[{'path':p.name,'sha256':digest(p)} for p in snapshots]}
summary['artifacts']={str(p.relative_to(OUT)):digest(p) for p in [OUT/'修订处置.md',OUT/'记录.md',OUT/'revision-changes.patch',OUT/'revision-audit03.json',OUT/'差分/revision-differential-final.json',OUT/'差分/revision-diagnose-final.json']}
save('revision-summary.json',summary)
print(json.dumps({'status':'completed','files_changed':len(changed),'history_files':len(base['files']),'snapshots_equal':len(snapshots),'links_checked':len(links),'report_path':summary['report_path'],'blockers':[]},ensure_ascii=False))
