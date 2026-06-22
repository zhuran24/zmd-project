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
| **WS** — 终端/发布 **witness 身份**：发布 `(R*,π*)` 的 `π*` **未被复验 binding/routing**（隔离 replay 只证「同尺寸存在某可行布局」、终端 validator 只查几何/供电/空矩形最优） | ⚠️（§1A.C done-condition 要「无 false-`CERTIFIED` 公开面」+ 谓词(4)(5) binding/routing；但**发布 witness 身份**未被这些机器条件覆盖） | ❌（无 fixed-witness binding/routing verifier） | ❌ | **BLOCK 级 GAP / OPEN → P1.3B（最强、先于 I1）** | 2026-06-21 GPT Pro 三方独立外审 + Codex/Claude 对源确认。`candidate_proof_replay.py:_replay_one_proof`(`:889-904`) 按 ghost_w/h **自由重解**（只证存在某可行布局）；终端 sink `require_record_solution_match=True`(`:525-535`) 保留 stored witness、不比 stored↔replay、不重跑 binding/routing；终端 validator `_validate_terminal_solution_against_project`(`exact_campaign.py:987-1235`) 只查几何/不重叠/供电/ghost空/空矩形最优。→ 一个 `active_ports=[]`/binding-INFEASIBLE 的 stored pose 可发成公开 CERTIFIED（`certified_surface` + `delivery_manifest` 同链）。**reachable = tamper-only（+ resume/迁移/并发写 benign drift），非 live**：正常 in-process 解只在 binding+routing 通过后才返 CERTIFIED；但 sink+validator 存在前提即「stored witness 不可信」，故 tamper/drift 可达即真 soundness 缺陷。**推翻下文「零 live 分歧」的隐含强断言（窄断言关于正常运行仍成立）、强于 I1**（I1 只过切=CERTIFIED-suboptimal，本条直接 mint 假 CERTIFIED）。**修复史**：2026-06-21 试 rebind-to-replay stopgap → 全量 preflight 证其**破坏合法认证交付**（终端证据 `candidate_status_digest` 内嵌 witness 指纹、build/verify 两端不一致、12 测试含 happy-path 挂）→ 撤回。owner 决定 **诚实 open + proper fix 进 P1.3B**。**P1.3B 红测须**：构造 binding-INFEASIBLE 的 stored witness、断言公开 CERTIFIED 面 fail-closed 拒发；durable = fixed-witness verifier（钉住 `π*` 原地重跑 binding+routing，不可行升 UNPROVEN）。 |
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

> **2026-06-21 补充修正（GPT Pro 外审）**：上面「零 live 认证分歧」是**本次 shadow 扫雷的范围结论**——它扫的是
> `src/cuts` 影子割里的几何/度量分歧，结论在该范围内成立（活认证路径内部对这 7 个量自洽）。但它**不覆盖终端
> witness 身份路径**。GPT Pro 三方外审后发现 **WS（witness-split）**：发布 witness 未被复验 binding/routing，
> tamper/drift 可达即可 mint 公开 false-`CERTIFIED`。故「零 live 分歧」**不得被读成「认证器不可能产假
> CERTIFIED」**——后者已被 WS 推翻（正常运行仍不产、但威胁模型内可达）。见 Gap 表 **WS** 行。

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

## 第二轮外审新登记 gap（2026-06-21 round-2，已 Codex→Claude 对源核）

