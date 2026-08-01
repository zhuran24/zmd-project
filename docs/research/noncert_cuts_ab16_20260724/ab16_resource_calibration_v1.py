#!/usr/bin/env python3
"""Fail-closed calibration records for the prospective AB16 resource cohort.

This module never launches pytest, a solver, Gate A, Gate B, or an AB16 arm.
It validates the declaration -> sample -> independent validation -> aggregate
-> installed-profile candidate chain.  A sample cannot authorize the profile
under which it ran.  Final launch readiness additionally requires two
different outside replay tools over three comparable samples from the exact
candidate execution surface.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Final, NoReturn, cast


DECLARATION_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-declaration-v1"
)
SAMPLE_SCHEMA: Final = "noncert-cuts-ab16-resource-calibration-sample-v1"
VALIDATION_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-validation-v1"
)
AGGREGATE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-aggregate-v1"
)
PROFILE_CANDIDATE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-profile-candidate-v1"
)
OUTSIDE_REPLAY_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-outside-replay-v1"
)
AUTHORIZATION_BUNDLE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-authorization-bundle-v1"
)
BUNDLE_SET_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-authorization-bundle-set-v1"
)
EXECUTION_SURFACE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-execution-surface-v3"
)
CALIBRATION_PACKAGE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-package-v2"
)
PORTABLE_PACKAGE_LAYOUT: Final = "PORTABLE_CANDIDATE_V1"
FOCUSED_PACKAGE_LAYOUT: Final = "FOCUSED_FIXTURE_V1"
OBSERVER_RESULT_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-observer-result-v1"
)

AUTHORITY_SCOPE: Final = "AB16_RESEARCH_ONLY"
STAGES: Final = frozenset(
    {"FULL_PREFLIGHT", "GATE_B_QUALIFICATION", "FORMAL_ORGANIC_ARM"}
)
WORKER_MODES: Final = frozenset(
    {"single-worker", "pytest-serial", "pytest-xdist-auto"}
)
SHA256_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
TOKEN_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{7,127}\Z")
SAMPLE_COUNT: Final = 3
FALSE_AUTHORIZATIONS: Final = {
    "formal_campaign_creation_authorized": False,
    "gate_b_approval_authorized": False,
    "organic_arm_launch_authorized": False,
    "profile_installation_authorized": False,
    "solver_run_authorized": False,
}


class CalibrationContractError(RuntimeError):
    """One calibration identity, comparison, or authority check failed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise CalibrationContractError(code, detail)


