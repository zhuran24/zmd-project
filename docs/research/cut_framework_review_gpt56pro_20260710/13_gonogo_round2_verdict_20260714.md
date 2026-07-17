# 13 — go/no-go round-2 + 合并定论(2026-07-14):两条负轨全死,witness 有进展未达

> 承 doc 12。工作流 `wf_27e41160-4cf`(4 Attack[min-cut claude+codex / constructor claude+codex] + 3 对抗 Verify),zero-sealed 只读,~53min。harness 在 `scratchpad/spike_round2/`;journal 在 `subagents/workflows/wf_27e41160-4cf/journal.jsonl`。

## 0. 合并定论(rounds 1+2)

**求第一个 CERTIFIED 全局最优,经识别出的所有"有界证明"方法均不可达;剩下的活路是"让 exact 求解在固定小锚点上真正终止"或换算力/换证明技术——这是 owner 级战略岔口。**

| 路线 | 目的 | 结论 | 轮次 |
|---|---|---|---|
| §4 全局面积夹逼 | 上界 | 死(frontier 已是小矩形,夹的是平凡 ≤1347) | 会议 |
| §2 sink 上收 | — | 已花掉(HEAD 已强制) | 会议 |
| front-exposure 计数 Hall | 上界(证不可行) | 死(模型允许 connector/front 共享,无 layout-不变地板) | R1 |
| **连通 min-cut/Menger** | 上界(证不可行) | **死(结构性)** | R2 |
| construct-verify witness | 下界(证可行) | 机制可用、有进展(582→138 front_blocked)、未达 | R1+R2 |

## 1. R2 track① — 连通 min-cut/Menger 上界证书:route_dead(claude+codex 独立一致)

**结论:拿不出 binding-不变且 layout-不变的组合 min-cut/Menger 割来证小矩形 INFEASIBLE。结构性死,非"没想到"。**
- **唯一 sound 的连通割是"完全不连通"(min_cut=0)**:F2 cutset 的 `commodity_demand > cut_size` 是**吞吐/容量**论证(dinic_node_split.py 顶注自认),连通谓词只要求可达(cut_size≥1 即连通、belt 可共享 cell、允许 merger/splitter),用 `demand>cut_size` 当连通证书=**UNSOUND fail-open**(淘汰 certified-可行的"连通但吞吐不足"布局,吞吐是 PROJECT_LOCK §1A OUT-OF-SCOPE)。
- **sound 连通需求恒=1**(codex 的 merger—单 crossing—splitter 最小反例:2 源汇合共享 1 跨割边再分叉,连通谓词允许)→ `demand>cut_size ⟹ cut_size=0` = 完全不连通 = 最脆的 layout-specific 形态。17 商品也凑不出 demand=17(没证所有商品在所有 binding 下跨同一割,且 physical state 允许多商品共享几何)。
- **两个校验器(cutset.py:276 / component_reach.py:158)都吃 `_free_cells(state)`=某一份具体布局**,无任何 all-layout/all-binding 量化(rg 零命中),类型系统还显式拒 GHOST_AGNOSTIC scope(`_validate_cutset_scope`:161)。"对所有布局都不连通"本身=master 问题(placement 是决策变量 exact_coordinate_master.py:2900 NewIntVar),不是廉价重算。
- **实测锚点**:同一 6×8 ghost、同一 src(29,33)/sink(36,33),布局A(一堵墙,4713 free)disconnected=True;布局B(留一行走廊,1184 free)disconnected=False → **断连随布局翻转、不是 ghost 逼出**。frontier 面积差仅 6-7 格(42 vs 48/49),不可能"42 连通、48 必断"。
- **对抗验证专门查了"边界一圈窄喉"候选**:确认它是 70 格长的带、不是 Menger 窄割,且占用随布局/binding 变 = front-exposure 非连通割 → 不构成反例。

## 2. R2 track② — routing-aware witness 构造器:stuck_at_front @138(582→138,未达)

- claude 与 codex 各自独立(不同布局/binding)把 front_blocked 从 doc12 的 **582 降到 138**(留 belt 走廊),binding FEASIBLE/OPTIMAL@0.031s、620 端口/17 商品全真、empty_binding_domain=0、266/266 合法、overlap 0、供电 220/220 全覆盖。
- 但仍 `stuck_at_front`(138 blocked=128 body/outgrid+10 connector-cross),**连通阶段从未进入**(disc=0 是 front_blocked 早退的空值签名,非"连通通过";full router 未建未跑、32G 风险面未触)。
- 对抗验证(claude)亲手重跑独立 verifier 逐位复现 138、SHA-256 对齐、确认真跑非 re-solve 作弊、非藏连通结果。
- **判读**:routing-aware 构造**有真实牵引力**(76% 降幅)但**没证明能清零 front**;138 仍多。"能否清零 front 并过连通"仍开放。

## 3. 对"上界那堵墙"的最终判读

- **上界(证最优=证比 A* 大的都 INFEASIBLE)没有便宜证书**:front 计数 + 连通 min-cut 两条负轨结构性全死。根因深:layout 是自由决策变量、连通冗余极大、sound 连通需求=1(只有完全不连通才 sound、而它最 layout-specific)。
- 所以证 6×8/7×7/8×6 INFEASIBLE **只能靠 exact binding↔routing 求解终止**(其 INFEASIBLE + I1 独立复验即证书)——而该循环**不终止**(无预算帽、解空间天文),且 I1 复验也需重解=双重死(doc 11 claude-s4)。
- **下界(证可行)可攻**但只给 feasibility(A*≥某值)、不给最优性;且构造器尚未清零 front。

## 4. 剩下的活路(owner 级战略,按 [[zmd-goal-no-degradation-fallback]] 不降级=换进攻法)

1. **让 exact 求解在固定小锚点终止**(会议里没人做过的线):把 routing-front 必要条件**真正上收进 master**(不是逐点 nogood),让 master 停止提 front-doomed 布局 → 枚举循环从数千轮塌到可终止 → exact INFEASIBLE 可达且 I1 可复验。这是**唯一把"上界"救活的已知方向**(不是有界证书、是让 exact 证明真正跑完)。风险:producer 与 I1 复验器都要终止;上收的必要条件本身要 sound。
2. **推 witness 构造器清零 front + 过连通**(下界):至少拿到第一个 feasibility incumbent(A* 候选),把 A* 顶上去;construct-verify 管线已验证可用。
3. **换算力 / 全新证明技术**(如 CP-SAT 不可行性 proof-log / 基地分解成独立子区),末选。

## 5. 质量

rounds 1+2 共 19 席、claude+codex 双模型独立算 + 对抗验证,0 fatal 驳倒;R2 两条 route_dead 各由两模型独立到达 + 对抗验证专查边界窄喉候选后确认。全 zero-sealed 只读、未跑 master/main.py。结论是研究判读、非 certified 结果。诚实边界:route_dead 只针对"min-cut 做 binding+layout 不变上界证书"这一问,不等于断言 6×8 可行;witness stuck@138 不等于 front 不可清零。
