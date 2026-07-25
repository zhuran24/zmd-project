#!/usr/bin/env python3
"""Production-typed Gate-1 v4 forced-positive pair builder.

This module is deliberately narrower than a solver experiment.  A caller must
already have created the campaign-bound formal-positive selection and must
provide one fresh, pre-registered export directory.  The builder then:

1. builds and solves one small genuine ``MasterPlacementModel`` with one worker;
2. seals the official binary model, complete ``CpSolverResponse``, solution and
   incumbent before either arm clone exists;
3. seals both arm bindings;
4. creates two fresh byte-identical pre-injection masters;
5. sends the control through an empty provider and the treatment through a
   forced *genuine* F1 ``region_capacity`` provider while retaining the real
   adapter, production registry/compiler, sole resolver and step-8 lowering;
6. never solves either post-injection model.

The fixture has 46 mandatory one-cell boundary placements.  Its frozen F1
state leaves capacity 45 in the left-or-bottom union, so the production cut is
active at the selected 1x1 ghost and excludes the sealed 46-placement
incumbent.  This is a mechanism positive control only.  It does not establish
family-global soundness, organic runtime usefulness, SAT/UNSAT, or B6
promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from unittest import mock

from google.protobuf import text_format
from ortools.sat import cp_model_pb2

from src.cuts.ledger import CutLedgerWriter, read_segment
from src.cuts.lifecycle import BState, GroupState, compute_source_digest
from src.cuts.oracles.region_capacity_oracle import (
    generate_region_capacity_cuts,
)
from src.models.cut_manager import CutManager
from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import LBBDController


FORMAL_SELECTION_SCHEMA = "noncert-cuts-gate1-v4-formal-positive-selection-v1"
FORMAL_PURPOSE = "gate1_v4_formal_campaign_positive_control"
PRODUCTION_DRILL_SELECTION_SCHEMA = "noncert-cuts-gate1-v4-production-drill-positive-selection-v1"
PRODUCTION_DRILL_PURPOSE = "gate1_v4_disposable_production_positive_control"
FORMAL_PROFILE = "formal_campaign"
PRODUCTION_DRILL_PROFILE = "disposable_drill"
FORMAL_ARM_SCHEMA = "noncert-cuts-gate1-v4-formal-positive-control-arm-v1"
FORMAL_COMPILED_SCHEMA = "noncert-cuts-gate1-v4-formal-production-compiled-record-v1"
FORMAL_ATTACH_SCHEMA = "noncert-cuts-gate1-v4-production-typed-attach-trace-v1"
ARITHMETIC_CORPUS_SCHEMA = "noncert-cuts-gate1-v4-arithmetic-corpus-v1"
ATTACH_TRIGGER = "binding_infeasible"
ATTACH_ITERATION = 1001
GRID_SIZE = 70
FACILITY_TYPE = "boundary_storage_port"
OPERATION_TYPE = "boundary_io"
MANDATORY_COUNT = 46
EXPECTED_CAPACITY = 45
EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
_RESEARCH_DIR = Path(__file__).resolve().parent
if "_PROJECT_ROOT" not in globals():
    _PROJECT_ROOT = _RESEARCH_DIR.parents[3]


def _load_support() -> ModuleType:
    path = _RESEARCH_DIR / "positive_control_v4.py"
    spec = importlib.util.spec_from_file_location(
        "noncert_cuts_gate1_v4_positive_support",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load positive-control support: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if "_SUPPORT" not in globals():
    _SUPPORT = _load_support()
    _SUPPORT_SELECTED_IDENTITY: Mapping[str, object] | None = None


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _require_fresh_directory(path: Path) -> Path:
    return _SUPPORT._mkdir_exclusive(_absolute(path))  # noqa: SLF001


def _read_profile_selection(
    root: Path,
    *,
    selection_schema: str,
    purpose: str,
    formal_eligible: bool,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    value, identity = _SUPPORT._read_json(  # noqa: SLF001
        root / "selection.json",
        label=f"{label} positive selection",
    )
    expected_keys = {
        "schema",
        "purpose",
        "campaign_id",
        "run_nonce",
        "manager_epoch_digest",
        "gate1_formal_eligible",
    }
    if (
        type(value) is not dict
        or set(value) != expected_keys
        or value.get("schema") != selection_schema
        or value.get("purpose") != purpose
        or value.get("gate1_formal_eligible") is not formal_eligible
        or any(
            type(value.get(key)) is not str or not value[key]
            for key in ("campaign_id", "run_nonce", "manager_epoch_digest")
        )
    ):
        raise ValueError(f"{label} positive selection drifted")
    return value, identity


def _read_selection(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    return _read_profile_selection(
        root,
        selection_schema=FORMAL_SELECTION_SCHEMA,
        purpose=FORMAL_PURPOSE,
        formal_eligible=True,
        label="formal campaign",
    )


def _read_drill_selection(
    root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    return _read_profile_selection(
        root,
        selection_schema=PRODUCTION_DRILL_SELECTION_SCHEMA,
        purpose=PRODUCTION_DRILL_PURPOSE,
        formal_eligible=False,
        label="disposable production drill",
    )


def _sources(*, purpose: str = FORMAL_PURPOSE) -> dict[str, object]:
    instances = [
        {
            "instance_id": f"boundary_{index:03d}",
            "facility_type": FACILITY_TYPE,
            "operation_type": OPERATION_TYPE,
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for index in range(MANDATORY_COUNT)
    ]
    poses = [
        {
            "pose_id": f"boundary_pose_{index:03d}",
            "anchor": {"x": x, "y": 0},
            "occupied_cells": [[x, 0]],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }
        for index, x in enumerate(range(1, MANDATORY_COUNT + 1))
    ]
    pools = {FACILITY_TYPE: poses}
    rules = {
        "globals": {"grid": {"width": GRID_SIZE, "height": GRID_SIZE}},
        "facility_templates": {
            FACILITY_TYPE: {
                "placement_rule": "left_or_bottom_boundary",
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
            }
        },
    }
    candidates = {"facility_pools": pools}
    digest_sources = {
        "candidate_placements": candidates,
        "canonical_rules": rules,
        "certified_exact_source_tree": {
            "repository_head": EXPECTED_HEAD,
            "purpose": purpose,
        },
        "commodity_demands": {},
        "generic_io_requirements": {},
        "mandatory_exact_instances": instances,
        "orbit_homogeneity_digest": {
            "facility_type": FACILITY_TYPE,
            "homogeneous": True,
        },
        "preprocess_plan": {
            "fixture": "gate1_v4_forced_positive",
            "schema_version": 1,
        },
    }
    artifact_hashes = {
        role: hashlib.sha256(
            b"cuts-gate1-v4-formal-positive:" + role.encode("utf-8") + b":" + canonical_json(payload)
        ).hexdigest()
        for role, payload in digest_sources.items()
    }
    return {
        "instances": instances,
        "poses": poses,
        "pools": pools,
        "rules": rules,
        "candidates": candidates,
        "artifact_hashes": artifact_hashes,
    }


def _build_core(sources: Mapping[str, object]) -> object:
    return MasterPlacementModel.build_exact_core(
        sources["instances"],
        sources["pools"],
        sources["rules"],
        skip_power_coverage=True,
        enable_symmetry_breaking=False,
    )


def _prepare_master(
    core: object,
    sources: Mapping[str, object],
) -> MasterPlacementModel:
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    if (
        len(master._ghost_domains) != GRID_SIZE * GRID_SIZE
        or len(master.u_vars) != GRID_SIZE * GRID_SIZE
        or master._ghost_domains[0].get("anchor") != {"x": 0, "y": 0}
        or master.u_vars[0].Name() != "ghost__0_0_1_1"
    ):
        raise RuntimeError("real master ghost selector topology drifted")

    # The positive control is bound to the first real master ghost selector.
    master.model.Add(master.u_vars[0] == 1)

    # The independent checker uses these mandatory-presence aliases to join
    # strict instance identities to the complete response.  They are exact
    # constants because every row in this fixture is mandatory.  Arithmetic is
    # still reconstructed from the real post-model presence terms, not aliases.
    for row in sources["instances"]:
        alias = master.model.NewBoolVar(f"select__{row['instance_id']}")
        master.model.Add(alias == 1)

    # Step-8's region-capacity lowerer uses content-addressed pose-presence
    # literals.  Pre-mint only those definitional literals before the common
    # solve so the later production attach appends exactly one inequality and
    # no helper definitions.  The treatment still obtains that inequality
    # exclusively through step_8_apply_to_master.
    delegate = master._coordinate_delegate
    if delegate is None:
        raise RuntimeError("formal positive fixture lacks exact coordinate delegate")
    groups = list(master._mandatory_groups)
    if len(groups) != 1:
        raise RuntimeError("formal positive fixture mandatory grouping drifted")
    group_id = str(groups[0]["group_id"])
    slots = list(delegate.mandatory_slots.get(group_id, []))
    pose_tuples = delegate._template_pose_tuple_by_idx.get(FACILITY_TYPE, {})  # noqa: SLF001
    if len(slots) != MANDATORY_COUNT or len(pose_tuples) != MANDATORY_COUNT:
        raise RuntimeError("formal positive fixture master domain drifted")
    for pose_index in sorted(pose_tuples):
        literal = delegate._pose_present_literal(  # noqa: SLF001
            slots,
            pose_tuples[pose_index],
        )
        if literal is None:
            raise RuntimeError("real pose-presence prewarm failed")
    return master


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _export_model(
    master: MasterPlacementModel,
    path: Path,
) -> tuple[bytes, dict[str, object]]:
    """Use the supported official binary export into one owned fresh directory."""

    absolute = _absolute(path)
    _SUPPORT._reject_symlink_components(absolute)  # noqa: SLF001
    if absolute.exists() or absolute.is_symlink():
        raise FileExistsError(f"refusing to overwrite model export: {absolute}")
    parent_mode = os.lstat(absolute.parent).st_mode
    if stat.S_ISLNK(parent_mode) or not stat.S_ISDIR(parent_mode):
        raise ValueError("model export parent is not a real directory")
    if not master.model.export_to_file(str(absolute)):
        raise RuntimeError(f"official CpModel export failed: {absolute}")
    _fsync_directory(absolute.parent)
    raw, identity = _SUPPORT._read_regular(absolute)  # noqa: SLF001
    parsed = cp_model_pb2.CpModelProto()
    consumed = parsed.ParseFromString(raw)
    if consumed != len(raw) or parsed.SerializeToString(deterministic=True) != raw:
        raise ValueError("official model export is not canonical binary CpModelProto")
    return raw, identity


def _response_bytes(master: MasterPlacementModel) -> bytes:
    if master._solver is None:
        raise RuntimeError("pre-injection master has no solver response")
    generated = cp_model_pb2.CpSolverResponse()
    text_format.Parse(str(master._solver.ResponseProto()), generated)
    raw = generated.SerializeToString(deterministic=True)
    replay = cp_model_pb2.CpSolverResponse()
    if replay.ParseFromString(raw) != len(raw):
        raise RuntimeError("complete solver response did not round-trip")
    if replay.status not in {cp_model_pb2.FEASIBLE, cp_model_pb2.OPTIMAL} or len(replay.solution) != len(
        master.model.Proto().variables
    ):
        raise RuntimeError("pre-injection solver response is incomplete")
    return raw


def _build_state(
    master: MasterPlacementModel,
    sources: Mapping[str, object],
) -> BState:
    groups = list(master._mandatory_groups)
    if len(groups) != 1:
        raise RuntimeError("formal positive fixture mandatory grouping drifted")
    group_id = str(groups[0]["group_id"])
    union = {(x, 0) for x in range(GRID_SIZE)} | {(0, y) for y in range(GRID_SIZE)}
    ghost_cells = frozenset({(0, 0)})
    unblocked_candidate_cells = {(x, 0) for x in range(1, EXPECTED_CAPACITY + 1)}
    exterior_blocks = frozenset(union - set(ghost_cells) - unblocked_candidate_cells)
    if (
        len(union) != 139
        or len(exterior_blocks) != 93
        or len(union - set(ghost_cells) - set(exterior_blocks)) != EXPECTED_CAPACITY
    ):
        raise RuntimeError("formal positive capacity construction drifted")
    state = BState(
        groups={
            group_id: GroupState(
                group_id=group_id,
                demand=MANDATORY_COUNT,
                pose_domain=frozenset(str(pose["pose_id"]) for pose in sources["poses"]),
                selected_poses=[],
            )
        },
        ghost_rect=(0, 0, 1, 1),
        ghost_cells=ghost_cells,
        exterior_blocks=exterior_blocks,
        artifact_hashes=dict(sources["artifact_hashes"]),
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=sources["rules"],
        instance_to_facility_type={group_id: FACILITY_TYPE},
        facility_templates=sources["rules"]["facility_templates"],
        candidate_placements=sources["candidates"],
    )
    state.source_digest = compute_source_digest(state)
    return state


def _jsonable_parameter(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable_parameter(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, tuple):
        return [_jsonable_parameter(item) for item in value]
    if type(value) in {str, int, bool} or value is None:
        return value
    raise TypeError(f"unsupported formal plan parameter: {type(value).__name__}")


def _constraint_projection(
    post_model_raw: bytes,
    pre_model_raw: bytes,
) -> tuple[cp_model_pb2.CpModelProto, dict[str, object]]:
    pre = cp_model_pb2.CpModelProto()
    post = cp_model_pb2.CpModelProto()
    if (
        pre.ParseFromString(pre_model_raw) != len(pre_model_raw)
        or post.ParseFromString(post_model_raw) != len(post_model_raw)
        or len(post.constraints) != len(pre.constraints) + 1
    ):
        raise RuntimeError("production treatment did not append exactly one constraint")
    stripped = cp_model_pb2.CpModelProto()
    stripped.CopyFrom(post)
    del stripped.constraints[-1]
    if stripped.SerializeToString(deterministic=True) != pre_model_raw:
        raise RuntimeError("production treatment changed bytes outside one constraint")
    constraint = post.constraints[-1]
    if constraint.WhichOneof("constraint") != "linear":
        raise RuntimeError("production treatment appended a non-linear constraint")
    return post, {
        "index": len(post.constraints) - 1,
        "name": str(constraint.name),
        "vars": [int(value) for value in constraint.linear.vars],
        "coeffs": [int(value) for value in constraint.linear.coeffs],
        "domain": [int(value) for value in constraint.linear.domain],
        "enforcement_literals": [int(value) for value in constraint.enforcement_literal],
    }


def _compiled_record(
    compiled: object,
    binding: object,
    *,
    post_model_raw: bytes,
    pre_model_raw: bytes,
) -> tuple[dict[str, object], cp_model_pb2.CpModelProto]:
    from src.cuts.typed_platform import CompiledCut

    if type(compiled) is not CompiledCut:
        raise TypeError("formal treatment did not produce an exact CompiledCut")
    post, constraint = _constraint_projection(post_model_raw, pre_model_raw)
    plan = compiled.plan
    condition_literals = [
        {
            "index": int(literal.Index()),
            "name": str(literal.Name()),
        }
        for literal in binding.condition_lits
    ]
    if (
        plan.family != "region_capacity"
        or plan.operation != "region_capacity_le"
        or plan.parameters.get("capacity") != EXPECTED_CAPACITY
        or len(condition_literals) != 1
        or condition_literals[0]["index"] not in constraint["enforcement_literals"]
    ):
        raise RuntimeError("compiled production F1 plan drifted")
    plan_record = {
        "schema_version": int(plan.schema_version),
        "family": str(plan.family),
        "operation": str(plan.operation),
        "parameters": _jsonable_parameter(plan.parameters),
        "model_scope": {
            "ghost_policy": str(plan.model_scope.ghost_policy),
            "ghost_rect_digest": plan.model_scope.ghost_rect_digest,
            "domain_fingerprint": str(plan.model_scope.domain_fingerprint),
        },
        "semantic_fingerprint": str(plan.semantic_fingerprint),
        "digest": str(plan.digest),
    }
    return (
        {
            "schema": FORMAL_COMPILED_SCHEMA,
            "cut_id": str(compiled.cut_id),
            "family": "region_capacity",
            "operation": "region_capacity_le",
            "plan": plan_record,
            "plan_digest": str(plan.digest),
            "compiled_digest": str(compiled.digest),
            "semantic_fingerprint": str(plan.semantic_fingerprint),
            "condition_literals": condition_literals,
            "post_constraint": constraint,
        },
        post,
    )


def _assignment(
    *,
    common_prestate_id: str,
    model_raw: bytes,
    response_raw: bytes,
) -> tuple[dict[str, object], cp_model_pb2.CpSolverResponse]:
    model = cp_model_pb2.CpModelProto()
    response = cp_model_pb2.CpSolverResponse()
    if (
        model.ParseFromString(model_raw) != len(model_raw)
        or response.ParseFromString(response_raw) != len(response_raw)
        or len(response.solution) != len(model.variables)
    ):
        raise RuntimeError("formal assignment authority is incomplete")
    return (
        {
            "schema": _SUPPORT.ASSIGNMENT_SCHEMA,
            "common_prestate_id": common_prestate_id,
            "pre_model_sha256": hashlib.sha256(model_raw).hexdigest(),
            "response_sha256": hashlib.sha256(response_raw).hexdigest(),
            "variables": [
                {
                    "index": index,
                    "name": str(model.variables[index].name),
                    "value": int(response.solution[index]),
                }
                for index in range(len(model.variables))
            ],
        },
        response,
    )


def _arithmetic_sample(
    compiled: Mapping[str, object],
    response: cp_model_pb2.CpSolverResponse,
) -> dict[str, object]:
    constraint = compiled["post_constraint"]
    plan = compiled["plan"]
    variables = constraint["vars"]
    coefficients = constraint["coeffs"]
    lhs = sum(
        coefficient * int(response.solution[index]) for index, coefficient in zip(variables, coefficients, strict=True)
    )
    rhs = int(constraint["domain"][1])
    weights = plan["parameters"]["group_cell_weights"]
    if len(weights) != 1:
        raise RuntimeError("formal positive fixture expected one F1 group")
    group_id, weight = next(iter(weights.items()))
    if any(coefficient != weight for coefficient in coefficients):
        raise RuntimeError("post-model coefficients differ from compiled F1 weight")
    selected_count = sum(int(response.solution[index]) for index in variables)
    enforcement = [
        {
            **compiled["condition_literals"][0],
            "value": int(response.solution[compiled["condition_literals"][0]["index"]]),
        }
    ]
    if (
        selected_count != MANDATORY_COUNT
        or lhs != MANDATORY_COUNT
        or rhs != EXPECTED_CAPACITY
        or enforcement[0]["value"] != 1
    ):
        raise RuntimeError("genuine F1 inequality does not exclude frozen incumbent")
    return {
        "schema": _SUPPORT.SAMPLE_SCHEMA,
        "cut_id": compiled["cut_id"],
        "family": "region_capacity",
        "operation": "region_capacity_le",
        "plan_digest": compiled["plan_digest"],
        "compiled_digest": compiled["compiled_digest"],
        "parameters": plan["parameters"],
        "enforcement_literals": enforcement,
        "contributions": [
            {
                "label": group_id,
                "selected_count": selected_count,
                "weight": weight,
                "value": lhs,
            }
        ],
        "lhs": lhs,
        "rhs": rhs,
        "active": True,
        "violated": True,
    }


def _production_attach(
    *,
    arm: str,
    master: MasterPlacementModel,
    state: BState,
    forced_cut: object,
    arm_dir: Path,
    common_prestate_id: str,
    artifact_hashes: Mapping[str, str],
) -> dict[str, object]:
    from src.cuts import lifecycle, typed_platform
    from src.cuts.typed_platform import CompiledCut

    checkpoint_dir = arm_dir / "checkpoint"
    cut_manager = CutManager(
        checkpoint_dir,
        solve_mode="exploratory",
        current_hashes=artifact_hashes,
    )
    ledger_writer = CutLedgerWriter(
        arm_dir / "production-ledger",
        scope_id=f"gate1-v4-{arm}",
        writer_id=f"gate1-v4-{arm}-writer",
        genesis_context={
            "arm": arm,
            "common_prestate_id": common_prestate_id,
        },
    )
    controller = LBBDController(
        master=master,
        cut_manager=cut_manager,
        project_root=_PROJECT_ROOT,
        solve_mode="exploratory",
        artifact_hashes=artifact_hashes,
        enabled_cut_families={"region_capacity"},
        cut_ledger=ledger_writer,
    )
    real_adapter = typed_platform.cut_to_envelope_v1
    real_compiler = typed_platform.validate_and_compile_cut
    real_resolver = lifecycle._resolve_model_scope_binding
    real_step_8 = lifecycle.step_8_apply_to_master
    captured: dict[str, list[object]] = {
        "provider": [],
        "adapter": [],
        "compiler": [],
        "resolver": [],
        "step_8": [],
    }

    def provider(*_args: object, **_kwargs: object) -> list[object]:
        values = [] if arm == "control" else [forced_cut]
        captured["provider"].append(tuple(values))
        return values

    def adapter(*args: object, **kwargs: object) -> object:
        result = real_adapter(*args, **kwargs)
        captured["adapter"].append(result)
        return result

    def compiler(*args: object, **kwargs: object) -> object:
        result = real_compiler(*args, **kwargs)
        captured["compiler"].append(result)
        return result

    def resolver(*args: object, **kwargs: object) -> object:
        result = real_resolver(*args, **kwargs)
        captured["resolver"].append(result)
        return result

    def step_8(*args: object, **kwargs: object) -> object:
        result = real_step_8(*args, **kwargs)
        captured["step_8"].append(args[0] if args else None)
        return result

    before_variables = len(master.model.Proto().variables)
    before_constraints = len(master.model.Proto().constraints)
    try:
        with (
            mock.patch.dict(
                os.environ,
                {
                    "EXACT_CUT_FRAMEWORK_ATTACH": "1",
                    "EXACT_CUT_FRAMEWORK_ATTACH_BUDGET": "8",
                },
            ),
            mock.patch.object(
                controller,
                "_build_cut_framework_state",
                return_value=state,
            ),
            mock.patch(
                "src.cuts.oracles.region_capacity_oracle.generate_region_capacity_cuts",
                side_effect=provider,
            ),
            mock.patch(
                "src.cuts.typed_platform.cut_to_envelope_v1",
                side_effect=adapter,
            ),
            mock.patch(
                "src.cuts.typed_platform.validate_and_compile_cut",
                side_effect=compiler,
            ),
            mock.patch(
                "src.cuts.lifecycle._resolve_model_scope_binding",
                side_effect=resolver,
            ),
            mock.patch(
                "src.cuts.lifecycle.step_8_apply_to_master",
                side_effect=step_8,
            ),
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger=ATTACH_TRIGGER,
                iteration=ATTACH_ITERATION,
                solution=None,
            )
    except Exception:
        ledger_writer.__exit__(*__import__("sys").exc_info())
        raise
    ledger_writer.seal()

    after_variables = len(master.model.Proto().variables)
    after_constraints = len(master.model.Proto().constraints)
    expected = 0 if arm == "control" else 1
    if (
        attached != expected
        or len(captured["provider"]) != 1
        or len(captured["adapter"]) != expected
        or len(captured["compiler"]) != expected
        or len(captured["resolver"]) != expected
        or len(captured["step_8"]) != expected
        or after_variables != before_variables
        or after_constraints != before_constraints + expected
    ):
        raise RuntimeError(f"{arm} did not traverse the exact production attach path")
    if arm == "treatment" and type(captured["compiler"][0]) is not CompiledCut:
        raise RuntimeError("treatment compiler did not return an exact CompiledCut")
    return {
        "attached": attached,
        "compiled": captured["compiler"],
        "bindings": captured["resolver"],
        "ledger_path": ledger_writer.path,
        "trace": {
            "schema": FORMAL_ATTACH_SCHEMA,
            "status": "PASS_PRODUCTION_TYPED_ATTACH",
            "arm": arm,
            "attach_entrypoint": "LBBDController._maybe_attach_framework_cuts",
            "adapter_entrypoint": "cut_to_envelope_v1",
            "compiler_entrypoint": "validate_and_compile_cut",
            "resolver_entrypoint": "_resolve_model_scope_binding",
            "apply_entrypoint": "step_8_apply_to_master",
            "attached": attached,
            "post_solve_performed": False,
        },
    }


def _materialize_arm(
    *,
    root: Path,
    export_dir: Path,
    arm: str,
    core: object,
    sources: Mapping[str, object],
    state: BState,
    forced_cut: object,
    pre_model_raw: bytes,
    response_raw: bytes,
) -> dict[str, object]:
    common, binding, artifacts = _SUPPORT._load_binding_state(root, arm)  # noqa: SLF001
    arms_dir = root / "arms"
    if not arms_dir.exists():
        _require_fresh_directory(arms_dir)
    elif arms_dir.is_symlink() or not arms_dir.is_dir():
        raise ValueError("formal arms root is not a real directory")
    arm_dir = _require_fresh_directory(arms_dir / arm)

    clone = _prepare_master(core, sources)
    clone_pre_raw, _clone_pre_identity = _export_model(
        clone,
        export_dir / f"{arm}-pre-injection-clone.pb",
    )
    if clone_pre_raw != pre_model_raw:
        raise RuntimeError(f"{arm} clone differs from the common pre-injection model")

    attach = _production_attach(
        arm=arm,
        master=clone,
        state=state,
        forced_cut=forced_cut,
        arm_dir=arm_dir,
        common_prestate_id=str(common["common_prestate_id"]),
        artifact_hashes=sources["artifact_hashes"],
    )
    post_model_raw, post_model_identity = _export_model(
        clone,
        arm_dir / "post-injection-model.pb",
    )
    assignment, response = _assignment(
        common_prestate_id=str(common["common_prestate_id"]),
        model_raw=pre_model_raw,
        response_raw=response_raw,
    )
    assignment_identity = _SUPPORT._write_json_exclusive(  # noqa: SLF001
        arm_dir / "assignment.json",
        assignment,
    )

    compiled_records: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    if arm == "control":
        if post_model_raw != pre_model_raw:
            raise RuntimeError("formal control clone was not an exact empty injection")
    else:
        if len(attach["compiled"]) != 1 or len(attach["bindings"]) != 1:
            raise RuntimeError("formal treatment lacks one compiled cut and binding")
        compiled, _post = _compiled_record(
            attach["compiled"][0],
            attach["bindings"][0],
            post_model_raw=post_model_raw,
            pre_model_raw=pre_model_raw,
        )
        compiled_records.append(compiled)
        samples.append(_arithmetic_sample(compiled, response))

    sample_corpus = {
        "schema": ARITHMETIC_CORPUS_SCHEMA,
        "arm": arm,
        "common_prestate_id": common["common_prestate_id"],
        "samples": samples,
    }
    sample_identity = _SUPPORT._write_json_exclusive(  # noqa: SLF001
        arm_dir / "arithmetic-samples.json",
        sample_corpus,
    )
    ledger_raw, _production_ledger_identity = _SUPPORT._read_regular(  # noqa: SLF001
        attach["ledger_path"],
    )
    ledger_result = read_segment(attach["ledger_path"])
    if ledger_result.status != "complete":
        raise RuntimeError(f"{arm} production ledger did not seal completely")
    ledger_identity = _SUPPORT._write_exclusive(  # noqa: SLF001
        arm_dir / "ledger.jsonl",
        ledger_raw,
    )

    generated = 0 if arm == "control" else 1
    injection = {
        "enabled": arm == "treatment",
        "provider": ("forced_production_region_capacity_provider" if arm == "treatment" else "empty_control_provider"),
        "generated": generated,
        "compiled": len(compiled_records),
        "applied": int(attach["attached"]),
        "compiled_records": compiled_records,
    }
    evidence = {
        "schema": FORMAL_ARM_SCHEMA,
        "arm": arm,
        "phase": "formal_post_injection_clone",
        "campaign_id": common["campaign_id"],
        "run_nonce": common["run_nonce"],
        "manager_epoch_digest": common["manager_epoch_digest"],
        "selection_identity": common["selection_identity"],
        "common_prestate_id": common["common_prestate_id"],
        "common_manifest_identity": binding["binding"]["common_manifest_identity"],
        "binding_identity": binding["binding_identity"],
        "binding_set_identity": binding["binding_set_identity"],
        "pre_model_identity": common["artifacts"]["pre_model"],
        "pre_response_identity": common["artifacts"]["response"],
        "post_model_identity": post_model_identity,
        "assignment_identity": assignment_identity,
        "sample_corpus_identity": sample_identity,
        "ledger_identity": ledger_identity,
        "post_solve_performed": False,
        "post_response_present": False,
        "injection": injection,
        "production_attach": attach["trace"],
        "ledger": {
            "event_count": len(ledger_result.events),
            "tail_hash": ledger_result.tail_hash,
        },
        "claim_boundary": {
            "established": (
                [
                    "one genuine production F1 cut traversed the typed attach chain",
                    "the concrete active inequality excludes the frozen incumbent",
                ]
                if arm == "treatment"
                else ["the control clone received an exact empty injection"]
            ),
            "not_established": [
                "post-attach solver result",
                "organic runtime usefulness",
                "family-global soundness",
                "B6 promotion",
                "SAT or UNSAT",
            ],
        },
    }
    evidence_identity = _SUPPORT._write_json_exclusive(  # noqa: SLF001
        arm_dir / "evidence.json",
        evidence,
    )
    return {
        **evidence,
        "evidence_identity": evidence_identity,
    }


def _prepare_positive_common(
    root: Path,
    *,
    export_dir: Path,
    solve_seconds: float = 5.0,
    selection_reader: object,
    purpose: str,
    profile: str,
) -> dict[str, object]:
    """Seal one profile's solved common prestate and both bindings.

    ``root/selection.json`` must already exist.  ``export_dir`` must not exist;
    the builder creates it with exclusive directory creation before using the
    official binary model exporter.  A caller can therefore pre-register both
    paths in a campaign topology without allowing this module to mint
    campaign authority or any post-injection arm.
    """

    root = _absolute(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"{profile} positive root must be an existing real directory")
    if os.environ.get("EXACT_CUT_FRAMEWORK_ATTACH") is not None:
        raise ValueError("attach must be absent before the common prestate is bound")
    if not callable(selection_reader):
        raise TypeError("positive selection reader must be callable")
    selection, selection_identity = selection_reader(root)
    export_dir = _require_fresh_directory(export_dir)
    sources = _sources(purpose=purpose)
    core = _build_core(sources)

    pre_master = _prepare_master(core, sources)
    with mock.patch.dict(
        os.environ,
        {"EXACT_MASTER_CP_SAT_WORKERS": "1"},
    ):
        status = pre_master.solve(time_limit_seconds=float(solve_seconds))
    if (
        pre_master._solver is None
        or pre_master._solver.StatusName(status) not in {"FEASIBLE", "OPTIMAL"}
        or pre_master.build_stats.get("last_solve", {}).get("solver_parameters", {}).get("num_search_workers") != 1
    ):
        raise RuntimeError("single-worker formal positive pre-solve did not finish")
    incumbent = pre_master.extract_solution()
    raw_ghost_pick = incumbent.get("ghost_pick")
    if type(raw_ghost_pick) is not dict:
        raise RuntimeError("real master incumbent lacks its selected ghost")
    # The shared byte contract intentionally stores only the solver-derived
    # selector identity.  Drop unrelated presentation fields added by
    # MasterPlacementModel.extract_solution().
    incumbent["ghost_pick"] = {
        "pose_id": raw_ghost_pick.get("pose_id"),
        "pose_idx": raw_ghost_pick.get("pose_idx"),
        "anchor": raw_ghost_pick.get("anchor"),
    }
    pre_model_raw, _pre_export_identity = _export_model(
        pre_master,
        export_dir / "common-pre-injection-model.pb",
    )
    response_raw = _response_bytes(pre_master)
    common = _SUPPORT.seal_common_prestate(
        root,
        model_raw=pre_model_raw,
        response_raw=response_raw,
        incumbent=incumbent,
        selector_contract={
            "schema_version": 1,
            "grid": {"width": GRID_SIZE, "height": GRID_SIZE},
            "ghost": {"width": 1, "height": 1},
        },
        mandatory=sources["instances"],
        candidates=sources["candidates"],
        selection_identity=selection_identity,
        campaign_id=selection["campaign_id"],
        run_nonce=selection["run_nonce"],
        manager_epoch_digest=selection["manager_epoch_digest"],
    )
    bindings = _SUPPORT.create_arm_bindings(root)
    return {
        "root": str(root),
        "export_dir": str(export_dir),
        "selection_identity": selection_identity,
        "common": common,
        "bindings": bindings,
        "post_attach_solve_performed": False,
        "claim_boundary": "common_prestate_and_bindings_only",
    }


def prepare_formal_positive_common(
    root: Path,
    *,
    export_dir: Path,
    solve_seconds: float = 5.0,
) -> dict[str, object]:
    """Formal-only common-prestate builder."""

    return _prepare_positive_common(
        root,
        export_dir=export_dir,
        solve_seconds=solve_seconds,
        selection_reader=_read_selection,
        purpose=FORMAL_PURPOSE,
        profile=FORMAL_PROFILE,
    )


def prepare_disposable_positive_common(
    root: Path,
    *,
    export_dir: Path,
    solve_seconds: float = 5.0,
) -> dict[str, object]:
    """Disposable-drill-only common-prestate builder."""

    return _prepare_positive_common(
        root,
        export_dir=export_dir,
        solve_seconds=solve_seconds,
        selection_reader=_read_drill_selection,
        purpose=PRODUCTION_DRILL_PURPOSE,
        profile=PRODUCTION_DRILL_PROFILE,
    )


def _materialize_positive_arm(
    root: Path,
    *,
    arm: str,
    export_dir: Path,
    selection_reader: object,
    purpose: str,
    profile: str,
) -> dict[str, object]:
    """Materialize one profile-bound post-model clone without solving it."""

    if arm not in {"control", "treatment"}:
        raise ValueError(f"{profile} positive arm must be control or treatment")
    root = _absolute(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"{profile} positive root must be an existing real directory")
    if os.environ.get("EXACT_CUT_FRAMEWORK_ATTACH") is not None:
        raise ValueError("attach must be absent before the selected arm callback")
    if not callable(selection_reader):
        raise TypeError("positive selection reader must be callable")
    _selection, _selection_identity = selection_reader(root)
    common, _binding, artifacts = _SUPPORT._load_binding_state(  # noqa: SLF001
        root,
        arm,
    )
    sources = _sources(purpose=purpose)
    if (
        artifacts["mandatory"] != canonical_json(sources["instances"]) + b"\n"
        or artifacts["candidates"] != canonical_json(sources["candidates"]) + b"\n"
    ):
        raise ValueError("formal positive strict source bytes drifted")
    export_dir = _require_fresh_directory(export_dir)
    core = _build_core(sources)
    state_master = _prepare_master(core, sources)
    state = _build_state(state_master, sources)
    cuts = generate_region_capacity_cuts(
        state,
        sources["rules"],
        iter_index=ATTACH_ITERATION,
    )
    if len(cuts) != 1 or cuts[0].family != "region_capacity":
        raise RuntimeError("genuine F1 provider did not produce one formal cut")
    result = _materialize_arm(
        root=root,
        export_dir=export_dir,
        arm=arm,
        core=core,
        sources=sources,
        state=state,
        forced_cut=cuts[0],
        pre_model_raw=artifacts["pre_model"],
        response_raw=artifacts["response"],
    )
    if result["common_prestate_id"] != common["common_prestate_id"]:
        raise RuntimeError(f"{profile} arm did not retain the sealed common prestate")
    return result


def materialize_formal_positive_arm(
    root: Path,
    *,
    arm: str,
    export_dir: Path,
) -> dict[str, object]:
    """Materialize one formal campaign post-model clone without solving it."""

    return _materialize_positive_arm(
        root,
        arm=arm,
        export_dir=export_dir,
        selection_reader=_read_selection,
        purpose=FORMAL_PURPOSE,
        profile=FORMAL_PROFILE,
    )


def materialize_disposable_positive_arm(
    root: Path,
    *,
    arm: str,
    export_dir: Path,
) -> dict[str, object]:
    """Materialize one disposable-drill post-model clone without solving it."""

    return _materialize_positive_arm(
        root,
        arm=arm,
        export_dir=export_dir,
        selection_reader=_read_drill_selection,
        purpose=PRODUCTION_DRILL_PURPOSE,
        profile=PRODUCTION_DRILL_PROFILE,
    )


def build_formal_positive_pair(
    root: Path,
    *,
    export_dir: Path,
    solve_seconds: float = 5.0,
) -> dict[str, object]:
    """Offline helper that exercises the strict common/control/treatment split."""

    prepared = prepare_formal_positive_common(
        root,
        export_dir=export_dir,
        solve_seconds=solve_seconds,
    )
    export_root = Path(str(prepared["export_dir"]))
    control = materialize_formal_positive_arm(
        root,
        arm="control",
        export_dir=export_root / "control",
    )
    treatment = materialize_formal_positive_arm(
        root,
        arm="treatment",
        export_dir=export_root / "treatment",
    )
    return {
        **prepared,
        "control": control,
        "treatment": treatment,
        "post_attach_solve_performed": False,
        "claim_boundary": "mechanism_positive_control_only",
    }


def build_disposable_positive_pair(
    root: Path,
    *,
    export_dir: Path,
    solve_seconds: float = 5.0,
) -> dict[str, object]:
    """Offline helper for the non-authorizing production-typed drill profile."""

    prepared = prepare_disposable_positive_common(
        root,
        export_dir=export_dir,
        solve_seconds=solve_seconds,
    )
    export_root = Path(str(prepared["export_dir"]))
    control = materialize_disposable_positive_arm(
        root,
        arm="control",
        export_dir=export_root / "control",
    )
    treatment = materialize_disposable_positive_arm(
        root,
        arm="treatment",
        export_dir=export_root / "treatment",
    )
    return {
        **prepared,
        "control": control,
        "treatment": treatment,
        "post_attach_solve_performed": False,
        "claim_boundary": "disposable_production_mechanism_positive_control_only",
    }


def _campaign_profile(
    campaign_root_identity: Mapping[str, object],
) -> str:
    path = campaign_root_identity.get("path")
    if type(path) is not str:
        raise ValueError("campaign root identity path is absent")
    root_path = Path(path)
    if not root_path.is_absolute() or root_path.name != "campaign-root.json":
        raise ValueError("campaign root identity path is not canonical")
    parent = root_path.parent.name
    if parent.startswith("dev-drill-") and len(parent) > len("dev-drill-"):
        return PRODUCTION_DRILL_PROFILE
    if parent.startswith("run-") and len(parent) > len("run-"):
        return FORMAL_PROFILE
    raise ValueError("campaign root identity parent does not select a known profile")


def run_forced_payload_v4(
    *,
    campaign_root: Mapping[str, object],
    campaign_root_identity: Mapping[str, object],
    selection: Mapping[str, object],
    selection_identity: Mapping[str, object],
    unit_slot: str,
    selected_tool_identity: Mapping[str, object],
) -> dict[str, object]:
    """Selected per-arm callback used only by the two forced Gate-1 units."""

    del selection_identity
    if unit_slot not in {"forced-control", "forced-treatment"}:
        raise ValueError("formal positive callback received a non-forced unit")
    profile = _campaign_profile(campaign_root_identity)
    expected_tool = selection.get("tools", {}).get("positive_control_formal_v4")
    support_tool = selection.get("tools", {}).get("positive_control_v4")
    if (
        type(expected_tool) is not dict
        or dict(selected_tool_identity) != expected_tool
        or type(support_tool) is not dict
        or _SUPPORT_SELECTED_IDENTITY is None
        or dict(_SUPPORT_SELECTED_IDENTITY) != support_tool
    ):
        raise ValueError("formal positive selected toolchain identity drifted")
    topology = campaign_root.get("stage_topology", {}).get("gate1_v4", {}).get("positive_control", {})
    if type(topology) is not dict:
        raise ValueError("formal positive campaign topology is absent")
    root = Path(str(topology.get("root_dir", "")))
    exports = topology.get("builder_export_dirs")
    arm_dirs = topology.get("arm_dirs")
    if (
        not root.is_absolute()
        or type(exports) is not dict
        or set(exports) != {"common", "control", "treatment"}
        or type(arm_dirs) is not dict
        or set(arm_dirs) != {"control", "treatment"}
    ):
        raise ValueError("formal positive pre-registered path map drifted")
    arm = "control" if unit_slot == "forced-control" else "treatment"
    if Path(str(arm_dirs[arm])) != root / "arms" / arm or Path(str(exports[arm])) != root / "builder-exports" / arm:
        raise ValueError("formal positive selected arm path escaped its topology")
    selection_reader = _read_selection if profile == FORMAL_PROFILE else _read_drill_selection
    arm_builder = materialize_formal_positive_arm if profile == FORMAL_PROFILE else materialize_disposable_positive_arm
    pair_selection, _pair_selection_identity = selection_reader(root)
    expected_manager_digest = hashlib.sha256(canonical_json(campaign_root["manager_epoch"]) + b"\n").hexdigest()
    if (
        pair_selection["campaign_id"] != campaign_root.get("campaign_id")
        or pair_selection["run_nonce"] != campaign_root.get("run_nonce")
        or pair_selection["manager_epoch_digest"] != expected_manager_digest
    ):
        raise ValueError("formal positive pair selection does not join campaign")
    evidence = arm_builder(
        root,
        arm=arm,
        export_dir=Path(str(exports[arm])),
    )
    return {
        "status": "PASS",
        "profile": profile,
        "arm": arm,
        "common_prestate_id": evidence["common_prestate_id"],
        "generated": evidence["injection"]["generated"],
        "compiled": evidence["injection"]["compiled"],
        "applied": evidence["injection"]["applied"],
        "support_tool_identity": dict(support_tool),
        "post_solve_performed": False,
        "organic_arm_launch_authorized": False,
        "global_claim_authorized": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--solve-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)
    result = build_formal_positive_pair(
        args.root,
        export_dir=args.export_dir,
        solve_seconds=args.solve_seconds,
    )
    print(
        json.dumps(
            {
                "status": "FORMAL_POSITIVE_PAIR_BUILT",
                "root": result["root"],
                "control": result["control"]["injection"],
                "treatment": result["treatment"]["injection"],
                "post_attach_solve_performed": False,
                "claim_boundary": result["claim_boundary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
