# F5 Orbit Lift Soundness Design v1 对抗审查报告

审查范围：仅基于 `f5_prompt_adversarial_review.md` 与 `f5_orbit_lift_design_v1.zip`。目标文档为 `docs/research/p1_3_f5_orbit_lift_soundness_design_v1.md`。

结论：当前设计文档的定理 2 不能直接进入 certified path。主要原因不是 P-HOM 数据本身失败，而是 oracle reject 的量词和 master 端 cut 表达没有被封成 soundness 前提。已提供统一补丁 `f5_orbit_lift_design_review.patch`，并生成修订后的完整文档 `docs/research/p1_3_f5_orbit_lift_soundness_design_v1.review_fixed.md`。

## 复核事实

1. `mandatory_exact_instances.json` 全量按 `(facility_type, operation_type)` 分组后，除 `instance_id` 外逐字段同质。实测 266 条记录、19 个组，P-HOM 违例数为 0。
2. 本包未包含运行时消费的 `candidate_placements.json`，只能从 `placement_generator.py` 证明候选池按 template 生成的意图，不能证明实际 artifact 未漂移。
3. 文档里的组合计数有两个数值错误：8 个 `manufacturing_3x3` 组的 `log10(34!²·18!·17!·11!·6!³)=123.470892`，不是约 `10^105`；`(34)_8 = 34·33·...·27 = 732,058,145,280`，不是约 `2×10^12`。
4. `pattern_nogood.py` 的 validator 禁止重复 `(group_id, slot_index)`，但允许同一 `(group_id, pose_id)` 通过不同 slot 重复出现。
5. `lifecycle.evaluate_literal_multiset()` 按 `(group_id, pose_id)` 计数，语义上是 multiplicity-aware；但 `exact_coordinate_master.add_benders_cut()` 路径存在 boolean presence nogood 形态，且 `_conflict_pose_entries()` 对重复抽象 presence fail-closed，不能直接承载重复 `(group, pose)` 的 F5 cut。
6. oracle adapter 协议是 `query(core, state, deadline)`。如果 adapter 读取 core 外的当前 incumbent 信息，例如 `selected_poses`、`cell_owner`、routing blocker 或 binding 选择，得到的 `INFEASIBLE` 只是 “core 加当前 state 上下文不可行”，不是 “任意扩展 core 都不可行”。这会破坏轨道提升定理 2 的量词。

核验脚本输出摘要：

```text
P-HOM mandatory_exact_instances groups: 19 records: 266
P-HOM violations modulo instance_id: 0
log10 Π n_g! for 8 manufacturing_3x3 groups: 123.470892
log10 Π n_g! for all mandatory groups in bundle: 243.503916
(34)_8 = 34·33·...·27: 732058145280
toy context-dependent oracle FP: reproduced
toy multiplicity-collapse FP: reproduced
```

## BLOCK-1：定理 2 缺少 “closed-core / liftable reject” 前提

问题：原文把 oracle 对带标签 pattern `π₀` 的 `INFEASIBLE` 直接提升为任意完整解的不可行结论。但源码里的 oracle adapter 形状允许 `query(core, state, deadline)` 读取当前 state。若不可行性依赖 core 外的 blocker、已选 pose、binding/routing 上下文或搜索边界，那么它不是轨道不变的 pattern reject。

最小反例：同一 core `{(g, slot0, poseA)}` 在 state S1 中因为外部 blocker `(h, poseQ)` 被判不可行；在删除 blocker 的 state S2 中可行。F5 cut 只记录 core 多重集，所以会在 S2 中仍然触发，剪掉合法解。这是 false positive。

影响：这直接使定理 2 的 soundness theorem 无效，属于 BLOCKER。

修复：补丁将 §2.3 改为 “liftable reject” 命题，明确 oracle 的 `INFEASIBLE` 必须证明 “任何完整解只要扩展 `π₀` 的任一带标签代表都不可行”。adapter 不得把 core 外 mutable state 当成 reject 语义的一部分；若证明需要这些信息，必须把它们提升为 core literal，或禁止该 verdict 生成 F5。§4 新增 `query_liftable(core, immutable_scope, deadline)` 契约，§6 将该问题从开放问题升级为 BLOCK 前提。

## BLOCK-2：master attach 若折成 boolean presence，会丢失 multiplicity

问题：定理 2 说 cut 的触发条件是 pose 多重集包含 `[π₀]`。多重集要求保留重复次数。当前 validator 允许两个不同 slot 使用同一 `(group_id, pose_id)`；而既有 master whole-layout nogood 机械是 boolean presence 风格。如果把重复 `(g, pose)` 当作一个 presence literal，`multiplicity=2` 的 cut 会退化成 `present(g, pose)`，把只出现一份该 pose 的合法解也剪掉。

最小反例：正确 cut 是 “同组至少两个 slot 都选 pose p 时不可行”。boolean presence attach 会变成 “至少一个 slot 选 pose p 时不可行”。后者严格更强，能制造 false positive。

影响：如果 F5 直接复用 boolean presence nogood，这也是 soundness BLOCKER。

