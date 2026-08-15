# DOC-ADR-006：选择、分离与消费机制坐标

状态：Accepted
日期：2026-08-11

## 背景

`reasoning_profile` 能说明一条结论对候选、模型或实验边界产生什么操作效果，`derivation_profile` 能说明它在数学证明图中的角色，但二者都不能稳定回答一组更具体的问题：候选从哪里来、靠什么策略选中、怎样验证、覆盖是否完备、最终在哪一层被消费，以及与通用 solver 或实验 baseline 的比较是否可识别。

这组区别在 cut framework、RAB/FCL、AB16、低余量发现法和 solver-rethink 设计中反复成为承重边界。一个 validator 能检查给定候选，不等于存在 autonomous separator；typed apply 能消费已知 cut，不等于能发现 cut；预算耗尽、零激活或未到达 producer，也不等于候选空间已经闭包。若仍只把它们写在研究正文里，后续 agent 很容易把 checker、selector、consumer 和 effectiveness 重新揉成一个模糊的“有 cut 能力”。

## 决定

1. claim 增加可选 `separation_profile`，只保存七类机器可查询坐标：
   - `target_stage`：pre-model、candidate generation、model build、search loop、post-solve 或 knowledge-only；
   - `candidate_source`：声明 inventory、显式有限集、隐式组合空间、solver events、外部 supplied candidate 或不适用；
   - `selection_modes`：人工定点、零余量排序、goal-backward search、pairwise closure、有限枚举、完整理论 solver、cut registry replay、raw-event separation、proof-obligation queue 或不适用；
   - `validation_modes`：无独立验证、直接算术、精确枚举、独立 validator、proof object、完整理论 solver、terminal replay 或反例；
   - `completeness`：对声明域已证明、仅相对声明片段、启发式、被反例否证、开放或不适用；
   - `consumption_modes`：model omission、pre-model filter、candidate filter、model constraint、objective bound、diagnostic-only 或 knowledge-only；
   - `baseline_comparison`：无比较、非识别性观察、受控比较或 formal comparison。
2. `separation_profile` 与 statement、premises、status、authority、`reasoning_profile` 和 `derivation_profile` 正交。它描述机制坐标，不授予数学有效性、owner authority 或 production promotion。
3. 候选发现与候选验证必须分开登记。能够验证 supplied candidate，不能因此宣称候选空间覆盖；能够系统地产生候选，也不能省略每条候选的 soundness 验证。
4. 完备性和终止语义 fail closed。预算、深度、未到达或零事件只能保持 `open`、`heuristic` 或 `not_applicable`，不能改写为固定点或不可分离定理。
5. “指定通用传播系统不能得到同样分离”的正式证据仍由 `reasoning_profile.generic_propagation_evidence=formal` 单独控制。`separation_profile.baseline_comparison=formal` 只说明该 claim 的比较口径正式，不自动满足 generic-propagation impossibility 的命题门槛。
6. `REASONING_LEDGER.md` 自动投影选择、验证、完备性、消费与 baseline 分布，并与数学推导图和 backfill review 放在同一查询入口。原始证明、实验记录和实现证据继续留在 dossier 与 evidence 路径。

## 后果

- 领域特定选择策略、通用 solver 对照、候选 validator、typed consumer 和实验 telemetry 可以分别查询，不再靠措辞猜测能力边界。
- agent 能看到“这个结论在哪一层可消费”，减少把 research-only 排除静默升级成 model omission 或 production constraint 的风险。
- schema、generator、架构说明、维护协议、policy 引用和回归测试必须一起演化。
- profile 的存在不证明机制有效或完备。语义审阅者仍需确认 statement、scope、premises、evidence 和 authority。

## 未采用的方案

- **只用 tags 标记 separator/cut/CP-SAT**：能做主题搜索，不能区分候选来源、验证、完备性和消费落点。
- **把 checker、selector 和 consumer 合并成一个 capability 字段**：会重新制造“能验证即能发现、能消费即能生成”的错误等价。
- **只记录实验 cut 数量**：零计数同时兼容未到达、无暴露、全拒绝、预算删失和真正无效，无法承担机制结论。
- **把所有领域排除都标为 generic propagation impossible**：混淆数学有效性与 solver 能力下界，证据门槛不可接受。
