"""Behavioural tests for the prune-system docs reference adapter.

Every scenario is built inside a throwaway fixture repository so that the tests
state what the scanner does rather than what this repository currently happens
to contain.  Two tests deliberately look at the real repository: one asserts the
committed registry is internally complete, the other asserts the shipped scanner
refuses to produce a report from a feature branch.
"""

from __future__ import annotations

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
    assert report["metadata"]["suppression_counts"]["commit_hash_classified_known_historical"] == 1


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
    assert report["metadata"]["suppression_counts"]["commit_hash_classified_known_historical"] == 1


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
    assert report["metadata"]["registry"]["path"] == scan.REGISTRY_RELPATH
    assert len(report["metadata"]["registry"]["sha256"]) == 64
    assert report["metadata"]["advisory"] is True


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
