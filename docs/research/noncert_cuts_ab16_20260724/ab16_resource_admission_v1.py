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
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from types import ModuleType
from typing import Any, NoReturn, cast


RESOURCE_ADMISSION_SCHEMA = "noncert-cuts-ab16-stage-resource-admission-v1"
PROFILE_SET_ID = "noncert-cuts-ab16-resource-profile-set-v1"
PROSPECTIVE_RESOURCE_ADMISSION_SCHEMA = (
    "noncert-cuts-ab16-stage-resource-admission-v3"
)
CALIBRATION_PRELAUNCH_RESOURCE_ADMISSION_SCHEMA = (
    "noncert-cuts-ab16-calibration-prelaunch-resource-admission-v2"
)
SAME_UID_PROCESS_BASELINE_SCHEMA = (
    "noncert-cuts-ab16-same-uid-process-baseline-v1"
)
SAME_UID_BASELINE_POLICY_ID = (
    "exact-resource-gate-pid-starttime-classification-v1"
)
SAME_UID_BASELINE_LIVE_MODE = "LIVE_PROCFS_FULL_SCOPE"
SAME_UID_BASELINE_TEST_MODE = "INJECTED_TEST_ONLY_NO_LAUNCH"
SAME_UID_PROCESS_CLASSIFICATIONS = frozenset(
    {
        "ALLOWED_CAMPAIGN_ACTOR",
        "NONCONFLICTING_AMBIENT",
        "RESOURCE_GATE_ANCESTOR",
    }
)
PROSPECTIVE_PROFILE_SET_ID = "noncert-cuts-ab16-resource-profile-set-v2"
BUDGET_PROFILE_SCHEMA = "noncert-cuts-ab16-resource-budget-profile-v1"
CALIBRATION_AUTHORIZATION_BUNDLE_SCHEMA = (
    "noncert-cuts-ab16-resource-calibration-authorization-bundle-v1"
)
CALIBRATION_EXECUTION_SURFACE_SCHEMA = (
    "noncert-cuts-ab16-resource-execution-surface-v3"
)
CALIBRATION_PACKAGE_SCHEMA = (
    "noncert-cuts-ab16-resource-calibration-package-v2"
)
CALIBRATION_PORTABLE_PACKAGE_LAYOUT = "PORTABLE_CANDIDATE_V1"
CALIBRATION_OUTSIDE_REPLAY_SCHEMA = (
    "noncert-cuts-ab16-resource-calibration-outside-replay-v1"
)
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
PROSPECTIVE_FALSE_AUTHORIZATIONS = {
    "formal_campaign_creation_authorized": False,
    "gate_b_approval_authorized": False,
    "organic_arm_launch_authorized": False,
    "profile_installation_authorized": False,
    "solver_run_authorized": False,
}
CALIBRATION_TOOL_ROLES = frozenset(
    {
        "aggregator",
        "alternate_replayer",
        "fd_loader",
        "observer_harness",
        "package_verifier",
        "primary_replayer",
        "protocol",
        "runner",
        "workload",
    }
)
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


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


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


def _prospective_dimension(
    predicted_peak_bytes: int,
    safety_margin_bytes: int,
    host_reserve_bytes: int,
    *,
    basis_class: str,
    basis_detail: str,
    availability_rule: str = "INDEPENDENT_MINIMUM",
) -> dict[str, object]:
    if availability_rule == "INDEPENDENT_MINIMUM":
        minimum = predicted_peak_bytes + safety_margin_bytes + host_reserve_bytes
    elif availability_rule == "COMBINED_RAM_LIMITED_SWAP":
        minimum = 0
    else:
        raise ValueError(f"unknown prospective availability rule {availability_rule!r}")
    return {
        "availability_rule": availability_rule,
        "basis_class": basis_class,
        "basis_detail": basis_detail,
        "host_reserve_bytes": host_reserve_bytes,
        "minimum_available_bytes": minimum,
        "predicted_peak_bytes": predicted_peak_bytes,
        "safety_margin_bytes": safety_margin_bytes,
    }


