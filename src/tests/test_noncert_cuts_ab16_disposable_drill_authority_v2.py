from __future__ import annotations

import base64
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


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load(
    "noncert_cuts_ab16_disposable_drill_authority_v2_tested",
    TOOLS / "disposable_drill_authority_v2.py",
)


FIXTURE_REPOSITORY_HEAD = BUILDER.HISTORY_FREEZE_HEAD


def _history_manifest(tmp_path: Path) -> tuple[Path, Path]:
    history_root = tmp_path / "immutable-history-repository"
    frozen_root = ".artifacts/noncert_cuts_ab16_20260724/failed-gate-a-a001"
    members: list[dict[str, object]] = []
    for relative, raw, mode in (
        (f"{frozen_root}/terminal.json", b'{"status":"FAILED"}\n', 0o400),
        (
            "docs/research/noncert_cuts_ab16_20260724/fixture_v1.py",
            b"# immutable v1 fixture\n",
            0o444,
        ),
    ):
        path = history_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(mode)
        identity = BUILDER.lifecycle.snapshot_regular(path).identity
        members.append({**identity, "path": relative})
    manifest = {
        "created_at_utc": "2026-07-24T05:27:12Z",
        "file_count": len(members),
        "files": members,
        "frozen_roots": [frozen_root],
        "purpose": BUILDER.HISTORY_FREEZE_PURPOSE,
        "repository_head": BUILDER.HISTORY_FREEZE_HEAD,
        "repository_root": str(history_root),
        "schema_version": BUILDER.HISTORY_FREEZE_SCHEMA,
        "v1_source_glob": "docs/research/noncert_cuts_ab16_20260724/*_v1.py",
    }
    manifest_path = history_root / ".artifacts/noncert_cuts_ab16_20260724/history-freeze-a001/manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(BUILDER.bootstrap.authority.canonical_json(manifest))
    manifest_path.chmod(0o444)
    return manifest_path, history_root


