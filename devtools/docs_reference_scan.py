#!/usr/bin/env python3
"""Deterministic reference-integrity scanner for registered repository documents.

This is the prune-system docs adapter (design v2 §1).  It answers exactly one
question per finding: *does this reference still resolve against the repository
as it is right now?*  Content, tone, duplication and staleness of narrative are
deliberately out of scope — those belong to the advisory LLM lens, never here.

Properties this module keeps, deliberately:

* Pure standard library, read-only against the repository, no LLM, no network.
  The only thing it writes is its own report under ``.prune/``, and that is
  enforced by the write primitive itself: the destination must be a
  repository-relative file under ``.prune/`` reached without traversal and
  without passing through a symlink.
* The document class registry is at a constant path, and it must be tracked and
  committed.  Classes are the safety gate, so the file that defines them cannot
  be swapped out by a caller, and a path claimed by two classes is a structural
  error rather than a race between rule orderings.
* Fail-closed self check.  A report may only be produced from ``main`` with the
  scanned truth sources committed.  There is no override flag; a dirty or
  branched tree gets a refusal and a non-zero exit, not a caveated report.
* Every finding carries the byte-exact source line it came from, so a reader can
  verify it without trusting this program.
* The report is advisory.  Nothing in the repository consumes it, and producing
  it authorizes no edit.  ``locked`` documents are never scanned at all and
  ``historical`` documents can only ever reach the FYI section.

The scanner intentionally under-reports.  Three exclusions inherited from the
dead-reference postmortem apply to every flag: prose that is not a
format-explicit reference is skipped, a reference whose surrounding paragraph is
already talking about removal/history is suppressed, and paths that are absent by
design (external artifacts, generated proof outputs) are allowlisted.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]

REGISTRY_RELPATH = "data/repository_governance/doc_classes.json"
REPORT_DIR_RELPATH = ".prune"
REPORT_RELPATH = ".prune/docs_reference_report.json"

REGISTRY_SCHEMA_VERSION = "repository_doc_classes_v1"
REPORT_SCHEMA_VERSION = "prune_docs_reference_report_v1"
GENERATOR = "devtools/docs_reference_scan.py"
GENERATOR_VERSION = "1"

REQUIRED_BRANCH = "main"
LAYER = "docs"
CONFIDENCE = "deterministic"

DOCUMENT_CLASSES = ("locked", "historical", "living")
SUBJECT_CLASSES = frozenset({"historical", "living"})
UNREGISTERED_CLASS = "unregistered"
CANDIDATE_CLASSES = frozenset({"living", UNREGISTERED_CLASS})

FLAGS = (
    "dead_repo_path",
    "dead_symbol_ref",
    "dead_doc_anchor",
    "dead_commit_hash",
    "unregistered_doc",
)

_MATCH_SELECTORS = ("path", "prefix", "glob", "paths")

_STDLIB_MODULES = frozenset(sys.stdlib_module_names)
_BUILTIN_NAMES = frozenset(dir(builtins))

_INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_LINK_TARGET_RE = re.compile(r"\[[^\]\n]*\]\(\s*([^)\s]+)")
_FENCE_RE = re.compile(r"^\s{0,3}(?:```|~~~)")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")

_FILE_LINE_RE = re.compile(r"^(?P<path>[^\s:]+):(?P<start>\d+)(?:-(?P<end>\d+))?$")
_SYMBOL_RE = re.compile(
    r"^(?P<qualifier>(?:[A-Za-z_][A-Za-z0-9_]*\.)*)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\(\)$"
)
_COMMIT_HASH_RE = re.compile(r"^[0-9a-f]{7,40}$")
_SECTION_RE = re.compile(r"§\s*(?P<section>[0-9A-Za-z]+(?:[.\-][0-9A-Za-z]+)*)")
# Section suffixes are letters, either case: this repository's most cited
# headings are ``## 1A.``, ``## 2B.``, ``### 3C.`` alongside ``### 0b.``.
_HEADING_NUMBER_RE = re.compile(r"^(?P<id>[0-9]+[A-Za-z]?(?:\.[0-9]+[A-Za-z]?)*)[.．]?(?:\s|$)")
_PATH_CHARS_RE = re.compile(r"^[0-9A-Za-z_./#*?+\-㐀-鿿]+$")
_SUFFIX_RE = re.compile(r"^\.[A-Za-z0-9]+$")
_ANCHOR_DEDUP_SUFFIX_RE = re.compile(r"-\d+$")
_SETEXT_UNDERLINE_RE = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")

_TRAILING_PUNCTUATION = "，。、；：！？）】」》,;:!?)]}>”’"
_LEADING_PUNCTUATION = "（【「《([{<“‘"


class DocScanError(RuntimeError):
    """A fail-closed docs-adapter error."""


class SelfCheckRefusal(DocScanError):
    """The generation preconditions were not met, so no report is produced."""


# --------------------------------------------------------------------------
# strict JSON + git plumbing
# --------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DocScanError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise DocScanError(f"non-finite JSON constant: {value}")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocScanError(f"cannot read strict JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DocScanError(f"{path} root must be a JSON object")
    return value


def _run_git(root: Path, args: Sequence[str]) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise DocScanError(f"git {' '.join(args)} failed: {stderr}")
    return completed.stdout


def _git_batch_check(root: Path, revisions: Sequence[str]) -> dict[str, bool]:
    """Resolve many revisions in one plumbing call.  True means 'is a commit'."""
    if not revisions:
        return {}
    payload = "".join(f"{revision}^{{commit}}\n" for revision in revisions).encode("utf-8")
    completed = subprocess.run(
        ["git", "cat-file", "--batch-check"],
        cwd=str(root),
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise DocScanError(f"git cat-file --batch-check failed: {stderr}")
    lines = completed.stdout.decode("utf-8", "replace").splitlines()
    if len(lines) != len(revisions):
        raise DocScanError("git cat-file --batch-check returned an unexpected record count")
    resolved: dict[str, bool] = {}
    for revision, line in zip(revisions, lines):
        parts = line.split()
        resolved[revision] = len(parts) >= 2 and parts[1] == "commit"
    return resolved


def _parse_nul_paths(raw: bytes) -> tuple[str, ...]:
    return tuple(os.fsdecode(item) for item in raw.split(b"\0") if item)


def tracked_paths(root: Path) -> tuple[str, ...]:
    paths = _parse_nul_paths(_run_git(root, ["ls-files", "--cached", "-z"]))
    for path in paths:
        if path.startswith("/") or ".." in PurePosixPath(path).parts or "\\" in path:
            raise DocScanError(f"unsafe tracked path: {path!r}")
    if len(paths) != len(set(paths)):
        raise DocScanError("tracked path enumeration contains duplicates")
    return tuple(sorted(paths))


def _assume_unchanged_paths(root: Path) -> tuple[str, ...]:
    """Paths git has been told to stop watching.

    ``git update-index --assume-unchanged`` (lowercase status letter) and
    ``--skip-worktree`` (``S``) both make git trust the index and stop reporting
    real worktree edits.  Every dirty check below reads ``git status``, so a
    single such mark silently switches the whole self check off.
    """
    raw = _run_git(root, ["ls-files", "-v", "-z"])
    hidden: list[str] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        decoded = os.fsdecode(item)
        if len(decoded) < 3 or decoded[1] != " ":
            raise DocScanError(f"malformed git ls-files -v record: {decoded!r}")
        flag, path = decoded[0], decoded[2:]
        if flag.islower() or flag == "S":
            hidden.append(path)
    return tuple(sorted(set(hidden)))


def _staged_removals(root: Path) -> tuple[str, ...]:
    """Paths that left the index relative to HEAD: deletions and rename sources.

    These cannot be caught by comparing against index-derived truth sources:
    the object is already gone from the index by the time the scope is
    resolved, so it never enters the truth set in the first place.

    A rename counts as a removal at its old path, and this is not an exotic
    case — ``git mv`` is routine.  ``git mv src/thing.py
    scripts/moved_thing.py`` takes a symbol source out of the symbol globs:
    the old path is gone from the index, the new path matches nothing, so the
    symbol silently disappears from the universe while ``git status`` shows a
    tidy ``R`` record and nothing else notices.  ``--name-status`` is required
    to see it — with ``--name-only`` a rename prints only its destination.
    """
    raw = _run_git(
        root,
        ["diff", "--cached", "--name-status", "--diff-filter=DR", "-M", "-z", "HEAD"],
    )
    fields = [os.fsdecode(item) for item in raw.split(b"\0")]
    while fields and fields[-1] == "":
        fields.pop()
    gone: list[str] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if status.startswith("R"):
            # ``R<score>\0<source>\0<destination>``; only the source left.
            if index + 1 >= len(fields):
                raise DocScanError("git diff rename record is missing a path")
            gone.append(fields[index])
            index += 2
            continue
        if status.startswith("D"):
            if index >= len(fields):
                raise DocScanError("git diff deletion record is missing its path")
            gone.append(fields[index])
            index += 1
            continue
        raise DocScanError(f"unexpected staged change status: {status!r}")
    return tuple(sorted(set(gone)))


def _is_rename_record(status: str) -> bool:
    return status[:1] in {"R", "C"} or status[1:2] in {"R", "C"}


def _parse_porcelain(raw: bytes) -> tuple[tuple[str, str], ...]:
    """Return (status_code, path) records from ``git status --porcelain=v1 -z``."""
    items = [item for item in raw.split(b"\0")]
    records: list[tuple[str, str]] = []
    index = 0
    while index < len(items):
        item = items[index]
        index += 1
        if not item:
            continue
        decoded = os.fsdecode(item)
        if len(decoded) < 4:
            raise DocScanError(f"malformed git status record: {decoded!r}")
        status = decoded[:2]
        path = decoded[3:]
        records.append((status, path))
        if _is_rename_record(status):
            if index >= len(items):
                raise DocScanError("git status rename record is missing its origin path")
            records.append((status, os.fsdecode(items[index])))
            index += 1
    return tuple(records)


# --------------------------------------------------------------------------
# glob + matcher helpers
# --------------------------------------------------------------------------


@lru_cache(maxsize=None)
def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    out = ["^"]
    index = 0
    length = len(pattern)
    while index < length:
        char = pattern[index]
        if char == "*":
            if pattern.startswith("**/", index):
                out.append("(?:[^/]+/)*")
                index += 3
                continue
            if pattern.startswith("**", index):
                out.append(".*")
                index += 2
                continue
            out.append("[^/]*")
            index += 1
            continue
        if char == "?":
            out.append("[^/]")
            index += 1
            continue
        out.append(re.escape(char))
        index += 1
    out.append("$")
    return re.compile("".join(out))


def _glob_match(path: str, pattern: str) -> bool:
    return _glob_to_regex(pattern).match(path) is not None


def _matches(path: str, matcher: Mapping[str, Any]) -> bool:
    if len(matcher) != 1:
        raise DocScanError(f"match object must contain exactly one selector: {matcher!r}")
    if "path" in matcher:
        return path == matcher["path"]
    if "prefix" in matcher:
        return path.startswith(matcher["prefix"])
    if "glob" in matcher:
        return _glob_match(path, matcher["glob"])
    if "paths" in matcher:
        return path in set(matcher["paths"])
    raise DocScanError(f"unsupported match selector: {matcher!r}")


def _validate_repository_pattern(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocScanError(f"{label} must be a non-empty string")
    pure = PurePosixPath(value)
    if value.startswith("/") or ".." in pure.parts or "\\" in value or "\0" in value:
        raise DocScanError(f"{label} is not a safe repository-relative pattern")
    return value


def _require_string_list(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise DocScanError(f"{label} must be {'a non-empty' if nonempty else 'a'} list")
    if any(not isinstance(item, str) or not item for item in value):
        raise DocScanError(f"{label} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise DocScanError(f"{label} contains duplicates")
    return value


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Registry:
    path: Path
    relpath: str
    sha256: str
    payload: dict[str, Any]

    @property
    def include_globs(self) -> list[str]:
        return list(self.payload["scan_scope"]["include_globs"])

    @property
    def exclude_globs(self) -> list[str]:
        return list(self.payload["scan_scope"]["exclude_globs"])

    @property
    def out_of_scope_patterns(self) -> list[str]:
        return [note["pattern"] for note in self.payload["scan_scope"]["out_of_scope_notes"]]

    @property
    def rules(self) -> list[dict[str, Any]]:
        return list(self.payload["rules"])

    @property
    def reference_scan(self) -> dict[str, Any]:
        return dict(self.payload["reference_scan"])


def load_registry(root: Path) -> Registry:
    """Load *the* registry.

    The registry location is a constant, not a parameter.  A caller-supplied
    path would be a way around the classification gate itself: an attacker (or
    a careless operator) could point the scanner at a structurally valid file
    that reclassifies ``PROJECT_LOCK.md`` as ``living`` and get change
    candidates for a locked document.  The class hard-gate is only a hard gate
    if the thing that defines the classes cannot be swapped out.
    """
    relpath = REGISTRY_RELPATH
    path = root / relpath
    payload = _load_json_object(path)
    _validate_registry_shape(payload)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return Registry(path=path, relpath=relpath, sha256=digest, payload=payload)


def _validate_registry_shape(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise DocScanError("unsupported doc class registry schema_version")

    authority = payload.get("authority")
    if not isinstance(authority, dict):
        raise DocScanError("authority must be an object")
    if authority.get("role") != "descriptive_governance_projection":
        raise DocScanError("registry must remain a descriptive governance projection")
    _require_string_list(authority.get("higher_authorities"), "authority.higher_authorities", nonempty=True)
    _require_string_list(authority.get("cannot_grant"), "authority.cannot_grant", nonempty=True)

    if tuple(payload.get("document_classes", ())) != DOCUMENT_CLASSES:
        raise DocScanError("document_classes order or membership drifted")

    scope = payload.get("scan_scope")
    if not isinstance(scope, dict) or set(scope) != {"include_globs", "exclude_globs", "out_of_scope_notes"}:
        raise DocScanError("scan_scope has invalid fields")
    include = _require_string_list(scope.get("include_globs"), "scan_scope.include_globs", nonempty=True)
    for index, pattern in enumerate(include):
        _validate_repository_pattern(pattern, f"scan_scope.include_globs[{index}]")
    if include != sorted(include):
        raise DocScanError("scan_scope.include_globs must be sorted")
    exclude = _require_string_list(scope.get("exclude_globs"), "scan_scope.exclude_globs")
    for index, pattern in enumerate(exclude):
        _validate_repository_pattern(pattern, f"scan_scope.exclude_globs[{index}]")
    if exclude != sorted(exclude):
        raise DocScanError("scan_scope.exclude_globs must be sorted")

    notes = scope.get("out_of_scope_notes")
    if not isinstance(notes, list) or not notes:
        raise DocScanError("scan_scope.out_of_scope_notes must be a non-empty list")
    note_patterns: list[str] = []
    for index, note in enumerate(notes):
        label = f"scan_scope.out_of_scope_notes[{index}]"
        if not isinstance(note, dict) or set(note) != {"pattern", "rationale"}:
            raise DocScanError(f"{label} has invalid fields")
        note_patterns.append(_validate_repository_pattern(note["pattern"], f"{label}.pattern"))
        if not isinstance(note["rationale"], str) or not note["rationale"].strip():
            raise DocScanError(f"{label}.rationale must be a non-empty string")
    if note_patterns != sorted(note_patterns):
        raise DocScanError("scan_scope.out_of_scope_notes must be sorted by pattern")
    if len(note_patterns) != len(set(note_patterns)):
        raise DocScanError("scan_scope.out_of_scope_notes contains duplicate patterns")

    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise DocScanError("rules must be a non-empty list")
    rule_ids: set[str] = set()
    for index, rule in enumerate(rules):
        label = f"rules[{index}]"
        if not isinstance(rule, dict) or set(rule) != {"id", "match", "document_class", "rationale"}:
            raise DocScanError(f"{label} has invalid fields")
        rule_id = rule["id"]
        if not isinstance(rule_id, str) or not re.fullmatch(r"[a-z0-9_]+", rule_id):
            raise DocScanError(f"{label}.id must be a lowercase identifier")
        if rule_id in rule_ids:
            raise DocScanError(f"duplicate rule id: {rule_id}")
        rule_ids.add(rule_id)
        matcher = rule["match"]
        if not isinstance(matcher, dict) or len(matcher) != 1:
            raise DocScanError(f"{label}.match must contain exactly one selector")
        selector, value = next(iter(matcher.items()))
        if selector not in _MATCH_SELECTORS:
            raise DocScanError(f"{label}.match has unsupported selector {selector!r}")
        if selector == "paths":
            members = _require_string_list(value, f"{label}.match.paths", nonempty=True)
            for member_index, member in enumerate(members):
                _validate_repository_pattern(member, f"{label}.match.paths[{member_index}]")
            if members != sorted(members):
                raise DocScanError(f"{label}.match.paths must be sorted")
        else:
            _validate_repository_pattern(value, f"{label}.match.{selector}")
        if rule["document_class"] not in DOCUMENT_CLASSES:
            raise DocScanError(f"{label}.document_class is invalid")
        if not isinstance(rule["rationale"], str) or not rule["rationale"].strip():
            raise DocScanError(f"{label}.rationale must be a non-empty string")

    reference_scan = payload.get("reference_scan")
    expected_fields = {
        "symbol_source_globs",
        "context_suppression_markers",
        "external_artifact_manifest",
        "absent_by_design_prefixes",
        "symbol_reference_ignore",
        "known_historical_commit_hashes",
    }
    if not isinstance(reference_scan, dict) or set(reference_scan) != expected_fields:
        raise DocScanError("reference_scan has invalid fields")
    symbol_globs = _require_string_list(
        reference_scan.get("symbol_source_globs"), "reference_scan.symbol_source_globs", nonempty=True
    )
    for index, pattern in enumerate(symbol_globs):
        _validate_repository_pattern(pattern, f"reference_scan.symbol_source_globs[{index}]")
    if symbol_globs != sorted(symbol_globs):
        raise DocScanError("reference_scan.symbol_source_globs must be sorted")
    markers = _require_string_list(
        reference_scan.get("context_suppression_markers"),
        "reference_scan.context_suppression_markers",
        nonempty=True,
    )
    if markers != sorted(markers):
        raise DocScanError("reference_scan.context_suppression_markers must be sorted")
    _validate_repository_pattern(
        reference_scan.get("external_artifact_manifest"), "reference_scan.external_artifact_manifest"
    )
    absent = reference_scan.get("absent_by_design_prefixes")
    if not isinstance(absent, list):
        raise DocScanError("reference_scan.absent_by_design_prefixes must be a list")
    absent_prefixes: list[str] = []
    for index, entry in enumerate(absent):
        label = f"reference_scan.absent_by_design_prefixes[{index}]"
        if not isinstance(entry, dict) or set(entry) != {"prefix", "rationale"}:
            raise DocScanError(f"{label} has invalid fields")
        absent_prefixes.append(_validate_repository_pattern(entry["prefix"], f"{label}.prefix"))
        if not isinstance(entry["rationale"], str) or not entry["rationale"].strip():
            raise DocScanError(f"{label}.rationale must be a non-empty string")
    if absent_prefixes != sorted(absent_prefixes):
        raise DocScanError("reference_scan.absent_by_design_prefixes must be sorted by prefix")
    if len(absent_prefixes) != len(set(absent_prefixes)):
        raise DocScanError("reference_scan.absent_by_design_prefixes contains duplicates")
    ignores = _require_string_list(
        reference_scan.get("symbol_reference_ignore"), "reference_scan.symbol_reference_ignore"
    )
    if ignores != sorted(ignores):
        raise DocScanError("reference_scan.symbol_reference_ignore must be sorted")

    hashes = reference_scan.get("known_historical_commit_hashes")
    if not isinstance(hashes, list):
        raise DocScanError("reference_scan.known_historical_commit_hashes must be a list")
    hash_values: list[str] = []
    for index, entry in enumerate(hashes):
        label = f"reference_scan.known_historical_commit_hashes[{index}]"
        if not isinstance(entry, dict) or set(entry) != {"hash", "cited_in", "rationale"}:
            raise DocScanError(f"{label} has invalid fields")
        value = entry["hash"]
        if not isinstance(value, str) or not _COMMIT_HASH_RE.fullmatch(value):
            raise DocScanError(f"{label}.hash must be 7-40 lowercase hex characters")
        hash_values.append(value)
        _validate_repository_pattern(entry["cited_in"], f"{label}.cited_in")
        if not isinstance(entry["rationale"], str) or not entry["rationale"].strip():
            raise DocScanError(f"{label}.rationale must be a non-empty string")
    if hash_values != sorted(hash_values):
        raise DocScanError("reference_scan.known_historical_commit_hashes must be sorted by hash")
    if len(hash_values) != len(set(hash_values)):
        raise DocScanError("reference_scan.known_historical_commit_hashes contains duplicates")


# --------------------------------------------------------------------------
# scope resolution
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Scope:
    documents: tuple[tuple[str, str], ...]
    unregistered: tuple[str, ...]
    class_counts: dict[str, int]
    symbol_sources: tuple[str, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(path for path, _document_class in self.documents)

    @property
    def subjects(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (path, document_class)
            for path, document_class in self.documents
            if document_class in SUBJECT_CLASSES
        )


def resolve_scope(registry: Registry, tracked: Sequence[str]) -> Scope:
    tracked_set = set(tracked)
    markdown = [path for path in tracked if path.endswith(".md")]

    include = registry.include_globs
    exclude = registry.exclude_globs
    in_scope = [
        path
        for path in markdown
        if any(_glob_match(path, pattern) for pattern in include)
        and not any(_glob_match(path, pattern) for pattern in exclude)
    ]
    in_scope_set = set(in_scope)

    note_patterns = registry.out_of_scope_patterns
    uncovered = [
        path
        for path in markdown
        if path not in in_scope_set
        and not any(_glob_match(path, pattern) for pattern in note_patterns)
    ]
    if uncovered:
        raise DocScanError(
            "tracked markdown is neither in scan scope nor declared out of scope: "
            f"{uncovered[:10]!r}"
        )
    overlapping = [
        path
        for path in in_scope
        if any(_glob_match(path, pattern) for pattern in note_patterns)
    ]
    if overlapping:
        raise DocScanError(
            f"out_of_scope_notes overlap the scan scope: {overlapping[:10]!r}"
        )
    for index, pattern in enumerate(note_patterns):
        if not any(_glob_match(path, pattern) for path in markdown):
            raise DocScanError(
                f"scan_scope.out_of_scope_notes[{index}].pattern matches no tracked markdown: {pattern}"
            )
    for index, pattern in enumerate(include):
        if not any(_glob_match(path, pattern) for path in markdown):
            raise DocScanError(
                f"scan_scope.include_globs[{index}] matches no tracked markdown: {pattern}"
            )

    _validate_rule_members(registry, tracked, tracked_set)

    documents: list[tuple[str, str]] = []
    unregistered: list[str] = []
    for path in sorted(in_scope):
        document_class = _classify(path, registry.rules)
        if document_class is None:
            unregistered.append(path)
            continue
        documents.append((path, document_class))

    class_counts = {name: 0 for name in DOCUMENT_CLASSES}
    for _path, document_class in documents:
        class_counts[document_class] += 1

    symbol_sources = tuple(
        sorted(
            path
            for path in tracked
            if path.endswith(".py")
            and any(_glob_match(path, pattern) for pattern in registry.reference_scan["symbol_source_globs"])
        )
    )
    if not symbol_sources:
        raise DocScanError("reference_scan.symbol_source_globs selected no tracked python sources")

    return Scope(
        documents=tuple(documents),
        unregistered=tuple(unregistered),
        class_counts=class_counts,
        symbol_sources=symbol_sources,
    )


def _classify(path: str, rules: Sequence[Mapping[str, Any]]) -> str | None:
    """Classify one document, refusing any ambiguity.

    First-match-wins would make rule *order* load-bearing: a broad ``*.md ->
    living`` rule inserted at the top silently reclassifies every locked and
    historical document underneath it.  A path that two rules claim for two
    different classes is a structural error in the registry, so it fails closed
    instead of resolving to whichever rule happens to come first.
    """
    matched = [
        (str(rule["id"]), str(rule["document_class"]))
        for rule in rules
        if _matches(path, rule["match"])
    ]
    if not matched:
        return None
    classes = {document_class for _rule_id, document_class in matched}
    if len(classes) > 1:
        raise DocScanError(
            f"conflicting document class rules for {path}: "
            f"{sorted(f'{rule_id}={document_class}' for rule_id, document_class in matched)!r}"
        )
    return matched[0][1]


def _validate_rule_members(registry: Registry, tracked: Sequence[str], tracked_set: set[str]) -> None:
    for rule in registry.rules:
        rule_id = rule["id"]
        matcher = rule["match"]
        selector, value = next(iter(matcher.items()))
        if selector == "path":
            if value not in tracked_set:
                raise DocScanError(f"rule {rule_id}: registered member is not tracked: {value}")
        elif selector == "paths":
            missing = [member for member in value if member not in tracked_set]
            if missing:
                raise DocScanError(f"rule {rule_id}: registered members are not tracked: {missing!r}")
        elif selector == "prefix":
            if not any(path.startswith(value) for path in tracked):
                raise DocScanError(f"rule {rule_id}: prefix matches no tracked path: {value}")
        else:
            if not any(_glob_match(path, value) for path in tracked):
                raise DocScanError(f"rule {rule_id}: glob matches no tracked path: {value}")

    reference_scan = registry.reference_scan
    manifest = reference_scan["external_artifact_manifest"]
    if manifest not in tracked_set:
        raise DocScanError(f"reference_scan.external_artifact_manifest is not tracked: {manifest}")
    for entry in reference_scan["known_historical_commit_hashes"]:
        if entry["cited_in"] not in tracked_set:
            raise DocScanError(
                f"known historical commit hash cites an untracked document: {entry['cited_in']}"
            )


# --------------------------------------------------------------------------
# symbol universe
# --------------------------------------------------------------------------


def build_symbol_universe(root: Path, sources: Sequence[str]) -> frozenset[str]:
    names: set[str] = set()
    for relpath in sources:
        path = root / relpath
        try:
            tree = ast.parse(path.read_bytes(), filename=relpath)
        except (OSError, SyntaxError, ValueError) as exc:
            raise DocScanError(f"cannot AST-parse symbol source {relpath}: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
    return frozenset(names)


def _external_artifact_paths(root: Path, manifest_relpath: str) -> frozenset[str]:
    payload = _load_json_object(root / manifest_relpath)
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise DocScanError(f"{manifest_relpath} has no artifacts list")
    paths: set[str] = set()
    for entry in artifacts:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise DocScanError(f"{manifest_relpath} has a malformed artifact record")
        paths.add(entry["path"])
    return frozenset(paths)


# --------------------------------------------------------------------------
# document parsing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    line: int
    column: int
    text: str
    kind: str


@dataclass(frozen=True)
class ParsedDocument:
    relpath: str
    lines: tuple[str, ...]
    tokens: tuple[Token, ...]
    contexts: tuple[str, ...]
    fenced_lines: int
    section_references: tuple[tuple[int, str, str], ...]


def _read_text(path: Path, relpath: str) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DocScanError(f"cannot read document {relpath}: {exc}") from exc


def parse_document(root: Path, relpath: str) -> ParsedDocument:
    text = _read_text(root / relpath, relpath)
    lines = tuple(text.split("\n"))

    # The fence state machine treats ``` and ~~~ as one delimiter and does not
    # remember which one opened a block, so an unpaired or mixed fence would
    # silently skip the rest of the document.  Measured across all 537 subject
    # documents no file has an odd fence count, so this does not bite today —
    # but the failure mode is silent under-reporting, not a visible error.
    inside_fence = False
    prose_flags: list[bool] = []
    fenced_lines = 0
    for line in lines:
        if _FENCE_RE.match(line):
            inside_fence = not inside_fence
            prose_flags.append(False)
            fenced_lines += 1
            continue
        prose_flags.append(not inside_fence)
        if inside_fence:
            fenced_lines += 1

    contexts = _build_contexts(lines, prose_flags)

    tokens: list[Token] = []
    section_references: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        if not prose_flags[index]:
            continue
        line_number = index + 1
        code_tokens: list[Token] = []
        for match in _INLINE_CODE_RE.finditer(line):
            code_tokens.append(
                Token(line=line_number, column=match.start(1) + 1, text=match.group(1), kind="inline_code")
            )
        for match in _LINK_TARGET_RE.finditer(line):
            code_tokens.append(
                Token(line=line_number, column=match.start(1) + 1, text=match.group(1), kind="link_target")
            )
        tokens.extend(code_tokens)
        for section_match in _SECTION_RE.finditer(line):
            document_token = _preceding_markdown_token(code_tokens, section_match.start())
            if document_token is None:
                continue
            section_references.append((line_number, document_token, section_match.group("section")))

    return ParsedDocument(
        relpath=relpath,
        lines=lines,
        tokens=tuple(tokens),
        contexts=contexts,
        fenced_lines=fenced_lines,
        section_references=tuple(section_references),
    )


def _preceding_markdown_token(tokens: Sequence[Token], column: int) -> str | None:
    """The nearest document named to the left of a ``§`` marker.

    Sorting matters: tokens are collected inline-code-first and then
    link-target, so list order is not left-to-right order, and a line naming
    both would otherwise attribute the section to the wrong document.
    """
    best: str | None = None
    for token in sorted(tokens, key=lambda item: item.column):
        if token.column - 1 > column:
            continue
        normalized = _normalize_path_token(token.text)
        if normalized is None or not normalized.endswith(".md"):
            continue
        best = normalized
    return best


def _build_contexts(lines: Sequence[str], prose_flags: Sequence[bool]) -> tuple[str, ...]:
    contexts: list[str] = [""] * len(lines)
    index = 0
    last_heading = ""
    while index < len(lines):
        if _HEADING_RE.match(lines[index]) and prose_flags[index]:
            last_heading = lines[index]
        if not lines[index].strip():
            contexts[index] = last_heading
            index += 1
            continue
        start = index
        while index < len(lines) and lines[index].strip():
            index += 1
        block = "\n".join(lines[start:index])
        merged = f"{last_heading}\n{block}"
        for position in range(start, index):
            contexts[position] = merged
    return tuple(contexts)


def _normalize_path_token(raw: str) -> str | None:
    token = raw.strip()
    while token and token[0] in _LEADING_PUNCTUATION:
        token = token[1:]
    while token and token[-1] in _TRAILING_PUNCTUATION:
        token = token[:-1]
    if not token:
        return None
    if "://" in token or token.startswith("#") or token.startswith("mailto:"):
        return None
    if token.startswith("/") or "\\" in token or "\0" in token:
        return None
    # ``docs/research/.../external_review/`` is a prose ellipsis placeholder,
    # not a path.  ``./`` and ``../`` are ordinary relative-path tokens and
    # standard Markdown link syntax, so only a literal three-or-more dot
    # segment is rejected.
    if any(len(part) >= 3 and set(part) == {"."} for part in token.split("/")):
        return None
    return token


def _normalize_relative(token: str) -> str | None:
    """Lexically resolve ``.``/``..`` inside a repository-relative token.

    Returns ``None`` when the token would climb above the repository root.
    This is purely lexical on purpose: the scanner never resolves symlinks, so
    it can never be talked into reading outside the tree.  A trailing slash is
    preserved because it is meaningful downstream: ``data/checkpoints/`` names
    a directory, and both the existence check and the absent-by-design prefix
    allowlist are written in terms of that shape.
    """
    parts: list[str] = []
    for part in PurePosixPath(token).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        return None
    return "/".join(parts) + ("/" if token.endswith("/") else "")


def _document_candidates(relpath: str, token: str) -> tuple[str, ...]:
    """Where a Markdown link in ``relpath`` may point, most likely first.

    Markdown resolves a relative link against the *citing* document, so that
    order comes first; the repository root is kept as a fallback because this
    repository's prose also cites root-relative paths in link syntax.  Getting
    the order backwards silently resolves ``docs/GUIDE.md`` → ``PLAN.md`` to
    the root file and misses a real dead link to ``docs/PLAN.md``.
    """
    candidates: list[str] = []
    parent = PurePosixPath(relpath).parent
    if str(parent) not in {"", "."}:
        local = _normalize_relative(f"{parent}/{token}")
        if local is not None:
            candidates.append(local)
    root_relative = _normalize_relative(token)
    if root_relative is not None and root_relative not in candidates:
        candidates.append(root_relative)
    return tuple(candidates)


# --------------------------------------------------------------------------
# finding construction
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    flag: str
    document: str
    document_class: str
    line: int
    column: int
    reference: str
    signals: tuple[str, ...]
    detail: dict[str, Any]


def _item_id(finding: Finding) -> str:
    payload = "␟".join(
        (LAYER, finding.flag, finding.document, str(finding.line), str(finding.column), finding.reference)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _to_item(finding: Finding, line_text: str) -> dict[str, Any]:
    if finding.document_class not in set(DOCUMENT_CLASSES) | {UNREGISTERED_CLASS}:
        raise DocScanError(f"unknown document class in finding: {finding.document_class!r}")
    locked = finding.document_class not in CANDIDATE_CLASSES
    reasons: list[str] = []
    if finding.document_class == "historical":
        reasons.append("historical_evidence_class_never_yields_a_change_candidate")
    if finding.document_class == "locked":
        reasons.append("locked_class_is_never_a_scan_subject")
    return {
        "item_id": _item_id(finding),
        "layer": LAYER,
        "flag": finding.flag,
        "signals": list(finding.signals),
        "safety_lock": {"locked": locked, "reasons": reasons},
        "confidence": CONFIDENCE,
        "evidence": {
            "document": finding.document,
            "document_class": finding.document_class,
            "line": finding.line,
            "column": finding.column,
            "reference": finding.reference,
            "line_text": line_text,
            "detail": finding.detail,
        },
    }


# --------------------------------------------------------------------------
# scanning
# --------------------------------------------------------------------------


@dataclass
class Suppressions:
    context_marker: int = 0
    external_artifact_allowlist: int = 0
    absent_by_design: int = 0
    not_format_explicit: int = 0
    fenced_code_lines: int = 0
    # Two different mechanisms suppress a commit hash: the registry allowlist,
    # and the document's own class.  One shared counter hid which of them was
    # actually carrying the load — in this repository the allowlist entries all
    # cite a historical document, so the class rule suppresses them anyway and
    # the allowlist's observable effect is nil.
    commit_hash_registered_known_historical: int = 0
    commit_hash_in_non_living_document: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "context_marker": self.context_marker,
            "external_artifact_allowlist": self.external_artifact_allowlist,
            "absent_by_design": self.absent_by_design,
            "not_format_explicit": self.not_format_explicit,
            "fenced_code_lines": self.fenced_code_lines,
            "commit_hash_registered_known_historical": (
                self.commit_hash_registered_known_historical
            ),
            "commit_hash_in_non_living_document": self.commit_hash_in_non_living_document,
        }


class DocumentScanner:
    def __init__(self, root: Path, registry: Registry, scope: Scope, tracked: Sequence[str]) -> None:
        self.root = root
        self.registry = registry
        self.scope = scope
        self.tracked = tuple(tracked)
        self.tracked_set = set(tracked)
        self.top_level_dirs = {path.split("/", 1)[0] for path in tracked if "/" in path}
        reference_scan = registry.reference_scan
        self.markers = tuple(reference_scan["context_suppression_markers"])
        self.symbol_ignore = frozenset(reference_scan["symbol_reference_ignore"])
        self.absent_prefixes = tuple(
            entry["prefix"] for entry in reference_scan["absent_by_design_prefixes"]
        )
        self.external_artifacts = _external_artifact_paths(
            root, reference_scan["external_artifact_manifest"]
        )
        self.known_hashes = frozenset(
            entry["hash"] for entry in reference_scan["known_historical_commit_hashes"]
        )
        self.symbols = build_symbol_universe(root, scope.symbol_sources)
        self.suppressions = Suppressions()
        self.consulted: set[str] = set()
        self._heading_cache: dict[str, AnchorIndex] = {}
        self._line_count_cache: dict[str, int | None] = {}

    # -- helpers ---------------------------------------------------------

    def _consult(self, relpath: str) -> None:
        """Record that the answer depends on the state of ``relpath``.

        Anything recorded here is re-checked for uncommitted state before the
        report is published, so that a finding can never be shaped — or made to
        disappear — by a file nobody committed.  Allowlisted-absent paths are
        deliberately excluded: the registry declares that whether they exist on
        a given machine is not a property of the document citing them, so the
        scan's answer does not depend on them either.

        A trailing slash is dropped so that a directory reference and the
        directory itself are one entry: the re-check compares this set against
        index paths, which never carry one.
        """
        normalized = relpath.rstrip("/")
        if not normalized:
            return
        if normalized in self.external_artifacts:
            return
        for prefix in self.absent_prefixes:
            if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
                return
        self.consulted.add(normalized)

    def _suppressed_by_context(self, context: str) -> bool:
        lowered = context.lower()
        return any(marker.lower() in lowered for marker in self.markers)

    def _path_exists(self, token: str) -> bool:
        if "*" in token or "?" in token:
            prefix = re.split(r"[*?]", token, maxsplit=1)[0]
            if not prefix:
                return True
            self._consult(prefix)
            return any(path.startswith(prefix) for path in self.tracked) or (self.root / prefix).exists()
        self._consult(token.rstrip("/"))
        if token.endswith("/"):
            return (self.root / token).is_dir() or any(
                path.startswith(token) for path in self.tracked
            )
        return token in self.tracked_set or (self.root / token).exists()

    def _is_repo_path_token(self, token: str) -> bool:
        if not _PATH_CHARS_RE.fullmatch(token):
            return False
        resolved = _normalize_relative(token)
        if resolved is None or "/" not in resolved:
            return False
        return resolved.split("/", 1)[0] in self.top_level_dirs

    def _is_file_line_target(self, path: str) -> bool:
        """Is ``path`` in ``path:line`` shaped like a file this repository has?

        A repository-root file is just as format-explicit as a nested one, so
        ``main.py:123`` is in scope.  A bare basename is only judged when the
        repository really does track that name at the root, and that condition
        is doing real work: in this repository a bare basename is usually
        shorthand for a nested file (``exact_campaign.py:3532`` means
        ``src/optimization/exact_campaign.py``), and shorthand is
        indistinguishable from a genuinely missing root-level file.  Requiring
        the tracked root file keeps the useful half — the line range is still
        checked, so a stale ``main.py:99999`` is still caught — and drops the
        half that would only produce false positives.  It also keeps ``9.16:0``
        and clock times from being read as file references.
        """
        if "#" in path or not _PATH_CHARS_RE.fullmatch(path):
            return False
        if not _SUFFIX_RE.fullmatch(PurePosixPath(path).suffix):
            return False
        if "/" in path:
            return self._is_repo_path_token(path)
        return path in self.tracked_set

    def _allowlisted_absent(self, token: str) -> str | None:
        """Which allowlist, if any, says this path's absence proves nothing.

        The trailing slash is normalised away.  ``data/checkpoints`` and
        ``data/checkpoints/`` are the same directory, and a document that omits
        the slash is making the same claim; letting the shapes disagree would
        both report a false dead path and make the report depend on whether
        this machine happens to have run a campaign.  The same predicate is
        used by ``_consult`` so that the two can never drift apart.
        """
        if token in self.external_artifacts:
            return "external_artifact_allowlist"
        trimmed = token.rstrip("/")
        for prefix in self.absent_prefixes:
            if trimmed == prefix.rstrip("/") or token.startswith(prefix):
                return "absent_by_design"
        return None

    def _line_count(self, relpath: str) -> int | None:
        self._consult(relpath)
        if relpath not in self._line_count_cache:
            path = self.root / relpath
            if not path.is_file():
                self._line_count_cache[relpath] = None
            else:
                try:
                    raw = path.read_bytes()
                except OSError as exc:
                    raise DocScanError(f"cannot read referenced file {relpath}: {exc}") from exc
                if not raw:
                    self._line_count_cache[relpath] = 0
                else:
                    count = raw.count(b"\n")
                    self._line_count_cache[relpath] = count if raw.endswith(b"\n") else count + 1
        return self._line_count_cache[relpath]

    def _anchors(self, relpath: str) -> AnchorIndex:
        self._consult(relpath)
        if relpath not in self._heading_cache:
            self._heading_cache[relpath] = _anchor_index(
                _read_text(self.root / relpath, relpath)
            )
        return self._heading_cache[relpath]

    def _resolve_document(self, relpath: str, token: str) -> str | None:
        for candidate in _document_candidates(relpath, token):
            self._consult(candidate)
            if (self.root / candidate).is_file():
                return candidate
        return None

    # -- per-document scan -----------------------------------------------

    def scan(
        self, relpath: str, document_class: str
    ) -> tuple[ParsedDocument, list[Finding], list[Finding]]:
        document = parse_document(self.root, relpath)
        self.suppressions.fenced_code_lines += document.fenced_lines
        findings: list[Finding] = []
        hash_candidates: list[Finding] = []

        for token in document.tokens:
            context = document.contexts[token.line - 1]
            produced = self._scan_token(relpath, document_class, token, context)
            if produced is None:
                continue
            kind, finding = produced
            if kind == "commit":
                hash_candidates.append(finding)
            else:
                findings.append(finding)

        findings.extend(self._scan_section_references(relpath, document_class, document))
        return document, findings, hash_candidates

    def _scan_token(
        self, relpath: str, document_class: str, token: Token, context: str
    ) -> tuple[str, Finding] | None:
        raw = token.text.strip()

        file_line = _FILE_LINE_RE.match(raw)
        if file_line is not None and self._is_file_line_target(file_line.group("path")):
            return self._scan_file_line(relpath, document_class, token, context, file_line)

        symbol = _SYMBOL_RE.match(raw)
        if symbol is not None:
            return self._scan_symbol(relpath, document_class, token, context, symbol)

        if _COMMIT_HASH_RE.fullmatch(raw) and _has_digit_and_letter(raw):
            return self._scan_commit_hash(relpath, document_class, token, context, raw)

        normalized = _normalize_path_token(token.text)
        if normalized is None or not _PATH_CHARS_RE.fullmatch(normalized):
            self.suppressions.not_format_explicit += 1
            return None

        # A markdown reference resolves relative to the citing document, so it
        # does not need to start at a repository top-level directory — but a
        # bare basename in prose (`some-card.md`) names a document rather than
        # pointing at one, so only a real link or a path-shaped token counts.
        if normalized.endswith(".md") or ".md#" in normalized:
            if token.kind == "link_target" or self._is_repo_path_token(normalized):
                return self._scan_document_reference(
                    relpath, document_class, token, context, normalized
                )
            self.suppressions.not_format_explicit += 1
            return None

        # ``#`` is only meaningful as a Markdown heading fragment, handled
        # above; anywhere else it makes the token something other than a plain
        # repository path, so no judgement is offered.
        if "#" in normalized or not self._is_repo_path_token(normalized):
            self.suppressions.not_format_explicit += 1
            return None
        target = _normalize_relative(normalized)
        if target is None:
            self.suppressions.not_format_explicit += 1
            return None
        return self._scan_repo_path(relpath, document_class, token, context, target)

    def _scan_repo_path(
        self, relpath: str, document_class: str, token: Token, context: str, normalized: str
    ) -> tuple[str, Finding] | None:
        # Allowlist first, so that an allowlisted path is never even consulted:
        # whether it happens to exist on this machine must not enter the
        # report's dependency set.
        allow = self._allowlisted_absent(normalized)
        if allow == "external_artifact_allowlist":
            self.suppressions.external_artifact_allowlist += 1
            return None
        if allow == "absent_by_design":
            self.suppressions.absent_by_design += 1
            return None
        if self._path_exists(normalized):
            return None
        if self._suppressed_by_context(context):
            self.suppressions.context_marker += 1
            return None
        return (
            "plain",
            Finding(
                flag="dead_repo_path",
                document=relpath,
                document_class=document_class,
                line=token.line,
                column=token.column,
                reference=normalized,
                signals=("referenced_repository_path_does_not_exist",),
                detail={"token_kind": token.kind},
            ),
        )

    def _scan_file_line(
        self,
        relpath: str,
        document_class: str,
        token: Token,
        context: str,
        match: re.Match[str],
    ) -> tuple[str, Finding] | None:
        target = match.group("path")
        start = int(match.group("start"))
        end = int(match.group("end")) if match.group("end") else start
        allow = self._allowlisted_absent(target)
        if allow == "external_artifact_allowlist":
            self.suppressions.external_artifact_allowlist += 1
            return None
        if allow == "absent_by_design":
            self.suppressions.absent_by_design += 1
            return None
        line_count = self._line_count(target)
        if line_count is None:
            if self._suppressed_by_context(context):
                self.suppressions.context_marker += 1
                return None
            signals = ("referenced_source_file_does_not_exist",)
            detail: dict[str, Any] = {"target": target, "start": start, "end": end}
        elif start < 1 or end < start or end > line_count:
            if self._suppressed_by_context(context):
                self.suppressions.context_marker += 1
                return None
            signals = ("referenced_line_range_is_outside_the_file",)
            detail = {"target": target, "start": start, "end": end, "file_line_count": line_count}
        else:
            return None
        return (
            "plain",
            Finding(
                flag="dead_symbol_ref",
                document=relpath,
                document_class=document_class,
                line=token.line,
                column=token.column,
                reference=token.text.strip(),
                signals=signals,
                detail=detail,
            ),
        )

    def _scan_symbol(
        self,
        relpath: str,
        document_class: str,
        token: Token,
        context: str,
        match: re.Match[str],
    ) -> tuple[str, Finding] | None:
        name = match.group("name")
        qualifier = match.group("qualifier")
        if qualifier:
            # ``cp_model.CpModel()`` / ``Path.write_text()`` name third-party or
            # standard-library surfaces.  Only follow a qualified reference when
            # its owner is itself a repository symbol, e.g.
            # ``ExactCampaign.supervisor_seal()``.
            head = qualifier.split(".", 1)[0]
            if head in _STDLIB_MODULES or head not in self.symbols:
                self.suppressions.not_format_explicit += 1
                return None
        if name in self.symbols or name in _BUILTIN_NAMES or name in self.symbol_ignore:
            return None
        if self._suppressed_by_context(context):
            self.suppressions.context_marker += 1
            return None
        return (
            "plain",
            Finding(
                flag="dead_symbol_ref",
                document=relpath,
                document_class=document_class,
                line=token.line,
                column=token.column,
                reference=token.text.strip(),
                signals=("referenced_symbol_is_not_defined_in_repository_sources",),
                detail={"symbol": name},
            ),
        )

    def _scan_commit_hash(
        self, relpath: str, document_class: str, token: Token, context: str, raw: str
    ) -> tuple[str, Finding] | None:
        if raw in self.known_hashes:
            self.suppressions.commit_hash_registered_known_historical += 1
            return None
        if document_class != "living":
            # Deliberately living-only: an unresolvable hash inside dated
            # evidence is a property of the evidence, so it is not even worth a
            # FYI line.  The counter above records how many were dropped here.
            self.suppressions.commit_hash_in_non_living_document += 1
            return None
        if self._suppressed_by_context(context):
            self.suppressions.context_marker += 1
            return None
        return (
            "commit",
            Finding(
                flag="dead_commit_hash",
                document=relpath,
                document_class=document_class,
                line=token.line,
                column=token.column,
                reference=raw,
                signals=("cited_commit_is_not_resolvable_in_this_checkout",),
                detail={"commit": raw},
            ),
        )

    def _scan_document_reference(
        self, relpath: str, document_class: str, token: Token, context: str, normalized: str
    ) -> tuple[str, Finding] | None:
        target, _, fragment = normalized.partition("#")
        if "*" in target or "?" in target:
            # ``F1-F5*.md`` names a family, not a document; a glob cannot be
            # resolved to one file, so it is not a format-explicit reference.
            self.suppressions.not_format_explicit += 1
            return None
        resolved = self._resolve_document(relpath, target)
        if resolved is None:
            if self._suppressed_by_context(context):
                self.suppressions.context_marker += 1
                return None
            return (
                "plain",
                Finding(
                    flag="dead_doc_anchor",
                    document=relpath,
                    document_class=document_class,
                    line=token.line,
                    column=token.column,
                    reference=normalized,
                    signals=("referenced_document_does_not_exist",),
                    detail={"target": target},
                ),
            )
        if not fragment:
            return None
        anchors = self._anchors(resolved)
        if not anchors.checkable or _fragment_is_live(fragment, anchors):
            return None
        if self._suppressed_by_context(context):
            self.suppressions.context_marker += 1
            return None
        return (
            "plain",
            Finding(
                flag="dead_doc_anchor",
                document=relpath,
                document_class=document_class,
                line=token.line,
                column=token.column,
                reference=normalized,
                signals=("referenced_heading_anchor_does_not_exist",),
                detail={"target": resolved, "fragment": fragment},
            ),
        )

    def _scan_section_references(
        self, relpath: str, document_class: str, document: ParsedDocument
    ) -> list[Finding]:
        findings: list[Finding] = []
        for line_number, target_token, section in document.section_references:
            context = document.contexts[line_number - 1]
            resolved = self._resolve_document(relpath, target_token.partition("#")[0])
            if resolved is None:
                continue
            anchors = self._anchors(resolved)
            if not anchors.checkable or section.lower() in anchors.sections:
                continue
            if self._suppressed_by_context(context):
                self.suppressions.context_marker += 1
                continue
            findings.append(
                Finding(
                    flag="dead_doc_anchor",
                    document=relpath,
                    document_class=document_class,
                    line=line_number,
                    column=1,
                    reference=f"{target_token} §{section}",
                    signals=("referenced_section_anchor_does_not_exist",),
                    detail={"target": resolved, "section": section},
                )
            )
        return findings


@dataclass(frozen=True)
class AnchorIndex:
    """What a document offers as anchor targets, and whether we may judge it.

    ``checkable`` is the honest half.  This scanner models ATX headings only,
    so a document that also carries Setext headings or hand-written HTML
    anchors has targets it cannot see.  For those documents it still answers
    "this document does not exist" but declines to answer "this anchor does not
    exist": a missed dead anchor costs nothing, a false one costs the reader's
    trust in every other finding.
    """

    slugs: frozenset[str]
    sections: frozenset[str]
    checkable: bool


def _anchor_index(text: str) -> AnchorIndex:
    lines = text.split("\n")
    slugs: set[str] = set()
    sections: set[str] = set()
    for line in lines:
        match = _HEADING_RE.match(line)
        if match is None:
            continue
        heading = match.group(2).strip()
        slugs.add(_slugify(heading))
        sections.update(_heading_section_ids(heading))
    return AnchorIndex(
        slugs=frozenset(slugs),
        sections=frozenset(sections),
        checkable=_anchors_are_checkable(lines, text),
    )


def _anchors_are_checkable(lines: Sequence[str], text: str) -> bool:
    if "<a " in text or "{#" in text:
        return False
    for index in range(1, len(lines)):
        previous = lines[index - 1]
        if not previous.strip() or _HEADING_RE.match(previous):
            continue
        underline = lines[index].strip()
        if len(underline) >= 3 and _SETEXT_UNDERLINE_RE.match(lines[index]):
            return False  # a Setext heading, which this scanner does not model
    return True


def _fragment_is_live(fragment: str, index: AnchorIndex) -> bool:
    """Conservative ``#fragment`` matching: under-report rather than over-report."""
    if "%" in fragment:
        # Percent-encoded anchors are not decoded here, so no judgement.
        return True
    slug = _slugify(fragment)
    if not slug:
        return True
    if slug in index.slugs:
        return True
    # Repeated headings are disambiguated with a ``-1``/``-2`` suffix; treat
    # those as live whenever the base slug exists.
    return _ANCHOR_DEDUP_SUFFIX_RE.sub("", slug) in index.slugs