- **OPEN-GATE（BLOCK）**：公开发布面 `certified_surface.evaluate_certified_delivery_surface` 的 publishable 条件**不读 P1.2 reopen / `exact_full_scale_status=open`** → open 期间仍 `publishable=true`（repro: published witness binding=INFEASIBLE）。即「诚实 open 即止血」是**运营纪律、非机器闸**。
- **TOCTOU（BLOCK / drift）**：`benders_loop.py:2197-2215` 先 `load_project_data`+generic_io/wireless-slot 载入、再 `compute_exact_artifact_hashes`(:2206)、再用 **pre-hash 内存对象** build；`build_exact_core` 不重读盘、`sha256_file` 另开句柄、无等值校验把 recorded hash 绑到实际 build 字节 → load↔hash 之间被换文件即得到「记录 hash 不 attest 实际求解字节」的 session。正常单进程两读一致，故 drift（并发写/篡改）可达、非 live。
- **PHASE-GATE-STRUCTURE（BLOCK / latent）**：`check_phase_review_gate.check_gate` 只验 JSON-shape/status/authority/doc-marker + 两个 acknowledgement bool,**对 witness-split/fixed-witness 零绑定**;`_check_step_8_boundary` 在 next_allowed=true 时立即返 [] 跳过唯一代码级 fail-closed。当前另有 `check_p1_2_proof_obligations.py:2323` 通用「必须保持 blocked」锚硬挡 next_allowed=true（故 latent 非 live）,但它无 witness 谓词、真闭合时被抬掉后无人重新施加 fixed-witness 要求。
- **CUSTOM-ROOT-PROFILE（CONCERN / latent，BLOCK 已被复审驳回）**：port-slot profile 来自源树 module-global `OPERATION_PORT_PROFILES`(`operation_profiles.py:18,113`)、binding 不调已存在的 root-参数化 `load_preprocess_context_from_paths`;但 `certified_artifact_contract` 的 locked 层对源 checkout 及任何带 PROJECT_LOCK.md 的 root 把 canonical_rules.json/preprocess_plan.json hash-pin 到全局表所读的同一字节、binding 前强制 → 任何 **certified** root 分歧即 SHA fail-closed,只非 locked TOY root（设计上非认证）暴露。剩纵深弱点。
- **LOCK-CHECKER-DRIFT（已修）**：PROJECT_LOCK 曾声称 rebind 已落而 code/checker 在 HEAD stored-witness → 文档↔代码漂移；已订正。根治见 P1.2-FIX-7。

## 第三轮（round-3）新发现 + 为什么"总能审出问题"

- **PYC-EXEC-DIGEST（BLOCK）**：`compute_certified_exact_source_digest`（`exact_campaign.py:340-378`）**只哈希 `.py`**，隔离 replay 子进程 import 时执行的是 `.pyc` 字节码、未绑定。PoC（两家独立复现）：伪造时间戳合法的恶意 `.pyc`，`.py` 字节 + source digest 全不变，子进程却执行假逻辑、把真可行候选伪造成权威 `INFEASIBLE`（同构可伪造 `CERTIFIED`，并经 `certified_frontier.py:215-217` 污染全局剪枝）。= **验证器自身执行身份未绑定**；与 TOCTOU/custom-root 同族（「所执行/所消费 ≠ 所哈希」）。
- **LOCK-CHECKER-DRIFT 复发（已补修）**：round-3 发现 PROJECT_LOCK §C 残留「stopgap 已 rebind…此谓词仅由 stopgap 满足」与 §B「已撤回」矛盾——已补修为「HEAD 无 stopgap、此谓词当前不满足」。这恰证明 **P1.2-FIX-7 的 doc↔code 漂移红测必须自动化**（人手反复漏修）。

### "总能审出问题"是真的——结构原因 + 收敛策略

对抗式外审**永远能再剥一层信任洋葱**：R1=witness(WS) → R2=发布闸/artifact 载入(OPEN-GATE/TOCTOU) → R3=验证器执行字节码(.pyc) → 再下去是解释器/OS/硬件。**"审到零发现"不可能、也不是收敛判据。** 真收敛 =：
1. **显式划定并冻结 TCB 线**：声明信任什么（如「验证器从不可变 hash-pin capsule 执行：源码+字节码+输入+依赖一体；解释器/OS 以下为命名 TCB」）。.pyc 这条说明执行身份当前在线**上**却没绑 → 必须绑（capsule / 哈希字节码 / `-B`），不能留在线上不管。
2. **修线以上全部**（= 下方 Tier-1 架构）。
3. **然后判 done**：此后新发现要么落 TCB 线**以下**（已声明信任、非 gap）、要么是 done 判据的**实例**（已覆盖）——这才是停审转建的判据。

**扩展 done 判据**：原「发布谓词在确切字节上独立复验 + 机器发布闸 + 红测」**再加**「验证器从不可变 capsule 执行（绑源码字节码+输入+依赖）+ 命名 TCB 声明」——把 PYC/TOCTOU/custom-root 收进 capsule 这一个根因。

**建议：三轮已够，停审进修。** 第四轮大概率继续往 TCB 下剥，边际是更深 latent 而非新决策。

