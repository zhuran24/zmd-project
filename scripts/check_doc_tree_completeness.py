#!/usr/bin/env python3
"""Check documentation-tree closeout completeness.

This checker turns the doc-tree closeout definition into a repeatable gate. It
is deliberately structural: it checks the living documentation architecture,
subject/projection wiring, and classified documentation surfaces. It does not
try to semantically rewrite historical archive prose.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import sync_doc_subjects as subject_sync

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs" / "DOC_TREE_COMPLETENESS.json"
DOCS_ROOT = REPO_ROOT / "docs"
PROJECT_BOOK_ROOT = DOCS_ROOT / "项目说明"
RESEARCH_ROOT = DOCS_ROOT / "research"
SPECS_ROOT = REPO_ROOT / "specs"
ROOT_MARKDOWN_SURFACES = ["README.md", "CLAUDE.md", "FILE_STATUS.md", "PROJECT_LOCK.md"]


@dataclass
class CheckState:
    failures: list[str] = field(default_factory=list)
    checks: int = 0

    def ok(self) -> None:
        self.checks += 1

    def fail(self, message: str) -> None:
        self.failures.append(message)


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def load_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"manifest not found: {rel(MANIFEST_PATH)}")
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("docs/DOC_TREE_COMPLETENESS.json schema_version must be 1")
    return data


def sorted_docs_top_level_files() -> list[str]:
    return sorted(rel(path) for path in DOCS_ROOT.iterdir() if path.is_file())


def sorted_docs_top_level_dirs() -> list[str]:
    return sorted(rel(path) for path in DOCS_ROOT.iterdir() if path.is_dir())


def sorted_project_book_docs() -> list[str]:
    return sorted(rel(path) for path in PROJECT_BOOK_ROOT.glob("*.md") if path.is_file())


def sorted_research_archive_dirs() -> list[str]:
    return sorted(path.name for path in RESEARCH_ROOT.iterdir() if path.is_dir())


def sorted_spec_files() -> list[str]:
    return sorted(rel(path) for path in SPECS_ROOT.glob("*.md") if path.is_file())


def compare_sequence(state: CheckState, label: str, actual: list[str], expected: list[str]) -> None:
    actual_set = set(actual)
    expected_set = set(expected)
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    if missing or extra:
        if missing:
            state.fail(f"{label}: manifest lists missing path(s): {', '.join(missing[:12])}")
        if extra:
            state.fail(f"{label}: unclassified new path(s): {', '.join(extra[:12])}")
        return
    state.ok()


def check_required_paths(state: CheckState, manifest: dict[str, object]) -> None:
    raw_paths = manifest.get("required_paths", [])
    if not isinstance(raw_paths, list):
        state.fail("required_paths must be a list")
        return
    missing = [path for path in raw_paths if not isinstance(path, str) or not (REPO_ROOT / path).exists()]
    if missing:
        state.fail(f"required_paths missing: {', '.join(str(path) for path in missing[:12])}")
        return
    state.ok()


def check_surface_manifests(state: CheckState, manifest: dict[str, object]) -> None:
    top_files = manifest.get("top_level_files", {})
    top_dirs = manifest.get("top_level_dirs", {})
    project_book = manifest.get("project_book_docs", [])
    research_dirs = manifest.get("research_archive_dirs", [])
    spec_files = manifest.get("spec_files", [])

    if not isinstance(top_files, dict):
        state.fail("top_level_files must be an object")
        return
    if not isinstance(top_dirs, dict):
        state.fail("top_level_dirs must be an object")
        return
    if not isinstance(project_book, list) or not all(isinstance(item, str) for item in project_book):
        state.fail("project_book_docs must be a list[str]")
        return
    if not isinstance(research_dirs, list) or not all(isinstance(item, str) for item in research_dirs):
        state.fail("research_archive_dirs must be a list[str]")
        return
    if not isinstance(spec_files, list) or not all(isinstance(item, str) for item in spec_files):
        state.fail("spec_files must be a list[str]")
        return

    compare_sequence(state, "docs top-level files", sorted_docs_top_level_files(), sorted(top_files))
    compare_sequence(state, "docs top-level dirs", sorted_docs_top_level_dirs(), sorted(top_dirs))
    compare_sequence(state, "project-book docs", sorted_project_book_docs(), sorted(project_book))
    compare_sequence(state, "research archive dirs", sorted_research_archive_dirs(), sorted(research_dirs))
    compare_sequence(state, "spec files", sorted_spec_files(), sorted(spec_files))

    unclassified_roles = [path for path, info in top_files.items() if isinstance(info, dict) and info.get("role") == "unclassified"]
    if unclassified_roles:
        state.fail(f"top_level_files has unclassified role(s): {', '.join(sorted(unclassified_roles)[:12])}")
    else:
        state.ok()


def markdown_surfaces() -> list[Path]:
    paths = [REPO_ROOT / path for path in ROOT_MARKDOWN_SURFACES]
    paths.extend(sorted(DOCS_ROOT.rglob("*.md")))
    return [path for path in paths if path.exists()]


def registered_projection_keys(projections: list[subject_sync.ProjectionSpec]) -> set[tuple[str, str, str]]:
    return {(rel(spec.path), spec.subject, spec.field) for spec in projections}


def check_subject_projection_graph(state: CheckState, manifest: dict[str, object]) -> None:
    try:
        subjects, projections = subject_sync.load_registry()
        fields = subject_sync.load_subject_fields(subjects)
        drifts = subject_sync.collect_drifts(projections, fields)
    except subject_sync.SubjectSyncError as exc:
        state.fail(f"subject/projection registry error: {exc}")
        return

    if drifts:
        sample = "; ".join(
            f"{rel(drift.projection.spec.path)}::{drift.projection.spec.subject}.{drift.projection.spec.field}"
            for drift in drifts[:8]
        )
        state.fail(f"subject/projection drift: {sample}")
    else:
        state.ok()

    registered_subject_paths = {rel(path) for path in subjects.values()}
    actual_subject_paths = sorted(
        rel(path) for path in (DOCS_ROOT / "subjects").glob("*.md") if path.name != "README.md"
    )
    compare_sequence(state, "registered subject files", actual_subject_paths, sorted(registered_subject_paths))

    projected_fields = {(spec.subject, spec.field) for spec in projections}
    unprojected_fields = sorted(
        f"{subject}.{field}" for subject, field in fields if (subject, field) not in projected_fields
    )
    if unprojected_fields:
        state.fail(f"subject field(s) with no projection: {', '.join(unprojected_fields[:12])}")
    else:
        state.ok()

    registered_blocks = registered_projection_keys(projections)
    discovered_blocks: set[tuple[str, str, str]] = set()
    duplicate_blocks: list[str] = []
    for path in markdown_surfaces():
        text = path.read_text(encoding="utf-8")
        seen_in_file: set[tuple[str, str]] = set()
        for match in subject_sync.PROJECTION_RE.finditer(text):
            key_in_file = (match.group("subject"), match.group("field"))
            if key_in_file in seen_in_file:
                duplicate_blocks.append(f"{rel(path)}::{key_in_file[0]}.{key_in_file[1]}")
            seen_in_file.add(key_in_file)
            discovered_blocks.add((rel(path), match.group("subject"), match.group("field")))

    unregistered = sorted(discovered_blocks - registered_blocks)
    missing_blocks = sorted(registered_blocks - discovered_blocks)
    if duplicate_blocks:
        state.fail(f"duplicate DOC-SUBJECT block(s): {', '.join(duplicate_blocks[:12])}")
    elif unregistered:
        sample = [f"{path}::{subject}.{field}" for path, subject, field in unregistered[:12]]
        state.fail(f"unregistered DOC-SUBJECT block(s): {', '.join(sample)}")
    elif missing_blocks:
        sample = [f"{path}::{subject}.{field}" for path, subject, field in missing_blocks[:12]]
        state.fail(f"registered projection block(s) not discovered: {', '.join(sample)}")
    else:
        state.ok()

    raw_required = manifest.get("required_projection_slots", [])
    if not isinstance(raw_required, list):
        state.fail("required_projection_slots must be a list")
        return
    required: set[tuple[str, str, str]] = set()
    for item in raw_required:
        if not isinstance(item, dict):
            state.fail("required_projection_slots entries must be objects")
            return
        try:
            required.add((str(item["path"]), str(item["subject"]), str(item["field"])))
        except KeyError as exc:
            state.fail(f"required_projection_slots entry missing key: {exc}")
            return
    missing_required = sorted(required - registered_blocks)
    if missing_required:
        sample = [f"{path}::{subject}.{field}" for path, subject, field in missing_required[:12]]
        state.fail(f"required projection slot(s) missing from registry: {', '.join(sample)}")
    else:
        state.ok()


def main() -> int:
    state = CheckState()
    try:
        manifest = load_manifest()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"doc tree completeness check failed: {exc}", file=sys.stderr)
        return 2

    check_required_paths(state, manifest)
    check_surface_manifests(state, manifest)
    check_subject_projection_graph(state, manifest)

    if state.failures:
        print(f"doc tree completeness check failed: {len(state.failures)} issue(s)")
        for failure in state.failures[:30]:
            print(f"  - {failure}")
        if len(state.failures) > 30:
            print(f"  ... {len(state.failures) - 30} more")
        return 1

    print(
        "doc tree completeness check passed: "
        f"{state.checks} structural checks, "
        f"{len(sorted_docs_top_level_files())} docs top-level files, "
        f"{len(sorted_project_book_docs())} project-book docs, "
        f"{len(sorted_research_archive_dirs())} research archive dirs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
