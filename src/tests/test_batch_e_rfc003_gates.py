"""批E RFC-003 §9 seven gates under the (b) fresh-model-regeneration semantics.

Spec: docs/research/cut_framework_review_gpt56pro_20260710/08_batch_e_rfc003_spec.md §4.
Fixture: the proven bound-region F1 world from the attach-wiring suite (real
master + production-dependency-aligned BState; the typed chain compiles,
resolves and lowers end-to-end).

Gate 4 (reader tri-state) lives in src/tests/cuts/test_cut_ledger.py. Gate 5
has three arms here: forged-ledger zero influence, fresh master/pool zero
inheritance, and the two-process kill/resume drill (a subprocess attaches with
a ledger then dies un-sealed; the resuming process must inherit nothing and
must never touch the dead segment). Gate 6 is fixture-level ONLY — the RFC
gate stays OPEN until 批C prod-scale A/B (spec §4, PIC-5 discipline).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence
from unittest import mock

import pytest

from src.cuts.ledger import CutLedgerWriter, read_segment
from src.models.cut_manager import CutManager
from src.search.benders_loop import LBBDController
from src.tests.test_cut_framework_attach_wiring import _bound_region_world


def _controller_e(
    master: Any,
    *,
    cut_ledger: Optional[CutLedgerWriter] = None,
    enabled_cut_families: Optional[Sequence[str]] = None,
) -> LBBDController:
    ckpt = Path(tempfile.mkdtemp(prefix="zmd_be_"))
    cm = CutManager(checkpoint_dir=ckpt, solve_mode="certified_exact")
    return LBBDController(
        master=master,
        cut_manager=cm,
        project_root=ckpt.parent,
        solve_mode="certified_exact",
        cut_ledger=cut_ledger,
        enabled_cut_families=enabled_cut_families,
    )


def _attach(controller: LBBDController, state: Any, iteration: int) -> int:
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ):
            return controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=iteration
            )


def _events(path: Path) -> tuple[dict[str, Any], ...]:
    return read_segment(path).events


# ---------------------------------------------------------------- gate 3


def test_gate3_same_semantics_attaches_once_and_ledgers_both_facts(
    tmp_path: Path,
) -> None:
    """RFC §9.3: same semantic cut, different cut_id/iteration → one attach.

    Round 2 regenerates the same F1 cut (fresh wallclock cut_id) and must be
    rejected as semantic_duplicate with the master constraint count unchanged;
    both facts land in a complete ledger segment with matching fingerprints.
    """
    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path, scope_id="gate3", writer_id="w1")
    controller = _controller_e(master, cut_ledger=ledger)
    a1 = _attach(controller, state, 1)
    count_after_r1 = int(master.build_stats["coordinate_framework_cut_count"])
    a2 = _attach(controller, state, 2)
    ledger.seal()
    assert a1 >= 1 and a2 == 0
    assert int(master.build_stats["coordinate_framework_cut_count"]) == count_after_r1
    result = read_segment(ledger.path)
    assert result.status == "complete"
    applied = [e for e in result.events if e["event"] == "APPLIED"]
    dup = [
        e
        for e in result.events
        if e["event"] == "REJECTED"
        and e.get("reason_code") == "semantic_duplicate"
    ]
    assert len(applied) == a1
    assert len(dup) >= 1
    assert {e["semantic_fingerprint"] for e in dup} <= {
        e["semantic_fingerprint"] for e in applied
    }
    # Different event identity (wallclock/iteration cut_id), same semantics.
    assert {e["cut_id"] for e in dup}.isdisjoint({e["cut_id"] for e in applied})
    for event in applied:
        receipt = event["receipt"]
        assert receipt["count_delta"] == 1
        assert receipt["apply_completed"] is True
        assert receipt["ghost_rect_digest"]
        for lit in receipt["condition_lits"]:
            assert isinstance(lit["index"], int) and isinstance(lit["name"], str)


def test_gate3_step7_refusal_does_not_poison_the_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Applied-only pool (spec D-2): a step-7 attach-timing refusal must not
    seed the fingerprint, so the same cut regenerated later still attaches."""
    import src.cuts.lifecycle as lifecycle

    master, state, _group = _bound_region_world()
    controller = _controller_e(master)
    real_step_7 = lifecycle.step_7_evaluate_cut
    calls = {"n": 0}

    def flaky_step_7(compiled: Any, snapshot: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            return False
        return real_step_7(compiled, snapshot)

    monkeypatch.setattr(lifecycle, "step_7_evaluate_cut", flaky_step_7)
    a1 = _attach(controller, state, 1)
    stats_r1 = dict(master.build_stats["cut_framework_attach_last"])
    a2 = _attach(controller, state, 2)
    assert stats_r1["rejected"]["attach_timing"] >= 1
    # The refused fingerprint was NOT falsely remembered as applied:
    assert a1 + a2 >= 1 and a2 >= 1


def test_gate3_fresh_master_does_not_consume_old_pool() -> None:
    """Generation boundary (spec D-2/D-3): a new master build gets a new pool —
    the same semantic cut must re-attach on the new build."""
    m1, s1, _g1 = _bound_region_world()
    c1 = _controller_e(m1)
    assert _attach(c1, s1, 1) >= 1
    m2, s2, _g2 = _bound_region_world()
    c2 = _controller_e(m2)
    assert _attach(c2, s2, 1) >= 1


def test_generation_guard_master_swap_fails_closed() -> None:
    m1, s1, _g1 = _bound_region_world()
    controller = _controller_e(m1)
    m2, _s2, _g2 = _bound_region_world()
    controller.master = m2
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with pytest.raises(RuntimeError, match="master build"):
            controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1
            )


