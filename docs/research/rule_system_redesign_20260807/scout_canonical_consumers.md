# 侦察报告：canonical_rules.json 真实消费图（2026-08-07）

> 只读侦察转述，**非权威**——承重引用前回源核对 file:line。fp-derivation 席派出、主线程存档。
> ⚠ **已知订正（fp-derivation 回源核出）**：本报告底表「routing_rules 全死」**过强不成立**——
> `src/rules/models.py:91` 有 `RoutingRulesConfig.layers` 且 `:79` 把 `elevated: Literal[1]=1`
> 钉在 pydantic；`src/rules/semantic_validator.py:50-54` 读 `bridge_mechanics`。正确表述=
> 「无认证/求解运行期消费者，但 pydantic 结构钉死 + 测试期语义校验在消费」。layers 搬家要连带改模型。
> 另 `semantic_validator.py:50` 的报错文案把**已退役**的桥读法写成「冻结真理」（布尔同、理由反）——
> 活标本，已入 FIRST_PRINCIPLES_DESIGN。

## 0. 底线表（含上述订正）

| 顶层键 | 真实读取深度 | 判定 |
|---|---|---|
| `globals` | 叶层（grid、empty_rectangle.objective/min_side、tick、belt_capacity、port_max_throughput） | **热**，认证路径 |
| `facility_templates` | 叶层（dimensions/needs_power/rotatable/is_solid_z/port_rule/core_limits/power_coverage_radius/placement_rule 全字段） | **热**，认证+生成器 |
| `recipes` | 叶层全 4 字段 | **热**，仅构建期（认证 solve 路径吃的是 data/preprocessed 派生物） |
| `commodity_metadata` | 叶层（source_kind/sink_kind/cycle_group） | **热**，认证 binding |
| `production_targets` | 叶层 | 仅构建期 |
| `metadata` | 仅 `version`（→内存审计串） | 近死 |
| `routing_rules` | pydantic 结构钉死+测试期校验（见订正） | 无运行期消费者、非全死 |
| `semantics` | **仅 1 子树被读**（power_coverage_stencil，被 1 个测试 pin 5 个叶字段） | ~93% 子树零读者、非 100% |
| `globals.logistics.machine_min_clearance_cells` | 仅 pydantic | 死（PROJECT_LOCK.md:161-162 自记） |
| `globals.empty_rectangle.emptiness*` | 仅 schema/pydantic | 死 |

全文件字节 sha 钉死（contract:100、preflight:63），故「描述性」键的修改仍改认证 hash——hash 在两个源码常量注册表里承重。

## 1. 载入点

**A. 认证 solve 路径（字节快照，hash 钉死）**：`src/search/exact_campaign.py:436`（read_once 原子快照；EXACT_HASH_FILES :278-286 含 canonical，OPTIONAL :287-295 含 plan；路径出 contract:89-95）→ `src/search/benders_loop.py:2547-2553` → `src/models/master_model.py:2283`（`load_project_data_from_texts`，**无 schema/pydantic 校验**，只有 hash 门）。另五个直接磁盘读：exact_campaign :744/:766/:843/:1412/:1439；L0 verifier 副本 pr2_l0_artifact_core :509/:529/:607/:1224/:1256 及 :627（candidate_placements 字节级重推）；pr2_l0_fixed_witness_core:2082；binding_subproblem :342/:849；master_model:2279（legacy）。

**B. 预处理/构建期**：preprocess_context :629/:640（**唯一 JSON-schema 校验点** :611-623）；placement_generator :474（也校验 :463-466）；material_skeleton :45；material_skeleton_verifier :73。

**C. 适配器/查看器（非认证）**：industrial_planner commodity_resolver :17/:70-71（lru 缓存）→ recipe_matcher :74-76、throughput_audit :155；render 四处；normalized_catalog :103；highs_candidate_evaluator :85。

