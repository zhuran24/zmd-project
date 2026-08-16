#!/usr/bin/env python3
"""Batch-1 developer tooling for the rule-system redesign line.

This module is deliberately outside ``src`` and ``scripts``.  It builds and
checks non-authoritative L2/L3 projections without entering the certified TCB,
changing canonical bytes, or pinning the canonical schema.  All project JSON
inputs are read with ``src.io.strict_json`` exact-decimal semantics.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.strict_json import load_strict_json_exact_decimal  # noqa: E402


DERIVED_ROOT = ROOT / "rules" / "derived"
ENTRY_DIR = DERIVED_ROOT / "entries"
ENTRY_SCHEMA_PATH = DERIVED_ROOT / "derived_rule.schema.json"
MANIFEST_PATH = DERIVED_ROOT / "manifest.json"
RULING_INDEX_PATH = DERIVED_ROOT / "ruling_index.jsonl"
FACILITY_GAP_PATH = DERIVED_ROOT / "facility_template_gap.json"
CANONICAL_PATH = ROOT / "rules" / "canonical_rules.json"
VENDORED_ENTITY_PATH = ROOT / "third_party_snapshots" / "industrial_planner" / "entity-definition.master.ts"
VENDORED_METADATA_PATH = ROOT / "third_party_snapshots" / "industrial_planner" / "SOURCE_METADATA.json"
MAPPING_REGISTRY_PATH = ROOT / "src" / "adapters" / "industrial_planner" / "mapping_registry.py"
OPEN_DEBT_LEDGER_PATH = (
    ROOT
    / "docs"
    / "research"
    / "rule_system_redesign_20260807"
    / "batch0_20260815"
    / "OPEN_DEBT_LEDGER.md"
)

VIEW_ROOT = ROOT / "docs" / "generated" / "rule_system"
VIEW_PATHS = {
    "V1": VIEW_ROOT / "V1_ENTITY_PARAMETERS.json",
    "V2": VIEW_ROOT / "V2_PARAMETER_REVERSE_INDEX.json",
    "V3": VIEW_ROOT / "V3_ENTRY_PREDICATE_MATRIX.json",
    "V4": VIEW_ROOT / "V4_AUDIT_LEDGER_PROJECTION.json",
    "V5": VIEW_ROOT / "V5_CAPABILITY_COVERAGE.json",
    "V6": VIEW_ROOT / "V6_DERIVATION_CLOSURE_GRAPH.json",
}

RULING_SOURCE_PATHS = (
    "docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md",
    "docs/research/canonical_batch_20260807/VERIFICATION_ANNEX_20260806.md",
)
RULING_PATTERN = re.compile(r"OWN-M[0-9]+|SIM-[A-Z][0-9]+|W-[A-Z][A-Z0-9-]*[0-9]+")
EXPECTED_OWN_GAPS = ("OWN-M25", "OWN-M26", "OWN-M28")
VENDORED_ENTITY_PATTERN = re.compile(r'^    id: "([^"]+)",$', re.MULTILINE)
TARGET_TYPE_PATTERN = re.compile(r'target_type_id="([^"]+)"')
DEBT_ROW_PATTERN = re.compile(r"^\| (OD-[A-Z0-9-]+) \| .*? \| ([A-Z_]+) \|", re.MULTILINE)

DERIVED_AUTHORITY = {
    "class": "NON_FROZEN_DERIVED",
    "statement": "非冻结派生件；不属于 canonical、freeze-ritual 或 owner authority；未经审查不得承重消费。",
}
VIEW_AUTHORITY = {
    "class": "GENERATED_VIEW_NON_AUTHORITY",
    "statement": "非权威生成视图；只作检索与差异定位；不得进入承重前提集，消费时必须回读 source_refs。",
}

FINGERPRINT_VERSION = "zmd-premise-fingerprint-v1"
RULING_INDEX_VERSION = "zmd-ruling-index-events-v1"
FACILITY_GAP_VERSION = "zmd-facility-template-gap-v1"
VIEW_VERSION = "zmd-rule-view-v1"

STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "UNREVIEWED": frozenset({"ACTIVE", "RETIRED", "SUPERSEDED"}),
    "ACTIVE": frozenset({"STALE", "RETIRED", "SUPERSEDED", "PROMOTED"}),
    "STALE": frozenset({"ACTIVE", "RETIRED", "SUPERSEDED", "PROMOTED"}),
    "RETIRED": frozenset(),
    "SUPERSEDED": frozenset(),
    "PROMOTED": frozenset(),
}


class RuleToolError(RuntimeError):
    """Fail-closed error raised by the batch-1 tooling."""


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _run_git(args: Sequence[str], *, root: Path = ROOT, allow_no_match: bool = False) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode == 1 and allow_no_match:
        return ""
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuleToolError(f"git {' '.join(args)} failed: {stderr}")
    return completed.stdout


def _strict_object(path: Path) -> dict[str, Any]:
    value = load_strict_json_exact_decimal(path)
    if not isinstance(value, dict):
        raise RuleToolError(f"{_relative(path)} root must be an object")
    return value


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def _fraction(value: Any) -> Fraction:
    if isinstance(value, bool):
        raise RuleToolError("booleans are not exact numbers")
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, Decimal):
        return Fraction(value)
    if isinstance(value, Mapping) and set(value) == {"exact_rational"}:
        raw = value["exact_rational"]
        if not isinstance(raw, str):
            raise RuleToolError("exact_rational must be a string")
        try:
            return Fraction(raw)
        except (ValueError, ZeroDivisionError) as exc:
            raise RuleToolError(f"invalid exact rational: {raw!r}") from exc
    raise RuleToolError(f"unsupported exact-number value: {value!r}")


def _normalize(value: Any) -> Any:
    """Return the D-21 canonical fingerprint representation.

    Dictionaries are key-sorted, lists preserve semantic order, strings are NFC
    with LF newlines, and all JSON numbers become reduced exact rationals.  An
    explicit ``{"exact_rational": "p/q"}`` object enters the same number path.
    """

    if isinstance(value, Mapping):
        if set(value) == {"exact_rational"}:
            rational = _fraction(value)
            return {"$number": f"{rational.numerator}/{rational.denominator}"}
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
        rational = _fraction(value)
        return {"$number": f"{rational.numerator}/{rational.denominator}"}
    if isinstance(value, str):
        return _normalize_text(value)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise RuleToolError("binary floats are forbidden; load JSON with exact_decimal semantics")
    raise RuleToolError(f"unsupported canonicalization value: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    normalized = _normalize(value)
    return (
        json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        rational = Fraction(value)
        return {"exact_rational": f"{rational.numerator}/{rational.denominator}"}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def pretty_json(value: Mapping[str, Any]) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, indent=2) + "\n"


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise RuleToolError(f"JSON pointer must start with '/': {pointer!r}")
    current = document
    for raw_part in pointer.split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if part not in current:
                raise RuleToolError(f"JSON pointer segment {part!r} is absent in {pointer!r}")
            current = current[part]
        elif isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError) as exc:
                raise RuleToolError(f"invalid list segment {part!r} in {pointer!r}") from exc
        else:
            raise RuleToolError(f"JSON pointer {pointer!r} descends through a scalar")
    return current


def _entry_by_id(entry_id: str, *, root: Path = ROOT) -> dict[str, Any]:
    path = root / "rules" / "derived" / "entries" / f"{entry_id}.json"
    if not path.is_file():
        raise RuleToolError(f"derived premise references missing entry: {_relative(path)}")
    return _strict_object(path)


def premise_material(entry: Mapping[str, Any], *, root: Path = ROOT) -> tuple[list[dict[str, Any]], list[str]]:
    raw_premises = entry.get("premises")
    if not isinstance(raw_premises, list):
        raise RuleToolError("entry.premises must be a list")

    material: list[dict[str, Any]] = []
    issues: list[str] = []
    refs_seen: set[str] = set()
    for index, premise in enumerate(raw_premises):
        if not isinstance(premise, Mapping):
            raise RuleToolError(f"premises[{index}] must be an object")
        kind = premise.get("kind")
        ref = premise.get("ref")
        if not isinstance(kind, str) or not isinstance(ref, str):
            raise RuleToolError(f"premises[{index}] requires string kind/ref")
        if ref in refs_seen:
            raise RuleToolError(f"duplicate premise ref: {ref}")
        refs_seen.add(ref)

        if kind == "source_value":
            source = premise.get("source")
            if not isinstance(source, Mapping):
                raise RuleToolError(f"source_value premise {ref!r} requires source object")
            source_path = source.get("path")
            pointer = source.get("pointer")
            if not isinstance(source_path, str) or not isinstance(pointer, str):
                raise RuleToolError(f"source_value premise {ref!r} requires source.path/source.pointer")
            source_document = load_strict_json_exact_decimal(root / source_path)
            current_value = resolve_json_pointer(source_document, pointer)
            if "value_at_derivation" not in premise:
                raise RuleToolError(f"source_value premise {ref!r} lacks value_at_derivation")
            declared_value = premise["value_at_derivation"]
            if _normalize(current_value) != _normalize(declared_value):
                issues.append(
                    f"{ref}: value_at_derivation={_normalize(declared_value)!r} "
                    f"does not match current source={_normalize(current_value)!r}"
                )
            material.append(
                {
                    "kind": kind,
                    "ref": ref,
                    "source": {"path": source_path, "pointer": pointer},
                    "current_value": current_value,
                }
            )
        elif kind == "assumption":
            statement = premise.get("statement")
            version = premise.get("assumption_version")
            if not isinstance(statement, str) or not statement:
                raise RuleToolError(f"assumption premise {ref!r} requires non-empty statement")
            if not isinstance(version, str) or not version:
                raise RuleToolError(f"assumption premise {ref!r} requires assumption_version")
            material.append(
                {
                    "kind": kind,
                    "ref": ref,
                    "statement": _normalize_text(statement),
                    "assumption_version": version,
                }
            )
        elif kind == "derived":
            entry_id = premise.get("entry_id")
            level = premise.get("level")
            if not isinstance(entry_id, str) or not isinstance(level, int):
                raise RuleToolError(f"derived premise {ref!r} requires entry_id and integer level")
            referenced = _entry_by_id(entry_id, root=root)
            if referenced.get("id") != entry_id:
                raise RuleToolError(f"derived premise {ref!r} resolved id mismatch")
            material.append(
                {
                    "kind": kind,
                    "ref": ref,
                    "entry_id": entry_id,
                    "level": level,
                    "premise_fingerprint": referenced.get("premise_fingerprint"),
                }
            )
        else:
            raise RuleToolError(f"unsupported premise kind {kind!r}")

    material.sort(key=lambda row: (str(row["kind"]), str(row["ref"])))
    return material, issues


def compute_premise_fingerprint(entry: Mapping[str, Any], *, root: Path = ROOT) -> str:
    material, _issues = premise_material(entry, root=root)
    payload = FINGERPRINT_VERSION.encode("utf-8") + b"\0" + canonical_bytes(material)
    return hashlib.sha256(payload).hexdigest()


def load_entry_schema(*, root: Path = ROOT) -> dict[str, Any]:
    path = root / "rules" / "derived" / "derived_rule.schema.json"
    schema = _strict_object(path)
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise RuleToolError(f"derived schema is invalid: {exc.message}") from exc
    return schema


def validate_entry(entry: Mapping[str, Any], *, root: Path = ROOT) -> None:
    schema = load_entry_schema(root=root)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(_json_safe(entry)),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise RuleToolError(f"derived entry schema failure at {location}: {first.message}")
    if entry.get("_authority") != DERIVED_AUTHORITY:
        raise RuleToolError("derived entry has the wrong _authority header")


def entry_currency(entry: Mapping[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    validate_entry(entry, root=root)
    _material, value_issues = premise_material(entry, root=root)
    computed = compute_premise_fingerprint(entry, root=root)
    stored = entry.get("premise_fingerprint")
    issues = list(value_issues)
    if stored != computed:
        issues.append(f"stored premise_fingerprint {stored!r} != computed {computed!r}")
    stale = bool(issues)
    consumers = entry.get("consumers")
    blocking = stale and entry.get("status") in {"ACTIVE", "STALE"} and isinstance(consumers, list) and bool(consumers)
    return {
        "id": entry.get("id"),
        "status": entry.get("status"),
        "stored_fingerprint": stored,
        "computed_fingerprint": computed,
        "stale": stale,
        "blocking": blocking,
        "issues": issues,
    }


def transition_allowed(before: str, after: str) -> bool:
    return after in STATUS_TRANSITIONS.get(before, frozenset())


def _derived_files(*, root: Path = ROOT) -> tuple[Path, ...]:
    derived_root = root / "rules" / "derived"
    if not derived_root.is_dir():
        raise RuleToolError("rules/derived directory is missing")
    return tuple(sorted(path for path in derived_root.rglob("*") if path.is_file()))


def check_authority_headers(*, root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for path in _derived_files(root=root):
        relative = path.relative_to(root).as_posix()
        if path.suffix == ".md":
            first_line = path.read_text(encoding="utf-8").splitlines()[0] if path.stat().st_size else ""
            if "_authority: NON_FROZEN_DERIVED" not in first_line or "非冻结派生件" not in first_line:
                issues.append(f"{relative}: Markdown header is missing NON_FROZEN_DERIVED/非冻结派生件")
        elif path.suffix == ".json":
            payload = _strict_object(path)
            if payload.get("_authority") != DERIVED_AUTHORITY:
                issues.append(f"{relative}: JSON _authority header mismatch")
        elif path.suffix == ".jsonl":
            lines = path.read_text(encoding="utf-8").splitlines()
            if not lines:
                issues.append(f"{relative}: empty JSONL")
                continue
            try:
                header = json.loads(lines[0])
            except json.JSONDecodeError as exc:
                issues.append(f"{relative}: invalid JSONL header: {exc}")
                continue
            if header.get("_authority") != DERIVED_AUTHORITY:
                issues.append(f"{relative}: JSONL first-record _authority mismatch")
        else:
            issues.append(f"{relative}: unsupported file type inside rules/derived")
    return issues


def _entry_paths(*, root: Path = ROOT) -> tuple[Path, ...]:
    entry_dir = root / "rules" / "derived" / "entries"
    return tuple(sorted(entry_dir.glob("*.json")))


def load_entries(*, root: Path = ROOT) -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in _entry_paths(root=root):
        entry = _strict_object(path)
        validate_entry(entry, root=root)
        entry_id = entry.get("id")
        if not isinstance(entry_id, str):
            raise RuleToolError(f"{_relative(path)} has no string id")
        if path.name != f"{entry_id}.json":
            raise RuleToolError(f"{_relative(path)} violates one-entry-per-file naming")
        if entry_id in seen:
            raise RuleToolError(f"duplicate derived entry id: {entry_id}")
        seen.add(entry_id)
        entries.append(entry)
    return tuple(entries)


def check_derived_scaffold(*, root: Path = ROOT) -> dict[str, Any]:
    authority_issues = check_authority_headers(root=root)
    manifest = _strict_object(root / "rules" / "derived" / "manifest.json")
    if manifest.get("_authority") != DERIVED_AUTHORITY:
        authority_issues.append("manifest authority mismatch")
    if manifest.get("canonical_schema_pin") != "OUT_OF_SCOPE_BATCH_2_OWNER_DECISION_PENDING":
        authority_issues.append("manifest must keep canonical schema pin out of batch 1")
    package = manifest.get("package_declaration")
    if not isinstance(package, Mapping):
        authority_issues.append("manifest.package_declaration is missing")
    else:
        if package.get("script_connection_status") != "DEFERRED_OPEN_DEBT":
            authority_issues.append("package script connection must remain deferred")
        if package.get("debt_id") != "OD-B1-PACKAGE-01":
            authority_issues.append("package declaration must point to OD-B1-PACKAGE-01")

    entries = load_entries(root=root)
    currencies = [entry_currency(entry, root=root) for entry in entries]
    blocking = [result for result in currencies if result["blocking"]]
    return {
        "authority_issues": authority_issues,
        "entry_count": len(entries),
        "currency": currencies,
        "blocking_currency": blocking,
        "ok": not authority_issues and not blocking,
    }


def _ruling_family(identifier: str) -> str:
    if identifier.startswith("OWN-M"):
        return "OWN-M"
    if identifier.startswith("SIM-"):
        return identifier.split("-", 1)[0] + "-" + identifier.split("-", 1)[1][0]
    return "W"


def _ruling_sort_key(identifier: str) -> tuple[str, int, str]:
    match = re.search(r"([0-9]+)$", identifier)
    number = int(match.group(1)) if match else 0
    return (_ruling_family(identifier), number, identifier)


def extract_ruling_occurrences(*, root: Path = ROOT) -> dict[str, list[dict[str, Any]]]:
    output = _run_git(
        ["grep", "-n", "-E", RULING_PATTERN.pattern, "--", *RULING_SOURCE_PATHS],
        root=root,
    )
    occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw_line in output.splitlines():
        try:
            path, line_number, text = raw_line.split(":", 2)
        except ValueError as exc:
            raise RuleToolError(f"git grep emitted malformed line: {raw_line!r}") from exc
        for match in RULING_PATTERN.finditer(text):
            occurrences[match.group(0)].append(
                {
                    "path": path,
                    "line": int(line_number),
                    "context": _normalize_text(text.strip()),
                }
            )
    return {key: occurrences[key] for key in sorted(occurrences, key=_ruling_sort_key)}


def render_initial_ruling_index(*, root: Path = ROOT) -> str:
    occurrences = extract_ruling_occurrences(root=root)
    header = {
        "_authority": DERIVED_AUTHORITY,
        "record_type": "HEADER",
        "format": RULING_INDEX_VERSION,
        "append_only": True,
        "source_paths": list(RULING_SOURCE_PATHS),
        "count_method": "git grep over the full tracked source paths; rg is advisory only because .rgignore can project files out",
    }
    records: list[dict[str, Any]] = [header]
    for identifier, rows in occurrences.items():
        first_seen = {"path": rows[0]["path"], "line": rows[0]["line"]}
        records.append(
            {
                "record_type": "IDENTIFIER_EVENT",
                "event": "DISCOVERED",
                "id": identifier,
                "family": _ruling_family(identifier),
                "occurrence_count_at_event": len(rows),
                "first_seen": first_seen,
            }
        )
    for gap in EXPECTED_OWN_GAPS:
        records.append(
            {
                "record_type": "GAP_EVENT",
                "event": "EXPECTED_GAP_CONFIRMED",
                "id": gap,
                "family": "OWN-M",
                "status": "MISSING_FROM_TRACKED_CORPUS",
                "checked_by": "git grep",
                "source_paths": list(RULING_SOURCE_PATHS),
            }
        )
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=False, separators=(",", ":")) + "\n"
        for record in records
    )


def parse_ruling_index(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise RuleToolError(f"ruling index line {line_number} is invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise RuleToolError(f"ruling index line {line_number} must be an object")
        records.append(record)
    if not records or records[0].get("record_type") != "HEADER":
        raise RuleToolError("ruling index must start with a HEADER event")
    if records[0].get("_authority") != DERIVED_AUTHORITY:
        raise RuleToolError("ruling index header has the wrong _authority")
    return records


def active_ruling_ids(records: Sequence[Mapping[str, Any]]) -> set[str]:
    active: dict[str, bool] = {}
    for record in records:
        if record.get("record_type") != "IDENTIFIER_EVENT":
            continue
        identifier = record.get("id")
        event = record.get("event")
        if not isinstance(identifier, str):
            raise RuleToolError("identifier event lacks string id")
        if event in {"DISCOVERED", "RESTORED"}:
            active[identifier] = True
        elif event == "REMOVED_FROM_CORPUS":
            active[identifier] = False
        else:
            raise RuleToolError(f"unsupported ruling-index event: {event!r}")
    return {identifier for identifier, is_active in active.items() if is_active}


def refresh_ruling_index_text(existing_text: str, *, root: Path = ROOT) -> str:
    records = parse_ruling_index(existing_text)
    active = active_ruling_ids(records)
    current = set(extract_ruling_occurrences(root=root))
    additions: list[dict[str, Any]] = []
    occurrences = extract_ruling_occurrences(root=root)
    for identifier in sorted(current - active, key=_ruling_sort_key):
        rows = occurrences[identifier]
        first_seen = {"path": rows[0]["path"], "line": rows[0]["line"]}
        additions.append(
            {
                "record_type": "IDENTIFIER_EVENT",
                "event": "RESTORED" if any(record.get("id") == identifier for record in records) else "DISCOVERED",
                "id": identifier,
                "family": _ruling_family(identifier),
                "occurrence_count_at_event": len(rows),
                "first_seen": first_seen,
            }
        )
    for identifier in sorted(active - current, key=_ruling_sort_key):
        additions.append(
            {
                "record_type": "IDENTIFIER_EVENT",
                "event": "REMOVED_FROM_CORPUS",
                "id": identifier,
                "family": _ruling_family(identifier),
            }
        )
    if not additions:
        return existing_text
    suffix = "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in additions
    )
    return existing_text + suffix


def check_ruling_index(*, root: Path = ROOT) -> dict[str, Any]:
    text = (root / "rules" / "derived" / "ruling_index.jsonl").read_text(encoding="utf-8")
    records = parse_ruling_index(text)
    active = active_ruling_ids(records)
    current_occurrences = extract_ruling_occurrences(root=root)
    current = set(current_occurrences)
    gap_records = {
        record.get("id")
        for record in records
        if record.get("record_type") == "GAP_EVENT"
        and record.get("event") == "EXPECTED_GAP_CONFIRMED"
    }
    missing_from_index = sorted(current - active, key=_ruling_sort_key)
    stale_active = sorted(active - current, key=_ruling_sort_key)
    missing_gap_records = sorted(set(EXPECTED_OWN_GAPS) - gap_records)
    gaps_that_now_exist = sorted(set(EXPECTED_OWN_GAPS) & current)
    family_counts: dict[str, int] = defaultdict(int)
    for identifier in current:
        family_counts[_ruling_family(identifier)] += 1
    return {
        "source_paths": list(RULING_SOURCE_PATHS),
        "git_grep_distinct_count": len(current),
        "index_active_count": len(active),
        "family_counts": dict(sorted(family_counts.items())),
        "own_ids": sorted((item for item in current if item.startswith("OWN-M")), key=_ruling_sort_key),
        "expected_gaps": list(EXPECTED_OWN_GAPS),
        "missing_from_index": missing_from_index,
        "stale_active": stale_active,
        "missing_gap_records": missing_gap_records,
        "gaps_that_now_exist": gaps_that_now_exist,
        "ok": not (missing_from_index or stale_active or missing_gap_records or gaps_that_now_exist),
    }


def _vendored_entity_ids(*, root: Path = ROOT) -> list[str]:
    text = (root / VENDORED_ENTITY_PATH.relative_to(ROOT)).read_text(encoding="utf-8")
    ids = VENDORED_ENTITY_PATTERN.findall(text)
    if len(ids) != len(set(ids)):
        raise RuleToolError("vendored IndustrialPlanner registry contains duplicate top-level entity ids")
    return sorted(ids)


def _explicit_adapter_target_ids(*, root: Path = ROOT) -> list[str]:
    text = (root / MAPPING_REGISTRY_PATH.relative_to(ROOT)).read_text(encoding="utf-8")
    return sorted(set(TARGET_TYPE_PATTERN.findall(text)))


def render_facility_template_gap(*, root: Path = ROOT) -> str:
    canonical = _strict_object(root / "rules" / "canonical_rules.json")
    templates = canonical.get("facility_templates")
    if not isinstance(templates, Mapping):
        raise RuleToolError("canonical facility_templates must be an object")
    template_ids = sorted(str(key) for key in templates)
    vendored_ids = _vendored_entity_ids(root=root)
    adapter_targets = _explicit_adapter_target_ids(root=root)
    directly_registered = sorted(set(vendored_ids) & (set(template_ids) | set(adapter_targets)))
    gaps = sorted(set(vendored_ids) - set(directly_registered))
    metadata = _strict_object(root / "third_party_snapshots" / "industrial_planner" / "SOURCE_METADATA.json")
    primary = metadata.get("files", {}).get("entity-definition.master.ts", {})
    payload = {
        "_authority": DERIVED_AUTHORITY,
        "format": FACILITY_GAP_VERSION,
        "comparison": "vendored top-level entity ids minus canonical facility-template ids and explicit adapter target ids",
        "interpretation_boundary": (
            "NOT_DIRECTLY_REGISTERED is a candidate coverage gap, not proof that the game capability is impossible "
            "to express. Generic template, routing-state, or future mapping coverage requires separate review."
        ),
        "sources": {
            "vendored_registry": "third_party_snapshots/industrial_planner/entity-definition.master.ts",
            "vendored_commit": primary.get("commit"),
            "facility_templates": "rules/canonical_rules.json#/facility_templates",
            "adapter_targets": "src/adapters/industrial_planner/mapping_registry.py::_FACILITY_MAPPINGS",
        },
        "counts": {
            "vendored_entity_ids": len(vendored_ids),
            "facility_template_ids": len(template_ids),
            "explicit_adapter_target_ids": len(adapter_targets),
            "directly_registered_vendored_ids": len(directly_registered),
            "not_directly_registered": len(gaps),
        },
        "facility_template_ids": template_ids,
        "explicit_adapter_target_ids": adapter_targets,
        "directly_registered_vendored_ids": directly_registered,
        "not_directly_registered": gaps,
    }
    return pretty_json(payload)


def check_facility_template_gap(*, root: Path = ROOT) -> dict[str, Any]:
    path = root / "rules" / "derived" / "facility_template_gap.json"
    expected = render_facility_template_gap(root=root)
    actual = path.read_text(encoding="utf-8")
    payload = _strict_object(path)
    gaps = payload.get("not_directly_registered")
    gap_set = set(gaps) if isinstance(gaps, list) else set()
    required_hits = {"item_log_admission", "item_pipe_admission"}
    return {
        "byte_current": actual == expected,
        "required_hits": sorted(required_hits),
        "missing_required_hits": sorted(required_hits - gap_set),
        "gap_count": len(gap_set),
        "ok": actual == expected and required_hits <= gap_set,
    }


def _flatten_scalars(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key in sorted(value):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            yield from _flatten_scalars(value[key], f"{pointer}/{escaped}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _flatten_scalars(item, f"{pointer}/{index}")
    else:
        yield pointer, value


def _display_value(value: Any) -> Any:
    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
        rational = _fraction(value)
        return {"exact_rational": f"{rational.numerator}/{rational.denominator}"}
    return _json_safe(value)


def _source_cell(path: str, pointer: str, value: Any) -> dict[str, Any]:
    return {
        "value": _display_value(value),
        "source": f"{path}#{pointer}",
    }


def _view_base(view_id: str, title: str, source_refs: Sequence[str]) -> dict[str, Any]:
    return {
        "_authority": VIEW_AUTHORITY,
        "format": VIEW_VERSION,
        "view_id": view_id,
        "title": title,
        "source_refs": list(source_refs),
        "currency": {
            "generator": "devtools/rule_system_tooling.py",
            "rule": "tracked bytes must equal a cold regeneration",
        },
    }


def render_view_v1(*, root: Path = ROOT) -> str:
    canonical = _strict_object(root / "rules" / "canonical_rules.json")
    templates = canonical["facility_templates"]
    expected_fields = (
        "dimensions",
        "rotatable",
        "needs_power",
        "is_solid_z",
        "port_rule",
        "placement_rule",
        "power_coverage_radius",
        "core_limits",
        "physical_input_ports",
        "physical_output_ports",
        "buffer_slots",
        "slot_capacity",
        "cycle_seconds",
    )
    rows: list[dict[str, Any]] = []
    total_missing = 0
    for template_id in sorted(templates):
        template = templates[template_id]
        row: dict[str, Any] = {"entity": template_id, "fields": {}, "missing": []}
        for field in expected_fields:
            if field in template:
                row["fields"][field] = _source_cell(
                    "rules/canonical_rules.json",
                    f"/facility_templates/{template_id}/{field}",
                    template[field],
                )
            else:
                row["missing"].append(field)
        row["missing_count"] = {
            "value": len(row["missing"]),
            "source": "devtools/rule_system_tooling.py::render_view_v1(expected_fields - present_fields)",
        }
        total_missing += len(row["missing"])
        rows.append(row)
    payload = _view_base(
        "V1",
        "实体参数表（MISSING 显式计数）",
        ["rules/canonical_rules.json#/facility_templates"],
    )
    payload.update(
        {
            "rows": rows,
            "summary": {
                "entity_count": {
                    "value": len(rows),
                    "source": "rules/canonical_rules.json#/facility_templates (object key count)",
                },
                "missing_field_count": {
                    "value": total_missing,
                    "source": "devtools/rule_system_tooling.py::render_view_v1",
                },
            },
        }
    )
    return pretty_json(payload)


def _literal_code_refs(leaf_key: str, *, root: Path = ROOT) -> list[str]:
    output = _run_git(
        ["grep", "-n", "-F", leaf_key, "--", "src", "scripts", "devtools"],
        root=root,
        allow_no_match=True,
    )
    refs: list[str] = []
    for raw_line in output.splitlines():
        parts = raw_line.split(":", 2)
        if len(parts) >= 2:
            refs.append(f"{parts[0]}:{parts[1]}")
    return sorted(set(refs))[:3]


def _l2_premise_refs(entries: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        entry_id = str(entry.get("id"))
        premises = entry.get("premises")
        if not isinstance(premises, list):
            continue
        for premise in premises:
            if not isinstance(premise, Mapping) or premise.get("kind") != "source_value":
                continue
            source = premise.get("source")
            if not isinstance(source, Mapping):
                continue
            path = source.get("path")
            pointer = source.get("pointer")
            if isinstance(path, str) and isinstance(pointer, str):
                refs[f"{path}#{pointer}"].append(entry_id)
    return {key: sorted(set(value)) for key, value in refs.items()}


def render_view_v2(*, root: Path = ROOT) -> str:
    canonical = _strict_object(root / "rules" / "canonical_rules.json")
    entries = load_entries(root=root)
    l2_refs = _l2_premise_refs(entries)
    pointers = [
        "/globals/grid",
        "/globals/time",
        "/globals/logistics",
        "/globals/empty_rectangle",
        *(f"/facility_templates/{key}" for key in sorted(canonical["facility_templates"])),
        *(f"/production_targets/{key}" for key in sorted(canonical["production_targets"])),
    ]
    rows: list[dict[str, Any]] = []
    for pointer in pointers:
        value = resolve_json_pointer(canonical, pointer)
        source_ref = f"rules/canonical_rules.json#{pointer}"
        leaf_key = pointer.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
        aggregated_l2_refs = sorted(
            {
                entry_id
                for premise_ref, entry_ids in l2_refs.items()
                if premise_ref == source_ref or premise_ref.startswith(f"{source_ref}/")
                for entry_id in entry_ids
            }
        )
        rows.append(
            {
                "parameter_family": pointer.lstrip("/").replace("/", "."),
                "value": _display_value(value),
                "canonical_source": source_ref,
                "l2_premise_refs": aggregated_l2_refs,
                "frozen_artifact_refs": [],
                "code_call_sites_non_exhaustive": _literal_code_refs(leaf_key, root=root),
            }
        )
    payload = _view_base(
        "V2",
        "参数反向索引",
        [
            "rules/canonical_rules.json#/globals",
            "rules/canonical_rules.json#/facility_templates",
            "rules/canonical_rules.json#/production_targets",
            "rules/derived/entries/*.json#/premises",
        ],
    )
    payload.update(
        {
            "columns": {
                "parameter": "参数路径",
                "canonical_source": "canonical 真源",
                "l2_premise_refs": "L2 前提引用",
                "frozen_artifact_refs": "冻结工件引用（仅显式登记）",
                "code_call_sites_non_exhaustive": (
                    "代码 call site（非完备；仅 git grep 字面叶键扫描；拼接、别名、动态访问和 .rgignore 投影都可能漏）"
                ),
            },
            "completeness_boundary": (
                "代码列明确非完备，不能被消费为全仓引用者全集；当前可机械闭合的列只有 canonical、L2 和显式冻结工件登记。"
            ),
            "rows": rows,
            "summary": {
                "parameter_row_count": {
                    "value": len(rows),
                    "source": "devtools/rule_system_tooling.py::render_view_v2(selected canonical top sections)",
                }
            },
        }
    )
    return pretty_json(payload)


def render_view_v3(*, root: Path = ROOT) -> str:
    canonical = _strict_object(root / "rules" / "canonical_rules.json")
    semantics = canonical.get("semantics")
    if not isinstance(semantics, Mapping):
        raise RuleToolError("canonical semantics must be an object")
    entry_names = sorted(key for key in semantics if not str(key).startswith("_"))
    rows: list[dict[str, Any]] = []
    for name in entry_names:
        entry = semantics[name]
        declared = entry.get("predicate_status") if isinstance(entry, Mapping) else None
        rows.append(
            {
                "entry": name,
                "predicate_1": "NOT_ASSESSED",
                "predicate_2": "NOT_ASSESSED",
                "predicate_3": "NOT_ASSESSED",
                "predicate_4": "NOT_ASSESSED",
                "predicate_5": "NOT_ASSESSED",
                "predicate_6": "NOT_ASSESSED",
                "declared_predicate_status": declared if declared is not None else "MISSING",
                "source": f"rules/canonical_rules.json#/semantics/{name}",
            }
        )
    rows.append(
        {
            "entry": "axis_without_axiom",
            "predicate_1": "NOT_ASSESSED",
            "predicate_2": "NOT_ASSESSED",
            "predicate_3": "NOT_ASSESSED",
            "predicate_4": "NOT_ASSESSED",
            "predicate_5": "NOT_ASSESSED",
            "predicate_6": "NOT_ASSESSED",
            "declared_predicate_status": "GENERATED_SENTINEL_ROW",
            "source": "docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md#3.8",
        }
    )
    payload = _view_base(
        "V3",
        "条目－六谓词矩阵",
        ["rules/canonical_rules.json#/semantics", "docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md#3.8"],
    )
    payload.update(
        {
            "interpretation_boundary": (
                "批 1 只机械枚举条目与保留 axis_without_axiom 行；六谓词映射尚未裁定，全部 fail-closed 为 NOT_ASSESSED。"
            ),
            "rows": rows,
            "summary": {
                "semantic_entry_count": {
                    "value": len(entry_names),
                    "source": "rules/canonical_rules.json#/semantics (excluding underscore-prefixed metadata)",
                },
                "matrix_row_count_including_axis_without_axiom": {
                    "value": len(rows),
                    "source": "devtools/rule_system_tooling.py::render_view_v3",
                },
            },
        }
    )
    return pretty_json(payload)


def _open_debt_summary(*, root: Path = ROOT) -> tuple[dict[str, int], list[dict[str, str]]]:
    path = root / OPEN_DEBT_LEDGER_PATH.relative_to(ROOT)
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []
    counts: dict[str, int] = defaultdict(int)
    for debt_id, status in DEBT_ROW_PATTERN.findall(text):
        if any(row["id"] == debt_id for row in rows):
            continue
        rows.append({"id": debt_id, "status": status})
        counts[status] += 1
    return dict(sorted(counts.items())), rows


def render_view_v4(*, root: Path = ROOT) -> str:
    ruling = check_ruling_index(root=root)
    gap = _strict_object(root / "rules" / "derived" / "facility_template_gap.json")
    debt_counts, debts = _open_debt_summary(root=root)
    payload = _view_base(
        "V4",
        "孔／墙／界三类台账投影",
        [
            "rules/derived/ruling_index.jsonl",
            "rules/derived/facility_template_gap.json",
            "docs/research/rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md",
        ],
    )
    payload.update(
        {
            "ledgers": [
                {
                    "ledger": "孔审计",
                    "projection_status": "NOT_ESTABLISHED",
                    "row_count": {
                        "value": 0,
                        "source": "批 1 未建立孔审计机器台账；沿用现行审计仅是后续批 6 事项",
                    },
                    "rows": [],
                },
                {
                    "ledger": "墙审计 bootstrap 输入",
                    "projection_status": "INPUTS_ONLY_NO_VERDICT",
                    "row_count": {
                        "value": ruling["git_grep_distinct_count"] + len(gap["not_directly_registered"]),
                        "source": "rules/derived/ruling_index.jsonl + rules/derived/facility_template_gap.json",
                    },
                    "components": {
                        "ruling_ids": ruling["git_grep_distinct_count"],
                        "registry_candidate_gaps": len(gap["not_directly_registered"]),
                    },
                },
                {
                    "ledger": "界审计 bootstrap 输入",
                    "projection_status": "OPEN_DEBT_PROJECTION_ONLY",
                    "row_count": {
                        "value": len(debts),
                        "source": "docs/research/rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md (unique index rows)",
                    },
                    "status_counts": debt_counts,
                    "rows": debts,
                },
            ],
            "interpretation_boundary": (
                "V4 只投影可机械抽取的 bootstrap 输入与开放账，不产生墙/界/孔 verdict，也不把缺行解释为不存在。"
            ),
        }
    )
    return pretty_json(payload)


def render_view_v5(*, root: Path = ROOT) -> str:
    gap = _strict_object(root / "rules" / "derived" / "facility_template_gap.json")
    templates = set(gap["facility_template_ids"])
    aliases = set(gap["explicit_adapter_target_ids"])
    vendored = _vendored_entity_ids(root=root)
    buckets: dict[str, list[str]] = defaultdict(list)
    for entity_id in vendored:
        if entity_id in templates:
            state = "DIRECT_TEMPLATE_ID"
        elif entity_id in aliases:
            state = "MAPPED_BY_EXPLICIT_ADAPTER_TARGET"
        else:
            state = "NOT_DIRECTLY_REGISTERED"
        buckets[state].append(entity_id)
    counts = {state: len(ids) for state, ids in buckets.items()}
    counts["NOT_ASSESSED"] = len(vendored)
    payload = _view_base(
        "V5",
        "能力覆盖率表",
        [
            "third_party_snapshots/industrial_planner/entity-definition.master.ts",
            "rules/canonical_rules.json#/facility_templates",
            "src/adapters/industrial_planner/mapping_registry.py::_FACILITY_MAPPINGS",
        ],
    )
    payload.update(
        {
            "state_contract": {
                "DIRECT_TEMPLATE_ID": "vendored id 与 canonical template id 字面相同",
                "MAPPED_BY_EXPLICIT_ADAPTER_TARGET": "vendored id 被当前 adapter target 显式点名",
                "NOT_DIRECTLY_REGISTERED": "未被前两类直接登记；只是候选缺口",
                "NOT_ASSESSED": "模型可表达性未审；批 1 不作表达力 verdict",
            },
            "registration_buckets": {
                state: {
                    "capability_ids": ids,
                    "source": "third_party_snapshots/industrial_planner/entity-definition.master.ts",
                }
                for state, ids in sorted(buckets.items())
            },
            "model_expressibility": {
                "state": "NOT_ASSESSED",
                "capability_ids": vendored,
                "source": "批 1 只做直接登记差集，不产生模型表达力 verdict",
            },
            "summary": {
                "counts": {
                    key: {
                        "value": value,
                        "source": "devtools/rule_system_tooling.py::render_view_v5",
                    }
                    for key, value in sorted(counts.items())
                }
            },
            "required_batch1_hits": ["item_log_admission", "item_pipe_admission"],
            "interpretation_boundary": (
                "直接登记缺口不等于游戏能力不可表达；真正的四态表达力判定留给墙审计。"
            ),
        }
    )
    return pretty_json(payload)


def render_view_v6(*, root: Path = ROOT) -> str:
    entries = load_entries(root=root)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    stale_edges: list[dict[str, str]] = []
    for entry in sorted(entries, key=lambda item: (int(item["level"]), str(item["id"]))):
        currency = entry_currency(entry, root=root)
        nodes.append(
            {
                "id": entry["id"],
                "level": entry["level"],
                "status": entry["status"],
                "currency": "STALE" if currency["stale"] else "CURRENT",
                "stored_fingerprint": entry["premise_fingerprint"],
                "computed_fingerprint": currency["computed_fingerprint"],
                "source": f"rules/derived/entries/{entry['id']}.json",
            }
        )
        for premise in entry["premises"]:
            edge = {"from": str(premise["ref"]), "to": str(entry["id"])}
            edges.append(edge)
            if currency["stale"]:
                stale_edges.append(edge)
    payload = _view_base(
        "V6",
        "派生闭包图",
        ["rules/derived/entries/*.json", "rules/derived/derived_rule.schema.json"],
    )
    payload.update(
        {
            "nodes": nodes,
            "edges": edges,
            "stale_or_broken_edges": stale_edges,
            "summary": {
                "node_count": {
                    "value": len(nodes),
                    "source": "rules/derived/entries/*.json (one-entry-per-file count)",
                },
                "edge_count": {
                    "value": len(edges),
                    "source": "rules/derived/entries/*.json#/premises",
                },
            },
            "interpretation_boundary": (
                "level 只是深度，不是已扫尽证明；UNREVIEWED 节点不得被下游消费，预算终止不得写成饱和。"
            ),
        }
    )
    return pretty_json(payload)


def render_views(*, root: Path = ROOT) -> dict[str, str]:
    return {
        "V1": render_view_v1(root=root),
        "V2": render_view_v2(root=root),
        "V3": render_view_v3(root=root),
        "V4": render_view_v4(root=root),
        "V5": render_view_v5(root=root),
        "V6": render_view_v6(root=root),
    }


def check_views(*, root: Path = ROOT) -> dict[str, Any]:
    rendered = render_views(root=root)
    stale: list[str] = []
    authority_issues: list[str] = []
    for view_id, expected in rendered.items():
        path = root / VIEW_PATHS[view_id].relative_to(ROOT)
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(view_id)
            continue
        payload = _strict_object(path)
        if payload.get("_authority") != VIEW_AUTHORITY:
            authority_issues.append(view_id)
    v2 = _strict_object(root / VIEW_PATHS["V2"].relative_to(ROOT))
    columns = v2.get("columns")
    code_header = columns.get("code_call_sites_non_exhaustive") if isinstance(columns, Mapping) else None
    v2_noncomplete = isinstance(code_header, str) and "非完备" in code_header
    return {
        "stale_views": stale,
        "authority_issues": authority_issues,
        "v2_code_header_noncomplete": v2_noncomplete,
        "ok": not stale and not authority_issues and v2_noncomplete,
    }


def render_sample_entry(*, root: Path = ROOT) -> str:
    entry: dict[str, Any] = {
        "_authority": DERIVED_AUTHORITY,
        "id": "D-B1-SCAFFOLD-001",
        "level": 1,
        "kind": "parameter_derivation",
        "statement": (
            "批 1 currency fixture：记录当前 belt_capacity_per_tick 的精确来源值；这是立架样例，不是生产结论。"
        ),
        "scope": "batch1_currency_fixture",
        "premises": [
            {
                "kind": "source_value",
                "ref": "canonical:globals.logistics.belt_capacity_per_tick",
                "source": {
                    "path": "rules/canonical_rules.json",
                    "pointer": "/globals/logistics/belt_capacity_per_tick",
                },
                "value_at_derivation": {"exact_rational": "1/1"},
            },
            {
                "kind": "assumption",
                "ref": "assumption:batch1-fixture-only",
                "statement": "本条目只用于批 1 currency 与视图闭包测试，不得作为 certified 前提。",
                "assumption_version": "1",
            },
        ],
        "premise_fingerprint": "0" * 64,
        "derivation": {
            "method": "direct_projection_fixture",
            "receipt": "docs/research/rule_system_redesign_20260807/batch1_20260815/BATCH1_SELF_RECEIPT.md",
            "recompute_cmd": ".venv/bin/python devtools/rule_system_tooling.py fingerprint rules/derived/entries/D-B1-SCAFFOLD-001.json",
        },
        "crystallization": {
            "free_variable": "none (currency fixture)",
            "collapsed_to": "exact source value",
            "detector": "direct_projection",
        },
        "direction": "neutral",
        "status": "UNREVIEWED",
        "consumers": [],
        "sentinel": "devtools/tests/test_rule_system_tooling.py::test_currency_mutation_turns_red",
    }
    entry["premise_fingerprint"] = compute_premise_fingerprint(entry, root=root)
    return pretty_json(entry)


def check_all(*, root: Path = ROOT) -> dict[str, Any]:
    derived = check_derived_scaffold(root=root)
    ruling = check_ruling_index(root=root)
    gap = check_facility_template_gap(root=root)
    views = check_views(root=root)
    ok = bool(derived["ok"] and ruling["ok"] and gap["ok"] and views["ok"])
    return {
        "derived": derived,
        "ruling_index": ruling,
        "facility_gap": gap,
        "views": views,
        "ok": ok,
    }


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(_json_safe(value), ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="print one deterministic tracked artifact")
    render.add_argument(
        "artifact",
        choices=("ruling-index", "facility-gap", "sample-entry", "V1", "V2", "V3", "V4", "V5", "V6"),
    )

    fingerprint = subparsers.add_parser("fingerprint", help="recompute one derived-entry premise fingerprint")
    fingerprint.add_argument("entry", type=Path)

    subparsers.add_parser("check", help="check the complete batch-1 tool surface")
    subparsers.add_parser("check-ruling-index", help="check append-only ruling index against git grep")
    subparsers.add_parser("check-facility-gap", help="check vendored registry gap projection")
    subparsers.add_parser("check-derived", help="check schema, authority headers and L2 currency")
    subparsers.add_parser("check-views", help="check V1-V6 tracked currency")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "render":
            if args.artifact == "ruling-index":
                sys.stdout.write(render_initial_ruling_index())
            elif args.artifact == "facility-gap":
                sys.stdout.write(render_facility_template_gap())
            elif args.artifact == "sample-entry":
                sys.stdout.write(render_sample_entry())
            else:
                sys.stdout.write(render_views()[args.artifact])
            return 0
        if args.command == "fingerprint":
            entry_path = args.entry if args.entry.is_absolute() else ROOT / args.entry
            entry = _strict_object(entry_path)
            print(compute_premise_fingerprint(entry))
            return 0
        if args.command == "check-ruling-index":
            result = check_ruling_index()
        elif args.command == "check-facility-gap":
            result = check_facility_template_gap()
        elif args.command == "check-derived":
            result = check_derived_scaffold()
        elif args.command == "check-views":
            result = check_views()
        else:
            result = check_all()
        _print_json(result)
        return 0 if result.get("ok") else 1
    except (OSError, UnicodeError, json.JSONDecodeError, jsonschema.ValidationError, RuleToolError) as exc:
        print(f"BLOCK: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
