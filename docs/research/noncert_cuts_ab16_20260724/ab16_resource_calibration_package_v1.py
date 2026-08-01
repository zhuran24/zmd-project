#!/usr/bin/env python3
"""Closed, research-only package for AB16 resource calibration workloads.

This is deliberately not a campaign/bootstrap package.  It cannot publish a
Gate-B approval, consume a formal attempt, select an arm, or grant launch
authority.  ``receipt.json`` is the one protocol-reserved terminal member; its
embedded manifest registers every other descendant and therefore never hashes
or sizes itself.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import unicodedata
from typing import Final, NoReturn, cast

from devtools.research_run_contract import (
    ExclusiveRunRoot,
    build_artifact_root_manifest,
    canonical_json_bytes,
    read_stable_snapshot,
    verify_artifact_root_closure,
)


PACKAGE_SCHEMA: Final = "noncert-cuts-ab16-resource-calibration-package-v2"
PACKAGE_AUTHORITY_SCOPE: Final = "AB16_RESOURCE_CALIBRATION_ONLY"
TERMINAL_PATH: Final = "receipt.json"
FOCUSED_FIXTURE_LAYOUT: Final = "FOCUSED_FIXTURE_V1"
PORTABLE_CANDIDATE_LAYOUT: Final = "PORTABLE_CANDIDATE_V1"
REPOSITORY_PREFIX: Final = "materialized/repository"
PYTHON_PREFIX: Final = "runtime/python-base"
SITE_PACKAGES_PREFIX: Final = "runtime/site-packages"
PYTHON_RELATIVE_PATH: Final = f"{PYTHON_PREFIX}/bin/python3.13"
CANDIDATE_RELATIVE_PATH: Final = (
    f"{REPOSITORY_PREFIX}/data/preprocessed/candidate_placements.json"
)
STAGES: Final = frozenset(
    {"FULL_PREFLIGHT", "GATE_B_QUALIFICATION", "FORMAL_ORGANIC_ARM"}
)
REQUIRED_ROLES: Final = frozenset(
    {
        "calibration-aggregator",
        "calibration-alternate-replay",
        "calibration-fd-loader",
        "calibration-observer",
        "calibration-package-verifier",
        "calibration-primary-replay",
        "calibration-protocol",
        "calibration-runner",
        "calibration-workload",
    }
)
FALSE_AUTHORIZATIONS: Final = {
    "formal_attempt_consumption_authorized": False,
    "formal_campaign_creation_authorized": False,
    "formal_selection_authorized": False,
    "gate_b_approval_authorized": False,
    "organic_arm_launch_authorized": False,
    "profile_installation_authorized": False,
    "solver_authority_authorized": False,
}
_DIRECTORY_FLAGS: Final = (
    os.O_RDONLY
    | os.O_DIRECTORY
    | os.O_CLOEXEC
    | getattr(os, "O_NOFOLLOW", 0)
)
_REGULAR_FLAGS: Final = (
    os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
)


class CalibrationPackageError(RuntimeError):
    """The package identity, closure, or no-authority boundary failed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise CalibrationPackageError(code, detail)


def _relative(
    value: object,
    label: str,
    *,
    allow_terminal: bool = False,
) -> str:
    if type(value) is not str:
        _fail("CALIBRATION_PACKAGE_PATH_INVALID", label)
    path = cast(str, value)
    parts = path.split("/")
    if (
        not path
        or path.startswith("/")
        or path.endswith("/")
        or "\\" in path
        or "\x00" in path
        or any(part in {"", ".", ".."} for part in parts)
        or (
            (path == TERMINAL_PATH or path.startswith(f"{TERMINAL_PATH}/"))
            and not (allow_terminal and path == TERMINAL_PATH)
        )
    ):
        _fail("CALIBRATION_PACKAGE_PATH_INVALID", f"{label}: {path!r}")
    return path


