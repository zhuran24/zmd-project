"""包三执行记录：只追加本包与更新总状态；原包一/二正文保持。"""
import importlib.util,json,re
from guard import OUT,ROOT,guard,digest
from work import write
spec=importlib.util.spec_from_file_location('p3summary',OUT/'package3-summary.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s=m.summary();audit=json.loads((OUT/s['final_audit']).read_text())
results={'p3-final-build':'通过；默认dev profile','p3-final-check':'通过','p3-final-clippy':'通过，无警告','p3-final-kernel-lib':'66项通过','p3-final-topology-lib':'1项通过','p3-final-reference':'13项通过；含九例4000步差分、独立账审及schema','p3-final-validation':'30项通过','p3-final-kernel-doc':'通过，0项','p3-final-topology-doc':'通过，0项','p3-final-catalog':'三正式源全文/SHA及目录投影回源通过','p3-final-catalog-tests':'9项通过；单位1173、配方154项逐叶变异拒收','p3-candidate-report':'4924通过、0失败、80不能静态检','p3-legacy-check':'按设计只读运行；旧114行断言失败，非本轮门禁'}
rows=[]
for c in s['commands']:
 name=c['name'];rows.append(f'| [{name}]({name}.log) | `{ " ".join(c["argv"]) }` | {c["exit_code"]} | {results[name]} |')
text='''

## 包三

### 结果与边界

包三完成：候选B重锁并重生成报告，两张覆盖表逐行同步，现行规格/README重写，两份修订记录追加r30；完整安全集通过，最终run.sh audit通过，活动文件旧SHA残留0。没有Git操作；没有运行workspace测试、任何CLI测试目标、verify_all.py批量验收或内核二进制写记录命令。源码、目录、配置v2、输出schema、全部新旧输入、前两包结果均保持包三开工字节。

本节是包三实施与自核记录，不替代设计指定的独立审查席/终审席，不另写或冒充审查.md、终审.md。完整基地周期、起动可达性、全称覆盖沿用现有未证明边界，不属于本包的未交付项。

汇总：[package3-summary.json](package3-summary.json)；业务文件前后SHA：[package3-changed-paths.json](package3-changed-paths.json)；最终审计：[p3-audit03.json](p3-audit03.json)；旧SHA全仓分类：[p3-audit03-old-sha-inventory.json](p3-audit03-old-sha-inventory.json)。

### 修改文件

以下路径相对求解器；16个业务文件修改，无新增/删除业务文件。维护目录中的脚本、备份、日志、快照另计。

| 文件 | 本包内容 |
|---|---|
| `规格/运行语义.md` | 三正式源全文指纹、现行文件清单；步边界、元件/层数/次序、成功轮询、收货组、即时前挪、制造/箱/准入口；保留18配方和非时间组织的条件论证 |
| `规格/受限转移定义.md` | 一步转移、事件台账、停止/恢复、D.1—D.5、phase-cycle-key-v2、步周期及件/tick率、真实仓库对应义务 |
| `规格/受限模型声明.md`、`规格/选择点参数轴.md` | 从配置v2逐项投影66轴及处置/值/依据/损失；注明双出口桥轴本版读法、注册表遗留注释的历史范围 |
| `规格/选择点清单.md` | T1/2/3/4/8/14/16/17标规则已解决；保留T5/6/7/9/10/11/12/15及其现行边界 |
| `规格/内核输入.md`、`规格/内核输出.md` | 输入v4、状态v2、记录v5、证书v4、显式接口、步单位及恢复/核验；schema文件不改 |
| `规格/规则覆盖表.md`、`数据/规则覆盖表.md` | 115行规则、15行任务逐行回源；全部去向与数据下标更新；两表77条约束行原字节保持 |
| `数据/候选B/来源清单.json` | 刷新规则/任务/目录/候选约束四项，另外12项只读核等；16项当前SHA相符 |
| `数据/候选B/校验报告.md`、`数据/候选B/验证记录.md` | 本轮build后二进制生成的报告原字节；首段指本轮，旧验证正文不改 |
| `规格/check_revision.py` | 只把只读指纹路径改为本维护目录；旧断言不移植为新门禁 |
| `规格/修订记录.md`、`crates/kernel/修订记录.md` | 追加r30：版本、目录/配置/三源SHA、语义删改、样例历史范围与本记录链接；校准文首史料截止日期 |
| `crates/kernel/README.md` | 当前用途、版本、步进机制、接口、安全入口和认证边界 |

本轮`guard.py`只额外准许设计§8明确要求的`python3 规格/check_revision.py`；不放宽任何cargo或二进制命令。`work.py`补audit分派，实际检查在package3-audit.py；保留原始initial-history.json，不重新init。只读快照[只读文件指纹.json](只读文件指纹.json)包含三正式源与候选约束当前四份原字节。

### 规则、设计与代码现实的取舍

1. 任务书要求更新旧check_examples.py来源表，但设计§6.3/§7要求旧工具及历史样例原字节保留；沿用前两包处置，不改旧校验器。当前30份输入锁新目录/配置，step_samples.py已有现行来源表，本包逐项审计，不替旧历史产物换来源。
2. 设计§1.10写“缓存格通往存货物品格的闸”方向倒置；按正式规则L18及任务书第1节，现行规格写“存货物品格通往缓存格”，只在开工时一次进用量。未因此修改设计或前包代码。
3. 设计概述“只有分流器会有多个候选”不覆盖双出口桥轴；按规则L28及设计§1.3，对桥轴同样显式选支。桥轴多收货组按L31传递联动的本版读法另标，不把九例sim2差分当作该未共同构型的独立证明。
4. 约束节77行原样保留的要求与重编号后的旧指针并存：运行语义保留§4.2轮询及§4.3速率/H条件证明，覆盖表另说明其旧“规则L63”现为L64、已解决T编号只作追溯。H以每tick计，现行每步一次判定不是H；未把条件算术升级为现行待审机制。
5. 发现包一配置v2三处说明残留：initialization.other_inventory.coverage_loss的“关闭时intake”；warehouse.external_supply.coverage_loss的旧physical/授权读取点名称；warehouse.periodic_lift.extension_gate的旧§6.5.5。按不回头大改前包要求，配置字节不动，两张轴表仍精确投影；表后明确这些是历史说明、现行无intake且读取/完整周期接口按新转移§6。它们不恢复任何旧执行语义。
6. 旧默认起法“完成一批停在缓存”须有实际输出阻塞条件；当前关闭机器不预收缓存原料，完成批可容即出。T11与运行语义据此保留起动后置状态未证边界，没有把合成种子当可达证明。
7. 周期对应字段按当前代码实际名称forward_projection/reverse_reconstruction/all_reachable_cycles描述；状态v2是State结构版本称呼，没有虚构独立schema字段。诊断周期仍不升级为全称或完整基地周期。

### 命令与结果

以下13条命令都经`bash 内核维护/2026-09-30-步进规则同步/run.sh run <唯一名> <命令>`执行，每条之前/之后各全量哈希比对一次，计26次；所有active_diff为空。完整argv、环境、时间和退出码在[commands.jsonl](commands.jsonl)。共享CARGO_TARGET_DIR为求解器/target，默认profile、-j 4、测试线程1，无新增profile。

| 日志 | 实际命令 | 退出码 | 结果 |
|---|---|---:|---|
'''+ '\n'.join(rows)+'''

完整安全集一遍由先执行的p3-final-build及[package3-safe-suite.sh](package3-safe-suite.sh)接续十项组成，共11项全部通过；build后才运行候选B。候选报告原字节等于p3-candidate-report.log，静态80项未覆盖继续保留，没有宣称运行达标。

旧规格自查按设计§8第6步不作门禁：[p3-legacy-check.log](p3-legacy-check.log)退出1，首个失败在`规格/check_revision.py:27`，计数由第24行硬编码114（任务仍16），断言文本“《明日方舟：终末地》游戏规则.txt：114 行覆盖”；没有执行到后续旧99轴/旧章节/旧词串断言，不伪称逐条已运行。当前115/15/77、66轴及当前章节/来源锁由run.sh audit核验通过。未为让旧脚本变绿而删断言。

`bash 内核维护/2026-09-30-步进规则同步/run.sh audit`共3次，另有6份前后全量快照：

| 回执 | 结果 |
|---|---|
| [p3-audit01.json](p3-audit01.json) | 失败：本包审计脚本把topology标题误写为“失败/未通过”，实际为“能检且不通过”；业务判据已通过到报告核验前，历史零变化。改成精确匹配现有0项标题，未放宽0失败要求。 |
| [p3-audit02.json](p3-audit02.json) | 通过；旧SHA全仓分类后活动残留0 |
| [p3-audit03.json](p3-audit03.json) | 最终通过；读者自审修正和历史注释限定落盘后再次核验，66个本地链接存在 |

编辑/生成命令均为`PYTHONDONTWRITEBYTECODE=1 python3 -B ...`，按顺序执行package3-docs.py、package3-interfaces.py、package3-sync.py、package3-reader-fixes.py、package3-final-notes.py；package3-work.py分别以p3-install01、p3-install02、p3-reader-fixes、p3-final-notes安装，写入前后守卫、原字节备份，再写目标。候选报告暂存及首段更新用本轮只读日志；源扫描以rg --hidden --no-ignore检全部仓库文本，排除.git、target、__pycache__、.cargo-home的工具/构建数据，不使用Git。

首次接口生成器有Python无效转义SyntaxWarning（Markdown竖线转义），生成成功；已修正生成器字符串，非测试失败。所有暂存及生成脚本为一次性实施史料，不能在后续包之后重放覆盖当前文件。当前入口以业务路径及package3-active-final.json为准。package3-summary.py整理回执，package3-record.py追加本节；脚本、日志、哈希清单均在本目录。

### 审计与历史保护

两表逐行核115行规则和15行任务的源文/序号/去向；数据表sources下标逐项一致。旧r29的rebuild_semantics_table/rebuild_contract_table只读重建后，77条约束行与包三前原字节相同，条款名/源行/据行逐个对上现行目录。18配方机型/用量/产量/耗时保持，66轴名/值/含义/依据/损失与注册表相符；30份v4输入的目录与配置路径及SHA、候选B16来源、三正式源在运行语义中的SHA全部核等。

历史全量包含被忽略文件：crates/kernel/evidence为572，crates/kernel/复核为2094，数据/复核为815；合计3481文件、1,018,807,436字节。13条命令的26次前后比对、3次audit的6次前后比对及所有写入守卫均等于包一initial-history.json，新增/删除/修改均0。清单本身SHA-256为`f6f6772a547e5a4bf4396e777f4823bf00e7dea81d7c3a416a9475f75a9d377e`，逐命令清单SHA及diff路径见package3-summary.json。最终封存见[package3-final-history.json](package3-final-history.json)和[diff](package3-final-history-diff.json)。

目录SHA保持`73de10b3a4849302eb259dd16c6830d3a37464ea4a6b211dbc6c38a655d30e53`；配置v2保持`680acb480aa28443431e119c98e4cc45ca6abade1670c9a4a1283a77a7d199a2`。业务开工/最终清单核仅上述16文件变化；crate源码、topology、输出schema、全部新旧样例/fixtures、旧配置、正式源均未修改。包一/二记录正文保持不变。

旧目录/规则/任务SHA全仓命中逐项分为protected_history、indexed_history、historical_spec、revision_history、archived_or_parallel、this_run_record；本轮最终活动类为0。分类依据在清单逐项列出：历史样例/测试须在两份历史说明中明列，规格以运行语义§1现行清单定界，其他沿用带轮次历史目录分类；未知路径默认活动，不靠放宽整个数据/源码目录掩盖残留。

### 交付自审与未完成项

已按未来读者视角复读现行正文、轴表、覆盖表、README及本节：版本/数字/时间量纲一致；源行与章节去向、名称和实际字段核对；删除旧语义的现行叙述；保留配方与条件证明的前件；区分已实现、本版读法、诊断、历史证据与未证全称。配置遗留注释不冒充现行运行机制，旧自查失败如实保留。包三未完成或做不了的项：无。
'''
assert s['changed_business_files']==16,s['changed_business_files']
p=ROOT/'内核维护/2026-09-30-步进规则同步/记录.md';before=p.read_text();assert '\n## 包三\n' not in before
updated=before.replace('包一、包二已验收；各包事实按执行时点分节，本记录不替代包三规格同步或独立终审。','包一、包二、包三已验收；各包事实按执行时点分节，本记录不替代独立终审。',1)+text
assert before.split('\n## 包一\n',1)[1]==updated.split('\n## 包一\n',1)[1].split('\n\n## 包三\n',1)[0]
guard('p3-record-before')
try:
 write('内核维护/2026-09-30-步进规则同步/记录.md',updated)
finally: guard('p3-record-after')
guard('package3-final')
s=m.summary()
print(json.dumps({'report_path':str(p),'summary':s['status'],'command_history_comparisons':s['command_history_comparisons'],'audit_history_comparisons':s['audit_history_comparisons'],'changed_business_files':s['changed_business_files'],'blockers':[]},ensure_ascii=False))
