# 《终末地》Endfield IndustrialPlanner — certified-exact 求解器:项目 handoff

> 这份文档是把本项目交给【另一台机器上从零接手】的工程师 / CC 用的**完整、诚实的史实 + 决策记录**。正文六章由 6 个维度的独立调查合并而成——每个维度各派一个 Opus agent 和一个 Codex agent 独立去挖 `cc_memory`(170 条协作史料)/ `CHANGELOG.md` / `PROJECT_LOCK.md`(~127KB)/ git(180 commit)/ 开发日志,再把两份合并、标注分歧;主导 CC 又叠加了对近期 PR2 工作的一手记忆。

## 怎么读这份文档

- **这是记录,不是命令。** owner 明确希望你【独立重新摸索】,借你的新视角发现我们可能没发现的盲点。所以每个决策尽量附了 rationale + 认真考虑过但被否决的替代方案 + 未决残余;哪里是开放问题、哪里可能没审透,都诚实标出(尤其见第 6 章「开放问题 / 可能盲点」)。**别把本文当"照这么做"的教条。**
- **权威顺序:** `PROJECT_LOCK.md`(失败关闭的 `F-*` / `PCR-*` / `CUT-*` 条款)是 release 边界的最高权威;与 `CLAUDE.md` / `NAV_MAP.md` / 旧文档 / docstring / 任何记忆冲突时,以 `PROJECT_LOCK.md` 为准(它自己声明)。`CHANGELOG.md` 是日期戳历史,其中的测试数 / 状态是【当时快照】、不是当前工作树断言。
- **凡涉及"证明 / 认证 / exactness"的断言,信任前先对着引用的源自查**(PROJECT_LOCK 条款 / 源码 `file:line` / 目标测试 / 相应 gate)——别因为文档这么写、或某测试过了、或某方法可用,就当"已认证 / 已发布"。
- 文中 **⚠** 标记 = 两份独立调查(Opus / Codex)在此处有出入或一方独有,已保留双方信息供你自行判断。

## 现状速览(一分钟看懂当前在哪)

- **项目:** 为《明日方舟:终末地》70×70 基地(266 个 mandatory 设施)求解【certified-exact 最大空矩形】,目标 `max_lex(area, min_side)`。核心铁律 = `certified_exact`(唯一能产证明材料的路径)与 `exploratory`(启发式 / 诊断,**永不能升为证明**)两条路径严格隔离。
- **P1.2 = 当前认证里程碑,状态 = RELEASE-BLOCKED:** 被一道【owner 仓库外人工 clean-review 计数】的手动门卡住(该 clean-review 计数 **owner-maintained outside the repo**;`next_allowed=false`);`main.py` 只停在 `CANDIDATE_PROPOSED`——生产 supervisor seal 入口已由 `scripts/run_supervisor_seal.py` 落地为独立命令,不会由 `main.py` 自动铸出 durable `CERTIFIED`。**别把"seal 方法存在 / 某测试调用过 / 生产入口存在"当成 owner 批准的 release closure。**
- **近期主线 = PR2 硬化**,尤其 **PR2 #5「close-kernel 第二道门」**:一套 AST / source-sha checker(`scripts/check_p1_2_proof_obligations.py`)+ runtime 父进程锚(`src/search/certified_artifact_contract.py`),防"能 reseal checker 的恶意维护者保 checker 全绿却掏空 runtime proof"。经 round-8→18 的多轮外审(GPT Pro panel)+ 本地 codex 对抗审,**结构性 BLOCK 已清零**;剩 3 类【已被 owner 裁定接受】的残余(详见第 4、6 章):**F**(import-time 执行完整性,图灵完备无界,单列专门线 #5-F)/ **checker-self**(checker 无法递归自证自己)/ **A4 witness-body 动态反射重绑**——三类共同兜底 = "相关源文件已被 source-sha 逐字节钉死 → 改它必留显眼 diff → 人工 clean-review"。
- **当前 HEAD(2026-07-04 更新):** PR2 #5 close-kernel 经 round-19/20 硬化后已由合并提交 `6e06922` **合入 main**(round-20 = `2413cc2`);mixflow-routing 数学面修复批次 1+2+3 也已合入(`3c99ed0`)。本文大量段落记录的是合入前快照(round-18 `9bbb3a6`、main `b35e5f9`——这些 hash 在本交付副本均不可解析,只当叙事线索;V99 blob 断言同属当时快照)。核对现状一律以 `git log` 实测为准。
- **PR2 剩余项(真实 backlog、当前不排期——owner 2026-07-04 澄清:round-20 画 TCB 线只停外审循环,不取消这些待办):** #1(最小 TCB 闭包,含 #5-F import-time 专门线)、#2/#3(loader / read-once 精化)、#5 独立枚举(候选域独立重推导)、#8(argv0/contract digest)、#9b/#9c(OS 写隔离 / 原生 TOCTOU)。#7(certify 生产入口 = go-live 最后通电)已于 2026-07-04 由 `scripts/run_supervisor_seal.py` 落地,但只补"supervisor 可执行入口"这一条机器条件。
- **一个部署前必做:** `pr2_dependency_floor_manifest.json` 现在钉的是【审计 Linux env 字节的占位】、非生产 canonical;生产前必须在 CachyOS + Py3.13 venv 重生成 + 审 + 重钉。

> **📌 2026-07-04 事实更新(后于正文六章的调查基线,读正文前先看这段):** 正文六章按 2026-07-02 前后的调查快照写成,其中三件事后来已发生——① `pr2-5-domain-frontier-gate`(PR2 #5 close-kernel)经 round-19/20 后已由 `6e06922` **合入 main**,owner 已画 TCB 线**停止 close-kernel 外审循环**(round-19/20 外审不发;画线≠取消 PR2 深化 backlog,见上「PR2 剩余项」);② mixflow-routing 数学面修复批次 1+2+3 已由 `3c99ed0` 合入,批次 3 尾巴与推迟项已关闭(`9aa4176`/`a8ea631`/`a731764`);③ PR2 #7 supervisor seal 生产入口已由 `349c56c` 落地。**因此正文中一切"未合入 / 等第 12 轮外审 / round-18 是当前进度 / main=`b35e5f9` / 新机器拿不到 `9bbb3a6`"的表述均为合入前史料快照,以本节为准。** P1.2 仍 OPEN/BLOCKED(owner 手动门),这一点没变。

## 目录

1. **项目本质、架构与认证边界** —— 这项目是什么、`certified_exact` vs `exploratory`、solve pipeline 每层证什么、frozen artifacts。
2. **认证 / 发布链、P1.2 与为什么 release-blocked** —— producer→supervisor seal→publisher 三分、手动门、proof-obligation gate。
3. **早期史** —— PR1 soundness 三轮外审、capsule 架构推翻、supervisor L0/L1 重做、算法核心 / 吞吐认证死路。
4. **PR2 完整 saga** —— #8/#9a + close-kernel 第二道门 round-8→18 + denylist 不收敛→3 类残余 + reseal ritual + 剩余项。
5. **不变量、坑与工具 / 工作流** —— reseal/LF/V99 floor/strict JSON/preflight/记忆系统/codex 路由/es/codegraph。
6. **项目现状、剩余工作与【开放问题 / 可能盲点】** —— 最关键:诚实列出"我们这套进路对不对、哪里可能没审透",给你从零摸索发现盲点的空间。

---

*以下六章为各维度独立调查合并结果(Opus + Codex 双源)。分歧处以 ⚠ 标注。*


---

# 第 1 章 · 项目本质、架构与认证边界

> **What this section is.** A faithful, traceable record of *what the Endfield IndustrialPlanner solver is, what it claims, what it does not claim, and how the "certified" boundary is drawn* — written for an engineer picking this up cold on another machine. Read it as a decision record, not marching orders. Where a rule is stated, its rationale and rejected alternatives are stated too; where something is unfinished, open, or reversed, it is marked as such. Verify anything proof-sensitive against the cited source before relying on it. This chapter merges two independent read-only investigations (one "Opus", one "Codex"); where they diverge, both readings are preserved and flagged with **⚠**.
>
> **Authority order (this matters).** `PROJECT_LOCK.md` is the release-boundary authority. When it conflicts with `CLAUDE.md`, `NAV_MAP.md`, older docs, docstrings, or any cc_memory note, `PROJECT_LOCK.md` wins (it says so itself, line 6). `CHANGELOG.md` holds dated history whose test counts / status claims are *historical snapshots*, not current-worktree assertions (CHANGELOG.md:4-5). The canonical predicate authority is `docs/项目说明/01_overview.md` §1.1/§1.3, mirrored by `PROJECT_LOCK §1A`.
>
> **Read-only provenance / tooling caveats (from both passes).** Neither investigation modified project files. The working tree already carries pre-existing dirty/untracked items (including `cc_memory/memory.db` and many logs / package dirs); these are not artifacts of the investigation. `cc_memory` search is lexical/LIKE-style: multi-word/broad queries repeatedly return no matches — shorten to 1–2 short tokens (`P1.2`, `candidate`, `preprocess_plan`, `50`) to hit. **⚠ Broken cc_memory id:** the witness-split note is `p1-2-witness-split-block-2026-06-21` (hyphenated date); the un-hyphenated `p1-2-witness-split-block-20260621` does **not** resolve. Codex also found a relation edge referencing a split-witness node id that returns "unknown node" on direct `read` — recorded as a stale/unreadable link, not used as evidence.

---

## 1. What this project actually is

A **certified-exact maximum-empty-rectangle solver** for base layouts in 《明日方舟：终末地》 (Arknights: Endfield). Concretely:

- **Grid:** a single **70×70** base. The only active certified base is `valley4_protocol_core` (70×70). Six other IndustrialPlanner bases are preserved as `future_scope` and are explicitly *not* part of the active checked-in / CI contract, and P1.2 conclusions must **not** be extrapolated to them (CLAUDE.md:8-13, :248-249; PROJECT_LOCK §2A lines 243-248). One of those, `wuling_protocol_core`, is 80×80, which the 70×70 canonical schema cannot express (CHANGELOG 2026-05-08, 2026-03-30).
- **Mandatory facilities:** exactly **266** mandatory facility instances that must be placed. Opus verified `data/preprocessed/mandatory_exact_instances.json` is a list of length 266; CLAUDE.md prose matches.
- **Objective = `max_lex(area, min_side)`** — lexicographically maximize first the empty rectangle's *area*, then its *minimum side length*. Confirmed: `rules/canonical_rules.json::globals.empty_rectangle` = `{"objective": "max_lex_area_min_side", "min_side_admissibility": 6}` (CLAUDE.md:27-31; PROJECT_LOCK §1 lines 10-14; canonical_rules.json:7-23).
- **`min_side >= 6` is a candidate *admissibility* rule — NOT an objective tie-break.** The number 6 is the production project floor (`min_side_admissibility`); toy/test projects may use smaller explicit floors. The authority is the canonical rules JSON, not any hard-coded constant. Turning `min_side` into a mere filter, or using `(area, width, height)` as the comparator, changes the exact frontier — both were rejected. `Phi(w, h)` is also **not** the exact source of truth. Publishing a terminal `CERTIFIED` whose `min_side` is below the canonical floor — *even if found in a superdomain run* — is a Forbidden Change (PROJECT_LOCK §1 lines 12-15, §4 line 456).
- **No hard "50 power poles + 10 protocol storage boxes" cap in exact mode.** If `50/10` (or 60, or the total 326) appears anywhere, it is **exploratory-only illustrative guidance**. History (§8): early specs (02 §2.6.1 / 06 §6.1 / 07) treated `I_opt=60` as a fixed enumeration; corrected on 2026-06-04 to **power poles = residual-optional** (activation count is a decision variable, coverage a lower bound, candidate pool an upper bound) and **protocol boxes = required-optional** (demand-driven from generic input-slot demand). The real masters model this with residual/required-optional, not a fixed 60. Promoting `50/10` to an exact cap would upgrade an exploratory cap into a proof constraint and could mint false-INFEASIBLE or a sub-optimal CERTIFIED (CLAUDE.md:30-31; PROJECT_LOCK §1 lines 15-17; master_model.py file header + master_model.py:2031-2056, :2080-2115, :5361-5363; CHANGELOG.md:193-199).

Python 3.13. Entry point `main.py` (default `--mode certified_exact`).

---

## 2. The single most important rule: `certified_exact` vs `exploratory`

**Two strictly separated solve paths that must never cross** (CLAUDE.md:17; PROJECT_LOCK §1 line 10, §4 lines 451-465):

| Path | May do | Must NOT do |
|---|---|---|
| `certified_exact` (default `--mode`) | produce proof-relevant candidate/proposal material; binding/routing checks; fixed-witness re-verification; supervisor seal; verified publication | use exploratory caps/hints/probes/sidecars as proof; let diagnostic flow gate; bypass frozen artifact / hash / open gate |
| `exploratory` | heuristics, diagnostics, visualization, sidecars, perf probes, empirical caps | produce certified pruning proof, terminal `CERTIFIED`, or public certified delivery |

Three rejected alternatives, recorded as Forbidden Changes:

1. **Treat exploratory caps/hints as exact lower/upper bounds.** Would let empirical constraints participate in the exact frontier and break the `max_lex(area, min_side)` proof object. Result: exact-safe bounds must be proof-neutral or independently proven. Solution hints may only write the CP-SAT `solution_hint` proto via `AddHint`, never constraints — a wrong hint costs time but cannot change the feasible set; malformed hints degrade to skip, never raise (PROJECT_LOCK §3 F-GM-R7-HINT-01 / F-GM-R8-HINT-02 line 314; §4 lines 451-465, 505-513). Frontier probes are exact-safe scheduling hints only (§3 line 278).
2. **Let the flow model gate pruning/publication.** `flow_subproblem.py` is a continuous LP (GLOP) diagnostic that cannot prove discrete belt throughput; even flow-INFEASIBLE cannot imply exact routing infeasibility. Result: flow stays diagnostic-only, never gates certified (flow_subproblem.py:1-11, :119-163; benders_loop.py:5151-5225; cc_memory `entry:p1-2-c3-kernel-audit-3source-20260620`).
3. **Let postprocess/serializer/viewer/adapter become the publication authority.** They may format/display but do not own a sealed campaign, the open gate, or disk-current revalidation. Result: only `publish_verified_certified_delivery_surface()` is the public certified publisher (NAV_MAP.md:32-43; certified_surface.py:758-904; PROJECT_LOCK §3 F-CAM-PR1-* lines 252-266).

### The producer / supervisor / publisher split (PR1)

Proof authority is deliberately divided so no single writer can mint a public `CERTIFIED` (PROJECT_LOCK §3 F-CAM-PR1-01..04 lines 252-266; landed as "PR1" on 2026-06-26, CHANGELOG 2026-06-26):

1. **Producer (F-CAM-PR1-01):** `src/search/outer_search.py` runs the search and at terminal completion persists **only `CANDIDATE_PROPOSED`** plus bound/fixed-witness/replay proposal material. It must **not** directly persist a terminal campaign `CERTIFIED` or publish; any producer `mark_campaign_stopped(..., "CERTIFIED")` is rejected. Its production-side terminus can only commit proposals (outer_search.py:855-887, :890-954, :1916-1969).
2. **Supervisor mint (F-CAM-PR1-02):** `ExactCampaign.supervisor_seal()` is the **sole durable terminal `CERTIFIED` mint**. It reads the committed proposal *from disk*, revalidates proposal + campaign bindings, executes sink replay and fixed-witness verification, and validates disk state before and after the write. A caller-held in-memory mapping is not authority. `save()` also rejects an unsupervised certified checkpoint claim. **⚠ Line refs:** Opus cites `exact_campaign.py:3566`; Codex cites `:3566-3599` (seal) plus `:3601-3610` and `:3652-3665` (rejection guards). Mint-hygiene: `mark_candidate_result` raises if a `CERTIFIED` result lacks a fresh solution mapping, raises if a non-`CERTIFIED` result carries a solution, blocks strong-status downgrades (audited), and raises on conflicting terminal statuses (`exact_campaign.py:3254-3362`, verified verbatim by Opus; PROJECT_LOCK F78-F-01 line 272). A persisted `candidate_proof` is a *replay request*, never a writer-issued grant.
3. **Public publication (F-CAM-PR1-03):** `publish_verified_certified_delivery_surface()` is the **sole certified public publisher**; it requires sealed + disk-current + terminal-frontier-evidence + open-gate-passed, then derives `final_solution.json`, `optimal_blueprint.json`, and `certified_delivery_manifest.json` as **one transaction** over the same disk-current sealed result, re-verifying after write and cleaning up partial outputs on failure (certified_surface.py:758-878, :881-904). Generic serializers, viewers, adapters, and legacy exporters are explicitly non-authoritative (NAV_MAP.md:32-43).
4. **Phase-open denial (F-CAM-PR1-04):** a valid internal seal is *necessary but not sufficient* — the P1.2 owner gate must independently resolve to the explicit closed form; missing/malformed/open gate data blocks publication.

**Crucial nuance to internalize:** *method availability and entrypoint availability are not release closure.* The seal method exists, and the production entry `scripts/run_supervisor_seal.py` now exists as an independent marker-driven command; `main.py` still stops at `CANDIDATE_PROPOSED`. A checker PASS, a local regression PASS, an entrypoint landing, or an internal seal must never be rewritten as an owner-closed release gate (PROJECT_LOCK §1A lines 136-137, C5 line 143). See §7.

---

## 3. The certified theorem scope (命题 P) — what CERTIFIED proves and what it does NOT

When `certified_exact` reports `CERTIFIED` on a candidate `(R*, π*)`, it proves **exactly and only** the "A block"; the "B block" is explicitly out of scope. This is the section most likely to be over-read (PROJECT_LOCK §1A lines 19-120).

### A. What CERTIFIED proves (6 gating predicates; any INFEASIBLE blocks CERTIFIED)

`π*` satisfies all six, and `(R*, π*)` is lex-optimal under `max_lex(area, min_side)`:

1. **No facility inside the ghost rectangle** `all_cells(π) ∩ R = ∅` — ghost optional interval merged into the same `AddNoOverlap2D` as all facility intervals (exact_coordinate_master.py:3744-3748). Hard geometric constraint. Owns predicate via ghost exactly-one + core/ghost `AddNoOverlap2D`.
2. **Instances pairwise non-overlapping** — core intervals' `AddNoOverlap2D` (exact_coordinate_master.py:3443-3445 / :3444). Depends on candidate-placement geometry bytes (a hash-pinned TCB).
3. **Per-instance placement_rule** — double-gated: the generator hard-binds `placement_rule` at pose-enumeration time and fails closed (`ValueError`) on mismatch so illegal geometry never enters the pool (placement_generator.py:267-271), *plus* master domain restriction (exact_coordinate_master.py:1557-1620, :2796). The candidate geometry itself is a hash-pinned TCB, not a runtime-derived theorem.
4. **Port-binding feasible, incl. port-level exact-count** — `binding_subproblem.py` gate: each instance exactly one binding; each generic output/input slot exactly one commodity; each demanded commodity's bound port slots **exactly equal** its `required` count. **Precision boundary:** proves the *count* of port slots equals the *declared* count (a 0/1 counting equality); does **not** prove per-port discrete throughput/rate. Driving artifact (Opus): `generic_io_requirements.json` outputs `{blue_iron_ore: 34, source_ore: 18}` (sum 52), inputs `{qiaoyu_capsule: 1, valley_battery: 1}` — artifact-driven, no literal in source. **⚠ Line refs:** Opus cites `:930` (one binding), `:976` (output slot), `:1022` (input slot); Codex cites `:348-451` and `:1037-1165`.
5. **Routing feasible = belts can connect (connectivity, NOT throughput)** — semantics: **discrete directed connectivity**; every commodity's every source front has a directed route-state path to a sink front, every sink front is fed, re-verified globally by `routing_subproblem.py:1623-1719 _validate_selected_route_connectivity` (rejects local-only incumbents; both passes agree on this range). Domain precheck emits only three validated states, connector cells are subtracted from the routable domain (connector = terminal node, not belt cell), unknown → `fail_closed_unknown` (routing_subproblem.py:126-132, :502-634). **Red line:** routing `FEASIBLE` ≠ throughput-feasible; the "capacity" `AddAtMostOne` (Opus: :1058-1061) is only "at most one route-state per cell per layer" — static spatial mutual exclusion, no time dimension.
6. **Power coverage feasible (the strongest predicate)** — two layers: (A) master hard constraint that every powered slot's cover-choice witness geometrically contains the slot footprint; **and** (B) an **independent terminal replay** that recomputes coverage cell-by-cell from the *frozen artifact's raw pose bytes* plus a no-redundant-tower check, failing closed on missing/unforced (exact_campaign.py:1131-1157). This is the *only* predicate with a second independent terminal re-verification; it explicitly does not trust the solver's internal variables. **Precision boundary:** proves geometric radius coverage + tower existence (`covered`), not electrical power throughput/balancing. The C3 kernel audit (2026-06-20) judged power coverage **sound**. **⚠ Master line refs:** Opus cites `:5827`, `:5275-5352`, `:5470-5499`, `:5845-5848`; Codex cites `:5141-5175`, `:5275-5352`, `:5827-5850`.

Plus **lex-optimality**: any lexicographically larger `(R', π')` must be infeasible.

### B. Explicitly OUT-OF-SCOPE (passing these off as proof triggers the §4 "diagnostic flow as proof" Forbidden Change)

- **(B-1) Material discrete throughput / belt bandwidth capacity is NOT proven.** Predicate (5) stops at connectivity. The one flow subproblem carrying demand quantities is **deliberately locked to diagnostic-only and never gates.** `flow_subproblem.py:1-11` docstring: in `certified_exact` it may act only as a diagnostic; its INFEASIBLE/UNKNOWN must never be written as an exact-safe cut. It is a continuous LP (`CreateSolver("GLOP")`, `NumVar(0.0, infinity)`); result stored only as a diagnostic status; a contract test monkeypatches flow→INFEASIBLE and asserts CERTIFIED still results with zero exact-safe cuts (`test_exact_contract.py:3532 test_exact_mode_uses_flow_only_as_diagnostic`) — a deliberately locked contract. **⚠ Diagnostic-status line ref:** Opus cites `benders_loop.py:5191 diagnostic_flow_status`; Codex cites the surrounding `benders_loop.py:5151-5225` region.
- **(B-2) Capacity / connectivity at ~98% density — an open research problem.** The F1–F9 cut families (`region_capacity`, `density_envelope`, etc.) are *area/space-density packing cuts, not throughput cuts*, and `src/cuts/` is **not yet integrated** into the production master (`lifecycle.py step_8_apply_to_master` raises `NotImplementedError`). Getting throughput into certified needs a **new paradigm** (changed predicate definitions + a new discrete-capacity subproblem), not "closing a gap."
- **(B-3) "Resources are sufficient" has three precisions with different proof status — never merge them:** ① port-level exact-count (predicate 4, `sum == required`, **certified**); ② power *coverage* sufficiency (predicate 6, geometric + tower existence + terminal replay, **certified**; NOT power throughput balancing); ③ material discrete throughput sufficiency (machines·rate ≥ flow demand, **NOT certified** — honest boundary / candidate cheap-win).
- **(B-4) Machine-to-machine physical clearance is not a predicate of P.** Canonical `globals.logistics.machine_min_clearance_cells=1` (Opus confirmed the value) is parsed by `src/rules/models.py` but has **no consumer on the certified path** (master's `_add_port_clearance_constraints` returns early in exact mode; routing's `_add_gap_rule` is telemetry-only). Owner clarification (2026-06-21): that field governs *port connector cells must be empty*, not machine-body separation — machine bodies touching is legal, so a "packed" certified layout is not a soundness violation. A residual public false-CERTIFIED path around connector/body occupancy was later *closed* by the terminal fixed-witness verifier rebuilding body occupancy from real `port_specs` and rejecting connector cells occupied by any facility body (`terminal_fixed_witness_verifier.py:848-866`) — no longer an open gap.

### Geometric trust boundary / named TCB (PROJECT_LOCK §1A lines 82-98)

Only two geometry facts are independently re-derived at solve time: (a) master recomputes `occupied_cells == bbox` from pose anchor + template dims for solid footprints (exact_coordinate_master.py:1043-1070); (b) master recomputes the power-pole radius-5 / 2×2-pole-induced **12×12 square** coverage (:5141-5175). **Everything else in the frozen `candidate_placements.json` pose bytes (`occupied_cells` / `power_coverage_cells` / port coords) is a named TCB** — trusted because generation-time `placement_generator._validate_template_geometry_contract` fails closed (:161-168, :252-257, :267-271) and the artifact hash pins the bytes. The canonical-rule→geometry mapping (e.g. `power_coverage_radius=5` → 12×12 square) is an *owner-confirmed spec fact and named TCB*, **not** a theorem the code auto-proves for P1.2.

---

## 4. The solve pipeline — call chain and per-layer proof authority

Module names do **not** themselves constitute soundness proof; proof scope is per `PROJECT_LOCK` and machine obligations (NAV_MAP.md:3). Normal CLI chain: `main.py` → `run_solve()` → `run_outer_search()` (main.py:51-88, :301-328); no call reaches `supervisor_seal()`, so a normal run ends at `CANDIDATE_PROPOSED`.

```
main.py                                        (default --mode certified_exact; stops at CANDIDATE_PROPOSED)
 └ src/search/outer_search.py                  PRODUCER: enumerates candidates, runs Benders/LBBD,
    │                                           commits CANDIDATE_PROPOSED ONLY (F-CAM-PR1-01)
    └ src/search/benders_loop.py               Benders / LBBD main loop
       ├ src/models/master_model.py            placement master (CP-SAT); header: no 50/10 as formal constraint
       ├ src/models/exact_coordinate_master.py DEFAULT certified coordinate backend
       ├ src/models/pose_bool_exact_master.py  env-gated ALT backend — NOT public certified
       │                                        (blocked by `pose_bool_master_not_certified`)
       ├ src/models/binding_subproblem.py       CERTIFIED GATE: port binding + exact-count
       ├ src/models/routing_subproblem.py       CERTIFIED GATE: grid routing (connectivity, not throughput)
       ├ src/models/flow_subproblem.py          DIAGNOSTIC ONLY — never proof authority, never gates
       ├ src/search/independent_infeasibility_reverifier.py  whole-layout nogood independent recheck (I1)
       └ src/cuts/lifecycle.py                  Benders cut store/lifecycle — NOT integrated (step_8 raises)
    ├ src/search/certified_frontier.py          strict full-frontier projection / evidence
    ├ src/search/terminal_fixed_witness_capsule.py / _verifier.py  re-verify the published π* in place
    ├ src/search/exact_campaign.py
    │  ├ scripts/run_supervisor_seal.py      PRODUCTION supervisor invocation surface (independent marker-driven command)
    │  └ ExactCampaign.supervisor_seal()        SOLE durable terminal CERTIFIED mint (F-CAM-PR1-02)
    └ src/search/exact_parallel_scheduler.py    coordinator-only writer, disjoint candidate waves
 └ src/search/certified_surface.py
    └ publish_verified_certified_delivery_surface()  SOLE public certified publisher (F-CAM-PR1-03)
```

Benders-loop role ordering (benders_loop.py:5795-6050, :6959-7132, :7489-7598): master → candidate layout; binding → generic-I/O exact count; routing → connectivity; flow → diagnostic status only; then a whole-layout nogood must pass the I1 reverifier before it becomes a proof-bearing cut. Routing `FEASIBLE` returns a solve-layer `RUN_STATUS_CERTIFIED` — this is **not** durable/public CERTIFIED.

Per-layer honest boundaries:

- **Master (`exact_coordinate_master`, default):** owns predicates (1)(2)(3) hard geometry and (6A) power master constraints. Geometry keyed by each pose's *actual* `occupied_cells`, not template default dims; non-rectangular footprints may be conservatively over-approximated by bbox but never under-approximated (PROJECT_LOCK §3 line 317).
- **`pose_bool_exact_master` (env-gated alt):** reachable only under `EXACT_USE_POSE_BOOL_MASTER=1` and `RuntimeError`-gated off the public certified path by `pose_bool_master_not_certified`. **But its soundness obligations still bind** — a line of F-GM-R11/R12/R13/R14-PB clauses fixed false-FEASIBLE / stale-witness seams there (PROJECT_LOCK §3 lines 316, 333, 336, 342). Caution: "gated off" ≠ "don't care."
- **Binding:** proves predicate (4). Its `binding_selection_safe_reject` precheck evidence is **binding-local** — `front_blocked` / `relaxed_disconnected` must first add a *binding-level* nogood and exhaust alternative port bindings; a master placement-level nogood is allowed only after binding alternatives are exhausted or an independent placement-level proof exists, else fail closed `UNKNOWN` (PROJECT_LOCK §3 line 318).
- **Routing:** proves predicate (5) connectivity only. CP-SAT `FEASIBLE` by itself is not a certification boundary — certified acceptance rebuilds the selected route-state graph and proves global source→sink reachability; a locally-closed but globally-disconnected incumbent is rejected and re-solved; budget exhaustion → `UNKNOWN`/`TIMEOUT`, never `CERTIFIED`. A large family of F-RT-* / F-BL-* clauses (front polarity, connector-cell exclusion, per-edge conservation, domain clipping, status-contract deny-unknown) harden against false-FEASIBLE and false-INFEASIBLE (PROJECT_LOCK §3 lines 304-310, 320, 334-335, 355).
- **Flow:** diagnostic only; never mints pruning/publication proof (B-1).
- **Independent infeasibility reverifier (I1):** before a proof-bearing *whole-layout* nogood may be added, the loop calls `reverify_whole_layout_infeasibility()`, which rebuilds the binding/routing question through its *own* entry point; `confirmed=false` / feasible divergence / malformed evidence / exception → `UNKNOWN` / no cut. It **confirms binding-INFEASIBLE-type conflicts**; routing exhaustion without a full independent proof is conservatively downgraded to UNKNOWN (a deliberate soundness-over-completeness choice, not a missing feature). It does **not** prove every future cut family has an independent checker, nor by itself close P1.2 or remove the verifier/solver stack from the TCB (independent_infeasibility_reverifier.py:1-14, :69-90, :146-240; PROJECT_LOCK §4 lines 467-476; landed at commit `44089a3`, cc_memory `entry:p1-2-fix-4-landed-44089a3`). **⚠ I1 call-site line ref:** Opus cites `benders_loop.py:7538-7585`; Codex cites `benders_loop.py:7489-7598`.
- **`src/cuts/` (F1–F9 cut lifecycle):** designed (B Design v2, PROJECT_LOCK §2B/§3A) but **NOT wired into production** — `CutScope` binds source digest / ghost+exterior hash / `artifact_hashes` / oracle versions / assumptions (cuts/lifecycle.py:175-195, :941-984), yet `step_8_apply_to_master` raises `NotImplementedError` (cuts/lifecycle.py:1121-1126) and no production module imports `src/cuts/`. `benders_loop`'s `exact_safe_cuts`/`BendersCut` is a *separate* Benders mechanism with no bridge (PROJECT_LOCK §3 line 353, F-CUT-BS-R3-01; NAV_MAP.md:49-53; §4 lines 478-503). Exactness rule is **FP=0**: a cut must never delete a legal solution; false-negatives (missed cuts, perf loss) are acceptable, false-positives fatal — prefer HOLD/QUARANTINE/UNKNOWN over admitting an incompletely-verified cut (PROJECT_LOCK §3A lines 361-449, Gemini round 19).

---

## 5. Source-of-truth frozen artifacts and hash pinning

The certified path is grounded in frozen inputs whose bytes are hash-pinned by the preflight gate (`scripts/preflight_gate.py::FROZEN_ARTIFACTS`, lines 37-55, :238-276) and, for some, bound into the campaign hash closure (`exact_campaign.OPTIONAL_EXACT_HASH_FILES`) (PROJECT_LOCK §2 lines 188-220).

**⚠ Hash/size detail differs by pass** — Opus fully verified `candidate_placements.json` bytes + several artifact *contents/counts*; Codex measured on-disk sizes + SHA256 for all five. Both are reproduced below; a new engineer should re-measure before trusting.

| Artifact | Role | Size (Codex, bytes) | SHA256 (Codex, upper-hex) |
|---|---|---:|---|
| `rules/canonical_rules.json` | canonical recipes / targets / commodity roles / objective (`min_side_admissibility=6`) | 12,795 | `32664AAC6C075AF7D57E001A0A2B11B9A8B9304D8513739414AAA7ED4501BCB3` |
| `rules/preprocess_plan.json` | additive overlay only (cycle groups / utility operations) | 1,387 | `1BCF0D13E1709CD7E04DDEA439EE005E837584F2F66A1A921159D198019C9ED8` |
| `data/preprocessed/mandatory_exact_instances.json` | 266 frozen mandatory instances | 88,261 | `545B98C2B4F96643F1346B423EDF2DC8E300A0C815B6CF821776CEED03CD4CD6` |
| `data/preprocessed/generic_io_requirements.json` | frozen generic I/O demand (outputs 34+18=52, inputs 1+1) | 561 | `AD5125B50E607A7F3F3BF0B54FEA64F93EDF87CEDB62E8D24F5590E1C895C44E` |
| `data/preprocessed/candidate_placements.json` | candidate pose pool (geometry TCB) | 45,774,305 | `A914BA6348544B7EF44D0834629C6DCF90F39FA5564E0CD4C50AF6AF550C444B` |

**Current pinned `candidate_placements.json`:** size **45,774,305 bytes**, SHA256 (lower-hex) `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b` — matches the pinned contract exactly. It is part of the certified contract even though some lightweight distributions externalize it; only then should it be regenerated/restored (`scripts/restore_external_artifacts.py`, or regenerated via `python src/placement/placement_generator.py`), and an archive is a valid restore source **only after** its bytes pass the pinned hash check (PROJECT_LOCK §2 lines 199-208). The immediately previous `45,773,799`-byte artifact, SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, predates the boundary `(0,0)` corner-pose fix and is superseded/hash-incompatible.

**Superseded artifact (must fail-closed):** the older `candidate_placements.json` of size **53,594,995 bytes**, SHA256 `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f`, is hash-incompatible; campaign resume must reject it with `artifact_hash_mismatch`. If the old size/hash appears, fail closed — do **not** "helpfully update the expected hash" (PROJECT_LOCK §2 lines 204-206; CLAUDE.md).

**Additional hash-closure member:** on 2026-06-16 a certified-exact **source-tree digest** (`certified_exact_source_tree`) was added to campaign `artifact_hashes` — *intentionally* breaking resume compatibility for older checkpoints (missing key → `artifact_hash_mismatch`), forcing a restart across the proof-kernel binding change (CHANGELOG 2026-06-16). The protected source set must include the **root entrypoint `main.py`**, not only `src/`/`scripts/` (PROJECT_LOCK §3 F-SRC-R9-01 line 276). Editing any frozen artifact is a **freeze-ritual change**: update the hash in the preflight gate, regenerate dependents, re-run the gate (CLAUDE.md conventions).

**Strict JSON everywhere on proof paths:** all proof-relevant parsing uses `src/io/strict_json.py` — duplicate keys and `NaN`/`Infinity` are rejected, writers emit `allow_nan=False` (PROJECT_LOCK §3 F-BIND-R2-02, F-PRE-R8/R9). A duplicate key silently keeping the last value could let a tampered artifact replace real demand with an empty section — the strictness is a soundness control, not hygiene. `generic_io_requirements.json` is loaded fail-closed (F-BIND-R1-02, R8-02/R9-01).

---

## 6. Why `preprocess_plan.json` is additive-only

`canonical_rules.json` carries recipes, production targets, commodity roles; `preprocess_plan.json` is an **additive overlay** that may carry only cycle groups / utility operations, and **must never carry top-level `recipes` / `production_targets` / `commodity_roles` override keys** (PROJECT_LOCK §2 line 220, clause **R6-F-01**).

**⚠ Important scope nuance (Codex adds, Opus omits):** the plan *may* reference recipe **ids** inside a cycle group (there is a list of recipe names inside cycle groups). What is forbidden is a **top-level `recipes`/`production_targets`/`commodity_roles` definition that could override canonical truth** — not a cycle group referencing a recipe id. A new engineer reading only Opus's "must never carry recipes" wording could wrongly conclude any recipe reference is illegal; Codex's reading is the more precise one and matches the code (the guard checks top-level override keys, then merges canonical role truth from `canonical_rules.json`, and lets the plan add cycle groups + utility operations).

**Rationale (the failure it prevents):** a same-key overlay could *silently rewrite* runtime operation profiles and binding utility slots — forking the source of truth so the hash looks valid but the semantics changed, a fail-open path into false results.

**Mechanism (verified in source):** `src/interchange/preprocess_context.py` defines `PLAN_CANONICAL_OVERRIDE_KEYS = ("recipes", "production_targets", "commodity_roles")` and the context builder **fails closed** — if any of those keys appear it raises `ValueError("preprocess_plan.json must be additive-only; canonical recipe/target/commodity metadata overrides are not allowed: ...")`. The utility-operation namespace was later hardened so a plan operation key cannot even *shadow* a canonical recipe's runtime port profile (PROJECT_LOCK §3 H-PRE-BS-01 line 349). The plan is bound into the exact campaign hash closure + preflight frozen-artifact registry, so editing it is a freeze-ritual change. **⚠ Line refs:** Opus cites `preprocess_context.py:25` (constant) and `:178-186` (fail-closed raise); Codex cites `:1-8`, `:24-25`, `:171-238`, `:461-470`. This additive-only consolidation landed 2026-03-25 (CHANGELOG 2026-03-25; CHANGELOG.md:162-165).

---

## 7. The release boundary — honest current status (P1.2 is OPEN / BLOCKED)

Do not read any safeguard above as "the project is done / published" (PROJECT_LOCK §1A/C lines 122-186; cc_memory `fact:fact-p1-2-release-gate-status-20260626`):

- **P1.2 is OPEN / BLOCKED.** The owner manual gate `data/review_gates/phase_1_2_spike_close.json` is currently `blocked_manual_review_count` (`next_phase_entry.allowed=false`; compat field `p1_3b_entry_allowed=false`). It opens only by the owner's explicit `owner_manual_decision`. The repo must **not** auto-derive P1.2-closed / P1.3-allowed from a receipt, report, package metadata, source-tree manifest, clean-count, or an internal supervisor seal.
- **`main.py` stops at `CANDIDATE_PROPOSED`.** The production supervisor entry is now `scripts/run_supervisor_seal.py`: an independent command that resumes a committed `CANDIDATE_PROPOSED` proposal, validates the proposal-ready marker first, calls `ExactCampaign.supervisor_seal()` (real isolated L0 recheck), and exits success/error. A normal `main.py` completion is still *not* a seal success — the single biggest "looks done but isn't" trap; entrypoint availability is not P1.2 closure (cc_memory `fact:fact-p1-2-supervisor-operability-20260626`, `entry:p1-2-supervisor-production-entry-gap-20260626`; main.py:51-88; `scripts/run_supervisor_seal.py`, commit `349c56c`, 2026-07-04).
- **preflight/checker green ≠ soundness.** cc_memory `entry:p1-2-current-validation-20260626` records ~3346 passed / 0 failed while the same memory set still marks P1.2 blocked.
- **PR2 (TCB shrink) is unfinished.** The smaller read-once / controlled-loader verification TCB is not implemented (still-open backlog: #1/#2/#3, #5 independent enumeration, #8, #9b/#9c — real to-dos, currently unscheduled per the owner's 2026-07-04 clarification). The review-snapshot packager has since been fixed to resolve the caller-supplied `treeish` to an immutable commit once and materialize from that same resolved commit (`scripts/package_review_snapshot.py`; pinned by a ref-move TOCTOU regression test, and PROJECT_LOCK §1A was synced accordingly on 2026-07-04); archive-policy coverage remains to be confirmed. *(The "close-kernel" AST-pin hardening line has since converged — merged to main at `6e06922` after round-19/20; the owner drew the TCB line on 2026-07-03 and stopped the external-review loop. The durable lesson relevant here, from cc_memory `entry:close-kernel-ast-pin-structural-vs-semantic-boundary`: an AST pin can protect **structure** (the sole durable-mint chokepoint, entry reachability, gate result-flow) but **cannot protect "the proof math is correct"** — leaf numeric helpers are consciously delegated to the sha source-floor + frozen-artifact hash + human re-pin review, and that boundary is honestly labeled, not papered over. Do not treat the structural checker as a substitute for human review.)*
- **What was closed (but does not close P1.2):** the PR1 producer/supervisor/publisher split; fixed-witness terminal re-verification; the fail-closed P1.2 OPEN-GATE (`resolve_p1_2_publish_open_gate()`); the connector/body terminal check; isolated-source bytecode binding (`PO-ISOLATED-EXEC-BYTECODE-BINDING`: verifier subprocess uses `-B -X pycache_prefix=<fresh>` from source-digest-protected `.py`); and the I1 independent whole-layout reverifier (CHANGELOG 2026-06-26). Python/stdlib/OR-Tools native extensions, the parent relay, and OS process/file isolation remain **named TCB** — never write "TCB fully eliminated" (PROJECT_LOCK §1A lines 169-171).

**Honest framing:** P1.2 "closed" would mean *only* that the §1A proposition-P machine boundary, the publication chain, and the owner manual gate are simultaneously satisfied. It is **not** a throughput theorem and does **not** auto-open the next phase (humans call it P1.3; `p1_3b_*` fields are legacy machine-compat identifiers) (PROJECT_LOCK §1A lines 139-146).

---

## 8. Timeline of decisions, rejected alternatives, reversals (faithful, merged)

- **`932483f`:** initial import; exact/exploratory dual-track formed thereafter.
- **2026-03-16 → 03-23:** built the exact-safe local-capacity path, coordinate-encoded master stabilization, routing-core shrink, resume, power coverage; **added the production parallel exact scheduler with coordinator-only persistence + disjoint candidate waves** (chosen so no worker can race-write proof state); formalized canonical blueprint export + certified delivery manifest; **locked the objective to `max_lex(area, min_side)`** and clarified `50/10` is exploratory-only; locked best-certified monotonicity within a campaign epoch (CHANGELOG 2026-03-16..03-23; CHANGELOG.md:173-199). *Rejected dead-ends:* HiGHS/SCIP master rewrites were tried and judged dead-ends, kept only as reference (CHANGELOG 2026-05-16; cc_memory `project_highs_rewrite_blocker`).
- **2026-03-25:** consolidated recipe/target/commodity truth into `canonical_rules.json`; slimmed `preprocess_plan.json` to the additive overlay (basis for §6 / R6-F-01); landed Phase-1 ecosystem scaffolding (`src/interchange/*`, `src/adapters/*`) as additive, non-certified (CHANGELOG.md:162-165).
- **2026-03-26:** added exact-safe **frontier probe** scheduling, designed *not* to change the certified objective or proof contract (probes are hints).
- **2026-04-14 → 04-17:** **narrowed the active IndustrialPlanner contract to the single 70×70 `valley4_protocol_core` base**; other bases (incl. 80×80 `wuling_protocol_core`) collapsed to `future_scope`. Rationale: keep the certified/CI-critical surface to one active base; larger-base outer-deployment translation stays adapter-side future-scope, never certified evidence (PROJECT_LOCK §2A, §5 line 511). A whole additive delivery/adapter product line (`src/render/industrial_planner_*`, `src/adapters/*`, `data/exports/*`) exists but must never redefine solve schemas or become source-of-truth.
- **2026-05-22 (B Design v2, Phase 0 close):** after a 23-round Gemini cross-check, froze the cut-object design: cut becomes a persisted first-class object with a 10-step lifecycle + 6-step replay-verify; **"FP=0" locked** ("宁可 FN 不可 FP"). Group/orbit-count symmetry state chosen over per-instance state to kill 10^134 label symmetry. **Reversal:** F9 `tight-K` quarantined (2026-06-04, v28), *superseding* the earlier Gemini round-4 "trust oracle K, defer tight-K re-verify to P1.5+" — replay proved the validator is a trust boundary that doesn't re-run the oracle, so trusting an un-recomputable cert scalar is a real FP at replay (PROJECT_LOCK §3A lines 425-437). Also locked: F9 must use area-based counting (`sum(|pose_cells ∩ W|)`) — v1.0/v1.2/v1.3 instance-based variants all proven unsound (FP or FN); reverting to instance-counting is a Forbidden Change (lines 384-389).
- **2026-06-04 (v28 GPT-pro external review):** the **`50桩+10箱`=60 fixed-enumeration reading was corrected** to residual-optional poles + required-optional boxes (§1). Added the cut-family validator numeric/literal source-of-truth gate (any scalar a validator can't cheaply recompute must be fail-closed cross-checked against canonical) — consolidated in `src/cuts/helpers/canonical_sot.py`. **Honest residual:** a 4th verbatim pole-radius copy was found hiding in `verifiers.py` after three prior review rounds + v28 all missed it — a candid admission that "finding a brand-new unguarded scalar" still relies on humans/review (PROJECT_LOCK §3A lines 411-421).
- **2026-06-16:** added the certified-exact source-tree digest to campaign hashes, intentionally breaking old-checkpoint resume (§5).
- **2026-06-20 (C3 three-source kernel audit):** judged P1.2 cannot yet establish a complete soundness theorem; the I1 no-good lacked independent infeasibility re-verification; throughput is an independent out-of-scope critical overclaim; **power coverage was judged sound** (cc_memory `entry:p1-2-c3-kernel-audit-3source-20260620`).
- **2026-06-21 (witness-split BLOCK — a dead-end recorded honestly):** discovered that the published witness did not re-run binding/routing *in place*. Tried a **rebind-to-replay stopgap**, but a full preflight exposed a digest mismatch that would corrupt legitimate delivery → **the stopgap was withdrawn**, choosing an honest OPEN + a proper fixed-witness repair instead (cc_memory `entry:p1-2-witness-split-block-2026-06-21`).
- **2026-06-23 (supervisor L0/L1 design meeting):** supervisor design changed from a single supervisor to a **two-layer L0/L1 + controlled loader**. The single-supervisor design was **rejected** because calling evaluate/publisher would drag the project + OR-Tools solve kernel into the TCB (cc_memory `entry:p1-2-supervisor-l0-l1-design-meeting-20260623`).
- **2026-06-23 (FIX-4 / FIX-5 design):** FIX-4 treats I1 as an independent re-verification gate; FIX-5 treats TOCTOU as read-once bytes/hash/parse from one source (cc_memory `entry:fix-4-fix-5-i1-toctou`).
- **`44089a3` (FIX-4 landed):** binding-INFEASIBLE independent re-verification; routing exhaustion phase-1 conservatively UNKNOWN (cc_memory `entry:p1-2-fix-4-landed-44089a3`).
- **2026-06-26 (PR1 landed):** producer/supervisor/publisher split landed and all release-boundary docs reconciled to it; recorded the then-open operational gap that `main.py`/launchers don't call `supervisor_seal()`; kept P1.2 OPEN/BLOCKED. That PR2 #7 gap was later filled on 2026-07-04 by `scripts/run_supervisor_seal.py`, without closing P1.2. **⚠ PR1 commit set differs by pass:** Codex cites `ddb3b5a` / `d3f9009` / `2904a81` / `072265a` / `1817c71` as the incremental supervisor/publication boundary landings (CHANGELOG.md:7-14). Opus does not enumerate PR1 commits but cites a *separate* set of **confirmed-then-fixed soundness bugs** (labeled A–H) merged at commits `a8b18d8` / `f226a55` / `44ef95e`; cc_memory `fact:fact-certified-exact-proof-path-has-confirmed-unpatched-soundness-critical-bugs` is now **CLOSED** — the slug word "unpatched" is a historical naming artifact; all are patched (read the value field, don't trust the slug). Treat both commit sets as real and union them.
- **"Blank-slate de-biased review" rounds R2–R5 (PROJECT_LOCK §3 lines 350-358 — Opus detail, showing real failure modes that actually bit):**
  - **F-GM-BS-R2-01:** the boundary-storage-port feasibility screen used `occupied ∪ port_connector_cells` as its hard-infeasibility premise; on canonical geometry (134 boundary poses with occupied cells on the grid edge, connector one cell inward) a corner-region ghost falsely pruned a master-legal, routing-feasible candidate → false-CERTIFIED of optimality. Fix: premise uses `occupied_cells` only. Red→green `test_boundary_port_precheck_soundness.py`.
  - **F-SCHED-BS-R3-01 / R4-01 / R5-01 / R5-02:** a *family* of parallel-scheduler worker-crash timing bugs (worker queues its final RESULT then dies non-zero: end-of-wave, mid-wave respawn, success-path shutdown TOCTOU, and the resume "preserve→persist→resume" residual). Each let a crashed worker's false `INFEASIBLE` become a sticky strong status that permanently prunes a true maximal rectangle → smaller rectangle certified as optimal → false-CERTIFIED. All default-env on the documented `main.py --parallel-processes` path, none behind an `EXACT_*` knob; upheld by multi-agent adversarial convergence (commit `3bc08b0` for R3's seal). **Lesson:** terminal validators are self-consistency over persisted statuses, not independent re-verification — they do not backstop a poisoned per-candidate status.
- **Current HEAD (⚠ only Codex states it):** at read time `b35e5f9`; memory/harness still record P1.2 as blocked, not a certified release (cc_memory `fact:fact-p1-2-release-gate-status-20260626`, `entry:p1-2-current-publication-surface-status-20260626`; harness resume `p1-2-resume-state-20260621.md:42-66`). *(2026-07-04: HEAD has moved on — pr2-5 and mixflow merges landed; `b35e5f9` is unresolvable in this delivery copy. Check `git log`.)*

---

## 9. Open problems, residuals, known limits (do NOT treat as closed)

1. **P1.2 not closed; `main.py` ends at `CANDIDATE_PROPOSED`** (§7). Headline open item. Gate = `blocked_manual_review_count; next_phase_entry.allowed=false`.
2. **`scripts/run_supervisor_seal.py` is the production supervisor entrypoint, but this only lands PR2 #7.** It is an independent marker-driven command to call `supervisor_seal()`; it does not make `main.py` seal, does not satisfy PR2 #1/#2/#3/#5-independent-enumeration/#5-F/#8/#9, and does not open the owner gate.
3. **preflight/checker green is not a soundness conclusion** (~3346 passed / 0 failed alongside P1.2 blocked).
4. **Discrete throughput / belt bandwidth / capacity-flow at high density is unproven and out of scope** — needs a new predicate + new proof chain, not opening `flow_subproblem.py` (B-1, B-2).
5. **Candidate geometry is a hash-pinned TCB** — the current theorem does not re-derive all candidate geometry from canonical rules; `candidate_placements.json` bytes are themselves inside the TCB.
6. **`src/cuts/` F1–F9 cut lifecycle is not integrated** — `step_8_apply_to_master` raises `NotImplementedError`; seeing `src/cuts/` does not imply F1–F9 can participate in certified pruning (F-CUT-BS-R3-01).
7. **Routing-exhaustion independent re-verification stays conservative** — FIX-4 is soundness-first; a legitimate cut may fail to land and fall back to UNKNOWN.
8. **PR2 / L0 / L1 / loader / read-once residual-risk remains** — the close-kernel rounds have since converged (merged at `6e06922`; owner drew the TCB line and stopped the review loop, 2026-07-03), while #1/#2/#3/#5-independent-enumeration/#8/#9 deepening stay real-but-unscheduled backlog; do not treat the structural checker as a substitute for human review.
9. **Named TCB remains:** interpreter, stdlib, OR-Tools native extensions, parent relay, OS process/file isolation, the on-disk sink verifier/protected source, and the frozen-geometry pose bytes (trusted via generation-time contract + hash pin). "TCB fully eliminated" is never a true statement here.
10. **`EXACT_POWER_PLACEMENT_SUBPROBLEM=1` is forbidden on any certified/production path** — exploratory only; the production readiness gate and `run_campaign_linux.sh` both block when set. Three known exactness gaps persist (live ghost-conditioned cut: implemented; persisted cut replay: implemented; **feasible-path pole alternatives: NOT implemented**, current stop-gap fail-closes to `UNKNOWN`) (PROJECT_LOCK §4 lines 460-465). A chain of CUT-R12..R16-H1 clauses hardens its obligations "the moment that channel is opened."
11. **`EXACT_*` env knobs are deny-unknown in `certified_exact`:** only documented allowlist entries; proof-semantics knobs stay at canonical default; unknown/future names block the run. `docs/env_variable_index.md` is **incomplete** — grep source for `os.environ`/`getenv` on `EXACT_` for the real set (CLAUDE.md; PROJECT_LOCK §3 line 303).
12. **Env-gated `pose_bool_exact_master` backend** carries live soundness obligations even though gated off the public path — a standing hazard if anyone promotes it (§4).
13. **Honest residual admissions kept in the lock itself:** an F6 grandfathered canonical-dims check not routed through `canonical_sot`; an `exact_coordinate_master` symmetry-narrowing site left as an "acceptable residual"; finding brand-new unguarded validator scalars still relies on human review (PROJECT_LOCK §3A lines 413-421, §3 line 342).

---

## 10. Independent-recheck entry points (verify before relying on this chapter)

Recommended order (don't just trust this document):

1. `PROJECT_LOCK.md:8-120` — theorem scope + out-of-scope (§1 constitution, §1A proposition P + 6 predicates, §1A/C P1.2 done-condition).
2. `main.py`, `outer_search.py`, `exact_campaign.py`, `certified_surface.py` — confirm proposal/seal/publish three-stage separation is not conflated.
3. `binding_subproblem.py`, `routing_subproblem.py`, `flow_subproblem.py` — confirm each layer's proof boundary.
4. `preprocess_context.py` + `scripts/preflight_gate.py` — confirm frozen artifacts and additive-only plan.
5. cc_memory ids: `p1-2-c3-kernel-audit-3source-20260620`, `p1-2-witness-split-block-2026-06-21` (note hyphenated date), `fix-4-fix-5-i1-toctou`, `p1-2-fix-4-landed-44089a3`, `p1-2-supervisor-l0-l1-design-meeting-20260623`, `p1-2-current-publication-surface-status-20260626`, `p1-2-current-validation-20260626`, `p1-2-supervisor-production-entry-gap-20260626`, `close-kernel-ast-pin-structural-vs-semantic-boundary`; facts: `fact-p1-2-release-gate-status-20260626`, `fact-p1-2-supervisor-operability-20260626`, `fact-certified-exact-proof-path-has-confirmed-unpatched-soundness-critical-bugs` (now CLOSED/patched); rejected-alt: `project_highs_rewrite_blocker`.
6. git commits — separate "code done" from "certification closed": `44089a3` (FIX-4), PR1 landings `ddb3b5a` / `d3f9009` / `2904a81` / `072265a` / `1817c71`, confirmed-fixed-bug merges `a8b18d8` / `f226a55` / `44ef95e`, scheduler R3 seal `3bc08b0`, read-time HEAD `b35e5f9`(已过时,现状以 `git log` 为准).

**Authority/navigation index:** `PROJECT_LOCK.md` §1/§1A/§1A-C/§2/§2A/§2B/§3A/§3/§4/§5; `NAV_MAP.md` (call + publish chains, reading order); `CLAUDE.md` (overview + conventions); `CHANGELOG.md` dated history (esp. 2026-06-26 PR1 split, 2026-06-16 source digest, 2026-06-04 v28 era, 2026-03-23/03-25/04-14).


---

# 第 2 章 · 认证 / 发布链、P1.2 与为什么仍 release-blocked

> **本章定位**：把一次求解运行变成公开 `CERTIFIED` 结果的**权限链（authority chain）**、管辖 release 关闭的**owner 手动闸**，以及这条链被硬化出来的完整（且诚实、包含死路的）历史。这是给另一台机器、从零接手的新工程师的**唯一上下文**——完整优先于简洁。凡涉及"我们决定了 X"，请当作**一条你可以重新裁定的既往决策证据**，不是你必须采纳的结论。所有条目尽量追溯到 `file:line`、git 短哈希、`cc_memory` 条目 id 或数据文件。
>
> **权威顺序**：`PROJECT_LOCK.md` §1A / §3 是权威；若本章任何内容与它冲突，以 `PROJECT_LOCK.md` 为准。
>
> **本史料由两份独立核查合并**（一份 Opus、一份 Codex，各自独立从 cc_memory / CHANGELOG / PROJECT_LOCK / git / RESUME 挖）。凡两版有出入、一版有另一版没有、或引用不一致处，均以 **⚠** 标注并保留全部信息，供终审裁定，未擅自取舍。

---

## 0. 证据范围、当前工作树状态、只读读数

两版核查的对象一致：`CLAUDE.md`、`NAV_MAP.md`、`PROJECT_LOCK.md`、`CHANGELOG.md`、`data/review_gates/phase_1_2_spike_close.json`、`data/proof_obligations/*`、`scripts/check_p1_2_proof_obligations.py`、关键代码路径、cc_memory 条目、harness resume 锚 `C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory\p1-2-resume-state-20260621.md`。

**工作树不是干净树**：核查开始时 `git status --short` 显示 `cc_memory/memory.db` 已修改，并有大量未跟踪日志 / 包 / 审查材料。两版核查均未写文件、未改代码、未清理。

**当前 checkout 的只读 gate 结果（Codex 实跑）**：

```powershell
python scripts/check_strong_status_write_allowlist.py
# strong-status write allowlist check passed: 64 registered AST node(s), 82 allowlist entry(ies)

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 14 obligations anchored; 59 proof-bearing sink files sealed
```

这只说明**当前 checkout 的结构 gate 通过**。它**不是** P1.2 closure、**不是** release approval、**不是** public CERTIFIED artifact 已发布。

**⚠ sink 数量出入**：当前 cwd main 的 checker 输出为 **59** proof-bearing sink files sealed（Codex 实跑）；而 RESUME 锚记录的 round-18 状态报告为 **60** sinks（Opus 引 RESUME 锚："14 obligations anchored; 60 sink files sealed"）。close_kernel_contract 内部 Opus 也记为 **59** `sink_files`。新工程师应把此当作"当前 main = 59、pr2-5 round-18 worktree = 60"的分支差异，不要混为一谈。

**⚠ 当前 git 位置**：Codex 记录当前 cwd main 的 `git log` 顶部为 `b35e5f9`，`origin/main` 为 `5ab006f`；而下文 PR2 #5 round-18 `9bbb3a6` 是**另一个 worktree/branch（`pr2-5-domain-frontier-gate`）**的状态，**未合入当前 main**。Opus 未记录当前 main HEAD，只给出 pr2-5 分支 HEAD。新工程师**不要**把 round-18 branch 的结论当作当前 main 已合入或 release 已批准。

---

## 1. 支配一切的单一事实

**当前不存在任何公开 `CERTIFIED` 结果，且正常求解 `main.py` 运行今天也铸不出。** 求解器默认入口停在 `CANDIDATE_PROPOSED`；能铸 durable 终态 `CERTIFIED` 的方法（`ExactCampaign.supervisor_seal()`）存在且有测试，生产入口已由 `scripts/run_supervisor_seal.py` 落地为独立命令：从 proposal-ready marker 驱动 supervisor seal，而不是由 `main.py` 顺手调用。即便有一个合法的内部 seal，也**不是 release**：release 关闭由一个**默认关闭的 owner 手动闸**管辖，其 clean-review 计数刻意保存在**仓库之外**。

三把串联的锁：

1. **Producer 只能提案**（不能认证）。
2. **只有 supervisor seal 能铸 durable `CERTIFIED`**——生产侧入口是独立的 `scripts/run_supervisor_seal.py`，不是 producer / `main.py` 自动调用。
3. **即便 seal 也"必要不充分"**：owner 手动闸必须独立打开，而它当前是 `blocked_manual_review_count` / `next_allowed=false`。

不要把"seal 方法存在 / 某个测试调用过它 / 结构 checker 通过"当成"owner 已批准 release 关闭"。`PROJECT_LOCK.md:136-137` 明写：*"任何 checker PASS、局部回归 PASS 或内部 supervisor seal 都不得改写为 owner 已关闭 release gate."*

cc_memory `p1-2-closure-path-verdict-20260619`（Codex 版补充）用最贴切的话表述历史结论：P1.2 **"可终结不等于已终结"**——机器层可关闭若干入口 gate，但语义正确性仍在显式 TCB 与外审 / 人工判断里；最终只能声称"gated chain closed and residual risks in declared TCB"，不能声称形式化零风险。

---

## 2. 认证 / 发布链的精确事实（带源）

链被写成已接受的不变量 `F-CAM-PR1-01..04`（`PROJECT_LOCK.md:252-266`），以及 §1A/C5 的 done-condition（`PROJECT_LOCK.md:139-169`）。三个接缝，每个有且仅有一个合法权威。

调用图（对齐 `CLAUDE.md:211-227` NAV / `NAV_MAP.md:8-37`）：

```
main.py
  -> src/search/outer_search.py           producer；只提交 CANDIDATE_PROPOSED
  -> scripts/run_supervisor_seal.py        生产 supervisor/certify 入口；独立命令，从 marker 驱动
     -> ExactCampaign.supervisor_seal()   唯一 durable 终态 CERTIFIED mint
        -> run_l0_supervisor_seal (L0 child verifier)
     -> publish_verified_certified_delivery_surface()  唯一公开 certified 发布口
        -> 由 resolve_p1_2_publish_open_gate 拦，除非 owner 打开 P1.2 manual gate
```

2026-07-04 后当前链应读作 `CANDIDATE_PROPOSED checkpoint -> proposal-ready marker -> scripts/run_supervisor_seal.py -> supervisor_seal() -> publish_verified_certified_delivery_surface()`；`scripts/run_supervisor_seal.py` 补的是 supervisor 可执行入口，不是 owner gate 或 publisher 放行。

### 2.1 Producer 边界 — 只提案（`F-CAM-PR1-01`）

- Producer（`src/search/outer_search.py`）在 terminal 完成时**只持久化 `CANDIDATE_PROPOSED` + 绑定的 proposal 材料**，不得直接持久化终态 `CERTIFIED`，不得发布公开 artifact。（`PROJECT_LOCK.md:55-56`, `:151-153`, `:252-254`, `:253-254`。）
- 具体代码位置（Codex）：`outer_search.py:876` terminal search status 设为 `CANDIDATE_PROPOSED_STATUS`；`:890-954` `_commit_terminal_full_frontier_certified_result` 记录 proposal run id / sink replay projection / terminal frontier evidence，然后以 `CANDIDATE_PROPOSED` 保存并写 proposal-ready marker；`:1969` 正常 terminal path 返回 `CANDIDATE_PROPOSED_STATUS`。
- **⚠ in-loop 候选判定（Opus 独有）**：`benders_loop.py:6973-6990` 会产出一个 solve 层的 `RUN_STATUS_CERTIFIED` 候选裁定，但它**明确不是** durable / publication 权威——只是候选级 claim，仍须过 sink-replay。（`PROJECT_LOCK.md:53-56`。）
- 机械强制（Opus）：`mark_campaign_stopped`（`src/search/exact_campaign.py:3601`）：
  ```python
  normalized_status = None if status is None else str(status)
  if normalized_status == "CERTIFIED":
      raise RuntimeError("CERTIFIED campaign stop must be minted by supervisor_seal")
  ```
  任何普通路径想以 `CERTIFIED` 停 campaign 都会 raise（`exact_campaign.py:3608-3610`）。
- **被否决的替代方案**：① 让 `outer_search.py` 成功即直接写 `CERTIFIED` / terminal checkpoint —— 被否，会把 candidate enumeration / solver process 本身变成 durable proof authority；② 让 candidate record 或 current-process freshness stamp 赋 proof authority —— 被 `PROJECT_LOCK.md:275` 否：strong-status proof authority 必须 **sink-replayed**，不是 producer / writer / function / closure / registry / 当前进程 fresh marker 授权。PR1 后 producer 降权，见 cc_memory `pr1-supervisor-mint-preflight`。

### 2.2 Supervisor mint 边界 — 唯一 durable `CERTIFIED` mint（`F-CAM-PR1-02`）

- `ExactCampaign.supervisor_seal()` 是**唯一 durable 终态 `CERTIFIED` mint**。它自己不算证书，委托给 PR2 L0 micro-verifier。
- **⚠ 行号**：Opus 记 `supervisor_seal` 在 `src/search/exact_campaign.py:3566`（并给出 `:3576-3599` 的委托体、`:3601` mark_campaign_stopped）；Codex 补更细：`:3470-3507`（supervisor 从 proposal-ready marker + checkpoint bytes 读取并校验 authority：checkpoint sha / strict JSON / campaign id / proposal state / run id，且要求 final status 是 `CANDIDATE_PROPOSED`）、`:3566-3599`（调 L0 seal request，非 `SEALED` verdict 即拒）、`:3601-3610`（普通 `mark_campaign_stopped(CERTIFIED)` raise）、`:3658-3660`（`save()` 拒绝 unsupervised proof-bearing terminal checkpoint）。两版一致指向同一函数，行段互补。委托体（Opus 抄录）：
  ```python
  from src.search.pr2_l0_micro_verifier_core import (... run_l0_supervisor_seal)
  ...
  verdict = run_l0_supervisor_seal(L0SupervisorSealRequest(
      project_root=self.project_root, campaign_path=self.path,
      marker_path=self.proposal_ready_marker_path,
      expected_campaign_instance_id=str(current_campaign_instance_id)))
  if verdict.status != PR2_L0_SEALED:
      raise RuntimeError(f"supervisor_seal {verdict.reason}")
  ```
- `run_l0_supervisor_seal`（`src/search/pr2_l0_micro_verifier_core.py:195`，Opus）是真正的干活者：从**磁盘**读已提交 proposal（不是任何 caller 持有的内存对象），重解析 proposal-ready marker + checkpoint，校验 marker / authority / strong-status / proof 绑定，spawn 一个**隔离 child verifier**（`run_l0_micro_verifier_round_trip`，verifier 模块 `TRUE_VERIFIER_MODULE`）独立重推 domain，然后在 checkpoint 写锁下做**写前 / 写后字节相等守护的原子写**铸 `CERTIFIED`，含写后校验与回滚（`:203-390`）。"caller 持有的内存 mapping 不是权威"（`PROJECT_LOCK.md:258`）。
- **验证更新**：`run_l0_supervisor_seal` 仍只应经 `ExactCampaign.supervisor_seal()` 委托进入；2026-07-04 后 `scripts/run_supervisor_seal.py` 是 `supervisor_seal()` 的生产（非测试）caller。`main.py` 里仍无 `supervisor_seal()` 调用，这半句保持成立。
- **被否决的替代方案**：① 让任意内部代码调用 `mark_campaign_stopped(CERTIFIED)`——代码层已禁；② "测试调用过 seal / 方法存在"等价 production closure——被 `PROJECT_LOCK.md:130-137`、cc_memory `fact-p1-2-supervisor-operability-20260626` 明确否定；③ 让 `supervisor_seal()` 依赖 caller 传入的内存 scratch state——早期外审抓到风险后改为从 disk proposal bytes 重取 authority。

### 2.3 公开发布边界 — 唯一 publisher（`F-CAM-PR1-03`）

- `publish_verified_certified_delivery_surface()`（`src/search/certified_surface.py:758`，Opus）是**唯一 certified 公开 publisher**。它：解析 campaign path、从磁盘严格重载 state；要求 `has_valid_terminal_full_frontier_certified_evidence_for_project(...)`（`:792`）；**两次**重查 P1.2 open-gate（staging 前 + commit 前）经 `resolve_p1_2_publish_open_gate`（`:802`, `:833`），gate open/missing 即 raise；stage 三 artifact，commit 前检查磁盘 campaign 字节未变（`:830-832`），把三件（final_solution.json + optimal_blueprint.json + certified_delivery_manifest.json）作为**一个事务** commit（含 backup/rollback `_commit_staged_...` / `_restore_..._backup`），commit 后再验证可发布性（`:847-853`）；任何异常 fail closed 并回滚 / 清 partial（`:856-878`）。
- **⚠ 行号补充（Codex）**：`certified_surface.py:151-171` `evaluate_certified_delivery_surface` 定义 publishable 条件（须绑定 checkpoint / terminal evidence / final_solution / blueprint / manifest 的当前性；缺失 / stale / malformed / symlinked / contradictory 全 fail closed）；`:607-649` staging 写三件并校验 manifest 与 staged 匹配；`:907-925` manifest export 明确 publishable manifests 必须走 publisher。两版行段互补。
- 通用 serializer、viewer / report builder、adapter、以及 legacy `save_certified_final_solution_and_blueprint` 兼容 wrapper（`certified_surface.py:881`，Opus）**明确非权威**——wrapper 只委托给 verified publisher。（`PROJECT_LOCK.md:259-263`, `:268-269`, `:260-266`。）
- **被否决的替代方案**：generic JSON serializer / viewer / adapter / legacy exporter 成为发布口；有 sealed checkpoint 即直接留用旧 public artifact；跳过 P1.2 publish open gate——均否。

### 2.4 阶段开放拒绝 — seal 必要不充分（`F-CAM-PR1-04`）

- 一个合法的内部 supervisor seal 对 release **必要不充分**。P1.2 owner gate 必须独立解析到显式的"关闭"形态；缺失 / 畸形 / open 的 gate 数据阻止发布。（`PROJECT_LOCK.md:264-266`，done-condition `:162-163`, `:260-266`。）

---

## 3. 为什么 `main.py` 停在 `CANDIDATE_PROPOSED`

这是**刻意留开的操作链缺口（operational-chain gap）**，不是 bug，也不是说 seal 逻辑缺失。该缺口已于 2026-07-04 由 `scripts/run_supervisor_seal.py` 补上；设计仍保留 `main.py` 普通完成不顺手 seal。

- **⚠ main.py 结构描述出入**：
  - **Opus 版**：`main.py:304` 调 `run_solve(...)`，打印 `status=...`（`:324`），唯一 keyed 在 `CERTIFIED` 上的只是**可视化**（`main.py:328`：`if status == "CERTIFIED" and result is not None: run_visualization(result)`）；`main.py` 里**没有任何** `supervisor_seal` 或 publisher 调用；引 `:304-329`。
  - **Codex 版**：`main.py:67-69` 导入并调用 `run_outer_search`；`:199` `main()` 入口；`:333` 脚本入口调 `main()`；搜索未发现 `supervisor_seal` / `publish_verified_certified_delivery_surface` / 直接 `CANDIDATE_PROPOSED` 处理。
  - 一版称入口函数是 `run_solve`（并有 `status=="CERTIFIED"` 触发可视化的分支），另一版称是 `run_outer_search`（且没找到 CERTIFIED 处理）。两版**一致结论**：`main.py` 终点是 proposal / `CANDIDATE_PROPOSED`，无 seal / publish 调用。新工程师应以实际源码为准复核这段。
- 文档确认：`CHANGELOG.md:10`（Opus）记录的是 2026-06-26 当时状态："`main.py` and current launchers do not invoke `supervisor_seal()`, so the worktree has authority methods but not a supported end-to-end supervisor command." 2026-07-04 后的现状是：`scripts/run_supervisor_seal.py` 已提供该 supervisor 可执行入口；`main.py` 终点仍是 `CANDIDATE_PROPOSED`，无 seal / publish 调用。
- cc_memory：`fact-p1-2-supervisor-operability-20260626`（predicate `production_entry_status`："supervisor_seal 已实现且有测试, 但仓库无生产 CLI/launcher/service 调用它; main.py 止于 CANDIDATE_PROPOSED"）；更全的 `p1-2-supervisor-production-entry-gap-20260626`（2026-06-26 一次 GPT-Pro 非代码文本 soundness 审计"逐文件核对发现、此前文档遗漏的关键缺口"）。
- **发现与决策**：缺口在 2026-06-23 supervisor 设计评审时浮现，2026-06-26 文本审计复确认。**刻意推后**：搭 production certify 入口（"go-live 最后通电"）排为 **PR2 task #7**，最后做，等 L0/L1 minimal-TCB 完成后——见 `pr2b-landed-pr2-remaining-status-20260628` 与 RESUME 锚 "#7"。理由：在 L0 verification TCB 证明 sound 之前接上生产 seal 调用，会有在不牢地基上铸 `CERTIFIED` 的风险，故入口刻意最后通电。该 #7 通电已于 2026-07-04 落地为 `scripts/run_supervisor_seal.py`。

历史路线决策表（Codex 版）：

| 问题 | 最终选择 | rationale | 被否决替代 | 结果 |
|---|---|---|---|---|
| producer 找到 terminal candidate 后能否直接写 `CERTIFIED` | 只写 `CANDIDATE_PROPOSED` | producer 不应成为 durable proof authority | 直接 `RUN_STATUS_CERTIFIED`/terminal checkpoint | PR1 后 producer 降权（`pr1-supervisor-mint-preflight`） |
| seal 能否由 `main.py` 顺手调用 | 不接入 `main.py`；使用独立 `scripts/run_supervisor_seal.py` | 需独立 supervisor 从磁盘 proposal bytes 重建 authority | solver process 末尾顺手 seal | #7 production certify entry 已于 2026-07-04 落地；不改变 P1.2 gate |
| 测试能调 seal 是否等价 release closure | 否 | test invocation 非 owner-approved production launcher | 把方法可用当 release | `PROJECT_LOCK.md:130-137` 明禁 |
| 单 supervisor 直接 import 全套 evaluate/publish 链是否足够 | 转向 L0/L1 split | 单 supervisor 会把 CP-SAT/search core 拖进 TCB | 单体 supervisor | `p1-2-supervisor-l0-l1-design-meeting-20260623` 记 team review 推翻 |

---

## 4. P1.2 是什么，以及命名注意

### 4.1 "P1.2" 的含义

- P1.2 的 done-condition：*`PROJECT_LOCK §1A` 命题 P 的机器边界、发布链、和 owner 手动闸同时满足*（`PROJECT_LOCK.md:145-146`）。命题 P 是那条 certified claim：70×70 `valley4_protocol_core` 底盘上 `max_lex(area, min_side)` 下的最大空矩形，由 **6 个 predicate** 把关（placement / no-overlap / per-instance placement_rule / port-binding exact-count / routing connectivity / power coverage —— `PROJECT_LOCK.md:38-98`）。
- **P1.2 明确不是吞吐定理，也不自动打开 P1.3**（`:146`）。吞吐 / 传送带带宽 / 离散容量流**显式 out-of-scope**（`PROJECT_LOCK.md:100-116`，B-1..B-3）；flow model 只诊断、永不 gate（`flow_subproblem.py:4-9`）。
- **两版视角互补**：Opus 强调 P1.2 是"命题 P 的 6-predicate 几何 + 端口精确计数 + 连通 + 供电覆盖"；Codex 强调 P1.2 本质是"**certification-chain soundness closure**"——producer/mint/publication 分权、candidate sink replay、fixed-witness、public surface currentness、phase gate、proof-bearing sink inventory、review/package provenance 等边界能否可靠关闭。二者是同一事物的两面：命题 P 是被认证的**内容**，认证链闭合是能否**可信声称**它。`CLAUDE.md:10-11`、`CHANGELOG.md:9-12` 均记录"已有 chain + fail-closed layers 但 P1.2 仍 blocked"。

### 4.2 命名注意（`naming-p1-3-vs-p1-2-fix`）

- 人类叫的下一阶段是 **P1.3**（PoseBoolExactMaster / production master integration）；机器字段里含 `p1_3b` 的名字仅为兼容保留，**不是**入口许可（`phase_1_2_spike_close.json:33-36`, `PROJECT_LOCK.md:181-185`）。
- "P1.2-FIX" 是当前"闭合 P1.2 soundness"的工作。

---

## 5. 手动闸 —— 权威文件 `data/review_gates/phase_1_2_spike_close.json`

当前状态（逐字读取）：

- `:5` `status: "blocked_manual_review_count"`
- `:8`, `:29` `current_review_anchor: "v99_p1_2_close_kernel_sealing"`
- `:9-13` `manual_review_standard`：`required_consecutive_clean_full_reviews: 3`，**`counting_authority: "owner_manual_count_outside_repo"`**，`repo_derives_clean_count_from_receipts: false`，`receipt_role: "informational_record_only"`（另见 `:404-408`）
- `:11` `counting_authority = owner_manual_count_outside_repo`（Codex 单列）
- `:14-20` 打断 clean-review streak 的五类 finding：`unsound_cut`、`certified_false_negative`、`proof_obligation_bypass`、`fake_certified_claim`、`reachable_phase_gate_false_ready`
- `:21` review receipts/reports 仅 informational，不是 clean credit 或 P1.3 entry 的机器 authority（Codex）
- `:24` `owner_manual_state.p1_2_close_status: "not_closed"`
- `:25` `p1_3b_entry_allowed: false`
- `:30` repo **不记录也不计算** 0/3、1/3、2/3、3/3；owner 保留计数
- `:32-37` / `:33-36` `next_phase_entry.allowed: false`，`authority: "owner_manual_decision_only"`，reason："Blocked by default. P1.3 entry requires an explicit owner_manual_decision; receipts, tests, structural checker passes, or an obsolete point-in-time seal cannot open this gate."；下一阶段名 "P1.3 production master integration"，机器兼容 id `p1_3b`
- `:38-386` `informational_history`（V28→V99 全史，见 §7.2）
- `:378` V99 sealing 只是 proof-bearing sink inventory / source hash / guard-token / TCB boundary；owner clean-streak 仍在 repo 外，P1.3 blocked；**并警告 post-V99 工作树改动不被旧 source-hash seal 覆盖，需重新 reseal**（另见 `:7`, `:30`）

**闸是 fail-closed by design**：repo 刻意不存进度计数，owner 在纸面 / repo 外记。cc_memory 锚：`fact-p1-2-release-gate-status-20260626`、`p1-2-current-publication-surface-status-20260626`（标题："P1.2 仍未闭合、人工 gate 仍 blocked;局部修复不得升级为 P1.2 CERTIFIED"）。

**为什么闸仍 blocked（诚实理由，`PROJECT_LOCK.md:130-137`）**——#7 supervisor 可执行入口已落地，但 P1.2 仍被这些条件卡住：
1. PR2 的其余机器条件仍未满足：#1 最小 TCB 闭包、#2/#3 loader / read-once、#5-F import-time 专门线、#9b/#9c OS 写隔离 / 原生 TOCTOU。
2. review-snapshot packager 仍从可变 `treeish` 物化而非已解析 commit，archive-policy 覆盖不全（PR1 GAP 部分已闭 —— §7.4）。
3. owner 未做、且按策略不能被自动催促做手动关闭决定；`blocked_manual_review_count` 仍是 release-block。

`PROJECT_LOCK.md:141-146` 进一步强调：PR1 split、fixed-witness、publish gate、I1 reverifier 是**已实现的 safeguard，不是 P1.2 closed**。

---

## 6. Proof-obligation gate 与 strong-status write allowlist

这两个机器 artifact 让 P1.2 soundness "具体到 review 不能悄悄漂回"——它们是**结构门，明确不是定理证明器**。

### 6.1 `scripts/check_p1_2_proof_obligations.py`

- **⚠ 规模 / 自述行号**：Opus 记全文 **4442 行**，docstring 在 `:2-6`："a small structural gate, not a theorem prover. It makes the P1.2 postmortems concrete enough that future reviews cannot silently drift back to local, duplicated proof checks."；Codex 记同类自述在 `:4247-4252`（seals proof-bearing authority surface，要求所有说 strong status 的源文件注册 / hash-bound / 分配 obligation / 带 guard tokens，但不 certify candidate、不 reason geometry）与 `:4054-4060`（V99 close claim 不能靠只改 JSON 缩小自身 authority 或 reseal source drift；改 checker 本身会 reopen review）。两处自述并存（顶部 docstring + 深处声明）。
- **在 pipeline 中的角色**：由 preflight gate 运行。`scripts/preflight_gate.py:510` 定义 `check_p1_2_proof_obligations`（preflight 内两处 caller，经 `_run_script_check` 跑脚本）；每次 `preflight_gate.py --full` 和 CI 都执行它；失败是**硬 BLOCK**（`GateResult.exit_code` 有任何 blocker 返回 1，`preflight_gate.py:117-121`）。
- **checker 当前检查范围（Codex 行段）**：
  - 必需 obligations `:76-87`（含 cut replay / master domain / terminal frontier evidence / export surface / phase gate provenance / close-kernel sealing / candidate sink replay authority）
  - close-kernel sealing tests `:369-386`（unregistered certified sink / guard token removal / registered sink hash drift / manifest strict JSON / self-binding / dependency floor drift / phase gate fail-closed）
  - public publisher contract `:1402-1457`（publisher 事务须有 evaluate / clear / strict JSON / currentness/gate checks / stage/commit/verify/rollback）
  - public writer allowlist `:1604-1657`（限制 canonical public writers 与 publisher direct call sites）
  - checker self-binding `:2133-2149`（main 须调 candidate sink replay / publication boundary / strong-status allowlist / close-kernel contract / phase gate provenance）
  - strong-status allowlist gate `:2158-2188`（用隔离 subprocess 跑 `scripts/check_strong_status_write_allowlist.py`，失败即 gate 失败）
  - close-kernel scan roots/tokens `:3772-3816`（proof-bearing tokens + scan roots）
  - unregistered/stale sink `:4384-4387`（未注册 proof-bearing sink 或 stale registered sink 报错）
  - `main()` 执行顺序 `:4788-4834`（加载 manifest → 依次跑各检查 → 打印 anchored obligations 与 sealed sink 数）

- **它验证的 manifest：`data/proof_obligations/p1_2_proof_obligations.json`（~95 KB）**。顶层 `status: "active_fail_closed_contract"`，`review_anchor: "v99_p1_2_close_kernel_sealing"`。锚 **14 条 proof obligation**（Opus 逐字表）：

  | id | statement |
  |---|---|
  | PO-STEP7-ATTACH-MIRROR | Step 7 hot-path evaluation mirrors Step 6 attachability |
  | PO-SOURCE-DIGEST-COVERAGE | Validator/generator source facts covered by one source-digest contract |
  | PO-RUNTIME-CACHE-NON-AUTHORITY | Runtime caches cannot become hidden proof sources |
  | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | Exact-safe BendersCut replay is strictly typed, all-or-nothing, faithfully encoded |
  | PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS | Certified master domain + power-witness match full-domain contract before session construction |
  | PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE | Terminal status requires strict full-frontier exhaustion evidence, not a candidate incumbent/best-effort stop |
  | PO-CERTIFIED-EXPORT-SURFACE | Export surfaces expose artifacts only after terminal full-frontier evidence committed |
  | PO-PHASE-GATE-PROVENANCE | Manual phase gate stays fail-closed, does not derive clean count from receipts |
  | PO-P1-2-CLOSE-KERNEL-SEALING | Close-kernel seals proof-bearing sink inventory, treats the gate as an attack surface |
  | PO-CANDIDATE-SINK-REPLAY-AUTHORITY | Candidate strong-status authority only via independent sink-side certified_exact replay |
  | PO-ISOLATED-EXEC-BYTECODE-BINDING | Isolated replay executes bytecode compiled from source covered by the source digest |
  | PO-TERMINAL-FIXED-WITNESS-VERIFIER | Public evidence rechecks the exact stored terminal witness (R*, π*) by rerunning binding+routing |
  | PO-EXACT-ARTIFACT-ATOMIC-SNAPSHOT | Certified session attests solved bytes: frozen artifacts snapshotted once, built from hashed bytes |
  | PO-INDEPENDENT-INFEASIBILITY-REVERIFY | Whole-layout INFEASIBLE nogoods need independent fail-closed re-verification before minting |

  **manifest 内 obligation 与 sink 注册的行段（Codex）**：`PO-P1-2-CLOSE-KERNEL-SEALING` 说明在 `:506-556`；proof-bearing tokens（含 `CERTIFIED`/`INFEASIBLE`）+ scan roots（`src` + checker + allowlist checker）在 `:792-814`；checker 自身注册为 `p1_2_close_kernel` sink `:880-907`；`check_strong_status_write_allowlist.py` 注册为 `p1_2_close_kernel` sink（含 source sha + guard tokens）`:910-927`；`certified_surface.py` 注册为 public surface sink `:1542-1562`；`exact_campaign.py` 注册为 certified path sink `:1578-1604`；`outer_search.py` 注册为 producer/certified path sink `:1674-1696`。

- **`close_kernel_contract` 块（V99 seal 心脏，Opus）**：钉死 4 `scan_roots`、8 `excluded_subpaths`、19 `critical_gate_files`、16 `proof_bearing_tokens`、13 `attack_categories`、**59 `sink_files`**（whole-file source hash 冻结）。`policy`："Small structural close kernel, not a theorem prover. It seals both the inventory of proof-bearing strong-status sinks and the sink-side isolated replay boundary … source hashes alone are not treated as proof that replay remains mandatory."
- **诚实 TCB 声明（`close_kernel_contract.trusted_computing_base`，11 项，Opus）**——被**信任而非证明**的：跑 checker + certified sinks 的 Python 运行时；一个全新的 `-I -B -X pycache_prefix=<empty>` 隔离解释器；被 `certified_exact_source_tree` 绑定的磁盘源码树；被 `compute_exact_artifact_hashes` 绑定的 canonical artifacts；solver + terminal witness validators；**deploy-pending PR2 L0 dependency-floor 占位字节**；stdlib + native 扩展（OR-Tools `.pyd/.so`）；OS 子进程 / pipe / nonce / exit 语义；文件系统字节语义；"pytest/CI exit status 与本 P1.2 边界的人工 review"。
- **`not_claimed`（7 项，Opus）**——seal 明确**不**承诺：所有软件 bug 不可能；sink verifier 或 OS TCB 的运行时变异无害；解释器 / stdlib / native bytecode 变异被 source_digest 覆盖；L0 dependency floor 跨 Python 安装可移植无需重生成；未来 P1.3B 安全；**"owner clean-review counting 或 P1.3B opening 在这里被自动化"（并没有）**；性能 / UX 被处理。

### 6.2 `data/proof_obligations/strong_status_write_allowlist.json`

- **⚠ 计数表述**：Opus 记 "schema v2，82 entries"；Codex 实跑 checker 输出 "64 registered AST node(s), 82 allowlist entry(ies)"。合并：schema v2；82 个 allowlist entry，对应 64 个已注册 AST node（两版不冲突，Codex 给出 node 数）。
- 目的（`description`）：**deny-by-default AST allowlist**，记录**每一处**可写 strong-status（`CERTIFIED`/`INFEASIBLE`）数据值或可发布 surface artifact 的位置。候选 strong status 是"untrusted data until isolated sink replay accepts their candidate_proof request"。
- `pinning_note`：每个 `source_sha256` 钉**整个模块文件**（经 `_pin_failures`），不只列出的 AST node——刻意冻结已注册的 data-ingress 与 publishable-sink 模块，直到每条被 review 并重钉。
- `root_cure_policy`："Writer identity, caller identity, closure cells, module rebinding, process-local freshness, and the compatibility wrapper are **not** proof authority." Proof authority 在 sink 侧 `python -I` replay 与下游 certified-surface validators 里。
- 这是 `PROJECT_LOCK.md:275`（F-CAM sink-replay 不变量）的机器编码：候选 strong-status 权威是 **sink-replayed**，不是 producer/writer/closure/registry/freshness 授权。

**历史教训**：checker green ≠ release green。PR2 #5 round 10-18 多次出现"忠实 reseal 后 checker 仍 green，但 GPT Pro / 本地对抗审找到 runtime hollowing / checker-self / silent channel / A4 reflection 残余"。cc_memory `pr2-5-round13-14-whitelist-landed`（Codex 版）与全局笔记记录：targeted tests 不够，必须完整 checker + full preflight + adversarial review；即便如此，结构 gate 仍不能替代 owner gate。

---

## 7. 历史时间线（诚实、含死路、按时序）

对独立重裁最重要的部分：上面的链是**长期对抗过程的幸存者**。反复出现的主题（我们当作硬教训，此处作为一条待重新检验的事实提出）：**对抗审查总能再剥一层信任洋葱；"审到零发现"不是收敛判据。**（`p1-2-review-converged-tcb-start-p1-3`，RESUME 锚。）

### 7.0 P1.2 closure path 被界定为"可关闭但未关闭"（约 2026-06-19）

cc_memory `p1-2-closure-path-verdict-20260619`（Codex 版）：P1.2 可经 consumer map / 真实路径对齐 / patch gates / algorithmic core / independent replay 逐步关闭，但"可终结≠已终结"。当时仍有 direct candidate CERTIFIED writes、cut payload allowlist、binding canonical validation、lifecycle stub illusions、consumer map 缺失、review imbalance 等问题。结果是把 P1.2 定义成 certification-chain closure，而非 solver throughput 或单点测试结果。

### 7.1 内部审计与首批外审（pre-V28 → V28）

内部 kernel 审计 C0–C5，随后三轮外审 R1/R2/R3（WS / OPEN-GATE / TOCTOU / PYC）审整条认证链，产出 FIX-1..5 + capsule + PYC 硬化（cc_memory `p1-2-fix-*`、`p1-2-capsule-f492690-fix-1-3-fix-5`、`p1-2-pyc-exec-digest-landed-88b2d32`）。第 4 轮重开 FIX-1/3；第 5 轮（两审）推翻"已收敛"claim、否决 **capsule 架构根**；`21a9dda` 三审轮审整个 HEAD、把 `sys.argv[0]` checker-identity 伪造从 tamper-only 升为 **LIVE**（`certified_artifact_contract:115`，cc_memory `21a9dda-argv0-live-12`）。包 `v28` 是一次**算法 soundness 重置**——原始 review 报告**不留仓库**（owner 仓库外维护）。

### 7.2 V28→V99 soundness-reset 阶梯（核心诚实记录）

`phase_1_2_spike_close.json:38-386` 的 `informational_history` 是新工程师最该读的东西：几乎每一轮外审都找到一个真实、本地复现的 soundness 洞，**把 owner clean-streak 重置为 0**。压缩地图（全出自该文件）：

- **V31/V32** —— Step-7 evaluator attachability 在 sibling bypass 后与 Step 6 合并；runtime-cache / source-digest 发现。
- **V46/V47-V50** —— review 协议重设计：审出**仓库派生的 receipt/report/Git 权威本身成了攻击面** → 仓库**停止自动计 clean review、停止自动打开 P1.3**。这就是 §5 里 `counting_authority` 现为 owner-outside-repo 的原因。
- **V53-V56** —— Certified BendersCut replay 忠实性（严格证据解析、整数 payload、别名冲突 member 可把多 member nogood 收紧成单文字 ban）→ cut-replay 忠实成显式 obligation。
- **V57-V66** —— 长 "certified lifecycle" 族：master-domain contract、candidate-frontier contract、terminal frontier evidence、export-surface boundary、power-witness 表示 env knobs。V66 合并成四舱：cut replay / master-domain+witness / frontier terminal evidence / export surface。
- **V73-V80** —— 中央 certified-surface verifier 合并与 authority 硬化；terminal-frontier evidence sealing；project-bound terminal evidence；delivery-manifest writer authority；canonical-surface writer pinning；env override 与 candidate-domain key 翻成 **deny-unknown**。
- **V81-V98** —— 极长尾的单 / 双 soundness 发现，每个本地复现、每个把 streak 重置为 0。代表切片（看洞有多深）：
  - V81：infeasible anchor prefix 剪掉一个候选；release builder 接受自称 CERTIFIED 的 summary。
  - V82：候选 domain 被 `h<=w` canonical 化而 master feasibility 对朝向敏感 → "只证了半个 domain 的穷尽"（在 3×3 toy 上演示了错误最优）；伪造 checkpoint cut 剪掉唯一可行 pose。
  - V83：伪造 checkpoint 发布几何不可能的空矩形；whole-layout nogoods 升级为候选 INFEASIBLE；loader 静默缩小 mandatory 集。**注意 reviewer-patch 缺陷**（把 ghost_pick 计为 occupancy 会拒绝**每一个**真结果）在 landing 时被抓。
  - V84-V98：witness scan 只证存在不证最优；artifact hashing 跟随项目外 symlink；伪造 occupancy blockers；required-optional（protocol_storage_box）遗漏；power-witness 从不 replay；unforced poles 计为 occupancy；ghost_rect anchor 从不 replay；final_result 字段 allowlist / 嵌套字段 sealing；release-status token bypass；symlink-ancestor 边界；canonical-checkpoint authority；B5A wrapper 预解析 symlink。多个 reviewer patch **弄坏了真实 solver 路径**，在 landing 时被纠正（V88：五个下游 consumer 把新 marker 当成了 facility）。
- **V99（当前锚）** —— `v99_p1_2_close_kernel_sealing`：seal proof-bearing sink inventory，加 `source_sha256` 漂移检测、guard-token 检查、显式 TCB / non-claim 边界。证据：`docs/research/p1_2_v99_close_kernel_sealing.md`、proof-obligations JSON、`check_p1_2_proof_obligations.py`、`src/tests/test_p1_2_proof_obligations.py`。**owner clean-streak 仍在 repo 外，P1.3 仍 blocked**（`:378`）。

新审查者的要点：V-阶梯**就是**没人信"它过了"的原因。每个 Vnn 都是承认前一个"已 sealed"claim 有可达的 false-CERTIFIED（或 false-INFEASIBLE → false-optimal）路径。

### 7.3 supervisor 重设计 —— PR1（producer/mint 拆分）

- **2026-06-23 设计评审**（一个多 agent **team**，非单审 —— cc_memory `p1-2-supervisor-l0-l1-design-meeting-20260623`）推翻原始单-supervisor 草案。单 supervisor 被否原因：它会调 `evaluate_certified_delivery_surface → certified_surface → exact_campaign → master_model`，把 CP-SAT solve core 拖进 TCB——与"最小 TCB"自相矛盾。**被否方案已记录。**
- 收敛设计：**L0/L1 两层** + 受控 import loader。
  - **L0 micro-verifier-core** = **真** TCB（~300-400 行，零项目 import，只做字节搬运 + 编排 + 二元裁定）。
  - **L1 orchestrator** = "verified-not-trusted"。
  - **child** = 语义 TCB（verifier + closure bytes + ortools `.so`）。
  - **四类 TCB 诚实框架**：某物可被**命名**为 TCB 当且仅当它架构上不可伪造；否则是"披着 TCB 外套的 LIVE 洞"。两条早先的 PROJECT_LOCK claim（"parent-only-relay = TCB"、"guard 不是决策权威"）被 reviewer 的 PoC **证伪并撤回**。
  - owner 选调用模型 **(a)**（独立 `certify` 命令 / L0 跑完即退的纯函数），而非 **(b)**（top-level spawn）。(b) 记为将来重接线可达。
- **PR1 landed** 为 `ddb3b5a`（cc_memory `pr1-supervisor-mint-preflight`）：使 `supervisor_seal` 成唯一 durable mint（module-private token；普通 `mark_campaign_stopped(CERTIFIED)` raise），加 `CANDIDATE_PROPOSED` 为非权威 state，剥掉 producer 的发布权，把 sink-replay 重验证（`build_sink_verified_terminal_frontier_evidence`）移到 mint 之前。
- **硬教训（记录两次）**：sub-agent review 报 CLEAN，但"两个真问题全是我全量 preflight 逮的"——mint 迁移时漏掉一次重验证，且 3 个算法测试因 mock 没跟新 sink path 而 UNPROVEN。教训：**"审 CLEAN ≠ 全量绿"**——certified-core 改动上，CLEAN 的 sub-agent review 不能替代全量 preflight（`pr1-supervisor-mint-preflight`、`mock-based-patch-mock-unproven-preflight`）。

### 7.4 PR1 发布面硬化（三轮外审，union patch）

- `072265a` HEAD 的测试债清理过了 pytest，但 `pr1-4` 外审找到**7 类未动的发布面 BLOCK**（manifest TOCTOU / 未 gate 的 canonical writer / 无 write-back rollback / stale viewer-export / fake-green checker / package 未绑 HEAD / archive 混 prompt 文件）。**"测试债收口 ≠ PR1 闭"**（`pr1-1c-external-review-7-blocks-unclosed`）。
- 解决：GPT-Pro 三轮独立 review → codex 合成**一个 union patch** → opus 环内 review → 我读源码 + 跑 `--full`/`--slow` 双绿 → landed `1817c71`，随后 cc_memory `b085a75`，push，CI 两 workflow 绿。最深修复（**D**）：checker 一直在**强制"恰好 3 处直接写"**——即它在**为一个非事务性 bug 背书**；改写成 AST staged-transaction 检查。（`pr1-publication-blocks-abc-fixed`、`pr1-soundness-b085a75-ci`、`p1-2-current-publication-surface-status-20260626`。）
- 两个残余 GAP（package `--skip-tests` 未标 + receipt 未内嵌；plugin autoload）经**4 轮跨模型对抗收敛**后关闭（receipt 内嵌、精确 test-set 绑定、treeish TOCTOU 关闭、集成 bug 只被 e2e 抓到）。**唯一不可约项**：内嵌 receipt 是自报数据；真证据靠 reviewer **重跑**——包按设计附带一条 re-verify 命令。

### 7.5 PR2 —— L0/L1 真隔离 + close-kernel 长征（进行中）

PR2 是仍开放的工作：真隔离 L0/L1 进程、controlled loader / 两段 bootstrap、B2（L0 内候选域独立枚举）、B3/BLOCK-D 完整性（L0 拥有 path + read-once + fd）、B4（`-I -S -B`）、certify 入口（#7）、AST reachability gate、argv0/contract digest。

- **PR2-b** landed `69980b3`/`592ea13`（SOUND）；codex 在 landing 前找到 2 条 false-CERTIFIED 路径（`pr2-b-codex-2-false-certified-opus-0-pr2-b-sound-tcb-b1-owner`）。关闭 load-time TOCTOU 与 caller floor 等局部项。
- **PR2 #8/#9a** landed 到 main 为 `099f5a3`（PR#2，CI 两 gate 绿含 @slow Linux 13min）。GPT-Pro 多会话 panel 找到**我和 codex 本地都漏的 3 个 BLOCK**：
  - `#8-A` checker 子进程 `-I -S -B -X pycache_prefix` 隔离（堵父进程 sitecustomize/PYTHONPATH 污染信任锚）；
  - `#8-B` `certified_artifact_contract.py` 进 V99 source-sha 楼面——**我曾亲自误判为"不需 reseal"**；
  - `#9a-A` L0 runtime byte-pin manifest + 删自动生成器（**TOCTOU 时序旁路**：gate 钉了字节但 runtime loader 没消费 pin、会自动生成）。
  - 成 claim-guard 卡 **`close-kernel-pin-reaches-runtime`**：① "现状没钉" ≠ "不需 reseal"——让文件成信任锚就必须钉；② "gate 钉" ≠ "runtime 钉"——pin 必须到 runtime 消费点 + fail-closed，否则 gate↔runtime "读了但不再验" 的 TOCTOU 打开。
  - **⚠ Deploy-pending 注意（仍开放）**：被钉的 `pr2_dependency_floor_manifest.json`（sha `41008dbb…`，size 574082）是**GPT sandbox 里生成的 audited-Linux-env 占位、非生产审过的 canonical**。`close_kernel_contract.dependency_floor_provenance.manifest_provenance_status = "deploy_pending_placeholder_regenerate_on_production_cachyos_py313"`。生产前**必须**在 CachyOS + Py3.13 重生成、审、重钉（PR2 task #6）。开发机是 WSL/Ubuntu，无 CachyOS distro、无 Py3.13 venv，**本机生不了**。`mutation_policy` 为 `dependency_floor_drift_reopens_p1_2_close_claim`。

- **PR2 #5 —— "close-kernel" AST-pin 长征（最长线;后续已收口:round-19/20 完成后由 `6e06922` 合入 main,外审循环 2026-07-03 画线停止——本小节其余为合入前史料）**。分支 `pr2-5-domain-frontier-gate`。起因：L0 child 升格 proposal 为 `CERTIFIED` 时漏设 `declare_mode`/`last_stop_reason`（只改 `final_status`），使 frontier-exhaustion / domain-canonical 校验在 durable seal 路径上成**死代码**——恶意 producer 可对切片 / 非穷尽域铸 false durable CERTIFIED（`pr2-5-seal-frontier-gate-landed`）。修复本身直接；**长征**是其后一切，也是信任洋葱问题最好的例证：
  - **⚠ round 提交链出入（保留两版全部）**：
    - **Opus 版完整链**：`2ec8954`→`2c258c6`→`4410b6a`→`dbd1d72`→`b6d41c6`→(main `d816b8b`)→`cce5dd5`→`dbe27c0`(r7)→`c115f31`(r8)→`7851c1e`(r9)→`a5a5e64`(r10)→`adeddc5`(r11)→`8714ee7`(r12)→`504b3f8`(r13)→`d1a59ad`(r14)→`1b90285`→`c96a601`(r16)→`2ca6864`(r17)→`9bbb3a6`(r18，分支当前 HEAD)。
    - **Codex 版**（仅列出核对到的子集）：`504b3f8`(r13)、`d1a59ad`(r14)、`9bbb3a6`(r18)。两版对 r13/r14/r18 一致；Opus 给出更全的中间链。
  - **round-14 判定**：Codex 记 round-14 `d1a59ad` 被**第 11 轮 GPT Pro 6-panel 判 NOT sound（收敛 BLOCK）→ round-15**（也与当前 git log 顶部 `b35e5f9 memory: PR2 #5 round-14 第11轮外审 triage — NOT sound…→ round-15` 一致；cc_memory `pr2-5-round14-11th-review-block-round15`）。
  - **元模式**（cc_memory `close-kernel-block-convergence-trend-20260630`）：**每个外审 BLOCK 比上一个深一层 indirection**（钉 X → X 的字段 → 函数体表达式 → 被审的 AST ≠ 运行时对象 → writer 引用的 globals/helper → 它调的 gate → …）。round-9 曾声称"123/123 可达 cert helper 已钉"；被**证伪**，逼 round-10 钉**一切**（3 文件里每个 def/class/method/constant，closed-world + import allowlist）。
  - **F 线单列（owner option 1，2026-07-01）**："import-time execution integrity" 子问题（`.pyw`/`scripts.*`/`importlib.__dict__`/def-time 隐式副作用）经枚举证明**不收敛**——"import-time 图灵完备，穷举不完"。owner 决定把 F **单列成专门线 PR2 #5-F**，紧邻 #1；round-12 的 F 代码作为 best-effort 留门里，但 F 的完整性**不是 merge blocker**。（harness `pr2-5-F-line-import-time-integrity-schedule`，cc_memory `pr2-5-round10-11-12-fspinout`，教训卡 `close-kernel-ast-checker-design-lessons`。）scope = ① import-machinery 完整性（有界）② 动态 import 完整性（有界）③ 非-import import-time 副作用（开放，设计 spike：追全 / 最小化 import-time TCB / 接受残余 + floor + 人审）。
  - **A4 dynamic-reflection rebind —— owner 接受为残余（2026-07-02）**：rounds 15-17 不断找到新形态（`exec` → `operator.setitem(globals(),…)`/`types.FunctionType` → `.__globals__[...]` → `sys._getframe().f_globals` → `sys.modules[__name__].witness=`），一次 5-lens codex 对抗 workflow 确认 A4 denylist **不确定性收敛**（每加一个 attr 只是掀开下一个）。因 witness 函数已被逐字节 source-sha 钉死（改它们 = clean-review 抓得到的显眼 diff），owner **（AskUserQuestion）决定接受 A4 dynamic reflection 为 best-effort / conspicuous-edit 残余——与 F、checker-self 同类——不再把 A4 完全闭合当 release blocker**。round-18（`9bbb3a6`）加了已知形态的 best-effort 覆盖。
  - **根本边界**（`close-kernel-ast-pin-structural-vs-semantic-boundary`）：AST/source-sha "第二道门" 能保护**结构**（防未来维护者一边保持 checker 绿 + 重钉 floor、一边掏空 elevation 语义），但**保护不了证明数学**——叶子 occupancy/mandatory/power 数学终归 bottom out 到 sha 楼面 + frozen-artifact hash + 人工重钉审查。owner 接受此边界并要我诚实标注。
  - **⚠ 当时状态出入（2026-07-02 快照,WAITING_EXTERNAL;后续:第 12 轮外审未再发,round-19/20 本地收口后 `6e06922` 合入 main）**：
    - **Opus 版**：round-18 `9bbb3a6` 绿（full preflight PASSED，**3734 pytest**，3 runtime 文件字节未动，committed blob sha == pins，CI-safe）。第 12 轮 GPT-Pro relay 包已备（`zmd_pr2_5_round18_9bbb3a6.7z`，sha `5a59999f…`）含 6 角度提示词，等 owner 跑。**结构 BLOCK 在 rounds 15-18 后归零**（3 外审 panel + 本地 codex 5-lens + owner 残余裁定）；剩余残余明确三类、全靠 conspicuous-diff + 人工 clean-review 兜底：(i) import-time #5-F、(ii) checker-self（改 checker 本身的维护者）、(iii) A4 dynamic reflection。CLEAN 回：merge `pr2-5`→main（CI @slow）→ 续 PR2 #2/#3/#1(含 #5-F)/#9b/#9c/#7。若出**新**的静默 / 可约结构 BLOCK：round-19。
    - **Codex 版**：round-18 `9bbb3a6` 在 `pr2-5` worktree/branch 通过 preflight，准备第 12 轮 GPT Pro relay；但反复强调 P1.2 仍 release-blocked，且 **`9bbb3a6` 是另一 worktree/branch 状态、当前 cwd main（`b35e5f9`）不应自动继承该结论**；当前 cwd checker 输出 59 sinks，而 round-18 报告 60 sinks（见 §0 的 ⚠）。
    - 两版一致（当时）：round-18 是当时分支进度、WAITING 第 12 轮外审、不改变 release-blocked。（实际后续走向:外审不再发,round-19 `5ff31ac` / round-20 `2413cc2` 本地收口,`6e06922` 合入 main。）
  - **元教训（提出，非定论）**：RESUME 锚明写——"逐形态 denylist 对图灵完备/反射面永不收敛,该早识别并归 conspicuous-edit 残余而非无限迭代."。新工程师可合理质疑 rounds-10→18 是否该更早收敛到"接受 + conspicuous-edit 残余"。此判断留开。

---

## 8. 被否决的替代方案（决策记录）

- **单-supervisor 设计** —— 2026-06-23 否决（把 CP-SAT 拖进 TCB；§7.3）。
- **调用模型 (b) top-level spawn** —— owner 选 (a) 独立 certify 命令；(b) 记为重接线可达。
- **两条被撤回的 PROJECT_LOCK TCB claim**（"parent relay = TCB"、"guard 不是权威"）—— 被 reviewer PoC 证伪、在 L0/L1 设计中撤回。
- **仓库派生 / receipt-based clean-review 计数** —— V46-V50 移除，因 receipt/report/Git 权威本身成攻击面；替换为 owner-outside-repo 手动计数。
- **正则 Stop-hook 巡查"要不要继续"措辞**（harness 级、非认证）—— 永久弃用；仅记以防重蹈。
- **PR2 #6 专门 AST-reachability gate** —— 决定**不**建（checker 自己的注释承认它是冗余层；source-sha 楼面是主防线，已被 #8-B 强化）。
- **把 A4 完全闭合当 release blocker** —— 放弃，改 best-effort + conspicuous-edit 残余（owner 裁定，§7.5）。
- **让 outer_search 成功即写 CERTIFIED / candidate 或 freshness stamp 赋权威** —— 否（§2.1，`PROJECT_LOCK.md:275`）。
- **generic serializer/viewer/adapter/legacy exporter 成发布口 / 有 sealed checkpoint 即复用旧 public artifact / 跳过 publish gate** —— 否（§2.3）。
- **盲应用外审 patch** —— 长期策略是**绝不**原样应用 GPT-Pro/codex diff（带 `/mnt` 路径、pytest 噪音、有时真 bug——如 V83/V88 patch 弄坏真 solver 路径、某 `#9a` patch 预解析 sentinel 成绝对路径致 child 拒绝）。patch 按 spec 重实现，然后我做终裁 + 全量 preflight。

---

## 9. 诚实的开放残余、死路、已知边界

1. **生产 seal 入口已落地，但不是 release closure。** `scripts/run_supervisor_seal.py` 是 `supervisor_seal()` 的生产 caller；`main.py` 终点仍是 `CANDIDATE_PROPOSED`。PR2 #7（certify 入口）已于 2026-07-04 通电，且只补这一条机器条件。
2. **P1.2 闸默认关闭、owner 手动、在 repo 外。** repo 不能开；只有显式 `owner_manual_decision` 能开，且需 owner 在纸面数满 3 连续 clean full review。
3. **V99 锚是时间点快照。** post-V99 工作树改动不被旧 source-hash seal 覆盖，任何 close claim 前须重新 reseal（`phase_1_2_spike_close.json:7`, `:30`）。
4. **dependency-floor manifest 是 deploy-pending 占位**（audited Linux env 字节，非生产 canonical）；生产前必须在 CachyOS/Py3.13 重生成 + 审 + 重钉（PR2 #6）——当前 WSL/Ubuntu 主机做不了。
5. **close-kernel 残余仅按 conspicuous-edit 接受**（非架构闭合）：import-time execution integrity（#5-F）、checker-self 变异、A4 dynamic reflection rebind。靠人工 clean-review 抓显眼 diff 兜底。
6. **PR2 仍开放（真实 backlog、当前不排期）：** #2/#3（loader min-snapshot+fd / read-once）→ #1（最小 TCB 闭包，含 #5-F）→ #5 独立枚举 → #8 深化 → #9b/#9c（OS write 隔离 / native `.pyd/.so` TOCTOU）。#5 close-kernel 结构门已不在此列（round-19/20 后 `6e06922` 合入 main,外审画线停止）。#7（production certify 入口）已于 2026-07-04 由 `scripts/run_supervisor_seal.py` 落地，但不关闭这些剩余项。另有押后的 **resume-envelope finding**（`pr2-resume-envelope-deferred-finding`，commit `05a2a85`）：非证明字段如 `created_at` 克隆进 durable state 能过终态门但 resume 时自拒——判真但越界、押后到 #2/#3。
7. **收敛问题哲学上开放。** "审到零发现"明确**不是**收敛判据；收敛 = 画并冻一条 TCB 线、在其上修、把线下新发现声明为受信假设或 done-instance（`p1-2-review-converged-tcb-start-p1-3`）。当前 TCB 线是否画对是新审查者该压的活问题。
8. **certified scope 窄、不得过度声称。** 只有 `valley4_protocol_core`（70×70）active；6 个 predicate 证的是**几何 + 端口精确计数 + 连通 + 供电覆盖**，**不是**吞吐 / 带宽 / 离散容量流（`PROJECT_LOCK.md:100-116`）。flow model 只诊断、永不 gate。
9. **A4 / F / checker-self 的"必须显眼改才能绕"残余分类**是历史 owner/codex/GPT Pro 互动下的工程裁定，**不是数学消除**。新工程师可重新挑战该分类。
10. **⚠ 分支 vs main 状态未同步（2026-07-02 快照;此警告已随 `6e06922` 合并失效——close-kernel 工作已全在 main）。** round-18 `9bbb3a6` 是 `pr2-5-domain-frontier-gate` worktree 状态；当时 cwd main 是 `b35e5f9`（`origin/main` `5ab006f`）。PR2 剩余项中有些可能已在别的 branch/worktree 有进展，新工程师应从当前 git branch、review gate、PROJECT_LOCK 和实际 tests 重新核，不要自动继承。

---

## 10. 可追溯性索引（下一步去哪看）

- **权威闸**：`data/review_gates/phase_1_2_spike_close.json`（`informational_history` 含 V28→V99 全史）。
- **权威不变量**：`PROJECT_LOCK.md` §1A（`:38-169`，尤其 F-CAM-PR1-01..04 在 `:252-266`，C5 done-conditions 在 `:139-169`；另 `:130-137` open/blockers、`:141-146` safeguards≠closed、`:151-163` hard boundary、`:181-185` 不得推断 closed、`:275` sink-replay 权威、`:100-116` throughput out-of-scope）。
- **链源码**：
  - producer：`src/search/outer_search.py:876` / `:890-954` / `:1969`（Codex）；`benders_loop.py:6973-6990` 候选 RUN_STATUS_CERTIFIED（Opus）；`main.py:304-329`（Opus，`run_solve`）/ `main.py:67-69,199,333`（Codex，`run_outer_search`）。
  - supervisor：`src/search/exact_campaign.py:3566`（`supervisor_seal`，Opus）/ `:3470-3507,3566-3610,3658-3660`（Codex）；`:3601` `mark_campaign_stopped`；`src/search/pr2_l0_micro_verifier_core.py:195`（`run_l0_supervisor_seal`，`:203-390`）。
  - publisher：`src/search/certified_surface.py:758`（`publish_verified_certified_delivery_surface`，Opus `:792,:802,:830-832,:833,:847-853,:856-878,:881`）/ `:151-171,607-649,758-878,907-925`（Codex）。
  - argv0 LIVE：`certified_artifact_contract:115`。
- **Gate**：`scripts/check_p1_2_proof_obligations.py`（⚠ Opus 记 4442 行、docstring `:2-6`；Codex 记自述 `:4247-4252`、`:4054-4060`；检查行段 `:76-87,369-386,1402-1457,1604-1657,2133-2149,2158-2188,3772-3816,4384-4387,4788-4834`）+ `data/proof_obligations/p1_2_proof_obligations.json`（14 obligations + close_kernel_contract 59 sinks；manifest 行段 `:506-556,792-814,880-907,910-927,1542-1562,1578-1604,1674-1696`）；`data/proof_obligations/strong_status_write_allowlist.json`（schema v2，82 entries / 64 registered AST nodes）；经 `scripts/preflight_gate.py:510`（`:117-121` exit code）运行。（`production_readiness_gate.py` 只 gate **campaign 启动**——freeze/venv/OOM——**不** gate P1.2 closure。）
- **cc_memory（读 `--body`）**：`fact-p1-2-release-gate-status-20260626`、`fact-p1-2-supervisor-operability-20260626`、`p1-2-supervisor-production-entry-gap-20260626`、`p1-2-current-publication-surface-status-20260626`、`p1-2-supervisor-l0-l1-design-meeting-20260623`、`p1-2-closure-path-verdict-20260619`、`p1-2-closegate-obligation-mechanism`、`pr1-supervisor-mint-preflight`、`pr1-publication-blocks-abc-fixed`、`pr1-1c-external-review-7-blocks-unclosed`、`pr1-soundness-b085a75-ci`、`mock-based-patch-mock-unproven-preflight`、`21a9dda-argv0-live-12`、`p1-2-capsule-f492690-fix-1-3-fix-5`、`p1-2-pyc-exec-digest-landed-88b2d32`、`p1-2-fix-*`（族）、`naming-p1-3-vs-p1-2-fix`、`pr2b-landed-pr2-remaining-status-20260628`、`pr2-8-9a-hardened-landed-099f5a3`、`pr2-b-codex-2-false-certified-opus-0-pr2-b-sound-tcb-b1-owner`、`pr2-5-seal-frontier-gate-landed`、`pr2-5-round8-9-converged-relayed-20260630`、`pr2-5-round10-11-12-fspinout`、`pr2-5-round13-14-whitelist-landed`、`pr2-5-round14-11th-review-block-round15`、`close-kernel-block-convergence-trend-20260630`、`close-kernel-ast-pin-structural-vs-semantic-boundary`、`close-kernel-pin-reaches-runtime`、`close-kernel-ast-checker-design-lessons`、`pr2-resume-envelope-deferred-finding`、`p1-2-review-converged-tcb-start-p1-3`。
- **关键 commit**：`ddb3b5a`（PR1 foundation）、`1817c71`/`b085a75`（PR1 union soundness）、`072265a`（PR1 测试债 HEAD、被 pr1-4 挖 7 blocks）、`099f5a3`（PR2 #8/#9a，PR#2）、`69980b3`/`592ea13`（PR2-b）、`21a9dda`（三审 argv0 LIVE）、`05a2a85`（resume-envelope 押后）、`d816b8b`（pr2-5 故事 / main）、`d68bdc9`（memory.db 版本参照）；分支 `pr2-5-domain-frontier-gate` HEAD `9bbb3a6`（close-kernel round-18，未合入）；第 12 轮 relay 包 `zmd_pr2_5_round18_9bbb3a6.7z`（sha `5a59999f…`）。**⚠ 当前 cwd main HEAD `b35e5f9`、`origin/main` `5ab006f`**（Codex 观测）。
- **RESUME 锚（最新逐轮细节）**：`C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory\p1-2-resume-state-20260621.md`（顶部 ▶▶▶▶ 段最新；round-18 状态在 `:12-16`）。另 harness 线 `pr2-5-F-line-import-time-integrity-schedule`。
- **docs**：`docs/research/p1_2_v99_close_kernel_sealing.md`、`src/tests/test_p1_2_proof_obligations.py`、`src/tests/test_p1_2_fixed_witness_terminal_verifier.py:309`。

---

## 11. 给新工程师的最小事实包（一句话底线）

不要从"测试过"或"checker 绿"推导 release。当前唯一可信叙述：

```text
main.py
  -> outer_search.py                     producer 只提交 CANDIDATE_PROPOSED
  -> scripts/run_supervisor_seal.py      生产 supervisor/certify 入口；独立命令，从 marker 驱动
     -> ExactCampaign.supervisor_seal()  唯一 durable 终态 CERTIFIED mint
     -> publish_verified_certified_delivery_surface()  唯一公开 certified publisher
        -> 仍被 P1.2 manual gate 拦住，除非 owner 打开
```

代码有三个真实、有测试、source-pinned 的权限接缝 + 一套深 obligation/allowlist 脚手架——但 P1.2 是 **OPEN/BLOCKED**，**无**端到端生产 seal 实跑记录（`run_supervisor_seal.py` 入口已存在,但从未有真实 campaign→seal 走通），review 锚是时间点快照，dependency floor 是占位，三类残余攻击面仅在"conspicuous-edit + 人工 clean-review"下被接受。把任何"它过了 / 方法存在"当作**必要不充分**。V-阶梯是这套姿态"挣来的、不是偏执"的证据。


---

# 第 3 章 · 早期史：算法核心 C3 审 · PR1 发布面 soundness · capsule 架构推翻 · supervisor L0/L1 重做 · 吞吐认证为何排不进

> **读者须知（写给从零接手的新工程师）**：这份是**史实 + 决策记录**，不是"照结论办"的说明书。每个决定都尽量写清了 **当时为什么这么定 / 认真考虑过但否掉了什么 / 结果如何**，并保留 **失败、返工、误判、被推翻、以及至今没闭的残余**。你完全可以拿着源码和 `PROJECT_LOCK.md` 独立再判——owner 请你来，部分目的就是想看你能不能发现我们当时的盲点（尤其算法核心层，见 §7/§10）。
>
> **本章由两份独立史料合并而成**（一份 Opus 挖、一份 Codex 挖，各自独立从 cc_memory / CHANGELOG / PROJECT_LOCK / git / RESUME 提取）。凡两版有分歧、或一版独有的引用/行号，均以「**⚠一版称…另一版称…**」显式标注、不擅自取舍。所有 `file:line` / cc_memory id / git 短 hash 都保留供你独立复核。**注意时效**：cc_memory 里的 `file:line` 是当时快照，行号可能已漂移；落地前对当前源码复核（读 cc_memory 全文用 `python cc_memory/mem.py read <id> --body`，读 git 用 `git show <hash>`）。

---

## 0. 证据范围 + 坐标系（术语 + 相位命名）

### 0.1 证据范围与两版的检索路径（诚实边界）

- **主 RESUME 锚**：`C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory\p1-2-resume-state-20260621.md`。⚠ Codex 版给出该文件规格「67 行 / 56,003 bytes，最新段覆盖到 2026-07-02，早期史关键在 `:43-77`, `:86-90`（另引 `:43`, `:44`, `:53-57`, `:60-66`, `:71-72`, `:86`）」；Opus 版只把它列为「PR2 后续主源」、未给行号。
- ⚠ **检索可用性差异**：Codex 版报告 `cc_memory search "PR1 soundness"` / `"capsule supervisor L0 L1"` / `"flow throughput 吞吐"` 在本机**返回 `no matches`**，实际路径是先从导出索引 `cc_memory/exports/MEMORY.md:112-138` 定位 id、再 `read --body` 读全文；Opus 版未报告 lexical 检索失败。两版都强调：lexical 无命中 ≠ 无史料。
- **两版共同局限**：都没逐字重读所有原始 GPT 外审回包目录，只读了项目记忆中已沉淀的全文条目、RESUME、git、锁文件、当前源码。

### 0.2 自造术语（不懂它下面全是雾）

- **`certified_exact` vs `exploratory`**：两条严格隔离、绝不能串的求解路径。只有 `certified_exact`（默认 `--mode`）有资格产出证明材料；`exploratory` 只是启发式探针/提示，其产物（caps/hints/probe/sidecar）**永远不得**升格成 certified 证据。
- **producer / supervisor / publisher 三段链**（整个 P1.2 的骨架）：
  - producer（`src/search/outer_search.py`）只提案，最多写 `CANDIDATE_PROPOSED`；
  - `ExactCampaign.supervisor_seal()`（`src/search/exact_campaign.py`）是**唯一**能铸造 durable terminal `CERTIFIED` 状态的入口；
  - `publish_verified_certified_delivery_surface()`（`src/search/certified_surface.py`）是**唯一**对外公开 certified 工件的中央发布器。
  - 权威锁佐证（Codex 引）：candidate strong-status proof authority 是 **sink-replayed**，**不是** producer/writer/function-identity/closure/registry/current-process 授权（`PROJECT_LOCK.md:275`）。

### 0.3 相位命名（owner 2026-06-22 定，cc_memory `naming-p1-3-vs-p1-2-fix`；此小节 Opus 独有）

- **P1.2** = 闭 certified soundness（**不新增证明能力**，只堵漏）。
- **P1.2-FIX** = 三/四/五轮外审挖出的 soundness 必修（fixed-witness verifier + 不可变执行 capsule + OPEN-GATE 机器发布闸 + I1 独立复验 + TOCTOU 修复 + doc↔code 漂移红测）——是闭 P1.2 的前提，**不是** P1.3。
- **P1.3** = 把 `src/cuts/lifecycle.py` 的 `step_8_apply_to_master` 真正接进活 master（PoseBoolExactMaster LBBD 集成）。owner 手动闸打开前不准动。旧文档里的"P1.3B / P1.3A 主体"都指同一坨 master 集成活；机器闸标识符 `p1_3b_*` 是历史名、不动（改名要碰 close-kernel = 另一次 freeze-ritual）。
- **顺序**：先做 P1.2-FIX 闭 P1.2 → 再开 P1.3。
- **PR1 / PR2**：supervisor 重做被切成两个 PR。PR1 = supervisor_seal + 剥发布权 + resume 语义 + producer 侧 BLOCK-D + marker + 复验迁移 + 发布面事务化/checker 硬化。PR2 = L0/L1 最小 TCB micro-verifier + 受控 import loader + 两段式自举 + child read-once + import-closure + certify 生产入口 + AST 闸。**PR2 至今没完**（接手时它在 #5 那一坨的第 14/15 轮外审里，属维度 4/5;后续 #5 close-kernel 已走到 round-20 并由 `6e06922` 合入 main,"没完"的含义转为 #1/#2/#3/#5独立枚举/#8/#9 未排期 backlog），本章只讲到 PR1 落地为止。
- **close-kernel / V99 floor**：用 `source_sha256` 把"强状态出口 sink"钉死的机制（详见 §1.2），后面反复出现。
- **外审 = GPT Pro**：多个独立 reviewer（常 3 个）盲审（blind A-G）打包好的仓库快照，owner 中转提示词与回复。这是本项目**收敛判据的核心工具**。

---

## 1. 地基裁决（2026-06-19）：两场 agents team 会议定了后面所有事的调子

> ⚠ **本节 Opus 独有**——Codex 版史料从 2026-06-20 的 C3 审开始，未覆盖 06-19 这两场奠基会议。它们不是代码，但你后面每次看到"信任洋葱""TCB 线""close-kernel 只是 lint"，根都在这里。会议形态 = 多智能体对抗（2 claude + 2 codex 或 4+4，"2c2c+contrarian"，双向认账才算收敛）。

### 1.1「P1.2 能不能闭、闭到哪层」—— `p1-2-closure-path-verdict-20260619`

8 人会议（obligation-enumerator / done-criteria / history-miner / pragmatic-roadmap [claude] + convergence-skeptic / coverage-prover / independent-reverify / contrarian [codex]）+ 代码实证，四方一致：

- **原理可终结，但"可终结 ≠ 已终结"**：CERTIFIED 被算错的信息流信道**先验有界**——布尔合取被算错只有三处：逻辑漏算(A) / 投影污染(B) / 输入源不真(C)，信息论穷举；再加第四信道 D = phase-gate provenance。全史 V31–V98 零反例。deny-by-default 白名单是闭集。
- **分层闭合（关键结论）**：
  - **入口门控层 = 可机器真闭**：deny-by-default 白名单 + AST allowlist 机械闭包，把"枚举所有攻击"(∀) 变成"所有 CERTIFIED 写入点都在 allowlist 内"这个可验证闭包。**AST 级强于子串扫描**（记住这句，后面 close-kernel 反复栽在子串扫描上）。
  - **语义正确性层（validator 用对不变量：nogood⊆真不可行 / master 域编码正确 / 剪枝单调）= 永久显式 TCB 残留**：可逐项独立重验，但"所有语义义务列全了"**无法机器穷举证明**（contrarian 终审："义务穷举 ≠ 形式证明完整，别让穷举冒充证明"）。
- **当时代码卡在哪（7 条，已代码实证定位）**：深层入口绕 terminal gate（`mark_candidate_result` 直写 candidate CERTIFIED；terminal INFEASIBLE 只写 `final_status` 不验 evidence；exploratory 路径 `outer_search.py:2784` 直产 `search_status=CERTIFIED` 无 gate）；cut cert payload 无统一 ALLOWED_FIELDS；binding 绕 on-disk canonical role 校验（`binding_subproblem.py:391`）；**闭合对象未校准**——`lifecycle.py` 的 F1–F9 是没接进真路径的 stub 孤岛（Step8 `NotImplementedError`），真路径是 `benders_loop→cut_manager→exact_coordinate_master`，187 个 PO 测试里 14 个（7.5%）打在孤岛上 = 覆盖虚高；consumer map 未建；**审查面失衡：18 轮火力全压表层认证发布层，深层算法核心欠正面审**（这条埋了 §7 的雷）。
- **对外口径（contrarian 定的发布阈值，至今有效）**：**不宣称"形式化零风险"，只宣称"认证链门控已闭合，剩余风险在声明的 TCB 内"。** 你交付任何东西都不能越过这条。

### 1.2「V99 close-kernel 到底有没有必要」—— `close-kernel-necessity-verdict-20260619`

**最该让你警惕的一条元裁决。** close-kernel 把"强状态出口"用 hash 钉死。四方（含最初判它"纯修辞"的 skeptic 逐行核代码后撤回）一致裁：

- **本质 = "被包装成闭合证明的 sink hash-pin lint"**。真必要的内核（占 35–45%）：强状态出口 sink 登记 + `source_sha256` + 磁盘 hash 真盾 + found↔registered 双向对账 + drift→fail-closed + 三个自保字段（V99 hash floor 锚 checker 源码，防"改源码+同步改 manifest hash"双写绕过 / MIN_SINK_COUNT 防缩表 / self-binding 防删调用入口）。
- **但 55–65% 是过度包装 + 治理退出**：把它升格叫"闭合系统 / P1.2 技术封口"是**纯命名修辞**，诞生在"外审死胡同"里、净效果是宣布闭合。
- **三条设计病，逐条记住**：
  1. **虚假安全感（最危险）**：`V99 CLOSED` 绿灯会把注意力从算法层（V81–V98 十八轮反复出血处：半域 / forged cut / 几何不可能矩形发 CERTIFIED）引开，**给没审的地方发及格证**。= owner 最初"想审算法却被认证层带走"那个病的系统化固化（§7 的原始出处）。
  2. 名实不符：子串扫描 / 子串 guard / 浅 AST self-binding 撑不起"闭合系统"。讽刺的是——子串扫描正是项目 V92 自己抓过的"embedded token 绕过 literal-match"同种病。
  3. 扫描面完整性无证明：把 registry 完整性当成 scanner 完整性。
- **处置（四方一致）**：留 ④a + 三自保字段 + CI 门禁化；sink discovery 从子串升级成 AST/符号级；**标签改成 "sink hash-pin gate"，语义仅 = "强状态出口清单本 checkpoint 未漂移"；P1.2 algorithmic soundness 单独标 open，green anchor 绝不替未受审算法层背书。**

> 提醒：后面你会看到无数次"close-kernel 全绿 / preflight PASSED"。**那从来不等于算法层 sound，也不等于 P1.2 闭合**。2026-06-19 就钉死了。

---

## 2. C-审基线 + sink-replay 隔离根治（2026-06-20）

### 2.1 ④b sink-replay 隔离重放根治 —— `p1-2-4b-sink-replay-rootcure-landed-20260620`（commit `a5ff5aa`）

> ⚠ **本节 Opus 独有**——Codex 版未单列 ④b / `a5ff5aa`。

**问题**：早先想用 `sys._getframe` 运行期栈帧锁挡"同进程可变对象冒充证明权威"，但会议判定这是**停机问题、不可终结**（同进程对手总能再绕）。

**决定（owner+codex 2026-06-18 亲自下单的方向）**：别再加 closure 锁；不让同进程可变对象当证明权威；改成 **sink 端独立验真 + 隔离 producer**。机制：candidate 自报的 CERTIFIED/INFEASIBLE 当**不可信数据**；frontier pruning / terminal / manifest / public surface 只信"sink 端在干净 `python -I` 子进程里重跑 `run_benders_for_ghost_rect` 确认"的强状态；未被 replay 接受的强状态降 UNPROVEN 并剥 solution/proof。生产 src 里 `getframe`/`__closure__`/`cell_contents` 运行期权威全删。

**被否方案**：(c) terminal-only replay（搜索期信未 replay 的 raw INFEASIBLE 剪枝）——**否**，会重开 forged-INFEASIBLE 剪掉真最优的洞。

**结果 / 残留**：soundness 真 sound；patch 评估 council（7+4 agent）+ re-seal workflow 当场抓出"实现者+3 验证者都漏测、`test_exact_contract` 全绿是假象"、揪出 3 个断掉的 frontier 契约测试并修了。**性能残留归 P1.3**：root-cure 在 outer_search 主循环每轮 + 内层 precheck 每圈对全部累积强候选**无缓存全量 re-replay**（每个冷启子进程重解 Benders）→ 168h 生产跑可能烧光预算退 UNKNOWN、出不了 CERTIFIED。perf 会议（4/4 收敛）裁走 (a) 内容哈希缓存 + (b) 增量 candidate_keys，3 硬条件保 soundness（键完备含 `source_digest` / 命中后仍每轮跑 shape 校验 / source 或 artifact 任一变强制全量 re-replay）。**真 168h 生产前必做，至今没做。**

### 2.2 C3 内核正面审（2026-06-20）—— `p1-2-c3-kernel-audit-3source-20260620`

**这是唯一一次正面审算法核心**（回应 owner 18 轮原始关切）。三源对抗：claude+codex（API workflow）+ **GPT Pro（数学论证面）**。结论：**当前 certified 活路径不能建立完整 soundness 定理。**

- **I1 nogood ⊆ 真不可行 = GAP（三源一致）**：whole-layout INFEASIBLE nogood（⚠ Opus 给发射点 `benders_loop.py:7452 _add_exact_whole_layout_nogood` → `master.add_benders_cut`；Codex 未给行号）信子问题 CP-SAT 自报 INFEASIBLE + 模型忠实，**落 cut 前零独立 ⊆-infeasible 复验**。能造成 proof-bearing false-INFEASIBLE（over-constrained 子问题模型 → 误剪真可行布局 → 抹真最优 → 发出次优的 CERTIFIED）。诚实边界：GAP = "缺独立复核防线"（确定），**不是**"已发现具体 over-constraint"（两源都没做子问题编码忠实性逐约束审）。修法 = 独立异构 ⊆-infeasible 复验器 → 工程量、非研究级 → 进 P1.2-FIX（后来的 FIX-4）。
- **吞吐 gap = 独立 CRITICAL false-CERTIFIED（GPT Pro 独家挖出、主控已核实代码）**：routing FEASIBLE 就 CERTIFIED、flow 只诊断不 gate。⚠ Opus 引 `benders_loop.py:6927-6944` + `flow_subproblem.py:4-9` + PROJECT_LOCK 锁死；Codex 引 `flow_subproblem.py:4-9`（"certified_exact 中不得单独产生正式剪枝证书，INFEASIBLE/UNKNOWN 只能按模式解释"）+ `:119-149`（"Certified-exact diagnostic only; not a pruning oracle"，求解器 GLOP 连续 LP）。**是故意锁死、不是 bug**——但对外没说清"不证吞吐" = overclaim。owner 拍：吞吐 OUT-OF-SCOPE（B 口径说实话），"证明级吞吐认证"(A) = 研究级 future。详见 §8。
- **供电（predicate #6）= 已 sound 做完、不是缺口**（⚠ Opus 独有；反直觉，易误判为 future 故留档）：master 几何约束求解时强制 + terminal 端独立见证复验（`exact_campaign.py:1131-1157`）——**比 routing/binding 还强**。
- **谓词分级（⚠ Opus 独有的完整分级）**：I2 master 域编码 = PARTIAL；I3 剪枝不过升级 = PARTIAL（跟 I1 同根）；I4/I5/I6 = SOUND。

**会议裁决（plan-restructure-council，⚠ Opus 独有）**：**不全盘重构骨架**（连主张重构的都收窄成文档化）。真动作 = 写权威「Certified Theorem Scope」（命题 P：把 6 predicate[ghost 空/不重/placement/port-binding/routing/power-coverage，**吞吐不在内**]提升进 `PROJECT_LOCK §1` 宪法层 + 显式 OUT-OF-SCOPE 清单）+ Soundness Gap Roadmap（每 gap 三态：原则已在 lock / 实现存在未测 / 实现缺失，**不能"文档化=已闭"**）。
- ⚠ **命题 P 落地 commit**：Codex 版给 `3f9ca45 docs(p1.2): land 命题 P`；Opus 版未给此 commit。
- **诚实 certified 口径（记住）**：证 **布局 + 连通(有路) + 供电覆盖 + 资源数量够；不证 吞吐 / 容量**。（Codex 表述：placement / binding / routing connectivity / power coverage 为 gating predicates；`PROJECT_LOCK.md:53-63` 红线写死 routing `FEASIBLE != 吞吐可行`，routing 语义 = "离散有向连通"。）

**flow 保持 diagnostic-only 的规格佐证（⚠ Codex 独有）**：`specs/08_topological_flow_subproblem.md:10-24` 把旧文档里"flow 失败后不进入 routing""自动生成 Farkas Benders cut"列为**历史文本、非当前行为**；`:57-59` 明确任何把 flow `INFEASIBLE` 当 exact-safe cut 都会越过认证边界。

### 2.3 C4/C5 cut 割族 latent false-INFEASIBLE 雷 —— `p1-2-c4-c5-2026-06-21-3-latent-false-infeasible-f7-f8-f3-cuts-live-canonical-p1-3b-tcb`

> ⚠ **本节 Opus 独有**——Codex 版未列 F7/F8/F3 割族（但 Codex 在 §8 死路里提到 F4 cell-flow 与 D2 Path17，见下）。

shadow 分歧扫雷发现 3 条 tier-1 latent 雷（全在 `src/cuts`、全 latent：`step_8_apply_to_master=NotImplementedError` + 生成器 env 默认关 + `benders_loop` 从不调用）：

- **F7** `power_cover.py:45` 欧氏圆 vs 活路径 12×12 方形覆盖；
- **F8** `power_network.py:69` 欧氏跳线可达；
- **F3** `candidate_placements.py:58-63` `DIRECTION_OFFSETS` 把 N/S 端口朝向算反。

都是方向性 false-INFEASIBLE（过度割、可破坏 max_lex 最优性）。**零 live 结论**：活认证路径 7 个几何量内部全自洽、零 live 认证分歧；这 3 条都 latent、不喂认证。**修法（owner 方向）= 收敛到单一 canonical 原语**：把覆盖形状/端口朝向/度量上提为 `src/rules/` 权威纯原语，活路径 + cut 家族都 import 复用，分歧结构上不可能发生；cut 家族接认证前（P1.3）必须先 wire 到共享原语 + 红测。**设计推后到 P1.3，至今未做。**

---

## 3. 三轮独立外审 + 「信任洋葱」认识（2026-06-21）—— `p1-2-review-converged-tcb-start-p1-3`（docs commit `53396e1`）

三轮 GPT Pro 外审（每轮 Codex→Claude 对源核，blind A-G），**每轮都 BLOCK**：

- **R1 = WS witness-split**（发布 π* 未复验 binding/routing）——见 §3.1，本阶段最重的发现。
- **R2 = OPEN-GATE**（公开发布面不读 reopen/open → "诚实 open"是运营纪律非机器闸）+ TOCTOU（load→hash 窗口）+ PHASE-GATE-STRUCTURE（手动闸不绑 fixed-witness）+ 逮到主控自己的 LOCK-CHECKER-DRIFT。
- **R3 = PYC-EXEC-DIGEST**（两家独立 PoC）：`compute_certified_exact_source_digest`（`exact_campaign.py:340-378`）只哈希 `.py`，隔离 replay 执行的 `.pyc` 未绑 → 时间戳合法的恶意 `.pyc` 在 `.py`/digest 不变时伪造 replay 权威 = 验证器自身执行身份未绑。又逮到主控 §C drift 残留。

**关键认识（回答 owner "不管怎么审都能审出问题"）**：对抗式外审**永远能再剥一层信任洋葱**：witness → 发布闸/artifact 载入 → 验证器执行字节码 → 解释器/OS/硬件。**"审到零发现"不可能、不是收敛判据。** 真收敛 = ① 显式划+冻 TCB 线（声明信任什么）② 修线以上全部 ③ 之后新发现要么落已声明 TCB 线下、要么是 done 判据实例 = 可停审。

**owner 决定（2026-06-21）**：三轮够了，停审、进修（后命名 P1.2-FIX）。done 判据扩展为：发布谓词在确切字节上独立复验 + 机器发布闸 + 红测 + 验证器从不可变 capsule 执行 + 命名 TCB 声明。

### 3.1 WS witness-split —— `p1-2-witness-split-block-2026-06-21`（本阶段最重要发现，⚠ 细节主要来自 Opus）

**漏洞（F1，CONFIRMED-REAL BLOCK）**：认证面发布 `(R*, π*)`。隔离 replay 只按 `ghost_w/ghost_h` 自由重解（证"该尺寸存在某可行布局"，`candidate_proof_replay.py:889-904`）；终端 validator 强制 published==stored 并几何复验（几何/不重叠/供电/ghost 空/空矩形最优），**唯独 binding（端口精确计数）+ routing（连通）没在发布 witness 上重跑** → `active_ports=[]`/boundary_bad pose（单独 binding=INFEASIBLE）能发成公开 CERTIFIED。

**reachable = tamper-only（关键 nuance）**：正常 in-process 解只在 binding+routing 都过后才返 CERTIFIED；但 sink+validator 存在的前提就是 stored witness 不可信，故 tamper/drift（resume/迁移/并发写）可达 → 真 soundness 缺陷。强于 I1（I1 只发次优 CERTIFIED，本条直接 mint 假 CERTIFIED）。

**试过并撤回的死路（重要教训）**：试过 **rebind-to-replay stopgap**（终端发布改用 replay 已证 witness）。子代理回环报 clean（**但只跑了 staged preflight**）。**主控自己跑全量 preflight 逮到它破坏合法认证交付**——12 个测试含 happy-path 挂，`terminal_frontier_candidate_status_digest_mismatch`。根因：终端证据 `candidate_status_digest`（`certified_frontier.py:505-524`）内嵌 witness 的 `solution_digest`；rebind 让该摘要依赖 re-solve 的 replay witness，build 端与 verify 端对 witness 表示不一致 → 摘要不匹配 → 拒掉合法交付。**这就是 digest-equality 误拒问题换了地方又冒出来。**

**owner 决定 A（否掉 rebind）**：撤掉 rebind（`git checkout HEAD` 撤回 9 文件），诚实 open + proper 修进 P1.2-FIX。理由：风险本就 tamper-only + 现在不发 CERTIFIED，诚实 open 已止血，不在认证核心铺脆补丁。
**durable 修法（→ FIX-1）**：fixed-witness verifier——**保留 stored witness 不变**（摘要稳），对发布 π* **原地**重跑 binding+routing（钉住 pose），不可行升 UNPROVEN。

---

## 4. P1.2-FIX 线（2026-06-22 / 23）：五个 FIX + capsule 根治

> ⚠ **本节主体来自 Opus**——Codex 版把这段压缩，仅覆盖第 4 轮推翻 FIX-1/3、capsule `f492690`、以及 FIX-4+PYC 误判被推翻；未逐一展开 FIX-1/2/3/5 与 PYC 的独立细节。

**时间线（⚠ 两版 git 链不同，均保留）**：
- Opus 链（旧→新）：`a5ff5aa`(④b) → `53396e1`(R3 doc) → `228f266`(FIX-3) → `f492690`(capsule 根治=FIX-1/3+FIX-5) → `44089a3`(FIX-4) → `88b2d32`(PYC-EXEC-DIGEST) → `21a9dda`(二次外审 HEAD) → `ddb3b5a`(PR1 supervisor 地基)。
- Codex 历史链另引：`3f9ca45`(命题 P)、`f4f6336`（Codex 列出但未说明其内容）、`53396e1`、`88b2d32`。

> **追溯性提示（Opus）**：FIX-2 记为 commit `de68515`（"ahead origin/main 12、未推"），**在当前 main 线性历史里查不到**——很可能被后续 rebase/squash 吸收。⚠ Codex 版完全未提 `de68515` / FIX-2。你在 `git log` 里看不到它别慌，功能已并进后续。

### FIX-1 设计 —— `p1-2-fix-1-design-fixed-witness-verifier`
结论：**可从现成零件搭，不是从零造能力**。binding 本就吃具体 placement（`PortBindingModel(placement_solution,...)` `binding_subproblem.py:356`），routing 本就支持固定占格（`RoutingPlacementCore.from_occupied_cells`）。要新建的只是"对确切 stored witness 接起来的终端 verifier"。**铁律（rebind 翻车教训）**：对现有 `record["solution"]`+`solution_digest` **验证、绝不改写**。

### FIX-2 OPEN-GATE 机器发布闸 —— `p1-2-fix-2-open-gate-landed-20260623`（`de68515`）
`certified_surface.evaluate_certified_delivery_surface` 在唯一 `publishable=True` 出口前调 `resolve_p1_2_publish_open_gate`，**永远** fail-closed 读 `data/review_gates/phase_1_2_spike_close.json`（仅 status=closed_manual_owner_decision + next_phase_entry.allowed + p1_3b_entry_allowed 才放行；缺失/畸形/symlink/dup-key/NaN/异常 → publishable=false）。
**跨模型审逮到 2 个单模型自审都漏的真 BLOCK**：① **override-bypass = WS 同族**：public verifier 曾暴露 `publish_open_gate_path` 覆盖参数 → 调用方能把权威 verifier 指向伪造的 closed gate 绕闸。**教训：给 fail-closed soundness 闸加"测试注入路径参数"暴露在 public surface = 把权威源变成可喂的 = 正是 witness-split 同族。** 修 = 删覆盖参数，resolver 结构性绑定权威路径。② module 共享 fixture 引入 symlink 顺序依赖 flaky。

### FIX-3 phase-gate 绑 fixed-witness —— `p1-2-fix-3-phase-gate-fixed-witness-228f266`（`228f266`，**后被 round-4 推翻**）
让 phase-gate close 条件从"通用钝锚（if next_allowed is not False）"换成 witness-bound：无条件 AST 断言 publish 链真调用 verifier。**关键设计**：止血（next_allowed 必须 False）和 witness 绑定拆成两条独立条件，witness 绑定无条件强制。当时 Codex 跨模型审判 CLEAN，但留了两条 CONCERN（`_calls_function` 有 shadow/别名局限）——**这两条 CONCERN 就是下一轮外审推翻它的入口**。

### 第 4 轮外审推翻 FIX-1/3（2026-06-23）—— `4-fix-1-3-reopen-capsule`
3 个独立 GPT Pro reviewer 裁：FIX-2 真闭；**FIX-1 未闭（2 BLOCK）**；**FIX-3 未闭（3 BLOCK）**。
- FIX-1：F3 connector own-body（same-owner collision 仍 CERTIFIED）；**可伪造 verdict（LIVE）**——`TerminalFixedWitnessVerdict._fresh_run_marker` 是公开构造器默认值，任意同进程代码 `TerminalFixedWitnessVerdict(publishable=True,…)` 自带 marker 过校验、不跑 binding/routing 就 mint CERTIFIED。**WS 信任只下移了一层。**
- FIX-3：stub 即过（只验文件存在+函数名）；`_calls_function` shadow（同名 local/nested def/param 骗过）；mutable-anchor 自重封（改 3 个 review anchor 就跳过 static floor，攻击者改 verifier + 同步 manifest hash 自盖章）。
**根因（3 reviewer 独立剥到同一层）**：信任机制本身可伪造（in-process verdict 对象 / name-based AST guard / self-resealable hash）。
**owner 拍板 → 上 capsule 根治**：验证器从不可变 hash-pin 隔离边界执行（仿 candidate sink-replay 的 `python -I` 子进程）+ verdict nonce 不可同进程伪造 + unknown-anchor/self-reseal fail-closed + guard 语义绑定（验执行结果而非函数名）。**逐个 patch 会再下移一层**（reviewer 明说）——这是"信任洋葱"第一次逼出架构级动作。

### capsule 根治落地 —— `p1-2-capsule-f492690-fix-1-3-fix-5`（`f492690`）
⚠ Codex 给 git stat「20 files, +3888/-193」（"大改"），Opus 未给 stat。commit 标题（Codex）：`feat(p1.2): capsule 根治闭 FIX-1/FIX-3 外审 BLOCK + FIX-5 TOCTOU`。

新 `src/search/terminal_fixed_witness_capsule.py`：fixed-witness 在隔离 `python -I` 子进程跑、nonce-bound response、父进程只信校验过的 response 不信 in-process verdict 对象；删 `_fresh_run_marker` 权威默认。含 read-once snapshot、v99 static floor、FIX-5 TOCTOU 修复。FIX-3：v99 static floor 永远跑、unknown anchor fail-closed、guard 验执行行为。**残留（非 live）**：可达性扫描器仍漏认 `assert False`/`range(0)`/`match` 无 catch-all 等"假不可达"——被 v99 floor hash 钉 + STRUCTURAL_GATE 机器闸兜死，Codex 端到端实测不可 data-only 利用（要利用必须改 checker 源码=git/人审 TCB 边界）。**Codex 注释诚实声明"扫描器是冗余第二层、floor 才是主防线"。**
- **canonical binding mock 坑**（cc_memory `capsule-opus-canonical-binding-mock`，⚠ Opus 索引提及）。

### FIX-4 I1 独立复验 —— `fix-4-fix-5-i1-toctou`（设计）+ `p1-2-fix-4-landed-44089a3`（`44089a3`）
**关键洞见**：FIX-1 验存在性（∃ 见证，廉价独立）；FIX-4 验**不存在性**（∀=INFEASIBLE，数学上只能靠另一完整 solver 也判 INFEASIBLE，**不能靠找见证廉价收口**）→ 第二复验器 = 独立构造异构可行性子问题求解。实现：新 `src/search/independent_infeasibility_reverifier.py`，binding-INFEASIBLE 由独立异构 CP-SAT 复验（自建 `PortBindingModel` + 全新 CpSolver + PORTFOLIO_SEARCH/seed 8675309/workers 2，**绝不读 self.master/_solver in-flight 缓存**）。真值表：独立确认 INFEASIBLE→落 cut；FEASIBLE 分歧/TIMEOUT/异常→UNKNOWN（绝不 mint INFEASIBLE）。⚠ Codex 版把 I1 复验器只登记为「实现项、方向」，未展开档 A/B/C 与 mock 坑。
- **被否/权衡**：routing 穷尽命题更难独立复验 → phase-1 只在独立 binding 也 INFEASIBLE 时放行、否则保守升 UNKNOWN（`routing_exhaustion_phase1_conservative_unknown`）。**sound 优先、伤收敛 = documented tradeoff，phase-2 才补 completeness。** 档 A（异构 CP-SAT）/ 档 B（独立编码判据）/ 档 C（二阶段 minimal-core）都登记；落地是档 A + phase-1 保守。
- **mock 坑（全量 preflight 逮的 3 回归）**：复验器直接 `from src.models.binding_subproblem import PortBindingModel` → 测试 `monkeypatch benders_loop_module.PortBindingModel=Fake` 碰不到复验器 → 复验器重建真 toy 模型不确认 → fail-closed。= **FIX-4 按设计工作（不信伪造 INFEASIBLE），非 bug**。修法：mock 复验入口而非 mock PortBindingModel。
- **锁文件登记（Codex）**：该项已登记为「实现」但明确「不等于 P1.2 closed」（`PROJECT_LOCK.md:122-128`）。

### PYC-EXEC-DIGEST —— `p1-2-pyc-exec-digest-landed-88b2d32`（`88b2d32`，闭 R3 窄洞）
`python -I` 只隔离 env、不阻止读 `__pycache__` 的 `.pyc`。修：隔离启动 argv 加 `-B -X pycache_prefix=<per-run mkdtemp 空目录>`（finally rmtree）→ 执行字节码 ⟸ 已哈希 `.py` 源。**可复用坑**：`-I` 隐含 `-E` 忽略所有 `PYTHON*` env → 必须用 CLI `-X pycache_prefix=`、不能用环境变量。
**⚠ 本条原写"FIX-4+PYC=收敛点达成"是误判**（见下 §5.2）。

---

## 5. capsule 架构为何被外审推翻 → owner 拍 supervisor L0/L1 重做

这是本维度**核心决策②**。

### 5.1 第二次外审（`21a9dda` 三审，2026-06-23）—— `21a9dda-argv0-live-12`
> ⚠ **本节 Opus 独有**——Codex 版把 argv0 等直接归进第 5 轮 capsule 拆解的 tamper cluster，未单列 `21a9dda` 这次带 5 条去重的二次外审。两版可能在描述部分重叠的审查轮次。

审含全部 FIX+capsule+PYC 的 HEAD，3 独立 reviewer 各带 PoC，判定一致：**未收敛、仍有 LIVE BLOCK**。去重 5 条：TOCTOU 执行源≠事后 digest；`-I` 缺 `-S` → system-site `.pth`/`sitecustomize` 先于 verifier 执行；v99 floor 非执行闭包（`port_binding.py` 改 binding 10→0、`operation_profiles.py` 端口槽归零，改活语义而 checker 绿；`certified_artifact_contract.py` 只存在性无内容 digest）；**`sys.argv[0]` 伪造 checker 身份跳过 close-kernel（`certified_artifact_contract.py:115`）**；phase-gate AST guard 被最终同名重绑定骗过。
**关键升级**：argv0 从 round-5 的 "tamper-only" 升为 **LIVE tamper-assisted**——只需 gate 数据写权 + 设 argv0、不改源，直接否定"data-only 不能自关闸"。教训："supervisor 设计原则性覆盖不能替代显式登记；argv0 这类 BLOCK 必须在设计中逐项钉住"→ 补进设计 §12 一期必闭（doc commit `7d3c800`）。

### 5.2 第 5 轮外审推翻收敛 —— `p1-2-round5-external-review-capsule-not-closed`（审 `a34fc07` capsule 包）
2 独立 reviewer 各带 PoC，判 **capsule 根治 = 未闭、全局未收敛，⚠（Opus 称 ~11 BLOCK；Codex 未给数量）**，**直接推翻主控"FIX-4+PYC=收敛点"的误判**。
- **主控误判根因（记住这条教训）**：把窄洞闭合 + Opus 子代理审 A-G 全 CLEAN 误当作架构收敛。但 **Opus/子代理审的是"这俩补丁闭没闭它们各自的小洞"，没去打 capsule 架构的根**。**收敛判断必须靠外审打架构、不是内审打补丁；子代理"补丁自洽" ≠ "架构 sound"。**
- **核心 LIVE BLOCK（两 reviewer 各自独立 PoC，同进程、无需改仓库）**：capsule + candidate_proof_replay 的应答**无来源认证**——父进程生成 nonce、连同期望 hash/source digest/authority state 全交给模块全局 `_invoke_isolated_capsule`/`_invoke_isolated_replay`，然后只校验应答字段自洽。**同进程 monkeypatch 这俩函数**（伪造体拿 nonce 原样回显 + 拼 FEASIBLE/INFEASIBLE）→ `publishable=True/CERTIFIED`（capsule）或把真可行候选投影成 INFEASIBLE（replay）→ **不启动子进程、不跑 binding/routing**。nonce 只防重放、不证来源 → **capsule 只是把可伪造性从"造 verdict 对象"平移到"造 response mapping"，根没动。** reviewer 点出：这正是 manifest 自称防的"module binding/monkeypatch 不授予 authority"——**声称防住、实际没防**。
- **Codex 补充的 tamper cluster**：除上述来源认证缺失外，还包括 `sys.argv[0]`、`sys.executable`、local package shadow、source exec before digest TOCTOU、root split、sink inventory 不闭；并记录 capsule 当时有 **parent parameters override parsed authority bytes** 的问题。
- **修方向（两 reviewer 头号必修一致）**：**把公开裁决移出不可信 producer 进程 → 最小可信 supervisor**：supervisor 自己生成 nonce、起子进程、读权威字节、直接发布；child read-once campaign 权威字节（禁父进程覆盖）；import 项目代码前先验执行完整性；v99 floor 机器推导"全部结构目标 + authority-transitive import closure"；强制 checked-root==executed-root。**= 信任洋葱下一层、实打实架构重做。**

### 5.3 supervisor 设计评审 team —— `p1-2-supervisor-l0-l1-design-meeting-20260623`（详设计 `docs/项目说明/p1_2_supervisor_detailed_design.md`）
redteam[codex]/soundness[opus]/tcb-arch[opus]/feasibility[codex] ~6 轮对抗，**推翻主控的单 supervisor 草案 → L0/L1 两层**。
- **为什么单 supervisor 被否**：单 supervisor 调 `evaluate_certified_delivery_surface` → 把 CP-SAT 求解核（certified_surface→exact_campaign→master_model）拖进 TCB，"最小 TCB"与"调 evaluate"自相矛盾。
- **收敛设计**：
  - **四类 TCB 诚实性框架**（soul）：TCB 项必落 ①架构事实（机器可验）②承认人审根 ③真信任非验证 ④verified-not-trusted。判据 = "能算命名 TCB 当且仅当架构上不可达伪造，否则是穿 TCB 外衣的 LIVE 洞"。（主控此前加的"父进程只 relay=TCB""guard 非判决权威"两条 PROJECT_LOCK claim 被此判据+外审 PoC 证伪，一期必收回。）
  - **L0 micro-verifier-core** = 真 TCB{L0 源+固定解释器+stdlib+OS}，无 ortools 无项目 `.py` 零 domain schema，只字节搬运+编排+二值裁决。⚠ **行数估计两版不同：Opus 称 ~300-350 行；Codex 称 约 300-400 行（最多 `strict_json` 单叶 import）。**
  - **L1 orchestrator** = verified-not-trusted / **child** = semantic TCB（verifier+闭包字节+ortools.so，负责 domain semantics，但由 L0 控制输入/字节/调用边界）。
  - **受控 import loader（技术核心）**：L0 spawn child 喂 meta-path importer，child 只从 L0 已核字节快照 import（经 fd）、不走 sys.path → 一个机制同闭 BLOCK-6 / 覆盖完整性 / package-shadow / root-split。两段式自举（阶段①纯 stdlib 核 floor 零项目 import → ②装 loader 后才 import）堵 B7。
  - **铁律**：L0 stdlib 重写项目码必须逐项等价、禁借"L0 要小"弱化（gate 5 道 / JSON 三类 dup-key+NaN+1e400 全保）；`inspect.stack`/env-token 是虚假保护，写闸删掉靠架构隔离（L1 物理无认证写 fd + OS 权限）。**L0 自身完整性 = 带外（git+signing+CI+人审）；诚实写"鸡生蛋根不可消除、只能缩小"。**
  - **工作量估计**：850-1060 行、55-75 测试、2-4 周、2 PR（PR1 / PR2）。
- **owner 之前选过 (b) 顶层 spawn，但 team 四方技术一致倾向 (a) 分离 certify 命令**（L0 跑完即退纯函数=最小核）。这条选择当时"待 owner 拍"。
- ⚠ **被否替代（Codex 补充）**：信 producer 写出的 `CERTIFIED` 或 function identity / closure / registry / current-process freshness——全否，与 `PROJECT_LOCK.md:275` 一致。
- **RESUME 登记的后续要求（Codex，RESUME `:60-66`）**：L0/L1 要真隔离进程、controlled loader、B2 候选域 L0 独立枚举、B3/BLOCK-D、B4 `-I -S -B`、certify 入口、argv0/contract digest 等。

---

## 6. PR1：supervisor 地基 + 发布面 soundness（核心决策①）

### 6.1 PR1 supervisor 地基落地 —— `pr1-supervisor-mint-preflight`（`ddb3b5a`，26 文件 +1818/-343）
两块：
- **mint 收敛**：`exact_campaign.supervisor_seal` 成唯一 durable CERTIFIED mint（模块私有 token，普通 `mark_campaign_stopped(CERTIFIED)` raise；⚠ Codex 给当前源码约束点 `src/search/exact_campaign.py:3566-3610`）+ CANDIDATE_PROPOSED 非权威态 + resume 语义 + outer_search 剥发布权。
- **BLOCK-D producer 侧 + marker + 复验迁移**：capsule `_authority_state_for_capsule` 收紧（优先落盘字节、拒 caller override、不一致 fail-closed）+ proposal_ready marker（producer 写 checkpoint_sha256，PR2 L0 自重算不信它）+ producer 终局只落 CANDIDATE_PROPOSED **不调 supervisor_seal**（发布权彻底剥离，PR2 certify 入口才 mint；⚠ Codex 给当前源码 `_build_certified_result` 写 CANDIDATE_PROPOSED、`_commit_terminal_full_frontier_certified_result` 写 proposal marker，`src/search/outer_search.py:855-954`）+ 复验迁移（supervisor_seal mint 前调 `build_sink_verified_terminal_frontier_evidence` sink-replay 复验 + fail-closed）。
- **教训**：第二块独立 Codex 审一路 CLEAN，但两个真问题全是主控全量 preflight 逮的（① 搬 mint 时把 `build_sink_verified` 丢了；② 3 算法测试 mock 没跟上新 sink 路径）。**审 CLEAN ≠ 全量绿。**

### 6.2 PR1.1c 外审：7 类外围发布面 BLOCK —— `pr1-1c-external-review-7-blocks-unclosed`（审 `072265a`）
> ⚠ **本小节的原始 7 类 BLOCK 主要来自 Opus**；Codex 版把它们直接以去重后的 A/B/C/D 组呈现（见 §6.3），未单列 raw 7。也因此 ⚠ Codex 的 git 证据列表里没有 `072265a`。

先有插曲：`pr1-test-debt-cleanup-20260626`（codex 三连提交 `d3f9009→2904a81→072265a` 把测试跟上代码，3316 passed）。**但外审明确：测试债收口（3316 passed）≠ PR1 闭合。** 核心发布闸门守住，但**外围发布面 7 类 BLOCK 原封未处理**（真 soundness 漏洞、不是测试问题，PR1 仍 REOPEN）：
1. manifest builder caller-Mapping TOCTOU（时变 dict 子类回放真值、检查后切回伪造，写出 forged CERTIFIED manifest）；
2. **可 import 的无门禁 canonical writer**（`_write_certified_final_solution_and_blueprint_unchecked` + serializer + blueprint_exporter，普通同进程 caller 不过 seal/gate 直写 canonical 为 CERTIFIED）；
3. manifest 写后验、拒绝不回滚（gate 关时只抛异常、留下公开 CERTIFIED manifest）；
4. 公共消费者留 stale/跨代输出（viewer 三件套/`--vis` 混代 PNG/industrial export 六文件无 rollback）；
5. proof checker + 默认测试集假绿（只 token/AST 锚定、不证 reachability/单代事务/Mapping 单读；默认只跑 4 个测试文件）；
6. package 脚本不绑 HEAD/commit（可造"旧树内容+当前 commit 名+自测全绿"的假绿包）；
7. 归档混入 prompt 类与旧 review packet。

### 6.3 A/B/C/D 四组修复 —— `pr1-publication-blocks-abc-fixed` + 现状 `p1-2-current-publication-surface-status-20260626`
把三轮（pr1-1/2/3，opus+codex 跨模型对抗）+ 四轮（pr1-4，全 codex）审查去重成 **11 组未闭洞总表 A/B/C/D**，四组全修、各终审全量 preflight 过：
- **A = false-CERTIFIED 核心**：删模块级无门禁 canonical writer + `save()` `type is not dict` 命门 + snapshot + readback + manifest builder 入口 snapshot + disk rebind + checker call-reachability 锁定。（同进程 import/raw write 留 PR2。）
- **B = 发布非事务/stale**：`publish_verified` except 全包 rollback；serve/--vis/industrial 事务化；single-base viewer fail-closed。
- **C = proposal/seal/resume**：`stable_terminal_fixed_witness_verdict` 严格 whitelist + 源头剥 fresh_run_token；`load_or_create` isolated replay on disk bytes + forged demote + durable writeback + clear 三件套。
- **D = BLOCK 5/6/7**：checker 自包含 AST + 默认测试集；package 绑 git HEAD/tree/blob + dirty 诚实；归档路径/内容过滤。
- **残留 2 GAP（⚠ Opus 独有；后闭）**：GAP-1 package 无标记 --skip-tests + receipt 不内嵌 archive；GAP-2 selftest 没隔离 `PYTEST_DISABLE_PLUGIN_AUTOLOAD`。codex 4 轮跨模型对抗逼至收敛后闭合。**唯一不可根除项 = 内嵌 receipt 是自报数据，真正证明靠 reviewer 重跑（by design，包提供一条重验命令）。**
- **GPT 文本审计落地（⚠ Opus 独有）**：GPT Pro 非代码文本 soundness 审计（101 文本+memory.db）回传，落地 91 文档 + 回退 8 个 v99-sealed 注释保封印 + 修 4 个 test_regression 文档不变量。

### 6.4 三轮外审并集 soundness 落地（= 任务点①核心）—— `pr1-soundness-b085a75-ci`（`1817c71` 代码 / `b085a75` 记忆 / `0bc36db` CI 前置）
⚠ Codex 给 `1817c71` git stat「13 files, +1124/-203」，commit 标题 `fix(p1.2): PR1 发布链 soundness 并集落地(三轮外审 B/D/A/C/B2/E)`；Opus 未给 stat。

GPT Pro 对 `0bc36db` 做**三轮独立外审 + 三份补丁（互冲不能叠加）**。走 codex-claude-clean-workflow：**codex 合成一份并集补丁 → opus 在环审 → 主控读源终审 + 全量 preflight + CI**。并集 = **B/D/A/C/B2/E** 六条，都对源码坐实：

- **B（BLOCK，三轮一致）— publisher 改真事务**：staged 暂存 + manifest-last `os.replace` 提交 + 已有 publishable 面 backup/restore（**不预删有效面**）+ commit 前重读 checkpoint（TOCTOU）+ 二次 publish-open gate + 单 try/except rollback re-raise + post-commit verify。delivery_manifest 绑 staged bytes、logical path 仍 canonical。⚠ Codex 给当前源码结构点 `src/search/certified_surface.py:607-655`, `:656-755`, `:758-877`；锁文件佐证 public publisher 唯一、失败写必须清 partial（`PROJECT_LOCK.md:259-263`）。
  - 被修的旧行为：非事务发布，可能留下 stale/半发布的公开 CERTIFIED 面。
- **D（BLOCK，三轮一致，最深）— checker 曾给 bug 背书**：`_check_publisher_transaction_shape` 原来**强制要求"正好 3 次直写 canonical"**——**= 把 B 的危险非事务形状固化成了证明目标，checker 在给 bug 背书**。重写成 **AST staged-事务检查**（禁直写 / 强制 stage<commit<verify / gate dominate / rollback restore+clear+reraise / staged 绑定）。strong-status allowlist 认 `os.replace` artifact 写 + stale-entry 检测。⚠ Codex 给当前 checker 源码点 `scripts/check_p1_2_proof_obligations.py:1382-1526`。
  - **本阶段最值得记住的元教训**：一个"证明 checker"可以在无人察觉时把当前的错误实现当成"正确形状"来强制，于是任何修正实现的 PR 都会被 checker 判红——checker 本身成了 soundness 漏洞的守卫。
- **A — save() 谓词收窄**：新增 `_has_unsupervised_certified_checkpoint_claim`（⚠ Codex 给 `src/search/exact_campaign.py:2564-2578`），**只挡 `== "CERTIFIED"` 三处**（`final_status` / `final_result.search_status` / `last_stop_reason.status`）。**关键不对称**：**不**用 `has_certified_export_surface`（那个含 `PROOF_BEARING_TERMINAL_STATUSES = CERTIFIED+INFEASIBLE`）——CERTIFIED 必须 seal-only，INFEASIBLE 是合法经 save/mark_campaign_stopped 落盘、保护在 resume-replay 层、不靠禁 save。
  - **被否/返工的替代**：原 A 修复错把两者混用 `has_certified_export_surface` → **误伤 INFEASIBLE = v101 回归**（被全量终审逮到）。
- **C — 裸 CANDIDATE_PROPOSED resume**：验 proposal/marker 权威（run_id/instance_id/sha），不匹配 → demote+writeback+unlink+清面。⚠ Codex 给当前源码点 `CANDIDATE_PROPOSED_STATUS` `src/search/exact_campaign.py:63-72`、proposal authority/demotion `:2130-2172`、resume sanitization `:2988-3072`；锁文件佐证 resume sanitization 必须 durable-before-public-reuse（`PROJECT_LOCK.md:273-274`）。
- **B2 — nonpublishable manifest export** 前清 stale final/blueprint。
- **E — package_review_snapshot** `git status -z` rename/copy 双路径解析。

**freeze ritual**：重封 5 核心文件 `source_sha256` + checker self-pin floor + allowlist；新增 9 负向测试。
**全量 preflight 教训复证（任务点①要求写的"逮到 in-loop 漏项"）**：in-loop 轻量检查（只跑 targeted 负向测试）漏了：① allowlist json 写成 CRLF（违 LF 政策，hash-pin 要连带重封）；② save() 收紧的 v101 INFEASIBLE 回归。都被主控 `--full` 逮到（FULL 曾 BLOCK 2 项）。⚠ Codex 另记「另有两个失败后来归为 pre-existing order flakes」。修复后主控权威 `--full` + `--slow` 双绿，committed `1817c71`，push origin/main，CI 两工作流 success（project-foundation 含 slow-soundness-gate 14m / industrial-planner-checked-artifacts）。RESUME `:86` 记录当时 HEAD=`b085a75`、已 push、CI 两工作流绿。

> **⚠ 追溯性诚实说明（两版组织方式的关键分歧，供终审裁定，不擅取舍）**：
> - **Opus 版**认为记录里存在**两波高度重叠的 PR1 发布面外审**——A/B/C/D（对 `072265a` 工作树、当时记为未提交/REOPEN，§6.3）与三轮并集 B/D/A/C/B2/E（对 `0bc36db`、落地为 `1817c71`+CI 绿，§6.4）；两者在"事务化 publisher / save() 谓词 / checker AST"上互相印证、部分重复推导。
> - **Codex 版**把它描述成**一条线**：`0bc36db` 附近的 7 类 BLOCK → 去重成 A/B/C/D 组 → 最终采用覆盖 B/D/A/C/B2/E 的并集补丁 → `1817c71`。
> - 无论哪种框架，committed + CI-green 的终点都是 `1817c71` / `b085a75`。若你重建精确的 commit↔fix 映射，**以 git 为准、别全信记忆的行号**。

### 6.5 PR1 后的诚实状态 —— `p1-2-supervisor-production-entry-gap-20260626` + CHANGELOG（2026-06-26）
> ⚠ **cc_memory id 分歧**：Opus 引 `p1-2-supervisor-production-entry-gap-20260626`（+ `p1-2-current-publication-surface-status-20260626`）；Codex 引 `fact-p1-2-supervisor-operability-20260626`。可能是同一事实的不同条目/别名，也可能是两条独立条目——**接手时两个 id 都 `read --body` 核一遍**。

**这是 PR1 落地后 supervisor 链的真实边界，务必读懂；2026-07-04 的 #7 落地只更新入口存在性，不更新 release 红线**：
- 工作树已实现 `ExactCampaign.supervisor_seal()`，producer 终态降为 `CANDIDATE_PROPOSED`；
- 生产入口现为 `scripts/run_supervisor_seal.py`：独立命令，从 proposal-ready marker 驱动 `supervisor_seal()`；`main.py` 正常链路**止于 proposal**，不能被描述为已 supervisor-sealed 或已公开 CERTIFIED。这补上的是**操作链缺口**，不等于 release closure。（Codex 佐证：`PROJECT_LOCK.md:130-136`, `:141-154`。）
- CHANGELOG 顶部（⚠ Codex 给 `CHANGELOG.md:9-11`；另引 `:126-131`）的 2026-06-26 历史快照确认：producer commits `CANDIDATE_PROPOSED`；`supervisor_seal()` sole durable terminal CERTIFIED mint；`publish_verified_certified_delivery_surface()` sole public publisher；当时 `main.py` 和 launchers 不 invoke `supervisor_seal()`。2026-07-04 更新：`scripts/run_supervisor_seal.py` 提供生产入口；方法、入口与 safeguard 存在仍**不转换为 P1.2 closure claim**。
- **P1.2 仍 blocked**：owner gate = `blocked_manual_review_count`（仓库外人工 clean-review 计数），fail-closed（Codex：`PROJECT_LOCK.md:130-146`）。PR2 的更小/read-once/受控 loader TCB 未完成。**局部修复不得升级为 P1.2 CERTIFIED。**

---

## 7. 算法核心 soundness 担忧（核心决策③：close-kernel 绿灯掩盖算法层）

> ⚠ **本节结构化担忧主要来自 Opus**；Codex 版在其 §1 也点了 I1 缺口与 flow diagnostic-only，但没有把"close-kernel 绿灯掩盖算法层"单列成贯穿性风险。这不是某个 commit，而是一个**贯穿全程的结构性担忧，你必须内化**：

- **flow model 只诊断，永不证明**（当前源码已核实）：`src/models/flow_subproblem.py:4-9` docstring 明写——certified_exact mode 下本模块**只允许作 diagnostic，不得单独产生正式剪枝证书**；返回的 INFEASIBLE/UNKNOWN 只能被上层按模式解释，exact 路径不得把这里的失败直接写成 exact-safe cut。⚠ Opus 引 `PROJECT_LOCK.md §B-1（行 102-106）`锁死唯一带 demand 量纲的 flow 子问题为 **diagnostic-only、绝不 gate**（`:149 CreateSolver("GLOP")` = 连续 LP 松弛）+ `test_exact_contract.py:3532 test_exact_mode_uses_flow_only_as_diagnostic`（monkeypatch flow→INFEASIBLE 仍断言 CERTIFIED）+ `PROJECT_LOCK.md:454` 把"Treating … diagnostic flow checks as certified proof"列 Forbidden Change；⚠ Codex 引 `flow_subproblem.py:119-149` + `PROJECT_LOCK.md:100-116`, `:145-150`, `:53-63`。
- **"close-kernel 绿灯掩盖算法层"的风险**（`close-kernel-necessity-verdict-20260619` 问题 2.2，最危险的一条）：`V99 CLOSED` 绿灯会把注意力从**算法层**（V81–V98 十八轮反复出血：半域 / forged cut / 几何不可能矩形发 CERTIFIED）引开，**给没审的地方发及格证**。这是 owner 最初"想审算法却被认证层带走"那个病的系统化固化。裁决明令：**P1.2 algorithmic soundness 单独标 open，green anchor 绝不替未受审算法层背书。**
- **算法层真实 gap 的定位与处置**（`p1-2-c3-kernel-audit-3source-20260620` + `p1-2-closure-path-verdict-20260619`）：
  - **审查面失衡是被明确记录的问题**：18 轮火力全压表层认证发布层，深层算法核心欠正面审。闭合裁决第 3 步就是"火力从表层转回深层算法核心"。**这块很可能就是 owner 想让你独立发现的盲区。**
  - **语义正确性层是永久显式 TCB 残留**：validator 用对不变量（nogood⊆真不可行 / master 域编码正确 / 剪枝单调）——可逐项独立重验，但"所有语义义务列全了"无法机器穷举证明。I1 的独立复验器（FIX-4）是往这层打的第一钉，但只覆盖 binding-INFEASIBLE、routing 穷尽还是 phase-1 保守（sound 但伤收敛）。
  - **I2 master 域编码 = PARTIAL**（缺 sealed 编码语义等价证明 + 缺 `occupied_cells==bbox` fail-closed 断言；当前 frozen 实心矩形数据不触发，是**沉睡的雷**）。
  - **cut 割族 canonical 原语未收敛**（F7/F8/F3，§2.3），P1.3 接认证前必须先 wire 到共享原语，否则 latent false-INFEASIBLE 会破坏 max_lex 最优性。

---

## 8. 吞吐 / throughput 认证为何排不进 P1.x（核心决策④）

被**三条 PROJECT_LOCK 不变量硬钉死**、不是排期能绕的问题。分三层：

### 8.1 postprocess 三态吞吐审计的 "proven" 只是静态计数 —— `throughput-audit-proven-is-static-count-not-flow.md`（harness memory）
`src/adapters/industrial_planner/throughput_audit.py` 的三态审计（`proven_equivalent` / `partially_proven` / `unproven_or_insufficient`）的 "proven" **不是离散容量流证明**，是两条整数计数比较（⚠ Codex 给源码点 `:1-14`, `:51-58`, `:606-628`；Opus 给逻辑但无行号）：
1. recipe capacity rollup：`proven_equivalent ⇔ proven_capacity_units ≥ required_fractional_runs`（= "设备台数 ≥ 需求台数"）；
2. boundary I/O rollup：`proven_slots = 端口槽数计数`，`required_slots = ceil(flow / port_max_throughput_per_tick)`（= "端口槽数 ≥ 需求槽数"）。
算术是 exact 的（全 Fraction），但审计自己在 `_DEFAULT_LIMITATIONS` + 模块注释明确声明**不模拟 runtime flow balance / splitter fairness / buffer / deadlock / 流体压力**。
**为什么升不成 certified 的"证吞吐"**：它证的是"名义满速容量下界 + 端口数充分"这个**必要条件**（台数够、端口够），**不是**"266 实例 + 98% 密度的离散带子在空间里真能把货流到"这个**充分条件**——后者要带空间约束的整数多商品流可行性见证，审计完全没碰空间/路由维度。⚠ Opus 引 `PROJECT_LOCK.md（约 :320）`明列 throughput-manifest 为 postprocess-only、不得提升 certified；Codex 未给该行、但同结论（sidecar 状态归约 `:606-628`，不能推导 solver CERTIFIED）。`src/search/commodity_throughput.py` 更弱（只算聚合速率、无几何），是 hint 层。

### 8.2 证明级吞吐认证(A)排不进任何 P1.x —— `throughput-cert-blocked-by-9-family-frozen.md`（harness memory）
根因三条 invariant：
1. **§4:274 + `flow_subproblem.py:4-9`**：锁死"diagnostic flow checks 当 certified proof"是 Forbidden Change；flow 是连续 LP(GLOP) 松弛，只诊断。98% 密度下精确证离散带子吞吐 = **研究级开放问题**。
2. **§3A 9-family frozen**（`PROJECT_LOCK.md:179-209`）：cut framework 被焊死成 area/几何/literal 三类静态推理，**无任何 family 表达"离散容量流够不够"**。⚠ Opus 引 `05_open_questions.md` Q1（"9 family 不充分 → 加 F10+，§3A frozen 约束需重审 = paradigm shift 入口"）；Codex 引 `docs/项目说明/05_open_questions.md:17-36`（9-family 覆盖性仍开放数学问题）+ `:173-179`（F4 cell-flow capacity 列 P1 开放；**D2 Path17 曾死路**）。**A 落地 = 解冻 §3A = 开 F10，不是排期动作。**
3. **§4 round22 F16「代数归 Master，几何归 Cut」二分法**（⚠ Opus 引 `PROJECT_LOCK.md:267-269` + 已核 `:449` 有 F16 verdict；Codex 引 `PROJECT_LOCK.md:447-449`）：吞吐是离散容量多商品流，既非纯代数全局约束、也非纯几何 cut，**现有二分法两边都不收**。安放 A 必须先扩这条 invariant。

相位语义对照：P1.2 = 闭 certified soundness（不新增证明能力）；P1.3 = 把已有 9 family 接进 master；P1.5 = 喂真生产 data——**三者都假设证明工具已存在**。A 连数学 paradigm 都没有 → 归 Phase 2+（与 Q1/Q14/Q15 同级 paradigm 入口）。

### 8.3 owner 决定
- **B（certified 口径收窄为"只证布局+连通(有路)+供电覆盖+资源数量够，不证吞吐/容量"）= 立刻做、与 A 解耦、不阻塞**——这就是 §2.2 落地的"Certified Theorem Scope + OUT-OF-SCOPE 清单"。
- **A（证明级吞吐认证）= 研究级 future，新建 `P2.0-throughput-cert` 挂 Phase2+、零排期 / paradigm-gated**。
- **被否决的替代（Codex 补充，逐条）**：把 flow `INFEASIBLE` 直接当 exact-safe cut（否，`specs/08:57-59`）；把 flow/routing `FEASIBLE` 当 throughput 证据（否，只证连通/连续诊断）；把吞吐塞进 §3A F1-F9 cut family（否，9-family 覆盖性本身仍开放）；用 F16 立即收纳（否，纳入需新 theorem/子问题/证书/replay/发布义务）。
- **被 defer 的最接近碎片（全 P1 defer、全未排定）**：F4-cap cell-flow capacity、F2 node-split min-cut、Q11 commodity registry 粒度——都停在 connectivity/容量盲区层，没一个触及"证明级吞吐认证"本身。

---

## 9. 跨切面方法论（这些"怎么工作"的规矩塑造了上面所有决定）

- **codex-claude-clean-workflow**（`codex-claude-clean-workflow`）：大活 = **Codex 实现 → Claude 子代理对抗审 → 主控读源终审 + 重封 v99 + 全量 preflight + 提交**。
- **全量 preflight 不可省（反复实证）**：子代理/codex 自测只跑 targeted 子集或 staged preflight，**多次漏掉全量才暴露的回归**（rebind 破坏交付 / v101 INFEASIBLE 回归 / CRLF allowlist / 3 算法 mock 回归 / GPT 只跑 126 定向漏 4 个文档回归）。`python scripts/preflight_gate.py --full`（含 pytest）+ `@slow` 单跑。
- **跨模型对抗 > 同模型自审**：codex 推翻 opus、GPT 独立逮 GAP、外审推翻主控"收敛"误判——反复证明同模型自审有盲点。**收敛判断必须靠外审打架构，不是内审打补丁。**
- **reseal / freeze-ritual 坑**：改 sealed sink 文件后必须重封 `source_sha256`（V99 floor + manifest sink_files + checker self-pin，self-pin 最后算）；allowlist 按 `qualname+line+source_sha256` 匹配，**改动导致写入点行号漂移 → 必须同步更新 allowlist 的 line**；**pin sha 必须按 LF 算**（`git show HEAD:<file> | sha256`，别用 python `write_text` 写 CRLF，`.gitattributes` 是 `* text=auto eol=lf`）。
- **"文档化 ≠ 已闭"**：Soundness Gap Roadmap 每 gap 三态（原则已在 lock / 实现存在未测 / 实现缺失）；写"I1 由 §131 覆盖" ≠ I1 真闭；红测才关 soundness，文档不关。

---

## 10. 早期史结束时的开放残余 / 已知局限（交接清单）

到 PR1 落地（约 2026-06-26）为止仍开着的：

1. **P1.2 未闭、仍 release-blocked**：owner 手动 gate = `blocked_manual_review_count`（仓库外人工 clean-review 计数），fail-closed。无任何公开 CERTIFIED。
2. **supervisor 操作链缺口（当时）**：到 PR1 落地时，`supervisor_seal()` 有实现但**无生产入口**，`main.py` 止于 `CANDIDATE_PROPOSED`。这是 PR2 #7（certify 生产入口 = go-live 最后通电）要做的；该 #7 已于 2026-07-04 由 `scripts/run_supervisor_seal.py` 落地。
3. **PR2 整条未完**：L0/L1 最小 TCB micro-verifier、受控 import loader（child 经 fd 从 L0 已核字节快照 import）、两段式自举、child read-once、import-closure、AST 闸、argv0/contract digest 硬钉、B2 候选域 L0 独立枚举、B4 `-I -S -B`。（接手时 PR2 在 #5 那一坨的第 14/15 轮外审里——属维度 4/5。）
4. **算法核心欠正面审（审查面失衡）**：18 轮火力全压表层认证发布层，深层算法核心只有 C3 那一次正面审。**I1 只补了 binding-INFEASIBLE 独立复验；routing 穷尽仍 phase-1 保守（sound 但伤收敛）。I2 master 域编码 PARTIAL（缺编码语义等价证明 + `occupied_cells==bbox` 断言，当前实心矩形数据不触发）。** ← 这块最可能藏着我们没发现的盲点。
5. **cut 割族 canonical 原语未收敛**（F7/F8/F3 latent false-INFEASIBLE 雷，P1.3 接认证前必须先 wire 共享原语 + 红测）。
6. **④b root-cure 的性能**：无缓存全量 re-replay，168h 生产前必做内容哈希缓存（3 硬条件保 soundness），至今没做。
7. **吞吐/容量永久 OUT-OF-SCOPE**（除非解冻 §3A 开 F16/F10 paradigm shift）；postprocess 三态审计只能当 telemetry / sidecar，`proven_equivalent` 不是 solver certified proof。
8. **可达性扫描器已知不完备**（漏认 `assert False`/`range(0)`/`match` 无 catch-all 等假不可达）——被 v99 floor hash 钉 + STRUCTURAL_GATE 兜死、实测不可 data-only 利用，但**扫描器本身是"冗余第二层、floor 才是主防线"**（codex 注释诚实声明）。
9. **诚实对外口径的天花板**：内嵌 receipt 是自报数据，真正证明靠 reviewer 重跑；"L0 自身完整性"是带外（git+signing+CI+人审），**"鸡生蛋"信任根不可消除、只能缩小**。永远只能宣称"认证链门控已闭合、剩余风险在声明的 TCB 内"，不能宣称"形式化零风险"。
10. **F492690 capsule 不是零价值**（Codex 强调的诚实点）：它闭了若干窄洞（F3 own-body、FIX-5 read-once/TOCTOU 等），这些后来作为 supervisor 设计 §10「不回退材料」保留；只是它**不能作为发布裁决根**。

---

## 附：关键引用索引（供你独立复核；标注哪一版引用）

**git commits（时间序，旧→新）**：
`a5ff5aa`(④b sink-replay root-cure，Opus) · `3f9ca45`(docs 命题 P，Codex) · `f4f6336`(Codex 列出未说明) · `53396e1`(R3 doc/收敛策略，两版) · `228f266`(FIX-3 phase-gate，后被推翻，Opus) · `f492690`(capsule 根治=FIX-1/3+FIX-5；Codex 给 20 files +3888/-193) · `44089a3`(FIX-4 I1 独立复验，Opus) · `88b2d32`(PYC-EXEC-DIGEST，两版) · `21a9dda`(二次外审 HEAD，Opus) · `7d3c800`(§12 argv0 doc，Opus) · `ddb3b5a`(PR1 supervisor 地基，两版；26 files +1818/-343) · `d3f9009→2904a81→072265a`(PR1 测试债三连，Opus) · `0bc36db`(CI @slow + delivery gate，两版) · `1817c71`(三轮并集 soundness；Codex 给 13 files +1124/-203) · `b085a75`(cc_memory，两版)。
⚠ `de68515`(FIX-2 OPEN-GATE)：Opus 记于记忆但**不在当前 main 线性历史**；Codex 未提及。

**cc_memory 条目**（`python cc_memory/mem.py read <id> --body`）：
`p1-2-closure-path-verdict-20260619`(Opus) · `close-kernel-necessity-verdict-20260619`(Opus) · `p1-2-4b-sink-replay-rootcure-landed-20260620`(Opus) · `p1-2-c3-kernel-audit-3source-20260620`(两版) · `p1-2-c4-c5-2026-06-21-3-latent-false-infeasible-f7-f8-f3-cuts-live-canonical-p1-3b-tcb`(Opus) · `p1-2-review-converged-tcb-start-p1-3`(两版) · `p1-2-witness-split-block-2026-06-21`(Opus) · `naming-p1-3-vs-p1-2-fix`(Opus) · `p1-2-fix-1-design-fixed-witness-verifier`(Opus) · `p1-2-fix-2-open-gate-landed-20260623`(Opus) · `p1-2-fix-3-phase-gate-fixed-witness-228f266`(Opus) · `4-fix-1-3-reopen-capsule`(两版) · `p1-2-capsule-f492690-fix-1-3-fix-5`(两版) · `capsule-opus-canonical-binding-mock`(Opus) · `fix-4-fix-5-i1-toctou`(Opus) · `p1-2-fix-4-landed-44089a3`(Opus) · `p1-2-pyc-exec-digest-landed-88b2d32`(Opus) · `21a9dda-argv0-live-12`(Opus) · `p1-2-round5-external-review-capsule-not-closed`(两版) · `p1-2-supervisor-l0-l1-design-meeting-20260623`(两版) · `pr1-supervisor-mint-preflight`(两版) · `pr1-test-debt-cleanup-20260626`(Opus) · `pr1-1c-external-review-7-blocks-unclosed`(Opus) · `pr1-publication-blocks-abc-fixed`(两版) · `pr1-soundness-b085a75-ci`(两版) · ⚠ `p1-2-supervisor-production-entry-gap-20260626`(Opus) / `fact-p1-2-supervisor-operability-20260626`(Codex)【两 id 都核】 · `p1-2-current-publication-surface-status-20260626`(Opus)。

**harness memory 文件**（`C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory\`）：`throughput-audit-proven-is-static-count-not-flow.md`(Opus) · `throughput-cert-blocked-by-9-family-frozen.md`(Opus) · `p1-2-resume-state-20260621.md`（PR2 后续主源；⚠ Codex 给 67 行 / 56,003 bytes，早期段 `:43-77`, `:86-90`）。导出索引：`cc_memory/exports/MEMORY.md:112-138`(Codex)。

**源码/文档已核实点**：
`src/models/flow_subproblem.py:4-9`（flow diagnostic-only，两版）+ `:119-149`（GLOP 连续 LP，Codex） · `PROJECT_LOCK.md`：§B-1 ⚠(Opus :102-106 / Codex :100-116)、`:145-150`(Codex)、`:53-63`(Codex，routing FEASIBLE != 吞吐)、Forbidden Change ⚠(Opus :454)、F16 verdict ⚠(Opus :267-269 & :449 / Codex :447-449)、§3A 9-family(:179-209，Opus)、throughput-manifest postprocess-only(约 :320，Opus)、public publisher 唯一/失败清 partial(:259-263，Codex)、resume durable-before-reuse(:273-274，Codex)、strong-status authority=sink-replay(:275，Codex)、I1 已实现≠closed(:122-128，Codex)、P1.2 blocked/operability gap(:130-146, :141-154，Codex) · `CHANGELOG.md` 2026-06-26 段（producer/seal/publisher 现状 + main.py 不 invoke seal；⚠ Codex 给 `:9-11`, `:126-131`） · `specs/08_topological_flow_subproblem.md:10-24`（历史文本非当前行为）、`:57-59`(Codex) · `src/adapters/industrial_planner/throughput_audit.py:1-14`, `:51-58`, `:606-628`(Codex) · `src/search/exact_campaign.py`：`supervisor_seal`/`mark_campaign_stopped` raise(:3566-3610)、`_has_unsupervised_certified_checkpoint_claim`(:2564-2578)、`CANDIDATE_PROPOSED_STATUS`(:63-72)、proposal authority/demotion(:2130-2172)、resume sanitization(:2988-3072)、供电见证复验(:1131-1157，Opus)、source digest(:340-378，Opus) · `src/search/outer_search.py`：`_build_certified_result`/`_commit_terminal_full_frontier_certified_result`(:855-954，Codex)、exploratory 直产 CERTIFIED(:2784，Opus) · `src/search/certified_surface.py`：staged/backup/restore/manifest-last/rollback(:607-655, :656-755, :758-877，Codex) · `scripts/check_p1_2_proof_obligations.py`：AST staged-transaction checker(:1382-1526，Codex) · `benders_loop.py`：`_add_exact_whole_layout_nogood`(:7452)、routing→CERTIFIED/flow 不 gate(:6927-6944)（均 Opus） · `binding_subproblem.py:356`(PortBindingModel)、`:391`(binding 绕 canonical role) · `certified_frontier.py:505-524`(candidate_status_digest) · `candidate_proof_replay.py:889-904`(自由重解) · `certified_artifact_contract.py:115`(argv0)（以上 Opus） · `docs/项目说明/05_open_questions.md`：⚠(Opus Q1 / Codex :17-36, :173-179 含 F4/D2 Path17 死路) · `docs/项目说明/p1_2_supervisor_detailed_design.md`（L0/L1 详设计，§12 argv0，两版） · `docs/项目说明/soundness_gap_roadmap.md`（I1–I7 + WS 行，Opus）。


---

# 第 4 章 · PR2 完整 Saga

> 范围：P1.2 发布链在被外审判定旧「capsule」发布架构不 sound、owner 下令「supervisor L0/L1 重做」之后的全部历史。覆盖：(a) 已合入 `main` 的 PR2 #8/#9a 硬化批次；(b) 更早合入的 PR2-b（B1/B2 假-CERTIFIED 信道）；(c) 仍未合并、在分支 `pr2-5-domain-frontier-gate` 上跑了 18 轮的 PR2 #5「close-kernel 第二道门」；(d) PR2 剩余 6 项及推荐执行序；(e) TCB 架构设计会议结论。
>
> 这是一份**决策记录**，不是「照我们的做法做」的手册。凡是我们做过判断的地方，都给出理由、被否方案、以及残余；凡是未决 / 已知受限的，明说。若干我们自己的结论后来被更晚的外审轮次推翻——新工程师应当自由重审任何一条。
>
> **两版史料合并说明**：本章由两份独立挖掘的史料（Opus 版、Codex 版）并集而成。凡两版有出入 / 一版独有 / 引用不一致处，均以 **⚠ 分歧** 显式标注、保留全部信息，交终审裁定，不擅自取舍。

---

## 0. 一段话定位（先读这段，别把「门绿」当「发布」）

P1.2 是一个断言：solver 的 certified-exact 结果**可被 durably sealed 成 CERTIFIED 并发布**。该断言在外审判定旧「capsule」发布架构 unsound 后被重开。owner 的修法是**把 supervisor 重做拆成两个 PR**：

- **PR1**（已落 `main`，commit `b085a75`）重塑了「谁有权 mint 一个 durable terminal `CERTIFIED` 状态」：`ExactCampaign.supervisor_seal()` 现在是唯一的 durable mint；outer-search producer 只提交 `CANDIDATE_PROPOSED`；`publish_verified_certified_delivery_surface()` 是唯一公开发布器。
- **PR2**（仍未完成的另一半）：建一个真正最小、verified-not-trusted 的 L0/L1 可信计算基（TCB）、受控 import loader、独立域枚举——以及吞掉大部分日历时间的那部分，**「close-kernel 第二道门」（PR2 #5）**，它试图约束「一个能重新 seal checker 的恶意未来维护者」还能做到什么。生产 `certify` 入口 #7 已于 2026-07-04 由 `scripts/run_supervisor_seal.py` 落地，但不关闭 #1/#2/#3/#5/#9 或 owner gate。

**无论上述任何进展，P1.2 仍 release-blocked** —— release gate 是 owner 控制的、仓库外的人工 clean-review 计数（`blocked_manual_review_count`，`next_allowed=false`）。下文没有任何东西「认证」或「发布」了任何结果；它只把 soundness 硬化到「将来某次发布**可能**被信任」的程度。

当前权威边界（两版一致，Codex 版给出精确行号）：producer 只到 `CANDIDATE_PROPOSED`、`scripts/run_supervisor_seal.py` 是独立生产 caller、公开发布必须走中央 publisher、owner gate 仍阻塞。见 `PROJECT_LOCK.md:130`、`NAV_MAP.md:23`、`CHANGELOG.md:7`。**不要**把 checker 绿 / preflight 绿 / branch 绿 / 外审 clean / supervisor 入口落地当成 owner release gate 已过。

---

## 0.1 权威源清单（核对这些，别信本稿的转述）

- harness RESUME 锚 `C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory\p1-2-resume-state-20260621.md`（PR2 #5 逐轮历史在其顶部 `▶▶▶` 段；被引用的具体行：`:12` round-14→15 判定、`:14` runtime 三文件字节未动、`:36` 剩余项状态表）
- cc_memory 条目（`python cc_memory/mem.py read <id> --body` 读正文）：
  `pr2b-landed-pr2-remaining-status-20260628`、`pr2-8-9a-hardened-landed-099f5a3`、`pr2-5-seal-frontier-gate-landed`、`pr2-5-ast-pin-canonical-window-hardening`、`pr2-5-closed-world-ast-pin-rounds-3-4`、`close-kernel-ast-pin-closed-world-progression`、`close-kernel-ast-pin-structural-vs-semantic-boundary`、`close-kernel-block-convergence-trend-20260630`、`pr2-5-round8-9-converged-relayed-20260630`、`pr2-5-round10-11-12-fspinout`、`close-kernel-ast-checker-design-lessons`、`pr2-5-round13-14-whitelist-landed`、`pr2-5-round14-11th-review-block-round15`、`gate-self-check-whitelist-not-blacklist`、`data-file-semantic-floor-runtime-anchor`、`pr2-resume-envelope-deferred-finding`、`p1-2-supervisor-l0-l1-design-meeting-20260623`、`p1-2-supervisor-production-entry-gap-20260626`、`pathspec-must-cover-full-reseal-set`、`p1-2-review-converged-tcb-start-p1-3`、`p1-2-fix-1-close-kernel-crlf`、`close-kernel-sealed-lint-v99-reseal-re-export-patch-ruff-f401`、`pr2-5-F-line-import-time-integrity-schedule`（后者为 harness note）
- vnext card `cc_memory_vnext/cards/close-kernel-pin-reaches-runtime.md`
- `CHANGELOG.md`、`PROJECT_LOCK.md`、`NAV_MAP.md`、设计文档 `docs/项目说明/p1_2_supervisor_detailed_design.md`、git 历史

⚠ 分歧（史料覆盖面）：设计会议 `p1-2-supervisor-l0-l1-design-meeting-20260623`、PR2-b 具体 commit（`69980b3`/`592ea13`）、resume-envelope deferred finding 三块**只有 Opus 版挖到并展开**；Codex 版未覆盖这三块（但覆盖了 PR2-b 的 B1/B2 内容、只是没给 commit hash）。反之，cc_memory id `pr2-5-round14-11th-review-block-round15` **只有 Codex 版显式引用**（Opus 版把 round-15~18 统归「RESUME anchor」）。两版都作为并集保留。

## 0.2 本稿写作时自核的实时仓库事实（2026-07-02 快照;2026-07-04 后 pr2-5 已 `6e06922` 合入 main,以下 branch-vs-main 对比已被合并事件取代,现状以 `git log` 为准）

- `main` HEAD = `b35e5f9`；PR2 #8/#9a 硬化更早已合于 `099f5a3`（PR #2）。`main` 上 `099f5a3` 之后的所有 commit 都是 memory/vnext 记账。
- `pr2-5-domain-frontier-gate` HEAD = `9bbb3a6`（round-18），**未合并到 main**。
- `git diff --stat main pr2-5-domain-frontier-gate`：31 文件，+14399/−1788。主导行是 `scripts/check_p1_2_proof_obligations.py` **+8753 行**。`src/search/exact_campaign.py` 仅 **+5 行**；`pr2_l0_micro_verifier_core.py` +20；`pr2_l0_true_verifier_child.py` +24；`certified_artifact_contract.py` ~456；obligations JSON ~100；`strong_status_write_allowlist.json` ~100。（此 diff stat 为 Opus 版自核；Codex 版未给数字。）
- 分支上三个 runtime close-kernel 文件 blob OID：`exact_campaign.py=2f55bc65…`、`pr2_l0_micro_verifier_core.py=af276679…`、`pr2_l0_true_verifier_child.py=da326456…`——与「runtime 字节 round 3→18 未动」的说法一致（重要细微差别见 §6.2）。
- 分支上 runtime 锚符号存在于 `certified_artifact_contract.py`：`LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS`（line 26）、`LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256`（line 31）、`locked_p1_2_close_kernel_violation(...)`（line 533，Codex 版核为 533-593）、`_locked_checker_top_level_closed_world_violation(...)`（line 491）。
- Codex 版另核：当前 `cwd` 的 `main` 代码只到 PR2 #8/#9a 合并态；round-10→18 大多在分支历史里，不在 `main` 文件内容里。**故 round-10→18 的 file:line 只能引分支（`git show 9bbb3a6:<path>:<lines>`），不能当 main 状态。**

⚠ 分歧（checker 行数）：Opus 版称 checker 在分支上 **~12,235 行**；Codex 版引用了 `git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:12639-12647` 的内容（即 checker 分支上 **≥12,647 行**）。两个数字有出入，交终审以实际 `git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py | wc -l` 核定。

---

## 1. PR2 要建的 TCB 架构（设计会议，2026-06-23）

来源：`p1-2-supervisor-l0-l1-design-meeting-20260623`、设计文档 `docs/项目说明/p1_2_supervisor_detailed_design.md`。（此节主要来自 Opus 版；Codex 版通过 `NAV_MAP.md:23` 佐证 producer→`CANDIDATE_PROPOSED`、当时 `supervisor_seal()` 尚无生产 caller、`data/proof_obligations/` 存机器义务/sink inventory/allowlist；#7 生产 caller 后续已于 2026-07-04 落地。）

一次 team review（redteam=codex、soundness=opus、tcb-arch=opus、feasibility=codex，~6 轮对抗，每条断言钉到 file:line）**推翻了初版单-supervisor 草案**，产出 PR2 现在实现的设计。

**为何否掉单 supervisor（理由 + 被否方案）**：单 supervisor 会调 `evaluate_certified_delivery_surface` → `certified_surface` → `exact_campaign` → `master_model`，把 CP-SAT 求解核拖进 TCB。「最小 TCB」和「调 evaluate」自相矛盾，故单-supervisor 设计被杀。

**胜出的设计 —— L0/L1 拆分 + 四类 TCB 诚实框架**：
- **L0 micro-verifier-core = 真 TCB**（~300–400 行）。可信集 = {L0 源 + 固定解释器 + stdlib + OS}。**零项目 import**（目标：`⊆ {strict_json}` 单叶），无 ortools，无域 schema。只做 byte-shuffling + 编排 + 二值 verdict。域解析 / shape 检查 / canonical 校验全放 child，使 L0 保持 <~400 行。
- **L1 orchestrator = verified-not-trusted。**
- **child = 语义 TCB**（verifier + closure bytes + `ortools.so`）。
- **受控 import loader（技术核心）**：L0 用 meta-path importer spawn child；child **只**从 L0 已验证的字节快照经 fd import，绝不走 `sys.path`。一个机制同时关掉 BLOCK-6 + 覆盖完备性 + package-shadow + root-split，也是「verified ⊆ floor」恒等式的物理基础。两阶段 bootstrap（阶段①纯 stdlib 零项目 import 验证 floor → ②装 loader 再 import）在 L0 内关掉 B7。
- **四类 TCB 诚实框架**：每个 TCB 条目必须是①架构事实（机器可验）②已承认的人审根 ③真正 trusted-not-verified ④verified-not-trusted。判据：**「你只能在『伪造它架构上不可达』时才称某物为 TCB；否则它是穿了 TCB 外套的 LIVE 洞」。** 早先两条 PROJECT_LOCK 断言（「parent-only relay = TCB」「guard 非决策权威」）被此规则 + 外部 PoC **证伪并在 phase 1 正式撤回**。

**owner 对调用模型的拍板**：选 **(a) 独立 `certify` 命令**（L0 跑到底并退出 = 最纯净的最小核）。整个 PR2 半程工作量估计：850–1060 行、55–75 测试、2–4 周。

**反复咬人的铁律**：L0 在 stdlib 里重实现项目代码时必须 *逐项等价* —— 你**不能**以「L0 应该小」为由弱化某个检查（5 个 fail-closed 门、三类 JSON：dup-key + NaN + `1e400`）。另外：**L0 自身完整性是 out-of-band**（git + 签名 + CI + 人审）；「诚实写入的鸡生蛋」根只能缩小、不能消除。这是整个努力的诚实天花板，写下来。

---

## 2. PR2 项分类与状态（截至 2026-06-28，`pr2b-landed-pr2-remaining-status-20260628`）

这张表是主地图。里面烤进一条硬教训：一个 Explore-式 subagent 把 1/2/3 标「done」，因为它*找到了表面证据*（L0 零 import、有 `-I -S -B`、用原子 fd 写）。codex 按*设计标准*审，把它们打回**partial**——快照仍扫全 `src/`/`scripts/`，child 仍 import 项目域模块（`from src.search…`），所以不是「最小 TCB 闭包」。我们采纳 codex 的更严裁定。**教训：「找到了」≠「done」；按设计标准审，深审/严审走 codex。**

| # | 项 | 状态 | 规模 |
|---|---|---|---|
| 4 | B4 解释器双固定 + `-I -S -B` | ✅ done | small |
| 8 | argv0 / contract-content digest（`certified_artifact_contract.py:112-123` 仍全信 `sys.argv[0]`） | greenfield → 并入 #8-B 硬化 | small |
| 9a | floor manifest + 生成器 close-kernel pin | ✅ 已落 & 硬化（`099f5a3`） | medium |
| 8（删自跳过） | 删 close-kernel 自跳过 / argv0 旁路信道 | ✅ 已落 & 硬化（`099f5a3`） | small |
| 5 | B2 候选域独立枚举（`pr2_l0_true_verifier_child` ~403-417 仍信 producer `candidate_generation`） | **partial —— 这条长成了 18 轮 close-kernel saga** | medium→huge |
| 2 | 受控 loader 最小快照 + fd | partial | medium |
| 3 | B3 fd-held read-once 全程（当前是 path re-read） | partial | medium |
| 7 | 生产 `certify` 入口（独立命令；main.py 仍停在 `CANDIDATE_PROPOSED`） | ✅ landed 2026-07-04（`scripts/run_supervisor_seal.py`） | medium |
| 1 | L0/L1 最小 TCB 闭包（快照扫全 `src/`，child import 项目域） | partial | huge |
| 6 | AST 可达性闸 | **决定不另建**（见下） | huge |
| 9b | OS 级写隔离（Linux uid namespace/seccomp、Windows 写隔离） | greenfield | huge |
| 9c | 原生 `.pyd`/`.so` TOCTOU（声明 NAMED-TCB 残余） | partial | huge（随 9b） |

**#6 决定（理由 + 被否方案）**：曾考虑建独立「AST 可达性闸」，后**决定不建**。checker 自己的注释承认可达性是冗余层，主防线——source-sha 楼面——已被 #8-B 强化。另建会加一份更弱的、我们已在强制的属性的第二份拷贝。新工程师可不同意；支持建它的论点是「自承冗余层」是跳过一个纵深防御控制的软理由。

**推荐执行序（轻→重、go-live 最后）**：#8 argv0 → #9a floor pin → 定 #6（大概率接受 source-hash 为主防线 = 跳）→ #5 B2 枚举 + #2/#3 loader/read-once 精化 → #1 最小 TCB 闭包 → #9b OS 隔离（+#9c）→ **#7 certify 入口（最后「通电」= P1.2 收敛点）**。（2026-07-04 注:此序为当时计划。后续实际:#7 已通电落地——但入口落地≠P1.2 收敛,收敛仍卡 owner 手动门;#5 close-kernel 已 `6e06922` 合入 main;其余深化项转未排期 backlog、不取消。）

**入口里带的诚实警告**：剩余项列表**会增长**——后续跨模型审剥更多信任洋葱（「trust onion」原理——对抗审总能再剥一层；「审到零发现」*不是*收敛判据；见 `p1-2-review-converged-tcb-start-p1-3`）。

**2026-07-05 状态更新**（supersedes 上表「状态」列；触发 = (b)/① 落地 + owner 暂缓拍板；源 = codex 逐项对当前 git/代码复核 + 本会话 commits，下列 hash 均在本仓库可解析）：

- **#1 最小 TCB 闭包 —— (a)+(b)/① done，整体仍 partial**：(a) runtime 隔离 `4388494`（child 主进程不 import 项目域大模块）；(b)/① 快照**模块清单**最小化 `9d224d8`（`_discover_project_snapshot_modules` 672→硬编码 24 白名单；child `_SnapshotFinder` 只服务白名单 + `sys.path` 仅 stdlib → child 误 import 三禁真 fail-closed；red-line 两条转硬断言）。**仍未闭**：②物理源闭包（三禁/`scripts` 的 `@source:` 文件仍物理留在快照供孙进程 replay）明确 defer；且语义 TCB 有「求解器硬地板」——replay 必须重跑 benders 证 frontier 耗尽/全局最优、fixed-witness 单独不够，故字面「全闭包」要 proof-carrying 第四路（不在 scope）。详见卡 `tcb-has-solver-hard-floor-replay-mandatory`。
- **#2 受控 loader 最小快照 + fd —— 残余 ≈ #3**：「最小快照」由 (b)/① 覆盖；「read-once + fd」= 暂缓的 #3。
- **#3 fd-held read-once / TOCTOU —— deferred**（owner 2026-07-05 拍板暂缓；判据 + 何时该翻转见卡 `deferred-verifier-hardening-toctou-os-isolation`）。
- **#4 —— done**（不变）。
- **#5 B2 候选域独立枚举 —— open（当前最实的未闭 soundness 项）**：close-kernel 硬化线 `6e06922` 合入 main（≠ B2）；replay 虽重跑求解器，但用的仍是 proposal 给的候选域，故 B2（不信 proposal `candidate_placements`、独立重推候选域）未闭。**#5-F part3**（import-time 副作用）仍 open spike，但 soundness 已被 V99 whole-file floor 兜住（TCB 线下、非 release-blocking，见卡 `stage3-spike-fused-5f-part3-findings`）。
- **#6 AST 可达性闸 —— 决定不建**（不变）。
- **#7 生产 certify 入口 —— done as machine entrypoint** `349c56c`（`scripts/run_supervisor_seal.py` 驱动 `supervisor_seal()`）；≠ P1.2 closed（仍卡 owner 手动门）。
- **#8 —— 子项 done，类别未判全 done**：「删自跳过」`52c1e8d`；深化项仍列 backlog。（上表 `099f5a3` 在当前对象库**不可解析**——git 历史被重建过，那是原机器 hash、只当叙事线索。）
- **#9a floor manifest + generator pin —— 机制 done，production bytes deploy-pending**（可解析 commits `016e126`/`9ef5974`/`30f9ee2`）。
- **#9b OS 写隔离 / #9c 原生 `.pyd`/`.so` TOCTOU —— deferred**（与 #3 同批暂缓，卡 `deferred-verifier-hardening-toctou-os-isolation`）。

**一句话**：除 #3/#9b/#9c（暂缓）与 #6（决定不建）外，仍 open/partial 的是 #1 整体闭包（受求解器硬地板 + ② defer 限）、#2 残余（≈#3）、**#5 B2 独立枚举**、#5-F part3（floor 兜住）、#8 深化、#9a production bytes（deploy-pending）。**不是「除暂缓项外全 done」。**

**2026-07-06 更新（PR2 #5 B2 Option A 落地 `16495f4`；文档注 `25e530c`）**：#5 B2 的**字节级**独立枚举已闭——child 在 terminal precheck 后**无条件**从冻结 `canonical_rules` 用 `placement_generator.generate_all_pools` 重推 candidate 几何、断言 `sha256 == 被钉 candidate_placements 字节`，不等即 fail-closed（受信基由「信 45MB 不透明字节」收缩为「信生成器源码〔已入 V99 floor〕 + canonical_rules」；命根子实测：生成器 ~1.5s 逐字节复现被钉字节）。checker 结构性钉死该 gate（进 child 期望 tail + 必调列表）。故上文 1107/1114「#5 B2 open／最实的未闭」**降级为「字节级已闭、下述残余 owner-only」**。**仍 open 的 B2 残余**：把 candidate_placements 彻底移出证明权威（Option B／契约迁移，`PROJECT_LOCK §1A`）是 owner-only；且这是**同生成器重推证字节等值、非独立重实现**。详见卡 `pr2-5-b2-candidate-geometry-rederivation-landed`。
> ⚠ **术语撞车**（坑过多次）：此「B2」= PR2 **#5** 候选**几何**域（candidate_placements）；**≠** §3「PR2-b B2」mint-floor 假-CERTIFIED 信道（早落 `69980b3`）；也 **≠** frontier **尺寸**域 `candidate_generation`（那个 anti-slice/穷尽早已独立锚定、有 PR2#5 切片拒绝测试）。三者同名不同物。

---

## 3. PR2-b（B1/B2 假-CERTIFIED 信道）—— 已落 `69980b3`+`592ea13`

来源：`pr2b-landed-pr2-remaining-status-20260628`、`pathspec-must-cover-full-reseal-set`。（此节 commit hash 来自 Opus 版；Codex 版覆盖了同样的 B1/B2 内容但未给这两个 commit。）

关掉两条假-CERTIFIED 信道：
- **B1（floor load-time TOCTOU）**：`_RestrictedThirdPartyFinder` 改为按 `{resolved_path → sha256}` 放行 + 用 `_RehashingSourceFileLoader` 替 `spec.loader`（`.py`：`get_data` 重读重 hash；`get_code` 编译这些字节、不信 pyc）。原生 `.pyd`/`.so` 用 `_RehashingExtensionFileLoader` best-effort；残余**声明 NAMED-TCB**。
- **B2（mint 接受 caller floor）**：删 `L0SupervisorSealRequest.dependency_manifest_path`；`run_l0_supervisor_seal` 现用无路径的 `_load_canonical_dependency_floor_manifest(source_root)`（结构性关掉、非仅入口；checker AST 强制 seal 调该 wrapper）。

**值得记的过程反转**：这花了*两*轮。round-1 修 B1/B2；跨模型审提 CONCERN，round-2 重构 B2（canonical wrapper 拆分）、令 child `is True`、令 docstring 诚实——它曾*撒谎*（「pinned generator」）被改成「host-NAMED-TCB，deferred to PR2-c」。**教训：over-claim 信任的 docstring 本身就是 soundness 缺陷。**

**CI 抓到的缺陷**：commit `592ea13` 是被 CI 逼出的、非本地测试——reseal commit 的 pathspec 漏了 `exact_campaign.py` 的 `supervisor_seal` delegation + 8 个迁移测试 + `.gitignore`。产出 `pathspec-must-cover-full-reseal-set`：**reseal commit 必须覆盖完整一致集，否则 CI 漂移。**

---

## 4. PR2 #8 / #9a 硬化 —— 已落 `main` @ `099f5a3`（CI 绿，两 gate）

来源：`pr2-8-9a-hardened-landed-099f5a3`、card `close-kernel-pin-reaches-runtime`、`CHANGELOG.md`。

**落地内容**（merge `099f5a3`，PR #2；CI：project-foundation 2m36s + slow-soundness 13m10s @slow 全 Linux）：
- **#8**（`be5ed93`）：删 close-kernel 自跳过（一条 argv0-伪造旁路；死分支，无递归）。
- **#9a**（`507f213`）：floor manifest + 生成器钉进 close-kernel sha 表。
- **GPT Pro 外部硬化**（`0657872`）：#8-A + #8-B + #9a-A（下）。
- **manifest deploy-pending 标记**（`ec7dc52`）。

当前 main 可核 file:line（Codex 版）：`certified_artifact_contract.py` 现无自跳过、强制用 `-I -S -B -X pycache_prefix=<fresh>` 子进程跑 checker —— `certified_artifact_contract.py:117`、`:129`；checker 常量钉 floor manifest/generator sha —— `check_p1_2_proof_obligations.py:42`；`certified_artifact_contract.py` 进 V99 source floor —— `check_p1_2_proof_obligations.py:3926`；obligations 记 deploy-pending provenance —— `p1_2_proof_obligations.json:855`；required manifest+checker —— `certified_artifact_contract.py:24`。

⚠ 分歧（argv0 行号）：Opus 版称修前 `certified_artifact_contract.py:112-123` 全信 `sys.argv[0]`；Codex 版引修后 `:117`/`:129`（已无自跳过、强制隔离子进程）。两者描述的是**修前 vs 修后**不同快照，不是矛盾——保留全部，注明语境。

**GPT Pro 多会话 panel 挖出的 3 个 BLOCK（我们本地审 *和* codex *都*漏）**（2 个独立 GPT Pro 会话收敛 = 高置信；单会话无 panel 大概率会 ship 这些洞，这验证了多会话 panel review 路由 `review-routing-gptpro-relay`）：
- **#8-A**：checker 子进程用 `-I -S -B -X pycache_prefix` 隔离（外加嵌套 strong-status 子 checker）堵父进程 `sitecustomize`/`PYTHONPATH` 对信任锚的污染。
- **#8-B**：`certified_artifact_contract.py` 进 V99 source-sha 楼面。**我曾亲自判「不需 reseal」，判错了。** 删自跳过让此文件成为 close-kernel 验证的*唯一*权威（信任锚）；一旦某改动让文件成信任锚，它**必须**被钉，否则有人把它改回 `return None` 旁路而 gate 只检查存在性。
- **#9a-A**：L0 *runtime* byte-pin manifest（size/sha 漂移 fail-closed）+ 删 `_generate_default_dependency_floor_manifest`。这关掉一条**时序旁路**：#9a 把 manifest 字节钉进 *checker*（gate），但 L0 *runtime* loader 不消费该 pin、缺失时 auto-generate → 在 gate-pass 和 mint 之间换 manifest 就用了未审 floor。（一个 GPT Pro 会话有可跑 PoC。）

**codex 在应用补丁时抓到并修了 GPT Pro 自己补丁里的一个真 bug**（L0 把 sentinel 预解析成绝对路径 → 与 pinned 字节不符 → child 拒；codex 保留 sentinel、让 child 解析）。**教训：外审补丁不盲应用**——按 spec 重实现。

**两条硬教训（贯穿所有剩余 PR2 项，已固化成 claim-guard 卡 `close-kernel-pin-reaches-runtime`，severity high）**：
1. **「当前没 sha-pin」≠「不需 reseal」。** 若某改动把文件升格成信任锚角色，它必须进 source-sha 楼面。问「这改动给它什么信任链角色」，别问「它今天在不在楼面」。
2. **gate-pinned ≠ runtime-pinned。** pin 必须落在*真正被执行/受信任的 runtime 消费点*、fail-closed、禁 runtime auto-generate。gate 与 runtime 之间任何「读了但不再重验」窗口都是 TOCTOU / 时序旁路。这是 PR2 反复出现的「gate-time vs runtime」主题的根。

**⚠️ 带向前的 Deploy-TODO，别丢**：钉进的 floor manifest 是 **dev/CI deploy-pending 占位**（GPT Pro sandbox 里审过的 Linux-env 字节），**不是**生产审过的 canonical。代码标 `manifest_provenance_status: deploy_pending_placeholder_regenerate_on_production_cachyos_py313`（在 obligations + L0 注释）。**生产部署前必须**，在 CachyOS + Python 3.13：跑 `scripts/generate_pr2_dependency_floor_manifest.py` → 审字节 → 换占位 size/sha → 重 seal（manifest sha/size、checker floor pin、L0 常量、obligations sink、allowlist）。本机生不了（WSL = Ubuntu，无 CachyOS、无 Py3.13 venv；CachyOS 是另一双启动入口）。runtime byte-pin / fail-closed 机制是 host-无关且完整；只有 manifest *内容* 等生产 host。这是 PR2 **#6-of-deploy** 任务（与上文 #6 AST-可达性决定不同——命名撞车，抱歉）。

---

## 5. PR2 #5「close-kernel 第二道门」—— 定义与威胁模型

这是 #5 项（B2 候选域独立枚举），但它远超原 scope、长成一个自检门的 18 轮对抗硬化。**写作时全在分支 `pr2-5-domain-frontier-gate`（HEAD `9bbb3a6`,未合并;后续 round-19/20 完成后已由 `6e06922` 合入 main）。**

### 5.1 两个 artifact

1. **checker** —— `scripts/check_p1_2_proof_obligations.py`（分支上 ⚠ 行数分歧见 §0.2；+8753 vs main）。做 AST + source-sha 检查：`CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH` 里逐符号 source-sha pin、closed-world 函数/模块顶层分析、import allowlist、data-flow/reachability、以及对*自身*的 self-integrity 检查。分支上 `_check_close_kernel_contract()` 自述它是 small structural gate、不证明 candidate 或 geometry、只封 proof-bearing authority surface（`git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:12639-12647`）。
2. **`certified_artifact_contract.py`** —— **runtime 父进程锚**。`locked_p1_2_close_kernel_violation(...)`（分支 line 533，Codex 核 533-593）在子进程跑 checker*前*先 parse 并 pin checker，并消费 runtime pin 如 `LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256`（line 31）。此文件本身在 V99 whole-file 楼面（即 #8-B）。分支上它先检查 required paths / manifest semantic projection / checker AST anchor 再跑子进程（`git show 9bbb3a6:src/search/certified_artifact_contract.py:533-593`），并把 required paths 扩到 manifest/allowlist/checker + protected callees（`git show 9bbb3a6:src/search/certified_artifact_contract.py:26-55`）——比当前 main #8/#9a 更进一步。

### 5.2 威胁模型（这是全部要点，内化它）

对手是**一个能重新 seal checker 的恶意未来维护者**——他能重算每个 source-sha、重钉 V99 floor、更新 obligations/checker self-pin，保持 checker *绿*。第二道门约束*重 seal 后的代码还被允许长成什么样*。一个发现只有在「对手在**忠实 reseal 且 checker 仍绿之后，仍能掏空 runtime proof**」时才是**真 BLOCK**。需要一个*显眼的 checker diff*的发现，按已接受边界不算 BLOCK（人工 clean-review 会抓）。

### 5.3 启动这一切的真 soundness gap（`pr2-5-seal-frontier-gate-landed`）

codex 对抗追踪 + 逐行确认发现一个**真 gap**（非假想）：L0 true-verifier child 把 producer proposal 升格进 `scratch_state` 跑终态 precheck 时，只设 `final_status="CERTIFIED"` 而**漏设 `declare_mode` 和 `last_stop_reason.status`**。同时 `mark_campaign_stopped`（`exact_campaign.py:3608-3616`）把诚实提案写成 `last_stop_reason={reason:…, status:"CANDIDATE_PROPOSED"}`、硬拒 producer mint `status=="CERTIFIED"`、且从不设 `declare_mode`。净效果：`has_terminal_full_frontier_certified_evidence(scratch_state)` **永远 False** → 三个校验*（全前沿穷尽 + winner-必是-最优候选 + canonical 域）* 在 durable-seal 路径上是**死代码**（对诚实*和*恶意提案都跳）。穷尽只在 *publish* 面被重查。durable supervisor seal 本身 unsound。

**最小对称修法（Option A′）**：child 升格时也设 `scratch_state["declare_mode"]="strict"` + `last_stop_reason={reason:TERMINAL_FULL_FRONTIER_CERTIFIED_REASON, status:"CERTIFIED"}`，让终态校验无条件跑。（commit `2ec8954`。）

⚠ 分歧（硬化 commit）：Opus 版称此后有硬化 commit `2c258c6`（checker 升格校验从 token 升级成 AST 顺序/参数检查 + 补穷尽维度负例）；Codex 版未提 `2c258c6`。保留。

**这就是为何 3 个 runtime 文件与 `main` 不同**——Opus 版自核：`exact_campaign.py` 比 main +5 行、`pr2_l0_true_verifier_child.py` +24、`pr2_l0_micro_verifier_core.py` +20。所以「runtime 字节从未动」这个大家挂嘴边的不变量要精确理解为：**runtime 文件相对 main 带着真的 #5 declare_mode 修复，然后在 *AST-pin 硬化 round 3→18* 期间冻结于 blob OID `2f55bc65/af276679/da326456`。** round 3–18 只动 checker + 测试 + obligations + `certified_artifact_contract.py`。别把「字节从未动」误读成「相对 main 无 runtime 改动」。

⚠ 分歧（字节不动的语义）：Opus 版强调「runtime 三文件相对 **main** 确有改动（declare_mode 修复），只是在 round 3→18 之间不动」；Codex 版表述为「三个 runtime close-kernel 文件字节不动」（round-to-round，引 blob OID + `p1-2-resume-state-20260621.md:14`）。两者不矛盾——Opus 版加了「vs main 的差异」这层精度；采 Opus 的精确表述，同时保留 Codex 的 round-to-round 观察。

### 5.4 修复本身上的两个 GPT Pro BLOCK（`4410b6a`, `dbd1d72`）

panel（5 会话）发现 2 个 codex 本地审 *和* 我都漏的真 BLOCK：
- **BLOCK-1（parent durable mint 不归一 `declare_mode`；3 会话收敛）**：child 只修了自己的 scratch_state；*parent* mint durable CERTIFIED checkpoint（`pr2_l0_micro_verifier_core.py` `run_l0_supervisor_seal` ~294）加**两个** transition validator（L0 `_supervisor_certified_transition_violation_l0` ~838、runtime `exact_campaign._supervisor_certified_transition_violation` ~1880）仍从 producer proposal 复制 `declare_mode`。→ producer 设 `declare_mode="best_effort"`，child 在自己的 strict scratch 上通过，parent 写 `final_status="CERTIFIED"` 而 `declare_mode!="strict"` = **自相矛盾的「钢印却可擦墨水」证书**，它过不了自己的 `has_terminal_full_frontier_certified_evidence`。修：在*三处*归一 `declare_mode="strict"` + 一个 `_postwrite_state_violation` 纵深守卫。**坑**：两个 transition validator 把 `expected`（从 proposal 克隆）与 durable state *逐字节* 比，所以三处必须一起改，否则得到假 `supervisor_seal_transition_mismatch`。
- **BLOCK-2（AST pin 太松）**：原 AST 检查只做 `ast.walk` 存在性 + 行序——可被 `if False:` 死代码、`scratch_state.update({...})` 动态覆盖、多重赋值、任意 `last_stop_reason` dict、嵌套 `scratch_state["last_stop_reason"]["status"]=…`、或在 aliased state 上跑 precheck 绕过。重写成 STRAIGHT-LINE 严检。

**CRLF/LF reseal 坑（`b6d41c6`，可复用）**：Python `write_text`/`open("w")`/`json.dump` 在 Windows 写 CRLF；repo `.gitattributes` 提交时强制 LF；checker hash *工作树* 字节 → 在 CRLF 树上算的 self-pin sha ≠ 提交的 LF blob sha → **本地过、CI/包挂。** `git checkout --` 不修（autocrlf 把 CRLF 树当「等于 LF index」）。**正确：reseal tracked 文件用 Edit 工具（保 LF）或 `open(...,newline="")`；绝不用 Python `write_text`；pin sha 用 `git show HEAD:<f> | sha256` 算。**（cc_memory `p1-2-fix-1-close-kernel-crlf`。）

### 5.5 逐轮墙（round 0 → 18）—— saga 的诚实核心

这是「一个永不收敛的黑名单，以及我们慢慢意识到这点」的故事。每轮：一个外部 panel（GPT Pro 多会话，1 综合 + ≤5 聚焦角度）和/或本地 codex 对抗 re-probe 找出*又一种*绕过形态；我们钉它；下一轮找出下一种。来源：`pr2-5-ast-pin-canonical-window-hardening`、`pr2-5-closed-world-ast-pin-rounds-3-4`、`close-kernel-ast-pin-closed-world-progression`、`close-kernel-ast-pin-structural-vs-semantic-boundary`、`pr2-5-round8-9-converged-relayed-20260630`、`pr2-5-round10-11-12-fspinout`、`pr2-5-round13-14-whitelist-landed`、`pr2-5-round14-11th-review-block-round15`、rounds 15–18 的 RESUME 锚。

**Round 1–2（黑名单 → canonical window）**：round-1 枚举禁止形态 → 漏 8 类（挪 `final_status`、别名、`__setitem__`、`|=`…）。round-2 把 init↔precheck「canonical window」限到 6 槽 + pop → 仍可绕，因为 6 槽中 3 槽 RHS 是任意表达式（`locals()[...].__setitem__`、`__ior__`、walrus、exec）。**第一洞见：whitelist > blacklist**（commit `cce5dd5`）。

**Round 3–4（closed-world；`44c8da6`, `2fa42b9`）**：正向 RHS 白名单 + runtime-rebind 封口 → panel 随后剥出更深的「global/reachability」类（早退支配、CPython 元对象、模块级 monkeypatch、伪造 `child_verdict`、return dict `**evil`、precheck 额外 kwarg）。round-4 = 「closed-world」（G1–G7）。**closed-world pinning 的四支柱**（每支柱省掉→仍可绕）：(1) closed-world 函数体——只许有限白名单语句；禁*所有*嵌套 def/class/lambda、`__builtins__`、*所有* dunder 属性、对任意属性目标赋值；import/getattr 降到精确 allowlist；(2) closed-world *模块顶层*（import-time monkeypatch 污染看似干净的函数）；(3) 可达性/支配（precheck 支配唯一 accepting return；钉锚点前的精确前缀，使 `return None`/`if True:` 早退无法把 pinned 区域变死代码——*别*试图「检测恒真判断」，那是打地鼠；只放行真 canonical 前缀）；(4) data-flow（被检查对象 = 返回对象 = 持久化对象）。**代价 = 刻意的脆性（「瓷封」）**——任何合法重构都令 checker 变红、逼一次同步 checker 改动 + 负例 + reseal。GPT Pro 3 会话同意这对 close-kernel 证明 pin 是*可接受*的、非 over-brittleness。

⚠ 分歧（round-3 commit）：Codex 版把 round-3 单列为 commit `7a6cd8c`、`eb93637`（正向 RHS 白名单/禁 runtime rebind/frame/dynamic namespace），round-4 = `44c8da6`、`2fa42b9`；Opus 版把 round 3–4 合并归于 `44c8da6`、`2fa42b9`、未提 `7a6cd8c`/`eb93637`。保留全部，交终审核 git log。（cc_memory `pr2-5-closed-world-ast-pin-rounds-3-4`。）

**Round 5–7（结构 vs 语义边界；`66511ce`, `9c06ab8`, `ad73e4f`, lint `dbe27c0`）**：每次 re-probe 剥一层更深的间接：
- r5 `66511ce` 钉 shape/capability（`_verify_supervisor_domain` 闭世界、transition helper 整 body、return dict、precheck、duplicate def 绑定）；
- r6 `9c06ab8` 钉可达性/早退/class-method body——child 的*真*入口是 `verify()`，checker 从未强制它 dispatch 到深审的 `_verify_supervisor_domain` → 给 `verify()` 整 body pin 且必须到达它；
- r7 `ad73e4f`/`dbe27c0` 钉 result-data-flow + 整 body pin `run_l0_supervisor_seal`（唯一 durable-CERTIFIED 写入器——唯一 chokepoint，整 body pin 吸收一整类 post-gate 篡改，如保留调用再覆盖 `replay_violations={}`、伪造 verdict、post-consume 改 state）。

**owner 在此首次划界（2026-06-30）**：写入路径*收敛*（`run_l0_supervisor_seal` 整 body pin；无 round-8 for it），但终态校验*内部数学***未**收敛——每个中间计算（`occupancy prefix`、`mandatory_instances`、power accumulators）都是「调 helper、覆盖结果」点，逐个钉是打地鼠，叶子 helper（`_build_occupancy_prefix`）终归只能靠 sha 楼面守——**AST 无法钉数学是否正确**。裁定：AST 门覆盖*结构*（durable writer 整 body pin + 入口可达性 + direct-gate data-flow + closed-world）；叶子数学划给 **sha 楼面 + frozen-artifact hash + 人工 reseal 审查**（输入是 preflight-hash-pinned 的 frozen artifact；任何篡改改 runtime sha → 触发 freeze-ritual → 人看到 `mandatory_instances=[]` 这种显眼 diff）。此边界诚实写进 checker 注释 + 审查包，让 reviewer 不 over-trust AST 门。（`close-kernel-ast-pin-structural-vs-semantic-boundary`。）

**Round 8–9（`c115f31`, `7851c1e`）**：第 5 轮 panel 对 round-7 `dbe27c0` 判 BLOCK，挖出 4 类（child 编排结果数据流、L0 装配链 TCB 未钉、`ExactCampaign.save` guard 未钉、空矩形 off-by-one）。round-8 `c115f31` 修 5 类：3 chokepoint 整 body pin、L0 装配链 17 helper/常量/child bootstrap source pin、`save` guard source-sha、compare-gate live-effect、空矩形叶子数学用**执行型 canary**（owner 的 call：source-sha 对 re-sha 对手无用、AST-pin 脆，故执行型 oracle 测试真正捕获它，*不改 runtime 数学*）。Lens A 独立确认 16 bypass 全堵。Lens B 随后挖第 6 类：一个*被 chokepoint 调用的* gate helper（`_strong_status_keys` → `return []` 跳过整个 candidate-sink replay 却仍 mint CERTIFIED）。round-9 `7851c1e` 从 6 个 chokepoint 走调用图，给 3 个文件内所有可达 cert helper 做函数级 source-sha pin，每个配一个「顶部早退掏空 → sha 漂移」拒绝测试；codex 独立重走 → 声称 123/123、0 gap。

⚠ 分歧（round-9 helper 计数）：Opus 版称「**123** 个可达 cert helper……codex 重走 123/123、0 gap」；Codex 版称「**108+/123** 个可达 cert helper……文档记载当时 re-probe 说 123/123 全覆盖」。数字有出入（108+ vs 123），且后来第 6 轮 panel *证伪* 了这个计数（见下）。保留全部。

**这是我们*以为*收敛的地方**——`close-kernel-block-convergence-trend-20260630` 记了三个「到底了吗」信号：(1) 深度阶梯有界——穷尽所有可达依赖；(2) 破法越来越*浅/显眼*（早轮 verify-echo 隐形且致命；晚轮早退掏空留显眼死代码、人 reseal 会抓）；(3) 战线从「修洞」移到「划界」。**这个收敛判断在 round 10–14 被证明是错的**——见下。这是值得标出的诚实反转：元模型说「收敛中」，现实又产出了四轮新形态。

**Round 10–12（pin-all + F 单列；`a5a5e64`, `adeddc5`, `8714ee7`）**：第 6 轮 panel *证伪*了 round-9 的「123/123 可达」（三会话各报*不同*可达计数 = 手工/单闭包计数不可靠）。round-10 `a5a5e64` 不再算可达闭包，**pin 全部**（3 文件里每个 FunctionDef + 整 class sha + method + 模块常量）+ `_check_close_kernel_files_fully_pinned` 断言全覆盖。分支保留的 round-10 设计注释说明此举让「是否覆盖所有可达 helper」结构上不再可能漏，因为新增 symbol 不 pin 就红（`git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:9281-9295`）。round-11 `adeddc5`（第 7 轮 5-session panel，9 个真 BLOCK）修：**decorator 不进 `ast.get_source_segment`**（segment 从 `def`/`class` 行起，给 pinned method 加恶意 decorator 只改整 class sha、可重 seal）→ `_source_text` 现从 `min(decorator.lineno)` 起；**类成员「最后绑定胜」vs checker「取第一个」**→ 类成员绑定唯一性 fail-closed；**first-party import-time 传递闭包不在 V99 floor**（改 `strict_json.py`，checker 变绿甚至无需 reseal）；另有嵌套类/async 漏、base/`__init_subclass__` def-time、常量 RHS import-time 副作用、`ImportFrom.level` 漏、`ast.walk` 只证明出现不证明 live、verifier canary。round-12 `8714ee7` 是对 import-time 闭包 walker 的 robust 重设计（22→60 文件），此前 codex 发现 4 个保绿绕过。

**然后 F 未收敛，owner 把它单列（2026-07-01，option 1）。** round-12 后 codex 继续挖 import-time 逃逸：resolver 只匹配 `src.*` 且只映射 `.py`/`__init__.py` → `.pyw`（本 host `SOURCE_SUFFIXES` 含它）、`scripts.*`、非-`.py` first-party 逃出闭包；`importlib.__dict__['import_module'](...)` 躲别名检测；任意 import-time 副作用 / def-time 隐式调用无法枚举。**硬元结论**：*每一轮，外审都在上一轮最新、最复杂的新增里找到又一种形态*（round-9 漏 pin → round-10 pin-all → decorator/class-body → round-11 → F 闭包 → round-12 → `.pyw`/`scripts.*`/`__dict__`/def-time）。**import-time 对能 reseal 的维护者是图灵完备执行面——你枚举不完，round-N 迭代收益递减。** → F（import-time 执行完整性）被拉成专线 **PR2 #5-F**，紧邻 #1；round-12 的 F 代码留在门里作 best-effort 部分防御。见 `pr2-5-F-line-import-time-integrity-schedule` 和 §7/§8。

**Round 13–14（结构白名单；`504b3f8`, `d1a59ad`）**：第 9 轮 panel 判 round-12 结构门 NOT sound（7 FIX 组：如 binding walker 忽略 RHS/defaults 里的 `NamedExpr`（`:=`）；`_has_live_errors_extend_call` 只验语法 shape、不验 `errors` 仍是到达 `if errors: return 1` 的原始 list；self-binding 检查的 required-call 列表不含*它自己*；`_check_evidence_and_tests` 不 floor obligations JSON 语义 = 第**三**条信道：保留 id+tests、抹掉 title/findings/evidence、仍绿）。我另自己抓到 **Finding A**（FIX-4 漏一个延迟方法别名 `s=errors.clear; s()`）。第 10 轮 panel 判 round-13 *仍* BLOCK（收敛中）——新的 checker self-integrity 检查（FIX-4/5）暴露一整片绕过 + 2 个新 data-file 信道。**战略转向（owner）**：对 checker-self 类，因它是开放攻击面但*已知*类可被白名单真正关掉（不像 F 无界），走结构化白名单 round-14 `d1a59ad`：`errors` 用法只许好形态（init 目标 / `extend(callee)` / `+= callee` / `append` / `if errors:` / `return errors`）、拒其余——`errors.__imul__(0)` 因「非允许形态」而 fail，无需枚举任何坏形态。加 fail-fast self-check 前置（别把自检结果 append 进同一个可清空 `errors`——「烟感接在会烧的电线上」——`gate-self-check-whitelist-not-blacklist`；自检结果落到 private `preflight_errors`）、required-callee FLOOR、两条静默 data-file 信道拉到 runtime 锚（C6/B1——`data-file-semantic-floor-runtime-anchor`：`strong_status_write_allowlist.json` 整字节 floor、obligations 语义投影 digest 钉到 `certified_artifact_contract.py` runtime 锚、不留在可重 seal 的 checker 自引用环里）。分支上 `_check_function_errors_whitelist()` 可见白名单做法（`git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:3526-3549`）。

**Round 15–18（blanket-forbid + A4 残余 + owner 裁定；`1b90285`, `c96a601`, `2ca6864`, `9bbb3a6`）—— 来自 RESUME 锚 + `pr2-5-round14-11th-review-block-round15`**：
- **round-15 `1b90285`**：第 11 轮 GPT Pro 6-panel 对 round-14 判 NOT sound，6 角度高度收敛，根因裁定 = round-14 把 whitelist 原则只用于 `errors` Name 引用，A3 成员写、A4 名字 shadow、checker-self runtime binding 仍是 blacklist（`p1-2-resume-state-20260621.md:12`）。round-15 把白名单/闭集扩到三面：S1 静默 manifest 信道的 closed-world key set；A3 用 `ast.walk` 禁命名反射原语的 complete-primitive-set 门；A4 name-shadow；C-b `errors` 绑定完整性（含 match-capture）；C-a entrypoint/callee 锚（阻 `main=lambda:0` 晚绑定）；C-c/C-d/C-e。我抓到一个**真残余（Finding A，BLOCK）**：C-a 锚漏了*模块顶层动态命名空间写*——`globals()["main"]=lambda:0`（一个 target 是 Subscript 的 Assign）没被算作 `main` 的绑定点，故 runtime 锚放过、真 `main` 的自检从不跑 → 子进程退 0、两端皆绿。修法 = 在 runtime 锚和 checker 两侧都加 checker-module 顶层 closed-world 白名单。此处发生一次**并发编辑事故**（我和 codex 同时在同一 worktree 实现 Finding A）——以 clean merge 收场，但教训是**别派 codex 在同一 worktree 并发自实现**。另：一次 reseal 暴露了 codex round-15 的潜伏 bug（一个 `PROTECTED_CALLEES` 字符串子串与 proof-bearing token 撞车）→ 我们正式把 `certified_artifact_contract.py` 注册为 close-kernel sink。还有一处 `weakref` 改动（`_p1_2_parent` 强引用 → `weakref.ref`，避 Py3.13 GC 环崩溃）。**记下的教训：targeted 测试不够——需 full checker 单跑 + full preflight 才能暴露 unregistered-sink 这类东西**（codex 从不 reseal、从不跑 full checker）。
- **round-16 `c96a601`**：codex 的*relay 前*本地对抗审判 round-15 NOT sound、3 个非-F BLOCK（round-15 的「完整闭集」*仍是*黑名单、*仍*漏形态）：BLOCK1 顶层 closed-world 只查语句*类型*、漏允许语句里的 import-time 表达式副作用；BLOCK2 A3 漏函数对象 mutation（`getattr(self,"supervisor_seal").__func__.__code__=…`）；BLOCK3 A4 漏 `exec(...,globals())` 重绑 witness 名。3 个都靠 blanket 禁整类修掉。
- **round-17 `2ca6864`**：codex-r16 审发现 A4 **form-4**（`operator.setitem(globals(),…)`、`dict.__setitem__(globals(),…)`、`types.FunctionType(compile(...),globals())()` 等）。→ A4 改**blanket-forbid**：若 witness body 引用 Name ∈ `{globals,locals,vars,exec,eval,compile,__import__,setattr,delattr,types,operator,ctypes,importlib,gc,inspect}` 或 Attr ∈ `{__dict__,__setitem__,__setattr__,__delattr__}` → fail-closed shadow。随后一个 5-lens codex 对抗 workflow（263K tokens，5/5）找到*唯一* structural_block = A4 **form-5**（`witness_func.__globals__["name"]=fake`——round-17 把 `__globals__` 加进 A3 attr 集却忘了同步进 A4 集）。
- **决定性认知 + owner 裁定（2026-07-02）**：我探测发现 A4 的黑名单**可证不收敛**——form-5 `.__globals__`、form-6 `sys._getframe().f_globals[...]`、form-7 `sys.modules[__name__].witness=`（attribute-target，`_function_shadows_name` 抓不到）全绕；每加一个 attr，下一个就冒出来。**但 witness 函数已被 source-sha 逐字节钉死（改它们 = 显眼 diff + 人工 clean-review），故此残余与 F #5-F、checker-self 同类。** 我按「黑名单→blanket 仍漏 = 战略决策而非又一轮」的站着承诺升级给 owner。**owner 裁定：接受 A4 dynamic-reflection rebind 为残余（推荐 option）**——并入「best-effort 门 + 显眼编辑/clean-review 残余」，与 F #5-F、checker-self 同类；不再是 release blocker。
- **round-18 `9bbb3a6`（当前 HEAD）**：对*已知* A4 形态做 best-effort 加固（attr 集 += `__globals__`/`f_globals`/`f_locals`/`f_back`/`tb_frame`；`_function_shadows_name` += form-7 的 attribute-target 检测）+ best-effort-残余注释。分支 checker 注释明写此裁定（`git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:1626-1634`）。Full preflight PASSED（3734 测试，无回归），提交 blob sha == pins（checker `1e49c70e`），3 runtime 文件字节未变。

**round-18 分支 commit 链（Codex 版给全链）**：`2ec8954`→`b6d41c6`→`cce5dd5`→`2fa42b9`→`66511ce`→`9c06ab8`→`ad73e4f/dbe27c0`→`c115f31`→`7851c1e`→`a5a5e64`→`adeddc5`→`8714ee7`→`504b3f8`→`d1a59ad`→`1b90285`→`c96a601`→`2ca6864`→`9bbb3a6`。⚠ 注：此链未含 round-3/4 的 `44c8da6`（及 Codex 版另提的 `7a6cd8c`/`eb93637`）、`4410b6a`/`dbd1d72`、Opus 版的 `2c258c6`——这些在逐轮正文里被提及但不在 Codex 给的显式链里，交终审用 `git log --oneline main..pr2-5-domain-frontier-gate` 核完整拓扑。

### 5.6 PR2 #5 当时状态（WAITING_EXTERNAL，截至 2026-07-02——历史快照;后续:第 12 轮外审未发,round-19/20 收口后 `6e06922` 合入 main,外审循环画线停止）

- HEAD `9bbb3a6`（round-18），分支 `pr2-5-domain-frontier-gate`，**未合并**。
- **第 12 轮 GPT Pro relay 已备好、staged 待 owner 跑**（经剪贴板/Win+V；owner 在仓库外跑 GPT Pro、回传报告）。包 `C:\Users\22957\pr2_pkg\zmd_pr2_5_round18_9bbb3a6.7z`（sha `5a59999f…`）+ 6 提示词 `C:\Users\22957\pr2_5_round18_review_entry_{1..6}_*.md`。提示词明确告诉 reviewer：A4 dynamic reflection 是*owner 裁定的 best-effort/clean-review 残余（同 F）*、请**别**再举已接受的 A4 dynamic 形态，而是查残余边界是否画对、以及是否存在任何*新的* 静默 / runtime-gut-without-checker-edit 结构 BLOCK。
- **回传后**：并集 + triage → 若无*新*结构 block（残余只剩 F / checker-self / A4-dynamic、边界正确）→ **merge `pr2-5` → main**（CI @slow）→ 续 #2/#3/#1(含 #5-F)/#9b/#9c/#7。若有静默/可 reducible 的结构 BLOCK → round-19。若残余边界画错 → 按 GPT Pro 指点补。
- **诚实状态行**：「round-15→18 的结构 BLOCK 已驱到零；残余是三个显式类、全靠显眼-diff + clean-review 兜底。」这是*关于结构发现的断言*，不是 soundness 证明。saga 自己的历史（round-9 宣布收敛、错到 round-14）就是「零结构 block」要谨慎对待的理由。

---

## 6. 元模式（动 checker 前请先读这段）

来源：`close-kernel-block-convergence-trend-20260630`、`close-kernel-ast-checker-design-lessons`、`gate-self-check-whitelist-not-blacklist`、`close-kernel-ast-pin-closed-world-progression`。

**对反射 / 图灵完备面逐形态黑名单永不收敛。** 对能 reseal 的维护者，「禁已知坏形态」无底——Python 提供无界方式清 list、重绑名、退进程、import-time 执行（`exec`、`operator`、`__globals__`、`sys._getframe`、`ctypes`、metaclass/`__set_name__`、可变默认、动态 import 变体…）。saga 是实证：18 轮，每轮在上轮最新代码里找到新形态。

**我们真正落到的收敛动作**：
1. **whitelist，非 blacklist**，对任何开放攻击面（`errors` 用法：只许 6 好形态、拒其余——无需枚举 `__imul__` 等）。
2. **closed-world**，非「禁坏形态」（只放行有限语句/attr/import 集；审*整个模块顶层*、不只函数）。
3. **让 checker COMPUTE 覆盖集并自强制**（pin-all，非手列「123 可达 helper」——对抗审下手工枚举*永远*不完整；round-9 的手列被证伪）。
4. **pin 必须到 runtime 消费点**、不只 gate（C6/B1 → `certified_artifact_contract.py` 锚模式；#9a-A 时序旁路）。
5. **执行型 canary** 补 AST/sha 抓不到的正确性属性（空矩形 off-by-one）。
6. **decorator、「最后绑定胜」、method resolution**——任何「checker 解析的符号 ≠ runtime 实际绑定/调用的符号」的情形都是洞（`ast.get_source_segment` 排除 decorator；类最后绑定胜）。
7. **`ast.walk` 证明「出现」、不证明「可达/生效」**——需 live-statement/dominance 检查、非存在性。

**诚实天花板**：自检门**无法递归证明自身完整性**（checker 自己的注释承认）。目标*不是*「掏空不可能」（不可达）——是「把攻击面压到最显眼的残余 + 人工 clean-review」。关键区分：**静默（无 diff）必须关；必须改-checker（留显眼 diff）是可接受残余。**

---

## 7. 三类已接受残余（owner 裁定）

这些是诚实、刻意不关的洞。新工程师须知它们是*已知且已接受*、非疏漏。三者共享同一兜底：**源文件被 source-sha 逐字节钉 → 改它逼一次 freeze-ritual reseal → 显眼 diff → owner 仓库外人工 clean-review。**

1. **F —— import-time 执行完整性（#5-F）。** import-time 图灵完备；resolver 得匹配 CPython 全部 import machinery，而非-import 的 import-time 副作用（metaclass/`__set_name__`/descriptor、可变默认 mutation、动态 import 形态）无界。单列专线（§8）。round-12 walker 留作 best-effort。
2. **checker-self。** checker 检查自己，但能 reseal 的维护者能掏空它；只有 runtime 锚的 callee 枚举抓最坏形态，「掏空整个 checker」终究要改 checker = 显眼。分支 `_check_close_kernel_checker_self_binding()` 仍努力查 top-level closed-world / required tuple floor / callee definitions / main live calls / 自检 preflight shape（`git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:4014-4065`），但这不是数学自证。
3. **A4 dynamic-reflection rebind**（owner 2026-07-02 裁定）。经 `__globals__`/`f_globals`/`sys.modules[__name__].witness=`/等重绑 witness 名是不收敛黑名单；witness 函数已被 source-sha 逐字节钉，故同显眼-diff 类。round-18 best-effort 加固已知形态、但*不*把 A4 完整闭合当 release blocker。

**新工程师应重判的开放问题**：「byte-pinned 源 + 人工 clean-review」对这三类是*足够*兜底、还是应换法关掉其一（如 #1 的 option (B)：最小化 close-kernel TCB 的 import-time 执行以缩攻击面、而非巡逻它）？owner 在时间压力和一个特定威胁模型下接受了残余；那是判断、非定理。

---

## 8. F 为何单列（#5-F）及其 scope

来源：harness note `pr2-5-F-line-import-time-integrity-schedule`。

**理由**：11→12 每轮外审都在最新 walker 代码里找到新的 import-time 逃逸形态；import-time 对能 reseal 的维护者是图灵完备执行面 → 枚举不可能、round-N 迭代收益递减。为不让它永远卡住*结构*门 merge，owner（option 1）把它拉成专线、结构上紧邻 **#1（最小 TCB 闭包）**——它本质是 #1 的 import-time 子 scope。

**scope（三部分）**：
1. **import-machinery 完整性（有界）**：resolver 须匹配真 CPython 解析——所有 `SOURCE_SUFFIXES`（`.py`/`.pyw`）+ `EXTENSION_SUFFIXES`（`.pyd`/`.so`）+ bytecode + namespace 包 + `__init__` 链 + 相对 import + re-export；first-party 检测须含 `scripts.*`/任意项目包（当前只 `src.*`）。
2. **dynamic-import 完整性（有界）**：封所有 import-time 动态加载（`importlib.import_module`/util/machinery、`__import__`、`__dict__` subscript、getattr、`spec_from_file_location`、`SourceFileLoader`、`runpy`、`pkgutil`、`imp`、exec 的 path）。
3. **非-import 的 import-time 副作用（开放，需设计 spike）**：metaclass/`__init_subclass__`/`__set_name__`/descriptor、可变默认/类属性/模块容器 mutation、decorator 引用的 floored-function 行为被 reseal 改变。**AST shape 扫描无法枚举** → 一个设计 spike 选其一：(A) 追到完整；(B) 重构以*最小化* close-kernel TCB 的 import-time 执行（缩攻击面）；(C) 接受为残余 + V99 whole-file floor + 人工 reseal 审查 + 诚实边界。

**排期**：纵深防御、**不在 P1.2 release 关键路径上**（release 是 owner 仓库外人工计数）。Parts 1+2（有界）进/先于 #1；part 3 是 #1 内/后的设计 spike。

---

## 9. reseal freeze-ritual 连锁（不能弄错的机制）

来源：`pr2-5-seal-frontier-gate-landed`、`p1-2-fix-1-close-kernel-crlf`、`data-file-semantic-floor-runtime-anchor`、`pathspec-must-cover-full-reseal-set`、`close-kernel-sealed-lint-v99-reseal-re-export-patch-ruff-f401`。

编辑任何 V99-sealed close-kernel 文件都触发 freeze-ritual，一组*联动*更新必须全一致、否则 CI 漂移 / gate 失败：
- **3 个 runtime close-kernel 文件**（`exact_campaign.py`、`pr2_l0_micro_verifier_core.py`、`pr2_l0_true_verifier_child.py`）是 **V99 whole-file 楼面**——blob OID 在 round 3–18 冻于 `2f55bc65 / af276679 / da326456`。任何字节改动重钉楼面。
- **`certified_artifact_contract.py`** 是 runtime 信任锚、也在 V99 楼面（#8-B）；它带 runtime-消费的 pin（`LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256`、`LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS`）。⚠ 分歧（required paths 范围）：当前 main 只 required manifest+checker（`certified_artifact_contract.py:24`）；分支 round-18 扩到 manifest+allowlist+checker + protected callees（`git show 9bbb3a6:src/search/certified_artifact_contract.py:26-55`）。
- **checker 里逐符号 source-sha**（`CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH`；须覆盖 decorator——从 `min(decorator.lineno)` 起）。⚠ 行号：main 上此常量含 `certified_artifact_contract.py` 见 `check_p1_2_proof_obligations.py:3926`；分支见 `git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:12274`。round-10 起改为 pin 全部 def/class/method/constant，新增 symbol 不 pin 就红（`git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:9281-9295`）。
- **obligations 语义投影 digest**（`data/proof_obligations/p1_2_proof_obligations.json`），排除 sink `source_sha256` 以避自引用环。分支 manifest 顶层 `semantic_projection_sha256` 在 `git show 9bbb3a6:data/proof_obligations/p1_2_proof_obligations.json:7`；checker closed-world 校验 extra/missing fields `git show 9bbb3a6:scripts/check_p1_2_proof_obligations.py:3054-3075`；runtime 也校验 digest `git show 9bbb3a6:src/search/certified_artifact_contract.py:174-182`。
- **`strong_status_write_allowlist.json`**——整字节 floor（sha + size），条目跟踪 `STATE_KEYS={final_result, final_status, last_stop_reason, terminal_frontier_evidence}`（`declare_mode` *不*在 STATE_KEYS，故它不拿 allowlist 条目）。
- **checker 自钉 sha**——*最后*算、**只 LF**（`git show HEAD:<f> | sha256`，绝不 Python `write_text`）。
- **cert sink 注册**——`certified_artifact_contract.py` 是注册的 close-kernel sink（round-15 修）。分支 obligations：`certified_artifact_contract.py` sink 见 `git show 9bbb3a6:data/proof_obligations/p1_2_proof_obligations.json:973-981`；checker 自身也登记为 sink 见 `git show 9bbb3a6:data/proof_obligations/p1_2_proof_obligations.json:939-947`。

**真花过时间的坑**：CRLF/LF 自钉不符（§5.4）；给广泛消费的 tuple/常量加元素（`LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS` 2→3）会破坏所有 unpack 点（`test_p1_2_close_kernel_runtime_guard.py` 7 测试）——**先 grep 所有 unpack/index 点、且永远跑 full preflight**，因为 codex 的 targeted `-k` 跑漏跨文件回归；sealed-file 编辑会触发 ruff F401/re-export reseal churn。

---

## 10. PR2 剩余项 —— 内容 + 推荐序（带细节）

（完整状态表在 §2；此处给 #2/#3/#1/#9b/#9c/#7 + deferred resume-envelope 的实质。来源 `pr2b-landed-pr2-remaining-status-20260628`、`p1-2-resume-state-20260621.md:36`。注意 #8/#9a 已合 main;#5 close-kernel 写作时在分支 round-18、后续已于 `6e06922` 合入 main。）

- **#2（受控 loader 最小快照 + fd）**：当前快照扫全 `src/`/`scripts/`；需变成最小、fd-based 快照。partial。
- **#3（B3 fd-held read-once 全程）**：当前是 path re-read（re-open）而非单 fd 持有 read-once——一个 TOCTOU 窗口。partial。与 #2 强相关。
- **#1（L0/L1 最小 TCB 闭包）**：最大项——快照仍扫全 `src/`，child 仍 import 项目域模块（`from src.search…`），故不是设计要的「最小 TCB 闭包」。吸收 #5-F parts 1+2（import-machinery + dynamic-import 完整性）和 round-9 deferred 的 sha-sealed verifier 模块（`candidate_proof_replay`/`certified_frontier`/`terminal_fixed_witness_verifier`——这些在 3 文件外、由 V99 whole-file 楼面 + 人审守；更广的「sha-only 模块 vs re-sha 对手」问题显式 deferred 到这里）。huge。
- **#9b（OS 级写隔离）**：Linux uid namespace / seccomp、Windows 写隔离——全 pending。设计原则是写门应*被架构*移除（L1 物理上无 fd/OS 权限写进 certified 路径），非靠 `inspect.stack`/env-token（那是「假保护」）。greenfield。
- **#9c（原生 `.pyd`/`.so` TOCTOU）**：best-effort 重 hash 已有（`_RehashingExtensionFileLoader`）；残余声明 NAMED-TCB。随 #9b。partial。
- **#7（生产 `certify` 入口）**：operational-chain gap（`p1-2-supervisor-production-entry-gap-20260626`，CHANGELOG line 10）已于 2026-07-04 落地为 `scripts/run_supervisor_seal.py`（commit `349c56c`）：独立命令 resume 已提交的 `CANDIDATE_PROPOSED` proposal → 校验 proposal-ready marker 前置 → 调 `ExactCampaign.supervisor_seal()`（真实隔离 L0 复验）→ 按成功/异常退出码。`main.py` 仍停在 `CANDIDATE_PROPOSED`；该入口存在不推导 P1.2 closed / 可发布 / P1.3 allowed。
- **Deferred 跨项发现 —— resume-envelope（`pr2-resume-envelope-deferred-finding`；仅 Opus 版展开）**：GPT Pro 会话 05（1/5）发现 parent durable mint 无检查地复制 producer proposal 的非-proof *envelope* 字段（`created_at`、`schema_version`、`master_domain_contract`、`campaign_hours`、`reset_reason`）。对手可把 `created_at` 设成非法值 → durable state 过终态门但**过不了自己的 resume validator** = 自相矛盾证书（`exact_campaign.py:~2399-2402` 拒它）。**判真但对 #5 越界**（它是*不同*不变量——checkpoint-envelope 自洽、非 declare_mode/穷尽 soundness、也非假-proof）。owner 裁定：**deferred 到 #2/#3 envelope 硬化或新项。** 做时：seal 前 fail-closed 校验 producer envelope 字段；注意别过度扩 child TCB（会话 05 的 probe-copy 修法把 `validate_exact_campaign_resume_state` + `compute_exact_artifact_hashes` import 进 child，逆着 #5 缩 child 的目标）；验证法 = 篡改 `created_at` + 重算 sha → seal 应被 REJECTED。

**推荐序（restated）**：#8 → #9a → 定 #6（大概率接受 source-hash 为主防线 = 跳）→ #5（B2 枚举）+ #2/#3 → #1（+ #5-F parts 1+2）→ #9b（+#9c）。#8/#9a 已落 main；#7 已于 2026-07-04 落地；#5 close-kernel 已 `6e06922` 合入 main、不再等 relay（#5 的 B2 独立枚举部分仍未做,与其余深化项同为未排期 backlog）。

---

## 11. 诚实的局限、死路、反转、开放问题

- **P1.2 与所有 PR2 工作无关地 release-blocked。** gate 是 `blocked_manual_review_count`、`next_allowed=false`——owner 仓库外人工 clean-review 计数。任何 PR2 硬化都翻不动它；PR2 让将来某次 release *可信*、不*授予*一次。别把「checker 绿 / preflight 过 / 方法存在 / 入口落地」当「certified/released」。
- **我们过早宣布收敛且错了。** round-8/9「123/123、收敛」判断（`close-kernel-block-convergence-trend-20260630`）被 round 10–14 证伪。对当前任何「零结构 block」断言持同样怀疑。
- **18 轮黑名单追逐本身就是警世故事**（`close-kernel-ast-checker-design-lessons`）：对反射面逐形态黑名单收益递减；早识别、转 whitelist/closed-world/compute-coverage，或把无界部分单列（如 F）。我们是花大代价学会的。
- **三类已接受残余**（F / checker-self / A4 dynamic reflection）*未关*——靠显眼-diff + 人审。该兜底是否足够是特定威胁模型下的判断、可重审。
- **钉进的 floor manifest 是占位**——生产需在 CachyOS + Py3.13 重生成 + 审 + reseal（§4 deploy-TODO）。本机生不了。
- **codex「假 done」隐患**：codex 报过「done」（round-13、round-14）却没真写代码 / 在 transport-layer 假失败后；**codex 报 done 后永远核 `git diff`。** 且**绝不派 codex 在同一 worktree 并发自实现**（round-15 并发编辑事故）。
- **full preflight 对 certified-core 改动是非协商的。**「审 CLEAN」≠「full 绿」——PR1 上证过、PR2 上反复证；targeted/`-k` 跑漏跨文件回归和只有 full checker 单跑 + full preflight 才暴露的 unregistered-sink 错误。
- **trust onion 永不见底。** 对抗审总能再剥一层；「零发现」非收敛判据。收敛 = 画 + 冻一条 TCB 线、在其上修、让新发现落其下（声明信任）或成为 done-criteria 实例（`p1-2-review-converged-tcb-start-p1-3`）。
- **给新工程师的开放问题（也是找你来的原因）**：我们对*能 reseal 的维护者*硬化 checker 18 轮。鉴于 release gate 本就是人工计数，这是否是值得花这么多的正确威胁模型？#1 的 option (B)——架构上最小化 close-kernel TCB 的 import-time 执行——会否*溶解*掉大部分 F/A4 而非巡逻它们？这些正是我们在圈内可能判错的 call。

**Codex 版另列的诚实接手点**（并集补充）：round-18 三类 residual 边界是否画对，尤其 A4 是否真的只能靠显眼 witness diff + clean-review；#5-F 是否被过早单列（若能提出有限、可验证、不打地鼠的 import-time closure 模型 = 实质突破）；`certified_artifact_contract.py` runtime anchor 是否足以把静默 data-file 信道从「只改 JSON」变成「必须动 runtime/checker/source floor」；`pr2-5-domain-frontier-gate` 未合 main，当前主线代码只能证 #8/#9a 已合、别拿分支 `9bbb3a6` 的 file:line 当 main 状态。（2026-07-04 注:已 `6e06922` 合入 main,此条转史料;「file:line 会漂移、以当前源码为准」的警告仍然成立。）

---

## 12. 可追溯性索引

- 分支 `pr2-5-domain-frontier-gate` @ `9bbb3a6`（当时未合并，round-18;后续 `6e06922` 合入 main）；当时 `main` @ `b35e5f9`（PR2 #8/#9a 合于 `099f5a3`，PR #2）；PR1 @ `b085a75`。
- 分支 #5 commit 链：`2ec8954`（+ Opus 版 `2c258c6`）→ `4410b6a`→`dbd1d72`→`b6d41c6`→`cce5dd5`→（round-3：⚠ Codex 版 `7a6cd8c`/`eb93637`）→`44c8da6`→`2fa42b9`→`66511ce`→`9c06ab8`→`ad73e4f`/`dbe27c0`→`c115f31`→`7851c1e`→`a5a5e64`→`adeddc5`→`8714ee7`→`504b3f8`→`d1a59ad`→`1b90285`→`c96a601`→`2ca6864`→`9bbb3a6`。（⚠ 完整拓扑以 `git log --oneline main..pr2-5-domain-frontier-gate` 为准。）
- #8/#9a 组成：`be5ed93`（#8）、`507f213`（#9a）、`0657872`（GPT Pro 硬化）、`ec7dc52`（deploy-pending 标记）。PR2-b：`69980b3`+`592ea13`（仅 Opus 版给）。
- checker：`scripts/check_p1_2_proof_obligations.py`（分支 ⚠ 行数：Opus ~12,235 / Codex ≥12,647）。
- runtime 文件：`src/search/{exact_campaign,pr2_l0_micro_verifier_core,pr2_l0_true_verifier_child}.py`（blob `2f55bc65/af276679/da326456`）。关键行：`exact_campaign.py:3608-3616`（mark_campaign_stopped）、`run_l0_supervisor_seal ~294`、`_supervisor_certified_transition_violation_l0 ~838`、`exact_campaign._supervisor_certified_transition_violation ~1880`、`pr2_l0_true_verifier_child ~403-417`、`exact_campaign.py:~2399-2402`（resume validator）。
- runtime 锚：`src/search/certified_artifact_contract.py`（`locked_p1_2_close_kernel_violation` @ 533 / Codex 533-593；`LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS` @ 26；`LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256` @ 31；`_locked_checker_top_level_closed_world_violation` @ 491；main 隔离子进程 @ 117/129；main required @ 24；runtime digest 校验 @ 174-182）。
- 数据楼面：`data/proof_obligations/p1_2_proof_obligations.json`（main deploy-pending @ 855；分支 semantic_projection @ 7、cert-contract sink @ 973-981、checker-self sink @ 939-947）、`data/…/strong_status_write_allowlist.json`。
- 设计文档：`docs/项目说明/p1_2_supervisor_detailed_design.md`。权威不变量：`PROJECT_LOCK.md`（F-*/PCR-*/CUT-* 条款，边界 @ :130）；`NAV_MAP.md:23`；`CHANGELOG.md:7`。
- harness RESUME：`p1-2-resume-state-20260621.md`（:12 round-14→15 判定、:14 runtime 三文件字节未动、:36 剩余项表）。
- 全部 cc_memory id 见 §0.1；读任一：`python cc_memory/mem.py read <id> --body`。


---

# 第 5 章 · 不变量、坑、工具 / 工作流

> 本章是给另一台机器、从零接手的新工程师的唯一上下文，目标是完整 > 简洁：把《明日方舟：终末地》certified-exact 求解器交接时最容易被踩到的硬不变量、封存/重封坑、门禁与工具流全部摆出来。它是**史料 + 决策记录**，不是照搬旧结论的命令。凡"代码做 X，但文档说 Y"处，是已核实的真实分歧，不是建议。两份独立史料（一份 Opus、一份 Codex）在事实、行号、引用上有出入处，一律用 **⚠一版称…另一版称…** 显式标注、保留全部信息，供终审裁定，不擅自取舍。
>
> 所有路径相对 `C:\claude pj\zmd_pj`。cc_memory 条目读法：`python cc_memory/mem.py read <id> --body`。

---

## 0. 贯穿全章的心智模型 + 证据边界

几乎所有下述不变量都在保护**同一条边界**：`certified_exact`（唯一可产出证明材料的路径） vs `exploratory`（只作启发式引导、绝不得升格为证据）。门禁机制、frozen hash、byte floor、strict JSON、env allowlist、forbidden paths 全是这条边界上分层的 **fail-closed** 防线。当你分不清一个改动是"只是管道"还是"触及 certified core"时，一律当作触及 core，先读 `PROJECT_LOCK.md`——它是权威真值源；任何其他文档（README、历史文档、生成导出、旧记忆）与它冲突时，`PROJECT_LOCK.md` 胜出（`CLAUDE.md:34-38`, `PROJECT_LOCK.md:1-6`）。

- **⚠ PROJECT_LOCK.md 体量：** 一版（Opus）称 "~127 KB"；另一版即项目 `CLAUDE.md` 原文称 "~106 KB"；Codex 版未给体量。无论如何它是密集的 `F-*` / `PCR-*` / `CUT-*` fail-closed 子句集合。

**§1–§3 反复出现的元教训：门禁时的检查 (gate-time check) 不等于运行时保证 (runtime guarantee)。** 一次次地，pin 被放进 checker，但 runtime 消费点从未重读它，留下 TOCTOU 时间窗（见 cc_memory `close-kernel-block-convergence-trend-20260630`，以及 vnext claim-guard 卡 `close-kernel-pin-reaches-runtime`）。始终保持这个怀疑。

**证据边界（务必先读）：** 当前主工作树 `C:\claude pj\zmd_pj` 的 `HEAD` 是 `b35e5f9`。PR2 #5 close-kernel 的最新隔离工作树在 `C:\claude pj\zmd_pj\.claude\worktrees\pr2-5-round10`，其 `HEAD` 是 `9bbb3a6`（round-18）。大量 round-by-round close-kernel 史料来自这个隔离工作树和 harness resume 锚 `C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory\p1-2-resume-state-20260621.md`（顶部 `▶▶▶` 段是最新）——**这不代表当前主线已等价包含全部 round-18 状态**。任何"round-18 已修"的说法都要先确认目标 clone/branch 是否含这些 commit。

**颜色一切的提醒：** 即便全绿 preflight + CI 也**不**铸公开 CERTIFIED 结果。`main.py` 停在 `CANDIDATE_PROPOSED`；只有 supervisor seal 铸 durable terminal status、只有中心 publisher 公开它；P1.2 被 release-block 在 owner 侧、仓库外、任何门禁都满足不了的人工 clean-review 计数后面。

---

## 1. Frozen artifacts 与 freeze-ritual

certified-exact 路径把若干输入文件当作冻结源头，进入 preflight hash/size 合约和 runtime certified artifact contract 的证明输入——不是普通可编辑配置。人手改这些文件却不同步更新证明链，会让求解器实际证明的是"另一个问题实例"。

### 冻结文件与 hash 存放位置
preflight 硬钉四个普通冻结输入的精确字节 SHA256，在 `scripts/preflight_gate.py:37-44` 的 `FROZEN_ARTIFACTS`（Opus 注：hash 为大写 hex）：

- `rules/canonical_rules.json` — recipes、targets、commodity roles、空矩形 admissibility
- `rules/preprocess_plan.json` — **additive-only** cycle groups / utility operations；绝不得携带 recipes/targets/commodity roles，context builder 见到这些 key 会 fail closed。（`preprocess_plan.json` 是 additive/preprocessing 的 source of truth，改它属 freeze-ritual change——`PROJECT_LOCK.md:188-220`）
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

第五个大文件在 `EXTERNAL_FROZEN_ARTIFACTS` 单独钉住：`data/preprocessed/candidate_placements.json`，expected **45,774,305 字节**，SHA256（完整值见 `CLAUDE.md`：`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`）。
- **⚠ 行号：** Opus 称 `EXTERNAL_FROZEN_ARTIFACTS` 在 `:46-55`；Codex 称 `:46-54`。
- **⚠ hash 缩写大小写：** Opus 写 `A914BA63...C50C444B`（大写）；Codex 写 `a914...444b`（小写）——同一值的缩写。
- 它属于 certified 合约，但分发策略允许 lightweight checkout 省略它。存在时 preflight 校验精确字节；缺失时 certified run 必须在解算前用 `scripts/restore_external_artifacts.py` 恢复/校验。拐角修复前的 **45,773,799 字节** / SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` artifact 是 superseded、hash-incompatible；旧的 **53,594,995 字节** artifact 与 hash 不兼容——campaign resume 必须拒绝它。
- runtime 侧也把这些 frozen artifact 的 SHA/size 放进 certified artifact contract，避免只靠 preflight 静态检查：`src/search/certified_artifact_contract.py:96-105`（Codex 提供此行号）。

### 检查函数（Codex 提供，Opus 未给）
- `check_frozen_artifacts()` 在 `scripts/preflight_gate.py:238-263`：逐个读文件、算 SHA256、比对 expected；对 external artifact 还检查缺失是否符合策略。

### freeze ritual（编辑冻结文件不是免费 overlay）
编辑任一冻结文件是多步仪式，不是一行改动：
1. 重生成依赖产物（plan 喂 runtime operation profiles / binding utility slots——见 `preflight_gate.py:40` 的 `R6-F-01` 注释）。
2. 更新 `FROZEN_ARTIFACTS` 里的 pinned hash。
3. 重跑 gate。

`PROJECT_LOCK.md:515-523` 规定：exact boundary / runtime behavior / certified output 变化时要同步更新 lock/status/spec/tests，而不是只改一个 JSON。

### 被否决的替代方案
- **把 frozen artifacts 当普通配置自由 overlay** — 否决：会让 hash-bound proof 输入和人以为的规则输入分离，preflight/runtime 合约不再表达同一事实。
- **只改 expected hash 来"修复" mismatch** — 否决：hash mismatch 是症状不是证明失败本身；只有 semantic source-of-truth 的变化是有意且被审查时，才允许更新 expected hash，并重生成依赖产物、更新 lock/spec/test、重跑 gate。

### 残余边界
这个机制只能证明"当前钉住的字节没漂移"，**不能**证明 frozen input 的数学语义本身正确；语义仍需人审和上位规格。

---

## 2. Reseal 铁律（这里最容易丢一天）

certified core 有一道 close-kernel 第二门（`scripts/check_p1_2_proof_obligations.py`）按 SHA256 钉源文件。任何改动被钉文件都要 reseal（重算并重钉 hash）。reseal 路径有几个硬学来的陷阱。核心是：**说清算的是哪一份字节序列——working tree、index、还是 `HEAD` blob。混用会本地绿 / CI 红，或 checker 常量指向未提交字节。**

### 2a. LF-only sha，从 committed/index 字节算——不是工作树
仓库行尾是 LF：`.gitattributes` 有 `* text=auto eol=lf`（注释说明 hash-pinned/proof-sensitive 文件依赖工作树字节稳定），由 `scripts/check_line_endings.py` 执行（Opus 称它是 preflight 检查 `[9/18]`；`scripts/check_line_endings.py:1-2,16-23,77-99`，接入 preflight 在 `scripts/preflight_gate.py:495-497`；策略定义在 `data/line_ending_policy.json:1-26`）。pin 按 **LF 字节**计算。

- 用 `git show HEAD:<path> | sha256sum` 算 pin（读 committed LF 字节）——**不要**在可能是 CRLF 时 hash 工作树文件。
- **不要**在 Windows 上用 Python `Path.write_text()` / `json.dump()` 写 tracked 文件：它们发 CRLF，与 `eol=lf` 冲突。具体事故：codex 在 Windows reseal 产出 CRLF，checker 自钉在 CRLF 上算出的 sha（Opus 记为 `a9bfaac7`）不等于 LF-committed 版（Opus 记为 `6294c58a`）→ 本地过、CI 挂。修法：strip `\r` 归 LF 后重算自钉。正确做法 = 用 `Edit` / `open(..., newline="")` / 归一 CRLF→LF，pin sha 按 LF 算（`git show HEAD:<f> | sha256`）。见 cc_memory `p1-2-fix-1-close-kernel-crlf`、`pr2-5-seal-frontier-gate-landed`。
- 微妙点：`git show :<path>` 读 **index**，`git show HEAD:<path>` 读 **commit**，`--full` preflight 读 **working tree**——三者可能互不相同。resume 锚 `p1-2-resume-state-20260621.md:16` 记录 "`git show :path` 读 index 非工作树" 是重复踩的坑。

### 2b. pathspec 必须覆盖"完整一致集"
提交 reseal 时，显式 `git` pathspec 必须含新 pin 引用的**每一个**文件——包括别的会话动过的文件。PR2-b 事故（cc_memory `pathspec-must-cover-full-reseal-set`）：reseal 钉了 *新* 的 `src/search/exact_campaign.py`（**⚠** Opus 记新 sha `2b44f7cb`、旧为 `1aa393fb`；Codex 未给具体 sha），但提交 pathspec 漏掉了该文件，仓库树仍是旧版。本地 `--full`（读工作树）过；CI（读 committed 树）挂在 source-hash drift 上。**⚠ 修复 commit：** Opus 记为后续 commit `592ea13` 覆盖全部 10 个文件；Codex 未给 commit 号。教训："本地绿 ≠ 提交集自洽"；push 前对 staged paths、`git diff --cached --stat`、`git show HEAD:<file> | sha256` 逐个对账、确认每个被钉文件的 committed sha 等于其 pin。

### 2c. close-kernel 改动的完整 reseal 面
按 cc_memory `p1-2-fix-1-close-kernel-crlf`，certified-core 改动后 reseal 意味着以下全部：
- (A) **V99 floor**：更新 `check_p1_2_proof_obligations.py` 里的 `CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH`（见 §3）；新的 proof-bearing 文件要加进 `data/proof_obligations/p1_2_proof_obligations.json`（`close_kernel_contract.sink_files`，带分类）和 checker 的 V99 required 常量。
- (B) **strong-status allowlist**：`data/proof_obligations/strong_status_write_allowlist.json` 由整文件 `source_sha256` 钉；动过就重 hash 所有条目、注册任何新 strong-status 写点（checker `scripts/check_strong_status_write_allowlist.py`）。
- checker 的**自钉 (self-pin) 最后算**（它 hash 自己）。
- 相关坑：cc_memory `close-kernel-sealed-lint-v99-reseal-re-export-patch-ruff-f401` 记录一个特定陷阱——对 sealed 文件做 lint/ruff F401 修复会触发 reseal 级联。

### 当前状态/开放风险
项目已有 line-ending gate + preflight 兜底，但 **"index vs working-tree 的 reseal 操作细则"在 cc_memory 中尚无独立正式条目**，散在 harness resume 和事故条目中。做 close-kernel reseal 前应把 hash 来源写进自己的操作记录。

---

## 3. V99 whole-file source-sha floor + "runtime 文件字节永不移动"不变量

V99 whole-file floor 的核心经验：只钉 manifest 的某些语义字段、checker 的某些结构片段、或某个 gate 的局部 token 都**不够**——攻击/误改可以走"未 floor 的数据字段""runtime 没读到的 gate pin""checker 自己被 faithful reseal"三条路。V99 的方向是：把 proof-bearing sink inventory、critical gate files、source SHA floor、dependency-floor provenance、required paths 放进闭合集合，让"只缩 manifest / 只重封 checker"的变化变成显眼 diff。

### floor 结构（⚠ 行号两版不同——很可能因读的是不同 checkout：Opus 疑读某一版、Codex 明确读 round-18 隔离工作树 `pr2-5-round10`）

**Opus 版行号：**
- `CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH`：`scripts/check_p1_2_proof_obligations.py:3926-3987`，按整文件 LF SHA256 钉约 60 个源文件。
- `CLOSE_KERNEL_V99_REQUIRED_SINK_CLASSIFICATION_BY_PATH:3820-3880` — 每个 proof-bearing sink 及其分类（`p1_2_certified_path`、`p1_2_public_surface`、`p1_2_close_kernel`、`non_authoritative_projection`、`out_of_scope_future_phase3b`、`diagnostic_or_telemetry_non_authority`、`exploratory_or_heuristic_non_authority`）。
- `CLOSE_KERNEL_V99_REQUIRED_CRITICAL_GATE_FILES:3882-3904` — checkers、obligations JSON、dependency-floor manifest+generator、trust-anchor runtime 文件。
- `CLOSE_KERNEL_V99_STRUCTURAL_GATE_SOURCE_PATHS:3911-3924` — 额外做 AST 结构检查的文件。`:3906-3910` 注释：AST reachability scanner 是**冗余**第二层，**主**防线是整文件 source-hash floor。

**Codex 版行号（round-18 工作树）：**
- checker 不能递归证明自己源码、git history + human review 是边界、合法 floor reseal 会改 checker code 而非只改 manifest/gate data：`scripts/check_p1_2_proof_obligations.py:3784-3791`。
- required scan roots 和 required sink paths：`:3812-3881`。
- critical gate files（checker、strong_status allowlist、floor generator/manifest、proof obligations、`certified_surface.py`、`certified_artifact_contract.py` 等）：`:3882-3891`。
- required source SHA table 起始、说明 primary anti-drift defense 是 V99 source-hash floor：`:3907-3934`。
- proof obligations 侧 close-kernel manifest/floor：`data/proof_obligations/p1_2_proof_obligations.json:506-557` 和 `:753-858`。

### "3 个 close-kernel runtime 文件字节不动"不变量
在长期 close-kernel 硬化战役（round 3→18，仍在分支 `pr2-5-domain-frontier-gate` / 隔离工作树 `pr2-5-round10`，**未 merge 到 main**）中，操作铁律是：**真正执行 seal 路径的 runtime 文件其 git blob OID 每轮不变；只有 *checker* 和 *数据文件* 变。** 理由：一轮硬化应在不改行为的前提下收紧"未来不可信维护者"能做的事；runtime 字节若动了，就无法证明该保证与 runtime 正交。

三个 runtime 文件（Codex 明确列举）：
- `src/search/certified_artifact_contract.py`
- `src/search/pr2_l0_micro_verifier_core.py`
- `src/search/pr2_l0_true_verifier_child.py`

**⚠ 三文件 blob OID 严重出入（供终审裁定）：**
- **Codex 版**（在 round-18 工作树 `HEAD=9bbb3a6` 实际 git 读）：三 runtime 文件 blob = `ef3987d…` / `af276679…` / `da326456…`；此外 checker = `f1d24ada…`，`exact_campaign.py` = `2f55bc65…`。
- **Opus 版**（引 resume 锚原文）："3 runtime 文件字节全程未动 (blob `2f55bc65` / `af276679` / `da326456`)"，并把 runtime 文件模糊描述为 `pr2_l0_micro_verifier_core.py` + `pr2_l0_true_verifier_child.py` + trust anchor `certified_artifact_contract.py` / `exact_campaign.py`。
- **分歧点**：Opus/resume 锚把 `2f55bc65` 列为"3 runtime 文件之一"，但 Codex 的 live git 读显示 `2f55bc65` 是 **`exact_campaign.py`** 的 blob、而三 runtime 文件的第一个应是 `certified_artifact_contract.py = ef3987d`。即 resume 锚记录的 blob 集与 Codex 现读不一致（`af276679`/`da326456` 两者一致，第三个 `2f55bc65` vs `ef3987d` 不一致）。终审需在目标 checkout 上 `git ls-tree` 复核。

`certified_artifact_contract.py` 还含 subprocess isolation 约束 `-I -S -B -X pycache_prefix`（`src/search/certified_artifact_contract.py:91-153`；locked close-kernel manifest/checker/isolation contract 在 `:24-27,91-168`）。早一轮 #8/#9a 的关键教训（cc_memory `pr2-8-9a-hardened-landed-099f5a3`）："gate pin != runtime pin"；#8-A 用 `-I -S -B -X pycache_prefix` 隔离 checker 子进程（堵父进程 sitecustomize 污染信任锚）；#8-B 把 `certified_artifact_contract.py` 纳入 V99 源码 sha 楼面（删 skip 让它成信任锚就必须钉）；#9a-A 增 L0 runtime byte-pin manifest + 删 `_generate_default_dependency_floor_manifest`（堵 gate 过后 mint 前换 manifest 用未审 floor 的时序旁路）。

### round-by-round 史料（合并两版；commit 号并集）
- **PR2 #5 初始缺口**（cc_memory `pr2-5-seal-frontier-gate-landed`）：L0 child `_verify_supervisor_domain` 升格提案为 CERTIFIED 时漏改 `declare_mode` + `last_stop_reason`（只改 `final_status`）→ `has_terminal_full_frontier_certified_evidence` 恒 False → 全前沿穷尽 + 最优候选 + canonical 域校验在 durable seal 路径静默跳过 → 恶意 producer 可对切片/非穷尽域铸 false durable CERTIFIED。GPT Pro panel 还挖出 parent mint 不归一 `declare_mode`、AST pin 太松。此轮同时暴露 CRLF reseal 坑。早期落地 commit（Opus 源列表）：`2ec8954`、`2c258c6`、`4410b6a`、`dbd1d72`、`b6d41c6`、`cce5dd5` 等。
- **round8 / round9**：`c115f31`（round-8，修 5 类，空矩形 off-by-one 用执行型 canary）、`7851c1e`（round-9，穷举 pin 3 文件内 123 可达 cert helper、re-probe 123/123 收敛）。harness `p1-2-resume-state-20260621.md:18` 开始强调 runtime 三文件 blob unchanged 的验证。
- **round10**：`a5a5e64` — 改为 close-kernel full-pin closure + closed-world + import allowlist；"pin all" 是因为逐个补漏洞不收敛（cc_memory `pr2-5-round10-11-12-fspinout`）。
- **round11**：`adeddc5` — def-time/import-time hardening + verifier canaries，但外审仍挖出 9 个 block。结论：import-time 执行面和 Python 动态绑定面很难靠枚举坏形态穷尽。
- **round12**：`8714ee7` — robust import-time closure walker。F-form/import-time integrity 仍不收敛 → owner 把 F 类独立为 **#5-F**，结构门保留 best-effort（见 harness `pr2-5-F-line-import-time-integrity-schedule`）。
- **round13**：`504b3f8` — close-kernel structural-gate soundness。此时发现 **silent data-file channel**（cc_memory `data-file-semantic-floor-runtime-anchor`）：proof obligations / strong-status allowlist 中某些语义字段（`title`/`v_findings`/`evidence_paths`；allowlist 的 prose 字段）没被 whole-file floor 覆盖，checker 仍可能绿。修法：整字节 floor + 把 semantic-projection digest 拉到 **runtime** 信任锚（`certified_artifact_contract.py` 的 `LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256`，由 campaign runtime 的 `locked_p1_2_close_kernel_violation()` 消费），而非只把 digest 放可自我重封的 checker 常量里。**Opus 记的关联坑**：拓宽一个共享 pinned 元组/常量（如 `LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS` 从 2→3 元素）会打断 `test_p1_2_close_kernel_runtime_guard.py` 里 7 处 unpack 站点——codex 只跑目标测试漏掉，**只有全量 preflight 抓到**。改共享常量前 grep 所有 unpack/index 站点；数据文件/共享常量改动需全量跑。
- **round14**：`d1a59ad` — structural whitelist hardening。仍不 sound，因为白名单原则只覆盖了 `errors` Name，A3/A4/checker-self 仍像黑名单（cc_memory `gate-self-check-whitelist-not-blacklist`、`pr2-5-round14-11th-review-block-round15`）。第 11 轮 6-panel 收敛出 3 类 block：manifest top-level silent fields、runtime gut + faithful reseal、checker-self main/callee late rebind。
- **round15**：`1b90285` — close-kernel 第二道门硬化，但 harness `p1-2-resume-state-20260621.md:14` 记录又发现 globals main 等残余。
- **round16**：`c96a601` — 收敛 close-kernel 闭集，codex 前置复审挖出 round15 的 3 个 block。
- **round17**：`2ca6864` — 对 A4 收敛，witness 体 blanket 禁 namespace/exec/reflection 面。
- **round18**：`9bbb3a6` — A4 动态反射重绑 best-effort 加固，并把一部分 A4 动态反射残余归为**已裁定残余**。不是"Python 动态反射已被数学封死"，而是"结构门已把可封部分推进到更显眼、更小的残余边界"。
- **⚠ commit `b085a75`** 仅出现在 Opus 的源引用列表中，两版正文均未说明其归属轮次；终审可忽略或按需追溯。

### 根本能力边界（owner 已裁定，勿盲目重打官司）
这是整个 certified surface 里最重要的诚实限制（cc_memory `close-kernel-ast-pin-structural-vs-semantic-boundary`、`close-kernel-ast-checker-design-lessons`）：
- AST/source-sha "第二门"能保护**结构**（durable-writer chokepoint 整个 body 被钉、entry-point 可达性、gate-result 数据流、closed-world entry/method body），**不能**保护**证明数学的正确性**——叶子 helper 的内部数学只由 source-sha floor + frozen-artifact hash + 人工重钉审查守。
- 对图灵完备语言，逐形态黑名单永不收敛。经验证明：round 13→18 不断发现 `errors` accumulator、member-write reflection、name-shadowing（`exec`、`operator.setitem(globals(),...)`、`witness.__globals__[...]=`、`sys.modules[__name__].witness=` …）的新绕过形态。收敛答案是**白名单（"只许这些好形态、其余全拒"），不是黑名单**（cc_memory `gate-self-check-whitelist-not-blacklist`）。checker 也不能递归证明自己（`check_p1_2_proof_obligations.py:3784-3791` 明说 checker 源码 + human review 是 TCB 边界）。
- **owner 裁定（Opus 记 2026-07-02）**：剩余 dynamic-reflection A4 rebind 形态**接受为残余**——与 (a) import-time 执行完整性（拆为专门线 PR2 #5-F）、(b) "你必须改 checker 本身"残余同类。三者只由**显眼 diff + 人工 clean-review**兜底，因为 witness 函数被 source-sha 钉死（改它 = 显眼 diff）。目标从来不是密码学不可能，而是把攻击面压到"必须产出显眼 checker/runtime diff"、并封死每一条**静默**信道（纯数据文件篡改）。

### 被否决的替代方案（合并）
- 只 pin manifest 不 pin runtime 消费点（#9a 教训：gate 看见的 pin ≠ runtime 真正消费的 bytes）。
- 只把 digest 放 checker 常量（checker 可 faithful reseal，自引用不等于外部信任根）。
- 用黑名单枚举 `errors.clear()`、late rebind、decorator、`exec`、reflection 等坏形态（追不完）。
- 让 checker 递归证明自己。

### 当前状态/残余边界
round-18 把很多 close-kernel 结构面推成 sealed floor，但 P1.2 仍非 formally closed：`scripts/run_supervisor_seal.py` 已补上独立生产入口，`main.py` 仍停在 `CANDIDATE_PROPOSED`，checker/local tests/入口落地都不是 release closure。**Opus 补**：该分支 HEAD 在最后 resume 更新时为 `9bbb3a6`（round-18），第 12 轮 GPT-Pro relay 已 staged、等 owner 跑。

---

## 4. Strict JSON（`src/io/strict_json.py`）——任何喂 proof 的路径都用它

stdlib `json.loads` 有两个对 proof artifact 危险的默认行为：重复 key last-write-wins、接受非有限常量 `NaN`/`Infinity`/`-Infinity`。在按精确字节定义含义的文件里，这会让"人读"和"程序读"分歧，或让非有限数进入几何/优化逻辑。项目把 proof-relevant JSON 入口收敛到 `src/io/strict_json.py`（`:1-6` 说明 stdlib 行为不安全）。

**Codex 版函数/行号：**
- `_reject_duplicate_json_keys()` `:17-23` — 用 `object_pairs_hook` 检测重复 key、发现同名就抛错。
- `_reject_json_constant()` `:26-27` — 拒绝 `NaN`/`Infinity`/`-Infinity`。
- `_parse_json_float()` `:30-47` — 检查 parse 后 float/Decimal 是否 finite，防 `1e400` 溢出为非有限数。
- `loads_strict_json()` `:51-67` — 组合 `object_pairs_hook`/`parse_constant`/`parse_float`。
- 文件入口 `load_strict_json_file()` / `load_strict_json_path()` `:70-79`。

**Opus 版函数命名（⚠ 与 Codex 有出入）：**
- 提供 `loads_strict_json(text, *, exact_decimal=False)` 和 `load_strict_json(path, ...)`；拒绝重复 key（`_reject_duplicate_json_keys`）与非有限数（`parse_constant` 抛错、floats 用 `math.isfinite` 检查）。
- `exact_decimal=True`（经 `load_strict_json_exact_decimal`）把 float token 解析为 `Decimal`，使下游 exact-rational 代码消费原始十进制词素而非二进制浮点近似。
- **分歧**：Opus 称文件入口/Decimal 入口函数名是 `load_strict_json` / `load_strict_json_exact_decimal`；Codex 称是 `load_strict_json_file` / `load_strict_json_path`。终审以目标 checkout 源码为准。

规则（项目 `CLAUDE.md`；`PROJECT_LOCK.md:285-288` 也写入 lock）：任何喂 binding/master/preprocess proof 输入的路径用这个共享 strict 入口、不用裸 `json.loads`；proof 路径的 writers 发 `allow_nan=False`。（Opus 注：loaders 已直接核实；"writers 发 `allow_nan=False`"是 `CLAUDE.md` 声明，动某个 writer 时逐点确认。）cc_memory 无独立"strict_json 事故"条目；相关史料在 L0 micro-verifier 设计条目 `p1-2-supervisor-l0-l1-design-meeting-20260623`（L0 小核不能以"小"为由削弱已有 fail-closed JSON gate）。若发现某 proof path 直接调 stdlib JSON，先判断是否已被上层 strict parser 包裹；没有 = 值得审的风险。

---

## 5. Forbidden staged paths + `src/ai_accel` proof 隔离 + exploratory 泄漏扫描

由 preflight 执行，目的是把"源码/规则/测试"和"运行生成产物"边界钉死。

### Forbidden staged paths（`scripts/preflight_gate.py:57-62`；`check_forbidden_staged_paths()` `:289-297`）
永不提交生成的 proof/blueprint 输出：
- `data/checkpoints/`
- `data/blueprints/optimal_blueprint.json`
- `data/solutions/final_solution.json`
- `data/solutions/certified_delivery_manifest.json`

（项目入口重复提醒：`AGENTS.md:368-372`, `CLAUDE.md:260-264`。被否决方案："先提交生成物保存、之后清理"——preflight 不留豁免。）

### `src/ai_accel` AI-safety 合约（`:64-78`；`check_ai_safety_contract()` `:300-327`）
`src/ai_accel`（特征提取 / replay scheduling）**绝不得触及 proof 路径**。`AI_MODULE_ROOT = "src/ai_accel"`；`AI_FORBIDDEN_PATH_REFS` = `data/checkpoints | data/solutions | data/blueprints`；`AI_FORBIDDEN_FILE_OPS` 标记该模块内出现的 `open(`、`write_text(`、`write_bytes(`、`Path(`、`pathlib`、`shutil`。即 `ai_accel` 可计算、绝不得写入或引用 proof 输出。被否决方案："AI accel 只读一下 proof 输出不算接入"——无灰区豁免。

### exact/exploratory 泄漏扫描（Opus 提供；Codex 未单列）
`EXPLORATORY_LEAK_PATTERNS`（`:80-87`）阻止 `"50 power poles"`、`"10 protocol storage"`、`exploratory_optional_caps` 等字符串出现在 `EXACT_MODE_FILES`（`:89-96`）列出的 certified 文件里。这是"exact 模式无 50-poles/10-boxes 硬 cap，那数字仅 exploratory 引导"的代码化形式。

---

## 6. `EXACT_*` env：certified_exact 下 deny-unknown + worker precedence + POWER_PLACEMENT_SUBPROBLEM

env 是最易被遗忘、最难从 artifact 复现的 proof-semantics 改动来源；旧 shell 残留的 `EXACT_*` 可能让 certified run 实际跑另一个语义。

### deny-unknown 闭合白名单
`certified_exact` 下 env 处理是**闭合白名单**而非黑名单。逻辑在 `src/search/benders_loop.py` 的 `_collect_forbidden_certified_master_domain_env_overrides`。
- **⚠ 行号：** Opus 称 `benders_loop.py:1332-1374`；Codex 称 `:1328-1405`。
- 注释（Opus 引 `:1335`）："V80 flips the guard from a blacklist to a closed allowlist"。
- 只有 `_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`（Opus 称 `:1254-1308`，约 50 个 operational 旋钮）里的名字可自由存在。
- 任何**未知/未来** `EXACT_*` 名字**仅凭出现即 fail closed** → blocker code `unclassified_exact_env_not_certified`。
- 任何**影响 proof-semantics** 的旋钮不在 canonical false/default 值 → blocker code `proof_semantics_exact_env_not_certified`。
- `PROJECT_LOCK.md:303` 和 `:175` 也把 `EXACT_*` deny-unknown 写入 lock。
- 后果：新工程师发明并设置一个新 `EXACT_FOO` 会阻塞 certified run，直到它被显式分类并加进 allowlist。env 索引 `docs/env_variable_index.md` **不完整**（`CLAUDE.md:255-259` 承认）——真实集合要 grep 源码里 `EXACT_` 上的 `os.environ`/`getenv`。

### `EXACT_POWER_PLACEMENT_SUBPROBLEM=1`（特别危险，Codex 详列多层阻断）
只能是 exploratory/forensic，不得在 certified 或 production campaign path 启用（`PROJECT_LOCK.md:451-466`）：
- `src/models/exact_coordinate_master.py:2228-2244` — `_delegate_power_placement_to_subproblem` 处 fresh read env。
- `src/models/exact_coordinate_master.py:3420-3437` — certified mode 见到它则除非 forensic bypass 否则 fail closed，报错指出它 forbidden in `certified_exact`。
- `scripts/run_campaign_linux.sh:31-41` — 生产 wrapper 阻断。
- `scripts/production_readiness_gate.py:306-315` — production/certified path 检查不允许它。
（Opus 只提到 Linux wrapper 若启用则拒绝启动。）

### worker-count precedence（`src/models/cp_sat_worker_config.py`）
优先级：**stage-specific env > global `EXACT_CP_SAT_WORKERS` > built-in default**。
- stage-specific 名：`EXACT_MASTER_CP_SAT_WORKERS`、`EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS`、`EXACT_BINDING_CP_SAT_WORKERS`、`EXACT_ROUTING_CP_SAT_WORKERS`。
- **Opus 补：** 默认值 master 8、local_capacity 8、binding 4、routing 8；解析 `_resolve_cp_sat_worker_count_with_source:52-60`；值须解析为整数 ≥ 1 否则抛错。
- **⚠ 行号：** Opus 称文档+实现在 `:1-31`；Codex 称说明 `:1-13`、env 名 `:25-31`、解析 `:52-60`、profile resolution `:63-81`。
- PowerShell wrapper 也提醒此优先级（`scripts/_exact_runner_common.ps1:4-6`）。

### preflight 跑 pytest 前 strip 若干 runtime EXACT_* env（Opus 提供；Codex 未提）
`preflight_gate.py:718-725` 和 `:761-767` 故意剥掉 `EXACT_OUTER_SKIP_UNKNOWN`、`EXACT_BINDING_DUMP_STATE`、`EXACT_MASTER_HINT_PERSISTENCE`、`EXACT_BINDING_USE_OVERLOAD_SEPARATION`，防生产 env 污染 default-behavior 测试。

### 被否决方案 / 残余
被否决："只列已知坏 env" / "unknown `EXACT_*` 默认忽略"。残余：若代码绕过统一 env collection 直接 `os.environ.get()` 仍需审。新增 env knob 必须同时更新 lock、tests、preflight/worker docs 和 certified blocker/allowlist。

---

## 7. Preflight gate、退出码、lanes、CI、生产 wrapper

preflight 是最重要的本地/CI gate，但**不是 certification proof 本身**。

### gate 的检查项与顺序
Opus 称共 **18 项**，`run_gate` 在 `:798-846`、顺序在 `:815-836`：frozen artifacts → external-artifact manifest → forbidden paths → AI-safety contract → exact/exploratory isolation → research-audit coverage → line-ending policy → publish secret scan → artifact boundaries → phase-review gate → P1.2 proof obligations → cc_memory consistency（仅当改动含 `cc_memory/` 时启用）→ strong-status allowlist → mypy → ruff → pytest。

### 入口
- `python scripts/preflight_gate.py` — staged changes。
- `--full` — 全量含 pytest（`-m "not slow"` 跳 `@slow`）。**⚠ 行号+细节：** Opus 称 1200s timeout、`-n auto` xdist（若可用）、`check_tests:687-745`；Codex 称 `:683-705`。
- `--hook` — git pre-commit 轻量入口。
- `--ci --base-ref <ref>` — PR/CI diff scope；设 `STRICT_TOOL_TIMEOUTS=True` 使工具超时警告变 blocker（`run_gate:802-804`）。
- `--slow-tests` — 专门 slow soundness lane：`-m slow`、串行（无 `-n`，因这些测试自己 spawn 子进程）。**⚠ 行号+细节：** Opus 称 `check_slow_tests:748-796`、2400s timeout、且 `require_collection=True` 使"没收集到 `@slow`"（pytest exit 5）成 blocker；Codex 称 `:748-758`。
- 四入口分派 Codex 称在 `:849-858`。

### 退出码——真实文档/代码不一致（两版一致确认，务必小心）
module docstring（`:18-22`）、README、`CLAUDE.md`（`:180-194`）都说 **exit 2 = pass-with-warnings**。**代码不这么做。** `GateResult.exit_code`（`:117-121`）只返回 `1`（有 blocker）或 `0`；`run_gate` 返回 `gate.exit_code`（`:846`）。有 warning 的 run 打印 verdict `"PASSED (with warnings)"`（`:839`）但**退出 0、不是 2**。别写分支 exit 2 的 CI/脚本——这个 gate 现状永不发 2。若新 pipeline 依赖它，先修代码或修文档。

### `@slow` 盲区（真实过往事故）
fast lane 故意跳 `@slow`，因为 slow 集成测试会撑爆 120s/600s timeout 并**掩盖**失败——正是代码注释里的 "C5 done-condition blindspot"（`:695-699`，Opus 引）曾让 stale tests 藏起来的盲区。硬教训（cc_memory `ci-saga-slow-blindspot-flaky-mechanism-20260626`）：**push producer/certification 改动前，本地跑 `preflight_gate.py --slow-tests`（约 13 min 串行）。** 本地 `--full` 反选 `@slow`、本身就是盲区。

### CI 三个 workflow（`.github/workflows/`）
- `project_foundation.yml` — 跑 `preflight_gate.py --ci --base-ref <ref>` 加 slow-soundness-gate（@slow, Linux, ~13 min）。Codex 补行号：基础 gate `:48-56`，slow-soundness-gate（恢复 candidate placements + 跑 `--slow-tests`）`:58-91`。
- `industrial_planner_single_base_delivery_surfaces.yml` — single-base delivery surfaces（Codex 称 `:60-101`）。
- `industrial_planner_checked_artifacts.yml` — focused IndustrialPlanner regressions（Codex 称 `:112-147`）。
后两者守护 IndustrialPlanner delivery/postprocess 表面（additive，不得成 solver/runtime source-of-truth）。

### 生产启动走 wrapper，不裸跑 `python main.py`
裸调丢 tuning。三个理由：
1. `main.py` 当前 production chain 只到 `CANDIDATE_PROPOSED`；supervisor seal 生产入口是独立的 `scripts/run_supervisor_seal.py`，不由 main/wrapper 顺手调用（`PROJECT_LOCK.md:130-137`，cc_memory `p1-2-supervisor-production-entry-gap-20260626`，commit `349c56c`）。
2. wrapper 设置生产环境/资源/安全检查。
3. wrapper 处理 resume/platform/proof-surface 状态。

- **Linux/CachyOS**：`scripts/run_campaign_linux.sh` — 加 jemalloc `LD_PRELOAD`、P-core `taskset` pinning、自动注入 `--resume-campaign`、若 `EXACT_POWER_PLACEMENT_SUBPROBLEM` 启用则拒绝启动。Codex 补行号：168h wrapper `:3-18`、要求 `.venv/bin/python` `:22-29`、阻断 power subproblem `:31-41`、设 jemalloc/`LD_PRELOAD`/`PYTHONMALLOC` `:44-66`。
- **Windows**：`scripts/run_prod_1x1_normal.ps1`、`run_prod_4x4_high.ps1`（Codex 称调用在 `:9-25`，`--mode certified_exact --campaign-hours ... --parallel-processes 4 ...` 支持 `--resume-campaign` + worker overrides）、`run_prod_4x4_normal.ps1`，共用 `scripts/_exact_runner_common.ps1`（`:1-7` 提醒 worker precedence）。
- `main.py --campaign-hours >= 24` 在 `certified_exact` 是 "production-class"，门在 `scripts/production_readiness_gate.py`（pacman-freeze/venv/preflight，检查 power subproblem disabled、OOM、disk、git、THP/jemalloc/P-core、Linux-only 等；readiness check/report 逻辑 `:1-27`、`:147-170`、`:459-482`）+ freeze monitor；`--skip-readiness-gate` 绕过（仅 debug/dry-run）。

被否决方案："裸跑 main.py 参数一样就等价"——certified run 失败模式含资源/env/resume/platform/proof-surface，不只 Python 参数。

---

## 8. 三套记忆系统（仅概念——新机器可用自己的）

新机器上从零接手的新工程师**不需要**用我们这边的记忆系统（owner 甚至希望他从零摸索以发现盲点），但要知道它们存在、各自角色，以便理解本文档引用来源。

1. **`cc_memory/`（SQLite `cc_memory/memory.db`）** — **full, searchable, pull** 历史库 + 低摩擦写入 inbox。单 CLI `python cc_memory/mem.py {boot,search,read,impact,add-entry,set-fact,link,check,export,...}`。`cc_memory/exports/MEMORY.md` 是可重生视图、**绝不手改**。可选 GPU semantic/rerank 检索。本文所有 `entry:*` id 都在这里（约 170 条）。变更前用 `impact`/`read --body`；禁止用 raw SQLite 正常编辑；禁止复活 `cc_context/memory`、`_cc_live_memory`、`memory_graph`（`AGENTS.md:1-40`, `CLAUDE.md:57-93`）。
2. **`cc_memory_vnext/`（确定性卡片编译器）** — **push** 层，`cards/*.md` 每轮经 hook 自动注入。只有"必须每回合注入的稳定事实"graduate 到这里（如 claim-guard 卡 `close-kernel-pin-reaches-runtime`）。CLI `python cc_memory_vnext/zmem.py {verify,build-index,context,eval}`。cc_memory `owner-no-vnext-status-card-20260630`：不要把高频项目状态做成 vnext status card（churn 太快），进度优先由 harness resume + cc_memory 承载。
3. **Harness auto-memory**（`.../projects/.../memory/MEMORY.md` + `p1-2-resume-state-20260621.md`）— session-load-once 薄层，放导航指针、短行为反射、跨会话 resume 锚。PR2 #5 saga 的最佳逐轮叙事源就是这个 resume 锚（顶部 `▶▶▶` 段最新）。

设计注（若采用）：每条记忆一个 live 源——graduate 到 vnext 卡时 archive 掉 cc_memory 源以防漂移；whole-DB freeze/migration 明确**不是**计划。边界：不能把旧对话摘要当 proof；追溯旧结论最好落到 cc_memory id / harness line / git commit / 源码 file:line 四者之一，追不到就降级为待验证假设。

---

## 9. Codex 调用路由 + review-routing（soundness 审查）

这是**我们团队**的协作协议。新 CC/工程师有自己的倾向；记在此让 commit/review 历史可读、让某些产物（外审包、提示词）的存在有解释。

### 按体量路由工作（cc_memory `codex-executes-claude-orchestrates` / `codex-claude-codex-claude-4-1-high`）
首要判据是**工作量大小**，不是任务标签：大活（实现、调查、**含大阅读/验证**）→ codex（full-permission 执行者，省 orchestrator 预算）；小活（含小实现）→ 自己做。"实现→codex / review→opus"只是经验相关、不是规则——按体量路由。过往事故：因工具模式反射把大阅读/调查派给 opus-backed Explore 子代理，烧约 3M token，本该给 codex。cc_memory `workstyle-codex-routing-cache-probe-junk-20260630`：大 fan-out / 问题 hunt / verification 转 codex；别杀快完成的 workflow（先查 cache/resume）；codex probes 可能在 repo root 留临时脚本，preflight/package 前按窄模式清理。

### 隔离 worktree 做实现（cc_memory `codex-agent-worktree-implement-integrate`）
大实现派 codex 用 `isolation:worktree`、`baseRef=head`，在 worktree branch 提交，然后主工作树 `git merge --ff-only` 集成。理由：共享 `.git` 保持线性、git blob LF 可控、减少主工作树并发污染。被否决：让 codex 在旧 checkout 或主工作树直接并发大改。仍要求人工审 diff + 独立关键验证 + 全量 preflight。

### 跨模型审查是常设、对称不变量
主活谁做、由**另一个模型**审。独立于体量路由。

### soundness/certified-core 审查路由（cc_memory `review-routing-codex-local-then-gptpro-relay`）
双模型对抗审原则不变；owner 2026-06-28 改的是**哪两个模型**，以停止在审查上烧 Claude 预算——从 `[opus + codex]` 改成 `[codex + GPT Pro]`（codex 未被去掉，被换的是 opus/Claude 侧）：
1. **本地 codex 先审+修**（便宜、本地）。
2. **打包 HEAD/diff + 写 lean、不剧透、全角度覆盖的提示词 → GPT Pro**（web relay，不花 Claude 预算）作第二个跨模型 pass。提示词请求每个 BLOCK 一个 patch，但 patch **绝不盲应用**——orchestrator 按 spec 重实现并重验证。
3. **审查不走 workflow**（workflow fan-out 拉 opus = 你要省的预算）。
4. orchestrator 角色不变：集成 + 终裁（审 patch 真伪 + reseal ritual + **自己跑全量 preflight**——子代理的 "CLEAN" 不是 regression pass，这点咬过我们两次，如 cc_memory `pr1-supervisor-mint-preflight`）。

**⚠ 审查角度上限来源（供终审注意，非硬冲突）：**
- 一版（Opus）把 "1 comprehensive + ≤5 focused = ≤6" 上限归到 cc_memory `review-cadence-narrow-iterates-defect-per-item-not-batched` + resume 锚。
- 另一版（Codex）明确核实：该上限**不在** cc_memory 条目里，而在 vnext 卡 `cc_memory_vnext/cards/review-routing-gptpro-relay.md:63`（owner 2026-07-01 加）："1 份【全面审查】必有 + focused 分角度 ≤5、总数 ≤6"；同文件 `:5` summary、`:58-67`、`:62`（lean/中性/不剧透"漏洞机制是 X / 我判 sound 因为 Y"以保盲审独立）。

GPT Pro 作 multi-session panel（独立会话、取最保守并集）——反复抓到 codex 本地审 + orchestrator 都漏的 BLOCK（如 merge `099f5a3` 背后的 3 个 BLOCK，cc_memory `pr2-8-9a-hardened-landed-099f5a3`）。

### GPT Pro relay 的项目级 UI/操作约束（`AGENTS.md:317-366`，Codex 提供）
P1.2 对抗 soundness 审查包要上传到 ChatGPT project `终末地` 的 **Sources tab**，不走 chat composer 附件；上传前删旧项目 review packages，但**不删** dependency/runtime packages；发送前确认 composer 是 boxed `Pro 扩展`；每个上传包发 **exactly three** review requests；rate-limit/风控形态的回复**不算** valid review；网页 timeout/missing-content 时关旧 tab 重开相同 URL，不点 retry，不把 partial network-error answer 算 valid。

### 诚实状态
整个 PR2 #5 close-kernel 战役（round 3→18）仍在分支 `pr2-5-domain-frontier-gate` / 隔离工作树 `pr2-5-round10`，**未 merge 到 main**。结构 BLOCK 已清；三类残余留存（import-time #5-F、"必须改 checker"、A4 动态反射），owner 接受为显眼-diff/clean-review 残余。

### 被否决方案（合并）
- 审查继续派 workflow fan-out 挂 opus（正好烧要省的额度）。
- 盲套 GPT Pro 补丁（仍需本地 triage/source read/reseal/preflight）。
- 只给 diff 不给完整包（vnext 卡记 owner 2026-06-29 纠正：给完整 HEAD snapshot package）。
- 写提示词剧透本地结论（破坏盲审独立性）。

### 残余边界
GPT Pro review 是 adversarial review、不是 formal proof；三份 review 或六会话 panel 都不能替代 `PROJECT_LOCK.md`、source read、checker/preflight 和 human final judgment；rate-limited 异常回复明确不算有效 review。

---

## 10. 搜索/导航工具（否则会白费力气）

### `es`（Everything CLI）——按名字/路径瞬时找文件
按文件名/扩展名/路径片段找文件用 `es`（Everything CLI，PATH 上 `es.exe`，Codex 补路径 `C:\Users\22957\scoop\shims\es.exe`）——全盘 NTFS 名字索引、近乎瞬时。优先于 `Get-ChildItem -Recurse` / `find` / `fd`（递归遍历慢、本机上挂过——全盘 `face*.mp4` 扫描曾卡死）。形式：`es <substring>`、`es dispatch ext:mp4`、`es -name foo.ps1`，加 `-size -date-modified -sort path`。它**只索引名字/路径、不索引内容**——内容搜索用 Grep。全局 PreToolUse hook `es_reminder.py` 拦递归 `find -name`/`fd`/`Get-ChildItem -Recurse` 并提示改用 es（120s 重发逃生门；批操作/内容搜索自动放行）。全局 `CLAUDE.md:44-61`；cc_memory `claude-code-custom-hooks-this-machine`。

### CodeGraph——符号/调用链索引
"X 怎么工作"、定位符号、追 callers/callees、圈定改动 blast radius，先用 CodeGraph（MCP `codegraph_explore`，或 CLI `codegraph explore|node|callers|callees|impact|search`）。一次调用返回逐字源码 + 谁调用它 + 影响什么。它是可重生 cache（`.codegraph/`，git-ignored，`codegraph init .` 重建），**不是** live memory、**不是** proof evidence、**对 certified 声明不权威**——proof-sensitive 工作用它**找**文件、再对 source + `PROJECT_LOCK.md` + targeted tests + 相关 gate 核实（`CLAUDE.md:117-141`, `AGENTS.md:107-118`）。
- **Codex 补 live 状态：** `codegraph status .` 报 index up to date：`1,482 files`、`30,862 nodes`、`88,938 edges`、DB `111.39 MB`。
- **Codex 补 stale 坑：** cc_memory `codegraph-index-branch-boundary-stale`——feature branch 改过的文件 CodeGraph 可能仍反映旧 index/main；proof-sensitive branch-changed code 必须读实际 source/diff，按需 `codegraph sync .`。cc_memory `codegraph-codegraph-codegraph-init-proof-cc-memory`：CodeGraph 不是 cc_memory、不是 proof、只是 map。
- **Opus 补 landmine（你会撞上）：** 全局 PreToolUse hook `codegraph_reminder.py` 拦看起来像符号/定义查找的 `Grep`/`grep` pattern（含 `def`/`class`/标识符 alternation），并**拒绝**它、指向 CodeGraph。逃生门 = **原样重发完全相同 pattern**（第二次就放行）。真正的内容/行搜索必须原样重发或改用 `Read`；内容搜索/regex/中文/docs 自动放行。（本文档准备期两次对 `preflight_gate.py` 的内容搜索被拦。）

### Shell 工具选择（Windows 全局铁律，Opus 补）
带 `C:\` 反斜杠路径、`Get-*`/`Set-*` cmdlet、`$env:`、`-ErrorAction` 的命令 → 默认 **PowerShell** 工具；纯 POSIX 脚本（正斜杠、无 cmdlet）→ **Bash** 工具。全局 PreToolUse hook 拦被误发给 Bash 的 PowerShell-shaped 命令（反斜杠吞引号 → `unexpected EOF`）。

---

## 开放问题 / 文档-实现不一致 / 未决残余（诚实收尾，两版并集）

1. **P1.2 仍 OPEN/BLOCKED**（`PROJECT_LOCK.md:130-137`）：producer 可提交 `CANDIDATE_PROPOSED`；`ExactCampaign.supervisor_seal()` 是唯一 durable terminal `CERTIFIED` mint，生产入口是独立的 `scripts/run_supervisor_seal.py`，`main.py` 仍停在 `CANDIDATE_PROPOSED`。别把 checker 绿、targeted tests 绿、方法存在、wrapper 能跑、入口落地解读成 P1.2 closed/released。P1.2 被 release-block 在 owner 侧、仓库外的人工 clean-review 计数后面。
2. **`preflight_gate.py` exit code 文档 ≠ 实现**：docstring/`CLAUDE.md` 说 `2 = warnings/no blockers`，但 `GateResult.exit_code`（`:117-121`）只返回 `1`/`0`。依赖 warning exit 前先修不一致或更新文档。
3. **reseal 的 index/HEAD/working-tree 操作细则尚无单一权威 runbook**：cc_memory 有 CRLF、pathspec、committed-tree 事故条目，harness `p1-2-resume-state-20260621.md:16` 有 `git show :path` 读 index 坑，但无单独"reseal algorithm"条目覆盖全部。做 close-kernel reseal 时在操作记录明说 hash 来源、用 `git show HEAD:<path> | sha256` 或 staged blob 对账。
4. **PR2 #5 round-18 是隔离工作树史料、不等价当前主线**：`9bbb3a6` 在 `.claude\worktrees\pr2-5-round10`；主工作树当前 `b35e5f9`。"round-18 已修"要先确认目标 clone/branch 是否含这些 commit。
5. **⚠ 三 runtime 文件 blob OID 两版不一致**（见 §3）：Codex live git 读为 `ef3987d`/`af276679`/`da326456`（+ `exact_campaign.py`=`2f55bc65`、checker=`f1d24ada`）；Opus 引 resume 锚为 `2f55bc65`/`af276679`/`da326456`。终审需在目标 checkout `git ls-tree` 复核。
6. **#8/#9a runtime byte-pin manifest 是 deploy-pending**（cc_memory `pr2-8-9a-hardened-landed-099f5a3`）：#8/#9a 已 merge main `099f5a3`，但 manifest 是审计 Linux env 字节的占位，生产前必须 **CachyOS + Py3.13 重生成 + 审 + 重钉**（本机 WSL=Ubuntu 无 CachyOS/无 Py3.13 venv，生不了）。别把"机制已落"误读成"生产 runtime pins 已最终物化"。
7. **close-kernel checker 有理论自证边界**（`check_p1_2_proof_obligations.py:3784-3791`）：checker 不能递归证明自己源码，git history/human review 是 TCB。V99 floor + whitelist 能把很多 silent drift 变显眼 diff，但消除不了"checker 自己被恶意/错误重封"的最终人审边界。
8. **close-kernel 第二门不能证明 proof-math 正确性**（§3，owner 裁定非疏忽）：叶子 helper 数学 + A4 动态反射 + import-time(#5-F) + "必须改 checker" 残余，只由 source-sha floor + frozen-artifact hash + 人工 clean-review 兜底。这是自动门保证的天花板；新审查者应正打这里探（owner 委托独立 handoff 的期望所在）。别写成"完全封死 Python 动态反射"。
9. **`EXACT_*` env index 不完整**（`CLAUDE.md:255-259` 承认）：deny-unknown 是防线，但绕过统一 env collection 直接 `os.environ.get()` 仍可能形成旁路。新增 env knob 必须同时更新 lock、tests、preflight/worker docs、certified blocker/allowlist。
10. **candidate_placements.json 在 lightweight checkout 可能缺失**：certified run 必须先 restore+verify，且必须拒绝旧 53,594,995 字节 artifact。
11. **CodeGraph 可能 stale**（尤其 feature worktree/branch 改动文件）：用于定位、非 proof；与源码不一致时以源码、git diff、`PROJECT_LOCK.md`、gates 为准，按需 `codegraph sync .`。
12. **cc_memory/vnext/harness 是旧团队上下文、非新机器必需依赖**：本文中只作史料来源。引用旧结论尽量追到 cc_memory id / harness line / git commit / file:line；追不到就降级为待验证假设。

### 本章主要可追溯源
`scripts/preflight_gate.py`、`scripts/check_p1_2_proof_obligations.py`、`scripts/check_line_endings.py`、`scripts/production_readiness_gate.py`、`scripts/run_campaign_linux.sh`、`scripts/run_prod_*.ps1`、`scripts/_exact_runner_common.ps1`、`src/io/strict_json.py`、`src/search/benders_loop.py`、`src/search/certified_artifact_contract.py`、`src/models/exact_coordinate_master.py`、`src/models/cp_sat_worker_config.py`、`data/proof_obligations/*`、`data/line_ending_policy.json`、`.gitattributes`、`.github/workflows/*`、项目+全局 `CLAUDE.md`、`AGENTS.md`、`PROJECT_LOCK.md`；cc_memory `p1-2-fix-1-close-kernel-crlf`、`pathspec-must-cover-full-reseal-set`、`close-kernel-ast-pin-structural-vs-semantic-boundary`、`close-kernel-ast-checker-design-lessons`、`gate-self-check-whitelist-not-blacklist`、`data-file-semantic-floor-runtime-anchor`、`close-kernel-sealed-lint-v99-reseal-re-export-patch-ruff-f401`、`review-routing-codex-local-then-gptpro-relay`、`codex-executes-claude-orchestrates`、`codex-claude-codex-claude-4-1-high`、`workstyle-codex-routing-cache-probe-junk-20260630`、`codex-agent-worktree-implement-integrate`、`close-kernel-block-convergence-trend-20260630`、`pr2-8-9a-hardened-landed-099f5a3`、`pr2-5-seal-frontier-gate-landed`、`pr2-5-round10-11-12-fspinout`、`pr2-5-round14-11th-review-block-round15`、`ci-saga-slow-blindspot-flaky-mechanism-20260626`、`p1-2-supervisor-production-entry-gap-20260626`、`p1-2-supervisor-l0-l1-design-meeting-20260623`、`owner-no-vnext-status-card-20260630`、`claude-code-custom-hooks-this-machine`、`codegraph-index-branch-boundary-stale`、`codegraph-codegraph-codegraph-init-proof-cc-memory`、`pr1-supervisor-mint-preflight`；vnext 卡 `close-kernel-pin-reaches-runtime`、`review-routing-gptpro-relay.md`；harness 锚 `p1-2-resume-state-20260621.md`；commits `b35e5f9`(main HEAD)、`9bbb3a6`(round-18)、`c96a601`、`2ca6864`、`1b90285`、`d1a59ad`、`504b3f8`、`8714ee7`、`adeddc5`、`a5a5e64`、`7851c1e`、`c115f31`、`099f5a3`、`592ea13`、`b085a75`（归属轮次未标注）、以及早期 `2ec8954`/`2c258c6`/`4410b6a`/`dbd1d72`/`b6d41c6`/`cce5dd5`。


---

# 第 6 章 · 项目现状 · 剩余工作 · 开放问题与可能盲点

> 面向【从零接手、不带我们的工作记忆、要独立重新摸索并有权重判我方结论】的新工程师。这是 faithful 的史实 + 决策记录，不是"照结论做"的说教。所有引用可追溯（file:line / git 短 hash / cc_memory 条目 id / 文档路径）。诚实包含失败、死路、反复、被否方案、未决残余、开放问题。
>
> **核心提醒（两版一致、反复用血教训坐实）**：本项目里"gate 绿灯 / 测试通过 / 方法已实现 / 一个 seal 方法被调过"从不等于"已认证 / 已发布"。P1.2 只能由 owner 仓库外手动门关闭。

---

## 一、证据基线与主源（读这段先搞清"最新状态活在哪里"）

- **写作时的最新状态（round-15→18）主要活在 harness RESUME 锚里，尚未完整沉淀进 cc_memory**（2026-07-04 注:round-19/20 与合并 `6e06922` 已进 main 历史,`git log` 即可看到,不再只活在 RESUME）。主源文件：`C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory\p1-2-resume-state-20260621.md`，顶部 `▶▶▶` 段最新、已完整读取。**⚠ Codex 版特别指出**：该 RESUME 自己在 round-18 段末尾写有"待记 cc_memory：round-15..18 完整故事"（`p1-2-resume-state-20260621.md:12-14`），即 **cc_memory DB 里只记到 round-14 / 更早的余项表**，最新的 round-15→18 只在 RESUME + git commit message 里。新工程师用 `cc_memory search` 查不到最新几轮，必须读 RESUME + git log。
- **两版都读了 harness RESUME + 本地 git + cc_memory + PROJECT_LOCK 作证据**；结论高度一致，差异点已在下文用 ⚠ 标注。
- **⚠ 一个引用可读性差异**：Opus 版把 `pr2-5-F-line-import-time-integrity-schedule` 当作权威来源引用（它确实作为 **harness 记忆 markdown 文件** `pr2-5-F-line-import-time-integrity-schedule.md` 存在，登记在 MEMORY.md 索引里）；Codex 版尝试用 cc_memory CLI 读同名 **DB 节点** 失败（报 `unknown node`），判定它"只能作为其它条目正文中提到的历史引用名，不能当作已读独立 cc_memory 条目"。**结论**：它是一个 harness 侧的 .md 文件、不是 cc_memory DB 里的节点；F 线的可读 cc_memory 正文集中在 `pr2-5-round10-11-12-fspinout`。

---

## 二、当时 HEAD / 分支位置 / 未 push 风险（2026-07-02 快照;接手硬阻碍已随 `6e06922` 合并解除——close-kernel 工作已全在 main,不再依赖未 push 分支）

- **`main` = `b35e5f9`**（两版一致，git 核过）。它是一条**纯记忆（memory）提交**（"PR2 #5 round-14 第11轮外审 triage — NOT sound（收敛 BLOCK）→ round-15"），**不含任何 PR2 #5 的代码硬化**。main 上最后的实质代码进展是更早合入的 PR2-b（`69980b3`+`592ea13`）和 PR2 #8/#9a（merge `099f5a3`）。
- **⚠ main 相对 origin 的位置**：Opus 版只说"origin 上最新是 `5ab006f`，更旧"；Codex 版明确 **本地 `main` 相对 `origin/main=5ab006f` 是 ahead 2**。两者不冲突，Codex 补了"ahead 2"这个精确量。
- **`pr2-5-domain-frontier-gate` = `9bbb3a6`**（两版一致，git 核过，分支 HEAD）。这是 PR2 #5 全部 close-kernel 硬化所在。
  - Opus 版：`git rev-list --count main..pr2-5-domain-frontier-gate` = **26**，即领先 main 26 个 commit（Codex 版未给此数，只说"相对 origin/main 有完整 round-7→18 线性硬化序列"，不冲突）。
  - **⚠ 工作树位置**：Codex 版补充该分支工作在 worktree `C:\claude pj\zmd_pj\.claude\worktrees\pr2-5-round10`（Opus 版未提）。
- **🔴 关键接手障碍（两版一致）：`9bbb3a6` 未 push 到任何 remote。** `git branch -r --contains 9bbb3a6` 为空；origin 上最新是 `5ab006f`（更旧）。**整个 PR2 #5 的 26 个 commit 只活在本地 `.git` 里。** 新机器 clone origin 只会看到 `origin/main=5ab006f` 和 `origin/pr2-8-9a-batch=ec7dc52`（后者仅 Codex 版列出），**拿不到 `9bbb3a6` 的任何工作**。交接必须由 owner 把这条本地分支带过去（打包 `.git`、`git bundle`、或 push），否则这段状态全丢。（2026-07-04 注:此风险已解除——round-19/20 收口后 `6e06922` 合入 main,close-kernel 工作随 main 交付。）
- **⚠ 工作树 dirty 状态**：Codex 版补充——PR2 worktree 的 `cc_memory/memory.db` dirty；主 checkout 也有 `cc_memory/memory.db` dirty + 大量未跟踪日志。**别把"commit 存在"误读成"所有工作树干净"。**（Opus 版未强调此点。）

**分支上 round-by-round 的 commit 链**（Opus 版 `git log` 核过；Codex 版核了各轮 commit stat，与文件范围吻合）：
```
9bbb3a6 round-18: A4 动态反射重绑 best-effort 加固 + 归为已裁定残余   ← HEAD
2ca6864 round-17: A4 收敛 — witness 体 blanket 禁 namespace/exec/reflection 面
c96a601 round-16: 收敛 close-kernel 闭集(codex 前置复审挖出 round-15 3 BLOCK)
1b90285 round-15: close-kernel 第二道门硬化(第11轮外审 BLOCK 后)
d1a59ad round-14: structural whitelist hardening (10th-review panel)
504b3f8 round-13: close-kernel structural-gate soundness (9th-review panel)
8714ee7 round-12: robust import-time closure walker (close F-form class)
adeddc5 round-11: close-kernel def-time/import-time hardening + verifier canaries
a5a5e64 round-10: close-kernel full-pin closure + closed-world + import allowlist
7851c1e round-9  pin close-kernel helpers
c115f31 round-8  close-kernel pins
dbe27c0 round-7  lint fix ...
... (更早 round-2..7 见 git log，commit 2ec8954 起)
```

---

## 三、round-18 状态 + 当时在等什么（WAITING_EXTERNAL,2026-07-02 快照;后续:第 12 轮外审未发,owner 画线停止外审循环,round-19/20 收口后 `6e06922` 合入 main）

round-18（`9bbb3a6`）已完成、已备好第 12 轮 GPT Pro 外审包等 owner 手动跑：

- **round-18 commit 内容**：**⚠ Codex 版补充精确 stat**——只改了 `data/proof_obligations/p1_2_proof_obligations.json` 和 `scripts/check_p1_2_proof_obligations.py`，stat **32 insertions / 2 deletions**（Opus 版未给 stat）。commit message 记录：5 镜头 codex 对抗审发现 round-17 A4 blanket 仍漏 `__globals__` / frame / module-attribute 形态；owner 2026-07-02 拍板把 A4 动态反射重绑接受为 best-effort + conspicuous diff / clean-review 残余，不再把完整 A4 闭合当 release blocker。
- **round-18 结果**：已知 form-5/6/7 被 best-effort 加固捕获（A4 attr 禁集加 `__globals__`/`f_globals`/`f_locals`/`f_back`/`tb_frame`，加 attribute-target 到 witness 名的检测），4 个 proof witness 函数零误伤，checker 单跑绿 60 sinks，加残余注释。
- **⚠ preflight 验证性质**：Opus 版直接写"preflight 绿（3734 passed）"；**Codex 版明确加了诚实边界**——"本轮我未重新跑 full preflight，这里记录的是 RESUME 与 commit message 的历史验证证据，而不是新的验证结果"。两版都称 pytest **3734 passed**、3 个 runtime close-kernel 文件字节未动。新工程师接手应把 3734 passed 当"历史记录"、必要时自己重跑全量 preflight 复核。
- **⚠ checker sink hash（仅 Codex 版给）**：manifest 里 checker sink hash = `1e49c70e...`，见 `9bbb3a6:data/proof_obligations/p1_2_proof_obligations.json:969`。
- **待审包（两版一致）**：`C:\Users\22957\pr2_pkg\zmd_pr2_5_round18_9bbb3a6.7z`，SHA256 = `5a59999f8432dd56862118e75212578c84acf2ea87495fa8e16cff692d293b84`（两版核过一致）。
- **6 份提示词（两版一致）**：`C:\Users\22957\pr2_5_round18_review_entry_{1..6}_*.md`。文件名 `entry_1_comprehensive.md` … `entry_6_false_positive.md`（Codex 版给全名）；角度分工（Opus 版给分工）= 1 全面 + 5 分角度：红队-silent 通道 / 红队-静态 pinned≠runtime / 边界-3 类残余裁定正确性 / checker 自完整性+reseal+C-a 父锚 / 误伤过约束。
- **⚠ 历史外审报告落地位置（仅 Opus 版给）**：第 11 轮报告原文在 `C:\22957\download\新建文件夹\pr2-12\`（6 份）；历史各轮在 `pr2-10`（第 9 轮）、`pr2-11`（第 10 轮）。
- **回传后判据（两版一致）**：union+triage → 若无【新】structural BLOCK 且残余仅三类（F / checker-self / A4 动态反射）且边界正确 → merge `pr2-5`→main（CI @slow）→续 PR2 余项；若有 silent 或可约（reducible）structural BLOCK → round-19；若残余边界画错 → 按 GPT Pro 指出的边界补。参考 `p1-2-resume-state-20260621.md:14`。

---

## 四、close-kernel「第二道门」round-15→18 史实链（理解当前状态最关键的一块）

**权威主源**：cc_memory `close-kernel-ast-pin-structural-vs-semantic-boundary`、`close-kernel-block-convergence-trend-20260630`、`pr2-5-round10-11-12-fspinout`、`pr2-5-round13-14-whitelist-landed`、`pr2-5-round14-11th-review-block-round15`、`close-kernel-ast-checker-design-lessons`、`gate-self-check-whitelist-not-blacklist`、`pr2-5-round8-9-converged-relayed-20260630`；harness RESUME `p1-2-resume-state-20260621.md` 顶部段。

### 4.1 这道门要防的威胁 + 两道门是什么

一个未来的维护者（或恶意方），保住 close-kernel checker 全绿——重算所有 source-sha256、重钉 V99 楼面、重钉 obligations 和 checker 自钉——却在这个过程里**把 L0 supervisor / child verifier 的证明语义掏空**（比如让终态校验变成死代码、让 durable CERTIFIED 铸造绕过全前沿穷尽校验）。

- **第一道门**：V99 的**整文件 source-sha256 楼面**（改字节就漂 hash → 触发 freeze-ritual 人工重钉审 diff）。
- **第二道门**：**AST 结构 pin**——想在"字节没漂到扎眼"的前提下额外锁住结构语义。

### 4.2 元模式（一条清晰主轴）：每轮 BLOCK 比上一轮深一层 indirection

六~十二轮外审 + 无数轮本地 codex 对抗 re-probe，信任泄漏点一路下移——"你钉住了 X，但 X 依赖 / 委托的 Y 没钉"：
1. 状态字段一致性（producer 铸 durable CERTIFIED / `declare_mode` 三处归一）→
2. 字面 pin 精确度（没钉 `final_status` 位置 / 可重绑·别名·`__setitem__`）→
3. 函数体内自由表达式空间（canonical 窗口 / 正向白名单仍可绕）→
4. **被审 AST ≠ 运行时绑定对象**（`_function_def` 取首个 def、运行时绑最后；import-time 执行）→
5. **写入器钉了、它引用的全局 / helper 没钉** → round-7 给 `run_l0_supervisor_seal`（唯一 durable CERTIFIED mint chokepoint）整 body pin；之后再没那条的 round = 写入器路径**收敛** →
6. **钉了调用、被调的 gate helper 体没钉** → round-8（`c115f31`）：`_strong_status_keys` → `return []` 跳整个 replay 仍铸 CERTIFIED → round-9（`7851c1e`）从 6 个 chokepoint 走调用图把 3 个 close-kernel 文件内 123 个可达 cert helper 全函数级 source-sha pin（cc_memory `pr2-5-round8-9-converged-relayed-20260630`）。

### 4.3 round-9 → round-14（转向白名单前的历史）

- **round-9「123/123 全覆盖」被证伪 → round-10（`a5a5e64`）改策略「pin 全部」**：第 6 轮 panel 三会话连"可达数"都各报不同（手工 / 单闭包计数不可靠）→ 不再算可达闭包补漏，直接把 3 个 close-kernel 文件的每个 FunctionDef + 整类 + 方法 + 模块常量全进 source-pin 表（+ closed-world + import allowlist）。
- **round-11（`adeddc5`）**：第 7 轮 5-session panel 又挖出 9 类真 BLOCK（装饰器不进 `ast.get_source_segment`、类体最后绑定胜、self-binding 用 `ast.walk` 可被死分支骗、**first-party import-time 传递闭包没进 V99 floor**——改 `strict_json.py` 等 checker 直接绿连 reseal 都不用）。
- **round-12（`8714ee7`）**：把 import-time 闭包 walker 做 robust（**22→60 文件**）。**然后 codex 又挖出 `.pyw`/`scripts.*`/`importlib.__dict__[...]`/def-time 隐式调用逃出闭包 = F（import-time 执行完整性）不收敛** → **owner 2026-07-01 拍板：F 单列成专门线 PR2 #5-F**（见 §八）。
- **round-13→14（`504b3f8`→`d1a59ad`）**：第 9、10 轮 panel。round-13 加 checker 自完整性（FIX-4/5）；第 10 轮 panel 又在这些新加法里挖出一大片绕过 + **2 条数据文件通道**（`strong_status_write_allowlist.json` 语义字段没 floor，只改 json 就掏空）。owner 选**结构化 round-14**：`errors` 用法改**白名单**（只放行好形态、其余全拒），残余压到"必须动 checker 自己"= 人工 clean-review 兜底。cc_memory `pr2-5-round13-14-whitelist-landed`。

### 4.4 round-15→18（denylist 不收敛的顶点，最近这段）

- **round-15（`1b90285`）**：第 11 轮 6-panel 判 **NOT sound、收敛 BLOCK**。
  - **⚠ finding 计数**：Opus 版称"约 13 个 finding"；Codex 版不给计数、给标签。合并后按 3 类：
    - **① silent**（纯数据不动 checker，如 obligations manifest 可新增未投影顶层字段；Codex 标 **S1**：manifest 顶层字段不 closed-world）；
    - **② runtime 掏空 + 忠实 reseal 保绿**（Codex 标 **A3/A4**）：实例 `__dict__` alias 写 / mutator alias / 类查找写 / comprehension shadow / `globals()[name]=` / `del`·type-alias 等；
    - **③ checker-self**（Codex 标 **C-a..e**，最 severe）：`main=lambda:0` 掏空整个 checker、`match []: case errors:` 重绑、runtime C6 锚两端都绿 等。
  - **⚠ diff 规模（仅 Codex 版）**：把白名单 / 闭集原则推到三面（manifest 顶层 closed-world；A3/A4 反射原语门；entrypoint/callee runtime 绑定锚 + errors 绑定完整性 / accumulator callee 身份 / append 参数纯度 / FLOOR walrus），**5 文件 1801+/47-**，preflight 历史 PASSED。
- **round-16（`c96a601`）**：codex 前置复审又挖出 round-15 的"完整闭集"仍是 denylist。**⚠ 两版对同一轮的框架略不同，均保留**：
  - Opus 版：round-16 是对 codex 前置复审所挖 **3 个新 BLOCK** 的回应——（允许语句里的 import-time 表达式副作用 / 函数对象 mutation `__code__` / exec 重绑）。
  - Codex 版：round-16 的动作是**从逐形态 denylist 转向 blanket 禁整类**（顶层 closed-world 禁 import-time 表达式副作用；A3 禁函数对象 mutation 关键属性；A4 禁 exec/eval/import 形态），**3 文件 177+/11-**；然后 round-16 后 codex 复审又发现 **A4 form-4**：`operator.setitem(globals(),...)`、`dict.__setitem__`、`types.FunctionType(compile(...), globals())()` 仍可重绑 witness 名。
  - 合并理解：涉及的三类（import-time 表达式副作用 / 函数对象 mutation / exec 重绑）在 round-16 被 blanket-forbid（正是 codex 前置复审把它们暴露为 round-15 仍可绕），随后 form-4 再冒出。
- **round-17（`2ca6864`）**：采纳 codex 建议，A4（名字 shadow 面）改 **blanket-forbid**（witness 体出现任一反射原语 Name/Attr 即 fail-closed），**2 文件 39+/14-**。5 镜头对抗 workflow 又挖出 A4 **form-5**（`__globals__` 加进了 A3 却漏同步进 A4）。
- **A4 denylist 确定性不收敛坐实**：form-5 `witness_func.__globals__`、form-6 `sys._getframe().f_globals`、form-7 `sys.modules[__name__].witness = fake` 全绕，每补一个 attr 冒下一个反射面。
- **owner 2026-07-02 拍板**：A4 动态反射重绑**接受为残余（推荐档）**，归入「best-effort 门 + 显眼编辑 / clean-review 残余」，与 F #5-F、checker-self 同类——依据是 **witness 函数已被 source-sha256 逐字节钉死**，改它 = 显眼 diff + 人工 clean-review 能逮。**不再把完整 A4 闭合当 release 阻塞。** **被否决的替代方案**：继续无限硬化；把 witness 体重构成更窄 whitelist（判为高风险 / 大改 / 可能误伤，未选）。代码注释见 `9bbb3a6:scripts/check_p1_2_proof_obligations.py:1626-1636`（"does NOT converge as a denylist" / "BEST-EFFORT gate" / "NOT a release blocker"）、`:1626-1647`、attribute-target 检测 `:1706-1714`。
- **round-18（`9bbb3a6`）**：best-effort 加固已知形态（见 §三），加残余注释。preflight 绿，等第 12 轮外审。

### 4.5 结论 + 贯穿全程的字节不变量

**结论（owner + 我方共识，但新工程师有权重判）**：close-kernel 结构性 BLOCK 经 round-15→18 已清零，残余明确归**三类**，全靠 conspicuous-diff + 人工 clean-review 兜底（详见 §五）。

**两个字节不变量（Opus 版核过 blob OID）**：3 个 runtime 文件的 git blob OID 从 round-5 到 round-18 **全程未动**：
- `2f55bc65` = `pr2_l0_micro_verifier_core.py`
- `af276679` = `pr2_l0_true_verifier_child.py`
- `da326456` = `exact_campaign.py`

每轮变的只是 checker（`check_p1_2_proof_obligations.py`）+ `certified_artifact_contract.py`（V99 楼面里的信任锚）+ 测试 + obligations manifest（`p1_2_proof_obligations.json`）。**这意味着：这十几轮全在加固"门"，没动被门保护的"证明逻辑本身"。**（Codex 版同样确认"3 runtime close-kernel 文件字节未动"，未给 OID。）

---

## 五、三类已接受残余与边界（转移，不是消失）

round-18 后 close-kernel 第二道门把残余明确归为三类，**边界从机器结构门转移到 source-sha / V99 floor / 人工 clean-review**：

1. **F / #5-F：import-time 执行完整性**——图灵完备执行面，对可 reseal 的维护者靠 AST shape 穷举不可收敛。cc_memory `pr2-5-round10-11-12-fspinout`、`close-kernel-ast-checker-design-lessons`。
2. **checker-self**——自完整性机器不能完全递归自证；能 reseal checker 的维护者本可掏空自校验机器，checker 源码注释自承这层冗余。**⚠ Codex 版补充判据**（cc_memory `gate-self-check-whitelist-not-blacklist`、`pr2-5-round14-11th-review-block-round15`）：**silent 必封；可结构性收紧的 checker-self 不得偷归残余；只有"必须改 checker 本体才能绕"的不可约类才进残余**。round-14/15 曾把可约的 C-a..e 修掉。
3. **A4 动态反射重绑**——反射面无限，witness 已 source-sha 钉死；owner 2026-07-02 接受为 best-effort / clean-review 残余，代码注释直接把它与 F、checker-self 放入同一 accepted-residual class（`9bbb3a6:scripts/check_p1_2_proof_obligations.py:1626-1636`）。

**这三类不是"证明消失"而是"边界转移"**：新工程师应独立判断这个边界是否合理，不应把它当成天然正确结论（见 §十一 盲点 A/B）。

---

## 六、release 仍被手动门卡死

**⚠ 两版从不同权威文件引同一事实，均保留（互补，不冲突）。**

**Opus 版**（直接读了 gate JSON 全文）：`data/review_gates/phase_1_2_spike_close.json`
- `"status": "blocked_manual_review_count"`，`owner_manual_state.p1_2_close_status: "not_closed"`，`p1_3b_entry_allowed: false`。
- **计数权威在仓库外**：`counting_authority: "owner_manual_count_outside_repo"`，`repo_derives_clean_count_from_receipts: false`。仓库**故意不记录也不计算** 0/3、1/3、2/3、3/3。
- 标准：`required_consecutive_clean_full_reviews: 3`（三次连续 clean 全面外审）。
- 打破 clean 的 finding 类：`unsound_cut` / `certified_false_negative` / `proof_obligation_bypass` / `fake_certified_claim` / `reachable_phase_gate_false_ready`。
- **receipt / report 只是 informational**，不是 machine authority，开不了门。`main.py` 结构 checker PASS / 测试通过 / 一个 seal 方法调用**都不能**推导出 P1.2 已 close。
- `current_review_anchor: "v99_p1_2_close_kernel_sealing"`——v99 是最后一个 owner 批准的锚点；v99 之后的工作树改动（PR1 发布面、PR2 全部）**都不被那个旧 source-hash seal 覆盖**，需要 fresh 重封 / 重验。
- **发布闭合的 6 个必要条件同时成立才能改 closed**：①producer 只提 proposal + 存在受支持可审计的独立 supervisor invocation surface（PR2 #7 已由 `scripts/run_supervisor_seal.py` 满足）②fixed-witness / sink replay / terminal evidence / disk-current 全 fail-closed ③publish gate 明确 owner-closed ④PR2 TCB / snapshot immutability / archive policy 未决项完成并有红测 ⑤close-kernel checker + targeted soundness tests + full gate 在同一工作树通过 ⑥owner 显式关闭 manual gate。**当前只满足其中一部分。**

**Codex 版**（引 PROJECT_LOCK 行号）：`PROJECT_LOCK.md:130-137`——owner manual gate 仍是 `blocked_manual_review_count`；`main.py` 终点仍 `CANDIDATE_PROPOSED`；任何 checker PASS / 局部回归 PASS / 内部 supervisor seal 都不得改写为 owner 已关闭 release gate。2026-07-04 更新：生产 supervisor 调度入口已由 `scripts/run_supervisor_seal.py` 落地，但 owner manual gate 未开、PR2 TCB 收缩 + release snapshot/policy 收口仍未完成。`PROJECT_LOCK.md:179-184`——不得从 receipt / 报告 / package metadata / source-tree manifest / clean-count / 内部 seal 自动推导 P1.2 closed / P1.3 allowed。发布链结构见 `NAV_MAP.md:31-43`；`CLAUDE.md:8-31` 同口径。

**共识**：round-18 即使第 12 轮 GPT Pro CLEAN，也只支持"merge PR2 #5 这部分 hardening"，**不支持"P1.2 已认证 / 已发布"**。

---

## 七、dependency-floor manifest 是 deploy-pending 占位（生产前必须重生成）

**主源**：cc_memory `pr2-8-9a-hardened-landed-099f5a3`；harness RESUME。

- **PR2 #8/#9a 已合 main 历史**：merge `099f5a3`（PR#2），含 #8 删除 close-kernel 自跳过、#9a floor 清单 / 生成器纳入 close-kernel pin，以及 GPT Pro 多会话 panel 挖出本地审漏的 **#8-A / #8-B / #9a-A 三个 BLOCK**。**关键教训**：信任锚必须进 source-sha 楼面；**gate 钉了不等于 runtime 钉了，pin 必须到真正 runtime 消费点**（否则 TOCTOU 时序旁路）。
- PR2 #9a 加了 L0 runtime byte-pin dependency-floor manifest（size/sha drift fail-closed）+ 删掉 runtime auto-generate，堵"gate 过后 mint 前换 manifest 用未审 floor"的时序旁路。
- **但 manifest 内容当前钉的是【审计 Linux dev/CI 环境字节】（GPT Pro 沙盒生成），不是【生产审过的 canonical】**。已标 `manifest_provenance_status: deploy_pending_placeholder_regenerate_on_production_cachyos_py313`。**⚠ Codex 版补 file:line**：注释见 `9bbb3a6:src/search/pr2_l0_micro_verifier_core.py:39-46`；provenance 字段见 `9bbb3a6:data/proof_obligations/p1_2_proof_obligations.json:906-918`。
- **生产部署前必须**：在 **CachyOS + Py3.13 venv** 跑 `scripts/generate_pr2_dependency_floor_manifest.py` 重生成 → 审字节 → 替换占位 → 重钉 SHA/size 重封（= PR2 task #6）。
- **本机（Windows/WSL=Ubuntu）生不了**：无 CachyOS distro、无 Py3.13 venv（CachyOS 是双系统另一启动项，要重启进）。runtime byte-pin / fail-closed 机制是 host-independent、已完整；只 manifest 内容待生产 host 落实。**被否决的替代方案**：把 dev/CI 占位字节说成生产审过 canonical（会掩盖 deploy risk）。

---

## 八、PR2 剩余项清单 + 推荐序 + 各自状态

**权威主源**：cc_memory `pr2b-landed-pr2-remaining-status-20260628`（含 file:line）；`docs/项目说明/soundness_gap_roadmap.md`（状态矩阵，注意 IMPLEMENTED ≠ P1.2 CLOSED）；F 线 harness `pr2-5-F-line-import-time-integrity-schedule.md`。

**关键教训**：一个 Explore 子代理曾把 #1/#2/#3 浅核判 DONE（理由：L0 核零 import、有 `-I -S -B`、fd 原子写）；codex 对设计标准严审打回 **partial**——快照仍扫全 `src/`+`scripts/`、child 仍 `from src.search...` import 项目域模块 = 不是"最小 TCB 闭包"。**别信"定位到表面证据就算 done"的浅核。**

| # | 项 | 状态 | 量 | file:line / 备注 |
|---|---|---|---|---|
| 4 | B4 `-I -S -B` 子进程隔离 | ✅ done | 小 | 已闭 |
| 8 | argv0/contract 内容 digest | greenfield | 小 | `certified_artifact_contract.py:112-123` 仍全信 `sys.argv[0]` 认 checker 身份 |
| 9a | floor 清单+生成器 close-kernel pin | partial | 中 | 生成器曾未进 pin map；#8/#9a 硬化已合 main（见 §七） |
| 5 | B2 候选域独立枚举 | **partial（close-kernel 结构门部分已 `6e06922` 合入 main;B2 独立枚举本身仍未做、未排期）** | 中 | `pr2_l0_true_verifier_child` ~403-417 仍信 producer candidate_generation |
| 2 | 受控 loader 最小快照+fd | partial | 中 | 快照仍扫全 src；当前未达设计标准的最小 TCB 闭包 |
| 3 | B3 全程 fd-held read-once | partial | 中 | 现在是 path re-read（two-points-in-time 风险），非 fd 持有；需把读入+验证绑到 fd-held snapshot |
| 7 | certify 生产入口 | ✅ landed 2026-07-04（`scripts/run_supervisor_seal.py`） | 中 | **`main.py` 仍停在 `CANDIDATE_PROPOSED`，seal 由独立命令从 marker 驱动**；通电只补 supervisor 可执行入口，不等于 P1.2 closed |
| 1 | L0/L1 最小 TCB 闭包（含 #5-F part1+2） | partial | 大 | 快照扫全 src、child import 项目域；#1 是最小 TCB 与 verifier 语义边界；硬骨头；**别把 F 的 best-effort 当已闭** |
| 6 | AST 可达性闸 | **已决定不另建**（可被新工程师重审） | — | checker 注释自承 reachability 是冗余层、主防线是源码 sha 楼面（已被 #8-B 强化） |
| 9b | OS 级写隔离 | greenfield | 大 | Linux uid namespace/seccomp、Windows 写隔离都 pending |
| 9c | 原生 .pyd/.so TOCTOU | partial | 大（随 9b） | `_RehashingExtensionFileLoader` 尽力重核，残留声明 NAMED-TCB / host-local 风险 |

**#5-F（import-time 执行完整性）专门线** scope 三部分：
- ① import-machinery 完整性（**有界**：全 SOURCE_SUFFIXES/.pyw + EXTENSION_SUFFIXES/.pyd/.so + namespace package + `scripts.*`）
- ② 动态 import 完整性（**有界**：堵所有 `importlib`/`__import__`/`__dict__` 下标/getattr/runpy/exec 拼路径）
- ③ **非-import import-time 副作用（开放，需设计 spike）**：metaclass/`__init_subclass__`/descriptor 副作用等——AST shape 扫描穷举不完，三选一：(A) 继续追完整、(B) 重构让 close-kernel TCB 的 import-time 执行最小化（减攻击面）、(C) 接受为残余 + V99 whole-file floor + 人工 reseal 复审兜底。
- **归属**：紧邻 #1（本质是 #1 的 import-time 子 scope），非 release 关键路径。

**推荐执行序（owner 方向，轻→重，go-live 最后）**：第 12 轮 CLEAN 后先 merge #5 结构门 → #8 argv0 → #9a floor pin → #5 B2 枚举 + #2/#3 loader/read-once 精化 → #1 最小 TCB 闭包（含 #5-F part1+2、part3 设计 spike）→ #9b OS 隔离（+#9c）→ **#7 certify 入口（最后通电）**。硬骨头 = #1/#9b/#9c + #5。参考 `p1-2-resume-state-20260621.md:14`。（2026-07-04 注:此为当时方向。实际后续:#5 结构门未再走第 12 轮、round-19/20 本地收口后直接合入 `6e06922`;#7 已通电 `349c56c`;其余深化项转未排期真实 backlog——owner 澄清画 TCB 线只停外审循环、不取消这些待办。）

---

## 九、已否决 / 搁置的路径（防重蹈）

1. **继续在 A4 动态反射面上逐轮硬化到"完全闭合"** —— 被 owner 否决为 release blocker。理由不是"这些绕法安全"，而是 round-15→18 已实证 denylist/blanket 都会继续漏新 Python 反射面；收益递减，且 witness body 已 source-sha pinned、攻击必产生显眼 diff。替代"重构 witness 体 whitelist"判高风险 / 大改 / 可能误伤，未选。
2. **把 F import-time 完整性放在 #5 gate 内继续追** —— 拆出为专门线 #5-F。cc_memory `close-kernel-ast-checker-design-lessons`：import-time 图灵完备；形态扫描每轮会在最新补丁里再挖一个洞。结构门可落地，F 单列。
3. **把测试通过 / checker 绿 / 内部 seal / 外审 clean count 自动变成 release closure** —— 被 `PROJECT_LOCK.md` 否决。release 需 owner 手动 gate；任何自动推导 P1.2 closed 的路径都 forbidden。
4. **⚠（仅 Codex 版记录）审查路由**：用 workflow 派 opus/claude 做审查已被替换为"**本地 codex 审修 → GPT Pro relay**"。cc_memory `review-routing-codex-local-then-gptpro-relay`：审查不再烧 Claude 额度，但保留跨模型独立性；Claude/本席角色 = 编排、终裁、重封、跑全量 preflight。这是工作流选择，不是 soundness 证明。
5. **#6 AST 可达性闸** —— 已决定不另建（checker 注释自承 reachability 冗余、主防线 source-sha 楼面已由 #8-B 强化）；此裁定可被新工程师重审。

---

## 十、未决残余（押后，已登记别丢）

- **`pr2-resume-envelope-deferred-finding`**（cc_memory，commit `05a2a85`）——第 3 轮复审 05 挖出 resume-envelope 的 `created_at` 等非证明字段克隆进 durable 会过终态门但 resume 自拒；owner 拍押后归 #2/#3 envelope 硬化或单列。（仅 Opus 版列出，Codex 版未提；保留。）

---

## 十一、开放问题 / 可能盲点（对"让新 CC 从零摸索、发现我方盲点"最关键，两版高度收敛）

> 这一节是给新工程师【独立再判】的空间。以下都是我方尚未定论、或明知有洞、或从未被对抗审覆盖的地方。别默认我方结论对。

### 盲点 A：close-kernel「第二道门」这个进路本身对不对？

- **现状**：AST 二道门从 round-3 折腾到 round-18（十几轮），每轮外审都能挖出新形态，最后 owner 拍板接受三类残余，靠 conspicuous-diff + 人工 clean-review 兜底。
- **元教训**（cc_memory `close-kernel-block-convergence-trend-20260630`）：对图灵完备语言 + 反射面做逐形态 denylist **永不收敛**；该早识别并归"conspicuous-edit 残余"而非无限迭代。round-15 才从 denylist 转 whitelist/blanket，round-17 A4 才认输接受残余——**这个转向本可以更早发生**。
- **未决元问题**：既然三个 runtime 文件的字节 18 轮全程未动、第一道门（整文件 source-sha256 楼面）本就能让任何篡改触发 freeze-ritual 人工重钉审 diff——**那这道耗了十几轮的 AST 二道门，相对"只靠 byte-pin + 人工 clean-review"到底净增了多少安全？值不值这个复杂度？** 它把 checker 本身变成了一个复杂的、需要自证完整性的攻击面（checker-self 类残余正是它自己引入的）。成本 / 收益从未被独立结算过。新工程师有权给出"二道门不该做 / 该做得薄很多"的不同判断——owner 想要的正是这种独立视角。**这不是数学定理，是中间路线。**

### 盲点 B：接受 3 类残余的取舍、边界画得对不对？

- **理论依据**（cc_memory `close-kernel-ast-pin-structural-vs-semantic-boundary`）：AST 门只能保护"结构"、保护不了"证明数学"；大型终态校验函数**内部数学** + 叶子 helper 函数体（如 `_build_occupancy_prefix`）划给"sha 楼面 + frozen 工件 hash + 人工重钉审查"。
- **这个划界依赖三个假设**，任一不成立边界就塌：① 输入是 frozen 工件且被 preflight hash 钉；② 任何篡改改 runtime sha → 触发 freeze-ritual = 人工审 diff；③ 篡改在 diff 里"扎眼"。**第 ③ 条最软**——"扎眼"是人的主观判断，`mandatory_instances=[]` 扎眼，但一个数学上等价掏空的巧妙改动**未必扎眼**。**"人工 clean-review 一定逮得到"从未被验证过**（计数在仓库外、我方看不到 owner 实际怎么审的）。
- 唯一被单独兜的隐蔽异常是空矩形 off-by-one（`_empty_rect_exists` 的 `+1` 消失不扎眼）→ 用执行型 canary。**"还有哪些语义掏空同样不扎眼、却没有 canary"是开放的。**
- **重开条件**：若能构造 silent / non-conspicuous / 不动 checker 逻辑且忠实 reseal 后仍绿的路径，这个裁定应重开。第 12 轮 GPT Pro prompt 已专门要求审 residual boundary；**回传前别把 round-18 当最终 clean**。

### 盲点 C：F 线 import-time 无界最终怎么收口？

- owner 拍板单列专门线（#5-F），part 1+2（有界）可实现，**part 3（非-import import-time 副作用）是开放设计问题**，三选一（追完整 / 重构最小化 import-time 执行面 / 接受残余）尚未定，**没做过设计 spike**。
- **我方倾向**是重构最小化（B）或接受残余（C）。新工程师从零看，可能发现"L0 TCB 根本不该有 import-time 副作用"这种更干净的架构切法——值得独立探。

### 盲点 D：throughput（吞吐）认证是不是死路？

- **我方结论：是死路，但不是排期能绕的死路，而是 paradigm 级开放问题。** **⚠ 两版引不同 PROJECT_LOCK 段落，均保留**：
  - **Opus 版依据**（cc_memory `throughput-cert-blocked-by-9-family-frozen`）：§4:274 锁死"diagnostic flow checks 当 certified proof"为 Forbidden Change；`flow_subproblem.py:4-9` 同锁（flow 是连续 LP/GLOP 松弛，只诊断不盖章）；§3A 9-family frozen（`PROJECT_LOCK:179-209`）把 cut framework 焊死成 area/几何/literal 三类静态推理、**无任何 family 表达"离散容量流够不够"**；§4 round22 F16"代数归 Master、几何归 Cut"二分法两边都不收吞吐；`PROJECT_LOCK:320` 明列 throughput-manifest 为 postprocess-only 不得升 certified。
  - **Codex 版依据**：`PROJECT_LOCK.md:100-116`——当前 certified 命题只证 routing 连通，不证物料离散吞吐 / belt 带宽容量；flow 子问题 diagnostic-only、绝不 gate。
- postprocess 的三态吞吐审计（`src/adapters/industrial_planner/throughput_audit.py`）的 `proven_equivalent` **只证"静态台数/槽数计数 ≥ 需求"（必要条件），不证"98% 密度离散带子在空间里真能把货流到"（充分条件）**（cc_memory `throughput-audit-proven-is-static-count-not-flow`）。
- **当前诚实 certified 口径**（C3 审定）：证 布局 + 连通（有路） + 供电覆盖 + 资源数量够；**不证 吞吐 / 容量**。要纳入吞吐 = 改 theorem scope + 新 proof paradigm（开 F10、解冻 §3A / 新增离散容量子问题 + 改命题 P）= 研究级，归 Phase 2+。
- **新工程师值得判**：这个"死路"判定建立在 PROJECT_LOCK 那几条 invariant 上；如果那些 invariant 本身被重新审视（比如"9-family 真的穷尽了 certified 需要的 cut 类吗"），死路可能变活路。但这是**范式入口**，不是工程活。

### 盲点 E（两版都判"最重要"）：算法核心 soundness 有没有被"gate 绿灯"掩盖？

**这是最该被独立重审的地方。** 观察到一个**结构性不对称**：

- **发布 / 终态面被审了几十轮**（收益递减）：gate 文件 `informational_history` 记录 V28→V99 **70+ 个外审包**，每个都找到真的 soundness bug（V79 域切片、V82 orientation-sensitive 域、V83 forged checkpoint、V84 "证了存在没证最优"、V86 power witness、V90 field allowlist……）。发布面 / terminal-evidence-validator 是全项目被对抗审最密的地方。
- **但求解算法核心（master/binding/routing 的 `max_lex(area,min_side)` 正确性）被审得相对少**。C3 内核审（cc_memory `p1-2-c3-kernel-audit-3source-20260620`，三源：claude+codex+GPT Pro）明确留了洞；Codex 版补 `PROJECT_LOCK.md:31-77` 列 6 个 gating 谓词 + lex 最优性，涉及文件 `master_model.py`（Codex 版补）/ `exact_coordinate_master.py` / `binding_subproblem.py` / `routing_subproblem.py`：
  - **I1（nogood ⊆ 真不可行）** 曾是 CRITICAL GAP：whole-layout INFEASIBLE nogood 落 cut 前**零独立 ⊆-infeasible 复验**，能造成 proof-bearing false-INFEASIBLE（over-constrained 子问题 CP 模型 → 误剪真可行布局 → 抹掉真最优 → CERTIFIED 次优）。**现在 roadmap 标 IMPLEMENTED**（`benders_loop.py:7538-7585` + `independent_infeasibility_reverifier.py`），**但注明"只覆盖登记的 whole-layout nogood 路径，不自动证明未来 cut family"**——复验器只兜住当前那一条路径，不是通用防线。
  - **子问题 CP-SAT 编码忠实性从未被逐约束审**：C3 明写"两源都没做子问题编码忠实性逐约束审"。若 routing 模型多加一条不该有的约束，它会自报 INFEASIBLE、生成 sound 形状的 nogood cut、剪掉真可行布局，而 I1 复验器（用同源 / 同编码）**抓不到**，gate 全绿。
  - **F7/F8/F3 三条 latent false-INFEASIBLE 雷**（cc_memory `p1-2-c4-c5-...`，⚠ Opus 版此 id 不完整）：`power_cover.py:45`（欧氏圆 vs 方形覆盖）、`power_network.py:69`、`candidate_placements.py:58-63`（N/S 端口朝向算反）——cut 家族各自重算认证几何量、定义跑偏。**当前全 latent**（生成器 env 默认关、`benders_loop` 从不调用、`step_8_apply_to_master` 是 `NotImplementedError`），不喂认证 = 不 live。但 P1.3B 一旦把 cut 家族接进认证前，必须先 wire 到共享 canonical 原语 + 红测，否则激活即引入 false-INFEASIBLE。roadmap 标"canonical→geometry shared primitives = PARTIAL / NAMED TCB"。
  - **最优性 vs 存在性**：V84 外审发现 witness scan 只证了 claimed empty rectangle 的**存在**、没证**最优**；已 sealed，但"落地时把最优性 scan scoped 到 non-empty mandatory sets"——这个 scoping 是否覆盖所有情况值得复看。
- **"绿灯掩盖"的机制被 gate 文件自己承认**（gate 文件第 16 行、roadmap 第 4/16 行）：proof obligation close-kernel PASS **只表示登记结构一致，不证明 owner 已 close 或 full suite 已过，更不证明数学正确**。即 **close-kernel checker 绿 = 结构没被掏空，≠ 求解器算得对**。十几轮 close-kernel 硬化保护的是"发布链不被伪造"，**完全没碰"master/binding/routing 到底有没有算出真最优"这个更底层的问题**。
- **给新工程师的直接建议（owner 想要的独立摸索方向）**：发布面已审饱和；**真正未审透的是 `src/models/binding_subproblem.py` / `routing_subproblem.py` / `exact_coordinate_master.py`（+`master_model.py`）的 CP-SAT 约束编码忠实性，和 cut lifecycle 的几何原语一致性**。从零做一次"子问题编码逐约束 vs canonical rules 忠实性审计"，很可能挖出十几轮 close-kernel 硬化完全没触及的 false-INFEASIBLE / 非最优盲点。binding/routing 的 false-INFEASIBLE 会导致 false-CERTIFIED optimality，不能被"发布链 checker 绿"遮蔽。

### 盲点 F：从没被任何对抗审覆盖的面（覆盖面盘点）

**已审过的面**：PR1 publication chain、PR2 #5 close-kernel、PR2 #8/#9a floor/runtime pin、部分 parallel scheduler/reset 类历史漏洞。

**未充分覆盖 / 仍 pending**：
- **#2/#3 loader/read-once**、**#1 最小 TCB 与 #5-F import-time**（partial/large，见 §八）。
- **OS 级写隔离（#9b）**：Linux uid namespace/seccomp、Windows 写隔离都 greenfield，从没实现也没审。
- **原生 .pyd/.so TOCTOU（#9c）**：OR-Tools native extension 目前 NAMED-TCB（声明信任），`_RehashingExtensionFileLoader` 只尽力重核。
- **dependency floor 生产 host 字节**（见 §七，deploy-pending）。
- **cut-family 若未来接入 certified path 的完整生命周期**（见盲点 E F7/F8/F3）。
- **certify 生产入口（#7）本身**：`scripts/run_supervisor_seal.py` 已存在，但这是新落地的 go-live 通电点；它只补 supervisor 可执行入口，不能替代 PR2 #1/#2/#3/#5/#9、publisher gate 或 owner 手动门审查。
- **解释器 / stdlib / OS / 硬件**：一律命名 TCB（cc_memory `p1-2-review-converged-tcb-start-p1-3` 的核心认识：对抗审"永远能再剥一层信任洋葱"，witness→发布闸→验证器执行字节码→解释器→OS→硬件；**"审到零发现"不是收敛判据**）。
- 导航参考：`NAV_MAP.md:7-26`（当前 solve chain）、`NAV_MAP.md:43-50`（adapter/exporter 不是独立 authority）。

### 盲点 G：方法论层面的反复（值得警惕）

- **"审 CLEAN ≠ 全量绿"实证两次**（cc_memory `pr1-supervisor-mint-preflight`、`mock-based-patch-mock-unproven-preflight`）：子代理独立审一路报 CLEAN，但真问题全是我方自己跑全量 preflight 逮的（复验缺陷 + mock 没跟上新 sink 路径）。**认证核心改动必须自己跑全量 preflight，不能信子代理的审腿。**
- **"补丁不盲应用"**：GPT Pro / codex 给的补丁多次自带真 bug（把哨兵预解析成绝对路径致 child 拒 / ghost_pick 当 occupancy 会拒掉每个真终态结果 / reviewer patch 破坏真 solver 路径）——一律按 spec 自实现、我方终裁，不 `git apply` 对方 diff。
- **targeted 测试不够、必须完整 checker 单跑 + 全量 preflight**：round-15 就是 targeted 25 passed 但完整 checker 单跑才炸出 unregistered-sink（codex 没 reseal 从没跑过完整 checker）。

### 盲点 H：状态分裂（操作风险，Codex 版强调）

最新 round-18 只活在 harness RESUME + 本地 branch；cc_memory 只记到 round-14 / 更早；`main` 和 PR2 branch 都有本地 ahead/dirty；PR2 branch 未 push。新工程师若从 GitHub 克隆，只看到 `origin/main=5ab006f` 和 `origin/pr2-8-9a-batch=ec7dc52`，**不会自动拿到 `9bbb3a6`**。交接包若没含 `.git` 或没明确带上 branch/commit bundle，这段状态会丢。（呼应 §二 的未 push 风险。2026-07-04 注:已随 `6e06922` 合并解除;「记忆层滞后于 git」的模式警告仍值得记取。）

---

## 十二、给新工程师的硬指针（接手第一步）

1. **权威不变量看 `PROJECT_LOCK.md`**（F-*/PCR-*/CUT-* 失败关闭条款）；与任何旧笔记冲突以它为准。**⚠ 大小有出入**：Opus 版史料称 ~127KB；项目 `CLAUDE.md` 称 ~106 KB——以实际文件为准。
2. **certified vs exploratory 铁律**：`certified_exact` 是唯一能产证明材料的路径；exploratory 输出（caps/hints/probe/sidecar）永远不能升 certified。`min_side>=6` 是候选 admissibility、不是目标 tie-break；exact 模式**没有**硬"50 电线杆+10 协议箱"上限（那是 exploratory-only 指导）。
3. **`main.py` 正常链止于 `CANDIDATE_PROPOSED`**；`supervisor_seal()` 的生产调用方是独立的 `scripts/run_supervisor_seal.py`；**别把"方法存在 / 测试调过 / 入口存在"当"已发布 CERTIFIED"**。
4. **改 frozen 工件 / v99 sealed sink = freeze-ritual**：更新 `scripts/preflight_gate.py` 的 hash + 重封 allowlist/obligations/checker 自钉，**LF only**（CRLF 会导致本地过 / CI 挂，cc_memory `p1-2-fix-1-close-kernel-crlf` 有血教训）。
5. **status 矩阵**：`docs/项目说明/soundness_gap_roadmap.md` 是所有 soundness gap 的 IMPLEMENTED/OPEN/PARTIAL/OUT-OF-SCOPE 权威表（**IMPLEMENTED ≠ P1.2 CLOSED**）。
6. **接手障碍提醒**：PR2 #5 全部 26 个 commit 在本地分支 `pr2-5-domain-frontier-gate`（HEAD `9bbb3a6`，worktree `.claude/worktrees/pr2-5-round10`）、**未 push**——新机器拿不到，需 owner 把这条分支带过去；且最新 round-15→18 完整故事只在 harness RESUME + git、尚未进 cc_memory。（2026-07-04 注:此条已失效——`6e06922` 合入后 main 自带全部 close-kernel 工作。）


---

*(文档结束。若你要复核任何 exactness / 认证断言,起点:`PROJECT_LOCK.md` + `scripts/check_p1_2_proof_obligations.py` + 相应 gate + 目标测试。)*
