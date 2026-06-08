#!/usr/bin/env python3
"""Check machine-readable phase review gates.

The gate can be honestly blocked. This script is not a phase-transition button;
it validates that blocked/closed state, review counters, evidence paths, and
front-door documentation agree.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import unicodedata
import sys
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE_DIR = PROJECT_ROOT / "data" / "review_gates"

OPEN_STATUSES = {"blocked_pending_clean_reviews", "open", "blocked"}
CLOSED_STATUS = "closed"
MAJOR_OR_SOUNDNESS_OUTCOMES = {"major_soundness_findings_found"}
ALLOWED_OUTCOMES = {"clean", *MAJOR_OR_SOUNDNESS_OUTCOMES}
CLEAN_FULL_REVIEW_TYPE = "independent_full_external"
REVIEW_EVIDENCE_ROOTS = (".artifacts", "docs/research")
REVIEW_PACKAGE_METADATA_KEYS = {
    "archive_name",
    "archive_sha256",
    "archive_size_bytes",
    "package",
    "source_head",
    "source_list_identity",
}
HEX_DIGITS = set("0123456789abcdef")
PLACEHOLDER_METADATA_VALUES = {"na", "none", "notprovided", "tbd", "unknown"}
SAFE_ARCHIVE_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
FULLWIDTH_COLON = "："
CURRENT_REVIEW_PACKAGE_KEYS = REVIEW_PACKAGE_METADATA_KEYS
REVIEW_HISTORY_ENTRY_KEYS = frozenset(
    {
        "package",
        "review_type",
        "outcome",
        "clean",
        "major_or_soundness_findings",
        "resets_counter",
        "evidence_paths",
    }
)
WINDOWS_RESERVED_ARCHIVE_STEMS = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)
WINDOWS_TRUSTED_GIT_COMMANDS = (
    Path(r"C:\Program Files\Git\cmd\git.exe"),
    Path(r"C:\Program Files\Git\bin\git.exe"),
    Path(r"C:\Program Files (x86)\Git\cmd\git.exe"),
    Path(r"C:\Program Files (x86)\Git\bin\git.exe"),
)
METADATA_DELIMITER_CONFUSABLES = frozenset(
    {
        FULLWIDTH_COLON,
        "︓",  # presentation form for vertical colon
        "﹕",  # small colon
        "꞉",  # modifier letter colon
        "ː",  # modifier letter triangular colon
        "˸",  # modifier letter raised colon
        "∶",  # ratio
        "∷",  # proportion
        "⁚",  # two dot punctuation
        "⦂",  # z notation type colon
        "ꓽ",  # lisu tone letter rendered as a colon-like mark
        "፥",  # ethiopic colon
        "׃",  # hebrew sof pasuq
        "։",  # armenian full stop rendered as a colon-like mark
        "᠄",  # mongolian colon
        "꛴",  # bamum colon
    }
)
HTML_UNESCAPE_MAX_DEPTH = 8
GIT_CONFIG_INCLUDE_SECTION_PREFIXES = ("include", "includeif")
PLACEHOLDER_METADATA_SUBSTRINGS = {
    "notprovided",
    "notavailable",
    "notsupplied",
    "notincluded",
    "notlisted",
    "unavailable",
    "tbd",
    "todo",
    "unknown",
    "absent",
    "omitted",
    "missing",
    "unspecified",
    "placeholder",
    "未提供",
    "未给出",
    "不可用",
    "未知",
    "省略",
    "缺失",
    "占位",
    "待定",
    "待办",
}

# Small, auditable security skeleton for the review-gate vocabulary.  NFKC
# catches compatibility spellings (fullwidth, mathematical alphabets, etc.) but
# not cross-script homoglyphs such as Cyrillic о in "оmitted" or Greek ο in
# "nοt provided".  The gate only needs to normalize a narrow ASCII metadata and
# placeholder vocabulary, so keep this local instead of depending on a broad
# Unicode confusables database at release time.
ASCII_SECURITY_CONFUSABLES = {
    "ɑ": "a",
    "α": "a",
    "а": "a",
    "ь": "b",
    "β": "b",
    "в": "b",
    "ϲ": "c",
    "с": "c",
    "ԁ": "d",
    "е": "e",
    "ε": "e",
    "ϵ": "e",
    "ҽ": "e",
    "ɡ": "g",
    "һ": "h",
    "н": "h",
    "і": "i",
    "ι": "i",
    "ı": "i",
    "ɪ": "i",
    "ј": "j",
    "κ": "k",
    "к": "k",
    "ӏ": "l",
    "ⅼ": "l",
    "м": "m",
    "ո": "n",
    "ο": "o",
    "о": "o",
    "օ": "o",
    "ρ": "p",
    "р": "p",
    "ѕ": "s",
    "τ": "t",
    "т": "t",
    "υ": "u",
    "ս": "u",
    "ν": "v",
    "ѵ": "v",
    "ԝ": "w",
    "ω": "w",
    "χ": "x",
    "х": "x",
    "γ": "y",
    "у": "y",
    "ү": "y",
}


class GateError(RuntimeError):
    pass


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GateError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise GateError(f"{label} must be a list")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise GateError(f"{label} must be a boolean")
    return value


def require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GateError(f"{label} must be an integer")
    return value


def require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GateError(f"{label} must be a non-empty string")
    return value


def require_unpadded_str(value: Any, label: str) -> str:
    text = require_str(value, label)
    if text != text.strip():
        raise GateError(f"{label} must not contain leading or trailing whitespace")
    return text


def _ascii_security_skeleton(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", _deep_html_unescape(value)).casefold()
    skeleton_chars: list[str] = []
    for ch in normalized:
        replacement = ASCII_SECURITY_CONFUSABLES.get(ch, ch)
        for part in unicodedata.normalize("NFKD", replacement):
            if not unicodedata.combining(part):
                skeleton_chars.append(part)
    return unicodedata.normalize("NFKC", "".join(skeleton_chars))


def _deep_html_unescape(value: str) -> str:
    """Decode nested HTML entities used to hide metadata vocabulary/delimiters."""
    decoded = value
    for _ in range(HTML_UNESCAPE_MAX_DEPTH):
        next_decoded = html.unescape(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    return decoded


def _normalized_match_text(value: str) -> str:
    normalized = _ascii_security_skeleton(value)
    return "".join(ch for ch in normalized if ch.isalnum())


def _canonical_package_key(package: str) -> str:
    return _normalized_match_text(package)


def _is_hex_digest(value: str, *, length: int) -> bool:
    return len(value) == length and all(ch in HEX_DIGITS for ch in value.lower())


def _is_placeholder_metadata_value(value: str) -> bool:
    normalized = _normalized_match_text(value)
    return normalized in PLACEHOLDER_METADATA_VALUES or any(
        placeholder in normalized for placeholder in PLACEHOLDER_METADATA_SUBSTRINGS
    )


def _is_windows_reserved_archive_name(value: str) -> bool:
    # Windows treats device names as reserved even when an extension is present
    # (for example, CON.7z or LPT1.7z).  Keep the cross-platform archive
    # identity inside the same safe basename set humans and tooling can share.
    stem = value.split(".", 1)[0].casefold()
    return stem in WINDOWS_RESERVED_ARCHIVE_STEMS


def _is_safe_archive_name(value: str) -> bool:
    return (
        bool(value)
        and value[0].isalnum()
        and value.endswith(".7z")
        and value == PurePosixPath(value).name
        and "\\" not in value
        and all(ch in SAFE_ARCHIVE_NAME_CHARS for ch in value)
        and not _is_windows_reserved_archive_name(value)
    )


def _trusted_git_search_dirs() -> list[str]:
    if os.name == "nt":
        return [str(path.parent) for path in WINDOWS_TRUSTED_GIT_COMMANDS]
    trusted_dirs: list[str] = []
    for raw_dir in os.defpath.split(os.pathsep):
        if not raw_dir or raw_dir == ".":
            continue
        if os.path.isabs(raw_dir):
            trusted_dirs.append(raw_dir)
    return trusted_dirs


def _path_is_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    if is_junction is None:
        return False
    try:
        return bool(is_junction())
    except OSError:
        return False


def _git_authority_path_is_external(git_dir: Path, path: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(git_dir.resolve(strict=True))
    except ValueError:
        return True
    except FileNotFoundError:
        return False
    return False


def _check_git_authority_path(git_dir: Path, path: Path, label: str) -> None:
    if not path.exists():
        return
    if path.is_symlink() or _path_is_junction(path):
        raise GateError(f"project git authority path must not be a symlink or junction: {label}")
    if _git_authority_path_is_external(git_dir, path):
        raise GateError(f"project git authority path resolves outside .git: {label}")


def _check_git_authority_tree(git_dir: Path, path: Path, label: str) -> None:
    _check_git_authority_path(git_dir, path, label)
    if not path.exists() or not path.is_dir():
        return
    for root, dirnames, filenames in os.walk(path):
        root_path = Path(root)
        for name in [*dirnames, *filenames]:
            child = root_path / name
            rel_child = child.relative_to(git_dir).as_posix()
            _check_git_authority_path(git_dir, child, rel_child)


def _git_control_file_text(git_dir: Path, rel_path: str) -> str | None:
    path = git_dir / rel_path
    if not path.exists():
        return None
    _check_git_authority_path(git_dir, path, rel_path)
    if not path.is_file():
        raise GateError(f"project git authority control path must be a file: {rel_path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - source identity controls must be readable.
        raise GateError(f"cannot read project git authority control file {rel_path}: {exc}") from exc


def _reject_git_alternates(git_dir: Path) -> None:
    for rel_path in ("objects/info/alternates", "objects/info/http-alternates"):
        text = _git_control_file_text(git_dir, rel_path)
        if text is not None and text.strip():
            raise GateError(f"project git authority must not use Git alternates: .git/{rel_path}")


def _reject_git_common_dir_indirection(git_dir: Path) -> None:
    for rel_path in ("commondir", "gitdir"):
        text = _git_control_file_text(git_dir, rel_path)
        if text is not None and text.strip():
            raise GateError(f"project git authority must not use worktree/common-dir indirection: .git/{rel_path}")


def _reject_git_config_includes(git_dir: Path) -> None:
    text = _git_control_file_text(git_dir, "config")
    if text is None:
        return
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if not stripped.startswith("[") or "]" not in stripped:
            continue
        section = stripped[1 : stripped.index("]")].strip().casefold()
        section_head = section.split(maxsplit=1)[0]
        if section_head.startswith(GIT_CONFIG_INCLUDE_SECTION_PREFIXES):
            raise GateError("project git authority config must not use include/includeIf indirection")


def _looks_like_bare_gitdir(path: Path) -> bool:
    return (path / "HEAD").exists() and (path / "objects").exists() and (path / "refs").exists()


def _validate_project_git_authority_root() -> Path | None:
    git_dir = PROJECT_ROOT / ".git"
    if git_dir.is_symlink() or _path_is_junction(git_dir):
        raise GateError("project .git must not be a symlink or junction")
    if not git_dir.exists():
        if _looks_like_bare_gitdir(PROJECT_ROOT):
            raise GateError("project git authority must be a worktree with a self-contained .git directory, not a bare gitdir")
        return None
    if not git_dir.is_dir():
        raise GateError("project .git must be a self-contained directory, not a gitdir file/worktree/submodule indirection")
    _check_git_authority_path(git_dir, git_dir / "HEAD", "HEAD")
    _check_git_authority_tree(git_dir, git_dir / "objects", "objects")
    _check_git_authority_tree(git_dir, git_dir / "refs", "refs")
    _check_git_authority_path(git_dir, git_dir / "packed-refs", "packed-refs")
    _reject_git_alternates(git_dir)
    _reject_git_common_dir_indirection(git_dir)
    _reject_git_config_includes(git_dir)
    return git_dir


def _project_git_env() -> dict[str, str]:
    # Git identity is the checked-out project root, not caller-provided Git
    # environment overrides.  Inherited GIT_DIR/GIT_WORK_TREE can otherwise make
    # `git rev-parse HEAD` resolve an unrelated repository while .git is present.
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["PATH"] = os.pathsep.join(_trusted_git_search_dirs())
    if os.name == "nt":
        # subprocess is invoked with an explicit git.exe path on Windows; keep
        # PATHEXT from reintroducing caller-controlled .bat/.cmd lookup semantics
        # into any helper lookup Git may perform for this metadata-only command.
        env["PATHEXT"] = ".EXE"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    return env


def _project_git_command() -> str:
    trusted_dirs = _trusted_git_search_dirs()
    if os.name == "nt":
        for candidate in WINDOWS_TRUSTED_GIT_COMMANDS:
            if candidate.is_file():
                return str(candidate)
        raise GateError(
            "cannot determine project git HEAD: git.exe not found in trusted Git for Windows locations"
        )
    trusted_path = os.pathsep.join(trusted_dirs)
    git_command = shutil.which("git", path=trusted_path)
    if git_command is not None:
        return git_command
    raise GateError(f"cannot determine project git HEAD: git not found on trusted PATH {trusted_path!r}")


def _project_git_head() -> str | None:
    if _validate_project_git_authority_root() is None:
        return None
    try:
        result = subprocess.run(
            [_project_git_command(), "rev-parse", "--verify", "HEAD^{commit}"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=_project_git_env(),
        )
    except Exception as exc:  # noqa: BLE001 - a present .git directory is source identity authority.
        raise GateError(f"cannot determine project git HEAD: {exc}") from exc
    head = result.stdout.strip().lower()
    if not _is_hex_digest(head, length=40):
        raise GateError(f"project git HEAD is not a 40-character hex commit: {head!r}")
    try:
        type_result = subprocess.run(
            [_project_git_command(), "cat-file", "-t", head],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=_project_git_env(),
        )
    except Exception as exc:  # noqa: BLE001 - source_head must name a real commit object.
        raise GateError(f"cannot verify project git HEAD object type: {exc}") from exc
    if type_result.stdout.strip() != "commit":
        raise GateError(f"project git HEAD is not a commit object: {head!r}")
    return head


def _is_review_evidence_path(rel_path: str) -> bool:
    path = PurePosixPath(rel_path)
    if path.is_absolute() or "\\" in rel_path or any(part in {"", ".", ".."} for part in path.parts):
        return False
    parts = path.parts
    return any(parts[: len(root.split("/"))] == tuple(root.split("/")) for root in REVIEW_EVIDENCE_ROOTS)


def _canonical_project_rel_path(rel_path: str) -> str:
    """Return the resolved project-relative identity for an evidence path.

    Evidence paths are security-sensitive provenance, not user-interface paths.
    They therefore have one accepted spelling and one canonical identity.  This
    prevents the same file from being counted multiple times via ``./`` aliases,
    duplicate slashes, symlinks, or other path spellings that resolve to the same
    filesystem object.
    """
    if "\\" in rel_path:
        raise GateError(f"evidence path must use POSIX separators: {rel_path}")
    path = PurePosixPath(rel_path)
    if path.is_absolute():
        raise GateError(f"evidence path must be project-relative: {rel_path}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise GateError(f"evidence path must be normalized without '.', '..', or empty parts: {rel_path}")
    canonical = path.as_posix()
    if canonical != rel_path:
        raise GateError(f"evidence path must use canonical spelling {canonical!r}: {rel_path}")

    full_path = PROJECT_ROOT / canonical
    try:
        project_root = PROJECT_ROOT.resolve(strict=True)
        resolved = full_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise GateError(f"missing evidence path: {canonical}") from exc
    except Exception as exc:  # noqa: BLE001 - report unreadable/unresolvable paths as gate failures.
        raise GateError(f"cannot resolve evidence path {canonical}: {exc}") from exc

    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise GateError(f"evidence path escapes project root: {canonical}") from exc

    if not resolved.is_file():
        raise GateError(f"evidence path must be a regular file: {canonical}")

    return resolved.relative_to(project_root).as_posix()


def _evidence_matches_package(rel_path: str, package: str) -> bool:
    """Return whether an evidence artifact is tied to the claimed package.

    This intentionally stays syntactic and local: it does not try to judge review
    independence, but it prevents a closed gate from counting arbitrary existing
    docs, duplicated front-door files, or old reset artifacts as fresh clean
    review provenance.
    """
    full_path = PROJECT_ROOT / rel_path
    try:
        with full_path.open("r", encoding="utf-8") as evidence_file:
            text = evidence_file.read(200_000)
    except Exception as exc:  # noqa: BLE001 - gate evidence must be readable, not path-name only.
        raise GateError(f"cannot read evidence path {rel_path}: {exc}") from exc
    # The filename is not provenance.  Require the evidence body itself to bind
    # to the claimed review package so three package-named copies of one generic
    # report cannot satisfy three clean-review slots.
    haystack = _normalized_match_text(text)
    package_norm = _normalized_match_text(package)
    return bool(package_norm) and package_norm in haystack


def _evidence_metadata_key(raw_key: str) -> str:
    normalized_key = _ascii_security_skeleton(raw_key)
    token = "".join(ch for ch in normalized_key if ch.isalnum())
    aliases = {
        "archivename": "archive_name",
        "archivesha": "archive_sha256",
        "archivesha256": "archive_sha256",
        "sha256": "archive_sha256",
        "archivesize": "archive_size_bytes",
        "archivesizebyte": "archive_size_bytes",
        "archivesizebytes": "archive_size_bytes",
        "size": "archive_size_bytes",
        "sizebytes": "archive_size_bytes",
        "package": "package",
        "head": "source_head",
        "commit": "source_head",
        "sourcehead": "source_head",
        "sourcecommit": "source_head",
        "sourcecommithead": "source_head",
        "sourcelistidentity": "source_list_identity",
    }
    if token in aliases:
        return aliases[token]
    key = normalized_key.strip().replace("-", "_").replace(" ", "_")
    while "__" in key:
        key = key.replace("__", "_")
    return key


def _canonical_outcome(raw_outcome: str) -> str:
    outcome = raw_outcome.strip().casefold().replace("-", "_").replace(" ", "_")
    while "__" in outcome:
        outcome = outcome.replace("__", "_")
    return outcome


def _read_evidence_text(rel_path: str) -> str:
    full_path = PROJECT_ROOT / rel_path
    try:
        return full_path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - gate evidence must be readable.
        raise GateError(f"cannot read evidence path {rel_path}: {exc}") from exc


def _is_metadata_delimiter_confusable(ch: str) -> bool:
    if ch == ":":
        return False
    if ch in METADATA_DELIMITER_CONFUSABLES:
        return True
    if unicodedata.normalize("NFKC", ch) == ":":
        return True
    name = unicodedata.name(ch, "")
    return "COLON" in name or "RATIO" in name


def _confusable_metadata_delimiter_error(line: str, rel_path: str) -> str | None:
    line = _deep_html_unescape(line)
    ascii_colon_index = line.find(":")
    scan_limit = ascii_colon_index if ascii_colon_index != -1 else len(line)
    for index, ch in enumerate(line[:scan_limit]):
        if not _is_metadata_delimiter_confusable(ch):
            continue
        key = _evidence_metadata_key(line[:index])
        if key in REVIEW_PACKAGE_METADATA_KEYS:
            return f"evidence metadata key {key!r} must use ASCII colon delimiter: {rel_path}"
    return None


def _markdown_table_metadata_error(line: str, rel_path: str) -> str | None:
    stripped = unicodedata.normalize("NFKC", _deep_html_unescape(line).strip())
    if "|" not in stripped:
        return None
    cells = [cell.strip(" `*_\t") for cell in stripped.strip("|").split("|")]
    if len(cells) < 2:
        return None
    for cell in cells:
        compact = cell.replace(" ", "").replace(":", "")
        if not compact or set(compact) <= {"-"}:
            continue
        key = _evidence_metadata_key(cell)
        if key in REVIEW_PACKAGE_METADATA_KEYS:
            return f"evidence metadata key {key!r} must use ASCII colon delimiter, not table syntax: {rel_path}"
    return None


HTML_TABLE_RE = re.compile(r"<\s*table\b.*?<\s*/\s*table\s*>", re.IGNORECASE | re.DOTALL)
HTML_TABLE_CELL_RE = re.compile(r"<\s*t[dh]\b[^>]*>(.*?)<\s*/\s*t[dh]\s*>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)


def _html_cell_text(cell: str) -> str:
    return _deep_html_unescape(HTML_TAG_RE.sub(" ", cell)).strip(" `*_\t\r\n")


def _html_table_metadata_error(text: str, rel_path: str) -> str | None:
    decoded_text = _deep_html_unescape(text)
    lowered = decoded_text.casefold()
    if not any(token in lowered for token in ("<table", "<td", "<th")):
        return None
    chunks = HTML_TABLE_RE.findall(decoded_text) or [decoded_text]
    for chunk in chunks:
        if not any(token in chunk.casefold() for token in ("<table", "<td", "<th")):
            continue
        cells = HTML_TABLE_CELL_RE.findall(chunk)
        if not cells and "<table" in chunk.casefold():
            cells = [chunk]
        for cell in cells:
            cell_text = _html_cell_text(cell)
            if not cell_text:
                continue
            key = _evidence_metadata_key(cell_text)
            if key in REVIEW_PACKAGE_METADATA_KEYS:
                return f"evidence metadata key {key!r} must use ASCII colon delimiter, not HTML table syntax: {rel_path}"
    return None


def _delimited_metadata_error(line: str, rel_path: str) -> str | None:
    stripped = unicodedata.normalize("NFKC", _deep_html_unescape(line).strip())
    for delimiter in (",", ";"):
        if delimiter not in stripped:
            continue
        cells = [cell.strip(" `*_[]\t") for cell in stripped.split(delimiter)]
        if len(cells) < 2:
            continue
        for cell in cells:
            if not cell:
                continue
            key = _evidence_metadata_key(cell)
            if key in REVIEW_PACKAGE_METADATA_KEYS:
                return f"evidence metadata key {key!r} must use ASCII colon delimiter, not delimited syntax: {rel_path}"
    return None


def _extract_evidence_metadata(rel_path: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    text = _read_evidence_text(rel_path)
    html_table_error = _html_table_metadata_error(text, rel_path)
    if html_table_error is not None:
        raise GateError(html_table_error)
    for raw_line in text.splitlines():
        line = _deep_html_unescape(raw_line)
        delimiter_error = _confusable_metadata_delimiter_error(line, rel_path)
        if delimiter_error is not None:
            raise GateError(delimiter_error)
        table_error = _markdown_table_metadata_error(line, rel_path)
        if table_error is not None:
            raise GateError(table_error)
        delimited_error = _delimited_metadata_error(line, rel_path)
        if delimited_error is not None:
            raise GateError(delimited_error)
        if ":" not in line:
            continue
        raw_key, raw_value = line.split(":", 1)
        key = _evidence_metadata_key(raw_key)
        if key not in REVIEW_PACKAGE_METADATA_KEYS:
            continue
        value = raw_value.strip()
        if not value:
            continue
        if key in metadata:
            raise GateError(f"duplicate evidence metadata key {key!r}: {rel_path}")
        metadata[key] = value
    return metadata


def _check_current_review_package_keys(package: dict[str, Any]) -> None:
    for raw_key in package:
        if not isinstance(raw_key, str):
            raise GateError("current_review_package keys must be strings")
        canonical_key = _evidence_metadata_key(raw_key)
        if raw_key in CURRENT_REVIEW_PACKAGE_KEYS:
            continue
        if canonical_key in CURRENT_REVIEW_PACKAGE_KEYS:
            raise GateError(
                f"current_review_package key {raw_key!r} conflicts with canonical key {canonical_key!r}; "
                "use exact schema keys"
            )
        raise GateError(f"current_review_package has unsupported key: {raw_key!r}")


def _review_history_entry_key(raw_key: str) -> str:
    normalized_key = _ascii_security_skeleton(raw_key)
    token = "".join(ch for ch in normalized_key if ch.isalnum())
    aliases = {
        "package": "package",
        "reviewpackage": "package",
        "reviewtype": "review_type",
        "type": "review_type",
        "outcome": "outcome",
        "verdict": "outcome",
        "clean": "clean",
        "isclean": "clean",
        "major": "major_or_soundness_findings",
        "majorfinding": "major_or_soundness_findings",
        "majorfindings": "major_or_soundness_findings",
        "soundnessfinding": "major_or_soundness_findings",
        "soundnessfindings": "major_or_soundness_findings",
        "majororsoundnessfinding": "major_or_soundness_findings",
        "majororsoundnessfindings": "major_or_soundness_findings",
        "majororsoundnessfindingscount": "major_or_soundness_findings",
        "finding": "major_or_soundness_findings",
        "findings": "major_or_soundness_findings",
        "findingcount": "major_or_soundness_findings",
        "resetscounter": "resets_counter",
        "resetcounter": "resets_counter",
        "resetscleanreviewcounter": "resets_counter",
        "evidence": "evidence_paths",
        "evidencepath": "evidence_paths",
        "evidencepaths": "evidence_paths",
    }
    if token in aliases:
        return aliases[token]
    key = normalized_key.strip().replace("-", "_").replace(" ", "_")
    while "__" in key:
        key = key.replace("__", "_")
    return key


def _check_review_history_entry_keys(entry: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    for raw_key in entry:
        if not isinstance(raw_key, str):
            errors.append(f"review_history[{index}] keys must be strings")
            continue
        canonical_key = _review_history_entry_key(raw_key)
        if raw_key in REVIEW_HISTORY_ENTRY_KEYS:
            continue
        if canonical_key in REVIEW_HISTORY_ENTRY_KEYS:
            errors.append(
                f"review_history[{index}] key {raw_key!r} conflicts with canonical key {canonical_key!r}; "
                "use exact schema keys"
            )
        else:
            errors.append(f"review_history[{index}] has unsupported key: {raw_key!r}")
    return errors


def _validate_current_review_package(raw_package: Any) -> dict[str, Any] | None:
    if raw_package is None:
        return None
    package = require_mapping(raw_package, "current_review_package")
    _check_current_review_package_keys(package)
    archive_name = require_unpadded_str(package.get("archive_name"), "current_review_package.archive_name")
    package_key = require_unpadded_str(package.get("package"), "current_review_package.package")
    archive_sha256 = require_unpadded_str(
        package.get("archive_sha256"),
        "current_review_package.archive_sha256",
    ).lower()
    archive_size_bytes = require_int(
        package.get("archive_size_bytes"),
        "current_review_package.archive_size_bytes",
    )
    source_head = require_unpadded_str(package.get("source_head"), "current_review_package.source_head").lower()
    source_list_identity = require_unpadded_str(
        package.get("source_list_identity"),
        "current_review_package.source_list_identity",
    )
    if not _is_safe_archive_name(archive_name):
        raise GateError(
            "current_review_package.archive_name must be a path-free ASCII .7z archive basename"
        )
    if not _is_hex_digest(archive_sha256, length=64):
        raise GateError("current_review_package.archive_sha256 must be a 64-character hex digest")
    if archive_size_bytes <= 0:
        raise GateError("current_review_package.archive_size_bytes must be positive")
    if not _is_hex_digest(source_head, length=40):
        raise GateError("current_review_package.source_head must be a 40-character hex commit")
    project_head = _project_git_head()
    if project_head is not None and source_head != project_head:
        raise GateError(f"current_review_package.source_head must match project git HEAD {project_head}: {source_head}")
    if package_key != archive_name:
        raise GateError("current_review_package.package must exactly match archive_name")
    if _is_placeholder_metadata_value(source_list_identity):
        raise GateError("current_review_package.source_list_identity must not be a placeholder")
    return {
        "archive_name": archive_name,
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_size_bytes,
        "package": package_key,
        "source_head": source_head,
        "source_list_identity": source_list_identity,
    }


def _check_evidence_matches_current_package(
    rel_path: str,
    current_package: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    try:
        metadata = _extract_evidence_metadata(rel_path)
    except GateError as exc:
        return [str(exc)]

    expected = {
        "archive_name": current_package["archive_name"],
        "archive_sha256": current_package["archive_sha256"],
        "archive_size_bytes": str(current_package["archive_size_bytes"]),
        "package": current_package["package"],
        "source_head": current_package["source_head"],
        "source_list_identity": current_package["source_list_identity"],
    }
    for key, expected_value in expected.items():
        value = metadata.get(key)
        if value is None:
            errors.append(f"evidence path {rel_path} missing current package metadata: {key}")
            continue
        if key in {"archive_sha256", "source_head"}:
            value = value.lower()
        if value != expected_value:
            errors.append(f"evidence path {rel_path} current package metadata {key} {value!r} != {expected_value!r}")
    return errors


def _evidence_file_identity(rel_path: str) -> tuple[int, int]:
    try:
        stat_result = (PROJECT_ROOT / rel_path).stat()
    except Exception as exc:  # noqa: BLE001 - evidence identity must be inspectable.
        raise GateError(f"cannot stat evidence path {rel_path}: {exc}") from exc
    return (int(stat_result.st_dev), int(stat_result.st_ino))


def _evidence_content_digest(rel_path: str) -> str:
    digest = hashlib.sha256()
    try:
        with (PROJECT_ROOT / rel_path).open("rb") as evidence_file:
            for chunk in iter(lambda: evidence_file.read(1024 * 1024), b""):
                digest.update(chunk)
    except Exception as exc:  # noqa: BLE001 - evidence bytes must be readable.
        raise GateError(f"cannot read evidence bytes {rel_path}: {exc}") from exc
    return digest.hexdigest()


def load_gate(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
    except Exception as exc:  # noqa: BLE001
        raise GateError(f"cannot read {rel(path)}: {exc}") from exc
    return require_mapping(payload, rel(path))


def _is_not_implemented_raise(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Raise) or stmt.exc is None:
        return False
    exc = stmt.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"


def _function_body_is_fail_closed_not_implemented(source_path: Path, symbol: str) -> bool:
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - gate should report parse/read failures.
        raise GateError(f"cannot inspect source boundary {rel(source_path)}: {exc}") from exc

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != symbol:
            continue
        body = list(node.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        if body and isinstance(body[0], ast.Delete):
            body = body[1:]
        return len(body) == 1 and _is_not_implemented_raise(body[0])
    raise GateError(f"source boundary symbol not found: {rel(source_path)}::{symbol}")


def _review_history_clean_counter(
    records: list[dict[str, Any]],
    *,
    latest_reset_index: int,
) -> int:
    """Derive the consecutive clean full-review counter from review_history.

    The JSON counter is intentionally redundant: it is a human-readable summary,
    not authority.  A gate is ready only when the review history after the latest
    reset contains the required consecutive independent full external reviews.
    """
    count = 0
    for record in records[latest_reset_index + 1 :]:
        if record["review_type"] != CLEAN_FULL_REVIEW_TYPE:
            continue
        if record["clean"] and record["major"] == 0 and not record["resets_counter"]:
            count += 1
        else:
            count = 0
    return count


def _check_source_boundaries(boundaries: list[Any], *, status: str) -> list[str]:
    errors: list[str] = []
    for index, raw_boundary in enumerate(boundaries):
        boundary = require_mapping(raw_boundary, f"source_boundaries[{index}]")
        rel_path = require_str(boundary.get("path"), f"source_boundaries[{index}].path")
        symbol = require_str(boundary.get("symbol"), f"source_boundaries[{index}].symbol")
        required_state = require_str(
            boundary.get("required_state_until_closed"),
            f"source_boundaries[{index}].required_state_until_closed",
        )
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            errors.append(f"source boundary target missing: {rel_path}")
            continue
        if status != CLOSED_STATUS and required_state == "fail_closed_not_implemented":
            if not _function_body_is_fail_closed_not_implemented(full_path, symbol):
                errors.append(f"source boundary no longer fail-closed before gate close: {rel_path}::{symbol}")
        elif required_state != "fail_closed_not_implemented":
            errors.append(f"unsupported source boundary required_state_until_closed: {required_state}")
    return errors


def _check_evidence_paths(
    paths: list[Any],
    label: str,
    *,
    required: bool = False,
    package: str | None = None,
    current_review_package: dict[str, Any] | None = None,
    require_review_artifact: bool = False,
) -> tuple[list[str], list[str], list[tuple[int, int]], list[str]]:
    errors: list[str] = []
    canonical_paths: list[str] = []
    file_identities: list[tuple[int, int]] = []
    content_digests: list[str] = []
    if required and not paths:
        errors.append(f"{label}.evidence_paths must contain at least one evidence path")
    seen_paths: set[str] = set()
    seen_file_identities: set[tuple[int, int]] = set()
    seen_content_digests: set[str] = set()
    for raw_path in paths:
        rel_path = require_str(raw_path, f"{label} evidence path")
        try:
            canonical_path = _canonical_project_rel_path(rel_path)
            file_identity = _evidence_file_identity(canonical_path)
            content_digest = _evidence_content_digest(canonical_path)
        except GateError as exc:
            errors.append(str(exc))
            continue
        canonical_paths.append(canonical_path)
        file_identities.append(file_identity)
        content_digests.append(content_digest)
        if canonical_path in seen_paths:
            errors.append(f"{label}.evidence_paths contains duplicate path: {rel_path}")
        seen_paths.add(canonical_path)
        if file_identity in seen_file_identities:
            errors.append(f"{label}.evidence_paths contains duplicate physical file: {rel_path}")
        seen_file_identities.add(file_identity)
        if content_digest in seen_content_digests:
            errors.append(f"{label}.evidence_paths contains duplicate evidence content: {rel_path}")
        seen_content_digests.add(content_digest)
        if require_review_artifact and (
            not _is_review_evidence_path(rel_path) or not _is_review_evidence_path(canonical_path)
        ):
            errors.append(
                f"{label}.evidence_paths must point to a review/research artifact "
                f"under {', '.join(REVIEW_EVIDENCE_ROOTS)}: {rel_path}"
            )
        if current_review_package is not None:
            errors.extend(_check_evidence_matches_current_package(canonical_path, current_review_package))
        else:
            try:
                package_matches = package is None or _evidence_matches_package(canonical_path, package)
            except GateError as exc:
                errors.append(str(exc))
                continue
            if not package_matches:
                errors.append(f"{label}.evidence_paths must match review package {package!r}: {rel_path}")
    return errors, canonical_paths, file_identities, content_digests


def _check_doc_markers(markers: list[Any]) -> list[str]:
    errors: list[str] = []
    for index, raw_marker in enumerate(markers):
        marker = require_mapping(raw_marker, f"required_doc_markers[{index}]")
        rel_path = require_str(marker.get("path"), f"required_doc_markers[{index}].path")
        needle = require_str(marker.get("contains"), f"required_doc_markers[{index}].contains")
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            errors.append(f"required doc marker target missing: {rel_path}")
            continue
        text = full_path.read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"required marker not found in {rel_path}: {needle!r}")
    return errors


def check_gate(path: Path) -> tuple[str, list[str]]:
    gate = load_gate(path)
    errors: list[str] = []

    if gate.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    gate_id = require_str(gate.get("gate_id"), "gate_id")
    status = require_str(gate.get("status"), "status")
    if status not in OPEN_STATUSES | {CLOSED_STATUS}:
        errors.append(f"unsupported status: {status}")

    close_policy = require_mapping(gate.get("close_policy"), "close_policy")
    counters = require_mapping(gate.get("counters"), "counters")
    next_phase_entry = require_mapping(gate.get("next_phase_entry"), "next_phase_entry")
    last_reset = require_mapping(gate.get("last_reset"), "last_reset")
    history = require_list(gate.get("review_history"), "review_history")
    current_review_package = _validate_current_review_package(gate.get("current_review_package"))

    required = require_int(
        close_policy.get("required_consecutive_clean_full_reviews"),
        "close_policy.required_consecutive_clean_full_reviews",
    )
    counted_required = require_int(
        counters.get("required_consecutive_clean_full_reviews"),
        "counters.required_consecutive_clean_full_reviews",
    )
    clean_count = require_int(
        counters.get("consecutive_clean_full_reviews_after_reset"),
        "counters.consecutive_clean_full_reviews_after_reset",
    )
    remaining = require_int(
        counters.get("remaining_clean_full_reviews"),
        "counters.remaining_clean_full_reviews",
    )
    if required <= 0:
        errors.append("required clean-review count must be positive")
    if counted_required != required:
        errors.append("counter required count disagrees with close_policy")
    if clean_count < 0:
        errors.append("clean review count cannot be negative")
    expected_remaining = max(required - clean_count, 0)
    if remaining != expected_remaining:
        errors.append(f"remaining_clean_full_reviews {remaining} != expected {expected_remaining}")

    next_allowed = require_bool(next_phase_entry.get("allowed"), "next_phase_entry.allowed")
    if status == CLOSED_STATUS:
        if clean_count < required:
            errors.append("closed gate must have enough consecutive clean full reviews")
        if not next_allowed:
            errors.append("closed gate should allow next phase entry")
    else:
        if clean_count >= required:
            errors.append("open/blocked gate has enough clean reviews; status should be closed")
        if next_allowed:
            errors.append("open/blocked gate must not allow next phase entry")

    reset_package = require_str(last_reset.get("review_package"), "last_reset.review_package")
    if not require_bool(last_reset.get("resets_counter"), "last_reset.resets_counter"):
        errors.append("last_reset.resets_counter must be true")
    (
        last_reset_errors,
        last_reset_canonical_evidence_paths,
        _last_reset_file_identities,
        _last_reset_content_digests,
    ) = _check_evidence_paths(
        require_list(last_reset.get("evidence_paths"), "last_reset.evidence_paths"),
        "last_reset",
        required=True,
        package=reset_package,
        require_review_artifact=True,
    )
    errors.extend(last_reset_errors)

    reset_entries = []
    all_reset_entries: list[tuple[int, str]] = []
    history_records: list[dict[str, Any]] = []
    reset_review_evidence_owner: dict[str, int] = {}
    reset_review_file_owner: dict[tuple[int, int], int] = {}
    reset_review_content_owner: dict[str, int] = {}
    reset_review_package_owner: dict[str, int] = {}
    clean_review_evidence_owner: dict[str, int] = {}
    clean_review_file_owner: dict[tuple[int, int], int] = {}
    clean_review_content_owner: dict[str, int] = {}
    for index, raw_entry in enumerate(history):
        entry = require_mapping(raw_entry, f"review_history[{index}]")
        errors.extend(_check_review_history_entry_keys(entry, index))
        package = require_str(entry.get("package"), f"review_history[{index}].package")
        review_type = require_str(entry.get("review_type"), f"review_history[{index}].review_type")
        outcome = require_str(entry.get("outcome"), f"review_history[{index}].outcome")
        clean = require_bool(entry.get("clean"), f"review_history[{index}].clean")
        major = require_int(
            entry.get("major_or_soundness_findings"),
            f"review_history[{index}].major_or_soundness_findings",
        )
        if "resets_counter" not in entry:
            errors.append(f"review_history[{index}].resets_counter is required")
            resets_counter = False
        else:
            resets_counter = require_bool(
                entry.get("resets_counter"),
                f"review_history[{index}].resets_counter",
            )
        history_records.append(
            {
                "index": index,
                "package": package,
                "review_type": review_type,
                "outcome": outcome,
                "clean": clean,
                "major": major,
                "resets_counter": resets_counter,
                "evidence_paths": require_list(entry.get("evidence_paths"), f"review_history[{index}].evidence_paths"),
            }
        )
        canonical_outcome = _canonical_outcome(outcome)
        if canonical_outcome not in ALLOWED_OUTCOMES:
            errors.append(f"review_history[{index}] has unsupported outcome: {outcome!r}")
        elif outcome != canonical_outcome:
            errors.append(
                f"review_history[{index}].outcome must use canonical spelling {canonical_outcome!r}: {outcome!r}"
            )
        outcome_reports_major = canonical_outcome in MAJOR_OR_SOUNDNESS_OUTCOMES
        if major < 0:
            errors.append(f"review_history[{index}].major_or_soundness_findings cannot be negative: {major}")
        if clean and canonical_outcome != "clean":
            errors.append(f"review_history[{index}] is clean but outcome is {outcome!r}")
        if not clean and canonical_outcome == "clean":
            errors.append(f"review_history[{index}] outcome is clean but clean=false")
        if clean and major != 0:
            errors.append(f"review_history[{index}] is clean but has {major} major/soundness findings")
        if clean and resets_counter:
            errors.append(f"review_history[{index}] is clean but resets the clean-review counter")
        if outcome_reports_major and major <= 0:
            errors.append(
                f"review_history[{index}] outcome {outcome!r} requires a positive major_or_soundness_findings count"
            )
        if not clean and major == 0 and resets_counter:
            errors.append(f"review_history[{index}] resets counter but has zero major/soundness findings")
        if not clean and (major > 0 or outcome_reports_major) and not resets_counter:
            errors.append(f"review_history[{index}] has major/soundness findings but does not reset counter")
        if resets_counter:
            all_reset_entries.append((index, package))
            reset_review_package_owner[_canonical_package_key(package)] = index
            if package == reset_package:
                reset_entries.append(index)
        evidence_paths = history_records[-1]["evidence_paths"]
        requires_evidence = resets_counter or (
            review_type == CLEAN_FULL_REVIEW_TYPE and clean and major == 0 and not resets_counter
        )
        requires_clean_review_evidence = (
            review_type == CLEAN_FULL_REVIEW_TYPE and clean and major == 0 and not resets_counter
        )
        (
            evidence_errors,
            canonical_evidence_paths,
            evidence_file_identities,
            evidence_content_digests,
        ) = _check_evidence_paths(
            evidence_paths,
            f"review_history[{index}]",
            required=requires_evidence,
            package=package if requires_evidence else None,
            current_review_package=current_review_package if requires_clean_review_evidence else None,
            require_review_artifact=requires_evidence,
        )
        errors.extend(evidence_errors)
        history_records[-1]["canonical_evidence_paths"] = canonical_evidence_paths
        if resets_counter:
            for canonical_path in canonical_evidence_paths:
                reset_review_evidence_owner[canonical_path] = index
            for file_identity in evidence_file_identities:
                reset_review_file_owner[file_identity] = index
            for content_digest in evidence_content_digests:
                reset_review_content_owner[content_digest] = index
        if requires_clean_review_evidence:
            package_key = _canonical_package_key(package)
            if current_review_package is None:
                errors.append(f"review_history[{index}] clean review requires current_review_package identity")
            else:
                if package != current_review_package["package"]:
                    errors.append(
                        f"review_history[{index}].package must exactly match current_review_package.package "
                        f"{current_review_package['package']!r}: {package}"
                    )
            reset_package_owner = reset_review_package_owner.get(package_key)
            if reset_package_owner is not None:
                errors.append(
                    f"review_history[{index}] reuses reset-review package "
                    f"from review_history[{reset_package_owner}]: {package}"
                )
            for canonical_path in canonical_evidence_paths:
                reset_owner = reset_review_evidence_owner.get(canonical_path)
                if reset_owner is not None:
                    errors.append(
                        f"review_history[{index}] reuses reset-review evidence path "
                        f"from review_history[{reset_owner}]: {canonical_path}"
                    )
                owner = clean_review_evidence_owner.get(canonical_path)
                if owner is not None:
                    errors.append(
                        f"review_history[{index}] reuses clean-review evidence path "
                        f"from review_history[{owner}]: {canonical_path}"
                    )
                else:
                    clean_review_evidence_owner[canonical_path] = index
            for file_identity in evidence_file_identities:
                reset_owner = reset_review_file_owner.get(file_identity)
                if reset_owner is not None:
                    errors.append(
                        f"review_history[{index}] reuses reset-review physical evidence file "
                        f"from review_history[{reset_owner}]"
                    )
                owner = clean_review_file_owner.get(file_identity)
                if owner is not None:
                    errors.append(
                        f"review_history[{index}] reuses clean-review physical evidence file "
                        f"from review_history[{owner}]"
                    )
                else:
                    clean_review_file_owner[file_identity] = index
            for content_digest in evidence_content_digests:
                reset_owner = reset_review_content_owner.get(content_digest)
                if reset_owner is not None:
                    errors.append(
                        f"review_history[{index}] reuses reset-review evidence content "
                        f"from review_history[{reset_owner}]"
                    )
                owner = clean_review_content_owner.get(content_digest)
                if owner is not None:
                    errors.append(
                        f"review_history[{index}] reuses clean-review evidence content from review_history[{owner}]"
                    )
                else:
                    clean_review_content_owner[content_digest] = index
    latest_reset_index: int | None = None
    if not reset_entries:
        errors.append(f"review_history lacks reset entry for {reset_package}")
    if all_reset_entries:
        latest_reset_index, latest_package = all_reset_entries[-1]
        if latest_package != reset_package:
            errors.append(
                "last_reset.review_package must match the latest resetting "
                f"review_history entry: review_history[{latest_reset_index}]={latest_package!r}, "
                f"last_reset={reset_package!r}"
            )
        else:
            latest_reset_evidence = set(last_reset_canonical_evidence_paths)
            history_reset_evidence = set(history_records[latest_reset_index].get("canonical_evidence_paths", []))
            if latest_reset_evidence != history_reset_evidence:
                errors.append(
                    "last_reset.evidence_paths must match the latest resetting "
                    f"review_history[{latest_reset_index}].evidence_paths"
                )
            derived_clean_count = _review_history_clean_counter(
                history_records,
                latest_reset_index=latest_reset_index,
            )
            if clean_count != derived_clean_count:
                errors.append(
                    "counters.consecutive_clean_full_reviews_after_reset "
                    f"{clean_count} != review_history-derived {derived_clean_count} "
                    f"since latest reset {reset_package!r}"
                )

    errors.extend(_check_doc_markers(require_list(gate.get("required_doc_markers"), "required_doc_markers")))
    errors.extend(
        _check_source_boundaries(require_list(gate.get("source_boundaries", []), "source_boundaries"), status=status)
    )
    summary = f"{gate_id}: status={status}, clean={clean_count}/{required}, next_allowed={next_allowed}"
    return summary, errors


def iter_gate_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise GateError(f"gate path not found: {path}")
    return sorted(path.glob("*.json"))


def _gate_by_id(paths: list[Path]) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    owners: dict[str, Path] = {}
    for path in paths:
        gate = load_gate(path)
        gate_id = require_str(gate.get("gate_id"), f"{rel(path)}.gate_id")
        if gate_id in gates:
            raise GateError(f"duplicate gate_id {gate_id!r}: {rel(owners[gate_id])} and {rel(path)}")
        gates[gate_id] = gate
        owners[gate_id] = path
    return gates


def _check_unique_gate_ids(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, Path] = {}
    for path in paths:
        gate = load_gate(path)
        gate_id = require_str(gate.get("gate_id"), f"{rel(path)}.gate_id")
        prior = seen.get(gate_id)
        if prior is not None:
            errors.append(f"duplicate gate_id {gate_id!r}: {rel(prior)} and {rel(path)}")
        else:
            seen[gate_id] = path
    return errors


def _check_required_ready(paths: list[Path], required_gate_ids: list[str]) -> list[str]:
    if not required_gate_ids:
        return []
    errors: list[str] = []
    gates = _gate_by_id(paths)
    for gate_id in required_gate_ids:
        gate = gates.get(gate_id)
        if gate is None:
            errors.append(f"required ready gate not found: {gate_id}")
            continue
        counters = require_mapping(gate.get("counters"), f"{gate_id}.counters")
        required = require_int(
            counters.get("required_consecutive_clean_full_reviews"),
            f"{gate_id}.counters.required_consecutive_clean_full_reviews",
        )
        clean_count = require_int(
            counters.get("consecutive_clean_full_reviews_after_reset"),
            f"{gate_id}.counters.consecutive_clean_full_reviews_after_reset",
        )
        next_phase_entry = require_mapping(gate.get("next_phase_entry"), f"{gate_id}.next_phase_entry")
        next_allowed = require_bool(next_phase_entry.get("allowed"), f"{gate_id}.next_phase_entry.allowed")
        status = require_str(gate.get("status"), f"{gate_id}.status")
        if status != CLOSED_STATUS or clean_count < required or not next_allowed:
            errors.append(
                f"{gate_id} is not ready: status={status}, clean={clean_count}/{required}, next_allowed={next_allowed}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check phase review gate manifests.")
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE_DIR, help="Gate JSON file or directory")
    parser.add_argument(
        "--require-ready",
        action="append",
        default=[],
        metavar="GATE_ID",
        help="Fail unless the named gate is closed, has enough clean reviews, and allows next-phase entry.",
    )
    args = parser.parse_args()

    try:
        paths = iter_gate_paths(args.gate)
    except GateError as exc:
        print(f"phase review gate check failed: {exc}", file=sys.stderr)
        return 2
    if not paths:
        print(f"phase review gate check failed: no gate manifests in {rel(args.gate)}", file=sys.stderr)
        return 2

    summaries: list[str] = []
    all_errors: list[str] = []
    for path in paths:
        try:
            summary, errors = check_gate(path)
        except GateError as exc:
            summary = rel(path)
            errors = [str(exc)]
        summaries.append(summary)
        for error in errors:
            all_errors.append(f"{rel(path)}: {error}")

    try:
        gate_id_errors = _check_unique_gate_ids(paths)
    except GateError as exc:
        gate_id_errors = [str(exc)]
    all_errors.extend(gate_id_errors)

    try:
        if not gate_id_errors:
            all_errors.extend(_check_required_ready(paths, args.require_ready))
    except GateError as exc:
        all_errors.append(str(exc))

    if all_errors:
        print(f"phase review gate check failed: {len(all_errors)} issue(s)")
        for error in all_errors[:40]:
            print(f"  - {error}")
        if len(all_errors) > 40:
            print(f"  ... {len(all_errors) - 40} more")
        return 1

    print("phase review gate check passed: " + "; ".join(summaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
