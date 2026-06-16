# F2/F4 Gemini Round 3 verdict (2026-05-24)

Round 3 cross-check on commit `d5e653d` (post round 2 F3 fix).

## Gemini verdict: GO_WITH_MINOR (close 条件满足)

## R2#3 fix verify: CORRECT

cert_hash 影响分析 sound:
- 加 `"blocking_facilities": []` 改 canonical JSON → hash 变, 但内容变 hash 应变,
  不是 false dedup risk
- JSON `sort_keys=True` 字母序: "blocking_facilities" 排在 "commodity_id" 前,
  cross-worker reproducibility 保留
- v1.1 validator 不 check 此 field → 加 carry 不破现有 test (292 cuts pytest pass)
- Phase 1.5+ causation split 填非空 → 新 cert 不同 hash (正确, 不同语义 cert 应不同 id)

## Round 3 New Finding 1: MEDIUM (already Gap A — 重述非新)

`cutset_oracle.py:150` `_is_strict_positive_int` 拒 float demand. Gemini 又提此
finding, 但跟 Round 1 Gap A 重复, **已在 project_phase_1_2_progress.md Phase 1.5+
defer list** (preprocess scale 或 math.ceil 在 Phase 1.5+ wiring 时统一处理).
Gemini 标 MEDIUM 因 round 1 当时 stand-alone, round 3 视角 fail-closed sound
(不发假 cut) 但降低剪枝效率. 处理: defer 不变.

## F2 generator 边界 case (3 段全 CORRECT)

1. `src == sink` skip (oracle:137) — Menger 没意义, sound 跳过
2. `bfs_component` 单源 + sink 不在 src component (oracle:140) — F4 territory,
   F2 跳过避免 family overlap, 设计精妙
3. `cut_capacity >= demand` 等号 skip (oracle:159) — Menger 严格 < 才 INFEASIBLE,
   等号 feasible, skip 正确

## Sanity (3 disproved with file:line citations)

- `extract_frontier_separator` separator 越界 → disproved (dinic_node_split.py:39
  neighbors_4conn 严 grid 边界 check)
- `cut_cell_edges` 重复无向边 → disproved (dinic_node_split.py:350 canonicalize
  pair = (min, max))
- (3rd disproof in raw response — see gemini_response.md)

## Stop condition 满足 (per v3 协议)

R1+R2+R3 共 6 个真 finding (除 round 3 finding 1 重述):
- R1#1 BLOCKER Dinic recursion — fixed ✅
- R1#2 HIGH Phase 1.5+ cell-cap arch limit — defer ✅
- R1#3 LOW bitset padding — fixed ✅
- R2#1 HIGH Phase 1.5+ node-split drop (≈ R1#2) — defer ✅
- R2#2 MEDIUM `cut_size` 命名 — defer ✅
- R2#3 LOW F4 cert blocking_facilities — fixed ✅

剩余全 Phase 1.5+ defer (架构层等 schema 升级一并改). 没新 critical / new
substantive finding catch. **F2/F4 cross-check loop close**.

## Gate state (post all 3 rounds)

- pytest cuts: 292 passed (361 with new dinic regression tests)
- mypy --strict 28 src 0 errors
- ruff / bandit / radon A clean
- exit_criteria 3 PASS / 8 PENDING_PHASE_1 / 0 FAIL

## 下一步

Per `project_phase_1_2_progress.md` compaction context step 3:
"F2/F4 GO 后启 F6 N=5 子代理 design"

接 F6 shape_packing_hall design 阶段, 启 5 路 opus 子代理 parallel
(per [[design-phase-n-parallel-agents]] v1 protocol).
