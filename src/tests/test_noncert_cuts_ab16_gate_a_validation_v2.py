from __future__ import annotations

import copy
import errno
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import resource
import shutil
import stat
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace

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


VALIDATION = _load(
    "noncert_cuts_ab16_gate_a_validation_v2_tested",
    TOOLS / "gate_a_validation_v2.py",
)


@pytest.mark.parametrize(
    ("mutation", "detail"),
    [
        ("authorization", "arm_launch_authorized"),
        ("authorization", "formal_campaign_creation_authorized"),
        ("authorization", "solver_run_authorized"),
        ("schema", ""),
        ("purpose", ""),
        ("extra", ""),
    ],
)
def test_authority_ready_requires_exact_nonauthorizing_semantics(
    mutation: str,
    detail: str,
) -> None:
    identity = {
        "mode": 0o444,
        "path": "/fixture/authority.json",
        "sha256": "b" * 64,
        "size_bytes": 123,
    }
    digest = "a" * 64
    run_nonce = "drill-fixture-ready"
    record = {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "disposable_drill_ready": True,
        "formal_campaign_created": False,
        "planned_source_set_digest": digest,
        "pre_run_authority_identity": identity,
        "purpose": VALIDATION.drill_authority.RESULT_PURPOSE,
        "run_nonce": run_nonce,
        "schema_version": VALIDATION.drill_authority.RESULT_SCHEMA,
        "selection_identity": identity,
        "status": "PASS",
    }
    assert (
        VALIDATION._validate_authority_ready(  # noqa: SLF001
            record,
            planned_source_set_digest=digest,
            pre_run_identity=identity,
            run_nonce=run_nonce,
            selection_identity=identity,
        )
        == record
    )

    mutated = copy.deepcopy(record)
    if mutation == "authorization":
        mutated["authorizations"][detail] = True
    elif mutation == "schema":
        mutated["schema_version"] = "drifted"
    elif mutation == "purpose":
        mutated["purpose"] = "drifted"
    elif mutation == "extra":
        mutated["unexpected"] = False
    else:  # pragma: no cover - the parameter list is static
        raise AssertionError("unreachable mutation")
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="authority-ready",
    ):
        VALIDATION._validate_authority_ready(  # noqa: SLF001
            mutated,
            planned_source_set_digest=digest,
            pre_run_identity=identity,
            run_nonce=run_nonce,
            selection_identity=identity,
        )


def _regular(path: Path, raw: bytes, *, mode: int = 0o444) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(mode)
    return VALIDATION._snapshot_identity(path)  # noqa: SLF001