def _prospective_profile(
    *,
    profile_id: str,
    stage: str,
    basis: Mapping[str, object],
    memory: Mapping[str, object],
    swap: Mapping[str, object],
    disk: Mapping[str, object],
    runtime_safety_limits: Mapping[str, object],
    budget_binding: Mapping[str, object] | None = None,
) -> dict[str, object]:
    profile: dict[str, object] = {
        "basis": dict(basis),
        "budget_binding": None if budget_binding is None else dict(budget_binding),
        "execution": {
            "calibration_execution_surface_required": True,
            "lock_paths": list(LOCK_PATHS),
            "same_uid_allowlist_identity_fields": ["pid", "starttime"],
            "same_uid_conflict_patterns": list(CONFLICT_PATTERNS),
            "same_uid_conflict_check_required": True,
            "single_worker_required": stage != FULL_PREFLIGHT,
        },
        "profile_id": profile_id,
        "profile_set_id": PROSPECTIVE_PROFILE_SET_ID,
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


_PROSPECTIVE_STATIC_PROFILES: dict[str, dict[str, object]] = {
    FULL_PREFLIGHT: _prospective_profile(
        profile_id="ab16-full-preflight-execution-bound-temporary-v2",
        stage=FULL_PREFLIGHT,
        basis=_basis(
            comparable_to_stage=True,
            evidence_class="HISTORICAL_EXTERNAL_SAMPLER_SAME_STAGE_PROXY",
            historical_observations=(_HISTORICAL_FULL_OBSERVATION,),
            prediction_method=(
                "bind the exact command, collected test inventory, xdist availability, "
                "and effective worker mode in the calibration execution surface; until "
                "three comparable samples exist, retain the rounded 16 GiB memory "
                "prediction with 4 GiB uncertainty, a provisional 2+2 GiB swap "
                "allowance, and 6+2 GiB measured-tree disk-growth allowance"
            ),
        ),
        memory=_prospective_dimension(
            16 * GIB,
            4 * GIB,
            12 * GIB,
            basis_class="HISTORICAL_EXTERNAL_SAMPLER_SAME_STAGE_PROXY",
            basis_detail="13.51 GB heterogeneous sampled RSS rounded up to 16 GiB",
        ),
        swap=_prospective_dimension(
            2 * GIB,
            2 * GIB,
            4 * GIB,
            basis_class="BOUNDED_TEMPORARY_EXECUTION_ALLOWANCE",
            basis_detail=(
                "no comparable swap cohort; temporary 2 GiB workload allowance "
                "plus 2 GiB error and an independent 4 GiB host reserve"
            ),
        ),
        disk=_prospective_dimension(
            6 * GIB,
            2 * GIB,
            4 * GIB,
            basis_class="BOUNDED_TEMPORARY_STAGE_TREE_GROWTH",
            basis_detail=(
                "full preflight writes only its isolated basetemp and declared "
                "outputs; provisional 6 GiB growth plus 2 GiB error"
            ),
        ),
        runtime_safety_limits=_NO_CGROUP_LIMITS,
    ),
    GATE_B_QUALIFICATION: _prospective_profile(
        profile_id="ab16-gate-b-bounded-publication-temporary-v2",
        stage=GATE_B_QUALIFICATION,
        basis=_basis(
            comparable_to_stage=False,
            evidence_class="BOUNDED_WORKLOAD_TEMPORARY_PROFILE",
            historical_observations=(),
            prediction_method=(
                "Gate-B qualification is a single-worker canonical parse/hash/"
                "publication workload over the sealed request, package candidate, "
                "and fixed receipts; provision 2 GiB memory and disk, then add "
                "independent 2 GiB memory, 1 GiB swap, and 1 GiB disk error "
                "allowances instead of reconstructing any historical global floor"
            ),
        ),
        memory=_prospective_dimension(
            2 * GIB,
            2 * GIB,
            8 * GIB,
            basis_class="BOUNDED_GATE_B_WORKLOAD_TEMPORARY",
            basis_detail="2 GiB bounded working set plus 2 GiB explicit error allowance",
        ),
        swap=_prospective_dimension(
            0,
            1 * GIB,
            2 * GIB,
            basis_class="BOUNDED_GATE_B_WORKLOAD_TEMPORARY",
            basis_detail="no planned swap; 1 GiB error allowance and 2 GiB host reserve",
        ),
        disk=_prospective_dimension(
            2 * GIB,
            1 * GIB,
            4 * GIB,
            basis_class="BOUNDED_GATE_B_RETAINED_GROWTH_TEMPORARY",
            basis_detail="2 GiB bounded retained/scratch growth plus 1 GiB error allowance",
        ),
        runtime_safety_limits=_NO_CGROUP_LIMITS,
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


_BUDGET_ARTIFACT_CLASSES = frozenset(
    {
        "closeout",
        "ledger",
        "metadata",
        "model",
        "normal",
        "publication",
        "scratch",
    }
)
_FORMAL_ARM_SLOTS = frozenset(
    {
        f"{family}-{direction}-{treatment}"
        for family in (
            "bundle",
            "power-hitting-set",
            "region-capacity",
            "shape-packing-hall",
        )
        for direction in ("ab", "ba")
        for treatment in ("control", "treatment")
    }
)
_FORMAL_ARM_APPEND_CHANNEL_LABELS = (
    "compile attach journal segment",
    "cut ledger segment",
    "runtime cut segment",
)


def _formal_arm_artifact_registry() -> dict[str, str]:
    """Read the one production runner registry used by every arm writer."""

    from docs.research.noncert_cuts_ab16_20260724.organic_arm_runner_v1 import (
        BUDGET_ARTIFACT_CLASS_BY_LABEL,
    )

    registry = BUDGET_ARTIFACT_CLASS_BY_LABEL
    if (
        type(registry) is not dict
        or len(registry) != 28
        or any(
            type(label) is not str
            or not label
            or type(artifact_class) is not str
            or artifact_class not in _BUDGET_ARTIFACT_CLASSES
            for label, artifact_class in registry.items()
        )
        or not set(_FORMAL_ARM_APPEND_CHANNEL_LABELS) <= set(registry)
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "production arm writer registry is malformed",
        )
    return dict(sorted(registry.items()))


def _budget_relative_path(
    value: object,
    *,
    label: str,
    allow_dot: bool = False,
) -> str:
    if type(value) is not str:
        _fail("FORMAL_BUDGET_PROFILE_REQUIRED", f"{label} is not text")
    if allow_dot and value == ".":
        return value
    parsed = PurePosixPath(value)
    if (
        parsed.is_absolute()
        or not parsed.parts
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        _fail("FORMAL_BUDGET_PROFILE_REQUIRED", f"{label} escapes formal root")
    return parsed.as_posix()


def _prospective_profile_identity(
    value: object,
    *,
    expected_bytes: bytes,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"}:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "budget profile identity field set drifted",
        )
    identity = cast(dict[str, object], value)
    path = identity["path"]
    if type(path) is not str or not Path(path).is_absolute():
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "budget profile identity path is not absolute",
        )
    if (
        type(identity["sha256"]) is not str
        or identity["sha256"] != hashlib.sha256(expected_bytes).hexdigest()
        or type(identity["size_bytes"]) is not int
        or identity["size_bytes"] != len(expected_bytes)
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "budget profile byte identity drifted",
        )
    return dict(identity)


def _budget_categories(value: object, *, label: str) -> dict[str, int]:
    if type(value) is not dict or not value:
        _fail("FORMAL_BUDGET_PROFILE_REQUIRED", f"{label} is absent")
    result: dict[str, int] = {}
    for category, raw in cast(dict[object, object], value).items():
        if (
            type(category) is not str
            or category not in _BUDGET_ARTIFACT_CLASSES
            or type(raw) is not int
            or raw < 0
        ):
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"{label} contains a malformed category",
            )
        result[category] = raw
    return dict(sorted(result.items()))


def derive_formal_disk_requirement(
    *,
    enforced_budget_profile: Mapping[str, object],
    enforced_budget_profile_identity: Mapping[str, object],
) -> dict[str, object]:
    """Derive formal disk admission from the enforceable aggregate escrow.

    The budget profile must already be launch-ready and byte-bound.  This
    function does not install or authorize it.  Its aggregate is the sum of
    the one formal-root broker's category limits; arm allocations and fixed
    overhead must form an exact partition of that same total.
    """

    profile = dict(enforced_budget_profile)
    expected_top = {
        "authority",
        "bootstrap",
        "execution_surface_sha256",
        "formal_root",
        "launch_ready",
        "profile_id",
        "profile_sha256",
        "schema_version",
    }
    if set(profile) != expected_top:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "budget profile field set drifted",
        )
    if (
        profile["schema_version"] != BUDGET_PROFILE_SCHEMA
        or profile["launch_ready"] is not True
        or type(profile["profile_id"]) is not str
        or not profile["profile_id"]
        or type(profile["execution_surface_sha256"]) is not str
        or len(profile["execution_surface_sha256"]) != 64
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "budget profile is not a launch-ready prospective profile",
        )
    authority = profile["authority"]
    expected_authority = {
        "changes_certified_exact": False,
        "changes_cut_state": False,
        "changes_lower_bound": False,
        "changes_production": False,
        "changes_upper_bound": False,
        "research_only": True,
    }
    if not _exact_tree_equal(authority, expected_authority):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "budget profile authority boundary drifted",
        )
    unhashed = dict(profile)
    recorded_internal_sha = unhashed.pop("profile_sha256")
    if (
        type(recorded_internal_sha) is not str
        or hashlib.sha256(_canonical_json_bytes(unhashed)).hexdigest()
        != recorded_internal_sha
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "budget profile internal SHA-256 drifted",
        )
    profile_bytes = _canonical_json_bytes(profile)
    identity = _prospective_profile_identity(
        enforced_budget_profile_identity,
        expected_bytes=profile_bytes,
    )

    formal = profile["formal_root"]
    expected_formal = {
        "append_channels",
        "arm_append_channels",
        "arm_allocations",
        "arm_artifact_caps",
        "arm_workload_contract",
        "artifact_maxima",
        "category_limits",
        "fixed_directories",
        "fixed_overhead_category_limits",
        "fixed_purpose_reservations",
        "root_relative_path",
    }
    if type(formal) is not dict or set(formal) != expected_formal:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal-root budget shape drifted",
        )
    formal_record = cast(dict[str, object], formal)
    if formal_record["root_relative_path"] != "formal-ab16/artifacts":
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal-root relative path drifted",
        )
    root_limits = _budget_categories(
        formal_record["category_limits"],
        label="formal-root category limits",
    )
    fixed = _budget_categories(
        formal_record["fixed_overhead_category_limits"],
        label="formal-root fixed overhead",
    )
    raw_arms = formal_record["arm_allocations"]
    if (
        type(raw_arms) is not dict
        or set(raw_arms) != _FORMAL_ARM_SLOTS
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal-root arm allocation set is not the fixed 16 slots",
        )
    allocated = {category: 0 for category in root_limits}
    checked_arm_allocations: dict[str, dict[str, int]] = {}
    for slot, raw_categories in cast(dict[object, object], raw_arms).items():
        if type(slot) is not str or not slot:
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                "formal-root arm slot label is malformed",
            )
        categories = _budget_categories(
            raw_categories,
            label=f"formal-root arm allocation {slot}",
        )
        checked_arm_allocations[cast(str, slot)] = categories
        for category, amount in categories.items():
            if category not in allocated:
                _fail(
                    "FORMAL_BUDGET_PROFILE_REQUIRED",
                    f"arm allocation category {category!r} is absent from root",
                )
            allocated[category] += amount
    for category, amount in fixed.items():
        if category not in allocated:
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"fixed category {category!r} is absent from root",
            )
        allocated[category] += amount
    if allocated != root_limits:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "arm allocations plus fixed overhead do not partition the root budget",
        )

    artifact_registry = _formal_arm_artifact_registry()
    raw_arm_caps = formal_record["arm_artifact_caps"]
    if type(raw_arm_caps) is not dict or set(raw_arm_caps) != _FORMAL_ARM_SLOTS:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal-root arm artifact-cap set is not the fixed 16 slots",
        )
    checked_arm_caps: dict[str, dict[str, dict[str, object]]] = {}
    arm_branch_totals: dict[
        str, dict[str, dict[str, int]]
    ] = {}
    for slot in sorted(_FORMAL_ARM_SLOTS):
        raw_slot_caps = cast(dict[str, object], raw_arm_caps).get(slot)
        if (
            type(raw_slot_caps) is not dict
            or set(raw_slot_caps) != set(artifact_registry)
        ):
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"arm artifact-cap label set differs for {slot}",
            )
        slot_limits = checked_arm_allocations[slot]
        slot_caps: dict[str, dict[str, object]] = {}
        branch_totals = {
            branch: {category: 0 for category in slot_limits}
            for branch in ("common", "failure", "success")
        }
        for label, expected_class in sorted(
            artifact_registry.items()
        ):
            raw_cap = cast(dict[str, object], raw_slot_caps).get(label)
            if (
                type(raw_cap) is not dict
                or set(raw_cap)
                != {
                    "artifact_class",
                    "branch",
                    "maximum_bytes",
                    "maximum_publications",
                    "multiplicity_source",
                    "path_contract",
                }
                or raw_cap["artifact_class"] != expected_class
                or type(raw_cap["maximum_bytes"]) is not int
                or cast(int, raw_cap["maximum_bytes"]) <= 0
                or raw_cap["branch"]
                not in {"common", "failure", "success"}
                or type(raw_cap["maximum_publications"]) is not int
                or cast(int, raw_cap["maximum_publications"]) < 0
                or expected_class not in slot_limits
                or cast(int, raw_cap["maximum_bytes"]) > slot_limits[expected_class]
            ):
                _fail(
                    "FORMAL_BUDGET_PROFILE_REQUIRED",
                    f"arm artifact cap is malformed or exceeds {slot} allocation: {label}",
                )
            count = cast(int, raw_cap["maximum_publications"])
            branch = cast(str, raw_cap["branch"])
            path_contract = raw_cap["path_contract"]
            multiplicity = raw_cap["multiplicity_source"]
            if (
                type(path_contract) is not dict
                or path_contract.get("root") != "formal-root"
                or type(multiplicity) is not dict
            ):
                _fail(
                    "FORMAL_BUDGET_PROFILE_REQUIRED",
                    f"arm artifact path/multiplicity is malformed for {slot}: {label}",
                )
            path_kind = path_contract.get("kind")
            if path_kind == "fixed":
                if (
                    set(path_contract)
                    != {"kind", "root", "root_relative_path"}
                ):
                    _fail(
                        "FORMAL_BUDGET_PROFILE_REQUIRED",
                        f"fixed arm artifact path drifted for {slot}: {label}",
                    )
                _budget_relative_path(
                    path_contract["root_relative_path"],
                    label=f"{slot}.{label}.root_relative_path",
                )
            elif path_kind in {
                "indexed-phase-template",
                "indexed-template",
            }:
                expected_path_fields = {
                    "index_maximum",
                    "index_minimum",
                    "index_name",
                    "kind",
                    "root",
                    "root_relative_path_template",
                }
                if path_kind == "indexed-phase-template":
                    expected_path_fields.add("allowed_phases")
                if (
                    set(path_contract) != expected_path_fields
                    or path_contract["index_name"] != "hook_id"
                    or path_contract["index_minimum"] != 0
                    or type(path_contract["index_maximum"]) is not int
                    or cast(int, path_contract["index_maximum"]) + 1
                    != 30
                    or (
                        path_kind == "indexed-phase-template"
                        and path_contract["allowed_phases"]
                        != ["post", "pre"]
                    )
                ):
                    _fail(
                        "FORMAL_BUDGET_PROFILE_REQUIRED",
                        f"indexed arm artifact path drifted for {slot}: {label}",
                    )
                template = _budget_relative_path(
                    path_contract["root_relative_path_template"],
                    label=f"{slot}.{label}.root_relative_path_template",
                )
                if slot not in template or "{hook_id:04d}" not in template:
                    _fail(
                        "FORMAL_BUDGET_PROFILE_REQUIRED",
                        f"indexed arm artifact template lost its slot for {slot}: {label}",
                    )
            elif path_kind == "append-channel":
                if (
                    set(path_contract) != {"channel", "kind", "root"}
                    or type(path_contract["channel"]) is not str
                    or not cast(str, path_contract["channel"]).startswith(
                        f"arm-{slot}-"
                    )
                ):
                    _fail(
                        "FORMAL_BUDGET_PROFILE_REQUIRED",
                        f"append-only arm artifact path drifted for {slot}: {label}",
                    )
            else:
                _fail(
                    "FORMAL_BUDGET_PROFILE_REQUIRED",
                    f"unknown arm artifact path kind for {slot}: {label}",
                )
            multiplicity_kind = multiplicity.get("kind")
            if multiplicity_kind == "terminal-branch-fixed-path":
                valid_multiplicity = (
                    set(multiplicity)
                    == {
                        "kind",
                        "maximum_fixed_publications",
                        "terminal_branch",
                    }
                    and multiplicity["terminal_branch"] == branch
                    and multiplicity["maximum_fixed_publications"] == count
                    and branch in {"failure", "success"}
                    and path_kind == "fixed"
                )
            elif multiplicity_kind == "single-fixed-path":
                valid_multiplicity = (
                    set(multiplicity)
                    == {"kind", "maximum_fixed_publications"}
                    and multiplicity["maximum_fixed_publications"] == count
                    and count == 1
                    and branch == "common"
                    and path_kind == "fixed"
                )
            elif multiplicity_kind == "attach-hook":
                valid_multiplicity = (
                    set(multiplicity)
                    == {
                        "kind",
                        "maximum_attach_hooks",
                        "publications_per_hook",
                    }
                    and multiplicity["maximum_attach_hooks"] == 30
                    and type(multiplicity["publications_per_hook"]) is int
                    and cast(int, multiplicity["publications_per_hook"]) > 0
                    and count
                    == 30
                    * cast(int, multiplicity["publications_per_hook"])
                    and branch == "common"
                    and path_kind
                    in {"indexed-phase-template", "indexed-template"}
                )
            elif multiplicity_kind == "append-channel-only":
                valid_multiplicity = (
                    set(multiplicity)
                    == {"kind", "maximum_fixed_publications"}
                    and multiplicity["maximum_fixed_publications"] == 0
                    and count == 0
                    and branch == "common"
                    and path_kind == "append-channel"
                )
            else:
                valid_multiplicity = False
            if not valid_multiplicity:
                _fail(
                    "FORMAL_BUDGET_PROFILE_REQUIRED",
                    f"arm artifact multiplicity drifted for {slot}: {label}",
                )
            slot_caps[label] = dict(raw_cap)
            allocation_branch = (
                "common"
                if label == "organic arm failure record"
                else branch
            )
            branch_totals[allocation_branch][expected_class] += (
                cast(int, raw_cap["maximum_bytes"]) * count
            )
        checked_arm_caps[slot] = slot_caps
        arm_branch_totals[slot] = branch_totals

    raw_arm_channels = formal_record["arm_append_channels"]
    if (
        type(raw_arm_channels) is not dict
        or set(raw_arm_channels) != _FORMAL_ARM_SLOTS
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal-root arm append-channel set is not the fixed 16 slots",
        )
    required_by_slot: dict[str, dict[str, int]] = {}
    for slot in sorted(_FORMAL_ARM_SLOTS):
        raw_slot_channels = cast(dict[str, object], raw_arm_channels).get(slot)
        if type(raw_slot_channels) is not list or len(raw_slot_channels) != 3:
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"arm append-channel table is not exact for {slot}",
            )
        expected_channels = sorted(
            (
                (
                    f"arm-{slot}-compile-journal",
                    "compile attach journal segment",
                    f"prospective/arms/{slot}/ledger/compile-attach-journal",
                    221,
                ),
                (
                    f"arm-{slot}-cut-ledger",
                    "cut ledger segment",
                    f"prospective/arms/{slot}/ledger/cut-ledger",
                    258,
                ),
                (
                    f"arm-{slot}-runtime-cuts",
                    "runtime cut segment",
                    f"prospective/arms/{slot}/checkpoint/runtime-cuts",
                    0,
                ),
            ),
            key=lambda item: item[0].encode("utf-8"),
        )
        append_totals = {
            category: 0 for category in checked_arm_allocations[slot]
        }
        for index, (
            (
                expected_channel,
                expected_label,
                expected_parent,
                expected_segments,
            ),
            raw_channel,
        ) in enumerate(
            zip(expected_channels, cast(list[object], raw_slot_channels), strict=True)
        ):
            cap = checked_arm_caps[slot][expected_label]
            if (
                type(raw_channel) is not dict
                or set(raw_channel)
                != {
                    "artifact_class",
                    "channel",
                    "label",
                    "maximum_bytes",
                    "maximum_segments",
                    "multiplicity_derivation",
                    "parent_path",
                }
                or raw_channel["artifact_class"] != "ledger"
                or raw_channel["channel"] != expected_channel
                or raw_channel["label"] != expected_label
                or raw_channel["maximum_bytes"] != cap["maximum_bytes"]
                or raw_channel["maximum_segments"] != expected_segments
                or raw_channel["parent_path"] != expected_parent
                or type(raw_channel["multiplicity_derivation"]) is not dict
                or set(raw_channel["multiplicity_derivation"])
                != {
                    "formula",
                    "maximum_attach_hooks",
                    "maximum_generated_cuts",
                    "result_maximum_segments",
                }
                or raw_channel["multiplicity_derivation"][
                    "maximum_attach_hooks"
                ]
                != 30
                or raw_channel["multiplicity_derivation"][
                    "maximum_generated_cuts"
                ]
                != 128
                or raw_channel["multiplicity_derivation"][
                    "result_maximum_segments"
                ]
                != expected_segments
                or type(
                    raw_channel["multiplicity_derivation"]["formula"]
                )
                is not str
                or not raw_channel["multiplicity_derivation"]["formula"]
            ):
                _fail(
                    "FORMAL_BUDGET_PROFILE_REQUIRED",
                    f"arm append channel[{index}] differs for {slot}",
                )
            append_totals["ledger"] += (
                cast(int, raw_channel["maximum_bytes"])
                * expected_segments
            )
        branch_totals = arm_branch_totals[slot]
        required_by_slot[slot] = {
            category: (
                branch_totals["common"].get(category, 0)
                + max(
                    branch_totals["success"].get(category, 0),
                    branch_totals["failure"].get(category, 0),
                )
                + append_totals.get(category, 0)
            )
            for category in (
                set(checked_arm_allocations[slot]) | {"scratch"}
            )
        }

    workload = formal_record["arm_workload_contract"]
    expected_workload_fields = {
        "allocation_formula",
        "allocation_margin_bytes",
        "branch_contract",
        "hard_limits",
        "historical_size_planning_input",
        "independent_failure_closeout_reserve",
        "model_export_contract",
        "per_file_cap_derivation",
        "required_category_bytes",
        "scratch_contract",
    }
    first_slot = sorted(_FORMAL_ARM_SLOTS)[0]
    expected_required = required_by_slot[first_slot]
    expected_margin = {
        category: checked_arm_allocations[first_slot].get(category, 0)
        - amount
        for category, amount in expected_required.items()
    }
    if (
        any(required != expected_required for required in required_by_slot.values())
        or any(amount < 0 for amount in expected_margin.values())
        or type(workload) is not dict
        or set(workload) != expected_workload_fields
        or workload["required_category_bytes"] != expected_required
        or workload["allocation_margin_bytes"] != expected_margin
        or workload["branch_contract"]
        != {
            "common": {"mutually_exclusive_with": []},
            "failure": {"mutually_exclusive_with": ["success"]},
            "success": {"mutually_exclusive_with": ["failure"]},
        }
        or type(workload["allocation_formula"]) is not str
        or not workload["allocation_formula"]
        or type(workload["historical_size_planning_input"]) is not dict
        or type(workload["per_file_cap_derivation"]) is not dict
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal arm workload aggregate arithmetic drifted",
        )
    hard_limits = cast(dict[str, object], workload["hard_limits"])
    failure_reserve = cast(
        dict[str, object],
        workload["independent_failure_closeout_reserve"],
    )
    model_export = cast(dict[str, object], workload["model_export_contract"])
    scratch_contract = cast(dict[str, object], workload["scratch_contract"])
    failure_cap = checked_arm_caps[first_slot][
        "organic arm failure record"
    ]
    if (
        type(hard_limits) is not dict
        or set(hard_limits)
        != {"maximum_attach_hooks", "maximum_generated_cuts"}
        or type(hard_limits["maximum_attach_hooks"]) is not dict
        or hard_limits["maximum_attach_hooks"].get("value") != 30
        or hard_limits["maximum_attach_hooks"].get("exhaustion")
        != "arm-consumed-incomplete"
        or type(hard_limits["maximum_generated_cuts"]) is not dict
        or hard_limits["maximum_generated_cuts"].get("value") != 128
        or hard_limits["maximum_generated_cuts"].get("exhaustion")
        != "fail before the first generated-cut write beyond the cap; "
        "arm-consumed-incomplete"
        or hard_limits["maximum_generated_cuts"].get("sufficiency_claim")
        is not False
        or failure_reserve
        != {
            "artifact_class": "closeout",
            "label": "organic arm failure record",
            "maximum_bytes": failure_cap["maximum_bytes"],
            "physical_accounting_branch": "common",
            "publication_branch": "failure",
            "release_policy": (
                "non-refundable; remains available after any partial or "
                "complete success-branch staging"
            ),
        }
        or model_export
        != {
            "cap_source": "attach model evidence.maximum_bytes",
            "export_open_mode": "O_TRUNC",
            "rlimit_fsize": (
                "set to the current model cap for each export and restore "
                "before any later publication"
            ),
            "sealed_memfd_required": True,
        }
        or scratch_contract
        != {
            "aggregate_allocation_bytes": 0,
            "known_retained_writer_count": 0,
            "tmp_directory_mode_octal": "0500",
            "write_attempt_result": "fail-closed",
        }
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal arm hard-limit or reserve contract drifted",
        )

    raw_directories = formal_record["fixed_directories"]
    if type(raw_directories) is not list:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal-root fixed directory table is absent",
        )
    directories: dict[str, str] = {}
    for index, raw in enumerate(cast(list[object], raw_directories)):
        if (
            type(raw) is not dict
            or set(raw) != {"mode_octal", "path"}
            or raw["mode_octal"] not in {"0500", "0700"}
        ):
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"formal fixed directory[{index}] is malformed",
            )
        relative = _budget_relative_path(
            raw["path"],
            label=f"formal fixed directory[{index}]",
            allow_dot=True,
        )
        if relative in directories:
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                "formal fixed directory table contains a duplicate",
            )
        directories[relative] = cast(str, raw["mode_octal"])
    if "." not in directories:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal-root directory itself is not preregistered",
        )
    for relative in directories:
        if relative == ".":
            continue
        parent = PurePosixPath(relative).parent.as_posix()
        if parent == ".":
            parent = "."
        if parent not in directories:
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"formal directory parent is not preregistered: {relative}",
            )

    fixed_claims = {category: 0 for category in fixed}
    claimed_targets: set[str] = set()
    raw_artifacts = formal_record["artifact_maxima"]
    if type(raw_artifacts) is not list or not raw_artifacts:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal fixed artifact table is absent",
        )
    artifact_labels: set[str] = set()
    for index, raw in enumerate(cast(list[object], raw_artifacts)):
        if (
            type(raw) is not dict
            or set(raw)
            != {
                "artifact_class",
                "label",
                "maximum_bytes",
                "path",
                "required_on_success",
            }
            or type(raw["label"]) is not str
            or not raw["label"]
            or raw["label"] in artifact_labels
            or type(raw["required_on_success"]) is not bool
            or type(raw["maximum_bytes"]) is not int
            or raw["maximum_bytes"] <= 0
            or type(raw["artifact_class"]) is not str
            or raw["artifact_class"] not in fixed_claims
        ):
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"formal artifact[{index}] is malformed",
            )
        artifact_labels.add(cast(str, raw["label"]))
        target = _budget_relative_path(
            raw["path"],
            label=f"formal artifact[{index}].path",
        )
        parent = PurePosixPath(target).parent.as_posix()
        if parent not in directories or target in claimed_targets:
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"formal artifact target is not uniquely preregistered: {target}",
            )
        claimed_targets.add(target)
        fixed_claims[cast(str, raw["artifact_class"])] += cast(
            int,
            raw["maximum_bytes"],
        )

    raw_channels = formal_record["append_channels"]
    if type(raw_channels) is not list or len(raw_channels) != 2:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal append-channel table is not exact",
        )
    expected_formal_channels = (
        (
            "ab16-baseline-rebuild-cuts",
            "AB16 baseline cut segment",
            "ledger",
            1024**2,
            128,
            "prospective/baseline/checkpoint/benders-cuts",
        ),
        (
            "budget-journal",
            "AB16 formal budget journal segment",
            "metadata",
            4096,
            16_384,
            "channels/budget-journal",
        ),
    )
    for index, (
        raw_channel,
        (
            expected_channel,
            expected_label,
            expected_class,
            expected_maximum,
            expected_segments,
            expected_parent,
        ),
    ) in enumerate(
        zip(
            cast(list[object], raw_channels),
            expected_formal_channels,
            strict=True,
        )
    ):
        if (
            type(raw_channel) is not dict
            or set(raw_channel)
            != {
                "artifact_class",
                "channel",
                "label",
                "maximum_bytes",
                "maximum_segments",
                "multiplicity_derivation",
                "parent_path",
            }
            or raw_channel["channel"] != expected_channel
            or raw_channel["label"] != expected_label
            or raw_channel["artifact_class"] != expected_class
            or raw_channel["maximum_bytes"] != expected_maximum
            or raw_channel["maximum_segments"] != expected_segments
            or raw_channel["parent_path"] != expected_parent
            or type(raw_channel["multiplicity_derivation"]) is not dict
            or raw_channel["multiplicity_derivation"].get(
                "result_maximum_segments"
            )
            != expected_segments
            or type(
                raw_channel["multiplicity_derivation"].get("basis")
            )
            is not str
            or not raw_channel["multiplicity_derivation"]["basis"]
            or raw_channel["multiplicity_derivation"].get(
                "evidence_status"
            )
            != "unmeasured-temporary"
            or expected_class not in fixed_claims
        ):
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"formal append channel[{index}] is malformed",
            )
        channel_parent = _budget_relative_path(
            raw_channel["parent_path"],
            label=f"formal append channel[{index}] parent",
        )
        if channel_parent not in directories:
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                "formal append channel parent is not preregistered",
            )
        fixed_claims[expected_class] += (
            expected_maximum * expected_segments
        )

    raw_reservations = formal_record["fixed_purpose_reservations"]
    if type(raw_reservations) is not list:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal fixed reservation table is absent",
        )
    purposes: set[str] = set()
    expected_campaign_root_reservations = {
        (
            "failure-terminal-release",
            "failure-terminal-release.json",
        ),
        (
            "formal-root-replay-alternate-receipt",
            "formal-root-replay-alternate.json",
        ),
        (
            "formal-root-replay-primary-receipt",
            "formal-root-replay-primary.json",
        ),
        (
            "success-dual-lock-release",
            "dual-lock-release.json",
        ),
    }
    observed_campaign_root_reservations: set[tuple[str, str]] = set()
    for index, raw in enumerate(cast(list[object], raw_reservations)):
        if (
            type(raw) is not dict
            or set(raw)
            != {
                "artifact_class",
                "maximum_bytes",
                "parent_path",
                "parent_scope",
                "purpose",
                "target_name",
            }
            or type(raw["purpose"]) is not str
            or not raw["purpose"]
            or raw["purpose"] in purposes
            or type(raw["maximum_bytes"]) is not int
            or raw["maximum_bytes"] <= 0
            or type(raw["artifact_class"]) is not str
            or raw["artifact_class"] not in fixed_claims
            or raw["parent_scope"] not in {"campaign-root", "formal-root"}
            or type(raw["target_name"]) is not str
            or PurePosixPath(raw["target_name"]).name != raw["target_name"]
            or raw["target_name"] in {"", ".", ".."}
        ):
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"formal reservation[{index}] is malformed",
            )
        purposes.add(cast(str, raw["purpose"]))
        parent = _budget_relative_path(
            raw["parent_path"],
            label=f"formal reservation[{index}].parent_path",
            allow_dot=True,
        )
        parent_scope = cast(str, raw["parent_scope"])
        target = (
            cast(str, raw["target_name"])
            if parent == "."
            else f"{parent}/{raw['target_name']}"
        )
        namespaced_target = (
            target
            if parent_scope == "formal-root"
            else f"campaign-root:{target}"
        )
        if (
            (
                parent_scope == "formal-root"
                and parent not in directories
            )
            or (
                parent_scope == "campaign-root"
                and (
                    parent != "formal-ab16/final-release"
                    or (
                        cast(str, raw["purpose"]),
                        cast(str, raw["target_name"]),
                    )
                    not in expected_campaign_root_reservations
                )
            )
            or namespaced_target in claimed_targets
        ):
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                f"formal reservation target is not uniquely preregistered: {target}",
            )
        claimed_targets.add(namespaced_target)
        if parent_scope == "campaign-root":
            observed_campaign_root_reservations.add(
                (
                    cast(str, raw["purpose"]),
                    cast(str, raw["target_name"]),
                )
            )
        fixed_claims[cast(str, raw["artifact_class"])] += cast(
            int,
            raw["maximum_bytes"],
        )
    if (
        observed_campaign_root_reservations
        != expected_campaign_root_reservations
    ):
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "campaign-root final-release reservation set drifted",
        )
    if directories.get("prospective/baseline/tmp") != "0500":
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal aggregate scratch directory is not sealed before launch",
        )
    # The one formal-root scratch pool is physical headroom rather than a
    # publishable artifact.  Its 64 MiB aggregate is enforced by the broker
    # category ledger and the initially non-writable TMPDIR boundary.
    fixed_claims["scratch"] = fixed_claims.get("scratch", 0) + 64 * 1024**2
    if fixed_claims != fixed:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "fixed targets/channels do not exactly consume fixed overhead",
        )

    aggregate = sum(root_limits.values())
    if aggregate <= 0:
        _fail(
            "FORMAL_BUDGET_PROFILE_REQUIRED",
            "formal-root aggregate budget is empty",
        )
    # Preallocated staging extents make payload allocation bounded by the
    # broker total.  Retain a deterministic 10% filesystem/metadata allowance,
    # never below 64 MiB, without inflating the workload to per-file caps.
    filesystem_uncertainty = max(64 * 1024**2, (aggregate + 9) // 10)
    host_reserve = 4 * GIB
    return {
        "aggregate_budget_bytes": aggregate,
        "budget_profile_identity": identity,
        "budget_profile_internal_sha256": recorded_internal_sha,
        "category_limits": root_limits,
        "filesystem_uncertainty_bytes": filesystem_uncertainty,
        "host_reserve_bytes": host_reserve,
        "minimum_available_bytes": aggregate
        + filesystem_uncertainty
        + host_reserve,
        "profile_id": profile["profile_id"],
    }


def _validated_prospective_dimension(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    expected = {
        "availability_rule",
        "basis_class",
        "basis_detail",
        "host_reserve_bytes",
        "minimum_available_bytes",
        "predicted_peak_bytes",
        "safety_margin_bytes",
    }
    if type(value) is not dict or set(value) != expected:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label} field set drifted")
    record = cast(dict[str, object], value)
    for field in ("basis_class", "basis_detail", "availability_rule"):
        if type(record[field]) is not str or not record[field]:
            _fail("RESOURCE_PROFILE_UNTRUSTED", f"{label}.{field} is malformed")
    predicted = _exact_nonnegative_int(
        record["predicted_peak_bytes"],
        f"{label}.predicted_peak_bytes",
    )
    margin = _exact_nonnegative_int(
        record["safety_margin_bytes"],
        f"{label}.safety_margin_bytes",
    )
    reserve = _exact_nonnegative_int(
        record["host_reserve_bytes"],
        f"{label}.host_reserve_bytes",
    )
    minimum = _exact_nonnegative_int(
        record["minimum_available_bytes"],
        f"{label}.minimum_available_bytes",
    )
    rule = record["availability_rule"]
    expected_minimum = (
        predicted + margin + reserve
        if rule == "INDEPENDENT_MINIMUM"
        else 0
        if rule == "COMBINED_RAM_LIMITED_SWAP"
        else -1
    )
    if minimum != expected_minimum:
        _fail(
            "RESOURCE_PROFILE_UNTRUSTED",
            f"{label} availability arithmetic drifted",
        )
    return dict(record)


def _validated_prospective_profile(
    stage: str,
    *,
    enforced_budget_profile: Mapping[str, object] | None,
    enforced_budget_profile_identity: Mapping[str, object] | None,
) -> dict[str, object]:
    if stage == FORMAL_ORGANIC_ARM:
        if (
            enforced_budget_profile is None
            or enforced_budget_profile_identity is None
        ):
            _fail(
                "FORMAL_BUDGET_PROFILE_REQUIRED",
                "formal v2 admission requires an exact launch-ready budget profile",
            )
        disk_binding = derive_formal_disk_requirement(
            enforced_budget_profile=enforced_budget_profile,
            enforced_budget_profile_identity=enforced_budget_profile_identity,
        )
        value = _prospective_profile(
            profile_id="ab16-formal-organic-arm-budget-bound-temporary-v2",
            stage=FORMAL_ORGANIC_ARM,
            basis=_basis(
                comparable_to_stage=False,
                evidence_class="BUDGET_BOUNDED_TEMPORARY_PROFILE",
                historical_observations=(_HISTORICAL_FORMAL_PLANNING_PROXY,),
                prediction_method=(
                    "use the 24 GiB planning proxy plus 4 GiB memory error; "
                    "admit swap only as RAM-complement capacity capped by "
                    "MemorySwapMax; derive disk from the launch-ready single "
                    "formal-root aggregate escrow plus deterministic filesystem "
                    "uncertainty and an independent host reserve"
                ),
            ),
            memory=_prospective_dimension(
                24 * GIB,
                4 * GIB,
                8 * GIB,
                basis_class="HETEROGENEOUS_PLANNING_PROXY",
                basis_detail="24 GiB planning proxy plus 4 GiB explicit uncertainty",
            ),
            swap=_prospective_dimension(
                0,
                4 * GIB,
                4 * GIB,
                basis_class="COMPOSITIONAL_RAM_SWAP_CAPACITY",
                basis_detail=(
                    "swap has no independent availability floor; after a 4 GiB "
                    "host reserve it may contribute only up to MemorySwapMax"
                ),
                availability_rule="COMBINED_RAM_LIMITED_SWAP",
            ),
            disk=_prospective_dimension(
                _exact_nonnegative_int(
                    disk_binding["aggregate_budget_bytes"],
                    "formal aggregate budget",
                ),
                _exact_nonnegative_int(
                    disk_binding["filesystem_uncertainty_bytes"],
                    "formal filesystem uncertainty",
                ),
                _exact_nonnegative_int(
                    disk_binding["host_reserve_bytes"],
                    "formal disk host reserve",
                ),
                basis_class="ENFORCED_FORMAL_ROOT_AGGREGATE_BUDGET",
                basis_detail=(
                    "single broker aggregate category limits plus max(64 MiB, "
                    "ceil(10%)) filesystem uncertainty"
                ),
            ),
            runtime_safety_limits=_FORMAL_CGROUP_LIMITS,
            budget_binding=disk_binding,
        )
    else:
        if (
            enforced_budget_profile is not None
            or enforced_budget_profile_identity is not None
        ):
            _fail(
                "RESOURCE_PROFILE_UNTRUSTED",
                "non-formal v2 admission received a formal budget profile",
            )
        if stage not in _PROSPECTIVE_STATIC_PROFILES:
            _fail("RESOURCE_PROFILE_UNKNOWN", f"unknown AB16 resource stage {stage!r}")
        value = deepcopy(_PROSPECTIVE_STATIC_PROFILES[stage])

    unhashed = dict(value)
    recorded_sha = unhashed.pop("profile_sha256", None)
    if (
        type(recorded_sha) is not str
        or _canonical_sha256(unhashed) != recorded_sha
        or value.get("profile_set_id") != PROSPECTIVE_PROFILE_SET_ID
        or value.get("stage") != stage
    ):
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} prospective profile drifted")
    requirements = value.get("requirements")
    if type(requirements) is not dict or set(requirements) != {"disk", "memory", "swap"}:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} requirement set drifted")
    checked_requirements = {
        dimension: _validated_prospective_dimension(
            cast(dict[str, object], requirements)[dimension],
            label=f"{stage}.{dimension}",
        )
        for dimension in ("disk", "memory", "swap")
    }
    limits = _validate_runtime_limits(
        value.get("runtime_safety_limits"),
        f"{stage}.runtime_safety_limits",
    )
    if stage == FORMAL_ORGANIC_ARM:
        if limits != _FORMAL_CGROUP_LIMITS:
            _fail("RESOURCE_PROFILE_UNTRUSTED", "formal cgroup limits drifted")
        if (
            checked_requirements["swap"]["availability_rule"]
            != "COMBINED_RAM_LIMITED_SWAP"
        ):
            _fail("RESOURCE_PROFILE_UNTRUSTED", "formal swap is not compositional")
    elif limits != _NO_CGROUP_LIMITS:
        _fail("RESOURCE_PROFILE_UNTRUSTED", f"{stage} unexpectedly has cgroup limits")
    return deepcopy(value)


