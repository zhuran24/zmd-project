from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_budget_broker_v1 as broker,
    ab16_formal_loader_v1 as loader,
)


class _SocketView:
    family = loader.socket.AF_UNIX

    def detach(self) -> int:
        return loader.BUDGET_BROKER_FD


class _NativeAuthorization:
    def __init__(self) -> None:
        self.helper = object()
        self.close_count = 0
        self.close_error: BaseException | None = None

    def close(self) -> None:
        self.close_count += 1
        if self.close_error is not None:
            raise self.close_error


def _stdio_contract() -> list[dict[str, object]]:
    return [
        {
            "access": (
                "read-only" if descriptor == 0 else "write-only"
            ),
            "descriptor": descriptor,
            "device": 101 + descriptor,
            "inode": 201 + descriptor,
            "kind": "pipe",
            "mode": 0o600,
            "rdev": 0,
        }
        for descriptor in range(3)
    ]


class _Backend:
    def __init__(self) -> None:
        self.close_count = 0
        self.close_error: BaseException | None = None
        self.confinement_count = 0

    def install_worker_confinement(
        self,
        retained_read_only_fds: tuple[int, ...],
    ) -> dict[str, object]:
        assert retained_read_only_fds == ()
        self.confinement_count += 1
        return {
            "filesystem_write_confinement": (
                "landlock-read-only-worker-v1"
            ),
            "retained_read_only_fds": [],
            "root_or_staging_writable_fd_count": 0,
            "stdio_contract": _stdio_contract(),
        }

    def close(self) -> None:
        self.close_count += 1
        if self.close_error is not None:
            raise self.close_error


class _RealBackendHelper:
    def __init__(self) -> None:
        self.allowlists: list[list[int]] = []
        self.landlock_count = 0

    def landlock_abi(self) -> int:
        return 1

    def close_range_allowlist(self, descriptors: list[int]) -> None:
        self.allowlists.append(list(descriptors))

    def install_no_filesystem_writes_landlock(self) -> None:
        self.landlock_count += 1


class _RealBackendBrokerClient:
    def __init__(self) -> None:
        self.connection = SimpleNamespace(
            fileno=lambda: loader.BUDGET_BROKER_FD
        )
        self.closed = False
        self.close_count = 0

    def close_session(self) -> None:
        self.close_count += 1
        self.closed = True


def _real_formal_worker_backend() -> tuple[
    broker.BrokerProcessFormalBudgetBackend,
    _RealBackendHelper,
    _RealBackendBrokerClient,
]:
    helper = _RealBackendHelper()
    client = _RealBackendBrokerClient()
    backend = object.__new__(broker.BrokerProcessFormalBudgetBackend)
    backend._broker = client  # noqa: SLF001
    backend._helper = helper  # noqa: SLF001
    backend._require_worker_confinement = True  # noqa: SLF001
    backend._confinement_installed = False  # noqa: SLF001
    return backend, helper, client


