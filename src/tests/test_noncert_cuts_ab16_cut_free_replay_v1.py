from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from ortools.sat import cp_model_pb2
from ortools.sat.python import cp_model
import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724"


def _load(name: str, module_name: str | None = None):
    path = RESEARCH / f"{name}.py"
    spec = importlib.util.spec_from_file_location(module_name or name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE_CONTRACT = _load("baseline_admission_v1")
REPLAY = _load("cut_free_incumbent_replay_v1")
REBUILD = _load("baseline_rebuild_v1")


def _write(path: Path, raw: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _tiny_inputs() -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    candidate = {
        "facility_pools": {
            "fixture": [
                {
                    "pose_id": "fixture-pose",
                    "anchor": {"x": 0, "y": 0},
                }
            ]
        }
    }
    mandatory = [
        {
            "instance_id": "fixture-001",
            "facility_type": "fixture",
            "operation_type": "op",
        }
    ]
    incumbent = {
        "fixture-001": {
            "instance_id": "fixture-001",
            "facility_type": "fixture",
            "operation_type": "op",
            "bound_type": "exact",
            "pose_idx": 0,
            "pose_id": "fixture-pose",
            "anchor": {"x": 0, "y": 0},
        }
    }
    return candidate, mandatory, incumbent


def _ghost_replay_fixture(tmp_path: Path) -> dict[str, Any]:
    candidate = {"facility_pools": {}}
    mandatory: list[object] = []
    incumbent = {
        "ghost_pick": {
            "anchor": {"x": 0, "y": 0},
            "instance_id": "ghost_pick",
            "pose_idx": 0,
        }
    }
    checkout_inputs = {
        "candidate_placements": _write(
            tmp_path / "data/preprocessed/candidate_placements.json",
            BASELINE_CONTRACT.canonical_json(candidate),
        ),
        "canonical_rules": _write(
            tmp_path / "rules/canonical_rules.json",
            BASELINE_CONTRACT.canonical_json({}),
        ),
        "mandatory_instances": _write(
            tmp_path / "data/preprocessed/mandatory_exact_instances.json",
            BASELINE_CONTRACT.canonical_json(mandatory),
        ),
    }
    _git(tmp_path, "init")
    _git(tmp_path, "add", "--", "data", "rules")
    _git(
        tmp_path,
        "-c",
        "user.name=AB16 Test",
        "-c",
        "user.email=ab16@example.invalid",
        "commit",
        "-m",
        "fixture checkout",
    )
    repository_head = _git(tmp_path, "rev-parse", "HEAD")
    repository_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}")

    campaign_dir = tmp_path / "run-ab16-fixture"
    package_dir = campaign_dir / "campaign-authority/package"
    package_inputs = {
        role: _write(
            package_dir / "payload" / f"input.{role}.json",
            Path(str(identity["path"])).read_bytes(),
        )
        for role, identity in checkout_inputs.items()
    }
    manifest_identity = _write(package_dir / "package-manifest.json", b"fixture package manifest\n")
    seal_identity = _write(package_dir / "SHA256SUMS", b"fixture package seal\n")
    package = {
        "manifest_identity": manifest_identity,
        "package_id": seal_identity["sha256"],
        "seal_identity": seal_identity,
    }
    git_path = shutil.which("git")
    assert git_path is not None
    git_identity = _identity(Path(git_path))
    campaign_root = {
        "authority_tools": {"git": git_identity},
        "package": {**package, "package_dir": str(package_dir)},
        "repository_head": repository_head,
        "strict_inputs": package_inputs,
    }
    campaign_root_identity = _write(
        campaign_dir / "campaign-root.json",
        BASELINE_CONTRACT.canonical_json(campaign_root),
    )
    campaign_provenance = {
        "authority_scope": BASELINE_CONTRACT.CAMPAIGN_PROVENANCE_AUTHORITY_SCOPE,
        "campaign_root_identity": campaign_root_identity,
        "git_identity": git_identity,
        "import_mode": BASELINE_CONTRACT.CHECKOUT_IMPORT_MODE,
        "input_identities": checkout_inputs,
        "package": package,
        "repository_head": repository_head,
        "repository_root": str(tmp_path.resolve()),
        "repository_tree": repository_tree,
        "schema_version": BASELINE_CONTRACT.CAMPAIGN_PROVENANCE_SCHEMA,
    }
    campaign_provenance_path = campaign_dir / "prospective-ab16/baseline/campaign-provenance.json"
    _write(
        campaign_provenance_path,
        BASELINE_CONTRACT.canonical_json(campaign_provenance),
    )

    model = cp_model.CpModel()
    ghost = model.new_bool_var("ghost__0_0_6_6")
    model.add(ghost == 1)
    model_path = tmp_path / "baseline/model.pb"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    assert model.export_to_file(str(model_path))
    model_raw = model_path.read_bytes()
    model_proto = cp_model_pb2.CpModelProto()
    model_proto.ParseFromString(model_raw)
    model_identity = _identity(model_path)
    incumbent_identity = _write(
        tmp_path / "baseline/incumbent.json",
        BASELINE_CONTRACT.canonical_json(incumbent),
    )
    historical_model_text_sha256 = BASELINE_CONTRACT.historical_model_text_sha256(model_proto)
    expectation = BASELINE_CONTRACT.BaselineExpectation(
        profile="tiny-ghost-v1",
        legacy_size_bytes=0,
        legacy_sha256="0" * 64,
        historical_model_text_sha256=historical_model_text_sha256,
        model_variable_count=1,
        model_constraint_count=1,
        incumbent_sha256=BASELINE_CONTRACT.semantic_digest(incumbent),
        incumbent_assignment_count=1,
    )
    builder_identity = _write(tmp_path / "baseline/builder.py", b"# fixture builder\n")
    metadata = {
        "builder_identity": builder_identity,
        "campaign_provenance": campaign_provenance,
        "canonical_binary": True,
        "created_at_utc": "2026-08-02T23:00:00Z",
        "errors": [],
        "global_claim_authorized": False,
        "historical_model_text_sha256": historical_model_text_sha256,
        "input_identities": checkout_inputs,
        "legacy_control_used_as_build_input": False,
        "model_backend": BASELINE_CONTRACT.MODEL_BACKEND,
        "model_binary_format": BASELINE_CONTRACT.MODEL_BINARY_FORMAT,
        "model_constraint_count": 1,
        "model_identity": model_identity,
        "model_variable_count": 1,
        "purpose": BASELINE_CONTRACT.REBUILD_PURPOSE,
        "schema_version": BASELINE_CONTRACT.METADATA_SCHEMA,
        "status": "PASS",
    }
    metadata_path = tmp_path / "baseline/metadata.json"
    _write(metadata_path, BASELINE_CONTRACT.canonical_json(metadata))
    return {
        "campaign_provenance_path": campaign_provenance_path,
        "expectation": expectation,
        "incumbent_path": Path(str(incumbent_identity["path"])),
        "metadata_path": metadata_path,
        "model_path": Path(str(model_identity["path"])),
    }


def test_fixed_assignment_replay_accepts_tiny_feasible_model(tmp_path: Path) -> None:
    model = cp_model.CpModel()
    x = model.new_bool_var("z__group::fixture::op::0__0")
    model.add(x == 1)
    model_path = tmp_path / "model.bin"
    assert model.export_to_file(str(model_path))

    result = REPLAY.replay_fixed_assignment(
        model_path.read_bytes(),
        incumbent=_tiny_inputs()[2],
        mandatory_instances=_tiny_inputs()[1],
        candidate_placements=_tiny_inputs()[0],
        max_time_seconds=2.0,
    )

    assert result["status"] == "PASS"
    assert result["variable_count"] == 1
    assert result["fixed_assignment_count"] == 1


def test_replay_paths_produces_tiny_ghost_receipt_with_real_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _ghost_replay_fixture(tmp_path)
    output = tmp_path / "baseline/replay.json"
    monkeypatch.chdir(tmp_path)

    receipt, identity = REPLAY._replay_paths(
        campaign_provenance_path=fixture["campaign_provenance_path"],
        model_path=fixture["model_path"],
        metadata_path=fixture["metadata_path"],
        incumbent_path=fixture["incumbent_path"],
        output_path=output,
        expectation=fixture["expectation"],
        created_at_utc="2026-08-02T23:00:01Z",
        max_time_seconds=2.0,
    )

    assert receipt["status"] == "PASS"
    assert receipt["solver_status"] == "OPTIMAL"
    assert receipt["model_variable_count"] == 1
    assert receipt["model_constraint_count"] == 1
    assert receipt["assignment_count"] == receipt["fixed_assignment_count"] == 1
    assert output.read_bytes() == REPLAY._authority_json(receipt)
    assert identity == _identity(output)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("model_variable_count", 2, "metadata semantics drifted"),
        ("model_constraint_count", 2, "metadata semantics drifted"),
        ("incumbent_assignment_count", 2, "incumbent digest or assignment count drifted"),
        ("incumbent_sha256", "f" * 64, "incumbent digest or assignment count drifted"),
    ],
)
def test_replay_paths_rejects_expectation_drift_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    fixture = _ghost_replay_fixture(tmp_path)
    output = tmp_path / "baseline/replay.json"
    monkeypatch.chdir(tmp_path)
    drifted = replace(fixture["expectation"], **{field: value})

    with pytest.raises(REPLAY.ReplayError, match=message):
        REPLAY._replay_paths(
            campaign_provenance_path=fixture["campaign_provenance_path"],
            model_path=fixture["model_path"],
            metadata_path=fixture["metadata_path"],
            incumbent_path=fixture["incumbent_path"],
            output_path=output,
            expectation=drifted,
            created_at_utc="2026-08-02T23:00:01Z",
            max_time_seconds=2.0,
        )
    assert not output.exists()


