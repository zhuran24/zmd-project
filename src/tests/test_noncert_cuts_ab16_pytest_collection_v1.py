from __future__ import annotations

import argparse
import errno
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AB16_DIR = PROJECT_ROOT / "docs/research/noncert_cuts_ab16_20260724"
PROTOCOL_PATH = AB16_DIR / "ab16_pytest_collection_protocol_v1.py"
PLUGIN_PATH = AB16_DIR / "ab16_pytest_collection_plugin_v1.py"
RUNNER_PATH = AB16_DIR / "ab16_preflight_qualification_v1.py"
FIXED_NONCE = "1" * 64
ONE_ITEM = [
    {
        "nodeid": "src/tests/test_sample.py::test_ok",
        "path": "src/tests/test_sample.py",
    }
]
ONE_ORIGIN = [
    {
        "kind": "file",
        "module": "test_sample",
        "path": "src/tests/test_sample.py",
        "resolved_path": "src/tests/test_sample.py",
    }
]


def _load_source(name: str, path: Path) -> ModuleType:
    raw = path.read_bytes()
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(
            compile(raw, str(path), "exec", dont_inherit=True),
            vars(module),
            vars(module),
        )
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


PROTOCOL = _load_source("_test_ab16_pytest_collection_protocol_v1", PROTOCOL_PATH)
PLUGIN = _load_source("_test_ab16_pytest_collection_plugin_v1", PLUGIN_PATH)
RUNNER = _load_source("_test_ab16_preflight_qualification_v1", RUNNER_PATH)


def _one_digest() -> str:
    return PROTOCOL.collection_nodeids_sha256(ONE_ITEM)


def _completed_session() -> tuple[Any, Any]:
    session = PROTOCOL.AB16CollectionSession.create(
        expected_count=1,
        expected_sha256=_one_digest(),
        nonce=FIXED_NONCE,
    )
    session.publish_stage(
        items=ONE_ITEM,
        module_origins=ONE_ORIGIN,
        workflow=PROTOCOL.COLLECTION_WORKFLOW,
        markexpr=PROTOCOL.COLLECTION_MARKEXPR,
    )
    session.publish_terminal(exitstatus=0, module_origins=ONE_ORIGIN)
    return session, session.validate(returncode=0)


def test_collection_protocol_requires_exactly_two_strict_records_and_rejects_tampering() -> None:
    session, validated = _completed_session()
    try:
        assert validated.projection["collection_count"] == 1
        assert validated.projection["collection_sha256"] == _one_digest()
        assert validated.projection["manifest_sha256"] == PROTOCOL.collection_manifest_sha256(ONE_ITEM)

        expectation = PROTOCOL.AB16CollectionExpectation(1, _one_digest())
        stage = dict(validated.stage)
        terminal = dict(validated.terminal)
        altered_stage = dict(stage)
        altered_stage["collection_count"] = 2
        altered_terminal = dict(terminal)
        altered_terminal["nonce"] = "2" * 64
        duplicate_key_stage = validated.stage_raw.replace(
            b'{"collection_count":1,',
            b'{"collection_count":1,"collection_count":1,',
            1,
        )
        tampered_records = (
            validated.raw + b"{}\n",
            PROTOCOL.canonical_json_line(altered_stage) + validated.terminal_raw,
            validated.stage_raw + PROTOCOL.canonical_json_line(altered_terminal),
            duplicate_key_stage + validated.terminal_raw,
        )
        for raw in tampered_records:
            with pytest.raises(PROTOCOL.AB16CollectionProtocolError):
                PROTOCOL.validate_collection_records(
                    raw,
                    expectation=expectation,
                    nonce=FIXED_NONCE,
                    returncode=0,
                )
    finally:
        session.close()


