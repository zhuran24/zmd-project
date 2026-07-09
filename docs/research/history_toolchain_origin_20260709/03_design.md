## 工具链最初设计的整体形状

- 转折后的核心形状是"LBBD 外层 cut framework",不是继续重写 master:数学地基写成"**不改 master, 在 master 外累积 sound 知识层**"。出处:[02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:13);短引:"不改 master"。

- 组件清单:`Cut` 对象、9 个 cut family、family-specific oracle、validator、scope-aware replay、CutStore watcher、quarantine/hold 状态机。出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:3);短引:"cut object schema / scope-aware replay / group-state contract / per-family validator / watcher index / quarantine"。

- `Cut` 的一等对象定义是 `family + scope + cert + body`,body 分成 literal 和 geometric 两类。出处:[02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:23);短引:"Cut 4 元组定义"。另见 [cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:313);短引:"literals … 与 geometric_payload … 互斥"。

- `cut_family_specs/` 清单最终锁成 9 个:`01_region_capacity`、`02_cutset`、`03_port_exposure`、`04_component_reach`、`05_pattern_nogood`、`06_shape_packing_hall`、`07_power_hitting_set`、`08_power_grid_reach`、`09_density_envelope`。出处:[PHASE_0_CLOSE.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md:37);短引:"9 大 Cut Family 矩阵"。

- 代表 family 1:`region_capacity` 是几何容量 cut,用 `demand_R > cap_R` 证明不可行。出处:[01_region_capacity.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md:29);短引:"demand_R > cap_R ⇒ INFEASIBLE"。

- 代表 family 6:`shape_packing_hall` 是 F1 的形状切片加强,F1 看 cell 总数,F6 看 interval 能否装下刚体。出处:[06_shape_packing_hall.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md:36);短引:"region_capacity 看 cell 总数, shape_hall 看 interval"。

- 代表 family 9:`density_envelope` 一开始想做几何 lift,后来被降级为 area-only,拒绝把 routing/binding 死锁泛化成密度。出处:[09_density_envelope.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_family_specs/09_density_envelope.md:29);短引:"Paradigm 降级"。

- `poc/` 清单是 `README.md`、`b_core_lifecycle_poc.py`、`test_b_core_lifecycle.py`;最早 PoC 只跑 F1,但验证了 9 步 lifecycle、互斥 schema、scope、hash、HOLD/QUARANTINE 等运行时路径。出处:[poc/README.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/poc/README.md:10);短引:"cut object lifecycle 9 步 … Family 1"。测试结论出处:[poc/README.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/poc/README.md:26);短引:"14 passed, 0 failed"。

- `red_fixtures/` 最初 F1-F4 是 schema-level 反例,后来加 F5 power grid disconnect。出处:[red_fixtures/README.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/red_fixtures/README.md:24);短引:"4 个 Red Fixture"。F5 出处:[F5_power_grid_disconnect.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/red_fixtures/F5_power_grid_disconnect.md:5);短引:"Family 8 power_grid_reach"。

## cut lifecycle 最早版本的状态机与关键不变量

- 最早主文档写成 Step 0-9 加 Step 10 deferred;Step 10 的 dominance/expiry/demotion 明确推迟到 Phase 2。出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:60);短引:"Lifecycle 10 步详解"。Step 10 出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:202);短引:"Step 10 (DEFER)"。

- 状态机核心是 `ACTIVE / HOLD / QUARANTINE`:`ACTIVE → QUARANTINE`,`HOLD → ACTIVE`,`HOLD → QUARANTINE`,`QUARANTINE` 不自动恢复。出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:845);短引:"Cut state machine"。

- `HOLD` 和 `QUARANTINE` 是最早设计里的关键区分:ghost 不匹配是 HOLD,不是删 cut;真正 source/hash/cert 出错才 quarantine。出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:400);短引:"不 quarantine — 不同 candidate 用不同 ghost 是正常"。不变量出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:447);短引:"HOLD 不删 cut"。

