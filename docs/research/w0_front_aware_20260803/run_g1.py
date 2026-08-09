"""W0 front-aware G1: the run orchestrator.

research-only.  No authority, no bound, no ledger effect.

Six subcommands, in pipeline order::

    generate   build the per-region-class pattern catalog (stage A engine)
    precheck   cheap arithmetic pre-gates over the catalog and the region model
    solve      exact-cover master over a frozen catalog
    expand     master answer -> full 70x70 geometry
    audit      independent front-viability audit, in an isolated child process
    gate       precheck -> solve -> expand -> audit -> the six-clause G1 verdict

Everything except ``generate`` writes into an **exclusively created** run root via
``devtools.research_run_contract``: the directory must not already exist, every
artifact is written once with ``O_EXCL``, and the run closes with a receipt whose
identity graph plus root-closure check together say "this directory is exactly
these files and nothing else".  A run that cannot close its root is a run whose
evidence cannot be trusted, so the closure check is fatal, not advisory.

The G1 verdict (charter section 2) is PASS only when all six hold:

1. the master returned OPTIMAL or FEASIBLE and the catalog digests it recorded
   match the catalog actually on disk;
2. expansion succeeded, the pole set was globally minimised, and the geometry
   parses strictly;
3. the independent audit says ``PASS`` with an empty issue list, in particular
   ``dead_for_any_actual_class == 0`` and a nine-row exact class census;
4. the audit process itself reported that it could not import ortools and had
   loaded no module of this line, and the geometry digest it recorded equals the
   digest this process computed;
5. the run root closes: it contains exactly the artifacts this run wrote, checked
   *before* any receipt exists, and the receipt is removed again if the check
   after writing it fails;
6. **every open obligation of the registry is discharged on this run's own
   artifacts.**  The registry says ``must_close_before: any G1 PASS``; until
   2026-08-04 nothing in this file read that field, so a PASS could be minted
   with the obligation still open.  Clause six closes that: the obligation list
   is read from ``derived_theorems.json``, each id is looked up in
   ``OBLIGATION_CHECKS``, and an id with no implemented check counts as *not*
   discharged.  Registering a new obligation therefore blocks PASS by itself,
   which is the direction a fail-closed gate has to fail.

Clause six is additionally a hard precondition of ``_terminal_state``, not only
one more ``ok`` flag in the conjunction: a run whose obligations are open reports
``OBLIGATION_OPEN`` and can never spell PASS, whatever the other clauses say.
That is a BLOCK/repair terminal in the charter's four-way split, never a science
terminal -- it says the gate is not entitled to an opinion yet.

Anything else is "G1 not passed" and the stopping report rules of charter
section 9 apply -- in particular the wording stays inside *this catalog, this
class table, this hole vocabulary, this restriction level*.

Runtime contract: stdlib + ortools (only the master and the generator touch the
solver).  One solve at a time.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if __package__ in {None, ""}:
    for _path in (str(_HERE), str(_REPO_ROOT)):
        if _path not in sys.path:
            sys.path.insert(0, _path)

from devtools.research_run_contract import (  # noqa: E402
    ARTIFACT_ROOT_MANIFEST_SCHEMA,
    TERMINAL_RECEIPT_PATH,
    ExclusiveRunRoot,
    ResearchRunContractError,
    make_research_run_config,
    make_research_run_receipt,
    verify_artifact_root_closure,
)
from g1_exact_cover_master import (  # noqa: E402
    MasterConfig,
    class_supply_pre_gate,
    load_catalogs,
    solve_master,
)
from g1_expand_solution import expand_master_solution, summarise  # noqa: E402
from g1_pattern_evaluator import (  # noqa: E402
    modes_for,
    pole_cells,
    side_front_cells,
)
from g1_pattern_schema import (  # noqa: E402
    canonical_json_bytes,
    load_strict,
    loads_strict,
    sha256_of_bytes,
)
from g1_port_semantics import (  # noqa: E402
    CLASS_BY_ID,
    CLASS_TABLE,
    DEFAULT_INSTANCES_PATH,
    DEFAULT_RULES_PATH,
    GRID_HEIGHT,
    GRID_WIDTH,
    TEMPLATE_SIZES,
)
from g1_region_model import (  # noqa: E402
    FIXED_FURNITURE,
    REGION_CLASS_ORDER,
    TOTAL_USABLE_CELLS,
)

__all__ = [
    "AUDIT_SCRIPT",
    "DEFAULT_GENERIC_IO_PATH",
    "GATE_CLAUSES",
    "OBLIGATION_CHECKS",
    "REGISTRY_PATH",
    "GenericIoContractError",
    "ObligationOpen",
    "RunPaths",
    "check_front_simultaneity",
    "discharge_open_obligations",
    "main",
]

AUDIT_SCRIPT = _HERE / "front_viability_audit.py"

#: The machine-readable theorem/obligation registry this gate answers to.
REGISTRY_PATH = _HERE / "derived_theorems.json"

#: The frozen generic-IO contract: how many resource-source slots the board has to
#: offer and how many final-product sink slots it has to absorb.  Consumed and
#: digest-bound by every run, see ``_generic_io_contract``.
DEFAULT_GENERIC_IO_PATH = (
    _REPO_ROOT / "data" / "preprocessed" / "generic_io_requirements.json"
)

#: The six clauses of the G1 verdict, in the charter's order.  Reported one by
#: one so a failure names itself instead of collapsing into "not PASS".
GATE_CLAUSES: Tuple[str, ...] = (
    "master_terminal_and_catalog_bound",
    "expansion_and_pole_minimisation",
    "independent_audit_clean",
    "audit_isolated_and_digest_bound",
    "receipt_closed",
    "open_obligations_discharged",
)

#: The terminal state a run reports when clause six is not satisfied.  Not a
#: science terminal: it says the gate may not speak, not that the geometry is bad.
OBLIGATION_OPEN = "OBLIGATION_OPEN"


class GenericIoContractError(RuntimeError):
    """Fail-closed: the pinned furniture cannot carry the frozen generic-IO contract."""


class ObligationOpen(RuntimeError):
    """Fail-closed: the obligation registry itself cannot be read as a list.

    Raised only for structural damage -- the ``open_obligations`` key missing or
    not a list.  An obligation that is *present and undischarged* is a clause-six
    failure, reported in the gate document; a registry the gate cannot read at all
    is not something to report a verdict about.
    """


@dataclass(frozen=True)
class RunPaths:
    catalogs: Tuple[Path, ...]
    rules: Path
    instances: Path
    generic_io: Path = DEFAULT_GENERIC_IO_PATH


def _fixed_furniture_port_supply() -> Dict[str, int]:
    """Split the pinned furniture's port front cells into sources and sinks.

    Every ``boundary_storage_port`` front is a resource source, i.e. a generic
    *output* slot.  The protocol core sits at orientation 1
    (``inputs_east_west``), so its east/west fronts are its inputs and its
    north/south fronts its outputs; the split is read off the geometry rather
    than hard-coded, so a change to the pinned layout moves this count with it.
    """
    outputs = 0
    inputs = 0
    for item in FIXED_FURNITURE:
        if item.kind == "boundary_storage_port":
            outputs += len(item.front_cells)
            continue
        if item.kind != "protocol_core":  # pragma: no cover - the layout is pinned
            raise GenericIoContractError(
                f"unknown fixed furniture kind {item.kind!r}; the generic-IO split "
                "is only defined for the pinned W0 layout"
            )
        anchor_x, anchor_y = item.anchor
        width, height = item.size
        for cell in item.front_cells:
            if not anchor_x <= cell[0] < anchor_x + width:
                inputs += 1
            elif not anchor_y <= cell[1] < anchor_y + height:
                outputs += 1
            else:  # pragma: no cover - a front cell is outside the body by definition
                raise GenericIoContractError(f"front cell {cell} is inside its body")
    return {"outputs": outputs, "inputs": inputs}


def _generic_io_contract(path: Path) -> Dict[str, Any]:
    """Consume the frozen generic-IO requirements and bind them to this board.

    The requirement is a slot count on each side: resource sources the board has
    to offer (``required_generic_outputs``) and final-product sinks it has to
    absorb (``required_generic_inputs``).  Only the pinned furniture can serve
    either -- manufacturing bodies are neither -- so the check is a constant, and
    a constant that fails means the restriction level is dead before the master
    runs.  Fail-closed: a shortfall raises instead of being filed as a finding.
    """
    # Same single-read rule as ``discharge_open_obligations``: the reported
    # sha256/size and the parsed contract come from one read of one byte string.
    payload = path.read_bytes()
    document = loads_strict(payload.decode("utf-8"))
    if not isinstance(document, Mapping):  # pragma: no cover - strict loader shape
        raise GenericIoContractError(f"{path} is not a JSON object")
    required_outputs = sum(
        int(value) for value in dict(document["required_generic_outputs"]).values()
    )
    required_inputs = sum(
        int(value) for value in dict(document["required_generic_inputs"]).values()
    )
    supply = _fixed_furniture_port_supply()
    covered = (
        required_outputs <= supply["outputs"] and required_inputs <= supply["inputs"]
    )
    report = {
        "path": str(path),
        "sha256": sha256_of_bytes(payload),
        "size_bytes": len(payload),
        "required_generic_output_slots": required_outputs,
        "required_generic_input_slots": required_inputs,
        "fixed_furniture_output_ports": supply["outputs"],
        "fixed_furniture_input_ports": supply["inputs"],
        "covered": covered,
        "reading": (
            "Only pinned furniture serves generic IO. The 46 boundary storage "
            "ports plus the protocol core's outputs carry the required source "
            "slots; the core's inputs absorb the required sink slots. All of "
            "these front cells are kept body-free by R-CORE-FRONT-RESERVE."
        ),
    }
    if not covered:
        raise GenericIoContractError(
            f"the pinned furniture cannot carry the generic-IO contract: {report}"
        )
    return report


# --------------------------------------------------------------------------
# clause six: discharging the registry's open obligations
# --------------------------------------------------------------------------


def _board_free_cells(geometry: Mapping[str, Any]) -> set:
    """Every board cell no facility body and no pole occupies.

    Recomputed from the geometry rather than carried alongside it, for the same
    reason the audit recomputes it: a number that travels with the artifact it
    describes is not evidence about that artifact.
    """
    occupied: set = set()
    for item in geometry["fixed_furniture"]:
        anchor_x, anchor_y = int(item["anchor"][0]), int(item["anchor"][1])
        width, height = int(item["size"][0]), int(item["size"][1])
        for dx in range(width):
            for dy in range(height):
                occupied.add((anchor_x + dx, anchor_y + dy))
    for placement in geometry["placements"]:
        anchor_x, anchor_y = int(placement["anchor"][0]), int(placement["anchor"][1])
        width, height = int(placement["size"][0]), int(placement["size"][1])
        for dx in range(width):
            for dy in range(height):
                occupied.add((anchor_x + dx, anchor_y + dy))
    for pole in geometry["power_poles"]:
        anchor = (int(pole["anchor"][0]), int(pole["anchor"][1]))
        occupied.update(pole_cells(anchor))
    return {
        (x, y)
        for x in range(GRID_WIDTH)
        for y in range(GRID_HEIGHT)
        if (x, y) not in occupied
    }


def _component_of(free: set, seeds: Sequence[Tuple[int, int]]) -> set:
    """The 4-connected free component holding ``seeds[0]`` (empty if none)."""
    roots = [cell for cell in seeds if cell in free]
    if not roots:
        return set()
    stack = [min(roots)]
    seen = set(stack)
    while stack:
        x, y = stack.pop()
        for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if neighbour in free and neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def _match_distinct_representatives(
    demands: Sequence[Tuple[str, Tuple[Tuple[int, int], ...]]]
) -> Dict[str, Optional[Tuple[int, int]]]:
    """Kuhn's algorithm: one distinct cell per demand, or ``None`` where it fails.

    Deterministic -- demands are processed in the order given and each demand's
    candidates in sorted order -- so the same geometry always yields the same
    witness, which is what makes the witness quotable.  Written iteratively
    because the augmenting path can be as long as the number of demands (574 at
    full census), and a recursive version would be one interpreter default away
    from a RecursionError inside a gate.
    """
    candidates = {label: tuple(sorted(cells)) for label, cells in demands}
    holder_of: Dict[Tuple[int, int], str] = {}
    cell_of: Dict[str, Tuple[int, int]] = {}

    def augment(start: str) -> bool:
        visited: set = set()
        reached_by: Dict[Tuple[int, int], str] = {}
        stack: List[Tuple[str, List[Tuple[int, int]]]] = [
            (start, list(candidates[start]))
        ]
        while stack:
            label, pending = stack[-1]
            cell: Optional[Tuple[int, int]] = None
            while pending:
                option = pending.pop(0)
                if option in visited:
                    continue
                visited.add(option)
                cell = option
                break
            if cell is None:
                stack.pop()
                continue
            reached_by[cell] = label
            holder = holder_of.get(cell)
            if holder is None:
                # Free cell: walk the alternating chain back to ``start``.
                while True:
                    owner = reached_by[cell]
                    previous = cell_of.get(owner)
                    holder_of[cell] = owner
                    cell_of[owner] = cell
                    if previous is None:
                        return True
                    cell = previous
            stack.append((holder, list(candidates[holder])))
        return False

    for label, _cells in demands:
        augment(label)
    return {label: cell_of.get(label) for label, _cells in demands}


def check_front_simultaneity(geometry: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Discharge ``O-FRONT-SIMULTANEITY`` on one expanded geometry.

    The obligation: capability is computed per body, and nothing downstream
    requires that all bodies can take **pairwise distinct** active front cells at
    the same time.  The registry offers two ways to close it; this is the first
    one -- an actual distinct-representatives check -- run on the batch's own
    product, because the answer depends on the master's class assignment and so
    cannot be settled ahead of the solve.

    Each placed body demands ``r_in`` input slots and ``r_out`` output slots from
    its assigned operation class.  A slot may be filled by any front cell on the
    matching side of the recorded mode that is body-free **and on the same
    free-space corridor as the geometry's active fronts** -- restricting to the
    corridor is what keeps the witness honest, because a cell no belt can reach
    is not a representative.  A perfect matching is an explicit simultaneous
    assignment, so finding one *proves* the obligation for this geometry; failing
    to find one proves nothing either way and therefore blocks the gate.

    Conservative on purpose: the check answers "is there a witness", never "the
    sharing is illegal".
    """
    report: Dict[str, Any] = {
        "obligation": "O-FRONT-SIMULTANEITY",
        "method": "distinct representatives (bipartite matching) over the run's geometry",
        "discharged": False,
    }
    if geometry is None:
        report["reason"] = "no geometry: the master produced nothing to check"
        return report

    free = _board_free_cells(geometry)
    seeds: List[Tuple[int, int]] = []
    for placement in geometry["placements"]:
        for key in ("active_input_fronts", "active_output_fronts"):
            for cell in placement[key]:
                seeds.append((int(cell[0]), int(cell[1])))
    corridor = _component_of(free, sorted(seeds))
    off_corridor = sorted(cell for cell in seeds if cell not in corridor)

    demands: List[Tuple[str, Tuple[Tuple[int, int], ...]]] = []
    shared_candidates: Dict[Tuple[int, int], int] = {}
    for index, placement in enumerate(geometry["placements"]):
        template = str(placement["template"])
        orientation = int(placement["orientation"])
        anchor = (int(placement["anchor"][0]), int(placement["anchor"][1]))
        mode_id = str(placement["mode"])
        row = CLASS_BY_ID[str(placement["operation_class"])]
        spec = next(
            (item for item in modes_for(template, orientation) if item.mode == mode_id),
            None,
        )
        if spec is None:
            report["reason"] = (
                f"placement {index} records mode {mode_id!r}, which {template} at "
                f"orientation {orientation} does not offer"
            )
            return report
        for side, count, kind in (
            (spec.in_side, row.r_in, "in"),
            (spec.out_side, row.r_out, "out"),
        ):
            pool = tuple(
                cell
                for cell in side_front_cells(template, orientation, anchor, side)
                if cell in corridor
            )
            for cell in pool:
                shared_candidates[cell] = shared_candidates.get(cell, 0) + 1
            for slot in range(count):
                demands.append((f"{index}:{kind}:{slot}", pool))

    matched = _match_distinct_representatives(demands)
    unmatched = sorted(label for label, cell in matched.items() if cell is None)
    shared = sorted(cell for cell, uses in shared_candidates.items() if uses > 1)

    report.update(
        {
            "discharged": not unmatched and not off_corridor,
            "bodies": len(geometry["placements"]),
            "front_slots_demanded": len(demands),
            "front_slots_matched": len(demands) - len(unmatched),
            "unmatched_slots": unmatched[:20],
            "recorded_active_fronts_off_corridor": [list(c) for c in off_corridor[:20]],
            "candidate_cells_wanted_by_several_bodies": len(shared),
            "witness_sha256": sha256_of_bytes(
                canonical_json_bytes(
                    {
                        label: None if cell is None else [cell[0], cell[1]]
                        for label, cell in sorted(matched.items())
                    }
                )
            ),
            "reading": (
                "A full matching is an explicit simultaneous choice of pairwise "
                "distinct active fronts, which is exactly what the obligation "
                "asks for. An incomplete matching is not a proof that the "
                "sharing is illegal -- it is the absence of a witness, and the "
                "gate refuses to pass without one."
            ),
        }
    )
    report["witness"] = {
        label: None if cell is None else [cell[0], cell[1]]
        for label, cell in sorted(matched.items())
    }
    return report