def _preflight_stdout() -> bytes:
    items = [
        {
            "nodeid": "src/tests/test_fixture.py::test_fixture",
            "path": "src/tests/test_fixture.py",
        }
    ]
    collection_sha256 = hashlib.sha256(
        b"src/tests/test_fixture.py::test_fixture\n"
    ).hexdigest()
    stage = {
        "collection_count": 1,
        "collection_sha256": collection_sha256,
        "expected_count": 1,
        "expected_sha256": collection_sha256,
        "items": items,
        "manifest_sha256": VALIDATION._collection_manifest_sha256(items),  # noqa: SLF001
        "markexpr": "not slow",
        "module_origins": [],
        "nonce": "1" * 64,
        "schema_version": VALIDATION.PYTEST_COLLECTION_STAGE_SCHEMA,
        "workflow": "full",
    }
    stage_raw = (
        json.dumps(
            stage,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    terminal = {
        "exitstatus": 0,
        "module_origins": [],
        "nonce": "1" * 64,
        "schema_version": VALIDATION.PYTEST_COLLECTION_TERMINAL_SCHEMA,
        "stage_sha256": hashlib.sha256(stage_raw).hexdigest(),
    }
    terminal_raw = (
        json.dumps(
            terminal,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    return (
        b"preflight stdout\n"
        + VALIDATION.PYTEST_COLLECTION_STDOUT_PREFIX
        + stage_raw
        + VALIDATION.PYTEST_COLLECTION_STDOUT_PREFIX
        + terminal_raw
    )


def test_gate_a_independently_parses_exact_collection_projection() -> None:
    expected_sha256 = hashlib.sha256(
        b"src/tests/test_fixture.py::test_fixture\n"
    ).hexdigest()
    projection = VALIDATION._pytest_collection_projection(  # noqa: SLF001
        _preflight_stdout(),
        expected_count=1,
        expected_sha256=expected_sha256,
        tracked_files={"src/tests/test_fixture.py"},
    )

    assert projection["collection_count"] == 1
    assert projection["collection_sha256"] == expected_sha256
    assert projection["workflow"] == "full"
    assert projection["markexpr"] == "not slow"


@pytest.mark.parametrize(
    "mutation",
    [
        "extra-record",
        "manifest",
        "expected-count",
        "terminal-exit",
        "origin-shape",
        "crlf-records",
        "mixed-line-endings",
    ],
)
def test_gate_a_independent_collection_parser_rejects_tamper(
    mutation: str,
) -> None:
    raw = _preflight_stdout()
    prefix = VALIDATION.PYTEST_COLLECTION_STDOUT_PREFIX
    records = [
        json.loads(line.removeprefix(prefix))
        for line in raw.splitlines()
        if line.startswith(prefix)
    ]
    assert len(records) == 2
    stage, terminal = records
    if mutation == "extra-record":
        raw += prefix + b"{}\n"
    elif mutation == "manifest":
        stage["manifest_sha256"] = "0" * 64
    elif mutation == "expected-count":
        stage["expected_count"] = 2
    elif mutation == "terminal-exit":
        terminal["exitstatus"] = 1
    elif mutation == "origin-shape":
        stage["module_origins"] = [{"module": "missing-required-fields"}]
    elif mutation in {"crlf-records", "mixed-line-endings"}:
        lines = raw.splitlines(keepends=True)
        record_indexes = [
            index
            for index, line in enumerate(lines)
            if line.startswith(prefix)
        ]
        assert len(record_indexes) == 2
        lines[record_indexes[0]] = lines[record_indexes[0]][:-1] + b"\r\n"
        if mutation == "crlf-records":
            lines[record_indexes[1]] = lines[record_indexes[1]][:-1] + b"\r\n"
        raw = b"".join(lines)
    else:  # pragma: no cover - static parameter set
        raise AssertionError("unreachable mutation")
    if mutation not in {"extra-record", "crlf-records", "mixed-line-endings"}:
        rendered = [
            (
                json.dumps(
                    record,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("ascii")
            for record in records
        ]
        raw = b"preflight stdout\n" + prefix + rendered[0] + prefix + rendered[1]
    with pytest.raises(VALIDATION.GateAValidationError):
        VALIDATION._pytest_collection_projection(raw)  # noqa: SLF001


def _forwarded_option(kwargs: dict[str, object], option: str) -> str:
    forwarded = kwargs["forwarded"]
    assert isinstance(forwarded, tuple)
    index = forwarded.index(option)
    value = forwarded[index + 1]
    assert isinstance(value, str)
    return value


def _create_forwarded_basetemp(kwargs: dict[str, object]) -> Path:
    basetemp = Path(_forwarded_option(kwargs, "--basetemp"))
    basetemp.mkdir(mode=0o700)
    return basetemp


def _fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, dict[str, object], Path]:
    repository = tmp_path / "repository"
    repository.mkdir(parents=True)
    python_identity = _regular(
        tmp_path / "tools/python3.13",
        b"fixture python executable\n",
        mode=0o755,
    )
    preflight_identity = _regular(
        tmp_path / "inputs/preflight_gate.py",
        b"raise AssertionError('subprocess must be monkeypatched')\n",
        mode=0o444,
    )
    qualification_identity = _regular(
        tmp_path / "tools/ab16_preflight_qualification_v1.py",
        b"raise AssertionError('subprocess must be monkeypatched')\n",
        mode=0o444,
    )
    protocol_identity = _regular(
        tmp_path / "tools/ab16_pytest_collection_protocol_v1.py",
        b"raise AssertionError('subprocess must be monkeypatched')\n",
        mode=0o444,
    )
    plugin_identity = _regular(
        tmp_path / "tools/ab16_pytest_collection_plugin_v1.py",
        b"raise AssertionError('subprocess must be monkeypatched')\n",
        mode=0o444,
    )
    current_tool = VALIDATION._snapshot_identity(Path(VALIDATION.__file__))  # noqa: SLF001
    authority_ready_identity = _regular(
        tmp_path / "drill/authority/authority-ready.json",
        b'{"status":"PASS"}',
    )
    detached_replay_path = tmp_path / "drill/attempt/detached-replay.json"
    detached_replay_identity = _regular(
        detached_replay_path,
        b'{"status":"PASS"}',
    )
    pre_run_identity = _regular(
        tmp_path / "drill/attempt/pre-run-authority.json",
        b'{"status":"PASS"}',
    )
    history_identity = _regular(
        tmp_path / "drill/authority/history-freeze-replay.json",
        b'{"status":"PASS"}',
    )
    capability_identity = _regular(
        tmp_path / "drill/authority/reference-capability.json",
        b'{"status":"PASS"}',
    )
    capability_transcript_identity = _regular(
        tmp_path / "drill/authority/reference-capability-transcript.json",
        b'{"status":"PASS"}',
    )
    authority = VALIDATION.bootstrap.authority
    manager_path = tmp_path / "tools/systemd"
    sudo_path = tmp_path / "tools/sudo"
    busctl_path = tmp_path / "tools/busctl"
    _regular(manager_path, b"fixture systemd manager\n", mode=0o755)
    _regular(sudo_path, b"fixture sudo\n", mode=0o755)
    _regular(busctl_path, b"fixture busctl\n", mode=0o755)
    full = lambda path: authority.full_identity(  # noqa: E731
        authority.snapshot_regular(path)
    )
    attestor = VALIDATION.bootstrap.V4_RESEARCH_DIR / "manager_attestor_v4.py"
    manager_epoch = {
        "attestation_toolchain": {
            "attestor": full(attestor),
            "python": full(Path(str(python_identity["path"]))),
            "sudo": full(sudo_path),
        },
        "attestor_ast_audit": authority.audit_attestor_source(attestor.read_bytes()),
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.77",
        "manager_executable": full(manager_path),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": full(busctl_path)},
        "schema": authority.MANAGER_EPOCH_SCHEMA,
    }
    planned_digest = "a" * 64
    pre_run = {
        "history_freeze_replay_identity": history_identity,
        "manager_epoch": manager_epoch,
        "reference_capability_identity": capability_identity,
        "reference_capability_transcript_identity": (capability_transcript_identity),
        "repository_head": HEAD,
        "repository_root": str(repository),
        "tool_identities": {"python3_13": python_identity},
    }
    sources = {
        VALIDATION.PREFLIGHT_SOURCE_ROLE: {
            **preflight_identity,
            "device": 1,
            "inode": 2,
            "mode_octal": f"{preflight_identity['mode']:04o}",
        },
        VALIDATION.QUALIFICATION_SOURCE_ROLE: {
            **qualification_identity,
            "device": 5,
            "inode": 6,
            "mode_octal": f"{qualification_identity['mode']:04o}",
        },
        VALIDATION.COLLECTION_PROTOCOL_SOURCE_ROLE: {
            **protocol_identity,
            "device": 7,
            "inode": 8,
            "mode_octal": f"{protocol_identity['mode']:04o}",
        },
        VALIDATION.COLLECTION_PLUGIN_SOURCE_ROLE: {
            **plugin_identity,
            "device": 9,
            "inode": 10,
            "mode_octal": f"{plugin_identity['mode']:04o}",
        },
        VALIDATION.TOOL_SOURCE_ROLE: {
            **current_tool,
            "device": 3,
            "inode": 4,
            "mode_octal": f"{current_tool['mode']:04o}",
        },
    }
    evidence: dict[str, object] = {
        "authority_ready_identity": authority_ready_identity,
        "detached_replay_identity": detached_replay_identity,
        "planned_source_set_digest": planned_digest,
        "pre_run": pre_run,
        "pre_run_identity": pre_run_identity,
        "selection_identity": _regular(
            tmp_path / "drill/attempt/selection.json",
            b'{"status":"PASS"}',
        ),
        "sources": sources,
    }

    def replay_drill(_authority_root: Path) -> dict[str, object]:
        for field in ("authority_ready_identity", "detached_replay_identity"):
            expected = evidence[field]
            assert isinstance(expected, dict)
            observed = VALIDATION._snapshot_identity(Path(str(expected["path"])))  # noqa: SLF001
            if observed != expected:
                raise VALIDATION.GateAValidationError(f"{field} byte identity drifted")
        return copy.deepcopy(evidence)

    monkeypatch.setattr(VALIDATION, "_verify_drill", replay_drill)
    monkeypatch.setattr(
        VALIDATION,
        "_reobserve_planned_sources",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        VALIDATION,
        "_verify_pytest_repository_surface",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        VALIDATION,
        "_verify_pytest_collection_stdout",
        lambda stdout, **_kwargs: VALIDATION._pytest_collection_projection(stdout),  # noqa: SLF001
    )
    collection_sha256 = hashlib.sha256(
        b"src/tests/test_fixture.py::test_fixture\n"
    ).hexdigest()
    monkeypatch.setattr(
        VALIDATION,
        "_head_pytest_collection_authority",
        lambda **_kwargs: (
            1,
            collection_sha256,
            {"src/tests/test_fixture.py"},
        ),
    )
    monkeypatch.setattr(
        VALIDATION.drill_authority,
        "_observe_repository_head",
        lambda _repository, _sources: HEAD,
    )
    monkeypatch.setattr(
        VALIDATION.drill_authority,
        "_capture_live_manager_epoch",
        lambda _sources: {
            "manager_epoch": copy.deepcopy(manager_epoch),
            "transcript": {},
        },
    )
    monkeypatch.setattr(
        VALIDATION,
        "_verified_session_bus_environment",
        lambda: {},
    )
    return repository, evidence, detached_replay_path


def _record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    exit_code: int,
) -> tuple[Path, Path, dict[str, object]]:
    repository, evidence, detached_replay_path = _fixture(
        tmp_path,
        monkeypatch,
    )
    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(
            returncode=exit_code,
            stderr=b"preflight stderr\n" if exit_code else b"",
            stdout=_preflight_stdout() if exit_code == 0 else b"preflight stdout\n",
        )

    monkeypatch.setattr(
        VALIDATION,
        "_run_same_fd_python_script",
        run_same_fd,
    )
    output = repository / "full-preflight-a001"
    result = VALIDATION.record_full_preflight(
        authority_root=tmp_path / "drill",
        repository_root=repository,
        output_dir=output,
    )
    return output, detached_replay_path, result


def _reseal_publication_commit(output: Path, receipt: dict[str, object]) -> None:
    receipt_identity = VALIDATION._snapshot_identity(output / "receipt.json")  # noqa: SLF001
    commit = {
        "output_root_identity": receipt["output_root_identity"],
        "receipt_identity": receipt_identity,
        "schema_version": VALIDATION.PREFLIGHT_PUBLICATION_COMMIT_SCHEMA,
        "status": "COMMITTED",
    }
    commit_path = output / "receipt.commit.json"
    commit_path.chmod(0o600)
    commit_path.write_bytes(VALIDATION.verifier.canonical_json_bytes(commit))
    commit_path.chmod(0o444)


def test_full_preflight_uses_clean_environment_and_closes_fresh_scratch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, evidence, _detached_replay_path = _fixture(
        tmp_path,
        monkeypatch,
    )
    captured: dict[str, object] = {}

    def run_same_fd(**kwargs: object) -> object:
        captured.update(kwargs)
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    monkeypatch.setenv("PYTEST_ADDOPTS", "--basetemp=/tmp/untrusted")
    monkeypatch.setenv("PYTEST_PLUGINS", "untrusted_plugin")
    monkeypatch.setenv("PYTHONPATH", "/tmp/untrusted-python")
    monkeypatch.setattr(
        VALIDATION,
        "_run_same_fd_python_script",
        run_same_fd,
    )
    result = VALIDATION.record_full_preflight(
        authority_root=tmp_path / "drill",
        repository_root=repository,
        output_dir=repository / "full-preflight-a001",
    )

    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert set(environment) == {
        "LANG",
        "LC_ALL",
        "PREFLIGHT_TIMEOUT_SCALE",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED",
        "PYTHONNOUSERSITE",
        "PYTHONSAFEPATH",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "TZ",
    }
    scratch_root = repository / "full-preflight-a001/pytest-scratch"
    assert "PYTEST_ADDOPTS" not in environment
    assert _forwarded_option(captured, "--basetemp") == str(
        scratch_root / VALIDATION.PREFLIGHT_BASETEMP_BASENAME
    )
    planned_sources = evidence["sources"]
    assert isinstance(planned_sources, dict)
    planned_qualification = planned_sources[VALIDATION.QUALIFICATION_SOURCE_ROLE]
    assert isinstance(planned_qualification, dict)
    assert captured["script_identity"] == {
        field: planned_qualification[field]
        for field in ("mode", "path", "sha256", "size_bytes")
    }
    support_identities = captured["support_identities"]
    assert isinstance(support_identities, tuple)
    assert [role for role, _identity in support_identities] == [
        "preflight",
        "protocol",
        "plugin",
    ]
    assert list(scratch_root.iterdir()) == [scratch_root / VALIDATION.PREFLIGHT_BASETEMP_BASENAME]
    assert not any((scratch_root / VALIDATION.PREFLIGHT_BASETEMP_BASENAME).iterdir())
    receipt = result["receipt"]
    assert receipt["pytest_scratch"]["status"] == "CLOSED_EMPTY_BASETEMP_RETAINED_AFTER_PASS"
    assert result["status"] == "PASS"


def test_successful_preflight_scratch_closure_failure_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(
        tmp_path,
        monkeypatch,
    )
    def run_same_fd(**kwargs: object) -> object:
        basetemp = _create_forwarded_basetemp(kwargs)
        (basetemp / "retained-payload").write_bytes(b"must fail closure\n")
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    output = repository / "full-preflight-a001"
    result = VALIDATION.record_full_preflight(
        authority_root=tmp_path / "drill",
        repository_root=repository,
        output_dir=output,
    )

    receipt = result["receipt"]
    assert result["status"] == "FAIL_CLOSED"
    assert receipt["exit_code"] == VALIDATION.PREFLIGHT_SCRATCH_CLOSURE_FAILURE_EXIT_CODE
    assert receipt["pytest_scratch"]["status"] == "CLOSURE_FAILED_FAIL_CLOSED"
    assert (output / "pytest-scratch").is_dir()
    assert b"GateAValidationError" in (output / "stderr.log").read_bytes()


def test_full_preflight_rejects_non_repository_scratch_parent_before_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(
        tmp_path,
        monkeypatch,
    )
    output = tmp_path / "outside-repository/full-preflight-a001"

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="repository-local child",
    ):
        VALIDATION.record_full_preflight(
            authority_root=tmp_path / "drill",
            repository_root=repository,
            output_dir=output,
        )

    assert not output.exists()


def test_full_preflight_environment_failure_closes_retained_directory_descriptors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        VALIDATION,
        "_preflight_environment",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("injected environment failure")),
    )
    before = len(os.listdir("/proc/self/fd"))
    output = repository / "full-preflight-a001"

    with pytest.raises(RuntimeError, match="injected environment failure"):
        VALIDATION.record_full_preflight(
            authority_root=tmp_path / "drill",
            repository_root=repository,
            output_dir=output,
        )

    assert len(os.listdir("/proc/self/fd")) == before
    assert output.is_dir()
    assert not (output / "receipt.json").exists()


def test_full_preflight_output_root_swap_before_first_write_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)
    output = repository / "full-preflight-a001"
    displaced = repository / "full-preflight-a001-displaced"

    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    original_write = VALIDATION._write_exclusive_at  # noqa: SLF001
    swapped = False

    def swap_then_write(*args: object, **kwargs: object) -> object:
        nonlocal swapped
        if not swapped:
            swapped = True
            output.rename(displaced)
            output.mkdir(mode=0o700)
            (displaced / VALIDATION.PREFLIGHT_SCRATCH_BASENAME).rename(
                output / VALIDATION.PREFLIGHT_SCRATCH_BASENAME
            )
        return original_write(*args, **kwargs)

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    monkeypatch.setattr(VALIDATION, "_write_exclusive_at", swap_then_write)

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="preflight output absolute topology drifted",
    ):
        VALIDATION.record_full_preflight(
            authority_root=tmp_path / "drill",
            repository_root=repository,
            output_dir=output,
        )

    assert swapped
    assert output.is_dir()
    assert displaced.is_dir()
    assert not (output / "receipt.json").exists()
    assert not (displaced / "receipt.json").exists()


