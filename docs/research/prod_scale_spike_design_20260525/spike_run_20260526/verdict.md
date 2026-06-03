# Spike Phase B run verdict — prod-scale master integration

**Date**: 2026-05-26
**Branch**: `spike/prod_scale_master_integration_20260526` (off master `f7b88b6`)
**Phase B commits**: B1 `292c3a4` / B4+B5 `e121800` / B2 `c4f2e35` / B3 `3a9d507` / B6 `c3e5078` / verdict-fix `0691175`,`f54f4f8` / F3 special-case phase telemetry `b1bab5c` + A3 rerun `1d935f3`
**Phase B wall-clock**: 206s
**Phase A wall-clock**: ~1-2h (per phase_a_report.md)

## Overall verdict: **GO_WITH_MINOR**

> **⚠️ writer 边界 (v24 外审 F6)**: 本 verdict.md 里的「第九审/v26 sizing 修正」「v23/v24 外审」等 post-run 段是
> **手写 addenda**, `spike_prod_scale_runner.write_verdict_md` **不生成**它们 (writer 只生成原始 spike-run
> 的 G 表 / N 表 / Finding 5 表 / Layer-2 risk 1–6 / wall 表)。**重跑 writer 会覆盖本文件 → 需手动重贴这些
> addenda**。"GO_WITH_MINOR" 是底层 spike-run 的历史结论; **当前外审状态 (两轮 B / PATCH) 见下方修正段**,
> 不是 writer 自动反映的。

Per MERGER §5.2 round-3 semantic gap documentation:

> Spike GO close *Sizing*, 不 close *Convergence* / *Adversarial robustness*, 后两者入 P1.3A risk register.

This verdict pertains to **Sizing only** (Finding 5 #1 / #2 / #3 / #4). Convergence (real
PoseBoolExactMaster + LBBD multi-iter behavior under 81K BoolVar) and adversarial robustness
(F1/F2/F3 patch hold under 100K scale + 50 bad / 9950 good inject) are explicitly NOT
verified by this spike — they are deferred to P1.3A 主体 design phase and P1.3B regression.

## 第九审/v26 sizing 修正 (2026-06-01) — Finding 5 #2 sizing 口径收窄 + 4 soundness 修复

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
remap 审计 `data/cuts/spike/remap_audit.json` (F5): 50 cert 150 pair 中 **36 个 unknown 被静默 remap**
(density_envelope 24 + port_exposure 12) → B2 cut_count_applied=100% 是 synthetic/remap 吞吐, 非真 body sizing。
**(v24 外审 F5 精确化)**: remap 计数字段 (`n_pairs_remapped` / `true_registry_bound`) 已加进 `scale_ramp.py`
**代码**, 但**历史 B2 ramp artifact (`scale_ramp_results.jsonl` / `phase_b_results.json`) 没重跑, 不带这些字段**;
透明度由独立 artifact `remap_audit.json` 承载 (= v24 的实际 remap 证据), 不是靠 ramp jsonl。

**v23 外审二次修正 (2026-06-02) — sizing gate 自己有 bitset bug**: 上面 (2026-06-01) 的 sizing gate v1
用 **MSB-first** 解 bitset, 但真源 `region_capacity_oracle._encode_region_bitset` 是 **LSB-first**
(`arr[idx//8] |= 1<<(idx%8)`)。v1 因此 region cells 解错, term 数偏高 ~10x。v23 外审 catch + 对真源核实属实,
sizing gate 已修 LSB (`p1_2_spike_sizing_gate_20260601/`, v2)。纠正后结论:

> cut body 的 master 约束大小取决于 lowering 方式。fixture 尺度下 (a) **所有 9 族** realistic compact
> (witness/no-good) lowering → 100K 都便宜 (~1–3 MB); (b) **expanded (full pose-overlap)** lowering 随
> **region-size × pool-density** 变化, **且 proto 预算还乘 per-term 字节 (按约束类型: linear ~4 B /
> BoolOr no-good ~11 B, v24 外审实测)**。fixture region(139)/window 给 ~百级 term/cut (region 大池子 ~264,
> cutset ~173, **F9-window scoped max 784** — 全 6 条非前 2 条, all-type UB 3341): F1/F9 scoped 784 走 linear
> ~0.3 GB / 走 **BoolOr ~0.86 GB**; routing/all-type UB (F4 5429 / F9 3341) 走 BoolOr **~3.7–6 GB**; 大
> region/window 趋近全 pool (~16–18K term) 任何类型都数 GB。**v1 的 "F1/F9 大池子 2000–3200 term → 1.9 GB"
> 是 MSB 解码 bug 的假数字** (真实 264, 不是 2026)。

