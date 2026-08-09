## Overall verdict
**NOT_GO**
理由: 核心交付流程的保真度校验机制 (F5 Protobuf hash 比对) 因 OR-Tools 变量索引生成的非确定性在数学上注定失败 (必产 false-negative 阻断 PR)，且 LBBD stub 设计 (单 iter 仅产 1 条 cut) 使得 15 iter 动态压测形同虚设，必须修正这两个机制 bug 才能放行。

## Round 1 fix verification table

| Finding ID | Fix 内容简述 | Round 2 verdict | 论证 (≤2 句) |
|---|---|---|---|
| F1 (G15 wall-time + stub) | 废弃 node count 改 wall-time 收敛；stub 改产 targeted no-good | PARTIAL | Wall-time 规避了 presolve 干扰，但未校验 Objective Bound，易被 "cut 导致快速 Infeasible" 的假收敛欺骗；stub 逻辑正确但密度太低 (见 Finding 2/3)。 |
| F2 (100K cut 恢复) | 恢复 100K 挡位，加 G4b (600s) / G9 (1GB) / N3 (RSS 30GB) | CORRECT | 100K cuts × 100 terms 约 120MB，1GB proto 阈值安全；600s build 容忍了超线性膨胀，能有效 catch 撞 L3 cache 导致的劣化。 |
| F3 (G17 probe 15s) | 加 50 inst probe ≤ 15s，超时 abort | CORRECT | 50 inst 15s (均摊 300ms/inst) 完美契合 failfast 语义，有效隔离 harness bug。 |
| F4 (G3 30s 折中) | 81K + 10K cut build wall 放宽至 30s | CORRECT | 考虑 Python SWIG 边界 9 family dispatch overhead (约 50K 次 C++ 调用)，30s 预留了合理的 2-3x margin，且与 G4 (50K/300s) 线性对齐。 |
| F5 (proto hash compare) | PR #2 必须 emit 同结构 Proto() 并 hash compare 验 fidelity | INCORRECT | OR-Tools `cp_model` 的变量 ID 严格依赖 `NewBoolVar` 调用顺序，任何 PR #2 的代码重构都会导致 ID 偏移，Protobuf hash 100% 报错 (见 Finding 1)。 |
| F6 (15 iter LBBD) | 5 iter 升至 ≥15 iter single candidate | PARTIAL | 15 iter 足够触及 phase transition，但前提是每 iter 注入的 cut 数量必须达到 batch 规模，当前 stub 仅产 1 条 cut 无法形成有效压力。 |
| C6.3 (G16 跨 candidate) | snapshot diff 验 watcher cleared / source_digest / 无 leak | PARTIAL | 逻辑层的 `store.snapshot()` 无法 catch Python 闭包或 SWIG C++ 底层持有的 dangling references 导致的真内存泄漏 (见 Finding 4)。 |
| C7 (residual P1.3A risk) | 3 项 residual risk 入 P1.3A risk register | CORRECT | 边界清晰，符合 spike 职责划分。 |

## Findings (round 2 新 finding, 含 fix verify push-back)

### Finding 1: Protobuf Hash 比对注定失败 (F5 机制缺陷)
- **Severity**: BLOCKER
- **针对**: Q7 (F5 fix verify)
- **问题**: 使用 `cp_model.Proto()` 的 raw byte hash 来校验 PR #2 重写保真度是不可行的。任何代码结构的重构都会改变变量声明顺序，导致 Protobuf hash 不匹配，从而 100% 阻断 PR 流程。
- **论证**: OR-Tools Python API 中，`NewBoolVar()` 会按调用顺序递增分配内部 Integer Variable Index。PR #2 作为重构，必然涉及循环展开、函数提取或约束重排，这会导致变量 ID 映射改变。即使数学模型完全等价，生成的 Protobuf 字节流也会因 ID 不同而 hash 失败。
- **建议 fix**: 废弃 raw hash compare，改为 **Semantic Invariant Check**: 提取 `cp_model.Proto()` 中的 `len(variables)`、`len(constraints)`，并在固定 Random Seed 下比对 `master.ResponseProto().objective_value` 和 `status` 是否严格一致。

### Finding 2: Stub Cut 密度过低导致 15 Iter 压测失效 (F1b 机制缺陷)
- **Severity**: HIGH
- **针对**: Q2 / Q4 (F1b / F6 fix verify)
- **问题**: 当前 stub 设计 `sum(x[g,p] for selected) <= len-1` 在每个 iteration 仅产生 **1 条** global no-good cut。15 iter 仅累积 15 条 cut，完全无法模拟真实 Benders 动力学中的 phase transition。
- **论证**: 真实的 binding/routing subproblem 通常会返回 batch cuts (例如每个违反的 capacity/path 各 1 条，单 iter 可达百条)。若单 iter 仅加 1 条 cut，master solver 的 presolver 几乎没有 overhead，15 iter 的 wall-time 压测将退化为毫无意义的空转。
- **建议 fix**: 修改 G15b stub 逻辑，使其每 iter 返回 **Batch Cuts**：1 条 global no-good + N 条 (e.g., 50-100) 从 `selected_pose` 随机采样的 subset no-goods，以模拟真实 subproblem 的 cut 密度。

