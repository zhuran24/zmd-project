"""Tests for Family 5 pattern_nogood (P1.2B-F5).

Coverage:
- Generator: empty input / unregistered oracle / version mismatch / full
  FEASIBLE / happy path / canonical sort.
- Validator: 7-phase (cert_kind / witness hash / core_minimization /
  oracle registration + version / forbidden_pose_pattern schema +
  pose_domain + dedup / cert↔literal match / oracle re-verify).
- Red fixtures: F5-timeout-last-verified-core / F5-132-group-anonymous /
  F5-cardinality-unsound-routing.
- Watcher: pattern_nogood watcher_keys helper.
- Registry: register / lookup / clear semantics.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pytest

from src.cuts.families.pattern_nogood import (
    validate_pattern_nogood,
    watcher_keys_pattern_nogood,
)
from src.cuts.helpers.bounded_core_minimizer import (
    LiteralAssignment,
    MinimizerBudget,
    OracleVerdict,
    canonical_sort_assignment,
)
from src.cuts.lifecycle import (
    AnonymousSlotRef,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    GroupState,
    OracleCert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    evaluate_literal_multiset,
)
from src.cuts.oracles.pattern_nogood_oracle import (
    clear_sub_problem_oracle_registry,
    generate_pattern_nogood_cuts,
    lookup_sub_problem_oracle,
    register_sub_problem_oracle,
    registered_sub_problem_oracle_names,
)


# ---- fixtures --------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_sub_problem_oracle_registry()
    yield
    clear_sub_problem_oracle_registry()


@dataclass
class FakeAdapter:
    """Configurable sub-problem oracle adapter for tests.

    verdict_map: keyed by canonical-sorted assignment tuple → (verdict, blob).
    """

    name: str
    version: str
    verdict_map: Dict[Tuple[LiteralAssignment, ...], Tuple[OracleVerdict, bytes]]
    default_verdict: OracleVerdict = "FEASIBLE"
    default_blob: bytes = b""
    raise_on_query: bool = False
    calls: List[Tuple[LiteralAssignment, ...]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.calls = []

    def query(
        self,
        core: Tuple[LiteralAssignment, ...],
        state: BState,
        *,
        deadline_seconds: float,
    ) -> Tuple[OracleVerdict, bytes]:
        del state, deadline_seconds  # fake adapter ignores
        self.calls.append(core)
        if self.raise_on_query:
            raise RuntimeError("fake adapter blew up")
        key = canonical_sort_assignment(core)
        return self.verdict_map.get(key, (self.default_verdict, self.default_blob))


def _make_state(
    *,
    groups: Dict[str, GroupState] | None = None,
    source_digest: str = "test-source-digest",
) -> BState:
    if groups is None:
        groups = {
            "g1": GroupState(
                group_id="g1",
                demand=2,
                pose_domain=frozenset({"pA", "pB", "pC"}),
                selected_poses=[],
            ),
            "g2": GroupState(
                group_id="g2",
                demand=2,
                pose_domain=frozenset({"pX", "pY"}),
                selected_poses=[],
            ),
        }
    state = BState(groups=groups)
    state.source_digest = source_digest
    return state


def _make_full_assignment(pairs: List[Tuple[str, int, str]]) -> Tuple[CutLiteral, ...]:
    return tuple(
        CutLiteral(slot_ref=AnonymousSlotRef(group_id=g, slot_index=s), pose_id=p)
        for (g, s, p) in pairs
    )


def _tamper_cert(cut: Cut, mutate) -> Cut:
    """Return a new Cut with cert payload mutated by ``mutate(dict)``.

    Re-computes cert_hash + oracle_cert_hash to keep R3 integrity check happy
    (we want to test family validator behavior, not R3 catch).
    """
    cert_dict = json.loads(cut.cert.cert_payload)
    mutate(cert_dict)
    new_payload = json.dumps(cert_dict, sort_keys=True, ensure_ascii=False).encode("utf-8")
    new_hash = hashlib.sha256(new_payload).hexdigest()
    return Cut(
        cut_id=cut.cut_id,
        family=cut.family,
        literals=cut.literals,
        geometric_payload=cut.geometric_payload,
        scope=cut.scope,
        cert=OracleCert(cert_kind=cut.cert.cert_kind, cert_payload=new_payload, cert_hash=new_hash),
        family_version=cut.family_version,
        validator_version=cut.validator_version,
        oracle_name=cut.oracle_name,
        oracle_cert_hash=new_hash,
        minimization_audit=dict(cut.minimization_audit),
        iter_index=cut.iter_index,
    )


def _build_happy_cut(state: BState) -> Tuple[Cut, FakeAdapter]:
    """Helper for validator tests: generate one F5 cut via the standard path."""
    full = _make_full_assignment([("g1", 0, "pA"), ("g2", 0, "pX")])
    triples_sorted = canonical_sort_assignment(
        tuple((lit.slot_ref.group_id, lit.slot_ref.slot_index, lit.pose_id) for lit in full)
    )
    adapter = FakeAdapter(
        name="binding_v1",
        version="v1.0",
        verdict_map={triples_sorted: ("INFEASIBLE", b"witness-blob-bytes")},
    )
    register_sub_problem_oracle(adapter)
    cuts = generate_pattern_nogood_cuts(
        state,
        sub_problem_oracle=adapter,
        full_assignment_literals=full,
        budget=MinimizerBudget(max_calls=10, max_seconds=2.0),
        iter_index=0,
    )
    assert len(cuts) == 1, f"expected 1 cut, got {len(cuts)}"
    return cuts[0], adapter


# ---- generator -------------------------------------------------------------


def test_generate_empty_assignment_returns_empty():
    adapter = FakeAdapter(name="binding_v1", version="v1.0", verdict_map={})
    register_sub_problem_oracle(adapter)
    cuts = generate_pattern_nogood_cuts(
        _make_state(), sub_problem_oracle=adapter, full_assignment_literals=()
    )
    assert cuts == []


def test_generate_oracle_not_registered_returns_empty():
    adapter = FakeAdapter(name="evil_v9", version="v9.0", verdict_map={})
    # NOT registered
    full = _make_full_assignment([("g1", 0, "pA")])
    cuts = generate_pattern_nogood_cuts(
        _make_state(), sub_problem_oracle=adapter, full_assignment_literals=full
    )
    assert cuts == []


def test_generate_oracle_version_mismatch_returns_empty():
    registered = FakeAdapter(name="binding_v1", version="v1.0", verdict_map={})
    register_sub_problem_oracle(registered)
    impostor = FakeAdapter(name="binding_v1", version="v9.0", verdict_map={})
    full = _make_full_assignment([("g1", 0, "pA")])
    cuts = generate_pattern_nogood_cuts(
        _make_state(), sub_problem_oracle=impostor, full_assignment_literals=full
    )
    assert cuts == []


def test_generate_full_assignment_feasible_returns_empty():
    adapter = FakeAdapter(
        name="binding_v1",
        version="v1.0",
        verdict_map={},
        default_verdict="FEASIBLE",
    )
    register_sub_problem_oracle(adapter)
    full = _make_full_assignment([("g1", 0, "pA")])
    cuts = generate_pattern_nogood_cuts(
        _make_state(), sub_problem_oracle=adapter, full_assignment_literals=full
    )
    assert cuts == []  # ValueError from minimizer → fail-closed


def test_generate_happy_path_produces_cut():
    cut, _ = _build_happy_cut(_make_state())
    assert cut.family == "pattern_nogood"
    assert cut.literals is not None and len(cut.literals) == 2
    assert cut.geometric_payload is None
    assert cut.cert.cert_kind == "bounded_deletion_core"
    assert cut.oracle_cert_hash == cut.cert.cert_hash  # R3 invariant


def test_generate_cut_literals_canonical_sorted():
    state = _make_state()
    # input out of canonical order
    full = _make_full_assignment([("g2", 0, "pX"), ("g1", 0, "pA")])
    triples_sorted = canonical_sort_assignment(
        tuple((lit.slot_ref.group_id, lit.slot_ref.slot_index, lit.pose_id) for lit in full)
    )
    adapter = FakeAdapter(
        name="binding_v1",
        version="v1.0",
        verdict_map={triples_sorted: ("INFEASIBLE", b"witness")},
    )
    register_sub_problem_oracle(adapter)
    cuts = generate_pattern_nogood_cuts(
        state, sub_problem_oracle=adapter, full_assignment_literals=full
    )
    assert len(cuts) == 1
    canonical_first = cuts[0].literals[0]
    assert (canonical_first.slot_ref.group_id, canonical_first.pose_id) == ("g1", "pA")


# ---- validator -------------------------------------------------------------


def test_validate_ok_path():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    vr = validate_pattern_nogood(cut, state, canonical_rules={})
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_validate_schema_err_cert_kind_wrong():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    tampered = _tamper_cert(cut, lambda d: d.__setitem__("cert_kind", "evil_kind"))
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "cert_kind" in (vr.detail or "")


def test_validate_schema_err_oracle_not_registered_at_validate_time():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    clear_sub_problem_oracle_registry()  # remove the adapter post-generate
    vr = validate_pattern_nogood(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "not in registry" in (vr.detail or "")


def test_validate_unsound_oracle_version_mismatch():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    tampered = _tamper_cert(
        cut, lambda d: d.__setitem__("sub_problem_oracle_version", "v9.0")
    )
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "version mismatch" in (vr.detail or "")


def test_validate_schema_err_size_before_bool():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    tampered = _tamper_cert(
        cut, lambda d: d["core_minimization"].__setitem__("size_before", True)
    )
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "size_before" in (vr.detail or "")


def test_validate_schema_err_stopped_reason_not_closed():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    tampered = _tamper_cert(
        cut, lambda d: d["core_minimization"].__setitem__("stopped_reason", "OK")
    )
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "stopped_reason" in (vr.detail or "")


def test_validate_unsound_is_verified_infeasible_false():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    tampered = _tamper_cert(
        cut, lambda d: d["core_minimization"].__setitem__("is_verified_infeasible", False)
    )
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "is_verified_infeasible" in (vr.detail or "")


def test_validate_schema_err_is_verified_infeasible_int_not_bool():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    tampered = _tamper_cert(
        cut, lambda d: d["core_minimization"].__setitem__("is_verified_infeasible", 1)
    )
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "is_verified_infeasible" in (vr.detail or "")


def test_validate_schema_err_forbidden_pose_pattern_duplicate():
    state = _make_state()
    cut, _ = _build_happy_cut(state)

    def _add_dup(d):
        d["forbidden_pose_pattern"].append(d["forbidden_pose_pattern"][0])

    tampered = _tamper_cert(cut, _add_dup)
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "duplicate" in (vr.detail or "")


def test_validate_unsound_pose_not_in_domain():
    state = _make_state()
    cut, _ = _build_happy_cut(state)

    def _alter(d):
        # change pose_id to one not in g1.pose_domain
        d["forbidden_pose_pattern"][0][2] = "pZZZ_not_in_domain"

    tampered = _tamper_cert(cut, _alter)
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "pose_domain" in (vr.detail or "")


def test_validate_unsound_unknown_group_id():
    state = _make_state()
    cut, _ = _build_happy_cut(state)

    def _alter(d):
        d["forbidden_pose_pattern"][0][0] = "ghost_group_id"

    tampered = _tamper_cert(cut, _alter)
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "unknown group_id" in (vr.detail or "")


def test_validate_unsound_cert_literals_length_mismatch():
    """cut.literals length differs from cert.forbidden_pose_pattern length.

    To exercise the cert↔literals binding layer (not the schema-level
    size_after cross-check added in Gemini round 2 fix #A.2), the test must
    drop a pattern entry AND update size_after to match, so the schema check
    passes and validation falls through to the literal-match layer.
    """
    state = _make_state()
    cut, _ = _build_happy_cut(state)

    def _drop_one(d):
        d["forbidden_pose_pattern"] = d["forbidden_pose_pattern"][:1]
        d["core_minimization"]["size_after"] = 1

    tampered = _tamper_cert(cut, _drop_one)
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "length" in (vr.detail or "")


def test_validate_schema_err_size_after_mismatches_pattern_length():
    """Gemini F5 round 2 review #A.2: pattern length must equal size_after."""
    state = _make_state()
    cut, _ = _build_happy_cut(state)

    def _drop_one_pattern_only(d):
        # Drop one pattern entry but leave size_after unchanged → schema_err.
        d["forbidden_pose_pattern"] = d["forbidden_pose_pattern"][:1]

    tampered = _tamper_cert(cut, _drop_one_pattern_only)
    vr = validate_pattern_nogood(tampered, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "size_after" in (vr.detail or "")


def test_validate_unsound_oracle_reverify_feasible():
    state = _make_state()
    cut, adapter = _build_happy_cut(state)
    # Mutate adapter to return FEASIBLE on re-verify
    adapter.verdict_map.clear()
    adapter.default_verdict = "FEASIBLE"
    vr = validate_pattern_nogood(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "FEASIBLE" in (vr.detail or "")


def test_validate_unsound_oracle_reverify_unknown():
    state = _make_state()
    cut, adapter = _build_happy_cut(state)
    adapter.verdict_map.clear()
    adapter.default_verdict = "UNKNOWN"
    vr = validate_pattern_nogood(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "UNKNOWN" in (vr.detail or "")


def test_validate_timeout_on_oracle_reverify_timeout():
    state = _make_state()
    cut, adapter = _build_happy_cut(state)
    adapter.verdict_map.clear()
    adapter.default_verdict = "TIMEOUT"
    vr = validate_pattern_nogood(cut, state, canonical_rules={})
    assert vr.kind == "timeout"


def test_validate_timeout_on_oracle_reverify_raises():
    """Per Gemini F5 round 3 review #2: adapter exception → timeout (quarantine), not unsound.

    Rationale: 'unsound' means cert is mathematically false (permanent discard);
    an adapter exception is transient (network/OOM/state blip) and should
    quarantine the cut for later re-verification, not destroy it.
    """
    state = _make_state()
    cut, adapter = _build_happy_cut(state)
    adapter.raise_on_query = True
    vr = validate_pattern_nogood(cut, state, canonical_rules={})
    assert vr.kind == "timeout"
    assert "raised" in (vr.detail or "")


def test_minimizer_bogus_oracle_verdict_fails_closed():
    """Per Gemini F5 round 3 review #1: out-of-closed-set verdict → EXCEPTION_FAIL_CLOSED.

    Without the explicit VALID_ORACLE_VERDICTS check in the minimizer, a
    buggy adapter returning 'BOGUS' would silently fall through (neither
    shrink core nor flag had_inconclusive), breaking the is_minimal contract.
    """
    from src.cuts.helpers.bounded_core_minimizer import (
        CoreStoppedReason,
        MinimizerBudget,
        deletion_minimize_core,
    )

    a = ("g1", 0, "pA")
    b = ("g2", 0, "pB")
    call_count = {"n": 0}

    def bogus_oracle(core):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "INFEASIBLE"  # initial verify
        return "BOGUS_VERDICT"  # type: ignore[return-value]

    result = deletion_minimize_core((a, b), bogus_oracle, MinimizerBudget(max_calls=10, max_seconds=2.0))
    assert result.stopped_reason == CoreStoppedReason.EXCEPTION_FAIL_CLOSED
    assert result.is_minimal is False
    assert result.is_verified_infeasible is True


# ---- red fixtures (P0 per docs/项目说明/15_workflow_testing.md §21.7) ---


def test_F5_timeout_last_verified_core():
    """Red fixture #1: minimizer timeout → returns last verified core, not partial.

    Validator must still accept the cert (since size_after may < initially
    verified size if shrunk before timeout, but is_verified_infeasible=True).
    """
    from src.cuts.helpers.bounded_core_minimizer import (
        CoreMinimizeResult,
        CoreStoppedReason,
    )

    # Construct a result mimicking a TIMEOUT-stopped minimizer
    result = CoreMinimizeResult(
        core=(("g1", 0, "pA"), ("g2", 0, "pX")),
        is_minimal=False,
        is_verified_infeasible=True,
        calls=3,
        elapsed_seconds=10.0,
        stopped_reason=CoreStoppedReason.TIMEOUT,
        size_before=5,
        size_after=2,
    )
    state = _make_state()
    from src.cuts.oracles.pattern_nogood_oracle import _build_pattern_nogood_cut

    adapter = FakeAdapter(name="binding_v1", version="v1.0", verdict_map={})
    register_sub_problem_oracle(adapter)
    cut = _build_pattern_nogood_cut(
        state=state,
        sub_problem_oracle=adapter,
        result=result,
        iter_index=0,
    )
    # cert.core_minimization.stopped_reason="TIMEOUT" + is_verified_infeasible=True
    cert_dict = json.loads(cut.cert.cert_payload)
    assert cert_dict["core_minimization"]["stopped_reason"] == "TIMEOUT"
    assert cert_dict["core_minimization"]["is_verified_infeasible"] is True
    assert cert_dict["core_minimization"]["size_after"] == 2
    assert cert_dict["core_minimization"]["size_before"] == 5

    # Mock oracle that re-verifies the core as INFEASIBLE (the minimizer
    # already confirmed this before timing out)
    triples = tuple(tuple(t) for t in cert_dict["forbidden_pose_pattern"])
    adapter.verdict_map[triples] = ("INFEASIBLE", b"witness")
    vr = validate_pattern_nogood(cut, state, canonical_rules={})
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_F5_132_group_anonymous():
    """Red fixture #2: slot-index permutation triggers the same multiset eval.

    cut.literals references (g, slot=0, pA) + (g, slot=1, pB); evaluator must
    fire regardless of which slot index pA / pB physically land in state's
    selected_poses (state_machine_v2 §5 anonymity).
    """
    state = _make_state(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=2,
                pose_domain=frozenset({"pA", "pB"}),
                selected_poses=["pB", "pA"],  # state's order: slot 0 = pB, slot 1 = pA
            ),
        }
    )
    # cut declares slot 0 = pA, slot 1 = pB (different physical slot order)
    full = _make_full_assignment([("g1", 0, "pA"), ("g1", 1, "pB")])
    triples = canonical_sort_assignment(
        tuple((lit.slot_ref.group_id, lit.slot_ref.slot_index, lit.pose_id) for lit in full)
    )
    adapter = FakeAdapter(
        name="binding_v1",
        version="v1.0",
        verdict_map={triples: ("INFEASIBLE", b"witness")},
    )
    register_sub_problem_oracle(adapter)
    cuts = generate_pattern_nogood_cuts(
        state, sub_problem_oracle=adapter, full_assignment_literals=full
    )
    assert len(cuts) == 1
    # multiset evaluator fires even though slot order is reversed
    assert evaluate_literal_multiset(cuts[0], state) is True


def test_F5_cardinality_unsound_routing():
    """Red fixture #3: routing failure cannot auto-lift into a cardinality cut.

    A routing failure on assignment {(g1, p1), (g2, p2)} does NOT prove
    "any 2 facilities from g1+g2 is infeasible". F5 cert must list specific
    poses; a generic "size_after=2 means any 2-facility is bad" framing would
    be unsound.

    This test verifies that the cert structure REQUIRES specific pose names —
    swapping pose_id to a sibling in pose_domain (not the one actually proven
    infeasible) must be caught by the oracle re-verify step (it returns
    FEASIBLE on the wrong pattern).
    """
    state = _make_state()
    cut, adapter = _build_happy_cut(state)

    # Tamper: swap pose_id in forbidden_pose_pattern to a different valid pose
    # (pose_domain says pB / pC are valid for g1, original cut uses pA).
    # cut.literals stays in sync to bypass the literal-match check.
    def _swap_pose(d):
        d["forbidden_pose_pattern"][0][2] = "pB"  # was "pA"

    tampered = _tamper_cert(cut, _swap_pose)
    # Also rebuild literals to match (canonical sort assumed)
    new_literals = tuple(
        CutLiteral(slot_ref=AnonymousSlotRef(group_id=g, slot_index=s), pose_id=p)
        for (g, s, p) in [("g1", 0, "pB"), ("g2", 0, "pX")]
    )
    tampered_aligned = Cut(
        cut_id=tampered.cut_id,
        family=tampered.family,
        literals=new_literals,
        geometric_payload=None,
        scope=tampered.scope,
        cert=tampered.cert,
        family_version=tampered.family_version,
        validator_version=tampered.validator_version,
        oracle_name=tampered.oracle_name,
        oracle_cert_hash=tampered.oracle_cert_hash,
        minimization_audit=dict(tampered.minimization_audit),
        iter_index=tampered.iter_index,
    )

    # Adapter has no INFEASIBLE entry for the tampered pattern → re-verify
    # returns FEASIBLE (default) → unsound
    vr = validate_pattern_nogood(tampered_aligned, state, canonical_rules={})
    assert vr.kind == "unsound"


# ---- watcher_keys ----------------------------------------------------------


def test_watcher_keys_pattern_nogood():
    state = _make_state()
    cut, _ = _build_happy_cut(state)
    keys = watcher_keys_pattern_nogood(cut)
    assert keys["group_keys"] == ["g1", "g2"]
    assert keys["pose_keys"] == [("g1", "pA"), ("g2", "pX")]


# ---- registry --------------------------------------------------------------


def test_register_lookup_idempotent():
    adapter = FakeAdapter(name="binding_v1", version="v1.0", verdict_map={})
    register_sub_problem_oracle(adapter)
    register_sub_problem_oracle(adapter)  # idempotent on same name
    assert lookup_sub_problem_oracle("binding_v1") is adapter
    assert "binding_v1" in registered_sub_problem_oracle_names()


def test_register_bad_name_raises():
    adapter = FakeAdapter(name="", version="v1.0", verdict_map={})
    with pytest.raises(ValueError, match="adapter.name"):
        register_sub_problem_oracle(adapter)


def test_register_bad_version_raises():
    adapter = FakeAdapter(name="binding_v1", version="", verdict_map={})
    with pytest.raises(ValueError, match="adapter.version"):
        register_sub_problem_oracle(adapter)


def test_lookup_unregistered_returns_none():
    assert lookup_sub_problem_oracle("nonexistent_v9") is None
