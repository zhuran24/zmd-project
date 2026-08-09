# Gemini 3 Pro cross-check verdict — Prod-scale spike MERGER (Round 2)

**Date**: 2026-05-26
**Model**: `gemini-3-pro-preview`
**Source files**:
- prompt: `prompt.txt`
- request: `request.json`
- raw JSON: `gemini_response_raw.json`
- text reply: `gemini_response.md`

**Note**: round 2 agent 撞 API socket error in final tool call, 4/5 file landed
(prompt/request/raw/response 全 OK), verdict.md 由 main 主对话直接 read response 整理.

---

## 1. Gemini overall verdict

**NOT_GO**, 但 Gemini 显式说 "无需 Round 3 漫长拉扯, 4 finding 1-line fix 后直接实施 spike".

理由 (原话): "核心交付流程的保真度校验机制 (F5 Protobuf hash 比对) 因 OR-Tools 变量索引生成的非确定性在数学上注定失败 (必产 false-negative 阻断 PR), 且 LBBD stub 设计 (单 iter 仅产 1 条 cut) 使得 15 iter 动态压测形同虚设, 必须修正这两个机制 bug 才能放行."

---

## 2. Finding count

| Severity | Count | IDs |
|---|---|---|
| BLOCKER | 1 | Finding 1 (F5 protobuf hash compare 数学不成立) |
| HIGH | 2 | Finding 2 (stub 单 cut/iter 退化空转), Finding 3 (wall-time 假收敛盲区) |
| MEDIUM | 1 | Finding 4 (G16 物理级 leak 校验不彻底) |
| Missing-risk | 2 | Q8.1 (SWIG memory leak), Q8.2 (GIL callback blocking) |

---

## 3. Round 1 fix verification table (8 finding)

| Round 1 Finding | Fix 内容简述 | Round 2 verdict | 论证 |
|---|---|---|---|
| F1 (G15 wall-time + stub) | 废弃 node count 改 wall-time 收敛, stub 改 targeted no-good | **PARTIAL** | Wall-time 规避 presolve 干扰, 但未校验 Objective Bound, 易被 "cut 导致快速 Infeasible" 假收敛欺骗; stub 逻辑正确但密度太低 (Finding 2/3) |
| F2 (100K cut 恢复) | 加 G4b 600s, G9 1GB, N3 RSS 30GB | **CORRECT** | 100K × 100 terms ≈ 120MB, 1GB proto 阈值安全; 600s build 容忍超线性膨胀 |
| F3 (G17 probe 15s) | 加 50 inst probe ≤ 15s 超时 abort | **CORRECT** | 50 inst 15s (均摊 300ms/inst) 完美契合 failfast 语义 |
| F4 (G3 30s 折中) | 81K + 10K cut build wall 30s | **CORRECT** | Python SWIG 边界 9 family dispatch overhead (~50K 次 C++ 调用), 30s 留 2-3x margin |
| F5 (proto hash compare) | PR #2 必 emit 同结构 Proto() hash compare | **INCORRECT** | `NewBoolVar()` 按调用顺序递增分配 Integer Variable Index, PR #2 重构必改 ID, hash 100% 报错 (Finding 1 重写为 semantic invariant check) |
| F6 (15 iter LBBD) | 5 iter 升 ≥15 iter | **PARTIAL** | 15 iter 足够触 phase transition, 但前提是每 iter cut batch 规模 (Finding 2 stub 单 cut 让 15 iter 失效) |
| C6.3 (G16 跨 candidate) | snapshot diff 验 watcher cleared / source_digest / 无 leak | **PARTIAL** | 逻辑层 store.snapshot() 看不见 Python 闭包 / SWIG C++ 底层 dangling references (Finding 4 补物理级 gc.collect() + RSS 波动 ≤ 5%) |
| C7 (residual P1.3A risk) | 3 项 residual risk 入 P1.3A risk register | **CORRECT** | 边界清晰, 符合 spike 职责划分 |

