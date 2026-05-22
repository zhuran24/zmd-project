"""Store-aware cut replay + 6-step verify dispatch (B Design v2 Phase 1.0 P1.3).

Implements cut_lifecycle_v2.md v3.2.2 §4 ``replay_cut`` algorithm — the high-
level wrapper over ``lifecycle.step_6_attach_scope_check`` that:

1. Runs 6-step verify (source_digest / ghost match / blocked-OR-exterior hash
   dispatch / artifact hash / oracle version / active assumptions).
2. On ATTACH, runs post-attach validation (Step 7 in cut_lifecycle_v2 §4)
   via family-dispatched validator — re-computes cert against current state.
3. Mutates CutStore (quarantine_cut / hold_cut / reactivate_cut) per
   decision; cut is expected to be already-registered in ``store.cuts``.

For brand-new cuts not yet in store, callers should use
``lifecycle.step_6_attach_scope_check`` (pure function, no side effects) +
decide manually whether to ``add_cut``.

Family validators currently wired:
- region_capacity → step_5_validate_region_capacity (P1.1 framework)

Phase 1.1+ adds: cutset / port_exposure / component_reach / pattern_nogood /
shape_packing_hall / power_hitting_set / power_grid_reach / density_envelope.

Refs:
- docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md v3.2.2 §4
- PROJECT_LOCK.md §3A invariant 4 (HOLD vs Quarantine)
"""
from __future__ import annotations

import os
from typing import Callable, Dict, Optional

from src.cuts.families.cutset import validate_cutset
from src.cuts.families.port_exposure import validate_port_exposure
from src.cuts.families.region_capacity import validate_region_capacity
from src.cuts.lifecycle import (
    AttachDecision,
    BState,
    Cut,
    ValidationResult,
    step_6_attach_scope_check,
)
from src.cuts.store import CutStore, QuarantineReason


FamilyValidator = Callable[[Cut, BState, Dict], ValidationResult]


# Family → post-attach validator dispatch.
# Phase 1.1 P1.5/P1.6: F1 region_capacity + F2 cutset production validators
# wired. F2 oracle is stub (Phase 1.5+ wraps patch_routing_core); validator
# 满足 cert structure + free_cells re-recompute.
# P1.7-P1.15 各 family src/cuts/families/*.py 实施后 register 进此表.
FAMILY_VALIDATORS: Dict[str, FamilyValidator] = {
    "region_capacity": validate_region_capacity,
    "cutset": validate_cutset,
    "port_exposure": validate_port_exposure,
}


