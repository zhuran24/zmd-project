"""Behavioural tests for the prune-system docs reference adapter.

Almost every scenario is built inside a throwaway fixture repository so that
the tests state what the scanner does rather than what this repository happens
to contain.  Four look at the real repository, and only at things a fixture
cannot stand in for: two assert the committed registry is internally complete
and names only tracked members, one asserts the anchor parser recognises
``PROJECT_LOCK.md``'s uppercase section numbering, and one drives the committed
suppression-marker list through the scanner one marker at a time.

A real-repository *scan* is deliberately not tested here: the scanner refuses
to produce a report from anything but ``main`` with a clean tree, so the
end-to-end refusal path is exercised on fixture repositories instead.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devtools import docs_reference_scan as scan  # noqa: E402


CONTRACT_KEYS = {
    "item_id",
    "layer",
    "flag",
    "signals",
    "safety_lock",
    "confidence",
    "evidence",
}

GIT_ENV_ARGS = (
    "-c",
    "user.name=docs scan fixture",
    "-c",
    "user.email=fixture@invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *GIT_ENV_ARGS, *args],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return completed.stdout.decode("utf-8")


def _default_registry() -> dict[str, Any]:
    return {
        "schema_version": "repository_doc_classes_v1",
        "authority": {
            "role": "descriptive_governance_projection",
            "higher_authorities": ["PROJECT_LOCK.md"],
            "cannot_grant": ["permission to edit any document"],
        },
        "document_classes": ["locked", "historical", "living"],
        "scan_scope": {
            "include_globs": ["*.md"],
            "exclude_globs": [],
            "out_of_scope_notes": [
                {"pattern": "notes/**", "rationale": "Scratch notes are not registered documents."}
            ],
        },
        "rules": [
            {
                "id": "locked_doc",
                "match": {"path": "LOCKED.md"},
                "document_class": "locked",
                "rationale": "Locked governance surface.",
            },
            {
                "id": "historical_doc",
                "match": {"path": "HISTORY.md"},
                "document_class": "historical",
                "rationale": "Dated evidence.",
            },
            {
                "id": "living_doc",
                "match": {"path": "GUIDE.md"},
                "document_class": "living",
                "rationale": "Current operating guidance.",
            },
        ],
        "reference_scan": {
            "symbol_source_globs": ["src/**/*.py"],
            "context_suppression_markers": ["removed", "已删"],
            "external_artifact_manifest": "data/external_artifacts.json",
            "absent_by_design_prefixes": [
                {"prefix": "data/generated/", "rationale": "Generated output, never committed."}
            ],
            "symbol_reference_ignore": [],
            "known_historical_commit_hashes": [
                {
                    "hash": "abc1234",
                    "cited_in": "GUIDE.md",
                    "rationale": "History predates the delivery copy.",
                }
            ],
        },
    }


BASE_DOCUMENTS: dict[str, str] = {
    "LOCKED.md": "# Locked\n\nDead on purpose: `src/never.py` and `absent_symbol()`.\n",
    "HISTORY.md": "# History\n\n## 1. real\n\nNothing to see.\n",
    "GUIDE.md": "# Guide\n\nAll good: `src/thing.py`.\n",
    "notes/aside.md": "# Aside\n\nOut of scope: `src/never.py`.\n",
}

BASE_SOURCES: dict[str, str] = {
    "src/thing.py": "def existing_symbol() -> int:\n    return 1\n",
    "scripts/real_tool.py": "print(1)\n",
    "data/external_artifacts.json": json.dumps(
        {
            "schema_version": 1,
            "artifacts": [{"id": "big", "path": "data/external/big.json"}],
        },
        indent=2,
    )
    + "\n",
}


def _write(root: Path, relpath: str, content: str) -> None:
    destination = root / relpath
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def make_repo(
    tmp_path: Path,
    *,
    documents: Mapping[str, str] | None = None,
    registry: Mapping[str, Any] | None = None,
    extra_files: Mapping[str, str] | None = None,
    name: str = "repo",
) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", "main", "-q")

    payload = dict(BASE_DOCUMENTS)
    payload.update(documents or {})
    payload.update(BASE_SOURCES)
    payload.update(extra_files or {})
    for relpath, content in payload.items():
        _write(root, relpath, content)
    _write(
        root,
        scan.REGISTRY_RELPATH,
        json.dumps(registry if registry is not None else _default_registry(), ensure_ascii=False, indent=2)
        + "\n",
    )

    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def build(root: Path) -> dict[str, Any]:
    return scan.build_report(root)


def flags(items: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [
        (item["flag"], item["evidence"]["document"], item["evidence"]["reference"]) for item in items
    ]


# --------------------------------------------------------------------------
# positive cases: one per deterministic flag
# --------------------------------------------------------------------------


def test_dead_repo_path_is_a_candidate_when_the_path_is_gone(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nRun `scripts/vanished_tool.py` first.\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [
        ("dead_repo_path", "GUIDE.md", "scripts/vanished_tool.py")
    ]
    item = report["candidates"][0]
    assert item["evidence"]["line"] == 3
    assert item["evidence"]["line_text"] == "Run `scripts/vanished_tool.py` first."
    assert item["safety_lock"] == {"locked": False, "reasons": []}


def test_dead_symbol_ref_is_a_candidate_when_the_symbol_is_gone(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nCall `load_strict_json_file()` to parse.\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [
        ("dead_symbol_ref", "GUIDE.md", "load_strict_json_file()")
    ]
    assert report["candidates"][0]["evidence"]["detail"]["symbol"] == "load_strict_json_file"


def test_dead_symbol_ref_covers_a_file_line_reference_past_the_end_of_the_file(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nGuard lives at `src/thing.py:4096`.\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [("dead_symbol_ref", "GUIDE.md", "src/thing.py:4096")]
    detail = report["candidates"][0]["evidence"]["detail"]
    assert detail["file_line_count"] == 2
    assert detail["start"] == 4096


def test_dead_doc_anchor_is_a_candidate_for_a_missing_document(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nSee [the plan](PLAN.md) for detail.\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [("dead_doc_anchor", "GUIDE.md", "PLAN.md")]
    assert report["candidates"][0]["signals"] == ["referenced_document_does_not_exist"]


def test_dead_doc_anchor_is_a_candidate_for_a_missing_section_anchor(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nRuling recorded in `HISTORY.md` §9.\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [("dead_doc_anchor", "GUIDE.md", "HISTORY.md §9")]
    assert report["candidates"][0]["signals"] == ["referenced_section_anchor_does_not_exist"]


def test_dead_commit_hash_is_a_candidate_when_the_commit_cannot_be_resolved(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nLanded in `fee1dead` on main.\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [("dead_commit_hash", "GUIDE.md", "fee1dead")]


def test_unregistered_document_in_scope_is_caught(tmp_path: Path) -> None:
    root = make_repo(tmp_path, documents={"NEWCOMER.md": "# Newcomer\n\nHello.\n"})
    report = build(root)
    assert flags(report["candidates"]) == [
        ("unregistered_doc", "NEWCOMER.md", "NEWCOMER.md")
    ]
    assert report["metadata"]["scope"]["unregistered_document_count"] == 1


# --------------------------------------------------------------------------
# anchors, fragments and relative links
# --------------------------------------------------------------------------


def _docs_registry() -> dict[str, Any]:
    """The default registry, widened to a ``docs/`` family."""
    registry = _default_registry()
    registry["scan_scope"]["include_globs"] = ["*.md", "docs/*.md"]
    registry["rules"].append(
        {
            "id": "docs_family",
            "match": {"glob": "docs/*.md"},
            "document_class": "living",
            "rationale": "Nested living documents.",
        }
    )
    registry["rules"].append(
        {
            "id": "root_plan",
            "match": {"path": "PLAN.md"},
            "document_class": "living",
            "rationale": "Root-level plan.",
        }
    )
    return registry


def test_a_heading_fragment_link_to_a_missing_document_is_a_candidate(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nSee [the plan](PLAN.md#definitely-missing).\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [
        ("dead_doc_anchor", "GUIDE.md", "PLAN.md#definitely-missing")
    ]
    assert report["candidates"][0]["signals"] == ["referenced_document_does_not_exist"]


def test_a_heading_fragment_that_no_heading_provides_is_a_candidate(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nSee [the record](HISTORY.md#no-such-heading).\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [
        ("dead_doc_anchor", "GUIDE.md", "HISTORY.md#no-such-heading")
    ]
    assert report["candidates"][0]["signals"] == ["referenced_heading_anchor_does_not_exist"]
    assert report["candidates"][0]["evidence"]["detail"]["fragment"] == "no-such-heading"


@pytest.mark.parametrize("fragment", ["history", "1-real", "history-1", "%E5%8E%86%E5%8F%B2"])
def test_a_live_or_unjudgeable_heading_fragment_is_not_a_candidate(
    tmp_path: Path, fragment: str
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": f"# Guide\n\nSee [the record](HISTORY.md#{fragment}).\n"},
    )
    assert build(root)["candidates"] == []


def test_setext_headings_switch_off_anchor_checking_but_not_missing_document_checking(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={
            "HISTORY.md": "History\n=======\n\nOld business\n------------\n\nNothing.\n",
            "GUIDE.md": (
                "# Guide\n\n"
                "See [the record](HISTORY.md#no-such-heading) and [the plan](PLAN.md#x).\n"
            ),
        },
    )
    report = build(root)
    assert flags(report["candidates"]) == [("dead_doc_anchor", "GUIDE.md", "PLAN.md#x")]


def test_a_relative_link_resolves_against_the_citing_document_before_the_root(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        registry=_docs_registry(),
        documents={
            "PLAN.md": "# Plan\n\n## 1. present at the root\n",
            "docs/PLAN.md": "# Nested plan\n\n## 2. only section two\n",
            "docs/GUIDE2.md": "# Nested guide\n\nRuling recorded in `PLAN.md` §1.\n",
        },
    )
    report = build(root)
    assert flags(report["candidates"]) == [("dead_doc_anchor", "docs/GUIDE2.md", "PLAN.md §1")]
    assert report["candidates"][0]["evidence"]["detail"]["target"] == "docs/PLAN.md"


def test_a_parent_relative_markdown_link_is_scanned(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        registry=_docs_registry(),
        documents={
            "PLAN.md": "# Plan\n",
            "docs/PLAN.md": "# Nested plan\n",
            "docs/GUIDE2.md": "# Nested guide\n\nUp one: [gone](../MISSING.md).\n",
        },
    )
    report = build(root)
    assert flags(report["candidates"]) == [
        ("dead_doc_anchor", "docs/GUIDE2.md", "../MISSING.md")
    ]


def test_a_dot_slash_relative_markdown_link_is_scanned(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nRight here: [gone](./MISSING.md).\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [("dead_doc_anchor", "GUIDE.md", "./MISSING.md")]


def test_a_dot_slash_repository_path_is_scanned(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nRun `./scripts/vanished_tool.py`.\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [
        ("dead_repo_path", "GUIDE.md", "scripts/vanished_tool.py")
    ]


def test_a_literal_ellipsis_placeholder_is_still_not_a_reference(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nEvidence lands in `docs/research/.../review/`.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["metadata"]["suppression_counts"]["not_format_explicit"] == 1


def test_an_uppercase_section_number_heading_is_recognised(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={
            "HISTORY.md": "# History\n\n## 1A. Certified Theorem Scope\n\n### 3C. Boundary\n",
            "GUIDE.md": "# Guide\n\nScope in `HISTORY.md` §1A, boundary in `HISTORY.md` §3C.\n",
        },
    )
    assert build(root)["candidates"] == []

    root_missing = make_repo(
        tmp_path,
        name="repo_missing",
        documents={
            "HISTORY.md": "# History\n\n## 1A. Certified Theorem Scope\n",
            "GUIDE.md": "# Guide\n\nBoundary in `HISTORY.md` §9Z.\n",
        },
    )
    assert flags(build(root_missing)["candidates"]) == [
        ("dead_doc_anchor", "GUIDE.md", "HISTORY.md §9Z")
    ]


def test_the_real_project_lock_uppercase_sections_are_recognised() -> None:
    """The repository's most cited anchors are ``## 1A.`` / ``### 3C.`` shaped."""
    text = (PROJECT_ROOT / "PROJECT_LOCK.md").read_text(encoding="utf-8")
    index = scan._anchor_index(text)
    assert index.checkable is True
    assert {"1a", "2a", "2b", "3a", "3b", "3c"} <= index.sections


