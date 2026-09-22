from pathlib import Path
import json,hashlib,re,subprocess,collections,datetime,ast
R=Path('/home/zhuran24/zmd-research-fresh'); W=R/'求解器'; S=W/'规格'; E=W/'会议成果/任务书7执行/证据/规格'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(E/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
results=[]
def check(name,value,detail=None):
 results.append({'check':name,'pass':bool(value),'detail':detail})
formal=['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']; catalog=json.loads((W/'数据/正式静态目录.json').read_text())
expected=['31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff','1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac','f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6']
for n,sha in zip(formal,expected):
 p=R/n; source=next(x for x in catalog['sources'] if x['path']==n)
 check('formal bytes and catalog lines: '+n,h(p)==sha==source['sha256'] and source['lines']==p.read_text().splitlines(),{'sha256':h(p),'line_count':len(source['lines'])})
conditions=[{'name':l.split('：',1)[0],'text':l.split('：',1)[1],'basis':'求解任务·'+l.split('：',1)[0]} for l in (R/'求解任务.txt').read_text().splitlines()[5:] if '：' in l]
check('task.conditions complete current text',catalog['task']['conditions']==conditions)
check('box transfer catalog current',next(x for x in catalog['units'] if x['id']=='协议储存箱')['transfer']['cooldown_scope']=='box')
old=json.loads((E/'before.json').read_text())
for x in old['files']:
 p=Path(x['path'])
 if x['path'] in old['protected'] or '/crates/kernel/src/' in str(p):check('protected unchanged: '+str(p),h(p)==x['sha256'])
c=json.loads((S/'内核配置-v1.json').read_text()); axes=c['axes'];check('99 axes retained',c['axis_count']==len(axes)==99)
for name in ['选择点参数轴.md','受限模型声明.md','内核输入.md']:
 matches=re.findall(r'^\| `([a-z_]+\.[a-z_]+)` \|', (S/name).read_text(),re.M)
 check('axis names exact once: '+name,len(matches)==99 and set(matches)==set(axes))
# Cross-file lifetime and explicit input group check.
rows={m[0]:m[1:] for m in re.findall(r'^\| `([a-z_]+\.[a-z_]+)` \| ([^|]+) \| ([^|]+) \| ([^\n]+)',(S/'选择点参数轴.md').read_text(),re.M)}
check('registry/config lifetimes equal',all(rows[a][1].strip()==v['lifetime'] for a,v in axes.items()))
known={'polling.both_failure':'advance_authorized','connection.port_meeting':'shared_edge_opposite','transfer.cooldown_scope':'box','transfer.partial_acceptance':'max_receivable','gate.identity_recovery':'current_conditions','gate.total_recovery':'current_conditions','gate.window_clock':'wall_clock','gate.window_recovery':'on_expiry_if_other_guards'}
for a,v in known.items():check('known: '+a,axes[a]['disposition']=='已定' and axes[a]['value']==v and axes[a]['lifetime']=='F')
check('debug permission distinct from tool stop','任意操作' in axes['initialization.debug_actions']['meaning'] and axes['initialization.debug_actions']['disposition']=='超出覆盖即停')
check('threshold keeps cumulative count','只改阈值保持全时段累计数n' in axes['gate.counter_edit']['meaning'])
check('zero-transfer fact explicitly pending',axes['transfer.failure_cooldown']['disposition']=='超出覆盖即停' and '缺游戏事实' in axes['transfer.failure_cooldown']['coverage_loss'])
# Scanner intentionally distinguishes explicit history sections from active provisions.
names=['运行语义.md','选择点清单.md','选择点参数轴.md','受限模型声明.md','受限转移定义.md','内核输入.md','内核输出.md','内核配置-v1.json','四件前置义务对照.md']
forbidden=['abc7a5867f64','10abf80fe6ee','all_or_nothing','"latched"','closed_segment_touch','no_attempt_hold','advance_both','手搬无正面来源','手搬无来源不能作为许可','增建范围另审','空格也参与','冷却粒度另外未定']
def active_text(n,t):
 if n=='受限转移定义.md': return t.split('## 5. 旧工程')[0]+t[t.index('### 6.5 正式循环'):]
 return t
hits=[]
for n in names:
 t=active_text(n,(S/n).read_text())
 for pattern in forbidden:
  for l,line in enumerate(t.splitlines(),1):
   if pattern in line:hits.append({'file':n,'active_view_line':l,'pattern':pattern,'text':line})
check('no active stale hashes/permissions/conflicting alternatives',not hits,hits)
fixtures=['abc7a5867f64','手搬无正面来源','all_or_nothing','closed_segment_touch','no_attempt_hold']
check('scanner detects stale fixtures',all(any(p in f for p in forbidden) for f in fixtures))
# Schema syntax and actual corner-value removal.
schema=json.loads((S/'内核输出.schema.json').read_text())
check('schema JSON parses and corner enum removed','closed_segment_touch' not in json.dumps(schema))
schema_change=next(x for x in json.loads((E/'polish-changes.json').read_text()) if x['path'].endswith('内核输出.schema.json'))
restored=json.loads(json.dumps(schema))
for pointer in schema_change['enum_paths']:
 parts=pointer.split('/')[1:]; cur=restored
 for part in parts:cur=cur[int(part)] if isinstance(cur,list) else cur[part]
 cur.append('closed_segment_touch')
check('schema changes limited to five enum removals',hashlib.sha256((json.dumps(restored,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()==schema_change['before_sha256'])
# Fingerprint chain matches the actual completed load.
v=json.loads((E/'load-verification.json').read_text())
check('completed load matches final config/catalog/registry',v['config_sha256']==h(S/'内核配置-v1.json') and v['catalog_sha256']==h(W/'数据/正式静态目录.json') and v['axis_sha256']==h(S/'选择点参数轴.md'))
check('build/seed/check passed',all(x['exit_code']==0 for x in json.loads((E/'commands.json').read_text())))
# Secondary active source registry: source constants only, no historical result reuse.
p=W/'数据/样例/check_examples.py'; tree=ast.parse(p.read_text())
node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCE_HASHES' for t in n.targets))
check('secondary SOURCE_HASHES current',ast.literal_eval(node.value)==dict(zip(formal,expected)))
secondary=json.loads((E/'secondary-registry.json').read_text())
check('secondary registry final bytes locked',h(p)==secondary['final_sha256'])
# Catalog copies / evidence hashes are inventoried, never rewritten in-place.
old_hashes={'rule':'abc7a5867f6477eedb619c63a21c4a77144c57ad4567fdcfb696b3049d66a670','task':'10abf80fe6eefe647471eabe78da4053f77b489d3806722c501c6acb405a2864','catalog':'74d21a5bd37c6178f988a86a4aa78a03d1e4244ecff26f133bb5e700ada82e43'}
refs={}
for label,sha in old_hashes.items():
 cmd=['rg','-l','-F',sha,str(W),'-g','!target/**','-g','!.git/**','-g','!会议成果/任务书7执行/**']
 r=subprocess.run(cmd,text=True,capture_output=True);assert r.returncode in [0,1]
 paths=[p for p in r.stdout.splitlines() if '/target/' not in p and '/任务书7执行/' not in p]
 refs[label]={'sha256':sha,'command':subprocess.list2cmdline(cmd),'exit_code':r.returncode,'file_count':len(paths),'files':paths,'treatment':'历史测试/复核/旧生成器引用登记为失配；本席未批量改写，任务8按依赖重生成或保留史料'}
save('historical-references.json',refs)
# Live compile-time catalog/config consumers are source includes, not additional hash registries.
load_code=[]
for name,ranges in {'input.rs':[(335,364)],'catalog.rs':[(66,95)],'config.rs':[(357,389)],'seed.rs':[(5,14)]}.items():
 p=W/'crates/kernel/src'/name; lines=p.read_text().splitlines();load_code.append({'path':str(p),'sha256':h(p),'excerpts':[{'start':a,'end':b,'lines':lines[a-1:b]} for a,b in ranges]})
p=W/'crates/topology/src/lib.rs';lines=p.read_text().splitlines();load_code.append({'path':str(p),'sha256':h(p),'excerpts':[{'start':228,'end':231,'lines':lines[227:231]}]})
save('loader-evidence.json',{'code':load_code,'interpretation':'reference()检查文件原始字节sha256；Catalog::load比较serde_json::Value相等，并非原始字节逐字相等；catalog和config编译期include_str使用当前文件。topology也include同一路径，本次按授权只编译kernel。另有样例检查器SOURCE_HASHES已仅同步两项哈希，见secondary-registry.json；候选B来源清单及各baseline属于既有证据指纹，不刷新其通过结果。'})
check('evidence allowed file extensions',all(p.suffix in {'.py','.sh','.log','.json','.md'} for p in E.iterdir() if p.is_file()))
report={'status':'passed' if all(x['pass'] for x in results) else 'failed','time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':results,'historical_reference_counts':{k:v['file_count'] for k,v in refs.items()},'source_review':'条文事实、必要条件、充分证明、局部反例、完整布局证据与未完成项按规格回填.md分层；无L/U更新','independent_review':False}
save('self-check.json',report)
print(json.dumps({'status':report['status'],'checks':len(results),'failures':[x for x in results if not x['pass']],'historical_reference_counts':report['historical_reference_counts']},ensure_ascii=False,indent=2))
raise SystemExit(0 if report['status']=='passed' else 1)
