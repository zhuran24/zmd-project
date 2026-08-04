#!/usr/bin/env python3
"""Deterministic shell for the memory gap lens (ADD / CORRECT candidates).

The lens itself is a model reading a session window and saying "this should have
been written down" or "this card is now wrong".  That judgement is not
deterministic, so the deterministic parts sit on both sides of it:

* ``assemble`` packs what a seat may see into ``.prune/memory_gap_evidence.json``
  — pointers and structured summaries of the three memory layers plus a listing
  of recent transcripts, never their bodies.  This is the one-way feed of the
  June design (§0.4): deterministic output may become model context, model output
  never re-enters a deterministic channel.
* ``verify`` lands a seat's candidate JSON against reality — every cited file
  must exist, every quote must appear verbatim in it, every ``CORRECT`` must name
  an object really present in the layer it claims.  Whatever fails is dropped
  whole and its reason recorded (§0.5, §3c.6).

Only ``assemble`` carries the clean-tree gate (§0.6); ``verify`` says so in its
own ``metadata.preconditions`` rather than implying a check that never ran.

**There is no apply path and there will not be one** (§0.3).  Nothing here writes
or edits a card, and ``verify`` emits one advisory report rather than something a
second tool could consume.  A human who wants a candidate to become memory
retypes the write command, and that command does not read this report.
``test_no_apply_path`` pins this by AST, as a **closed whitelist**: every call in
the module whose leaf name belongs to the filesystem, process or database
families is matched against an exact ``(call, enclosing function)`` table, so a
writing verb nobody thought to blacklist — ``Path.touch`` was the one that got
through the earlier deny-list — fails the test by not being on the list.  Every
report path constant is rooted at ``.prune/``.

Standard library plus the repository's own strict JSON decoder, read-only against
every scanned object, no network.

Threat model and known boundaries
---------------------------------

The threat model is **cooperative-operator** (owner ruling 2026-07-06, card
``deliberate-insider-hardening-deferred-to-release``): a read-only advisory tool
used by the system's own owner, not built to resist a filesystem someone arranged
to fool it.  Declared rather than closed, and repeated in
``metadata.self_check_scope``: a hardlinked report destination; an ancestor
directory swapped between the path walk and the write; ``assume-unchanged`` and
``skip-worktree`` marks, which switch every git dirty check off; and half the
scanned objects living outside the repository (under ``~/.claude/``), so "clean"
is claimed for the in-repository half only.

The candidate JSON is still treated as untrusted, because a model wrote it rather
than the operator: duplicate keys rejected (``loads_strict_json``), file capped at
``MAX_CANDIDATE_BYTES``, list at ``MAX_CANDIDATES``, free text at
``MAX_FIELD_CHARS``, and an ``evidence.path`` outside the allowed roots refused
rather than read.  Untrusted here means "may be confidently wrong", not "may be an
attacker".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.strict_json import loads_strict_json  # noqa: E402

GENERATOR = "devtools/memory_gap_lens.py"
GENERATOR_VERSION = "1"
THREAT_MODEL = "cooperative-operator"

REPORT_DIR_RELPATH = ".prune"
EVIDENCE_RELPATH = ".prune/memory_gap_evidence.json"
CANDIDATES_RELPATH = ".prune/memory_gap_candidates.json"
PRIOR_REPORT_RELPATH = ".prune/memory_reference_report.json"
EVIDENCE_SCHEMA_VERSION = "prune_memory_gap_evidence_v1"
CANDIDATES_SCHEMA_VERSION = "prune_memory_gap_candidates_v1"

DEFAULT_FILE_MEMORY_DIR = Path.home() / ".claude/projects/-home-zhuran24-zmd-pj/memory"
DEFAULT_TRANSCRIPT_DIR = Path.home() / ".claude/projects/-home-zhuran24-zmd-pj"
VNEXT_CARDS_RELPATH = "cc_memory_vnext/cards"
CC_MEMORY_DB_RELPATH = "cc_memory/memory.db"
INDEX_FILENAME = "MEMORY.md"
DEFAULT_TRANSCRIPT_WINDOW_DAYS = 14

LAYER_FILE, LAYER_VNEXT, LAYER_ARCHIVE = "file_memory", "vnext", "cc_memory_archive"
OBJECT_LAYERS = (LAYER_FILE, LAYER_VNEXT, LAYER_ARCHIVE)
KINDS = ("ADD", "CORRECT")

MAX_CANDIDATE_BYTES = 2 * 1024 * 1024
MAX_CANDIDATES = 500
MAX_EVIDENCE_PER_CANDIDATE = 20
MAX_FIELD_CHARS = 2000
MIN_QUOTE_CHARS = 20

SELF_CHECK_GIT_ARGV = ("git", "status", "--porcelain=v1", "--untracked-files=all", "--ignored")
SELF_CHECK_PATHS = (VNEXT_CARDS_RELPATH, CC_MEMORY_DB_RELPATH)

SELF_CHECK_SCOPE: dict[str, Any] = {
    "covers": ["uncommitted, untracked or ignored files under cc_memory_vnext/cards",
               "uncommitted changes to cc_memory/memory.db, the frozen archive layer"],
    "does_not_cover": [
        "the file-memory directory and its index: outside the repository, no committed baseline",
        "the transcript directory, same reason",
        "assume-unchanged and skip-worktree marks, which switch every dirty check off",
        "an object changing between the self check and the read",
        "a hardlinked report destination",
        "an ancestor directory swapped between the check and the write",
        "the truth of what a model asserts: only existence and byte-match are checked",
        "anything a deliberate insider arranges, per the cooperative-operator model",
    ],
    "clean_means": "clean for the in-repository half only; the rest is read as found on disk",
    "deferred_by": "owner ruling 2026-07-06: insider-only hardening is deferred to the release point",
    "documented_in": f"{GENERATOR} module docstring, section 'Threat model and known boundaries'",
}

APPLIES_NOTHING = ("Advisory only.  This file authorizes no edit, nothing in the repository consumes it, "
                   "and it is not an input to any batch-apply tool.")

# The clean-tree gate (§0.6) sits on ``assemble``, which is where a report gets
# built out of the layers themselves.  ``verify`` states the filesystem as found:
# most of what it lands against — the file-memory cards and the transcripts —
# has no committed baseline at all, so refusing on an unrelated uncommitted vnext
# card would buy friction rather than truth.  Saying so in the report is the
# point: a reader must not read the scope block below as a check that ran.
VERIFY_PRECONDITIONS: dict[str, Any] = {
    "in_repository_self_check": "not run",
    "reason": "verify lands candidates against the filesystem as found; the clean-tree gate is on assemble",
    "objects_are_read_as_found": True,
}

_INDEX_ENTRY_RE = re.compile(r"^\s*[-*]\s*\[(?P<title>[^\]]*)\]\((?P<target>[^)]+)\)(?P<rest>.*)$")
_FRONTMATTER_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<value>.*?)\s*$")


class GapLensError(RuntimeError):
    """A fail-closed gap-lens error."""


class SelfCheckRefusal(GapLensError):
    """The generation preconditions were not met, so no report is produced."""


class CandidateRejected(Exception):
    """One candidate failed landing verification and is dropped whole."""


# readers, shared by both subcommands


def _read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GapLensError(f"cannot read {path}: {exc}") from exc


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _mtime_utc(path: Path) -> str:
    return _stamp(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))


def parse_frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar keys of a leading ``---`` block, nothing deeper.

    Four string lookups do not justify a YAML dependency, so nested structure is
    skipped rather than half-understood.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line[:1] in (" ", "\t") or not line.strip():
            continue
        match = _FRONTMATTER_KEY_RE.match(line)
        if match is not None:
            fields[match.group("key")] = match.group("value").strip().strip('"').strip("'")
    return fields


def file_memory_snapshot(directory: Path) -> dict[str, Any]:
    """Index lines verbatim plus one pointer record per card.  No card bodies."""
    index_path = directory / INDEX_FILENAME
    if not directory.is_dir():
        raise GapLensError(f"file-memory directory does not exist: {directory}")
    if not index_path.is_file():
        raise GapLensError(f"file-memory index does not exist: {index_path}")
    index_lines = []
    for number, line in enumerate(_read_text(index_path).split("\n"), start=1):
        match = _INDEX_ENTRY_RE.match(line)
        if match is not None:
            index_lines.append({"line": number, "text": line, "target": match.group("target").strip()})
    cards = []
    for path in sorted(directory.glob("*.md")):
        if path.name == INDEX_FILENAME:
            continue
        front = parse_frontmatter(_read_text(path))
        cards.append({"name": front.get("name") or path.stem, "description": front.get("description", ""),
                      "mtime_utc": _mtime_utc(path), "path": str(path)})
    return {"index_path": str(index_path), "index_lines": index_lines, "cards": cards}


def vnext_snapshot(directory: Path) -> dict[str, Any]:
    """One ``{id, kind, summary, mtime}`` record per vnext card.  No card bodies."""
    if not directory.is_dir():
        raise GapLensError(f"vnext card directory does not exist: {directory}")
    cards = []
    for path in sorted(directory.glob("*.md")):
        front = parse_frontmatter(_read_text(path))
        cards.append({"id": front.get("id") or path.stem, "kind": front.get("kind", ""),
                      "summary": front.get("summary", ""), "mtime_utc": _mtime_utc(path), "path": str(path)})
    return {"cards_dir": str(directory), "cards": cards}


def archive_snapshot(db_path: Path) -> dict[str, Any]:
    """Entry titles of the frozen cc_memory archive, over a footprint-free read.

    ``mode=ro&immutable=1`` rather than a bare ``mode=ro``, following the
    precedent measured in ``cc_memory/mem.py:connect_immutable`` on 2026-08-03: a
    bare read-only open of a WAL-mode database still creates ``memory.db-wal``
    and ``memory.db-shm`` beside it, so a tool that claims to change nothing it
    reads would leave two files behind on every run.  ``immutable=1`` skips
    locking and the shared-memory index entirely and writes nothing.  ``mode=ro``
    stays in the URI because ``immutable=1`` alone will happily create a 0-byte
    file at a path that does not exist.

    The one thing ``immutable=1`` costs — rows a concurrent writer committed but
    has not checkpointed are invisible — does not apply here: the archive layer
    is frozen read-only (owner ruling 2026-08-03), so there is no concurrent
    writer whose WAL could hold rows this read would miss.
    """
    if not db_path.is_file():
        return {"db_path": str(db_path), "status": "no_data", "entries": [],
                "reason": "archive database not present"}
    connection = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        rows = connection.execute("select id, title, status from entries order by id").fetchall()
    except sqlite3.Error as exc:
        raise GapLensError(f"cannot read the archive entries table: {exc}") from exc
    finally:
        connection.close()
    return {"db_path": str(db_path), "status": "frozen_read_only",
            "entries": [{"id": row[0], "title": row[1], "entry_status": row[2]} for row in rows]}


def transcript_listing(directory: Path, *, window_days: int, now: datetime | None = None) -> dict[str, Any]:
    """Recent transcripts listed, never read.  Nested session directories included."""
    if not directory.is_dir():
        raise GapLensError(f"transcript directory does not exist: {directory}")
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=window_days)).timestamp()
    files = []
    for path in sorted(directory.rglob("*.jsonl")):
        if path.is_file() and path.stat().st_mtime >= cutoff:
            files.append({"path": str(path), "mtime_utc": _mtime_utc(path),
                          "size_bytes": path.stat().st_size})
    files.sort(key=lambda record: (record["mtime_utc"], record["path"]), reverse=True)
    return {"transcript_dir": str(directory), "window_days": window_days, "files": files}


def run_self_check(root: Path) -> dict[str, Any]:
    """Fail closed on uncommitted in-repository memory objects, declare the rest.

    Independent implementation of the rule the sibling scanners keep (§0.2:
    shared contract, unshared code): a report must not describe bytes nobody
    committed.  ``--untracked-files=all --ignored`` is not optional — an ignored
    card is invisible to git's default status view and perfectly visible to the
    snapshot readers above.
    """
    args = [SELF_CHECK_GIT_ARGV[0], "-C", str(root), *SELF_CHECK_GIT_ARGV[1:], "--", *SELF_CHECK_PATHS]
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SelfCheckRefusal(f"cannot run git for the in-repository self check: {exc}") from exc
    if completed.returncode != 0:
        raise SelfCheckRefusal(f"git status failed: {completed.stderr.strip()}")
    dirty = [line.strip() for line in completed.stdout.split("\n") if line.strip()]
    if dirty:
        raise SelfCheckRefusal("the in-repository memory objects have uncommitted, untracked or ignored "
                               f"files, so a report would describe uncommitted bytes: {'; '.join(dirty[:5])}")
    return {"in_repository_objects_clean": True, "checked_paths": list(SELF_CHECK_PATHS),
            "verified_by": " ".join(SELF_CHECK_GIT_ARGV),
            "out_of_repository_objects_are_read_as_found": True}


def _metadata(now: datetime | None, extra: dict[str, Any]) -> dict[str, Any]:
    return {"generator": GENERATOR, "generator_version": GENERATOR_VERSION,
            "generated_at_utc": _stamp(now or datetime.now(timezone.utc)),
            "advisory": True, "applies_nothing": APPLIES_NOTHING, "threat_model": THREAT_MODEL,
            "self_check_scope": dict(SELF_CHECK_SCOPE), **extra}


# assemble: the evidence package a seat is fed


def build_evidence(*, root: Path = ROOT, file_memory_dir: Path = DEFAULT_FILE_MEMORY_DIR,
                   vnext_cards_dir: Path | None = None, archive_db: Path | None = None,
                   transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
                   window_days: int = DEFAULT_TRANSCRIPT_WINDOW_DAYS,
                   prior_report: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    preconditions = run_self_check(root)
    file_memory = file_memory_snapshot(file_memory_dir)
    vnext = vnext_snapshot(vnext_cards_dir if vnext_cards_dir is not None else root / VNEXT_CARDS_RELPATH)
    archive = archive_snapshot(archive_db if archive_db is not None else root / CC_MEMORY_DB_RELPATH)
    transcripts = transcript_listing(transcript_dir, window_days=window_days, now=now)

    prior_path = prior_report if prior_report is not None else root / PRIOR_REPORT_RELPATH
    prior: dict[str, Any] = {"path": str(prior_path), "present": prior_path.is_file(), "report": None}
    if prior["present"]:
        prior["report"] = loads_strict_json(_read_text(prior_path))

    counts = {"file_memory_index_lines": len(file_memory["index_lines"]),
              "file_memory_cards": len(file_memory["cards"]), "vnext_cards": len(vnext["cards"]),
              "archive_entries": len(archive["entries"]),
              "transcripts_in_window": len(transcripts["files"]),
              "deterministic_prior_present": prior["present"]}
    return {"schema_version": EVIDENCE_SCHEMA_VERSION,
            "metadata": _metadata(now, {
                "one_way_feed": ("deterministic output may become model context; "
                                 "model output never returns to a deterministic channel"),
                "preconditions": preconditions, "counts": counts}),
            "file_memory": file_memory, "vnext": vnext, "cc_memory_archive": archive,
            "transcripts": transcripts, "deterministic_prior": prior}


# verify: landing a seat's candidates against reality


def allowed_evidence_roots(root: Path, transcript_dir: Path, file_memory_dir: Path) -> tuple[Path, ...]:
    """The only trees an ``evidence.path`` may name."""
    return tuple(dict.fromkeys(path.resolve() for path in (root, transcript_dir, file_memory_dir)))


def resolve_evidence_path(raw: Any, roots: Sequence[Path]) -> Path:
    if not isinstance(raw, str) or not raw.strip() or "\0" in raw:
        raise CandidateRejected(f"evidence path is not a usable path: {raw!r}")
    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else roots[0] / candidate).resolve()
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise CandidateRejected(f"evidence path is outside the allowed roots: {raw}")
    if not resolved.is_file():
        raise CandidateRejected(f"evidence path does not exist: {raw}")
    return resolved


def locate_quote(path: Path, quote: Any) -> str:
    """``path:line`` where the quote appears verbatim, or a rejection.

    A transcript is JSON per line, so a quote taken from a session is matched
    against the raw line text — the same bytes the seat was shown — and never
    against a decoded field.

    The length floor counts stripped characters while the match still uses the
    quote verbatim.  Measured against ``MIN_QUOTE_CHARS`` on the raw string, a
    quote of twenty spaces cleared the floor and then matched the indentation of
    almost any source line, so a hallucinated candidate could hand itself a
    locator and land.  A quote carries evidence only through the text in it, so
    the floor counts text; the byte-match stays verbatim because trimming the
    string a seat submitted would be landing a quote it never made.
    """
    if not isinstance(quote, str):
        raise CandidateRejected("evidence quote is not a string")
    trimmed = quote.strip()
    if not trimmed:
        raise CandidateRejected("evidence quote is blank, which is shorter than "
                                f"{MIN_QUOTE_CHARS} characters of actual text")
    if len(trimmed) < MIN_QUOTE_CHARS:
        raise CandidateRejected(f"evidence quote is shorter than {MIN_QUOTE_CHARS} characters "
                                "once surrounding whitespace is stripped")
    text = _read_text(path)
    for number, line in enumerate(text.split("\n"), start=1):
        if quote in line:
            return f"{path}:{number}"
    if path.suffix != ".jsonl" and quote in text:
        return f"{path}:{text.count(chr(10), 0, text.index(quote)) + 1}"
    raise CandidateRejected(f"evidence quote does not appear verbatim in {path}")


def layer_object_keys(*, file_memory_dir: Path, vnext_cards_dir: Path,
                      archive_db: Path) -> dict[str, set[str]]:
    """Every name by which a real object in each layer may legitimately be cited."""
    file_cards = file_memory_snapshot(file_memory_dir)
    archive = archive_snapshot(archive_db)
    return {
        LAYER_FILE: {card["name"] for card in file_cards["cards"]}
        | {Path(card["path"]).stem for card in file_cards["cards"]}
        | {entry["target"] for entry in file_cards["index_lines"]},
        LAYER_VNEXT: {card["id"] for card in vnext_snapshot(vnext_cards_dir)["cards"]},
        LAYER_ARCHIVE: {entry["id"] for entry in archive["entries"]}
        | {entry["title"] for entry in archive["entries"]},
    }


def is_utf8_encodable(value: Any) -> bool:
    """False only for a string holding an unpaired surrogate."""
    if not isinstance(value, str):
        return True
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def first_unencodable_location(value: Any, where: str = "candidate") -> str | None:
    """Where an unpaired surrogate sits inside a candidate, or ``None``.

    ``"\\ud800"`` is valid JSON and survives :func:`loads_strict_json`, because
    Python strings may hold an unpaired surrogate; UTF-8 cannot encode one.  Left
    alone it travels the whole way through verification and detonates at the
    report write instead, which is the wrong place for it to fail — see
    :func:`write_report`.  Landing it as a candidate-level drop keeps the failure
    where every other bad candidate fails: this one candidate, with a reason, and
    the rest of the run intact.

    Keys are walked as well as values: a surrogate in an unknown key would ride
    into ``unvalidated_field_names`` and reach the report the same way.
    """
    if isinstance(value, str):
        return None if is_utf8_encodable(value) else where
    if isinstance(value, dict):
        for key, item in value.items():
            if not is_utf8_encodable(key):
                return f"{where} key {key.encode('utf-8', 'backslashreplace').decode('ascii')!r}"
            found = first_unencodable_location(item, f"{where}.{key}" if isinstance(key, str) else where)
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for position, item in enumerate(value):
            found = first_unencodable_location(item, f"{where}[{position}]")
            if found is not None:
                return found
    return None


def _require_text(candidate: dict[str, Any], field: str) -> str:
    value = candidate.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CandidateRejected(f"{field} is missing or not a non-empty string")
    if len(value) > MAX_FIELD_CHARS:
        raise CandidateRejected(f"{field} is longer than {MAX_FIELD_CHARS} characters")
    return value


def verify_candidate(candidate: Any, *, roots: Sequence[Path], keys: dict[str, set[str]]) -> dict[str, Any]:
    """One candidate, landed against reality, or :class:`CandidateRejected`."""
    if not isinstance(candidate, dict):
        raise CandidateRejected("candidate is not a JSON object")
    unencodable = first_unencodable_location(candidate)
    if unencodable is not None:
        raise CandidateRejected(f"{unencodable} holds an unpaired surrogate, which is not encodable "
                                "as UTF-8 and so cannot appear in a report")
    kind, layer = candidate.get("kind"), candidate.get("object_layer")
    if kind not in KINDS:
        raise CandidateRejected(f"kind must be one of {KINDS}, got {kind!r}")
    if layer not in OBJECT_LAYERS:
        raise CandidateRejected(f"object_layer must be one of {OBJECT_LAYERS}, got {layer!r}")
    claim = _require_text(candidate, "claim")
    action = _require_text(candidate, "proposed_action")

    object_id = candidate.get("object_id")
    if kind == "CORRECT":
        if not isinstance(object_id, str) or not object_id.strip():
            raise CandidateRejected("a CORRECT candidate must name the object it corrects in object_id")
        if object_id not in keys[layer]:
            raise CandidateRejected(f"object_id {object_id!r} does not exist in layer {layer}")
    elif object_id is not None and not isinstance(object_id, str):
        raise CandidateRejected("object_id must be a string when present")

    evidence = candidate.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise CandidateRejected("evidence must be a non-empty list")
    if len(evidence) > MAX_EVIDENCE_PER_CANDIDATE:
        raise CandidateRejected(f"evidence has more than {MAX_EVIDENCE_PER_CANDIDATE} entries")
    landed = []
    for entry in evidence:
        if not isinstance(entry, dict):
            raise CandidateRejected("evidence entry is not a JSON object")
        path = resolve_evidence_path(entry.get("path"), roots)
        quote = entry.get("quote")
        landed.append({"path": str(path), "quote": quote, "locator": locate_quote(path, quote)})

    known = {"kind", "object_layer", "object_id", "claim", "evidence", "proposed_action"}
    item_id = hashlib.sha256("␟".join((kind, layer, object_id or "", claim)).encode("utf-8")).hexdigest()
    return {"item_id": item_id[:16], "kind": kind, "object_layer": layer, "object_id": object_id,
            "claim": claim, "proposed_action": action, "evidence": landed,
            "unvalidated_field_names": sorted(key for key in candidate if key not in known)}


def load_candidate_document(path: Path) -> list[Any]:
    """The seat's output, treated as untrusted: bounded, strict, shape-checked."""
    if not path.is_file():
        raise GapLensError(f"candidate file does not exist: {path}")
    size = path.stat().st_size
    if size > MAX_CANDIDATE_BYTES:
        raise GapLensError(f"candidate file is larger than {MAX_CANDIDATE_BYTES} bytes: {size}")
    try:
        document = loads_strict_json(_read_text(path))
    except ValueError as exc:
        raise GapLensError(f"candidate file is not strict JSON: {exc}") from exc
    if isinstance(document, dict):
        document = document.get("candidates")
    if not isinstance(document, list):
        raise GapLensError("candidate file must be a list, or an object with a 'candidates' list")
    if len(document) > MAX_CANDIDATES:
        raise GapLensError(f"candidate file holds more than {MAX_CANDIDATES} candidates: {len(document)}")
    return document


