# Candidate D (Path 17) Phase 0 + 0b verdict — 2026-05-20

## 结论

**🎯 Phase 0b D2 ✅ GO** — 第一次 Phase 0 cheap gate 真 GO 的 paradigm.

D1 (轻版本: u vars + cell capacity + port adherence) 5/7 anchor FEASIBLE, 跟
production routing precheck 无增量.

D2 (D1 + arc vars + channeling + flow conservation) **7/7 eligible anchor INFEASIBLE
in 0.05-0.15s**, vars 全在 cap 内.

paradigm 真有 connectivity-level 增量信号: production routing precheck + D1 cell
capacity 都看不到的 commodity flow imbalance, D2 detect 出来.

## Phase 0 D1 ❌

| anchor | D1 status | wall | u_vars | cstr |
|---|---|---|---|---|
| interior_22_28 | INFEASIBLE | 0.01s | 23,389 | 1,312 |
| interior_10_10 | FEASIBLE | 0.03s | 12,217 | 666 |
| interior_44_30 | FEASIBLE | 0.04s | 12,217 | 661 |
| interior_15_40 | INFEASIBLE | 0.04s | 22,629 | 1,311 |
| corner_0_0 | (master INFEASIBLE, no capture) | — | — | — |
| small_10x10 | FEASIBLE | 0.13s | 8,341 | 458 |
| small_15x10 | FEASIBLE | 0.07s | 7,657 | 420 |
| small_15x15 | FEASIBLE | 0.06s | 9,785 | 533 |

**D1 verdict**: 2/7 INFEASIBLE, 5/7 FEASIBLE — paradigm 在 D1 cheap version 上无
增量信号. cell capacity 对 binding-solved port_specs (binding 已避开 port-port
conflict) 不能 detect 出 INFEASIBLE.

## Phase 0b D2 ✅

| anchor | D1 → D2 transition | D2 wall | D2 vars (u+e) | D2 cstr |
|---|---|---|---|---|
| interior_22_28 | INF → INF | 0.08s | 23K+78K=102K | 181K |
| interior_10_10 | **FEA → INF** | 0.05s | 12K+36K=48K | 84K |
| interior_44_30 | **FEA → INF** | 0.08s | 12K+37K=49K | 87K |
| interior_15_40 | INF → INF | 0.12s | 23K+61K=83K | 145K |
| corner_0_0 | (master INFEASIBLE, no capture) | — | — | — |
| small_10x10 | **FEA → INF** | 0.15s | 8K+17K=26K | 44K |
| small_15x10 | **FEA → INF** | 0.10s | 8K+18K=26K | 45K |
| small_15x15 | **FEA → INF** | 0.09s | 10K+25K=35K | 60K |

**D2 verdict**: **7/7 eligible anchor INFEASIBLE in 0.05-0.15s**. 全 anchor 资源:
- max total vars = **102K** (cap 250K, **2.5x under**)
- max constraints = **181K** (cap 650K, **3.6x under**)
- max wall = **0.15s** (budget 600s, **4000x under**)

paradigm 自身资源**远低于** cap. RSS 整 process 累积 13-19 GB 是 master+binding+Python
interpreter 累, 不是 D2 自身.

## D1 → D2 关键 finding

D1 上 FEASIBLE 的 5 anchor (interior_10_10, interior_44_30, small_10x10/15x10/15x15)
在 D2 上**全部变 INFEASIBLE**.

意味着 D2 加的 **flow conservation** 提供了 D1 看不到的信息. 具体 INFEASIBLE 原因:
某 commodity 的 source ports 数跟 sink ports 数不平衡, 或 source-sink 之间 grid
上 active cells 形成 net flow 在 cell capacity 约束下不可行.

这是 production routing precheck (只看 port-front-clear + component reachability) +
D1 (只看 cell capacity) **都看不到的 connectivity-level paradigm 信息**.

## 跟之前 5 paradigm 比较

