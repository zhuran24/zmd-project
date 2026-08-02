from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = PROJECT_ROOT / "docs/research/noncert_cuts_ab16_20260724"
GATE1_DIR = PROJECT_ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
MANAGER_ATTESTOR_PATH = GATE1_DIR / "manager_attestor_v4.py"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load(RESEARCH_DIR / "ab16_authority_v1.py", "ab16_retry_authority_tested")
BASELINE = _load(RESEARCH_DIR / "baseline_admission_v1.py", "ab16_baseline_admission_for_authority_tested")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", ".")
    _git(
        repository,
        "-c",
        "user.name=AB16 Test",
        "-c",
        "user.email=ab16@example.invalid",
        "commit",
        "-m",
        message,
    )
    return _git(repository, "rev-parse", "HEAD")


def _detached(identity: dict[str, object]) -> dict[str, object]:
    return {key: identity[key] for key in ("path", "sha256", "size_bytes")}


def _identity(path: Path) -> dict[str, object]:
    return AUTH._snapshot(path)[1]  # noqa: SLF001


def _full_identity(path: Path) -> dict[str, object]:
    authority = AUTH.bootstrap.authority
    return dict(authority.full_identity(authority.snapshot_regular(path)))


def _manager_material(
    authority_dir: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, Path]]:
    authority = AUTH.bootstrap.authority
    tool_dir = authority_dir / "manager-tools"
    tool_dir.mkdir(parents=True)
    tools: dict[str, Path] = {}
    for role in ("systemd", "busctl", "sudo", "python"):
        path = tool_dir / role
        path.write_bytes(f"fixture {role}\n".encode())
        tools[role] = path
    attestor_identity = _full_identity(MANAGER_ATTESTOR_PATH)
    audit = authority.audit_attestor_source(MANAGER_ATTESTOR_PATH.read_bytes())
    epoch: dict[str, object] = {
        "attestation_toolchain": {
            "attestor": attestor_identity,
            "python": _full_identity(tools["python"]),
            "sudo": _full_identity(tools["sudo"]),
        },
        "attestor_ast_audit": audit,
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "capture_protocol": "double-unprivileged-join-plus-read-only-sudo-attestation-v4",
        "dbus_unique_owner": ":1.42",
        "manager_executable": _full_identity(tools["systemd"]),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 101,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": _full_identity(tools["busctl"])},
        "schema": authority.MANAGER_EPOCH_SCHEMA,
    }
    state = {
        key: epoch[key]
        for key in (
            "boot_id",
            "dbus_unique_owner",
            "manager_features",
            "manager_pid",
            "manager_pid_starttime",
            "manager_version",
        )
    }
    attestation = {
        "manager_executable": epoch["manager_executable"],
        "request": {
            "boot_id": epoch["boot_id"],
            "dbus_unique_owner": epoch["dbus_unique_owner"],
            "manager_pid": epoch["manager_pid"],
            "manager_pid_starttime": epoch["manager_pid_starttime"],
        },
        "schema": authority.ATTESTOR_SCHEMA,
        "status": "PASS",
    }
    attestation_tools = epoch["attestation_toolchain"]
    assert isinstance(attestation_tools, dict)
    invocation = {
        "argv": [
            attestation_tools["sudo"]["path"],
            "-n",
            "--",
            attestation_tools["python"]["path"],
            "-I",
            "-c",
            authority._LOADER,  # noqa: SLF001
            "--pid",
            str(epoch["manager_pid"]),
            "--expected-starttime",
            str(epoch["manager_pid_starttime"]),
            "--expected-boot-id",
            epoch["boot_id"],
            "--dbus-owner",
            epoch["dbus_unique_owner"],
        ],
        "exit_code": 0,
        "stdin_sha256": attestor_identity["sha256"],
        "stdin_size_bytes": attestor_identity["size_bytes"],
        "stdout_base64": base64.b64encode(authority.canonical_json(attestation)).decode("ascii"),
    }
    rounds = [
        {
            "attestation_toolchain": copy.deepcopy(epoch["attestation_toolchain"]),
            "attestor_ast_audit": copy.deepcopy(epoch["attestor_ast_audit"]),
            "attestor_invocation": copy.deepcopy(invocation),
            "observation_toolchain": copy.deepcopy(epoch["observation_toolchain"]),
            "observation_finished_monotonic_ns": index * 20,
            "observation_started_monotonic_ns": index * 20 - 10,
            "privileged_attestation": copy.deepcopy(attestation),
            "round_index": index,
            "unprivileged_after": copy.deepcopy(state),
            "unprivileged_before": copy.deepcopy(state),
        }
        for index in (1, 2)
    ]
    transcript = {
        "capture_protocol": "two-round-before-read-only-attestor-after-transcript-v4",
        "rounds": rounds,
        "schema": authority.MANAGER_EPOCH_TRANSCRIPT_SCHEMA,
    }
    authority.validate_manager_epoch_capture_transcript(transcript, expected_epoch=epoch)
    return epoch, transcript, tools


def _execution_context(
    fixture: dict[str, object],
    *,
    slot: str,
    attempt_ordinal: int,
) -> dict[str, object]:
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    attempt_dir = Path(preregistration["slot_roots"][slot]) / f"attempt-{attempt_ordinal:04d}"
    tool_paths = AUTH._execution_tool_paths(None)  # noqa: SLF001
    attempt_tools: dict[str, dict[str, object]] = {}
    for index, (role, source) in enumerate(sorted(tool_paths.items())):
        raw, source_identity = AUTH._snapshot(source)  # noqa: SLF001
        attempt_tools[role] = {
            "mode": 0o600,
            "path": str(attempt_dir / "tool-snapshots" / f"{index:04d}.bin"),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": source_identity["size_bytes"],
        }

    system_identities = fixture["system_tool_identities"]
    assert isinstance(system_identities, dict)
    execution_tools = {
        role: attempt_tools[role]
        for role in (
            "ab16_contract",
            "ab16_terminal_gate",
            "organic_arm_replay",
            "organic_arm_runner",
            "organic_resource_lifecycle",
            "organic_resource_verifier",
            "organic_unit_orchestrator",
        )
    }
    execution_tools.update(system_identities)

    package = fixture["package"]
    campaign_root_identity = fixture["campaign_root_identity"]
    continuation_identity = fixture["continuation_identity"]
    assert isinstance(package, dict)
    assert isinstance(campaign_root_identity, dict)
    assert isinstance(continuation_identity, dict)
    return {
        "authority_chain": {
            "campaign_root_identity": campaign_root_identity,
            "continuation_identity": continuation_identity,
            "manager_epoch_authority_identity": _detached(execution_tools["manager_epoch_authority"]),
            "package": package,
        },
        "campaign_id": "a" * 64,
        "campaign_root_identity": campaign_root_identity,
        "continuation_identity": continuation_identity,
        "manager_epoch": fixture["manager_epoch"],
        "package": package,
        "repository_git_tool_identity": fixture["git_identity"],
        "repository_root": str(fixture["repository"]),
        "run_nonce": "ab16-test-run",
        "tool_identities": execution_tools,
        "unit_name": f"ab16-{slot}.service",
    }


