---
name: phase-1-2-progress
description: 2026-05-27 Phase 1.2 spike close 收尾 + F3 special-case phase **已完成**. F3 port_exposure generator 已实现 (c768806 + b5860bc), Gemini 3-round cross-check 全 PASS (含 self-blocker guard c639063), A3 rerun 50 cert/9 family/0 unsound. GPT pro 外部审查 v14(一审)→v22(八审) 共 8 轮逐 finding 修到 CLEAN GO, v22 (sha 72a04545) 已 Windows 重建两版 (faithful+clean), 本地独立九审复审 CLEAN GO, 等 GPT pro 正式九审 (详见 handoff-windows-ninth-review-pending). spike close gate = GO_WITH_MINOR (G6a SOFT 进 P1.3A risk register). **下一步 P1.3A 主体, 从 master 起 (F3 generator 已在 master); spike 分支是 throw-away spike harness+review 数据, P1.3A 走 N=8 design 不 cherry-pick spike code**. (旧状态: 早期本文记的 "F3 仍 stub / 等四审" 已过时, 见下方 2026-05-27 终态段。)
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## ✅ 2026-05-27 终态 — F3 special-case phase 完成 + 8 轮外审收口

> **这段是最新真实状态。下面所有 2026-05-26 及更早的段是历史过程, 别当现状读。**

### F3 special-case phase: 完成

F3 port_exposure generator 之前是 Phase 1.1 stub (`return []`)。GPT pro v15 三审
catch 它是 G10 fixture coverage 真 gap, user 拍板第三条路: Phase 1.2 base 按
v16 documented NOT_GO 收口 + F3 独立 special-case phase 补齐 + 外审 GO 才进
P1.3A。**F3 已实现完毕**:

| commit | 内容 |
|---|---|
| `c768806` | feat(F3): 实现 port_exposure generator (oracle 277→344 行, 15 test, 413 pass) |
| `b5860bc` | fix(F3): Gemini round 1 — 7 处 silent skip 加 logging |
| `c639063` | fix(F3): self-blocker defensive guard (Gemini round 3 catch: 防 self-referential cut 退化成 unsound false pruning) |
| `d342784` | refactor(F9): generate_density_envelope_cuts radon D(27)→B(10) (七审 Reviewer B catch) |
| `5d214f4` | fix(gate-script): exit_criteria 用 sys.executable + F7/F8/F9 真测试名 (readiness review catch) |
| `959b6de` | chore(claude): 移除 settings.json paused 硬编码心跳 hook (交接打包时 catch) |

Gemini cross-check 3 round 全 PASS (round1 generator soundness 5/6 + round2 logging
fix + round3 self-blocker guard 数学等价)。A3 oracle emit rerun: **50 cert / 9 family
/ 0 unsound** (F3 emit 6), telemetry 加 `emit_rss_after_solve` event。

### GPT pro 外审 8 轮 (v14→v22)

spike close gate 经 GPT pro **v14(一审)→v22(八审) 共 8 轮**外部审查, 每轮 catch 不同层
finding 逐步修。关键里程碑:

- v14 一审 / v15 二审: NOT_GO (F7/F8 validator binding + F3 fixture 缺口)
- v15 三审: 接受"诚实 NOT_GO 证据包" → user 第三条路决策 (F3 special-case phase)
- v17 四审: GO_WITH_MINOR (5 项 MINOR)
- v18 五审: catch B2 toy_translator nogood_families 缺 port_exposure (100K 只 apply 88K)
- v19 六审: catch _cert_literal_pairs F3 走 synthetic fallback 不真解析 (semantics overclaim)
- v20 七审 (两 reviewer): F3 真 2-literal parse 验证 + F9 radon D + doclag
- v21: union fix
- v22 八审 (两 reviewer): GO_WITH_MINOR / PATCH_REQUIRED (F3 malformed fail-closed 不完整 + 2 NIT) → v22 已修