def _calibration_identity(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"}:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            f"{label} identity field set drifted",
        )
    record = cast(dict[str, object], value)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or len(record["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in record["sha256"])
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            f"{label} identity is malformed",
        )
    return dict(record)


def _calibration_tool_content_identity(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) not in (
        {"sha256", "size_bytes"},
        {"mode", "sha256", "size_bytes"},
    ):
        _fail(
            "CALIBRATION_TOOL_IDENTITY_INVALID",
            f"{label} content identity field set drifted",
        )
    record = cast(dict[str, object], value)
    if (
        type(record["sha256"]) is not str
        or len(record["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in record["sha256"])
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] <= 0
        or (
            "mode" in record
            and (
                type(record["mode"]) is not int
                or cast(int, record["mode"]) < 0
                or cast(int, record["mode"]) > 0o7777
            )
        )
    ):
        _fail("CALIBRATION_TOOL_IDENTITY_INVALID", label)
    return dict(record)


def _validated_calibration_tool_identity_map(
    value: Mapping[str, Mapping[str, object]] | None,
) -> dict[str, dict[str, object]]:
    if value is None or set(value) != CALIBRATION_TOOL_ROLES:
        _fail(
            "CALIBRATION_TOOL_IDENTITY_INVALID",
            "externally pinned calibration tool role set is not exact",
        )
    return {
        role: _calibration_tool_content_identity(identity, label=role)
        for role, identity in sorted(value.items())
    }


_CALIBRATION_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | os.O_CLOEXEC
    | os.O_DIRECTORY
    | getattr(os, "O_NOFOLLOW", 0)
)
_CALIBRATION_REGULAR_FLAGS = (
    os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
)


def _open_calibration_absolute_directory(path: Path, *, label: str) -> int:
    if path != path.absolute() or not path.is_absolute():
        _fail("CALIBRATION_EVIDENCE_PATH_INVALID", f"{label} is not absolute")
    opened = [os.open("/", _CALIBRATION_DIRECTORY_FLAGS)]
    primary: BaseException | None = None
    try:
        for component in path.parts[1:]:
            if component in {"", ".", ".."}:
                _fail(
                    "CALIBRATION_EVIDENCE_PATH_INVALID",
                    f"{label} contains an unsafe component",
                )
            opened.append(
                os.open(
                    component,
                    _CALIBRATION_DIRECTORY_FLAGS,
                    dir_fd=opened[-1],
                )
            )
    except BaseException as exc:
        primary = exc
    result = opened[-1] if primary is None else -1
    for descriptor in reversed(
        opened[:-1] if primary is None else opened
    ):
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    f"{label} directory cleanup failed: {close_error}"
                )
    if primary is not None:
        if result >= 0:
            try:
                os.close(result)
            except BaseException as close_error:
                primary.add_note(
                    f"{label} retained directory cleanup failed: {close_error}"
                )
        raise primary
    return result


