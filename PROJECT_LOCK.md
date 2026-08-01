# PROJECT_LOCK.md

**Status**: CURRENT_LOCK
**Updated**: 2026-07-30 (AB16 stage-specific conservative resource admission and prelaunch rechecks; A038 immutable FAIL_CLOSED; prior: formal selected-loader and pathname-transport hardening; Gate-A v6 explicit-plugin qualification, committed publication/self-replay and ECHILD-only descendant closure; AB16 Gate-B/formal research-only cohort, terminal-reference archive replay v2 and persistent-owner lifecycle; W0 D6 research-only artifact protocol cohorts; active-port boundary-domain correction and candidate reseal; front-offset incident batches 3+5 authority closure; physical, routed generic-input providers; provider/instance-aware lower bound; V94 fresh-witness dominance; batch-1 identity reseal; P1.2 owner-close; F8 retirement; Stage B complete through B5b — typed lowering F1/F6/F7 only, F5 shadow-only since B5a; RAB-SEP certified allowlisting F-BL-R11-01; front-clear lift F-GM-FCL-01)
**Purpose**: Freeze exactness boundaries, source-of-truth rules, accepted invariants, and forbidden changes for the current repository state.
**History**: Date-stamped engineering history lives in [CHANGELOG.md](CHANGELOG.md). If this file conflicts with older notes, this file wins. Symbol/function names are authoritative; numeric source-line anchors below are informational and were refreshed against snapshot `48901c5` on 2026-07-11.

## 1. Exactness Constitution

- `certified_exact` and `exploratory` are separate paths. Exploratory outputs must not be promoted as certified evidence.
- The exact empty-rectangle objective is `max_lex(area, min_side)`.
- `min_side >= 6` is a candidate admissibility rule, not an objective tie-break.
- `rules/canonical_rules.json::globals.empty_rectangle.min_side_admissibility` is the project-level authority for that admissibility floor; the production project value is `6`, while toy projects may use smaller explicit floors.
- `Phi(w, h)` is not the exact source of truth.
- `(area, width, height)` is not the exact source-of-truth comparator.
- Exact mode has no hard `50 power poles + 10 protocol storage boxes` cap. If that number appears anywhere, it is exploratory-only guidance.
  - (2026-06-04) specs 02 §2.6.1 / 06 §6.1 / 07 §7.2·§7.4.1 早先把 `I_opt=60 (50桩+10箱)` / 总集 326 当 exact 固定枚举, 已对齐为: 供电桩 residual-optional (激活数为决策变量、coverage 下界、候选池上界)、协议箱 required-optional (demand 驱动); 60/326 仅标 exploratory illustrative 参考。真实 master (`pose_bool_exact_master` / `exact_coordinate_master`) 实证无此 cap (源码 residual/required-optional 建模, 非固定 60)。
- **(F-FRONT-INC-01, 2026-07-18) front 错位事故 addendum — identity 语义与历史状态失效**。事故：全仓
  front 消费机械把 stored 端口坐标再 `+dir` 推一格（查体外第 2 格），而游戏真语义（owner 游戏内实测定谳）
  是 stored 坐标格自身（体外第 1 格）须可放带——双向污染（假 INFEASIBLE / 假放行），权威档案
  `docs/research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md`。本批（批 1）已把
  certified 主链全部 front 消费点改为 identity 语义（F-RT-R2-01/R3-01/R5-01 改判承载）。fail-closed 义务：
  ① 任何新 front 消费点必须经 `routing_subproblem._port_front_cell` / `routing_binding_context.port_front_status`
  的 identity 定义，从 stored 坐标 `+dir` 推 front 即事故复发；② 事故前生成的一切持久化判定
  （campaign checkpoint、persisted nogood、front_blocked 证据、strong status）承载的是错位语义，必须经
  source-digest 失效——不得在 identity 代码下 resume 消费；③ **theorem scope（owner 批 0 拍板：补域，批 3 已完成）**：
  事故发现时的冻结池因生成期错位剪枝缺失 2,064 个墙距-1 合法 pose（66,405 → 68,469）；该限制已由批 3
  的生成器判界修正、全域重生成与 freeze ritual 换钉关闭。叠加批 5 的协议箱实体端口域后，现行冻结池共
  `82,829` 个 pose，以 §2 的 size/SHA256 为唯一当前钉。最优性命题现在覆盖该**重生成且换钉的候选域**；事故前候选池不再
  具有证明权威。④ certified 不可达面（pose_bool/D2/patch/abstract/
  separator/deletion-core/F3 族/io-render 标注）的残留旧语义消费点由批 2 收尾；在批 2 落地前这些面继续
  被 env 白名单/unsafe-map 挡在 certified 之外，不构成在线污染。
- **(F-PORT-ACTIVE-BOUNDARY-01, 2026-07-18) 端口边界剪枝必须使用可证明的最小激活影子**。
  候选对象记录全部实体口的 routing access cell；只有实际被 operation profile / generic binding 选中的口才
  必须拥有图内、未被设施本体占用且方向兼容的可布带格。制造模板的每个 canonical operation 都至少激活
  1 个输入和 1 个输出，且两类口各集中在一整侧，因此任一必需侧全部越界仍是健全的生成期剪枝。
  协议核心与协议箱不同：generic 槽允许 `__unused__`，实际只激活需求子集；它们的候选域只要求本体完整落在
  `70x70` 网格内，未激活实体口可以越界。其精确本体由 binding/routing 与终验 fail-closed 复核；不得把
  “所有物理边都可用”误当成必要条件，也不得借当前冻结商品数量作更强的隐式剪枝。

## 1A. Certified Theorem Scope (命题 P)

> **Reference, do not diverge.** 下面 6 谓词的**外延**与 soundness 短语 reproduce 自
> `docs/项目说明/01_overview.md` §1.1（谓词 1–6）与 §1.3（soundness 定义），那两节仍是 canonical
> 谓词权威（镜像 §1 引 `canonical_rules.json` 作 admissibility 权威）。本节在**不改变谓词外延**的
> 前提下附加 scope-precision 注解；若与 `01_overview` §1.1/§1.3 的谓词外延冲突，以那两节为准、本节
> 须 re-sync。

当 certified_exact 对候选输出 `(R*, π*)` 报 `CERTIFIED` 时，它**恰好且仅仅**证明 A 块命题；B 块那些
**不在**证明范围、**不得**被当作 certified 证据冒充（违反即触发 §4 "Treating … diagnostic flow
checks as certified proof"）。

### A. CERTIFIED PROVES

π* 满足下列全部 **gating 谓词**（任一 INFEASIBLE 阻止 CERTIFIED），且 `(R*, π*)` 在
`max_lex(area, min_side)` 下 **lex-最优**：

- **(1) ghost 内无 facility** `all_cells(π) ∩ R = ∅` — ghost optional interval 并入与全部 facility
  interval 同一组合 `AddNoOverlap2D`（`exact_coordinate_master.py:4178`，core+ghost interval 全集）。
  master 硬几何约束、非诊断。
- **(2) instance 两两不重叠** `∀ i≠j, occupied_cells(π(i)) ∩ occupied_cells(π(j)) = ∅` — core
  intervals 的 `AddNoOverlap2D`（`exact_coordinate_master.py:3759`），与谓词(1) 的组合约束并列、同属
  NoOverlap2D 约束族（非字面同一条）。
- **(3) per-instance placement_rule** — 双闸：生成器在 pose 枚举期对每 template 通过
  `placement_generator._validate_template_geometry_contract()`（`placement_generator.py:159`）硬绑并
  fail-closed，违规几何不 emit 进 `P(i)`；master 侧由 `ModeRectDomain`
  （`exact_coordinate_master.py:699`）与 `AddExactlyOne(all_region_lits)`（`:3021`）限制域。
- **(4) port_binding feasible（含端口级 exact-count）** — `binding_subproblem.py` 真 gate 子问题：每
  instance 恰一 binding（`:930`）；每 generic output / input slot 恰一 commodity（`:976` / `:1022`）；
  每被需求 commodity 已绑端口槽数**精确等于**其 `required`（output `:1048` / input `:1035`；工件
  `generic_io_requirements.json` 当前 output 侧 `blue_iron_ore:34 + source_ore:18 = 52`、input 侧
  `qiaoyu_capsule:1 + valley_battery:1 = 2`，源码无字面量、由工件驱动）。generic-input assignment 必须落到
  被选 provider instance 的实体 input port；selection 必须覆盖该 provider 的完整 slot-key 集（未用口显式为
  `__unused__`，不得提交残缺 provider map）。binding INFEASIBLE → `benders_loop.py:5989`（routing 穷尽同走 `:7117`）落 nogood、不
  certify。**精度边界**：证「端口槽『个数』= 需求声明『个数』」（0/1 计数等式），**不证**每口离散吞吐
  速率（见 B）。
- **(5) routing feasible = belts 能连（连通可行，NOT 吞吐）** — `benders_loop.py:6973-6990`
  在 routing `FEASIBLE` 后只产生求解层 `RUN_STATUS_CERTIFIED` 候选判决，且**不读任何吞吐/容量量**。
  该判决不是 durable terminal/publication authority：`outer_search.py:855-954` 只能提交
  `CANDIDATE_PROPOSED`，最终必须经 `ExactCampaign.supervisor_seal()` 和中央发布器。证的精确语义 =
  **离散有向连通（global source→sink reachability）**：generic-input final 也从 recipe producer 的实体
  output front 全程路由到被选 `protocol_core` / `protocol_storage_box` provider 的实体 input front；每
  commodity 每 source front 存在到 sink front
  的有向 route-state 路径、每 sink front 被喂到，经 `routing_subproblem.py:1678-1775
  _validate_selected_route_connectivity` 全局复验、拒 local-only incumbent。此连通复验已由 §130 列为
  活路径 certified 硬契约（区别于 §131 acceleration-only 的 lazy connectivity cut）。routing 的
  `capacity`（`:1058-1061 AddAtMostOne`）仅「一格一层至多一条 route-state」的**静态空间互斥、无时序
  维度、非吞吐容量**。**红线（防 overclaim）**：**routing FEASIBLE ≠ 吞吐可行**；给的是「belt 路径
  **存在**、port 对连通」级保证，不是「每单位时间扛得住 required 离散吞吐/带宽」级保证；「belts 能连」
  字面即连通、不得读成「带宽达标」。
- **(6) power_coverage feasible（最强谓词：master 强制 + 独立 terminal 复验）** — (A) master 硬约束
  `exact_coordinate_master.py` 的 powered-slot cover-choice 约束：被选塔覆盖矩形与 slot footprint
  几何**相交**（**owner 2026-07-07 裁定：供电覆盖谓词=intersection——受电设施 footprint 与被选塔覆盖矩形 ≥1 格重叠即算覆盖，非 containment/全包含**）；terminal 侧由
  `pr2_l0_artifact_core.py:986-1045` 以 `any(cell in coverage_cells)` 独立复验覆盖并拒绝 missing/unforced
  tower（**不信 solver 内部变量**——routing/binding 无此第二道）。附注：聚合容量下界由
  `exact_coordinate_master._add_global_valid_inequalities()`（`:6520`，记录类型
  `power_capacity_lower_bound` 于 `:6988`）加入，属 **sound 冗余有效不等式**，**非主 gating**。**精度
  边界**：证「几何半径覆盖 + 塔实存」（`covered`），**不证**电网功率吞吐/容量配平（`covered ≠
  throughput-balanced`）。
- **lex 最优性** — 任一 lex 更大的 `(R', π')`（即 `lex(area(R'), min_side(R')) > lex(area*,
  min_side*)`）必 infeasible（`01_overview` §1.3 soundness 定义；`min_side >= 6` 是 admissibility、
  非 tie-break）。

> 6 谓词全 gating；其中 **power_coverage(谓词6) 额外携带一道独立 terminal witness 复核**，强度高于只在
> in-loop 求解的 routing(5) 与 binding(4)。
>
> **几何信任边界 / C4**：关系层的认证硬锚点仍成立：NoOverlap2D 覆盖 ghost/facility
> 不相交（`exact_coordinate_master.py:3759` / `:4178`）、binding 端口槽 exact-count
> 等式（`binding_subproblem.py:930` / `:976` / `:1022` / `:1035` / `:1048`）、routing
> FEASIBLE 后的全局 source→sink 连通复验（`routing_subproblem.py:1678-1775` / `:1885-1900`）、
> power terminal 覆盖相交 + 无冗余塔复验（`pr2_l0_artifact_core.py:986-1045`）均是活认证路径约束 /
> 复验，不依赖 cut-family shadow 路径。几何层只有两类 solve-time 独立重导已存在且可声明：
> (a) master 对实心矩形 footprint 从 pose anchor + template dims 重算
> `occupied_cells == bbox`（`exact_coordinate_master.py:1043-1070`）；(b) 对矩形受电
> footprint，master 重算 power-pole 的 radius-5 / 2×2 pole 诱导 12×12 方形
> `power_coverage_cells`（`exact_coordinate_master.py:5141-5175`，游戏规则确认为 12×12 方形）。
> 其余 candidate geometry 字节是命名 TCB：冻结 `candidate_placements.json` 内每个 pose 的
> `occupied_cells` / `power_coverage_cells` / port 坐标被采信，前提是 generation-time
> `placement_generator._validate_template_geometry_contract` fail-closed
> (`placement_generator.py:161-168`, `:252-257`, `:267-271`) 且 artifact hash-pin 锁住字节。
> canonical 规则 → 几何字节的映射（例如 `power_coverage_radius=5` 对应 12×12 方形覆盖，
> `placement_generator.py:400-415`）是 owner 确认的规格事实和命名 TCB；它不是 P1.2 已由代码
> 自动证明的定理。
>
> **2026-07-06 更新（PR2 #5 B2 / `16495f4`）**：candidate_placements 的**字节**已被封印期重推 gate
> `canonical_candidate_geometry_rederivation_violation`（`pr2_l0_artifact_core.py`，L0 true child 在
> terminal precheck 后无条件调用）交叉验证——verifier 从冻结 `canonical_rules` 用
> `placement_generator.generate_all_pools` 重推、精确紧凑序列化、断言 `sha256 == LOCKED_EXACT_ARTIFACT_SHA256["candidate_placements"]`，
> 不等即 fail-closed。受信基由「信 45MB 不透明字节」收缩为「信生成器源码（已入 V99 floor 整文件钉死）+ canonical_rules」。
> **仍为命名 TCB**：生成器源码本身、及 canonical 规则 → 几何**语义**映射（非字节）未被独立重实现证明；
> 把 candidate_placements 彻底移出证明权威（Option B / 契约迁移，本文件 §1A「certified 立足于…」）未做——
> 暂缓判据（2026-07-06 派 3 路 codex 核实：P1.2 close 不要求它、按 owner scope 决定；它比 Option A 多关的是**窄 TOCTOU/
> 多读一致性残余**〔terminal precheck 活读未被 A digest 专绑；主求解器/fixed-witness 已 snapshot-bound〕、与已暂缓 #3/#9b
> 同族；迁移成本 ~20 文件/9 子系统）见记忆卡 `pr2-5-b2-candidate-geometry-rederivation-landed`。

### B. EXPLICITLY OUT-OF-SCOPE（certified 不证、不得冒充）

- **(B-1) 物料离散吞吐 / belt 带宽容量未证** — 谓词(5) 只到连通；唯一带 demand 量纲的 flow 子问题被
  锁成 **diagnostic-only、绝不 gate**（`flow_subproblem.py:4-9` docstring / `:149 CreateSolver("GLOP")`
  连续 LP / `:159 NumVar(0.0, infinity)` 连续无界，运行后只存 `benders_loop.py:5191
  diagnostic_flow_status`、从不门控）。`test_exact_contract.py:3532
  test_exact_mode_uses_flow_only_as_diagnostic` monkeypatch flow→INFEASIBLE 仍断言 CERTIFIED + 零
  exact_safe cut——**刻意锁死的契约**、非疏漏。
- **(B-2) capacity / 连通 (ii)(iii)（98% 密度离散流墙，研究级）** — open research problem；active F1-F7+F9 cut
  family（F8 retired）（region_capacity / density_envelope 等）是**面积/空间密度 packing cut、非吞吐 cut**（截至
  2026-07-12：F1/F6/F7 走 typed lowering（registry→resolver→`step_8_apply_to_master`→`typed_apply`）；
  F5 shadow-only、只产 `ShadowValidated`、无 lowering 绝不改 master；F2/F3/F4/F9 为 LEGACY_DIAGNOSTIC、
  在 typed 单入口的 registry 边界拒绝（旧「step_8 `NotImplementedError` fallback」机制已随 B5a 退役）；
  attach 在 certified 下仍被 `EXACT_CUT_FRAMEWORK_ATTACH` unsafe-map 禁用），
  无 cut family 表达「离散容量流够不够」。进 certified 需**新范式**（改 6 谓词定义 + 新增离散容量
  子问题），**非「关现有 gap」**。
- **(B-3)「资源数量够」三种精度、证明地位完全不同、不得混成一句**：① 端口级 exact-count（谓词4，binding
  `sum == required`，**已 certified**）；② 电力**覆盖**充分性（谓词6，几何覆盖 + 塔实存 + terminal 独立
  replay，**已 certified**；**非**电力吞吐配平）；③ 物料离散吞吐充分性（台数·产率 ≥ 流 demand，**未
  certified**，诚实边界 / 待接 cheap win）。
- **(B-4) 机器间物理间隔（`machine_min_clearance_cells`）非命题 P 谓词** — canonical
  `globals.logistics.machine_min_clearance_cells=1`（`rules/canonical_rules.json`）仅被 `src/rules/models.py`
  解析、认证路径**无消费者**（master `_add_port_clearance_constraints` 在 exact_mode 提前 return；routing
  `_add_gap_rule` 仅 telemetry）。**owner 2026-06-21 规格澄清 + 2026-07-18 front 错位事故再裁**：该字段管的是
  **使用中端口的 front/带子格（= port spec 的 stored 坐标格自身，体外第 1 格）须可放带、否则接口接不起来**；
  **机器身体之间贴着合法、无身-身间隔要求**（游戏实测：贴脸死 / 隔 1 格通 / 1 格带合法 / 两相对口共享中间格）。
  故「贴着布局被认证」非 soundness 违规（同吞吐：命题 P 只证 6 谓词）。端口 front 格由 routing 强制（identity
  语义，F-RT-R2-01/R3-01）；当前工作树的终端 fixed-witness 边界还会用实际 `port_specs` 对精确发布 witness 重建
  body occupancy，并在 stored front 格被任一 facility body 占用时拒绝（实现在
  `pr2_l0_fixed_witness_core.py` `_connector_body_exclusion_violation`——`terminal_fixed_witness_verifier.py`
  是 re-export 门面；该 backstop 在错位事故期间行为恰好正确，是假放行未穿透发布边界的原因；capsule/terminal
  回归覆盖）。solve-time 更早拒绝仍可作为纵深/性能增强，但该已知 public false-CERTIFIED 路径不再登记为开放 gap。

**已知 soundness gap / 修复状态登记（当前工作树，2026-07-11）**：三态矩阵仍以
`docs/项目说明/soundness_gap_roadmap.md` 为行为索引，但本锁文件是发布边界权威。2026-06-21
登记的 F1 witness-split、OPEN-GATE 和 I1 whole-layout nogood 独立复验已在当前工作树落地：
`terminal_fixed_witness_capsule.py` / `terminal_fixed_witness_verifier.py` 钉住提案中的 `π*` 原地复验，
`certified_surface.resolve_p1_2_publish_open_gate()` 在人工 phase gate 未打开时 fail-closed，
`independent_infeasibility_reverifier.py` 在 whole-layout nogood 落 cut 前独立复验并在不确认时升
`UNKNOWN`。这些修复关闭了相应已知实现缺口，但**不等于 P1.2 closed**。