**v22 包 sha `72a045450d0c3dc2f0ff22d9d8d8053edaf641ce4ca1c7564e1f858369adae38`。**
**(更新 2026-05-31)**: v22 包已从 Linux 迁至 Windows, 并按 [[review-pkg-no-prompt-inside]]
重建为**两版** (faithful: `cc_context/review/phase1_2_spike_review_v22.zip`; clean/去 priming:
`phase1_2_spike_review_v22_clean.zip`; build 脚本 `build_v22_win.py` + `build_v22_clean_win.py`
均在 `cc_context/review/`)。本 session 主代理已做**独立九审复审 = CLEAN GO** (本地复审, 非 GPT 输出:
真 soundness 守卫 3/3 + 414 cuts pass + v22 fail-closed 9/9 + verdict 诚实)。**当前 = 等
GPT pro 对 faithful + clean 两版独立送审 (正式九审)。** 历史包仍在外盘
`/mnt/wd_external/zmd_review_archive/`。当前交接状态见单一 living 源
[[windows-ninth-review-pending]]。

外审方法论 + 每轮 finding 全过程记在 [[external-review-prompt-template]] +
[[review-pkg-data-completeness]] + [[review-pkg-no-prompt-inside]]。

### spike close gate verdict + 下一步

- Spike close gate: **GO_WITH_MINOR** (13 hard G PASS / 1 G SOFT = G6a wall 180s
  cap FEASIBLE+bound valid / 0 hard N)。
- G6a SOFT 是 toy master inherent, 进 **P1.3A risk register** (real PoseBoolExactMaster
  收敛不可假设 single-solve termination)。
