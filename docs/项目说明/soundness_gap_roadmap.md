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
| **I4** — `left_or_bottom_boundary` 边界落位 admissibility 在活认证路径上**无 solve-time 独立复验** | ⚠️（§1A 谓词(3) 记录 generation-time + master 域限制；C4 已命名其几何字节 TCB） | ⚠️（generation-time guard + hash-pin；无 terminal/sink 几何重导） | ❌ | **GAP / OPEN → 排 P1.3B（带红测）** | 当前证据链：`placement_generator.py:267-271` 只在候选池生成期 fail-closed 要求 `placement_rule == "left_or_bottom_boundary"`；`gen_boundary_ports :419-444` 枚举 x=0 左边界与 y=0 下边界 pose；冻结 `candidate_placements.json` hash-pin 后，solve-time 直接采信这些 pose 字节。`src/cuts` 的 `left_or_bottom_boundary_saturation` 属 cut-family 影子路径，且 `lifecycle.py:1121-1126 step_8_apply_to_master` 仍 `NotImplementedError`，没有接入活认证 master。P1.3B 闭合标准：从 canonical template + placement_rule 独立重算每个边界 pose 的 admissibility，缺证据升 UNKNOWN / fail-closed，并加红测。 |
| **I5** — **F7/F8 供电割欧氏覆盖 vs 活路径 12×12 方形覆盖分歧** | ⚠️（§1A C4 已命名 active/canonical 12×12 方形与 cut-family 分歧） | ⚠️（helper 存在但未接入认证） | ❌ | **GAP / LANDMINE（latent 非 live）→ P1.3B 接入认证前必须收敛到共享 canonical 几何原语** | `src/cuts/helpers/power_cover.py:40-54` 的 `_min_cell_distance` 用 `math.sqrt` 欧氏 cell-to-cell 距离，`compute_cover_set :96-118` 由 `power_hitting_set.py`、`power_grid_reach.py:453/504`、`power_cover_oracle.py:212/216`、`power_grid_reach_oracle.py:228/251` 复用；活路径 generator/master 是 12×12 方形：`placement_generator.py:400-415` 生成 `[x-5,x+6]×[y-5,y+6]`，`exact_coordinate_master.py:5161-5174` 重算同一方形字节。欧氏圆 ⊆ 12×12 方形，若未来 F7/F8 接入认证，会更悲观，可能把真实可被方形覆盖的布局剪成 false-`INFEASIBLE`，抹掉真最优。当前 `lifecycle.py:1121-1126` 未接 master、F7/F8 generator default-disabled / shadow-first，故为 latent landmine 非 live certified gap。根治不是只把 F7/F8 各自私改成方形，而是把覆盖形状/度量等 canonical→geometry 规则上提为 `src/rules/` 纯 canonical 原语，活路径与 cut family 共同 import 复用并加红测。 |
| **I6** — canonical 规则 → 几何规格常量（覆盖形状等）是**命名人确认 TCB**，非代码可证 | ✅（§1A C4 明确命名 TCB/非定理） | n/a（规格事实，不是当前代码可闭实现） | n/a | **NAMED TCB / SPEC GAP（不宣称已由代码闭合）** | `rules/canonical_rules.json` 只给 `power_coverage_radius: 5`；`placement_generator.py:252-257` 校验 radius=5，`:400-415` 把它解释成 12×12 方形覆盖；owner 已确认 12×12 方形是正确游戏规则。P1.2 当前只能诚实命名此 TCB，并由 artifact hash-pin 锁字节；若要“代码证明 canonical→geometry 映射”，需 P1.3B 或后续规格层机制（显式 schema 字段/独立生成器复验/红测），不能在 C4 文档化中假装已闭。 |
| **I7** — **F3 port_exposure N/S front 方向与 canonical DIR_DELTA 南北对调（非电力几何 landmine）** | ⚠️（§1A C4 已命名 port 坐标/候选几何字节 TCB；§253 要 terminal front polarity 由规则推导） | ⚠️（helper/validator/oracle 存在但未接入认证） | ❌ | **GAP / LANDMINE（latent 非 live）→ P1.3B 接入认证前必须收敛到共享 canonical 端口原语** | `src/cuts/helpers/candidate_placements.py:56-64` 的 `DIRECTION_OFFSETS` 把 N/S 写成 N=(0,-1), S=(0,+1)，与活路径 canonical `DIR_DELTA` N=(0,+1), S=(0,-1) 相反（`placement_generator.py:34-39`、`routing_binding_context.py:26-28`）；E/W 一致。活路径 generator 明确端口是本体外侧相邻 connector，front=`port + DIR_DELTA[dir]` 须继续向外（`placement_generator.py:52-92`），冻结工件抽样也确认 N/S 端口 connector 在本体外侧一格、canonical front 继续向外。直接消费者是 F3 `port_exposure` oracle/family：oracle 从 helper import 并在 `port + direction_offset` 处生成 front（`port_exposure_oracle.py:39`、`:199-204`），validator 用同 helper 校验 cert front（`port_exposure.py:11-16`、`:64-75`）。风险方向：未来接认证时，合法向外 N/S 口会被 shadow helper 指回本体内占格，误判 `front` 被堵，生成虚假阻塞割，false-`INFEASIBLE` 过度收紧并破坏最优性。当前为 latent：`EXACT_F3_GENERATOR_ENABLED` 默认关（`port_exposure_oracle.py:1-4`、`:68-73`），`benders_loop.py:1040` 仅 allowlist env key、不调用 F3，`lifecycle.py:1121-1126` 的 `step_8_apply_to_master` 仍 `NotImplementedError`。F8 不直接 import 该 helper，但与 I5 同属 tier-1 shadow-cut 几何分歧类，P1.3B 前一并要求复用共享 canonical 原语。 |
| **吞吐 + capacity-(ii)/(iii)** — 98% 密度离散流墙 | ✅（明确 OUT by design） | ❌（无 cut family 表达） | n/a（设计上不在 6 谓词） | **SCOPE EXCLUSION（by design）— 不是要关的 gap** | **这是诚实边界、不是实现缺口、不是「待关 gap」。** 谓词(5)=连通「belts 能连」非吞吐；flow=GLOP 连续 LP 诊断-only 绝不 gate（`flow_subproblem.py:4-9/:149/:159`；`test_exact_contract.py:3532` 锁死）。lock §274 禁 diagnostic-flow-as-proof、§280 `EXACT_POWER_PLACEMENT_SUBPROBLEM` exploratory-only、§320 throughput-manifest postprocess-only。F1–F9 是面积/密度 packing cut 非吞吐，`src/cuts/` 未集成（`step_8 NotImplementedError`）。要进 certified 需**先发明能表达「离散容量流够不够」的 cut 范式**（= 新特性、改 6 谓词定义 + 新增离散容量子问题，非「关现有 gap」；auto-memory 9-family-frozen / F16 二分法两边都不收吞吐）。**当前不排进 P1.x 硬证据线。** |
| **供电 power_coverage**（谓词6） | ✅（01_overview §1.1 line 22） | ✅（master `:5827` 几何 witness + 塔实存守卫 `:5470-5499`） | ✅（terminal 独立 replay `exact_campaign.py:1131-1157` + v86/v87 test） | **PROVEN_SOUND（已闭）— 反例：不是缺口** | 列此行仅为对照防误判：master 求解时硬约束 + terminal 端**独立 replay 见证复验**（从原始 pose 字节重算覆盖格、不信 solver 变量，missing coverage / unforced pole fail-closed），是 6 谓词里独立复验**最强**的一条。证的是**覆盖 + 塔实存**（非电力吞吐配平；`:6336 power_capacity_lower_bound` 只是 sound 冗余有效不等式、`skip_power_coverage` 时 `:6284` 跳过、非主 gating）。UNKNOWN gap 仅在被禁 exploratory `EXACT_POWER_PLACEMENT_SUBPROBLEM` + synthetic_pole 路径（`benders_loop.py:7471-7479`），对 active base `valley4_protocol_core` moot（lock §280-285 该 flag 在 certified/production 全程 forbidden + readiness gate / `run_campaign_linux.sh` 双重 block）。**勿因「也有个 UNKNOWN gap」就把它误列成开口缺口。** |

