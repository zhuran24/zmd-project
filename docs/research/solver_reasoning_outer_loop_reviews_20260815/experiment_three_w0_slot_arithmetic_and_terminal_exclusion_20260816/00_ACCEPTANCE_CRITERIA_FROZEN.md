# W0 席位算术引理与终局排除：冻结验收判据

> **状态：** `FROZEN_ON_FIRST_COMMIT / PRE_PROOF`
> **日期：** 2026-08-16
> **性质：** `research_only / non_authorizing`
> **授权坐标：** [`00_OWNER_AUTHORIZATION_20260816.md`](00_OWNER_AUTHORIZATION_20260816.md)
> **时序纪律：** 本文件及其输入 manifest 必须先于任何定理正文、checker、收据和终局主张进入独立 Git 提交；后续结果不得原地修改本判据。若发现判据错误，只能新增 erratum 或后继协议，不能回写门槛迁就结果。

## 1. 批目标

本批只回答两个固定问题：

1. 在钉死的 W0 binding contract 中，是否可以不依赖实验日志、仅凭 52 个 generic-output 席位与 34+18 的精确需求，证明 `boundary_port_041:out:0` 在每个合法绑定中都必须活动；
2. 若答案为是，能否与已存在的条件式定理 `J-W0-GHOST-FRONT-BOUNDARY-041-V1` 组合，证明固定 W0 布局下固定矩形 `R=[1,6]×[51,57]` 不存在合法 binding+routing witness。

它不检验其他布局、其他矩形、通用家族、production lowering、认证或全局最优性。

## 2. 定理二验收

定理二必须形成与实验一同形的五件套，并同时满足以下条件。

### 2.1 范围

- 只量化钉死 W0 输入下的 binding selection；
- 问题、目标、上下文、规则、候选池、mandatory instances、generic I/O、固定布局与固定矩形均由 [`01_CONTEXT_MANIFEST.json`](01_CONTEXT_MANIFEST.json) 的 SHA-256 绑定；
- “合法绑定”必须显式定义为：52 个命名 generic-output 席位各从 `{blue_iron_ore, source_ore, __unused__}` 选择恰好一个标签，并满足全局精确计数 `Σblue=34`、`Σsource=18`；
- 不把 CP-SAT 的搜索顺序、实验输出、1007 次观测或某个 solver 终态写进定理前提。

### 2.2 条件与结论

- 条件不得偷带目标结论；应为上述固定 binding contract 的合法性条件；
- 结论必须是：每个合法绑定都满足 `boundary_port_041:out:0 != __unused__`，即 `Active_041(b)`；
- 不得把结论扩大为其他 slot 必活动、其他布局同样成立或 adjudicated game 的无条件事实。

### 2.3 证明

证明必须从下列两条独立计数链闭合：

1. 固定布局、mandatory instance metadata 与 candidate pool 共同重导 generic-output 席位全集，得到 46 个 boundary slots 加 6 个 protocol-core slots，共 52 个，且包含唯一目标 slot `boundary_port_041:out:0`；
2. canonical recipes、commodity metadata 与 266 个 mandatory exact instances 重导 external-boundary 需求 `blue_iron_ore=34`、`source_ore=18`，并与 pinned `generic_io_requirements.json` 逐项相等。

随后只允许使用有限计数：

\[
\sum_s blue_s=34,\qquad
\sum_s source_s=18,\qquad
blue_s+source_s+unused_s=1,
\]

对 52 个 slot 求和，推出 `Σunused=52−34−18=0`；由每个 `unused_s∈{0,1}` 推出所有 slot 的 unused indicator 都为 0，特别是 slot 041 必活动。

任何一步若得到 slot 数不是 52、需求和不是 52、目标 slot 不在全集、域不含且仅含三个标签，或重导需求与 generic I/O 不一致，定理必须 fail-closed。

### 2.4 独立 checker

checker 必须：

- 只使用 Python 标准库；
- 不 import `src/`、Phase -1 harness、金丝雀 runner、OR-Tools 或实验一 checker；
- 从钉死字节重新读取并重数 52/34/18；
- 核验所有承重输入 SHA-256 与 size；
- 独立执行算术证明；
- 至少杀死以下负变体：少一个 slot、多一个 slot、需求总和 51、目标 slot 缺失、recipe coefficient 漂移、stale input hash；
- 缺文件、JSON 重复键、非有限数字、类型漂移或字节不符时 fail-closed；
- 生成带下列顶层八字段的收据：`result_kind / outcome / subject_identity / verified_scope / authority_basis / granted_effects / non_implications / contract_identity`。

### 2.5 事后覆盖

1007 份 W0 selection journal 只可作为 `POST_HOC_OBSERVATIONAL_ONLY` 覆盖材料：