def _session() -> dict[str, object]:
    return {
        "broker_grant": {"opaque": "factory-validates-the-exact-grant"},
        "credential": "a" * 64,
        "schema_version": loader.FORMAL_WORKER_SESSION_SCHEMA,
    }


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _install_main_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    role: str,
    formal_selection: Path | None,
    worker_session: str | None,
    selected_module: ModuleType,
    argument_overrides: dict[str, object] | None = None,
) -> tuple[_NativeAuthorization, list[int]]:
    args = Namespace(
        authority_fd=loader.AUTHORITY_FD,
        authority_identity="authority",
        budget_broker_fd=loader.BUDGET_BROKER_FD,
        campaign_dir=Path("/campaign"),
        formal_launch_claim_fd=None,
        formal_launch_claim_identity=None,
        formal_selection_for_budget=formal_selection,
        formal_supervisor_session_fd=None,
        formal_worker_session_json=worker_session,
        loader_identity="loader",
        native_helper_fd=loader.NATIVE_HELPER_FD,
        native_helper_identity="helper",
        native_helper_wrapper_fd=loader.NATIVE_HELPER_WRAPPER_FD,
        native_helper_wrapper_identity="wrapper",
        role=role,
        role_argv=[],
    )
    for name, value in (argument_overrides or {}).items():
        setattr(args, name, value)
    if role == "formal-controller":
        assert formal_selection is not None
        args.role_argv = [
            "--",
            "--campaign-dir",
            "/campaign",
            "--formal-selection",
            str(formal_selection),
        ]
    elif role in {"organic-arm", "organic-supervisor"}:
        args.role_argv = [
            "--pre-run",
            "/pre-run.json",
            "--selection",
            "/selection.json",
            "--module-origin-receipt",
            "/module-origin-receipt.json",
        ]
    monkeypatch.setattr(
        loader,
        "_parser",
        lambda: SimpleNamespace(parse_args=lambda _argv: args),
    )
    monkeypatch.setattr(loader, "_parse_loader_identity", lambda _value: {})
    monkeypatch.setattr(
        loader,
        "_verify_executing_loader",
        lambda _identity: ModuleType("__main__"),
    )
    monkeypatch.setattr(loader, "_parse_authority_identity", lambda _value: {})
    monkeypatch.setattr(
        loader,
        "load_selected_authority_from_fd",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        loader,
        "_parse_mode_identity_argument",
        lambda _value, *, label: {"label": label},
    )
    monkeypatch.setattr(
        loader.socket,
        "socket",
        lambda *, fileno: _SocketView(),
    )
    authorization = _NativeAuthorization()
    monkeypatch.setattr(
        loader,
        "load_selected_native_budget_helper_from_fds",
        lambda **_kwargs: authorization,
    )
    monkeypatch.setattr(
        loader,
        "load_verified_role",
        lambda *_args, **_kwargs: loader.LoadedRole(
            context={},
            module=selected_module,
            role=role,
        ),
    )
    closed: list[int] = []
    monkeypatch.setattr(loader.os, "close", closed.append)
    return authorization, closed


def test_formal_controller_loader_transfers_fd8_and_closes_backend_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_formal_controller")
    selection = Path("/campaign/formal-selection.json")
    backend = _Backend()
    observed: dict[str, Any] = {}

    def factory(descriptor: int, **kwargs: object) -> _Backend:
        observed["factory"] = (descriptor, kwargs)
        return backend

    def entrypoint(argv: list[str], **kwargs: object) -> int:
        observed["entrypoint"] = (argv, kwargs)
        observed["native_closed_at_entry"] = authorization.close_count
        observed["source_closed_at_entry"] = tuple(closed)
        return 0

    selected.formal_budget_backend_from_fd = factory
    selected.main = entrypoint
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role="formal-controller",
        formal_selection=selection,
        worker_session=None,
        selected_module=selected,
    )

    assert loader.main([]) == 0
    descriptor, factory_kwargs = observed["factory"]
    assert descriptor == loader.BUDGET_BROKER_FD
    assert factory_kwargs == {
        "campaign_dir": Path("/campaign"),
        "formal_selection": selection,
        "native_budget_helper": authorization.helper,
    }
    _argv, entrypoint_kwargs = observed["entrypoint"]
    assert entrypoint_kwargs == {
        "formal_budget_backend": backend,
        "native_budget_helper": authorization.helper,
    }
    assert backend.close_count == 1
    assert backend.confinement_count == 0
    assert authorization.close_count == 1
    assert observed["native_closed_at_entry"] == 1
    assert set(observed["source_closed_at_entry"]) == {
        loader.AUTHORITY_FD,
        loader.LOADER_FD,
        loader.PYTHON_FD,
    }
    assert loader.BUDGET_BROKER_FD not in closed