**P1.2 已于 2026-07-07 由 owner 显式 `owner_manual_decision` 关闭**（gate = `closed_manual_owner_decision`、
`next_phase_entry.allowed=true`，详见下 §C5 现状框）。本段其余事实仍然成立：生产 supervisor 入口
`scripts/run_supervisor_seal.py` 已落地（独立命令，从 proposal-ready marker 驱动独立
supervisor 调 `supervisor_seal()`），补上了 done-condition 的「supervisor 可执行入口」这一条
机器条件；`main.py` 普通完成仍止于 `CANDIDATE_PROPOSED`（seal 是独立命令、不由 main.py
顺手做），入口存在与 seal 成功都**不是**关门动作本身；PR2 的更小、
read-once/controlled-loader verification TCB（仅防蓄意内鬼）已按 2026-07-06 owner 令移至发布时点（见下段）；review snapshot 打包器已把 mutable `treeish`
一次解析为 immutable commit 并统一用于 provenance/manifest/物化（TOCTOU 窗口已闭，由
`test_package_review_snapshot_ref_move_after_resolve_keeps_packaged_commit` 回归钉住），归档策略已按
`28d9d2c` 收窄；roadmap 中其它 OPEN/PARTIAL 几何/规格
边界仍需按 principle/implementation/red-test 状态处理。connector/body 的已知公开发布缺口已由终端
fixed-witness 拒绝路径关闭，不应继续列作未实现项。当前阶段为 **P1.3**；
现有 `p1_3b_*` 字段仅为历史机器兼容标识。任何 checker PASS、局部回归 PASS 或内部 supervisor
seal 都不得改写为 owner 关门动作——关门权威只在 owner_manual_decision（已于 2026-07-07 行使）。

**2026-07-06 close-scope 修改（owner，行使 `docs/项目说明/12_go_criteria.md:30`「或 owner 明确修改 close scope」）**：上文列为未决的「PR2 更小/read-once/controlled-loader verification TCB」及其同类——凡**只防「能执行 reseal 仪式的蓄意内鬼」**的硬化（#8 深化、#3 fd-held read-once、#9b OS 写隔离、#9c 原生 TOCTOU、#5-F import-time 完整性、#5 Option B、#2）——owner 统一**暂缓到发布时点、明确不作为 P1.2 闭合的必要条件**。判据：手滑/无心之失与外部篡改已被字节 sha floor 常开拦死（不延期、是核心），这些锚只对忠实 reseal 后的蓄意内鬼有意义（威胁模型定性见 `close-kernel-threat-model-reseal-adversary`）。提取全集＋判据＋何时翻转见记忆卡 `deliberate-insider-hardening-deferred-to-release`。（时点注：此修改做出时 P1.2 尚未关闭、且它本身**不**是关门动作——只把这些项从「收口编码前提」移到发布时点；P1.2 后于 2026-07-07 由 owner_manual_decision 关闭。）

### C. P1.2 done-condition (C5)

> **当前状态（2026-07-07）：CLOSED。owner 显式 owner_manual_decision 关闭 P1.2、开启 P1.3B。** PR1 的
> producer/supervisor mint split、fixed-witness 终端复验、P1.2 fail-closed 发布闸、I1 独立复验、生产
> supervisor 调度入口（`scripts/run_supervisor_seal.py`）均已实现;三轮收口外审（权限结构 / 数学语义 /
> TCB 线诚实性）0 上-TCB soundness 洞;`_check_phase_gate_fixed_witness_close_binding` 的 stay-blocked
> sentinel 已按其 docstring 预期的转换撤除（fixed-witness publish binding 保留、无条件强制），gate =
> `closed_manual_owner_decision` + `next_allowed=true`,close-kernel checker / full / slow 已 reseal 通过。
> 「仅防蓄意内鬼」的 PR2 TCB 深化项按 2026-07-06 令移至发布时点（见上 close-scope 修改段）。**此关闭是
> owner 显式手动决定,非自动推导**;历史"不得因类方法/局部修复/入口存在而自动宣称 closed"的纪律仍成立。

P1.2 可被诚实宣布闭合，仅表示当前 `PROJECT_LOCK §1A` 命题 P 的机器边界、发布链和 owner 手动闸
同时满足。它不是吞吐定理，也不自动打开 P1.3。

机器可查条件（任一失败即不得宣称 P1.2 closed）：

- 命题 P scope 锁死：6 个 gating 谓词外延不扩大；吞吐、belt 带宽和离散容量流仍明确 OUT-OF-SCOPE。
- producer/mint 分权：`outer_search.py` 只能落 `CANDIDATE_PROPOSED`；唯一 durable terminal
  `CERTIFIED` mint 是 `ExactCampaign.supervisor_seal()`，其它 `mark_campaign_stopped(...,
  "CERTIFIED")` 调用必须被拒。
- supervisor 可执行入口：受支持的生产命令/launcher 必须从 proposal-ready marker 驱动独立 supervisor。该入口已由 `scripts/run_supervisor_seal.py` 满足（独立命令，非 `main.py` 顺手完成）；普通 `main.py` 完成仍不能被记成 seal 成功，且入口存在只补此机器条件、不打开 owner 门、不推导 P1.2 closed。
- fixed-witness 身份绑定：supervisor 必须读取已提交提案字节，用固定 witness capsule/verifier 对提案的
  `(R*, π*)` 本身复跑 binding/routing，而不是只证明同尺寸另有某个可行布局；复验拒绝或材料缺失必须
  fail-closed。
- 公共发布单入口：`publish_verified_certified_delivery_surface()` 必须从 disk-current、supervisor-sealed
  campaign 原子地派生 `final_solution.json`、`optimal_blueprint.json` 与
  `certified_delivery_manifest.json`；generic writer、viewer/report、adapter 和 compatibility exporter
  不得成为替代认证发布器，失败后不得遗留部分公开面。
- P1.2 OPEN-GATE：`resolve_p1_2_publish_open_gate()` 必须读取权威 review gate；缺失、畸形、open 或
  非 owner-closed 形态一律使公开面不可发布。
- proof-bearing candidate `CERTIFIED` / `INFEASIBLE` 在进入 frontier pruning、终端证据或 supervisor
  seal 前继续走 sink replay；producer、writer、函数对象、closure、registry、当前进程 freshness stamp
  均不能授予证明权。
- whole-layout nogood 在落 exact-safe cut 前必须通过 independent infeasibility reverify；不确认、分歧或
  异常均升 `UNKNOWN`，不得把原子问题自己的判决当独立证明。
- 隔离验证器执行身份继续满足 `PO-ISOLATED-EXEC-BYTECODE-BINDING`：子进程使用 `-B -X
  pycache_prefix=<fresh-dir>` 从受 source digest 保护的 `.py` 编译。Python/stdlib/OR-Tools native
  extension、父 relay 和 OS process/file isolation 仍是命名 TCB，不得被写成“完全消除 TCB”。
- close-kernel checker 的 sink inventory、source hash、guard token、checker 自绑定和强状态 allowlist
  必须通过；修改受保护文本/docstring 导致 hash 漂移时必须按同一工作树重新封存，不能删 obligation
  或缩 scan root 来“过闸”。
- `EXACT_*` 在 `certified_exact` 中继续 deny-unknown；未知或 proof-semantics knob fail-closed。
- release snapshot 必须从已解析 immutable commit 物化，并通过完整的归档排除/敏感面策略；仅把
  treeish 解析成 metadata、随后仍物化 mutable 名称，不满足该条件。

owner 手动条件：

- `data/review_gates/phase_1_2_spike_close.json` 只能由 owner 的显式 `owner_manual_decision` 打开；仓库
  不得从 receipt、报告、package metadata、source-tree manifest、clean-count 或内部 supervisor seal
  自动推导 P1.2 closed / P1.3 allowed。
- 当前 gate 为 `closed_manual_owner_decision`（owner 2026-07-07 显式关闭 P1.2、开启 P1.3），兼容字段
  `p1_3b_entry_allowed=true`。该关闭是 owner 真实手动输入；此前在 owner 明确改闸前，公开发布与下一阶段
  入口一直保持关闭（fail-closed 机制本身不变，未来任何 gate 变更仍只认 owner_manual_decision）。


## 2. Certified Source of Truth

The certified path is grounded in:

- `rules/canonical_rules.json` (now also carries consolidated preprocess recipe / target / commodity truth and empty-rectangle admissibility)
- `rules/preprocess_plan.json` (additive operation-profile/utility-slot plan; exact-hash-bound and forbidden from redefining canonical recipe/target/commodity truth)
- `data/preprocessed/candidate_placements.json` (external large artifact: lightweight checkouts/distributions may omit it — verify with `scripts/check_external_artifacts.py`; certified runs require the pinned bytes)
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`
- artifact-hash-compatible campaign state
- provenance-complete exact-safe cuts

The current exact-source pins are:

- `rules/canonical_rules.json`: size `17,510`, SHA256 `5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05`;
- `rules/preprocess_plan.json`: size `1,383`, SHA256 `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`;
- `data/preprocessed/candidate_placements.json`: size `54,467,709`, SHA256 `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`.
  The 53,595,501-byte / `78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef`
  activation-pruned artifact is superseded and hash-incompatible.

`data/preprocessed/candidate_placements.json` is an external large artifact. Whether a given
checkout actually contains it is a packaging property, not a lock guarantee — a lightweight
distribution may externalize it (the default external-artifact checker tolerates that;
`--require candidate_placements` does not). That packaging choice does not change the certified
contract: the pinned bytes must be restored or regenerated before a certified run, and any
freeze/reseal or `--require-large` flow must verify size/SHA256 first. An earlier
artifact (size `45,774,305`, SHA256
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`) predates the Batch-3
domain regeneration and Batch-5 physical-provider expansion, is superseded, and is hash-incompatible.
The preceding artifact (size `45,773,799`, SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) predates the boundary
`(0,0)` corner-pose fix, is superseded, and is hash-incompatible. The former
artifact (size `53,594,995`, SHA256
`d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f`) is superseded and
must fail resume with `artifact_hash_mismatch`. Regeneration source is
`python src/placement/placement_generator.py`; an archive is a valid restore source only after its
bytes pass the pinned hash check.

The following non-canonical-truth surfaces remain additive and must not redefine internal solve schemas:

- `data/solutions/final_solution.json`
- `data/blueprints/optimal_blueprint.json`
- `data/solutions/certified_delivery_manifest.json`
- generated viewer/report sidecars such as `viewer_report.json`
- compatibility export bundles such as `data/exports/industrial_planner/*`
- adapter-side outer deployment sidecars / validator probes for IndustrialPlanner larger-base experiments
- neutral interchange contracts under `src/interchange/*`
- build-time / export-time adapters under `src/adapters/*`
- build-time preprocess plan `rules/preprocess_plan.json` and `src/interchange/preprocess_context.py` — **additive-only** (cycle groups / utility operations). The plan must never carry `recipes` / `production_targets` / `commodity_roles`: recipe/target/commodity truth derives exclusively from `rules/canonical_rules.json`, and the context builder fails closed on any such key (R6-F-01: a same-key plan overlay could silently rewrite runtime operation profiles). Because the plan feeds runtime operation profiles and binding utility slots, it is bound into the exact campaign hash closure (`exact_campaign.OPTIONAL_EXACT_HASH_FILES`) and the preflight frozen-artifact registry; editing it is a freeze-ritual change, not a free overlay edit.

## 2B. B Design v2 Cut Object Boundary (2026-05-22)

Phase 0 close (`docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md`) 后,
**cut object 升级为持久化一等公民**. New source-of-truth additions:

