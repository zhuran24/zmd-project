"""
Tests for the exact port-binding subproblem.
"""

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def facility_pools(project_root):
    data = json.loads(
        (project_root / "data" / "preprocessed" / "candidate_placements.json").read_text(
            encoding="utf-8"
        )
    )
    return data["facility_pools"]


def test_binding_model_extracts_concrete_port_specs(project_root, facility_pools):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    instances = [
        {
            "instance_id": "packaging_battery_001",
            "facility_type": "manufacturing_6x4",
            "operation_type": "packaging_battery",
            "is_mandatory": True,
        },
        {
            "instance_id": "boundary_port_001",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
    ]
    placement_solution = {
        "packaging_battery_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["manufacturing_6x4"][0]["pose_id"],
            "anchor": facility_pools["manufacturing_6x4"][0]["anchor"],
            "facility_type": "manufacturing_6x4",
        },
        "boundary_port_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["boundary_storage_port"][0]["pose_id"],
            "anchor": facility_pools["boundary_storage_port"][0]["anchor"],
            "facility_type": "boundary_storage_port",
        },
    }

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 1, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 0, "qiaoyu_capsule": 0},
    )
    model.build()
    assert model.solve(time_limit_seconds=10.0) == "FEASIBLE"

    port_specs = model.extract_port_specs()
    assert len(port_specs) == 7
    assert sum(1 for p in port_specs if p["type"] == "in") == 5
    assert sum(1 for p in port_specs if p["type"] == "out") == 2
    assert sum(1 for p in port_specs if p["commodity"] == "dense_source_powder") == 3
    assert sum(1 for p in port_specs if p["commodity"] == "steel_part") == 2
    assert sum(1 for p in port_specs if p["commodity"] == "valley_battery") == 1
    assert sum(1 for p in port_specs if p["commodity"] == "source_ore") == 1


def test_binding_model_nogood_cut_forces_new_selection(project_root, facility_pools):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    instances = [
        {
            "instance_id": "packaging_battery_001",
            "facility_type": "manufacturing_6x4",
            "operation_type": "packaging_battery",
            "is_mandatory": True,
        },
        {
            "instance_id": "boundary_port_001",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
    ]
    placement_solution = {
        "packaging_battery_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["manufacturing_6x4"][0]["pose_id"],
            "anchor": facility_pools["manufacturing_6x4"][0]["anchor"],
            "facility_type": "manufacturing_6x4",
        },
        "boundary_port_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["boundary_storage_port"][0]["pose_id"],
            "anchor": facility_pools["boundary_storage_port"][0]["anchor"],
            "facility_type": "boundary_storage_port",
        },
    }

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 1, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 0, "qiaoyu_capsule": 0},
    )
    model.build()
    assert model.solve(time_limit_seconds=10.0) == "FEASIBLE"
    first = model.extract_selection()

    model.add_nogood_cut(first)
    assert model.solve(time_limit_seconds=10.0) == "FEASIBLE"
    second = model.extract_selection()

    assert first != second


def test_binding_model_assigns_generic_wireless_sink_inputs(project_root, facility_pools):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    instances = [
        {
            "instance_id": "protocol_box_001",
            "facility_type": "protocol_storage_box",
            "operation_type": "wireless_sink",
            "is_mandatory": False,
        },
    ]
    placement_solution = {
        "protocol_box_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["protocol_storage_box"][0]["pose_id"],
            "anchor": facility_pools["protocol_storage_box"][0]["anchor"],
            "facility_type": "protocol_storage_box",
        },
    }

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 0, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 1, "qiaoyu_capsule": 1},
    )
    model.build()
    assert model.solve(time_limit_seconds=10.0) == "FEASIBLE"

    assert len(model.generic_input_slots) == 3
    assert all(slot.get("virtual") is True for slot in model.generic_input_slots)
    assert all(slot.get("routing_free") is True for slot in model.generic_input_slots)
    assert all(
        "x" not in slot and "y" not in slot and "dir" not in slot
        for slot in model.generic_input_slots
    )

    selection = model.extract_selection()
    assert len(selection["generic_inputs"]) == 3
    assert sum(1 for c in selection["generic_inputs"].values() if c == "valley_battery") == 1
    assert sum(1 for c in selection["generic_inputs"].values() if c == "qiaoyu_capsule") == 1
    assert sum(1 for c in selection["generic_inputs"].values() if c == "__unused__") == 1

    port_specs = model.extract_port_specs()
    sink_specs = [
        p
        for p in port_specs
        if p["instance_id"] == "protocol_box_001" and p["type"] == "in"
    ]
    assert sink_specs == []


