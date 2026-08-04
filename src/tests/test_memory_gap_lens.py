"""Behavioural tests for the memory gap lens shell (assemble / verify).

Every scenario is built inside a throwaway fixture — a small git repository for
the in-repository half, plain directories for the file-memory and transcript
halves, a hand-built archive database — so the tests state what the tool does
rather than what this machine happens to contain.  Nothing here reads the real
memory layers, the real transcripts or the real archive.

The landing-verification cases are the point of the file: a language model wrote
the candidates, so each check that stands between a confident sentence and the
report is exercised on its own, and the structural test at the end pins the
absence of an apply path by AST rather than by intention.
"""

from __future__ import annotations

import ast
import collections
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devtools import memory_gap_lens as lens  # noqa: E402

NOW = datetime(2026, 8, 3, 12, 0, 0, tzinfo=timezone.utc)
BODY_MARKER = "CARDBODY-must-never-reach-the-evidence-package"
QUOTE = "the argv self-match pitfall bit us four times in three weeks"

GIT_ENV_ARGS = (
    "-c", "user.name=gap lens fixture",
    "-c", "user.email=fixture@invalid",
    "-c", "commit.gpgsign=false",
    "-c", "core.hooksPath=/dev/null",
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *GIT_ENV_ARGS, *args], cwd=str(root), check=True, capture_output=True)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _touched(path: Path, days_ago: float) -> Path:
    moment = (NOW - timedelta(days=days_ago)).timestamp()
    os.utime(path, (moment, moment))
    return path


