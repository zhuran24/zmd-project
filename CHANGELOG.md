# CHANGELOG.md

This file is the canonical home for dated engineering history that used to be
split between `PROJECT_LOCK.md` and `FILE_STATUS.md`.

## 2026-06-16

- Added a certified-exact source-tree digest to campaign `artifact_hashes`. This intentionally breaks resume compatibility for older checkpoints: states without the new `certified_exact_source_tree` key fail with `artifact_hash_mismatch`, so campaigns must be restarted instead of resumed across this proof-kernel binding change. [src/search/exact_campaign.py]

## 2026-05-16

### D step 2: Community blueprint hint 注入 (master.solve hint integration)

- Added `scripts/blueprint_to_master_hint.py` — convert IP v2 blueprint JSON (用户手调验证版 `BP-2026-05-13 08_35_36.blueprint(1).json`) to `Dict[instance_id, pose_idx]` for `master.solve(solution_hint=...)`. 226 facility devices → 225 mapped (1 hub miss due to anchor range geometry). [scripts/]
- Added regression test `src/tests/test_blueprint_to_master_hint.py` — 10 hand-verified samples (4 facility_type × 4 rotation × orientation 0+1) lock rotation→(orientation, port_mode) mapping. [src/tests/]
- Added integration in `src/search/benders_loop.py:3565` — `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` env loads JSON + merges with greedy hint (community overrides greedy on overlap, since user-curated > heuristic). [src/search/]
- Updated `scripts/run_campaign_p2_workers1.sh` + `run_campaign_workers2.sh` — auto-default `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=data/hints/blueprint_2026_05_13_master_hint.json` when file present. [scripts/]
- Added edge case tests `src/tests/test_community_hint_env_injection.py` — 9 cases (empty/whitespace/missing-file/malformed-JSON/non-int values). [src/tests/]
- Added `scripts/hint_coverage_report.py` — audit hint coverage % + pose_idx range validity (225/266 = 84.6% mandatory hinted, 0 out-of-range). [scripts/]
- Added `scripts/analyze_hint_vs_baseline.py` — compare baseline state vs hint state for UNKNOWN→FEASIBLE / UNKNOWN→INFEASIBLE upgrade signals. [scripts/]
- Added `CLAUDE.md` runbook section — community hint workflow + integration mechanism. [CLAUDE.md]

**Empirical results** (5 short trials, master_seconds 600s..3600s × workers 1..8 × profile guided_branching_v4/ghost_first_v1):
- All 5 candidates (35×14 / 33×15 / 31×16 / 27×15 / 24×17) returned UNKNOWN, including 27×15 (blueprint natural empty rect 15×27 exact match)
- Telemetry verified: 266 mandatory instances × 3 (x/y/mode) = 798 AddHint calls per candidate
- Conclusion: hint integration end-to-end works zero-loss, but master.solve cannot decide these candidates in 600-3600s even with perfect hint shape match. Master `inherent difficulty`, not hint failure.

### 项目整理 (清晰为主, 不丢东西)

- Added `docs/lever_verdicts.md` — 主线 master 加速 lever 路线总账 (L1-L11) + 实测 verdict (9 ❌ 死路, 1 🟡 未试 hard constraint). [docs/]
- Added `docs/env_variable_index.md` — 100+ `EXACT_*` / `PHASE3B_*` env 变量集中索引, 11 组分类. [docs/]
- Added `docs/phase3b_module_index.md` — 670 个 Phase 3B 文件物理分类 (154 src + 264 tests + 252 scripts), 17 cluster + active 主线明确区分. [docs/]
- Added `docs/specs_index.md` — 23 份 specs/编号 spec 一句话索引 + 9 份 ecosystem_notes 索引. [docs/]
- Added `src/adapters/README.md` — 4 个 adapter 子目录 (industrial_planner / endfield_calc / dige / base_planner) 职责说明 + 数据流向. [src/adapters/]
- Added `scripts/README.md` — scripts/ 入口分类: campaign wrapper / gates / IP delivery / vendor refresh / hint 工具 / Phase 3B 生成器. [scripts/]
- Updated `README.md` — 顶部加项目状态地图 (Phase 3A done / 3B in progress / 3C planning) + 6 个关键文档入口. [README]
- Updated `src/models/master_model.py` / `src/models/exact_coordinate_master.py` / `src/search/benders_loop.py` — 3 个 5000+ 行单文件顶部加 module docstring 索引 (主要 section 行号 + 公开 API + env 引用). [src/]
- Updated `src/tests/test_master.py` / `src/tests/test_exact_contract.py` — 10000+/5000+ 行测试文件加目录索引 docstring. [src/tests/]
- Updated `src/models/highs_master_model.py` / `scip_master_model.py` / `scip_power_separator.py` — 加 STATUS 标注 "实验 PoC, 验证为死路, 留作 reference" (per memory `project_highs_rewrite_blocker`). [src/models/]
- Updated 5 个 Codex-era 永远 skip 测试文件 (test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_*.py) 加文件头 docstring 说明缘由 + 保留原因. [src/tests/]
- Updated `.gitignore` — 加 `.claude/worktrees/` (Claude Code agent worktree, regenerable, not source).

