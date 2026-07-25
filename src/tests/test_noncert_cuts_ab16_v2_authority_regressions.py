from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import stat
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = _load(
    "noncert_cuts_ab16_campaign_bootstrap_v2_regression",
    TOOLS / "ab16_campaign_bootstrap_v2.py",
)
RESOURCE = _load(
    "noncert_cuts_ab16_resource_verifier_v2_regression",
    TOOLS / "organic_resource_verifier_v2.py",
)
TERMINAL = _load(
    "noncert_cuts_ab16_terminal_gate_v2_regression",
    TOOLS / "ab16_terminal_gate_v2.py",
)
TERMINAL_V1_FIXTURE = _load(
    "noncert_cuts_ab16_terminal_gate_v1_fixture_regression",
    ROOT / "src/tests/test_noncert_cuts_ab16_terminal_gate_v1.py",
)


def _regular(path: Path, raw: bytes, *, mode: int = 0o444) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(mode)
    snapshot = BOOTSTRAP.authority.snapshot_regular(path)
    return {
        "mode": stat.S_IMODE(snapshot.stat_result.st_mode),
        **BOOTSTRAP.authority.detached_identity(snapshot),
    }


def _full(path: Path) -> dict[str, object]:
    return dict(BOOTSTRAP.authority.full_identity(BOOTSTRAP.authority.snapshot_regular(path)))


def _manager_epoch(tmp_path: Path) -> dict[str, object]:
    manager = Path(
        _regular(
            tmp_path / "tools/systemd",
            b"fixture systemd manager\n",
            mode=0o755,
        )["path"]
    )
    python = Path(
        _regular(
            tmp_path / "tools/python3.13",
            b"fixture Python\n",
            mode=0o755,
        )["path"]
    )
    sudo = Path(
        _regular(
            tmp_path / "tools/sudo",
            b"fixture sudo\n",
            mode=0o755,
        )["path"]
    )
    busctl = Path(
        _regular(
            tmp_path / "tools/busctl",
            b"fixture busctl\n",
            mode=0o755,
        )["path"]
    )
    attestor = BOOTSTRAP.V4_RESEARCH_DIR / "manager_attestor_v4.py"
    value = {
        "attestation_toolchain": {
            "attestor": _full(attestor),
            "python": _full(python),
            "sudo": _full(sudo),
        },
        "attestor_ast_audit": BOOTSTRAP.authority.audit_attestor_source(attestor.read_bytes()),
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.77",
        "manager_executable": _full(manager),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": _full(busctl)},
        "schema": BOOTSTRAP.authority.MANAGER_EPOCH_SCHEMA,
    }
    BOOTSTRAP.authority.validate_manager_epoch(value)
    return value


def _gate_a_record(
    tmp_path: Path,
    *,
    campaign_dir: Path,
    planned_digest: str,
    manager_epoch: dict[str, object],
) -> tuple[dict[str, object], dict[str, Path]]:
    evidence_paths: dict[str, Path] = {}
    evidence: dict[str, dict[str, object]] = {}
    for field in (
        "disposable_authority_ready_identity",
        "disposable_detached_replay_identity",
        "full_preflight_receipt_identity",
        "history_freeze_replay_identity",
        "reference_capability_identity",
        "reference_capability_transcript_identity",
    ):
        path = tmp_path / "gate-a-evidence" / f"{field}.json"
        evidence_paths[field] = path
        evidence[field] = _regular(
            path,
            json.dumps({"field": field}, sort_keys=True).encode(),
        )
    record: dict[str, object] = {
        "approval_id": "gate-a-fixture-v2",
        "arm_launch_authorized": False,
        "created_at_utc": "2026-07-24T00:00:00Z",
        "decision": "PASS",
        **evidence,
        "formal_campaign_creation_authorized": False,
        "gate": "A",
        "manager_epoch": manager_epoch,
        "offline_candidate_only": True,
        "planned_source_set_digest": planned_digest,
        "purpose": BOOTSTRAP.GATE_A_PURPOSE,
        "repository_head": HEAD,
        "repository_root": str(tmp_path / "repository"),
        "run_nonce": campaign_dir.name,
        "schema_version": BOOTSTRAP.GATE_A_SCHEMA,
        "target_campaign_dir": str(campaign_dir),
    }
    BOOTSTRAP._validate_gate_a(record)  # noqa: SLF001
    return record, evidence_paths


