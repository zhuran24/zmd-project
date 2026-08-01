from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Mapping

import pytest

from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_controller_v1 as controller,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    organic_unit_orchestrator_v2 as organic_orchestrator,
)


def _fd_count() -> int:
    return len(
        [
            name
            for name in os.listdir("/proc/self/fd")
            if name.isdecimal()
            and Path(f"/proc/self/fd/{name}").exists()
        ]
    )


def _factory_fault_probe(
    factory_name: str,
    *,
    cleanup_close_failure: bool,
) -> dict[str, object]:
    result_read, initial_result_write = os.pipe2(os.O_CLOEXEC)
    result_write = fcntl.fcntl(
        initial_result_write,
        fcntl.F_DUPFD_CLOEXEC,
        100,
    )
    os.close(initial_result_write)
    pid = os.fork()
    if pid == 0:
        os.close(result_read)
        real_close = os.close
        real_fcntl = fcntl.fcntl
        try:
            try:
                real_close(8)
            except OSError:
                pass
            baseline = _fd_count()
            source = os.open(
                "/dev/null",
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            if source != 8:
                os.dup2(source, 8, inheritable=False)
                real_close(source)

            duplicated: list[int] = []
            close_counts: dict[int, int] = {}

            def observed_fcntl(
                descriptor: int,
                command: int,
                argument: int = 0,
            ) -> int:
                result = real_fcntl(descriptor, command, argument)
                if (
                    descriptor == 8
                    and command == fcntl.F_DUPFD_CLOEXEC
                ):
                    duplicated.append(result)
                return result

            def observed_close(descriptor: int) -> None:
                if descriptor == 8 or descriptor in duplicated:
                    close_counts[descriptor] = (
                        close_counts.get(descriptor, 0) + 1
                    )
                real_close(descriptor)
                if (
                    cleanup_close_failure
                    and descriptor in duplicated
                ):
                    raise OSError("injected cleanup close failure")

            def fail_after_fd_transfer(*_args: object, **_kwargs: object) -> None:
                raise RuntimeError("injected post-open validation failure")

            old_fcntl = controller.fcntl.fcntl
            old_close = controller.os.close
            old_load = controller.load_formal_inputs
            controller.fcntl.fcntl = observed_fcntl
            controller.os.close = observed_close
            controller.load_formal_inputs = fail_after_fd_transfer
            observed_exception: BaseException | None = None
            try:
                factory: Callable[..., object] = getattr(
                    controller,
                    factory_name,
                )
                if factory_name == "formal_budget_backend_from_fd":
                    factory(
                        8,
                        native_budget_helper=object(),
                        campaign_dir=Path("/not-read"),
                        formal_selection=Path("/not-read/selection.json"),
                    )
                else:
                    factory(
                        8,
                        native_budget_helper=object(),
                        campaign_dir=Path("/not-read"),
                        formal_selection=Path("/not-read/selection.json"),
                        worker_role="baseline-admission",
                        worker_session={
                            "broker_grant": {},
                            "credential": "a" * 64,
                            "schema_version": (
                                controller.FORMAL_WORKER_SESSION_SCHEMA
                            ),
                        },
                    )
            except BaseException as exc:
                observed_exception = exc
            finally:
                controller.fcntl.fcntl = old_fcntl
                controller.os.close = old_close
                controller.load_formal_inputs = old_load

            payload = {
                "close_counts": {
                    str(descriptor): count
                    for descriptor, count in close_counts.items()
                },
                "duplicate": duplicated,
                "exception_message": (
                    None
                    if observed_exception is None
                    else str(observed_exception)
                ),
                "exception_notes": (
                    []
                    if observed_exception is None
                    else list(
                        getattr(observed_exception, "__notes__", ())
                    )
                ),
                "exception_type": (
                    None
                    if observed_exception is None
                    else type(observed_exception).__name__
                ),
                "fd_delta": _fd_count() - baseline,
            }
            os.write(
                result_write,
                json.dumps(payload, sort_keys=True).encode(),
            )
            exit_code = 0
        except BaseException as exc:
            os.write(
                result_write,
                json.dumps(
                    {
                        "probe_error": (
                            f"{type(exc).__name__}: {exc}"
                        )
                    },
                    sort_keys=True,
                ).encode(),
            )
            exit_code = 2
        finally:
            real_close(result_write)
        os._exit(exit_code)

    os.close(result_write)
    raw = bytearray()
    while True:
        block = os.read(result_read, 65536)
        if not block:
            break
        raw.extend(block)
    os.close(result_read)
    observed_pid, status = os.waitpid(pid, 0)
    assert observed_pid == pid
    assert os.waitstatus_to_exitcode(status) == 0, raw.decode(
        "utf-8",
        "replace",
    )
    result = json.loads(raw)
    assert "probe_error" not in result
    return result


@pytest.mark.parametrize(
    "factory_name",
    [
        "formal_budget_backend_from_fd",
        "formal_worker_budget_backend_from_fd",
    ],
)
@pytest.mark.parametrize("cleanup_close_failure", [False, True])
def test_budget_backend_factories_transfer_fd8_exactly_once_on_fault(
    factory_name: str,
    cleanup_close_failure: bool,
) -> None:
    result = _factory_fault_probe(
        factory_name,
        cleanup_close_failure=cleanup_close_failure,
    )
    assert result["exception_type"] == "RuntimeError"
    assert result["exception_message"] == (
        "injected post-open validation failure"
    )
    duplicate = result["duplicate"]
    assert isinstance(duplicate, list) and len(duplicate) == 1
    assert result["close_counts"] == {
        "8": 1,
        str(duplicate[0]): 1,
    }
    assert result["fd_delta"] == 0
    notes = result["exception_notes"]
    if cleanup_close_failure:
        prefix = (
            "formal worker factory"
            if "worker" in factory_name
            else "formal broker factory"
        )
        assert notes == [
            (
                f"{prefix} cleanup failed: OSError: "
                "injected cleanup close failure"
            )
        ]
    else:
        assert notes == []


def _identity(path: Path, marker: str) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": marker * 64,
        "size_bytes": 17,
    }


