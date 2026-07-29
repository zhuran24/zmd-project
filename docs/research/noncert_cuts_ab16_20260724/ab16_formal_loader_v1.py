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
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
from typing import Any


LOADER_CONTEXT_SCHEMA = "noncert-cuts-ab16-formal-loader-context-v1"
AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
HEAD_RE = re.compile(r"[0-9a-f]{40}\Z")
AUTHORITY_FD = 5
MAX_AUTHORITY_BYTES = 64 * 1024 * 1024
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


def _parse_authority_identity(value: object) -> dict[str, object]:
    if type(value) is not str or not value:
        raise FormalLoaderError("authority identity argument is absent")

    def pairs_without_duplicates(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise FormalLoaderError(
                    "authority identity argument contains a duplicate key"
                )
            result[key] = item
        return result

    try:
        parsed = json.loads(
            value,
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                FormalLoaderError(
                    f"authority identity contains invalid constant {token}"
                )
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise FormalLoaderError("authority identity argument is invalid JSON") from exc
    canonical = json.dumps(
        parsed,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if canonical != value:
        raise FormalLoaderError("authority identity argument is not canonical")
    return _mode_identity(parsed, "package-pinned authority")


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


def _reject_ambient_modules(spec: RoleSpec, authority_module: ModuleType) -> None:
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
    if cached is not None:
        raise FormalLoaderError(f"{module.__name__} unexpectedly exposed bytecode cache state")


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
) -> LoadedRole:
    """Replay, isolate and import one role through ordinary ``PathFinder``."""

    if sys.flags.isolated != 1 or sys.dont_write_bytecode is not True:
        raise FormalLoaderError("formal loader requires one coherent CPython invocation with -I -B")
    spec = ROLE_MAP.get(role)
    if spec is None:
        raise FormalLoaderError(f"unknown formal loader role: {role}")
    _reject_ambient_modules(spec, authority_module)
    context = replay_loader_context(authority_module, campaign_dir=campaign_dir, role=role)
    snapshot_root = _resolved(context["snapshot_root"])
    expected_source = snapshot_root / spec.source_path
    _verify_file_with_authority(
        authority_module,
        expected_source,
        context["role_source_identity"],
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
    """Load the FD5 authority selected by the fixed three-FD primitive.

    The preceding selected-byte literal validates FD3 Python, FD4 loader and
    FD5 authority against its package-pinned identity JSON before ``execve``.
    This second stage replays FD5 from the same inherited descriptor and
    requires its pathname to be the sealed package payload role.  That
    authority then owns replay of the separately materialized source snapshot.
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
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--role", choices=tuple(ROLE_MAP), required=True)
    parser.add_argument("role_argv", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Load one selected role and preserve only its explicit integer exit."""

    args = _parser().parse_args(argv)
    role_argv = list(args.role_argv)
    if role_argv[:1] == ["--"]:
        role_argv = role_argv[1:]
    try:
        authority_identity = _parse_authority_identity(args.authority_identity)
        authority_module = load_selected_authority_from_fd(
            campaign_dir=args.campaign_dir,
            descriptor=args.authority_fd,
            expected_identity=authority_identity,
        )
        selected = load_verified_role(
            authority_module,
            campaign_dir=args.campaign_dir,
            role=args.role,
        )
        entrypoint = getattr(selected.module, "main", None)
        if not callable(entrypoint):
            raise FormalLoaderError(f"selected role has no callable main: {args.role}")
        result = entrypoint([*ROLE_MAP[args.role].argv_prefix, *role_argv])
        if type(result) is not int or not 0 <= result <= 255:
            raise FormalLoaderError("selected role returned a non-exit-code value")
        return result
    except SystemExit as exc:
        if type(exc.code) is int and 0 <= exc.code <= 255:
            return exc.code
        print(f"FAIL_CLOSED: selected role raised invalid SystemExit: {exc.code!r}", file=sys.stderr)
        return 125
    except BaseException as exc:
        print(f"FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
