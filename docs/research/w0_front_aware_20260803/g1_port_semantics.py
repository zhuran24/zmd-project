"""W0 front-aware G1: operation-class table derived on the spot from frozen authority.

research-only.  Nothing in this module carries authority, a bound, or a ledger
effect.  It is the single source of truth for two derived objects used by the G1
pattern generator, the exact-cover master and the independent audit:

* ``CLASS_TABLE`` -- the nine mandatory manufacturing operation classes, keyed by
  ``(template, r_in, r_out)`` where ``r_in`` / ``r_out`` are the **port slot**
  counts the repository actually demands;
* ``BUCKET_SERVABLE`` -- the eight live capability buckets, i.e. every servable
  class set a manufacturing body geometry can realise.

Derivation correction: eight buckets, not eleven
------------------------------------------------
The G1 blueprint parameterised a 3x3 bucket by an independent pair ``(o, i)`` --
``o`` = best servable fan-out, ``i`` = "can serve 2-in" -- and counted six live
3x3 buckets.  Those two coordinates are not independent.  A square's mode set is
closed under swapping the two sides of a pair (``TB``/``BT``, ``RL``/``LR``), so
``o >= 2`` and ``i = 1`` are the *same* condition: a pair with ``n_X >= 1`` and
``n_Y >= 2`` is, read the other way round, a pair with ``n_Y >= 2`` and
``n_X >= 1``.  Only three 3x3 buckets are reachable (``o = 1, 2, 3``), giving
``3 + 2 + 3 = 8`` live buckets overall.  Deriving instead of transcribing is what
surfaced this; the blueprint's ``M3_o2_i0`` / ``M3_o3_i0`` / ``M3_o1_i1`` name
nothing.

Port-semantics enforcement clause (line charter section 3)
---------------------------------------------------------
The opening brief inherited from document 19 step 4 the instruction to compute
class demand as the *commodity kind count* of the frozen ``canonical_rules.json``
recipes ("every 3x3 is 1-in-1-out", ...).  Hand recomputation against the
repository shows that characterisation of repo semantics is wrong: the repo
demand SSOT is the **slot count**

    slots(c) = ceil( rate(c) / belt_capacity_per_tick ),
    rate(c)  = amount(c) / ticks_per_cycle

(``src/preprocess/operation_profiles._rate_to_slots`` +
``src/interchange/preprocess_context.PreprocessRecipe.input_rate``), and
``src/models/port_binding.routing_visible_port_demands`` sums those slots as the
per-side binding demand.  Kind counts are strictly weaker than the real demand
(``crusher_sandleaf`` genuinely needs three free output front cells, not one), so
using them would let G1 pass geometries that are dead at G3 -- the very disease
(cheap necessary condition pushed downstream) this line exists to cure.

This module therefore satisfies the *intent* of the enforcement clause -- derive
from frozen repository authority, never copy an external document's table -- with
the correct arithmetic.  ``src/tests/test_w0_g1_port_semantics.py`` pins the
result against ``routing_visible_port_demands`` row by row; any drift is a red
test, not a silent divergence.

Runtime contract: stdlib only (``json`` / ``fractions`` / ``pathlib``).  No
solver, no ``src`` import, importable under ``python -I -S -B``-style isolation
when the containing directory is on ``sys.path``.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Sequence, Tuple

__all__ = [
    "GRID_WIDTH",
    "GRID_HEIGHT",
    "MANUFACTURING_TEMPLATES",
    "TEMPLATE_SIZES",
    "TEMPLATE_PORT_RULE",
    "ClassRow",
    "ClassTable",
    "CLASS_TABLE",
    "CLASS_BY_ID",
    "CLASS_DEMAND",
    "CLASS_ORDER",
    "BUCKET_SERVABLE",
    "BUCKET_ORDER",
    "EXTERNAL_CLASS_ALIASES",
    "EXTERNAL_BUCKET_ALIASES",
    "DEFAULT_RULES_PATH",
    "DEFAULT_INSTANCES_PATH",
    "derive_class_table",
    "derive_bucket_table",
    "slots_for_amount",
    "bucket_id_for_servable",
    "servable_classes_for_side_counts",
]

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES_PATH = REPO_ROOT / "rules" / "canonical_rules.json"
DEFAULT_INSTANCES_PATH = (
    REPO_ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json"
)

GRID_WIDTH = 70
GRID_HEIGHT = 70

MANUFACTURING_TEMPLATES: Tuple[str, ...] = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)

TEMPLATE_SIZES: Dict[str, Tuple[int, int]] = {
    "manufacturing_3x3": (3, 3),
    "manufacturing_5x5": (5, 5),
    "manufacturing_6x4": (6, 4),
}

# ``port_rule`` decides which side pairs a mode may use.  Mirrors
# ``src/placement/placement_generator``: squares expose four orthogonal modes at a
# single orientation, the 6x4 rectangle exposes two modes per orientation on its
# long sides.
TEMPLATE_PORT_RULE: Dict[str, str] = {
    "manufacturing_3x3": "opposite_parallel_sides",
    "manufacturing_5x5": "opposite_parallel_sides",
    "manufacturing_6x4": "long_sides",
}

# Short template tag used when minting derived class / bucket identifiers.
_TEMPLATE_TAG: Dict[str, str] = {
    "manufacturing_3x3": "3",
    "manufacturing_5x5": "5",
    "manufacturing_6x4": "6",
}

# Names document 17 / the GPT delivery used for the same rows.  Recorded for
# cross-reading only; this line never consumes an external table.
EXTERNAL_CLASS_ALIASES: Dict[str, str] = {
    "3L": "3L",
    "3I2": "3I2",
    "3O2": "3O2",
    "3O3": "3O3",
    "5L": "5L",
    "5O2": "5O2",
    "6I3": "6G",
    "6I4": "6F",
    "6I5": "6B",
}

# Blueprint bucket names mapped onto the derived identifiers.  The three
# blueprint names absent here (``M3_o2_i0`` / ``M3_o3_i0`` / ``M3_o1_i1``) are
# geometrically unreachable; see the module docstring.
EXTERNAL_BUCKET_ALIASES: Dict[str, str] = {
    "M3_1i1o": "M3_o1_i0",
    "M3_1i2o+2i1o": "M3_o2_i1",
    "M3_1i3o+2i1o": "M3_o3_i1",
    "M5_1i1o": "M5_o1",
    "M5_1i2o": "M5_o2",
    "M6_3i1o": "M6_i3",
    "M6_4i1o": "M6_i4",
    "M6_5i1o": "M6_i5",
}


class PortSemanticsError(RuntimeError):
    """Fail-closed error for malformed or unexpected frozen input."""


@dataclass(frozen=True)
class ClassRow:
    """One mandatory operation class: a (template, r_in, r_out) demand row."""

    class_id: str
    template: str
    r_in: int
    r_out: int
    count: int
    operations: Tuple[str, ...]

    def as_json(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "template": self.template,
            "r_in": self.r_in,
            "r_out": self.r_out,
            "count": self.count,
            "operations": list(self.operations),
        }


ClassTable = Tuple[ClassRow, ...]


def _load_json(path: Path) -> Any:
    def _reject_duplicates(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
        seen: Dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                raise PortSemanticsError(f"duplicate JSON key {key!r} in {path}")
            seen[key] = value
        return seen

    def _reject_constant(name: str) -> Any:
        raise PortSemanticsError(f"non-finite JSON constant {name!r} in {path}")

    import json

    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )


def _exact_fraction(value: Any, *, what: str) -> Fraction:
    if isinstance(value, bool):
        raise PortSemanticsError(f"{what} must not be a boolean")
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    raise PortSemanticsError(f"{what} has unsupported type {type(value).__name__}")


def slots_for_amount(
    amount: Any, ticks_per_cycle: Any, belt_capacity_per_tick: Any
) -> int:
    """Repo port-slot arithmetic: ``ceil(amount / ticks / belt_capacity)``.

    Exact rational arithmetic throughout; mirrors
    ``src.preprocess.operation_profiles._rate_to_slots`` composed with
    ``PreprocessRecipe.input_rate`` / ``output_rate``.
    """
    rate = _exact_fraction(amount, what="recipe amount") / _exact_fraction(
        ticks_per_cycle, what="ticks_per_cycle"
    )
    if rate <= 0:
        return 0
    capacity = _exact_fraction(
        belt_capacity_per_tick, what="belt_capacity_per_tick"
    )
    if capacity <= 0:
        raise PortSemanticsError("belt_capacity_per_tick must be > 0")
    required = rate / capacity
    return -((-required.numerator) // required.denominator)


def _derived_class_id(template: str, r_in: int, r_out: int) -> str:
    """Deterministic identifier minted from the derived demand pair.

    ``L`` = the plain 1-in-1-out line row; ``O{n}`` = fan-out rows; ``I{n}`` =
    fan-in rows; ``I{n}O{m}`` for a hypothetical both-sided row (not reachable
    with the current frozen recipes, kept so tampered inputs still name cleanly).
    """
    tag = _TEMPLATE_TAG[template]
    if r_in == 1 and r_out == 1:
        return f"{tag}L"
    if r_in == 1:
        return f"{tag}O{r_out}"
    if r_out == 1:
        return f"{tag}I{r_in}"
    return f"{tag}I{r_in}O{r_out}"


def derive_class_table(
    rules_path: Path | str = DEFAULT_RULES_PATH,
    instances_path: Path | str = DEFAULT_INSTANCES_PATH,
) -> ClassTable:
    """Derive the mandatory manufacturing class table from frozen authority.

    Reads recipes / belt capacity out of ``canonical_rules.json`` and the
    mandatory instance census out of ``mandatory_exact_instances.json``.  Only
    operations whose template is a manufacturing template participate; the
    boundary storage ports and the protocol core are fixed furniture, not
    decision bodies, and carry generic hub slots rather than recipe slots.
    """
    rules = _load_json(Path(rules_path))
    instances = _load_json(Path(instances_path))

    try:
        belt_capacity = rules["globals"]["logistics"]["belt_capacity_per_tick"]
    except (KeyError, TypeError) as exc:
        raise PortSemanticsError(
            f"canonical rules missing globals.logistics.belt_capacity_per_tick: {exc}"
        ) from exc
    recipes = rules.get("recipes")
    if not isinstance(recipes, dict):
        raise PortSemanticsError("canonical rules missing a recipes object")
    if not isinstance(instances, list):
        raise PortSemanticsError("mandatory instances artifact must be a JSON array")

    counts: Dict[str, int] = {}
    for instance in instances:
        if not isinstance(instance, dict):
            raise PortSemanticsError("mandatory instance entries must be objects")
        operation = str(instance["operation_type"])
        counts[operation] = counts.get(operation, 0) + 1

    grouped: Dict[Tuple[str, int, int], list] = {}
    for operation in sorted(counts):
        recipe = recipes.get(operation)
        if recipe is None:
            # Fixed furniture (boundary_io / protocol_core) has no recipe.
            continue
        template = str(recipe["template"])
        if template not in MANUFACTURING_TEMPLATES:
            continue
        ticks = recipe["ticks_per_cycle"]
        r_in = sum(
            slots_for_amount(amount, ticks, belt_capacity)
            for amount in dict(recipe["inputs"]).values()
        )
        r_out = sum(
            slots_for_amount(amount, ticks, belt_capacity)
            for amount in dict(recipe["outputs"]).values()
        )
        if r_in <= 0 or r_out <= 0:
            raise PortSemanticsError(
                f"{operation} derives a degenerate demand ({r_in}, {r_out}); "
                "a manufacturing class must consume and produce"
            )
        grouped.setdefault((template, r_in, r_out), []).append(operation)

    table: list = []
    for key in sorted(
        grouped, key=lambda k: (MANUFACTURING_TEMPLATES.index(k[0]), k[1], k[2])
    ):
        template, r_in, r_out = key
        operations = tuple(sorted(grouped[key]))
        table.append(
            ClassRow(
                class_id=_derived_class_id(template, r_in, r_out),
                template=template,
                r_in=r_in,
                r_out=r_out,
                count=sum(counts[op] for op in operations),
                operations=operations,
            )
        )
    ids = [row.class_id for row in table]
    if len(set(ids)) != len(ids):
        raise PortSemanticsError(f"derived class ids are not unique: {ids}")
    return tuple(table)


def servable_classes_for_side_counts(
    template: str,
    table: ClassTable,
    mode_pairs: Iterable[Tuple[int, int]],
) -> FrozenSet[str]:
    """Classes of ``template`` servable given the per-mode ``(n_in, n_out)`` pairs.

    ``mode_pairs`` enumerates, for every mode the body geometry actually offers,
    how many *free* front cells the mode's input side and output side provide.
    A class is servable iff some single mode covers both of its demands -- exactly
    the condition ``_enumerate_side_binding_patterns`` imposes (it needs
    ``total_slots`` distinct free cells on that side of that pose).
    """
    pairs = tuple(mode_pairs)
    servable = set()
    for row in table:
        if row.template != template:
            continue
        if any(n_in >= row.r_in and n_out >= row.r_out for n_in, n_out in pairs):
            servable.add(row.class_id)
    return frozenset(servable)


def _frontier(
    servable: FrozenSet[str], table: ClassTable
) -> Tuple[Tuple[int, int], ...]:
    demands = {row.class_id: (row.r_in, row.r_out) for row in table}
    points = sorted(demands[class_id] for class_id in servable)
    maximal = [
        point
        for point in points
        if not any(
            other != point and other[0] >= point[0] and other[1] >= point[1]
            for other in points
        )
    ]
    return tuple(sorted(maximal))


def bucket_id_for_servable(
    template: str, servable: FrozenSet[str], table: ClassTable
) -> str:
    """Canonical bucket identifier derived from the servable class set.

    A servable set is downward closed in ``(r_in, r_out)``, so its maximal
    frontier determines it uniquely given the class table.  ``M3_1i3o+2i1o`` reads
    "a 3x3 body that can serve up to 1-in/3-out and up to 2-in/1-out".
    """
    if not servable:
        raise PortSemanticsError("dead bodies have no bucket")
    tag = _TEMPLATE_TAG[template]
    frontier = _frontier(servable, table)
    return f"M{tag}_" + "+".join(f"{a}i{b}o" for a, b in frontier)


def _mode_pair_space(template: str) -> Iterable[Tuple[Tuple[int, int], ...]]:
    """All per-mode ``(n_in, n_out)`` profiles a body of ``template`` can exhibit."""
    width, height = TEMPLATE_SIZES[template]
    rule = TEMPLATE_PORT_RULE[template]
    if rule == "opposite_parallel_sides":
        side = width  # squares only
        for n_top in range(side + 1):
            for n_bottom in range(side + 1):
                for n_left in range(side + 1):
                    for n_right in range(side + 1):
                        yield (
                            (n_top, n_bottom),
                            (n_bottom, n_top),
                            (n_right, n_left),
                            (n_left, n_right),
                        )
    elif rule == "long_sides":
        long_side = max(width, height)
        for n_a in range(long_side + 1):
            for n_b in range(long_side + 1):
                # A concrete body has one orientation, hence exactly the two
                # modes that swap its two long sides.
                yield ((n_a, n_b), (n_b, n_a))
    else:  # pragma: no cover - guarded by TEMPLATE_PORT_RULE
        raise PortSemanticsError(f"unsupported port rule {rule!r}")


def derive_bucket_table(table: ClassTable) -> Dict[str, FrozenSet[str]]:
    """Every live capability bucket, i.e. every reachable non-empty servable set."""
    buckets: Dict[str, FrozenSet[str]] = {}
    for template in MANUFACTURING_TEMPLATES:
        for profile in _mode_pair_space(template):
            servable = servable_classes_for_side_counts(template, table, profile)
            if not servable:
                continue
            bucket = bucket_id_for_servable(template, servable, table)
            existing = buckets.get(bucket)
            if existing is not None and existing != servable:
                raise PortSemanticsError(
                    f"bucket id {bucket!r} is ambiguous: {sorted(existing)} vs "
                    f"{sorted(servable)}"
                )
            buckets[bucket] = servable
    return buckets


CLASS_TABLE: ClassTable = derive_class_table()
CLASS_ORDER: Tuple[str, ...] = tuple(row.class_id for row in CLASS_TABLE)
CLASS_DEMAND: Dict[str, int] = {row.class_id: row.count for row in CLASS_TABLE}
CLASS_BY_ID: Dict[str, ClassRow] = {row.class_id: row for row in CLASS_TABLE}
BUCKET_SERVABLE: Dict[str, FrozenSet[str]] = derive_bucket_table(CLASS_TABLE)
BUCKET_ORDER: Tuple[str, ...] = tuple(
    sorted(BUCKET_SERVABLE, key=lambda b: (b.split("_")[0], len(BUCKET_SERVABLE[b]), b))
)


def classes_for_template(template: str, table: ClassTable = CLASS_TABLE) -> Tuple[str, ...]:
    return tuple(row.class_id for row in table if row.template == template)


def summary(table: ClassTable = CLASS_TABLE) -> Mapping[str, Any]:
    """Machine-readable digest used by the catalog manifest and the report."""
    return {
        "classes": [row.as_json() for row in table],
        "total_bodies": sum(row.count for row in table),
        "bodies_by_template": {
            template: sum(row.count for row in table if row.template == template)
            for template in MANUFACTURING_TEMPLATES
        },
        "front_demand_cells": sum(row.count * (row.r_in + row.r_out) for row in table),
        "body_area_cells": sum(
            row.count * TEMPLATE_SIZES[row.template][0] * TEMPLATE_SIZES[row.template][1]
            for row in table
        ),
        "buckets": {
            bucket: sorted(BUCKET_SERVABLE[bucket]) for bucket in BUCKET_ORDER
        },
    }


if __name__ == "__main__":  # pragma: no cover - operator convenience
    import json as _json

    print(_json.dumps(summary(), indent=2, ensure_ascii=False))