def _open_calibration_identity_fd(
    identity: Mapping[str, object],
    *,
    label: str,
) -> int:
    checked = _calibration_identity(identity, label=label)
    path = Path(cast(str, checked["path"]))
    parent = _open_calibration_absolute_directory(
        path.parent,
        label=f"{label} parent",
    )
    descriptor = -1
    primary: BaseException | None = None
    try:
        descriptor = os.open(
            path.name,
            _CALIBRATION_REGULAR_FLAGS,
            dir_fd=parent,
        )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            _fail(
                "CALIBRATION_EVIDENCE_IDENTITY_DRIFT",
                f"{label} is not a single-linked regular file",
            )
        digest = hashlib.sha256()
        offset = 0
        while offset < before.st_size:
            block = os.pread(
                descriptor,
                min(1024 * 1024, before.st_size - offset),
                offset,
            )
            if not block:
                _fail(
                    "CALIBRATION_EVIDENCE_IDENTITY_DRIFT",
                    f"{label} short read",
                )
            digest.update(block)
            offset += len(block)
        after = os.fstat(descriptor)
        def signature(value: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
            return (
                value.st_dev,
                value.st_ino,
                value.st_mode,
                value.st_nlink,
                value.st_size,
                value.st_mtime_ns,
                value.st_ctime_ns,
            )
        if (
            signature(before) != signature(after)
            or before.st_size != checked["size_bytes"]
            or digest.hexdigest() != checked["sha256"]
        ):
            _fail(
                "CALIBRATION_EVIDENCE_IDENTITY_DRIFT",
                f"{label} bytes changed",
            )
        rejoined_parent = _open_calibration_absolute_directory(
            path.parent,
            label=f"{label} final parent",
        )
        rejoined_file = -1
        try:
            if (
                os.fstat(parent).st_dev,
                os.fstat(parent).st_ino,
            ) != (
                os.fstat(rejoined_parent).st_dev,
                os.fstat(rejoined_parent).st_ino,
            ):
                _fail(
                    "CALIBRATION_EVIDENCE_IDENTITY_DRIFT",
                    f"{label} parent drifted",
                )
            rejoined_file = os.open(
                path.name,
                _CALIBRATION_REGULAR_FLAGS,
                dir_fd=rejoined_parent,
            )
            named = os.fstat(rejoined_file)
            if (named.st_dev, named.st_ino) != (after.st_dev, after.st_ino):
                _fail(
                    "CALIBRATION_EVIDENCE_IDENTITY_DRIFT",
                    f"{label} final path does not name the retained inode",
                )
        finally:
            if rejoined_file >= 0:
                os.close(rejoined_file)
            os.close(rejoined_parent)
    except BaseException as exc:
        primary = exc
    try:
        os.close(parent)
    except BaseException as close_error:
        if primary is None:
            primary = close_error
        else:
            primary.add_note(f"{label} parent close failed: {close_error}")
    if primary is not None:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException as close_error:
                primary.add_note(f"{label} descriptor close failed: {close_error}")
        raise primary
    return descriptor


def _read_calibration_identity_bytes(
    identity: Mapping[str, object],
    *,
    label: str,
) -> bytes:
    try:
        descriptor = _open_calibration_identity_fd(identity, label=label)
    except OSError as exc:
        _fail(
            "CALIBRATION_EVIDENCE_OPEN_FAILED",
            f"{label}: {exc}",
        )
    primary: BaseException | None = None
    try:
        metadata = os.fstat(descriptor)
        raw = os.pread(descriptor, metadata.st_size + 1, 0)
        if len(raw) != metadata.st_size:
            _fail(
                "CALIBRATION_EVIDENCE_IDENTITY_DRIFT",
                f"{label} size drifted",
            )
    except BaseException as exc:
        primary = exc
        raw = b""
    try:
        os.close(descriptor)
    except BaseException as close_error:
        if primary is None:
            raise
        primary.add_note(f"{label} descriptor close failed: {close_error}")
    if primary is not None:
        raise primary
    return raw


def _load_calibration_tool_from_fd(
    descriptor: int,
    *,
    module_name: str,
) -> ModuleType:
    origin = f"/proc/self/fd/{descriptor}"
    spec = importlib.util.spec_from_loader(
        module_name,
        SourceFileLoader(module_name, origin),
        origin=origin,
    )
    if spec is None or spec.loader is None:
        _fail("CALIBRATION_TOOL_LOAD_FAILED", module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _require_tool_content_pin(
    site_identity: Mapping[str, object],
    expected_content_identity: Mapping[str, object],
    *,
    label: str,
) -> int:
    descriptor = _open_calibration_identity_fd(site_identity, label=label)
    try:
        metadata = os.fstat(descriptor)
        raw = os.pread(descriptor, metadata.st_size + 1, 0)
        actual: dict[str, object] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        expected = _calibration_tool_content_identity(
            expected_content_identity,
            label=label,
        )
        if "mode" in expected:
            actual["mode"] = stat.S_IMODE(metadata.st_mode)
        if actual != expected:
            _fail(
                "CALIBRATION_TOOL_IDENTITY_DRIFT",
                f"{label} differs from the external content pin",
            )
    except BaseException as exc:
        try:
            os.close(descriptor)
        except BaseException as close_error:
            exc.add_note(f"{label} cleanup failed: {close_error}")
        raise
    return descriptor


def _strict_calibration_json(raw: bytes, *, label: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in items:
            if key in result:
                _fail(
                    "CALIBRATION_EVIDENCE_JSON_INVALID",
                    f"{label}: duplicate key {key!r}",
                )
            result[key] = item
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: _fail(
                "CALIBRATION_EVIDENCE_JSON_INVALID",
                f"{label}: {token}",
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("CALIBRATION_EVIDENCE_JSON_INVALID", f"{label}: {exc}")
    if type(value) is not dict or _canonical_json_bytes(value) != raw:
        _fail(
            "CALIBRATION_EVIDENCE_JSON_INVALID",
            f"{label} is not canonical JSON",
        )
    return cast(dict[str, object], value)


def _validated_calibration_execution_surface(
    value: object,
    *,
    stage: str,
    profile_identity: Mapping[str, object],
) -> dict[str, object]:
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
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution surface field set drifted",
        )
    surface = cast(dict[str, object], value)
    digest = surface["execution_surface_sha256"]
    if (
        surface["schema_version"] != CALIBRATION_EXECUTION_SURFACE_SCHEMA
        or surface["stage"] != stage
        or type(digest) is not str
        or type(surface["execution_site_receipt_sha256"]) is not str
        or len(cast(str, surface["execution_site_receipt_sha256"])) != 64
        or type(surface["working_directory"]) is not str
        or not Path(surface["working_directory"]).is_absolute()
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution surface identity/digest drifted",
        )
    command = surface["command"]
    if (
        type(command) is not list
        or not command
        or any(type(item) is not str or not item for item in command)
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution command is malformed",
        )
    controls = surface["control_plane_identities"]
    members = surface["execution_member_identities"]
    portable = surface["portable_package"]
    if type(controls) is not dict or type(members) is not dict:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution byte identity maps are malformed",
        )
    checked_controls = {
        label: _calibration_identity(identity, label=f"control {label}")
        for label, identity in cast(dict[object, object], controls).items()
        if type(label) is str and label
    }
    checked_members = {
        label: _calibration_identity(identity, label=f"member {label}")
        for label, identity in cast(dict[object, object], members).items()
        if type(label) is str and label
    }
    if (
        len(checked_controls) != len(controls)
        or len(checked_members) != len(members)
        or not {"code_assets", "profile", "project_lock"} <= set(checked_controls)
        or checked_controls["profile"] != profile_identity
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution byte identity/profile join drifted",
        )
    # The content-only execution digest is deliberately stable across sites,
    # but acceptance belongs to this exact candidate site.  Reopen every
    # recorded execution/control member through the descriptor-relative,
    # no-symlink stable-reader before accepting the site receipt.  Otherwise a
    # later clean commit could change PROJECT_LOCK, code-assets, preflight, or
    # another executed member while retaining an old three-sample cohort.
    for label, identity in sorted(
        {**checked_controls, **checked_members}.items()
    ):
        _read_calibration_identity_bytes(
            identity,
            label=f"execution-site member {label}",
        )
    if (
        type(portable) is not dict
        or set(portable)
        != {
            "host_runtime_content_sha256",
            "layout",
            "package_receipt_identity",
            "package_schema_version",
            "source_sets_sha256",
        }
        or portable["layout"] != CALIBRATION_PORTABLE_PACKAGE_LAYOUT
        or portable["package_schema_version"] != CALIBRATION_PACKAGE_SCHEMA
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "portable package closure shape drifted",
        )
    package_receipt = _calibration_identity(
        portable["package_receipt_identity"],
        label="portable package receipt",
    )
    if Path(cast(str, package_receipt["path"])).name != "receipt.json":
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "portable package receipt path is not fixed",
        )
    for field in ("host_runtime_content_sha256", "source_sets_sha256"):
        if (
            type(portable[field]) is not str
            or len(cast(str, portable[field])) != 64
            or any(
                character not in "0123456789abcdef"
                for character in cast(str, portable[field])
            )
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"portable package {field} is malformed",
            )
    executable_role = next(
        (
            label
            for label, identity in {**checked_members, **checked_controls}.items()
            if identity["path"] == command[0]
        ),
        None,
    )
    if executable_role is None:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution command executable is absent from its byte map",
        )
    inventory = surface["test_inventory"]
    worker = surface["worker"]
    if (
        type(inventory) is not dict
        or set(inventory) != {"collection_count", "collection_sha256"}
        or type(inventory["collection_count"]) is not int
        or inventory["collection_count"] < 0
        or type(inventory["collection_sha256"]) is not str
        or len(inventory["collection_sha256"]) != 64
        or type(worker) is not dict
        or set(worker) != {"count", "mode", "xdist_available"}
        or type(worker["count"]) is not int
        or worker["count"] <= 0
        or type(worker["xdist_available"]) is not bool
        or type(worker["mode"]) is not str
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution inventory/worker fingerprint is malformed",
        )
    fidelity = surface["workload_fidelity"]
    if (
        type(fidelity) is not dict
        or set(fidelity) != {"class", "launch_admissible"}
        or type(fidelity["class"]) is not str
        or not fidelity["class"]
        or type(fidelity["launch_admissible"]) is not bool
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "workload fidelity declaration is malformed",
        )
    stable_surface = {
        "command": {
            "arguments": command[1:],
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
            "host_runtime_content_sha256": portable[
                "host_runtime_content_sha256"
            ],
            "layout": CALIBRATION_PORTABLE_PACKAGE_LAYOUT,
            "package_receipt_content_identity": {
                "sha256": package_receipt["sha256"],
                "size_bytes": package_receipt["size_bytes"],
            },
            "package_schema_version": CALIBRATION_PACKAGE_SCHEMA,
            "source_sets_sha256": portable["source_sets_sha256"],
        },
        "schema_version": CALIBRATION_EXECUTION_SURFACE_SCHEMA,
        "stage": stage,
        "test_inventory": dict(cast(dict[str, object], inventory)),
        "worker": dict(cast(dict[str, object], worker)),
        "workload_fidelity": dict(cast(dict[str, object], fidelity)),
        "working_directory_role": "repository-root",
    }
    site_receipt = {
        "command": list(cast(list[str], command)),
        "control_plane_identities": checked_controls,
        "execution_member_identities": checked_members,
        "portable_package": {
            **portable,
            "package_receipt_identity": package_receipt,
        },
        "working_directory": surface["working_directory"],
    }
    if (
        digest != hashlib.sha256(_canonical_json_bytes(stable_surface)).hexdigest()
        or surface["execution_site_receipt_sha256"]
        != hashlib.sha256(_canonical_json_bytes(site_receipt)).hexdigest()
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "stable execution surface or site receipt digest drifted",
        )
    if stage == FULL_PREFLIGHT:
        if (
            len(command) != 3
            or command[1:] != ["scripts/preflight_gate.py", "--full"]
            or inventory["collection_count"] <= 0
            or worker["mode"] != "pytest-xdist-auto"
            or worker["xdist_available"] is not True
            or worker["count"] <= 1
        ):
            _fail(
                "CALIBRATION_EXECUTION_MODE_PROFILE_MISSING",
                "only the exact xdist full-preflight profile is installed",
            )
    elif (
        inventory["collection_count"] != 0
        or inventory["collection_sha256"] != hashlib.sha256(b"").hexdigest()
        or worker
        != {
            "count": 1,
            "mode": "single-worker",
            "xdist_available": False,
        }
    ):
        _fail(
            "CALIBRATION_EXECUTION_MODE_PROFILE_MISSING",
            f"{stage} calibration is not the fixed single-worker execution",
        )
    if fidelity["launch_admissible"] is not True:
        _fail(
            "CALIBRATION_WORKLOAD_NOT_LAUNCH_COMPARABLE",
            (
                f"{stage} calibration workload is explicitly "
                f"{fidelity['class']!r}, not the exact launch workload"
            ),
        )
    return deepcopy(surface)