#: obligation id -> the function that may discharge it.  An id in the registry
#: with no entry here is *not* discharged, so registering an obligation blocks
#: PASS until someone writes its check.
OBLIGATION_CHECKS: Dict[str, Any] = {
    "O-FRONT-SIMULTANEITY": check_front_simultaneity,
}


def discharge_open_obligations(
    geometry: Optional[Mapping[str, Any]], *, registry_path: Path = REGISTRY_PATH
) -> Dict[str, Any]:
    """Clause six: read the registry's obligations and try to discharge each one.

    The registry is the authority on *which* obligations exist -- this file does
    not keep its own list, because a second list is a list that drifts.  The
    registry is digest-bound into the report so a run states which version of the
    obligation set it answered to.
    """
    # One read, one set of bytes: the digest this report publishes and the
    # obligation list it decided against are the *same* bytes.  Reading the file
    # twice (hash it, then parse it) leaves a window in which the second read can
    # see a different file, and the report would then swear to a digest that no
    # longer describes what the gate looked at.
    payload = registry_path.read_bytes()
    registry = loads_strict(payload.decode("utf-8"))
    raw = registry.get("open_obligations") if isinstance(registry, Mapping) else None
    if not isinstance(raw, list):
        raise ObligationOpen(
            f"{registry_path} carries no open_obligations list; the gate cannot "
            "decide clause six against a registry it cannot read"
        )
    entries = list(raw)
    results: List[Dict[str, Any]] = []
    for entry in entries:
        obligation_id = str(entry["id"])
        checker = OBLIGATION_CHECKS.get(obligation_id)
        if checker is None:
            results.append(
                {
                    "id": obligation_id,
                    "must_close_before": str(entry["must_close_before"]),
                    "checker": None,
                    "discharged": False,
                    "detail": {
                        "reason": (
                            "no discharge check is implemented for this "
                            "obligation; a registered obligation blocks PASS "
                            "until one is"
                        )
                    },
                }
            )
            continue
        detail = checker(geometry)
        results.append(
            {
                "id": obligation_id,
                "must_close_before": str(entry["must_close_before"]),
                "checker": f"run_g1.{checker.__name__}",
                "discharged": bool(detail.get("discharged")),
                "detail": detail,
            }
        )
    return {
        "schema": "w0_g1_obligation_discharge_v1",
        "registry": str(registry_path),
        "registry_sha256": sha256_of_bytes(payload),
        "obligations": results,
        "all_discharged": bool(results) and all(item["discharged"] for item in results),
        "reading": (
            "The registry says these must close before any G1 PASS. Clause six "
            "is the mechanism that makes that sentence executable: PASS is "
            "unreachable while any of them is open, and an obligation with no "
            "implemented check counts as open. An empty obligation list also "
            "counts as open -- the line's own contract test says the list must "
            "not silently empty out, so an empty one is a missing list, not a "
            "finished proof."
        ),
    }


