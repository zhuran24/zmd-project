# P1.3 批 1 C1 certified 化任务书草案（2026-07-10）

范围：只把批 0 已实测获胜的 C1 供电编码升格为 `src/models/exact_coordinate_master.py` 的 certified 默认编码，并补齐解级 dominance 剪杆与 reseal 材料。本文件是主会话对抗复核前的任务书草案，不是实现提交。

批 0 权威结论：C1 v1 在自由 w6 1800s 下 `OPTIMAL @541.3s`，26 杆、6x6 ghost、独立覆盖复验通过，且每杆都是某设施唯一覆盖者（`docs/research/p1_3_a_batch0_20260709/README.md:7-14`）；w12 两连 OOM，w6 安全（`README.md:29-41`），w24 cgroup 42G 在 9min03s 事件尖峰 OOM（`README.md:59-66`）。批 1 建议已明确为 C1 certified 化 + 完整 reseal + canonical env + EXACT_* 三件套 + 池完整性 fail-closed + 解级 dominance 剪杆 + 内存条款 + 新旧编码等价性测试（`README.md:44-49`）。

外审约束并入本任务书：

- 统一 validated attach admission gate：C1 手术不得给 cut attach 链新增绕过面；现有 attach gate 顺序集中在 `_maybe_attach_framework_cuts()` 的 integrity、family validator、step_6、step_7、step_8 链（`src/search/benders_loop.py:7734-7914`）。
- 首轮生产面只收 F1/F5/F6/F7：当前生成面在 F1/F7、F6、F5 adapter 三段（`src/search/benders_loop.py:7807-7861`），本批不得顺手打开其他 oracle/adapter。
- F5 adapter 登记 TCB：`src/search/f5_binding_empty_domain_adapter.py` 自述为 F5 首个 production adapter（`src/search/f5_binding_empty_domain_adapter.py:1-24`），但 V99 floor 仍把它标成 `out_of_scope_future_phase3b`（`scripts/check_p1_2_proof_obligations.py:12773-12822`），本批 reseal 必须处理。

## 一、改动面清单(文件级→函数级,逐项标注 sealed 与否)

