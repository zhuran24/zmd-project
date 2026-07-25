"""Focused tests for strict witness binding, I/O, and checker isolation."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any

import pytest


witness_io = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.witness_io"
)

WitnessIOError = witness_io.WitnessIOError
assemble_strict_witness = witness_io.assemble_strict_witness
backmap_port_specs_to_bindings = witness_io.backmap_port_specs_to_bindings
bind_placements = witness_io.bind_placements
bind_placements_from_port_specs = witness_io.bind_placements_from_port_specs
canonical_json_bytes = witness_io.canonical_json_bytes
complete_port_bindings = witness_io.complete_port_bindings
derive_production_port_specs = witness_io.derive_production_port_specs
run_independent_checker = witness_io.run_independent_checker

_CATEGORIES = {
    "J": "strict_json",
    "S": "document_shape",
    "I": "instance_integrity",
    "F": "facility_geometry",
    "P": "port_binding",
    "PW": "power",
    "R": "routing",
    "O": "objective",
}


@pytest.fixture
def strict_instance() -> dict[str, Any]:
    return {
        "commodities": ["final", "ore", "plate"],
        "facility_templates": {
            "machine": {
                "modes": [
                    {
                        "id": "west_to_east",
                        "body": {"width": 2, "height": 2},
                        "ports": [
                            {
                                "id": "input_W_0",
                                "kind": "input",
                                "direction": "W",
                                "body_cell": {"x": 0, "y": 0},
                            },
                            {
                                "id": "input_W_1",
                                "kind": "input",
                                "direction": "W",
                                "body_cell": {"x": 0, "y": 1},
                            },
                            {
                                "id": "output_E_0",
                                "kind": "output",
                                "direction": "E",
                                "body_cell": {"x": 1, "y": 0},
                            },
                            {
                                "id": "output_E_1",
                                "kind": "output",
                                "direction": "E",
                                "body_cell": {"x": 1, "y": 1},
                            },
                        ],
                    }
                ]
            },
            "boundary_storage_port": {
                "modes": [
                    {
                        "id": "left_boundary",
                        "body": {"width": 1, "height": 1},
                        "ports": [
                            {
                                "id": "output_E_0",
                                "kind": "output",
                                "direction": "E",
                                "body_cell": {"x": 0, "y": 0},
                            }
                        ],
                    }
                ]
            },
            "protocol_core": {
                "modes": [
                    {
                        "id": "fixed",
                        "body": {"width": 1, "height": 1},
                        "ports": [
                            {
                                "id": "input_N_0",
                                "kind": "input",
                                "direction": "N",
                                "body_cell": {"x": 0, "y": 0},
                            },
                            {
                                "id": "input_W_0",
                                "kind": "input",
                                "direction": "W",
                                "body_cell": {"x": 0, "y": 0},
                            },
                            {
                                "id": "output_E_0",
                                "kind": "output",
                                "direction": "E",
                                "body_cell": {"x": 0, "y": 0},
                            },
                        ],
                    }
                ]
            },
            "storage_box": {
                "modes": [
                    {
                        "id": "fixed",
                        "body": {"width": 1, "height": 1},
                        "ports": [
                            {
                                "id": "input_W_0",
                                "kind": "input",
                                "direction": "W",
                                "body_cell": {"x": 0, "y": 0},
                            },
                            {
                                "id": "output_E_0",
                                "kind": "output",
                                "direction": "E",
                                "body_cell": {"x": 0, "y": 0},
                            },
                        ],
                    }
                ]
            },
            "power_pole": {
                "modes": [{"id": "fixed", "body": {"width": 1, "height": 1}, "ports": []}]
            },
        },
        "operation_groups": [
            {
                "id": "smelt",
                "template": "machine",
                "count": 2,
                "instance_ids": ["machine_001", "machine_002"],
                "port_needs": {"inputs": {"ore": 1}, "outputs": {"plate": 1}},
            }
        ],
        "required_instances": [
            {"id": "machine_001", "template": "machine", "operation": "smelt"},
            {"id": "machine_002", "template": "machine", "operation": "smelt"},
            {"id": "boundary_001", "template": "boundary_storage_port", "operation": "generic_io"},
            {"id": "core_001", "template": "protocol_core", "operation": "generic_io"},
        ],
        "generic_requirements": {
            "raw_output_providers": ["boundary_storage_port", "protocol_core"],
            "final_input_providers": ["protocol_core", "storage_box"],
            "raw_outputs": {"ore": 2},
            "final_inputs": {"final": 1},
        },
        "repeatable_auxiliaries": ["power_pole", "storage_box"],
    }


@pytest.fixture
def geometry() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    required = [
        {
            "instance_id": "machine_001",
            "template": "machine",
            "mode": "west_to_east",
            "anchor": {"x": 10, "y": 10},
        },
        {
            "instance_id": "machine_002",
            "template": "machine",
            "mode": "west_to_east",
            "anchor": {"x": 20, "y": 20},
        },
        {
            "instance_id": "boundary_001",
            "template": "boundary_storage_port",
            "mode": "left_boundary",
            "anchor": {"x": 0, "y": 30},
        },
        {
            "instance_id": "core_001",
            "template": "protocol_core",
            "mode": "fixed",
            "anchor": {"x": 40, "y": 40},
        },
    ]
    optional = [
        {
            "instance_id": "box_001",
            "template": "storage_box",
            "mode": "fixed",
            "anchor": {"x": 50, "y": 50},
        }
    ]
    return required, optional


def _explicit_bindings() -> dict[str, dict[str, str]]:
    return {
        "machine_001": {"input_W_0": "ore", "output_E_0": "plate"},
        "machine_002": {"input_W_0": "ore", "output_E_0": "plate"},
        "boundary_001": {"output_E_0": "ore"},
        "core_001": {"output_E_0": "ore"},
        "box_001": {"input_W_0": "final"},
    }


def test_complete_port_bindings_emits_full_null_map(strict_instance: dict[str, Any]) -> None:
    placement = {
        "instance_id": "machine_001",
        "template": "machine",
        "mode": "west_to_east",
        "anchor": {"x": 10, "y": 10},
    }
    completed = complete_port_bindings(
        strict_instance,
        placement,
        {"input_W_0": "ore", "output_E_1": "plate"},
    )

    assert completed["port_bindings"] == {
        "input_W_0": "ore",
        "input_W_1": None,
        "output_E_0": None,
        "output_E_1": "plate",
    }

    with pytest.raises(WitnessIOError) as exc_info:
        complete_port_bindings(strict_instance, placement, {"ghost": "ore"})
    assert exc_info.value.code == "UNKNOWN_PORT_ID"


def test_explicit_binding_checks_every_instance_and_generic_total(
    strict_instance: dict[str, Any],
    geometry: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    required, optional = geometry
    bound = bind_placements(
        strict_instance,
        required_placements=required,
        optional_placements=optional,
        selected_port_bindings=_explicit_bindings(),
    )

    by_id = {
        placement["instance_id"]: placement
        for placement in (*bound["required_placements"], *bound["optional_placements"])
    }
    assert [placement["instance_id"] for placement in bound["required_placements"]] == sorted(
        placement["instance_id"] for placement in bound["required_placements"]
    )
    assert [placement["instance_id"] for placement in bound["optional_placements"]] == sorted(
        placement["instance_id"] for placement in bound["optional_placements"]
    )
    assert sum(value is not None for value in by_id["machine_001"]["port_bindings"].values()) == 2
    assert by_id["machine_001"]["port_bindings"]["input_W_1"] is None
    assert by_id["box_001"]["port_bindings"] == {"input_W_0": "final", "output_E_0": None}

    bad_manufacturing = _explicit_bindings()
    del bad_manufacturing["machine_002"]["output_E_0"]
    with pytest.raises(WitnessIOError) as exc_info:
        bind_placements(
            strict_instance,
            required_placements=required,
            optional_placements=optional,
            selected_port_bindings=bad_manufacturing,
        )
    assert exc_info.value.code == "MANUFACTURING_BINDING_MISMATCH"

    bad_generic = _explicit_bindings()
    del bad_generic["boundary_001"]["output_E_0"]
    with pytest.raises(WitnessIOError) as exc_info:
        bind_placements(
            strict_instance,
            required_placements=required,
            optional_placements=optional,
            selected_port_bindings=bad_generic,
        )
    assert exc_info.value.code == "GENERIC_BINDING_MISMATCH"


def test_auto_binding_respects_scaffold_and_requested_core_final_front(
    strict_instance: dict[str, Any],
    geometry: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    required, _optional = geometry
    allowed = {
        (9, 10),
        (12, 10),
        (19, 20),
        (22, 20),
        (1, 30),
        (41, 40),
        (39, 40),
    }
    bound = bind_placements(
        strict_instance,
        required_placements=required,
        allowed_access_cells=allowed,
        core_final_input_access_cells={(39, 40)},
    )
    by_id = {placement["instance_id"]: placement for placement in bound["required_placements"]}

    assert by_id["machine_001"]["port_bindings"]["input_W_0"] == "ore"
    assert by_id["machine_001"]["port_bindings"]["input_W_1"] is None
    assert by_id["core_001"]["port_bindings"] == {
        "input_N_0": None,
        "input_W_0": "final",
        "output_E_0": "ore",
    }
    specs = derive_production_port_specs(
        strict_instance,
        required_placements=bound["required_placements"],
    )
    assert {(spec["x"], spec["y"]) for spec in specs}.issubset(allowed)

    with pytest.raises(WitnessIOError) as exc_info:
        bind_placements(
            strict_instance,
            required_placements=required,
            allowed_access_cells=allowed - {(41, 40)},
            core_final_input_access_cells={(39, 40)},
        )
    assert exc_info.value.code == "AUTO_BINDING_INFEASIBLE"


def test_real_strict_instance_recomputes_all_binding_sentinels() -> None:
    project_root = Path(__file__).resolve().parents[2]
    instance_path = (
        project_root
        / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    )
    instance = json.loads(instance_path.read_text(encoding="utf-8"))
    # Geometry coordinates are intentionally inert in this binding-only test;
    # the independent checker owns overlap/front feasibility.
    placements = [
        {
            "instance_id": required["id"],
            "template": required["template"],
            "mode": instance["facility_templates"][required["template"]]["modes"][0]["id"],
            "anchor": {"x": 10, "y": 10},
        }
        for required in instance["required_instances"]
    ]

    bound = bind_placements(instance, required_placements=placements)
    all_bindings = [
        commodity
        for placement in bound["required_placements"]
        for commodity in placement["port_bindings"].values()
    ]
    core = next(
        placement for placement in bound["required_placements"] if placement["template"] == "protocol_core"
    )

    assert len(bound["required_placements"]) == 266
    assert len(all_bindings) == 1804
    assert sum(commodity is not None for commodity in all_bindings) == 628
    assert sum(commodity is None for commodity in all_bindings) == 1176
    assert sum(
        commodity is not None
        for port_id, commodity in core["port_bindings"].items()
        if port_id.startswith("output_")
    ) == 6


def test_identity_port_specs_round_trip_without_second_offset(
    strict_instance: dict[str, Any],
    geometry: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    required, optional = geometry
    bound = bind_placements(
        strict_instance,
        required_placements=required,
        optional_placements=optional,
        selected_port_bindings=_explicit_bindings(),
    )
    specs = derive_production_port_specs(
        strict_instance,
        required_placements=bound["required_placements"],
        optional_placements=bound["optional_placements"],
    )

    machine_input = next(
        spec for spec in specs if spec["instance_id"] == "machine_001" and spec["type"] == "in"
    )
    assert machine_input == {
        "instance_id": "machine_001",
        "x": 9,
        "y": 10,
        "dir": "W",
        "type": "in",
        "commodity": "ore",
    }
    selected = backmap_port_specs_to_bindings(
        strict_instance,
        required_placements=required,
        optional_placements=optional,
        port_specs=specs,
    )
    assert selected == _explicit_bindings()
    rebound = bind_placements_from_port_specs(
        strict_instance,
        required_placements=required,
        optional_placements=optional,
        port_specs=specs,
    )
    assert rebound == bound


def test_backmap_rejects_double_offset_ambiguity_and_wrong_owner(
    strict_instance: dict[str, Any],
    geometry: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    required, optional = geometry
    bound = bind_placements(
        strict_instance,
        required_placements=required,
        optional_placements=optional,
        selected_port_bindings=_explicit_bindings(),
    )
    specs = derive_production_port_specs(
        strict_instance,
        required_placements=bound["required_placements"],
        optional_placements=bound["optional_placements"],
    )

    double_offset = deepcopy(specs)
    target = next(spec for spec in double_offset if spec["instance_id"] == "machine_001" and spec["type"] == "in")
    target["x"] -= 1
    with pytest.raises(WitnessIOError) as exc_info:
        backmap_port_specs_to_bindings(
            strict_instance,
            required_placements=required,
            optional_placements=optional,
            port_specs=double_offset,
        )
    assert exc_info.value.code == "PORT_SPEC_NO_MATCH"

    wrong_owner = deepcopy(specs)
    wrong_owner[0]["instance_id"] = "machine_001"
    with pytest.raises(WitnessIOError) as exc_info:
        backmap_port_specs_to_bindings(
            strict_instance,
            required_placements=required,
            optional_placements=optional,
            port_specs=wrong_owner,
        )
    assert exc_info.value.code == "PORT_SPEC_INSTANCE_MISMATCH"

    ambiguous_required = deepcopy(required)
    ambiguous_required[1]["anchor"] = deepcopy(ambiguous_required[0]["anchor"])
    one_spec = [
        {
            "instance_id": "machine_001",
            "x": 9,
            "y": 10,
            "dir": "W",
            "type": "in",
            "commodity": "ore",
        }
    ]
    with pytest.raises(WitnessIOError) as exc_info:
        backmap_port_specs_to_bindings(
            strict_instance,
            required_placements=ambiguous_required,
            optional_placements=optional,
            port_specs=one_spec,
        )
    assert exc_info.value.code == "AMBIGUOUS_PORT_ENDPOINT"


def test_assemble_and_encode_are_deterministic(
    strict_instance: dict[str, Any],
    geometry: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    required, optional = geometry
    bound = bind_placements(
        strict_instance,
        required_placements=required,
        optional_placements=optional,
        selected_port_bindings=_explicit_bindings(),
    )
    instance_payload = b'{"strict":"instance"}\n'
    routes = [
        {
            "cell": {"x": 7, "y": 2},
            "kind": "straight",
            "inputs": ["E"],
            "outputs": ["W"],
            "commodities": ["plate", "ore"],
        },
        {
            "cell": {"x": 3, "y": 1},
            "kind": "cross",
            "channels": [
                {"inputs": ["N"], "outputs": ["S"], "commodities": ["plate"]},
                {"inputs": ["W"], "outputs": ["E"], "commodities": ["ore"]},
            ],
        },
    ]
    objective = {"rectangle": {"x": 0, "y": 0, "width": 6, "height": 7}, "area": 42, "min_side": 6}
    first = assemble_strict_witness(
        instance_payload=instance_payload,
        required_placements=list(reversed(bound["required_placements"])),
        optional_placements=bound["optional_placements"],
        route_components=routes,
        claimed_objective=objective,
    )
    second = assemble_strict_witness(
        instance_payload=instance_payload,
        required_placements=bound["required_placements"],
        optional_placements=list(reversed(bound["optional_placements"])),
        route_components=list(reversed(routes)),
        claimed_objective=deepcopy(objective),
    )

    assert first == second
    assert first["instance_digest"] == "sha256:" + hashlib.sha256(instance_payload).hexdigest()
    assert [(route["cell"]["x"], route["cell"]["y"]) for route in first["route_components"]] == [(3, 1), (7, 2)]
    assert first["route_components"][0]["channels"][0]["inputs"] == ["W"]
    encoded = canonical_json_bytes(first)
    assert encoded.endswith(b"\n")
    assert encoded == canonical_json_bytes(second)
    assert json.loads(encoded) == first


def _fake_checker(
    tmp_path: Path,
    *,
    report: dict[str, Any] | None = None,
    exit_code: int = 0,
    body: str | None = None,
) -> Path:
    script = tmp_path / f"checker_{len(list(tmp_path.glob('checker_*.py')))}.py"
    if body is None:
        payload = json.dumps(report, sort_keys=True) + "\n" if report is not None else ""
        body = f"import sys\nsys.stdout.write({payload!r})\nraise SystemExit({exit_code})\n"
    script.write_text(body, encoding="utf-8")
    return script


def _dummy_checker_inputs(tmp_path: Path) -> tuple[Path, Path]:
    instance_path = tmp_path / "instance.json"
    witness_path = tmp_path / "witness.json"
    instance_path.write_text("{}\n", encoding="utf-8")
    witness_path.write_text("{}\n", encoding="utf-8")
    return instance_path, witness_path


def _checker_report(status: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": status,
        "categories": _CATEGORIES,
        "errors": (
            []
            if status == "LAYOUT_FEASIBLE"
            else [{"category": "S", "pointer": "/", "message": "rejected"}]
        ),
    }
    if status == "LAYOUT_FEASIBLE":
        report["recomputed_objective"] = {
            "x": 0,
            "y": 0,
            "width": 6,
            "height": 7,
            "area": 42,
            "min_side": 6,
        }
    return report


@pytest.mark.parametrize(
    ("status", "exit_code"),
    [("LAYOUT_FEASIBLE", 0), ("LAYOUT_INVALID", 1), ("CONTRACT_ERROR", 2), ("INTERNAL_ERROR", 3)],
)
def test_checker_accepts_only_matching_exit_status_pairs(
    tmp_path: Path,
    status: str,
    exit_code: int,
) -> None:
    instance_path, witness_path = _dummy_checker_inputs(tmp_path)
    checker = _fake_checker(tmp_path, report=_checker_report(status), exit_code=exit_code)
    result = run_independent_checker(
        instance_path,
        witness_path,
        checker_path=checker,
        python_executable=Path(sys.executable),
    )

    assert result.classification == status
    assert result.accepted is False
    assert result.checker_trusted is False


def test_checker_process_and_report_failures_are_classified(tmp_path: Path) -> None:
    instance_path, witness_path = _dummy_checker_inputs(tmp_path)

    mismatch = _fake_checker(
        tmp_path,
        report=_checker_report("LAYOUT_FEASIBLE"),
        exit_code=1,
    )
    assert run_independent_checker(
        instance_path,
        witness_path,
        checker_path=mismatch,
    ).classification == "RESULT_INTEGRITY_INVALID"

    bad_schema = _fake_checker(tmp_path, report={"status": "LAYOUT_FEASIBLE"}, exit_code=0)
    assert run_independent_checker(
        instance_path,
        witness_path,
        checker_path=bad_schema,
    ).classification == "RESULT_SCHEMA_INVALID"

    invalid_json = _fake_checker(tmp_path, body="print('not-json')\n")
    assert run_independent_checker(
        instance_path,
        witness_path,
        checker_path=invalid_json,
    ).classification == "RESULT_MISSING_OR_INVALID"

    unexpected_exit = _fake_checker(tmp_path, body="raise SystemExit(9)\n")
    assert run_independent_checker(
        instance_path,
        witness_path,
        checker_path=unexpected_exit,
    ).classification == "PROCESS_NONZERO_EXIT"

    timeout = _fake_checker(tmp_path, body="import time\ntime.sleep(1)\n")
    assert run_independent_checker(
        instance_path,
        witness_path,
        checker_path=timeout,
        timeout_seconds=0.01,
    ).classification == "CHECKER_TIMEOUT"

    terminated = _fake_checker(
        tmp_path,
        body="import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n",
    )
    signal_result = run_independent_checker(
        instance_path,
        witness_path,
        checker_path=terminated,
    )
    assert signal_result.classification == "CHECKER_SIGNAL"
    assert signal_result.signal_number == signal.SIGTERM

    start_error = run_independent_checker(
        instance_path,
        witness_path,
        checker_path=invalid_json,
        python_executable=tmp_path / "missing-python",
    )
    assert start_error.classification == "PROCESS_START_ERROR"


def test_existing_strict_checker_runs_as_an_independent_process(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    instance_path = (
        project_root
        / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    )
    witness_path = tmp_path / "malformed_witness.json"
    witness_path.write_text("{}\n", encoding="utf-8")

    result = run_independent_checker(instance_path, witness_path)

    assert result.classification == "CONTRACT_ERROR"
    assert result.exit_code == 2
    assert result.status == "CONTRACT_ERROR"
    assert result.accepted is False
    assert result.report is not None and result.report["errors"]
    assert result.checker_trusted is True
    assert result.checker_sha256 == witness_io.EXPECTED_CHECKER_SHA256
    assert result.checker_source_path == str(witness_io.EXPECTED_CHECKER_PATH)
    assert result.checker_source_identity is not None
    assert result.checker_source_identity[4] == result.checker_snapshot_size_bytes
    assert result.checker_python_executable == str(Path(sys.executable).resolve())
    assert result.checker_execution_mode == witness_io.PINNED_CHECKER_EXECUTION_MODE


def test_checker_executes_the_stable_snapshot_via_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance_path, witness_path = _dummy_checker_inputs(tmp_path)
    checker = _fake_checker(tmp_path, report=_checker_report("LAYOUT_FEASIBLE"))
    checker_payload = checker.read_bytes()
    real_run = subprocess.run
    observed: dict[str, Any] = {}

    def inspect_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        observed["command"] = command
        observed["input"] = kwargs.get("input")
        return real_run(command, **kwargs)

    monkeypatch.setattr(witness_io.subprocess, "run", inspect_run)
    result = run_independent_checker(instance_path, witness_path, checker_path=checker)

    assert result.classification == "LAYOUT_FEASIBLE"
    assert observed["input"] == checker_payload
    assert observed["command"][1:4] == ["-I", "-S", "-c"]
    assert str(checker) not in observed["command"]
    assert result.checker_sha256 == hashlib.sha256(checker_payload).hexdigest()
    assert result.checker_snapshot_size_bytes == len(checker_payload)
    assert result.checker_execution_mode == witness_io.PINNED_CHECKER_EXECUTION_MODE


def test_checker_source_drift_cannot_change_executed_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance_path, witness_path = _dummy_checker_inputs(tmp_path)
    checker = _fake_checker(tmp_path, report=_checker_report("LAYOUT_FEASIBLE"))
    original_payload = checker.read_bytes()
    real_run = subprocess.run

    def replace_source_before_exec(
        command: list[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[bytes]:
        assert kwargs["input"] == original_payload
        checker.write_text("raise SystemExit(9)\n", encoding="utf-8")
        return real_run(command, **kwargs)

    monkeypatch.setattr(witness_io.subprocess, "run", replace_source_before_exec)
    result = run_independent_checker(instance_path, witness_path, checker_path=checker)

    assert json.loads(result.stdout)["status"] == "LAYOUT_FEASIBLE"
    assert result.classification == "CHECKER_INTEGRITY_INVALID"
    assert result.checker_trusted is False
    assert result.checker_sha256 == hashlib.sha256(original_payload).hexdigest()
    assert "source identity changed" in result.stderr


def test_pinned_checker_ignores_inherited_pythonpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    instance_path = (
        project_root
        / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    )
    witness_path = tmp_path / "malformed_witness.json"
    witness_path.write_text("{}\n", encoding="utf-8")
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    marker = tmp_path / "pythonpath-imported"
    (attacker / "json.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('loaded')\n"
        "raise RuntimeError('inherited PYTHONPATH was used')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(attacker))

    result = run_independent_checker(instance_path, witness_path)

    assert result.classification == "CONTRACT_ERROR"
    assert result.exit_code == 2
    assert not marker.exists()
