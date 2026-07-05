# 00 — 总路线图（master roadmap）

> **本文档的地位（先读这段）**：全项目工作线的**总图 + 排期快照 + 指针**，
> 2026-07-05 起立此存照。它不复制各阶段计划的细节（细节仍在 08/09/10 与
> docs/research/ 各设计稿），也**不是**状态权威——release 边界以
> `PROJECT_LOCK.md` + gate JSON 为准，当前实现状态以
> [06_current_status](06_current_status.md) + [soundness_gap_roadmap](soundness_gap_roadmap.md)
> 为准，主线执行序以 owner 拍板的排期卡
> （`cc_memory_vnext/cards/p1-2-closeout-then-tcb-backlog-order.md`，
> **以其正文 2026-07-04 晚修正版为准**）为准。本文档过时时，以上述权威为准
> 并回来修这里。
>
> **为什么有这份文档**（2026-07-05 盘点结论）：此前"阶段之间的总图"散在
> 05 号汇总表、排期卡与各研究稿里，没有单一入口；且 2026-07-04/05 两天
> 新增了整条形式化验证线（P3.0 双轴）与吞吐改判（P2.0 必做），旧计划
> 文档没有它们的位置。08/09/10/13 是"史料+现行混排"的 ledger，**保持
> 原样加注、不重写**；总图由本文档承担。

## 0. 一句话现状（2026-07-05）

P1.2 认证链 **OPEN/BLOCKED**（owner 手动门 `blocked_manual_review_count`）；
close-kernel 外审已画线收口（2026-07-03），PR2 #5 合入 / #7 通电（07-04）；
主线在 PR2 深化阶段（枢纽 = #1 最小 TCB 闭包，先深化再收口外审）；
形式化线（P3.0 轴 A）68 条定理两轮外审闭环；吞吐（P2.0）已改判必做、
设计稿 v2(含 v3 终审) 完成；证书侧（P3.0c 轴 B）路线图定型、待开工。

## 1. 主线（关键路径，串行）

```
PR2 深化(四阶段执行序) → P1.2 收口 → P1.3A spike → P1.3 主体 → P1.5+ → P2.0b
```

### 1a. PR2 深化（进行中；执行序 = 排期卡正文，此处仅摘要）

阶段1（轻）：#8 argv0/contract digest + #9a 仓库侧收尾 + #6 决策确认 →
批2a：#2 受控 loader + #3 read-once（带 resume/frontier/replay 纯核心抽取）→
批2b：#5-B2 候选域独立枚举（带 outer_search 接缝；批后收 306s 巨无霸测试）→
#5-F part3 设计 spike（带 fused child 实验）→ **#1 最小 TCB 闭包**（吞
l0-snapshot 拆分 + lazy import）→ 阶段4：#9b OS 级写隔离 + #9c 原生 TOCTOU。
pytest 提速余项已全部溶进上述批次（不独立成批，绑定表见排期卡）。
**owner 修正（07-04 晚）：P1.2 收口前提至少含 #1**——先深化再收口。
**owner 再拍板（07-06）：收口前提 = 整条 backlog 编码项**（#8、#2/#3、#5-B2、
#5-F spike、#1、#9b/#9c 全部完成），不只 #1；#9a 生产字节重钉维持部署时点
定位、不阻塞收口判定。即收口外审排在阶段4 之后。

### 1b. P1.2 收口

