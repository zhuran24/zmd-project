from pathlib import Path
import json,hashlib,datetime
R=Path('/home/zhuran24/zmd-research-fresh'); W=R/'求解器'; D=W/'会议成果/任务书7执行'; E=D/'证据/规格'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,obj):(E/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
check=json.loads((E/'self-check.json').read_text()); assert check['status']=='passed'
commands=json.loads((E/'commands.json').read_text()); src=json.loads((E/'source-relock.json').read_text())
formal=[R/x for x in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']]
owner=[{'id':'BOX-ZERO-COOLDOWN','kind':'缺游戏事实','basis':'规则L36“能送多少送多少，5 tick 冷却”；合用L20、L25及约束L8、L80。','deduction_end':'有货传输后的箱级5 tick冷却已定；现文删除空格也尝试的专句，空箱或全拒收、实际送入0件是否启动冷却仍无唯一结论。','needed_fact':'零传输时是否启动新的5 tick冷却；相位全取值义务保留。'}]
save('for-owner.json',owner)
# Engineering records, with scope, are kept apart from current rule statements.
(E/'执行说明.md').write_text('''# 规格回填执行记录

日期：2026-09-21。范围：源指纹、规格/配置/schema回填及一个样例的装载验证。

关键命令、cwd、退出码和完整stdout/stderr见commands.json与三个同名日志；源文件sha256sum原始输出见sha256sum.json。首次构建实际编译kernel，输出为`Compiling kernel v0.1.0`和`Finished release profile [optimized] target(s) in 5.40s`；文字自审修改轴表说明后重跑相同命令，最终日志为增量构建0.01s，退出码均0。最终装载证据以load-verification.json锁定的版本为准。

backfill_specs.py首次在冗余替换断言处退出1，未写规格；删去重复要求后完成九份规格写入。polish_contracts.py首次因重复标点替换断言退出1，先前两个文件的修正已写入；改为幂等替换后继续完成，最终文件由manifest.json及自核锁定。这两项属于编写脚本的字符串定位错误。

audit_backfill.py最初因`ModuleNotFoundError: No module named 'jsonschema'`退出1。最终用标准库解析schema，并将五处删除的枚举加回，核恢复字节SHA-256等于修改前值，证明schema改动只限五处枚举删除；没有声称运行第三方JSON Schema元模式验证。最终39项自核通过。

没有遇到OpenAI/Codex额度、配额、usage limit或rate limit错误。

未运行git；未改三份正式文件、候选约束、推导正文或Rust源码；模拟器未访问。编译产物只在指定target中；证据目录只保留脚本、日志、JSON和Markdown，target产物仅以路径/哈希登记。
''')
rows=[
('正式源与目录文本','运行语义原§1 L11—12；正式静态目录.json sources[].sha256/lines、task.conditions、箱transfer','三份正式源完整哈希；任务L9、L12—16；规则L36','同步三份逐行文本与哈希；补拿取条目及调试原文；约束126行逐行相同；箱级冷却与部分传输写入派生说明','旧证据/样例的来源链须由任务8重新生成或维持史料身份'),
('实际尝试失败后前移','选择点T3；参数轴及配置polling.both_failure；受限转移§3.3','规则L29“尝试后立刻传给下一条”、L30；v46 S-D05','实际尝试后的前移列已定，撤去失败后保持/成功才转备选；保留最高可移动级筛选','任务6核双端怎样构成一次尝试、参与侧、空转终止和同刻继续推进；both协调仍为工程定义'),
('正常5 tick窗口','选择点T8；gate.window_clock/window_recovery；转移§2.1/§3.4','规则L64；v46 S-D04、N-F19','首件起窗、走满后由下一件重起已定；清窗口计数、保留全时段累计；撤身份阻断停表备选','任务6核同刻维护、恢复事件与轮询/阻尼衔接'),
('同一门只改阈值','选择点T9；gate.counter_edit；内核输入§4/§6.1','规则L22、L64；任务L12—13；v46 N-F19','累计n保留；C>n解除累计耗尽，C<=n继续用尽；计数变化与实际调试动作分别记录','改身份、另行处理历史状态、拆建、窗口后果与实际送达归任务5/6；动作回放归任务8'),
('按现值解除阻断','选择点T8；gate.identity_recovery/total_recovery；转移§2.2/§3.4','规则L16、L22、L64；v46 N-F19','身份、累计与窗口按现值判断；全部原因消失恢复资格；撤永久锁存读法','任务6补观察和恢复事件；任务8替换旧Rust锁存代码；实际移动仍核容量、滞留和权限'),
('任意调试操作','选择点T11；initialization.debug_actions/cancel_limit/belt_shape_lifecycle；内核输入§3.2/§6.1','任务L12任意操作、L13精度、L8—9零干预与拿取；规则L10—11、L22','拆建、增建、清理、手工放料、改设定/取消限额均获准；unsupported只登记工具缺回放','任务5/6给实际收支、几何/进度后果和全部调试后态；任务8补尚缺动作编码'),
('默认堵满起法','运行语义§5；选择点T11；initialization.other_inventory；输入§6.1','任务书7 §0.1；主会话三审 §6；任务L12—13','关机、送料填满带和存货格、上游每台做一批停缓存、末级最后开作为默认程序','任务5证明后态集合与放开后的过程；合成全空样例仅作工程校验'),
('角点不成通道','运行语义原§2.1 L39；T5；connection.port_meeting；输入§2.2；输出/schema','规则L12、L16；约束L28、L94、L100、L123；owner 09-21三审§6','共边相遇列fixed/F已定，撤角点候选与覆盖损失；schema五处枚举同步','桥先接平局及互依赖仍缺相应历史推导；传送带元件连续关系另属规则L26'),
('箱体传输与冷却','选择点T6；transfer.*；转移原§4.3；输出§2.0；目录箱transfer','规则L25、L36“能送多少送多少”、L13、L41、L72；三审§6','箱级5 tick冷却已定；按每种余量尽量送，余货留箱，台账记实际入量；撤整箱全收守卫','零传输冷却列for_owner；残留格、同刻组织缺任务6推导；部分接收和停止边界缺任务8实现'),
('周期证书及旧证明去向','运行语义§5；T12；受限转移旧§5、§6.1—6.5；warehouse.periodic_lift；内核输出','任务L2、L8—10、L13；规则L14、L36、L41、L73；三审§2.4、§6','旧级二名目撤下；环境前提为“仓库收得下成品”；成品分别记I−O−P；旧算法证明分区标史料，§6.5改为交接义务','任务2/6有效替换稿尚未收到，完整循环对应继续待证；任务8同步证书和实现'),
('现行行号与实现支持','九份规格全部入口及配置；内核输入§5参数镜像','任务现行9/10/11/12/13/14/15/16行；三份现行源','现行条款引用同步，历史证明注明旧行号映射；99轴名单、生命周期、配置和输入镜像一致','独立复核尚未进行；历史参数投影及黄金记录由任务8迁移'),
('另一处现行指纹登记','数据/样例/check_examples.py原L58—62的SOURCE_HASHES，使用点L720、L734—735','三份正式文件当前完整SHA-256；任务1“登记处不止一处全部同步”','仅改规则、任务两个哈希字面量；约束哈希及算法保持','该脚本依赖的旧样例和投影尚未重生成；本次未运行其全套历史回归'),
]
report='''# 规格回填

日期：2026-09-21。状态：任务书7任务1规则回填完成。完成范围为现行规则、选择点、契约、配置和正式源登记；编译及一个样例的seed装载验证通过。完整运行语义、循环对应和全称达标认证仍由后续任务承担。L=0、U=1113保持任务书起点。

## 1. 依据与证据层级

已读任务书7的§0、§1.1、§2规格席一行、§3、§4，三审§2/§6，三份正式文件及现有规格入口，并回核v46 S-D04、S-D05、N-F19、N-F39、N-F42和总结的工作纪律。owner 09-21角点、箱体传输和默认起法裁定按现行范围回填。历史工作报告和验证文件按当时版本读取。下文未带目录的证据文件名均相对[证据/规格](证据/规格/)。

| 正式文件 | 行数 | 本次核验完整SHA-256 |
|---|---:|---|
'''
for p in formal:report+=f'| `{p}` | {len(p.read_text().splitlines())} | `{h(p)}` |\n'
report+='''
条文事实已回填；正式约束按自身前件承接；本次没有新充分证明、完整布局见证或L/U改进。仓库79999件、箱中2件的例子只核部分接收的局部算术。seed与check是输入装载证据，轨迹步数为0；39项自核属于作者检查，独立复核仍待执行。

## 2. 逐项处置

“原位置”以修改前文件的节/字段定位，原始字节哈希见before.json，逐项差异见spec-changes.json、polish-changes.json、reader-fixes.json及secondary-registry.json。

| 项目 | 原位置 | 现行依据 | 最终处置 | 仍缺的后效 |
|---|---|---|---|---|
'''
for row in rows:report+='| '+' | '.join(row)+' |\n'
report+='''
## 3. 指纹链、装载与同步范围

正式静态目录的sources[].sha256与lines逐份同步，task.goal/conditions从现行任务全文转录；任务12行重复字保留。约束哈希和126行内容均一致。箱transfer.cooldown_scope和说明随规则回填。目录最终SHA-256为`'''+h(W/'数据/正式静态目录.json')+'''`。

装载链实核如下：input.rs的reference()检查样例所引目录字节哈希；Catalog::load比较解析后的serde_json::Value与编译期include_str目录；input.rs L357逐份核正式源哈希。第二层检查的是JSON值相等，原始字节哈希由第一层保障。config.rs也在编译期读取当前配置。topology/src/lib.rs包含同一路径目录，未另存一套源哈希；本次按任务要求只编译kernel，topology旧二进制不作本次验收。

另一处现行登记为数据/样例/check_examples.py的SOURCE_HASHES，已同步两个过期字面量。候选B/来源清单.json、kernel/evidence/baseline.json及复核目录中的baseline是旧证据的版本记录，保持原样。全目录扫描仍含旧规则哈希1063个文件、旧任务哈希1040个文件、旧目录哈希1619个文件；这些计数可以重叠，清单见historical-references.json。其中包括原样例、参数投影、黄金结果、复核快照及旧脚本；后续执行须重建依赖并重验，不能只换哈希沿用通过结果。

验证输入由数据/样例/混做粉碎机两下游.json派生到证据/规格/装载样例.json，仅改引用路径/哈希、当前配置值/生命周期及种子中的参数镜像，保留原几何、设定、库存和历史。该小例无箱、无准入口、无调试动作；原样例和其黄金结果未改。sample-migration.json列全部变更JSON路径，load-verification.json锁定输入、派生结果、目录、配置、轴表和二进制完整哈希。

额外文件修改已声明：①内核输出.schema.json只删除五处closed_segment_touch枚举，恢复这五处后能得到原字节哈希；②check_examples.py只更新SOURCE_HASHES的两个哈希。前者落实已定几何入口，后者同步实际执行的源登记。未修改Rust源码、推导正文或原样例；三份正式文件及候选约束字节保持，模拟器未访问，无git操作。

## 4. 命令与实际结果

以下命令cwd均为`/home/zhuran24/zmd-research-fresh/求解器`，完整stdout/stderr见commands.json及相应日志。

'''
for c in commands:
 report+='```bash\n'+c['command']+'\n```\n\n退出码：`'+str(c['exit_code'])+'`。输出：\n\n```text\n'+(c['stdout']+c['stderr']).strip()+'\n```\n\n'
report+='''seed的命令行摘要显示status=null，是因为成功返回的对象为kernel-input-v3而不含status字段；退出码0、seed-output.json的schema及后续check的input_checked共同确认成功。main.rs的seed分支调用Input::canonicalize_seed，没有调用step。该结果证明新目录、正式源和参数依赖已装载，不验证部分接收或门恢复的运行后果。

自核命令（cwd为仓库根）：

```bash
python -B 求解器/会议成果/任务书7执行/证据/规格/audit_backfill.py
```

退出码0；39项通过。覆盖三份哈希与逐行文本、task派生内容、99轴恰集与生命周期、已定值、旧禁令/旧指纹扫描及故意注入的旧条款识别、schema五处局部改动、装载证据版本匹配、现行第二登记和受保护文件。JSON Schema第三方验证库未安装；本次只做JSON解析和严格局部差异核对，未声称全模式验证。完整执行记录见证据/规格/执行说明.md。

## 5. 后续交接与for_owner

任务2：提交仓库接收与循环对应的有效替换稿，连同标签、空格序、实际接收边界和每种成品I−O−P账。任务5：核默认堵满程序的全部后置状态与放开过程。任务6：核双端尝试、失败空转、同刻推进、准入口恢复事件、箱内残留格及必要的时间/参数覆盖。任务8：同步Rust部分接收与条件恢复、落实未定义后效的停止、更新旧样例/参数投影/证书，并重做受影响验证。

for_owner仅一项（缺游戏事实）：规则L36“能送多少送多少，5 tick 冷却”；合用L20、L25及约束L8、L80，有货传输的箱级5 tick冷却已定。\n现文删除空格也尝试的专句，空箱或全拒收、实际送入0件时，是否启动新的5 tick冷却仍无唯一结论。\n所需补充为零传输冷却的触发条件；相位全取值义务保持。机器可读条目见for-owner.json。

重建自动物品去向只影响依赖其自动结果的方案；明确清理再拆建可绕开，默认程序不依赖它，本次for_owner不另列。双端协调、后置状态、残留格和循环对应列缺推导/复核，不转交owner代证。

## 6. 读者自审与文件清单

已按独立读者顺序核对：当前结论与旧史料分区、头部状态与实际结果一致、原位置/现行依据/最终处置/仍缺后效四栏齐全、任务行号与史料行号映射明确、交叉引用存在、样例装载与行为验收范围分明。自审修正了冷却旧选值、调试权限、角点schema、旧周期层级、重复用语和唯一后继的过宽表述。独立复核仍待安排。

本次新建/修改的全部交付与支持文件（绝对路径）见下列清单；完整SHA-256见manifest.json。指定target内本轮时段更新的17个构建文件另列build-products.json，仅登记路径/哈希，未复制进证据目录。

'''
# Enumerate every authored artifact, including this generation script and the upcoming manifest/build inventory.
specs=[W/'规格'/n for n in ['运行语义.md','选择点清单.md','选择点参数轴.md','受限模型声明.md','受限转移定义.md','内核输入.md','内核输出.md','内核配置-v1.json','四件前置义务对照.md','内核输出.schema.json']]
modified=specs+[W/'数据/正式静态目录.json',W/'数据/样例/check_examples.py']
newfiles=sorted(set([p for p in E.iterdir() if p.is_file()]+[E/'manifest.json',E/'build-products.json',D/'规格回填.md']))
for p in modified+newfiles:report+='- `'+str(p)+'`\n'
(D/'规格回填.md').write_text(report)
before=json.loads((E/'before.json').read_text());start=datetime.datetime.fromisoformat(before['time']).timestamp()
build=[{'path':str(p),'sha256':h(p),'size':p.stat().st_size} for p in sorted((W/'target').rglob('*')) if p.is_file() and p.stat().st_mtime>=start]
save('build-products.json',{'scope':'mtime >= before.json time; generated or refreshed under the required build target. No copies.','files':build})
files=modified+sorted([p for p in E.iterdir() if p.is_file() and p.name!='manifest.json'])+[D/'规格回填.md']
base_hash={x['path']:x['sha256'] for x in before['files']}
for extra in ['secondary-registry.json','polish-changes.json']:
 j=json.loads((E/extra).read_text())
 for x in (j if isinstance(j,list) else [j]):
  if x['path'] not in base_hash:base_hash[x['path']]=x.get('original_sha256',x.get('before_sha256'))
save('manifest.json',{'status':'rule_backfill_completed','error':None,'scope':'任务1规则回填；非完整语义获证','files':[{'path':str(p),'action':'modified' if p in modified else 'created','sha256':h(p),'before_sha256':base_hash.get(str(p))} for p in files],'self':str(E/'manifest.json'),'self_hash_note':'manifest does not recursively hash itself','build_products':str(E/'build-products.json'),'for_owner':owner,'checks_passed':len(check['checks'])})
print(json.dumps({'status':'rule_backfill_completed','report':str(D/'规格回填.md'),'authored_files':len(files)+1,'build_files':len(build),'for_owner':len(owner)},ensure_ascii=False))