修复：补丁在 §2.3 和 §4 加入二选一约束：A) validator 禁止重复 `(group_id, pose_id)`，把这类几何平凡真交给 no-overlap / F6；或 B) master 提供 cardinality-aware attach，为每个 `(group, pose)` 建 count/threshold literal，例如 `count_g_pose ≥ m`，再施加 `Σ threshold_lits ≤ r-1`。在没有 B 之前，A 是更小的安全落地方案。

## CONCERN-1：规范重标定义不足，minimize 后可能留下 slot gap

问题：`canonical_sort_assignment()` 当前只按 `(group_id, slot_index, pose_id)` 排序并去重，不会把删除后的 slot gap 重标为 `0..k-1`。如果文档声称 “按 pose_id 字典序占用 slot 0..k-1”，实现必须真的 relabel，而不是仅排序。

影响：主要是去重和证书稳定性问题；通常不直接制造 false positive，但会让同一轨道重复生成 cut，使 F5 重新撞墙，也会造成 replay/cert canonical drift。

修复：补丁 §4 定义 idempotent `canonical_relabel(pattern)`：逐组按 `(pose_id, occurrence_serial)` 排序，把占用 slot 重标为 `0..k_g-1`。generator 初始 full assignment、deletion minimizer 每个 trial core、oracle query 输入和最终 cert 存储都必须先过该函数。validator 增加 `cert == canonical_relabel(cert)` 检查。

## CONCERN-2：P-HOM 门不能只检查 mandatory JSON，必须覆盖实际 pose pool artifact 和 digest

问题：本包的 mandatory 数据通过了 P-HOM，但 master 实际消费 `candidate_placements.json`。审查包没有提供该文件，因此不能把 “pose 池无 instance 维度” 写成已证事实，只能写成需 preflight 机器化验证的前提。

影响：若运行时候选池出现 per-instance 字段或漂移，定理 1 的谓词不变性会断裂。

修复：补丁 §2.2 和 §4 要求 P-HOM checker 覆盖 mandatory 全记录、operation profiles、实际 `candidate_placements.json.facility_pools`，并把 `orbit_homogeneity_digest` 注入 certified preflight 与 cut replay scope。缺失 digest、digest 漂移、候选池 artifact 缺失或新增 per-instance 字段都 fail-closed。

## CONCERN-3：CP-SAT `symmetry_level=3` 不能被当成建模层第二全序

问题：文档讨论 master order_key 与对称序复合安全，但审查指令特别要求关注 CP-SAT `symmetry_level=3`。源码中 binding solver 会提高 CP-SAT internal symmetry 参数。它是 solver 搜索/预处理策略，不是持久建模约束；安全性依赖消费 solver status 的方式。

影响：只要 `TIMEOUT/UNKNOWN` 是 no-cut，并且只有可复验 `INFEASIBLE` 才产 cut，内部 symmetry 不构成第二全序问题。若未来把 solver 内部 symmetry 产物外显为约束、hint-to-constraint，或把 timeout 当 exhaustion proof，则需要重证。

修复：补丁 §2.4 明确 CP-SAT 内部 symmetry 不属于 F-GM-R8-SYM-01 的建模层 order；§2.3 和 §4 明确 `TIMEOUT/UNKNOWN/contract violation` 全部 no-cut / quarantine。

## CONCERN-4：组合计数段落需要修正公式和口径

问题：原文的 `C(n,k)·k!·|pose|^k` 把 literal 顺序又数了一遍，与后文缩减因子 `n!/(n-k)!` 不一致；数字 `10^105` 和 `2×10^12` 也不准确。

影响：不直接影响 soundness，但会误导验收指标和问题规模评估。

修复：补丁 §1.1 与 §5 改成两种口径：允许重复 pose 时，带标签空间为 `C(n,k)·P^k`、轨道商为 `C(P+k-1,k)`；禁止重复 `(group,pose)` 时，带标签空间为 `C(n,k)·(P)_k`、轨道商为 `C(P,k)`，缩减精确为 `n!/(n-k)!`。

## NOTE-1：P-HOM mandatory exact 数据本身未发现违例

全量数据通过同组 modulo `instance_id` 的逐字段一致性检查。该事实支持定理 1 的数据侧前提，但不能替代对 runtime pose pool artifact 和 adapter closure 的证明。

## NOTE-2：定理 2 的注入证明可以补严

在加入 liftable reject、无 slot 复用和 multiplicity 保真后，轨道提升证明可以成立。补丁 §2.3 给出了逐组注入和补全到 `S_{n_g}` 的证明文本。

## 产物说明

- `f5_orbit_lift_design_review.patch`：统一 diff，可作为文档修复补丁。
- `docs/research/p1_3_f5_orbit_lift_soundness_design_v1.review_fixed.md`：应用补丁思想后的完整修订文档。
- `verify_f5_review_claims.py`：复核脚本，包含 P-HOM、计数和两个 toy FP 复现。
- 本报告：结构化 BLOCK / CONCERN / NOTE 审查结果。
