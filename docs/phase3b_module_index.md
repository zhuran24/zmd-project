# Phase 3B Module Index — 670 个文件的物理分类

**最后更新**: 2026-05-16

Phase 3B 优化期间 sprint / spike / audit / validator 产生了 **154 src + 264 tests + 252 scripts = 670 个**带 `phase3b_` 前缀的文件. 这份索引按主题 cluster 分类, 方便定位"哪些文件干嘛".

**重要**: 这些文件**没有物理重组**到子目录, 因为 import 路径变动 risk 太大. 索引只是逻辑分类. 真要找文件还是 `grep` / `ls scripts/build_phase3b_*` / `find src/search -name 'phase3b_*'`.

---

## 文件分布总览

```
src/search/phase3b_*.py            154 个 (运行时模块: probe / validator / audit / advisory guard)
src/tests/test_phase3b_*.py        264 个 (上述模块的测试)
scripts/build_phase3b_*.py         252 个 (生成 artifact: review packet / readiness check / scoreboard)

合计 670 个文件 (~95K LOC)
```

src/search/, src/tests/, scripts/ **三个目录文件名 1:1 对应** (大多数情况). 例如:
```
src/search/phase3b_coordinate_validation_assumption_core.py
src/tests/test_phase3b_coordinate_validation_assumption_core.py
scripts/build_phase3b_coordinate_validation_assumption_core.py
```

也就是说 670 个文件其实代表大约 **220-260 个独立 Phase 3B sprint 主题**, 三角形 (src + test + script) 一组.

---

## 主题 cluster 分类 (按文件数从多到少)

### 1. Checkpoint-free 评估 (95 src tests + 95 scripts ≈ 190 文件)

**主线 Phase 3B 优化路径**. 不动 checkpoint 直接评估 candidate, 提供 lite baseline + ablation patch / family bound formulation comparison / signature bucket optimization 实验.

代表文件:
- `test_phase3b_checkpoint_free_evaluator.py` — 主 entry
- `test_phase3b_checkpoint_free_eval_scoreboard.py` — 评分板
- `test_phase3b_checkpoint_free_family_bound_*` (multiple variants) — family bound formulation 实验
- `test_phase3b_checkpoint_free_signature_bucket_*` — signature bucket optimization 系列
  - 含 5 个永远 skip 的 Codex-era artifact 依赖测试 (有标注 docstring)
- `test_phase3b_checkpoint_free_candidate_shape_*` — candidate shape 维度实验

**子聚类**:
- `*_signature_bucket_powered_support_coverer_*` (15+) — 信号桶供能支撑覆盖
- `*_signature_bucket_template_footprint_*` (10+) — 模板足迹
- `*_signature_bucket_mandatory_region_*` (10+) — 强制区域统计
- `*_signature_bucket_tightening_*` (5+) — 收紧 pass

---

### 2. Coordinate validation 坐标有效性多维审计 (55 src + 55 tests + 55 scripts ≈ 165 文件)

各种维度 (assumption_core / equality_core / direct_equality / actual_path / row_domain / etc) 的**坐标对齐 + 几何有效性 audit**.

代表文件:
- `phase3b_coordinate_validation_assumption_core.py` — assumption-based 验证
- `phase3b_coordinate_validation_direct_equality_core.py` — direct equality 验证
- `phase3b_coordinate_validation_actual_path_equality_core.py` — 实际路径 equality
- `phase3b_coordinate_validation_field_channel_delta.py` — field channel delta

**子聚类**:
- `*_anchor119_row_domain_*` (15+) — anchor119 行域系列 (acceptance authorization 子链)
- `*_authorization_*_cover_note / instruction_packet / operator_handoff_bundle` — 多份"操作员交接" packet
- 各种 `*_assumption_core / equality_core / direct_equality / actual_path` 变体

---

### 3. Family bound 家族容量 (11 + 11 + 11 ≈ 33 文件)

设施 family-level 容量约束 audit / formulation 实验.

代表文件:
- `phase3b_family_bound_audit.py`
- `phase3b_family_bound_formulation_probe.py` — formulation 变体探针
- `phase3b_family_bound_parameter_probe.py`
- `phase3b_family_bound_semantic_audit.py`
- `phase3b_family_bound_solver_profile.py`

---

### 4. Grouped / Joined block_xy 几何分组 (6+6 grouped + 4+4 joined ≈ 20 文件)

(x, y) 坐标的 grouped 跟 joined 等价性 / 探针 audit.

代表文件:
- `phase3b_grouped_block_xy_candidate.py`
- `phase3b_grouped_block_xy_equivalence_oracle.py`
- `phase3b_joined_xy_sat_expansion_audit.py`

---

### 5. Anchor inventory / domain audit (6 + 6 + 6 ≈ 18 文件)

anchor (放置锚点) inventory 全面盘点 + dynamic coupling.

代表文件:
- `phase3b_anchor_constraint_inventory.py`
- `phase3b_anchor_differential_audit.py`
- `phase3b_anchor_domain_inventory.py`
- `phase3b_anchor_dynamic_coupling_audit.py`
- `phase3b_anchor_packable_pole_audit.py`

