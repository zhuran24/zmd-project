#!/usr/bin/env python3
"""Self-contained bootstrap for one prospective non-certified-cuts AB16 campaign.

The offline candidate freezes the planned repository-local source set without
creating a campaign or authorizing an arm.  Bootstrap replays those bytes,
HEAD, the manager epoch, and the scientific preregistration before calling the
unchanged Gate-1 v4 authority API.  Historical Gate inputs are represented by
one pinned, non-authorizing archive locator; their archived bytes are never a
local bootstrap requirement.

This module creates authority bytes only.  It never starts a unit, solver, arm,
or experiment.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any


V4_RESEARCH_DIR = Path(__file__).resolve().parents[1] / "noncert_cuts_ab_trust_gate1_v4_20260724"
if str(V4_RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(V4_RESEARCH_DIR))

import campaign_authority_v4 as authority  # noqa: E402


CANDIDATE_SCHEMA = "noncert-cuts-ab16-bootstrap-offline-candidate-v2"
CAPTURE_SCHEMA = "noncert-cuts-ab16-bootstrap-manager-capture-v2"
RESULT_SCHEMA = "noncert-cuts-ab16-campaign-bootstrap-result-v2"
PATH_PREREGISTRATION_SCHEMA = "noncert-cuts-ab16-scientific-preregistration-v3"
ARCHIVE_LOCATORS_SCHEMA = "noncert-cuts-ab16-archive-locators-v1"

CANDIDATE_PURPOSE = "AB16_OFFLINE_NONAUTHORIZING_CANDIDATE"
PATH_PREREGISTRATION_PURPOSE = "prospective_noncert_cuts_ab16_scientific_preregistration"
ARCHIVE_LOCATORS_PURPOSE = "AB16_ARCHIVE_ONLY_PROVENANCE_LOCATORS"
EXTERNAL_ARTIFACTS_SCHEMA = 1

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
RUN_NONCE_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{4,123}\Z")
ARCHIVE_NAMESPACE_RE = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")

AB16_ARM_SEQUENCE = tuple(
    f"{configuration}-{order}-{arm}"
    for configuration in authority.AB16_CONFIGURATIONS
    for order, ordered_arms in (
        ("ab", authority.AB16_ARMS),
        ("ba", tuple(reversed(authority.AB16_ARMS))),
    )
    for arm in ordered_arms
)
AB16_EXPERIMENT_CONTRACT_SHA256 = "24b45e110952505e6ffa92d3ddfdf33874cc3cb4503397e993898e79174ded9e"
AB16_SCIENTIFIC_INPUT_SET_SCHEMA = "noncert-cuts-ab16-campaign-scientific-input-set-v1"
AB16_SEED = 2026072301
AB16_WORKERS = 1
AB16_RETRY_POLICY: dict[str, object] = {
    "credible_terminal_closes_slot": True,
    "failed_attempt_retryable": True,
    "lowest_credible_ordinal_wins": True,
    "no_overwrite_per_attempt": True,
    "retry_limit": None,
}

V4_SCRIPT_TOOL_FILES: dict[str, str] = {
    "campaign_authority_v4": "campaign_authority_v4.py",
    "gate1_campaign_bootstrap_v4": "gate1_campaign_bootstrap_v4.py",
    "gate1_campaign_driver_v4": "gate1_campaign_driver_v4.py",
    "gate1_campaign_execution_v4": "gate1_campaign_execution_v4.py",
    "gate1_payload_v4": "gate1_payload_v4.py",
    "gate1_unit_orchestrator_v4": "gate1_unit_orchestrator_v4.py",
    "independent_arithmetic_v4": "independent_arithmetic_v4.py",
    "manager_attestor_v4": "manager_attestor_v4.py",
    "positive_control_formal_v4": "positive_control_formal_v4.py",
    "positive_control_v4": "positive_control_v4.py",
    "positive_control_gate_v4": "positive_control_gate_v4.py",
    "resource_lifecycle_v4": "resource_lifecycle_v4.py",
    "resource_verifier_v4": "resource_verifier_v4.py",
}
AB16_SCRIPT_TOOL_FILES: dict[str, str] = {
    "ab16_authority_v1": "ab16_authority_v1.py",
    "ab16_campaign_bootstrap_v1": "ab16_campaign_bootstrap_v1.py",
    "ab16_contract_v1": "ab16_contract_v1.py",
    "ab16_terminal_gate_v1": "ab16_terminal_gate_v1.py",
    "baseline_admission_v1": "baseline_admission_v1.py",
    "baseline_rebuild_v1": "baseline_rebuild_v1.py",
    "cut_free_incumbent_replay_v1": "cut_free_incumbent_replay_v1.py",
    "organic_arm_replay_v1": "organic_arm_replay_v1.py",
    "organic_arm_runner_v1": "organic_arm_runner_v1.py",
    "organic_resource_lifecycle_v1": "organic_resource_lifecycle_v1.py",
    "organic_resource_verifier_v1": "organic_resource_verifier_v1.py",
    "organic_unit_orchestrator_v1": "organic_unit_orchestrator_v1.py",
}
SCRIPT_TOOL_FILES = {**V4_SCRIPT_TOOL_FILES, **AB16_SCRIPT_TOOL_FILES}

STRICT_INPUT_ROLES = frozenset(
    {
        "candidate_placements",
        "canonical_rules",
        "cuts_mandatory_schedule",
        "history_freeze_manifest",
        "legacy_control_a002",
        "mandatory_instances",
        "project_lock",
    }
)
ARCHIVED_SCIENTIFIC_INPUT_ROLES = frozenset(
    {
        "history_freeze_manifest",
        "legacy_control_a002",
    }
)
SCIENTIFIC_INPUT_ROLES = STRICT_INPUT_ROLES
SYSTEM_TOOL_ROLES = frozenset(
    {
        "attestor_python",
        "busctl",
        "git",
        "python3_13",
        "sudo",
        "systemctl",
        "systemd_run",
    }
)
JSON_INPUT_ROLES = frozenset(
    {
        "candidate_placements",
        "canonical_rules",
        "history_freeze_manifest",
        "legacy_control_a002",
        "mandatory_instances",
    }
)
CANONICAL_JSON_INPUT_ROLES = frozenset(
    {
        "candidate_placements",
        "history_freeze_manifest",
        "legacy_control_a002",
        "mandatory_instances",
    }
)

CANDIDATE_INPUT_ROLE = "ab16_offline_candidate"
CANDIDATE_PACKAGE_ROLE = "input.ab16_offline_candidate.json"
CAPTURE_INPUT_ROLE = "ab16_bootstrap_manager_epoch_capture"
CAPTURE_PACKAGE_ROLE = "input.ab16_bootstrap_manager_epoch_capture.json"
PATH_PREREGISTRATION_INPUT_ROLE = "ab16_path_preregistration"
PATH_PREREGISTRATION_PACKAGE_ROLE = "input.ab16_path_preregistration.json"
ARCHIVE_LOCATORS_PATH = Path(__file__).resolve().with_name("archive_locators_v1.json")
CANDIDATE_PLACEMENTS_PIN: dict[str, object] = {
    "id": "candidate_placements",
    "path": "data/preprocessed/candidate_placements.json",
    "sha256": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    "size_bytes": 54_467_709,
}
ARCHIVE_LOCATOR_ENTRIES: dict[str, dict[str, object]] = {
    "history_freeze_manifest": {
        "archive_locator": (
            "zmd-codex-autonomy-20260801:"
            ".artifacts/noncert_cuts_ab_trust_gate1_v4_20260724/history-freeze-a001/manifest.json"
        ),
        "sha256": "35e99c96482573976b70698f3422c9ab586afb1df3366e466ff93f901114de68",
        "size_bytes": 1_397_516,
    },
    "legacy_control_a002": {
        "archive_locator": (
            "zmd-codex-autonomy-20260801:"
            ".artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/"
            "positive-control/control-a002/result.json"
        ),
        "sha256": "9e747c214c2108b7fc73fede1d31873b24bf765d74857cf4a846cf5178ebcff6",
        "size_bytes": 507_095,
    },
}


class BootstrapError(RuntimeError):
    """A staged bootstrap precondition failed closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _utc(value: object, label: str) -> str:
    if type(value) is not str:
        raise BootstrapError(f"{label} must be an exact UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BootstrapError(f"{label} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise BootstrapError(f"{label} is not UTC")
    return value


def _exact_keys(
    value: object,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise BootstrapError(f"{label} key set drifted")
    return value


def _canonical_record(
    path: Path | str,
    label: str,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    snapshot = authority.snapshot_regular(path)
    value = authority.strict_loads(snapshot.data, label)
    if authority.canonical_json(value) != snapshot.data:
        raise BootstrapError(f"{label} is not canonical strict JSON")
    if not isinstance(value, Mapping):
        raise BootstrapError(f"{label} is not a JSON object")
    return value, authority.detached_identity(snapshot)


def validate_archive_locators(value: object) -> Mapping[str, Any]:
    """Validate the sole non-authorizing reference to retired historical bytes."""

    record = _exact_keys(
        value,
        {
            "authorizing",
            "entries",
            "local_bytes_required",
            "purpose",
            "schema_version",
        },
        "archive locators",
    )
    entries = _exact_keys(
        record["entries"],
        set(ARCHIVED_SCIENTIFIC_INPUT_ROLES),
        "archive locator entries",
    )
    for role, expected in ARCHIVE_LOCATOR_ENTRIES.items():
        entry = _exact_keys(
            entries[role],
            {"archive_locator", "sha256", "size_bytes"},
            f"archive locator {role}",
        )
        locator = entry["archive_locator"]
        if type(locator) is not str:
            raise BootstrapError(f"archive locator {role} is malformed")
        namespace, separator, relative = locator.partition(":")
        relative_path = PurePosixPath(relative)
        if (
            not separator
            or ARCHIVE_NAMESPACE_RE.fullmatch(namespace) is None
            or not relative
            or relative.startswith("/")
            or "\\" in relative
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or str(relative_path) != relative
        ):
            raise BootstrapError(f"archive locator {role} is not a safe relative reference")
        if dict(entry) != expected:
            raise BootstrapError(f"archive locator {role} differs from its pinned provenance")
    if (
        record["schema_version"] != ARCHIVE_LOCATORS_SCHEMA
        or record["purpose"] != ARCHIVE_LOCATORS_PURPOSE
        or record["local_bytes_required"] is not False
        or type(record["local_bytes_required"]) is not bool
        or record["authorizing"] is not False
        or type(record["authorizing"]) is not bool
    ):
        raise BootstrapError("archive locator authority boundary drifted")
    return record


def load_archive_locators(
    path: Path | str,
    *,
    expected_identity: Mapping[str, object] | None = None,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    record, identity = _canonical_record(path, "archive locators")
    record = validate_archive_locators(record)
    if expected_identity is not None:
        for field in ("path", "sha256", "size_bytes"):
            if expected_identity.get(field) != identity[field]:
                raise BootstrapError("archive locator identity drifted")
    return record, identity


def _validate_candidate_placements_preregistration(
    repository_root: Path | str,
    candidate_placements: Path | str,
) -> dict[str, object]:
    """Replay the tracked external-artifact pin before admitting candidate bytes."""

    repository = _absolute(repository_root)
    candidate_path = _absolute(candidate_placements)
    expected_path = repository / str(CANDIDATE_PLACEMENTS_PIN["path"])
    if candidate_path != expected_path:
        raise BootstrapError("candidate placements is not the preregistered repository input")

    manifest_snapshot = authority.snapshot_regular(repository / "data" / "external_artifacts.json")
    try:
        manifest = authority.strict_loads(manifest_snapshot.data, "external artifact manifest")
    except Exception as exc:
        raise BootstrapError("external artifact manifest is not strict JSON") from exc
    manifest = _exact_keys(
        manifest,
        {"artifacts", "description", "schema_version"},
        "external artifact manifest",
    )
    artifacts = manifest["artifacts"]
    if (
        manifest["schema_version"] != EXTERNAL_ARTIFACTS_SCHEMA
        or type(manifest["schema_version"]) is not int
        or type(manifest["description"]) is not str
        or not manifest["description"]
        or type(artifacts) is not list
    ):
        raise BootstrapError("external artifact manifest semantics drifted")
    entries = [
        entry
        for entry in artifacts
        if isinstance(entry, Mapping) and entry.get("id") == CANDIDATE_PLACEMENTS_PIN["id"]
    ]
    if len(entries) != 1:
        raise BootstrapError("external artifact manifest lacks one candidate placements pin")
    entry = _exact_keys(
        entries[0],
        {
            "id",
            "optional_in_lightweight_checkout",
            "path",
            "required_for",
            "restore_hints",
            "sha256",
            "size_bytes",
        },
        "candidate placements external artifact entry",
    )
    if any(entry[field] != expected for field, expected in CANDIDATE_PLACEMENTS_PIN.items()):
        raise BootstrapError("candidate placements external artifact pin drifted")
    if (
        entry["optional_in_lightweight_checkout"] is not True
        or type(entry["optional_in_lightweight_checkout"]) is not bool
        or type(entry["required_for"]) is not list
        or not entry["required_for"]
        or any(type(value) is not str or not value for value in entry["required_for"])
        or len(set(entry["required_for"])) != len(entry["required_for"])
        or type(entry["restore_hints"]) is not list
        or not entry["restore_hints"]
        or any(type(value) is not str or not value for value in entry["restore_hints"])
    ):
        raise BootstrapError("candidate placements external artifact metadata drifted")

    observed = authority.full_identity(authority.snapshot_regular(candidate_path))
    if (
        observed["path"] != str(expected_path)
        or observed["sha256"] != CANDIDATE_PLACEMENTS_PIN["sha256"]
        or observed["size_bytes"] != CANDIDATE_PLACEMENTS_PIN["size_bytes"]
    ):
        raise BootstrapError("candidate placements bytes differ from the preregistered pin")
    return observed


def _digest_without(record: Mapping[str, object], field: str) -> str:
    value = dict(record)
    value.pop(field, None)
    return hashlib.sha256(authority.canonical_json(value)).hexdigest()


def _source_set_digest(source_identities: Mapping[str, object]) -> str:
    return hashlib.sha256(authority.canonical_json(source_identities)).hexdigest()


def _scientific_input_set_digest(source_identities: Mapping[str, object]) -> str:
    """Digest only bootstrap-known strict scientific input bytes, never paths or tools."""

    expected_roles = {f"input.{role}" for role in STRICT_INPUT_ROLES}
    actual_roles = {
        role for role in source_identities if type(role) is str and role.startswith("input.")
    }
    if actual_roles != expected_roles:
        raise BootstrapError("scientific input source roles drifted")
    members: dict[str, dict[str, object]] = {}
    archived_source_roles = {f"input.{role}" for role in ARCHIVED_SCIENTIFIC_INPUT_ROLES}
    for source_role in sorted(expected_roles - archived_source_roles):
        identity = source_identities[source_role]
        if not isinstance(identity, Mapping):
            raise BootstrapError(f"scientific input identity {source_role} is malformed")
        sha256 = identity.get("sha256")
        size_bytes = identity.get("size_bytes")
        if (
            type(sha256) is not str
            or SHA256_RE.fullmatch(sha256) is None
            or type(size_bytes) is not int
            or size_bytes < 0
        ):
            raise BootstrapError(f"scientific input identity {source_role} is malformed")
        members[source_role.removeprefix("input.")] = {
            "sha256": sha256,
            "size_bytes": size_bytes,
        }
    for role in sorted(ARCHIVED_SCIENTIFIC_INPUT_ROLES):
        locator_identity = source_identities[f"input.{role}"]
        if not isinstance(locator_identity, Mapping):
            raise BootstrapError(f"scientific input identity input.{role} is malformed")
        archive_locators, _identity = load_archive_locators(
            str(locator_identity.get("path", "")),
            expected_identity=locator_identity,
        )
        entry = archive_locators["entries"][role]
        members[role] = {
            "sha256": entry["sha256"],
            "size_bytes": entry["size_bytes"],
        }
    if set(members) != set(SCIENTIFIC_INPUT_ROLES):
        raise BootstrapError("scientific input member projection drifted")
    projection = {
        "arm_sequence": list(AB16_ARM_SEQUENCE),
        "experiment_contract_sha256": AB16_EXPERIMENT_CONTRACT_SHA256,
        "members": members,
        "schema": AB16_SCIENTIFIC_INPUT_SET_SCHEMA,
        "seed": AB16_SEED,
        "workers": AB16_WORKERS,
    }
    return hashlib.sha256(authority.canonical_json(projection)).hexdigest()


def _script_paths() -> dict[str, Path]:
    ab16_dir = Path(__file__).resolve().parent
    paths: dict[str, Path] = {}
    for role, filename in V4_SCRIPT_TOOL_FILES.items():
        paths[role] = V4_RESEARCH_DIR / filename
    for role, filename in AB16_SCRIPT_TOOL_FILES.items():
        paths[role] = ab16_dir / filename
    if set(paths) != set(SCRIPT_TOOL_FILES):
        raise BootstrapError("script tool role construction drifted")
    for role, path in paths.items():
        authority.snapshot_regular(path)
        if path.suffix != ".py":
            raise BootstrapError(f"script tool {role} is not a Python source")
    if not authority.REQUIRED_GATE1_TOOL_ROLES <= (set(paths) | set(SYSTEM_TOOL_ROLES)):
        raise BootstrapError("script allowlist misses a mandatory Gate-1 role")
    return paths


def _exact_path_map(
    value: Mapping[str, Path | str],
    roles: frozenset[str],
    label: str,
) -> dict[str, Path]:
    if type(value) is not dict or set(value) != set(roles):
        raise BootstrapError(f"{label} must have the exact pre-registered roles")
    result: dict[str, Path] = {}
    for role, raw_path in value.items():
        if type(role) is not str or not isinstance(raw_path, (str, os.PathLike)):
            raise BootstrapError(f"{label}.{role!s} path is malformed")
        path = _absolute(raw_path)
        authority.snapshot_regular(path)
        result[role] = path
    return result


def _resolved_system_tools(
    paths: Mapping[str, Path | str],
) -> tuple[dict[str, Path], dict[str, dict[str, object]]]:
    if type(paths) is not dict or set(paths) != set(SYSTEM_TOOL_ROLES):
        raise BootstrapError("system tools must have the exact pre-registered roles")
    resolved: dict[str, Path] = {}
    identities: dict[str, dict[str, object]] = {}
    for role, raw_path in sorted(paths.items()):
        if type(role) is not str or not isinstance(raw_path, (str, os.PathLike)):
            raise BootstrapError(f"system tool {role!s} path is malformed")
        _, full = authority.snapshot_tool(raw_path)
        resolved[role] = Path(str(full["path"]))
        identities[role] = dict(full)
    return resolved, identities


def _planned_source_identities(
    *,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    repository_root: Path | str | None = None,
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, Path],
    dict[str, Path],
    dict[str, Path],
]:
    strict_paths = _exact_path_map(
        strict_input_paths,
        STRICT_INPUT_ROLES,
        "strict inputs",
    )
    if strict_paths["history_freeze_manifest"] != strict_paths["legacy_control_a002"]:
        raise BootstrapError("historical roles must share the one tracked archive locator")
    load_archive_locators(strict_paths["history_freeze_manifest"])
    if repository_root is not None:
        _validate_candidate_placements_preregistration(
            repository_root,
            strict_paths["candidate_placements"],
        )
    system_paths, system_identities = _resolved_system_tools(system_tool_paths)
    scripts = _script_paths()
    identities: dict[str, dict[str, object]] = {}
    for role, path in sorted(scripts.items()):
        identities[f"script.{role}"] = authority.full_identity(authority.snapshot_regular(path))
    for role, full in sorted(system_identities.items()):
        identities[f"system.{role}"] = full
    for role, path in sorted(strict_paths.items()):
        identities[f"input.{role}"] = authority.full_identity(authority.snapshot_regular(path))
    return identities, scripts, system_paths, strict_paths


def observe_planned_sources(
    *,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
) -> dict[str, object]:
    """Observe planned sources without creating a candidate or campaign."""

    identities, _, _, _ = _planned_source_identities(
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
    )
    return {
        "planned_source_identities": identities,
        "planned_source_set_digest": _source_set_digest(identities),
    }


def _validate_source_identities(
    value: object,
) -> Mapping[str, Any]:
    expected_roles = {
        *(f"script.{role}" for role in SCRIPT_TOOL_FILES),
        *(f"system.{role}" for role in SYSTEM_TOOL_ROLES),
        *(f"input.{role}" for role in STRICT_INPUT_ROLES),
    }
    records = _exact_keys(value, expected_roles, "planned source identities")
    for role, identity in records.items():
        expected_keys = {
            "device",
            "inode",
            "mode",
            "mode_octal",
            "path",
            "sha256",
            "size_bytes",
        }
        if role.startswith("system."):
            expected_keys.add("requested_path")
        item = _exact_keys(
            identity,
            expected_keys,
            f"planned source identity {role}",
        )
        if (
            type(item["path"]) is not str
            or not Path(item["path"]).is_absolute()
            or type(item["sha256"]) is not str
            or SHA256_RE.fullmatch(item["sha256"]) is None
            or type(item["size_bytes"]) is not int
            or item["size_bytes"] < 0
            or type(item["device"]) is not int
            or type(item["inode"]) is not int
            or type(item["mode"]) is not int
            or type(item["mode_octal"]) is not str
            or item["mode_octal"] != f"{item['mode']:04o}"
            or (
                role.startswith("system.")
                and (type(item["requested_path"]) is not str or not Path(item["requested_path"]).is_absolute())
            )
        ):
            raise BootstrapError(f"planned source identity {role} is malformed")
    return records


def validate_candidate(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "arm_launch_authorized",
            "candidate_id",
            "candidate_only",
            "created_at_utc",
            "formal_campaign_creation_authorized",
            "path_preregistration_identity",
            "planned_source_identities",
            "planned_source_set_digest",
            "purpose",
            "repository_head",
            "repository_root",
            "run_nonce",
            "schema_version",
            "target_campaign_dir",
        },
        "offline candidate",
    )
    _utc(record["created_at_utc"], "candidate created_at_utc")
    authority.validate_detached_identity(
        record["path_preregistration_identity"],
        "candidate AB16 path preregistration",
    )
    sources = _validate_source_identities(record["planned_source_identities"])
    if (
        record["schema_version"] != CANDIDATE_SCHEMA
        or record["purpose"] != CANDIDATE_PURPOSE
        or record["candidate_only"] is not True
        or record["formal_campaign_creation_authorized"] is not False
        or record["arm_launch_authorized"] is not False
        or type(record["candidate_id"]) is not str
        or record["candidate_id"] != _digest_without(record, "candidate_id")
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["repository_root"]) is not str
        or not Path(record["repository_root"]).is_absolute()
        or type(record["run_nonce"]) is not str
        or RUN_NONCE_RE.fullmatch(record["run_nonce"]) is None
        or type(record["target_campaign_dir"]) is not str
        or not Path(record["target_campaign_dir"]).is_absolute()
        or Path(record["target_campaign_dir"]).name != record["run_nonce"]
        or record["planned_source_set_digest"] != _source_set_digest(sources)
    ):
        raise BootstrapError("offline candidate semantics drifted")
    return record


def _assert_campaign_absent(campaign_dir: Path) -> None:
    authority._reject_symlink_chain(campaign_dir.parent)  # noqa: SLF001
    if not campaign_dir.parent.is_dir():
        raise BootstrapError("campaign parent must already exist")
    if campaign_dir.exists() or campaign_dir.is_symlink():
        raise BootstrapError("campaign directory already exists; no-overwrite applies")


def _assert_expected_tool_identity(
    observed: Mapping[str, object],
    expected: Mapping[str, object],
) -> None:
    fields = {
        "device",
        "inode",
        "mode",
        "mode_octal",
        "path",
        "sha256",
        "size_bytes",
    }
    if not fields <= set(expected) or any(observed[field] != expected[field] for field in fields):
        raise BootstrapError("Git executable differs from the planned source identity")


def _observe_repository_head(
    repository_root: Path,
    git_path: Path,
    *,
    expected_identity: Mapping[str, object],
) -> str:
    absolute = _absolute(git_path)
    try:
        _, observed = authority.snapshot_tool(absolute)
    except authority.AuthorityError as exc:
        raise BootstrapError(f"Git executable path is invalid: {exc}") from exc
    _assert_expected_tool_identity(observed, expected_identity)
    try:
        completed = subprocess.run(
            [
                str(absolute),
                "-C",
                str(repository_root),
                "rev-parse",
                "--verify",
                "HEAD",
            ],
            check=False,
            close_fds=True,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BootstrapError(f"repository HEAD observation failed: {exc}") from exc
    if (
        completed.returncode != 0
        or completed.stderr
        or len(completed.stdout) != 41
        or not completed.stdout.endswith(b"\n")
    ):
        raise BootstrapError("repository HEAD observation was not one clean SHA")
    try:
        head = completed.stdout[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise BootstrapError("repository HEAD was not ASCII") from exc
    if GIT_SHA_RE.fullmatch(head) is None:
        raise BootstrapError("repository HEAD was not lowercase 40-hex")
    return head


def _validate_manager_capture(value: object) -> dict[str, object]:
    captured = value
    if type(captured) is not dict or set(captured) != {
        "manager_epoch",
        "transcript",
    }:
        raise BootstrapError("manager capture returned the wrong exact schema")
    authority.validate_manager_epoch(captured["manager_epoch"])
    authority.validate_manager_epoch_capture_transcript(
        captured["transcript"],
        expected_epoch=captured["manager_epoch"],
    )
    return captured


def _capture_epoch(
    *,
    scripts: Mapping[str, Path],
    system_paths: Mapping[str, Path],
) -> dict[str, object]:
    return _validate_manager_capture(
        authority.capture_manager_epoch_with_transcript(
            attestor_path=scripts["manager_attestor_v4"],
            busctl_path=system_paths["busctl"],
            python_path=system_paths["attestor_python"],
            sudo_path=system_paths["sudo"],
        )
    )


def _path_preregistration(
    campaign_dir: Path | str,
    *,
    scientific_input_set_sha256: str,
) -> dict[str, object]:
    """Build the immutable scientific design and retryable slot-root registry."""

    if type(scientific_input_set_sha256) is not str or SHA256_RE.fullmatch(scientific_input_set_sha256) is None:
        raise BootstrapError("scientific input-set digest is malformed")
    campaign = _absolute(campaign_dir)
    prospective = campaign / "prospective-ab16"
    baseline = prospective / "baseline"
    package_payload = campaign / "campaign-authority" / "package" / "payload"
    slot_roots = {slot: str(prospective / "arms" / slot) for slot in AB16_ARM_SEQUENCE}
    return {
        "arm_sequence": list(AB16_ARM_SEQUENCE),
        "attempt_directory_pattern": "attempt-[0-9]{4,}",
        "baseline_admission_path": str(prospective / "baseline-admission-a001.json"),
        "baseline_fixed_replay_path": str(baseline / "fixed-replay-a001.json"),
        "baseline_incumbent_path": str(baseline / "incumbent.json"),
        "baseline_rebuilt_metadata_path": str(baseline / "rebuilt-model-metadata.json"),
        "baseline_rebuilt_model_path": str(baseline / "cut-free-model.bin"),
        "binding_paths": {
            slot: str(prospective / "bindings" / f"{slot}.json")
            for slot in AB16_ARM_SEQUENCE
        },
        "campaign_dir": str(campaign),
        "classification_contract_path": str(package_payload / "tool.ab16_contract_v1.py"),
        "common_prestate_path": str(prospective / "common-prestate-a001.json"),
        "experiment_contract_sha256": AB16_EXPERIMENT_CONTRACT_SHA256,
        "manifest_path": str(prospective / "manifest-a001.json"),
        "purpose": PATH_PREREGISTRATION_PURPOSE,
        "retry_policy": dict(AB16_RETRY_POLICY),
        "run_nonce": campaign.name,
        "runtime_max_sec": 3600,
        "schema": PATH_PREREGISTRATION_SCHEMA,
        "seed": AB16_SEED,
        "scientific_input_set_sha256": scientific_input_set_sha256,
        "slot_roots": slot_roots,
        "suite_selection_path": str(prospective / "selection-a001.json"),
        "terminal_classification_path": str(prospective / "terminal-classification-a001.json"),
        "workers": AB16_WORKERS,
    }


def validate_path_preregistration(
    value: object,
    *,
    campaign_dir: Path | str,
) -> Mapping[str, Any]:
    """Reject any scientific design or slot-root topology drift."""

    if not isinstance(value, Mapping):
        raise BootstrapError("AB16 path preregistration key set drifted")
    scientific_input_set_sha256 = value.get("scientific_input_set_sha256")
    if type(scientific_input_set_sha256) is not str:
        raise BootstrapError("scientific input-set digest is malformed")
    expected = _path_preregistration(
        campaign_dir,
        scientific_input_set_sha256=scientific_input_set_sha256,
    )
    record = _exact_keys(
        value,
        set(expected),
        "AB16 path preregistration",
    )
    if record != expected:
        raise BootstrapError("AB16 path preregistration topology drifted")
    campaign = _absolute(campaign_dir)
    path_fields = {
        "baseline_admission_path",
        "baseline_fixed_replay_path",
        "baseline_incumbent_path",
        "baseline_rebuilt_metadata_path",
        "baseline_rebuilt_model_path",
        "classification_contract_path",
        "common_prestate_path",
        "manifest_path",
        "suite_selection_path",
        "terminal_classification_path",
    }
    paths = [Path(record[field]) for field in path_fields]
    for mapping_field in ("binding_paths", "slot_roots"):
        mapping = _exact_keys(
            record[mapping_field],
            set(AB16_ARM_SEQUENCE),
            f"AB16 path preregistration {mapping_field}",
        )
        paths.extend(Path(path) for path in mapping.values())
    slot_roots = record["slot_roots"]
    expected_parent = campaign / "prospective-ab16" / "arms"
    if (
        len(set(slot_roots.values())) != len(AB16_ARM_SEQUENCE)
        or any(Path(slot_roots[slot]).parent != expected_parent for slot in AB16_ARM_SEQUENCE)
        or any(not path.is_absolute() or not path.is_relative_to(campaign) for path in paths)
    ):
        raise BootstrapError("AB16 path preregistration escaped the campaign")
    return record


def _validate_path_preregistration_against_root(
    value: Mapping[str, Any],
    root: Mapping[str, Any],
    *,
    campaign_dir: Path | str,
) -> None:
    """Join the package-pinned registry to the unchanged v4 campaign root."""

    record = validate_path_preregistration(
        value,
        campaign_dir=campaign_dir,
    )
    prospective = root["stage_topology"]["prospective_ab16"]
    root_slot_roots = {arm["slot"]: arm["attempt_dir"] for arm in prospective["arms"]}
    if (
        record["manifest_path"] != prospective["manifest_path"]
        or record["suite_selection_path"] != prospective["arm_selection_path"]
        or record["terminal_classification_path"] != prospective["terminal_classification_path"]
        or record["slot_roots"] != root_slot_roots
        or set(root_slot_roots) != set(AB16_ARM_SEQUENCE)
    ):
        raise BootstrapError("AB16 path preregistration differs from v4 root")


def build_offline_candidate(
    *,
    output_path: Path | str,
    repository_root: Path | str,
    target_campaign_dir: Path | str,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    created_at_utc: str | None = None,
) -> dict[str, object]:
    """Write only a non-authorizing candidate; never create a campaign."""

    campaign_dir = _absolute(target_campaign_dir)
    candidate_output = _absolute(output_path)
    preregistration_output = candidate_output.parent / "ab16-path-preregistration.json"
    repository = _absolute(repository_root)
    _assert_campaign_absent(campaign_dir)
    authority._reject_symlink_chain(candidate_output.parent)  # noqa: SLF001
    if (
        candidate_output.exists()
        or candidate_output.is_symlink()
        or preregistration_output.exists()
        or preregistration_output.is_symlink()
    ):
        raise BootstrapError("offline candidate or path preregistration already exists")
    planned, _, system_paths, _ = _planned_source_identities(
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
        repository_root=repository,
    )
    digest = _source_set_digest(planned)
    observed_head = _observe_repository_head(
        repository,
        system_paths["git"],
        expected_identity=planned["system.git"],
    )
    timestamp = created_at_utc or _utc_now()
    _utc(timestamp, "candidate created_at_utc")
    preregistration = _path_preregistration(
        campaign_dir,
        scientific_input_set_sha256=_scientific_input_set_digest(planned),
    )
    validate_path_preregistration(
        preregistration,
        campaign_dir=campaign_dir,
    )
    preregistration_identity = authority.write_exclusive(
        preregistration_output,
        authority.canonical_json(preregistration),
    )
    candidate: dict[str, object] = {
        "arm_launch_authorized": False,
        "candidate_id": "",
        "candidate_only": True,
        "created_at_utc": timestamp,
        "formal_campaign_creation_authorized": False,
        "path_preregistration_identity": preregistration_identity,
        "planned_source_identities": planned,
        "planned_source_set_digest": digest,
        "purpose": CANDIDATE_PURPOSE,
        "repository_head": observed_head,
        "repository_root": str(repository),
        "run_nonce": campaign_dir.name,
        "schema_version": CANDIDATE_SCHEMA,
        "target_campaign_dir": str(campaign_dir),
    }
    candidate["candidate_id"] = _digest_without(candidate, "candidate_id")
    validate_candidate(candidate)
    candidate_identity = authority.write_exclusive(
        candidate_output,
        authority.canonical_json(candidate),
    )
    if campaign_dir.exists() or campaign_dir.is_symlink():
        raise BootstrapError("candidate creation illegally created the campaign directory")
    return {
        "candidate": candidate,
        "candidate_identity": candidate_identity,
        "formal_campaign_created": False,
        "path_preregistration": preregistration,
        "path_preregistration_identity": preregistration_identity,
    }


def _payload_identity(
    package_dir: Path,
    role: str,
) -> dict[str, object]:
    return authority.detached_identity(authority.snapshot_regular(package_dir / "payload" / role))


def _package_roles(
    *,
    scripts: Mapping[str, Path],
    system_paths: Mapping[str, Path],
    strict_paths: Mapping[str, Path],
    candidate_path: Path,
    capture_path: Path,
    path_preregistration_path: Path,
) -> tuple[
    list[authority.SourceSpec],
    dict[str, str],
    dict[str, str],
]:
    specs: list[authority.SourceSpec] = []
    script_roles: dict[str, str] = {}
    for role, path in sorted(scripts.items()):
        package_role = "campaign_authority_v4.py" if role == "campaign_authority_v4" else f"tool.{role}.py"
        script_roles[role] = package_role
        specs.append(authority.SourceSpec(package_role, path))
    for role, path in sorted(system_paths.items()):
        specs.append(authority.SourceSpec(f"system.{role}.bin", path))
    input_roles: dict[str, str] = {}
    for role, path in sorted(strict_paths.items()):
        suffix = ".json" if role in JSON_INPUT_ROLES else ".txt"
        package_role = f"input.{role}{suffix}"
        input_roles[role] = package_role
        specs.append(
            authority.SourceSpec(
                package_role,
                path,
                parse_json=role in CANONICAL_JSON_INPUT_ROLES,
            )
        )
    input_roles[CANDIDATE_INPUT_ROLE] = CANDIDATE_PACKAGE_ROLE
    specs.append(authority.SourceSpec(CANDIDATE_PACKAGE_ROLE, candidate_path, parse_json=True))
    input_roles[CAPTURE_INPUT_ROLE] = CAPTURE_PACKAGE_ROLE
    specs.append(
        authority.SourceSpec(
            CAPTURE_PACKAGE_ROLE,
            capture_path,
            parse_json=True,
        )
    )
    input_roles[PATH_PREREGISTRATION_INPUT_ROLE] = PATH_PREREGISTRATION_PACKAGE_ROLE
    specs.append(
        authority.SourceSpec(
            PATH_PREREGISTRATION_PACKAGE_ROLE,
            path_preregistration_path,
            parse_json=True,
        )
    )
    return specs, script_roles, input_roles


def _detached_from_full(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "path": value["path"],
        "sha256": value["sha256"],
        "size_bytes": value["size_bytes"],
    }


def _package_source_join(
    package_dir: Path,
    *,
    planned: Mapping[str, Mapping[str, object]],
    candidate_identity: Mapping[str, object],
    capture_identity: Mapping[str, object],
    path_preregistration_identity: Mapping[str, object],
) -> None:
    manifest_snapshot = authority.snapshot_regular(package_dir / "package-manifest.json")
    manifest = authority.strict_loads(
        manifest_snapshot.data,
        "AB16 package manifest source join",
    )
    if not isinstance(manifest, Mapping) or not isinstance(
        manifest.get("external_sources"),
        list,
    ):
        raise BootstrapError("package source manifest is malformed")
    records: dict[str, Mapping[str, object]] = {}
    for raw_record in manifest["external_sources"]:
        record = _exact_keys(
            raw_record,
            {
                "package_path",
                "parse_json",
                "role",
                "source_identity",
            },
            "package external source",
        )
        role = record["role"]
        if type(role) is not str or role in records:
            raise BootstrapError("package external source role drifted")
        if not isinstance(record["source_identity"], Mapping):
            raise BootstrapError("package source identity is malformed")
        records[role] = record["source_identity"]

    expected_full: dict[str, Mapping[str, object]] = {}
    for role in SCRIPT_TOOL_FILES:
        package_role = "campaign_authority_v4.py" if role == "campaign_authority_v4" else f"tool.{role}.py"
        expected_full[package_role] = planned[f"script.{role}"]
    for role in SYSTEM_TOOL_ROLES:
        expected_full[f"system.{role}.bin"] = planned[f"system.{role}"]
    for role in STRICT_INPUT_ROLES:
        suffix = ".json" if role in JSON_INPUT_ROLES else ".txt"
        expected_full[f"input.{role}{suffix}"] = planned[f"input.{role}"]
    if set(records) != (
        set(expected_full)
        | {
            CANDIDATE_PACKAGE_ROLE,
            CAPTURE_PACKAGE_ROLE,
            PATH_PREREGISTRATION_PACKAGE_ROLE,
        }
    ):
        raise BootstrapError("package external source role set drifted")
    for role, expected in expected_full.items():
        actual = dict(records[role])
        normalized_expected = dict(expected)
        normalized_expected.pop("requested_path", None)
        if actual != normalized_expected:
            raise BootstrapError(f"package source changed after candidate capture: {role}")
    detached_expectations = {
        CANDIDATE_PACKAGE_ROLE: candidate_identity,
        CAPTURE_PACKAGE_ROLE: capture_identity,
        PATH_PREREGISTRATION_PACKAGE_ROLE: path_preregistration_identity,
    }
    for role, expected in detached_expectations.items():
        if _detached_from_full(records[role]) != expected:
            raise BootstrapError(f"package candidate/capture source changed during creation: {role}")


def _check_epoch_toolchain(
    epoch: Mapping[str, object],
    *,
    scripts: Mapping[str, Path],
    system_full: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    attestor = {key: epoch["attestation_toolchain"]["attestor"][key] for key in ("path", "sha256", "size_bytes")}
    authority.validate_detached_identity(attestor, "epoch attestor")
    current_attestor = authority.detached_identity(authority.snapshot_regular(scripts["manager_attestor_v4"]))
    expected = {
        "attestor_python": epoch["attestation_toolchain"]["python"],
        "busctl": epoch["observation_toolchain"]["busctl"],
        "sudo": epoch["attestation_toolchain"]["sudo"],
    }
    if attestor != current_attestor:
        raise BootstrapError("manager epoch attestor does not match selected bytes")
    for role, full in expected.items():
        if _detached_from_full(system_full[role]) != {key: full[key] for key in ("path", "sha256", "size_bytes")}:
            raise BootstrapError(f"manager epoch {role} does not match selected bytes")
    return attestor


def bootstrap_campaign(
    *,
    campaign_dir: Path | str,
    repository_root: Path | str,
    offline_candidate: Path | str,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    created_at_utc: str | None = None,
    manager_capture: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create a complete v4 campaign authority from one replayed candidate."""

    output = _absolute(campaign_dir)
    repository = _absolute(repository_root)
    _assert_campaign_absent(output)
    candidate_path = _absolute(offline_candidate)
    candidate, candidate_identity = _canonical_record(
        candidate_path,
        "offline candidate",
    )
    candidate = validate_candidate(candidate)
    path_preregistration_path = _absolute(candidate["path_preregistration_identity"]["path"])
    path_preregistration, path_preregistration_identity = _canonical_record(
        path_preregistration_path,
        "AB16 path preregistration",
    )
    if path_preregistration_identity != candidate["path_preregistration_identity"]:
        raise BootstrapError("candidate AB16 path preregistration identity drifted")
    path_preregistration = validate_path_preregistration(
        path_preregistration,
        campaign_dir=output,
    )
    if (
        candidate["target_campaign_dir"] != str(output)
        or candidate["run_nonce"] != output.name
        or candidate["repository_root"] != str(repository)
    ):
        raise BootstrapError("offline candidate does not target this campaign checkout")

    planned, scripts, system_paths, strict_paths = _planned_source_identities(
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
        repository_root=repository,
    )
    if candidate["planned_source_identities"] != planned or candidate[
        "planned_source_set_digest"
    ] != _source_set_digest(planned):
        raise BootstrapError("planned package source bytes drifted after candidate capture")
    if path_preregistration["scientific_input_set_sha256"] != _scientific_input_set_digest(planned):
        raise BootstrapError("scientific input-set anchor differs from planned sources")
    system_full = {role: planned[f"system.{role}"] for role in SYSTEM_TOOL_ROLES}
    repository_head = _observe_repository_head(
        repository,
        system_paths["git"],
        expected_identity=planned["system.git"],
    )
    if repository_head != candidate["repository_head"]:
        raise BootstrapError("repository HEAD drifted before campaign creation")
    captured = (
        _capture_epoch(scripts=scripts, system_paths=system_paths)
        if manager_capture is None
        else _validate_manager_capture(manager_capture)
    )
    epoch_attestor = _check_epoch_toolchain(
        captured["manager_epoch"],
        scripts=scripts,
        system_full=system_full,
    )
    if (
        _observe_repository_head(
            repository,
            system_paths["git"],
            expected_identity=planned["system.git"],
        )
        != repository_head
    ):
        raise BootstrapError("repository HEAD drifted before campaign creation")
    timestamp = created_at_utc or _utc_now()
    _utc(timestamp, "bootstrap created_at_utc")

    authority.mkdir_exclusive(output)
    bootstrap_dir = authority.mkdir_exclusive(output / "bootstrap-authority")
    capture_record = {
        "candidate_identity": candidate_identity,
        "formal_arm_launch_authorized": False,
        "manager_epoch": captured["manager_epoch"],
        "purpose": "manager epoch captured after candidate replay for v4 campaign creation",
        "repository_head": repository_head,
        "run_nonce": output.name,
        "schema": CAPTURE_SCHEMA,
        "transcript": captured["transcript"],
    }
    capture_path = bootstrap_dir / "manager-epoch-capture.json"
    capture_source_identity = authority.write_exclusive(
        capture_path,
        authority.canonical_json(capture_record),
    )
    package_dir = authority.mkdir_exclusive(output / "campaign-authority") / "package"
    source_specs, script_package_roles, input_package_roles = _package_roles(
        scripts=scripts,
        system_paths=system_paths,
        strict_paths=strict_paths,
        candidate_path=candidate_path,
        capture_path=capture_path,
        path_preregistration_path=path_preregistration_path,
    )
    package = authority.build_package(
        package_dir,
        source_specs,
        repository_head=repository_head,
        run_nonce=output.name,
        manager_epoch=captured["manager_epoch"],
    )
    _package_source_join(
        package_dir,
        planned=planned,
        candidate_identity=candidate_identity,
        capture_identity=capture_source_identity,
        path_preregistration_identity=path_preregistration_identity,
    )
    tools = {role: _payload_identity(package_dir, package_role) for role, package_role in script_package_roles.items()}
    if (
        tools["manager_attestor_v4"]["sha256"] != epoch_attestor["sha256"]
        or tools["manager_attestor_v4"]["size_bytes"] != epoch_attestor["size_bytes"]
    ):
        raise BootstrapError("sealed attestor copy differs from epoch attestor")
    tools["manager_attestor_v4"] = epoch_attestor
    tools.update({role: _detached_from_full(system_full[role]) for role in SYSTEM_TOOL_ROLES})
    inputs = {role: _payload_identity(package_dir, package_role) for role, package_role in input_package_roles.items()}
    project_lock_source = authority.detached_identity(authority.snapshot_regular(strict_paths["project_lock"]))
    project_lock_copy = inputs["project_lock"]
    if (
        project_lock_source["sha256"] != project_lock_copy["sha256"]
        or project_lock_source["size_bytes"] != project_lock_copy["size_bytes"]
    ):
        raise BootstrapError("sealed PROJECT_LOCK differs from selected source")
    inputs["project_lock"] = project_lock_source

    root = authority.build_campaign_root(
        output,
        package=package,
        repository_head=repository_head,
        run_nonce=output.name,
        manager_epoch=captured["manager_epoch"],
        authority_tools=tools,
        strict_inputs=inputs,
        created_at_utc=timestamp,
    )
    root_scientific_sources = {
        f"input.{role}": root["strict_inputs"][role] for role in STRICT_INPUT_ROLES
    }
    if path_preregistration["scientific_input_set_sha256"] != _scientific_input_set_digest(
        root_scientific_sources
    ):
        raise BootstrapError("package scientific input-set anchor differs from preregistration")
    _validate_path_preregistration_against_root(
        path_preregistration,
        root,
        campaign_dir=output,
    )
    root_identity = authority.write_campaign_root(output, root)
    selection = authority.make_gate1_selection(
        root,
        campaign_root_identity=root_identity,
        tools=tools,
        inputs=inputs,
        created_at_utc=timestamp,
    )
    selection_identity = authority.write_gate1_selection(
        output / "campaign-root.json",
        root_identity,
        selection,
    )
    if (
        _observe_repository_head(
            repository,
            system_paths["git"],
            expected_identity=planned["system.git"],
        )
        != repository_head
    ):
        raise BootstrapError("repository HEAD drifted after selection; campaign is consumed")
    authority.verify_package(
        package_dir,
        expected_manager_epoch=captured["manager_epoch"],
        replay_external=True,
    )
    authority.replay_gate1_selection(
        output / "campaign-root.json",
        root_identity,
        selection_identity,
        current_manager_epoch=captured["manager_epoch"],
    )
    selection_path = Path(root["stage_topology"]["gate1_v4"]["selection_path"])
    if any(
        path.exists() or path.is_symlink() for path in authority.reserved_child_paths(root) if path != selection_path
    ):
        raise BootstrapError("a reserved post-selection child was created")
    return {
        "bootstrap_capture_source_identity": capture_source_identity,
        "campaign_dir": str(output),
        "campaign_root_identity": root_identity,
        "candidate_identity": candidate_identity,
        "formal_arm_launch_authorized": False,
        "gate1_selection_identity": selection_identity,
        "organic_ab16_authorized": False,
        "package_id": package["package_id"],
        "path_preregistration_identity": inputs[PATH_PREREGISTRATION_INPUT_ROLE],
        "repository_head": repository_head,
        "run_nonce": output.name,
        "schema": RESULT_SCHEMA,
        "status": "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED",
    }


def _add_common_cli_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    parser.add_argument(
        "--python3-13",
        type=Path,
        default=Path("/home/zhuran24/zmd-pj/.venv-uvbolt-backup/bin/python3.13"),
    )
    parser.add_argument(
        "--attestor-python",
        type=Path,
        default=Path("/usr/bin/python3.14"),
    )
    parser.add_argument("--busctl", type=Path, default=Path("/usr/bin/busctl"))
    parser.add_argument("--git", type=Path, default=Path("/usr/bin/git"))
    parser.add_argument("--sudo", type=Path, default=Path("/usr/bin/sudo"))
    parser.add_argument(
        "--systemctl",
        type=Path,
        default=Path("/usr/bin/systemctl"),
    )
    parser.add_argument(
        "--systemd-run",
        type=Path,
        default=Path("/usr/bin/systemd-run"),
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    candidate = commands.add_parser(
        "candidate",
        help="freeze repository-local sources in one non-authorizing O_EXCL candidate",
    )
    _add_common_cli_arguments(candidate)
    candidate.add_argument("--candidate-output", type=Path, required=True)
    bootstrap = commands.add_parser(
        "bootstrap",
        help="replay one offline candidate and create v4 campaign authority",
    )
    _add_common_cli_arguments(bootstrap)
    bootstrap.add_argument("--offline-candidate", type=Path, required=True)
    return parser.parse_args(argv)


def _production_strict_inputs(
    repository: Path,
) -> dict[str, Path]:
    archive_locators = (
        repository
        / "docs"
        / "research"
        / "noncert_cuts_ab16_20260724"
        / "archive_locators_v1.json"
    )
    return {
        "candidate_placements": (repository / "data" / "preprocessed" / "candidate_placements.json"),
        "canonical_rules": repository / "rules" / "canonical_rules.json",
        "cuts_mandatory_schedule": (
            repository
            / "docs"
            / "research"
            / "b1_sidewise_marked_membrane_authority_recovery_20260724"
            / "04_cuts_mandatory_schedule.md"
        ),
        "history_freeze_manifest": archive_locators,
        "legacy_control_a002": archive_locators,
        "mandatory_instances": (repository / "data" / "preprocessed" / "mandatory_exact_instances.json"),
        "project_lock": repository / "PROJECT_LOCK.md",
    }


def _cli_system_tools(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "attestor_python": args.attestor_python,
        "busctl": args.busctl,
        "git": args.git,
        "python3_13": args.python3_13,
        "sudo": args.sudo,
        "systemctl": args.systemctl,
        "systemd_run": args.systemd_run,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repository = _absolute(args.repository_root)
    try:
        if args.command == "candidate":
            result = build_offline_candidate(
                output_path=args.candidate_output,
                repository_root=repository,
                target_campaign_dir=args.campaign_dir,
                strict_input_paths=_production_strict_inputs(repository),
                system_tool_paths=_cli_system_tools(args),
                created_at_utc=args.created_at_utc,
            )
        elif args.command == "bootstrap":
            result = bootstrap_campaign(
                campaign_dir=args.campaign_dir,
                repository_root=repository,
                offline_candidate=args.offline_candidate,
                strict_input_paths=_production_strict_inputs(repository),
                system_tool_paths=_cli_system_tools(args),
                created_at_utc=args.created_at_utc,
            )
        else:
            raise BootstrapError("unknown CLI command")
    except (authority.AuthorityError, BootstrapError) as exc:
        sys.stderr.buffer.write(
            authority.canonical_json(
                {
                    "error": str(exc),
                    "schema": RESULT_SCHEMA,
                    "status": "FAIL_CLOSED",
                }
            )
        )
        return 2
    sys.stdout.buffer.write(authority.canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
