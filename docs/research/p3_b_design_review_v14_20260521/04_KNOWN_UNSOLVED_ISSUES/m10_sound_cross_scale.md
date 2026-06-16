# Known unsolved issue: m10 sound 性临界跨规模

## 现象描述

cand C Phase 2 v3 metric m10 = "integer reconstruction match" — 即 RMP
LP optimal 解 round 到 integer 后, 是否 set partition exactly-1 covered
(`check_set_partitioning` strict).

实测跨 ramp:

| Ramp | m10 | Notes |
|---|---|---|
| 5inst | **False** | 3 iter exit no_negative_rc, integer round fail (size-scaled m10 threshold relaxed) |
| 20inst | True | 70 iter, RF + std fallback used |
| 40inst | True | 92 iter, RF + std fallback used |
| 80inst | **False** | 100 iter no_negative_rc, integer round fail |
| 160inst | False | RMP 0 iter infeasible (m10 不 applicable) |
| 266inst | False | RMP 0 iter infeasible (m10 不 applicable) |

→ **80 inst 是临界点**. 20/40 GO, 80 失败. 不是单调 size scaling 失败.

## 为什么是 trap

### Trap 1: A3 set-covering vs partition 的临界

A3 (set-covering LP relax: Σ_k λ_k [iid∈k] ≥ 1) 在小规模容易整数化, 在
80 inst 临界点 fail. 根因:

- 5/20/40 inst: pose pool 大, RMP 收敛后 fractional λ 数量少, integer
  round 容易 (RF + std fallback 都 work)
- 80 inst: pose pool 跟 instance 数比例临界. RMP 收敛但 fractional λ 数
  量 ~ 20-30. RF max_depth 10 + rounded_at_cap fallback 都不能保证 partition
  exactly-1.

### Trap 2: 集合 covering 跟 partition 的 sound 分界

PROJECT_LOCK 要求 certified_exact, 即 column generation 在 master 收敛
时 column pool 内**不能丢失任何 mandatory facility constraint**. 实际:

- LP relax 走 set covering (≥ 1)
- Integer reconstruction 要 partition (= 1)
- 这两者在 80 inst 临界点 **不等价** (over-cover 是 LP feasible 但
  partition infeasible)

m10 strict validator (`check_set_partitioning`) 看到 over-cover →
ValidationError. v3 实施 RF branching on over-cover (强制 λ_k 上限 0
某些 column) 试图 fix. 80 inst 上 fail.

### Trap 3: 8 worker × 100 iter 的临界

cand C 80 inst ramp 100 iter exit at no_negative_rc. iter 数已经撞 100
(默认 max iter), RMP 收敛但 integer round fail. RF tree depth 也撞
max_depth 10.

→ 这是 cand C 的 "scaling wall": 80 inst 是 RF + std + A3 + 100 iter 都
撞 cap 仍 fail 的 size.

## 跟 B 设计的关系

B 不在 LP 范畴, m10 这个 metric 不直接 applicable. 但 B 设计的 sub-problem
oracle 需要 cover m10 等价的 cert:

- 给 placement 是否 layoutable (binding + routing feasible)?
- 若 infeasible, 给出 sound cut

B 的 sub-problem oracle 接口跟 m10 不同 (state-machine-friendly, 不是
LP λ-space). 但 cand C `integer_validator.py` 内 `check_set_partitioning`
strict logic 是 set partition validity check 的 reference, B oracle 可
复用其 validation algorithm.

## 还没解的部分

1. **80 inst 上的 sound check fail 根因**: 是 RF degeneracy, 还是 A3
   relax 太宽? 80 inst RAMP 数据 partially 表明 RF 在 over-cover branch
   时 pair 选无效
2. **80 inst → 160 inst 之间的 gap**: 80 inst m10 False, 160 inst 直接
   RMP 0 iter infeasible. 中间是否还有 100-120 inst ramp 撞另一种 failure?
3. **B oracle 在 80 inst sound 临界上的 behavior**: 同样规模, B 的
   state machine 是否能 cover (因为 B 不走 LP)?

## Stress test 视角

构造恶魔构型起点之三: 选 ~80 个 mandatory instance, 分布跟实际 5/20/40
ramp 同 type proportion (132/49/46/38/1 等比缩到 80 = 40/15/14/11/1 等).
不要全 manufacturing 不要全 boundary, 让 type 多样.

观察:
- cand C v3 在此 layout 实测 m10 False 跟 v3 phase2_results.json 80inst
  一致
- B 设计的 state machine + 5 cut family 是否能在此 layout 拿到 certified
  feasible / certified infeasible verdict?

若 B 也 fail at 80 inst sound 临界, **5 cut family 不完备** — 需要补
第 6 类 (e.g. cross-instance sound consistency cut 强制 integer projection
exactly-1).

若 B 在 80 inst 上 work 但 160/266 上 fail, root cause 是 algorithm
scaling 不是 sound 性问题 — Phase plan 调整 phase 5+ scaling.

## 跟 cand C 实测的 cross-reference

cand C Phase 2 v3 80inst data (从 phase2_results.json):
- m1 generated columns: ~6800 iter 100 之后
- m2 pricing p95 wall: ~25-40s (估)
- m5 multi-facility col %: 83.9%
- m10: False ← key
- m11 nodes: ~5000 (估)
- m14 RF/std: 1.54

这些数据 stress test 可作为对照, 验 B 设计在同样 80 inst 配置下是否能拿
verdict.