**汇总**: 8 finding fix verdict — 4 CORRECT / 3 PARTIAL / 1 INCORRECT. 3 个 PARTIAL/INCORRECT 全 mechanical fix.

---

## 4. Round 2 new finding (4 + 2 missing-risk)

### Finding 1 BLOCKER — Protobuf hash 比对注定失败 (F5 INCORRECT)
- 针对: Q7 (F5 fix verify)
- 问题: `cp_model.Proto()` raw byte hash 校验 PR #2 重写保真度不可行. PR #2 必涉及循环展开 / 函数提取 / 约束重排, NewBoolVar 顺序变 → 变量 ID 变 → hash 必失败. 100% false-negative 阻断 PR.
- Fix: 改 **Semantic Invariant Check**:
  - `len(variables)` 严格等
  - `len(constraints)` 严格等
  - 固定 random seed 下 `master.ResponseProto().objective_value` + `status` 严格一致

### Finding 2 HIGH — Stub cut 密度过低 15 iter 压测失效 (F1b/F6 PARTIAL)
- 针对: Q2 / Q4 (F1b / F6 fix verify)
- 问题: 当前 stub `sum(x[g,p] for selected) ≤ len-1` 每 iter 仅 1 条 global no-good cut. 15 iter 累积 15 cut, master presolver 几乎 0 overhead, wall-time 压测退化空转.
- 论证: 真 binding/routing subproblem 单 iter 返 batch cuts (违反 capacity/path 各 1 条, 可达百条). 单 cut/iter 模拟不到真 LBBD 密度.
- Fix: stub 每 iter 返 **Batch Cuts**: 1 条 global no-good + 50-100 条从 selected_pose 随机采样的 subset no-good

### Finding 3 HIGH — Wall-time 假收敛盲区 (F1 PARTIAL)
- 针对: Q1 (F1 fix verify)
- 问题: 仅依赖 wall-time 下降作收敛指标, 易被 "cut 导致快速 Infeasible" corner case 欺骗. Cut 跟现有约束直接冲突时 Presolver 在 root node 瞬间证 Infeasible, wall 骤降 0.1s 满足 "wall 下降 30%" 但实际模型崩了.
- Fix: G15 加 Objective Bound 校验:
  - `master.ResponseProto().best_objective_bound` 单调不减
  - 所有 15 iter status ∈ {OPTIMAL, FEASIBLE}

### Finding 4 MEDIUM — 跨 candidate 内存泄漏校验不彻底 (C6.3 PARTIAL)
- 针对: Q5 (C6.3 fix verify)
- 问题: G16 仅通过 `store.snapshot()` 检查逻辑层 watcher entries cleared, 无法捕获 Python dangling references / SWIG C++ 真内存泄漏. 3 candidate 切换可能隐式 OOM.
- Fix: G16 补物理级校验:
  - 强制 `gc.collect()` 后断言 `sys.getrefcount()` 属 candidate N 的大对象实例数 = 0
  - OR RSS 波动 ≤ 5%

### Q8 missing-risk (round 2 新 catch)

**Q8.1 SWIG memory leak on repeated model modification (CP-SAT 9.15)**
- OR-Tools `cp_model` 非设计为 "长生命周期 + 动态增量加 100K 约束". 反复 `model.Add()` 100K 次可能触发 SWIG wrapper 隐式内存泄漏 (C++ 对象已释放但 Python proxy 未回收).
- 处理: spike 必加. G8/N3 已隐式 cover, 在 N3 显式标注 "监控 SWIG proxy leak".

**Q8.2 Callback blocking (GIL / 线程锁死)**
- 若 targeted no-good stub 通过 `cp_model.SolutionCallback` 注入, Python 层 callback 持 GIL block 底层 C++ search workers, 多线程 portfolio 失效, wall 暴涨.
- 处理: spike 必加. §5.3 NOT-scope 显式 "采用 Outer-loop LBBD 模式, 禁用 SolutionCallback".