| 文件 | sealed | 函数/区域 | 批 1 改动性质 | 行号依据 |
|---|---:|---|---|---|
| `src/models/exact_coordinate_master.py` | 是 | `_prepare_power_pole_families()` 与 power-pole family 预计算 | 继续复用 pose/family 权威数据；C1 下 family count 改成 `sum(p_k in family)`，不能依赖残留 pole slot | `src/models/exact_coordinate_master.py:2084-2114`, `2160-2258`; V99 classified certified path: `scripts/check_p1_2_proof_obligations.py:12790-12799` |
| `src/models/exact_coordinate_master.py` | 是 | `_prepare_slot_specs()` / `_residual_optional_slot_upper_bound()` | C1 默认下 residual `power_pole` 坐标槽不再出生；required power-pole 必须原生进同一 `p_k` 池语义，不能保持 prototype 的 fail-closed | slot cap special-case: `src/models/exact_coordinate_master.py:1646-1669`; mandatory/slot prep: `2283-2295`; prototype fail-closed: `docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:36-47`; v0 bug: `02_c1_patch_codex_review.md:24-26` |
| `src/models/exact_coordinate_master.py` | 是 | `_create_power_pole_slot_vars()` | 主手术：拆除 763 个坐标 pole slot 的 x/y/family/shell lookup/symmetry 链，创建完整 `p_k` pose bool 池、常量 optional intervals、family count vars、池完整性 fail-closed | current pole slot machine: `src/models/exact_coordinate_master.py:3329-3447`; C1 design: `00_design_decision.md:17-22`; prototype: `c1_encoding_patch.py:50-100` |
| `src/models/exact_coordinate_master.py` | 是 | `build()` no-overlap / coverage call | `p_k` 常量 intervals 必须在组合 `AddNoOverlap2D` 前进入 `_core_x/_core_y_intervals`；覆盖约束改为 C1 cov 通道 | no-overlap build point: `src/models/exact_coordinate_master.py:3449-3505`; prototype interval injection: `c1_encoding_patch.py:83-90` |
| `src/models/exact_coordinate_master.py` | 是 | `_record_slot_footprint_binding()`, `_bind_slot_specs()`, `bind_from_core()`, `export_core_binding()` | 新增单独的 C1 pole binding 命名空间；不得把 `p_k` 假装成 `_slot_binding` 的 residual slot；clone/ghost overlay 必须恢复 C1 intervals | current bind/export: `src/models/exact_coordinate_master.py:3528-3645`; v0 clone bug: `02_c1_patch_codex_review.md:14-18`; prototype name-scan fix only可作反例: `c1_encoding_patch.py:103-144` |
| `src/models/exact_coordinate_master.py` | 是 | `_supports_rectangular_power_coverage()`, `_add_geometric_power_coverage_constraints()` | witness 从 wide-element pole-slot witness 改为全局 `cov[cell] <= sum(p_k cover cell)` + 每 powered 一个 witness cell；非矩形必须 fail-closed 或显式旧编码回退，不能用 bbox 洞 | rectangular guard: `src/models/exact_coordinate_master.py:5266-5300`; current dispatch/stats: `5952-6034`; C1 witness proof: `00_design_decision.md:22`; prototype: `c1_encoding_patch.py:146-214` |
| `src/models/exact_coordinate_master.py` | 是 | `_add_global_valid_inequalities()` | C1 下补生产 selected-powered dominance bound 与 capacity family inequalities 的等价输入；residual pole slots 消失后原 bound 不会自动触发 | selected-powered bound: `src/models/exact_coordinate_master.py:6357-6405`; capacity family: `6417-6465`; prototype修复: `c1_encoding_patch.py:216-237`; review finding: `02_c1_patch_codex_review.md:34-36` |
| `src/models/exact_coordinate_master.py` | 是 | `_finalize_build_stats()`, `extract_solution()` | build_stats representation/encoding 改为 C1 原生命名；selected `p_k` 必须落盘为 authorized `pose_optional::power_pole::<pose_id>` solution entry | stats: `src/models/exact_coordinate_master.py:6810-6851`; extraction: `6864-6915`; terminal authorization: `src/search/exact_campaign.py:937-967`; review extraction gap: `02_c1_patch_codex_review.md:38-42` |
| `src/models/exact_coordinate_master.py` | 是 | `add_power_pose_exclusion_cut()` | F7 attach seam 不得因 pole 槽命名空间变化放宽；继续使用 pose pool coverer table + powered pose literal，拒绝空 condition lits | F7 gate/table checks: `src/models/exact_coordinate_master.py:7362-7445`; external attach concern maps to `src/search/benders_loop.py:7734-7914` |
| `src/search/benders_loop.py` | 是 | certified env guard / canonical witness defaults / EXACT_* allowlist | C1 若成为默认 representation，canonical env 默认、known EXACT_*、unsafe override 检查、测试锁都要 reseal；旧 witness 若保留为 env 对照，必须进三件套 | env constants: `src/search/benders_loop.py:928-1021`; unknown EXACT fail-closed/canonical lock: `1328-1420`; sealed path: `scripts/check_p1_2_proof_obligations.py:12814` |
| `src/search/benders_loop.py` | 是 | `_master_search_summary()` | 继续输出 `power_coverage` summary 的 representation/encoding/powered/pole/cover/witness/element 字段，避免 delivery/telemetry 消费者断裂 | summary reads stats: `src/search/benders_loop.py:4237-4480` |
| `src/search/benders_loop.py` | 是 | certified solve return path | 解级 dominance 剪杆应在 `master.extract_solution()` 之后、candidate/proposal sink 之前；若 L4a power subproblem 被启用，也必须在注入 synthetic poles 后再剪 | extract/heartbeat: `src/search/benders_loop.py:5180-5189`; power subproblem hook: `5205-5233`; return certified: `5375-5383`, `7000-7017` |
| `src/search/benders_loop.py` | 是 | cut framework attach | 保持外审要求的 attach admission gate；C1 solution entries 不得让 `_framework_target_poses()` 或 F5/F7 adapter 看见未验证的 pole 面 | target pose extraction: `src/search/benders_loop.py:7667-7732`; attach gate: `7734-7914` |
| `src/search/outer_search.py` | 是 | `_build_certified_result()`, terminal commit, candidate mark result | 若剪杆放在 `benders_loop.py`，这里只作防御性验证；任何 CERTIFIED candidate 落盘前必须已经是剪杆后 solution | result/proposal: `src/search/outer_search.py:855-954`; worker CERTIFIED write: `2470-2493`; serial CERTIFIED write: `2673-2741`; evidence path: `data/proof_obligations/p1_2_proof_obligations.json:653-662` |
| `src/search/exact_campaign.py` | 是 | terminal verifier | 原则上不改 terminal verifier；用它作为剪杆后独立验收权威。若为复用 coverage 逻辑抽 helper，必须 reseal | coverage and unforced checks: `src/search/exact_campaign.py:1083-1255`; authorized pose optional: `937-967`; sealed path: `scripts/check_p1_2_proof_obligations.py:12822` |
| `data/proof_obligations/p1_2_proof_obligations.json` | 是 | obligations, evidence paths, source pins, semantic digest | 增加/更新 C1 等价、dominance 剪杆、F5 adapter TCB、source hash pins；语义字段变更要更新 semantic projection digest | current semantic digest: `data/proof_obligations/p1_2_proof_obligations.json:7`; close-kernel evidence: `620-665`; coordinate/benders/campaign source pins: `1299-1310`, `1559-1574`, `1691-1717` |
| `scripts/check_p1_2_proof_obligations.py` | 是 | required IDs/tests, V99 floor, source hash floor, strong status allowlist pins | checker 自身是 TCB；新增 obligation/test/source classification 必须改 checker 代码而不只改 JSON | required obligation IDs: `scripts/check_p1_2_proof_obligations.py:87-104`; evidence/test checks: `3070-3110`; semantic digest check: `3292-3351`; named TCB boundary: `12737-12743`; floor/classification: `12745-12822`; source pins: `12971-12972` |
| `data/proof_obligations/strong_status_write_allowlist.json` | 是 | strong-status writer allowlist | 只在改到 strong-status writer/source hash 面时更新；若 `outer_search.py` 或 `exact_campaign.py` hash 变，allowlist 与 checker byte pins 同步 reseal | allowlist policy: `data/proof_obligations/strong_status_write_allowlist.json:3-5`; checker byte pin enforcement: `scripts/check_p1_2_proof_obligations.py:4543-4600` |
| `src/search/f5_binding_empty_domain_adapter.py` | 需升格 | `BindingEmptyDomainAdapter.query_liftable()` 与 builder | 代码未必改；proof floor 分类必须从 out-of-scope 登记为本批批准的 TCB/production adapter，且绑定空域 liftable 语义写入 obligation | adapter contract: `src/search/f5_binding_empty_domain_adapter.py:1-24`, `66-117`, `132-145`; current misclassification: `scripts/check_p1_2_proof_obligations.py:12815` |
| `src/tests/...` | 通常否，若列入 obligation 则受锁 | C1 equivalence, clone/bind, required pole, env guard, attach, proof obligations, memory | 新增/更新 targeted tests；列入 manifest 的 required tests 后成为 proof gate | existing required-pole test surface: `src/tests/test_exact_coordinate_protocol_bounds.py:117-177`; proof required tests mechanism: `scripts/check_p1_2_proof_obligations.py:177-197`, `3070-3110` |
| `src/models/cp_sat_worker_config.py` / campaign wrappers | 否，若进 proof surface 则重审 | worker/memory defaults | 生产内存条款落地位置；CP-SAT `max_memory_in_mb` 只是软 cap，不能替代 cgroup/RSS 硬帽 | worker defaults: `src/models/cp_sat_worker_config.py:20-31`; memory caveat: `140-149`; w6/w12/w24 evidence: `README.md:39-41`, `59-66` |