def build_candidate_report(candidates_path: Path, *, root: Path = ROOT,
                           file_memory_dir: Path = DEFAULT_FILE_MEMORY_DIR,
                           vnext_cards_dir: Path | None = None, archive_db: Path | None = None,
                           transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
                           now: datetime | None = None) -> dict[str, Any]:
    vnext_dir = vnext_cards_dir if vnext_cards_dir is not None else root / VNEXT_CARDS_RELPATH
    database = archive_db if archive_db is not None else root / CC_MEMORY_DB_RELPATH
    document = load_candidate_document(candidates_path)
    roots = allowed_evidence_roots(root, transcript_dir, file_memory_dir)
    keys = layer_object_keys(file_memory_dir=file_memory_dir, vnext_cards_dir=vnext_dir, archive_db=database)

    accepted: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for position, candidate in enumerate(document):
        try:
            accepted.append(verify_candidate(candidate, roots=roots, keys=keys))
        except CandidateRejected as exc:
            fields = candidate if isinstance(candidate, dict) else {}
            claim = fields.get("claim")
            # The echo is of rejected input, so it is filtered the same way the
            # rejection was: a candidate dropped for an unpaired surrogate must
            # not carry that surrogate back out through its own drop record.
            dropped.append({"index": position, "reason": str(exc),
                            "kind": fields.get("kind") if is_utf8_encodable(fields.get("kind")) else None,
                            "object_layer": (fields.get("object_layer")
                                             if is_utf8_encodable(fields.get("object_layer")) else None),
                            "claim": claim if isinstance(claim, str) and is_utf8_encodable(claim) else None})

    landing = {"checks": ["evidence path exists and is inside the allowed roots",
                          f"evidence quote of at least {MIN_QUOTE_CHARS} non-whitespace characters "
                          "appears verbatim",
                          "a CORRECT candidate names an object that exists in the layer it claims",
                          "no field holds an unpaired surrogate"],
               "allowed_roots": [str(path) for path in roots],
               "failure_policy": "any failed check drops the whole candidate"}
    source = {"path": str(candidates_path), "submitted_count": len(document),
              "sha256": hashlib.sha256(candidates_path.read_bytes()).hexdigest()}
    return {"schema_version": CANDIDATES_SCHEMA_VERSION,
            "metadata": _metadata(now, {
                "preconditions": VERIFY_PRECONDITIONS,
                "source_candidates": source, "landing_verification": landing,
                "accepted_count": len(accepted), "dropped_count": len(dropped),
                "drop_reasons": [{"index": item["index"], "reason": item["reason"]} for item in dropped],
                "accepted_by_kind": {kind: sum(1 for item in accepted if item["kind"] == kind)
                                     for kind in KINDS},
                "accepted_by_object_layer": {layer: sum(1 for item in accepted
                                                        if item["object_layer"] == layer)
                                             for layer in OBJECT_LAYERS}}),
            "candidates": accepted, "dropped": dropped}


