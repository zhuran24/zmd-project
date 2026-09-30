# 步进规则同步：执行记录

性质：实施与验收史料，截止 2026-09-30。包一、包二、包三已验收；各包事实按执行时点分节，本记录不替代独立终审。

## 包一

### 结果与边界

完成整数步核心、静态目录 v3、66 轴配置 v2、输入 v4 与状态 v2；完整安全集通过。没有 Git 操作，没有运行七个 CLI 测试目标、全工作区测试或内核二进制写文件命令。构建使用共享 `求解器/target`、默认 profile、`-j 4`，测试统一 `--test-threads=1`。

机器汇总：[package1-summary.json](package1-summary.json)。完整修改清单及前后 SHA-256：[package1-changed-paths.json](package1-changed-paths.json)。安全命令原始回执：[commands.jsonl](commands.jsonl)。

本包不实施包二、包三：输出记录、周期证书与生产键、Python 核验器、sim2 九例逐步差分、其余样例迁移、覆盖表和规格总同步。`output.rs`、`cycle.rs`、`cycle_io.rs`、`event_identity.rs`、`seed.rs` 原字节保留，已从模块表移出。CLI 当前只有 `check INPUT` 与 `run INPUT --steps N --no-output`；本轮未实际调用其二进制入口。七个旧 CLI 测试源码按设计留到包二删除，不能对当前工作区跑全测试。

### 文件变更

以下路径均相对于 `求解器/`；维护目录内的脚本、日志、哈希清单另列在后面。业务文件新增 13、修改 16、删除 11。

| 类别 | 文件 | 结果 |
|---|---|---|
| 目录投影 | `数据/工具/formal_units.py`、`formal_catalog.py`、`test_formal_catalog.py`；`数据/正式静态目录.json` | 从三份现行正式源重建 r30，加入 `timing`，任务条件变为 10；同步箱体冷却和准入口不收货语义；新增 timing 变异拒收 |
| 配置与装载 | 新建 `规格/内核配置-v2.json`；`crates/kernel/src/value.rs`、`catalog.rs`、`config.rs`、`model.rs`、`input.rs`、`interfaces.rs` | 整数步、目录时长换算、66 轴、精简边界状态、v4 严格装载、配置字节绑定、显式选支/环层数/箱体先后接口 |
| 转移 | 新建 `crates/kernel/src/graph.rs`、`step.rs`；改 `engine.rs`、`warehouse.rs`、`polling.rs`、`lib.rs`、`main.rs` | 元件和固定层数/次序、收货组联动、成功后轮询、带内即时前挪、结束/判定/开工、40 步冷却与窗口、台账和 observe 投影 |
| 新测试 | `crates/kernel/src/tests_support.rs`、`tests_graph.rs`、`tests_step.rs`、`tests_manufacture.rs`、`tests_box_gate.rs`、`tests_seed.rs`、`tests_warehouse.rs`、`tests_config.rs` | 54 个只读/内存机制及拒收测试 |
| 新输入 | `数据/工具/step_inputs.py`；`crates/kernel/tests/fixtures/step/base.json`；改 `crates/kernel/tests/reference.rs` | 独立简要布局生成库/标准输出入口，锁新目录和配置；新 fixture 装载后执行 64 步 |
| 删除 | `crates/kernel/src/transition.rs`、`cache.rs`、`tests.rs`、`tests_revision.rs`、`tests_revision_r2.rs`、`tests_revision_r3.rs`、`tests_revision_r4.rs`、`tests_revision_r5.rs`、`tests_round5.rs`、`tests_round6.rs`、`tests_bridge.rs` | 移除旧转移、缓存和依赖旧状态的测试模块；仓库身份、整数、事务失败与守恒断言已迁入新测试 |