## 二、编码手术方案(杆槽族拆除/p_k 池/cov 通道/witness cell 在生产代码里的落位——不再是 monkeypatch,要处理 clone/bind、extract_solution、build_stats representation、slot_binding 契约、容量族、对称链的全部接缝;v1 原型四修复的原生化)

1. 入口形态：C1 不是 monkeypatch，也不是临时 env。`c1_encoding_patch.py` 的 `apply_c1_patch()`/`revert_c1_patch()` 只说明原型替换了 `_prepare_slot_specs`、`_create_power_pole_slot_vars`、`_add_geometric_power_coverage_constraints`、`bind_from_core`（`c1_encoding_patch.py:252-269`）；生产实现必须把这些语义原生落在 `CoordinateExactMasterDelegate` 的构造、build、bind、extract 和 stats 路径中。

2. 杆槽族拆除：
   - 当前 `_create_power_pole_slot_vars()` 为每个 residual pole slot 建 active、x/y、family、shell distance lookup、tuple table、`_slot_binding`、interval binding、family literal、active/family/order symmetry chain、family count vars（`src/models/exact_coordinate_master.py:3329-3447`）。
   - C1 默认下，residual `power_pole` 不再创建 coordinate slot；`_residual_optional_slot_upper_bound()` 中的 power-pole cap 仍保留为总杆数上界输入（`src/models/exact_coordinate_master.py:1646-1669`）。
   - 对称链（active 前缀、family 单调、同 family order_key 单调）是 coordinate slot 置换用的（`src/models/exact_coordinate_master.py:3425-3437`）。`p_k` 池没有同质槽置换，不应机械迁移；C4a 全局 lex 已被对抗审查判为过约束/零增量，不进批 1（`00_design_decision.md:76-86`, `100-120`）。

3. `p_k` 池与 fail-closed 完整性：
   - 权威池来自 `owner.facility_pools["power_pole"]`，等价性依赖“pose 池 = 坐标杆域完整格阵”引理（`00_design_decision.md:17-22`, `68-70`, `116`）。
   - 生产 build 必须逐点校验 anchor 集合等于 `_template_full_mode_rect_domains["power_pole"]` 的笛卡尔域，禁止只验数量。v0 bug 明确指出“缺 `(68,68)`、重复 `(0,0)` 但长度仍 4761”会假 INFEASIBLE（`02_c1_patch_codex_review.md:20-22`）；v1 原型使用 anchor set equality（`c1_encoding_patch.py:56-76`）。
   - 同一校验还要确认 pose tuple / occupied bbox / `power_coverage_cells` 与 anchor/domain 一致。`_build_mode_rect_domains_from_pose_indices()` 与 `_template_pose_tuple_by_idx` 已给出 pose/domain 数据来源（`src/models/exact_coordinate_master.py:1581-1644`, `731-770`），不能用 ad hoc 字符串推断。

4. required/mandatory power-pole 原生化：
   - v1 原型对 required/mandatory `power_pole` 选择 fail-closed（`c1_encoding_patch.py:36-47`），但 review 已指出 certified 版必须处理生产 `_all_power_pole_slots()` 包含 required + residual 的事实（`02_c1_patch_codex_review.md:24-26`; current helper `src/models/exact_coordinate_master.py:3128-3132`）。
   - 批 1 实现要求：required pose-optional power_pole 进入同一 `p_k` 池，以 required count 下界/等式表达，不再保留“required 坐标杆 + 全池 p_k”的混合语义；true mandatory power_pole 若 artifacts 未来出现，必须在 build 阶段以机器可查证据映射到 fixed `p_k`，否则 fail-closed 并新增测试。现有 required-pole 测试面在 `src/tests/test_exact_coordinate_protocol_bounds.py:117-177`。

5. 常量 intervals 与 no-overlap：
   - 每个 power-pole pose 建 `BoolVar p_k`，再用 pose `occupied_cells` 的 bbox 建常量 optional x/y intervals，presence=`p_k`，在 `build()` 调用 `AddNoOverlap2D` 前追加进 `_core_x_intervals/_core_y_intervals`（build point `src/models/exact_coordinate_master.py:3472-3479`; prototype `c1_encoding_patch.py:77-94`）。
   - 这是 v0 最严重 bug 的生产修复面：clone + ghost overlay 时 C1 interval 若未进入 export/bind，会导致 ghost/设施/杆互相重叠仍 FEASIBLE（`02_c1_patch_codex_review.md:14-18`）。生产不能采用 prototype 的 proto-name scan hack（`c1_encoding_patch.py:103-144`）；应在 `export_core_binding()` 输出稳定的 `c1_power_pole_binding`，由 `bind_from_core()` 按 binding 重建 bool/interval/family membership。