- replay 的不变量是 6 步 scope verify:source digest、ghost、blocked/exterior hash、artifact、oracle version、active assumptions。出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:394);短引:"6 步 verify"。

- literal cut 必须用 group 内 multiset 语义,不按 slot 顺序判定;slot_index 只保留 debug/serialization。出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:582);短引:"set of (group_id, pose_id) multiset"。另见 [cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:612);短引:"slot_index 只为 debug"。

- source 变化必须 fail-closed:所有 cut 重新 validate,artifact 变则 quarantine,不 silent recovery。出处:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:868);短引:"source change → 所有 cut 必须重 validate"。

## 最早规划的 phase 路线图

- Phase 0 交付的是设计闭环,不改 `src/`:state machine、cut lifecycle、9 family、5 fixtures、PoC、22 轮 cross-check。出处:[PHASE_0_CLOSE.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md:109);短引:"进 Phase 1 前 ready checklist"。

- Phase 1 的原始 scope 是完整 `src/cuts/` 实施、接 `benders_loop`、跑 5/20/40/80 ramp。出处:[PHASE_1_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md:7);短引:"9 family 完整 src 实施 + benders_loop integration"。

- Phase 1.0 是 framework:`lifecycle.py`、`store.py`、`replay.py`、assumption verifiers、helpers。出处:[PHASE_1_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md:78);短引:"Phase 1.0 — Framework"。

- Phase 1.1 实施 F1-F4;Phase 1.2 实施 F5-F9;Phase 1.3 接 master;Phase 1.4 ramp 到 266 inst。出处:[PHASE_1_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md:93)、[PHASE_1_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md:103)、[PHASE_1_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md:114)、[PHASE_1_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md:127)。

- Phase 1 完成物原计划包括 `src/cuts/`、`data/cuts/*.json`、ramp reports、exit criteria、168h go/no-go gate。出处:[PHASE_1_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md:215);短引:"Phase 1 完成 deliverable"。

- `PHASE_POST_1_1_REFACTOR_PLAN.md` 自身不是正文,而是 redirect stub;原 1449 行 plan 与数学文档被拆到 `docs/项目说明/` 21 个子文档。出处:[PHASE_POST_1_1_REFACTOR_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md:1);短引:"SUPERSEDED"。迁移出处:[PHASE_POST_1_1_REFACTOR_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md:7);短引:"21 sub-doc"。

## 数学地基文档的核心主张

- `MATHEMATICAL_FOUNDATIONS.md` 本体已 superseded,内容迁到 `docs/项目说明/02_mathematical_foundations.md` 等文件,且声明旧内容 100% 进入新位置。出处:[MATHEMATICAL_FOUNDATIONS.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/MATHEMATICAL_FOUNDATIONS.md:1);短引:"SUPERSEDED"。迁移出处:[MATHEMATICAL_FOUNDATIONS.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/MATHEMATICAL_FOUNDATIONS.md:36);短引:"旧 math content 100% 进新位置"。

- 核心主张 1:27 个死路归纳出 4 个 root cause,结论是不重写 master,而在外部积累 sound cut 知识。出处:[02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:7);短引:"27 个其他 paradigm 死路"。结论出处:[02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:13);短引:"不改 master"。

- 核心主张 2:sound deduction rule 是 `scope.matches + validator OK ⇒ cut 只排除不可行 assignment`。出处:[02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:34);短引:"Sound deduction rule"。

- 核心主张 3:9 family 各有数学根据,覆盖容量、割、端口、连通、nogood、Hall、hitting set、电网、密度。出处:[02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:47);短引:"9 family 数学根据 overview"。

- 核心主张 4:validator 是 trust boundary,oracle 可被当成 Byzantine;validator 必须独立重算。出处:[02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:135);短引:"oracle Byzantine"。另见 [02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:139);短引:"validator 是 cut framework 唯一 trust point"。

- 核心主张 5:收敛性不是数学地基已证明的东西;9 family 是否 complete 仍 open。出处:[02_mathematical_foundations.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/02_mathematical_foundations.md:530);短引:"9 family 是否 cover 所有 INFEASIBLE 类? — open"。

