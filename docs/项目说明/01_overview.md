# 01 — 项目概览与认证命题

> 本文描述当前工作树的求解与发布边界。发布状态以根目录
> `PROJECT_LOCK.md` 和 `data/review_gates/phase_1_2_spike_close.json` 为准。
> “支持 certified_exact”不等于“P1.2 已关闭”或“已有可公开 CERTIFIED 交付”。

## 1.1 形式问题

在 `G = {0, …, 69} × {0, …, 69}` 上，给定 266 个 mandatory facility instance、每个
instance 的有限 candidate-pose 集、canonical rules、generic I/O requirements 和
per-instance placement rule，寻找 `(R, π)`：

```text
R 是 G 内轴向矩形；π(i) 是 instance i 的候选 pose
(1) all_cells(π) ∩ R = ∅
(2) 任意两个 instance 的 occupied_cells 不重叠
(3) 每个 instance 的 placement_rule 成立
(4) port binding feasible，且 generic slot exact-count 成立
(5) routing feasible，即每个 routed commodity 的 source/sink fronts 满足有向连通
(6) power coverage feasible，即受电设施被真实存在的供电桩几何覆盖
```

目标是 `max_lex(area(R), min_side(R))`。`min_side >= 6` 是 production 项目的候选
admissibility floor，不是第二目标的替代品。toy project 可在自己的 canonical rules 中显式给出
不同 floor。

## 1.2 `CERTIFIED` 精确证明什么

只有经过 sink replay、fixed-witness terminal verification、
`ExactCampaign.supervisor_seal()`，并通过公开发布闸的结果，才有资格在 public delivery surface
上携带 proof-bearing `CERTIFIED`。此时命题仅为：

1. 发布的确切 `(R*, π*)` 满足上述六个谓词；
2. 完整 admissible candidate frontier 中不存在 lex 更优的可行解；
3. solution、blueprint 和 delivery manifest 来自同一 disk-current supervisor seal。

该命题不证明 belt 离散吞吐、单位时间产率、电网吞吐或任何未列入六谓词的游戏机制。
`flow_subproblem.py` 是连续 LP 诊断器，不门控 certified verdict，也不能单独生成 proof-bearing cut。

超时、预算耗尽、验证材料缺失或 verifier 返回 UNKNOWN 时，正确结论是 `UNKNOWN` / `UNPROVEN`，
不是 `INFEASIBLE`，也不是 `CERTIFIED`。

## 1.3 当前求解与发布链

```text
main.py
  -> outer_search.py
       枚举候选并运行 benders_loop
       terminal success 只提交 CANDIDATE_PROPOSED + replay/fixed-witness material
  -> exact_campaign.py
       [当前无生产 supervisor CLI/launcher]
       supervisor_seal() 需由独立 supervisor 显式调用，从磁盘重读提案并执行 sink replay、fixed-witness 与终端证据复验
       唯一 durable terminal CERTIFIED mint
  -> certified_surface.py
       resolve_p1_2_publish_open_gate()
       publish_verified_certified_delivery_surface()
       唯一公开 certified publisher
```

`benders_loop.py` 内部的 `RUN_STATUS_CERTIFIED` 是单个候选的求解层 verdict，不是 durable campaign
终态，更不是公开发布权。generic serializers、viewer/report builders、IndustrialPlanner adapters 和
compatibility exports 都是派生面，不能自行把数据命名为 certified。

当前 `main.py` 只到 `CANDIDATE_PROPOSED`，仓库没有生产 supervisor 调度入口。因此上图是已实现的
authority API 顺序，不是当前已打通的一键发布流程。

## 1.4 求解内核

默认 certified decomposition 是 placement master → binding → routing。binding 与 routing 是命题 P
的 gating subproblem。whole-layout nogood 在落 exact-safe cut 前还要经过
`independent_infeasibility_reverifier.py`；独立复验不能确认时，不落 cut并返回 UNKNOWN。

`src/cuts/` 中的 F1–F9 cut framework 是受生命周期约束的知识层。部分 family 已有 generator、
validator 和 shadow tests，但 `step_8_apply_to_master` 仍不是当前 production certified integration。
把 cut framework 真正接进主 master 属后续 P1.3，不能因 schema 或单元测试已存在而写成已上线。

## 1.5 `certified_exact` 与 `exploratory`

- `certified_exact` 是唯一有资格产生证明材料的路径，但仍受 supervisor、publish gate 和 owner gate
  约束。
- `exploratory` 只用于启发式、诊断、probe 和研究；历史的 “50 power poles + 10 storage boxes”
  等 cap 不得进入 exact proof。
- 两条路径的 status、cut、sidecar、hint 和 artifact 不得跨界提升。

## 1.6 当前发布状态

截至 2026-06-26，工作树已有 producer/supervisor split、fixed-witness capsule、fail-closed
P1.2 OPEN-GATE、独立 whole-layout reverify 和中央公开发布器。P1.2 仍为 OPEN/BLOCKED，原因包括：

- 没有受支持的 production supervisor CLI/launcher；普通 solve run 不会自动 seal；
- owner manual gate 仍是 `blocked_manual_review_count`；
- PR2 的 smaller/read-once/controlled-loader verification TCB 尚未完成；
- review snapshot 仍需从 resolved immutable commit 物化，并补齐归档策略覆盖；
- 其它 roadmap 中仍为 OPEN/PARTIAL 的规格与几何边界尚未全部关闭。

现有机器字段 `p1_3b_*` 是历史兼容名。人类文档把后续 master integration 称为 P1.3。

## 1.7 输入与规模

`data/preprocessed/candidate_placements.json` 当前存在于工作树，大小 45,774,305 字节，SHA256 为
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`。某些轻量分发包可能将其
externalize，但 certified contract 始终要求同一 pinned bytes。拐角修复前的 45,773,799 字节 /
SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 版本已 superseded，且
hash-incompatible。

组合空间很大，exact campaign 依赖 candidate-frontier 枚举、CP-SAT、LBBD 和受验证 cut 来缩小搜索。
性能瓶颈或 168h 预算不是证明捷径，跑得久也不会自动把 open/unknown 变成 certified。