def test_binding_model_overload_separation_default_off(project_root, facility_pools, monkeypatch):
    """P1 #9 hint 2 stage 2: with EXACT_BINDING_USE_OVERLOAD_SEPARATION
    unset (default), nogood method must NOT be invoked and
    conflict_summary must report overload_separation_enabled=False."""
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    monkeypatch.delenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", raising=False)

    instances = [
        {
            "instance_id": "protocol_box_001",
            "facility_type": "protocol_storage_box",
            "operation_type": "wireless_sink",
            "is_mandatory": False,
        },
    ]
    placement_solution = {
        "protocol_box_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["protocol_storage_box"][0]["pose_id"],
            "anchor": facility_pools["protocol_storage_box"][0]["anchor"],
            "facility_type": "protocol_storage_box",
        },
    }
    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 0, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 1, "qiaoyu_capsule": 1},
        project_root=project_root,
    )
    model.build()
    summary = model.extract_conflict_summary()
    assert summary["overload_separation_enabled"] is False
    assert summary["overload_nogoods_added"] == 0


def test_binding_model_overload_separation_when_enabled_records_summary(
    project_root, facility_pools, monkeypatch
):
    """P1 #9 hint 2 stage 2: with EXACT_BINDING_USE_OVERLOAD_SEPARATION=1,
    nogood method runs and conflict_summary reports
    overload_separation_enabled=True (regardless of nogood count, which
    depends on commodity classification on the project's real data)."""
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    monkeypatch.setenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "1")

    instances = [
        {
            "instance_id": "protocol_box_001",
            "facility_type": "protocol_storage_box",
            "operation_type": "wireless_sink",
            "is_mandatory": False,
        },
    ]
    placement_solution = {
        "protocol_box_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["protocol_storage_box"][0]["pose_id"],
            "anchor": facility_pools["protocol_storage_box"][0]["anchor"],
            "facility_type": "protocol_storage_box",
        },
    }
    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 0, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 1, "qiaoyu_capsule": 1},
        project_root=project_root,
    )
    model.build()
    summary = model.extract_conflict_summary()
    assert summary["overload_separation_enabled"] is True
    assert summary["overload_nogoods_added"] >= 0  # depends on classification


def _make_lbbd_controller_stub(project_root):
    """Minimal stub exposing only the attributes
    `_retry_binding_without_overload_separation` reads. Bound-method invocation
    via the unbound function on LBBDController so we don't need to construct a
    real controller (which requires master / cut_manager / ...)."""
    stub = type("LBBDControllerStub", (), {})()
    stub.master = type("MasterStub", (), {"facility_pools": {}, "source_instances": []})()
    stub.project_root = project_root
    stub.binding_seconds = 1.0
    stub._heartbeat_callback = None
    # _emit_heartbeat reads several timing attrs even when callback is None,
    # but only via dict-build on the early-return; keep them available anyway.
    stub.max_iterations = 1
    stub.master_seconds = 1.0
    stub.routing_seconds = 1.0
    stub.flow_seconds = 1.0
    # No-op heartbeat — the real method early-returns when callback is None,
    # but we'd need to bind it; cleaner to stub directly.
    stub._emit_heartbeat = lambda **_kwargs: None
    return stub


