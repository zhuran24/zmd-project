from __future__ import annotations

import fcntl
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"


def _load_helper() -> ModuleType:
    path = RESEARCH / "ab16_outer_refunit_closeout_v1.py"
    spec = importlib.util.spec_from_file_location(
        "_test_ab16_lock_release_ownership",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(RESEARCH))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(RESEARCH))
    return module


HELPER = _load_helper()


@pytest.mark.parametrize("failed_index", (0, 1, 2))
def test_three_lock_close_failure_never_claims_release_or_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_index: int,
) -> None:
    lock_paths = tuple(
        str((tmp_path / f"formal-{index}.lock").absolute())
        for index in range(3)
    )
    descriptors: dict[str, int] = {}
    for path in lock_paths:
        descriptor = os.open(
            path,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        descriptors[path] = descriptor
    monkeypatch.setattr(HELPER, "LOCK_PATHS", lock_paths)
    host = HELPER.PinnedHost(SimpleNamespace(), descriptors)
    failed_path = lock_paths[failed_index]
    failed_descriptor = descriptors[failed_path]
    close_counts = {descriptor: 0 for descriptor in descriptors.values()}
    real_close = os.close

    def close_with_one_uncertain_result(descriptor: int) -> None:
        if descriptor in close_counts:
            close_counts[descriptor] += 1
        if descriptor == failed_descriptor:
            raise RuntimeError("deterministic lock close failure")
        real_close(descriptor)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(HELPER.os, "close", close_with_one_uncertain_result)
            with pytest.raises(
                HELPER.OuterCloseoutError,
                match="three-lock release failed or is uncertain",
            ):
                host.release_locks_once()
            first_counts = dict(close_counts)
            with pytest.raises(
                HELPER.OuterCloseoutError,
                match="three-lock release was already attempted",
            ):
                host.release_locks_once()
            assert close_counts == first_counts
    finally:
        for descriptor in descriptors.values():
            try:
                real_close(descriptor)
            except OSError:
                pass

    assert close_counts == {descriptor: 1 for descriptor in descriptors.values()}
    assert host.lock_release_attempted is True
    assert host.lock_release_uncertain is True
    assert host.locks_released is False
    assert host.held_locks == {failed_path: failed_descriptor}
    with pytest.raises(
        HELPER.OuterCloseoutError,
        match="exact three-lock lease is not held",
    ):
        host.lock_evidence()
