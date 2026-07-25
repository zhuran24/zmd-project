#!/usr/bin/env python3
"""Independent brute-force checker for small sidewise-membrane fixtures.

This file deliberately does not import the primary model kernel.  It accepts
the same closed fixture schema and is capped at twelve occurrences.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA = "b1_sidewise_marked_membrane_fixture_v1"
RESULT_SCHEMA = "b1_sidewise_marked_membrane_independent_fixture_result_v1"
ENDPOINTS = {"none", "left", "right"}
MAX_OCCURRENCES = 12
MAX_SEARCH_NODES = 200_000


class CheckError(ValueError):
    """Independent fixture parsing or enumeration failure."""


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CheckError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _mapping(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise CheckError(f"{label} has the wrong closed key set")
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CheckError(f"{label} must be an integer >= {minimum}")
    return value


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise CheckError(f"{label} must be a non-empty string")
    return value


def _parse(raw: bytes) -> tuple[tuple[int, ...], int, int, tuple[dict[str, Any], ...]]:
    try:
        top = json.loads(raw, object_pairs_hook=_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"invalid fixture JSON: {exc}") from exc
    top = _mapping(
        top,
        {"schema_version", "side_capacities", "free_score", "target_score", "groups"},
        "fixture",
    )
    if top["schema_version"] != SCHEMA:
        raise CheckError("schema_version drifted")
    capacities = top["side_capacities"]
    if (
        not isinstance(capacities, list)
        or len(capacities) != 4
        or any(type(item) is not int or item <= 0 for item in capacities)
    ):
        raise CheckError("side_capacities are invalid")
    free_score = _integer(top["free_score"], "free_score")
    target_score = _integer(top["target_score"], "target_score")
    raw_groups = top["groups"]
    if not isinstance(raw_groups, list) or not raw_groups:
        raise CheckError("groups are invalid")
    occurrences: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for group_index, raw_group in enumerate(raw_groups):
        group = _mapping(raw_group, {"name", "multiplicity", "faces"}, "group")
        name = _text(group["name"], f"group[{group_index}].name")
        if name in seen_groups:
            raise CheckError("duplicate group name")
        seen_groups.add(name)
        multiplicity = _integer(group["multiplicity"], "multiplicity", 1)
        faces = group["faces"]
        if not isinstance(faces, list) or not faces:
            raise CheckError("faces are invalid")
        parsed_faces: list[dict[str, Any]] = []
        seen_faces: set[str] = set()
        for raw_face in faces:
            face = _mapping(raw_face, {"name", "contacts"}, "face")
            face_name = _text(face["name"], "face.name")
            if face_name in seen_faces:
                raise CheckError("duplicate face name")
            seen_faces.add(face_name)
            contacts = face["contacts"]
            if not isinstance(contacts, list) or not contacts:
                raise CheckError("contacts are invalid")
            parsed_contacts: list[dict[str, Any]] = []
            seen_contacts: set[str] = set()
            for raw_contact in contacts:
                contact = _mapping(
                    raw_contact,
                    {"name", "length", "active", "marks", "endpoint"},
                    "contact",
                )
                contact_name = _text(contact["name"], "contact.name")
                if contact_name in seen_contacts:
                    raise CheckError("duplicate contact name")
                seen_contacts.add(contact_name)
                length = _integer(contact["length"], "contact.length", 1)
                active = _integer(contact["active"], "contact.active")
                marks = _integer(contact["marks"], "contact.marks")
                endpoint = _text(contact["endpoint"], "contact.endpoint")
                if endpoint not in ENDPOINTS or marks > active or active > length:
                    raise CheckError("contact semantics are invalid")
                parsed_contacts.append(
                    {
                        "name": contact_name,
                        "length": length,
                        "score": active + marks,
                        "endpoint": endpoint,
                    }
                )
            parsed_faces.append({"name": face_name, "contacts": parsed_contacts})
        for copy_index in range(multiplicity):
            occurrences.append(
                {
                    "name": f"{name}#{copy_index + 1}",
                    "faces": parsed_faces,
                }
            )
    if len(occurrences) > MAX_OCCURRENCES:
        raise CheckError(f"{len(occurrences)} occurrences exceed independent fixture cap {MAX_OCCURRENCES}")
    return tuple(capacities), free_score, target_score, tuple(occurrences)


def _solve(
    capacities: tuple[int, ...],
    free_score: int,
    occurrences: tuple[dict[str, Any], ...],
) -> tuple[int, list[str], int]:
    best_score = free_score
    best_trace: list[str] = []
    leaves = 0
    nodes = 0

    def visit(
        index: int,
        used: tuple[int, ...],
        left_mask: int,
        right_mask: int,
        score: int,
        trace: list[str],
    ) -> None:
        nonlocal best_score, best_trace, leaves, nodes
        nodes += 1
        if nodes > MAX_SEARCH_NODES:
            raise CheckError(f"search nodes exceed independent fixture cap {MAX_SEARCH_NODES}")
        if index == len(occurrences):
            leaves += 1
            if score > best_score or (score == best_score and trace < best_trace):
                best_score = score
                best_trace = list(trace)
            return
        occurrence = occurrences[index]
        visit(index + 1, used, left_mask, right_mask, score, trace)
        for side_index, capacity in enumerate(capacities):
            bit = 1 << side_index
            for face in occurrence["faces"]:
                for contact in face["contacts"]:
                    length = contact["length"]
                    if used[side_index] + length > capacity:
                        continue
                    endpoint = contact["endpoint"]
                    if endpoint == "left" and left_mask & bit:
                        continue
                    if endpoint == "right" and right_mask & bit:
                        continue
                    new_used = list(used)
                    new_used[side_index] += length
                    label = f"{occurrence['name']}:{face['name']}:{contact['name']}@side{side_index}"
                    visit(
                        index + 1,
                        tuple(new_used),
                        left_mask | (bit if endpoint == "left" else 0),
                        right_mask | (bit if endpoint == "right" else 0),
                        score + contact["score"],
                        [*trace, label],
                    )

    visit(0, (0, 0, 0, 0), 0, 0, free_score, [])
    return best_score, best_trace, leaves


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.fixture.is_symlink() or not args.fixture.is_file():
            raise CheckError("fixture must be a regular non-symlink file")
        capacities, free_score, target_score, occurrences = _parse(args.fixture.read_bytes())
        maximum, trace, leaves = _solve(capacities, free_score, occurrences)
        print(
            json.dumps(
                {
                    "schema_version": RESULT_SCHEMA,
                    "status": "PASS",
                    "mode": "synthetic_fixture_only",
                    "fixture": str(args.fixture.resolve()),
                    "maximum_score": maximum,
                    "target_score": target_score,
                    "target_reached": maximum >= target_score,
                    "occurrence_count": len(occurrences),
                    "leaf_count": leaves,
                    "trace": trace,
                    "claim_boundary": ("synthetic_fixture_only_no_strict_geometry_or_upper_bound_claim"),
                },
                sort_keys=True,
            )
        )
        return 0
    except (CheckError, OSError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": RESULT_SCHEMA,
                    "status": "FAIL_CLOSED",
                    "error": str(exc),
                    "claim_boundary": "none",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