@pytest.mark.parametrize(
    "swap_phase",
    ["before-receipt", "between-receipt-and-marker", "after-promotion"],
)
def test_full_preflight_publication_root_swap_never_returns_committed_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_phase: str,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)
    output = repository / "full-preflight-a001"
    displaced = repository / "full-preflight-a001-displaced"
    unknown = output / "unknown-replacement"

    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    swapped = False

    def swap_root() -> None:
        nonlocal swapped
        assert not swapped
        swapped = True
        output.rename(displaced)
        output.mkdir(mode=0o700)
        unknown.write_bytes(b"late output-root replacement\n")

    original_write = VALIDATION._write_exclusive_at  # noqa: SLF001

    def staged_write(*args: object, **kwargs: object) -> object:
        absolute_path = kwargs["absolute_path"]
        assert isinstance(absolute_path, Path)
        if swap_phase == "before-receipt" and absolute_path.name == "receipt.json" and not swapped:
            swap_root()
        result = original_write(*args, **kwargs)
        if (
            swap_phase == "between-receipt-and-marker"
            and absolute_path.name == "receipt.json"
            and not swapped
        ):
            swap_root()
        return result

    original_promote = VALIDATION._promote_preflight_publication_commit  # noqa: SLF001

    def promote_then_swap(*args: object, **kwargs: object) -> object:
        result = original_promote(*args, **kwargs)
        if swap_phase == "after-promotion" and not swapped:
            swap_root()
        return result

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    monkeypatch.setattr(VALIDATION, "_write_exclusive_at", staged_write)
    monkeypatch.setattr(
        VALIDATION,
        "_promote_preflight_publication_commit",
        promote_then_swap,
    )

    with pytest.raises(
        (VALIDATION.GateAValidationError, VALIDATION.verifier.VerificationError),
    ):
        VALIDATION.record_full_preflight(
            authority_root=tmp_path / "drill",
            repository_root=repository,
            output_dir=output,
        )

    assert swapped
    assert unknown.read_bytes() == b"late output-root replacement\n"
    assert not (output / "receipt.json").exists()
    assert not (output / "receipt.commit.json").exists()
    assert (displaced / "receipt.json").is_file()
    marker_mode = stat.S_IMODE((displaced / "receipt.commit.json").stat().st_mode)
    assert marker_mode == (0o444 if swap_phase == "after-promotion" else 0o600)


def test_full_preflight_forces_exact_modes_under_restrictive_umask(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)

    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    output = repository / "full-preflight-a001"
    previous = os.umask(0o077)
    try:
        result = VALIDATION.record_full_preflight(
            authority_root=tmp_path / "drill",
            repository_root=repository,
            output_dir=output,
        )
    finally:
        os.umask(previous)

    assert result["status"] == "PASS"
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "pytest-scratch").stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "pytest-scratch/basetemp").stat().st_mode) == 0o700
    for name in ("receipt.commit.json", "receipt.json", "stderr.log", "stdout.log"):
        assert stat.S_IMODE((output / name).stat().st_mode) == 0o444


def test_staged_publication_marker_is_never_consumable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _, result = _record(tmp_path, monkeypatch, exit_code=0)
    assert result["status"] == "PASS"
    (output / "receipt.commit.json").chmod(0o600)
    gate_a_path = tmp_path / "gate-a-staged-marker.json"

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="publication commit",
    ):
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=output / "receipt.json",
            output_path=gate_a_path,
            approval_id="gate-a-fixture-staged-marker",
            target_campaign_dir=tmp_path / "run-fixture-staged-marker",
            run_nonce="run-fixture-staged-marker",
        )

    assert not gate_a_path.exists()


def test_post_signal_pipe_close_error_reconciles_committed_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)
    output = repository / "full-preflight-a001"

    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    parent_pid = os.getpid()
    pipe_fds: dict[str, int] = {}
    injected = False
    original_pipe2 = os.pipe2
    original_close = os.close

    def observed_pipe2(flags: int) -> tuple[int, int]:
        read_fd, write_fd = original_pipe2(flags)
        pipe_fds.update(read=read_fd, write=write_fd)
        return read_fd, write_fd

    def close_with_post_signal_error(descriptor: int) -> None:
        nonlocal injected
        if (
            os.getpid() == parent_pid
            and descriptor == pipe_fds.get("write")
            and not injected
        ):
            deadline = time.monotonic() + 2
            marker = output / "receipt.commit.json"
            while (
                time.monotonic() < deadline
                and (
                    not marker.exists()
                    or stat.S_IMODE(marker.stat().st_mode) != 0o444
                )
            ):
                time.sleep(0.001)
            assert marker.exists()
            assert stat.S_IMODE(marker.stat().st_mode) == 0o444
            injected = True
            original_close(descriptor)
            raise OSError(errno.EIO, "injected post-signal close failure")
        original_close(descriptor)

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    monkeypatch.setattr(VALIDATION.os, "pipe2", observed_pipe2)
    monkeypatch.setattr(VALIDATION.os, "close", close_with_post_signal_error)
    before = len(os.listdir("/proc/self/fd"))

    result = VALIDATION.record_full_preflight(
        authority_root=tmp_path / "drill",
        repository_root=repository,
        output_dir=output,
    )

    assert injected
    assert result["status"] == "PASS"
    assert stat.S_IMODE((output / "receipt.commit.json").stat().st_mode) == 0o444
    assert len(os.listdir("/proc/self/fd")) == before