class _CloseTrackingStream:
    def __init__(self, stream: Any, *, fail_once: bool = False) -> None:
        self.stream = stream
        self.fail_once = fail_once
        self.close_count = 0

    @property
    def closed(self) -> bool:
        return bool(self.stream.closed)

    def fileno(self) -> int:
        return int(self.stream.fileno())

    def close(self) -> None:
        self.close_count += 1
        if self.fail_once:
            self.fail_once = False
            raise OSError(errno.EIO, "injected close failure")
        self.stream.close()


def test_collection_transport_owns_close_once_on_the_normal_path() -> None:
    underlying = tempfile.TemporaryFile(mode="w+b", buffering=0, dir="/tmp")
    stream = _CloseTrackingStream(underlying)
    transport = PROTOCOL.AB16AnonymousTransport(stream)

    transport.close()
    transport.close()

    assert transport.closed is True
    assert stream.close_count == 1
    assert underlying.closed is True


def test_collection_transport_close_failure_is_not_reported_as_closed_and_can_be_retried() -> None:
    underlying = tempfile.TemporaryFile(mode="w+b", buffering=0, dir="/tmp")
    stream = _CloseTrackingStream(underlying, fail_once=True)
    transport = PROTOCOL.AB16AnonymousTransport(stream)

    with pytest.raises(PROTOCOL.AB16CollectionProtocolError, match="close failed"):
        transport.close()
    assert transport.closed is False
    assert stream.close_count == 1
    assert underlying.closed is False

    transport.close()
    assert transport.closed is True
    assert stream.close_count == 2
    assert underlying.closed is True


class _WorkflowOptionPlugin:
    def pytest_addoption(self, parser: pytest.Parser) -> None:
        parser.addoption(
            "--repository-workflow",
            action="store",
            default="auto",
        )


def test_explicit_plugin_object_records_the_actual_serial_full_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    tests = repository / "src/tests"
    tests.mkdir(parents=True)
    (repository / "pytest.ini").write_text("[pytest]\naddopts =\n", encoding="utf-8")
    (tests / "test_sample.py").write_text(
        "def test_ok():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    basetemp = repository / "pytest-scratch/basetemp"
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)
    # These legacy ambient values are intentionally irrelevant to the explicit
    # session/plugin-object handoff.
    monkeypatch.setenv("AB16_PYTEST_COLLECTION_FD", "0")
    monkeypatch.setenv("AB16_PYTEST_COLLECTION_NONCE", "ambient-is-not-authority")

    session = PROTOCOL.AB16CollectionSession.create(
        expected_count=1,
        expected_sha256=_one_digest(),
        nonce=FIXED_NONCE,
    )
    plugin = PLUGIN.AB16PytestCollectionPlugin(
        session=session,
        repository_root=repository,
        basetemp_root=basetemp,
    )
    try:
        returncode = int(
            pytest.main(
                [
                    "-q",
                    "-p",
                    "randomly",
                    "-p",
                    "no:cacheprovider",
                    "--rootdir",
                    str(repository),
                    "-c",
                    str(repository / "pytest.ini"),
                    "--confcutdir",
                    str(tests),
                    "--repository-workflow=full",
                    "-m",
                    "not slow",
                    "--basetemp",
                    str(basetemp),
                    str(tests),
                ],
                plugins=[_WorkflowOptionPlugin(), plugin],
            )
        )
        validated = session.validate(returncode=returncode)
    finally:
        session.close()

    assert returncode == 0
    assert validated.projection["workflow"] == "full"
    assert validated.projection["markexpr"] == "not slow"
    assert validated.stage["items"] == ONE_ITEM


def _source_binding(path: Path, role: str) -> tuple[list[str], int, bytes]:
    raw = f"ROLE = {role!r}\n".encode("ascii")
    path.write_bytes(raw)
    path.chmod(0o644)
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    return (
        [
            role,
            str(descriptor),
            str(path),
            str(0o644),
            str(len(raw)),
            hashlib.sha256(raw).hexdigest(),
        ],
        descriptor,
        raw,
    )