6. `slot_binding` 契约：
   - `_slot_binding` 当前记录的是 coordinate slot 的 active/x/y/mode/family 与 footprint binding（`src/models/exact_coordinate_master.py:3412-3420`, `3528-3560`）。
   - C1 `p_k` 不是 coordinate slot，不进入 `_slot_binding`，避免污染 replay/cut 期对 slot key 的假设。新增 binding 命名空间只服务 clone/no-overlap/extract，不暴露为 residual slot。
   - `add_power_pose_exclusion_cut()` 的 F7 seam 依赖 powered pose literal、mandatory group mapping、pole pool coverer table，而不是 pole slot literal；它已有空 condition lit 拒绝、coverer table 检查和 coverage-cell 校验（`src/models/exact_coordinate_master.py:7362-7445`）。C1 改名空间不得放宽这些 gate。

7. cov 通道与 witness cell：
   - 构造 `cov[cx,cy]` BoolVar，若无 coverer 则 `cov == 0`，否则 `cov <= sum(p_k covering cell)`；只有 `<=` 方向是有意设计，`target == 1` 会反推至少一个覆盖杆，且不会虚报覆盖（`00_design_decision.md:22`; review确认 `02_c1_patch_codex_review.md:28-32`; prototype `c1_encoding_patch.py:168-185`）。
   - 对每个 powered slot，建 `wx/wy` 钳在 footprint bbox 内，`flat = wx + wy * grid_w`，`AddElement(flat, cov, target)`，active slot 走 `OnlyEnforceIf(active)`，mandatory powered 走硬约束（prototype `c1_encoding_patch.py:187-214`; footprint helper `src/models/exact_coordinate_master.py:2528-2540`）。
   - 当前 production `_supports_rectangular_power_coverage()` 会校验 powered footprint 与 expected coverage rectangle 的一致性（`src/models/exact_coordinate_master.py:5266-5300`）。C1 witness-cell 仅在矩形前提 sound；非矩形不能走 bbox witness，必须 fail-closed 或显式落回经 reseal 的旧/table 语义。
   - 无 pole pool 时保持当前 fail-closed 语义：optional powered 禁用，mandatory powered infeasible（current path `src/models/exact_coordinate_master.py:5952-6034`; prototype `c1_encoding_patch.py:151-166`）。

8. 容量族与杆数上界：
   - `_prepare_power_pole_families()`/precompute 当前按 pose/family 构建 family membership 与 lookup rows（`src/models/exact_coordinate_master.py:2084-2114`, `2160-2258`），C1 可直接把 pose-level family membership 编译为 `family -> [p_k]`。
   - `power_pole_family_count_vars[family] == sum(p_k in family)` 后，继续喂给 per-template capacity inequalities（`src/models/exact_coordinate_master.py:6417-6465`）。
   - selected-powered dominance bound 当前只在 residual pole slots 存在时建立（`src/models/exact_coordinate_master.py:6357-6405`）。C1 移除 residual slots 后必须补等价 bound；这是 v1 原型修复 4（`c1_encoding_patch.py:216-237`）和 review finding 6（`02_c1_patch_codex_review.md:34-36`）。
   - `EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE` 仍保持 certified unsafe：源码注释已说明 override 可能造成假 INFEASIBLE（`src/models/exact_coordinate_master.py:2100-2113`），benders env guard 也把它视为 certified domain tightening（`src/search/benders_loop.py:950-984`, `1328-1420`）。

9. build_stats / representation：
   - 现有 `power_coverage` stats 被 `_master_search_summary()` 读取并外显 representation、encoding、powered_slots、pole_slots、cover_literals、witness_indices、element_constraints、radius 等字段（`src/search/benders_loop.py:4237-4480`）。
   - C1 建议使用稳定命名：`representation="coordinate_geometric"`，`encoding="c1_pose_bool_cov_channel_v1"`，同时增加非破坏性字段如 `pole_pose_bools`、`cov_channel_literals`、`constant_pole_intervals`、`dominance_bound_terms`。不要删除已有 summary 消费字段。
   - `_finalize_build_stats()` 当前记录 interval count、slot counts、pose bool literal count 等总体统计（`src/models/exact_coordinate_master.py:6810-6851`），C1 应把 `p_k` 计入可审计字段，避免 production log 看起来仍是旧 witness。

10. `extract_solution()`：
   - 现有 extraction 只遍历 mandatory、required optional、residual optional coordinate slots（`src/models/exact_coordinate_master.py:6864-6915`），v0 review 已指出 C1 free 解会缺 power_pole entries（`02_c1_patch_codex_review.md:38-42`）。
   - 对每个 selected `p_k` 输出 `instance_id="pose_optional::power_pole::<pose_id>"`，`facility_type="power_pole"`，`pose_id` 与 `bound_type="exact_pose_optional"`；这些字段必须满足 terminal authorization helper（`src/search/exact_campaign.py:937-967`）。
   - 输出 entries 不应携带新的 terminal 不认识字段；terminal final result 对未知字段是 fail-closed（`src/search/exact_campaign.py:2581-2683`）。

11. v1 原型四修复的原生化验收：
   - clone/bind/no-overlap interval 不丢：见 review BUG 1（`02_c1_patch_codex_review.md:14-18`）。
   - 池完整性逐点 fail-closed：见 BUG 2（`02_c1_patch_codex_review.md:20-22`）。
   - required/mandatory power-pole 不混合语义：见 BUG 3（`02_c1_patch_codex_review.md:24-26`）。
   - selected-powered dominance bound 保留：见 finding 6（`02_c1_patch_codex_review.md:34-36`）。
   - 额外必须补：selected `p_k` extraction，见 review observation（`02_c1_patch_codex_review.md:38-42`）。