---

### 6. B5a localized evidence review (4+4+4 + 5+4+5 ≈ 26 文件)

B5a sprint 的局部证据 readiness / review packet / validator 链.

代表文件:
- `phase3b_b5a_localized_evidence_readiness.py`
- `phase3b_b5a_localized_evidence_review_packet.py`
- `phase3b_b5a_localized_evidence_review_state.py`
- `phase3b_b5a_localized_evidence_validator.py`
- `phase3b_b5a_blocker_pivot.py` — blocker pivot
- `phase3b_b5a_certification_contracts.py` (src only)
- `phase3b_b5a_certified_anchor_promotion_review_packet.py`
- `phase3b_b5a_coordinate_validation_reason_localization.py`
- `phase3b_b5a_gate_integration_marker.py`
- `phase3b_b5a_post_acceptance_blocker_summary.py`

---

### 7. Group packing 组装 precheck (5+5+5 ≈ 15 文件)

组级别 packing precheck + promotion spec.

代表文件:
- `phase3b_group_packing_ghost_only.py`
- `phase3b_group_packing_precheck_candidate.py`
- `phase3b_group_packing_precheck_promotion_spec.py`
- `phase3b_group_packing_proof_promotion.py`
- `phase3b_group_packing_soundness.py`

---

### 8. Forced anchor (5+5+2 ≈ 12 文件)

强制锚点 / proto reduction / model slice.

代表文件:
- `phase3b_forced_anchor_master.py`
- `phase3b_forced_anchor_model_slice.py`
- `phase3b_forced_anchor_proto_reduction.py`
- `phase3b_forced_anchor_presolve_profile_probe.py`
- `phase3b_forced_anchor_solver_matrix.py`

---

### 9. Anchor119 行域 guard (5+5+3 ≈ 13 文件)

Phase 3B 特定 anchor119 行域 (y=119 那个坐标) 防护 guard advisory.

代表文件:
- `phase3b_anchor119_guard_controls.py`
- `phase3b_anchor119_guarded_precheck_runtime.py`
- `phase3b_anchor119_guarded_precheck_spec.py`
- `phase3b_anchor119_mixed_lane_dp_crosscheck.py`
- `phase3b_anchor119_mixed_lane_tiling_verifier.py`

---

### 10. Start (compatibility / repair) (5+5+4 ≈ 14 文件)

Phase 3B startline freeze 的 compatibility + repair 链.

代表文件:
- `phase3b_start_compatibility.py`
- `phase3b_start_repair_evidence_surface.py`
- `phase3b_start_repair_portfolio_audit.py`
- `phase3b_start_repair_portfolio_sample_comparison.py`
- `phase3b_start_repair_profiler.py`

---

### 11. Power coverage encoding (4+4+4 ≈ 12 文件)

功率覆盖 witness encoding 实验.

代表文件:
- `phase3b_power_coverage_anchor_delta.py`
- `phase3b_power_coverage_core_blocker.py`
- `phase3b_power_coverage_witness_audit.py`
- `phase3b_power_coverage_witness_domain.py`

---

### 12. Signature monotonic forced label (3+4+3 ≈ 10 文件)

Signature 单调强制标签 precheck + 运行时.

代表文件:
- `phase3b_signature_monotonic_forced_label_audit.py`
- `phase3b_signature_monotonic_precheck_candidate.py`
- `phase3b_signature_monotonic_precheck_promotion_spec.py`
- `phase3b_signature_monotonic_runtime_precheck.py` (test only)

---

### 13. Pose order validation (3+3+3 ≈ 9 文件)

代表文件:
- `phase3b_pose_order_geometry_signature.py`
- `phase3b_pose_order_unknown_resolution.py`
- `phase3b_pose_order_validation_probe.py`
- `phase3b_greedy_pose_order_comparison.py`
- `phase3b_residual_pose_order_taxonomy.py`

---

### 14. Active guard 主动守卫 (3+3+3 ≈ 9 文件)

`phase3b_active_guard_block_xy_scale_equivalence.py`, `phase3b_active_guard_proto_shape_audit.py`, `phase3b_active_guard_residual_surface.py`

---

### 15. Mandatory core / region (3+3+1 ≈ 7 文件)

`phase3b_mandatory_core_encoding.py`, `phase3b_mandatory_core_matrix.py`, `phase3b_mandatory_rectangle_precheck_profiler.py`

---

### 16. AI sidecar (test 3 + scripts 5 ≈ 8 文件, src 没有运行时模块)

AI 数据集 + offline replay + shadow.

代表文件:
- `build_phase3b_ai_candidate_dataset.py`
- `build_phase3b_ai_dataset_v0.py`
- `build_phase3b_ai_offline_replay_v0.py`
- `build_phase3b_ai_offline_replay_readiness.py`
- `build_phase3b_ai_order_shadow.py`

---

