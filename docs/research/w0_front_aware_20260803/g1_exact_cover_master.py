"""W0 front-aware G1: the exact-cover master over the frozen pattern catalog.

research-only.  No authority, no bound, no ledger effect.

Stage A froze a per-region-class pattern catalog.  This module answers the one
question the catalog was built for: **is there a way to give each of the 25
regions one pattern so that the nine operation classes come out at exactly
109 / 6 / 11 / 6 / 32 / 17 / 32 / 3 / 3 and exactly one 6x7 or 7x6 hole exists?**

The model is deliberately tiny.  Every geometric fact was already decided and
recomputed by the evaluator when the catalog was loaded, so the master sees only
two things per pattern: its capability-bucket multiset and whether it carries the
hole.  Two patterns agreeing on those are interchangeable, which is what makes a
catalog of a few hundred signatures per class enough.

Constraints, in the blueprint's numbering
-----------------------------------------
``C1``   every region takes exactly one pattern
``C2a``  bucket supply conservation: bodies of bucket *b* = classes assigned to *b*
``C2b``  every operation class gets exactly its census count
``C2c``  redundant total (219 bodies), kept because it names the failure faster
``C3``   exactly one selected pattern carries the hole
``C4``   portal compatibility -- **zero constraints** at the default level, see below
``C5``   scale gate: refuse to solve a model that outgrew the design envelope

C4 costs nothing because of ``R-PORTAL-FIXED``: every pattern leaves the same
eight stub cells body-free and neighbouring stubs are 4-adjacent across each
seam, so per-pattern connectivity composes into board-wide connectivity by
construction.  The negotiated fallback (each pattern publishing a per-edge
free-cell bitmap, one crossing variable per seam position) is upgrade rung L3 and
is not implemented here; reaching for it would mean the fixed stub layout was the
binding restriction, which is a finding, not a detail.

Registered gap -- CLOSED 2026-08-04 (fix-and-rerun batch).  The composition
argument above additionally requires every live stub of a pattern to share ONE
free component (the charter's registered R-PAT-CONN semantics).  The 2026-08-04
review found the shipped evaluator implementing the weaker
union-of-stub-components reading, so C4 = zero constraints was not backed for
witness purposes (855 of 2,593 shipped patterns had multiple stub-bearing
components); that had no effect on the batch's INFEASIBLE results, because
strengthening only deletes columns.  ``g1_pattern_evaluator.portal_component``
now floods from one canonical root and the generator carries the same
restriction as an in-model single-source flow certificate, so every pattern a
catalog can contain has one corridor and the composition argument holds again.
See docs/research/w0_front_aware_20260803/CONSULT_VERDICT_20260804.md.

The empty pattern (T-EMPTY-PATTERN)
-----------------------------------
The stage A generator only ever emitted targets with at least one body, so its
``CORE`` catalog is empty -- correctly, because ``CORE`` provably holds no
manufacturing body at all.  A master built from those files alone would report
INFEASIBLE for a bookkeeping reason ("region CORE has no pattern to take"), which
would be a false negative dressed up as a result.  So the loader synthesises the
empty pattern -- no bodies, no poles, no hole -- for every region class and puts
it through the ordinary evaluator before admitting it.  It is a legal pattern of
every class; refusing to represent it would be a modelling error, not a
restriction.

Infeasibility evidence
----------------------
C1, C2b, C2c and C3 each hang off an assumption literal, so an INFEASIBLE answer
comes back with ``sufficient_assumptions_for_infeasibility`` naming which
constraint family cannot be met.  That is the certificate the section 0b gate
order demands of an early rejection; a bare "infeasible" would not be one.

Runtime contract: stdlib + ortools.  One solve at a time, workers <= 4, single
solve time limit 1800s.  This model is thousands of variables and tens of
constraints; a prod-scale profile here means the model is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
import sys
import time
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from g1_pattern_evaluator import (  # noqa: E402
    PatternEvaluation,
    evaluate_pattern,
    load_pattern,
)
from g1_pattern_schema import (  # noqa: E402
    CatalogSpec,
    MASTER_RESULT_SCHEMA,
    PatternSpec,
    RESEARCH_AUTHORITY,
    SchemaError,
    load_strict,
    mask_sha256,
    sha256_of_bytes,
)
from g1_port_semantics import (  # noqa: E402
    BUCKET_ORDER,
    BUCKET_SERVABLE,
    CLASS_BY_ID,
    CLASS_DEMAND,
    CLASS_ORDER,
    TEMPLATE_SIZES,
)
from g1_region_model import (  # noqa: E402
    REGION_CLASS_ORDER,
    REGION_CLASSES,
)

__all__ = [
    "COLLAPSE_EQUIVALENCE",
    "EMPTY_PATTERN",
    "SCALE_MAX_VARIABLES",
    "SCALE_MAX_CONSTRAINTS",
    "MASTER_TIME_LIMIT_SECONDS",
    "MASTER_WORKERS",
    "PatternRecord",
    "RegionClassColumns",
    "MasterConfig",
    "MasterError",
    "empty_pattern_record",
    "catalog_directories",
    "load_catalogs",
    "build_master",
    "solve_master",
    "bucket_supply_ceiling",
    "class_supply_pre_gate",
]

#: T-ARCHETYPE-COLLAPSE anchor.  ``True`` means the master may represent the 16
#: geometrically identical CLEAN regions by *how many* of them take each pattern
#: instead of by which one does.  The two forms are feasibility-equivalent: any
#: assignment of patterns to interchangeable regions induces the counts, and any
#: counts summing to the multiplicity can be dealt out to the regions in a fixed
#: order.  ``src/tests/test_w0_g1_master.py`` runs both forms on the same catalog
#: and asserts they agree, which is the executable form of that argument.
COLLAPSE_EQUIVALENCE = True

#: T-EMPTY-PATTERN anchor.  The origin tag of the pattern that places nothing.
#: Legal in every region class (it is what ``CORE`` must take), and still put
#: through the evaluator before it is admitted.
EMPTY_PATTERN = "empty"

#: C5 scale gate.  Past these the model has left the design envelope and the run
#: stops with a report instead of pushing through.
SCALE_MAX_VARIABLES = 20000
SCALE_MAX_CONSTRAINTS = 200000

MASTER_TIME_LIMIT_SECONDS = 1800.0
MASTER_WORKERS = 4


class MasterError(RuntimeError):
    """Fail-closed: the catalog or the request could not become a master model."""


# --------------------------------------------------------------------------
# columns
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PatternRecord:
    """What the master is allowed to know about one pattern."""

    region_class: str
    pattern_id: str
    bucket_counts: Mapping[str, int]
    hole: bool
    body_count: int
    origin: str
    #: Cells the bodies of this pattern occupy.  Not part of what the master
    #: reasons with -- it never sees geometry -- but the cheapest binding
    #: necessary condition this line has, so it rides along for the pre-gate.
    body_area: int = 0

    @property
    def signature(self) -> Tuple[Tuple[Tuple[str, int], ...], bool]:
        return (tuple(sorted(self.bucket_counts.items())), self.hole)

    def as_json(self) -> Dict[str, Any]:
        return {
            "region_class": self.region_class,
            "pattern_id": self.pattern_id,
            "bucket_counts": dict(sorted(self.bucket_counts.items())),
            "hole": self.hole,
            "body_count": self.body_count,
            "body_area": self.body_area,
            "origin": self.origin,
        }


@dataclass(frozen=True)
class RegionClassColumns:
    """One region class's admissible columns plus the provenance of the file."""

    region_class: str
    multiplicity: int
    regions: Tuple[Tuple[int, int], ...]
    complete: bool
    catalog_sha256: Optional[str]
    patterns: Tuple[PatternRecord, ...]

    def pattern_by_id(self, pattern_id: str) -> PatternRecord:
        for record in self.patterns:
            if record.pattern_id == pattern_id:
                return record
        raise MasterError(
            f"region class {self.region_class} has no pattern {pattern_id!r}"
        )