def test_unknown_family_rejected_at_construction() -> None:
    m1, _s1, _g1 = _bound_region_world()
    with pytest.raises(ValueError, match="unknown cut families"):
        _controller_e(m1, enabled_cut_families=["region_capacity", "nope"])


# ---------------------------------------------------------------- gate 1 / 2


def test_gate1_apply_chain_failure_poisons_ledger_and_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injection sentinel (批D reachability-sentinel口径): a step-8 fault must
    ① propagate (no publishable conclusion), ② leave zero APPLIED events and a
    POISONED event, ③ leave the pool unseeded and the master counter at 0."""
    import src.cuts.lifecycle as lifecycle

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path, scope_id="gate1", writer_id="w1")
    controller = _controller_e(master, cut_ledger=ledger)

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("injected step_8 fault")

    monkeypatch.setattr(lifecycle, "step_8_apply_to_master", boom)
    with pytest.raises(RuntimeError, match="injected step_8 fault"):
        _attach(controller, state, 1)
    names = [e["event"] for e in _events(ledger.path)]
    assert "POISONED" in names
    assert "APPLIED" not in names
    assert controller._attached_semantic_fingerprints == set()
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0


def test_gate2_resolver_fault_arm_poisons_and_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gate 2 resolver/apply arm (rev3): a resolver-level mis-binding is an
    exception — POISONED + propagate, zero APPLIED, master zero write."""
    import src.cuts.lifecycle as lifecycle

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path, scope_id="gate2r", writer_id="w1")
    controller = _controller_e(master, cut_ledger=ledger)

    def mis_bind(*args: Any, **kwargs: Any) -> None:
        raise ValueError("injected resolver mis-binding")

    monkeypatch.setattr(lifecycle, "_resolve_model_scope_binding", mis_bind)
    with pytest.raises(ValueError, match="injected resolver mis-binding"):
        _attach(controller, state, 1)
    names = [e["event"] for e in _events(ledger.path)]
    assert "POISONED" in names and "APPLIED" not in names
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0