## 2026-06-21 Shadow 分歧扫雷结论

2026-06-21 对 7 个认证语义量（度量 / 覆盖 / 占格 / 端口 / 边界 / 连通 + 非几何兜底）做了双源
只读系统扫雷（codex + claude）。结论是：**零 live 认证分歧**，活认证路径内部全自洽；已发现的分歧
全部 confined 在 latent `src/cuts`、env-gated-off、diagnostic-only 或 postprocess/adapters 面上。除
I5（F7/F8 电力欧氏覆盖）与 I7（F3 N/S 端口朝向）这两类 tier-1 false-`INFEASIBLE` latent landmine 外，
其余项登记为 **watch-on-wiring**，只有未来接认证/硬 gate 时才升级处理：

- `commodity_throughput` overload hint：`src/search/commodity_throughput.py:1-10` 是纯 helper，
  `EXACT_BINDING_USE_OVERLOAD_SEPARATION` 默认关（`binding_subproblem.py:689-702`），且硬 nogood 注释
  要求 caller fallback（`:721-733`；`benders_loop.py:5916-5925`）。
- flow dummy-commodity：`benders_loop.py:5681-5699` 仅构造诊断 flow 输入并返回 bottleneck；
  `flow_subproblem.py:4-9` 明确 certified_exact 中只能 diagnostic，`diagnostic_flow_status` 只向后传递
  为状态字段（`benders_loop.py:5190-5191`、`:5324-5330`），不 mint exact-safe cut。