def _planned_sources(
    tmp_path: Path,
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, Path],
    dict[str, Path],
    dict[str, Path],
]:
    planned: dict[str, dict[str, object]] = {}
    scripts: dict[str, Path] = {}
    systems: dict[str, Path] = {}
    strict: dict[str, Path] = {}
    for role in BOOTSTRAP.SCRIPT_TOOL_FILES:
        path = tmp_path / "planned/scripts" / f"{role}.py"
        _regular(path, f"# {role}\n".encode(), mode=0o444)
        scripts[role] = path
        planned[f"script.{role}"] = _full(path)
    for role in BOOTSTRAP.SYSTEM_TOOL_ROLES:
        path = tmp_path / "planned/system" / role
        _regular(path, f"{role}\n".encode(), mode=0o755)
        systems[role] = path
        planned[f"system.{role}"] = {
            **_full(path),
            "requested_path": str(path),
        }
    for role in BOOTSTRAP.STRICT_INPUT_ROLES:
        path = tmp_path / "planned/inputs" / role
        _regular(path, f"{role}\n".encode(), mode=0o444)
        strict[role] = path
        planned[f"input.{role}"] = _full(path)
    return planned, scripts, systems, strict


def _write_authority_json(path: Path, value: object) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    return BOOTSTRAP.authority.write_exclusive(
        path,
        BOOTSTRAP.authority.canonical_json(value),
    )


def test_gate_a_evidence_mutation_fails_before_campaign_creation(
    tmp_path: Path,
) -> None:
    (tmp_path / "campaigns").mkdir()
    (tmp_path / "repository").mkdir()
    campaign = tmp_path / "campaigns/run-gate-a-mutation-v2"
    epoch = _manager_epoch(tmp_path)
    gate_a, evidence_paths = _gate_a_record(
        tmp_path,
        campaign_dir=campaign,
        planned_digest="a" * 64,
        manager_epoch=epoch,
    )
    gate_a_path = tmp_path / "gate-a.json"
    _write_authority_json(gate_a_path, gate_a)

    mutated = evidence_paths["disposable_detached_replay_identity"]
    mutated.chmod(0o644)
    mutated.write_bytes(b'{"field":"mutated"}')
    mutated.chmod(0o444)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="bytes drifted"):
        BOOTSTRAP.build_gate_a_candidate(
            output_path=tmp_path / "candidate.json",
            gate_a_receipt=gate_a_path,
            repository_root=tmp_path / "repository",
            target_campaign_dir=campaign,
            strict_input_paths={},
            system_tool_paths={},
        )
    assert not campaign.exists()
    assert not (tmp_path / "candidate.json").exists()


def test_current_manager_epoch_drift_fails_before_campaign_mkdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "campaigns").mkdir()
    (tmp_path / "repository").mkdir()
    campaign = tmp_path / "campaigns/run-manager-drift-v2"
    planned, scripts, systems, strict = _planned_sources(tmp_path)
    digest = BOOTSTRAP._source_set_digest(planned)  # noqa: SLF001
    epoch = _manager_epoch(tmp_path)
    gate_a, _ = _gate_a_record(
        tmp_path,
        campaign_dir=campaign,
        planned_digest=digest,
        manager_epoch=epoch,
    )
    gate_a_path = tmp_path / "gate-a.json"
    gate_a_identity = _write_authority_json(gate_a_path, gate_a)

    monkeypatch.setattr(
        BOOTSTRAP,
        "_planned_source_identities",
        lambda **_kwargs: (planned, scripts, systems, strict),
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_observe_repository_head",
        lambda *_args, **_kwargs: HEAD,
    )
    candidate_result = BOOTSTRAP.build_gate_a_candidate(
        output_path=tmp_path / "candidate.json",
        gate_a_receipt=gate_a_path,
        repository_root=tmp_path / "repository",
        target_campaign_dir=campaign,
        strict_input_paths={},
        system_tool_paths={},
    )
    gate_b = {
        "approval_id": "gate-b-fixture-v2",
        "arm_launch_authorized": False,
        "candidate_identity": candidate_result["candidate_identity"],
        "created_at_utc": "2026-07-24T00:01:00Z",
        "decision": "APPROVED",
        "formal_campaign_creation_authorized": True,
        "gate": "B",
        "gate_a_receipt_identity": gate_a_identity,
        "planned_source_set_digest": digest,
        "purpose": BOOTSTRAP.GATE_B_PURPOSE,
        "repository_head": HEAD,
        "repository_root": str(tmp_path / "repository"),
        "run_nonce": campaign.name,
        "schema_version": BOOTSTRAP.GATE_B_SCHEMA,
        "target_campaign_dir": str(campaign),
    }
    gate_b_path = tmp_path / "gate-b.json"
    _write_authority_json(gate_b_path, gate_b)
    drifted_epoch = copy.deepcopy(epoch)
    drifted_epoch["boot_id"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_kwargs: {
            "manager_epoch": drifted_epoch,
            "transcript": {},
        },
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_check_epoch_toolchain",
        lambda *_args, **_kwargs: {},
    )

    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="current manager/boot epoch differs",
    ):
        BOOTSTRAP.bootstrap_campaign(
            campaign_dir=campaign,
            repository_root=tmp_path / "repository",
            gate_a_receipt=gate_a_path,
            offline_candidate=tmp_path / "candidate.json",
            gate_b_approval=gate_b_path,
            strict_input_paths={},
            system_tool_paths={},
        )
    assert not campaign.exists()


