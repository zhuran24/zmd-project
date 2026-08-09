"""Behavioural tests for the prune-system memory adapter.

Every scenario is built inside a throwaway fixture — a small git repository for
the vnext half, a plain directory for the file-memory half, and hand-written
transcript records — so the tests state what the scanner does rather than what
this machine happens to contain.  Nothing here reads the real memory layers or
the real transcripts.

The ``said_card_unwritten`` cases reproduce the shape of the historical true
positive the flag exists for: a promise made on 2026-07-12, the card written on
2026-08-02, and four repeats of the pitfall in between.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devtools import memory_reference_scan as scan  # noqa: E402

CONTRACT_KEYS = {"item_id", "layer", "flag", "signals", "safety_lock", "confidence", "evidence"}

GIT_ENV_ARGS = (
    "-c", "user.name=memory scan fixture",
    "-c", "user.email=fixture@invalid",
    "-c", "commit.gpgsign=false",
    "-c", "core.hooksPath=/dev/null",
)


def _git(root: Path, *args: str, when: str | None = None) -> None:
    env = None
    if when is not None:
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", *GIT_ENV_ARGS, *args], cwd=str(root), check=True, capture_output=True, env=env)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _touched(path: Path, when: str) -> Path:
    moment = datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp()
    os.utime(path, (moment, moment))
    return path


def _file_card(
    directory: Path,
    name: str,
    *,
    body: str = "body",
    description: str = "",
    modified: str | None = None,
) -> Path:
    metadata = f"metadata:\n  modified: {modified}\n" if modified is not None else ""
    front = f"---\nname: {name}\ndescription: \"{description}\"\n{metadata}---\n"
    return _write(directory / f"{name}.md", front + body + "\n")


def _vnext_card(directory: Path, card_id: str, *, body: str = "body", title: str = "") -> Path:
    front = f"---\nid: {card_id}\nkind: reference\ntitle: {title or card_id}\n---\n"
    return _write(directory / f"{card_id}.md", front + body + "\n")


def _index(directory: Path, names: Sequence[str]) -> Path:
    lines = ["# Memory Index"]
    lines += [f"- [{name}]({name}.md) — one line about {name}" for name in names]
    return _write(directory / scan.INDEX_FILENAME, "\n".join(lines) + "\n")


def _ledger(path: Path, records: Sequence[tuple[str, Sequence[str]]]) -> Path:
    payload = "\n".join(
        json.dumps({"ts": ts, "injected": [{"id": card} for card in cards]}) for ts, cards in records
    )
    return _write(path, payload + "\n")


def _transcript(directory: Path, name: str, records: Sequence[tuple[str, str]]) -> Path:
    lines = [
        json.dumps(
            {
                "type": "assistant",
                "timestamp": ts,
                "sessionId": name,
                "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
            },
            ensure_ascii=False,
        )
        for ts, text in records
    ]
    return _write(directory / f"{name}.jsonl", "\n".join(lines) + "\n")


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    """A repository with vnext cards, plus the out-of-repository halves."""
    root = tmp_path / "repo"
    cards = root / scan.VNEXT_CARDS_RELPATH
    cards.mkdir(parents=True)
    _vnext_card(cards, "seed-card")
    _write(root / ".gitignore", "logs/\n")
    _git(root, "init", "-b", "main", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture", when="2026-01-01T00:00:00+00:00")

    memory = tmp_path / "memory"
    memory.mkdir()
    _file_card(memory, "alpha")
    _index(memory, ["alpha"])

    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    return {
        "root": root,
        "cards": cards,
        "memory": memory,
        "transcripts": transcripts,
        "ledger": root / "logs" / "activation.jsonl",
    }


def build(world: dict[str, Path], **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "root": world["root"],
        "file_memory_dir": world["memory"],
        "vnext_cards_dir": world["cards"],
        "transcript_dir": world["transcripts"],
        "activation_ledger": world["ledger"],
    }
    kwargs.update(overrides)
    return scan.build_report(**kwargs)


def flags(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(item["flag"], item["evidence"].get("card") or item["evidence"].get("target", "")) for item in items]


def commit_cards(world: dict[str, Path], *, when: str) -> None:
    _git(world["root"], "add", "-A")
    _git(world["root"], "commit", "-q", "-m", "cards", when=when)


# --------------------------------------------------------------------------
# index integrity
# --------------------------------------------------------------------------


def test_a_card_missing_from_the_index_is_a_candidate(world: dict[str, Path]) -> None:
    _file_card(world["memory"], "beta")
    report = build(world)
    assert flags(report["candidates"]) == [("orphan_card", "beta.md")]
    assert report["candidates"][0]["safety_lock"] == {"locked": False, "reasons": []}


def test_an_index_line_pointing_nowhere_is_a_candidate(world: dict[str, Path]) -> None:
    _index(world["memory"], ["alpha", "ghost"])
    report = build(world)
    assert flags(report["candidates"]) == [("dangling_index_entry", "ghost.md")]
    assert report["candidates"][0]["evidence"]["index_line"] == 3


def test_the_index_file_itself_is_never_reported_as_an_orphan(world: dict[str, Path]) -> None:
    report = build(world)
    assert report["metadata"]["flag_counts"]["orphan_card"] == 0
    assert report["metadata"]["sources"]["file_memory_card_count"] == 1


# --------------------------------------------------------------------------
# wikilinks
# --------------------------------------------------------------------------


def test_a_dangling_wikilink_is_reported_but_never_as_a_candidate(world: dict[str, Path]) -> None:
    _file_card(world["memory"], "beta", body="see [[nowhere-card]] for the rest")
    _index(world["memory"], ["alpha", "beta"])
    report = build(world)
    assert report["candidates"] == []
    assert flags(report["fyi"]) == [("dangling_wikilink", "beta.md")]
    assert report["fyi"][0]["safety_lock"]["locked"] is True
    assert report["fyi"][0]["evidence"]["target"] == "nowhere-card"


def test_a_wikilink_that_resolves_is_not_reported(world: dict[str, Path]) -> None:
    _file_card(world["memory"], "beta", body="see [[alpha]] for the rest")
    _index(world["memory"], ["alpha", "beta"])
    report = build(world)
    assert report["metadata"]["flag_counts"]["dangling_wikilink"] == 0


def test_a_link_from_one_layer_to_another_is_not_dangling(world: dict[str, Path]) -> None:
    """Cross-layer links are the normal shape, not a defect.

    Resolving a link only within the citing card's own layer reported 14
    healthy links as dangling on 2026-08-03 — every one of them a file-memory
    card pointing at a real vnext card — which left the flag with no signal
    value.  Both directions must resolve.
    """
    _vnext_card(world["cards"], "alpha")
    _file_card(world["memory"], "beta", body="see [[seed-card]] and [[alpha]]")
    _index(world["memory"], ["alpha", "beta"])
    commit_cards(world, when="2026-01-02T00:00:00+00:00")
    report = build(world)
    assert report["metadata"]["flag_counts"]["dangling_wikilink"] == 0


def test_a_link_to_an_archived_cc_memory_entry_is_not_dangling(world: dict[str, Path]) -> None:
    """The frozen archive is the third link target, read without a footprint."""
    database = world["root"] / scan.ARCHIVE_DB_RELPATH
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        connection.execute("create table entries (id text primary key)")
        connection.execute("create table facts (id text primary key)")
        connection.execute("insert into entries values ('archived-entry')")
        connection.execute("insert into facts values ('fact-archived')")
        connection.commit()
    finally:
        connection.close()
    _file_card(world["memory"], "beta", body="see [[archived-entry]] and [[fact-archived]]")
    _index(world["memory"], ["alpha", "beta"])
    commit_cards(world, when="2026-01-02T00:00:00+00:00")
    report = build(world)
    assert report["metadata"]["flag_counts"]["dangling_wikilink"] == 0
    assert report["metadata"]["sources"]["archive_read_status"] == "read"
    assert report["metadata"]["sources"]["archive_id_count"] == 2
    assert not list(database.parent.glob("memory.db-*")), "the read left sidecar files behind"


def test_a_link_to_nothing_at_all_still_dangles(world: dict[str, Path]) -> None:
    """Widening the search must not silence the flag it was widened for."""
    _vnext_card(world["cards"], "alpha")
    _file_card(world["memory"], "beta", body="see [[not-in-any-layer]]")
    _index(world["memory"], ["alpha", "beta"])
    commit_cards(world, when="2026-01-02T00:00:00+00:00")
    report = build(world)
    assert flags(report["fyi"]) == [("dangling_wikilink", "beta.md")]
    assert report["fyi"][0]["signals"] == ["wikilink_target_is_not_a_card_in_any_memory_layer"]


def test_an_absent_archive_degrades_instead_of_failing_the_scan(world: dict[str, Path]) -> None:
    """One missing layer must over-report, never crash or under-report."""
    assert not (world["root"] / scan.ARCHIVE_DB_RELPATH).exists()
    _file_card(world["memory"], "beta", body="see [[archived-entry]]")
    _index(world["memory"], ["alpha", "beta"])
    report = build(world)
    assert report["metadata"]["sources"]["archive_read_status"] == "absent"
    assert report["metadata"]["sources"]["archive_id_count"] == 0
    assert flags(report["fyi"]) == [("dangling_wikilink", "beta.md")]


# --------------------------------------------------------------------------
# never_read_card
# --------------------------------------------------------------------------


def test_a_card_the_ledger_never_injected_is_a_candidate(world: dict[str, Path]) -> None:
    _vnext_card(world["cards"], "unread-card")
    commit_cards(world, when="2026-03-01T00:00:00+00:00")
    _ledger(world["ledger"], [("2026-02-01T00:00:00", ["seed-card"])])
    report = build(world)
    assert flags(report["candidates"]) == [("never_read_card", "unread-card.md")]
    evidence = report["candidates"][0]["evidence"]
    assert evidence["ledger_covers_whole_card_lifetime"] is True


def test_a_card_older_than_the_ledger_can_only_reach_fyi(world: dict[str, Path]) -> None:
    """The ledger cannot speak about the time before it existed."""
    _vnext_card(world["cards"], "unread-card")
    commit_cards(world, when="2026-01-05T00:00:00+00:00")
    _ledger(world["ledger"], [("2026-02-01T00:00:00", ["seed-card"])])
    report = build(world)
    assert report["candidates"] == []
    assert flags(report["fyi"]) == [("never_read_card", "unread-card.md")]
    assert report["fyi"][0]["safety_lock"]["reasons"] == [
        "ledger_starts_after_the_card_did_so_earlier_reads_are_unknowable"
    ]


def test_an_injected_card_is_not_reported(world: dict[str, Path]) -> None:
    _vnext_card(world["cards"], "read-card")
    commit_cards(world, when="2026-03-01T00:00:00+00:00")
    _ledger(world["ledger"], [("2026-02-01T00:00:00", ["seed-card", "read-card"])])
    report = build(world)
    assert report["metadata"]["flag_counts"]["never_read_card"] == 0


def test_no_ledger_means_no_data_rather_than_a_guess(world: dict[str, Path]) -> None:
    _vnext_card(world["cards"], "unread-card")
    commit_cards(world, when="2026-03-01T00:00:00+00:00")
    report = build(world)
    assert report["metadata"]["flag_counts"]["never_read_card"] == 0
    vnext_status = report["metadata"]["never_read_card_status"][0]
    assert vnext_status["status"] == "no_data"
    assert vnext_status["missing_ledger"] == str(world["ledger"])


def test_the_file_memory_layer_always_declares_no_data(world: dict[str, Path]) -> None:
    """There is no read ledger for that layer, and no proxy is invented for it."""
    _ledger(world["ledger"], [("2026-02-01T00:00:00", ["seed-card"])])
    report = build(world)
    statuses = {entry["layer"]: entry for entry in report["metadata"]["never_read_card_status"]}
    assert statuses[scan.LAYER_VNEXT]["status"] == "computed"
    file_status = statuses[scan.LAYER_FILE]
    assert file_status["status"] == "no_data"
    assert file_status["missing_ledger"]
    assert file_status["what_would_close_it"]
    assert all(item["layer"] != scan.LAYER_FILE for item in report["candidates"] + report["fyi"]
               if item["flag"] == "never_read_card")


# --------------------------------------------------------------------------
# said_card_unwritten
# --------------------------------------------------------------------------

PROMISE = "又踩了 `pkill -f` 自杀坑(今晚第二次,这个坑值得进记忆)"
PROMISE_AT = "2026-07-12T23:20:58Z"


def test_every_said_card_pattern_has_exactly_one_aspect_classification() -> None:
    classes = (
        set(scan.COMMITMENT_ONLY_PATTERNS),
        set(scan.TENSE_NEUTRAL_PATTERNS),
        set(scan.PAST_ONLY_PATTERNS),
    )
    assert not (classes[0] & classes[1] or classes[0] & classes[2] or classes[1] & classes[2])
    assert set(scan.SAID_CARD_PATTERNS) == set().union(*classes)


def test_a_promise_nobody_kept_is_a_candidate(world: dict[str, Path]) -> None:
    """The 2026-07-12 case, reproduced: said then, written 21 days later.

    An unrelated card written the next day must not be mistaken for the one
    that was promised.
    """
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, PROMISE)])
    _touched(_file_card(world["memory"], "unrelated-disk-layout"), "2026-07-13T00:00:00+00:00")
    _touched(
        _file_card(
            world["memory"],
            "process-probe-argv-self-match-pitfall",
            description="pkill -f argv 自匹配导致探测进程自杀",
        ),
        "2026-08-02T00:00:00+00:00",
    )
    _index(
        world["memory"],
        ["alpha", "unrelated-disk-layout", "process-probe-argv-self-match-pitfall"],
    )
    report = build(world)
    said = [item for item in report["candidates"] if item["flag"] == "said_card_unwritten"]
    assert len(said) == 1
    assert said[0]["evidence"]["pattern"] == "值得进记忆"
    assert said[0]["evidence"]["said_at"].startswith("2026-07-12")
    assert said[0]["confidence"] == scan.CONFIDENCE_HEURISTIC
    assert report["metadata"]["said_card_unwritten_by_class"] == {
        "self_reference": 0,
        "past_tense_verified": 0,
        "candidate": 1,
    }
    assert report["said_card_unwritten"]["groups"]["candidate"][0]["evidence"][
        "quote"
    ] == PROMISE


@pytest.mark.parametrize(
    "text",
    [
        "分析报告列出 `补进记忆` 这个 guard。",
        "分析报告列出「补进记忆」这个 guard。",
        "分析报告列出『补进记忆』这个 guard。",
        '分析报告列出"补进记忆"这个 guard。',
        "分析报告列出“补进记忆”这个 guard。",
    ],
    ids=("backticks", "corner_quotes", "double_corner_quotes", "straight_quotes", "curly_quotes"),
)
def test_a_wrapped_trigger_is_a_suppressed_self_reference(
    world: dict[str, Path], text: str
) -> None:
    _transcript(world["transcripts"], "self-reference", [(PROMISE_AT, text)])
    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["metadata"]["suppressed_by_class"] == {
        "self_reference": 1,
        "past_tense_verified": 0,
    }
    grouped = report["said_card_unwritten"]["groups"]["self_reference"]
    assert len(grouped) == 1
    assert grouped[0]["evidence"]["quote"] == text


def test_markdown_emphasis_is_removed_before_use_mention_detection(
    world: dict[str, Path],
) -> None:
    text = "07-12 我写的原句正是「**又踩了**…这个坑值得**进记忆**」——两个 guard 词同时命中。"
    _transcript(world["transcripts"], "emphasized-mention", [(PROMISE_AT, text)])
    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["metadata"]["suppressed_by_class"]["self_reference"] == 1
    assert report["said_card_unwritten"]["groups"]["self_reference"][0]["evidence"][
        "quote"
    ] == text


def test_pattern_metadata_is_a_suppressed_self_reference(world: dict[str, Path]) -> None:
    text = "历史真阳仍在案：session.jsonl pattern=值得进记忆。"
    _transcript(world["transcripts"], "pattern-field", [(PROMISE_AT, text)])
    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["metadata"]["suppressed_by_class"]["self_reference"] == 1


def test_a_real_use_is_not_suppressed_by_an_unrelated_backticked_topic(
    world: dict[str, Path],
) -> None:
    _transcript(world["transcripts"], "pkill-use", [(PROMISE_AT, PROMISE)])
    report = build(world)
    assert report["metadata"]["said_card_unwritten_by_class"]["candidate"] == 1
    assert report["metadata"]["suppressed_by_class"]["self_reference"] == 0


def test_named_past_report_checks_card_existence_instead_of_time_window(
    world: dict[str, Path],
) -> None:
    slug = "rgignore-hides-live-research-code"
    said_at = "2026-08-05T23:19:16.499Z"
    _transcript(
        world["transcripts"],
        "past-named",
        [(said_at, f"`.rgignore` 这个坑已写进记忆卡，卡名是 `{slug}`。")],
    )
    _file_card(
        world["memory"],
        slug,
        description="rgignore hides live research code",
        modified="2026-08-05T23:18:38.315Z",
    )
    _index(world["memory"], ["alpha", slug])

    # A zero-day window makes the 38.184-second ordering bug observable: only
    # exact existence, not a temporal topic match, can verify this report.
    report = build(world, window_days=0)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["metadata"]["suppressed_by_class"]["past_tense_verified"] == 1
    past = report["said_card_unwritten"]["groups"]["past_tense_verified"]
    assert past[0]["evidence"]["verification"] == "named_card_exists_in_a_memory_namespace"
    assert past[0]["evidence"]["verified_card_slugs"] == [slug]


@pytest.mark.parametrize("missing", ["rgignore-card-that-is-absent", "foobar"])
def test_a_missing_named_past_card_is_not_fuzzily_washed_away(
    world: dict[str, Path], missing: str
) -> None:
    _transcript(
        world["transcripts"],
        "past-missing",
        [(PROMISE_AT, f"`.rgignore` 这个坑已写进记忆卡 `{missing}`。")],
    )
    _file_card(
        world["memory"],
        "rgignore-similar-but-different",
        description="rgignore 记忆卡",
        modified="2026-07-12T23:20:58Z",
    )
    _index(world["memory"], ["alpha", "rgignore-similar-but-different"])
    report = build(world)
    assert report["metadata"]["said_card_unwritten_by_class"]["candidate"] == 1
    said = next(item for item in report["candidates"] if item["flag"] == "said_card_unwritten")
    assert "named_card_slug_not_found_in_any_memory_namespace" in said["signals"]


def test_every_named_card_must_exist_before_a_past_report_is_verified(
    world: dict[str, Path],
) -> None:
    _transcript(
        world["transcripts"],
        "past-two-cards",
        [(PROMISE_AT, "已写进记忆卡 `existing-card` 和 `missing-card`。")],
    )
    _file_card(
        world["memory"],
        "existing-card",
        description="existing",
        modified="2026-07-12T23:20:58Z",
    )
    _index(world["memory"], ["alpha", "existing-card"])
    report = build(world)
    assert report["metadata"]["said_card_unwritten_by_class"]["candidate"] == 1
    assert report["metadata"]["suppressed_by_class"]["past_tense_verified"] == 0


def test_unnamed_past_report_uses_a_bidirectional_window(world: dict[str, Path]) -> None:
    text = "这些 CC-Session-Id 坐标我已存进记忆，下次会先反查。"
    _transcript(world["transcripts"], "past-unnamed", [(PROMISE_AT, text)])
    _file_card(
        world["memory"],
        "session-id-trailer-coordinates",
        description="CC-Session-Id trailer 坐标反查",
        modified="2026-07-11T23:20:58Z",
    )
    _index(world["memory"], ["alpha", "session-id-trailer-coordinates"])
    report = build(world, window_days=3)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    past = report["said_card_unwritten"]["groups"]["past_tense_verified"]
    assert past[0]["evidence"]["verification"] == "topic_matching_card_in_bidirectional_window"


def test_completed_ba_construction_is_past_tense(world: dict[str, Path]) -> None:
    text = "我把昨晚的 fan-out 判据写进记忆："
    _transcript(world["transcripts"], "past-ba", [(PROMISE_AT, text)])
    _file_card(
        world["memory"],
        "fan-out-model-tier-rule",
        description="fan-out 模型等级判据",
        modified="2026-07-12T22:20:58Z",
    )
    _index(world["memory"], ["alpha", "fan-out-model-tier-rule"])
    report = build(world)
    assert report["metadata"]["suppressed_by_class"]["past_tense_verified"] == 1
    assert report["said_card_unwritten"]["groups"]["past_tense_verified"][0]["evidence"][
        "tense"
    ] == scan.PROMISE_TENSE_PAST


@pytest.mark.parametrize(
    ("text", "expected_tense"),
    [
        ("我已经把重要判据写进记忆：", scan.PROMISE_TENSE_PAST),
        ("我已把第一梯队 family，完整写进记忆：", scan.PROMISE_TENSE_PAST),
        ("我已把决定性判据写进记忆：", scan.PROMISE_TENSE_PAST),
        ("问题已确认，这条存进记忆：", scan.PROMISE_TENSE_COMMITMENT),
        ("我会把这条重要判据写进记忆：", scan.PROMISE_TENSE_COMMITMENT),
        ("我已经决定把这条判据写进记忆：", scan.PROMISE_TENSE_COMMITMENT),
    ],
)
def test_tense_markers_do_not_leak_across_words_or_clauses(
    world: dict[str, Path], text: str, expected_tense: str
) -> None:
    _transcript(world["transcripts"], "tense-boundary", [(PROMISE_AT, text)])
    report = build(world)
    candidate = report["said_card_unwritten"]["groups"]["candidate"][0]
    assert candidate["evidence"]["tense"] == expected_tense


def test_present_action_phrase_remains_a_candidate(world: dict[str, Path]) -> None:
    text = "编排 fan-out 一律用低成本模型，这条存进记忆："
    _transcript(world["transcripts"], "present-use", [(PROMISE_AT, text)])
    report = build(world)
    assert report["metadata"]["said_card_unwritten_by_class"]["candidate"] == 1
    candidate = report["said_card_unwritten"]["groups"]["candidate"][0]
    assert candidate["evidence"]["tense"] == scan.PROMISE_TENSE_COMMITMENT


def test_backward_tolerance_does_not_accept_one_generic_topic_token(
    world: dict[str, Path],
) -> None:
    """The live 07-08 sentinel: an unrelated earlier verdict card is not fan-out memory."""
    text = (
        "编排 fan-out 一律用 sonnet/haiku 级，Fable 只留给顶级推理单点，"
        "比如最终 verdict 对抗性复核。这条存进记忆："
    )
    _transcript(world["transcripts"], "fan-out-use", [("2026-07-08T17:20:18.529Z", text)])
    _file_card(
        world["memory"],
        "p1-3-m5-phase1-verdict",
        description="phase 1 verdict",
        modified="2026-07-08T08:58:42Z",
    )
    _index(world["memory"], ["alpha", "p1-3-m5-phase1-verdict"])
    report = build(world)
    assert report["metadata"]["said_card_unwritten_by_class"]["candidate"] == 1


def test_backward_tolerance_accepts_one_distinctive_topic_token(
    world: dict[str, Path],
) -> None:
    _transcript(
        world["transcripts"],
        "distinctive-backward-topic",
        [(PROMISE_AT, "zqxunique 这个坑值得进记忆。")],
    )
    _file_card(
        world["memory"],
        "prior-topic-card",
        description="zqxunique",
        modified="2026-07-12T12:00:00Z",
    )
    _index(world["memory"], ["alpha", "prior-topic-card"])
    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0


def test_commitment_allows_one_day_write_then_announce_tolerance(
    world: dict[str, Path],
) -> None:
    _transcript(world["transcripts"], "write-then-announce", [(PROMISE_AT, PROMISE)])
    _file_card(
        world["memory"],
        "pkill-argv-self-match-pitfall",
        description="pkill -f 自杀坑",
        modified="2026-07-12T12:00:00Z",
    )
    _index(world["memory"], ["alpha", "pkill-argv-self-match-pitfall"])
    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["metadata"]["said_card_unwritten_by_class"]["candidate"] == 0
    assert scan.SAID_CARD_BACKWARD_TOLERANCE == timedelta(days=1)


def test_a_promise_kept_inside_the_window_is_not_reported(world: dict[str, Path]) -> None:
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, PROMISE)])
    _touched(
        _file_card(world["memory"], "pkill-argv-self-match-pitfall", description="pkill -f 自杀坑"),
        "2026-07-13T00:00:00+00:00",
    )
    _index(world["memory"], ["alpha", "pkill-argv-self-match-pitfall"])
    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["metadata"]["sources"]["promises_found"] == 1


def test_the_window_is_a_parameter_not_a_constant(world: dict[str, Path]) -> None:
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, PROMISE)])
    _touched(
        _file_card(world["memory"], "pkill-argv-self-match-pitfall", description="pkill -f 自杀坑"),
        "2026-07-20T00:00:00+00:00",
    )
    _index(world["memory"], ["alpha", "pkill-argv-self-match-pitfall"])
    assert build(world, window_days=3)["metadata"]["flag_counts"]["said_card_unwritten"] == 1
    assert build(world, window_days=30)["metadata"]["flag_counts"]["said_card_unwritten"] == 0


def test_a_card_written_before_the_promise_does_not_satisfy_it(world: dict[str, Path]) -> None:
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, PROMISE)])
    _touched(
        _file_card(world["memory"], "pkill-argv-self-match-pitfall", description="pkill -f 自杀坑"),
        "2026-07-01T00:00:00+00:00",
    )
    _index(world["memory"], ["alpha", "pkill-argv-self-match-pitfall"])
    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 1


def test_a_promise_made_only_in_a_thinking_block_is_not_a_promise(
    world: dict[str, Path],
) -> None:
    """Deliberation is not a commitment (2026-08-03 对抗审查 provenance)。

    Reasoning about whether a card is worth writing — and concluding no — used
    to produce a candidate accusing the session of breaking a promise it never
    made.  The narrowing is real and deliberate: a promise made only while
    thinking and then kept silently is now missed, which costs less than a false
    accusation from the file's one heuristic flag.
    """
    record = json.dumps(
        {
            "type": "assistant",
            "timestamp": PROMISE_AT,
            "sessionId": "session-b",
            "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": PROMISE}]},
        },
        ensure_ascii=False,
    )
    _write(world["transcripts"] / "session-b.jsonl", record + "\n")
    report = build(world)
    assert report["metadata"]["sources"]["promises_found"] == 0
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    stats = report["metadata"]["sources"]["promise_collection"]
    assert stats["records_matching_a_phrase"] == 1
    assert stats["excluded_not_assistant_reply_text"] == 1


def test_a_user_turn_quoting_the_phrase_is_not_a_promise(world: dict[str, Path]) -> None:
    """A quotation, and especially a negation, is not a commitment by anyone.

    A user turn carries ``message.content`` as a bare string — exactly the shape
    the old reader accepted without asking whose turn it was — so every time the
    operator wrote "别说『这个坑值得进记忆』就完了" the scanner logged a promise
    against the assistant.
    """
    record = json.dumps(
        {
            "type": "user",
            "timestamp": PROMISE_AT,
            "sessionId": "session-c",
            "message": {
                "role": "user",
                "content": f"我并没有说「{PROMISE}」,这是引用不是承诺。",
            },
        },
        ensure_ascii=False,
    )
    _write(world["transcripts"] / "session-c.jsonl", record + "\n")
    report = build(world)
    assert report["metadata"]["sources"]["promises_found"] == 0
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["metadata"]["sources"]["promise_collection"][
        "excluded_not_assistant_reply_text"
    ] == 1


def test_a_promise_about_this_systems_own_governance_files_is_excluded(
    world: dict[str, Path],
) -> None:
    """Snake-eating-its-tail: an eval fixture saying the phrase is not a promise.

    Same exclusion surface the error-recall hook uses (P2.2), same reason — the
    prune system reading its own design notes, card bodies, tests and eval
    fixtures generates promise-shaped text forever.
    """
    quoted = f"跑 cc_memory_vnext/eval/regression.jsonl 时样本里写着「{PROMISE}」,那是评测文本。"
    _transcript(world["transcripts"], "session-d", [(PROMISE_AT, quoted)])
    report = build(world)
    assert report["metadata"]["sources"]["promises_found"] == 0
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    stats = report["metadata"]["sources"]["promise_collection"]
    assert stats["excluded_governance_context"] == 1
    assert "cc_memory_vnext/eval" in stats["governance_exclusion_markers"]


def test_the_governance_markers_match_the_error_recall_hook(world: dict[str, Path]) -> None:
    """Two copies of one rule, kept honest by comparison rather than by import.

    The scanners share the rule and deliberately not the code; this test is what
    makes "deliberately" true instead of "accidentally divergent".

    Skipped rather than deleted while the memory layer is gone (2026-08-09,
    removed whole for a blank rebuild): the comparison is only meaningful with
    both copies present, and deleting it would retire the guarantee silently —
    whoever rebuilds the hook would have to remember this test used to exist.
    A skip says so on every run and revives itself the moment the file is back.
    """
    import importlib.util

    hook_path = (
        Path(__file__).resolve().parents[2]
        / "cc_memory_vnext"
        / "hooks"
        / "post_tool_error_recall.py"
    )
    if not hook_path.is_file():
        pytest.skip(
            "记忆层 hook 已于 2026-08-09 整体移除待重建；"
            f"{hook_path.name} 回来后这条双拷贝比对自动恢复"
        )
    spec = importlib.util.spec_from_file_location("recall_hook_under_test", hook_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["recall_hook_under_test"] = module
    try:
        spec.loader.exec_module(module)
        assert set(scan.GOVERNANCE_PATH_MARKERS) == set(module.GOVERNANCE_MARKERS)
    finally:
        sys.modules.pop("recall_hook_under_test", None)


def test_a_promise_in_a_subagent_transcript_is_read(world: dict[str, Path]) -> None:
    """Transcript enumeration is recursive (2026-08-03 对抗审查 nested-transcript)。

    The real directory has 59 files at the top level and 1100 in the tree:
    subagent and workflow sessions live in subdirectories, and a subagent that
    said it would write a card and did not is precisely what this flag is for.
    """
    nested = world["transcripts"] / "subagent" / "deeper"
    _transcript(nested, "session-nested", [(PROMISE_AT, PROMISE)])
    report = build(world)
    sources = report["metadata"]["sources"]
    assert sources["transcripts_scanned"] == 1
    assert sources["promise_collection"]["transcripts_in_subdirectories"] == 1
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 1
    said = [item for item in report["candidates"] if item["flag"] == "said_card_unwritten"]
    assert said[0]["evidence"]["transcript"] == "subagent/deeper/session-nested.jsonl"


def test_a_nested_and_a_top_level_transcript_say_the_same_thing(
    world: dict[str, Path],
) -> None:
    """The PoC's exact control: identical bytes, two locations, one answer."""
    _transcript(world["transcripts"], "top", [(PROMISE_AT, PROMISE)])
    top_only = build(world)["metadata"]["flag_counts"]["said_card_unwritten"]
    (world["transcripts"] / "top.jsonl").unlink()
    _transcript(world["transcripts"] / "workflow", "top", [(PROMISE_AT, PROMISE)])
    nested_only = build(world)["metadata"]["flag_counts"]["said_card_unwritten"]
    assert top_only == nested_only == 1


