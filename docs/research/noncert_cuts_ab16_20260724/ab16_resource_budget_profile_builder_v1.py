#!/usr/bin/env python3
"""Build the launch-blocked AB16 aggregate resource-budget profile.

This is research/developer infrastructure.  It does not publish Gate A,
Gate B, a formal selection, an attempt-consumption marker, or any campaign
authority.  The resulting profile retains the project's all-false authority
boundary and is launch-blocked unless the caller supplies the explicit
launch-ready acknowledgement used by a later calibrated candidate.

The builder has three deliberately separate inputs:

* the exact fixed bootstrap/package role registries are read mechanically
  from ``ab16_campaign_bootstrap_v2.py`` without importing or executing it;
* the per-arm artifact label/class registry is read mechanically from
  ``organic_arm_runner_v1.py``; and
* repository-snapshot member paths and sizes are enumerated from the
  candidate worktree for a blocked profile, or from a clean ``HEAD`` for an
  explicitly acknowledged launch-ready profile.

Per-file maxima are guards, not an aggregate-disk formula.  Each arm receives
one explicit aggregate allocation, atomically debited from the formal root by
the runtime broker.  The aggregate is instead derived from the maximum number
of publications admitted for each label, the mutually exclusive terminal
branches, and finite append-channel segment counts.  Exhausting any count is
an incomplete arm, never permission to omit retained evidence.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from typing import NoReturn, cast


SCHEMA_VERSION = "noncert-cuts-ab16-resource-budget-profile-v1"
PROFILE_RELATIVE_PATH = (
    "docs/research/noncert_cuts_ab16_20260724/"
    "ab16_resource_budget_profile_phase2_blocked_v1.json"
)
BOOTSTRAP_SOURCE_RELATIVE_PATH = (
    "docs/research/noncert_cuts_ab16_20260724/"
    "ab16_campaign_bootstrap_v2.py"
)
RUNNER_SOURCE_RELATIVE_PATH = (
    "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py"
)
BUILDER_SOURCE_RELATIVE_PATH = (
    "docs/research/noncert_cuts_ab16_20260724/"
    "ab16_resource_budget_profile_builder_v1.py"
)
V4_SOURCE_DIRECTORY = (
    "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
)
AB16_SOURCE_DIRECTORY = "docs/research/noncert_cuts_ab16_20260724"
CANDIDATE_PLACEMENTS_RELATIVE_PATH = (
    "data/preprocessed/candidate_placements.json"
)

PROFILE_ID_PHASE2_BLOCKED = (
    "ab16-phase2-launch-blocked-budget-profile-v1"
)
PHASE2_BLOCKED_EXECUTION_SURFACE_SHA256 = hashlib.sha256(
    b"AB16_PHASE2_LAUNCH_BLOCKED_NO_EXECUTION_SURFACE_V1\n"
).hexdigest()
LAUNCH_READY_ACKNOWLEDGEMENT = (
    "I_ACCEPT_ONLY_AN_INDEPENDENTLY_CALIBRATED_EXACT_EXECUTION_SURFACE"
)

MIB = 1024**2
PROFILE_SELF_MAXIMUM_BYTES = 32 * MIB
CANONICAL_RECORD_MAXIMUM_BYTES = 4 * MIB
LARGE_CANONICAL_RECORD_MAXIMUM_BYTES = 16 * MIB
PACKAGE_MANIFEST_MAXIMUM_BYTES = 64 * MIB
EXTERNAL_STRICT_INPUT_MAXIMUM_BYTES = 64 * MIB
PACKAGE_INDEPENDENT_REPLAY_MAXIMUM_BYTES = 4 * MIB
BOOTSTRAP_FAILURE_CLOSEOUT_MAXIMUM_BYTES = 4 * MIB

FALSE_AUTHORITY = {
    "changes_certified_exact": False,
    "changes_cut_state": False,
    "changes_lower_bound": False,
    "changes_production": False,
    "changes_upper_bound": False,
    "research_only": True,
}
ARTIFACT_CLASSES = frozenset(
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
ARM_SLOTS = tuple(
    sorted(
        f"{configuration}-{order}-{arm}"
        for configuration in (
            "region-capacity",
            "shape-packing-hall",
            "power-hitting-set",
            "bundle",
        )
        for order in ("ab", "ba")
        for arm in ("control", "treatment")
    )
)
MAXIMUM_ATTACH_HOOKS = 30
MAXIMUM_GENERATED_CUTS = 128
ARM_LEDGER_SEGMENT_MAXIMUM_BYTES = 256 * 1024
FORMAL_BASELINE_MAXIMUM_SEGMENTS = 128
FORMAL_BUDGET_JOURNAL_MAXIMUM_BYTES = 4096
FORMAL_BUDGET_JOURNAL_MAXIMUM_SEGMENTS = 16_384
FORMAL_BUDGET_JOURNAL_PER_ARM_CONTROL_ALLOWANCE = 64
FORMAL_BUDGET_JOURNAL_ROOT_CONTROL_ALLOWANCE = 2048
INDEPENDENT_FAILURE_CLOSEOUT_LABEL = "organic arm failure record"
OUTSIDE_FINAL_RELEASE_PARENT_PATH = "formal-ab16/final-release"

# These immutable observations are planning input only.  The profile does not
# depend on the historical root being mounted, and none of these bytes grants
# calibration, Gate-B, campaign, result, or proof authority.
HISTORICAL_SIZE_OBSERVATIONS: tuple[dict[str, object], ...] = (
    {
        "label": "assignment",
        "sha256": (
            "f394d2753bcfcde6e293d4fe3f2189d4261bea688b231a09c"
            "3d84bf66fe2d1a7"
        ),
        "size_bytes": 760_886,
    },
    {
        "label": "incumbent",
        "sha256": (
            "6b7bc7b9faca38c872f54e35e6bbc357e5514f5525afe8eb"
            "a751a14ea60cfe4f"
        ),
        "size_bytes": 11_886,
    },
    {
        "label": "post-model",
        "sha256": (
            "98cdc2e1eed6ccbbbc2c0b4a8b388904cc97b7f36fb765ae"
            "c10341011d875982"
        ),
        "size_bytes": 1_358_143,
    },
    {
        "label": "pre-model",
        "sha256": (
            "0f150a204639074634a408140e2cd63929bf3152b727491d3"
            "5c6741c1187995c"
        ),
        "size_bytes": 1_357_978,
    },
    {
        "label": "solution-vector",
        "sha256": (
            "f2d1437aecb89b418f61206df86bbbdae8103572be8f06528"
            "7ab37c95a4a7171"
        ),
        "size_bytes": 20_252,
    },
)
HISTORICAL_SIZE_PLANNING_INPUT: dict[str, object] = {
    "authority": "planning-input-only-not-calibration-authority",
    "sample_id": "gate1-v4-positive-control-common-20260723",
    "observations": list(HISTORICAL_SIZE_OBSERVATIONS),
    "runtime_dependency": False,
}
ARM_BRANCH_CONTRACT: dict[str, dict[str, list[str]]] = {
    "common": {"mutually_exclusive_with": []},
    "failure": {"mutually_exclusive_with": ["success"]},
    "success": {"mutually_exclusive_with": ["failure"]},
}
ARM_AGGREGATE_ALLOCATION = {
    "closeout": 64 * MIB,
    "ledger": 128 * MIB,
    "metadata": 32 * MIB,
    "model": 480 * MIB,
    "publication": 224 * MIB,
}
ARM_APPEND_CHANNELS = (
    (
        "compile-journal",
        "compile attach journal segment",
        "ledger/compile-attach-journal",
        3 + 3 * MAXIMUM_ATTACH_HOOKS + MAXIMUM_GENERATED_CUTS,
        (
            "3 genesis/seal records + 3 records per attach hook + "
            "at most one compiled-cut record per generated cut"
        ),
    ),
    (
        "cut-ledger",
        "cut ledger segment",
        "ledger/cut-ledger",
        2 + 2 * MAXIMUM_GENERATED_CUTS,
        (
            "2 genesis/seal records + at most one generated and one "
            "terminal disposition record per generated cut"
        ),
    ),
    (
        "runtime-cuts",
        "runtime cut segment",
        "checkpoint/runtime-cuts",
        0,
        (
            "certified_exact AB16 routes cut events through the cut ledger; "
            "runtime-cut publication is forbidden"
        ),
    ),
)
ARM_DIRECTORY_SUFFIX_MODES = (
    ("checkpoint", "0700"),
    ("checkpoint/runtime-cuts", "0700"),
    ("ledger", "0700"),
    ("ledger/compile-attach-journal", "0700"),
    ("ledger/cut-ledger", "0700"),
    ("replays", "0700"),
    ("runtime", "0700"),
    ("tmp", "0500"),
)

FORMAL_FIXED_RESERVATIONS = (
    {
        "artifact_class": "closeout",
        "maximum_bytes": 4 * MIB,
        "parent_path": OUTSIDE_FINAL_RELEASE_PARENT_PATH,
        "parent_scope": "campaign-root",
        "purpose": "failure-terminal-release",
        "target_name": "failure-terminal-release.json",
    },
    {
        "artifact_class": "closeout",
        "maximum_bytes": 64 * 1024,
        "parent_path": "formal-closure",
        "parent_scope": "formal-root",
        "purpose": "formal-budget-terminal",
        "target_name": "budget-terminal.json",
    },
    {
        "artifact_class": "metadata",
        "maximum_bytes": 4096,
        "parent_path": "locks",
        "parent_scope": "formal-root",
        "purpose": "formal-closure-consumption",
        "target_name": "formal-closure-consumption.json",
    },
    {
        "artifact_class": "metadata",
        "maximum_bytes": 64 * 1024,
        "parent_path": "formal-closure",
        "parent_scope": "formal-root",
        "purpose": "formal-manifest",
        "target_name": "formal-manifest.json",
    },
    {
        "artifact_class": "closeout",
        "maximum_bytes": 4 * MIB,
        "parent_path": OUTSIDE_FINAL_RELEASE_PARENT_PATH,
        "parent_scope": "campaign-root",
        "purpose": "formal-root-replay-alternate-receipt",
        "target_name": "formal-root-replay-alternate.json",
    },
    {
        "artifact_class": "closeout",
        "maximum_bytes": 4 * MIB,
        "parent_path": OUTSIDE_FINAL_RELEASE_PARENT_PATH,
        "parent_scope": "campaign-root",
        "purpose": "formal-root-replay-primary-receipt",
        "target_name": "formal-root-replay-primary.json",
    },
    {
        "artifact_class": "closeout",
        "maximum_bytes": 4 * MIB,
        "parent_path": "closeout",
        "parent_scope": "formal-root",
        "purpose": "recovery-closeout",
        "target_name": "formal-consumed-incomplete.json",
    },
    {
        "artifact_class": "closeout",
        "maximum_bytes": 4 * MIB,
        "parent_path": "formal-closure",
        "parent_scope": "formal-root",
        "purpose": "recovery-disarm-terminal",
        "target_name": "recovery-disarm-terminal.json",
    },
    {
        "artifact_class": "metadata",
        "maximum_bytes": 4096,
        "parent_path": "locks",
        "parent_scope": "formal-root",
        "purpose": "recovery-takeover-consumption",
        "target_name": "recovery-takeover-consumption.json",
    },
    {
        "artifact_class": "closeout",
        "maximum_bytes": 4 * MIB,
        "parent_path": OUTSIDE_FINAL_RELEASE_PARENT_PATH,
        "parent_scope": "campaign-root",
        "purpose": "success-dual-lock-release",
        "target_name": "dual-lock-release.json",
    },
)
FORMAL_FIXED_HEADROOM = {
    # TMPDIR is an aggregate pool; it is not inferred from file guards.
    "scratch": 64 * MIB,
}

SYSTEM_ROLE_MAXIMUM_BYTES = {
    "attestor_python": 64 * MIB,
    "busctl": 32 * MIB,
    "git": 32 * MIB,
    "libsystemd": 32 * MIB,
    "native_budget_helper": 4 * MIB,
    "python3_13": 64 * MIB,
    "sudo": 32 * MIB,
    "systemctl": 32 * MIB,
    "systemd_run": 32 * MIB,
}
TRACKED_STRICT_INPUT_PATHS = {
    "candidate_placements": CANDIDATE_PLACEMENTS_RELATIVE_PATH,
    "canonical_rules": "rules/canonical_rules.json",
    "mandatory_instances": (
        "data/preprocessed/mandatory_exact_instances.json"
    ),
    "preflight_gate": "scripts/preflight_gate.py",
    "project_lock": "PROJECT_LOCK.md",
}

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class ProfileBuildError(RuntimeError):
    """One deterministic profile-build contract failed closed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise ProfileBuildError(code, detail)


