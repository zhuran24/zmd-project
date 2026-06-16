# F7 Gemini Round 2 verdict (2026-05-25)

Round 2 cross-check on commit `9f21901` (post R1 BLOCKER fix).

## Gemini verdict: NOT_GO with 3 finding

R1 fix verified CORRECT (facility_cells exclude in both validator + oracle;
masks byte-equal across callers). 3 new finding analyzed:

## Finding 1 [CRITICAL claimed] — **WRONG** (Gemini 误读)

Gemini claim: validator rejects ``facility_pose_id`` as int (says
``PoseId`` "通常是 int", citing spec F3 example ``"pose_17"``).

**Main verify**: ``src/cuts/lifecycle.py:44-48``:

```python
# Gap 10 (Gemini round 30): PoseId = str (vs PoC int). Source: candidate_placements
PoseId = str
```

Real data `data/preprocessed/candidate_placements.json` confirms — every
``pose_id`` is a string like ``"p_x00_y01_o0_m_TB"``. F5 / F6 ``pose_id`` cert
fields are str. Spec example ``"pose_17"`` is a string literal not an int.

Gemini misread ``"pose_17"`` as int in the F3 example. PoseId locked to
str in the project — F7 validator's ``_is_non_empty_str(fp)`` is correct
fail-closed contract.

**Action**: no fix.

## Finding 2 [MEDIUM] — Phase 1.5+ defer (consistent with F5/F6)

Gemini claim: generator omits ``active_assumptions``; spec §4 requires
``Assumption("power_pole_radius", "R=5")`` etc.

**Main analysis**: F5 / F6 generators also default ``active_assumptions=()``
in their CutScope construction. Phase 1.2 simplification — Phase 1.5+
canonical_rules rotation needs assumption tracking; at Phase 1.2 the
``artifact_hashes`` already covers source-of-truth integrity. Same defer
pattern is consistent across families.

**Action**: Phase 1.5+ defer (track in F7 Phase 1.5+ defer list).

## Finding 3 [LOW] — FIXED this round

Helper module retained dead ``compute_cover_set_ghost_only`` after R1
inlined the ghost-only mask construction into validator + oracle. 0 callers.

**Fix landed**: removed helper, replaced with module-level note pointing to
the new call-site pattern (R1 fix).

## R1 fix verify (Gemini)

- **R1#1 facility_cells exclude**: CORRECT. Both validator phase 6/7 and
  oracle ``_full_free_cells_minus_facility`` / ``_ghost_only_free_cells_minus_facility``
  apply the exclusion via frozenset union (idempotent on overlap).
- **Mask byte-equality across validator + oracle**: CORRECT. Both compute
  ``grid - ghost - exterior - facility`` (ghost-only) and
  ``grid - ghost - exterior - cell_owner - facility`` (full); cross-worker
  reproducible.

## Sanity (Gemini, 3 disproved with file:line)

1. Float precision in ``_min_cell_distance`` — disproved (integer min_sq,
   ``math.sqrt(25) == 5.0`` exact under IEEE 754, ``power_cover.py:36``).
2. Mask construction with ghost ∩ facility overlap — disproved
   (frozenset union, ``power_hitting_set.py:269``).
3. Empty ``occupied_cells`` crash — disproved (returns ``()`` cleanly,
   ``power_cover_oracle.py:108``).

## Stop condition (v3 protocol)

R1+R2 共 4 真 finding (R1#1 fix, R1#2/3/4 defer-or-reject, R2#1 WRONG,
R2#2 defer, R2#3 fix). Remaining items all Phase 1.5+ defer.

**F7 cross-check loop closes** per v3 "GO 或只剩 Phase 1.5+ defer".

## Gate state (post all R1+R2 fixes)

- pytest cuts: 352 passed
- mypy --strict 33 src 0 errors
- ruff / bandit / radon A clean
- exit_criteria 3 PASS / 0 FAIL

## Phase 1.5+ defer list (F7 specific)

- cell_owner causation multi-literal cut (cert_kind "power_cover_emptyset_cell_owner")
- active_assumptions tracking (power_pole_radius / power_pole_shape)
- Hitting set min size generalize (spec §1d v1.2)
- Pole shape generalize (canonical_rules schema enum)
- L16 lazy_power_completion 切换为 F7 oracle (current shadow-only)
- Pose lookup O(N) → dict index (R1#2)
- Float sqrt → int squared (R1#3)
- Spec text update: 1×1 → 2×2 pole (Gap A)

## 下一步

F8 power_grid_reach N=5 子代理 design 启动. Mini Step 8 spike 也是 F7 close
后的 candidate trigger (per [[gpt-pro-p1-2-in-progress-review]] #6).