@pytest.mark.parametrize(
    ("role", "expects_prospective"),
    [
        ("baseline-admission", True),
        ("baseline-rebuild", True),
        ("cut-free-incumbent-replay", False),
    ],
)
def test_formal_worker_loader_requires_canonical_session_and_closes_once(
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    expects_prospective: bool,
) -> None:
    selected = ModuleType(f"_selected_{role}")
    selection = Path("/campaign/formal-selection.json")
    session = _session()
    backend = _Backend()
    observed: dict[str, Any] = {}

    def factory(descriptor: int, **kwargs: object) -> _Backend:
        observed["factory"] = (descriptor, kwargs)
        return backend

    def entrypoint(argv: list[str], **kwargs: object) -> int:
        observed["entrypoint"] = (argv, kwargs)
        observed["native_closed_at_entry"] = authorization.close_count
        observed["source_closed_at_entry"] = tuple(closed)
        return 0

    selected.formal_worker_budget_backend_from_fd = factory
    selected.main = entrypoint
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role=role,
        formal_selection=selection,
        worker_session=_canonical(session),
        selected_module=selected,
    )

    assert loader.main([]) == 0
    descriptor, factory_kwargs = observed["factory"]
    assert descriptor == loader.BUDGET_BROKER_FD
    assert factory_kwargs == {
        "campaign_dir": Path("/campaign"),
        "formal_selection": selection,
        "native_budget_helper": authorization.helper,
        "worker_role": role,
        "worker_session": session,
    }
    _argv, entrypoint_kwargs = observed["entrypoint"]
    expected_keywords: dict[str, object] = {"budget_backend": backend}
    if expects_prospective:
        expected_keywords["prospective"] = True
    assert entrypoint_kwargs == expected_keywords
    assert backend.close_count == 1
    assert backend.confinement_count == 1
    assert authorization.close_count == 1
    assert observed["native_closed_at_entry"] == 1
    assert set(observed["source_closed_at_entry"]) == {
        loader.AUTHORITY_FD,
        loader.LOADER_FD,
        loader.PYTHON_FD,
    }
    assert loader.BUDGET_BROKER_FD not in closed


def test_formal_worker_loader_accepts_complete_real_backend_confinement_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_real_backend_worker")
    selection = Path("/campaign/formal-selection.json")
    backend, helper, client = _real_formal_worker_backend()
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        broker,
        "validate_worker_stdio_contract",
        _stdio_contract,
    )

    def factory(
        descriptor: int,
        **kwargs: object,
    ) -> broker.BrokerProcessFormalBudgetBackend:
        observed["factory"] = (descriptor, kwargs)
        return backend

    def entrypoint(argv: list[str], **kwargs: object) -> int:
        observed["entrypoint"] = (argv, kwargs)
        return 0

    selected.formal_worker_budget_backend_from_fd = factory
    selected.main = entrypoint
    _authorization, _closed = _install_main_stubs(
        monkeypatch,
        role="baseline-rebuild",
        formal_selection=selection,
        worker_session=_canonical(_session()),
        selected_module=selected,
    )

    assert loader.main([]) == 0
    assert helper.allowlists == [[0, 1, 2, loader.BUDGET_BROKER_FD]]
    assert helper.landlock_count == 1
    assert client.close_count == 1
    assert client.closed is True
    assert observed["entrypoint"] == (
        [],
        {"budget_backend": backend, "prospective": True},
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.pop("stdio_contract"),
        lambda receipt: receipt["stdio_contract"].append(
            dict(receipt["stdio_contract"][0])
        ),
        lambda receipt: receipt["stdio_contract"][1].__setitem__(
            "kind",
            "regular-file",
        ),
        lambda receipt: receipt["stdio_contract"][2].__setitem__(
            "descriptor",
            99,
        ),
    ],
)
def test_worker_confinement_receipt_rejects_stdio_projection_or_drift(
    mutate: Any,
) -> None:
    receipt: dict[str, Any] = {
        "filesystem_write_confinement": (
            "landlock-read-only-worker-v1"
        ),
        "retained_read_only_fds": [],
        "root_or_staging_writable_fd_count": 0,
        "stdio_contract": _stdio_contract(),
    }
    mutate(receipt)
    with pytest.raises(loader.FormalLoaderError):
        loader._validate_worker_confinement_receipt(  # noqa: SLF001
            receipt,
            label="test worker receipt",
        )


