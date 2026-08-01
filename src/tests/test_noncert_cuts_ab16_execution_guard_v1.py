from __future__ import annotations

from contextlib import contextmanager
import fcntl
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "docs/research/noncert_cuts_ab16_20260724/organic_unit_orchestrator_v1.py"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ORCHESTRATOR = _load(MODULE_PATH, "noncert_cuts_ab16_execution_guard_v1_tested")


def test_prod_scale_lock_names_remain_compatible() -> None:
    assert ORCHESTRATOR.PROD_SCALE_LOCK_PATHS == (
        Path("/tmp/zmd-pj-codex-heavy-validation.lock"),
        Path("/run/user/1000/zmd_pj_prod_scale_solver.lock"),
        Path("/run/user/1000/zmd-pj-prod-scale-solve.lock"),
    )


def test_lock_contention_fails_closed_and_releases_partial_set(tmp_path: Path) -> None:
    first = tmp_path / "first.lock"
    blocked = tmp_path / "blocked.lock"
    blocker = os.open(blocked, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    fcntl.flock(blocker, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(ORCHESTRATOR.OrchestratorError, match="already held"):
            with ORCHESTRATOR._exclusive_prod_scale_locks((first, blocked)):  # noqa: SLF001
                raise AssertionError("contended lock set must not enter")
        with ORCHESTRATOR._exclusive_prod_scale_locks((first,)):  # noqa: SLF001
            assert first.is_file()
    finally:
        fcntl.flock(blocker, fcntl.LOCK_UN)
        os.close(blocker)


def test_formal_entry_holds_locks_for_the_complete_orchestration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"locked": False, "orchestrated": False}
    pre_run = {
        "execution_class": "FORMAL_AB16",
        "tool_identities": {"organic_unit_orchestrator": {}},
    }

    monkeypatch.setattr(
        ORCHESTRATOR,
        "snapshot_bytes",
        lambda _path: SimpleNamespace(identity={"sha256": "0" * 64}),
    )
    monkeypatch.setattr(ORCHESTRATOR, "_strict_load", lambda _snapshot, _label: pre_run)
    monkeypatch.setattr(ORCHESTRATOR, "_identity_matches", lambda *_args: None)
    monkeypatch.setattr(ORCHESTRATOR, "build_pinned_epoch_observer", lambda _pre_run: object())

    @contextmanager
    def fake_locks():
        assert state["locked"] is False
        state["locked"] = True
        try:
            yield
        finally:
            state["locked"] = False

    class FakeAdapter:
        def __init__(self, **_kwargs: object) -> None:
            assert state["locked"] is True

    def fake_orchestrate(**_kwargs: object) -> dict[str, object]:
        assert state["locked"] is True
        state["orchestrated"] = True
        return {"status": "PASS"}

    monkeypatch.setattr(ORCHESTRATOR, "_exclusive_prod_scale_locks", fake_locks)
    monkeypatch.setattr(ORCHESTRATOR, "SubprocessLifecycleAdapter", FakeAdapter)
    monkeypatch.setattr(ORCHESTRATOR, "orchestrate_with_adapter", fake_orchestrate)

    assert ORCHESTRATOR.run_pinned_entry(
        execution_class="FORMAL_AB16",
        pre_run_path=Path("pre-run.json"),
        selection_path=Path("selection.json"),
    ) == {"status": "PASS"}
    assert state == {"locked": False, "orchestrated": True}


def test_disposable_drill_does_not_take_prod_scale_locks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pre_run = {
        "execution_class": "DISPOSABLE_LIVE_DRILL",
        "tool_identities": {"organic_unit_orchestrator": {}},
    }
    monkeypatch.setattr(
        ORCHESTRATOR,
        "snapshot_bytes",
        lambda _path: SimpleNamespace(identity={"sha256": "0" * 64}),
    )
    monkeypatch.setattr(ORCHESTRATOR, "_strict_load", lambda _snapshot, _label: pre_run)
    monkeypatch.setattr(ORCHESTRATOR, "_identity_matches", lambda *_args: None)
    monkeypatch.setattr(ORCHESTRATOR, "build_pinned_epoch_observer", lambda _pre_run: object())
    monkeypatch.setattr(ORCHESTRATOR, "SubprocessLifecycleAdapter", lambda **_kwargs: object())
    monkeypatch.setattr(
        ORCHESTRATOR,
        "orchestrate_with_adapter",
        lambda **_kwargs: {"status": "PASS"},
    )

    @contextmanager
    def forbidden_locks():
        raise AssertionError("disposable drills must not claim prod-scale locks")
        yield

    monkeypatch.setattr(ORCHESTRATOR, "_exclusive_prod_scale_locks", forbidden_locks)
    assert ORCHESTRATOR.run_pinned_entry(
        execution_class="DISPOSABLE_LIVE_DRILL",
        pre_run_path=Path("pre-run.json"),
        selection_path=Path("selection.json"),
    ) == {"status": "PASS"}