def test_live_formal_adapter_binds_observed_supervisor_pidfd_before_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, object]] = []
    current_pid = os.getpid()
    current_starttime = organic_orchestrator._proc_starttime(  # noqa: SLF001
        current_pid
    )
    assert current_starttime is not None

    class Backend:
        @staticmethod
        def open_manager_openfile_pidfd(
            pid: int,
        ) -> tuple[int, str]:
            assert pid == current_pid
            return (
                os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC),
                "test-pidfd-opener",
            )

        @staticmethod
        def bind_manager_openfile_arm_grant(
            *,
            application_peer: Mapping[str, object],
            pidfd: int,
            pidfd_method: str,
        ) -> Mapping[str, object]:
            events.append(("bind", dict(application_peer)))
            assert os.fstat(pidfd)
            assert pidfd_method == "test-pidfd-opener"
            return {
                "application_peer": dict(application_peer),
                "state": "BOUND",
            }

    adapter = object.__new__(
        organic_orchestrator.SubprocessLifecycleAdapter
    )
    adapter.pre_run = {
        "schema_version": organic_orchestrator.FORMAL_PRE_RUN_SCHEMA
    }
    adapter.formal_budget_backend = Backend()
    adapter._monotonic = lambda: 0.0
    adapter.sleep = lambda _seconds: None
    adapter._show = lambda *_args, **_kwargs: {
        "ActiveState": "activating",
        "InvocationID": "1" * 32,
        "MainPID": str(current_pid),
        "SubState": "start",
    }
    adapter._bind_formal_arm_supervisor(  # noqa: SLF001
        unit_name="ab16-organic-fixture.service"
    )
    assert events == [
        (
            "bind",
            {
                "pid": current_pid,
                "pid_starttime": current_starttime,
                "uid": os.getuid(),
            },
        )
    ]


