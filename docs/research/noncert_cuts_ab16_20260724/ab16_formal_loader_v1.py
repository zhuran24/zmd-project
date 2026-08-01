#!/usr/bin/env python3
"""Second-stage isolated loader for one verified AB16 snapshot role.

The first stage must already have loaded and byte-verified the sealed
``ab16_authority_v2`` package tool.  This module calls its planned
``replay_loader_context`` interface and deliberately has no fallback package
or snapshot verifier.  After replay it:

1. rejects ambient repository modules and checkout-shaped import paths;
2. injects only the verified materialized snapshot root into the ordinary
   ``PathFinder`` search path;
3. imports one fixed role;
4. proves that every repository module origin/path is inside that snapshot.

CPython, the standard library, OR-Tools/protobuf and their native dependencies
remain explicit external platform assumptions.  The loader is intended for
``python -I -B`` and fails closed under a coherent interpreter lacking either
flag.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import importlib
from importlib.machinery import BuiltinImporter, FrozenImporter, PathFinder
from importlib.util import cache_from_source
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
from types import ModuleType
from typing import Any, cast


LOADER_CONTEXT_SCHEMA = "noncert-cuts-ab16-formal-loader-context-v1"
AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
HEAD_RE = re.compile(r"[0-9a-f]{40}\Z")
PYTHON_FD = 3
LOADER_FD = 4
AUTHORITY_FD = 5
NATIVE_HELPER_WRAPPER_FD = 6
NATIVE_HELPER_FD = 7
BUDGET_BROKER_FD = 8
FORMAL_LAUNCH_CLAIM_FD = 9
FORMAL_SUPERVISOR_SESSION_FD = 10
MAX_FORMAL_SUPERVISOR_SESSION_BYTES = 64 * 1024
FORMAL_LAUNCH_CLAIM_IDENTITY_SCHEMA = (
    "noncert-cuts-ab16-formal-launch-owner-claim-identity-v1"
)
MAX_AUTHORITY_BYTES = 64 * 1024 * 1024
MAX_NATIVE_HELPER_WRAPPER_BYTES = 16 * 1024 * 1024
MAX_NATIVE_HELPER_BYTES = 4 * 1024 * 1024
PACKAGE_PAYLOAD_MODE = 0o600

RESEARCH_PREFIX = "docs.research.noncert_cuts_ab16_20260724"


@dataclass(frozen=True)
class RoleSpec:
    module_name: str
    source_path: str
    argv_prefix: tuple[str, ...] = ()


ROLE_MAP: dict[str, RoleSpec] = {
    "baseline-rebuild": RoleSpec(
        f"{RESEARCH_PREFIX}.baseline_rebuild_v1",
        "docs/research/noncert_cuts_ab16_20260724/baseline_rebuild_v1.py",
    ),
    "baseline-admission": RoleSpec(
        f"{RESEARCH_PREFIX}.baseline_admission_v1",
        "docs/research/noncert_cuts_ab16_20260724/baseline_admission_v1.py",
    ),
    "cut-free-incumbent-replay": RoleSpec(
        f"{RESEARCH_PREFIX}.cut_free_incumbent_replay_v1",
        "docs/research/noncert_cuts_ab16_20260724/cut_free_incumbent_replay_v1.py",
    ),
    "formal-launch-authority": RoleSpec(
        f"{RESEARCH_PREFIX}.ab16_formal_launch_authority_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_launch_authority_v1.py",
    ),
    "formal-launch-validator": RoleSpec(
        f"{RESEARCH_PREFIX}.ab16_formal_launch_validator_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_launch_validator_v1.py",
    ),
    "formal-orchestrator": RoleSpec(
        f"{RESEARCH_PREFIX}.ab16_formal_orchestrator_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_orchestrator_v1.py",
    ),
    "formal-controller": RoleSpec(
        f"{RESEARCH_PREFIX}.ab16_formal_controller_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_controller_v1.py",
    ),
    "formal-success-verifier": RoleSpec(
        f"{RESEARCH_PREFIX}.ab16_formal_success_verifier_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_success_verifier_v1.py",
    ),
    "formal-supervisor": RoleSpec(
        f"{RESEARCH_PREFIX}.ab16_formal_campaign_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_campaign_v1.py",
    ),
    "organic-arm": RoleSpec(
        f"{RESEARCH_PREFIX}.organic_arm_runner_v1",
        "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py",
    ),
    "organic-supervisor": RoleSpec(
        f"{RESEARCH_PREFIX}.organic_resource_lifecycle_v2",
        "docs/research/noncert_cuts_ab16_20260724/organic_resource_lifecycle_v2.py",
        ("supervise",),
    ),
    "outer-guardian": RoleSpec(
        f"{RESEARCH_PREFIX}.ab16_outer_guardian_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_outer_guardian_v1.py",
    ),
}

BUDGET_BOUND_WORKER_ROLES = frozenset(
    {
        "baseline-admission",
        "baseline-rebuild",
        "cut-free-incumbent-replay",
    }
)
FORMAL_ARM_SUPERVISOR_ROLE = "organic-supervisor"
FORMAL_ARM_WORKER_ROLE = "organic-arm"
FORMAL_WORKER_SESSION_SCHEMA = "noncert-cuts-ab16-formal-worker-session-v1"

LOADER_CONTEXT_FIELDS = frozenset(
    {
        "authority_scope",
        "campaign_dir",
        "campaign_root_identity",
        "package_id",
        "package_manifest_identity",
        "package_seal_identity",
        "repository_head",
        "repository_tree",
        "role",
        "role_module",
        "role_source_identity",
        "schema_version",
        "snapshot_materialization_identity",
        "snapshot_root",
        "status",
    }
)

LEGACY_ALIASES = (
    (
        "ab16_authority_v2",
        f"{RESEARCH_PREFIX}.ab16_authority_v2",
        "docs/research/noncert_cuts_ab16_20260724/ab16_authority_v2.py",
    ),
    (
        "ab16_outer_closeout_state_v1",
        f"{RESEARCH_PREFIX}.ab16_outer_closeout_state_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_outer_closeout_state_v1.py",
    ),
    (
        "ab16_resource_admission_v1",
        f"{RESEARCH_PREFIX}.ab16_resource_admission_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_resource_admission_v1.py",
    ),
    (
        "ab16_outer_refunit_closeout_v1",
        f"{RESEARCH_PREFIX}.ab16_outer_refunit_closeout_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_outer_refunit_closeout_v1.py",
    ),
)


class FormalLoaderError(RuntimeError):
    """The isolated source closure or its authority replay failed closed."""


@dataclass(frozen=True)
class LoadedRole:
    context: dict[str, object]
    module: ModuleType
    role: str


def _closed(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise FormalLoaderError(f"{label} field set drifted")
    return dict(value)


def _reject_none(value: object, label: str) -> None:
    if value is None:
        raise FormalLoaderError(f"{label} contains an unproved null")
    children = value.items() if type(value) is dict else enumerate(value) if type(value) is list else ()
    for key, item in children:
        _reject_none(item, f"{label}.{key}")


def _identity(value: object, label: str) -> dict[str, object]:
    record = _closed(value, frozenset({"path", "sha256", "size_bytes"}), label)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise FormalLoaderError(f"{label} is malformed")
    return record


def _mode_identity(value: object, label: str) -> dict[str, object]:
    record = _closed(
        value,
        frozenset({"mode", "path", "sha256", "size_bytes"}),
        label,
    )
    projected = _identity(
        {name: record[name] for name in ("path", "sha256", "size_bytes")},
        label,
    )
    if (
        type(record["mode"]) is not int
        or record["mode"] < 0
        or record["mode"] & ~0o7777
    ):
        raise FormalLoaderError(f"{label} mode is malformed")
    return {"mode": record["mode"], **projected}


def _parse_mode_identity_argument(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not str or not value:
        raise FormalLoaderError(f"{label} identity argument is absent")

    def pairs_without_duplicates(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise FormalLoaderError(
                    f"{label} identity argument contains a duplicate key"
                )
            result[key] = item
        return result

    try:
        parsed = json.loads(
            value,
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                FormalLoaderError(
                    f"{label} identity contains invalid constant {token}"
                )
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise FormalLoaderError(
            f"{label} identity argument is invalid JSON"
        ) from exc
    canonical = json.dumps(
        parsed,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if canonical != value:
        raise FormalLoaderError(
            f"{label} identity argument is not canonical"
        )
    return _mode_identity(parsed, label)


def _parse_authority_identity(value: object) -> dict[str, object]:
    return _parse_mode_identity_argument(
        value,
        label="package-pinned authority",
    )


def _parse_loader_identity(value: object) -> dict[str, object]:
    return _parse_mode_identity_argument(
        value,
        label="selected formal loader",
    )


def _parse_formal_launch_claim_identity(
    value: object,
) -> dict[str, object]:
    if type(value) is not str or not value:
        raise FormalLoaderError(
            "formal-launch claim identity argument is absent"
        )
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise FormalLoaderError(
            "formal-launch claim identity argument is invalid JSON"
        ) from exc
    canonical = json.dumps(
        parsed,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if (
        canonical != value
        or type(parsed) is not dict
        or set(parsed)
        != {"schema_version", "seal_mask", "sha256", "size_bytes"}
        or parsed["schema_version"]
        != FORMAL_LAUNCH_CLAIM_IDENTITY_SCHEMA
        or type(parsed["seal_mask"]) is not int
        or parsed["seal_mask"] <= 0
        or type(parsed["sha256"]) is not str
        or SHA256_RE.fullmatch(parsed["sha256"]) is None
        or type(parsed["size_bytes"]) is not int
        or parsed["size_bytes"] <= 0
    ):
        raise FormalLoaderError(
            "formal-launch claim identity argument drifted"
        )
    return parsed


def _parse_formal_worker_session(value: object) -> dict[str, object]:
    """Parse the one canonical child-only broker session envelope."""

    if type(value) is not str or not value:
        raise FormalLoaderError("formal worker session argument is absent")

    def pairs_without_duplicates(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise FormalLoaderError(
                    "formal worker session contains a duplicate key"
                )
            result[key] = item
        return result

    try:
        parsed = json.loads(
            value,
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                FormalLoaderError(
                    "formal worker session contains invalid constant "
                    f"{token}"
                )
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise FormalLoaderError(
            "formal worker session argument is invalid JSON"
        ) from exc
    canonical = json.dumps(
        parsed,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if canonical != value:
        raise FormalLoaderError(
            "formal worker session argument is not canonical"
        )
    if (
        type(parsed) is not dict
        or set(parsed) != {"broker_grant", "credential", "schema_version"}
        or parsed["schema_version"] != FORMAL_WORKER_SESSION_SCHEMA
    ):
        raise FormalLoaderError("formal worker session field set drifted")
    return parsed


def _validate_worker_confinement_receipt(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    """Join the selected package backend's complete Landlock receipt.

    The backend validates the live descriptors immediately before it closes
    the worker FD surface and installs Landlock.  The loader must preserve
    that proof instead of accepting a projection which silently drops the
    stdio capabilities that remain writable after confinement.
    """

    receipt = _closed(
        value,
        frozenset(
            {
                "filesystem_write_confinement",
                "retained_read_only_fds",
                "root_or_staging_writable_fd_count",
                "stdio_contract",
            }
        ),
        label,
    )
    stdio = receipt["stdio_contract"]
    if (
        receipt["filesystem_write_confinement"]
        != "landlock-read-only-worker-v1"
        or receipt["retained_read_only_fds"] != []
        or receipt["root_or_staging_writable_fd_count"] != 0
        or type(stdio) is not list
        or len(stdio) != 3
    ):
        raise FormalLoaderError(f"{label} drifted")
    checked_stdio: list[dict[str, object]] = []
    for descriptor, raw in enumerate(stdio):
        record = _closed(
            raw,
            frozenset(
                {
                    "access",
                    "descriptor",
                    "device",
                    "inode",
                    "kind",
                    "mode",
                    "rdev",
                }
            ),
            f"{label}.stdio_contract[{descriptor}]",
        )
        expected_access = "read-only" if descriptor == 0 else {
            "read-write",
            "write-only",
        }
        access = record["access"]
        if (
            record["descriptor"] != descriptor
            or (
                access != expected_access
                if isinstance(expected_access, str)
                else access not in expected_access
            )
            or record["kind"]
            not in {"null-character-device", "pipe", "socket"}
            or any(
                isinstance(record[field], bool)
                or not isinstance(record[field], int)
                or record[field] < 0
                for field in ("device", "inode", "mode", "rdev")
            )
            or cast(int, record["mode"]) & ~0o7777
        ):
            raise FormalLoaderError(
                f"{label}.stdio_contract[{descriptor}] drifted"
            )
        checked_stdio.append(record)
    return {
        "filesystem_write_confinement": (
            "landlock-read-only-worker-v1"
        ),
        "retained_read_only_fds": [],
        "root_or_staging_writable_fd_count": 0,
        "stdio_contract": checked_stdio,
    }


def _formal_selection_argument(
    value: object,
    *,
    required: bool,
) -> Path | None:
    if value is None:
        if required:
            raise FormalLoaderError(
                "budget-bound selected role lacks formal selection"
            )
        return None
    if not required:
        raise FormalLoaderError(
            "non-budget selected role received a formal selection"
        )
    if not isinstance(value, Path) or not value.is_absolute():
        raise FormalLoaderError(
            "budget-bound formal selection is not one absolute path"
        )
    return value


def _role_formal_selection(
    role_argv: list[str],
) -> Path:
    positions = [
        index
        for index, token in enumerate(role_argv)
        if token == "--formal-selection"
    ]
    if (
        len(positions) != 1
        or positions[0] + 1 >= len(role_argv)
        or role_argv[positions[0] + 1].startswith("--")
    ):
        raise FormalLoaderError(
            "formal controller argv lacks one formal selection"
        )
    return Path(role_argv[positions[0] + 1])


def _role_absolute_path_argument(
    role_argv: list[str],
    *,
    option: str,
    label: str,
) -> Path:
    """Select one absolute role argument without accepting aliases."""

    positions = [
        index
        for index, token in enumerate(role_argv)
        if token == option
    ]
    if (
        len(positions) != 1
        or positions[0] + 1 >= len(role_argv)
        or role_argv[positions[0] + 1].startswith("--")
    ):
        raise FormalLoaderError(f"{label} lacks one {option} argument")
    value = Path(role_argv[positions[0] + 1])
    if not value.is_absolute():
        raise FormalLoaderError(f"{label} {option} is not absolute")
    return value


def _close_selected_source_fds() -> None:
    """Close FD3-FD5 exactly once, preserving the first cleanup failure."""

    primary: BaseException | None = None
    for descriptor in (AUTHORITY_FD, LOADER_FD, PYTHON_FD):
        try:
            os.close(descriptor)
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "additional selected source FD cleanup failed: "
                    f"{type(exc).__name__}: {exc}"
                )
    if primary is not None:
        raise primary


def _selected_package_member_bytes(
    *,
    campaign_dir: Path | str,
    descriptor: int,
    expected_identity: object,
    package_name: str,
    maximum_bytes: int,
    required_mode: int = PACKAGE_PAYLOAD_MODE,
    label: str,
) -> tuple[bytes, dict[str, object]]:
    expected = _mode_identity(expected_identity, label)
    expected_path = (
        _resolved(campaign_dir)
        / "campaign-authority"
        / "package"
        / "payload"
        / package_name
    )
    try:
        before = os.fstat(descriptor)
        linked = os.readlink(f"/proc/self/fd/{descriptor}")
    except OSError as exc:
        raise FormalLoaderError(f"{label} retained FD is unavailable") from exc
    if (
        linked.endswith(" (deleted)")
        or _resolved(linked) != expected_path
        or expected["path"] != str(expected_path)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != expected["mode"]
        or expected["mode"] != required_mode
        or before.st_size != expected["size_bytes"]
        or not 0 < before.st_size <= maximum_bytes
    ):
        raise FormalLoaderError(f"{label} retained FD metadata drifted")
    raw = bytearray()
    offset = 0
    while offset < before.st_size:
        block = os.pread(
            descriptor,
            min(1 << 20, before.st_size - offset),
            offset,
        )
        if not block:
            raise FormalLoaderError(f"{label} retained FD ended early")
        raw.extend(block)
        offset += len(block)
    if os.pread(descriptor, 1, offset):
        raise FormalLoaderError(f"{label} retained FD grew during replay")
    after = os.fstat(descriptor)
    named = os.stat(expected_path, follow_symlinks=False)
    stable = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if (
        any(getattr(before, field) != getattr(after, field) for field in stable)
        or (named.st_dev, named.st_ino) != (before.st_dev, before.st_ino)
        or len(raw) != expected["size_bytes"]
        or hashlib.sha256(raw).hexdigest() != expected["sha256"]
    ):
        raise FormalLoaderError(f"{label} retained FD identity drifted")
    return bytes(raw), expected


@dataclass
class SelectedNativeBudgetHelperAuthorization:
    """Exact FD6/FD7 package authorization owned by one selected role call."""

    wrapper_module: ModuleType
    helper: Any
    wrapper_fd: int
    helper_fd: int
    wrapper_identity: dict[str, object]
    helper_identity: dict[str, object]
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            raise FormalLoaderError(
                "selected native-helper authorization cannot close twice"
            )
        self._closed = True
        primary: BaseException | None = None
        for descriptor in (self.helper_fd, self.wrapper_fd):
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        "additional native-helper FD close failure: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary is not None:
            raise primary


def load_selected_native_budget_helper_from_fds(
    *,
    campaign_dir: Path | str,
    wrapper_identity: object,
    helper_identity: object,
    wrapper_fd: int = NATIVE_HELPER_WRAPPER_FD,
    helper_fd: int = NATIVE_HELPER_FD,
) -> SelectedNativeBudgetHelperAuthorization:
    """Replay FD6/FD7 and construct the package-pinned worker-side helper."""

    if (
        wrapper_fd != NATIVE_HELPER_WRAPPER_FD
        or helper_fd != NATIVE_HELPER_FD
        or wrapper_fd == helper_fd
    ):
        raise FormalLoaderError(
            "native helper must arrive on fixed FDs 6 and 7"
        )
    wrapper_raw, checked_wrapper = _selected_package_member_bytes(
        campaign_dir=campaign_dir,
        descriptor=wrapper_fd,
        expected_identity=wrapper_identity,
        package_name="tool.ab16_native_budget_helper_v1.py",
        maximum_bytes=MAX_NATIVE_HELPER_WRAPPER_BYTES,
        label="package-pinned native-helper wrapper",
    )
    _helper_raw, checked_helper = _selected_package_member_bytes(
        campaign_dir=campaign_dir,
        descriptor=helper_fd,
        expected_identity=helper_identity,
        package_name="system.native_budget_helper.bin",
        maximum_bytes=MAX_NATIVE_HELPER_BYTES,
        required_mode=0o555,
        label="package-pinned native-helper binary",
    )
    module = ModuleType("_ab16_selected_native_budget_helper_v1")
    module.__file__ = f"/proc/self/fd/{wrapper_fd}"
    module.__package__ = None
    try:
        exec(
            compile(
                wrapper_raw,
                module.__file__,
                "exec",
                dont_inherit=True,
            ),
            module.__dict__,
            module.__dict__,
        )
        expected_package_identity = module.expected_package_identity()
        if (
            expected_package_identity["package_path"]
            != "payload/system.native_budget_helper.bin"
            or expected_package_identity["wrapper_package_path"]
            != "payload/tool.ab16_native_budget_helper_v1.py"
            or expected_package_identity["sha256"]
            != checked_helper["sha256"]
            or expected_package_identity["size_bytes"]
            != checked_helper["size_bytes"]
        ):
            raise FormalLoaderError(
                "package-pinned native-helper wrapper/binary join drifted"
            )
        module.__dict__.pop("build_shared_object", None)
        module.__dict__.pop("subprocess", None)
        helper = module.NativeBudgetHelper(
            helper_fd,
            expected_identity=expected_package_identity,
        )
    except BaseException:
        raise
    return SelectedNativeBudgetHelperAuthorization(
        wrapper_module=module,
        helper=helper,
        wrapper_fd=wrapper_fd,
        helper_fd=helper_fd,
        wrapper_identity=checked_wrapper,
        helper_identity=checked_helper,
    )


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolved(value: str | os.PathLike[str]) -> Path:
    return Path(os.path.abspath(os.fspath(value))).resolve(strict=False)


def _checkout_shaped(path: Path) -> bool:
    """Recognize a live checkout without treating the sealed snapshot as one."""

    if not path.is_dir():
        return False
    if (path / ".git").exists():
        return True
    return (
        (path / "PROJECT_LOCK.md").is_file()
        and (path / "src").is_dir()
        and (path / "docs" / "research").is_dir()
    )


def _checkout_ancestor(path: Path) -> Path | None:
    cursor = path if path.is_dir() else path.parent
    for candidate in (cursor, *cursor.parents):
        if _checkout_shaped(candidate):
            return candidate
    return None


def _runtime_prefixes() -> tuple[Path, ...]:
    result: list[Path] = []
    for raw in (
        sys.base_prefix,
        sys.base_exec_prefix,
        sys.prefix,
        sys.exec_prefix,
    ):
        if type(raw) is not str or not raw:
            continue
        path = _resolved(raw)
        if path not in result:
            result.append(path)
    return tuple(result)


def _live_checkout_origin(path: Path) -> bool:
    checkout = _checkout_ancestor(path)
    if checkout is None:
        return False
    for prefix in _runtime_prefixes():
        if checkout != prefix and _inside(path, prefix) and _inside(prefix, checkout):
            # A pinned interpreter or venv can itself live below a broader
            # Git work tree (for example a home-directory dotfiles repo).
            # Keep that explicit platform TCB, but do not excuse a checkout
            # nested inside the runtime prefix: the nearest checkout would
            # then no longer contain the prefix.
            return False
    return True


def _origin_paths(module: ModuleType) -> list[Path]:
    paths: list[Path] = []
    raw_file = getattr(module, "__file__", None)
    if type(raw_file) is str and raw_file and raw_file not in {"built-in", "frozen"}:
        paths.append(_resolved(raw_file))
    raw_package_path = getattr(module, "__path__", ())
    if raw_package_path is not None:
        try:
            values = list(raw_package_path)
        except TypeError as exc:
            raise FormalLoaderError(f"{module.__name__} has a malformed __path__") from exc
        for value in values:
            if type(value) is not str or not value:
                raise FormalLoaderError(f"{module.__name__} has a malformed __path__ entry")
            paths.append(_resolved(value))
    return paths


def _repository_module(name: str) -> bool:
    return (
        name == "src"
        or name.startswith("src.")
        or name == "docs"
        or name.startswith("docs.")
        or name in {alias for alias, _module, _path in LEGACY_ALIASES}
    )


def _verify_executing_loader(
    expected: dict[str, object],
) -> ModuleType:
    module = sys.modules.get("__main__")
    raw_file = getattr(module, "__file__", None)
    if (
        __name__ != "__main__"
        or not isinstance(module, ModuleType)
        or module.__dict__ is not globals()
        or raw_file != "/proc/self/fd/4"
    ):
        raise FormalLoaderError(
            "selected formal loader did not execute from fixed FD4"
        )
    expected_path = _resolved(str(expected["path"]))
    signature_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    try:
        before = os.fstat(4)
        current = os.stat(expected_path, follow_symlinks=False)
        proc_entry = os.stat(raw_file)
        digest = hashlib.sha256()
        offset = 0
        while offset < before.st_size:
            block = os.pread(4, min(1 << 20, before.st_size - offset), offset)
            if not block:
                raise FormalLoaderError(
                    "selected formal loader FD4 ended early"
                )
            digest.update(block)
            offset += len(block)
        if os.pread(4, 1, offset):
            raise FormalLoaderError("selected formal loader FD4 grew during replay")
        after = os.fstat(4)
    except OSError as exc:
        raise FormalLoaderError(
            "selected formal loader FD4 could not be replayed"
        ) from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != expected["mode"]
        or before.st_size != expected["size_bytes"]
        or digest.hexdigest() != expected["sha256"]
        or any(
            getattr(before, field) != getattr(after, field)
            for field in signature_fields
        )
        or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
        or (proc_entry.st_dev, proc_entry.st_ino)
        != (before.st_dev, before.st_ino)
    ):
        raise FormalLoaderError(
            "selected formal loader FD4 identity drifted"
        )
    return module


def _reject_ambient_modules(
    spec: RoleSpec,
    authority_module: ModuleType,
    *,
    executing_loader_module: ModuleType | None = None,
) -> None:
    if executing_loader_module is not None:
        loader_globals = executing_loader_module.__dict__
        if (
            sys.modules.get("__main__") is not executing_loader_module
            or loader_globals is not globals()
            or loader_globals.get("__name__") != "__main__"
            or loader_globals.get("__file__") != "/proc/self/fd/4"
        ):
            raise FormalLoaderError(
                "verified executing loader module or globals drifted"
            )
    forbidden = [
        name
        for name in sys.modules
        if name == "src"
        or name.startswith("src.")
        or name == "docs"
        or name.startswith("docs.")
        or name in {alias for alias, _module, _path in LEGACY_ALIASES}
        or name == spec.module_name
        or name.startswith(spec.module_name + ".")
    ]
    if forbidden:
        raise FormalLoaderError(f"ambient/preloaded repository modules are forbidden: {sorted(forbidden)}")
    for name, module in list(sys.modules.items()):
        if not isinstance(module, ModuleType):
            continue
        if module is authority_module:
            continue
        if name == "__main__" and module is executing_loader_module:
            # The first-stage selected-byte literal has already verified FD4,
            # and _verify_executing_loader independently joins that exact FD,
            # path and identity.  No alias or replacement __main__ receives
            # this exemption.
            continue
        for origin in _origin_paths(module):
            if _live_checkout_origin(origin):
                raise FormalLoaderError(f"preloaded module {name} came from a live checkout")


def _platform_paths(snapshot_root: Path) -> list[str]:
    result: list[str] = []
    seen: set[Path] = set()
    for raw in sys.path:
        if type(raw) is not str or not raw:
            raise FormalLoaderError("isolated sys.path contains cwd/relative injection")
        path = _resolved(raw)
        if path == snapshot_root:
            continue
        if not path.is_absolute():
            raise FormalLoaderError("isolated sys.path contains a non-absolute entry")
        if _live_checkout_origin(path):
            raise FormalLoaderError(f"checkout-shaped import path is forbidden: {path}")
        if path not in seen:
            seen.add(path)
            result.append(str(path))
    return result


def _validate_context(value: object, *, campaign_dir: Path, role: str, spec: RoleSpec) -> dict[str, object]:
    record = _closed(value, LOADER_CONTEXT_FIELDS, "formal loader replay context")
    if (
        record["schema_version"] != LOADER_CONTEXT_SCHEMA
        or record["status"] != "PASS"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["role"] != role
        or record["role_module"] != spec.module_name
        or record["campaign_dir"] != str(campaign_dir)
        or type(record["package_id"]) is not str
        or SHA256_RE.fullmatch(record["package_id"]) is None
        or type(record["repository_head"]) is not str
        or HEAD_RE.fullmatch(record["repository_head"]) is None
        or type(record["repository_tree"]) is not str
        or HEAD_RE.fullmatch(record["repository_tree"]) is None
        or type(record["snapshot_root"]) is not str
        or not Path(record["snapshot_root"]).is_absolute()
    ):
        raise FormalLoaderError("formal loader replay context scalar drifted")
    result = dict(record)
    for field in (
        "campaign_root_identity",
        "package_manifest_identity",
        "package_seal_identity",
        "role_source_identity",
        "snapshot_materialization_identity",
    ):
        result[field] = _identity(record[field], f"formal loader {field}")
    _reject_none(record, "formal loader replay context")
    snapshot_root = _resolved(record["snapshot_root"])
    source = _resolved(result["role_source_identity"]["path"])
    expected_source = snapshot_root / spec.source_path
    if source != expected_source or not _inside(source, snapshot_root):
        raise FormalLoaderError("formal role source escaped the verified snapshot")
    result["snapshot_root"] = str(snapshot_root)
    return result


def replay_loader_context(
    authority_module: ModuleType,
    *,
    campaign_dir: Path | str,
    role: str,
) -> dict[str, object]:
    """Call the package owner; absence is a hard authorization failure."""

    spec = ROLE_MAP.get(role)
    if spec is None:
        raise FormalLoaderError(f"unknown formal loader role: {role}")
    directory = _resolved(campaign_dir)
    replay = getattr(authority_module, "replay_loader_context", None)
    if not callable(replay):
        raise FormalLoaderError(
            "ab16_authority_v2.replay_loader_context is unavailable; "
            "isolated formal execution remains unauthorized"
        )
    try:
        raw = replay(
            campaign_dir=directory,
            role=role,
            role_module=spec.module_name,
            role_path=spec.source_path,
        )
    except Exception as exc:
        raise FormalLoaderError(f"authority-owned loader replay failed: {exc}") from exc
    return _validate_context(raw, campaign_dir=directory, role=role, spec=spec)


def _verify_file_with_authority(
    authority_module: ModuleType,
    path: Path,
    expected: dict[str, object],
) -> None:
    snapshot_regular = getattr(authority_module, "snapshot_regular", None)
    detached_identity = getattr(authority_module, "detached_identity", None)
    if not callable(snapshot_regular) or not callable(detached_identity):
        raise FormalLoaderError("authority snapshot identity API is unavailable")
    try:
        observed = detached_identity(snapshot_regular(path))
    except Exception as exc:
        raise FormalLoaderError(f"formal role source replay failed: {exc}") from exc
    if observed != expected:
        raise FormalLoaderError("formal role source identity drifted after loader replay")


def _verify_module_origin(module: ModuleType, *, expected: Path, snapshot_root: Path) -> None:
    origins = _origin_paths(module)
    raw_file = getattr(module, "__file__", None)
    if type(raw_file) is not str or _resolved(raw_file) != expected:
        raise FormalLoaderError(f"{module.__name__} did not originate at its fixed snapshot path")
    if not origins or any(not _inside(origin, snapshot_root) for origin in origins):
        raise FormalLoaderError(f"{module.__name__} escaped the verified snapshot")
    cached = getattr(module, "__cached__", None)
    module_spec = getattr(module, "__spec__", None)
    spec_cached = getattr(module_spec, "cached", None)
    if cached is None and spec_cached is None:
        return
    expected_cached = os.path.abspath(cache_from_source(str(expected)))
    if (
        (cached is not None and (type(cached) is not str or cached != expected_cached))
        or spec_cached != expected_cached
        or not _inside(_resolved(expected_cached), snapshot_root)
    ):
        raise FormalLoaderError(
            f"{module.__name__} exposed noncanonical bytecode cache metadata"
        )
    try:
        os.lstat(expected_cached)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise FormalLoaderError(
            f"{module.__name__} bytecode cache absence could not be proved"
        ) from exc
    else:
        raise FormalLoaderError(
            f"{module.__name__} unexpectedly materialized bytecode cache state"
        )
    setattr(module, "__cached__", None)
    if getattr(module, "__cached__", None) is not None:
        raise FormalLoaderError(
            f"{module.__name__} bytecode cache metadata could not be cleared"
        )


def _prepare_legacy_aliases(snapshot_root: Path, authority_module: ModuleType) -> None:
    """Bridge existing bare AB16 imports without another finder or source copy."""

    research_package = importlib.import_module(RESEARCH_PREFIX)
    for alias, module_name, relative in LEGACY_ALIASES:
        if alias in sys.modules:
            raise FormalLoaderError(f"ambient legacy alias is forbidden: {alias}")
        if alias == "ab16_authority_v2":
            module = authority_module
            sys.modules[module_name] = module
            setattr(research_package, "ab16_authority_v2", module)
        else:
            module = importlib.import_module(module_name)
            _verify_module_origin(
                module,
                expected=snapshot_root / relative,
                snapshot_root=snapshot_root,
            )
        sys.modules[alias] = module


def _verify_import_closure(
    before: set[str],
    snapshot_root: Path,
    target: ModuleType,
    spec: RoleSpec,
    authority_module: ModuleType,
) -> None:
    _verify_module_origin(
        target,
        expected=snapshot_root / spec.source_path,
        snapshot_root=snapshot_root,
    )
    for name in sorted(set(sys.modules) - before):
        module = sys.modules.get(name)
        if not isinstance(module, ModuleType):
            continue
        if module is authority_module:
            # FD5 is the separately verified sealed package authority.  Its
            # canonical and legacy aliases do not turn it into snapshot source.
            continue
        origins = _origin_paths(module)
        if _repository_module(name):
            if not origins or any(not _inside(origin, snapshot_root) for origin in origins):
                raise FormalLoaderError(f"repository module escaped snapshot root: {name}")
        for origin in origins:
            if _inside(origin, snapshot_root):
                continue
            if _live_checkout_origin(origin):
                raise FormalLoaderError(f"new module {name} originated in a live checkout")


def load_verified_role(
    authority_module: ModuleType,
    *,
    campaign_dir: Path | str,
    role: str,
    executing_loader_module: ModuleType | None = None,
) -> LoadedRole:
    """Replay, isolate and import one role through ordinary ``PathFinder``."""

    if sys.flags.isolated != 1 or sys.dont_write_bytecode is not True:
        raise FormalLoaderError("formal loader requires one coherent CPython invocation with -I -B")
    spec = ROLE_MAP.get(role)
    if spec is None:
        raise FormalLoaderError(f"unknown formal loader role: {role}")
    _reject_ambient_modules(
        spec,
        authority_module,
        executing_loader_module=executing_loader_module,
    )
    context = replay_loader_context(authority_module, campaign_dir=campaign_dir, role=role)
    snapshot_root = _resolved(cast(str, context["snapshot_root"]))
    expected_source = snapshot_root / spec.source_path
    _verify_file_with_authority(
        authority_module,
        expected_source,
        cast(dict[str, object], context["role_source_identity"]),
    )
    platform_paths = _platform_paths(snapshot_root)
    previous_path = list(sys.path)
    previous_meta_path = list(sys.meta_path)
    previous_cwd = Path.cwd()
    before = set(sys.modules)
    try:
        sys.path[:] = [str(snapshot_root), *platform_paths]
        sys.meta_path[:] = [BuiltinImporter, FrozenImporter, PathFinder]
        sys.path_importer_cache.clear()
        importlib.invalidate_caches()
        os.chdir(snapshot_root)
        _prepare_legacy_aliases(snapshot_root, authority_module)
        module = importlib.import_module(spec.module_name)
        _verify_import_closure(
            before,
            snapshot_root,
            module,
            spec,
            authority_module,
        )
    except BaseException:
        os.chdir(previous_cwd)
        sys.path[:] = previous_path
        sys.meta_path[:] = previous_meta_path
        sys.path_importer_cache.clear()
        importlib.invalidate_caches()
        raise
    return LoadedRole(context=context, module=module, role=role)


def role_source_digest(path: Path | str) -> str:
    """Small diagnostic helper; authority replay remains the identity owner."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while block := source.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def load_selected_authority_from_fd(
    *,
    campaign_dir: Path | str,
    expected_identity: object,
    descriptor: int = AUTHORITY_FD,
) -> ModuleType:
    """Load FD5 after the versioned selected-FD literal verifies its cohort.

    The prospective literal validates FD3 Python, FD4 loader, FD5 authority,
    FD6 native-helper wrapper, FD7 native-helper binary and FD8 broker socket
    before ``execve``.  This second stage replays FD5 from the same inherited
    descriptor and requires its pathname to be the sealed package payload
    role.  Historical three-FD roots remain governed only by their own pinned
    loader bytes.
    """

    if descriptor != AUTHORITY_FD:
        raise FormalLoaderError("formal authority must arrive on fixed FD5")
    expected = _mode_identity(
        expected_identity,
        "package-pinned authority",
    )
    campaign = _resolved(campaign_dir)
    expected_path = (
        campaign
        / "campaign-authority"
        / "package"
        / "payload"
        / "tool.ab16_authority_v2.py"
    )
    try:
        before = os.fstat(descriptor)
        linked = os.readlink(f"/proc/self/fd/{descriptor}")
    except OSError as exc:
        raise FormalLoaderError("package-pinned authority FD5 is unavailable") from exc
    if (
        linked.endswith(" (deleted)")
        or _resolved(linked) != expected_path
        or expected["path"] != str(expected_path)
    ):
        raise FormalLoaderError("package-pinned authority FD5 path drifted")
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != expected["mode"]
        or expected["mode"] != PACKAGE_PAYLOAD_MODE
        or before.st_size != expected["size_bytes"]
        or before.st_size <= 0
        or before.st_size > MAX_AUTHORITY_BYTES
    ):
        raise FormalLoaderError("package-pinned authority FD5 metadata drifted")
    signature_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = before.st_size
    while remaining:
        block = os.read(descriptor, min(1 << 20, remaining))
        if not block:
            raise FormalLoaderError("package-pinned authority FD5 ended early")
        chunks.append(block)
        remaining -= len(block)
    if os.read(descriptor, 1):
        raise FormalLoaderError("package-pinned authority FD5 grew during replay")
    after = os.fstat(descriptor)
    current = os.stat(expected_path, follow_symlinks=False)
    if (
        any(getattr(before, field) != getattr(after, field) for field in signature_fields)
        or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
    ):
        raise FormalLoaderError("package-pinned authority FD5 changed during replay")
    raw = b"".join(chunks)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected["sha256"]:
        raise FormalLoaderError("package-pinned authority FD5 digest drifted")
    name = f"_ab16_formal_selected_authority_{digest[:16]}"
    module = ModuleType(name)
    module.__file__ = str(expected_path)
    module.__package__ = None
    sys.modules[name] = module
    try:
        code = compile(raw, str(expected_path), "exec", dont_inherit=True)
        exec(code, module.__dict__, module.__dict__)
    except BaseException as exc:
        sys.modules.pop(name, None)
        raise FormalLoaderError("package-pinned authority FD5 execution failed") from exc
    for required in (
        "detached_identity",
        "replay_loader_context",
        "snapshot_regular",
    ):
        if not callable(getattr(module, required, None)):
            sys.modules.pop(name, None)
            raise FormalLoaderError(f"package-pinned authority lacks {required}")
    return module


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-fd", type=int, required=True)
    parser.add_argument("--authority-identity", required=True)
    parser.add_argument("--loader-identity", required=True)
    parser.add_argument("--native-helper-wrapper-fd", type=int, required=True)
    parser.add_argument(
        "--native-helper-wrapper-identity",
        required=True,
    )
    parser.add_argument("--native-helper-fd", type=int, required=True)
    parser.add_argument("--native-helper-identity", required=True)
    parser.add_argument("--budget-broker-fd", type=int, required=True)
    parser.add_argument("--formal-launch-claim-fd", type=int)
    parser.add_argument("--formal-launch-claim-identity")
    parser.add_argument("--formal-supervisor-session-fd", type=int)
    parser.add_argument("--formal-selection-for-budget", type=Path)
    parser.add_argument("--formal-worker-session-json")
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--role", choices=tuple(ROLE_MAP), required=True)
    parser.add_argument("role_argv", nargs=argparse.REMAINDER)
    return parser