**整理原则**: 重组 / 加文档 / 加索引 OK, 删任何文件 NOT OK. 全部 ~1500 行新文档, 0 文件删, 0 代码逻辑改动. 2207 pytest pass + 0 failed.

## 2026-05-08

- Refreshed the vendored `JamboChen/endfield-calc` snapshot from package version `0.5.2` (commit unavailable, observed 2026-03-27) to `0.6.2` master commit `49be16e1`. Catalog grew from 130 items / 172 recipes / 14 facilities to 178 / 260 / 16. Newly observed facilities `ITEM_PORT_LIQUID_PURIFIER_1` and `ITEM_PORT_MIX_POOL_2` likely correspond to 1.2 武陵 content; `ITEM_PORT_DISMANTLER_1` re-tiered 4→3. `canonical_rules.json` intentionally still keeps the original 17-recipe semantic-aligned subset; the refresh did not re-project the catalog. [FILE_STATUS]
- Added `scripts/refresh_endfield_calc_snapshot.py` so future endfield-calc snapshot refreshes are mechanical: fetch latest TypeScript catalog, rewrite `SOURCE_METADATA.json` with version/commit/`observed_counts`/previous tracking, and print a diff report. The script does not touch `canonical_rules.json` or release-note files. [FILE_STATUS]
- Vendored a field-subset of upstream `hsyhhssyy/IndustrialPlanner` BASES at `third_party_snapshots/industrial_planner/bases/bases.json` (7 bases: 3 武陵 80/50/50, 4 四号谷地 70/40/40/40), extracted from branch `v2` commit `c494c5ae`. Confirmed `wuling_protocol_core` is 80x80; PROJECT_LOCK active scope still `valley4_protocol_core` (70x70). Added `scripts/refresh_industrial_planner_bases.py` so this snapshot can be re-pulled mechanically. [FILE_STATUS]
- Refactored `src/tests/test_endfield_calc_typescript_snapshot.py` to read `SOURCE_METADATA.json` for expected counts and source_version, eliminating hardcoded numbers so the next upstream refresh does not require test edits. Added a 5% noise floor against silent regressions. [FILE_STATUS]
- Added `src/tests/test_industrial_planner_bases_snapshot.py` to sanity-check the new vendored bases (schema, required fields, active-scope presence, count-collapse guard); also reads `SOURCE_METADATA.json` so it stays refresh-friendly. [FILE_STATUS]

## 2026-04-17

