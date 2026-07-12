# FILE_STATUS.md

**Status:** CURRENT_INVENTORY  
**Updated:** 2026-07-11
**Release state:** P1.2 OWNER-CLOSED / P1.3 IN PROGRESS (cut attach not yet promoted)
**History**: Engineering history lives in [CHANGELOG.md](CHANGELOG.md).

本文件只列当前运行角色，不是 owner gate。任何 `CURRENT_CODE_ALIGNED` 只表示本次审计已对照工作树，
不表示 P1.2 closed、full suite passed 或交付已获认证。

## 状态词

- `CURRENT_CODE_ALIGNED`：当前工作树中的活动实现，已在本轮文本审计中对照。
- `STRUCTURAL_GATE`：结构/一致性闸，不等同于 soundness 或 release 结论。
- `POSTPROCESS_ONLY`：派生输出面，不是认证 authority。
- `DIAGNOSTIC_ONLY`：诊断或研究路径，不能产生 proof-bearing 结论。
- `HISTORICAL_OR_PLAN`：历史快照或后续设计。
- `OPEN`：已知未完成边界。
- `LANDED`：已落地的入口/能力；不等同于 soundness 或 release 结论。

## 认证发布链

| Path | Status | 当前角色 |
|---|---|---|
| `src/search/outer_search.py` | CURRENT_CODE_ALIGNED | producer；terminal success 只提交 `CANDIDATE_PROPOSED` 与绑定证据，不铸 durable `CERTIFIED` |
| `src/search/exact_campaign.py` | CURRENT_CODE_ALIGNED | campaign authority、resume validation；`supervisor_seal()` 是唯一 durable terminal `CERTIFIED` mint；生产入口是独立的 `scripts/run_supervisor_seal.py` |
| `src/search/terminal_fixed_witness_capsule.py` | CURRENT_CODE_ALIGNED | 隔离子进程 fixed-witness authority，nonce-bound response |
| `src/search/terminal_fixed_witness_verifier.py` | CURRENT_CODE_ALIGNED | 对提案中确切 witness 复验 geometry/binding/routing/power/connector-body |
| `src/search/candidate_proof_replay.py` | CURRENT_CODE_ALIGNED | candidate strong-status sink replay；不替代 fixed-witness identity check |
| `src/search/certified_surface.py` | CURRENT_CODE_ALIGNED | owner-closed P1.2 gate resolver、sealed-campaign evaluation、唯一 public certified publisher |
| `src/search/independent_infeasibility_reverifier.py` | CURRENT_CODE_ALIGNED | whole-layout nogood 落 cut 前的独立确认；不确认则 UNKNOWN/no cut |
| `src/search/certified_frontier.py` | CURRENT_CODE_ALIGNED | replay-verified candidate frontier projection，不是 owner gate |
| `data/review_gates/phase_1_2_spike_close.json` | CURRENT_CODE_ALIGNED | `closed_manual_owner_decision`; `p1_3b_entry_allowed=true`; `next_phase_entry.allowed=true` |

## 求解内核

| Path | Status | 当前角色 |
|---|---|---|
| `src/search/benders_loop.py` | CURRENT_CODE_ALIGNED | placement master → binding → routing；flow 只记诊断；whole-layout reject 经过 independent reverify |
| `src/models/master_model.py` / `exact_coordinate_master.py` | CURRENT_CODE_ALIGNED | 默认 certified placement master |
| `src/models/binding_subproblem.py` | CURRENT_CODE_ALIGNED | 命题 P 的 binding gate |
| `src/models/routing_subproblem.py` | CURRENT_CODE_ALIGNED | 命题 P 的有向连通 gate，含 selected-route connectivity recheck |
| `src/models/flow_subproblem.py` | DIAGNOSTIC_ONLY | 连续 LP 诊断；不门控 certified verdict，不产生认证吞吐证明 |
| `src/models/pose_bool_exact_master.py` | HISTORICAL_OR_PLAN | env-gated alternative；不是当前 public certified backend |
| `src/cuts/` | CURRENT_CODE_ALIGNED | active F1-F7+F9（F8 retired）；Stage B B0-B5b + 批D + α/α2 已落地（2026-07-12）：F1/F6/F7 typed lowering 全链、F5 shadow-only（无 lowering，真 adapter 在 verifier 前 fail-closed）、F2/F3/F4/F9 LEGACY_DIAGNOSTIC registry 拒绝；attach 仍 certified unsafe/default-off，PIC-4/5 生产层+RFC-003+B6 owner pending |

## Frozen inputs