def _catalog_digests(catalog_dirs: Sequence[Path]) -> Dict[str, str]:
    """Per region class, the digests of every catalog file the run consumed.

    A union of catalogs is still one input: the gate binds the master's answer to
    all of them, so a plus-joined digest is what has to match.
    """
    digests: Dict[str, str] = {}
    for name in list(REGION_CLASS_ORDER) + ["manifest"]:
        parts = [
            sha256_of_bytes((directory / f"{name}.json").read_bytes())
            for directory in catalog_dirs
            if (directory / f"{name}.json").exists()
        ]
        if parts:
            digests[name] = parts[0] if len(parts) == 1 else "+".join(parts)
    return digests


def _area_pre_gate() -> Dict[str, Any]:
    """The census body-area demand, restated next to the board's usable budget.

    Not a decision on its own -- the packing ceilings that make it a real gate
    live in the catalog manifest -- but it belongs in every run's evidence.
    """
    demand = sum(
        row.count * TEMPLATE_SIZES[row.template][0] * TEMPLATE_SIZES[row.template][1]
        for row in CLASS_TABLE
    )
    return {
        "body_area_demand": demand,
        "board_usable_cells": TOTAL_USABLE_CELLS,
        "front_demand_cells": sum(row.count * (row.r_in + row.r_out) for row in CLASS_TABLE),
        "bodies": sum(row.count for row in CLASS_TABLE),
    }