def test_a_transcript_with_no_promise_costs_nothing(world: dict[str, Path]) -> None:
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, "just an ordinary reply")])
    report = build(world)
    assert report["metadata"]["sources"]["promises_found"] == 0
    assert report["metadata"]["sources"]["transcripts_scanned"] == 1


def test_a_vnext_card_added_in_the_window_can_also_keep_a_promise(world: dict[str, Path]) -> None:
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, PROMISE)])
    _vnext_card(world["cards"], "pkill-argv-self-match-pitfall", title="pkill -f 自杀坑")
    commit_cards(world, when="2026-07-13T00:00:00+00:00")
    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0


def test_vnext_arrival_uses_earliest_git_add_after_readd_and_mtime_rewrite(
    world: dict[str, Path],
) -> None:
    """Git first-add survives both a later re-add and a metadata-only rewrite."""
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, PROMISE)])
    card = _vnext_card(world["cards"], "pkill-argv-self-match-pitfall", title="pkill -f 自杀坑")
    commit_cards(world, when="2026-07-13T00:00:00+00:00")

    relative = card.relative_to(world["root"]).as_posix()
    _git(world["root"], "rm", "-q", "--", relative)
    _git(world["root"], "commit", "-q", "-m", "remove card", when="2026-07-20T00:00:00+00:00")
    card = _vnext_card(world["cards"], "pkill-argv-self-match-pitfall", title="pkill -f 自杀坑")
    commit_cards(world, when="2026-08-02T00:00:00+00:00")
    _touched(card, "2099-01-01T00:00:00+00:00")

    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert scan.git_first_added_times(world["root"], world["cards"])[card.resolve()] == datetime(
        2026, 7, 13, tzinfo=timezone.utc,
    )
    assert report["arrival_source"] == {"git": 2, "frontmatter": 0, "mtime": 1}