def _identity(path: str, raw: bytes) -> dict[str, object]:
    return {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _strict_json(raw: bytes, label: str) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail("CALIBRATION_PACKAGE_JSON_INVALID", f"{label}: duplicate {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> NoReturn:
        _fail("CALIBRATION_PACKAGE_JSON_INVALID", f"{label}: non-integer {value!r}")

    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("CALIBRATION_PACKAGE_JSON_INVALID", f"{label}: {exc}")
    if type(value) is not dict or canonical_json_bytes(value) != raw:
        _fail("CALIBRATION_PACKAGE_JSON_INVALID", f"{label}: not canonical JSON")
    return cast(dict[str, object], value)


def _validate_identity(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"}:
        _fail("CALIBRATION_PACKAGE_IDENTITY_INVALID", label)
    record = cast(dict[str, object], value)
    if (
        type(record["path"]) is not str
        or type(record["sha256"]) is not str
        or len(cast(str, record["sha256"])) != 64
        or any(char not in "0123456789abcdef" for char in cast(str, record["sha256"]))
        or type(record["size_bytes"]) is not int
        or cast(int, record["size_bytes"]) <= 0
    ):
        _fail("CALIBRATION_PACKAGE_IDENTITY_INVALID", label)
    _relative(record["path"], label)
    return dict(record)


def _validate_absolute_identity(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"}:
        _fail("CALIBRATION_PACKAGE_IDENTITY_INVALID", label)
    record = cast(dict[str, object], value)
    if (
        type(record["path"]) is not str
        or not Path(cast(str, record["path"])).is_absolute()
        or type(record["sha256"]) is not str
        or len(cast(str, record["sha256"])) != 64
        or any(
            character not in "0123456789abcdef"
            for character in cast(str, record["sha256"])
        )
        or type(record["size_bytes"]) is not int
        or cast(int, record["size_bytes"]) <= 0
    ):
        _fail("CALIBRATION_PACKAGE_IDENTITY_INVALID", label)
    return dict(record)


def _validate_portable_layout(
    receipt: Mapping[str, object],
    *,
    checked_member_records: Mapping[str, Mapping[str, object]],
) -> None:
    repository = receipt.get("repository_snapshot")
    runtime = receipt.get("runtime_layout")
    source_sets = receipt.get("source_sets")
    host_runtime = receipt.get("host_runtime_identities")
    if (
        type(repository) is not dict
        or set(repository)
        != {
            "candidate_package_identity",
            "candidate_source_identity",
            "repository_head",
            "repository_prefix",
            "repository_tree",
            "source_set",
        }
        or type(runtime) is not dict
        or set(runtime)
        != {
            "cpython_version",
            "libpython_relative_path",
            "ortools_version",
            "python_prefix",
            "python_relative_path",
            "site_packages_prefix",
            "stdlib_prefix",
        }
        or type(source_sets) is not dict
        or type(host_runtime) is not dict
        or not host_runtime
    ):
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "portable repository/runtime layout is malformed",
        )
    repository_record = cast(dict[str, object], repository)
    runtime_record = cast(dict[str, object], runtime)
    candidate_package = _validate_identity(
        repository_record["candidate_package_identity"],
        "packaged candidate placements",
    )
    candidate_source = _validate_absolute_identity(
        repository_record["candidate_source_identity"],
        "external candidate placements",
    )
    if (
        candidate_package != checked_member_records.get(CANDIDATE_RELATIVE_PATH)
        or candidate_package["sha256"] != candidate_source["sha256"]
        or candidate_package["size_bytes"] != candidate_source["size_bytes"]
        or repository_record["repository_prefix"] != REPOSITORY_PREFIX
        or repository_record["source_set"]
        != cast(dict[str, object], source_sets).get("repository")
        or type(repository_record["repository_head"]) is not str
        or len(cast(str, repository_record["repository_head"])) != 40
        or any(
            character not in "0123456789abcdef"
            for character in cast(str, repository_record["repository_head"])
        )
        or type(repository_record["repository_tree"]) is not str
        or len(cast(str, repository_record["repository_tree"])) != 40
        or any(
            character not in "0123456789abcdef"
            for character in cast(str, repository_record["repository_tree"])
        )
    ):
        _fail(
            "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
            "portable repository snapshot join drifted",
        )
    if runtime_record != {
        "cpython_version": "3.13.13",
        "libpython_relative_path": (
            f"{PYTHON_PREFIX}/lib/libpython3.13.so.1.0"
        ),
        "ortools_version": runtime_record.get("ortools_version"),
        "python_prefix": PYTHON_PREFIX,
        "python_relative_path": PYTHON_RELATIVE_PATH,
        "site_packages_prefix": SITE_PACKAGES_PREFIX,
        "stdlib_prefix": f"{PYTHON_PREFIX}/lib/python3.13",
    } or (
        type(runtime_record["ortools_version"]) is not str
        or not runtime_record["ortools_version"]
    ):
        _fail(
            "CALIBRATION_PACKAGE_RUNTIME_INVALID",
            "portable runtime path/version layout drifted",
        )
    required_runtime_members = {
        PYTHON_RELATIVE_PATH,
        f"{PYTHON_PREFIX}/lib/libpython3.13.so.1.0",
        f"{PYTHON_PREFIX}/lib/python3.13/os.py",
        f"{SITE_PACKAGES_PREFIX}/ortools/__init__.py",
    }
    if not required_runtime_members <= set(checked_member_records):
        _fail(
            "CALIBRATION_PACKAGE_RUNTIME_INVALID",
            "portable runtime closure omits required members",
        )
    if (
        checked_member_records[PYTHON_RELATIVE_PATH].get("mode") != 0o555
        or checked_member_records[
            f"{PYTHON_PREFIX}/lib/libpython3.13.so.1.0"
        ].get("mode")
        not in {0o444, 0o555}
    ):
        _fail(
            "CALIBRATION_PACKAGE_RUNTIME_INVALID",
            "portable Python executable/library modes drifted",
        )


def _mkdir_parents(root: ExclusiveRunRoot, relative: str, made: set[str]) -> None:
    parts = relative.split("/")[:-1]
    for end in range(1, len(parts) + 1):
        directory = "/".join(parts[:end])
        if directory not in made:
            root.mkdir(directory, mode=0o700)
            made.add(directory)


def _member_record(relative: str, raw: bytes, mode: int) -> dict[str, object]:
    return {
        "mode": mode,
        "path": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _source_set_descriptor(
    *,
    kind: str,
    prefix: str,
    records: list[dict[str, object]],
) -> dict[str, object]:
    ordered = sorted(records, key=lambda item: cast(str, item["path"]).encode("utf-8"))
    return {
        "kind": kind,
        "member_count": len(ordered),
        "ordered_member_digest": hashlib.sha256(
            canonical_json_bytes(ordered)
        ).hexdigest(),
        "prefix": prefix,
        "total_bytes": sum(cast(int, item["size_bytes"]) for item in ordered),
    }


def _write_member(
    root: ExclusiveRunRoot,
    *,
    relative: str,
    raw: bytes,
    mode: int,
    made: set[str],
    identities: dict[str, dict[str, object]],
    modes: dict[str, int],
) -> dict[str, object]:
    checked = _relative(relative, f"package member {relative!r}")
    if checked in identities:
        _fail("CALIBRATION_PACKAGE_SHAPE_INVALID", f"duplicate member {checked}")
    if mode not in {0o400, 0o444, 0o500, 0o555}:
        _fail(
            "CALIBRATION_PACKAGE_MEMBER_INVALID",
            f"{checked}: unsupported immutable mode {mode:o}",
        )
    _mkdir_parents(root, checked, made)
    root.write_bytes(checked, raw, mode=mode)
    identities[checked] = _identity(checked, raw)
    modes[checked] = mode
    return _member_record(checked, raw, mode)


def _safe_git_path(raw: bytes) -> str:
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail("CALIBRATION_PACKAGE_REPOSITORY_INVALID", "non-UTF-8 Git path")
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or unicodedata.normalize("NFC", value) != value
    ):
        _fail(
            "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
            f"unsafe Git path {value!r}",
        )
    return value


def _git(
    repository: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        _fail("CALIBRATION_PACKAGE_REPOSITORY_INVALID", f"git failed: {exc}")
    if result.returncode != 0:
        _fail(
            "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
            result.stderr.decode("utf-8", errors="replace")[-4096:],
        )
    return result.stdout


def _git_commit_members(
    repository: Path,
    expected_head: str,
) -> tuple[str, list[tuple[str, int, bytes]]]:
    if (
        not repository.is_absolute()
        or len(expected_head) != 40
        or any(character not in "0123456789abcdef" for character in expected_head)
    ):
        _fail(
            "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
            "repository root or candidate commit is malformed",
        )
    observed_head = _git(repository, "rev-parse", "--verify", "HEAD").decode(
        "ascii", errors="strict"
    ).strip()
    if observed_head != expected_head:
        _fail(
            "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
            f"candidate HEAD differs: {observed_head} != {expected_head}",
        )
    tree = _git(
        repository,
        "rev-parse",
        "--verify",
        f"{expected_head}^{{tree}}",
    ).decode("ascii", errors="strict").strip()
    raw_tree = _git(
        repository,
        "ls-tree",
        "-rz",
        "-r",
        "--full-tree",
        expected_head,
    )
    entries: list[tuple[str, str, str]] = []
    collision_keys: set[str] = set()
    for record in raw_tree.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            raw_mode, object_type, raw_oid = metadata.split(b" ")
        except ValueError as exc:
            _fail(
                "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
                f"malformed ls-tree record: {exc}",
            )
        path = _safe_git_path(raw_path)
        mode = raw_mode.decode("ascii", errors="strict")
        oid = raw_oid.decode("ascii", errors="strict")
        collision = unicodedata.normalize("NFC", path).casefold()
        if (
            object_type != b"blob"
            or mode not in {"100644", "100755"}
            or len(oid) != 40
            or any(character not in "0123456789abcdef" for character in oid)
            or collision in collision_keys
        ):
            _fail(
                "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
                f"inadmissible tracked member {path}",
            )
        collision_keys.add(collision)
        entries.append((path, mode, oid))
    if not entries or entries != sorted(
        entries, key=lambda item: item[0].encode("utf-8")
    ):
        _fail(
            "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
            "tracked member order is not canonical",
        )
    batch = _git(
        repository,
        "cat-file",
        "--batch",
        input_bytes=b"".join(
            oid.encode("ascii") + b"\n" for _path, _mode, oid in entries
        ),
    )
    offset = 0
    result: list[tuple[str, int, bytes]] = []
    for path, mode, expected_oid in entries:
        newline = batch.find(b"\n", offset)
        if newline < 0:
            _fail(
                "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
                f"truncated cat-file header for {path}",
            )
        header = batch[offset:newline].split(b" ")
        if len(header) != 3 or header[1] != b"blob":
            _fail(
                "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
                f"cat-file object type drifted for {path}",
            )
        try:
            size = int(header[2])
        except ValueError as exc:
            _fail(
                "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
                f"cat-file size drifted for {path}: {exc}",
            )
        start = newline + 1
        end = start + size
        if (
            header[0].decode("ascii", errors="strict") != expected_oid
            or end >= len(batch)
            or batch[end : end + 1] != b"\n"
        ):
            _fail(
                "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
                f"cat-file framing drifted for {path}",
            )
        result.append((path, 0o555 if mode == "100755" else 0o444, batch[start:end]))
        offset = end + 1
    if offset != len(batch):
        _fail(
            "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
            "cat-file batch has trailing bytes",
        )
    return tree, result


def _tree_files(root: Path) -> list[Path]:
    if not root.is_absolute():
        _fail("CALIBRATION_PACKAGE_RUNTIME_INVALID", f"{root} is not absolute")
    metadata = os.lstat(root)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        _fail(
            "CALIBRATION_PACKAGE_RUNTIME_INVALID",
            f"{root} is not one real directory",
        )
    result: list[Path] = []
    for directory, raw_directories, raw_files in os.walk(root, followlinks=False):
        raw_directories.sort(key=os.fsencode)
        raw_files.sort(key=os.fsencode)
        parent = Path(directory)
        for name in raw_directories:
            child = parent / name
            child_metadata = os.lstat(child)
            if stat.S_ISLNK(child_metadata.st_mode):
                _fail(
                    "CALIBRATION_PACKAGE_RUNTIME_INVALID",
                    f"runtime directory symlink is forbidden: {child}",
                )
            if not stat.S_ISDIR(child_metadata.st_mode):
                _fail(
                    "CALIBRATION_PACKAGE_RUNTIME_INVALID",
                    f"runtime special directory entry is forbidden: {child}",
                )
        for name in raw_files:
            child = parent / name
            child_metadata = os.lstat(child)
            if (
                stat.S_ISLNK(child_metadata.st_mode)
                or not stat.S_ISREG(child_metadata.st_mode)
            ):
                _fail(
                    "CALIBRATION_PACKAGE_RUNTIME_INVALID",
                    f"runtime special/symlink member is forbidden: {child}",
                )
            result.append(child)
    return sorted(
        result,
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    )


def _stable_source_bytes(path: Path, *, label: str) -> tuple[bytes, int]:
    snapshot = read_stable_snapshot(path)
    if snapshot.stat_signature[3] != 1:
        _fail(
            "CALIBRATION_PACKAGE_MEMBER_INVALID",
            f"{label}: source is not single-linked",
        )
    mode = stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode)
    return snapshot.data, (0o555 if mode & 0o111 else 0o444)


def _host_runtime_dependencies(
    *,
    dynamic_objects: list[Path],
    internal_roots: tuple[Path, ...],
) -> dict[str, dict[str, object]]:
    pending = list(dict.fromkeys(path.absolute() for path in dynamic_objects))
    seen: set[Path] = set()
    external: set[Path] = set()
    while pending:
        target = pending.pop()
        if target in seen:
            continue
        seen.add(target)
        result = subprocess.run(
            ["ldd", str(target)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            _fail(
                "CALIBRATION_PACKAGE_RUNTIME_INVALID",
                f"ldd failed for {target}: {result.stderr[-2048:]}",
            )
        for row in result.stdout.splitlines():
            stripped = row.strip()
            if "not found" in stripped:
                _fail(
                    "CALIBRATION_PACKAGE_RUNTIME_INVALID",
                    f"unresolved runtime dependency: {stripped}",
                )
            candidate: str | None = None
            if "=>" in stripped:
                right = stripped.partition("=>")[2].strip().split(maxsplit=1)
                if right and right[0].startswith("/"):
                    candidate = right[0]
            else:
                first = stripped.split(maxsplit=1)
                if first and first[0].startswith("/"):
                    candidate = first[0]
            if candidate is None:
                continue
            dependency = Path(candidate).absolute()
            if any(
                dependency == root or root in dependency.parents
                for root in internal_roots
            ):
                continue
            if dependency not in external:
                external.add(dependency)
                pending.append(dependency)
    identities: dict[str, dict[str, object]] = {}
    for index, path in enumerate(sorted(external, key=lambda item: os.fsencode(item))):
        raw, _mode = _stable_source_bytes(path, label=f"host runtime {path}")
        identities[f"host-runtime-{index:04d}"] = {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
    return identities


def _finish_package(
    root: ExclusiveRunRoot,
    *,
    identities: dict[str, dict[str, object]],
    modes: dict[str, int],
    roles: Mapping[str, str],
    stage_fixtures: Mapping[str, str],
    layout: str,
    source_sets: Mapping[str, Mapping[str, object]],
    repository_snapshot: Mapping[str, object] | None,
    runtime_layout: Mapping[str, object] | None,
    host_runtime_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    role_paths = {
        role: _relative(relative, f"role {role}")
        for role, relative in roles.items()
    }
    fixture_paths = {
        stage: _relative(relative, f"fixture {stage}")
        for stage, relative in stage_fixtures.items()
    }
    if set(role_paths) != REQUIRED_ROLES or set(fixture_paths) != STAGES:
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "role or stage-fixture discriminator set is not exact",
        )
    if not (set(role_paths.values()) | set(fixture_paths.values())) <= set(
        identities
    ):
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "a role or fixture is absent from package members",
        )
    manifest = build_artifact_root_manifest(root)
    receipt = {
        "authority_scope": PACKAGE_AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "host_runtime_identities": {
            label: dict(identity)
            for label, identity in sorted(host_runtime_identities.items())
        },
        "layout": layout,
        "manifest": manifest,
        "member_identities": dict(sorted(identities.items())),
        "member_modes": dict(sorted(modes.items())),
        "repository_snapshot": (
            None if repository_snapshot is None else dict(repository_snapshot)
        ),
        "roles": role_paths,
        "runtime_layout": None if runtime_layout is None else dict(runtime_layout),
        "schema_version": PACKAGE_SCHEMA,
        "source_sets": {
            label: dict(record) for label, record in sorted(source_sets.items())
        },
        "stage_fixtures": fixture_paths,
        "status": "CLOSED_NO_AUTHORITY",
        "terminal_self_exclusion": {
            "excluded_from_manifest": TERMINAL_PATH,
            "self_hash_or_size_present": False,
        },
    }
    root.write_bytes(TERMINAL_PATH, canonical_json_bytes(receipt), mode=0o400)
    verify_artifact_root_closure(root, manifest, receipt_present=True)
    return receipt


def build_calibration_package(
    output_root: Path | str,
    *,
    members: Mapping[str, Path | str],
    roles: Mapping[str, str],
    stage_fixtures: Mapping[str, str],
) -> dict[str, object]:
    """Build a small capability fixture; it can never be launch-comparable."""

    if set(roles) != REQUIRED_ROLES or set(stage_fixtures) != STAGES:
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "role or stage-fixture discriminator set is not exact",
        )
    normalized_members = {
        _relative(relative, f"member {relative!r}"): Path(source)
        for relative, source in members.items()
    }
    if len(normalized_members) != len(members):
        _fail("CALIBRATION_PACKAGE_SHAPE_INVALID", "duplicate member path")
    referenced = set(roles.values()) | set(stage_fixtures.values())
    if not referenced <= set(normalized_members):
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "a role or fixture is absent from package members",
        )

    snapshots: dict[str, bytes] = {}
    for relative, source in sorted(normalized_members.items()):
        snapshot = read_stable_snapshot(source)
        if snapshot.stat_signature[3] != 1:
            _fail(
                "CALIBRATION_PACKAGE_MEMBER_INVALID",
                f"{relative}: source is not single-linked",
            )
        snapshots[relative] = snapshot.data

    root = ExclusiveRunRoot.create(Path(output_root).absolute())
    made: set[str] = set()
    identities: dict[str, dict[str, object]] = {}
    modes: dict[str, int] = {}
    records: list[dict[str, object]] = []
    for relative, raw in sorted(snapshots.items()):
        records.append(
            _write_member(
                root,
                relative=relative,
                raw=raw,
                mode=0o400,
                made=made,
                identities=identities,
                modes=modes,
            )
        )
    return _finish_package(
        root,
        identities=identities,
        modes=modes,
        roles=roles,
        stage_fixtures=stage_fixtures,
        layout=FOCUSED_FIXTURE_LAYOUT,
        source_sets={
            "fixture-members": _source_set_descriptor(
                kind="FOCUSED_FIXTURE_MEMBERS",
                prefix=".",
                records=records,
            )
        },
        repository_snapshot=None,
        runtime_layout=None,
        host_runtime_identities={},
    )


def build_portable_calibration_package(
    output_root: Path | str,
    *,
    repository: Path | str,
    repository_head: str,
    candidate_placements: Path | str,
    python_base_root: Path | str,
    site_packages_root: Path | str,
    members: Mapping[str, Path | str],
    roles: Mapping[str, str],
    stage_fixtures: Mapping[str, str],
) -> dict[str, object]:
    """Build the no-authority, self-contained candidate calibration package.

    Repository bytes come from the exact candidate commit rather than the
    mutable checkout.  The one external candidate-placement overlay is read
    independently.  Python executes from copied prefix bytes; only ELF/glibc
    dependencies that cannot be copied into that prefix remain explicit host
    runtime identities.
    """

    if set(roles) != REQUIRED_ROLES or set(stage_fixtures) != STAGES:
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "portable role or stage-fixture discriminator set is not exact",
        )
    repository_path = Path(repository).absolute()
    candidate_path = Path(candidate_placements).absolute()
    python_base = Path(python_base_root).absolute()
    site_packages = Path(site_packages_root).absolute()
    for path, label in (
        (repository_path, "repository"),
        (candidate_path, "candidate placements"),
        (python_base, "Python base"),
        (site_packages, "site packages"),
    ):
        if Path(os.path.realpath(path)) != path:
            _fail(
                "CALIBRATION_PACKAGE_SOURCE_PATH_INVALID",
                f"{label} path has a symlink component: {path}",
            )

    tree, tracked = _git_commit_members(repository_path, repository_head)
    tracked_paths = {path for path, _mode, _raw in tracked}
    candidate_inside = "data/preprocessed/candidate_placements.json"
    if candidate_inside in tracked_paths:
        _fail(
            "CALIBRATION_PACKAGE_REPOSITORY_INVALID",
            "candidate-placement overlay already exists in the candidate tree",
        )
    candidate_snapshot = read_stable_snapshot(candidate_path)
    if candidate_snapshot.stat_signature[3] != 1:
        _fail(
            "CALIBRATION_PACKAGE_MEMBER_INVALID",
            "candidate placements source is not single-linked",
        )

    python_source = python_base / "bin/python3.13"
    libpython_source = python_base / "lib/libpython3.13.so.1.0"
    stdlib_source = python_base / "lib/python3.13"
    for path, label in (
        (python_source, "Python executable"),
        (libpython_source, "libpython"),
        (stdlib_source, "Python standard library"),
    ):
        if not path.exists() or path.is_symlink():
            _fail(
                "CALIBRATION_PACKAGE_RUNTIME_INVALID",
                f"{label} source is absent or symlinked: {path}",
            )

    normalized_members = {
        _relative(relative, f"member {relative!r}"): Path(source).absolute()
        for relative, source in members.items()
    }
    if len(normalized_members) != len(members):
        _fail("CALIBRATION_PACKAGE_SHAPE_INVALID", "duplicate member path")
    referenced = set(roles.values()) | set(stage_fixtures.values())
    required_support = {"devtools/research_run_contract.py"}
    if not referenced <= set(normalized_members) or not required_support <= set(
        normalized_members
    ):
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "portable package omits a fixed role, fixture, or verifier support member",
        )

    root = ExclusiveRunRoot.create(Path(output_root).absolute())
    made: set[str] = set()
    identities: dict[str, dict[str, object]] = {}
    modes: dict[str, int] = {}
    source_records: dict[str, list[dict[str, object]]] = {
        "package-members": [],
        "python-base": [],
        "repository": [],
        "site-packages": [],
    }
    dynamic_objects: list[Path] = []

    for relative, source in sorted(normalized_members.items()):
        raw, _source_mode = _stable_source_bytes(
            source,
            label=f"package member {relative}",
        )
        source_records["package-members"].append(
            _write_member(
                root,
                relative=relative,
                raw=raw,
                mode=0o400,
                made=made,
                identities=identities,
                modes=modes,
            )
        )

    for relative, mode, raw in tracked:
        package_relative = f"{REPOSITORY_PREFIX}/{relative}"
        source_records["repository"].append(
            _write_member(
                root,
                relative=package_relative,
                raw=raw,
                mode=mode,
                made=made,
                identities=identities,
                modes=modes,
            )
        )
    source_records["repository"].append(
        _write_member(
            root,
            relative=CANDIDATE_RELATIVE_PATH,
            raw=candidate_snapshot.data,
            mode=0o444,
            made=made,
            identities=identities,
            modes=modes,
        )
    )

    for source, package_relative in (
        (python_source, PYTHON_RELATIVE_PATH),
        (
            libpython_source,
            f"{PYTHON_PREFIX}/lib/libpython3.13.so.1.0",
        ),
    ):
        raw, mode = _stable_source_bytes(source, label=package_relative)
        source_records["python-base"].append(
            _write_member(
                root,
                relative=package_relative,
                raw=raw,
                mode=mode,
                made=made,
                identities=identities,
                modes=modes,
            )
        )
        if raw.startswith(b"\x7fELF"):
            dynamic_objects.append(source)

    for source in _tree_files(stdlib_source):
        relative = source.relative_to(stdlib_source).as_posix()
        package_relative = f"{PYTHON_PREFIX}/lib/python3.13/{relative}"
        raw, mode = _stable_source_bytes(source, label=package_relative)
        source_records["python-base"].append(
            _write_member(
                root,
                relative=package_relative,
                raw=raw,
                mode=mode,
                made=made,
                identities=identities,
                modes=modes,
            )
        )
        if raw.startswith(b"\x7fELF"):
            dynamic_objects.append(source)

    for source in _tree_files(site_packages):
        relative = source.relative_to(site_packages).as_posix()
        package_relative = f"{SITE_PACKAGES_PREFIX}/{relative}"
        raw, mode = _stable_source_bytes(source, label=package_relative)
        source_records["site-packages"].append(
            _write_member(
                root,
                relative=package_relative,
                raw=raw,
                mode=mode,
                made=made,
                identities=identities,
                modes=modes,
            )
        )
        if raw.startswith(b"\x7fELF"):
            dynamic_objects.append(source)

    host_runtime_identities = _host_runtime_dependencies(
        dynamic_objects=dynamic_objects,
        internal_roots=(python_base, site_packages),
    )
    runtime_python = root.path / PYTHON_RELATIVE_PATH
    runtime_site = root.path / SITE_PACKAGES_PREFIX
    probe_source = (
        "import json,sys;sys.path.insert(0,sys.argv[1]);"
        "import ortools;from ortools.sat.python import cp_model;"
        "m=cp_model.CpModel();x=m.new_bool_var('x');m.maximize(x);"
        "s=cp_model.CpSolver();s.parameters.num_search_workers=1;"
        "status=s.solve(m);print(json.dumps({"
        "'ortools':ortools.__version__,'prefix':sys.prefix,"
        "'status':s.status_name(status)},sort_keys=True,separators=(',',':')))"
    )
    probe = subprocess.run(
        [
            str(runtime_python),
            "-I",
            "-B",
            "-c",
            probe_source,
            str(runtime_site),
        ],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            "LANG": "C",
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "TZ": "UTC",
        },
    )
    try:
        probe_record = json.loads(probe.stdout)
    except json.JSONDecodeError as exc:
        _fail(
            "CALIBRATION_PACKAGE_RUNTIME_INVALID",
            f"copied runtime probe returned invalid JSON: {exc}",
        )
    if (
        probe.returncode != 0
        or type(probe_record) is not dict
        or set(probe_record) != {"ortools", "prefix", "status"}
        or probe_record["prefix"] != str(root.path / PYTHON_PREFIX)
        or probe_record["status"] != "OPTIMAL"
    ):
        _fail(
            "CALIBRATION_PACKAGE_RUNTIME_INVALID",
            "copied Python/OR-Tools runtime probe failed: "
            f"{probe.stderr[-2048:]}",
        )

    source_sets = {
        label: _source_set_descriptor(
            kind={
                "package-members": "CALIBRATION_ROLE_AND_FIXTURE_BYTES",
                "python-base": "COPIED_CPYTHON_BASE_BYTES",
                "repository": "CANDIDATE_COMMIT_PLUS_EXTERNAL_OVERLAY",
                "site-packages": "COPIED_SITE_PACKAGES_BYTES",
            }[label],
            prefix={
                "package-members": ".",
                "python-base": PYTHON_PREFIX,
                "repository": REPOSITORY_PREFIX,
                "site-packages": SITE_PACKAGES_PREFIX,
            }[label],
            records=records,
        )
        for label, records in source_records.items()
    }
    repository_snapshot = {
        "candidate_package_identity": identities[CANDIDATE_RELATIVE_PATH],
        "candidate_source_identity": {
            "path": str(candidate_path),
            "sha256": candidate_snapshot.sha256,
            "size_bytes": candidate_snapshot.size_bytes,
        },
        "repository_head": repository_head,
        "repository_prefix": REPOSITORY_PREFIX,
        "repository_tree": tree,
        "source_set": source_sets["repository"],
    }
    runtime_layout = {
        "cpython_version": "3.13.13",
        "libpython_relative_path": (
            f"{PYTHON_PREFIX}/lib/libpython3.13.so.1.0"
        ),
        "ortools_version": probe_record["ortools"],
        "python_prefix": PYTHON_PREFIX,
        "python_relative_path": PYTHON_RELATIVE_PATH,
        "site_packages_prefix": SITE_PACKAGES_PREFIX,
        "stdlib_prefix": f"{PYTHON_PREFIX}/lib/python3.13",
    }
    return _finish_package(
        root,
        identities=identities,
        modes=modes,
        roles=roles,
        stage_fixtures=stage_fixtures,
        layout=PORTABLE_CANDIDATE_LAYOUT,
        source_sets=source_sets,
        repository_snapshot=repository_snapshot,
        runtime_layout=runtime_layout,
        host_runtime_identities=host_runtime_identities,
    )


