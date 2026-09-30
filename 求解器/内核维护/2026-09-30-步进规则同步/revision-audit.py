"""修订只读审计；复用包三回源与逐轴投影判据，前后复用3481文件原始基线。"""
import importlib.util,json,re,subprocess,sys,time,traceback
from collections import Counter
from pathlib import Path
from guard import OUT,ROOT,REPO,HISTORY,SOURCES,guard,digest,save,active_snapshot,difference
ACTIVE=['运行语义.md','受限转移定义.md','受限模型声明.md','选择点清单.md','选择点参数轴.md','内核输入.md','内核输出.md','内核输出.schema.json','内核配置-v2.json','规则覆盖表.md']
BUSINESS=['规格/'+n for n in ACTIVE if n not in ['内核配置-v2.json','内核输出.schema.json']]+['规格/check_revision.py','规格/修订记录.md','数据/规则覆盖表.md','数据/候选B/来源清单.json','数据/候选B/校验报告.md','数据/候选B/验证记录.md','crates/kernel/README.md','crates/kernel/修订记录.md']
OLD=['680acb480aa28443431e119c98e4cc45ca6abade1670c9a4a1283a77a7d199a2','74deafed83876dcf40fffe55d8f01d45edcfd2840e35725c8006da996c877e02','6e64e3903a65536c530b363c9f3aef8c1bb2a1c1193e866799125dd047159924','1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac']
def historical_lists():
 entries=set()
 for rel in ['数据/样例/历史说明.md','crates/kernel/tests/历史说明.md']:
  p=ROOT/rel
  for target in re.findall(r'^- \[[^\]]+\]\(([^)]+)\)',p.read_text(),re.M):entries.add((p.parent/target).resolve())
 return entries

def scan(label):
 argv=['rg','--hidden','--no-ignore','-l','-0','-F']
 for h in OLD:argv+=['-e',h]
 argv+=['-g','!.git/**','-g','!**/target/**','-g','!**/__pycache__/**','-g','!**/.cargo-home/**','.']
 r=subprocess.run(argv,cwd=REPO,capture_output=True);assert r.returncode in (0,1),r.stderr.decode()
 explicit=historical_lists();rows=[]
 archives=['内核维护/','老项目/','候选简化轮次/','规则修订/','构造/','几何/','结构检测/','候选约束轮次/','约束修订/','会议成果/']
 for name in sorted(p.removeprefix('./') for p in r.stdout.decode().split('\0') if p):
  p=REPO/name;relative=name.removeprefix('求解器/')
  if any(relative.startswith(x+'/') for x in HISTORY):kind='protected_history';basis='任务书§2三历史目录'
  elif p.resolve().is_relative_to(OUT):kind='this_run_record';basis='本轮实施日志及before/staging不作活动入口'
  elif p.resolve() in explicit:kind='indexed_history';basis='设计§7及样例/测试历史说明逐文件清单'
  elif relative in ['规格/修订记录.md','crates/kernel/修订记录.md']:kind='revision_history';basis='按时点追加的修订记录'
  elif relative.startswith('规格/') and relative not in ['规格/'+x for x in ACTIVE]+['规格/check_revision.py']:
   kind='historical_spec';basis='运行语义§1现行清单之外的规格/复核'
  elif name.startswith('求解器/') and any(relative.startswith(a) for a in archives):kind='archived_or_parallel';basis='带轮次的历史研究/维护档案，沿用r29分类'
  else:kind='active';basis='不在历史清单或归档范围'
  rows.append({'path':name,'category':kind,'basis':basis})
 value={'argv':argv,'exit_code':r.returncode,'counts':dict(Counter(x['category'] for x in rows)),'files':rows,'active_residuals':[x['path'] for x in rows if x['category']=='active']}
 save(label+'-old-sha-inventory.json',value)
 return value