def canonical_json_bytes(value: object) -> bytes:
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


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def detached_identity(path: str, raw: bytes) -> dict[str, object]:
    absolute = Path(path)
    if not absolute.is_absolute():
        _fail("CALIBRATION_IDENTITY_INVALID", f"path is not absolute: {path!r}")
    return {
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _closed(value: object, fields: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        _fail("CALIBRATION_RECORD_INVALID", f"{label} field set drifted")
    return dict(value)


def _sha(value: object, label: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        _fail("CALIBRATION_IDENTITY_INVALID", f"{label} is not a SHA-256")
    return value


def _token(value: object, label: str) -> str:
    if type(value) is not str or TOKEN_RE.fullmatch(value) is None:
        _fail("CALIBRATION_RECORD_INVALID", f"{label} is malformed")
    return value


def _nonnegative(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(
            "CALIBRATION_MEASUREMENT_INVALID",
            f"{label} is not an exact nonnegative integer",
        )
    return value


def _identity(value: object, label: str) -> dict[str, object]:
    record = _closed(
        value,
        {"path", "sha256", "size_bytes"},
        f"{label} identity",
    )
    path = record["path"]
    if type(path) is not str or not Path(path).is_absolute():
        _fail(
            "CALIBRATION_IDENTITY_INVALID",
            f"{label} path is not absolute",
        )
    _sha(record["sha256"], f"{label} SHA-256")
    _nonnegative(record["size_bytes"], f"{label} size")
    return record


def _package_closure(
    value: object,
    *,
    launch_admissible: bool,
) -> dict[str, object]:
    record = _closed(
        value,
        {
            "host_runtime_content_sha256",
            "layout",
            "package_receipt_identity",
            "package_schema_version",
            "source_sets_sha256",
        },
        "calibration package closure",
    )
    if (
        record["layout"] not in {
            FOCUSED_PACKAGE_LAYOUT,
            PORTABLE_PACKAGE_LAYOUT,
        }
        or record["package_schema_version"] != CALIBRATION_PACKAGE_SCHEMA
        or (
            launch_admissible
            and record["layout"] != PORTABLE_PACKAGE_LAYOUT
        )
    ):
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "calibration package schema/layout/fidelity drifted",
        )
    receipt = _identity(
        record["package_receipt_identity"],
        "portable package receipt",
    )
    if Path(cast(str, receipt["path"])).name != "receipt.json":
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "portable package terminal receipt path is not fixed",
        )
    return {
        "host_runtime_content_sha256": _sha(
            record["host_runtime_content_sha256"],
            "portable host-runtime content digest",
        ),
        "layout": record["layout"],
        "package_receipt_identity": receipt,
        "package_schema_version": CALIBRATION_PACKAGE_SCHEMA,
        "source_sets_sha256": _sha(
            record["source_sets_sha256"],
            "portable source-set digest",
        ),
    }


def _positive_process_identity(value: object, label: str) -> dict[str, int]:
    record = _closed(value, {"pid", "starttime"}, label)
    pid = _nonnegative(record["pid"], f"{label} PID")
    starttime = _nonnegative(record["starttime"], f"{label} starttime")
    if pid == 0 or starttime == 0:
        _fail("CALIBRATION_SAMPLE_INVALID", f"{label} is malformed")
    return {"pid": pid, "starttime": starttime}


def _directory_identity(value: object, label: str) -> dict[str, object]:
    record = _closed(
        value,
        {"device", "inode", "mode", "path", "uid"},
        label,
    )
    for field in ("device", "inode", "mode", "uid"):
        _nonnegative(record[field], f"{label} {field}")
    if record["inode"] == 0:
        _fail("CALIBRATION_SAMPLE_INVALID", f"{label} inode is zero")
    path = record["path"]
    if type(path) is not str or not Path(path).is_absolute():
        _fail("CALIBRATION_SAMPLE_INVALID", f"{label} path is not absolute")
    return record


def _authorizations(value: object) -> dict[str, bool]:
    if type(value) is not dict or value != FALSE_AUTHORIZATIONS:
        _fail(
            "CALIBRATION_AUTHORITY_EXPANSION",
            "calibration record carries a launch or production authorization",
        )
    return dict(FALSE_AUTHORIZATIONS)


def _stage(value: object) -> str:
    if type(value) is not str or value not in STAGES:
        _fail("CALIBRATION_STAGE_INVALID", f"unknown stage: {value!r}")
    return value


def build_execution_surface(
    *,
    stage: str,
    command: Sequence[str],
    working_directory: str,
    test_inventory_count: int,
    test_inventory_sha256: str,
    xdist_available: bool,
    worker_mode: str,
    worker_count: int,
    member_identities: Mapping[str, Mapping[str, object]],
    control_plane_identities: Mapping[str, Mapping[str, object]],
    portable_package: Mapping[str, object],
    workload_fidelity_class: str = "UNSPECIFIED_LAUNCH_BLOCKED",
    launch_admissible: bool = False,
) -> dict[str, object]:
    """Build the byte-level execution fingerprint sampled by calibration.

    ``member_identities`` are bytes executed/read by the stage.
    ``control_plane_identities`` must include the installed profile,
    ``PROJECT_LOCK.md``, repository code-assets manifest, and every other byte
    whose value changes full discovery or stage branching.
    """

    checked_stage = _stage(stage)
    if (
        type(command) not in {list, tuple}
        or not command
        or any(type(item) is not str or not item for item in command)
    ):
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "execution command is not one nonempty string vector",
        )
    if (
        type(workload_fidelity_class) is not str
        or not workload_fidelity_class
        or type(launch_admissible) is not bool
    ):
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "workload fidelity declaration is malformed",
        )
    if (
        type(working_directory) is not str
        or not Path(working_directory).is_absolute()
        or str(Path(working_directory).absolute()) != working_directory
    ):
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "execution working directory is not one absolute lexical path",
        )
    count = _nonnegative(test_inventory_count, "test inventory count")
    inventory_sha = _sha(test_inventory_sha256, "test inventory SHA-256")
    if type(xdist_available) is not bool:
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "xdist availability is not boolean",
        )
    if worker_mode not in WORKER_MODES:
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            f"worker mode is unknown: {worker_mode!r}",
        )
    workers = _nonnegative(worker_count, "worker count")
    if workers < 1:
        _fail("CALIBRATION_FINGERPRINT_INVALID", "worker count must be positive")
    if worker_mode == "pytest-xdist-auto" and not xdist_available:
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "xdist-auto mode was declared while xdist is unavailable",
        )
    if worker_mode != "pytest-xdist-auto" and workers != 1:
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "serial/single-worker execution declared multiple workers",
        )
    if checked_stage == "FULL_PREFLIGHT":
        if count <= 0:
            _fail(
                "CALIBRATION_FINGERPRINT_INVALID",
                "full preflight lacks a measured test inventory",
            )
    elif count != 0 or inventory_sha != hashlib.sha256(b"").hexdigest():
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "non-pytest stage carries a test inventory",
        )
    members = {
        name: _identity(identity, f"execution member {name}")
        for name, identity in sorted(member_identities.items())
        if type(name) is str and name
    }
    controls = {
        name: _identity(identity, f"control-plane member {name}")
        for name, identity in sorted(control_plane_identities.items())
        if type(name) is str and name
    }
    if set(members) != set(member_identities) or set(controls) != set(
        control_plane_identities
    ):
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "execution/control member labels are malformed",
        )
    required_controls = {"code_assets", "profile", "project_lock"}
    if not required_controls <= set(controls):
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "execution surface omits a mandatory control-plane byte",
        )
    package = _package_closure(
        portable_package,
        launch_admissible=launch_admissible,
    )
    command_list = list(command)
    executable_role = next(
        (
            name
            for name, identity in {**members, **controls}.items()
            if identity["path"] == command_list[0]
        ),
        None,
    )
    if executable_role is None:
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "execution command executable is absent from the byte identity maps",
        )
    stable_surface = {
        "command": {
            "arguments": command_list[1:],
            "executable_role": executable_role,
        },
        "execution_member_content_identities": {
            name: {
                "sha256": identity["sha256"],
                "size_bytes": identity["size_bytes"],
            }
            for name, identity in members.items()
        },
        "portable_package": {
            "host_runtime_content_sha256": package[
                "host_runtime_content_sha256"
            ],
            "layout": package["layout"],
            "package_receipt_content_identity": {
                "sha256": cast(dict[str, object], package["package_receipt_identity"])[
                    "sha256"
                ],
                "size_bytes": cast(
                    dict[str, object],
                    package["package_receipt_identity"],
                )["size_bytes"],
            },
            "package_schema_version": package["package_schema_version"],
            "source_sets_sha256": package["source_sets_sha256"],
        },
        "schema_version": EXECUTION_SURFACE_SCHEMA,
        "stage": checked_stage,
        "test_inventory": {
            "collection_count": count,
            "collection_sha256": inventory_sha,
        },
        "worker": {
            "count": workers,
            "mode": worker_mode,
            "xdist_available": xdist_available,
        },
        "workload_fidelity": {
            "class": workload_fidelity_class,
            "launch_admissible": launch_admissible,
        },
        "working_directory_role": "repository-root",
    }
    site_receipt = {
        "command": command_list,
        "control_plane_identities": controls,
        "execution_member_identities": members,
        "portable_package": package,
        "working_directory": working_directory,
    }
    surface: dict[str, object] = {
        "command": command_list,
        "control_plane_identities": controls,
        "execution_member_identities": members,
        "portable_package": package,
        "execution_site_receipt_sha256": canonical_sha256(site_receipt),
        "schema_version": EXECUTION_SURFACE_SCHEMA,
        "stage": checked_stage,
        "test_inventory": {
            "collection_count": count,
            "collection_sha256": inventory_sha,
        },
        "worker": {
            "count": workers,
            "mode": worker_mode,
            "xdist_available": xdist_available,
        },
        "workload_fidelity": {
            "class": workload_fidelity_class,
            "launch_admissible": launch_admissible,
        },
        "working_directory": working_directory,
    }
    surface["execution_surface_sha256"] = canonical_sha256(stable_surface)
    return surface


def validate_execution_surface(value: object) -> dict[str, object]:
    record = _closed(
        value,
        {
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
        },
        "execution surface",
    )
    _sha(
        record["execution_surface_sha256"],
        "execution surface digest",
    )
    _sha(
        record["execution_site_receipt_sha256"],
        "execution site receipt digest",
    )
    inventory = _closed(
        record["test_inventory"],
        {"collection_count", "collection_sha256"},
        "test inventory",
    )
    worker = _closed(
        record["worker"],
        {"count", "mode", "xdist_available"},
        "worker fingerprint",
    )
    fidelity = _closed(
        record["workload_fidelity"],
        {"class", "launch_admissible"},
        "workload fidelity",
    )
    rebuilt = build_execution_surface(
        stage=_stage(record["stage"]),
        command=record["command"],  # type: ignore[arg-type]
        working_directory=cast(str, record["working_directory"]),
        test_inventory_count=_nonnegative(
            inventory["collection_count"],
            "test inventory count",
        ),
        test_inventory_sha256=_sha(
            inventory["collection_sha256"],
            "test inventory SHA-256",
        ),
        xdist_available=worker["xdist_available"],  # type: ignore[arg-type]
        worker_mode=worker["mode"],  # type: ignore[arg-type]
        worker_count=_nonnegative(worker["count"], "worker count"),
        member_identities=record["execution_member_identities"],  # type: ignore[arg-type]
        control_plane_identities=record["control_plane_identities"],  # type: ignore[arg-type]
        portable_package=record["portable_package"],  # type: ignore[arg-type]
        workload_fidelity_class=cast(str, fidelity["class"]),
        launch_admissible=cast(bool, fidelity["launch_admissible"]),
    )
    if rebuilt != record:
        _fail(
            "CALIBRATION_FINGERPRINT_INVALID",
            "execution surface canonical reconstruction drifted",
        )
    return rebuilt


