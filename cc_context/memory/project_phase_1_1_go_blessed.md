---
name: phase-1-1-go-blessed
description: 2026-05-23→24 Phase 1.1 cut framework GO blessed (5 轮 deliverable). 189 cuts pass (R5 F3 grid-bound + 命名口径统一) / mypy strict 0 / radon A 4.273 / source_digest 真 sha256 / strict gate ON / cut integrity check / watcher 返副本 / F1+F2 payload 加严 / bool!=int strict / F3 grid bound. 可进 Phase 1.2 P1.2B-F5/F6/F7/F8/F9.
metadata:
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-23: 外部 reviewer (GPT pro v8 全项目 audit 后) 给完整 Phase 1.1 exit hardening delivery — 不只 audit, 是 audit + fix + 验收 + plan v2 全做了.

## 包内容

`phase1_1_exit_hardening_user_delivery.zip` (230 KB):
- `docs/PHASE_1_1_EXIT_AUDIT_AND_FIX_REPORT.md` — audit + fix verdict
- `docs/PHASE_POST_1_1_REFACTOR_PLAN_v2.md` — plan v2 (内容已 merge 进 docs/项目说明/)
- `gate_outputs/01-08*.txt` — pytest / ruff / mypy / bandit / radon / vulture 输出
- `modified_files/` — 26 file (src/cuts + tests + 5 spec + vulture whitelist + 2 new doc)
- `patch/phase1_1_exit_hardening.patch` (133 KB) — clean apply

archive 进 `docs/research/p3_b_design_v2_20260521/external_review/`:
- `phase1_1_exit_hardening_audit_report_20260523.md`
- `phase1_1_exit_hardening_plan_v2_20260523.md`

## 8 项 fix (我们 plan §10 入门 7 项 + 1 项新发现)

1. ✅ strict gate `EXACT_FAMILY_VALIDATOR_STRICT="0"→"1"`
2. ✅ source_digest 真 sha256 (canonical_rules + candidate_placements + mandatory_exact_instances + facility_templates + commodity_demands + commodity_routes, 排除 `__*` cache key)
3. ✅ validator 拆 helper, radon D(27/24/23) → 最高 C(15)
4. ✅ F3 删 `evaluate_literal_port_exposure` (vulture catch unused, F3 统一走 `evaluate_literal_multiset`)
5. ✅ ghost_rect tuple 锁定 `(x, y, x_span, y_span)` + 非方形 fixture `(10,20,3,7)` → `(10,20,13,27)` (防 F8 接入时高宽反)
6. ✅ **新发现**: `on_ghost_rect_changed` 改 `unsafe_test_replay_fn=...` + `allow_unsafe_test_replay_fn=True` 双 flag (防生产误用 stub 绕 full family validator)
7. ✅ mypy strict 37 errors → 0
8. ✅ spec drift 全清 (state_machine v2 `PoseId=str`; cut_lifecycle v2 family list 删 `symmetry_lift` 加 F8/F9; 03 direction N/S/E/W; 02/04 commodity registry semantic)

## 验收 (delivery 含 gate outputs)

- pytest cuts: **172 → 178 pass** (+6 regression cover ghost_rect / source_digest / unsafe stub)
- python -O pytest cuts: 178 pass
- ruff default + no-ignores: pass
- mypy --strict --explicit-package-bases src/cuts/: pass
- bandit: 0 issues
- radon: average A, no D
- vulture (whitelist `scripts/vulture_cuts_whitelist.py`): pass

非阻塞: 全项目 src/tests collect 4 个 optional solver import error (highspy / pyscipopt 缺失) — 不在 cut framework gate.

## Plan v2 修正 (从 deliverable merge 进 docs/项目说明/)

外部 reviewer 修了我们 plan 几个错:
- **lifecycle 9 step vs 10 step**: 旧 plan "9-step lifecycle" 但列 `0..9` 是 10 个. v2 统一: 核心 9 步 (generate → minimize → serialize → deserialize → validate → attach-scope → evaluate → apply-to-master → replay/regression). `canonicalize` 是工具不算业务步
- **Phase 命名**: `P1.11` 同时用作 "入门 7 项" + "F5 pattern_nogood" 误导. v2 拆: P1.2A entry + P1.2B-F{5,6,7,8,9}
- **Phase 1.3 不再假设只剩接线**: 加 P1.3A CP-SAT attach spike (验 attach 方式可行性, ≤3 day PoC)
- **F6/F7/F9 proof obligation 加严**: greedy/LP relax 只能 oracle hint, validator 必重算 witness 或安全下界
- **F8 mode 锁 geometric** (cert 可引用 pole group/pose, body 不走 literal path)
- **telemetry 单位修正**: p95 ≤ 500µs (hot path), stretch ≤ 100µs