def test_factory_failure_owns_fd8_and_loader_does_not_double_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_formal_controller_failure")
    selection = Path("/campaign/formal-selection.json")

    authorization, closed = _install_main_stubs(
        monkeypatch,
        role="formal-controller",
        formal_selection=selection,
        worker_session=None,
        selected_module=selected,
    )

    def factory(descriptor: int, **_kwargs: object) -> object:
        loader.os.close(descriptor)
        raise RuntimeError("factory failure after consume")

    selected.formal_budget_backend_from_fd = factory
    selected.main = lambda *_args, **_kwargs: 0

    assert loader.main([]) == 125
    assert closed.count(loader.BUDGET_BROKER_FD) == 1
    assert authorization.close_count == 1


def test_pre_factory_failure_closes_raw_fd8_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_formal_controller_mismatch")
    selection = Path("/campaign/formal-selection.json")
    selected.formal_budget_backend_from_fd = lambda *_args, **_kwargs: _Backend()
    selected.main = lambda *_args, **_kwargs: 0
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role="formal-controller",
        formal_selection=Path("/campaign/different-selection.json"),
        worker_session=None,
        selected_module=selected,
    )
    monkeypatch.setattr(
        loader,
        "_role_formal_selection",
        lambda _argv: selection,
    )

    assert loader.main([]) == 125
    assert closed.count(loader.BUDGET_BROKER_FD) == 1
    assert authorization.close_count == 1


def test_backend_close_failure_does_not_obscure_primary_and_closes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_formal_controller_close_failure")
    selection = Path("/campaign/formal-selection.json")
    backend = _Backend()
    backend.close_error = RuntimeError("backend close failure")
    primary = ValueError("selected role failure")
    selected.formal_budget_backend_from_fd = (
        lambda *_args, **_kwargs: backend
    )

    def entrypoint(*_args: object, **_kwargs: object) -> int:
        raise primary

    selected.main = entrypoint
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role="formal-controller",
        formal_selection=selection,
        worker_session=None,
        selected_module=selected,
    )

    assert loader.main([]) == 125
    assert backend.close_count == 1
    assert authorization.close_count == 1
    assert loader.BUDGET_BROKER_FD not in closed
    assert any(
        "selected budget backend cleanup failed" in note
        for note in getattr(primary, "__notes__", ())
    )


def test_native_fd_close_failure_before_role_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_formal_controller_native_close_failure")
    selection = Path("/campaign/formal-selection.json")
    backend = _Backend()
    entry_count = 0
    selected.formal_budget_backend_from_fd = (
        lambda *_args, **_kwargs: backend
    )

    def entrypoint(*_args: object, **_kwargs: object) -> int:
        nonlocal entry_count
        entry_count += 1
        return 0

    selected.main = entrypoint
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role="formal-controller",
        formal_selection=selection,
        worker_session=None,
        selected_module=selected,
    )
    authorization.close_error = RuntimeError("native close failure")

    assert loader.main([]) == 125
    assert authorization.close_count == 1
    assert entry_count == 0
    assert backend.close_count == 1
    assert loader.BUDGET_BROKER_FD not in closed


