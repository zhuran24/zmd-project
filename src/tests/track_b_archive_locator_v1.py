"""Fail-closed R21 locators for the archived Track-B test fixtures."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any


SCHEMA_VERSION = "track-b-test-archive-locators-v1"
PURPOSE = "R21_TRACK_B_TEST_ARCHIVE_LOCATORS"
DEFAULT_LOCATOR_PATH = Path(__file__).resolve().with_name("track_b_archive_locators_v1.json")
MOUNT_POINT = Path("/mnt/wd_external")
ARCHIVE_ROOT = MOUNT_POINT / "archives/zmd-codex-autonomy-20260801"
MOUNT_HINT = (
    "Mount the wd_external archive volume at /mnt/wd_external and verify with "
    "`findmnt -T /mnt/wd_external`."
)
ARCHIVE_NAMESPACE = "zmd-codex-autonomy-20260801"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

_TOP_LEVEL_KEYS = {
    "authorizing",
    "entries",
    "local_bytes_required",
    "mount",
    "purpose",
    "schema_version",
}
_MOUNT_KEYS = {"archive_root", "mount_hint", "mount_point"}
_ENTRY_KEYS = {"archive_locator", "key_artifacts"}
_ARTIFACT_KEYS = {"path", "sha256", "size_bytes"}
_EXPECTED_ENTRIES: dict[str, tuple[str, dict[str, str]]] = {
    "archived_project_zmd_pj_codex_20260801": (
        f"{ARCHIVE_NAMESPACE}:zmd-pj-codex",
        {
            "core_plan": "核心计划书.md",
        },
    ),
    "track_b_b0_1190_20260721": (
        f"{ARCHIVE_NAMESPACE}:baselines/track-b-b0-1190-20260721",
        {
            "r4_formal_authority_receipt": (
                ".artifacts/track_b_b1_r4_1188_22_pb_20260723/"
                "formal-a001-20260723T091800Z-398f8725/authority_receipt.json"
            ),
            "r4_formal_manifest": (
                ".artifacts/track_b_b1_r4_1188_22_pb_20260723/"
                "formal-a001-20260723T091800Z-398f8725/SHA256SUMS"
            ),
            "strict_instance": (
                "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
            ),
        },
    ),
    "track_b_b1_sidewise_membrane_20260724": (
        f"{ARCHIVE_NAMESPACE}:baselines/track-b-b1-sidewise-membrane-20260724",
        {
            "smm2_closeout": (
                ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724/"
                "run-20260723T161302Z-SMM2/closeout-a001/closeout.json"
            ),
            "smm2_geometry_admission": (
                ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724/"
                "run-20260723T161302Z-SMM2/geometry-admission-a002/admission.json"
            ),
            "smm3_authority": (
                ".artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/"
                "run-20260723T192209Z-SMM3-a003/authority-a001/authority.json"
            ),
        },
    ),
    "witness_ea407fa_20260720": (
        f"{ARCHIVE_NAMESPACE}:baselines/witness-ea407fa-20260720",
        {
            "w2d_failure_report_json": (
                "docs/research/witness_constructor_20260717/07_routing_aware/"
                "08_track_w_w2d_failure_report_20260721.json"
            ),
            "w2d_failure_report_markdown": (
                "docs/research/witness_constructor_20260717/07_routing_aware/"
                "08_track_w_w2d_failure_report_20260721.md"
            ),
        },
    ),
}


class ArchiveLocatorError(RuntimeError):
    """A malformed locator or unavailable/drifted archive fixture."""


def _absolute(path: Path | str) -> Path:
    return Path(path).expanduser().absolute()


def _error(code: str, locator: Path, detail: str) -> ArchiveLocatorError:
    return ArchiveLocatorError(f"{code}: {detail} Locator: {locator}")


def _invalid(locator: Path, detail: str) -> ArchiveLocatorError:
    return _error("R21_TRACK_B_ARCHIVE_LOCATOR_INVALID", locator, detail)


def _unavailable(locator: Path, detail: str) -> ArchiveLocatorError:
    return _error(
        "R21_TRACK_B_ARCHIVE_UNAVAILABLE",
        locator,
        (
            f"{detail} Mount point: {MOUNT_POINT}; expected archive root: {ARCHIVE_ROOT}. "
            f"{MOUNT_HINT} This dependency fails closed; no skip/xfail fallback is permitted."
        ),
    )


def _missing(locator: Path, role: str, path: Path, detail: str) -> ArchiveLocatorError:
    return _error(
        "R21_TRACK_B_ARCHIVE_ENTRY_MISSING",
        locator,
        f"role={role}; path={path}; {detail}",
    )


def _drift(locator: Path, role: str, artifact: str, path: Path, detail: str) -> ArchiveLocatorError:
    return _error(
        "R21_TRACK_B_ARCHIVE_IDENTITY_DRIFT",
        locator,
        f"role={role}; artifact={artifact}; path={path}; {detail}",
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON constant {value!r}")


def _canonical_json(value: object) -> bytes:
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


def _exact_mapping(
    value: object,
    expected_keys: set[str],
    *,
    locator: Path,
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        observed = sorted(value) if isinstance(value, Mapping) else type(value).__name__
        raise _invalid(locator, f"{label} keys drifted: expected={sorted(expected_keys)!r}, observed={observed!r}.")
    return value


def _safe_relative(value: object, *, locator: Path, label: str) -> PurePosixPath:
    if type(value) is not str:
        raise _invalid(locator, f"{label} must be a string.")
    relative = PurePosixPath(value)
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or relative.is_absolute()
        or ".." in relative.parts
        or str(relative) != value
    ):
        raise _invalid(locator, f"{label} is not a safe canonical relative path: {value!r}.")
    return relative


def _load_locator(path: Path | str | None) -> tuple[Path, Mapping[str, Any]]:
    locator = _absolute(DEFAULT_LOCATOR_PATH if path is None else path)
    try:
        mode = locator.lstat().st_mode
    except OSError as exc:
        raise _invalid(locator, f"cannot stat locator: {exc}.") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise _invalid(locator, "locator must be a non-symlink regular file.")
    try:
        raw = locator.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise _invalid(locator, f"cannot read strict JSON: {exc}.") from exc
    if _canonical_json(value) != raw:
        raise _invalid(locator, "locator bytes are not canonical one-line JSON.")
    record = _exact_mapping(value, _TOP_LEVEL_KEYS, locator=locator, label="top-level locator")
    if (
        record["schema_version"] != SCHEMA_VERSION
        or record["purpose"] != PURPOSE
        or type(record["authorizing"]) is not bool
        or record["authorizing"] is not False
        or type(record["local_bytes_required"]) is not bool
        or record["local_bytes_required"] is not True
    ):
        raise _invalid(locator, "schema, purpose, or non-authorizing/local-byte boundary drifted.")
    mount = _exact_mapping(record["mount"], _MOUNT_KEYS, locator=locator, label="mount")
    if dict(mount) != {
        "archive_root": str(ARCHIVE_ROOT),
        "mount_hint": MOUNT_HINT,
        "mount_point": str(MOUNT_POINT),
    }:
        raise _invalid(locator, "mount contract drifted.")
    entries = _exact_mapping(
        record["entries"],
        set(_EXPECTED_ENTRIES),
        locator=locator,
        label="archive entries",
    )
    for role, (expected_archive_locator, expected_artifacts) in _EXPECTED_ENTRIES.items():
        entry = _exact_mapping(entries[role], _ENTRY_KEYS, locator=locator, label=f"entry {role}")
        if entry["archive_locator"] != expected_archive_locator:
            raise _invalid(locator, f"entry {role} archive_locator drifted.")
        artifacts = _exact_mapping(
            entry["key_artifacts"],
            set(expected_artifacts),
            locator=locator,
            label=f"entry {role} key_artifacts",
        )
        for artifact_name, expected_path in expected_artifacts.items():
            artifact = _exact_mapping(
                artifacts[artifact_name],
                _ARTIFACT_KEYS,
                locator=locator,
                label=f"entry {role} artifact {artifact_name}",
            )
            relative = _safe_relative(
                artifact["path"],
                locator=locator,
                label=f"entry {role} artifact {artifact_name} path",
            )
            if str(relative) != expected_path:
                raise _invalid(locator, f"entry {role} artifact {artifact_name} path drifted.")
            if type(artifact["sha256"]) is not str or SHA256_RE.fullmatch(artifact["sha256"]) is None:
                raise _invalid(locator, f"entry {role} artifact {artifact_name} SHA-256 is malformed.")
            if type(artifact["size_bytes"]) is not int or artifact["size_bytes"] < 0:
                raise _invalid(locator, f"entry {role} artifact {artifact_name} size is malformed.")
    return locator, record


def _require_directory(path: Path, *, locator: Path, role: str, artifact: str) -> Path:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise _missing(locator, role, path, "required archive directory does not exist.") from exc
    except OSError as exc:
        raise _missing(locator, role, path, f"cannot stat required archive directory: {exc}.") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise _drift(locator, role, artifact, path, "expected a non-symlink directory.")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise _drift(locator, role, artifact, path, f"cannot resolve directory: {exc}.") from exc
    if resolved != path:
        raise _drift(locator, role, artifact, path, f"directory resolves to unexpected path {resolved}.")
    return resolved


def _verify_artifact(
    root: Path,
    role: str,
    artifact_name: str,
    artifact: Mapping[str, Any],
    *,
    locator: Path,
) -> None:
    relative = PurePosixPath(str(artifact["path"]))
    path = root.joinpath(*relative.parts)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise _missing(locator, role, path, f"key artifact {artifact_name} does not exist.") from exc
    except OSError as exc:
        raise _missing(locator, role, path, f"cannot stat key artifact {artifact_name}: {exc}.") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise _drift(locator, role, artifact_name, path, "expected a non-symlink regular file.")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _drift(locator, role, artifact_name, path, f"cannot read key artifact: {exc}.") from exc
    observed_sha256 = hashlib.sha256(raw).hexdigest()
    expected_size = artifact["size_bytes"]
    expected_sha256 = artifact["sha256"]
    if len(raw) != expected_size or observed_sha256 != expected_sha256:
        raise _drift(
            locator,
            role,
            artifact_name,
            path,
            (
                f"expected size={expected_size}, sha256={expected_sha256}; "
                f"observed size={len(raw)}, sha256={observed_sha256}."
            ),
        )


def resolve_archive_roots(
    *roles: str,
    locator_path: Path | str | None = None,
    mount_check: Callable[[Path], bool] | None = None,
) -> dict[str, Path]:
    """Resolve and byte-check requested archive roots without any symlink fallback."""

    locator, record = _load_locator(locator_path)
    requested = roles or tuple(_EXPECTED_ENTRIES)
    if len(set(requested)) != len(requested):
        raise _invalid(locator, f"duplicate requested roles: {requested!r}.")
    unknown = sorted(set(requested) - set(_EXPECTED_ENTRIES))
    if unknown:
        raise _invalid(locator, f"unknown requested roles: {unknown!r}.")

    try:
        mount_mode = MOUNT_POINT.lstat().st_mode
    except OSError as exc:
        raise _unavailable(locator, f"archive mount point cannot be inspected: {exc}.") from exc
    if stat.S_ISLNK(mount_mode) or not stat.S_ISDIR(mount_mode):
        raise _unavailable(locator, "archive mount point is not a non-symlink directory.")
    check = Path.is_mount if mount_check is None else mount_check
    try:
        mounted = check(MOUNT_POINT)
    except OSError as exc:
        raise _unavailable(locator, f"archive mount check failed: {exc}.") from exc
    if mounted is not True:
        raise _unavailable(locator, "archive volume is not mounted at the required mount point.")

    archive_root = _require_directory(
        ARCHIVE_ROOT,
        locator=locator,
        role="archive_namespace",
        artifact="archive_root",
    )
    entries = record["entries"]
    resolved_roots: dict[str, Path] = {}
    for role in requested:
        entry = entries[role]
        _namespace, _separator, relative_text = entry["archive_locator"].partition(":")
        relative = PurePosixPath(relative_text)
        root = _require_directory(
            archive_root.joinpath(*relative.parts),
            locator=locator,
            role=role,
            artifact="archive_root",
        )
        for artifact_name, artifact in entry["key_artifacts"].items():
            _verify_artifact(root, role, artifact_name, artifact, locator=locator)
        resolved_roots[role] = root
    return resolved_roots


__all__ = ["ArchiveLocatorError", "resolve_archive_roots"]
