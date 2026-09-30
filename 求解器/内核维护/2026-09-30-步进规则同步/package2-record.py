"""追加包二已验事实与差分结果；不执行测试。"""
from guard import OUT,ROOT,guard
from work import write
import json
summary=json.loads((OUT/'package2-summary.json').read_text())
commands=[json.loads(s) for s in (OUT/'commands.jsonl').read_text().splitlines() if json.loads(s)['name'].startswith('p2-')]
results={
'p2-check01':'编译失败：旧 Parameters::current 已删除；改从三个参数组取完整 Decision',
'p2-check02':'通过',
'p2-lib01':'开发测试 213.407 秒后由本进程发 SIGTERM 终止；非通过，随后完整重跑',
'p2-lib02':'60 通过、3 失败：周期完整末态行序、机制样例超出补矿覆盖',
'p2-lib03':'61 通过、2 失败：已定位为 warehouse.slots 的序列差异',
'p2-lib04':'63 通过',
'p2-lib05':'66 通过',
'p2-reference01':'9 通过、2 拒收：迟滞/断尾误改了任务初始满仓快照',
'p2-reference02':'10 通过、1 失败：分矿空跑，精炼炉输入须为蓝铁矿',
'p2-reference03':'10 通过、2 失败：九例差分已过；schema 尚有旧轴和参数点结构',
'p2-reference04':'13 通过，含 4000 步差分、schema、独立审计、迁移生成',
'p2-clippy01':'通过，无警告',
'p2-final-build':'通过','p2-final-check':'通过','p2-final-clippy':'通过，无警告',
'p2-final-kernel-lib':'66 通过','p2-final-topology-lib':'1 通过','p2-final-reference':'13 通过',
'p2-final-validation':'30 通过','p2-final-kernel-doc':'通过（0 项）','p2-final-topology-doc':'通过（0 项）',
'p2-final-catalog':'三份正式源全文及 SHA 回源通过',
'p2-final-catalog-tests':'9 通过，单位 1173、配方 154 项逐叶变异全部拒绝'}
rows='\n'.join(f"| [{r['name']}]({r['name']}.log) | `{' '.join(r['argv'])}` | {r['exit_code']} | {results[r['name']]} |" for r in commands)
entries=[
('a-纯链',400,'启动后每 8 步开工一次'),('b-迟滞',400,'n=2 活支连续两次出件间隔合计 17 步，16/17 满速比'),('c-换主料',800,'主料交替，回到同主料开工间隔 18 步；耗尽后停机状态也逐步相等'),('d-满箱串联',400,'上游 b0 第 3 步才首次送出，三个满箱各晚一步'),('e-汇流',400,'稳态合流每 8 步出一件，40 步上限 1 的稀疏支通过'),('断尾',400,'m=2<L=3；n=1 间隔 9 步，8/9 满速比'),('分矿',400,'两台精炼炉各每 16 步开工，两条出料线均进入核心'),('侧面优先',400,'过路带送入 50 件，侧箱 0 件'),('三上游',400,'合流 50 件，全部来自同一个上游')]
diff='''# 步进规则同步：包二差分

日期：2026-09-30。状态：九例共同构型 4000 步全相等，现象断言全部通过；没有未定位差异。范围为固定输入的共同投影，不是独立全域证明。

## 入口与证据

Rust：`crates/kernel/tests/reference.rs`；Python：`数据/工具/step_graph.py` 与 `sim2_adapter.py`。适配器直接只读导入 `规则修订/2026-09-30-迟滞/sim2/simulator.py`，没有复制或修改该模拟器。当前 simulator.py SHA-256 为 `'''+summary['sim2_sha256']+'''`。

最终命令为 `cargo test -p kernel --test reference -j 4 -- --test-threads=1`，由本目录 run.sh 包裹；[p2-final-reference.log](p2-final-reference.log) 显示 13 项全部通过。每例遇差异立即报告第一步、第一字段；Rust 逐步实际状态与独立 Python 数组逐行比较。没有把摘要相等当成逐步相等。

共同字段：step、按执行次序的 moves、逐运输格物种与年龄、普通格（含缓存）物种件数、制造阶段与剩余、箱冷却、仓库非零物种件数。同层序位由输入接通时刻及 connection.tie 独立计算；层数交给 sim2.layers_for；全部元件之后按显式 nontransport_order 判定。

## 九例

| 输入 | 步数 | 已执行现象断言 |
|---|---:|---|
'''+ '\n'.join(f'| [{name}](../../数据/样例/步进/差分/{name}.json) | {steps} | {desc} |' for name,steps,desc in entries)+'''

换主料前两种 16 步情形由包一的正式配方单元测试覆盖；本差分 c 按设计取第三种研磨机情形。b 为同层时 X 较早，断尾为 X 层数严格较小。两例的任务初始仓库仍满，仅运行条件种子减去部分源矿以留出核心接收空间。

## 独立审计与其余核对

reference 的其余四项分别检查：五份 step fixtures；Python audit_step.py 对全状态及增量记录重算事务、仓库守恒、箱逐格内容与冷却，并拒绝篡改；v4 周期 schema 与生产代表调整账；29 份输入重复生成及 before/after 迁移、intake 拒收。普通制造审计仅执行其显式补矿覆盖内的 25 步。全部记录通过标准输入/输出管道传递，未写仓库内运行记录或证书。

## 定位过的问题与共同域边界

开发期差异均定位在新实现/样例侧：b、断尾的任务初始满仓快照误改导致装载拒收；分矿最初误供源矿，Rust 与 sim2 同样空跑，独立现象断言将其抓出后按正式精炼配方改为蓝铁矿，并核两条入核心通道；schema 残留旧轴与参数点 Decision 结构问题由独立 schema 校验抓出。没有发现 sim2 在本九例中读错条文。

适配器的共同域不包括纯带环、两出口桥轴、协议核心送货和未定义的跨格严格部分残留；相应请求明确拒绝。原 sim2 没有实现新条文的同层接通序，适配器按规则 L27 补这一层排程。ConfiguredGate 补可设准入口身份/累计/窗口守卫；Box 包装器只拒绝未定义的跨格部分残留，不改模拟器事务规则。制造在制缓存原料由 running recipe 投影恢复，未借 Rust 状态填 Python 结果。

周期和检查点中发现的仓库行序差异属于序列化/恢复问题，见[记录·包二](记录.md#包二)，不冒称为 sim2 差分发现。包三规格与覆盖表同步、独立终审不在本包范围。
'''
record='''

## 包二

### 结果与边界

包二完成：kernel-output-v5 逐步记录、全状态/检查点增量、phase-cycle-key-v2、kernel-cycle-v4、种子规范化与检查点、完整 CLI、Python 独立账审、九例差分及样例/fixture 迁移。最终完整安全集通过；九例共 4000 步逐步投影一致并通过现象断言。

汇总：[package2-summary.json](package2-summary.json)。全部业务变更及前后 SHA：[package2-changed-paths.json](package2-changed-paths.json)。差分：[差分.md](差分.md)。无 Git 操作；未运行 cargo test --workspace、七个旧 CLI 目标、verify_all.py 批量入口或内核二进制写文件命令；未新建 profile。测试用共享 `求解器/target`、默认 profile、`-j 4` 与 `--test-threads=1`。

本包没有实施包三的候选 B 重锁、覆盖表、运行语义等规格正文和总修订记录。记录/证书只在安全测试内存中生成，仓库里仅新增输入。周期维持 diagnostic_cycle，不把一次固定种子执行升级为全称或完整基地周期证明。

### 文件变更

以下相对 `求解器/`。业务新增 39、修改 12、删除 9；维护目录内的脚本、日志、快照另计。

| 类别 | 文件/目录 | 内容 |
|---|---|---|
| 输出与周期 | `crates/kernel/src/output.rs`、`cycle.rs`、`cycle_io.rs`、`seed.rs`、`main.rs`、`lib.rs` | 一行一步、连续事件身份、完整来源绑定、重放与篡改拒收、步预算和件/tick 率、恢复模块表；全状态格式名为 full_state_each_step；删除旧扫描控制和特判 |
| 包二必要的装载/恢复修正 | `crates/kernel/src/interfaces.rs`、`warehouse.rs` | 初相位只在初始锚点和种子冷却核等；新增仓库格后排序并重建索引，保证完整检查点后继相同 |
| 测试与独立账审 | 新 `src/tests_output.rs`、`src/tests_cycle.rs`、`tests/audit_step.py`；改 `tests/reference.rs`、`tests/verify_all.py` | 记录与周期往返、错误拒收、余留规范化、平均率、内存引用记录、样例装载；独立重算六类仓库流、总账、逐格箱货、冷却与身份；schema 校验；版本分类 |
| 生成与适配 | 新 `数据/工具/step_graph.py`、`sim2_adapter.py`、`step_samples.py`、`migrate_input_v4.py` | 独立元件/接通序，直接导入 sim2，来源 SHA 表，v3→v4 迁移、全物理通道及显式代表参数 |
| 新输入 | `数据/样例/步进/差分/` 9 份、`机制/` 14 份、`周期/` 2 份；`crates/kernel/tests/fixtures/step/` 新增 bridge、core_inbound、priority、benchmark_1000 | 29 份；加上包一 base 共 30 份 v4 输入全部核对新目录/配置 SHA |
| Schema 与说明 | 改 `规格/内核输出.schema.json`、`crates/kernel/周期键读取审计.md`；新 `数据/样例/步进/README.md`、`数据/样例/历史说明.md`、`crates/kernel/tests/历史说明.md` | 现行版本结构、生产键各字段读取与证据方向、各例步数/检查点/重生成方法及逐项历史清单 |
| 删除 | `src/event_identity.rs`；`tests/revision_cli.rs`、`revision_r2_cli.rs`…`revision_r5_cli.rs`、`round5_cli.rs`、`round6_cli.rs`、`tests/support/mod.rs` | 移除旧事件身份模块和会写历史证据的七个 CLI 测试目标 |

`ledger.rs`、`digest.rs`、包一 base fixture、目录/配置、step_inputs.py、topology、候选 B、其他规格文件及全部旧样例/fixtures 字节不变。`周期键读取审计.md` 不在通用 active_snapshot 的目录枚举内，另按首次写入前备份补列其前后 SHA，见 [package2-extra-baseline.json](package2-extra-baseline.json)；没有改写开工快照。

### 规则读法与设计冲突的处理

1. 任务书“历史产物不改写”和设计 §6.3/§7 优先：旧 check_examples.py 与其 SOURCE_HASHES 保留，新输入由 step_samples.py 的三源 SHA 表及目录/配置引用锁定。124 个旧文件逐字节未变（115 个旧样例/工具/记录 + 9 个旧 fixtures）；包一汇总的 135 是它当时连同旧配置、正式源及保留模块等的保护总数，不是旧样例单独数量。
2. 设计要求 checkpoint 固定参数原封不动；包一接口仍逐次要求 transfer.phase 等于当前冷却。按初相位及步边界读法，仅在种子等于 initial_state 原锚点时要求相等，后续边界保留原初相位但严格核当前 0…40 冷却。只做这一处必要装载修正，没有重做包一。
3. 生产环带的完整周期重跑暴露新仓库格追加行序与 Engine 装载排序不同。物种及件数一致但完整状态数组不同。按设计“完整状态恢复”要求，在创建格的提交处统一格名序并重建索引，不更改物种身份或收货选择。没有用忽略完整状态差异来放过验收。
4. 机制“无线多格歧义”原本就是规则未定的严格跨格部分残留负例。设计同时要求迁移 14 例并全跑，按任务书第 1 节保留该合法输入，在第 0 步明确断言 unsupported/transfer.partial_acceptance；不能为让它一直运行而猜扣格顺序。其余 13 例跑满说明给的步数。“装载与普通制造”保留显式补矿 through=24 步，实际跑 25 步，不扩写其历史补给证据。
5. 分矿使用正式精炼配方的蓝铁矿；c 差分只取设计指定的第三种研磨机 18 步例，16/16 两例继续由包一单元测试覆盖。默认选支及 before_send 仅是一个显式代表，不宣称全称。

### 命令、失败与修复

全部安全命令通过 `bash 内核维护/2026-09-30-步进规则同步/run.sh run <唯一名> <命令>` 运行。共 23 条、46 份测试/检查前后历史快照；每条 active_diff 也为空。完整环境与时间见 [commands.jsonl](commands.jsonl)。

| 日志 | 命令 | 退出码 | 结果 |
|---|---|---:|---|
'''+rows+'''

最终完整入口：[package2-safe-suite.sh](package2-safe-suite.sh)。11 条 p2-final-* 全部退出 0；Clippy 无警告。原始失败日志未删除或覆盖。

最初强制哈希碰撞测试恢复每个候选时重复解析和回源，执行较慢；`kill -TERM 505994` 只结束本轮测试进程，该次 p2-lib01 没记通过。内部恢复改为复用已经装载的固定 Input、重新严格装载完整 State，仍逐候选完整键比较；强制碰撞的 48 步预算测试明确保持 inconclusive，重放预算耗尽也不报周期。周期正例另用原种子独立搜索与周期重跑验证。

编辑/生成命令：`python3 -B package2-work.py baseline`；`package2-rust.py`、`package2-cycle.py`、`package2-schema.py` 写暂存稿；后续 `python3 -B -` 定向编辑同一暂存目录；`package2-work.py <标签>` 按 guard→before 原字节备份→安装→guard 写入；`package2-generate.py <标签>` 生成输入；`package2-docs.py` 生成说明；`package2-format.py` 仅格式化本包 Rust 文件（skip_children=true）；`package2-summary.py` 整理回执；`package2-record.py` 追加本节。均设置 PYTHONDONTWRITEBYTECODE=1。暂存稿与一次性编辑脚本是实施史料，不能在后续包后重放覆盖当前实现。

第一次样例生成因目标目录尚不存在且相对目录未 resolve 而退出，无输入落盘；finally 守卫仍零差异，后续在读取前规范路径后生成成功。整理汇总时曾误把包一合计保护数 135 当作旧样例/fixtures 数，改为直接分类核对 115+9=124。所有数据写入前后守卫及两次格式化 argv/退出码均在本目录；安全命令未产生活动文件变化。

### 核对与哈希

- 内核库：66 项通过；包括两个生产环带找到诊断周期并 verify_cycle(record_mode=none) 通过，周期账篡改被拒，内存引用记录重跑通过，剩余停留/窗口规范化、种子幂等、固定参数 checkpoint 和精确件/tick 率。
- reference：13 项通过；九例共 4000 步逐字段相等，外加现象断言；Python 审计普通/生产代表记录及增量、箱格和冷却，篡改被拒；全部迁移与 fixtures 装载；29 份生成结果与保存输入相等。
- topology 库 1 项、validation 30 项通过；两个 doc 目标通过（各 0 项）。目录回源与 9 项目录测试通过，单位 1173、配方 154 项逐叶变异全部拒绝。
- verify_all.py 仅代码审查：历史版本在收集阶段分流，不进 schema/CLI/审计；当前 v5/v4 才进入新核验器。未实际运行批量入口。

历史目录全量核对包含被忽略文件：evidence 572、kernel/复核 2094、数据/复核 815，合计 3481 个文件、1,018,807,436 字节。23 条安全命令的 46 次前后快照均等于包一开工 initial-history.json，新增/删除/修改全为 0。清单本身 SHA 均为 `'''+summary['history_manifest_sha256']+'''`，最终见 [package2-final-v3-history.json](package2-final-v3-history.json) 与 [diff](package2-final-v3-history-diff.json)。每条回执和清单 SHA 见 package2-summary.json 的 receipts。

目录 SHA：`'''+summary['catalog_sha256']+'''`。配置 v2 SHA：`'''+summary['config_sha256']+'''`。输出 schema SHA：`'''+summary['schema_sha256']+'''`。新输入及来源表见 [package2-samples.json](package2-samples.json)，包含包一 base 在内的 30 个输入引用逐个复核通过。

### 交付自审与未完成项

已按未来读者视角复读生产键审计、两份历史清单、样例 README、本节与差分.md，核过链接、现行/历史标签、测试计数、步数、固定参数边界和未声明的证明方向。包二未完成或做不了的项：无。后续复用原始历史基线；包三与独立终审仍由其工作范围承接。
'''
guard('p2-record-before')
try:
 text=(OUT/'记录.md').read_text();assert '\n## 包二\n' not in text
 text=text.replace('包一已验收；本记录不代替包二、包三的运行记录、差分或规格交付。','包一、包二已验收；各包事实按执行时点分节，本记录不替代包三规格同步或独立终审。')
 write(str((OUT/'记录.md').relative_to(ROOT)),text+record)
 write(str((OUT/'差分.md').relative_to(ROOT)),diff)
finally:guard('p2-record-after')