def rows(t):return [[c.strip() for c in line.split('|')[1:-1]] for line in t.splitlines() if re.match(r'^\| \d+ \|',line)]
def checks(label):
 sys.path.insert(0,str(ROOT/'数据/工具'))
 import formal_catalog
 cat=json.loads((ROOT/'数据/正式静态目录.json').read_text());formal_catalog.verify(cat)
 assert cat['schema']=='static-catalog-v3' and cat['version']=='2026-09-30-r30-step'
 inputs=[];prof=ROOT/'规格/内核配置-v2.json';catalog=ROOT/'数据/正式静态目录.json'
 for base in [ROOT/'数据/样例/步进',ROOT/'crates/kernel/tests/fixtures/step']:
  for p in sorted(base.rglob('*.json')):
   a=json.loads(p.read_text());assert a['schema']=='kernel-input-v4',p
   for key,target in [(a['catalog'],catalog),(a['parameters']['axis_registry'],prof)]:
    assert (p.parent/key['path']).resolve()==target.resolve(),p
    assert key['sha256']==digest(target),p
   inputs.append({'path':str(p.relative_to(ROOT)),'sha256':digest(p)})
 assert len(inputs)==30,len(inputs)
 candidate=json.loads((ROOT/'数据/候选B/来源清单.json').read_text());assert len(candidate)==16
 for ref in candidate: assert digest(Path(ref['path']))==ref['sha256'],ref['path']
 fingerprints=json.loads((OUT/'只读文件指纹.json').read_text());assert len(fingerprints)==4
 for p,h in fingerprints.items():assert digest(Path(p))==h,p
 semantics=(ROOT/'规格/运行语义.md').read_text()
 for name in SOURCES: assert digest(REPO/name) in semantics,name
 sections=set(re.findall(r'^#{2,3} (\d+(?:\.\d+)*)\.',semantics,re.M))|set(re.findall(r'^#{2,3} (\d+(?:\.\d+)*) ',semantics,re.M))
 st=(ROOT/'规格/规则覆盖表.md').read_text();dt=(ROOT/'数据/规则覆盖表.md').read_text()
 for n,name,sh,dh in [(0,SOURCES[0],'## 1. 游戏规则逐行','## 《明日方舟：终末地》游戏规则.txt'),(1,SOURCES[1],'## 2. 求解任务逐行','## 求解任务.txt')]:
  source=(REPO/name).read_text().splitlines()
  for text,head,isdata in [(st,sh,False),(dt,dh,True)]:
   r=rows(text.split(head,1)[1].split('\n## ',1)[0]);assert len(r)==len(source),(name,isdata)
   for i,(row,line) in enumerate(zip(r,source)):
    assert row[0]==str(i+1) and row[1]==(line.strip() or '（空行）'),(name,i+1)
    assert all(row[2:]),row
    if isdata:assert f'sources[{n}].lines[{i}]' in row[2],row
    else:
     for sec in re.findall(r'§(\d+(?:\.\d+)*)',row[2]):assert sec in sections,sec
 # 旧工具只读核约束行重建字节不变，再对照包三前表。
 p=ROOT/'内核维护/2026-09-26-第88-89轮三审同步/work.py'
 spec=importlib.util.spec_from_file_location('r29_work_audit',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 for rel,fn in [('规格/规则覆盖表.md',m.rebuild_semantics_table),('数据/规则覆盖表.md',m.rebuild_contract_table)]:
  t=(ROOT/rel).read_text();assert fn(t,cat)==t,rel
  before=(OUT/'package3-before'/rel).read_text()
  select=lambda x:[l for l in x.splitlines() if re.match(r'^\| \d+ \| \d+ \| 约束·',l) or '`constraints[' in l]
  assert select(before)==select(t) and len(select(t))==77,rel
 specrows=rows(st.split('## 3. 正式约束条目登记',1)[1].split('\n## ',1)[0]);assert len(specrows)==77
 for i,(r,c) in enumerate(zip(specrows,cat['constraints']),1):assert (r[0],r[1],r[2])==(str(i),str(c['source_line']),'约束·'+c['name'])
 # 配方表保留18项，字段/耗时逐条核目录。
 rec=re.findall(r'^\| `([^`]+)` \| `([^`]+)` \| (.*?) \| (\d+) \|$',semantics,re.M)
 assert len(rec)==18
 rm={x['id']:x for x in cat['recipes']}
 for ident,kind,formula,duration in rec:
  r=rm[ident];fmt=lambda d:'＋'.join(q['value']+' '+item for item,q in d.items())
  assert (kind,formula,duration)==(r['kind'],fmt(r['inputs'])+' → '+fmt(r['outputs']),r['duration']['value'])
 config=json.loads(prof.read_text());assert len(config['axes'])==config['axis_count']==66
 counts=Counter(v['disposition'] for v in config['axes'].values());assert counts=={'已定':21,'本版选值':14,'由输入全称量化':15,'超出覆盖即停':16}
 for rel in ['规格/受限模型声明.md','规格/选择点参数轴.md']:
  text=(ROOT/rel).read_text();axisrows={x[1]:x[2] for x in re.findall(r'^(\| `([^`]+)` \| (.*))$',text,re.M)}
  assert set(axisrows)==set(config['axes']) and len(axisrows)==66,rel
  for k,v in config['axes'].items():
   line=axisrows[k]
   for field in (['disposition','meaning','basis','coverage_loss','extension_gate'] if '受限模型' in rel else ['disposition','meaning','basis','choice','lifetime']):assert str(v[field]).replace('|','&#124;') in line,(rel,k,field)
   val=json.dumps(v['value'],ensure_ascii=False,separators=(',',':')).replace('|','&#124;');assert '`'+val+'`' in line,(rel,k)
 choices=(ROOT/'规格/选择点清单.md').read_text();ids=re.findall(r'^## (T\d+)\.',choices,re.M);assert set(ids)=={f'T{i}' for i in range(1,18) if i!=13} and len(ids)==16
 for i in [1,2,3,4,8,14,16,17]:assert '由 2026-09-30 规则解决' in choices.split(f'## T{i}.',1)[1].split('\n## ',1)[0]
 forbidden=r'ordered_sweeps|dual_permission|damping\.|存货优先级|断开存货端口通道|judgment\.order'
 for name in ['运行语义.md','受限转移定义.md','受限模型声明.md','选择点参数轴.md','内核输入.md','内核输出.md']:assert not re.search(forbidden,(ROOT/'规格'/name).read_text()),name
 links=[]
 for rel in BUSINESS:
  p=ROOT/rel
  if p.suffix!='.md' or rel.endswith('修订记录.md'):continue
  # 候选验证记录的正文是原字节历史；只核当前首段。
  text=p.read_text().split('## 2026-09-19 历史验证')[0] if rel.endswith('验证记录.md') else p.read_text()
  for target in re.findall(r'\]\(([^)]+)\)',text):
   if '://' in target:continue
   assert (p.parent/target.split('#')[0]).exists(),(rel,target)
   links.append((rel,target))
 # candidate报告来源为本次守卫命令，不重新运行二进制。
 report=ROOT/'数据/候选B/校验报告.md'
 assert report.read_bytes()==(OUT/'p3-candidate-report.log').read_bytes()
 rt=report.read_text();assert '2026-09-30-r30-step' in rt
 headings=re.findall(r'^## (.*)',rt,re.M)
 assert re.search(r'^## 能检且不通过（0 项，算术推论）$',rt,re.M)
 # 相对修订开工字节的显式允许域；其余旧输入、工具、源码与规格均保持。
 before=json.loads((OUT/'revision-active-before.json').read_text());after=active_snapshot()
 for rel in ['crates/kernel/README.md','crates/kernel/修订记录.md','内核维护/2026-09-30-步进规则同步/设计.md','内核维护/2026-09-30-步进规则同步/差分/diagnose.py']:
  after['求解器/'+rel]=digest(ROOT/rel)
 allowed=set('求解器/'+r for r in [
  'crates/kernel/src/input.rs','crates/kernel/src/graph.rs','crates/kernel/src/output.rs',
  'crates/kernel/src/tests_graph.rs','crates/kernel/src/tests_output.rs','crates/kernel/tests/reference.rs',
  '数据/工具/step_graph.py','数据/工具/step_inputs.py','数据/样例/历史说明.md',
  '规格/内核配置-v2.json','规格/运行语义.md','规格/内核输入.md','规格/内核输出.md',
  '规格/受限模型声明.md','规格/选择点参数轴.md','规格/修订记录.md','crates/kernel/修订记录.md',
  '内核维护/2026-09-30-步进规则同步/设计.md','内核维护/2026-09-30-步进规则同步/差分/diagnose.py'])
 allowed.update('求解器/'+r for r in json.loads((OUT/'revision-samples-final.json').read_text())['files'])
 delta=difference(before,after)
 assert not delta['added'] and not delta['deleted'],delta
 assert set(delta['changed'])<=allowed,delta
 # 30 份输入除配置 SHA 之外，其余语义字节对象与开工时相等。
 for rel in json.loads((OUT/'revision-samples-final.json').read_text())['files']:
  old=json.loads((OUT/'revision-before/求解器'/rel).read_text());new=json.loads((ROOT/rel).read_text())
  old['parameters']['axis_registry']['sha256']=new['parameters']['axis_registry']['sha256']
  assert old==new,rel
 save(label+'-active-after.json',after)
 inventory=scan(label);assert not inventory['active_residuals'],inventory['active_residuals']
 return {'status':'pass','catalog_sha256':digest(catalog),'config_sha256':digest(prof),'inputs':inputs,'candidate_sources':16,'candidate_headings':headings,'rule_lines':115,'task_lines':15,'constraints':77,'constraint_rows_unchanged':True,'recipes':18,'axes':66,'axis_dispositions':dict(counts),'local_links_checked':len(links),'readonly_fingerprints':4,'active_diff':delta,'old_sha_counts':inventory['counts'],'active_old_sha_residuals':0,'old_sha_inventory':label+'-old-sha-inventory.json'}
def audit():
 n=1
 while (OUT/f'revision-audit{n:02d}.json').exists():n+=1
 label=f'revision-audit{n:02d}';guard(label+'-before');start=time.monotonic();result={}
 try:result=checks(label)
 except Exception as e:
  result={'status':'fail','error':str(e),'traceback':traceback.format_exc()};raise
 finally:
  result['seconds']=round(time.monotonic()-start,3);result['argv']=['python3','-B','内核维护/2026-09-30-步进规则同步/revision-audit.py'];save(label+'.json',result);guard(label+'-after')
 print(json.dumps({k:v for k,v in result.items() if k not in ['inputs','active_diff']},ensure_ascii=False))
if __name__=='__main__':audit()