def _inputs(tmp_path: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    strict: dict[str, Path] = {}
    for role in sorted(BUILDER.bootstrap.STRICT_INPUT_ROLES):
        if role == "history_freeze_manifest":
            strict[role], _ = _history_manifest(tmp_path)
            continue
        path = tmp_path / "inputs" / role
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture {role}\n")
        strict[role] = path

    system: dict[str, Path] = {}
    for role in sorted(BUILDER.bootstrap.SYSTEM_TOOL_ROLES):
        path = tmp_path / "system" / role
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fixture {role}\n".encode())
        path.chmod(0o755)
        system[role] = path
    return strict, system


def _capture(
    tmp_path: Path,
    system: dict[str, Path],
) -> dict[str, object]:
    authority = BUILDER.bootstrap.authority
    manager = tmp_path / "manager"
    manager.write_bytes(b"fixture manager\n")
    full = lambda path: authority.full_identity(  # noqa: E731
        authority.snapshot_regular(path)
    )
    attestor = BUILDER.bootstrap.V4_RESEARCH_DIR / "manager_attestor_v4.py"
    epoch = {
        "attestation_toolchain": {
            "attestor": full(attestor),
            "python": full(system["attestor_python"]),
            "sudo": full(system["sudo"]),
        },
        "attestor_ast_audit": authority.audit_attestor_source(attestor.read_bytes()),
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.77",
        "manager_executable": full(manager),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": full(system["busctl"])},
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
    toolchain = epoch["attestation_toolchain"]
    invocation = {
        "argv": [
            toolchain["sudo"]["path"],
            "-n",
            "--",
            toolchain["python"]["path"],
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
        "stdin_sha256": toolchain["attestor"]["sha256"],
        "stdin_size_bytes": toolchain["attestor"]["size_bytes"],
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
        "capture_protocol": ("two-round-before-read-only-attestor-after-transcript-v4"),
        "rounds": rounds,
        "schema": authority.MANAGER_EPOCH_TRANSCRIPT_SCHEMA,
    }
    authority.validate_manager_epoch(epoch)
    authority.validate_manager_epoch_capture_transcript(
        transcript,
        expected_epoch=epoch,
    )
    return {"manager_epoch": epoch, "transcript": transcript}


def _capability(
    *,
    busctl_identity: dict[str, object],
    manager_epoch: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    methods = {
        name: {
            "in_signature": "s",
            "interface": "org.freedesktop.systemd1.Manager",
            "out_signature": "-",
        }
        for name in ("RefUnit", "UnrefUnit")
    }
    digest = BUILDER.lifecycle.epoch_digest(manager_epoch)
    transcript = {
        "argv": [
            "busctl",
            "--user",
            "introspect",
            "org.freedesktop.systemd1",
            "/org/freedesktop/systemd1",
            "org.freedesktop.systemd1.Manager",
        ],
        "busctl_identity": BUILDER._identity(busctl_identity),  # noqa: SLF001
        "exit_code": 0,
        "manager_epoch_digest": digest,
        "purpose": "AB16_GATE_A_REFERENCE_CAPABILITY_RAW_TRANSCRIPT",
        "schema_version": "noncert-cuts-ab16-reference-capability-transcript-v1",
        "stderr": "",
        "stdout": (".RefUnit method s - -\n.UnrefUnit method s - -\n"),
    }
    receipt = {
        "manager_epoch_digest": digest,
        "methods": methods,
        "purpose": "AB16_GATE_A_REFERENCE_CAPABILITY_REPLAY",
        "schema_version": "noncert-cuts-ab16-reference-capability-v1",
        "status": "PASS",
        "verdict": "REFUNIT_UNREFUNIT_EXACT_SURFACE_PASS",
    }
    return transcript, receipt


def _build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, dict[str, Path], dict[str, Path], dict[str, object]]:
    strict, system = _inputs(tmp_path)
    observed = BUILDER.bootstrap.observe_planned_sources(
        strict_input_paths=strict,
        system_tool_paths=system,
    )
    capture = _capture(tmp_path, system)
    monkeypatch.setattr(
        BUILDER,
        "_capture_live_manager_epoch",
        lambda _: copy.deepcopy(capture),
    )
    monkeypatch.setattr(BUILDER, "_capture_reference_capability", _capability)
    monkeypatch.setattr(
        BUILDER,
        "_observe_repository_head",
        lambda _repository, _planned: FIXTURE_REPOSITORY_HEAD,
    )
    monkeypatch.setenv(
        "DBUS_SESSION_BUS_ADDRESS",
        "unix:path=/run/user/1000/bus",
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    destination = tmp_path / "drill-v2-fixture-a001"
    result = BUILDER.build_disposable_drill_authority(
        output_dir=destination,
        repository_root=ROOT,
        repository_head=FIXTURE_REPOSITORY_HEAD,
        run_nonce=destination.name,
        expected_planned_source_set_digest=observed["planned_source_set_digest"],
        strict_input_paths=strict,
        system_tool_paths=system,
    )
    return destination, strict, system, result


def test_v2_authority_seals_exact_surface_and_never_authorizes_formal_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination, strict, system, result = _build(tmp_path, monkeypatch)

    pre_run = json.loads((destination / "attempt/pre-run-authority.json").read_text())
    selection = json.loads((destination / "attempt/selection.json").read_text())
    authority_ready = json.loads((destination / "authority/authority-ready.json").read_text())
    package_manifest = json.loads((destination / "authority/package/package-manifest.json").read_text())
    planned_sources = json.loads((destination / "authority/planned-source-identities.json").read_text())
    capability = json.loads((destination / "authority/reference-capability.json").read_text())
    history = json.loads((destination / "authority/history-freeze-replay.json").read_text())

    assert result["formal_campaign_created"] is False
    assert authority_ready["formal_campaign_created"] is False
    assert authority_ready["authorizations"] == {
        "arm_launch_authorized": False,
        "formal_campaign_creation_authorized": False,
        "solver_run_authorized": False,
    }
    assert selection["authorizations"] == {
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": False,
        "production_certified_authorized": False,
        "solver_run_authorized": False,
    }
    assert pre_run["arm_launch_authorized"] is False
    assert pre_run["solver_run_authorized"] is False
    assert package_manifest["authorizations"] == {
        "arm_launch_authorized": False,
        "formal_campaign_creation_authorized": False,
        "solver_run_authorized": False,
    }

    assert set(pre_run["tool_identities"]) == set(BUILDER.lifecycle.TOOL_ROLES)
    assert set(pre_run["output_paths"]) == set(BUILDER.lifecycle.OUTPUT_ROLES)
    expected_phases = set(BUILDER.lifecycle.PHASES) - {"preselection"}
    assert set(pre_run["epoch_observation_paths"]) == expected_phases
    assert set(pre_run["epoch_transcript_paths"]) == expected_phases
    assert pre_run["schema_version"].endswith("-v2")
    assert (
        Path(pre_run["tool_identities"]["organic_resource_lifecycle"]["path"]).name
        == "organic_resource_lifecycle_v2.py"
    )
    assert (
        Path(pre_run["tool_identities"]["organic_resource_verifier"]["path"]).name == "organic_resource_verifier_v2.py"
    )
    assert (
        Path(pre_run["tool_identities"]["organic_unit_orchestrator"]["path"]).name == "organic_unit_orchestrator_v2.py"
    )
    expected_source_roles = {
        *(f"script.{role}" for role in BUILDER.bootstrap.SCRIPT_TOOL_FILES),
        *(f"system.{role}" for role in BUILDER.bootstrap.SYSTEM_TOOL_ROLES),
        *(f"input.{role}" for role in BUILDER.bootstrap.STRICT_INPUT_ROLES),
    }
    assert set(planned_sources["planned_source_identities"]) == expected_source_roles
    assert planned_sources["planned_source_set_digest"] == authority_ready["planned_source_set_digest"]

    sealed_lib = package_manifest["sealed_payload_identities"]["libsystemd"]
    source_lib = package_manifest["external_source_identities"]["system.libsystemd"]
    assert sealed_lib == pre_run["tool_identities"]["libsystemd"]
    assert sealed_lib["path"] == str(destination / "authority/package/payload/libsystemd.so")
    assert sealed_lib["sha256"] == source_lib["sha256"]
    assert sealed_lib["size_bytes"] == source_lib["size_bytes"]
    assert Path(sealed_lib["path"]).read_bytes() == system["libsystemd"].read_bytes()
    assert stat.S_IMODE(Path(sealed_lib["path"]).stat().st_mode) == 0o444
    seal_lines = (destination / "authority/package/SHA256SUMS").read_text().splitlines()
    assert seal_lines == [
        (f"{pre_run['package']['manifest_identity']['sha256']}  package-manifest.json"),
        f"{sealed_lib['sha256']}  payload/libsystemd.so",
    ]

    assert capability["status"] == "PASS"
    assert capability["methods"] == {
        "RefUnit": {
            "in_signature": "s",
            "interface": "org.freedesktop.systemd1.Manager",
            "out_signature": "-",
        },
        "UnrefUnit": {
            "in_signature": "s",
            "interface": "org.freedesktop.systemd1.Manager",
            "out_signature": "-",
        },
    }
    assert capability["transcript_identity"] == pre_run["reference_capability_transcript_identity"]
    assert history["status"] == "PASS"
    assert history["file_count"] == 2
    assert history["authorizations"] == {
        "formal_campaign_creation_authorized": False,
        "organic_arm_launch_authorized": False,
    }
    assert history["manifest_identity"] == pre_run["strict_input_identities"]["input.history_freeze_manifest"]
    assert all(pre_run["preflight_results"].values())
    BUILDER.verifier.validate_pre_run_authority(pre_run)

    assert sorted(path.name for path in (destination / "attempt").iterdir()) == [
        "pre-run-authority.json",
        "selection.json",
    ]
    with pytest.raises(BUILDER.DrillAuthorityError, match="already exists"):
        BUILDER.build_disposable_drill_authority(
            output_dir=destination,
            repository_root=ROOT,
            repository_head=FIXTURE_REPOSITORY_HEAD,
            run_nonce=destination.name,
            expected_planned_source_set_digest=authority_ready["planned_source_set_digest"],
            strict_input_paths=strict,
            system_tool_paths=system,
        )


def test_v2_authority_rejects_source_and_receipt_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strict, system = _inputs(tmp_path / "source")
    observed = BUILDER.bootstrap.observe_planned_sources(
        strict_input_paths=strict,
        system_tool_paths=system,
    )
    strict["project_lock"].write_bytes(b"mutated strict source\n")
    destination = tmp_path / "source" / "drill-v2-source-mutation"
    with pytest.raises(BUILDER.DrillAuthorityError, match="digest drifted"):
        BUILDER.build_disposable_drill_authority(
            output_dir=destination,
            repository_root=ROOT,
            repository_head=FIXTURE_REPOSITORY_HEAD,
            run_nonce=destination.name,
            expected_planned_source_set_digest=observed["planned_source_set_digest"],
            strict_input_paths=strict,
            system_tool_paths=system,
        )
    assert not destination.exists()

    built, built_strict, _, _ = _build(tmp_path / "receipt", monkeypatch)
    pre_run = json.loads((built / "attempt/pre-run-authority.json").read_text())
    strict_source = built_strict["project_lock"]
    original_source = strict_source.read_bytes()
    strict_source.write_bytes(b"post-build strict source mutation\n")
    with pytest.raises(
        BUILDER.verifier.VerificationError,
        match="strict input input.project_lock byte identity drifted",
    ):
        BUILDER.verifier.validate_pre_run_authority(pre_run)
    strict_source.write_bytes(original_source)
    BUILDER.verifier.validate_pre_run_authority(pre_run)

    receipt_path = built / "authority/reference-capability.json"
    original_receipt = receipt_path.read_bytes()
    receipt = json.loads(receipt_path.read_text())
    receipt["verdict"] = "MUTATED_BUT_SELF_CONSISTENT"
    receipt_path.chmod(0o644)
    receipt_path.write_bytes(BUILDER.lifecycle.canonical_json_bytes(receipt))
    receipt_path.chmod(0o444)
    with pytest.raises(
        BUILDER.verifier.VerificationError,
        match="reference_capability_identity",
    ):
        BUILDER.verifier.validate_pre_run_authority(pre_run)
    receipt_path.chmod(0o644)
    receipt_path.write_bytes(original_receipt)
    receipt_path.chmod(0o444)
    BUILDER.verifier.validate_pre_run_authority(pre_run)

    history_path = built / "authority/history-freeze-replay.json"
    history = json.loads(history_path.read_text())
    history["verdict"] = "MUTATED_BUT_SELF_CONSISTENT"
    history_path.chmod(0o644)
    history_path.write_bytes(BUILDER.lifecycle.canonical_json_bytes(history))
    history_path.chmod(0o444)
    with pytest.raises(
        BUILDER.verifier.VerificationError,
        match="history_freeze_replay_identity",
    ):
        BUILDER.verifier.validate_pre_run_authority(pre_run)


def test_history_replay_uses_manifest_repository_not_active_repository(
    tmp_path: Path,
) -> None:
    manifest_path, history_root = _history_manifest(tmp_path)

    replay = BUILDER._replay_history_freeze(  # noqa: SLF001
        manifest_path=manifest_path,
    )

    manifest = json.loads(manifest_path.read_text())
    assert manifest["repository_root"] == str(history_root)
    assert manifest["repository_root"] != str(ROOT)
    assert replay["status"] == "PASS"
    assert replay["file_count"] == 2


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("extra_manifest_field", "schema drifted"),
        ("active_repository_root", "member is missing"),
        ("symlink_repository_root", "root is missing or symlinked"),
        ("member_extra_field", "member schema drifted"),
        ("member_absolute_path", "member path is invalid"),
        ("member_hash", "member byte identity drifted"),
        ("member_mode", "member byte identity drifted"),
        ("member_symlink", "member is missing, non-regular, or symlinked"),
    ),
)
def test_history_replay_fails_closed_on_manifest_root_and_member_drift(
    tmp_path: Path,
    mutation: str,
    match: str,
) -> None:
    manifest_path, history_root = _history_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    if mutation == "extra_manifest_field":
        manifest["unexpected"] = False
    elif mutation == "active_repository_root":
        manifest["repository_root"] = str(ROOT)
    elif mutation == "symlink_repository_root":
        link = tmp_path / "history-root-link"
        link.symlink_to(history_root, target_is_directory=True)
        manifest["repository_root"] = str(link)
    elif mutation == "member_extra_field":
        manifest["files"][0]["unexpected"] = False
    elif mutation == "member_absolute_path":
        manifest["files"][0]["path"] = str(history_root / manifest["files"][0]["path"])
    elif mutation == "member_hash":
        manifest["files"][0]["sha256"] = "0" * 64
    elif mutation == "member_mode":
        manifest["files"][0]["mode"] = 0o444
    elif mutation == "member_symlink":
        member = history_root / manifest["files"][0]["path"]
        target = tmp_path / "history-member-target"
        target.write_bytes(member.read_bytes())
        member.unlink()
        member.symlink_to(target)
    else:
        raise AssertionError(f"unknown mutation: {mutation}")
    if mutation != "member_symlink":
        manifest_path.chmod(0o644)
        manifest_path.write_bytes(BUILDER.bootstrap.authority.canonical_json(manifest))
        manifest_path.chmod(0o444)

    with pytest.raises(BUILDER.DrillAuthorityError, match=match):
        BUILDER._replay_history_freeze(  # noqa: SLF001
            manifest_path=manifest_path,
        )


def test_history_replay_rejects_symlink_manifest(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _history_manifest(tmp_path)
    manifest_link = tmp_path / "manifest-link.json"
    manifest_link.symlink_to(manifest_path)

    with pytest.raises(BUILDER.DrillAuthorityError, match="symlink"):
        BUILDER._replay_history_freeze(  # noqa: SLF001
            manifest_path=manifest_link,
        )
