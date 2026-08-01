#!/usr/bin/env python3
"""Retained-FD loader for package-pinned, zero-authority AB16 calibration."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import os
from pathlib import Path
import stat
import sys
from types import ModuleType
from typing import NoReturn, Sequence


LOADER_SCHEMA = "noncert-cuts-ab16-resource-calibration-fd-loader-v2"
PACKAGE_SCHEMA = "noncert-cuts-ab16-resource-calibration-package-v2"
PORTABLE_LAYOUT = "PORTABLE_CANDIDATE_V1"
STAGES = frozenset({"GATE_B_QUALIFICATION", "FORMAL_ORGANIC_ARM"})


class CalibrationLoaderError(RuntimeError):
    pass


def _fail(detail: str) -> NoReturn:
    raise CalibrationLoaderError(detail)


def _require_process_contract() -> None:
    observed = (
        sys.flags.isolated,
        sys.flags.ignore_environment,
        sys.flags.no_user_site,
        bool(getattr(sys.flags, "safe_path", False)),
        sys.flags.dont_write_bytecode,
        sys.dont_write_bytecode,
    )
    if observed != (1, 1, 1, True, 1, True):
        _fail(f"isolated Python contract differs: {observed!r}")


def _require_fd(descriptor: int, *, directory: bool, writable: bool) -> None:
    try:
        metadata = os.fstat(descriptor)
    except OSError as exc:
        _fail(f"retained descriptor {descriptor} is unavailable: {exc}")
    if directory:
        if not stat.S_ISDIR(metadata.st_mode):
            _fail(f"retained descriptor {descriptor} is not a directory")
        return
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        _fail(f"retained descriptor {descriptor} is not a single-linked regular file")
    flags = os.O_RDONLY
    try:
        import fcntl

        flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
    except OSError as exc:
        _fail(f"retained descriptor {descriptor} flags unavailable: {exc}")
    access = flags & os.O_ACCMODE
    if writable and access == os.O_RDONLY:
        _fail(f"retained descriptor {descriptor} is not writable")
    if not writable and access != os.O_RDONLY:
        _fail(f"retained descriptor {descriptor} is writable")


def _load_from_fd(
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
        _fail(f"cannot build retained-FD module spec for {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _open_absolute_file(path: Path) -> int:
    if path != path.absolute() or not path.is_absolute():
        _fail(f"host runtime path is not absolute: {path}")
    directory_flags = (
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    opened = [os.open("/", directory_flags)]
    descriptor = -1
    primary: BaseException | None = None
    try:
        for component in path.parts[1:-1]:
            opened.append(
                os.open(component, directory_flags, dir_fd=opened[-1])
            )
        descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=opened[-1],
        )
    except BaseException as exc:
        primary = exc
    for parent in reversed(opened):
        try:
            os.close(parent)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "host runtime parent cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException as close_error:
                primary.add_note(
                    "host runtime descriptor cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise primary
    return descriptor


def _verify_host_runtime_identities(value: object) -> None:
    if type(value) is not dict or not value:
        _fail("portable package host-runtime identity table is absent")
    paths: set[str] = set()
    for label, raw_identity in sorted(value.items()):
        if (
            type(label) is not str
            or not label.startswith("host-runtime-")
            or type(raw_identity) is not dict
            or set(raw_identity) != {"path", "sha256", "size_bytes"}
        ):
            _fail("portable package host-runtime identity shape drifted")
        identity = raw_identity
        if (
            type(identity["path"]) is not str
            or identity["path"] in paths
            or type(identity["sha256"]) is not str
            or len(identity["sha256"]) != 64
            or type(identity["size_bytes"]) is not int
            or identity["size_bytes"] <= 0
        ):
            _fail(f"portable host-runtime identity is malformed: {label}")
        paths.add(identity["path"])
        descriptor = _open_absolute_file(Path(identity["path"]))
        primary: BaseException | None = None
        try:
            before = os.fstat(descriptor)
            flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or flags & os.O_ACCMODE != os.O_RDONLY
                or before.st_size != identity["size_bytes"]
            ):
                _fail(f"portable host-runtime file identity drifted: {label}")
            digest = hashlib.sha256()
            offset = 0
            while offset < before.st_size:
                block = os.pread(
                    descriptor,
                    min(1024 * 1024, before.st_size - offset),
                    offset,
                )
                if not block:
                    _fail(f"portable host-runtime short read: {label}")
                digest.update(block)
                offset += len(block)
            after = os.fstat(descriptor)
            def signature(
                item: os.stat_result,
            ) -> tuple[int, int, int, int, int, int, int]:
                return (
                    item.st_dev,
                    item.st_ino,
                    item.st_mode,
                    item.st_nlink,
                    item.st_size,
                    item.st_mtime_ns,
                    item.st_ctime_ns,
                )
            if (
                signature(before) != signature(after)
                or digest.hexdigest() != identity["sha256"]
            ):
                _fail(f"portable host-runtime bytes drifted: {label}")
        except BaseException as exc:
            primary = exc
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                raise
            primary.add_note(
                f"host runtime descriptor close failed: {close_error}"
            )
        if primary is not None:
            raise primary


def _verify_executing_python(
    *,
    package_root_fd: int,
    receipt: dict[str, object],
) -> None:
    runtime = receipt["runtime_layout"]
    members = receipt["member_identities"]
    if type(runtime) is not dict or type(members) is not dict:
        _fail("portable Python layout/member table is malformed")
    checked_runtime = runtime
    checked_members = members
    relative = checked_runtime["python_relative_path"]
    identity = checked_members.get(relative)
    if (
        type(relative) is not str
        or type(identity) is not dict
        or set(identity) != {"path", "sha256", "size_bytes"}
        or identity["path"] != relative
    ):
        _fail("portable Python member identity is malformed")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        _fail("portable Python member path is unsafe")
    directories = [os.dup(package_root_fd)]
    directory_signatures: list[tuple[int, ...]] = []
    package_descriptor = -1
    executing_descriptor = -1
    primary: BaseException | None = None
    try:
        for part in parts[:-1]:
            metadata = os.fstat(directories[-1])
            directory_signatures.append(
                (
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_mode,
                    metadata.st_uid,
                    metadata.st_nlink,
                    metadata.st_mtime_ns,
                    metadata.st_ctime_ns,
                )
            )
            directories.append(
                os.open(
                    part,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    dir_fd=directories[-1],
                )
            )
        final_parent = os.fstat(directories[-1])
        directory_signatures.append(
            (
                final_parent.st_dev,
                final_parent.st_ino,
                final_parent.st_mode,
                final_parent.st_uid,
                final_parent.st_nlink,
                final_parent.st_mtime_ns,
                final_parent.st_ctime_ns,
            )
        )
        package_descriptor = os.open(
            parts[-1],
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directories[-1],
        )
        executing_descriptor = os.open("/proc/self/exe", os.O_RDONLY | os.O_CLOEXEC)
        for descriptor, label in (
            (package_descriptor, "packaged Python"),
            (executing_descriptor, "executing Python"),
        ):
            metadata = os.fstat(descriptor)
            digest = hashlib.sha256()
            offset = 0
            while offset < metadata.st_size:
                block = os.pread(
                    descriptor,
                    min(1024 * 1024, metadata.st_size - offset),
                    offset,
                )
                if not block:
                    _fail(f"{label} short read")
                digest.update(block)
                offset += len(block)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size != identity["size_bytes"]
                or digest.hexdigest() != identity["sha256"]
            ):
                _fail(f"{label} differs from the portable package identity")
        for descriptor, expected in zip(
            directories,
            directory_signatures,
            strict=True,
        ):
            metadata = os.fstat(descriptor)
            observed = (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_mode,
                metadata.st_uid,
                metadata.st_nlink,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
            )
            if observed != expected:
                _fail("portable Python directory chain drifted")
    except BaseException as exc:
        primary = exc
    for descriptor in (
        executing_descriptor,
        package_descriptor,
        *reversed(directories),
    ):
        if descriptor < 0:
            continue
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "portable Python descriptor cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        raise primary


def _install_portable_import_surface(
    *,
    package_root_fd: int,
    package_root_path: Path,
    receipt: dict[str, object],
) -> None:
    if (
        receipt.get("schema_version") != PACKAGE_SCHEMA
        or receipt.get("layout") != PORTABLE_LAYOUT
        or type(receipt.get("runtime_layout")) is not dict
        or type(receipt.get("repository_snapshot")) is not dict
    ):
        _fail("calibration loader requires one portable package-v2 closure")
    runtime = receipt["runtime_layout"]
    repository = receipt["repository_snapshot"]
    assert type(runtime) is dict
    assert type(repository) is dict
    expected_runtime_keys = {
        "cpython_version",
        "libpython_relative_path",
        "ortools_version",
        "python_prefix",
        "python_relative_path",
        "site_packages_prefix",
        "stdlib_prefix",
    }
    if (
        set(runtime) != expected_runtime_keys
        or runtime["cpython_version"] != "3.13.13"
        or repository.get("repository_prefix") != "materialized/repository"
    ):
        _fail("portable package runtime/repository discriminator drifted")
    retained_root = Path(f"/proc/self/fd/{package_root_fd}")
    named_root = Path(os.path.abspath(package_root_path))
    python_prefix = retained_root / str(runtime["python_prefix"])
    named_python_prefix = named_root / str(runtime["python_prefix"])
    snapshot = retained_root / str(repository["repository_prefix"])
    site_packages = retained_root / str(runtime["site_packages_prefix"])
    initial = [Path(path) for path in sys.path if path]
    if not initial or any(
        (
            python_prefix not in path.parents
            and path != python_prefix
            and named_python_prefix not in path.parents
            and path != named_python_prefix
        )
        for path in initial
    ):
        _fail(f"ambient Python import path survived copied-prefix exec: {initial!r}")
    sys.path[:] = [
        str(snapshot),
        str(site_packages),
        *(str(path) for path in initial),
    ]
    os.chdir(snapshot)
    if Path.cwd() != snapshot.resolve():
        _fail("portable repository snapshot cwd join drifted")


def _close_unknown_fds(allowed: set[int]) -> None:
    try:
        observed = {
            int(name)
            for name in os.listdir("/proc/self/fd")
            if name.isdigit()
        }
    except OSError as exc:
        _fail(f"cannot enumerate retained FD surface: {exc}")
    for descriptor in sorted(observed - allowed - {0, 1, 2}):
        try:
            os.close(descriptor)
        except OSError:
            # The directory enumeration FD closes before listdir returns.
            pass


def run(args: argparse.Namespace) -> dict[str, object]:
    _require_process_contract()
    if args.stage not in STAGES:
        _fail(f"unknown calibration stage: {args.stage!r}")
    _require_fd(args.package_root_fd, directory=True, writable=False)
    _require_fd(args.verifier_fd, directory=False, writable=False)
    _require_fd(args.workload_fd, directory=False, writable=False)
    _require_fd(args.fixture_fd, directory=False, writable=False)
    _require_fd(args.stage_root_fd, directory=True, writable=True)
    try:
        result_stat = os.fstat(args.result_fd)
    except OSError as exc:
        _fail(f"result descriptor unavailable: {exc}")
    if not stat.S_ISFIFO(result_stat.st_mode):
        _fail("result descriptor is not the pre-reserved pipe")

    initial_runtime_paths = list(sys.path)
    sys.path.insert(0, f"/proc/self/fd/{args.package_root_fd}")
    try:
        verifier = _load_from_fd(
            args.verifier_fd,
            module_name="_ab16_calibration_package_verifier_retained",
        )
    finally:
        sys.path[:] = initial_runtime_paths
    receipt_identity = {
        "path": str(Path(args.package_root_path) / "receipt.json"),
        "sha256": args.package_receipt_sha256,
        "size_bytes": args.package_receipt_size,
    }
    receipt = verifier.verify_retained_calibration_package(
        args.package_root_fd,
        Path(args.package_root_path),
        expected_receipt_identity=receipt_identity,
    )
    verifier_path = receipt["roles"]["calibration-package-verifier"]
    verifier_identity = receipt["member_identities"][verifier_path]
    verifier_stat = os.fstat(args.verifier_fd)
    if (
        verifier_stat.st_size != verifier_identity["size_bytes"]
        or args.verifier_sha256 != verifier_identity["sha256"]
    ):
        _fail("package verifier retained identity differs")
    _install_portable_import_surface(
        package_root_fd=args.package_root_fd,
        package_root_path=Path(args.package_root_path),
        receipt=receipt,
    )
    _verify_executing_python(
        package_root_fd=args.package_root_fd,
        receipt=receipt,
    )
    _verify_host_runtime_identities(receipt.get("host_runtime_identities"))

    os.close(args.verifier_fd)
    allowed = {
        args.package_root_fd,
        args.workload_fd,
        args.fixture_fd,
        args.stage_root_fd,
        args.result_fd,
    }
    _close_unknown_fds(allowed)
    workload = _load_from_fd(
        args.workload_fd,
        module_name="_ab16_calibration_workload_retained",
    )
    entry = getattr(workload, "run_from_retained_package", None)
    if entry is None:
        _fail("calibration workload role lacks its fixed entrypoint")
    result = entry(
        stage=args.stage,
        package_root_fd=args.package_root_fd,
        package_receipt=receipt,
        fixture_fd=args.fixture_fd,
        stage_root_fd=args.stage_root_fd,
        result_fd=args.result_fd,
    )
    if type(result) is not dict:
        _fail("calibration workload returned a non-object")
    _verify_host_runtime_identities(receipt.get("host_runtime_identities"))
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--package-root-fd", type=int, required=True)
    parser.add_argument("--package-root-path", required=True)
    parser.add_argument("--package-receipt-sha256", required=True)
    parser.add_argument("--package-receipt-size", type=int, required=True)
    parser.add_argument("--verifier-fd", type=int, required=True)
    parser.add_argument("--verifier-sha256", required=True)
    parser.add_argument("--workload-fd", type=int, required=True)
    parser.add_argument("--fixture-fd", type=int, required=True)
    parser.add_argument("--stage-root-fd", type=int, required=True)
    parser.add_argument("--result-fd", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        run(_parser().parse_args(argv))
    except BaseException as exc:
        print(f"FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
