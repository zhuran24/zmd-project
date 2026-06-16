# PCR-CUT (Path 14) Phase 5 verdict — 2026-05-19

## 结论

🟡 **0/8 CERTIFIED**, 7/8 UNPROVEN, 1/8 sound master-INFEASIBLE.

Phase 0-4 全 GO ✅ — paradigm 端到端 land 进 production (env-gated, fail-closed).
Phase 5 multi-anchor breakthrough verdict: paradigm 跟 [Path 12 RAB-SEP] +
[Path 13 SAC-Hull L2] 同 verdict — necessary cut 不 sufficient.

## 8 anchor × max_iter=10 全表

| label | size | (ax, ay) | status | wall_s |
|---|---|---|---|---|
| interior_22_28 | 27×15 | (22, 28) | UNPROVEN | 594.8 |
| interior_10_10 | 27×15 | (10, 10) | UNPROVEN | 611.3 |
| interior_44_30 | 27×15 | (44, 30) | UNPROVEN | 591.3 |
| interior_15_40 | 27×15 | (15, 40) | UNPROVEN | 613.3 |
| corner_0_0_NEGATIVE | 27×15 | (0, 0) | INFEASIBLE | 55.9 |
| small_10x10 | 10×10 | (25, 25) | UNPROVEN | 648.6 |
| small_15x10 | 15×10 | (22, 28) | UNPROVEN | 622.6 |
| small_15x15 | 15×15 | (22, 28) | UNPROVEN | 657.6 |

Total wall: ~73 min (4395s).

## 关键观察

**Paradigm 端到端 work** ✅:
- 70 PCR-CUT cuts added across 7 non-corner anchors (每 anchor 10/10 iter).
- master.solve 全 OPTIMAL — no UNKNOWN before max_iter cap.
- separator p50 ~0.25s, p95 ~8s, p_max ~10s. 全在 15s 预算内.
- baseline byte-for-byte unchanged when env off.

**但 paradigm 不 sufficient** ❌:
- 累 10 cut layout 仍 routing INFEASIBLE → 加新 cut → continue. 没 layout family 退化到 routing-feasible.
- signature lifting lift_count 都 = 1 — pose pool 内每 pose unique footprint+ports, no equivalence class.
- 跟 SAC-Hull L2 + RAB-SEP cert 同质: patch-local INFEASIBLE 是全图 routing-INFEASIBLE 的 necessary 不 sufficient condition.

## paradigm 不 sufficient 的几何根因

PCR-CUT 在 patch P 上证明 layout L 的 routing infeasibility, master 加 cut
forbid {pose_i for owner_i in core}. master 再 solve 给 L', L' 在 P 上 可能
routing-feasible 但 在 patch Q 上 INFEASIBLE — 加新 cut continue. 这是 patch
本地 cut 跟全图 geometry 的 gap.

要 sufficient 需要 cut form 表达全图 routing-feasibility, 但 PROJECT_LOCK
禁绕过 binding/routing CP-SAT 直接 hard constraint master.

## 留下的 infrastructure (可复用)

- **patch_routing_core.py 983 LOC** — PatchSpec + PatchRoutingCore + replay validate +
  QuickXplain. 任何后续 paradigm 需 "patch-local CP-SAT certificate" 都可用.
- **patch_conflict_separator.py 469 LOC** — orchestration: candidates → patch solve →
  validate → master cut. 可换不同 candidate selection / cut form.
- **pose_bool_exact_master 加 signature lifting helpers** — within-instance pose
  equivalence lifting. 任何后续 cut 类型可复用.
- **Phase 0 oracle (phase0_patch_oracle_probe.py)** — 找压力集中区. 未来 paradigm
  可拿同 framework 找 hot spot.

## ROI 评估 (Claude pace)

- 总 wall: ~6h (Phase 0/1 prep + Phase 1 PoC + Phase 2-4 implement + Phase 5 wait 73 min)
- Phase 0 cheap gate 验证有效: 30 min 救 6h 浪费
- Phase 5 verdict 跟之前 paradigm verdict 跑出 isomorphic pattern — 可重复验证
  paradigm 投资的 cap 估算

## 下一步候选 (待用户决策)

1. **combo trial** — PCR-CUT + SAC-Hull dynamic + abstract routing L2 同时
   开 1 anchor, 看叠加是否突破. 30 min cheap probe.
2. **GPT v4 review** — 把 PCR-CUT 经验 zip 进 review 包, 求 GPT 给 break paradigm
   建议. 1h prep + 1-2 day GPT.
3. **L11 牺牲严格性** — 用户拒绝.
4. **paradigm shift** — set-packing prover (L15) 已死.

## commits

- Phase 0: `24ed7d8`
- Phase 1: `a56ab41`
- Phase 2: `e71879e`
- Phase 3: `f3a7382`
- Phase 4: `2f9bee5`

## 跟其他 paradigm 比较

| paradigm | Phase 0-1 cheap gate | end-to-end land | breakthrough |
|---|---|---|---|
| L12 RAB-SEP (Path 12) | GO | ✅ | ❌ |
| L13 SAC-Hull (Path 13) | GO | ✅ | ❌ |
| L14 PCR-CUT (Path 14) | GO | ✅ | ❌ |

3 paradigm 全 端到端 land ✅ 全 breakthrough ❌. 模式很明确.