def test_lbbd_retry_helper_sets_env_off_during_build_and_restores(
    project_root, monkeypatch
):
    """P1 #9 hint 2 stage 3: helper must set env to '' for the rebuild,
    then restore the prior value after returning."""
    import os
    import sys

    sys.path.insert(0, str(project_root))
    from src.search import benders_loop as bl

    captured_env_at_build: list[str | None] = []

    class RecordingBindingModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def build(self):
            captured_env_at_build.append(
                os.environ.get("EXACT_BINDING_USE_OVERLOAD_SEPARATION")
            )

        def solve(self, **_kwargs):
            return "FEASIBLE"

        def extract_conflict_summary(self):
            return {
                "overload_separation_enabled": False,
                "overload_nogoods_added": 0,
            }

    monkeypatch.setattr(bl, "PortBindingModel", RecordingBindingModel)
    monkeypatch.setenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "1")

    stub = _make_lbbd_controller_stub(project_root)
    model, status = bl.LBBDController._retry_binding_without_overload_separation(
        stub, solution={}, iteration=0
    )

    assert captured_env_at_build == [""]
    assert os.environ.get("EXACT_BINDING_USE_OVERLOAD_SEPARATION") == "1"
    assert status == "FEASIBLE"
    assert isinstance(model, RecordingBindingModel)


def test_lbbd_retry_helper_pops_env_when_not_set_originally(
    project_root, monkeypatch
):
    """If env was UNSET going in, helper must remove its temporary '' value
    and not leave the key set."""
    import os
    import sys

    sys.path.insert(0, str(project_root))
    from src.search import benders_loop as bl

    class FastBindingModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def build(self):
            pass

        def solve(self, **_kwargs):
            return "INFEASIBLE"

        def extract_conflict_summary(self):
            return {
                "overload_separation_enabled": False,
                "overload_nogoods_added": 0,
            }

    monkeypatch.setattr(bl, "PortBindingModel", FastBindingModel)
    monkeypatch.delenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", raising=False)

    stub = _make_lbbd_controller_stub(project_root)
    _model, status = bl.LBBDController._retry_binding_without_overload_separation(
        stub, solution={}, iteration=0
    )

    assert "EXACT_BINDING_USE_OVERLOAD_SEPARATION" not in os.environ
    assert status == "INFEASIBLE"


def test_lbbd_retry_helper_restores_env_even_when_solve_raises(
    project_root, monkeypatch
):
    """The env restore must be in a finally block; verify by raising in solve."""
    import os
    import sys

    sys.path.insert(0, str(project_root))
    from src.search import benders_loop as bl

    class ExplodingBindingModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def build(self):
            pass

        def solve(self, **_kwargs):
            raise RuntimeError("synthetic solver failure")

        def extract_conflict_summary(self):
            return {}

    monkeypatch.setattr(bl, "PortBindingModel", ExplodingBindingModel)
    monkeypatch.setenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "yes")

    stub = _make_lbbd_controller_stub(project_root)
    with pytest.raises(RuntimeError, match="synthetic solver failure"):
        bl.LBBDController._retry_binding_without_overload_separation(
            stub, solution={}, iteration=0
        )

    assert os.environ.get("EXACT_BINDING_USE_OVERLOAD_SEPARATION") == "yes"


