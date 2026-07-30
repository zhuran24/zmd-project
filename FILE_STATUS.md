# FILE_STATUS.md

**Status:** CURRENT_INVENTORY  
**Updated:** 2026-07-30
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
| `src/models/pose_bool_exact_master.py` | CURRENT_CODE_ALIGNED | active env-gated alternative master；certified mode 显式禁用并 fail closed；不是 public certified backend |
| `src/cuts/` | CURRENT_CODE_ALIGNED | active F1-F7+F9（F8 retired）；Stage B B0-B5b + 批D + α/α2 已落地（2026-07-12）：F1/F6/F7 typed lowering 全链、F5 shadow-only（无 lowering，真 adapter 在 verifier 前 fail-closed）、F2/F3/F4/F9 LEGACY_DIAGNOSTIC registry 拒绝；attach 仍 certified unsafe/default-off，PIC-4/5 生产层+RFC-003+B6 owner pending |

## Frozen inputs

| Path | Status | 说明 |
|---|---|---|
| `rules/canonical_rules.json` | CURRENT_CODE_ALIGNED | canonical rule truth；17,510 bytes / SHA256 `5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05` |
| `rules/preprocess_plan.json` | CURRENT_CODE_ALIGNED | additive preprocess plan，不能覆盖 recipe/target/commodity truth；1,383 bytes / SHA256 `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee` |
| `data/preprocessed/mandatory_exact_instances.json` | CURRENT_CODE_ALIGNED | mandatory instances |
| `data/preprocessed/generic_io_requirements.json` | CURRENT_CODE_ALIGNED | validated generic I/O requirements |
| `data/preprocessed/candidate_placements.json` | CURRENT_CODE_ALIGNED | 外部大工件，在不在位因副本而异（用 `scripts/check_external_artifacts.py` 实测，别信文档）；pinned bytes = 54,467,709 / SHA256 `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`；`a914…` 45,774,305、`adcc…` 45,773,799、`d5e3…` 53,594,995 和 `78e2…` 53,595,501 仅属 superseded、hash-incompatible 历史链 |

轻量分发可以 externalize candidate placements（stripped 审查副本通常缺它，默认 checker 容忍缺失、`--require` 不容忍）；certified contract 始终要求 pinned bytes 先恢复再跑。

当前 exact generic-input 语义是实体路由合同：`box_sink` 3 个物理输入/3 个物理输出，mandatory core 14 个物理输入/6 个物理输出，成品从 producer output 路由到 provider physical input。provider-aware、instance-aware 下界不得给未实例化模板记容量；需求 2 已由 mandatory core 覆盖，所以 box lower bound 为 0。campaign 必须绑定并比较完整 `generic_input_slots_by_operation` map。

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
| `devtools/research_run_contract.py` | CURRENT_CODE_ALIGNED | G3 developer/research-only 的稳定字节快照、独占 no-overwrite run root、逐组件 no-follow artifact-root 打开、全树目录 FD/signature 保留至终检、manifest 排除 `receipt.json` 自身而完成态 closure 要求 manifest 加唯一普通文件 `receipt.json`、`-I -B` 进程合同、canonical envelope 与字节 identity replay；不进入 certified exact-source TCB 或 production authority |
| `docs/research/w0_power_cycle_domino_d6_20260728/` | DIAGNOSTIC_ONLY | W0 专用 D6 intake、exact front-aware joint completion、固定 artifact label/path 合同与 stdlib-only replay；closed-root v2 的 seed-narrow、28-slot antecedent 与 v3 `d6_6b_d9_6g_swap_v1` antecedent 均为 replay-accepted local `INFEASIBLE`；v3 已通过 full preflight、前后两次相同资源门禁和两份逐字节一致的异构 replay，只关闭其 exact local antecedent，不产生全图 witness、cut、上下界或 production authority |
| `docs/research/noncert_cuts_ab16_20260724/` | DIAGNOSTIC_ONLY | AB16 Gate-A/Gate-B/package/formal/16-arm research-only 链；A031–A033 均为不可改写 frozen roots，A033 只发布 formal admission，未发布 guardian-ready、attempt consumption、selection 或 arm。当前 runtime roles 保留 canonical absolute socket identity，仅以 retained-dirfd `/proc/self/fd` alias 适配长 worktree 的 Linux AF_UNIX 调用；alias 不进入 artifact/schema/authority，任何 parent/leaf/peer drift fail closed。下一 fresh root 必须重新绑定 committed source bytes 和完整前后门禁 |
| `data/proof_obligations/p1_2_proof_obligations.json` | STRUCTURAL_GATE | 15 active obligations；绑定 sink/hash/guard/critical files |
| `data/proof_obligations/strong_status_write_allowlist.json` | STRUCTURAL_GATE | deny-by-default strong-status occurrence registry；不是 completeness proof |
| `scripts/check_p1_2_proof_obligations.py` | STRUCTURAL_GATE | checker PASS 只表示登记结构一致 |
| `scripts/preflight_gate.py` | STRUCTURAL_GATE | repository preflight；不运行已退役 doc-subject sync |
| production supervisor entrypoint | LANDED | `scripts/run_supervisor_seal.py` 是独立生产命令；`main.py` 仍只提交 `CANDIDATE_PROPOSED`；入口存在 ≠ P1.2 closed |
| `scripts/package_review_snapshot.py` | CURRENT_CODE_ALIGNED | resolve-once：treeish 一次解析为 immutable commit，provenance/manifest/物化三处统一用它（TOCTOU 回归测试钉住）；archive policy 覆盖完整性仍是 OPEN 边界 |

