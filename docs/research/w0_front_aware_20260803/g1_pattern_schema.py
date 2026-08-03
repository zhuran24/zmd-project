"""W0 front-aware G1: strict schemas and canonical hashing for the five artifacts.

research-only.  No authority, no bound, no ledger effect.

Five JSON shapes travel between the G1 stages:

===========================  =====================================================
``w0_g1_pattern_v1``         one region-local pattern (bodies / poles / hole /
                             per-body mode table and class witnesses)
``w0_g1_catalog_v1``         all patterns of one region class, plus the masks they
                             were generated against
``w0_g1_master_result_v1``   the exact-cover master's answer (stage B)
``w0_g1_geometry_v1``        the expanded full-board geometry (stage B)
``w0_g1_audit_v1``           the independent front-viability audit verdict
===========================  =====================================================

These constants are the stage A / stage B freeze line: stage B may add a
``w0_g1_*_v2`` alongside, never mutate a ``_v1`` field.

Strictness.  ``loads_strict`` rejects duplicate object keys, ``NaN`` /
``Infinity`` and out-of-range float literals; every object parser rejects unknown
and missing fields rather than defaulting them, and every schema string is
matched exactly.  Fail-closed is the point: a catalog that has drifted must stop
the run, not be repaired in flight.

Authority.  ``RESEARCH_AUTHORITY`` is the only accepted authority block and all
three of its fields are false.  ``require_research_authority`` is called by every
parser, so no artifact of this line can claim authority even by hand-editing.

Runtime contract: stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "PATTERN_SCHEMA",
    "CATALOG_SCHEMA",
    "MASTER_RESULT_SCHEMA",
    "GEOMETRY_SCHEMA",
    "AUDIT_SCHEMA",
    "ALL_SCHEMAS",
    "RESEARCH_AUTHORITY",
    "SchemaError",
    "canonical_json_text",
    "canonical_json_bytes",
    "sha256_of_obj",
    "sha256_of_bytes",
    "loads_strict",
    "load_strict",
    "dump_canonical",
    "require_research_authority",
    "require_keys",
    "BodySpec",
    "PoleSpec",
    "HoleSpec",
    "PatternSpec",
    "CatalogSpec",
]

PATTERN_SCHEMA = "w0_g1_pattern_v1"
CATALOG_SCHEMA = "w0_g1_catalog_v1"
MASTER_RESULT_SCHEMA = "w0_g1_master_result_v1"
GEOMETRY_SCHEMA = "w0_g1_geometry_v1"
AUDIT_SCHEMA = "w0_g1_audit_v1"

ALL_SCHEMAS: Tuple[str, ...] = (
    PATTERN_SCHEMA,
    CATALOG_SCHEMA,
    MASTER_RESULT_SCHEMA,
    GEOMETRY_SCHEMA,
    AUDIT_SCHEMA,
)

#: The only authority block this line is allowed to emit.  Every field false.
RESEARCH_AUTHORITY: Dict[str, Any] = {
    "is_authoritative": False,
    "carries_bound": False,
    "ledger_effect": "none",
}

Cell = Tuple[int, int]


class SchemaError(ValueError):
    """Fail-closed parse/validation error."""


# --------------------------------------------------------------------------
# canonical bytes + strict parsing
# --------------------------------------------------------------------------


def canonical_json_text(obj: Any) -> str:
    """Deterministic text form: sorted keys, no spaces, ASCII-escaped."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def canonical_json_bytes(obj: Any) -> bytes:
    return canonical_json_text(obj).encode("utf-8")


def sha256_of_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def sha256_of_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    seen: Dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise SchemaError(f"duplicate JSON key: {key!r}")
        seen[key] = value
    return seen


def _reject_constant(name: str) -> Any:
    raise SchemaError(f"non-finite JSON constant: {name!r}")


def loads_strict(text: str) -> Any:
    return json.loads(
        text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant
    )


def load_strict(path: Path | str) -> Any:
    return loads_strict(Path(path).read_text(encoding="utf-8"))


def dump_canonical(path: Path | str, obj: Any) -> str:
    """Write ``obj`` in canonical form (LF terminated) and return its sha256."""
    payload = canonical_json_bytes(obj) + b"\n"
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return sha256_of_obj(obj)


# --------------------------------------------------------------------------
# shared field helpers
# --------------------------------------------------------------------------


