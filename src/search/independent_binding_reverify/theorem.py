"""Closed-form binding theorem and deterministic explicit witness builder."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .protocol import CERTIFICATE_SCHEMA, canonical_digest
from .semantics import BindingSemanticModel, FixedDomain, GenericSlot, PortCell


OUTCOME_INFEASIBLE = "ARITHMETIC_INFEASIBLE"
OUTCOME_FEASIBLE = "CONSTRUCTIVE_FEASIBLE"
_UNUSED = "__unused__"


def build_binding_certificate(model: BindingSemanticModel) -> Dict[str, Any]:
    """Build a small negative certificate or a concrete positive assignment.

    This is the only theorem-builder entrypoint.  ``certificate.py`` validates
    the result independently and never calls this function.
    """

    deficits = _deficits(model)
    certificate: Dict[str, Any] = {
        "schema": CERTIFICATE_SCHEMA,
        "model_identity": {
            "artifact_hashes": dict(model.artifact_hashes),
            "solution_digest": model.solution_digest,
            "selected_pose_snapshot_digest": model.selected_pose_snapshot_digest,
        },
        "capacity_accounts": {
            "generic_input": _capacity_account(
                model.required_generic_inputs,
                len(model.generic_input_slots),
            ),
            "generic_output": _capacity_account(
                model.required_generic_outputs,
                len(model.generic_output_slots),
            ),
        },
        "fixed_domain_count": len(model.fixed_domains),
        "source_rejected_selection_count": model.source_rejected_selection_count,
        "proof_rule": (
            "fixed-operation sides are independent injections; generic input and "
            "output are disjoint exact-cardinality assignments with one "
            "commodity-or-unused value per physical slot"
        ),
        "solver_dependency": "none",
        "runtime_relaxations": list(model.runtime_relaxations),
    }
    if deficits:
        certificate.update(
            {
                "outcome": OUTCOME_INFEASIBLE,
                "deficits": deficits,
                "witness": None,
            }
        )
    else:
        witness = {
            "fixed_assignments": [
                _fixed_domain_assignment(domain) for domain in model.fixed_domains
            ],
            "generic_input_assignments": _generic_assignments(
                model.generic_input_slots,
                model.required_generic_inputs,
            ),
            "generic_output_assignments": _generic_assignments(
                model.generic_output_slots,
                model.required_generic_outputs,
            ),
        }
        certificate.update(
            {
                "outcome": OUTCOME_FEASIBLE,
                "deficits": [],
                "witness": witness,
                "witness_digest": canonical_digest(witness),
            }
        )
    certificate["certificate_digest"] = canonical_digest(
        {key: value for key, value in certificate.items() if key != "certificate_digest"}
    )
    return certificate


def _capacity_account(
    requirements: Mapping[str, int],
    physical_slots: int,
) -> Dict[str, Any]:
    required_positive_slots = sum(count for count in requirements.values() if count > 0)
    return {
        "requirements": dict(requirements),
        "required_positive_slots": required_positive_slots,
        "physical_slots": int(physical_slots),
        "slack": int(physical_slots) - required_positive_slots,
    }


def _deficits(model: BindingSemanticModel) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for side, requirements, slots in (
        ("generic_input", model.required_generic_inputs, model.generic_input_slots),
        ("generic_output", model.required_generic_outputs, model.generic_output_slots),
    ):
        required = sum(count for count in requirements.values() if count > 0)
        physical = len(slots)
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


def _fixed_domain_assignment(domain: FixedDomain) -> Dict[str, Any]:
    return {
        "instance_id": domain.instance_id,
        "operation_type": domain.operation_type,
        "input": _inject_commodities(domain.input_ports, domain.input_slot_counts),
        "output": _inject_commodities(domain.output_ports, domain.output_slot_counts),
    }


def _inject_commodities(
    ports: Iterable[PortCell],
    requirements: Mapping[str, int],
) -> list[Dict[str, Any]]:
    available = list(ports)
    assignments: list[Dict[str, Any]] = []
    cursor = 0
    for commodity, count in sorted(requirements.items()):
        for _ in range(max(0, int(count))):
            port = available[cursor]
            cursor += 1
            assignments.append({"commodity": commodity, **port.to_dict()})
    return assignments


def _generic_assignments(
    slots: Iterable[GenericSlot],
    requirements: Mapping[str, int],
) -> list[Dict[str, Any]]:
    ordered_slots = list(slots)
    assigned_commodities: list[str] = []
    for commodity, count in sorted(requirements.items()):
        assigned_commodities.extend([commodity] * max(0, int(count)))
    assigned_commodities.extend(
        [_UNUSED] * (len(ordered_slots) - len(assigned_commodities))
    )
    return [
        {**slot.to_dict(), "commodity": commodity}
        for slot, commodity in zip(ordered_slots, assigned_commodities, strict=True)
    ]