- Added `docs/phase3b_exact_endgame_execution_plan.md` and linked it from the root/readme entry surfaces, so the repository now carries one detailed current-to-finish execution book for the remaining Phase 3B exact endgame instead of leaving the solver-side closeout implicit after the single-base delivery/productization line landed. [FILE_STATUS]
- Closed the remaining single-base consumer-surface productization tail by surfacing `current_surface_health.{json,md,txt}` directly in the repo-front frontdoor helper links/manifest/status card and the aggregate `active_single_base_delivery_entrypoints.{json,md}` manifest, then tightening the no-drift audit plus release-promotion convergence loop so those surfaced health refs/counts must agree with the checked-in health snapshot before the final surface is left behind. [FILE_STATUS]
- Added a compact checked-in `current_surface_health.{json,md,txt}` trio plus a dedicated builder/guide, so CI/reviewer tooling/scripts can read the active single-base consumer-surface clean/drift verdict and top-line counts without parsing the full no-drift audit payload first; the release builder now emits that health snapshot automatically after the converged surface-alignment audit finishes clean. [FILE_STATUS]
- Tightened the single-base consumer-surface no-drift audit so it now fail-closes on the surfaced `surface_alignment_summary.{json,md,txt}` refs themselves across the repo-front frontdoor HTML/manifest and the aggregate entrypoints manifest, instead of only checking the older frontdoor/entrypoints linkage. [FILE_STATUS]
- Refreshed the promotion chain so it now converges that surfaced audit metadata in three passes — initial audit, surfaced rebuild, closing audit — and only leaves the checked-in frontdoor/entrypoints pair behind after the final audit summary, counts, and refs agree. [FILE_STATUS]
- Surfaced the checked-in `surface_alignment_summary.{json,md,txt}` trio directly in the repo-front single-base homepage and `frontdoor_manifest.json`, so reviewers can see whether the current consumer surface is clean without manually drilling into `.artifacts/`. [FILE_STATUS]
- Extended `active_single_base_delivery_entrypoints.{json,md}` so it now carries the latest consumer-surface audit summary alongside the current release/viewer/landing/latest-bundle entrypoints, giving script consumers one aligned file that also reports clean/drift status. [FILE_STATUS]
- Tightened `build_industrial_planner_single_base_delivery_release.py` so it now refreshes the surface-alignment audit, re-renders the aggregate entrypoints/frontdoor with that audit summary wired in, and then re-runs the audit on the final checked-in surface before declaring the promotion clean. [FILE_STATUS]

## 2026-04-16

- Added a lightweight repo-front / aggregate-entrypoints no-drift audit (`scripts/audit_industrial_planner_single_base_delivery_surface_alignment.py`) plus a dedicated GitHub workflow, so the checked-in single-base consumer surface now fail-closes when helper links, frontdoor metadata, or aggregate script-entry paths drift apart even without repromoting a release. [FILE_STATUS]
- Tightened the repo-front single-base homepage so its hero helper links now point directly at `active_single_base_delivery_entrypoints.{json,md}`, added explicit script-entry metadata to `frontdoor_manifest.json`, and refreshed the release builder so future promotions rebuild the frontdoor after the aggregate manifest exists instead of leaving humans and automation on slightly different current-entry surfaces. [FILE_STATUS]
- Added `active_single_base_delivery_entrypoints.{json,md}` plus a dedicated builder/guide, so script consumers now get one checked-in manifest that fail-closes on drift while summarizing the active release pointer, current viewer, stable landing bundle, and top-level latest bundle alias in one place. [FILE_STATUS]
- Extended the single-base delivery release builder to refresh that aggregate current-entrypoints manifest by default, and tightened rollback so repo-front latest-alias outputs are restored too if a later post-promotion step fails. [FILE_STATUS]
- Added a shorter repo-front latest-bundle alias trio — `industrial_planner_latest_single_base_delivery_bundle.zip` plus `latest_single_base_delivery_bundle.{json,md}` — and repointed the download-first primary action to that top-level alias so script consumers no longer need to remember the `current_delivery/downloads/` subdirectory. [FILE_STATUS]
- Added a stable one-file current bundle ZIP alias under `data/examples/industrial_planner/current_delivery/downloads/`, plus JSON/Markdown pointer sidecars, and repointed the repo-front download-first primary action at that alias so users can pull the active single-base delivery surface without manually assembling sidecars. [FILE_STATUS]
- Tightened the checked-in IndustrialPlanner repo front door into an explicit browse-first/download-first homepage, added machine-readable `entry_modes` metadata to `frontdoor_manifest.json`, and fail-closed the frontdoor build when the stable landing no longer exposes the required viewer/download actions. [FILE_STATUS]
- Added a higher-level checked-in repo front door for the active IndustrialPlanner single-base line: `data/examples/industrial_planner/index.html` plus `frontdoor_manifest.json`, a dedicated frontdoor builder/guide, and a root `README.md` that now points straight at the active current-delivery path instead of making users hunt through pointer files first. [FILE_STATUS]
- Hooked the single-base delivery release builder into that repo-front refresh and tightened rollback so a frontdoor failure now restores the stable current-landing directory instead of leaving a half-updated checked-in consumer surface behind. [FILE_STATUS]
- Made the stable `current_delivery/landing_manifest.json` emit repo-relative source/output paths for repo-local builds, so the checked-in landing metadata no longer captures build-machine absolute paths. [FILE_STATUS]
- Added a stable `current_delivery/` landing/download layer on top of the checked-in current-viewer pointer, plus `scripts/build_industrial_planner_single_base_delivery_landing.py` and `src/render/industrial_planner_single_base_delivery_landing.py`, so the active `valley4_protocol_core` 70×70 line now has one fixed consumer entry path with a copied viewer bundle under `viewer/` and grouped quick downloads without widening `future_scope`. [FILE_STATUS]
- Hooked the single-base delivery release builder directly into that current-landing refresh, so each promoted active-contract release can now fail-closed while refreshing the versioned viewer bundle/current-viewer pointer **and** the stable current landing/download directory. [FILE_STATUS]
- Hooked the single-base delivery release builder directly into the viewer promotion path, so each promoted `valley4_protocol_core` 70×70 release can now fail-closed while refreshing a versioned checked-in viewer bundle, `active_single_base_delivery_viewer.{json,md}`, and `viewers/viewer_index.{json,md}` alongside the existing release pointer/index. [FILE_STATUS]
- Added an active-current-release viewer-bundle workflow for the IndustrialPlanner single-base line: a builder that resolves `active_single_base_delivery_release.json`, materializes a compact static viewer bundle, prunes `candidate_placements.json` down to the release-selected poses only, regenerates `viewer_report.json`, and publishes grouped delivery/support/gate/meta download links via `release_viewer_manifest.json`. [FILE_STATUS]
- Extended the static web viewer so it can optionally surface single-base delivery release cards and grouped artifact downloads when `release_viewer_manifest.json` is present, while still hiding those sections and falling back to the older blueprint-first behavior when the manifest is absent. [FILE_STATUS]

