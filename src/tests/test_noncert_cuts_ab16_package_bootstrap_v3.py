from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
BOOTSTRAP_PATH = RESEARCH / "ab16_campaign_bootstrap_v2.py"
VERIFIER_PATH = RESEARCH / "package_independent_verifier_v1.py"
VERIFIER_PACKAGE_PATH = "payload/tool.package_independent_verifier_v1.py"
NATIVE_HELPER_PATH = RESEARCH / "ab16_native_budget_helper_x86_64_v1.so"
NATIVE_HELPER_PACKAGE_PATH = "payload/system.native_budget_helper.bin"
NATIVE_HELPER_WRAPPER_PATH = RESEARCH / "ab16_native_budget_helper_v1.py"
NATIVE_HELPER_WRAPPER_PACKAGE_PATH = (
    "payload/tool.ab16_native_budget_helper_v1.py"
)
FINAL_RELEASE_ACTOR_PATH = RESEARCH / "ab16_final_release_actor_v1.py"
FINAL_RELEASE_ACTOR_PACKAGE_PATH = (
    "payload/tool.ab16_final_release_actor_v1.py"
)


def _load() -> ModuleType:
    name = "_test_noncert_cuts_ab16_package_bootstrap_v3"
    spec = importlib.util.spec_from_file_location(name, BOOTSTRAP_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bootstrap() -> ModuleType:
    return _load()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _full_identity(path: Path) -> dict[str, object]:
    metadata = path.stat()
    raw = path.read_bytes()
    mode = stat.S_IMODE(metadata.st_mode)
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": mode,
        "mode_octal": f"{mode:04o}",
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _detached(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _write_package(
    tmp_path: Path,
    *,
    manifest_schema: str = "noncert-cuts-campaign-authority-manifest-v5",
    forge_verifier_member: bool = False,
) -> tuple[
    Path,
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    package = tmp_path / "package"
    payload = package / "payload"
    payload.mkdir(parents=True)
    verifier_raw = VERIFIER_PATH.read_bytes()
    members = {
        VERIFIER_PACKAGE_PATH: verifier_raw,
        NATIVE_HELPER_PACKAGE_PATH: NATIVE_HELPER_PATH.read_bytes(),
        NATIVE_HELPER_WRAPPER_PACKAGE_PATH: (
            NATIVE_HELPER_WRAPPER_PATH.read_bytes()
        ),
        FINAL_RELEASE_ACTOR_PACKAGE_PATH: (
            FINAL_RELEASE_ACTOR_PATH.read_bytes()
        ),
        "payload/input.fixture.json": _canonical({"fixture": "value"}),
    }
    for relative, raw in members.items():
        member = package / relative
        member.write_bytes(raw)
        member.chmod(0o600)
    member_records: list[dict[str, object]] = []
    source_records: list[dict[str, object]] = []
    for ordinal, (relative, raw) in enumerate(sorted(members.items()), start=1):
        digest = hashlib.sha256(raw).hexdigest()
        member_records.append(
            {
                "path": relative,
                "sha256": (
                    "0" * 64
                    if forge_verifier_member and relative == VERIFIER_PACKAGE_PATH
                    else digest
                ),
                "size_bytes": len(raw),
            }
        )
        source_mode = (
            0o555
            if relative == NATIVE_HELPER_PACKAGE_PATH
            else 0o600
        )
        source_records.append(
            {
                "package_path": relative,
                "parse_json": relative.endswith(".json"),
                "role": Path(relative).name,
                "source_identity": {
                    "device": ordinal,
                    "inode": ordinal,
                    "mode": source_mode,
                    "mode_octal": f"{source_mode:04o}",
                    "path": f"/predeclared/{Path(relative).name}",
                    "sha256": digest,
                    "size_bytes": len(raw),
                },
            }
        )
    manager_epoch = {"schema": "fixture-manager-epoch-v1"}
    manifest = {
        "authorization_semantics": (
            "byte qualification only; package PASS cannot launch any child"
        ),
        "external_sources": source_records,
        "manager_epoch": manager_epoch,
        "package_members": member_records,
        "repository_head": "1" * 40,
        "run_nonce": "run-fixture-0001",
        "schema": manifest_schema,
        "seal_contract": {
            "package_id": "sha256(SHA256SUMS exact bytes)",
            "sha256sums_domain": (
                "all regular files below package except SHA256SUMS"
            ),
            "writes_after_seal": "forbidden",
        },
    }
    manifest_raw = _canonical(manifest)
    manifest_path = package / "package-manifest.json"
    manifest_path.write_bytes(manifest_raw)
    manifest_path.chmod(0o600)
    sealed = {**members, "package-manifest.json": manifest_raw}
    seal_raw = "".join(
        f"{hashlib.sha256(sealed[path]).hexdigest()}  {path}\n"
        for path in sorted(sealed)
    ).encode("ascii")
    seal_path = package / "SHA256SUMS"
    seal_path.write_bytes(seal_raw)
    seal_path.chmod(0o600)
    package_record = {
        "manifest_identity": _detached(manifest_path),
        "package_dir": str(package),
        "package_id": hashlib.sha256(seal_raw).hexdigest(),
        "schema": "noncert-cuts-campaign-authority-package-v5",
        "seal_identity": _detached(seal_path),
        "status": "SEALED",
    }
    return package, package_record, _full_identity(VERIFIER_PATH), manager_epoch


def _run(
    bootstrap: ModuleType,
    package: Path,
    package_record: dict[str, object],
    source_identity: dict[str, object],
    manager_epoch: dict[str, object],
) -> bytes:
    native_identity = _full_identity(NATIVE_HELPER_PATH)
    native_identity["requested_path"] = str(NATIVE_HELPER_PATH)
    return bootstrap._run_package_independent_verifier(  # noqa: SLF001
        package_dir=package,
        package=package_record,
        verifier_source_identity=source_identity,
        python_path=Path(sys.executable),
        repository_head="1" * 40,
        run_nonce="run-fixture-0001",
        manager_epoch=manager_epoch,
        native_helper_source_identity=native_identity,
    )


def test_selected_fd_verifier_and_no_replace_receipt_positive_control(
    tmp_path: Path,
    bootstrap: ModuleType,
) -> None:
    package, package_record, source_identity, manager_epoch = _write_package(
        tmp_path
    )
    raw = _run(
        bootstrap,
        package,
        package_record,
        source_identity,
        manager_epoch,
    )
    result = json.loads(raw)
    assert result["status"] == "PASS"
    assert result["landlock"]["new_path_opens_denied"] is True
    output = tmp_path / "bootstrap-authority"
    output.mkdir()
    final = output / "package-independent-replay.json"
    staged = output / ".package-independent-replay.json.staged"
    identity = bootstrap._publish_package_independent_replay(  # noqa: SLF001
        raw=raw,
        final_path=final,
        staging_path=staged,
    )
    assert identity == _detached(final)
    assert stat.S_IMODE(final.stat().st_mode) == 0o444
    assert not staged.exists()
    with pytest.raises(bootstrap.BootstrapError, match="no-overwrite"):
        bootstrap._publish_package_independent_replay(  # noqa: SLF001
            raw=raw,
            final_path=final,
            staging_path=staged,
        )


def test_published_replay_authorization_retains_exact_fd_until_close(
    tmp_path: Path,
    bootstrap: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, package_record, source_identity, manager_epoch = _write_package(
        tmp_path
    )
    raw = _run(
        bootstrap,
        package,
        package_record,
        source_identity,
        manager_epoch,
    )
    output = tmp_path / "bootstrap-authority"
    output.mkdir()
    final = output / "package-independent-replay.json"
    identity = bootstrap._publish_package_independent_replay(  # noqa: SLF001
        raw=raw,
        final_path=final,
        staging_path=output / ".package-independent-replay.json.staged",
    )
    before = len(os.listdir("/proc/self/fd"))
    retained = bootstrap._retain_published_package_independent_replay(  # noqa: SLF001
        raw=raw,
        result=json.loads(raw),
        identity=identity,
    )
    descriptor = retained.fileno()
    assert len(os.listdir("/proc/self/fd")) == before + 1

    real_close = bootstrap.os.close
    close_count = 0

    def tracked_close(candidate: int) -> None:
        nonlocal close_count
        if candidate == descriptor:
            close_count += 1
        real_close(candidate)

    monkeypatch.setattr(bootstrap.os, "close", tracked_close)
    retained.close()
    retained.close()
    assert close_count == 1
    assert len(os.listdir("/proc/self/fd")) == before


def test_published_replay_authorization_drift_fails_and_closes_once(
    tmp_path: Path,
    bootstrap: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _canonical({"status": "PASS"})
    output = tmp_path / "bootstrap-authority"
    output.mkdir()
    final = output / "package-independent-replay.json"
    identity = bootstrap._publish_package_independent_replay(  # noqa: SLF001
        raw=raw,
        final_path=final,
        staging_path=output / ".package-independent-replay.json.staged",
    )
    retained = bootstrap._retain_published_package_independent_replay(  # noqa: SLF001
        raw=raw,
        result={"status": "PASS"},
        identity=identity,
    )
    descriptor = retained.fileno()
    before = len(os.listdir("/proc/self/fd"))
    real_close = bootstrap.os.close
    close_count = 0

    def tracked_close(candidate: int) -> None:
        nonlocal close_count
        if candidate == descriptor:
            close_count += 1
        real_close(candidate)

    monkeypatch.setattr(bootstrap.os, "close", tracked_close)
    os.chmod(final, 0o644)
    with pytest.raises(
        bootstrap.BootstrapError,
        match="retained package-independent replay identity drifted",
    ):
        retained.close()
    assert close_count == 1
    assert len(os.listdir("/proc/self/fd")) == before - 1


def test_external_pin_drift_fails_before_receipt_publication(
    tmp_path: Path,
    bootstrap: ModuleType,
) -> None:
    package, package_record, source_identity, manager_epoch = _write_package(
        tmp_path
    )
    source_identity["sha256"] = "f" * 64
    with pytest.raises(bootstrap.BootstrapError, match="pre-registration"):
        _run(
            bootstrap,
            package,
            package_record,
            source_identity,
            manager_epoch,
        )
    assert not (tmp_path / "package-independent-replay.json").exists()


def test_candidate_gate_b_and_current_verifier_pin_must_be_identical(
    bootstrap: ModuleType,
) -> None:
    identity = _full_identity(VERIFIER_PATH)
    planned = {"script.package_independent_verifier_v1": identity}
    candidate = {"package_verifier_source_identity": dict(identity)}
    gate_b = {"package_verifier_source_identity": dict(identity)}
    assert (
        bootstrap._require_package_verifier_source_binding(  # noqa: SLF001
            planned=planned,
            candidate=candidate,
            gate_b=gate_b,
        )
        == identity
    )
    gate_b["package_verifier_source_identity"]["sha256"] = "f" * 64
    with pytest.raises(bootstrap.BootstrapError, match="binding drifted"):
        bootstrap._require_package_verifier_source_binding(  # noqa: SLF001
            planned=planned,
            candidate=candidate,
            gate_b=gate_b,
        )


@pytest.mark.parametrize(
    ("manifest_schema", "forge_verifier_member"),
    [
        ("noncert-cuts-campaign-authority-manifest-v4", False),
        ("noncert-cuts-campaign-authority-manifest-v5", True),
    ],
)
def test_cross_version_or_self_manifest_forgery_fails_closed(
    tmp_path: Path,
    bootstrap: ModuleType,
    manifest_schema: str,
    forge_verifier_member: bool,
) -> None:
    package, package_record, source_identity, manager_epoch = _write_package(
        tmp_path,
        manifest_schema=manifest_schema,
        forge_verifier_member=forge_verifier_member,
    )
    with pytest.raises(bootstrap.BootstrapError, match="failed closed"):
        _run(
            bootstrap,
            package,
            package_record,
            source_identity,
            manager_epoch,
        )


def test_receipt_rename_failure_retains_uncommitted_staging(
    tmp_path: Path,
    bootstrap: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, package_record, source_identity, manager_epoch = _write_package(
        tmp_path
    )
    raw = _run(
        bootstrap,
        package,
        package_record,
        source_identity,
        manager_epoch,
    )
    output = tmp_path / "bootstrap-authority"
    output.mkdir()
    final = output / "package-independent-replay.json"
    staged = output / ".package-independent-replay.json.staged"

    def reject_rename(*_args: object) -> None:
        raise OSError(5, "injected rename failure")

    monkeypatch.setattr(bootstrap, "_rename_noreplace_at", reject_rename)
    with pytest.raises(OSError, match="injected rename failure"):
        bootstrap._publish_package_independent_replay(  # noqa: SLF001
            raw=raw,
            final_path=final,
            staging_path=staged,
        )
    assert not final.exists()
    assert staged.read_bytes() == raw
    assert stat.S_IMODE(staged.stat().st_mode) == 0o444
    assert staged.stat().st_blocks * 512 >= (
        bootstrap.PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES
    )


def test_failed_independent_verification_never_reaches_publisher(
    bootstrap: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    published = False

    def reject(**_kwargs: object) -> bytes:
        raise bootstrap.BootstrapError("independent rejection")

    def publish(**_kwargs: object) -> dict[str, object]:
        nonlocal published
        published = True
        return {}

    monkeypatch.setattr(bootstrap, "_run_package_independent_verifier", reject)
    monkeypatch.setattr(
        bootstrap,
        "_publish_package_independent_replay",
        publish,
    )
    with pytest.raises(bootstrap.BootstrapError, match="independent rejection"):
        bootstrap._verify_and_publish_package_independent_replay(  # noqa: SLF001
            package_dir=tmp_path / "package",
            package={},
            verifier_source_identity={},
            python_path=Path(sys.executable),
            repository_head="1" * 40,
            run_nonce="run-fixture-0001",
            manager_epoch={},
            native_helper_source_identity={
                **_full_identity(NATIVE_HELPER_PATH),
                "requested_path": str(NATIVE_HELPER_PATH),
            },
            final_path=tmp_path / "final",
            staging_path=tmp_path / "staged",
        )
    assert published is False


def test_bootstrap_executes_no_later_package_role_before_independent_pass() -> None:
    tree = ast.parse(BOOTSTRAP_PATH.read_text(encoding="utf-8"))
    bootstrap_campaign = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "bootstrap_campaign"
    )
    calls = [
        node
        for node in ast.walk(bootstrap_campaign)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    verifier_boundary = next(
        node
        for node in calls
        if node.func.id == "_verify_and_publish_package_independent_replay"
    )
    first_later_role = next(
        node
        for node in calls
        if node.func.id == "_bootstrap_persistent_budget_runtime"
    )
    assert verifier_boundary.lineno < first_later_role.lineno