十项 close 条件见 [12_go_criteria](12_go_criteria.md)（PR2 TCB 收缩是第 10 项）。
路径（owner 2026-07-06 拍板版）：**整条 backlog 编码项完成**（含阶段4 #9b/#9c，
见 1a 尾注）→ 代码冻结 + fresh reseal → 收口外审（本地多镜头对抗审 + GPT Pro
relay，按 owner 需要发）→ **审到 owner 判定足够为止** → owner 关手动门
（gate JSON `owner_manual_decision`）。
**「三连 clean 计数」语义澄清（owner 2026-07-06）**：那是 owner 当时图方便的
说法，不是硬判据——实际判据就是「外审到 owner 觉得合适为止」，轮数可多可少；
gate JSON 的 `required_consecutive_clean_full_reviews=3` 与关门确认字段里的
"three clean reviews" 字样保留为机器兼容值（同 `p1_3b_*` 模式），checker pin
死了这个数字，改字段值属于 checker+tests 连锁手术、留待收口批一并考虑或不做。
配套部署时点任务（不阻塞收口判定、但在真发布前必做）：#9a 生产字节重钉、
真实 campaign→seal 实跑、dependency floor manifest 在 CachyOS 生产机重生成。

### 1c. P1.3A attach spike → P1.3 主体

spike 只回答一个问题：CP-SAT Python 路径能否把 cut 及时变成有效 master
约束（[09](09_phase_1_3_plan.md)；GO 标准 = prod-scale 跑通且 wall-clock
退化 <50%）。**这是全项目唯一真正的研究级风险所在**（cut 体系接上后收不
收敛没有理论保证，只能实测；退路见 §4 拍板台账 L11）。
主体 = step_8 落地 + F1-F9 逐 family 接线 + 三份 2026-07 新增规格在此落地：
- F5 orbit lift 实施规格七项（F5 稿 §4：P-HOM 结构门 / canonical_relabel /
  validator 增补 / query_liftable / master attach / telemetry / 红测⑥⑦⑧）；
- Q1a 工程桥（Q1 分类学稿 v2：owner lemma 五段合同 + 红测 R1-R10）；
- F7/F8 欧氏 vs 12×12 stencil 语义 reconcile（这也是形式化 F8 的解锁条件）。

### 1d. P1.5+ 生产集成（[10](10_phase_1_5_plan.md)，未变）

真生产 registry 注入、route schema 拍板、F2 max-flow witness、
**F3 active_port_witness 硬门**（生产默认开启前二选一）。

### 1e. P2.0 吞吐认证（owner 2026-07-04 改判**必做**；旧文档"圈外"口径作废）

P2.0a 残余：toy path-phase 证书 + prototype checker E2E（设计稿已含 v3 终审）。
P2.0b（P1.3 后）：按吞吐稿 §6 落 TP7-S/TP7-D 证书链 + 伪造红测。
P2.0c：D1-D8 实测与 FIFO/game 语义对齐。
形式化侧已预置：TP7-S 等式键边界 4 条定理 + 盲方 T1-T6 必要性陈述蓝图。

## 2. 支线（与主线并行，不碰生产代码/锁面）

### 2a. P3.0 轴 A：范式数学的 Lean 机器检查（已开工，68 条定理落 main）

现状：六模块 68 条、公理审计干净、两轮独立外审（7 会话+盲对拼）全回收。
余项（不依赖主线）：盲方 T1-T6 必要性定理族、C5b 覆盖容量 owner lemma、
TP7-D 验收语义、工程 W 定理对象（availableCuts/SoundAtScope）形式化。
等待解锁的：F8（等 1c 的 stencil reconcile）。
纪律不变：formal/ 不进认证 TCB、不改 gate（16 号 §6.4 政策原样有效）。

### 2b. P3.0c 轴 B：证书侧 proof logging（**本次排入**，待开工）

打"CP-SAT 编码忠实性单点"（瓶颈审计第 2 硬骨头）的终极解。七阶段
（P3.0 设计稿 §P3.0c）；**第一落点 = Phase 0+1：binding 子问题的 PB
独立重建 + VeriPB 证明日志 sidecar 复验**（2-5 周 PoC）。
关键设计约束：**独立重建**（不从生产代码导出编码，保持异构交叉验证价值；
与 PR2 #5-B2、I1 是同一笔投资的三个面）；纯旁路，不写生产路径。
执行位：数学面线程（形式化线的自然延续）；与主线零文件交集。
后续阶段（core 切片器→routing 分流→有理 Farkas checker→nightly 化）
按 PoC 结果再排。