# the one write primitive


def resolve_report_destination(root: Path, relpath: str) -> Path:
    """The one place a report may be written, or a fail-closed refusal.

    Four constraints, implemented here rather than imported from a sibling
    scanner: repository-relative, no upward traversal, rooted at ``.prune/``, no
    symlinked component, regular file at the end.
    """
    if not isinstance(relpath, str) or not relpath.strip():
        raise GapLensError("report path must be a non-empty repository-relative path")
    if "\0" in relpath or "\\" in relpath:
        raise GapLensError(f"report path is not a safe repository-relative path: {relpath!r}")
    if relpath.startswith("/") or PurePosixPath(relpath).is_absolute():
        raise GapLensError(f"report path must be relative, not absolute: {relpath!r}")
    parts = [part for part in PurePosixPath(relpath).parts if part != "."]
    if any(part == ".." for part in parts):
        raise GapLensError(f"report path may not traverse upwards: {relpath!r}")
    if len(parts) < 2 or parts[0] != REPORT_DIR_RELPATH:
        raise GapLensError(f"report path must name a file under {REPORT_DIR_RELPATH}/: {relpath!r}")
    if not root.is_dir():
        raise GapLensError(f"repository root is not a directory: {root}")
    walked = root
    for index, part in enumerate(parts):
        walked = walked / part
        so_far = "/".join(parts[: index + 1])
        try:
            status = walked.lstat()
        except FileNotFoundError:
            break
        except OSError as exc:
            raise GapLensError(f"cannot inspect report path component {so_far}: {exc}") from exc
        if stat.S_ISLNK(status.st_mode):
            raise GapLensError(f"refusing to write through a symlink: {so_far}")
        if index == len(parts) - 1 and not stat.S_ISREG(status.st_mode):
            raise GapLensError(f"report destination is not a regular file: {so_far}")
        if index < len(parts) - 1 and not stat.S_ISDIR(status.st_mode):
            raise GapLensError(f"report path component is not a directory: {so_far}")
    return root.joinpath(*parts)