def _history_authority(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    repository = tmp_path / "history-repository"
    member_path = repository / "frozen/member.txt"
    member_identity = _regular(member_path, b"immutable history\n")
    manifest = {
        "created_at_utc": "2026-07-24T00:00:00Z",
        "file_count": 1,
        "files": [
            {
                **member_identity,
                "path": "frozen/member.txt",
            }
        ],
        "frozen_roots": ["frozen"],
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_FREEZE",
        "repository_head": HEAD,
        "repository_root": str(repository),
        "schema_version": ("noncert-cuts-ab16-terminal-reference-history-freeze-v1"),
        "v1_source_glob": ["frozen/*"],
    }
    manifest_path = tmp_path / "history-manifest.json"
    manifest_path.write_bytes(
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    manifest_path.chmod(0o444)
    _raw, manifest_identity = RESOURCE.snapshot_bytes(manifest_path)
    receipt = {
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
        },
        "file_count": 1,
        "manifest_identity": manifest_identity,
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY",
        "schema_version": ("noncert-cuts-ab16-terminal-reference-history-replay-v1"),
        "status": "PASS",
        "verdict": "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS",
    }
    receipt_path = tmp_path / "history-receipt.json"
    receipt_path.write_bytes(RESOURCE.canonical_json_bytes(receipt))
    receipt_path.chmod(0o444)
    _raw, receipt_identity = RESOURCE.snapshot_bytes(receipt_path)
    pre_run = {
        "history_freeze_replay_identity": receipt_identity,
        "repository_head": HEAD,
        "repository_root": str(repository),
    }
    return pre_run, manifest_identity


@pytest.mark.parametrize(
    ("execution_class", "manifest_role"),
    [
        ("DISPOSABLE_LIVE_DRILL", "input.history_freeze_manifest"),
        ("FORMAL_AB16", "history_freeze_manifest"),
    ],
)
def test_history_freeze_role_is_execution_class_specific_and_source_bound(
    tmp_path: Path,
    execution_class: str,
    manifest_role: str,
) -> None:
    pre_run, manifest_identity = _history_authority(tmp_path)
    pre_run["execution_class"] = execution_class
    RESOURCE._replay_history_freeze(  # noqa: SLF001
        pre_run=pre_run,
        strict_inputs={manifest_role: manifest_identity},
    )

    wrong_role = "history_freeze_manifest" if manifest_role.startswith("input.") else "input.history_freeze_manifest"
    with pytest.raises(
        RESOURCE.VerificationError,
        match="receipt semantics drifted",
    ):
        RESOURCE._replay_history_freeze(  # noqa: SLF001
            pre_run=pre_run,
            strict_inputs={wrong_role: manifest_identity},
        )

    source = Path(str(manifest_identity["path"]))
    copied = tmp_path / "copied-history-manifest.json"
    copied.write_bytes(source.read_bytes())
    copied.chmod(0o444)
    _raw, copied_identity = RESOURCE.snapshot_bytes(copied)
    with pytest.raises(
        RESOURCE.VerificationError,
        match="receipt semantics drifted",
    ):
        RESOURCE._replay_history_freeze(  # noqa: SLF001
            pre_run=pre_run,
            strict_inputs={manifest_role: copied_identity},
        )


def _snapshot_identity(tmp_path: Path, name: str) -> dict[str, object]:
    path = tmp_path / "resource-identities" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(RESOURCE.canonical_json_bytes({"name": name}))
    path.chmod(0o444)
    _raw, identity = RESOURCE.snapshot_bytes(path)
    return identity


def _terminal_inputs(tmp_path: Path) -> dict[str, object]:
    values = TERMINAL_V1_FIXTURE._arm_inputs()  # noqa: SLF001
    preterminal_identity = _snapshot_identity(tmp_path, "preterminal-receipt")
    terminal_identity = _snapshot_identity(tmp_path, "terminal-receipt")
    verifier_identity = _snapshot_identity(tmp_path, "resource-verifier")
    reference_acquisition = _snapshot_identity(
        tmp_path,
        "reference-acquisition",
    )
    reference_release = _snapshot_identity(tmp_path, "reference-release")
    values["resource_preterminal_identity"] = dict(preterminal_identity)
    values["resource_receipt_identity"] = dict(terminal_identity)
    values["resource_verifier_tool_identity"] = dict(verifier_identity)
    for receipt_name in (
        "resource_preterminal_receipt",
        "replayed_resource_preterminal_receipt",
    ):
        receipt = values[receipt_name]
        assert isinstance(receipt, dict)
        receipt["schema_version"] = TERMINAL.RESOURCE_PRETERMINAL_SCHEMA
        receipt["verifier_tool_identity"] = dict(verifier_identity)
    for receipt_name in (
        "resource_receipt",
        "replayed_resource_receipt",
    ):
        receipt = values[receipt_name]
        assert isinstance(receipt, dict)
        receipt["schema_version"] = TERMINAL.RESOURCE_SCHEMA
        receipt["resource_verification_identity"] = dict(preterminal_identity)
        receipt["reference_acquisition_identity"] = dict(reference_acquisition)
        receipt["reference_release_identity"] = dict(reference_release)
        receipt["verifier_tool_identity"] = dict(verifier_identity)
    return values


def test_terminal_gate_accepts_mode_bearing_snapshot_and_rejects_drift(
    tmp_path: Path,
) -> None:
    values = _terminal_inputs(tmp_path)
    result = TERMINAL.build_arm_gate(**values)
    assert result["status"] == "PASS"
    assert result["resource_preterminal_identity"]["mode"] == 0o444
    assert result["resource_receipt_identity"]["mode"] == 0o444

    for field, replacement in (("mode", 0o400), ("sha256", "f" * 64)):
        drifted = copy.deepcopy(values)
        outer = dict(drifted["resource_preterminal_identity"])
        outer[field] = replacement
        drifted["resource_preterminal_identity"] = outer
        with pytest.raises(
            TERMINAL.GateError,
            match="identity chain failed",
        ):
            TERMINAL.build_arm_gate(**drifted)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function not found: {name}")


def _assigned_literal(
    function: ast.FunctionDef,
    name: str,
) -> object:
    for node in ast.walk(function):
        target: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"assignment not found: {name}")