def _heading_section_ids(heading: str) -> frozenset[str]:
    """Section identifiers a ``§`` reference may legitimately name.

    Two conventions live side by side in this repository: headings numbered as
    ``## 4. 拍板台账`` / ``### 0b. 方法论`` / ``### 6.4 边界``, and headings that
    spell the section marker out as ``§1A``.  Both are accepted.
    """
    ids: set[str] = set()
    number = _HEADING_NUMBER_RE.match(heading)
    if number is not None:
        ids.add(number.group("id").lower())
    for section_match in _SECTION_RE.finditer(heading):
        ids.add(section_match.group("section").lower())
    return frozenset(ids)


def _has_digit_and_letter(value: str) -> bool:
    return any(char.isdigit() for char in value) and any(char.isalpha() for char in value)


def _slugify(text: str) -> str:
    lowered = text.strip().lower()
    kept = "".join(
        char for char in lowered if char.isalnum() or char in {"-", "_", " ", "§"}
    )
    return kept.replace(" ", "-").strip("-")


# --------------------------------------------------------------------------
# self check
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WorktreeState:
    """One snapshot of everything git can say about uncommitted state."""

    branch: str
    head: str
    records: tuple[tuple[str, str], ...]
    staged_removals: tuple[str, ...]
    assume_unchanged: tuple[str, ...]

    @property
    def uncommitted_paths(self) -> frozenset[str]:
        paths = {path.rstrip("/") for _status, path in self.records}
        paths.update(self.staged_removals)
        paths.discard("")
        return frozenset(paths)


