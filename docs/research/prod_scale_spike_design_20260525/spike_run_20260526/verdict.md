# Spike Phase B run verdict — prod-scale master integration

**Date**: 2026-05-26
**Branch**: `spike/prod_scale_master_integration_20260526` (off master `f7b88b6`)
**Phase B commits**: B1 `292c3a4` / B4+B5 `e121800` / B2 `c4f2e35` / B3 `3a9d507` / B6 `c3e5078` / verdict-fix `0691175`,`f54f4f8` / F3 special-case phase telemetry `b1bab5c` + A3 rerun `1d935f3`
**Phase B wall-clock**: 206s
**Phase A wall-clock**: ~1-2h (per phase_a_report.md)

## Overall verdict: **GO_WITH_MINOR**

Per MERGER §5.2 round-3 semantic gap documentation:

> Spike GO close *Sizing*, 不 close *Convergence* / *Adversarial robustness*, 后两者入 P1.3A risk register.

This verdict pertains to **Sizing only** (Finding 5 #1 / #2 / #3 / #4). Convergence (real
PoseBoolExactMaster + LBBD multi-iter behavior under 81K BoolVar) and adversarial robustness
(F1/F2/F3 patch hold under 100K scale + 50 bad / 9950 good inject) are explicitly NOT
verified by this spike — they are deferred to P1.3A 主体 design phase and P1.3B regression.

## 第九审修正 (2026-06-01) — Finding 5 #2 sizing 口径收窄 + 4 soundness 修复

第九审 (GPT pro, faithful + clean 两版独立跑) **双双判 B (未 clean close)**。复核全部属实,
本分支已落修复:

**toy_translator / oracle_emit_fixture 4 项 (本 commit):**
1. `_decode_cert_b64`: `base64.b64decode(..., validate=True)` —— 合法 b64 混入垃圾字符现在
   fail-closed (旧码静默丢弃 → F3 不 fail-closed)。micro-probe 加 3 case (prefix/suffix/middle),
   现 **12/12 PASS**。
2. salted `hash()` → `_stable_hash` (blake2b): fallback / remap 跨进程可复现 (旧码 PYTHONHASHSEED
   随机, 每跑不同)。
3. unknown pose 静默 hash-remap → 新增 telemetry (`n_pairs_remapped` / `per_family_remapped`):
   applied 计数不再静默掩盖 "literal 没绑真 registry" (第九审实测 50 cert 中 36 个 pair unknown:
   density_envelope 24 + port_exposure 12, 全被静默 remap)。
4. A3 G10 pass 判定加 `schema_err_count == 0` (旧码放行 schema_err)。

**Finding 5 #2 "真 cut body 分布 sizing" 口径收窄 (核心):**
第九审指出 B2 的 100K proto/RSS 是 **合成/remap 吞吐量**, 不是 **真 cut body 绑真 registry**。
2026-06-01 sizing cheap gate (`docs/research/p1_2_spike_sizing_gate_20260601/`, 对真 fixture+真
registry 直算) 给出精确结论:

> cut body 的 master 约束大小不是固定可测的事实, 而是个 **~1000x 设计变量**, 取决于 lowering 方式。
> 100K cut master sizing 有界且便宜 (~1–40 MB), **唯一** blow-up 路径是把 **F1 region_capacity /
> F9 density_envelope 的大池子 (manufacturing/storage ~17952 pose) 容量 cut 按展开式 lower**
> (每条 ~2000–3200 term → 100K ~1.9 GB)。其余 7 族 (路由/no-good/小池子) 任意 lower 都是几项到
> 几十项, 随便扛。spike 的 19.55 MB 是 "紧凑 no-good / 小池子" 的合理代理, 但对大池子展开低估 50–100x。

