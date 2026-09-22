"""规格、schema及负例的作者自核；不运行内核，不把合成形状样例作为游戏证书。"""
from pathlib import Path
import copy,hashlib,json,re,subprocess,sys
from collections import Counter
R=Path('/home/zhuran24/zmd-research-fresh'); S=R/'求解器/规格'; E=Path(__file__).resolve().parent
AJV=Path('/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js')
SCHEMA=json.loads((S/'内核输出.schema.json').read_text())
config=json.loads((S/'内核配置-v1.json').read_text()); axes=config['axes']
before=json.loads((E/'before.json').read_text())['files']
checks=[]
def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

protected=['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt',
 '求解器/会议成果/任务书7执行/受限转移定义-§6.5替换稿.md','求解器/会议成果/任务书7执行/规格修改稿-任务6.md',
 '求解器/会议成果/任务书7执行/相位离线与认证范围.md','求解器/会议成果/任务书7执行/仓库接收与循环对应.md']
for n in protected:
 p=R/n; check('输入原字节保持: '+n,digest(p)==before[str(p)]['sha256'])
registry=(S/'选择点参数轴.md').read_text(); model=(S/'受限模型声明.md').read_text(); inp=(S/'内核输入.md').read_text()
def rows(s):
 out={}
 for line in s.splitlines():
  m=re.match(r'^\| `([^`]+)` \| (.*) \|$',line)
  if m and m[1] in axes:
   check('表行无重复:'+m[1]+':'+str(len(out)),m[1] not in out)
   out[m[1]]=m[2].split(' | ')
 return out
rr,mr,ir=rows(registry),rows(model),rows(inp)
check('四份99轴恰集一致',len(axes)==99 and config['axis_count']==99 and set(axes)==set(rr)==set(mr)==set(ir))
for k,a in axes.items():
 check('生命周期三处一致:'+k,rr[k][1]==a['lifetime'] and a['lifetime'] in ir[k][0])
 check('配置与模型处置一致:'+k,mr[k][0]==a['disposition'] and ('`'+json.dumps(a['value'],ensure_ascii=False,separators=(',',':'))+'`') in mr[k][1])
counts=dict(Counter(a['disposition'] for a in axes.values()))
check('当前处置计数',counts=={'已定':22,'本版选值':44,'由输入全称量化':15,'超出覆盖即停':18},counts)
for k,v in [('judgment.order_scope','fixed_run_order'),('transfer.failure_cooldown','every_attempt'),('warehouse.acceptance','receivable_products'),('warehouse.acceptance_quantifier','all_candidate_and_actual_checks')]:
 check('已定字段:'+k,axes[k]['disposition']=='已定' and axes[k]['value']==v and axes[k]['lifetime']=='F')
check('固定排序F',axes['judgment.order']['lifetime']=='F')
active=['运行语义.md','选择点清单.md','选择点参数轴.md','受限模型声明.md','受限转移定义.md','内核输入.md','内核输出.md','四件前置义务对照.md']
for n in active:
 s=(S/n).read_text()
 check('当前源指纹:'+n,'d150b86b398f' in s and '31ced2a24fef' not in s)
 check('旧口径清除:'+n,not re.search(r'零传输[^\n]{0,25}(缺游戏事实|未唯一|是否启动冷却)|full_base|under_capacity|F\(global\)/U\(per_instant\)|替换稿尚未|任务2有效替换稿待汇入|§6.1—6.4史料',s))
 for label,url in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',s):
  if '://' not in url and not url.startswith('#'):
   p=(S/url.split('#')[0]).resolve()
   check('相对链接存在:'+n+':'+label,p.exists(),str(p))
trans=(S/'受限转移定义.md').read_text()
for heading in ['6.5.1','6.5.2','6.5.3','6.5.4','6.5.5','6.5.6']:
 check('仓库替换节:'+heading,('#### '+heading) in trans)
for tag in ['residual=max','min(n,C)','phase-cycle-key-v1','代表化','player_withdrawal','representative_adjustment','真实唤醒','all_candidate_and_actual_checks']:
 check('关键状态/收支条款:'+tag,tag in trans or tag in (S/'内核输出.md').read_text())
ob=(S/'四件前置义务对照.md').read_text()
check('PC-01至09逐项落地',all('| PC-%02d |'%i in ob for i in range(1,10)))
check('执行证明与史料分区','§1—7为原扫描约减及检查记录的史料' in (S/'参数扫描约减.md').read_text())

# 用旧循环对象仅作内存形状脚手架，不保存其拷贝，不刷新其正式证据。
fixture_path=R/'求解器/数据/样例/生产循环环带-周期证书-kernel.json'
old=json.loads(fixture_path.read_text()); fixture=copy.deepcopy(old)
def replace_versions(x):
 if isinstance(x,str): return x.replace('kernel-output-v3','kernel-output-v4').replace('kernel-cycle-v2','kernel-cycle-v3').replace('production-cycle-key-v1','phase-cycle-key-v1').replace('production_v1','phase_production_v1').replace('cycle-normalization-v1','cycle-normalization-v2')
 if isinstance(x,list): return [replace_versions(v) for v in x]
 if isinstance(x,dict): return {k:replace_versions(v) for k,v in x.items()}
 return x