## 2026-04-15

- Added an operator-facing `scripts/run_industrial_planner_single_base_e2e.py` workflow plus a dedicated single-base runbook doc, so the active `valley4_protocol_core` 70×70 line now has one standard end-to-end path from regenerated source truth through export bundle, validator/throughput sidecars, fresh support reports, checked-in inventory/gate rechecks, and a failure-classified handoff summary without widening scope. [FILE_STATUS]
- Added `scripts/build_industrial_planner_single_base_delivery_release.py`, a dedicated release guide, and checked-in pointer/index artifacts for versioned active-contract delivery bundles, so a delivery-ready `valley4_protocol_core` 70×70 run can now be promoted into a fixed release id with bundled evidence, checksums, and an honest exact-status note without reactivating any `future_scope` base. [FILE_STATUS]

## 2026-04-14

- Narrowed the active IndustrialPlanner support contract to the single 70×70 `valley4_protocol_core` base, rewrote the checked-in full-demand base/deployment/overview reports around that single active scope, and collapsed the three dormant 40×40 valley4 sub-bases into grouped `future_scope` metadata instead of keeping them in the active matrix surface. [PROJECT_LOCK]
- Simplified the checked-in support-suite inventory and repo-level checked-artifact family inventory to one active report family/report set, while preserving the old protocol-core transition slice and outer-bundle family as explicit `future_scope` metadata rather than deleting them. [FILE_STATUS]
- Froze the outer-deployment bundle path out of the active IndustrialPlanner CI gate, refreshed the focused regression workflow to cover only the active single-base support surface, and updated governance/docs to describe the new scope boundary clearly. [FILE_STATUS]

## 2026-04-07

- Added a second checked-in IndustrialPlanner support report-set for the focused `valley4_protocol_core` + `wuling_protocol_core` protocol-core transition slice, expanded the support-suite inventory summary to track unique audited-base coverage plus repeated-base overlap, and refreshed the repo-level checked-artifact gate so the support leg now exercises both the full-universe report set and an overlapping focused subset without double-counting decision-surface state. [FILE_STATUS]
- Added a second checked-in IndustrialPlanner outer-deployment bundle for the degenerate 70×70 `valley4_protocol_core` identity path and refreshed the outer-bundle suite summary so it now distinguishes translated vs identity outer bundles; the inventory-driven gate therefore exercises both the real larger-base `wuling_protocol_core` path and the zero-moat canonical-size path through checked-in artifacts instead of only one translated example. [FILE_STATUS]
- Added a checked-in `checked_artifact_family_inventory.json` and refactored `audit_industrial_planner_checked_artifact_suite.py` to dispatch through that inventory-of-inventories, so the repo-level IndustrialPlanner gate now reads family-specific inventories/builders from one checked-in registry instead of hard-coding separate support/outer wiring; the existing support-suite and outer-bundle legs remain clean under the new family-driven path. [FILE_STATUS]
- Added a checked-in `full_demand_support_suite_inventory.json` plus an inventory-driven `audit_industrial_planner_full_demand_support_suite_inventory.py` wrapper, so the strict/additive decision-surface leg now scales the same way as the translated outer-bundle leg and the repo-level checked-artifact gate can consume inventories on both sides instead of hard-coding one support-report directory. [FILE_STATUS]
- Added an inventory-driven IndustrialPlanner outer-base bundle suite plus a checked-in `outer_base_bundle_inventory.json`, so the repo-level checked-artifact gate now scales beyond a single hard-coded `wuling_protocol_core` example and can fail closed on every listed translated larger-base bundle through one checked-in inventory. [FILE_STATUS]
- Added a checked-in GitHub Actions workflow for the repo-level IndustrialPlanner checked-artifact gate and taught `audit_industrial_planner_checked_artifact_suite.py` to emit a plain-text summary copy alongside its JSON/Markdown sidecars, so relevant PRs can run focused regressions, fail closed on decision-surface or outer-bundle drift, and upload reviewable artifacts without changing canonical truth or certified evidence. [FILE_STATUS]