def test_fixed_assignment_replay_rejects_unmapped_assignment(
    tmp_path: Path,
) -> None:
    model = cp_model.CpModel()
    x = model.new_bool_var("z__group::fixture::op::0__0")
    model.add(x == 1)
    model_path = tmp_path / "model.bin"
    assert model.export_to_file(str(model_path))

    candidate, mandatory, incumbent = _tiny_inputs()
    incumbent["fixture-001"]["pose_idx"] = 1
    with pytest.raises(REPLAY.ReplayError, match="absent or duplicated"):
        REPLAY.replay_fixed_assignment(
            model_path.read_bytes(),
            incumbent=incumbent,
            mandatory_instances=mandatory,
            candidate_placements=candidate,
            max_time_seconds=2.0,
        )


def test_fixed_assignment_replay_allows_unnamed_nonselector(
    tmp_path: Path,
) -> None:
    model = cp_model.CpModel()
    x = model.new_bool_var("z__group::fixture::op::0__0")
    unnamed = model.new_bool_var("")
    model.add(x == 1)
    model.add(unnamed == 0)
    model_path = tmp_path / "model.bin"
    assert model.export_to_file(str(model_path))

    result = REPLAY.replay_fixed_assignment(
        model_path.read_bytes(),
        incumbent=_tiny_inputs()[2],
        mandatory_instances=_tiny_inputs()[1],
        candidate_placements=_tiny_inputs()[0],
        max_time_seconds=2.0,
    )

    assert result["status"] == "PASS"
    assert result["fixed_assignment_count"] == 1