fixture=replace_versions(fixture)
proof={'path':'synthetic-shape-proof.md','sha256':'0'*64}
def evidence(kind='production_cycle',direction='conditional_witness'):
 return {'kind':kind,'support_domain':['synthetic schema-only fixture; no game claim'], 'fixed_parameter_lifecycle':'fixed_run_order throughout', 'context_bindings':[proof], 'initial_state_coverage':{'description':'synthetic shape fixture only','exact_reachable_set_enumerated':False},'direction':direction,'review_status':'pending','proof_sources':[proof]}
def obligation(definition,status='not_claimed'):
 names=[p['allOf'][1]['properties']['condition']['const'] for p in definition['properties']['checks']['prefixItems']]
 return {'status':status,'proof_sources':[proof] if status=='proved' else [],'checks':[{'condition':n,'status':'pass' if status=='proved' else 'not_claimed','evidence':['synthetic structural fixture only']} for n in names]}
def migrate_params(params):
 merged={}
 for group in ['fixed','offline_mutable','fixedness_unproven']: merged.update(params[group]);params[group]={}
 for k,a in axes.items():
  decision=merged[k]; decision['value']=copy.deepcopy(a['value']) if a['disposition']!='由输入全称量化' else decision['value']
  group='fixed' if a['lifetime'].startswith('F') else ('offline_mutable' if a['lifetime'].startswith('O') else 'fixedness_unproven')
  params[group][k]=decision
migrate_params(fixture['parameter_point']['assignment'])
fixture['status']='cycle_found';fixture['stop']=None
fixture['evidence_scope']=evidence();fixture['environment_assumption']='仓库收得下成品。'
fixture['reading']['warehouse_acceptance']='receivable_products';fixture['reading']['acceptance_quantifier']='all_candidate_and_actual_checks'
cycle=fixture['cycle'];cycle.pop('lift');cycle['normalization']['mapping_proof']=proof
cycle['reception_scope']={'checks':'all_candidate_and_actual_checks','interval':'synthetic interval','state_coverage':'synthetic states','recovery_state_coverage':'not claimed','status':'proved','proof_sources':[proof]}
cycle['correspondence']={k:obligation(v,'proved' if k=='forward_projection' else 'not_claimed') for k,v in SCHEMA['$defs']['CycleCorrespondence']['properties'].items()}
for rate in cycle['rates']: rate['comparison']='eq'
for key in ['start_key','end_key']:
 for row in cycle[key]['product_acceptance']:row['state']='receivable_at_all_checks'
 for slot in cycle[key]['state']['inventory']:
  for content in slot['contents']:
   content['entered_at']={'residual':{'value':'0'}} if content['entered_at'] is not None else None
 for gate in cycle[key]['state']['logistics']['gate_counters']:
  gate['window_started_at']={'phase':'idle'}

cases=[]
def add(name,value,valid=True,definition=None): cases.append({'name':name,'value':copy.deepcopy(value),'valid':valid,'definition':definition})
def mutate(name,fn,valid=False,base=None):
 x=copy.deepcopy(fixture if base is None else base);fn(x);add(name,x,valid)
add('生产部分证书形状',fixture)
add('旧版本证书拒收',old,False)
mutate('环境句缺失拒收',lambda x:x.pop('environment_assumption'))
mutate('数值环境替换句拒收',lambda x:x.update(environment_assumption='成品低于80000'))
mutate('端点未满标记拒收',lambda x:x['cycle']['start_key']['product_acceptance'][0].update(state='under_capacity'))
mutate('旧lift字段拒收',lambda x:x['cycle'].update(lift=None))
mutate('两次电池替代两成品拒收',lambda x:x['cycle']['rates'].__setitem__(1,copy.deepcopy(x['cycle']['rates'][0])))
mutate('缺接收区间证明拒收',lambda x:x['cycle']['reception_scope'].update(status='unresolved'))
mutate('声称证明但前向检查未过拒收',lambda x:x['cycle']['correspondence']['forward_projection']['checks'][0].update(status='unresolved'))
mutate('固定判定值变为global拒收',lambda x:x['parameter_point']['assignment']['fixed']['judgment.order_scope'].update(value='global'))
def moved_order(x):
 p=x['parameter_point']['assignment'];p['fixedness_unproven']['judgment.order']=p['fixed'].pop('judgment.order')