def require_keys(
    obj: Any, required: Iterable[str], optional: Iterable[str] = (), *, what: str
) -> Mapping[str, Any]:
    if not isinstance(obj, dict):
        raise SchemaError(f"{what} must be a JSON object, got {type(obj).__name__}")
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - set(obj))
    if missing:
        raise SchemaError(f"{what} is missing required fields: {missing}")
    unknown = sorted(set(obj) - allowed)
    if unknown:
        raise SchemaError(f"{what} has unknown fields: {unknown}")
    return obj


def require_schema(obj: Mapping[str, Any], expected: str, *, what: str) -> None:
    actual = obj.get("schema")
    if actual != expected:
        raise SchemaError(f"{what} expects schema {expected!r}, got {actual!r}")


def require_research_authority(obj: Mapping[str, Any], *, what: str) -> None:
    """Every artifact of this line must carry the all-false authority block."""
    authority = obj.get("authority")
    if not isinstance(authority, dict):
        raise SchemaError(f"{what} is missing its authority block")
    if set(authority) != set(RESEARCH_AUTHORITY):
        raise SchemaError(
            f"{what} authority fields are {sorted(authority)}, expected "
            f"{sorted(RESEARCH_AUTHORITY)}"
        )
    for field, expected in RESEARCH_AUTHORITY.items():
        if authority[field] != expected:
            raise SchemaError(
                f"{what} authority.{field} must be {expected!r}, got "
                f"{authority[field]!r} -- this line never carries authority"
            )