def test_selected_source_close_failure_attempts_each_fd_once_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_formal_controller_source_close_failure")
    selection = Path("/campaign/formal-selection.json")
    backend = _Backend()
    entry_count = 0
    selected.formal_budget_backend_from_fd = (
        lambda *_args, **_kwargs: backend
    )

    def entrypoint(*_args: object, **_kwargs: object) -> int:
        nonlocal entry_count
        entry_count += 1
        return 0

    selected.main = entrypoint
    authorization, _closed = _install_main_stubs(
        monkeypatch,
        role="formal-controller",
        formal_selection=selection,
        worker_session=None,
        selected_module=selected,
    )
    close_counts: dict[int, int] = {}

    def injected_close(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        if descriptor == loader.LOADER_FD:
            raise RuntimeError("source close failure")

    monkeypatch.setattr(loader.os, "close", injected_close)
    assert loader.main([]) == 125
    assert {
        descriptor: close_counts[descriptor]
        for descriptor in (
            loader.PYTHON_FD,
            loader.LOADER_FD,
            loader.AUTHORITY_FD,
        )
    } == {
        loader.PYTHON_FD: 1,
        loader.LOADER_FD: 1,
        loader.AUTHORITY_FD: 1,
    }
    assert entry_count == 0
    assert backend.close_count == 1
    assert authorization.close_count == 1


def test_nonbudget_fd8_close_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_nonbudget_close_failure")
    selected.main = lambda _argv: 0
    authorization, _closed = _install_main_stubs(
        monkeypatch,
        role="formal-success-verifier",
        formal_selection=None,
        worker_session=None,
        selected_module=selected,
    )
    close_count = 0

    def failing_close(descriptor: int) -> None:
        nonlocal close_count
        if descriptor == loader.BUDGET_BROKER_FD:
            close_count += 1
            raise RuntimeError("uncertain close")

    monkeypatch.setattr(loader.os, "close", failing_close)
    assert loader.main([]) == 125
    assert close_count == 1
    assert authorization.close_count == 1


def test_worker_session_parser_rejects_noncanonical_or_mixed_shape() -> None:
    session = _session()
    with pytest.raises(
        loader.FormalLoaderError,
        match="not canonical",
    ):
        loader._parse_formal_worker_session(  # noqa: SLF001
            json.dumps(session, sort_keys=False)
        )
    with pytest.raises(
        loader.FormalLoaderError,
        match="field set drifted",
    ):
        loader._parse_formal_worker_session(  # noqa: SLF001
            _canonical({**session, "unexpected": False})
        )


def test_organic_supervisor_loader_retains_sources_and_attaches_arm_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_organic_supervisor")
    backend = _Backend()
    observed: dict[str, Any] = {}

    def factory(descriptor: int, **kwargs: object) -> _Backend:
        observed["factory"] = (descriptor, kwargs)
        return backend

    def entrypoint(argv: list[str], **kwargs: object) -> int:
        observed["entrypoint"] = (argv, kwargs)
        observed["native_closed_at_entry"] = authorization.close_count
        observed["source_closed_at_entry"] = tuple(closed)
        return 0

    selected.formal_arm_supervisor_budget_backend_from_fd = factory
    selected.main = entrypoint
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role="organic-supervisor",
        formal_selection=None,
        worker_session=None,
        selected_module=selected,
    )

    assert loader.main([]) == 0
    descriptor, factory_kwargs = observed["factory"]
    assert descriptor == loader.BUDGET_BROKER_FD
    assert factory_kwargs == {
        "campaign_dir": Path("/campaign"),
        "native_budget_helper": authorization.helper,
        "pre_run_path": Path("/pre-run.json"),
        "selection_path": Path("/selection.json"),
    }
    _argv, entrypoint_kwargs = observed["entrypoint"]
    assert entrypoint_kwargs == {
        "formal_budget_backend": backend,
        "native_budget_helper": authorization.helper,
        "selected_source_fds": (
            loader.PYTHON_FD,
            loader.LOADER_FD,
            loader.AUTHORITY_FD,
            loader.NATIVE_HELPER_WRAPPER_FD,
            loader.NATIVE_HELPER_FD,
        ),
    }
    assert backend.close_count == 1
    assert backend.confinement_count == 0
    assert observed["native_closed_at_entry"] == 0
    assert observed["source_closed_at_entry"] == ()
    assert authorization.close_count == 1
    assert set(closed) == {
        loader.AUTHORITY_FD,
        loader.LOADER_FD,
        loader.PYTHON_FD,
    }
    assert loader.BUDGET_BROKER_FD not in closed