def capture_worktree_state(root: Path) -> WorktreeState:
    """Snapshot uncommitted state *before* anything is derived from the index.

    Order matters.  Resolving the scan scope from the index and only then
    asking whether the tree is clean cannot see a staged deletion: the deleted
    object left the index before the scope was built, so it never became a
    truth source that a dirty check could flag.

    ``--ignored`` is not optional here.  ``.gitignore`` is a committed file, so
    an ignored path is not an attacker's construction: a build output landing
    at a path some document cites changes what the scan answers while leaving
    ``git status`` completely empty.
    """
    return WorktreeState(
        branch=_run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"]).decode("utf-8").strip(),
        head=_run_git(root, ["rev-parse", "HEAD"]).decode("utf-8").strip(),
        records=_parse_porcelain(
            _run_git(
                root,
                ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored"],
            )
        ),
        staged_removals=_staged_removals(root),
        assume_unchanged=_assume_unchanged_paths(root),
    )


_VERIFIED_BY = (
    "git rev-parse --abbrev-ref HEAD",
    "git rev-parse HEAD",
    "git status --porcelain=v1 -z --untracked-files=all --ignored",
    "git diff --cached --name-status --diff-filter=DR -M -z HEAD",
    "git ls-files -v -z",
    "git ls-files --cached -z (worktree presence vs index for every consulted path)",
)


