#!/usr/bin/env python3
"""Second, independently structured stdlib replay for AB16 calibration."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import NoReturn, cast


AUTHORITY = "AB16_RESEARCH_ONLY"
ROOT_SCHEMA = "noncert-cuts-ab16-resource-calibration-root-receipt-v1"
REPLAY_SCHEMA = "noncert-cuts-ab16-resource-calibration-outside-replay-v1"
EXECUTION_SURFACE_SCHEMA = "noncert-cuts-ab16-resource-execution-surface-v3"
CALIBRATION_PACKAGE_SCHEMA = "noncert-cuts-ab16-resource-calibration-package-v2"
PORTABLE_PACKAGE_LAYOUT = "PORTABLE_CANDIDATE_V1"
NO_AUTHORITY = {
    "formal_campaign_creation_authorized": False,
    "gate_b_approval_authorized": False,
    "organic_arm_launch_authorized": False,
    "profile_installation_authorized": False,
    "solver_run_authorized": False,
}
PATHS = {
    "aggregate": "aggregate.json",
    "declaration": "declaration.json",
    "installed_profile": "installed-profile.json",
    "profile_candidate": "profile-candidate.json",
    "observer_result_1": "observer-results/01.json",
    "observer_result_2": "observer-results/02.json",
    "observer_result_3": "observer-results/03.json",
    "sample_1": "samples/01.json",
    "sample_2": "samples/02.json",
    "sample_3": "samples/03.json",
    "validation_1": "validations/01.json",
    "validation_2": "validations/02.json",
    "validation_3": "validations/03.json",
}


class AltReplayError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _die(code: str, detail: str) -> NoReturn:
    raise AltReplayError(code, detail)


def _encode(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _object_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            _die("ALT_JSON_REJECTED", f"duplicate key {key!r}")
        result[key] = value
    return result


def _json(raw: bytes, name: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_constant=lambda token: _die(
                "ALT_JSON_REJECTED",
                f"{name}: {token}",
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        _die("ALT_JSON_REJECTED", f"{name}: {exc}")
    if type(value) is not dict or _encode(value) != raw:
        _die("ALT_JSON_REJECTED", f"{name}: not canonical")
    return cast(dict[str, object], value)


def _open_dir(absolute: Path) -> int:
    if absolute != absolute.absolute():
        _die("ALT_ROOT_REJECTED", "path is not absolute")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    opened = [os.open("/", flags)]
    primary: BaseException | None = None
    try:
        for part in absolute.parts[1:]:
            opened.append(
                os.open(part, flags, dir_fd=opened[-1])
            )
    except BaseException as exc:
        primary = exc
    result = opened[-1] if primary is None else -1
    for descriptor in reversed(opened[:-1] if primary is None else opened):
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "alternate replay directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        if result >= 0:
            try:
                os.close(result)
            except BaseException as close_error:
                primary.add_note(
                    "alternate replay retained-root cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise primary
    return result


def _sig(item: os.stat_result) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_uid,
        item.st_gid,
        item.st_size,
        item.st_blocks,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )


def _slurp(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        item = os.read(descriptor, 131072)
        if not item:
            return b"".join(chunks)
        chunks.append(item)


def _snapshot(root: Path) -> tuple[dict[str, bytes], dict[str, str], os.stat_result]:
    anchor = _open_dir(root)
    anchor_stat = os.fstat(anchor)
    retained: list[tuple[int, str, tuple[int, ...], tuple[str, ...]]] = []
    files: dict[str, bytes] = {}
    kinds: dict[str, str] = {}
    inodes: set[tuple[int, int]] = set()
    primary: BaseException | None = None
    try:
        for current, directories, filenames, transient_fd in os.fwalk(
            ".",
            topdown=True,
            follow_symlinks=False,
            dir_fd=anchor,
        ):
            relative_dir = os.path.relpath(current, ".")
            relative_dir = "" if relative_dir == "." else relative_dir
            retained_fd = os.dup(transient_fd)
            observed_names = tuple(
                sorted((*directories, *filenames), key=os.fsencode)
            )
            retained.append(
                (
                    retained_fd,
                    relative_dir,
                    _sig(os.fstat(retained_fd)),
                    observed_names,
                )
            )
            for directory in directories:
                relative = (
                    f"{relative_dir}/{directory}"
                    if relative_dir
                    else directory
                )
                node = os.stat(
                    directory,
                    dir_fd=retained_fd,
                    follow_symlinks=False,
                )
                if not stat.S_ISDIR(node.st_mode) or stat.S_ISLNK(node.st_mode):
                    _die("ALT_ROOT_REJECTED", relative)
                kinds[relative] = "directory"
            for filename in filenames:
                relative = (
                    f"{relative_dir}/{filename}"
                    if relative_dir
                    else filename
                )
                before = os.stat(
                    filename,
                    dir_fd=retained_fd,
                    follow_symlinks=False,
                )
                if not stat.S_ISREG(before.st_mode):
                    _die("ALT_ROOT_SPECIAL_NODE", relative)
                if before.st_nlink != 1 or (before.st_dev, before.st_ino) in inodes:
                    _die("ALT_ROOT_HARDLINK", relative)
                inodes.add((before.st_dev, before.st_ino))
                opened = os.open(
                    filename,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=retained_fd,
                )
                try:
                    if _sig(os.fstat(opened)) != _sig(before):
                        _die("ALT_ROOT_CHANGED", relative)
                    raw = _slurp(opened)
                    if _sig(os.fstat(opened)) != _sig(before):
                        _die("ALT_ROOT_CHANGED", relative)
                finally:
                    os.close(opened)
                files[relative] = raw
                kinds[relative] = "regular_file"
        for descriptor, relative, signature, names in retained:
            if (
                _sig(os.fstat(descriptor)) != signature
                or tuple(
                    sorted(os.listdir(descriptor), key=os.fsencode)
                )
                != names
            ):
                _die("ALT_ROOT_CHANGED", relative or ".")
        rejoined = _open_dir(root)
        try:
            if _sig(os.fstat(rejoined)) != _sig(anchor_stat):
                _die("ALT_ROOT_CHANGED", "final absolute join")
        finally:
            os.close(rejoined)
        return files, kinds, anchor_stat
    except BaseException as exc:
        primary = exc
        raise
    finally:
        for descriptor, _relative, _signature, _names in reversed(retained):
            try:
                os.close(descriptor)
            except BaseException as close_error:
                if primary is None:
                    raise
                primary.add_note(f"alt replay close failed: {close_error}")
        os.close(anchor)


def _file_identity(root: Path, name: str, raw: bytes) -> dict[str, object]:
    return {
        "path": str((root / name).absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _boundary(
    record: dict[str, object],
    *,
    schema: str,
    status: str,
    label: str,
) -> None:
    if (
        record.get("authority_scope") != AUTHORITY
        or record.get("authorizations") != NO_AUTHORITY
        or record.get("schema_version") != schema
        or record.get("status") != status
    ):
        _die("ALT_CHAIN_REJECTED", f"{label} boundary")


def _number(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        _die("ALT_CHAIN_REJECTED", label)
    return value


def _surface_digest(
    value: object,
    *,
    stage: object,
    profile_identity: Mapping[str, object],
) -> str:
    expected = {
        "command",
        "control_plane_identities",
        "execution_member_identities",
        "portable_package",
        "execution_site_receipt_sha256",
        "execution_surface_sha256",
        "schema_version",
        "stage",
        "test_inventory",
        "worker",
        "workload_fidelity",
        "working_directory",
    }
    if type(value) is not dict or set(value) != expected:
        _die("ALT_CHAIN_REJECTED", "execution surface shape")
    surface = cast(dict[str, object], value)
    command = surface["command"]
    controls = surface["control_plane_identities"]
    members = surface["execution_member_identities"]
    inventory = surface["test_inventory"]
    worker = surface["worker"]
    fidelity = surface["workload_fidelity"]
    portable = surface["portable_package"]
    if (
        surface["schema_version"] != EXECUTION_SURFACE_SCHEMA
        or surface["stage"] != stage
        or type(command) is not list
        or not command
        or any(type(item) is not str or not item for item in command)
        or type(surface["working_directory"]) is not str
        or not Path(cast(str, surface["working_directory"])).is_absolute()
        or type(controls) is not dict
        or type(members) is not dict
        or type(inventory) is not dict
        or set(cast(dict[str, object], inventory))
        != {"collection_count", "collection_sha256"}
        or type(worker) is not dict
        or set(cast(dict[str, object], worker))
        != {"count", "mode", "xdist_available"}
        or type(fidelity) is not dict
        or set(cast(dict[str, object], fidelity))
        != {"class", "launch_admissible"}
        or cast(dict[str, object], fidelity)["launch_admissible"] is not True
        or type(portable) is not dict
        or set(cast(dict[str, object], portable))
        != {
            "host_runtime_content_sha256",
            "layout",
            "package_receipt_identity",
            "package_schema_version",
            "source_sets_sha256",
        }
        or cast(dict[str, object], portable)["layout"]
        != PORTABLE_PACKAGE_LAYOUT
        or cast(dict[str, object], portable)["package_schema_version"]
        != CALIBRATION_PACKAGE_SCHEMA
        or cast(dict[str, object], controls).get("profile") != profile_identity
    ):
        _die("ALT_CHAIN_REJECTED", "execution surface boundary")
    checked_controls: dict[str, dict[str, object]] = {}
    checked_members: dict[str, dict[str, object]] = {}
    for target, raw_map, label in (
        (checked_controls, cast(dict[object, object], controls), "control"),
        (checked_members, cast(dict[object, object], members), "member"),
    ):
        for name, identity in sorted(raw_map.items()):
            if (
                type(name) is not str
                or not name
                or type(identity) is not dict
                or set(identity) != {"path", "sha256", "size_bytes"}
            ):
                _die("ALT_CHAIN_REJECTED", f"execution {label} identity")
            target[name] = cast(dict[str, object], identity)
    if not {"code_assets", "profile", "project_lock"} <= set(checked_controls):
        _die("ALT_CHAIN_REJECTED", "execution control identity set")
    for label, identity in {
        **checked_controls,
        **checked_members,
    }.items():
        if (
            type(identity["path"]) is not str
            or not Path(cast(str, identity["path"])).is_absolute()
            or type(identity["sha256"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", cast(str, identity["sha256"]))
            or type(identity["size_bytes"]) is not int
            or cast(int, identity["size_bytes"]) < 0
        ):
            _die("ALT_CHAIN_REJECTED", f"execution identity {label}")
    executable_role = next(
        (
            name
            for name, identity in {**checked_members, **checked_controls}.items()
            if identity["path"] == cast(list[object], command)[0]
        ),
        None,
    )
    if executable_role is None:
        _die("ALT_CHAIN_REJECTED", "execution command role")
    portable_record = cast(dict[str, object], portable)
    raw_package_receipt = portable_record["package_receipt_identity"]
    if (
        type(raw_package_receipt) is not dict
        or set(raw_package_receipt) != {"path", "sha256", "size_bytes"}
    ):
        _die("ALT_CHAIN_REJECTED", "portable package receipt identity")
    package_receipt = cast(dict[str, object], raw_package_receipt)
    if (
        type(package_receipt["path"]) is not str
        or not Path(cast(str, package_receipt["path"])).is_absolute()
        or Path(cast(str, package_receipt["path"])).name != "receipt.json"
        or type(package_receipt["sha256"]) is not str
        or len(cast(str, package_receipt["sha256"])) != 64
        or type(package_receipt["size_bytes"]) is not int
        or cast(int, package_receipt["size_bytes"]) <= 0
        or type(portable_record["host_runtime_content_sha256"]) is not str
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            cast(str, portable_record["host_runtime_content_sha256"]),
        )
        or type(portable_record["source_sets_sha256"]) is not str
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            cast(str, portable_record["source_sets_sha256"]),
        )
    ):
        _die("ALT_CHAIN_REJECTED", "portable package closure")
    inventory_record = cast(dict[str, object], inventory)
    worker_record = cast(dict[str, object], worker)
    fidelity_record = cast(dict[str, object], fidelity)
    working_directory = cast(str, surface["working_directory"])
    if (
        str(Path(working_directory).absolute()) != working_directory
        or type(inventory_record["collection_count"]) is not int
        or cast(int, inventory_record["collection_count"]) < 0
        or type(inventory_record["collection_sha256"]) is not str
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            cast(str, inventory_record["collection_sha256"]),
        )
        or type(worker_record["count"]) is not int
        or cast(int, worker_record["count"]) <= 0
        or type(worker_record["mode"]) is not str
        or type(worker_record["xdist_available"]) is not bool
        or type(fidelity_record["class"]) is not str
        or not cast(str, fidelity_record["class"])
    ):
        _die("ALT_CHAIN_REJECTED", "execution inventory/worker/fidelity values")
    command_record = cast(list[str], command)
    if (
        "python_interpreter" not in checked_members
        or checked_members["python_interpreter"]["path"] != command_record[0]
    ):
        _die("ALT_CHAIN_REJECTED", "execution Python command role")
    if stage == "FULL_PREFLIGHT":
        if (
            command_record[1:] != ["scripts/preflight_gate.py", "--full"]
            or cast(int, inventory_record["collection_count"]) <= 0
            or (
                worker_record
                != {
                    "count": 1,
                    "mode": "pytest-serial",
                    "xdist_available": False,
                }
                and not (
                    worker_record["mode"] == "pytest-xdist-auto"
                    and worker_record["xdist_available"] is True
                )
            )
        ):
            _die("ALT_CHAIN_REJECTED", "full command/inventory/worker mode")
    else:
        if stage not in {"GATE_B_QUALIFICATION", "FORMAL_ORGANIC_ARM"}:
            _die("ALT_CHAIN_REJECTED", "unknown stage")
        verifier = checked_members.get("calibration_package_verifier")
        if verifier is None:
            _die("ALT_CHAIN_REJECTED", "package verifier identity absent")
        expected_command = [
            command_record[0],
            "-I",
            "-B",
            "/proc/self/fd/4",
            "--stage",
            cast(str, stage),
            "--package-root-fd",
            "5",
            "--package-root-path",
            str(Path(cast(str, package_receipt["path"])).parent),
            "--package-receipt-sha256",
            cast(str, package_receipt["sha256"]),
            "--package-receipt-size",
            str(package_receipt["size_bytes"]),
            "--verifier-fd",
            "6",
            "--verifier-sha256",
            cast(str, verifier["sha256"]),
            "--workload-fd",
            "7",
            "--fixture-fd",
            "8",
            "--stage-root-fd",
            "9",
            "--result-fd",
            "10",
        ]
        if (
            command_record != expected_command
            or inventory_record
            != {
                "collection_count": 0,
                "collection_sha256": hashlib.sha256(b"").hexdigest(),
            }
            or worker_record
            != {
                "count": 1,
                "mode": "single-worker",
                "xdist_available": False,
            }
        ):
            _die("ALT_CHAIN_REJECTED", "package command/inventory/worker mode")
    stable = {
        "command": {
            "arguments": cast(list[object], command)[1:],
            "executable_role": executable_role,
        },
        "execution_member_content_identities": {
            name: {
                "sha256": identity["sha256"],
                "size_bytes": identity["size_bytes"],
            }
            for name, identity in checked_members.items()
        },
        "portable_package": {
            "host_runtime_content_sha256": portable_record[
                "host_runtime_content_sha256"
            ],
            "layout": PORTABLE_PACKAGE_LAYOUT,
            "package_receipt_content_identity": {
                "sha256": package_receipt["sha256"],
                "size_bytes": package_receipt["size_bytes"],
            },
            "package_schema_version": CALIBRATION_PACKAGE_SCHEMA,
            "source_sets_sha256": portable_record["source_sets_sha256"],
        },
        "schema_version": EXECUTION_SURFACE_SCHEMA,
        "stage": stage,
        "test_inventory": dict(cast(dict[str, object], inventory)),
        "worker": dict(cast(dict[str, object], worker)),
        "workload_fidelity": dict(cast(dict[str, object], fidelity)),
        "working_directory_role": "repository-root",
    }
    site = {
        "command": list(cast(list[str], command)),
        "control_plane_identities": checked_controls,
        "execution_member_identities": checked_members,
        "portable_package": portable_record,
        "working_directory": surface["working_directory"],
    }
    digest = hashlib.sha256(_encode(stable)).hexdigest()
    if (
        surface["execution_surface_sha256"] != digest
        or surface["execution_site_receipt_sha256"]
        != hashlib.sha256(_encode(site)).hexdigest()
    ):
        _die("ALT_CHAIN_REJECTED", "execution surface digest")
    return digest


def _semantic(root: Path, files: dict[str, bytes]) -> dict[str, object]:
    records = {
        name: _json(raw, name)
        for name, raw in files.items()
        if name != "receipt.json"
    }
    declaration = records[PATHS["declaration"]]
    profile = records[PATHS["installed_profile"]]
    aggregate = records[PATHS["aggregate"]]
    candidate = records[PATHS["profile_candidate"]]
    _boundary(
        declaration,
        schema="noncert-cuts-ab16-resource-calibration-declaration-v1",
        status="DECLARED_NO_AUTHORITY",
        label="declaration",
    )
    declaration_identity = _file_identity(
        root,
        PATHS["declaration"],
        files[PATHS["declaration"]],
    )
    profile_identity = _file_identity(
        root,
        PATHS["installed_profile"],
        files[PATHS["installed_profile"]],
    )
    if declaration.get("installed_profile_identity") != profile_identity:
        _die("ALT_CHAIN_REJECTED", "profile identity")
    surface_sha = _surface_digest(
        declaration.get("execution_surface"),
        stage=declaration.get("stage"),
        profile_identity=profile_identity,
    )

    maxima = {
        "disk_growth_peak_bytes": 0,
        "disk_peak_bytes": 0,
        "memory_peak_bytes": 0,
        "swap_peak_bytes": 0,
    }
    expected_cohort: list[dict[str, object]] = []
    uniqueness: set[tuple[object, object, object]] = set()
    for index in range(1, 4):
        observer_name = PATHS[f"observer_result_{index}"]
        sample_name = PATHS[f"sample_{index}"]
        validation_name = PATHS[f"validation_{index}"]
        observer = records[observer_name]
        sample = records[sample_name]
        validation = records[validation_name]
        _boundary(
            observer,
            schema="noncert-cuts-ab16-resource-calibration-observer-result-v1",
            status="PEAKS_CAPTURED_BEFORE_CGROUP_DISAPPEARANCE",
            label=f"observer {index}",
        )
        _boundary(
            sample,
            schema="noncert-cuts-ab16-resource-calibration-sample-v1",
            status="MEASURED_SUCCESS",
            label=f"sample {index}",
        )
        if (
            validation.get("schema_version")
            != "noncert-cuts-ab16-resource-calibration-validation-v1"
            or validation.get("conclusion") != "ACCEPTED_COMPARABLE_SAMPLE"
            or validation.get("authority_scope") != AUTHORITY
            or validation.get("authorizations") != NO_AUTHORITY
        ):
            _die("ALT_CHAIN_REJECTED", f"validation {index} boundary")
        source = cast(dict[str, object], sample.get("measurement_source"))
        if source.get("observer_result_identity") != _file_identity(
            root,
            observer_name,
            files[observer_name],
        ):
            _die("ALT_CHAIN_REJECTED", f"observer identity {index}")
        limits = observer.get("cgroup_limits")
        disk = cast(dict[str, object], observer.get("disk"))
        disk_io = disk.get("cgroup_io")
        if (
            type(limits) is not dict
            or set(limits) != {"memory.high", "memory.max", "memory.swap.max"}
            or any(type(item) is not int or item < 0 for item in limits.values())
            or type(disk_io) is not dict
            or set(disk_io)
            != {"rows_after", "wbytes_after", "wbytes_before", "wbytes_delta"}
            or any(
                type(disk_io.get(name)) is not int
                or cast(int, disk_io[name]) < 0
                for name in ("wbytes_after", "wbytes_before", "wbytes_delta")
            )
            or disk_io["wbytes_delta"]
            != cast(int, disk_io["wbytes_after"]) - cast(int, disk_io["wbytes_before"])
            or disk.get("measurement_rule")
            != "MAX_RETAINED_TREE_POLLING_AND_CGROUP_IO_WBYTES"
            or type(disk.get("polling_growth_peak_bytes")) is not int
            or disk.get("growth_peak_bytes")
            != max(
                cast(int, disk["polling_growth_peak_bytes"]),
                cast(int, disk_io["wbytes_delta"]),
            )
        ):
            _die("ALT_CHAIN_REJECTED", f"observer cgroup/io {index}")
        cgroup = cast(dict[str, object], sample.get("cgroup"))
        observer_cgroup = cast(dict[str, object], observer.get("cgroup"))
        cgroup_identity = cast(dict[str, object], observer_cgroup.get("identity"))
        if (
            cgroup.get("identity") != cgroup_identity
            or cgroup.get("path") != cgroup_identity.get("path")
            or cgroup.get("peak_read_before_disappearance") is not True
            or cgroup.get("disappeared_after_peak_read") is not True
        ):
            _die("ALT_CHAIN_REJECTED", f"cgroup {index}")
        measurement = cast(dict[str, object], sample.get("measurements"))
        expected_measurement = {
            "disk_after_bytes": disk.get("after_bytes"),
            "disk_before_bytes": disk.get("before_bytes"),
            "disk_growth_peak_bytes": disk.get("growth_peak_bytes"),
            "disk_peak_bytes": disk.get("peak_bytes"),
            "memory_peak_bytes": observer.get("memory_peak_bytes"),
            "swap_peak_bytes": observer.get("swap_peak_bytes"),
        }
        if (
            sample.get("declaration_identity") != declaration_identity
            or sample.get("execution_surface_sha256") != surface_sha
            or sample.get("stage") != declaration.get("stage")
            or sample.get("observer_process_identity")
            != observer.get("observer_process_identity")
            or sample.get("workload_exit_code") != 0
            or measurement != expected_measurement
        ):
            _die("ALT_CHAIN_REJECTED", f"sample join {index}")
        sample_identity = _file_identity(root, sample_name, files[sample_name])
        validation_identity = _file_identity(
            root,
            validation_name,
            files[validation_name],
        )
        if (
            validation.get("declaration_identity") != declaration_identity
            or validation.get("sample_identity") != sample_identity
            or validation.get("sample_measurements") != measurement
            or validation.get("execution_surface_sha256") != surface_sha
        ):
            _die("ALT_CHAIN_REJECTED", f"validation join {index}")
        unique = (
            sample.get("sample_id"),
            cgroup.get("path"),
            sample_identity["sha256"],
        )
        if unique in uniqueness:
            _die("ALT_CHAIN_REJECTED", "sample reuse")
        uniqueness.add(unique)
        for name in maxima:
            maxima[name] = max(maxima[name], _number(measurement.get(name), name))
        expected_cohort.append(
            {
                "sample_id": sample.get("sample_id"),
                "sample_identity": sample_identity,
                "validation_identity": validation_identity,
                "validator_identity": validation.get("validator_identity"),
            }
        )

    aggregate_body = dict(aggregate)
    aggregate_sha = aggregate_body.pop("aggregate_sha256", None)
    if (
        aggregate.get("authority_scope") != AUTHORITY
        or aggregate.get("authorizations") != NO_AUTHORITY
        or aggregate.get("schema_version")
        != "noncert-cuts-ab16-resource-calibration-aggregate-v1"
        or aggregate.get("status") != "AGGREGATED_NO_SELF_AUTHORITY"
        or aggregate.get("sample_count") != 3
        or aggregate.get("declaration_identity") != declaration_identity
        or aggregate.get("cohort") != expected_cohort
        or aggregate.get("maxima") != maxima
        or aggregate_sha != hashlib.sha256(_encode(aggregate_body)).hexdigest()
    ):
        _die("ALT_CHAIN_REJECTED", "aggregate")
    aggregate_identity = _file_identity(
        root,
        PATHS["aggregate"],
        files[PATHS["aggregate"]],
    )
    _boundary(
        candidate,
        schema="noncert-cuts-ab16-resource-calibration-profile-candidate-v1",
        status="INSTALLED_PROFILE_CANDIDATE_ONLY",
        label="candidate",
    )
    if (
        candidate.get("aggregate_identity") != aggregate_identity
        or candidate.get("declaration_identity") != declaration_identity
        or candidate.get("installed_profile_identity") != profile_identity
        or candidate.get("execution_surface_sha256") != surface_sha
        or candidate.get("sample_count") != 3
        or candidate.get("threshold_effect")
        != {
            "may_change_sampled_profile": False,
            "may_lower_current_cohort_threshold": False,
            "profile_was_installed_before_sampling": True,
        }
    ):
        _die("ALT_CHAIN_REJECTED", "candidate join")
    requirements = cast(dict[str, object], profile.get("requirements"))
    coverage = cast(dict[str, object], candidate.get("coverage"))
    if set(requirements) != {"disk", "memory", "swap"} or set(coverage) != {
        "disk",
        "memory",
        "swap",
    }:
        _die("ALT_CHAIN_REJECTED", "coverage shape")
    observed = {
        "disk": maxima["disk_growth_peak_bytes"],
        "memory": maxima["memory_peak_bytes"],
        "swap": maxima["swap_peak_bytes"],
    }
    for dimension in observed:
        requirement = cast(dict[str, object], requirements[dimension])
        predicted = _number(requirement.get("predicted_peak_bytes"), dimension)
        margin = _number(requirement.get("safety_margin_bytes"), dimension)
        reserve = _number(requirement.get("host_reserve_bytes"), dimension)
        minimum = _number(requirement.get("minimum_available_bytes"), dimension)
        rule = requirement.get("availability_rule", "INDEPENDENT_MINIMUM")
        if minimum != (
            predicted + margin + reserve
            if rule == "INDEPENDENT_MINIMUM"
            else 0
            if rule == "COMBINED_RAM_LIMITED_SWAP"
            else -1
        ):
            _die("ALT_CHAIN_REJECTED", f"{dimension} threshold")
        allowance = predicted + margin
        if observed[dimension] > allowance or coverage[dimension] != {
            "host_reserve_bytes": reserve,
            "observed_peak_bytes": observed[dimension],
            "predicted_plus_safety_bytes": allowance,
            "within_preinstalled_workload_allowance": True,
        }:
            _die("ALT_CHAIN_REJECTED", f"{dimension} coverage")
    return {
        "candidate_identity": _file_identity(
            root,
            PATHS["profile_candidate"],
            files[PATHS["profile_candidate"]],
        ),
        "execution_surface_sha256": surface_sha,
        "stage": declaration.get("stage"),
    }


def replay(root: Path) -> dict[str, object]:
    files, kinds, root_stat = _snapshot(root)
    expected_files = set(PATHS.values()) | {"receipt.json"}
    expected = {
        **{name: "regular_file" for name in expected_files},
        "observer-results": "directory",
        "samples": "directory",
        "validations": "directory",
    }
    if kinds != expected:
        _die("ALT_ROOT_CLOSURE_MISMATCH", repr(kinds))
    receipt = _json(files["receipt.json"], "receipt.json")
    if (
        receipt.get("schema_version") != ROOT_SCHEMA
        or receipt.get("status") != "CLOSED_NO_LAUNCH_AUTHORITY"
        or receipt.get("authority_scope") != AUTHORITY
        or receipt.get("authorizations") != NO_AUTHORITY
        or receipt.get("fixed_paths") != PATHS
    ):
        _die("ALT_ROOT_RECEIPT_REJECTED", "receipt boundary")
    manifest = {
        "schema": "research_artifact_root_manifest_v1",
        "entries": [
            {"path": name, "type": kind}
            for name, kind in sorted(expected.items())
            if name != "receipt.json"
        ],
    }
    artifacts = [
        {
            "path": name,
            "sha256": hashlib.sha256(files[name]).hexdigest(),
            "size_bytes": len(files[name]),
        }
        for name in sorted(set(PATHS.values()))
    ]
    root_identity = {
        "device": root_stat.st_dev,
        "inode": root_stat.st_ino,
        "mode": stat.S_IMODE(root_stat.st_mode),
        "path": str(root.absolute()),
        "uid": root_stat.st_uid,
    }
    if (
        receipt.get("manifest") != manifest
        or receipt.get("artifacts") != artifacts
        or receipt.get("root_identity") != root_identity
    ):
        _die("ALT_ROOT_RECEIPT_REJECTED", "receipt closure/identity")
    result = _semantic(root, files)
    result["root_receipt_identity"] = _file_identity(
        root,
        "receipt.json",
        files["receipt.json"],
    )
    return result


def _publish(path: Path, value: object) -> None:
    if path != path.absolute():
        _die("ALT_OUTPUT_REJECTED", "output path is not absolute")
    parent = _open_dir(path.parent)
    target = -1
    primary: BaseException | None = None
    try:
        target = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o400,
            dir_fd=parent,
        )
        data = _encode(value)
        offset = 0
        while offset < len(data):
            count = os.write(target, data[offset:])
            if count <= 0:
                _die("ALT_OUTPUT_REJECTED", "short write")
            offset += count
        os.fsync(target)
    except BaseException as exc:
        primary = exc
    if target >= 0:
        try:
            os.close(target)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "alternate replay output close failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    try:
        os.close(parent)
    except BaseException as close_error:
        if primary is None:
            primary = close_error
        else:
            primary.add_note(
                "alternate replay output-parent close failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
    if primary is not None:
        raise primary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--slot", required=True, choices=("replay-a", "replay-b"))
    parser.add_argument("--expected-source-sha256", required=True)
    arguments = parser.parse_args()
    try:
        source = Path(__file__).read_bytes()
        source_sha = hashlib.sha256(source).hexdigest()
        if arguments.expected_source_sha256 != source_sha:
            _die("ALT_REPLAYER_IDENTITY_DRIFT", source_sha)
        result = replay(arguments.root)
        record = {
            "authority_scope": AUTHORITY,
            "authorizations": dict(NO_AUTHORITY),
            "conclusion": "REPLAY_ACCEPTED_PROFILE_CANDIDATE",
            "execution_surface_sha256": result["execution_surface_sha256"],
            "profile_candidate_identity": result["candidate_identity"],
            "replay_slot": arguments.slot,
            "replay_tool_identity": {
                "path": str(Path(__file__).absolute()),
                "sha256": source_sha,
                "size_bytes": len(source),
            },
            "root_receipt_identity": result["root_receipt_identity"],
            "schema_version": REPLAY_SCHEMA,
            "stage": result["stage"],
            "status": "PASS_NO_LAUNCH_AUTHORITY",
        }
        _publish(arguments.output, record)
        sys.stdout.buffer.write(_encode(record))
        return 0
    except BaseException as exc:
        sys.stdout.buffer.write(
            _encode(
                {
                    "authority_scope": AUTHORITY,
                    "code": getattr(exc, "code", type(exc).__name__),
                    "conclusion": None,
                    "status": "FAIL_CLOSED",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
