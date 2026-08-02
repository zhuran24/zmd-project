from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType
from typing import Any

from ortools.sat import cp_model_pb2
import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724"


def _load(name: str) -> ModuleType:
    path = RESEARCH / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ADMISSION = _load("baseline_admission_v1")
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
    return _write_identity(path, path.read_bytes())


def _write_identity(path: Path, raw: bytes) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _canonical(value: object) -> bytes:
    return ADMISSION.canonical_json(value)


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _tiny_model() -> cp_model_pb2.CpModelProto:
    model = cp_model_pb2.CpModelProto()
    variable = model.variables.add()
    variable.name = "ghost_pick"
    variable.domain.extend([0, 1])
    return model


def _tiny_incumbent() -> dict[str, object]:
    return {
        "ghost_pick": {
            "instance_id": "ghost_pick",
            "selected": True,
        }
    }


def _fixture(tmp_path: Path) -> dict[str, Any]:
    inputs = {
        role: _write(tmp_path / relative, _canonical({"role": role}))
        for role, relative in ADMISSION.CHECKOUT_INPUT_PATHS.items()
    }
    _git(tmp_path, "init")
    _git(
        tmp_path,
        "add",
        "--",
        ADMISSION.CHECKOUT_INPUT_PATHS["canonical_rules"].as_posix(),
        ADMISSION.CHECKOUT_INPUT_PATHS["mandatory_instances"].as_posix(),
    )
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
    git_path = shutil.which("git")
    assert git_path is not None
    git_identity = _identity(Path(git_path))

    campaign_dir = tmp_path / "run-ab16-fixture"
    package_dir = campaign_dir / "campaign-authority" / "package"
    package_payload = package_dir / "payload"
    package_payload.mkdir(parents=True)
    package_inputs = {
        role: _write(package_payload / f"input.{role}.json", Path(identity["path"]).read_bytes())
        for role, identity in inputs.items()
    }
    package_manifest_identity = _write(package_dir / "package-manifest.json", b"fixture package manifest\n")
    package_seal_identity = _write(package_dir / "SHA256SUMS", b"fixture package seal\n")
    package = {
        "manifest_identity": package_manifest_identity,
        "package_id": package_seal_identity["sha256"],
        "seal_identity": package_seal_identity,
    }
    campaign_root = {
        "authority_tools": {"git": git_identity},
        "package": {**package, "package_dir": str(package_dir)},
        "repository_head": repository_head,
        "strict_inputs": package_inputs,
    }
    campaign_root_identity = _write(campaign_dir / "campaign-root.json", _canonical(campaign_root))
    campaign_provenance = {
        "authority_scope": ADMISSION.CAMPAIGN_PROVENANCE_AUTHORITY_SCOPE,
        "campaign_root_identity": campaign_root_identity,
        "git_identity": git_identity,
        "import_mode": ADMISSION.CHECKOUT_IMPORT_MODE,
        "input_identities": inputs,
        "package": package,
        "repository_head": repository_head,
        "repository_root": str(tmp_path.resolve()),
        "repository_tree": repository_tree,
        "schema_version": ADMISSION.CAMPAIGN_PROVENANCE_SCHEMA,
    }
    output_dir = campaign_dir / "prospective-ab16" / "baseline"
    campaign_provenance_path = output_dir / "campaign-provenance.json"
    _write(campaign_provenance_path, _canonical(campaign_provenance))

    model = _tiny_model()
    incumbent = _tiny_incumbent()
    expectation = ADMISSION.BaselineExpectation(
        profile="tiny-rebuild-writer-v1",
        legacy_size_bytes=1,
        legacy_sha256=hashlib.sha256(b"x").hexdigest(),
        historical_model_text_sha256=ADMISSION.historical_model_text_sha256(model),
        model_variable_count=1,
        model_constraint_count=0,
        incumbent_sha256=ADMISSION.semantic_digest(incumbent),
        incumbent_assignment_count=1,
    )
    computation = REBUILD.BaselineComputation(
        model=model,
        incumbent=incumbent,
        solution_values=(1,),
        runner_status="OPTIMAL",
        proof_summary={"fixture": "deterministic-solver-substitute"},
        wall_seconds=0.125,
    )
    return {
        "campaign_dir": campaign_dir,
        "campaign_provenance": campaign_provenance,
        "campaign_provenance_path": campaign_provenance_path,
        "computation": computation,
        "expectation": expectation,
        "inputs": {role: Path(identity["path"]) for role, identity in inputs.items()},
        "output_dir": output_dir,
        "repository_root": tmp_path,
    }


def _rebuild(fixture: dict[str, Any]) -> dict[str, object]:
    return REBUILD._rebuild_paths(
        output_dir=fixture["output_dir"],
        campaign_provenance_path=fixture["campaign_provenance_path"],
        candidate_placements=fixture["inputs"]["candidate_placements"],
        canonical_rules=fixture["inputs"]["canonical_rules"],
        mandatory_instances=fixture["inputs"]["mandatory_instances"],
        computation=fixture["computation"],
        expectation=fixture["expectation"],
        run_nonce="tiny-rebuild-run",
        parameters={"solver_substitute": "one-variable-ghost-model"},
        created_at_utc="2026-08-02T23:30:00Z",
    )


def _assert_no_rebuild_outputs(fixture: dict[str, Any]) -> None:
    for name in (
        "cut-free-model.bin",
        "incumbent.json",
        "rebuilt-model-metadata.json",
        "rebuild-result.json",
    ):
        assert not (fixture["output_dir"] / name).exists()