def build_declaration(
    *,
    declaration_id: str,
    cohort_id: str,
    execution_surface: Mapping[str, object],
    harness_identity: Mapping[str, object],
    observer_identity: Mapping[str, object],
    installed_profile_identity: Mapping[str, object],
) -> dict[str, object]:
    surface = validate_execution_surface(execution_surface)
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "cohort_id": _token(cohort_id, "calibration cohort ID"),
        "declaration_id": _token(declaration_id, "calibration declaration ID"),
        "execution_surface": surface,
        "harness_identity": _identity(harness_identity, "calibration harness"),
        "installed_profile_identity": _identity(
            installed_profile_identity,
            "installed resource profile",
        ),
        "observer_identity": _identity(
            observer_identity,
            "persistent calibration observer",
        ),
        "required_sample_count": SAMPLE_COUNT,
        "schema_version": DECLARATION_SCHEMA,
        "stage": surface["stage"],
        "status": "DECLARED_NO_AUTHORITY",
    }


def validate_declaration(value: object) -> dict[str, object]:
    record = _closed(
        value,
        {
            "authority_scope",
            "authorizations",
            "cohort_id",
            "declaration_id",
            "execution_surface",
            "harness_identity",
            "installed_profile_identity",
            "observer_identity",
            "required_sample_count",
            "schema_version",
            "stage",
            "status",
        },
        "calibration declaration",
    )
    surface = validate_execution_surface(record["execution_surface"])
    rebuilt = build_declaration(
        declaration_id=_token(
            record["declaration_id"],
            "calibration declaration ID",
        ),
        cohort_id=_token(record["cohort_id"], "calibration cohort ID"),
        execution_surface=surface,
        harness_identity=_identity(record["harness_identity"], "harness"),
        observer_identity=_identity(record["observer_identity"], "observer"),
        installed_profile_identity=_identity(
            record["installed_profile_identity"],
            "installed profile",
        ),
    )
    if (
        record["schema_version"] != DECLARATION_SCHEMA
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["status"] != "DECLARED_NO_AUTHORITY"
        or record["required_sample_count"] != SAMPLE_COUNT
        or record["stage"] != surface["stage"]
    ):
        _fail(
            "CALIBRATION_DECLARATION_INVALID",
            "declaration scalar boundary drifted",
        )
    _authorizations(record["authorizations"])
    if rebuilt != record:
        _fail(
            "CALIBRATION_DECLARATION_INVALID",
            "declaration canonical reconstruction drifted",
        )
    return rebuilt


def build_sample(
    *,
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
    sample_id: str,
    observer_result: Mapping[str, object],
    observer_result_identity: Mapping[str, object],
    workload_process_identity: Mapping[str, object],
    workload_exit_code: int,
) -> dict[str, object]:
    checked = validate_declaration(declaration)
    observer_record = _closed(
        observer_result,
        {
            "authority_scope",
            "authorizations",
            "cgroup",
            "cgroup_limits",
            "disk",
            "memory_peak_bytes",
            "observer_process_identity",
            "sample_count",
            "schema_version",
            "status",
            "swap_peak_bytes",
        },
        "persistent observer result",
    )
    _authorizations(observer_record["authorizations"])
    if (
        observer_record["schema_version"] != OBSERVER_RESULT_SCHEMA
        or observer_record["authority_scope"] != AUTHORITY_SCOPE
        or observer_record["status"]
        != "PEAKS_CAPTURED_BEFORE_CGROUP_DISAPPEARANCE"
    ):
        _fail(
            "CALIBRATION_OBSERVER_RECEIPT_INVALID",
            "persistent observer result boundary drifted",
        )
    cgroup = _closed(
        observer_record["cgroup"],
        {
            "disappeared_after_peak_read",
            "identity",
            "peak_read_before_disappearance",
        },
        "persistent observer cgroup",
    )
    cgroup_identity = _directory_identity(
        cgroup["identity"],
        "persistent observer cgroup identity",
    )
    transient_cgroup = cgroup_identity["path"]
    if (
        type(transient_cgroup) is not str
        or not transient_cgroup.startswith("/")
        or transient_cgroup == "/"
        or ".." in Path(transient_cgroup).parts
    ):
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "sample transient cgroup path is invalid",
        )
    if (
        cgroup["disappeared_after_peak_read"] is not True
        or cgroup["peak_read_before_disappearance"] is not True
    ):
        _fail(
            "CALIBRATION_SAMPLE_UNCLOSED",
            "persistent observer did not close the transient cgroup",
        )
    disk = _closed(
        observer_record["disk"],
        {
            "after_bytes",
            "before_bytes",
            "cgroup_io",
            "growth_peak_bytes",
            "measurement_rule",
            "peak_bytes",
            "polling_growth_peak_bytes",
            "target_identity",
        },
        "persistent observer disk result",
    )
    disk_target_identity = _directory_identity(
        disk["target_identity"],
        "persistent observer disk target identity",
    )
    limits = _closed(
        observer_record["cgroup_limits"],
        {"memory.high", "memory.max", "memory.swap.max"},
        "persistent observer cgroup limits",
    )
    for name, value in limits.items():
        _nonnegative(value, f"persistent observer {name}")
    io_record = _closed(
        disk["cgroup_io"],
        {"rows_after", "wbytes_after", "wbytes_before", "wbytes_delta"},
        "persistent observer cgroup io",
    )
    for name in ("wbytes_after", "wbytes_before", "wbytes_delta"):
        _nonnegative(io_record[name], f"persistent observer io {name}")
    if (
        io_record["wbytes_delta"]
        != cast(int, io_record["wbytes_after"])
        - cast(int, io_record["wbytes_before"])
        or type(io_record["rows_after"]) is not list
        or disk["measurement_rule"]
        != "MAX_RETAINED_TREE_POLLING_AND_CGROUP_IO_WBYTES"
    ):
        _fail(
            "CALIBRATION_MEASUREMENT_INVALID",
            "persistent observer cgroup io/disk rule drifted",
        )
    workload = _positive_process_identity(
        workload_process_identity,
        "workload process identity",
    )
    observer = _positive_process_identity(
        observer_record["observer_process_identity"],
        "observer process identity",
    )
    if workload == observer:
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "workload cannot be its own persistent observer",
        )
    memory = _nonnegative(observer_record["memory_peak_bytes"], "memory peak")
    swap = _nonnegative(observer_record["swap_peak_bytes"], "swap peak")
    disk_before = _nonnegative(disk["before_bytes"], "disk before")
    disk_peak = _nonnegative(disk["peak_bytes"], "disk peak")
    disk_after = _nonnegative(disk["after_bytes"], "disk after")
    if disk_peak < max(disk_before, disk_after):
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "disk peak is below a boundary observation",
        )
    if _nonnegative(disk["growth_peak_bytes"], "disk growth peak") != (
        disk_peak - disk_before
    ):
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "persistent observer disk growth arithmetic drifted",
        )
    polling_growth = _nonnegative(
        disk["polling_growth_peak_bytes"],
        "disk polling growth peak",
    )
    if cast(int, disk["growth_peak_bytes"]) != max(
        polling_growth,
        cast(int, io_record["wbytes_delta"]),
    ):
        _fail(
            "CALIBRATION_MEASUREMENT_INVALID",
            "conservative disk growth is not max(retained polling, cgroup io)",
        )
    sample_count = _nonnegative(
        observer_record["sample_count"],
        "persistent observer sample count",
    )
    if sample_count < 2:
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "persistent observer did not capture boundary and final samples",
        )
    if type(workload_exit_code) is not int:
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "workload exit code is not an exact integer",
        )
    execution_surface = cast(
        Mapping[str, object],
        checked["execution_surface"],
    )
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "cgroup": {
            "identity": cgroup_identity,
            "disappeared_after_peak_read": True,
            "path": transient_cgroup,
            "peak_read_before_disappearance": True,
        },
        "declaration_identity": _identity(
            declaration_identity,
            "calibration declaration",
        ),
        "execution_surface_sha256": execution_surface["execution_surface_sha256"],
        "measurements": {
            "disk_after_bytes": disk_after,
            "disk_before_bytes": disk_before,
            "disk_growth_peak_bytes": disk_peak - disk_before,
            "disk_peak_bytes": disk_peak,
            "memory_peak_bytes": memory,
            "swap_peak_bytes": swap,
        },
        "measurement_source": {
            "disk_target_identity": disk_target_identity,
            "observer_result_identity": _identity(
                observer_result_identity,
                "persistent observer result",
            ),
            "sample_count": sample_count,
        },
        "observer_process_identity": observer,
        "sample_id": _token(sample_id, "calibration sample ID"),
        "schema_version": SAMPLE_SCHEMA,
        "stage": checked["stage"],
        "status": (
            "MEASURED_SUCCESS"
            if workload_exit_code == 0
            else "MEASURED_WORKLOAD_FAILURE"
        ),
        "workload_exit_code": workload_exit_code,
        "workload_process_identity": workload,
    }