def _precheck(
    columns: Mapping[str, Any],
    catalog_dirs: Sequence[Path],
    generic_io: Mapping[str, Any],
) -> Dict[str, Any]:
    supply = class_supply_pre_gate(columns)
    manifest_pre_gate: Optional[Any] = None
    for directory in catalog_dirs:
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            manifest = load_strict(manifest_path)
            manifest_pre_gate = manifest.get("arithmetic_pre_gate")
            break
    return {
        "schema": "w0_g1_precheck_v1",
        "authority": {
            "is_authoritative": False,
            "carries_bound": False,
            "ledger_effect": "none",
        },
        "census": _area_pre_gate(),
        "generic_io_contract": dict(generic_io),
        "catalog_area_pre_gate": manifest_pre_gate,
        "catalog_class_supply": supply,
        "catalog_columns": {
            name: {
                "patterns": len(columns[name].patterns),
                "multiplicity": columns[name].multiplicity,
                "complete": columns[name].complete,
            }
            for name in sorted(columns)
        },
    }


def _run_audit(
    geometry_path: Path, paths: RunPaths, *, timeout: float = 900.0
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run the audit in an isolated child and return (report, observation)."""
    with tempfile.TemporaryDirectory(prefix="w0g1audit") as scratch:
        output = Path(scratch) / "g1_audit.json"
        argv = [
            sys.executable,
            "-I",
            "-S",
            "-B",
            str(AUDIT_SCRIPT),
            "--geometry",
            str(geometry_path),
            "--rules",
            str(paths.rules),
            "--instances",
            str(paths.instances),
            "--output",
            str(output),
        ]
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_REPO_ROOT),
            env={"PATH": os.environ.get("PATH", "")},
        )
        observation = {
            "argv": argv,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip()[-4000:],
        }
        if not output.exists():
            return {}, observation
        report = json.loads(output.read_text(encoding="utf-8"))
    return report, observation


def _gate_verdict(
    master: Mapping[str, Any],
    catalog_digests: Mapping[str, str],
    pre_gate: Mapping[str, Any],
    geometry: Optional[Mapping[str, Any]],
    geometry_sha256: Optional[str],
    audit: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    root_closure_error: Optional[str],
    obligations: Mapping[str, Any],
) -> Dict[str, Any]:
    clauses: Dict[str, Any] = {}
    recorded = master.get("catalogs") or {}
    catalog_bound = bool(recorded) and all(
        catalog_digests.get(name) == entry.get("sha256")
        for name, entry in recorded.items()
    )
    # The solver-free supply pre-gate and the master answer the same question by
    # two independent routes.  ``SHORT`` is a proof that no selection covers the
    # census, so a master that nonetheless returns a solution means one of the two
    # is wrong -- and that has to be raised here, not filed side by side in the run
    # root as if both were evidence.
    pre_gate_verdict = ((pre_gate.get("catalog_class_supply") or {}).get("verdict"))
    contradiction = pre_gate_verdict == "SHORT" and master.get("status") in {
        "OPTIMAL",
        "FEASIBLE",
    }
    clauses[GATE_CLAUSES[0]] = {
        "ok": (
            master.get("status") in {"OPTIMAL", "FEASIBLE"}
            and catalog_bound
            and not contradiction
        ),
        "status": master.get("status"),
        "catalog_digests_match": catalog_bound,
        "pre_gate_verdict": pre_gate_verdict,
        "pre_gate_contradicts_master": contradiction,
    }
    expansion = (geometry or {}).get("expansion") or {}
    clauses[GATE_CLAUSES[1]] = {
        "ok": geometry is not None
        and expansion.get("poles_after_minimisation") is not None
        and int(expansion.get("poles_after_minimisation", -1))
        <= int(expansion.get("poles_before_minimisation", -1)),
        "expansion": expansion or None,
    }
    issues = audit.get("issues")
    summary = audit.get("summary") or {}
    clauses[GATE_CLAUSES[2]] = {
        "ok": audit.get("verdict") == "PASS" and issues == [],
        "verdict": audit.get("verdict"),
        "issue_codes": audit.get("issue_codes"),
        "dead_for_any_actual_class": summary.get("dead_for_any_actual_class"),
    }
    recorded_geometry = ((audit.get("inputs") or {}).get("geometry") or {}).get("sha256")
    argv = list(observation.get("argv") or [])
    # Isolation is decided by what the *child* reported about itself, not by the
    # argv this process built nine lines earlier -- checking our own argv would be
    # a tautology in the production path.  The child states whether a solver was
    # importable at all and whether it had loaded any module of this line.
    environment = audit.get("environment") or {}
    flags = environment.get("flags") or {}
    child_isolated = (
        environment.get("ortools_importable") is False
        and environment.get("line_modules_loaded") == []
        and environment.get("src_modules_loaded") == []
        and flags.get("isolated") is True
        and flags.get("no_site") is True
        and flags.get("dont_write_bytecode") is True
    )
    clauses[GATE_CLAUSES[3]] = {
        "ok": bool(geometry_sha256)
        and recorded_geometry == geometry_sha256
        and child_isolated
        and observation.get("returncode") == 0,
        "geometry_sha256": geometry_sha256,
        "audit_recorded_geometry_sha256": recorded_geometry,
        "child_reported_isolation": child_isolated,
        "child_environment": {
            "ortools_importable": environment.get("ortools_importable"),
            "line_modules_loaded": environment.get("line_modules_loaded"),
            "src_modules_loaded": environment.get("src_modules_loaded"),
            "flags": dict(flags),
        },
        "launch_argv_isolation_flags": [
            flag for flag in ("-I", "-S", "-B") if flag in argv
        ],
        "returncode": observation.get("returncode"),
    }
    # Clause 5 is decided before any receipt exists: the run root is compared
    # against the manifest of what this run actually wrote (not against a manifest
    # built by enumerating the root, which could never notice an intruder).  The
    # receipt is written only when that holds, and removed again if the check
    # after writing it fails -- so a failed closure can leave neither a PASS nor a
    # receipt behind.
    clauses[GATE_CLAUSES[4]] = {
        "ok": root_closure_error is None,
        "checked_before_receipt": True,
        "error": root_closure_error,
        "decided_by": (
            "root closure against this run's own artifact manifest, verified "
            "before the receipt is written; the receipt is deleted if the "
            "post-receipt closure check fails"
        ),
    }
    # Clause six: the registry's own "must close before any G1 PASS" field, made
    # executable.  It is also read directly by ``_terminal_state``, so a future
    # edit that drops it out of this conjunction still cannot mint a PASS.
    clauses[GATE_CLAUSES[5]] = {
        "ok": bool(obligations.get("all_discharged")),
        "registry_sha256": obligations.get("registry_sha256"),
        "open_obligation_ids": [
            str(item["id"])
            for item in obligations.get("obligations", ())
            if not item.get("discharged")
        ],
        "discharged_obligation_ids": [
            str(item["id"])
            for item in obligations.get("obligations", ())
            if item.get("discharged")
        ],
        "decided_by": (
            "derived_theorems.json open_obligations, each discharged on this "
            "run's own artifacts; an obligation with no implemented check "
            "counts as open"
        ),
    }
    return clauses


def _terminal_state(master: Mapping[str, Any], clauses: Mapping[str, Any]) -> str:
    """Terminal state from all six clauses.

    Clause six is a *precondition*, checked before the conjunction: an open
    obligation makes PASS unreachable no matter what the rest of the run looks
    like.  The redundancy with ``all(...)`` below is deliberate -- the charter
    says no G1 PASS may carry an unproved assumption, and one lock on that is one
    edit away from none.
    """
    if master.get("status") == "SCALE_ABORT":
        return "SCALE_ABORT"
    if master.get("status") == "INFEASIBLE":
        return "INFEASIBLE"
    if master.get("status") not in {"OPTIMAL", "FEASIBLE"}:
        return "UNKNOWN"
    if not clauses[GATE_CLAUSES[2]]["ok"]:
        return "AUDIT_FAIL"
    if not clauses.get(GATE_CLAUSES[5], {}).get("ok"):
        return OBLIGATION_OPEN
    return "PASS" if all(entry.get("ok") for entry in clauses.values()) else "GATE_FAIL"


# --------------------------------------------------------------------------
# the run root
# --------------------------------------------------------------------------


class _Run:
    """One exclusively owned run root plus its artifact identity graph.

    The root manifest is built from what this run *wrote*, never from enumerating
    the directory: an enumerated manifest would silently adopt any file that
    turned up in the root, so closing against it could not fail.  Closure is
    therefore intent versus reality, and it is checked before the receipt exists.
    """

    def __init__(self, root_path: Path, experiment_id: str, payload: Any) -> None:
        self.root = ExclusiveRunRoot.create(root_path)
        self.experiment_id = experiment_id
        self.artifacts: Dict[str, Any] = {}
        self._directories: List[str] = []
        self._files: List[str] = []
        config = make_research_run_config(experiment_id=experiment_id, payload=payload)
        self.config_identity = self.root.write_json("config.json", config)
        self._files.append("config.json")

    def mkdir(self, relative: str) -> None:
        self.root.mkdir(relative)
        self._directories.append(relative)

    def write(self, relative: str, label: str, value: Any) -> str:
        payload = canonical_json_bytes(value) + b"\n"
        identity = self.root.write_bytes(relative, payload)
        self.artifacts[label] = identity
        self._files.append(relative)
        return identity.sha256

    def write_bytes(self, relative: str, label: str, payload: bytes) -> str:
        identity = self.root.write_bytes(relative, payload)
        self.artifacts[label] = identity
        self._files.append(relative)
        return identity.sha256

    def intended_manifest(self) -> Dict[str, Any]:
        """Exactly the directories and files this run created, path-sorted."""
        entries: List[Dict[str, str]] = [
            {"path": path, "type": "directory"} for path in self._directories
        ]
        entries.extend({"path": path, "type": "regular_file"} for path in self._files)
        entries.sort(key=lambda entry: entry["path"])
        return {"schema": ARTIFACT_ROOT_MANIFEST_SCHEMA, "entries": entries}

    def closure_error(self) -> Optional[str]:
        """The pre-receipt closure check, as a message instead of an exception.

        Used by the gate so clause five can *record* what it found; ``close``
        makes the same check fatal.
        """
        try:
            verify_artifact_root_closure(
                self.root, self.intended_manifest(), receipt_present=False
            )
        except ResearchRunContractError as exc:
            return str(exc)
        return None

    def _remove_receipt(self) -> None:
        try:
            os.unlink(self.root.path / TERMINAL_RECEIPT_PATH)
        except FileNotFoundError:  # pragma: no cover - only reachable on a race
            pass

    def close(self, payload: Any) -> Dict[str, Any]:
        manifest = self.intended_manifest()
        # Before the receipt: a root that does not close must not acquire one.
        verify_artifact_root_closure(self.root, manifest, receipt_present=False)
        receipt = make_research_run_receipt(
            experiment_id=self.experiment_id,
            config_identity=self.config_identity,
            artifacts=self.artifacts,
            payload={"root_manifest": manifest, "run": payload},
        )
        self.root.write_json("receipt.json", receipt)
        try:
            verify_artifact_root_closure(self.root, manifest, receipt_present=True)
        except BaseException:
            # Anything that appeared during the write invalidates the receipt, and
            # a receipt left on disk would be read as "this root closed".
            self._remove_receipt()
            raise
        return receipt


def _int_payload(value: Any) -> Any:
    """Coerce a report into the receipt payload's int/str/bool/None domain."""
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, Mapping):
        return {str(key): _int_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_int_payload(item) for item in value]
    return str(value)


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------