def write_report(root: Path, report: dict[str, Any], *, relpath: str) -> Path:
    """Serialise first, open second, so a bad report cannot destroy a good one.

    ``O_TRUNC`` empties the destination the moment the file is opened, so any
    failure after that point leaves a truncated report behind.  Encoding is the
    one step here that can fail on the report's own content — a string holding an
    unpaired surrogate is not encodable as UTF-8 — and encoding it before the
    open moves that failure in front of the truncation: the previous report is
    still whole, and the caller gets a :class:`GapLensError` instead of an
    unhandled ``UnicodeEncodeError``.

    :func:`verify_candidate` already drops a candidate carrying one, so this is
    the second of two layers rather than the only one: it also covers a surrogate
    arriving from somewhere no candidate check looks, such as an undecodable
    filename picked up by the transcript listing.
    """
    destination = resolve_report_destination(root, relpath)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise GapLensError(f"report directory is not a plain directory: {parent}")
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        encoded = payload.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise GapLensError(f"report content is not encodable as UTF-8, so nothing was written "
                           f"to {destination}: {exc}") from exc
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    try:
        handle = os.open(destination, flags, 0o644)
    except OSError as exc:
        raise GapLensError(f"cannot open report destination {destination}: {exc}") from exc
    with os.fdopen(handle, "wb") as stream:
        stream.write(encoded)
    return destination