def _verify_calibration_portable_package(
    surface: Mapping[str, object],
    *,
    stage: str,
    expected_tools: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Replay the package named by the surface and join all pinned role bytes."""

    members = cast(dict[str, object], surface["execution_member_identities"])
    portable = cast(dict[str, object], surface["portable_package"])
    host_verifier_identity = members.get("calibration_package_verifier_host")
    if type(host_verifier_identity) is not dict:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution surface omits the independently pinned package verifier",
        )
    verifier_fd = _require_tool_content_pin(
        cast(dict[str, object], host_verifier_identity),
        expected_tools["package_verifier"],
        label="independent calibration package verifier",
    )
    package: Any | None = None
    retained: list[int] = []
    primary: BaseException | None = None
    try:
        verifier = _load_calibration_tool_from_fd(
            verifier_fd,
            module_name=(
                "_ab16_calibration_admission_package_verifier_"
                f"{os.getpid()}_{id(surface)}"
            ),
        )
        receipt_identity = cast(
            dict[str, object],
            portable["package_receipt_identity"],
        )
        package_root = Path(cast(str, receipt_identity["path"])).parent
        package = verifier.RetainedCalibrationPackage.open(
            package_root,
            expected_receipt_identity=receipt_identity,
        )
        receipt = package.receipt
        host_runtime_content = {
            label: {
                "sha256": identity["sha256"],
                "size_bytes": identity["size_bytes"],
            }
            for label, identity in sorted(
                cast(
                    dict[str, dict[str, object]],
                    receipt["host_runtime_identities"],
                ).items()
            )
        }
        if (
            receipt["schema_version"] != CALIBRATION_PACKAGE_SCHEMA
            or receipt["layout"] != CALIBRATION_PORTABLE_PACKAGE_LAYOUT
            or hashlib.sha256(
                _canonical_json_bytes(receipt["source_sets"])
            ).hexdigest()
            != portable["source_sets_sha256"]
            or hashlib.sha256(
                _canonical_json_bytes(host_runtime_content)
            ).hexdigest()
            != portable["host_runtime_content_sha256"]
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                "portable package closure differs from the execution surface",
            )

        role_labels = {
            "aggregator": "calibration-aggregator",
            "alternate_replayer": "calibration-alternate-replay",
            "fd_loader": "calibration-fd-loader",
            "observer_harness": "calibration-observer",
            "package_verifier": "calibration-package-verifier",
            "primary_replayer": "calibration-primary-replay",
            "protocol": "calibration-protocol",
            "runner": "calibration-runner",
            "workload": "calibration-workload",
        }
        role_member_labels = {
            "fd_loader": "calibration_fd_loader",
            "observer_harness": "calibration_observer",
            "package_verifier": "calibration_package_verifier",
            "protocol": "calibration_protocol",
            "runner": "calibration_runner",
            "workload": "calibration_workload",
        }
        package_root_path = Path(
            cast(str, receipt_identity["path"])
        ).parent
        package_roles = cast(dict[str, str], receipt["roles"])
        package_identities = cast(
            dict[str, dict[str, object]],
            receipt["member_identities"],
        )
        for tool_role, package_role in role_labels.items():
            descriptor = package.open_role(package_role)
            retained.append(descriptor)
            metadata = os.fstat(descriptor)
            raw = os.pread(descriptor, metadata.st_size + 1, 0)
            actual_content: dict[str, object] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
            expected_content = expected_tools[tool_role]
            if "mode" in expected_content:
                actual_content["mode"] = stat.S_IMODE(metadata.st_mode)
            if actual_content != expected_content:
                _fail(
                    "CALIBRATION_TOOL_IDENTITY_DRIFT",
                    f"portable package role differs: {tool_role}",
                )
            surface_label = role_member_labels.get(tool_role)
            if surface_label is None:
                continue
            site_identity = members.get(surface_label)
            package_relative = package_roles[package_role]
            expected_site_identity = {
                **package_identities[package_relative],
                "path": str(package_root_path / package_relative),
            }
            if site_identity != expected_site_identity:
                _fail(
                    "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                    f"surface/package role join differs: {surface_label}",
                )

        fixture_fd = package.open_fixture(stage)
        retained.append(fixture_fd)
        fixture_relative = cast(
            dict[str, str],
            receipt["stage_fixtures"],
        )[stage]
        expected_fixture_identity = {
            **package_identities[fixture_relative],
            "path": str(package_root_path / fixture_relative),
        }
        if members.get("calibration_stage_fixture") != expected_fixture_identity:
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                "surface/package stage fixture join differs",
            )
        runtime = cast(dict[str, object], receipt["runtime_layout"])
        python_relative = cast(str, runtime["python_relative_path"])
        expected_python_identity = {
            **package_identities[python_relative],
            "path": str(package_root_path / python_relative),
        }
        if members.get("python_interpreter") != expected_python_identity:
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                "surface/package Python interpreter join differs",
            )
        return deepcopy(receipt)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        for descriptor in reversed(retained):
            try:
                os.close(descriptor)
            except BaseException as close_error:
                if primary is None:
                    raise
                primary.add_note(
                    "portable package role cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if package is not None:
            try:
                package.close()
            except BaseException as close_error:
                if primary is None:
                    raise
                primary.add_note(
                    "portable package cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        try:
            os.close(verifier_fd)
        except BaseException as close_error:
            if primary is None:
                raise
            primary.add_note(
                "package verifier cleanup failed: "
                f"{type(close_error).__name__}: {close_error}"
            )


def validate_calibration_authorization_bundle(
    value: object,
    *,
    bundle_identity: Mapping[str, object],
    stage: str,
    expected_profile: Mapping[str, object],
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ] | None,
) -> dict[str, object]:
    """Validate the immutable three-sample/two-replay launch prerequisite."""

    fields = {
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
    }
    if type(value) is not dict or set(value) != fields:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "calibration authorization bundle field set drifted",
        )
    bundle = cast(dict[str, object], value)
    expected_tools = _validated_calibration_tool_identity_map(
        expected_calibration_tool_identities
    )
    if (
        bundle["schema_version"] != CALIBRATION_AUTHORIZATION_BUNDLE_SCHEMA
        or bundle["authority_scope"] != AUTHORITY_SCOPE
        or not _exact_tree_equal(
            bundle["authorizations"],
            PROSPECTIVE_FALSE_AUTHORIZATIONS,
        )
        or bundle["stage"] != stage
        or bundle["status"] != "ACCEPTED"
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "calibration authorization boundary drifted",
        )
    checked_bundle_identity = _calibration_identity(
        bundle_identity,
        label="calibration authorization bundle",
    )
    bundle_bytes = _canonical_json_bytes(bundle)
    actual_bundle = _strict_calibration_json(
        _read_calibration_identity_bytes(
            checked_bundle_identity,
            label="calibration authorization bundle",
        ),
        label="calibration authorization bundle",
    )
    if (
        not _exact_tree_equal(actual_bundle, bundle)
        or
        checked_bundle_identity["sha256"]
        != hashlib.sha256(bundle_bytes).hexdigest()
        or checked_bundle_identity["size_bytes"] != len(bundle_bytes)
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "calibration authorization bundle byte identity drifted",
        )
    profile_identity = _calibration_identity(
        bundle["profile_identity"],
        label="preinstalled resource profile",
    )
    profile_bytes = _canonical_json_bytes(expected_profile)
    actual_profile = _strict_calibration_json(
        _read_calibration_identity_bytes(
            profile_identity,
            label="preinstalled resource profile",
        ),
        label="preinstalled resource profile",
    )
    if (
        not _exact_tree_equal(actual_profile, expected_profile)
        or
        profile_identity["sha256"] != hashlib.sha256(profile_bytes).hexdigest()
        or profile_identity["size_bytes"] != len(profile_bytes)
        or bundle["profile_internal_sha256"]
        != expected_profile.get("profile_sha256")
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "preinstalled profile identity/internal SHA drifted",
        )
    surface = _validated_calibration_execution_surface(
        bundle["execution_surface"],
        stage=stage,
        profile_identity=profile_identity,
    )
    surface_sha = surface["execution_surface_sha256"]
    if bundle["execution_surface_sha256"] != surface_sha:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "execution surface join drifted",
        )
    # Full preflight intentionally executes the exact final candidate worktree;
    # its package closure is a cohort binding, not its execution root.  The two
    # package-executed stages must additionally replay and retain the named
    # portable package at the launch-admission join.
    if stage != FULL_PREFLIGHT:
        _verify_calibration_portable_package(
            surface,
            stage=stage,
            expected_tools=expected_tools,
        )
    aggregate_identity = _calibration_identity(
        bundle["aggregate_identity"],
        label="calibration aggregate",
    )
    samples = bundle["comparable_samples"]
    if type(samples) is not list or len(samples) != 3:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "calibration bundle lacks three comparable samples",
        )
    sample_ids: set[str] = set()
    sample_shas: set[str] = set()
    validation_shas: set[str] = set()
    cgroups: set[str] = set()
    for index, raw in enumerate(cast(list[object], samples)):
        if (
            type(raw) is not dict
            or set(raw)
            != {
                "sample_id",
                "sample_identity",
                "transient_cgroup",
                "validation_identity",
            }
            or type(raw["sample_id"]) is not str
            or not raw["sample_id"]
            or type(raw["transient_cgroup"]) is not str
            or not raw["transient_cgroup"].startswith("/")
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"comparable sample[{index}] is malformed",
            )
        sample_identity = _calibration_identity(
            raw["sample_identity"],
            label=f"sample {index}",
        )
        validation_identity = _calibration_identity(
            raw["validation_identity"],
            label=f"validation {index}",
        )
        sample_id = cast(str, raw["sample_id"])
        cgroup = cast(str, raw["transient_cgroup"])
        if (
            sample_id in sample_ids
            or sample_identity["sha256"] in sample_shas
            or validation_identity["sha256"] in validation_shas
            or cgroup in cgroups
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                "calibration sample bytes/cgroup were reused",
            )
        sample_ids.add(sample_id)
        sample_shas.add(cast(str, sample_identity["sha256"]))
        validation_shas.add(cast(str, validation_identity["sha256"]))
        cgroups.add(cgroup)

    candidate = bundle["profile_candidate_binding"]
    if (
        type(candidate) is not dict
        or set(candidate)
        != {
            "aggregate_identity",
            "execution_surface_sha256",
            "identity",
            "installed_profile_identity",
        }
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "profile candidate binding shape drifted",
        )
    candidate_identity = _calibration_identity(
        candidate["identity"],
        label="profile candidate",
    )
    if (
        candidate["aggregate_identity"] != aggregate_identity
        or candidate["installed_profile_identity"] != profile_identity
        or candidate["execution_surface_sha256"] != surface_sha
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "profile candidate binding drifted",
        )

    outside = bundle["outside_replays"]
    if type(outside) is not dict or set(outside) != {"alternate", "primary"}:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "outside replay implementation set drifted",
        )
    replay_records: list[dict[str, object]] = []
    replay_receipt_shas: set[str] = set()
    replay_tool_shas: set[str] = set()
    root_receipt_identity: dict[str, object] | None = None
    replay_results: dict[str, dict[str, object]] = {}
    for implementation, raw in sorted(cast(dict[str, object], outside).items()):
        if (
            type(raw) is not dict
            or set(raw) != {"receipt_identity", "record"}
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"{implementation} replay envelope drifted",
            )
        replay = raw["record"]
        replay_fields = {
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
        if type(replay) is not dict or set(replay) != replay_fields:
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"{implementation} replay record drifted",
            )
        replay_record = cast(dict[str, object], replay)
        if (
            replay_record["schema_version"] != CALIBRATION_OUTSIDE_REPLAY_SCHEMA
            or replay_record["authority_scope"] != AUTHORITY_SCOPE
            or replay_record["authorizations"] != PROSPECTIVE_FALSE_AUTHORIZATIONS
            or replay_record["conclusion"]
            != "REPLAY_ACCEPTED_PROFILE_CANDIDATE"
            or replay_record["status"] != "PASS_NO_LAUNCH_AUTHORITY"
            or replay_record["stage"] != stage
            or replay_record["execution_surface_sha256"] != surface_sha
            or replay_record["profile_candidate_identity"] != candidate_identity
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"{implementation} replay acceptance target drifted",
            )
        expected_slot = "replay-a" if implementation == "primary" else "replay-b"
        if replay_record["replay_slot"] != expected_slot:
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"{implementation} replay slot drifted",
            )
        tool_identity = _calibration_identity(
            replay_record["replay_tool_identity"],
            label=f"{implementation} replay tool",
        )
        replay_root = _calibration_identity(
            replay_record["root_receipt_identity"],
            label=f"{implementation} calibration root receipt",
        )
        if root_receipt_identity is None:
            root_receipt_identity = replay_root
        elif replay_root != root_receipt_identity:
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                "outside replays did not accept the same closed root",
            )
        receipt_identity = _calibration_identity(
            raw["receipt_identity"],
            label=f"{implementation} outside replay receipt",
        )
        replay_bytes = _canonical_json_bytes(replay_record)
        actual_replay_record = _strict_calibration_json(
            _read_calibration_identity_bytes(
                receipt_identity,
                label=f"{implementation} outside replay receipt",
            ),
            label=f"{implementation} outside replay receipt",
        )
        if (
            not _exact_tree_equal(actual_replay_record, replay_record)
            or
            receipt_identity["sha256"]
            != hashlib.sha256(replay_bytes).hexdigest()
            or receipt_identity["size_bytes"] != len(replay_bytes)
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"{implementation} replay receipt byte identity drifted",
            )
        expected_role = (
            "primary_replayer"
            if implementation == "primary"
            else "alternate_replayer"
        )
        tool_fd = _require_tool_content_pin(
            tool_identity,
            expected_tools[expected_role],
            label=f"{implementation} outside replay tool",
        )
        replay_error: BaseException | None = None
        try:
            replay_module = _load_calibration_tool_from_fd(
                tool_fd,
                module_name=(
                    "_ab16_calibration_admission_replay_"
                    f"{implementation}_{os.getpid()}_{id(bundle)}"
                ),
            )
            replay_root_path = Path(cast(str, replay_root["path"])).parent
            if (
                Path(cast(str, replay_root["path"])).name != "receipt.json"
                or not replay_root_path.is_absolute()
            ):
                _fail(
                    "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                    "outside replay root receipt path is not fixed",
                )
            replay_result = replay_module.replay(replay_root_path)
            if type(replay_result) is not dict:
                _fail(
                    "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                    f"{implementation} replay did not return an object",
                )
            replay_results[implementation] = dict(replay_result)
        except BaseException as exc:
            if isinstance(exc, ResourceAdmissionError):
                replay_error = exc
            else:
                replay_error = ResourceAdmissionError(
                    "CALIBRATION_INDEPENDENT_REPLAY_FAILED",
                    f"{implementation}: {type(exc).__name__}: {exc}",
                )
        try:
            os.close(tool_fd)
        except BaseException as close_error:
            if replay_error is None:
                raise
            replay_error.add_note(
                f"{implementation} replay tool close failed: {close_error}"
            )
        if replay_error is not None:
            raise replay_error
        replay_receipt_shas.add(cast(str, receipt_identity["sha256"]))
        replay_tool_shas.add(cast(str, tool_identity["sha256"]))
        replay_records.append(deepcopy(replay_record))
    if len(replay_receipt_shas) != 2 or len(replay_tool_shas) != 2:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "outside replays are not two heterogeneous receipts/tools",
        )
    if root_receipt_identity is None or set(replay_results) != {
        "alternate",
        "primary",
    }:
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "independent replay result set is incomplete",
        )
    root_receipt_raw = _read_calibration_identity_bytes(
        root_receipt_identity,
        label="calibration root receipt",
    )
    root_receipt = _strict_calibration_json(
        root_receipt_raw,
        label="calibration root receipt",
    )
    root_path = Path(cast(str, root_receipt_identity["path"])).parent
    fixed_paths = {
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
    artifacts = root_receipt.get("artifacts")
    if (
        root_receipt.get("fixed_paths") != fixed_paths
        or type(artifacts) is not list
        or len(artifacts) != len(fixed_paths)
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "closed calibration root path/artifact set drifted",
        )
    artifact_identities: dict[str, dict[str, object]] = {}
    for index, raw in enumerate(cast(list[object], artifacts)):
        if (
            type(raw) is not dict
            or set(raw) != {"path", "sha256", "size_bytes"}
            or type(raw["path"]) is not str
            or raw["path"] not in fixed_paths.values()
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"root artifact {index} is malformed",
            )
        relative = cast(str, raw["path"])
        site_identity = {
            "path": str((root_path / relative).absolute()),
            "sha256": raw["sha256"],
            "size_bytes": raw["size_bytes"],
        }
        _read_calibration_identity_bytes(
            site_identity,
            label=f"calibration root artifact {relative}",
        )
        artifact_identities[relative] = site_identity
    if set(artifact_identities) != set(fixed_paths.values()):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "calibration root artifact bijection drifted",
        )
    declaration_identity = artifact_identities[fixed_paths["declaration"]]
    declaration = _strict_calibration_json(
        _read_calibration_identity_bytes(
            declaration_identity,
            label="calibration declaration",
        ),
        label="calibration declaration",
    )
    if (
        artifact_identities[fixed_paths["aggregate"]] != aggregate_identity
        or artifact_identities[fixed_paths["profile_candidate"]]
        != candidate_identity
        or artifact_identities[fixed_paths["installed_profile"]]
        != profile_identity
    ):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "bundle identities do not name the replayed root artifacts",
        )
    for index, comparable in enumerate(
        cast(list[dict[str, object]], samples),
        start=1,
    ):
        if (
            comparable["sample_identity"]
            != artifact_identities[fixed_paths[f"sample_{index}"]]
            or comparable["validation_identity"]
            != artifact_identities[fixed_paths[f"validation_{index}"]]
        ):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"sample {index} identity does not name its root artifact",
            )
    expected_replay_result = {
        "candidate_identity": candidate_identity,
        "execution_surface_sha256": surface_sha,
        "root_receipt_identity": root_receipt_identity,
        "stage": stage,
    }
    for implementation, result in replay_results.items():
        if not _exact_tree_equal(result, expected_replay_result):
            _fail(
                "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
                f"{implementation} live replay result drifted",
            )
    declaration_surface = declaration.get("execution_surface")
    if not _exact_tree_equal(declaration_surface, surface):
        _fail(
            "CALIBRATION_AUTHORIZATION_BUNDLE_INVALID",
            "bundle surface differs from the replayed declaration",
        )
    members = cast(
        dict[str, Mapping[str, object]],
        cast(dict[str, object], declaration_surface)[
            "execution_member_identities"
        ],
    )
    tool_sites: dict[str, Mapping[str, object]] = {
        "fd_loader": members.get("calibration_fd_loader", {}),
        "observer_harness": cast(
            Mapping[str, object],
            declaration.get("observer_identity"),
        ),
        "package_verifier": members.get(
            "calibration_package_verifier_host",
            {},
        ),
        "protocol": members.get("calibration_protocol", {}),
        "runner": cast(
            Mapping[str, object],
            declaration.get("harness_identity"),
        ),
        "workload": members.get("calibration_workload", {}),
    }
    for role, identity in sorted(tool_sites.items()):
        descriptor = _require_tool_content_pin(
            identity,
            expected_tools[role],
            label=f"calibration {role}",
        )
        os.close(descriptor)
    return deepcopy(bundle)


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


def _same_uid_process_baseline(
    processes: Sequence[Mapping[str, object]],
    *,
    mode: str,
) -> dict[str, object]:
    return {
        "mode": mode,
        "observed_uid": os.getuid(),
        "policy_id": SAME_UID_BASELINE_POLICY_ID,
        "process_scope_contract": (
            "EXACT_PID_STARTTIME_CLASSIFICATION_NO_GLOBAL_FD_SCAN"
            if mode == SAME_UID_BASELINE_LIVE_MODE
            else "NOT_OBSERVED_TEST_INJECTION"
        ),
        "processes": [dict(item) for item in processes],
        "schema_version": SAME_UID_PROCESS_BASELINE_SCHEMA,
        "threat_boundary": (
            "NONADVERSARIAL_SAME_UID_AMBIENT"
            if mode == SAME_UID_BASELINE_LIVE_MODE
            else "TEST_ONLY_NO_AUTHORITY"
        ),
    }


def validate_same_uid_process_baseline(
    value: object,
    *,
    expected_sha256: object | None = None,
    require_live: bool,
) -> dict[str, object]:
    """Validate the canonical baseline without reinterpreting commands."""

    expected_fields = {
        "mode",
        "observed_uid",
        "policy_id",
        "process_scope_contract",
        "processes",
        "schema_version",
        "threat_boundary",
    }
    if type(value) is not dict or set(value) != expected_fields:
        _fail(
            "RESOURCE_SAME_UID_BASELINE_INVALID",
            "same-UID process baseline field set drifted",
        )
    baseline = cast(dict[str, object], value)
    mode = baseline["mode"]
    if (
        baseline["schema_version"] != SAME_UID_PROCESS_BASELINE_SCHEMA
        or baseline["policy_id"] != SAME_UID_BASELINE_POLICY_ID
        or type(baseline["observed_uid"]) is not int
        or baseline["observed_uid"] != os.getuid()
        or mode not in {
            SAME_UID_BASELINE_LIVE_MODE,
            SAME_UID_BASELINE_TEST_MODE,
        }
        or (
            mode == SAME_UID_BASELINE_LIVE_MODE
            and (
                baseline["process_scope_contract"]
                != "EXACT_PID_STARTTIME_CLASSIFICATION_NO_GLOBAL_FD_SCAN"
                or baseline["threat_boundary"]
                != "NONADVERSARIAL_SAME_UID_AMBIENT"
            )
        )
        or (
            mode == SAME_UID_BASELINE_TEST_MODE
            and (
                baseline["process_scope_contract"]
                != "NOT_OBSERVED_TEST_INJECTION"
                or baseline["threat_boundary"] != "TEST_ONLY_NO_AUTHORITY"
            )
        )
    ):
        _fail(
            "RESOURCE_SAME_UID_BASELINE_INVALID",
            "same-UID process baseline discriminator drifted",
        )
    if require_live and mode != SAME_UID_BASELINE_LIVE_MODE:
        _fail(
            "RESOURCE_SAME_UID_BASELINE_NOT_LIVE",
            "injected same-UID evidence cannot authorize a launch",
        )
    raw_processes = baseline["processes"]
    if type(raw_processes) is not list:
        _fail(
            "RESOURCE_SAME_UID_BASELINE_INVALID",
            "same-UID process baseline is not one list",
        )
    checked_processes: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for index, raw_process in enumerate(cast(list[object], raw_processes)):
        fields = {
            "classification",
            "command_sha256",
            "pid",
            "starttime",
        }
        if type(raw_process) is not dict or set(raw_process) != fields:
            _fail(
                "RESOURCE_SAME_UID_BASELINE_INVALID",
                f"same-UID process baseline member {index} drifted",
            )
        process = cast(dict[str, object], raw_process)
        if (
            process["classification"] not in SAME_UID_PROCESS_CLASSIFICATIONS
            or type(process["command_sha256"]) is not str
            or len(process["command_sha256"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in process["command_sha256"]
            )
            or type(process["pid"]) is not int
            or process["pid"] <= 0
            or type(process["starttime"]) is not int
            or process["starttime"] <= 0
        ):
            _fail(
                "RESOURCE_SAME_UID_BASELINE_INVALID",
                f"same-UID process baseline member {index} is malformed",
            )
        identity = (cast(int, process["pid"]), cast(int, process["starttime"]))
        if identity in seen:
            _fail(
                "RESOURCE_SAME_UID_BASELINE_INVALID",
                f"same-UID process baseline member {index} is duplicated",
            )
        seen.add(identity)
        checked_processes.append(dict(process))
    if checked_processes != sorted(
        checked_processes,
        key=lambda item: (cast(int, item["pid"]), cast(int, item["starttime"])),
    ):
        _fail(
            "RESOURCE_SAME_UID_BASELINE_INVALID",
            "same-UID process baseline ordering drifted",
        )
    if mode == SAME_UID_BASELINE_TEST_MODE and checked_processes:
        _fail(
            "RESOURCE_SAME_UID_BASELINE_INVALID",
            "injected same-UID process baseline must be empty",
        )
    checked = {
        **baseline,
        "processes": checked_processes,
    }
    digest = _canonical_sha256(checked)
    if expected_sha256 is not None and expected_sha256 != digest:
        _fail(
            "RESOURCE_SAME_UID_BASELINE_INVALID",
            "same-UID process baseline digest drifted",
        )
    return deepcopy(checked)


def observe_same_uid_process_scope(
    value: object,
    *,
    expected_sha256: object,
    allowed_runtime_actors: Sequence[Mapping[str, int]],
    proc_root: Path = Path("/proc"),
) -> dict[str, object]:
    """Join live process identities to the resource-gate scope.

    Commands are not reinterpreted here.  The resource gate alone assigns the
    closed classifications; this late join accepts only exact PID/starttime
    identities from that baseline plus package-declared runtime actors.
    """

    baseline = validate_same_uid_process_baseline(
        value,
        expected_sha256=expected_sha256,
        require_live=True,
    )
    baseline_processes = cast(
        list[dict[str, object]],
        baseline["processes"],
    )
    baseline_identities = {
        (cast(int, item["pid"]), cast(int, item["starttime"]))
        for item in baseline_processes
    }
    checked_runtime = _validate_allowed_process_identities(
        allowed_runtime_actors
    )
    runtime_identities = {
        (item["pid"], item["starttime"])
        for item in checked_runtime
    }
    if baseline_identities & runtime_identities:
        _fail(
            "RESOURCE_SAME_UID_SCOPE_INVALID",
            "runtime actor already appears in the resource-gate baseline",
        )
    try:
        entries = tuple(proc_root.iterdir())
    except OSError as exc:
        _fail(
            "RESOURCE_SAME_UID_SCOPE_UNTRUSTED",
            f"cannot enumerate {proc_root}: {exc}",
        )
    observed_baseline: list[dict[str, int]] = []
    observed_runtime: list[dict[str, int]] = []
    for item in entries:
        if not item.name.isdecimal():
            continue
        pid = int(item.name)
        try:
            before = item.stat()
            raw = (item / "stat").read_text(encoding="ascii")
            starttime = int(raw.rsplit(")", 1)[1].split()[19])
            after = item.stat()
            replay_raw = (item / "stat").read_text(encoding="ascii")
            replay_starttime = int(
                replay_raw.rsplit(")", 1)[1].split()[19]
            )
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, UnicodeError, IndexError, ValueError) as exc:
            _fail(
                "RESOURCE_SAME_UID_SCOPE_UNTRUSTED",
                f"cannot identify PID {pid}: {exc}",
            )
        if (
            (before.st_dev, before.st_ino, before.st_uid)
            != (after.st_dev, after.st_ino, after.st_uid)
            or starttime != replay_starttime
        ):
            _fail(
                "RESOURCE_SAME_UID_SCOPE_UNTRUSTED",
                f"PID {pid} changed during late scope observation",
            )
        if before.st_uid != os.getuid():
            continue
        identity = (pid, starttime)
        record = {"pid": pid, "starttime": starttime}
        if identity in baseline_identities:
            observed_baseline.append(record)
        elif identity in runtime_identities:
            observed_runtime.append(record)
        else:
            _fail(
                "RESOURCE_SAME_UID_SCOPE_DRIFT",
                f"same-UID PID {pid} was not classified by the resource gate",
            )
    if {
        (item["pid"], item["starttime"])
        for item in observed_runtime
    } != runtime_identities:
        _fail(
            "RESOURCE_SAME_UID_SCOPE_DRIFT",
            "a package-declared runtime actor is absent or changed",
        )
    observed_baseline.sort(key=lambda item: (item["pid"], item["starttime"]))
    observed_runtime.sort(key=lambda item: (item["pid"], item["starttime"]))
    return {
        "allowed_runtime_actors": observed_runtime,
        "baseline_live_processes": observed_baseline,
        "baseline_sha256": expected_sha256,
        "policy_id": SAME_UID_BASELINE_POLICY_ID,
        "state": "EXACT_BASELINE_OR_PACKAGE_ACTOR_SCOPE",
        "threat_boundary": "NONADVERSARIAL_SAME_UID_AMBIENT",
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


def _same_uid_conflicts_with_baseline(
    *,
    allowed_processes: Sequence[Mapping[str, int]],
    proc_root: Path = Path("/proc"),
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    ancestors = _ancestor_pids(proc_root)
    found: list[dict[str, object]] = []
    baseline_processes: list[dict[str, object]] = []
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
        observation = _process_observation(item, pid=pid)
        if observation is None:
            continue
        if observation["uid"] != os.getuid():
            continue
        command = str(observation["command"])
        if not command:
            _fail(
                "RESOURCE_CONFLICT_SCAN_UNTRUSTED",
                f"same-UID PID {pid} has no classifiable command",
            )
        final_observation = _process_observation(item, pid=pid)
        if final_observation is None:
            continue
        if final_observation != observation:
            _fail(
                "RESOURCE_CONFLICT_SCAN_UNTRUSTED",
                f"same-UID PID {pid} changed during baseline observation",
            )
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
            observed_allowed[identity] = record
            classification = "ALLOWED_CAMPAIGN_ACTOR"
        elif pid in ancestors:
            classification = "RESOURCE_GATE_ANCESTOR"
        elif any(pattern in lowered for pattern in CONFLICT_PATTERNS):
            found.append(record)
            continue
        else:
            classification = "NONCONFLICTING_AMBIENT"
        baseline_processes.append(
            {
                "classification": classification,
                "command_sha256": hashlib.sha256(
                    command.encode("utf-8")
                ).hexdigest(),
                "pid": pid,
                "starttime": identity[1],
            }
        )
    if set(observed_allowed) != set(allowed_by_identity):
        _fail(
            "RESOURCE_CONFLICT_ALLOWLIST_UNVERIFIED",
            "an allowed same-UID process is absent, changed, or has an empty command",
        )
    baseline_processes.sort(
        key=lambda item: (
            cast(int, item["pid"]),
            cast(int, item["starttime"]),
        )
    )
    baseline = _same_uid_process_baseline(
        baseline_processes,
        mode=SAME_UID_BASELINE_LIVE_MODE,
    )
    validate_same_uid_process_baseline(
        baseline,
        require_live=True,
    )
    return (
        sorted(found, key=lambda item: cast(int, item["pid"])),
        [observed_allowed[(item["pid"], item["starttime"])] for item in allowed],
        baseline,
    )


def _same_uid_conflicts(
    *,
    allowed_processes: Sequence[Mapping[str, int]],
    proc_root: Path = Path("/proc"),
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Preserve the accepted v1 resource-receipt scan semantics."""

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
        _fail(
            "RESOURCE_CONFLICT_SCAN_UNTRUSTED",
            f"cannot enumerate {proc_root}: {exc}",
        )
    allowed_pids = {identity["pid"] for identity in allowed}
    for item in entries:
        if not item.name.isdigit():
            continue
        pid = int(item.name)
        if pid in ancestors and pid not in allowed_pids:
            continue
        observation = _process_observation(item, pid=pid)
        if observation is None or observation["uid"] != os.getuid():
            continue
        command = str(observation["command"])
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
        if command and any(
            pattern in command.lower()
            for pattern in CONFLICT_PATTERNS
        ):
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
        minimum = cast(int, requirement["minimum_available_bytes"])
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
        minimum = cast(int, requirement["minimum_available_bytes"])
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


def _prospective_arithmetic(
    *,
    stage: str,
    profile: Mapping[str, object],
    disk_available: int,
    mem_available: int,
    swap_available: int,
    error_code: str,
) -> tuple[dict[str, int], dict[str, object]]:
    requirements = cast(Mapping[str, Mapping[str, object]], profile["requirements"])
    observed = {
        "disk": disk_available,
        "memory": mem_available,
        "swap": swap_available,
    }
    headroom: dict[str, int] = {}
    for dimension, available in observed.items():
        requirement = requirements[dimension]
        minimum = cast(int, requirement["minimum_available_bytes"])
        rule = requirement["availability_rule"]
        if rule == "INDEPENDENT_MINIMUM":
            if available < minimum:
                _fail(
                    error_code,
                    f"{stage}.{dimension}: available={available}, required={minimum}",
                )
            headroom[f"{dimension}_bytes_above_minimum"] = available - minimum
        elif dimension == "swap" and rule == "COMBINED_RAM_LIMITED_SWAP":
            headroom["swap_bytes_above_minimum"] = swap_available
        else:
            _fail(
                "RESOURCE_PROFILE_UNTRUSTED",
                f"{stage}.{dimension} has an invalid availability rule",
            )

    limits = cast(Mapping[str, object], profile["runtime_safety_limits"])
    feasibility: dict[str, object] = {
        "applies": False,
        "memory_after_host_reserve_bytes": 0,
        "memory_max_bytes": 0,
        "planned_memory_peak_bytes": 0,
        "swap_after_host_reserve_capped_bytes": 0,
        "total_capacity_for_memory_max_bytes": 0,
    }
    if limits["applies"] is True:
        memory_requirement = requirements["memory"]
        swap_requirement = requirements["swap"]
        usable_memory = max(
            0,
            mem_available - cast(int, memory_requirement["host_reserve_bytes"]),
        )
        usable_swap = min(
            max(
                0,
                swap_available - cast(int, swap_requirement["host_reserve_bytes"]),
            ),
            cast(int, limits["memory_swap_max_bytes"]),
        )
        planned_memory = cast(
            int,
            memory_requirement["predicted_peak_bytes"],
        ) + cast(
            int,
            memory_requirement["safety_margin_bytes"],
        )
        memory_max = cast(int, limits["memory_max_bytes"])
        total_capacity = usable_memory + usable_swap
        if usable_memory < planned_memory or total_capacity < memory_max:
            _fail(
                (
                    "RESOURCE_HARD_CAP_FEASIBILITY_FAILED"
                    if error_code == "RESOURCE_HEADROOM_INSUFFICIENT"
                    else error_code
                ),
                (
                    f"usable_ram={usable_memory}, planned_ram={planned_memory}, "
                    f"usable_limited_swap={usable_swap}, capacity={total_capacity}, "
                    f"MemoryMax={memory_max}"
                ),
            )
        feasibility = {
            "applies": True,
            "memory_after_host_reserve_bytes": usable_memory,
            "memory_max_bytes": memory_max,
            "planned_memory_peak_bytes": planned_memory,
            "swap_after_host_reserve_capped_bytes": usable_swap,
            "total_capacity_for_memory_max_bytes": total_capacity,
        }
        headroom["swap_bytes_usable_for_combined_capacity"] = usable_swap
    return headroom, feasibility


def evaluate_calibration_prelaunch_resource_admission(
    path: Path | str,
    *,
    stage: str,
    lock_identities: Sequence[Mapping[str, object]],
    lock_identity_format: str,
    observation_context: Mapping[str, object],
    installed_profile: Mapping[str, object],
    enforced_budget_profile: Mapping[str, object] | None = None,
    enforced_budget_profile_identity: Mapping[str, object] | None = None,
    meminfo: Mapping[str, int] | None = None,
    disk_free: int | None = None,
    conflicts: Sequence[Mapping[str, object]] | None = None,
    allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
    observed_at_utc: str | None = None,
) -> dict[str, object]:
    """Recheck the installed profile immediately before a calibration fork.

    This is deliberately not launch admission and does not consume calibration
    evidence.  It reuses the prospective profile validator, exact lock
    identities, same-UID scan, disk measurement and capacity arithmetic so the
    run being measured cannot lower its own threshold or substitute a second
    implementation of the resource rules.
    """

    profile = _validated_prospective_profile(
        stage,
        enforced_budget_profile=enforced_budget_profile,
        enforced_budget_profile_identity=enforced_budget_profile_identity,
    )
    if not _exact_tree_equal(installed_profile, profile):
        _fail(
            "CALIBRATION_INSTALLED_PROFILE_DRIFT",
            "calibration plan does not carry the exact preinstalled stage profile",
        )
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
        _fail(
            "RESOURCE_MEASUREMENT_UNTRUSTED",
            "MemAvailable or SwapFree is absent",
        )
    mem_available = _measurement(memory["MemAvailable"], "MemAvailable")
    swap_free = _measurement(memory["SwapFree"], "SwapFree")
    disk_available, disk_target = _measure_disk_target(path, disk_free=disk_free)
    if conflicts is None:
        heavy, observed_allowed, same_uid_baseline = (
            _same_uid_conflicts_with_baseline(
            allowed_processes=allowed_same_uid_processes,
            )
        )
    else:
        if allowed_same_uid_processes:
            _fail(
                "RESOURCE_CONFLICT_SCAN_UNTRUSTED",
                "injected conflict evidence cannot verify a nonempty allowlist",
        )
        heavy = [dict(item) for item in conflicts]
        observed_allowed = []
        same_uid_baseline = _same_uid_process_baseline(
            (),
            mode=SAME_UID_BASELINE_TEST_MODE,
        )
    for index, item in enumerate(heavy):
        command = item.get("command")
        pid = item.get("pid")
        starttime = item.get("starttime")
        if (
            type(item) is not dict
            or set(item) not in (
                {"command", "pid"},
                {"command", "pid", "starttime"},
            )
            or type(command) is not str
            or not command
            or type(pid) is not int
            or pid <= 0
            or (
                "starttime" in item
                and (type(starttime) is not int or starttime <= 0)
            )
        ):
            _fail(
                "RESOURCE_CONFLICT_SCAN_UNTRUSTED",
                f"conflict {index} is malformed",
            )
    if heavy:
        _fail("RESOURCE_CONFLICT_DETECTED", f"same-UID conflicts: {heavy}")
    headroom, feasibility = _prospective_arithmetic(
        stage=stage,
        profile=profile,
        disk_available=disk_available,
        mem_available=mem_available,
        swap_available=swap_free,
        error_code="RESOURCE_HEADROOM_INSUFFICIENT",
    )
    timestamp = (
        datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if observed_at_utc is None
        else observed_at_utc
    )
    timestamp = _validated_utc(timestamp, "observation timestamp")
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(PROSPECTIVE_FALSE_AUTHORIZATIONS),
        "created_at_utc": timestamp,
        "disk_target": disk_target,
        "hard_cap_feasibility": feasibility,
        "headroom": headroom,
        "lock_check": {
            "checked_after_acquisition": True,
            "identities": checked_locks,
            "identity_format": lock_identity_format,
            "paths": list(LOCK_PATHS),
        },
        "measurements": {
            "disk_free_bytes": disk_available,
            "mem_available_bytes": mem_available,
            "same_uid_allowed_processes": observed_allowed,
            "same_uid_conflicts": [],
            "same_uid_process_baseline": same_uid_baseline,
            "same_uid_process_baseline_sha256": _canonical_sha256(
                same_uid_baseline
            ),
            "swap_free_bytes": swap_free,
        },
        "observation_context": checked_context,
        "observation_context_sha256": _canonical_sha256(checked_context),
        "profile": profile,
        "schema_version": CALIBRATION_PRELAUNCH_RESOURCE_ADMISSION_SCHEMA,
        "stage": stage,
        "status": "PASS_NO_LAUNCH_AUTHORITY",
    }


