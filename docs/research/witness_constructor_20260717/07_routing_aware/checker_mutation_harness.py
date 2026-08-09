"""Independent negative-path harness for one checker-accepted layout.

The harness snapshots explicit hash-pinned instance/layout inputs, requires the
pinned independent checker to accept the baseline, creates seven deterministic
single-change layouts, and invokes the same checker for every mutation.  A
negative case passes only when the trusted checker returns ``LAYOUT_INVALID``
and reports the expected error category.  Constructor-side checks never count
as acceptance or rejection.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any


PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESEARCH_ROOT = Path(__file__).resolve().parent
strict_contract = importlib.import_module(f"{PREFIX}.strict_contract")
witness_io = importlib.import_module(f"{PREFIX}.witness_io")

REPORT_SCHEMA_VERSION = "independent_checker_mutation_report.v1"
REPORT_SUCCESS_STATUS = "ALL_MUTATIONS_REJECTED_AS_EXPECTED"
REPORT_FAILURE_STATUS = "MUTATION_HARNESS_REJECTED"
CLAIM_BOUNDARY = "research_checker_negative_path_only"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_DIRECTIONS = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
_EXPECTED_CATEGORIES = {
    "overlap": "F",
    "placement_boundary": "F",
    "front_block": "P",
    "port_exact_count": "P",
    "route_break": "R",
    "power_removal": "PW",
    "objective_plus_one": "O",
}


class CheckerMutationHarnessError(RuntimeError):
    """Stable fail-closed harness error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class SourceSnapshot:
    path: Path
    payload: bytes
    sha256: str
    identity: tuple[int, int, int, int, int, int, int]
    value: Mapping[str, Any]

    def record(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "sha256": self.sha256,
            "size_bytes": len(self.payload),
            "identity": _identity_record(self.identity),
        }


@dataclass(frozen=True)
class Mutation:
    name: str
    expected_category: str
    layout: Mapping[str, Any]
    detail: Mapping[str, Any]


@dataclass(frozen=True)
class MutationHarnessOutcome:
    accepted: bool
    report_path: Path
    work_dir: Path
    report: Mapping[str, Any]