**D. checker/侧车**：certside sidecar frontend :165（独立重推 operation profiles）、parity_check :24；preflight/contract 仅 hash；cc_memory_vnext pre_tool_risk_gate :84-85（冻结名单）。

**E. 测试实文件读**：test_rules :29；test_helpers_power_cover_stencil :97-107；test_w0_g1_audit :447；test_commodity_throughput :113；test_material_skeleton :103；test_p1_2_fix_5 :119；test_band22_registration_driver_v2 :25。

**F. PoC 脚本**：scip_phase4 :37、highs_phase3 :37、build_industrial_planner_full_demand_fixture :162/:671、b_design_v2_exit_criteria :70。

## 2. 逐键要点

- **`semantics`**：唯一真实读者=`src/tests/cuts/test_helpers_power_cover_stencil.py:100`（pin power_coverage_stencil 的 radius=5/anchor 2×2/axis_aligned_square/12×12 五叶）。其余 13 子树（_note/axiom_kernel/boundary_placement/routing_cross_junction/mixed_commodity_flow/connectivity_quantifier/machine_min_clearance/warehouse_bridge_exclusion/protocol_storage_box_wireless/power_source_note/item_admission_port_exclusion/rate_lemma_scope/port_commodity_scope）**零代码读者**（只被 .md 散文与 power_cover.py docstring 引用；power_cover.py 硬编码 `_POLE_SIZE=2`、radius 走参数，不读文件）。结构上 semantics 被「准入不被检视」：`src/rules/models.py:185` `Optional[Dict[str,Any]]`，schema `additionalProperties:true` 非 required——两个校验器只要求键可声明、都不约束内容。
- **`metadata`**：仅 version 被读（preprocess_context :175/:222 → 内存审计字段；normalized_catalog :193/:197）。不进任何 data/preprocessed 工件（generic_io_requirements 的 metadata 块硬编码在 demand_solver:194-202）。
- **`globals`** 最深最热：grid 十余处（master/highs/scip/cpsat_minimum/checkpoint_free_evaluator/outer_search/benders/campaign/L0 双 core）；objective+min_side 走 campaign :776-780 与 L0 :539-543 → outer_search :1849、frontier_core :142-144/:328-346；tick→preprocess_context :164；belt→:165+sidecar frontend :113；port_max_throughput 仅 throughput_audit :158；machine_min_clearance_cells 死；emptiness* 死。

## 3. preprocess_plan.json 消费

metadata.version/description→preprocess_context :176/:215-223；cycle_groups→:206→:850-857→_solve_cycle_group_exact（:664+）；utility_operations→:210→:876-889 + binding_subproblem :112-137（只读 generic_input_slots）+ sidecar frontend :142-154/real_sample :39-41；整文件→binding_subproblem :55/:158 与 :169+（certified 快照变体，接线 benders_loop :2564-2574）+ sidecar parity_check :25；additive-only 双闸=schema 根 closed + PLAN_CANONICAL_OVERRIDE_KEYS（preprocess_context :25/:178-186；sidecar frontend :31/:108-110 独立镜像）。$schema 无人读。

## 4. data/preprocessed 派生链（编辑 canonical 后的再生序）

三个独立生成入口、无一键脚本：`python src/preprocess/demand_solver.py`（→4 需求工件）→ `python src/preprocess/instance_builder.py`（依赖 machine_counts）→ `python src/placement/placement_generator.py`（→candidate_placements，~1.5s/54MB）→（可选）`python src/preprocess/material_skeleton.py`。之后 pin 更新两个源码常量注册表（contract :97-107、preflight :63-66），否则 artifact_hash_mismatch fail-closed。审计路径（不写 preprocessed）：`scripts/build_current_preprocess_context.py:203`（内存重生成+对冻结字节 diff，spec 19 :47-55）。验证器侧重推：pr2_l0_artifact_core :627（从冻结 canonical 字节重跑 generate_all_pools 断言 sha 相等）＋ material_skeleton_verifier :73。
