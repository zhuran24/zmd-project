#!/usr/bin/env python3
"""No-overwrite bootstrap for one CUTS_GATE1_V4 campaign authority.

This entry point creates authority only: a sealed byte package, the immutable
campaign root, and the Gate 1 child selection.  It never starts a unit, solver,
or arm.  A ``run-*`` directory additionally requires the explicit
``--formal-campaign`` flag; a ``dev-drill-*`` directory rejects that flag.

Python tools selected by the campaign point at ``.py`` members inside the
sealed package.  System executables point at their independently resolved real
bytes.  The existing exact-byte loaders can therefore set ``__file__`` to the
selected package member and execute precisely the bytes the package sealed.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

import campaign_authority_v4 as authority


SCHEMA = "noncert-cuts-gate1-v4-campaign-bootstrap-result-v1"
BOOTSTRAP_CAPTURE_SCHEMA = "noncert-cuts-gate1-v4-bootstrap-manager-capture-v1"

SCRIPT_TOOL_FILES: dict[str, str] = {
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
STRICT_INPUT_ROLES = frozenset(authority.REQUIRED_GATE1_INPUT_ROLES)
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
        "mandatory_instances",
    }
)
CANONICAL_JSON_INPUT_ROLES = JSON_INPUT_ROLES - {"canonical_rules"}
BOOTSTRAP_CAPTURE_INPUT_ROLE = "bootstrap_manager_epoch_capture"


class BootstrapError(RuntimeError):
    """A campaign bootstrap precondition or replay failed closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _exact_path_map(
    value: Mapping[str, Path | str],
    expected_roles: frozenset[str],
    label: str,
) -> dict[str, Path]:
    if type(value) is not dict or set(value) != set(expected_roles):
        raise BootstrapError(f"{label} must have the exact pre-registered role set")
    result: dict[str, Path] = {}
    for role, untyped_path in value.items():
        if type(role) is not str or not isinstance(untyped_path, (str, os.PathLike)):
            raise BootstrapError(f"{label}.{role!s} has an invalid path")
        path = _absolute(untyped_path)
        authority.snapshot_regular(path)
        result[role] = path
    return result


def _validate_mode(campaign_dir: Path, *, formal_campaign: bool) -> str:
    if type(formal_campaign) is not bool:
        raise BootstrapError("formal_campaign must be an exact bool")
    if campaign_dir.name.startswith("dev-drill-"):
        if formal_campaign:
            raise BootstrapError("dev-drill-* rejects formal campaign authorization")
        return "dev-drill"
    if campaign_dir.name.startswith("run-"):
        if not formal_campaign:
            raise BootstrapError("run-* requires explicit formal campaign authorization")
        return "formal"
    raise BootstrapError("campaign directory must be dev-drill-* or run-*")


def _assert_output_absent(campaign_dir: Path) -> None:
    parent = campaign_dir.parent
    # The authority primitive checks every parent component and rejects links.
    authority._reject_symlink_chain(parent)  # noqa: SLF001
    if not parent.is_dir():
        raise BootstrapError("campaign parent must already be a directory")
    if campaign_dir.exists() or campaign_dir.is_symlink():
        raise BootstrapError("campaign directory already exists; no-overwrite applies")


def _resolved_system_tools(
    paths: Mapping[str, Path | str],
) -> tuple[dict[str, Path], dict[str, dict[str, object]]]:
    if type(paths) is not dict or set(paths) != set(SYSTEM_TOOL_ROLES):
        raise BootstrapError("system tool paths must have the exact pre-registered role set")
    resolved: dict[str, Path] = {}
    identities: dict[str, dict[str, object]] = {}
    for role, untyped_path in sorted(paths.items()):
        if type(role) is not str or not isinstance(
            untyped_path,
            (str, os.PathLike),
        ):
            raise BootstrapError(f"system tool paths.{role!s} has an invalid path")
        requested_path = _absolute(untyped_path)
        _, full = authority.snapshot_tool(requested_path)
        real_path = Path(str(full["path"]))
        resolved[role] = real_path
        identities[role] = {key: full[key] for key in ("path", "sha256", "size_bytes")}
    return resolved, identities