def validate_sample(
    value: object,
    *,
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
) -> dict[str, object]:
    expected_fields = {
        "authority_scope",
        "authorizations",
        "cgroup",
        "declaration_identity",
        "execution_surface_sha256",
        "measurement_source",
        "measurements",
        "observer_process_identity",
        "sample_id",
        "schema_version",
        "stage",
        "status",
        "workload_exit_code",
        "workload_process_identity",
    }
    record = _closed(value, expected_fields, "calibration sample")
    checked_declaration = validate_declaration(declaration)
    if _identity(record["declaration_identity"], "sample declaration") != _identity(
        declaration_identity,
        "expected declaration",
    ):
        _fail(
            "CALIBRATION_SAMPLE_NONCOMPARABLE",
            "sample declaration identity drifted",
        )
    cgroup = _closed(
        record["cgroup"],
        {
            "disappeared_after_peak_read",
            "identity",
            "path",
            "peak_read_before_disappearance",
        },
        "sample cgroup",
    )
    declaration_surface = cast(
        Mapping[str, object],
        checked_declaration["execution_surface"],
    )
    if (
        cgroup["disappeared_after_peak_read"] is not True
        or cgroup["peak_read_before_disappearance"] is not True
    ):
        _fail(
            "CALIBRATION_SAMPLE_UNCLOSED",
            "persistent observer did not read the peak before cgroup disappearance",
        )
    cgroup_identity = _directory_identity(
        cgroup["identity"],
        "sample cgroup identity",
    )
    if cgroup["path"] != cgroup_identity["path"]:
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "sample cgroup path differs from its retained identity",
        )
    measurement_source = _closed(
        record["measurement_source"],
        {
            "disk_target_identity",
            "observer_result_identity",
            "sample_count",
        },
        "sample measurement source",
    )
    _directory_identity(
        measurement_source["disk_target_identity"],
        "sample disk target identity",
    )
    _identity(
        measurement_source["observer_result_identity"],
        "sample observer result",
    )
    if _nonnegative(
        measurement_source["sample_count"],
        "sample observer count",
    ) < 2:
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "sample observer count is too small",
        )
    measurements = _closed(
        record["measurements"],
        {
            "disk_after_bytes",
            "disk_before_bytes",
            "disk_growth_peak_bytes",
            "disk_peak_bytes",
            "memory_peak_bytes",
            "swap_peak_bytes",
        },
        "sample measurements",
    )
    before = _nonnegative(measurements["disk_before_bytes"], "disk before")
    peak = _nonnegative(measurements["disk_peak_bytes"], "disk peak")
    after = _nonnegative(measurements["disk_after_bytes"], "disk after")
    if (
        _nonnegative(measurements["disk_growth_peak_bytes"], "disk growth")
        != peak - before
        or peak < max(before, after)
    ):
        _fail(
            "CALIBRATION_MEASUREMENT_INVALID",
            "sample disk growth arithmetic drifted",
        )
    _nonnegative(measurements["memory_peak_bytes"], "memory peak")
    _nonnegative(measurements["swap_peak_bytes"], "swap peak")
    _authorizations(record["authorizations"])
    if (
        record["schema_version"] != SAMPLE_SCHEMA
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["stage"] != checked_declaration["stage"]
        or record["execution_surface_sha256"]
        != declaration_surface["execution_surface_sha256"]
        or record["status"] != "MEASURED_SUCCESS"
        or record["workload_exit_code"] != 0
    ):
        _fail(
            "CALIBRATION_SAMPLE_NONCOMPARABLE",
            "sample stage/surface/outcome is not comparable",
        )
    _token(record["sample_id"], "calibration sample ID")
    for label in ("observer_process_identity", "workload_process_identity"):
        _positive_process_identity(record[label], label)
    if record["observer_process_identity"] == record["workload_process_identity"]:
        _fail(
            "CALIBRATION_SAMPLE_INVALID",
            "sample observer collapsed into the workload",
        )
    return deepcopy(record)


def build_validation(
    *,
    sample: Mapping[str, object],
    sample_identity: Mapping[str, object],
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
    validator_identity: Mapping[str, object],
) -> dict[str, object]:
    checked_sample = validate_sample(
        sample,
        declaration=declaration,
        declaration_identity=declaration_identity,
    )
    checked_declaration = validate_declaration(declaration)
    validator = _identity(validator_identity, "calibration validator")
    if validator == checked_declaration["harness_identity"]:
        _fail(
            "CALIBRATION_VALIDATOR_NOT_INDEPENDENT",
            "executing harness cannot validate its own sample",
        )
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "conclusion": "ACCEPTED_COMPARABLE_SAMPLE",
        "declaration_identity": _identity(
            declaration_identity,
            "calibration declaration",
        ),
        "execution_surface_sha256": checked_sample[
            "execution_surface_sha256"
        ],
        "sample_identity": _identity(sample_identity, "calibration sample"),
        "sample_measurements": deepcopy(checked_sample["measurements"]),
        "schema_version": VALIDATION_SCHEMA,
        "stage": checked_sample["stage"],
        "validator_identity": validator,
    }


