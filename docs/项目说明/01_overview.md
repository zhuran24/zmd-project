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
(5) routing feasible，即每个 routed commodity 的 source/sink fronts 满足有向连通，
    且所有 route cell ∈ G ∖ R（空矩形内不得有任何物流件；owner 2026-08-05 空地语义
    裁决之甲案落地——「空」由 (1)∧(5) 联合保证：(1) 排设施机身，(5) 排路由占用）
(6) power coverage feasible，即受电设施被真实存在的供电桩几何覆盖（覆盖=**相交**语义:footprint 与塔覆盖区 ≥1 格重叠即算覆盖,owner 2026-07-07 裁定;非全包含 containment）
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
       [生产 supervisor 入口 = scripts/run_supervisor_seal.py（独立命令、proposal-ready marker 驱动）]
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

当前 `main.py` 只到 `CANDIDATE_PROPOSED`；生产 supervisor 调度入口是独立命令
`scripts/run_supervisor_seal.py`（`349c56c`，2026-07-04），不由 `main.py` 顺手执行。上图是已实现的
authority API 顺序，不是当前已打通的一键发布流程。

## 1.4 求解内核

默认 certified decomposition 是 placement master → binding → routing。binding 与 routing 是命题 P
的 gating subproblem。whole-layout nogood 在落 exact-safe cut 前还要经过
`independent_infeasibility_reverifier.py`；独立复验不能确认时，不落 cut并返回 UNKNOWN。

`src/cuts/` 当前在册为 F1-F7+F9（F8 已退役）。F1/F5/F6/F7 已有 reviewed Step-8 translator，
`benders_loop._maybe_attach_framework_cuts()` 也已提供 `EXACT_CUT_FRAMEWORK_ATTACH` 门控的 direct bridge；
该开关仍在 certified unsafe map、默认关闭，因此不能写成已进入默认 certified theorem。Stage B B0/B1
已落地（含 B1.5 typed 平台层），B2-B5、PIC C/D/E 与 B6 owner promotion 仍待完成。

## 1.5 `certified_exact` 与 `exploratory`

- `certified_exact` 是唯一有资格产生证明材料的路径，但仍受 supervisor、publish gate 和 owner gate
  约束。
- `exploratory` 只用于启发式、诊断、probe 和研究；历史的 “50 power poles + 10 storage boxes”
  等 cap 不得进入 exact proof。
- 两条路径的 status、cut、sidecar、hint 和 artifact 不得跨界提升。

## 1.6 当前发布状态

截至 2026-07-11，工作树已有 producer/supervisor split、fixed-witness capsule、fail-closed
P1.2 OPEN-GATE、独立 whole-layout reverify、中央公开发布器和生产 supervisor 入口
（`scripts/run_supervisor_seal.py`）。P1.2 已由 owner 显式 `owner_manual_decision`
关闭（`status=closed_manual_owner_decision`，`p1_3b_entry_allowed=true`，P1.3 已开放）。
这不是从测试、receipt、seal 或 checker 绿灯自动推导；clean 计数仍保存在仓库外。
后续边界包括：

- 普通 solve run 不会自动 seal；supervisor 入口是独立命令、仅满足一条机器条件，且尚无真实生产
  campaign→seal 实跑记录（部署时点任务，非 P1.2 close blocker）；
- owner manual gate 已是 `closed_manual_owner_decision`；唯一权威关门动作仍只认
  owner 手动决定；
- PR2 的 smaller/read-once/controlled-loader verification TCB 属发布时点硬化残项，非
  P1.2 blocker；
- review snapshot 已改为从 resolved immutable commit 物化（ref-move TOCTOU 回归测试已钉住），归档
  策略覆盖仍需补齐；
- 其它 roadmap 中仍为 OPEN/PARTIAL 的规格与几何边界尚未全部关闭。

现有机器字段 `p1_3b_*` 是历史兼容名。人类文档把后续 master integration 称为 P1.3。

## 1.7 输入与规模

当前冻结输入是 `rules/canonical_rules.json` 18,137 字节 / SHA256
`c3666d78d5dd1329514c7813be9f91f09cb3ce7b94907ef5b6ce746c9bcbbbd5`、
`rules/preprocess_plan.json` 1,383 字节 / SHA256
`5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`，以及
`data/preprocessed/candidate_placements.json` 54,467,709 字节 / SHA256
`f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`。某些轻量分发包可能将
candidate externalize，但 certified contract 始终要求同一 pinned bytes。superseded 历史链为 45,774,305-byte
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`、45,773,799-byte
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`、53,594,995-byte
`d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` 与 53,595,501-byte
`78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef` 仅属 superseded、
hash-incompatible 历史链。

generic-input 成品按普通 commodity 从 producer output 路由到 provider physical input。
`box_sink` 有 3 个物理输入/3 个物理输出，mandatory core 有 14 个物理输入/6 个物理输出；
provider-aware、instance-aware 下界不为未实例化模板记容量。当前需求 2 已被真实 core 覆盖，
所以 box lower bound 为 0。exact session 绑定同一 plan snapshot 的完整
`generic_input_slots_by_operation` map。

组合空间很大，exact campaign 依赖 candidate-frontier 枚举、CP-SAT、LBBD 和受验证 cut 来缩小搜索。
性能瓶颈或 168h 预算不是证明捷径，跑得久也不会自动把 open/unknown 变成 certified。
