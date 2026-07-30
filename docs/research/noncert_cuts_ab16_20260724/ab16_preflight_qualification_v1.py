#!/usr/bin/env python3
"""Run the AB16-only full-preflight qualification surface.

This entry point is loaded through Gate A's retained-FD supervisor.  It
verifies and loads the ordinary preflight, the AB16 collection protocol, and
the AB16 collection plugin from three retained source descriptors.  It then
replaces only the in-memory preflight ``check_tests`` function and invokes the
ordinary ``run_gate(full=True)`` path once.

Nothing here changes the shared developer/full/slow preflight commands.  A
successful invocation only emits the two canonical collection records for
Gate A's separate consumer; it authorizes no campaign, arm, solver, cut, or
certified result.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
from typing import Any, Sequence


_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SUPPORT_ROLES = frozenset({"plugin", "preflight", "protocol"})
_MODULE_NAMES = {
    "plugin": "_ab16_pinned_pytest_collection_plugin_v1",
    "preflight": "_ab16_pinned_preflight_gate",
    "protocol": "_ab16_pinned_pytest_collection_protocol_v1",
}


class AB16PreflightQualificationError(RuntimeError):
    """The isolated AB16 qualification runner failed closed."""


def _absolute(value: Path | str) -> Path:
    path = Path(os.fspath(value))
    if not path.is_absolute():
        raise AB16PreflightQualificationError("qualification path is not absolute")
    return Path(os.path.abspath(path))


def _repository_relative(value: Path) -> Path:
    if value.is_absolute() or not value.parts or any(part in {"", ".", ".."} for part in value.parts):
        raise AB16PreflightQualificationError(
            "qualification repository-relative path is unsafe"
        )
    return value


def _fd_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _snapshot_bound_source(
    *,
    descriptor: int,
    path: Path,
    mode: int,
    size_bytes: int,
    sha256: str,
    role: str,
) -> bytes:
    before = os.fstat(descriptor)
    if (
        descriptor < 3
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != mode
        or before.st_size != size_bytes
    ):
        raise AB16PreflightQualificationError(
            f"qualification support source {role} metadata drifted"
        )
    descriptor_path = Path(f"/proc/{os.getpid()}/fd/{descriptor}")
    if not descriptor_path.exists() or not os.path.samefile(descriptor_path, path):
        raise AB16PreflightQualificationError(
            f"qualification support source {role} path/descriptor join drifted"
        )
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    remaining = size_bytes
    while remaining:
        chunk = os.read(descriptor, min(1 << 20, remaining))
        if not chunk:
            raise AB16PreflightQualificationError(
                f"qualification support source {role} truncated"
            )
        chunks.append(chunk)
        digest.update(chunk)
        remaining -= len(chunk)
    if os.read(descriptor, 1):
        raise AB16PreflightQualificationError(
            f"qualification support source {role} grew during verification"
        )
    after = os.fstat(descriptor)
    raw = b"".join(chunks)
    if (
        _fd_signature(before) != _fd_signature(after)
        or len(raw) != size_bytes
        or digest.hexdigest() != sha256
    ):
        raise AB16PreflightQualificationError(
            f"qualification support source {role} identity drifted"
        )
    return raw


def _support_sources(
    values: Sequence[Sequence[str]],
) -> tuple[dict[str, bytes], dict[str, Path]]:
    descriptors: list[int] = []
    parsed: dict[str, tuple[int, Path, int, int, str]] = {}
    primary: BaseException | None = None
    try:
        for value in values:
            if len(value) != 6:
                raise AB16PreflightQualificationError(
                    "qualification support-source record shape drifted"
                )
            role, raw_descriptor, raw_path, raw_mode, raw_size, sha256 = value
            try:
                descriptor = int(raw_descriptor)
            except ValueError as exc:
                raise AB16PreflightQualificationError(
                    f"qualification support source {role!r} descriptor is malformed"
                ) from exc
            if descriptor < 3:
                raise AB16PreflightQualificationError(
                    f"qualification support source {role!r} descriptor is unsafe"
                )
            descriptors.append(descriptor)
            try:
                mode = int(raw_mode)
                size_bytes = int(raw_size)
            except ValueError as exc:
                raise AB16PreflightQualificationError(
                    f"qualification support source {role!r} numeric field is malformed"
                ) from exc
            path = _absolute(raw_path)
            if (
                role not in _SUPPORT_ROLES
                or role in parsed
                or descriptor < 3
                or mode not in {0o444, 0o555, 0o644, 0o755}
                or size_bytes <= 0
                or _SHA256_RE.fullmatch(sha256) is None
                ):
                raise AB16PreflightQualificationError(
                    "qualification support-source binding is malformed"
                )
            parsed[role] = (descriptor, path, mode, size_bytes, sha256)
        if set(parsed) != _SUPPORT_ROLES or len(set(descriptors)) != len(descriptors):
            raise AB16PreflightQualificationError(
                "qualification support-source role/descriptor set drifted"
            )
        raw_sources = {
            role: _snapshot_bound_source(
                descriptor=binding[0],
                path=binding[1],
                mode=binding[2],
                size_bytes=binding[3],
                sha256=binding[4],
                role=role,
            )
            for role, binding in sorted(parsed.items())
        }
        paths = {role: binding[1] for role, binding in parsed.items()}
        return raw_sources, paths
    except BaseException as exc:
        primary = exc
        raise
    finally:
        close_errors: list[BaseException] = []
        for descriptor in reversed(tuple(dict.fromkeys(descriptors))):
            try:
                os.close(descriptor)
            except BaseException as exc:
                close_errors.append(exc)
        if primary is not None:
            for close_error in close_errors:
                primary.add_note(
                    "qualification support-source cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        elif close_errors:
            raise AB16PreflightQualificationError(
                "qualification support-source descriptor cleanup failed"
            ) from close_errors[0]


def _load_pinned_module(*, role: str, path: Path, raw: bytes) -> ModuleType:
    name = _MODULE_NAMES[role]
    if name in sys.modules:
        raise AB16PreflightQualificationError(
            f"qualification module name is already occupied: {name}"
        )
    module = ModuleType(name)
    namespace = vars(module)
    namespace.update(
        {
            "__builtins__": __builtins__,
            "__cached__": None,
            "__file__": str(path),
            "__loader__": None,
            "__package__": "",
            "__spec__": None,
        }
    )
    sys.modules[name] = module
    try:
        exec(
            compile(raw, str(path), "exec", dont_inherit=True),
            namespace,
            namespace,
        )
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _require_isolated_runtime(repository_root: Path) -> None:
    if (
        sys.flags.isolated != 1
        or sys.flags.dont_write_bytecode != 1
        or os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1"
        or "PYTEST_ADDOPTS" in os.environ
        or "PYTEST_PLUGINS" in os.environ
    ):
        raise AB16PreflightQualificationError(
            "qualification runner lacks its fixed isolated Python/pytest environment"
        )
    runtime_prefixes: set[Path] = set()
    for attribute in ("base_exec_prefix", "base_prefix", "exec_prefix", "prefix"):
        raw_prefix = getattr(sys, attribute, None)
        if type(raw_prefix) is not str or not raw_prefix:
            continue
        for prefix in {
            Path(os.path.abspath(raw_prefix)),
            Path(os.path.realpath(raw_prefix)),
        }:
            if prefix != repository_root:
                runtime_prefixes.add(prefix)
    for raw_entry in sys.path:
        if type(raw_entry) is not str or not raw_entry:
            continue
        for entry in {
            Path(os.path.abspath(raw_entry)),
            Path(os.path.realpath(raw_entry)),
        }:
            try:
                entry.relative_to(repository_root)
            except ValueError:
                continue
            if any(
                entry == prefix or prefix in entry.parents
                for prefix in runtime_prefixes
            ):
                continue
            raise AB16PreflightQualificationError(
                "qualification runner inherited a repository path before explicit pytest collection"
            )


def _pytest_arguments(*, repository_root: Path, basetemp: Path) -> list[str]:
    return [
        "-q",
        "--tb=short",
        "--no-header",
        "-p",
        "randomly",
        "-p",
        "no:cacheprovider",
        "--rootdir",
        str(repository_root),
        "-c",
        str(repository_root / "pytest.ini"),
        "--confcutdir",
        str(repository_root / "src/tests"),
        "--repository-workflow=full",
        "-m",
        "not slow",
        "--basetemp",
        str(basetemp),
        "-o",
        "tmp_path_retention_policy=failed",
        str(repository_root / "src/tests"),
    ]


def _run_qualification(args: argparse.Namespace) -> int:
    repository_root = _absolute(args.repository_root)
    basetemp = _absolute(args.basetemp)
    basetemp_relative = _repository_relative(args.basetemp_relative)
    if basetemp != repository_root / basetemp_relative:
        raise AB16PreflightQualificationError(
            "qualification basetemp absolute/relative binding drifted"
        )
    _require_isolated_runtime(repository_root)
    raw_sources, source_paths = _support_sources(args.support_source)
    declared_source_paths = {
        "plugin": _absolute(args.collection_plugin_source),
        "preflight": _absolute(args.preflight_source),
        "protocol": _absolute(args.collection_protocol_source),
    }
    if source_paths != declared_source_paths:
        raise AB16PreflightQualificationError(
            "qualification support-source CLI/path binding drifted"
        )
    protocol = _load_pinned_module(
        role="protocol",
        path=source_paths["protocol"],
        raw=raw_sources["protocol"],
    )
    plugin_module = _load_pinned_module(
        role="plugin",
        path=source_paths["plugin"],
        raw=raw_sources["plugin"],
    )
    preflight = _load_pinned_module(
        role="preflight",
        path=source_paths["preflight"],
        raw=raw_sources["preflight"],
    )
    session_type = getattr(protocol, "AB16CollectionSession", None)
    plugin_type = getattr(plugin_module, "AB16PytestCollectionPlugin", None)
    run_gate = getattr(preflight, "run_gate", None)
    if not callable(session_type) or not callable(plugin_type) or not callable(run_gate):
        raise AB16PreflightQualificationError(
            "qualification pinned module surface drifted"
        )
    session = session_type.create(
        expected_count=args.expected_count,
        expected_sha256=args.expected_sha256,
    )
    pytest_state: dict[str, object] = {"called": False, "returncode": None}
    primary: BaseException | None = None
    result: int | None = None
    validated: Any | None = None
    original_check_tests: Any | None = None
    check_tests_replaced = False
    try:
        plugin = plugin_type(
            session=session,
            repository_root=repository_root,
            basetemp_root=basetemp,
        )

        def ab16_check_tests(gate: Any, *, full: bool = False) -> None:
            if full is not True or pytest_state["called"] is not False:
                raise AB16PreflightQualificationError(
                    "qualification preflight test hook invocation drifted"
                )
            pytest_state["called"] = True
            import pytest

            returncode = int(
                pytest.main(
                    _pytest_arguments(
                        repository_root=repository_root,
                        basetemp=basetemp,
                    ),
                    plugins=[plugin],
                )
            )
            pytest_state["returncode"] = returncode
            if returncode == 0:
                gate.ok("pytest (AB16 fixed full · serial · not slow): exact PASS")
            else:
                gate.block(
                    "pytest (AB16 fixed full · serial · not slow) "
                    f"failed (exit={returncode})"
                )

        original_check_tests = getattr(preflight, "check_tests", None)
        if not callable(original_check_tests):
            raise AB16PreflightQualificationError(
                "qualification preflight check_tests surface drifted"
            )
        setattr(preflight, "check_tests", ab16_check_tests)
        check_tests_replaced = True
        result = run_gate(full=True)
        if type(result) is not int or pytest_state["called"] is not True:
            raise AB16PreflightQualificationError(
                "qualification preflight terminal state drifted"
            )
        pytest_returncode = pytest_state["returncode"]
        if result == 0:
            if type(pytest_returncode) is not int or pytest_returncode != 0:
                raise AB16PreflightQualificationError(
                    "qualification preflight passed without one pytest PASS"
                )
            validated = session.validate(returncode=pytest_returncode)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if check_tests_replaced:
            setattr(preflight, "check_tests", original_check_tests)
        try:
            session.close()
        except BaseException as close_error:
            if primary is not None:
                primary.add_note(
                    "qualification collection-session cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
            else:
                raise
    assert result is not None
    if result != 0:
        return result
    if validated is None:
        raise AB16PreflightQualificationError(
            "qualification preflight lacks validated collection records"
        )
    stdout_bytes = validated.stdout_bytes()
    sys.stdout.flush()
    sys.stdout.buffer.write(stdout_bytes)
    sys.stdout.buffer.flush()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the hash-bound AB16 full-preflight qualification"
    )
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--basetemp", required=True, type=Path)
    parser.add_argument("--basetemp-relative", required=True, type=Path)
    parser.add_argument("--expected-count", required=True, type=int)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--preflight-source", required=True, type=Path)
    parser.add_argument("--collection-protocol-source", required=True, type=Path)
    parser.add_argument("--collection-plugin-source", required=True, type=Path)
    parser.add_argument(
        "--support-source",
        action="append",
        default=[],
        nargs=6,
        metavar=("ROLE", "FD", "PATH", "MODE", "SIZE", "SHA256"),
    )
    parser.add_argument("--full", action="store_true", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.full is not True:
        raise AB16PreflightQualificationError(
            "qualification runner requires the full lane"
        )
    return _run_qualification(args)


if __name__ == "__main__":
    raise SystemExit(main())