## 三、解级 dominance 剪杆步的落位(extract 之后、proposal 之前;引理写进 proof obligations 的义务条目草案)

落位原则：剪杆是 solution-level normalization，不是 master 可行域收缩。它必须发生在 `extract_solution()` 之后，任何 candidate/proposal sink 之前；若某配置先注入 synthetic power poles，也必须注入后再剪。

1. 必要性：
   - 对抗审查阻断项已指出 master 到 seal 之间没有冗余杆剪除步，terminal verifier 要求每杆至少是某 powered 的唯一覆盖者，否则 `unforced_power_pole_instance` fail-closed（`00_design_decision.md:100-104`, `118-120`; terminal check `src/search/exact_campaign.py:1227-1253`）。
   - 批 0 b0_4r 解 `unforced=0`，说明 C1 常能自发给极简杆集，但剪杆仍必须在链上作为通用封口（`README.md:9-14`, `44-49`）。

2. 生产落点：
   - 主落点放在 `src/search/benders_loop.py`，紧跟 `master.extract_solution()`（`src/search/benders_loop.py:5180-5189`）。
   - 如果 `_run_power_placement_subproblem()` 路径启用并注入 poles（当前 certified env 禁用，但代码有 hook），剪杆应在该注入之后（`src/search/benders_loop.py:5205-5233`）。
   - 最终返回 `RUN_STATUS_CERTIFIED, solution` 前必须保证 solution 已剪过（`src/search/benders_loop.py:5375-5383`, `7000-7017`）。
   - `src/search/outer_search.py` 的 CERTIFIED 写入点只接收已剪 solution；可加防御性断言/telemetry，但不要在多个 sink 重复实现算法（worker path `src/search/outer_search.py:2470-2493`; serial path `2673-2741`; final result builder `855-887`）。

3. 算法草案：
   - 输入：placement solution、facility pools、templates、grid dimensions。
   - 复用 terminal verifier 同语义：计算所有 selected power_pole 的 `power_coverage_cells` 与所有 needs-power facility 的 occupied cells（`src/search/exact_campaign.py:1192-1207`），检查每个 powered facility 至少被一个 pole 覆盖（`1227-1242`）。
   - 迭代删除任意不是任何 powered facility 唯一覆盖者的 pole；每删一杆后重算 coverer sets，直到所有剩余杆都是某 powered 的唯一覆盖者，或无 pole 可删。
   - 剪后立即用同语义 checker 复验 coverage；若 malformed pose/unknown entry/coverage 破坏，fail-closed 为 UNKNOWN/UNPROVEN，不产 CERTIFIED candidate。

4. dominance 引理草案：
   - 删除非唯一覆盖杆不会破坏供电：被删杆不是任何 powered 的唯一 coverer，删除后每个原已覆盖 powered 仍有其他 coverer。
   - 删除杆只释放 occupied cells，不会制造 overlap；power_pole 本身不属于需电设施，terminal powered 集按 template `needs_power` 收集（`src/search/exact_campaign.py:1206-1207`）。
   - power_pole 不参与 binding/routing 端口责任；这点必须作为 proof obligation 的显式前提并由测试覆盖。对抗审查已要求不能默认这一点（`00_design_decision.md:84-86`）。
   - ghost rect、lex objective、mandatory/required non-pole placements 不变，因此任意可行 solution 可正规化到同一 lex 值的 terminal-acceptable solution。

5. proof obligations 条目草案：
   - 新 ID 建议：`PO-CERTIFIED-POWER-POLE-DOMINANCE-NORMALIZATION`。若选择并入 `PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS`，仍需在 checker required tests 中列出专门测试；新增 ID 则要更新 `REQUIRED_OBLIGATION_IDS`（`scripts/check_p1_2_proof_obligations.py:87-104`）。
   - evidence_paths：`src/search/benders_loop.py`、`src/search/outer_search.py`、`src/search/exact_campaign.py`、`src/models/exact_coordinate_master.py`、新增 dominance tests、本文档。
   - required_tests 草案：冗余杆被删且 coverage 保持；每杆唯一时 no-op；删除链需迭代到 fixed point；malformed/unknown pose fail-closed；candidate record/proposal sink 无法绕过未剪 solution；lex value 不变；terminal verifier 全段通过。
   - checker 会验证 evidence paths 和 test symbols 存在（`scripts/check_p1_2_proof_obligations.py:3070-3110`），语义字段改动要更新 semantic projection digest（`3292-3351`）。

## 四、等价性测试计划(新旧编码小实例可行集+lex 值一致性/池完整性 fail-closed/内存条款测试)

1. C1 vs old witness 小实例等价：
   - 构造 4x4/5x5/小 70 子域 fixtures，枚举或穷举多组 powered footprint、ghost anchor、pole pool，比较旧 witness 与 C1 的可行集投影和 lex 最优值。
   - 覆盖 mandatory powered 硬约束、optional powered active guard、无 coverer 禁用、ghost no-overlap、capacity family count。
   - 批 0 已有 toy equivalence PASS 作为先例，但那是 monkeypatch 测量材料，不可替代 production 单测（`README.md:42`; prototype warning `README.md:3-5`）。

2. 池完整性 fail-closed：
   - 缺 anchor、重复 anchor、pose anchor 与 occupied bbox 不一致、`power_coverage_cells` 与 radius/rect 不一致，全部应 build-time fail-closed。
   - 测试直接对应 C1 等价性引理（`00_design_decision.md:22`, `116`）与 review BUG 2（`02_c1_patch_codex_review.md:20-22`）。
   - 现有 production geometry contract 已断言 `power_pole` pose pool 数量为 `69*69`，但批 1 要升级到集合/内容校验，而不只是数量。