def test_qualification_runner_support_sources_bind_fd_path_identity_and_close_ownership(
    tmp_path: Path,
) -> None:
    bindings = [
        _source_binding(tmp_path / f"{role}.py", role)
        for role in ("plugin", "preflight", "protocol")
    ]
    records = [binding[0] for binding in bindings]
    descriptors = [binding[1] for binding in bindings]
    expected = {binding[0][0]: binding[2] for binding in bindings}

    observed, paths = RUNNER._support_sources(records)

    assert observed == expected
    assert paths == {
        role: tmp_path / f"{role}.py"
        for role in ("plugin", "preflight", "protocol")
    }
    for descriptor in descriptors:
        with pytest.raises(OSError) as error:
            os.fstat(descriptor)
        assert error.value.errno == errno.EBADF


def test_qualification_runner_rejects_fd_path_and_digest_drift(tmp_path: Path) -> None:
    first_record, first_fd, first_raw = _source_binding(tmp_path / "first.py", "plugin")
    second_path = tmp_path / "second.py"
    second_path.write_bytes(first_raw)
    second_path.chmod(0o644)
    try:
        with pytest.raises(
            RUNNER.AB16PreflightQualificationError,
            match="path/descriptor join drifted",
        ):
            RUNNER._snapshot_bound_source(
                descriptor=first_fd,
                path=second_path,
                mode=0o644,
                size_bytes=len(first_raw),
                sha256=hashlib.sha256(first_raw).hexdigest(),
                role="plugin",
            )
        with pytest.raises(
            RUNNER.AB16PreflightQualificationError,
            match="identity drifted",
        ):
            RUNNER._snapshot_bound_source(
                descriptor=first_fd,
                path=Path(first_record[2]),
                mode=0o644,
                size_bytes=len(first_raw),
                sha256="0" * 64,
                role="plugin",
            )
    finally:
        os.close(first_fd)


def test_qualification_runner_closes_owned_fd_when_later_binding_validation_fails(
    tmp_path: Path,
) -> None:
    record, descriptor, _raw = _source_binding(tmp_path / "plugin.py", "plugin")
    record[-1] = "not-a-sha256"

    with pytest.raises(
        RUNNER.AB16PreflightQualificationError,
        match="binding is malformed",
    ):
        RUNNER._support_sources([record])

    with pytest.raises(OSError) as error:
        os.fstat(descriptor)
    assert error.value.errno == errno.EBADF


def _runner_args(repository: Path) -> argparse.Namespace:
    return argparse.Namespace(
        basetemp=repository / ".artifacts/preflight/pytest-scratch/basetemp",
        basetemp_relative=Path(".artifacts/preflight/pytest-scratch/basetemp"),
        collection_plugin_source=repository / "plugin.py",
        collection_protocol_source=repository / "protocol.py",
        expected_count=1,
        expected_sha256=_one_digest(),
        full=True,
        preflight_source=repository / "preflight.py",
        repository_root=repository,
        support_source=[],
    )


def test_qualification_runner_rejects_support_cli_path_disagreement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    args = _runner_args(repository)
    monkeypatch.setattr(RUNNER, "_require_isolated_runtime", lambda _root: None)
    monkeypatch.setattr(
        RUNNER,
        "_support_sources",
        lambda _values: (
            {"plugin": b"", "preflight": b"", "protocol": b""},
            {
                "plugin": repository / "different-plugin.py",
                "preflight": args.preflight_source,
                "protocol": args.collection_protocol_source,
            },
        ),
    )

    with pytest.raises(
        RUNNER.AB16PreflightQualificationError,
        match="CLI/path binding drifted",
    ):
        RUNNER._run_qualification(args)