def _paths(args: argparse.Namespace) -> RunPaths:
    catalogs = getattr(args, "catalogs", None) or ()
    return RunPaths(
        catalogs=tuple(Path(item).resolve() for item in catalogs),
        rules=Path(getattr(args, "rules", None) or DEFAULT_RULES_PATH).resolve(),
        instances=Path(
            getattr(args, "instances", None) or DEFAULT_INSTANCES_PATH
        ).resolve(),
        generic_io=Path(
            getattr(args, "generic_io", None) or DEFAULT_GENERIC_IO_PATH
        ).resolve(),
    )


def cmd_generate(args: argparse.Namespace) -> int:
    from g1_pattern_generator import main as generator_main

    forwarded: List[str] = ["--output-dir", str(args.output_dir)]
    for flag, value in (
        ("--budget-seconds", args.budget_seconds),
        ("--target-seconds", args.target_seconds),
        ("--solutions-per-target", args.solutions_per_target),
        ("--max-derived-subsets", args.max_derived_subsets),
        ("--workers", args.workers),
        ("--seed", args.seed),
        ("--max-targets", args.max_targets),
        ("--min-bodies", args.min_bodies),
    ):
        if value is not None:
            forwarded.extend([flag, str(value)])
    for name in args.region_classes or ():
        forwarded.extend(["--region-class", name])
    return generator_main(forwarded)