def _consume_formal_supervisor_session(
    descriptor: int,
) -> dict[str, object]:
    """Consume the private owner-to-selected-child pipe exactly once."""

    def pairs_without_duplicates(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise FormalLoaderError(
                    "formal supervisor session contains a duplicate key"
                )
            result[key] = item
        return result

    if descriptor != FORMAL_SUPERVISOR_SESSION_FD:
        raise FormalLoaderError(
            "formal supervisor session must arrive on fixed FD10"
        )
    chunks: list[bytes] = []
    size = 0
    try:
        while True:
            block = os.read(
                descriptor,
                min(
                    64 * 1024,
                    MAX_FORMAL_SUPERVISOR_SESSION_BYTES + 1 - size,
                ),
            )
            if not block:
                break
            chunks.append(block)
            size += len(block)
            if size > MAX_FORMAL_SUPERVISOR_SESSION_BYTES:
                raise FormalLoaderError(
                    "formal supervisor session is oversized"
                )
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if not raw:
        raise FormalLoaderError("formal supervisor session is absent")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                FormalLoaderError(
                    "formal supervisor session contains invalid constant "
                    f"{token}"
                )
            ),
        )
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise FormalLoaderError(
            "formal supervisor session is not strict JSON"
        ) from exc
    if (
        type(value) is not dict
        or json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        != raw
    ):
        raise FormalLoaderError(
            "formal supervisor session is not one canonical object"
        )
    return cast(dict[str, object], value)


