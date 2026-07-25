from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pytest
from ortools.sat import cp_model_pb2


ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724" / "baseline_admission_v1.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cuts_ab16_baseline_admission_v1", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ADMISSION = _load()


def _write(path: Path, raw: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _canonical(value: object) -> bytes:
    return ADMISSION.canonical_json(value)


def _incumbent() -> dict[str, object]:
    return {
        "machine_001": {
            "anchor": {"x": 1, "y": 2},
            "instance_id": "machine_001",
            "pose_id": "p1",
            "pose_idx": 3,
        },
        "machine_002": {
            "anchor": {"x": 4, "y": 5},
            "instance_id": "machine_002",
            "pose_id": "p2",
            "pose_idx": 7,
        },
    }


def _model() -> cp_model_pb2.CpModelProto:
    model = cp_model_pb2.CpModelProto()
    for name in ("pick_1", "pick_2"):
        variable = model.variables.add()
        variable.name = name
        variable.domain.extend([0, 1])
    constraint = model.constraints.add()
    constraint.name = "one_pick"
    constraint.exactly_one.literals.extend([0, 1])
    return model


def _legacy(
    *,
    historical_model_text_sha256: str,
    variable_count: int,
    constraint_count: int,
    incumbent_sha256: str,
    incumbent: dict[str, object],
) -> dict[str, object]:
    return {
        "arm": "control",
        "injection": {
            "arithmetic_sample_count": 0,
            "compiled_observed": 0,
            "wall_seconds": 0.0,
        },
        "prestate": {
            "incumbent": incumbent,
            "incumbent_sha256": incumbent_sha256,
            "model_constraint_count": constraint_count,
            "model_proto_sha256": historical_model_text_sha256,
            "model_variable_count": variable_count,
        },
        "run_tag": "pc-control-a002",
        "schema_version": 1,
        "terminal_status": "ARM_COMPLETE",
    }


def _fixture(tmp_path: Path) -> dict[str, Any]:
    model = _model()
    model_raw = model.SerializeToString(deterministic=True)
    model_identity = _write(tmp_path / "rebuilt-model.pb", model_raw)
    historical_model_text_sha256 = ADMISSION.historical_model_text_sha256(model)
    assert model_identity["sha256"] != historical_model_text_sha256
    incumbent = _incumbent()
    incumbent_sha256 = ADMISSION.semantic_digest(incumbent)
    incumbent_identity = _write(tmp_path / "incumbent.json", _canonical(incumbent))
    builder_identity = _write(tmp_path / "builder.py", b"# fixture builder\n")
    replay_tool_identity = _write(tmp_path / "fixed_replay.py", b"# fixture replay\n")
    inputs = {
        role: _write(tmp_path / f"{role}.json", _canonical({"role": role}))
        for role in sorted(ADMISSION.REQUIRED_REBUILD_INPUT_ROLES)
    }
    metadata = {
        "builder_identity": builder_identity,
        "canonical_binary": True,
        "created_at_utc": "2026-07-24T01:00:00Z",
        "errors": [],
        "global_claim_authorized": False,
        "input_identities": inputs,
        "legacy_control_used_as_build_input": False,
        "model_backend": ADMISSION.MODEL_BACKEND,
        "model_binary_format": ADMISSION.MODEL_BINARY_FORMAT,
        "model_constraint_count": len(model.constraints),
        "model_identity": model_identity,
        "historical_model_text_sha256": historical_model_text_sha256,
        "model_variable_count": len(model.variables),
        "purpose": ADMISSION.REBUILD_PURPOSE,
        "repository_head": "a" * 40,
        "schema_version": ADMISSION.METADATA_SCHEMA,
        "status": "PASS",
    }
    metadata_identity = _write(tmp_path / "metadata.json", _canonical(metadata))
    replay = {
        "all_fixed_equalities_added": True,
        "assignment_count": len(incumbent),
        "conflicting_assignment_count": 0,
        "created_at_utc": "2026-07-24T01:00:01Z",
        "fixed_assignment_count": len(incumbent),
        "global_claim_authorized": False,
        "incumbent_identity": incumbent_identity,
        "incumbent_sha256": incumbent_sha256,
        "legacy_control_used_as_truth_root": False,
        "metadata_identity": metadata_identity,
        "model_constraint_count": len(model.constraints),
        "model_identity": model_identity,
        "model_validation_errors": [],
        "model_variable_count": len(model.variables),
        "purpose": ADMISSION.REPLAY_PURPOSE,
        "replay_errors": [],
        "replay_tool_identity": replay_tool_identity,
        "schema_version": ADMISSION.REPLAY_SCHEMA,
        "solution_matches_fixed_assignments": True,
        "solver_status": "OPTIMAL",
        "status": "PASS",
        "unresolved_assignment_count": 0,
        "verdict": ADMISSION.REPLAY_VERDICT,
    }
    replay_identity = _write(tmp_path / "replay.json", _canonical(replay))
    legacy = _legacy(
        historical_model_text_sha256=historical_model_text_sha256,
        variable_count=len(model.variables),
        constraint_count=len(model.constraints),
        incumbent_sha256=incumbent_sha256,
        incumbent=incumbent,
    )
    legacy_raw = json.dumps(legacy, indent=2, sort_keys=True).encode() + b"\n"
    legacy_identity = _write(tmp_path / "control-a002-result.json", legacy_raw)
    expectation = ADMISSION.BaselineExpectation(
        profile="small-fixture-v1",
        repository_head="a" * 40,
        legacy_path=legacy_identity["path"],
        legacy_size_bytes=legacy_identity["size_bytes"],
        legacy_sha256=legacy_identity["sha256"],
        historical_model_text_sha256=historical_model_text_sha256,
        model_variable_count=len(model.variables),
        model_constraint_count=len(model.constraints),
        incumbent_sha256=incumbent_sha256,
        incumbent_assignment_count=len(incumbent),
    )
    return {
        "expectation": expectation,
        "incumbent": incumbent,
        "incumbent_path": Path(incumbent_identity["path"]),
        "legacy_path": Path(legacy_identity["path"]),
        "metadata": metadata,
        "metadata_path": Path(metadata_identity["path"]),
        "model_identity": model_identity,
        "model_path": Path(model_identity["path"]),
        "replay": replay,
        "replay_path": Path(replay_identity["path"]),
    }


def _admit(fixture: dict[str, Any]) -> dict[str, object]:
    return ADMISSION._admit_paths(
        legacy_control=fixture["legacy_path"],
        rebuilt_model=fixture["model_path"],
        rebuilt_metadata=fixture["metadata_path"],
        fixed_assignment_replay=fixture["replay_path"],
        created_at_utc="2026-07-24T01:00:02Z",
        expectation=fixture["expectation"],
    )


def _rewrite_metadata(fixture: dict[str, Any]) -> None:
    identity = _write(fixture["metadata_path"], _canonical(fixture["metadata"]))
    fixture["replay"]["metadata_identity"] = identity
    _write(fixture["replay_path"], _canonical(fixture["replay"]))


def _rewrite_replay(fixture: dict[str, Any]) -> None:
    _write(fixture["replay_path"], _canonical(fixture["replay"]))


def test_small_rebuilt_baseline_is_admitted_without_downstream_authority(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    result = _admit(fixture)
    assert result["status"] == "PASS"
    assert result["verdict"] == ADMISSION.ADMISSION_VERDICT
    assert result["legacy_control"]["provenance_only"] is True
    assert result["legacy_control"]["authorizing"] is False
    assert result["authorizations"] == {
        "baseline_inputs_admitted": True,
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": False,
        "solver_run_authorized": False,
    }
    assert result["rebuilt_model"]["canonical_binary"] is True
    assert result["rebuilt_model"]["identity"]["sha256"] == fixture["model_identity"]["sha256"]
    assert (
        result["expected_baseline"]["historical_model_text_sha256"]
        == fixture["expectation"].historical_model_text_sha256
    )
    assert result["rebuilt_model"]["identity"]["sha256"] != result["expected_baseline"]["historical_model_text_sha256"]
    assert result["fixed_assignment_replay"]["status"] == "PASS"


def test_production_expectation_is_exactly_pinned() -> None:
    expected = ADMISSION.PRODUCTION_EXPECTATION
    assert expected.historical_model_text_sha256 == ("3a9be08dcca722fc4bf7dfc9bcf7be4a1213af14ded9ec7b769909a029904d32")
    assert expected.model_variable_count == 37_760
    assert expected.model_constraint_count == 95_136
    assert expected.incumbent_sha256 == ("13f88404d7f5e4fde86929f82997a2b9850fa1cc4791d710c0363ed3e072f223")
    assert expected.incumbent_assignment_count == 293
    assert expected.legacy_size_bytes == 507_095
    assert expected.legacy_sha256 == ("9e747c214c2108b7fc73fede1d31873b24bf765d74857cf4a846cf5178ebcff6")


def test_legacy_bytes_are_provenance_only_and_byte_locked(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["legacy_path"].write_bytes(fixture["legacy_path"].read_bytes() + b" ")
    with pytest.raises(ADMISSION.AdmissionError, match="pinned provenance"):
        _admit(fixture)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("canonical_binary", False, "metadata semantics"),
        ("legacy_control_used_as_build_input", True, "metadata semantics"),
        ("global_claim_authorized", True, "metadata semantics"),
        ("model_variable_count", True, "expected integer"),
    ],
)
def test_metadata_semantic_mutations_fail_closed(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["metadata"][field] = value
    _rewrite_metadata(fixture)
    with pytest.raises(ADMISSION.AdmissionError, match=message):
        _admit(fixture)


def test_metadata_duplicate_key_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    raw = fixture["metadata_path"].read_bytes()
    assert raw.startswith(b"{")
    fixture["metadata_path"].write_bytes(b'{"status":"PASS",' + raw[1:])
    metadata_identity = {
        "path": str(fixture["metadata_path"].resolve()),
        "sha256": hashlib.sha256(fixture["metadata_path"].read_bytes()).hexdigest(),
        "size_bytes": fixture["metadata_path"].stat().st_size,
    }
    fixture["replay"]["metadata_identity"] = metadata_identity
    _rewrite_replay(fixture)
    with pytest.raises(ADMISSION.AdmissionError, match="duplicate JSON key"):
        _admit(fixture)


def test_binary_digest_cannot_replace_historical_text_digest(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    binary_sha256 = fixture["model_identity"]["sha256"]
    assert binary_sha256 != fixture["expectation"].historical_model_text_sha256
    fixture["metadata"]["historical_model_text_sha256"] = binary_sha256
    _rewrite_metadata(fixture)
    with pytest.raises(ADMISSION.AdmissionError, match="metadata semantics"):
        _admit(fixture)


def test_unknown_or_noncanonical_protobuf_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    raw = fixture["model_path"].read_bytes() + b"\xa0\x06\x00"
    model_identity = _write(fixture["model_path"], raw)
    fixture["metadata"]["model_identity"] = model_identity
    _rewrite_metadata(fixture)
    fixture["replay"]["model_identity"] = model_identity
    _rewrite_replay(fixture)
    with pytest.raises(ADMISSION.AdmissionError, match="unknown protobuf|not canonical"):
        _admit(fixture)


def test_rebuild_input_or_builder_drift_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    builder = Path(fixture["metadata"]["builder_identity"]["path"])
    builder.write_text("# drifted builder\n", encoding="utf-8")
    with pytest.raises(ADMISSION.AdmissionError, match="metadata builder"):
        _admit(fixture)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("solver_status", "UNKNOWN"),
        ("solution_matches_fixed_assignments", False),
        ("fixed_assignment_count", 1),
        ("unresolved_assignment_count", 1),
        ("unresolved_assignment_count", False),
        ("conflicting_assignment_count", 1),
        ("legacy_control_used_as_truth_root", True),
        ("global_claim_authorized", True),
        ("replay_errors", ["fixture error"]),
    ],
)
def test_fixed_assignment_receipt_mutations_fail_closed(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["replay"][field] = value
    _rewrite_replay(fixture)
    with pytest.raises(ADMISSION.AdmissionError, match="replay semantics|expected integer"):
        _admit(fixture)


def test_incumbent_semantic_drift_fails_even_with_self_consistent_identity(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    changed = dict(fixture["incumbent"])
    changed["machine_001"] = dict(changed["machine_001"])
    changed["machine_001"]["pose_idx"] = 99
    incumbent_identity = _write(fixture["incumbent_path"], _canonical(changed))
    fixture["replay"]["incumbent_identity"] = incumbent_identity
    fixture["replay"]["incumbent_sha256"] = ADMISSION.semantic_digest(changed)
    _rewrite_replay(fixture)
    with pytest.raises(ADMISSION.AdmissionError, match="replay semantics|incumbent semantic"):
        _admit(fixture)


def test_symlinked_direct_input_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    target = fixture["model_path"]
    link = tmp_path / "model-link.pb"
    link.symlink_to(target)
    fixture["model_path"] = link
    with pytest.raises(ADMISSION.AdmissionError, match="non-symlink"):
        _admit(fixture)


def test_output_is_canonical_and_no_overwrite(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    result = _admit(fixture)
    output = tmp_path / "admission.json"
    identity = ADMISSION.write_exclusive(output, result)
    before = output.read_bytes()
    assert before == _canonical(result)
    assert identity["sha256"] == hashlib.sha256(before).hexdigest()
    with pytest.raises(ADMISSION.AdmissionError, match="already exists"):
        ADMISSION.write_exclusive(output, result)
    assert output.read_bytes() == before


def test_output_parent_symlink_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    result = _admit(fixture)
    real = tmp_path / "real-output"
    real.mkdir()
    link = tmp_path / "output-link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ADMISSION.AdmissionError, match="non-symlink directory"):
        ADMISSION.write_exclusive(link / "admission.json", result)