def test_gate2_single_entry_rejection_arm_ledgers_and_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gate 2 single-entry arm: a CutRejection from validate_and_compile is a
    bucketed skip — REJECTED event with the stage as reason_code, zero APPLIED,
    master zero write, and the loop continues (no exception)."""
    import src.cuts.typed_platform as typed_platform

    master, state, _group = _bound_region_world()
    ledger = CutLedgerWriter(tmp_path, scope_id="gate2s", writer_id="w1")
    controller = _controller_e(master, cut_ledger=ledger)
    rejection = typed_platform.CutRejection(
        stage="scope", reason="injected scope mismatch", cut_id="cut-under-test"
    )
    monkeypatch.setattr(
        typed_platform,
        "validate_and_compile_cut",
        lambda envelope, snapshot, registry: rejection,
    )
    attached = _attach(controller, state, 1)
    ledger.seal()
    assert attached == 0
    result = read_segment(ledger.path)
    assert result.status == "complete"
    rejected = [e for e in result.events if e["event"] == "REJECTED"]
    assert any(e.get("reason_code") == "scope" for e in rejected)
    assert not any(e["event"] == "APPLIED" for e in result.events)
    assert int(master.build_stats.get("coordinate_framework_cut_count", 0)) == 0
    stats = master.build_stats["cut_framework_attach_last"]
    assert stats["rejected"]["scope"] >= 1


# ---------------------------------------------------------------- gate 5


def test_gate5_forged_ledger_has_zero_influence_and_is_never_touched(
    tmp_path: Path,
) -> None:
    """Substitute gate (spec D-1 waiver, NOT the RFC replay gate): pre-planted
    forged ledger content must not change attach behaviour by one bit (non-
    consumption isolation), must never be appended to, and the new writer's
    GENESIS must carry lineage fields."""
    scope_dir = tmp_path / "gate5"
    scope_dir.mkdir(parents=True)
    forged = scope_dir / "segment_evil_00000.jsonl"
    forged_bytes = (
        b'{"event":"APPLIED","cut_id":"evil","semantic_fingerprint":"'
        + b"a" * 64
        + b'","seq":0}\n'
    )
    forged.write_bytes(forged_bytes)

    baseline_master, baseline_state, _g = _bound_region_world()
    baseline = _attach(_controller_e(baseline_master), baseline_state, 1)

    master, state, _g2 = _bound_region_world()
    writer = CutLedgerWriter(
        tmp_path,
        scope_id="gate5",
        writer_id="w1",
        genesis_context={
            "predecessor_segment": None,
            "predecessor_tail_hash": None,
            "recovery_reason": "fresh_start",
        },
    )
    controller = _controller_e(master, cut_ledger=writer)
    attached = _attach(controller, state, 1)
    writer.seal()

    assert attached == baseline  # forged disk content changed nothing
    assert forged.read_bytes() == forged_bytes  # never appended / rewritten
    assert writer.path != forged
    genesis = _events(writer.path)[0]
    assert genesis["event"] == "GENESIS"
    assert "predecessor_segment" in genesis and "recovery_reason" in genesis
    # Every APPLIED in the fresh segment came from this process's typed chain
    # (receipt present), not from any disk record.
    for event in _events(writer.path):
        if event["event"] == "APPLIED":
            assert event["receipt"]["apply_completed"] is True


_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_KILL_SCRIPT = r"""
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from unittest import mock
from src.cuts.ledger import CutLedgerWriter
from src.models.cut_manager import CutManager
from src.search.benders_loop import LBBDController
from src.tests.test_cut_framework_attach_wiring import _bound_region_world

master, state, _g = _bound_region_world()
ledger = CutLedgerWriter(Path(sys.argv[2]), scope_id="gate5proc", writer_id="victim")
ckpt = Path(tempfile.mkdtemp(prefix="zmd_be_kill_"))
controller = LBBDController(
    master=master,
    cut_manager=CutManager(checkpoint_dir=ckpt, solve_mode="certified_exact"),
    project_root=ckpt.parent,
    solve_mode="certified_exact",
    cut_ledger=ledger,
)
with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
    with mock.patch.object(
        LBBDController, "_build_cut_framework_state", return_value=state
    ):
        n = controller._maybe_attach_framework_cuts(
            trigger="binding_infeasible", iteration=1
        )
