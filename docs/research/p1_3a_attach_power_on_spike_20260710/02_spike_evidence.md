# P1.3A attach 通电 spike——判决证据(2026-07-10 深夜)

## 判决:GO(效度边界内)

prod-scale(266 mandatory 实例,70×70,C1 coordinate master)+ 10K cut 直调 `step_8_apply_to_master` 的对照实验,全部判据远低于 GO 线(总 wall 退化 <50%):

| 指标 | E1' 基线 | E2' 10K cut | 退化 |
|---|---|---|---|
| solve | OPTIMAL @513.5s | **OPTIMAL @534.8s** | **+4.1%** |
| attach 段(纯 step_8 循环) | — | **16.55s** | — |
| cut 生成+三重预验(计时区外) | — | 3.9s+3.4s | digest memoize 生效 |
| build(core+master) | 27.0s | 26.2s | 持平 |
| **总 wall(build+attach+solve)** | **540.5s** | **577.6s** | **+6.9%,GO 线 810s** |
| branches | 4,879,651 | 4,962,462 | +1.7% |
| conflicts | 486 | 1,047 | 绝对量极小 |
| proto 约束数 | 64,597 | 332,726(+268,129) | **约束 ×4.15,solve 仅 +4.1%** |
| proto 变量数 | 30,684 | +59,697 | presence/match 辅助结构 |
| scope 记账峰值 | 40.4G RSS+19.6G swap | 41.6G RSS+19.4G swap | 同域(42G/20G 条款内) |

**核心结论**:①attach 工程通路(step_8→delegate→CpModel.Add)在 10K 量级下开销可忽略(16.6s,含 presence 辅助结构阶梯创建);②CP-SAT 对 4 倍约束量的 presolve/传播消化极好(solve +4.1%);③预验三重(integrity+validator+Step6)成本由 digest memoize 压平(10K 共 3.4s)。断言全过(`coordinate_framework_cut_count` 增量恰 10,000;proto 对照落 JSON)。

## 效度边界(GO 报告必须携带,不得省略)

1. **workload 是数学冗余合成 F5**(static-overlap:同 pose 双 group pattern,被 NoOverlap2D 天然禁止)——测的是 attach/presence/proto/solve 工程开销,**不模拟生产 convergence 语义**(Step 7 在真实 incumbent 上对这些 pattern 恒假)。
2. **harness shim 形态**:GHOST_AGNOSTIC F5 经 harness-only shim(空条件→共享恒真 literal)attach,每条约束多一层 `OnlyEnforceIf(恒真)`;presolve 消化良好(见 solve 退化),但与未来原生 unconditional lowering 不逐位等价。
3. **F5 治理裁决**(规格书 §E2' 拍板):生产通电时 F5 仍走 shadow(三硬门条款有效);本实验借 F5 lowering 形态造 workload,不预演生产 F5 治理。
4. **solve 参数形态**:两轮均用原型参数(automatic/probing1/symmetry1/软cap,第五刀绿配方)——「产品默认 solve 参数(FIXED+probing3+symmetry3)在 C1 上不可用」是 M5 线待解的**独立前置**,不被本 GO 掩盖。
5. **单 rect 单 solve**:6×6 ghost 直建,非 campaign 多 rect 序列;跨 solve 的 cut 池演化/淘汰行为未测(通电线 checklist 项)。

## TRIAGE 移交(通电线处理)

- **agnostic-F5 语义缝**:lifecycle step_8 对 GHOST_AGNOSTIC F5 走无条件 attach 分支(lifecycle.py:1393-1402 传空 condition_lits),coordinate delegate 对空条件直接拒(exact_coordinate_master.py:8050-8051)→ fail-closed RuntimeError。安全无 soundness 问题,但 F5 正式落地时须二选一:delegate 支持空条件,或 lifecycle 禁 agnostic F5 进 step_8。
- cut 修复批遗留:replay 诊断 subset 残留(生产不可达,前批已记)。

## 实验线全记录索引

E1 端到端 exploratory 路线四连死验尸+py-spy 破案+形态修订=`01_spike_spec.md` 追加段;E1'/E2' 原始 JSON+日志+RSS 曲线=`~/m5_runs/spike_e2_*`;harness=`e2_harness.py`(本目录,codex 实现+双向冒烟,shim/断言/计时口径见文件头注释)。

## 下一步(GO 后)

production integration checklist 开工(三硬门保留:F3 纵深原子封口替代/F5 shadow/单 epoch 豁免 ledger);M5 线独立前置(产品默认参数病态归因)排期不变;attach 预算 env 化(E3,规格书原 §2)并入 checklist。