## 与当前实现可见的差异点

- Step 数口径变了:早期文档写"完整 10 步 lifecycle,Step 10 defer",当前项目说明把业务 lifecycle 固化为 9 step,并把 canonicalize 当基础工具。出处早期:[cut_lifecycle_v2.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:3);短引:"完整 10 步"。出处当前:[04_design_invariants.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/04_design_invariants.md:31);短引:"为什么 lifecycle 是 9 step"。

- 当前 `src/cuts/lifecycle.py` 已比 PoC 硬化:9-family map、`exterior_blocks_hash`、Step 2/8 stub 都写在模块头。出处:[lifecycle.py](/home/zhuran24/claude-pj/zmd/src/cuts/lifecycle.py:6);短引:"9-family map"。Step 2/8 出处:[lifecycle.py](/home/zhuran24/claude-pj/zmd/src/cuts/lifecycle.py:15);短引:"stubbed with NotImplementedError"。

- 当前源码可见 F5-F9 已有 family/oracle 文件并在 replay validator 表注册;这比原 Phase 1.1/F1-F4 阶段更靠后。出处:[families/__init__.py](/home/zhuran24/claude-pj/zmd/src/cuts/families/__init__.py:8);短引:"pattern_nogood … Phase 1.2"。注册出处:[replay.py](/home/zhuran24/claude-pj/zmd/src/cuts/replay.py:62);短引:"FAMILY_VALIDATORS"。

- 但当前仍未看到 B Design v2 的 master 注入完成:`step_8_apply_to_master` 仍 `NotImplementedError`,计划文档也写"当前 … NotImplementedError"。出处源码:[lifecycle.py](/home/zhuran24/claude-pj/zmd/src/cuts/lifecycle.py:1005);短引:"Step 8 — push cut"。出处计划:[09_phase_1_3_plan.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/09_phase_1_3_plan.md:35);短引:"step_8_apply_to_master 实施"。

- 当前 `CutStore` 仍是 in-memory store,disk persist 被文档标为 Phase 1.3 defer;这不同于最早 Phase 1 deliverable 里的 `data/cuts/*.json`。出处当前:[store.py](/home/zhuran24/claude-pj/zmd/src/cuts/store.py:21);短引:"in-memory CutStore"。原计划出处:[PHASE_1_PLAN.md](/home/zhuran24/claude-pj/zmd/docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md:217);短引:"data/cuts/*.json"。

- 当前还有旧 `src/models/cut_manager.py` 运行时 JSONL/structured Benders cut 兼容层;它不是同一个 `src/cuts/CutStore` lifecycle。出处:[cut_manager.py](/home/zhuran24/claude-pj/zmd/src/models/cut_manager.py:157);短引:"Compatibility manager for both runtime JSONL cuts and structured exact cuts"。因此"已有 cut manager"不能等同于 B Design v2 cut framework 已完整接 master,存疑。

- 当前实现明显吸收了后来 audit hardening:默认 add_cut 先 held、replay 必做 integrity check、validator fail-closed。出处:[store.py](/home/zhuran24/claude-pj/zmd/src/cuts/store.py:127);短引:"默认 held"。出处:[replay.py](/home/zhuran24/claude-pj/zmd/src/cuts/replay.py:103);短引:"validate_cut_integrity"。出处:[lifecycle.py](/home/zhuran24/claude-pj/zmd/src/cuts/lifecycle.py:467);短引:"payload/hash bookkeeping"。

- 当前生产集成仍有未闭环项:生产 data 注入、F2/F3/F4 真 oracle、F3 active port witness、F2 max-flow LP witness 都在 Phase 1.5+。出处:[10_phase_1_5_plan.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/10_phase_1_5_plan.md:38);短引:"各 family oracle 真实施"。F3 风险出处:[10_phase_1_5_plan.md](/home/zhuran24/claude-pj/zmd/docs/项目说明/10_phase_1_5_plan.md:51);短引:"production-前置 risk"。