def test_tiny_computation_uses_canonical_production_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    monkeypatch.chdir(fixture["repository_root"])

    record = _rebuild(fixture)

    model_raw = (fixture["output_dir"] / "cut-free-model.bin").read_bytes()
    assert model_raw == fixture["computation"].model.SerializeToString(deterministic=True)
    incumbent_raw = (fixture["output_dir"] / "incumbent.json").read_bytes()
    assert incumbent_raw == _canonical(fixture["computation"].incumbent)
    metadata = json.loads((fixture["output_dir"] / "rebuilt-model-metadata.json").read_bytes())
    result = json.loads((fixture["output_dir"] / "rebuild-result.json").read_bytes())
    assert metadata["schema_version"] == ADMISSION.METADATA_SCHEMA
    assert metadata["created_at_utc"] == result["created_at_utc"] == "2026-08-02T23:30:00Z"
    assert metadata["campaign_provenance"] == fixture["campaign_provenance"]
    assert metadata["model_identity"] == record["cut_free_model_identity"]
    assert result == record
    ADMISSION._parse_model(model_raw, fixture["expectation"])
    metadata_snapshot = ADMISSION.snapshot_regular(
        fixture["output_dir"] / "rebuilt-model-metadata.json",
        max_bytes=ADMISSION.MAX_JSON_BYTES,
        label="real rebuild writer metadata",
    )
    validated_metadata = ADMISSION._validate_metadata(
        metadata_snapshot,
        campaign_provenance=fixture["campaign_provenance"],
        model_identity=record["cut_free_model_identity"],
        expectation=fixture["expectation"],
    )
    assert validated_metadata["input_identities"] == fixture["campaign_provenance"]["input_identities"]
    assert record["observed"] == {
        "incumbent_assignment_count": 1,
        "incumbent_sha256": fixture["expectation"].incumbent_sha256,
        "model_constraint_count": 0,
        "model_proto_sha256": fixture["expectation"].historical_model_text_sha256,
        "model_variable_count": 1,
    }
    assert record["claim_boundary"]["authorizing"] is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("model_variable_count", 2, "did not reproduce"),
        ("model_constraint_count", 1, "did not reproduce"),
        ("incumbent_sha256", "0" * 64, "did not reproduce"),
        ("incumbent_assignment_count", 2, "did not reproduce"),
    ),
)
def test_expectation_drift_fails_before_any_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["expectation"] = replace(fixture["expectation"], **{field: value})
    monkeypatch.chdir(fixture["repository_root"])

    with pytest.raises(REBUILD.BaselineRebuildError, match=message):
        _rebuild(fixture)

    _assert_no_rebuild_outputs(fixture)


def test_solver_solution_length_fails_before_any_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["computation"] = replace(fixture["computation"], solution_values=())
    monkeypatch.chdir(fixture["repository_root"])

    with pytest.raises(REBUILD.BaselineRebuildError, match="solver response length"):
        _rebuild(fixture)

    _assert_no_rebuild_outputs(fixture)


def test_output_with_extra_child_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    (fixture["output_dir"] / "unexpected.txt").write_text("stray\n", encoding="utf-8")
    monkeypatch.chdir(fixture["repository_root"])

    with pytest.raises(REBUILD.BaselineRebuildError, match="only campaign-provenance"):
        _rebuild(fixture)

    _assert_no_rebuild_outputs(fixture)


def test_campaign_provenance_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    provenance = fixture["campaign_provenance_path"]
    detached = provenance.with_name("detached-provenance.json")
    provenance.rename(detached)
    provenance.symlink_to(detached)
    monkeypatch.chdir(fixture["repository_root"])

    with pytest.raises(REBUILD.BaselineRebuildError, match="campaign provenance failed closed"):
        _rebuild(fixture)

    _assert_no_rebuild_outputs(fixture)


def test_output_directory_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    output = fixture["output_dir"]
    detached = fixture["campaign_dir"] / "detached-baseline"
    output.rename(detached)
    output.symlink_to(detached, target_is_directory=True)
    monkeypatch.chdir(fixture["repository_root"])

    with pytest.raises(REBUILD.BaselineRebuildError, match="symlink path component"):
        _rebuild(fixture)


def test_noncanonical_provenance_location_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    other = fixture["campaign_dir"] / "prospective-ab16" / "other" / "campaign-provenance.json"
    _write(other, fixture["campaign_provenance_path"].read_bytes())
    fixture["campaign_provenance_path"] = other
    monkeypatch.chdir(fixture["repository_root"])

    with pytest.raises(REBUILD.BaselineRebuildError, match="canonical output child"):
        _rebuild(fixture)

    _assert_no_rebuild_outputs(fixture)


def test_canonical_writer_never_overwrites_existing_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    monkeypatch.chdir(fixture["repository_root"])
    context = REBUILD._prepare_rebuild_context(
        output_dir=fixture["output_dir"],
        campaign_provenance_path=fixture["campaign_provenance_path"],
        strict_inputs=fixture["inputs"],
    )
    publish = {
        "context": context,
        "computation": fixture["computation"],
        "expectation": fixture["expectation"],
        "run_nonce": "tiny-rebuild-run",
        "parameters": {"solver_substitute": "one-variable-ghost-model"},
        "created_at_utc": "2026-08-02T23:30:00Z",
    }
    REBUILD._publish_rebuild(**publish)
    original = (fixture["output_dir"] / "cut-free-model.bin").read_bytes()

    with pytest.raises(REBUILD.BaselineRebuildError, match="already exists"):
        REBUILD._publish_rebuild(**publish)

    assert (fixture["output_dir"] / "cut-free-model.bin").read_bytes() == original
