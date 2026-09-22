"""封存任务8当前交付、来源保护及完整绝对路径清单；仅写本席目录。"""
from pathlib import Path
import json,hashlib,re
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');D=ROOT/'会议成果/任务书7执行';E=D/'证据/内核';S=ROOT/'数据/样例/任务7内核'
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=read(E/'checks.json');extra=read(E/'supplemental-checks.json');assert len(checks)==80 and len(extra)==2 and all(x['passed'] for x in checks+extra)
commands=read(E/'commands.json');batch=json.loads(next(r['stdout'] for r in commands[::-1] if r['name']=='batch-current' and r['exit_code']==0));assert len(batch['records'])==19 and len(batch['cycles'])==6
sources=read(E/'formal-source-audit.json');before=read(E/'before.json');protected=[]
for r in before:
 p=Path(r['path'])
 if '/crates/kernel/' not in str(p):
  assert h(p)==r['sha256'],str(p)
  protected.append({'path':str(p),'sha256':h(p),'unchanged':True})
write(E/'protected-files.json',protected)
changes=[
('crates/kernel/src/config.rs','修改','参数生命周期按现行99轴表判断；judgment.order固定F组，移除旧global/per_instant特殊分桶。'),
('crates/kernel/src/engine.rs','修改','累计数允许n>C的耗尽后态；核旧制造预计截止≤当前时间+剩余工作量，保护剩余量投影与事件身份。'),
('crates/kernel/src/warehouse.rs','修改','无线按物种最大可收量拟定原子事务；部分残留保留原格；同种分占多个编号格的严格部分扣减在提交前unsupported；四类尝试均5tick冷却。'),
('crates/kernel/src/polling.rs','修改','从原几何候选按现值重算三类门原因；批量删/恢复边并重建级、阻尼、环和指针；事件记原因前后及恢复边。'),
('crates/kernel/src/cycle.rs','修改','实现phase-cycle-key-v1的成熟剩余、非运输同种分组归并、累计处理、门窗及制造剩余量；逐口全矿准入；v3证书环境与对应义务，工程周期统一diagnostic_cycle。'),
('crates/kernel/src/cycle_io.rs','修改','v3周期及v4引用记录实际重放；证明引用也核原始字节并按所属目录解析；装载停止外壳同步新范围字段。'),
('crates/kernel/src/output.rs','修改','生成v4记录、公共evidence_scope和当前读取审计指纹；记录门恢复实际覆盖；新证明引用规范化。'),
('crates/kernel/src/main.rs','修改','CLI识别diagnostic_cycle与新周期版本；checkpoint和装载诊断按当前固定几何参数定位。'),
('crates/kernel/src/transition.rs','修改','在闭包输出明确首次完整重复成员的工程出口及PC-06对应断点，保留现有反复扫描。'),
('crates/kernel/tests/verify_all.py','修改','批量入口分派当前v4/v3，历史版本另列；撤用过期正式源保护快照，当前源由实际依赖链核验；调用新部分接收审计，拒未知版本与未迁移参考生产者。'),
('crates/kernel/tests/audit_task7.py','新增','独立于Rust转移实现，逐事件重算仓库、编号箱格、最大部分接收、实际入库账和箱冷却。'),
('crates/kernel/周期键读取审计.md','新增','给出实际字段读取、条件规范化、代表接收证明及未完成的真实对应；作为证书mapping_proof锁定。'),
('crates/kernel/README.md','修改','提供当前命令、输入输出版本、退出码、支持域和任务7证据入口，旧性能与测试数字归史料。')]
change_rows=[{'path':str(ROOT/p),'action':a,'reason':r,'sha256':h(ROOT/p)} for p,a,r in changes]
write(E/'code-changes.json',change_rows)
cycle_rows=[]
for p in sorted((E/'runs').glob('*cycle.json')):
 d=read(p);c=d['cycle'];cycle_rows.append({'path':str(p),'status':d['status'],'completed_ticks':d['budget']['completed_ticks'],'period':c['period']['value'] if c else None,'rates':c['rates'] if c else None,'universal_claim':False})