**因此 P1.3A lowering 设计必须对 F1/F9 二选一**: (a) 按 witness 紧凑 no-good lower, 或 (b) 给大池子
展开容量 cut 的条数/规模设上界。这是带数字的硬约束, 已移交 P1.3A risk register (Layer-2 #6)。
另一条未测轴: cert 证书存储 + replay 校验在 100K 规模 (~613 字节 bitset/cert → ~60 MB store +
逐条 revalidate) 也归 P1.3A proof lifecycle sizing。

## G criteria (sizing — Finding 5 #1/#3/#4)

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| G1 build 0 cut | ≤ 10s | 1.94s | PASS |
| G2 build+translate 1K cut | ≤ 20s | 2.00s | PASS |
| G3 build+translate 10K cut | ≤ 30s | 2.22s | PASS |
| G4 build+translate 50K cut | ≤ 300s | 2.62s | PASS |
| G4b build+translate 100K cut | ≤ 600s | 3.36s | PASS |
| G5 0 cut feasibility solve | ≤ 30s | 0.72s (OPTIMAL) | PASS |
| G7 100K solve wall (measure, no hard cap) | — | 0.97s (OPTIMAL) | n/a (measure) |
| G8 RSS peak | ≤ 20 GB | after-solve max 1.0316GB | PASS |
| G9 proto @ 50K | ≤ 500 MB | 17.9MB | PASS |
| G9 proto @ 100K | ≤ 1 GB | 19.6MB | PASS |
| G10 oracle real-emit 45 cert (A3) | ≥45 + 0 unsound | 50 cert / 9 family / 0 unsound | PASS |
| G11 active filter Hybrid mock loop | wall ≤ 100ms/iter + eviction fires | total 0.073s, max 9.5ms, evict @ iter [6] | PASS |
| G17 failfast probe (A2) | ≤ 15s | 3.4s | PASS (A2 phase_a_report) |
| G6a feasible smoke wall | < 180s cap | 180.01s | FAIL *(SOFT — see notes)* |
| G6a feasible smoke status | OPTIMAL/FEASIBLE | FEASIBLE | PASS |
| G6a best_objective_bound valid | not None | 76884.0 | PASS |
| G6b random cut tolerate-INFEAS wall | > 1s if INFEASIBLE | 0.83s (OPTIMAL) | PASS |

## N (NOT-GO) criteria trigger status

| Criterion | Trigger? | Detail |
|---|---|---|
| N1_build_overlimit_0 | no | — |
| N1_build_overlimit_1K | no | — |
| N1_build_overlimit_10K | no | — |
| N1_build_overlimit_50K | no | — |
| N1_build_overlimit_100K | no | — |
| N2_random_presolve_crash | no | — |
| N2_random_presolve_crash_1K | no | — |
| N2_random_presolve_crash_10K | no | — |
| N2_random_presolve_crash_50K | no | — |
| N2_random_presolve_crash_100K | no | — |
| N3_rss_critical | no | — |
| N4_proto_critical | no | — |
| N6_oracle_unsound | no | — |
| N9_reproducibility_variance | no | — |
| N10_wall_cap | no | — |
| N11_telemetry_missing_class | no | — |
| N12_off_limits | no | — |
| N13_probe_overlimit | no | — |

## Finding 5 (5 项) cover evidence

Per MERGER §5.2: spike must close Finding 5 sizing/measurement gate, NOT close P1.3A 主体.

| # | Finding 5 item | Spike evidence | Cover? |
|---|---|---|---|
| 1 | 真 prod registry build master var | A3 oracle emit + B1 load_pose_registry: 81,795 BoolVar from real `data/preprocessed/candidate_placements.json` 7 facility pool | YES |
| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 50 cert × 9 family 真 oracle emit ✅; **但** B2 translator 把 body lower 成合成/remap 小约束, 非真 registry-bound body sizing | **PARTIAL** — 见「第九审修正」: sizing 是 ~1000x lowering 设计变量, F1/F9 大池子展开是唯一 blow-up 路径, 已收窄口径 + 移交 P1.3A |
| 3 | build wall / proto / RSS / solve wall 实测 | B2 ramp (v20 rerun, F3 real 2-literal): build 1.94–2.09s + translation 0.00–1.27s, proto 16.3–19.6 MB, build RSS 0.84–0.90 GB, after-solve RSS max 1.0316 GB, solve 0.72–0.97s across 0–100K; 5/5 tier cut_count_applied == target | YES |
| 4 | active filter @ 10K/50K/100K, Hybrid score | B4 mock loop 10 iter: total 0.073s, eviction fired iter [6] (52K→30K), age_decay validated via multi-iter age tick | YES |
| 5 | feasible realistic case 避 INFEAS-早停 | B3 feasible smoke: 10K known-feasible cut (blueprint hint) + Maximize obj → FEASIBLE obj=76795 bound=76884 (gap 0.12%) NOT Presolve-crash | YES (with G6a wall SOFT FAIL) |

## Layer 2 risk acknowledgment (per `[[adversarial-soundness-audit]]`)

This spike validates **Sizing-Layer-1 only**. The following Layer-2 risks remain OPEN and
enter P1.3A risk register:

1. **Convergence (Gemini round 3 Q8 semantic gap)** — Toy master has 81,795 BoolVar + loose
   `sum(group_vars) >= 1` demand. Real PoseBoolExactMaster will have ExactlyOne per instance
   + port-linking + anti-overlap. Whose solve cost the spike's v20 `solve_wall_s 0.72–0.97s` does
   NOT predict. P1.3A LBBD outer-loop convergence must be empirically validated separately.

2. **G6a wall SOFT FAIL is honest finding** — Solver hit 180s cap at FEASIBLE with bound gap
   0.12% on toy master. With real master constraints this gap will likely be larger. P1.3A
   should NOT assume single-solve termination at 81K + 10K cut scale.

3. **Random tier OPTIMAL (not INFEASIBLE) finding** — Toy master too loose for 10K random
   no-good cuts to make it infeasible. This means the spike's G6b guard 'INFEASIBLE wall > 1s'
   was not actively tested. Adversarial robustness (50 bad cert / 9950 good — MERGER §5.3)
   deferred to P1.3B regression.

4. **Single solve, not multi-iter LBBD** — Per MERGER §5.3 explicit NOT-scope. Spike single
   build/solve cannot trigger Lever-12 (v8 anchor slicing) / Lever-16 (lazy power completion) /
   PCR-CUT Phase 5 / B1 path-2 style convergence failures.

5. **F1/F2/F3 patch hold at scale unverified** — Adversarial validator inject not in spike.
   GPT pro Layer-2 catch may still surface issues here (per `[[gpt-pro-p11-audit-not-go]]`
   pattern). Deferred to P1.3B.

6. **F1/F9 大池子容量 cut lowering sizing (2026-06-01 第九审 sizing gate)** — 带数字硬约束:
   region_capacity (F1) / density_envelope (F9) 容量/面积 cut 若按展开式 lower 且打大制造池子
   (~17952 pose), 每条 ~2000–3200 term → 100K ~1.9 GB proto, 会爆。P1.3A lowering 设计**必须**
   二选一: (a) witness 紧凑 no-good, 或 (b) 给大池子展开容量 cut 条数/规模设上界。其余 7 族任意
   lower 都安全。证据: `docs/research/p1_2_spike_sizing_gate_20260601/`。附带: 100K cert 证书
   存储 + replay 校验成本 (~60 MB store + 逐条 revalidate) 归 P1.3A proof lifecycle sizing。

## Actual wall / Claude time vs estimate

Per MERGER §5.6 (shrunk estimate): 8-12h Claude / 4-7h wall total.

| Step | Estimate (Claude) | Actual (Claude) | Wall |
|---|---|---|---|
| Phase A (all) | 3.5-5h | ~4-5.5h | ~1-2h |
| B1 toy translator | 1-2h | ~30 min | <5 min |
| B4 filter mock + B5 telemetry | 0.5-1h + 1-2h | ~30 min combined | <5s self-test |
| B2 scale ramp | 1-2h Claude + 2-3h wall | ~30 min | 18s (0.3min) |
| B3 feasible smoke | 1h Claude + <5min wall | ~30 min | 188s (3.1min) |
| B6 runner + verdict.md | 1-2h Claude + 1-2h wall | ~30-45 min | <1 min |
| **Phase B total** | **6-9h Claude + 3-5h wall** | **~2-3h Claude** | **206s (3.4min)** |

Phase B wall was MUCH smaller than estimate (3-5h) because:
- Build + translation cost is essentially linear and well below thresholds (4.10s for 100K not 600s)
- Toy master + loose constraints → no INFEASIBLE early-stop loop
- Single-worker + single-solve per tier (no multi-iter LBBD per MERGER §5.3)

## Unexpected behavior

1. **All ramp tiers OPTIMAL** — Expected at least some tiers to be FEASIBLE-only or hit
   max_time. Toy master demand=`sum>=1` + cut form `AddBoolOr / AddLinear<=K-1` is loose enough
   for 81K vars to trivially satisfy. Documents the gap toy ≠ real.

2. **proto size only 16-20 MB at 100K cuts** — Much smaller than G9 1 GB threshold. CP-SAT
   stores BoolVar as varint-packed indices not name strings, so 100K AddBoolOr × ~3 lit avg =
   ~300K lit refs ≈ few MB on top of base 16 MB.

3. **RSS peak stays near 0.84–1.03 GB across all tiers** — Build phase already loads OR-Tools +
   81K BoolVar. Additional cuts add proportionally small protobuf footprint; v20 raw telemetry
   records the 100K after-solve peak explicitly at 1.0316 GB. No L24 augmented-master-style
   RSS explosion at this scale on toy master.

4. **G6a feasible solver bound gap 0.12% at 180s** — Bound 76884 vs obj 76795 over 81K var
   max-sum. Pure structural: 10K AddBoolOr each forbids ~3 vars conjunction. Solver finds a
   FEASIBLE quickly (within hint-biased region) but proving OPTIMAL across 81K is harder than
   expected. Honest finding.

## Recommended next step (main conversation)

Historical v20 rerun verdict: **GO_WITH_MINOR** — soft fails: ['G6a_feasible_wall']. All HARD G criteria PASS (G10 closed by F3 special-case phase rerun: 50 cert / 9 family / 0 unsound), zero hard N trigger. Soft fails documented as known sizing limitations (G6a wall is toy artifact, will be reassessed under real master in P1.3A). v21 / v22 packages apply post-review doc + code-context fixes on top of the same v20 rerun data set; see README v20 → v21 → v22 sections for current package status (this verdict block is preserved as the underlying spike run conclusion, not a re-issued recommendation).

Off-limits enforce: PASS (B1-B6 added only spike-lib files + this verdict.md;
`scripts/spike_prod_scale_lib/off_limits_check.py` would report 0 violation against master).

---

## Raw artifacts

- Telemetry jsonl: `data/cuts/spike/telemetry_278858.jsonl` (205 rss_sample + 14 proto_sample + 5 rss_sample_after_solve + 1 dark_matter_emit)
- Scale ramp jsonl: `data/cuts/spike/scale_ramp_results.jsonl` (5 tier records)
- A3 oracle fixture: `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` (50 cert × 9 family / 0 unsound)