def evaluate_prospective_resource_admission(
    path: Path | str,
    *,
    stage: str,
    lock_identities: Sequence[Mapping[str, object]],
    lock_identity_format: str,
    observation_context: Mapping[str, object],
    calibration_authorization_bundle: Mapping[str, object],
    calibration_authorization_bundle_identity: Mapping[str, object],
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ],
    enforced_budget_profile: Mapping[str, object] | None = None,
    enforced_budget_profile_identity: Mapping[str, object] | None = None,
    meminfo: Mapping[str, int] | None = None,
    disk_free: int | None = None,
    conflicts: Sequence[Mapping[str, object]] | None = None,
    allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
    observed_at_utc: str | None = None,
) -> dict[str, object]:
    """Evaluate the prospective v2 stage profile without changing v1 callers."""

    profile = _validated_prospective_profile(
        stage,
        enforced_budget_profile=enforced_budget_profile,
        enforced_budget_profile_identity=enforced_budget_profile_identity,
    )
    checked_calibration = validate_calibration_authorization_bundle(
        calibration_authorization_bundle,
        bundle_identity=calibration_authorization_bundle_identity,
        stage=stage,
        expected_profile=profile,
        expected_calibration_tool_identities=expected_calibration_tool_identities,
    )
    checked_calibration_identity = _calibration_identity(
        calibration_authorization_bundle_identity,
        label="calibration authorization bundle",
    )
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
    disk_available, disk_target = _measure_disk_target(path, disk_free=disk_free)

    if conflicts is None:
        heavy, observed_allowed, same_uid_baseline = (
            _same_uid_conflicts_with_baseline(
            allowed_processes=allowed_same_uid_processes,
            )
        )
    else:
        if allowed_same_uid_processes:
            _fail(
                "RESOURCE_CONFLICT_SCAN_UNTRUSTED",
                "injected conflict evidence cannot verify a nonempty allowlist",
        )
        heavy = [dict(item) for item in conflicts]
        observed_allowed = []
        same_uid_baseline = _same_uid_process_baseline(
            (),
            mode=SAME_UID_BASELINE_TEST_MODE,
        )
    for index, item in enumerate(heavy):
        command = item.get("command")
        pid = item.get("pid")
        starttime = item.get("starttime")
        if (
            type(item) is not dict
            or set(item) not in ({"command", "pid"}, {"command", "pid", "starttime"})
            or type(command) is not str
            or not command
            or type(pid) is not int
            or pid <= 0
            or (
                "starttime" in item
                and (
                    type(starttime) is not int
                    or starttime <= 0
                )
            )
        ):
            _fail("RESOURCE_CONFLICT_SCAN_UNTRUSTED", f"conflict {index} is malformed")
    if heavy:
        _fail("RESOURCE_CONFLICT_DETECTED", f"same-UID conflicts: {heavy}")

    headroom, feasibility = _prospective_arithmetic(
        stage=stage,
        profile=profile,
        disk_available=disk_available,
        mem_available=mem_available,
        swap_available=swap_free,
        error_code="RESOURCE_HEADROOM_INSUFFICIENT",
    )
    timestamp = (
        datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if observed_at_utc is None
        else observed_at_utc
    )
    timestamp = _validated_utc(timestamp, "observation timestamp")
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(PROSPECTIVE_FALSE_AUTHORIZATIONS),
        "calibration_authorization_bundle": checked_calibration,
        "calibration_authorization_bundle_identity": checked_calibration_identity,
        "created_at_utc": timestamp,
        "disk_target": disk_target,
        "hard_cap_feasibility": feasibility,
        "headroom": headroom,
        "lock_check": {
            "checked_after_acquisition": True,
            "identities": checked_locks,
            "identity_format": lock_identity_format,
            "paths": list(LOCK_PATHS),
        },
        "measurements": {
            "disk_free_bytes": disk_available,
            "mem_available_bytes": mem_available,
            "same_uid_allowed_processes": observed_allowed,
            "same_uid_conflicts": [],
            "same_uid_process_baseline": same_uid_baseline,
            "same_uid_process_baseline_sha256": _canonical_sha256(
                same_uid_baseline
            ),
            "swap_free_bytes": swap_free,
        },
        "observation_context": checked_context,
        "observation_context_sha256": _canonical_sha256(checked_context),
        "profile": profile,
        "schema_version": PROSPECTIVE_RESOURCE_ADMISSION_SCHEMA,
        "stage": stage,
        "status": "PASS",
    }