## P1.2-FIX 修复计划（闭 P1.2 的 soundness 必修；分层 + 单一 done 判据）

> **命名（owner 2026-06-22 定）**：闭 P1.2 的 soundness 必修统称 **P1.2-FIX**；真正的 master 集成
> （PoseBoolExactMaster / `step_8_apply_to_master` 接线）统称 **P1.3**（= 旧项目书 `P1.3B` = 旧 cc_memory
> 「P1.3A 主体」，**无 A/B 之分**）。旧文里 soundness 语境的「P1.3B」读作 P1.2-FIX、master 语境读作 P1.3；
> 机器闸标识符 `p1_3b_*` / gate JSON 为历史名、本轮不动。顺序：**先做 P1.2-FIX 闭 P1.2 → 再开 P1.3**。

**单一 done 判据**：每条认证发布谓词都在**确切发布物**（序列化字节、非仅 pre-write 对象）上被**独立复验**，且在**机器强制的 owner 发布闸**之后，带 fail-closed 红测。新发现落在此判据内 = 已被计划覆盖的**实例**（非新票）；落在外才算新 scope——以此**钉住球门**。

**根因合并（按根因修、不按实例打补丁）**：多数发现是同一结构病的不同脸——「权威闸没对它实际发布/信任的确切东西做独立复验/强制」：WS、OPEN-GATE、PHASE-GATE-STRUCTURE、F3 同族；I1、TOCTOU 是「信任未独立复验」的另两面。

**收敛标尺**：盯"还在冒新 BLOCK，还是只剩 CONCERN/latent"。round1=WS(BLOCK)、round2=OPEN-GATE(新 BLOCK) → **未收敛**；某轮只剩 CONCERN/latent = BLOCK 类收敛、可停审进修。

### 第4轮外审推翻 FIX-1/3 → capsule 根治闭合（2026-06-23，提交 `f492690`）

第4轮外审（3 个独立 GPT Pro reviewer，blind A-G）判 **FIX-2 真闭；FIX-1 + FIX-3 未闭、REOPEN**（`228f266` 之前的实现不够）：
- **FIX-1 2 BLOCK**：可伪造 in-process verdict（`TerminalFixedWitnessVerdict._fresh_run_marker` 是公开构造器默认字段，同进程构造即过、不跑 binding/routing，**LIVE**）+ F3 own-body（`_connector_body_exclusion_violation` 只拒 other-body、放过自己 body 占 connector）。
- **FIX-3 3 BLOCK**：stub 即过（只验文件+2 函数名）+ `_calls_function` shadow（同名 local/nested/param shadow）+ mutable-anchor 自重封（改 3 review anchor 跳过 v99 floor → manifest 自报 hash 自盖章）。

根因=**信任机制本身可伪造**（in-process verdict 对象 / name-based AST guard / self-resealable hash）→ owner 拍板上 **capsule 根治**（= done-criterion 早钉的「验证器从不可变 capsule 执行 + nonce 不可伪造 + 命名 TCB」）：
- **FIX-1 闭**：新 `src/search/terminal_fixed_witness_capsule.py` —— fixed-witness 在隔离 `python -I` 子进程执行（仿 `candidate_proof_replay`）、返回 nonce-bound response，父进程只信校验过 response、不信 in-process verdict 对象；删 `_fresh_run_marker` 权威；旧公开入口强制 fail-close。F3 任意 in-grid connector `owner!=None` 都拒。
- **FIX-3 闭**：v99 static floor **永远跑** + 5 处 review anchor 强制==硬编码 `CLOSE_KERNEL_APPROVED_REVIEW_ANCHOR`（unknown fail-closed）+ guard 验执行行为（`_reachable_direct_call` 死分支折叠认 Name-guard/三元/BoolOp/post-return·raise）+ capsule 进 v99 floor 四套结构 + 新 `CLOSE_KERNEL_V99_STRUCTURAL_GATE_SOURCE_PATHS` 机器闸（结构 gate 文件⟹必在 floor）+ 命名 checker-source TCB。
- **FIX-5 顺带闭**（create-window load↔hash + canonical 子窗口 TOCTOU）。

