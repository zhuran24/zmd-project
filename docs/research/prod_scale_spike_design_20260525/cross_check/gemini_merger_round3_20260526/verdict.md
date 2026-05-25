# Gemini 3 Pro cross-check verdict — Prod-scale spike MERGER (Round 3)

**Date**: 2026-05-26
**Model**: `gemini-3-pro-preview`
**Token usage**: prompt 3473 / response 2404 / thoughts 2320 / total 8197
**MERGER commit**: `b44d0c6` (含 round 1+2 fix + 2026-05-26 user scope creep shrink)
**Source files**:
- prompt: `prompt.txt`
- request: `request.json`
- raw JSON: `gemini_response_raw.json`
- text reply: `gemini_response.md`

---

## 1. Gemini overall verdict

**NOT_GO**

理由 (Gemini 原话): "Shrink 后的 Scope 极其精准, 但 G6 的 FEASIBLE 强校验与
随机 Cut 注入在数学上互斥, 且单次 Pass 导致 G11 的 Age Decay 逻辑物理失效,
必须进行 Mechanical Fix 才能防止 CI 必挂."

Gemini 自评 round 3 跟 round 1/2 不同: "在 Build/Memory 维度可以完美 close,
但在 Solve/Filter 维度存在物理级语义断层, 会导致 CI 必然失败或数据无意义."

---

## 2. Finding count by severity