def canonical_json(value: object) -> bytes:
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


def digest_without(record: Mapping[str, object], field: str) -> str:
    projected = dict(record)
    projected.pop(field, None)
    return hashlib.sha256(canonical_json(projected)).hexdigest()


def _literal_assignment(path: Path, name: str) -> object:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _fail("SOURCE_READ_FAILED", f"{path}: {exc}")
    try:
        tree = ast.parse(raw, filename=str(path))
    except (SyntaxError, ValueError) as exc:
        _fail("SOURCE_PARSE_FAILED", f"{path}: {exc}")
    matches: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in targets
            ):
                if node.value is None:
                    _fail(
                        "SOURCE_REGISTRY_NOT_LITERAL",
                        f"{path}: {name} has no value",
                    )
                matches.append(node.value)
    if len(matches) != 1:
        _fail(
            "SOURCE_REGISTRY_MISSING",
            f"{path}: expected one literal assignment for {name}",
        )
    value_node = matches[0]
    if (
        isinstance(value_node, ast.Call)
        and isinstance(value_node.func, ast.Name)
        and value_node.func.id == "frozenset"
        and len(value_node.args) == 1
        and not value_node.keywords
    ):
        value_node = value_node.args[0]
    try:
        return ast.literal_eval(value_node)
    except (ValueError, TypeError, SyntaxError) as exc:
        _fail(
            "SOURCE_REGISTRY_NOT_LITERAL",
            f"{path}: {name}: {exc}",
        )


def fixed_source_registries(
    repository_root: Path | str,
) -> dict[str, object]:
    root = Path(os.path.abspath(os.fspath(repository_root)))
    bootstrap = root / BOOTSTRAP_SOURCE_RELATIVE_PATH
    runner = root / RUNNER_SOURCE_RELATIVE_PATH
    v4_scripts = _literal_assignment(
        bootstrap,
        "V4_SCRIPT_TOOL_FILES",
    )
    ab16_scripts = _literal_assignment(
        bootstrap,
        "AB16_SCRIPT_TOOL_FILES",
    )
    strict_roles = _literal_assignment(bootstrap, "STRICT_INPUT_ROLES")
    system_roles = _literal_assignment(bootstrap, "SYSTEM_TOOL_ROLES")
    json_input_roles = _literal_assignment(bootstrap, "JSON_INPUT_ROLES")
    gate_inputs = _literal_assignment(bootstrap, "GATE_INPUT_ROLES")
    calibration_inputs = _literal_assignment(
        bootstrap,
        "RESOURCE_CALIBRATION_INPUT_ROLES",
    )
    arm_labels = _literal_assignment(
        runner,
        "BUDGET_ARTIFACT_CLASS_BY_LABEL",
    )
    if (
        type(v4_scripts) is not dict
        or type(ab16_scripts) is not dict
        or type(strict_roles) not in {set, frozenset}
        or type(system_roles) not in {set, frozenset}
        or type(json_input_roles) not in {set, frozenset}
        or type(gate_inputs) is not dict
        or type(calibration_inputs) is not dict
        or type(arm_labels) is not dict
    ):
        _fail(
            "SOURCE_REGISTRY_SHAPE_DRIFT",
            "bootstrap or runner registry has an unexpected literal type",
        )
    v4_scripts = cast(dict[str, str], v4_scripts)
    ab16_scripts = cast(dict[str, str], ab16_scripts)
    strict_roles = cast(set[str] | frozenset[str], strict_roles)
    system_roles = cast(set[str] | frozenset[str], system_roles)
    json_input_roles = cast(
        set[str] | frozenset[str],
        json_input_roles,
    )
    gate_inputs = cast(dict[str, str], gate_inputs)
    calibration_inputs = cast(dict[str, str], calibration_inputs)
    arm_labels = cast(dict[str, str], arm_labels)
    scripts = {**v4_scripts, **ab16_scripts}
    if len(scripts) != len(v4_scripts) + len(ab16_scripts):
        _fail(
            "SOURCE_REGISTRY_COLLISION",
            "V4 and AB16 script roles collide",
        )
    if (
        set(system_roles) != set(SYSTEM_ROLE_MAXIMUM_BYTES)
        or set(strict_roles) != {
            "candidate_placements",
            "canonical_rules",
            "cuts_mandatory_schedule",
            "history_freeze_manifest",
            "legacy_control_a002",
            "mandatory_instances",
            "preflight_gate",
            "project_lock",
        }
        or set(calibration_inputs)
        != {
            "FULL_PREFLIGHT",
            "GATE_B_QUALIFICATION",
            "FORMAL_ORGANIC_ARM",
        }
        or set(arm_labels) != {
            "AB16 immediate stop",
            "AB16 arm budget terminal",
            "AB16 organic attempt artifact manifest",
            "AB16 organic attempt root replay",
            "arm allocation unselected terminal",
            "arm consumed incomplete",
            "arm credibility gate",
            "arm launch environment",
            "attach model evidence",
            "attach solution-vector evidence",
            "compile attach journal segment",
            "cut ledger segment",
            "cut-free incumbent replay receipt",
            "independent arithmetic replay receipt",
            "independent resource terminal replay",
            "module-origin receipt",
            "organic arm consumption",
            "organic arm failure record",
            "organic arm result",
            "organic arm selection",
            "organic pre-run authority",
            "organic pre-run candidate",
            "preselection manager epoch",
            "preselection manager transcript",
            "raw incumbent export",
            "raw solution-vector export",
            "runtime cut segment",
            "terminal classification",
        }
        or arm_labels.get("organic arm consumption") != "closeout"
        or any(
            type(label) is not str
            or type(artifact_class) is not str
            or artifact_class not in ARTIFACT_CLASSES
            for label, artifact_class in arm_labels.items()
        )
    ):
        _fail(
            "SOURCE_REGISTRY_COHORT_DRIFT",
            "fixed bootstrap/runner cohort is incomplete or mixed",
        )
    return {
        "ab16_scripts": dict(ab16_scripts),
        "arm_labels": dict(arm_labels),
        "calibration_inputs": dict(calibration_inputs),
        "gate_inputs": dict(gate_inputs),
        "json_input_roles": frozenset(json_input_roles),
        "scripts": scripts,
        "strict_roles": frozenset(strict_roles),
        "system_roles": frozenset(system_roles),
        "v4_scripts": dict(v4_scripts),
    }


def _git(
    repository_root: Path,
    arguments: Sequence[str],
) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        _fail(
            "GIT_ENUMERATION_FAILED",
            completed.stderr.decode("utf-8", "replace")[:4096],
        )
    return completed.stdout


def _portable_relative_path(value: str, *, label: str) -> str:
    if not value or "\\" in value:
        _fail("PATH_INVALID", f"{label}: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        _fail("PATH_INVALID", f"{label}: {value!r}")
    return value


def _regular_size(path: Path, *, label: str) -> int:
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        _fail("MEMBER_STAT_FAILED", f"{label}: {path}: {exc}")
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink < 1
        or metadata.st_size < 0
    ):
        _fail("MEMBER_NOT_REGULAR", f"{label}: {path}")
    return max(1, metadata.st_size)