def test_post_signal_waitpid_error_reconciles_committed_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)
    output = repository / "full-preflight-a001"

    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    parent_pid = os.getpid()
    child_pid: int | None = None
    injected = False
    original_fork = os.fork
    original_waitpid = os.waitpid

    def observed_fork() -> int:
        nonlocal child_pid
        result = original_fork()
        if os.getpid() == parent_pid and result > 0:
            child_pid = result
        return result

    def waitpid_with_post_reap_error(pid: int, options: int) -> tuple[int, int]:
        nonlocal injected
        result = original_waitpid(pid, options)
        if os.getpid() == parent_pid and pid == child_pid and not injected:
            injected = True
            raise OSError(errno.EIO, "injected post-reap waitpid failure")
        return result

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    monkeypatch.setattr(VALIDATION.os, "fork", observed_fork)
    monkeypatch.setattr(VALIDATION.os, "waitpid", waitpid_with_post_reap_error)
    before = len(os.listdir("/proc/self/fd"))

    result = VALIDATION.record_full_preflight(
        authority_root=tmp_path / "drill",
        repository_root=repository,
        output_dir=output,
    )

    assert injected
    assert result["status"] == "PASS"
    assert stat.S_IMODE((output / "receipt.commit.json").stat().st_mode) == 0o444
    assert len(os.listdir("/proc/self/fd")) == before


def test_post_commit_self_replay_close_error_retries_complete_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)
    output = repository / "full-preflight-a001"

    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    original_verify = VALIDATION._verify_preflight_output_root  # noqa: SLF001
    calls = 0

    def verify_then_fail_once(**kwargs: object) -> None:
        nonlocal calls
        calls += 1
        original_verify(**kwargs)
        if calls == 1:
            raise OSError(errno.EIO, "injected post-close self-replay failure")

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    monkeypatch.setattr(VALIDATION, "_verify_preflight_output_root", verify_then_fail_once)

    result = VALIDATION.record_full_preflight(
        authority_root=tmp_path / "drill",
        repository_root=repository,
        output_dir=output,
    )

    assert result["status"] == "PASS"
    assert calls >= 3
    assert stat.S_IMODE((output / "receipt.commit.json").stat().st_mode) == 0o444


def test_post_commit_wrapped_output_open_eio_retries_complete_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)
    output = repository / "full-preflight-a001"

    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    original_open = VALIDATION._open_directory_no_symlinks  # noqa: SLF001
    injected = False

    def open_with_one_post_commit_eio(path: Path) -> int:
        nonlocal injected
        marker = output / "receipt.commit.json"
        if (
            path == output
            and marker.exists()
            and stat.S_IMODE(marker.stat().st_mode) == 0o444
            and not injected
        ):
            injected = True
            raise OSError(errno.EIO, "injected wrapped output-root open failure")
        return original_open(path)

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    monkeypatch.setattr(
        VALIDATION,
        "_open_directory_no_symlinks",
        open_with_one_post_commit_eio,
    )

    result = VALIDATION.record_full_preflight(
        authority_root=tmp_path / "drill",
        repository_root=repository,
        output_dir=output,
    )

    assert injected
    assert result["status"] == "PASS"


def test_final_self_replay_root_check_cannot_hide_late_basetemp_residual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _evidence, _detached_replay_path = _fixture(tmp_path, monkeypatch)
    output = repository / "full-preflight-a001"
    residual = output / "pytest-scratch/basetemp/late-residual"

    def run_same_fd(**kwargs: object) -> object:
        _create_forwarded_basetemp(kwargs)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=_preflight_stdout())

    original_verify = VALIDATION._verify_preflight_output_root  # noqa: SLF001
    post_commit_checks = 0
    injected = False

    def verify_then_inject_before_final_scratch(**kwargs: object) -> None:
        nonlocal injected, post_commit_checks
        original_verify(**kwargs)
        marker = output / "receipt.commit.json"
        if marker.exists() and stat.S_IMODE(marker.stat().st_mode) == 0o444:
            post_commit_checks += 1
            if post_commit_checks == 2:
                residual.write_bytes(b"late-canonical-replacement\n")
                injected = True

    monkeypatch.setattr(VALIDATION, "_run_same_fd_python_script", run_same_fd)
    monkeypatch.setattr(
        VALIDATION,
        "_verify_preflight_output_root",
        verify_then_inject_before_final_scratch,
    )

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="basetemp is not empty",
    ):
        VALIDATION.record_full_preflight(
            authority_root=tmp_path / "drill",
            repository_root=repository,
            output_dir=output,
        )

    assert injected
    assert residual.read_bytes() == b"late-canonical-replacement\n"
    assert stat.S_IMODE((output / "receipt.commit.json").stat().st_mode) == 0o444


def _runtime_report_source() -> bytes:
    grandchild = """
import json
import os
import sys
import sysconfig
print(json.dumps({
    "base_executable": sys._base_executable,
    "executable": sys.executable,
    "fd_reachable": bool(sys.executable and os.path.exists(sys.executable)),
    "prefix": sys.prefix,
    "exec_prefix": sys.exec_prefix,
    "stdlib": sysconfig.get_path("stdlib"),
}, sort_keys=True))
""".strip()
    child = f"""
import json
import os
import subprocess
import sys
import sysconfig
completed = subprocess.run(
    [sys.executable, "-I", "-c", {grandchild!r}],
    check=True,
    capture_output=True,
    text=True,
)
print(json.dumps({{
    "base_executable": sys._base_executable,
    "executable": sys.executable,
    "fd_reachable": bool(sys.executable and os.path.exists(sys.executable)),
    "grandchild": json.loads(completed.stdout),
    "grandchild_stderr": completed.stderr,
    "prefix": sys.prefix,
    "exec_prefix": sys.exec_prefix,
    "stdlib": sysconfig.get_path("stdlib"),
}}, sort_keys=True))
""".strip()
    source = f"""
import json
import os
import subprocess
import sys
import sysconfig
completed = subprocess.run(
    [sys.executable, "-I", "-c", {child!r}],
    check=True,
    capture_output=True,
    text=True,
)
print(json.dumps({{
    "argv": sys.argv,
    "base_executable": sys._base_executable,
    "child": json.loads(completed.stdout),
    "child_stderr": completed.stderr,
    "executable": sys.executable,
    "fd_reachable": bool(sys.executable and os.path.exists(sys.executable)),
    "pid": os.getpid(),
    "prefix": sys.prefix,
    "exec_prefix": sys.exec_prefix,
    "stdlib": sysconfig.get_path("stdlib"),
}}, sort_keys=True))
""".strip()
    return source.encode()


def _assert_runtime_report(report: dict[str, object], *, expected_prefix: str) -> None:
    executable = report["executable"]
    assert isinstance(executable, str) and executable.startswith(expected_prefix)
    assert report["base_executable"] == executable
    assert report["fd_reachable"] is True
    for field in ("prefix", "exec_prefix", "stdlib"):
        value = report[field]
        assert isinstance(value, str) and Path(value).is_absolute()
        assert Path(value).is_dir()


def test_same_fd_python_supports_two_nested_python_launches(
    tmp_path: Path,
) -> None:
    python_path = Path(sys.executable).resolve()
    python_identity = VALIDATION._snapshot_identity(python_path)  # noqa: SLF001
    script_path = tmp_path / "nested_preflight.py"
    script_identity = _regular(
        script_path,
        _runtime_report_source(),
    )

    completed = VALIDATION._run_same_fd_python_script(  # noqa: SLF001
        python_identity=python_identity,
        script_identity=script_identity,
        repository=tmp_path,
        forwarded=("--fixture-full",),
        environment=os.environ,
        timeout_seconds=20,
    )

    assert completed.returncode == 0
    assert completed.stderr == b""
    assert b"Could not find platform dependent libraries" not in completed.stderr
    report = json.loads(completed.stdout)
    expected_prefix = f"/proc/{report['pid']}/fd/"
    assert report["argv"] == [str(script_path), "--fixture-full"]
    _assert_runtime_report(report, expected_prefix=expected_prefix)
    child = report["child"]
    assert isinstance(child, dict)
    _assert_runtime_report(child, expected_prefix=expected_prefix)
    assert child["grandchild_stderr"] == ""
    grandchild = child["grandchild"]
    assert isinstance(grandchild, dict)
    _assert_runtime_report(grandchild, expected_prefix=expected_prefix)
    assert report["child_stderr"] == ""


