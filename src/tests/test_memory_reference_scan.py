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


def _file_card(directory: Path, name: str, *, body: str = "body", description: str = "") -> Path:
    front = f"---\nname: {name}\ndescription: \"{description}\"\n---\n"
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


def test_a_promise_nobody_kept_is_a_candidate(world: dict[str, Path]) -> None:
    """The 2026-07-12 case, reproduced: said then, written 21 days later.

    An unrelated card written the next day must not be mistaken for the one
    that was promised.
    """
    _transcript(world["transcripts"], "session-a", [(PROMISE_AT, PROMISE)])
    _touched(_file_card(world["memory"], "unrelated-disk-layout"), "2026-07-13T00:00:00+00:00")
    _touched(
        _file_card(world["memory"], "pkill-argv-self-match-pitfall", description="pkill -f 自杀坑"),
        "2026-08-02T00:00:00+00:00",
    )
    _index(world["memory"], ["alpha", "unrelated-disk-layout", "pkill-argv-self-match-pitfall"])
    report = build(world)
    said = [item for item in report["candidates"] if item["flag"] == "said_card_unwritten"]
    assert len(said) == 1
    assert said[0]["evidence"]["pattern"] == "值得进记忆"
    assert said[0]["evidence"]["said_at"].startswith("2026-07-12")
    assert said[0]["confidence"] == scan.CONFIDENCE_HEURISTIC


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
    """
    import importlib.util

    hook_path = (
        Path(__file__).resolve().parents[2]
        / "cc_memory_vnext"
        / "hooks"
        / "post_tool_error_recall.py"
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


def test_the_cli_writes_a_report_and_exits_zero(world: dict[str, Path]) -> None:
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
