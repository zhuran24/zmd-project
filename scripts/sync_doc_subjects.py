#!/usr/bin/env python3
"""Synchronize project knowledge subjects and projections.

The project knowledge tree uses a subject/projection model inspired by the CC
memory instance/projection transclusion scheme:

- subject fields live in docs/subjects/*.md;
- projection blocks live in concrete docs and memory nodes;
- cc_context/knowledge/PROJECT_SUBJECT_PROJECTIONS.json declares every projection;
- --check fails on drift;
- --sync copies subject fields to all projections;
- --absorb updates a subject field from an intentionally edited projection,
  then fans that subject change back out.

Projection-start markers carry the sha256 of the subject field that generated
that block. That checksum lets --absorb distinguish "projection intentionally
edited from the latest subject" from "subject changed and projection is stale".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "cc_context" / "knowledge" / "PROJECT_SUBJECT_PROJECTIONS.json"

FIELD_RE = re.compile(
    r"<!--\s*SUBJECT-FIELD:(?P<field>[A-Za-z0-9_.-]+)\s+START\s*-->\n"
    r"(?P<body>.*?)"
    r"\n<!--\s*SUBJECT-FIELD:(?P=field)\s+END\s*-->",
    re.DOTALL,
)

PROJECTION_RE = re.compile(
    r"(?P<start><!--\s*DOC-SUBJECT:(?P<subject>[A-Za-z0-9_.-]+)\s+"
    r"FIELD:(?P<field>[A-Za-z0-9_.-]+)\s+START(?:\s+sha256:(?P<sha>[0-9a-f]{64}))?\s*-->)\n"
    r"(?P<body>.*?)"
    r"\n(?P<end><!--\s*DOC-SUBJECT:(?P=subject)\s+FIELD:(?P=field)\s+END\s*-->)",
    re.DOTALL,
)


@dataclass(frozen=True)
class SubjectField:
    subject: str
    field: str
    path: Path
    body: str

    @property
    def sha256(self) -> str:
        return hash_text(self.body)


@dataclass(frozen=True)
class ProjectionSpec:
    path: Path
    subject: str
    field: str
    purpose: str


@dataclass(frozen=True)
class ProjectionBlock:
    spec: ProjectionSpec
    body: str
    marker_sha: str | None
    body_sha: str
    start: int
    end: int


@dataclass(frozen=True)
class Drift:
    projection: ProjectionBlock
    subject_field: SubjectField
    reason: str


class SubjectSyncError(RuntimeError):
    pass


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def load_registry(path: Path = REGISTRY_PATH) -> tuple[dict[str, Path], list[ProjectionSpec]]:
    if not path.exists():
        raise SubjectSyncError(f"registry not found: {rel(path)}")
    registry = json.loads(read_text(path))
    if registry.get("schema_version") != 1:
        raise SubjectSyncError("cc_context/knowledge/PROJECT_SUBJECT_PROJECTIONS.json schema_version must be 1")

    subjects: dict[str, Path] = {}
    for subject_id, info in registry.get("subjects", {}).items():
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", subject_id):
            raise SubjectSyncError(f"invalid subject id: {subject_id!r}")
        subject_path = REPO_ROOT / info["path"]
        if not subject_path.exists():
            raise SubjectSyncError(f"subject path for {subject_id} not found: {info['path']}")
        subjects[subject_id] = subject_path

    projections: list[ProjectionSpec] = []
    seen_slots: set[tuple[str, str, str]] = set()
    for raw in registry.get("projections", []):
        subject = raw["subject"]
        if subject not in subjects:
            raise SubjectSyncError(f"projection references unknown subject: {subject}")
        field = raw["field"]
        projection_path = REPO_ROOT / raw["path"]
        if not projection_path.exists():
            raise SubjectSyncError(f"projection target not found: {raw['path']}")
        slot_key = (projection_path.as_posix(), subject, field)
        if slot_key in seen_slots:
            raise SubjectSyncError(f"duplicate projection slot in registry: {raw['path']} {subject}.{field}")
        seen_slots.add(slot_key)
        projections.append(
            ProjectionSpec(
                path=projection_path,
                subject=subject,
                field=field,
                purpose=raw.get("purpose", ""),
            )
        )
    return subjects, projections


def load_subject_fields(subjects: dict[str, Path]) -> dict[tuple[str, str], SubjectField]:
    fields: dict[tuple[str, str], SubjectField] = {}
    for subject_id, path in subjects.items():
        text = read_text(path)
        matches = list(FIELD_RE.finditer(text))
        if not matches:
            raise SubjectSyncError(f"subject has no SUBJECT-FIELD blocks: {rel(path)}")
        for match in matches:
            field_id = match.group("field")
            key = (subject_id, field_id)
            if key in fields:
                raise SubjectSyncError(f"duplicate field {subject_id}.{field_id} in {rel(path)}")
            body = match.group("body")
            if body.strip() == "":
                raise SubjectSyncError(f"empty field {subject_id}.{field_id} in {rel(path)}")
            fields[key] = SubjectField(subject_id, field_id, path, body)
    return fields


def find_projection_block(spec: ProjectionSpec) -> ProjectionBlock:
    text = read_text(spec.path)
    matches = [
        match
        for match in PROJECTION_RE.finditer(text)
        if match.group("subject") == spec.subject and match.group("field") == spec.field
    ]
    if not matches:
        raise SubjectSyncError(
            f"projection block missing: {rel(spec.path)} :: {spec.subject}.{spec.field}"
        )
    if len(matches) > 1:
        raise SubjectSyncError(
            f"projection block appears {len(matches)} times: {rel(spec.path)} :: {spec.subject}.{spec.field}"
        )
    match = matches[0]
    body = match.group("body")
    return ProjectionBlock(
        spec=spec,
        body=body,
        marker_sha=match.group("sha"),
        body_sha=hash_text(body),
        start=match.start(),
        end=match.end(),
    )


def render_projection(subject: str, field: str, body: str) -> str:
    sha = hash_text(body)
    return (
        f"<!-- DOC-SUBJECT:{subject} FIELD:{field} START sha256:{sha} -->\n"
        f"{body}\n"
        f"<!-- DOC-SUBJECT:{subject} FIELD:{field} END -->"
    )


def replace_one_projection(text: str, block: ProjectionBlock, subject_field: SubjectField) -> str:
    rendered = render_projection(block.spec.subject, block.spec.field, subject_field.body)
    return text[: block.start] + rendered + text[block.end :]


def collect_drifts(
    projections: Iterable[ProjectionSpec],
    fields: dict[tuple[str, str], SubjectField],
) -> list[Drift]:
    drifts: list[Drift] = []
    for spec in projections:
        field = fields.get((spec.subject, spec.field))
        if field is None:
            raise SubjectSyncError(f"registered projection references missing field: {spec.subject}.{spec.field}")
        block = find_projection_block(spec)
        reasons = []
        if block.body != field.body:
            reasons.append("body differs")
        if block.marker_sha != field.sha256:
            marker = block.marker_sha or "<missing>"
            reasons.append(f"marker sha {marker} != subject sha {field.sha256}")
        if reasons:
            drifts.append(Drift(block, field, "; ".join(reasons)))
    return drifts


def sync_projections(
    projections: Iterable[ProjectionSpec],
    fields: dict[tuple[str, str], SubjectField],
) -> list[str]:
    changed: list[str] = []
    by_path: dict[Path, list[tuple[ProjectionBlock, SubjectField]]] = {}
    for spec in projections:
        field = fields[(spec.subject, spec.field)]
        block = find_projection_block(spec)
        if block.body != field.body or block.marker_sha != field.sha256:
            by_path.setdefault(spec.path, []).append((block, field))

    for path, replacements in by_path.items():
        text = read_text(path)
        # Replace from the end so earlier indexes remain stable.
        for block, field in sorted(replacements, key=lambda item: item[0].start, reverse=True):
            text = replace_one_projection(text, block, field)
        write_text(path, text)
        changed.append(rel(path))
    return sorted(changed)


def replace_subject_field(subject_field: SubjectField, new_body: str) -> None:
    text = read_text(subject_field.path)

    def repl(match: re.Match[str]) -> str:
        if match.group("field") != subject_field.field:
            return match.group(0)
        return (
            f"<!-- SUBJECT-FIELD:{subject_field.field} START -->\n"
            f"{new_body}\n"
            f"<!-- SUBJECT-FIELD:{subject_field.field} END -->"
        )

    new_text, count = FIELD_RE.subn(repl, text)
    if count == 0:
        raise SubjectSyncError(f"could not replace subject field: {subject_field.subject}.{subject_field.field}")
    write_text(subject_field.path, new_text)


def absorb_projection_edits(
    projections: Iterable[ProjectionSpec],
    fields: dict[tuple[str, str], SubjectField],
) -> list[str]:
    candidates: dict[tuple[str, str], dict[str, ProjectionBlock]] = {}
    stale_or_ambiguous: list[str] = []

    for spec in projections:
        field = fields[(spec.subject, spec.field)]
        block = find_projection_block(spec)
        if block.body == field.body and block.marker_sha == field.sha256:
            continue

        if block.marker_sha == field.sha256 and block.body != field.body:
            # Projection was edited from a block generated by the current subject.
            candidates.setdefault((spec.subject, spec.field), {})[block.body] = block
            continue

        stale_or_ambiguous.append(
            f"{rel(spec.path)} :: {spec.subject}.{spec.field} ({block.marker_sha or '<missing>'} -> {field.sha256}; body sha {block.body_sha})"
        )

    if stale_or_ambiguous:
        details = "\n  ".join(stale_or_ambiguous[:12])
        raise SubjectSyncError(
            "cannot absorb stale or ambiguous projection drift; run --sync if the subject changed, "
            "or edit from a freshly synced projection first:\n  " + details
        )

    changed_fields: list[str] = []
    for key, body_to_block in sorted(candidates.items()):
        if len(body_to_block) != 1:
            examples = ", ".join(sorted(hash_text(body)[:12] for body in body_to_block))
            raise SubjectSyncError(f"conflicting projection edits for {key[0]}.{key[1]}: {examples}")
        new_body = next(iter(body_to_block))
        field = fields[key]
        replace_subject_field(field, new_body)
        changed_fields.append(f"{key[0]}.{key[1]}")
    return changed_fields


def cmd_check() -> int:
    subjects, projections = load_registry()
    fields = load_subject_fields(subjects)
    drifts = collect_drifts(projections, fields)
    if not drifts:
        print(
            f"doc subject projection check passed: {len(subjects)} subjects, "
            f"{len(fields)} fields, {len(projections)} projections"
        )
        return 0

    print(f"doc subject projection check failed: {len(drifts)} drift(s)")
    for drift in drifts[:20]:
        print(
            f"  {rel(drift.projection.spec.path)} :: "
            f"{drift.projection.spec.subject}.{drift.projection.spec.field}: {drift.reason}"
        )
    if len(drifts) > 20:
        print(f"  ... {len(drifts) - 20} more")
    print("Run `python scripts/sync_doc_subjects.py --sync` after subject edits, or `--absorb` after intentional projection edits.")
    return 1


def cmd_sync() -> int:
    subjects, projections = load_registry()
    fields = load_subject_fields(subjects)
    changed = sync_projections(projections, fields)
    if changed:
        print("synced projections:")
        for path in changed:
            print(f"  {path}")
    else:
        print("all projections already synced")
    return 0


def cmd_absorb() -> int:
    subjects, projections = load_registry()
    fields = load_subject_fields(subjects)
    changed_fields = absorb_projection_edits(projections, fields)
    if changed_fields:
        print("absorbed projection edits into subjects:")
        for field in changed_fields:
            print(f"  {field}")
        # Reload fields after subject writes, then fan out updated subject values.
        fields = load_subject_fields(subjects)
        changed_paths = sync_projections(projections, fields)
        for path in changed_paths:
            print(f"  synced {path}")
    else:
        print("no projection edits to absorb")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="fail if any projection differs from its subject field")
    group.add_argument("--sync", action="store_true", help="rewrite projection blocks from subject fields")
    group.add_argument("--absorb", action="store_true", help="absorb intentional projection edits into subject fields, then sync")
    args = parser.parse_args(argv)

    try:
        if args.check:
            return cmd_check()
        if args.sync:
            return cmd_sync()
        if args.absorb:
            return cmd_absorb()
        raise AssertionError("unreachable")
    except SubjectSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