| Severity | Count | IDs |
|---|---|---|
| BLOCKER | 1 | G6 FEASIBLE vs random cut 互斥 (Q9 #1) |
| HIGH | 1 | G11 Filter age decay 单 pass 无法触发 (Q9 #2) |
| MEDIUM | 0 | — |
| LOW | 0 | — |

Plus 语义降级判定 (Q8): spike GO ≠ Finding 5 close 完全等价, 只是必要不充分
条件 — Gemini 建议**接受**此 semantic gap, 不强求等价 (强求会让 scope 又
膨胀回 P1.3A).

---

## 3. Finding 5 cover verification table (Gemini Q1)

| GPT pro Finding 5 需求 | Spike 对应 step/scope | GO criteria | Cover 度 | Gemini 论证 |
|---|---|---|---|---|
| **#1 真规模 master var** | Master scale (81,795 BoolVar toy master) | G1-G4b | **Partial** | Build 成本准 (Proto+SWIG 跟 prod 一致), Solve 成本不准 (toy 缺 ExactlyOne/Implication/port-linking, LP relaxation 太松, 分支树形态完全不同) — 只能作 lower bound |
| **#2 真 cut body 分布** | Real oracle ≥45 cert + toy translator | G10 | **Full** | 真 protobuf 序列化 + AddLinearConstraint 复杂度被真实还原 |
| **#3 测 build/solve/RSS/ByteSize** | Cut count ramp + 基本 telemetry | G1-G9 | **Full** | 物理级 metric 采集完整 |
| **#4 active filter / rotation** | Active filter sizing | G11 | **Partial** | 单 pass 无法触发 age_decay, 只 verify filter 自身计算开销不验 eviction 策略动态行为 |
| **#5 feasible realistic case** | Feasible smoke | G5, G6 | **Broken** | G6 逻辑自相矛盾 (见 Q9 BLOCKER) |

**汇总**: 5 项 = 2 Full / 2 Partial / 1 Broken. BLOCKER 在 #5 (G6 内部互斥),
HIGH 在 #4 (G11 age decay 失效). #1 Partial 是 spike 跟 PoseBoolExactMaster
固有差距 (Q8 接受), 非缺陷.

---

## 4. Round 3 specific finding 详情

### BLOCKER: G6 FEASIBLE vs random cut 数学互斥

**问题**: G6 要求 10K cut feasibility wall ≤ 180s + status OPTIMAL/FEASIBLE
+ 不能 INFEASIBLE 早停. 但 10K cuts 是从 45 真 cert sample/ramp 出来,
toy master 缺真变量互斥约束 (ExactlyOne / Implication / port-linking), 强行
注入 10K 真 cuts 极大概率 Presolve 阶段直接证 INFEASIBLE.

**后果**: CP-SAT 0.1s 内返 INFEASIBLE → G6 失败 → spike CI 必挂. 不是 toy
master 写错, 是数学上 toy + random cut 组合天然不可能 FEASIBLE.

**Fix (Gemini 给的 2 选 1)**:
- Option A: G6 允许 INFEASIBLE 但前提 `wall_time > 1.0s` (证明经过实际
  propagation 不是 trivial presolve 瞬间空集)
- Option B: 10K 挡位**只注入** Feasible Smoke case 提取的 known-feasible
  cuts (不 random sample)

### HIGH: G11 Filter age decay 单 pass 无法触发

**问题**: 单 Build/Solve 架构无 LBBD 循环. Filter 函数只调用一次, `age`
变量永远不递增, `0.1 * age_decay` 永远 0. G11 实际只测 `activity_count` 排
序, 未 verify Hybrid score 核心逻辑.

**Fix**: Active filter sizing step 强制写**纯 Python mock loop** (`for i in
range(10):`), loop 内随机增 activity + 递增 age, 只测 filter 函数 100ms
性能 + eviction trigger. **不挂 CP-SAT solve** → 不违反 "不跑 multi-iter
LBBD" NOT-scope, 又真 verify Hybrid 公式.

### Q8 semantic gap (非 finding 但需文档化)

Spike GO ≠ Finding 5 close 数学等价, 只是必要不充分条件:
- **真等价**: spike 失败 → prod 必失败 (e.g. 100K cut OOM)
- **降级**: spike 成功 → 只代表 "物理容量达标", **不代表** "100K cut 下
  能收敛" (收敛需 P1.3A 主体 multi-iter LBBD + PoseBoolExactMaster)

Gemini 建议: 接受此 gap, 文档化 "spike close Finding 5 *Sizing* 目的, 不
close *Convergence* 目的". 强求等价会让 scope 膨胀回 P1.3A.

---

## 5. Round 1/2 fix shrink 后仍有效性 (Gemini Q5 + Q7)

| Round 1/2 fix | shrink 后是否仍有效 | Gemini 论证 |
|---|---|---|
| R2-F3 (objective_bound + status check, G6) | **YES** 仍必要 | 单 solve 也防 "假 solve" — status=UNKNOWN + bound 空说明 10K cut 让 Presolve 陷死锁/数值不稳, 是 Build 物理缺陷信号 |
| R2-Q8.1 (SWIG monitor, N3) | **YES** | 100K cut 仍可能触发 SWIG proxy leak |
| R2-Q8.2 (禁 SolutionCallback) | **YES** | NOT-scope 仍正确 |
| R1-F2 (100K cut 恢复) | **YES** | G4b 600s 安全 (Gemini 算: 100K×100 terms ≈ 120MB, 1GB proto 阈值安全) |
| R1-F3 (G17 probe 15s) | **YES** | 失效不影响 |
| R1-F4 (G3 30s 折中) | **YES** | Python SWIG 9 family dispatch overhead 30s 留 2-3x margin |
| R1-F1 + R2-F2 (LBBD metric / batch cut) | **N/A** | shrink 删除 LBBD multi-iter 段, fix 无须考虑 |

工时 8-12h Claude / 4-7h wall: **Gemini verdict 合理且偏保守 (安全)**. 主要
wall 占 50K/100K CP-SAT 求解 (G4b 600s, G7 no cap).

---

## 6. Agent (Claude) 自评 sanity check

### Round 3 finding 真新还是 round 1/2 cover?

- **G6 互斥 (BLOCKER)**: **真新**. Round 1/2 都没 catch. Round 1 F1 改了
  G15 LBBD metric, Round 2 F3 加 objective_bound check, 都没 hit "random
  cut + toy master = 必 INFEASIBLE" 这个组合层 issue. 因 round 1/2 假设
  scope 含 LBBD multi-iter, cut 是渐进加 (前几 iter 不互斥), 没考虑 single
  build + 10K cut 一次性注入场景. Shrink 改了 scope, 新风险出现.
- **G11 age decay 失效 (HIGH)**: **真新**. Round 1/2 cover multi-iter
  context, age decay 自然 work. Shrink 删 multi-iter, age 永 0 — 这是
  shrink 直接因. Gemini Q3 已 hint 此点 (Q3 说"无法 cover rotation 阈值"),
  Q9 升级到 HIGH finding.
- **Q8 semantic gap**: Gemini 建议接受, 不算 finding. 跟 [[gemini-prompt-
  audit-mode]] 风格一致 — Gemini 不强推完美等价, 接受工程级足够即可.

### Verdict 信号

Round 3 NOT_GO 跟 round 1/2 不同维度: round 1/2 是 CP-SAT internals 数学层
finding (presolve 重排 / protobuf hash / cut 密度), round 3 是 shrink 自身
副作用 (random cut + toy 必 INFEASIBLE / 单 pass age 永 0). 都是 mechanical
fix 不涉及 paradigm 重设.

2 finding fix 全 trivial:
- G6: 选 Option B (注入 feasible-smoke cuts) 更稳, 工时 +0.5h
- G11: 加 10-iter Python mock loop, 工时 +0.5h

Fix 后 spike 可启动. **不建议 round 4** — 跟 round 2 同理, 强行 round 4
陷入 GO ritual.

---

## 7. 推荐主对话下一步

### 必修 (BLOCKER + HIGH, mechanical 1h)

1. **Fix G6** (BLOCKER): 改 MERGER §5.4 G6 — 10K cut feasibility 改为
   "10K cut 从 feasible smoke case (IP v2 blueprint hint) 提取 known-feasible
   cuts 注入" (Option B). 不再 random sample. 若选 Option A (放宽 INFEASIBLE
   但要 wall>1s) 是退路.
2. **Fix G11** (HIGH): 改 MERGER §5.2 Active filter sizing + §5.4 G11 —
   加 "纯 Python mock loop `for i in range(10):` 内随机增 activity + 递增
   age, 测 filter 100ms + eviction trigger, **不挂 CP-SAT solve**" (不违
   反 NOT-scope multi-iter LBBD).