def test_same_fd_qualification_runner_loads_verified_plugin_object_without_authority(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    tests = repository / "src/tests"
    tests.mkdir(parents=True)
    (repository / "pytest.ini").write_text("[pytest]\naddopts =\n", encoding="utf-8")
    (tests / "conftest.py").write_text(
        "def pytest_addoption(parser):\n"
        "    parser.addoption('--repository-workflow', action='store', default='auto')\n",
        encoding="utf-8",
    )
    (tests / "test_sample.py").write_text(
        "def test_ok():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    preflight_identity = _regular(
        repository / "tools/preflight_gate.py",
        (
            "class Gate:\n"
            "    def __init__(self):\n"
            "        self.blocked = False\n"
            "    def ok(self, _message):\n"
            "        return None\n"
            "    def block(self, _message):\n"
            "        self.blocked = True\n"
            "\n"
            "def check_tests(_gate, *, full=False):\n"
            "    raise RuntimeError('qualification runner did not replace check_tests')\n"
            "\n"
            "def run_gate(*, full=False):\n"
            "    gate = Gate()\n"
            "    check_tests(gate, full=full)\n"
            "    return int(gate.blocked)\n"
        ).encode("ascii"),
    )
    qualification_path = TOOLS / "ab16_preflight_qualification_v1.py"
    protocol_path = TOOLS / "ab16_pytest_collection_protocol_v1.py"
    plugin_path = TOOLS / "ab16_pytest_collection_plugin_v1.py"
    basetemp = repository / ".pytest_tmp/ab16-qualification/basetemp"
    expected_sha256 = hashlib.sha256(
        b"src/tests/test_sample.py::test_ok\n"
    ).hexdigest()

    completed = VALIDATION._run_same_fd_python_script(  # noqa: SLF001
        python_identity=VALIDATION._snapshot_identity(  # noqa: SLF001
            Path(sys.executable).resolve()
        ),
        script_identity=VALIDATION._snapshot_identity(qualification_path),  # noqa: SLF001
        support_identities=(
            ("preflight", preflight_identity),
            (
                "protocol",
                VALIDATION._snapshot_identity(protocol_path),  # noqa: SLF001
            ),
            (
                "plugin",
                VALIDATION._snapshot_identity(plugin_path),  # noqa: SLF001
            ),
        ),
        repository=repository,
        forwarded=(
            "--repository-root",
            str(repository),
            "--basetemp",
            str(basetemp),
            "--basetemp-relative",
            ".pytest_tmp/ab16-qualification/basetemp",
            "--expected-count",
            "1",
            "--expected-sha256",
            expected_sha256,
            "--preflight-source",
            str(preflight_identity["path"]),
            "--collection-protocol-source",
            str(protocol_path),
            "--collection-plugin-source",
            str(plugin_path),
            "--full",
        ),
        environment=VALIDATION._preflight_environment(),  # noqa: SLF001
        timeout_seconds=30,
    )

    assert completed.returncode == 0
    assert completed.stderr == b""
    projection = VALIDATION._pytest_collection_projection(completed.stdout)  # noqa: SLF001
    assert projection["collection_count"] == 1
    assert projection["collection_sha256"] == expected_sha256
    assert not (repository / "authority").exists()
    assert not (repository / "campaign").exists()
    assert not (repository / "formal").exists()


def test_same_fd_subreaper_rejects_and_reaps_detached_descendant(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "late-descendant-marker"
    child = (
        "import pathlib,time;"
        "time.sleep(0.5);"
        f"pathlib.Path({str(marker)!r}).write_bytes(b'late')"
    )
    selected = tmp_path / "detached-descendant.py"
    selected_identity = _regular(
        selected,
        (
            "import subprocess,sys\n"
            "subprocess.Popen(\n"
            f"    [sys.executable, '-I', '-c', {child!r}],\n"
            "    start_new_session=True,\n"
            "    stdin=subprocess.DEVNULL,\n"
            "    stdout=subprocess.DEVNULL,\n"
            "    stderr=subprocess.DEVNULL,\n"
            ")\n"
        ).encode(),
    )

    completed = VALIDATION._run_same_fd_python_script(  # noqa: SLF001
        python_identity=VALIDATION._snapshot_identity(Path(sys.executable).resolve()),  # noqa: SLF001
        script_identity=selected_identity,
        repository=tmp_path,
        forwarded=(),
        environment=os.environ,
        timeout_seconds=10,
    )

    assert completed.returncode == VALIDATION.PREFLIGHT_SCRATCH_CLOSURE_FAILURE_EXIT_CODE
    assert b"selected preflight observed 1 descendant(s)" in completed.stderr
    time.sleep(0.75)
    assert not marker.exists()


def test_same_fd_timeout_reaps_detached_descendant_without_pipe_hang(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "timeout-descendant-marker"
    child = (
        "import pathlib,time;"
        "time.sleep(1.0);"
        f"pathlib.Path({str(marker)!r}).write_bytes(b'late')"
    )
    selected = tmp_path / "timeout-descendant.py"
    selected_identity = _regular(
        selected,
        (
            "import subprocess,sys,time\n"
            "subprocess.Popen(\n"
            f"    [sys.executable, '-I', '-c', {child!r}],\n"
            "    start_new_session=True,\n"
            ")\n"
            "time.sleep(30)\n"
        ).encode(),
    )
    started = time.monotonic()

    with pytest.raises(subprocess.TimeoutExpired):
        VALIDATION._run_same_fd_python_script(  # noqa: SLF001
            python_identity=VALIDATION._snapshot_identity(Path(sys.executable).resolve()),  # noqa: SLF001
            script_identity=selected_identity,
            repository=tmp_path,
            forwarded=(),
            environment=os.environ,
            timeout_seconds=0.2,
        )

    assert time.monotonic() - started < 5
    time.sleep(1.1)
    assert not marker.exists()


def _run_loader_source(
    *,
    tmp_path: Path,
    loader_source: str,
    selected_source: bytes,
) -> subprocess.CompletedProcess[bytes]:
    python_path = Path(sys.executable).resolve()
    python_identity = VALIDATION._snapshot_identity(python_path)  # noqa: SLF001
    script_path = tmp_path / "loader-selected.py"
    script_identity = _regular(script_path, selected_source)
    python_fd = os.open(
        python_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    script_fd = os.open(
        script_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    argv = [
        str(python_path),
        "-I",
        "-B",
        "-c",
        loader_source,
        str(python_fd),
        str(script_fd),
        str(python_path),
        str(python_identity["mode"]),
        str(python_identity["size_bytes"]),
        str(python_identity["sha256"]),
        str(script_path),
        str(script_identity["mode"]),
        str(script_identity["size_bytes"]),
        str(script_identity["sha256"]),
    ]
    try:
        return subprocess.run(
            argv,
            check=False,
            close_fds=True,
            executable=f"/proc/self/fd/{python_fd}",
            pass_fds=(python_fd, script_fd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
    finally:
        os.close(script_fd)
        os.close(python_fd)


def test_pytest_surface_rejects_ignored_collected_test_module_that_exits_zero(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git = shutil.which("git")
    assert git is not None

    def run_git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [git, "-C", str(repository), *arguments],
            check=True,
            close_fds=True,
            env={
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "HOME": str(tmp_path / "git-home"),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )

    run_git("init", "-q")
    run_git("config", "user.email", "fixture@example.invalid")
    run_git("config", "user.name", "Fixture")
    tests = repository / "src/tests"
    tests.mkdir(parents=True)
    (repository / "pytest.ini").write_text("[pytest]\ntestpaths = src/tests\n", encoding="utf-8")
    governance = repository / "data/repository_governance/code_assets.json"
    governance.parent.mkdir(parents=True)
    governance.write_bytes(
        VALIDATION.verifier.canonical_json_bytes(
            {
                "code_selector": {
                    "extensions": [".py", ".pyi"],
                }
            }
        )
    )
    (tests / "conftest.py").write_text("", encoding="utf-8")
    (tests / "test_real.py").write_text(
        "def test_real_failure():\n    assert False\n",
        encoding="utf-8",
    )
    run_git(
        "add",
        "pytest.ini",
        "data/repository_governance/code_assets.json",
        "src/tests/conftest.py",
        "src/tests/test_real.py",
    )
    run_git("commit", "-q", "-m", "fixture")
    (repository / ".git/info/exclude").write_text(
        "src/tests/test_early_exit.py\n",
        encoding="utf-8",
    )
    (tests / "test_early_exit.py").write_text(
        "import os\nos._exit(0)\n",
        encoding="utf-8",
    )
    assert (
        run_git(
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            ".",
        ).stdout
        == b""
    )

    bypass_control = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "pytest",
            "-p",
            "no:randomly",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(repository),
            "--confcutdir",
            str(tests),
            str(tests),
            "-q",
        ],
        check=False,
        close_fds=True,
        cwd=repository,
        env={
            "HOME": str(tmp_path / "pytest-home"),
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        },
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    assert bypass_control.returncode == 0
    assert bypass_control.stdout == b""
    assert bypass_control.stderr == b""

    git_identity = VALIDATION.drill_authority.bootstrap.authority.snapshot_tool(  # noqa: SLF001
        Path(git)
    )[1]
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="pytest discovery surface differs from HEAD",
    ):
        VALIDATION._verify_pytest_repository_surface(  # noqa: SLF001
            repository=repository,
            sources={"system.git": git_identity},
        )


def test_pytest_surface_rejects_ignored_repo_root_package_that_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git = shutil.which("git")
    assert git is not None

    def run_git(*arguments: str) -> bytes:
        return subprocess.run(
            [git, "-C", str(repository), *arguments],
            check=True,
            close_fds=True,
            env={
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "HOME": str(tmp_path / "git-home"),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        ).stdout

    run_git("init", "-q")
    run_git("config", "user.email", "fixture@example.invalid")
    run_git("config", "user.name", "Fixture")
    tests = repository / "src/tests"
    tests.mkdir(parents=True)
    (repository / "pytest.ini").write_text("[pytest]\ntestpaths = src/tests\n", encoding="utf-8")
    governance = repository / "data/repository_governance/code_assets.json"
    governance.parent.mkdir(parents=True)
    governance.write_bytes(
        VALIDATION.verifier.canonical_json_bytes(
            {
                "logical_isolation": {
                    "pytest": {
                        "enabled": True,
                        "lane_rules": [
                            {
                                "glob": "src/tests/**",
                                "lane": "developer",
                            }
                        ],
                    }
                },
                "pytest_entrypoints": [
                    {
                        "expected_count": 1,
                        "expected_sha256": hashlib.sha256(
                            b"src/tests/test_real.py::test_real_failure\n"
                        ).hexdigest(),
                        "id": "preflight_full_non_slow",
                    }
                ],
            }
        )
    )
    (tests / "conftest.py").write_bytes((ROOT / "src/tests/conftest.py").read_bytes())
    (repository / "src/foo.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tests / "test_real.py").write_text(
        "import src.foo\n\ndef test_real_failure():\n    assert False\n",
        encoding="utf-8",
    )
    run_git("add", ".")
    run_git("commit", "-q", "-m", "fixture")
    git_identity = VALIDATION.drill_authority.bootstrap.authority.snapshot_tool(  # noqa: SLF001
        Path(git)
    )[1]
    before_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    before_fds = len(os.listdir("/proc/self/fd"))
    monkeypatch.setattr(
        resource,
        "setrlimit",
        lambda *_args, **_kwargs: pytest.fail("pytest surface guard must not change RLIMIT"),
    )
    for _index in range(3):
        surface_guard = VALIDATION._verify_pytest_repository_surface(  # noqa: SLF001
            repository=repository,
            sources={"system.git": git_identity},
        )
        assert resource.getrlimit(resource.RLIMIT_NOFILE) == before_limit
        assert len(os.listdir("/proc/self/fd")) == before_fds
        surface_guard.verify_and_close()
    aborted_guard = VALIDATION._verify_pytest_repository_surface(  # noqa: SLF001
        repository=repository,
        sources={"system.git": git_identity},
    )
    aborted_guard.abort(RuntimeError("fixture abort"))
    assert resource.getrlimit(resource.RLIMIT_NOFILE) == before_limit
    assert len(os.listdir("/proc/self/fd")) == before_fds

    (repository / ".git/info/exclude").write_text(
        "src/__init__.py\n",
        encoding="utf-8",
    )
    (repository / "src/__init__.py").write_text(
        "import os\nos._exit(0)\n",
        encoding="utf-8",
    )
    assert run_git("status", "--porcelain=v1", "--untracked-files=all", "--", ".") == b""

    bypass_control = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "pytest",
            "-p",
            "no:randomly",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(repository),
            "--confcutdir",
            str(tests),
            str(tests),
            "-q",
        ],
        check=False,
        close_fds=True,
        cwd=repository,
        env={
            "HOME": str(tmp_path / "pytest-home"),
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        },
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    assert bypass_control.returncode == 0
    assert bypass_control.stdout == b""
    assert bypass_control.stderr == b""

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="pytest discovery surface differs from HEAD",
    ):
        VALIDATION._verify_pytest_repository_surface(  # noqa: SLF001
            repository=repository,
            sources={"system.git": git_identity},
        )

    (repository / "src/__init__.py").unlink()
    (repository / ".git/info/exclude").write_text("", encoding="utf-8")
    drift_guard = VALIDATION._verify_pytest_repository_surface(  # noqa: SLF001
        repository=repository,
        sources={"system.git": git_identity},
    )
    with (repository / ".git/info/exclude").open("a", encoding="utf-8") as stream:
        stream.write("src/tests/test_late_pollution.py\n")
    late_pollution = tests / "test_late_pollution.py"
    late_pollution.write_text("def test_late_pollution():\n    pass\n", encoding="utf-8")
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="pytest discovery surface drifted across execution",
    ):
        drift_guard.verify_and_close()
    assert late_pollution.read_text(encoding="utf-8").startswith("def test_late_pollution")

    late_pollution.unlink()
    (repository / ".git/info/exclude").write_text(
        "src/__init__.py\n",
        encoding="utf-8",
    )
    (repository / "src/__init__.py").write_text(
        "import os\nos._exit(0)\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("relative", "node_kind"),
    [
        ("shadow_package", "symlink"),
        ("shadow_module.pyc", "file"),
        (
            "shadow_extension"
            + next(
                suffix
                for suffix in VALIDATION._pytest_import_suffixes()  # noqa: SLF001
                if suffix in importlib.machinery.EXTENSION_SUFFIXES
            ),
            "file",
        ),
    ],
)
def test_pytest_surface_observes_untracked_pathfinder_candidates(
    tmp_path: Path,
    relative: str,
    node_kind: str,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git = shutil.which("git")
    assert git is not None

    def run_git(*arguments: str) -> bytes:
        return subprocess.run(
            [git, "-C", str(repository), *arguments],
            check=True,
            close_fds=True,
            env={
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "HOME": str(tmp_path / "git-home"),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        ).stdout

    run_git("init", "-q")
    run_git("config", "user.email", "fixture@example.invalid")
    run_git("config", "user.name", "Fixture")
    tests = repository / "src/tests"
    tests.mkdir(parents=True)
    (repository / "pytest.ini").write_text("[pytest]\ntestpaths = src/tests\n", encoding="utf-8")
    governance = repository / "data/repository_governance/code_assets.json"
    governance.parent.mkdir(parents=True)
    governance.write_text("{}\n", encoding="utf-8")
    (tests / "conftest.py").write_text("", encoding="utf-8")
    (tests / "test_fixture.py").write_text("def test_fixture():\n    pass\n", encoding="utf-8")
    run_git("add", ".")
    run_git("commit", "-q", "-m", "fixture")

    (repository / ".git/info/exclude").write_text(relative + "\n", encoding="utf-8")
    candidate = repository / relative
    if node_kind == "symlink":
        outside = tmp_path / "outside"
        outside.mkdir()
        candidate.symlink_to(outside, target_is_directory=True)
        expected_bytes: bytes | None = None
    elif relative.endswith(".pyc"):
        source = repository / "shadow_module_source.py"
        source.write_text("VALUE = 1\n", encoding="utf-8")
        py_compile.compile(
            str(source),
            cfile=str(candidate),
            doraise=True,
        )
        source.unlink()
        expected_bytes = candidate.read_bytes()
    else:
        candidate.write_bytes(b"untracked-import-candidate")
        expected_bytes = candidate.read_bytes()
    assert run_git("status", "--porcelain=v1", "--untracked-files=all", "--", ".") == b""
    git_identity = VALIDATION.drill_authority.bootstrap.authority.snapshot_tool(  # noqa: SLF001
        Path(git)
    )[1]
    before_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    before_fds = len(os.listdir("/proc/self/fd"))

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="pytest discovery surface differs from HEAD",
    ):
        VALIDATION._verify_pytest_repository_surface(  # noqa: SLF001
            repository=repository,
            sources={"system.git": git_identity},
        )

    assert resource.getrlimit(resource.RLIMIT_NOFILE) == before_limit
    assert len(os.listdir("/proc/self/fd")) == before_fds
    if node_kind == "symlink":
        assert candidate.is_symlink()
        assert candidate.readlink() == outside
    else:
        assert candidate.read_bytes() == expected_bytes


def test_pytest_surface_keeps_nonidentifier_artifact_subtree_opaque(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    hidden = repository / ".artifacts/private/ignored.py"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("raise RuntimeError('must remain opaque')\n", encoding="utf-8")

    assert VALIDATION._observe_pytest_surface(repository) == {}  # noqa: SLF001


def test_static_import_surface_blocks_origin_spoof(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git = shutil.which("git")
    assert git is not None

    def run_git(*arguments: str) -> bytes:
        return subprocess.run(
            [git, "-C", str(repository), *arguments],
            check=True,
            close_fds=True,
            env={
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "HOME": str(tmp_path / "git-home"),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        ).stdout

    run_git("init", "-q")
    run_git("config", "user.email", "fixture@example.invalid")
    run_git("config", "user.name", "Fixture")
    tests = repository / "src/tests"
    tests.mkdir(parents=True)
    (repository / "pytest.ini").write_text("[pytest]\ntestpaths = src/tests\n", encoding="utf-8")
    expected_nodeids = b"src/tests/test_real.py::test_real\n"
    governance = repository / "data/repository_governance/code_assets.json"
    governance.parent.mkdir(parents=True)
    governance.write_bytes(
        VALIDATION.verifier.canonical_json_bytes(
            {
                "logical_isolation": {
                    "pytest": {
                        "enabled": True,
                        "lane_rules": [
                            {
                                "glob": "src/tests/**",
                                "lane": "developer",
                            }
                        ],
                    }
                },
                "pytest_entrypoints": [
                    {
                        "expected_count": 1,
                        "expected_sha256": hashlib.sha256(expected_nodeids).hexdigest(),
                        "id": "preflight_full_non_slow",
                    }
                ],
            }
        )
    )
    (tests / "conftest.py").write_bytes((ROOT / "src/tests/conftest.py").read_bytes())
    (repository / "src/foo.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tests / "test_real.py").write_text(
        "import src.foo\n\ndef test_real():\n    assert src.foo.VALUE == 1\n",
        encoding="utf-8",
    )
    run_git("add", ".")
    run_git("commit", "-q", "-m", "fixture")
    (repository / ".git/info/exclude").write_text("src/__init__.py\n", encoding="utf-8")
    hidden_init = repository / "src/__init__.py"
    hidden_init.write_text(
        "import sys\n"
        "from types import ModuleType\n"
        "_replacement = ModuleType('src')\n"
        "_replacement.__path__ = list(__path__)\n"
        "sys.modules['src'] = _replacement\n",
        encoding="utf-8",
    )
    assert run_git("status", "--porcelain=v1", "--untracked-files=all", "--", ".") == b""
    git_identity = VALIDATION.drill_authority.bootstrap.authority.snapshot_tool(  # noqa: SLF001
        Path(git)
    )[1]

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="pytest discovery surface differs from HEAD",
    ):
        VALIDATION._verify_pytest_repository_surface(  # noqa: SLF001
            repository=repository,
            sources={"system.git": git_identity},
        )

    assert hidden_init.is_file()
    assert not (repository / ".artifacts").exists()


def test_loader_fails_closed_without_any_public_pidfd_api(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "selected-must-not-run"
    loader = VALIDATION._SCRIPT_LOADER  # noqa: SLF001
    replacements = {
        'native_pidfd_open = getattr(os, "pidfd_open", None)': "native_pidfd_open = None",
        'native_pidfd_send_signal = getattr(signal, "pidfd_send_signal", None)': (
            "native_pidfd_send_signal = None"
        ),
        'libc_pidfd_open = getattr(libc, "pidfd_open", None)': "libc_pidfd_open = None",
        'libc_pidfd_send_signal = getattr(libc, "pidfd_send_signal", None)': (
            "libc_pidfd_send_signal = None"
        ),
    }
    for original, replacement in replacements.items():
        assert loader.count(original) == 1
        loader = loader.replace(original, replacement)

    completed = _run_loader_source(
        tmp_path=tmp_path,
        loader_source=loader,
        selected_source=f"from pathlib import Path\nPath({str(marker)!r}).touch()\n".encode(),
    )

    assert completed.returncode != 0
    assert b"requires public pidfd APIs" in completed.stderr
    assert not marker.exists()
    assert "SYS_PIDFD" not in VALIDATION._SCRIPT_LOADER  # noqa: SLF001


@pytest.mark.parametrize(
    "fault",
    [
        "pidfd-open",
        "pidfd-send",
        "pidfd-close",
        "children-read",
        "post-wait-signal",
    ],
)
def test_loader_faults_fail_closed_and_reap_only_adopted_descendants(
    tmp_path: Path,
    fault: str,
) -> None:
    marker = tmp_path / f"late-descendant-{fault}"
    child = (
        "import pathlib,time;"
        "time.sleep(0.5);"
        f"pathlib.Path({str(marker)!r}).write_bytes(b'late')"
    )
    selected_source = (
        "import subprocess,sys\n"
        "subprocess.Popen(\n"
        f"    [sys.executable, '-I', '-c', {child!r}],\n"
        "    start_new_session=True,\n"
        "    stdin=subprocess.DEVNULL,\n"
        "    stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL,\n"
        ")\n"
    ).encode()
    loader = VALIDATION._SCRIPT_LOADER  # noqa: SLF001
    if fault == "pidfd-open":
        anchor = "def pidfd_open(pid):\n"
        replacement = (
            "injected_pidfd_open = False\n"
            "def pidfd_open(pid):\n"
            "    global injected_pidfd_open\n"
            "    if not injected_pidfd_open:\n"
            "        injected_pidfd_open = True\n"
            "        raise OSError(errno.EIO, 'injected pidfd_open failure')\n"
        )
    elif fault == "pidfd-send":
        anchor = "def pidfd_send_signal(descriptor, signum):\n"
        replacement = (
            "injected_pidfd_send = False\n"
            "def pidfd_send_signal(descriptor, signum):\n"
            "    global injected_pidfd_send\n"
            "    if not injected_pidfd_send:\n"
            "        injected_pidfd_send = True\n"
            "        raise OSError(errno.EIO, 'injected pidfd_send_signal failure')\n"
        )
    elif fault == "pidfd-close":
        anchor = "            os.close(pidfd)\n"
        replacement = (
            "            os.close(pidfd)\n"
            "            raise OSError(errno.EIO, 'injected pidfd close failure')\n"
        )
    elif fault == "children-read":
        anchor = "def direct_children():\n"
        replacement = (
            "injected_children_read = False\n"
            "def direct_children():\n"
            "    global injected_children_read\n"
            "    if not injected_children_read:\n"
            "        injected_children_read = True\n"
            "        raise OSError(errno.EIO, 'injected children read failure')\n"
        )
    elif fault == "post-wait-signal":
        anchor = "    _waited, worker_status = os.waitpid(worker, 0)\n"
        replacement = (
            "    _waited, worker_status = os.waitpid(worker, 0)\n"
            "    os.kill(os.getpid(), signal.SIGTERM)\n"
        )
    else:  # pragma: no cover - static parameter list
        raise AssertionError("unreachable fault")
    assert loader.count(anchor) == 1
    loader = loader.replace(anchor, replacement)

    completed = _run_loader_source(
        tmp_path=tmp_path,
        loader_source=loader,
        selected_source=selected_source,
    )

    assert completed.returncode != 0
    time.sleep(0.75)
    assert not marker.exists()


def test_loader_requires_waitpid_echild_when_procfs_temporarily_misses_live_descendant(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "procfs-missed-live-descendant"
    child = (
        "import pathlib,time;"
        "time.sleep(0.5);"
        f"pathlib.Path({str(marker)!r}).write_bytes(b'late')"
    )
    selected_source = (
        "import subprocess,sys\n"
        "subprocess.Popen(\n"
        f"    [sys.executable, '-I', '-c', {child!r}],\n"
        "    start_new_session=True,\n"
        "    stdin=subprocess.DEVNULL,\n"
        "    stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL,\n"
        ")\n"
    ).encode()
    loader = VALIDATION._SCRIPT_LOADER  # noqa: SLF001
    anchor = "def direct_children():\n"
    replacement = (
        "injected_empty_children_reads = 0\n"
        "def direct_children():\n"
        "    global injected_empty_children_reads\n"
        "    if injected_empty_children_reads < 2:\n"
        "        injected_empty_children_reads += 1\n"
        "        return []\n"
    )
    assert loader.count(anchor) == 1
    loader = loader.replace(anchor, replacement)

    completed = _run_loader_source(
        tmp_path=tmp_path,
        loader_source=loader,
        selected_source=selected_source,
    )

    assert completed.returncode != 0
    assert b"observed 1 descendant(s)" in completed.stderr
    time.sleep(0.75)
    assert not marker.exists()


@pytest.mark.parametrize("python_fd_mode", ["wrong", "closed"])
def test_loader_rejects_wrong_or_closed_python_fd(
    tmp_path: Path,
    python_fd_mode: str,
) -> None:
    python_path = Path(sys.executable).resolve()
    python_identity = VALIDATION._snapshot_identity(python_path)  # noqa: SLF001
    script_path = tmp_path / "loader_fixture.py"
    script_path.write_bytes(b"print('must not run')\n")
    script_path.chmod(0o444)
    script_identity = VALIDATION._snapshot_identity(script_path)  # noqa: SLF001
    python_fd = os.open(
        python_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    script_fd = os.open(
        script_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    closed_fd = os.open(
        script_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    os.close(closed_fd)
    supplied_python_fd = script_fd if python_fd_mode == "wrong" else closed_fd
    argv = [
        str(python_path),
        "-I",
        "-c",
        VALIDATION._SCRIPT_LOADER,  # noqa: SLF001
        str(supplied_python_fd),
        str(script_fd),
        str(python_path),
        str(python_identity["mode"]),
        str(python_identity["size_bytes"]),
        str(python_identity["sha256"]),
        str(script_path),
        str(script_identity["mode"]),
        str(script_identity["size_bytes"]),
        str(script_identity["sha256"]),
    ]
    try:
        completed = subprocess.run(
            argv,
            check=False,
            close_fds=True,
            executable=f"/proc/self/fd/{python_fd}",
            pass_fds=(python_fd, script_fd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
    finally:
        os.close(script_fd)
        os.close(python_fd)
    assert completed.returncode != 0
    assert b"must not run" not in completed.stdout
    assert b"Could not find platform dependent libraries" not in completed.stderr


def test_same_fd_runner_rejects_script_identity_drift(
    tmp_path: Path,
) -> None:
    python_identity = VALIDATION._snapshot_identity(  # noqa: SLF001
        Path(sys.executable).resolve()
    )
    script_path = tmp_path / "drifted.py"
    script_identity = _regular(script_path, b"print('original')\n")
    script_path.chmod(0o644)
    script_path.write_bytes(b"print('mutated')\n")
    script_path.chmod(0o444)

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="preflight script identity drifted",
    ):
        VALIDATION._run_same_fd_python_script(  # noqa: SLF001
            python_identity=python_identity,
            script_identity=script_identity,
            repository=tmp_path,
            forwarded=(),
            environment=os.environ,
            timeout_seconds=20,
        )


def test_failed_full_preflight_is_immutable_and_cannot_finalize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _, result = _record(tmp_path, monkeypatch, exit_code=1)
    receipt = json.loads((output / "receipt.json").read_text())
    assert result["status"] == "FAIL_CLOSED"
    assert receipt["status"] == "FAIL_CLOSED"
    assert receipt["exit_code"] == 1
    assert receipt["timed_out"] is False
    assert receipt["authorizations"] == {
        "formal_campaign_creation_authorized": False,
        "organic_arm_launch_authorized": False,
        "solver_run_authorized": False,
    }
    assert receipt["pytest_scratch"]["status"] == "PRESERVED_AFTER_PREFLIGHT_FAILURE"
    assert (output / "pytest-scratch").is_dir()

    gate_a_path = tmp_path / "gate-a-should-not-exist.json"
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="not an exact PASS",
    ):
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=output / "receipt.json",
            output_path=gate_a_path,
            approval_id="gate-a-fixture-fail",
            target_campaign_dir=tmp_path / "run-fixture-fail",
            run_nonce="run-fixture-fail",
        )
    assert not gate_a_path.exists()
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="no-overwrite",
    ):
        VALIDATION.record_full_preflight(
            authority_root=tmp_path / "drill",
            repository_root=tmp_path / "repository",
            output_dir=output,
        )


def test_successful_full_preflight_finalizes_only_nonauthorizing_gate_a(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _, result = _record(tmp_path, monkeypatch, exit_code=0)
    assert result["status"] == "PASS"
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["schema_version"] == VALIDATION.PREFLIGHT_SCHEMA
    basetemp = Path(receipt["pytest_scratch"]["basetemp_path"])
    repository = Path(receipt["repository_root"])
    assert receipt["command"] == {
        "argv": [
            receipt["python_identity"]["path"],
            "-I",
            "-B",
            receipt["qualification_runner_identity"]["path"],
            "--repository-root",
            str(repository),
            "--basetemp",
            str(basetemp),
            "--basetemp-relative",
            basetemp.relative_to(repository).as_posix(),
            "--expected-count",
            str(receipt["pytest_collection"]["collection_count"]),
            "--expected-sha256",
            receipt["pytest_collection"]["collection_sha256"],
            "--preflight-source",
            receipt["preflight_script_identity"]["path"],
            "--collection-protocol-source",
            receipt["pytest_collection_protocol_identity"]["path"],
            "--collection-plugin-source",
            receipt["pytest_collection_plugin_identity"]["path"],
            "--full",
        ],
        "execution_strategy": VALIDATION.PREFLIGHT_EXECUTION_STRATEGY,
        "loader_identity": VALIDATION._loader_identity(),  # noqa: SLF001
    }
    gate_a_path = tmp_path / "gate-a-pass.json"
    final = VALIDATION.finalize_gate_a(
        authority_root=tmp_path / "drill",
        preflight_receipt=output / "receipt.json",
        output_path=gate_a_path,
        approval_id="gate-a-fixture-pass",
        target_campaign_dir=tmp_path / "run-fixture-pass",
        run_nonce="run-fixture-pass",
    )
    gate_a = final["gate_a"]
    assert final["status"] == "PASS"
    assert gate_a["decision"] == "PASS"
    assert gate_a["offline_candidate_only"] is True
    assert gate_a["arm_launch_authorized"] is False
    assert gate_a["formal_campaign_creation_authorized"] is False
    assert json.loads(gate_a_path.read_text()) == gate_a
    VALIDATION.bootstrap._validate_gate_a(gate_a)  # noqa: SLF001

    with pytest.raises(
        VALIDATION.bootstrap.authority.AuthorityError,
        match="overwrite",
    ) as collision:
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=output / "receipt.json",
            output_path=gate_a_path,
            approval_id="gate-a-fixture-pass",
            target_campaign_dir=tmp_path / "run-fixture-pass",
            run_nonce="run-fixture-pass",
        )
    assert collision.value.code == "NO_OVERWRITE_COLLISION"


@pytest.mark.parametrize(
    "mutation",
    ["late-basetemp-file", "unexpected-outer-child", "basetemp-replacement", "basetemp-symlink", "outer-replacement"],
)
def test_retained_success_scratch_mutation_blocks_finalize_and_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    output, _, result = _record(tmp_path, monkeypatch, exit_code=0)
    assert result["status"] == "PASS"
    scratch_root = output / VALIDATION.PREFLIGHT_SCRATCH_BASENAME
    basetemp = scratch_root / VALIDATION.PREFLIGHT_BASETEMP_BASENAME
    preserved: list[Path] = []
    if mutation == "late-basetemp-file":
        preserved = [basetemp / "unknown"]
        preserved[0].write_bytes(b"late scratch replacement\n")
    elif mutation == "unexpected-outer-child":
        preserved = [scratch_root / "unknown"]
        preserved[0].write_bytes(b"late scratch replacement\n")
    elif mutation == "basetemp-replacement":
        moved = scratch_root / "basetemp-moved"
        basetemp.rename(moved)
        basetemp.mkdir(mode=0o700)
        preserved = [moved, basetemp]
    elif mutation == "basetemp-symlink":
        moved = scratch_root / "basetemp-moved"
        basetemp.rename(moved)
        basetemp.symlink_to(moved.name)
        preserved = [moved, basetemp]
    elif mutation == "outer-replacement":
        moved = output / "pytest-scratch-moved"
        scratch_root.rename(moved)
        scratch_root.mkdir(mode=0o700)
        (scratch_root / VALIDATION.PREFLIGHT_BASETEMP_BASENAME).mkdir(mode=0o700)
        preserved = [moved, scratch_root]
    else:  # pragma: no cover - static parameter list
        raise AssertionError("unreachable mutation")
    gate_a_path = tmp_path / "gate-a-should-not-exist.json"

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="output-root|scratch|basetemp",
    ):
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=output / "receipt.json",
            output_path=gate_a_path,
            approval_id="gate-a-fixture-recreated",
            target_campaign_dir=tmp_path / "run-fixture-recreated",
            run_nonce="run-fixture-recreated",
        )

    assert not gate_a_path.exists()
    assert all(path.exists() or path.is_symlink() for path in preserved)


@pytest.mark.parametrize("mutation", ["strategy", "loader", "argv"])
def test_finalize_rejects_preflight_execution_chain_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    output, _, result = _record(tmp_path, monkeypatch, exit_code=0)
    assert result["status"] == "PASS"
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if mutation == "strategy":
        receipt["command"]["execution_strategy"] = "same-fd-python-and-script-compile-exec-v1"
    elif mutation == "loader":
        receipt["command"]["loader_identity"]["sha256"] = "0" * 64
    elif mutation == "argv":
        receipt["command"]["argv"][0] = "/mutable/python3.13"
    else:  # pragma: no cover - the parameter list is static
        raise AssertionError("unreachable mutation")
    receipt_path.chmod(0o644)
    receipt_path.write_bytes(VALIDATION.verifier.canonical_json_bytes(receipt))
    receipt_path.chmod(0o444)
    _reseal_publication_commit(output, receipt)

    gate_a_path = tmp_path / f"gate-a-{mutation}.json"
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="tool/command identity drifted",
    ):
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=receipt_path,
            output_path=gate_a_path,
            approval_id=f"gate-a-fixture-{mutation}",
            target_campaign_dir=tmp_path / f"run-fixture-{mutation}",
            run_nonce=f"run-fixture-{mutation}",
        )
    assert not gate_a_path.exists()


def test_detached_replay_mutation_blocks_finalize_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, detached_replay_path, result = _record(
        tmp_path,
        monkeypatch,
        exit_code=0,
    )
    assert result["status"] == "PASS"
    detached_replay_path.chmod(0o644)
    detached_replay_path.write_bytes(b'{"status":"MUTATED"}')
    detached_replay_path.chmod(0o444)

    gate_a_path = tmp_path / "gate-a-mutation.json"
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="detached_replay_identity byte identity drifted",
    ):
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=output / "receipt.json",
            output_path=gate_a_path,
            approval_id="gate-a-fixture-mutation",
            target_campaign_dir=tmp_path / "run-fixture-mutation",
            run_nonce="run-fixture-mutation",
        )
    assert not gate_a_path.exists()