## 2026-04-06

- Added a deterministic no-drift audit for the checked-in IndustrialPlanner outer-base bundle plus a repo-level checked-artifact gate, so CI can now fail closed on either stale strict/additive support reports or stale translated `wuling_protocol_core` example artifacts; the IndustrialPlanner compatibility manifest now reuses the canonical blueprint `export_timestamp` for `generated_at` to keep those bundle checks reproducible. [FILE_STATUS]
- Added a no-drift `--check` mode to the IndustrialPlanner full-demand support-suite workflow plus drift-detection regression coverage, so CI can now fail closed when any checked-in canonical/deployment/overview report is missing or stale instead of silently letting the repo-level decision surface lag behind current code. [FILE_STATUS]
- Added a one-shot IndustrialPlanner full-demand support-suite workflow plus a checked-in `full_demand_support_overview` summary, so the strict canonical matrix, additive deployment-path matrix, and cross-view status deltas now regenerate together; `wuling_protocol_core` is surfaced as the sole current checked-in transition (`unsupported_by_canonical_contract -> proven_equivalent`). [FILE_STATUS]
- Added a checked-in IndustrialPlanner full-demand deployment-path matrix plus a dedicated audit CLI/tests, so the repo now preserves the strict canonical 70×70 support view while also surfacing the best available outer-deployment result; `wuling_protocol_core` now shows up as validator-clean translated `proven_equivalent` on the additive path instead of disappearing behind the old contract-ceiling summary alone. [FILE_STATUS]
- Taught the larger-base outer-plan path to stage pure-input boundary loaders inboard when a true edge lacks foundation bus, synthesize grouped input-side `item_port_log_hongs_bus` witnesses, and refresh the checked-in outer-base bundle so `wuling_protocol_core` now validates cleanly and reaches translated `proven_equivalent` without widening canonical truth. [FILE_STATUS]
- Added a real adapter-side IndustrialPlanner outer deployment representation: `OuterBaseDeploymentPlan`, deterministic larger-base inner-island placement, explicit true-edge boundary assignments, moat-only connector reservations, witness reservations, and export mappings that keep the canonical 70×70 schema unchanged. [FILE_STATUS]
- Added a validator-grounded outer export probe for larger IndustrialPlanner bases plus dedicated CLIs/tests, so `wuling_protocol_core` can now be pushed past the old contract-ceiling placeholder and surfaced as a real geometry blocker (`true_edge_witness_geometry_shortfall`) instead of stopping at “70×70 cannot express 80×80”. [FILE_STATUS]
- Integrated `OuterBaseDeploymentPlan` into the production IndustrialPlanner exporter and static throughput audit via a postprocess-only manifest export-mapping section, so translated larger-base exports can now retain canonical-instance pairing evidence without widening the canonical schema or the certified proof boundary. [FILE_STATUS]

## 2026-03-30

