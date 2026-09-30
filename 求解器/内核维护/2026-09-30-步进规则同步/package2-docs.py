from pathlib import Path
import json
O=Path(__file__).resolve().parent;R=O.parents[1];S=O/'package2-stage'
def put(p,t):
 f=S/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(t)
sha=json.loads((O/'formal-sources.json').read_text())
put('crates/kernel/周期键读取审计.md',f'''# phase-cycle-key-v2 的读取前件与步进支持域

日期：2026-09-30。状态：包二实现读取审计；独立全域证明不在本文件内。键用于同一固定输入内的生产代表查重，完整状态用于恢复；发现重键只报告 `diagnostic_cycle`。

## 1. 正式来源与上下文

规则 SHA-256：`{sha['《明日方舟：终末地》游戏规则.txt']}`。任务 SHA-256：`{sha['求解任务.txt']}`。时间语义见规则 L23—L33、L36—L37、L65：一步为 1/8 tick，运输滞留至少 8 步，箱冷却与准入口窗口均为 40 步。所有状态位于步与步之间；`environment.time=s` 表示下一步是 s。

上下文包含目录、完整几何与建成接通史、66 轴参数、设定、`step-order-v1` 和按箱的 `transfer-timing-v1`。层数与先后在装载时确定，运行中固定。不同上下文不能只凭裸键比较；证书来源指纹绑定这些输入及实现、配置和本审计。

## 2. 准入条件

| 条件 | 实现读取与范围 |
|---|---|
| D.1 | 在线、零干预、`sufficient` 原矿补给；无未来建成、离线、玩家动作或拿取策略；无待响应拿取记忆。|
| D.2 | 两矿各有唯一正库存；现存回矿候选及可尝试无线回矿在读取抽象容量前停止。`step.rs::route` 与 `warehouse.rs::transfer` 继续动态核对。|
| D.3 | 仓库匿名空格顺序为空，全部取货指派均为矿石格；成品当前或历史身份格不被指派。`W_new_` 标签须与物种编码相符。|
| D.4 | `Input` 完整装载、`step.order` 已校验、全部层数和先后已算出；不据此声明种子可达。|
| D.5 | 每步结构入量界 B = 核心入货通道数 + 300 × 有电且开传输的箱数，要求 B < 80000。每个元件一判定最多送一件，每箱一判定最多尝试一次全箱传输。|

## 3. 字段读取与规范化

| 状态字段 | 实际读取 | 键中表示 |
|---|---|---|
| 运输格 `entered_at` | `step.rs::mature/settle` 只核已停满 8 步 | 剩余停留 `max(0, entered_at+8-time)`，范围 0…8。成熟旧件年龄不再增长。|
| 桥格 `last_unit` | `route` 禁止立即送回刚离开的单位 | 原值保留，桥轴不合并。|
| 非运输格库存 | `source/target/put/remove/try_start/flush` 读取物种与件数 | 每格按物种合计，时刻为 null；不同编号箱格不合并。|
| 制造阶段、配方、剩余 | 每步开头减剩余、结束；步末开工 | 原值保留；只有 idle/working/completed。停机剩余冻结。|
| 箱冷却 | 开功能时每步减一；判定中为零才传输 | 相对冷却 0…40 保留。|
| 准入口累计 | 收货检查固定阈值，成功加一 | 有上限 C 时取 min(n,C)，无上限时置 null；完整状态保留审计累计。|
| 准入口窗口 | 收货检查本窗上限，收尾清到期窗口 | idle，或 active、已收数与 `w+40-time`；不改变通道和层数。|
| `poll_state` | 循环侧从上次成功下一条试；非运输输出按 recency 试 | 原样保留。只有成功移动更新，无绝对时间。|
| 仓库 | 核心接收、取货、传输与补给 | 成品当前或历史身份格移出，两矿数量写 sufficient；其余身份和库存保留并按格名排序。|
| 环境与语义上下文 | 固定阶段、在线与拿取记忆；D.3 空格序 | 删除绝对 time，其他未来有效字段保留。|

数量先作精确有理数规范化，再移除 category；说明性的 basis 不参与判等。键不包含运行事件或台账。绝对步事件身份 `E|s|i` 只服务记录审计，不影响下一步守卫。完整状态、事件和仓库逐物种账仍在独立重跑中逐字段核对。

整数溢出和重放预算不足均停止为 `inconclusive`；有限程序的重键证据不代替无限资源或全称结论。`Engine` 实例应只由本身转移推进；跨状态公开键入口会重新装载状态。

## 4. 仓库代表与完整恢复

每步开始将两种成品仓库数归零，保留物种历史身份；扣量记入 `representative_adjustment`，不算玩家拿取、不算负交付。B < 80000 保证从这个代表开始，一步内所有候选及实际成品容量查询可接收。物理通路、供电、冷却与来货仍由生产状态决定。环境前提仍是“仓库收得下成品”。

无线部分接收逐物种取仓库余量；同种跨多个编号格且严格部分接收时，残留分配未由规则确定，提交前报 `unsupported`。全收、全拒收或单格部分接收的后态唯一。

新仓库格建立后即时按格名排序并重建索引，与装载采用同一行序，保证检查点恢复和连续执行的完整状态字节表示一致。`checkpoint_input` 保留原始历史和固定参数。箱初相位在原始锚点核对，后续边界允许冷却变化；当前冷却仍按状态域严格检查。

## 5. 搜索、证书与证据方向

搜索每步取一次键。SHA-256 仅定位候选桶；命中后从已保存检查点重跑到候选位置，比较完整键。找到正步长 P 后，从原周期起点独立执行恰 P 步，核完整末态、逐步事件身份、台账和接收报告。验收从原输入重新搜索，并再次独立重跑周期段；`record_mode=none` 也执行这些检查。

`kernel-cycle-v4` 的预算为 max_steps/completed_steps；`period` 是步数，`period_ticks=P/8` 精确约分。件/tick 平均率为 `inbound×8/P`，目标比较使用交叉乘法。`cycle-normalization-v3` 与 `phase-cycle-key-v2` 共同锁定这套表示。

`correspondence` 保留三组义务：前向投影仍为 unresolved，反向完整循环复原和全部可达循环为 not_claimed。即使实际平均率达到目标，当前证书仍是诊断周期；本次测试、差分和读取审计均不升级其证明方向。
''')
# Explicit inventories avoid relabeling any old bytes.
old=json.loads((O/'package2-active-start.json').read_text())
files=[p.removeprefix('求解器/数据/样例/') for p in old if p.startswith('求解器/数据/样例/') and '/步进/' not in p]
put('数据/样例/历史说明.md','''# 样例版本与历史文件

日期：2026-09-30。现行输入在 [步进/README.md](步进/README.md)，为 kernel-input-v4、静态目录 v3、配置 v2。下列文件保留原字节，属于旧语义的输入、参数投影、黄金轨迹、运行记录、证书及旧校验工具；不能用现行内核验证其旧轨迹。

旧输入由迁移工具只读用于生成新的条件种子；迁移不继承轮询记忆，也不继承旧运行结论。旧 check_examples.py 的 SOURCE_HASHES 不刷新。运行入口读取新输入；旧记录由 verify_all.py 按版本列入 historical_records，不重验、不重写。下列目录索引不改变文件本身。

## 历史清单

'''+''.join(f'- [{p}]({p})\n' for p in sorted(files)))
tests=[p.removeprefix('求解器/crates/kernel/tests/') for p in old if p.startswith('求解器/crates/kernel/tests/') and (p.endswith('.py') or '/fixtures/' in p or '/legacy_probes/' in p) and not p.endswith('/verify_all.py') and '/fixtures/step/' not in p]
put('crates/kernel/tests/历史说明.md','''# 测试入口与历史材料

日期：2026-09-30。现行库测试为 src/tests_output.rs、src/tests_cycle.rs 及整数步机制测试；reference.rs 在内存中比较九例 sim2 投影、审计 v5 台账、验证 schema 与样例生成。现行 fixtures 在 fixtures/step/。

verify_all.py 当前仅验 kernel-output-v5 与 kernel-cycle-v4；kernel-output-v1…v4、kernel-cycle-v1…v3 只列为 historical_records。它使用配置 v2 与 audit_step.py。该批量入口本轮仅代码审查，没有实际运行。

七个旧 CLI 目标 revision_cli、revision_r2_cli…revision_r5_cli、round5_cli、round6_cli，以及 support/mod.rs 已删除，其原字节在本轮维护目录 before/ 中。它们曾写历史证据，不能将其旧隔离凭据用于新源码。现行库和 reference 测试不写仓库文件；Python 子进程使用 -B 及管道。

以下旧 Python 工具和 fixtures 原字节保留，只作历史材料；不能将它们的通过解释为当前步进语义已验证。

## 历史清单

'''+''.join(f'- [{p}]({p})\n' for p in sorted(tests)))
# README generated from the current manifest to avoid hand-maintained counts or windows.
manifest=json.loads((O/'package2-samples.json').read_text());rows=[]
for rel in sorted(manifest['inputs']):
 if rel.startswith('数据/样例/步进/'):
  raw=json.loads((R/rel).read_text());sc=raw['scenario'];short=rel.removeprefix('数据/样例/步进/');n=sc.get('steps',sc.get('differential',{}).get('steps'));desc='；'.join(sc['assertions']);rows.append(f'| [{short}]({short}) | {n} | {desc} |')