def _launch_environment(tmp_path: Path) -> dict[str, str]:
    return {
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        "HOME": str(tmp_path / "home"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "TZ": "UTC",
        "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
    }


def _fixture(
    tmp_path: Path,
    *,
    materialize_pre_manifest: bool = True,
    publish_manifest: bool = True,
) -> dict[str, object]:
    if publish_manifest and not materialize_pre_manifest:
        raise ValueError("the manifest requires materialized pre-manifest inputs")
    git_path = shutil.which("git")
    assert git_path is not None
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")
    tracked = repository / "tracked.txt"
    repairable_tool = repository / "repairable_tool.py"
    canonical_rules = repository / "rules" / "canonical_rules.json"
    mandatory_instances = repository / "data" / "preprocessed" / "mandatory_exact_instances.json"
    tracked.write_text("initial\n", encoding="utf-8")
    repairable_tool.write_text("VERSION = 1\n", encoding="utf-8")
    _write(canonical_rules, {"fixture": "canonical-rules"})
    _write(mandatory_instances, [{"instance_id": "fixture"}])
    first_head = _commit(repository, "initial")
    candidate_placements = repository / "data" / "preprocessed" / "candidate_placements.json"
    _write(candidate_placements, {"facility_pools": {}})

    campaign = tmp_path / "run-ab16-test"
    campaign.mkdir()
    (campaign / "prospective-ab16").mkdir()
    authority_dir = tmp_path / "execution-authority"
    authority_dir.mkdir()
    manager_epoch, manager_transcript, manager_tools = _manager_material(authority_dir)
    system_tools = {
        "busctl": manager_tools["busctl"],
        "manager_attestor": MANAGER_ATTESTOR_PATH,
        "manager_epoch_authority": Path(AUTH.bootstrap.authority.__file__),
        "python3_13": manager_tools["python"],
        "sudo": manager_tools["sudo"],
        "systemctl": authority_dir / "systemctl",
        "systemd_run": authority_dir / "systemd-run",
    }
    for role in ("systemctl", "systemd_run"):
        system_tools[role].write_bytes(f"fixture {role}\n".encode())
    system_tool_identities = {role: _identity(path) for role, path in system_tools.items()}

    continuation_path = authority_dir / "continuation.json"
    package_manifest_path = authority_dir / "package-manifest.json"
    package_seal_path = authority_dir / "package-seal.json"
    for path, payload in (
        (continuation_path, b"continuation\n"),
        (package_manifest_path, b"package manifest\n"),
        (package_seal_path, b"package seal\n"),
    ):
        path.write_bytes(payload)
    seal_identity = _detached(_identity(package_seal_path))

    preregistration = AUTH.bootstrap._path_preregistration(  # noqa: SLF001
        campaign,
        scientific_input_set_sha256="5" * 64,
    )
    package_dir = campaign / "campaign-authority" / "package"
    package_payload_dir = package_dir / "payload"
    package_payload_dir.mkdir(parents=True)
    preregistration_path = package_payload_dir / AUTH.bootstrap.PATH_PREREGISTRATION_PACKAGE_ROLE
    preregistration_path.write_bytes(AUTH.bootstrap.authority.canonical_json(preregistration))
    checkout_inputs = {
        "candidate_placements": candidate_placements,
        "canonical_rules": canonical_rules,
        "mandatory_instances": mandatory_instances,
    }
    package_inputs: dict[str, Path] = {}
    for role, source in checkout_inputs.items():
        destination = package_payload_dir / f"input.{role}.json"
        destination.write_bytes(source.read_bytes())
        package_inputs[role] = destination

    baseline_paths = AUTH._baseline_material_paths(preregistration)  # noqa: SLF001
    for index, path in enumerate(sorted(set(baseline_paths.values()), key=os.fspath)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fixed-scientific-input-{index}\n".encode())
    fixture_incumbent = {"fixture_pick": {"instance_id": "fixture_pick", "pose_idx": 0}}
    baseline_paths["baseline_incumbent"].write_bytes(BASELINE.canonical_json(fixture_incumbent))
    fixture_provenance = {"fixture": "shared baseline provenance"}
    fixture_incumbent_identity = _detached(_identity(baseline_paths["baseline_incumbent"]))
    baseline_admission = {
        "admission_tool_identity": _detached(_identity(Path(BASELINE.__file__))),
        "authorizations": {
            "baseline_inputs_admitted": True,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        },
        "campaign_provenance": fixture_provenance,
        "created_at_utc": "2026-08-02T00:00:00Z",
        "expectation_profile": "authority-state-fixture-v1",
        "expected_baseline": {
            "historical_model_text_sha256": "1" * 64,
            "incumbent_assignment_count": 1,
            "incumbent_sha256": BASELINE.semantic_digest(fixture_incumbent),
            "model_constraint_count": 1,
            "model_variable_count": 1,
        },
        "fixed_assignment_replay": {
            "campaign_provenance": fixture_provenance,
            "incumbent_identity": fixture_incumbent_identity,
            "receipt_identity": _detached(_identity(baseline_paths["baseline_fixed_replay"])),
            "replay_tool_identity": _detached(_identity(Path(BASELINE.__file__))),
            "solver_status": "OPTIMAL",
            "status": "PASS",
            "verdict": "INCUMBENT_FIXED_ASSIGNMENT_REPLAY_PASS",
        },
        "legacy_control": {},
        "rebuilt_model": {
            "canonical_binary": True,
            "identity": _detached(_identity(baseline_paths["baseline_rebuilt_model"])),
            "metadata": {"campaign_provenance": fixture_provenance},
            "model_backend": "fixture",
            "model_binary_format": "fixture",
        },
        "schema_version": BASELINE.ADMISSION_SCHEMA,
        "status": "PASS",
        "verdict": BASELINE.ADMISSION_VERDICT,
    }
    baseline_paths["baseline_admission"].write_bytes(BASELINE.canonical_json(baseline_admission))

    campaign_root = AUTH.bootstrap.authority.build_campaign_root(
        campaign,
        package={
            "manifest_identity": _detached(_identity(package_manifest_path)),
            "package_dir": str(package_dir),
            "package_id": seal_identity["sha256"],
            "schema": AUTH.bootstrap.authority.PACKAGE_SCHEMA,
            "seal_identity": seal_identity,
            "status": "SEALED",
        },
        repository_head=first_head,
        run_nonce=campaign.name,
        manager_epoch=manager_epoch,
        authority_tools={
            "campaign_authority_v4": _detached(_identity(Path(AUTH.bootstrap.authority.__file__))),
            "git": _detached(_identity(Path(git_path))),
        },
        strict_inputs={
            AUTH.bootstrap.PATH_PREREGISTRATION_INPUT_ROLE: _detached(_identity(preregistration_path)),
            **{role: _detached(_identity(path)) for role, path in package_inputs.items()},
        },
        created_at_utc="2026-08-02T00:00:00Z",
    )
    campaign_root_path = campaign / "campaign-root.json"
    campaign_root_path.write_bytes(AUTH.bootstrap.authority.canonical_json(campaign_root))

    materialized = (
        AUTH.materialize_pre_manifest_inputs(preregistration_path) if materialize_pre_manifest else None
    )
    manifest = AUTH.build_manifest(preregistration_path) if publish_manifest else None
    suite_selection = AUTH.create_suite_selection(preregistration_path) if publish_manifest else None
    if manifest is not None:
        assert manifest["manifest"]["scientific_input_set_sha256"] == preregistration[
            "scientific_input_set_sha256"
        ]
        assert manifest["manifest"]["scientific_materialization_sha256"] != preregistration[
            "scientific_input_set_sha256"
        ]

    return {
        "campaign": campaign,
        "campaign_root_identity": _detached(_identity(campaign_root_path)),
        "continuation_identity": _detached(_identity(continuation_path)),
        "first_head": first_head,
        "git_identity": _identity(Path(git_path)),
        "launch_environment": _launch_environment(tmp_path),
        "manager_capture": {"manager_epoch": manager_epoch, "transcript": manager_transcript},
        "manager_epoch": manager_epoch,
        "manifest": manifest,
        "materialized": materialized,
        "package": {
            "manifest_identity": _detached(_identity(package_manifest_path)),
            "package_id": seal_identity["sha256"],
            "seal_identity": seal_identity,
        },
        "package_manifest_path": package_manifest_path,
        "package_seal_path": package_seal_path,
        "package_inputs": package_inputs,
        "preregistration": preregistration,
        "preregistration_path": preregistration_path,
        "repairable_tool": repairable_tool,
        "repository": repository,
        "checkout_inputs": checkout_inputs,
        "suite_selection": suite_selection,
        "system_tool_identities": system_tool_identities,
        "tracked": tracked,
    }


def _prepare(fixture: dict[str, object], *, slot: str | None = None) -> dict[str, object]:
    selected_slot = slot or AUTH.contract.ARM_SEQUENCE[0]
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    slot_root = Path(preregistration["slot_roots"][selected_slot])
    attempt_ordinal = len(list(slot_root.glob("attempt-*"))) + 1 if slot_root.exists() else 1
    return AUTH.prepare_attempt(
        fixture["preregistration_path"],
        repository_root=fixture["repository"],
        slot=slot,
        execution_context=_execution_context(
            fixture,
            slot=selected_slot,
            attempt_ordinal=attempt_ordinal,
        ),
    )


def _produce(
    fixture: dict[str, object],
    prepared: dict[str, object],
    *,
    selection_nonce: str = "test-selection",
) -> dict[str, object]:
    return AUTH.produce_selection(
        fixture["preregistration_path"],
        slot=prepared["slot"],
        attempt_ordinal=prepared["attempt_ordinal"],
        selection_nonce=selection_nonce,
        manager_capture=fixture["manager_capture"],
        launch_environment=fixture["launch_environment"],
    )


def _run_atomic_publication_crash(final_path: Path, raw: bytes, *, phase: str) -> subprocess.CompletedProcess[bytes]:
    child = r"""
import importlib.util
import os
from pathlib import Path
import signal
import sys

source = Path(sys.argv[1])
final_path = Path(sys.argv[2])
raw = bytes.fromhex(sys.argv[3])
phase = sys.argv[4]
spec = importlib.util.spec_from_file_location("ab16_atomic_crash_child", source)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
if phase == "write":
    original_write = module.os.write

    def crash_write(descriptor, data):
        written = original_write(descriptor, data[: max(1, len(data) // 2)])
        os.kill(os.getpid(), signal.SIGKILL)
        return written

    module.os.write = crash_write
elif phase == "link":
    original_unlink = module.os.unlink

    def crash_unlink(path, *args, **kwargs):
        if str(path).startswith(f".{final_path.name}.pending-"):
            os.kill(os.getpid(), signal.SIGKILL)
        return original_unlink(path, *args, **kwargs)

    module.os.unlink = crash_unlink
else:
    raise AssertionError(phase)
module._write_bytes_exclusive(final_path, raw)
"""
    return subprocess.run(
        (
            sys.executable,
            "-c",
            child,
            str(RESEARCH_DIR / "ab16_authority_v1.py"),
            str(final_path),
            raw.hex(),
            phase,
        ),
        check=False,
        capture_output=True,
    )


def _run_prepare_before_open_crash(
    fixture: dict[str, object],
    *,
    slot: str,
) -> subprocess.CompletedProcess[bytes]:
    context_path = Path(fixture["campaign"]) / "prepare-crash-execution-context.json"
    _write(context_path, _execution_context(fixture, slot=slot, attempt_ordinal=1))
    child = r"""
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys

source = Path(sys.argv[1])
preregistration = Path(sys.argv[2])
repository = Path(sys.argv[3])
slot = sys.argv[4]
context = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
spec = importlib.util.spec_from_file_location("ab16_prepare_crash_child", source)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
original_write_record = module._write_record

def crash_before_open(path, value):
    if Path(path).name == "attempt-open.json":
        os.kill(os.getpid(), signal.SIGKILL)
    return original_write_record(path, value)

module._write_record = crash_before_open
module.prepare_attempt(
    preregistration,
    repository_root=repository,
    slot=slot,
    execution_context=context,
)
"""
    return subprocess.run(
        (
            sys.executable,
            "-c",
            child,
            str(RESEARCH_DIR / "ab16_authority_v1.py"),
            str(fixture["preregistration_path"]),
            str(fixture["repository"]),
            slot,
            str(context_path),
        ),
        check=False,
        capture_output=True,
    )


def _run_incomplete_close_write_crash(
    fixture: dict[str, object],
    *,
    slot: str,
    attempt_ordinal: int,
) -> subprocess.CompletedProcess[bytes]:
    child = r"""
import importlib.util
import os
from pathlib import Path
import signal
import sys

source = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("ab16_close_crash_child", source)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
original_write = module.os.write

def crash_write(descriptor, data):
    written = original_write(descriptor, data[: max(1, len(data) // 2)])
    os.kill(os.getpid(), signal.SIGKILL)
    return written

module.os.write = crash_write
module.close_attempt(
    Path(sys.argv[2]),
    slot=sys.argv[3],
    attempt_ordinal=int(sys.argv[4]),
    outcome=module.CREDIBILITY_INCOMPLETE,
    failure_code="INJECTED_CLOSE_CRASH",
)
"""
    return subprocess.run(
        (
            sys.executable,
            "-c",
            child,
            str(RESEARCH_DIR / "ab16_authority_v1.py"),
            str(fixture["preregistration_path"]),
            slot,
            str(attempt_ordinal),
        ),
        check=False,
        capture_output=True,
    )


def _pending_paths(final_path: Path) -> list[Path]:
    return sorted(final_path.parent.glob(f".{final_path.name}.pending-*"))


def _fake_credible_gate(attempt_dir: Path, *, slot: str, selection_identity: dict[str, object]) -> Path:
    path = attempt_dir / "work" / "arm-gate.json"
    _write(
        path,
        {
            "authorizations": {
                "family_global_soundness_authorized": False,
                "global_claim_authorized": False,
                "mathematical_claim_authorized": False,
                "production_certified_authorized": False,
                "runtime_effect_authorized": False,
                "stage_b_promotion_authorized": False,
            },
            "credibility_status": "PASS",
            "schema_version": "noncert-cuts-ab16-arm-credibility-gate-v1",
            "selection_identity": selection_identity,
            "slot": slot,
            "status": "PASS",
        },
    )
    return path


def _advance_first_slot_for_state_setup(
    fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """Advance one slot while isolating terminal evidence unrelated to state tests."""

    first_slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture, slot=first_slot)
    produced = _produce(fixture, prepared)
    AUTH.bind_selection(
        fixture["preregistration_path"],
        slot=first_slot,
        attempt_ordinal=1,
        selection_path=produced["selection_identity"]["path"],
    )

    def state_setup_gate(attempt_dir: Path, **_kwargs: object) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        gate_path = _fake_credible_gate(
            attempt_dir,
            slot=first_slot,
            selection_identity=produced["selection_identity"],
        )
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        gate_identity = _identity(gate_path)
        return gate, gate_identity, {"arm_gate": gate_identity}

    with monkeypatch.context() as patch:
        patch.setattr(AUTH, "_build_credible_gate", state_setup_gate)
        AUTH.close_attempt(
            fixture["preregistration_path"],
            slot=first_slot,
            attempt_ordinal=1,
            outcome=AUTH.CREDIBLE_TERMINAL,
        )
    return prepared


def _assert_false_authorizations(value: object) -> None:
    if type(value) is dict:
        for key, member in value.items():
            if "authoriz" in key:
                if type(member) is dict:
                    assert member
                    assert all(item is False for item in member.values())
                else:
                    assert member is False
            _assert_false_authorizations(member)
    elif type(value) is list:
        for member in value:
            _assert_false_authorizations(member)


def test_pre_manifest_materializer_derives_v2_common_and_bindings(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, publish_manifest=False)
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)

    common_path = Path(preregistration["common_prestate_path"])
    common = json.loads(common_path.read_text(encoding="utf-8"))
    assert set(common) == {
        "authorizations",
        "baseline_admission_identity",
        "baseline_fixed_replay_identity",
        "baseline_incumbent_identity",
        "baseline_rebuilt_metadata_identity",
        "baseline_rebuilt_model_identity",
        "campaign_root_identity",
        "classification_contract_identity",
        "experiment_contract",
        "preregistration_identity",
        "purpose",
        "schema_version",
        "scientific_input_set_sha256",
        "status",
        "verdict",
    }
    assert common["schema_version"] == AUTH.COMMON_PRESTATE_SCHEMA
    assert common["preregistration_identity"] == _detached(_identity(Path(fixture["preregistration_path"])))
    assert common["campaign_root_identity"] == fixture["campaign_root_identity"]
    assert common["scientific_input_set_sha256"] == preregistration["scientific_input_set_sha256"]
    assert common["experiment_contract"] == AUTH.runner.EXPERIMENT_CONTRACT
    for role, path_field in {
        "baseline_admission_identity": "baseline_admission_path",
        "baseline_fixed_replay_identity": "baseline_fixed_replay_path",
        "baseline_incumbent_identity": "baseline_incumbent_path",
        "baseline_rebuilt_metadata_identity": "baseline_rebuilt_metadata_path",
        "baseline_rebuilt_model_identity": "baseline_rebuilt_model_path",
        "classification_contract_identity": "classification_contract_path",
    }.items():
        assert common[role] == _detached(_identity(Path(preregistration[path_field])))

    common_identity = _detached(_identity(common_path))
    root = json.loads((Path(fixture["campaign"]) / "campaign-root.json").read_text(encoding="utf-8"))
    units = {
        item["slot"]: item["unit_name"]
        for item in root["stage_topology"]["prospective_ab16"]["arms"]
    }
    for slot_index, slot in enumerate(AUTH.contract.ARM_SEQUENCE):
        binding = json.loads(Path(preregistration["binding_paths"][slot]).read_text(encoding="utf-8"))
        configuration, order, arm = AUTH._slot_parts(slot)  # noqa: SLF001
        assert set(binding) == {
            "arm",
            "authorizations",
            "common_prestate_identity",
            "configuration",
            "enabled_families",
            "order",
            "preregistration_identity",
            "purpose",
            "schema_version",
            "slot",
            "slot_index",
            "slot_root",
            "status",
            "unit_name",
            "verdict",
        }
        assert binding["schema_version"] == AUTH.ARM_BINDING_SCHEMA
        assert binding["slot_index"] == slot_index
        assert (binding["configuration"], binding["order"], binding["arm"]) == (configuration, order, arm)
        assert binding["enabled_families"] == (
            [] if arm == "control" else list(AUTH.runner.CONFIGURATION_FAMILIES[configuration])
        )
        assert binding["common_prestate_identity"] == common_identity
        assert binding["preregistration_identity"] == common["preregistration_identity"]
        assert binding["slot_root"] == preregistration["slot_roots"][slot]
        assert binding["unit_name"] == units[slot]
        assert not {"attempt_dir", "attempt_ordinal", "selection_nonce"} & set(binding)


@pytest.mark.parametrize("target", ("common", "binding"))
def test_build_manifest_replays_pre_manifest_semantics_before_hashing(tmp_path: Path, target: str) -> None:
    fixture = _fixture(tmp_path, publish_manifest=False)
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    if target == "common":
        path = Path(preregistration["common_prestate_path"])
        record = json.loads(path.read_text(encoding="utf-8"))
        record["scientific_input_set_sha256"] = "0" * 64
    else:
        slot = AUTH.contract.ARM_SEQUENCE[-1]
        path = Path(preregistration["binding_paths"][slot])
        record = json.loads(path.read_text(encoding="utf-8"))
        record["slot_index"] = 0
    _write(path, record)

    with pytest.raises(AUTH.AuthorityError, match="replayed record"):
        AUTH.build_manifest(fixture["preregistration_path"])
    assert not Path(preregistration["manifest_path"]).exists()


def test_pre_manifest_partial_publication_recovers_only_exact_existing_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, materialize_pre_manifest=False, publish_manifest=False)
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    failed_slot = AUTH.contract.ARM_SEQUENCE[2]
    failed_path = Path(preregistration["binding_paths"][failed_slot])
    original_write = AUTH._write_record  # noqa: SLF001

    def stop_mid_publication(path: Path, value: object) -> dict[str, object]:
        if Path(path) == failed_path:
            raise AUTH.AuthorityError("injected pre-manifest interruption")
        return original_write(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(AUTH, "_write_record", stop_mid_publication)
        with pytest.raises(AUTH.AuthorityError, match="injected pre-manifest interruption"):
            AUTH.materialize_pre_manifest_inputs(fixture["preregistration_path"])

    preserved_paths = [
        Path(preregistration["common_prestate_path"]),
        *(Path(preregistration["binding_paths"][slot]) for slot in AUTH.contract.ARM_SEQUENCE[:2]),
    ]
    preserved = {
        path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in preserved_paths
    }
    resumed = AUTH.materialize_pre_manifest_inputs(fixture["preregistration_path"])

    assert resumed["replayed_roles"] == [
        f"arm_binding.{AUTH.contract.ARM_SEQUENCE[0]}",
        f"arm_binding.{AUTH.contract.ARM_SEQUENCE[1]}",
        "common_prestate",
    ]
    assert f"arm_binding.{failed_slot}" in resumed["published_roles"]
    for path, before in preserved.items():
        assert (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) == before
    assert all(Path(path).is_file() for path in preregistration["binding_paths"].values())


def test_pre_manifest_replay_is_no_overwrite_when_all_bytes_are_exact(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, publish_manifest=False)
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    paths = [
        Path(preregistration["common_prestate_path"]),
        *(Path(path) for path in preregistration["binding_paths"].values()),
    ]
    before = {path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths}

    replayed = AUTH.materialize_pre_manifest_inputs(fixture["preregistration_path"])

    assert replayed["published_roles"] == []
    assert len(replayed["replayed_roles"]) == 1 + len(AUTH.contract.ARM_SEQUENCE)
    assert {path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths} == before


def test_pre_manifest_materializer_does_not_repair_changed_existing_bytes(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, publish_manifest=False)
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    common_path = Path(preregistration["common_prestate_path"])
    common_path.write_bytes(common_path.read_bytes() + b"\n")
    changed = common_path.read_bytes()

    with pytest.raises(AUTH.AuthorityError, match="differ from the replayed record"):
        AUTH.materialize_pre_manifest_inputs(fixture["preregistration_path"])
    assert common_path.read_bytes() == changed


def test_pre_manifest_materializer_rejects_extra_binding_directory_member(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, materialize_pre_manifest=False, publish_manifest=False)
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    binding_dir = Path(preregistration["binding_paths"][AUTH.contract.ARM_SEQUENCE[0]]).parent
    binding_dir.mkdir()
    (binding_dir / "unexpected.json").write_text("unexpected\n", encoding="utf-8")

    with pytest.raises(AUTH.AuthorityError, match="unexpected members"):
        AUTH.materialize_pre_manifest_inputs(fixture["preregistration_path"])
    assert not Path(preregistration["common_prestate_path"]).exists()


def test_materialize_pre_manifest_cli_uses_the_real_producer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _fixture(tmp_path, materialize_pre_manifest=False, publish_manifest=False)

    assert AUTH.main(
        [
            "materialize-pre-manifest",
            "--preregistration",
            str(fixture["preregistration_path"]),
        ]
    ) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "PRE_MANIFEST_INPUTS_READY"
    assert output["published_roles"][0] == "common_prestate"


def test_selection_uses_the_admitted_incumbent_semantic_digest(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    prepared = _prepare(fixture)
    produced = _produce(fixture, prepared)
    pre_run = json.loads(Path(produced["pre_run_authority_identity"]["path"]).read_bytes())
    selection = json.loads(Path(produced["selection_identity"]["path"]).read_bytes())
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    incumbent_raw = Path(preregistration["baseline_incumbent_path"]).read_bytes()
    incumbent = json.loads(incumbent_raw)
    semantic_digest = BASELINE.semantic_digest(incumbent)

    assert semantic_digest != hashlib.sha256(incumbent_raw).hexdigest()
    assert pre_run["baseline_incumbent_sha256"] == semantic_digest
    assert selection["baseline_incumbent_sha256"] == semantic_digest


def test_incomplete_attempt_can_retry_after_clean_code_fix(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]

    first = _prepare(fixture, slot=slot)
    first_attempt = Path(first["attempt_dir"])
    first_input_bytes = (first_attempt / "attempt-input-set.json").read_bytes()
    first_execution = json.loads((first_attempt / "attempt-execution.json").read_text(encoding="utf-8"))
    first_preregistration_sha = first["preregistration_sha256"]
    assert first["attempt_ordinal"] == 1
    assert first["repository_head"] == fixture["first_head"]

    first_selection = _produce(fixture, first, selection_nonce="attempt-0001")
    assert {path.name for path in Path(first["work_dir"]).iterdir()} == {
        "pre-run-authority.json",
        "selection.json",
    }
    AUTH.bind_selection(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        selection_path=first_selection["selection_identity"]["path"],
    )

    closed = AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="EXECUTION_TOOL_BUG",
    )
    assert closed["retry_disposition"] == "SAME_SLOT_RETRY_ALLOWED"

    fixture["repairable_tool"].write_text("VERSION = 2\n", encoding="utf-8")
    fixture["tracked"].write_text("repair\n", encoding="utf-8")
    second_head = _commit(fixture["repository"], "repair")
    second = _prepare(fixture, slot=slot)
    second_attempt = Path(second["attempt_dir"])
    second_execution = json.loads((second_attempt / "attempt-execution.json").read_text(encoding="utf-8"))

    assert second["attempt_ordinal"] == 2
    assert second["repository_head"] == second_head != first["repository_head"]
    assert second["preregistration_sha256"] == first_preregistration_sha
    assert second["input_set_sha256"] != first["input_set_sha256"]
    assert (first_attempt / "attempt-input-set.json").read_bytes() == first_input_bytes
    assert second_execution["manifest_identity"] == first_execution["manifest_identity"]
    assert second_execution["scientific_input_set_sha256"] == first_execution["scientific_input_set_sha256"]
    assert second_execution["run_dir"] != first_execution["run_dir"]
    assert second["attempt_execution_identity"] != first["attempt_execution_identity"]

    second_selection = _produce(fixture, second, selection_nonce="attempt-0002")
    assert {path.name for path in Path(second["work_dir"]).iterdir()} == {
        "pre-run-authority.json",
        "selection.json",
    }
    AUTH.bind_selection(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=2,
        selection_path=second_selection["selection_identity"]["path"],
    )
    second_closed = AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=2,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="RUNNER_EVIDENCE_UNAVAILABLE",
    )
    assert second_closed["retry_disposition"] == "SAME_SLOT_RETRY_ALLOWED"

    replay = AUTH.replay_campaign(fixture["preregistration_path"])
    assert replay["consumption_state"]["next_index"] == 0
    assert [attempt["outcome"] for attempt in replay["attempts"]] == [
        AUTH.CREDIBILITY_INCOMPLETE,
        AUTH.CREDIBILITY_INCOMPLETE,
    ]

    for path in (
        first_attempt / "attempt-input-set.json",
        first_attempt / "attempt-result.json",
        second_attempt / "attempt-input-set.json",
        second_attempt / "attempt-result.json",
    ):
        _assert_false_authorizations(json.loads(path.read_text(encoding="utf-8")))


