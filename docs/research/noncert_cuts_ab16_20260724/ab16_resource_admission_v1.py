#!/usr/bin/env python3
"""Stage-specific, research-only host admission for the AB16 authority chain.

Admission headroom and cgroup safety limits are deliberately separate:

* an admission profile estimates one stage's working set and adds an explicit
  safety margin plus a host reserve;
* the formal organic-arm cgroup retains its independently fixed
  ``MemoryHigh``, ``MemoryMax`` and ``MemorySwapMax`` safety ceilings.

Every current profile is conservative and temporary.  None is represented as
an empirical peak for its own stage.  The hash-bound source and the returned
receipt preserve that limitation until accepted peak receipts justify a new
profile version.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import NoReturn, cast


RESOURCE_ADMISSION_SCHEMA = "noncert-cuts-ab16-stage-resource-admission-v1"
PROFILE_SET_ID = "noncert-cuts-ab16-resource-profile-set-v1"
AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
FULL_PREFLIGHT = "FULL_PREFLIGHT"
GATE_B_QUALIFICATION = "GATE_B_QUALIFICATION"
FORMAL_ORGANIC_ARM = "FORMAL_ORGANIC_ARM"
GATE_B_LOCK_IDENTITY_FORMAT = "gate-b-retained-lock-v1"
FORMAL_LOCK_IDENTITY_FORMAT = "formal-pinned-host-lock-v1"

GIB = 1024**3
LOCK_PATHS = (
    "/tmp/zmd-pj-codex-heavy-validation.lock",
    "/run/user/1000/zmd_pj_prod_scale_solver.lock",
    "/run/user/1000/zmd-pj-prod-scale-solve.lock",
)
CONFLICT_PATTERNS = (
    "ab16_formal_campaign_v1.py",
    "--role outer-guardian",
    "cp_model_solver",
    "endfield",
    "gamescope",
    "organic_unit_orchestrator",
    "platformprocess",
    "preflight_gate.py",
    "proton",
    "pytest",
    "steam",
    "wine",
)
FALSE_AUTHORIZATIONS = {
    "formal_campaign_creation_authorized": False,
    "organic_arm_launch_authorized": False,
    "solver_run_authorized": False,
}
_OBSERVATION_KINDS_BY_STAGE = {
    FULL_PREFLIGHT: {
        "GATE_A_FULL_PREFLIGHT",
        "GATE_B_FINAL_FULL_PREFLIGHT",
    },
    GATE_B_QUALIFICATION: {
        "GATE_B_QUALIFICATION_PUBLICATION",
    },
    FORMAL_ORGANIC_ARM: {
        "FORMAL_INITIAL_POST_LOCK",
        "FORMAL_ORGANIC_ARM_PRELAUNCH",
        "FORMAL_OUTER_PRELAUNCH",
    },
}

_NOT_STAGE_MEASURED = "TEMPORARY_PROFILE_NOT_A_STAGE_PEAK_MEASUREMENT"
_NO_CGROUP_LIMITS = {
    "applies": False,
    "memory_high_bytes": 0,
    "memory_max_bytes": 0,
    "memory_swap_max_bytes": 0,
    "scope": "NOT_APPLICABLE",
}
_FORMAL_CGROUP_LIMITS = {
    "applies": True,
    "memory_high_bytes": 35 * GIB,
    "memory_max_bytes": 39 * GIB,
    "memory_swap_max_bytes": 16 * GIB,
    "scope": "ONE_SERIAL_ORGANIC_ARM_CGROUP",
}
_HISTORICAL_FULL_OBSERVATION = {
    "kind": "EXTERNAL_SAMPLER_NOT_RECEIPT_AUTHORITY",
    "measurements": {
        "minimum_disk_free_bytes": 28_302_282_752,
        "minimum_mem_available_bytes": 22_188_326_912,
        "minimum_swap_free_bytes": 50_168_647_680,
        "process_tree_peak_rss_bytes": 13_507_510_272,
        "sample_count": 218,
    },
    "source": "docs/research/noncert_cuts_ab16_20260724/03_execution_record.md",
    "suitability": "HETEROGENEOUS_HISTORICAL_FULL_PREFLIGHT_SCHEDULING_ONLY",
}
_HISTORICAL_FORMAL_PLANNING_PROXY = {
    "kind": "HETEROGENEOUS_PLANNING_PROXY_NOT_MEASUREMENT",
    "measurements": {
        "historical_planning_upper_bytes": 24 * GIB,
    },
    "source": "docs/research/noncert_cuts_ab16_20260724/README.md",
    "suitability": "PLANNING_UPPER_BOUND_ONLY_NOT_COMPARABLE_TO_ORGANIC_ARM",
}


def _canonical_sha256(value: Mapping[str, object]) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _exact_tree_equal(actual: object, expected: object) -> bool:
    """Compare JSON-shaped values without Python's bool/int numeric aliasing."""

    if type(actual) is not type(expected):
        return False
    if type(actual) is dict:
        actual_mapping = cast(dict[object, object], actual)
        expected_mapping = cast(dict[object, object], expected)
        return (
            set(actual_mapping) == set(expected_mapping)
            and all(
                _exact_tree_equal(actual_mapping[key], expected_mapping[key])
                for key in expected_mapping
            )
        )
    if type(actual) is list:
        actual_items = cast(list[object], actual)
        expected_items = cast(list[object], expected)
        return len(actual_items) == len(expected_items) and all(
            _exact_tree_equal(left, right)
            for left, right in zip(actual_items, expected_items, strict=True)
        )
    return bool(actual == expected)