`ledger.rs`、`digest.rs`、topology 源码、旧配置 v1、所有旧样例和旧 fixtures 未修改。新 fixtures 是新增路径，未给旧样例重锁。目录按对象核对：77 条约束、18 条配方、32 个常量、19 项物料流量，以及单位尺寸、端口、库存定义全部不变；详情见 [catalog-change.json](catalog-change.json)。

### 规则读法与设计偏差

1. 任务书 §2 总述要求更新旧 `check_examples.py` 来源锁；设计 §6.3、§7 明确将旧样例及该工具保留为历史，且任务书同时禁止改写历史产物。本包按后者处理：旧工具字节不变，只锁新 fixture；包三负责其余重锁与历史索引。不是用新来源为旧语义样例背书。
2. 设计 §10.1 将换主料 16/16/18 三例统称“研磨机”。只读核对 `规则修订/2026-09-30-迟滞/sim2/run_checks.py::machine_builder` 和 `simulator.py::Machine`：前两例是单格、单主料、一次用量 1 的机型；第三例才有两格、主料 2 加砂叶辅料 1。按正式配方，测试以前两例粉碎机、第三例研磨机实现，三个往返周期分别严格断言 16、16、18 步，没有修改正式配方或 sim2。测试为 `tests_manufacture::material_switch_cycles_are_16_16_and_18_steps_with_formal_recipes`。
3. 本轮直接复用旧守卫逻辑时，删除初始化里的全部 Git 调用，改为 `os.walk` 全量文件快照；仍覆盖被忽略文件。没有使用 Git 去查询被忽略路径，因而不单报其数量。
4. 层数歧义、桥轴两出口的收货组传递联动、非运输单位无出口时的显式位置、空箱和全拒收也重启冷却，均按设计 §1 实施。本包没有另增隐式选择或生产周期结论。

### 核心逐条自核

| 规则/边界 | 实现及已验内容 |
|---|---|
| 步与判定 | `step.rs` 明确阶段；每个元件一次、非运输单位一次；带内前挪不占判定；无端口预算 |
| 元件/层数/先后 | 带链与纯环身份、桥两轴、候选选支、环锚点；缺选支/环锚点 unresolved；错误输入 invalid；同层按最早外送通道序位；非运输全序核对 |
| 收货/轮询 | 非分流器上游成组，分流器不被带动；桥轴的组传递联动；一次最多外送一件；成功才更新两侧；循环记忆和非运输 recency 分开 |
| 制造 | 开始后第 8d 步结束；完成批即时整批进输出；取走一件后立即再尝试出缓存；关闭时不开工、在制冻结；同种普通格唯一 |
| 箱体/准入口 | 输入的 before/after 两种次序；40 步冷却、暂停、空箱/全拒收、部分接收与多格歧义停止；累计和窗口、窗口到期规范化、阻断不改图 |
| 主要现象 | 纯链每 8 步开工；断尾 n=1、2、3 的 8n/(8n+1) 与选活支满速；满箱串联 k=1、2、3 每箱晚一步；换料 16/16/18；侧面过路带独占；三上游一家独占 |
| 输入/仓库/停止 | 运输时刻、非运输无时刻、桥来路、轮询侧全集、坏阶段/剩余/窗口、旧 schema 拒收；仓库历史身份/空格竞争/规范命名；补矿逐物种守恒；显式最后一件矿拒收；离线前置停止与错误封存 |

以上是包一代码与断言自核。sim2 全构型逐步差分及独立终审仍属于后续工作包，未以本包通过替代。

### 命令与结果

守卫入口是 `bash 内核维护/2026-09-30-步进规则同步/run.sh run <唯一名称> <命令>`（执行 cwd 为 `求解器/`）。以下 18 条均有独立的 `*-before-history.json`、`*-after-history.json` 及对应 diff；总计 36 次安全命令前后全量比对。