| paradigm | Phase 0 verdict | end-to-end |
|---|---|---|
| Path 12 RAB-SEP | (no Phase 0) | breakthrough ❌ |
| Path 13 SAC-Hull | GO | breakthrough ❌ |
| Path 14 PCR-CUT | GO | breakthrough ❌ |
| Path 15 PGW-UB | NO-GO (no locality) | — |
| Path 16 GOC-C2 | NO-GO (RAM 爆) | — |
| **Path 17 D2** | **GO ✅** | 待 Phase 1 测 |

**D2 是第一次 Phase 0 cheap gate 拿 GO 的 paradigm** since paradigm investigation
started. 之前 Path 13/14 也 GO 但 end-to-end breakthrough fail; Path 15/16 直接
Phase 0 fail.

## Phase 0 GO ≠ paradigm 真 work

Phase 0 只验证: **D2 model 自身能在 budget 内 detect INFEASIBLE**. paradigm 真
work 必须:

1. D2 INFEASIBLE → 生成 cut, 反馈 master pose-bool 维度
2. master 加 cut → 给新 layout, 多 iter 后真给 routing-feasible layout

cut form (per Phase 1 设计) 仍是 instance-pose conjunction (跟 RAB-SEP cert 同类型).
RAB-SEP 实测 8/8 anchor UNPROVEN — cut tight 但切空间 ≪ 1%. D2 cut 是否同病, 需
Phase 1 multi-anchor campaign 测.

Phase 1 投资估 5-10h Claude + 1-2h trial.

## 设计 limitations + future 增强方向

### D2 当前限制

1. **没分 layer** — production routing 含 ground+elevated 2 层 (bridge 跨过). D2
   只用 ground layer 简化. 后续 D3 加 layer 重新评 vars (× 2).

2. **flow conservation 假设 commodity net flow** — 实际 production routing 含 splitter/
   merger (1→多 / 多→1), D2 简化为 sum 净流. 可能漏 detect 某些 splitter-specific
   冲突.

3. **没接 owner-pose 选择条件** — 当前 D2 model 用 binding-solved port_specs (一个
   pose 选择). 跟 master pose 之间没 conditional. Phase 1 实施时, cut 需 conditional
   on (instance_id, pose_idx).

4. **terminal demand 假设 1 per port** — 跟 production demand 一致 (per port 1 belt).
   未来 generic IO 可能 > 1.

### 增量信号源

D2 INFEASIBLE 的具体原因 (Phase 1 要 extract 出来给 master cut):
- multi-port-cell collision: 多 port 共享同 front cell 但不同 commodity (D1 已 detect)
- flow conservation imbalance: 某 commodity 的 source/sink 总数 不一致 (D2 新)
- bottleneck cell: cell capacity 不够支撑全图 commodity flow (D2 新)
- disconnected components: source 跟 sink 不在同一 grid component (D2 新)

cut 应基于 INFEASIBLE 原因生成 minimal owner-pose subset.

## 实测投入

- Phase 0 D1: 1 文件 ~340 LOC trial, 1.5h wall
- Phase 0b D2: 1 文件 ~400 LOC trial, 30 min wall
- 总: ~2h Claude pace (含 D1 bug fix iteration), ~2h wall
- 节约: paradigm 真 NO-GO 早识别避 Phase 1 浪费 5-10h Claude work; paradigm GO 信号
  正面早确认 投资 Phase 1 ROI 高

## commit

`a4b8341` (Path 16 GOC-C2 verdict, 之前 commit)
- TBD (本 Phase 0/0b D2 verdict)

## Related

- Path 17 phase 0 + 0b files: phase0_candidate_d_probe.py + phase0_candidate_d2_probe.py + stats jsons
- GPT v7 plan Candidate D 数学描述 reference (in v7 plan, 但未在本包内 inline)
- BOTTLENECK_STRUCTURE.md "3 类资源 dead end" — D2 落在 Ω(K|V|+K|E|) 区域, 实测在 cap 内
