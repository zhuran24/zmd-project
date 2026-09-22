from pathlib import Path
import hashlib, json, subprocess, datetime, difflib
ROOT=Path('/home/zhuran24/zmd-research-fresh')
OUT=ROOT/'求解器/会议成果/任务书7执行/证据/规格'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
formal=[ROOT/n for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']]
expected=['31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff','1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac','f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6']
specs=[ROOT/'求解器/规格'/n for n in ['运行语义.md','选择点清单.md','选择点参数轴.md','受限模型声明.md','受限转移定义.md','内核输入.md','内核输出.md','内核配置-v1.json','四件前置义务对照.md']]
cat=ROOT/'求解器/数据/正式静态目录.json'
inputs=[ROOT/'求解器/会议成果'/n for n in ['任务书7草案.md','主会话三审-0920.md','会议2成果修订-v46.md','工作/总结-终稿.md']]
inputs += [ROOT/'求解器/crates/kernel/src'/n for n in ['input.rs','catalog.rs','config.rs','main.rs','transition.rs']]
protected=formal+[ROOT/'候选约束.txt']
# Hash-only baseline; no source tree or artifact copies.
assert not (OUT/'before.json').exists(), 'preserve original baseline; do not rerun mutating relock'
tracked=specs+[cat]+inputs+protected
save('before.json',{'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':[{'path':str(p),'sha256':digest(p),'lines':len(p.read_text().splitlines())} for p in dict.fromkeys(tracked)],'protected':[str(p) for p in protected]})
cmd=['sha256sum',*[str(p) for p in formal]]
r=subprocess.run(cmd,text=True,capture_output=True)
save('sha256sum.json',{'command':subprocess.list2cmdline(cmd),'cwd':str(ROOT),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
assert r.returncode==0
assert [digest(p) for p in formal]==expected
old=json.loads(cat.read_text()); new=json.loads(cat.read_text()); checks=[]
for s in new['sources']:
 p=ROOT/s['path']; lines=p.read_text().splitlines(); old_s=next(x for x in old['sources'] if x['path']==s['path'])
 checks.append({'path':str(p),'old_sha256':s['sha256'],'new_sha256':digest(p),'old_lines':len(s['lines']),'new_lines':len(lines),'old_lines_exact_match':s['lines']==lines,'line_diff':list(difflib.unified_diff(s['lines'],lines,fromfile='catalog before',tofile='formal source',lineterm=''))})
 s['sha256']=digest(p); s['lines']=lines
new['task']['goal']=formal[1].read_text().splitlines()[1]
new['task']['conditions']=[{'name':l.split('：',1)[0],'text':l.split('：',1)[1],'basis':'求解任务·'+l.split('：',1)[0]} for l in formal[1].read_text().splitlines()[5:] if '：' in l]
for u in new['units']:
 if u['id']=='协议储存箱':
  print('box feature',json.dumps(u.get('transfer',u.get('wireless_transfer')),ensure_ascii=False))
new['version']='2026-09-21-task7-source-relock'
new['transcribed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
cat.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n')
save('source-relock.json',{'checks':checks,'catalog_before':hashlib.sha256(json.dumps(old,ensure_ascii=False).encode()).hexdigest(),'catalog_after':digest(cat),'note':'catalog_before is parsed-value serialization digest; original byte digest is before.json. task.goal/conditions also refreshed from all current task lines.'})
print(r.stdout,end='');print('catalog',digest(cat));print('all source lines compared; constraints exact:',checks[2]['old_lines_exact_match'])