def _fail(code: str, message: str) -> None:
    raise CheckerMutationHarnessError(code, message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail("MALFORMED_OBJECT", f"{label} must be an object with string keys")
    return value


def _sequence(value: object, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail("MALFORMED_ARRAY", f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        _fail("MALFORMED_STRING", f"{label} must be a nonempty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("MALFORMED_INTEGER", f"{label} must be a literal integer")
    return int(value)


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _identity_record(value: tuple[int, int, int, int, int, int, int]) -> dict[str, int]:
    return {
        "device": value[0],
        "inode": value[1],
        "mode": value[2],
        "link_count": value[3],
        "size_bytes": value[4],
        "mtime_ns": value[5],
        "ctime_ns": value[6],
    }


def _read_pinned_json(path: Path, expected_sha256: str, *, label: str) -> SourceSnapshot:
    if type(expected_sha256) is not str or _SHA256_RE.fullmatch(expected_sha256) is None:
        _fail("SOURCE_HASH_INVALID", f"{label}: {expected_sha256!r}")
    source = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        _fail("SOURCE_OPEN_FAILED", f"{label}: {exc}")
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            _fail("SOURCE_FILE_TYPE", f"{label} must be a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        _fail("SOURCE_READ_FAILED", f"{label}: {exc}")
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    if _identity(before) != _identity(after) or len(payload) != before.st_size:
        _fail("SOURCE_DRIFT", f"{label} changed while it was read")
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != expected_sha256:
        _fail("SOURCE_HASH_MISMATCH", f"{label}: expected {expected_sha256}, observed {observed_sha256}")
    try:
        value = strict_contract.strict_json_loads(payload, label=label)
    except Exception as exc:  # noqa: BLE001 - strict input boundary
        _fail("SOURCE_JSON_INVALID", f"{label}: {type(exc).__name__}: {exc}")
    return SourceSnapshot(
        path=source.resolve(strict=True),
        payload=payload,
        sha256=observed_sha256,
        identity=_identity(before),
        value=_mapping(value, label),
    )


def _write_bytes_exclusive(path: Path, payload: bytes) -> Path:
    target = Path(path)
    try:
        with target.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        _fail("OUTPUT_ALREADY_EXISTS", str(target))
    except OSError as exc:
        _fail("OUTPUT_WRITE_FAILED", f"{target}: {exc}")
    return target


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> tuple[Path, str]:
    try:
        payload = (
            json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        _fail("OUTPUT_JSON_INVALID", str(exc))
    return _write_bytes_exclusive(path, payload), hashlib.sha256(payload).hexdigest()


def _verify_file(path: Path, expected_sha256: str) -> dict[str, Any]:
    snapshot = _read_pinned_json(path, expected_sha256, label=str(path))
    return snapshot.record()


def _require_cli_output_scope(path: Path) -> Path:
    resolved = Path(path).resolve()
    research_root = RESEARCH_ROOT.resolve(strict=True)
    try:
        resolved.relative_to(research_root)
    except ValueError:
        _fail("OUTPUT_SCOPE_VIOLATION", f"CLI output must remain under {research_root}: {resolved}")
    return resolved


def _placements(layout: Mapping[str, Any]) -> list[tuple[str, int, Mapping[str, Any]]]:
    result: list[tuple[str, int, Mapping[str, Any]]] = []
    for field in ("required_placements", "optional_placements"):
        for index, raw in enumerate(_sequence(layout.get(field), field)):
            result.append((field, index, _mapping(raw, f"{field}[{index}]")))
    return result


def _mode_index(instance: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    templates = _mapping(instance.get("facility_templates"), "facility_templates")
    for template_id, raw_template in templates.items():
        template = _mapping(raw_template, f"facility_templates.{template_id}")
        for raw_mode in _sequence(template.get("modes"), f"facility_templates.{template_id}.modes"):
            mode = _mapping(raw_mode, f"facility_templates.{template_id}.mode")
            key = (_string(template_id, "template id"), _string(mode.get("id"), "mode id"))
            if key in result:
                _fail("INSTANCE_MODE_DUPLICATE", repr(key))
            result[key] = mode
    return result


def _body_cells(
    placement: Mapping[str, Any],
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
) -> frozenset[tuple[int, int]]:
    template = _string(placement.get("template"), "placement.template")
    mode_id = _string(placement.get("mode"), "placement.mode")
    mode = modes.get((template, mode_id))
    if mode is None:
        _fail("PLACEMENT_MODE_UNKNOWN", f"{template}/{mode_id}")
    anchor = _mapping(placement.get("anchor"), "placement.anchor")
    anchor_x = _integer(anchor.get("x"), "placement.anchor.x")
    anchor_y = _integer(anchor.get("y"), "placement.anchor.y")
    body = _mapping(mode.get("body"), f"{template}/{mode_id}.body")
    width = _integer(body.get("width"), f"{template}/{mode_id}.body.width")
    height = _integer(body.get("height"), f"{template}/{mode_id}.body.height")
    return frozenset(
        (anchor_x + dx, anchor_y + dy)
        for dx in range(width)
        for dy in range(height)
    )


def _active_terminal_cells(
    instance: Mapping[str, Any],
    layout: Mapping[str, Any],
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[tuple[str, int, str, tuple[int, int]], ...]:
    result: list[tuple[str, int, str, tuple[int, int]]] = []
    for field, index, placement in _placements(layout):
        template = str(placement["template"])
        mode_id = str(placement["mode"])
        mode = modes[(template, mode_id)]
        anchor = _mapping(placement.get("anchor"), "placement.anchor")
        anchor_x = int(anchor["x"])
        anchor_y = int(anchor["y"])
        bindings = _mapping(placement.get("port_bindings"), "placement.port_bindings")
        for raw_port in _sequence(mode.get("ports"), f"{template}/{mode_id}.ports"):
            port = _mapping(raw_port, f"{template}/{mode_id}.port")
            port_id = str(port["id"])
            if bindings.get(port_id) is None:
                continue
            body_cell = _mapping(port.get("body_cell"), f"{template}/{mode_id}/{port_id}.body_cell")
            direction = str(port["direction"])
            delta = _DIRECTIONS.get(direction)
            if delta is None:
                _fail("INSTANCE_PORT_DIRECTION", direction)
            access = (
                anchor_x + int(body_cell["x"]) + delta[0],
                anchor_y + int(body_cell["y"]) + delta[1],
            )
            result.append((field, index, port_id, access))
    if not result:
        _fail("MUTATION_TARGET_UNAVAILABLE", "layout has no active terminals")
    return tuple(result)


def _copy_layout(layout: Mapping[str, Any]) -> dict[str, Any]:
    copied = deepcopy(dict(layout))
    return dict(_mapping(copied, "layout copy"))


def _mutable_placement(layout: dict[str, Any], field: str, index: int) -> dict[str, Any]:
    rows = layout[field]
    if not isinstance(rows, list) or not isinstance(rows[index], dict):
        _fail("MALFORMED_LAYOUT", f"{field}[{index}]")
    return rows[index]


def _mutate_overlap(
    instance: Mapping[str, Any], layout: Mapping[str, Any], modes: Mapping[tuple[str, str], Mapping[str, Any]]
) -> Mutation:
    del modes
    templates = _mapping(instance.get("facility_templates"), "facility_templates")
    rows = _placements(layout)
    movable = [
        row
        for row in rows
        if _mapping(templates.get(str(row[2]["template"])), "template").get("placement_rule")
        == "any_body_in_grid"
    ]
    if not movable or len(rows) < 2:
        _fail("MUTATION_TARGET_UNAVAILABLE", "overlap")
    source = movable[0]
    target = next((row for row in rows if row[:2] != source[:2]), None)
    if target is None:
        _fail("MUTATION_TARGET_UNAVAILABLE", "overlap target")
    mutated = _copy_layout(layout)
    placement = _mutable_placement(mutated, source[0], source[1])
    placement["anchor"] = deepcopy(target[2]["anchor"])
    return Mutation(
        "overlap",
        "F",
        mutated,
        {"pointer": f"/{source[0]}/{source[1]}/anchor", "overlaps_instance": target[2]["instance_id"]},
    )


def _mutate_placement_boundary(
    instance: Mapping[str, Any], layout: Mapping[str, Any], modes: Mapping[tuple[str, str], Mapping[str, Any]]
) -> Mutation:
    del modes
    templates = _mapping(instance.get("facility_templates"), "facility_templates")
    width = _integer(_mapping(instance.get("grid"), "grid").get("width"), "grid.width")
    source = next(
        (
            row
            for row in _placements(layout)
            if _mapping(templates.get(str(row[2]["template"])), "template").get("placement_rule")
            == "any_body_in_grid"
        ),
        None,
    )
    if source is None:
        _fail("MUTATION_TARGET_UNAVAILABLE", "placement boundary")
    mutated = _copy_layout(layout)
    placement = _mutable_placement(mutated, source[0], source[1])
    anchor = dict(_mapping(placement.get("anchor"), "placement.anchor"))
    anchor["x"] = width
    placement["anchor"] = anchor
    return Mutation(
        "placement_boundary",
        "F",
        mutated,
        {"pointer": f"/{source[0]}/{source[1]}/anchor/x", "new_x": width},
    )


def _mutate_front_block(
    instance: Mapping[str, Any], layout: Mapping[str, Any], modes: Mapping[tuple[str, str], Mapping[str, Any]]
) -> Mutation:
    power = _mapping(instance.get("power"), "power")
    pole_template = _string(power.get("pole_template"), "power.pole_template")
    poles = [row for row in _placements(layout) if row[0] == "optional_placements" and row[2].get("template") == pole_template]
    if not poles:
        _fail("MUTATION_TARGET_UNAVAILABLE", "front block needs an optional pole")
    grid = _mapping(instance.get("grid"), "grid")
    width = _integer(grid.get("width"), "grid.width")
    height = _integer(grid.get("height"), "grid.height")
    terminals = _active_terminal_cells(instance, layout, modes)
    for pole in poles:
        pole_cells = _body_cells(pole[2], modes)
        occupied_without_pole = set().union(
            *(
                _body_cells(row[2], modes)
                for row in _placements(layout)
                if row[:2] != pole[:2]
            )
        )
        pole_mode = modes[(str(pole[2]["template"]), str(pole[2]["mode"]))]
        body = _mapping(pole_mode.get("body"), "pole mode body")
        pole_width = _integer(body.get("width"), "pole width")
        pole_height = _integer(body.get("height"), "pole height")
        for _field, _index, port_id, access in terminals:
            for dx in range(pole_width):
                for dy in range(pole_height):
                    anchor = (access[0] - dx, access[1] - dy)
                    candidate_cells = {
                        (anchor[0] + ox, anchor[1] + oy)
                        for ox in range(pole_width)
                        for oy in range(pole_height)
                    }
                    if (
                        candidate_cells == set(pole_cells)
                        or candidate_cells & occupied_without_pole
                        or any(not (0 <= x < width and 0 <= y < height) for x, y in candidate_cells)
                    ):
                        continue
                    mutated = _copy_layout(layout)
                    placement = _mutable_placement(mutated, pole[0], pole[1])
                    placement["anchor"] = {"x": anchor[0], "y": anchor[1]}
                    return Mutation(
                        "front_block",
                        "P",
                        mutated,
                        {
                            "pointer": f"/{pole[0]}/{pole[1]}/anchor",
                            "blocked_port_id": port_id,
                            "blocked_access": [access[0], access[1]],
                        },
                    )
    _fail("MUTATION_TARGET_UNAVAILABLE", "no legal pole relocation blocks an active front")


def _mutate_port_exact_count(
    instance: Mapping[str, Any], layout: Mapping[str, Any], modes: Mapping[tuple[str, str], Mapping[str, Any]]
) -> Mutation:
    del instance, modes
    for field, index, placement in _placements(layout):
        bindings = _mapping(placement.get("port_bindings"), "placement.port_bindings")
        active_port = next((port_id for port_id, commodity in bindings.items() if commodity is not None), None)
        if active_port is None:
            continue
        mutated = _copy_layout(layout)
        target = _mutable_placement(mutated, field, index)
        target_bindings = dict(_mapping(target.get("port_bindings"), "placement.port_bindings"))
        target_bindings[active_port] = None
        target["port_bindings"] = target_bindings
        return Mutation(
            "port_exact_count",
            "P",
            mutated,
            {"pointer": f"/{field}/{index}/port_bindings/{active_port}", "new_value": None},
        )
    _fail("MUTATION_TARGET_UNAVAILABLE", "port exact count")


def _mutate_route_break(
    instance: Mapping[str, Any], layout: Mapping[str, Any], modes: Mapping[tuple[str, str], Mapping[str, Any]]
) -> Mutation:
    terminals = _active_terminal_cells(instance, layout, modes)
    components = _sequence(layout.get("route_components"), "route_components")
    by_cell: dict[tuple[int, int], int] = {}
    for index, raw_component in enumerate(components):
        component = _mapping(raw_component, f"route_components[{index}]")
        cell = _mapping(component.get("cell"), f"route_components[{index}].cell")
        by_cell[(_integer(cell.get("x"), "route x"), _integer(cell.get("y"), "route y"))] = index
    target = next(((port_id, access, by_cell[access]) for _field, _index, port_id, access in terminals if access in by_cell), None)
    if target is None:
        _fail("MUTATION_TARGET_UNAVAILABLE", "route break")
    mutated = _copy_layout(layout)
    removed = mutated["route_components"].pop(target[2])
    return Mutation(
        "route_break",
        "R",
        mutated,
        {
            "pointer": f"/route_components/{target[2]}",
            "terminal_port_id": target[0],
            "removed_cell": removed["cell"],
        },
    )


def _mutate_power_removal(
    instance: Mapping[str, Any], layout: Mapping[str, Any], modes: Mapping[tuple[str, str], Mapping[str, Any]]
) -> Mutation:
    templates = _mapping(instance.get("facility_templates"), "facility_templates")
    power = _mapping(instance.get("power"), "power")
    pole_template = _string(power.get("pole_template"), "power.pole_template")
    coverage = _mapping(power.get("coverage_from_pole_anchor"), "power.coverage_from_pole_anchor")
    offsets = (
        _integer(coverage.get("x_min_offset"), "coverage.x_min_offset"),
        _integer(coverage.get("x_max_offset"), "coverage.x_max_offset"),
        _integer(coverage.get("y_min_offset"), "coverage.y_min_offset"),
        _integer(coverage.get("y_max_offset"), "coverage.y_max_offset"),
    )
    placements = _placements(layout)
    poles = [row for row in placements if row[0] == "optional_placements" and row[2].get("template") == pole_template]
    powered = [
        row
        for row in placements
        if _mapping(templates.get(str(row[2]["template"])), "template").get("requires_power") is True
    ]

    def pole_covers(pole: tuple[str, int, Mapping[str, Any]], facility: tuple[str, int, Mapping[str, Any]]) -> bool:
        anchor = _mapping(pole[2].get("anchor"), "pole.anchor")
        px = int(anchor["x"])
        py = int(anchor["y"])
        return any(
            px + offsets[0] <= x <= px + offsets[1]
            and py + offsets[2] <= y <= py + offsets[3]
            for x, y in _body_cells(facility[2], modes)
        )

    essential: tuple[str, int, Mapping[str, Any]] | None = None
    uncovered_instance: str | None = None
    for facility in powered:
        covering = [pole for pole in poles if pole_covers(pole, facility)]
        if len(covering) == 1:
            essential = covering[0]
            uncovered_instance = str(facility[2]["instance_id"])
            break
    if essential is None:
        _fail("MUTATION_TARGET_UNAVAILABLE", "no individually essential power pole")
    mutated = _copy_layout(layout)
    removed = mutated["optional_placements"].pop(essential[1])
    return Mutation(
        "power_removal",
        "PW",
        mutated,
        {
            "pointer": f"/optional_placements/{essential[1]}",
            "removed_instance_id": removed["instance_id"],
            "uncovered_instance_id": uncovered_instance,
        },
    )


def _mutate_objective_plus_one(
    instance: Mapping[str, Any], layout: Mapping[str, Any], modes: Mapping[tuple[str, str], Mapping[str, Any]]
) -> Mutation:
    del instance, modes
    mutated = _copy_layout(layout)
    objective = dict(_mapping(mutated.get("claimed_objective"), "claimed_objective"))
    old_area = _integer(objective.get("area"), "claimed_objective.area")
    objective["area"] = old_area + 1
    mutated["claimed_objective"] = objective
    return Mutation(
        "objective_plus_one",
        "O",
        mutated,
        {"pointer": "/claimed_objective/area", "old_value": old_area, "new_value": old_area + 1},
    )


_MUTATORS: tuple[
    Callable[
        [Mapping[str, Any], Mapping[str, Any], Mapping[tuple[str, str], Mapping[str, Any]]],
        Mutation,
    ],
    ...,
] = (
    _mutate_overlap,
    _mutate_placement_boundary,
    _mutate_front_block,
    _mutate_port_exact_count,
    _mutate_route_break,
    _mutate_power_removal,
    _mutate_objective_plus_one,
)


def generate_mutations(instance: Mapping[str, Any], layout: Mapping[str, Any]) -> tuple[Mutation, ...]:
    """Generate all seven deterministic single-change layouts in memory."""

    modes = _mode_index(instance)
    mutations = tuple(mutator(instance, layout, modes) for mutator in _MUTATORS)
    names = [mutation.name for mutation in mutations]
    if names != list(_EXPECTED_CATEGORIES) or any(
        mutation.expected_category != _EXPECTED_CATEGORIES[mutation.name]
        for mutation in mutations
    ):
        _fail("MUTATION_SET_DRIFT", repr(names))
    return mutations


def _checker_provenance_ok(checker: Any) -> bool:
    identity = checker.checker_source_identity
    return (
        checker.checker_trusted is True
        and checker.checker_sha256 == witness_io.EXPECTED_CHECKER_SHA256
        and checker.checker_source_path == str(witness_io.EXPECTED_CHECKER_PATH)
        and isinstance(identity, tuple)
        and len(identity) == 7
        and stat.S_ISREG(identity[2])
        and checker.checker_snapshot_size_bytes == identity[4]
        and isinstance(checker.checker_snapshot_size_bytes, int)
        and checker.checker_snapshot_size_bytes > 0
        and checker.checker_python_executable == str(Path(sys.executable).resolve())
        and checker.checker_execution_mode == witness_io.PINNED_CHECKER_EXECUTION_MODE
        and checker.signal_number is None
        and checker.stderr == ""
    )


def _checker_record(checker: Any) -> dict[str, Any]:
    identity = checker.checker_source_identity
    return {
        "classification": checker.classification,
        "exit_code": checker.exit_code,
        "status": checker.status,
        "accepted": checker.accepted,
        "checker_trusted": checker.checker_trusted,
        "checker_sha256": checker.checker_sha256,
        "checker_source_path": checker.checker_source_path,
        "checker_source_identity": _identity_record(identity) if isinstance(identity, tuple) and len(identity) == 7 else None,
        "checker_snapshot_size_bytes": checker.checker_snapshot_size_bytes,
        "checker_python_executable": checker.checker_python_executable,
        "checker_execution_mode": checker.checker_execution_mode,
        "signal_number": checker.signal_number,
        "stderr": checker.stderr,
        "stdout": checker.stdout,
        "report": checker.report,
    }


def _negative_checker_verdict(checker: Any, expected_category: str) -> tuple[bool, list[str]]:
    report = checker.report
    schema_ok = isinstance(report, Mapping) and witness_io._checker_report_schema_valid(report)
    errors = report.get("errors") if isinstance(report, Mapping) else None
    error_rows = errors if isinstance(errors, list) else []
    categories = sorted(
        {
            str(error.get("category"))
            for error in error_rows
            if isinstance(error, Mapping)
        }
    )
    passed = (
        _checker_provenance_ok(checker)
        and checker.accepted is False
        and checker.classification == "LAYOUT_INVALID"
        and checker.exit_code == 1
        and checker.status == "LAYOUT_INVALID"
        and schema_ok
        and isinstance(errors, list)
        and bool(errors)
        and expected_category in categories
    )
    return passed, categories


def run_checker_mutation_harness(
    instance_path: Path,
    layout_path: Path,
    *,
    expected_instance_sha256: str,
    expected_layout_sha256: str,
    report_path: Path,
    work_dir: Path | None = None,
    checker_timeout_seconds: float = 60.0,
    checker_runner: Callable[..., Any] | None = None,
) -> MutationHarnessOutcome:
    """Run the pinned checker on the baseline and all seven mutations."""

    if (
        isinstance(checker_timeout_seconds, bool)
        or not isinstance(checker_timeout_seconds, (int, float))
        or not math.isfinite(float(checker_timeout_seconds))
        or checker_timeout_seconds <= 0
    ):
        _fail("CHECKER_TIMEOUT_INVALID", repr(checker_timeout_seconds))
    target_report = Path(report_path)
    if target_report.exists() or target_report.is_symlink():
        _fail("REPORT_ALREADY_EXISTS", str(target_report))
    try:
        parent = target_report.parent.resolve(strict=True)
    except OSError as exc:
        _fail("REPORT_PARENT_INVALID", str(exc))
    if not parent.is_dir():
        _fail("REPORT_PARENT_INVALID", str(parent))
    target_report = parent / target_report.name

    instance_source = _read_pinned_json(instance_path, expected_instance_sha256, label="instance")
    layout_source = _read_pinned_json(layout_path, expected_layout_sha256, label="layout")
    chosen_work_dir = Path(work_dir) if work_dir is not None else parent / f"{target_report.stem}.inputs"
    try:
        chosen_work_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError:
        _fail("WORK_DIRECTORY_EXISTS", str(chosen_work_dir))
    except OSError as exc:
        _fail("WORK_DIRECTORY_CREATE_FAILED", str(exc))
    chosen_work_dir = chosen_work_dir.resolve(strict=True)

    instance_snapshot_path = _write_bytes_exclusive(
        chosen_work_dir / f"instance.{instance_source.sha256}.json",
        instance_source.payload,
    )
    layout_snapshot_path = _write_bytes_exclusive(
        chosen_work_dir / f"baseline.{layout_source.sha256}.json",
        layout_source.payload,
    )
    _verify_file(instance_snapshot_path, instance_source.sha256)
    _verify_file(layout_snapshot_path, layout_source.sha256)

    runner = checker_runner or witness_io.run_independent_checker
    baseline = runner(
        instance_snapshot_path,
        layout_snapshot_path,
        timeout_seconds=checker_timeout_seconds,
    )
    _verify_file(instance_snapshot_path, instance_source.sha256)
    _verify_file(layout_snapshot_path, layout_source.sha256)
    if not baseline.accepted or not _checker_provenance_ok(baseline):
        _fail("BASELINE_NOT_ACCEPTED_BY_PINNED_CHECKER", repr(baseline.classification))

    mutations = generate_mutations(instance_source.value, layout_source.value)
    mutation_records: list[dict[str, Any]] = []
    for index, mutation in enumerate(mutations, start=1):
        mutation_payload = witness_io.canonical_json_bytes(mutation.layout)
        mutation_sha256 = hashlib.sha256(mutation_payload).hexdigest()
        mutation_path = _write_bytes_exclusive(
            chosen_work_dir / f"{index:02d}-{mutation.name}.{mutation_sha256}.json",
            mutation_payload,
        )
        checker = runner(
            instance_snapshot_path,
            mutation_path,
            timeout_seconds=checker_timeout_seconds,
        )
        instance_record = _verify_file(instance_snapshot_path, instance_source.sha256)
        mutation_input_record = _verify_file(mutation_path, mutation_sha256)
        passed, observed_categories = _negative_checker_verdict(checker, mutation.expected_category)
        mutation_records.append(
            {
                "name": mutation.name,
                "expected_category": mutation.expected_category,
                "observed_categories": observed_categories,
                "passed": passed,
                "detail": dict(mutation.detail),
                "checker_input": {
                    "instance": instance_record,
                    "layout": mutation_input_record,
                },
                "checker": _checker_record(checker),
            }
        )

    passed_count = sum(record["passed"] is True for record in mutation_records)
    accepted = passed_count == len(_EXPECTED_CATEGORIES)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": REPORT_SUCCESS_STATUS if accepted else REPORT_FAILURE_STATUS,
        "claim_boundary": CLAIM_BOUNDARY,
        "source": {
            "instance": instance_source.record(),
            "layout": layout_source.record(),
        },
        "snapshots": {
            "instance": _verify_file(instance_snapshot_path, instance_source.sha256),
            "baseline_layout": _verify_file(layout_snapshot_path, layout_source.sha256),
        },
        "baseline_checker": _checker_record(baseline),
        "mutations": mutation_records,
        "summary": {
            "mutation_count": len(mutation_records),
            "passed_count": passed_count,
            "failed_count": len(mutation_records) - passed_count,
            "all_rejected_with_expected_category": accepted,
        },
    }
    written_report, _report_sha256 = _write_json_exclusive(target_report, report)
    return MutationHarnessOutcome(accepted, written_report, chosen_work_dir, report)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--expected-instance-sha256", required=True)
    parser.add_argument("--expected-layout-sha256", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--checker-timeout-seconds", type=float, default=60.0)
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report_path = _require_cli_output_scope(args.report)
        work_dir = _require_cli_output_scope(args.work_dir) if args.work_dir is not None else None
        outcome = run_checker_mutation_harness(
            args.instance,
            args.layout,
            expected_instance_sha256=args.expected_instance_sha256,
            expected_layout_sha256=args.expected_layout_sha256,
            report_path=report_path,
            work_dir=work_dir,
            checker_timeout_seconds=args.checker_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - one CLI classification boundary
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "accepted": outcome.accepted,
                "report": str(outcome.report_path),
                "work_dir": str(outcome.work_dir),
                "claim_boundary": CLAIM_BOUNDARY,
            },
            sort_keys=True,
        )
    )
    return 0 if outcome.accepted else 1


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()


__all__ = [
    "CheckerMutationHarnessError",
    "Mutation",
    "MutationHarnessOutcome",
    "generate_mutations",
    "run_checker_mutation_harness",
    "run_cli",
]