---

## 5. Gemini Next-step 推荐 (原话)

"**无需 Round 3 漫长拉扯**. 请 Merger 直接在本地应用 Finding 1-4 的 1-line 修正
(改 hash 为 semantic check, 改单 cut 为 batch cuts, 加 objective bound check),
更新 commit 后即可**直接实施 Spike**."

---

## 6. Agent (Claude) 自评 sanity check

### Round 2 finding 跟 round 1 + 8 路 sibling blind spot 对比

- **Finding 1 (F5 INCORRECT)**: 真 BLOCKER + Gemini 数学论证扎实 (`NewBoolVar` 顺序敏感性是 OR-Tools 实测行为). round 1 F5 fix 是 main merger 自己提的, 我 8 路 sibling 0 cover protobuf 内部行为. fix 简单 (改 semantic invariant), 1-line edit.
- **Finding 2 (F1b/F6 PARTIAL)**: 真 HIGH, 但我之前没意识到 "stub 单 cut 跟 15 iter 互锁" — F1 fix (stub targeted no-good) 跟 F6 fix (15 iter) 都是 round 1 各自 fix, 没联系起来想这两个 fix 在一起退化空转. fix 直接 (batch cuts).
- **Finding 3 (F1 PARTIAL)**: 真 HIGH, Gemini 论证扎实 (presolver root-node 瞬间 infeasible 是 OR-Tools 实测行为). fix 简单 (加 objective_bound 单调不减 check). 
- **Finding 4 (C6.3 PARTIAL)**: 真 MEDIUM, 跟项目 latency-bound (per [[project-workload-latency-bound-not-bandwidth]]) + Python SWIG bindings 风险一致. fix 加 gc.collect() + RSS 波动 ≤ 5%, trivial.
- **Q8.1 (SWIG leak)**: Gemini 提了之前 round 1 / 8 路 sibling 都没 cover 的 OR-Tools 9.15 Python bindings 底层 C++ 内存管理. 跟 [[project-workload-latency-bound-not-bandwidth]] 互补. 加 N3 监控 trivial.
- **Q8.2 (GIL block)**: Gemini 提了 LBBD 模式选择 (Outer-loop vs SolutionCallback inner-loop) 我之前没明确. 加 NOT-scope trivial.

### Verdict 信号

Round 2 NOT_GO 但 Gemini 自己说不需 round 3. 我倾向**接受**: 4 finding 全是 mechanical fix (改 metric / 加 batch / 加 check / 加 gc), 不涉及 paradigm 重设. fix 完后 spike 实施可启动. 强行 round 3 会陷入 [[gemini-prompt-audit-mode]] "GO 章 ritual" 反面.

---

## 7. 推荐主对话下一步

按 Gemini 建议:

1. **直接 fix 4 finding + 2 missing-risk 进 MERGER** (mechanical edit):
   - §5.1 F5 fix: protobuf hash → semantic invariant (vars/constraints count + objective_value + status)
   - §5.2 + §5.4 G15b: stub 改 batch cuts (1 global + 50-100 sampled)
   - §5.4 G15: 加 objective_bound 单调不减 + status ∈ {OPTIMAL, FEASIBLE}
   - §5.4 G16: 加 G16b 物理级 gc.collect() + RSS 波动 ≤ 5%
   - §5.5 N3: 加 SWIG proxy leak 监控
   - §5.3 NOT-scope: 加 "禁用 SolutionCallback, 严守 Outer-loop LBBD"
2. **Commit** (按 round 1 fix 同 message 风格).
3. **不开 round 3** (Gemini 显式建议 + 4 fix 全 mechanical).
4. **Spike 实施开始** — 按 final MERGER spec spawn opus closed-loop agent, branch `spike/prod_scale_master_integration_20260526`, 7-day cap, 20-29h Claude / 5-9h wall.
5. **若 spike 实施期间发现 round 2 fix 自己有问题** → 暂停, 重 Gemini round 3 verify.