def _is_truth_source_shaped(path: str, registry: Registry) -> bool:
    """Would this path have been a truth source if it were still in the index?"""
    if path == registry.relpath:
        return True
    if path == registry.reference_scan["external_artifact_manifest"]:
        return True
    if path.endswith(".md"):
        return any(_glob_match(path, pattern) for pattern in registry.include_globs) and not any(
            _glob_match(path, pattern) for pattern in registry.exclude_globs
        )
    if path.endswith(".py"):
        return any(
            _glob_match(path, pattern)
            for pattern in registry.reference_scan["symbol_source_globs"]
        )
    return False


def run_self_check(
    root: Path,
    registry: Registry,
    scope: Scope,
    tracked: Sequence[str],
    state: WorktreeState,
) -> tuple[dict[str, Any], frozenset[str]]:
    if state.branch != REQUIRED_BRANCH:
        raise SelfCheckRefusal(
            f"refusing to generate a report: HEAD is {state.branch!r}, not {REQUIRED_BRANCH!r}"
        )
    if state.assume_unchanged:
        raise SelfCheckRefusal(
            "refusing to generate a report: git has been told to ignore worktree changes for "
            f"{list(state.assume_unchanged)[:10]!r} (assume-unchanged / skip-worktree), "
            "so no dirty check below can be trusted"
        )

    # The registry decides which documents may ever yield a candidate, so an
    # untracked registry is an unreviewed registry: it never passed through a
    # commit anybody could read.
    if registry.relpath not in set(tracked):
        raise SelfCheckRefusal(
            f"refusing to generate a report: the doc class registry is not tracked: {registry.relpath}"
        )

    truth_sources = set(scope.paths)
    truth_sources.update(scope.unregistered)
    truth_sources.add(registry.relpath)
    truth_sources.update(scope.symbol_sources)
    truth_sources.add(registry.reference_scan["external_artifact_manifest"])

    dirty: list[str] = []
    untracked_in_scope: list[str] = []
    include = registry.include_globs
    exclude = registry.exclude_globs
    for status, path in state.records:
        if status in {"??", "!!"}:
            if (
                path.endswith(".md")
                and any(_glob_match(path, pattern) for pattern in include)
                and not any(_glob_match(path, pattern) for pattern in exclude)
            ):
                untracked_in_scope.append(path)
            continue
        if path in truth_sources:
            dirty.append(path)
            continue
        # Both ends of a rename record are judged by shape, because neither end
        # need be in the truth set: the source has left the index and the
        # destination may have landed outside every glob.
        if _is_rename_record(status) and _is_truth_source_shaped(path, registry):
            dirty.append(path)
    if dirty:
        raise SelfCheckRefusal(
            "refusing to generate a report: scanned truth sources have uncommitted changes: "
            f"{sorted(set(dirty))[:10]!r}"
        )
    if untracked_in_scope:
        raise SelfCheckRefusal(
            "refusing to generate a report: untracked or ignored documents fall inside the "
            f"scan scope: {sorted(set(untracked_in_scope))[:10]!r}"
        )
    removed = [path for path in state.staged_removals if _is_truth_source_shaped(path, registry)]
    if removed:
        raise SelfCheckRefusal(
            "refusing to generate a report: truth sources are deleted in the index: "
            f"{removed[:10]!r}"
        )

    preconditions = {
        "required_branch": REQUIRED_BRANCH,
        "observed_branch": state.branch,
        "head_commit": state.head,
        "truth_sources_clean": True,
        "truth_source_kinds": [
            "registered scan-scope documents",
            "doc class registry",
            "external artifact manifest",
            "tracked python symbol sources",
            "every filesystem path the scan consulted",
        ],
        "truth_source_count": len(truth_sources),
        "verified_by": list(_VERIFIED_BY),
    }
    return preconditions, frozenset(truth_sources)