- `docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md` v3.2.2 — cut
  object schema + 10 步 lifecycle + 6 步 replay verify + 6 维 watcher
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/{01-09}` — 历史九族 cut
  family spec（F8 `power_grid_reach` 已于 2026-07-08 退役；当前 active registry 为 F1-F7+F9） (region_capacity / cutset / port_exposure / component_reach /
  pattern_nogood / shape_packing_hall / power_hitting_set / power_grid_reach /
  density_envelope) 全 final version
- `docs/research/p3_b_design_v2_20260521/state_machine_v2.md` — group-orbit
  state + AnonymousSlotRef (替代 v14 per-instance state, 消 10^134 label
  symmetry)
- Phase 1 起 `data/cuts/*.json` (persisted active cuts) + `data/cuts/
  quarantine/*.json` (quarantined cuts) 加进 certified path source-of-truth
  (currently 空, 等 Phase 1 cut store 落地后启用)

**postprocess/adapter boundary** unchanged: cut object 仅在 certified core 内
循环, 不进 `src/adapters/*` / `data/exports/*`.

## 2A. IndustrialPlanner Active Scope

- The current certified IndustrialPlanner support contract targets `valley4_protocol_core` (70×70) exclusively.
- The other known IndustrialPlanner bases (`valley4_infra_outpost`, `valley4_rebuilt_command`, `valley4_refugee_shelter`, `wuling_tianwangping_aid`, `wuling_heart_repair_station`, and `wuling_protocol_core`) are preserved as `future_scope` and are not part of the active checked-in audit / CI contract.
- The checked-in full-demand base matrix, deployment-path matrix, umbrella overview, support-suite inventory, and checked-artifact gate must default to that single active 70×70 base.
- The outer-deployment subsystem for larger-base translation remains adapter-side `future_scope`: it may stay in the repository, but it must not be treated as active certified evidence or as part of the default CI-critical path until explicitly reactivated.

## 3. Accepted Invariants

- Producer proposal boundary (F-CAM-PR1-01): terminal solve completion in `outer_search.py`
  persists `CANDIDATE_PROPOSED` plus bound proposal material only. It must not directly persist a
  terminal campaign `CERTIFIED` state or publish public delivery artifacts.
- Supervisor mint boundary (F-CAM-PR1-02): `ExactCampaign.supervisor_seal()` is the sole durable
  terminal `CERTIFIED` mint. It reads the committed proposal from disk, revalidates proposal and
  campaign bindings, executes sink replay and fixed-witness verification, and validates disk state
  before and after the write. A caller-held in-memory mapping is not authority.
- Public publication boundary (F-CAM-PR1-03):
  `publish_verified_certified_delivery_surface()` is the sole certified public publisher. The
  solution, blueprint, and manifest are one transaction over the same sealed result; a failed write
  must clean up partial outputs. Generic serializers, report/viewer builders, adapters, and legacy
  compatibility exports remain non-authoritative.
- Phase-open denial (F-CAM-PR1-04): a valid internal supervisor seal is necessary but not sufficient
  for release. The P1.2 owner gate must independently resolve to the explicit closed form; missing,
  malformed, or open gate data blocks publication.
- Best certified result is monotonic within the current campaign process/persistence epoch. Across a mutable JSON checkpoint resume boundary, proof-bearing candidate strong statuses must be re-established before they can support frontier pruning or terminal certified export.
- `final_solution.json`, `optimal_blueprint.json`, and `certified_delivery_manifest.json` must be derived transactionally from the same disk-current supervisor-sealed result; their mere presence or internal `CERTIFIED` text is not proof of publishability.
- Optional compatibility exports must be derived from the canonical blueprint and must not become the source of truth for solver/runtime consumers.
- Postprocess manifest/export mappings used to bridge translated larger-base exports remain adapter-side evidence only and must not be promoted into certified proof.
- Production parallel scheduling uses a coordinator-only writer with disjoint candidate waves.
- Candidate-record solution hygiene (F78-F-01): a persisted candidate `solution` may exist only on a `CERTIFIED` record; every incoming `CERTIFIED` result must carry its own fresh solution mapping (no inheritance across `mark_candidate_started`/`mark_candidate_result` rewrites); resume validation rejects any non-`CERTIFIED` record carrying a solution. Strong statuses (`CERTIFIED`/`INFEASIBLE`) are monotone inside the current trusted campaign write epoch: rerun preambles must not downgrade them to `RUNNING`, weak results must not overwrite them (audited block), and contradictory strong statuses fail loudly. This monotonicity does not make checkpoint-loaded strong statuses proof-bearing after resume.
- Checkpoint-loaded candidate strong statuses require fresh replay (F-CAM-R8-01): a mutable JSON checkpoint may carry syntactically valid `CERTIFIED` or `INFEASIBLE` candidate records, but the checkpoint does not carry a replayable binding/routing/master proof certificate for those candidate-level conclusions. On resume, both statuses must be demoted to `UNKNOWN`, any stored candidate `solution` / exact-safe cut counts must be removed from the proof surface, terminal frontier evidence must be cleared, and any certified export surface that relied on them must be cleared before the campaign can continue. Otherwise a stale or edited checkpoint `CERTIFIED` can become the positive witness for terminal full-frontier export without replaying binding/routing proof (false-CERTIFIED), while a stale `INFEASIBLE` can prune a true maximal candidate (false-INFEASIBLE -> false-CERTIFIED optimality).
- Resume sanitization is durable before public proof reuse (F-CAM-R8-02): when `load_or_create(..., resume=True)` demotes checkpoint-loaded strong candidate evidence, it must immediately write the sanitized campaign state back to `exact_campaign_state.json` before returning. When outer search resumes into a non-terminal certified state, it must save the demoted campaign state and clear stale certified delivery artifacts before any next candidate solve can run. An in-memory-only downgrade still leaves stale proof-bearing checkpoint/export surfaces available to crashes, concurrent readers, archive scripts, or later resumes.
- Candidate strong-status proof authority is sink-replayed, not producer-, writer-, function-, closure-, registry-, or current-process-freshness-authorized (P1.2 sink replay, superseding the interim F-CAM-R9-01 / F-CAM-R10-01 authority model). `ExactCampaign.mark_candidate_result()` may persist a data-only `candidate_proof` replay request, but neither that request nor the caller that supplied it is proof. Before `CERTIFIED` or proof-bearing `INFEASIBLE` may influence certified frontier pruning, terminal evidence, the delivery manifest, or the public certified surface, the sink must use the isolated on-disk verifier to recheck strict request shape, project/source/artifact/campaign/candidate bindings, snapshot and rehash the exact inputs, and independently replay the fixed `certified_exact` solve. Frontier verification must atomically adopt the replay projection so a rejected forged strong status becomes `UNPROVEN` and cannot lock the candidate lifecycle; downstream sinks fail closed. Missing replay material, closure-cell mutation, module rebinding, monkeypatching of the producer process, and test-helper injection therefore cannot mint candidate proof authority. The on-disk sink verifier/protected source plus interpreter and operating-system isolation remain TCB assumptions; arbitrary mutation of that sink boundary itself is not claimed away.
- Certified exact source digests include the root entrypoint (F-SRC-R9-01): the protected source set must include root-level production Python files such as `main.py`, not only `src/` and `scripts/`. A change to campaign entry/control semantics must alter `compute_certified_exact_source_digest()` and invalidate hash-bound campaign/source evidence.
- Parallel wave results are identity-bound (F78-F-02): a worker result is accepted only when its `dispatch_seq`, `attempt_index`, `candidate`, and `candidate_key` all match the dispatched task, validated independently on both the scheduler side and the consumer side before any campaign write; duplicate sequences, mismatched identities, and errored results never become proof-bearing outputs, and a malformed wave stops the campaign as `worker_process_failed`/`UNKNOWN`. A scheduler-side result-validation failure immediately discards all retained per-sequence results and the tail drain stops accumulating proof-bearing results, and the consumer discards a non-completed wave's results unless the failure is a worker crash / process-failure that legitimately carries identity-valid completed progress (F-PS-R4-01: closes the gap where a retained first `CERTIFIED` could otherwise leak into candidate records from a wave the scheduler had already classified as malformed). F-PS-R5-01 closes the residual leak paths the F-PS-R4-01 fix left open: the discard latch is now set (and `results_by_seq` cleared) on **every** validation-failure path — including the main-loop non-`WorkerResult` branch that previously only set `failure_reason` and let the tail drain re-accumulate, and the crash drain which previously kept processing further results in the same batch after clearing — plus a final pre-return guard that re-clears whenever the latch is set; the worker's raw `error` is namespaced `worker_result_error:{dispatch_seq}:{error}` so it cannot collide with the process/crash reason namespace; and the consumer's result-preserving whitelist is tightened from bare `startswith(prefix)` to `reason == prefix or reason.startswith(prefix + ":")`, so a spoofed `worker_process_failed_validation_failure:*` / `worker_crash_respawn_limit_validation_failure:*` reason can no longer smuggle a malformed wave's `CERTIFIED` companion into persisted candidate records — a false-CERTIFIED that would otherwise survive into resume and be read by `_compute_exact_frontier_state` as real certified frontier evidence, prune-dominating candidates that should still be explored. Only a genuine `worker_process_failed` / `worker_crash_respawn_limit` (exact or colon-suffixed) still preserves identity-valid completed progress while the campaign stops `UNKNOWN`.
- Optional frontier probe mode is an exact-safe scheduling hint only and must not replace completeness requirements.
- Global pooling semantics for shared boundary/core resources must remain commodity-aggregated.
- Batch-5 provider geometry is physical and operation-addressed. `protocol_storage_box` is the `box_sink` provider: every candidate pose has 3 physical input ports and 3 physical output ports (no `omni_wireless`, virtual-port, or `port_mode="omni"` authority), while `rules/preprocess_plan.json::utility_operations.box_sink.generic_input_slots = 3`. The mandatory `protocol_core` provider has 14 physical input ports and 6 physical output ports, with `utility_operations.protocol_core.generic_input_slots = 14` and `generic_output_slots = 6`. A declared slot capacity must be realized by the selected pose's matching physical port cells; geometry/capacity mismatch fails binding closed.
- A canonical `sink_kind == "generic_input"` final commodity — including `qiaoyu_capsule` and `valley_battery` — is a normal routed commodity from its recipe producer's physical output front to the physical input front selected on a concrete `protocol_core` or `box_sink` provider instance. Producer outputs and active provider sinks must both reach `extract_port_specs()` and every routing/front consumer; no generic-input-final producer output may be hidden by a routing-free or wireless classification. Provider capacity slots not selected for a commodity remain explicit binding-internal `__unused__` entries and emit no terminal.
- Generic output slot domains must include an explicit unused sentinel (F-BIND-R1-01): full boundary/core output-port occupancy in the current base is a numeric consequence of the exact-count constraints over real commodities (R=S=52, specs/04 §4.5), not a structural domain assumption. Encoding fullness structurally (dropping the `__unused__` choice) turns any requirement-below-slot-count configuration into false-INFEASIBLE. The sentinel is binding-internal only: it must never reach `extract_port_specs()` or any routing/flow surface, and it is a reserved name that may not appear as a commodity in any requirements artifact.
- Generic I/O requirement and provider-capacity loading is fail-closed (F-BIND-R1-02, Batch 5): both requirement sections must be present (a missing section is an error, not an empty default), and `load_generic_input_slots_by_operation()` must return the complete per-operation capacity map with strict non-negative integers (bool/float/string coercion rejected). The current map is `{"protocol_core": 14, "box_sink": 3}`. On the default artifact loading path every generic output commodity must have canonical `source_kind == "external_boundary"` and every generic input commodity canonical `sink_kind == "generic_input"`. All production `PortBindingModel` constructions consume the validated requirements and full provider map; explicitly passed toy maps are test-fixture-only and must not appear in solver/runtime code.
- The fail-closed generic I/O entry point is proof-surface-wide, not binding-local (F-BIND-R2-01): the certified master core consumes generic I/O requirements **before** binding ever runs (hard constraints and certified optional lower bounds derived at `ExactSearchSession` construction), so `master_model.load_generic_io_requirements_artifact()` must delegate to the same fail-closed binding loader — a second, looser parser of the same artifact is a forbidden proof-surface fork.
- Proof-relevant JSON artifact parsing is strict (F-BIND-R2-02): duplicate object keys (Python `json.loads` silently keeps the last value, letting a tampered artifact replace real demand with an empty section or rewrite one provider's capacity) and non-standard JSON constants (`NaN`/`Infinity`) must be rejected at every loader feeding binding/master proof inputs (generic I/O requirements, the per-operation provider-capacity map, canonical commodity-role reads).
- Proof inputs are single-parse, single-snapshot (F-BIND-R3-01..05, F-BIND-R4-01, Batch-5 atomic-map extension): within one certified session, every consumer of a proof artifact must consume the same in-memory snapshot or the same validated loader — the certified binding receives the master's normalized `generic_io_requirements` snapshot instead of re-reading disk (no two-points-in-time fork); `load_project_data`'s JSON reads (mandatory instances, candidate placements, canonical rules) are strict-parsed; utility slot counts in `preprocess_context` are strict non-negative ints; and the **entire** provider-capacity map flows atomically from the snapshotted project-root plan into master optional lower bounds, outer safe-area, campaign proof helpers, coordinate stats, terminal replay, and certified binding construction. A single `wireless_sink` scalar, partial-map fallback, import-time default profile, or later binding-time disk reread is forbidden. Campaign proof helpers load generic I/O through the shared validated artifact loader, never a private parse.
- The single-snapshot seal extends across the outer search and worker processes (F-BIND-R5-01): the certified frontier candidate domain and every solver session proving candidates from it must be sealed to the same artifact snapshot — `run_outer_search` records its domain snapshot (artifact hashes, generic I/O requirements, full provider-capacity map) and every `ExactSearchSession` created or ensured afterwards must match it exactly (mismatch is a `RuntimeError`, not a silent re-read); parallel workers receive the coordinator's expected artifact hashes and fail startup (`STARTUP_ERROR`) when their self-built session disagrees, so no worker can produce candidate proofs in a different artifact universe than the frontier domain they feed.
- Strict parsing extends to the preprocess (re)generation chain (F-PRE-R8-01): the hash closure pins artifact bytes but cannot disambiguate parsing of those bytes, so first-build inputs are a layer below it. Canonical/plan loading in `preprocess_context`, the placement generator's canonical read, `machine_counts` loading in the instance builder, and frozen-parity consumption must all use the shared strict JSON entry (`src/io/strict_json.py`); preprocess artifact writers must emit `allow_nan=False`. A duplicate key in a generation input must fail loudly, never rewrite a target value, a port rule, or a machine count silently. Strictness includes numeric overflow (F-PRE-R9-01): a JSON number literal parsing to a non-finite float (`1e309` → `inf`) must be rejected at the shared strict entry via `parse_float` (`parse_constant` only catches spelled-out `NaN`/`Infinity`), and every preprocess/parity writer — including the context/diff report writer — must write with `allow_nan=False`, so non-finite values can neither enter through a literal nor exit as a non-standard constant.
- Schema validation must run at the file-loading boundary, not exist only as a bystander (F-PRE-R10-01): the preprocess context path loaders (`load_default_preprocess_context`, `load_preprocess_context_from_paths`) must validate strict-loaded canonical/plan payloads against `canonical_rules.schema.json` / `preprocess_plan.schema.json` before context construction applies defaults — a schema-required field silently absorbed by a code-level default is fail-open. The low-level dict-to-context builder stays a pure constructor for test variants; file entrances are the enforcement boundary.
- Closed-form pose generators must verify the canonical geometry they hard-code (F-PRE-R10-02, Batch-3/5 update): the placement generator families that emit frozen geometry (core 9x9 with 14 physical inputs/6 physical outputs, protocol-storage-box 3x3 with 3 physical inputs/3 physical outputs, pole 2x2 with the radius-5 stencil, boundary 1x3 left/bottom, long-sides w>h, square w==h) must fail closed when the canonical template's schema-visible fields (`dimensions`, `core_limits`, port geometry/modes, `power_coverage_radius`, `placement_rule`) drift from those assumptions. A schema-valid canonical edit must never let canonical claim one geometry while generated candidate poses carry another (owner-gated canonical extensions inherit this contract).
- Every canonical file entrance validates schema, not just the context loaders (F-PRE-R11-01): the placement generator's `load_templates()` is an independent canonical file entrance feeding candidate regeneration; like the context path loaders it must run `canonical_rules.schema.json` validation immediately after strict JSON loading. Any future reader that strict-loads canonical bytes from disk inherits this obligation — a schema-required field absorbed by downstream defaults through any entrance is fail-open.
- The geometry contract locks every field the generators consume or implicitly assume (F-PRE-R11-02): beyond the R10 field set, `rotatable` and `is_solid_z` are generator-semantic fields — emitting rotated orientations for a non-rotatable template, or emitting solid `occupied_cells` for a non-solid one, lets schema-valid canonical drift fork canonical semantics from generated poses. `_validate_template_geometry_contract()` must pin the per-family expected values (and type-check them as booleans) before dispatch.
- Cycle-group solutions must be proven non-negative, not just unique (F-PRE-R11-03): a square non-singular cycle system can still yield negative run rates under canonical drift, and downstream demand aggregation filters non-positive entries — silently deleting machines from the frozen demand artifacts. Context validation must prove each net-export commodity admits a non-negative basis solution, every net-export commodity must be an internal commodity of its group, and `_solve_cycle_group_exact()` must fail closed on any negative run rate at solve time.
- Cycle-group demand keys are a closed set, membership-checked at both ends (F-PRE-R12-01): the RHS is assembled by iterating `internal_commodities`, so a positive external demand keyed by a commodity outside that list would be silently dropped — producing frozen demand/instance artifacts that are missing the supporting machines (fail-open). Context validation must require every `cycle_internal` commodity to be listed in its declared group's `internal_commodities` (reverse-index check, not just group existence), and `_solve_cycle_group_exact()` must reject positive demand keys that are not both internal and net-export (preserving the R11-03 proof premise that RHS lies in the non-negative span of proven net-export unit directions) and reject negative demands outright; explicit zero entries stay accepted.
- Cycle groups must be a recipe I/O closure, checked at both ends (F-PRE-R13-01): the cycle solver builds its matrix and downstream machine-run aggregation only over `internal_commodities`, so any cycle recipe input/output referencing a commodity outside that list is silently dropped from demand propagation — under canonical drift a cycle recipe consuming an external commodity (e.g. an ore) would leave the frozen `commodity_demands`/`port_budget`/`generic_io_requirements` artifacts missing that supply requirement while still claiming the 52-port budget feasible (fail-open, the F-PRE-R12-01 membership-closure class extended from demand keys to recipe I/O). Context validation must require every cycle-group recipe's `inputs ∪ outputs` to lie entirely within the group's `internal_commodities`, and `_solve_cycle_group_exact()` must repeat the check at its entry to cover direct solver calls on unvalidated contexts.
- Preprocess recipes are single-output until a coupled co-product demand solve exists (F-PRE-R14-01): the current backward demand expansion owns a commodity by selecting its unique producer and charging that recipe's run rate per demanded output, so a schema-valid multi-output recipe with two demanded products would double-charge the same operation instead of sharing co-products. Canonical rule schema validation, `validate_canonical_document()`, and direct `validate_preprocess_context()` construction must fail closed on `len(outputs) != 1`; relaxing this requires replacing the per-output backpropagation with an explicit coupled recipe-flow solve and updating the frozen-artifact proof obligations.
- Cycle-internal commodity producers are owned by their declared cycle group (F-PRE-R14-02): demand propagation routes any positive demand for a `cycle_group` commodity directly into the cycle solver before consulting the non-cycle producer index, so a recipe outside that group that outputs the same cycle-internal commodity would be ignored while its target/output rate could still seed downstream demand. Context validation must reject any recipe output of a cycle-internal commodity unless that recipe is a member of the commodity's declared cycle group; non-cycle consumption of cycle-internal commodities remains the intended external-demand edge into the group.
- Public preprocess solvers must re-check the full `PreprocessContext` validity before demand expansion (F-PRE-R15-01): the file loaders and builder validate the canonical path, but direct callers can still pass a hand-built or mutated context into `solve_demands_exact()` / `solve_demands()`. That entry must call `validate_preprocess_context()` before computing target rates or backpropagating demands, so the R14 single-output and cycle-internal producer-ownership premises cannot be bypassed. The direct cycle-group solver must also repeat the cycle-internal output ownership guard for the requested group, matching the R12/R13 two-ended membership checks.
- External-boundary commodities must be producer-free (F-PRE-R16-01): demand propagation treats `source_kind == "external_boundary"` as a terminal source and stops before consulting producer recipes. A commodity cannot therefore be both boundary-supplied and recipe-produced; otherwise a schema-valid role drift could skip the producer's machines and upstream inputs while replacing them with generic output slots. Canonical semantic validation and direct `validate_preprocess_context()` construction must both fail closed on any recipe output whose commodity metadata says `external_boundary`.
- Direct cycle solves must repeat the group-local role contract (F-PRE-R16-02): `_solve_cycle_group_exact()` builds its matrix solely from `CycleGroup.recipes` and `CycleGroup.internal_commodities`, so a hand-built context whose group list and commodity-role declarations disagree can be solved even though full context validation rejects it. The raw cycle solver entry must fail closed unless the requested group is square, all recipes exist, every internal commodity declares `source_kind='cycle_internal'` and exactly that `cycle_group`, and every net-export commodity is internal, before matrix/RHS construction.
- A fully enclosed legal empty rectangle remains allowed; exterior connectivity is not part of the exact contract.
- Terminal certified frontier evidence is a closed, project-bound contract: unknown `candidate_generation` keys, non-authoritative domain values, stale evidence schema versions, and sub-admissible terminal best results must fail closed before any public CERTIFIED surface.
- In `certified_exact`, `EXACT_*` environment knobs are deny-unknown by default: only documented operational allowlist entries may be present, known proof-semantics knobs must stay at canonical false/default values, and future/unclassified names must block the run.
- Terminal front polarity is toward the facility body (F-RT-R2-01, re-adjudicated 2026-07-18 front-offset incident): a port spec stores the outward normal `dir` and the stored coordinate `(port.x, port.y)` **IS** the routing front/belt cell itself — the first cell outside the facility body; the physical port sits on the adjacent body-edge cell at `port - dir`. Deriving the front as `port + dir` (the pre-incident reading) is the one-cell offset bug: it checks the second cell outside the body and poisons feasibility in both directions (owner in-game adjudication + 599,384-record frozen-pool scan, `docs/research/front_offset_incident_20260718/00`). The polarity law is unchanged: the source front receives with `flow_in = Opp(dir)` and the sink front sends back with `flow_out = Opp(dir)`. Encoding the sink front in the outward direction rejects legal straight corridors (false-INFEASIBLE) and lets roomy layouts satisfy a phantom outward state without feeding the port. The solver's port indexing/adherence and every independent verifier must derive front identity and polarity from the rule, not from each other — a verifier that copies the solver's key orientation is blind to exactly this class (the diff-fuzz oracle shared the same inverted key for its first 900 instances; the offset incident itself was an all-consumer common-mode failure).
- Per-edge channel conservation holds across layer overlap (F-RT-R2-02): legal L0-straight/L1-bridge overlap on one 2D cell must not let a single directed edge feed both layers or merge two layers into one edge — for every commodity and every non-terminal cell-to-cell directed edge, the number of selected sending states equals the number of selected receiving states. Local "at least one supporter" continuity alone licenses hidden splitters/mergers at overlap cells that the connectivity guard cannot see.
- Terminal front cells are ordinary routable belt cells (F-RT-R3-01, **inverted** 2026-07-18 front-offset incident — supersedes the pre-incident "connector cells are terminal nodes, never belt cells" reading): the stored port cell `(port.x, port.y)` is the front/belt cell where the terminal belt physically sits, so the routing domain must **keep** every in-grid stored port cell in free/active routing cells; the former connector-cell subtraction (`free_cells - port_connector_cells`) was the second half of the offset bug and is removed. Game semantics (owner adjudication): a 1-cell belt is legal and two opposite facing ports may share the single middle cell — the route-state dual index expresses both with zero state-space change. Directional terminal discipline replaces cell exclusion: ordinary route states must not send into a source front against its receive polarity nor receive from a sink front against its send polarity (the successor/predecessor terminal exemptions keyed on the stored cell), and belt/belt co-location on any cell — including a front cell crossed by another commodity's belt — is adjudicated solely by the routing layer's cross-junction constraints (perpendicular straight channels only; a turning belt on the front cell means the port is blocked, owner adjudication 2026-07-18). Facility bodies (power poles included) on a front cell block the port; belts do not. Independent verifiers must check stored-cell body-occupancy as their own rule-derived predicate.
- Same-commodity terminal fronts may live in multiple disconnected components (F-RT-R4-01): the routing-domain precheck must not require all terminal fronts of a commodity to share one connected component — the rule semantics (each source front reaches some sink front, each sink front is reached by some source front; specs/08 pool model) admit multiple physically disconnected islands each closing its own supply/demand. When a commodity has both sources and sinks, every terminal-bearing component must contain at least one source front and one sink front, the active domain is the union of the satisfying components, and per-component core peeling applies; collapsing this to a single-component requirement rejects legal layouts (false-INFEASIBLE through the binding-local safe-reject consumption of `relaxed_disconnected`).
- Terminal front keys must be unique per physical port (F-RT-R4-02): two port specs folding onto the same `(front, terminal_dir, commodity, type)` key would collapse two exact-one adherence obligations into one (multiplicity lost). Canonically unreachable (identity semantics: a shared front cell with the same `dir` implies both facilities occupy the same body-side cell at `front - dir`, which master no-overlap forbids across facilities and the generator never emits within a pose; opposite-facing ports sharing the middle cell differ in `terminal_dir`/`type` and do not fold), but externally supplied `port_specs`/`domain_analysis` can construct it — the precheck and the solver build must both fail closed (`front_blocked`/reject) on duplicate terminal front keys rather than silently folding.
- Externally supplied routing domains must be clipped to the real free grid (F-RT-R5-01, identity-updated 2026-07-18): binding a caller-supplied `domain_analysis` must intersect every commodity's active/component cell set with `grid.free_cells` (stored port cells are ordinary free cells and stay in — the pre-incident `- port_connector_cells` subtraction is removed with F-RT-R3-01's inversion). The CP-SAT obstacle exclusion is implemented as "route states are only created on active domain cells", so a stale or hostile external analysis containing an occupied solid cell would otherwise materialize route states on solid cells and produce an accepted `FEASIBLE` through a wall (false-FEASIBLE; specs/09 solid obstacle exclusion). Occupied cells and out-of-grid cells must both be rejected by the same intersection; a port front clipped out of the active domain stays fail-closed through the `0 == 1` adherence guard.
- Routing CP-SAT `FEASIBLE` is not a certification boundary by itself: certified acceptance must rebuild the selected per-commodity route-state graph and prove every source front reaches a sink front and every sink front is reachable from a source. A locally closed but globally disconnected incumbent must be rejected and re-solved; if the budget is exhausted before a connected incumbent is found, the certified path returns `UNKNOWN`/`TIMEOUT`, never `CERTIFIED`.
- P0-1 lazy routing connectivity cuts are acceleration-only proof obligations: every source-side component cut must independently revalidate its `W`/`X` certificate (source fronts in `W`, sink fronts outside `W`; removing `X` disconnects all source fronts from sink fronts in the full potential state graph; incumbent selected states are disjoint from `X`) before attachment, otherwise it must fall back to the selected-positive nogood.
- Certified generic-input provider lower bounds are provider-aware and instance-aware (F-GM-Q3-01, Batch 5). Compute gross positive `required_generic_inputs`, subtract the physical generic-input capacity supplied by mandatory provider instances according to the atomic operation map, and only then convert residual demand into optional `protocol_storage_box` instances at `box_sink=3` slots each. In the current frozen project, gross demand is `2`, the mandatory `protocol_core` contributes `1 × 14`, residual demand is `0`, and the certified `protocol_storage_box` lower bound is therefore `0` — never `ceil(2/3)=1`. Fixed required optional providers count as constant capacity contributions; only a remaining shortfall may be demanded from the residual optional pool. Encoding the bound over a single provider type, over the residual pool alone, or from a partial provider map turns valid mandatory-provider configurations into false-INFEASIBLE. The dual obligation (F-GM-Q3-01-R3-A): when fixed required slots exist but do not satisfy the lower bound (`0 < fixed < lower`), the residual optional pool must still be constructed so the shortfall has literals to draw from — skipping residual slot construction whenever any fixed slot exists encodes `0 >= shortfall` and turns legal fixed+residual mixes into false-INFEASIBLE. Residual pool sizing and powered residual upper-bound statistics must both subtract the fixed count from the template upper bound (no double-spending the same capacity) and must use the same residual-needed predicate as slot construction (no one-sided fixes splitting bucket preparation from slot creation). Fixed required optional slots must carry the template's full role semantics (F-GM-Q3-01-R4-A): a fixed `power_pole` slot is a real pole, not just a geometric footprint — it must enter pole family membership/count channels and the table/geometric power-coverage witness enumeration; under "fixed fully represents the template" semantics the residual pole pool is skipped, so a fixed pole left out of the power channels turns legal fixed-pole-powered configurations into false-INFEASIBLE. The degenerate boundary (F-GM-Q3-01-R5-A): attaching fixed poles to the capacity-family channel is only meaningful when the family mapping exists — when power coverage is skipped or the model has no powered demand at all, the family table is legitimately empty and the attach must be skipped entirely rather than emitting an empty-table `0 == 1` (which rejects legal geometry-only fixed-pole configurations). With a non-empty family mapping, an unexpectedly empty tuple table keeps the fail-closed rejection.
- Terminal protocol-storage-box minimality is a **fresh fixed-witness dominance** obligation (V94, Batch 5), not a placement-only cardinality rejection. The campaign must not reject a selected layout merely because its box count exceeds the provider-aware lower bound. At the terminal publication boundary, the isolated fixed-witness replay must freshly rebuild binding and routing against the actual selected provider instances and physical ports, require the `generic_inputs` assignment to cover the complete slot-id set atomically (including explicit `__unused__` values), and prove every required generic-input commodity has both its routed producer source and exactly its required number of active physical provider sink endpoints. Every selected optional `protocol_storage_box` must bind at least one active physical `box_sink` generic-input sink; otherwise publication fails closed with `terminal_fixed_witness_unbound_storage_box_violates_dominance_rule`. A cached, partial, or placement-only witness has no authority for this decision.
- Applying a cut must invalidate the previous solver witness, not just the solution cache (F-GM-R6-01): a successfully added Benders cut changes the model, so the pre-cut `CpSolver` assignment is no longer a witness for the current model. Clearing only `_last_solution` leaves `extract_solution()` / `extract_bound_state()` free to rebuild the just-forbidden placement (or its objective bound) from the stale solver until the next solve. Cut application must clear the solver and status on both the exact-coordinate and legacy paths so post-cut, pre-resolve extraction returns empty/no-incumbent instead of a stale witness. The LBBD main loop re-solves immediately after cutting, so this is an API-surface fail-closed obligation; it binds any future consumer that extracts between cut and re-solve.
- Solution hints are search guidance only and malformed entries degrade to skip (F-GM-R7-HINT-01): the hint path (greedy, community blueprint merge, ghost anchor) may only write the CP-SAT `solution_hint` proto via `AddHint` — never constraints — so a wrong hint can cost time but can never change the feasible set or the conclusion. Malformed hint entries (non-int pose index, out-of-range pose, unknown ghost anchor index) must be skipped instead of raising pre-solve: a performance suggestion must not be able to interrupt a certified solve. Each solve clears the previous hint proto before applying the current one. Hint index parsing is strict-int end to end — bools, floats, and numeric strings are skipped, and no later stage (telemetry included) may re-coerce a rejected raw value (F-GM-R8-HINT-02). Every hint-value ingress (coordinate delegate, community blueprint merge, legacy solve fallback, pose-bool delegate) parses through the single shared `src/models/solution_hint_parser.py` helper — a new ingress with its own ad-hoc `int()` re-opens the truncation seam (R9 closed three such residual ingresses; R10 closed the persisted master-hint ingress — `master_hint_persistence.py` `write_master_hints`/`load_master_hints` plus the legacy `apply_master_hints` path — where `write` fails closed with `TypeError` on a non-int value and `load`/`apply` skip it, LOW-HINT-R10-01).
- Symmetry breaking may impose at most one total order per interchangeable slot family (F-GM-R8-SYM-01): every symmetry constraint must preserve at least one representative of each feasible equivalence class. Two simultaneous monotonic orders over different keys (slot `order_key` and `signature_int`) are NOT jointly representative-preserving — a pose pair ascending in one key and descending in the other leaves no arrangement satisfying both, deleting the entire class (false-INFEASIBLE; under `max_lex` this silently drops true maximal rectangles, and real candidate pools contain such reversed pairs). A secondary monotonic order may only be added when it is provably a consequence of the primary order over the family's full candidate set (same-order gate), and skipped families must be visible in telemetry.
- The env-gated pose-bool master backend is in geometry-master scope and its soundness obligations mirror the coordinate backend's (F-GM-R11-PB-01): even though `PoseBoolExactMasterDelegate` is reachable only under `EXACT_USE_POSE_BOOL_MASTER=1` and is gated off the public certified path by `pose_bool_master_not_certified`, it is a directly enablable master backend, so its false-FEASIBLE and stale-witness seams bind. (a) Fixed required `power_pole` demand must be enforced on the shared pole pool (F-GM-R11-PB-REQ-POLE-01): the pose-bool build previously `continue`d past `exact_required_pose_optional_counts["power_pole"]`, building only a residual optional pole pool with "no demand fix", so when every pole pose is excluded by the ghost body the model returned `OPTIMAL` with no pole — a true INFEASIBLE minted as FEASIBLE (the coordinate-backend obligation F-GM-Q3-01-R4-A recurring in the pose-bool backend). The fixed demand must accumulate and, once feasible pole vars exist, add `sum(pole_vars) >= required_power_pole_demand` (and `0 >= demand` fail-closed when feasible poles number fewer than the demand); `>=` not `==` so residual poles may still appear as extra coverage witnesses, and `required_optional_slots["power_pole"]` is populated so slot/statistics semantics stay visible. (b) Applying a pose-bool local-model cut must invalidate the owner solver witness, not just `_last_solution` (F-GM-R11-PB-STALE-01, same shape as F-GM-R6-01): the delegate's incremental cut paths (`add_patch_routing_core_cut`, `add_separator_capacity_cut`, `add_benders_cut`, `add_routing_port_lazy_demand_cut`, `add_routing_port_blocking_cell_cut`) must clear `owner._last_solution`/`_solver`/`_status` together through a shared `_invalidate_owner_solver_witness()` helper, or `MasterPlacementModel.extract_solution()`/`extract_bound_state()` rebuild the just-cut placement from the stale `CpSolver` until the next solve.
- Coordinate exact master geometry must be keyed by each candidate pose's `occupied_cells` footprint, not by template default dimensions alone. No-overlap, ghost interaction, and power-coverage witness spans must use a mode-channelled footprint bounding box derived from the selected pose; non-rectangular footprints may be conservatively over-approximated by that box but must not under-approximate.
- `binding_selection_safe_reject=True` routing precheck evidence is binding-local. `front_blocked` and `relaxed_disconnected` must first add a binding-level nogood and enumerate alternative port bindings while any remain. A master placement-level nogood is allowed only after binding alternatives are exhausted or an independent placement-level proof exists; otherwise the certified path fails closed as `UNKNOWN`. When `EXACT_BINDING_USE_OVERLOAD_SEPARATION` is active and has injected hard overload nogoods, an `INFEASIBLE` binding re-solve is not on its own an exhaustion proof (F-BIND-R8-01): every binding re-solve site must first retry with overload separation forced off and **all** prior routing-rejected selections replayed, and only an env-off `INFEASIBLE` that survives the replay may feed the exhaustion chain (an env-off `FEASIBLE` resumes enumeration; a `TIMEOUT` fails closed as `UNKNOWN`) — otherwise the heuristic's local nogood exhaustion is miscertified as true binding/routing exhaustion (false-INFEASIBLE).
- `load_generic_io_requirements()` integrity (F-BIND-R8-02 / F-BIND-R9-01, Batch-5 meaning): once a generic I/O requirements artifact is non-empty (either `required_generic_outputs` or `required_generic_inputs`), its `required_generic_inputs` section must cover every canonical `sink_kind == generic_input` commodity with a positive slot count, else the loader fails closed — a missing or non-positive entry would silently remove the required physical provider endpoint while leaving the recipe producer output routing-visible, creating an unmatched routed source and spurious `front_blocked` / false-INFEASIBLE. A fully empty requirements set (both output/input sections empty) remains a legal degenerate case (early return); an output-only artifact is non-empty and must be rejected by the same completeness check.
- Budget exhaustion is never an exhaustion proof (F-BL-R3-01): hitting an enumeration cap (e.g. `EXACT_B1_BINDING_ALT_CAP`) while binding alternatives remain must return `UNKNOWN` without minting any binding-level or whole-layout nogood — only a binding CP-SAT `INFEASIBLE` re-solve proves the alternatives are exhausted. Likewise the main loop consumes subproblem statuses through an explicit contract (F-BL-R3-02): any routing status other than `FEASIBLE`/`INFEASIBLE`/`TIMEOUT` fails closed as `UNKNOWN` with no cut, never down the infeasible branch. The same contract binds every binding solve and re-solve site (F-BL-R4-01): any binding status other than `FEASIBLE`/`INFEASIBLE`/`TIMEOUT` — at the initial solve, overload-fallback retry, precheck safe-reject re-solve, relaxed-disconnected re-solve, or post-routing-INFEASIBLE re-enumeration — fails closed as `UNKNOWN` (`subproblem_status_contract_violation="unexpected_binding_status"`) without entering the exhaustion chain; only a contract-valid binding `INFEASIBLE` re-solve may feed the binding/routing-exhausted whole-layout nogood. The same status contract binds the routing precheck consumer (F-BL-R7-01): `_run_exact_binding_and_routing()` must check `run_exact_routing_precheck()['status']` against the verified allowlist `{feasible, front_blocked, relaxed_disconnected}` before any B1 bypass, front-blocked cut, relaxed-disconnected branch, or routing build — because `RoutingSubproblem.build()` adds `0 == 1` whenever `domain_analysis['status'] != 'feasible'`, an un-allowlisted precheck status (`TIMEOUT`/`UNKNOWN`/`MODEL_INVALID`/`ERROR`/misspelled, or a captured precheck exception coerced to status `ERROR`) would otherwise be transcribed into a CP-SAT `INFEASIBLE` proof and could mint a whole-layout nogood deleting a legal master solution. Any non-allowlisted status fails closed to `UNKNOWN` (`subproblem_status_contract_violation="unexpected_routing_precheck_status"`, `master_follow_up="fail_closed_unknown"`), building no routing subproblem and registering no cut.
- Master-level cell-pattern cuts may only quantify over necessarily-active ports (F-CUT-R2-01): the env-gated pose-bool cell cut `sum(poses with a port at (cell,dir)) + sum(poses occupying the front cell) <= 1` is exact only when every enumerated port candidate is necessarily active and routing-visible whenever its pose is selected — the side's visible demand must cover all physical ports on that side (input: concrete routing-visible `input_demand >= physical_port_count`; output: visible output non-zero, equal to total output, and `>= physical_port_count`). Generic-input provider slots are **physical routed ports when bound**, but slot capacity is not mandatory per-port activity (CUT-R3-H1): a `protocol_core` or `box_sink` pose can retain `__unused__` physical input slots, so raw provider capacity alone must not enter necessarily-active front demand. Generic-output slots likewise count only when the required generic-output total globally saturates the mandatory capacity (saturation forces every physical slot away from `__unused__`), and the capacity total must be computed fail-closed — any provider group whose instance count is unknowable makes capacity unknowable and the side is not registered. A blocked port that binding may leave inactive does not make pose+blocker infeasible (binding can select another slot), so registering optional binding slots — or residual-optional poses without operation binding identity — in the routing-visible per-cell port index over-cuts feasible placements; use the weaker exact lazy-demand/count cut until a binding-aware/global activity proof exists. Candidate pose data is global-coordinate: port/cell lookup caches must not re-apply the anchor offset (double-anchoring aliases candidates to phantom cells, silently missing or mis-targeting cuts). The hook is blocked on the public certified path by the `pose_bool_master_not_certified` env guard; this clause binds any future promotion of pose-bool/cell cuts into certified.
  CUT-R4-H1 Batch-5 addendum: `routing_free_sink_commodities_from_generic_inputs()` is empty by contract, so a generic-input final's producer output cannot be removed from routing visibility and there is no current mixed visible/routing-free branch. Generic-output saturation still proves only non-`__unused__`; any future terminal-hiding classification requires a new explicit authority and binding-aware proof rather than reviving the superseded wireless exception.
- The PCR-CUT patch model must be a relaxation (over-approximation) of full routing, end to end (PCR-R5): the entire proof value of `patch INFEASIBLE ⇒ layout INFEASIBLE` rests on the patch CP-SAT accepting every continuation the full model accepts. Four obligations bind this (each was violated once): boundary relaxation must exist for **every** routing layer, not just ground (an elevated bridge crossing the artificial patch border must remain feasible, PCR-R5-H1); patch port-front polarity must match `RoutingSubproblem` exactly — input/sink fronts send toward the connector via `Opp(dir)` (PCR-R5-H2, the F-RT-R2-01 polarity class recurring in a re-implementation); constant-occupancy support must be carried into the conflict core and master terms — patch cells plus their cardinal boundary neighbors whose occupancy shaped the infeasibility must appear as assumptions/terms, otherwise the cut blames the victim pose unconditionally while the real blocker walks (PCR-R5-H3); and signature lifting must fail closed when lifted master var sets overlap — a duplicated BoolVar in the linear nogood strengthens `co-occurrence forbidden` into `single pose forbidden` (PCR-R5-H4). Replay validation (presolve=false, workers=1) re-proves the patch model's own UNSAT; it cannot substitute for these encoding-level relaxation obligations. QuickXplain cap hits may return a non-minimum core (weaker cut) — never treat the result as a global minimum.
- Patch port membership is decided by terminal-front intersection, not connector membership (PCR-CUT-R6-H1, fifth relaxation obligation): a port whose connector cell lies outside the patch but whose terminal front cell lies inside still injects/absorbs flow inside the patch in the full model — dropping it makes the patch stricter than full routing, and boundary relaxation cannot compensate because the connector cell is occupied and never receives boundary variables. Port indexing, port adherence, separator patch-port collection, and local pose signatures must all include a port when its connector **or** its front cell intersects the patch (front-in-patch external connectors enter the signature so lifting cannot merge poses whose terminals do and do not touch the patch).
- A separator's master cut may not be narrower than the layout context compiled into its model (CUT-R8-H1, the PCR-R5-H3 constant-support obligation restated for every separator channel): a CP-SAT assumption core only covers assumption literals, while any layout state baked into the model as constants (occupancy grid from selected footprints, helper terminal positions) is unguarded proof context. A cut over the raw core alone upgrades "this terminal subset is infeasible under the current obstacles" into "these poses are infeasible in any layout" — over-cut. The master conflict tuple must include every selected pose that contributed compiled constants (all occupancy contributors and all current port owners, ghost excluded) alongside the raw core; augmenting only weakens the cut, keeping its forbidden set within the proof obligation. The env-gated D2 commodity-flow rung violated this once (`EXACT_B1_D2_COMMODITY_FLOW`, raw-terminal-core cut while the entire layout footprint was a model constant).
- A separator model that is not a proven relaxation of production routing is not a master-cut proof source (CUT-R9-H1): the D2 commodity-flow core is stricter than production routing in at least two encodings — its per-cell `AddAtMostOne` is 2D and cannot express two commodities crossing the same cell on different layers (bridges), and its unit flow conservation cannot express splitter/merger topology (one source feeding multiple sinks). A production-feasible layout can therefore be D2-INFEASIBLE, and even a fully support-augmented cut would forbid it (over-cut on top of, and independent from, CUT-R8-H1). Until a separator's model is proven a relaxation end-to-end (the PCR-R5 obligation family), its INFEASIBLE may only gate telemetry/core-shrinking; the master cut's proof source must be an independent production-side impossibility proof for the same compiled context — the D2 rung now requires the production routing precheck to classify the same occupied grid + port specs as `front_blocked`/`relaxed_disconnected` (deny-unknown on every other status) before any cut is emitted, with the separator-side occupied compilation kept at or below the production occupancy (ghost excluded) so the blocked/disconnected judgement stays monotone-safe.
- The power-conditioned infeasible cut must keep the full non-pole fixed-occupancy support (CUT-R12-H1, the CUT-R8-H1/PCR-R5-H3 constant-support obligation surfacing in the power-conditioned cut channel): `PowerPlacementSubproblem` filters candidate poles against *all* fixed master occupancy — every selected non-`power_pole`, non-`ghost_pick` facility — not only powered consumers, so an INFEASIBLE proof can hinge on an unpowered facility (real data: `boundary_storage_port` ×46, `protocol_core` ×1) blocking the only covering pole cell. The exact-safe `power_subproblem_infeasible_nogood` `conflict_set` must therefore include every non-pole, non-ghost selected occupancy (fail closed to ABORT on an unparseable `pose_idx`), not just the powered-instance tuple — otherwise moving the unpowered blocker away while the powered tuple and ghost anchor stay fixed leaves a legal layout falsely forbidden. Gated behind `EXACT_POWER_PLACEMENT_SUBPROBLEM` (deny-unknown in certified, forensic-bypass only), HIGH the moment that channel is opened.
- The delegated power FEASIBLE witness must share the selected ghost context of its proof and fail closed when that context is unrecoverable (CUT-R13-H1, the CUT-R8-H1/PCR-R5-H3 proof-context obligation surfacing on the power witness FEASIBLE path): `_run_power_placement_subproblem()`'s FEASIBLE branch injects synthetic `power_pole` cells into the certified solution, and their legality rests on the same selected empty rectangle as the master — the witness poles must avoid both fixed master occupancy and the selected ghost rectangle (the subproblem compiles `ghost_cells` into fixed obstacles). The INFEASIBLE cut path already ABORTs when `_selected_ghost_anchor()` is unrecoverable, but the FEASIBLE path historically built and solved a de-ghosted subproblem regardless; a lost ghost context (a master variant without recoverable `u_vars`/`_ghost_domains`/solver handle, or an empty `_selected_ghost_cells()`) could then place a pole inside the selected ghost rectangle and certify an illegal completion. The selected ghost anchor and a non-empty ghost cell set must therefore be recovered **before** the subproblem is built — ABORT (fail-closed UNKNOWN: no cut, no injected witness) on a missing anchor or empty ghost cells — and the INFEASIBLE cut path must reuse that same `(rect_idx, u_var, anchor)` so both branches share one ghost context (no TOCTOU drift between witness and cut). Gated behind `EXACT_POWER_PLACEMENT_SUBPROBLEM` (deny-unknown in certified, forensic-bypass only), HIGH the moment that channel is opened.
- Precheck-elimination campaign writes must re-verify the full INFEASIBLE precheck contract, not just `triggered=True` (F-PS-R6-01, conditional hardening): `_record_precheck_elimination()` marks a candidate `INFEASIBLE` on both the serial and parallel coordinator precheck paths whenever the precheck outcome reports `triggered`. A precheck result that is `triggered` yet not internally self-consistent (`status` / `proof_summary.master_status != INFEASIBLE`, or a missing `master_candidate_precheck` skip record) must fail closed and continue to the solver/worker instead of writing a strong `INFEASIBLE` record. Canonical `evaluate_exact_candidate_pre_master_precheck` hard-binds `status=INFEASIBLE` on every `triggered=True` return, so the divergent shape is unreachable on the certified path with canonical data + default env; this is a fail-closed guard against future drift, not a reachable false-INFEASIBLE.
- Direct/raw `PreprocessContext` entries must enforce mapping key/inner-id identity and the cycle-group reverse contract (F-PRE-R17-01 / F-PRE-R17-02, conditional hardening): a hand-built context whose `commodity_roles` dict key differs from the inner `CommodityRole.commodity_id` can pass `validate_preprocess_context()` (which checks the inner id) yet short-circuit demand backprop on the key (machine undercount 219→169, false-FEASIBLE direction); and the raw `solve_cycle_group_exact()` local contract checked only the forward direction (each internal commodity has a role) but not the reverse (a role declaring a `cycle_group` must be listed in that group's `internal_commodities`), so the raw entry accepted a context that full validation rejects. `validate_preprocess_context()` must enforce key==inner-id (str-typed) across every proof-critical mapping, and the raw cycle contract must add the reverse-membership scan. Canonical build derives dict key and inner id from one loop variable and canonical cycle data is fully self-consistent, so both divergences are reachable only via hand-constructed dataclasses — public/direct-entry hardening, not a certified-path break.
- Operation slot counts must use exact rational ceiling, not float-epsilon ceiling (F-BIND-R10-01, conditional hardening): `_rate_to_slots()` used `ceil(rate / capacity - 1e-9)`, which rounds a rate fractionally above an integer multiple of capacity down one slot (e.g. `1.0000000005 / 1.0` → 1 slot where 2 are needed), under-requesting a physical binding slot (false-FEASIBLE / false-CERTIFIED direction). The slot count must be computed from the `PreprocessContext`'s exact `Fraction` rate/capacity with rational ceiling. Canonical profiles use only rate ∈ {0.2, 1, 2, 3} with capacity 1.0 and never land in the `(N, N+1e-9]` band (0 slot-count mismatch across all 17 recipes), so the boundary is latent on the certified path with packaged data; this is invariant hardening for future/alternate rates, not a reachable certified-path break.
- The delegated power witness's selected-ghost context must be recovered as one atomic `(rect_idx, u_var, anchor, cells)` unit (CUT-R14-H1, completing the CUT-R13-H1 ghost-context obligation): `_selected_ghost_anchor()` and `_selected_ghost_cells()` were two independent scanners, so under multiple `u_var` reading selected, or a selected domain whose cells fail to parse while a later domain parses, the FEASIBLE path could take rect A's anchor/condition literal but rect B's `ghost_cells`, injecting a synthetic pole inside the selected empty rectangle. A single `_selected_ghost_context()` must atomically recover a unique selected ghost with explicit anchor x/y and a fully-parseable cell set geometrically consistent with `ghost_rect`, and both the FEASIBLE witness and the INFEASIBLE cut must reuse it (ABORT fail-closed on divergence; no `(0,0)` anchor fallback). Gated behind `EXACT_POWER_PLACEMENT_SUBPROBLEM` (deny-unknown in certified, forensic-bypass only); canonical `AddExactlyOne` + same-loop cell construction make the split unreachable on the certified path, HIGH the moment that channel is opened.
- The env-gated pose-bool master backend must encode ghost-anchor exclusion and certified optional lower bounds (F-GM-R12-PB-01, continuing the F-GM-R11-PB-01 pose-bool obligation line): even though `PoseBoolExactMasterDelegate` is reachable only under `EXACT_USE_POSE_BOOL_MASTER=1` and `RuntimeError`-gated off the certified path (`pose_bool_master_not_certified`), its false-FEASIBLE seams bind. (a) F-GM-R12-PB-GHOST-01: when a ghost rect exists but `ghost_anchor_filter is None`, the pose-bool build emitted no ghost-anchor `u_vars` / `AddExactlyOne` / body-overlap, leaving the ghost wholly unconstrained — a true INFEASIBLE (1×1 grid + required pole + 1×1 ghost) minted OPTIMAL. The build must explicitly enumerate ghost-anchor BoolVars with `AddExactlyOne` and body-only overlap (faithful to the coordinate/legacy `_add_ghost_rect_constraints`). (b) F-GM-R12-PB-PROTOCOL-LB-01: the pose-bool optional block read only `_exact_required_pose_optional_counts` and skipped `_certified_optional_lower_bounds`, so a provider/instance-aware residual `protocol_storage_box` lower bound with an insufficient candidate pool returned OPTIMAL where certified-correct is INFEASIBLE; the bound must be encoded as `sum >= max(fixed, lower)` (fail-closed when candidates are insufficient). The current frozen lower bound is zero because mandatory `protocol_core` capacity 14 covers demand 2; alternate snapshots must recompute it from the full provider map, never a wireless scalar. The certified path uses `ExactCoordinateMaster`, which already encodes both correctly; these are env-gated backend hardening, not a certified-path soundness reset.
- The env-gated B1 routing-precheck bypass must fail closed on build-time domain contradiction, and the precheck status read must not fail open (F-BL-R8-01 / F-BL-R8-02 / F-BL-R8-03): under `EXACT_USE_POSE_BOOL_MASTER=1 + EXACT_B1_BYPASS_ROUTING_PRECHECK=1` the bypass flipped local `precheck_status` `front_blocked → feasible` without updating `routing_domain_analysis['status']`, so `RoutingSubproblem.build()` still inserted `0 == 1` on the stale `front_blocked` domain and the old loop could consume that build contradiction as a routing-`INFEASIBLE` whole-layout nogood deleting a legal master layout (F-BL-R8-01, env-gated false-deletion). A build-time guard must read `build_stats['domain_analysis']['status']` after build and fail closed to `UNKNOWN` (no cut) on any non-`feasible` build-domain status (F-BL-R8-03 same-type residual; canonical duplicate terminal-front is already classified `front_blocked` in precheck, unreachable without an external port-spec fork). The precheck status read must use a `MISSING_STATUS` sentinel rather than defaulting a malformed precheck dict to `feasible` (F-BL-R8-02 — first-party `run_exact_routing_precheck()` always returns a status, canonical-unreachable; availability hardening). All three are gated off the certified path (the bypass needs both env flags, and `EXACT_USE_POSE_BOOL_MASTER` alone is blocked by `pose_bool_master_not_certified`); none is a certified-path soundness reset.
- The routing-precheck/build consumer must deny-unknown on three further malformed-load paths (F-BL-R9-01 / F-BL-R9-02 / F-BL-R9-03, conditional hardening extending F-BL-R7-01): (01) the post-build domain guard read only `build_stats['domain_analysis']['status']` and missed a third build-time `0 == 1` from `_add_port_adherence()` when a port front cell is absent from `commodity_active_cells` while the domain status is still `feasible` — `port_adherence.blocked_ports > 0` must fail closed to `UNKNOWN` before the routing `INFEASIBLE` is consumed as a whole-layout nogood; (02) a `front_blocked`/`relaxed_disconnected` precheck summary missing its `_analysis` mapping skipped the summary↔analysis identity check and could feed a placement-local nogood from summary-only evidence — a non-feasible precheck must carry a mapping `_analysis` with matching status or fail closed; (03) the reject-status cut read `bool(summary.get('binding_selection_safe_reject'))`, so a truthy text like `"False"` counted as True — the safe-reject proof bit must be a literal `True` and consistent between summary and `_analysis`. All three are canonical-unreachable (first-party `run_exact_routing_precheck` always attaches `_analysis`, `analyze_exact_routing_domain` returns literal-bool safe bits, `_peel_terminal_core` never drops terminal front cells so canonical `blocked_ports == 0`); they harden against external/future domain-analysis drift (false-deletion direction), not a reachable certified soundness reset.
- The env-gated pose-bool backend must build real geometry for a no-ghost direct solve and must honor skip-power-coverage (F-GM-R13-PB-NOGHOST-NOOP-01 / -SKIPPOWER-01, continuing the F-GM-R11/R12-PB pose-bool line): with `EXACT_USE_POSE_BOOL_MASTER=1` and `ghost_rect is None`, the pose-bool `build()` short-circuited to an exact-core packaging no-op adding zero constraints (no mandatory `AddExactlyOne`, no no-overlap), so the empty CP-SAT model returned OPTIMAL regardless of feasibility — the packaging no-op must be gated behind an explicit `_pose_bool_exact_core_proto_build` sentinel and a direct no-ghost solve must build mandatory/no-overlap normally (NOGHOST-NOOP-01). The power-coverage block ignored `skip_power_coverage=True`, pinning a legal geometry-only powered pose to 0 (SKIPPOWER-01, availability/false-INFEASIBLE). Reachable only under the env flag and off the certified path (blocked by `pose_bool_master_not_certified`); env-gated backend hardening, not a certified soundness reset.
- The delegated power FEASIBLE witness must not inject a synthetic pole that collides with an already-present pole, and must fail closed on a mixed-power context (CUT-R15-H1, extending CUT-R13-H1/CUT-R14-H1 on the power-witness injection side): when the entry solution already contains a `power_pole`, the subproblem excludes it from fixed occupancy and the injection side performed no second geometric disjoint check, so a different-`pose_id` synthetic pole could be injected onto the same cell. The injection must ABORT fail-closed (no subproblem build, no witness, no cut) on this mixed-power context. Gated behind `EXACT_POWER_PLACEMENT_SUBPROBLEM` (deny-unknown in certified, forensic-bypass only); not a certified soundness reset.
- Direct/raw preprocess entries must inherit the R17 identity guard, use exact rational machine-count ceiling, and enforce the positive-rate recipe contract (F-PRE-R18-01 / -02 / -03, conditional hardening extending F-PRE-R16/R17): (01) raw `solve_cycle_group_exact()` did not run the R17-01 key/inner-id consistency guard before matrix construction — it must; (02) `ceil_machine_count()` used the `ceil(float(x) - 1e-9)` float-epsilon family (same shape as F-BIND-R10-01) and could under-count a regenerated `required_generic_outputs` slot — it must use exact `Fraction` ceiling and route the proof-critical regeneration through `solve_demands_exact()`; (03) a direct `PreprocessRecipe` did not repeat the schema positive-rate contract — full/direct/raw must all reject non-positive `ticks_per_cycle`/input/output amounts. Canonical build derives ids from one loop variable, canonical rates never hit the epsilon band, canonical recipes are positive — all three are reachable only via hand-built/future data; direct-entry/future-rate hardening, not a certified soundness reset. (The binding-face same-type residual F-BIND-R11-02 is this same `ceil_machine_count` fix; F-BIND-R11-01 — a strict-JSON Decimal source loader so JSON float tokens cannot bypass the exact ceiling — is a separate conditional-latent hardening that was deferred in round-2 (its patch overlapped the landed preprocess r18 changes), then **re-confirmed by binding r12 and landed** in round-3 as the opt-in `exact_decimal` Decimal source loader (default-off, so env-off/non-opt-in callers are unchanged; canonical preprocess loading opts in).)
- Campaign resume validation must reject a torn/partial on-disk state rather than resume from it (F-CAM-R6-01, conditional availability hardening): a crash between the write and a clean campaign-state reset could leave an on-disk state that `_validate_resume_state` accepted yet was semantically partial; resume validation must fail closed (clean reset / `UNKNOWN`) on such a state. Reachable only under a real crash/torn-write at a narrow window — an availability/robustness obligation, not a reachable false-CERTIFIED soundness reset.
- Every precheck-elimination strong-write site must go through the shared INFEASIBLE-contract validator, not just the outer coordinator gate (F-PS-R7-01, conditional hardening extending F-PS-R6-01): the F-PS-R6-01 fix validated the outer coordinator precheck-elimination write, but `run_benders_for_ghost_rect()` still used a bare `triggered == True` to promote a precheck outcome to a strong `INFEASIBLE` record. The precheck-elimination contract must be a shared validator used by both the outer and the solver-entry write sites. Canonical prechecks always carry a self-consistent INFEASIBLE shape, so the bare-triggered promotion is canonical-unreachable; drift-only fail-closed hardening (false-INFEASIBLE direction), not a certified soundness reset.
- The RAB-SEP EMPTY_DOMAIN placement-local cut channel is bound by the constant-support obligation (F-BL-R11-01, the CUT-R8-H1 obligation restated for build-time filter evidence, all-or-nothing per the F-BL-BS-01 doctrine; admitted by the adversarially verified soundness review `docs/research/rab_sep_promotion_20260716/01_front_free_necessity_soundness_review.md` v2, 2026-07-16): a `rab_sep_clear_deficit_certificate` conflict tuple must include the owner pose and **every** blocker pose whose occupancy contributed a rejection to the empty filtered domain — certificate emission fails closed (no cut) when any rejection lacks blocker attribution (an in-grid occupied front with no owner attribution breaks the occupied/owner same-source invariant of `build_routing_binding_context()`) or when any blocker literal cannot be resolved to a placed pose (a silently narrowed certificate deletes legal layouts); and the unconditioned thin fallback `{owner: pose}` (a global pose ban) may only be minted for pose-intrinsic emptiness (all rejections out-of-grid) — any layout-dependent emptiness (non-empty blockers, or incomplete attribution) forbids the thin fallback, the owner is skipped, and an all-skipped iteration fails closed through the existing cut_stall → `UNKNOWN` path. `build_routing_binding_context()` must exclude non-facility placement markers (`ghost_pick`) from occupancy so that empty-domain evidence stays ghost-agnostic (the emitted nogoods are unconditioned across anchors). On this basis `EXACT_B1_ROUTING_AWARE_BINDING` is certified-allowlisted (proposition N: a routing-visible port front out-of-grid or body-occupied makes the certified routing predicate infeasible — live guard is the `RoutingSubproblem.build()` non-feasible-domain `0 == 1` short-circuit, with the active-domain/adherence layer as independent depth; the filter is a sound relaxation with routing-visible port-set equality to `extract_port_specs()`); the knob stays default-OFF and sentinel regressions live in `src/tests/test_rab_sep_soundness_sentinels.py`.
- The front-clear necessary-condition lift into the certified coordinate master (F-GM-FCL-01, 2026-07-16 front-clear lift batch; design + four-seat adversarial review `docs/research/rab_sep_promotion_20260716/04_front_clear_lift_design_20260716.md` v2) is bound by four structural obligations. (1) **Dual-NoOverlap topology**: the shared one-directional free-cell certificates (`free[c]=1 ⟹ no selected facility body occupies c`, lowered as 1×1 optional intervals) participate ONLY in the body∪free NoOverlap2D; they must never enter the ghost overlay's combined NoOverlap (which expands `_core_*` — free intervals therefore live in a separate `_front_clear_*` list and are forbidden in `_core_*`), because ghost-interior cells are genuinely free under the routing predicate (`ghost_pick` exclusion) and a leaked free-vs-ghost exclusion systematically over-cuts the true optimum under `max_lex(area, min_side)`; the `_dedup_subsumed_core_no_overlap` subset check must refuse to clear the body∪free constraint (both constraints stay live when the lift is ON). (2) **Exclusion-universe premise**: the free-certificate exclusion set equals the body-interval set (facilities + C1 poles, both RAB blockers), which equals exact `occupied_cells` only under the rectangular-footprint invariant — the offsets derivation fails closed on any non-rectangular pose, same-side duplicate fronts, port fronts inside their own body, or per-mode translation-invariance violations (each a verified premise of the counting-equivalence theorem: RAB filter-empty ⟺ some side's free-front count < that side's routing-visible demand). (3) **Demand SSOT**: per-side demands come exclusively from `src/models/port_binding.py::routing_visible_port_demands` fed with the master-carried certified `generic_io_requirements` snapshot. `routing_free_sink_commodities_from_generic_inputs()` remains the single shared SSOT helper but, under Batch-5 authority, it validates its input and always returns `frozenset()`; therefore every generic-input final producer output remains routing-visible. The coordinate master's `_group_port_demand` (which counts RFSC and generic slots) is forbidden as a demand source, and out-of-scope operations (generic-slot, unprofiled) get no lift constraint (weakening-only direction). (4) **Operational discipline**: `EXACT_MASTER_FRONT_CLEAR_LIFT` is certified-allowlisted with a strict value domain (unset//0/false/off = OFF, 1/true/on = ON, anything else fails closed at build — never silently OFF), stays default-OFF pending the staged validation ladder; clones must inherit the lift identity from the exported core binding and never re-read the ambient env; and the lift's acceptance metric is the raw lift-scope-bucketed `empty_binding_domain` event count (strictly zero when a master incumbent reaches the binding build; the accepted-cut counters are diagnostics only and must not substitute). Sentinel regressions live in `src/tests/test_front_clear_lift_master.py` (dual-topology membership, ghost-interior-free feasibility, blocked-front bite with OFF control, env domain, clone identity) and `src/tests/test_front_clear_lift_full_pool_golden.py` (full-pool bidirectional offsets/index golden differential); the lift does not alter the RAB-SEP runtime channel, which remains the independent enforcement belt for the same necessary condition.
- The routing-precheck cut-evidence carrier and integer counters must be well-formedness-checked, not only the status/safe-reject bits (F-BL-R10-01 / -02, conditional hardening extending F-BL-R9): r9 hardened the precheck status and safe-reject proof bit but left the actual placement-local cut evidence (`blocked_ports` per-port records) summary-trustable and consumed a `port_adherence.blocked_ports` count via `int(...)` truncation. A guard must fail closed to `UNKNOWN` before any placement-local `routing_front_blocked_nogood` when summary/`_analysis` `blocked_ports` are malformed or unequal, and the build-guard count must use a strict literal-non-negative-int check (reject bool/float/str/None). Canonical first-party `run_exact_routing_precheck` shallow-copies the same `_analysis` records into the summary and writes pure integer counters, so summary==`_analysis` and the count is always int — unreachable; false-deletion-direction drift hardening, not a certified soundness reset.
- The env-gated pose-bool exact-core overlay sentinel and the coordinate skip-power-coverage symmetry narrowing must be precise (F-GM-R14-PB-CORE-OVERLAY-01 / -COORD-SKIPPOWER-01, env-gated / conditional hardening continuing the F-GM-R11/R12/R13-PB pose-bool and coordinate geometry line): the pose-bool proto-overlay no-op sentinel completeness and the coordinate-master skip-power-coverage symmetry-breaking narrowing range. Reachable only under `EXACT_USE_POSE_BOOL_MASTER` or hand-built/non-canonical data; not a certified soundness reset. (The r14 patch fixes 2 of 3 narrowing call sites; the residual `exact_coordinate_master.py` symmetry-narrowing site is non-canonical and documented as an acceptable residual.)
- The delegated power witness write-back/injection side needs further proof-context tightening (CUT-R16-H1, env-gated forensic hardening extending CUT-R13/R14/R15-H1): the synthetic-pole injection back into the certified solution and the pre-existing-pole detection have a residual TOCTOU/disjointness gap between the injected pole and the selected empty rectangle. Gated behind `EXACT_POWER_PLACEMENT_SUBPROBLEM` (deny-unknown in certified, forensic-bypass only); not a certified soundness reset (GPT-labeled HIGH relabeled to forensic hardening — reachable only via forensic bypass / master-state corruption / future backend).
- Further raw/direct preprocess validation-vs-consumption asymmetry and float-epsilon residuals are hardened (H-PRE-R19-01 / -02, conditional hardening extending F-PRE-R18): additional raw-entry guard-inheritance completeness and the `normalize_artifact_number` 1e-9 near-integer snap on artifact-boundary numbers. Canonical-unreachable / artifact-boundary tolerance outside the certified hash closure; not a certified soundness reset.
- A further campaign resume/persistence torn-state and timestamp-ordering window must fail closed (F-CAM-R7-01, conditional availability hardening extending F-CAM-R6-01). Reachable only under a real crash/torn-write at a narrow window; availability hardening, not a reachable false-CERTIFIED soundness reset.
- The precheck-elimination strong-write path must fail closed on a malformed precheck shape at the additional write entry (F-PS-R8-01, conditional hardening extending F-PS-R6/R7-01): a Mapping-gate must reject a malformed precheck outcome before promotion to a strong record. Canonical prechecks are well-formed so unreachable; drift hardening, not a certified soundness reset.
- The port-binding model must fail closed (binding status `INVALID_INPUT`, consumed as non-tri-state UNKNOWN with no master cut and no routing entry) when a master-supplied placement instance is missing from or inconsistent with the canonical instance metadata, instead of silently erasing the mandatory facility's port obligation to an empty binding model (F-BIND-BS-01, blank-slate de-biased review hardening). On the canonical default-env certified path the solution keys are produced from the same `source_instances` that populate the binding instance map, so missing/inconsistent ids cannot arise; the leak is reachable only via hand-built input or a hash-gate-defeating corrupt artifact. Defense-in-depth fail-closed, NOT a certified soundness reset (GPT self-rated CRITICAL; independent adversarial verification reclassified to conditional/hardening — canonical-unreachable).
- The instance-level fallback conflict-cut encoder must be all-or-nothing: any unresolvable conflict instance id fails closed to UNKNOWN/cut_stall instead of being silently dropped, which would otherwise mint a strict-subset (over-strong) master nogood that deletes legal solutions (F-BL-BS-01, blank-slate de-biased review hardening). On the canonical default-env path every conflict id is same-source as the solution dict and therefore resolvable, so the silent-drop branch is unreachable; the patch hardens a contract the r7 ledger already asserted. Invariant hardening, NOT a certified soundness reset (GPT self-rated HIGH; independent adversarial verification reclassified to MEDIUM/hardening — canonical-unreachable, the probe required a monkeypatched unresolvable id).
- `preprocess_plan.utility_operations` must fail closed when an operation key shadows a canonical recipe's runtime port profile, extending the R6-F-01 additive-only plan boundary into the operation namespace (H-PRE-BS-01, blank-slate de-biased review hardening). The current frozen utility keys do not intersect the canonical recipe ids, so the shadow is unreachable on canonical data; only a malformed or future canonical source entering the hash closure could trigger it. Conditional source-boundary hardening, NOT a certified soundness reset (GPT self-rated HIGH-conditional; independent adversarial verification confirmed conditional).
- The boundary-storage-port feasibility screen's hard-infeasibility premise must use only facility `occupied_cells`, never port connector cells (F-GM-BS-R2-01, blank-slate de-biased review Round 2 — **reachable certified soundness reset**): `_boundary_storage_port_feasibility_screen_spec()` (`src/models/master_model.py`) previously set `blocking_cells = frozenset(occupied ∪ port_connector_cells)`, and when every ghost anchor screens infeasible the default `certified_exact` candidate precheck (`src/search/benders_loop.py` ~2305-2404) returns a hard `INFEASIBLE` with `precheck_reason="boundary_port_all_anchors_infeasible"`, skipping master/binding/routing with no downstream re-check. This is strictly stronger than the certified contract: the coordinate master ghost constraint and the terminal certified validator use occupied-only ghost occupancy, stored port front cells are ordinary routable belt cells (F-RT-R3-01, identity semantics post-2026-07-18) not master footprint, and the default routing domain does not exclude ghost cells (`_extract_occupied_cells` skips `ghost_pick`; the active F1-F7+F9 cut families (F8 retired) that treat `ghost_cells ∪ exterior_blocks` as blocked remain certified-unsafe/default-off; only F1/F5/F6/F7 have a controlled direct bridge), so belts may traverse the empty rectangle and a boundary port whose `occupied_cells` avoid the ghost but whose connector lands inside it is master-legal and routing-feasible. On canonical data the 136 `boundary_storage_port` poses place occupied cells on the grid edge (x=0 / y=0) with the connector one cell inward (x=1 / y=1), so any corner-region ghost touching x=1 / y=1 triggers the false prune in default env (anchor cap `EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS=64`, no `EXACT_*` knob) — verified by red→green regression `src/tests/test_boundary_port_precheck_soundness.py` (old code: `screen_pass_anchor_count=0` for ghost 39×69; patched: anchors survive). A false-`INFEASIBLE` on a master-legal, routing-feasible candidate under `max_lex(area, min_side)` silently drops true maximal rectangles → false-CERTIFIED of optimality. The fix sets `blocking_cells = frozenset(occupied_cells)`; connector-cell blocking remains valid only as a greedy warm-start heuristic (`_pose_greedy_blocking_cells`), never as a hard infeasibility proof premise. Unlike the Round 1 BS findings above (all canonical-unreachable hardening), this executes on canonical default-env geometry; independent CC verification (routing-trace + red→green + canonical pose-geometry confirmation + full-suite 3137 passed) upheld it as a real reachable certified soundness reset, resetting the blank-slate review streak.

- The parallel wave scheduler must seal worker process exit codes at end-of-wave, never reporting a wave `completed` when a worker died with a non-zero exit code after delivering its final RESULT (F-SCHED-BS-R3-01, blank-slate de-biased review Round 3 — **reachable certified soundness reset**): `ExactParallelWorkerPool.run_wave()` (`src/search/exact_parallel_scheduler.py`) checked worker `exitcode` only inside the `queue.Empty` wait branch; once `len(results_by_seq) == len(tasks)` the main loop exits and `completed` was computed from `failure_reason is None` alone, with no end-of-wave process-failure seal. A worker that queues its final `WorkerResult` and then dies with a non-zero exitcode (real operational events: OOM SIGKILL, OR-Tools native segfault) yields `completed=True, failure_reason=None`. The consumer (`src/search/outer_search.py` ~2305-2495) has no independent post-wave liveness check — it sets `effective_wave_completed = bool(wave_execution.completed) and wave_identity_failure is None` and only stops the campaign `UNKNOWN` (`mark_campaign_stopped("worker_process_failed", UNKNOWN)`) when not completed; the `worker_process_failed` result-preserving whitelist (`outer_search.py` ~162-173) is the codified contract that any non-zero worker exit makes the wave untrustworthy. With the seal missing, an untrustworthy wave silently drives proof-complete: if it exhausts the frontier the outer search advances to terminal CERTIFIED. This is default-env (no `EXACT_*` knob) on the documented production path (`main.py --parallel-processes`). The terminal validators do not backstop it: `_validate_terminal_solution_against_project` scans only the chosen layout's best empty rectangle (cannot reconstruct a falsely-pruned larger candidate's different arrangement), `terminal_certified_final_result_violation` skips `status != CERTIFIED` records (trusts recorded status), and `certified_frontier` re-runs the projection over the same persisted statuses (self-consistency, not independent re-verification) — every layer assumes the per-candidate strong statuses are trustworthy, which is exactly what a crashed worker's result breaks. The dangerous mechanism: an OOM-starved worker truncating its proof search can emit a false `INFEASIBLE` on a larger candidate, persisted as a sticky strong status (`exact_campaign.py` ~2115-2146, no downgrade), permanently pruning a true maximal rectangle → smaller rectangle certified as optimal → false-CERTIFIED of optimality under `max_lex(area, min_side)`. The fix adds an end-of-wave seal (`_failed_worker_processes`/`_worker_process_failed_reason` helpers; after tail-drain, `if failure_reason is None and _failed_worker_processes(self._processes): failure_reason = "worker_process_failed:..."`), preserving identity-valid results as progress while stopping the campaign UNKNOWN — red→green regression `src/tests/test_parallel_scheduler.py::test_parallel_worker_pool_reports_worker_crash_after_all_results_arrive` (old: completed=True fail-open; patched: completed=False with worker_process_failed). Like F-GM-BS-R2-01 this executes on canonical default-env; independent adversarial verification (3-way convergence: CC code-trace + opus patch-verifier red→green + dedicated opus reachability agent confirming no terminal backstop) upheld it as a real reachable certified soundness reset, resetting the blank-slate review streak (Round 3 not clean).
- The cut-family `CutScope.artifact_hashes` must snapshot its dict at construction, never aliasing a live `BState.artifact_hashes` (F-CUT-BS-R3-01, blank-slate de-biased review Round 3 — canonical-unreachable hardening): `CutScope` (`src/cuts/lifecycle.py`) is a frozen dataclass but did not copy the inner `artifact_hashes` dict; the inline F1 region-capacity generator and `src/cuts/oracles/region_capacity_oracle.py` passed `artifact_hashes=state.artifact_hashes` as a live alias (the other 8 oracles already copy defensively), so an in-place `BState.artifact_hashes` mutation (artifact rotation / checkpoint reload reusing BState) would silently rewrite the stored cut's proof scope, making the Step-6 attach scope check compare the same dict to itself and return ATTACH where it should QUARANTINE (proof-premise rewrite → fail-open ATTACH of a stale cut). The fix snapshots in `CutScope.__post_init__` via `object.__setattr__(self, "artifact_hashes", dict(self.artifact_hashes))`, centrally protecting all family callers and the `from_dict` deserialization path — red→green regression `src/tests/cuts/test_replay.py::test_cut_scope_artifact_hashes_snapshot_not_state_alias`. At the Round-3 review checkpoint this was canonical-unreachable because the cut-family subsystem had no production bridge. **Status addendum (2026-07-11, refreshed 2026-07-17, supersedes that reachability sentence):** `step_8_apply_to_master` now translates F1/F6/F7 via the typed single-entry chain (F5's apply/lowering was physically deleted in Stage B B5a; F5 is shadow-only) and `benders_loop._maybe_attach_framework_cuts()` imports the lifecycle behind `EXACT_CUT_FRAMEWORK_ATTACH`; certified runs still fail closed because that env remains in the unsafe map. The alias-snapshot obligation remains binding, but it is no longer accurate to say no production module imports `src/cuts/` or that Step 8 is wholly unimplemented.
- The end-of-wave worker-failure seal must also cover the mid-wave crash+respawn timing, never retaining a crashed generation's RESULT across `_respawn_all_workers()` (F-SCHED-BS-R4-01, blank-slate de-biased review Round 4 — **reachable certified soundness reset**): the F-SCHED-BS-R3-01 seal (3bc08b0) checks `_failed_worker_processes(self._processes)` only after the main loop exits, but the mid-wave `queue.Empty` branch (`src/search/exact_parallel_scheduler.py` ~498-544) drains an already-queued RESULT into `results_by_seq`, computes `pending`, and — when pending tasks remain under the respawn cap — calls `_respawn_all_workers()` which sets `self._processes=[]` then repopulates with a fresh healthy generation, structurally erasing the crashed process objects *before* the seal runs, so the seal is blind to the crash. A worker that emits task N's `INFEASIBLE` RESULT then dies non-zero on task N+1 (OOM SIGKILL / OR-Tools native segfault, real default-env events; `main.py --parallel-processes>1` is the documented production path, no `EXACT_*` knob) yields `completed=True, failure_reason=None` with the crashed generation's INFEASIBLE merged with the respawn generation's results. The consumer (`src/search/outer_search.py` ~2305-2495) is fail-open: `_parallel_wave_result_identity_failure` checks only identity (dispatch_seq/attempt/candidate/key), never liveness, so the identity-valid crash result passes and `effective_wave_completed` stays True (the `worker_process_failed` UNKNOWN-stop branch never fires); `_total_crash_respawns` is incremented but never surfaced in `ParallelWaveExecution` nor read by the consumer — there is no independent crash telemetry. The retained INFEASIBLE is persisted as a sticky strong status (`exact_campaign.py` ~2115-2146, no downgrade), permanently pruning a true maximal rectangle → smaller rectangle certified as optimal under `max_lex(area, min_side)` → false-CERTIFIED of optimality, with the same terminal validators (which trust recorded status) failing to backstop — identical chain to F-SCHED-BS-R3-01. The R3 regression stubbed `_respawn_all_workers` to a no-op, so the respawn path was never exercised and the R3 fix was structurally incomplete for the mid-wave timing. The fix validates queued RESULTs into a scratch `validated_results_by_seq` during crash-drain: if it covers all tasks the result is kept and the still-present crashed process is sealed to `worker_process_failed` (completed=false); if tasks remain pending it clears all tainted prefix results and respawns rerunning **all** tasks (not just pending); at the respawn cap it sets the discard latch and clears results — no crashed generation's result ever crosses the respawn boundary. red→green regression `src/tests/test_parallel_scheduler.py::test_parallel_worker_pool_reruns_all_tasks_after_mid_wave_crash_respawn` + `::test_parallel_worker_pool_crash_respawn_limit_discards_tainted_prefix_results`. Like F-GM-BS-R2-01 / F-SCHED-BS-R3-01 this executes on canonical default-env; independent adversarial verification (3-way opus convergence including a refuter explicitly tasked to argue hardening — all returned REACHABLE_RESET high-confidence; plus CC code-trace + a RED probe reproducing `completed=True` on HEAD + a consumer fail-open trace; full-suite 3141 passed) upheld it as a real reachable certified soundness reset, resetting the blank-slate review streak (Round 4 not clean).
- The routing subproblem's public `domain_analysis` ingestion must fail closed (routing `TIMEOUT` / CP-SAT `UNKNOWN`) on any status outside the verified set {`feasible`, `front_blocked`, `relaxed_disconnected`}, never compiling an unverified/non-proof status into a `0 == 1` contradiction that `solve()` reports as `INFEASIBLE` (F-RT-BS-R5-01, blank-slate de-biased review Round 5 — canonical-unreachable hardening): `RoutingSubproblem.build()` (`src/models/routing_subproblem.py` ~821) previously did `if str(analysis.get("status","feasible")) != "feasible": self.model.Add(0 == 1)`, minting a proof-bearing `INFEASIBLE` from a non-proof status (e.g. a hand-injected `"TIMEOUT"`/`"ERROR"`), while a missing status was silently treated as `"feasible"`. Only `front_blocked`/`relaxed_disconnected` are proof-bearing reject statuses produced by `analyze_exact_routing_domain()`. This is **canonical-unreachable** on the default-env certified path: the sole canonical producer `analyze_exact_routing_domain()` (`routing_subproblem.py` 385-630) emits exactly three statuses (`front_blocked`/`relaxed_disconnected`/`feasible`) and never a non-tri-state value; `run_exact_routing_precheck` fills both `precheck["status"]` and `precheck["_analysis"]` from that same analysis object (same string, no split); the benders caller (`src/search/benders_loop.py`) gates with (i) the precheck allowlist (~5599: status ∉ the verified set → `RUN_STATUS_UNKNOWN`), (ii) a precheck/`_analysis` status-consistency guard (~5619), and (iii) a post-build guard (~6317: `build_stats.domain_analysis.status != "feasible"` → `RUN_STATUS_UNKNOWN`) firing before any routing `INFEASIBLE` is consumed (~6414+); `_bind_domain_analysis` records the real input status into `build_stats` (no asymmetric overwrite-to-`feasible`), and the synthesized precheck-error dict (~5544 `"ERROR"`) carries no `_analysis` key so `routing_domain_analysis` is `None` and the build recomputes via the 3-status producer. The only override of `precheck_status` to `feasible` needs two `EXACT_*` env knobs (non-default) and still leaves `_analysis` non-`feasible` for guard (iii). The GPT repro is a hand-built `RoutingSubproblem(..., domain_analysis={"status":"TIMEOUT"})` direct construction — a PROJECT_LOCK hand-built input. The fix adds the closed verified-status set, routes non-verified/missing statuses to a `domain_status_contract_violation` early return (no `0 == 1`) with `solve()` returning `TIMEOUT` / CP-SAT `UNKNOWN`, and records the real status in `build_stats` — red→green regression `src/tests/test_routing.py::test_unverified_domain_analysis_status_fails_closed_unknown` (old: `"TIMEOUT"` domain → `INFEASIBLE`; patched: → `TIMEOUT` / `ROUTING_DOMAIN_STATUS_CONTRACT_VIOLATION`), full-suite 3142 passed. Defense-in-depth fail-closed of the routing subproblem's own public contract, NOT a certified soundness reset (GPT self-rated HIGH; independent 3-lens adversarial reachability verification — consumer-trace + guard-completeness + a refuter explicitly tasked to argue REACHABLE and to default to reachable if uncertain — all three returned UNREACHABLE_HARDENING high-confidence; canonical-unreachable, does not reset the blank-slate review streak).
- The success-path worker rotation must seal a worker shutdown-time non-zero exit before erasing the process objects, never letting a worker that dies during the clean rotation (after the end-of-wave seal's non-blocking `exitcode` poll already read `None`) be erased into a `completed=True` wave (F-SCHED-BS-R5-01, blank-slate de-biased review Round 5 — **reachable certified soundness reset**): the F-SCHED-BS-R3-01 end-of-wave seal (`src/search/exact_parallel_scheduler.py` ~619-627) reads `process.exitcode` via a non-blocking poll, which returns `None` for a worker still mid-death (OS not yet reaped). On the success path (`failure_reason is None`) the wave then calls `_respawn_all_workers()` (~632) whose `process.join(timeout)` **blocks and reaps**, making the crashed worker's `exitcode` non-zero — but the original `_respawn_all_workers()` set `self._processes=[]` and started a fresh generation without checking that reaped exit code, so the late failure was erased and the wave returned `ParallelWaveExecution(completed=True, failure_reason=None, results=(...))`. This is a TOCTOU between the seal's poll and the respawn's join, default-env (`main.py --parallel-processes`, no `EXACT_*` knob) on real OOM SIGKILL / OR-Tools native segfault when a worker crashes right after queuing its final RESULT — the third crash timing after R3 (end-of-wave) and R4 (mid-wave respawn). A late-crashing generation's false `INFEASIBLE` then drives the same chain as R3/R4 (sticky strong status pruning a true maximal rectangle → false-CERTIFIED of optimality). The fix adds `_respawn_all_workers(fail_on_worker_shutdown_failure=True)` on the success path: snapshot `old_processes`, run sentinel/join/terminate (which reaps), then `if fail_on_worker_shutdown_failure and _failed_worker_processes(old_processes): restore self._processes and return _worker_process_failed_reason(...)` BEFORE rebuilding queues / clearing `self._processes`; `run_wave()` converts a returned shutdown failure into `completed=False` + `terminate()`. The mid-wave respawn path keeps the default `fail_on_worker_shutdown_failure=False` (it already clears the tainted prefix and reruns all tasks). red→green regression `src/tests/test_parallel_scheduler.py::test_parallel_worker_pool_reports_worker_crash_during_successful_wave_shutdown` (old: `completed=True`; patched: `completed=False` / `worker_process_failed:...`), full-suite 3143 passed. Like F-SCHED-BS-R3-01/R4-01 this executes on canonical default-env; GPT-surfaced HIGH, independently red→green confirmed + adjudicated reachable (the seal's non-blocking poll cannot guarantee a mid-death worker is reaped before the blocking join), upheld as a real reachable certified soundness reset (Round 5 not clean).
- A not-effective-completed wave's preserved `INFEASIBLE` must NOT be persisted by the consumer as a sticky strong candidate record, closing the resume residual that F-SCHED-BS-R3-01/R4-01 left open by *preserving* crashed-wave results (F-SCHED-BS-R5-02, blank-slate de-biased review Round 5 — **reachable certified soundness reset**): R3/R4 correctly seal `completed=False` on a worker crash but deliberately preserve the wave's identity-valid results (`_parallel_wave_failure_discards_results` returns False for `worker_process_failed`/`worker_crash_respawn_limit`, `src/search/outer_search.py` ~162-173). The consumer then persists the preserved `INFEASIBLE` via `mark_candidate_result(ghost_w,ghost_h,INFEASIBLE)` (~2390-2417) and `exact_campaign.save()` BEFORE the `if not effective_wave_completed: mark_campaign_stopped("worker_process_failed", UNKNOWN)` stop (~2484-2495). The envelope carries no worker pid (`exact_parallel_scheduler` result comment), so the consumer cannot attribute which RESULT came from the dead worker, and `_total_crash_respawns` is never read on the consumer side. The persisted `INFEASIBLE` is sticky strong + monotone (`exact_campaign.py` ~2062-2070 `mark_candidate_started` early-returns on strong status → never re-solved; ~2115-2140 downgrade-blocked); `mark_campaign_stopped` does not un-persist it (~2223-2238); `load_or_create` resume clears the stop only for `campaign_time_budget_exhausted`, never for `worker_process_failed` (~1898-1905), and `_validate_resume_state` accepts it; the outer search has no `final_status`/`last_stop_reason` resume early-return, so on the canonical watchdog resume (`campaign_watchdog` auto `--resume-campaign`) the search re-enters, the sticky false `INFEASIBLE` poisons `compute_terminal_frontier_projection` (pruning the true maximal rectangle AND its dominated domain), and with default `strict` declare_mode the campaign declares a smaller rectangle terminal full-frontier `CERTIFIED` → false-CERTIFIED of optimality under `max_lex(area, min_side)`. No backstop: the terminal validators are self-consistency over the poisoned records (`certified_frontier` re-runs the projection over the same records and never re-solves an `INFEASIBLE`) and `_validate_terminal_solution_against_project` only verifies the chosen smaller-rectangle witness, never that a larger empty rectangle is impossible. This is default-env (`main.py --parallel-processes` + watchdog resume, no `EXACT_*` knob) and the *same defect family* as R3/R4 — their tainted `INFEASIBLE` is also put-before-crash and also preserved+persisted; the only difference is that R3/R4 sealed the `completed=True` branch while this is the `completed=False` preserve→persist→resume residual of the identical doctrine ("a crashed wave's `INFEASIBLE` must not become proof"). The fix gates the consumer's sticky `INFEASIBLE` write on `effective_wave_completed` (`outer_search.py`: `persist_strong_results = bool(effective_wave_completed)`; a not-completed wave's `INFEASIBLE` is skipped so the candidate stays `RUNNING` and re-solves on resume; `CERTIFIED` — witness re-validated at terminal export, non-pruning — and `UNKNOWN`/`UNPROVEN` — non-strong — persist normally; the result is still recorded into wave telemetry). red→green regression `src/tests/test_parallel_scheduler.py::test_worker_failure_does_not_persist_crashed_wave_infeasible_as_sticky` (renamed from the prior `..._preserves_completed_progress...` test that locked the buggy behavior; old asserted `INFEASIBLE in statuses`, now asserts all candidates `RUNNING` with telemetry preserved), full-suite 3143 passed. CC independent audit surfaced it (verification-ladder line 2, not a reviewer finding); 2-way adversarial debate convergence (prosecution + a defense agent explicitly tasked to argue HARDENING — both returned REACHABLE_RESET high-confidence; the defense conceded after exhaustively finding no backstop and that "put-before-crash ⇒ valid" is self-report-not-evidence from the pid-less consumer and would retroactively unseat R3/R4); reachable certified soundness reset (Round 5 not clean).

### 3A. B Design v2 invariant additions (2026-05-22)

Phase 0 23 round Gemini cross-check 后 frozen invariants. **Phase 1 实施
不可破**:

- **Exactness FP = 0**: 任何 cut 都不能误剪合法解 (False Positive = 0).
  False Negative (cut 漏发, 性能退化) 可接受, FP 致命. Gemini round 19 原则
  "宁可 FN 不可 FP" 写进 lock.
- **Group/orbit-count symmetry**: state 必走 group-orbit 而非 per-instance,
  消 10^134 label symmetry. AnonymousSlotRef multiset 包含语义跨 candidate
  enumeration order 必 sound (slot_index 仅 debug/serialization 用, 不参与
  soundness 推理).
- **Cut family ↔ mode 一致性**: `_FAMILY_MODE_MAP` (cut_lifecycle_v2 v3 §3)
  契约 — 当前在册 literal-based family (3/5/7) 走 multiset evaluate，geometric family
  (1/2/4/6/9) 走 evaluate_geometric；F8 已于 2026-07-08 因游戏规则前提为假整族退役。
  `__post_init__` enforce literals XOR geometric_payload 互斥。
- **Scope-aware HOLD vs Quarantine**: 6 步 verify (cut_lifecycle v3.2.2 §4)
  失败的处理必须严格区分 — HOLD 不删 cut 等下次 candidate matching;
  QUARANTINE 不删 cut 留 audit trail 不进 active resolve; 两者不能混. ghost-
  agnostic cut (`GHOST_AGNOSTIC` sentinel) 跳 ghost_rect_id 校验**但**仍走
  exterior_blocks_hash 校验 (v3.2.2 dispatch).
- **F9 paradigm 降级 lock**: density_envelope 只 trigger
  `area_capacity_overflow` 凭证. binding/routing/PCR-CUT INFEASIBLE 必 fallback
  Family 5 pattern_nogood (Gemini round 19 verdict). 不允许 silent generalize
  topological deadlock → density cut.
- **F9 area-based counting lock** (Gemini round 24 B2 — round 20 finding 焊死):
  F9 evaluator + validator 必走 area-based `sum(|pose_cells ∩ W|)` 计数,
  **不可退化** instance-based counting (v1.0 over-count / v1.2 origin-in-W
  / v1.3 all-in-W 全 unsound — v1.0 FP, v1.2 FP, v1.3 FN). v1.4+ 全
  area paradigm 是唯一 sound 路径, 任何 refactor 退回 instance-counting 算
  Forbidden Change.
- **(2026-06-04 v28 GPT pro 外审) Cut-family validator 数值/字面量 source-of-truth
  gate**: 任何 accepted cut 里 validator **无法独立便宜重算**的 scalar/literal
  payload, 必须对 canonical_rules / source-of-truth fail-closed 交叉核对 (镜像 v28
  F7 `pole_radius` 修复)。逐 family 焊死:
  - **F5 pattern_nogood slot 完整性**: `forbidden_pose_pattern` 每个 literal 必须绑
    一个真实、唯一、在界内的匿名 slot — `slot_index < group.demand` + `(group, slot)`
    唯一 + per-group literal 数 ≤ demand。Why: generic evaluator
    (`evaluate_literal_multiset`) 刻意丢 slot 身份按 `(group, pose)` multiset 评估,
    一个 slot-collision 核 `[(g,0,pA),(g,0,pB)]` 虽被 oracle 正确判 INFEASIBLE (单
    slot 不能两 pose), lift 成 multiset cut 后却比 oracle 实际证明的更强 → 错剪合法
    布局 slot0→pA/slot1→pB (FP)。
  - **F6 shape_packing_hall region_demand 下界**: `region_demand ≤ max(0, group_demand
    − 对侧 baseline 容量)`, 且仅接受 `left_or_bottom_boundary` 模板。Why: 单边 Hall
    cut 只对 "被 pigeonhole 强制到该侧" 的数量 sound; 容量上界 ≠ 强制下界, 伪
    `region_demand` 会错剪合法 split (全放另一边)。
  - **F7 footprint SoT（active）/ F8 retirement（historical）**: F7 的 power_pole footprint 2×2
    必须对 `canonical_rules.facility_templates.power_pole.dimensions` fail-closed 核对（与既有
    `pole_radius` gate 同款）。F8 的 protocol_core 9×9 / pole-jump 校验只保留为退役前审计史料；
    `CutFamily`、mode map、oracle/validator/assumption 路径不得重新登记 F8，除非 owner 先重开游戏规则前提并
    同步 lock/spec/src/test。
  共享实现集中在 `src/cuts/helpers/canonical_sot.py` (canonical lookup + fail-closed
  dims 校验), F7 委托它；`src/tests/cuts/test_canonical_sot_coverage.py`
  meta-test 强制 (登记契约 + 私有 lookup 不复活)。**新增信任 canonical 标量的 family 必须
  走 canonical_sot + 进登记表 + 加 behavioral red-test** (meta-test 抓回归, 但发现"全新未守
  标量"仍靠人/审查 —— 诚实边界)。**已知 grandfathered**: F6 (shape_packing_hall) 有一份
  family-local canonical-dims SoT 核对 (pose_length vs template dims, 经 state.facility_templates
  alias, sound fail-closed) 未走 canonical_sot、未进登记表 —— 它**非 fail-open 洞** (v28 合并只
  针对 fail-open), 是预存未 consolidate 项; meta-test 的 dimensions 私有扫描刻意不覆盖它。
  **(2026-06-04 historical fresh-pass; 2026-07-08 retirement addendum)**:
  `verify_power_pole_jump_radius` 与 `verify_protocol_core_position` 属 F8 退役前审计路径；当前源码已删除这些
  F8 assumption verifier。不得把“待 consolidate”继续当活待办；若未来 owner 重开 F8，须重新定义并审计
  assumption/canonical-SoT 边界。`src/cuts/oracles/power_cover_oracle.py` 是 F7 generator 侧读 canonical
  （产 cert 非验，不在 validator-side scan 范围）。
  **澄清: F1 region_capacity 的 `cells_per_pose` 不是未守 SoT** —— 是 Gemini round-14 #5 **刻意
  信任 cert** (防 canonical pose-shape 微调时全 cut quarantine), 同 F9 tight-K 的 deferral 性质,
  **勿 consolidate** (改了会反转刻意决定)。
- **(2026-06-04 v28) F9 tight-K quarantine (supersedes Gemini round-4 oracle-trust
  deferral)**: density_envelope validator 对 `max_allowed_area = K < safe_ub` fail-
  closed 拒 (Phase 1.2 cert 不携带 replayable tight-bound proof)。净效果: F9 只剩
  K==safe_ub 的平凡 cut (`_validate_witness_overflow` 的 strict `>` 在 K==safe_ub
  不可满足 → F9 实质停用)。**这反转 Gemini round 4 "信任 oracle K、tight-K 重验
  defer P1.5+" 的判断**: replay 实证 validator 是信任边界且不重跑 oracle
  (`replay.py` 对 deserialized cert re-validate), 信任无法重算的 cert 标量 = replay
  时真 FP 暴露; 与上方 validator SoT gate 原则一致。恢复 tight F9 须在 Phase 1.5+
  给 cert 加 area-capacity proof-carrying 字段 + replay 校验 (与 F5 v1.0 信任
  INFEASIBLE 同类升级)。**解封时同步恢复**
  `test_generator_witness_canonical_order_independent_cert_hash` 的 cert_hash 不变量
  覆盖 (quarantine 期间该测试改为 assert 空)。与 "F9 area-based counting lock" 正交
  (不改计数 paradigm, 只加 K fail-closed gate)。
- **RAM 测量必走 psutil RSS** (Gemini round 25 B2 — Phase 1 OOM 防虚假 PASS):
  168h campaign cut store RAM 监测 (`exit_criteria` #6 + ramp report
  `cut_store_peak_mb_per_worker`) **必须** 用
  `psutil.Process(pid).memory_info().rss` 读 OS 级真物理内存. **禁** 用
  逻辑大小计算 (`sys.getsizeof(cut)` / JSON string len 累加 / `dict` len ×
  estimate). Why: Python 对象头 + dict/tuple/dataclass 小对象内存碎片化导致
  逻辑 3 GB → RSS 8 GB. 若 #6 PASS based on 逻辑大小但 RSS 已超 5 GB, 168h
  campaign 仍触发 OS OOM kill. Phase 1 ramp report 必 emit
  `rss_peak_mb_per_worker` field, exit_criteria 优先验该字段.
- **代数 vs 几何分工**: 全局代数约束 (e.g. power supply cap, total worker
  count) 必走 Master CP-SAT 线性约束, 不进 cut framework (Gemini round 22
  F16 verdict — "代数归 Master, 几何归 Cut").

### 3B. W0 D6 research-only artifact protocol boundary

- This boundary applies only to the isolated W0 D6 research package under
  `docs/research/w0_power_cycle_domino_d6_20260728/`. It does not add that package,
  any D6 receipt, or any replay output to §2 Certified Source of Truth, the
  `certified_exact` source TCB, a production publisher, a frozen/sealed input, or
  checkpoint authority.
- The accepted complete protocol cohorts are closed:

  | cohort | antecedent | run-config payload | receipt payload | replay receipt |
  |---|---|---|---|---|
  | closed-root v2 | `w0_d6_antecedent_v1` | `w0_d6_run_config_v2` | `w0_d6_receipt_payload_v2` | `w0_d6_replay_receipt_v2` |
  | D6/D9 class-transfer v3 | `w0_d6_antecedent_v2` | `w0_d6_run_config_v3` | `w0_d6_receipt_payload_v3` | `w0_d6_replay_receipt_v3` |

  The common developer/research envelopes (`research_run_config_v1`,
  `research_run_receipt_v1`, `artifact_identity_graph_v1`,
  `research_artifact_root_manifest_v1`, and
  `isolated_python_process_contract_v1`) remain unchanged and opaque to W0
  mathematics. The W0 gate result, result wrapper, local configuration, and
  minimal certificate remain at their existing v1 schemas unless their own
  field set or meaning changes.
- A producer or replayer must select exactly one complete row. Any cross-row,
  partially upgraded, unknown, or future combination fails before artifact
  status or a D6 conclusion is interpreted with
  `ARTIFACT_PROTOCOL_COHORT_MISMATCH`. There is no coercion, relabeling,
  auto-migration, or in-place repair of a historical run root. A real
  `w0_d6_receipt_payload_v1` remains the narrower historical case and fails
  before artifact/status replay with `ROOT_CLOSURE_CONTRACT_MISSING`.
- The v3 protocol pins the exact SHA-256 of this authorized lock successor as a
  W0 protocol-identity scalar across its antecedent, run-config payload,
  receipt payload, and replay receipt. The runner must verify the actual stable
  `PROJECT_LOCK.md` bytes before creating an exclusive run root and revalidate
  them before writing a terminal receipt. The independent replayer verifies the
  bound scalar and its own pinned expected value; because the lock is not a
  run-root artifact, replay must not claim to have rehashed the live repository
  lock. A mismatch is a run/replay contract failure with no D6 verdict, not
  `INFEASIBLE`.
- `FEASIBLE` remains evidence only for the byte-bound local D6 antecedent;
  `INFEASIBLE` closes only the identical local antecedent and complete protocol
  cohort; `UNKNOWN`, interruption, intake failure, cohort failure, or replay
  failure has no rejecting force. No row can mint a whole-layout witness, lower
  ledger entry, cut, rejection, upper- or lower-bound change, production
  authority, or certified authority. In particular, `U` and `L` remain
  unchanged by this research protocol.

### 3C. AB16 Gate-B and formal-campaign research-only authority boundary

- This boundary applies only to the prospective non-certified AB16 campaign
  under `docs/research/noncert_cuts_ab16_20260724/`. It does not promote any
  AB16 source, package, Gate-1/Gate-A/Gate-B record, campaign receipt, arm
  result, replay, or closeout into §2 Certified Source of Truth, the
  `certified_exact` TCB, production attach authority, family-global cut
  soundness, a proof sidecar, B6/Stage-B promotion, a witness, or a bound.
- Formal execution is valid only from the registered independent worktree
  `/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723`,
  after its tracked tree is safely advanced with `git merge --ff-only main`
  to the final clean committed HEAD. Historical untracked `.artifacts` roots
  are immutable. Any fast-forward failure, tracked dirt, target-path
  collision, or source/input/tool-byte mismatch fails closed; reset, force
  checkout, overwrite, reuse, repair, or splicing of historical roots is
  forbidden. The main checkout is a control plane and cannot run this
  authority chain.
- The table below is the version-sensitive discriminator matrix for the one
  legal AB16 campaign cohort. Every listed discriminator is mandatory and the
  rows form one ordered cohort. Schema names cannot be independently selected, relabeled, or mixed.
  Package-internal transport, observer, child-audit, and
  terminal helper records that carry no independent version choice remain
  governed by the SHA-pinned package/source set and their closed validators;
  this table does not purport to enumerate those auxiliary schemas:

  | boundary | exact accepted schemas |
  |---|---|
  | stage resource admission | `noncert-cuts-ab16-stage-resource-admission-v1` |
  | Gate-A/Gate-B qualification | `noncert-cuts-ab16-bootstrap-gate-a-receipt-v2`; `noncert-cuts-ab16-bootstrap-offline-candidate-v2`; `noncert-cuts-ab16-gate-a-full-preflight-receipt-v6`; `noncert-cuts-ab16-gate-a-preflight-publication-commit-v1`; `noncert-cuts-ab16-gate-b-qualification-v2`; `noncert-cuts-ab16-gate-b-resource-gate-v2`; `noncert-cuts-ab16-gate-b-owner-request-v1`; `noncert-cuts-ab16-gate-b-owner-response-v1`; `noncert-cuts-ab16-gate-b-owner-release-v1`; `noncert-cuts-ab16-gate-b-epoch-observation-v4`; `noncert-cuts-ab16-bootstrap-gate-b-approval-v5`; `noncert-cuts-ab16-gate-b-bootstrap-handoff-request-v1`; `noncert-cuts-ab16-gate-b-bootstrap-handoff-response-v1` |
  | Gate-A terminal-reference history | `noncert-cuts-ab16-terminal-reference-history-freeze-v1`; `noncert-cuts-ab16-terminal-reference-history-replay-v2` |
  | bootstrap/package | `noncert-cuts-ab16-bootstrap-manager-capture-v2`; `noncert-cuts-ab16-campaign-bootstrap-result-v4`; `noncert-cuts-ab16-repository-snapshot-v1`; `noncert-cuts-ab16-repository-snapshot-materialization-v1`; `noncert-cuts-ab16-external-platform-assumptions-v2`; `noncert-cuts-ab16-path-preregistration-v4` |
  | formal launch | `noncert-cuts-ab16-formal-launch-context-v3`; `noncert-cuts-ab16-formal-launch-owner-request-v1`; `noncert-cuts-ab16-formal-launch-owner-response-v1`; `noncert-cuts-ab16-formal-launch-admission-v2`; `noncert-cuts-ab16-outer-guardian-ready-v1`; `noncert-cuts-ab16-formal-attempt-consumption-v1`; `noncert-cuts-ab16-formal-launch-selection-v1`; `noncert-cuts-ab16-formal-outer-prelaunch-v2`; `noncert-cuts-ab16-formal-outer-start-v2` |
  | AB16 campaign/arms | `noncert-cuts-gate1-v4-continuation-authorization-v1`; `noncert-cuts-ab16-baseline-admission-v1`; `noncert-cuts-ab16-common-prestate-v1`; `noncert-cuts-ab16-organic-manifest-v2`; `noncert-cuts-ab16-suite-selection-v2`; `noncert-cuts-ab16-arm-binding-v2`; `noncert-cuts-ab16-organic-pre-run-authority-v2`; `noncert-cuts-ab16-organic-arm-selection-v1`; `noncert-cuts-ab16-organic-arm-consumption-v2`; `noncert-cuts-ab16-formal-arm-prelaunch-v2`; `noncert-cuts-ab16-formal-controller-result-v2`; `noncert-cuts-ab16-immediate-stop-v1` |
  | successful formal closeout | `noncert-cuts-ab16-formal-pre-release-success-v2`; `noncert-cuts-ab16-outer-guardian-lock-close-v1`; `noncert-cuts-ab16-formal-guardian-absence-v1`; `noncert-cuts-ab16-formal-dual-lock-release-v2` |
  | incomplete formal closeout | `noncert-cuts-ab16-formal-consumed-incomplete-v2`; `noncert-cuts-ab16-formal-pre-release-failure-v3`; `noncert-cuts-ab16-formal-detached-incomplete-v3`; `noncert-cuts-ab16-formal-failure-terminal-release-v3` |
  | containment support | `noncert-cuts-ab16-formal-markerless-incomplete-v1`; `noncert-cuts-ab16-formal-reference-lifecycle-v1`; `noncert-cuts-ab16-formal-containment-hold-v1`; `noncert-cuts-ab16-containment-guardian-absence-v1`; `noncert-cuts-ab16-formal-containment-cleared-after-hold-v1`; `noncert-cuts-ab16-formal-lock-release-v1` |

  Any omission of a listed discriminator, unknown discriminator version,
  legacy substitution, or cross-row mismatch fails before launch or result
  interpretation. In particular, Gate-B
  full-preflight receipt v5, Gate-B qualification v1, Gate-B approval v4
  and below, Gate-B epoch v3 and below, Gate-B resource gate v1,
  campaign-bootstrap result v3, formal context v1, formal outer-prelaunch v1,
  formal outer-start v1, formal arm-prelaunch v1, formal controller-result v1,
  detached-success v1,
  dual-lock-release v1, consumed-incomplete v1, detached-incomplete v1/v2,
  failure-release v1/v2, and incomplete closeouts lacking a distinct
  pre-release/terminal-release join cannot be coerced into this cohort.
  Historical roots remain replayable only by their own pinned bytes and never
  become ancestors of the fresh campaign merely because a schema label
  matches.
- The terminal-reference history freeze remains the immutable singly linked
  regular file
  `/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723/.artifacts/noncert_cuts_ab16_20260724/gate-a-terminal-reference-history-freeze-a001/manifest.json`
  at mode `0400`, size `15584`, and SHA-256
  `f1a2edd604f06cb958258ea5bfcb3cc8a7ad154cbce184cd73e6a9b15302f619`.
  Its historical execution HEAD remains
  `398f8725c770f3c36408adebe9448a890ed886fe`; neither the file nor that
  field may be rewritten. Its closed member set is exactly `67` entries:
  `53` historical artifact members under its two declared frozen roots and
  `14` manifest-listed v1 source members.
- The `53` historical artifact members continue to be replayed byte-for-byte
  from the registered worktree root. The `14` source members are replayed
  from archival Git blobs at the fixed source-materialization commit
  `c0a4aa717ccb3f1dbc7cd26a581934c47b7a14eb`, whose tree is
  `1bae4f350bfdb1d7b51058cad0849c27af71b4c9` and whose sole parent is the
  manifest execution HEAD `398f8725c770f3c36408adebe9448a890ed886fe`.
  That archival commit must be an ancestor of the fresh committed worktree
  HEAD. It records the source bytes; it is not reinterpreted as the historical
  execution HEAD. Member paths, regular-blob modes, sizes and SHA-256 values
  must match the immutable manifest exactly. The manifest's
  `v1_source_glob` is not re-expanded against either the live tree or the
  archival tree, and no additional matching source path becomes a member.
- The fresh producer and independent verifier must each execute the
  planned-source `system.git` bytes through a same-FD execution descriptor,
  reject replacement or alternate-object indirection, and independently
  recheck the commit, tree, exact path, blob mode and blob bytes. Fresh
  receipts use only
  `noncert-cuts-ab16-terminal-reference-history-replay-v2`; the earlier
  `noncert-cuts-ab16-terminal-reference-history-replay-v1` remains valid only
  inside immutable historical roots under those roots' own SHA-pinned
  verifier bytes and is not accepted by the fresh cohort. Missing objects,
  path/classification drift, live artifact drift, source-blob drift, Git
  identity drift, HEAD drift or producer/verifier disagreement fails before
  Gate-B qualification. This archival byte bridge grants no new experiment,
  cut, witness, bound, production or certified authority.
- `guardian_control_socket_path` remains exactly the canonical absolute
  campaign child `formal-ab16/guardian-control.sock`. Records, handoff joins,
  and socket identities store only that absolute path plus its exact
  device/inode/mode/uid; a `/proc/self/fd/<retained-parent-fd>/...` spelling
  is never serialized and grants no authority. Because the registered
  worktree path exceeds Linux pathname `AF_UNIX` capacity, the package-pinned
  listener and connector may pass only that short descriptor alias to the
  kernel after opening every absolute parent component with
  `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`. The listener must pin the created leaf
  with `O_PATH`, join device/inode before and after mode `0600` installation,
  and retain the parent FD through cleanup. Linux pathname unlink cannot be
  atomically conditioned on the verified inode, so the authority chain never
  calls pathname unlink. Instead, path preregistration v4 and formal context
  v3/admission v2 bind the sole fixed terminal sibling
  `formal-ab16/guardian-control.sock.retired`; cleanup atomically moves the
  current canonical occupant there with `renameat2(RENAME_NOREPLACE)`, never
  overwrites the terminal member, fsyncs the retained parent, and verifies the
  captured device/inode/type/mode/uid. The expected closed socket remains as
  that inert terminal member. If the captured node is not the verified
  socket, cleanup attempts only a no-overwrite restoration; whether restoration
  succeeds or not, it preserves every unknown node, fails closed, and closes
  the retained parent FD exactly once. Parent drift, leaf drift, retirement
  collision, syscall unavailability, verification uncertainty, or durability
  uncertainty cannot report successful cleanup. Fresh cleanup success retains
  every no-follow descriptor in the canonical absolute directory chain plus an
  `O_PATH` descriptor for the exact retired inode, arms Linux mutation watches
  for the chain and inode, and descriptor-relatively replays the complete chain
  after the watches are armed. Only the subsequent nonblocking watch read's
  kernel `EAGAIN`, after exact parent/retired/canonical observations and with no
  queued mutation, is the cleanup-success linearization point; any queued
  event, watch/read uncertainty, chain/leaf drift, or descriptor cleanup error
  fails closed. A mutation after that kernel linearization is a later operation
  and does not rewrite the already-linearized temporal result; this grants no
  persistence claim beyond that point. The subsequent lock handoff still joins
  the canonical socket identity with `SO_PEERCRED` PID/starttime.
  Historical roots remain bound to their own pinned schemas and source bytes;
  this successor cannot retrofit, replay, or authorize them.
- Fresh AB16 resource admission uses the single
  `noncert-cuts-ab16-resource-profile-set-v1` profile set. It does not reuse one
  global memory/swap/disk threshold across unrelated stages. Every dimension
  closes the exact arithmetic
  `minimum_available = predicted_peak + safety_margin + host_reserve`; every
  receipt records the stage/profile identity and canonical `profile_sha256`,
  evidence basis, prediction method, all four dimension fields, runtime safety
  limits, live memory/swap/disk observations, exact retained-lock identities,
  same-UID conflict observation, research-only scope, all three launch
  authorizations false, and exact `PASS` status. Missing, malformed,
  arithmetically inconsistent, or untrusted basis/measurement/lock data raises
  a stable fail-closed error and cannot produce an authorizing PASS receipt.

  | stage profile | predicted peak | safety margin | host reserve | resulting minimum available |
  |---|---|---|---|---|
  | `FULL_PREFLIGHT` | memory `16 GiB`; swap `0 GiB`; disk `6 GiB` | memory `4 GiB`; swap `8 GiB`; disk `2 GiB` | memory `12 GiB`; swap `8 GiB`; disk `8 GiB` | memory `32 GiB`; swap `16 GiB`; disk `16 GiB` |
  | `GATE_B_QUALIFICATION` | memory `2 GiB`; swap `0 GiB`; disk `2 GiB` | memory `22 GiB`; swap `8 GiB`; disk `6 GiB` | memory `12 GiB`; swap `8 GiB`; disk `8 GiB` | memory `36 GiB`; swap `16 GiB`; disk `16 GiB` |
  | `FORMAL_ORGANIC_ARM` | memory `24 GiB`; swap `0 GiB`; disk `2 GiB` | memory `4 GiB`; swap `12 GiB`; disk `6 GiB` | memory `8 GiB`; swap `4 GiB`; disk `8 GiB` | memory `36 GiB`; swap `16 GiB`; disk `16 GiB` |

  These are explicitly `CONSERVATIVE_TEMPORARY` profiles, not accepted
  stage-peak measurements; each basis declares confidence `LOW`.
  The full-preflight profile may cite only the
  heterogeneous historical external sampler as scheduling evidence
  (`13,507,510,272` bytes sampled process-tree peak RSS, `218` samples); it is
  not receipt authority and is the only basis marked comparable to its stage.
  Gate-B qualification has no accepted stage peak and is non-comparable.
  Formal organic arms likewise have no accepted stage peak and use the
  historical `24 GiB` planning upper bound only as a heterogeneous,
  non-comparable proxy. Every basis therefore records zero accepted stage-peak
  receipts and the warning
  `TEMPORARY_PROFILE_NOT_A_STAGE_PEAK_MEASUREMENT`. A later measured profile
  requires a new exact source/schema cohort; it cannot silently reinterpret
  these values.

  Admission headroom and runtime cgroup containment are distinct layers.
  Only one serial formal organic arm uses `MemoryHigh=35 GiB`,
  `MemoryMax=39 GiB`, `MemorySwapMax=16 GiB`, and
  `RuntimeMaxSec=3600`; these are fail-closed safety caps, not substitutes for
  the live profile check and not a claim that those maxima will be consumed.
  Formal admission separately verifies that live RAM after host reserve plus
  live swap after host reserve, capped at `MemorySwapMax`, can back
  `MemoryMax`; that feasibility arithmetic does not become a predicted
  working set.
  All three stages require one worker, an exact same-UID conflict scan, and
  the same three retained locks:
  `/tmp/zmd-pj-codex-heavy-validation.lock`,
  `/run/user/1000/zmd_pj_prod_scale_solver.lock`, and
  `/run/user/1000/zmd-pj-prod-scale-solve.lock`. A conflicting process,
  unavailable/conflicting lock, uncertain scan, or resource value even one
  byte below the stage minimum blocks launch.
- Gate-B qualification has one persistent owner actor. The same
  PID/starttime and qualification session acquire and retain the exact three
  heavy-work locks before the first resource gate, cover the final full
  preflight, publish the epoch observation as sequence 1, cover the second
  stage-specific resource gate, and publish Gate-B approval as sequence 2.
  After lock acquisition it re-closes the current three retained FD/path
  identities and evaluates `FULL_PREFLIGHT` immediately before the pinned
  full preflight. It re-closes those same identities and evaluates
  `GATE_B_QUALIFICATION` immediately before approval and bootstrap. A prior
  observation cannot be substituted after waiting or resource drift. The
  pinned preflight creates one fresh no-overwrite mode-`0700` output root,
  its mode-`0700` `pytest-scratch` child, and exactly one mode-`0700`
  `pytest-scratch/basetemp` child. It supplies a minimal fixed environment,
  runs the full `not slow` pytest lane serially under `-I -B` with the pinned
  `pytest.ini`, rootdir, confcutdir and explicit `randomly` plugin, and rejects
  inherited Python/pytest plugin or option injection. Before and after the
  selected preflight it independently enumerates, without Git-ignore
  semantics, the fixed pytest configuration/governance members, the complete
  discovery tree, and every repository-root `PathFinder` source, bytecode,
  extension or identifier-namespace candidate. Each descriptor-relative
  observation is compared with the committed HEAD projection, closes all of
  its descriptors before returning, and never changes `RLIMIT_NOFILE`.
  The AB16 qualification runner, not shared pytest configuration or the
  ordinary preflight command, explicitly loads one hash-bound plugin object.
  That plugin writes its canonical collected nodeid/path manifest and two
  terminally closed records through one anonymous retained regular FD. The
  Gate-A consumer independently parses the recorded stdout bytes and binds
  the exact same-run collection projection to the receipt. Any reported
  module origins are diagnostic only: they are not a fixed-HEAD byte proof or
  a closed import-set claim.

  This pre/post surface contract rejects pre-existing or persistent ambient
  pollution. It does not claim to defeat an actively hostile same-UID writer
  that replaces and restores a path entirely between the two observations;
  the formal lane requires the three locks and an isolated host with no such
  writer. If that stronger threat is ever admitted, it requires a separate
  fixed-commit, no-extra-member execution snapshot rather than retained
  whole-repository blob FDs. The Linux loader is a child subreaper; only
  `waitpid(-1, WNOHANG)` reaching `ECHILD` proves descendant closure.
  `/proc/.../children` is used only to discover direct/adopted descendants for
  public-runtime/named-libc pidfd signaling. Unsupported capability or cleanup
  uncertainty fails closed, and unrelated same-UID processes are never
  scanned or terminated.

  A v6 PASS requires the retained scratch identity, one unchanged basetemp
  identity, and an empty basetemp; no producer cleanup deletes the tree.
  Stdout, stderr, `receipt.json`, and a mode-`0600` staged
  `receipt.commit.json` are created and verified through the retained
  creation-time output-root FD. After critical parent descriptors close, a
  dedicated child performs the sole mode-`0444` marker-promotion syscall.
  The producer then independently reopens the recorded absolute path and
  replays the exact output-root identity, exact five-member tree, receipt,
  marker, logs and scratch before returning. The final closed-scratch
  observation is the producer's temporal linearization check; a later
  external mutation is a later operation, not a rewrite of that observation.
  All Gate-A, bootstrap and authority parsers require the exact mode-`0444`
  committed marker; a staged marker is never consumable. Failure or timeout
  preserves the root for diagnosis, while descendant, scratch, Git-surface,
  publication, close, or replay uncertainty cannot mint a PASS. Gate B
  reaches the same contract through its pinned Gate-A entrypoint. Historical
  v3 receipts remain frozen to their own source set and grant no successor
  qualification.
  The owner actor retains the sealed request, rendered-record, renderer-source,
  mechanical-publisher, output-directory, and lock descriptors through the
  live bootstrap handoff. It may release only after bootstrap has
  independently joined the actor, session, lock identities, source bytes,
  epoch and approval, created the package/campaign with no overwrite, and
  returned a canonical result that the qualifier has read back. Actor death,
  sequence drift, FD loss, lock drift, or premature release invalidates
  Gate-B authority.
- The formal-launch owner is a different persistent actor. One PID/starttime
  publishes admission as sequence 1 and remains alive while the
  package-selected formal supervisor acquires the same exact three formal
  locks, re-closes their identities, passes the post-lock
  `FORMAL_ORGANIC_ARM` gate, starts the guardian, and creates both
  guardian-ready and the consumed-attempt marker. The same owner alone may
  then publish selection as sequence 2. Selection must bind the admission,
  guardian-ready, attempt-consumption, current three lock identities,
  package, manager epoch, HEAD, snapshot, and selected tool bytes. No Gate-1
  or organic formal unit may launch before that selection is validated. In
  this cohort the owner handoff closes only after the selected supervisor
  returns its selection-bound `VERIFIED` or `INCOMPLETE` result.
- The formal supervisor retains all three locks through the fixed Gate-1
  units, baseline admission, manifest/suite selection, all serial organic
  arms that remain eligible, observers, terminal evidence, cleanup,
  exact-once `RefUnit`/`UnrefUnit`, post-Unref absence, and detached
  substantive replay. Only after those items close may it release the
  guardian and supervisor locks and publish the terminal release join.
  While those locks remain live, it must repeat `FORMAL_ORGANIC_ARM` admission
  immediately before the outer formal unit and immediately before each
  organic arm's one-shot prelaunch publication. Each v2 prelaunch receipt
  embeds and independently validates that admission against the current three
  lock identities. The v2 outer-start and controller-result receipts
  separately carry and strictly replay the final live reevaluation performed
  at the corresponding `systemd-run` syscall edge; an earlier PASS cannot
  authorize a later launch.
  Missing actor liveness, out-of-order publication, an unjoined lock identity,
  or any terminal/replay gap fails closed. A post-selection failure is
  consumed, retry-ineligible, and cannot be replaced by another arm or
  attempt.
- Gate A remains non-authorizing for Gate B. Gate B authorizes only creation
  of the exact research campaign; admission and selection authorize only
  their fixed local launches. `MECHANISM_CREDIBLE` and the preregistered arm
  outcome classes remain local non-certified research conclusions. Every
  artifact keeps all whole-instance, witness, upper/lower-bound,
  cut/promotion, production/certified, attainability, optimality, and
  SAT/UNSAT authority false. Tracked state remains `U=(1188,18)` and
  `L=absent`.

## 4. Forbidden Changes

- Reintroducing exploratory caps as exact-mode bounds.
- Treating exploratory artifacts, legacy cuts, or diagnostic flow checks as certified proof.
- Changing campaign, artifact, or proof schemas without explicitly updating the lock/spec/test boundary together.
- Publishing a terminal `CERTIFIED` final result whose empty-rectangle `min_side` is below the canonical project `min_side_admissibility`, even if it was found in a superdomain run.
- Adding a new `candidate_generation` or `EXACT_*` certified-surface axis without first classifying it in the closed contract and adding fail-closed red tests.
- Enabling `EXACT_CUT_FRAMEWORK_ATTACH=1` in any certified / production campaign path (classified 2026-07-08, P1.3 M3-4). The active eight-family framework (F1-F7+F9; F8 retired) has typed Step-8 lowerings only for F1/F6/F7 (registry→resolver→`step_8_apply_to_master`→`typed_apply`); F5 is shadow-only (`ShadowValidated`, no lowering, structurally cannot mutate the master — its former Step-8 apply path was physically deleted in B5a); F2/F3/F4/F9 are LEGACY_DIAGNOSTIC and are rejected at the typed single-entry registry boundary. `_maybe_attach_framework_cuts` remains registered in the certified unsafe env map (`cut_framework_attach_not_certified`) with red tests on both direct-benders and outer-search entrances. Promotion out of the unsafe map requires **all** current production-integration prerequisites, not merely the M4 ladder/equivalence work: PIC-4/PIC-5 production-host evolution/orchestration validation at production scale (the integration-harness layer of PIC-5 is already covered by directed tests; the production-campaign layer is not), RFC-003 ledger+dedup+epoch, the batch-α2 B6 checklist items, the session-bundle ownership decision recorded in the Stage-B spec, and finally B6 explicit owner promotion with this lock/checker/red-test flip. Status snapshot 2026-07-12: Stage B B0-B5b, the independent F5 verifier (RFC-002, batch D), pre-promotion hardening batches α/α2, the B6-prep engineering batch (session-scoped bundle ownership), and RFC-003 batch E (orchestration-layer semantic dedup with an applied-only per-master-build pool, plus a strictly non-consumed JSONL audit ledger — restart re-qualification is regeneration through the typed chain under an owner-approved waiver of the ledger-envelope-replay reading; the batch-E harness/fixture gates are green while the RFC §9.6 prod-scale A/B gate stays OPEN for batch C) have landed; the agnostic-F5 seam was eliminated by architecture in B5a; the real F5 adapter still fails closed before the verifier (frozen tuple/list shape gap, pinned by a sentinel test), so any F5 promotion additionally requires the adapter fix plus a real-adapter e2e. Until owner promotion, F5 stays shadow-only and the direct attach path remains unsafe/default-off. The promoted path inherits every cut-lifecycle fail-closed obligation in this lock (F-*/PCR-*/CUT-* families).
- Rebinding globally pooled resources into per-line or per-instance hard bindings without a new exact proof basis.
- Adding any exterior-path requirement for the ghost rectangle.
- Enabling `EXACT_POWER_PLACEMENT_SUBPROBLEM=1` in any certified / production campaign path. The power-pole subproblem feature flag is exploratory only. Status of the three known exactness gaps (originally characterized in the GPT v4 review follow-up; 三项 status 至 v28 外审未变, gate 仍强制):
  - **Live ghost-conditioned infeasible cut**: implemented (`condition_lits` 走 master.add_benders_cut, `OnlyEnforceIf`).
  - **Persisted cut replay**: `BendersCut.condition_set` 在 `run_benders_for_ghost_rect` 现已通过 `_resolve_condition_lits_from_condition_set` 反解析回 master `u_var`, certified mode 下未知 condition fail-closed skip cut (不退化成无条件).
  - **Feasible-path pole alternatives**: 未实现 witness-complete cut. 现 stop-gap: `_add_exact_whole_layout_nogood` 在 flag on 且 solution 含 synthetic power_pole entry 时 fail-closed skip cut, caller 升 `UNKNOWN`. 真正解锁 feature 需要 enumeration / 多 witness 增量排除.
  
  The production readiness gate and `scripts/run_campaign_linux.sh` both still block when the env var is set; do not bypass them until pole alternatives is implemented and re-audited.