### 2c. TNS 全域无解证书链（设计稿完成，实施未排）

O-1~O-16 义务 + ghost-use inventory（TNS 稿 §6）。数学侧已在 formal/
（覆盖链 + Finset 版全套）。排期建议：P1.2 收口后、P1.3 期间的独立批
（它动 producer/supervisor/publisher 的负向面，收口冻结期内不动）。

## 3. 圈外（明确不做，改判需 owner 裁定）

Q15 跨 base 迁移（Phase 2+）、Q16 多 base 联合优化（Phase 3+）、
Q1p partial-assignment 完备性（缺数学对象）、S_global 收敛性定理
（实验命题）、PBLean 自研验证器（轴 B Phase 6，远期）。

## 4. 拍板台账（owner 未决事项，集中登记）

| # | 事项 | 现状 | 影响 |
|---|---|---|---|
| 1 | Q1 状态改写（拆 Q1a/Q1p 进 05 号） | 建议已成稿（Q1a 稿 v2），待裁定 | 05 号 Q1/Q14 行的分级与措辞 |
| 2 | L11 命题降级退路（钉 blueprint 只证剩 41 个） | 挂起（算力墙的最后退路） | P1.3 实测不收敛时的 Plan B |
| 3 | GitHub 远端推送（main 停在 07-01） | 待定；建议从 C:\codex pj\zmd_pj 副本推 | 机外冗余 |
| 4 | P2.0b 实现规格批准时点 | 终审判"修复后可作实现规格"，修复已完成 | P2.0b 开工前提 |
| 5 | 168h 执行层债余项排期（OOM 配置雷等） | 部分溶入批2a/2b；余项未排 | 长跑稳定性 |
| 6 | 冻结输入正确性加固（pose 枚举独立重验） | B2（批2b）覆盖一部分；抽样穷举比对未排 | 瓶颈第 6 条 |

## 5. 风险对照（2026-07-02 瓶颈审计 7 条硬骨头 → 本图位置）

①算力硬墙 → 1c 见真章 + 台账 2 退路；②编码忠实性单点 → 2b（终极解）+
批2b B2 + I1（已落）；③F1-F9 未接入 → 1c；④floor manifest 占位 → 1b
部署时点；⑤168h 执行债 → 台账 5；⑥冻结输入只证"没变" → 台账 6；
⑦手动门 owner-only → 设计如此（1b 终点闸）。

## 6. 文档修订台账（本次盘点发现的过时点及处置）

| 文档 | 过时点 | 处置 |
|---|---|---|
| 05 号 Q14 | "形式化不投资" | 已加注（2026-07-05，指向本文档 §2a/2b） |
| 05 号 Q1 | 无 Q1a/Q1p 拆分信息 | 已加注（指向 Q1a 稿 v2，标注待裁定） |
| 12 号 SUPERVISOR OPERABLE | "当前不成立"基于 06-26 基线 | 已加注（07-04 入口落地，语义以 PROJECT_LOCK 为准） |
| 排期卡 title/summary | 仍写"先收口后深化"（正文已修正） | 已修正卡片头部 |
| PROJECT_LOCK `Updated` 字段 | 停在 06-26，正文已含 07-04 内容 | **不动**（锁文件元数据，owner 域；此处登记） |
| README 中后段旧 hash/旧叙事 | b35e5f9 等不可解析、"未合入"旧段 | 已有后注文化兜底；增量清理随下次 README 大修 |
| 08 号后半 | P1.2B 各 family "待实施"是史料 | 文档自带历史化标注，不动 |
| 13 号 | 估时已史料化 | 文档自带标注，不动 |

## 7. 阅读入口（新会话/新协作者按此序）

1. `PROJECT_LOCK.md`（release 红线）→ 2. 本文档（总图）→
3. [06_current_status](06_current_status.md)（当前状态）→
4. 排期卡正文（主线执行序）→ 5. 对应阶段的细节文档/研究稿。