def test_a_repository_root_file_line_reference_is_scanned(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nGuard lives at `HISTORY.md:4096`.\n"},
    )
    report = build(root)
    assert flags(report["candidates"]) == [("dead_symbol_ref", "GUIDE.md", "HISTORY.md:4096")]
    assert report["candidates"][0]["signals"] == ["referenced_line_range_is_outside_the_file"]


def test_a_colon_number_token_that_names_no_tracked_root_file_is_not_a_reference(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nortools `9.16:0` and clock `12:30`.\n"},
    )
    assert build(root)["candidates"] == []


def test_a_bare_basename_file_line_reference_to_a_nested_file_is_not_judged(
    tmp_path: Path,
) -> None:
    """``thing.py:99`` is shorthand for ``src/thing.py``, not a missing root file.

    The repository-root ``main.py`` is what makes this ambiguous: it puts a
    root-level ``.py`` in the tree, so a bare ``.py`` basename becomes
    plausible as a root file — and this repository's prose uses exactly that
    shorthand (``exact_campaign.py:3532`` for a file under ``src/``).
    """
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nGuard lives at `thing.py:99`.\n"},
        extra_files={"main.py": "print(0)\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    # The root-level file that really is tracked stays checkable.
    checked = make_repo(
        tmp_path,
        name="repo_root_main",
        documents={"GUIDE.md": "# Guide\n\nGuard lives at `main.py:99`.\n"},
        extra_files={"main.py": "print(0)\n"},
    )
    assert flags(build(checked)["candidates"]) == [("dead_symbol_ref", "GUIDE.md", "main.py:99")]


def test_a_trailing_slash_directory_reference_keeps_its_absent_by_design_allowlist(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nNever commit `data/generated/`.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["metadata"]["suppression_counts"]["absent_by_design"] == 1


# --------------------------------------------------------------------------
# negative cases: the three-premise exclusions, one at a time
# --------------------------------------------------------------------------


def test_a_reference_whose_paragraph_talks_about_removal_is_suppressed(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={
            "GUIDE.md": "# Guide\n\n旧脚本 `scripts/vanished_tool.py` 已删，改走新入口。\n",
        },
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["metadata"]["suppression_counts"]["context_marker"] == 1


COMMITTED_SUPPRESSION_MARKERS = tuple(
    scan.load_registry(PROJECT_ROOT).reference_scan["context_suppression_markers"]
)


@pytest.mark.parametrize("marker", COMMITTED_SUPPRESSION_MARKERS)
def test_every_registered_suppression_marker_actually_suppresses(
    tmp_path: Path, marker: str
) -> None:
    """Pin every marker the committed registry declares, not just one of them.

    A marker that stops working — a spelling drift, an accidental deletion —
    is invisible unless each one is exercised, and the whole three-premise
    exclusion rests on this list.
    """
    registry = _default_registry()
    registry["reference_scan"]["context_suppression_markers"] = sorted(
        COMMITTED_SUPPRESSION_MARKERS
    )
    root = make_repo(
        tmp_path,
        registry=registry,
        documents={"GUIDE.md": f"# Guide\n\n`scripts/vanished_tool.py` {marker} 2026-01-01.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["metadata"]["suppression_counts"]["context_marker"] == 1


def test_an_external_artifact_path_is_allowlisted_even_though_it_is_absent(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nRestore `data/external/big.json` first.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["metadata"]["suppression_counts"]["external_artifact_allowlist"] == 1


def test_an_absent_by_design_generated_path_is_allowlisted(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nOutput lands in `data/generated/run.json`.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["metadata"]["suppression_counts"]["absent_by_design"] == 1


def test_an_absent_by_design_file_line_reference_is_counted_as_absent_by_design(
    tmp_path: Path,
) -> None:
    """It was counted against the external-artifact allowlist, which it is not."""
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nSee `data/generated/run.json:12`.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    counts = report["metadata"]["suppression_counts"]
    assert counts["absent_by_design"] == 1
    assert counts["external_artifact_allowlist"] == 0


def test_an_external_artifact_file_line_reference_is_counted_against_the_allowlist(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nSee `data/external/big.json:12`.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    counts = report["metadata"]["suppression_counts"]
    assert counts["external_artifact_allowlist"] == 1
    assert counts["absent_by_design"] == 0


def test_prose_and_fenced_code_are_not_format_explicit_references(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={
            "GUIDE.md": (
                "# Guide\n\n"
                "Historically the entry point was scripts/vanished_tool.py somewhere.\n\n"
                "```bash\n"
                "python scripts/vanished_tool.py --full\n"
                "```\n"
            )
        },
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["metadata"]["suppression_counts"]["fenced_code_lines"] == 3


def test_the_fence_state_machine_skips_only_what_is_inside_the_fence(tmp_path: Path) -> None:
    """Sensitive to the mechanism, not just to the absence of findings.

    The token inside the fence is a real format-explicit dead reference and the
    one after it is identical, so this stays green only while the state machine
    both enters *and* leaves the fenced block.
    """
    root = make_repo(
        tmp_path,
        documents={
            "GUIDE.md": (
                "# Guide\n\n"
                "```bash\n"
                "Inside the fence: `scripts/inside_tool.py` and [link](INSIDE.md).\n"
                "```\n\n"
                "Outside the fence: `scripts/outside_tool.py`.\n"
            )
        },
    )
    report = build(root)
    assert flags(report["candidates"]) == [
        ("dead_repo_path", "GUIDE.md", "scripts/outside_tool.py")
    ]
    assert report["metadata"]["suppression_counts"]["fenced_code_lines"] == 3


def test_a_registered_known_historical_commit_hash_never_becomes_a_candidate(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nOriginal machine history: `abc1234`.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["fyi"] == []
    counts = report["metadata"]["suppression_counts"]
    assert counts["commit_hash_registered_known_historical"] == 1
    assert counts["commit_hash_in_non_living_document"] == 0


def test_a_historical_document_only_ever_reaches_the_fyi_section(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={
            "HISTORY.md": "# History\n\n## 1. real\n\nBuilt with `scripts/vanished_tool.py`.\n"
        },
    )
    report = build(root)
    assert report["candidates"] == []
    assert flags(report["fyi"]) == [
        ("dead_repo_path", "HISTORY.md", "scripts/vanished_tool.py")
    ]
    assert report["fyi"][0]["safety_lock"] == {
        "locked": True,
        "reasons": ["historical_evidence_class_never_yields_a_change_candidate"],
    }


def test_a_historical_document_never_reports_an_unresolvable_commit_hash(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"HISTORY.md": "# History\n\n## 1. real\n\nLanded in `fee1dead`.\n"},
    )
    report = build(root)
    assert report["candidates"] == []
    assert report["fyi"] == []
    counts = report["metadata"]["suppression_counts"]
    # The two suppression mechanisms are counted apart, so a reader can tell
    # which one actually kept this hash out of the report.
    assert counts["commit_hash_in_non_living_document"] == 1
    assert counts["commit_hash_registered_known_historical"] == 0


def test_a_locked_document_is_never_a_scan_subject(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    report = build(root)
    documents = {
        item["evidence"]["document"] for item in report["candidates"] + report["fyi"]
    }
    assert "LOCKED.md" not in documents
    assert report["metadata"]["scope"]["class_counts"]["locked"] == 1
    assert report["metadata"]["scope"]["subject_document_count"] == 2


def test_live_references_produce_no_findings_at_all(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD").strip()[:9]
    (root / "GUIDE.md").write_text(
        "# Guide\n\n"
        "Module `src/thing.py`, symbol `existing_symbol()`, line `src/thing.py:1`.\n\n"
        "History in [the record](HISTORY.md) `HISTORY.md` §1, landed in `" + head + "`.\n",
        encoding="utf-8",
    )
    _git(root, "commit", "-q", "-a", "-m", "live references")
    report = build(root)
    assert report["candidates"] == []
    assert report["fyi"] == []


# --------------------------------------------------------------------------
# fail-closed self check
# --------------------------------------------------------------------------


def test_a_modified_scanned_document_hard_refuses_the_report(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "GUIDE.md").write_text("# Guide\n\nUncommitted edit `src/gone.py`.\n", encoding="utf-8")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "GUIDE.md" in str(excinfo.value)


def test_a_modified_registry_hard_refuses_the_report(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    registry = _default_registry()
    registry["rules"][2]["rationale"] = "edited in the worktree"
    (root / scan.REGISTRY_RELPATH).write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert scan.REGISTRY_RELPATH in str(excinfo.value)


def test_a_modified_symbol_source_hard_refuses_the_report(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "src" / "thing.py").write_text("def existing_symbol():\n    return 2\n", encoding="utf-8")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "src/thing.py" in str(excinfo.value)


def test_a_non_main_branch_hard_refuses_the_report(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "feature/whatever")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "feature/whatever" in str(excinfo.value)


def test_an_untracked_in_scope_document_hard_refuses_the_report(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "DRAFT.md").write_text("# Draft\n", encoding="utf-8")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "DRAFT.md" in str(excinfo.value)


# The six bypasses below share one shape: the report's content depends on
# filesystem state that the old truth-source set did not cover, so the scan
# answered a different question while still certifying its inputs were clean.


def test_a_modified_file_line_target_outside_the_symbol_globs_hard_refuses(
    tmp_path: Path,
) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nEntry point at `scripts/real_tool.py:5`.\n"},
    )
    assert flags(build(root)["candidates"]) == [
        ("dead_symbol_ref", "GUIDE.md", "scripts/real_tool.py:5")
    ]
    # scripts/ is outside the fixture's symbol_source_globs, so this file was
    # never a truth source — but the finding is a function of its line count.
    (root / "scripts" / "real_tool.py").write_text("print(1)\n" * 6, encoding="utf-8")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "scripts/real_tool.py" in str(excinfo.value)


def test_a_modified_out_of_scope_anchor_target_hard_refuses(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nRuling in `notes/aside.md` §2.\n"},
    )
    assert flags(build(root)["candidates"]) == [
        ("dead_doc_anchor", "GUIDE.md", "notes/aside.md §2")
    ]
    # notes/** is declared out of scope, so it is not a scanned document — but
    # its headings decide whether the anchor above resolves.
    (root / "notes" / "aside.md").write_text(
        "# Aside\n\n## 2. now it exists\n\nOut of scope: `src/never.py`.\n", encoding="utf-8"
    )
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "notes/aside.md" in str(excinfo.value)


def test_a_new_untracked_file_at_a_referenced_path_hard_refuses(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nRun `scripts/vanished_tool.py` first.\n"},
    )
    assert flags(build(root)["candidates"]) == [
        ("dead_repo_path", "GUIDE.md", "scripts/vanished_tool.py")
    ]
    (root / "scripts" / "vanished_tool.py").write_text("print(2)\n", encoding="utf-8")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "scripts/vanished_tool.py" in str(excinfo.value)


def test_a_staged_deletion_of_a_symbol_source_hard_refuses(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nCall `existing_symbol()` to parse.\n"},
        extra_files={"src/other.py": "def other_symbol() -> int:\n    return 2\n"},
    )
    assert build(root)["candidates"] == []
    _git(root, "rm", "-q", "src/thing.py")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    message = str(excinfo.value)
    assert "deleted in the index" in message
    assert "src/thing.py" in message


def test_a_staged_deletion_of_an_in_scope_document_hard_refuses(tmp_path: Path) -> None:
    root = make_repo(tmp_path, documents={"NEWCOMER.md": "# Newcomer\n\nHello.\n"})
    assert flags(build(root)["candidates"]) == [
        ("unregistered_doc", "NEWCOMER.md", "NEWCOMER.md")
    ]
    _git(root, "rm", "-q", "NEWCOMER.md")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    message = str(excinfo.value)
    assert "deleted in the index" in message
    assert "NEWCOMER.md" in message


def test_an_assume_unchanged_document_hard_refuses(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _git(root, "update-index", "--assume-unchanged", "GUIDE.md")
    (root / "GUIDE.md").write_text("# Guide\n\nGone: `scripts/vanished_tool.py`.\n", encoding="utf-8")
    assert _git(root, "status", "--porcelain") == ""
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    message = str(excinfo.value)
    assert "assume-unchanged" in message
    assert "GUIDE.md" in message


def test_a_skip_worktree_document_hard_refuses(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _git(root, "update-index", "--skip-worktree", "GUIDE.md")
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "GUIDE.md" in str(excinfo.value)


def test_the_cli_refuses_with_a_non_zero_exit_and_writes_no_report(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "feature/whatever")
    exit_code = scan.main(["--repo-root", str(root), "scan"])
    assert exit_code == 1
    assert not (root / scan.REPORT_RELPATH).exists()


def test_the_cli_writes_the_report_when_the_preconditions_hold(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={"GUIDE.md": "# Guide\n\nRun `scripts/vanished_tool.py`.\n"},
    )
    exit_code = scan.main(["--repo-root", str(root), "scan"])
    assert exit_code == 0
    report = json.loads((root / scan.REPORT_RELPATH).read_text(encoding="utf-8"))
    assert report["schema_version"] == scan.REPORT_SCHEMA_VERSION
    preconditions = report["metadata"]["preconditions"]
    assert preconditions["observed_branch"] == "main"
    assert preconditions["required_branch"] == "main"
    assert preconditions["truth_sources_clean"] is True
    assert len(preconditions["head_commit"]) == 40
    consulted = preconditions["consulted_paths"]
    assert consulted["reverified_after_scan"] is True
    assert consulted["consulted_path_count"] >= 1
    assert report["metadata"]["registry"]["path"] == scan.REGISTRY_RELPATH
    assert len(report["metadata"]["registry"]["sha256"]) == 64
    assert report["metadata"]["advisory"] is True


# --------------------------------------------------------------------------
# the write primitive: .prune/ or nothing
# --------------------------------------------------------------------------


def _guide_bytes(root: Path) -> bytes:
    return (root / "GUIDE.md").read_bytes()


@pytest.mark.parametrize(
    "output",
    [
        "GUIDE.md",
        "data/repository_governance/doc_classes.json",
        "../escaped.json",
        ".prune/../GUIDE.md",
        ".prune/../../escaped.json",
        ".prune",
        "",
    ],
)
def test_a_report_target_outside_the_prune_directory_is_refused(
    tmp_path: Path, output: str
) -> None:
    root = make_repo(tmp_path)
    before = _guide_bytes(root)
    exit_code = scan.main(["--repo-root", str(root), "scan", "--output", output])
    assert exit_code == 1
    assert _guide_bytes(root) == before
    assert not (root / scan.REPORT_RELPATH).exists()
    assert _git(root, "status", "--porcelain") == ""


def test_an_absolute_report_target_is_refused(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    victim = tmp_path / "outside.json"
    victim.write_text("untouched\n", encoding="utf-8")
    exit_code = scan.main(["--repo-root", str(root), "scan", "--output", str(victim)])
    assert exit_code == 1
    assert victim.read_text(encoding="utf-8") == "untouched\n"


def test_a_symlinked_report_file_is_refused(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    before = _guide_bytes(root)
    prune = root / scan.REPORT_DIR_RELPATH
    prune.mkdir()
    (prune / "docs_reference_report.json").symlink_to(root / "GUIDE.md")
    exit_code = scan.main(["--repo-root", str(root), "scan"])
    assert exit_code == 1
    assert _guide_bytes(root) == before
    assert (prune / "docs_reference_report.json").is_symlink()


def test_a_symlinked_prune_directory_is_refused(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / scan.REPORT_DIR_RELPATH).symlink_to(elsewhere, target_is_directory=True)
    exit_code = scan.main(["--repo-root", str(root), "scan"])
    assert exit_code == 1
    assert list(elsewhere.iterdir()) == []


def test_a_symlinked_nested_report_directory_is_refused(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    prune = root / scan.REPORT_DIR_RELPATH
    prune.mkdir()
    (prune / "nested").symlink_to(elsewhere, target_is_directory=True)
    exit_code = scan.main(["--repo-root", str(root), "scan", "--output", ".prune/nested/out.json"])
    assert exit_code == 1
    assert list(elsewhere.iterdir()) == []


def test_a_legal_nested_report_target_under_prune_is_written(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    exit_code = scan.main(
        ["--repo-root", str(root), "scan", "--output", ".prune/history/run.json"]
    )
    assert exit_code == 0
    written = root / ".prune" / "history" / "run.json"
    assert json.loads(written.read_text(encoding="utf-8"))["schema_version"] == (
        scan.REPORT_SCHEMA_VERSION
    )
    assert _git(root, "status", "--porcelain", "--untracked-files=no") == ""


# --------------------------------------------------------------------------
# shared output contract
# --------------------------------------------------------------------------


def test_every_item_carries_the_shared_prune_report_contract(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={
            "GUIDE.md": "# Guide\n\nGone: `scripts/vanished_tool.py` and `vanished()`.\n",
            "HISTORY.md": "# History\n\n## 1. real\n\nAlso gone: `scripts/vanished_tool.py`.\n",
            "NEWCOMER.md": "# Newcomer\n",
        },
    )
    report = build(root)
    items = report["candidates"] + report["fyi"]
    assert len(items) == 4
    for item in items:
        assert set(item) == CONTRACT_KEYS
        assert item["layer"] == "docs"
        assert item["confidence"] == "deterministic"
        assert item["flag"] in scan.FLAGS
        assert item["signals"] and all(isinstance(signal, str) for signal in item["signals"])
        assert set(item["safety_lock"]) == {"locked", "reasons"}
        assert set(item["evidence"]) >= {"document", "document_class", "line", "reference"}
    assert len({item["item_id"] for item in items}) == len(items)


def test_findings_are_ordered_deterministically(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        documents={
            "GUIDE.md": (
                "# Guide\n\n"
                "Second `scripts/b_tool.py`.\n"
                "First `scripts/a_tool.py`.\n"
            )
        },
    )
    report = build(root)
    assert [item["evidence"]["line"] for item in report["candidates"]] == [3, 4]


# --------------------------------------------------------------------------
# registry validation is fail-closed
# --------------------------------------------------------------------------


def test_a_registry_rule_naming_an_untracked_member_is_rejected(tmp_path: Path) -> None:
    registry = _default_registry()
    registry["rules"].append(
        {
            "id": "ghost",
            "match": {"path": "GHOST.md"},
            "document_class": "living",
            "rationale": "Names a document that is not tracked.",
        }
    )
    root = make_repo(tmp_path, registry=registry)
    with pytest.raises(scan.DocScanError) as excinfo:
        scan.validate_registry(root)
    assert "GHOST.md" in str(excinfo.value)


def test_markdown_that_is_neither_in_scope_nor_declared_out_of_scope_is_rejected(
    tmp_path: Path,
) -> None:
    root = make_repo(tmp_path, extra_files={"elsewhere/stray.md": "# Stray\n"})
    with pytest.raises(scan.DocScanError) as excinfo:
        scan.validate_registry(root)
    assert "elsewhere/stray.md" in str(excinfo.value)


def test_an_out_of_scope_note_may_not_overlap_the_scan_scope(tmp_path: Path) -> None:
    registry = _default_registry()
    registry["scan_scope"]["out_of_scope_notes"].append(
        {"pattern": "GUIDE.md", "rationale": "Contradicts the living rule."}
    )
    registry["scan_scope"]["out_of_scope_notes"].sort(key=lambda note: note["pattern"])
    root = make_repo(tmp_path, registry=registry)
    with pytest.raises(scan.DocScanError) as excinfo:
        scan.validate_registry(root)
    assert "GUIDE.md" in str(excinfo.value)


def test_an_unsorted_registry_list_is_rejected(tmp_path: Path) -> None:
    registry = _default_registry()
    registry["reference_scan"]["context_suppression_markers"] = ["已删", "removed"]
    root = make_repo(tmp_path, registry=registry)
    with pytest.raises(scan.DocScanError) as excinfo:
        scan.validate_registry(root)
    assert "context_suppression_markers" in str(excinfo.value)


def test_an_unknown_registry_field_is_rejected(tmp_path: Path) -> None:
    registry = _default_registry()
    registry["reference_scan"]["future_knob"] = True
    root = make_repo(tmp_path, registry=registry)
    with pytest.raises(scan.DocScanError) as excinfo:
        scan.validate_registry(root)
    assert "reference_scan" in str(excinfo.value)


def test_an_invalid_document_class_is_rejected(tmp_path: Path) -> None:
    registry = _default_registry()
    registry["rules"][2]["document_class"] = "advisory"
    root = make_repo(tmp_path, registry=registry)
    with pytest.raises(scan.DocScanError):
        scan.validate_registry(root)


def test_duplicate_json_keys_in_the_registry_are_rejected(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "temp")
    text = (root / scan.REGISTRY_RELPATH).read_text(encoding="utf-8")
    duplicated = text.replace(
        '"schema_version": "repository_doc_classes_v1",',
        '"schema_version": "repository_doc_classes_v1",\n  "rules": [],',
        1,
    )
    (root / scan.REGISTRY_RELPATH).write_text(duplicated, encoding="utf-8")
    with pytest.raises(scan.DocScanError) as excinfo:
        scan.load_registry(root)
    assert "duplicate JSON key" in str(excinfo.value)


# --------------------------------------------------------------------------
# the registry is the class gate, so it cannot be swapped out or contradicted
# --------------------------------------------------------------------------


def test_the_registry_path_is_a_constant_with_no_caller_supplied_override(tmp_path: Path) -> None:
    """A caller-chosen registry would be a way around the document class gate."""
    for function in (scan.load_registry, scan.build_report, scan.validate_registry):
        parameters = set(inspect.signature(function).parameters)
        assert parameters == {"root"}, f"{function.__name__} accepts more than a repository root"

    root = make_repo(tmp_path)
    rogue = tmp_path / "rogue_doc_classes.json"
    rogue_registry = _default_registry()
    rogue_registry["rules"][0]["document_class"] = "living"
    rogue.write_text(json.dumps(rogue_registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        scan.main(["--repo-root", str(root), "--registry", str(rogue), "scan"])
    assert excinfo.value.code == 2
    assert not (root / scan.REPORT_RELPATH).exists()

    # The committed registry is the only one the scanner will ever read.
    assert scan.load_registry(root).relpath == scan.REGISTRY_RELPATH
    report = build(root)
    documents = {item["evidence"]["document"] for item in report["candidates"] + report["fyi"]}
    assert "LOCKED.md" not in documents


def test_an_untracked_registry_hard_refuses_the_report(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _git(root, "rm", "-q", "--cached", scan.REGISTRY_RELPATH)
    _git(root, "commit", "-q", "-m", "untrack the registry")
    assert (root / scan.REGISTRY_RELPATH).is_file()
    with pytest.raises(scan.SelfCheckRefusal) as excinfo:
        build(root)
    assert "not tracked" in str(excinfo.value)
    assert scan.REGISTRY_RELPATH in str(excinfo.value)


def test_two_rules_claiming_one_document_for_different_classes_are_rejected(
    tmp_path: Path,
) -> None:
    registry = _default_registry()
    registry["rules"].insert(
        0,
        {
            "id": "catch_all",
            "match": {"glob": "*.md"},
            "document_class": "living",
            "rationale": "A broad rule that contradicts the locked and historical rules.",
        },
    )
    root = make_repo(tmp_path, registry=registry)
    with pytest.raises(scan.DocScanError) as excinfo:
        scan.validate_registry(root)
    message = str(excinfo.value)
    assert "conflicting document class rules" in message
    assert "catch_all=living" in message
    with pytest.raises(scan.DocScanError) as locked_conflict:
        scan._classify("LOCKED.md", registry["rules"])
    assert "LOCKED.md" in str(locked_conflict.value)


def test_two_rules_claiming_one_document_for_the_same_class_are_accepted(tmp_path: Path) -> None:
    registry = _default_registry()
    registry["rules"].insert(
        0,
        {
            "id": "living_doc_again",
            "match": {"glob": "GUIDE.*"},
            "document_class": "living",
            "rationale": "Redundant but not contradictory.",
        },
    )
    root = make_repo(tmp_path, registry=registry)
    assert scan.validate_registry(root)["class_counts"]["living"] == 1


# --------------------------------------------------------------------------
# the committed registry itself
# --------------------------------------------------------------------------


def test_the_committed_registry_covers_every_tracked_markdown_file() -> None:
    result = scan.validate_registry(PROJECT_ROOT)
    assert result["status"] == "PASS"
    assert result["unregistered_documents"] == []
    counts = result["class_counts"]
    assert set(counts) == set(scan.DOCUMENT_CLASSES)
    assert counts["locked"] >= 1
    assert counts["historical"] >= 1
    assert counts["living"] >= 1
    assert result["in_scope_document_count"] == sum(counts.values())


def test_the_committed_registry_only_names_members_that_exist() -> None:
    registry = scan.load_registry(PROJECT_ROOT)
    tracked = set(scan.tracked_paths(PROJECT_ROOT))
    for rule in registry.rules:
        selector, value = next(iter(rule["match"].items()))
        if selector == "path":
            assert value in tracked, f"{rule['id']} names an untracked member: {value}"
        elif selector == "paths":
            missing = [member for member in value if member not in tracked]
            assert not missing, f"{rule['id']} names untracked members: {missing}"
        elif selector == "prefix":
            assert any(path.startswith(value) for path in tracked), rule["id"]
        else:
            assert any(scan._glob_match(path, value) for path in tracked), rule["id"]
    reference_scan = registry.reference_scan
    assert reference_scan["external_artifact_manifest"] in tracked
    for entry in reference_scan["known_historical_commit_hashes"]:
        assert entry["cited_in"] in tracked
