"""CutStore + 6-dim watcher index (B Design v2 Phase 1.0 P1.2).

Implements cut_lifecycle_v2.md v3.2.2 §7 Cut store + watcher index.

Central data structure for B Design v2:
- ``cuts``: active cut registry (cut_id → Cut)
- ``quarantined``: cut_id → QuarantineReason (audit-only, 不 active)
- ``held``: cut_id set (HOLD decision retention, 等下次 scope match)
- 6-dim watcher index (avoid scanning all cuts on state change):
  - ``by_cell_watcher``: F1/F2/F3/F4/F6/F7/F9
  - ``by_group_watcher``: F3/F5/F6/F7/F9
  - ``by_pose_watcher``: F3/F5/F7
  - ``by_commodity_watcher``: F2/F4
  - ``by_region_watcher``: F1/F6
  - ``by_ghost_watcher``: F2/F4/F5/F6/F7/F9 (not F1/F3 — F1 ghost-agnostic,
    F3 spec §5 明定 ghost-blocked front 不发 cut; F8 deleted 2026-07-08)

Watcher 添加规则 (cut_lifecycle_v2 §7 table) 是 family-specific; ``add_cut``
接口允许 caller (Phase 1.1+ family validator) 传 watcher keys per family rule.

Phase 1.0 P1.2 scope:
- in-memory CutStore + watcher index
- add_cut / quarantine_cut / hold_cut / reactivate_cut
- on_ghost_rect_changed (with injected replay function — P1.3 接 replay.py)
- lookup helpers (cuts_affected_by_*)

Defer to Phase 1.3 P1.21:
- disk persist (data/cuts/active/*.json + data/cuts/quarantine/*.json)
- source_digest invalidation on artifact rotation

Refs:
- docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md v3.2.2 §7-§8
- PROJECT_LOCK.md §2B Cut Object Boundary
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple

from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    BState,
    AttachDecision,
    Cell,
    Cut,
    CutId,
    GhostRectId,
    GroupId,
    PoseId,
)

# Watcher key types (cut_lifecycle_v2 §7).
CommodityId = str
RegionId = str
ReplayCallback = Callable[[Cut, BState], AttachDecision]


@dataclass(frozen=True)
class QuarantineReason:
    """Audit-only — written to quarantined[cut_id] when cut transitions to QUARANTINE."""
    reason_code: str  # "validate_unsound" | "scope_mismatch" | "artifact_changed" | ...
    detail: str = ""
    iter_index: int = -1


@dataclass
class CutStore:
    """In-memory cut store + 6-dim watcher index.

    Disk persist (data/cuts/{active,quarantine}/*.json) is Phase 1.3 P1.21 — this
    Phase 1.0 P1.2 holds in-memory state only.

    Watcher is a mapping: <state-dimension-key> → Set[CutId]. State change
    (e.g. ghost_cells 新增 cell) only retriggers re-evaluation of cuts in the
    affected watcher set — not whole store scan.
    """

    cuts: Dict[CutId, Cut] = field(default_factory=dict)

    # 6-dim watcher (v3.2 Day 17d 加 by_ghost — Family 6/7/8/9 ghost-bound 必需).
    by_cell_watcher: Dict[Cell, Set[CutId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_group_watcher: Dict[GroupId, Set[CutId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_pose_watcher: Dict[Tuple[GroupId, PoseId], Set[CutId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_commodity_watcher: Dict[CommodityId, Set[CutId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_region_watcher: Dict[RegionId, Set[CutId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_ghost_watcher: Dict[GhostRectId, Set[CutId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    # **Phase 1.3 P1.21 defer**: by_exterior_watcher (Gemini round 33/34/35 P0):
    # F1 GHOST_AGNOSTIC cut depend on exterior_blocks via static cap_R. master
    # 改 exterior_blocks 时应 trigger affected cut re-replay. Phase 1.1 framework
    # 当前 evaluate 重算 sound (families/region_capacity.evaluate_geometric_*
    # 每调用 recompute cap_R), 不需要 watcher 主动 invalidate; Phase 1.3 接
    # propagator 真 hot path 时 watcher 是 efficiency 必须. 参考 Gemini round 35
    # verdict — 当前 deferred 不是漏修, 是 Phase 1.3 scope.

    # Quarantine + Hold sets (state machine cut_lifecycle_v2 §8).
    quarantined: Dict[CutId, QuarantineReason] = field(default_factory=dict)
    held: Set[CutId] = field(default_factory=set)

    # ---- Core mutators ----------------------------------------------------

    def add_cut(
        self,
        cut: Cut,
        *,
        cell_keys: Iterable[Cell] = (),
        group_keys: Iterable[GroupId] = (),
        pose_keys: Iterable[Tuple[GroupId, PoseId]] = (),
        commodity_keys: Iterable[CommodityId] = (),
        region_keys: Iterable[RegionId] = (),
        initial_state: str = "held",
    ) -> None:
        """Register cut + watchers, default initial_state='held' (pending validation).

        GPT pro v5 P0-2 fix: 原 add_cut 直接 active 注册让 "validator unsound cut"
        在 replay 前能被 is_active() 看到 → silent attach window. 改默认 held —
        caller (oracle / replay 成功 path) 必须显式 reactivate_cut(cut_id) 后才
        active. 防 add 跟 validate 之间的 race window.

        ``*_keys`` are family-specific (caller computes per cut_lifecycle_v2 §7
        table). ``by_ghost_watcher`` is auto-derived from cut.scope.ghost_rect_id
        (GHOST_AGNOSTIC cuts 不入此 watcher per §7 footnote).

        Args:
            initial_state: "held" (default, pending replay/validator) | "active"
                (legacy, 仅 test fixture 用; production 必须经 replay → reactivate
                gate).
        """
        if cut.cut_id in self.cuts:
            raise ValueError(f"cut_id={cut.cut_id} 已注册")
        if cut.scope is None:
            raise ValueError(
                f"cut_id={cut.cut_id} scope is None — schema invariant violated"
            )
        # GPT pro v6 P0 fix: initial_state 验在 mutation 前 (原 verify 在 mutation
        # 后 ValueError raise 完 cut 残留 store + is_active=True silent attach).
        if initial_state not in ("held", "active"):
            raise ValueError(
                f"add_cut initial_state must be 'held' or 'active', got {initial_state!r}"
            )

        self.cuts[cut.cut_id] = cut

        for c in cell_keys:
            self.by_cell_watcher[c].add(cut.cut_id)
        for g in group_keys:
            self.by_group_watcher[g].add(cut.cut_id)
        for p in pose_keys:
            self.by_pose_watcher[p].add(cut.cut_id)
        for cm in commodity_keys:
            self.by_commodity_watcher[cm].add(cut.cut_id)
        for r in region_keys:
            self.by_region_watcher[r].add(cut.cut_id)

        ghost_id = cut.scope.ghost_rect_id
        if ghost_id != GHOST_AGNOSTIC:
            self.by_ghost_watcher[ghost_id].add(cut.cut_id)

        # GPT pro v5 P0-2: 默认 held (pending validation). caller 必经 replay/
        # validator gate 后调 reactivate_cut(cut_id) 才 active.
        if initial_state == "held":
            self.held.add(cut.cut_id)
        # initial_state == "active": 直接 active (legacy test fixture path).

    def quarantine_cut(self, cut_id: CutId, reason: QuarantineReason) -> None:
        """Move cut to quarantine. cut 仍保留在 self.cuts (audit trail);
        从 held / watcher 移除 (不再 trigger propagation)."""
        if cut_id not in self.cuts:
            raise KeyError(f"cut_id={cut_id} 不在 store")
        self.quarantined[cut_id] = reason
        self.held.discard(cut_id)
        self._unregister_from_watchers(cut_id)

    def hold_cut(self, cut_id: CutId) -> None:
        """Move cut to HOLD (scope mismatch or oracle unavailable). 不从 watcher
        移除 — held 状态等下次 ghost change 时 by_ghost_watcher 命中 re-replay."""
        if cut_id not in self.cuts:
            raise KeyError(f"cut_id={cut_id} 不在 store")
        if cut_id in self.quarantined:
            raise ValueError(f"cut_id={cut_id} 已 quarantined, 不能 hold")
        self.held.add(cut_id)

    def reactivate_cut(self, cut_id: CutId) -> None:
        """Move cut from HOLD back to ACTIVE (replay returned ATTACH)."""
        if cut_id not in self.cuts:
            raise KeyError(f"cut_id={cut_id} 不在 store")
        if cut_id in self.quarantined:
            raise ValueError(f"cut_id={cut_id} 已 quarantined, 不能 reactivate")
        self.held.discard(cut_id)

    def is_active(self, cut_id: CutId) -> bool:
        return (
            cut_id in self.cuts
            and cut_id not in self.quarantined
            and cut_id not in self.held
        )

    # ---- Watcher lookups (propagation hot path) ---------------------------

    def cuts_affected_by_cell(self, cell: Cell) -> Set[CutId]:
        return set(self.by_cell_watcher.get(cell, set()))

    def cuts_affected_by_group(self, gid: GroupId) -> Set[CutId]:
        return set(self.by_group_watcher.get(gid, set()))

    def cuts_affected_by_pose(self, gid: GroupId, pose_id: PoseId) -> Set[CutId]:
        return set(self.by_pose_watcher.get((gid, pose_id), set()))

    def cuts_affected_by_commodity(self, commodity_id: CommodityId) -> Set[CutId]:
        return set(self.by_commodity_watcher.get(commodity_id, set()))

    def cuts_affected_by_region(self, region_id: RegionId) -> Set[CutId]:
        return set(self.by_region_watcher.get(region_id, set()))

    def cuts_affected_by_ghost(self, ghost_id: GhostRectId) -> Set[CutId]:
        return set(self.by_ghost_watcher.get(ghost_id, set()))

    # ---- Ghost transition (cut_lifecycle_v2 §7 on_ghost_rect_changed) ----

    def on_ghost_rect_changed(
        self,
        old_ghost_id: GhostRectId,
        new_ghost_id: GhostRectId,
        state: BState,
        unsafe_test_replay_fn: Optional[ReplayCallback] = None,
        *,
        allow_unsafe_test_replay_fn: bool = False,
    ) -> None:
        """Triggered when ghost_rect changes (candidate transition).

        Default path lazy-imports replay_cut and always runs the full family
        validator. Test stubs must pass allow_unsafe_test_replay_fn=True so a
        scope-only replay function cannot be supplied accidentally in production.

        1. 旧 ghost_id 关联 cuts → hold (不 quarantine — 下次 ghost 回 old_id
           时 re-attach; v3.2.2 dispatch 让 cuts 跨 candidate 复用).
        2. 新 ghost_id 关联 cuts → 走 full replay_cut: 包括 step_6_attach_scope_check
           + family validator. validator ok → ATTACH; unsound/schema_err →
           QUARANTINE; HOLD 保留.

        GHOST_AGNOSTIC cuts (F1 仅当 ghost ∩ R == ∅) 不入 by_ghost_watcher, 由
        family validator 在 replay 时拒错标 (GPT v6 P0 fix: validator step 4b
        check scope.ghost_rect_id == GHOST_AGNOSTIC 合法性).
        """
        if unsafe_test_replay_fn is not None and not allow_unsafe_test_replay_fn:
            raise ValueError("unsafe_test_replay_fn requires allow_unsafe_test_replay_fn=True")

        if old_ghost_id != GHOST_AGNOSTIC:
            affected = self.by_ghost_watcher.get(old_ghost_id, set()).copy()
            for cut_id in affected:
                if cut_id in self.quarantined:
                    continue
                self.held.add(cut_id)

        if new_ghost_id != GHOST_AGNOSTIC:
            candidates = self.by_ghost_watcher.get(new_ghost_id, set()).copy()
            for cut_id in candidates:
                if cut_id in self.quarantined:
                    continue
                cut = self.cuts[cut_id]
                # GPT pro v6 P0: 默认走 full replay_cut (跑 family validator),
                # 不接受 scope-only replay_fn.
                if unsafe_test_replay_fn is None:
                    from src.cuts.replay import replay_cut
                    decision = replay_cut(
                        cut, state, self,
                        canonical_rules=state.canonical_rules,
                    )
                else:
                    decision = unsafe_test_replay_fn(cut, state)
                if decision == "ATTACH":
                    self.held.discard(cut_id)
                elif decision == "HOLD":
                    self.held.add(cut_id)
                elif decision == "QUARANTINE":
                    # replay_cut 已 quarantine; legacy replay_fn path 在此手动
                    if cut_id not in self.quarantined:
                        self.quarantine_cut(
                            cut_id,
                            QuarantineReason(
                                reason_code="ghost_transition_replay",
                                detail=f"old_ghost={old_ghost_id} new_ghost={new_ghost_id}",
                            ),
                        )

    # ---- Internal: watcher unregister -------------------------------------

    def _unregister_from_watchers(self, cut_id: CutId) -> None:
        """Remove cut from all 6 watchers (called by quarantine_cut)."""
        self._drop_from(self.by_cell_watcher, cut_id)
        self._drop_from(self.by_group_watcher, cut_id)
        self._drop_from(self.by_pose_watcher, cut_id)
        self._drop_from(self.by_commodity_watcher, cut_id)
        self._drop_from(self.by_region_watcher, cut_id)
        self._drop_from(self.by_ghost_watcher, cut_id)

    @staticmethod
    def _drop_from(watcher: Dict[Any, Set[CutId]], cut_id: CutId) -> None:
        for key in list(watcher.keys()):
            watcher[key].discard(cut_id)
            if not watcher[key]:
                del watcher[key]

    # ---- Statistics / introspection --------------------------------------

    def stats(self) -> Dict[str, int]:
        """Snapshot for telemetry (exit_criteria ramp report)."""
        return {
            "total_cuts": len(self.cuts),
            "active": sum(1 for c in self.cuts if self.is_active(c)),
            "held": len(self.held),
            "quarantined": len(self.quarantined),
            "by_cell_keys": len(self.by_cell_watcher),
            "by_group_keys": len(self.by_group_watcher),
            "by_pose_keys": len(self.by_pose_watcher),
            "by_commodity_keys": len(self.by_commodity_watcher),
            "by_region_keys": len(self.by_region_watcher),
            "by_ghost_keys": len(self.by_ghost_watcher),
        }