def _tracked_directories(tracked: Sequence[str]) -> frozenset[str]:
    """Every directory the index implies, so a directory can be asked about."""
    directories: set[str] = set()
    for path in tracked:
        parts = path.split("/")
        for depth in range(1, len(parts)):
            directories.add("/".join(parts[:depth]))
    return frozenset(directories)


def _worktree_disagrees_with_index(
    root: Path, path: str, tracked_set: frozenset[str], tracked_directories: frozenset[str]
) -> bool:
    """Does the working tree answer a question the index answers differently?

    ``git status`` is not a complete account of the working tree.  It says
    nothing about a path ``.gitignore`` covers, and it can say nothing at all
    about an empty directory, because git does not record directories.  Both
    change what the scan sees — an ignored build output appearing at a cited
    path, or ``mkdir`` alone resurrecting a dead directory reference — so the
    presence question is asked directly instead of being inferred from status.
    """
    known = path in tracked_set or path in tracked_directories
    return (root / path).exists() != known


def verify_consulted_state_is_committed(
    root: Path,
    before: WorktreeState,
    consulted: frozenset[str],
    tracked: Sequence[str],
) -> dict[str, Any]:
    """Re-run the dirty check over everything the scan actually read.

    The truth-source set is derived from the registry; the *consulted* set is
    derived from the documents themselves, and it is strictly larger: a
    reference reaches out to any path it names.  Checking only the first set
    lets a report be shaped by uncommitted state — an edited out-of-scope
    file, a fresh untracked file at a cited path, a staged deletion — while
    the report still claims its truth sources were clean.
    """
    after = capture_worktree_state(root)
    if after.branch != before.branch or after.head != before.head:
        raise SelfCheckRefusal(
            "refusing to publish a report: the checkout moved during the scan "
            f"({before.branch}@{before.head[:12]} -> {after.branch}@{after.head[:12]})"
        )
    if after.assume_unchanged:
        raise SelfCheckRefusal(
            "refusing to publish a report: git has been told to ignore worktree changes for "
            f"{list(after.assume_unchanged)[:10]!r} (assume-unchanged / skip-worktree)"
        )
    touched = sorted(
        (before.uncommitted_paths | after.uncommitted_paths) & consulted
    )
    if touched:
        raise SelfCheckRefusal(
            "refusing to publish a report: filesystem state consulted by the scan is not "
            f"committed: {touched[:10]!r}"
        )
    tracked_set = frozenset(tracked)
    tracked_directories = _tracked_directories(tracked)
    unrepresented = sorted(
        path
        for path in consulted
        if _worktree_disagrees_with_index(root, path, tracked_set, tracked_directories)
    )
    if unrepresented:
        raise SelfCheckRefusal(
            "refusing to publish a report: filesystem state consulted by the scan is present "
            "in the working tree but not in the index (or the reverse): "
            f"{unrepresented[:10]!r}"
        )
    return {
        "consulted_path_count": len(consulted),
        "reverified_after_scan": True,
        "worktree_presence_matches_index": True,
        "verified_by": list(_VERIFIED_BY),
    }


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------


