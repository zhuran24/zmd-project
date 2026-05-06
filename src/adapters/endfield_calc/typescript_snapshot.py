"""Parse endfield-calc TypeScript data files into snapshot-friendly JSON payloads."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

_TYPESCRIPT_REQUIRED = ("items.ts", "recipes.ts", "facilities.ts", "constants.ts")
_CONST_PATTERN_TEMPLATE = r"const\s+{name}\s*=\s*\{{(?P<body>.*?)\}}\s*as\s+const;"
_UPSTREAM_REPOSITORY = "https://github.com/JamboChen/endfield-calc"
_REPOSITORY_RELATIVE_PATHS = {
    "items.ts": PurePosixPath("src/data/items.ts"),
    "recipes.ts": PurePosixPath("src/data/recipes.ts"),
    "facilities.ts": PurePosixPath("src/data/facilities.ts"),
    "constants.ts": PurePosixPath("src/types/constants.ts"),
}


@dataclass(frozen=True)
class _ResolvedTypeScriptSource:
    layout: str
    texts: dict[str, str]
    source_version: str | None = None
    package_name: str | None = None


@dataclass(frozen=True)
class _DirectoryCandidate:
    root: Path
    layout: str


@dataclass(frozen=True)
class _ArchiveCandidate:
    prefix: str
    layout: str


def can_load_typescript_source(source_path: Path) -> bool:
    try:
        load_typescript_source_dir(source_path)
        return True
    except (FileNotFoundError, ValueError, zipfile.BadZipFile):
        return False


# Backwards-compatible public entrypoint; it now accepts:
# 1) a flat fixture directory with the four required TypeScript files,
# 2) an extracted upstream repository root,
# 3) a .zip archive containing the upstream repository layout.
def load_typescript_source_dir(source_dir: Path) -> dict[str, Any]:
    resolved = _resolve_typescript_source(Path(source_dir))

    constants_text = resolved.texts["constants.ts"]
    namespaces = {
        "ItemId": _parse_constant_object(constants_text, "ItemId"),
        "RecipeId": _parse_constant_object(constants_text, "RecipeId"),
        "FacilityId": _parse_constant_object(constants_text, "FacilityId"),
    }

    items = _parse_exported_array(resolved.texts["items.ts"], "items", namespaces)
    recipes = _parse_exported_array(resolved.texts["recipes.ts"], "recipes", namespaces)
    facilities = _parse_exported_array(resolved.texts["facilities.ts"], "facilities", namespaces)

    snapshot_metadata: dict[str, Any] = {
        "source": "JamboChen/endfield-calc TypeScript source",
        "upstream_repository": _UPSTREAM_REPOSITORY,
        "source_license": "MIT",
        "tick_interval_seconds": 1.0,
        "notes": [
            "Parsed from upstream TypeScript data files without adding a runtime dependency.",
            "Accepted input layouts: flat fixture directory, extracted repository root, or zip archive.",
            "Field naming stays source-shaped until the neutral normalized catalog pass runs.",
        ],
        "source_layout": resolved.layout,
    }
    if resolved.source_version:
        snapshot_metadata["source_version"] = resolved.source_version
    if resolved.package_name:
        snapshot_metadata["package_name"] = resolved.package_name

    return {
        "items": items,
        "recipes": recipes,
        "facilities": facilities,
        "snapshot_metadata": snapshot_metadata,
    }


def _resolve_typescript_source(source_path: Path) -> _ResolvedTypeScriptSource:
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"typescript source path not found: {source_path}")
    if source_path.is_file():
        if source_path.suffix.lower() != ".zip":
            raise FileNotFoundError(
                "typescript source input must be a directory or .zip archive: "
                f"{source_path}"
            )
        return _resolve_typescript_archive(source_path)
    return _resolve_typescript_directory(source_path)


def _resolve_typescript_directory(source_dir: Path) -> _ResolvedTypeScriptSource:
    direct_flat = _directory_flat_candidate(source_dir)
    if direct_flat is not None:
        return _materialize_directory_candidate(direct_flat)

    direct_repo = _directory_repo_candidate(source_dir)
    if direct_repo is not None:
        return _materialize_directory_candidate(direct_repo)

    nested_repo_roots = {candidate.root for candidate in _find_nested_directory_repo_candidates(source_dir)}
    if nested_repo_roots:
        selected_root = _select_directory_candidate(
            nested_repo_roots,
            source_dir=source_dir,
            description="nested endfield-calc repository roots",
        )
        return _materialize_directory_candidate(_DirectoryCandidate(root=selected_root, layout="repository_root"))

    nested_flat_roots = {candidate.root for candidate in _find_nested_directory_flat_candidates(source_dir)}
    if nested_flat_roots:
        selected_root = _select_directory_candidate(
            nested_flat_roots,
            source_dir=source_dir,
            description="nested flat TypeScript fixture directories",
        )
        return _materialize_directory_candidate(_DirectoryCandidate(root=selected_root, layout="flat_directory"))

    raise FileNotFoundError(
        "could not locate endfield-calc TypeScript source files under "
        f"{source_dir}; expected either the four flat files, an upstream repo root, "
        "or a zip archive containing that repo layout"
    )


def _directory_flat_candidate(source_dir: Path) -> _DirectoryCandidate | None:
    if all((source_dir / filename).is_file() for filename in _TYPESCRIPT_REQUIRED):
        return _DirectoryCandidate(root=source_dir, layout="flat_directory")
    return None


def _directory_repo_candidate(source_dir: Path) -> _DirectoryCandidate | None:
    if all((source_dir / relative_path).is_file() for relative_path in _REPOSITORY_RELATIVE_PATHS.values()):
        return _DirectoryCandidate(root=source_dir, layout="repository_root")
    return None


def _find_nested_directory_repo_candidates(source_dir: Path) -> list[_DirectoryCandidate]:
    candidates: list[_DirectoryCandidate] = []
    for items_path in source_dir.glob("**/src/data/items.ts"):
        repo_root = items_path.parents[2]
        candidate = _directory_repo_candidate(repo_root)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _find_nested_directory_flat_candidates(source_dir: Path) -> list[_DirectoryCandidate]:
    candidates: list[_DirectoryCandidate] = []
    for items_path in source_dir.glob("**/items.ts"):
        flat_root = items_path.parent
        candidate = _directory_flat_candidate(flat_root)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _select_directory_candidate(candidates: set[Path], *, source_dir: Path, description: str) -> Path:
    if not candidates:
        raise ValueError(f"no candidates available for selection: {description}")
    ordered = sorted(
        candidates,
        key=lambda path: (_relative_depth(path, source_dir), str(path).lower()),
    )
    shallowest_depth = _relative_depth(ordered[0], source_dir)
    shallowest = [path for path in ordered if _relative_depth(path, source_dir) == shallowest_depth]
    if len(shallowest) > 1:
        rendered = ", ".join(_render_relative_path(path, source_dir) for path in shallowest)
        raise ValueError(f"ambiguous {description}: {rendered}")
    return ordered[0]


def _relative_depth(path: Path, base: Path) -> int:
    return len(path.relative_to(base).parts)


def _render_relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _materialize_directory_candidate(candidate: _DirectoryCandidate) -> _ResolvedTypeScriptSource:
    if candidate.layout == "flat_directory":
        file_paths = {filename: candidate.root / filename for filename in _TYPESCRIPT_REQUIRED}
    elif candidate.layout == "repository_root":
        file_paths = {
            filename: candidate.root / relative_path
            for filename, relative_path in _REPOSITORY_RELATIVE_PATHS.items()
        }
    else:
        raise ValueError(f"unsupported directory layout: {candidate.layout}")

    texts = {
        filename: file_path.read_text(encoding="utf-8")
        for filename, file_path in file_paths.items()
    }
    package_name, source_version = _read_directory_package_info(candidate.root)
    return _ResolvedTypeScriptSource(
        layout=candidate.layout,
        texts=texts,
        source_version=source_version,
        package_name=package_name,
    )


def _resolve_typescript_archive(source_zip: Path) -> _ResolvedTypeScriptSource:
    with zipfile.ZipFile(source_zip) as archive:
        entries = _normalized_archive_entries(archive)

        direct_flat_prefixes = _find_archive_flat_prefixes(entries)
        if direct_flat_prefixes:
            selected_prefix = _select_archive_prefix(
                direct_flat_prefixes,
                description="flat TypeScript fixture directories in archive",
            )
            return _materialize_archive_candidate(
                archive,
                entries,
                _ArchiveCandidate(prefix=selected_prefix, layout="zip_archive_flat"),
            )

        repository_prefixes = _find_archive_repository_prefixes(entries)
        if repository_prefixes:
            selected_prefix = _select_archive_prefix(
                repository_prefixes,
                description="endfield-calc repository roots in archive",
            )
            return _materialize_archive_candidate(
                archive,
                entries,
                _ArchiveCandidate(prefix=selected_prefix, layout="zip_archive_repository"),
            )

    raise FileNotFoundError(
        "could not locate endfield-calc TypeScript source files in archive "
        f"{source_zip}; expected either the four flat files or an upstream repo layout"
    )


def _normalized_archive_entries(archive: zipfile.ZipFile) -> dict[str, str]:
    entries: dict[str, str] = {}
    for original_name in archive.namelist():
        if original_name.endswith(("/", "\\")):
            continue
        normalized_name = str(PurePosixPath(original_name.replace("\\", "/")))
        entries[normalized_name] = original_name
    return entries


def _find_archive_flat_prefixes(entries: dict[str, str]) -> set[str]:
    prefixes: set[str] = set()
    for normalized_name in entries:
        prefix = _strip_suffix_prefix(normalized_name, "items.ts")
        if prefix is None:
            continue
        if all(_archive_entry_exists(entries, _join_archive_path(prefix, filename)) for filename in _TYPESCRIPT_REQUIRED):
            prefixes.add(prefix)
    return prefixes


def _find_archive_repository_prefixes(entries: dict[str, str]) -> set[str]:
    prefixes: set[str] = set()
    repo_items_suffix = str(_REPOSITORY_RELATIVE_PATHS["items.ts"])
    for normalized_name in entries:
        prefix = _strip_suffix_prefix(normalized_name, repo_items_suffix)
        if prefix is None:
            continue
        if all(
            _archive_entry_exists(entries, _join_archive_path(prefix, str(relative_path)))
            for relative_path in _REPOSITORY_RELATIVE_PATHS.values()
        ):
            prefixes.add(prefix)
    return prefixes


def _strip_suffix_prefix(normalized_name: str, suffix: str) -> str | None:
    if normalized_name == suffix:
        return ""
    suffix_with_sep = f"/{suffix}"
    if normalized_name.endswith(suffix_with_sep):
        return normalized_name[: -len(suffix_with_sep)]
    return None


def _join_archive_path(prefix: str, relative_path: str) -> str:
    return relative_path if not prefix else f"{prefix}/{relative_path}"


def _archive_entry_exists(entries: dict[str, str], normalized_name: str) -> bool:
    return normalized_name in entries


def _select_archive_prefix(prefixes: set[str], *, description: str) -> str:
    if not prefixes:
        raise ValueError(f"no archive prefixes available for selection: {description}")
    ordered = sorted(prefixes, key=lambda prefix: (_archive_prefix_depth(prefix), prefix.lower()))
    shallowest_depth = _archive_prefix_depth(ordered[0])
    shallowest = [prefix for prefix in ordered if _archive_prefix_depth(prefix) == shallowest_depth]
    if len(shallowest) > 1:
        rendered = ", ".join(prefix or "<archive-root>" for prefix in shallowest)
        raise ValueError(f"ambiguous {description}: {rendered}")
    return ordered[0]


def _archive_prefix_depth(prefix: str) -> int:
    return 0 if not prefix else len([part for part in prefix.split("/") if part])


def _materialize_archive_candidate(
    archive: zipfile.ZipFile,
    entries: dict[str, str],
    candidate: _ArchiveCandidate,
) -> _ResolvedTypeScriptSource:
    if candidate.layout == "zip_archive_flat":
        normalized_paths = {
            filename: _join_archive_path(candidate.prefix, filename)
            for filename in _TYPESCRIPT_REQUIRED
        }
    elif candidate.layout == "zip_archive_repository":
        normalized_paths = {
            filename: _join_archive_path(candidate.prefix, str(relative_path))
            for filename, relative_path in _REPOSITORY_RELATIVE_PATHS.items()
        }
    else:
        raise ValueError(f"unsupported archive layout: {candidate.layout}")

    texts = {
        filename: archive.read(entries[normalized_path]).decode("utf-8")
        for filename, normalized_path in normalized_paths.items()
    }
    package_name, source_version = _read_archive_package_info(archive, entries, candidate.prefix)
    return _ResolvedTypeScriptSource(
        layout=candidate.layout,
        texts=texts,
        source_version=source_version,
        package_name=package_name,
    )


def _read_directory_package_info(root: Path) -> tuple[str | None, str | None]:
    package_path = root / "package.json"
    if not package_path.is_file():
        return None, None
    return _parse_package_info_text(package_path.read_text(encoding="utf-8"))


def _read_archive_package_info(
    archive: zipfile.ZipFile,
    entries: dict[str, str],
    prefix: str,
) -> tuple[str | None, str | None]:
    package_path = _join_archive_path(prefix, "package.json")
    if package_path not in entries:
        return None, None
    return _parse_package_info_text(archive.read(entries[package_path]).decode("utf-8"))


def _parse_package_info_text(text: str) -> tuple[str | None, str | None]:
    package_payload = json.loads(text)
    package_name = package_payload.get("name")
    version = package_payload.get("version")
    return (
        str(package_name) if package_name is not None else None,
        str(version) if version is not None else None,
    )


def _parse_constant_object(text: str, const_name: str) -> dict[str, str]:
    pattern = re.compile(_CONST_PATTERN_TEMPLATE.format(name=re.escape(const_name)), re.S)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"could not locate constant object {const_name!r}")
    body = match.group("body")
    entries = dict(re.findall(r"([A-Za-z0-9_]+)\s*:\s*\"([^\"]+)\"", body))
    if not entries:
        raise ValueError(f"constant object {const_name!r} did not yield any entries")
    return entries


def _parse_exported_array(
    text: str,
    export_name: str,
    namespaces: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    marker = f"export const {export_name}"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"could not locate exported array {export_name!r}")
    equals_index = text.find("=", start)
    if equals_index < 0:
        raise ValueError(f"could not locate '=' for exported array {export_name!r}")
    array_start = text.find("[", equals_index)
    if array_start < 0:
        raise ValueError(f"could not locate '[' for exported array {export_name!r}")
    array_end = _find_matching_bracket(text, array_start)
    array_text = text[array_start : array_end + 1]

    normalized = array_text
    for namespace, mapping in namespaces.items():
        normalized = re.sub(
            rf"\b{re.escape(namespace)}\.([A-Za-z0-9_]+)\b",
            lambda match: json.dumps(_resolve_constant(mapping, namespace, match.group(1))),
            normalized,
        )
    normalized = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', normalized)
    normalized = re.sub(r",\s*([}\]])", r"\1", normalized)
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse exported array {export_name!r} as JSON") from exc
    if not isinstance(payload, list):
        raise ValueError(f"exported array {export_name!r} did not parse into a list")
    if not all(isinstance(entry, dict) for entry in payload):
        raise ValueError(f"exported array {export_name!r} must contain object entries")
    return payload


def _find_matching_bracket(text: str, start_index: int) -> int:
    depth = 0
    in_string = False
    escape = False
    quote_char = '"'
    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote_char:
                in_string = False
            continue
        if char in {"'", '"'}:
            in_string = True
            quote_char = char
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("could not find matching closing bracket")


def _resolve_constant(mapping: dict[str, str], namespace: str, key: str) -> str:
    if key not in mapping:
        raise KeyError(f"{namespace}.{key} is missing from constants.ts")
    return mapping[key]