def _require_catalog(paths: RunPaths) -> Tuple[Path, ...]:
    if not paths.catalogs:  # pragma: no cover - argparse makes it required
        raise SystemExit("this subcommand needs at least one --catalog")
    return paths.catalogs


def cmd_precheck(args: argparse.Namespace) -> int:
    paths = _paths(args)
    catalog = _require_catalog(paths)
    generic_io = _generic_io_contract(paths.generic_io)
    columns = load_catalogs(catalog)
    report = _precheck(columns, catalog, generic_io)
    run = _Run(
        Path(args.run_root),
        "w0_g1_precheck",
        {
            "catalogs": [str(item) for item in catalog],
            "catalog_digests": _catalog_digests(catalog),
            "generic_io": str(paths.generic_io),
            "generic_io_sha256": generic_io["sha256"],
        },
    )
    run.write("precheck.json", "precheck", report)
    run.close(
        _int_payload(
            {
                "verdict": report["catalog_class_supply"]["verdict"],
                "generic_io_sha256": generic_io["sha256"],
            }
        )
    )
    print(json.dumps(report["catalog_class_supply"]["verdict"], indent=2))
    print(f"precheck -> {run.root.path}")
    return 0


def _solve(
    args: argparse.Namespace, paths: RunPaths
) -> Tuple[Any, Dict[str, Any], Dict[str, Any], bytes]:
    """Load, solve, and hand back the solver log as bytes.

    The CP-SAT log is written to a scratch file and returned rather than written
    where it lands: everything a run publishes has to go through the exclusive run
    root's write-once API, and a solver writing straight into the root would be a
    second author of the evidence.
    """
    catalog = _require_catalog(paths)
    columns = load_catalogs(catalog)
    digests = _catalog_digests(catalog)
    with tempfile.TemporaryDirectory(prefix="w0g1solve") as scratch:
        log_path = Path(scratch) / "cpsat.log"
        config = MasterConfig(
            collapse=not args.no_archetype_collapse,
            max_time_in_seconds=float(args.max_seconds),
            workers=int(args.workers),
            seed=int(args.seed),
            log_path=log_path,
        )
        result = solve_master(
            columns,
            config,
            catalog_manifest_sha256=digests.get("manifest"),
        )
        log_bytes = log_path.read_bytes() if log_path.exists() else b""
    return columns, digests, result, log_bytes