流程=Codex 实现 / Opus 子代理三轮对抗审全清（逮到 capsule-未进-floor + 死分支可达性两个同族新洞、已返工修）/ 我终审 `--full` preflight 20/20·pytest 3277·`next_allowed=False` 止血保持·12 obligations·54 sinks·allowlist 45/45。**残留（非 live、跟进）**：可达性扫描器漏认 `assert False`/`range(0)`/`match` 无 catch-all 等"假不可达"——被 v99 floor hash 钉 + STRUCTURAL_GATE 机器闸兜死，要利用必须改 checker 源码（=git/人审 TCB 边界）。详 cc_memory `p1-2-capsule-f492690-fix-1-3-fix-5`、外审原文 `C:\22957\download\新建文件夹\{1,2,3}\回复.txt`。

**收敛标尺更新**：round4 仍冒新 BLOCK（FIX-1/3 reopen + capsule 内 2 个同族新洞）但都已闭，Opus 三轮后只剩 floor-兜死的 CONCERN = **BLOCK 类收敛**。剩 Tier-1 **FIX-4**（I1）+ Tier-2 FIX-6 + 一致性 FIX-7。

### Tier 1 — 挡"诚实发布"的 BLOCK（必须先修）
- **P1.2-FIX-1 fixed-witness 终端 verifier（WS/F1，并吞 F3）**：钉完整 (R*,π*) 非仅 pose；binding+routing 共享同一 witness/assignment；routing 用 R* 确切 ghost origin/extent；含 connector/body 排除；**序列化字节 round-trip 复验**；timeout/UNKNOWN→UNPROVEN，绝不→INFEASIBLE；证据绑 stored solution digest、无 witness 替换。红测:binding/routing witness 不一致→FAIL；非-R* origin→FAIL；UNKNOWN→UNPROVEN；写后字节被篡→FAIL。
- **P1.2-FIX-2 OPEN-GATE 机器发布闸**：certified surface / delivery manifest / inspector / adapters 一律读 reopen/`exact_full_scale_status`，open 期间 `publishable=false` fail-closed（单一机器闸、所有面共用）。红测:status=open ⇒ 各面拒发。
- **P1.2-FIX-3 phase-gate 绑 fixed-witness 条件**：`check_phase_review_gate` 不得只凭 shape+acknowledgement 接受 closed/next_allowed=true；须硬断言 P1.2-FIX-1 verifier 在场+过红测；next_allowed=true 不得跳过 step_8 fail-closed；把 `check_p1_2_proof_obligations.py:2323` 通用锚换成 witness-bound close 条件。
- **P1.2-FIX-4 I1 独立 fixed-layout 不可行复验**：落 whole-layout nogood 前用解耦第二复验，不能独立确认 INFEASIBLE（含 timeout）就不落 cut（视作 UNPROVEN）。
- **P1.2-FIX-5 TOCTOU 原子快照**：消除 `benders_loop.py:2197-2215` 的 load→hash 窗口（先 hash 再从同字节 build，或 read-once→hash 同 buffer→喂 build）；recorded hash 须 attest 实际 build 字节。

### Tier 2 — CONCERN / 纵深
- **P1.2-FIX-6 custom-root profile 本地化（CONCERN/latent）**：binding 走已存在的 `load_preprocess_context_from_paths`，让 port-slot profile 与 hash-bound root 同源（当前 locked-hash 契约已兜、无 certified 路径可坏，修纵深 + 关 TOY-root 暴露）。

### 一致性
- **P1.2-FIX-7 doc↔code 漂移修复 + 红测**：PROJECT_LOCK / proof-obligation / checker 对齐到「发布 π* == replay 已证 witness」单一 canonical 谓词；加红测:PROJECT_LOCK 声称已修而 code/checker 仍在 stopgap 即 FAIL（防 LOCK-CHECKER-DRIFT 复发）。

### 不变的既有项（详见上方 Gap 表）
I5/I7 几何 landmine（接认证前收敛到共享 canonical 原语）、I6 命名规格 TCB（不写成代码已证）、I2/I3（latent / 同根 I1，随 I1 加固）、I4 边界落位 solve-time 复验、吞吐/capacity 研究级 scope-exclusion。活路径 power_coverage 方形覆盖 + terminal witness 仍是已闭 sound 锚点；勿把 shadow helper 的欧氏/N-S landmine 误读成 live certified 缺口。
