# Soundness Gap Roadmap

> 本文件跟踪 certified_exact 路径相对 `PROJECT_LOCK §1A`（命题 P / Certified Theorem Scope）的
> 已知 soundness gap，每条以三态记录。它是**活文档**（gap 关闭/新增时更新），不是宪法层冻结条款；
> 权威 scope 定义在 `PROJECT_LOCK §1A` 与 `docs/项目说明/01_overview.md` §1.1/§1.3。
>
> 来源：C3 内核三源审（cc_memory `p1-2-c3-kernel-audit-3source-20260620`）+ 逐谓词对真代码核实
> （workflow `w0euoad7m`，6 ground agent + 3 对抗审含 codex 异源）。

## Hawk 护栏（先读）

**文档化 ≠ soundness 已闭。** 一个 gap 只有落地了**红绿测试**（fail-closed red test，能在回归里真的
拦住违例）后才算关闭。下表「Red/green test」列是 ✅ 才算 gap 真闭；Principle 与 Impl 即便都 ✅，
只要 Test 为 ❌/⚠️，该 gap 仍**未关**。每条 gap 以「**原则行号 + 实现符号 + 回归测试断言**」三元组
记录；缺任一项不得标 closed。

三态图例：✅ = 满足/已闭；⚠️ = 部分（latent 或自洽非独立）；❌ = 缺失。

## Gap 表