def _archive_db(path: Path, entries: tuple[tuple[str, str], ...]) -> Path:
    """A WAL-mode archive, because the real ``cc_memory/memory.db`` is one.

    The journal mode is not decoration: a plain ``mode=ro`` open of a WAL
    database creates ``-wal`` and ``-shm`` beside it, and a rollback-journal
    fixture would have hidden that from every test in this file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    with connection:
        connection.execute("CREATE TABLE entries(id TEXT PRIMARY KEY, title TEXT NOT NULL, "
                           "body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active')")
        connection.executemany("INSERT INTO entries(id, title, body) VALUES (?, ?, 'archived body')",
                               entries)
    connection.close()
    return path


def _sidecars(db_path: Path) -> list[Path]:
    """The two files SQLite drops beside a WAL database when it is opened for real."""
    return [db_path.parent / f"{db_path.name}{suffix}" for suffix in ("-wal", "-shm")]


@pytest.fixture()
def world(tmp_path: Path) -> dict[str, Any]:
    """A repository half, a home half and a transcript half, all disposable."""
    repo = tmp_path / "repo"
    cards = repo / lens.VNEXT_CARDS_RELPATH
    _write(cards / "agent-longrun-wait-wake-protocol.md",
           "---\nid: agent-longrun-wait-wake-protocol\nkind: decision\n"
           f"summary: teammate agents sleep through long runs\n---\n{BODY_MARKER}\n")
    _write(cards / "process-probe-argv-self-match.md",
           "---\nid: process-probe-argv-self-match\nkind: pitfall\n"
           f"summary: pgrep -f matches its own argv\n---\n{BODY_MARKER}\n")
    _archive_db(repo / lens.CC_MEMORY_DB_RELPATH,
                (("frozen-archive-map-20260803", "archive map"), ("fact-single-source", "single source")))
    _git(repo, "init", "-q", ".")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")

    memory_dir = tmp_path / "home" / "memory"
    _write(memory_dir / "MEMORY.md",
           "# Memory Index\n"
           "- [argv self-match](process-probe-argv-self-match-pitfall.md) — pgrep -f bites itself\n"
           "- [disk layout](disk-archive-layout-and-root-hogs.md) — root disk fills up\n"
           "\nnot an index line at all\n")
    _write(memory_dir / "process-probe-argv-self-match-pitfall.md",
           f"---\nname: process-probe-argv-self-match-pitfall\ndescription: \"argv self match\"\n---\n"
           f"{BODY_MARKER}\n{QUOTE}\n")
    _write(memory_dir / "disk-archive-layout-and-root-hogs.md",
           f"---\nname: disk-archive-layout-and-root-hogs\ndescription: \"disk layout\"\n---\n{BODY_MARKER}\n")

    transcripts = tmp_path / "home" / "transcripts"
    fresh = _write(transcripts / "session-a.jsonl",
                   json.dumps({"type": "assistant", "text": f"I said: {QUOTE}"}, ensure_ascii=False) + "\n")
    nested = _write(transcripts / "sub" / "session-b.jsonl",
                    json.dumps({"type": "assistant", "text": "nested and recent"}) + "\n")
    stale = _write(transcripts / "session-old.jsonl", json.dumps({"type": "user", "text": "old"}) + "\n")
    _touched(fresh, 1)
    _touched(nested, 3)
    _touched(stale, 30)

    return {"repo": repo, "cards": cards, "memory_dir": memory_dir, "transcripts": transcripts,
            "archive_db": repo / lens.CC_MEMORY_DB_RELPATH, "fresh": fresh, "card_path": memory_dir /
            "process-probe-argv-self-match-pitfall.md"}


def _assemble(world: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "root": world["repo"], "file_memory_dir": world["memory_dir"],
        "transcript_dir": world["transcripts"], "now": NOW,
    }
    arguments.update(overrides)
    return lens.build_evidence(**arguments)


def _verify(world: dict[str, Any], candidates: Any, tmp_path: Path, **overrides: Any) -> dict[str, Any]:
    path = tmp_path / "candidates.json"
    payload = candidates if isinstance(candidates, str) else json.dumps(candidates, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")
    arguments: dict[str, Any] = {
        "root": world["repo"], "file_memory_dir": world["memory_dir"],
        "transcript_dir": world["transcripts"], "now": NOW,
    }
    arguments.update(overrides)
    return lens.build_candidate_report(path, **arguments)


def _candidate(**overrides: Any) -> dict[str, Any]:
    base = {"kind": "ADD", "object_layer": lens.LAYER_FILE,
            "claim": "the argv pitfall was never written down while it was biting",
            "evidence": [{"path": "PLACEHOLDER", "quote": QUOTE}],
            "proposed_action": "write a card naming the pgrep -f self-match"}
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# assemble
# --------------------------------------------------------------------------


def test_assemble_counts_each_layer(world: dict[str, Any]) -> None:
    package = _assemble(world)
    counts = package["metadata"]["counts"]
    assert counts["file_memory_index_lines"] == 2
    assert counts["file_memory_cards"] == 2
    assert counts["vnext_cards"] == 2
    assert counts["archive_entries"] == 2
    assert counts["transcripts_in_window"] == 2  # the 30-day-old transcript is outside the window
    assert package["schema_version"] == lens.EVIDENCE_SCHEMA_VERSION
    assert package["metadata"]["threat_model"] == lens.THREAT_MODEL
    assert package["metadata"]["advisory"] is True


def test_assemble_carries_pointers_not_bodies(world: dict[str, Any]) -> None:
    package = _assemble(world)
    assert BODY_MARKER not in json.dumps(package, ensure_ascii=False)

    index_lines = package["file_memory"]["index_lines"]
    assert [entry["line"] for entry in index_lines] == [2, 3]
    assert index_lines[0]["text"].startswith("- [argv self-match]")
    assert index_lines[0]["target"] == "process-probe-argv-self-match-pitfall.md"

    card = next(item for item in package["file_memory"]["cards"]
                if item["name"] == "process-probe-argv-self-match-pitfall")
    assert card["description"] == "argv self match"
    assert card["path"] == str(world["card_path"])
    assert card["mtime_utc"].endswith("Z")

    vnext = next(item for item in package["vnext"]["cards"] if item["id"] == "process-probe-argv-self-match")
    assert vnext["kind"] == "pitfall" and vnext["summary"] == "pgrep -f matches its own argv"

    assert {entry["id"] for entry in package["cc_memory_archive"]["entries"]} == {
        "frozen-archive-map-20260803", "fact-single-source"}
    assert package["cc_memory_archive"]["status"] == "frozen_read_only"


def test_assemble_lists_nested_transcripts_without_reading_them(world: dict[str, Any]) -> None:
    listing = _assemble(world)["transcripts"]
    paths = {record["path"] for record in listing["files"]}
    assert paths == {str(world["fresh"]), str(world["transcripts"] / "sub" / "session-b.jsonl")}
    assert all(set(record) == {"path", "mtime_utc", "size_bytes"} for record in listing["files"])
    assert all(record["size_bytes"] > 0 for record in listing["files"])
    assert "nested and recent" not in json.dumps(listing, ensure_ascii=False)


def test_assemble_attaches_the_deterministic_prior_when_present(world: dict[str, Any],
                                                                tmp_path: Path) -> None:
    absent = _assemble(world)
    assert absent["deterministic_prior"]["present"] is False
    assert absent["metadata"]["counts"]["deterministic_prior_present"] is False

    prior = _write(world["repo"] / lens.PRIOR_REPORT_RELPATH,
                   json.dumps({"schema_version": "prune_memory_reference_report_v1",
                               "metadata": {"candidate_count": 3}, "candidates": [], "fyi": []}))
    package = _assemble(world, prior_report=prior)
    assert package["deterministic_prior"]["present"] is True
    assert package["deterministic_prior"]["report"]["metadata"]["candidate_count"] == 3


def test_assemble_refuses_on_an_uncommitted_in_repository_card(world: dict[str, Any]) -> None:
    _write(world["cards"] / "process-probe-argv-self-match.md",
           "---\nid: process-probe-argv-self-match\nkind: pitfall\nsummary: edited in place\n---\nbody\n")
    with pytest.raises(lens.SelfCheckRefusal) as caught:
        _assemble(world)
    assert "uncommitted" in str(caught.value)


def test_assemble_refuses_on_an_untracked_card(world: dict[str, Any]) -> None:
    _write(world["cards"] / "brand-new.md", "---\nid: brand-new\n---\nbody\n")
    with pytest.raises(lens.SelfCheckRefusal):
        _assemble(world)


def test_assemble_reads_the_archive_without_leaving_sidecars(world: dict[str, Any]) -> None:
    """A tool that claims to change nothing must not deposit two files per run.

    A bare ``mode=ro`` open of a WAL database creates ``memory.db-wal`` and
    ``memory.db-shm`` next to it — which is a write, into the frozen archive
    layer's own directory, on every ``assemble`` and every ``verify``.  Same
    finding and same fix as ``cc_memory/mem.py:connect_immutable``.
    """
    database = world["archive_db"]
    assert not any(path.exists() for path in _sidecars(database)), "fixture starts clean"

    package = _assemble(world)

    assert package["metadata"]["counts"]["archive_entries"] == 2, "the archive really was read"
    assert [path for path in _sidecars(database) if path.exists()] == []


def test_verify_reads_the_archive_without_leaving_sidecars(world: dict[str, Any], tmp_path: Path) -> None:
    database = world["archive_db"]
    candidate = _candidate(kind="CORRECT", object_layer=lens.LAYER_ARCHIVE,
                           object_id="frozen-archive-map-20260803",
                           evidence=[{"path": str(world["card_path"]), "quote": QUOTE}])
    report = _verify(world, [candidate], tmp_path)
    assert report["metadata"]["accepted_count"] == 1, "the archive keys really were read"
    assert [path for path in _sidecars(database) if path.exists()] == []


def test_assemble_declares_what_its_self_check_does_not_cover(world: dict[str, Any]) -> None:
    metadata = _assemble(world)["metadata"]
    assert metadata["preconditions"]["in_repository_objects_clean"] is True
    assert metadata["preconditions"]["checked_paths"] == list(lens.SELF_CHECK_PATHS)
    joined = " ".join(metadata["self_check_scope"]["does_not_cover"])
    assert "transcript directory" in joined and "assume-unchanged" in joined
    assert "2026-07-06" in metadata["self_check_scope"]["deferred_by"]


# --------------------------------------------------------------------------
# verify: landing verification
# --------------------------------------------------------------------------


def test_verify_accepts_a_landed_candidate(world: dict[str, Any], tmp_path: Path) -> None:
    candidate = _candidate(evidence=[{"path": str(world["card_path"]), "quote": QUOTE}])
    report = _verify(world, [candidate], tmp_path)
    assert report["metadata"]["accepted_count"] == 1
    assert report["metadata"]["dropped_count"] == 0
    assert report["metadata"]["drop_reasons"] == []
    accepted = report["candidates"][0]
    assert accepted["kind"] == "ADD" and accepted["object_layer"] == lens.LAYER_FILE
    assert accepted["evidence"][0]["locator"] == f"{world['card_path']}:6"
    assert accepted["item_id"] and len(accepted["item_id"]) == 16
    assert report["metadata"]["accepted_by_kind"] == {"ADD": 1, "CORRECT": 0}
    assert report["metadata"]["accepted_by_object_layer"][lens.LAYER_FILE] == 1


def test_verify_matches_a_transcript_quote_in_the_raw_line(world: dict[str, Any], tmp_path: Path) -> None:
    candidate = _candidate(evidence=[{"path": str(world["fresh"]), "quote": QUOTE}])
    report = _verify(world, [candidate], tmp_path)
    assert report["metadata"]["accepted_count"] == 1
    assert report["candidates"][0]["evidence"][0]["locator"] == f"{world['fresh']}:1"


def test_verify_drops_a_quote_split_across_transcript_lines(world: dict[str, Any], tmp_path: Path) -> None:
    spanning = _write(world["transcripts"] / "session-c.jsonl", "first half of the sentence\nsecond half\n")
    candidate = _candidate(evidence=[{"path": str(spanning),
                                      "quote": "first half of the sentence\nsecond half"}])
    report = _verify(world, [candidate], tmp_path)
    assert report["metadata"]["dropped_count"] == 1
    assert "does not appear verbatim" in report["metadata"]["drop_reasons"][0]["reason"]


def test_verify_drops_a_missing_path_a_wrong_quote_and_a_short_quote(world: dict[str, Any],
                                                                    tmp_path: Path) -> None:
    submitted = [
        _candidate(claim="cites a file that is not there",
                   evidence=[{"path": str(world["memory_dir"] / "never-written.md"), "quote": QUOTE}]),
        _candidate(claim="cites a real file with an invented quote",
                   evidence=[{"path": str(world["card_path"]),
                              "quote": "a sentence the operator never typed anywhere"}]),
        _candidate(claim="cites a quote too short to locate anything",
                   evidence=[{"path": str(world["card_path"]), "quote": "argv"}]),
        _candidate(claim="lands cleanly", evidence=[{"path": str(world["card_path"]), "quote": QUOTE}]),
    ]
    report = _verify(world, submitted, tmp_path)
    assert report["metadata"]["accepted_count"] == 1
    assert report["metadata"]["dropped_count"] == 3
    reasons = {item["index"]: item["reason"] for item in report["metadata"]["drop_reasons"]}
    assert set(reasons) == {0, 1, 2}
    assert "does not exist" in reasons[0]
    assert "does not appear verbatim" in reasons[1]
    assert f"shorter than {lens.MIN_QUOTE_CHARS}" in reasons[2]
    assert [item["claim"] for item in report["dropped"]] == [item["claim"] for item in submitted[:3]]
    assert report["candidates"][0]["claim"] == "lands cleanly"


def test_verify_drops_a_whitespace_only_quote(world: dict[str, Any], tmp_path: Path) -> None:
    """Twenty spaces cleared the raw-length floor and then matched almost anything.

    The floor exists so that a locator means something.  Measured on the raw
    string it did not: a quote of ``MIN_QUOTE_CHARS`` spaces passed it and then
    found a verbatim match in the indentation of any sufficiently indented line,
    so a candidate with no evidence at all could hand itself a ``path:line`` and
    land.  The floor now counts stripped characters.
    """
    indented = _write(world["memory_dir"] / "deeply-indented.md",
                      f"---\nname: deeply-indented\n---\n{' ' * 40}nested value\n")
    submitted = [
        _candidate(claim="props itself up on source indentation",
                   evidence=[{"path": str(indented), "quote": " " * lens.MIN_QUOTE_CHARS}]),
        _candidate(claim="pads a genuinely short quote out to the floor",
                   evidence=[{"path": str(indented), "quote": f"{' ' * 30}nested"}]),
    ]
    report = _verify(world, submitted, tmp_path)
    assert report["metadata"]["accepted_count"] == 0
    reasons = {item["index"]: item["reason"] for item in report["metadata"]["drop_reasons"]}
    assert "blank" in reasons[0] and f"shorter than {lens.MIN_QUOTE_CHARS}" in reasons[0]
    assert f"shorter than {lens.MIN_QUOTE_CHARS}" in reasons[1] and "whitespace is stripped" in reasons[1]


def test_verify_still_matches_a_padded_quote_byte_for_byte(world: dict[str, Any], tmp_path: Path) -> None:
    """The floor counts stripped characters; the match stays verbatim.

    Trimming the string a seat submitted before matching it would land a quote
    the seat never made, so the two operations stay separate: padding that a real
    line carries is matched, padding that it does not carry is a miss.
    """
    padded = f"   {QUOTE}   "
    carrier = _write(world["memory_dir"] / "padded.md", f"---\nname: padded\n---\n{padded}\n")
    submitted = [
        _candidate(claim="the padding is really in the line", evidence=[{"path": str(carrier),
                                                                        "quote": padded}]),
        _candidate(claim="the padding is not in this line", evidence=[{"path": str(world["card_path"]),
                                                                       "quote": padded}]),
    ]
    report = _verify(world, submitted, tmp_path)
    assert report["metadata"]["accepted_count"] == 1
    assert report["candidates"][0]["evidence"][0]["quote"] == padded, "the quote is stored unmodified"
    assert report["candidates"][0]["evidence"][0]["locator"] == f"{carrier}:4"
    assert "does not appear verbatim" in report["metadata"]["drop_reasons"][0]["reason"]


def test_verify_drops_a_candidate_holding_an_unpaired_surrogate(world: dict[str, Any],
                                                                tmp_path: Path) -> None:
    """``"\\ud800"`` is valid JSON, is a valid Python string, and is not UTF-8.

    It used to travel the whole way through verification and detonate at the
    report write with an unhandled ``UnicodeEncodeError``, taking the previous
    report with it.  Now it is what it always was — one bad candidate — and the
    surrounding run finishes.
    """
    evidence = json.dumps([{"path": str(world["card_path"]), "quote": QUOTE}])
    lone = "\\ud800"
    submitted = ("[" + ", ".join(
        f'{{"kind": "ADD", "object_layer": "file_memory", "claim": {claim}, '
        f'"evidence": {ev}, "proposed_action": {action}}}'
        for claim, ev, action in (
            (f'"a claim ending in {lone}"', evidence, '"write a card"'),
            ('"a clean claim"', evidence, f'"an action ending in {lone}"'),
            ('"a clean claim"', f'[{{"path": {json.dumps(str(world["card_path"]))}, '
                                f'"quote": "{QUOTE}{lone}"}}]', '"write a card"'),
            ('"a clean claim"', evidence, '"write a card"'),
        )) + "]")

    report = _verify(world, submitted, tmp_path)

    assert report["metadata"]["accepted_count"] == 1
    assert report["metadata"]["dropped_count"] == 3
    reasons = {item["index"]: item["reason"] for item in report["metadata"]["drop_reasons"]}
    assert set(reasons) == {0, 1, 2}
    assert all("unpaired surrogate" in reason for reason in reasons.values())
    assert "candidate.claim" in reasons[0]
    assert "candidate.proposed_action" in reasons[1]
    assert "candidate.evidence[0].quote" in reasons[2]
    assert report["dropped"][0]["claim"] is None, "the drop record must not carry the surrogate back out"
    json.dumps(report, ensure_ascii=False).encode("utf-8")


def test_verify_drops_evidence_outside_the_allowed_roots(world: dict[str, Any], tmp_path: Path) -> None:
    outsider = _write(tmp_path / "elsewhere" / "notes.md", f"{QUOTE}\n")
    escape = _candidate(evidence=[{"path": f"../../{outsider.name}", "quote": QUOTE}])
    report = _verify(world, [_candidate(evidence=[{"path": str(outsider), "quote": QUOTE}]), escape],
                     tmp_path)
    assert report["metadata"]["accepted_count"] == 0
    assert all("outside the allowed roots" in item["reason"] or "does not exist" in item["reason"]
               for item in report["metadata"]["drop_reasons"])
    assert report["metadata"]["landing_verification"]["allowed_roots"] == [
        str(world["repo"].resolve()), str(world["transcripts"].resolve()),
        str(world["memory_dir"].resolve())]


def test_verify_checks_a_correction_target_in_the_layer_it_claims(world: dict[str, Any],
                                                                  tmp_path: Path) -> None:
    evidence = [{"path": str(world["card_path"]), "quote": QUOTE}]
    submitted = [
        _candidate(kind="CORRECT", object_layer=lens.LAYER_FILE, claim="file card is stale",
                   object_id="process-probe-argv-self-match-pitfall", evidence=evidence),
        _candidate(kind="CORRECT", object_layer=lens.LAYER_VNEXT, claim="vnext card is stale",
                   object_id="process-probe-argv-self-match", evidence=evidence),
        _candidate(kind="CORRECT", object_layer=lens.LAYER_ARCHIVE, claim="archive entry is stale",
                   object_id="frozen-archive-map-20260803", evidence=evidence),
        _candidate(kind="CORRECT", object_layer=lens.LAYER_VNEXT, claim="right name, wrong layer",
                   object_id="process-probe-argv-self-match-pitfall", evidence=evidence),
        _candidate(kind="CORRECT", object_layer=lens.LAYER_FILE, claim="a card nobody ever wrote",
                   object_id="hallucinated-card", evidence=evidence),
        _candidate(kind="CORRECT", object_layer=lens.LAYER_FILE, claim="no target named at all",
                   evidence=evidence),
    ]
    report = _verify(world, submitted, tmp_path)
    assert report["metadata"]["accepted_count"] == 3
    assert report["metadata"]["accepted_by_kind"] == {"ADD": 0, "CORRECT": 3}
    reasons = {item["index"]: item["reason"] for item in report["metadata"]["drop_reasons"]}
    assert set(reasons) == {3, 4, 5}
    assert "does not exist in layer vnext" in reasons[3]
    assert "does not exist in layer file_memory" in reasons[4]
    assert "must name the object it corrects" in reasons[5]


def test_verify_drops_malformed_candidates(world: dict[str, Any], tmp_path: Path) -> None:
    evidence = [{"path": str(world["card_path"]), "quote": QUOTE}]
    submitted: list[Any] = [
        _candidate(kind="ARCHIVE", evidence=evidence),
        _candidate(object_layer="mem0", evidence=evidence),
        {key: value for key, value in _candidate(evidence=evidence).items() if key != "object_layer"},
        _candidate(claim="   ", evidence=evidence),
        _candidate(proposed_action="x" * (lens.MAX_FIELD_CHARS + 1), evidence=evidence),
        _candidate(evidence=[]),
        _candidate(evidence=["a bare string, not an object"]),
        _candidate(evidence=[{"path": str(world["card_path"])}]),
        "not an object at all",
    ]
    report = _verify(world, submitted, tmp_path)
    assert report["metadata"]["accepted_count"] == 0
    assert report["metadata"]["dropped_count"] == len(submitted)
    reasons = {item["index"]: item["reason"] for item in report["metadata"]["drop_reasons"]}
    assert "kind must be one of" in reasons[0]
    assert "object_layer must be one of" in reasons[1] and "object_layer must be one of" in reasons[2]
    assert "claim is missing" in reasons[3]
    assert f"longer than {lens.MAX_FIELD_CHARS}" in reasons[4]
    assert "evidence must be a non-empty list" in reasons[5]
    assert "evidence entry is not a JSON object" in reasons[6]
    assert "quote is not a string" in reasons[7]
    assert "not a JSON object" in reasons[8]


def test_verify_says_plainly_that_no_clean_tree_check_ran(world: dict[str, Any],
                                                          tmp_path: Path) -> None:
    """The scope block travels with both reports, so verify must not imply a check it skipped."""
    candidate = _candidate(evidence=[{"path": str(world["card_path"]), "quote": QUOTE}])
    metadata = _verify(world, [candidate], tmp_path)["metadata"]
    assert metadata["preconditions"]["in_repository_self_check"] == "not run"
    assert "assemble" in metadata["preconditions"]["reason"]
    assert metadata["self_check_scope"]["clean_means"]

    _write(world["cards"] / "written-after-the-fact.md", "---\nid: written-after-the-fact\n---\nbody\n")
    dirty = _verify(world, [candidate], tmp_path)["metadata"]
    assert dirty["accepted_count"] == 1, "verify does not gate on the in-repository dirty state"


def test_verify_records_but_does_not_trust_unknown_fields(world: dict[str, Any], tmp_path: Path) -> None:
    candidate = _candidate(evidence=[{"path": str(world["card_path"]), "quote": QUOTE}],
                           confidence="certain", apply_command="python cc_memory/mem.py add-entry")
    report = _verify(world, [candidate], tmp_path)
    accepted = report["candidates"][0]
    assert accepted["unvalidated_field_names"] == ["apply_command", "confidence"]
    assert "mem.py add-entry" not in json.dumps(accepted, ensure_ascii=False)


def test_verify_accepts_an_object_wrapper_and_reports_its_source(world: dict[str, Any],
                                                                 tmp_path: Path) -> None:
    candidate = _candidate(evidence=[{"path": str(world["card_path"]), "quote": QUOTE}])
    report = _verify(world, {"lens": "gap", "candidates": [candidate]}, tmp_path)
    assert report["metadata"]["accepted_count"] == 1
    source = report["metadata"]["source_candidates"]
    assert source["submitted_count"] == 1 and len(source["sha256"]) == 64
    assert report["metadata"]["applies_nothing"].startswith("Advisory only")


# --------------------------------------------------------------------------
# verify: untrusted input handling
# --------------------------------------------------------------------------


def test_verify_rejects_duplicate_keys(world: dict[str, Any], tmp_path: Path) -> None:
    raw = ('[{"kind": "ADD", "kind": "CORRECT", "object_layer": "file_memory", "claim": "c", '
           '"evidence": [], "proposed_action": "a"}]')
    with pytest.raises(lens.GapLensError) as caught:
        _verify(world, raw, tmp_path)
    assert "duplicate JSON key" in str(caught.value)


def test_verify_rejects_a_document_that_is_neither_list_nor_wrapper(world: dict[str, Any],
                                                                    tmp_path: Path) -> None:
    with pytest.raises(lens.GapLensError) as caught:
        _verify(world, '{"candidates": {"kind": "ADD"}}', tmp_path)
    assert "must be a list" in str(caught.value)


def test_verify_rejects_an_oversized_file(world: dict[str, Any], tmp_path: Path) -> None:
    path = tmp_path / "huge.json"
    path.write_bytes(b"[" + b" " * (lens.MAX_CANDIDATE_BYTES + 1) + b"]")
    with pytest.raises(lens.GapLensError) as caught:
        lens.build_candidate_report(path, root=world["repo"], file_memory_dir=world["memory_dir"],
                                    transcript_dir=world["transcripts"])
    assert "larger than" in str(caught.value)


def test_verify_rejects_too_many_candidates(world: dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(lens.GapLensError) as caught:
        _verify(world, [{"kind": "ADD"}] * (lens.MAX_CANDIDATES + 1), tmp_path)
    assert "more than" in str(caught.value)


def test_verify_rejects_a_missing_file(world: dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(lens.GapLensError):
        lens.build_candidate_report(tmp_path / "absent.json", root=world["repo"],
                                    file_memory_dir=world["memory_dir"],
                                    transcript_dir=world["transcripts"])


# --------------------------------------------------------------------------
# the write primitive and the command line
# --------------------------------------------------------------------------


@pytest.mark.parametrize("relpath", ["", "report.json", "../escape.json", "/etc/report.json",
                                     "prune/report.json", ".prune", ".prune/../../out.json",
                                     ".prune\\report.json"])
def test_report_destination_refuses_anything_outside_prune(tmp_path: Path, relpath: str) -> None:
    with pytest.raises(lens.GapLensError):
        lens.resolve_report_destination(tmp_path, relpath)


def test_report_destination_refuses_a_symlinked_component(tmp_path: Path) -> None:
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / ".prune").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(lens.GapLensError) as caught:
        lens.resolve_report_destination(tmp_path, lens.EVIDENCE_RELPATH)
    assert "symlink" in str(caught.value)


def test_write_report_serialises_before_it_truncates(tmp_path: Path) -> None:
    """``O_TRUNC`` empties the destination at open, so encoding has to come first.

    Encoding is the one step that can fail on the report's own content.  Behind
    the open it destroyed the previous report on its way out; in front of it the
    previous report is untouched and the caller sees a ``GapLensError``.
    """
    destination = _write(tmp_path / lens.EVIDENCE_RELPATH, '{"previous": "report"}\n')
    before = destination.read_bytes()

    with pytest.raises(lens.GapLensError) as caught:
        lens.write_report(tmp_path, {"claim": "\ud800"}, relpath=lens.EVIDENCE_RELPATH)

    assert "not encodable as UTF-8" in str(caught.value)
    assert destination.read_bytes() == before, "the previous report survived the failed write"

    lens.write_report(tmp_path, {"claim": "a report that encodes"}, relpath=lens.EVIDENCE_RELPATH)
    assert json.loads(destination.read_text(encoding="utf-8")) == {"claim": "a report that encodes"}


def test_cli_survives_a_surrogate_candidate_without_losing_the_previous_report(
        world: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """End to end: the crash that truncated a report to zero bytes is now a drop."""
    previous = _write(world["repo"] / lens.CANDIDATES_RELPATH, '{"previous": "report"}\n')
    candidates = tmp_path / "seat_output.json"
    candidates.write_text('[{"kind": "ADD", "object_layer": "file_memory", "claim": "a claim", '
                          f'"evidence": [{{"path": {json.dumps(str(world["card_path"]))}, '
                          f'"quote": "{QUOTE}"}}], "proposed_action": "\\ud800"}}]', encoding="utf-8")

    code = lens.main(["--repo-root", str(world["repo"]), "--file-memory-dir", str(world["memory_dir"]),
                      "--transcript-dir", str(world["transcripts"]), "verify", str(candidates)])

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["accepted"] == 0 and summary["dropped"] == 1
    written = json.loads(previous.read_text(encoding="utf-8"))
    assert written["schema_version"] == lens.CANDIDATES_SCHEMA_VERSION
    assert "unpaired surrogate" in written["metadata"]["drop_reasons"][0]["reason"]


def test_cli_writes_both_reports_under_prune(world: dict[str, Any], tmp_path: Path,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    common = ["--repo-root", str(world["repo"]), "--file-memory-dir", str(world["memory_dir"]),
              "--transcript-dir", str(world["transcripts"])]
    assert lens.main([*common, "assemble"]) == 0
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["status"] == "EVIDENCE_WRITTEN"
    written = world["repo"] / lens.EVIDENCE_RELPATH
    assert written.is_file()
    assert json.loads(written.read_text())["schema_version"] == lens.EVIDENCE_SCHEMA_VERSION

    candidates = tmp_path / "seat_output.json"
    candidates.write_text(json.dumps([_candidate(evidence=[{"path": str(world["card_path"]),
                                                            "quote": QUOTE}])]), encoding="utf-8")
    assert lens.main([*common, "verify", str(candidates)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "CANDIDATES_VERIFIED" and summary["accepted"] == 1
    assert (world["repo"] / lens.CANDIDATES_RELPATH).is_file()


def test_cli_refuses_an_output_outside_prune(world: dict[str, Any],
                                             capsys: pytest.CaptureFixture[str]) -> None:
    code = lens.main(["--repo-root", str(world["repo"]), "--file-memory-dir", str(world["memory_dir"]),
                      "--transcript-dir", str(world["transcripts"]), "assemble", "--output", "out.json"])
    assert code == 1
    assert "memory gap lens failed" in capsys.readouterr().err
    assert not (world["repo"] / "out.json").exists()


def test_verify_leaves_every_memory_object_untouched(world: dict[str, Any], tmp_path: Path) -> None:
    """The whole point of an advisory tool: running it changes nothing it read."""
    watched = sorted(list(world["memory_dir"].rglob("*")) + list(world["cards"].rglob("*"))
                     + [world["archive_db"]])
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in watched if path.is_file()}

    candidates = tmp_path / "seat_output.json"
    candidates.write_text(json.dumps([_candidate(evidence=[{"path": str(world["card_path"]),
                                                            "quote": QUOTE}])]), encoding="utf-8")
    assert lens.main(["--repo-root", str(world["repo"]), "--file-memory-dir", str(world["memory_dir"]),
                      "--transcript-dir", str(world["transcripts"]), "verify", str(candidates)]) == 0

    after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in watched if path.is_file()}
    assert after == before
    written = {path.relative_to(world["repo"]) for path in world["repo"].rglob("*") if path.is_file()}
    assert all(str(path).startswith(".prune/") or str(path).startswith(".git/")
               or str(path) in {"cc_memory/memory.db"} or str(path).startswith("cc_memory_vnext/")
               for path in written)


# --------------------------------------------------------------------------
# the structural pin: no apply path
# --------------------------------------------------------------------------


def _module_tree() -> ast.Module:
    return ast.parse(Path(lens.__file__).read_text(encoding="utf-8"))


def _called_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                names.append(child.func.attr)
            elif isinstance(child.func, ast.Name):
                names.append(child.func.id)
    return names


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name)


def _calls_by_owner(tree: ast.Module) -> collections.Counter[tuple[str, str]]:
    """Every call in the module as ``(leaf name, enclosing function) -> count``.

    The leaf name is what a deny-list or an allow-list can actually see: an AST
    cannot tell ``os.open`` from ``socket.open`` without resolving imports, so
    the enclosing function is carried as a second key.  That is what stops a
    sanctioned call from being quietly relocated: ``os.open`` is allowed *inside
    write_report*, not in the module at large.
    """
    counted: collections.Counter[tuple[str, str]] = collections.Counter()

    def descend(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else owner
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    counted[(child.func.attr, owner)] += 1
                elif isinstance(child.func, ast.Name):
                    counted[(child.func.id, owner)] += 1
            descend(child, inner)

    descend(tree, "<module>")
    return counted


# Every call name that could write to the filesystem, start a process or change a
# database, gathered by family rather than by what this module happens to use.
# Membership here does not accuse a call of anything: it only means the call must
# appear in _SANCTIONED_SENSITIVE_CALLS to be allowed to exist.
_SENSITIVE_CALL_NAMES = frozenset({
    # os: file and directory mutation
    "open", "fdopen", "close", "closerange", "write", "writev", "pwrite", "writelines", "truncate",
    "ftruncate", "remove", "unlink", "rename", "renames", "replace", "rmdir", "removedirs", "mkdir",
    "makedirs", "link", "symlink", "chmod", "lchmod", "chown", "lchown", "utime", "mknod", "mkfifo",
    "umask", "chdir", "chroot", "sendfile", "copy_file_range", "dup", "dup2", "pipe",
    # os: process control and code execution
    "system", "popen", "fork", "forkpty", "kill", "killpg", "abort", "startfile", "posix_spawn",
    "execv", "execve", "execvp", "execvpe", "execl", "execle", "execlp", "spawnv", "spawnl",
    "exec", "eval", "__import__",
    # pathlib: the write half of Path
    "touch", "write_text", "write_bytes", "symlink_to", "hardlink_to",
    # shutil
    "copy", "copy2", "copyfile", "copyfileobj", "copymode", "copystat", "copytree", "move", "rmtree",
    "make_archive", "unpack_archive",
    # subprocess
    "run", "call", "check_call", "check_output", "Popen", "communicate", "getoutput",
    "getstatusoutput",
    # tempfile
    "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile", "TemporaryDirectory", "mkstemp",
    "mkdtemp", "mktemp",
    # sqlite3
    "connect", "cursor", "execute", "executemany", "executescript", "commit", "rollback", "backup",
    "create_function", "set_trace_callback",
})

# The closed list.  Anything sensitive that is not exactly here fails the test,
# including a sanctioned call that moved to another function.
_SANCTIONED_SENSITIVE_CALLS = {
    ("connect", "archive_snapshot"): 1,   # sqlite3.connect, mode=ro&immutable=1
    ("execute", "archive_snapshot"): 1,   # one select, pinned separately below
    ("close", "archive_snapshot"): 1,     # closing that connection
    ("run", "run_self_check"): 1,         # subprocess.run, git status, pinned separately below
    ("mkdir", "write_report"): 1,         # .prune/ itself
    ("open", "write_report"): 1,          # os.open of the one report destination
    ("fdopen", "write_report"): 1,        # wrapping that descriptor
    ("write", "write_report"): 1,         # the one write in the module
}


def test_no_apply_path() -> None:
    """No mutating call exists outside the sanctioned report write — by allow-list.

    A promise in a docstring is not a structural guarantee, and neither is a
    deny-list: the earlier version of this test named the writing verbs it could
    think of, and a mutation adding ``path.touch()`` in a fresh function passed
    all four structural tests.  A deny-list can only catch what someone already
    thought of, which is the wrong shape for a pin that has to survive future
    edits by people who have not read it.

    So the direction is inverted.  Every call in the module is classified by leaf
    name; every call landing in the filesystem, process or database families must
    match ``_SANCTIONED_SENSITIVE_CALLS`` exactly, count and enclosing function
    included.  A new sensitive call fails by not being listed, and a sanctioned
    one fails if it moves.
    """
    tree = _module_tree()
    observed = {key: count for key, count in _calls_by_owner(tree).items()
                if key[0] in _SENSITIVE_CALL_NAMES}
    assert observed == _SANCTIONED_SENSITIVE_CALLS

    assert "resolve_report_destination" in _called_names(_function(tree, "write_report"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "open", "the builtin open() is never used"


def test_the_allow_list_catches_a_writing_verb_nobody_blacklisted() -> None:
    """The mutation that got through the deny-list, run against the allow-list.

    Without this the allow-list is only asserted to pass on the code as written,
    which is exactly what the deny-list also did.  The probe is the one that
    escaped: a filesystem write, in a function of its own, using a verb
    (``Path.touch``) that no hand-written forbidden set had listed.
    """
    source = Path(lens.__file__).read_text(encoding="utf-8")
    mutant = ast.parse(source + "\n\ndef _latent_outside_prune_write(path: Path) -> None:\n"
                                "    path.touch()\n")
    observed = {key: count for key, count in _calls_by_owner(mutant).items()
                if key[0] in _SENSITIVE_CALL_NAMES}
    assert observed != _SANCTIONED_SENSITIVE_CALLS
    assert observed.get(("touch", "_latent_outside_prune_write")) == 1

    relocated = ast.parse(source.replace("def write_report(", "def _write_report_moved("))
    moved = {key: count for key, count in _calls_by_owner(relocated).items()
             if key[0] in _SENSITIVE_CALL_NAMES}
    assert moved != _SANCTIONED_SENSITIVE_CALLS, "a sanctioned call may not change owner unnoticed"


def test_every_report_path_constant_is_rooted_at_prune() -> None:
    """No module-level path constant can send a report anywhere but ``.prune/``."""
    tree = _module_tree()
    constants = [(target.id, node.value.value) for node in tree.body if isinstance(node, ast.Assign)
                 for target in node.targets if isinstance(target, ast.Name)
                 if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    prune_constants = [(name, value) for name, value in constants if ".prune" in value]
    assert len(prune_constants) >= 4
    for name, value in prune_constants:
        assert value.startswith(".prune"), f"{name} = {value!r}"
    assert lens.EVIDENCE_RELPATH.startswith(f"{lens.REPORT_DIR_RELPATH}/")
    assert lens.CANDIDATES_RELPATH.startswith(f"{lens.REPORT_DIR_RELPATH}/")


def test_the_only_database_traffic_is_a_select() -> None:
    tree = _module_tree()
    statements: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "execute":
            continue
        for argument in node.args:
            assert isinstance(argument, ast.Constant) and isinstance(argument.value, str)
            statements.append(argument.value)
    assert statements and all(text.lower().startswith("select ") for text in statements)
    assert "?mode=ro&immutable=1" in Path(lens.__file__).read_text(encoding="utf-8")


def test_the_only_subprocess_is_a_read_only_git_status() -> None:
    tree = _module_tree()
    callers = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
               and "run" in _called_names(node) and "subprocess" in ast.dump(node)]
    assert callers == ["run_self_check"]
    assert lens.SELF_CHECK_GIT_ARGV[0] == "git" and lens.SELF_CHECK_GIT_ARGV[1] == "status"


def test_the_module_declares_its_threat_model_and_boundaries() -> None:
    docstring = lens.__doc__ or ""
    assert "Threat model and known boundaries" in docstring
    assert "cooperative-operator" in docstring and "2026-07-06" in docstring
    assert "no apply path" in docstring
    assert lens.SELF_CHECK_SCOPE["does_not_cover"] and lens.THREAT_MODEL == "cooperative-operator"