def cmd_solve(args: argparse.Namespace) -> int:
    paths = _paths(args)
    catalog = _require_catalog(paths)
    generic_io = _generic_io_contract(paths.generic_io)
    started = time.monotonic()
    columns, digests, result, log_bytes = _solve(args, paths)
    run = _Run(
        Path(args.run_root),
        "w0_g1_solve",
        {
            "catalogs": [str(item) for item in catalog],
            "catalog_digests": digests,
            "generic_io": str(paths.generic_io),
            "generic_io_sha256": generic_io["sha256"],
        },
    )
    run.mkdir("master")
    run.write("master/pre_gate.json", "pre_gate", _precheck(columns, catalog, generic_io))
    run.write("master/master_result.json", "master_result", result)
    run.write_bytes("master/cpsat.log", "cpsat_log", log_bytes)
    run.close(
        _int_payload(
            {
                "status": result["status"],
                "scale": result["scale"],
                "wall_seconds": int(time.monotonic() - started),
                "generic_io_sha256": generic_io["sha256"],
            }
        )
    )
    print(json.dumps({"status": result["status"], "scale": result["scale"]}, indent=2))
    print(f"solve -> {run.root.path}")
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 1


def cmd_expand(args: argparse.Namespace) -> int:
    paths = _paths(args)
    catalog = _require_catalog(paths)
    master = load_strict(Path(args.master))
    geometry = expand_master_solution(master, catalog, instances_path=paths.instances)
    run = _Run(
        Path(args.run_root),
        "w0_g1_expand",
        {
            "catalogs": [str(item) for item in catalog],
            "master": str(Path(args.master).resolve()),
        },
    )
    run.mkdir("geometry")
    run.write("geometry/g1_geometry.json", "geometry", geometry)
    run.close(_int_payload(summarise(geometry)))
    print(json.dumps(summarise(geometry), indent=2))
    print(f"expand -> {run.root.path}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    paths = _paths(args)
    geometry_path = Path(args.geometry).resolve()
    report, observation = _run_audit(geometry_path, paths)
    run = _Run(
        Path(args.run_root),
        "w0_g1_audit",
        {"geometry": str(geometry_path)},
    )
    run.mkdir("audit")
    run.write("audit/g1_audit.json", "audit", report)
    run.write("audit/child_process.json", "audit_process", observation)
    run.close(_int_payload({"verdict": report.get("verdict")}))
    print(json.dumps({"verdict": report.get("verdict"), "issues": len(report.get("issues") or [])}))
    print(f"audit -> {run.root.path}")
    return 0 if report.get("verdict") == "PASS" else 1


def cmd_gate(args: argparse.Namespace) -> int:
    paths = _paths(args)
    catalog = _require_catalog(paths)
    generic_io = _generic_io_contract(paths.generic_io)
    started = time.monotonic()
    columns, digests, master, log_bytes = _solve(args, paths)

    run = _Run(
        Path(args.run_root),
        "w0_g1_gate",
        {
            "catalogs": [str(item) for item in catalog],
            "catalog_digests": digests,
            "rules": str(paths.rules),
            "instances": str(paths.instances),
            "generic_io": str(paths.generic_io),
            "generic_io_sha256": generic_io["sha256"],
            "collapse": not args.no_archetype_collapse,
            "max_seconds": int(args.max_seconds),
            "workers": int(args.workers),
            "seed": int(args.seed),
            "python": platform.python_version(),
        },
    )
    pre_gate = _precheck(columns, catalog, generic_io)
    run.mkdir("master")
    run.write("master/pre_gate.json", "pre_gate", pre_gate)
    run.write("master/master_result.json", "master_result", master)
    run.write_bytes("master/cpsat.log", "cpsat_log", log_bytes)

    geometry: Optional[Dict[str, Any]] = None
    geometry_sha256: Optional[str] = None
    audit_report: Dict[str, Any] = {}
    observation: Dict[str, Any] = {}
    if master["status"] in {"OPTIMAL", "FEASIBLE"}:
        geometry = expand_master_solution(
            master, catalog, instances_path=paths.instances
        )
        run.mkdir("geometry")
        geometry_sha256 = run.write("geometry/g1_geometry.json", "geometry", geometry)
        geometry_path = run.root.path / "geometry" / "g1_geometry.json"
        audit_report, observation = _run_audit(geometry_path, paths)
        run.mkdir("audit")
        run.write("audit/g1_audit.json", "audit", audit_report)
        run.write("audit/child_process.json", "audit_process", observation)

    # Clause six before clause five: the obligation discharge is an artifact of
    # this run, so it has to be written into the root *before* the root is asked
    # whether it closes.
    obligations = discharge_open_obligations(geometry)
    run.mkdir("obligations")
    run.write("obligations/discharge.json", "obligation_discharge", obligations)

    # Clause five is settled here, on the last root state before gate.json is
    # written and long before any receipt exists.
    root_closure_error = run.closure_error()
    clauses = _gate_verdict(
        master,
        digests,
        pre_gate,
        geometry,
        geometry_sha256,
        audit_report,
        observation,
        root_closure_error=root_closure_error,
        obligations=obligations,
    )
    terminal = _terminal_state(master, clauses)
    gate_doc = {
        "schema": "w0_g1_gate_v1",
        "authority": {
            "is_authoritative": False,
            "carries_bound": False,
            "ledger_effect": "none",
        },
        "terminal_state": terminal,
        "verdict": "PASS" if terminal == "PASS" else "NOT_PASSED",
        "verdict_is_conditional_on_receipt": terminal == "PASS",
        "clauses": clauses,
        "open_obligations": {
            "registry_sha256": obligations["registry_sha256"],
            "all_discharged": obligations["all_discharged"],
            "ids": [str(item["id"]) for item in obligations["obligations"]],
        },
        "master_status": master["status"],
        "infeasibility_core": master.get("infeasibility_core"),
        "scale": master["scale"],
        "wall_seconds": round(time.monotonic() - started, 3),
        "registers_lower_bound": False,
        "wording_scope": (
            "This verdict is limited to this catalog (digests recorded in the run "
            "config), this class table (derived on the spot from the frozen rules), "
            "this hole vocabulary (a 6x7 or 7x6 rectangle that does not straddle a "
            "region seam) and this restriction level (the R-* set registered in "
            "derived_theorems.json). It says nothing about the benchmark and it "
            "registers no bound."
        ),
    }
    run.write("gate.json", "gate", gate_doc)
    try:
        receipt = run.close(
        _int_payload(
            {
                "terminal_state": terminal,
                "master_status": master["status"],
                "infeasibility_core": master.get("infeasibility_core"),
                "generic_io_sha256": generic_io["sha256"],
                "open_obligations_all_discharged": obligations["all_discharged"],
                "gate_clause_five": (
                    "closed: the root matched this run's own artifact manifest "
                    "before this receipt was written, and again after"
                ),
            }
        )
        )
    except BaseException:
        # The root failed to close after gate.json was written.  A verdict that
        # was conditional on a receipt must not stay behind as the last word in
        # a root that has none.
        gate_doc["terminal_state"] = "ROOT_CLOSURE_FAILED"
        gate_doc["verdict"] = "NOT_PASSED"
        gate_doc["verdict_is_conditional_on_receipt"] = False
        gate_doc["invalidated_by"] = "post_gate_root_closure_failure"
        (run.root.path / "gate.json").write_bytes(
            canonical_json_bytes(gate_doc) + b"\n"
        )
        raise
    print(
        json.dumps(
            {
                "terminal_state": terminal,
                "master_status": master["status"],
                "infeasibility_core": master.get("infeasibility_core"),
                "receipt_closed": bool(receipt),
                "run_root": str(run.root.path),
            },
            indent=2,
        )
    )
    return 0 if terminal == "PASS" else 1


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _add_catalog_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog", dest="catalogs", required=True, action="append", type=Path,
        help="catalog directory; repeat to union several generation passes",
    )
    parser.add_argument("--rules", type=Path, default=None)
    parser.add_argument("--instances", type=Path, default=None)
    parser.add_argument("--generic-io", dest="generic_io", type=Path, default=None)


