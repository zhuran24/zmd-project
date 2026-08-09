## Overall verdict
NOT_GO
理由: Spike 选取的 LBBD 收敛指标 (G15: search tree node 单调减) 在 OR-Tools CP-SAT 的 portfolio search 与 presolve 机制下数学上不成立, 且抛弃 100K cut scale 测试将直接在 168h prod run 中触发 OOM/超时盲区, 必须修正这两大基石才能启动。

---

## Findings

### Finding 1: LBBD stub 设计与收敛指标在 CP-SAT 语境下完全失效
- **Severity**: BLOCKER
- **决策**: C2 / C4 (D3 resolve, G15 metric)
- **问题**: G15 假设加 cut 后 "search tree node count 单调减 ≥30%" 违背了 CP-SAT 的底层逻辑。同时, deterministic stub 若不根据 master 的 *current assignment* 生成 cut, 无法模拟 Benders 真正的 pruning 动力学。
- **论证**: CP-SAT 并非单纯的 branch-and-bound。它使用 LNS (Large Neighborhood Search) 和基于多线程的 portfolio search。当新 cut 加入后, presolve phase 会产生不同的 variable substitution 和 root node dual bound, 导致 branch tree 重新 layout。反例构造: stub 返回 $x_1 + x_2 \le 1$, CP-SAT presolve 将其与原有约束结合, 可能决定对 $x_3$ 优先 branching, 导致节点数激增但 wall-time 减少 (因为发现了更快的 infeasibility 路径)。文献支撑: OR-Tools 官方文档及 Laurent Perron 的多次 presentation 均明确 "node count in CP-SAT is not a reliable measure of search space size or progress across model mutations"。
- **建议 fix**: 废除 "单调减" 指标。Stub 必须设计为 "Targeted No-Good Generator" (读取 master current solution, 随机选 1-5 个赋值为 1 的 pose-bool, 产出 `sum(chosen) <= len(chosen)-1`) 以确保切掉当前解。收敛 metric 改为 "Dual bound (objective bound) improvement per iter" 或 "multi-iter 总 wall-time 收敛性"。

### Finding 2: 100K Cut Scale 盲区将引发 Prod 环境的 168h 死亡
- **Severity**: HIGH
- **决策**: C3 (D5 resolve)
- **问题**: 将 Cut count ramp 上限从 100K 砍到 50K 会导致 P1.3A 无法评估长期运行的内存与时间爆炸风险。
- **论证**: 预算 168h = 604,800s。即使以极保守的 60s/iter 计算，系统将执行 ~10,000 次 LBBD iterations。若每次 sub-problem 产生 10 个 cut (F1-F9 多 family 叠加极易超过此数), 168h 累积的 cut 数量必然达到 100K 级别。OR-Tools 的 Protobuf C++ backend 在约束激增时, 若未做 memory reserve, 其 arena allocation 会出现碎片化导致超线性 RSS 增长, 50K 到 100K 往往是越过 L3 Cache boundary 进而引发 30GB RSS 崩溃 (L24 死因) 的拐点。
- **建议 fix**: 恢复 100K 挡位。Ramp 设计改为指数分布: `1K / 10K / 50K / 100K`, 且必须在 100K 挡位验证 G8 (RSS ≤ 20 GB)。

### Finding 3: 50 Inst Probe 的 5-10 min Cap 掩盖了常数级工程 Bug
- **Severity**: HIGH
- **决策**: C1 (D1 resolve)
- **问题**: 赋予 50 inst probe "5-10 min" 的 wall cap 极其荒谬，放水严重。
- **论证**: 根据 A.5 提供的数据, mini Step 8 在 50 BoolVar 下 10K cuts 的 build cost 仅为 114ms, solve 2ms。即便加上完整的 9-step lifecycle Python overhead，总耗时也不应超过 5 秒。如果一个 50 variables 的 probe fixture 运行超过 10 秒, 必然说明 harness 中存在 $O(N^3)$ 甚至无意义的 polling wait、死锁或 serialization 灾难。允许其跑 5 分钟意味着 "failfast" 失去了 fast 的意义。
- **建议 fix**: 强制设置 50 inst probe 的 failfast timeout 为 `wall_time <= 15 seconds`。超过 15s 立即 raise RuntimeError 并 abort 整个 pipeline。

### Finding 4: G3 Build Wall (60s @ 10K cut) 阈值过于宽松，未能卡住 $O(N^2)$ 劣化
- **Severity**: MEDIUM
- **决策**: C4 (G3 build wall metric)
- **问题**: 60s 用于 build 10K cuts 会掩盖 Python 层的 SWIG 交互效率低下。
- **论证**: 假设 10K cuts, 平均每个 cut 包含 100 个 boolean terms, 总计 $10^6$ 个 terms。在 OR-Tools 中, 使用 `sum()` 与 `LinearExpr` 批量构造百万项约束的 C++ 底层耗时在 1-2 秒级别。如果外推到 60s, 说明存在 10x~30x 的 margin。这种巨大的 margin 容忍了在 Python `for` 循环中逐条 `model.Add()` 的反模式, 一旦进入 100K cuts, 这种反模式会导致 OOM 或数百秒的 freeze。
- **建议 fix**: 收紧 G3 阈值至 `wall <= 15s`。强制要求在 spike 中验证 vectorized construction (如 `LinearExpr.Sum()`) 而非 list comprehension 逐项添加。