def test_lbbd_retry_helper_replays_rejected_selections_after_overload_exhaustion(
    project_root, facility_pools, monkeypatch
):
    """When overload separation exhausts only the separated assignments, the
    fallback must retry env-off with all prior routing-rejected selections
    replayed.  Otherwise a later INFEASIBLE after binding nogoods can be
    mistaken for true binding exhaustion."""
    import os
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel
    from src.search import benders_loop as bl

    def fake_classification(self):
        return {
            "qiaoyu_capsule": "high_prod_low_demand",
            "valley_battery": "low_prod_high_demand",
        }

    monkeypatch.setattr(
        PortBindingModel,
        "_load_overload_classification",
        fake_classification,
    )
    monkeypatch.setenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "1")

    instances = []
    placement_solution = {}
    for index in range(2):
        instance_id = f"protocol_box_{index + 1:03d}"
        pose = facility_pools["protocol_storage_box"][index]
        instances.append(
            {
                "instance_id": instance_id,
                "facility_type": "protocol_storage_box",
                "operation_type": "wireless_sink",
                "is_mandatory": False,
            }
        )
        placement_solution[instance_id] = {
            "pose_idx": index,
            "pose_id": pose["pose_id"],
            "anchor": pose["anchor"],
            "facility_type": "protocol_storage_box",
        }

    generic_io_requirements = {
        "required_generic_outputs": {"source_ore": 0, "blue_iron_ore": 0},
        "required_generic_inputs": {"qiaoyu_capsule": 1, "valley_battery": 1},
    }
    env_on_model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        project_root=project_root,
        wireless_sink_generic_input_slots=3,
        **generic_io_requirements,
    )
    env_on_model.build()
    assert env_on_model.extract_conflict_summary()["overload_nogoods_added"] == 18

    status = env_on_model.solve(time_limit_seconds=1.0)
    rejected_selections = []
    while status == "FEASIBLE":
        selection = env_on_model.extract_selection()
        rejected_selections.append(selection)
        env_on_model.add_nogood_cut(selection)
        status = env_on_model.solve(time_limit_seconds=1.0)

    assert status == "INFEASIBLE"
    assert len(rejected_selections) == 18

    stub = _make_lbbd_controller_stub(project_root)
    stub.solve_mode = "certified_exact"
    stub.master.facility_pools = facility_pools
    stub.master.source_instances = instances
    stub.master.generic_io_requirements = generic_io_requirements
    stub.master.wireless_sink_generic_input_slots = 3

    retry_model, retry_status = bl.LBBDController._retry_binding_without_overload_separation(
        stub,
        solution=placement_solution,
        iteration=0,
        rejected_selections=rejected_selections,
    )

    assert retry_status == "FEASIBLE"
    assert os.environ.get("EXACT_BINDING_USE_OVERLOAD_SEPARATION") == "1"
    retry_summary = retry_model.extract_conflict_summary()
    assert retry_summary["overload_separation_enabled"] is False
    selected_inputs = retry_model.extract_selection()["generic_inputs"]
    by_instance = {}
    for slot_id, commodity in selected_inputs.items():
        if commodity == "__unused__":
            continue
        instance_id = slot_id.split(":in:", maxsplit=1)[0]
        by_instance.setdefault(instance_id, set()).add(commodity)
    assert {"qiaoyu_capsule", "valley_battery"} in by_instance.values()


def test_binding_model_reports_pose_binding_domain_cache_reuse(project_root, facility_pools):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel
    from src.models.port_binding import clear_pose_level_binding_domain_cache

    clear_pose_level_binding_domain_cache()

    instances = [
        {
            "instance_id": "packaging_battery_001",
            "facility_type": "manufacturing_6x4",
            "operation_type": "packaging_battery",
            "is_mandatory": True,
        },
        {
            "instance_id": "packaging_battery_002",
            "facility_type": "manufacturing_6x4",
            "operation_type": "packaging_battery",
            "is_mandatory": True,
        },
    ]
    placement_solution = {
        "packaging_battery_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["manufacturing_6x4"][0]["pose_id"],
            "anchor": facility_pools["manufacturing_6x4"][0]["anchor"],
            "facility_type": "manufacturing_6x4",
        },
        "packaging_battery_002": {
            "pose_idx": 2,
            "pose_id": facility_pools["manufacturing_6x4"][2]["pose_id"],
            "anchor": facility_pools["manufacturing_6x4"][2]["anchor"],
            "facility_type": "manufacturing_6x4",
        },
    }

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 0, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 0, "qiaoyu_capsule": 0},
    )
    model.build()
    summary = model.extract_conflict_summary()

    assert summary["binding_domain_cache_hits"] == 1
    assert summary["binding_domain_cache_misses"] == 1
    assert summary["binding_domain_reused_instances"] == ["packaging_battery_002"]


def test_binding_model_keeps_generic_slot_instances_out_of_pose_level_cache(project_root, facility_pools):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel
    from src.models.port_binding import clear_pose_level_binding_domain_cache

    clear_pose_level_binding_domain_cache()

    instances = [
        {
            "instance_id": "boundary_port_001",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
    ]
    placement_solution = {
        "boundary_port_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["boundary_storage_port"][0]["pose_id"],
            "anchor": facility_pools["boundary_storage_port"][0]["anchor"],
            "facility_type": "boundary_storage_port",
        },
    }

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 1, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 0, "qiaoyu_capsule": 0},
    )
    model.build()
    summary = model.extract_conflict_summary()

    assert summary["binding_domain_cache_hits"] == 0
    assert summary["binding_domain_cache_misses"] == 0
    assert summary["binding_domain_reused_instances"] == []