def _add_master_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-seconds", type=float, default=1800.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-archetype-collapse", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="W0 front-aware G1 run orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="build the pattern catalog")
    generate.add_argument("--output-dir", required=True, type=Path)
    generate.add_argument("--budget-seconds", type=float, default=None)
    generate.add_argument("--target-seconds", type=float, default=None)
    generate.add_argument("--solutions-per-target", type=int, default=None)
    generate.add_argument("--max-derived-subsets", type=int, default=None)
    generate.add_argument("--workers", type=int, default=None)
    generate.add_argument("--seed", type=int, default=None)
    generate.add_argument("--max-targets", type=int, default=None)
    generate.add_argument("--min-bodies", type=int, default=None)
    generate.add_argument("--region-class", dest="region_classes", action="append")
    generate.set_defaults(func=cmd_generate)

    precheck = sub.add_parser("precheck", help="arithmetic pre-gates only")
    _add_catalog_args(precheck)
    precheck.add_argument("--run-root", required=True, type=Path)
    precheck.set_defaults(func=cmd_precheck)

    solve = sub.add_parser("solve", help="exact-cover master only")
    _add_catalog_args(solve)
    _add_master_args(solve)
    solve.add_argument("--run-root", required=True, type=Path)
    solve.set_defaults(func=cmd_solve)

    expand = sub.add_parser("expand", help="master answer -> geometry")
    _add_catalog_args(expand)
    expand.add_argument("--master", required=True, type=Path)
    expand.add_argument("--run-root", required=True, type=Path)
    expand.set_defaults(func=cmd_expand)

    audit = sub.add_parser("audit", help="independent audit of a geometry")
    audit.add_argument("--rules", type=Path, default=None)
    audit.add_argument("--instances", type=Path, default=None)
    audit.add_argument("--geometry", required=True, type=Path)
    audit.add_argument("--run-root", required=True, type=Path)
    audit.set_defaults(func=cmd_audit)

    gate = sub.add_parser("gate", help="the whole G1 chain and its verdict")
    _add_catalog_args(gate)
    _add_master_args(gate)
    gate.add_argument("--run-root", required=True, type=Path)
    gate.set_defaults(func=cmd_gate)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