3. clone/bind/no-overlap regression：
   - 复现 v0 bug：build exact core 后 clone/ghost overlay，ghost 覆盖唯一 pole pose 时必须 INFEASIBLE 或禁止该 `p_k`，不得返回与 ghost 重叠的 FEASIBLE。
   - 验证 `export_core_binding()` 中 C1 binding 完整，`bind_from_core()` 重建后 `_core_x/_core_y_intervals` 含所有 selected-capable pole intervals。bug 来源见 `02_c1_patch_codex_review.md:14-18`，生产 bind/export 面见 `src/models/exact_coordinate_master.py:3528-3645`。

4. required power-pole path：
   - 扩展 `src/tests/test_exact_coordinate_protocol_bounds.py` 中 required pose optional power_pole 场景（现有测试面 `src/tests/test_exact_coordinate_protocol_bounds.py:117-177`），验证 C1 下 required count 进入 `p_k` 下界/等式、extract entries authorized、terminal verifier 通过。
   - 确认不存在“required 坐标杆 + residual p_k 池”双重建模。

5. build_stats / telemetry compatibility：
   - 断言 `build_stats["power_coverage"]` 新 encoding 出现，旧 summary 字段仍可被 `_master_search_summary()` 读取（`src/search/benders_loop.py:4237-4480`）。
   - 断言 interval count、pose bool count、pole count 与 C1 pool/selection 一致（`src/models/exact_coordinate_master.py:6810-6851`）。

6. extract_solution / terminal verifier：
   - 对 selected `p_k` 的 solution entries 调用 terminal authorization helper 覆盖的格式（`src/search/exact_campaign.py:937-967`）。
   - 用 terminal verifier 的 coverage + unforced 全段作为剪杆后验收（`src/search/exact_campaign.py:1083-1255`）。

7. attach seam regression：
   - F7 helper/master equivalence：C1 后 `add_power_pose_exclusion_cut()` 仍使用 pole pool coverer table，拒绝缺 coverer 表、空 condition_lits、无 coverage 交集的 cut（`src/models/exact_coordinate_master.py:7362-7445`）。
   - F1/F5/F6/F7 attach admission gate：更新 existing cut framework attach tests，确保所有 cut 仍经过 integrity validator、family validator、step_6/7/8（`src/search/benders_loop.py:7734-7914`）。
   - F5 adapter TCB：增加 proof-obligation test 证明 adapter 不再是 out-of-scope future phase，且 routing-aware binding env 开启时返回 no-cut（adapter behavior `src/search/f5_binding_empty_domain_adapter.py:66-117`）。

8. env guard / canonical defaults：
   - 更新 certified env guard tests：未知 `EXACT_*` fail-closed、canonical power witness env 默认锁、非 canonical 值在 certified 下拒绝（`src/search/benders_loop.py:985-1021`, `1328-1420`; required tests机制 `scripts/check_p1_2_proof_obligations.py:177-197`）。
   - 若保留旧 witness env 对照，必须有 test 证明 certified 不能通过未锁 env 切到非 canonical witness。

9. 内存条款测试：
   - 单元层：验证 production profile/wrapper 把 C1 certified master worker 限制在 w6 或更保守，并记录 `EXACT_SUBPROBLEM_MAX_MEMORY_MB` 只是 CP-SAT 软限制，不当作 RSS 硬帽（`src/models/cp_sat_worker_config.py:140-149`）。
   - 集成/manual lane：w6 full solve 或 replay 作为 acceptance；w12/w24 不作为默认 CI，但记录 cgroup 硬帽命令与 OOM 预期，避免误把 worker 上探并入 certified 默认（batch0 evidence `README.md:39-41`, `59-66`）。

## 五、reseal 全集清单(触碰的 sealed 文件、pins、allowlist、canonical env 面、EXACT_* 三件套)

1. sealed source pins：
   - `src/models/exact_coordinate_master.py`：C1 model surgery 主文件。它在 V99 floor 中是 `p1_2_certified_path`（`scripts/check_p1_2_proof_obligations.py:12795`），manifest source pin 在 `data/proof_obligations/p1_2_proof_obligations.json:1299-1310`。
   - `src/search/benders_loop.py`：canonical env、summary、dominance normalization、attach proof surface。V99 floor `scripts/check_p1_2_proof_obligations.py:12814`，source hash floor `12971`，manifest pin `data/proof_obligations/p1_2_proof_obligations.json:1559-1574`。
   - `src/search/outer_search.py`：若加入防御性验证或 proof summary 字段，属于 candidate sink replay authority evidence path（`data/proof_obligations/p1_2_proof_obligations.json:653-662`）。
   - `src/search/exact_campaign.py`：原则上只作为 verifier；若抽 helper 或改 terminal surface，V99 floor `scripts/check_p1_2_proof_obligations.py:12822`，manifest pin `data/proof_obligations/p1_2_proof_obligations.json:1691-1717`。

2. proof obligations manifest：
   - 新增/更新 C1 等价性、pool completeness、dominance normalization、F5 adapter TCB 条款。
   - 更新 evidence_paths、required_tests、source_sha256。manifest semantic projection hash 在 `data/proof_obligations/p1_2_proof_obligations.json:7`，checker 会复核 semantic digest（`scripts/check_p1_2_proof_obligations.py:3292-3351`）。

3. checker 自身：
   - `scripts/check_p1_2_proof_obligations.py` 是 named TCB boundary；合法 reseal 必须改 checker code，不只改 JSON（`scripts/check_p1_2_proof_obligations.py:12737-12743`）。
   - 更新 `REQUIRED_OBLIGATION_IDS` / required tests（`87-104`, `3070-3110`）、V99 classification floor（`12773-12822`）、source hash floor（`12971-12972`）。