| Path | Status | 说明 |
|---|---|---|
| `rules/canonical_rules.json` | CURRENT_CODE_ALIGNED | canonical rule truth |
| `rules/preprocess_plan.json` | CURRENT_CODE_ALIGNED | additive preprocess plan，不能覆盖 recipe/target/commodity truth |
| `data/preprocessed/mandatory_exact_instances.json` | CURRENT_CODE_ALIGNED | mandatory instances |
| `data/preprocessed/generic_io_requirements.json` | CURRENT_CODE_ALIGNED | validated generic I/O requirements |
| `data/preprocessed/candidate_placements.json` | CURRENT_CODE_ALIGNED | 外部大工件，在不在位因副本而异（用 `scripts/check_external_artifacts.py` 实测，别信文档）；pinned bytes = 45,774,305 / SHA256 `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`；45,773,799 bytes / `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 是拐角修复前 superseded、hash-incompatible 旧版 |

轻量分发可以 externalize candidate placements（stripped 审查副本通常缺它，默认 checker 容忍缺失、`--require` 不容忍）；certified contract 始终要求 pinned bytes 先恢复再跑。

## Public / derived outputs

| Path | Status | 当前角色 |
|---|---|---|
| `data/solutions/final_solution.json` | POSTPROCESS_ONLY | 只有 central publisher 从 sealed campaign 写出时才有 certified publication 语义 |
| `data/blueprints/optimal_blueprint.json` | POSTPROCESS_ONLY | 同上 |
| `data/solutions/certified_delivery_manifest.json` | POSTPROCESS_ONLY | 同上；文件名或字段本身不能授予 authority |
| `src/io/serializer.py`, `src/io/delivery_manifest.py` | POSTPROCESS_ONLY | formatting/compatibility；不能旁路 central publisher |
| `src/render/*`, `src/adapters/*`, `scripts/export_*` | POSTPROCESS_ONLY | viewer/report/adapter/export；只能消费已验证 surface 或明确输出 non-authoritative 数据 |

## Gates and evidence

| Path | Status | 说明 |
|---|---|---|
| `data/proof_obligations/p1_2_proof_obligations.json` | STRUCTURAL_GATE | 15 active obligations；绑定 sink/hash/guard/critical files |
| `data/proof_obligations/strong_status_write_allowlist.json` | STRUCTURAL_GATE | deny-by-default strong-status occurrence registry；不是 completeness proof |
| `scripts/check_p1_2_proof_obligations.py` | STRUCTURAL_GATE | checker PASS 只表示登记结构一致 |
| `scripts/preflight_gate.py` | STRUCTURAL_GATE | repository preflight；不运行已退役 doc-subject sync |
| production supervisor entrypoint | LANDED | `scripts/run_supervisor_seal.py` 是独立生产命令；`main.py` 仍只提交 `CANDIDATE_PROPOSED`；入口存在 ≠ P1.2 closed |
| `scripts/package_review_snapshot.py` | CURRENT_CODE_ALIGNED | resolve-once：treeish 一次解析为 immutable commit，provenance/manifest/物化三处统一用它（TOCTOU 回归测试钉住）；archive policy 覆盖完整性仍是 OPEN 边界 |

## Documentation and memory

| Path | Status | 说明 |
|---|---|---|
| `PROJECT_LOCK.md` | CURRENT_CODE_ALIGNED | 认证边界权威；2026-07-11 已同步 F8 retirement / partial attach / Stage B boundary |
| `README.md`, `NAV_MAP.md`, `docs/项目说明/06_current_status.md` | CURRENT_CODE_ALIGNED | 当前入口与状态摘要 |
| `docs/research/**` | HISTORICAL_OR_PLAN | 时间点证据/实验档案；不得覆盖当前工作树 |
| `cc_memory/memory.db` | CURRENT_CODE_ALIGNED | active collaboration memory；通过 CLI 更新并保持 edges/facts 一致 |

## Specs

| Path | Status | 说明 |
|---|---|---|
| `specs/01_problem_statement.md` | CURRENT_CODE_ALIGNED | current exact objective, admissibility, and geometry legality boundary |
| `specs/11_pipeline_orchestration.md` | CURRENT_CODE_ALIGNED | producer/supervisor/publisher pipeline; non-authoritative frontier probe |
| `specs/21_frontier_probe_and_campaign_telemetry.md` | CURRENT_CODE_ALIGNED | frontier probe + campaign telemetry spec (diagnostic-only) |

## Test inventory

2026-07-12 collect-only（HEAD `07d04b3`，`.venv` 解释器）：455 个 `test*.py` 文件（`git ls-files 'src/tests/**/test*.py' 'src/tests/test*.py'`）/ 4424 tests；`-m slow` 收集 31 个实例（`_SLOW_TEST_NODEIDS` 字面登记 24 条）；`src/tests/cuts` 单独为 833 tests。以上均是收集数量，不是通过数量；批次提交信息里的 cuts N 是各自 commit 时点快照，不是当前树数字。结构 checker 当前口径：15 obligations / 67 proof-bearing sinks；strong-status 65 AST nodes / 83 allowlist entries。