## commit

`docs/项目说明/06_current_status.md` + `07_historical_review.md §5.12` + `08_phase_1_2_plan.md` + `09_phase_1_3_plan.md` + `12_go_criteria.md §8.1` 全 update.

## 第 3 轮 deliverable — final hardening (2026-05-23 末, `db8d9cd` commit)

继 exit hardening (`9e01a6e`) + docs/项目说明/ v1.1 (`ecc96c7`) + v9 build (`907dade`) 之后, 外部 reviewer 再给 **`phase1_1_final_delivery_package.zip`** (140 KB) — 10 项新发现 adversarial soundness 升级:

1. source_digest 不信外部手写值 (BState.source_digest 备注, replay 必重算)
2. cut 证书完整性检查 — 新 `validate_cut_integrity()` 验 cert_payload hash + oracle_cert_hash + geometric ↔ cert payload
3. Cut runtime schema 加严 (空 cut_id / 非 tuple literals / 非 bytes payload / 坏 cert / literal bool|float|string slot / 非字符串 pose_id / 坏 minimization_audit fail-closed)
4. CutStore 状态机补洞 (不存在 cut 不能 reactivate; quarantined cut 不能重激活)
5. watcher 返副本 (`cuts_affected_by_*()` 不暴露内部 set, 外部 `.clear()` 不破坏 index)
6. F2 cutset free_cells 排除 `exterior_blocks` (不允许路线穿过静态阻挡)
7. F1/F2 payload 解析加严 (bitset 合法 base64 + 长度正确 + 高位不置; cell 不用宽松 `int(...)`, bool/float/越界 fail)
8. optional HiGHS/SCIP test skip (缺依赖时不 collection error)
9. exit_criteria script 文件名修 (`test_family_3_port_exposure` → `test_family_port_exposure`, `test_replay_suite` → `test_replay`)
10. 文档对齐 (cuts 测试数 178 → **181**; source_digest 不写 placeholder; strict gate 默认 ON 已落地)

验收 (final delivery 跑过):
- pytest cuts: 178 → **181 passed** (+3 regression: cut integrity / watcher copy / schema strict)
- python -O cuts: 181 passed
- mypy --strict src/cuts/: 22 source 0 errors
- ruff / bandit / vulture / radon: 全 pass
- exit_criteria 1/2/4: PASS
- optional HiGHS/SCIP: 14 skipped exit 0

Archive: `docs/research/p3_b_design_v2_20260521/external_review/phase1_1_final_delivery_20260523/`

## 第 4 轮 deliverable — recheck补强 (2026-05-24, `7b0c3c8` commit)

继 R3 后 reviewer 自发"再挑刺"复查, 修 R3 漏的 6 类 schema 边界 (adversarial layer 2):

1. base64 改 strict (`validate=True`), 拒 junk char (R3 加了 length 检查但没 strict mode)
2. region bitset 加 grid 外高位 0 check (`(70*70+7)//8` byte length + `arr[-1] >> extra_bits == 0`)
3. `Cut.scope` / `Cut.cert` 强制真 `CutScope`/`OracleCert` 对象 (非只验 hasattr)
4. **Python `bool` 是 `int` 子类陷阱**: `isinstance(True, int)=True`, R3 加的 `isinstance(x, int)` 检查会被 `True` 偷渡过. F1-F4 所有 numeric 字段加 `_parse_strict_int` (cap_R/demand_R/gap/cells_per_pose/cut_size/commodity_demand/blocking_slot/cell 坐标)
5. malformed cert evaluator fail-closed: F2/F4 evaluator `try-except` 返 False, 不抛异常
6. 文档对齐 181 → 188 + `docs/research/.../external_review/` 路径

`Cut.__post_init__` 从单 60+ line fn 拆 10 个 helper (`_validate_cut_mode` / `_require_scope` / `_require_cert` / `_validate_cut_scalar_schema` / `_validate_cut_identity_and_payload` / `_validate_cert_schema` / `_validate_cut_metadata_schema` / `_validate_cut_status_schema` / `_validate_scope_schema` / `_validate_literal_schema`) 保 radon A. R3 加的 `validate_cut_integrity()` 保持原位 (radon B(7) 不变), R4 跟 R3 兼容.