## Documentation and memory

| Path | Status | 说明 |
|---|---|---|
| `PROJECT_LOCK.md` | CURRENT_CODE_ALIGNED | 认证边界权威；2026-07-30 窄增 AB16 selected-loader/pathname transport 合同，保持既有 schema、绝对 artifact identity 与 research-only authority；W0 D6 v2/v3、F8 retirement、partial attach 与 Stage B boundary 不变 |
| `README.md`, `NAV_MAP.md`, `docs/项目说明/06_current_status.md` | CURRENT_CODE_ALIGNED | 当前入口与状态摘要 |
| `docs/项目说明/24_repository_asset_governance.md` | CURRENT_CODE_ALIGNED | G1/G2 代码资产治理与 G3 最小公共研究基础层索引；不授予认证 authority |
| `data/repository_governance/code_assets.json` | STRUCTURAL_GATE | 可复算目录规则、显式例外与基线收据；由 schema/checker fail closed 校验 |
| `docs/research/**`（下列 §2B current-spec 除外） | HISTORICAL_OR_PLAN | 时间点证据/实验档案；不得覆盖当前工作树 |
| `docs/research/p3_b_design_v2_20260521/{cut_lifecycle_v2.md,state_machine_v2.md,cut_family_specs/**}` | CURRENT_CODE_ALIGNED | `PROJECT_LOCK.md` §2B 指定的 cut object current specs；不受历史源码默认搜索投影影响 |
| `cc_memory/memory.db` | CURRENT_CODE_ALIGNED | active collaboration memory；通过 CLI 更新并保持 edges/facts 一致 |

## Specs

| Path | Status | 说明 |
|---|---|---|
| `specs/01_problem_statement.md` | CURRENT_CODE_ALIGNED | current exact objective, admissibility, and geometry legality boundary |
| `specs/11_pipeline_orchestration.md` | CURRENT_CODE_ALIGNED | producer/supervisor/publisher pipeline; non-authoritative frontier probe |
| `specs/21_frontier_probe_and_campaign_telemetry.md` | CURRENT_CODE_ALIGNED | frontier probe + campaign telemetry spec (diagnostic-only) |

## Repository code-asset inventory

2026-07-28 基线收据（tracked-clean `main`，HEAD
`201c1988243951e16473af15f5d670ab11edf964`）：Git-visible 资产 3,249 个；其中代码资产
2,001 个、36,483,677 bytes、912,444 LF 行。分类为 active implementation 386、test 646、
common infrastructure 475、authoritative input 4、enforcement control 7、historical evidence 464、
retirement candidate 19。该数字只描述这个带日期的基线；当前工作树由
`python devtools/check_repository_code_assets.py check` 重新枚举并校验，不能把本段抄作后续现值。

## Test inventory

2026-07-28、G2 隔离前的 tracked-clean `201c198` bare-pytest 基线为 6,624 个 nodeid，
规范化 SHA256 为
`6917fa03f27442fb0d42deb7e143dbd52cb943fd64b3b39551f6eb8509961f96`。当前互斥快速面为：
developer 3,541（`a430d75867516b5b0b05516a4db191287e34d5c10bf4c1a3b188f723c7abc9d7`）、
evidence/non-replay 1,512（`362e0187f943eabb9e36b13a7d283b8ffc3d55e6a22c6e6e37bd0c263474c0d2`）、
replay 1,563（`bac7d8817a81e5637db4c69ad9cbfe1ea4f0c3db5cadd21e6134c1387a55f75f`）。
三者并集逐 nodeid 等于 full/non-slow 6,616
（`a635e8d531b849bdebe2c7b005299dcdfdcfd8a9abc25d7ec9946ad3e2de4855`）。

以上都是 collect-only 身份，不是通过数量或 soundness 结论。full/all 为 6,647
（`eeb6f3e1b45d491be286ece460c4da7758b677971ebf59bc766572462589ca16`），slow 仍为 31
（`9606959449cd99e6c4ca6c0c305e75f9d4fb4459a159bd2f7daf1e45e82ff6dd`）；
`cuts_collection_counter` 仍为 958，因 lock-parity test 重命名而更新规范化 SHA256 为
`1431c01e8a0aa94f04bb9071e6cb5d6fdd5415d917133f3758ab9ffdf904bb0d`，其他既有 focused
入口收据不变。另有 107 个 auxiliary memory tests 通过显式 full 路径保留，nodeid SHA256
为 `32d6a873dc1aa2d2b559d8a9978b8dae13652f4f93457fc2385d53528a19f8d1`。
入口命令和边界见 `docs/项目说明/24_repository_asset_governance.md`；
完整 preflight 仍由非 slow 与 slow 两条显式门禁共同组成。
