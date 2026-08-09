# B1 Phase 5 — Cell-Level Cut + A Priori Port Clearance (3 form 全 over-restrictive)

> **历史失效标记（Batch 4，2026-07-18）**：本文的 47,666 个约束、十个
> `INFEASIBLE@47–56s`、相关旧 front 数字及据此得出的判词检查了错位 front，
> 已撤销（MAY-02）。关于“master 不知道最终 active port、假定全部 port active
> 会超杀”的量词结论不依赖该坐标错误，仍然保留（MAY-03）。详见
> [历史重判附录](../../../front_offset_incident_20260718/01_historical_rejudgment_addendum.md)。

## 当时项目情况

B1 Phase 4 routing convergence 发现 port-clearance 是 cut 方向. 实验 3 种 cut form.

## 为什么走这条路

试 cut form 强化:
1. Cell-level reactive (mutual exclusion)
2. A priori hard mutual
3. A priori hard channeled-OR implication

paradigm: 让 master 直接知道 "port front 不能被堵".

## 实验过程

3 个 form 实测 (env `EXACT_B1_PORT_CLEARANCE_HARD` 等):

| form | 约束数 |
|---|---|
| Cell-level reactive (per iter) | 加 1587 cuts (5 iter) |
| A priori hard mutual `sum(port) + sum(front) <= 1` | 47666 |
| A priori hard channeled-OR `any_port + sum(front) <= 1` | 47666 + K1 channeling |

跑 6 anchor + 4 small candidate (10-20×10-15).

## 实验结果

3 form **全 over-restrictive**:

| form | 实测 |
|---|---|
| Cell-level reactive | 5 iter 加 1587 cuts, blocked_ports 仍 519-611 浮动**不收敛**. 切掉合法解 (多 facility 共享 port_cell) |
| A priori hard mutual | 6 anchor + 4 small candidate **全 INFEASIBLE in 47-56s** |
| A priori hard channeled-OR | 同 INFEASIBLE 47s, sound form 但仍 over-approximation |

## 经验跟教训 (含瓶颈理解更新)

- **Root cause**: master 不知 binding 选哪些 port active. binding 阶段每 facility 5-7 个 port 选其中**一部分**, 没接的 port 前面被堵不影响.
- a priori clearance 把 "所有 port 必须 active" 当 hard → 自然 INFEASIBLE.
- **瓶颈理解更新**: routing precheck 本身就是这种 over-approximation. 实际 routing CP-SAT 可能能 solve some layouts (bypass routing precheck trial 跑 42 min binding enumerate stuck 不可定论).
- **Phase 6 要做的**: 改 master/binding 责任边界, 让 port 选择从 binding 提到 master.

## code/

- `code/` 含 phase5_production_trial.py
- 实施: `shared_infra/src/models/pose_bool_exact_master.py` 内 `add_routing_port_blocking_cell_cut` 方法