| Gap | Principle in lock | Impl exists | Red/green test | 三态判定 | 说明 / 反例（什么时候会咬人） |
|---|---|---|---|---|---|
| **I1** — 活路径 whole-layout INFEASIBLE nogood 落 cut 前**无独立异构 ⊆-infeasible 复验** | ⚠️（§130/§138/§140 保证「子问题 INFEASIBLE 本身成立」；但 whole-layout 冲突子集的**独立异构重导**未登记） | ❌ | ❌ | **GAP / OPEN → 排 P1.3B（带红测）** | 发射点 `benders_loop.py:5989`(binding)/`:7117`(routing) → `_add_exact_whole_layout_nogood :7452` → `_build_whole_layout_conflict :7368-7378`（仅把整层 pose_idx 拷进 conflict_set、**未 minimize**）→ master `add_benders_cut`（`exact_coordinate_master.py:7044-7096` 只把 `sum(present_lits) <= N-1` 编进 CP-SAT、**从不重解/重证**）。落 cut 唯一 guard 是 synthetic-pole fail-closed skip（`:7471-7489`，仅 exploratory `EXACT_POWER_PLACEMENT_SUBPROBLEM` 路径）。cut 信任**产出 INFEASIBLE 的同一个子问题 solver**，无第二/异构 verifier 独立重导 ⊆-infeasible。**关键区分**：「子问题 status 可信」（§130 routing 连通复验 + §138 F-BIND-R8-01 binding ordering + §140 status 契约都覆盖）vs「whole-layout 冲突子集是否过强、是否真 minimal——未独立重证」（真 gap）。lock §4 §280-283 那三条已知 gap **未登记**此条——它是**第四条 distinct gap**（已在 §1A / §4 登记）。**P1.3B 红测须**：构造「子问题报 INFEASIBLE 但其 ⊆-子集其实可行 / cut 过强」的情形，断言独立 verifier 拦下、缺证据则升 UNKNOWN 不落 cut。 |
| **I2** — master 域编码语义等价 + `occupied_cells == bbox` fail-closed | ✅ §137 | ✅ | ⚠️ | **PARTIAL（divergence 路径在冻结数据上 latent）** | impl 真实：`exact_coordinate_master.py` 以 occupied_cells footprint 为键（`_pose_footprint_key :993`、`_pose_has_template_rect_footprint :1043-1070` actual==expected bbox、`_pose_rectangular_footprint_bounds :1072-1091` 非矩形返回 None 走保守 over-approx 不 under-approx）；powered pose 缺 footprint 证据 → `ValueError('Missing occupied_cells…')` fail-closed。测试存在（`test_p0_certified_soundness_fixes.py:511/571/633`）。**但**冻结生产数据全是实心矩形 ⇒ `occupied_cells == bbox` 恒成立、非矩形 over-approx/语义分叉分支**永不命中**——guard 在场但 latent。反例需一份非矩形 footprint 的 artifact 才触发。 |
| **I3** — ④b 关掉 forged/stale/cross-process 污染；但**同源确定性语义编码错误**仍复现 | ✅ §307-312 / §287 | ✅（对外部污染） | ⚠️ | **PARTIAL（同根 I1）** | provenance/④b guard 真实且对**外部**污染有效：§307-312 source_digest 不匹配→quarantine（无 auto-migrate/无 silent fix）、未知 `ASSUMPTION_VERIFIERS` key→fail-closed HOLD；§287 六步 lifecycle + artifact_hashes 快照。**但**一个确定性语义编码错误（同 source 字节、同 encoder、同 solver）在 replay 时**完全相同地复现**——replay 是对反序列化 cert 用**同一个 validator** 做自洽校验、**不是独立重导**，与 encoder 共享。若 I1 发射点把「INFEASIBLE-but-deeper-context」编成过强/错误 cut，④b 与 replay 都抓不到。**同根 I1：缺异构独立 verifier。** |
| **吞吐 + capacity-(ii)/(iii)** — 98% 密度离散流墙 | ✅（明确 OUT by design） | ❌（无 cut family 表达） | n/a（设计上不在 6 谓词） | **SCOPE EXCLUSION（by design）— 不是要关的 gap** | **这是诚实边界、不是实现缺口、不是「待关 gap」。** 谓词(5)=连通「belts 能连」非吞吐；flow=GLOP 连续 LP 诊断-only 绝不 gate（`flow_subproblem.py:4-9/:149/:159`；`test_exact_contract.py:3532` 锁死）。lock §274 禁 diagnostic-flow-as-proof、§280 `EXACT_POWER_PLACEMENT_SUBPROBLEM` exploratory-only、§320 throughput-manifest postprocess-only。F1–F9 是面积/密度 packing cut 非吞吐，`src/cuts/` 未集成（`step_8 NotImplementedError`）。要进 certified 需**先发明能表达「离散容量流够不够」的 cut 范式**（= 新特性、改 6 谓词定义 + 新增离散容量子问题，非「关现有 gap」；auto-memory 9-family-frozen / F16 二分法两边都不收吞吐）。**当前不排进 P1.x 硬证据线。** |
| **供电 power_coverage**（谓词6） | ✅（01_overview §1.1 line 22） | ✅（master `:5827` 几何 witness + 塔实存守卫 `:5470-5499`） | ✅（terminal 独立 replay `exact_campaign.py:1131-1157` + v86/v87 test） | **PROVEN_SOUND（已闭）— 反例：不是缺口** | 列此行仅为对照防误判：master 求解时硬约束 + terminal 端**独立 replay 见证复验**（从原始 pose 字节重算覆盖格、不信 solver 变量，missing coverage / unforced pole fail-closed），是 6 谓词里独立复验**最强**的一条。证的是**覆盖 + 塔实存**（非电力吞吐配平；`:6336 power_capacity_lower_bound` 只是 sound 冗余有效不等式、`skip_power_coverage` 时 `:6284` 跳过、非主 gating）。UNKNOWN gap 仅在被禁 exploratory `EXACT_POWER_PLACEMENT_SUBPROBLEM` + synthetic_pole 路径（`benders_loop.py:7471-7479`），对 active base `valley4_protocol_core` moot（lock §280-285 该 flag 在 certified/production 全程 forbidden + readiness gate / `run_campaign_linux.sh` 双重 block）。**勿因「也有个 UNKNOWN gap」就把它误列成开口缺口。** |

## 优先级线索

唯一**实现侧、活路径、可立即排期**的 soundness gap 是 **I1**（whole-layout 冲突子集无独立异构
⊆-infeasible 复验，§280-283 三条之外的第四条 distinct gap）→ 进 **P1.3B 并强制配 fail-closed 红测**。
I2/I3 是 PARTIAL（latent / 同根 I1），可随 I1 一并加固。吞吐/capacity 是**研究级 scope exclusion**、
不进硬证据线。供电是已闭 sound 锚点、不是缺口。
