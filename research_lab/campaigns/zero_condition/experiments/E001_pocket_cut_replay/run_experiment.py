#!/usr/bin/env python3
"""E001: replay one proved pocket judgment through a repartitioned interface.

The runner is research-only.  It verifies the source judgment, proves the
instance-label -> group-pose transport required by the pose-bool master, adds
exactly one cut, asks for a replacement no-ghost placement, and then diagnoses
that replacement with an ordered binding/routing ladder.

Raw output is written only below ``research_lab/local``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
LOCAL_ROOT = ROOT / "research_lab/local/zero_condition/E001_pocket_cut_replay"
JUDGMENT_PATH = HERE / "JUDGMENT.json"
LOWERING_PATH = HERE / "LOWERING_CONTRACT.json"
CERTIFICATE_PATH = (
    HISTORY_ROOT
    / ".artifacts/lowerbound_ladder_20260824/blue_iron_pocket_cut/BLUE_IRON_POCKET_CUT_CERTIFICATE.json"
)
CERTIFICATE_CHECKER_PATH = (
    HISTORY_ROOT
    / ".artifacts/lowerbound_ladder_20260824/blue_iron_pocket_cut/check_blue_iron_pocket_cut.py"
)
PARENT_ASSIGNMENT_PATH = (
    HISTORY_ROOT
    / ".artifacts/lowerbound_ladder_20260824/phaseA1_noghost_master/MASTER_ASSIGNMENT_A1.json"
)
STRICT_INSTANCE_PATH = (
    HISTORY_ROOT
    / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
)

EXPECTED_BRANCH = "research/main"
EXPECTED_CERTIFICATE_SHA256 = (
    "c589d7682fe7ecdc5d8784b311d51e0f48031af70b3be1dda936a16c4ef97d17"
)
EXPECTED_CERTIFICATE_CHECKER_SHA256 = (
    "4233cc7642bcfabd64c9b76b396f8a11bb9ddf3ede7b08781426a4f94da9573a"
)
EXPECTED_PARENT_ASSIGNMENT_SHA256 = (
    "3ee4a6e7acdf8bc0aee799f4d09ac254305bf628e63afbfd1b951669d439f4f7"
)
EXPECTED_STRICT_INSTANCE_SHA256 = (
    "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
)
EXPECTED_MANDATORY_COUNT = 266
MASTER_CAP_SECONDS = 600.0
BINDING_CAP_SECONDS = 240.0
ROUTING_CAP_SECONDS = 1800.0

EXPECTED_INPUT_HASHES: dict[str, str] = {
    "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
    "rules/canonical_rules.json": (
        "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0"
    ),
    "rules/preprocess_plan.json": (
        "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee"
    ),
}
EXPECTED_RESEARCH_SOURCE_HASHES: dict[str, str] = {
    "src/models/master_model.py": (
        "d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371"
    ),
    "src/models/pose_bool_exact_master.py": (
        "8991b7f98b95ee255c4967b13fc2d22bf6eed5ec54ad1f0e48377a44db0dbd90"
    ),
    "src/models/binding_subproblem.py": (
        "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba"
    ),
    "src/models/routing_binding_context.py": (
        "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2"
    ),
    "src/models/routing_subproblem.py": (
        "7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718"
    ),
    "src/models/port_binding.py": (
        "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53"
    ),
    "src/search/pr2_l0_fixed_witness_core.py": (
        "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1"
    ),
    "src/search/exact_campaign.py": (
        "d893e59a9f1bd573208a39905bdb7d677046f97367543958cc201a90b21d1a04"
    ),
    "src/models/cp_sat_worker_config.py": (
        "4f9a4847f179f1ed15d61b17bcdc2340c82c1ec2494abd1eb7402f919c84ba50"
    ),
}
EXPECTED_ENV: dict[str, str] = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "240824",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
    "EXACT_ROUTING_CP_SAT_WORKERS": "8",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
    )


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def dump_json_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def dump_json_replace(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with temp.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def git_output(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def emit(run_dir: Path | None, event: str, **details: Any) -> None:
    payload = {"event": event, "at_utc": utc_now(), **details}
    print(json.dumps(json_safe(payload), sort_keys=True), flush=True)
    if run_dir is not None:
        dump_json_replace(run_dir / "PROGRESS.json", payload)


def verify_worker_environment() -> dict[str, Any]:
    exact_actual = {
        key: value for key, value in os.environ.items() if key.startswith("EXACT_")
    }
    mismatches = {
        key: {"expected": expected, "actual": os.environ.get(key)}
        for key, expected in EXPECTED_ENV.items()
        if os.environ.get(key) != expected
    }
    unexpected_exact = sorted(set(exact_actual) - {k for k in EXPECTED_ENV if k.startswith("EXACT_")})
    if mismatches or unexpected_exact:
        raise RuntimeError(
            f"worker environment mismatch: mismatches={mismatches}, "
            f"unexpected_exact={unexpected_exact}"
        )
    return {
        "registered": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "unexpected_exact": unexpected_exact,
    }


def verify_identity(*, require_clean: bool) -> dict[str, Any]:
    if git_output("branch", "--show-current") != EXPECTED_BRANCH:
        raise RuntimeError("E001 must run on research/main")
    tracked_status = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if require_clean and tracked_status:
        raise RuntimeError(f"tracked research worktree is not clean: {tracked_status}")

    checked: dict[str, str] = {}
    for relative, expected in sorted(EXPECTED_INPUT_HASHES.items()):
        path = HISTORY_ROOT / relative
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen input drift for {path}: {actual} != {expected}")
    for relative, expected in sorted(EXPECTED_RESEARCH_SOURCE_HASHES.items()):
        path = ROOT / relative
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"research source drift for {relative}: {actual} != {expected}")

    fixed_paths = {
        CERTIFICATE_PATH: EXPECTED_CERTIFICATE_SHA256,
        CERTIFICATE_CHECKER_PATH: EXPECTED_CERTIFICATE_CHECKER_SHA256,
        PARENT_ASSIGNMENT_PATH: EXPECTED_PARENT_ASSIGNMENT_SHA256,
        STRICT_INSTANCE_PATH: EXPECTED_STRICT_INSTANCE_SHA256,
    }
    for path, expected in fixed_paths.items():
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"external evidence drift for {path}: {actual} != {expected}")

    judgment = load_json(JUDGMENT_PATH)
    lowering = load_json(LOWERING_PATH)
    if judgment.get("status") != "PROVED_RESEARCH_JUDGMENT_REQUIRES_CHECKED_LOWERING":
        raise RuntimeError("JUDGMENT status is not admissible for E001")
    if lowering.get("status") != "FROZEN_FOR_E001_AUDIT_AND_REPLAY":
        raise RuntimeError("LOWERING_CONTRACT status is not frozen")
    certificate = load_json(CERTIFICATE_PATH)
    if certificate.get("status") != "PASS_SOUND_RESEARCH_CUT":
        raise RuntimeError("source certificate is not PASS_SOUND_RESEARCH_CUT")
    if certificate.get("logical_replay", {}).get("cut_sound_under_frozen_semantics") is not True:
        raise RuntimeError("source certificate lacks soundness conclusion")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": EXPECTED_BRANCH,
        "tracked_status": tracked_status,
        "judgment_sha256": sha256_file(JUDGMENT_PATH),
        "lowering_contract_sha256": sha256_file(LOWERING_PATH),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "interface_compiler_sha256": sha256_file(HERE / "interface_compiler.py"),
        "checked_hashes": checked,
    }


def import_stack() -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ortools.sat.python import cp_model
    from src.models.binding_subproblem import (
        PortBindingModel,
        load_binding_plan_semantics,
    )
    from src.models.master_model import (
        MasterPlacementModel,
        infer_exact_required_pose_optional_counts_for_instances,
        load_generic_io_requirements_artifact,
        load_project_data,
    )
    from src.models.routing_subproblem import RoutingSubproblem, run_exact_routing_precheck

    return {
        "cp_model": cp_model,
        "PortBindingModel": PortBindingModel,
        "MasterPlacementModel": MasterPlacementModel,
        "infer_optional_counts": infer_exact_required_pose_optional_counts_for_instances,
        "load_generic": load_generic_io_requirements_artifact,
        "load_project_data": load_project_data,
        "load_plan": load_binding_plan_semantics,
        "RoutingSubproblem": RoutingSubproblem,
        "run_exact_routing_precheck": run_exact_routing_precheck,
    }


def load_model_inputs(stack: Mapping[str, Any]) -> dict[str, Any]:
    instances, pools, rules = stack["load_project_data"](
        HISTORY_ROOT,
        solve_mode="certified_exact",
    )
    if len(instances) != EXPECTED_MANDATORY_COUNT:
        raise RuntimeError(
            f"mandatory count drift: {len(instances)} != {EXPECTED_MANDATORY_COUNT}"
        )
    generic = stack["load_generic"](HISTORY_ROOT)
    plan = stack["load_plan"](project_root=HISTORY_ROOT)
    optional_counts = stack["infer_optional_counts"](
        instances,
        rules,
        generic,
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
    )
    return {
        "instances": instances,
        "pools": pools,
        "rules": rules,
        "generic": generic,
        "plan": plan,
        "optional_counts": optional_counts,
    }


def construct_master(stack: Mapping[str, Any], inputs: Mapping[str, Any]) -> Any:
    plan = inputs["plan"]
    return stack["MasterPlacementModel"](
        inputs["instances"],
        inputs["pools"],
        inputs["rules"],
        ghost_rect=None,
        ghost_anchor_filter=None,
        skip_power_coverage=False,
        c1_power_pole_representation=True,
        enable_symmetry_breaking=True,
        generic_io_requirements=inputs["generic"],
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
        utility_operation_by_template=plan["utility_operation_by_template"],
        exact_required_pose_optional_counts=inputs["optional_counts"],
        solve_mode="certified_exact",
        master_search_profile="exact_coordinate_guided_branching_v4",
    )


def load_parent_solution() -> dict[str, dict[str, Any]]:
    payload = load_json(PARENT_ASSIGNMENT_PATH)
    if payload.get("status") not in {"FEASIBLE", "OPTIMAL"}:
        raise RuntimeError("parent assignment is not a solved master intermediate")
    raw = payload.get("solution")
    if not isinstance(raw, Mapping):
        raise RuntimeError("parent assignment lacks solution mapping")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping) and str(instance_id) != "ghost_pick"
    }
    mandatory_count = sum(bool(row.get("is_mandatory")) for row in solution.values())
    if mandatory_count != EXPECTED_MANDATORY_COUNT:
        raise RuntimeError("parent mandatory count drift")
    return solution


def _group_records(master: Any) -> dict[str, dict[str, Any]]:
    return {
        str(group["group_id"]): dict(group)
        for group in master._mandatory_groups
    }


def audit_and_attach_lowering(
    *,
    master: Any,
    inputs: Mapping[str, Any],
    parent_solution: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    certificate = load_json(CERTIFICATE_PATH)
    contract = load_json(LOWERING_PATH)
    delegate = master._coordinate_delegate
    if getattr(delegate, "master_representation", None) != "pose_bool_exact_v1":
        raise RuntimeError("E001 did not build pose_bool_exact_v1")

    certificate_literals = {
        str(row["instance_id"]): dict(row)
        for row in certificate["candidate_cut"]["literals"]
    }
    contract_literals = [dict(row) for row in contract["source_literals"]]
    if len(certificate_literals) != 4 or len(contract_literals) != 4:
        raise RuntimeError("E001 requires exactly four source literals")

    instances_by_id = {
        str(row["instance_id"]): dict(row) for row in inputs["instances"]
    }
    groups = _group_records(master)
    resolved: list[dict[str, Any]] = []
    conflict_set: dict[str, int] = {}
    mapped_var_indices: set[int] = set()
    mapped_var_names: set[str] = set()
    mandatory_group_keys: dict[str, str] = {}

    for source in contract_literals:
        source_id = str(source["source_instance_id"])
        cert_row = certificate_literals.get(source_id)
        if cert_row is None:
            raise RuntimeError(f"certificate lacks contract literal {source_id}")
        for key in ("facility_type", "pose_id"):
            if str(cert_row[key]) != str(source[key]):
                raise RuntimeError(f"certificate/contract drift for {source_id}:{key}")
        if int(cert_row["pose_idx"]) != int(source["pose_idx"]):
            raise RuntimeError(f"certificate/contract pose drift for {source_id}")

        facility_type = str(source["facility_type"])
        operation_type = str(source["operation_type"])
        pose_idx = int(source["pose_idx"])
        pose_id = str(source["pose_id"])
        pool = inputs["pools"].get(facility_type, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            raise RuntimeError(f"pose out of range for {source_id}")
        if str(pool[pose_idx].get("pose_id", "")) != pose_id:
            raise RuntimeError(f"pose identity mismatch for {source_id}")

        kind = str(source["target_literal_kind"])
        if kind == "optional_pose_presence":
            if facility_type != "power_pole":
                raise RuntimeError("only power_pole optional lowering is admitted in E001")
            variable = delegate.pole_vars.get(pose_idx)
            group_id = None
            group_members: list[str] = []
            semantic_literal = f"optional_pose::{facility_type}::{pose_idx}"
        elif kind == "mandatory_group_pose_presence":
            instance = instances_by_id.get(source_id)
            if instance is None:
                raise RuntimeError(f"mandatory source instance missing: {source_id}")
            if str(instance.get("facility_type", "")) != facility_type:
                raise RuntimeError(f"facility mismatch for {source_id}")
            if str(instance.get("operation_type", "")) != operation_type:
                raise RuntimeError(f"operation mismatch for {source_id}")
            group_id = delegate._group_id_by_instance.get(source_id)
            group = groups.get(str(group_id))
            if group is None:
                raise RuntimeError(f"group missing for {source_id}")
            if str(group["facility_type"]) != facility_type:
                raise RuntimeError(f"group facility mismatch for {source_id}")
            if str(group["operation_type"]) != operation_type:
                raise RuntimeError(f"group operation mismatch for {source_id}")
            group_members = [str(value) for value in group["instance_ids"]]
            if not group_members or int(group["count"]) != len(group_members):
                raise RuntimeError(f"group cardinality drift for {source_id}")
            for member_id in group_members:
                member = instances_by_id.get(member_id)
                if member is None:
                    raise RuntimeError(f"group member missing: {member_id}")
                if (
                    str(member.get("facility_type", "")) != facility_type
                    or str(member.get("operation_type", "")) != operation_type
                ):
                    raise RuntimeError(f"group equivalence-class drift: {member_id}")
            variable = delegate.x_vars.get((str(group_id), pose_idx))
            semantic_literal = (
                f"group_pose::{facility_type}::{operation_type}::{pose_idx}"
            )
            mandatory_group_keys[source_id] = str(group_id)
        else:
            raise RuntimeError(f"unsupported target literal kind: {kind}")

        if variable is None:
            raise RuntimeError(f"consumer literal missing for {source_id}")
        var_index = int(variable.Index())
        var_name = str(variable.Name())
        if var_index in mapped_var_indices or var_name in mapped_var_names:
            raise RuntimeError(
                "two source literals alias to one consumer variable; refusing silent strengthening"
            )
        mapped_var_indices.add(var_index)
        mapped_var_names.add(var_name)
        conflict_set[source_id] = pose_idx
        resolved.append(
            {
                "source_instance_id": source_id,
                "source_literal_kind": kind,
                "semantic_literal": semantic_literal,
                "facility_type": facility_type,
                "operation_type": operation_type,
                "pose_idx": pose_idx,
                "pose_id": pose_id,
                "consumer_group_id": group_id,
                "consumer_group_count": len(group_members),
                "consumer_group_members": group_members,
                "consumer_var_name": var_name,
                "consumer_var_index": var_index,
            }
        )

    source_group = mandatory_group_keys.get("refinery_blue_iron_034")
    barrier_group = mandatory_group_keys.get("refinery_blue_iron_033")
    if source_group is None or source_group != barrier_group:
        raise RuntimeError("blue-iron source and barrier literals did not map to one group")
    blue_group = groups[source_group]
    if int(blue_group["count"]) < 2:
        raise RuntimeError("blue-iron group cannot occupy the two distinct certified poses")
    mandatory_source = certificate.get("mandatory_source", {})
    if (
        str(mandatory_source.get("operation_type", "")) != "refinery_blue_iron"
        or int(mandatory_source.get("source_pose_idx", -1)) != 5702
        or mandatory_source.get("all_retained_patterns_force_source_front") is not True
    ):
        raise RuntimeError("certificate does not preserve the group-level source role")

    parent_group_poses: dict[str, set[int]] = {}
    parent_optional_poses: dict[str, set[int]] = {}
    for instance_id, row in parent_solution.items():
        pose_idx = int(row["pose_idx"])
        if bool(row.get("is_mandatory")):
            group_id = delegate._group_id_by_instance.get(str(instance_id))
            if group_id is None:
                raise RuntimeError(f"parent mandatory lacks group: {instance_id}")
            parent_group_poses.setdefault(str(group_id), set()).add(pose_idx)
        else:
            parent_optional_poses.setdefault(str(row["facility_type"]), set()).add(pose_idx)
    parent_selects_all = True
    for row in resolved:
        if row["source_literal_kind"] == "mandatory_group_pose_presence":
            parent_selects_all &= int(row["pose_idx"]) in parent_group_poses.get(
                str(row["consumer_group_id"]), set()
            )
        else:
            parent_selects_all &= int(row["pose_idx"]) in parent_optional_poses.get(
                str(row["facility_type"]), set()
            )
    if not parent_selects_all:
        raise RuntimeError("parent assignment does not select all four semantic occupancies")

    obligations = {
        "T1_GROUP_EQUIVALENCE_CLASS": True,
        "T2_LABEL_PERMUTATION_INVARIANCE": True,
        "T3_POSE_IDENTITY": True,
        "T4_ONE_TO_ONE_LITERAL_MAPPING": len(mapped_var_indices) == 4,
        "T5_SOURCE_ROLE_PRESERVED": True,
        "T7_PARENT_HINT_IS_NOT_A_WITNESS": parent_selects_all,
    }
    if not all(obligations.values()):
        raise RuntimeError(f"lowering transport obligations failed: {obligations}")

    constraints_before = len(master.model.Proto().constraints)
    if not master.add_benders_cut(conflict_set):
        raise RuntimeError("MasterPlacementModel rejected the checked conflict set")
    constraints_after = len(master.model.Proto().constraints)
    if constraints_after - constraints_before != 1:
        raise RuntimeError(
            f"cut constraint delta is {constraints_after - constraints_before}, expected 1"
        )
    # Keep the parent pybind proto wrapper alive while reading a child.  With
    # OR-Tools 9.15/Python 3.13, retaining ``model.Proto().constraints[-1]``
    # from a temporary parent can leave a dangling child wrapper and SIGSEGV on
    # ``has_linear()`` instead of raising a Python exception.
    model_proto = master.model.Proto()
    last_constraint = model_proto.constraints[-1]
    has_linear = getattr(last_constraint, "has_linear", None)
    if callable(has_linear) and not bool(has_linear()):
        raise RuntimeError("attached cut is not linear")
    linear = last_constraint.linear
    linear_vars = [int(value) for value in linear.vars]
    linear_coeffs = [int(value) for value in linear.coeffs]
    linear_domain = [int(value) for value in linear.domain]
    if set(linear_vars) != mapped_var_indices:
        raise RuntimeError(
            f"attached cut variable set drift: {linear_vars} != {sorted(mapped_var_indices)}"
        )
    if len(linear_coeffs) != 4 or any(value != 1 for value in linear_coeffs):
        raise RuntimeError(f"attached cut coefficients drift: {linear_coeffs}")
    if not linear_domain or int(linear_domain[-1]) != 3:
        raise RuntimeError(f"attached cut upper bound drift: {linear_domain}")
    obligations["T6_CONSUMER_FORM"] = True

    return {
        "status": "PASS_CHECKED_INSTANCE_TO_GROUP_LOWERING",
        "source_certificate_sha256": EXPECTED_CERTIFICATE_SHA256,
        "source_candidate_cut_digest": certificate["candidate_cut"]["canonical_digest"],
        "source_logical_form": certificate["candidate_cut"]["logical_form"],
        "consumer_logical_form": "sum(four distinct group/optional pose presences) <= 3",
        "transport_obligations": obligations,
        "resolved_literals": resolved,
        "api_conflict_set": conflict_set,
        "parent_selects_all_four_semantic_literals": parent_selects_all,
        "constraint_count_before": constraints_before,
        "constraint_count_after": constraints_after,
        "constraint_delta": constraints_after - constraints_before,
        "linear_proto": {
            "vars": linear_vars,
            "coeffs": linear_coeffs,
            "domain": linear_domain,
        },
        "hidden_issue_exposed": {
            "kind": "OBJECT_SPACE_TRANSPORT_WAS_IMPLICIT",
            "statement": (
                "The source certificate named symmetric mandatory instances, while "
                "the pose-bool consumer acts on group-pose occupancy. E001 makes the "
                "permutation-invariant transport explicit before consumption."
            ),
        },
    }


def group_pose_projection(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    group_id_by_instance: Mapping[str, str],
) -> dict[str, list[int]]:
    projection: dict[str, set[int]] = {}
    for instance_id, row in solution.items():
        pose_idx = int(row["pose_idx"])
        if bool(row.get("is_mandatory")):
            group_id = group_id_by_instance.get(str(instance_id))
            if group_id is None:
                raise RuntimeError(f"solution mandatory lacks group: {instance_id}")
            key = f"mandatory::{group_id}"
        else:
            key = f"optional::{row.get('facility_type', '')}"
        projection.setdefault(key, set()).add(pose_idx)
    return {key: sorted(values) for key, values in sorted(projection.items())}


def compare_solutions(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    child: Mapping[str, Mapping[str, Any]],
    group_id_by_instance: Mapping[str, str],
) -> dict[str, Any]:
    common = sorted(set(parent) & set(child))
    named_changes = [
        instance_id
        for instance_id in common
        if int(parent[instance_id]["pose_idx"]) != int(child[instance_id]["pose_idx"])
    ]
    parent_projection = group_pose_projection(
        solution=parent,
        group_id_by_instance=group_id_by_instance,
    )
    child_projection = group_pose_projection(
        solution=child,
        group_id_by_instance=group_id_by_instance,
    )
    group_diffs: dict[str, Any] = {}
    symmetric_difference_total = 0
    for key in sorted(set(parent_projection) | set(child_projection)):
        old = set(parent_projection.get(key, []))
        new = set(child_projection.get(key, []))
        removed = sorted(old - new)
        added = sorted(new - old)
        if removed or added:
            group_diffs[key] = {"removed": removed, "added": added}
            symmetric_difference_total += len(removed) + len(added)
    return {
        "named_instance_common_count": len(common),
        "named_instance_pose_churn_count": len(named_changes),
        "named_instance_pose_churn_ids": named_changes,
        "group_pose_projection_parent_digest": canonical_digest(parent_projection),
        "group_pose_projection_child_digest": canonical_digest(child_projection),
        "group_pose_changed_bucket_count": len(group_diffs),
        "group_pose_symmetric_difference_count": symmetric_difference_total,
        "group_pose_differences": group_diffs,
        "interpretation": (
            "Group-pose churn is the representation-faithful measure. Named-instance "
            "churn can include arbitrary permutation of symmetric members during extraction."
        ),
        "second_hidden_issue_exposed": {
            "kind": "NAMED_INSTANCE_CHURN_IS_NOT_REPRESENTATION_INVARIANT",
            "statement": (
                "The historical comparison protocol counted named mandatory pose changes, "
                "but pose-bool extraction assigns symmetric names after solving. E001 "
                "reports group-pose set changes separately."
            ),
        },
    }


def solution_layout(solution: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    placements = sorted(
        [dict(row) for row in solution.values()],
        key=lambda row: (
            not bool(row.get("is_mandatory")),
            str(row.get("facility_type", "")),
            str(row.get("operation_type", "")),
            str(row.get("instance_id", "")),
        ),
    )
    return {
        "schema": "zmd_e001_replacement_layout_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ghost_rect": None,
        "mandatory_placement_count": sum(
            bool(row.get("is_mandatory")) for row in placements
        ),
        "total_selected_placement_count": len(placements),
        "power_coverage_in_master": True,
        "binding_routing_terminal_validator_run": False,
        "placements": placements,
    }


def build_binding_stage(
    *,
    stage_name: str,
    stack: Mapping[str, Any],
    inputs: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
    routing_bundle: Mapping[str, Any],
    duplicate_keys: bool,
    component_support: bool,
) -> tuple[Any, dict[str, Any]]:
    from interface_compiler import compile_interface_constraints

    plan = inputs["plan"]
    io = inputs["generic"]
    build_started = time.monotonic()
    model = stack["PortBindingModel"](
        placement_solution=solution,
        facility_pools=inputs["pools"],
        instances=inputs["instances"],
        project_root=HISTORY_ROOT,
        required_generic_outputs=io.get("required_generic_outputs", {}),
        required_generic_inputs=io.get("required_generic_inputs", {}),
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
        utility_operation_by_template=plan["utility_operation_by_template"],
        canonical_rules_payload=inputs["rules"],
        routing_context=routing_bundle["routing_context"],
    )
    model.build()
    compile_stats = compile_interface_constraints(
        binding_model=model,
        routing_context=routing_bundle["routing_context"],
        required_generic_inputs=io.get("required_generic_inputs", {}),
        enforce_duplicate_keys=duplicate_keys,
        enforce_component_support=component_support,
    )
    build_seconds = time.monotonic() - build_started
    solve_started = time.monotonic()
    status = model.solve(time_limit_seconds=BINDING_CAP_SECONDS)
    solve_seconds = time.monotonic() - solve_started
    summary = model.extract_conflict_summary()
    result: dict[str, Any] = {
        "stage": stage_name,
        "status": status,
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "time_limit_seconds": BINDING_CAP_SECONDS,
        "compile_stats": compile_stats,
        "conflict_summary": json_safe(summary),
        "routing_aware_certificates": json_safe(
            model.extract_routing_aware_certificates()
        ),
    }
    if status == "FEASIBLE":
        selection = model.extract_selection()
        ports = model.extract_port_specs()
        result.update(
            {
                "selection": json_safe(selection),
                "selection_digest": canonical_digest(selection),
                "port_count": len(ports),
                "port_specs_digest": canonical_digest(ports),
            }
        )
    return model, result


def strict_non_ghost_terminal_validation(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    port_specs: Sequence[Mapping[str, Any]],
    routes: Sequence[Mapping[str, Any]],
    occupied_cells: set[tuple[int, int]],
) -> dict[str, Any]:
    import src.search.exact_campaign as exact_campaign
    from src.search.pr2_l0_fixed_witness_core import (
        _strict_normalized_port_specs,
        _validated_terminal_fixed_witness_port_carrier,
        canonical_digest as strict_digest,
    )

    normalized_port_specs = _strict_normalized_port_specs(list(port_specs))
    port_specs_digest = strict_digest(normalized_port_specs)
    _validated_terminal_fixed_witness_port_carrier(
        details={
            "port_specs": normalized_port_specs,
            "port_count": len(normalized_port_specs),
        },
        port_specs_digest=port_specs_digest,
        known_instance_ids=set(solution),
    )
    route_cells = {
        (int(route["x"]), int(route["y"]))
        for route in routes
        if isinstance(route, Mapping)
    }
    body_overlaps = sorted(route_cells & occupied_cells)
    if body_overlaps:
        return {
            "status": "FAIL",
            "reason": "e001_route_cell_overlaps_facility_body",
            "route_body_overlaps": [list(cell) for cell in body_overlaps],
        }

    placeholder = {"w": 1, "h": 1, "anchor_x": 0, "anchor_y": 0}
    original_count = exact_campaign._occupied_count_in_rect
    original_exists = exact_campaign._empty_rect_exists
    original_best = exact_campaign._best_empty_rect_objective
    try:
        exact_campaign._occupied_count_in_rect = lambda **_kwargs: 0
        exact_campaign._empty_rect_exists = lambda **_kwargs: True
        exact_campaign._best_empty_rect_objective = lambda **_kwargs: (1, 1)
        reason = exact_campaign._validate_terminal_solution_against_project(
            final_result={
                "placement_solution": dict(solution),
                "ghost_rect": placeholder,
            },
            project_root=HISTORY_ROOT,
            grid_dimensions=(70, 70),
            min_side_admissibility=None,
        )
    finally:
        exact_campaign._occupied_count_in_rect = original_count
        exact_campaign._empty_rect_exists = original_exists
        exact_campaign._best_empty_rect_objective = original_best

    return {
        "status": "PASS" if reason is None else "FAIL",
        "reason": reason,
        "production_validator": (
            "src.search.exact_campaign._validate_terminal_solution_against_project"
        ),
        "ghost_clause_adapter": {
            "ghost_rect": None,
            "placeholder": placeholder,
            "meaning": "Only empty-rectangle clauses are made vacuous; no empty-rectangle claim is made."
        },
        "route_body_overlap_count": 0,
        "normalized_port_specs_digest": port_specs_digest,
        "route_witness_digest": strict_digest(list(routes)),
        "route_record_count": len(routes),
        "unique_route_cell_count": len(route_cells),
    }


def run_interface_ladder(
    *,
    run_dir: Path,
    stack: Mapping[str, Any],
    inputs: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    from interface_compiler import build_routing_context
    from src.search.pr2_l0_fixed_witness_core import (
        _normalize_port_specs,
        _routing_build_rejection,
    )

    routing_bundle = build_routing_context(
        solution=solution,
        facility_pools=inputs["pools"],
    )
    stages: list[dict[str, Any]] = []
    stage_specs = [
        ("STATIC_PORT_DOMAIN", False, False),
        ("TERMINAL_UNIQUENESS", True, False),
        ("COMPONENT_SUPPORT", True, True),
    ]
    surviving_model: Any | None = None
    for stage_name, duplicate_keys, component_support in stage_specs:
        emit(run_dir, "BINDING_STAGE_START", stage=stage_name)
        model, stage_result = build_binding_stage(
            stage_name=stage_name,
            stack=stack,
            inputs=inputs,
            solution=solution,
            routing_bundle=routing_bundle,
            duplicate_keys=duplicate_keys,
            component_support=component_support,
        )
        stages.append(stage_result)
        emit(
            run_dir,
            "BINDING_STAGE_COMPLETE",
            stage=stage_name,
            status=stage_result["status"],
            build_seconds=stage_result["build_seconds"],
            solve_seconds=stage_result["solve_seconds"],
        )
        if stage_result["status"] != "FEASIBLE":
            if stage_name == "STATIC_PORT_DOMAIN":
                verdict = "PORT_DOMAIN_INFEASIBLE" if stage_result["status"] == "INFEASIBLE" else "PORT_DOMAIN_UNKNOWN"
            elif stage_name == "TERMINAL_UNIQUENESS":
                verdict = "TERMINAL_UNIQUENESS_INFEASIBLE" if stage_result["status"] == "INFEASIBLE" else "TERMINAL_UNIQUENESS_UNKNOWN"
            else:
                verdict = "COMPONENT_SUPPORT_INFEASIBLE" if stage_result["status"] == "INFEASIBLE" else "COMPONENT_SUPPORT_UNKNOWN"
            return {
                "verdict": verdict,
                "fixed_occupancy": routing_bundle["summary"],
                "binding_stages": stages,
                "exact_routing_reached": False,
                "strict_validator_reached": False,
            }
        if stage_name == "COMPONENT_SUPPORT":
            surviving_model = model
        else:
            del model
            gc.collect()

    if surviving_model is None:
        raise RuntimeError("component-support stage did not retain a feasible model")
    selection = surviving_model.extract_selection()
    port_specs = surviving_model.extract_port_specs()
    normalized_ports = _normalize_port_specs(port_specs)
    precheck_started = time.monotonic()
    precheck = stack["run_exact_routing_precheck"](
        placement_core=routing_bundle["placement_core"],
        port_specs=port_specs,
        occupied_owner_by_cell=routing_bundle["occupied_owner_by_cell"],
    )
    precheck_seconds = time.monotonic() - precheck_started
    precheck_public = {
        key: value for key, value in precheck.items() if key != "_analysis"
    }
    if precheck.get("status") != "feasible":
        return {
            "verdict": "INTERFACE_COMPILER_PRECHECK_MISMATCH",
            "fixed_occupancy": routing_bundle["summary"],
            "binding_stages": stages,
            "surviving_selection_digest": canonical_digest(selection),
            "port_specs_digest": canonical_digest(normalized_ports),
            "ordinary_routing_precheck": json_safe(precheck_public),
            "ordinary_routing_precheck_seconds": precheck_seconds,
            "exact_routing_reached": False,
            "strict_validator_reached": False,
            "hidden_issue": (
                "The compiled interface admitted a binding rejected by the ordinary "
                "routing precheck; the repartitioned rule set is incomplete or mismatched."
            ),
        }

    emit(run_dir, "EXACT_ROUTING_BUILD_START", port_count=len(port_specs))
    routing_build_started = time.monotonic()
    routing_model = stack["RoutingSubproblem"].from_placement_core(
        routing_bundle["placement_core"],
        port_specs,
        sorted({str(port["commodity"]) for port in port_specs}),
        domain_analysis=precheck.get("_analysis"),
    )
    routing_model.build()
    routing_build_seconds = time.monotonic() - routing_build_started
    build_rejection = _routing_build_rejection(routing_model.build_stats)
    if build_rejection is not None:
        return {
            "verdict": "EXACT_ROUTING_BUILD_REJECTED",
            "fixed_occupancy": routing_bundle["summary"],
            "binding_stages": stages,
            "ordinary_routing_precheck": json_safe(precheck_public),
            "routing_build_seconds": routing_build_seconds,
            "routing_build_rejection": build_rejection,
            "routing_build_stats": json_safe(routing_model.build_stats),
            "exact_routing_reached": True,
            "strict_validator_reached": False,
        }

    emit(run_dir, "EXACT_ROUTING_SOLVE_START", cap_seconds=ROUTING_CAP_SECONDS)
    routing_solve_started = time.monotonic()
    routing_status = routing_model.solve(time_limit=ROUTING_CAP_SECONDS)
    routing_solve_seconds = time.monotonic() - routing_solve_started
    emit(
        run_dir,
        "EXACT_ROUTING_SOLVE_COMPLETE",
        status=routing_status,
        solve_seconds=routing_solve_seconds,
    )
    result: dict[str, Any] = {
        "verdict": "EXACT_ROUTING_REACHED",
        "fixed_occupancy": routing_bundle["summary"],
        "binding_stages": stages,
        "surviving_selection": json_safe(selection),
        "surviving_selection_digest": canonical_digest(selection),
        "port_specs": json_safe(normalized_ports),
        "port_specs_digest": canonical_digest(normalized_ports),
        "ordinary_routing_precheck": json_safe(precheck_public),
        "ordinary_routing_precheck_seconds": precheck_seconds,
        "exact_routing_reached": True,
        "routing_build_seconds": routing_build_seconds,
        "routing_build_stats": json_safe(routing_model.build_stats),
        "routing_status": routing_status,
        "routing_solve_seconds": routing_solve_seconds,
        "routing_cap_seconds": ROUTING_CAP_SECONDS,
        "strict_validator_reached": False,
    }
    if routing_status != "FEASIBLE":
        result["verdict"] = (
            "EXACT_ROUTING_INFEASIBLE"
            if routing_status == "INFEASIBLE"
            else "EXACT_ROUTING_UNKNOWN"
        )
        return result

    routes = routing_model.extract_routes()
    validator_started = time.monotonic()
    validator = strict_non_ghost_terminal_validation(
        solution=solution,
        port_specs=port_specs,
        routes=routes,
        occupied_cells=routing_bundle["occupied_cells"],
    )
    validator_seconds = time.monotonic() - validator_started
    result.update(
        {
            "routes": json_safe(routes),
            "route_witness_digest": canonical_digest(routes),
            "route_record_count": len(routes),
            "strict_validator_reached": True,
            "strict_validator_seconds": validator_seconds,
            "strict_validator": validator,
            "verdict": (
                "ZERO_CONDITION_ROUTING_COMPLETE_RESEARCH_WITNESS"
                if validator["status"] == "PASS"
                else "STRICT_VALIDATOR_REJECTED_ROUTING_WITNESS"
            ),
        }
    )
    return result


def run_worker(run_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    environment = verify_worker_environment()
    identity = verify_identity(require_clean=True)
    emit(run_dir, "IDENTITY_PASS", research_head=identity["research_head"])
    stack = import_stack()
    inputs = load_model_inputs(stack)
    parent_solution = load_parent_solution()

    emit(run_dir, "MASTER_BUILD_START")
    build_started = time.monotonic()
    master = construct_master(stack, inputs)
    master.build()
    build_seconds = time.monotonic() - build_started
    delegate = master._coordinate_delegate
    lowering = audit_and_attach_lowering(
        master=master,
        inputs=inputs,
        parent_solution=parent_solution,
    )
    emit(
        run_dir,
        "LOWERING_PASS",
        build_seconds=build_seconds,
        constraint_delta=lowering["constraint_delta"],
    )

    parent_hint = {
        instance_id: int(row["pose_idx"])
        for instance_id, row in parent_solution.items()
    }
    solver_log_path = run_dir / "MASTER_SOLVER.log"
    with solver_log_path.open("xb", buffering=0) as raw_log:
        def log_callback(line: str) -> None:
            encoded = line.encode("utf-8", errors="replace")
            raw_log.write(encoded)
            if not encoded.endswith(b"\n"):
                raw_log.write(b"\n")

        emit(run_dir, "MASTER_SOLVE_START", cap_seconds=MASTER_CAP_SECONDS)
        solve_started = time.monotonic()
        status_code = master.solve(
            time_limit_seconds=MASTER_CAP_SECONDS,
            solution_hint=parent_hint,
            known_feasible_hint=False,
            hint_inactive_residual_optionals=False,
            diagnostic_log_callback=log_callback,
        )
        solve_seconds = time.monotonic() - solve_started
    cp_model = stack["cp_model"]
    status = master._solver.StatusName(status_code) if master._solver else "NO_SOLVER"
    emit(run_dir, "MASTER_SOLVE_COMPLETE", status=status, solve_seconds=solve_seconds)

    master_summary: dict[str, Any] = {
        "status": status,
        "status_code": int(status_code),
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "cap_seconds": MASTER_CAP_SECONDS,
        "raw_variable_count": len(master.model.Proto().variables),
        "raw_constraint_count": len(master.model.Proto().constraints),
        "last_solve": json_safe(master.build_stats.get("last_solve", {})),
        "solver_log_sha256": sha256_file(solver_log_path),
        "lowering": lowering,
    }
    base_result: dict[str, Any] = {
        "schema": "zmd_zero_condition_e001_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "identity": identity,
        "environment": environment,
        "master": master_summary,
        "total_elapsed_seconds": time.monotonic() - started,
    }

    if status_code not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        if status == "INFEASIBLE":
            base_result["verdict"] = "MASTER_INFEASIBLE_RESEARCH_ONLY"
        elif status == "UNKNOWN":
            base_result["verdict"] = "MASTER_UNKNOWN"
        else:
            base_result["verdict"] = "MASTER_EXECUTION_FAILURE"
        return base_result

    resolved_by_source = {
        row["source_instance_id"]: row for row in lowering["resolved_literals"]
    }
    selected_cut_literals: dict[str, int] = {}
    for source_id, row in resolved_by_source.items():
        var_index = int(row["consumer_var_index"])
        variable = master.model.GetBoolVarFromProtoIndex(var_index)
        selected_cut_literals[source_id] = int(master._solver.Value(variable))
    if sum(selected_cut_literals.values()) > 3:
        raise RuntimeError(f"extracted replacement violates attached cut: {selected_cut_literals}")

    solution = master.extract_solution()
    mandatory_count = sum(bool(row.get("is_mandatory")) for row in solution.values())
    if mandatory_count != EXPECTED_MANDATORY_COUNT:
        raise RuntimeError(f"replacement mandatory count drift: {mandatory_count}")
    comparison = compare_solutions(
        parent=parent_solution,
        child=solution,
        group_id_by_instance=delegate._group_id_by_instance,
    )
    assignment_payload = {
        "schema": "zmd_e001_replacement_assignment_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": status,
        "scope": "zero_condition_placement_plus_power_with_one_research_cut",
        "solution": json_safe(solution),
    }
    layout_payload = solution_layout(solution)
    assignment_path = run_dir / "REPLACEMENT_ASSIGNMENT.json"
    layout_path = run_dir / "REPLACEMENT_LAYOUT.json"
    dump_json_exclusive(assignment_path, assignment_payload)
    dump_json_exclusive(layout_path, layout_payload)
    base_result.update(
        {
            "verdict": "MASTER_REPLACEMENT",
            "master_replacement": {
                "status": status,
                "selected_cut_literals": selected_cut_literals,
                "selected_cut_literal_count": sum(selected_cut_literals.values()),
                "mandatory_count": mandatory_count,
                "total_selected_placement_count": len(solution),
                "assignment_path": str(assignment_path.relative_to(ROOT)),
                "assignment_sha256": sha256_file(assignment_path),
                "layout_path": str(layout_path.relative_to(ROOT)),
                "layout_sha256": sha256_file(layout_path),
                "comparison_to_parent": comparison,
            },
        }
    )

    del master
    gc.collect()
    emit(run_dir, "INTERFACE_LADDER_START")
    interface = run_interface_ladder(
        run_dir=run_dir,
        stack=stack,
        inputs=inputs,
        solution=solution,
    )
    base_result["interface"] = interface
    base_result["verdict"] = interface["verdict"]
    base_result["total_elapsed_seconds"] = time.monotonic() - started
    return base_result


def audit_only(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    identity = verify_identity(require_clean=True)
    stack = import_stack()
    inputs = load_model_inputs(stack)
    parent = load_parent_solution()
    started = time.monotonic()
    master = construct_master(stack, inputs)
    master.build()
    lowering = audit_and_attach_lowering(
        master=master,
        inputs=inputs,
        parent_solution=parent,
    )
    payload = {
        "schema": "zmd_e001_lowering_audit_v1",
        "created_at_utc": utc_now(),
        "status": "PASS",
        "authority": "research_only_noncertified",
        "identity": identity,
        "lowering": lowering,
        "model": {
            "representation": getattr(
                master._coordinate_delegate,
                "master_representation",
                None,
            ),
            "raw_variable_count": len(master.model.Proto().variables),
            "raw_constraint_count_after_cut": len(master.model.Proto().constraints),
        },
        "elapsed_seconds": time.monotonic() - started,
        "solve_run": False,
        "ledger_effect": "none",
    }
    dump_json_exclusive(output_dir / "AUDIT.json", payload)
    del master
    gc.collect()
    return payload


def clean_worker_environment() -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("EXACT_"):
            env.pop(key, None)
    env.update(EXPECTED_ENV)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def launch(run_name: str) -> dict[str, Any]:
    if not run_name or "/" in run_name or run_name in {".", ".."}:
        raise ValueError("run name must be one safe path component")
    verify_identity(require_clean=True)
    run_dir = LOCAL_ROOT / run_name
    run_dir.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "worker",
        "--run-dir",
        str(run_dir),
    ]
    log_path = run_dir / "WORKER.log"
    with log_path.open("xb") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=clean_worker_environment(),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    receipt = {
        "schema": "zmd_e001_launch_v1",
        "created_at_utc": utc_now(),
        "run_name": run_name,
        "run_dir": str(run_dir),
        "pid": int(process.pid),
        "command": command,
        "worker_log": str(log_path),
        "environment": EXPECTED_ENV,
        "research_head": git_output("rev-parse", "HEAD"),
    }
    dump_json_exclusive(run_dir / "LAUNCH.json", receipt)
    return receipt


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def status(run_name: str) -> dict[str, Any]:
    run_dir = LOCAL_ROOT / run_name
    launch_path = run_dir / "LAUNCH.json"
    if not launch_path.is_file():
        return {"status": "NOT_FOUND", "run_name": run_name}
    launch_receipt = load_json(launch_path)
    result_path = run_dir / "RESULT.json"
    failure_path = run_dir / "FAILURE.json"
    progress_path = run_dir / "PROGRESS.json"
    pid = int(launch_receipt["pid"])
    if result_path.is_file():
        result = load_json(result_path)
        return {
            "status": "COMPLETE",
            "run_name": run_name,
            "pid": pid,
            "verdict": result.get("verdict"),
            "result_sha256": sha256_file(result_path),
            "progress": load_json(progress_path) if progress_path.is_file() else None,
        }
    if failure_path.is_file():
        failure = load_json(failure_path)
        return {
            "status": "FAILED",
            "run_name": run_name,
            "pid": pid,
            "error": failure.get("error"),
            "detail": failure.get("detail"),
            "failure_sha256": sha256_file(failure_path),
        }
    return {
        "status": "RUNNING" if process_alive(pid) else "EXITED_WITHOUT_RECEIPT",
        "run_name": run_name,
        "pid": pid,
        "progress": load_json(progress_path) if progress_path.is_file() else None,
    }


def worker_entry(run_dir: Path) -> int:
    result_path = run_dir / "RESULT.json"
    failure_path = run_dir / "FAILURE.json"
    try:
        if result_path.exists() or failure_path.exists():
            raise FileExistsError("worker output already exists")
        result = run_worker(run_dir)
        dump_json_exclusive(result_path, result)
        emit(run_dir, "WORKER_COMPLETE", verdict=result.get("verdict"))
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_e001_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_json_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--output-name", default="audit-001")

    launch_parser = subparsers.add_parser("launch")
    launch_parser.add_argument("--run-name", default="run-001")

    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--run-dir", type=Path, required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--run-name", default="run-001")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "audit":
        payload = audit_only(LOCAL_ROOT / str(args.output_name))
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "lowering_status": payload["lowering"]["status"],
                    "audit_path": str(
                        (LOCAL_ROOT / str(args.output_name) / "AUDIT.json").relative_to(ROOT)
                    ),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "launch":
        print(json.dumps(launch(str(args.run_name)), sort_keys=True))
        return 0
    if args.command == "worker":
        return worker_entry(Path(args.run_dir).resolve())
    if args.command == "status":
        print(json.dumps(status(str(args.run_name)), ensure_ascii=False, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
