from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import ModuleType
import zipfile

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
AUTHORITY = _load(
    "noncert_cuts_ab16_authority_v2_regression",
    TOOLS / "ab16_authority_v2.py",
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


def _top_level_literal(path: Path, name: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path.name} does not define literal {name}")


def test_project_lock_registers_one_exact_ab16_formal_cohort() -> None:
    lock = (ROOT / "PROJECT_LOCK.md").read_text(encoding="utf-8")
    section = lock.split(
        "### 3C. AB16 Gate-B and formal-campaign research-only authority boundary",
        1,
    )[1].split("## 4. Forbidden Changes", 1)[0]
    qualification = TOOLS / "ab16_gate_b_qualification_v1.py"
    launch = TOOLS / "ab16_formal_launch_validator_v1.py"
    success = TOOLS / "ab16_formal_success_verifier_v1.py"
    closeout = TOOLS / "ab16_outer_closeout_state_v1.py"
    accepted = {
        BOOTSTRAP.GATE_A_SCHEMA,
        BOOTSTRAP.CANDIDATE_SCHEMA,
        BOOTSTRAP.FINAL_FULL_PREFLIGHT_SCHEMA,
        BOOTSTRAP.GATE_B_SCHEMA,
        BOOTSTRAP.GATE_B_EPOCH_SCHEMA,
        BOOTSTRAP.CAPTURE_SCHEMA,
        BOOTSTRAP.RESULT_SCHEMA,
        BOOTSTRAP.PATH_PREREGISTRATION_SCHEMA,
        BOOTSTRAP.REPOSITORY_SNAPSHOT_SCHEMA,
        BOOTSTRAP.SNAPSHOT_MATERIALIZATION_SCHEMA,
        BOOTSTRAP.EXTERNAL_PLATFORM_SCHEMA,
        RESOURCE.HISTORY_FREEZE_SCHEMA,
        RESOURCE.HISTORY_REPLAY_SCHEMA,
        _top_level_literal(qualification, "QUALIFICATION_SCHEMA"),
        _top_level_literal(qualification, "RESOURCE_GATE_SCHEMA"),
        _top_level_literal(qualification, "OWNER_REQUEST_SCHEMA"),
        _top_level_literal(qualification, "OWNER_RESPONSE_SCHEMA"),
        _top_level_literal(qualification, "OWNER_RELEASE_SCHEMA"),
        _top_level_literal(qualification, "HANDOFF_REQUEST_SCHEMA"),
        _top_level_literal(qualification, "HANDOFF_RESPONSE_SCHEMA"),
        _top_level_literal(launch, "FORMAL_CONTEXT_SCHEMA"),
        _top_level_literal(launch, "FORMAL_ADMISSION_SCHEMA"),
        _top_level_literal(launch, "FORMAL_SELECTION_SCHEMA"),
        _top_level_literal(launch, "GUARDIAN_READY_SCHEMA"),
        _top_level_literal(launch, "ATTEMPT_CONSUMPTION_SCHEMA"),
        AUTHORITY.CONTINUATION_SCHEMA,
        AUTHORITY.BASELINE_ADMISSION_SCHEMA,
        AUTHORITY.COMMON_PRESTATE_SCHEMA,
        AUTHORITY.MANIFEST_SCHEMA,
        AUTHORITY.SUITE_SELECTION_SCHEMA,
        AUTHORITY.ARM_BINDING_SCHEMA,
        AUTHORITY.PRE_RUN_AUTHORITY_SCHEMA,
        AUTHORITY.ARM_SELECTION_SCHEMA,
        AUTHORITY.ARM_CONSUMPTION_SCHEMA,
        AUTHORITY.CAMPAIGN_STOP_SCHEMA,
        _top_level_literal(success, "SUCCESS_RECEIPT_SCHEMA"),
        _top_level_literal(success, "INCOMPLETE_RECEIPT_SCHEMA"),
        _top_level_literal(success, "FAILURE_RELEASE_SCHEMA"),
        _top_level_literal(success, "FAILURE_TERMINAL_RELEASE_SCHEMA"),
        _top_level_literal(success, "GUARDIAN_LOCK_CLOSE_SCHEMA"),
        _top_level_literal(success, "CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA"),
        _top_level_literal(closeout, "MARKERLESS_SCHEMA"),
        _top_level_literal(closeout, "INCOMPLETE_SCHEMA"),
        _top_level_literal(closeout, "REFERENCE_SCHEMA"),
        _top_level_literal(closeout, "HOLD_SCHEMA"),
        _top_level_literal(closeout, "HOLD_CLEAR_SCHEMA"),
        _top_level_literal(closeout, "LOCK_RELEASE_SCHEMA"),
    }
    missing = sorted(schema for schema in accepted if f"`{schema}`" not in section)
    assert missing == []
    assert "Schema names cannot be independently selected, relabeled, or mixed" in section
    assert "cannot be coerced into this cohort" in section
    assert "The main checkout is a control plane" in section
    assert "Tracked state remains `U=(1188,18)` and" in section
    assert "`L=absent`" in section


def test_project_lock_pins_terminal_reference_history_archive_bridge() -> None:
    lock = (ROOT / "PROJECT_LOCK.md").read_text(encoding="utf-8")
    section = lock.split(
        "### 3C. AB16 Gate-B and formal-campaign research-only authority boundary",
        1,
    )[1].split("## 4. Forbidden Changes", 1)[0]
    history_row = next(
        line
        for line in section.splitlines()
        if line.startswith("  | Gate-A terminal-reference history |")
    )
    assert f"`{RESOURCE.HISTORY_FREEZE_SCHEMA}`" in history_row
    assert f"`{RESOURCE.HISTORY_REPLAY_SCHEMA}`" in history_row
    assert (
        "`noncert-cuts-ab16-terminal-reference-history-replay-v1`"
        not in history_row
    )
    for fixed_identity in (
        RESOURCE.HISTORY_FREEZE_MANIFEST_SHA256,
        RESOURCE.HISTORY_FREEZE_HEAD,
        RESOURCE.HISTORY_SOURCE_COMMIT,
        RESOURCE.HISTORY_SOURCE_TREE,
    ):
        assert f"`{fixed_identity}`" in section
    for fixed_count in (
        f"`{RESOURCE.HISTORY_ARTIFACT_COUNT + RESOURCE.HISTORY_SOURCE_COUNT}`",
        f"`{RESOURCE.HISTORY_ARTIFACT_COUNT}`",
        f"`{RESOURCE.HISTORY_SOURCE_COUNT}`",
    ):
        assert fixed_count in section
    assert "whose sole parent is the" in section
    assert "`v1_source_glob` is not re-expanded" in section
    assert "is not accepted by the fresh cohort" in section
    assert "grants no new experiment," in section


def test_formal_orchestrator_outer_module_entry_is_cache_free() -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            (
                "docs.research.noncert_cuts_ab16_20260724."
                "ab16_formal_orchestrator_v1"
            ),
            "--help",
        ],
        check=False,
        cwd=ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert completed.returncode == 0
    assert b"--campaign-dir" in completed.stdout
    assert completed.stderr == b""


