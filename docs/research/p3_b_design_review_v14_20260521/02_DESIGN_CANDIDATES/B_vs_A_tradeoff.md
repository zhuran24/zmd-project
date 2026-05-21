# B vs A — Tradeoff 对比 (项目方判断 + 仍欢迎 stress test 反驳)

## 对比表

| 维度 | Design A (cand C + cut language) | Design B (feature-level engine) |
|---|---|---|
| **Master form** | LP set covering + pricing CP-SAT + B&P (cand C) | 自研 state machine (不用通用 solver) |
| **Cut variable space** | λ-space (column weights) | placement variable space + cell bitset |
| **Cut 表达力上限** | 线性 (Σ_k a_k λ_k ≤ b 形式) | 任意可计算 predicate (含 connectivity / projection) |
| **复用范围** | cand C Phase 0/1/2 ~80% | cand C ~40-50% + 死路 paradigm 当 oracle |
| **96% utilization 应对** | LP 0 iter infeasible — 加 cut 不救 | bitset propagation 早期识别 → sound cut |
| **boundary trap 应对** | LP relax 无 natural perimeter constraint 表达 | port exposure cut 直接编码 |
| **实施成本** | ~3 weeks | ~3-5 month |
| **实施风险** | 中 (在已死 paradigm 加工程) | 中-高 (paradigm-level 投资 + bitset kernel 选型) |
| **现 cut language 范畴** | **已穷尽** (v3 实测) | 跳出范畴 — 新 cut family 直接编码几何 invariant |
| **paradigm 风险** | 高 (已 NO-GO, 升级 cut 无 leverage 在 LP 0 iter inf) | 中 (第 6 类 cut 风险 → stress test 预判) |

## 项目方判断 (送审稿前结论)

**Design B 严格 stronger 是因为**:

1. **cand C v3 撞的是 master form 的墙, 不是 cut language 不够**
   - LP 0 iter infeasible at 160/266 inst 即使 bootstrap fill 218/324 column
     cover all instance
   - LP relax 在 96% utilization 下 cell exclusivity vs exactly-1 cover
     dual 不兼容 — 加 cut 不让 LP 变可行
   - → 修不了 LP 范畴的 master form

2. **27 lever 已经验过 master form 替换是可解锁路径**
   - B1 paradigm 从 coordinate master 30 min UNKNOWN → pose-bool master
     53s OPTIMAL 跨数量级
   - 但 B1 pose-bool master 解锁后 cut framework 6 paradigm 撞同墙 (sub-problem
     cut 翻译退化 instance-pose conjunction)
   - → master form 决定 cut 表达力上限. 不重写 master form, cut framework
     表达力被锁

3. **现 cut language 升级方向 27 lever 都 cover**
   - Path 13 SAC-Hull (corridor Menger min-cut) ~ "perimeter capacity cut"
   - Path 17 D2 (commodity cell-flow) ~ "component reachability cut"
   - Path 14 PCR-CUT (patch routing core) ~ "cutset cut"
   - 6 paradigm 全 verdict 死 cut 表达力被 master 锁
   - → cand C 加这些方向同类 cut 也大概率撞同墙

4. **B 设计的 5 cut family 直接编码几何 invariant**
   - region capacity, cutset, port exposure, component reachability,
     pattern no-good, symmetry-lifted
   - 这些 cut family 在 LP 范畴需要 lift 到 column subset 的 meta-property
     (LP variable 爆炸); 在 B 的 placement variable + bitset 范畴是直接
     编码
   - → 表达力 step change 不是 incremental

## 反驳 channel (欢迎 stress test 提出)

项目方判断**不是 final**, 仍欢迎 stress test 反驳. 主要反驳 channel:

### 反驳 1: cand C v3 0 iter infeasible 是 bootstrap 不够好, 不是 LP 不可行

可能的反驳数据:
- v3 bootstrap layer 1 (`solve_direct_mini_master` 60s) 仍是 mini-master
  替代 pricing, 不是完整 pose pool
- 如果 bootstrap 加 Vanderbeck-style "primal heuristic + perturbation
  loop" 可能拿到 LP-feasible column pool
- → 加 column 而不是加 cut 可能突破 0 iter infeasible

项目方回应: cand C v3 已 land 3-layer bootstrap (Layer 1+2+3) + n_columns
= 324 cover all 266 inst, 仍 LP infeasible. 不像 column 太少的问题.

### 反驳 2: B 的 5 cut family 不完备 → 需要第 6 类

如果你能构造 "恶魔构型" 使得 5 类都不能切, B 设计需要补.

项目方回应: **这正是 stress test 的目的**, 不是反驳, 而是修正 B 设计. 如
果第 6 类要补, 修计划包含补 cut 即可.

### 反驳 3: B 设计 paradigm-level 投资过高

3-5 month investment vs A 的 3 weeks. ROI 不对.

项目方回应: 27 lever 全死 + cand C 也 NO-GO 后**没有 3 weeks 选项了**. 选
A 是相对低成本但**预期 NO-GO** (撞同墙); 选 B 是高成本但**有可能突破**.
预期值 calculation 偏 B.

### 反驳 4: 推 Design B 是基于不完整 evidence

主对话 Gemini fat-context 推 B 严格更好, 但 Gemini 可能 bias / 缺
ground truth.

项目方回应: stress test (此包) 就是 second opinion / 独立审稿. GPT 如果
看完包后 verdict 不同, 项目方愿意重新评估. 包没有展示 Gemini verdict 内
容防止 prior bias.

## 跟 cand C 完全废弃的关系

选 B 不代表 cand C 完全废弃:

- **保留 cand C Phase 1 ~80% LOC** 当 sub-problem oracle (pricing CP-SAT
  + region multi-facility generator + cache infra)
- **保留 cand C Phase 2 v3 bootstrap** 当 B 的 alternative blueprint
  generator (在 master state machine 的某个 decision point 调 cand C
  oracle 推 candidate poses)
- **Ryan-Foster branching** 不复用 (跟 B 的 state machine decision schema
  不兼容)
- **Set covering RMP** 完全废弃 (B 不在 LP 范畴)

→ cand C investment 没浪费, 部分组件复用. 详 reuse 清单
`03_B_DESIGN_DETAILS/reuse_from_cand_c.md`.

## Stress test 的预期反馈

不希望 stress test 输出 "我同意项目方判断" — 那是低价值答复. 希望 stress
test:

- **反驳**: 给出具体反例 + 数学论证 (e.g. 5 cut family 不完备的 case)
- **修正**: 给出 B 设计的具体修正 suggestion (e.g. 加第 6 cut family
  / 改 cut store schema / 改 bitset kernel 选型)
- **验证**: 给出形式化论证 5 cut family 完备 (e.g. 引用 Chvátal-Gomory
  closure / Lovász theta function 等 textbook 结果)
- **新方向**: 给出 B 之外的 third option (项目方没考虑到的 paradigm)

形式化论证比 "我觉得" "可能" 价值高得多. 不可达必须给 lower bound /
complexity reduction / resource inequality, 不准 "I believe / intuition".
