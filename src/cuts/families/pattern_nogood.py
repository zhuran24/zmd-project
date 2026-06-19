"""Family 5 pattern_nogood — production validator (P1.2B-F5).

Validator re-verifies F5 cuts as the trust boundary: oracle responses are
treated as untrusted, every cert field is schema-checked, and the sub-problem
oracle is re-queried on the forbidden core to confirm INFEASIBLE.

Cert payload contract (canonical JSON, per
``src/cuts/oracles/pattern_nogood_oracle._build_pattern_nogood_cut``):

    cert_kind: "bounded_deletion_core"
    sub_problem_oracle_name: str (∈ _REGISTERED_SUB_PROBLEM_ORACLES)
    sub_problem_oracle_version: str (strict-equals registry value)
    forbidden_pose_pattern: list of [group_id, slot_index, pose_id], dedup
    core_minimization:
        size_before, size_after, calls: strict int >= 0
        stopped_reason: ∈ {INFEASIBLE_VERIFIED, TIMEOUT, MAX_CALLS,
                          EXCEPTION_FAIL_CLOSED}
        is_verified_infeasible: True (rejected otherwise)

Note: Sub-problem witness bytes are NOT included in cert_payload (per Gemini
F5 review #1 BLOCKER fix). Witness bytes can be non-deterministic across
workers, which would break cert_hash cross-worker reproducibility. Validator
re-queries the oracle on forbidden_pose_pattern as its soundness check —
identity of the witness bytes is irrelevant, only the INFEASIBLE verdict matters.

Re-verify budget is conservative — Phase 1.2 default 5s wall. TIMEOUT → ValidationResult("timeout") so CutStore can quarantine without classifying as unsound.

Evaluator: F5 is literal-based, delegated to ``lifecycle.evaluate_literal_multiset``
via ``step_7_evaluate_cut`` dispatch (no F5-specific evaluator).

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F5
- docs/项目说明/12_go_criteria.md §8.1.x acceptance A
- docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from src.cuts.helpers.bounded_core_minimizer import (
    VALID_STOPPED_REASONS,
)
from src.cuts.lifecycle import BState, Cut, ValidationResult, validate_cert_payload
from src.cuts.oracles.pattern_nogood_oracle import (
    SubProblemOracleAdapter,
    lookup_sub_problem_oracle,
)


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


# Validator re-verify deadline. Per Gemini F5 round 1 #3 it must be >= the
# generator's MinimizerBudget.max_seconds (default 10.0s). Per Gemini F5
# round 2 #B it must also absorb machine-load noise — a generator finishing
# in 9.9s should not be quarantined by a validator hitting 10.1s on a busy
# host. 1.5× generator default provides a usable buffer. Phase 1.5+ may tune
# this against real binding/routing/pcr_cut adapter latency telemetry.
_VALIDATOR_REVERIFY_DEADLINE_SECONDS: float = 15.0

def _vr(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(
        kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None
    )


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _parse_cert_payload(cert_payload: bytes) -> Dict[str, Any]:
    """Parse cert payload JSON. Raises ValueError on malformed input."""
    return validate_cert_payload("pattern_nogood", cert_payload)


def _validate_cert_kind(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    cert_kind = cert_dict.get("cert_kind")
    if cert_kind != "bounded_deletion_core":
        return _vr(
            "schema_err",
            t0,
            f"cert_kind must be 'bounded_deletion_core', got {cert_kind!r}",
        )
    return None


def _validate_sub_problem_oracle(
    cert_dict: Dict[str, Any], t0: float
) -> Tuple[Optional[ValidationResult], Optional[SubProblemOracleAdapter]]:
    name = cert_dict.get("sub_problem_oracle_name")
    version = cert_dict.get("sub_problem_oracle_version")
    if not _is_non_empty_str(name):
        return (
            _vr("schema_err", t0, f"sub_problem_oracle_name must be non-empty str, got {name!r}"),
            None,
        )
    if not _is_non_empty_str(version):
        return (
            _vr(
                "schema_err",
                t0,
                f"sub_problem_oracle_version must be non-empty str, got {version!r}",
            ),
            None,
        )
    adapter = lookup_sub_problem_oracle(cast(str, name))
    if adapter is None:
        return (
            _vr(
                "schema_err",
                t0,
                f"sub_problem_oracle_name {name!r} not in registry (fail-closed)",
            ),
            None,
        )
    if adapter.version != version:
        return (
            _vr(
                "unsound",
                t0,
                f"sub_problem_oracle_version mismatch: cert={version!r}, registry={adapter.version!r}",
            ),
            None,
        )
    return None, adapter


# Witness hash validation removed (Gemini F5 review #1 fix): witness bytes
# are not deterministic across workers; soundness comes from oracle re-query,
# not byte-equal witness identity.


def _validate_core_minimization(
    cert_dict: Dict[str, Any], t0: float
) -> Optional[ValidationResult]:
    cm = cert_dict.get("core_minimization")
    if not isinstance(cm, dict):
        return _vr("schema_err", t0, f"core_minimization must be dict, got {type(cm).__name__}")
    for field in ("size_before", "size_after", "calls"):
        v = cm.get(field)
        if not _is_strict_int(v):
            return _vr(
                "schema_err",
                t0,
                f"core_minimization.{field} must be strict int, got {v!r}",
            )
        if cast(int, v) < 0:
            return _vr("schema_err", t0, f"core_minimization.{field} must be >= 0, got {v}")
    if cast(int, cm["size_after"]) > cast(int, cm["size_before"]):
        return _vr(
            "schema_err",
            t0,
            f"size_after ({cm['size_after']}) > size_before ({cm['size_before']})",
        )
    reason = cm.get("stopped_reason")
    if not isinstance(reason, str) or reason not in VALID_STOPPED_REASONS:
        return _vr(
            "schema_err",
            t0,
            f"core_minimization.stopped_reason {reason!r} not in {sorted(VALID_STOPPED_REASONS)}",
        )
    verified = cm.get("is_verified_infeasible")
    if not isinstance(verified, bool):
        return _vr(
            "schema_err",
            t0,
            f"core_minimization.is_verified_infeasible must be bool, got {type(verified).__name__}",
        )
    if verified is not True:
        return _vr(
            "unsound",
            t0,
            "core_minimization.is_verified_infeasible is False (cert self-declares unverified)",
        )
    return None


def _validate_forbidden_pose_pattern(
    cert_dict: Dict[str, Any], state: BState, t0: float
) -> Tuple[Optional[ValidationResult], Optional[Tuple[Tuple[str, int, str], ...]]]:
    raw = cert_dict.get("forbidden_pose_pattern")
    if not isinstance(raw, list) or not raw:
        return (
            _vr("schema_err", t0, "forbidden_pose_pattern must be non-empty list"),
            None,
        )
    triples: List[Tuple[str, int, str]] = []
    seen: set[Tuple[str, int, str]] = set()
    seen_slots: set[Tuple[str, int]] = set()
    per_group_count: Dict[str, int] = {}
    for idx, entry in enumerate(raw):
        if not isinstance(entry, list) or len(entry) != 3:
            return (
                _vr(
                    "schema_err",
                    t0,
                    f"forbidden_pose_pattern[{idx}] must be 3-element list",
                ),
                None,
            )
        g, s, p = entry
        if not _is_non_empty_str(g):
            return (
                _vr("schema_err", t0, f"forbidden_pose_pattern[{idx}].group_id must be non-empty str, got {g!r}"),
                None,
            )
        if not _is_strict_int(s) or cast(int, s) < 0:
            return (
                _vr("schema_err", t0, f"forbidden_pose_pattern[{idx}].slot_index must be strict int >= 0, got {s!r}"),
                None,
            )
        if not _is_non_empty_str(p):
            return (
                _vr("schema_err", t0, f"forbidden_pose_pattern[{idx}].pose_id must be non-empty str, got {p!r}"),
                None,
            )
        triple = (cast(str, g), cast(int, s), cast(str, p))
        if triple in seen:
            return (
                _vr("schema_err", t0, f"forbidden_pose_pattern duplicate triple {triple!r}"),
                None,
            )
        # pose ∈ state.groups[g].pose_domain check (defense-in-depth)
        group_state = state.groups.get(triple[0])
        if group_state is None:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"forbidden_pose_pattern[{idx}] references unknown group_id {triple[0]!r}",
                ),
                None,
            )
        # Slot ids are anonymous but still denote distinct instances inside one
        # group.  The oracle re-query may treat duplicate slot assignments as
        # trivially UNSAT (one slot cannot take two poses), while the generic
        # evaluator intentionally drops slot ids and checks only a (group, pose)
        # multiset.  Therefore every cert literal must bind a real, unique slot.
        if triple[1] >= group_state.demand:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"forbidden_pose_pattern[{idx}] slot_index {triple[1]} >= "
                    f"group {triple[0]!r} demand {group_state.demand}",
                ),
                None,
            )
        slot_key = (triple[0], triple[1])
        if slot_key in seen_slots:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"forbidden_pose_pattern[{idx}] reuses slot {slot_key!r}; "
                    "slot-colliding cores are oracle-trivial but evaluator lifts them to a stronger multiset cut",
                ),
                None,
            )
        seen_slots.add(slot_key)
        per_group_count[triple[0]] = per_group_count.get(triple[0], 0) + 1
        if per_group_count[triple[0]] > group_state.demand:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"forbidden_pose_pattern contains {per_group_count[triple[0]]} literals "
                    f"for group {triple[0]!r} with demand {group_state.demand}",
                ),
                None,
            )
        if triple[2] not in group_state.pose_domain:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"forbidden_pose_pattern[{idx}] pose_id {triple[2]!r} not in group {triple[0]!r} pose_domain",
                ),
                None,
            )
        seen.add(triple)
        triples.append(triple)
    return None, tuple(triples)


def _validate_cert_literals_match(
    cut: Cut,
    cert_triples: Tuple[Tuple[str, int, str], ...],
    t0: float,
) -> Optional[ValidationResult]:
    """cert.forbidden_pose_pattern ↔ cut.literals binding (multiset, not ordered).

    Per Gemini F5 round 2 review #C: comparing ordered tuples violates
    state_machine_v2 §5 multiset anonymity — if serialization or any
    legitimate transformation reorders cut.literals, an ordered check would
    falsely return unsound. Both cert and literals are dedup'd (generator
    invariant + validator forbidden_pose_pattern dedup check), so frozenset
    equality is equivalent to multiset equality and respects anonymity.
    """
    if cut.literals is None or len(cut.literals) != len(cert_triples):
        cut_len = 0 if cut.literals is None else len(cut.literals)
        return _vr(
            "unsound",
            t0,
            f"cut.literals length {cut_len} != forbidden_pose_pattern length {len(cert_triples)}",
        )
    literal_triples_set = frozenset(
        (lit.slot_ref.group_id, lit.slot_ref.slot_index, lit.pose_id)
        for lit in cut.literals
    )
    cert_triples_set = frozenset(cert_triples)
    if literal_triples_set != cert_triples_set:
        return _vr(
            "unsound",
            t0,
            "cut.literals do not match cert.forbidden_pose_pattern (set equality required, order-independent)",
        )
    return None


def _reverify_sub_problem_oracle(
    adapter: SubProblemOracleAdapter,
    cert_triples: Tuple[Tuple[str, int, str], ...],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    """Re-query the sub-problem oracle on the forbidden core. Must return INFEASIBLE.

    Per Gemini F5 review #1 BLOCKER fix: witness bytes are non-deterministic
    across workers; we no longer compare witness hash against cert. The
    soundness contract is the INFEASIBLE verdict alone.
    """
    try:
        verdict, _witness_blob = adapter.query(
            cert_triples,
            state,
            deadline_seconds=_VALIDATOR_REVERIFY_DEADLINE_SECONDS,
        )
    except Exception as e:  # noqa: BLE001 — oracle is untrusted
        # Per Gemini F5 round 3 review #2: an adapter exception (network blip,
        # OOM, transient state) is "temporarily unable to verify", not "the
        # cert is mathematically false". Returning "unsound" would permanently
        # discard the cut. Use "timeout" semantics — CutStore quarantines and
        # the cut may be revived on a future state.
        return _vr(
            "timeout",
            t0,
            f"sub-problem oracle re-verify raised {type(e).__name__}: {e} (treated as transient, quarantine)",
        )
    if verdict == "TIMEOUT":
        return _vr(
            "timeout",
            t0,
            f"sub-problem oracle re-verify TIMEOUT (deadline={_VALIDATOR_REVERIFY_DEADLINE_SECONDS}s)",
        )
    if verdict != "INFEASIBLE":
        return _vr(
            "unsound",
            t0,
            f"sub-problem oracle re-verify returned {verdict!r}, expected INFEASIBLE",
        )
    return None


def validate_pattern_nogood(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """Re-validate F5 pattern_nogood cut. Trust boundary: oracle is untrusted.

    7-phase validation:
    1. cert payload JSON parse
    2. cert_kind == 'bounded_deletion_core'
    3. sub_problem_oracle_name in registry + version strict-equal
    4. sub_problem_witness_hash hex sha256 schema
    5. core_minimization fields schema (strict int / closed-set stopped_reason
       / is_verified_infeasible True)
    6. forbidden_pose_pattern dedup + each entry schema + pose ∈ pose_domain +
       1:1 match with cut.literals in canonical order
    7. sub-problem oracle re-verify on forbidden core (TIMEOUT → quarantine)
    """
    t0 = time.monotonic()
    del canonical_rules

    if cut.cert is None or cut.literals is None or len(cut.literals) == 0:
        return _vr(
            "schema_err",
            t0,
            "F5 requires non-empty cert + literals (cut_lifecycle_v2 §3)",
        )

    try:
        cert_dict = _parse_cert_payload(cut.cert.cert_payload)
    except ValueError as e:
        return _vr("schema_err", t0, str(e))

    for error in (
        _validate_cert_kind(cert_dict, t0),
        _validate_core_minimization(cert_dict, t0),
    ):
        if error is not None:
            return error

    oracle_err, adapter = _validate_sub_problem_oracle(cert_dict, t0)
    if oracle_err is not None:
        return oracle_err
    if adapter is None:  # belt-and-suspenders (None implies oracle_err non-None)
        return _vr("schema_err", t0, "sub-problem oracle adapter resolution failed")

    pattern_err, cert_triples = _validate_forbidden_pose_pattern(cert_dict, state, t0)
    if pattern_err is not None:
        return pattern_err
    if cert_triples is None:
        return _vr("schema_err", t0, "forbidden_pose_pattern parse returned None")

    # Per Gemini F5 round 2 review #A.2: forbidden_pose_pattern length must
    # match core_minimization.size_after. Without this cross-check, an attacker
    # could pad the pattern (e.g. claim size_after=1 but ship 100 literals)
    # and the audit trail would silently disagree with the actual cut.
    cert_size_after = int(cert_dict["core_minimization"]["size_after"])
    if len(cert_triples) != cert_size_after:
        return _vr(
            "schema_err",
            t0,
            f"forbidden_pose_pattern length {len(cert_triples)} != core_minimization.size_after {cert_size_after}",
        )

    literal_err = _validate_cert_literals_match(cut, cert_triples, t0)
    if literal_err is not None:
        return literal_err

    reverify_err = _reverify_sub_problem_oracle(
        adapter,
        cert_triples,
        state,
        t0,
    )
    if reverify_err is not None:
        return reverify_err

    return _vr("ok", t0)


def watcher_keys_pattern_nogood(cut: Cut) -> Dict[str, List[Any]]:
    """Return watcher keys for CutStore.add_cut (cut_lifecycle_v2 §7 table).

    F5 walls by group + pose (per spec — slot/cell anonymity).
    by_ghost is auto-added by store from cut.scope.ghost_rect_id.
    """
    if cut.literals is None:
        return {"group_keys": [], "pose_keys": []}
    group_keys = sorted({lit.slot_ref.group_id for lit in cut.literals})
    pose_keys = sorted({(lit.slot_ref.group_id, lit.pose_id) for lit in cut.literals})
    return {"group_keys": group_keys, "pose_keys": pose_keys}