### 文档化 (Q8 semantic gap)

3. MERGER §5.2 序言加: "Spike GO close Finding 5 *Sizing* 目的 (物理容量/
   建模/测量), 不 close *Convergence* 目的 (100K cut 下能否收敛). 后者需
   P1.3A 主体 multi-iter LBBD + PoseBoolExactMaster, defer."

### 后续

4. 2 fix commit (按 round 1/2 fix 同 message 风格, mechanical 标注).
5. **不开 round 4** (跟 round 2 同, 全 mechanical).
6. Spike 实施启动 — 按 final shrunk MERGER spec spawn opus closed-loop
   agent, branch `spike/prod_scale_master_integration_20260526`, 7-day cap,
   **8-12h Claude / 4-7h wall** budget.

---

## 8. 主对话备注

- Gemini 没 push back 的 shrink 决策 (隐含 GO):
  - Q2 toy master Build/Memory 100% 复用 (Solve 不复用是 acceptable trade-off)
  - Q4 删 adversarial inject 不影响 Finding 5 cover
  - Q6 G11 阈值合理 (100ms/iter @ 100K + 双 trigger)
  - Q7 工时 8-12h Claude 合理
- 没有 ritual GO — 2 finding 全 specific + 数学论证扎实 (G6 INFEASIBLE
  数学论证 / G11 age 0 物理论证), 不是 vague hyperbole
- Round 3 跟 round 1/2 不同维度 — shrink 自身副作用 finding, 不是 CP-SAT
  internals 加深. 此种风险只有在 user scope creep audit 完触发 shrink 后
  才会浮现, [[gemini-review-algorithm-math]] v2 "每 commit cross-check"
  在 shrink commit `b44d0c6` 后立刻 round 3 正好 catch — 验证了 v2 加严的
  价值.
- 此 round 验证了 [[gemini-prompt-audit-mode]] "armor" prompt 模式 — round 3
  prompt 明示"不接受 vague claim", Gemini 给的 finding 全带量化论证 (G6
  presolve 时序 / G11 age=0 物理推断), 没出现"我认为"/"经验"等 vague 措辞.