4. canonical env 面：
   - `_CERTIFIED_POWER_WITNESS_CANONICAL_ENV_DEFAULTS` 当前锁 witness/family/coverage/interval env canonical 值（`src/search/benders_loop.py:985-1021`）；C1 默认改变 representation 后必须更新 canonical defaults 或删除旧 witness-only 锁。
   - `_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES` 已把 pose-bool master、pole slot override、lazy power、power placement subproblem、cut framework attach 等列为 certified unsafe（`src/search/benders_loop.py:950-984`）。本批不得通过 env 打开这些面。
   - EXACT_* 三件套：known name/allowlist、canonical lock、tests 必须同步；未知 `EXACT_*` fail-closed 在 `src/search/benders_loop.py:1328-1420`。

5. strong-status allowlist：
   - 若 `outer_search.py`/`exact_campaign.py` 或任何 strong-status writer hash 变化，更新 `data/proof_obligations/strong_status_write_allowlist.json` 并更新 checker byte pins。allowlist policy 在 `data/proof_obligations/strong_status_write_allowlist.json:3-5`，checker enforcing path 在 `scripts/check_p1_2_proof_obligations.py:4543-4600`。

6. F5 adapter TCB 登记：
   - 当前 floor 把 `src/search/f5_binding_empty_domain_adapter.py` 标为 `out_of_scope_future_phase3b`（`scripts/check_p1_2_proof_obligations.py:12815`），但外审要求登记 TCB。
   - reseal 时把 adapter 的 frozen-artifact-only liftability 语义写进 obligation，并更新 source hash floor（当前 hash pin在 `scripts/check_p1_2_proof_obligations.py:12972`）。adapter 自述和行为依据见 `src/search/f5_binding_empty_domain_adapter.py:1-24`, `66-117`。

7. reseal 顺序建议：
   - 先改模型/normalization/tests。
   - 跑 targeted tests 与 proof checker，确认语义稳定。
   - 再更新 manifest source pins / semantic digest。
   - 最后更新 checker V99 floor、strong-status allowlist pins，并重跑 `scripts/check_p1_2_proof_obligations.py` 与 strong-status allowlist checker。

## 六、风险与回滚(旧 witness 编码是否保留为 env 对照及其白名单代价;w6 内存条款怎么进生产配置)

1. 旧 witness 编码是否保留：
   - 推荐 certified 默认不保留 runtime env 回退。理由：旧 witness 连“钉入已知可行布局再搜杆”都 `UNKNOWN @600s`（`README.md:51-57`），作为 production fallback 实用价值低；保留 env 会扩大 EXACT_* allowlist/canonical/test/reseal 面。
   - 若保留旧 witness 作为研究对照，只能是 certified unsafe 或明确 canonical-locked 的有限值。任何 `EXACT_POWER_COVERAGE_*` env 让 certified 切换语义，都必须进入 `_CERTIFIED_POWER_WITNESS_CANONICAL_ENV_DEFAULTS`、known env、unsafe/canonical lock、tests（`src/search/benders_loop.py:985-1021`, `1328-1420`）。
   - 回滚优先级：把 C1 model surgery 单独提交，出现性能/内存/semantic regression 时 revert 该提交与 env pins；解级 dominance normalization 是 representation-independent，可独立保留，前提是 proof obligation 已通过。

2. 内存风险：
   - C1 w12 OOM 两连，w24 cgroup 42G 在解附近出现 3 秒 +26GB 尖峰，w6 安全（`README.md:29-41`, `59-66`）。这不是稳态 RSS 问题，不能靠普通 log 平均值判断。
   - 生产配置应把 certified C1 master workers 限到 w6 或更低，并在 campaign wrapper 使用 cgroup/RSS 硬帽。`EXACT_SUBPROBLEM_MAX_MEMORY_MB` 是 CP-SAT soft cap，不代表 OS RSS hard cap（`src/models/cp_sat_worker_config.py:140-149`）。
   - 验收门不应要求 w12/w24 通过；worker 上探只能在单独 perf lane，以 cgroup 硬帽和 OOM 预期记录为准。

3. 语义风险：
   - 池完整性断言若漏校验，会把 artifact drift 变成假 INFEASIBLE，直接威胁穷尽性（`00_design_decision.md:68-70`, `116`; review `02_c1_patch_codex_review.md:20-22`）。
   - required/mandatory power-pole 若仍走 prototype fail-closed，会破坏 production 测试覆盖；若走混合语义，则可能假 FEASIBLE/假 INFEASIBLE（`02_c1_patch_codex_review.md:24-26`）。
   - 非矩形 footprint 若误走 witness-cell bbox，是欠约束；必须由 `_supports_rectangular_power_coverage()` gate 防住（`src/models/exact_coordinate_master.py:5266-5300`）。
   - C1 intervals 若 clone/bind 丢失，会复现 v0 假 FEASIBLE（`02_c1_patch_codex_review.md:14-18`）。

4. attach 链风险：
   - C1 不能让 optional pole solution entries 成为 `_framework_target_poses()` 的未验证 target；该函数只应从 solution/group mapping 解析 target poses（`src/search/benders_loop.py:7667-7709`）。
   - 所有 F1/F5/F6/F7 cut 必须继续走 `_maybe_attach_framework_cuts()` 的 validated admission gate（`src/search/benders_loop.py:7734-7914`）。本批不扩大 oracle surface。

