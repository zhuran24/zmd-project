"""Independent checker for binding arithmetic certificates and witnesses.

The checker deliberately does not import or call ``theorem.build_binding_certificate``.
It validates the certificate against the reconstructed semantic model directly.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Dict

from .protocol import CERTIFICATE_SCHEMA, canonical_digest
from .semantics import BindingSemanticModel, FixedDomain, GenericSlot, PortCell


OUTCOME_INFEASIBLE = "ARITHMETIC_INFEASIBLE"
OUTCOME_FEASIBLE = "CONSTRUCTIVE_FEASIBLE"
_UNUSED = "__unused__"


@dataclass(frozen=True)
class CertificateCheck:
    ok: bool
    outcome: str
    failures: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "outcome": str(self.outcome),
            "failures": list(self.failures),
        }


def verify_binding_certificate(
    model: BindingSemanticModel,
    raw_certificate: Mapping[str, Any],
) -> CertificateCheck:
    failures: list[str] = []
    certificate = dict(raw_certificate)
    expected_keys = {
        "schema",
        "model_identity",
        "capacity_accounts",
        "fixed_domain_count",
        "source_rejected_selection_count",
        "proof_rule",
        "solver_dependency",
        "runtime_relaxations",
        "outcome",
        "deficits",
        "witness",
        "certificate_digest",
    }
    outcome = str(certificate.get("outcome", ""))
    if outcome == OUTCOME_FEASIBLE:
        expected_keys.add("witness_digest")
    if set(certificate) != expected_keys:
        failures.append(
            f"certificate keys mismatch: missing={sorted(expected_keys - set(certificate))};"
            f"extra={sorted(set(certificate) - expected_keys)}"
        )
    if certificate.get("schema") != CERTIFICATE_SCHEMA:
        failures.append(f"unexpected certificate schema: {certificate.get('schema')!r}")
    if certificate.get("solver_dependency") != "none":
        failures.append("certificate solver_dependency must be 'none'")
    expected_runtime_relaxations = (
        ["routing_context_domain_filter_omitted_monotone_superset"]
        if model.routing_context_relaxation_active
        else []
    )
    if not _canonical_equal(
        certificate.get("runtime_relaxations"),
        expected_runtime_relaxations,
    ):
        failures.append(
            "runtime_relaxations do not match the observed production relaxation"
        )
    fixed_domain_count = certificate.get("fixed_domain_count")
    if (
        isinstance(fixed_domain_count, bool)
        or not isinstance(fixed_domain_count, int)
        or fixed_domain_count != len(model.fixed_domains)
    ):
        failures.append("fixed_domain_count does not match reconstructed model")
    rejected_count = certificate.get("source_rejected_selection_count")
    if (
        isinstance(rejected_count, bool)
        or not isinstance(rejected_count, int)
        or rejected_count != model.source_rejected_selection_count
    ):
        failures.append("source_rejected_selection_count does not match request contract")

    raw_runtime_relaxations = certificate.get("runtime_relaxations")
    if (
        isinstance(raw_runtime_relaxations, (str, bytes, bytearray))
        or not isinstance(raw_runtime_relaxations, Sequence)
    ):
        failures.append("runtime_relaxations must be an array")
    else:
        normalized_runtime_relaxations: list[str] = []
        for index, raw_relaxation in enumerate(raw_runtime_relaxations):
            if not isinstance(raw_relaxation, str) or not raw_relaxation:
                failures.append(
                    f"runtime_relaxations[{index}] must be a non-empty string"
                )
                continue
            normalized_runtime_relaxations.append(raw_relaxation)
        if len(set(normalized_runtime_relaxations)) != len(
            normalized_runtime_relaxations
        ):
            failures.append("runtime_relaxations contains duplicates")
        if tuple(normalized_runtime_relaxations) != tuple(model.runtime_relaxations):
            failures.append(
                "runtime_relaxations do not match reconstructed production relaxation state"
            )


    identity = certificate.get("model_identity")
    if not isinstance(identity, Mapping):
        failures.append("model_identity must be an object")
    else:
        if dict(identity.get("artifact_hashes", {})) != dict(model.artifact_hashes):
            failures.append("artifact hashes do not match reconstructed authority")
        if identity.get("solution_digest") != model.solution_digest:
            failures.append("solution_digest mismatch")
        if identity.get("selected_pose_snapshot_digest") != model.selected_pose_snapshot_digest:
            failures.append("selected_pose_snapshot_digest mismatch")

    expected_accounts = {
        "generic_input": _capacity_account(
            model.required_generic_inputs,
            len(model.generic_input_slots),
        ),
        "generic_output": _capacity_account(
            model.required_generic_outputs,
            len(model.generic_output_slots),
        ),
    }
    if not _canonical_equal(certificate.get("capacity_accounts"), expected_accounts):
        failures.append("capacity_accounts do not match reconstructed model")

    expected_deficits = _expected_deficits(model)
    if outcome == OUTCOME_INFEASIBLE:
        if not _canonical_equal(certificate.get("deficits"), expected_deficits):
            failures.append("negative deficits do not match reconstructed capacities")
        if not expected_deficits:
            failures.append("negative certificate has no actual deficit")
        if certificate.get("witness") is not None:
            failures.append("negative certificate must not carry a witness")
    elif outcome == OUTCOME_FEASIBLE:
        if expected_deficits:
            failures.append("positive certificate issued despite an actual deficit")
        if not _canonical_equal(certificate.get("deficits"), []):
            failures.append("positive certificate must carry an empty deficit list")
        witness = certificate.get("witness")
        if not isinstance(witness, Mapping):
            failures.append("positive certificate witness must be an object")
        else:
            _verify_positive_witness(model, witness, failures)
            if certificate.get("witness_digest") != canonical_digest(witness):
                failures.append("witness_digest mismatch")
    else:
        failures.append(f"unsupported certificate outcome: {outcome!r}")

    declared_digest = certificate.get("certificate_digest")
    actual_digest = canonical_digest(
        {key: value for key, value in certificate.items() if key != "certificate_digest"}
    )
    if declared_digest != actual_digest:
        failures.append("certificate_digest mismatch")
    return CertificateCheck(
        ok=not failures,
        outcome=outcome,
        failures=tuple(failures),
    )


def _verify_positive_witness(
    model: BindingSemanticModel,
    witness: Mapping[str, Any],
    failures: list[str],
) -> None:
    expected_keys = {
        "fixed_assignments",
        "generic_input_assignments",
        "generic_output_assignments",
    }
    if set(witness) != expected_keys:
        failures.append(
            f"witness keys mismatch: missing={sorted(expected_keys - set(witness))};"
            f"extra={sorted(set(witness) - expected_keys)}"
        )
        return
    _verify_fixed_assignments(
        model.fixed_domains,
        witness.get("fixed_assignments"),
        failures,
    )
    _verify_generic_assignments(
        model.generic_input_slots,
        model.required_generic_inputs,
        witness.get("generic_input_assignments"),
        "generic_input",
        failures,
    )
    _verify_generic_assignments(
        model.generic_output_slots,
        model.required_generic_outputs,
        witness.get("generic_output_assignments"),
        "generic_output",
        failures,
    )


def _verify_fixed_assignments(
    domains: Sequence[FixedDomain],
    raw_assignments: Any,
    failures: list[str],
) -> None:
    if isinstance(raw_assignments, (str, bytes, bytearray)) or not isinstance(
        raw_assignments,
        Sequence,
    ):
        failures.append("fixed_assignments must be an array")
        return
    expected = {domain.instance_id: domain for domain in domains}
    actual: Dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(raw_assignments):
        if not isinstance(raw, Mapping):
            failures.append(f"fixed_assignments[{index}] must be an object")
            continue
        instance_id = str(raw.get("instance_id", ""))
        if not instance_id or instance_id in actual:
            failures.append(f"fixed assignment has invalid/duplicate instance_id {instance_id!r}")
            continue
        actual[instance_id] = raw
    if set(actual) != set(expected):
        failures.append(
            f"fixed assignment set mismatch: missing={sorted(set(expected)-set(actual))};"
            f"extra={sorted(set(actual)-set(expected))}"
        )
    for instance_id in sorted(set(actual) & set(expected)):
        assignment = actual[instance_id]
        domain = expected[instance_id]
        if assignment.get("operation_type") != domain.operation_type:
            failures.append(f"{instance_id}: operation_type mismatch")
        _verify_fixed_side(
            instance_id,
            "input",
            domain.input_ports,
            domain.input_slot_counts,
            assignment.get("input"),
            failures,
        )
        _verify_fixed_side(
            instance_id,
            "output",
            domain.output_ports,
            domain.output_slot_counts,
            assignment.get("output"),
            failures,
        )


def _verify_fixed_side(
    instance_id: str,
    side: str,
    allowed_ports: Sequence[PortCell],
    requirements: Mapping[str, int],
    raw_assignments: Any,
    failures: list[str],
) -> None:
    if isinstance(raw_assignments, (str, bytes, bytearray)) or not isinstance(
        raw_assignments,
        Sequence,
    ):
        failures.append(f"{instance_id}.{side} must be an array")
        return
    allowed = {(port.x, port.y, port.direction) for port in allowed_ports}
    used: set[tuple[int, int, str]] = set()
    counts: Counter[str] = Counter()
    for index, raw in enumerate(raw_assignments):
        if not isinstance(raw, Mapping):
            failures.append(f"{instance_id}.{side}[{index}] must be an object")
            continue
        try:
            x = _strict_witness_int(raw["x"])
            y = _strict_witness_int(raw["y"])
            direction = _strict_witness_string(raw["dir"])
            commodity = _strict_witness_string(raw["commodity"])
            key = (x, y, direction)
        except (KeyError, TypeError, ValueError):
            failures.append(f"{instance_id}.{side}[{index}] is malformed")
            continue
        if key not in allowed:
            failures.append(f"{instance_id}.{side}[{index}] uses a port outside the pose")
        if key in used:
            failures.append(f"{instance_id}.{side}[{index}] reuses a physical port")
        used.add(key)
        counts[commodity] += 1
    expected_counts = Counter(
        {commodity: count for commodity, count in requirements.items() if count > 0}
    )
    if counts != expected_counts:
        failures.append(
            f"{instance_id}.{side} commodity counts {dict(counts)} != {dict(expected_counts)}"
        )


def _verify_generic_assignments(
    slots: Sequence[GenericSlot],
    requirements: Mapping[str, int],
    raw_assignments: Any,
    side: str,
    failures: list[str],
) -> None:
    if isinstance(raw_assignments, (str, bytes, bytearray)) or not isinstance(
        raw_assignments,
        Sequence,
    ):
        failures.append(f"{side}_assignments must be an array")
        return
    expected = {slot.slot_id: slot for slot in slots}
    actual: Dict[str, Mapping[str, Any]] = {}
    counts: Counter[str] = Counter()
    for index, raw in enumerate(raw_assignments):
        if not isinstance(raw, Mapping):
            failures.append(f"{side}_assignments[{index}] must be an object")
            continue
        raw_slot_id = raw.get("slot_id")
        slot_id = raw_slot_id if isinstance(raw_slot_id, str) else ""
        if not slot_id or slot_id in actual:
            failures.append(f"{side} assignment has invalid/duplicate slot_id {slot_id!r}")
            continue
        actual[slot_id] = raw
        raw_commodity = raw.get("commodity")
        commodity = raw_commodity if isinstance(raw_commodity, str) else ""
        if commodity != _UNUSED:
            counts[commodity] += 1
    if set(actual) != set(expected):
        failures.append(
            f"{side} slot set mismatch: missing={sorted(set(expected)-set(actual))};"
            f"extra={sorted(set(actual)-set(expected))}"
        )
    allowed_commodities = set(requirements) | {_UNUSED}
    for slot_id in sorted(set(actual) & set(expected)):
        assignment = actual[slot_id]
        slot = expected[slot_id]
        expected_metadata = slot.to_dict()
        try:
            actual_metadata = {
                "side": _strict_witness_string(assignment.get("side")),
                "slot_id": _strict_witness_string(assignment.get("slot_id")),
                "instance_id": _strict_witness_string(assignment.get("instance_id")),
                "operation_type": _strict_witness_string(
                    assignment.get("operation_type")
                ),
                "local_index": _strict_witness_int(assignment.get("local_index")),
                "x": _strict_witness_int(assignment.get("x")),
                "y": _strict_witness_int(assignment.get("y")),
                "dir": _strict_witness_string(assignment.get("dir")),
            }
        except (TypeError, ValueError):
            actual_metadata = {}
        if not _canonical_equal(actual_metadata, expected_metadata):
            failures.append(f"{side} slot {slot_id} metadata mismatch")
        raw_commodity = assignment.get("commodity")
        commodity = raw_commodity if isinstance(raw_commodity, str) else ""
        if commodity not in allowed_commodities:
            failures.append(f"{side} slot {slot_id} has unsupported commodity {commodity!r}")
    expected_counts = Counter(
        {commodity: count for commodity, count in requirements.items() if count > 0}
    )
    if counts != expected_counts:
        failures.append(f"{side} commodity counts {dict(counts)} != {dict(expected_counts)}")


def _canonical_equal(left: Any, right: Any) -> bool:
    try:
        return canonical_digest(left) == canonical_digest(right)
    except (TypeError, ValueError):
        return False


def _strict_witness_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("witness integer field must be a strict int")
    return int(value)


def _strict_witness_string(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("witness string field must be non-empty")
    return value


def _capacity_account(
    requirements: Mapping[str, int],
    physical_slots: int,
) -> Dict[str, Any]:
    required = sum(count for count in requirements.values() if count > 0)
    return {
        "requirements": dict(requirements),
        "required_positive_slots": required,
        "physical_slots": int(physical_slots),
        "slack": int(physical_slots) - required,
    }


def _expected_deficits(model: BindingSemanticModel) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for side, requirements, physical in (
        ("generic_input", model.required_generic_inputs, len(model.generic_input_slots)),
        ("generic_output", model.required_generic_outputs, len(model.generic_output_slots)),
    ):
        required = sum(count for count in requirements.values() if count > 0)
        if required > physical:
            result.append(
                {
                    "side": side,
                    "required_positive_slots": required,
                    "physical_slots": physical,
                    "deficit": required - physical,
                }
            )
    return result