def empty_pattern_record(region_class: str) -> Tuple[PatternRecord, PatternEvaluation]:
    """The evaluator-validated empty pattern of ``region_class`` (T-EMPTY-PATTERN)."""
    spec = PatternSpec(region_class=region_class, bodies=(), poles=(), hole=None)
    evaluation = evaluate_pattern(spec)
    if not evaluation.ok:
        raise MasterError(
            f"the empty pattern of {region_class} violates "
            f"{list(evaluation.violations)}; the region model and the evaluator "
            "disagree about what an untouched region looks like"
        )
    record = PatternRecord(
        region_class=region_class,
        pattern_id=spec.pattern_id,
        bucket_counts={},
        hole=False,
        body_count=0,
        origin=EMPTY_PATTERN,
    )
    return record, evaluation


def catalog_directories(
    catalog_dirs: Path | str | Sequence[Path | str],
) -> Tuple[Path, ...]:
    """Normalise one directory or an ordered list of them."""
    if isinstance(catalog_dirs, (str, Path)):
        return (Path(catalog_dirs),)
    directories = tuple(Path(item) for item in catalog_dirs)
    if not directories:
        raise MasterError("no catalog directory was given")
    return directories


def load_catalogs(
    catalog_dirs: Path | str | Sequence[Path | str],
    *,
    region_classes: Sequence[str] = REGION_CLASS_ORDER,
    admit_empty: bool = True,
) -> Dict[str, RegionClassColumns]:
    """Load, **recompute** and column-ise every region class catalog.

    Catalog loader iron rule (charter section 8): a stored signature is a cache,
    never evidence.  ``load_pattern`` re-runs the evaluator on the stored decision
    content and refuses the whole file on any disagreement.  The two mask digests
    are checked against the live region model as well, so a catalog generated
    against a different fixed-furniture layout cannot be consumed by accident.

    Several directories may be given.  They are unioned per region class and
    deduplicated by *signature*, first directory wins -- which is sound because a
    signature is exactly what the master can see, so two patterns sharing one are
    interchangeable by construction (T-CAPABILITY-BUCKET).  Generation passes are
    aimed at different bands of the target menu (the ordering heuristic is right
    for an average region and wrong for a dense one), and unioning their outputs
    is how a run uses more than one aim without regenerating everything.
    """
    directories = catalog_directories(catalog_dirs)
    columns: Dict[str, RegionClassColumns] = {}
    for name in region_classes:
        region = REGION_CLASSES[name]
        records: List[PatternRecord] = []
        seen: Dict[object, str] = {}
        digests: List[str] = []
        complete = True
        for directory in directories:
            path = directory / f"{name}.json"
            payload = load_strict(path)
            catalog = CatalogSpec.from_json(payload, what=f"catalog[{name}]")
            if catalog.region_class != name:
                raise MasterError(
                    f"{path} declares region class {catalog.region_class!r}, expected "
                    f"{name!r}"
                )
            if catalog.region_multiplicity != region.multiplicity:
                raise MasterError(
                    f"{path} claims multiplicity {catalog.region_multiplicity}, the "
                    f"region model says {region.multiplicity}"
                )
            if catalog.fixed_mask_sha256 != mask_sha256(region.fixed_local):
                raise MasterError(f"{path} was generated against a different fixed mask")
            if catalog.reserved_mask_sha256 != mask_sha256(region.reserved_local):
                raise MasterError(
                    f"{path} was generated against a different reserved mask"
                )
            digests.append(sha256_of_bytes(path.read_bytes()))
            complete = complete and catalog.complete

            local: Dict[object, str] = {}
            for index, stored in enumerate(catalog.patterns):
                try:
                    evaluation = load_pattern(stored, region_class=name)
                except SchemaError as exc:
                    raise MasterError(f"{path} pattern {index} rejected: {exc}") from exc
                record = PatternRecord(
                    region_class=name,
                    pattern_id=evaluation.spec.pattern_id,
                    bucket_counts=dict(sorted(evaluation.bucket_counts.items())),
                    hole=evaluation.hole is not None,
                    body_count=len(evaluation.spec.bodies),
                    body_area=sum(
                        TEMPLATE_SIZES[body.template][0] * TEMPLATE_SIZES[body.template][1]
                        for body in evaluation.spec.bodies
                    ),
                    origin="catalog",
                )
                if record.signature in local:
                    raise MasterError(
                        f"{path} carries two patterns with signature "
                        f"{record.signature!r} ({local[record.signature]} and "
                        f"{record.pattern_id}); one catalog is supposed to be "
                        "signature-deduplicated"
                    )
                local[record.signature] = record.pattern_id
                if record.signature in seen:
                    continue
                seen[record.signature] = record.pattern_id
                records.append(record)
        if admit_empty:
            empty, _evaluation = empty_pattern_record(name)
            if empty.signature not in seen:
                records.append(empty)
        columns[name] = RegionClassColumns(
            region_class=name,
            multiplicity=region.multiplicity,
            regions=region.regions,
            complete=complete,
            catalog_sha256=digests[0] if len(digests) == 1 else "+".join(digests),
            patterns=tuple(records),
        )
    return columns


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------