def replay_cut(
    cut: Cut,
    state: BState,
    store: CutStore,
    *,
    canonical_rules: Optional[Dict] = None,
    iter_index: int = -1,
) -> AttachDecision:
    """6-step verify + post-attach validation. Mutates store per decision.

    Caller responsibility:
    - ``cut`` 必须已经在 ``store.cuts`` (e.g. previously added 或 on_ghost_rect_changed
      命中 by_ghost_watcher 拉出).
    - ``canonical_rules`` 在 Phase 1.4 (P1.4 BState 加 parsed rules) 后变 required.
      Phase 1.0-1.3 期 optional — None 时跳过 post-attach validation
      (Phase 1.0 framework only — P1.5+ family validator 实施后 unlock 严格).

    Returns AttachDecision:
    - "ATTACH": store.reactivate_cut(cut_id) (从 held 回 active)
    - "HOLD": store.hold_cut(cut_id) (scope mismatch / oracle 不可用 / assumption 不 hold)
    - "QUARANTINE": store.quarantine_cut(cut_id, reason) (sound-violating bug)
    """
    if cut.cut_id not in store.cuts:
        raise KeyError(
            f"replay_cut: cut_id={cut.cut_id} 不在 store; "
            f"brand-new cut 应用 step_6_attach_scope_check (pure)."
        )

    # 1-6 步 dispatch — lifecycle.py step_6_attach_scope_check 跟 v3.2.2 §4 一致.
    decision = step_6_attach_scope_check(cut, state)

    if decision == "QUARANTINE":
        store.quarantine_cut(
            cut.cut_id,
            QuarantineReason(
                reason_code="scope_verify_failed",
                detail=_diagnose_quarantine(cut, state),
                iter_index=iter_index,
            ),
        )
        return decision

    if decision == "HOLD":
        if cut.cut_id not in store.quarantined:
            store.hold_cut(cut.cut_id)
        return decision

    # decision == "ATTACH" — 跑 Step 7 post-attach validation
    if canonical_rules is None:
        # Phase 1.0 framework: BState 还没持 parsed rules (P1.4 加).
        # 暂时跳过 post-attach validation — P1.5+ unlock.
        store.reactivate_cut(cut.cut_id)
        return "ATTACH"

    validator = FAMILY_VALIDATORS.get(cut.family)
    if validator is None:
        # Gemini round 28 finding #1 修: 防 P1.5+ 漏注册 silent skip.
        # EXACT_FAMILY_VALIDATOR_STRICT=1 (Phase 1.4 ramp 启动) 让 fail-closed;
        # 默认 (Phase 1.0/1.1 partial 实施期) silent skip 让 P1.5-P1.15 增量推进.
        if os.environ.get("EXACT_FAMILY_VALIDATOR_STRICT", "0") == "1":
            raise NotImplementedError(
                f"family={cut.family} validator 未注册 (FAMILY_VALIDATORS). "
                f"P1.5+ 实施时必须 register; 或调用方传 canonical_rules=None 跳过 Step 7."
            )
        store.reactivate_cut(cut.cut_id)
        return "ATTACH"

    vr = validator(cut, state, canonical_rules)
    if vr.kind == "ok":
        store.reactivate_cut(cut.cut_id)
        return "ATTACH"

    # unsound / timeout / schema_err → QUARANTINE (PROJECT_LOCK fail-closed)
    reason_code_map = {
        "unsound": "post_attach_validation_unsound",
        "timeout": "validate_timeout",
        "schema_err": "validate_schema_err",
    }
    store.quarantine_cut(
        cut.cut_id,
        QuarantineReason(
            reason_code=reason_code_map[vr.kind],
            detail=vr.detail or "",
            iter_index=iter_index,
        ),
    )
    return "QUARANTINE"


def regression_sweep(
    store: CutStore,
    state: BState,
    *,
    canonical_rules: Optional[Dict] = None,
    iter_index: int = -1,
) -> Dict[str, int]:
    """Re-validate all non-quarantined cuts (cut_lifecycle_v2 §9).

    Triggered:
    - Campaign 启动 (load cut store from disk)
    - Source artifact rotate detection (compute_source_digest 变)
    - Manual audit (debug)

    Returns counts of per-decision outcomes.
    """
    counts: Dict[str, int] = {
        "ATTACH": 0,
        "HOLD": 0,
        "QUARANTINE": 0,
        "skipped_quarantined": 0,
    }
    for cut_id in list(store.cuts.keys()):
        if cut_id in store.quarantined:
            counts["skipped_quarantined"] += 1
            continue
        cut = store.cuts[cut_id]
        decision = replay_cut(
            cut, state, store,
            canonical_rules=canonical_rules,
            iter_index=iter_index,
        )
        counts[decision] += 1
    return counts


# ---- Internal helpers -----------------------------------------------------

def _diagnose_quarantine(cut: Cut, state: BState) -> str:
    """生成 quarantine reason detail. 试推 6-step 哪步 fail (best-effort)."""
    assert cut.scope is not None
    from src.cuts.lifecycle import (
        GHOST_AGNOSTIC,
        compute_blocked_cells_hash,
        compute_exterior_blocks_hash,
        compute_ghost_rect_id,
    )

    # Step 1
    if cut.scope.source_digest != "poc_source_digest":
        return f"source_digest mismatch (cut={cut.scope.source_digest!r})"
    # Step 3 dispatch
    current_ghost_id = compute_ghost_rect_id(state.ghost_rect)
    is_ghost_agnostic = cut.scope.ghost_rect_id == GHOST_AGNOSTIC
    if is_ghost_agnostic:
        if cut.scope.exterior_blocks_hash != compute_exterior_blocks_hash(state):
            return "exterior_blocks_hash changed (GHOST_AGNOSTIC cut)"
    else:
        if cut.scope.ghost_rect_id == current_ghost_id and \
           cut.scope.blocked_cells_hash != compute_blocked_cells_hash(state):
            return "blocked_cells_hash changed (ghost-bound cut)"
    # Step 4
    for fname, h in cut.scope.artifact_hashes.items():
        if state.artifact_hashes.get(fname) != h:
            return f"artifact {fname} hash mismatch"
    return "scope verify failed (unspecified branch)"