def _open_absolute_directory(path: Path) -> int:
    if not path.is_absolute():
        _fail("CALIBRATION_PACKAGE_ROOT_INVALID", "root is not absolute")
    opened = [os.open("/", _DIRECTORY_FLAGS)]
    primary: BaseException | None = None
    try:
        for part in path.parts[1:]:
            opened.append(
                os.open(part, _DIRECTORY_FLAGS, dir_fd=opened[-1])
            )
    except OSError as exc:
        primary = CalibrationPackageError(
            "CALIBRATION_PACKAGE_ROOT_OPEN_FAILED",
            f"{path}: {exc}",
        )
    except BaseException as exc:
        primary = exc
    result = opened[-1] if primary is None else -1
    to_close = opened[:-1] if primary is None else opened
    for descriptor in reversed(to_close):
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "calibration package directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        if result >= 0:
            try:
                os.close(result)
            except BaseException as close_error:
                primary.add_note(
                    "calibration package root cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise primary
    return result


def _open_member(root_fd: int, relative: str) -> int:
    parts = _relative(
        relative,
        "retained member",
        allow_terminal=relative == TERMINAL_PATH,
    ).split("/")
    directories = [os.dup(root_fd)]
    result = -1
    primary: BaseException | None = None
    try:
        for part in parts[:-1]:
            directories.append(
                os.open(part, _DIRECTORY_FLAGS, dir_fd=directories[-1])
            )
        result = os.open(parts[-1], _REGULAR_FLAGS, dir_fd=directories[-1])
    except OSError as exc:
        primary = CalibrationPackageError(
            "CALIBRATION_PACKAGE_OPEN_FAILED",
            f"{relative}: {exc}",
        )
    except BaseException as exc:
        primary = exc
    for descriptor in reversed(directories):
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "calibration package member parent close failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        if result >= 0:
            try:
                os.close(result)
            except BaseException as close_error:
                primary.add_note(
                    "calibration package member cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise primary
    return result


def _read_member(root_fd: int, relative: str) -> tuple[bytes, os.stat_result]:
    descriptor = _open_member(root_fd, relative)
    primary: BaseException | None = None
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size <= 0
        ):
            _fail("CALIBRATION_PACKAGE_MEMBER_INVALID", relative)
        raw = bytearray()
        offset = 0
        while offset < before.st_size:
            block = os.pread(descriptor, min(1024 * 1024, before.st_size - offset), offset)
            if not block:
                _fail("CALIBRATION_PACKAGE_MEMBER_DRIFT", relative)
            raw.extend(block)
            offset += len(block)
        if os.pread(descriptor, 1, before.st_size):
            _fail("CALIBRATION_PACKAGE_MEMBER_DRIFT", relative)
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            _fail("CALIBRATION_PACKAGE_MEMBER_DRIFT", relative)
        result = (bytes(raw), after)
    except BaseException as exc:
        primary = exc
        result = None
    try:
        os.close(descriptor)
    except BaseException as close_error:
        if primary is None:
            raise
        primary.add_note(
            "calibration package member descriptor close failed: "
            f"{type(close_error).__name__}: {close_error}"
        )
    if primary is not None:
        raise primary
    assert result is not None
    return result


def _require_absolute_rejoin(
    root_fd: int,
    absolute: Path,
    *,
    expected: os.stat_result,
) -> None:
    try:
        joined = _open_absolute_directory(absolute)
    except OSError as exc:
        _fail(
            "CALIBRATION_PACKAGE_ROOT_REJOIN_FAILED",
            f"{absolute}: {exc}",
        )
    except CalibrationPackageError as exc:
        if exc.code == "CALIBRATION_PACKAGE_ROOT_OPEN_FAILED":
            _fail(
                "CALIBRATION_PACKAGE_ROOT_REJOIN_FAILED",
                f"{absolute}: {exc}",
            )
        raise
    primary: BaseException | None = None
    try:
        current = os.fstat(root_fd)
        named = os.fstat(joined)
        if (
            current.st_dev != expected.st_dev
            or current.st_ino != expected.st_ino
            or named.st_dev != expected.st_dev
            or named.st_ino != expected.st_ino
        ):
            _fail(
                "CALIBRATION_PACKAGE_ROOT_REJOIN_FAILED",
                str(absolute),
            )
    except BaseException as exc:
        primary = exc
    try:
        os.close(joined)
    except BaseException as close_error:
        if primary is None:
            raise
        primary.add_note(
            "calibration package rejoin descriptor close failed: "
            f"{type(close_error).__name__}: {close_error}"
        )
    if primary is not None:
        raise primary


def verify_retained_calibration_package(
    root_fd: int,
    root: Path | str,
    *,
    expected_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Replay a package while retaining its creation-time directory identity."""

    absolute = Path(os.path.abspath(root))
    try:
        root_stat = os.fstat(root_fd)
    except OSError as exc:
        _fail("CALIBRATION_PACKAGE_ROOT_INVALID", str(exc))
    if not stat.S_ISDIR(root_stat.st_mode):
        _fail("CALIBRATION_PACKAGE_ROOT_INVALID", str(absolute))
    retained_root = ExclusiveRunRoot(
        path=absolute,
        _device=root_stat.st_dev,
        _inode=root_stat.st_ino,
    )
    initial_signature = (
        root_stat.st_dev,
        root_stat.st_ino,
        root_stat.st_mode,
        root_stat.st_nlink,
        root_stat.st_uid,
        root_stat.st_mtime_ns,
        root_stat.st_ctime_ns,
    )
    receipt_raw, _receipt_stat = _read_member(root_fd, TERMINAL_PATH)
    if {
        "path": str(absolute / TERMINAL_PATH),
        "sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "size_bytes": len(receipt_raw),
    } != dict(expected_receipt_identity):
        _fail("CALIBRATION_PACKAGE_RECEIPT_DRIFT", str(absolute))
    receipt = _strict_json(receipt_raw, "calibration package receipt")
    if set(receipt) != {
        "authority_scope",
        "authorizations",
        "host_runtime_identities",
        "layout",
        "manifest",
        "member_identities",
        "member_modes",
        "repository_snapshot",
        "roles",
        "runtime_layout",
        "schema_version",
        "source_sets",
        "stage_fixtures",
        "status",
        "terminal_self_exclusion",
    }:
        _fail("CALIBRATION_PACKAGE_SHAPE_INVALID", "receipt fields drifted")
    if (
        receipt["schema_version"] != PACKAGE_SCHEMA
        or receipt["authority_scope"] != PACKAGE_AUTHORITY_SCOPE
        or receipt["authorizations"] != FALSE_AUTHORIZATIONS
        or receipt["status"] != "CLOSED_NO_AUTHORITY"
        or receipt["layout"]
        not in {FOCUSED_FIXTURE_LAYOUT, PORTABLE_CANDIDATE_LAYOUT}
        or receipt["terminal_self_exclusion"]
        != {
            "excluded_from_manifest": TERMINAL_PATH,
            "self_hash_or_size_present": False,
        }
        or type(receipt["roles"]) is not dict
        or set(cast(dict[str, object], receipt["roles"])) != REQUIRED_ROLES
        or type(receipt["stage_fixtures"]) is not dict
        or set(cast(dict[str, object], receipt["stage_fixtures"])) != STAGES
    ):
        _fail("CALIBRATION_PACKAGE_SHAPE_INVALID", "authority or discriminator drift")
    identities = receipt["member_identities"]
    modes = receipt["member_modes"]
    if (
        type(identities) is not dict
        or type(modes) is not dict
        or set(cast(dict[str, object], identities))
        != set(cast(dict[str, object], modes))
    ):
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "member identity/mode tables are not one exact bijection",
        )
    checked_member_records: dict[str, dict[str, object]] = {}
    for relative, value in cast(dict[str, object], identities).items():
        checked = _validate_identity(value, f"member {relative}")
        mode = cast(dict[str, object], modes).get(relative)
        if (
            checked["path"] != relative
            or type(mode) is not int
            or mode not in {0o400, 0o444, 0o500, 0o555}
        ):
            _fail("CALIBRATION_PACKAGE_IDENTITY_INVALID", relative)
        raw, metadata = _read_member(root_fd, relative)
        if (
            _identity(relative, raw) != checked
            or stat.S_IMODE(metadata.st_mode) != mode
        ):
            _fail("CALIBRATION_PACKAGE_MEMBER_DRIFT", relative)
        checked_member_records[relative] = _member_record(
            relative,
            raw,
            cast(int, mode),
        )
    source_sets = receipt["source_sets"]
    host_runtime = receipt["host_runtime_identities"]
    if type(source_sets) is not dict or type(host_runtime) is not dict:
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "source-set or host-runtime table is malformed",
        )
    checked_host_paths: set[str] = set()
    for label, raw_identity in sorted(cast(dict[str, object], host_runtime).items()):
        if type(label) is not str or not label.startswith("host-runtime-"):
            _fail(
                "CALIBRATION_PACKAGE_RUNTIME_INVALID",
                "host-runtime label set drifted",
            )
        identity = _validate_absolute_identity(
            raw_identity,
            f"host runtime {label}",
        )
        if identity["path"] in checked_host_paths:
            _fail(
                "CALIBRATION_PACKAGE_RUNTIME_INVALID",
                "host-runtime path is duplicated",
            )
        checked_host_paths.add(cast(str, identity["path"]))
    layout = receipt["layout"]
    expected_source_labels = (
        {"fixture-members"}
        if layout == FOCUSED_FIXTURE_LAYOUT
        else {"package-members", "python-base", "repository", "site-packages"}
    )
    if set(cast(dict[str, object], source_sets)) != expected_source_labels:
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "source-set discriminator set drifted",
        )
    selected_paths: dict[str, list[str]] = {}
    if layout == FOCUSED_FIXTURE_LAYOUT:
        selected_paths["fixture-members"] = sorted(checked_member_records)
        if (
            receipt["repository_snapshot"] is not None
            or receipt["runtime_layout"] is not None
            or host_runtime
        ):
            _fail(
                "CALIBRATION_PACKAGE_SHAPE_INVALID",
                "focused fixture gained portable runtime authority",
            )
    else:
        selected_paths["python-base"] = sorted(
            path
            for path in checked_member_records
            if path.startswith(f"{PYTHON_PREFIX}/")
        )
        selected_paths["repository"] = sorted(
            path
            for path in checked_member_records
            if path.startswith(f"{REPOSITORY_PREFIX}/")
        )
        selected_paths["site-packages"] = sorted(
            path
            for path in checked_member_records
            if path.startswith(f"{SITE_PACKAGES_PREFIX}/")
        )
        assigned = {
            path for paths in selected_paths.values() for path in paths
        }
        selected_paths["package-members"] = sorted(
            set(checked_member_records) - assigned
        )
        _validate_portable_layout(
            receipt,
            checked_member_records=checked_member_records,
        )
    if any(not paths for paths in selected_paths.values()):
        _fail(
            "CALIBRATION_PACKAGE_SHAPE_INVALID",
            "one package source set is empty",
        )
    for label, paths in selected_paths.items():
        expected_descriptor = _source_set_descriptor(
            kind={
                "fixture-members": "FOCUSED_FIXTURE_MEMBERS",
                "package-members": "CALIBRATION_ROLE_AND_FIXTURE_BYTES",
                "python-base": "COPIED_CPYTHON_BASE_BYTES",
                "repository": "CANDIDATE_COMMIT_PLUS_EXTERNAL_OVERLAY",
                "site-packages": "COPIED_SITE_PACKAGES_BYTES",
            }[label],
            prefix={
                "fixture-members": ".",
                "package-members": ".",
                "python-base": PYTHON_PREFIX,
                "repository": REPOSITORY_PREFIX,
                "site-packages": SITE_PACKAGES_PREFIX,
            }[label],
            records=[checked_member_records[path] for path in paths],
        )
        if cast(dict[str, object], source_sets)[label] != expected_descriptor:
            _fail(
                "CALIBRATION_PACKAGE_SHAPE_INVALID",
                f"source-set descriptor drifted: {label}",
            )
    verify_artifact_root_closure(
        retained_root,
        receipt["manifest"],
        receipt_present=True,
    )
    final_stat = os.fstat(root_fd)
    final_signature = (
        final_stat.st_dev,
        final_stat.st_ino,
        final_stat.st_mode,
        final_stat.st_nlink,
        final_stat.st_uid,
        final_stat.st_mtime_ns,
        final_stat.st_ctime_ns,
    )
    if final_signature != initial_signature:
        _fail("CALIBRATION_PACKAGE_ROOT_DRIFT", str(absolute))
    _require_absolute_rejoin(root_fd, absolute, expected=root_stat)
    return receipt


def verify_calibration_package(
    root: Path | str,
    *,
    expected_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Independently replay exact members and root closure from a retained root."""

    absolute = Path(os.path.abspath(root))
    root_fd = _open_absolute_directory(absolute)
    try:
        return verify_retained_calibration_package(
            root_fd,
            absolute,
            expected_receipt_identity=expected_receipt_identity,
        )
    finally:
        os.close(root_fd)


class RetainedCalibrationPackage:
    """Verified package descriptor plus retained fixed role/fixture members."""

    def __init__(
        self,
        root_path: Path,
        root_fd: int,
        receipt: dict[str, object],
    ) -> None:
        self.root_path = root_path
        self.root_fd = root_fd
        self.receipt = receipt

    @classmethod
    def open(
        cls,
        root: Path | str,
        *,
        expected_receipt_identity: Mapping[str, object],
    ) -> "RetainedCalibrationPackage":
        absolute = Path(os.path.abspath(root))
        root_fd = _open_absolute_directory(absolute)
        try:
            initial = os.fstat(root_fd)
            receipt = verify_retained_calibration_package(
                root_fd,
                absolute,
                expected_receipt_identity=expected_receipt_identity,
            )
            # Keep a final join in the ownership-transfer frame as well.  A
            # fault hook or future verifier return-path change cannot create a
            # verify-then-transfer gap.
            _require_absolute_rejoin(
                root_fd,
                absolute,
                expected=initial,
            )
        except BaseException as exc:
            try:
                os.close(root_fd)
            except BaseException as close_error:
                exc.add_note(
                    "retained calibration package cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
            raise
        return cls(absolute, root_fd, receipt)

    def open_role(self, role: str) -> int:
        roles = cast(dict[str, object], self.receipt["roles"])
        if role not in REQUIRED_ROLES or type(roles.get(role)) is not str:
            _fail("CALIBRATION_PACKAGE_ROLE_INVALID", role)
        return _open_member(self.root_fd, cast(str, roles[role]))

    def open_fixture(self, stage: str) -> int:
        fixtures = cast(dict[str, object], self.receipt["stage_fixtures"])
        if stage not in STAGES or type(fixtures.get(stage)) is not str:
            _fail("CALIBRATION_PACKAGE_FIXTURE_INVALID", stage)
        return _open_member(self.root_fd, cast(str, fixtures[stage]))

    def close(self) -> None:
        if self.root_fd >= 0:
            descriptor = self.root_fd
            self.root_fd = -1
            os.close(descriptor)

    def __enter__(self) -> "RetainedCalibrationPackage":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