- cuts source-digest 字段名混淆：`lifecycle.py:93-100` 字段名含 `generic_io_requirements`，但
  source payload 实填 `state.commodity_demands`（`:505-512`）。这是字段名/语义债，当前仍在未接 master 的
  cut lifecycle 面。
- boundary region 超集 + `verify_boundary_saturation` 空壳验证器：`verify_boundary_saturation`
  目前只校验 `state.canonical_rules` 非空（`src/cuts/assumptions/verifiers.py:72-82`），方向保守
  fail-closed，非 live 危险；P1.21/P1.3B 接线时补真实 saturation 数字校验。
- `patch_conflict_separator` 8-邻接聚类：`_collect_blocked_port_cells` 明示 8-connected clusters
  （`patch_conflict_separator.py:75`、`:109-118`），但入口由 `EXACT_B1_PATCH_ROUTING_CORE` env gate 控制
  （`benders_loop.py:6410-6416`），聚类只用于候选 patch 排序/构造（`patch_conflict_separator.py:218-285`），
  不是证明邻接。
- postprocess adapters：IndustrialPlanner `_EDGE_DELTA` 使用 y-down 坐标系（如
  `throughput_audit.py:60-64`、`:858-866`，`export_blueprint.py:54-58`、`:752-758`），
  `endfield_calc` 硬编码 port_rule 映射（`semantic_mapping.py:223-255`、`:523-529`）；按仓库入口说明，
  `src/adapters/*` 是 postprocess/delivery surface，不得成为 solver source-of-truth
  （`CLAUDE.md:222-228`）。

## 几何分歧根治原则

I5/I7 暴露的是同一类系统问题：活路径与 cut 家族各自重算“canonical 规则 → 几何”时，会在覆盖形状、
端口朝向、度量或边界解释上悄悄分叉。owner 已批方向：**诚实登记 + 真修留 P1.3B**，根治方案是
**收敛到单一 canonical 原语**。

具体要求：把覆盖形状、端口朝向、度量、边界 pose admissibility 等 canonical 规则到几何对象的定义，
上提为 `src/rules/` 权威层的**纯 canonical 原语**（无 exploratory 逻辑、无 cut-family 私有推导）。活路径
generator/master/routing 与 F1-F9 cut family 必须 import 复用这些原语；cut family 在 P1.3B 接入认证前
不得各自重算认证几何，必须先 wire 到共享原语并加 fail-closed 红测。这个原则取代 I5 里“F7/F8 各自改成
方形”的窄修法：窄修治标，共享原语治本。I6 的几何 TCB 边界仍保留：共享原语只能消除代码分歧，不能把
owner 确认的 canonical→geometry 规格事实伪装成 P1.2 已由代码证明。

## 优先级线索

当前实现侧必须排 P1.3B 的 open 项是 **I1** 与 **I4**；**I5/I7** 是 tier-1 latent landmine，任何 F7/F8
供电割或 F3 port_exposure 接入认证前，必须先统一到共享 canonical 原语并加红测；**I6** 是命名规格 TCB，
不能写成代码已证。I2/I3 是 PARTIAL（latent / 同根 I1），可随 I1 一并加固。吞吐/capacity 是**研究级
scope exclusion**、不进硬证据线。活路径 power_coverage 方形覆盖 + terminal witness 仍是已闭 sound
锚点；不要把 F7/F8 shadow helper 的欧氏 landmine 或 F3 shadow helper 的 N/S landmine 误读成当前 live
certified 缺口。