def test_live_formal_adapter_stops_when_supervisor_bind_is_uncertain() -> None:
    class Backend:
        @staticmethod
        def open_manager_openfile_pidfd(
            _pid: int,
        ) -> tuple[int, str]:
            return (
                os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC),
                "test-pidfd-opener",
            )

        @staticmethod
        def bind_manager_openfile_arm_grant(
            **_kwargs: object,
        ) -> Mapping[str, object]:
            raise RuntimeError("injected uncertain bind")

    adapter = object.__new__(
        organic_orchestrator.SubprocessLifecycleAdapter
    )
    adapter.pre_run = {
        "schema_version": organic_orchestrator.FORMAL_PRE_RUN_SCHEMA
    }
    adapter.formal_budget_backend = Backend()
    adapter._monotonic = lambda: 0.0
    adapter.sleep = lambda _seconds: None
    adapter._show = lambda *_args, **_kwargs: {
        "ActiveState": "activating",
        "InvocationID": "2" * 32,
        "MainPID": str(os.getpid()),
        "SubState": "start",
    }

    with pytest.raises(
        organic_orchestrator.OrchestratorError,
        match="binding failed or is uncertain",
    ):
        adapter._bind_formal_arm_supervisor(  # noqa: SLF001
            unit_name="ab16-organic-fixture.service"
        )


def test_controller_closes_arm_in_exact_post_selection_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    slot = controller.ARM_SEQUENCE[0]
    formal_root = tmp_path / "formal"
    attempt_prefix = f"prospective/arms/{slot}"
    manifest_identity = _identity(
        formal_root / attempt_prefix / "attempt-artifact-manifest.json",
        "1",
    )
    terminal_identity = _identity(
        formal_root / "budget/arm-terminals" / f"{slot}.json",
        "2",
    )
    accepted_identity = _identity(
        formal_root / "channels/budget-journal/segment-00000003.bin",
        "3",
    )
    replay_identity = _identity(
        formal_root / "replays/arm-attempt-roots" / f"{slot}.json",
        "4",
    )
    response_authentication = {
        "nonce": "5" * 64,
        "response_sequence": 2,
        "response_sha256": "6" * 64,
    }
    bindings = {"arm_allocation_identity": {"sha256": "7" * 64, "size_bytes": 9}}
    prepared = {
        "arm_attempt_prefix": attempt_prefix,
        "closure_bindings": bindings,
        "evidence": {},
        "formal_root": str(formal_root),
        "pre_run_authority_identity": _identity(tmp_path / "pre-run.json", "8"),
        "selection_identity": _identity(tmp_path / "selection.json", "9"),
        "slot": slot,
        "state": "PREPARED_NOT_CONSUMED",
        "suite_terminal_identity": None,
    }
    terminal = {
        "arm_expected_path_types": [
            {"path": attempt_prefix, "type": "directory"},
        ]
    }

    class Backend:
        @staticmethod
        def expected_root_path_types() -> list[dict[str, str]]:
            events.append("inventory")
            return [{"path": attempt_prefix, "type": "directory"}]

        @staticmethod
        def accept_prior_arm_seal_response(
            *,
            continuation: str,
            successor_arm_slot: str | None,
        ) -> Mapping[str, object]:
            events.append("accept")
            assert continuation == "next-arm"
            assert successor_arm_slot == controller.ARM_SEQUENCE[1]
            return {
                "accepted": {"state": "PRIOR_RESPONSE_ACCEPTED"},
                "journal": accepted_identity,
            }

    backend = Backend()

    def publish_manifest(*_args: object, **kwargs: object) -> dict[str, object]:
        events.append("seal")
        assert kwargs["bindings"] == bindings
        return {
            "arm_budget_terminal": terminal,
            "arm_budget_terminal_identity": terminal_identity,
            "arm_seal_response_authentication": response_authentication,
            "manifest_identity": manifest_identity,
        }

    def publish_replay(*_args: object, **kwargs: object) -> dict[str, object]:
        events.append("replay")
        assert kwargs["prior_response_accepted_identity"] == accepted_identity
        return {"replay_identity": replay_identity}

    closure = SimpleNamespace(
        publish_arm_attempt_manifest=publish_manifest,
        replay_and_publish_arm_attempt_root=publish_replay,
        verify_published_arm_attempt_replay=lambda *_args, **_kwargs: (
            events.append("verify")
        ),
    )
    monkeypatch.setattr(
        controller,
        "_import_snapshot_owner",
        lambda *_args, **_kwargs: closure,
    )

    expected_result = {"status": "PASS", "consumption": {}}

    def consume(
        *_args: object,
        **kwargs: object,
    ) -> dict[str, object]:
        events.append("consume")
        assert kwargs["prepared"] == prepared
        assert kwargs["arm_closure"] == {
            "arm_attempt_manifest_identity": manifest_identity,
            "arm_attempt_replay_identity": replay_identity,
            "arm_budget_terminal_identity": terminal_identity,
            "prior_response_accepted_identity": accepted_identity,
            "seal_response_authentication": response_authentication,
        }
        return expected_result

    monkeypatch.setattr(
        controller.authority,
        "consume_prepared_arm",
        consume,
    )
    inputs = controller.FormalInputs(
        context={"campaign_dir": str(tmp_path)},
        guardian_process_identity={"pid": 1, "starttime": 2},
        supervisor_process_identity={"pid": 3, "starttime": 4},
        selection={},
        selection_identity=_identity(tmp_path / "formal-selection.json", "a"),
    )
    assert (
        controller._close_and_consume_prepared_arm(  # noqa: SLF001
            inputs,
            slot=slot,
            ordinal=1,
            prepared=prepared,
            arm_budget_backend=backend,
        )
        is expected_result
    )
    assert events == [
        "inventory",
        "seal",
        "accept",
        "replay",
        "verify",
        "consume",
    ]


