from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import subprocess
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


@dataclass(frozen=True)
class _HistoryGitFixture:
    root: Path
    manifest_path: Path
    manifest_head: str
    archival_head: str
    archival_tree: str
    current_head: str
    current_tree: str
    side_head: str
    frozen_root: str
    artifact_path: Path
    source_paths: tuple[str, ...]
    archival_source_bytes: dict[str, bytes]
    git_path: Path
    git_identity: dict[str, object]


def _git(
    repository: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
) -> bytes:
    git = shutil.which("git")
    assert git is not None
    environment = {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": str(repository.parent / "git-home"),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }
    completed = subprocess.run(
        [git, "-C", str(repository), *arguments],
        check=False,
        close_fds=True,
        env=environment,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    assert completed.returncode == 0, (
        arguments,
        completed.returncode,
        completed.stderr.decode("utf-8", "replace"),
    )
    return completed.stdout


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", "-A")
    _git(
        repository,
        "-c",
        "user.name=AB16 Hermetic Test",
        "-c",
        "user.email=ab16-test@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )
    return _git(repository, "rev-parse", "--verify", "HEAD").decode("ascii").strip()


def _member(relative: str, raw: bytes, mode: int) -> dict[str, object]:
    return {
        "mode": mode,
        "path": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _patch_history_constants(
    monkeypatch: pytest.MonkeyPatch,
    fixture: _HistoryGitFixture,
) -> None:
    values: dict[str, object] = {
        "HISTORY_ARTIFACT_COUNT": 1,
        "HISTORY_FREEZE_HEAD": fixture.manifest_head,
        "HISTORY_FREEZE_MANIFEST_SHA256": hashlib.sha256(
            fixture.manifest_path.read_bytes()
        ).hexdigest(),
        "HISTORY_FREEZE_MANIFEST_SIZE": fixture.manifest_path.stat().st_size,
        "HISTORY_FREEZE_MANIFEST_PATH": fixture.manifest_path,
        "HISTORY_FREEZE_MANIFEST_MODE": 0o400,
        "HISTORY_FROZEN_ROOTS": (fixture.frozen_root,),
        "HISTORY_REPOSITORY_ROOT": fixture.root,
        "HISTORY_SOURCE_COMMIT": fixture.archival_head,
        "HISTORY_SOURCE_COUNT": len(fixture.source_paths),
        "HISTORY_SOURCE_GLOB": (
            "docs/research/noncert_cuts_ab16_20260724/*_v1.py"
        ),
        "HISTORY_SOURCE_TREE": fixture.archival_tree,
    }
    for module in (BUILDER, BUILDER.verifier):
        for name, value in values.items():
            monkeypatch.setattr(module, name, value)


def _history_git_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> _HistoryGitFixture:
    repository = tmp_path / "immutable-history-repository"
    repository.mkdir(parents=True)
    _git(repository, "init", "-q")

    marker = repository / "manifest-head.txt"
    marker.write_text("manifest head\n", encoding="utf-8")
    manifest_head = _commit(repository, "manifest head")

    archival_source_bytes = {
        "docs/research/noncert_cuts_ab16_20260724/alpha_v1.py": (
            b"# archival alpha v1\nVALUE = 'archival-alpha'\n"
        ),
        "docs/research/noncert_cuts_ab16_20260724/beta_v1.py": (
            b"#!/usr/bin/env python3\n# archival beta v1\nVALUE = 'archival-beta'\n"
        ),
    }
    for relative, raw in archival_source_bytes.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o755 if relative.endswith("beta_v1.py") else 0o644)
    archival_head = _commit(repository, "archive failed Gate-A v1 sources")
    archival_tree = (
        _git(repository, "rev-parse", "--verify", f"{archival_head}^{{tree}}")
        .decode("ascii")
        .strip()
    )

    for relative in archival_source_bytes:
        path = repository / relative
        path.write_bytes(
            f"# current successor bytes for {Path(relative).name}\n".encode("utf-8")
        )
    current_head = _commit(repository, "advance live v1 sources")
    current_tree = (
        _git(repository, "rev-parse", "--verify", f"{current_head}^{{tree}}")
        .decode("ascii")
        .strip()
    )

    _git(repository, "checkout", "-q", "--detach", manifest_head)
    side = repository / "side.txt"
    side.write_text("not descended from archival source commit\n", encoding="utf-8")
    side_head = _commit(repository, "side successor")
    _git(repository, "checkout", "-q", "--detach", current_head)

    frozen_root = ".artifacts/noncert_cuts_ab16_20260724/failed-gate-a-a001"
    artifact_path = repository / frozen_root / "terminal.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_raw = b'{"status":"FAILED"}\n'
    artifact_path.write_bytes(artifact_raw)
    artifact_path.chmod(0o400)
    members = [_member(f"{frozen_root}/terminal.json", artifact_raw, 0o400)]
    members.extend(
        _member(
            relative,
            raw,
            0o755 if relative.endswith("beta_v1.py") else 0o644,
        )
        for relative, raw in archival_source_bytes.items()
    )
    manifest = {
        "created_at_utc": "2026-07-24T05:27:12Z",
        "file_count": len(members),
        "files": members,
        "frozen_roots": [frozen_root],
        "purpose": BUILDER.HISTORY_FREEZE_PURPOSE,
        "repository_head": manifest_head,
        "repository_root": str(repository),
        "schema_version": BUILDER.HISTORY_FREEZE_SCHEMA,
        "v1_source_glob": (
            "docs/research/noncert_cuts_ab16_20260724/*_v1.py"
        ),
    }
    manifest_path = (
        repository
        / ".artifacts/noncert_cuts_ab16_20260724/"
        "gate-a-terminal-reference-history-freeze-a001/manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(BUILDER.bootstrap.authority.canonical_json(manifest))
    manifest_path.chmod(0o400)

    selected_git = Path(shutil.which("git") or "").resolve(strict=True)
    git_path = tmp_path / "pinned-system-tools/git"
    git_path.parent.mkdir(parents=True)
    shutil.copy2(selected_git, git_path)
    git_path.chmod(0o755)
    fixture = _HistoryGitFixture(
        root=repository,
        manifest_path=manifest_path,
        manifest_head=manifest_head,
        archival_head=archival_head,
        archival_tree=archival_tree,
        current_head=current_head,
        current_tree=current_tree,
        side_head=side_head,
        frozen_root=frozen_root,
        artifact_path=artifact_path,
        source_paths=tuple(archival_source_bytes),
        archival_source_bytes=archival_source_bytes,
        git_path=git_path,
        git_identity=BUILDER.bootstrap.authority.snapshot_tool(git_path)[1],
    )
    _patch_history_constants(monkeypatch, fixture)
    return fixture


def _inputs(
    tmp_path: Path,
    history: _HistoryGitFixture,
) -> tuple[dict[str, Path], dict[str, Path]]:
    strict: dict[str, Path] = {}
    for role in sorted(BUILDER.bootstrap.STRICT_INPUT_ROLES):
        if role == "history_freeze_manifest":
            strict[role] = history.manifest_path
            continue
        path = tmp_path / "inputs" / role
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture {role}\n")
        strict[role] = path

    system: dict[str, Path] = {}
    for role in sorted(BUILDER.bootstrap.SYSTEM_TOOL_ROLES):
        if role == "git":
            system[role] = history.git_path
            continue
        path = tmp_path / "system" / role
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fixture {role}\n".encode())
        path.chmod(0o755)
        system[role] = path
    return strict, system


def _expected_history_source_records(
    history: _HistoryGitFixture,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for relative in sorted(history.source_paths, key=lambda value: value.encode("utf-8")):
        raw = history.archival_source_bytes[relative]
        executable = relative.endswith("beta_v1.py")
        oid = (
            _git(
                history.root,
                "rev-parse",
                "--verify",
                f"{history.archival_head}:{relative}",
            )
            .decode("ascii")
            .strip()
        )
        records.append(
            {
                "git_blob_oid": oid,
                "git_mode": "100755" if executable else "100644",
                "mode": 0o755 if executable else 0o644,
                "path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
        )
    return records


def _rewrite_history_manifest(
    history: _HistoryGitFixture,
    monkeypatch: pytest.MonkeyPatch,
    manifest: dict[str, object],
) -> None:
    history.manifest_path.chmod(0o600)
    history.manifest_path.write_bytes(
        BUILDER.bootstrap.authority.canonical_json(manifest)
    )
    history.manifest_path.chmod(0o400)
    _patch_history_constants(monkeypatch, history)


def _producer_history_replay(
    history: _HistoryGitFixture,
) -> dict[str, object]:
    return BUILDER._replay_history_freeze(  # noqa: SLF001
        manifest_path=history.manifest_path,
        repository_root=history.root,
        current_repository_head=history.current_head,
        git_identity=history.git_identity,
    )


@pytest.mark.parametrize(
    ("injected", "expected_error"),
    [
        (OSError("injected Git execution failure"), BUILDER.DrillAuthorityError),
        (RuntimeError("injected non-OS failure"), RuntimeError),
    ],
)
def test_producer_history_git_closes_owned_descriptors_on_all_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    injected: BaseException,
    expected_error: type[BaseException],
) -> None:
    history = _history_git_fixture(tmp_path, monkeypatch)
    before = len(tuple(Path("/proc/self/fd").iterdir()))

    def fail_run(*_args: object, **_kwargs: object) -> None:
        raise injected

    monkeypatch.setattr(BUILDER.subprocess, "run", fail_run)
    with pytest.raises(expected_error):
        BUILDER._run_history_git(  # noqa: SLF001
            repository_root=history.root,
            git_identity=history.git_identity,
            arguments=("rev-parse", "--verify", "HEAD"),
        )
    assert len(tuple(Path("/proc/self/fd").iterdir())) == before


def _verify_history_replay(
    tmp_path: Path,
    history: _HistoryGitFixture,
    receipt: dict[str, object],
) -> None:
    receipt_path = tmp_path / "independent-history-replay.json"
    receipt_path.write_bytes(BUILDER.verifier.canonical_json_bytes(receipt))
    receipt_path.chmod(0o444)
    receipt_identity = BUILDER.lifecycle.snapshot_regular(receipt_path).identity
    manifest_identity = BUILDER.lifecycle.snapshot_regular(
        history.manifest_path
    ).identity
    BUILDER.verifier._replay_history_freeze(  # noqa: SLF001
        pre_run={
            "execution_class": "DISPOSABLE_LIVE_DRILL",
            "history_freeze_replay_identity": receipt_identity,
            "repository_git_tool_identity": BUILDER._identity(  # noqa: SLF001
                history.git_identity
            ),
            "repository_head": history.current_head,
            "repository_root": str(history.root),
        },
        strict_inputs={"input.history_freeze_manifest": manifest_identity},
    )


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
) -> tuple[
    Path,
    dict[str, Path],
    dict[str, Path],
    dict[str, object],
    _HistoryGitFixture,
]:
    history = _history_git_fixture(tmp_path, monkeypatch)
    strict, system = _inputs(tmp_path, history)
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
        repository_root=history.root,
        repository_head=history.current_head,
        run_nonce=destination.name,
        expected_planned_source_set_digest=observed["planned_source_set_digest"],
        strict_input_paths=strict,
        system_tool_paths=system,
    )
    return destination, strict, system, result, history


def test_v2_authority_seals_exact_surface_and_never_authorizes_formal_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination, strict, system, result, history_fixture = _build(tmp_path, monkeypatch)

    pre_run = json.loads((destination / "attempt/pre-run-authority.json").read_text())
    selection = json.loads((destination / "attempt/selection.json").read_text())
    authority_ready = json.loads((destination / "authority/authority-ready.json").read_text())
    package_manifest = json.loads((destination / "authority/package/package-manifest.json").read_text())
    planned_sources = json.loads((destination / "authority/planned-source-identities.json").read_text())
    capability = json.loads((destination / "authority/reference-capability.json").read_text())
    history = json.loads((destination / "authority/history-freeze-replay.json").read_text())
    snapshot_manifest = json.loads(
        (destination / "authority/source-snapshot/manifest.json").read_text()
    )
    snapshot_receipt = json.loads(
        (
            destination
            / "authority/source-snapshot/materialization-receipt.json"
        ).read_text()
    )

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
    assert set(history) == {
        "artifact_file_count",
        "authorizations",
        "file_count",
        "manifest_identity",
        "purpose",
        "schema_version",
        "source_file_count",
        "source_materialization",
        "status",
        "verdict",
    }
    assert history["schema_version"] == BUILDER.HISTORY_REPLAY_SCHEMA
    assert history["file_count"] == 3
    assert history["artifact_file_count"] == 1
    assert history["source_file_count"] == 2
    assert history["authorizations"] == {
        "formal_campaign_creation_authorized": False,
        "organic_arm_launch_authorized": False,
    }
    assert history["manifest_identity"] == pre_run["strict_input_identities"]["input.history_freeze_manifest"]
    expected_history_records = _expected_history_source_records(history_fixture)
    assert history["source_materialization"] == {
        "commit": history_fixture.archival_head,
        "file_count": 2,
        "manifest_head_parent": history_fixture.manifest_head,
        "member_digest": hashlib.sha256(
            BUILDER.bootstrap.authority.canonical_json(expected_history_records)
        ).hexdigest(),
        "tree": history_fixture.archival_tree,
    }

    snapshot_root = destination / "authority/source-snapshot/repository"
    assert set(snapshot_manifest) == {
        "authorizations",
        "external_system_identities",
        "import_mode",
        "member_count",
        "member_digest",
        "members",
        "planned_source_set_digest",
        "repository_head",
        "repository_root",
        "schema_version",
        "snapshot_root",
    }
    assert snapshot_manifest["schema_version"] == (
        "noncert-cuts-ab16-disposable-source-snapshot-v1"
    )
    assert snapshot_manifest["authorizations"] == {
        "formal_execution_authorized": False,
        "organic_arm_launch_authorized": False,
        "solver_run_authorized": False,
    }
    assert snapshot_manifest["import_mode"] == (
        "not-executed-disposable-source-snapshot"
    )
    assert snapshot_manifest["repository_root"] == str(history_fixture.root)
    assert snapshot_manifest["repository_head"] == history_fixture.current_head
    assert snapshot_manifest["snapshot_root"] == str(snapshot_root)
    assert snapshot_manifest["planned_source_set_digest"] == planned_sources[
        "planned_source_set_digest"
    ]
    assert pre_run["live_source_provenance_root"] == str(history_fixture.root)
    assert pre_run["sealed_snapshot_execution_root"] == str(snapshot_root)
    assert pre_run["snapshot_manifest_identity"] == (
        BUILDER.lifecycle.snapshot_regular(
            destination / "authority/source-snapshot/manifest.json"
        ).identity
    )
    assert pre_run["snapshot_materialization_receipt_identity"] == (
        BUILDER.lifecycle.snapshot_regular(
            destination
            / "authority/source-snapshot/materialization-receipt.json"
        ).identity
    )
    assert set(snapshot_manifest["external_system_identities"]) == {
        role for role in expected_source_roles if role.startswith("system.")
    }
    for role, identity in snapshot_manifest[
        "external_system_identities"
    ].items():
        assert identity == BUILDER._identity(  # noqa: SLF001
            planned_sources["planned_source_identities"][role]
        )
    expected_snapshot_roles = {
        role for role in expected_source_roles if not role.startswith("system.")
    }
    members = snapshot_manifest["members"]
    assert [member["role"] for member in members] == sorted(expected_snapshot_roles)
    assert snapshot_manifest["member_count"] == len(expected_snapshot_roles)
    assert snapshot_manifest["member_digest"] == hashlib.sha256(
        BUILDER.bootstrap.authority.canonical_json(members)
    ).hexdigest()
    for member in members:
        assert set(member) == {
            "materialized_identity",
            "path",
            "role",
            "source_identity",
        }
        category, name = member["role"].split(".", 1)
        assert member["path"] == f"{category}/{name}"
        assert member["source_identity"] == BUILDER._identity(  # noqa: SLF001
            planned_sources["planned_source_identities"][member["role"]]
        )
        materialized = snapshot_root / member["path"]
        assert member["materialized_identity"] == {
            "mode": 0o444,
            "path": str(materialized),
            "sha256": member["source_identity"]["sha256"],
            "size_bytes": member["source_identity"]["size_bytes"],
        }
        assert materialized.read_bytes() == Path(
            member["source_identity"]["path"]
        ).read_bytes()
    assert set(snapshot_receipt) == {
        "authorizations",
        "manifest_identity",
        "member_count",
        "member_digest",
        "planned_source_set_digest",
        "schema_version",
        "snapshot_root",
        "status",
    }
    assert snapshot_receipt == {
        "authorizations": snapshot_manifest["authorizations"],
        "manifest_identity": pre_run["snapshot_manifest_identity"],
        "member_count": snapshot_manifest["member_count"],
        "member_digest": snapshot_manifest["member_digest"],
        "planned_source_set_digest": snapshot_manifest[
            "planned_source_set_digest"
        ],
        "schema_version": (
            "noncert-cuts-ab16-disposable-source-snapshot-materialization-v1"
        ),
        "snapshot_root": str(snapshot_root),
        "status": "PASS",
    }
    assert (
        pre_run["snapshot_materialization_receipt_identity"]["path"]
        == str(
            destination
            / "authority/source-snapshot/materialization-receipt.json"
        )
    )
    assert all(pre_run["preflight_results"].values())
    BUILDER.verifier.validate_pre_run_authority(pre_run)

    assert sorted(path.name for path in (destination / "attempt").iterdir()) == [
        "pre-run-authority.json",
        "selection.json",
    ]
    with pytest.raises(BUILDER.DrillAuthorityError, match="already exists"):
        BUILDER.build_disposable_drill_authority(
            output_dir=destination,
            repository_root=history_fixture.root,
            repository_head=history_fixture.current_head,
            run_nonce=destination.name,
            expected_planned_source_set_digest=authority_ready["planned_source_set_digest"],
            strict_input_paths=strict,
            system_tool_paths=system,
        )


def test_v2_authority_rejects_source_and_receipt_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    history = _history_git_fixture(source_root, monkeypatch)
    strict, system = _inputs(source_root, history)
    observed = BUILDER.bootstrap.observe_planned_sources(
        strict_input_paths=strict,
        system_tool_paths=system,
    )
    strict["project_lock"].write_bytes(b"mutated strict source\n")
    destination = tmp_path / "source" / "drill-v2-source-mutation"
    with pytest.raises(BUILDER.DrillAuthorityError, match="digest drifted"):
        BUILDER.build_disposable_drill_authority(
            output_dir=destination,
            repository_root=history.root,
            repository_head=history.current_head,
            run_nonce=destination.name,
            expected_planned_source_set_digest=observed["planned_source_set_digest"],
            strict_input_paths=strict,
            system_tool_paths=system,
        )
    assert not destination.exists()

    built, built_strict, _, _, _ = _build(tmp_path / "receipt", monkeypatch)
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


def test_history_replay_materializes_archival_child_not_changed_live_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history_git_fixture(tmp_path, monkeypatch)
    for relative, archival_raw in history.archival_source_bytes.items():
        assert (history.root / relative).read_bytes() != archival_raw
    untracked = _git(
        history.root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).decode("utf-8")
    assert f"?? {history.artifact_path.relative_to(history.root)}" in untracked
    assert f"?? {history.manifest_path.relative_to(history.root)}" in untracked

    replay = _producer_history_replay(history)
    expected_records = _expected_history_source_records(history)
    assert replay == {
        "artifact_file_count": 1,
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
        },
        "file_count": 3,
        "manifest_identity": BUILDER.lifecycle.snapshot_regular(
            history.manifest_path
        ).identity,
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY",
        "schema_version": "noncert-cuts-ab16-terminal-reference-history-replay-v2",
        "source_file_count": 2,
        "source_materialization": {
            "commit": history.archival_head,
            "file_count": 2,
            "manifest_head_parent": history.manifest_head,
            "member_digest": hashlib.sha256(
                BUILDER.bootstrap.authority.canonical_json(expected_records)
            ).hexdigest(),
            "tree": history.archival_tree,
        },
        "status": "PASS",
        "verdict": "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS",
    }
    _verify_history_replay(tmp_path, history, replay)


def test_history_replay_rejects_wrong_manifest_head_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history_git_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(BUILDER, "HISTORY_SOURCE_COMMIT", history.current_head)
    monkeypatch.setattr(BUILDER, "HISTORY_SOURCE_TREE", history.current_tree)

    with pytest.raises(
        BUILDER.DrillAuthorityError,
        match="not the unique manifest-head child",
    ):
        _producer_history_replay(history)


def test_history_replay_rejects_wrong_archival_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history_git_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(BUILDER, "HISTORY_SOURCE_TREE", "0" * 40)

    with pytest.raises(
        BUILDER.DrillAuthorityError,
        match="source commit tree identity drifted",
    ):
        _producer_history_replay(history)


def test_history_replay_rejects_archival_commit_outside_current_ancestry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history_git_fixture(tmp_path, monkeypatch)
    _git(history.root, "checkout", "-q", "--detach", history.side_head)
    try:
        with pytest.raises(
            BUILDER.DrillAuthorityError,
            match="history replay Git query failed closed",
        ):
            BUILDER._replay_history_freeze(  # noqa: SLF001
                manifest_path=history.manifest_path,
                repository_root=history.root,
                current_repository_head=history.side_head,
                git_identity=history.git_identity,
            )
    finally:
        _git(history.root, "checkout", "-q", "--detach", history.current_head)


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("source_path", "Git tree path set drifted"),
        ("source_mode", "Git blob identity drifted"),
        ("source_blob", "Git blob identity drifted"),
        ("member_class", "member class is ambiguous"),
    ),
)
def test_history_replay_rejects_manifest_member_drift_against_archival_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    match: str,
) -> None:
    history = _history_git_fixture(tmp_path, monkeypatch)
    manifest = json.loads(history.manifest_path.read_text())
    artifact = manifest["files"][0]
    source = manifest["files"][1]
    if mutation == "source_path":
        source["path"] = (
            "docs/research/noncert_cuts_ab16_20260724/missing_v1.py"
        )
    elif mutation == "source_mode":
        source["mode"] = 0o755 if source["mode"] == 0o644 else 0o644
    elif mutation == "source_blob":
        source["sha256"] = "0" * 64
    elif mutation == "member_class":
        artifact["path"] = "unclassified/terminal.json"
    else:
        raise AssertionError(f"unknown mutation: {mutation}")
    _rewrite_history_manifest(history, monkeypatch, manifest)

    with pytest.raises(BUILDER.DrillAuthorityError, match=match):
        _producer_history_replay(history)


def test_history_replay_rejects_alternate_object_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history_git_fixture(tmp_path, monkeypatch)
    alternate_path = history.root / ".git/objects/info/alternates"
    alternate_path.write_text("/untrusted/object-store\n", encoding="utf-8")

    with pytest.raises(
        BUILDER.DrillAuthorityError,
        match="alternate object store is forbidden",
    ):
        _producer_history_replay(history)


def test_independent_history_replay_rejects_v1_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history_git_fixture(tmp_path, monkeypatch)
    replay = _producer_history_replay(history)
    replay["schema_version"] = (
        "noncert-cuts-ab16-terminal-reference-history-replay-v1"
    )

    with pytest.raises(
        BUILDER.verifier.VerificationError,
        match="history freeze replay receipt semantics drifted",
    ):
        _verify_history_replay(tmp_path, history, replay)