### 17. 单文件 sprint (一对一对应, 各 1-3 个文件)

下面这些 cluster 每个只有 1-3 个文件, 完整 grep 才能掌握:

- **B5 anchor sprint** (1+1): `phase3b_b5_anchor_sprint.py`
- **Cover choice / literal**: `phase3b_cover_choice_profile_comparison.py`, `phase3b_cover_literal_scale_estimate.py`
- **Protocol target / witness** (2+2+2): `phase3b_protocol_target_channel_slot_audit.py`, `phase3b_protocol_witness_prefix_audit.py`
- **Direct equality** (2+2+3): `phase3b_direct_equality_core_exchange.py`, `phase3b_direct_equality_core_geometry.py`, `phase3b_direct_equality_final_core_verifier.py` (script only)
- **Same X capacity / strip fixed** (1+2+1): `phase3b_same_x_capacity_anchor_sweep.py`, `phase3b_same_x_strip_capacity_precheck.py`
- **Residual optional / pose order** (2+2+2): `phase3b_residual_optional_encoding.py`, `phase3b_residual_pose_order_taxonomy.py`
- **Failed anchor inventory** (1+1+1): `phase3b_failed_anchor_inventory.py`
- **Zero branch / order independent**: `phase3b_zero_branch_unknown_triage.py`, `phase3b_order_independent_predicate_scan.py`
- **Y unique local hypothesis**: `phase3b_y_unique_local_hypothesis.py`
- **Coordinate group precheck candidate**: `phase3b_coordinate_group_precheck_candidate.py`
- **Power capacity GVI audit**: `phase3b_power_capacity_gvi_audit.py`
- **Power-protocol interaction** (一个大文件: 2763 行): `phase3b_power_protocol_interaction.py`
- **Selected block equivalence**: `phase3b_selected_block_equivalence.py`
- **Full forced hint field family delta**: `phase3b_full_forced_hint_field_family_delta.py`
- **Pre-master profiler**: `phase3b_pre_master_profiler.py`
- **Presolve log comparison**: (test/script only) `presolve_log_comparison.py`
- **Runtime group packing**: `phase3b_runtime_group_packing.py`
- **Signature region equivalence audit**: `phase3b_signature_region_equivalence_audit.py`
- **Campaign repair / triage**: `phase3b_campaign_repair.py` (src), `test_phase3b_campaign_triage.py` (test only)
- **Operating profile** (1+1+1): `phase3b_operating_profile.py`
- **Long-run preflight** (1+1+1): `phase3b_long_run_preflight.py`
- **Short-run readiness pack** (test/script only): `*_short_run_readiness_pack.py`
- **Priority / affinity manifest** (test/script only): `*_priority_affinity_manifest.py`
- **Stage worker manifest** (test/script only)
- **Config matrix manifest** (test/script only)
- **S3-lite baseline scorecard** (test/script only)
- **Production 4x4 dry run** (test/script only)
- **Local tuning harness** (test only)
- **Profile comparison** (test/script only)
- **Ghost overlap forced domain precheck** (test only)
- **Ghost Y overlap runtime precheck** (test only)

---

## 真正常用的 Phase 3B 主线 (active 维护)

670 个文件里大部分是 **历史 spike / audit / sprint 产物**, 但少数是 **active 主线**, 每天可能用:

| 文件 | 类型 | 作用 |
|---|---|---|
| `phase3b_long_run_preflight.py` | active | 168h campaign 启动前 preflight |
| `phase3b_operating_profile.py` | active | 运行配置 |
| `phase3b_anchor119_*` (5 个) | active advisory | env-gated advisory 守卫 |
| `phase3b_coordinate_validation_anchor119_row_domain_*` (15+) | active probe | 启 anchor119 advisory 时 fire |
| `phase3b_b5a_localized_evidence_validator.py` | active | B5a 当前 sprint validator |
| `phase3b_forced_anchor_proto_reduction.py` | active (大文件 3314 行) | 锚点空间降维 |
| `phase3b_forced_anchor_model_slice.py` | active (大文件 2990 行) | 锚点模型分片 |
| `phase3b_power_protocol_interaction.py` | active (大文件 2763 行) | 功率-协议耦合建模 |

其他大多是 **历史 spike / audit**, 留作 reference 不删 (per `feedback_cleanup_preserve_clarify`).

---

## 怎么找一个具体 Phase 3B 文件

如果你听说"someone mentioned phase3b_X" 但不知道在哪:

```bash
# Try src/search/ first (runtime module)
ls src/search/ | grep phase3b | grep <keyword>

# Or test (test file 一般跟 runtime module 同名)
ls src/tests/ | grep phase3b | grep <keyword>

# Or scripts (artifact generator)
ls scripts/ | grep phase3b | grep <keyword>
```

实际上 src/search + src/tests + scripts 文件名基本对齐. 找一个就能找另两个.

---

## Memory 引用

- [[feedback_cleanup_preserve_clarify]] — 不丢任何 phase3b 文件原则
- [[project_endfield_solver]] — 项目总览