def test_formal_orchestrator_is_one_package_and_loader_authority_source() -> None:
    assert (
        BOOTSTRAP.AB16_SCRIPT_TOOL_FILES["ab16_formal_orchestrator_v1"]
        == "ab16_formal_orchestrator_v1.py"
    )
    assert "tool.ab16_formal_orchestrator_v1.py" in AUTHORITY.REQUIRED_PACKAGE_ROLES
    assert AUTHORITY.FORMAL_ROLE_SOURCES["formal-orchestrator"] == (
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_orchestrator_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_orchestrator_v1.py",
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


def _gate_b_publisher(
    output_path: Path,
    *,
    sequence: int = 2,
    session_id: str = "a" * 64,
) -> dict[str, object]:
    return BOOTSTRAP._gate_b_publisher_for_parent(  # noqa: SLF001
        output_path,
        sequence=sequence,
        session_id=session_id,
    )


def test_gate_b_renderer_uses_live_planned_identity_and_joins_staged_bytes(
    tmp_path: Path,
) -> None:
    raw = b"print('selected Gate-B renderer')\n"
    planned = {
        "mode": 0o644,
        "path": str(tmp_path / "live/ab16_campaign_bootstrap_v2.py"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    staged = {
        "device": 1,
        "inode": 2,
        "mode": 0o444,
        "path": str(tmp_path / "package-source-staging/script.ab16_campaign_bootstrap_v2.py"),
        "sha256": planned["sha256"],
        "size_bytes": planned["size_bytes"],
    }
    assert AUTHORITY._join_gate_b_renderer_identity(planned, staged) == planned  # noqa: SLF001

    for field, replacement in (("sha256", "f" * 64), ("size_bytes", len(raw) + 1)):
        drifted = copy.deepcopy(staged)
        drifted[field] = replacement
        with pytest.raises(
            AUTHORITY.AuthorityError,
            match="live/staged renderer identity drifted",
        ):
            AUTHORITY._join_gate_b_renderer_identity(planned, drifted)  # noqa: SLF001


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
    final_identity = _regular(
        tmp_path / "gate-b-final.json",
        BOOTSTRAP.authority.canonical_json({}),
    )
    epoch_path = tmp_path / "gate-b-epoch.json"
    epoch_identity = _regular(
        epoch_path,
        BOOTSTRAP.authority.canonical_json(
            {
                "manager_epoch": epoch,
                "publisher": _gate_b_publisher(epoch_path, sequence=1),
            }
        ),
    )
    gate_b_path = tmp_path / "gate-b.json"
    gate_b = {
        "approval_id": "gate-b-fixture-v2",
        "arm_launch_authorized": False,
        "candidate_identity": candidate_result["candidate_identity"],
        "created_at_utc": "2026-07-24T00:01:00Z",
        "decision": "APPROVED",
        "final_full_preflight_receipt_identity": final_identity,
        "formal_campaign_creation_authorized": True,
        "gate": "B",
        "gate_a_receipt_identity": gate_a_identity,
        "gate_b_epoch_observation_identity": epoch_identity,
        "planned_source_set_digest": digest,
        "publisher": _gate_b_publisher(gate_b_path),
        "purpose": BOOTSTRAP.GATE_B_PURPOSE,
        "repository_head": HEAD,
        "repository_root": str(tmp_path / "repository"),
        "run_nonce": campaign.name,
        "schema_version": BOOTSTRAP.GATE_B_SCHEMA,
        "target_campaign_dir": str(campaign),
    }
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
    monkeypatch.setattr(
        BOOTSTRAP,
        "_validate_final_full_preflight",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_validate_gate_b_epoch_observation",
        lambda value, **_kwargs: value,
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


def _gate_b_record(tmp_path: Path) -> dict[str, object]:
    campaign = tmp_path / "campaigns/run-gate-b-evidence-v2"
    approval_path = tmp_path / "gate-b/approval.json"
    candidate = _regular(tmp_path / "gate-b/candidate.json", b"{}\n")
    gate_a = _regular(tmp_path / "gate-b/gate-a.json", b"{}\n")
    return {
        "approval_id": "gate-b-evidence-v2", "arm_launch_authorized": False,
        "candidate_identity": {key: candidate[key] for key in ("path", "sha256", "size_bytes")},
        "created_at_utc": "2026-07-24T00:01:00Z", "decision": "APPROVED",
        "final_full_preflight_receipt_identity": _regular(tmp_path / "gate-b/final.json", b"{}\n"),
        "formal_campaign_creation_authorized": True, "gate": "B",
        "gate_a_receipt_identity": {key: gate_a[key] for key in ("path", "sha256", "size_bytes")},
        "gate_b_epoch_observation_identity": _regular(tmp_path / "gate-b/epoch.json", b"{}\n"),
        "planned_source_set_digest": "a" * 64,
        "publisher": _gate_b_publisher(approval_path),
        "purpose": BOOTSTRAP.GATE_B_PURPOSE,
        "repository_head": HEAD, "repository_root": str(tmp_path / "repository"),
        "run_nonce": campaign.name, "schema_version": BOOTSTRAP.GATE_B_SCHEMA,
        "target_campaign_dir": str(campaign),
    }


@pytest.mark.parametrize(
    ("field", "mutation"),
    [
        ("final_full_preflight_receipt_identity", "missing"),
        ("gate_b_epoch_observation_identity", "missing"),
        ("final_full_preflight_receipt_identity", "drift"),
        ("gate_b_epoch_observation_identity", "drift"),
    ],
)
def test_gate_b_independent_evidence_identity_is_fail_closed(
    tmp_path: Path,
    field: str,
    mutation: str,
) -> None:
    record = _gate_b_record(tmp_path)
    if mutation == "missing":
        record.pop(field)
    else:
        identity = dict(record[field])
        identity["sha256"] = "f" * 64
        record[field] = identity
    with pytest.raises(BOOTSTRAP.BootstrapError):
        BOOTSTRAP._validate_gate_b(record)  # noqa: SLF001


def test_gate_b_v4_publisher_identity_and_schema_are_strict(
    tmp_path: Path,
) -> None:
    record = _gate_b_record(tmp_path)
    assert BOOTSTRAP._validate_gate_b(record) == record  # noqa: SLF001

    mutations: list[dict[str, object]] = []
    old_schema = copy.deepcopy(record)
    old_schema["schema_version"] = "noncert-cuts-ab16-bootstrap-gate-b-approval-v3"
    mutations.append(old_schema)
    missing = copy.deepcopy(record)
    missing.pop("publisher")
    mutations.append(missing)
    extra = copy.deepcopy(record)
    extra["unexpected"] = False
    mutations.append(extra)
    actor_drift = copy.deepcopy(record)
    actor_drift["publisher"]["actor"]["role"] = "AB16_FORMAL_SUPERVISOR"
    mutations.append(actor_drift)
    renderer_drift = copy.deepcopy(record)
    renderer_drift["publisher"]["renderer_source"]["sha256"] = "f" * 64
    mutations.append(renderer_drift)
    for changed in mutations:
        with pytest.raises(BOOTSTRAP.BootstrapError):
            BOOTSTRAP._validate_gate_b(changed)  # noqa: SLF001


def test_gate_b_epoch_v3_joins_one_live_owner_and_rejects_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    epoch = _manager_epoch(tmp_path)
    campaign = tmp_path / "campaigns/run-gate-b-epoch-v2"
    gate_a_identity = {
        key: value
        for key, value in _regular(tmp_path / "gate-b-epoch/gate-a.json", b"{}\n").items()
        if key in {"path", "sha256", "size_bytes"}
    }
    candidate_identity = {
        key: value
        for key, value in _regular(tmp_path / "gate-b-epoch/candidate.json", b"{}\n").items()
        if key in {"path", "sha256", "size_bytes"}
    }
    final_identity = _regular(tmp_path / "gate-b-epoch/final-full.json", b"{}\n")
    gate_a = {
        "manager_epoch": epoch,
        "planned_source_set_digest": "a" * 64,
        "repository_head": HEAD,
        "repository_root": str(tmp_path / "repository"),
        "run_nonce": campaign.name,
        "target_campaign_dir": str(campaign),
    }
    epoch_path = tmp_path / "gate-b-epoch/observation.json"
    record: dict[str, object] = {
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        },
        "candidate_identity": candidate_identity,
        "capture_transcript": {"fixture": "validated-by-focused-stub"},
        "created_at_utc": "2026-07-27T00:00:00Z",
        "final_full_preflight_receipt_identity": final_identity,
        "gate_a_receipt_identity": gate_a_identity,
        "manager_epoch": epoch,
        "planned_source_set_digest": gate_a["planned_source_set_digest"],
        "publisher": _gate_b_publisher(epoch_path, sequence=1),
        "purpose": BOOTSTRAP.GATE_B_EPOCH_PURPOSE,
        "repository_head": gate_a["repository_head"],
        "repository_root": gate_a["repository_root"],
        "run_nonce": gate_a["run_nonce"],
        "schema_version": BOOTSTRAP.GATE_B_EPOCH_SCHEMA,
        "status": "PASS",
        "target_campaign_dir": gate_a["target_campaign_dir"],
    }
    monkeypatch.setattr(
        BOOTSTRAP.authority,
        "validate_manager_epoch_capture_transcript",
        lambda value, *, expected_epoch: (
            value,
            expected_epoch,
        ),
    )
    assert (
        BOOTSTRAP._validate_gate_b_epoch_observation(  # noqa: SLF001
            record,
            gate_a=gate_a,
            gate_a_identity=gate_a_identity,
            candidate_identity=candidate_identity,
            final_full_preflight_identity=final_identity,
        )
        == record
    )
    approval = _gate_b_record(tmp_path / "same-owner")
    assert approval["publisher"]["actor"] == record["publisher"]["actor"]
    assert (
        approval["publisher"]["qualification_session"]["session_id"]
        == record["publisher"]["qualification_session"]["session_id"]
    )

    mutations: list[dict[str, object]] = []
    old_schema = copy.deepcopy(record)
    old_schema["schema_version"] = "noncert-cuts-ab16-gate-b-epoch-observation-v2"
    mutations.append(old_schema)
    missing = copy.deepcopy(record)
    missing.pop("publisher")
    mutations.append(missing)
    extra = copy.deepcopy(record)
    extra["unexpected"] = False
    mutations.append(extra)
    actor_drift = copy.deepcopy(record)
    actor_drift["publisher"]["actor"]["pid_starttime"] = "1"
    mutations.append(actor_drift)
    upstream_drift = copy.deepcopy(record)
    upstream_drift["candidate_identity"]["sha256"] = "f" * 64
    mutations.append(upstream_drift)
    for changed in mutations:
        with pytest.raises(BOOTSTRAP.BootstrapError):
            BOOTSTRAP._validate_gate_b_epoch_observation(  # noqa: SLF001
                changed,
                gate_a=gate_a,
                gate_a_identity=gate_a_identity,
                candidate_identity=candidate_identity,
                final_full_preflight_identity=final_identity,
            )


def _repository_manifest(tmp_path: Path) -> dict[str, object]:
    tracked = b"from __future__ import annotations\n"
    candidate = b'{"placements":[]}\n'
    members: list[dict[str, object]] = [
        {
            "git_blob_oid": "1" * 40, "git_mode": "100644", "materialized_mode": 0o444,
            "path": "pkg/module.py", "raw_sha256": hashlib.sha256(tracked).hexdigest(),
            "size_bytes": len(tracked), "source_kind": "git_blob",
        },
        {
            "materialized_mode": 0o444, "package_role": "input.candidate_placements.json",
            "path": "data/preprocessed/candidate_placements.json",
            "raw_sha256": hashlib.sha256(candidate).hexdigest(), "size_bytes": len(candidate),
            "source_kind": "package_overlay",
        },
    ]
    return {
        "archive_descriptor": {
            "package_role": "input.ab16_repository_snapshot.zip",
            "sha256": "2" * 64,
            "size_bytes": 10,
        },
        "authority_scope": "AB16_RESEARCH_ONLY", "import_mode": "ordinary_pathfinder",
        "member_count": len(members), "members": members,
        "ordered_member_digest": hashlib.sha256(AUTHORITY.canonical_json(members)).hexdigest(),
        "repository_head": HEAD, "repository_tree": "3" * 40,
        "schema_version": AUTHORITY.REPOSITORY_SNAPSHOT_SCHEMA,
        "total_bytes": sum(member["size_bytes"] for member in members),
    }


def _zip_bytes(path: str, raw: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(path, raw)
    return output.getvalue()


def test_repository_snapshot_manifest_exact_member_and_overlay_contract(
    tmp_path: Path,
) -> None:
    record = _repository_manifest(tmp_path)
    assert AUTHORITY.validate_repository_snapshot_manifest(record) == record

    missing = copy.deepcopy(record)
    missing.pop("member_count")
    extra = copy.deepcopy(record)
    extra["unexpected"] = True
    no_overlay = copy.deepcopy(record)
    no_overlay["members"].pop()
    no_overlay.update(member_count=1, total_bytes=no_overlay["members"][0]["size_bytes"])
    no_overlay["ordered_member_digest"] = hashlib.sha256(AUTHORITY.canonical_json(no_overlay["members"])).hexdigest()
    mutations = [missing, extra, no_overlay]
    for field, replacement in (
        ("path", "data/preprocessed/other.json"),
        ("materialized_mode", 0o400),
    ):
        changed = copy.deepcopy(record)
        changed["members"][-1][field] = replacement
        changed["ordered_member_digest"] = hashlib.sha256(AUTHORITY.canonical_json(changed["members"])).hexdigest()
        mutations.append(changed)
    forbidden_overlay_source = copy.deepcopy(record)
    forbidden_overlay_source["members"][-1]["source_identity"] = {
        "mode": 0o444,
        "path": str(tmp_path / "candidate-source.json"),
        "sha256": "e" * 64,
        "size_bytes": 1,
    }
    forbidden_overlay_source["ordered_member_digest"] = hashlib.sha256(
        AUTHORITY.canonical_json(forbidden_overlay_source["members"])
    ).hexdigest()
    mutations.append(forbidden_overlay_source)
    for changed in mutations:
        with pytest.raises(AUTHORITY.AuthorityError):
            AUTHORITY.validate_repository_snapshot_manifest(changed)


def test_bootstrap_materializer_rejects_manifest_without_candidate_overlay(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "run-bootstrap-materializer-v1"
    payload = campaign / "campaign-authority/package/payload"
    payload.mkdir(parents=True)
    raw = b"tracked\n"
    archive_path = payload / BOOTSTRAP.SNAPSHOT_ARCHIVE_PACKAGE_ROLE
    archive_path.write_bytes(_zip_bytes("tracked.txt", raw))
    archive_path.chmod(0o444)
    candidate_path = payload / "input.candidate_placements.json"
    candidate_path.write_bytes(b"{}\n")
    candidate_path.chmod(0o444)
    members = [
        {
            "git_blob_oid": "1" * 40, "git_mode": "100644", "materialized_mode": 0o444,
            "path": "tracked.txt",
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw), "source_kind": "git_blob",
        }
    ]
    manifest = {
        **_repository_manifest(tmp_path),
        "archive_descriptor": {
            "package_role": BOOTSTRAP.SNAPSHOT_ARCHIVE_PACKAGE_ROLE,
            "sha256": BOOTSTRAP.authority.snapshot_regular(archive_path).sha256,
            "size_bytes": BOOTSTRAP.authority.snapshot_regular(archive_path).size,
        },
        "member_count": 1, "members": members,
        "ordered_member_digest": hashlib.sha256(BOOTSTRAP.authority.canonical_json(members)).hexdigest(),
        "total_bytes": len(raw),
    }
    manifest_path = payload / BOOTSTRAP.SNAPSHOT_MANIFEST_PACKAGE_ROLE
    manifest_path.write_bytes(BOOTSTRAP.authority.canonical_json(manifest))
    manifest_path.chmod(0o444)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="candidate overlay"):
        BOOTSTRAP._materialize_repository_snapshot(  # noqa: SLF001
            campaign_dir=campaign,
            package_dir=payload.parent,
            package_id="4" * 64,
            created_at_utc="2026-07-27T00:00:00Z",
        )


def _materialized_snapshot_fixture(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object], Path]:
    campaign = tmp_path / "run-snapshot-replay-v1"
    payload = campaign / "campaign-authority/package/payload"
    repository = campaign / "campaign-authority/source-snapshot-a001/repository"
    payload.mkdir(parents=True)
    (repository / "pkg").mkdir(parents=True)
    (repository / "data/preprocessed").mkdir(parents=True)
    tracked = b"from __future__ import annotations\n"
    candidate = b'{"placements":[]}\n'
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("pkg/module.py", tracked)
    archive_path = payload / "input.ab16_repository_snapshot.zip"
    candidate_path = payload / "input.candidate_placements.json"
    python_path = Path(os.path.realpath(sys.executable))
    for path, raw, mode in (
        (archive_path, archive_buffer.getvalue(), 0o444),
        (candidate_path, candidate, 0o444),
        (repository / "pkg/module.py", tracked, 0o444),
        (repository / "data/preprocessed/candidate_placements.json", candidate, 0o444),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(mode)
    manifest = _repository_manifest(tmp_path)
    archive_snapshot = AUTHORITY.snapshot_regular(archive_path)
    manifest["archive_descriptor"] = {
        "package_role": "input.ab16_repository_snapshot.zip",
        "sha256": archive_snapshot.sha256,
        "size_bytes": archive_snapshot.size_bytes,
    }
    manifest["ordered_member_digest"] = hashlib.sha256(AUTHORITY.canonical_json(manifest["members"])).hexdigest()
    manifest_path = payload / "input.ab16_repository_snapshot.json"
    manifest_path.write_bytes(AUTHORITY.canonical_json(manifest))
    manifest_path.chmod(0o444)
    platform = BOOTSTRAP._external_platform_record(  # noqa: SLF001
        repository_head=HEAD,
        python_identity=_full(python_path),
    )
    platform_path = payload / "input.ab16_external_platform_assumptions.json"
    platform_path.write_bytes(AUTHORITY.canonical_json(platform))
    platform_path.chmod(0o444)
    package_id = "4" * 64
    receipt = {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "candidate_identity": AUTHORITY.detached_identity(AUTHORITY.snapshot_regular(candidate_path)),
        "created_at_utc": "2026-07-27T00:00:00Z",
        "import_mode": "ordinary_pathfinder",
        "member_count": manifest["member_count"],
        "ordered_member_digest": manifest["ordered_member_digest"],
        "package_id": package_id,
        "repository_head": HEAD,
        "repository_tree": manifest["repository_tree"],
        "schema_version": AUTHORITY.SNAPSHOT_MATERIALIZATION_SCHEMA,
        "snapshot_archive_identity": AUTHORITY.detached_identity(
            AUTHORITY.snapshot_regular(archive_path)
        ),
        "snapshot_manifest_identity": AUTHORITY.detached_identity(AUTHORITY.snapshot_regular(manifest_path)),
        "snapshot_root": str(repository),
        "status": "PASS",
        "total_bytes": manifest["total_bytes"],
    }
    receipt_path = repository.parent / "materialization-receipt.json"
    receipt_path.write_bytes(AUTHORITY.canonical_json(receipt))
    receipt_path.chmod(0o444)
    for directory in sorted((path for path in repository.rglob("*") if path.is_dir()), reverse=True):
        directory.chmod(0o555)
    repository.chmod(0o555)
    bootstrap_source = TOOLS / "ab16_campaign_bootstrap_v2.py"
    bootstrap_payload = payload / "tool.ab16_campaign_bootstrap_v2.py"
    bootstrap_payload.write_bytes(bootstrap_source.read_bytes())
    bootstrap_payload.chmod(0o444)
    files = {
        path.name: AUTHORITY.snapshot_regular(path)
        for path in (
            archive_path,
            bootstrap_payload,
            candidate_path,
            manifest_path,
            platform_path,
        )
    }
    sources = {
        "input.ab16_repository_snapshot.zip": {"package_path": archive_path.name},
        "input.ab16_repository_snapshot.json": {"package_path": manifest_path.name},
        "input.ab16_external_platform_assumptions.json": {"package_path": platform_path.name},
        "input.candidate_placements.json": {"package_path": candidate_path.name},
        "tool.ab16_campaign_bootstrap_v2.py": {
            "package_path": bootstrap_payload.name,
            "source_identity": _full(bootstrap_source),
        },
    }
    root = {
        "authority_tools": {"python3_13": AUTHORITY.detached_identity(AUTHORITY.snapshot_regular(python_path))},
        "package": {"package_id": package_id},
        "repository_head": HEAD,
        "strict_inputs": {
            "ab16_external_platform_assumptions": AUTHORITY.detached_identity(files[platform_path.name]),
            "ab16_repository_snapshot": AUTHORITY.detached_identity(files[manifest_path.name]),
            "ab16_repository_snapshot_archive": AUTHORITY.detached_identity(files[archive_path.name]),
            "ab16_repository_snapshot_materialization": AUTHORITY.detached_identity(
                AUTHORITY.snapshot_regular(receipt_path)
            ),
        },
    }
    return {"directory": campaign, "root": root, "files": files, "sources": sources}, manifest, repository


@pytest.mark.parametrize(
    "mutation",
    [
        "legacy-schema",
        "legacy-two-fd",
        "selected-literal",
        "owner-driver",
        "dual-holder",
        "extra",
    ],
)
def test_external_platform_v2_rejects_legacy_and_identity_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    kwargs, _manifest, repository = _materialized_snapshot_fixture(tmp_path)
    platform_role = "ab16_external_platform_assumptions"
    platform_path = Path(kwargs["root"]["strict_inputs"][platform_role]["path"])
    try:
        replay = AUTHORITY._replay_repository_snapshot(**kwargs)  # noqa: SLF001
        platform = copy.deepcopy(replay["external_platform"])
        if mutation == "legacy-schema":
            platform["schema_version"] = "noncert-cuts-ab16-external-platform-assumptions-v1"
        elif mutation == "legacy-two-fd":
            platform["selected_byte_launch"]["direct_fd_map"] = {
                "loader": 4,
                "python": 3,
            }
            platform["selected_byte_launch"]["systemd_fd_map"] = {
                "loader": 4,
                "python": 3,
            }
            platform["selected_byte_launch"]["systemd_fd_names"] = [
                "ab16-python",
                "ab16-loader",
            ]
        elif mutation == "selected-literal":
            platform["selected_byte_launch"]["literal_identity"]["sha256"] = "f" * 64
        elif mutation == "owner-driver":
            platform["formal_launch_owner_driver"]["sha256"] = "f" * 64
        elif mutation == "dual-holder":
            platform["dual_holder_survival"]["single_holder_death_must_be_contained"] = False
        else:
            platform["unexpected"] = False
        platform_path.chmod(0o644)
        platform_path.write_bytes(AUTHORITY.canonical_json(platform))
        platform_path.chmod(0o444)
        snapshot = AUTHORITY.snapshot_regular(platform_path)
        kwargs["files"][platform_path.name] = snapshot
        kwargs["root"]["strict_inputs"][platform_role] = AUTHORITY.detached_identity(
            snapshot
        )
        with pytest.raises(AUTHORITY.AuthorityError):
            AUTHORITY._replay_repository_snapshot(**kwargs)  # noqa: SLF001
    finally:
        for current, dirnames, _filenames in os.walk(repository):
            Path(current).chmod(0o755)
            for dirname in dirnames:
                (Path(current) / dirname).chmod(0o755)


@pytest.mark.parametrize(
    "mutation",
    ["extra", "missing", "path", "mode", "hash", "symlink", "hardlink", "identity"],
)
def test_materialized_repository_snapshot_replay_is_fail_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    kwargs, _manifest, repository = _materialized_snapshot_fixture(tmp_path)
    target = repository / "pkg/module.py"
    if mutation in {"extra", "symlink", "hardlink"}:
        repository.chmod(0o755)
        path = repository / ("extra.py" if mutation == "extra" else f"{mutation}.py")
        if mutation == "extra":
            path.write_bytes(b"extra\n")
        elif mutation == "symlink":
            path.symlink_to(target)
        else:
            path.hardlink_to(target)
        repository.chmod(0o555)
    elif mutation in {"missing", "path"}:
        target.parent.chmod(0o755)
        target.unlink() if mutation == "missing" else target.rename(target.with_name("renamed.py"))
        target.parent.chmod(0o555)
    elif mutation == "mode":
        target.chmod(0o400)
    elif mutation == "hash":
        target.chmod(0o644)
        target.write_bytes(b"drift\n")
        target.chmod(0o444)
    else:
        kwargs["root"]["strict_inputs"]["ab16_repository_snapshot"]["sha256"] = "f" * 64
    try:
        with pytest.raises(AUTHORITY.AuthorityError):
            AUTHORITY._replay_repository_snapshot(**kwargs)  # noqa: SLF001
    finally:
        for current, dirnames, _filenames in os.walk(repository):
            Path(current).chmod(0o755)
            for dirname in dirnames:
                (Path(current) / dirname).chmod(0o755)


def _history_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, object]]:
    repository = tmp_path / "history-repository"
    repository.mkdir()
    git_path = Path("/usr/bin/git")

    def git(*arguments: str) -> str:
        return subprocess.run(
            [str(git_path), "-C", str(repository), *arguments],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    git("init", "--quiet")
    git("config", "user.email", "ab16-history-fixture@example.invalid")
    git("config", "user.name", "AB16 history fixture")
    git("-c", "commit.gpgSign=false", "commit", "--quiet", "--allow-empty", "-m", "history head")
    history_head = git("rev-parse", "--verify", "HEAD^{commit}")
    source_relative = (
        "docs/research/noncert_cuts_ab16_20260724/"
        "history_role_fixture_v1.py"
    )
    source_path = repository / source_relative
    archived_source = b"ARCHIVED_FIXTURE = True\n"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(archived_source)
    git("add", "--", source_relative)
    git("-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "archive source")
    source_commit = git("rev-parse", "--verify", "HEAD^{commit}")
    source_tree = git("rev-parse", "--verify", "HEAD^{tree}")
    source_blob = git("rev-parse", "--verify", f"HEAD:{source_relative}")
    source_path.write_bytes(b"LIVE_FIXTURE = True\n")
    git("add", "--", source_relative)
    git("-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "advance live source")
    current_head = git("rev-parse", "--verify", "HEAD^{commit}")

    frozen_root = ".artifacts/noncert_cuts_ab16_fixture/history-frozen"
    artifact_relative = f"{frozen_root}/member.txt"
    artifact_identity = _regular(
        repository / artifact_relative,
        b"immutable history\n",
    )
    sealed_snapshot_root = tmp_path / "sealed-history-snapshot"
    sealed_snapshot_root.mkdir()
    snapshot_manifest_full = _regular(
        tmp_path / "history-snapshot-manifest-identity.json",
        RESOURCE.canonical_json_bytes(
            {"schema_version": "fixture-history-snapshot-manifest-v1"}
        ),
    )
    snapshot_receipt_full = _regular(
        tmp_path / "history-snapshot-materialization-identity.json",
        RESOURCE.canonical_json_bytes(
            {"schema_version": "fixture-history-snapshot-materialization-v1"}
        ),
    )
    snapshot_manifest_identity = {
        key: snapshot_manifest_full[key]
        for key in ("path", "sha256", "size_bytes")
    }
    snapshot_receipt_identity = {
        key: snapshot_receipt_full[key]
        for key in ("path", "sha256", "size_bytes")
    }
    manifest = {
        "created_at_utc": "2026-07-24T00:00:00Z",
        "file_count": 2,
        "files": sorted(
            [
            {
                    **artifact_identity,
                    "path": artifact_relative,
                },
                {
                    "mode": 0o644,
                    "path": source_relative,
                    "sha256": hashlib.sha256(archived_source).hexdigest(),
                    "size_bytes": len(archived_source),
                },
            ],
            key=lambda item: str(item["path"]).encode("utf-8"),
        ),
        "frozen_roots": [frozen_root],
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_FREEZE",
        "repository_head": history_head,
        "repository_root": str(repository),
        "schema_version": ("noncert-cuts-ab16-terminal-reference-history-freeze-v1"),
        "v1_source_glob": "docs/research/noncert_cuts_ab16_20260724/*_v1.py",
    }
    manifest_path = repository / ".artifacts/history-freeze/manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(
        RESOURCE.canonical_json_bytes(manifest) + b"\n"
    )
    manifest_path.chmod(0o400)
    _raw, manifest_identity = RESOURCE.snapshot_bytes(manifest_path)
    source_records = [
        {
            "git_blob_oid": source_blob,
            "git_mode": "100644",
            "mode": 0o644,
            "path": source_relative,
            "sha256": hashlib.sha256(archived_source).hexdigest(),
            "size_bytes": len(archived_source),
        }
    ]
    source_member_digest = hashlib.sha256(
        RESOURCE.canonical_json_bytes(source_records) + b"\n"
    ).hexdigest()
    contract = {
        "HISTORY_FREEZE_HEAD": history_head,
        "HISTORY_FREEZE_MANIFEST_MODE": manifest_identity["mode"],
        "HISTORY_FREEZE_MANIFEST_PATH": manifest_identity["path"],
        "HISTORY_FREEZE_MANIFEST_SHA256": manifest_identity["sha256"],
        "HISTORY_FREEZE_MANIFEST_SIZE": manifest_identity["size_bytes"],
        "HISTORY_SOURCE_COMMIT": source_commit,
        "HISTORY_SOURCE_TREE": source_tree,
        "HISTORY_SOURCE_GLOB": manifest["v1_source_glob"],
        "HISTORY_ARTIFACT_COUNT": 1,
        "HISTORY_SOURCE_COUNT": 1,
        "HISTORY_REPOSITORY_ROOT": repository,
        "HISTORY_FROZEN_ROOTS": (frozen_root,),
    }
    for name, value in contract.items():
        monkeypatch.setattr(RESOURCE, name, value)
    receipt = {
        "artifact_file_count": 1,
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
        },
        "file_count": 2,
        "manifest_identity": manifest_identity,
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY",
        "schema_version": ("noncert-cuts-ab16-terminal-reference-history-replay-v2"),
        "source_file_count": 1,
        "source_materialization": {
            "commit": source_commit,
            "file_count": 1,
            "manifest_head_parent": history_head,
            "member_digest": source_member_digest,
            "tree": source_tree,
        },
        "status": "PASS",
        "verdict": "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS",
    }
    receipt_path = tmp_path / "history-receipt.json"
    receipt_path.write_bytes(RESOURCE.canonical_json_bytes(receipt))
    receipt_path.chmod(0o444)
    _raw, receipt_identity = RESOURCE.snapshot_bytes(receipt_path)
    _raw, git_identity = RESOURCE.snapshot_bytes(git_path)
    pre_run = {
        "history_freeze_replay_identity": receipt_identity,
        "repository_git_tool_identity": git_identity,
        "repository_head": current_head,
        "repository_root": str(repository),
        "live_source_provenance_root": str(repository),
        "sealed_snapshot_execution_root": str(sealed_snapshot_root),
        "snapshot_manifest_identity": snapshot_manifest_identity,
        "snapshot_materialization_receipt_identity": snapshot_receipt_identity,
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
    monkeypatch: pytest.MonkeyPatch,
    execution_class: str,
    manifest_role: str,
) -> None:
    pre_run, manifest_identity = _history_authority(tmp_path, monkeypatch)
    pre_run["execution_class"] = execution_class
    RESOURCE._replay_history_freeze(  # noqa: SLF001
        pre_run=pre_run,
        strict_inputs={manifest_role: manifest_identity},
    )

    wrong_role = "history_freeze_manifest" if manifest_role.startswith("input.") else "input.history_freeze_manifest"
    with pytest.raises(
        RESOURCE.VerificationError,
        match="history freeze strict input identity",
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