def test_binding_model_keeps_generic_outputs_globally_pooled(project_root, facility_pools):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    instances = [
        {
            "instance_id": "boundary_port_001",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
        {
            "instance_id": "boundary_port_002",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
    ]
    placement_solution = {
        "boundary_port_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["boundary_storage_port"][0]["pose_id"],
            "anchor": facility_pools["boundary_storage_port"][0]["anchor"],
            "facility_type": "boundary_storage_port",
        },
        "boundary_port_002": {
            "pose_idx": 1,
            "pose_id": facility_pools["boundary_storage_port"][1]["pose_id"],
            "anchor": facility_pools["boundary_storage_port"][1]["anchor"],
            "facility_type": "boundary_storage_port",
        },
    }

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 1, "blue_iron_ore": 1},
        required_generic_inputs={"valley_battery": 0, "qiaoyu_capsule": 0},
    )
    model.build()
    summary = model.extract_conflict_summary()

    assert summary["binding_domain_count"] == 0
    assert summary["binding_domain_cache_hits"] == 0
    assert summary["binding_domain_cache_misses"] == 0
    assert summary["binding_domain_reused_instances"] == []

    assert model.solve(time_limit_seconds=10.0) == "FEASIBLE"
    first = model.extract_selection()
    assert first["binding_choice"] == {}
    assert sorted(first["generic_outputs"].values()) == ["blue_iron_ore", "source_ore"]

    model.add_nogood_cut(first)
    assert model.solve(time_limit_seconds=10.0) == "FEASIBLE"
    second = model.extract_selection()

    assert second["binding_choice"] == {}
    assert sorted(second["generic_outputs"].values()) == ["blue_iron_ore", "source_ore"]
    assert first["generic_outputs"] != second["generic_outputs"]


def test_binding_model_reports_exact_search_guidance(project_root, facility_pools):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    instances = [
        {
            "instance_id": "packaging_battery_001",
            "facility_type": "manufacturing_6x4",
            "operation_type": "packaging_battery",
            "is_mandatory": True,
        },
        {
            "instance_id": "boundary_port_001",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
    ]
    placement_solution = {
        "packaging_battery_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["manufacturing_6x4"][0]["pose_id"],
            "anchor": facility_pools["manufacturing_6x4"][0]["anchor"],
            "facility_type": "manufacturing_6x4",
        },
        "boundary_port_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["boundary_storage_port"][0]["pose_id"],
            "anchor": facility_pools["boundary_storage_port"][0]["anchor"],
            "facility_type": "boundary_storage_port",
        },
    }

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 1, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 0, "qiaoyu_capsule": 0},
    )
    model.build()
    summary = model.extract_conflict_summary()

    assert summary["search_guidance"]["applied"] is True
    assert summary["search_guidance"]["profile"] == "exact_binding_guided_branching_v1"
    assert summary["search_guidance"]["binding_literals"] > 0
    assert summary["search_guidance"]["generic_output_literals"] > 0

    assert model.solve(time_limit_seconds=10.0) == "FEASIBLE"
    solved_summary = model.extract_conflict_summary()
    assert solved_summary["search_profile"] == "exact_binding_guided_branching_v1"
    assert solved_summary["search_branching"].endswith("FIXED_SEARCH")


def test_binding_solver_worker_override_changes_only_solver_parameter(
    project_root,
    facility_pools,
    monkeypatch,
):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    monkeypatch.setenv("EXACT_BINDING_CP_SAT_WORKERS", "2")

    instances = [
        {
            "instance_id": "protocol_box_001",
            "facility_type": "protocol_storage_box",
            "operation_type": "wireless_sink",
            "is_mandatory": False,
        },
    ]
    placement_solution = {
        "protocol_box_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["protocol_storage_box"][0]["pose_id"],
            "anchor": facility_pools["protocol_storage_box"][0]["anchor"],
            "facility_type": "protocol_storage_box",
        },
    }

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 0, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 1, "qiaoyu_capsule": 0},
    )
    model.build()
    assert model.solve(time_limit_seconds=10.0) == "FEASIBLE"
    assert model._solver is not None
    assert int(model._solver.parameters.num_workers) == 2


