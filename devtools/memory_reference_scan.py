#!/usr/bin/env python3
"""Deterministic integrity scanner for the two live memory layers.

The docs adapter asks whether a document's references still resolve.  This asks
the same question one layer over: does the memory system's own bookkeeping hold
together?  Five flags, four plain lookups and exactly one heuristic, marked as
such in every item it emits.

* ``orphan_card`` — a card file exists in the file-memory directory but
  ``MEMORY.md`` has no index line for it.  The index is the only surface a
  session sees at startup, so an unindexed card is invisible to its reader.
* ``dangling_index_entry`` — the mirror image: an index line pointing at a file
  that is not there.
* ``dangling_wikilink`` — a ``[[name]]`` with no card behind it.  FYI-only by
  design: such a link is usually a note about a card that *should* exist, and
  that intent is information rather than a defect.
* ``never_read_card`` — a vnext card the injection ledger has never injected.
  Computed only where a ledger exists; see below.
* ``said_card_unwritten`` — a session said it would write a card and no matching
  card appeared inside the window.  This is the heuristic, and it is here
  because it has a documented true positive: a card declared worth writing on
  2026-07-12 was written on 2026-08-02, and the pitfall it describes was stepped
  in four times in between.  Only the **assistant's own reply text** counts as a
  promise: user turns (a quotation or a negation is not a commitment) and
  ``thinking`` blocks (deliberation is not a commitment) are excluded, as is any
  quote naming one of this system's own governance surfaces.  See
  ``_text_blocks`` for the trade that exclusion makes.

Pure standard library, read-only against every scanned object, no LLM, no
network.  The only thing it writes is its own report under ``.prune/``, and the
write primitive enforces that.  Nothing consumes the report and producing it
authorises no edit.  It is deliberately thin: the layers it scans hold tens of
files, and a scanner that outgrows its subject stops being maintained.

Honesty about ``never_read_card``
---------------------------------

"Never read" is only answerable where something recorded the reads, and the two
layers differ, so the report states both answers rather than averaging them.
vnext cards have ``cc_memory_vnext/logs/activation_decisions.jsonl``, which
records the ids injected at each prompt — a real ledger, so the flag is computed
from it, and a card older than the ledger's first entry can only reach FYI.
File-memory cards have no read ledger at all: their index is injected wholesale
every session, so injection cannot discriminate between cards, and transcripts
only cover retained sessions.  That layer therefore gets ``status: no_data`` with
the missing ledger named.  A proxy built from whatever happens to be lying
around would produce confident numbers about nothing.

Threat model and known boundaries
---------------------------------

The threat model is **cooperative-operator**, per the owner ruling of 2026-07-06
that also governs the docs adapter: a read-only advisory diagnostic with no
apply path, used by the system's own owner.  It is not built to resist someone
arranging the filesystem to fool it.

One boundary is specific to this scanner and is published in
``metadata.self_check_scope``: **half of what it scans lives outside the
repository**.  The file-memory directory and the transcripts are under
``~/.claude/``, which git knows nothing about, so "clean" is claimed for the
in-repository half — the vnext cards — and nothing else.  The rest is read as
found on disk, with no committed baseline, and the report says so.

Known boundaries, declared rather than closed
---------------------------------------------

Each of these came out of the 2026-08-03 adversarial review, each needs a
repository or filesystem somebody arranged on purpose, and each is left open
under the same 2026-07-06 owner ruling that governs the docs adapter:
insider-only hardening is deferred to the release point and is not a condition
of closing this line.  The card is
``deliberate-insider-hardening-deferred-to-release``.  They are listed here and
in ``metadata.self_check_scope.does_not_cover`` so that "clean" is never read as
a wider claim than it is.

* **a hardlinked report destination** — the write primitive opens the
  destination with ``O_TRUNC | O_NOFOLLOW``, which stops a symlink but not a
  second name for the same inode.  Effect: the report's bytes land on a tracked
  file, or one outside the repository, with a zero exit.  To close it: require
  ``st_nlink == 1``, or write a fresh temporary name and rename over it.
* **an ancestor directory swapped between the check and the write** —
  ``resolve_report_destination`` walks each component and refuses a symlink,
  then ``write_report`` opens by path.  ``O_NOFOLLOW`` protects the final
  component only, so with the right timing the report escapes ``.prune/``.  To
  close it: walk the path with ``O_DIRECTORY|O_NOFOLLOW`` descriptors and write
  through ``openat``.
* **``assume-unchanged`` and ``skip-worktree`` marks** — one
  ``git update-index --assume-unchanged`` on a card makes git report a clean
  worktree no matter what the file says, so the self check passes while the
  scan reads uncommitted bytes.  This is the half of ``hidden-dirty-card-claim``
  that stays open; the ignored/untracked half is closed (see
  :func:`run_self_check`).  To close it: read ``git ls-files -v -z`` and refuse
  on any lowercase status letter or ``S``, as the docs adapter does.
* **cards changing between the self check and the read** — the check runs once
  up front and the card files are read afterwards, so a write landing in
  between is described by a report that already claimed clean.  To close it:
  re-verify the consulted set after the scan, as the docs adapter does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Sequence

ROOT = Path(__file__).resolve().parents[1]

REPORT_DIR_RELPATH = ".prune"
REPORT_RELPATH = ".prune/memory_reference_report.json"
REPORT_SCHEMA_VERSION = "prune_memory_reference_report_v1"
GENERATOR = "devtools/memory_reference_scan.py"
GENERATOR_VERSION = "1"

THREAT_MODEL = "cooperative-operator"
CONFIDENCE_DETERMINISTIC = "deterministic"
CONFIDENCE_HEURISTIC = "heuristic"

DEFAULT_FILE_MEMORY_DIR = Path.home() / ".claude/projects/-home-zhuran24-zmd-pj/memory"
DEFAULT_TRANSCRIPT_DIR = Path.home() / ".claude/projects/-home-zhuran24-zmd-pj"
VNEXT_CARDS_RELPATH = "cc_memory_vnext/cards"
ACTIVATION_LEDGER_RELPATH = "cc_memory_vnext/logs/activation_decisions.jsonl"

INDEX_FILENAME = "MEMORY.md"

LAYER_FILE = "memory_file"
LAYER_VNEXT = "memory_vnext"
LAYER_TRANSCRIPT = "transcript"

FLAGS = ("orphan_card", "dangling_index_entry", "dangling_wikilink", "never_read_card", "said_card_unwritten")

SELF_CHECK_SCOPE: dict[str, Any] = {
    "covers": [
        "uncommitted edits to the in-repository vnext card directory",
        "untracked and ignored files inside that directory",
    ],
    "does_not_cover": [
        "the file-memory directory and its index: outside the repository, no committed baseline",
        "the transcript directory, same reason",
        "the injection ledger, which is a git-ignored append-only log",
        "assume-unchanged and skip-worktree marks, which switch every dirty check off",
        "a card changing between the self check and the read",
        "a hardlinked report destination",
        "an ancestor directory swapped between the check and the write",
        "anything a deliberate insider arranges, per the cooperative-operator model",
    ],
    "clean_means": "clean for the in-repository half only; the rest is read as found on disk",
    "deferred_by": "owner ruling 2026-07-06: insider-only hardening is deferred to the release point",
    "documented_in": f"{GENERATOR} module docstring, sections 'Threat model and known boundaries' "
                     "and 'Known boundaries, declared rather than closed'",
}

# "I should write a card about this" in the phrasings this operator actually
# uses, Chinese and English.  A constant so that the list can grow without
# touching the scan: a missed phrasing costs one uncaught promise, a
# too-greedy one costs a false candidate, so new entries should stay specific.
SAID_CARD_PATTERNS = (
    "值得进记忆", "值得记一笔", "值得立卡", "值得写张卡", "记一张卡", "写一张卡", "写张卡",
    "该立卡", "立一张卡", "立张卡", "该写进记忆", "写进记忆", "写进 memory", "写进memory",
    "存进记忆", "进记忆层", "补一张卡", "补张卡", "补进记忆",
    "worth a memory card", "should write a card", "write a memory card",
)

# What counts as a topic word when matching a promise against the cards that
# appeared after it.  Latin runs are identifier-shaped and taken whole; a run of
# Chinese is cut into overlapping two-character grams, because Chinese does not
# space its words and a whole-run token would only ever match an identical
# sentence.
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-/]{3,}")
_CJK_RUN_RE = re.compile(r"[一-鿿]{2,}")
# Vocabulary every promise shares, plus the words a promise is made of.  Left
# in, they would match almost any new card and silently answer "kept".
_TOPIC_STOPWORDS = frozenset(
    {"记忆", "卡片", "一张", "这个", "那个", "应该", "值得", "写进", "立卡", "进记", "一笔", "memory",
     "card", "cards", "write", "should", "worth", "的东", "东西", "这正", "正是", "就是", "不是", "可以",
     "没有", "已经", "现在", "我们", "如果", "问题", "一个", "所以", "还是", "这里", "那里", "什么"}
)

_INDEX_ENTRY_RE = re.compile(r"^\s*[-*]\s*\[(?P<title>[^\]]*)\]\((?P<target>[^)]+)\)(?P<rest>.*)$")
_WIKILINK_RE = re.compile(r"\[\[([^\]\n|]+?)\]\]")
_FRONTMATTER_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<value>.*?)\s*$")


class MemoryScanError(RuntimeError):
    """A fail-closed memory-adapter error."""


class SelfCheckRefusal(MemoryScanError):
    """The generation preconditions were not met, so no report is produced."""


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Card:
    layer: str
    key: str
    path: Path
    display: str
    body: str


def _read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MemoryScanError(f"cannot read {path}: {exc}") from exc


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
        if match is None:
            continue
        value = match.group("value").strip().strip('"').strip("'")
        fields[match.group("key")] = value
    return fields


def load_cards(directory: Path, *, layer: str, key_field: str) -> dict[str, Card]:
    """Every ``*.md`` in a card directory, keyed the way that layer cites them.

    vnext cards are cited by frontmatter ``id``, file-memory cards by ``name``,
    with the filename stem as the fallback for either.
    """
    if not directory.is_dir():
        raise MemoryScanError(f"card directory does not exist: {directory}")
    cards: dict[str, Card] = {}
    for path in sorted(directory.glob("*.md")):
        if path.name == INDEX_FILENAME:
            continue
        text = _read_text(path)
        front = parse_frontmatter(text)
        key = front.get(key_field) or path.stem
        display = front.get("title") or front.get("description") or front.get("summary") or ""
        cards[key] = Card(layer=layer, key=key, path=path, display=display, body=text)
    return cards


@dataclass(frozen=True)
class IndexEntry:
    line: int
    title: str
    target: str
    description: str


def load_index(directory: Path) -> tuple[Path, tuple[IndexEntry, ...]]:
    index_path = directory / INDEX_FILENAME
    if not index_path.is_file():
        raise MemoryScanError(f"file-memory index does not exist: {index_path}")
    entries: list[IndexEntry] = []
    for number, line in enumerate(_read_text(index_path).split("\n"), start=1):
        match = _INDEX_ENTRY_RE.match(line)
        if match is None:
            continue
        entries.append(IndexEntry(number, match.group("title").strip(), match.group("target").strip(),
                                  match.group("rest").strip(" —-")))
    return index_path, tuple(entries)


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    flag: str
    layer: str
    subject: str
    locator: str
    signals: tuple[str, ...]
    evidence: dict[str, Any]
    confidence: str = CONFIDENCE_DETERMINISTIC
    locked: bool = False  # locked == FYI: reported, never proposed as a cleanup candidate
    lock_reasons: tuple[str, ...] = ()


def _item(finding: Finding) -> dict[str, Any]:
    payload = "␟".join((finding.layer, finding.flag, finding.subject, finding.locator))
    return {
        "item_id": hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16],
        "layer": finding.layer,
        "flag": finding.flag,
        "signals": list(finding.signals),
        "safety_lock": {"locked": finding.locked, "reasons": list(finding.lock_reasons)},
        "confidence": finding.confidence,
        "evidence": dict(finding.evidence),
    }


def scan_index_integrity(directory: Path, cards: dict[str, Card], entries: Sequence[IndexEntry]) -> list[Finding]:
    findings: list[Finding] = []
    indexed = {entry.target for entry in entries}
    for key, card in sorted(cards.items()):
        if card.path.name in indexed:
            continue
        findings.append(Finding(
            flag="orphan_card", layer=LAYER_FILE, subject=key, locator=card.path.name,
            signals=("card_file_has_no_line_in_the_memory_index",),
            evidence={"card": card.path.name, "index": str(directory / INDEX_FILENAME),
                      "detail": "unindexed cards are invisible at session start"},
        ))
    for entry in entries:
        if (directory / entry.target).is_file():
            continue
        findings.append(Finding(
            flag="dangling_index_entry", layer=LAYER_FILE, subject=entry.target,
            locator=f"{INDEX_FILENAME}:{entry.line}",
            signals=("index_line_points_at_a_file_that_does_not_exist",),
            evidence={"index_line": entry.line, "title": entry.title, "target": entry.target},
        ))
    return findings


def scan_wikilinks(cards: dict[str, Card], *, layer: str, aliases: set[str]) -> list[Finding]:
    """Dangling ``[[name]]`` links, locked to FYI at the source.

    The v2 design calls these a mark worth recording rather than an error, so
    the lock is set here instead of being left to a reader's judgement.
    """
    findings: list[Finding] = []
    for key, card in sorted(cards.items()):
        seen: set[str] = set()
        for number, line in enumerate(card.body.split("\n"), start=1):
            for match in _WIKILINK_RE.finditer(line):
                target = match.group(1).strip()
                if not target or target in aliases or target in seen:
                    continue
                seen.add(target)
                findings.append(Finding(
                    flag="dangling_wikilink", layer=layer, subject=key,
                    locator=f"{card.path.name}:{number}:{target}",
                    signals=("wikilink_target_is_not_a_card_in_this_layer",),
                    evidence={"card": card.path.name, "line": number, "target": target,
                              "line_text": line.strip()[:400]},
                    locked=True,
                    lock_reasons=("a_link_to_a_missing_card_is_a_mark_worth_recording_not_a_defect",),
                ))
    return findings


# --------------------------------------------------------------------------
# never_read_card
# --------------------------------------------------------------------------


def _parse_timestamp(raw: str) -> datetime | None:
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_injection_ledger(path: Path) -> tuple[set[str], datetime | None, datetime | None, int]:
    injected: set[str] = set()
    first: datetime | None = None
    last: datetime | None = None
    lines = 0
    if not path.is_file():
        return injected, first, last, lines
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            lines += 1
            moment = _parse_timestamp(str(record.get("ts", "")))
            if moment is not None:
                first = moment if first is None else min(first, moment)
                last = moment if last is None else max(last, moment)
            for entry in record.get("injected") or ():
                if isinstance(entry, dict) and entry.get("id"):
                    injected.add(str(entry["id"]))
                elif isinstance(entry, str):
                    injected.add(entry)
    return injected, first, last, lines


def git_added_at(root: Path, path: Path) -> datetime | None:
    """When a tracked file first appeared, or ``None`` if git cannot say."""
    args = ["git", "-C", str(root), "log", "--diff-filter=A", "--format=%aI", "-1", "--", str(path)]
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return _parse_timestamp(completed.stdout.strip().split("\n")[0])


def scan_never_read(root: Path, cards: dict[str, Card], ledger_path: Path) -> tuple[list[Finding], dict[str, Any]]:
    injected, first, last, lines = read_injection_ledger(ledger_path)
    if not lines:
        return [], {"status": "no_data", "layer": LAYER_VNEXT, "missing_ledger": str(ledger_path),
                    "detail": "no injection ledger, so 'never read' is not answerable for this layer"}
    window = {"ledger": str(ledger_path), "ledger_first_entry": first.isoformat() if first else None,
              "ledger_last_entry": last.isoformat() if last else None}
    findings: list[Finding] = []
    for key, card in sorted(cards.items()):
        if key in injected:
            continue
        added = git_added_at(root, card.path)
        # A card older than the ledger may well have been read before the ledger
        # existed, and no amount of reading it now would show up.  Only a card
        # the ledger fully covers can be a candidate.
        covered = added is not None and first is not None and added >= first
        findings.append(Finding(
            flag="never_read_card", layer=LAYER_VNEXT, subject=key, locator=card.path.name,
            signals=("card_id_never_appears_in_the_injection_ledger",),
            evidence={"card": card.path.name, **window, "card_added_at": added.isoformat() if added else None,
                      "ledger_covers_whole_card_lifetime": covered},
            locked=not covered,
            lock_reasons=() if covered else ("ledger_starts_after_the_card_did_so_earlier_reads_are_unknowable",),
        ))
    status = {"status": "computed", "layer": LAYER_VNEXT, **window, "ledger_entries": lines,
              "distinct_injected_ids": len(injected)}
    return findings, status


def file_memory_never_read_status(directory: Path) -> dict[str, Any]:
    """Why this layer gets a blank instead of a number."""
    return {
        "status": "no_data", "layer": LAYER_FILE, "directory": str(directory),
        "missing_ledger": "no per-card read or injection ledger exists for the file-memory layer",
        "why_no_proxy": "the index is injected whole at session start, so injection cannot discriminate "
                        "between cards, and transcripts only cover retained sessions",
        "what_would_close_it": "a ledger recording which card bodies were opened, written at the read",
    }


# --------------------------------------------------------------------------
# said_card_unwritten
# --------------------------------------------------------------------------


def topic_tokens(text: str) -> set[str]:
    tokens = {match.group(0).lower() for match in _LATIN_TOKEN_RE.finditer(text)}
    for run in _CJK_RUN_RE.finditer(text):
        word = run.group(0)
        tokens.update(word[index : index + 2] for index in range(len(word) - 1))
    return {token for token in tokens if token not in _TOPIC_STOPWORDS}


@dataclass(frozen=True)
class Promise:
    transcript: str
    session: str
    at: datetime
    pattern: str
    quote: str


def _text_blocks(record: dict[str, Any]) -> Iterator[str]:
    """The assistant's own spoken reply text, and nothing else.

    Provenance is the whole point of this filter (2026-08-03 adversarial review
    ``promise-provenance-self-trigger``).  A promise is something the assistant
    *said it would do*, so two other sources have to be excluded even though
    they contain the same words:

    * **user turns** — the operator quoting or negating a phrase ("I did not
      promise to 'write a memory card about X'") is not a commitment by anyone.
      The old reader took ``message.content`` as a bare string, which is exactly
      the shape a user turn has, so every quotation became a promise.
    * **``thinking`` blocks** — deliberation is not a commitment.  Reasoning
      out loud about whether a card is worth writing, and concluding no, used to
      produce a candidate accusing the session of breaking a promise it never
      made.  This is a real narrowing: a promise made only in thinking and then
      kept silently is now missed.  That trade is deliberate — the flag is
      already the file's one heuristic, and a false accusation costs more than a
      missed one.

    The exclusion is stated in the module docstring and published in
    ``metadata.sources.promise_provenance``.
    """
    message = record.get("message")
    if not isinstance(message, dict):
        return
    if message.get("role") != "assistant":
        return
    content = message.get("content")
    if isinstance(content, str):
        yield content
        return
    for block in content if isinstance(content, list) else ():
        if not isinstance(block, dict):
            continue
        value = block.get("text")
        if isinstance(value, str) and value:
            yield value


def _quote_around(text: str, index: int, *, width: int = 160) -> str:
    start = max(0, index - width // 2)
    return text[start : index + width // 2].replace("\n", " ").strip()


def _transcript_label(root: Path, path: Path) -> str:
    """How a transcript is named in a finding, now that they nest.

    A bare filename stopped being unique once subdirectories were included, and
    a locator that cannot be reopened is not evidence.
    """
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


# The prune system's own governance surfaces.  A promise-shaped sentence that
# comes from one of these is the system reading itself: an eval fixture, a card
# body, a test, or this batch's own design notes.  Same marker shape as the
# error-recall hook's ``governance_target`` (P2.2, ``cc_memory_vnext/hooks/
# post_tool_error_recall.py``) -- directory paths with a slash, so ordinary
# source paths cannot collide -- and deliberately a separate copy: the two
# scanners share the rule, not the code, so one refactor cannot widen the
# other's blast radius.  ``test_the_governance_markers_match_the_hook`` keeps
# the two lists from drifting.
GOVERNANCE_PATH_MARKERS = (
    "cc_memory_vnext/eval",
    "cc_memory_vnext/cards",
    "cc_memory_vnext/tests",
    "cc_memory/tests",
    ".artifacts/prune_v2_",
)


def governance_context(text: str) -> str | None:
    """Which governance surface this promise-shaped sentence is talking about.

    ``None`` when it is talking about ordinary work.  Matching is on the quoted
    window rather than the whole record: a long session that merely touched a
    card file earlier should still have its real promises read.
    """
    haystack = text.replace("\\", "/")
    for marker in GOVERNANCE_PATH_MARKERS:
        if marker in haystack:
            return marker
    return None


def collect_promises(transcript_dir: Path) -> tuple[list[Promise], dict[str, Any]]:
    """Every "I will write a card" line the assistant actually said.

    A raw substring test on the undecoded line skips the JSON parse for almost
    all of a half-gigabyte of transcripts; survivors are parsed properly.

    Enumeration is **recursive** (2026-08-03 adversarial review
    ``nested-transcript-omission``).  The transcript directory has 59 files at
    its top level and 1100 in the tree: subagent and workflow sessions get their
    own subdirectories, and those are the sessions this flag most wants to read,
    because a subagent that says it will write a card and does not is exactly
    the missed-promise shape the flag exists for.  The old direct-child glob saw
    none of them while the module docstring claimed retained-transcript
    coverage.

    Returns the promises plus a stats dict that the report publishes verbatim,
    so "how many did you read, and what did you drop" is answerable from the
    report instead of from this source.
    """
    if not transcript_dir.is_dir():
        raise MemoryScanError(f"transcript directory does not exist: {transcript_dir}")
    raw_patterns = [pattern.encode("utf-8") for pattern in SAID_CARD_PATTERNS]
    promises: list[Promise] = []
    scanned = 0
    nested = 0
    matched_records = 0
    excluded_not_assistant_text = 0
    excluded_governance_context = 0
    for path in sorted(transcript_dir.rglob("*.jsonl")):
        if not path.is_file():
            continue
        scanned += 1
        if path.parent != transcript_dir:
            nested += 1
        with path.open("rb") as stream:
            for raw in stream:
                if not any(pattern in raw for pattern in raw_patterns):
                    continue
                try:
                    record = json.loads(raw.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                moment = _parse_timestamp(str(record.get("timestamp", "")))
                if moment is None:
                    continue
                matched_records += 1
                blocks = list(_text_blocks(record))
                if not blocks:
                    excluded_not_assistant_text += 1
                    continue
                for text in blocks:
                    for pattern in SAID_CARD_PATTERNS:
                        index = text.find(pattern)
                        if index < 0:
                            continue
                        quote = _quote_around(text, index)
                        marker = governance_context(quote)
                        if marker is not None:
                            excluded_governance_context += 1
                            continue
                        promises.append(Promise(
                            _transcript_label(transcript_dir, path),
                            str(record.get("sessionId", "")),
                            moment,
                            pattern,
                            quote,
                        ))
    stats = {
        "transcripts_scanned": scanned,
        "transcripts_in_subdirectories": nested,
        "records_matching_a_phrase": matched_records,
        "excluded_not_assistant_reply_text": excluded_not_assistant_text,
        "excluded_governance_context": excluded_governance_context,
        "promises_kept": len(promises),
        "enumeration": "recursive (rglob) over *.jsonl, subagent sessions included",
        "promise_provenance": (
            "assistant-role reply text only; user turns and thinking blocks are "
            "excluded, so a promise made only while thinking is missed on purpose"
        ),
        "governance_exclusion_markers": list(GOVERNANCE_PATH_MARKERS),
    }
    return promises, stats


@dataclass(frozen=True)
class CardArrival:
    layer: str
    key: str
    at: datetime
    tokens: frozenset[str]


def card_arrivals(root: Path, file_cards: dict[str, Card], vnext_cards: dict[str, Card]) -> list[CardArrival]:
    """When each live card appeared, with the topic words it is about.

    vnext cards are tracked, so git dates them; file-memory cards are outside
    the repository, so mtime is the only date on offer.  An edited file-memory
    card therefore looks newer than it is, which can only suppress a candidate,
    never invent one.
    """
    arrivals: list[CardArrival] = []
    for key, card in file_cards.items():
        try:
            moment: datetime | None = datetime.fromtimestamp(card.path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if moment is not None:
            arrivals.append(CardArrival(LAYER_FILE, key, moment, frozenset(topic_tokens(f"{key} {card.display}"))))
    for key, card in vnext_cards.items():
        moment = git_added_at(root, card.path)
        if moment is not None:
            arrivals.append(CardArrival(LAYER_VNEXT, key, moment, frozenset(topic_tokens(f"{key} {card.display}"))))
    return arrivals


def scan_said_card_unwritten(promises: Sequence[Promise], arrivals: Sequence[CardArrival], *,
                             window_days: int) -> list[Finding]:
    """A promise is kept if a card sharing one of its topic words arrived in the window.

    Sharing a topic word is a loose test, and loose in the safe direction: it
    over-credits, so the flag under-reports rather than accusing the operator of
    a promise they did in fact keep under a different name.
    """
    window = timedelta(days=window_days)
    findings: list[Finding] = []
    seen: set[str] = set()
    for promise in sorted(promises, key=lambda item: (item.at, item.transcript, item.quote)):
        wanted = topic_tokens(promise.quote)
        if not wanted:
            continue
        kept: CardArrival | None = None
        for arrival in arrivals:
            if not promise.at <= arrival.at <= promise.at + window:
                continue
            if arrival.tokens & wanted:
                kept = arrival
                break
        if kept is not None:
            continue
        locator = hashlib.sha256(promise.quote.encode("utf-8")).hexdigest()[:12]
        if locator in seen:
            continue
        seen.add(locator)
        findings.append(Finding(
            flag="said_card_unwritten", layer=LAYER_TRANSCRIPT, subject=promise.pattern,
            locator=f"{promise.transcript}:{locator}",
            signals=("a_session_said_it_would_write_a_card",
                     f"no_matching_card_appeared_within_{window_days}_days"),
            evidence={"transcript": promise.transcript, "session": promise.session,
                      "said_at": promise.at.isoformat(), "pattern": promise.pattern, "quote": promise.quote,
                      "window_days": window_days,
                      "matched_on": "a card whose id or title shares a topic word with the quote"},
            confidence=CONFIDENCE_HEURISTIC,
        ))
    return findings


# --------------------------------------------------------------------------
# self check, report, write
# --------------------------------------------------------------------------


SELF_CHECK_GIT_COMMAND = (
    "git status --porcelain=v1 --untracked-files=all --ignored -- <cards>"
)


def run_self_check(root: Path, cards_relpath: str) -> dict[str, Any]:
    """Fail closed on an uncommitted in-repository card, declare the rest.

    Same spirit as the docs adapter — a report must not be shaped by bytes
    nobody committed — but only half the subject matter is in the repository, so
    the check reports which half it covered rather than implying it covered all.

    ``--untracked-files=all --ignored`` is not optional (2026-08-03 adversarial
    review ``hidden-dirty-card-claim``, and the same fix the docs adapter took
    in P1.2).  The card loader enumerates ``*.md`` off the filesystem, while
    git's default status view says nothing about a path ``.gitignore`` covers.
    A single ignored card file therefore changed the findings while the report
    printed ``in_repository_cards_clean: true``.  ``.gitignore`` is committed,
    so an ignored path here is ordinary developer state rather than an
    attacker's construction — which is exactly why it has to be visible.

    Still not covered, and declared rather than closed: ``assume-unchanged`` /
    ``skip-worktree`` marks, which switch every git dirty check off at once.
    See the module docstring's known-boundaries section.
    """
    args = [
        "git", "-C", str(root), "status", "--porcelain=v1",
        "--untracked-files=all", "--ignored", "--", cards_relpath,
    ]
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SelfCheckRefusal(f"cannot run git for the in-repository self check: {exc}") from exc
    if completed.returncode != 0:
        raise SelfCheckRefusal(f"git status failed for {cards_relpath}: {completed.stderr.strip()}")
    dirty = [line for line in completed.stdout.split("\n") if line.strip()]
    if dirty:
        raise SelfCheckRefusal(
            f"{cards_relpath} has uncommitted, untracked or ignored files, so a report would "
            f"describe bytes nobody committed: {'; '.join(entry.strip() for entry in dirty[:5])}"
        )
    return {"in_repository_cards_clean": True, "checked_path": cards_relpath,
            "verified_by": SELF_CHECK_GIT_COMMAND,
            "out_of_repository_objects_are_read_as_found": True}


def build_report(
    *,
    root: Path = ROOT,
    file_memory_dir: Path = DEFAULT_FILE_MEMORY_DIR,
    vnext_cards_dir: Path | None = None,
    transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
    activation_ledger: Path | None = None,
    window_days: int = 3,
) -> dict[str, Any]:
    vnext_dir = vnext_cards_dir if vnext_cards_dir is not None else root / VNEXT_CARDS_RELPATH
    ledger = activation_ledger if activation_ledger is not None else root / ACTIVATION_LEDGER_RELPATH

    try:
        relative_cards = str(vnext_dir.resolve().relative_to(root.resolve()))
    except ValueError:
        relative_cards = str(vnext_dir)
    preconditions = run_self_check(root, relative_cards)

    file_cards = load_cards(file_memory_dir, layer=LAYER_FILE, key_field="name")
    index_path, entries = load_index(file_memory_dir)
    vnext_cards = load_cards(vnext_dir, layer=LAYER_VNEXT, key_field="id")

    findings: list[Finding] = []
    findings.extend(scan_index_integrity(file_memory_dir, file_cards, entries))

    file_aliases = set(file_cards) | {card.path.stem for card in file_cards.values()}
    findings.extend(scan_wikilinks(file_cards, layer=LAYER_FILE, aliases=file_aliases))
    findings.extend(scan_wikilinks(vnext_cards, layer=LAYER_VNEXT, aliases=set(vnext_cards)))

    never_read, vnext_status = scan_never_read(root, vnext_cards, ledger)
    findings.extend(never_read)

    promises, promise_stats = collect_promises(transcript_dir)
    arrivals = card_arrivals(root, file_cards, vnext_cards)
    findings.extend(scan_said_card_unwritten(promises, arrivals, window_days=window_days))

    findings.sort(key=lambda item: (item.layer, item.flag, item.subject, item.locator))
    candidates = [_item(finding) for finding in findings if not finding.locked]
    fyi = [_item(finding) for finding in findings if finding.locked]

    flag_counts = {flag: 0 for flag in FLAGS}
    for finding in findings:
        flag_counts[finding.flag] += 1

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "metadata": {
            "generator": GENERATOR,
            "generator_version": GENERATOR_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "advisory": True,
            "applies_nothing": (
                "This report authorizes no edit; nothing in the repository consumes it."
            ),
            "threat_model": THREAT_MODEL,
            "self_check_scope": dict(SELF_CHECK_SCOPE),
            "preconditions": preconditions,
            "sources": {
                "file_memory_dir": str(file_memory_dir), "file_memory_index": str(index_path),
                "file_memory_card_count": len(file_cards), "file_memory_index_entry_count": len(entries),
                "vnext_cards_dir": str(vnext_dir), "vnext_card_count": len(vnext_cards),
                "transcript_dir": str(transcript_dir),
                "transcripts_scanned": promise_stats["transcripts_scanned"],
                "promises_found": len(promises), "said_card_window_days": window_days,
                "promise_collection": dict(promise_stats),
            },
            "never_read_card_status": [vnext_status, file_memory_never_read_status(file_memory_dir)],
            "flag_counts": flag_counts,
            "candidate_count": len(candidates),
            "fyi_count": len(fyi),
        },
        "candidates": candidates,
        "fyi": fyi,
    }


def resolve_report_destination(root: Path, relpath: str) -> Path:
    """The one place a report may be written, or a fail-closed refusal.

    Independent implementation of the docs adapter's four constraints:
    repository-relative, no upward traversal, rooted at ``.prune/``, no symlinked
    component, regular file at the end.  The scanners share the rule and
    deliberately not the code — a shared helper would let one scanner's refactor
    widen another's blast radius.
    """
    if not isinstance(relpath, str) or not relpath.strip():
        raise MemoryScanError("report path must be a non-empty repository-relative path")
    if "\0" in relpath or "\\" in relpath:
        raise MemoryScanError(f"report path is not a safe repository-relative path: {relpath!r}")
    if relpath.startswith("/") or PurePosixPath(relpath).is_absolute():
        raise MemoryScanError(f"report path must be relative, not absolute: {relpath!r}")
    parts = [part for part in PurePosixPath(relpath).parts if part != "."]
    if any(part == ".." for part in parts):
        raise MemoryScanError(f"report path may not traverse upwards: {relpath!r}")
    if len(parts) < 2 or parts[0] != REPORT_DIR_RELPATH:
        raise MemoryScanError(f"report path must name a file under {REPORT_DIR_RELPATH}/: {relpath!r}")
    if not root.is_dir():
        raise MemoryScanError(f"repository root is not a directory: {root}")

    walked = root
    for index, part in enumerate(parts):
        walked = walked / part
        so_far = "/".join(parts[: index + 1])
        try:
            status = walked.lstat()
        except FileNotFoundError:
            break
        except OSError as exc:
            raise MemoryScanError(f"cannot inspect report path component {so_far}: {exc}") from exc
        if stat.S_ISLNK(status.st_mode):
            raise MemoryScanError(f"refusing to write through a symlink: {so_far}")
        if index == len(parts) - 1:
            if not stat.S_ISREG(status.st_mode):
                raise MemoryScanError(f"report destination is not a regular file: {so_far}")
        elif not stat.S_ISDIR(status.st_mode):
            raise MemoryScanError(f"report path component is not a directory: {so_far}")
    return root.joinpath(*parts)


def write_report(root: Path, report: dict[str, Any], *, relpath: str = REPORT_RELPATH) -> Path:
    destination = resolve_report_destination(root, relpath)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise MemoryScanError(f"report directory is not a plain directory: {parent}")
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    try:
        handle = os.open(destination, flags, 0o644)
    except OSError as exc:
        raise MemoryScanError(f"cannot open report destination {destination}: {exc}") from exc
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(payload)
    return destination


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--file-memory-dir", default=str(DEFAULT_FILE_MEMORY_DIR))
    parser.add_argument("--vnext-cards-dir", default=None)
    parser.add_argument("--transcript-dir", default=str(DEFAULT_TRANSCRIPT_DIR))
    parser.add_argument("--activation-ledger", default=None)
    parser.add_argument("--said-card-window-days", type=int, default=3)
    parser.add_argument(
        "--output",
        default=REPORT_RELPATH,
        help=f"report path, which must be a repository-relative file under {REPORT_DIR_RELPATH}/",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.repo_root).resolve()
    try:
        resolve_report_destination(root, args.output)
        report = build_report(
            root=root,
            file_memory_dir=Path(args.file_memory_dir),
            vnext_cards_dir=Path(args.vnext_cards_dir) if args.vnext_cards_dir else None,
            transcript_dir=Path(args.transcript_dir),
            activation_ledger=Path(args.activation_ledger) if args.activation_ledger else None,
            window_days=args.said_card_window_days,
        )
        destination = write_report(root, report, relpath=args.output)
    except SelfCheckRefusal as exc:
        print(f"memory reference scan refused: {exc}", file=sys.stderr)
        return 1
    except MemoryScanError as exc:
        print(f"memory reference scan failed: {exc}", file=sys.stderr)
        return 1
    summary = {"status": "REPORT_WRITTEN", "report": str(destination),
               "candidates": report["metadata"]["candidate_count"], "fyi": report["metadata"]["fyi_count"]}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