新增 7 个 regression (181 → **188**):
- lifecycle 非法 base64 拒绝 / region bitset 高位拒绝 / scope 非 CutScope 拒绝
- F1 `cap_R` bool / F2 `commodity_demand` bool / F3 `blocking_slot` bool / F4 commodity 坐标 bool

8 门禁验收 (reviewer log + 本地 reproduce byte-equal):
- pytest cuts: **188 passed** (普通 + `python -O`)
- ruff / mypy --strict (22 source 0 errors) / vulture / bandit (0 issues): PASS
- radon: Average A (**4.260869565217392**) — 与 reviewer log byte-equal
- exit_criteria: **3 PASS / 8 PENDING_PHASE_1 / 0 FAIL** (PENDING 全是 F7/F8/F9 测试未建 + 80/160-inst ramp report 没跑 + cut_store rotation 测试未建, 都是 Phase 1.2/168h ramp 要做的事, 不是埋雷)

Archive: `docs/research/p3_b_design_v2_20260521/external_review/phase1_1_recheck_20260524/`

Reviewer verdict: **Phase 1.1 GO, 建议下一步直接 Phase 1.2B-F5 fallback 优先**.

## 第 5 轮 deliverable — final polish (2026-05-24, `4278307` commit, v12 fixed 整包)

R4 之后 reviewer 出 **v12 fixed 整包** (127 MB 含 zmd_deps_v3.zip) 做 final polish. 不是 patch — 整包 cp 模式. 真实 src 改动只 1 个 bug fix + 1 个 test 修复 + 1 个新 regression, 其余 6 处全是文档命名对齐:

1. **F3 port_exposure cell 加 70×70 grid bound** — R4 加了 strict int 但漏了 grid 范围, 跟 F2/F4 `_parse_cell` 风格不一致. 补 `if not (0<=cell[0]<70 and 0<=cell[1]<70): raise` out-of-grid → schema_err fail-closed
2. **test 修复 + 新 regression** — 原 test `front_cell=(99,99)` 是 math 错路径, 现 grid bound 加严后 (99,99) 先被 grid reject (math 错 path 测不到), 改 `(8,10)` 保留 math 错语义; 新加 `test_validate_port_exposure_schema_err_out_of_grid_cell` 真测 out-of-grid 拒绝
3. **命名口径统一** — `P1.11/P1.12/...` → `P1.2B-F5/F6/F7/F8/F9` (避免旧版 P1.11 同时表示"入门" + "F5" 的混乱); 188 → 189 gate 口径; docs/项目说明/ 6 file (04/06/08/12/15 + README) 全 update

8 门禁验收 (reviewer + 本地 reproduce byte-equal):
- pytest cuts: **189 passed** (普通 + `python -O`, 188 → +1 F3 out-of-grid regression)
- ruff / mypy --strict (22 source 0 errors) / vulture / bandit (0 issues): PASS
- radon: Average A (**4.273291925465839**) — 与 reviewer log byte-equal (跟 R4 的 4.260... 差 0.013, 因 F3 加 helper)
- exit_criteria: 3 PASS / 8 PENDING_PHASE_1 / 0 FAIL

Archive: `docs/research/p3_b_design_v2_20260521/external_review/phase1_1_final_polish_20260524/`

**R5 verdict: Phase 1.1 gate 正式通过, 可进 Phase 1.2 P1.2B-F5**. 这是 reviewer 第一次 explicitly 说 "1.1 gate 可以正式通过" (前 4 轮都是 GO blessed 但建议继续 polish).

## Refs

- [[gpt-pro-p11-audit-not-go]] — 11 round audit history (现 verdict GO)
- [[cp-sat-no-add-lazy-constraint]] — Phase 1.3 critical paradigm 限制
- [[f9-area-only-not-density]] — F9 invariant
- `docs/research/p3_b_design_v2_20260521/external_review/phase1_1_exit_hardening_*` archive
- `docs/research/p3_b_design_v2_20260521/external_review/phase1_1_final_delivery_20260523/` (第 3 轮)
- `docs/research/p3_b_design_v2_20260521/external_review/phase1_1_recheck_20260524/` (第 4 轮)
- `docs/research/p3_b_design_v2_20260521/external_review/phase1_1_final_polish_20260524/` (第 5 轮)