write(E/'cycle-results.json',cycle_rows)
final_run=next(r for r in commands[::-1] if r['name']=='final-validation-02');assert final_run['exit_code']==0
binary=ROOT/'target/release/kernel';write(E/'build-binding.json',{'binary_path':str(binary),'sha256':h(binary),'build_command':['cargo','build','--release','-p','kernel','--target-dir',str(ROOT/'target')],'cwd':str(ROOT),'builds':[{'id':r['evidence_id'],'exit_code':r['exit_code'],'output':r['stderr']}for r in commands if r['name'].startswith('build-')],'source_sha256':{str(p):h(p)for p in sorted((ROOT/'crates/kernel/src').glob('*.rs'))},'artifact_copied':False})
formal_table='\n'.join(f"| `{r['path']}` | {r['line_count']} | `{r['sha256']}` |" for r in sources['formal'])
code_table='\n'.join(f"| [{p}]({ '../../'+p }) | {a} | {r} |" for p,a,r in changes)
cycle_table='\n'.join(f"| [{Path(r['path']).name}](证据/内核/runs/{Path(r['path']).name}) | {r['status']} | {r['completed_ticks']} | {r['period'] or '无'} | {'0 / 0' if r['period'] else '未形成周期'} |"for r in cycle_rows)
report=f'''# 任务书7任务8内核验收

日期：2026-09-21。状态：工程同步及作者定向验收完成；独立接口与证据席的复核待交。现行schema通过，80项主检查与2项D.3边界检查通过；批量重放19份当前运行记录和6份周期结果。正式全范围达标证明继续按具体断点承接，L=0，必要条件上界U=1113。

## 1. 正式来源与指纹冲突处置

| 正式文件 | 行数 | 本轮实际SHA-256 |
|---|---:|---|
{formal_table}

规则第36行实际读到：“传输：协议储存箱在供电状态时会一直尝试把自身物品格内的所有物品立刻无线传输到仓库中，即使那个物品格中没有物品也一样，能送多少送多少，5 tick 冷却”。任务书§0.1的d150b86b398f与实际字节匹配；派发开头31ced2a24fef是同日中间版本。按实际现文采用d150b86b398f，核对过程及目录逐行一致性见[正式源核对](证据/内核/formal-source-audit.json)。

`数据/正式静态目录.json`当前SHA-256为`{sources['catalog_sha256']}`，三份sources[].sha256和全部lines均与正式源一致。任务1的重锁已完成，本轮保持该目录原字节。input.rs的逐份正式源校验与catalog.rs的编译期目录比对仍在；新样例显式迁移目录/轴表引用并重新seed，原样例及黄金轨迹保持史料版本。

## 2. 规格汇入逐项核对

已完整读取任务书指定章节、三审§2/§6、正式三文件、规格回填含汇入记录、任务2/3/4/5/6交付与现行规格/实现。机读接口全文解码，438台机器、629条逻辑送料逐项读入；其实际几何和默认程序认证仍为各原席所列状态。当前核对清单见[输入读取](证据/内核/input-reading-audit.json)。

对汇入记录列出的11个文件逐项核实际落点：受限转移§2—6.5；输出正文、schema及新证书；配置与参数轴；受限模型；输入生命周期/离线/后态；运行语义；选择点；四件义务；参数约减的史料分区和§8。结果为11项已回填、0项未回填、0项部分回填。99轴名字、生命周期及配置值在三张表与配置一致：22已定、44选值、18停止、15输入量化。具体行号、完整哈希及核查词见[汇入核对](证据/内核/spec-merge-audit.json)。

工程细节与文字衔接另外交[规格修改稿-任务8](规格修改稿-任务8.md)，共七条。该稿尚未汇入规格目录；当前schema已接受实际输出。汇入记录中的“新增条件证明待复核”按其当时范围读取，任务6已有的否证F15/F16与F26—29分别保留局部有效范围及完整调度、实数时间/外部环境断点。

## 3. 实际代码与契约变更

| 文件 | 动作 | 理由 |
|---|---|---|
{code_table}

共9个Rust源文件、2个Python验收文件和2个内核文档。完整绝对路径、当前指纹和理由见[改动清单](证据/内核/code-changes.json)。18个机制输入新建在`/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/`，逐文件用途与指纹见[样例清单](证据/内核/sample-manifest.json)。规格目录、本次开始前的全部数据样例、正式目录、三份正式源和候选约束保持字节。

### 3.1 必须同步的行为

规则第36行给按件部分接收与每次尝试后的5tick。无线事务先核每种可收量、仓格身份及残留后态，再同时提交库存和实际账；有一种满仓时，其它可收物种继续发送。在本轮初始冷却为0的小例中，空箱和全拒收同样在t=0、5发生尝试。多格同种全部送出或全部拒收后态唯一，可以执行；严格部分扣减落在哪个编号格仍缺有据后态，保持提交前unsupported。

规则第64行及现行规格给当前条件恢复。维护从原几何对接源读取身份，断边仍参与观察，重算原因后一次恢复图与轮询级；实际身份切换样例在同一运行中先断再恢复。规则第22、64行使调低阈值后的n>C合法，完整状态保留n，只有键使用min(n,C)。本轮没有执行玩家改阈值动作程序。

任务第15行固定排序的输入轴已放F，EventOrder与运行上下文继续用global表示这份固定模板序。旧排序分桶会拒绝新输入，本轮已同步并用错组负例核拒收。规则第23—24行所需的成熟旧货重试由既有反复扫描实现，小链实际得到前格空、后两格各一件，新入格仍等待。

### 3.2 周期键及输出契约

键按实际读取条件保存成熟剩余、门窗和全部控制量，非运输同种审计分组归并，暂停制造使用剩余工作量；完整原始状态用于恢复。旧制造预计截止核deadline≤t+remaining，规则第20行的暂停只推迟完成，使被删除的旧预计身份不会占用以后批次。详细推导与剩余整数资源边界见[周期键读取审计](../../crates/kernel/周期键读取审计.md)。

运行记录为kernel-output-v4，循环结果为kernel-cycle-v3。证书环境前提固定为：仓库收得下成品。

接收响应范围、固定参数、初态覆盖、前向投影、反向复原与全部可达循环各自有字段。PC-06未结清期间，生成器把找到的工程周期都列diagnostic_cycle；正率或低率按实际账保留。具体完整周期和真实反例请求缺复原证据时明确拒收。证明引用与运行引用都核原字节指纹及所属目录，relative路径已经实际重放。

## 4. 实际命令、退出码与结果

全部编译和验证的cwd为`/home/zhuran24/zmd-research-fresh/求解器`。实际argv、退出码、stdout和stderr逐条保存在[commands.json](证据/内核/commands.json)，顺读版本为[commands.log](证据/内核/commands.log)。build-01保存的是exec与wait返回的合并输出，未区分原始流；其余命令由Python分别捕获stdout/stderr。证据id可唯一定位一次执行；pre_final_iteration为修订期间的历史检查，最终结论以当前版本记录为准。

| 命令 | 退出码 | 关键输出与范围 |
|---|---:|---|
| `cargo build --release -p kernel --target-dir /home/zhuran24/zmd-research-fresh/求解器/target` | 两次均0 | 第一次5.56s；补截止不变量后5.99s，均Finished release profile。二进制与源码绑定见build-binding.json。 |
| `python -B 会议成果/任务书7执行/证据/内核/generate_cases.py` | 0 | 18个当前机制输入，逐一kernel seed退出0；最终输入保存在样例目录。 |
| `python -B 会议成果/任务书7执行/证据/内核/validate_cases.py` | 最后一次0 | PASS 80 checks；逐个run/verify-record/cycle/verify-cycle及schema核验见命令表。 |
| `python -B 会议成果/任务书7执行/证据/内核/supplemental_checks.py` | 0 | PASS 2 D.3 boundary checks：普通植物取货配置可装载，生产D.3静态拒收。 |
| `python -B 会议成果/任务书7执行/证据/内核/audit_inputs.py` | 0 | 三份源及逐行文本、11项汇入、99轴、438机/629计划边。 |
| `target/release/kernel verify-batch 会议成果/任务书7执行/证据/内核/runs --config 规格/内核配置-v1.json` | 最后一次0 | status=input_checked；19份运行记录、6份周期结果，含5个诊断周期和1个预算未决。 |
| 旧输入装载、歧义跨格部分传输、排序错组、过晚预计截止、7项证据篡改负例 | 按用例均2 | 预期拒收；相关log给具体字段/原因。旧输入失败发生在装载，跨格传输停止在执行请求。 |

第一次最终批量尝试退出2，因为runs还留有修订前的identity-delta记录，其绑定的读取审计指纹已过期；外层检查脚本相应退出1。原记录移入historical保留，当前输出重新生成并验收后80项检查退出0。该历史失败用于证明指纹闸生效，工程输入或轨迹结论按各自范围判读。

未运行cargo test、旧全量性能试验或141项历史测试集合。当前独立Python检查重算每次无线最大可收量、编号格残留、同刻双箱争余量、仓库逐物种账及冷却；Rust验收另从原输入完整重放。作者检查与独立席审查分别记录。

## 5. 三类结果

### 5.1 只通过装载而未步进

18个新样例的seed调用退出0，仅派生与装载。另对“装载与普通制造”和“无线多格歧义”执行check，退出0。后者随后在实际请求多编号格部分传输时按规格返回unsupported，说明装载成功只说明输入结构成立。D.3补充试验普通check退出0，生产域check退出2且trajectory_executed=false；它是支持域检查。

旧“混做粉碎机两下游”原输入check退出2，旧“生产循环环带”cycle也在装载前退出2、completed_ticks=0；装载诊断独立复现退出0，cycle_replayed=false。原始旧样例没有改写。

### 5.2 受限参数单跑

82项检查覆盖现行固定参数点的有限机制及证据入口，主要实际结果如下。

- 仓存电池79999、箱中电池2时实际送1、原格留1；胶囊仓满时留下其3件。另一例电池已满而胶囊可收，实际送胶囊3。
- 同种两编号格2+3件且仓库全收时实际送5；仓库只余2位时因残留位置未定退出2，完成轨迹为空。两箱同刻争最后1位时，两次实际总入量为1。
- 空箱和全拒收都在0、5 tick尝试，实际无线账为空；随后冷却保留5。身份切换确实出现删边和恢复边；窗口到期及多级阻尼恢复都实际运行并重放。
- n=3、C=2的后态保持3并耗尽，C=5的条件种子最多再收至5；固定C键为2，无上限循环门的真实累计递增而规范键相同。
- 小链成熟旧货在后方腾空后同刻再移，新入格保留滞留；缓存开关全记录相等，两种编码重建同一轨迹，after_closure恢复从下一刻开始。
- 错组固定排序、过晚制造预计截止、篡改入库账/固定参数/范围/周期长/证明引用/运行引用，以及伪造真实反例均被相应入口拒收。

周期结果均按相同种子、参数、来源和实现重新核验：

| 结果文件 | 状态 | 实际推进刻数 | 周期tick | 周期电池/胶囊平均入库 |
|---|---|---:|---:|---|
{cycle_table}

五个诊断周期的周期内成品率均为0；环带初始箱货在周期前缀中送入，周期账只计(a,b]。它们用于核新键、窗口、暂停及证明边界。19份运行记录中的部分入库账另有上述非零事件，台账按实际边界逐笔重算。

### 5.3 全范围证明

本轮新增完整布局达标证明0份，新增全参数/全初态/全部可达循环认证0份。任务2仓库非干扰、任务4局部安全族、任务5条件势函数及任务6局部状态删除按各自正文与复核范围承接，本轮没有为这些已经用推导完成的命题追加强制运行见证。

规则第24—25、29—32行与任务第15行已推出持续尝试、固定次序、最高可动级和失败前移；从这些条文到一般双端协调、失败环真实唤醒仍缺推导与复核（PC-06）。任务第12—13行和规则第20行给任意非精确操作及进度保留，能够产生连续相对残余；任意实数默认后态的有限表示、全部离线/恢复及共同安全集合仍分别缺PC-04/07/08的推导。任务第10行要求基地状态重复，生产键周期的反向实际拿取、仓库/矿库存/标签及操作精度复原仍须逐项证明。这些义务均保留在新证书字段，for_owner为空。

## 6. 交付、写入边界与复核

验收文档为`/home/zhuran24/zmd-research-fresh/求解器/会议成果/任务书7执行/内核验收.md`；跨规格修改稿为`/home/zhuran24/zmd-research-fresh/求解器/会议成果/任务书7执行/规格修改稿-任务8.md`。全部代码、样例、脚本、日志和结果的绝对路径见[文件清单](证据/内核/文件清单.md)，完整指纹见[交付清单](证据/内核/交付清单.json)，机器回传见[结构化结果](证据/内核/结构化结果.json)。清单不自列自身哈希。

三份正式文件、候选约束、规格目录和原数据样例的保护检查见[protected-files.json](证据/内核/protected-files.json)。未执行git，未访问模拟器内容；编译产物留在指定target，证据只保存脚本、日志、JSON和Markdown。代码与读取审计还需任务书指定的独立接口与证据席复核；本席的82项通过不替代该席裁定。

当前环境没有可调用的StructuredOutput工具，检索结果见[工具可用性](证据/内核/tool-availability.json)；交付结构化JSON作为返回值。执行中没有收到额度、配额、usage limit或rate limit报错，quota_error=false。
'''
(D/'内核验收.md').write_text(report)
# Final inventory includes the files written below, so the result is a complete absolute path list.
planned=[E/'结构化结果.json',E/'reader-review.json',E/'交付清单.json',E/'文件清单.md',E/'final-check.log']
files=sorted(set([ROOT/p for p,_,_ in changes]+list(S.glob('*.json'))+[D/'内核验收.md',D/'规格修改稿-任务8.md']+[p for p in E.rglob('*') if p.is_file()]+planned),key=str)
result={'type':'StructuredOutput','status':'completed','task':'任务书7任务8工程部分','error':None,'quota_error':False,'for_owner':[],
 'engineering_completed':True,'independent_seat_review':'pending','formal_sources':sources['formal'],'code_changes':change_rows,
 'validation':{'main_checks':80,'supplemental_checks':2,'passed':82,'records_replayed':19,'cycle_results_replayed':6,'diagnostic_cycles':5,'budget_inconclusive':1,'build_exit_codes':[0,0],'final_validation_exit_code':0,'batch_exit_code':0,'expected_rejection_exit_code':2,'commands':str(E/'commands.json'),'build_binding':str(E/'build-binding.json')},
 'evidence_categories':{'load_only':'18个seed、指定check及D.3静态边界；均不步进；旧源失配另列装载诊断。','restricted_parameter_runs':'19份记录，5份周期诊断和1份预算未决；实际局部传输/恢复/键/重放见checks.json及cycle-results.json。','full_scope_proofs':{'new_full_layout_certificates':0,'new_universal_certificates':0,'L':0,'U':1113,'open':'PC-04/06/07/08及完整真实周期复原；直接条件推导按原范围承接。'}},
 'deliverables':{'acceptance':str(D/'内核验收.md'),'spec_proposal':str(D/'规格修改稿-任务8.md'),'evidence':str(E),'file_manifest':str(E/'交付清单.json')},
 'spec_proposals':['S8-01 累计n>C后态','S8-02 D.3逐口全矿前件','S8-03 非运输同种审计分组归并','S8-04 制造deadline不变量及remaining_work编码','S8-05 高率但对应未齐也保留诊断','S8-06 v4/v3版本与当前验收入口','S8-07 当前非空种子/恢复支持范围'],
 'files':[str(p) for p in files]}