def build_report(root: Path) -> dict[str, Any]:
    # Snapshot uncommitted state before anything is derived from the index.
    state = capture_worktree_state(root)
    registry = load_registry(root)
    tracked = tracked_paths(root)
    scope = resolve_scope(registry, tracked)
    preconditions, truth_sources = run_self_check(root, registry, scope, tracked, state)

    scanner = DocumentScanner(root, registry, scope, tracked)
    findings: list[Finding] = []
    commit_findings: list[Finding] = []
    line_texts: dict[tuple[str, int], str] = {}

    for relpath, document_class in scope.subjects:
        document, document_findings, hash_candidates = scanner.scan(relpath, document_class)
        for finding in document_findings:
            findings.append(finding)
            line_texts[(relpath, finding.line)] = document.lines[finding.line - 1]
        for finding in hash_candidates:
            commit_findings.append(finding)
            line_texts[(relpath, finding.line)] = document.lines[finding.line - 1]

    revisions = sorted({finding.reference for finding in commit_findings})
    resolved = _git_batch_check(root, revisions)
    for finding in commit_findings:
        if resolved.get(finding.reference, False):
            continue
        findings.append(finding)

    for relpath in scope.unregistered:
        findings.append(
            Finding(
                flag="unregistered_doc",
                document=relpath,
                document_class="unregistered",
                line=1,
                column=1,
                reference=relpath,
                signals=("document_is_in_scan_scope_but_absent_from_doc_classes",),
                detail={"registry": registry.relpath},
            )
        )
        line_texts[(relpath, 1)] = ""

    findings.sort(key=lambda item: (item.document, item.line, item.column, item.flag, item.reference))

    candidates: list[dict[str, Any]] = []
    fyi: list[dict[str, Any]] = []
    for finding in findings:
        item = _to_item(finding, line_texts.get((finding.document, finding.line), ""))
        if item["safety_lock"]["locked"]:
            fyi.append(item)
        else:
            candidates.append(item)

    flag_counts = {flag: 0 for flag in FLAGS}
    for finding in findings:
        flag_counts[finding.flag] += 1

    consulted = frozenset(scanner.consulted) | truth_sources
    preconditions["consulted_paths"] = verify_consulted_state_is_committed(
        root, state, consulted, tracked
    )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "metadata": {
            "generator": GENERATOR,
            "generator_version": GENERATOR_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "layer": LAYER,
            "advisory": True,
            "applies_nothing": (
                "This report authorizes no edit; nothing in the repository consumes it."
            ),
            "preconditions": preconditions,
            "registry": {"path": registry.relpath, "sha256": registry.sha256},
            "scope": {
                "in_scope_document_count": len(scope.documents) + len(scope.unregistered),
                "subject_document_count": len(scope.subjects),
                "class_counts": dict(scope.class_counts),
                "unregistered_document_count": len(scope.unregistered),
                "symbol_source_count": len(scope.symbol_sources),
                "symbol_universe_size": len(scanner.symbols),
            },
            "flag_counts": flag_counts,
            "suppression_counts": scanner.suppressions.as_dict(),
            "candidate_count": len(candidates),
            "fyi_count": len(fyi),
        },
        "candidates": candidates,
        "fyi": fyi,
    }