- Added an IndustrialPlanner adapter-side static recipe/capacity conformance layer: exact canonical->target recipe matching, conservative facility-intent recovery, per-recipe full-speed lower-bound rollups, and conservative boundary I/O audit sidecars without changing certified-exact semantics or the canonical blueprint schema. [FILE_STATUS]
- Extended IndustrialPlanner bundle/export plumbing, delivery-manifest compatibility exports, and the public exporter surface so throughput audit JSON/Markdown sidecars are written and discoverable next to the existing blueprint, compatibility, and validator artifacts. [FILE_STATUS]
- Added standalone throughput-audit CLI coverage, targeted regression tests for exact-match / mismatch / fallback / status-cap behavior, and synced example/docs/status files for the new post-Spec-22 production-conformance layer. [FILE_STATUS]
- Added a deterministic full-demand IndustrialPlanner recipe-capacity fixture plus a regeneration script, so the repo now carries a clean validator-compatible example that proves all 17 recipe-capacity rollups while honestly surfacing the remaining partial boundary-proof ceiling on the default base. [FILE_STATUS]
- Extended pure-input `boundary_storage_port` export with adjacent `item_log_admission` witnesses, taught the throughput audit to count those bindings as explicit proof, and refreshed the checked-in full-demand fixture so both final-product sink commodities now land at `proven_equivalent` while `source_ore` remains the only honest boundary partial on the default base. [FILE_STATUS]
- Refined throughput-audit overall-status reduction so boundary rollups that are explicitly `partially_proven` remain partial at the report top level instead of being collapsed into `unproven_or_insufficient`, matching the intended tri-state sidecar semantics. [FILE_STATUS]
- Added grouped export-side `item_port_log_hongs_bus` witnesses for interior-facing pure-output boundary unloaders, refreshed the checked-in full-demand fixture to use the new bottom/right `source_ore` slots, and pushed the default-base full-demand audit from `partially_proven` to `proven_equivalent` while keeping the validator clean. [FILE_STATUS]
- Generalized IndustrialPlanner boundary-bus witness synthesis from the old default-base bottom/right special case into a base-aware all-edge search: the exporter now greedily packs clean `item_port_log_hongs_bus` witnesses for any in-lot top/left/bottom/right pure-output requirement, adds multi-base regression coverage, and emits explicit warnings when a chosen base would require outside-lot bus coverage that cannot be synthesized. [FILE_STATUS]
- Reworked `scripts/build_industrial_planner_full_demand_fixture.py` into a base-aware fixture planner: it now derives the default full-demand boundary-slot layout from current `generic_io_requirements` plus exporter/validator feedback, emits optional planning-report JSON/Markdown sidecars, and fails closed on bases that are too small or that exceed the fixed canonical 70×70 anchor contract. [FILE_STATUS]
- Added a checked-in IndustrialPlanner full-demand base-support matrix plus a dedicated audit CLI, so the repo now summarizes every known base under the current 70×70 oracle: one base is fully supported, four are blocked by manufacturing-area shortfall, and `wuling_protocol_core` is isolated as the lone contract-ceiling candidate if a future outer planning representation is introduced. [FILE_STATUS]

## 2026-03-29

- Closed the remaining IndustrialPlanner translation-miss accounting gap so placeholder/empty commodities now increment structured miss counts for both `boundary_storage_port` bindings and precise facility-recipe fallback paths, while keeping geometry export intact. [FILE_STATUS]
- Refreshed the checked-in 70×70 validator benchmark evidence on the current Python 3.13 reference environment. [FILE_STATUS]

## 2026-03-28

- Hardened IndustrialPlanner commodity translation so invalid upstream-like `item_*` ids fail closed, are dropped from exported config bindings, and increment structured translation-miss accounting instead of being silently passed through. [FILE_STATUS]
- Added deterministic 70×70 IndustrialPlanner validator benchmark assets: a checked-in benchmark fixture, a reusable benchmark harness, raw benchmark JSON output, and a benchmark markdown report documenting AC-B12 evidence. [FILE_STATUS]
- Synced IndustrialPlanner governance/docs with the implemented state by adding the final Spec 22 markdown, expanding the compatibility matrix note, refreshing example-fixture guidance, and recording the new benchmark/documentation files in `FILE_STATUS.md`. [FILE_STATUS]

## 2026-03-27

- Extended `endfield-calc` TypeScript ingest so the existing adapter can consume a flat fixture directory, an extracted upstream repository root, or a `.zip` archive without manual file copying. [PROJECT_LOCK]
- Vendored a raw upstream `endfield-calc` repository fixture (`0.5.2`, commit unavailable from uploaded archive), enriched snapshot provenance with package-version/layout metadata, and added real-fixture regression coverage. [FILE_STATUS]
- Added an explicit `endfield-calc` semantic-alignment registry for the verified 17-recipe overlap with `rules/canonical_rules.json`, plus semantic diff reporting and exact-match regression coverage. [FILE_STATUS]

