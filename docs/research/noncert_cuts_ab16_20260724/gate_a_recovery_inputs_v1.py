#!/usr/bin/env python3
"""Publish one no-overwrite AB16 Gate-A recovery input set.

This is the production boundary for the two path maps consumed by
``disposable_drill_authority_v2.py``.  It also publishes the detached
planned-source observation consumed by the pinned Gate-A entrypoint.  All
three files use the lifecycle canonical JSON encoding, which has no trailing
newline.

The command creates input authority only.  It does not acquire a validation
lock, capture a manager epoch, build a disposable authority, launch a unit,
run preflight, create a formal campaign, or authorize a solver or arm.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import sys
from typing import Any, cast


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ab16_campaign_bootstrap_v2 as bootstrap  # noqa: E402
import organic_resource_lifecycle_v2 as lifecycle  # noqa: E402


SCHEMA_VERSION = "noncert-cuts-ab16-gate-a-recovery-inputs-v1"
PURPOSE = "AB16_GATE_A_CANONICAL_RECOVERY_INPUT_PRODUCTION"
STRICT_INPUTS_NAME = "strict-inputs.json"
SYSTEM_TOOLS_NAME = "system-tools.json"
PLANNED_OBSERVATION_NAME = "planned-source-observation.json"
INPUT_AUTHORITY_DIR_NAME = "input-authority-a001"


class RecoveryInputError(RuntimeError):
    """A recovery input could not be published without weakening authority."""


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _canonical_path_map(
    value: Mapping[str, Path | str],
    *,
    expected_roles: frozenset[str],
    label: str,
) -> dict[str, str]:
    if type(value) is not dict or set(value) != set(expected_roles):
        raise RecoveryInputError(f"{label} must have the exact registered roles")
    result: dict[str, str] = {}
    for role, raw_path in value.items():
        if type(role) is not str or not (type(raw_path) is str or isinstance(raw_path, Path)):
            raise RecoveryInputError(f"{label}.{role!s} must be a path string")
        path = _absolute(raw_path)
        if not path.is_absolute():
            raise RecoveryInputError(f"{label}.{role} must be absolute")
        result[role] = str(path)
    return result


def _identity(raw: bytes, identity: Mapping[str, Any], *, path: Path) -> dict[str, object]:
    expected = {
        "mode": identity["mode"],
        "path": str(_absolute(path)),
        "sha256": identity["sha256"],
        "size_bytes": identity["size_bytes"],
    }
    observed = lifecycle.snapshot_regular(path)
    actual = {
        "mode": observed.identity["mode"],
        "path": observed.identity["path"],
        "sha256": observed.identity["sha256"],
        "size_bytes": observed.identity["size_bytes"],
    }
    if actual != expected or observed.raw != raw:
        raise RecoveryInputError(f"published bytes drifted for {path.name}")
    return actual


def publish_recovery_inputs(
    *,
    output_dir: Path | str,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    resource_calibration_bundle_paths: Mapping[str, Path | str],
) -> dict[str, object]:
    """Create one exact three-file recovery input directory."""

    destination = _absolute(output_dir)
    strict_map = _canonical_path_map(
        strict_input_paths,
        expected_roles=bootstrap.STRICT_INPUT_ROLES,
        label="strict input path map",
    )
    system_map = _canonical_path_map(
        system_tool_paths,
        expected_roles=bootstrap.SYSTEM_TOOL_ROLES,
        label="system tool path map",
    )

    # Validate every mapped source and tool before consuming the output
    # directory.  This uses the same source enumeration as the downstream
    # disposable-authority builder.
    observation = bootstrap.observe_planned_sources(
        strict_input_paths=strict_map,
        system_tool_paths=system_map,
    )
    (
        _calibration_paths,
        calibration_identities,
    ) = bootstrap._resource_calibration_bundle_sources(  # noqa: SLF001
        resource_calibration_bundle_paths
    )
    observation["resource_calibration_bundle_identities"] = (
        calibration_identities
    )
    if type(observation) is not dict or set(observation) != {
        "planned_source_identities",
        "planned_source_set_digest",
        "resource_calibration_bundle_identities",
    }:
        raise RecoveryInputError("planned-source observation schema drifted")

    bootstrap.authority.mkdir_exclusive(destination, mode=0o700)
    input_authority_dir = bootstrap.authority.mkdir_exclusive(
        destination / INPUT_AUTHORITY_DIR_NAME,
        mode=0o700,
    )
    strict_path = input_authority_dir / STRICT_INPUTS_NAME
    system_path = input_authority_dir / SYSTEM_TOOLS_NAME
    observation_path = input_authority_dir / PLANNED_OBSERVATION_NAME

    strict_raw = lifecycle.canonical_json_bytes(strict_map)
    system_raw = lifecycle.canonical_json_bytes(system_map)
    observation_raw = lifecycle.canonical_json_bytes(observation)
    if any(raw.endswith(b"\n") for raw in (strict_raw, system_raw, observation_raw)):
        raise RecoveryInputError("lifecycle canonical JSON unexpectedly has a trailing newline")

    strict_identity = lifecycle.write_exclusive(strict_path, strict_raw)
    system_identity = lifecycle.write_exclusive(system_path, system_raw)

    reloaded_strict = lifecycle.strict_loads(
        lifecycle.snapshot_regular(strict_path).raw,
        "strict input path map",
    )
    reloaded_system = lifecycle.strict_loads(
        lifecycle.snapshot_regular(system_path).raw,
        "system tool path map",
    )
    if reloaded_strict != strict_map or reloaded_system != system_map:
        raise RecoveryInputError("published path map semantic replay drifted")

    replayed_observation = bootstrap.observe_planned_sources(
        strict_input_paths=reloaded_strict,
        system_tool_paths=reloaded_system,
    )
    replayed_observation["resource_calibration_bundle_identities"] = (
        calibration_identities
    )
    if replayed_observation != observation:
        raise RecoveryInputError("planned-source observation drifted after path-map publication")
    observation_identity = lifecycle.write_exclusive(
        observation_path,
        observation_raw,
    )

    entries = list(input_authority_dir.iterdir())
    expected_members = {
        STRICT_INPUTS_NAME,
        SYSTEM_TOOLS_NAME,
        PLANNED_OBSERVATION_NAME,
    }
    if (
        {item.name for item in entries} != expected_members
        or any(not item.is_file() or item.is_symlink() for item in entries)
        or list(destination.iterdir()) != [input_authority_dir]
    ):
        raise RecoveryInputError("recovery input directory member set drifted")

    return {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "input_authority_dir": str(input_authority_dir),
        "planned_source_count": len(
            cast(
                Mapping[str, object],
                observation["planned_source_identities"],
            )
        ),
        "planned_source_observation_identity": _identity(
            observation_raw,
            observation_identity,
            path=observation_path,
        ),
        "planned_source_set_digest": observation["planned_source_set_digest"],
        "purpose": PURPOSE,
        "recovery_dir": str(destination),
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "strict_inputs_identity": _identity(
            strict_raw,
            strict_identity,
            path=strict_path,
        ),
        "system_tools_identity": _identity(
            system_raw,
            system_identity,
            path=system_path,
        ),
    }


def _strict_inputs(repository: Path, arguments: argparse.Namespace) -> dict[str, Path]:
    return {
        "candidate_placements": repository / "data/preprocessed/candidate_placements.json",
        "canonical_rules": repository / "rules/canonical_rules.json",
        "cuts_mandatory_schedule": arguments.cuts_mandatory_schedule,
        "history_freeze_manifest": arguments.history_freeze_manifest,
        "legacy_control_a002": arguments.legacy_control_a002,
        "mandatory_instances": repository / "data/preprocessed/mandatory_exact_instances.json",
        "preflight_gate": repository / "scripts/preflight_gate.py",
        "project_lock": repository / "PROJECT_LOCK.md",
    }


def _system_tools(arguments: argparse.Namespace) -> dict[str, Path]:
    return {
        "attestor_python": arguments.attestor_python,
        "busctl": arguments.busctl,
        "git": arguments.git,
        "libsystemd": arguments.libsystemd,
        "native_budget_helper": arguments.native_budget_helper,
        "python3_13": arguments.python3_13,
        "sudo": arguments.sudo,
        "systemctl": arguments.systemctl,
        "systemd_run": arguments.systemd_run,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--history-freeze-manifest", required=True, type=Path)
    parser.add_argument("--cuts-mandatory-schedule", required=True, type=Path)
    parser.add_argument("--legacy-control-a002", required=True, type=Path)
    parser.add_argument(
        "--attestor-python",
        type=Path,
        default=Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13"),
    )
    parser.add_argument(
        "--python3-13",
        type=Path,
        default=Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13"),
    )
    parser.add_argument("--busctl", type=Path, default=Path("/usr/bin/busctl"))
    parser.add_argument("--git", type=Path, default=Path("/usr/bin/git"))
    parser.add_argument("--libsystemd", type=Path, default=Path("/usr/lib/libsystemd.so.0"))
    parser.add_argument("--native-budget-helper", type=Path, required=True)
    parser.add_argument(
        "--resource-calibration-full-preflight",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--resource-calibration-gate-b-qualification",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--resource-calibration-formal-organic-arm",
        type=Path,
        required=True,
    )
    parser.add_argument("--sudo", type=Path, default=Path("/usr/bin/sudo"))
    parser.add_argument("--systemctl", type=Path, default=Path("/usr/bin/systemctl"))
    parser.add_argument("--systemd-run", type=Path, default=Path("/usr/bin/systemd-run"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repository = _absolute(arguments.repository_root)
    try:
        result = publish_recovery_inputs(
            output_dir=arguments.output_dir,
            strict_input_paths=_strict_inputs(repository, arguments),
            system_tool_paths=_system_tools(arguments),
            resource_calibration_bundle_paths=(
                bootstrap._cli_resource_calibration_bundle_paths(  # noqa: SLF001
                    arguments
                )
            ),
        )
    except Exception as exc:
        sys.stderr.buffer.write(
            lifecycle.canonical_json_bytes(
                {
                    "detail": str(exc),
                    "schema_version": SCHEMA_VERSION,
                    "status": "FAIL_CLOSED",
                }
            )
        )
        return 2
    sys.stdout.buffer.write(lifecycle.canonical_json_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