mutate('固定排序放U桶拒收',moved_order)
mutate('零传输冷却停止值拒收',lambda x:x['parameter_point']['assignment']['fixed']['transfer.failure_cooldown'].update(value={'policy':'stop'}))
mutate('成熟剩余旧age编码拒收',lambda x:x['cycle']['start_key']['state']['inventory'][0]['contents'].append({'item':'源矿','quantity':{'value':'1'},'entered_at':{'age':{'value':'2'}}}))
full=copy.deepcopy(fixture);full['level']='concrete_full_cycle';full['execution_mode']='finite_concrete';full['reading']['cycle_interpretation']='concrete_base_with_withdrawal';full['evidence_scope']=evidence('concrete_full_cycle')
add('缺反向复原完整周期拒收',full,False)
full['cycle']['correspondence']['reverse_reconstruction']=obligation(SCHEMA['$defs']['CycleCorrespondence']['properties']['reverse_reconstruction'],'proved')
add('完整周期逐项材料形状',full)
mutate('完整复原漏操作精度拒收',lambda x:x['cycle']['correspondence']['reverse_reconstruction']['checks'].pop(),False,full)
bad=copy.deepcopy(full);bad['status']='counterexample';bad['evidence_scope']=evidence('concrete_full_cycle','counterexample');bad['cycle']['rates'][0]['comparison']='lt';bad['stop']={'kind':'low_rate','axis':None,'event':None,'time':None,'reason':'synthetic low rate','partial_events':[]}
add('真实反例材料形状',bad)
mutate('反例复原未过拒收',lambda x:x['cycle']['correspondence']['reverse_reconstruction']['checks'][0].update(status='unresolved'),False,bad)
diag=copy.deepcopy(fixture);diag['status']='diagnostic_cycle';diag['evidence_scope']=evidence('diagnostic','diagnostic');diag['cycle']['rates'][0]['comparison']='lt'
add('低产生产循环诊断形状',diag)
mutate('生产低产直接报真实反例拒收',lambda x:x.update(status='counterexample'),False,diag)
pc={'schema':'kernel-proof-v1','result_id':'shape-only','environment_assumption':'仓库收得下成品。','evidence_scope':evidence('conditional_local_proof','sufficient'),'fingerprints':[], 'statement':'synthetic conditional statement','proof_status':'conditional','obligations':[{'condition':'S invariant','status':'unresolved','evidence':['shape only']}],'all_reachable_cycles':obligation(SCHEMA['$defs']['ProofCertificate']['properties']['all_reachable_cycles']),'open_items':['shape validation only']}
add('直接条件证明形状',pc)
mutate('直接已证但义务未过拒收',lambda x:x.update(proof_status='proved'),False,pc)
ledger=copy.deepcopy(cycle['ledger'][0]['warehouse_ledger'])
add('仓库独立台账形状',ledger,True,'WarehouseLedger')
mixed=copy.deepcopy(ledger);mixed['player_withdrawal']=[{'item':'高容谷地电池','quantity':{'value':'1','category':'候选'},'reason':'production_representative'}]
add('数学代表调整冒充玩家拿取拒收',mixed,False,'WarehouseLedger')
mixed=copy.deepcopy(ledger);mixed['representative_adjustment']=[{'item':'高容谷地电池','quantity':{'value':'1','category':'候选'},'event':'player-1','slot':'warehouse-product'}]
add('玩家拿取冒充代表调整拒收',mixed,False,'WarehouseLedger')

node_script='''const fs=require('fs');const Ajv=require(process.argv[1]);const p=JSON.parse(fs.readFileSync(0,'utf8'));const a=new Ajv({strict:false,allErrors:true});const meta=a.validateSchema(p.schema);if(!meta){console.log(JSON.stringify({meta,errors:a.errors}));process.exit(1)}const main=a.compile(p.schema);const cache={};const results=p.cases.map(c=>{const v=c.definition?(cache[c.definition]||(cache[c.definition]=a.compile({$schema:p.schema.$schema,$defs:p.schema.$defs,$ref:'#/$defs/'+c.definition}))):main;const ok=v(c.value);return {name:c.name,expected:c.valid,actual:ok,passed:ok===c.valid,errors:ok?[]:v.errors.slice(0,4)}});console.log(JSON.stringify({meta,results}));'''
proc=subprocess.run(['node','-e',node_script,str(AJV)],input=json.dumps({'schema':SCHEMA,'cases':cases}),text=True,capture_output=True)
check('AJV执行退出0',proc.returncode==0,proc.stderr)
if proc.returncode==0:
 result=json.loads(proc.stdout);check('Draft2020-12元校验',result['meta'])
 for result_case in result['results']:
  check('schema:'+result_case['name'],result_case['passed'],{k:v for k,v in result_case.items() if k not in ['name','passed']})
else: result={'error':proc.stderr}
report={'scope':'作者规格一致性、链接、保护文件与schema正负例检查；无内核运行、无游戏证书或独立复核声明',
 'checks':checks,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks),
 'schema_case_count':len(cases),'dependencies':{str(AJV):digest(AJV),str(fixture_path):digest(fixture_path),str(S/'内核输出.schema.json'):digest(S/'内核输出.schema.json')},
 'schema_results':result,'counts':counts}
(E/'audit-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checks':len(checks),'passed':report['passed'],'failed':report['failed'],'schema_cases':len(cases),'failed_names':[x['name'] for x in checks if not x['passed']]},ensure_ascii=False))
sys.exit(1 if report['failed'] else 0)