@dataclass
class MasterConfig:
    collapse: bool = True
    max_time_in_seconds: float = MASTER_TIME_LIMIT_SECONDS
    workers: int = MASTER_WORKERS
    seed: int = 0
    log_path: Optional[Path] = None
    hole_count: int = 1

    def as_json(self) -> Dict[str, Any]:
        return {
            "collapse": self.collapse,
            "max_time_in_seconds": self.max_time_in_seconds,
            "workers": self.workers,
            "seed": self.seed,
            "hole_count": self.hole_count,
            "log_path": None if self.log_path is None else str(self.log_path),
        }


@dataclass
class BuiltMaster:
    model: Any
    selection_vars: Dict[Tuple[str, str], Any]
    per_region_vars: Dict[Tuple[Tuple[int, int], str], Any]
    class_vars: Dict[Tuple[str, str], Any]
    families: Tuple[str, ...]
    columns: Mapping[str, RegionClassColumns]
    demand: Mapping[str, int]
    scale: Dict[str, int]


def build_master(
    columns: Mapping[str, RegionClassColumns],
    config: MasterConfig,
    *,
    demand: Mapping[str, int] = CLASS_DEMAND,
    bucket_servable: Mapping[str, FrozenSet[str]] = BUCKET_SERVABLE,
    dropped: Sequence[str] = (),
) -> BuiltMaster:
    """Build the exact-cover model.  Pure construction: nothing is solved here.

    Every gated family (C1 per region class, C2b per class, C2c, C3) is posted
    under a name.  ``dropped`` names families to leave out entirely, which is how
    the deletion-based core extraction relaxes the model -- see ``_extract_core``.
    Naming, rather than enforcement literals, is deliberate: an enforced copy of
    this model is empirically far harder for CP-SAT than the plain one (300s
    UNKNOWN versus 0.2s INFEASIBLE on the stage A catalog), and a certificate that
    costs more than the answer is a bad trade.
    """
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    posted: List[str] = []
    excluded = set(dropped)
    selection: Dict[Tuple[str, str], Any] = {}
    per_region: Dict[Tuple[Tuple[int, int], str], Any] = {}

    def post(name: str, build: Any) -> None:
        """Post one named family unless this build drops it."""
        if name in excluded:
            return
        build()
        posted.append(name)

    # ---- C1: every region takes exactly one pattern ----------------------
    for name in sorted(columns):
        block = columns[name]
        if not block.patterns:
            raise MasterError(
                f"region class {name} has no admissible pattern at all; the master "
                "would be vacuously infeasible"
            )
        if config.collapse:
            for record in block.patterns:
                selection[(name, record.pattern_id)] = model.new_int_var(
                    0, block.multiplicity, f"n[{name},{record.pattern_id}]"
                )
            post(
                f"assume_cover[{name}]",
                lambda name=name, block=block: model.add(
                    sum(selection[(name, r.pattern_id)] for r in block.patterns)
                    == block.multiplicity
                ),
            )
        else:
            for region in block.regions:
                for record in block.patterns:
                    per_region[(region, record.pattern_id)] = model.new_bool_var(
                        f"z[{region[0]}_{region[1]},{record.pattern_id}]"
                    )
                post(
                    f"assume_cover[{name},{region[0]}_{region[1]}]",
                    lambda region=region, block=block: model.add(
                        sum(per_region[(region, r.pattern_id)] for r in block.patterns)
                        == 1
                    ),
                )

    def taken(name: str, pattern_id: str) -> Any:
        if config.collapse:
            return selection[(name, pattern_id)]
        block = columns[name]
        return sum(per_region[(region, pattern_id)] for region in block.regions)

    # ---- C2a: bucket supply conservation ---------------------------------
    class_vars: Dict[Tuple[str, str], Any] = {}
    total_bodies = sum(int(count) for count in demand.values())
    for bucket in sorted(bucket_servable):
        servable = sorted(bucket_servable[bucket] & set(demand))
        supply_terms = [
            int(record.bucket_counts.get(bucket, 0)) * taken(name, record.pattern_id)
            for name in sorted(columns)
            for record in columns[name].patterns
            if record.bucket_counts.get(bucket, 0)
        ]
        for class_id in servable:
            # Upper bound is the whole census, not this class's demand: the demand
            # belongs to C2b, and letting it leak into the always-on conservation
            # family would make every infeasibility core mention C2b by accident.
            class_vars[(bucket, class_id)] = model.new_int_var(
                0, total_bodies, f"y[{bucket},{class_id}]"
            )
        supply = sum(supply_terms) if supply_terms else 0
        assigned = (
            sum(class_vars[(bucket, class_id)] for class_id in servable)
            if servable
            else 0
        )
        model.add(supply == assigned)

    # ---- C2b: exact class census ----------------------------------------
    for class_id in sorted(demand):
        carriers = [
            class_vars[(bucket, class_id)]
            for bucket in sorted(bucket_servable)
            if (bucket, class_id) in class_vars
        ]
        post(
            f"assume_class[{class_id}]",
            lambda carriers=carriers, class_id=class_id: model.add(
                (sum(carriers) if carriers else 0) == int(demand[class_id])
            ),
        )

    # ---- C2c: redundant total, kept because it names the failure faster ---
    body_terms = [
        record.body_count * taken(name, record.pattern_id)
        for name in sorted(columns)
        for record in columns[name].patterns
        if record.body_count
    ]
    post(
        "assume_total_bodies",
        lambda: model.add((sum(body_terms) if body_terms else 0) == total_bodies),
    )

    # ---- C3: exactly one hole -------------------------------------------
    hole_terms = [
        taken(name, record.pattern_id)
        for name in sorted(columns)
        for record in columns[name].patterns
        if record.hole
    ]
    post(
        "assume_hole",
        lambda: model.add(
            (sum(hole_terms) if hole_terms else 0) == int(config.hole_count)
        ),
    )

    # ---- C4: nothing.  R-PORTAL-FIXED makes seams structurally compatible.

    proto = model.proto
    scale = {
        "num_variables": len(proto.variables),
        "num_constraints": len(proto.constraints),
        "num_pattern_columns": sum(len(block.patterns) for block in columns.values()),
        "num_class_assignment_vars": len(class_vars),
    }
    return BuiltMaster(
        model=model,
        selection_vars=selection,
        per_region_vars=per_region,
        class_vars=class_vars,
        families=tuple(posted),
        columns=columns,
        demand=dict(demand),
        scale=scale,
    )


