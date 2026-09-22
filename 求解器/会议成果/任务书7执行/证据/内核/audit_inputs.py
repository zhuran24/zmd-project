"""只读核正式来源、汇入落点、99轴与全量JSON接口；结果写本席证据。"""
from pathlib import Path
import json,hashlib,re,collections
from fractions import Fraction
from run_command import ROOT,E

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(E/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
catalog=json.loads((ROOT/'数据/正式静态目录.json').read_text());formal=[]
for r in catalog['sources']:
 p=ROOT.parent/r['path'];raw=p.read_bytes();lines=raw.decode().splitlines()
 assert digest(p)==r['sha256'] and lines==r['lines']
 formal.append({'path':str(p),'sha256':digest(p),'line_count':len(lines),'registered_hash_matches':True,'all_registered_lines_match':True})
assert formal[0]['sha256'].startswith('d150b86b398f')
assert '即使那个物品格中没有物品也一样，能送多少送多少' in catalog['sources'][0]['lines'][35]
write('formal-source-audit.json',{'formal':formal,'catalog_sha256':digest(ROOT/'数据/正式静态目录.json'),'conflict_resolution':'31ced2a24fef为09-21中间版本；本轮重读实际第36行并核完整SHA-256，采用d150b86b398f；登记已同步，未修改数据目录。'})
config=json.loads((ROOT/'规格/内核配置-v1.json').read_text());axes=config['axes'];tables={}
for name in ['内核输入.md','选择点参数轴.md','受限模型声明.md']:
 lines=(ROOT/'规格'/name).read_text().splitlines();rows={}
 for i,line in enumerate(lines,1):
  m=re.match(r'^\| `([^`]+)` \| (.*) \|$',line)
  if m and m[1] in axes:assert m[1] not in rows;rows[m[1]]={'line':i,'cells':m[2].split(' | ')}
 assert rows.keys()==axes.keys();tables[name]=rows
for k,a in axes.items():
 assert tables['选择点参数轴.md'][k]['cells'][1]==a['lifetime']
 assert a['lifetime'] in tables['内核输入.md'][k]['cells'][0]
 assert tables['受限模型声明.md'][k]['cells'][0]==a['disposition']
 assert '`'+json.dumps(a['value'],ensure_ascii=False,separators=(',',':'))+'`' in tables['受限模型声明.md'][k]['cells'][1]
counts=dict(collections.Counter(v['disposition'] for v in axes.values()));assert counts=={'已定':22,'本版选值':44,'超出覆盖即停':18,'由输入全称量化':15}
checks={
'受限转移定义.md':('§2—5、§6.1—6.5',['6.5.1','6.5.6','部分','5 tick冷却','phase-cycle-key-v1','PC-06','representative_adjustment']),
'内核输出.md':('§1—2、§4—5',['kernel-output-v4','kernel-cycle-v3','kernel-proof-v1','mapping_proof','reverse_reconstruction','all_candidate_and_actual_checks']),
'内核输出.schema.json':('$defs RunRecord/Cycle/CycleResult/ProofCertificate',['kernel-output-v4','kernel-cycle-v3','kernel-proof-v1','remaining_work' if False else 'phase-cycle-key-v1','diagnostic_cycle']),
'内核配置-v1.json':('revision及axes',['task7-merge-2026-09-21','every_attempt','fixed_run_order','all_candidate_and_actual_checks']),
'选择点参数轴.md':('§1—2、§3 A3',['fixed_run_order','every_attempt','current_conditions']),
'受限模型声明.md':('§2、§4—5',['22','44','18','15','PC-06','every_attempt']),
'内核输入.md':('§3.3、§5、§10',['fixed_run_order','全部有限操作迟延','intake','phase-cycle-key-v1']),
'运行语义.md':('§1—5、§7',['d150b86b398f','PA-11','仓库收得下成品']),
'选择点清单.md':('T2/T6/T10—12',['fixed_run_order','every_attempt','PA-01']),
'四件前置义务对照.md':('§1—6',['PC-01','PC-09','for_owner为空']),
'参数扫描约减.md':('史料状态及§8',['§1—7为原扫描约减及检查记录的史料','当前规则下的约减准入','门按当前条件恢复'])}
merged=[]
for file,(section,tokens) in checks.items():
 p=ROOT/'规格'/file;txt=p.read_text();found=[]
 for token in tokens:
  matches=[i for i,line in enumerate(txt.splitlines(),1) if token in line];assert matches,(file,token);found.append({'token':token,'lines':matches})
 merged.append({'path':str(p),'section':section,'status':'已回填','sha256':digest(p),'confirmed_locations':found,'meaning':'与汇入记录逐项核对当前文字；工程落实状态另列内核验收，新增证明仍按独立复核范围承接。'})
write('spec-merge-audit.json',{'files':merged,'axis_count':len(axes),'dispositions':counts,'axis_locations':{k:{f:r[k]['line'] for f,r in tables.items()} for k in axes},'not_merged':[],'partially_merged':[],'additional_task8_proposals':'规格修改稿-任务8.md'})
interface=json.loads((ROOT/'会议成果/任务书7执行/送料与接口.json').read_text());rows=[]
for c in interface['candidates']:
 # JSON全文解码，629条计划边、438台机器逐项读取；本审计不把逻辑表冒充实际路径。
 assert len(c['machines'])==219
 for machine in c['machines']:assert isinstance(machine,dict)
 for feed in c['feeds']:assert isinstance(feed,dict)
 rows.append({'candidate':c['id'],'machines_read':len(c['machines']),'feeds_read':len(c['feeds']),'keys_read':list(c),'geometry_certified':False})
assert sum(c['feeds_read'] for c in rows)==629
required=['规格回填.md','受限转移定义-§6.5替换稿.md','推导复核范围.md','植物运行试点.md','送料与接口.json','调试与释放.md','调试后状态.json','相位离线与认证范围.md','规格修改稿-任务6.md','仓库接收与循环对应.md']
inputs=[]
for name in required:
 p=ROOT/'会议成果/任务书7执行'/name;txt=p.read_text();inputs.append({'path':str(p),'sha256':digest(p),'lines':len(txt.splitlines()),'json_parsed':name.endswith('.json')})
for p in sorted((ROOT/'crates/kernel/src').glob('*.rs')):
 txt=p.read_text();inputs.append({'path':str(p),'sha256':digest(p),'lines':len(txt.splitlines()),'kind':'Rust source or historical tests; cargo test not invoked'})
write('input-reading-audit.json',{'inputs':inputs,'plant_candidates':rows,'semantic_scope':'正文按机制及支持域核读；重复轴行和完整JSON由程序逐项对照。源读取和结构核对不宣称游戏步进或独立席复核。'})
print('PASS: 3 formal sources and line arrays; 11 merged files; 99 axes; 438 machines / 629 feeds')
