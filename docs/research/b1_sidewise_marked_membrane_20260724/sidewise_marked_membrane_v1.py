#!/usr/bin/env python3
"""Lightweight exact model kernel for the B1 sidewise membrane round.

The current entry point intentionally executes only synthetic fixtures.  The
strict-instance optimizer and every PB/formal action are behind the explicit
``PAUSE_FOR_USER_GAME_END`` boundary documented by this research package.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

MODEL_SCHEMA = "b1_sidewise_marked_membrane_fixture_v1"
RESULT_SCHEMA = "b1_sidewise_marked_membrane_fixture_result_v1"
PAUSE_STATUS = "PAUSE_FOR_USER_GAME_END"
ENDPOINTS = frozenset({"none", "left", "right"})
STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"

TOTAL_TERMINALS = 628
TOTAL_MARKS = 110
CONTROL_TERMINAL_CAP = 124
CONTROL_MARK_CAP = 88
CONTROL_COMBINED_CAP = 212
TREATMENT_TARGET_CAP = 209
OUTSIDE_INCIDENCE_CAP = 4
AVAILABLE_NONBODY_CELLS = 1320
CEILING_WIDTH = 22
CEILING_HEIGHT = 54


class ModelError(ValueError):
    """A closed-schema or exact-enumeration failure."""


class StateLimitExceeded(ModelError):
    """The configured lightweight state ceiling was exceeded."""


@dataclasses.dataclass(frozen=True, slots=True)
class Contact:
    name: str
    length: int
    active: int
    marks: int
    endpoint: str

    @property
    def score(self) -> int:
        return self.active + self.marks


@dataclasses.dataclass(frozen=True, slots=True)
class Face:
    name: str
    contacts: tuple[Contact, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Group:
    name: str
    multiplicity: int
    faces: tuple[Face, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Model:
    side_capacities: tuple[int, int, int, int]
    free_score: int
    target_score: int
    groups: tuple[Group, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class SolveResult:
    maximum_score: int
    state_count: int
    occurrence_count: int
    trace: tuple[str, ...]


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _closed_mapping(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ModelError(f"{label} must contain exactly {sorted(keys)}")
    if not all(type(key) is str for key in value):
        raise ModelError(f"{label} keys must be strings")
    return value


def _exact_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ModelError(f"{label} must be an integer >= {minimum}")
    return value


def _exact_string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise ModelError(f"{label} must be a non-empty string")
    return value


def parse_model_bytes(raw: bytes) -> Model:
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelError(f"invalid fixture JSON: {exc}") from exc
    top = _closed_mapping(
        payload,
        {"schema_version", "side_capacities", "free_score", "target_score", "groups"},
        "fixture",
    )
    if top["schema_version"] != MODEL_SCHEMA:
        raise ModelError("fixture schema_version drifted")
    capacities_raw = top["side_capacities"]
    if (
        not isinstance(capacities_raw, list)
        or len(capacities_raw) != 4
        or any(type(value) is not int or value <= 0 for value in capacities_raw)
    ):
        raise ModelError("side_capacities must be four positive integers")
    capacities = tuple(capacities_raw)
    free_score = _exact_int(top["free_score"], "free_score")
    target_score = _exact_int(top["target_score"], "target_score")

    groups_raw = top["groups"]
    if not isinstance(groups_raw, list) or not groups_raw:
        raise ModelError("groups must be a non-empty list")
    groups: list[Group] = []
    group_names: set[str] = set()
    for group_index, raw_group in enumerate(groups_raw):
        group_map = _closed_mapping(
            raw_group,
            {"name", "multiplicity", "faces"},
            f"groups[{group_index}]",
        )
        group_name = _exact_string(group_map["name"], f"groups[{group_index}].name")
        if group_name in group_names:
            raise ModelError(f"duplicate group name: {group_name}")
        group_names.add(group_name)
        multiplicity = _exact_int(
            group_map["multiplicity"],
            f"groups[{group_index}].multiplicity",
            minimum=1,
        )
        faces_raw = group_map["faces"]
        if not isinstance(faces_raw, list) or not faces_raw:
            raise ModelError(f"groups[{group_index}].faces must be non-empty")
        faces: list[Face] = []
        face_names: set[str] = set()
        for face_index, raw_face in enumerate(faces_raw):
            face_map = _closed_mapping(
                raw_face,
                {"name", "contacts"},
                f"groups[{group_index}].faces[{face_index}]",
            )
            face_name = _exact_string(
                face_map["name"],
                f"groups[{group_index}].faces[{face_index}].name",
            )
            if face_name in face_names:
                raise ModelError(f"duplicate face name in {group_name}: {face_name}")
            face_names.add(face_name)
            contacts_raw = face_map["contacts"]
            if not isinstance(contacts_raw, list) or not contacts_raw:
                raise ModelError(f"{group_name}.{face_name}.contacts must be non-empty")
            contacts: list[Contact] = []
            contact_names: set[str] = set()
            for contact_index, raw_contact in enumerate(contacts_raw):
                label = f"{group_name}.{face_name}.contacts[{contact_index}]"
                contact_map = _closed_mapping(
                    raw_contact,
                    {"name", "length", "active", "marks", "endpoint"},
                    label,
                )
                contact_name = _exact_string(contact_map["name"], f"{label}.name")
                if contact_name in contact_names:
                    raise ModelError(f"duplicate contact name in {group_name}.{face_name}: {contact_name}")
                contact_names.add(contact_name)
                length = _exact_int(contact_map["length"], f"{label}.length", minimum=1)
                active = _exact_int(contact_map["active"], f"{label}.active")
                marks = _exact_int(contact_map["marks"], f"{label}.marks")
                endpoint = _exact_string(contact_map["endpoint"], f"{label}.endpoint")
                if endpoint not in ENDPOINTS:
                    raise ModelError(f"{label}.endpoint is invalid")
                if marks > active:
                    raise ModelError(f"{label}.marks cannot exceed active")
                if active > length:
                    raise ModelError(f"{label}.active cannot exceed contact length")
                contacts.append(Contact(contact_name, length, active, marks, endpoint))
            faces.append(Face(face_name, tuple(contacts)))
        groups.append(Group(group_name, multiplicity, tuple(faces)))
    return Model(capacities, free_score, target_score, tuple(groups))


def load_model(path: Path) -> Model:
    if path.is_symlink() or not path.is_file():
        raise ModelError("fixture must be a regular non-symlink file")
    return parse_model_bytes(path.read_bytes())


def aggregate_control() -> dict[str, int]:
    combined = CONTROL_TERMINAL_CAP + CONTROL_MARK_CAP
    if combined != CONTROL_COMBINED_CAP:
        raise ModelError("aggregate control constants drifted")
    return {
        "terminal_inside_cap": CONTROL_TERMINAL_CAP,
        "marked_inside_cap": CONTROL_MARK_CAP,
        "combined_inside_cap": combined,
    }


def ceiling_consequence(maximum_inside_score: int) -> dict[str, int | bool]:
    maximum_inside_score = _exact_int(maximum_inside_score, "maximum_inside_score")
    outside_incidences = TOTAL_TERMINALS + TOTAL_MARKS - maximum_inside_score
    outside_cells = (outside_incidences + OUTSIDE_INCIDENCE_CAP - 1) // OUTSIDE_INCIDENCE_CAP
    area = CEILING_WIDTH * CEILING_HEIGHT
    left_hand_side = area + outside_cells
    return {
        "inside_cap": maximum_inside_score,
        "outside_incidences": outside_incidences,
        "outside_cells": outside_cells,
        "area": area,
        "left_hand_side": left_hand_side,
        "available_nonbody_cells": AVAILABLE_NONBODY_CELLS,
        "ceiling_excluded": left_hand_side > AVAILABLE_NONBODY_CELLS,
    }


def _expanded_occurrences(model: Model) -> tuple[tuple[str, tuple[Face, ...]], ...]:
    return tuple(
        (f"{group.name}#{copy_index + 1}", group.faces)
        for group in model.groups
        for copy_index in range(group.multiplicity)
    )


def solve_exact_fixture(model: Model, *, state_limit: int = 100_000) -> SolveResult:
    """Solve a bounded synthetic fixture by exact finite-state dynamic programming."""

    state_limit = _exact_int(state_limit, "state_limit", minimum=1)
    occurrences = _expanded_occurrences(model)
    # State: used lengths, left-endpoint mask, right-endpoint mask.
    initial_state = ((0, 0, 0, 0), 0, 0)
    states: dict[tuple[tuple[int, int, int, int], int, int], tuple[int, tuple[str, ...]]] = {
        initial_state: (model.free_score, ())
    }
    for occurrence_name, faces in occurrences:
        next_states = dict(states)
        for state, (score, trace) in states.items():
            used, left_mask, right_mask = state
            for side_index, capacity in enumerate(model.side_capacities):
                side_bit = 1 << side_index
                for face in faces:
                    for contact in face.contacts:
                        new_length = used[side_index] + contact.length
                        if new_length > capacity:
                            continue
                        if contact.endpoint == "left" and left_mask & side_bit:
                            continue
                        if contact.endpoint == "right" and right_mask & side_bit:
                            continue
                        new_used_list = list(used)
                        new_used_list[side_index] = new_length
                        new_left = left_mask | (side_bit if contact.endpoint == "left" else 0)
                        new_right = right_mask | (side_bit if contact.endpoint == "right" else 0)
                        new_state = (tuple(new_used_list), new_left, new_right)
                        candidate = (
                            score + contact.score,
                            trace + (f"{occurrence_name}:{face.name}:{contact.name}@side{side_index}",),
                        )
                        previous = next_states.get(new_state)
                        if previous is None or candidate[0] > previous[0]:
                            next_states[new_state] = candidate
        if len(next_states) > state_limit:
            raise StateLimitExceeded(f"state count {len(next_states)} exceeds lightweight limit {state_limit}")
        states = next_states
    maximum_score, trace = max(states.values(), key=lambda item: (item[0], item[1]))
    return SolveResult(maximum_score, len(states), len(occurrences), trace)


def _fixture_result(path: Path, state_limit: int) -> dict[str, Any]:
    model = load_model(path)
    result = solve_exact_fixture(model, state_limit=state_limit)
    return {
        "schema_version": RESULT_SCHEMA,
        "status": "PASS",
        "mode": "synthetic_fixture_only",
        "fixture": str(path.resolve()),
        "maximum_score": result.maximum_score,
        "target_score": model.target_score,
        "target_reached": result.maximum_score >= model.target_score,
        "state_count": result.state_count,
        "occurrence_count": result.occurrence_count,
        "trace": list(result.trace),
        "aggregate_control": aggregate_control(),
        "claim_boundary": "synthetic_fixture_only_no_strict_geometry_or_upper_bound_claim",
    }


def _pause_result(path: Path) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA,
        "status": PAUSE_STATUS,
        "mode": "strict_instance_not_executed",
        "strict_instance": str(path.resolve(strict=False)),
        "expected_sha256": STRICT_SHA256,
        "next_action": "wait_for_explicit_user_game_end_authorization",
        "claim_boundary": "no_strict_recomputation_no_geometry_admission_no_upper_update",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--fixture", type=Path)
    inputs.add_argument("--strict-instance", type=Path)
    parser.add_argument("--state-limit", type=int, default=100_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.strict_instance is not None:
            print(json.dumps(_pause_result(args.strict_instance), sort_keys=True))
            return 3
        assert args.fixture is not None
        print(json.dumps(_fixture_result(args.fixture, args.state_limit), sort_keys=True))
        return 0
    except (ModelError, OSError) as exc:
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