def _observe_repository_head(repository_root: Path, git_path: Path) -> str:
    """Observe one exact HEAD with the already-resolved Git executable."""

    _, git_identity = authority.snapshot_tool(git_path)
    argv = [
        str(git_identity["path"]),
        "-C",
        str(repository_root),
        "rev-parse",
        "--verify",
        "HEAD",
    ]
    try:
        completed = subprocess.run(
            argv,
            check=False,
            env={
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
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
    if authority.GIT_SHA_RE.fullmatch(head) is None:
        raise BootstrapError("repository HEAD was not lowercase 40-hex")
    _, after = authority.snapshot_tool(git_path)
    if after != git_identity:
        raise BootstrapError("Git executable drifted during HEAD observation")
    return head


def _payload_identity(
    package_dir: Path,
    package_role: str,
) -> dict[str, object]:
    return authority.detached_identity(authority.snapshot_regular(package_dir / "payload" / package_role))


def _script_paths() -> dict[str, Path]:
    source_dir = Path(__file__).absolute().parent
    result = {role: source_dir / filename for role, filename in SCRIPT_TOOL_FILES.items()}
    for role, path in result.items():
        authority.snapshot_regular(path)
        if path.suffix != ".py":
            raise BootstrapError(f"selected Python tool lacks .py suffix: {role}")
    if not authority.REQUIRED_GATE1_TOOL_ROLES <= (set(result) | set(SYSTEM_TOOL_ROLES)):
        raise BootstrapError("bootstrap script allowlist misses a mandatory tool role")
    return result


def _capture_epoch(
    *,
    script_paths: Mapping[str, Path],
    system_paths: Mapping[str, Path],
) -> dict[str, object]:
    # Deliberately no injectable production argument.  Tests may monkeypatch
    # this module-level authority function; the CLI always uses this call.
    value = authority.capture_manager_epoch_with_transcript(
        attestor_path=script_paths["manager_attestor_v4"],
        busctl_path=system_paths["busctl"],
        python_path=system_paths["attestor_python"],
        sudo_path=system_paths["sudo"],
    )
    if type(value) is not dict or set(value) != {"manager_epoch", "transcript"}:
        raise BootstrapError("manager capture returned the wrong exact schema")
    authority.validate_manager_epoch(value["manager_epoch"])
    authority.validate_manager_epoch_capture_transcript(
        value["transcript"],
        expected_epoch=value["manager_epoch"],
    )
    return value


def bootstrap_campaign(
    campaign_dir: Path | str,
    *,
    repository_root: Path | str,
    formal_campaign: bool,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    created_at_utc: str | None = None,
) -> dict[str, object]:
    """Create package, campaign root, and Gate 1 selection without execution."""

    output = _absolute(campaign_dir)
    root_dir = _absolute(repository_root)
    mode = _validate_mode(output, formal_campaign=formal_campaign)
    _assert_output_absent(output)
    strict_paths = _exact_path_map(
        strict_input_paths,
        STRICT_INPUT_ROLES,
        "strict input paths",
    )
    scripts = _script_paths()
    system_paths, system_identities = _resolved_system_tools(system_tool_paths)
    timestamp = created_at_utc or _utc_now()
    authority._utc(timestamp, "bootstrap created_at_utc")  # noqa: SLF001

    repository_head = _observe_repository_head(root_dir, system_paths["git"])
    captured = _capture_epoch(
        script_paths=scripts,
        system_paths=system_paths,
    )
    if _observe_repository_head(root_dir, system_paths["git"]) != repository_head:
        raise BootstrapError("repository HEAD drifted before campaign creation")

    authority.mkdir_exclusive(output)
    bootstrap_dir = authority.mkdir_exclusive(output / "bootstrap-authority")
    capture_record = {
        "campaign_mode": mode,
        "formal_creation_explicitly_authorized": formal_campaign,
        "manager_epoch": captured["manager_epoch"],
        "purpose": "live manager epoch used to create this campaign root",
        "repository_head": repository_head,
        "run_nonce": output.name,
        "schema": BOOTSTRAP_CAPTURE_SCHEMA,
        "transcript": captured["transcript"],
    }
    capture_source_path = bootstrap_dir / "manager-epoch-capture.json"
    capture_source_identity = authority.write_exclusive(
        capture_source_path,
        authority.canonical_json(capture_record),
    )

    campaign_authority_dir = authority.mkdir_exclusive(output / "campaign-authority")
    package_dir = campaign_authority_dir / "package"
    source_specs: list[authority.SourceSpec] = []
    script_package_roles: dict[str, str] = {}
    for role, path in sorted(scripts.items()):
        package_role = "campaign_authority_v4.py" if role == "campaign_authority_v4" else f"tool.{role}.py"
        script_package_roles[role] = package_role
        source_specs.append(authority.SourceSpec(package_role, path))
    system_package_roles: dict[str, str] = {}
    for role, path in sorted(system_paths.items()):
        package_role = f"system.{role}.bin"
        system_package_roles[role] = package_role
        source_specs.append(authority.SourceSpec(package_role, path))
    input_package_roles: dict[str, str] = {}
    for role, path in sorted(strict_paths.items()):
        suffix = ".json" if role in JSON_INPUT_ROLES else ".txt"
        package_role = f"input.{role}{suffix}"
        input_package_roles[role] = package_role
        source_specs.append(
            authority.SourceSpec(
                package_role,
                path,
                parse_json=role in CANONICAL_JSON_INPUT_ROLES,
            )
        )
    capture_package_role = "input.bootstrap_manager_epoch_capture.json"
    source_specs.append(
        authority.SourceSpec(
            capture_package_role,
            capture_source_path,
            parse_json=True,
        )
    )

    package = authority.build_package(
        package_dir,
        source_specs,
        repository_head=repository_head,
        run_nonce=output.name,
        manager_epoch=captured["manager_epoch"],
    )
    tools = {role: _payload_identity(package_dir, package_role) for role, package_role in script_package_roles.items()}
    attestor_epoch_identity = {
        key: captured["manager_epoch"]["attestation_toolchain"]["attestor"][key]
        for key in ("path", "sha256", "size_bytes")
    }
    authority.validate_detached_identity(
        attestor_epoch_identity,
        "bootstrap manager attestor epoch identity",
    )
    if (
        tools["manager_attestor_v4"]["sha256"] != attestor_epoch_identity["sha256"]
        or tools["manager_attestor_v4"]["size_bytes"] != attestor_epoch_identity["size_bytes"]
    ):
        raise BootstrapError("sealed manager attestor copy does not match the live epoch tool")
    # The privileged helper keeps the exact path identity recorded by the live
    # epoch.  Its package copy remains sealed and cross-checked above.
    tools["manager_attestor_v4"] = attestor_epoch_identity
    tools.update(system_identities)
    inputs = {role: _payload_identity(package_dir, package_role) for role, package_role in input_package_roles.items()}
    project_lock_source = authority.detached_identity(authority.snapshot_regular(strict_paths["project_lock"]))
    project_lock_copy = inputs["project_lock"]
    if (
        project_lock_copy["sha256"] != project_lock_source["sha256"]
        or project_lock_copy["size_bytes"] != project_lock_source["size_bytes"]
    ):
        raise BootstrapError("sealed PROJECT_LOCK copy does not match its repository source")
    # This selected input retains the external source path so the unit
    # working-directory and selected imports resolve the real, byte-locked
    # repository rather than the immutable package payload.
    inputs["project_lock"] = project_lock_source
    inputs[BOOTSTRAP_CAPTURE_INPUT_ROLE] = _payload_identity(
        package_dir,
        capture_package_role,
    )

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

    if _observe_repository_head(root_dir, system_paths["git"]) != repository_head:
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
    if any(
        path.exists() or path.is_symlink()
        for path in authority.reserved_child_paths(root)
        if path != Path(str(root["stage_topology"]["gate1_v4"]["selection_path"]))
    ):
        raise BootstrapError("a reserved post-selection child was created")

    return {
        "bootstrap_capture_source_identity": capture_source_identity,
        "campaign_dir": str(output),
        "campaign_mode": mode,
        "campaign_root_identity": root_identity,
        "formal_arm_launch_authorized": False,
        "gate1_selection_identity": selection_identity,
        "organic_ab16_authorized": False,
        "package_id": package["package_id"],
        "repository_head": repository_head,
        "run_nonce": output.name,
        "schema": SCHEMA,
        "status": "AUTHORITY_READY_NO_UNIT_LAUNCHED",
    }


def _production_strict_inputs(
    repository_root: Path,
    *,
    history_freeze_manifest: Path,
    cuts_mandatory_schedule: Path,
) -> dict[str, Path]:
    return {
        "candidate_placements": (repository_root / "data" / "preprocessed" / "candidate_placements.json"),
        "canonical_rules": repository_root / "rules" / "canonical_rules.json",
        "cuts_mandatory_schedule": cuts_mandatory_schedule,
        "history_freeze_manifest": history_freeze_manifest,
        "mandatory_instances": (repository_root / "data" / "preprocessed" / "mandatory_exact_instances.json"),
        "project_lock": repository_root / "PROJECT_LOCK.md",
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--history-freeze-manifest", type=Path, required=True)
    parser.add_argument("--cuts-mandatory-schedule", type=Path, required=True)
    parser.add_argument("--formal-campaign", action="store_true")
    parser.add_argument("--created-at-utc")
    parser.add_argument(
        "--python3-13",
        type=Path,
        default=Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13"),
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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(argv)
    repository_root = _absolute(arguments.repository_root)
    try:
        result = bootstrap_campaign(
            arguments.campaign_dir,
            repository_root=repository_root,
            formal_campaign=arguments.formal_campaign,
            strict_input_paths=_production_strict_inputs(
                repository_root,
                history_freeze_manifest=arguments.history_freeze_manifest,
                cuts_mandatory_schedule=arguments.cuts_mandatory_schedule,
            ),
            system_tool_paths={
                "attestor_python": arguments.attestor_python,
                "busctl": arguments.busctl,
                "git": arguments.git,
                "python3_13": arguments.python3_13,
                "sudo": arguments.sudo,
                "systemctl": arguments.systemctl,
                "systemd_run": arguments.systemd_run,
            },
            created_at_utc=arguments.created_at_utc,
        )
    except (authority.AuthorityError, BootstrapError) as exc:
        sys.stderr.buffer.write(
            authority.canonical_json(
                {
                    "error": str(exc),
                    "schema": SCHEMA,
                    "status": "FAIL_CLOSED",
                }
            )
        )
        return 2
    sys.stdout.buffer.write(authority.canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
