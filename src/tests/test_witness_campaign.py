"""Focused tests for the sole witness build/acceptance path."""

from __future__ import annotations

from dataclasses import replace
import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


campaign = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.witness_campaign"
)
objective_audit = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.objective_audit"
)
witness_io = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.witness_io"
)


def test_current_witness_api_requires_explicit_geometry_result() -> None:
    signature = inspect.signature(campaign.build_current_witness)
    assert signature.parameters["geometry_result"].default is inspect.Parameter.empty


def _built() -> campaign.BuiltWitness:
    rectangle = objective_audit.EmptyRectangle(1, 63, 6, 7, 42, 6)
    audit = objective_audit.ObjectiveAudit(rectangle, rectangle, 3656)
    return campaign.BuiltWitness(
        witness={},
        objective=audit,
        route_component_count=1219,
        route_cell_count=1219,
        terminal_count=628,
        source_count=316,
        sink_count=312,
        pole_count=28,
        box_count=0,
    )


def _checker(*, objective: dict[str, int] | None = None) -> witness_io.CheckerProcessResult:
    if objective is None:
        objective = {"x": 1, "y": 63, "width": 6, "height": 7, "area": 42, "min_side": 6}
    return witness_io.CheckerProcessResult(
        classification="LAYOUT_FEASIBLE",
        exit_code=0,
        status="LAYOUT_FEASIBLE",
        report={
            "status": "LAYOUT_FEASIBLE",
            "categories": {
                "J": "strict_json",
                "S": "document_shape",
                "I": "instance_integrity",
                "F": "facility_geometry",
                "P": "port_binding",
                "PW": "power",
                "R": "routing",
                "O": "objective",
            },
            "errors": [],
            "recomputed_objective": objective,
        },
        stdout="",
        stderr="",
        checker_trusted=True,
        checker_sha256=witness_io.EXPECTED_CHECKER_SHA256,
        checker_source_path=str(witness_io.EXPECTED_CHECKER_PATH),
        checker_source_identity=(1, 2, 0o100444, 1, 123, 4, 5),
        checker_snapshot_size_bytes=123,
        checker_python_executable=str(Path(sys.executable).resolve()),
        checker_execution_mode=witness_io.PINNED_CHECKER_EXECUTION_MODE,
    )


def test_acceptance_requires_pinned_checker_and_exact_objective_agreement() -> None:
    accepted = campaign.accept_independent_checker(_built(), _checker())

    assert accepted == {
        "status": "INDEPENDENT_ACCEPTANCE_OK",
        "checker_sha256": witness_io.EXPECTED_CHECKER_SHA256,
        "checker_status": "LAYOUT_FEASIBLE",
        "recomputed_objective": {
            "x": 1,
            "y": 63,
            "width": 6,
            "height": 7,
            "area": 42,
            "min_side": 6,
        },
        "claim_boundary": "feasible_layout_lower_bound_only",
    }

    with pytest.raises(campaign.WitnessCampaignError) as exc_info:
        campaign.accept_independent_checker(
            _built(),
            replace(_checker(), checker_trusted=False),
        )
    assert exc_info.value.code == "INDEPENDENT_CHECKER_REJECTED"

    changed = {"x": 1, "y": 63, "width": 6, "height": 8, "area": 48, "min_side": 6}
    with pytest.raises(campaign.WitnessCampaignError) as exc_info:
        campaign.accept_independent_checker(_built(), _checker(objective=changed))
    assert exc_info.value.code == "OBJECTIVE_AUDIT_DISAGREEMENT"


def test_current_core_final_input_policy_is_south_only() -> None:
    bundle = campaign.strict_contract.load_input_bundle()
    instance = bundle.strict_instance.value
    required = [
        {
            "instance_id": "protocol_core_001",
            "template": "protocol_core",
            "mode": "inputs_north_south",
            "anchor": {"x": 3, "y": 44},
        }
    ]

    cells = campaign._core_south_input_cells(instance, required)

    assert cells == frozenset((x, 43) for x in range(4, 11))
    assert not any(y == 53 for _x, y in cells)


def test_diagnostics_state_lower_bound_claim_only() -> None:
    diagnostics = _built().diagnostics()

    assert diagnostics["claim_boundary"] == "feasible_layout_lower_bound_only"
    assert diagnostics["terminal_count"] == 628
    assert diagnostics["pole_count"] >= 9