def discover_repository_members(
    repository_root: Path | str,
    *,
    launch_ready: bool,
    profile_relative_path: str = PROFILE_RELATIVE_PATH,
) -> dict[str, int]:
    root = Path(os.path.abspath(os.fspath(repository_root)))
    if launch_ready:
        status = _git(root, ["status", "--porcelain=v1", "-z"])
        if status:
            _fail(
                "LAUNCH_READY_TREE_NOT_CLEAN",
                "launch-ready enumeration requires a clean committed HEAD",
            )
        raw = _git(
            root,
            ["ls-tree", "-r", "-z", "--long", "--full-tree", "HEAD"],
        )
        members: dict[str, int] = {}
        for entry in raw.split(b"\0"):
            if not entry:
                continue
            try:
                header, raw_path = entry.split(b"\t", 1)
                mode, object_type, _oid, raw_size = header.split(b" ", 3)
                relative = raw_path.decode("utf-8")
                size = int(raw_size)
            except (ValueError, UnicodeDecodeError) as exc:
                _fail("GIT_TREE_RECORD_INVALID", repr(exc))
            if object_type != b"blob" or mode not in {
                b"100644",
                b"100755",
            }:
                _fail(
                    "GIT_TREE_MEMBER_UNSUPPORTED",
                    f"{relative}: mode={mode!r} type={object_type!r}",
                )
            members[_portable_relative_path(relative, label="HEAD member")] = max(
                1,
                size,
            )
        if profile_relative_path not in members:
            _fail(
                "LAUNCH_READY_PROFILE_NOT_COMMITTED",
                profile_relative_path,
            )
        return dict(sorted(members.items()))

    raw = _git(
        root,
        [
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
    )
    members = {}
    for raw_path in raw.split(b"\0"):
        if not raw_path:
            continue
        try:
            relative = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            _fail("WORKTREE_PATH_NOT_UTF8", str(exc))
        relative = _portable_relative_path(
            relative,
            label="candidate worktree member",
        )
        members[relative] = _regular_size(
            root / relative,
            label="candidate worktree member",
        )
    # The output is self-referential only in membership, never in size/hash.
    # Its maximum is fixed independently of its eventual bytes.
    members[profile_relative_path] = PROFILE_SELF_MAXIMUM_BYTES
    if BUILDER_SOURCE_RELATIVE_PATH not in members:
        _fail(
            "BUILDER_SOURCE_NOT_ENUMERATED",
            BUILDER_SOURCE_RELATIVE_PATH,
        )
    return dict(sorted(members.items()))


def _source_size(
    repository_root: Path,
    members: Mapping[str, int],
    relative: str,
    *,
    fallback: int,
) -> int:
    if relative in members:
        if relative == PROFILE_RELATIVE_PATH:
            return PROFILE_SELF_MAXIMUM_BYTES
        return max(1, int(members[relative]))
    path = repository_root / relative
    if path.exists() and not path.is_symlink():
        return _regular_size(path, label="fixed source")
    return fallback


def _zip_maximum_bytes(members: Mapping[str, int]) -> int:
    total = sum(members.values())
    # zlib's DEFLATE bound is below 1%; 512 bytes/member covers both ZIP
    # headers and path metadata, while 1 MiB covers archive-global overhead.
    return max(
        1,
        total + (total + 99) // 100 + len(members) * 512 + MIB,
    )


def _artifact(
    *,
    artifact_class: str,
    label: str,
    maximum_bytes: int,
    path: str,
    required_on_success: bool = True,
) -> dict[str, object]:
    if artifact_class not in ARTIFACT_CLASSES:
        _fail("ARTIFACT_CLASS_INVALID", artifact_class)
    _portable_relative_path(label, label="artifact label")
    _portable_relative_path(path, label="artifact path")
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or maximum_bytes <= 0
    ):
        _fail("ARTIFACT_MAXIMUM_INVALID", label)
    return {
        "artifact_class": artifact_class,
        "label": label,
        "maximum_bytes": maximum_bytes,
        "path": path,
        "required_on_success": required_on_success,
    }


def _directory_closure(paths: Sequence[str]) -> set[str]:
    result = {"."}
    for raw in paths:
        path = PurePosixPath(raw)
        parent = path if raw.endswith("/") else path.parent
        while parent.as_posix() != ".":
            result.add(parent.as_posix())
            parent = parent.parent
    return result