def test_organic_arm_loader_attaches_worker_then_landlocks_before_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ModuleType("_selected_organic_arm")
    backend = _Backend()
    session = _session()
    observed: dict[str, Any] = {}

    def factory(descriptor: int, **kwargs: object) -> _Backend:
        observed["factory"] = (descriptor, kwargs)
        return backend

    def entrypoint(argv: list[str], **kwargs: object) -> int:
        observed["entrypoint"] = (argv, kwargs)
        observed["native_closed_at_entry"] = authorization.close_count
        observed["source_closed_at_entry"] = tuple(closed)
        observed["confinement_at_entry"] = backend.confinement_count
        return 0

    selected.formal_arm_worker_budget_backend_from_fd = factory
    selected.main = entrypoint
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role="organic-arm",
        formal_selection=None,
        worker_session=_canonical(session),
        selected_module=selected,
    )

    assert loader.main([]) == 0
    descriptor, factory_kwargs = observed["factory"]
    assert descriptor == loader.BUDGET_BROKER_FD
    assert factory_kwargs == {
        "campaign_dir": Path("/campaign"),
        "native_budget_helper": authorization.helper,
        "pre_run_path": Path("/pre-run.json"),
        "selection_path": Path("/selection.json"),
        "worker_session": session,
    }
    _argv, entrypoint_kwargs = observed["entrypoint"]
    assert entrypoint_kwargs == {"budget_backend": backend}
    assert backend.close_count == 1
    assert backend.confinement_count == 1
    assert observed["confinement_at_entry"] == 1
    assert observed["native_closed_at_entry"] == 1
    assert set(observed["source_closed_at_entry"]) == {
        loader.AUTHORITY_FD,
        loader.LOADER_FD,
        loader.PYTHON_FD,
    }
    assert authorization.close_count == 1
    assert loader.BUDGET_BROKER_FD not in closed


@pytest.mark.parametrize(
    ("role", "worker_session", "message"),
    [
        (
            "organic-supervisor",
            _canonical(_session()),
            "supervisor received a child worker session",
        ),
        (
            "organic-arm",
            None,
            "formal worker session argument is absent",
        ),
    ],
)
def test_organic_budget_roles_reject_mixed_or_missing_worker_session(
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    worker_session: str | None,
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    selected = ModuleType(f"_selected_{role}_bad_session")
    selected.formal_arm_supervisor_budget_backend_from_fd = (
        lambda *_args, **_kwargs: _Backend()
    )
    selected.formal_arm_worker_budget_backend_from_fd = (
        lambda *_args, **_kwargs: _Backend()
    )
    selected.main = lambda *_args, **_kwargs: 0
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role=role,
        formal_selection=None,
        worker_session=worker_session,
        selected_module=selected,
    )

    assert loader.main([]) == 125
    assert message in capsys.readouterr().err
    assert closed.count(loader.BUDGET_BROKER_FD) == 1
    assert authorization.close_count == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("native_helper_wrapper_fd", 9, "fixed FDs 6 and 7"),
        ("native_helper_fd", 9, "fixed FDs 6 and 7"),
        ("budget_broker_fd", 9, "fixed FD8"),
    ],
)
def test_organic_worker_rejects_missing_or_misnumbered_selected_fd(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: int,
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    selected = ModuleType("_selected_organic_arm_fd_drift")
    selected.formal_arm_worker_budget_backend_from_fd = (
        lambda *_args, **_kwargs: _Backend()
    )
    selected.main = lambda *_args, **_kwargs: 0
    authorization, closed = _install_main_stubs(
        monkeypatch,
        role="organic-arm",
        formal_selection=None,
        worker_session=_canonical(_session()),
        selected_module=selected,
        argument_overrides={field: value},
    )

    assert loader.main([]) == 125
    assert message in capsys.readouterr().err
    assert authorization.close_count in {0, 1}
    assert len(closed) == len(set(closed))