def validate_prospective_resource_admission_receipt(
    value: object,
    *,
    expected_stage: str,
    expected_lock_identities: Sequence[Mapping[str, object]],
    expected_lock_identity_format: str,
    expected_observation_context: Mapping[str, object],
    calibration_authorization_bundle: Mapping[str, object],
    calibration_authorization_bundle_identity: Mapping[str, object],
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ],
    enforced_budget_profile: Mapping[str, object] | None = None,
    enforced_budget_profile_identity: Mapping[str, object] | None = None,
    expected_allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
) -> dict[str, object]:
    """Replay one v2 receipt against its exact profile and budget binding."""

    expected_fields = {
        "authority_scope",
        "authorizations",
        "calibration_authorization_bundle",
        "calibration_authorization_bundle_identity",
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
        _fail("RESOURCE_RECEIPT_INVALID", "prospective receipt field set drifted")
    record = cast(dict[str, object], value)
    if (
        record["schema_version"] != PROSPECTIVE_RESOURCE_ADMISSION_SCHEMA
        or record["authority_scope"] != AUTHORITY_SCOPE
        or not _exact_tree_equal(
            record["authorizations"],
            PROSPECTIVE_FALSE_AUTHORIZATIONS,
        )
        or record["stage"] != expected_stage
        or record["status"] != "PASS"
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "prospective receipt identity drifted")
    _validated_utc(record["created_at_utc"], "receipt observation timestamp")
    expected_profile = _validated_prospective_profile(
        expected_stage,
        enforced_budget_profile=enforced_budget_profile,
        enforced_budget_profile_identity=enforced_budget_profile_identity,
    )
    checked_calibration = validate_calibration_authorization_bundle(
        calibration_authorization_bundle,
        bundle_identity=calibration_authorization_bundle_identity,
        stage=expected_stage,
        expected_profile=expected_profile,
        expected_calibration_tool_identities=expected_calibration_tool_identities,
    )
    checked_calibration_identity = _calibration_identity(
        calibration_authorization_bundle_identity,
        label="calibration authorization bundle",
    )
    if (
        not _exact_tree_equal(
            record["calibration_authorization_bundle"],
            checked_calibration,
        )
        or record["calibration_authorization_bundle_identity"]
        != checked_calibration_identity
    ):
        _fail(
            "RESOURCE_RECEIPT_INVALID",
            "calibration authorization bundle join drifted",
        )
    if not _exact_tree_equal(record["profile"], expected_profile):
        _fail("RESOURCE_RECEIPT_INVALID", "prospective profile drifted")
    checked_context = _validated_observation_context(
        expected_observation_context,
        stage=expected_stage,
        disk_path=None,
    )
    if (
        not _exact_tree_equal(record["observation_context"], checked_context)
        or record["observation_context_sha256"] != _canonical_sha256(checked_context)
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "prospective observation context drifted")
    checked_locks = _validate_lock_identities(
        expected_lock_identities,
        identity_format=expected_lock_identity_format,
    )
    if not _exact_tree_equal(
        record["lock_check"],
        {
            "checked_after_acquisition": True,
            "identities": checked_locks,
            "identity_format": expected_lock_identity_format,
            "paths": list(LOCK_PATHS),
        },
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "prospective lock join drifted")
    disk_target = record["disk_target"]
    if (
        type(disk_target) is not dict
        or set(disk_target) != {"device", "inode", "mode", "path", "type", "uid"}
        or disk_target["path"] != checked_context["disk_path"]
        or disk_target["type"] != "directory"
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "prospective disk target drifted")
    for field in ("device", "inode", "mode", "uid"):
        if type(disk_target[field]) is not int or disk_target[field] < 0:
            _fail("RESOURCE_RECEIPT_INVALID", "prospective disk identity is malformed")
    if disk_target["inode"] == 0:
        _fail("RESOURCE_RECEIPT_INVALID", "prospective disk inode is zero")

    measurements = record["measurements"]
    if type(measurements) is not dict or set(measurements) != {
        "disk_free_bytes",
        "mem_available_bytes",
        "same_uid_allowed_processes",
        "same_uid_conflicts",
        "same_uid_process_baseline",
        "same_uid_process_baseline_sha256",
        "swap_free_bytes",
    }:
        _fail("RESOURCE_RECEIPT_INVALID", "prospective measurements drifted")
    measured = cast(dict[str, object], measurements)
    if measured["same_uid_conflicts"] != []:
        _fail("RESOURCE_RECEIPT_INVALID", "prospective receipt retained a conflict")
    validate_same_uid_process_baseline(
        measured["same_uid_process_baseline"],
        expected_sha256=measured["same_uid_process_baseline_sha256"],
        require_live=False,
    )
    expected_allowed = _validate_allowed_process_identities(
        expected_allowed_same_uid_processes,
    )
    recorded_allowed = measured["same_uid_allowed_processes"]
    if type(recorded_allowed) is not list or len(recorded_allowed) != len(
        expected_allowed
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "prospective allowlist cardinality drifted")
    for recorded, expected_identity in zip(
        recorded_allowed,
        expected_allowed,
        strict=True,
    ):
        if (
            type(recorded) is not dict
            or set(recorded) != {"command", "pid", "starttime"}
            or type(recorded["command"]) is not str
            or {
                "pid": recorded["pid"],
                "starttime": recorded["starttime"],
            }
            != expected_identity
        ):
            _fail("RESOURCE_RECEIPT_INVALID", "prospective allowlist identity drifted")
    disk_available = _measurement(measured["disk_free_bytes"], "receipt disk free")
    mem_available = _measurement(
        measured["mem_available_bytes"],
        "receipt MemAvailable",
    )
    swap_available = _measurement(
        measured["swap_free_bytes"],
        "receipt SwapFree",
    )
    expected_headroom, expected_feasibility = _prospective_arithmetic(
        stage=expected_stage,
        profile=expected_profile,
        disk_available=disk_available,
        mem_available=mem_available,
        swap_available=swap_available,
        error_code="RESOURCE_RECEIPT_INVALID",
    )
    if (
        not _exact_tree_equal(record["headroom"], expected_headroom)
        or not _exact_tree_equal(
            record["hard_cap_feasibility"],
            expected_feasibility,
        )
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "prospective arithmetic drifted")
    return deepcopy(record)


def _prospective_launch_contract_from_receipt(
    value: object,
    *,
    calibration_authorization_bundle: Mapping[str, object],
    calibration_authorization_bundle_identity: Mapping[str, object],
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ],
    enforced_budget_profile: Mapping[str, object] | None,
    enforced_budget_profile_identity: Mapping[str, object] | None,
) -> tuple[
    dict[str, object],
    str,
    list[dict[str, object]],
    str,
    dict[str, object],
    list[dict[str, int]],
]:
    if type(value) is not dict:
        _fail("RESOURCE_RECEIPT_INVALID", "prospective launch receipt is not an object")
    record = cast(dict[str, object], value)
    stage = record.get("stage")
    lock_check = record.get("lock_check")
    context = record.get("observation_context")
    measurements = record.get("measurements")
    if (
        type(stage) is not str
        or type(lock_check) is not dict
        or type(context) is not dict
        or type(measurements) is not dict
        or type(lock_check.get("identities")) is not list
        or type(lock_check.get("identity_format")) is not str
        or type(measurements.get("same_uid_allowed_processes")) is not list
    ):
        _fail("RESOURCE_RECEIPT_INVALID", "prospective launch contract is malformed")
    allowed: list[dict[str, int]] = []
    for item in cast(list[object], measurements["same_uid_allowed_processes"]):
        if (
            type(item) is not dict
            or type(item.get("pid")) is not int
            or type(item.get("starttime")) is not int
        ):
            _fail("RESOURCE_RECEIPT_INVALID", "prospective allowed process is malformed")
        allowed.append(
            {
                "pid": cast(int, item["pid"]),
                "starttime": cast(int, item["starttime"]),
            }
        )
    identities = _validate_lock_identities(
        lock_check["identities"],
        identity_format=cast(str, lock_check["identity_format"]),
    )
    checked = validate_prospective_resource_admission_receipt(
        record,
        expected_stage=stage,
        expected_lock_identities=identities,
        expected_lock_identity_format=cast(str, lock_check["identity_format"]),
        expected_observation_context=context,
        calibration_authorization_bundle=calibration_authorization_bundle,
        calibration_authorization_bundle_identity=(
            calibration_authorization_bundle_identity
        ),
        expected_calibration_tool_identities=expected_calibration_tool_identities,
        enforced_budget_profile=enforced_budget_profile,
        enforced_budget_profile_identity=enforced_budget_profile_identity,
        expected_allowed_same_uid_processes=allowed,
    )
    validate_same_uid_process_baseline(
        measurements.get("same_uid_process_baseline"),
        expected_sha256=measurements.get(
            "same_uid_process_baseline_sha256"
        ),
        require_live=True,
    )
    return (
        checked,
        stage,
        identities,
        cast(str, lock_check["identity_format"]),
        dict(context),
        allowed,
    )


