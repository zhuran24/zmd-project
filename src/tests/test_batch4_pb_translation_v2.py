from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = (
    PROJECT_ROOT
    / "docs"
    / "research"
    / "front_offset_incident_20260718"
    / "batch4_harness"
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def encoder() -> ModuleType:
    return _load_module("batch4_pb_encoder_v2_test", HARNESS_ROOT / "pb_encoder_v2.py")


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    return _load_module("batch4_pb_translation_gate_v2_test", HARNESS_ROOT / "verify_pb_translation_v2.py")


@pytest.fixture(scope="module")
def toolchain() -> ModuleType:
    return _load_module("batch4_pb_toolchain_v2_test", HARNESS_ROOT / "run_pb_toolchain_v2.py")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def _assert_source_record(record: dict[str, object], path: Path) -> None:
    assert record["path"] == _display_path(path)
    assert record["sha256"] == _sha256(path)
    assert record["size_bytes"] == path.stat().st_size


def _assert_git_snapshot(snapshot: dict[str, object]) -> None:
    assert set(snapshot) == {
        "head",
        "tracked_dirty",
        "tracked_diff_sha256",
        "tracked_diff_size_bytes",
    }
    assert isinstance(snapshot["head"], str) and len(snapshot["head"]) == 40
    assert isinstance(snapshot["tracked_diff_sha256"], str)
    assert len(snapshot["tracked_diff_sha256"]) == 64
    assert type(snapshot["tracked_diff_size_bytes"]) is int
    assert type(snapshot["tracked_dirty"]) is bool
    assert snapshot["tracked_dirty"] is (snapshot["tracked_diff_size_bytes"] > 0)


def _fixture_paths(tmp_path: Path, *, bad_direction: bool = False) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    candidate = tmp_path / "candidate.json"
    instances = tmp_path / "instances.json"
    generic_io = tmp_path / "generic_io.json"
    canonical_rules = tmp_path / "canonical_rules.json"
    preprocess_plan = tmp_path / "preprocess_plan.json"
    direction = "NE" if bad_direction else "E"
    _write_json(
        candidate,
        {
            "facility_pools": {
                "manufacturing_3x3": [
                    {
                        "pose_id": "p0",
                        "occupied_cells": [[1, 2]],
                        "input_port_cells": [{"x": 0, "y": 0, "dir": direction}],
                        "output_port_cells": [{"x": 2, "y": 2, "dir": "E"}],
                    },
                    {
                        "pose_id": "p1",
                        "occupied_cells": [[3, 2]],
                        "input_port_cells": [{"x": 0, "y": 1, "dir": "W"}],
                        "output_port_cells": [{"x": 2, "y": 2, "dir": "W"}],
                    },
                    {
                        "pose_id": "p2",
                        "occupied_cells": [[2, 2]],
                        "input_port_cells": [{"x": 0, "y": 2, "dir": "N"}],
                        "output_port_cells": [{"x": 0, "y": 3, "dir": "S"}],
                    },
                ]
            }
        },
    )
    _write_json(
        instances,
        [
            {
                "instance_id": "crusher_1",
                "facility_type": "manufacturing_3x3",
                "operation_type": "crusher_blue_iron",
                "is_mandatory": True,
            },
            {
                "instance_id": "crusher_2",
                "facility_type": "manufacturing_3x3",
                "operation_type": "crusher_blue_iron",
                "is_mandatory": True,
            }
        ],
    )
    _write_json(
        generic_io,
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    _write_json(canonical_rules, {"globals": {"grid": {"width": 4, "height": 4}}})
    _write_json(preprocess_plan, {})
    return {
        "candidate": candidate,
        "instances": instances,
        "generic_io": generic_io,
        "canonical_rules": canonical_rules,
        "preprocess_plan": preprocess_plan,
    }


def _encoder_args(paths: dict[str, Path], out: Path) -> list[str]:
    return [
        "--project-root",
        str(PROJECT_ROOT),
        "--candidate",
        str(paths["candidate"]),
        "--instances",
        str(paths["instances"]),
        "--generic-io",
        str(paths["generic_io"]),
        "--canonical-rules",
        str(paths["canonical_rules"]),
        "--preprocess-plan",
        str(paths["preprocess_plan"]),
        "--ghost-w",
        "1",
        "--ghost-h",
        "1",
        "--out",
        str(out),
    ]


def _generated_paths(out: Path) -> tuple[Path, Path]:
    return out.with_suffix(".meta.json"), out.with_suffix(".var_map.json")


def _generate_tiny(encoder: ModuleType, tmp_path: Path) -> tuple[Path, Path, Path]:
    inputs = _fixture_paths(tmp_path)
    opb = tmp_path / "tiny.opb"
    assert encoder.main(_encoder_args(inputs, opb)) == 0
    meta, var_map = _generated_paths(opb)
    return opb, meta, var_map


def test_corrected_translation_gate_accepts_complete_tiny_model(
    encoder: ModuleType, gate: ModuleType, tmp_path: Path
) -> None:
    opb, meta_path, var_map_path = _generate_tiny(encoder, tmp_path)
    report_path = tmp_path / "gate.json"
    assert gate.main(
        [
            "--project-root",
            str(PROJECT_ROOT),
            "--opb",
            str(opb),
            "--meta",
            str(meta_path),
            "--var-map",
            str(var_map_path),
            "--output",
            str(report_path),
        ]
    ) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert all(report["checks"].values())
    assert report["constraint_multiset_sha256"]["actual"] == report["constraint_multiset_sha256"]["expected"]
    assert report["proof_status"] == "translation_only_no_unsat_or_proof_claim"

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    assert metadata["semantics"] == "reconstructed_new_baseline"
    assert metadata["execution"] == {"random_seed": None, "workers": None}
    assert metadata["historical_v1_status"]["valid_for_intended_relaxation"] is False
    assert len(metadata["historical_v1_status"]["independent_defects"]) == 2
    assert set(metadata["inputs"]) == {
        "candidate_placements",
        "mandatory_instances",
        "generic_io_requirements",
        "canonical_rules",
        "preprocess_plan",
        "operation_profiles_source",
        "port_binding_source",
    }
    assert all(len(record["sha256"]) == 64 for record in metadata["inputs"].values())
    encoder_path = HARNESS_ROOT / "pb_encoder_v2.py"
    gate_path = HARNESS_ROOT / "verify_pb_translation_v2.py"
    _assert_source_record(metadata["harness_source"], encoder_path)
    _assert_git_snapshot(metadata["git_snapshot"])
    assert metadata["git_revision"] == metadata["git_snapshot"]["head"]

    _assert_source_record(report["encoder_source"], encoder_path)
    _assert_source_record(report["gate_source"], gate_path)
    _assert_git_snapshot(report["encoder_git_snapshot"])
    _assert_git_snapshot(report["git_snapshot"])
    assert report["encoder_source"] == metadata["harness_source"]
    assert report["encoder_git_snapshot"] == metadata["git_snapshot"]
    assert set(report["translation_inputs"]) == {"meta", "opb", "var_map"}
    for key, path in {
        "meta": meta_path,
        "opb": opb,
        "var_map": var_map_path,
    }.items():
        record = report["translation_inputs"][key]
        assert record["path"] == _display_path(path)
        assert record["sha256"] == _sha256(path)
        assert record["size_bytes"] == path.stat().st_size


def test_encoder_uses_one_occupancy_channel_for_shared_opposite_front(
    encoder: ModuleType, tmp_path: Path
) -> None:
    opb, _meta_path, var_map_path = _generate_tiny(encoder, tmp_path)
    variable_map = json.loads(var_map_path.read_text(encoding="utf-8"))["variables"]
    pose_zero = next(value["id"] for value in variable_map if value["name"] == "pose__manufacturing_3x3__0")
    pose_one = next(value["id"] for value in variable_map if value["name"] == "pose__manufacturing_3x3__1")
    shared_occupancy = next(
        value["id"]
        for value in variable_map
        if value["kind"] == "occupancy" and value["x"] == 2 and value["y"] == 2
    )
    lines = opb.read_text(encoding="ascii").splitlines()
    assert f"-1 x{pose_zero} -1 x{shared_occupancy} >= -1 ;" in lines
    assert f"-1 x{pose_one} -1 x{shared_occupancy} >= -1 ;" in lines
    assert not any(
        line.startswith(f"-1 x{pose_zero} -1 x{pose_one}")
        or line.startswith(f"-1 x{pose_one} -1 x{pose_zero}")
        for line in lines
    )


def test_gate_rejects_encoder_source_provenance_tamper(
    encoder: ModuleType, gate: ModuleType, tmp_path: Path
) -> None:
    opb, meta_path, var_map_path = _generate_tiny(encoder, tmp_path)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["harness_source"]["sha256"] = "0" * 64
    _write_json(meta_path, metadata)
    report_path = tmp_path / "source_tamper_gate.json"

    assert gate.main(
        [
            "--project-root",
            str(PROJECT_ROOT),
            "--opb",
            str(opb),
            "--meta",
            str(meta_path),
            "--var-map",
            str(var_map_path),
            "--output",
            str(report_path),
        ]
    ) == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert "harness_source" in report["error"]["message"]


def test_gate_rejects_constraint_tamper_even_when_outer_hash_is_resealed(
    encoder: ModuleType, gate: ModuleType, tmp_path: Path
) -> None:
    opb, meta_path, var_map_path = _generate_tiny(encoder, tmp_path)
    variable_map = json.loads(var_map_path.read_text(encoding="utf-8"))["variables"]
    shared_occupancy = next(
        value["id"]
        for value in variable_map
        if value["kind"] == "occupancy" and value["x"] == 2 and value["y"] == 2
    )
    lines = opb.read_text(encoding="ascii").splitlines()
    target = next(
        index
        for index, line in enumerate(lines)
        if f"-1 x{shared_occupancy} >= -1 ;" in line
    )
    lines[target] = lines[target].replace("-1 x", "-2 x", 1)
    opb.write_text("\n".join(lines) + "\n", encoding="ascii")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["outputs"]["opb_sha256"] = hashlib.sha256(opb.read_bytes()).hexdigest()
    _write_json(meta_path, metadata)

    report_path = tmp_path / "tamper_gate.json"
    assert gate.main(
        [
            "--project-root",
            str(PROJECT_ROOT),
            "--opb",
            str(opb),
            "--meta",
            str(meta_path),
            "--var-map",
            str(var_map_path),
            "--output",
            str(report_path),
        ]
    ) == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["checks"]["constraint_multiset_exact"] is False
    assert report["constraint_diff"]["missing_total"] == 1
    assert report["constraint_diff"]["unexpected_total"] == 1


def test_front_clear_big_m_truth_table(encoder: ModuleType, tmp_path: Path) -> None:
    opb, _meta_path, var_map_path = _generate_tiny(encoder, tmp_path)
    variable_map = json.loads(var_map_path.read_text(encoding="utf-8"))["variables"]
    pose_zero = next(value["id"] for value in variable_map if value["name"] == "pose__manufacturing_3x3__0")
    shared_occupancy = next(
        value["id"]
        for value in variable_map
        if value["kind"] == "occupancy" and value["x"] == 2 and value["y"] == 2
    )
    expected = f"-1 x{pose_zero} -1 x{shared_occupancy} >= -1 ;"
    assert expected in opb.read_text(encoding="ascii").splitlines()

    def satisfies(selected: int, occupied: int) -> bool:
        return -selected - occupied >= -1

    assert satisfies(0, 1)  # Unselected pose imposes no clearance requirement.
    assert satisfies(1, 0)  # Selected pose with exactly d=1 free front is allowed.
    assert not satisfies(1, 1)  # Selected pose with d-1=0 free fronts is rejected.


def test_front_clear_big_m_truth_table_for_demand_greater_than_one(
    encoder: ModuleType, gate: ModuleType, tmp_path: Path
) -> None:
    inputs = _fixture_paths(tmp_path)
    fronts = [
        {"x": 0, "y": 0, "dir": "N"},
        {"x": 0, "y": 1, "dir": "S"},
        {"x": 0, "y": 2, "dir": "E"},
        {"x": 0, "y": 3, "dir": "W"},
    ]
    bodies = [[3, 3], [0, 0], [0, 1], [0, 2], [0, 3]]
    _write_json(
        inputs["candidate"],
        {
            "facility_pools": {
                "manufacturing_6x4": [
                    {
                        "pose_id": f"d3_p{index}",
                        "occupied_cells": [body],
                        "input_port_cells": fronts,
                        "output_port_cells": [{"x": 3, "y": 0, "dir": "E"}],
                    }
                    for index, body in enumerate(bodies)
                ]
            }
        },
    )
    _write_json(
        inputs["instances"],
        [
            {
                "instance_id": "grinder_1",
                "facility_type": "manufacturing_6x4",
                "operation_type": "grinder_dense_blue_iron",
                "is_mandatory": True,
            }
        ],
    )

    opb = tmp_path / "d3.opb"
    assert encoder.main(_encoder_args(inputs, opb)) == 0
    meta_path, var_map_path = _generated_paths(opb)
    variables = json.loads(var_map_path.read_text(encoding="utf-8"))["variables"]
    target_pose = next(
        value["id"] for value in variables if value["name"] == "pose__manufacturing_6x4__0"
    )
    occupancies = [
        next(
            value["id"]
            for value in variables
            if value["kind"] == "occupancy" and value["x"] == 0 and value["y"] == y_value
        )
        for y_value in range(4)
    ]
    expected = " ".join(
        [f"-3 x{target_pose}", *(f"-1 x{variable}" for variable in occupancies)]
    ) + " >= -4 ;"
    assert expected in opb.read_text(encoding="ascii").splitlines()

    def satisfies(selected: int, occupied_count: int) -> bool:
        return -3 * selected - occupied_count >= -4

    assert satisfies(0, 4)  # x=0 with every front occupied is unconstrained.
    assert satisfies(1, 1)  # x=1 with exactly d=3 free fronts is allowed.
    assert not satisfies(1, 2)  # x=1 with d-1=2 free fronts is rejected.

    report_path = tmp_path / "d3_gate.json"
    assert gate.main(
        [
            "--project-root",
            str(PROJECT_ROOT),
            "--opb",
            str(opb),
            "--meta",
            str(meta_path),
            "--var-map",
            str(var_map_path),
            "--output",
            str(report_path),
        ]
    ) == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "PASS"


def test_insufficient_port_domain_is_forced_zero_separately(
    encoder: ModuleType, gate: ModuleType, tmp_path: Path
) -> None:
    inputs = _fixture_paths(tmp_path)
    candidate = json.loads(inputs["candidate"].read_text(encoding="utf-8"))
    candidate["facility_pools"]["manufacturing_3x3"] = [
        {
            "pose_id": "insufficient",
            "occupied_cells": [[1, 1]],
            "input_port_cells": [],
            "output_port_cells": [{"x": 2, "y": 1, "dir": "E"}],
        }
    ]
    _write_json(inputs["candidate"], candidate)
    instances = json.loads(inputs["instances"].read_text(encoding="utf-8"))
    _write_json(inputs["instances"], instances[:1])

    opb = tmp_path / "forced_zero.opb"
    assert encoder.main(_encoder_args(inputs, opb)) == 0
    meta_path, var_map_path = _generated_paths(opb)
    variable_map = json.loads(var_map_path.read_text(encoding="utf-8"))["variables"]
    pose_variable = next(value["id"] for value in variable_map if value["kind"] == "pose")
    assert f"+1 x{pose_variable} = 0 ;" in opb.read_text(encoding="ascii").splitlines()
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    assert metadata["stats"]["forced_zero"] == 1
    assert metadata["stats"].get("front_clear_input", 0) == 0
    assert metadata["stats"].get("front_clear_output", 0) == 0

    report_path = tmp_path / "forced_zero_gate.json"
    assert gate.main(
        [
            "--project-root",
            str(PROJECT_ROOT),
            "--opb",
            str(opb),
            "--meta",
            str(meta_path),
            "--var-map",
            str(var_map_path),
            "--output",
            str(report_path),
        ]
    ) == 0


def test_closed_direction_validation_and_no_overwrite(
    encoder: ModuleType, gate: ModuleType, tmp_path: Path
) -> None:
    invalid_inputs = _fixture_paths(tmp_path / "invalid", bad_direction=True)
    invalid_out = tmp_path / "invalid.opb"
    with pytest.raises(encoder.EncoderError, match="N/S/E/W"):
        encoder.main(_encoder_args(invalid_inputs, invalid_out))
    assert not invalid_out.exists()

    opb, meta_path, var_map_path = _generate_tiny(encoder, tmp_path / "valid")
    with pytest.raises(FileExistsError, match="overwrite"):
        encoder.main(_encoder_args(_fixture_paths(tmp_path / "valid_inputs"), opb))

    report_path = tmp_path / "valid_gate.json"
    gate_args = [
        "--project-root",
        str(PROJECT_ROOT),
        "--opb",
        str(opb),
        "--meta",
        str(meta_path),
        "--var-map",
        str(var_map_path),
        "--output",
        str(report_path),
    ]
    assert gate.main(gate_args) == 0
    with pytest.raises(FileExistsError, match="overwrite"):
        gate.main(gate_args)


def test_coordinate_canaries_and_source_independence(gate: ModuleType) -> None:
    canaries = gate.coordinate_canaries()
    assert set(canaries) == {
        "stored_blocked_adjacent_free",
        "stored_free_adjacent_blocked",
        "opposite_ports_share_middle_front",
    }
    assert all(record["pass"] is True for record in canaries.values())

    for file_name in ("pb_encoder_v2.py", "verify_pb_translation_v2.py"):
        source = (HARNESS_ROOT / file_name).read_text(encoding="utf-8")
        assert "routing_binding_context" not in source
        assert "port_front_status" not in source
        assert "_DIR_DELTA" not in source
    gate_source = (HARNESS_ROOT / "verify_pb_translation_v2.py").read_text(encoding="utf-8")
    assert "import pb_encoder_v2" not in gate_source


def test_toolchain_classifies_internal_time_limit_without_a_claim(toolchain: ModuleType) -> None:
    assert toolchain._solver_status("s TIMELIMIT\n", "", False) == "TIME_LIMIT"
    assert toolchain._solver_status("", "", True) == "EXTERNAL_TIMEOUT"


def test_toolchain_records_closed_provenance_and_refuses_overwrite(
    encoder: ModuleType,
    gate: ModuleType,
    toolchain: ModuleType,
    tmp_path: Path,
) -> None:
    opb, meta_path, var_map_path = _generate_tiny(encoder, tmp_path / "model")
    gate_path = tmp_path / "translation_gate.json"
    assert gate.main(
        [
            "--project-root",
            str(PROJECT_ROOT),
            "--opb",
            str(opb),
            "--meta",
            str(meta_path),
            "--var-map",
            str(var_map_path),
            "--output",
            str(gate_path),
        ]
    ) == 0

    fake_roundingsat = tmp_path / "roundingsat"
    fake_roundingsat.write_text("#!/bin/sh\nprintf 's TIMELIMIT\\n'\nexit 4\n", encoding="utf-8")
    fake_roundingsat.chmod(0o755)
    fake_veripb = tmp_path / "veripb"
    fake_veripb.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    fake_veripb.chmod(0o755)
    output_dir = tmp_path / "toolchain"
    args = [
        "--opb",
        str(opb),
        "--meta",
        str(meta_path),
        "--translation-gate",
        str(gate_path),
        "--roundingsat",
        str(fake_roundingsat),
        "--roundingsat-repo",
        str(PROJECT_ROOT),
        "--veripb",
        str(fake_veripb),
        "--output-dir",
        str(output_dir),
        "--solver-time-limit",
        "1",
        "--wall-timeout",
        "2",
    ]
    assert toolchain.main(args) == 0

    record = json.loads((output_dir / "toolchain_record.json").read_text(encoding="utf-8"))
    assert record["solver"]["status"] == "TIME_LIMIT"
    assert record["claim"] == "none"
    assert record["verifier"]["status"] == "NOT_RUN_NO_COMPLETE_UNSAT_PROOF"
    assert set(record["inputs"]) == {"meta", "opb", "translation_gate", "var_map"}
    assert record["inputs"]["opb"]["sha256"] == _sha256(opb)
    assert record["inputs"]["meta"]["sha256"] == _sha256(meta_path)
    assert record["inputs"]["var_map"]["sha256"] == _sha256(var_map_path)
    assert record["inputs"]["translation_gate"]["sha256"] == _sha256(gate_path)
    for key, path in {
        "runner": HARNESS_ROOT / "run_pb_toolchain_v2.py",
        "gate": HARNESS_ROOT / "verify_pb_translation_v2.py",
        "encoder": HARNESS_ROOT / "pb_encoder_v2.py",
    }.items():
        _assert_source_record(record["sources"][key], path)
        _assert_git_snapshot(record["git_snapshots"][key])

    with pytest.raises(FileExistsError, match="overwrite"):
        toolchain.main(args)