put('数据/样例/步进/README.md','''# 整数步内核样例

日期：2026-09-30。输入版本 kernel-input-v4，目录 static-catalog-v3，配置 kernel_profile_v2。包含九个差分、14 个机制、两个周期输入；运行记录和周期证书只在安全测试内存中生成。

所有种子均为明示条件输入，不构成起动、全部接通史或全部参数的证明。每一步是 1/8 tick；状态 time 指下一步。差分与 sim2 共同域比较移动先后、运输物种和年龄、普通库存、制造阶段和剩余、箱冷却、仓库物种件数。

## 样例

| 输入 | 执行步数 | 检查内容 |
|---|---:|---|
'''+ '\n'.join(rows)+'''

无线多格歧义要求在第 0 步以 transfer.partial_acceptance 停止；该停止是样例的预期结果。装载与普通制造只执行显式补矿覆盖内的步数，不把超出来源覆盖的停止记作制造故障。

机制与周期输入由历史 v3 输入迁移：所有时刻乘 8，before_boundary 的 t 变 8t，after_closure 的 t 变 8(t+1)。不继承旧轮询记忆；intake 阶段拒绝迁移。默认选支取最小结果层数、同层取身份序，环给字典序最小元件层 1，箱传输取 before_send。这只是一个代表值。每份输入在 scenario.migration 保存历史来源与其 SHA。

差分均显式写 step.order、transfer.timing 与完整物理通道表。c 采用正式研磨配方与预装砂叶粉末；有限供料耗尽后继续比较停机状态。分矿采用精炼炉实际接受的蓝铁矿；两支均有完整入核心通道。

## 生成与核对

从求解器目录运行 `python3 -B 数据/工具/step_samples.py --case a-纯链` 可将一个输入输出到标准输出；不带 --case 输出全部 29 份新输入的路径映射（另四份是 fixtures）。工具内 SOURCE_HASHES 锁三份正式源，生成时校验原始字节。迁移单文件入口是 `python3 -B 数据/工具/migrate_input_v4.py OLD.json --base DESTINATION_DIRECTORY`，同样只输出标准输出。

向仓库写入必须使用维护目录 package2-generate.py 的守卫写入入口，传一个新的唯一标签；它核历史 SHA、备份原字节、写输入、再核历史 SHA。不得重放 package2-work.py 的旧暂存安装稿覆盖后续维护成果。

验收从维护目录 run.sh 运行任务书安全目标 kernel --lib 与 kernel --test reference；每条安全命令前后均校验历史目录。reference 的 schema 校验使用 Node 与 AJV 2020，可用 KERNEL_AJV 指定模块路径。迁移重复生成、全部样例装载、预期停止、周期重放和九例现象都有内存测试。

sim2 适配器不接受两出口桥轴、纯带环、协议核心送货或未定义的跨格部分残留；这些构型未被九例差分覆盖。对应内核机制由库测试单独检查。本目录不给独立全域证明或全称覆盖结论。
''')