def _ortools_version() -> str:
    """The solver version, from the two places that actually carry it.

    ``cp_model`` has no ``__version__`` in ortools 9.x, so the old
    ``getattr(cp_model, "__version__", "unknown")`` recorded an unknown solver
    version in every receipt this line wrote while the run itself was perfectly
    reproducible.  The imported package carries the version; the installed
    distribution carries it as an independent second source.
    """
    try:
        import ortools

        version = str(getattr(ortools, "__version__", "") or "")
        if version:
            return version
        from importlib import metadata

        return metadata.version("ortools")
    except Exception:  # pragma: no cover - reported, never fatal
        return "unavailable"


def _selection_json(
    built: BuiltMaster, solver: Any, config: MasterConfig
) -> List[Dict[str, Any]]:
    """Deal the solution out to concrete regions, deterministically.

    Collapsed form: within a region class the regions are taken in ``(i, j)``
    lexicographic order and the patterns in ``pattern_id`` order, so the same
    solution always expands to the same board.
    """
    rows: List[Dict[str, Any]] = []
    for name in sorted(built.columns):
        block = built.columns[name]
        if config.collapse:
            queue: List[str] = []
            for record in sorted(block.patterns, key=lambda r: r.pattern_id):
                count = int(
                    solver.value(built.selection_vars[(name, record.pattern_id)])
                )
                queue.extend([record.pattern_id] * count)
            if len(queue) != block.multiplicity:  # pragma: no cover - C1 forbids it
                raise MasterError(
                    f"region class {name} selected {len(queue)} patterns for "
                    f"{block.multiplicity} regions"
                )
            for region, pattern_id in zip(block.regions, queue):
                rows.append(
                    {
                        "region": list(region),
                        "region_class": name,
                        "pattern_id": pattern_id,
                    }
                )
        else:
            for region in block.regions:
                chosen = [
                    record.pattern_id
                    for record in sorted(block.patterns, key=lambda r: r.pattern_id)
                    if solver.value(built.per_region_vars[(region, record.pattern_id)])
                ]
                if len(chosen) != 1:  # pragma: no cover - C1 forbids it
                    raise MasterError(f"region {region} selected {len(chosen)} patterns")
                rows.append(
                    {
                        "region": list(region),
                        "region_class": name,
                        "pattern_id": chosen[0],
                    }
                )
    rows.sort(key=lambda row: (row["region"][0], row["region"][1]))
    return rows