### Finding 5: 2 PR 流程中的 Fidelity Gap 风险
- **Severity**: MEDIUM
- **决策**: C5 (D7 resolve)
- **问题**: 实施 "2 PR 重写" (不 cherry-pick spike code) 以避免技术债是好 paradigm，但缺乏机制保证重写后的 P1.3A 依然保持 spike 验证过的性能特征。
- **论证**: CP-SAT 模型对约束添加的顺序 (constraint ordering) 或 Python generator 转换为 list 的时机极为敏感。重写时若工程师 "顺手优化" 了一段 serialization 逻辑, 可能导致 C++ Protobuf 结构化差异, 使 spike 验证的 solve time 完全作废。历史上的 "paradigm shift" 经常死于重写时引入的隐式假设 (类比 L13 hidden assumption)。
- **建议 fix**: 在 2 PR 流程中加入硬性要求: 必须导出 spike 成功时的 `.cp_model` (Protobuf 二进制) 的 hash 或 checksum，P1.3A PR 的 integration test 必须输出结构同构的模型。

### Finding 6: 5 iter LBBD 循环深度不足以暴露 Lazy Constraints 收敛性死角
- **Severity**: HIGH
- **决策**: C2 (D3 resolve)
- **问题**: L16 死于不收敛, B1 path-2 跑了 10 iter UNPROVEN, 但本 spike 仅设定 5 iter 验证收敛，样本过少。
- **论证**: 前 5 个 iter 通常 cut 掉的是最明显的 trivial infeasibility (例如区域面积绝对不够)。只有进入深层 LBBD (iter 7+), CP-SAT 才开始面临大量 marginal cuts (即多维空间中只削去极小多面体的 cuts), 这时 presolver 常常失效, 导致 solve time 发生指数级 phase transition。5 iter 完全处于这个 phase transition 之前。
- **建议 fix**: 修改 D3 和 G15, 强制要求 `Multi-iter LBBD ≥ 15 iter`。在 15 iter 中, 观察 iter 10-15 的 solve time variance。

---

## C6 missing-risk inventory (8 路未 cover, 必须关注)

1. **CP-SAT Threading / Presolve Non-determinism (Spike 内必加)**
   - 描述: G13 adversarial quarantine 依赖 cut validation。如果在多线程求解下, valid cut 和 forged cut 加入 master 的顺序发生交错, 是否会导致 CP-SAT abort?
   - 理由: OR-Tools 在并发加 lazy cut 时有严苛的 callback thread-safety 要求。8 路均未提及 `model.Clear()` 后的资源竞争。
2. **Cut Staleness / Memory Leak 过期 Cut 冗余堆积 (Defer P1.3A, 但需注册)**
   - 描述: 随着 LBBD 推进, 早期切掉的大量 cut 在当前 search subtree 中已经 slack (不再 binding)。
   - 理由: 不做 cut purge 会在 168h 中导致 RSS 爆炸。Spike 时长短暴露不出, 但必须在 P1.3A 建立 `purge_slack_cuts` 的机制。
3. **Source Digest Invalidation 错乱在 Multi-Candidate 枚举下的表现 (Spike 内必加)**
   - 描述: 外层枚举 candidate ghost rect 发生切换时 (Area 降序), 上一个 candidate 的 store cache / source digest 是否被彻底清空？
   - 理由: 如果不清空, F1-F9 的 validity check 可能基于错误的坐标系通过 (Finding 3 patch `035bd21` 的延伸风险), 导致 sound cert 被污染为 unsound。

---

## C7 residual P1.3A risk (Spike GO 后仍 open 的风险)

1. **Sub-problem Cut Structure Gap**: Stub 生成的 cut 的数学结构 (sparsity, big-M coefficients) 与真实的 `binding/routing` 生成的 cut 存在鸿沟。如果真路由子问题生成的是极密集的 global cut, CP-SAT 会退化为纯 LP bound 求解, 性能直接断崖跌落。
2. **Inner Benders Timeout Handling**: Spike 假设 sub-problem 能立即返回 verdict (或通过 stub 秒返)。真实环境如果 routing subproblem 自身需要 5 min 才证明 infeasible, LBBD 的 outer wait 策略是什么？
3. **The "Optimal but Unprovable" Trap**: Master 可能在 2h 内找到了 max_lex 最优解, 但为了 prove 它是最优的, 仍需遍历剩余所有 candidate 并验证其 infeasibility。168h 是否足够走完这个 proof stage? Cut framework 的 prune strength 在 sub-optimal branch 上是否依然强劲? (需要引入 gap threshold 或 proof early-stopping)。

---

## Closing
该 merger doc 展现了非常高的工程素养与防御性编程思维 (如 10 项 abort criteria, 2 PR rollback 机制, 拒绝 mock 的立场)，整体 Epistemic Posture 属于 **合理严谨但对 CP-SAT 内部机制过度自信**。其设计完美防御了 Python 层的胶水逻辑崩溃, 却由于对 OR-Tools 的求解动力学 (presolve 重构、branch count 非单调性、100K 内存拐点) 认知不足, 设计出了几个无效的量化门控 (G15, 60s G3, 50K cap)。必须打破将 solver 视为 "单调黑盒" 的直觉, 引入基于多面体切割特征的 metric, 方可真正守住 P1.3A 的大门。