def test_file_arrival_uses_frontmatter_modified_after_mtime_rewrite(world: dict[str, Path]) -> None:
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, PROMISE)])
    card = _file_card(
        world["memory"],
        "pkill-argv-self-match-pitfall",
        description="pkill -f 自杀坑",
        modified="2026-07-13T00:00:00Z",
    )
    _touched(card, "2099-01-01T00:00:00+00:00")
    _index(world["memory"], ["alpha", "pkill-argv-self-match-pitfall"])

    report = build(world)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["arrival_source"] == {"git": 1, "frontmatter": 1, "mtime": 1}


def test_both_primary_arrival_sources_fall_back_to_mtime_and_are_counted(tmp_path: Path) -> None:
    root = tmp_path / "not-a-repository"
    file_dir = root / "file-cards"
    vnext_dir = root / "vnext-cards"
    file_card = _touched(_file_card(file_dir, "file-fallback"), "2026-07-13T00:00:00+00:00")
    vnext_card = _touched(_vnext_card(vnext_dir, "vnext-fallback"), "2026-07-14T00:00:00+00:00")

    arrivals, sources = scan.card_arrivals(
        root,
        scan.load_cards(file_dir, layer=scan.LAYER_FILE, key_field="name"),
        scan.load_cards(vnext_dir, layer=scan.LAYER_VNEXT, key_field="id"),
    )

    assert {arrival.key: arrival.at for arrival in arrivals} == {
        file_card.stem: datetime(2026, 7, 13, tzinfo=timezone.utc),
        vnext_card.stem: datetime(2026, 7, 14, tzinfo=timezone.utc),
    }
    assert sources == {"git": 0, "frontmatter": 0, "mtime": 2}
    assert not (root / ".git").exists()