### Finding 3: Wall-time 假收敛盲区 (F1 机制缺陷)
- **Severity**: HIGH
- **针对**: Q1 (F1 fix verify)
- **问题**: 仅依赖 wall-time 下降 (iter N+1 ≤ iter N × 1.5) 作为收敛指标，容易被 "Cut 导致模型快速 Infeasible" 的 corner case 欺骗，产生假阳性 GO 信号。
- **论证**: 在 CP-SAT 中，如果新加入的 cut 与现有约束产生直接冲突，Presolver 会在 root node 瞬间证明 Infeasible，导致 wall-time 从数十秒骤降至 0.1s。这满足了 "wall-time 下降 30%" 的指标，但实际上是模型崩了，而非 Benders 收敛。
- **建议 fix**: 在 G15 中增加 Objective Bound 校验：`master.ResponseProto().best_objective_bound` 必须单调不减 (monotonically non-decreasing)，且所有 15 iter 的 status 必须保持 OPTIMAL 或 FEASIBLE。

### Finding 4: 跨 Candidate 内存泄漏校验不彻底 (C6.3 机制缺陷)
- **Severity**: MEDIUM
- **针对**: Q5 (C6.3 fix verify)
- **问题**: G16 仅通过 `store.snapshot()` 检查逻辑层的 watcher entries cleared，无法捕获 Python 层的 dangling references 或 SWIG C++ 对象的真内存泄漏。
- **论证**: 如果某个 callback 或 event handler 意外持有了 `Ghost` 或 `cp_model.Constraint` 的强引用，`store.snapshot()` 的 dict diff 会显示已清空，但底层对象并未被 GC 回收。在 3 candidate 切换时，这会导致隐式 OOM 风险。
- **建议 fix**: 在 G16 中补充物理级校验：Candidate N 切换到 N+1 后，强制调用 `gc.collect()`，并断言 `sys.getrefcount()` 或 `gc.get_objects()` 中属于上一个 Candidate 的特定大对象 (如特定 Ghost Proto) 实例数为 0；或直接校验 RSS 波动 ≤ 5%。

## Q8 missing-risk inventory (round 2 新 catch)

1. **SWIG Memory Leak on Repeated Model Modification (CP-SAT 9.15 风险)**
   - **描述**: OR-Tools `cp_model` 并非为 "长生命周期 + 动态增量加 100K 约束" 设计。在同一个 Python model 实例上反复调用 `model.Add()` 100K 次，可能触发 SWIG wrapper 的隐式内存泄漏 (C++ 对象已释放但 Python proxy 未回收)。
   - **原因**: Round 1 重点在业务逻辑，未深入 OR-Tools Python bindings 的底层 C++ 内存管理边界。
   - **处理**: Spike 必加。当前的 G8 (RSS ≤ 20GB) 和 N3 (100K 挡位 RSS 超线性 trigger) 已经隐式 cover 了这个风险，但建议在 N3 中明确标注 "监控 SWIG proxy leak"。

2. **Callback Blocking (GIL / 线程锁死风险)**
   - **描述**: 如果 targeted no-good stub 是通过 OR-Tools 的 `SolutionCallback` (即 Branch-and-Benders-Cut 模式) 注入，Python 层的 callback 会持有 GIL，直接 block 掉 CP-SAT 的底层 C++ search workers，导致多线程 portfolio 失效，wall-time 暴涨。
   - **原因**: Spike 文档仅写了 "benders_loop 接 stub"，未明确是 Outer-loop LBBD (每次解完重建/热启动) 还是 Inner-loop Callback。
   - **处理**: Spike 必加。必须在 §5.3 NOT-scope 或 §5.2 中明确声明："采用 Outer-loop LBBD 模式，严禁在 spike 中使用 `cp_model.SolutionCallback` 注入 cut，以规避 GIL 锁死"。

## Closing

Round 1 的 fix 整体上极大地提升了压测的真实度 (100K cut 恢复、15 iter 引入、probe 熔断机制均非常精准)，epistemic posture 从 "盲目乐观" 转向了 "量化防御"。然而，**F5 的 Protobuf hash 校验属于对 OR-Tools 底层机制的数学误判**，若不修正将直接导致后续 PR 流程瘫痪；同时 stub 的单 cut 产出也让 15 iter 的动态压测失去了意义。
**Next-step 推荐**: 无需 Round 3 漫长拉扯。请 Merger 直接在本地应用 Finding 1-4 的 1-line 修正 (改 hash 为 semantic check，改单 cut 为 batch cuts，加 objective bound check)，更新 commit 后即可直接 **实施 Spike**。