5. rollback 触发条件：
   - 任一小实例 C1 vs old witness 等价失败。
   - clone/ghost no-overlap regression 失败。
   - terminal verifier 对剪杆后 solution 失败。
   - certified env guard 无法 fail-closed unknown/noncanonical `EXACT_*`。
   - w6 replay 出现不可接受 OOM 或稳定 UNKNOWN regression，且不能通过 worker/parameter clause 收敛。

## 七、分批提交计划(每批的验收门)

1. 批 1A：C1 原生骨架与 pool/interval binding
   - 内容：新增 `p_k` 池、pool completeness fail-closed、constant intervals、export/bind、no-overlap clone regression；旧 witness 仍可作为内部对照但不进 certified 默认。
   - 验收：pool fail-closed tests、clone/ghost regression、small no-overlap fixtures、`pytest` targeted；不得改 proof pins。
   - 行号锚点：pole slot machine `src/models/exact_coordinate_master.py:3329-3447`，bind/export `3528-3645`，review BUG 1/2 `02_c1_patch_codex_review.md:14-22`。

2. 批 1B：cov channel / witness cell / capacity / extraction
   - 内容：替换 coverage witness 为 C1 cov 通道；补 selected-powered bound、family count vars、build_stats、extract_solution selected `p_k` entries；required power-pole 原生化。
   - 验收：C1 vs old witness 小实例可行集与 lex 值一致；required pole tests；terminal verifier coverage pass；build_stats summary compatibility。
   - 行号锚点：coverage dispatch `src/models/exact_coordinate_master.py:5952-6034`，capacity `6357-6465`，extract `6864-6915`，terminal verifier `src/search/exact_campaign.py:1083-1255`。

3. 批 1C：解级 dominance normalization
   - 内容：在 `benders_loop.py` extract 后、candidate sink 前加入剪杆 helper 与 proof_summary counters；`outer_search.py` 只作防御性验证/telemetry（如需要）。
   - 验收：冗余杆删除、fixed point、malformed fail-closed、lex unchanged、terminal verifier 全段通过、candidate/proposal sink 不可绕过。
   - 行号锚点：extract path `src/search/benders_loop.py:5180-5189`，return path `5375-5383`/`7000-7017`，outer sink `src/search/outer_search.py:2470-2493`/`2673-2741`。

4. 批 1D：canonical env / attach gate / F5 TCB reseal
   - 内容：更新 C1 certified 默认 env 面、EXACT_* allowlist/canonical tests、attach regression tests、F5 adapter TCB classification。
   - 验收：unknown `EXACT_*` fail-closed；noncanonical witness env 拒绝；F1/F5/F6/F7 attach 全部经过 validated gate；F5 adapter classification/source pins 更新。
   - 行号锚点：canonical env `src/search/benders_loop.py:985-1021`，env guard `1328-1420`，attach gate `7734-7914`，F5 adapter floor `scripts/check_p1_2_proof_obligations.py:12815`。

5. 批 1E：proof obligations / source pins / strong-status allowlist reseal
   - 内容：更新 manifest obligations、required tests、source hashes、semantic digest、checker V99 floor、必要的 strong-status allowlist pins。
   - 验收：`scripts/check_p1_2_proof_obligations.py` 通过；strong-status allowlist checker 通过；required tests symbols 都存在；source hash floor 与 manifest 一致。
   - 行号锚点：manifest evidence/tests `data/proof_obligations/p1_2_proof_obligations.json:620-665`，checker required tests `scripts/check_p1_2_proof_obligations.py:3070-3110`，named TCB boundary `12737-12743`。

6. 批 1F：生产 replay 与内存条款
   - 内容：以 w6/cgroup 硬帽运行 b0_4r 等价 replay 或完整 certified smoke；记录 wall time、RSS、proof_summary、terminal verifier；把 worker 上限写入 production profile/wrapper。
   - 验收：w6 不 OOM，剪杆后 solution terminal verifier 通过，proof artifacts 可重放；w12/w24 只做 optional perf lane，不作为 release gate。
   - 行号锚点：batch0 w6/w12/w24 evidence `README.md:29-41`, `59-66`，worker config caveat `src/models/cp_sat_worker_config.py:140-149`。

## 九、1A 双审移交 1B 的发现（2026-07-10 凌晨，opus+codex 双审产出）

1A 内放行、1B 落地覆盖约束前**必须**处理的三项（放行论证：1A 无覆盖约束，杆只进 no-overlap/Σ≤cap/family count，池缩水最多少几个杆 bool，不产生假判决；1B 覆盖强制选杆后同样的缺陷会变成假 INFEASIBLE=穷尽性威胁）：

1. **池完整性校验是自证式的（opus CONCERN-1）**：`_validate_c1_power_pole_pool` 的期望格阵来自 `_template_full_mode_rect_domains`，而该域本身从同一个池的 anchor min/max 现算——「整体均匀缩小但仍完整的格阵」（如只覆盖 [0,50]²）会通过。1B 修法：把独立的域 bbox pin（或 69×69 计数断言）纳入 C1 build 路径本身，不依赖外部 geometry contract。
2. **空池静默放行（opus NOTE-2）**：校验与建变量对空池都 `return`。1B 需保证「存在 mandatory powered 但池空」在 C1 路径 fail-closed（与现 witness 语义对齐：optional powered 禁用、mandatory powered infeasible）。
3. **单 anchor 单 pose 隐含假设（opus NOTE-3）**：多 mode 杆会被误判为重复 anchor → fail-closed。方向安全（宁拒不放），但若工件演化出现多朝向杆，C1 拒建——1B 时显式记录该假设为引理或解除。

（1A 内已修：codex 三 BUG——binding 缺键 fail-closed、anchor 严格解析、coverage cells 逐点校验；opus NOTE-5 测试加强。）