def test_vnext_path_without_an_add_record_falls_back_to_mtime(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main", "-q")
    _write(root / "README.md", "fixture\n")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "seed", when="2026-01-01T00:00:00+00:00")
    vnext_dir = root / scan.VNEXT_CARDS_RELPATH
    card = _touched(_vnext_card(vnext_dir, "no-add-record"), "2026-07-13T00:00:00+00:00")

    arrivals, sources = scan.card_arrivals(
        root,
        {},
        scan.load_cards(vnext_dir, layer=scan.LAYER_VNEXT, key_field="id"),
    )

    assert arrivals[0].at == datetime(2026, 7, 13, tzinfo=timezone.utc)
    assert arrivals[0].key == card.stem
    assert sources == {"git": 0, "frontmatter": 0, "mtime": 1}


def test_invalid_frontmatter_modified_falls_back_to_mtime_and_counts_source(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    file_dir = root / "file-cards"
    card = _touched(
        _file_card(file_dir, "bad-modified", modified="not-an-iso-timestamp"),
        "2026-07-13T00:00:00+00:00",
    )

    arrivals, sources = scan.card_arrivals(
        root,
        scan.load_cards(file_dir, layer=scan.LAYER_FILE, key_field="name"),
        {},
        git_arrivals={},
    )

    assert arrivals[0].at == datetime(2026, 7, 13, tzinfo=timezone.utc)
    assert arrivals[0].key == card.stem
    assert sources == {"git": 0, "frontmatter": 0, "mtime": 1}


def test_malformed_frontmatter_falls_back_to_mtime_instead_of_using_a_partial_parse(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    file_dir = root / "file-cards"
    card = _touched(
        _write(
            file_dir / "malformed.md",
            "---\nname: malformed\nmetadata:\n  modified: 2099-01-01T00:00:00Z\nbroken: [\n---\nbody\n",
        ),
        "2026-07-13T00:00:00+00:00",
    )

    arrivals, sources = scan.card_arrivals(
        root,
        scan.load_cards(file_dir, layer=scan.LAYER_FILE, key_field="name"),
        {},
        git_arrivals={},
    )

    assert arrivals[0].at == datetime(2026, 7, 13, tzinfo=timezone.utc)
    assert arrivals[0].key == card.stem
    assert sources == {"git": 0, "frontmatter": 0, "mtime": 1}


def test_git_unavailable_falls_back_to_mtime_without_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    vnext_dir = root / scan.VNEXT_CARDS_RELPATH
    card = _touched(_vnext_card(vnext_dir, "git-unavailable"), "2026-07-13T00:00:00+00:00")

    def unavailable(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError("git unavailable in fixture")

    monkeypatch.setattr(scan.subprocess, "run", unavailable)
    arrivals, sources = scan.card_arrivals(
        root,
        {},
        scan.load_cards(vnext_dir, layer=scan.LAYER_VNEXT, key_field="id"),
    )

    assert arrivals[0].at == datetime(2026, 7, 13, tzinfo=timezone.utc)
    assert arrivals[0].key == card.stem
    assert sources == {"git": 0, "frontmatter": 0, "mtime": 1}


def test_vnext_arrival_history_is_loaded_once_for_the_directory(
    world: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _vnext_card(world["cards"], "second-card")
    _vnext_card(world["cards"], "third-card")
    commit_cards(world, when="2026-07-13T00:00:00+00:00")
    real_run = subprocess.run
    calls: list[list[str]] = []

    def recording_run(args: list[str], *run_args: Any, **run_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return real_run(args, *run_args, **run_kwargs)

    monkeypatch.setattr(scan.subprocess, "run", recording_run)
    report = build(world)
    log_calls = [args for args in calls if "log" in args]

    assert len(log_calls) == 1
    assert "--diff-filter=A" in log_calls[0]
    assert "--name-only" in log_calls[0]
    assert log_calls[0][-1] == scan.VNEXT_CARDS_RELPATH
    assert report["arrival_source"]["git"] == 3


# --------------------------------------------------------------------------
# report shape, declarations and self check
# --------------------------------------------------------------------------


def test_every_item_carries_the_shared_prune_report_contract(world: dict[str, Path]) -> None:
    _file_card(world["memory"], "beta", body="see [[nowhere-card]]")
    report = build(world)
    items = report["candidates"] + report["fyi"]
    assert items
    for item in items:
        assert set(item) == CONTRACT_KEYS
        assert item["flag"] in scan.FLAGS
        assert item["signals"]
        assert set(item["safety_lock"]) == {"locked", "reasons"}


def test_the_report_publishes_its_threat_model_and_the_half_it_cannot_check(
    world: dict[str, Path],
) -> None:
    metadata = build(world)["metadata"]
    assert metadata["advisory"] is True
    assert metadata["threat_model"] == "cooperative-operator"
    scope = metadata["self_check_scope"]
    assert scope["covers"] and scope["does_not_cover"]
    assert any("outside the repository" in entry for entry in scope["does_not_cover"])
    assert metadata["preconditions"]["out_of_repository_objects_are_read_as_found"] is True


def test_the_module_docstring_carries_the_threat_model_boundary_section() -> None:
    doc = scan.__doc__ or ""
    assert "Threat model and known boundaries" in doc
    assert "cooperative-operator" in doc
    assert "half of what it scans lives outside" in doc


def test_the_declared_but_unclosed_boundaries_are_named_with_their_ruling() -> None:
    """The 乙组 declaration: four ways in, left open on the 2026-07-06 ruling.

    Each was confirmed by the 2026-08-03 adversarial review and each needs a
    filesystem somebody arranged on purpose, so it falls under the owner ruling
    that defers insider-only hardening to the release point.  Declaring them is
    the obligation; this test is what stops the declaration from quietly
    shrinking while the gaps stay.
    """
    doc = " ".join((scan.__doc__ or "").split())
    assert "Known boundaries, declared rather than closed" in doc
    assert "2026-07-06" in doc
    assert "deliberate-insider-hardening-deferred-to-release" in doc
    for boundary in (
        "a hardlinked report destination",
        "an ancestor directory swapped between the check and the write",
        "``assume-unchanged`` and ``skip-worktree`` marks",
        "cards changing between the self check and the read",
    ):
        assert boundary in doc, boundary
    # Every declared boundary also has to reach the report, so a reader who
    # never opens this file still sees the shape of the claim.
    published = scan.SELF_CHECK_SCOPE["does_not_cover"]
    for entry in (
        "assume-unchanged and skip-worktree marks, which switch every dirty check off",
        "a card changing between the self check and the read",
        "a hardlinked report destination",
        "an ancestor directory swapped between the check and the write",
    ):
        assert entry in published, entry


def test_an_ignored_card_file_refuses_the_report(world: dict[str, Path]) -> None:
    """The closed half of ``hidden-dirty-card-claim``.

    The card loader reads ``*.md`` off the filesystem, so an ignored card is
    read like any other; git's default status view does not mention it.  The
    combination let uncommitted bytes shape the findings under an explicit
    ``in_repository_cards_clean: true``.
    """
    _write(world["root"] / ".gitignore", "logs/\ncc_memory_vnext/cards/hidden-*.md\n")
    _git(world["root"], "add", "-A")
    _git(world["root"], "commit", "-q", "-m", "ignore hidden cards")
    _vnext_card(world["cards"], "hidden-ignored", body="see [[nowhere-card]]")
    assert subprocess.run(
        ["git", *GIT_ENV_ARGS, "status", "--porcelain"],
        cwd=str(world["root"]), capture_output=True, text=True, check=True,
    ).stdout.strip() == "", "前提:普通 git status 看不见它,否则这条测的不是这个洞"
    with pytest.raises(scan.SelfCheckRefusal):
        build(world)


def test_an_untracked_card_file_refuses_the_report(world: dict[str, Path]) -> None:
    """Same command, the other half: ``--untracked-files=all``."""
    _vnext_card(world["cards"], "untracked-card")
    with pytest.raises(scan.SelfCheckRefusal):
        build(world)


def test_the_self_check_publishes_the_git_command_it_trusted(
    world: dict[str, Path],
) -> None:
    preconditions = build(world)["metadata"]["preconditions"]
    assert preconditions["verified_by"] == scan.SELF_CHECK_GIT_COMMAND
    assert "--ignored" in preconditions["verified_by"]
    assert "--untracked-files=all" in preconditions["verified_by"]


def test_an_uncommitted_vnext_card_refuses_the_report(world: dict[str, Path]) -> None:
    _vnext_card(world["cards"], "uncommitted-card")
    with pytest.raises(scan.SelfCheckRefusal):
        build(world)


def test_a_missing_file_memory_directory_fails_closed(world: dict[str, Path], tmp_path: Path) -> None:
    with pytest.raises(scan.MemoryScanError):
        build(world, file_memory_dir=tmp_path / "gone")


def test_findings_are_ordered_deterministically(world: dict[str, Path]) -> None:
    _file_card(world["memory"], "beta", body="see [[nowhere-card]]")
    _file_card(world["memory"], "gamma", body="see [[nowhere-card]]")
    first = build(world)
    second = build(world)
    assert [item["item_id"] for item in first["fyi"]] == [item["item_id"] for item in second["fyi"]]
    assert [item["evidence"]["card"] for item in first["fyi"]] == ["beta.md", "gamma.md"]


# --------------------------------------------------------------------------
# the write primitive
# --------------------------------------------------------------------------


def test_a_report_target_outside_the_prune_directory_is_refused(tmp_path: Path) -> None:
    for relpath in ("PROJECT_LOCK.md", "../escape.json", ".prune", "docs/report.json"):
        with pytest.raises(scan.MemoryScanError):
            scan.resolve_report_destination(tmp_path, relpath)


def test_an_absolute_report_target_is_refused(tmp_path: Path) -> None:
    with pytest.raises(scan.MemoryScanError):
        scan.resolve_report_destination(tmp_path, "/etc/passwd")


def test_a_symlinked_report_file_is_refused(tmp_path: Path) -> None:
    (tmp_path / ".prune").mkdir()
    (tmp_path / "target.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".prune" / "report.json").symlink_to(tmp_path / "target.json")
    with pytest.raises(scan.MemoryScanError):
        scan.resolve_report_destination(tmp_path, ".prune/report.json")


def test_a_legal_report_target_is_written(world: dict[str, Path]) -> None:
    report = build(world)
    destination = scan.write_report(world["root"], report, relpath=".prune/memory_report.json")
    assert destination == world["root"] / ".prune" / "memory_report.json"
    written = json.loads(destination.read_text(encoding="utf-8"))
    assert written["schema_version"] == scan.REPORT_SCHEMA_VERSION


def test_the_cli_writes_a_report_and_exits_zero(
    world: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = scan.main(
        [
            "--repo-root", str(world["root"]),
            "--file-memory-dir", str(world["memory"]),
            "--vnext-cards-dir", str(world["cards"]),
            "--transcript-dir", str(world["transcripts"]),
            "--activation-ledger", str(world["ledger"]),
            "--output", ".prune/memory_reference_report.json",
        ]
    )
    assert exit_code == 0
    assert (world["root"] / ".prune" / "memory_reference_report.json").is_file()
    summary = json.loads(capsys.readouterr().out)
    assert summary["said_card_unwritten_by_class"] == {
        "self_reference": 0,
        "past_tense_verified": 0,
        "candidate": 0,
    }
    assert summary["suppressed_by_class"] == {
        "self_reference": 0,
        "past_tense_verified": 0,
    }


def test_the_cli_refuses_with_a_non_zero_exit_and_writes_no_report(world: dict[str, Path]) -> None:
    _vnext_card(world["cards"], "uncommitted-card")
    exit_code = scan.main(
        [
            "--repo-root", str(world["root"]),
            "--file-memory-dir", str(world["memory"]),
            "--vnext-cards-dir", str(world["cards"]),
            "--transcript-dir", str(world["transcripts"]),
            "--activation-ledger", str(world["ledger"]),
        ]
    )
    assert exit_code == 1
    assert not (world["root"] / ".prune" / "memory_reference_report.json").exists()


def test_timedelta_import_is_used_for_the_window() -> None:
    """Guard against the window silently becoming a no-op."""
    promise = scan.Promise("t.jsonl", "s", datetime(2026, 7, 12, tzinfo=timezone.utc), "值得进记忆", PROMISE)
    arrival = scan.CardArrival(
        scan.LAYER_FILE, "pkill", promise.at + timedelta(days=10), frozenset({"pkill"})
    )
    assert scan.scan_said_card_unwritten([promise], [arrival], window_days=3)
    assert not scan.scan_said_card_unwritten([promise], [arrival], window_days=30)


# --------------------------------------------------------------------------
# every namespace, not just this project's (2026-08-08)
# --------------------------------------------------------------------------


@pytest.fixture
def namespaces(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    """Two CC namespaces side by side, in the shape the discovery rule requires.

    `~/.claude/projects/<ns>/memory` — the parent-of-parent must be literally
    named ``projects``, or the expansion does not fire.  That guard is what
    stops a fixture path from dragging in its neighbours.
    """
    projects = tmp_path / "projects"
    current = projects / "-home-zhuran24-zmd-pj" / "memory"
    neighbour = projects / "-home-zhuran24-other" / "memory"
    current.mkdir(parents=True)
    neighbour.mkdir(parents=True)
    _file_card(current, "alpha")
    _index(current, ["alpha"])
    _file_card(neighbour, "beta")
    _file_card(neighbour, "gamma")
    _index(neighbour, ["beta", "gamma"])
    monkeypatch.setattr(scan, "DEFAULT_FILE_MEMORY_DIR", current)
    return {"projects": projects, "current": current, "neighbour": neighbour}


def _namespace_sources(report: dict[str, Any]) -> dict[str, int]:
    return {
        entry["namespace"]: entry["card_count"]
        for entry in report["metadata"]["sources"]["file_memory_namespaces"]
    }


def test_the_default_surface_is_every_namespace(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """One hard-coded namespace left 148 cards outside every machine we have."""
    report = build(world, file_memory_dir=None)

    assert _namespace_sources(report) == {"current": 1, "-home-zhuran24-other": 2}
    assert report["metadata"]["sources"]["file_memory_cards_all_namespaces"] == 3


def test_named_past_report_resolves_a_card_in_another_namespace(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    slug = "cross-namespace-memory-card"
    _file_card(
        namespaces["neighbour"],
        slug,
        description="cross namespace completion",
        modified="2020-01-01T00:00:00Z",
    )
    _index(namespaces["neighbour"], ["beta", "gamma", slug])
    _transcript(
        world["transcripts"],
        "cross-namespace-past",
        [(PROMISE_AT, f"这个坑已写进记忆卡 `{slug}`。")],
    )

    report = build(world, file_memory_dir=None, window_days=0)
    assert report["metadata"]["flag_counts"]["said_card_unwritten"] == 0
    assert report["metadata"]["suppressed_by_class"]["past_tense_verified"] == 1
    verified = report["said_card_unwritten"]["groups"]["past_tense_verified"][0]
    assert verified["evidence"]["verified_card_slugs"] == [slug]


def test_a_neighbour_card_is_judged_against_its_own_index(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """本条是防刷屏的那道闸。

    别的命名空间的卡不在**本项目**的 MEMORY.md 里是常态,不是孤儿——拿本项目
    的索引去对照它们,148 张卡会整批变成"候选",而那不是发现,是类目错误。
    """
    report = build(world, file_memory_dir=None)

    assert report["metadata"]["flag_counts"]["orphan_card"] == 0
    assert flags(report["candidates"]) == []
    assert flags(report["fyi"]) == []


def test_a_real_neighbour_orphan_is_reported_as_fyi_with_its_namespace(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """邻居真有孤儿卡要报出来,但那是人家的清理工作,不进本仓候选。"""
    _file_card(namespaces["neighbour"], "delta")
    report = build(world, file_memory_dir=None)

    assert report["metadata"]["flag_counts"]["orphan_card"] == 1
    assert flags(report["candidates"]) == []
    orphan = [item for item in report["fyi"] if item["flag"] == "orphan_card"]
    assert len(orphan) == 1
    assert orphan[0]["evidence"]["namespace"] == "-home-zhuran24-other"
    assert orphan[0]["safety_lock"]["locked"] is True


def test_the_same_card_name_in_two_namespaces_gets_two_item_ids(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """item_id 从 layer/flag/subject/locator 算出来,同名卡不带命名空间会撞成一条。"""
    _file_card(namespaces["current"], "twin")
    _file_card(namespaces["neighbour"], "twin")
    report = build(world, file_memory_dir=None)

    orphans = [
        item
        for item in report["candidates"] + report["fyi"]
        if item["flag"] == "orphan_card" and item["evidence"]["card"] == "twin.md"
    ]
    assert len(orphans) == 2
    assert len({item["item_id"] for item in orphans}) == 2


def test_an_orphan_in_this_namespace_is_still_a_candidate(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """扩面不许把本项目自己的孤儿也降级。"""
    _file_card(namespaces["current"], "unindexed")
    report = build(world, file_memory_dir=None)

    assert flags(report["candidates"]) == [("orphan_card", "unindexed.md")]
    assert report["candidates"][0]["evidence"]["namespace"] == "current"


def test_an_explicit_directory_scans_only_that_directory(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """点名一个目录 = 只问那一个,夹具永远不该被邻居污染。"""
    report = build(world, file_memory_dir=namespaces["current"])

    assert _namespace_sources(report) == {"current": 1}


def test_a_wikilink_to_a_neighbour_card_is_not_dangling(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """跨命名空间的链接对读者是通的(`mem.py find` 就是跨层查),报 dangling 是假阳。"""
    _file_card(namespaces["current"], "linker", body="see [[beta]]")
    _index(namespaces["current"], ["alpha", "linker"])
    report = build(world, file_memory_dir=None)

    assert report["metadata"]["flag_counts"]["dangling_wikilink"] == 0


def test_a_neighbour_without_an_index_reports_its_cards_instead_of_stopping(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """邻居缺索引不是静默跳过:把它当空索引,里面的卡就都以孤儿身份现身。"""
    (namespaces["neighbour"] / scan.INDEX_FILENAME).unlink()
    report = build(world, file_memory_dir=None)

    assert report["metadata"]["flag_counts"]["orphan_card"] == 2
    assert flags(report["candidates"]) == []
    assert {item["evidence"]["namespace"] for item in report["fyi"] if item["flag"] == "orphan_card"} == {
        "-home-zhuran24-other"
    }


def test_this_namespace_still_fails_closed_without_an_index(
    world: dict[str, Path], namespaces: dict[str, Path]
) -> None:
    """本项目自己的收件箱缺索引是系统坏了,不是邻居的事——照旧硬失败。"""
    (namespaces["current"] / scan.INDEX_FILENAME).unlink()
    with pytest.raises(scan.MemoryScanError):
        build(world, file_memory_dir=None)


def test_the_discovery_rule_only_expands_a_real_namespace_shape(tmp_path: Path) -> None:
    plain = tmp_path / "memory"
    plain.mkdir()
    (tmp_path / "sibling" / "memory").mkdir(parents=True)

    assert scan.file_memory_dirs(plain) == [(plain, scan.NAMESPACE_CURRENT)]