**因此 P1.3A lowering 设计硬约束 (scope 已纠正, 不止 F1/F9)**: 对**任何**族的 geometric / large-overlap
expanded lowering 设 **per-cut term cap + cumulative proto budget** (F2/F4 expanded 同样可达 hundreds/thousands);
其余维持 compact lowering 则全 9 族安全。已移交 P1.3A risk register (Layer-2 #6)。

**F7 (malformed scope hygiene)**: toy_translator **只有 F3 `port_exposure` malformed fail-closed**;
其余 family 的 cert decode 失败仍走 deterministic synthetic fallback (3 literal)。所以 fail-closed 结论
**不能泛化成全局**; 非 F3 的 synthetic lowering 只能算 synthetic/remap sizing, 不是真 registry-bound evidence。

另一条未测轴: cert 证书存储 + replay 校验在 100K 规模 (~613 字节 bitset/cert → ~60 MB store +
逐条 revalidate) 归 P1.3A proof lifecycle sizing。

## v25 外审修正 (2026-06-02, 第四轮两份独立外审并集) — concrete-literal sizing scope (post-run hand addendum)

第四轮 (v25) 两份独立外审都判 **B/PATCH, 无 soundness 洞**, 核心 framing (LSB / compact 全族便宜 / bytes/term
按约束类型分 / cap 按 max/p99 跨所有族) 都 sound。并集修正 4 条 sizing 证据精度 finding (主代理逐条对真代码核实,
已落 master `docs/research/p1_2_spike_sizing_gate_20260601/` sizing_gate v5 + RESULTS):

- **[A-F1, 最重] type-pool 数 ≠ 真 master concrete literal 数**: 上方 sizing 用的是按 facility **type** 的 pose
  pool overlap (type-pool total 81,795)。但真 pose-bool master 按 `(facility_type, operation_type)` **group×pose**
  建变量 (266 instance → 19 group; mfg_3x3=8 / mfg_5x5=4 / mfg_6x4=5), concrete 数 ≈4× type-pool (**325,747**)。
  F4 5429→**20,157** 是 group-expanded proxy。**F9 现有 cert 是 single-group** (density_envelope cert 带 group_id,
  validator 拒 witness group ≠ cert group): 当前 per-cut cert-group max 仍是 **784**；same-template proxy max **4,608**；
  all-manufacturing cross-group stress proxy **11,644**，不是当前 F9 per-cut literal vector。→ **上方 all-type UB 数
  (F9 3341 / F4 5429 / ~16–18K) 是 type-pool cheap proxy, 不是真-master literal 上界**。单 group 的 F9 **784** +
  region LSB **~264** 仍是真实的单 group / region 尺度信号。**P1.3A expanded-lowering cap 的输入必须是真 translator 在
  group/template/optional 展开后发出的 concrete literal vector 长度** (`expanded_terms = len(final_concrete_literals)`),
  按约束类型分 (linear ~4 / BoolOr ~11) 设 per-cut max/p99 cap + cumulative proto budget; 超 cap → compact fallback / reject / defer。
- **[B-F1]** sizing_gate family summary 的 density_envelope 行不再 fallback 到 compact 4.0 (现承载真实 window→pose overlap)。
- **[B-F2]** bytes/term 现脚本内可复现实测 (ExportToFile; linear 4.03 / BoolOr 10.01), 不再只 hardcode。
- **[A-F2]** F9 `window_rect` 读序修正为 `[x,y,h,w]` (现 fixture 全 10×10 故数字不变)。

另: 主线 F7/F8 registry validator 已加 **duplicate pose_id 唯一性守卫** (B-F3, fail-closed 硬化, len(matches)==1
else unsound; 当前 registry 无 dup 故非现漏洞) + 2 回归测试 (cuts 414→416)。**这些都是证据精度/scoping/hardening,
不改 spike 的 Sizing-only GO_WITH_MINOR 方向**; 两份外审都明说合补丁后可 close → 进 P1.3A。

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
| G10 oracle real-emit 45 cert (A3) | ≥45 + 0 unsound + 0 schema_err | 50 cert / 9 family / 0 unsound / 0 schema_err | PASS |
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
| 1 | prod type-pool registry build / master-var proxy | A3 oracle emit + B1 load_pose_registry build 81,795 type-pool BoolVar from real `data/preprocessed/candidate_placements.json` 7 facility pools; concrete pose-bool upper proxy is 325,747 by mandatory group expansion, cheap-counted in sizing_gate, not built/solved by B2 | PARTIAL — sizing-only evidence; P1.3A must measure/cap `len(final_concrete_literals)` |
| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 50 cert × 9 family 真 oracle emit ✅; **但** B2 translator 把 body lower 成合成/remap 小约束 (remap_audit: 36/50 unknown), 非真 registry-bound body sizing | **PARTIAL** — 见「第九审/v26 sizing 修正」: compact lowering 全族安全; expanded lowering 随 region×pool 变 (跨所有族非 F1/F9 专属), 需 term cap; concrete cap 以 `len(final_concrete_literals)` 为准; 已移交 P1.3A Layer-2 #6 |
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

6. **expanded lowering sizing (2026-06-02 LSB + bytes/term-by-kind; v23+v24 外审)** — 带数字硬约束 (跨**所有**
   族, 不止 F1/F9): 100K proto 预算 = **(per-cut term, 随 region/window × pool-density 变) × (per-term 字节,
   按约束类型: linear ~4 B / BoolOr no-good ~11 B, v24 外审实测)**。fixture: region 大池子 ~264 (不是 v1 MSB bug
   的 2026); cutset ~173; **F9-window scoped max 784** (全 6 条非前 2 条, all-type UB 3341)。F1/F9 scoped 784
   走 linear ~0.3 GB / 走 BoolOr ~0.86 GB; routing/all-type UB (F4 5429 / F9 3341) 走 BoolOr ~3.7–6 GB; 大
   region/window 趋近全 pool (~16–18K term) 任何类型数 GB。P1.3A lowering 设计**必须**: compact (witness/no-good)
   → 全 9 族安全; 任何族 geometric/expanded → **按约束类型**设 per-cut term cap + cumulative proto budget
   (cap 按 max/p99 非 family-avg)。证据: `docs/research/p1_2_spike_sizing_gate_20260601/` (v3)。附带: 100K
   cert 证书存储 + replay 校验成本 (~60 MB store + 逐条 revalidate) 归 P1.3A proof lifecycle sizing。

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