def _fixed_directories(
    paths: Sequence[str],
    *,
    read_only_roots: Sequence[str] = (),
    explicit_modes: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    directories = _directory_closure(paths)
    modes = {"." : "0700"}
    for directory in directories - {"."}:
        modes[directory] = "0700"
    for root in read_only_roots:
        for directory in directories:
            if directory == root or directory.startswith(f"{root}/"):
                modes[directory] = "0500"
    if explicit_modes is not None:
        for directory, mode in explicit_modes.items():
            if directory not in directories or mode not in {"0500", "0700"}:
                _fail(
                    "DIRECTORY_MODE_INVALID",
                    f"{directory}: {mode}",
                )
            modes[directory] = mode
    return [
        {"mode_octal": modes[path], "path": path}
        for path in sorted(directories, key=lambda item: item.encode("utf-8"))
    ]


def _bootstrap_artifacts(
    repository_root: Path,
    members: Mapping[str, int],
    registries: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    scripts = registries["scripts"]
    strict_roles = registries["strict_roles"]
    system_roles = registries["system_roles"]
    json_input_roles = registries["json_input_roles"]
    gate_inputs = registries["gate_inputs"]
    calibration_inputs = registries["calibration_inputs"]
    assert isinstance(scripts, dict)
    assert isinstance(strict_roles, frozenset)
    assert isinstance(system_roles, frozenset)
    assert isinstance(json_input_roles, frozenset)
    assert isinstance(gate_inputs, dict)
    assert isinstance(calibration_inputs, dict)

    artifacts_by_path: dict[str, dict[str, object]] = {}

    def add(
        path: str,
        maximum: int,
        *,
        artifact_class: str = "normal",
        required: bool = True,
    ) -> None:
        if path in artifacts_by_path:
            _fail("BOOTSTRAP_PATH_COLLISION", path)
        artifacts_by_path[path] = _artifact(
            artifact_class=artifact_class,
            label=f"bootstrap/{path}",
            maximum_bytes=maximum,
            path=path,
            required_on_success=required,
        )

    add(
        "bootstrap-authority/bootstrap-budget-contract.json",
        CANONICAL_RECORD_MAXIMUM_BYTES,
        artifact_class="metadata",
    )
    add(
        "bootstrap-authority/manager-epoch-capture.json",
        CANONICAL_RECORD_MAXIMUM_BYTES,
        artifact_class="metadata",
    )

    script_source_sizes: dict[str, int] = {}
    v4_scripts = registries["v4_scripts"]
    assert isinstance(v4_scripts, dict)
    v4_roles = set(v4_scripts)
    for role, filename in sorted(scripts.items()):
        source_relative = (
            f"{V4_SOURCE_DIRECTORY}/{filename}"
            if role in v4_roles
            else f"{AB16_SOURCE_DIRECTORY}/{filename}"
        )
        size = _source_size(
            repository_root,
            members,
            source_relative,
            fallback=EXTERNAL_STRICT_INPUT_MAXIMUM_BYTES,
        )
        script_source_sizes[role] = size
        add(
            f"bootstrap-authority/package-source-staging/script.{role}.py",
            size,
        )

    strict_source_sizes: dict[str, int] = {}
    for role in sorted(strict_roles):
        relative = TRACKED_STRICT_INPUT_PATHS.get(role)
        size = (
            _source_size(
                repository_root,
                members,
                relative,
                fallback=EXTERNAL_STRICT_INPUT_MAXIMUM_BYTES,
            )
            if relative is not None
            else EXTERNAL_STRICT_INPUT_MAXIMUM_BYTES
        )
        strict_source_sizes[role] = size
        add(
            f"bootstrap-authority/package-source-staging/input.{role}",
            size,
        )

    snapshot_members = dict(members)
    candidate_size = _source_size(
        repository_root,
        members,
        CANDIDATE_PLACEMENTS_RELATIVE_PATH,
        fallback=EXTERNAL_STRICT_INPUT_MAXIMUM_BYTES,
    )
    snapshot_members[CANDIDATE_PLACEMENTS_RELATIVE_PATH] = candidate_size
    archive_maximum = _zip_maximum_bytes(snapshot_members)
    add(
        "bootstrap-authority/repository-snapshot-sources/"
        "repository-snapshot.zip",
        archive_maximum,
    )
    add(
        "bootstrap-authority/repository-snapshot-sources/"
        "repository-snapshot.json",
        PACKAGE_MANIFEST_MAXIMUM_BYTES,
        artifact_class="metadata",
    )
    add(
        "bootstrap-authority/repository-snapshot-sources/"
        "external-platform-assumptions.json",
        CANONICAL_RECORD_MAXIMUM_BYTES,
        artifact_class="metadata",
    )

    package_roles: dict[str, int] = {}
    for role, size in script_source_sizes.items():
        package_role = (
            "campaign_authority_v4.py"
            if role == "campaign_authority_v4"
            else f"tool.{role}.py"
        )
        package_roles[package_role] = size
    for role in sorted(system_roles):
        package_roles[f"system.{role}.bin"] = (
            SYSTEM_ROLE_MAXIMUM_BYTES[role]
        )
    for role, size in strict_source_sizes.items():
        suffix = ".json" if role in json_input_roles else ".txt"
        package_roles[f"input.{role}{suffix}"] = size
    for stage, role in sorted(calibration_inputs.items()):
        if type(stage) is not str or type(role) is not str:
            _fail("CALIBRATION_ROLE_INVALID", repr((stage, role)))
        package_roles[f"input.{role}.json"] = (
            LARGE_CANONICAL_RECORD_MAXIMUM_BYTES
        )
    for role, package_role in sorted(gate_inputs.items()):
        if type(role) is not str or type(package_role) is not str:
            _fail("GATE_INPUT_ROLE_INVALID", repr((role, package_role)))
        package_roles[package_role] = (
            LARGE_CANONICAL_RECORD_MAXIMUM_BYTES
        )
    package_roles.update(
        {
            "input.ab16_bootstrap_manager_epoch_capture.json": (
                CANONICAL_RECORD_MAXIMUM_BYTES
            ),
            "input.ab16_path_preregistration.json": (
                LARGE_CANONICAL_RECORD_MAXIMUM_BYTES
            ),
            "input.ab16_resource_budget_profile.json": (
                PROFILE_SELF_MAXIMUM_BYTES
            ),
            "input.ab16_repository_snapshot.zip": archive_maximum,
            "input.ab16_repository_snapshot.json": (
                PACKAGE_MANIFEST_MAXIMUM_BYTES
            ),
            "input.ab16_external_platform_assumptions.json": (
                CANONICAL_RECORD_MAXIMUM_BYTES
            ),
        }
    )
    for role, maximum in sorted(package_roles.items()):
        add(f"campaign-authority/package/payload/{role}", maximum)
    add(
        "campaign-authority/package/package-manifest.json",
        PACKAGE_MANIFEST_MAXIMUM_BYTES,
        artifact_class="metadata",
    )
    add(
        "campaign-authority/package/SHA256SUMS",
        max(64 * 1024, len(package_roles) * 256),
        artifact_class="metadata",
    )
    add(
        "bootstrap-authority/package-independent-replay.json",
        PACKAGE_INDEPENDENT_REPLAY_MAXIMUM_BYTES,
        artifact_class="metadata",
    )

    for relative, maximum in sorted(snapshot_members.items()):
        add(
            "campaign-authority/source-snapshot-a001/repository/"
            f"{relative}",
            maximum,
        )
    add(
        "campaign-authority/source-snapshot-a001/"
        "materialization-receipt.json",
        LARGE_CANONICAL_RECORD_MAXIMUM_BYTES,
        artifact_class="metadata",
    )
    add(
        "campaign-root.json",
        LARGE_CANONICAL_RECORD_MAXIMUM_BYTES,
        artifact_class="metadata",
    )
    add(
        "gate1-v4/selection-a001.json",
        LARGE_CANONICAL_RECORD_MAXIMUM_BYTES,
        artifact_class="metadata",
    )
    add(
        "bootstrap-authority/bootstrap-budget-terminal.json",
        LARGE_CANONICAL_RECORD_MAXIMUM_BYTES,
        artifact_class="closeout",
    )

    artifacts = sorted(
        artifacts_by_path.values(),
        key=lambda item: str(item["label"]).encode("utf-8"),
    )
    directories = _fixed_directories(
        [str(item["path"]) for item in artifacts]
        + [
            "formal-ab16/control/",
        ],
        read_only_roots=(
            "bootstrap-authority",
            "campaign-authority",
        ),
        explicit_modes={
            ".": "0700",
            "formal-ab16": "0700",
            "formal-ab16/control": "0700",
            "gate1-v4": "0700",
        },
    )
    return artifacts, directories


def _arm_cap(
    label: str,
    artifact_class: str,
) -> int:
    if artifact_class == "model":
        return 8 * MIB
    if artifact_class == "ledger":
        return ARM_LEDGER_SEGMENT_MAXIMUM_BYTES
    if artifact_class == "metadata":
        return 4 * MIB
    if artifact_class == "closeout":
        return 8 * MIB
    if artifact_class != "publication":
        _fail("ARM_CAP_CLASS_UNSUPPORTED", f"{label}: {artifact_class}")
    if label in {
        "arm credibility gate",
        "independent arithmetic replay receipt",
        "independent resource terminal replay",
        "terminal classification",
    }:
        return 4 * MIB
    return {
        "attach solution-vector evidence": 4 * MIB,
        "raw incumbent export": 4 * MIB,
        "raw solution-vector export": 4 * MIB,
    }.get(label, 16 * MIB)


def _arm_multiplicity(
    label: str,
) -> tuple[int, str, dict[str, object]]:
    if label == "attach model evidence":
        return (
            2 * MAXIMUM_ATTACH_HOOKS,
            "common",
            {
                "kind": "attach-hook",
                "maximum_attach_hooks": MAXIMUM_ATTACH_HOOKS,
                "publications_per_hook": 2,
            },
        )
    if label == "attach solution-vector evidence":
        return (
            MAXIMUM_ATTACH_HOOKS,
            "common",
            {
                "kind": "attach-hook",
                "maximum_attach_hooks": MAXIMUM_ATTACH_HOOKS,
                "publications_per_hook": 1,
            },
        )
    if label in {
        "compile attach journal segment",
        "cut ledger segment",
        "runtime cut segment",
    }:
        return (
            0,
            "common",
            {
                "kind": "append-channel-only",
                "maximum_fixed_publications": 0,
            },
        )
    if label == "module-origin receipt":
        return (
            1,
            "common",
            {
                "kind": "single-fixed-path",
                "maximum_fixed_publications": 1,
            },
        )
    if label in {
        "AB16 immediate stop",
        "arm allocation unselected terminal",
        "arm consumed incomplete",
        "organic arm failure record",
    }:
        return (
            1,
            "failure",
            {
                "kind": "terminal-branch-fixed-path",
                "maximum_fixed_publications": 1,
                "terminal_branch": "failure",
            },
        )
    if label in {
        "arm launch environment",
        "organic arm selection",
        "organic pre-run authority",
        "organic pre-run candidate",
        "preselection manager epoch",
        "preselection manager transcript",
    }:
        return (
            1,
            "common",
            {
                "kind": "single-fixed-path",
                "maximum_fixed_publications": 1,
            },
        )
    if label in {
        "AB16 arm budget terminal",
        "AB16 organic attempt artifact manifest",
        "AB16 organic attempt root replay",
        "arm credibility gate",
        "cut-free incumbent replay receipt",
        "independent arithmetic replay receipt",
        "independent resource terminal replay",
        "organic arm consumption",
        "organic arm result",
        "raw incumbent export",
        "raw solution-vector export",
        "terminal classification",
    }:
        return (
            1,
            "success",
            {
                "kind": "terminal-branch-fixed-path",
                "maximum_fixed_publications": 1,
                "terminal_branch": "success",
            },
        )
    _fail("ARM_MULTIPLICITY_LABEL_UNSUPPORTED", label)


def _arm_path_contract(label: str, slot: str) -> dict[str, object]:
    attempt = f"prospective/arms/{slot}"
    fixed = {
        "AB16 immediate stop": "prospective/immediate-stop-a001.json",
        "AB16 arm budget terminal": f"budget/arm-terminals/{slot}.json",
        "AB16 organic attempt artifact manifest": (
            f"{attempt}/attempt-artifact-manifest.json"
        ),
        "AB16 organic attempt root replay": (
            f"replays/arm-attempt-roots/{slot}.json"
        ),
        "arm allocation unselected terminal": (
            f"{attempt}/arm-unselected-terminal.json"
        ),
        "arm consumed incomplete": (
            f"{attempt}/arm-consumed-incomplete.json"
        ),
        "arm credibility gate": (
            f"{attempt}/replays/arm-credibility.json"
        ),
        "arm launch environment": (
            "prospective/pre-run-candidates/"
            f"{slot}-launch-environment.json"
        ),
        "cut-free incumbent replay receipt": (
            f"{attempt}/replays/cut-free-incumbent.json"
        ),
        "independent arithmetic replay receipt": (
            f"{attempt}/replays/independent-arithmetic.json"
        ),
        "independent resource terminal replay": (
            f"{attempt}/replays/independent-resource-terminal.json"
        ),
        "module-origin receipt": f"{attempt}/module-origin-receipt.json",
        "organic arm consumption": (
            f"prospective/consumptions/{slot}.json"
        ),
        "organic arm failure record": f"{attempt}/failure.json",
        "organic arm result": f"{attempt}/result.json",
        "organic arm selection": f"{attempt}/selection.json",
        "organic pre-run authority": (
            f"{attempt}/pre-run-authority.json"
        ),
        "organic pre-run candidate": (
            f"prospective/pre-run-candidates/{slot}.json"
        ),
        "preselection manager epoch": (
            "prospective/pre-run-candidates/"
            f"{slot}-preselection-epoch.json"
        ),
        "preselection manager transcript": (
            "prospective/pre-run-candidates/"
            f"{slot}-preselection-transcript.json"
        ),
        "raw incumbent export": f"{attempt}/raw-incumbent.json",
        "raw solution-vector export": (
            f"{attempt}/raw-solution-vector.json"
        ),
        "terminal classification": (
            "prospective/terminal-classification-a001.json"
        ),
    }
    if label in fixed:
        return {
            "kind": "fixed",
            "root": "formal-root",
            "root_relative_path": fixed[label],
        }
    if label == "attach model evidence":
        return {
            "allowed_phases": ["post", "pre"],
            "index_maximum": MAXIMUM_ATTACH_HOOKS - 1,
            "index_minimum": 0,
            "index_name": "hook_id",
            "kind": "indexed-phase-template",
            "root": "formal-root",
            "root_relative_path_template": (
                f"{attempt}/runtime/hook-{{hook_id:04d}}-"
                "{phase}-model.pb"
            ),
        }
    if label == "attach solution-vector evidence":
        return {
            "index_maximum": MAXIMUM_ATTACH_HOOKS - 1,
            "index_minimum": 0,
            "index_name": "hook_id",
            "kind": "indexed-template",
            "root": "formal-root",
            "root_relative_path_template": (
                f"{attempt}/runtime/hook-{{hook_id:04d}}-"
                "solution-vector.json"
            ),
        }
    suffix_by_label = {
        channel_label: suffix
        for suffix, channel_label, _parent, _segments, _derivation in (
            ARM_APPEND_CHANNELS
        )
    }
    if label in suffix_by_label:
        return {
            "channel": f"arm-{slot}-{suffix_by_label[label]}",
            "kind": "append-channel",
            "root": "formal-root",
        }
    _fail("ARM_PATH_LABEL_UNSUPPORTED", label)


def _arm_cap_record(
    *,
    artifact_class: str,
    label: str,
    slot: str,
) -> dict[str, object]:
    maximum_publications, branch, multiplicity = _arm_multiplicity(label)
    return {
        "artifact_class": artifact_class,
        "branch": branch,
        "maximum_bytes": _arm_cap(label, artifact_class),
        "maximum_publications": maximum_publications,
        "multiplicity_source": multiplicity,
        "path_contract": _arm_path_contract(label, slot),
    }


def _arm_append_record(
    *,
    slot: str,
    suffix: str,
    label: str,
    relative_parent: str,
    maximum_segments: int,
    derivation: str,
) -> dict[str, object]:
    return {
        "artifact_class": "ledger",
        "channel": f"arm-{slot}-{suffix}",
        "label": label,
        "maximum_bytes": ARM_LEDGER_SEGMENT_MAXIMUM_BYTES,
        "maximum_segments": maximum_segments,
        "multiplicity_derivation": {
            "formula": derivation,
            "maximum_attach_hooks": MAXIMUM_ATTACH_HOOKS,
            "maximum_generated_cuts": MAXIMUM_GENERATED_CUTS,
            "result_maximum_segments": maximum_segments,
        },
        "parent_path": (
            f"prospective/arms/{slot}/{relative_parent}"
        ),
    }


def _arm_required_category_bytes(
    caps: Mapping[str, Mapping[str, object]],
    channels: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    by_branch: dict[str, dict[str, int]] = {
        branch: {} for branch in ARM_BRANCH_CONTRACT
    }
    for label, cap in caps.items():
        artifact_class = cap.get("artifact_class")
        maximum = cap.get("maximum_bytes")
        count = cap.get("maximum_publications")
        branch = cap.get("branch")
        if (
            type(artifact_class) is not str
            or artifact_class not in ARTIFACT_CLASSES
            or type(maximum) is not int
            or maximum <= 0
            or type(count) is not int
            or count < 0
            or type(branch) is not str
            or branch not in ARM_BRANCH_CONTRACT
        ):
            _fail("ARM_CAP_MULTIPLICITY_INVALID", label)
        # Publication branches stay mutually exclusive.  The failure record's
        # physical extent is nevertheless reserved in the common pool so it
        # survives any non-refundable success-branch staging that preceded a
        # later failure.
        allocation_branch = (
            "common"
            if label == INDEPENDENT_FAILURE_CLOSEOUT_LABEL
            else branch
        )
        branch_totals = by_branch[allocation_branch]
        branch_totals[artifact_class] = (
            branch_totals.get(artifact_class, 0) + maximum * count
        )
    append_totals: dict[str, int] = {}
    for channel in channels:
        artifact_class = channel.get("artifact_class")
        maximum = channel.get("maximum_bytes")
        count = channel.get("maximum_segments")
        name = channel.get("channel")
        if (
            type(artifact_class) is not str
            or artifact_class not in ARTIFACT_CLASSES
            or type(maximum) is not int
            or maximum <= 0
            or type(count) is not int
            or count < 0
            or type(name) is not str
        ):
            _fail("ARM_CHANNEL_MULTIPLICITY_INVALID", repr(name))
        append_totals[artifact_class] = (
            append_totals.get(artifact_class, 0) + maximum * count
        )
    classes = set(append_totals)
    for totals in by_branch.values():
        classes.update(totals)
    classes.add("scratch")
    required: dict[str, int] = {}
    for artifact_class in sorted(classes):
        required[artifact_class] = (
            by_branch["common"].get(artifact_class, 0)
            + max(
                by_branch["success"].get(artifact_class, 0),
                by_branch["failure"].get(artifact_class, 0),
            )
            + append_totals.get(artifact_class, 0)
        )
    return required


def _arm_branch_maximum_publications(
    caps: Mapping[str, Mapping[str, object]],
) -> int:
    totals = {branch: 0 for branch in ARM_BRANCH_CONTRACT}
    for label, cap in caps.items():
        count = cap.get("maximum_publications")
        branch = cap.get("branch")
        if (
            type(count) is not int
            or count < 0
            or type(branch) is not str
            or branch not in totals
        ):
            _fail("ARM_CAP_MULTIPLICITY_INVALID", label)
        totals[branch] += count
    return totals["common"] + max(totals["success"], totals["failure"])


def _arm_workload_contract(
    *,
    required_category_bytes: Mapping[str, int],
) -> dict[str, object]:
    allocation_margin = {
        artifact_class: (
            ARM_AGGREGATE_ALLOCATION.get(artifact_class, 0) - required
        )
        for artifact_class, required in required_category_bytes.items()
    }
    if any(value < 0 for value in allocation_margin.values()):
        _fail(
            "ARM_AGGREGATE_UNDERALLOCATED",
            "derived branch/channel maximum exceeds the arm allocation",
        )
    return {
        "allocation_formula": (
            "common[including the independent failure-closeout reserve] + "
            "per-class "
            "max(success branch, failure branch) + "
            "append[segment cap * maximum segments] + explicit margin"
        ),
        "allocation_margin_bytes": dict(sorted(allocation_margin.items())),
        "branch_contract": {
            branch: {
                "mutually_exclusive_with": list(
                    contract["mutually_exclusive_with"]
                )
            }
            for branch, contract in sorted(ARM_BRANCH_CONTRACT.items())
        },
        "hard_limits": {
            "maximum_attach_hooks": {
                "basis": "formal runtime maximum Benders iterations",
                "exhaustion": "arm-consumed-incomplete",
                "value": MAXIMUM_ATTACH_HOOKS,
            },
            "maximum_generated_cuts": {
                "basis": (
                    "policy-defined bounded workload cap; next power of two "
                    "above four generated cuts per maximum attach hook"
                ),
                "evidence_status": "unmeasured-temporary",
                "exhaustion": (
                    "fail before the first generated-cut write beyond the cap; "
                    "arm-consumed-incomplete"
                ),
                "sufficiency_claim": False,
                "value": MAXIMUM_GENERATED_CUTS,
            },
        },
        "historical_size_planning_input": {
            **HISTORICAL_SIZE_PLANNING_INPUT,
            "observations": [
                dict(item)
                for item in HISTORICAL_SIZE_OBSERVATIONS
            ],
        },
        "independent_failure_closeout_reserve": {
            "artifact_class": "closeout",
            "label": INDEPENDENT_FAILURE_CLOSEOUT_LABEL,
            "maximum_bytes": 8 * MIB,
            "physical_accounting_branch": "common",
            "publication_branch": "failure",
            "release_policy": (
                "non-refundable; remains available after any partial or "
                "complete success-branch staging"
            ),
        },
        "model_export_contract": {
            "cap_source": "attach model evidence.maximum_bytes",
            "export_open_mode": "O_TRUNC",
            "rlimit_fsize": (
                "set to the current model cap for each export and restore "
                "before any later publication"
            ),
            "sealed_memfd_required": True,
        },
        "per_file_cap_derivation": {
            "ledger_segment": {
                "basis": (
                    "policy-defined retained-segment cap pending comparable "
                    "calibration"
                ),
                "evidence_status": "unmeasured-temporary",
                "exhaustion": (
                    "fail before an oversized append publication; "
                    "arm-consumed-incomplete"
                ),
                "result_maximum_bytes": (
                    ARM_LEDGER_SEGMENT_MAXIMUM_BYTES
                ),
                "sufficiency_claim": False,
            },
            "model": {
                "factor": 4,
                "observed_maximum_bytes": 1_358_143,
                "result_maximum_bytes": 8 * MIB,
                "rounding": "next-power-of-two",
            },
            "vector_or_incumbent": {
                "factor": 4,
                "observed_maximum_bytes": 760_886,
                "result_maximum_bytes": 4 * MIB,
                "rounding": "next-power-of-two",
            },
            "temporary_canonical_record": {
                "evidence_status": "unmeasured-temporary",
                "labels": [
                    "AB16 organic attempt artifact manifest",
                    "cut-free incumbent replay receipt",
                    "organic arm result",
                ],
                "result_maximum_bytes": 16 * MIB,
            },
        },
        "required_category_bytes": dict(
            sorted(required_category_bytes.items())
        ),
        "scratch_contract": {
            "aggregate_allocation_bytes": 0,
            "known_retained_writer_count": 0,
            "tmp_directory_mode_octal": "0500",
            "write_attempt_result": "fail-closed",
        },
    }


def _formal_fixed_artifacts() -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []

    def add(
        label: str,
        path: str,
        artifact_class: str,
        maximum: int,
        *,
        required: bool = True,
    ) -> None:
        artifacts.append(
            _artifact(
                artifact_class=artifact_class,
                label=label,
                maximum_bytes=maximum,
                path=path,
                required_on_success=required,
            )
        )

    add(
        "formal-contract",
        "formal-root-budget-contract.json",
        "metadata",
        4 * MIB,
    )
    add(
        "formal-root-handoff",
        "formal-root-budget-handoff.json",
        "metadata",
        16 * MIB,
    )
    add(
        "AB16 baseline campaign provenance",
        "prospective/baseline/campaign-provenance.json",
        "metadata",
        4 * MIB,
    )
    add(
        "AB16 baseline incumbent",
        "prospective/baseline/incumbent.json",
        "publication",
        16 * MIB,
    )
    add(
        "AB16 baseline rebuild result",
        "prospective/baseline/rebuild-result.json",
        "publication",
        16 * MIB,
    )
    add(
        "AB16 baseline rebuilt metadata",
        "prospective/baseline/rebuilt-model-metadata.json",
        "metadata",
        16 * MIB,
    )
    add(
        "AB16 baseline rebuilt model",
        "prospective/baseline/cut-free-model.bin",
        "model",
        128 * MIB,
    )
    add(
        "AB16 baseline admission",
        "prospective/baseline-admission-a001.json",
        "publication",
        16 * MIB,
    )
    add(
        "AB16 baseline fixed replay",
        "prospective/baseline/fixed-replay-a001.json",
        "publication",
        16 * MIB,
    )
    add(
        "AB16 common prestate",
        "prospective/common/common-prestate-a001.json",
        "publication",
        16 * MIB,
    )
    add(
        "AB16 suite manifest",
        "prospective/manifest-a001.json",
        "publication",
        4 * MIB,
    )
    add(
        "AB16 suite selection",
        "prospective/selection-a001.json",
        "publication",
        4 * MIB,
    )
    add(
        "AB16 immediate stop",
        "prospective/immediate-stop-a001.json",
        "closeout",
        4 * MIB,
        required=False,
    )
    add(
        "AB16 terminal classification",
        "prospective/terminal-classification-a001.json",
        "publication",
        4 * MIB,
    )
    add(
        "formal launch admission",
        "formal-launch-admission-a001.json",
        "metadata",
        4 * MIB,
    )
    add(
        "outer guardian ready",
        "outer-guardian-ready-a001.json",
        "metadata",
        4 * MIB,
    )

    formal_attempt_artifacts = (
        ("child audit", "child-audit.json", "metadata", 4 * MIB, True),
        (
            "formal attempt consumption",
            "attempt-consumption.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal markerless incomplete",
            "markerless-incomplete.json",
            "closeout",
            4 * MIB,
            False,
        ),
        (
            "formal selection",
            "selection.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal gate1 prelaunch ownership",
            "gate1-prelaunch-ownership.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal outer barrier",
            "outer-barrier-release.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal controller result",
            "controller-result.json",
            "publication",
            8 * MIB,
            True,
        ),
        (
            "formal detached closeout",
            "detached-closeout.json",
            "closeout",
            4 * MIB,
            True,
        ),
        (
            "formal detached incomplete closeout",
            "detached-incomplete-closeout.json",
            "closeout",
            4 * MIB,
            False,
        ),
        (
            "formal guardian absence",
            "guardian-absence.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal guardian lock close",
            "guardian-lock-close.json",
            "metadata",
            4 * MIB,
            True,
        ),
        ("formal observer", "observer.json", "metadata", 4 * MIB, True),
        (
            "formal outer prelaunch",
            "outer-prelaunch.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal outer resource",
            "resource-live.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal outer start",
            "outer-start.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal outer terminal",
            "outer-terminal.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal post-Unref absence",
            "post-unref-absence.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal pre-Unref cleanup",
            "pre-unref-cleanup.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal reference acquisition",
            "reference-acquisition.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal reference connection close",
            "reference-connection-close.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal reference release",
            "reference-release.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal reference terminal",
            "reference-terminal.json",
            "metadata",
            4 * MIB,
            True,
        ),
        (
            "formal supervisor raw lock release",
            "supervisor-raw-lock-release.json",
            "metadata",
            4 * MIB,
            True,
        ),
    )
    for label, name, artifact_class, maximum, required in (
        formal_attempt_artifacts
    ):
        add(
            label,
            f"formal-attempt-a001/{name}",
            artifact_class,
            maximum,
            required=required,
        )

    for slot in ARM_SLOTS:
        add(
            f"{slot} pre-run candidate",
            f"prospective/pre-run-candidates/{slot}.json",
            "metadata",
            512 * 1024,
        )
        add(
            f"{slot} preselection epoch",
            "prospective/pre-run-candidates/"
            f"{slot}-preselection-epoch.json",
            "metadata",
            512 * 1024,
        )
        add(
            f"{slot} preselection transcript",
            "prospective/pre-run-candidates/"
            f"{slot}-preselection-transcript.json",
            "metadata",
            512 * 1024,
        )
        add(
            f"{slot} launch environment",
            "prospective/pre-run-candidates/"
            f"{slot}-launch-environment.json",
            "metadata",
            512 * 1024,
        )
        add(
            f"{slot} binding",
            f"prospective/bindings/{slot}.json",
            "metadata",
            512 * 1024,
        )
        add(
            f"{slot} arm prelaunch request",
            f"formal-attempt-a001/arm-prelaunch/{slot}-request.json",
            "metadata",
            512 * 1024,
        )
        add(
            f"{slot} arm prelaunch receipt",
            f"formal-attempt-a001/arm-prelaunch/{slot}-receipt.json",
            "metadata",
            512 * 1024,
        )
    return sorted(
        artifacts,
        key=lambda item: str(item["label"]).encode("utf-8"),
    )


def _sum_by_class(
    artifacts: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in artifacts:
        artifact_class = str(item["artifact_class"])
        maximum_raw = item["maximum_bytes"]
        if isinstance(maximum_raw, bool) or not isinstance(
            maximum_raw,
            int,
        ):
            _fail("ARTIFACT_MAXIMUM_INVALID", artifact_class)
        maximum = maximum_raw
        result[artifact_class] = (
            result.get(artifact_class, 0) + maximum
        )
    return result


def build_profile(
    *,
    repository_root: Path | str,
    repository_members: Mapping[str, int],
    execution_surface_sha256: str,
    profile_id: str,
    launch_ready: bool,
    launch_ready_acknowledgement: str | None = None,
) -> dict[str, object]:
    root = Path(os.path.abspath(os.fspath(repository_root)))
    if (
        SHA256_RE.fullmatch(execution_surface_sha256) is None
        or type(profile_id) is not str
        or not profile_id
    ):
        _fail(
            "PROFILE_IDENTITY_INVALID",
            "profile_id and execution-surface SHA are required",
        )
    if launch_ready and (
        launch_ready_acknowledgement != LAUNCH_READY_ACKNOWLEDGEMENT
    ):
        _fail(
            "LAUNCH_READY_ACK_REQUIRED",
            "launch-ready generation requires the exact calibration acknowledgement",
        )
    if not launch_ready and launch_ready_acknowledgement is not None:
        _fail(
            "LAUNCH_READY_ACK_UNEXPECTED",
            "blocked profile must not carry a launch-ready acknowledgement",
        )
    members = {
        _portable_relative_path(path, label="repository member"): (
            int(size)
        )
        for path, size in repository_members.items()
    }
    if (
        not members
        or any(
            isinstance(size, bool) or size <= 0
            for size in members.values()
        )
        or PROFILE_RELATIVE_PATH not in members
    ):
        _fail(
            "REPOSITORY_MEMBER_SET_INVALID",
            "repository members must be positive and include the profile",
        )

    registries = fixed_source_registries(root)
    bootstrap_artifacts, bootstrap_directories = _bootstrap_artifacts(
        root,
        members,
        registries,
    )
    bootstrap_limits = _sum_by_class(bootstrap_artifacts)
    bootstrap_limits["closeout"] = (
        bootstrap_limits.get("closeout", 0)
        + BOOTSTRAP_FAILURE_CLOSEOUT_MAXIMUM_BYTES
    )

    arm_labels = registries["arm_labels"]
    assert isinstance(arm_labels, dict)
    arm_allocations = {
        slot: dict(ARM_AGGREGATE_ALLOCATION) for slot in ARM_SLOTS
    }
    arm_artifact_caps = {
        slot: {
            label: _arm_cap_record(
                artifact_class=artifact_class,
                label=label,
                slot=slot,
            )
            for label, artifact_class in sorted(
                arm_labels.items(),
                key=lambda item: item[0].encode("utf-8"),
            )
        }
        for slot in ARM_SLOTS
    }
    arm_append_channels = {
        slot: sorted(
            [
                _arm_append_record(
                    slot=slot,
                    suffix=suffix,
                    label=label,
                    relative_parent=relative_parent,
                    maximum_segments=maximum_segments,
                    derivation=derivation,
                )
                for (
                    suffix,
                    label,
                    relative_parent,
                    maximum_segments,
                    derivation,
                ) in ARM_APPEND_CHANNELS
            ],
            key=lambda item: str(item["channel"]).encode("utf-8"),
        )
        for slot in ARM_SLOTS
    }
    first_slot = ARM_SLOTS[0]
    arm_required_category_bytes = _arm_required_category_bytes(
        arm_artifact_caps[first_slot],
        arm_append_channels[first_slot],
    )
    arm_workload_contract = _arm_workload_contract(
        required_category_bytes=arm_required_category_bytes,
    )
    arm_append_maximum = 0
    for channel in arm_append_channels[first_slot]:
        segments = channel["maximum_segments"]
        if type(segments) is not int or segments < 0:
            _fail(
                "ARM_CHANNEL_MULTIPLICITY_INVALID",
                str(channel["channel"]),
            )
        arm_append_maximum += segments
    arm_fixed_publication_maximum = _arm_branch_maximum_publications(
        arm_artifact_caps[first_slot]
    )
    journal_policy_minimum = (
        len(ARM_SLOTS)
        * (
            arm_append_maximum
            + arm_fixed_publication_maximum
            + FORMAL_BUDGET_JOURNAL_PER_ARM_CONTROL_ALLOWANCE
        )
        + FORMAL_BUDGET_JOURNAL_ROOT_CONTROL_ALLOWANCE
    )
    if journal_policy_minimum > FORMAL_BUDGET_JOURNAL_MAXIMUM_SEGMENTS:
        _fail(
            "FORMAL_BUDGET_JOURNAL_UNDERALLOCATED",
            "policy-derived action count exceeds the journal allocation",
        )

    formal_artifacts = _formal_fixed_artifacts()
    formal_append_maximum = MIB
    formal_append_channels = [
        {
            "artifact_class": "ledger",
            "channel": "ab16-baseline-rebuild-cuts",
            "label": "AB16 baseline cut segment",
            "maximum_bytes": formal_append_maximum,
            "maximum_segments": FORMAL_BASELINE_MAXIMUM_SEGMENTS,
            "multiplicity_derivation": {
                "basis": (
                    "temporary unmeasured conservative baseline append cap"
                ),
                "evidence_status": "unmeasured-temporary",
                "exhaustion": "formal-consumed-incomplete",
                "result_maximum_segments": (
                    FORMAL_BASELINE_MAXIMUM_SEGMENTS
                ),
            },
            "parent_path": (
                "prospective/baseline/checkpoint/benders-cuts"
            ),
        },
        {
            "artifact_class": "metadata",
            "channel": "budget-journal",
            "label": "AB16 formal budget journal segment",
            "maximum_bytes": FORMAL_BUDGET_JOURNAL_MAXIMUM_BYTES,
            "maximum_segments": (
                FORMAL_BUDGET_JOURNAL_MAXIMUM_SEGMENTS
            ),
            "multiplicity_derivation": {
                "basis": (
                    "profile-derived data-plane maxima plus explicit "
                    "temporary control-plane allowances"
                ),
                "bootstrap_and_formal_control_allowance": (
                    FORMAL_BUDGET_JOURNAL_ROOT_CONTROL_ALLOWANCE
                ),
                "derived_minimum_actions": journal_policy_minimum,
                "evidence_status": "unmeasured-temporary",
                "exhaustion": (
                    "fail before the next broker-journal append; "
                    "formal-consumed-incomplete"
                ),
                "formal_arm_count": len(ARM_SLOTS),
                "maximum_segment_bytes": (
                    FORMAL_BUDGET_JOURNAL_MAXIMUM_BYTES
                ),
                "per_arm_append_maximum": arm_append_maximum,
                "per_arm_control_allowance": (
                    FORMAL_BUDGET_JOURNAL_PER_ARM_CONTROL_ALLOWANCE
                ),
                "per_arm_fixed_publication_branch_maximum": (
                    arm_fixed_publication_maximum
                ),
                "retained_allocation_bytes": (
                    FORMAL_BUDGET_JOURNAL_MAXIMUM_BYTES
                    * FORMAL_BUDGET_JOURNAL_MAXIMUM_SEGMENTS
                ),
                "result_maximum_segments": (
                    FORMAL_BUDGET_JOURNAL_MAXIMUM_SEGMENTS
                ),
                "segment_cap_basis": (
                    "policy-defined canonical action-record cap pending "
                    "comparable calibration"
                ),
                "segment_count_rounding": (
                    "next power of two above derived minimum actions"
                ),
                "sufficiency_claim": False,
            },
            "parent_path": "channels/budget-journal",
        },
    ]
    formal_append_channels.sort(
        key=lambda item: str(item["channel"]).encode("utf-8")
    )
    formal_paths = [str(item["path"]) for item in formal_artifacts]
    formal_paths.extend(
        str(item["parent_path"]) + "/"
        for item in formal_append_channels
    )
    formal_paths.extend(
        str(item["parent_path"]) + "/"
        for item in FORMAL_FIXED_RESERVATIONS
        if item["parent_scope"] == "formal-root"
    )
    formal_paths.extend(
        (
            "budget/arm-terminals/",
            "replays/arm-attempt-roots/",
            "prospective/arms/",
            "prospective/bindings/",
            "prospective/common/",
            "prospective/consumptions/",
            "prospective/pre-run-candidates/",
            "prospective/baseline/tmp/",
            "formal-attempt-a001/arm-prelaunch/",
        )
    )
    for slot in ARM_SLOTS:
        for suffix, _mode in ARM_DIRECTORY_SUFFIX_MODES:
            formal_paths.append(f"prospective/arms/{slot}/{suffix}/")
        formal_paths.append(f"prospective/arms/{slot}/")
    formal_modes = {
        f"prospective/arms/{slot}/tmp": "0500"
        for slot in ARM_SLOTS
    }
    formal_modes["prospective/baseline/tmp"] = "0500"
    formal_directories = _fixed_directories(
        formal_paths,
        explicit_modes=formal_modes,
    )

    fixed_limits = _sum_by_class(formal_artifacts)
    for channel in formal_append_channels:
        artifact_class = str(channel["artifact_class"])
        maximum_raw = channel["maximum_bytes"]
        segments_raw = channel["maximum_segments"]
        if (
            type(maximum_raw) is not int
            or maximum_raw <= 0
            or type(segments_raw) is not int
            or segments_raw < 0
        ):
            _fail(
                "FORMAL_CHANNEL_MAXIMUM_INVALID",
                str(channel["channel"]),
            )
        fixed_limits[artifact_class] = (
            fixed_limits.get(artifact_class, 0)
            + maximum_raw * segments_raw
        )
    for reservation in FORMAL_FIXED_RESERVATIONS:
        artifact_class = str(reservation["artifact_class"])
        maximum_raw = reservation["maximum_bytes"]
        if isinstance(maximum_raw, bool) or not isinstance(
            maximum_raw,
            int,
        ):
            _fail("RESERVATION_MAXIMUM_INVALID", artifact_class)
        fixed_limits[artifact_class] = (
            fixed_limits.get(artifact_class, 0)
            + maximum_raw
        )
    for artifact_class, maximum in FORMAL_FIXED_HEADROOM.items():
        fixed_limits[artifact_class] = (
            fixed_limits.get(artifact_class, 0) + maximum
        )
    formal_limits = dict(fixed_limits)
    for allocation in arm_allocations.values():
        for artifact_class, maximum in allocation.items():
            formal_limits[artifact_class] = (
                formal_limits.get(artifact_class, 0) + maximum
            )

    formal_reservations = [
        dict(item) for item in FORMAL_FIXED_RESERVATIONS
    ]
    formal_reservations.sort(
        key=lambda item: str(item.get("purpose")).encode("utf-8")
    )
    profile: dict[str, object] = {
        "authority": dict(FALSE_AUTHORITY),
        "bootstrap": {
            "artifact_maxima": bootstrap_artifacts,
            "category_limits": dict(sorted(bootstrap_limits.items())),
            "failure_closeout_reserve": {
                "artifact_class": "closeout",
                "maximum_bytes": (
                    BOOTSTRAP_FAILURE_CLOSEOUT_MAXIMUM_BYTES
                ),
                "parent_path": "bootstrap-authority",
                "purpose": "bootstrap-failure-closeout",
                "target_name": (
                    "bootstrap-package-failure-closeout.json"
                ),
            },
            "fixed_directories": bootstrap_directories,
            "root_relative_path": ".",
        },
        "execution_surface_sha256": execution_surface_sha256,
        "formal_root": {
            "append_channels": formal_append_channels,
            "arm_allocations": arm_allocations,
            "arm_append_channels": arm_append_channels,
            "arm_artifact_caps": arm_artifact_caps,
            "arm_workload_contract": arm_workload_contract,
            "artifact_maxima": formal_artifacts,
            "category_limits": dict(sorted(formal_limits.items())),
            "fixed_directories": formal_directories,
            "fixed_overhead_category_limits": dict(
                sorted(fixed_limits.items())
            ),
            "fixed_purpose_reservations": formal_reservations,
            "root_relative_path": "formal-ab16/artifacts",
        },
        "launch_ready": launch_ready,
        "profile_id": profile_id,
        "profile_sha256": "",
        "schema_version": SCHEMA_VERSION,
    }
    profile["profile_sha256"] = digest_without(
        profile,
        "profile_sha256",
    )
    validate_built_profile(profile, arm_labels=arm_labels)
    return profile


def validate_built_profile(
    profile: Mapping[str, object],
    *,
    arm_labels: Mapping[str, str],
) -> None:
    if (
        set(profile)
        != {
            "authority",
            "bootstrap",
            "execution_surface_sha256",
            "formal_root",
            "launch_ready",
            "profile_id",
            "profile_sha256",
            "schema_version",
        }
        or profile["authority"] != FALSE_AUTHORITY
        or profile["schema_version"] != SCHEMA_VERSION
        or type(profile["launch_ready"]) is not bool
        or type(profile["profile_id"]) is not str
        or not profile["profile_id"]
        or type(profile["execution_surface_sha256"]) is not str
        or SHA256_RE.fullmatch(profile["execution_surface_sha256"]) is None
        or type(profile["profile_sha256"]) is not str
        or profile["profile_sha256"]
        != digest_without(profile, "profile_sha256")
    ):
        _fail("PROFILE_IDENTITY_DRIFT", "top-level profile closure failed")
    bootstrap = profile["bootstrap"]
    formal = profile["formal_root"]
    if type(bootstrap) is not dict or type(formal) is not dict:
        _fail("PROFILE_SECTION_INVALID", "bootstrap/formal root is absent")
    if (
        set(bootstrap)
        != {
            "artifact_maxima",
            "category_limits",
            "failure_closeout_reserve",
            "fixed_directories",
            "root_relative_path",
        }
        or bootstrap["root_relative_path"] != "."
        or set(formal)
        != {
            "append_channels",
            "arm_allocations",
            "arm_append_channels",
            "arm_artifact_caps",
            "arm_workload_contract",
            "artifact_maxima",
            "category_limits",
            "fixed_directories",
            "fixed_overhead_category_limits",
            "fixed_purpose_reservations",
            "root_relative_path",
        }
        or formal["root_relative_path"] != "formal-ab16/artifacts"
    ):
        _fail("PROFILE_SECTION_FIELDS_DRIFT", "section key set drifted")
    if set(formal["arm_allocations"]) != set(ARM_SLOTS):
        _fail("ARM_ALLOCATION_SET_DRIFT", "arm allocation set is not exact")
    expected_reservations = sorted(
        (dict(item) for item in FORMAL_FIXED_RESERVATIONS),
        key=lambda item: str(item["purpose"]).encode("utf-8"),
    )
    if formal["fixed_purpose_reservations"] != expected_reservations:
        _fail(
            "FORMAL_FIXED_RESERVATION_DRIFT",
            "fixed-purpose reservation set or storage domain is not exact",
        )
    if set(formal["arm_artifact_caps"]) != set(ARM_SLOTS):
        _fail("ARM_CAP_SET_DRIFT", "arm cap set is not exact")
    if set(formal["arm_append_channels"]) != set(ARM_SLOTS):
        _fail("ARM_CHANNEL_SET_DRIFT", "arm channel set is not exact")
    first_slot_caps = {
        label: _arm_cap_record(
            artifact_class=artifact_class,
            label=label,
            slot=ARM_SLOTS[0],
        )
        for label, artifact_class in arm_labels.items()
    }
    first_slot_channels = [
        _arm_append_record(
            slot=ARM_SLOTS[0],
            suffix=suffix,
            label=label,
            relative_parent=relative_parent,
            maximum_segments=maximum_segments,
            derivation=derivation,
        )
        for (
            suffix,
            label,
            relative_parent,
            maximum_segments,
            derivation,
        ) in ARM_APPEND_CHANNELS
    ]
    expected_arm_append_maximum = sum(
        cast(int, channel["maximum_segments"])
        for channel in first_slot_channels
    )
    expected_arm_fixed_maximum = _arm_branch_maximum_publications(
        first_slot_caps
    )
    expected_journal_minimum = (
        len(ARM_SLOTS)
        * (
            expected_arm_append_maximum
            + expected_arm_fixed_maximum
            + FORMAL_BUDGET_JOURNAL_PER_ARM_CONTROL_ALLOWANCE
        )
        + FORMAL_BUDGET_JOURNAL_ROOT_CONTROL_ALLOWANCE
    )
    expected_formal_append_channels = [
        {
            "artifact_class": "ledger",
            "channel": "ab16-baseline-rebuild-cuts",
            "label": "AB16 baseline cut segment",
            "maximum_bytes": MIB,
            "maximum_segments": FORMAL_BASELINE_MAXIMUM_SEGMENTS,
            "multiplicity_derivation": {
                "basis": (
                    "temporary unmeasured conservative baseline append cap"
                ),
                "evidence_status": "unmeasured-temporary",
                "exhaustion": "formal-consumed-incomplete",
                "result_maximum_segments": (
                    FORMAL_BASELINE_MAXIMUM_SEGMENTS
                ),
            },
            "parent_path": (
                "prospective/baseline/checkpoint/benders-cuts"
            ),
        },
        {
            "artifact_class": "metadata",
            "channel": "budget-journal",
            "label": "AB16 formal budget journal segment",
            "maximum_bytes": FORMAL_BUDGET_JOURNAL_MAXIMUM_BYTES,
            "maximum_segments": (
                FORMAL_BUDGET_JOURNAL_MAXIMUM_SEGMENTS
            ),
            "multiplicity_derivation": {
                "basis": (
                    "profile-derived data-plane maxima plus explicit "
                    "temporary control-plane allowances"
                ),
                "bootstrap_and_formal_control_allowance": (
                    FORMAL_BUDGET_JOURNAL_ROOT_CONTROL_ALLOWANCE
                ),
                "derived_minimum_actions": expected_journal_minimum,
                "evidence_status": "unmeasured-temporary",
                "exhaustion": (
                    "fail before the next broker-journal append; "
                    "formal-consumed-incomplete"
                ),
                "formal_arm_count": len(ARM_SLOTS),
                "maximum_segment_bytes": (
                    FORMAL_BUDGET_JOURNAL_MAXIMUM_BYTES
                ),
                "per_arm_append_maximum": (
                    expected_arm_append_maximum
                ),
                "per_arm_control_allowance": (
                    FORMAL_BUDGET_JOURNAL_PER_ARM_CONTROL_ALLOWANCE
                ),
                "per_arm_fixed_publication_branch_maximum": (
                    expected_arm_fixed_maximum
                ),
                "retained_allocation_bytes": (
                    FORMAL_BUDGET_JOURNAL_MAXIMUM_BYTES
                    * FORMAL_BUDGET_JOURNAL_MAXIMUM_SEGMENTS
                ),
                "result_maximum_segments": (
                    FORMAL_BUDGET_JOURNAL_MAXIMUM_SEGMENTS
                ),
                "segment_cap_basis": (
                    "policy-defined canonical action-record cap pending "
                    "comparable calibration"
                ),
                "segment_count_rounding": (
                    "next power of two above derived minimum actions"
                ),
                "sufficiency_claim": False,
            },
            "parent_path": "channels/budget-journal",
        },
    ]
    if formal["append_channels"] != expected_formal_append_channels:
        _fail(
            "FORMAL_CHANNEL_CONTRACT_DRIFT",
            "baseline append multiplicity is not exact",
        )
    expected_workload: dict[str, object] | None = None
    for slot in ARM_SLOTS:
        caps = formal["arm_artifact_caps"][slot]
        if set(caps) != set(arm_labels):
            _fail("ARM_CAP_LABEL_SET_DRIFT", slot)
        for label, artifact_class in arm_labels.items():
            expected_cap = _arm_cap_record(
                artifact_class=artifact_class,
                label=label,
                slot=slot,
            )
            if caps[label] != expected_cap:
                _fail(
                    "ARM_CAP_CONTRACT_DRIFT",
                    f"{slot}: {label}",
                )
        channels = formal["arm_append_channels"][slot]
        if type(channels) is not list or len(channels) != 3:
            _fail("ARM_CHANNEL_COUNT_DRIFT", slot)
        for item, (
            suffix,
            label,
            parent,
            maximum_segments,
            derivation,
        ) in zip(
            channels,
            ARM_APPEND_CHANNELS,
            strict=True,
        ):
            if item != _arm_append_record(
                slot=slot,
                suffix=suffix,
                label=label,
                relative_parent=parent,
                maximum_segments=maximum_segments,
                derivation=derivation,
            ):
                _fail("ARM_CHANNEL_CONTRACT_DRIFT", slot)
        required = _arm_required_category_bytes(caps, channels)
        workload = _arm_workload_contract(
            required_category_bytes=required,
        )
        if expected_workload is None:
            expected_workload = workload
        elif workload != expected_workload:
            _fail("ARM_WORKLOAD_PER_SLOT_DRIFT", slot)
        allocation = formal["arm_allocations"][slot]
        if type(allocation) is not dict:
            _fail("ARM_AGGREGATE_DRIFT", slot)
        for artifact_class, amount in required.items():
            allocated = allocation.get(artifact_class, 0)
            if (
                type(allocated) is not int
                or allocated < amount
            ):
                _fail(
                    "ARM_AGGREGATE_UNDERALLOCATED",
                    f"{slot}: {artifact_class}",
                )
        if allocation != ARM_AGGREGATE_ALLOCATION:
            _fail("ARM_AGGREGATE_DRIFT", slot)
    if (
        expected_workload is None
        or formal["arm_workload_contract"] != expected_workload
    ):
        _fail(
            "ARM_WORKLOAD_CONTRACT_DRIFT",
            "shared arm workload derivation differs",
        )
    expected_formal_limits = dict(
        formal["fixed_overhead_category_limits"]
    )
    for allocation in formal["arm_allocations"].values():
        for artifact_class, maximum in allocation.items():
            expected_formal_limits[artifact_class] = (
                expected_formal_limits.get(artifact_class, 0)
                + maximum
            )
    if formal["category_limits"] != dict(
        sorted(expected_formal_limits.items())
    ):
        _fail(
            "FORMAL_AGGREGATE_ARITHMETIC_DRIFT",
            "root is not fixed overhead plus sixteen arm allocations",
        )
    bootstrap_totals = _sum_by_class(bootstrap["artifact_maxima"])
    reserve = bootstrap["failure_closeout_reserve"]
    bootstrap_totals[reserve["artifact_class"]] = (
        bootstrap_totals.get(reserve["artifact_class"], 0)
        + reserve["maximum_bytes"]
    )
    if bootstrap["category_limits"] != dict(
        sorted(bootstrap_totals.items())
    ):
        _fail(
            "BOOTSTRAP_AGGREGATE_ARITHMETIC_DRIFT",
            "bootstrap category limits do not cover exact retained maxima",
        )


def _open_absolute_directory_no_symlinks(path: Path) -> int:
    absolute = Path(os.path.abspath(path))
    if not absolute.is_absolute():
        _fail("OUTPUT_PARENT_INVALID", str(path))
    owned = [
        os.open(
            "/",
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
        )
    ]
    result = -1
    primary: BaseException | None = None
    try:
        for part in absolute.parts[1:]:
            owned.append(
                os.open(
                    part,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    dir_fd=owned[-1],
                )
            )
        result = owned.pop()
        while owned:
            os.close(owned.pop())
        return result
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if primary is not None:
            descriptors = (
                ([result] if result >= 0 else []) + list(reversed(owned))
            )
            for descriptor in descriptors:
                try:
                    os.close(descriptor)
                except BaseException as cleanup_error:
                    primary.add_note(
                        "output-parent descriptor cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )


def write_no_overwrite(path: Path | str, raw: bytes) -> dict[str, object]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parent_fd = -1
    descriptor = -1
    primary: BaseException | None = None
    try:
        try:
            parent_fd = _open_absolute_directory_no_symlinks(
                absolute.parent
            )
        except OSError as exc:
            _fail(
                "OUTPUT_PARENT_OPEN_FAILED",
                f"{absolute.parent}: {exc}",
            )
        try:
            descriptor = os.open(
                absolute.name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | os.O_NOFOLLOW,
                0o444,
                dir_fd=parent_fd,
            )
        except FileExistsError:
            _fail("OUTPUT_NO_OVERWRITE", str(absolute))
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                _fail("OUTPUT_WRITE_STALLED", str(absolute))
            offset += written
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        named = os.stat(
            absolute.name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o444
            or metadata.st_uid != os.getuid()
            or metadata.st_dev != named.st_dev
            or metadata.st_ino != named.st_ino
            or metadata.st_size != len(raw)
        ):
            _fail("OUTPUT_IDENTITY_DRIFT", str(absolute))
        os.fsync(parent_fd)
        return {
            "path": str(absolute),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
    except BaseException as exc:
        primary = exc
        raise
    finally:
        for owned in (descriptor, parent_fd):
            if owned < 0:
                continue
            try:
                os.close(owned)
            except BaseException as close_error:
                if primary is None:
                    raise
                primary.add_note(
                    "profile output descriptor cleanup also failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )


def build_phase2_blocked_profile(
    repository_root: Path | str,
) -> dict[str, object]:
    members = discover_repository_members(
        repository_root,
        launch_ready=False,
    )
    return build_profile(
        repository_root=repository_root,
        repository_members=members,
        execution_surface_sha256=(
            PHASE2_BLOCKED_EXECUTION_SURFACE_SHA256
        ),
        profile_id=PROFILE_ID_PHASE2_BLOCKED,
        launch_ready=False,
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--execution-surface-sha256",
        default=PHASE2_BLOCKED_EXECUTION_SURFACE_SHA256,
    )
    parser.add_argument(
        "--profile-id",
        default=PROFILE_ID_PHASE2_BLOCKED,
    )
    parser.add_argument("--launch-ready", action="store_true")
    parser.add_argument("--launch-ready-acknowledgement")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare exact canonical bytes instead of publishing",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    members = discover_repository_members(
        args.repository_root,
        launch_ready=args.launch_ready,
    )
    profile = build_profile(
        repository_root=args.repository_root,
        repository_members=members,
        execution_surface_sha256=args.execution_surface_sha256,
        profile_id=args.profile_id,
        launch_ready=args.launch_ready,
        launch_ready_acknowledgement=(
            args.launch_ready_acknowledgement
        ),
    )
    raw = canonical_json(profile)
    if args.check:
        try:
            observed = args.output.read_bytes()
        except OSError as exc:
            _fail("PROFILE_CHECK_READ_FAILED", str(exc))
        if observed != raw:
            _fail(
                "PROFILE_CHECK_MISMATCH",
                str(args.output.absolute()),
            )
        result = {
            "launch_ready": profile["launch_ready"],
            "path": str(args.output.absolute()),
            "profile_sha256": profile["profile_sha256"],
            "schema_version": profile["schema_version"],
            "status": "MATCH",
        }
    else:
        identity = write_no_overwrite(args.output, raw)
        result = {
            "identity": identity,
            "launch_ready": profile["launch_ready"],
            "profile_sha256": profile["profile_sha256"],
            "schema_version": profile["schema_version"],
            "status": "CREATED",
        }
    sys.stdout.buffer.write(canonical_json(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProfileBuildError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(2) from exc