def test_unresolved_attempt_blocks_retry_and_records_are_no_overwrite(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture)

    with pytest.raises(AUTH.AuthorityError, match="must close"):
        _prepare(fixture)

    produced = _produce(fixture, prepared)
    selection_path = produced["selection_identity"]["path"]
    AUTH.bind_selection(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        selection_path=selection_path,
    )
    with pytest.raises(AUTH.AuthorityError, match="no-overwrite"):
        AUTH.bind_selection(
            fixture["preregistration_path"],
            slot=slot,
            attempt_ordinal=1,
            selection_path=selection_path,
        )
    AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="RUN_FAILED",
    )
    with pytest.raises(AUTH.AuthorityError, match="only the active"):
        AUTH.close_attempt(
            fixture["preregistration_path"],
            slot=slot,
            attempt_ordinal=1,
            outcome=AUTH.CREDIBILITY_INCOMPLETE,
            failure_code="REWRITE",
        )


@pytest.mark.parametrize("case", ["unknown", "symlink", "gap", "future"])
def test_slot_topology_fails_closed(tmp_path: Path, case: str) -> None:
    fixture = _fixture(tmp_path)
    preregistration = fixture["preregistration"]
    first_root = Path(preregistration["slot_roots"][AUTH.contract.ARM_SEQUENCE[0]])
    first_root.mkdir(parents=True)
    if case == "unknown":
        (first_root / "notes.txt").write_text("unexpected\n", encoding="utf-8")
    elif case == "symlink":
        target = tmp_path / "target"
        target.mkdir()
        (first_root / "attempt-0001").symlink_to(target, target_is_directory=True)
    elif case == "gap":
        (first_root / "attempt-0002").mkdir()
    else:
        future_root = Path(preregistration["slot_roots"][AUTH.contract.ARM_SEQUENCE[1]])
        (future_root / "attempt-0001").mkdir(parents=True)
    with pytest.raises(AUTH.AuthorityError):
        AUTH.replay_campaign(fixture["preregistration_path"])