def test_controller_stops_before_consumption_when_outside_replay_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    slot = controller.ARM_SEQUENCE[-1]
    formal_root = tmp_path / "formal"
    attempt_prefix = f"prospective/arms/{slot}"
    prepared = {
        "arm_attempt_prefix": attempt_prefix,
        "closure_bindings": {"arm_allocation_identity": {"sha256": "1" * 64, "size_bytes": 9}},
        "evidence": {},
        "formal_root": str(formal_root),
        "pre_run_authority_identity": _identity(tmp_path / "pre-run.json", "2"),
        "selection_identity": _identity(tmp_path / "selection.json", "3"),
        "slot": slot,
        "state": "PREPARED_NOT_CONSUMED",
        "suite_terminal_identity": _identity(tmp_path / "suite.json", "4"),
    }

    class Backend:
        @staticmethod
        def expected_root_path_types() -> list[dict[str, str]]:
            return [{"path": attempt_prefix, "type": "directory"}]

        @staticmethod
        def accept_prior_arm_seal_response(
            *,
            continuation: str,
            successor_arm_slot: str | None,
        ) -> Mapping[str, object]:
            events.append("accept")
            assert continuation == "formal-finalize"
            assert successor_arm_slot is None
            return {
                "accepted": {"state": "PRIOR_RESPONSE_ACCEPTED"},
                "journal": _identity(tmp_path / "accepted.json", "5"),
            }

    closure = SimpleNamespace(
        publish_arm_attempt_manifest=lambda *_args, **_kwargs: {
            "arm_budget_terminal": {
                "arm_expected_path_types": [
                    {"path": attempt_prefix, "type": "directory"},
                ]
            },
            "arm_budget_terminal_identity": _identity(
                tmp_path / "terminal.json",
                "6",
            ),
            "arm_seal_response_authentication": {
                "nonce": "7" * 64,
                "response_sequence": 2,
                "response_sha256": "8" * 64,
            },
            "manifest_identity": _identity(tmp_path / "manifest.json", "9"),
        },
        replay_and_publish_arm_attempt_root=lambda *_args, **_kwargs: (
            (_ for _ in ()).throw(RuntimeError("injected replay failure"))
        ),
    )
    monkeypatch.setattr(
        controller,
        "_import_snapshot_owner",
        lambda *_args, **_kwargs: closure,
    )
    monkeypatch.setattr(
        controller.authority,
        "consume_prepared_arm",
        lambda *_args, **_kwargs: events.append("consume"),
    )
    inputs = controller.FormalInputs(
        context={"campaign_dir": str(tmp_path)},
        guardian_process_identity={"pid": 1, "starttime": 2},
        supervisor_process_identity={"pid": 3, "starttime": 4},
        selection={},
        selection_identity=_identity(tmp_path / "formal-selection.json", "a"),
    )
    with pytest.raises(
        controller.FormalControllerError,
        match="outside replay failed or is uncertain",
    ):
        controller._close_and_consume_prepared_arm(  # noqa: SLF001
            inputs,
            slot=slot,
            ordinal=len(controller.ARM_SEQUENCE),
            prepared=prepared,
            arm_budget_backend=Backend(),
        )
    assert events == ["accept"]
