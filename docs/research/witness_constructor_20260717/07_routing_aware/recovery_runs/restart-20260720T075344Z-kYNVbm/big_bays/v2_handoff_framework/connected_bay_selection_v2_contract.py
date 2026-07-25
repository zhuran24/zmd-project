"""Pure-stdlib fail-closed parser for ``connected_bay_selection.v2``.

This is a research handoff contract copy.  It does not import a constructor,
solver, materializer, or router.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "connected_bay_selection.v2"
READY_STATUS = "CONNECTED_BAY_SELECTION_READY"
EXPECTED_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
EXPECTED_COMPONENTS = frozenset(range(17))
EXPECTED_COUNTS = {
    "manufacturing_3x3": 132,
    "manufacturing_5x5": 49,
    "manufacturing_6x4": 38,
}
EXPECTED_POSES = 219
EXPECTED_POLES = 35
GRID_SIZE = 70
PROTECTED_SHAPE = (6, 7)
SHA_RE = re.compile(r"[0-9a-f]{64}")
Cell = tuple[int, int]


class ContractError(ValueError):
    """Stable local handoff rejection."""


@dataclass(frozen=True)
class ParsedSelection:
    pole_anchors: tuple[Cell, ...]
    protected_rectangle: tuple[int, int, int, int]
    component_ids: tuple[int, ...]
    template_counts: Mapping[str, int]
    pose_count: int
    body_cell_count: int
    source_count: int


def fail(code: str, detail: str) -> None:
    raise ContractError(f"{code}: {detail}")


def mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        fail("MALFORMED_OBJECT", label)
    return value


def sequence(value: object, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        fail("MALFORMED_ARRAY", label)
    return value


def string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        fail("MALFORMED_STRING", label)
    return value


def integer(value: object, label: str) -> int:
    if type(value) is not int:
        fail("MALFORMED_INTEGER", label)
    return value


def cell(value: object, label: str) -> Cell:
    pair = sequence(value, label)
    if len(pair) != 2:
        fail("MALFORMED_CELL", label)
    return integer(pair[0], f"{label}[0]"), integer(pair[1], f"{label}[1]")


def exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        fail("SCHEMA_FIELDS", f"{label}: expected={sorted(expected)!r}, observed={sorted(value)!r}")


def regular_non_symlink(path: Path, label: str) -> Path:
    try:
        metadata = path.lstat()
    except OSError as exc:
        fail("SOURCE_UNAVAILABLE", f"{label}: {exc}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        fail("SOURCE_FILE_TYPE", label)
    return path.resolve(strict=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_selection(
    value: object,
    *,
    selection_parent: Path,
    source_root: Path,
    verify_sources: bool = True,
) -> ParsedSelection:
    root = mapping(value, "selection")
    exact_fields(
        root,
        {
            "schema_version",
            "status",
            "claim_boundary",
            "baseline_head",
            "source_artifacts",
            "pole_anchors",
            "protected_rectangle",
            "components",
        },
        "selection",
    )
    if root.get("schema_version") != SCHEMA_VERSION:
        fail("SCHEMA_VERSION", repr(root.get("schema_version")))
    if root.get("status") != READY_STATUS:
        fail("STATUS", repr(root.get("status")))
    string(root.get("claim_boundary"), "claim_boundary")
    if root.get("baseline_head") != EXPECTED_HEAD:
        fail("BASELINE_HEAD", repr(root.get("baseline_head")))

    sources = sequence(root.get("source_artifacts"), "source_artifacts")
    if not sources:
        fail("SOURCE_EMPTY", "at least one source is required")
    seen_paths: set[Path] = set()
    for index, raw in enumerate(sources):
        row = mapping(raw, f"source_artifacts[{index}]")
        exact_fields(row, {"path", "sha256"}, f"source_artifacts[{index}]")
        raw_path = Path(string(row.get("path"), f"source_artifacts[{index}].path"))
        path = raw_path if raw_path.is_absolute() else selection_parent / raw_path
        path = regular_non_symlink(path, f"source_artifacts[{index}]")
        try:
            path.relative_to(source_root.resolve(strict=True))
        except ValueError:
            fail("SOURCE_SCOPE", str(path))
        digest = string(row.get("sha256"), f"source_artifacts[{index}].sha256")
        if SHA_RE.fullmatch(digest) is None:
            fail("SOURCE_HASH", digest)
        if path in seen_paths:
            fail("SOURCE_DUPLICATE", str(path))
        seen_paths.add(path)
        if verify_sources and sha256(path) != digest:
            fail("SOURCE_HASH_MISMATCH", str(path))

    poles = tuple(cell(raw, f"pole_anchors[{index}]") for index, raw in enumerate(sequence(root.get("pole_anchors"), "pole_anchors")))
    if len(poles) != EXPECTED_POLES or len(set(poles)) != EXPECTED_POLES:
        fail("POLE_COUNT", f"expected {EXPECTED_POLES} unique anchors")
    pole_bodies: set[Cell] = set()
    for anchor in poles:
        body = {(x, y) for x in range(anchor[0], anchor[0] + 2) for y in range(anchor[1], anchor[1] + 2)}
        if len(body) != 4 or any(not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE) for x, y in body):
            fail("POLE_GRID", repr(anchor))
        if body & pole_bodies:
            fail("POLE_OVERLAP", repr(anchor))
        pole_bodies |= body

    protected_raw = sequence(root.get("protected_rectangle"), "protected_rectangle")
    if len(protected_raw) != 4:
        fail("PROTECTED_RECTANGLE", "expected [x,y,width,height]")
    protected_rectangle = tuple(integer(item, f"protected_rectangle[{index}]") for index, item in enumerate(protected_raw))
    px, py, width, height = protected_rectangle
    if (width, height) != PROTECTED_SHAPE:
        fail("PROTECTED_RECTANGLE", f"shape {(width, height)!r}")
    protected = {(x, y) for x in range(px, px + width) for y in range(py, py + height)}
    if len(protected) != 42 or any(not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE) for x, y in protected):
        fail("PROTECTED_RECTANGLE", "outside grid")
    if protected & pole_bodies:
        fail("PROTECTED_AUX_OVERLAP", "protected rectangle intersects a pole body")

    component_ids: list[int] = []
    counts: Counter[str] = Counter()
    occupied: set[Cell] = set()
    pose_count = 0
    for component_index, raw in enumerate(sequence(root.get("components"), "components")):
        row = mapping(raw, f"components[{component_index}]")
        exact_fields(row, {"component", "origin", "selected"}, f"components[{component_index}]")
        component = integer(row.get("component"), f"components[{component_index}].component")
        origin = cell(row.get("origin"), f"components[{component_index}].origin")
        component_ids.append(component)
        for pose_index, raw_pose in enumerate(sequence(row.get("selected"), f"components[{component_index}].selected")):
            label = f"components[{component_index}].selected[{pose_index}]"
            pose = mapping(raw_pose, label)
            exact_fields(pose, {"template", "mode", "body", "inputs", "outputs"}, label)
            template = string(pose.get("template"), f"{label}.template")
            if template not in EXPECTED_COUNTS:
                fail("TEMPLATE", template)
            string(pose.get("mode"), f"{label}.mode")
            parsed_fields: dict[str, tuple[Cell, ...]] = {}
            for field in ("body", "inputs", "outputs"):
                parsed = tuple(cell(item, f"{label}.{field}[{index}]") for index, item in enumerate(sequence(pose.get(field), f"{label}.{field}")))
                if not parsed or len(parsed) != len(set(parsed)):
                    fail("POSE_CELLS", f"{label}.{field}")
                global_cells = tuple((origin[0] + x, origin[1] + y) for x, y in parsed)
                if any(not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE) for x, y in global_cells):
                    fail("POSE_GRID", f"{label}.{field}")
                parsed_fields[field] = global_cells
            body = set(parsed_fields["body"])
            if body & occupied:
                fail("BODY_OVERLAP", label)
            if body & pole_bodies:
                fail("BODY_AUX_OVERLAP", label)
            if body & protected:
                fail("BODY_PROTECTED_OVERLAP", label)
            occupied |= body
            counts[template] += 1
            pose_count += 1
    if frozenset(component_ids) != EXPECTED_COMPONENTS or len(component_ids) != len(set(component_ids)):
        fail("COMPONENT_IDS", repr(sorted(component_ids)))
    if pose_count != EXPECTED_POSES:
        fail("POSE_COUNT", str(pose_count))
    if dict(counts) != EXPECTED_COUNTS:
        fail("TEMPLATE_COUNTS", repr(dict(counts)))
    return ParsedSelection(
        pole_anchors=tuple(sorted(poles, key=lambda item: (item[1], item[0]))),
        protected_rectangle=protected_rectangle,
        component_ids=tuple(sorted(component_ids)),
        template_counts=dict(counts),
        pose_count=pose_count,
        body_cell_count=len(occupied),
        source_count=len(sources),
    )