def reevaluate_prospective_resource_admission_for_launch(
    expected_receipt: object,
    *,
    calibration_authorization_bundle: Mapping[str, object],
    calibration_authorization_bundle_identity: Mapping[str, object],
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ],
    enforced_budget_profile: Mapping[str, object] | None = None,
    enforced_budget_profile_identity: Mapping[str, object] | None = None,
    meminfo: Mapping[str, int] | None = None,
    disk_free: int | None = None,
    conflicts: Sequence[Mapping[str, object]] | None = None,
    observed_at_utc: str | None = None,
) -> dict[str, object]:
    """Repeat the same prospective profile after retaining all three locks."""

    (
        _checked,
        stage,
        lock_identities,
        identity_format,
        context,
        allowed,
    ) = _prospective_launch_contract_from_receipt(
        expected_receipt,
        calibration_authorization_bundle=calibration_authorization_bundle,
        calibration_authorization_bundle_identity=(
            calibration_authorization_bundle_identity
        ),
        expected_calibration_tool_identities=expected_calibration_tool_identities,
        enforced_budget_profile=enforced_budget_profile,
        enforced_budget_profile_identity=enforced_budget_profile_identity,
    )
    probes = _open_launch_lock_probes(
        lock_identities,
        identity_format=identity_format,
    )
    final_receipt: dict[str, object] | None = None
    primary: BaseException | None = None
    try:
        final_receipt = evaluate_prospective_resource_admission(
            cast(str, context["disk_path"]),
            stage=stage,
            lock_identities=lock_identities,
            lock_identity_format=identity_format,
            observation_context=context,
            calibration_authorization_bundle=calibration_authorization_bundle,
            calibration_authorization_bundle_identity=(
                calibration_authorization_bundle_identity
            ),
            expected_calibration_tool_identities=expected_calibration_tool_identities,
            enforced_budget_profile=enforced_budget_profile,
            enforced_budget_profile_identity=enforced_budget_profile_identity,
            meminfo=meminfo,
            disk_free=disk_free,
            conflicts=conflicts,
            allowed_same_uid_processes=allowed,
            observed_at_utc=observed_at_utc,
        )
        _revalidate_launch_lock_probes(probes)
        validate_prospective_resource_admission_receipt(
            final_receipt,
            expected_stage=stage,
            expected_lock_identities=lock_identities,
            expected_lock_identity_format=identity_format,
            expected_observation_context=context,
            calibration_authorization_bundle=calibration_authorization_bundle,
            calibration_authorization_bundle_identity=(
                calibration_authorization_bundle_identity
            ),
            expected_calibration_tool_identities=expected_calibration_tool_identities,
            enforced_budget_profile=enforced_budget_profile,
            enforced_budget_profile_identity=enforced_budget_profile_identity,
            expected_allowed_same_uid_processes=allowed,
        )
        final_measurements = final_receipt.get("measurements")
        if type(final_measurements) is not dict:
            _fail(
                "RESOURCE_RECEIPT_INVALID",
                "launch recheck lacks resource measurements",
            )
        validate_same_uid_process_baseline(
            final_measurements.get("same_uid_process_baseline"),
            expected_sha256=final_measurements.get(
                "same_uid_process_baseline_sha256"
            ),
            require_live=True,
        )
    except BaseException as exc:
        primary = exc
    _close_launch_lock_probes(probes, primary=primary)
    assert final_receipt is not None
    return final_receipt


def validate_prospective_launch_resource_reevaluation(
    value: object,
    *,
    expected_receipt: object,
    calibration_authorization_bundle: Mapping[str, object],
    calibration_authorization_bundle_identity: Mapping[str, object],
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ],
    enforced_budget_profile: Mapping[str, object] | None = None,
    enforced_budget_profile_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    (
        _checked,
        stage,
        lock_identities,
        identity_format,
        context,
        allowed,
    ) = _prospective_launch_contract_from_receipt(
        expected_receipt,
        calibration_authorization_bundle=calibration_authorization_bundle,
        calibration_authorization_bundle_identity=(
            calibration_authorization_bundle_identity
        ),
        expected_calibration_tool_identities=expected_calibration_tool_identities,
        enforced_budget_profile=enforced_budget_profile,
        enforced_budget_profile_identity=enforced_budget_profile_identity,
    )
    checked = validate_prospective_resource_admission_receipt(
        value,
        expected_stage=stage,
        expected_lock_identities=lock_identities,
        expected_lock_identity_format=identity_format,
        expected_observation_context=context,
        calibration_authorization_bundle=calibration_authorization_bundle,
        calibration_authorization_bundle_identity=(
            calibration_authorization_bundle_identity
        ),
        expected_calibration_tool_identities=expected_calibration_tool_identities,
        enforced_budget_profile=enforced_budget_profile,
        enforced_budget_profile_identity=enforced_budget_profile_identity,
        expected_allowed_same_uid_processes=allowed,
    )
    measurements = checked.get("measurements")
    if type(measurements) is not dict:
        _fail(
            "RESOURCE_RECEIPT_INVALID",
            "launch recheck lacks resource measurements",
        )
    validate_same_uid_process_baseline(
        measurements.get("same_uid_process_baseline"),
        expected_sha256=measurements.get(
            "same_uid_process_baseline_sha256"
        ),
        require_live=True,
    )
    return checked