- **下一步 = P1.3A 主体设计**。从 master 起 (F3 generator + 全 9 family 都在 master)。
  `spike/prod_scale_master_integration_20260526` 分支是 throw-away spike harness +
  review 数据 (PR #1 verdict-only style), **P1.3A 走 N=8 parallel design, 不
  cherry-pick spike code**。P1.3A 5 项 Layer 2 risk (Convergence / G6a under real
  master / adversarial inject / multi-iter LBBD / F1-F3 patch hold @ 100K) 全 open,
  P1.3A 主体应 cover。

---

## 🟠 2026-05-26 三审 NOT_GO documented gap → F3 special-case phase (历史过程)

v15 三审 GPT pro verdict: 接受 v15 作为"诚实 NOT_GO 证据包", 拒绝 spike close
gate close. 3 patches land:

| Commit | branch | 内容 |
|---|---|---|
| `b3c370e` | master | patch 0001 — repro project root walk-up (PROJECT_LOCK.md + src/cuts 双标记) |
| `f17f13e` | master | patch 0002 — F8 streaming reachability (新 `any_target_reachable_from_pc` 替代 build_power_network+bfs, 解锁 audit 大半径 case 11M pair O(n^2) 卡死). 398 pytest + mypy + ruff clean. **Gemini cross-check PASS** (4 步严格数学等价证明: 三角不等式 cutoff + Chebyshev⊇Euclidean + BFS 语义等价 + edge case 健壮性) |
| `f54f4f8` | spike | patch 0003 — verdict.md RSS evidence boundary 拆 (build RSS max 0.866GB / phase_b_results after-solve 1.029GB / raw telemetry 无 1.03GB event) |
| `3b0cc76` | master | v16 build script |

v16 zip `/home/zhuran24/linwin_share/phase1_2_spike_review_v16.zip` sha
`32b191d8835913f449bbc6fcce63fce9c86be5612235d9864dcea1c9916c0f41`.

### Spike close gate verdict — 永久 "NOT_GO until G10 is repaired"

F3 port_exposure generator 仍是 Phase 1.1 stub `return []`. A3 oracle emit
fixture 44 cert / 8 family (缺 F3) 不达 G10 ≥45 + 9 families. GPT 明确:
doc-only re-scope 维持 NOT_GO 可接受, 但永远不能从 NOT_GO 改 GO. F3 fixture
不能用 "P1.3A convergence later" 豁免 (F3 是 Sizing 层 finding 不是
Convergence 层).

### User 2026-05-26 phase boundary 决策

**第三条路** (既非 P1.2 内 scope creep 做 F3, 亦非 P1.3A 主体 fold F3):

1. Phase 1.2 按 v16 "NOT_GO with documented gap" 完结 (不假装 close)
2. F3 single special-case phase 启动 — 独立 phase 不属任何 main phase
3. F3 done + GPT 四审 GO 才进 P1.3A 主体

Per [[main-merger-scope-creep-bias]]: 严守 phase boundary, F3 不 fold 进
P1.2 close gate (避免 scope creep), 也不 fold 进 P1.3A 主体 (GPT 三审明确
F3 不能 convergence later 豁免). User catch + force 独立 phase 是同种
scope-boundary audit, 8 路 sibling + 2-3 round Gemini 都看不到这层.

### F3 special-case phase implementation 状态

- F3 spec `docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md`
  v1.0 173 行 frozen
- Family validator `src/cuts/families/port_exposure.py` 196 行 Phase 1.1
  已 land (validator 完整, 只 oracle stub)
- Oracle `src/cuts/oracles/port_exposure_oracle.py` 55 行 stub
  (`return []` placeholder, 待 wrap cand C `boundary_constraints.py`)
- Implementation 参考: `docs/research/cand_c_column_generation_phase2_20260521/boundary_constraints.py`
  (per-(cell, dir) net flow equality)
- Per [[design-phase-n-parallel-agents]] frozen spec → code 翻译 **不触发**
  N=8 parallel design — sub-agent 单线实施即可
- Per [[gemini-review-algorithm-math]] 每 commit Gemini cross-check 循环
  到 GO/minor

### F3 phase exit criteria (待满足全部进 P1.3A)

1. F3 generator implementation + pytest 398+ pass + mypy/ruff/preflight
2. Gemini per-commit cross-check 循环到 GO/minor
3. Spike runner 加 100K after-solve RSS raw event (GPT 三审 finding 4 跟
   F3 一起 fix)
4. 重跑 A3 oracle emit fixture 验 ≥45 cert / 9 family / 0 unsound
5. v17 包 build (新 build script) → GPT pro 四审 GO

## 🔄 2026-05-25 POST-PATCH state

GPT pro audit (`docs/research/phase1_2_gpt_pro_audit_20260525/`) verdict NOT GO
后 3 commit 落地:

| Commit | Finding 修 |
|---|---|
| `68fa7f0` fix(cuts) | F1/F2 BLOCKER — F7/F8 validator 加 `_validate_facility_cells_match_pose_registry` |
| `a3414ee` fix(cuts) | F3 HIGH — 7 oracle 全改 `source_digest = compute_source_digest(state)` |
| `035bd21` docs | F6 LOW — plan doc `lifecycle.py:743-751` → `::step_8_apply_to_master` 函数名 ref + audit archive |

Post-patch verify:
- 395 → 398 cuts pass (+3 regression test)
- mypy --strict 35 src 0 errors / ruff / vulture / bandit clean
- 4 原 reproducer post-patch: F1/F2 validator `ok` → `unsound`, F3 step6
  `QUARANTINE` → `HOLD` scope_eq_computed `True`

## ❗ 仍 open

- **Finding 4 MED** (F8 power_network `_pole_pole_edges` all-pairs, R=50 单测
  11-28s): defer 到 Phase 1.3, 不入 1.5+. 真接 master 前要 spatial bucket /
  grid-neighborhood / DSU 重构, 加 psutil RSS + wall microbench 门禁.
- **Finding 5 HIGH** (mini Step 8 spike 50 BoolVar toy 不足以当 close gate):
  framing critique 不是 code bug. 真 close Phase 1.2 → P1.3A 需 prod-shaped
  spike. **5 路 opus parallel design in flight** at
  `docs/research/prod_scale_spike_design_20260525/<slant>_design.md`. main 合
  merger 后实施 spike, verdict GO 才 close.

## v13 review pkg post-patch

`/home/zhuran24/linwin_share/phase1_2_post_patch_review_v13.zip` (sha256
`2d7d0738c941ff545328e3ab5602c758c9cc9ffb2e1e94e77285629882cf1efa`, 7.21 MB).
反映 post-patch 状态, 仍含 Finding 4/5 未解决 + GPT audit archive.

**未送 GPT 二审** — 决定改打 v14 (含 spike GO verdict) 一起送, 见下.

## 🟢 2026-05-26 spike GO_WITH_MINOR

GPT pro audit Finding 5 close gate 走完: N=8 parallel design + main merger +
3 round Gemini cross-check + user scope creep audit (catch leak P1.3A 主体) +
spike Phase A/B 实施. 10 commit on `spike/prod_scale_master_integration_20260526`.

### Spike Phase 流程

| Phase | Commits | 关键 G/N |
|---|---|---|
| A1 branch + off-limits enforce | `09da356` | 8 项 off-limits PR-rebase enforce |
| A2 failfast probe (50 inst) | `6679f34` | G17 PASS 3.4s ≤ 15s |
| A3 oracle real-emit 44 cert | `7922676` | G10 PASS 0 unsound (44/45 target) |
| Round 3 archive 补 commit | `a32a796` | Gemini round 3 verdict.md 漏 f7b88b6 |
| A report | `755ff59` | phase_a_report.md |
| B1 toy translator | `292c3a4` | 81K BoolVar + 9 family translator |
| B4+B5 filter mock + telemetry | `e121800` | 10 iter mock + RSS/proto/dark_matter hook |
| B2 scale ramp | `c4f2e35` | G1-G4b/G5/G7/G8/G9 全 PASS |
| B3 feasible smoke | `3a9d507` | G6a SOFT-FAIL (wall 180s cap), G6b PASS |
| B6 full run + verdict.md | `c3e5078` | overall GO_WITH_MINOR |

### Sizing 数字 (Finding 5 #1/#3/#4 Full cover)

| 挡位 | build | translator | solve | RSS | proto | status |
|---|---|---|---|---|---|---|
| 0 cut | 2.02s | 0s | 0.71s | 0.61GB | 16.3MB | OPTIMAL |
| 1K | 2.04s | 0.01s | 0.74s | 0.73GB | 16.3MB | OPTIMAL |
| 10K | 2.17s | 0.13s | 0.73s | 0.83GB | 16.6MB | OPTIMAL |
| 50K | 2.71s | 0.67s | 0.81s | 0.83GB | 18.0MB | OPTIMAL |
| **100K** | **3.38s** | **1.34s** | **0.89s** | **1.03GB** | **19.7MB** | **OPTIMAL** |

vs G criteria:
- G4b 100K build ≤ 600s: **3.38s ✅ 300× margin**
- G8 RSS ≤ 20 GB: **1.03GB ✅ 24× margin**
- G9 proto ≤ 1 GB @ 100K: **19.7MB ✅ 50× margin**

### G6a SOFT-FAIL (唯一 minor)

10K known-feasible cuts (via IP v2 blueprint hint) → solver 180s 顶 cap,
但 status FEASIBLE + `best_objective_bound=76884` 有效 + obj=76795 (gap
0.12%). **不是 Presolve 瞬间崩 anti-pattern** (N2 是防 INFEASIBLE wall ≤ 1s
不是 FEASIBLE wall = cap). agent 解读 "soft-fail accept" — P1.3A 应该
**不假设 single-solve termination** at 81K + 10K cut scale.

### Q8 semantic gap 文档化 (per MERGER §5.2)

Spike GO close *Sizing*, **不** close *Convergence* / *Adversarial robustness*.
Layer 2 risk 5 项入 P1.3A risk register:
1. Convergence under real PoseBoolExactMaster (+ ExactlyOne + port-linking + anti-overlap)
2. G6a wall behavior under real master constraints
3. Adversarial cut inject (50 bad / 9950 good)
4. Multi-iter LBBD convergence (L12/L16/PCR-CUT P5 reference)
5. F1/F2/F3 patch hold at 100K scale (GPT pro Layer 2 catch pattern 仍 applicable)

### 实际工时 vs estimate

- Phase A: ~4-5h Claude / 1-2h wall (estimate 3.5-5h / 0.5-1.5h)
- Phase B: ~2-2.5h Claude / 205s wall (estimate 6-9h / 3-5h — **wall 50× faster** because toy master 极松 solve 秒级 + Claude 估值偏 wall 而非 Claude pace)
- Total spike: ~6-7.5h Claude / ~1.5h wall (estimate 8-12h / 4-7h)

### Next

v14 review 包 build (含 patch verify + spike GO_WITH_MINOR verdict + 3 round
Gemini archive + 10 spike commit) → 送 GPT pro 二审 → 若 GPT GO 启 P1.3A
主体 design (N=8 parallel per [[design-phase-n-parallel-agents]]).

---



## 🚨 2026-05-25 后续 — GPT pro audit REVERT Phase 1.2 close

包 `phase1_2_close_review_v12.zip` (build `cb8e347`) 送 GPT pro 后 verdict 是
**NOT GO**. 5 个 finding 全本地 reproduce 成功:

| # | sev | 问题 | 反例 |
|---|---|---|---|
| 1 | BLOCKER | F7 `power_hitting_set.py` validator 不验 `facility_cells ↔ candidate_placements[facility_pose_id].occupied_cells` 真 footprint | 真 pose 在 (0,0)-(2,2), cert 写 (30,30)-(32,32) — validator `ok`, evaluator `True` → false-positive cut 禁掉真 pose |
| 2 | BLOCKER | F8 `power_grid_reach.py` 同 pattern | 真 pose footprint 完全 reachable, cert 写 (60,60)-(62,62) — validator `ok`, evaluator `True` |
| 3 | HIGH | 7 oracle 写 `state.source_digest or compute_source_digest(state)` — stale digest → cut scope=stale → step 6 QUARANTINE | `state.source_digest='stale-...'` → cuts 生成 OK 但 scope_digest 是 stale → step6 = QUARANTINE |
| 4 | MED | F8 `power_network.py` `_pole_pole_edges` all-pairs, R=50 单测 11-28s | full pytest src/tests/cuts 在 300s 内未完成 |
| 5 | HIGH | Mini Step 8 spike 50 BoolVar toy 不能支撑 "prod integration path clear" 结论 | spike INFEASIBLE early stop, 真 prod 266 inst × ~280K pose 没测 |
| 6 | LOW | `docs/项目说明/09_phase_1_3_plan.md:36` 行号 stale | 写 `lifecycle.py:743-751`, 实际 `step_8_apply_to_master` 在 `1005-1010` |

audit archive: `docs/research/phase1_2_gpt_pro_audit_20260525/` (AUDIT_REPORT.md +
patches/0001-bind-power-family-pose-cells-and-digest.py 210 行 + 3 repro script).
GPT 自报 patch 后 `3 passed in 4.28s`. Patch apply + verify 闭环 spawn opus
agent in flight.

**Root cause**: BLOCKER 1/2 是典型 Layer 2 "假 cert 能 pass" attack, 跟
[[adversarial-soundness-audit]] memory 完全 align — Gemini 强 Layer 1
(spec↔src↔data 接合), GPT pro 强 Layer 2 (adversarial). 20 round Gemini
cross-check 全 close 没 catch.

**对 [[phase-1-1-go-blessed]] / mini Step 8 spike GO 的影响**: Phase 1.1
不受影响 (F1-F4 不在 audit scope). mini Step 8 spike Finding 5 verdict
降为 "API translator sanity check 通过, 但不足以当 Phase 1.3A close gate".

---



Phase 1.2 P1.2B implementation进度 (2026-05-24, master branch).

## 完成 milestone (3/5)

### F5 pattern_nogood ✅ GO_WITH_MINOR
Commits: `11f5337` (initial) → `3d93b1d` (Gemini round 1 fix 4 finding) → `ca60a35` (round 2 fix 4+2 LOW) → `9cd676a` (round 3 minor 2 + close)

3 round Gemini cross-check 总 catch 14 finding. Files:
- `src/cuts/helpers/bounded_core_minimizer.py` — deletion-based bounded MUS
- `src/cuts/oracles/pattern_nogood_oracle.py` — SubProblemOracleAdapter Protocol + registry + generator
- `src/cuts/families/pattern_nogood.py` — 7-phase validator

Phase 1.5+ defer (Gemini 接受 trade-off):
- #2 deletion O(n) on 150-literal → QuickXplain
- #6 module-level registry → multiprocessing.spawn worker init hook

### F9 density_envelope ✅ GO
Commits: `f2d8f31` (initial) → `515aed4` (R1 fix 3 finding) → `e3aa3e9` (R2 fix 2 finding) → `6153ce5` (R3 WRONG patch cert_max=0 reject) → `0bed978` (R4 revert R3 + positive test)

5 round Gemini cross-check; R3 wrong patch revert. R4 verdict R4 revert CORRECT. R5 clean GO + 0 new finding. Files:
- `src/cuts/families/density_envelope.py` — 9-phase validator + evaluator + watcher_keys
- `src/cuts/oracles/density_envelope_oracle.py` — generator

Phase 1.5+ defer:
- #2 NP-hard tight-K validator replay (paradigm trade-off 同 F5 trust oracle)

### F2/F4 generator + helper ✅ 3 round GO_WITH_MINOR (close)
Commits: `92224c4` (initial) → `01d368a` (R1 BLOCKER Dinic recursion → iterative + LOW bitset padding) → `d5e653d` (R2 LOW F4 blocking_facilities cert carry) + R3 close

Files:
- `src/cuts/helpers/dinic_node_split.py` — Dinic max-flow iterative + BFS reachability + frontier separator
- `src/cuts/oracles/cutset_oracle.py` — F2 Dinic-based (edge-only mode)
- `src/cuts/oracles/component_reach_oracle.py` — F4 BFS-based + separator extract

Validator + evaluator 已在 Phase 1.1 R3 land (`families/cutset.py` + `families/component_reach.py`). Phase 1.2 仅填 generator algorithm.

Phase 1.5+ defer:
- F2 LP dual algebraic witness (witness_blob_b64=None in Phase 1.2)
- True node-split (cell_cap < ∞) when belt capacity binds + Phase 1.5+ cell-cap cross-check schema upgrade
- PCR-CUT patch enumerate integration
- Multi-commodity F2 aggregate (Phase 1.2 是 per-commodity per cut)
- F2 cut_size 命名 → cut_capacity 重命名 (edge_capacity>1 时 validator fix)
- F2/F4 dedicated oracle tests

### F6 shape_packing_hall ✅ 3 round close (Phase 1.2 GO + Phase 1.5+ defer)
Commits: `6adc5fd` (initial 27 test) → `9fac6d6` (R1 1 CRITICAL + 1 HIGH + 2 MEDIUM + Gap B) → `97388a0` (R2 1 CRITICAL evaluator scope check + 2 HIGH generator default-disabled + missing-key-skip) + R3 close

5 parallel opus subagent design merger 进 final design:
- correctness-paranoid: 10 phase validator + spec self-inconsistency (group.demand=46 全 group vs per-region 23)
- throughput: 3-layer cache + by_ghost+by_region+by_group watcher (no by_cell)
- adversarial: 20 attack matrix + 4 patches
- integration: F6 plug benders_loop:~4341, path c (outer-loop reject) Phase 1.2
- minimum viable: helper baseline_partition.py 已 P1.4 land 复用

Files:
- `src/cuts/families/shape_packing_hall.py` — 11-phase validator + O(1) evaluator (scope drift guard) + watcher_keys
- `src/cuts/oracles/shape_packing_hall_oracle.py` — generator (Phase 1.2 default-disabled, Phase 1.5+ region_demand_overrides 接 master.solution)
- `src/cuts/helpers/baseline_partition.py` — 已 P1.4 land
- 35 test (15 schema_err + 7 unsound + 5 evaluator + 3 watcher + 5 generator)

Phase 1.5+ defer (sound 但 wiring/perf 议题):
- Multi-region union Hall (left+bottom (0,0) corner 共享, spec §10 #5)
- cert.region_demand watcher / master_iteration tracking (R3 stale-demand finding)
- LP dual / Farkas algebraic witness
- Multi-shape Hall ILP feasibility (PARTITION-reducible)
- Interior region shape_hall
- F1 ↔ F6 dominance dedup (perf)

### F7 power_hitting_set ✅ 2 round close (Phase 1.2 GO + Phase 1.5+ defer)
Commits: `c30d681` (initial 25 test, single-case cert_kind "power_cover_emptyset_ghost") → `9f21901` (R1 CRITICAL fail-open fix — facility_cells exclude in validator + oracle, real data verify pole 2×2 not spec's 1×1) → `9b14ed4` (R2 close: F1 WRONG / F2 defer / F3 LOW dead code rm)

5 parallel opus subagent design merger:
- correctness-paranoid: CRITICAL pole 2×2 not 1×1 finding (verified canonical_rules);
  metric must be Euclidean source-of-truth via helper; cell_owner causation defer Phase 1.5+
- throughput: lazy per-candidate bucket, ~ms per call
- adversarial: 15+ attack matrix; needs_power=False catch (spec 漏)
- integration: post-master L16 paradigm wrap via SubProblemOracleAdapter Phase 1.5+
- minimum viable: 7-phase validator + 3 file structure + cell_owner causation defer

Files:
- `src/cuts/helpers/power_cover.py` — compute_cover_set helper (pole 2×2, Euclidean)
- `src/cuts/families/power_hitting_set.py` — 7-phase validator + watcher_keys
- `src/cuts/oracles/power_cover_oracle.py` — generator (default-disabled per F6 pattern)
- 25 test (F3 fixture + 7 schema_err + 7 unsound + 2 evaluator + 2 watcher + 6 generator)

Phase 1.5+ defer:
- cell_owner causation multi-literal cut (cert_kind "empty_coverset_cell_owner")
- active_assumptions tracking (power_pole_radius / power_pole_shape)
- L16 lazy_power_completion swap to F7 typed cut (current shadow-only)
- Hitting set generalize (min-size不够 case spec §1d)
- Pole shape generalize / metric enum
- O(N) pose lookup → dict index
- Float sqrt → int squared
- Spec text 1×1 → 2×2 pole update

### F8 power_grid_reach ✅ 5 round close (Phase 1.2 GO at R5, ~12 finding addressed)
Commits: `4be1b60` (initial 21 test) → `b9ab24a` (R1 fix 3 CRITICAL: full pole-anchor enumeration + 9×9 multi-cell pc + evaluator selected_poses) → `fe7c239` (R2 fix 3: cell-to-cell metric + cell-center segments + pole-set dedup; #4 Gemini misread JSON rejected) → `29b64d0` (R3 fix 3: any-pair segment scan + active_assumptions audit + verifier dispatch power_pole_jump_radius+protocol_core_position) → `3b9c8b3` (R4 fix 4: evaluator protocol_core position + validator SoT cross-check phase + negative-coord parse) → `4721c04` (R5 GO close, 0 new finding, 3 disproved hypotheses cited)

**F8 needed 5 rounds — longest in Phase 1.2 (F2/F4/F6/F7/F9 all closed 2-3 rounds)**. Gemini R5 explained: not systemic blindness, just inherent complexity of global connectivity cut (dynamic geometric graph + BFS + multi-axis SoT cross-check). Each round caught real new bugs in different layers.

5 parallel opus subagent design merger:
- correctness: protocol_core anchor state-dependent (7200 candidate poses);
  pole_to_pole jump radius NO canonical field (caller-supplied); Liang-Barsky
  boundary tangent conservative block
- throughput: build_power_network ~1.5s/call → R2 added anchor-distance early
  reject (~99% rejection at R=5 on 70×70 grid, 180s→60s test); evaluator MUST
  trust scope-binding (chose monotone-preserved invariant over cache); cert
  deliberately omits power_graph_b64 (~4MB/cut otherwise)
- adversarial: 24 attack matrix + 5 spec §7 patches → all caught by SoT phase
- integration: post-master plug benders_loop._run_power_placement_subproblem
  (L16 paradigm); F7+F8 mutual exclusion (F7 first)
- minimum viable: 7-phase validator (post-R4: 9-phase), cert NO graph snapshot,
  default-disabled

Files (final state at 4721c04):
- `src/cuts/families/power_grid_reach.py` — 9-phase validator + O(1) evaluator
  with protocol_core position check + watcher_keys + 8 extracted helpers (radon
  hygiene: D(27)→B(10) avg B(5.92))
- `src/cuts/oracles/power_grid_reach_oracle.py` — generator (default-disabled;
  emits active_assumptions audit trail)
- `src/cuts/helpers/power_network.py` — build_power_network with pc_cells multi-
  cell + any-pair cell-to-cell distance + cell-center segment + anchor-distance
  early reject (4 sub-helpers: _can_jump / _pole_pole_edges / _pc_internal_edges
  / _pole_pc_edges)
- `src/cuts/helpers/power_cover.py` — added public `enumerate_valid_pole_anchors`
- `src/cuts/assumptions/verifiers.py` — added `verify_power_pole_jump_radius`
  (cross-check canonical_rules.power_pole.power_coverage_radius) +
  `verify_protocol_core_position` (9×9 bounds + cell_owner cross-check)
- ~30 F8 + helper + verifier test (was 21, +9 across R1-R4 regressions)

R5 GO blessed: Phase 1.5+ defer items (per Gemini final list):
- introduce dedicated `pole_to_pole_jump_radius` canonical field (spec §1c
  simplification: Phase 1.2 uses pole→facility radius as pole→pole)
- widen watcher to BoundingBox(facility, R_jump + pc_size) for cell_owner-
  release reconnect scenarios
- multi-literal support for cell_owner-caused disconnects (cert_kind alt)
- exterior_blocks_jump witness_kind
- LP dual / Farkas algebraic witness
- Multi-protocol_core sources (spec §10 #4)
- Incremental BFS for propagator hot-path
- BState `protocol_core_anchor` field wiring

## Gate state (post F8 R5 close, 2026-05-25)

- pytest: **2632 passed** / 60 skipped / 0 fail (python + python -O)
- ruff / mypy strict (40+ source 0 errors) / vulture / bandit: PASS
- radon: Average A-B
- exit_criteria: 3 PASS / 8 PENDING_PHASE_1 / 0 FAIL

## 剩余 — 无 (Phase 1.2 已 close)

Mini Step 8 spike (commit `3f1c581`) verdict: **GO**. 5 distinct CP-SAT
constraint forms cover 6 family (F1/F9 linear-area; F3/F5/F7 multiset-
nogood; F2/F4 edge-cut-witness; F6 region-Hall; F8 per-pose-forbid). 全
用 `Add` / `AddLinearConstraint` (no AddLazyConstraint needed). 10K cuts
build = 114ms, solve = 2ms (~250x headroom vs 30s GO threshold).

Phase 1.2 plan COMPLETE: F5 ✅ → F9 ✅ → F2/F4 ✅ → F6 ✅ → F7 ✅ → F8 ✅
→ mini Step 8 spike ✅ → **Phase 1.2 全 close**.

## Active protocols

- [[design-phase-n-parallel-agents]] v1: N=5 子代理 design parallel + main merger
- [[gemini-review-algorithm-math]] v4: 每 commit 后 Gemini cross-check 循环直到 GO/minor; src phase prompt 必含**真数据 paths** + **armor strict mode** + **反 GO ritual**
- [[gemini-prompt-audit-mode]]: 历史 r27/r28/r29 GO 章 ritual 反例
- [[phase-1-1-go-blessed]]: 上游 Phase 1.1 5 轮外部 deliverable history

## Compaction context (2026-05-25 session, post F8 R5 close)

Phase 1.2 **7/7 families closed** (F5/F9/F2-F4/F6/F7/F8 all Gemini GO). 下次 main 接续:

1. **Mini Step 8 spike** (per [[gpt-pro-p1-2-in-progress-review]] #6):
   - 6 family 形态 (literal / area / edge-cut / hall-marriage / power-hitting / power-grid) 转 CP-SAT
   - 10K cuts rebuild cost 排雷
2. Mini Step 8 spike GO → **Phase 1.2 全 close**

Pending audit task (per memory):
- [[gpt-pro-p1-2-in-progress-review]] action 4 (F5 orbit-aware 132 instance)
- [[gpt-pro-p1-2-in-progress-review]] action 5 (F9 non-trivial envelope fixture)

Post-compaction F8 round commits (6 added this resume session):
- F8 R1 fix (b9ab24a): full pole-anchor enum + 9×9 multi-cell pc + evaluator selected_poses
- F8 R2 fix (fe7c239): cell-to-cell metric + cell-center segments + pole-set dedup
- F8 R3 fix (29b64d0): any-pair segment scan + active_assumptions + verifier dispatch
- F8 R4 fix (3b9c8b3): evaluator pc-position + validator SoT phase + negative-coord parse
- F8 R5 close (4721c04): GO verdict + Phase 1.5+ defer list
- Prior pre-compaction commits (14): F2/F4 R1-R3 + GPT review sound≠converge + F6 R1-R3 + F7 R1-R2 + F8 initial

F8 stats: 5 rounds, ~12 finding (R1: 4 + R2: 3+1rejected + R3: 3 + R4: 4 + R5: 0). Longest convergence in Phase 1.2 — Gemini R5 verdict explained as global connectivity inherent complexity, not systemic blindness.
