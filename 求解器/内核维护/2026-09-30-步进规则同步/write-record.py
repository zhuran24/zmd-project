"""从封存回执追加包一执行记录。"""
import json, subprocess
from pathlib import Path
from guard import OUT, ROOT, save
s=json.loads((OUT/'package1-summary.json').read_text())
commands=[json.loads(line) for line in (OUT/'commands.jsonl').read_text().splitlines()]
argv=['rg','-n','max_sweeps|ordered_sweeps|after_closure|before_boundary|damping|level_order|level_tie|tick_context|pending_events|blocked_channels|port_usage|scan_round_then_template','crates/kernel/src']
for f in ['output.rs','cycle.rs','cycle_io.rs','event_identity.rs','seed.rs']:argv+=['-g','!'+f]
r=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True)
assert r.returncode==1 and not r.stdout and not r.stderr
save('package1-legacy-scan.json',{'argv':argv,'cwd':str(ROOT),'exit_code':r.returncode,'matches':0,'stdout':r.stdout,'stderr':r.stderr})
record='''# 步进规则同步：执行记录

性质：实施与验收史料，截止 2026-09-30。包一已验收；本记录不代替包二、包三的运行记录、差分或规格交付。

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
'''
counts={'lib-01':'39 通过、4 失败；见下方修正','lib-02':'43 通过','lib-03':'48 通过','lib-04':'54 通过','final-kernel-lib':'54 通过','final-topology-lib':'1 通过','final-reference':'1 通过（fixture 64 步）','final-validation':'30 通过','final-kernel-doc':'通过（0 项）','final-topology-doc':'通过（0 项）','final-catalog':'回源通过','final-catalog-tests':'9 通过；另含单位 1173、配方 154 个逐叶变异拒收','reference-01':'1 通过（fixture 64 步）'}
for c in commands:
    result=counts.get(c['name'],'通过，无警告' if 'clippy' in c['name'] else '通过')
    record+=f"| [{c['name']}]({c['name']}.log) | `{' '.join(c['argv'])}` | {c['exit_code']} | {result} |\n"
record+='''
最终整套执行入口：[safe-suite.sh](safe-suite.sh)，其中 11 条 `final-*` 命令全部返回 0。未创建新 profile，未将 target 或 cargo registry 复制进维护/证据目录。

失败与修正：首次 `lib-01` 的四个失败中，三个揭示零冷却使用有符号 `saturating_sub(1)` 后会变成 −1，已改为减后钳制到 0；另一个测试把入核心的带放在核心取货边，改到正式存货边。该轮另有测试代码未用 import 的两条告警，已删除；最终内核测试和 Clippy 均无告警。`lib-02` 起全部通过，新增测试后的 `lib-03`、`lib-04` 与最终全套也通过。失败日志没有覆盖或删除。

编辑/生成命令：依次使用 `python3 -B edit-data.py`、`python3 -B edit-core.py`、`python3 -B edit-engine.py`、`python3 -B work.py`（分批安装编辑稿）、`python3 -B finish-base.py`、`python3 -B finalize-code.py`；调用时均设 `PYTHONDONTWRITEBYTECODE=1`。首次 `edit-core.py` 因旧源码定位串不符退出 1，业务写入止于目录/配置基础迁移，立即补作 [core-edit-interrupted-after-history-diff.json](core-edit-interrupted-after-history-diff.json)，零差异；修正定位后重执行成功。数据生成与安装均按 `work.py` 先守卫、备份原字节、再写入、后守卫的模式；格式化只触及本包 Rust 文件，精确 argv 与退出码见 [format-command.json](format-command.json)。`staging/` 为当时的编辑稿，不是当前源码入口；当前实现及指纹以实际 crate 路径和 `package1-active-final.json` 为准，不能重放编辑脚本覆盖后续包。

### 哈希与保护

'''
record+=f"目录 SHA-256：`{s['catalog_sha256']}`。\n\n配置 v2 SHA-256：`{s['config_sha256']}`。\n\n新 fixture SHA-256：`{s['fixture_sha256']}`。\n\n"
record+='''三份正式源的完整 SHA 在 [formal-sources.json](formal-sources.json)，目录回源已核当前字节。

| 历史目录 | 全量文件数 |
|---|---:|
'''
for path,n in s['history_files'].items():record+=f'| `{path}` | {n} |\n'
record+=f"\n合计 3,481 个文件、{s['history_bytes']:,} 字节。18 条安全命令的 36 份前后快照逐文件等于初始快照；新增、删除、修改均为 0。每份快照的 SHA 和命令对应关系保存在 [package1-summary.json](package1-summary.json) 的 `receipts`。最终 [package1-final-history.json](package1-final-history.json) 文件本身的 SHA-256 为 `{s['history_manifest_sha256']}`，最终 diff 为三个空数组。\n\n"
record+='''135 个旧样例/fixtures、旧配置、三正式源及保留模块/台账相关路径另按开工活动清单核对，全部字节不变。旧语义关键词检查按设计排除五个暂不编译的文件，活动源码零命中，精确命令见 [package1-legacy-scan.json](package1-legacy-scan.json)。

### 交付检查与未完成项

记录已按读者视角复读：文件路径、日志链接、测试数、版本、来源锁、失败与修正、包一和后续包的边界一致。包一未完成或做不了的项：无。下一包复用本目录初始历史基线，不重新初始化或放宽历史守卫。
'''
p=OUT/'记录.md'
if p.exists():
    previous=p.read_text()
    assert '## 包一' not in previous,'不覆盖既有包一记录'
    p.write_text(previous+'\n'+record.split('## 包一',1)[1].join(['## 包一','']) if False else previous+'\n\n## 包一'+record.split('## 包一',1)[1])
else:p.write_text(record)
print(str(p))