def _validated_utc(value: object, label: str) -> str:
    if type(value) is not str or not value.endswith("Z"):
        _fail("RESOURCE_MEASUREMENT_UNTRUSTED", f"{label} is not a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        _fail("RESOURCE_MEASUREMENT_UNTRUSTED", f"{label} is malformed: {exc}")
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        _fail("RESOURCE_MEASUREMENT_UNTRUSTED", f"{label} is not UTC")
    return value


def _dimension(
    predicted_peak_bytes: int,
    safety_margin_bytes: int,
    host_reserve_bytes: int,
    *,
    basis_class: str,
    basis_detail: str,
) -> dict[str, object]:
    return {
        "basis_class": basis_class,
        "basis_detail": basis_detail,
        "host_reserve_bytes": host_reserve_bytes,
        "minimum_available_bytes": (
            predicted_peak_bytes + safety_margin_bytes + host_reserve_bytes
        ),
        "predicted_peak_bytes": predicted_peak_bytes,
        "safety_margin_bytes": safety_margin_bytes,
    }


def _basis(
    *,
    comparable_to_stage: bool,
    evidence_class: str,
    historical_observations: Sequence[Mapping[str, object]],
    prediction_method: str,
) -> dict[str, object]:
    return {
        "classification": "CONSERVATIVE_TEMPORARY",
        "comparable_to_stage": comparable_to_stage,
        "confidence": "LOW",
        "evidence_class": evidence_class,
        "historical_observations": [dict(item) for item in historical_observations],
        "prediction_method": prediction_method,
        "stage_peak_receipt_count": 0,
        "stage_peak_receipts": [],
        "warning": _NOT_STAGE_MEASURED,
    }


def _profile(
    *,
    profile_id: str,
    stage: str,
    basis: Mapping[str, object],
    memory: Mapping[str, object],
    swap: Mapping[str, object],
    disk: Mapping[str, object],
    runtime_safety_limits: Mapping[str, object],
) -> dict[str, object]:
    profile: dict[str, object] = {
        "basis": dict(basis),
        "execution": {
            "lock_paths": list(LOCK_PATHS),
            "same_uid_allowlist_identity_fields": ["pid", "starttime"],
            "same_uid_conflict_patterns": list(CONFLICT_PATTERNS),
            "same_uid_conflict_check_required": True,
            "single_worker_required": True,
        },
        "profile_id": profile_id,
        "profile_set_id": PROFILE_SET_ID,
        "requirements": {
            "disk": dict(disk),
            "memory": dict(memory),
            "swap": dict(swap),
        },
        "runtime_safety_limits": dict(runtime_safety_limits),
        "stage": stage,
    }
    profile["profile_sha256"] = _canonical_sha256(profile)
    return profile


RESOURCE_PROFILES: dict[str, dict[str, object]] = {
    FULL_PREFLIGHT: _profile(
        profile_id="ab16-full-preflight-conservative-temporary-v1",
        stage=FULL_PREFLIGHT,
        basis=_basis(
            comparable_to_stage=True,
            evidence_class="HISTORICAL_EXTERNAL_SAMPLER_SAME_STAGE_PROXY",
            historical_observations=(_HISTORICAL_FULL_OBSERVATION,),
            prediction_method=(
                "round the heterogeneous 13.51 GB historical sampled RSS peak "
                "up to 16 GiB; add 4 GiB uncertainty and retain 12 GiB for the host"
            ),
        ),
        memory=_dimension(
            16 * GIB,
            4 * GIB,
            12 * GIB,
            basis_class="HISTORICAL_EXTERNAL_SAMPLER_SAME_STAGE_PROXY",
            basis_detail="13.51 GB sampled process-tree RSS rounded up to 16 GiB",
        ),
        swap=_dimension(
            0,
            8 * GIB,
            8 * GIB,
            basis_class="INHERITED_CONSERVATIVE_POLICY_FLOOR",
            basis_detail="no trustworthy stage swap peak; retain the historical 16 GiB floor",
        ),
        disk=_dimension(
            6 * GIB,
            2 * GIB,
            8 * GIB,
            basis_class="INHERITED_CONSERVATIVE_POLICY_FLOOR",
            basis_detail="unmeasured retained growth uses the historical 16 GiB floor",
        ),
        runtime_safety_limits=_NO_CGROUP_LIMITS,
    ),
    GATE_B_QUALIFICATION: _profile(
        profile_id="ab16-gate-b-publication-conservative-temporary-v1",
        stage=GATE_B_QUALIFICATION,
        basis=_basis(
            comparable_to_stage=False,
            evidence_class="NO_STAGE_PEAK_EVIDENCE",
            historical_observations=(),
            prediction_method=(
                "no accepted Gate-B peak receipt exists; use 2 GiB provisional "
                "memory and disk working-set estimates, then retain the inherited "
                "36/16/16 GiB admission floors as explicit temporary uncertainty "
                "and host reserve"
            ),
        ),
        memory=_dimension(
            2 * GIB,
            22 * GIB,
            12 * GIB,
            basis_class="INHERITED_CONSERVATIVE_POLICY_FLOOR",
            basis_detail="no Gate-B peak receipt; retain the historical 36 GiB floor",
        ),
        swap=_dimension(
            0,
            8 * GIB,
            8 * GIB,
            basis_class="INHERITED_CONSERVATIVE_POLICY_FLOOR",
            basis_detail="no Gate-B swap peak receipt; retain the historical 16 GiB floor",
        ),
        disk=_dimension(
            2 * GIB,
            6 * GIB,
            8 * GIB,
            basis_class="INHERITED_CONSERVATIVE_POLICY_FLOOR",
            basis_detail="no Gate-B retained-growth receipt; retain the historical 16 GiB floor",
        ),
        runtime_safety_limits=_NO_CGROUP_LIMITS,
    ),
    FORMAL_ORGANIC_ARM: _profile(
        profile_id="ab16-formal-organic-arm-conservative-temporary-v1",
        stage=FORMAL_ORGANIC_ARM,
        basis=_basis(
            comparable_to_stage=False,
            evidence_class="HETEROGENEOUS_PLANNING_PROXY",
            historical_observations=(_HISTORICAL_FORMAL_PLANNING_PROXY,),
            prediction_method=(
                "no accepted organic-arm peak receipt exists; use the historical "
                "24 GiB planning upper bound for memory, add 4 GiB uncertainty, "
                "retain the inherited swap/disk floors, and assess MemoryMax "
                "capacity only in the separate hard-cap feasibility layer"
            ),
        ),
        memory=_dimension(
            24 * GIB,
            4 * GIB,
            8 * GIB,
            basis_class="HETEROGENEOUS_PLANNING_PROXY",
            basis_detail="historical 24 GiB planning upper bound, not an organic-arm peak",
        ),
        swap=_dimension(
            0,
            12 * GIB,
            4 * GIB,
            basis_class="INHERITED_CONSERVATIVE_POLICY_FLOOR",
            basis_detail="no organic-arm swap peak; retain the historical 16 GiB floor",
        ),
        disk=_dimension(
            2 * GIB,
            6 * GIB,
            8 * GIB,
            basis_class="INHERITED_CONSERVATIVE_POLICY_FLOOR",
            basis_detail="no organic-arm retained-growth receipt; retain the historical 16 GiB floor",
        ),
        runtime_safety_limits=_FORMAL_CGROUP_LIMITS,
    ),
}


class ResourceAdmissionError(RuntimeError):
    """One resource profile, observation, or retained-lock check failed closed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise ResourceAdmissionError(code, detail)


class HeldResourceLocks:
    """Own the exact three AB16 locks for one local resource-gated action."""

    _OWNERSHIP_TOKEN = object()

    def __init__(
        self,
        descriptors: Mapping[str, int],
        *,
        identity_format: str,
        _ownership_token: object,
    ) -> None:
        if _ownership_token is not self._OWNERSHIP_TOKEN:
            raise TypeError("HeldResourceLocks must be created by acquire() or adopt_owned()")
        self._descriptors = dict(descriptors)
        self._identity_format = identity_format
        self._released = False

    @property
    def released(self) -> bool:
        return self._released

    @staticmethod
    def _checked_identity_format(identity_format: str) -> str:
        if identity_format not in {
            GATE_B_LOCK_IDENTITY_FORMAT,
            FORMAL_LOCK_IDENTITY_FORMAT,
        }:
            _fail(
                "RESOURCE_LOCK_EVIDENCE_INVALID",
                f"unknown lock identity format {identity_format!r}",
            )
        return identity_format

    @staticmethod
    def _close_owned_descriptors(
        descriptors: Sequence[int],
        *,
        primary: BaseException | None,
        code: str,
        action: str,
    ) -> None:
        seen: set[int] = set()
        for descriptor in reversed(tuple(descriptors)):
            if descriptor in seen:
                continue
            seen.add(descriptor)
            try:
                os.close(descriptor)
            except BaseException as close_error:
                if primary is None:
                    if isinstance(close_error, OSError):
                        primary = ResourceAdmissionError(
                            code,
                            f"{action} descriptor {descriptor}: {close_error}",
                        )
                    else:
                        primary = close_error
                else:
                    primary.add_note(
                        f"{action} close failed for descriptor {descriptor}: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
        if primary is not None:
            raise primary

    @classmethod
    def acquire(cls, *, identity_format: str) -> HeldResourceLocks:
        checked_format = cls._checked_identity_format(identity_format)
        descriptors: dict[str, int] = {}
        try:
            for path in LOCK_PATHS:
                descriptor = os.open(
                    path,
                    os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600,
                )
                descriptors[path] = descriptor
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            primary: BaseException = exc
            if isinstance(exc, OSError):
                primary = ResourceAdmissionError(
                    "RESOURCE_LOCK_ACQUISITION_FAILED",
                    str(exc),
                )
            cls._close_owned_descriptors(
                tuple(descriptors.values()),
                primary=primary,
                code="RESOURCE_LOCK_ACQUISITION_FAILED",
                action="resource-lock acquisition cleanup",
            )
            raise AssertionError("unreachable")
        return cls.adopt_owned(
            descriptors,
            identity_format=checked_format,
        )

    @classmethod
    def adopt_owned(
        cls,
        descriptors: Mapping[str, int],
        *,
        identity_format: str,
    ) -> HeldResourceLocks:
        """Take ownership of exact duplicated lock FDs and validate their live lease.

        Ownership transfers at call entry.  Success leaves all descriptors owned
        by the returned lease; every failure closes each distinct valid input FD
        exactly once without closing the caller's original pre-dup descriptors.
        """

        try:
            items = list(descriptors.items())
        except BaseException:
            # A Mapping that cannot enumerate its values cannot provide a
            # complete close set, so it is outside this ownership API.
            raise
        owned = [
            descriptor
            for _path, descriptor in items
            if type(descriptor) is int and descriptor >= 0
        ]
        primary: BaseException | None = None
        checked_format = identity_format
        try:
            checked_format = cls._checked_identity_format(identity_format)
            if tuple(path for path, _descriptor in items) != LOCK_PATHS:
                _fail(
                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                    "owned lock descriptor paths/order drifted",
                )
            if any(type(descriptor) is not int or descriptor < 0 for _path, descriptor in items):
                _fail(
                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                    "owned lock descriptor is not an exact nonnegative integer",
                )
            if len(set(owned)) != len(owned):
                _fail(
                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                    "owned lock descriptors are duplicated",
                )
            lease = cls(
                dict(items),
                identity_format=checked_format,
                _ownership_token=cls._OWNERSHIP_TOKEN,
            )
            lease.identities()
            return lease
        except BaseException as exc:
            primary = exc
        cls._close_owned_descriptors(
            owned,
            primary=primary,
            code="RESOURCE_LOCK_EVIDENCE_INVALID",
            action="owned resource-lock adoption cleanup",
        )
        raise AssertionError("unreachable")

    def identities(self) -> list[dict[str, object]]:
        if self._released or set(self._descriptors) != set(LOCK_PATHS):
            _fail("RESOURCE_LOCK_EVIDENCE_INVALID", "the exact three-lock lease is not live")
        result: list[dict[str, object]] = []
        expected_signatures: dict[str, tuple[int, int, int, int, int]] = {}
        for path in LOCK_PATHS:
            descriptor = self._descriptors[path]
            try:
                opened = os.fstat(descriptor)
                named = os.stat(path, follow_symlinks=False)
            except OSError as exc:
                _fail("RESOURCE_LOCK_EVIDENCE_INVALID", f"{path}: {exc}")
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) != 0o600
                or opened.st_nlink != 1
                or _lock_signature(named) != _lock_signature(opened)
            ):
                _fail("RESOURCE_LOCK_EVIDENCE_INVALID", f"{path} identity drifted")
            expected_signature = _lock_signature(opened)
            probe: int | None = None
            primary: BaseException | None = None
            try:
                probe = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
                probed = os.fstat(probe)
                if _lock_signature(probed) != expected_signature:
                    _fail(
                        "RESOURCE_LOCK_EVIDENCE_INVALID",
                        f"{path} probe identity drifted",
                    )
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    _fail("RESOURCE_LOCK_EVIDENCE_INVALID", f"{path} is not exclusively held")
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    _fail(
                        "RESOURCE_LOCK_EVIDENCE_INVALID",
                        f"{path} descriptor does not own the retained lock: {exc}",
                    )
            except ResourceAdmissionError as exc:
                primary = exc
            except OSError as exc:
                primary = ResourceAdmissionError(
                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                    f"{path} probe failed: {exc}",
                )
            except BaseException as exc:
                primary = exc
            finally:
                if probe is not None:
                    try:
                        os.close(probe)
                    except BaseException as close_error:
                        if primary is None:
                            if isinstance(close_error, OSError):
                                primary = ResourceAdmissionError(
                                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                                    f"{path} probe close failed: {close_error}",
                                )
                            else:
                                primary = close_error
                        else:
                            primary.add_note(
                                f"resource-lock probe close failed for {path}: "
                                f"{type(close_error).__name__}: {close_error}"
                            )
            if primary is not None:
                raise primary
            expected_signatures[path] = expected_signature
            record: dict[str, object] = {
                "device": opened.st_dev,
                "inode": opened.st_ino,
                "path": path,
                "uid": opened.st_uid,
            }
            if self._identity_format == GATE_B_LOCK_IDENTITY_FORMAT:
                record.update({"mode": 0o600, "nlink": 1})
            result.append(record)
        for path in LOCK_PATHS:
            try:
                final_named = os.stat(path, follow_symlinks=False)
            except OSError as exc:
                _fail("RESOURCE_LOCK_EVIDENCE_INVALID", f"{path} final name rejoin failed: {exc}")
            if _lock_signature(final_named) != expected_signatures[path]:
                _fail(
                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                    f"{path} final name identity drifted",
                )
        return _validate_lock_identities(
            result,
            identity_format=self._identity_format,
        )

    def release_once(self) -> list[dict[str, object]]:
        if self._released:
            _fail("RESOURCE_LOCK_RELEASE_FAILED", "resource locks were already released")
        primary: BaseException | None = None
        identities: list[dict[str, object]] = []
        try:
            identities = self.identities()
        except BaseException as exc:
            primary = exc
        self._released = True
        descriptors: list[int] = []
        for path in reversed(LOCK_PATHS):
            descriptor = self._descriptors.pop(path, None)
            if descriptor is None:
                continue
            descriptors.append(descriptor)
        self._close_owned_descriptors(
            descriptors,
            primary=primary,
            code="RESOURCE_LOCK_RELEASE_FAILED",
            action="resource-lock release",
        )
        return identities


def _lock_signature(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_nlink,
    )


def _validated_observation_context(
    value: object,
    *,
    stage: str,
    disk_path: Path | str | None,
) -> dict[str, object]:
    expected = {
        "authority_id",
        "disk_path",
        "kind",
        "ordinal",
        "scope_id",
        "sequence",
        "slot",
        "target",
    }
    if type(value) is not dict or set(value) != expected:
        _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", "observation context fields drifted")
    for field in ("authority_id", "scope_id"):
        item = value[field]
        if (
            type(item) is not str
            or len(item) != 64
            or any(character not in "0123456789abcdef" for character in item)
        ):
            _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", f"{field} is not a SHA-256")
    for field in ("disk_path", "kind", "slot", "target"):
        if type(value[field]) is not str:
            _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", f"{field} is malformed")
    if not value["kind"] or not value["target"]:
        _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", "observation context text is absent")
    for field in ("ordinal", "sequence"):
        if type(value[field]) is not int or value[field] < 0:
            _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", f"{field} is malformed")
    kind = value["kind"]
    if kind not in _OBSERVATION_KINDS_BY_STAGE.get(stage, set()):
        _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", f"{kind!r} does not match {stage}")
    if kind == "FORMAL_ORGANIC_ARM_PRELAUNCH":
        if (
            not value["slot"]
            or not 1 <= value["ordinal"] <= 16
            or value["sequence"] != value["ordinal"] + 1
        ):
            _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", "formal arm order drifted")
    elif value["slot"] or value["ordinal"] != 0:
        _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", f"{kind} slot/ordinal drifted")
    expected_sequence = {
        "FORMAL_INITIAL_POST_LOCK": 0,
        "FORMAL_OUTER_PRELAUNCH": 1,
        "GATE_A_FULL_PREFLIGHT": 1,
        "GATE_B_FINAL_FULL_PREFLIGHT": 1,
        "GATE_B_QUALIFICATION_PUBLICATION": 2,
    }.get(kind)
    if expected_sequence is not None and value["sequence"] != expected_sequence:
        _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", f"{kind} sequence drifted")
    absolute_disk_path = str(Path(value["disk_path"]).absolute())
    if value["disk_path"] != absolute_disk_path:
        _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", "disk path is not absolute")
    if disk_path is not None and value["disk_path"] != str(Path(disk_path).absolute()):
        _fail("RESOURCE_OBSERVATION_CONTEXT_INVALID", "disk path differs from measured target")
    return dict(value)


class _OwnedDirectoryDescriptor:
    """Own one directory descriptor until close, including exceptional paths."""

    __slots__ = ("_descriptor",)

    def __init__(self) -> None:
        self._descriptor: int | None = None

    @property
    def descriptor(self) -> int:
        if self._descriptor is None:
            raise RuntimeError("directory descriptor ownership is absent")
        return self._descriptor

    @property
    def owned(self) -> bool:
        return self._descriptor is not None

    def acquire(self, descriptor: int) -> None:
        if self._descriptor is not None:
            raise RuntimeError("directory descriptor ownership is already present")
        self._descriptor = descriptor

    def close(self) -> BaseException | None:
        descriptor = self.descriptor
        self._descriptor = None
        try:
            os.close(descriptor)
        except BaseException as exc:
            return exc
        return None


def _directory_signature(value: os.stat_result) -> tuple[int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
    )


def _close_directory_descriptors(
    owners: Sequence[_OwnedDirectoryDescriptor],
    *,
    primary: BaseException | None,
) -> BaseException | None:
    for owner in reversed(tuple(owners)):
        if not owner.owned:
            continue
        close_error = owner.close()
        if close_error is None:
            continue
        if primary is None:
            if isinstance(close_error, OSError):
                primary = ResourceAdmissionError(
                    "RESOURCE_MEASUREMENT_UNAVAILABLE",
                    f"disk target descriptor close failed: {close_error}",
                )
            else:
                primary = close_error
        else:
            primary.add_note(
                "disk target descriptor close failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
    return primary


def _open_absolute_directory_chain(
    path: Path | str,
) -> tuple[Path, tuple[_OwnedDirectoryDescriptor, ...], tuple[tuple[int, int, int, int], ...]]:
    """Open an absolute directory from trusted ``/`` with no followed component."""

    target = Path(os.path.abspath(os.fspath(path)))
    if not target.is_absolute() or target.anchor != "/":
        _fail("RESOURCE_MEASUREMENT_UNTRUSTED", "disk target is not an absolute Linux path")
    required_flags = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    if any(not hasattr(os, name) for name in required_flags):
        _fail(
            "RESOURCE_MEASUREMENT_UNAVAILABLE",
            "descriptor-relative no-follow directory opening is unsupported",
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    owners: list[_OwnedDirectoryDescriptor] = []
    signatures: list[tuple[int, int, int, int]] = []
    try:
        root = _OwnedDirectoryDescriptor()
        owners.append(root)
        root.acquire(os.open("/", flags))
        opened = os.fstat(root.descriptor)
        if not stat.S_ISDIR(opened.st_mode):
            _fail("RESOURCE_MEASUREMENT_UNTRUSTED", "trusted root is not one directory")
        signatures.append(_directory_signature(opened))
        for component in target.parts[1:]:
            owner = _OwnedDirectoryDescriptor()
            owners.append(owner)
            owner.acquire(os.open(component, flags, dir_fd=owners[-2].descriptor))
            opened = os.fstat(owner.descriptor)
            if not stat.S_ISDIR(opened.st_mode):
                _fail(
                    "RESOURCE_MEASUREMENT_UNTRUSTED",
                    f"disk target component {component!r} is not one directory",
                )
            signatures.append(_directory_signature(opened))
    except BaseException as exc:
        primary: BaseException = exc
        if isinstance(exc, OSError):
            primary = ResourceAdmissionError(
                "RESOURCE_MEASUREMENT_UNAVAILABLE",
                f"disk target {target}: {exc}",
            )
        closed_primary = _close_directory_descriptors(owners, primary=primary)
        assert closed_primary is not None
        primary = closed_primary
        if primary is exc:
            raise
        raise primary from exc
    return target, tuple(owners), tuple(signatures)


def _measure_disk_target(
    path: Path | str,
    *,
    disk_free: int | None,
) -> tuple[int, dict[str, object]]:
    """Measure and rejoin one retained disk target without pathname TOCTOU."""

    retained: tuple[_OwnedDirectoryDescriptor, ...] = ()
    rejoined: tuple[_OwnedDirectoryDescriptor, ...] = ()
    primary: BaseException | None = None
    result: tuple[int, dict[str, object]] | None = None
    caught: BaseException | None = None
    try:
        target, retained, retained_signatures = _open_absolute_directory_chain(path)
        target_descriptor = retained[-1].descriptor
        before = os.fstat(target_descriptor)
        filesystem = os.fstatvfs(target_descriptor)
        after = os.fstat(target_descriptor)
        if (
            not stat.S_ISDIR(before.st_mode)
            or _directory_signature(before) != _directory_signature(after)
            or _directory_signature(after) != retained_signatures[-1]
        ):
            _fail(
                "RESOURCE_MEASUREMENT_UNTRUSTED",
                "retained disk target identity drifted during measurement",
            )
        measured_free = filesystem.f_bavail * filesystem.f_frsize
        observed_disk = measured_free if disk_free is None else disk_free
        disk_available = _measurement(observed_disk, "disk free")

        rejoined_target, rejoined, rejoined_signatures = _open_absolute_directory_chain(
            target
        )
        retained_final = os.fstat(target_descriptor)
        rejoined_final = os.fstat(rejoined[-1].descriptor)
        if (
            rejoined_target != target
            or retained_signatures != rejoined_signatures
            or _directory_signature(retained_final) != retained_signatures[-1]
            or _directory_signature(rejoined_final) != retained_signatures[-1]
        ):
            _fail(
                "RESOURCE_MEASUREMENT_UNTRUSTED",
                "disk target absolute-path identity changed after measurement",
            )
        result = (
            disk_available,
            {
                "device": retained_final.st_dev,
                "inode": retained_final.st_ino,
                "mode": stat.S_IMODE(retained_final.st_mode),
                "path": str(target),
                "type": "directory",
                "uid": retained_final.st_uid,
            },
        )
    except BaseException as exc:
        caught = exc
        primary = exc
        if isinstance(exc, OSError):
            primary = ResourceAdmissionError(
                "RESOURCE_MEASUREMENT_UNAVAILABLE",
                f"disk target measurement: {exc}",
            )
    primary = _close_directory_descriptors(rejoined, primary=primary)
    primary = _close_directory_descriptors(retained, primary=primary)
    if primary is not None:
        if caught is not None and primary is not caught:
            raise primary from caught
        raise primary
    if result is None:
        raise AssertionError("disk measurement completed without a result")
    return result


def _exact_nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} is not an exact nonnegative integer")
    return value


def _validate_dimension(value: object, label: str) -> dict[str, object]:
    expected = {
        "basis_class",
        "basis_detail",
        "host_reserve_bytes",
        "minimum_available_bytes",
        "predicted_peak_bytes",
        "safety_margin_bytes",
    }
    if type(value) is not dict or set(value) != expected:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} field set drifted")
    if (
        type(value["basis_class"]) is not str
        or not value["basis_class"]
        or type(value["basis_detail"]) is not str
        or not value["basis_detail"]
    ):
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} basis is malformed")
    checked = {
        field: _exact_nonnegative_int(value[field], f"{label}.{field}")
        for field in (
            "host_reserve_bytes",
            "minimum_available_bytes",
            "predicted_peak_bytes",
            "safety_margin_bytes",
        )
    }
    if checked["minimum_available_bytes"] != (
        checked["predicted_peak_bytes"]
        + checked["safety_margin_bytes"]
        + checked["host_reserve_bytes"]
    ):
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} arithmetic does not close")
    return {
        "basis_class": value["basis_class"],
        "basis_detail": value["basis_detail"],
        **checked,
    }


def _validate_basis(value: object, label: str) -> dict[str, object]:
    expected = {
        "classification",
        "comparable_to_stage",
        "confidence",
        "evidence_class",
        "historical_observations",
        "prediction_method",
        "stage_peak_receipt_count",
        "stage_peak_receipts",
        "warning",
    }
    if type(value) is not dict or set(value) != expected:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} field set drifted")
    if (
        value["classification"] != "CONSERVATIVE_TEMPORARY"
        or type(value["comparable_to_stage"]) is not bool
        or value["confidence"] != "LOW"
        or type(value["evidence_class"]) is not str
        or not value["evidence_class"]
        or type(value["stage_peak_receipt_count"]) is not int
        or value["stage_peak_receipt_count"] != 0
        or type(value["stage_peak_receipts"]) is not list
        or value["stage_peak_receipts"]
        or value["warning"] != _NOT_STAGE_MEASURED
        or type(value["prediction_method"]) is not str
        or not value["prediction_method"]
        or type(value["historical_observations"]) is not list
    ):
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} is not an honest temporary basis")
    observations: list[dict[str, object]] = []
    for index, item in enumerate(value["historical_observations"]):
        item_label = f"{label}.historical_observations[{index}]"
        if type(item) is not dict or set(item) != {
            "kind",
            "measurements",
            "source",
            "suitability",
        }:
            _fail("RESOURCE_PROFILE_UNTRUSTED", f"{item_label} field set drifted")
        if any(type(item[field]) is not str or not item[field] for field in ("kind", "source", "suitability")):
            _fail("RESOURCE_PROFILE_UNTRUSTED", f"{item_label} text is malformed")
        measurements = item["measurements"]
        if type(measurements) is not dict or any(
            type(key) is not str
            or not key
            or type(measurement) is not int
            or measurement < 0
            for key, measurement in measurements.items()
        ):
            _fail("RESOURCE_PROFILE_UNTRUSTED", f"{item_label} measurements are malformed")
        observations.append(
            {
                "kind": item["kind"],
                "measurements": dict(measurements),
                "source": item["source"],
                "suitability": item["suitability"],
            }
        )
    return {
        "classification": value["classification"],
        "comparable_to_stage": value["comparable_to_stage"],
        "confidence": value["confidence"],
        "evidence_class": value["evidence_class"],
        "historical_observations": observations,
        "prediction_method": value["prediction_method"],
        "stage_peak_receipt_count": 0,
        "stage_peak_receipts": [],
        "warning": value["warning"],
    }


def _validate_runtime_limits(value: object, label: str) -> dict[str, object]:
    expected = {
        "applies",
        "memory_high_bytes",
        "memory_max_bytes",
        "memory_swap_max_bytes",
        "scope",
    }
    if type(value) is not dict or set(value) != expected:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} field set drifted")
    if type(value["applies"]) is not bool or type(value["scope"]) is not str:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} applicability is malformed")
    memory_high_bytes = _exact_nonnegative_int(
        value["memory_high_bytes"], f"{label}.memory_high_bytes"
    )
    memory_max_bytes = _exact_nonnegative_int(
        value["memory_max_bytes"], f"{label}.memory_max_bytes"
    )
    memory_swap_max_bytes = _exact_nonnegative_int(
        value["memory_swap_max_bytes"], f"{label}.memory_swap_max_bytes"
    )
    result: dict[str, object] = {
        "applies": value["applies"],
        "memory_high_bytes": memory_high_bytes,
        "memory_max_bytes": memory_max_bytes,
        "memory_swap_max_bytes": memory_swap_max_bytes,
        "scope": value["scope"],
    }
    if result["applies"] is False:
        if result != _NO_CGROUP_LIMITS:
            _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} non-applicable values drifted")
    elif (
        result["scope"] != "ONE_SERIAL_ORGANIC_ARM_CGROUP"
        or memory_high_bytes <= 0
        or memory_max_bytes < memory_high_bytes
        or memory_swap_max_bytes <= 0
    ):
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} formal safety limits are malformed")
    return result


def _validated_profile(stage: str) -> dict[str, object]:
    if type(stage) is not str or stage not in RESOURCE_PROFILES:
        _fail("RESOURCE_PROFILE_UNKNOWN", f"unknown AB16 resource stage {stage!r}")
    value = deepcopy(RESOURCE_PROFILES[stage])
    expected = {
        "basis",
        "execution",
        "profile_id",
        "profile_sha256",
        "profile_set_id",
        "requirements",
        "runtime_safety_limits",
        "stage",
    }
    if type(value) is not dict or set(value) != expected:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} profile field set drifted")
    if (
        value["stage"] != stage
        or value["profile_set_id"] != PROFILE_SET_ID
        or type(value["profile_id"]) is not str
        or not value["profile_id"]
        or type(value["profile_sha256"]) is not str
        or len(value["profile_sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in value["profile_sha256"])
    ):
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} profile identity drifted")
    unhashed_profile = dict(value)
    recorded_profile_sha256 = unhashed_profile.pop("profile_sha256")
    if _canonical_sha256(unhashed_profile) != recorded_profile_sha256:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} profile SHA-256 drifted")
    execution = value["execution"]
    if type(execution) is not dict or not _exact_tree_equal(
        execution,
        {
            "lock_paths": list(LOCK_PATHS),
            "same_uid_allowlist_identity_fields": ["pid", "starttime"],
            "same_uid_conflict_patterns": list(CONFLICT_PATTERNS),
            "same_uid_conflict_check_required": True,
            "single_worker_required": True,
        },
    ):
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} execution constraints drifted")
    requirements = value["requirements"]
    if type(requirements) is not dict or set(requirements) != {"disk", "memory", "swap"}:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} requirement set drifted")
    checked_requirements: dict[str, dict[str, object]] = {
        dimension: _validate_dimension(requirements[dimension], f"{stage}.{dimension}")
        for dimension in ("disk", "memory", "swap")
    }
    limits = _validate_runtime_limits(
        value["runtime_safety_limits"],
        f"{stage}.runtime_safety_limits",
    )
    if stage == FORMAL_ORGANIC_ARM:
        if limits != _FORMAL_CGROUP_LIMITS:
            _fail("RESOURCE_PROFILE_UNTRUSTED", "formal cgroup safety limits drifted")
        planned_memory = _exact_nonnegative_int(
            checked_requirements["memory"]["predicted_peak_bytes"],
            "formal predicted memory",
        ) + _exact_nonnegative_int(
            checked_requirements["memory"]["safety_margin_bytes"],
            "formal memory safety margin",
        )
        memory_high = _exact_nonnegative_int(
            limits["memory_high_bytes"],
            "formal MemoryHigh",
        )
        if planned_memory > memory_high:
            _fail("RESOURCE_PROFILE_UNTRUSTED", "formal planned memory exceeds MemoryHigh")
    elif limits != _NO_CGROUP_LIMITS:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} unexpectedly carries cgroup limits")
    return {
        "basis": _validate_basis(value["basis"], f"{stage}.basis"),
        "execution": dict(execution),
        "profile_id": value["profile_id"],
        "profile_sha256": value["profile_sha256"],
        "profile_set_id": value["profile_set_id"],
        "requirements": checked_requirements,
        "runtime_safety_limits": limits,
        "stage": stage,
    }


def _meminfo() -> dict[str, int]:
    try:
        raw = Path("/proc/meminfo").read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        _fail("RESOURCE_MEASUREMENT_UNAVAILABLE", f"/proc/meminfo: {exc}")
    result: dict[str, int] = {}
    for line in raw.splitlines():
        fields = line.replace(":", "").split()
        if len(fields) == 3 and fields[1].isdigit() and fields[2] == "kB":
            if fields[0] in result:
                _fail("RESOURCE_MEASUREMENT_UNTRUSTED", f"duplicate meminfo field {fields[0]}")
            result[fields[0]] = int(fields[1]) * 1024
    return result


def _ancestor_pids(proc_root: Path = Path("/proc")) -> set[int]:
    result: set[int] = set()
    current = os.getpid()
    while current > 1:
        if current in result:
            _fail("RESOURCE_CONFLICT_SCAN_UNTRUSTED", "process ancestry contains a cycle")
        result.add(current)
        try:
            raw = (proc_root / str(current) / "stat").read_text(encoding="ascii")
            closing = raw.rfind(")")
            fields = raw[closing + 2 :].split()
            parent = int(fields[1])
        except (OSError, UnicodeError, IndexError, ValueError) as exc:
            _fail("RESOURCE_CONFLICT_SCAN_UNTRUSTED", f"cannot establish process ancestry: {exc}")
        if parent < 0 or parent == current:
            _fail("RESOURCE_CONFLICT_SCAN_UNTRUSTED", "process ancestry is malformed")
        current = parent
    return result


def _process_observation(
    item: Path,
    *,
    pid: int,
) -> dict[str, object] | None:
    try:
        metadata = item.stat()
        raw_stat = (item / "stat").read_text(encoding="ascii")
        closing = raw_stat.rfind(")")
        fields = raw_stat[closing + 2 :].split()
        starttime = int(fields[19])
        command = (item / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8",
            "replace",
        ).strip()
        final_metadata = item.stat()
        final_stat = (item / "stat").read_text(encoding="ascii")
        final_closing = final_stat.rfind(")")
        final_fields = final_stat[final_closing + 2 :].split()
        final_starttime = int(final_fields[19])
    except (FileNotFoundError, ProcessLookupError):
        return None
    except (OSError, UnicodeError, IndexError, ValueError) as exc:
        _fail("RESOURCE_CONFLICT_SCAN_UNTRUSTED", f"cannot identify PID {pid}: {exc}")
    if (
        (metadata.st_dev, metadata.st_ino, metadata.st_uid)
        != (final_metadata.st_dev, final_metadata.st_ino, final_metadata.st_uid)
        or starttime != final_starttime
    ):
        _fail("RESOURCE_CONFLICT_SCAN_UNTRUSTED", f"PID {pid} changed during observation")
    return {
        "command": command,
        "pid": pid,
        "starttime": starttime,
        "uid": metadata.st_uid,
    }


def _validate_allowed_process_identities(
    value: object,
) -> list[dict[str, int]]:
    if type(value) not in {list, tuple}:
        _fail("RESOURCE_CONFLICT_ALLOWLIST_INVALID", "same-UID allowlist is not a sequence")
    items = cast(Sequence[object], value)
    checked: list[dict[str, int]] = []
    seen: set[tuple[int, int]] = set()
    for index, item in enumerate(items):
        if (
            type(item) is not dict
            or set(item) != {"pid", "starttime"}
            or type(item["pid"]) is not int
            or item["pid"] <= 0
            or type(item["starttime"]) is not int
            or item["starttime"] <= 0
        ):
            _fail(
                "RESOURCE_CONFLICT_ALLOWLIST_INVALID",
                f"same-UID allowlist identity {index} is malformed",
            )
        identity = (item["pid"], item["starttime"])
        if identity in seen:
            _fail(
                "RESOURCE_CONFLICT_ALLOWLIST_INVALID",
                f"same-UID allowlist identity {index} is duplicated",
            )
        seen.add(identity)
        checked.append({"pid": item["pid"], "starttime": item["starttime"]})
    return checked


def _same_uid_conflicts(
    *,
    allowed_processes: Sequence[Mapping[str, int]],
    proc_root: Path = Path("/proc"),
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    ancestors = _ancestor_pids(proc_root)
    found: list[dict[str, object]] = []
    allowed = _validate_allowed_process_identities(allowed_processes)
    allowed_by_identity = {
        (item["pid"], item["starttime"]): item
        for item in allowed
    }
    observed_allowed: dict[tuple[int, int], dict[str, object]] = {}
    try:
        entries = tuple(proc_root.iterdir())
    except OSError as exc:
        _fail("RESOURCE_CONFLICT_SCAN_UNTRUSTED", f"cannot enumerate {proc_root}: {exc}")
    for item in entries:
        if not item.name.isdigit():
            continue
        pid = int(item.name)
        if pid in ancestors and pid not in {
            identity["pid"] for identity in allowed
        }:
            continue
        observation = _process_observation(item, pid=pid)
        if observation is None:
            continue
        if observation["uid"] != os.getuid():
            continue
        command = str(observation["command"])
        lowered = command.lower()
        observed_starttime = observation["starttime"]
        if type(observed_starttime) is not int:
            _fail(
                "RESOURCE_CONFLICT_SCAN_UNTRUSTED",
                f"PID {pid} starttime is malformed",
            )
        identity = (pid, observed_starttime)
        record = {
            "command": command,
            "pid": pid,
            "starttime": identity[1],
        }
        if identity in allowed_by_identity:
            if command:
                observed_allowed[identity] = record
            continue
        if command and any(pattern in lowered for pattern in CONFLICT_PATTERNS):
            found.append(record)
    if set(observed_allowed) != set(allowed_by_identity):
        _fail(
            "RESOURCE_CONFLICT_ALLOWLIST_UNVERIFIED",
            "an allowed same-UID process is absent, changed, or has an empty command",
        )
    return (
        sorted(found, key=lambda item: cast(int, item["pid"])),
        [observed_allowed[(item["pid"], item["starttime"])] for item in allowed],
    )


def _validate_lock_identities(
    value: object,
    *,
    identity_format: str,
) -> list[dict[str, object]]:
    if type(value) not in {list, tuple}:
        _fail("RESOURCE_LOCK_EVIDENCE_INVALID", "exactly three lock identities are required")
    items = cast(Sequence[object], value)
    if len(items) != len(LOCK_PATHS):
        _fail("RESOURCE_LOCK_EVIDENCE_INVALID", "exactly three lock identities are required")
    if identity_format == GATE_B_LOCK_IDENTITY_FORMAT:
        expected_fields = {"device", "inode", "mode", "nlink", "path", "uid"}
    elif identity_format == FORMAL_LOCK_IDENTITY_FORMAT:
        expected_fields = {"device", "inode", "path", "uid"}
    else:
        _fail("RESOURCE_LOCK_EVIDENCE_INVALID", f"unknown lock identity format {identity_format!r}")
    checked: list[dict[str, object]] = []
    for index, (item, expected_path) in enumerate(zip(items, LOCK_PATHS, strict=True)):
        if type(item) is not dict or set(item) != expected_fields:
            _fail(
                "RESOURCE_LOCK_EVIDENCE_INVALID",
                f"lock identity {index} field set drifted",
            )
        for field in ("device", "inode", "uid"):
            if type(item[field]) is not int or item[field] < 0:
                _fail(
                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                    f"lock identity {index}.{field} is malformed",
                )
        if item["inode"] == 0 or item["path"] != expected_path:
            _fail("RESOURCE_LOCK_EVIDENCE_INVALID", f"lock identity {index} drifted")
        if identity_format == GATE_B_LOCK_IDENTITY_FORMAT and (
            type(item["mode"]) is not int
            or item["mode"] != 0o600
            or type(item["nlink"]) is not int
            or item["nlink"] != 1
        ):
            _fail("RESOURCE_LOCK_EVIDENCE_INVALID", f"lock identity {index} is unsafe")
        checked.append(dict(item))
    return checked


def _measurement(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail("RESOURCE_MEASUREMENT_UNTRUSTED", f"{label} is not an exact nonnegative integer")
    return value


def evaluate_resource_admission(
    path: Path | str,
    *,
    stage: str,
    lock_identities: Sequence[Mapping[str, object]],
    lock_identity_format: str,
    observation_context: Mapping[str, object],
    meminfo: Mapping[str, int] | None = None,
    disk_free: int | None = None,
    conflicts: Sequence[Mapping[str, object]] | None = None,
    allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
    observed_at_utc: str | None = None,
) -> dict[str, object]:
    """Evaluate one post-lock stage profile and return its auditable receipt."""

    profile = _validated_profile(stage)
    checked_context = _validated_observation_context(
        observation_context,
        stage=stage,
        disk_path=path,
    )
    checked_locks = _validate_lock_identities(
        lock_identities,
        identity_format=lock_identity_format,
    )
    memory = dict(_meminfo() if meminfo is None else meminfo)
    if set(memory) < {"MemAvailable", "SwapFree"}:
        _fail("RESOURCE_MEASUREMENT_UNTRUSTED", "MemAvailable or SwapFree is absent")
    mem_available = _measurement(memory["MemAvailable"], "MemAvailable")
    swap_free = _measurement(memory["SwapFree"], "SwapFree")
    disk_available, disk_target = _measure_disk_target(
        path,
        disk_free=disk_free,
    )
    if conflicts is None:
        heavy, observed_allowed = _same_uid_conflicts(
            allowed_processes=allowed_same_uid_processes,
        )
    else:
        if allowed_same_uid_processes:
            _fail(
                "RESOURCE_CONFLICT_SCAN_UNTRUSTED",
                "injected conflict evidence cannot verify a nonempty allowlist",
            )
        heavy = [dict(item) for item in conflicts]
        observed_allowed = []
    for index, item in enumerate(heavy):
        if (
            type(item) is not dict
            or set(item) not in ({"command", "pid"}, {"command", "pid", "starttime"})
            or type(item["command"]) is not str
            or not item["command"]
            or type(item["pid"]) is not int
            or item["pid"] <= 0
            or (
                "starttime" in item
                and (
                    type(item["starttime"]) is not int
                    or item["starttime"] <= 0
                )
            )
        ):
            _fail("RESOURCE_CONFLICT_SCAN_UNTRUSTED", f"conflict {index} is malformed")
    if heavy:
        _fail("RESOURCE_CONFLICT_DETECTED", f"same-UID conflicts: {heavy}")

    requirements = profile["requirements"]
    assert isinstance(requirements, dict)
    observed = {
        "disk_free_bytes": disk_available,
        "mem_available_bytes": mem_available,
        "same_uid_allowed_processes": observed_allowed,
        "same_uid_conflicts": [],
        "swap_free_bytes": swap_free,
    }
    observed_by_dimension = {
        "disk": disk_available,
        "memory": mem_available,
        "swap": swap_free,
    }
    headroom: dict[str, int] = {}
    for dimension, available in observed_by_dimension.items():
        requirement = requirements[dimension]
        assert isinstance(requirement, dict)
        minimum = int(requirement["minimum_available_bytes"])
        if available < minimum:
            _fail(
                "RESOURCE_HEADROOM_INSUFFICIENT",
                f"{stage}.{dimension}: available={available}, required={minimum}",
            )
        headroom[f"{dimension}_bytes_above_minimum"] = available - minimum

    limits = profile["runtime_safety_limits"]
    assert isinstance(limits, dict)
    hard_cap_feasibility: dict[str, object] = {
        "applies": False,
        "memory_after_host_reserve_bytes": 0,
        "memory_max_bytes": 0,
        "swap_after_host_reserve_capped_bytes": 0,
        "total_capacity_for_memory_max_bytes": 0,
    }
    if limits["applies"] is True:
        memory_requirement = requirements["memory"]
        swap_requirement = requirements["swap"]
        assert isinstance(memory_requirement, dict)
        assert isinstance(swap_requirement, dict)
        memory_after_reserve = mem_available - int(
            memory_requirement["host_reserve_bytes"]
        )
        swap_after_reserve = swap_free - int(swap_requirement["host_reserve_bytes"])
        capped_swap = min(
            max(0, swap_after_reserve),
            int(limits["memory_swap_max_bytes"]),
        )
        total_capacity = max(0, memory_after_reserve) + capped_swap
        memory_max = int(limits["memory_max_bytes"])
        if total_capacity < memory_max:
            _fail(
                "RESOURCE_HARD_CAP_FEASIBILITY_FAILED",
                f"capacity={total_capacity}, MemoryMax={memory_max}",
            )
        hard_cap_feasibility = {
            "applies": True,
            "memory_after_host_reserve_bytes": max(0, memory_after_reserve),
            "memory_max_bytes": memory_max,
            "swap_after_host_reserve_capped_bytes": capped_swap,
            "total_capacity_for_memory_max_bytes": total_capacity,
        }

    timestamp = (
        datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if observed_at_utc is None
        else observed_at_utc
    )
    timestamp = _validated_utc(timestamp, "observation timestamp")
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "created_at_utc": timestamp,
        "disk_target": disk_target,
        "hard_cap_feasibility": hard_cap_feasibility,
        "headroom": headroom,
        "lock_check": {
            "checked_after_acquisition": True,
            "identities": checked_locks,
            "identity_format": lock_identity_format,
            "paths": list(LOCK_PATHS),
        },
        "measurements": observed,
        "observation_context": checked_context,
        "observation_context_sha256": _canonical_sha256(checked_context),
        "profile": profile,
        "schema_version": RESOURCE_ADMISSION_SCHEMA,
        "stage": stage,
        "status": "PASS",
    }


def validate_resource_admission_receipt(
    value: object,
    *,
    expected_stage: str,
    expected_lock_identities: Sequence[Mapping[str, object]],
    expected_lock_identity_format: str,
    expected_observation_context: Mapping[str, object],
    expected_allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
) -> dict[str, object]:
    """Strictly replay one already captured admission receipt."""

    expected_fields = {
        "authority_scope",
        "authorizations",
        "created_at_utc",
        "disk_target",
        "hard_cap_feasibility",
        "headroom",
        "lock_check",
        "measurements",
        "observation_context",
        "observation_context_sha256",
        "profile",
        "schema_version",
        "stage",
        "status",
    }
    if type(value) is not dict or set(value) != expected_fields:
        _fail("RESOURCE_RECEIPT_INVALID", "resource admission receipt field set drifted")
    if (
        value["schema_version"] != RESOURCE_ADMISSION_SCHEMA
        or value["authority_scope"] != AUTHORITY_SCOPE
        or not _exact_tree_equal(value["authorizations"], FALSE_AUTHORIZATIONS)
        or value["stage"] != expected_stage
        or value["status"] != "PASS"
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "resource admission receipt identity drifted")
    _validated_utc(value["created_at_utc"], "receipt observation timestamp")
    expected_profile = _validated_profile(expected_stage)
    if not _exact_tree_equal(value["profile"], expected_profile):
        _fail("RESOURCE_RECEIPT_INVALID", "resource admission profile drifted")
    checked_context = _validated_observation_context(
        expected_observation_context,
        stage=expected_stage,
        disk_path=None,
    )
    if (
        not _exact_tree_equal(value["observation_context"], checked_context)
        or value["observation_context_sha256"] != _canonical_sha256(checked_context)
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "resource observation context drifted")
    disk_target = value["disk_target"]
    if (
        type(disk_target) is not dict
        or set(disk_target) != {"device", "inode", "mode", "path", "type", "uid"}
        or any(
            type(disk_target[field]) is not int
            or disk_target[field] < 0
            for field in ("device", "inode", "mode", "uid")
        )
        or disk_target["inode"] <= 0
        or disk_target["path"] != checked_context["disk_path"]
        or disk_target["type"] != "directory"
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "resource disk target identity drifted")
    checked_expected_locks = _validate_lock_identities(
        expected_lock_identities,
        identity_format=expected_lock_identity_format,
    )
    lock_check = value["lock_check"]
    if type(lock_check) is not dict or not _exact_tree_equal(
        lock_check,
        {
            "checked_after_acquisition": True,
            "identities": checked_expected_locks,
            "identity_format": expected_lock_identity_format,
            "paths": list(LOCK_PATHS),
        },
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "resource admission lock join drifted")
    measurements = value["measurements"]
    if type(measurements) is not dict or set(measurements) != {
        "disk_free_bytes",
        "mem_available_bytes",
        "same_uid_allowed_processes",
        "same_uid_conflicts",
        "swap_free_bytes",
    }:
        _fail("RESOURCE_RECEIPT_INVALID", "resource admission measurements drifted")
    if measurements["same_uid_conflicts"] != []:
        _fail("RESOURCE_RECEIPT_INVALID", "resource admission retained a conflict")
    expected_allowed = _validate_allowed_process_identities(
        expected_allowed_same_uid_processes,
    )
    recorded_allowed = measurements["same_uid_allowed_processes"]
    if type(recorded_allowed) is not list or len(recorded_allowed) != len(expected_allowed):
        _fail("RESOURCE_RECEIPT_INVALID", "resource admission allowlist cardinality drifted")
    for index, (recorded, expected_identity) in enumerate(
        zip(recorded_allowed, expected_allowed, strict=True)
    ):
        if (
            type(recorded) is not dict
            or set(recorded) != {"command", "pid", "starttime"}
            or type(recorded["command"]) is not str
            or not recorded["command"]
            or type(recorded["pid"]) is not int
            or type(recorded["starttime"]) is not int
            or not _exact_tree_equal(
                {
                    "pid": recorded["pid"],
                    "starttime": recorded["starttime"],
                },
                expected_identity,
            )
        ):
            _fail(
                "RESOURCE_RECEIPT_INVALID",
                f"resource admission allowed process {index} drifted",
            )
    observed = {
        "disk": _measurement(measurements["disk_free_bytes"], "receipt disk free"),
        "memory": _measurement(
            measurements["mem_available_bytes"],
            "receipt MemAvailable",
        ),
        "swap": _measurement(measurements["swap_free_bytes"], "receipt SwapFree"),
    }
    requirements = expected_profile["requirements"]
    assert isinstance(requirements, dict)
    expected_headroom: dict[str, int] = {}
    for dimension, available in observed.items():
        requirement = requirements[dimension]
        assert isinstance(requirement, dict)
        minimum = int(requirement["minimum_available_bytes"])
        if available < minimum:
            _fail("RESOURCE_RECEIPT_INVALID", f"receipt {dimension} is below its profile")
        expected_headroom[f"{dimension}_bytes_above_minimum"] = available - minimum
    if not _exact_tree_equal(value["headroom"], expected_headroom):
        _fail("RESOURCE_RECEIPT_INVALID", "resource admission headroom arithmetic drifted")

    limits = expected_profile["runtime_safety_limits"]
    assert isinstance(limits, dict)
    expected_feasibility: dict[str, object] = {
        "applies": False,
        "memory_after_host_reserve_bytes": 0,
        "memory_max_bytes": 0,
        "swap_after_host_reserve_capped_bytes": 0,
        "total_capacity_for_memory_max_bytes": 0,
    }
    if limits["applies"] is True:
        memory_requirement = requirements["memory"]
        swap_requirement = requirements["swap"]
        assert isinstance(memory_requirement, dict)
        assert isinstance(swap_requirement, dict)
        memory_after_reserve = max(
            0,
            observed["memory"] - int(memory_requirement["host_reserve_bytes"]),
        )
        swap_after_reserve = max(
            0,
            observed["swap"] - int(swap_requirement["host_reserve_bytes"]),
        )
        capped_swap = min(swap_after_reserve, int(limits["memory_swap_max_bytes"]))
        total_capacity = memory_after_reserve + capped_swap
        memory_max = int(limits["memory_max_bytes"])
        if total_capacity < memory_max:
            _fail("RESOURCE_RECEIPT_INVALID", "receipt cannot back formal MemoryMax")
        expected_feasibility = {
            "applies": True,
            "memory_after_host_reserve_bytes": memory_after_reserve,
            "memory_max_bytes": memory_max,
            "swap_after_host_reserve_capped_bytes": capped_swap,
            "total_capacity_for_memory_max_bytes": total_capacity,
        }
    if not _exact_tree_equal(value["hard_cap_feasibility"], expected_feasibility):
        _fail("RESOURCE_RECEIPT_INVALID", "hard-cap feasibility arithmetic drifted")
    return deepcopy(value)


def _launch_contract_from_receipt(
    value: object,
) -> tuple[
    dict[str, object],
    str,
    list[dict[str, object]],
    str,
    dict[str, object],
    list[dict[str, int]],
]:
    """Strictly replay a receipt and recover only its exact launch contract."""

    if type(value) is not dict:
        _fail("RESOURCE_RECEIPT_INVALID", "launch resource receipt is not an object")
    stage = value.get("stage")
    lock_check = value.get("lock_check")
    context = value.get("observation_context")
    measurements = value.get("measurements")
    if (
        type(stage) is not str
        or type(lock_check) is not dict
        or type(context) is not dict
        or type(measurements) is not dict
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "launch resource contract is malformed")
    lock_identities = lock_check.get("identities")
    identity_format = lock_check.get("identity_format")
    recorded_allowed = measurements.get("same_uid_allowed_processes")
    if (
        type(lock_identities) is not list
        or type(identity_format) is not str
        or type(recorded_allowed) is not list
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "launch resource contract fields are malformed")
    allowed: list[dict[str, int]] = []
    for index, item in enumerate(recorded_allowed):
        if (
            type(item) is not dict
            or type(item.get("pid")) is not int
            or type(item.get("starttime")) is not int
        ):
            _fail(
                "RESOURCE_RECEIPT_INVALID",
                f"launch resource allowed process {index} is malformed",
            )
        allowed.append(
            {
                "pid": item["pid"],
                "starttime": item["starttime"],
            }
        )
    checked = validate_resource_admission_receipt(
        value,
        expected_stage=stage,
        expected_lock_identities=lock_identities,
        expected_lock_identity_format=identity_format,
        expected_observation_context=context,
        expected_allowed_same_uid_processes=allowed,
    )
    return (
        checked,
        stage,
        _validate_lock_identities(
            lock_identities,
            identity_format=identity_format,
        ),
        identity_format,
        dict(context),
        allowed,
    )


def _open_launch_lock_probes(
    identities: Sequence[Mapping[str, object]],
    *,
    identity_format: str,
) -> list[tuple[int, tuple[int, int, int, int, int]]]:
    """Retain probes proving each exact named lock is still safely held."""

    checked = _validate_lock_identities(
        identities,
        identity_format=identity_format,
    )
    opened: list[tuple[int, tuple[int, int, int, int, int]]] = []
    try:
        for path, expected in zip(LOCK_PATHS, checked, strict=True):
            descriptor = os.open(
                path,
                os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            opened.append((descriptor, (0, 0, 0, 0, 0)))
            observed = os.fstat(descriptor)
            named = os.stat(path, follow_symlinks=False)
            signature = _lock_signature(observed)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_uid != os.getuid()
                or stat.S_IMODE(observed.st_mode) != 0o600
                or observed.st_nlink != 1
                or _lock_signature(named) != signature
                or observed.st_dev != expected["device"]
                or observed.st_ino != expected["inode"]
                or observed.st_uid != expected["uid"]
            ):
                _fail(
                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                    f"{path} launch-time identity drifted",
                )
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                _fail(
                    "RESOURCE_LOCK_EVIDENCE_INVALID",
                    f"{path} is not held at the launch boundary",
                )
            opened[-1] = (descriptor, signature)
    except BaseException as primary:
        for descriptor, _signature in reversed(opened):
            try:
                os.close(descriptor)
            except BaseException as close_error:
                primary.add_note(
                    "launch lock-probe cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise
    return opened


def _close_launch_lock_probes(
    opened: Sequence[tuple[int, tuple[int, int, int, int, int]]],
    *,
    primary: BaseException | None,
) -> None:
    for descriptor, _signature in reversed(tuple(opened)):
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = (
                    ResourceAdmissionError(
                        "RESOURCE_LOCK_EVIDENCE_INVALID",
                        f"launch lock-probe close failed: {close_error}",
                    )
                    if isinstance(close_error, OSError)
                    else close_error
                )
            else:
                primary.add_note(
                    "launch lock-probe close failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        raise primary


def _revalidate_launch_lock_probes(
    opened: Sequence[tuple[int, tuple[int, int, int, int, int]]],
) -> None:
    if len(opened) != len(LOCK_PATHS):
        _fail(
            "RESOURCE_LOCK_EVIDENCE_INVALID",
            "launch lock-probe cardinality drifted",
        )
    for (descriptor, expected_signature), path in zip(
        opened,
        LOCK_PATHS,
        strict=True,
    ):
        opened_metadata = os.fstat(descriptor)
        named = os.stat(path, follow_symlinks=False)
        if (
            _lock_signature(opened_metadata) != expected_signature
            or _lock_signature(named) != expected_signature
        ):
            _fail(
                "RESOURCE_LOCK_EVIDENCE_INVALID",
                f"{path} drifted across launch-time resource reevaluation",
            )


def reevaluate_resource_admission_for_launch(
    expected_receipt: object,
    *,
    meminfo: Mapping[str, int] | None = None,
    disk_free: int | None = None,
    conflicts: Sequence[Mapping[str, object]] | None = None,
    observed_at_utc: str | None = None,
) -> dict[str, object]:
    """Re-evaluate an already replayed contract at the actual launch edge.

    The old receipt supplies no live authority.  It supplies only the exact
    stage, context, lock identities, and PID/starttime allowlist that this
    function must reclose before taking fresh host measurements.
    """

    (
        _checked_expected,
        stage,
        lock_identities,
        identity_format,
        context,
        allowed,
    ) = _launch_contract_from_receipt(expected_receipt)
    probes = _open_launch_lock_probes(
        lock_identities,
        identity_format=identity_format,
    )
    final_receipt: dict[str, object] | None = None
    primary: BaseException | None = None
    try:
        final_receipt = evaluate_resource_admission(
            cast(str, context["disk_path"]),
            stage=stage,
            lock_identities=lock_identities,
            lock_identity_format=identity_format,
            observation_context=context,
            meminfo=meminfo,
            disk_free=disk_free,
            conflicts=conflicts,
            allowed_same_uid_processes=allowed,
            observed_at_utc=observed_at_utc,
        )
        _revalidate_launch_lock_probes(probes)
        validate_resource_admission_receipt(
            final_receipt,
            expected_stage=stage,
            expected_lock_identities=lock_identities,
            expected_lock_identity_format=identity_format,
            expected_observation_context=context,
            expected_allowed_same_uid_processes=allowed,
        )
    except BaseException as exc:
        primary = exc
    _close_launch_lock_probes(probes, primary=primary)
    assert final_receipt is not None
    return final_receipt


def validate_launch_resource_reevaluation(
    value: object,
    *,
    expected_receipt: object,
) -> dict[str, object]:
    """Replay a launch-edge receipt against the exact prelaunch contract."""

    (
        _checked_expected,
        stage,
        lock_identities,
        identity_format,
        context,
        allowed,
    ) = _launch_contract_from_receipt(expected_receipt)
    return validate_resource_admission_receipt(
        value,
        expected_stage=stage,
        expected_lock_identities=lock_identities,
        expected_lock_identity_format=identity_format,
        expected_observation_context=context,
        expected_allowed_same_uid_processes=allowed,
    )
