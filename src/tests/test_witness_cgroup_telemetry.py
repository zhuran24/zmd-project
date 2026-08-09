"""Focused worker-side cgroup-v2 contract and telemetry tests."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest


TELEMETRY = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.cgroup_telemetry"
)
SUPERVISOR = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.run_supervisor"
)

UNIT_NAME = "zmd-witness-test.service"
EVENT_KEYS = ("low", "high", "max", "oom", "oom_kill", "oom_group_kill")


def _write(path: Path, value: int | str) -> None:
    path.write_text(f"{value}\n", encoding="ascii")


def _write_limits(
    path: Path,
    *,
    memory_high: int | str = "max",
    memory_max: int | str = "max",
    memory_swap_max: int | str = "max",
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _write(path / "memory.high", memory_high)
    _write(path / "memory.max", memory_max)
    _write(path / "memory.swap.max", memory_swap_max)


def _write_events(path: Path, **updates: int) -> None:
    values = dict.fromkeys(EVENT_KEYS, 0)
    values.update(updates)
    path.write_text("".join(f"{key} {values[key]}\n" for key in EVENT_KEYS), encoding="ascii")


def _build_tree(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "cgroup"
    user_slice = root / "user.slice"
    app_slice = user_slice / "user-1000.slice" / "user@1000.service" / "app.slice"
    leaf = app_slice / UNIT_NAME
    for path in (root, user_slice, user_slice / "user-1000.slice", app_slice.parent, app_slice):
        _write_limits(path)
    _write_limits(
        leaf,
        memory_high=SUPERVISOR.MEMORY_HIGH_BYTES,
        memory_max=SUPERVISOR.MEMORY_MAX_BYTES,
        memory_swap_max=SUPERVISOR.MEMORY_SWAP_MAX_BYTES,
    )
    counters = {
        "memory.current": 100,
        "memory.peak": 200,
        "memory.swap.current": 3,
        "memory.swap.peak": 4,
        "pids.current": 5,
    }
    for filename, value in counters.items():
        _write(leaf / filename, value)
    _write_events(leaf / "memory.events")
    proc = tmp_path / "proc-self-cgroup"
    relative = "/" + leaf.relative_to(root).as_posix()
    proc.write_text(f"0::{relative}\n", encoding="utf-8")
    return {"root": root, "leaf": leaf, "proc": proc, "relative": relative}


def _begin(tree: dict[str, Any]):
    return TELEMETRY.begin_worker_cgroup_telemetry(
        expected_unit_name=UNIT_NAME,
        proc_self_cgroup=tree["proc"],
        cgroup_root=tree["root"],
    )


def test_compliant_leaf_and_unlimited_ancestors_are_recorded(tmp_path: Path) -> None:
    tree = _build_tree(tmp_path)
    start = _begin(tree)

    assert start.relative_path == tree["relative"]
    assert start.contract.leaf.as_dict() == {
        "path": tree["relative"],
        "memory.high": SUPERVISOR.MEMORY_HIGH_BYTES,
        "memory.max": SUPERVISOR.MEMORY_MAX_BYTES,
        "memory.swap.max": SUPERVISOR.MEMORY_SWAP_MAX_BYTES,
    }
    assert [record.relative_path for record in start.contract.ancestors] == [
        "/user.slice/user-1000.slice/user@1000.service/app.slice",
        "/user.slice/user-1000.slice/user@1000.service",
        "/user.slice/user-1000.slice",
        "/user.slice",
        "/",
    ]
    assert all(record.memory_max == "max" for record in start.contract.ancestors)
    assert start.counters.as_dict()["memory.current"] == 100

    _write(tree["leaf"] / "memory.current", 150)
    _write(tree["leaf"] / "memory.peak", 250)
    _write(tree["leaf"] / "memory.swap.current", 2)
    _write(tree["leaf"] / "memory.swap.peak", 6)
    _write(tree["leaf"] / "pids.current", 4)
    _write_events(tree["leaf"] / "memory.events", high=2, max=1)
    record = TELEMETRY.finish_worker_cgroup_telemetry(start)

    assert record.events_delta["high"] == 2
    assert record.events_delta["max"] == 1
    assert record.oom_attribution == TELEMETRY.NO_CGROUP_OOM
    payload = record.as_dict()
    assert payload["schema_version"] == TELEMETRY.TELEMETRY_SCHEMA_VERSION
    assert payload["counters_end"]["memory.peak"] == 250
    assert payload["contract_end"]["effective"] == {
        "memory.high": SUPERVISOR.MEMORY_HIGH_BYTES,
        "memory.max": SUPERVISOR.MEMORY_MAX_BYTES,
        "memory.swap.max": SUPERVISOR.MEMORY_SWAP_MAX_BYTES,
    }


def test_root_control_files_may_be_implicit_max_but_nonroot_files_may_not_be_missing(tmp_path: Path) -> None:
    tree = _build_tree(tmp_path)
    for filename in ("memory.high", "memory.max", "memory.swap.max"):
        (tree["root"] / filename).unlink()

    start = _begin(tree)
    assert start.contract.ancestors[-1].as_dict() == {
        "path": "/",
        "memory.high": "max",
        "memory.max": "max",
        "memory.swap.max": "max",
    }

    (tree["root"] / "user.slice" / "memory.high").unlink()
    with pytest.raises(TELEMETRY.CgroupTelemetryError) as raised:
        _begin(tree)
    assert raised.value.code == "CGROUP_FILE_MISSING"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("memory.high", SUPERVISOR.MEMORY_HIGH_BYTES),
        ("memory.max", SUPERVISOR.MEMORY_MAX_BYTES),
        ("memory.swap.max", SUPERVISOR.MEMORY_SWAP_MAX_BYTES),
    ],
)
def test_any_stricter_ancestor_limit_is_rejected(tmp_path: Path, filename: str, expected: int) -> None:
    tree = _build_tree(tmp_path)
    _write(tree["root"] / "user.slice" / filename, expected - 1)

    with pytest.raises(TELEMETRY.CgroupTelemetryError) as raised:
        _begin(tree)
    assert raised.value.code == "ANCESTOR_LIMIT_STRICTER"
    assert filename in str(raised.value)


@pytest.mark.parametrize(
    ("filename", "mode", "value", "code"),
    [
        ("memory.high", "missing", None, "CGROUP_FILE_MISSING"),
        ("memory.max", "replace", "garbage", "CGROUP_VALUE_INVALID"),
        ("memory.swap.max", "replace", "max", "LEAF_LIMIT_UNBOUNDED"),
    ],
)
def test_missing_unparseable_and_unbounded_leaf_limits_fail_closed(
    tmp_path: Path,
    filename: str,
    mode: str,
    value: str | None,
    code: str,
) -> None:
    tree = _build_tree(tmp_path)
    target = tree["leaf"] / filename
    if mode == "missing":
        target.unlink()
    else:
        assert value is not None
        _write(target, value)

    with pytest.raises(TELEMETRY.CgroupTelemetryError) as raised:
        _begin(tree)
    assert raised.value.code == code


@pytest.mark.parametrize(
    ("updates", "attribution"),
    [
        ({"oom": 1}, SUPERVISOR.CGROUP_OOM_EVENT),
        ({"oom": 2, "oom_kill": 1}, SUPERVISOR.CGROUP_OOM_KILL),
        ({"oom": 2, "oom_group_kill": 1}, SUPERVISOR.CGROUP_OOM_KILL),
    ],
)
def test_oom_events_are_attributed_from_attempt_delta(
    tmp_path: Path,
    updates: dict[str, int],
    attribution: str,
) -> None:
    tree = _build_tree(tmp_path)
    _write_events(tree["leaf"] / "memory.events", oom=7, oom_kill=3, oom_group_kill=2)
    start = _begin(tree)
    after = {"oom": 7, "oom_kill": 3, "oom_group_kill": 2}
    for key, increment in updates.items():
        after[key] += increment
    _write_events(tree["leaf"] / "memory.events", **after)

    record = TELEMETRY.finish_worker_cgroup_telemetry(start)
    assert record.oom_attribution == attribution
    for key, expected in updates.items():
        assert record.events_delta[key] == expected


def test_end_snapshot_revalidates_contract_and_event_monotonicity(tmp_path: Path) -> None:
    tree = _build_tree(tmp_path)
    _write_events(tree["leaf"] / "memory.events", oom=3)
    start = _begin(tree)
    _write(tree["root"] / "user.slice" / "memory.max", SUPERVISOR.MEMORY_MAX_BYTES - 1)
    with pytest.raises(TELEMETRY.CgroupTelemetryError) as raised:
        TELEMETRY.finish_worker_cgroup_telemetry(start)
    assert raised.value.code == "ANCESTOR_LIMIT_STRICTER"

    _write(tree["root"] / "user.slice" / "memory.max", "max")
    _write_events(tree["leaf"] / "memory.events", oom=2)
    with pytest.raises(TELEMETRY.CgroupTelemetryError) as raised:
        TELEMETRY.finish_worker_cgroup_telemetry(start)
    assert raised.value.code == "MEMORY_EVENTS_DELTA_INVALID"


def test_proc_path_and_expected_unit_are_fail_closed(tmp_path: Path) -> None:
    tree = _build_tree(tmp_path)
    tree["proc"].write_text("0::/user.slice/../escape.service\n", encoding="utf-8")
    with pytest.raises(TELEMETRY.CgroupTelemetryError) as raised:
        _begin(tree)
    assert raised.value.code == "PROC_CGROUP_PATH_INVALID"

    tree = _build_tree(tmp_path / "second")
    with pytest.raises(TELEMETRY.CgroupTelemetryError) as raised:
        TELEMETRY.begin_worker_cgroup_telemetry(
            expected_unit_name="zmd-witness-other.service",
            proc_self_cgroup=tree["proc"],
            cgroup_root=tree["root"],
        )
    assert raised.value.code == "UNIT_MISMATCH"