assert n >= 1, n
os._exit(42)  # hard kill: no seal, no interpreter cleanup
"""


def test_gate5_two_process_kill_resume_inherits_nothing(tmp_path: Path) -> None:
    """Gate 5 two-process arm: a writer process attaches (APPLIED on disk) and
    dies without sealing. The resuming process must regenerate through its own
    typed chain (zero inheritance — the dead APPLIED suppresses nothing), must
    never append to the dead segment, and must link it via GENESIS lineage."""
    proc = subprocess.run(
        [sys.executable, "-c", _KILL_SCRIPT, str(_PROJECT_ROOT), str(tmp_path)],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 42, (proc.returncode, proc.stderr[-2000:])
    scope = tmp_path / "gate5proc"
    segments = sorted(scope.glob("segment_*.jsonl"))
    assert len(segments) == 1
    dead = read_segment(segments[0])
    assert dead.status == "truncated"  # killed before seal
    assert not dead.supports_negative_assertions
    assert any(e["event"] == "APPLIED" for e in dead.events)
    dead_bytes = segments[0].read_bytes()

    master, state, _g = _bound_region_world()
    successor = CutLedgerWriter(
        tmp_path,
        scope_id="gate5proc",
        writer_id="resumer",
        genesis_context={
            "predecessor_segment": segments[0].name,
            "predecessor_tail_hash": dead.tail_hash,
            "recovery_reason": "restart_after_kill",
        },
    )
    controller = _controller_e(master, cut_ledger=successor)
    attached = _attach(controller, state, 1)
    successor.seal()
    assert attached >= 1  # regeneration, not replay: nothing inherited
    assert segments[0].read_bytes() == dead_bytes  # dead segment untouched
    result = read_segment(successor.path)
    assert result.status == "complete"
    genesis = result.events[0]
    assert genesis["predecessor_segment"] == segments[0].name
    assert genesis["predecessor_tail_hash"] == dead.tail_hash
    assert genesis["recovery_reason"] == "restart_after_kill"


# ---------------------------------------------------------------- gate 6 / 7


def test_gate6_fixture_arms_on_off() -> None:
    """Fixture-level arms only (RFC gate 6 stays OPEN → 批C): attach-on must
    show real work (generated>0 && applied>0); attach-off must apply nothing."""
    m_on, s_on, _g = _bound_region_world()
    c_on = _controller_e(m_on)
    attached_on = _attach(c_on, s_on, 1)
    stats_on = m_on.build_stats["cut_framework_attach_last"]
    assert stats_on["generated"] > 0
    assert attached_on > 0

    m_off, s_off, _g2 = _bound_region_world()
    c_off = _controller_e(m_off)
    env = dict(os.environ)
    env.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
    with mock.patch.dict(os.environ, env, clear=True):
        attached_off = c_off._maybe_attach_framework_cuts(
            trigger="binding_infeasible", iteration=1
        )
    assert attached_off == 0
    assert int(m_off.build_stats.get("coordinate_framework_cut_count", 0)) == 0


def test_ghost_rect_digest_uniqueness_sentinel() -> None:
    """Spec D-2 ghost-uniqueness sentinel: the resolver's `_locate_master_
    ghost_rect` returns the FIRST digest match, so a production master must
    never carry two ghost domains with the same rect digest (else a bound cut
    could resolve to the wrong u_var). Pin that the production builder keeps
    them unique."""
    from src.cuts.lifecycle import _ghost_rect_digest

    master, _state, _g = _bound_region_world()
    digests = []
    for domain in master._ghost_domains:
        cells = domain.get("cells") or ()
        if not cells:
            continue
        xs = [int(c[0]) for c in cells]
        ys = [int(c[1]) for c in cells]
        rect = [min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1]
        digests.append(_ghost_rect_digest(rect))
    assert digests, "fixture master has no ghost domains"
    assert len(digests) == len(set(digests)), "ghost rect digest collision"


def test_gate1_apply_failure_is_not_persistent_on_fresh_master(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §4 gate1 ③: an injected apply failure must not persist — a fresh
    master (new build, new pool) re-attaches the same cut cleanly. Proves the
    poison aborts the run without corrupting future builds."""
    import src.cuts.lifecycle as lifecycle

    m1, s1, _g1 = _bound_region_world()
    c1 = _controller_e(m1)
    real_step_8 = lifecycle.step_8_apply_to_master

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("injected step_8 fault")

    monkeypatch.setattr(lifecycle, "step_8_apply_to_master", boom)
    with pytest.raises(RuntimeError, match="injected step_8 fault"):
        _attach(c1, s1, 1)
    assert int(m1.build_stats.get("coordinate_framework_cut_count", 0)) == 0

    # Fresh master + restored step_8: the same cut attaches normally.
    monkeypatch.setattr(lifecycle, "step_8_apply_to_master", real_step_8)
    m2, s2, _g2 = _bound_region_world()
    c2 = _controller_e(m2)
    assert _attach(c2, s2, 1) >= 1
    assert int(m2.build_stats.get("coordinate_framework_cut_count", 0)) >= 1


def test_gate7_compiler_version_rollback_reattaches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §4 gate7 compiler-rollback variant (behavioural, not structural):
    the semantic fingerprint embeds the family compiler version, so rolling
    that version changes every fingerprint. A cut whose fingerprint the pool
    already holds under the old version must therefore re-attach (miss the
    pool) under a rolled version — the exact eviction RFC §9.7 asks for."""
    import src.cuts.families.region_capacity_typed as rct

    master, state, _g = _bound_region_world()
    controller = _controller_e(master)
    a1 = _attach(controller, state, 1)
    assert a1 >= 1
    # Same version again → dedup (pool hit), zero re-attach.
    assert _attach(controller, state, 2) == 0

    # Roll the F1 compiler version: fingerprints shift, old pool entries no
    # longer match → the regenerated cut re-attaches instead of dedup-skip.
    monkeypatch.setattr(
        rct, "REGION_CAPACITY_COMPILER_VERSION", "rolled-test-version-v999"
    )
    a3 = _attach(controller, state, 3)
    assert a3 >= 1, "compiler rollback must evict the stale fingerprint"


def test_gate7_rollback_drill_family_disable(tmp_path: Path) -> None:
    """RFC §9.7 in (b) semantics: positive epoch first (family APPLIED>0 on a
    complete segment), then a fresh master with the family disabled — zero
    constraints of that family on the new build, zero APPLIED on its complete
    segment, and the enabled_family_set component visibly changes the epoch
    semantic digest. Compiler-rollback variant is structurally covered: pools
    are per-master-build, so no cross-epoch suppression channel exists."""
    m1, s1, _g1 = _bound_region_world()
    l1 = CutLedgerWriter(tmp_path, scope_id="gate7", writer_id="w1")
    c1 = _controller_e(m1, cut_ledger=l1)
    assert _attach(c1, s1, 1) >= 1
    l1.seal()
    r1 = read_segment(l1.path)
    assert r1.status == "complete"
    assert any(
        e["event"] == "APPLIED" and e["family"] == "region_capacity"
        for e in r1.events
    )
    digest1 = m1.build_stats["cut_framework_attach_last"]["epoch_semantic_digest"]

    m2, s2, _g2 = _bound_region_world()
    l2 = CutLedgerWriter(tmp_path, scope_id="gate7", writer_id="w2")
    c2 = _controller_e(
        m2,
        cut_ledger=l2,
        enabled_cut_families=[
            "shape_packing_hall",
            "power_hitting_set",
            "pattern_nogood",
        ],
    )
    attached2 = _attach(c2, s2, 1)
    l2.seal()
    r2 = read_segment(l2.path)
    assert r2.status == "complete"
    assert r2.supports_negative_assertions  # negative claims need complete
    assert not any(
        e["event"] in {"APPLIED", "GENERATED"}
        and e.get("family") == "region_capacity"
        for e in r2.events
    )
    assert int(m2.build_stats.get("coordinate_framework_cut_count", 0)) == 0
    assert attached2 == 0  # this world only yields F1 cuts
    digest2 = m2.build_stats["cut_framework_attach_last"]["epoch_semantic_digest"]
    assert digest1 != digest2
    stats2 = m2.build_stats["cut_framework_attach_last"]
    assert "region_capacity" not in stats2["enabled_families"]