def solve_master(
    columns: Mapping[str, RegionClassColumns],
    config: MasterConfig,
    *,
    demand: Mapping[str, int] = CLASS_DEMAND,
    bucket_servable: Mapping[str, FrozenSet[str]] = BUCKET_SERVABLE,
    catalog_manifest_sha256: Optional[str] = None,
    core_seconds: float = 60.0,
) -> Dict[str, Any]:
    """Build, gate on scale, solve, and return the ``w0_g1_master_result_v1`` doc."""
    from ortools.sat.python import cp_model

    built = build_master(columns, config, demand=demand, bucket_servable=bucket_servable)
    catalog_summary = {
        name: {
            "multiplicity": columns[name].multiplicity,
            "patterns": len(columns[name].patterns),
            "complete": columns[name].complete,
            "sha256": columns[name].catalog_sha256,
        }
        for name in sorted(columns)
    }
    base: Dict[str, Any] = {
        "schema": MASTER_RESULT_SCHEMA,
        "authority": dict(RESEARCH_AUTHORITY),
        "config": config.as_json(),
        "catalog_manifest_sha256": catalog_manifest_sha256,
        "catalogs": catalog_summary,
        "demand": dict(sorted(demand.items())),
        "scale": built.scale,
        "selection": [],
        "class_assignment": [],
        "infeasibility_core": None,
        "stats": {},
    }

    # ---- C5 scale gate ---------------------------------------------------
    if (
        built.scale["num_variables"] > SCALE_MAX_VARIABLES
        or built.scale["num_constraints"] > SCALE_MAX_CONSTRAINTS
    ):
        base["status"] = "SCALE_ABORT"
        base["scale_limits"] = {
            "max_variables": SCALE_MAX_VARIABLES,
            "max_constraints": SCALE_MAX_CONSTRAINTS,
        }
        base["stats"] = {"wall_time": 0.0, "solved": False}
        return base

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(config.max_time_in_seconds)
    solver.parameters.num_workers = int(config.workers)
    solver.parameters.random_seed = int(config.seed)
    solver.parameters.log_search_progress = config.log_path is not None
    log_lines: List[str] = []
    if config.log_path is not None:
        solver.log_callback = log_lines.append

    started = time.monotonic()
    status = solver.solve(built.model)
    wall = time.monotonic() - started

    if config.log_path is not None:
        Path(config.log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(config.log_path).write_text("".join(log_lines), encoding="utf-8")

    base["status"] = solver.status_name(status)
    base["stats"] = {
        "wall_time": round(wall, 3),
        "solver_wall_time": round(solver.wall_time, 3),
        "workers": int(config.workers),
        "cpsat_version": _ortools_version(),
        "python": platform.python_version(),
        "branches": int(solver.num_branches),
        "conflicts": int(solver.num_conflicts),
        "solved": True,
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        base["selection"] = _selection_json(built, solver, config)
        base["class_assignment"] = [
            {"bucket": bucket, "class": class_id, "count": int(solver.value(var))}
            for (bucket, class_id), var in sorted(built.class_vars.items())
            if int(solver.value(var))
        ]
        return base

    if status == cp_model.INFEASIBLE:
        core_report = _extract_core(
            columns,
            config,
            demand=demand,
            bucket_servable=bucket_servable,
            seconds=min(float(config.max_time_in_seconds), core_seconds),
        )
        base["infeasibility_core"] = core_report["core"]
        base["infeasibility_core_detail"] = {
            key: value for key, value in core_report.items() if key != "core"
        }
    return base


def _family_order(families: Sequence[str]) -> List[str]:
    """Deletion order for the core search: try to drop the least telling first.

    The hole family goes first, then the per-region-class cover families, then the
    per-class census families, and ``assume_total_bodies`` last.  Deletion-based
    extraction returns *a* minimal infeasible subset and which one depends on the
    order, so the order is fixed and stated rather than incidental: what survives
    at the end is the tightest, most specific accusation available.
    """
    def rank(name: str) -> Tuple[int, str]:
        if name == "assume_hole":
            return (0, name)
        if name.startswith("assume_cover["):
            return (1, name)
        if name.startswith("assume_class["):
            return (2, name)
        return (3, name)

    return sorted(families, key=rank)


def _extract_core(
    columns: Mapping[str, RegionClassColumns],
    config: MasterConfig,
    *,
    demand: Mapping[str, int],
    bucket_servable: Mapping[str, FrozenSet[str]],
    seconds: float,
) -> Dict[str, Any]:
    """Deletion-based infeasible core over the *named constraint families*.

    Start from the full model, which is known INFEASIBLE.  Walk the families in a
    fixed order; drop one, rebuild, re-solve.  If the model is still INFEASIBLE
    the family is not needed and stays dropped, otherwise it goes back.  What
    remains is a minimal infeasible subset: remove any one of its families and the
    instance becomes satisfiable.

    Why not CP-SAT's own assumption core: the enforcement-literal copy of this
    model is dramatically harder than the plain one (measured: 300s UNKNOWN
    against 0.2s INFEASIBLE), so the built-in facility cannot even reach the
    answer.  Deletion pays one cheap solve per family instead.

    Honesty about minimality: a solve that returns UNKNOWN inside the budget keeps
    its family (dropping it is not justified), and the report says so via
    ``proved_minimal``.  A non-minimal core is still a sufficient explanation --
    it is just not the tightest one.

    Cost is bounded by one solve per family at ``seconds`` each; the default
    budget is 60s a solve against a model that answers in fractions of a second,
    so the loop is cheap in practice and cannot run away in the worst case.
    """
    from ortools.sat.python import cp_model

    probe = build_master(
        columns, config, demand=demand, bucket_servable=bucket_servable
    )
    order = _family_order(probe.families)
    started = time.monotonic()
    solves = 0
    undecided: List[str] = []
    dropped: List[str] = []

    def infeasible_without(candidates: Sequence[str]) -> Optional[bool]:
        nonlocal solves
        built = build_master(
            columns,
            config,
            demand=demand,
            bucket_servable=bucket_servable,
            dropped=candidates,
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(seconds)
        solver.parameters.num_workers = int(config.workers)
        solver.parameters.random_seed = int(config.seed)
        status = solver.solve(built.model)
        solves += 1
        if status == cp_model.INFEASIBLE:
            return True
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return False
        return None

    for family in order:
        verdict = infeasible_without(dropped + [family])
        if verdict is True:
            dropped.append(family)
        elif verdict is None:
            undecided.append(family)

    core = sorted(name for name in order if name not in set(dropped))
    return {
        "core": core,
        "status": "deletion_core",
        "proved_minimal": not undecided,
        "undecided_families": sorted(undecided),
        "solves": solves,
        "families_total": len(order),
        "wall_time": round(time.monotonic() - started, 3),
    }


def bucket_supply_ceiling(
    columns: Mapping[str, RegionClassColumns],
) -> Dict[str, int]:
    """Per bucket, the largest supply any selection could produce.

    Independent of the master and much cheaper: take, for each region class, the
    pattern with the most bodies of that bucket, times the class multiplicity.

    The buckets counted are the frozen ones *plus* whatever the columns actually
    carry.  Missing a bucket the catalog uses would under-count supply, and an
    under-counted ceiling is the one error direction this pre-gate cannot afford:
    it would accuse a catalog of a shortage it does not have.
    """
    ceiling: Dict[str, int] = {}
    present = {
        bucket
        for block in columns.values()
        for record in block.patterns
        for bucket in record.bucket_counts
    }
    for bucket in sorted(set(BUCKET_ORDER) | present):
        total = 0
        for name in sorted(columns):
            block = columns[name]
            best = max(
                (int(record.bucket_counts.get(bucket, 0)) for record in block.patterns),
                default=0,
            )
            total += best * block.multiplicity
        ceiling[bucket] = total
    return ceiling


def class_supply_pre_gate(
    columns: Mapping[str, RegionClassColumns],
    *,
    demand: Mapping[str, int] = CLASS_DEMAND,
    bucket_servable: Mapping[str, FrozenSet[str]] = BUCKET_SERVABLE,
) -> Dict[str, Any]:
    """Arithmetic pre-gate over classes (blueprint section 11 item 4).

    The bodies serving a class must come from buckets that can serve it, so the
    summed bucket supply ceiling bounds what any selection could deliver.  The
    ceiling takes each region class's best pattern independently and therefore
    over-counts: ``supply < demand`` proves this catalog cannot cover the census,
    while ``supply >= demand`` excludes nothing.
    """
    ceiling = bucket_supply_ceiling(columns)
    ordered = [class_id for class_id in CLASS_ORDER if class_id in demand]
    ordered.extend(sorted(set(demand) - set(ordered)))
    findings: List[Dict[str, Any]] = []
    for class_id in ordered:
        supply = sum(
            ceiling[bucket]
            for bucket in ceiling
            if class_id in bucket_servable.get(bucket, frozenset())
        )
        need = int(demand[class_id])
        findings.append(
            {
                "class": class_id,
                "supply_ceiling": supply,
                "demand": need,
                "short": supply < need,
            }
        )
    findings.extend(_count_pre_gates(columns, demand))
    shortfalls = [entry for entry in findings if entry["short"]]
    return {
        "bucket_supply_ceiling": ceiling,
        "classes": findings,
        "verdict": "SHORT" if shortfalls else "NOT_EXCLUDED",
        "shortfalls": shortfalls,
        "reading": (
            "supply_ceiling takes the best pattern per region class independently, so "
            "it over-counts. supply < demand therefore proves this catalog cannot "
            "cover the census; supply >= demand excludes nothing."
        ),
    }


def _area_demand(demand: Mapping[str, int]) -> Optional[int]:
    """Cells the given class demand occupies, or ``None`` if it is not derivable.

    Each class fixes its template, hence its footprint, so any demand over the
    frozen classes has an area.  An unknown class id means the caller is running a
    synthetic vocabulary and no area statement can be made about it.
    """
    total = 0
    for class_id, count in demand.items():
        row = CLASS_BY_ID.get(class_id)
        if row is None:
            return None
        width, height = TEMPLATE_SIZES[row.template]
        total += int(count) * width * height
    return total


def _count_pre_gates(
    columns: Mapping[str, RegionClassColumns], demand: Mapping[str, int]
) -> List[Dict[str, Any]]:
    """Two more ceilings from the same over-counting argument.

    ``__body_area__`` -- the census fixes how many cells the 219 bodies occupy
    (3325), so the same "best pattern per region class, independently" ceiling
    applies to occupied area.  It is the tightest of the three in practice,
    because a catalog can hold plenty of *bodies* while its dense patterns are all
    3x3.
    ``__total_bodies__`` -- every region takes one pattern, so the board can hold
    at most the sum over region classes of (best body count in that class) times
    its multiplicity.  Below 219 the catalog is provably short, no solve needed.
    ``__template:M3__`` and friends do the same per template family, which is
    where a shortage can hide from both totals.

    The area rows follow the ``demand`` they are given: each class's bodies occupy
    its template's footprint, so the area demand is derivable from any demand whose
    classes are real.  A demand naming classes outside the frozen table has no
    derivable area, and the rows then carry ``demand: None`` and ``short: False``
    -- a row that cannot decide must not accuse.  (Reading a synthetic catalog's
    area against the real 3325 census is exactly the spurious ``SHORT`` this
    avoids.)
    """
    rows: List[Dict[str, Any]] = []
    area_ceiling = sum(
        max((record.body_area for record in block.patterns), default=0)
        * block.multiplicity
        for block in columns.values()
    )
    area_demand = _area_demand(demand)
    rows.append(
        {
            "class": "__body_area__",
            "supply_ceiling": area_ceiling,
            "demand": area_demand,
            "short": area_demand is not None and area_ceiling < area_demand,
        }
    )
    # Sharper.  Exactly one region has to carry the hole, and a hole-carrying
    # pattern of a region class is never denser than that class's densest pattern
    # -- the hole is 42 body-free cells.  So the board gives up at least the
    # cheapest such penalty, whichever region ends up holding it.  A region class
    # with no hole-carrying pattern simply cannot be the one that does.
    penalties = []
    for block in columns.values():
        best = max((record.body_area for record in block.patterns), default=0)
        with_hole = max(
            (record.body_area for record in block.patterns if record.hole), default=None
        )
        if with_hole is not None:
            penalties.append(best - with_hole)
    if penalties:
        holed = area_ceiling - min(penalties)
        rows.append(
            {
                "class": "__body_area_with_hole__",
                "supply_ceiling": holed,
                "demand": area_demand,
                "short": area_demand is not None and holed < area_demand,
            }
        )
    total_ceiling = sum(
        max((record.body_count for record in block.patterns), default=0)
        * block.multiplicity
        for block in columns.values()
    )
    total_demand = sum(int(count) for count in demand.values())
    rows.append(
        {
            "class": "__total_bodies__",
            "supply_ceiling": total_ceiling,
            "demand": total_demand,
            "short": total_ceiling < total_demand,
        }
    )
    for tag in ("M3", "M5", "M6"):
        family = {
            class_id
            for bucket, servable in BUCKET_SERVABLE.items()
            if bucket.startswith(f"{tag}_")
            for class_id in servable
        }
        need = sum(int(demand[class_id]) for class_id in family if class_id in demand)
        if not need:
            continue
        ceiling = sum(
            max(
                (
                    sum(
                        count
                        for bucket, count in record.bucket_counts.items()
                        if bucket.startswith(f"{tag}_")
                    )
                    for record in block.patterns
                ),
                default=0,
            )
            * block.multiplicity
            for block in columns.values()
        )
        rows.append(
            {
                "class": f"__template:{tag}__",
                "supply_ceiling": ceiling,
                "demand": need,
                "short": ceiling < need,
            }
        )
    return rows