- 必须核对冻结 prefix hash、记录数和 1007 个互异 selection digest；
- 必须复算 1007/1007 记录均显示 `boundary_port_041` 活动；
- coverage 可关闭而核心证明仍 PASS；
- coverage 不得成为 52/34/18 证明前提。

## 3. W0 终局主张验收

终局文书只有在定理一与定理二 checker 均 PASS 后才可给出 `PROVED_EXCLUDED_RESEARCH`。它必须显式写出以下 lift。

### 3.1 组合链

1. 定理二：对每个当前 W0 binding-contract 合法绑定 `b`，`Active_041(b)`；
2. 定理一：在同一 problem/objective/context 与固定矩形下，`Active_041(b)` 蕴含不存在 canonical predicate-5 routing witness；
3. 因此：不存在同时满足当前 W0 binding contract 与 routing predicate 的 `(b,r)`；
4. 所以固定布局 `W0-ALIGNMENT` 与固定矩形 `R=[1,6]×[51,57]` 在声明的研究模型作用域内被排除。

### 3.2 路径级忠实性义务

从槽级算术到固定矩形排除的每条实现映射必须单列义务、证据和状态，至少包括：

- 输入身份进入 binding model；
- 52 个物理 generic-output slot 的枚举完整性；
- 每 slot 三标签 ExactlyOne；
- 两条全局精确需求等式；
- 非 `__unused__` label 到活动 source terminal 的映射；
- `__unused__` 不导出 source terminal；
- routing precheck/solver 消费相同 port specs 与 strict-empty rectangle；
- 定理一、定理二的 problem/objective 与 W0 布局、矩形身份一致；定理二 context 必须被证明为在定理一 base context 上只增加 binding-contract 前提的结构化扩展，组合时显式使用前提弱化／context transport，不得只比较名称或裸 hash；
- 当前 research harness 没有绕过该 binding model 的第二入口。

其中 source implementation、A_BASELINE model snapshot 和 harness 路径可作为“模型忠实性/路径闭合”的证据，但不得反向充当定理二的数学前提。任一承重路径义务未关闭时，终局主张只能是 `CONDITIONAL`，不得写 `PROVED_EXCLUDED_RESEARCH`。

### 3.3 终点候选账

typed-null 纪律不可破坏：当前 `L=ABSENT`，故全局 `M_t` 仍为 `N_A_NOT_READY`，不得虚构一个数值基线。

本批允许并要求登记一个候选级非零交易：

```text
subject rectangle: (x=1,y=51,w=6,h=7)
research candidate state: UNKNOWN -> PROVED_EXCLUDED
unresolved candidate mass without lower bound: ΔM_bottom = -1
canonical M_t: N_A_NOT_READY -> N_A_NOT_READY
```

证据类型必须标为 `EXACT_SINGLETON_EXCLUSION_BY_COMPOSED_THEOREMS`。这是一笔固定候选的研究面排除，不是 research upper ledger、production exact-status 或 certified frontier 的写入。

### 3.4 与金丝雀的关系

- W0 unary-lowering 金丝雀的冻结判词继续是 `INCONCLUSIVE`；
- 本批不得修改、重算或“纠正”该历史判词；
- 新终局主张来自独立的静态算术定理与定理组合，不是用后见信息把 C 臂 timeout 改判为 solver `INFEASIBLE`；
- 可以说明新定理解释了 C 臂为何面对一个数学上空的残余域，但该解释是后续研究结论，不倒签成金丝雀当时已经观测到的终态。

## 4. 非蕴含硬边界

最终 Judgment、收据和终局文书必须全部列明：

- 不改 `data/solutions/exact_full_scale_status.json`；
- 不写 `data/knowledge/claims.jsonl`；
- 不产生 production `CERTIFIED`、publisher、supervisor 或 release 效力；
- 不解冻通用 D3/D4；
- 不授权 production lowering 或 theorem registry 常态化；
- 不外推其他布局、其他矩形或完整 adjudicated-game 最优性；
- 不把 current-model binding restriction 冒充完整游戏语义；
- 不回改实验二金丝雀的 `INCONCLUSIVE`；
- 不把 1007 条 journal 当数学证明。

## 5. 提交与登记

- 第一笔提交只允许包含本验收判据、owner 授权记录、输入 manifest 与目录入口；
- 定理正文、checker、收据和终局主张必须位于后续提交；
- 禁止 amend；提交标题使用仓库中文 `type(scope)` 惯例，并带 `Co-Authored-By: GPT-5.6 Pro <noreply@openai.com>`；
- 批尾以精确 pathspec 将新 tracked dossier 登记进 inventory，刷新生成投影；
- 活树 intake、doctor、knowledge 必须归因检查。本批引入的 BLOCK 必须清偿；并行写窗的在途目录不得被本批擅自登记或改写。
