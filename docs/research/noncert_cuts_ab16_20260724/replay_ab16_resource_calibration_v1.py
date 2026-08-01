#!/usr/bin/env python3
"""Independent stdlib replay for one closed AB16 calibration cohort."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import NoReturn, cast


RECEIPT_SCHEMA = "noncert-cuts-ab16-resource-calibration-root-receipt-v1"
REPLAY_SCHEMA = "noncert-cuts-ab16-resource-calibration-outside-replay-v1"
AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
SAMPLE_COUNT = 3
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
FALSE_AUTHORIZATIONS = {
    "formal_campaign_creation_authorized": False,
    "gate_b_approval_authorized": False,
    "organic_arm_launch_authorized": False,
    "profile_installation_authorized": False,
    "solver_run_authorized": False,
}
VALIDATION_SCHEMA = "noncert-cuts-ab16-resource-calibration-validation-v1"
EXECUTION_SURFACE_SCHEMA = "noncert-cuts-ab16-resource-execution-surface-v3"
CALIBRATION_PACKAGE_SCHEMA = "noncert-cuts-ab16-resource-calibration-package-v2"
PORTABLE_PACKAGE_LAYOUT = "PORTABLE_CANDIDATE_V1"
FIXED_PATHS = {
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


class ReplayError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise ReplayError(code, detail)


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


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("CALIBRATION_JSON_INVALID", f"duplicate key {key!r}")
        result[key] = value
    return result


def _load(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_constant=lambda item: _fail(
                "CALIBRATION_JSON_INVALID",
                f"{label}: non-finite number {item}",
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("CALIBRATION_JSON_INVALID", f"{label}: {exc}")
    if type(value) is not dict or _canonical(value) != raw:
        _fail("CALIBRATION_JSON_INVALID", f"{label}: bytes are not canonical")
    return cast(dict[str, object], value)


def _closed(value: object, fields: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        _fail("CALIBRATION_RECORD_INVALID", f"{label} field set drifted")
    return cast(dict[str, object], value)


def _nonnegative(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail("CALIBRATION_RECORD_INVALID", f"{label} is not nonnegative")
    return value


def _identity(
    value: object,
    *,
    path: str,
    raw: bytes,
    label: str,
) -> dict[str, object]:
    expected = {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    if value != expected:
        _fail("CALIBRATION_IDENTITY_MISMATCH", f"{label} identity drifted")
    return expected


def _authority(value: object, label: str) -> None:
    if value != FALSE_AUTHORIZATIONS:
        _fail("CALIBRATION_AUTHORITY_EXPANSION", label)


def _external_identity(value: object, label: str) -> dict[str, object]:
    record = _closed(value, {"path", "sha256", "size_bytes"}, label)
    if (
        type(record["path"]) is not str
        or not Path(cast(str, record["path"])).is_absolute()
        or type(record["sha256"]) is not str
        or SHA_RE.fullmatch(cast(str, record["sha256"])) is None
        or type(record["size_bytes"]) is not int
        or cast(int, record["size_bytes"]) < 0
    ):
        _fail("CALIBRATION_IDENTITY_MISMATCH", f"{label} is malformed")
    return record


def _require_canonical_content_identity(
    value: object,
    identity: Mapping[str, object],
    label: str,
) -> None:
    if type(value) is not dict:
        _fail(
            "CALIBRATION_IDENTITY_MISMATCH",
            f"{label} content is not a strict JSON object",
        )
    try:
        raw = _canonical(value)
    except (TypeError, ValueError) as exc:
        _fail(
            "CALIBRATION_IDENTITY_MISMATCH",
            f"{label} content is not canonical JSON: {exc}",
        )
    if (
        identity["sha256"] != hashlib.sha256(raw).hexdigest()
        or identity["size_bytes"] != len(raw)
    ):
        _fail(
            "CALIBRATION_IDENTITY_MISMATCH",
            f"{label} canonical content does not match its identity",
        )


def build_independent_validation(
    *,
    sample: Mapping[str, object],
    sample_identity: Mapping[str, object],
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
    validator_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build one protocol-compatible validation in the primary replay code."""

    checked_declaration_identity = _external_identity(
        declaration_identity,
        "declaration identity",
    )
    checked_sample_identity = _external_identity(
        sample_identity,
        "sample identity",
    )
    _require_canonical_content_identity(
        declaration,
        checked_declaration_identity,
        "declaration",
    )
    _require_canonical_content_identity(
        sample,
        checked_sample_identity,
        "sample",
    )
    if (
        declaration.get("schema_version")
        != "noncert-cuts-ab16-resource-calibration-declaration-v1"
        or declaration.get("status") != "DECLARED_NO_AUTHORITY"
        or declaration.get("authority_scope") != AUTHORITY_SCOPE
        or sample.get("schema_version")
        != "noncert-cuts-ab16-resource-calibration-sample-v1"
        or sample.get("status") != "MEASURED_SUCCESS"
        or sample.get("authority_scope") != AUTHORITY_SCOPE
    ):
        _fail(
            "CALIBRATION_SAMPLE_NONCOMPARABLE",
            "sample/declaration discriminator drifted",
        )
    _authority(declaration.get("authorizations"), "declaration")
    _authority(sample.get("authorizations"), "sample")
    checked_validator = _external_identity(
        validator_identity,
        "validator identity",
    )
    source = Path(__file__).read_bytes()
    if (
        checked_validator["sha256"] != hashlib.sha256(source).hexdigest()
        or checked_validator["size_bytes"] != len(source)
    ):
        _fail(
            "CALIBRATION_VALIDATOR_IDENTITY_DRIFT",
            "validator identity does not name the executing replay bytes",
        )
    surface = declaration.get("execution_surface")
    measurements = sample.get("measurements")
    if (
        type(surface) is not dict
        or type(measurements) is not dict
        or sample.get("declaration_identity") != checked_declaration_identity
        or sample.get("stage") != declaration.get("stage")
        or sample.get("execution_surface_sha256")
        != surface.get("execution_surface_sha256")
        or sample.get("workload_exit_code") != 0
    ):
        _fail(
            "CALIBRATION_SAMPLE_NONCOMPARABLE",
            "sample/declaration join drifted",
        )
    expected_measurements = {
        "disk_after_bytes",
        "disk_before_bytes",
        "disk_growth_peak_bytes",
        "disk_peak_bytes",
        "memory_peak_bytes",
        "swap_peak_bytes",
    }
    if set(measurements) != expected_measurements or any(
        type(value) is not int or value < 0 for value in measurements.values()
    ):
        _fail(
            "CALIBRATION_SAMPLE_NONCOMPARABLE",
            "sample measurements are malformed",
        )
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "conclusion": "ACCEPTED_COMPARABLE_SAMPLE",
        "declaration_identity": checked_declaration_identity,
        "execution_surface_sha256": surface["execution_surface_sha256"],
        "sample_identity": checked_sample_identity,
        "sample_measurements": dict(measurements),
        "schema_version": VALIDATION_SCHEMA,
        "stage": declaration["stage"],
        "validator_identity": checked_validator,
    }