def test_snapshot_tamper_fails_replay_but_source_code_repair_does_not(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    prepared = _prepare(fixture)
    attempt_dir = Path(prepared["attempt_dir"])
    input_record = json.loads((attempt_dir / "attempt-input-set.json").read_text(encoding="utf-8"))
    tool_snapshot = Path(input_record["tool_identities"]["ab16_authority"]["path"])

    fixture["repairable_tool"].write_text("VERSION = 99\n", encoding="utf-8")
    fixture["tracked"].write_text("new source\n", encoding="utf-8")
    _commit(fixture["repository"], "later repair")
    assert AUTH.replay_campaign(fixture["preregistration_path"])["active_attempt"] is not None

    tool_snapshot.write_text("tampered snapshot\n", encoding="utf-8")
    with pytest.raises(AUTH.AuthorityError, match="drifted"):
        AUTH.replay_campaign(fixture["preregistration_path"])


def test_scientific_input_drift_is_rejected_before_allocating_retry(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    first = _prepare(fixture)
    AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="RETRY",
    )
    preregistration = fixture["preregistration"]
    Path(preregistration["baseline_incumbent_path"]).write_text("changed science\n", encoding="utf-8")
    with pytest.raises(AUTH.AuthorityError, match="scientific"):
        _prepare(fixture)
    slot_root = Path(preregistration["slot_roots"][slot])
    assert sorted(path.name for path in slot_root.iterdir()) == ["attempt-0001"]
    assert Path(first["attempt_dir"]).is_dir()


@pytest.mark.parametrize(
    "case",
    ("baseline", "common_prestate", "later_binding", "manifest", "suite_selection"),
)
def test_campaign_scientific_anchor_blocks_cross_slot_replay_and_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    fixture = _fixture(tmp_path)
    second_slot = AUTH.contract.ARM_SEQUENCE[1]
    _advance_first_slot_for_state_setup(fixture, monkeypatch)
    assert AUTH.replay_campaign(fixture["preregistration_path"])["consumption_state"]["next_index"] == 1

    preregistration = fixture["preregistration"]
    if case == "baseline":
        Path(preregistration["baseline_incumbent_path"]).write_bytes(b"drifted baseline\n")
    elif case == "common_prestate":
        Path(preregistration["common_prestate_path"]).write_bytes(b"drifted prestate\n")
    elif case == "later_binding":
        Path(preregistration["binding_paths"][second_slot]).write_bytes(b"drifted binding\n")
    elif case == "manifest":
        manifest_path = Path(preregistration["manifest_path"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["scientific_materialization_sha256"] = "0" * 64
        _write(manifest_path, manifest)
    else:
        suite_path = Path(preregistration["suite_selection_path"])
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        suite["status"] = "DRIFTED"
        _write(suite_path, suite)

    with pytest.raises(AUTH.AuthorityError, match="scientific|suite selection"):
        AUTH.replay_campaign(fixture["preregistration_path"])
    with pytest.raises(AUTH.AuthorityError, match="scientific|suite selection"):
        _prepare(fixture, slot=second_slot)
    assert not Path(preregistration["slot_roots"][second_slot]).exists()


def test_manifest_cannot_replace_the_preregistered_scientific_anchor(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    preregistration = fixture["preregistration"]
    manifest_path = Path(preregistration["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["scientific_input_set_sha256"] = "6" * 64
    _write(manifest_path, manifest)

    with pytest.raises(AUTH.AuthorityError, match="preregistration join"):
        _prepare(fixture)
    first_slot_root = Path(preregistration["slot_roots"][AUTH.contract.ARM_SEQUENCE[0]])
    assert not first_slot_root.exists()


def test_campaign_root_rejects_a_self_consistent_forged_preregistration(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    forged = copy.deepcopy(fixture["preregistration"])
    forged["scientific_input_set_sha256"] = "6" * 64
    forged_path = tmp_path / "forged-scientific-preregistration.json"
    forged_path.write_bytes(AUTH.bootstrap.authority.canonical_json(forged))

    with pytest.raises(AUTH.AuthorityError, match="differs from the campaign root"):
        AUTH.build_manifest(forged_path)


def test_second_slot_archived_input_cannot_introduce_a_new_campaign_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    _advance_first_slot_for_state_setup(fixture, monkeypatch)
    second = _prepare(fixture, slot=AUTH.contract.ARM_SEQUENCE[1])
    attempt_dir = Path(second["attempt_dir"])

    input_path = attempt_dir / "attempt-input-set.json"
    input_record = json.loads(input_path.read_text(encoding="utf-8"))
    input_record["scientific_input_set_sha256"] = "6" * 64
    _write(input_path, input_record)
    input_identity = _identity(input_path)

    execution_path = attempt_dir / "attempt-execution.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["input_set_identity"] = input_identity
    execution["scientific_input_set_sha256"] = "6" * 64
    _write(execution_path, execution)
    execution_identity = _identity(execution_path)

    open_path = attempt_dir / "attempt-open.json"
    open_record = json.loads(open_path.read_text(encoding="utf-8"))
    open_record["input_set_identity"] = input_identity
    open_record["attempt_execution_identity"] = execution_identity
    _write(open_path, open_record)

    with pytest.raises(AUTH.AuthorityError, match="attempt input-set joins drifted"):
        AUTH.replay_campaign(fixture["preregistration_path"])


def test_prepare_baseline_provenance_bootstraps_the_clean_checkout_consumer(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    produced = AUTH.prepare_baseline_provenance(
        fixture["preregistration_path"],
        repository_root=fixture["repository"],
    )
    provenance_path = Path(produced["campaign_provenance_identity"]["path"])
    replayed = BASELINE.campaign_provenance(provenance_path)

    assert replayed == produced["campaign_provenance"]
    assert replayed["schema_version"] == AUTH.BASELINE_PROVENANCE_SCHEMA == BASELINE.CAMPAIGN_PROVENANCE_SCHEMA
    assert replayed["import_mode"] == AUTH.BASELINE_IMPORT_MODE == BASELINE.CHECKOUT_IMPORT_MODE
    assert set(replayed) == {
        "authority_scope",
        "campaign_root_identity",
        "git_identity",
        "import_mode",
        "input_identities",
        "package",
        "repository_head",
        "repository_root",
        "repository_tree",
        "schema_version",
    }
    assert set(replayed["input_identities"]) == set(AUTH.BASELINE_CHECKOUT_INPUT_PATHS)
    for role, relative in AUTH.BASELINE_CHECKOUT_INPUT_PATHS.items():
        assert replayed["input_identities"][role]["path"] == str(Path(fixture["repository"]) / relative)


def test_baseline_provenance_ignores_ambient_git_repository_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "ambient.git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "ambient-worktree"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "ambient-index"))

    produced = AUTH.prepare_baseline_provenance(
        fixture["preregistration_path"],
        repository_root=fixture["repository"],
    )

    assert BASELINE.campaign_provenance(
        Path(produced["campaign_provenance_identity"]["path"])
    ) == produced["campaign_provenance"]


def test_prepare_baseline_provenance_requires_the_git_top_level(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    nested = Path(fixture["repository"]) / "untracked-nested-checkout"
    nested.mkdir()

    with pytest.raises(AUTH.AuthorityError, match="not the Git top-level"):
        AUTH.prepare_baseline_provenance(
            fixture["preregistration_path"],
            repository_root=nested,
        )


def test_clean_checkout_consumer_requires_the_git_top_level(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    produced = AUTH.prepare_baseline_provenance(
        fixture["preregistration_path"],
        repository_root=fixture["repository"],
    )
    provenance_path = Path(produced["campaign_provenance_identity"]["path"])
    nested = Path(fixture["repository"]) / "untracked-nested-checkout"
    nested_inputs: dict[str, dict[str, object]] = {}
    for role, relative in AUTH.BASELINE_CHECKOUT_INPUT_PATHS.items():
        source = Path(fixture["repository"]) / relative
        destination = nested / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        nested_inputs[role] = _detached(_identity(destination))
    record = copy.deepcopy(produced["campaign_provenance"])
    record["repository_root"] = str(nested)
    record["input_identities"] = nested_inputs
    provenance_path.write_bytes(BASELINE.canonical_json(record))

    with pytest.raises(BASELINE.AdmissionError, match="not the Git top-level"):
        BASELINE.campaign_provenance(provenance_path)


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("head", "HEAD differs"),
        ("dirty", "tracked tree or index"),
        ("input", "input differs from the campaign root"),
    ),
)
def test_prepare_baseline_provenance_rejects_checkout_drift_before_publication(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    repository = Path(fixture["repository"])
    if case == "head":
        Path(fixture["repairable_tool"]).write_text("VERSION = 2\n", encoding="utf-8")
        _commit(repository, "different head")
    elif case == "dirty":
        Path(fixture["tracked"]).write_text("dirty\n", encoding="utf-8")
    else:
        candidate = fixture["checkout_inputs"]["candidate_placements"]
        Path(candidate).write_bytes(_canonical({"facility_pools": {"drifted": []}}))

    with pytest.raises(AUTH.AuthorityError, match=message):
        AUTH.prepare_baseline_provenance(
            fixture["preregistration_path"],
            repository_root=repository,
        )
    assert not (Path(fixture["preregistration"]["baseline_rebuilt_model_path"]).parent / "campaign-provenance.json").exists()


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("root", "detached identity mismatch"),
        ("package", "detached identity mismatch"),
        ("input", "detached identity mismatch"),
        ("dirty", "tracked tree or index"),
        ("head", "HEAD or tree drifted"),
        ("tree", "HEAD or tree drifted"),
        ("git", "root/package/Git join drifted"),
    ),
)
def test_clean_checkout_provenance_replay_fails_closed_on_drift(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    produced = AUTH.prepare_baseline_provenance(
        fixture["preregistration_path"],
        repository_root=fixture["repository"],
    )
    provenance_path = Path(produced["campaign_provenance_identity"]["path"])
    if case == "root":
        campaign_root_path = Path(produced["campaign_provenance"]["campaign_root_identity"]["path"])
        campaign_root_path.write_bytes(campaign_root_path.read_bytes() + b" ")
    elif case == "package":
        Path(fixture["package_manifest_path"]).write_bytes(b"drifted package manifest\n")
    elif case == "input":
        Path(fixture["checkout_inputs"]["candidate_placements"]).write_bytes(
            _canonical({"facility_pools": {"drifted": []}})
        )
    elif case == "dirty":
        Path(fixture["tracked"]).write_text("dirty\n", encoding="utf-8")
    elif case == "head":
        Path(fixture["repairable_tool"]).write_text("VERSION = 2\n", encoding="utf-8")
        _commit(Path(fixture["repository"]), "different head")
    else:
        record = copy.deepcopy(produced["campaign_provenance"])
        if case == "tree":
            record["repository_tree"] = "0" * 40
        else:
            record["git_identity"] = _detached(_identity(Path(fixture["package_manifest_path"])))
        provenance_path.write_bytes(BASELINE.canonical_json(record))

    with pytest.raises(BASELINE.AdmissionError, match=message):
        BASELINE.campaign_provenance(provenance_path)


def test_tracked_dirty_repository_is_rejected_without_consuming_attempt(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["tracked"].write_text("dirty\n", encoding="utf-8")
    with pytest.raises(AUTH.AuthorityError, match="not clean"):
        _prepare(fixture)
    slot_root = Path(fixture["preregistration"]["slot_roots"][AUTH.contract.ARM_SEQUENCE[0]])
    assert not slot_root.exists()


@pytest.mark.parametrize(
    "case",
    (
        "slot_argument",
        "ordinal_argument",
        "selection_slot",
        "selection_ordinal",
        "preregistration",
        "attempt_execution",
        "two_key_selection",
    ),
)
def test_bind_rejects_selection_that_does_not_formally_join_active_attempt(tmp_path: Path, case: str) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture)
    produced = _produce(fixture, prepared)
    selection_path = Path(produced["selection_identity"]["path"])
    bind_slot = slot
    bind_ordinal = 1

    if case == "slot_argument":
        bind_slot = AUTH.contract.ARM_SEQUENCE[1]
    elif case == "ordinal_argument":
        bind_ordinal = 2
    else:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        if case == "selection_slot":
            selection["slot"] = AUTH.contract.ARM_SEQUENCE[1]
        elif case == "selection_ordinal":
            selection["attempt_ordinal"] = 2
        elif case == "preregistration":
            selection["preregistration_sha256"] = "0" * 64
        elif case == "attempt_execution":
            selection["attempt_execution_identity"]["sha256"] = "0" * 64
        else:
            selection = {"purpose": "test selection", "schema_version": "test-selection-v1"}
        _write(selection_path, selection)

    with pytest.raises(AUTH.AuthorityError):
        AUTH.bind_selection(
            fixture["preregistration_path"],
            slot=bind_slot,
            attempt_ordinal=bind_ordinal,
            selection_path=selection_path,
        )


def test_handwritten_gate_cannot_credibly_close_formal_selection(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture)
    attempt_dir = Path(prepared["attempt_dir"])
    produced = _produce(fixture, prepared)
    selection_path = Path(produced["selection_identity"]["path"])
    AUTH.bind_selection(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        selection_path=selection_path,
    )
    gate_path = _fake_credible_gate(
        attempt_dir,
        slot=slot,
        selection_identity=produced["selection_identity"],
    )
    with pytest.raises(AUTH.AuthorityError):
        AUTH.close_attempt(
            fixture["preregistration_path"],
            slot=slot,
            attempt_ordinal=1,
            outcome=AUTH.CREDIBLE_TERMINAL,
            evidence_paths={"arm_gate": gate_path},
        )


def test_preregistration_and_result_hash_tampering_fail_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture)
    AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="EXPECTED",
    )
    result_path = Path(prepared["attempt_dir"]) / "attempt-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["failure_code"] = "TAMPERED"
    _write(result_path, result)
    with pytest.raises(AUTH.AuthorityError, match="envelope"):
        AUTH.replay_campaign(fixture["preregistration_path"])

    preregistration_path = fixture["preregistration_path"]
    original = preregistration_path.read_bytes()
    preregistration_path.write_bytes(original + b"\n")
    with pytest.raises(AUTH.AuthorityError, match="canonical"):
        AUTH.replay_campaign(preregistration_path)


def test_source_contains_no_permanent_freeze_or_hostile_same_uid_mechanism() -> None:
    source = (RESEARCH_DIR / "ab16_authority_v1.py").read_text(encoding="utf-8")
    retired_terms = (
        "immediate-stop",
        "CAMPAIGN_IMMEDIATE_STOPPED",
        "renameat2",
        "AF_UNIX",
        "PathFinder",
        "same-UID",
        ".chmod(",
        "os.chmod(",
    )
    assert all(term not in source for term in retired_terms)


def test_attempt_input_digest_recomputes_from_snapshots(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    prepared = _prepare(fixture)
    input_path = Path(prepared["attempt_dir"]) / "attempt-input-set.json"
    record = json.loads(input_path.read_text(encoding="utf-8"))
    assert record["input_set_sha256"] == AUTH.contract.attempt_input_set_sha256(
        preregistration_sha256=record["preregistration_sha256"],
        repository_head=record["repository_head"],
        strict_input_identities=record["strict_input_identities"],
        tool_identities=record["tool_identities"],
    )
    assert hashlib.sha256(Path(record["preregistration_identity"]["path"]).read_bytes()).hexdigest() == record[
        "preregistration_sha256"
    ]


def test_atomic_publication_recovers_partial_pending_without_exposing_final(tmp_path: Path) -> None:
    publication_dir = tmp_path / "atomic-partial"
    publication_dir.mkdir()
    final_path = publication_dir / "result.json"
    raw = _canonical({"payload": "x" * 16_384, "schema_version": "atomic-test-v1"})

    crashed = _run_atomic_publication_crash(final_path, raw, phase="write")

    assert crashed.returncode == -signal.SIGKILL
    assert not final_path.exists()
    pending = _pending_paths(final_path)
    assert len(pending) == 1
    assert 0 < pending[0].stat().st_size < len(raw)

    AUTH.recover_staging(final_path)
    assert not _pending_paths(final_path)
    published = AUTH._write_bytes_exclusive(final_path, raw)  # noqa: SLF001
    assert published["sha256"] == hashlib.sha256(raw).hexdigest()
    assert final_path.read_bytes() == raw
    assert final_path.stat().st_nlink == 1


def test_atomic_publication_recovers_linked_pending_alias(tmp_path: Path) -> None:
    publication_dir = tmp_path / "atomic-linked"
    publication_dir.mkdir()
    final_path = publication_dir / "result.json"
    raw = _canonical({"payload": "complete", "schema_version": "atomic-test-v1"})

    crashed = _run_atomic_publication_crash(final_path, raw, phase="link")

    assert crashed.returncode == -signal.SIGKILL
    assert final_path.read_bytes() == raw
    pending = _pending_paths(final_path)
    assert len(pending) == 1
    assert pending[0].stat().st_ino == final_path.stat().st_ino
    assert final_path.stat().st_nlink == 2

    AUTH.recover_staging(final_path)
    assert not _pending_paths(final_path)
    assert final_path.read_bytes() == raw
    assert final_path.stat().st_nlink == 1


def test_abandon_incomplete_prepare_then_allocate_next_attempt(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    preregistration = fixture["preregistration"]
    assert isinstance(preregistration, dict)
    attempt_dir = Path(preregistration["slot_roots"][slot]) / "attempt-0001"

    crashed = _run_prepare_before_open_crash(fixture, slot=slot)

    assert crashed.returncode == -signal.SIGKILL
    assert attempt_dir.is_dir()
    assert not (attempt_dir / "attempt-open.json").exists()
    with pytest.raises(AUTH.AuthorityError):
        AUTH.replay_campaign(fixture["preregistration_path"])

    abandoned = AUTH.abandon_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        failure_code="PREPARE_PROCESS_KILLED",
    )
    assert abandoned["status"] == "ATTEMPT_ABANDONED"
    second = _prepare(fixture, slot=slot)
    assert second["attempt_ordinal"] == 2
    assert Path(second["attempt_dir"]).name == "attempt-0002"


def test_incomplete_close_partial_envelope_is_recoverable_and_reentrant(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture, slot=slot)
    result_path = Path(prepared["attempt_dir"]) / "attempt-result.json"

    crashed = _run_incomplete_close_write_crash(fixture, slot=slot, attempt_ordinal=1)

    assert crashed.returncode == -signal.SIGKILL
    assert not result_path.exists()
    pending = _pending_paths(result_path)
    assert len(pending) == 1
    assert pending[0].stat().st_size > 0
    assert AUTH.replay_campaign(fixture["preregistration_path"])["active_attempt"] is not None

    AUTH.recover_staging(result_path)
    closed = AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="INJECTED_CLOSE_CRASH",
    )
    assert closed["retry_disposition"] == "SAME_SLOT_RETRY_ALLOWED"
    assert not _pending_paths(result_path)
    assert result_path.stat().st_nlink == 1
    envelope = json.loads(result_path.read_text(encoding="utf-8"))
    assert envelope["failure_code"] == "INJECTED_CLOSE_CRASH"
