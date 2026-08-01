from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
HARNESS = RESEARCH / "ab16_resource_calibration_harness_v1.py"
PROTOCOL = RESEARCH / "ab16_resource_calibration_v1.py"


def _load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_test_ab16_resource_calibration_harness_v1",
        HARNESS,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    ).encode("utf-8")


def _write_frame(descriptor: int, value: object) -> None:
    raw = _canonical(value)
    os.write(descriptor, len(raw).to_bytes(4, "big") + raw)


def _read_exact(descriptor: int, size: int) -> bytes:
    result = b""
    while len(result) < size:
        chunk = os.read(descriptor, size - len(result))
        assert chunk
        result += chunk
    return result


def _read_frame(descriptor: int) -> dict[str, object]:
    size = int.from_bytes(_read_exact(descriptor, 4), "big")
    value = json.loads(_read_exact(descriptor, size))
    assert type(value) is dict
    return value


def _start(
    tmp_path: Path,
) -> tuple[subprocess.Popen[bytes], int, int, Path]:
    cgroup = tmp_path / "fresh-cgroup"
    cgroup.mkdir()
    (cgroup / "memory.peak").write_text("1048576\n", encoding="ascii")
    (cgroup / "memory.swap.peak").write_text("4096\n", encoding="ascii")
    disk = tmp_path / "stage-root"
    disk.mkdir()
    retained = os.open(
        disk / "retained.extent",
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        os.posix_fallocate(retained, 0, 8192)
        os.fsync(retained)
    finally:
        os.close(retained)
    control_read, control_write = os.pipe2(os.O_CLOEXEC)
    result_read, result_write = os.pipe2(os.O_CLOEXEC)
    observer_fd = os.open(HARNESS, os.O_RDONLY | os.O_CLOEXEC)
    protocol_fd = os.open(PROTOCOL, os.O_RDONLY | os.O_CLOEXEC)
    env = os.environ.copy()
    env["AB16_CALIBRATION_PROTOCOL_SHA256"] = hashlib.sha256(
        PROTOCOL.read_bytes()
    ).hexdigest()
    process = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-B",
            str(HARNESS),
            "--cgroup",
            str(cgroup),
            "--disk",
            str(disk),
            "--control-fd",
            str(control_read),
            "--result-fd",
            str(result_write),
            "--observer-fd",
            str(observer_fd),
            "--protocol-fd",
            str(protocol_fd),
            "--protocol-sha256",
            hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
            "--timeout-seconds",
            "5",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=(control_read, result_write, observer_fd, protocol_fd),
        env=env,
    )
    os.close(control_read)
    os.close(result_write)
    os.close(observer_fd)
    os.close(protocol_fd)
    return process, control_write, result_read, cgroup


def test_persistent_observer_reads_peak_before_fresh_cgroup_disappears(
    tmp_path: Path,
) -> None:
    process, control, result, cgroup = _start(tmp_path)
    try:
        _write_frame(
            control,
            {
                "action": "WORKLOAD_EXITED_REQUEST_FINAL_CAPTURE",
                "schema_version": (
                    "noncert-cuts-ab16-calibration-observer-protocol-v1"
                ),
            },
        )
        assert _read_frame(result)["action"] == "FINAL_CAPTURE_COMPLETE"
        (cgroup / "memory.peak").unlink()
        (cgroup / "memory.swap.peak").unlink()
        cgroup.rmdir()
        _write_frame(
            control,
            {
                "action": "CGROUP_REMOVAL_COMPLETE",
                "schema_version": (
                    "noncert-cuts-ab16-calibration-observer-protocol-v1"
                ),
            },
        )
        receipt = _read_frame(result)
        assert (
            receipt["status"]
            == "PEAKS_CAPTURED_BEFORE_CGROUP_DISAPPEARANCE"
        )
        assert receipt["cgroup"]["peak_read_before_disappearance"] is True
        assert receipt["cgroup"]["disappeared_after_peak_read"] is True
        assert receipt["memory_peak_bytes"] == 1048576
        assert receipt["swap_peak_bytes"] == 4096
        assert receipt["disk"]["peak_bytes"] >= 8192
        assert receipt["disk"]["growth_peak_bytes"] == 0
        assert process.wait(timeout=5) == 0
    finally:
        os.close(control)
        os.close(result)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_observer_fails_closed_if_cgroup_disappears_before_final_read(
    tmp_path: Path,
) -> None:
    process, control, result, cgroup = _start(tmp_path)
    try:
        (cgroup / "memory.peak").unlink()
        (cgroup / "memory.swap.peak").unlink()
        cgroup.rmdir()
        _write_frame(
            control,
            {
                "action": "WORKLOAD_EXITED_REQUEST_FINAL_CAPTURE",
                "schema_version": (
                    "noncert-cuts-ab16-calibration-observer-protocol-v1"
                ),
            },
        )
        receipt = _read_frame(result)
        assert receipt["status"] == "FAIL_CLOSED"
        assert receipt["conclusion"] is None
        assert process.wait(timeout=5) == 2
    finally:
        os.close(control)
        os.close(result)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_disk_measurement_is_exact_stage_tree_not_whole_filesystem(
    tmp_path: Path,
) -> None:
    module = _load_harness()
    stage = tmp_path / "stage"
    stage.mkdir()
    empty_allocated = module._disk_used(stage)  # noqa: SLF001
    extent = os.open(
        stage / "extent.bin",
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        os.posix_fallocate(extent, 0, 1024 * 1024)
        os.fsync(extent)
    finally:
        os.close(extent)
    allocated = module._disk_used(stage)  # noqa: SLF001
    assert allocated - empty_allocated >= 1024 * 1024


@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_disk_measurement_rejects_nonclosed_tree_nodes(
    tmp_path: Path,
    kind: str,
) -> None:
    module = _load_harness()
    stage = tmp_path / "stage"
    stage.mkdir()
    if kind == "symlink":
        (stage / "unknown").symlink_to("/dev/null")
    else:
        os.mkfifo(stage / "unknown", 0o600)
    with pytest.raises(
        module.CalibrationObserverError,
        match="CALIBRATION_PATH_UNTRUSTED",
    ):
        module._disk_used(stage)  # noqa: SLF001


def test_disk_measurement_rejects_hardlinked_allocation(
    tmp_path: Path,
) -> None:
    module = _load_harness()
    stage = tmp_path / "stage"
    stage.mkdir()
    first = stage / "first.bin"
    first.write_bytes(b"retained")
    os.link(first, stage / "second.bin")
    with pytest.raises(
        module.CalibrationObserverError,
        match="CALIBRATION_DISK_HARDLINK_REJECTED",
    ):
        module._disk_used(stage)  # noqa: SLF001