def test_formal_pre_run_v2_shape_preregisters_and_replays_references() -> None:
    source = (TOOLS / "ab16_authority_v2.py").read_text()
    tree = ast.parse(source)
    builder = _function(tree, "_build_pre_run_candidate_unprotected")
    output_names = _assigned_literal(builder, "output_names")
    assert isinstance(output_names, dict)
    assert {
        "abort_reference_release",
        "reference_acquisition",
        "reference_release",
    }.issubset(output_names)
    phases = _assigned_literal(builder, "phases")
    assert phases == (
        "launch",
        "preterminal",
        "reference-acquire",
        "release",
        "terminal-first",
        "terminal-stable",
        "reference-release",
        "cleanup",
        "detached-replay",
    )

    record_keys: set[str] | None = None
    for node in ast.walk(builder):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "record"
            and isinstance(node.value, ast.Dict)
        ):
            record_keys = {
                key.value for key in node.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            break
    assert record_keys is not None
    assert {
        "history_freeze_replay_identity",
        "reference_capability_identity",
        "reference_capability_transcript_identity",
        "reference_contract",
    }.issubset(record_keys)

    replay = _function(tree, "_replay_selected_arm_evidence")
    detached_calls = [
        node
        for node in ast.walk(replay)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "verify_detached"
    ]
    assert len(detached_calls) == 1
    keywords = {keyword.arg for keyword in detached_calls[0].keywords}
    assert {"reference_acquisition", "reference_release"}.issubset(keywords)