def validate_validation(
    value: object,
    *,
    sample: Mapping[str, object],
    sample_identity: Mapping[str, object],
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _closed(
        value,
        {
            "authority_scope",
            "authorizations",
            "conclusion",
            "declaration_identity",
            "execution_surface_sha256",
            "sample_identity",
            "sample_measurements",
            "schema_version",
            "stage",
            "validator_identity",
        },
        "calibration validation",
    )
    checked_sample = validate_sample(
        sample,
        declaration=declaration,
        declaration_identity=declaration_identity,
    )
    expected = build_validation(
        sample=checked_sample,
        sample_identity=sample_identity,
        declaration=declaration,
        declaration_identity=declaration_identity,
        validator_identity=_identity(record["validator_identity"], "validator"),
    )
    if record != expected:
        _fail(
            "CALIBRATION_VALIDATION_INVALID",
            "independent validation record drifted",
        )
    return expected


def aggregate_validations(
    *,
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
    accepted: Sequence[
        tuple[
            Mapping[str, object],
            Mapping[str, object],
            Mapping[str, object],
            Mapping[str, object],
        ]
    ],
    aggregator_identity: Mapping[str, object],
) -> dict[str, object]:
    """Aggregate exactly three independently accepted comparable samples.

    Each tuple is ``(sample, sample_identity, validation,
    validation_identity)``.
    """

    checked_declaration = validate_declaration(declaration)
    if len(accepted) != SAMPLE_COUNT:
        _fail(
            "CALIBRATION_COHORT_INCOMPLETE",
            f"expected {SAMPLE_COUNT} samples, received {len(accepted)}",
        )
    sample_ids: set[str] = set()
    sample_identity_shas: set[str] = set()
    cgroups: set[str] = set()
    validator_shas: set[str] = set()
    rows: list[dict[str, object]] = []
    maxima = {
        "disk_growth_peak_bytes": 0,
        "disk_peak_bytes": 0,
        "memory_peak_bytes": 0,
        "swap_peak_bytes": 0,
    }
    for index, (sample, sample_identity, validation, validation_identity) in enumerate(
        accepted
    ):
        checked_validation = validate_validation(
            validation,
            sample=sample,
            sample_identity=sample_identity,
            declaration=checked_declaration,
            declaration_identity=declaration_identity,
        )
        checked_sample = validate_sample(
            sample,
            declaration=checked_declaration,
            declaration_identity=declaration_identity,
        )
        sample_sha = _identity(
            sample_identity,
            f"sample {index}",
        )["sha256"]
        validation_id = _identity(
            validation_identity,
            f"validation {index}",
        )
        sample_id = str(checked_sample["sample_id"])
        sample_cgroup = cast(Mapping[str, object], checked_sample["cgroup"])
        validator_identity = cast(
            Mapping[str, object],
            checked_validation["validator_identity"],
        )
        cgroup = str(sample_cgroup["path"])
        validator_sha = str(validator_identity["sha256"])
        if (
            sample_id in sample_ids
            or sample_sha in sample_identity_shas
            or cgroup in cgroups
        ):
            _fail(
                "CALIBRATION_COHORT_FORGED",
                "sample ID, bytes, or transient cgroup was reused",
            )
        sample_ids.add(sample_id)
        sample_identity_shas.add(str(sample_sha))
        cgroups.add(cgroup)
        validator_shas.add(validator_sha)
        measurements = checked_validation["sample_measurements"]
        assert isinstance(measurements, dict)
        for field in maxima:
            maxima[field] = max(maxima[field], int(measurements[field]))
        rows.append(
            {
                "sample_id": sample_id,
                "sample_identity": _identity(sample_identity, f"sample {index}"),
                "validation_identity": validation_id,
                "validator_identity": checked_validation["validator_identity"],
            }
        )
    if not validator_shas:
        _fail(
            "CALIBRATION_COHORT_FORGED",
            "calibration cohort contains no independent validator",
        )
    aggregator = _identity(aggregator_identity, "calibration aggregator")
    if aggregator["sha256"] in validator_shas or aggregator == checked_declaration[
        "harness_identity"
    ]:
        _fail(
            "CALIBRATION_AGGREGATOR_NOT_INDEPENDENT",
            "aggregator collapsed into a sampler or validator",
        )
    declaration_surface = cast(
        Mapping[str, object],
        checked_declaration["execution_surface"],
    )
    aggregate: dict[str, object] = {
        "aggregator_identity": aggregator,
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "cohort": rows,
        "declaration_identity": _identity(
            declaration_identity,
            "calibration declaration",
        ),
        "execution_surface_sha256": declaration_surface["execution_surface_sha256"],
        "maxima": maxima,
        "sample_count": SAMPLE_COUNT,
        "schema_version": AGGREGATE_SCHEMA,
        "stage": checked_declaration["stage"],
        "status": "AGGREGATED_NO_SELF_AUTHORITY",
    }
    aggregate["aggregate_sha256"] = canonical_sha256(aggregate)
    return aggregate


def _installed_profile_workload_limits(
    value: object,
    *,
    expected_stage: str,
) -> dict[str, dict[str, object]]:
    """Recover workload allowances without folding host reserve into peaks."""

    if type(value) is not dict:
        _fail(
            "CALIBRATION_PROFILE_INVALID",
            "installed profile is not an object",
        )
    profile = cast(dict[str, object], value)
    if profile.get("stage") != expected_stage:
        _fail(
            "CALIBRATION_PROFILE_INVALID",
            "installed profile stage differs from the sampled stage",
        )
    raw_requirements = profile.get("requirements")
    if type(raw_requirements) is not dict or set(raw_requirements) != {
        "disk",
        "memory",
        "swap",
    }:
        _fail(
            "CALIBRATION_PROFILE_INVALID",
            "installed profile requirement set drifted",
        )

    checked: dict[str, dict[str, object]] = {}
    for dimension in ("disk", "memory", "swap"):
        raw = cast(dict[str, object], raw_requirements)[dimension]
        if type(raw) is not dict:
            _fail(
                "CALIBRATION_PROFILE_INVALID",
                f"installed {dimension} requirement is not an object",
            )
        requirement = cast(dict[str, object], raw)
        required = {
            "host_reserve_bytes",
            "minimum_available_bytes",
            "predicted_peak_bytes",
            "safety_margin_bytes",
        }
        if not required <= set(requirement):
            _fail(
                "CALIBRATION_PROFILE_INVALID",
                f"installed {dimension} requirement omits threshold fields",
            )
        predicted = _nonnegative(
            requirement["predicted_peak_bytes"],
            f"installed {dimension} predicted peak",
        )
        margin = _nonnegative(
            requirement["safety_margin_bytes"],
            f"installed {dimension} safety margin",
        )
        reserve = _nonnegative(
            requirement["host_reserve_bytes"],
            f"installed {dimension} host reserve",
        )
        minimum = _nonnegative(
            requirement["minimum_available_bytes"],
            f"installed {dimension} minimum",
        )
        rule = requirement.get("availability_rule", "INDEPENDENT_MINIMUM")
        if rule == "INDEPENDENT_MINIMUM":
            expected_minimum = predicted + margin + reserve
        elif rule == "COMBINED_RAM_LIMITED_SWAP":
            expected_minimum = 0
        else:
            _fail(
                "CALIBRATION_PROFILE_INVALID",
                f"installed {dimension} availability rule is unknown",
            )
        if minimum != expected_minimum:
            _fail(
                "CALIBRATION_PROFILE_INVALID",
                f"installed {dimension} threshold arithmetic drifted",
            )
        checked[dimension] = {
            "availability_rule": rule,
            "host_reserve_bytes": reserve,
            "minimum_available_bytes": minimum,
            "workload_allowance_bytes": predicted + margin,
        }
    return checked


def build_installed_profile_candidate(
    *,
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
    aggregate: Mapping[str, object],
    aggregate_identity: Mapping[str, object],
    installed_profile: Mapping[str, object],
    candidate_builder_identity: Mapping[str, object],
) -> dict[str, object]:
    """Nominate the already-installed profile; never rewrite it from samples."""

    checked_declaration = validate_declaration(declaration)
    declaration_surface = cast(
        Mapping[str, object],
        checked_declaration["execution_surface"],
    )
    if (
        type(aggregate) is not dict
        or aggregate.get("schema_version") != AGGREGATE_SCHEMA
        or aggregate.get("sample_count") != SAMPLE_COUNT
        or aggregate.get("stage") != checked_declaration["stage"]
        or aggregate.get("execution_surface_sha256")
        != declaration_surface["execution_surface_sha256"]
        or aggregate.get("status") != "AGGREGATED_NO_SELF_AUTHORITY"
    ):
        _fail(
            "CALIBRATION_AGGREGATE_INVALID",
            "profile candidate received a non-comparable aggregate",
        )
    aggregate_copy = dict(aggregate)
    digest = aggregate_copy.pop("aggregate_sha256", None)
    if _sha(digest, "aggregate SHA-256") != canonical_sha256(aggregate_copy):
        _fail(
            "CALIBRATION_AGGREGATE_INVALID",
            "aggregate canonical digest drifted",
        )
    profile_identity = cast(
        Mapping[str, object],
        checked_declaration["installed_profile_identity"],
    )
    surface_controls = declaration_surface["control_plane_identities"]
    assert isinstance(surface_controls, dict)
    if profile_identity != surface_controls["profile"]:
        _fail(
            "CALIBRATION_PROFILE_SELF_REFERENCE",
            "installed profile bytes differ from the sampled execution surface",
        )
    profile = dict(installed_profile)
    if canonical_sha256(profile) != profile_identity["sha256"]:
        _fail(
            "CALIBRATION_PROFILE_IDENTITY_INVALID",
            "installed profile content does not match its sampled identity",
        )
    limits = _installed_profile_workload_limits(
        profile,
        expected_stage=str(checked_declaration["stage"]),
    )
    maxima = cast(Mapping[str, object], aggregate["maxima"])
    observed_by_dimension = {
        "disk": _nonnegative(
            maxima.get("disk_growth_peak_bytes"),
            "aggregate disk growth peak",
        ),
        "memory": _nonnegative(
            maxima.get("memory_peak_bytes"),
            "aggregate memory peak",
        ),
        "swap": _nonnegative(
            maxima.get("swap_peak_bytes"),
            "aggregate swap peak",
        ),
    }
    coverage: dict[str, object] = {}
    for dimension, observed in observed_by_dimension.items():
        allowance = _nonnegative(
            limits[dimension]["workload_allowance_bytes"],
            f"installed {dimension} workload allowance",
        )
        if observed > allowance:
            _fail(
                "CALIBRATION_PROFILE_UNDERSIZED",
                (
                    f"{dimension}: observed={observed}, "
                    f"predicted_plus_safety={allowance}"
                ),
            )
        coverage[dimension] = {
            "host_reserve_bytes": limits[dimension]["host_reserve_bytes"],
            "observed_peak_bytes": observed,
            "predicted_plus_safety_bytes": allowance,
            "within_preinstalled_workload_allowance": True,
        }
    return {
        "aggregate_identity": _identity(
            aggregate_identity,
            "calibration aggregate",
        ),
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "candidate_builder_identity": _identity(
            candidate_builder_identity,
            "profile candidate builder",
        ),
        "coverage": coverage,
        "declaration_identity": _identity(
            declaration_identity,
            "calibration declaration",
        ),
        "execution_surface_sha256": declaration_surface["execution_surface_sha256"],
        "installed_profile_identity": profile_identity,
        "sample_count": SAMPLE_COUNT,
        "schema_version": PROFILE_CANDIDATE_SCHEMA,
        "stage": checked_declaration["stage"],
        "status": "INSTALLED_PROFILE_CANDIDATE_ONLY",
        "threshold_effect": {
            "may_change_sampled_profile": False,
            "may_lower_current_cohort_threshold": False,
            "profile_was_installed_before_sampling": True,
        },
    }


def build_outside_replay(
    *,
    profile_candidate: Mapping[str, object],
    profile_candidate_identity: Mapping[str, object],
    replay_tool_identity: Mapping[str, object],
    root_receipt_identity: Mapping[str, object],
    replay_slot: str,
) -> dict[str, object]:
    candidate = _closed(
        profile_candidate,
        {
            "aggregate_identity",
            "authority_scope",
            "authorizations",
            "candidate_builder_identity",
            "coverage",
            "declaration_identity",
            "execution_surface_sha256",
            "installed_profile_identity",
            "sample_count",
            "schema_version",
            "stage",
            "status",
            "threshold_effect",
        },
        "installed profile candidate",
    )
    _authorizations(candidate["authorizations"])
    if (
        candidate["schema_version"] != PROFILE_CANDIDATE_SCHEMA
        or candidate["authority_scope"] != AUTHORITY_SCOPE
        or candidate["status"] != "INSTALLED_PROFILE_CANDIDATE_ONLY"
        or candidate["sample_count"] != SAMPLE_COUNT
        or candidate["threshold_effect"]
        != {
            "may_change_sampled_profile": False,
            "may_lower_current_cohort_threshold": False,
            "profile_was_installed_before_sampling": True,
        }
    ):
        _fail(
            "CALIBRATION_PROFILE_CANDIDATE_INVALID",
            "profile candidate authority boundary drifted",
        )
    coverage = candidate["coverage"]
    if type(coverage) is not dict or set(coverage) != {
        "disk",
        "memory",
        "swap",
    }:
        _fail(
            "CALIBRATION_PROFILE_CANDIDATE_INVALID",
            "profile candidate coverage dimensions drifted",
        )
    for dimension, raw in cast(dict[str, object], coverage).items():
        checked = _closed(
            raw,
            {
                "host_reserve_bytes",
                "observed_peak_bytes",
                "predicted_plus_safety_bytes",
                "within_preinstalled_workload_allowance",
            },
            f"profile candidate {dimension} coverage",
        )
        observed = _nonnegative(
            checked["observed_peak_bytes"],
            f"profile candidate {dimension} observed peak",
        )
        allowance = _nonnegative(
            checked["predicted_plus_safety_bytes"],
            f"profile candidate {dimension} allowance",
        )
        _nonnegative(
            checked["host_reserve_bytes"],
            f"profile candidate {dimension} host reserve",
        )
        if (
            checked["within_preinstalled_workload_allowance"] is not True
            or observed > allowance
        ):
            _fail(
                "CALIBRATION_PROFILE_CANDIDATE_INVALID",
                f"profile candidate {dimension} coverage is false",
            )
    if replay_slot not in {"replay-a", "replay-b"}:
        _fail(
            "CALIBRATION_REPLAY_INVALID",
            "outside replay slot is not fixed",
        )
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "conclusion": "REPLAY_ACCEPTED_PROFILE_CANDIDATE",
        "execution_surface_sha256": _sha(
            candidate["execution_surface_sha256"],
            "candidate execution surface SHA-256",
        ),
        "profile_candidate_identity": _identity(
            profile_candidate_identity,
            "profile candidate",
        ),
        "replay_slot": replay_slot,
        "replay_tool_identity": _identity(
            replay_tool_identity,
            "outside replay tool",
        ),
        "root_receipt_identity": _identity(
            root_receipt_identity,
            "calibration root receipt",
        ),
        "schema_version": OUTSIDE_REPLAY_SCHEMA,
        "stage": _stage(candidate["stage"]),
        "status": "PASS_NO_LAUNCH_AUTHORITY",
    }