def main(argv: list[str] | None = None) -> int:
    """Load one selected role and preserve only its explicit integer exit."""

    args = _parser().parse_args(argv)
    role_argv = list(args.role_argv)
    if role_argv[:1] == ["--"]:
        role_argv = role_argv[1:]
    native_authorization: SelectedNativeBudgetHelperAuthorization | None = None
    native_fds_owned = False
    budget_backend: object | None = None
    broker_fd_owned = False
    claim_fd_owned = False
    supervisor_session_fd_owned = False
    supervisor_session: dict[str, object] | None = None
    selected_source_fds_owned = True
    primary: BaseException | None = None
    try:
        loader_identity = _parse_loader_identity(args.loader_identity)
        executing_loader_module = _verify_executing_loader(loader_identity)
        authority_identity = _parse_authority_identity(args.authority_identity)
        authority_module = load_selected_authority_from_fd(
            campaign_dir=args.campaign_dir,
            descriptor=args.authority_fd,
            expected_identity=authority_identity,
        )
        if (
            args.native_helper_wrapper_fd != NATIVE_HELPER_WRAPPER_FD
            or args.native_helper_fd != NATIVE_HELPER_FD
        ):
            raise FormalLoaderError(
                "native helper must arrive on fixed FDs 6 and 7"
            )
        native_fds_owned = True
        wrapper_identity = _parse_mode_identity_argument(
            args.native_helper_wrapper_identity,
            label="package-pinned native-helper wrapper",
        )
        helper_identity = _parse_mode_identity_argument(
            args.native_helper_identity,
            label="package-pinned native-helper binary",
        )
        if args.budget_broker_fd != BUDGET_BROKER_FD:
            raise FormalLoaderError(
                "formal budget broker must arrive on fixed FD8"
            )
        broker_fd_owned = True
        claim_identity: dict[str, object] | None = None
        if args.role == "formal-orchestrator":
            if args.formal_launch_claim_fd != FORMAL_LAUNCH_CLAIM_FD:
                raise FormalLoaderError(
                    "formal orchestrator claim must arrive on fixed FD9"
                )
            claim_fd_owned = True
            claim_identity = _parse_formal_launch_claim_identity(
                args.formal_launch_claim_identity
            )
            if args.formal_supervisor_session_fd is not None:
                raise FormalLoaderError(
                    "formal orchestrator received a supervisor session"
                )
        elif args.role == "formal-supervisor":
            if (
                args.formal_launch_claim_fd is not None
                or args.formal_launch_claim_identity is not None
                or args.formal_supervisor_session_fd
                != FORMAL_SUPERVISOR_SESSION_FD
            ):
                raise FormalLoaderError(
                    "formal supervisor fixed session transport drifted"
                )
            supervisor_session_fd_owned = True
            supervisor_session = _consume_formal_supervisor_session(
                args.formal_supervisor_session_fd
            )
            supervisor_session_fd_owned = False
        elif (
            args.formal_launch_claim_fd is not None
            or args.formal_launch_claim_identity is not None
            or args.formal_supervisor_session_fd is not None
        ):
            raise FormalLoaderError(
                "selected role received an unauthorized owner session"
            )
        try:
            broker_socket = socket.socket(fileno=args.budget_broker_fd)
        except OSError as exc:
            raise FormalLoaderError(
                "formal budget broker FD8 is not a socket"
            ) from exc
        try:
            if broker_socket.family != socket.AF_UNIX:
                raise FormalLoaderError(
                    "formal budget broker FD8 is not one UNIX socket"
                )
        finally:
            broker_socket.detach()
        native_authorization = load_selected_native_budget_helper_from_fds(
            campaign_dir=args.campaign_dir,
            wrapper_fd=args.native_helper_wrapper_fd,
            wrapper_identity=wrapper_identity,
            helper_fd=args.native_helper_fd,
            helper_identity=helper_identity,
        )
        native_fds_owned = False
        selected = load_verified_role(
            authority_module,
            campaign_dir=args.campaign_dir,
            role=args.role,
            executing_loader_module=executing_loader_module,
        )
        entrypoint = getattr(selected.module, "main", None)
        if not callable(entrypoint):
            raise FormalLoaderError(f"selected role has no callable main: {args.role}")
        selected_argv = [*ROLE_MAP[args.role].argv_prefix, *role_argv]
        formal_selection_bound = (
            args.role == "formal-controller"
            or args.role in BUDGET_BOUND_WORKER_ROLES
        )
        formal_selection = _formal_selection_argument(
            args.formal_selection_for_budget,
            required=formal_selection_bound,
        )
        if args.role == "formal-orchestrator":
            assert claim_identity is not None
            factory = getattr(
                selected.module,
                "formal_launch_claim_transport_from_fds",
                None,
            )
            if not callable(factory):
                raise FormalLoaderError(
                    "formal orchestrator lacks its claim transport factory"
                )
            broker_fd_owned = False
            transport = factory(
                broker_descriptor=args.budget_broker_fd,
                claim_descriptor=FORMAL_LAUNCH_CLAIM_FD,
                claim_identity=claim_identity,
                native_helper=native_authorization.helper,
            )
            authorization_to_close = native_authorization
            native_authorization = None
            authorization_to_close.close()
            selected_source_fds_owned = False
            _close_selected_source_fds()
            result = entrypoint(
                selected_argv,
                claim_transport=transport,
            )
        elif args.role == "formal-supervisor":
            assert supervisor_session is not None
            factory = getattr(
                selected.module,
                "formal_supervisor_capabilities_from_fd",
                None,
            )
            if not callable(factory):
                raise FormalLoaderError(
                    "formal supervisor lacks its capability factory"
                )
            broker_fd_owned = False
            capabilities = factory(
                args.budget_broker_fd,
                native_budget_helper=native_authorization.helper,
                campaign_dir=args.campaign_dir,
                supervisor_session=supervisor_session,
            )
            budget_backend = getattr(
                capabilities,
                "budget_backend",
                None,
            )
            if budget_backend is None:
                raise FormalLoaderError(
                    "formal supervisor capability backend is absent"
                )
            authorization_to_close = native_authorization
            native_authorization = None
            authorization_to_close.close()
            selected_source_fds_owned = False
            _close_selected_source_fds()
            result = entrypoint(
                selected_argv,
                formal_supervisor_capabilities=capabilities,
            )
        elif args.role == "formal-controller":
            assert formal_selection is not None
            if _role_formal_selection(selected_argv) != formal_selection:
                raise FormalLoaderError(
                    "formal controller selection arguments disagree"
                )
            if args.formal_worker_session_json is not None:
                raise FormalLoaderError(
                    "formal controller received a child worker session"
                )
            factory = getattr(
                selected.module,
                "formal_budget_backend_from_fd",
                None,
            )
            if not callable(factory):
                raise FormalLoaderError(
                    "formal controller lacks its budget backend factory"
                )
            broker_fd_owned = False
            budget_backend = factory(
                args.budget_broker_fd,
                native_budget_helper=native_authorization.helper,
                campaign_dir=args.campaign_dir,
                formal_selection=formal_selection,
            )
            native_helper = native_authorization.helper
            authorization_to_close = native_authorization
            native_authorization = None
            authorization_to_close.close()
            selected_source_fds_owned = False
            _close_selected_source_fds()
            result = entrypoint(
                selected_argv,
                native_budget_helper=native_helper,
                formal_budget_backend=budget_backend,
            )
        elif args.role in BUDGET_BOUND_WORKER_ROLES:
            assert formal_selection is not None
            worker_session = _parse_formal_worker_session(
                args.formal_worker_session_json
            )
            factory = getattr(
                selected.module,
                "formal_worker_budget_backend_from_fd",
                None,
            )
            if not callable(factory):
                raise FormalLoaderError(
                    "formal worker lacks its budget backend factory"
                )
            broker_fd_owned = False
            budget_backend = factory(
                args.budget_broker_fd,
                native_budget_helper=native_authorization.helper,
                campaign_dir=args.campaign_dir,
                formal_selection=formal_selection,
                worker_role=args.role,
                worker_session=worker_session,
            )
            authorization_to_close = native_authorization
            native_authorization = None
            authorization_to_close.close()
            selected_source_fds_owned = False
            _close_selected_source_fds()
            install = getattr(
                budget_backend,
                "install_worker_confinement",
                None,
            )
            if not callable(install):
                raise FormalLoaderError(
                    "formal worker lacks its mandatory Landlock installer"
                )
            _validate_worker_confinement_receipt(
                install(()),
                label="formal worker Landlock receipt",
            )
            worker_keywords: dict[str, object] = {
                "budget_backend": budget_backend,
            }
            if args.role in {"baseline-admission", "baseline-rebuild"}:
                worker_keywords["prospective"] = True
            result = entrypoint(selected_argv, **worker_keywords)
        elif args.role == FORMAL_ARM_SUPERVISOR_ROLE:
            if args.formal_worker_session_json is not None:
                raise FormalLoaderError(
                    "formal arm supervisor received a child worker session"
                )
            pre_run_path = _role_absolute_path_argument(
                role_argv,
                option="--pre-run",
                label="formal arm supervisor",
            )
            selection_path = _role_absolute_path_argument(
                role_argv,
                option="--selection",
                label="formal arm supervisor",
            )
            factory = getattr(
                selected.module,
                "formal_arm_supervisor_budget_backend_from_fd",
                None,
            )
            if not callable(factory):
                raise FormalLoaderError(
                    "formal arm supervisor lacks its budget backend factory"
                )
            broker_fd_owned = False
            budget_backend = factory(
                args.budget_broker_fd,
                native_budget_helper=native_authorization.helper,
                campaign_dir=args.campaign_dir,
                pre_run_path=pre_run_path,
                selection_path=selection_path,
            )
            result = entrypoint(
                selected_argv,
                formal_budget_backend=budget_backend,
                native_budget_helper=native_authorization.helper,
                selected_source_fds=(
                    PYTHON_FD,
                    LOADER_FD,
                    AUTHORITY_FD,
                    NATIVE_HELPER_WRAPPER_FD,
                    NATIVE_HELPER_FD,
                ),
            )
        elif args.role == FORMAL_ARM_WORKER_ROLE:
            pre_run_path = _role_absolute_path_argument(
                role_argv,
                option="--pre-run",
                label="formal arm worker",
            )
            selection_path = _role_absolute_path_argument(
                role_argv,
                option="--selection",
                label="formal arm worker",
            )
            worker_session = _parse_formal_worker_session(
                args.formal_worker_session_json
            )
            factory = getattr(
                selected.module,
                "formal_arm_worker_budget_backend_from_fd",
                None,
            )
            if not callable(factory):
                raise FormalLoaderError(
                    "formal arm worker lacks its budget backend factory"
                )
            broker_fd_owned = False
            budget_backend = factory(
                args.budget_broker_fd,
                native_budget_helper=native_authorization.helper,
                campaign_dir=args.campaign_dir,
                pre_run_path=pre_run_path,
                selection_path=selection_path,
                worker_session=worker_session,
            )
            authorization_to_close = native_authorization
            native_authorization = None
            authorization_to_close.close()
            selected_source_fds_owned = False
            _close_selected_source_fds()
            install = getattr(
                budget_backend,
                "install_worker_confinement",
                None,
            )
            if not callable(install):
                raise FormalLoaderError(
                    "formal arm worker lacks its mandatory Landlock installer"
                )
            _validate_worker_confinement_receipt(
                install(()),
                label="formal arm worker Landlock receipt",
            )
            result = entrypoint(
                selected_argv,
                budget_backend=budget_backend,
            )
        else:
            if args.formal_worker_session_json is not None:
                raise FormalLoaderError(
                    "non-worker selected role received a worker session"
                )
            broker_fd_owned = False
            os.close(args.budget_broker_fd)
            authorization_to_close = native_authorization
            native_authorization = None
            authorization_to_close.close()
            selected_source_fds_owned = False
            _close_selected_source_fds()
            result = entrypoint(selected_argv)
        if type(result) is not int or not 0 <= result <= 255:
            raise FormalLoaderError("selected role returned a non-exit-code value")
        return result
    except SystemExit as exc:
        primary = exc
        if type(exc.code) is int and 0 <= exc.code <= 255:
            return exc.code
        print(f"FAIL_CLOSED: selected role raised invalid SystemExit: {exc.code!r}", file=sys.stderr)
        return 125
    except BaseException as exc:
        primary = exc
        print(f"FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 125
    finally:
        cleanup_primary = primary
        if supervisor_session_fd_owned:
            try:
                os.close(FORMAL_SUPERVISOR_SESSION_FD)
            except BaseException as close_exc:
                if cleanup_primary is not None:
                    cleanup_primary.add_note(
                        "formal supervisor session FD cleanup failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                else:
                    raise
        if budget_backend is not None:
            try:
                close_backend = getattr(budget_backend, "close", None)
                if not callable(close_backend):
                    raise FormalLoaderError(
                        "selected budget backend lacks close"
                    )
                close_backend()
            except BaseException as close_exc:
                if cleanup_primary is not None:
                    cleanup_primary.add_note(
                        "selected budget backend cleanup failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                else:
                    cleanup_primary = close_exc
        elif broker_fd_owned:
            try:
                os.close(BUDGET_BROKER_FD)
            except BaseException as close_exc:
                if cleanup_primary is not None:
                    cleanup_primary.add_note(
                        "selected broker raw FD cleanup failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                else:
                    cleanup_primary = close_exc
        if claim_fd_owned:
            claim_fd_owned = False
            try:
                os.close(FORMAL_LAUNCH_CLAIM_FD)
            except BaseException as close_exc:
                if cleanup_primary is not None:
                    cleanup_primary.add_note(
                        "formal-launch claim FD cleanup failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                else:
                    cleanup_primary = close_exc
        if selected_source_fds_owned:
            selected_source_fds_owned = False
            try:
                _close_selected_source_fds()
            except BaseException as close_exc:
                if cleanup_primary is not None:
                    cleanup_primary.add_note(
                        "selected source FD cleanup failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                else:
                    cleanup_primary = close_exc
        if native_authorization is not None:
            try:
                native_authorization.close()
            except BaseException as close_exc:
                if cleanup_primary is not None:
                    cleanup_primary.add_note(
                        "selected native-helper cleanup failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                else:
                    cleanup_primary = close_exc
        elif native_fds_owned:
            close_errors: list[BaseException] = []
            for descriptor in (NATIVE_HELPER_FD, NATIVE_HELPER_WRAPPER_FD):
                try:
                    os.close(descriptor)
                except BaseException as close_exc:
                    close_errors.append(close_exc)
            if close_errors:
                if cleanup_primary is not None:
                    for cleanup_error in close_errors:
                        cleanup_primary.add_note(
                            "selected native-helper raw FD cleanup failed: "
                            f"{type(cleanup_error).__name__}: {cleanup_error}"
                        )
                else:
                    cleanup_primary = close_errors[0]
                    for cleanup_error in close_errors[1:]:
                        cleanup_primary.add_note(
                            "additional selected native-helper raw FD cleanup "
                            f"failed: {type(cleanup_error).__name__}: "
                            f"{cleanup_error}"
                        )
        if primary is None and cleanup_primary is not None:
            raise cleanup_primary


if __name__ == "__main__":
    raise SystemExit(main())
