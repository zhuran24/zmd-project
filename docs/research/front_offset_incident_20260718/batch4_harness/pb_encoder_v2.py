"""Build the corrected Batch 4 front-clear PB relaxation.

This is a reconstructed new baseline, not a replay of the withdrawn v1
experiment.  Candidate port coordinates already denote front cells.  Their
N/S/E/W direction is validated, but it never changes the stored ``(x, y)``.

The model is intentionally a relaxation: mandatory instances are anonymous
within a template, optional facilities and power/binding/routing constraints
are omitted, shared clear fronts are allowed, and unknown template demand
removes that template's front constraints.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.io.strict_json import loads_strict_json  # noqa: E402
from src.models.binding_subproblem import load_generic_io_requirements_from_text  # noqa: E402
from src.models.port_binding import (  # noqa: E402
    routing_free_sink_commodities_from_generic_inputs,
    routing_visible_port_demands,
    supports_exact_pose_level_binding,
)
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES  # noqa: E402


SEMANTICS = "reconstructed_new_baseline"
SCHEMA_VERSION = "front_clear_pb_v2"
ALLOWED_DIRECTIONS = frozenset({"N", "S", "E", "W"})
HISTORICAL_V1_STATUS = {
    "valid_for_intended_relaxation": False,
    "independent_defects": [
        "v1 moved stored front coordinates by direction a second time",
        "v1 used front-clear RHS demand-minus-port-count instead of minus-port-count",
    ],
    "consequence": "v1 UNSAT or proof output cannot certify the intended relaxation",
}
INPUT_PATHS = {
    "candidate_placements": Path("data/preprocessed/candidate_placements.json"),
    "mandatory_instances": Path("data/preprocessed/mandatory_exact_instances.json"),
    "generic_io_requirements": Path("data/preprocessed/generic_io_requirements.json"),
    "canonical_rules": Path("rules/canonical_rules.json"),
    "preprocess_plan": Path("rules/preprocess_plan.json"),
    "operation_profiles_source": Path("src/preprocess/operation_profiles.py"),
    "port_binding_source": Path("src/models/port_binding.py"),
}


class EncoderError(ValueError):
    """Raised when an input cannot be translated without guessing."""


@dataclass(frozen=True, slots=True)
class Constraint:
    """Canonical linear PB constraint; terms are ``(variable, coefficient)``."""

    terms: tuple[tuple[int, int], ...]
    relation: str
    rhs: int

    def render(self) -> str:
        rendered = " ".join(
            f"{'+' if coefficient >= 0 else ''}{coefficient} x{variable}"
            for variable, coefficient in self.terms
        )
        return f"{rendered} {self.relation} {self.rhs} ;"


@dataclass(frozen=True, slots=True)
class Snapshot:
    key: str
    path: Path
    display_path: str
    raw: bytes
    sha256: str

    @property
    def text(self) -> str:
        return self.raw.decode("utf-8")

    def record(self) -> dict[str, Any]:
        return {
            "path": self.display_path,
            "sha256": self.sha256,
            "size_bytes": len(self.raw),
        }


@dataclass(slots=True)
class EncodedModel:
    variables: list[dict[str, Any]]
    constraints: list[Constraint]
    template_counts: dict[str, int]
    template_demands: dict[str, dict[str, Any]]
    routing_free_sink_commodities: list[str]
    stats: dict[str, int]
    grid_width: int
    grid_height: int
    ghost_width: int
    ghost_height: int


def _exact_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise EncoderError(f"{field} must be an exact integer")
    return int(value)


def _positive_int(value: Any, field: str) -> int:
    parsed = _exact_int(value, field)
    if parsed <= 0:
        raise EncoderError(f"{field} must be positive")
    return parsed


def _snapshot(key: str, path: Path, project_root: Path) -> Snapshot:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"missing {key} input: {resolved}")
    raw = resolved.read_bytes()
    try:
        display = str(resolved.relative_to(project_root.resolve()))
    except ValueError:
        display = str(resolved)
    return Snapshot(
        key=key,
        path=resolved,
        display_path=display,
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _load_snapshots(args: argparse.Namespace) -> dict[str, Snapshot]:
    project_root = args.project_root.resolve()
    selected = {
        "candidate_placements": args.candidate,
        "mandatory_instances": args.instances,
        "generic_io_requirements": args.generic_io,
        "canonical_rules": args.canonical_rules,
        "preprocess_plan": args.preprocess_plan,
        "operation_profiles_source": project_root / INPUT_PATHS["operation_profiles_source"],
        "port_binding_source": project_root / INPUT_PATHS["port_binding_source"],
    }
    return {
        key: _snapshot(key, path, project_root)
        for key, path in selected.items()
    }


def _json_payload(snapshot: Snapshot) -> Any:
    return loads_strict_json(snapshot.text)


def _grid_size(canonical_rules: Any) -> tuple[int, int]:
    if not isinstance(canonical_rules, Mapping):
        raise EncoderError("canonical_rules must be an object")
    globals_payload = canonical_rules.get("globals")
    if not isinstance(globals_payload, Mapping):
        raise EncoderError("canonical_rules.globals must be an object")
    grid = globals_payload.get("grid")
    if not isinstance(grid, Mapping):
        raise EncoderError("canonical_rules.globals.grid must be an object")
    return (
        _positive_int(grid.get("width"), "canonical grid width"),
        _positive_int(grid.get("height"), "canonical grid height"),
    )


def _cell(value: Any, field: str) -> tuple[int, int]:
    if isinstance(value, Mapping):
        x_value, y_value = value.get("x"), value.get("y")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        x_value, y_value = value
    else:
        raise EncoderError(f"{field} must be [x, y] or an x/y object")
    return _exact_int(x_value, f"{field}.x"), _exact_int(y_value, f"{field}.y")


def _stored_front(value: Any, field: str) -> tuple[int, int]:
    if not isinstance(value, Mapping):
        raise EncoderError(f"{field} must be an object")
    direction = value.get("dir")
    if type(direction) is not str or direction not in ALLOWED_DIRECTIONS:
        raise EncoderError(f"{field}.dir must be one of N/S/E/W")
    return (
        _exact_int(value.get("x"), f"{field}.x"),
        _exact_int(value.get("y"), f"{field}.y"),
    )


def _canonical_constraint(
    terms: Iterable[tuple[int, int]],
    relation: str,
    rhs: int,
) -> Constraint:
    if relation not in {"=", ">="}:
        raise EncoderError(f"unsupported PB relation: {relation}")
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        variable_id = _positive_int(variable, "constraint variable id")
        coefficient_value = _exact_int(coefficient, "constraint coefficient")
        combined[variable_id] += coefficient_value
    canonical = tuple(sorted((variable, coefficient) for variable, coefficient in combined.items() if coefficient))
    if not canonical:
        raise EncoderError("constant-only constraints are not supported by this harness")
    return Constraint(canonical, relation, _exact_int(rhs, "constraint rhs"))


def _template_demand_summary(
    instances: Sequence[Mapping[str, Any]],
    routing_free: frozenset[str],
) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    counts: Counter[str] = Counter()
    operations: defaultdict[str, list[str]] = defaultdict(list)
    seen_instance_ids: set[str] = set()
    for index, instance in enumerate(instances):
        if not isinstance(instance, Mapping):
            raise EncoderError(f"mandatory_instances[{index}] must be an object")
        instance_id = instance.get("instance_id")
        if type(instance_id) is not str or not instance_id:
            raise EncoderError(f"mandatory_instances[{index}].instance_id must be non-empty")
        if instance_id in seen_instance_ids:
            raise EncoderError(f"duplicate mandatory instance_id: {instance_id}")
        seen_instance_ids.add(instance_id)
        if instance.get("is_mandatory") is not True:
            raise EncoderError(f"mandatory instance {instance_id} is not marked mandatory")
        template = instance.get("facility_type")
        operation = instance.get("operation_type")
        if type(template) is not str or not template:
            raise EncoderError(f"mandatory instance {instance_id} has invalid facility_type")
        if type(operation) is not str or not operation:
            raise EncoderError(f"mandatory instance {instance_id} has invalid operation_type")
        counts[template] += 1
        operations[template].append(operation)

    summaries: dict[str, dict[str, Any]] = {}
    for template in sorted(counts):
        known: list[tuple[int, int]] = []
        unknown_operations: set[str] = set()
        for operation in operations[template]:
            if operation not in OPERATION_PORT_PROFILES:
                unknown_operations.add(operation)
                continue
            try:
                if not supports_exact_pose_level_binding(operation):
                    unknown_operations.add(operation)
                    continue
                demand = routing_visible_port_demands(operation, routing_free)
            except ValueError:
                unknown_operations.add(operation)
                continue
            known.append((int(demand[0]), int(demand[1])))

        unique_known = sorted(set(known))
        if unknown_operations or len(known) != counts[template]:
            selected: list[int] | None = None
            policy = "omitted_unknown_demand"
        elif not unique_known:
            selected = None
            policy = "omitted_no_known_demand"
        else:
            selected = [
                min(value[0] for value in unique_known),
                min(value[1] for value in unique_known),
            ]
            policy = (
                "componentwise_min_inconsistent"
                if len(unique_known) > 1
                else "consistent_known_demand"
            )
        summaries[template] = {
            "selected": selected,
            "policy": policy,
            "known_demands": [list(value) for value in unique_known],
            "unknown_operations": sorted(unknown_operations),
        }
    return dict(sorted(counts.items())), summaries


def build_model(
    *,
    candidate_payload: Any,
    instances_payload: Any,
    generic_io_text: str,
    canonical_rules_text: str,
    preprocess_plan_payload: Any,
    ghost_width: int,
    ghost_height: int,
    project_root: Path,
) -> EncodedModel:
    """Translate snapshotted inputs into a deterministic PB relaxation."""

    if not isinstance(candidate_payload, Mapping):
        raise EncoderError("candidate_placements must be an object")
    pools_payload = candidate_payload.get("facility_pools")
    if not isinstance(pools_payload, Mapping):
        raise EncoderError("candidate_placements.facility_pools must be an object")
    if not isinstance(instances_payload, Sequence) or isinstance(instances_payload, (str, bytes)):
        raise EncoderError("mandatory_instances must be an array")
    if not isinstance(preprocess_plan_payload, Mapping):
        raise EncoderError("preprocess_plan must be an object")

    canonical_payload = loads_strict_json(canonical_rules_text)
    grid_width, grid_height = _grid_size(canonical_payload)
    ghost_width = _positive_int(ghost_width, "ghost width")
    ghost_height = _positive_int(ghost_height, "ghost height")
    if ghost_width > grid_width or ghost_height > grid_height:
        raise EncoderError("ghost rectangle must fit inside the canonical grid")

    io_requirements = load_generic_io_requirements_from_text(
        text=generic_io_text,
        project_root=project_root,
        canonical_rules_text=canonical_rules_text,
    )
    routing_free = routing_free_sink_commodities_from_generic_inputs(
        io_requirements["required_generic_inputs"]
    )
    template_counts, template_demands = _template_demand_summary(
        list(instances_payload), routing_free
    )

    pools: dict[str, Sequence[Any]] = {}
    for template, count in template_counts.items():
        raw_pool = pools_payload.get(template)
        if not isinstance(raw_pool, Sequence) or isinstance(raw_pool, (str, bytes)):
            raise EncoderError(f"candidate pool missing or invalid for mandatory template {template}")
        if not raw_pool:
            raise EncoderError(f"candidate pool is empty for mandatory template {template}")
        if count > len(raw_pool):
            raise EncoderError(
                f"mandatory count {count} exceeds candidate pool {len(raw_pool)} for {template}"
            )
        pools[template] = raw_pool

    variables: list[dict[str, Any]] = []
    names: set[str] = set()

    def new_variable(name: str, kind: str, **fields: Any) -> int:
        if name in names:
            raise EncoderError(f"duplicate generated variable name: {name}")
        names.add(name)
        variable_id = len(variables) + 1
        variables.append({"id": variable_id, "name": name, "kind": kind, **fields})
        return variable_id

    pose_variables: dict[tuple[str, int], int] = {}
    cover: defaultdict[tuple[int, int], list[int]] = defaultdict(list)
    front_records: list[tuple[int, list[tuple[int, int]], list[tuple[int, int]], int, int]] = []
    forced_zero: list[int] = []

    for template in sorted(template_counts):
        demand_record = template_demands[template]
        selected_demand = demand_record["selected"]
        for pose_index, pose_value in enumerate(pools[template]):
            if not isinstance(pose_value, Mapping):
                raise EncoderError(f"candidate pose {template}[{pose_index}] must be an object")
            variable = new_variable(
                f"pose__{template}__{pose_index}",
                "pose",
                template=template,
                pose_index=pose_index,
            )
            pose_variables[(template, pose_index)] = variable

            occupied_raw = pose_value.get("occupied_cells")
            if not isinstance(occupied_raw, Sequence) or isinstance(occupied_raw, (str, bytes)):
                raise EncoderError(f"{template}[{pose_index}].occupied_cells must be an array")
            occupied = {
                _cell(value, f"{template}[{pose_index}].occupied_cells[{cell_index}]")
                for cell_index, value in enumerate(occupied_raw)
            }
            if not occupied:
                raise EncoderError(f"{template}[{pose_index}] has no occupied cells")
            for x_value, y_value in occupied:
                if not (0 <= x_value < grid_width and 0 <= y_value < grid_height):
                    raise EncoderError(f"{template}[{pose_index}] body cell is outside the grid")
            for body_cell in sorted(occupied):
                cover[body_cell].append(variable)

            sides: list[list[tuple[int, int]]] = []
            for side_name in ("input_port_cells", "output_port_cells"):
                raw_ports = pose_value.get(side_name) or []
                if not isinstance(raw_ports, Sequence) or isinstance(raw_ports, (str, bytes)):
                    raise EncoderError(f"{template}[{pose_index}].{side_name} must be an array")
                stored = [
                    _stored_front(port, f"{template}[{pose_index}].{side_name}[{port_index}]")
                    for port_index, port in enumerate(raw_ports)
                ]
                sides.append(
                    [
                        (x_value, y_value)
                        for x_value, y_value in stored
                        if 0 <= x_value < grid_width and 0 <= y_value < grid_height
                    ]
                )

            if selected_demand is None:
                continue
            input_demand, output_demand = int(selected_demand[0]), int(selected_demand[1])
            if len(sides[0]) < input_demand or len(sides[1]) < output_demand:
                forced_zero.append(variable)
                continue
            front_records.append((variable, sides[0], sides[1], input_demand, output_demand))

    occupancy_variables: dict[tuple[int, int], int] = {}
    for x_value, y_value in sorted(cover):
        occupancy_variables[(x_value, y_value)] = new_variable(
            f"occupancy__{x_value}__{y_value}",
            "occupancy",
            x=x_value,
            y=y_value,
        )

    ghost_variables: dict[tuple[int, int], int] = {}
    for anchor_x in range(grid_width - ghost_width + 1):
        for anchor_y in range(grid_height - ghost_height + 1):
            ghost_variables[(anchor_x, anchor_y)] = new_variable(
                f"ghost__{anchor_x}__{anchor_y}",
                "ghost_anchor",
                anchor_x=anchor_x,
                anchor_y=anchor_y,
            )

    constraints: list[Constraint] = []
    category_counts: Counter[str] = Counter()

    def append_constraint(category: str, constraint: Constraint) -> None:
        constraints.append(constraint)
        category_counts[category] += 1

    for template, count in sorted(template_counts.items()):
        append_constraint(
            "template_count",
            _canonical_constraint(
                ((pose_variables[(template, index)], 1) for index in range(len(pools[template]))),
                "=",
                count,
            ),
        )

    for cell_value, coverers in sorted(cover.items()):
        occupancy = occupancy_variables[cell_value]
        append_constraint(
            "occupancy_channel",
            _canonical_constraint(
                [*((variable, 1) for variable in coverers), (occupancy, -1)],
                "=",
                0,
            ),
        )

    for variable in sorted(forced_zero):
        append_constraint(
            "forced_zero",
            _canonical_constraint(((variable, 1),), "=", 0),
        )

    for variable, input_fronts, output_fronts, input_demand, output_demand in front_records:
        for side, fronts, demand in (
            ("input", input_fronts, input_demand),
            ("output", output_fronts, output_demand),
        ):
            if demand <= 0:
                continue
            terms = [(variable, -demand)]
            terms.extend(
                (occupancy_variables[front], -1)
                for front in fronts
                if front in occupancy_variables
            )
            append_constraint(
                f"front_clear_{side}",
                _canonical_constraint(terms, ">=", -len(fronts)),
            )

    append_constraint(
        "ghost_one_hot",
        _canonical_constraint(((variable, 1) for variable in ghost_variables.values()), "=", 1),
    )
    for (anchor_x, anchor_y), ghost in ghost_variables.items():
        for x_value in range(anchor_x, anchor_x + ghost_width):
            for y_value in range(anchor_y, anchor_y + ghost_height):
                occupancy = occupancy_variables.get((x_value, y_value))
                if occupancy is None:
                    continue
                append_constraint(
                    "ghost_body_exclusion",
                    _canonical_constraint(((ghost, -1), (occupancy, -1)), ">=", -1),
                )

    stats = {
        "variables": len(variables),
        "constraints": len(constraints),
        "pose_variables": len(pose_variables),
        "occupancy_variables": len(occupancy_variables),
        "ghost_variables": len(ghost_variables),
        "forced_zero": len(forced_zero),
        **{key: category_counts[key] for key in sorted(category_counts)},
    }
    return EncodedModel(
        variables=variables,
        constraints=constraints,
        template_counts=template_counts,
        template_demands=template_demands,
        routing_free_sink_commodities=sorted(routing_free),
        stats=stats,
        grid_width=grid_width,
        grid_height=grid_height,
        ghost_width=ghost_width,
        ghost_height=ghost_height,
    )


def _display_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(project_root.resolve()))
    except ValueError:
        return str(resolved)


def _file_record(path: Path, project_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"provenance source is missing: {resolved}")
    raw = resolved.read_bytes()
    return {
        "path": _display_path(resolved, project_root),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _git_snapshot(project_root: Path) -> dict[str, Any]:
    revision_result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    revision = revision_result.stdout.strip()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise EncoderError(f"unexpected git revision: {revision!r}")
    diff_result = subprocess.run(
        [
            "git",
            "-C",
            str(project_root),
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "HEAD",
            "--",
        ],
        check=True,
        capture_output=True,
    )
    tracked_diff = diff_result.stdout
    return {
        "head": revision,
        "tracked_dirty": bool(tracked_diff),
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "tracked_diff_size_bytes": len(tracked_diff),
    }


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _write_outputs(
    *,
    model: EncodedModel,
    snapshots: Mapping[str, Snapshot],
    out_path: Path,
    meta_path: Path,
    var_map_path: Path,
    project_root: Path,
    argv_record: Sequence[str],
) -> dict[str, Any]:
    paths = [out_path.resolve(), meta_path.resolve(), var_map_path.resolve()]
    if len(set(paths)) != len(paths):
        raise EncoderError("OPB, metadata, and variable-map outputs must be distinct")
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite existing output(s): " + ", ".join(existing))

    equal_count = sum(constraint.relation == "=" for constraint in model.constraints)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("x", encoding="ascii", newline="\n") as handle:
        handle.write(
            f"* #variable= {len(model.variables)} #constraint= {len(model.constraints)} "
            f"#equal= {equal_count} intsize= 64\n"
        )
        handle.write(
            "* front_clear_relaxation generated_by=pb_encoder_v2 "
            f"semantics={SEMANTICS} ghost={model.ghost_width}x{model.ghost_height} "
            f"grid={model.grid_width}x{model.grid_height}\n"
        )
        for constraint in model.constraints:
            handle.write(constraint.render())
            handle.write("\n")

    var_map_payload = {
        "schema_version": "front_clear_pb_var_map_v2",
        "semantics": SEMANTICS,
        "variable_count": len(model.variables),
        "variables": model.variables,
    }
    _exclusive_json(var_map_path, var_map_payload)

    input_records = {key: snapshots[key].record() for key in sorted(snapshots)}
    git_snapshot = _git_snapshot(project_root)
    meta = {
        "schema_version": SCHEMA_VERSION,
        "semantics": SEMANTICS,
        "harness": "pb_encoder_v2",
        "harness_source": _file_record(Path(__file__), project_root),
        "git_revision": git_snapshot["head"],
        "git_snapshot": git_snapshot,
        "argv": list(argv_record),
        "execution": {"random_seed": None, "workers": None},
        "grid": {"width": model.grid_width, "height": model.grid_height},
        "ghost": {"width": model.ghost_width, "height": model.ghost_height},
        "inputs": input_records,
        "outputs": {
            "opb": str(out_path.resolve()),
            "meta": str(meta_path.resolve()),
            "var_map": str(var_map_path.resolve()),
            "opb_sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
            "var_map_sha256": hashlib.sha256(var_map_path.read_bytes()).hexdigest(),
        },
        "template_counts": model.template_counts,
        "template_demands": model.template_demands,
        "routing_free_sink_commodities": model.routing_free_sink_commodities,
        "stats": model.stats,
        "soundness_scope": [
            "mandatory instances are anonymous within each facility template",
            "occupancy equality channels body non-overlap",
            "unknown demand omits template front constraints",
            "inconsistent known demand uses the componentwise minimum",
            "stored port x/y is the front cell; direction is validation-only",
            "front cells may be shared by any number of ports",
            "power, binding, routing, and optional facilities are omitted",
            "one ghost anchor is selected and excludes mandatory body occupancy",
        ],
        "proof_status": "translation_only_no_unsat_or_proof_claim",
        "historical_v1_status": HISTORICAL_V1_STATUS,
    }
    _exclusive_json(meta_path, meta)
    return meta


def _default_output(path: Path, suffix: str) -> Path:
    return path.with_suffix(suffix)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", type=Path, default=PROJECT_ROOT / INPUT_PATHS["candidate_placements"])
    parser.add_argument("--instances", type=Path, default=PROJECT_ROOT / INPUT_PATHS["mandatory_instances"])
    parser.add_argument("--generic-io", type=Path, default=PROJECT_ROOT / INPUT_PATHS["generic_io_requirements"])
    parser.add_argument("--canonical-rules", type=Path, default=PROJECT_ROOT / INPUT_PATHS["canonical_rules"])
    parser.add_argument("--preprocess-plan", type=Path, default=PROJECT_ROOT / INPUT_PATHS["preprocess_plan"])
    parser.add_argument("--ghost-w", type=int, default=6)
    parser.add_argument("--ghost-h", type=int, default=6)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--meta-out", type=Path)
    parser.add_argument("--var-map-out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    args.project_root = args.project_root.resolve()
    meta_path = args.meta_out or _default_output(args.out, ".meta.json")
    var_map_path = args.var_map_out or _default_output(args.out, ".var_map.json")
    snapshots = _load_snapshots(args)

    candidate_payload = _json_payload(snapshots["candidate_placements"])
    instances_payload = _json_payload(snapshots["mandatory_instances"])
    preprocess_plan_payload = _json_payload(snapshots["preprocess_plan"])
    model = build_model(
        candidate_payload=candidate_payload,
        instances_payload=instances_payload,
        generic_io_text=snapshots["generic_io_requirements"].text,
        canonical_rules_text=snapshots["canonical_rules"].text,
        preprocess_plan_payload=preprocess_plan_payload,
        ghost_width=args.ghost_w,
        ghost_height=args.ghost_h,
        project_root=args.project_root,
    )
    argv_record = (
        list(sys.argv)
        if argv is None
        else [str(Path(__file__).resolve()), *[str(value) for value in argv]]
    )
    meta = _write_outputs(
        model=model,
        snapshots=snapshots,
        out_path=args.out,
        meta_path=meta_path,
        var_map_path=var_map_path,
        project_root=args.project_root,
        argv_record=argv_record,
    )
    print(
        json.dumps(
            {
                "status": "generated",
                "semantics": SEMANTICS,
                "opb": meta["outputs"]["opb"],
                "variables": model.stats["variables"],
                "constraints": model.stats["constraints"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
