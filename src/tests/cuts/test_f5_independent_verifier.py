"""RFC-002 batch D: the F5 independent binding-empty-domain verifier.

Covers the verifier as a standalone TCB unit, the double-implementation
differential against the production enumerator, and the RFC-002 §7 red-test
battery (malicious oracle, stale mapping, sequential isolation, oracle
unreachability via an AST import TRIPWIRE, env invariance, and differential
equivalence).
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from unittest import mock

import pytest

from src.cuts.verifiers.binding_empty_domain_verifier import (
    BindingDomainUndecidable,
    BindingEmptyDomainVerdict,
    binding_domain_is_empty,
    verify_binding_empty_domain,
)
from src.models.port_binding import enumerate_pose_level_port_bindings
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

# The verifiable-world / envelope fixtures live with the typed-platform suite;
# reuse them so the integration path is exercised through the real production
# registry rather than a re-implementation.
from src.tests.cuts.test_stage_b_typed_platform import (
    _PRODUCTION_ARTIFACT_HASHES,
    _DifferentialF5Oracle,
    _build_f5_verifiable_world,
    _f5_dead_pose,
    _f5_live_pose,
    _make_verifiable_pattern_cut,
    _pick_f5_verifiable_op,
    _trusted_test_envelope,
)
from src.cuts.oracles.pattern_nogood_oracle import (
    clear_sub_problem_oracle_registry,
    register_sub_problem_oracle,
)
from src.cuts.typed_platform import (
    CutRejection,
    ShadowValidated,
    build_production_registry,
    validate_and_compile_cut,
)

VERIFIER_PATH = Path(__file__).resolve().parents[2] / "cuts" / "verifiers" / "binding_empty_domain_verifier.py"


def _mk_pose(n_in: int, n_out: int, *, pose_id: str = "p") -> dict[str, object]:
    return {
        "pose_id": pose_id,
        "input_port_cells": [{"x": i, "y": 0, "dir": "N"} for i in range(n_in)],
        "output_port_cells": [{"x": i, "y": 9, "dir": "S"} for i in range(n_out)],
    }


# ---------------------------------------------------------------------------
# Verifier unit contracts
# ---------------------------------------------------------------------------


def test_zero_port_pose_has_empty_domain() -> None:
    op, _facility = _pick_f5_verifiable_op()
    assert binding_domain_is_empty(op, _mk_pose(0, 0)) is True


def test_saturated_pose_has_nonempty_domain() -> None:
    op, _facility = _pick_f5_verifiable_op()
    profile = OPERATION_PORT_PROFILES[op]
    need_in = sum(profile.input_slots.values())
    need_out = sum(profile.output_slots.values())
    assert binding_domain_is_empty(op, _mk_pose(need_in, need_out)) is False


def test_generic_hub_operation_is_undecidable() -> None:
    generic = next(
        op
        for op, profile in sorted(OPERATION_PORT_PROFILES.items())
        if profile.generic_input_slots or profile.generic_output_slots
    )
    with pytest.raises(BindingDomainUndecidable):
        binding_domain_is_empty(generic, _mk_pose(0, 0))


def test_unknown_operation_is_undecidable() -> None:
    with pytest.raises(BindingDomainUndecidable):
        binding_domain_is_empty("__no_such_operation__", _mk_pose(1, 1))


def test_malformed_port_cell_is_undecidable_not_empty() -> None:
    op, _facility = _pick_f5_verifiable_op()
    pose = {"pose_id": "p", "input_port_cells": [{"nope": 1}], "output_port_cells": []}
    with pytest.raises(BindingDomainUndecidable):
        binding_domain_is_empty(op, pose)


def test_top_level_confirms_dead_pose_and_refutes_live_pose() -> None:
    op, facility = _pick_f5_verifiable_op()
    group_id = f"group::{facility}::{op}::0"
    itf = {group_id: facility}
    pools = {facility: [_f5_dead_pose(), _f5_live_pose(op)]}

    dead = verify_binding_empty_domain([[group_id, 0, "p_dead"]], instance_to_facility_type=itf, facility_pools=pools)
    assert isinstance(dead, BindingEmptyDomainVerdict)
    assert dead.verified is True
    assert dead.witness_literal == (group_id, 0, "p_dead")

    live = verify_binding_empty_domain([[group_id, 0, "p_live"]], instance_to_facility_type=itf, facility_pools=pools)
    assert live.verified is False
    assert live.witness_literal is None


def test_top_level_reads_frozen_snapshot_pools() -> None:
    """The verifier must read the deep-frozen snapshot projection (dicts thawed
    to MappingProxy, lists to tuples), not just plain builtins."""
    state, snapshot, group_id = _build_f5_verifiable_world()
    inputs = snapshot.family_inputs["pattern_nogood"]
    verdict = verify_binding_empty_domain(
        [[group_id, 0, "p_dead"]],
        instance_to_facility_type=inputs.instance_to_facility_type,
        facility_pools=inputs.facility_pools,
    )
    assert verdict.verified is True


def test_pose_absent_from_pool_is_refuted() -> None:
    op, facility = _pick_f5_verifiable_op()
    group_id = f"group::{facility}::{op}::0"
    verdict = verify_binding_empty_domain(
        [[group_id, 0, "p_missing"]],
        instance_to_facility_type={group_id: facility},
        facility_pools={facility: [_f5_live_pose(op)]},
    )
    assert verdict.verified is False


def test_malformed_pattern_is_refused() -> None:
    verdict = verify_binding_empty_domain("not-a-pattern", instance_to_facility_type={}, facility_pools={})
    assert verdict.verified is False


# ---------------------------------------------------------------------------
# RFC-002 §7 red tests
# ---------------------------------------------------------------------------


def test_red1_malicious_infeasible_oracle_is_refuted_by_verifier() -> None:
    """§7.1: a malicious adapter returning INFEASIBLE for any core lets the
    generator emit a shadow, but the independent verifier must reject it — here
    the named pose has a fully saturated (non-empty) binding domain."""
    state, snapshot, group_id = _build_f5_verifiable_world(
        artifact_hashes=_PRODUCTION_ARTIFACT_HASHES,
    )
    # Point the pattern at the LIVE pose (non-empty domain); the fake oracle
    # still lies INFEASIBLE, so only the independent verifier can catch it.
    envelope = _trusted_test_envelope(_make_verifiable_pattern_cut(state, group_id, pose_id="p_live"), snapshot)
    clear_sub_problem_oracle_registry()
    register_sub_problem_oracle(_DifferentialF5Oracle())  # type: ignore[arg-type]
    try:
        result = validate_and_compile_cut(envelope, snapshot, build_production_registry())
    finally:
        clear_sub_problem_oracle_registry()
    assert isinstance(result, CutRejection)
    assert result.stage == "proof"
    assert "binding-empty-domain verifier" in result.reason


def test_red2_stale_operation_mapping_is_refuted() -> None:
    """§7.2: a group_id encoding an operation whose frozen facility differs from
    the instance→facility binding (a stale/spoofed mapping) cannot be confirmed —
    the verifier cross-checks the recovered operation against the frozen facility."""
    op, facility = _pick_f5_verifiable_op()
    # group_id claims a different facility than instance_to_facility_type binds.
    spoofed_group_id = f"group::{facility}::{op}::0"
    verdict = verify_binding_empty_domain(
        [[spoofed_group_id, 0, "p_dead"]],
        instance_to_facility_type={spoofed_group_id: "a_different_facility"},
        facility_pools={"a_different_facility": [_f5_dead_pose()]},
    )
    assert verdict.verified is False


def test_red3_sequential_calls_share_no_state() -> None:
    """§7.3: two sequential 'controllers' must not share any private mapping —
    the verifier is a pure function with no module-level mutable registry, so
    verdicts depend only on the arguments of each call."""
    op, facility = _pick_f5_verifiable_op()
    gid_a = f"group::{facility}::{op}::0"

    world_a = verify_binding_empty_domain(
        [[gid_a, 0, "p_dead"]],
        instance_to_facility_type={gid_a: facility},
        facility_pools={facility: [_f5_dead_pose()]},
    )
    # A second call with an unrelated binding must NOT inherit world A's mapping.
    world_b = verify_binding_empty_domain(
        [[gid_a, 0, "p_dead"]],
        instance_to_facility_type={gid_a: "unmapped_facility"},
        facility_pools={"unmapped_facility": [_f5_live_pose(op)]},
    )
    assert world_a.verified is True
    assert world_b.verified is False
    # Re-running world A after world B still yields A's answer (no carryover).
    world_a_again = verify_binding_empty_domain(
        [[gid_a, 0, "p_dead"]],
        instance_to_facility_type={gid_a: facility},
        facility_pools={facility: [_f5_dead_pose()]},
    )
    assert world_a_again.verified is True


def test_red4_verifier_module_imports_no_oracle_surface() -> None:
    """§7 independence TRIPWIRE (照 B5b 范式): the verifier file must not import
    the oracle / adapter / registry / production-enumerator modules, nor name
    their re-query / registry entry points.

    Threat-model boundary: this matches only statically written ``import`` nodes
    and bare/attribute name references.  Dynamic import (``importlib``, string
    building) escapes it by construction; a green run is NOT proof of absence.
    The hard guarantee remains the recompute-from-frozen-facts structure itself.
    """
    source = VERIFIER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_module_prefixes = (
        "src.cuts.oracles",  # pattern_nogood_oracle + the sub-problem registry
        "src.search.f5_binding_empty_domain_adapter",
        "src.models.port_binding",  # the production enumerator being differed against
    )
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                pytest.fail("verifier must not use relative imports")
            if node.module:
                imported.add(node.module)
    for module in imported:
        for prefix in forbidden_module_prefixes:
            assert not module.startswith(prefix), f"verifier imports forbidden oracle/adapter surface: {module}"

    forbidden_names = {
        "query_liftable",
        "lookup_sub_problem_oracle",
        "register_sub_problem_oracle",
        "clear_sub_problem_oracle_registry",
        "enumerate_pose_level_port_bindings",
        "enumerate_pose_level_port_bindings_with_cache_info",
        "SubProblemOracleAdapter",
        "BindingEmptyDomainAdapter",
    }
    referenced_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced_names.add(node.attr)
    leaked = forbidden_names & referenced_names
    assert not leaked, f"verifier references forbidden oracle/enumerator names: {sorted(leaked)}"


def test_red5_environment_change_does_not_affect_verifier() -> None:
    """§7.5: the adapter's RAB-SEP env toggle makes the ADAPTER refuse to lift,
    but the verifier reads no environment — its verdict is invariant."""
    op, facility = _pick_f5_verifiable_op()
    group_id = f"group::{facility}::{op}::0"
    args = dict(
        instance_to_facility_type={group_id: facility},
        facility_pools={facility: [_f5_dead_pose()]},
    )
    baseline = verify_binding_empty_domain([[group_id, 0, "p_dead"]], **args)
    with mock.patch.dict(
        os.environ,
        {"EXACT_B1_ROUTING_AWARE_BINDING": "1", "EXACT_CP_SAT_WORKERS": "7"},
    ):
        toggled = verify_binding_empty_domain([[group_id, 0, "p_dead"]], **args)
    assert baseline.verified is True
    assert toggled.verified is True
    assert baseline.verified == toggled.verified


def test_red6_differential_equivalence_with_production_enumerator() -> None:
    """§7.6: on a constructed (op, pose) sweep, the verifier's emptiness verdict
    equals the production enumerator's (raises-or-empty) verdict for every
    exact-binding operation."""

    def _enumerator_reports_empty(op: str, pose: dict[str, object]) -> bool:
        try:
            return len(enumerate_pose_level_port_bindings(op, pose)) == 0
        except ValueError:
            return True

    checked = 0
    for op, profile in sorted(OPERATION_PORT_PROFILES.items()):
        if profile.generic_input_slots or profile.generic_output_slots:
            with pytest.raises(BindingDomainUndecidable):
                binding_domain_is_empty(op, _mk_pose(1, 1))
            continue
        need_in = sum(profile.input_slots.values())
        need_out = sum(profile.output_slots.values())
        for din in range(0, need_in + 3):
            for dout in range(0, need_out + 3):
                pose = _mk_pose(din, dout)
                assert binding_domain_is_empty(op, pose) == _enumerator_reports_empty(op, pose), (
                    f"differential mismatch for {op} in={din} out={dout}"
                )
                checked += 1
    assert checked > 0


def test_verifier_is_deterministic() -> None:
    op, facility = _pick_f5_verifiable_op()
    group_id = f"group::{facility}::{op}::0"
    args = dict(
        instance_to_facility_type={group_id: facility},
        facility_pools={facility: [_f5_dead_pose(), _f5_live_pose(op)]},
    )
    verdicts = {verify_binding_empty_domain([[group_id, 0, "p_dead"]], **args).verified for _ in range(5)}
    assert verdicts == {True}


# ---------------------------------------------------------------------------
# B-D dual-review amendments (2026-07-12)
# ---------------------------------------------------------------------------


def test_real_adapter_currently_rejected_before_verifier_reaches_it() -> None:
    """Reachability sentinel for the adapter frozen-tuple gap (dual-review MEDIUM).

    The PRODUCTION BindingEmptyDomainAdapter._find_pose uses isinstance(pool,
    list), but the frozen snapshot thaws pools to tuples — so on the typed path
    the real adapter answers FEASIBLE for every literal and the (earlier)
    _reverify_f5_oracle stage rejects the cut BEFORE the independent verifier
    runs.  Consequence: the "independently-verified" tag is currently
    unreachable with the real adapter; only test oracles exercise the verifier.

    This test PINS that fail-closed behaviour.  When the adapter gap is fixed
    (F5 promotion batch), this test MUST go red — at that point replace it with
    a real-adapter end-to-end assertion that the shadow carries
    telemetry_tag == "independently-verified" (do NOT silently delete).
    """
    from src.search.f5_binding_empty_domain_adapter import (
        build_binding_empty_domain_adapter,
    )

    state, snapshot, group_id = _build_f5_verifiable_world(
        artifact_hashes=_PRODUCTION_ARTIFACT_HASHES,
    )
    op, _facility = _pick_f5_verifiable_op()
    adapter = build_binding_empty_domain_adapter([{"group_id": group_id, "operation_type": op}])
    envelope = _trusted_test_envelope(_make_verifiable_pattern_cut(state, group_id, pose_id="p_dead"), snapshot)
    clear_sub_problem_oracle_registry()
    register_sub_problem_oracle(adapter)  # type: ignore[arg-type]
    try:
        result = validate_and_compile_cut(envelope, snapshot, build_production_registry())
    finally:
        clear_sub_problem_oracle_registry()
    assert isinstance(result, CutRejection)
    assert result.stage == "proof"
    assert "FEASIBLE, expected INFEASIBLE" in result.reason


def test_differential_bool_coordinate_corner_verifier_refuses() -> None:
    """Dual-review LOW: bool coordinates are an implementation-divergence corner.

    The production enumerator normalises int(True) == 1 and would count the
    cell; the verifier's _require_int_like rejects bool and raises
    BindingDomainUndecidable.  The divergence direction is SAFE (undecidable ->
    no empty-domain confirmation -> refute), so the differential asserts the
    verifier side refuses rather than matching the enumerator.
    """
    op, _facility = _pick_f5_verifiable_op()
    pose = {
        "pose_id": "p_bool",
        "input_port_cells": [{"x": True, "y": 0, "dir": "N"}],
        "output_port_cells": [{"x": 0, "y": 9, "dir": "S"}],
    }
    with pytest.raises(BindingDomainUndecidable):
        binding_domain_is_empty(op, pose)


def test_tag_grant_is_downstream_of_verifier_call_linear_chain() -> None:
    """AST sentinel for the static shadow_telemetry_tag (dual-review LOW).

    The "independently-verified" tag is a static class attribute, coupled to
    the verifier actually running ONLY by parse_and_validate_proof being a
    linear, no-early-exit chain ending in the verifier call.  TRIPWIRE: this
    sentinel pins that structure — the _verify_f5_binding_empty_domain call
    must be a TOP-LEVEL statement of parse_and_validate_proof (not nested under
    if/try/with), and no `return` may precede it.  Dynamic-grant refactor
    (token/return-value driven tag) is registered for the F5 promotion batch.
    """
    import src.cuts.typed_platform as tp

    source = Path(tp.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "_PatternNogoodPlugin":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "parse_and_validate_proof":
                    func = item
    assert func is not None, "_PatternNogoodPlugin.parse_and_validate_proof not found"

    verifier_stmt_idx = None
    for idx, stmt in enumerate(func.body):
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Call):
                target = sub.func
                name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
                if name == "_verify_f5_binding_empty_domain":
                    assert isinstance(stmt, (ast.Expr, ast.Assign)), (
                        f"verifier call must be a top-level linear statement, found inside {type(stmt).__name__}"
                    )
                    verifier_stmt_idx = idx
    assert verifier_stmt_idx is not None, "verifier call missing from parse_and_validate_proof"
    for stmt in func.body[:verifier_stmt_idx]:
        for sub in ast.walk(stmt):
            assert not isinstance(sub, ast.Return), (
                "early return before the verifier call breaks the tag-grant linearity"
            )