## 2026-03-26

- Added OR-Tools cross-version CP-SAT compatibility shims for `search_branching` enum naming and `CpModel(model_proto=...)` fallback, plus targeted regression tests for the old-surface path. [PROJECT_LOCK]
- Added optional exact-safe frontier probe scheduling, pending-probe resume handling, and probe-aware campaign telemetry without changing the certified objective or proof contract. [PROJECT_LOCK]
- Added probe operator guidance and a new scheduling spec for manual probe workflows, `--frontier-probe-mode`, and probe telemetry fields. [FILE_STATUS]
- Restored exact-contract regression compatibility after the probe-mode signature expansion by updating frontier-state test doubles to accept the new optional `frontier_probe_mode` keyword and revalidating the core search-contract suites. [FILE_STATUS]

## 2026-03-25

- Consolidated preprocess recipe / production-target / commodity metadata truth into `rules/canonical_rules.json`, slimmed `preprocess_plan.json` to an overlay contract, and updated schema/model/validator coverage without changing certified runtime inputs. [PROJECT_LOCK]
- Added frozen-compatible preprocess regeneration: `rules/preprocess_plan.json`, `PreprocessContext`, context-driven demand/template/profile derivation, and parity-report tooling without changing certified runtime inputs. [PROJECT_LOCK]
- Regenerated preprocess artifacts with clean numeric serialization, added parallel-configuration guidance, and checked in a minimal IndustrialPlanner example export bundle plus new preprocess contract tests. [FILE_STATUS]
- Added Phase-1 ecosystem upgrade scaffolding: `src/interchange/*`, `src/adapters/*`, synthetic third-party snapshot fixtures, and provenance notes without changing certified exact solver semantics. [PROJECT_LOCK]
- Added normalized catalog, compatibility manifest, export registry, build-time `endfield-calc` snapshot ingest, and viewer-side report shaping/tests. [FILE_STATUS]
- Upgraded the static web viewer with routing/power/active-port overlays, local persistence, and generated `viewer_report.json` sidecar support. [FILE_STATUS]
- Landed Phase-2 compatibility adapters: one-way `IndustrialPlanner` bundle export, compatibility-export manifest integration, and `endfield-calc` TypeScript-source ingest with diff reporting. [PROJECT_LOCK]
- Added explicit compatibility specs/matrix and adapter regressions for `industrial_planner` export, target bundle discovery, TypeScript snapshot parsing, and catalog diff reports. [FILE_STATUS]

## 2026-03-16

- Built out the current exact-safe local-capacity path, frontier guidance, and routing-core shrink work that made the certified path viable at scale. [PROJECT_LOCK]
- Tightened the separation between certified artifacts and exploratory carry-over material. [FILE_STATUS]

## 2026-03-17

- Landed static exact-core reuse, coordinate-encoded master stabilization, and exact-safe search guidance refinements. [PROJECT_LOCK]
- Continued collapsing legacy branching and cut assumptions into the current certified-only chain. [FILE_STATUS]

## 2026-03-18

- Hardened campaign persistence, resume behavior, and geometric power-coverage handling. [PROJECT_LOCK]
- Reduced precompute ambiguity between preprocess artifacts and runtime consumers. [FILE_STATUS]

## 2026-03-19

- Progressed the local-capacity oracle line that culminated in the compact exact rectangle path now used by current mainline. [PROJECT_LOCK]
- Reinforced that exploratory caps and exploratory artifacts are not exact-mode truth. [FILE_STATUS]

## 2026-03-22

- Added the production-grade parallel exact scheduler with coordinator-owned persistence and disjoint candidate execution. [PROJECT_LOCK]
- Added process-priority override support and launcher-script consolidation for stable runtime entrypoints. [FILE_STATUS]

## 2026-03-23

- Formalized canonical output delivery with schema-backed blueprint export, blueprint-first render consumers, and a certified delivery manifest. [PROJECT_LOCK]
- Locked campaign best-certified monotonicity, aligned the exact objective to `max_lex(area, min_side)`, and clarified that `50/10` is exploratory-only. [PROJECT_LOCK]
- Added spec metadata, preprocess golden regeneration coverage, numeric artifact normalization, and runtime worker-profile discoverability. [FILE_STATUS]