# cli


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--file-memory-dir", default=str(DEFAULT_FILE_MEMORY_DIR))
    parser.add_argument("--vnext-cards-dir", default=None)
    parser.add_argument("--archive-db", default=None)
    parser.add_argument("--transcript-dir", default=str(DEFAULT_TRANSCRIPT_DIR))
    subparsers = parser.add_subparsers(dest="command", required=True)
    assemble = subparsers.add_parser("assemble", help="pack the evidence a lens seat is allowed to see")
    assemble.add_argument("--transcript-window-days", type=int, default=DEFAULT_TRANSCRIPT_WINDOW_DAYS)
    assemble.add_argument("--prior-report", default=None)
    assemble.add_argument("--output", default=EVIDENCE_RELPATH,
                          help=f"repository-relative file under {REPORT_DIR_RELPATH}/")
    verify = subparsers.add_parser("verify", help="land a seat's candidates against reality")
    verify.add_argument("candidates", help="path to the candidate JSON a lens seat produced")
    verify.add_argument("--output", default=CANDIDATES_RELPATH,
                        help=f"repository-relative file under {REPORT_DIR_RELPATH}/")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.repo_root).resolve()
    common: dict[str, Any] = {"root": root, "file_memory_dir": Path(args.file_memory_dir),
              "vnext_cards_dir": Path(args.vnext_cards_dir) if args.vnext_cards_dir else None,
              "archive_db": Path(args.archive_db) if args.archive_db else None,
              "transcript_dir": Path(args.transcript_dir)}
    try:
        resolve_report_destination(root, args.output)
        if args.command == "assemble":
            report = build_evidence(window_days=args.transcript_window_days,
                                    prior_report=Path(args.prior_report) if args.prior_report else None,
                                    **common)
            summary = {"status": "EVIDENCE_WRITTEN", "counts": report["metadata"]["counts"]}
        else:
            report = build_candidate_report(Path(args.candidates).resolve(), **common)
            summary = {"status": "CANDIDATES_VERIFIED", "accepted": report["metadata"]["accepted_count"],
                       "dropped": report["metadata"]["dropped_count"]}
        destination = write_report(root, report, relpath=args.output)
    except SelfCheckRefusal as exc:
        print(f"memory gap lens refused: {exc}", file=sys.stderr)
        return 1
    except GapLensError as exc:
        print(f"memory gap lens failed: {exc}", file=sys.stderr)
        return 1
    summary["report"] = str(destination)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
