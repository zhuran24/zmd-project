from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from ortools.sat import cp_model_pb2
from ortools.sat.python import cp_model
import pytest

from src.models.master_model import MasterPlacementModel


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724"


def _load(name: str, module_name: str | None = None):
    path = RESEARCH / f"{name}.py"
    spec = importlib.util.spec_from_file_location(module_name or name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE_CONTRACT = _load("baseline_admission_v1")
REPLAY = _load("cut_free_incumbent_replay_v1")
REBUILD = _load("baseline_rebuild_v1")


@pytest.fixture(autouse=True)
def _coordinate_master_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep focused replay tests on the production coordinate backend."""

    for variable in (
        "EXACT_USE_POSE_BOOL_MASTER",
        "EXACT_POWER_PLACEMENT_SUBPROBLEM",
        "EXACT_LAZY_POWER_COMPLETION",
    ):
        monkeypatch.delenv(variable, raising=False)


def _write(path: Path, raw: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _coordinate_master_replay_fixture(
    *,
    protocol_required_count: int = 0,
) -> tuple[
    cp_model_pb2.CpModelProto,
    dict[str, dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
    MasterPlacementModel,
]:
    """Build the production coordinate representation without using its binding report."""

    grid_width = 4
    grid_height = 3
    mandatory = [
        {
            "instance_id": "miner_002",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]

    def single_cell_pose(pose_id: str, x_val: int, y_val: int) -> dict[str, object]:
        return {
            "pose_id": pose_id,
            "anchor": {"x": x_val, "y": y_val},
            "occupied_cells": [[x_val, y_val]],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }

    coverage = [
        [x_val, y_val]
        for x_val in range(grid_width)
        for y_val in range(grid_height)
    ]

    def pole_pose(pose_id: str, x_val: int, y_val: int) -> dict[str, object]:
        return {
            "pose_id": pose_id,
            "anchor": {"x": x_val, "y": y_val},
            "occupied_cells": [
                [x_val + dx, y_val + dy]
                for dx in range(2)
                for dy in range(2)
            ],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": coverage,
        }

    pools = {
        "miner": [
            # Deliberately reverse pose-index and coordinate order.  Production
            # slots are anonymous and ordered by x/y/mode, not instance id.
            single_cell_pose("miner_top", 0, 2),
            single_cell_pose("miner_bottom", 0, 0),
            single_cell_pose("miner_right_bottom", 3, 0),
            single_cell_pose("miner_right_top", 3, 2),
        ],
        "protocol_storage_box": [
            {
                **single_cell_pose("box_0", 1, 2),
                "pose_params": {"orientation": "rotated"},
            },
            single_cell_pose("box_1", 2, 2),
        ],
        "power_pole": [
            pole_pose(f"pole_{x_val}_{y_val}", x_val, y_val)
            for x_val in range(grid_width - 1)
            for y_val in range(grid_height - 1)
        ],
    }
    rules = {
        "globals": {"grid": {"width": grid_width, "height": grid_height}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
            },
            "power_pole": {
                "dimensions": {"w": 2, "h": 2},
                "needs_power": False,
                "power_coverage_radius": 5,
            },
        },
    }
    core = MasterPlacementModel.build_exact_core(
        mandatory,
        pools,
        rules,
        skip_power_coverage=True,
        exact_required_pose_optional_counts={
            "protocol_storage_box": protocol_required_count,
            "power_pole": 1,
        },
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        },
    )
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    master.build()
    proto = REBUILD._portable_cp_model_proto(master.model.Proto())
    incumbent = {
        "miner_001": {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "pose_idx": 0,
            "pose_id": "miner_top",
            "anchor": {"x": 0, "y": 2},
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        },
        "miner_002": {
            "instance_id": "miner_002",
            "facility_type": "miner",
            "operation_type": "mining",
            "pose_idx": 1,
            "pose_id": "miner_bottom",
            "anchor": {"x": 0, "y": 0},
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        },
        "pose_optional::protocol_storage_box::box_0": {
            "instance_id": "pose_optional::protocol_storage_box::box_0",
            "facility_type": "protocol_storage_box",
            "operation_type": "box_sink",
            "pose_idx": 0,
            "pose_id": "box_0",
            "anchor": {"x": 1, "y": 2},
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        },
        "pose_optional::power_pole::pole_2_1": {
            "instance_id": "pose_optional::power_pole::pole_2_1",
            "facility_type": "power_pole",
            "operation_type": "power_supply",
            "pose_idx": 5,
            "pose_id": "pole_2_1",
            "anchor": {"x": 2, "y": 1},
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        },
        "ghost_pick": {
            "instance_id": "ghost_pick",
            "facility_type": "ghost_rect",
            "pose_idx": 1,
            "pose_id": "ghost_anchor::0,1",
            "anchor": {"x": 0, "y": 1},
            "is_mandatory": False,
            "bound_type": "ghost_rect",
            "solve_mode": "certified_exact",
        },
    }
    return proto, incumbent, mandatory, {"facility_pools": pools}, master


def test_fixed_assignment_replay_consumes_real_coordinate_master_representation() -> None:
    """Exercise the production x/y/mode, C1-pole, and ghost variable surfaces."""

    proto, incumbent, mandatory, candidate_placements, _master = _coordinate_master_replay_fixture()
    assert _master.build_stats["master_representation"] == "coordinate_exact_v2"
    assert _master.build_stats["exact_core_reuse"]["used"] is True
    names = [variable.name for variable in proto.variables]
    assert sum(name.startswith("x__") for name in names) == 4
    assert sum(name.startswith("y__") for name in names) == 4
    assert sum(name.startswith("mode__") for name in names) == 4
    assert sum(name.startswith("active__") for name in names) == 2
    assert any("__residual_optional::protocol_storage_box::slot::" in name for name in names)
    assert any(name.startswith("signature__") for name in names)
    assert sum(name.startswith("region__") for name in names) == 4
    assert sum(name.startswith("c1pole__") for name in names) == 6
    assert sum(name.startswith("ghost__") for name in names) == 12
    assert not any(name.startswith(("z__", "opt__")) for name in names)

    plan = REPLAY._placement_fix_plan(
        proto,
        incumbent=incumbent,
        mandatory_instances=mandatory,
        candidate_placements=candidate_placements,
    )
    mapped_names = {
        instance_id: tuple(proto.variables[index].name for index in indices)
        for instance_id, indices in plan.assignment_variables.items()
    }
    assert "x__group::miner::mining::0::slot::0" in mapped_names["miner_002"]
    assert "x__group::miner::mining::0::slot::1" in mapped_names["miner_001"]
    assert mapped_names["pose_optional::power_pole::pole_2_1"] == ("c1pole__5",)
    assert mapped_names["ghost_pick"] == ("ghost__0_1_1_1",)
    box_mode_index = next(
        index
        for index in plan.assignment_variables["pose_optional::protocol_storage_box::box_0"]
        if proto.variables[index].name.startswith("mode__")
    )
    assert list(proto.variables[box_mode_index].domain) == [0, 1]
    assert plan.values[box_mode_index] == 1
    active_values = {
        proto.variables[index].name: value
        for index, value in plan.values.items()
        if proto.variables[index].name.startswith("active__")
    }
    assert active_values == {
        "active__residual_optional::protocol_storage_box::slot::0": 1,
        "active__residual_optional::protocol_storage_box::slot::1": 0,
    }
    c1_values = {
        proto.variables[index].name: value
        for index, value in plan.values.items()
        if proto.variables[index].name.startswith("c1pole__")
    }
    assert c1_values == {f"c1pole__{pose_idx}": int(pose_idx == 5) for pose_idx in range(6)}
    ghost_values = {
        proto.variables[index].name: value
        for index, value in plan.values.items()
        if proto.variables[index].name.startswith("ghost__")
    }
    assert len(ghost_values) == 12
    assert sum(ghost_values.values()) == ghost_values["ghost__0_1_1_1"] == 1
    assert len(plan.assignment_variables) == len(incumbent) == 5

    result = REPLAY.replay_fixed_assignment(
        proto.SerializeToString(deterministic=True),
        incumbent=incumbent,
        mandatory_instances=mandatory,
        candidate_placements=candidate_placements,
        max_time_seconds=2.0,
    )

    assert result["status"] == "PASS"
    assert result["solver_status"] == "OPTIMAL"
    assert result["fixed_assignment_count"] == len(incumbent) == 5


def test_fixed_assignment_replay_maps_required_coordinate_optional_slot() -> None:
    proto, incumbent, mandatory, candidate_placements, _master = _coordinate_master_replay_fixture(
        protocol_required_count=1
    )
    names = [variable.name for variable in proto.variables]
    assert any(name.startswith("x__required_optional::protocol_storage_box::slot::") for name in names)
    assert not any(name.startswith("active__") for name in names)

    result = REPLAY.replay_fixed_assignment(
        proto.SerializeToString(deterministic=True),
        incumbent=incumbent,
        mandatory_instances=mandatory,
        candidate_placements=candidate_placements,
        max_time_seconds=2.0,
    )

    assert result["status"] == "PASS"
    assert result["fixed_assignment_count"] == len(incumbent) == 5


@pytest.mark.parametrize(
    ("surface", "protocol_required_count"),
    [
        ("mandatory", 0),
        ("residual_optional", 0),
        ("required_optional", 1),
        ("c1_power_pole", 0),
        ("ghost", 0),
    ],
)
def test_fixed_assignment_replay_constrains_each_production_surface(
    surface: str,
    protocol_required_count: int,
) -> None:
    proto, incumbent, mandatory, candidate, _master = _coordinate_master_replay_fixture(
        protocol_required_count=protocol_required_count
    )
    conflicting = copy.deepcopy(incumbent)
    if surface == "mandatory":
        conflicting["miner_002"].update(
            {
                "pose_idx": 3,
                "pose_id": "miner_right_top",
                "anchor": {"x": 3, "y": 2},
            }
        )
    elif surface in {"residual_optional", "required_optional"}:
        assignment = conflicting.pop("pose_optional::protocol_storage_box::box_0")
        assignment.update(
            {
                "instance_id": "pose_optional::protocol_storage_box::box_1",
                "pose_idx": 1,
                "pose_id": "box_1",
                "anchor": {"x": 2, "y": 2},
            }
        )
        conflicting[str(assignment["instance_id"])] = assignment
    elif surface == "c1_power_pole":
        assignment = conflicting.pop("pose_optional::power_pole::pole_2_1")
        assignment.update(
            {
                "instance_id": "pose_optional::power_pole::pole_0_0",
                "pose_idx": 0,
                "pose_id": "pole_0_0",
                "anchor": {"x": 0, "y": 0},
            }
        )
        conflicting[str(assignment["instance_id"])] = assignment
    else:
        conflicting["ghost_pick"].update(
            {
                "pose_idx": 0,
                "pose_id": "ghost_anchor::0,0",
                "anchor": {"x": 0, "y": 0},
            }
        )

    with pytest.raises(REPLAY.ReplayError, match="fixed assignment was not feasible"):
        REPLAY.replay_fixed_assignment(
            proto.SerializeToString(deterministic=True),
            incumbent=conflicting,
            mandatory_instances=mandatory,
            candidate_placements=candidate,
            max_time_seconds=2.0,
        )


def _ghost_replay_fixture(tmp_path: Path) -> dict[str, Any]:
    candidate: dict[str, object] = {"facility_pools": {}}
    mandatory: list[object] = []
    incumbent = {
        "ghost_pick": {
            "anchor": {"x": 0, "y": 0},
            "bound_type": "ghost_rect",
            "facility_type": "ghost_rect",
            "instance_id": "ghost_pick",
            "is_mandatory": False,
            "pose_idx": 0,
            "pose_id": "ghost_anchor::0,0",
            "solve_mode": "certified_exact",
        }
    }
    checkout_inputs = {
        "candidate_placements": _write(
            tmp_path / "data/preprocessed/candidate_placements.json",
            BASELINE_CONTRACT.canonical_json(candidate),
        ),
        "canonical_rules": _write(
            tmp_path / "rules/canonical_rules.json",
            BASELINE_CONTRACT.canonical_json({}),
        ),
        "mandatory_instances": _write(
            tmp_path / "data/preprocessed/mandatory_exact_instances.json",
            BASELINE_CONTRACT.canonical_json(mandatory),
        ),
    }
    _git(tmp_path, "init")
    _git(tmp_path, "add", "--", "data", "rules")
    _git(
        tmp_path,
        "-c",
        "user.name=AB16 Test",
        "-c",
        "user.email=ab16@example.invalid",
        "commit",
        "-m",
        "fixture checkout",
    )
    repository_head = _git(tmp_path, "rev-parse", "HEAD")
    repository_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}")

    campaign_dir = tmp_path / "run-ab16-fixture"
    package_dir = campaign_dir / "campaign-authority/package"
    package_inputs = {
        role: _write(
            package_dir / "payload" / f"input.{role}.json",
            Path(str(identity["path"])).read_bytes(),
        )
        for role, identity in checkout_inputs.items()
    }
    manifest_identity = _write(package_dir / "package-manifest.json", b"fixture package manifest\n")
    seal_identity = _write(package_dir / "SHA256SUMS", b"fixture package seal\n")
    package = {
        "manifest_identity": manifest_identity,
        "package_id": seal_identity["sha256"],
        "seal_identity": seal_identity,
    }
    git_path = shutil.which("git")
    assert git_path is not None
    git_identity = _identity(Path(git_path))
    campaign_root = {
        "authority_tools": {"git": git_identity},
        "package": {**package, "package_dir": str(package_dir)},
        "repository_head": repository_head,
        "strict_inputs": package_inputs,
    }
    campaign_root_identity = _write(
        campaign_dir / "campaign-root.json",
        BASELINE_CONTRACT.canonical_json(campaign_root),
    )
    campaign_provenance = {
        "authority_scope": BASELINE_CONTRACT.CAMPAIGN_PROVENANCE_AUTHORITY_SCOPE,
        "campaign_root_identity": campaign_root_identity,
        "git_identity": git_identity,
        "import_mode": BASELINE_CONTRACT.CHECKOUT_IMPORT_MODE,
        "input_identities": checkout_inputs,
        "package": package,
        "repository_head": repository_head,
        "repository_root": str(tmp_path.resolve()),
        "repository_tree": repository_tree,
        "schema_version": BASELINE_CONTRACT.CAMPAIGN_PROVENANCE_SCHEMA,
    }
    campaign_provenance_path = campaign_dir / "prospective-ab16/baseline/campaign-provenance.json"
    _write(
        campaign_provenance_path,
        BASELINE_CONTRACT.canonical_json(campaign_provenance),
    )

    model = cp_model.CpModel()
    ghost = model.new_bool_var("ghost__0_0_6_6")
    model.add(ghost == 1)
    model_path = tmp_path / "baseline/model.pb"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    assert model.export_to_file(str(model_path))
    model_raw = model_path.read_bytes()
    model_proto = cp_model_pb2.CpModelProto()
    model_proto.ParseFromString(model_raw)
    model_identity = _identity(model_path)
    incumbent_identity = _write(
        tmp_path / "baseline/incumbent.json",
        BASELINE_CONTRACT.canonical_json(incumbent),
    )
    historical_model_text_sha256 = BASELINE_CONTRACT.historical_model_text_sha256(model_proto)
    expectation = BASELINE_CONTRACT.BaselineExpectation(
        profile="tiny-ghost-v1",
        legacy_size_bytes=0,
        legacy_sha256="0" * 64,
        historical_model_text_sha256=historical_model_text_sha256,
        model_variable_count=1,
        model_constraint_count=1,
        incumbent_sha256=BASELINE_CONTRACT.semantic_digest(incumbent),
        incumbent_assignment_count=1,
    )
    builder_identity = _write(tmp_path / "baseline/builder.py", b"# fixture builder\n")
    metadata = {
        "builder_identity": builder_identity,
        "campaign_provenance": campaign_provenance,
        "canonical_binary": True,
        "created_at_utc": "2026-08-02T23:00:00Z",
        "errors": [],
        "global_claim_authorized": False,
        "historical_model_text_sha256": historical_model_text_sha256,
        "input_identities": checkout_inputs,
        "legacy_control_used_as_build_input": False,
        "model_backend": BASELINE_CONTRACT.MODEL_BACKEND,
        "model_binary_format": BASELINE_CONTRACT.MODEL_BINARY_FORMAT,
        "model_constraint_count": 1,
        "model_identity": model_identity,
        "model_variable_count": 1,
        "purpose": BASELINE_CONTRACT.REBUILD_PURPOSE,
        "schema_version": BASELINE_CONTRACT.METADATA_SCHEMA,
        "status": "PASS",
    }
    metadata_path = tmp_path / "baseline/metadata.json"
    _write(metadata_path, BASELINE_CONTRACT.canonical_json(metadata))
    return {
        "campaign_provenance_path": campaign_provenance_path,
        "expectation": expectation,
        "incumbent_path": Path(str(incumbent_identity["path"])),
        "metadata_path": metadata_path,
        "model_path": Path(str(model_identity["path"])),
    }


def test_replay_paths_produces_tiny_ghost_receipt_with_real_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _ghost_replay_fixture(tmp_path)
    output = tmp_path / "baseline/replay.json"
    monkeypatch.chdir(tmp_path)

    receipt, identity = REPLAY._replay_paths(
        campaign_provenance_path=fixture["campaign_provenance_path"],
        model_path=fixture["model_path"],
        metadata_path=fixture["metadata_path"],
        incumbent_path=fixture["incumbent_path"],
        output_path=output,
        expectation=fixture["expectation"],
        created_at_utc="2026-08-02T23:00:01Z",
        max_time_seconds=2.0,
    )

    assert receipt["status"] == "PASS"
    assert receipt["solver_status"] == "OPTIMAL"
    assert receipt["model_variable_count"] == 1
    assert receipt["model_constraint_count"] == 1
    assert receipt["assignment_count"] == receipt["fixed_assignment_count"] == 1
    assert output.read_bytes() == REPLAY._authority_json(receipt)
    assert identity == _identity(output)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("model_variable_count", 2, "metadata semantics drifted"),
        ("model_constraint_count", 2, "metadata semantics drifted"),
        ("incumbent_assignment_count", 2, "incumbent digest or assignment count drifted"),
        ("incumbent_sha256", "f" * 64, "incumbent digest or assignment count drifted"),
    ],
)
def test_replay_paths_rejects_expectation_drift_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    fixture = _ghost_replay_fixture(tmp_path)
    output = tmp_path / "baseline/replay.json"
    monkeypatch.chdir(tmp_path)
    drifted = replace(fixture["expectation"], **{field: value})

    with pytest.raises(REPLAY.ReplayError, match=message):
        REPLAY._replay_paths(
            campaign_provenance_path=fixture["campaign_provenance_path"],
            model_path=fixture["model_path"],
            metadata_path=fixture["metadata_path"],
            incumbent_path=fixture["incumbent_path"],
            output_path=output,
            expectation=drifted,
            created_at_utc="2026-08-02T23:00:01Z",
            max_time_seconds=2.0,
        )
    assert not output.exists()


def test_fixed_assignment_replay_rejects_unmapped_assignment(
) -> None:
    proto, incumbent, mandatory, candidate, _master = _coordinate_master_replay_fixture()
    drifted = copy.deepcopy(incumbent)
    drifted["miner_001"]["pose_idx"] = 99
    with pytest.raises(REPLAY.ReplayError, match="does not exist in candidate data"):
        REPLAY.replay_fixed_assignment(
            proto.SerializeToString(deterministic=True),
            incumbent=drifted,
            mandatory_instances=mandatory,
            candidate_placements=candidate,
            max_time_seconds=2.0,
        )


def test_fixed_assignment_replay_allows_unnamed_nonselector(
) -> None:
    proto, incumbent, mandatory, candidate, _master = _coordinate_master_replay_fixture()
    unnamed = proto.variables.add()
    unnamed.domain.extend((0, 1))

    result = REPLAY.replay_fixed_assignment(
        proto.SerializeToString(deterministic=True),
        incumbent=incumbent,
        mandatory_instances=mandatory,
        candidate_placements=candidate,
        max_time_seconds=2.0,
    )

    assert result["status"] == "PASS"
    assert result["fixed_assignment_count"] == len(incumbent) == 5


def test_fixed_assignment_replay_rejects_nonboolean_c1_variable() -> None:
    proto, incumbent, mandatory, candidate, _master = _coordinate_master_replay_fixture()
    c1_variable = next(variable for variable in proto.variables if variable.name == "c1pole__5")
    del c1_variable.domain[:]
    c1_variable.domain.extend((0, 2))

    with pytest.raises(REPLAY.ReplayError, match="exact boolean"):
        REPLAY.replay_fixed_assignment(
            proto.SerializeToString(deterministic=True),
            incumbent=incumbent,
            mandatory_instances=mandatory,
            candidate_placements=candidate,
            max_time_seconds=2.0,
        )


def test_fixed_assignment_replay_rejects_duplicate_mandatory_pose_mapping() -> None:
    proto, incumbent, mandatory, candidate, _master = _coordinate_master_replay_fixture()
    duplicated = copy.deepcopy(incumbent)
    duplicated["miner_002"].update(
        {
            "pose_idx": 0,
            "pose_id": "miner_top",
            "anchor": {"x": 0, "y": 2},
        }
    )

    with pytest.raises(REPLAY.ReplayError, match="ordering is not one-to-one"):
        REPLAY.replay_fixed_assignment(
            proto.SerializeToString(deterministic=True),
            incumbent=duplicated,
            mandatory_instances=mandatory,
            candidate_placements=candidate,
            max_time_seconds=2.0,
        )


@pytest.mark.parametrize(
    ("instance_id", "field", "value", "message"),
    [
        ("miner_001", "is_mandatory", False, "mandatory incumbent identity"),
        (
            "pose_optional::protocol_storage_box::box_0",
            "operation_type",
            "wrong_operation",
            "optional incumbent semantics",
        ),
        ("ghost_pick", "bound_type", "exact", "ghost incumbent semantics"),
    ],
)
def test_fixed_assignment_replay_rejects_incumbent_semantic_drift(
    instance_id: str,
    field: str,
    value: object,
    message: str,
) -> None:
    proto, incumbent, mandatory, candidate, _master = _coordinate_master_replay_fixture()
    drifted = copy.deepcopy(incumbent)
    drifted[instance_id][field] = value

    with pytest.raises(REPLAY.ReplayError, match=message):
        REPLAY.replay_fixed_assignment(
            proto.SerializeToString(deterministic=True),
            incumbent=drifted,
            mandatory_instances=mandatory,
            candidate_placements=candidate,
            max_time_seconds=2.0,
        )


def test_fixed_assignment_replay_rejects_mandatory_authority_semantic_drift() -> None:
    proto, incumbent, mandatory, candidate, _master = _coordinate_master_replay_fixture()
    drifted = copy.deepcopy(mandatory)
    drifted[0]["bound_type"] = "not_exact"

    with pytest.raises(REPLAY.ReplayError, match="mandatory instance authority semantics"):
        REPLAY.replay_fixed_assignment(
            proto.SerializeToString(deterministic=True),
            incumbent=incumbent,
            mandatory_instances=drifted,
            candidate_placements=candidate,
            max_time_seconds=2.0,
        )


def test_strict_json_requires_canonical_authority_bytes() -> None:
    assert REPLAY._strict_json(b'{"a":1}\n', "fixture") == {"a": 1}
    with pytest.raises(REPLAY.ReplayError, match="not canonical"):
        REPLAY._strict_json(b'{"a": 1}\n', "fixture")


def _fixed_args(**changes: object) -> argparse.Namespace:
    value = {
        "master_seconds": 900.0,
        "binding_seconds": 600.0,
        "routing_seconds": 600.0,
        "max_iterations": 30,
        "binding_alt_cap": 200,
        "workers": 1,
        "seed": 2026072301,
        "ghost_w": 6,
        "ghost_h": 6,
        "run_nonce": "fixture-run",
        "campaign_provenance": ROOT / ".artifacts/fixture-campaign/campaign-provenance.json",
        "candidate_placements": (ROOT / "data/preprocessed/candidate_placements.json"),
        "canonical_rules": (ROOT / "rules/canonical_rules.json"),
        "mandatory_instances": (ROOT / "data/preprocessed/mandatory_exact_instances.json"),
    }
    value.update(changes)
    return argparse.Namespace(**value)


def test_baseline_rebuild_rejects_parameter_drift() -> None:
    REBUILD._validate_fixed_parameters(_fixed_args())
    with pytest.raises(REBUILD.BaselineRebuildError, match="parameters drifted"):
        REBUILD._validate_fixed_parameters(_fixed_args(seed=7))
    with pytest.raises(REBUILD.BaselineRebuildError, match="nonce"):
        REBUILD._validate_fixed_parameters(_fixed_args(run_nonce=""))
    with pytest.raises(REBUILD.BaselineRebuildError, match="campaign provenance"):
        REBUILD._validate_fixed_parameters(_fixed_args(campaign_provenance=Path("relative-provenance.json")))
    with pytest.raises(REBUILD.BaselineRebuildError, match="not absolute"):
        REBUILD._validate_fixed_parameters(_fixed_args(candidate_placements=Path("relative.json")))


def test_baseline_builder_declares_non_authorizing_output() -> None:
    source = (RESEARCH / "baseline_rebuild_v1.py").read_text(encoding="utf-8")
    assert '"authorizing": False' in source
    assert "EXACT_CUT_FRAMEWORK_ATTACH" in source
    assert "enabled_cut_families=()" in source
    assert "EXPECTED_REPOSITORY_ROOT" not in source
    assert "EXPECTED_HEAD" not in source
    assert "sys.meta_path" not in source
    assert "importlib" not in source
    assert "baseline_contract.campaign_provenance" in source
    assert BASELINE_CONTRACT.CHECKOUT_IMPORT_MODE == "tracked_clean_pinned_checkout"