def _router_result(bundle: object) -> dict[str, object]:
    instance = bundle.strict_instance.value
    required = [
        {
            "instance_id": record["id"],
            "template": record["template"],
            "mode": "mode",
            "anchor": {"x": 0, "y": 0},
            "port_bindings": {},
        }
        for record in instance["required_instances"]
    ]
    optional = [
        {
            "instance_id": f"research_power_pole_{index:03d}",
            "template": "power_pole",
            "mode": "fixed",
            "anchor": {"x": index, "y": 0},
            "port_bindings": {},
        }
        for index in range(9)
    ]
    port_specs = [{} for _ in range(628)]
    routes = [
        {
            "cell": {"x": 69, "y": 69},
            "kind": "straight",
            "inputs": ["W"],
            "outputs": ["E"],
            "commodities": list(instance["commodities"]),
        }
    ]
    return {
        "schema_version": "fixed_geometry_router_result.v1",
        "status": "FEASIBLE",
        "classification": "STRICT_ROUTES_INDEPENDENTLY_REACHABLE",
        "claim_boundary": "research_witness_candidate_only",
        "required_placements": required,
        "optional_placements": optional,
        "port_specs": port_specs,
        "route_components": routes,
        "route_components_digest": campaign.fixed_geometry_router.canonical_digest(routes),
        "telemetry": {
            "input_snapshot": {
                "geometry_sha256": "a" * 64,
                "post_solve_revalidated": True,
                "dependency_hashes": dict(sorted(bundle.hashes.items())),
            },
            "cgroup": {"oom_attribution": "NO_CGROUP_OOM"},
            "port_specs_digest": campaign.fixed_geometry_router.canonical_digest(port_specs),
        },
    }


def test_routed_result_repeats_structural_reachability_and_objective_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = campaign.strict_contract.load_input_bundle()
    result = _router_result(bundle)
    terminals = [
        *(SimpleNamespace(kind="output") for _ in range(316)),
        *(SimpleNamespace(kind="input") for _ in range(312)),
    ]
    rectangle = objective_audit.EmptyRectangle(1, 63, 6, 7, 42, 6)
    audit = objective_audit.ObjectiveAudit(rectangle, rectangle, 3656)
    calls: list[str] = []
    monkeypatch.setattr(campaign, "_instance_payload", lambda _bundle: b"{}")
    monkeypatch.setattr(campaign.network_router, "terminals_from_witness", lambda *_args: terminals)
    monkeypatch.setattr(
        campaign.network_router,
        "assert_terminal_route_reachability",
        lambda *_args: calls.append("reachability"),
    )
    monkeypatch.setattr(campaign.network_router, "occupied_body_cells", lambda *_args: frozenset())
    monkeypatch.setattr(
        campaign.witness_io,
        "derive_production_port_specs",
        lambda *_args, **_kwargs: result["port_specs"],
    )
    monkeypatch.setattr(campaign.objective_audit, "maximum_empty_rectangle", lambda *_args: rectangle)
    monkeypatch.setattr(campaign.objective_audit, "audit_witness_objective", lambda *_args: audit)
    monkeypatch.setattr(campaign.witness_io, "assemble_strict_witness", lambda **_kwargs: {"layout": True})

    built = campaign.build_routed_witness(result, bundle=bundle)

    assert calls == ["reachability"]
    assert built.witness == {"layout": True}
    assert built.terminal_count == 628
    assert built.pole_count == 9
    assert built.objective.score == (42, 6)


def test_routed_result_rejects_missing_post_solve_revalidation() -> None:
    bundle = campaign.strict_contract.load_input_bundle()
    result = _router_result(bundle)
    result["telemetry"]["input_snapshot"]["post_solve_revalidated"] = False

    with pytest.raises(campaign.WitnessCampaignError) as exc_info:
        campaign.build_routed_witness(result, bundle=bundle)

    assert exc_info.value.code == "ROUTER_INPUT_NOT_REVALIDATED"


@pytest.mark.parametrize("mutation, expected_code", [
    (lambda result: result.pop("route_components_digest"), "ROUTER_RESULT_FIELDS"),
    (lambda result: result.__setitem__("unexpected", True), "ROUTER_RESULT_FIELDS"),
    (
        lambda result: result["route_components"][0]["cell"].__setitem__("x", 68),
        "ROUTER_ROUTE_DIGEST_MISMATCH",
    ),
    (lambda result: result.__setitem__("claim_boundary", "other"), "ROUTER_CLAIM_BOUNDARY"),
    (
        lambda result: result["telemetry"]["input_snapshot"].__setitem__("geometry_sha256", "bad"),
        "ROUTER_GEOMETRY_HASH",
    ),
    (
        lambda result: result["telemetry"]["cgroup"].__setitem__("oom_attribution", "CGROUP_OOM_EVENT"),
        "ROUTER_CGROUP_GATE",
    ),
])
def test_routed_result_requires_exact_fields_digests_and_production_gates(
    mutation: object,
    expected_code: str,
) -> None:
    bundle = campaign.strict_contract.load_input_bundle()
    result = _router_result(bundle)
    mutation(result)

    with pytest.raises(campaign.WitnessCampaignError) as exc_info:
        campaign.build_routed_witness(result, bundle=bundle)
    assert exc_info.value.code == expected_code


def test_routed_result_recomputes_port_specs_from_bound_placements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = campaign.strict_contract.load_input_bundle()
    result = _router_result(bundle)
    monkeypatch.setattr(
        campaign.witness_io,
        "derive_production_port_specs",
        lambda *_args, **_kwargs: [{"different": True} for _ in range(628)],
    )

    with pytest.raises(campaign.WitnessCampaignError) as exc_info:
        campaign.build_routed_witness(result, bundle=bundle)
    assert exc_info.value.code == "ROUTER_PORT_SPECS_MISMATCH"