def test_binding_model_allows_unused_generic_output_slots():
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    pose = {
        "pose_id": "protocol_core_two_outputs",
        "anchor": {"x": 10, "y": 10},
        "occupied_cells": [],
        "input_port_cells": [],
        "output_port_cells": [
            {"x": 10, "y": 9, "dir": "N"},
            {"x": 11, "y": 9, "dir": "N"},
        ],
    }
    instances = [
        {
            "instance_id": "core_001",
            "facility_type": "protocol_core",
            "operation_type": "protocol_core",
            "is_mandatory": True,
        }
    ]
    placement_solution = {
        "core_001": {
            "pose_idx": 0,
            "pose_id": pose["pose_id"],
            "anchor": pose["anchor"],
            "facility_type": "protocol_core",
        }
    }

    model = PortBindingModel(
        placement_solution,
        {"protocol_core": [pose]},
        instances,
        required_generic_outputs={"source_ore": 1},
        required_generic_inputs={},
    )
    model.build()
    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"

    selection = model.extract_selection()
    assert sorted(selection["generic_outputs"].values()) == ["__unused__", "source_ore"]

    port_specs = model.extract_port_specs()
    assert len(port_specs) == 1
    assert port_specs[0]["commodity"] == "source_ore"


def test_load_generic_io_requirements_rejects_missing_sections(tmp_path):
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_generic_io_requirements

    path = tmp_path / "generic_io_requirements.json"
    path.write_text(json.dumps({"required_generic_outputs": {}}), encoding="utf-8")

    with pytest.raises(KeyError, match="required_generic_inputs"):
        load_generic_io_requirements(path=path, validate_against_canonical=False)