def test_fixed_assignment_replay_rejects_nonboolean_selector(
    tmp_path: Path,
) -> None:
    model = cp_model.CpModel()
    x = model.new_int_var(0, 2, "z__group::fixture::op::0__0")
    model.add(x == 1)
    model_path = tmp_path / "model.bin"
    assert model.export_to_file(str(model_path))

    with pytest.raises(REPLAY.ReplayError, match="exact boolean"):
        REPLAY.replay_fixed_assignment(
            model_path.read_bytes(),
            incumbent=_tiny_inputs()[2],
            mandatory_instances=_tiny_inputs()[1],
            candidate_placements=_tiny_inputs()[0],
            max_time_seconds=2.0,
        )


def test_strict_json_requires_canonical_authority_bytes() -> None:
    assert REPLAY._strict_json(b'{"a":1}\n', "fixture") == {"a": 1}
    with pytest.raises(REPLAY.ReplayError, match="not canonical"):
        REPLAY._strict_json(b'{"a": 1}\n', "fixture")


def _fixed_args(**changes: object) -> argparse.Namespace:
    value = {
        "master_seconds": 900.0,
        "binding_seconds": 600.0,
        "routing_seconds": 600.0,
        "max_iterations": 30,
        "binding_alt_cap": 200,
        "workers": 1,
        "seed": 2026072301,
        "ghost_w": 6,
        "ghost_h": 6,
        "run_nonce": "fixture-run",
        "campaign_provenance": ROOT / ".artifacts/fixture-campaign/campaign-provenance.json",
        "candidate_placements": (ROOT / "data/preprocessed/candidate_placements.json"),
        "canonical_rules": (ROOT / "rules/canonical_rules.json"),
        "mandatory_instances": (ROOT / "data/preprocessed/mandatory_exact_instances.json"),
    }
    value.update(changes)
    return argparse.Namespace(**value)


def test_baseline_rebuild_rejects_parameter_drift() -> None:
    REBUILD._validate_fixed_parameters(_fixed_args())
    with pytest.raises(REBUILD.BaselineRebuildError, match="parameters drifted"):
        REBUILD._validate_fixed_parameters(_fixed_args(seed=7))
    with pytest.raises(REBUILD.BaselineRebuildError, match="nonce"):
        REBUILD._validate_fixed_parameters(_fixed_args(run_nonce=""))
    with pytest.raises(REBUILD.BaselineRebuildError, match="campaign provenance"):
        REBUILD._validate_fixed_parameters(_fixed_args(campaign_provenance=Path("relative-provenance.json")))
    with pytest.raises(REBUILD.BaselineRebuildError, match="not absolute"):
        REBUILD._validate_fixed_parameters(_fixed_args(candidate_placements=Path("relative.json")))


def test_baseline_builder_declares_non_authorizing_output() -> None:
    source = (RESEARCH / "baseline_rebuild_v1.py").read_text(encoding="utf-8")
    assert '"authorizing": False' in source
    assert "EXACT_CUT_FRAMEWORK_ATTACH" in source
    assert "enabled_cut_families=()" in source
    assert "EXPECTED_REPOSITORY_ROOT" not in source
    assert "EXPECTED_HEAD" not in source
    assert "sys.meta_path" not in source
    assert "importlib" not in source
    assert "baseline_contract.campaign_provenance" in source
    assert BASELINE_CONTRACT.CHECKOUT_IMPORT_MODE == "tracked_clean_pinned_checkout"