- **Whole-layout nogood independent reverify (I1, implemented in current worktree)**:
  `benders_loop.py::_reverify_whole_layout_infeasibility_before_cut` (current call path around `:8279`) calls
  `independent_infeasibility_reverifier.reverify_whole_layout_infeasibility()` before a
  proof-bearing whole-layout nogood may be added. The reverifier rebuilds the relevant binding or
  routing question through its own entry point; `confirmed=false`, a feasible divergence, malformed
  evidence, or an exception yields `UNKNOWN`/no cut. This closes the previously registered
  “same solver attests its own whole-layout conflict” implementation gap and is sealed by
  `PO-INDEPENDENT-INFEASIBILITY-REVERIFY`. It does not prove that every future cut family has an
  independent checker, and it does not by itself close P1.2 or remove the verifier/solver stack from
  the TCB.

- Bypassing **exact-safe proof object lifecycle**. Any persisted artifact carrying solver-side semantics (e.g. `BendersCut.condition_set`, `BendersCut.metadata`) must have all six steps wired before being trusted in certified mode: generate → serialize → deserialize → validate → resolve runtime literals → replay → behavioral regression test. Landing a new schema field without the runtime resolver + regression coverage is treated as a Forbidden Change, regardless of how harmless the "feature gate currently off" feels.
- **(2026-05-22) Bypassing B Design v2 cut lifecycle**: new B Design v2
  cut object (Phase 1 起在 `src/cuts/` 落地) 必须 wire 全部 lifecycle 步骤
  （**canonicalize = Step 0 共用哈希/序列化基础、非业务步；业务链 9 步**，
  与 docs/项目说明/04 §2.2 / 06 / cut_lifecycle_v2 口径一致）:
  canonicalize → generate → minimize/normalize → serialize → deserialize →
  validate → attach-scope check → resolve → activation index → replay/regression.
  (Step 10 dominance/expiry/demotion defer to Phase 2 per Gemini round 13.)
  跳过任一步骤 (例如 Phase 1 implementation 没写 scope-aware replay 直接进
  168h campaign) 算 Forbidden Change. PoC `docs/research/p3_b_design_v2_20260521/
  poc/b_core_lifecycle_poc.py` 14/14 PASS 必跨 src/ boundary 真验.

  **Capacity-based Eviction 豁免** (Gemini round 24 B1 — A2 §4 vs A3 R2 冲突解):
  Step 10 dominance/expiry/demotion 严禁的是**语义级 expiry** (基于 cut
  hit-count / age / subsumption 主动 demote/expire). **不禁** capacity-based
  eviction — 当 cut store 达 RAM/disk 上限 (e.g. 5 GB/worker per criterion #6)
  时, 走 LRU/FIFO 驱逐**最近最不命中的 cut** (cut 仍 sound 只是工程上不存)
  防 OOM. 这是工程兜底, 不属于 Step 10. Phase 1 实施时驱逐 cut 必走
  `data/cuts/quarantine/evicted/` 子目录留 audit trail (不删, 168h close 后
  归档), 跟 Step 10 semantic expiry 不混.
- **(2026-05-22) Silent recovery 禁止**: B Design v2 9 family cut + replay
  全 fail-closed. cut.scope.source_digest 跟当前 source-of-truth hash 不一致
  → quarantine, **不可 auto-migrate**. 即使重算 cert 在新 source 下 sound,
  仍要手动 audit override (PROJECT_LOCK 一致 — certified exact 不允许 silent
  fix). Validator `ASSUMPTION_VERIFIERS` 未知 key → fail-closed return False
  (HOLD), 不可 silent return True. (Gemini round 14-22 共识 invariant.)

## 5. Allowed Changes

- Exact-safe lower bounds, dominance rules, reuse, caching, and scheduling improvements.
- Optional frontier probes that evaluate legitimate potential-domain candidates without weakening proof semantics.
- Additive postprocess exports, viewer/report sidecars, and delivery summaries.
- Additive neutral contract layers in `src/interchange/*` and build-time/export-time adapters in `src/adapters/*`.
- Adapter-side outer deployment planning/probing for larger IndustrialPlanner bases, plus optional exporter/throughput-manifest bridge metadata for those translated exports, may remain preserved as future-scope tooling provided those artifacts stay postprocess-only and are not promoted as certified evidence.
- Documentation, governance, provenance, and regression coverage improvements.
- Runtime discoverability improvements that do not alter solver semantics.

## 6. Update Rule

If a change affects exact boundaries, runtime roles, or certified output meaning, update:

1. `PROJECT_LOCK.md`
2. `FILE_STATUS.md`
3. the relevant spec(s)
4. the relevant regression tests