def resolve_report_destination(root: Path, relpath: str) -> Path:
    """Resolve the one place a report may be written, or fail closed.

    This is the scanner's only write primitive, so it is also the whole of its
    blast radius.  Left unconstrained it is a general-purpose "overwrite any
    file" tool that happens to be reachable from a read-only analysis command:
    ``scan --output PROJECT_LOCK.md`` overwrites a locked file, and a planted
    ``.prune/docs_reference_report.json -> ../PROJECT_LOCK.md`` symlink does the
    same thing with no arguments at all.  Four constraints, all fail-closed:

    * the path is repository-relative — no absolute paths, no backslashes;
    * it may not traverse upwards, so it cannot leave the repository;
    * it is rooted at ``.prune/`` and names a file inside it;
    * no component below the repository root may be a symlink, and an existing
      destination must be a plain file.

    The write itself then uses ``O_NOFOLLOW`` so that a symlink planted between
    this check and the write still cannot be followed.
    """
    if not isinstance(relpath, str) or not relpath.strip():
        raise DocScanError("report path must be a non-empty repository-relative path")
    if "\0" in relpath or "\\" in relpath:
        raise DocScanError(f"report path is not a safe repository-relative path: {relpath!r}")
    if relpath.startswith("/") or PurePosixPath(relpath).is_absolute() or Path(relpath).is_absolute():
        raise DocScanError(f"report path must be relative, not absolute: {relpath!r}")

    parts = [part for part in PurePosixPath(relpath).parts if part != "."]
    if any(part == ".." for part in parts):
        raise DocScanError(f"report path may not traverse upwards: {relpath!r}")
    if len(parts) < 2 or parts[0] != REPORT_DIR_RELPATH:
        raise DocScanError(
            f"report path must name a file under {REPORT_DIR_RELPATH}/: {relpath!r}"
        )

    if not root.is_dir():
        raise DocScanError(f"repository root is not a directory: {root}")
    walked = root
    for index, part in enumerate(parts):
        walked = walked / part
        so_far = "/".join(parts[: index + 1])
        try:
            status = walked.lstat()
        except FileNotFoundError:
            # Nothing exists from here down, so nothing below can be a symlink.
            break
        except OSError as exc:
            raise DocScanError(f"cannot inspect report path component {so_far}: {exc}") from exc
        if stat.S_ISLNK(status.st_mode):
            raise DocScanError(f"refusing to write through a symlink: {so_far}")
        if index == len(parts) - 1:
            if not stat.S_ISREG(status.st_mode):
                raise DocScanError(f"report destination is not a regular file: {so_far}")
        elif not stat.S_ISDIR(status.st_mode):
            raise DocScanError(f"report path component is not a directory: {so_far}")
    return root.joinpath(*parts)