def test_qualification_runner_cli_keeps_all_support_identity_fields_explicit(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    support = [
        "plugin",
        "10",
        str(repository / "plugin.py"),
        str(0o644),
        "10",
        "a" * 64,
    ]
    parsed = RUNNER._parser().parse_args(
        [
            "--repository-root",
            str(repository),
            "--basetemp",
            str(repository / "scratch/basetemp"),
            "--basetemp-relative",
            "scratch/basetemp",
            "--expected-count",
            "1",
            "--expected-sha256",
            _one_digest(),
            "--preflight-source",
            str(repository / "preflight.py"),
            "--collection-protocol-source",
            str(repository / "protocol.py"),
            "--collection-plugin-source",
            str(repository / "plugin.py"),
            "--support-source",
            *support,
            "--full",
        ]
    )

    assert parsed.full is True
    assert parsed.support_source == [support]
    assert parsed.expected_count == 1
    assert parsed.expected_sha256 == _one_digest()


class _FakeGate:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def ok(self, message: str) -> None:
        self.events.append(("gate.ok", message))

    def block(self, message: str) -> None:
        self.events.append(("gate.block", message))


class _CapturedBuffer:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.data = bytearray()

    def write(self, raw: bytes) -> int:
        self.events.append(("stdout.write", bytes(raw)))
        self.data.extend(raw)
        return len(raw)

    def flush(self) -> None:
        self.events.append("stdout.buffer.flush")


class _CapturedStdout:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.buffer = _CapturedBuffer(events)

    def flush(self) -> None:
        self.events.append("stdout.flush")


def _install_runner_fakes(
    *,
    monkeypatch: pytest.MonkeyPatch,
    args: argparse.Namespace,
    fail_close: bool,
) -> tuple[list[object], _CapturedStdout, Any, Any]:
    events: list[object] = []
    captured = _CapturedStdout(events)

    class FakeValidated:
        def stdout_bytes(self) -> bytes:
            assert fake_session.closed is True
            events.append("validated.stdout_bytes")
            return b"AB16_PYTEST_COLLECTION_RECORD={}\n"

    class FakeSession:
        workflow = "full"

        def __init__(self) -> None:
            self.closed = False

        def validate(self, *, returncode: int) -> FakeValidated:
            events.append(("session.validate", returncode))
            return FakeValidated()

        def close(self) -> None:
            events.append("session.close")
            if fail_close:
                raise OSError(errno.EIO, "injected session close failure")
            self.closed = True

    fake_session = FakeSession()

    class FakeSessionType:
        @classmethod
        def create(cls, *, expected_count: int, expected_sha256: str) -> FakeSession:
            events.append(("session.create", expected_count, expected_sha256))
            return fake_session

    class FakePlugin:
        def __init__(self, **values: object) -> None:
            events.append(("plugin.create", dict(values)))

    preflight = SimpleNamespace(check_tests=lambda _gate, *, full=False: None)
    original_check_tests = preflight.check_tests

    def run_gate(*, full: bool = False) -> int:
        events.append(("run_gate", full))
        preflight.check_tests(_FakeGate(events), full=full)
        return 0

    preflight.run_gate = run_gate
    protocol = SimpleNamespace(AB16CollectionSession=FakeSessionType)
    plugin_module = SimpleNamespace(AB16PytestCollectionPlugin=FakePlugin)
    support_paths = {
        "plugin": args.collection_plugin_source,
        "preflight": args.preflight_source,
        "protocol": args.collection_protocol_source,
    }
    monkeypatch.setattr(RUNNER, "_require_isolated_runtime", lambda _root: None)
    monkeypatch.setattr(
        RUNNER,
        "_support_sources",
        lambda _values: (
            {"plugin": b"plugin", "preflight": b"preflight", "protocol": b"protocol"},
            support_paths,
        ),
    )
    monkeypatch.setattr(
        RUNNER,
        "_load_pinned_module",
        lambda *, role, path, raw: {
            "plugin": plugin_module,
            "preflight": preflight,
            "protocol": protocol,
        }[role],
    )
    monkeypatch.setattr(
        pytest,
        "main",
        lambda arguments, *, plugins: (
            events.append(("pytest.main", list(arguments), list(plugins))) or 0
        ),
    )
    monkeypatch.setattr(RUNNER, "sys", SimpleNamespace(stdout=captured))
    return events, captured, fake_session, (preflight, original_check_tests)


def test_qualification_runner_emits_no_collection_record_until_session_close_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    args = _runner_args(repository)
    events, captured, session, preflight_state = _install_runner_fakes(
        monkeypatch=monkeypatch,
        args=args,
        fail_close=False,
    )
    preflight, original_check_tests = preflight_state

    assert RUNNER._run_qualification(args) == 0
    assert session.closed is True
    assert bytes(captured.buffer.data) == b"AB16_PYTEST_COLLECTION_RECORD={}\n"
    assert events.index("session.close") < events.index("validated.stdout_bytes")
    assert events.index("validated.stdout_bytes") < next(
        index
        for index, event in enumerate(events)
        if isinstance(event, tuple) and event[0] == "stdout.write"
    )
    pytest_event = next(event for event in events if isinstance(event, tuple) and event[0] == "pytest.main")
    pytest_arguments = pytest_event[1]
    explicit_plugins = pytest_event[2]
    assert "--repository-workflow=full" in pytest_arguments
    assert "-m" in pytest_arguments
    assert "not slow" in pytest_arguments
    assert len(explicit_plugins) == 1
    assert preflight.check_tests is original_check_tests


def test_qualification_runner_close_failure_suppresses_all_collection_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    args = _runner_args(repository)
    events, captured, session, _preflight_state = _install_runner_fakes(
        monkeypatch=monkeypatch,
        args=args,
        fail_close=True,
    )

    with pytest.raises(OSError, match="injected session close failure"):
        RUNNER._run_qualification(args)

    assert session.closed is False
    assert bytes(captured.buffer.data) == b""
    assert "validated.stdout_bytes" not in events
    assert not any(
        isinstance(event, tuple) and event[0] == "stdout.write"
        for event in events
    )


def test_qualification_runner_rejects_ordinary_or_ambient_pytest_environments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    fake_sys = SimpleNamespace(
        flags=SimpleNamespace(isolated=0, dont_write_bytecode=1),
        path=["/usr/lib/python3.13"],
    )
    monkeypatch.setattr(RUNNER, "sys", fake_sys)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)

    with pytest.raises(
        RUNNER.AB16PreflightQualificationError,
        match="fixed isolated Python/pytest environment",
    ):
        RUNNER._require_isolated_runtime(repository)
    fake_sys.flags = SimpleNamespace(isolated=1, dont_write_bytecode=1)
    RUNNER._require_isolated_runtime(repository)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p ambient-plugin")
    with pytest.raises(
        RUNNER.AB16PreflightQualificationError,
        match="fixed isolated Python/pytest environment",
    ):
        RUNNER._require_isolated_runtime(repository)


def test_qualification_runner_allows_pinned_runtime_prefix_but_rejects_repo_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    runtime = repository / ".pinned-venv"
    site_packages = runtime / "lib/python3.13/site-packages"
    repository_source = repository / "src"
    site_packages.mkdir(parents=True)
    repository_source.mkdir(parents=True)
    outside_link = tmp_path / "repo-source-link"
    outside_link.symlink_to(repository_source, target_is_directory=True)
    fake_sys = SimpleNamespace(
        base_exec_prefix=str(runtime),
        base_prefix=str(runtime),
        exec_prefix=str(runtime),
        flags=SimpleNamespace(isolated=1, dont_write_bytecode=1),
        path=[str(site_packages)],
        prefix=str(runtime),
    )
    monkeypatch.setattr(RUNNER, "sys", fake_sys)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)

    RUNNER._require_isolated_runtime(repository)
    fake_sys.path = [str(outside_link)]
    with pytest.raises(
        RUNNER.AB16PreflightQualificationError,
        match="inherited a repository path",
    ):
        RUNNER._require_isolated_runtime(repository)
