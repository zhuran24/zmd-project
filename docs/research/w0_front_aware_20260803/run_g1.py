"""W0 front-aware G1: the run orchestrator.

research-only.  No authority, no bound, no ledger effect.

Six subcommands, in pipeline order::

    generate   build the per-region-class pattern catalog (stage A engine)
    precheck   cheap arithmetic pre-gates over the catalog and the region model
    solve      exact-cover master over a frozen catalog
    expand     master answer -> full 70x70 geometry
    audit      independent front-viability audit, in an isolated child process
    gate       precheck -> solve -> expand -> audit -> the five-clause G1 verdict

Everything except ``generate`` writes into an **exclusively created** run root via
``devtools.research_run_contract``: the directory must not already exist, every
artifact is written once with ``O_EXCL``, and the run closes with a receipt whose
identity graph plus root-closure check together say "this directory is exactly
these files and nothing else".  A run that cannot close its root is a run whose
evidence cannot be trusted, so the closure check is fatal, not advisory.

The G1 verdict (charter section 2) is PASS only when all five hold:

1. the master returned OPTIMAL or FEASIBLE and the catalog digests it recorded
   match the catalog actually on disk;
2. expansion succeeded, the pole set was globally minimised, and the geometry
   parses strictly;
3. the independent audit says ``PASS`` with an empty issue list, in particular
   ``dead_for_any_actual_class == 0`` and a nine-row exact class census;
4. that audit ran in a separate ``python -I -S -B`` process which cannot import
   ortools, and the geometry digest it recorded equals the digest this process
   computed;
5. the run receipt closes.

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
    ExclusiveRunRoot,
    build_artifact_root_manifest,
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
from g1_pattern_schema import (  # noqa: E402
    canonical_json_bytes,
    load_strict,
    sha256_of_bytes,
)
from g1_port_semantics import (  # noqa: E402
    CLASS_TABLE,
    DEFAULT_INSTANCES_PATH,
    DEFAULT_RULES_PATH,
    TEMPLATE_SIZES,
)
from g1_region_model import REGION_CLASS_ORDER, TOTAL_USABLE_CELLS  # noqa: E402

__all__ = [
    "AUDIT_SCRIPT",
    "GATE_CLAUSES",
    "RunPaths",
    "main",
]

AUDIT_SCRIPT = _HERE / "front_viability_audit.py"

#: The five clauses of the G1 verdict, in the charter's order.  Reported one by
#: one so a failure names itself instead of collapsing into "not PASS".
GATE_CLAUSES: Tuple[str, ...] = (
    "master_terminal_and_catalog_bound",
    "expansion_and_pole_minimisation",
    "independent_audit_clean",
    "audit_isolated_and_digest_bound",
    "receipt_closed",
)


@dataclass(frozen=True)
class RunPaths:
    catalogs: Tuple[Path, ...]
    rules: Path
    instances: Path


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


def _precheck(columns: Mapping[str, Any], catalog_dirs: Sequence[Path]) -> Dict[str, Any]:
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
    geometry: Optional[Mapping[str, Any]],
    geometry_sha256: Optional[str],
    audit: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> Dict[str, Any]:
    clauses: Dict[str, Any] = {}
    recorded = master.get("catalogs") or {}
    catalog_bound = bool(recorded) and all(
        catalog_digests.get(name) == entry.get("sha256")
        for name, entry in recorded.items()
    )
    clauses[GATE_CLAUSES[0]] = {
        "ok": master.get("status") in {"OPTIMAL", "FEASIBLE"} and catalog_bound,
        "status": master.get("status"),
        "catalog_digests_match": catalog_bound,
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
    clauses[GATE_CLAUSES[3]] = {
        "ok": bool(geometry_sha256)
        and recorded_geometry == geometry_sha256
        and {"-I", "-S", "-B"} <= set(argv)
        and observation.get("returncode") == 0,
        "geometry_sha256": geometry_sha256,
        "audit_recorded_geometry_sha256": recorded_geometry,
        "isolation_flags": [flag for flag in ("-I", "-S", "-B") if flag in argv],
        "returncode": observation.get("returncode"),
    }
    # Clause 5 cannot be self-reported: the receipt is written *after* this
    # document, because the root manifest has to enumerate a finished root.  What
    # settles it is the presence of a valid ``receipt.json`` in this run root --
    # if the closure check fails the process raises and no receipt exists at all,
    # so a reader can decide the clause from the directory rather than from a
    # claim made inside it.
    clauses[GATE_CLAUSES[4]] = {
        "ok": None,
        "decided_by": "receipt.json in this run root; absent = clause 5 failed",
    }
    return clauses


def _terminal_state(master: Mapping[str, Any], clauses: Mapping[str, Any]) -> str:
    """Terminal state from clauses 1-4; clause 5 is settled by the receipt."""
    if master.get("status") == "SCALE_ABORT":
        return "SCALE_ABORT"
    if master.get("status") == "INFEASIBLE":
        return "INFEASIBLE"
    if master.get("status") not in {"OPTIMAL", "FEASIBLE"}:
        return "UNKNOWN"
    if not clauses[GATE_CLAUSES[2]]["ok"]:
        return "AUDIT_FAIL"
    decided = [
        entry.get("ok") for name, entry in clauses.items() if name != GATE_CLAUSES[4]
    ]
    return "PASS" if all(decided) else "GATE_FAIL"


# --------------------------------------------------------------------------
# the run root
# --------------------------------------------------------------------------


class _Run:
    """One exclusively owned run root plus its artifact identity graph."""

    def __init__(self, root_path: Path, experiment_id: str, payload: Any) -> None:
        self.root = ExclusiveRunRoot.create(root_path)
        self.experiment_id = experiment_id
        self.artifacts: Dict[str, Any] = {}
        config = make_research_run_config(experiment_id=experiment_id, payload=payload)
        self.config_identity = self.root.write_json("config.json", config)

    def mkdir(self, relative: str) -> None:
        self.root.mkdir(relative)

    def write(self, relative: str, label: str, value: Any) -> str:
        payload = canonical_json_bytes(value) + b"\n"
        identity = self.root.write_bytes(relative, payload)
        self.artifacts[label] = identity
        return identity.sha256

    def write_bytes(self, relative: str, label: str, payload: bytes) -> str:
        identity = self.root.write_bytes(relative, payload)
        self.artifacts[label] = identity
        return identity.sha256

    def close(self, payload: Any) -> Dict[str, Any]:
        manifest = build_artifact_root_manifest(self.root)
        receipt = make_research_run_receipt(
            experiment_id=self.experiment_id,
            config_identity=self.config_identity,
            artifacts=self.artifacts,
            payload={"root_manifest": manifest, "run": payload},
        )
        self.root.write_json("receipt.json", receipt)
        verify_artifact_root_closure(self.root, manifest, receipt_present=True)
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
    columns = load_catalogs(catalog)
    report = _precheck(columns, catalog)
    run = _Run(
        Path(args.run_root),
        "w0_g1_precheck",
        {
            "catalogs": [str(item) for item in catalog],
            "catalog_digests": _catalog_digests(catalog),
        },
    )
    run.write("precheck.json", "precheck", report)
    run.close(_int_payload({"verdict": report["catalog_class_supply"]["verdict"]}))
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
    started = time.monotonic()
    columns, digests, result, log_bytes = _solve(args, paths)
    run = _Run(
        Path(args.run_root),
        "w0_g1_solve",
        {"catalogs": [str(item) for item in catalog], "catalog_digests": digests},
    )
    run.mkdir("master")
    run.write("master/pre_gate.json", "pre_gate", _precheck(columns, catalog))
    run.write("master/master_result.json", "master_result", result)
    run.write_bytes("master/cpsat.log", "cpsat_log", log_bytes)
    run.close(
        _int_payload(
            {
                "status": result["status"],
                "scale": result["scale"],
                "wall_seconds": int(time.monotonic() - started),
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
            "collapse": not args.no_archetype_collapse,
            "max_seconds": int(args.max_seconds),
            "workers": int(args.workers),
            "seed": int(args.seed),
            "python": platform.python_version(),
        },
    )
    run.mkdir("master")
    run.write("master/pre_gate.json", "pre_gate", _precheck(columns, catalog))
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

    clauses = _gate_verdict(
        master, digests, geometry, geometry_sha256, audit_report, observation
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
    receipt = run.close(
        _int_payload(
            {
                "terminal_state": terminal,
                "master_status": master["status"],
                "infeasibility_core": master.get("infeasibility_core"),
                "gate_clause_five": "closed: this receipt exists and the root closes",
            }
        )
    )
    clause_five = bool(receipt)
    print(
        json.dumps(
            {
                "terminal_state": terminal,
                "master_status": master["status"],
                "infeasibility_core": master.get("infeasibility_core"),
                "receipt_closed": clause_five,
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