def write_report(root: Path, report: Mapping[str, Any], *, relpath: str = REPORT_RELPATH) -> Path:
    destination = resolve_report_destination(root, relpath)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise DocScanError(f"report directory is not a plain directory: {parent}")
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    try:
        handle = os.open(destination, flags, 0o644)
    except OSError as exc:
        raise DocScanError(f"cannot open report destination {destination}: {exc}") from exc
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(payload)
    return destination


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def validate_registry(root: Path) -> dict[str, Any]:
    registry = load_registry(root)
    tracked = tracked_paths(root)
    scope = resolve_scope(registry, tracked)
    return {
        "status": "PASS",
        "registry": registry.relpath,
        "registry_sha256": registry.sha256,
        "in_scope_document_count": len(scope.documents) + len(scope.unregistered),
        "class_counts": dict(scope.class_counts),
        "unregistered_documents": list(scope.unregistered),
        "symbol_source_count": len(scope.symbol_sources),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--repo-root", default=str(ROOT), help="repository root to scan")
    # There is deliberately no --registry flag: the registry path is a constant
    # so that the document class gate cannot be swapped out from the CLI.
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan", help="run the fail-closed reference scan and write the report"
    )
    scan_parser.add_argument(
        "--output",
        default=REPORT_RELPATH,
        help=f"report path, which must be a repository-relative file under {REPORT_DIR_RELPATH}/",
    )

    subparsers.add_parser(
        "validate-registry",
        help="validate the doc class registry and scope without producing a report",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    try:
        if args.command == "scan":
            # Validate the write target before doing any work, so an illegal
            # destination cannot even reach the point of having bytes to write.
            resolve_report_destination(root, args.output)
            report = build_report(root)
            destination = write_report(root, report, relpath=args.output)
            summary = {
                "status": "REPORT_WRITTEN",
                "report": str(destination),
                "candidates": report["metadata"]["candidate_count"],
                "fyi": report["metadata"]["fyi_count"],
            }
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        elif args.command == "validate-registry":
            print(json.dumps(validate_registry(root), ensure_ascii=False, sort_keys=True))
        else:
            parser.error(f"unsupported command: {args.command}")
            return 1
    except SelfCheckRefusal as exc:
        print(f"docs reference scan refused: {exc}", file=sys.stderr)
        return 1
    except DocScanError as exc:
        print(f"docs reference scan failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