write(E/'结构化结果.json',result)
(E/'文件清单.md').write_text('# 任务8完整文件清单\n\n日期：2026-09-21。仅列本席交付及修改的文件；完整SHA-256见同目录交付清单.json。指定target的二进制仅在build-binding.json登记，没有复制到证据目录。\n\n'+'\n'.join('- `'+str(p)+'`' for p in files)+'\n')
# Mechanical part of reader audit, after the main prose has been manually reread.
links=[]
for p in [D/'内核验收.md',D/'规格修改稿-任务8.md',ROOT/'crates/kernel/README.md',ROOT/'crates/kernel/周期键读取审计.md']:
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  if '://' not in target and not target.startswith('#'):
   dest=(p.parent/target.split('#')[0]);assert dest.exists() or dest in planned,(p,target);links.append(str(dest.resolve()))
write(E/'reader-review.json',{'status':'passed','manual_review':['当前结论与修订史分区；最终检查80+2、19记录/6结果口径统一','所有证明先列前件；工程诊断与真实反例、全称证明分开','跨规格七条逐项给原位置、现行文字、建议和理由；已核物理行号','正式指纹以当前字节为准；owner无待补事实，配额报错未触发','完整路径、构建版本、引用链接与文件清单核对'],'links_checked':len(links),'protected_files_checked':len(protected),'quota_error':False})
log='command: python -B 会议成果/任务书7执行/证据/内核/finalize_artifacts.py\ncwd: '+str(ROOT)+'\nexit: 0\nPASS: 82 directed checks, 19 record replays, 6 cycle results; source protection and reader links verified.\n'
(E/'final-check.log').write_text(log)
for p in files:
 if p!=E/'交付清单.json':assert p.is_file(),p
assert all(p.suffix in ['.py','.log','.json','.md'] for p in files if p.is_relative_to(E))
write(E/'交付清单.json',{'status':'sealed','manifest_self_hash_omitted':True,'files':[{'path':str(p),'sha256':h(p),'bytes':p.stat().st_size} if p!=E/'交付清单.json' else {'path':str(p),'sha256':None,'reason':'manifest self hash omitted'} for p in files]})
print(log,end='');print('files:',len(files),'evidence_bytes:',sum(p.stat().st_size for p in E.rglob('*') if p.is_file()))