def _signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_blocks,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _open_root(path: Path) -> int:
    absolute = path.absolute()
    if path != absolute:
        _fail("CALIBRATION_ROOT_INVALID", "root path is not absolute")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    opened = [os.open("/", flags)]
    primary: BaseException | None = None
    try:
        for component in absolute.parts[1:]:
            opened.append(
                os.open(component, flags, dir_fd=opened[-1])
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
                    "calibration replay directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        if result >= 0:
            try:
                os.close(result)
            except BaseException as close_error:
                primary.add_note(
                    "calibration replay retained-root cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise primary
    return result


def _read_root(path: Path) -> tuple[dict[str, bytes], dict[str, str], os.stat_result]:
    root = _open_root(path)
    directories: list[tuple[int, str, tuple[int, ...], tuple[str, ...]]] = []
    files: dict[str, bytes] = {}
    types: dict[str, str] = {}
    seen_inodes: set[tuple[int, int]] = set()
    primary: BaseException | None = None
    root_stat = os.fstat(root)
    try:
        pending = [(root, "")]
        root = -1
        while pending:
            descriptor, prefix = pending.pop()
            metadata = os.fstat(descriptor)
            names = tuple(sorted(os.listdir(descriptor), key=os.fsencode))
            directories.append((descriptor, prefix, _signature(metadata), names))
            for name in names:
                relative = f"{prefix}/{name}" if prefix else name
                if (
                    name in {"", ".", ".."}
                    or "/" in name
                    or "\\" in name
                    or "\x00" in name
                ):
                    _fail("CALIBRATION_ROOT_INVALID", f"unsafe member {relative!r}")
                observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISDIR(observed.st_mode):
                    child = os.open(
                        name,
                        os.O_RDONLY
                        | os.O_CLOEXEC
                        | os.O_DIRECTORY
                        | os.O_NOFOLLOW,
                        dir_fd=descriptor,
                    )
                    if _signature(os.fstat(child)) != _signature(observed):
                        os.close(child)
                        _fail("CALIBRATION_ROOT_CHANGED", relative)
                    types[relative] = "directory"
                    pending.append((child, relative))
                elif stat.S_ISREG(observed.st_mode):
                    if observed.st_nlink != 1:
                        _fail("CALIBRATION_ROOT_HARDLINK_REJECTED", relative)
                    inode = (observed.st_dev, observed.st_ino)
                    if inode in seen_inodes:
                        _fail("CALIBRATION_ROOT_HARDLINK_REJECTED", relative)
                    seen_inodes.add(inode)
                    child = os.open(
                        name,
                        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=descriptor,
                    )
                    try:
                        opened = os.fstat(child)
                        if _signature(opened) != _signature(observed):
                            _fail("CALIBRATION_ROOT_CHANGED", relative)
                        chunks: list[bytes] = []
                        while True:
                            chunk = os.read(child, 1024 * 1024)
                            if not chunk:
                                break
                            chunks.append(chunk)
                        if _signature(os.fstat(child)) != _signature(opened):
                            _fail("CALIBRATION_ROOT_CHANGED", relative)
                    finally:
                        os.close(child)
                    files[relative] = b"".join(chunks)
                    types[relative] = "regular_file"
                else:
                    _fail("CALIBRATION_ROOT_SPECIAL_NODE_REJECTED", relative)
        for descriptor, relative, before, names in directories:
            if (
                _signature(os.fstat(descriptor)) != before
                or tuple(sorted(os.listdir(descriptor), key=os.fsencode)) != names
            ):
                _fail("CALIBRATION_ROOT_CHANGED", relative or ".")
        rejoined = _open_root(path)
        try:
            if _signature(os.fstat(rejoined)) != _signature(root_stat):
                _fail("CALIBRATION_ROOT_CHANGED", "absolute root join drifted")
        finally:
            os.close(rejoined)
        return files, types, root_stat
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if root >= 0:
            os.close(root)
        for descriptor, _relative, _before, _names in reversed(directories):
            try:
                os.close(descriptor)
            except BaseException as close_error:
                if primary is None:
                    raise
                primary.add_note(
                    f"calibration replay descriptor close failed: {close_error}"
                )


def _require_schema(
    value: Mapping[str, object],
    schema: str,
    status: str,
    label: str,
) -> None:
    if (
        value.get("schema_version") != schema
        or value.get("status") != status
        or value.get("authority_scope") != AUTHORITY_SCOPE
    ):
        _fail("CALIBRATION_CHAIN_INVALID", f"{label} boundary drifted")
    _authority(value.get("authorizations"), label)


def _profile_limits(profile: Mapping[str, object], stage: object) -> dict[str, int]:
    if profile.get("stage") != stage:
        _fail("CALIBRATION_CHAIN_INVALID", "installed profile stage drifted")
    requirements = profile.get("requirements")
    if type(requirements) is not dict or set(requirements) != {
        "disk",
        "memory",
        "swap",
    }:
        _fail("CALIBRATION_CHAIN_INVALID", "installed profile requirements drifted")
    result: dict[str, int] = {}
    for dimension in ("disk", "memory", "swap"):
        item = cast(dict[str, object], requirements)[dimension]
        if type(item) is not dict:
            _fail("CALIBRATION_CHAIN_INVALID", f"{dimension} profile is malformed")
        predicted = _nonnegative(item.get("predicted_peak_bytes"), dimension)
        margin = _nonnegative(item.get("safety_margin_bytes"), dimension)
        reserve = _nonnegative(item.get("host_reserve_bytes"), dimension)
        minimum = _nonnegative(item.get("minimum_available_bytes"), dimension)
        rule = item.get("availability_rule", "INDEPENDENT_MINIMUM")
        expected = (
            predicted + margin + reserve
            if rule == "INDEPENDENT_MINIMUM"
            else 0
            if rule == "COMBINED_RAM_LIMITED_SWAP"
            else -1
        )
        if minimum != expected:
            _fail("CALIBRATION_CHAIN_INVALID", f"{dimension} arithmetic drifted")
        result[dimension] = predicted + margin
    return result


def _execution_surface_digest(
    surface: object,
    *,
    stage: object,
    profile_identity: Mapping[str, object],
) -> str:
    fields = {
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
    value = _closed(surface, fields, "execution surface")
    command = value["command"]
    controls = value["control_plane_identities"]
    members = value["execution_member_identities"]
    inventory = value["test_inventory"]
    worker = value["worker"]
    fidelity = value["workload_fidelity"]
    portable = value["portable_package"]
    if (
        value["schema_version"] != EXECUTION_SURFACE_SCHEMA
        or value["stage"] != stage
        or type(command) is not list
        or not command
        or any(type(item) is not str or not item for item in command)
        or type(value["working_directory"]) is not str
        or not Path(cast(str, value["working_directory"])).is_absolute()
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
        _fail("CALIBRATION_CHAIN_INVALID", "execution surface shape/join drifted")
    checked_controls = {
        name: _closed(
            identity,
            {"path", "sha256", "size_bytes"},
            f"control identity {name}",
        )
        for name, identity in sorted(cast(dict[str, object], controls).items())
        if type(name) is str and name
    }
    checked_members = {
        name: _closed(
            identity,
            {"path", "sha256", "size_bytes"},
            f"member identity {name}",
        )
        for name, identity in sorted(cast(dict[str, object], members).items())
        if type(name) is str and name
    }
    if (
        len(checked_controls) != len(cast(dict[str, object], controls))
        or len(checked_members) != len(cast(dict[str, object], members))
        or not {"code_assets", "profile", "project_lock"} <= set(checked_controls)
    ):
        _fail("CALIBRATION_CHAIN_INVALID", "execution surface labels drifted")
    for label, identity in {
        **checked_controls,
        **checked_members,
    }.items():
        if (
            type(identity["path"]) is not str
            or not Path(cast(str, identity["path"])).is_absolute()
            or type(identity["sha256"]) is not str
            or SHA_RE.fullmatch(cast(str, identity["sha256"])) is None
            or type(identity["size_bytes"]) is not int
            or cast(int, identity["size_bytes"]) < 0
        ):
            _fail(
                "CALIBRATION_CHAIN_INVALID",
                f"execution identity is malformed: {label}",
            )
    executable_role = next(
        (
            name
            for name, identity in {**checked_members, **checked_controls}.items()
            if identity["path"] == cast(list[object], command)[0]
        ),
        None,
    )
    if executable_role is None:
        _fail("CALIBRATION_CHAIN_INVALID", "execution surface executable is unbound")
    portable_record = cast(dict[str, object], portable)
    package_receipt = _closed(
        portable_record["package_receipt_identity"],
        {"path", "sha256", "size_bytes"},
        "portable package receipt identity",
    )
    if (
        type(package_receipt["path"]) is not str
        or not Path(cast(str, package_receipt["path"])).is_absolute()
        or Path(cast(str, package_receipt["path"])).name != "receipt.json"
        or type(package_receipt["sha256"]) is not str
        or len(cast(str, package_receipt["sha256"])) != 64
        or type(package_receipt["size_bytes"]) is not int
        or cast(int, package_receipt["size_bytes"]) <= 0
        or type(portable_record["host_runtime_content_sha256"]) is not str
        or SHA_RE.fullmatch(
            cast(str, portable_record["host_runtime_content_sha256"])
        )
        is None
        or type(portable_record["source_sets_sha256"]) is not str
        or SHA_RE.fullmatch(cast(str, portable_record["source_sets_sha256"]))
        is None
    ):
        _fail("CALIBRATION_CHAIN_INVALID", "portable package closure is malformed")
    inventory_record = cast(dict[str, object], inventory)
    worker_record = cast(dict[str, object], worker)
    fidelity_record = cast(dict[str, object], fidelity)
    working_directory = cast(str, value["working_directory"])
    if (
        str(Path(working_directory).absolute()) != working_directory
        or type(inventory_record["collection_count"]) is not int
        or cast(int, inventory_record["collection_count"]) < 0
        or type(inventory_record["collection_sha256"]) is not str
        or SHA_RE.fullmatch(
            cast(str, inventory_record["collection_sha256"])
        )
        is None
        or type(worker_record["count"]) is not int
        or cast(int, worker_record["count"]) <= 0
        or type(worker_record["mode"]) is not str
        or type(worker_record["xdist_available"]) is not bool
        or type(fidelity_record["class"]) is not str
        or not cast(str, fidelity_record["class"])
    ):
        _fail(
            "CALIBRATION_CHAIN_INVALID",
            "execution inventory/worker/fidelity values are malformed",
        )
    command_record = cast(list[str], command)
    if (
        "python_interpreter" not in checked_members
        or checked_members["python_interpreter"]["path"] != command_record[0]
    ):
        _fail(
            "CALIBRATION_CHAIN_INVALID",
            "execution command is not bound to the Python interpreter role",
        )
    if stage == "FULL_PREFLIGHT":
        if (
            command_record[1:] != ["scripts/preflight_gate.py", "--full"]
            or cast(int, inventory_record["collection_count"]) <= 0
            or (
                worker_record
                not in (
                    {
                        "count": 1,
                        "mode": "pytest-serial",
                        "xdist_available": False,
                    },
                )
                and not (
                    worker_record["mode"] == "pytest-xdist-auto"
                    and worker_record["xdist_available"] is True
                )
            )
        ):
            _fail(
                "CALIBRATION_CHAIN_INVALID",
                "full execution command/inventory/worker mode drifted",
            )
    else:
        if stage not in {"GATE_B_QUALIFICATION", "FORMAL_ORGANIC_ARM"}:
            _fail("CALIBRATION_CHAIN_INVALID", f"unknown stage: {stage!r}")
        verifier_identity = checked_members.get(
            "calibration_package_verifier"
        )
        if verifier_identity is None:
            _fail(
                "CALIBRATION_CHAIN_INVALID",
                "package verifier identity is absent",
            )
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
            cast(str, verifier_identity["sha256"]),
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
            _fail(
                "CALIBRATION_CHAIN_INVALID",
                "package execution command/inventory/worker mode drifted",
            )
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
        "portable_package": {
            **portable_record,
            "package_receipt_identity": package_receipt,
        },
        "working_directory": value["working_directory"],
    }
    digest = hashlib.sha256(_canonical(stable)).hexdigest()
    if (
        value["execution_surface_sha256"] != digest
        or value["execution_site_receipt_sha256"]
        != hashlib.sha256(_canonical(site)).hexdigest()
    ):
        _fail("CALIBRATION_CHAIN_INVALID", "execution surface digest drifted")
    return digest


def _replay_chain(
    root: Path,
    files: Mapping[str, bytes],
) -> tuple[dict[str, object], dict[str, object]]:
    values = {
        path: _load(raw, path)
        for path, raw in files.items()
        if path != "receipt.json"
    }
    declaration = values[FIXED_PATHS["declaration"]]
    profile = values[FIXED_PATHS["installed_profile"]]
    aggregate = values[FIXED_PATHS["aggregate"]]
    candidate = values[FIXED_PATHS["profile_candidate"]]
    _require_schema(
        declaration,
        "noncert-cuts-ab16-resource-calibration-declaration-v1",
        "DECLARED_NO_AUTHORITY",
        "declaration",
    )
    declaration_path = str((root / FIXED_PATHS["declaration"]).absolute())
    declaration_identity = {
        "path": declaration_path,
        "sha256": hashlib.sha256(
            files[FIXED_PATHS["declaration"]]
        ).hexdigest(),
        "size_bytes": len(files[FIXED_PATHS["declaration"]]),
    }
    profile_identity = _identity(
        declaration.get("installed_profile_identity"),
        path=str((root / FIXED_PATHS["installed_profile"]).absolute()),
        raw=files[FIXED_PATHS["installed_profile"]],
        label="installed profile",
    )
    surface_digest = _execution_surface_digest(
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
    cohort: list[dict[str, object]] = []
    sample_ids: set[object] = set()
    cgroups: set[object] = set()
    for index in range(1, SAMPLE_COUNT + 1):
        observer_path = FIXED_PATHS[f"observer_result_{index}"]
        sample_path = FIXED_PATHS[f"sample_{index}"]
        validation_path = FIXED_PATHS[f"validation_{index}"]
        observer = values[observer_path]
        sample = values[sample_path]
        validation = values[validation_path]
        _require_schema(
            observer,
            "noncert-cuts-ab16-resource-calibration-observer-result-v1",
            "PEAKS_CAPTURED_BEFORE_CGROUP_DISAPPEARANCE",
            f"observer {index}",
        )
        _require_schema(
            sample,
            "noncert-cuts-ab16-resource-calibration-sample-v1",
            "MEASURED_SUCCESS",
            f"sample {index}",
        )
        if (
            validation.get("schema_version")
            != "noncert-cuts-ab16-resource-calibration-validation-v1"
            or validation.get("conclusion") != "ACCEPTED_COMPARABLE_SAMPLE"
            or validation.get("authority_scope") != AUTHORITY_SCOPE
        ):
            _fail(
                "CALIBRATION_CHAIN_INVALID",
                f"validation {index} boundary drifted",
            )
        _authority(
            validation.get("authorizations"),
            f"validation {index}",
        )
        observer_identity = _identity(
            cast(dict[str, object], sample["measurement_source"])[
                "observer_result_identity"
            ],
            path=str((root / observer_path).absolute()),
            raw=files[observer_path],
            label=f"observer {index}",
        )
        del observer_identity
        limits = observer.get("cgroup_limits")
        disk_io = cast(dict[str, object], cast(dict[str, object], observer.get("disk")).get("cgroup_io"))
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
        ):
            _fail("CALIBRATION_CHAIN_INVALID", f"observer {index} cgroup/io drifted")
        if sample.get("declaration_identity") != declaration_identity:
            _fail("CALIBRATION_CHAIN_INVALID", f"sample {index} declaration drifted")
        cgroup = cast(dict[str, object], sample.get("cgroup"))
        observer_cgroup = cast(dict[str, object], observer.get("cgroup"))
        if (
            cgroup.get("identity") != observer_cgroup.get("identity")
            or cgroup.get("path")
            != cast(dict[str, object], observer_cgroup.get("identity")).get("path")
            or cgroup.get("peak_read_before_disappearance") is not True
            or cgroup.get("disappeared_after_peak_read") is not True
        ):
            _fail("CALIBRATION_CHAIN_INVALID", f"sample {index} cgroup drifted")
        measurements = cast(dict[str, object], sample.get("measurements"))
        observer_disk = cast(dict[str, object], observer.get("disk"))
        if (
            observer_disk.get("measurement_rule")
            != "MAX_RETAINED_TREE_POLLING_AND_CGROUP_IO_WBYTES"
            or type(observer_disk.get("polling_growth_peak_bytes")) is not int
            or observer_disk.get("growth_peak_bytes")
            != max(
                cast(int, observer_disk["polling_growth_peak_bytes"]),
                cast(int, disk_io["wbytes_delta"]),
            )
        ):
            _fail("CALIBRATION_CHAIN_INVALID", f"observer {index} disk rule drifted")
        expected_measurements = {
            "disk_after_bytes": observer_disk.get("after_bytes"),
            "disk_before_bytes": observer_disk.get("before_bytes"),
            "disk_growth_peak_bytes": observer_disk.get("growth_peak_bytes"),
            "disk_peak_bytes": observer_disk.get("peak_bytes"),
            "memory_peak_bytes": observer.get("memory_peak_bytes"),
            "swap_peak_bytes": observer.get("swap_peak_bytes"),
        }
        if measurements != expected_measurements or sample.get(
            "observer_process_identity"
        ) != observer.get("observer_process_identity"):
            _fail("CALIBRATION_CHAIN_INVALID", f"sample {index} measurement drifted")
        if sample.get("workload_exit_code") != 0:
            _fail("CALIBRATION_CHAIN_INVALID", f"sample {index} workload failed")
        sample_id = sample.get("sample_id")
        cgroup_path = cgroup.get("path")
        if sample_id in sample_ids or cgroup_path in cgroups:
            _fail("CALIBRATION_CHAIN_INVALID", "sample/cgroup was reused")
        sample_ids.add(sample_id)
        cgroups.add(cgroup_path)
        sample_identity = {
            "path": str((root / sample_path).absolute()),
            "sha256": hashlib.sha256(files[sample_path]).hexdigest(),
            "size_bytes": len(files[sample_path]),
        }
        validation_identity = {
            "path": str((root / validation_path).absolute()),
            "sha256": hashlib.sha256(files[validation_path]).hexdigest(),
            "size_bytes": len(files[validation_path]),
        }
        if (
            validation.get("declaration_identity") != declaration_identity
            or validation.get("sample_identity") != sample_identity
            or validation.get("sample_measurements") != measurements
            or validation.get("stage") != declaration.get("stage")
            or validation.get("execution_surface_sha256") != surface_digest
        ):
            _fail("CALIBRATION_CHAIN_INVALID", f"validation {index} join drifted")
        for field in maxima:
            maxima[field] = max(maxima[field], _nonnegative(measurements[field], field))
        cohort.append(
            {
                "sample_id": sample_id,
                "sample_identity": sample_identity,
                "validation_identity": validation_identity,
                "validator_identity": validation.get("validator_identity"),
            }
        )

    aggregate_copy = dict(aggregate)
    aggregate_digest = aggregate_copy.pop("aggregate_sha256", None)
    if (
        aggregate_digest
        != hashlib.sha256(_canonical(aggregate_copy)).hexdigest()
        or aggregate.get("schema_version")
        != "noncert-cuts-ab16-resource-calibration-aggregate-v1"
        or aggregate.get("status") != "AGGREGATED_NO_SELF_AUTHORITY"
        or aggregate.get("sample_count") != SAMPLE_COUNT
        or aggregate.get("declaration_identity") != declaration_identity
        or aggregate.get("execution_surface_sha256") != surface_digest
        or aggregate.get("cohort") != cohort
        or aggregate.get("maxima") != maxima
    ):
        _fail("CALIBRATION_CHAIN_INVALID", "aggregate reconstruction drifted")
    _authority(aggregate.get("authorizations"), "aggregate")

    aggregate_identity = {
        "path": str((root / FIXED_PATHS["aggregate"]).absolute()),
        "sha256": hashlib.sha256(files[FIXED_PATHS["aggregate"]]).hexdigest(),
        "size_bytes": len(files[FIXED_PATHS["aggregate"]]),
    }
    _require_schema(
        candidate,
        "noncert-cuts-ab16-resource-calibration-profile-candidate-v1",
        "INSTALLED_PROFILE_CANDIDATE_ONLY",
        "profile candidate",
    )
    if (
        candidate.get("aggregate_identity") != aggregate_identity
        or candidate.get("declaration_identity") != declaration_identity
        or candidate.get("installed_profile_identity") != profile_identity
        or candidate.get("execution_surface_sha256") != surface_digest
        or candidate.get("sample_count") != SAMPLE_COUNT
        or candidate.get("threshold_effect")
        != {
            "may_change_sampled_profile": False,
            "may_lower_current_cohort_threshold": False,
            "profile_was_installed_before_sampling": True,
        }
    ):
        _fail("CALIBRATION_CHAIN_INVALID", "profile candidate join drifted")
    limits = _profile_limits(profile, declaration.get("stage"))
    coverage = candidate.get("coverage")
    if type(coverage) is not dict or set(coverage) != {"disk", "memory", "swap"}:
        _fail("CALIBRATION_CHAIN_INVALID", "candidate coverage drifted")
    observed = {
        "disk": maxima["disk_growth_peak_bytes"],
        "memory": maxima["memory_peak_bytes"],
        "swap": maxima["swap_peak_bytes"],
    }
    requirements = cast(dict[str, object], profile["requirements"])
    for dimension in ("disk", "memory", "swap"):
        item = cast(dict[str, object], coverage[dimension])
        reserve = cast(dict[str, object], requirements[dimension])[
            "host_reserve_bytes"
        ]
        if item != {
            "host_reserve_bytes": reserve,
            "observed_peak_bytes": observed[dimension],
            "predicted_plus_safety_bytes": limits[dimension],
            "within_preinstalled_workload_allowance": True,
        } or observed[dimension] > limits[dimension]:
            _fail(
                "CALIBRATION_CHAIN_INVALID",
                f"candidate {dimension} coverage drifted",
            )
    return candidate, declaration


def replay(root: Path) -> dict[str, object]:
    files, types, root_stat = _read_root(root)
    expected_files = set(FIXED_PATHS.values()) | {"receipt.json"}
    expected_types = {
        **{path: "regular_file" for path in expected_files},
        "observer-results": "directory",
        "samples": "directory",
        "validations": "directory",
    }
    if types != expected_types:
        _fail("CALIBRATION_ROOT_CLOSURE_MISMATCH", repr(types))
    receipt = _load(files["receipt.json"], "receipt.json")
    _closed(
        receipt,
        {
            "artifacts",
            "authority_scope",
            "authorizations",
            "fixed_paths",
            "manifest",
            "root_identity",
            "schema_version",
            "status",
        },
        "root receipt",
    )
    _require_schema(
        receipt,
        RECEIPT_SCHEMA,
        "CLOSED_NO_LAUNCH_AUTHORITY",
        "root receipt",
    )
    if receipt["fixed_paths"] != FIXED_PATHS:
        _fail("CALIBRATION_FIXED_PATH_MISMATCH", "fixed path mapping drifted")
    expected_manifest = {
        "schema": "research_artifact_root_manifest_v1",
        "entries": [
            {"path": path, "type": node_type}
            for path, node_type in sorted(expected_types.items())
            if path != "receipt.json"
        ],
    }
    if receipt["manifest"] != expected_manifest:
        _fail("CALIBRATION_ROOT_CLOSURE_MISMATCH", "manifest drifted")
    expected_artifacts = [
        {
            "path": path,
            "sha256": hashlib.sha256(files[path]).hexdigest(),
            "size_bytes": len(files[path]),
        }
        for path in sorted(set(FIXED_PATHS.values()))
    ]
    if receipt["artifacts"] != expected_artifacts:
        _fail("CALIBRATION_ARTIFACT_IDENTITY_MISMATCH", "artifact list drifted")
    expected_root_identity = {
        "device": root_stat.st_dev,
        "inode": root_stat.st_ino,
        "mode": stat.S_IMODE(root_stat.st_mode),
        "path": str(root.absolute()),
        "uid": root_stat.st_uid,
    }
    if receipt["root_identity"] != expected_root_identity:
        _fail("CALIBRATION_ROOT_IDENTITY_MISMATCH", "root identity drifted")
    candidate, declaration = _replay_chain(root, files)
    candidate_raw = files[FIXED_PATHS["profile_candidate"]]
    return {
        "candidate_identity": {
            "path": str((root / FIXED_PATHS["profile_candidate"]).absolute()),
            "sha256": hashlib.sha256(candidate_raw).hexdigest(),
            "size_bytes": len(candidate_raw),
        },
        "execution_surface_sha256": candidate["execution_surface_sha256"],
        "root_receipt_identity": {
            "path": str((root / "receipt.json").absolute()),
            "sha256": hashlib.sha256(files["receipt.json"]).hexdigest(),
            "size_bytes": len(files["receipt.json"]),
        },
        "stage": declaration["stage"],
    }


def _write_no_overwrite(path: Path, value: object) -> None:
    if path != path.absolute():
        _fail("CALIBRATION_REPLAY_OUTPUT_INVALID", "output path is not absolute")
    parent = _open_root(path.parent)
    descriptor = -1
    primary: BaseException | None = None
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o400,
            dir_fd=parent,
        )
        raw = _canonical(value)
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                _fail("CALIBRATION_REPLAY_OUTPUT_FAILED", str(path))
            view = view[written:]
        os.fsync(descriptor)
    except BaseException as exc:
        primary = exc
    if descriptor >= 0:
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "calibration replay output close failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    try:
        os.close(parent)
    except BaseException as close_error:
        if primary is None:
            primary = close_error
        else:
            primary.add_note(
                "calibration replay output-parent close failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
    if primary is not None:
        raise primary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--slot", required=True, choices=("replay-a", "replay-b"))
    parser.add_argument("--expected-source-sha256", required=True)
    arguments = parser.parse_args(argv)
    try:
        source_raw = Path(__file__).read_bytes()
        source_sha = hashlib.sha256(source_raw).hexdigest()
        if (
            SHA_RE.fullmatch(arguments.expected_source_sha256) is None
            or source_sha != arguments.expected_source_sha256
        ):
            _fail("CALIBRATION_REPLAYER_IDENTITY_DRIFT", source_sha)
        result = replay(arguments.root)
        output = {
            "authority_scope": AUTHORITY_SCOPE,
            "authorizations": dict(FALSE_AUTHORIZATIONS),
            "conclusion": "REPLAY_ACCEPTED_PROFILE_CANDIDATE",
            "execution_surface_sha256": result["execution_surface_sha256"],
            "profile_candidate_identity": result["candidate_identity"],
            "replay_slot": arguments.slot,
            "replay_tool_identity": {
                "path": str(Path(__file__).absolute()),
                "sha256": source_sha,
                "size_bytes": len(source_raw),
            },
            "root_receipt_identity": result["root_receipt_identity"],
            "schema_version": REPLAY_SCHEMA,
            "stage": result["stage"],
            "status": "PASS_NO_LAUNCH_AUTHORITY",
        }
        _write_no_overwrite(arguments.output, output)
        sys.stdout.buffer.write(_canonical(output))
        return 0
    except BaseException as exc:
        failure = {
            "authority_scope": AUTHORITY_SCOPE,
            "code": getattr(exc, "code", type(exc).__name__),
            "conclusion": None,
            "status": "FAIL_CLOSED",
        }
        sys.stdout.buffer.write(_canonical(failure))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