def validate_dual_outside_replay(
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    expected_fields = {
        "authority_scope",
        "authorizations",
        "conclusion",
        "execution_surface_sha256",
        "profile_candidate_identity",
        "replay_slot",
        "replay_tool_identity",
        "root_receipt_identity",
        "schema_version",
        "stage",
        "status",
    }
    records = [
        _closed(first, expected_fields, "outside replay A"),
        _closed(second, expected_fields, "outside replay B"),
    ]
    for record in records:
        _authorizations(record["authorizations"])
        if (
            record["schema_version"] != OUTSIDE_REPLAY_SCHEMA
            or record["authority_scope"] != AUTHORITY_SCOPE
            or record["conclusion"] != "REPLAY_ACCEPTED_PROFILE_CANDIDATE"
            or record["status"] != "PASS_NO_LAUNCH_AUTHORITY"
        ):
            _fail(
                "CALIBRATION_REPLAY_INVALID",
                "outside replay authority boundary drifted",
            )
        _identity(record["profile_candidate_identity"], "profile candidate")
        _identity(record["replay_tool_identity"], "replay tool")
        _identity(record["root_receipt_identity"], "calibration root receipt")
        _sha(
            record["execution_surface_sha256"],
            "replay execution surface",
        )
        _stage(record["stage"])
    if {record["replay_slot"] for record in records} != {"replay-a", "replay-b"}:
        _fail(
            "CALIBRATION_REPLAY_INVALID",
            "dual replay slots are not exact",
        )
    for field in (
        "execution_surface_sha256",
        "profile_candidate_identity",
        "root_receipt_identity",
        "stage",
    ):
        if records[0][field] != records[1][field]:
            _fail(
                "CALIBRATION_REPLAY_DIVERGED",
                f"dual replay {field} differs",
            )
    replay_a_identity = cast(
        Mapping[str, object],
        records[0]["replay_tool_identity"],
    )
    replay_b_identity = cast(
        Mapping[str, object],
        records[1]["replay_tool_identity"],
    )
    if replay_a_identity["sha256"] == replay_b_identity["sha256"]:
        _fail(
            "CALIBRATION_REPLAY_NOT_HETEROGENEOUS",
            "dual replay tools have the same byte identity",
        )
    return deepcopy(records[0]), deepcopy(records[1])


def _require_content_identity(
    value: object,
    *,
    content: object,
    label: str,
) -> dict[str, object]:
    identity = _identity(value, label)
    raw = canonical_json_bytes(content)
    if (
        identity["sha256"] != hashlib.sha256(raw).hexdigest()
        or identity["size_bytes"] != len(raw)
    ):
        _fail(
            "CALIBRATION_IDENTITY_INVALID",
            f"{label} identity does not match canonical content",
        )
    return identity


def build_calibration_authorization_bundle(
    *,
    declaration: Mapping[str, object],
    installed_profile: Mapping[str, object],
    aggregate: Mapping[str, object],
    aggregate_identity: Mapping[str, object],
    profile_candidate: Mapping[str, object],
    profile_candidate_identity: Mapping[str, object],
    samples: Sequence[Mapping[str, object]],
    primary_replay: Mapping[str, object],
    primary_replay_receipt_identity: Mapping[str, object],
    alternate_replay: Mapping[str, object],
    alternate_replay_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Join the accepted cohort without granting launch authority by itself."""

    checked_declaration = validate_declaration(declaration)
    profile_identity = _require_content_identity(
        checked_declaration["installed_profile_identity"],
        content=installed_profile,
        label="preinstalled profile",
    )
    if (
        type(aggregate) is not dict
        or aggregate.get("schema_version") != AGGREGATE_SCHEMA
        or aggregate.get("status") != "AGGREGATED_NO_SELF_AUTHORITY"
        or aggregate.get("sample_count") != SAMPLE_COUNT
    ):
        _fail(
            "CALIBRATION_AGGREGATE_INVALID",
            "authorization bundle aggregate is not accepted",
        )
    aggregate_body = dict(aggregate)
    aggregate_digest = aggregate_body.pop("aggregate_sha256", None)
    if aggregate_digest != canonical_sha256(aggregate_body):
        _fail(
            "CALIBRATION_AGGREGATE_INVALID",
            "authorization bundle aggregate digest drifted",
        )
    checked_aggregate_identity = _require_content_identity(
        aggregate_identity,
        content=aggregate,
        label="calibration aggregate",
    )
    candidate = _closed(
        profile_candidate,
        {
            "aggregate_identity",
            "authority_scope",
            "authorizations",
            "candidate_builder_identity",
            "coverage",
            "declaration_identity",
            "execution_surface_sha256",
            "installed_profile_identity",
            "sample_count",
            "schema_version",
            "stage",
            "status",
            "threshold_effect",
        },
        "profile candidate",
    )
    if (
        candidate["aggregate_identity"] != checked_aggregate_identity
        or candidate["installed_profile_identity"] != profile_identity
        or candidate["execution_surface_sha256"]
        != cast(
            Mapping[str, object],
            checked_declaration["execution_surface"],
        )["execution_surface_sha256"]
    ):
        _fail(
            "CALIBRATION_PROFILE_CANDIDATE_INVALID",
            "authorization bundle candidate binding drifted",
        )
    checked_candidate_identity = _require_content_identity(
        profile_candidate_identity,
        content=profile_candidate,
        label="profile candidate",
    )
    first, second = validate_dual_outside_replay(
        primary_replay,
        alternate_replay,
    )
    if (
        first["replay_slot"] != "replay-a"
        or second["replay_slot"] != "replay-b"
        or first["profile_candidate_identity"] != checked_candidate_identity
    ):
        _fail(
            "CALIBRATION_REPLAY_INVALID",
            "authorization bundle replay role/target drifted",
        )
    primary_receipt_identity = _require_content_identity(
        primary_replay_receipt_identity,
        content=first,
        label="primary outside replay receipt",
    )
    alternate_receipt_identity = _require_content_identity(
        alternate_replay_receipt_identity,
        content=second,
        label="alternate outside replay receipt",
    )

    raw_cohort = aggregate.get("cohort")
    if (
        type(raw_cohort) is not list
        or len(raw_cohort) != SAMPLE_COUNT
        or len(samples) != SAMPLE_COUNT
    ):
        _fail(
            "CALIBRATION_COHORT_INCOMPLETE",
            "authorization bundle lacks three aggregate/sample rows",
        )
    samples_by_id: dict[str, Mapping[str, object]] = {}
    for sample in samples:
        checked = validate_sample(
            sample,
            declaration=checked_declaration,
            declaration_identity=cast(
                Mapping[str, object],
                candidate["declaration_identity"],
            ),
        )
        sample_id = cast(str, checked["sample_id"])
        if sample_id in samples_by_id:
            _fail(
                "CALIBRATION_COHORT_FORGED",
                "authorization bundle repeats a sample ID",
            )
        samples_by_id[sample_id] = checked
    comparable: list[dict[str, object]] = []
    for index, raw in enumerate(cast(list[object], raw_cohort)):
        if (
            type(raw) is not dict
            or set(raw)
            != {
                "sample_id",
                "sample_identity",
                "validation_identity",
                "validator_identity",
            }
            or type(raw["sample_id"]) is not str
            or raw["sample_id"] not in samples_by_id
        ):
            _fail(
                "CALIBRATION_COHORT_FORGED",
                f"authorization bundle aggregate row {index} drifted",
            )
        sample = samples_by_id[cast(str, raw["sample_id"])]
        cgroup = cast(Mapping[str, object], sample["cgroup"])
        comparable.append(
            {
                "sample_id": raw["sample_id"],
                "sample_identity": _identity(
                    raw["sample_identity"],
                    f"sample {index}",
                ),
                "transient_cgroup": cgroup["path"],
                "validation_identity": _identity(
                    raw["validation_identity"],
                    f"validation {index}",
                ),
            }
        )
    profile_internal_sha = installed_profile.get("profile_sha256")
    if type(profile_internal_sha) is not str or SHA256_RE.fullmatch(
        profile_internal_sha
    ) is None:
        _fail(
            "CALIBRATION_PROFILE_INVALID",
            "preinstalled profile lacks its internal SHA-256",
        )
    surface = cast(
        Mapping[str, object],
        checked_declaration["execution_surface"],
    )
    return {
        "aggregate_identity": checked_aggregate_identity,
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "comparable_samples": comparable,
        "execution_surface": deepcopy(surface),
        "execution_surface_sha256": surface["execution_surface_sha256"],
        "outside_replays": {
            "alternate": {
                "receipt_identity": alternate_receipt_identity,
                "record": second,
            },
            "primary": {
                "receipt_identity": primary_receipt_identity,
                "record": first,
            },
        },
        "profile_candidate_binding": {
            "aggregate_identity": checked_aggregate_identity,
            "execution_surface_sha256": surface["execution_surface_sha256"],
            "identity": checked_candidate_identity,
            "installed_profile_identity": profile_identity,
        },
        "profile_identity": profile_identity,
        "profile_internal_sha256": profile_internal_sha,
        "schema_version": AUTHORIZATION_BUNDLE_SCHEMA,
        "stage": checked_declaration["stage"],
        "status": "ACCEPTED",
    }


def _validate_built_authorization_bundle(
    value: object,
    *,
    expected_stage: str,
) -> dict[str, object]:
    record = _closed(
        value,
        {
            "aggregate_identity",
            "authority_scope",
            "authorizations",
            "comparable_samples",
            "execution_surface",
            "execution_surface_sha256",
            "outside_replays",
            "profile_candidate_binding",
            "profile_identity",
            "profile_internal_sha256",
            "schema_version",
            "stage",
            "status",
        },
        f"{expected_stage} calibration authorization bundle",
    )
    if (
        record["schema_version"] != AUTHORIZATION_BUNDLE_SCHEMA
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["status"] != "ACCEPTED"
        or record["stage"] != expected_stage
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            f"{expected_stage} bundle discriminator or authority boundary drifted",
        )
    _authorizations(record["authorizations"])
    _identity(record["aggregate_identity"], f"{expected_stage} aggregate")
    _identity(record["profile_identity"], f"{expected_stage} profile")
    surface = validate_execution_surface(record["execution_surface"])
    if (
        surface["stage"] != expected_stage
        or surface["execution_surface_sha256"]
        != record["execution_surface_sha256"]
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            f"{expected_stage} execution surface binding drifted",
        )
    samples = record["comparable_samples"]
    if type(samples) is not list or len(samples) != SAMPLE_COUNT:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            f"{expected_stage} comparable sample set is incomplete",
        )
    return deepcopy(record)


def build_calibration_authorization_bundle_set(
    *,
    bundles: Mapping[str, Mapping[str, object]],
    detached_paths: Mapping[str, str],
) -> dict[str, object]:
    """Return exact three-stage canonical records plus their detached identities."""

    if set(bundles) != STAGES or set(detached_paths) != STAGES:
        _fail(
            "CALIBRATION_BUNDLE_SET_INCOMPLETE",
            "bundle/identity stage set is not the exact prospective three-stage set",
        )
    records: dict[str, dict[str, object]] = {}
    identities: dict[str, dict[str, object]] = {}
    paths: set[str] = set()
    for stage in sorted(STAGES):
        record = _validate_built_authorization_bundle(
            bundles[stage],
            expected_stage=stage,
        )
        path = detached_paths[stage]
        if (
            type(path) is not str
            or not Path(path).is_absolute()
            or str(Path(path).absolute()) != path
            or path in paths
        ):
            _fail(
                "CALIBRATION_BUNDLE_SET_INVALID",
                f"{stage} detached path is not unique and absolute",
            )
        paths.add(path)
        raw = canonical_json_bytes(record)
        identity = detached_identity(path, raw)
        records[stage] = {
            "identity": deepcopy(identity),
            "record": record,
        }
        identities[stage] = deepcopy(identity)
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "resource_calibration_authorization_bundles": records,
        "resource_calibration_bundle_identities": identities,
        "schema_version": BUNDLE_SET_SCHEMA,
        "stages": sorted(STAGES),
        "status": "ACCEPTED_NO_LAUNCH_AUTHORITY",
    }


def validate_calibration_authorization_bundle_set(
    value: object,
) -> dict[str, object]:
    record = _closed(
        value,
        {
            "authority_scope",
            "authorizations",
            "resource_calibration_authorization_bundles",
            "resource_calibration_bundle_identities",
            "schema_version",
            "stages",
            "status",
        },
        "calibration authorization bundle set",
    )
    if (
        record["schema_version"] != BUNDLE_SET_SCHEMA
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["status"] != "ACCEPTED_NO_LAUNCH_AUTHORITY"
        or record["stages"] != sorted(STAGES)
    ):
        _fail(
            "CALIBRATION_BUNDLE_SET_INVALID",
            "bundle-set discriminator or stage list drifted",
        )
    _authorizations(record["authorizations"])
    raw_bundles = record["resource_calibration_authorization_bundles"]
    raw_identities = record["resource_calibration_bundle_identities"]
    if (
        type(raw_bundles) is not dict
        or set(raw_bundles) != STAGES
        or type(raw_identities) is not dict
        or set(raw_identities) != STAGES
    ):
        _fail(
            "CALIBRATION_BUNDLE_SET_INCOMPLETE",
            "bundle-set maps do not contain exactly three stages",
        )
    paths: set[str] = set()
    for stage in sorted(STAGES):
        wrapper = _closed(
            cast(dict[str, object], raw_bundles)[stage],
            {"identity", "record"},
            f"{stage} bundle wrapper",
        )
        bundle = _validate_built_authorization_bundle(
            wrapper["record"],
            expected_stage=stage,
        )
        identity = _require_content_identity(
            wrapper["identity"],
            content=bundle,
            label=f"{stage} bundle",
        )
        if identity != cast(dict[str, object], raw_identities)[stage]:
            _fail(
                "CALIBRATION_BUNDLE_SET_INVALID",
                f"{stage} preregistered and verified identities differ",
            )
        if cast(str, identity["path"]) in paths:
            _fail(
                "CALIBRATION_BUNDLE_SET_INVALID",
                "bundle-set detached paths are not unique",
            )
        paths.add(cast(str, identity["path"]))
    return deepcopy(record)