def _require_int(value: Any, *, what: str, low: Optional[int] = None, high: Optional[int] = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{what} must be an integer, got {value!r}")
    if low is not None and value < low:
        raise SchemaError(f"{what} must be >= {low}, got {value}")
    if high is not None and value > high:
        raise SchemaError(f"{what} must be <= {high}, got {value}")
    return value


def require_cell(value: Any, *, what: str) -> Cell:
    if not isinstance(value, list) or len(value) != 2:
        raise SchemaError(f"{what} must be a two-element [x, y] array, got {value!r}")
    return (
        _require_int(value[0], what=f"{what}.x"),
        _require_int(value[1], what=f"{what}.y"),
    )


def require_cells(value: Any, *, what: str) -> Tuple[Cell, ...]:
    if not isinstance(value, list):
        raise SchemaError(f"{what} must be an array of cells")
    return tuple(require_cell(item, what=f"{what}[{index}]") for index, item in enumerate(value))


def _cells_json(cells: Iterable[Cell]) -> List[List[int]]:
    return [[int(x), int(y)] for x, y in cells]


# --------------------------------------------------------------------------
# pattern objects
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BodySpec:
    """A manufacturing body placed in region-local coordinates.

    Carries no operation and no class: which class a body serves is the master's
    decision, constrained only by the body's capability bucket.
    """

    bid: int
    template: str
    orientation: int
    local_anchor: Cell

    @staticmethod
    def from_json(obj: Any, *, what: str = "body") -> "BodySpec":
        payload = require_keys(
            obj, ("bid", "template", "orientation", "local_anchor"), what=what
        )
        return BodySpec(
            bid=_require_int(payload["bid"], what=f"{what}.bid", low=0),
            template=str(payload["template"]),
            orientation=_require_int(
                payload["orientation"], what=f"{what}.orientation", low=0, high=1
            ),
            local_anchor=require_cell(payload["local_anchor"], what=f"{what}.local_anchor"),
        )

    def as_json(self) -> Dict[str, Any]:
        return {
            "bid": self.bid,
            "template": self.template,
            "orientation": self.orientation,
            "local_anchor": list(self.local_anchor),
        }


@dataclass(frozen=True)
class PoleSpec:
    """A 2x2 power pole in region-local coordinates."""

    local_anchor: Cell

    @staticmethod
    def from_json(obj: Any, *, what: str = "pole") -> "PoleSpec":
        payload = require_keys(obj, ("local_anchor",), what=what)
        return PoleSpec(
            local_anchor=require_cell(payload["local_anchor"], what=f"{what}.local_anchor")
        )

    def as_json(self) -> Dict[str, Any]:
        return {"local_anchor": list(self.local_anchor)}


@dataclass(frozen=True)
class HoleSpec:
    """The candidate body-only empty rectangle, 6x7 or 7x6, region-local.

    R-HOLE-IN-REGION: at this restriction level the hole never straddles a seam.
    A cross-seam hole is upgrade rung L4 of the stage B ladder, not a v1 field.
    """

    local_anchor: Cell
    width: int
    height: int

    @staticmethod
    def from_json(obj: Any, *, what: str = "hole") -> "HoleSpec":
        payload = require_keys(obj, ("local_anchor", "width", "height"), what=what)
        width = _require_int(payload["width"], what=f"{what}.width", low=1)
        height = _require_int(payload["height"], what=f"{what}.height", low=1)
        if (width, height) not in ((6, 7), (7, 6)):
            raise SchemaError(
                f"{what} must be 6x7 or 7x6, got {width}x{height}"
            )
        return HoleSpec(
            local_anchor=require_cell(payload["local_anchor"], what=f"{what}.local_anchor"),
            width=width,
            height=height,
        )

    def as_json(self) -> Dict[str, Any]:
        return {
            "local_anchor": list(self.local_anchor),
            "width": self.width,
            "height": self.height,
        }

    @property
    def cells(self) -> Tuple[Cell, ...]:
        ax, ay = self.local_anchor
        return tuple(
            (ax + dx, ay + dy) for dx in range(self.width) for dy in range(self.height)
        )


@dataclass(frozen=True)
class PatternSpec:
    """The decision content of a pattern: what the generator chose.

    Everything else in the on-disk pattern (buckets, mode tables, class
    witnesses, the portal component digest) is *derived* and is recomputed from
    this spec by the evaluator on load.  The loader never trusts a stored
    signature -- see ``g1_pattern_evaluator.load_pattern``.
    """

    region_class: str
    bodies: Tuple[BodySpec, ...]
    poles: Tuple[PoleSpec, ...]
    hole: Optional[HoleSpec]

    @staticmethod
    def from_json(obj: Any, *, what: str = "pattern") -> "PatternSpec":
        payload = require_keys(obj, ("region_class", "bodies", "poles", "hole"), what=what)
        raw_bodies = payload["bodies"]
        raw_poles = payload["poles"]
        if not isinstance(raw_bodies, list) or not isinstance(raw_poles, list):
            raise SchemaError(f"{what}.bodies and {what}.poles must be arrays")
        hole_payload = payload["hole"]
        return PatternSpec(
            region_class=str(payload["region_class"]),
            bodies=tuple(
                BodySpec.from_json(item, what=f"{what}.bodies[{index}]")
                for index, item in enumerate(raw_bodies)
            ),
            poles=tuple(
                PoleSpec.from_json(item, what=f"{what}.poles[{index}]")
                for index, item in enumerate(raw_poles)
            ),
            hole=None if hole_payload is None else HoleSpec.from_json(hole_payload, what=f"{what}.hole"),
        )

    def as_json(self) -> Dict[str, Any]:
        return {
            "region_class": self.region_class,
            "bodies": [body.as_json() for body in self.bodies],
            "poles": [pole.as_json() for pole in self.poles],
            "hole": None if self.hole is None else self.hole.as_json(),
        }

    @property
    def pattern_id(self) -> str:
        """Content address of the decision content (first 16 hex of its sha256)."""
        return sha256_of_obj(self.as_json())[:16]


@dataclass(frozen=True)
class CatalogSpec:
    """One region class's frozen pattern catalog."""

    region_class: str
    region_multiplicity: int
    fixed_mask_sha256: str
    reserved_mask_sha256: str
    complete: bool
    patterns: Tuple[Mapping[str, Any], ...]

    @staticmethod
    def from_json(obj: Any, *, what: str = "catalog") -> "CatalogSpec":
        payload = require_keys(
            obj,
            (
                "schema",
                "authority",
                "region_class",
                "region_multiplicity",
                "fixed_mask_sha256",
                "reserved_mask_sha256",
                "complete",
                "patterns",
            ),
            what=what,
        )
        require_schema(payload, CATALOG_SCHEMA, what=what)
        require_research_authority(payload, what=what)
        patterns = payload["patterns"]
        if not isinstance(patterns, list):
            raise SchemaError(f"{what}.patterns must be an array")
        complete = payload["complete"]
        if not isinstance(complete, bool):
            raise SchemaError(f"{what}.complete must be a boolean")
        return CatalogSpec(
            region_class=str(payload["region_class"]),
            region_multiplicity=_require_int(
                payload["region_multiplicity"], what=f"{what}.region_multiplicity", low=1
            ),
            fixed_mask_sha256=str(payload["fixed_mask_sha256"]),
            reserved_mask_sha256=str(payload["reserved_mask_sha256"]),
            complete=complete,
            patterns=tuple(patterns),
        )


def mask_sha256(cells: Iterable[Cell]) -> str:
    """Content address of a cell mask, order-insensitive."""
    return sha256_of_obj(_cells_json(sorted(set(cells))))


def cells_json(cells: Iterable[Cell]) -> List[List[int]]:
    return _cells_json(cells)