| 名称/日志 | 实际命令 | 退出码 | 结果 |
|---|---|---:|---|
| [check-01](check-01.log) | `cargo check --workspace -j 4` | 0 | 通过 |
| [reference-01](reference-01.log) | `cargo test -p kernel --test reference -j 4 -- --test-threads=1` | 0 | 1 通过（fixture 64 步） |
| [lib-01](lib-01.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 101 | 39 通过、4 失败；见下方修正 |
| [lib-02](lib-02.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 0 | 43 通过 |
| [lib-03](lib-03.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 0 | 48 通过 |
| [lib-04](lib-04.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 0 | 54 通过 |
| [clippy-01](clippy-01.log) | `cargo clippy --workspace -j 4` | 0 | 通过，无警告 |
| [final-build](final-build.log) | `cargo build --workspace -j 4` | 0 | 通过 |
| [final-check](final-check.log) | `cargo check --workspace -j 4` | 0 | 通过 |
| [final-clippy](final-clippy.log) | `cargo clippy --workspace -j 4` | 0 | 通过，无警告 |
| [final-kernel-lib](final-kernel-lib.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 0 | 54 通过 |
| [final-topology-lib](final-topology-lib.log) | `cargo test -p topology --lib -j 4 -- --test-threads=1` | 0 | 1 通过 |
| [final-reference](final-reference.log) | `cargo test -p kernel --test reference -j 4 -- --test-threads=1` | 0 | 1 通过（fixture 64 步） |
| [final-validation](final-validation.log) | `cargo test -p topology --test validation -j 4 -- --test-threads=1` | 0 | 30 通过 |
| [final-kernel-doc](final-kernel-doc.log) | `cargo test -p kernel --doc -j 4 -- --test-threads=1` | 0 | 通过（0 项） |
| [final-topology-doc](final-topology-doc.log) | `cargo test -p topology --doc -j 4 -- --test-threads=1` | 0 | 通过（0 项） |
| [final-catalog](final-catalog.log) | `python3 数据/工具/formal_catalog.py` | 0 | 回源通过 |
| [final-catalog-tests](final-catalog-tests.log) | `python3 数据/工具/test_formal_catalog.py` | 0 | 9 通过；另含单位 1173、配方 154 个逐叶变异拒收 |

最终整套执行入口：[safe-suite.sh](safe-suite.sh)，其中 11 条 `final-*` 命令全部返回 0。未创建新 profile，未将 target 或 cargo registry 复制进维护/证据目录。

失败与修正：首次 `lib-01` 的四个失败中，三个揭示零冷却使用有符号 `saturating_sub(1)` 后会变成 −1，已改为减后钳制到 0；另一个测试把入核心的带放在核心取货边，改到正式存货边。该轮另有测试代码未用 import 的两条告警，已删除；最终内核测试和 Clippy 均无告警。`lib-02` 起全部通过，新增测试后的 `lib-03`、`lib-04` 与最终全套也通过。失败日志没有覆盖或删除。

编辑/生成命令：依次使用 `python3 -B edit-data.py`、`python3 -B edit-core.py`、`python3 -B edit-engine.py`、`python3 -B work.py`（分批安装编辑稿）、`python3 -B finish-base.py`、`python3 -B finalize-code.py`；调用时均设 `PYTHONDONTWRITEBYTECODE=1`。首次 `edit-core.py` 因旧源码定位串不符退出 1，业务写入止于目录/配置基础迁移，立即补作 [core-edit-interrupted-after-history-diff.json](core-edit-interrupted-after-history-diff.json)，零差异；修正定位后重执行成功。数据生成与安装均按 `work.py` 先守卫、备份原字节、再写入、后守卫的模式；格式化只触及本包 Rust 文件，精确 argv 与退出码见 [format-command.json](format-command.json)。`staging/` 为当时的编辑稿，不是当前源码入口；当前实现及指纹以实际 crate 路径和 `package1-active-final.json` 为准，不能重放编辑脚本覆盖后续包。

### 哈希与保护

目录 SHA-256：`73de10b3a4849302eb259dd16c6830d3a37464ea4a6b211dbc6c38a655d30e53`。

配置 v2 SHA-256：`680acb480aa28443431e119c98e4cc45ca6abade1670c9a4a1283a77a7d199a2`。

新 fixture SHA-256：`93c81bafd26d8225c508a693ed7d3b9ed84cbade45c4c64294cef3bc4e63daf4`。

三份正式源的完整 SHA 在 [formal-sources.json](formal-sources.json)，目录回源已核当前字节。

| 历史目录 | 全量文件数 |
|---|---:|
| `crates/kernel/evidence` | 572 |
| `crates/kernel/复核` | 2094 |
| `数据/复核` | 815 |

合计 3,481 个文件、1,018,807,436 字节。18 条安全命令的 36 份前后快照逐文件等于初始快照；新增、删除、修改均为 0。每份快照的 SHA 和命令对应关系保存在 [package1-summary.json](package1-summary.json) 的 `receipts`。最终 [package1-final-history.json](package1-final-history.json) 文件本身的 SHA-256 为 `f6f6772a547e5a4bf4396e777f4823bf00e7dea81d7c3a416a9475f75a9d377e`，最终 diff 为三个空数组。

135 个旧样例/fixtures、旧配置、三正式源及保留模块/台账相关路径另按开工活动清单核对，全部字节不变。旧语义关键词检查按设计排除五个暂不编译的文件，活动源码零命中，精确命令见 [package1-legacy-scan.json](package1-legacy-scan.json)。

### 交付检查与未完成项

记录已按读者视角复读：文件路径、日志链接、测试数、版本、来源锁、失败与修正、包一和后续包的边界一致。包一未完成或做不了的项：无。下一包复用本目录初始历史基线，不重新初始化或放宽历史守卫。


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
| [p2-check01](p2-check01.log) | `cargo check --workspace -j 4` | 101 | 编译失败：旧 Parameters::current 已删除；改从三个参数组取完整 Decision |
| [p2-check02](p2-check02.log) | `cargo check --workspace -j 4` | 0 | 通过 |
| [p2-lib01](p2-lib01.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 101 | 开发测试 213.407 秒后由本进程发 SIGTERM 终止；非通过，随后完整重跑 |
| [p2-reference01](p2-reference01.log) | `cargo test -p kernel --test reference -j 4 -- --test-threads=1` | 101 | 9 通过、2 拒收：迟滞/断尾误改了任务初始满仓快照 |
| [p2-lib02](p2-lib02.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 101 | 60 通过、3 失败：周期完整末态行序、机制样例超出补矿覆盖 |
| [p2-reference02](p2-reference02.log) | `cargo test -p kernel --test reference -j 4 -- --test-threads=1` | 101 | 10 通过、1 失败：分矿空跑，精炼炉输入须为蓝铁矿 |
| [p2-lib03](p2-lib03.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 101 | 61 通过、2 失败：已定位为 warehouse.slots 的序列差异 |
| [p2-reference03](p2-reference03.log) | `cargo test -p kernel --test reference -j 4 -- --test-threads=1` | 101 | 10 通过、2 失败：九例差分已过；schema 尚有旧轴和参数点结构 |
| [p2-lib04](p2-lib04.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 0 | 63 通过 |
| [p2-reference04](p2-reference04.log) | `cargo test -p kernel --test reference -j 4 -- --test-threads=1` | 0 | 13 通过，含 4000 步差分、schema、独立审计、迁移生成 |
| [p2-clippy01](p2-clippy01.log) | `cargo clippy --workspace -j 4` | 0 | 通过，无警告 |
| [p2-lib05](p2-lib05.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 0 | 66 通过 |
| [p2-final-build](p2-final-build.log) | `cargo build --workspace -j 4` | 0 | 通过 |
| [p2-final-check](p2-final-check.log) | `cargo check --workspace -j 4` | 0 | 通过 |
| [p2-final-clippy](p2-final-clippy.log) | `cargo clippy --workspace -j 4` | 0 | 通过，无警告 |
| [p2-final-kernel-lib](p2-final-kernel-lib.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 0 | 66 通过 |
| [p2-final-topology-lib](p2-final-topology-lib.log) | `cargo test -p topology --lib -j 4 -- --test-threads=1` | 0 | 1 通过 |
| [p2-final-reference](p2-final-reference.log) | `cargo test -p kernel --test reference -j 4 -- --test-threads=1` | 0 | 13 通过 |
| [p2-final-validation](p2-final-validation.log) | `cargo test -p topology --test validation -j 4 -- --test-threads=1` | 0 | 30 通过 |
| [p2-final-kernel-doc](p2-final-kernel-doc.log) | `cargo test -p kernel --doc -j 4 -- --test-threads=1` | 0 | 通过（0 项） |
| [p2-final-topology-doc](p2-final-topology-doc.log) | `cargo test -p topology --doc -j 4 -- --test-threads=1` | 0 | 通过（0 项） |
| [p2-final-catalog](p2-final-catalog.log) | `python3 数据/工具/formal_catalog.py` | 0 | 三份正式源全文及 SHA 回源通过 |
| [p2-final-catalog-tests](p2-final-catalog-tests.log) | `python3 数据/工具/test_formal_catalog.py` | 0 | 9 通过，单位 1173、配方 154 项逐叶变异全部拒绝 |

最终完整入口：[package2-safe-suite.sh](package2-safe-suite.sh)。11 条 p2-final-* 全部退出 0；Clippy 无警告。原始失败日志未删除或覆盖。

最初强制哈希碰撞测试恢复每个候选时重复解析和回源，执行较慢；`kill -TERM 505994` 只结束本轮测试进程，该次 p2-lib01 没记通过。内部恢复改为复用已经装载的固定 Input、重新严格装载完整 State，仍逐候选完整键比较；强制碰撞的 48 步预算测试明确保持 inconclusive，重放预算耗尽也不报周期。周期正例另用原种子独立搜索与周期重跑验证。

编辑/生成命令：`python3 -B package2-work.py baseline`；`package2-rust.py`、`package2-cycle.py`、`package2-schema.py` 写暂存稿；后续 `python3 -B -` 定向编辑同一暂存目录；`package2-work.py <标签>` 按 guard→before 原字节备份→安装→guard 写入；`package2-generate.py <标签>` 生成输入；`package2-docs.py` 生成说明；`package2-format.py` 仅格式化本包 Rust 文件（skip_children=true）；`package2-summary.py` 整理回执；`package2-record.py` 追加本节。均设置 PYTHONDONTWRITEBYTECODE=1。暂存稿与一次性编辑脚本是实施史料，不能在后续包后重放覆盖当前实现。

第一次样例生成因目标目录尚不存在且相对目录未 resolve 而退出，无输入落盘；finally 守卫仍零差异，后续在读取前规范路径后生成成功。整理汇总时曾误把包一合计保护数 135 当作旧样例/fixtures 数，改为直接分类核对 115+9=124。所有数据写入前后守卫及两次格式化 argv/退出码均在本目录；安全命令未产生活动文件变化。

### 核对与哈希

- 内核库：66 项通过；包括两个生产环带找到诊断周期并 verify_cycle(record_mode=none) 通过，周期账篡改被拒，内存引用记录重跑通过，剩余停留/窗口规范化、种子幂等、固定参数 checkpoint 和精确件/tick 率。
- reference：13 项通过；九例共 4000 步逐字段相等，外加现象断言；Python 审计普通/生产代表记录及增量、箱格和冷却，篡改被拒；全部迁移与 fixtures 装载；29 份生成结果与保存输入相等。
- topology 库 1 项、validation 30 项通过；两个 doc 目标通过（各 0 项）。目录回源与 9 项目录测试通过，单位 1173、配方 154 项逐叶变异全部拒绝。
- verify_all.py 仅代码审查：历史版本在收集阶段分流，不进 schema/CLI/审计；当前 v5/v4 才进入新核验器。未实际运行批量入口。

历史目录全量核对包含被忽略文件：evidence 572、kernel/复核 2094、数据/复核 815，合计 3481 个文件、1,018,807,436 字节。23 条安全命令的 46 次前后快照均等于包一开工 initial-history.json，新增/删除/修改全为 0。清单本身 SHA 均为 `f6f6772a547e5a4bf4396e777f4823bf00e7dea81d7c3a416a9475f75a9d377e`，最终见 [package2-final-v3-history.json](package2-final-v3-history.json) 与 [diff](package2-final-v3-history-diff.json)。每条回执和清单 SHA 见 package2-summary.json 的 receipts。

目录 SHA：`73de10b3a4849302eb259dd16c6830d3a37464ea4a6b211dbc6c38a655d30e53`。配置 v2 SHA：`680acb480aa28443431e119c98e4cc45ca6abade1670c9a4a1283a77a7d199a2`。输出 schema SHA：`eb3fa3c25d52bbc39df16a13e610fb9d4ea022fdc9f20ed8e2639e747ec439a8`。新输入及来源表见 [package2-samples.json](package2-samples.json)，包含包一 base 在内的 30 个输入引用逐个复核通过。

### 交付自审与未完成项

已按未来读者视角复读生产键审计、两份历史清单、样例 README、本节与差分.md，核过链接、现行/历史标签、测试计数、步数、固定参数边界和未声明的证明方向。包二未完成或做不了的项：无。后续复用原始历史基线；包三与独立终审仍由其工作范围承接。


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
| [p3-final-build](p3-final-build.log) | `cargo build --workspace -j 4` | 0 | 通过；默认dev profile |
| [p3-candidate-report](p3-candidate-report.log) | `/home/zhuran24/zmd-research-fresh/求解器/target/debug/topology 数据/候选B/contract.json` | 0 | 4924通过、0失败、80不能静态检 |
| [p3-final-check](p3-final-check.log) | `cargo check --workspace -j 4` | 0 | 通过 |
| [p3-final-clippy](p3-final-clippy.log) | `cargo clippy --workspace -j 4` | 0 | 通过，无警告 |
| [p3-final-kernel-lib](p3-final-kernel-lib.log) | `cargo test -p kernel --lib -j 4 -- --test-threads=1` | 0 | 66项通过 |
| [p3-final-topology-lib](p3-final-topology-lib.log) | `cargo test -p topology --lib -j 4 -- --test-threads=1` | 0 | 1项通过 |
| [p3-final-reference](p3-final-reference.log) | `cargo test -p kernel --test reference -j 4 -- --test-threads=1` | 0 | 13项通过；含九例4000步差分、独立账审及schema |
| [p3-final-validation](p3-final-validation.log) | `cargo test -p topology --test validation -j 4 -- --test-threads=1` | 0 | 30项通过 |
| [p3-final-kernel-doc](p3-final-kernel-doc.log) | `cargo test -p kernel --doc -j 4 -- --test-threads=1` | 0 | 通过，0项 |
| [p3-final-topology-doc](p3-final-topology-doc.log) | `cargo test -p topology --doc -j 4 -- --test-threads=1` | 0 | 通过，0项 |
| [p3-final-catalog](p3-final-catalog.log) | `python3 数据/工具/formal_catalog.py` | 0 | 三正式源全文/SHA及目录投影回源通过 |
| [p3-final-catalog-tests](p3-final-catalog-tests.log) | `python3 数据/工具/test_formal_catalog.py` | 0 | 9项通过；单位1173、配方154项逐叶变异拒收 |
| [p3-legacy-check](p3-legacy-check.log) | `python3 规格/check_revision.py` | 1 | 按设计只读运行；旧114行断言失败，非本轮门禁 |

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