def test_load_generic_io_requirements_rejects_invalid_slot_counts(tmp_path):
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_generic_io_requirements

    path = tmp_path / "generic_io_requirements.json"
    path.write_text(
        json.dumps(
            {
                "required_generic_outputs": {"source_ore": 0.5},
                "required_generic_inputs": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match="source_ore"):
        load_generic_io_requirements(path=path, validate_against_canonical=False)


def test_load_generic_io_requirements_rejects_non_canonical_roles(tmp_path):
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_generic_io_requirements

    path = tmp_path / "generic_io_requirements.json"
    path.write_text(
        json.dumps(
            {
                "required_generic_outputs": {"steel_block": 1},
                "required_generic_inputs": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="external_boundary"):
        load_generic_io_requirements(project_root=project_root, path=path)

    path.write_text(
        json.dumps(
            {
                "required_generic_outputs": {},
                "required_generic_inputs": {"steel_block": 1},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="generic_input"):
        load_generic_io_requirements(project_root=project_root, path=path)


def test_load_generic_io_requirements_rejects_output_only_when_canonical_generic_inputs_exist(
    tmp_path, project_root
):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_generic_io_requirements

    path = tmp_path / "generic_io_requirements.json"
    path.write_text(
        json.dumps(
            {
                "required_generic_outputs": {"source_ore": 18, "blue_iron_ore": 34},
                "required_generic_inputs": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing=qiaoyu_capsule,valley_battery"):
        load_generic_io_requirements(project_root=project_root, path=path)


def test_load_generic_io_requirements_rejects_missing_or_zero_canonical_generic_inputs(
    tmp_path, project_root
):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_generic_io_requirements

    path = tmp_path / "generic_io_requirements.json"
    path.write_text(
        json.dumps(
            {
                "required_generic_outputs": {"source_ore": 18, "blue_iron_ore": 34},
                "required_generic_inputs": {"valley_battery": 1},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing=qiaoyu_capsule"):
        load_generic_io_requirements(project_root=project_root, path=path)

    path.write_text(
        json.dumps(
            {
                "required_generic_outputs": {"source_ore": 18, "blue_iron_ore": 34},
                "required_generic_inputs": {"qiaoyu_capsule": 0, "valley_battery": 1},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non_positive=qiaoyu_capsule"):
        load_generic_io_requirements(project_root=project_root, path=path)


def test_load_wireless_sink_generic_input_slots_rejects_non_integer(tmp_path):
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_wireless_sink_generic_input_slots

    path = tmp_path / "preprocess_plan.json"
    path.write_text(
        json.dumps(
            {
                "utility_operations": {
                    "wireless_sink": {
                        "generic_input_slots": 3.5,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match="generic_input_slots"):
        load_wireless_sink_generic_input_slots(path=path)


def test_load_generic_io_requirements_rejects_reserved_unused_commodity(tmp_path):
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_generic_io_requirements

    path = tmp_path / "generic_io_requirements.json"
    path.write_text(
        json.dumps(
            {
                "required_generic_outputs": {"__unused__": 1},
                "required_generic_inputs": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="__unused__"):
        load_generic_io_requirements(path=path, validate_against_canonical=False)


def test_master_generic_io_artifact_loader_rejects_loose_counts(tmp_path, project_root):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.master_model import load_generic_io_requirements_artifact

    (tmp_path / "data" / "preprocessed").mkdir(parents=True)
    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "canonical_rules.json").write_text(
        (project_root / "rules" / "canonical_rules.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "data" / "preprocessed" / "generic_io_requirements.json").write_text(
        json.dumps(
            {
                "required_generic_outputs": {"source_ore": 0},
                "required_generic_inputs": {"valley_battery": "100"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match="valley_battery"):
        load_generic_io_requirements_artifact(tmp_path)


def test_master_generic_io_artifact_loader_rejects_noncanonical_roles(tmp_path, project_root):
    import sys

    sys.path.insert(0, str(project_root))
    from src.models.master_model import load_generic_io_requirements_artifact

    (tmp_path / "data" / "preprocessed").mkdir(parents=True)
    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "canonical_rules.json").write_text(
        (project_root / "rules" / "canonical_rules.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "data" / "preprocessed" / "generic_io_requirements.json").write_text(
        json.dumps(
            {
                "required_generic_outputs": {},
                "required_generic_inputs": {"steel_block": 1},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="generic_input"):
        load_generic_io_requirements_artifact(tmp_path)


def test_load_generic_io_requirements_rejects_duplicate_json_keys(tmp_path):
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_generic_io_requirements

    path = tmp_path / "generic_io_requirements.json"
    path.write_text(
        '{"required_generic_outputs":{"source_ore":1},'
        '"required_generic_outputs":{},'
        '"required_generic_inputs":{}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_generic_io_requirements(path=path, validate_against_canonical=False)


def test_load_wireless_sink_generic_input_slots_rejects_duplicate_json_keys(tmp_path):
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import load_wireless_sink_generic_input_slots

    path = tmp_path / "preprocess_plan.json"
    path.write_text(
        '{"utility_operations":{"wireless_sink":{'
        '"generic_input_slots":3,'
        '"generic_input_slots":0}}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_wireless_sink_generic_input_slots(path=path)

def test_binding_uses_injected_wireless_slot_snapshot_over_project_root_plan(tmp_path):
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.models.binding_subproblem import PortBindingModel

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "preprocess_plan.json").write_text(
        json.dumps(
            {
                "utility_operations": {
                    "wireless_sink": {
                        "facility_type": "protocol_storage_box",
                        "generic_input_slots": 1,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    pose = {
        "pose_id": "box_pose",
        "anchor": {"x": 1, "y": 1},
        "occupied_cells": [],
        "input_port_cells": [],
        "output_port_cells": [],
    }
    instances = [
        {
            "instance_id": "box_001",
            "facility_type": "protocol_storage_box",
            "operation_type": "wireless_sink",
            "is_mandatory": True,
        }
    ]
    placement = {
        "box_001": {
            "pose_idx": 0,
            "pose_id": "box_pose",
            "anchor": {"x": 1, "y": 1},
            "facility_type": "protocol_storage_box",
        }
    }

    model = PortBindingModel(
        placement,
        {"protocol_storage_box": [pose]},
        instances,
        required_generic_outputs={},
        required_generic_inputs={"valley_battery": 3},
        project_root=tmp_path,
        wireless_sink_generic_input_slots=3,
    )
    model.build()

    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    assert len(model.generic_input_slots) == 3
