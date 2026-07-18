from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.presolve.pre_master_profiler as profiler_module
from src.search.phase3b.presolve.pre_master_profiler import (
    build_phase3b_pre_master_empty_hint_anchor_scan,
    build_phase3b_pre_master_precheck_profile,
    render_phase3b_pre_master_empty_hint_anchor_scan_text,
    render_phase3b_pre_master_profile_markdown,
    render_phase3b_pre_master_profile_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_toy_exact_project(project_root: Path) -> Path:
    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 2, "height": 1}},
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
            },
        },
    )
    _write_json(
        project_root / "rules" / "preprocess_plan.json",
        {"utility_operations": {}},
    )
    _write_json(
        project_root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_0",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    }
                ]
            }
        },
    )
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def _fake_session() -> SimpleNamespace:
    return SimpleNamespace(
        core=SimpleNamespace(
            candidate_precheck_artifacts={
                "mandatory_support_diagnostics": {
                    "unsupported_group_count": 0,
                    "empty_candidate_pool_group_count": 0,
                    "groups": [],
                }
            },
            build_stats={},
            rules={},
        ),
        core_build_seconds=1.25,
        master_search_profile="fake_profile",
    )


def test_pre_master_profile_records_boundary_elimination(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        profiler_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"canonical_rules": "abc"},
    )
    monkeypatch.setattr(
        profiler_module,
        "create_exact_search_session",
        lambda *args, **kwargs: _fake_session(),
    )
    monkeypatch.setattr(
        profiler_module,
        "evaluate_exact_candidate_pre_master_precheck",
        lambda **kwargs: {
            "triggered": True,
            "status": "INFEASIBLE",
            "boundary_port_precheck": {
                "supported": True,
                "required_count": 46,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 2,
                "screen_pass_anchor_count": 0,
                "unsupported_anchor_count": 0,
                "max_packable_min": 19,
                "max_packable_max": 42,
                "first_infeasible_anchor_idx": 0,
                "first_infeasible_anchor_max_packable": 19,
            },
            "proof_summary": {
                "master_candidate_precheck": {
                    "precheck_reason": "boundary_port_all_anchors_infeasible"
                }
            },
        },
    )

    profile = build_phase3b_pre_master_precheck_profile(
        tmp_path / "project",
        candidate="69x19",
    )

    assert profile["metadata"]["source"] == "phase3b_pre_master_precheck_profiler_v1"
    assert profile["status"]["outcome"] == "pre_master_boundary_eliminated"
    assert profile["status"]["precheck_reason"] == "boundary_port_all_anchors_infeasible"
    assert profile["stages"]["boundary_port_precheck"]["triggered"] is True
    assert profile["checks"][0]["status"] == "pass"
    markdown = render_phase3b_pre_master_profile_markdown(profile)
    text = render_phase3b_pre_master_profile_text(profile)
    assert "boundary_port_all_anchors_infeasible" in markdown
    assert "outcome=pre_master_boundary_eliminated" in text


def test_pre_master_profile_skips_mandatory_rectangle_when_cap_exceeded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        profiler_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"canonical_rules": "abc"},
    )
    monkeypatch.setattr(
        profiler_module,
        "create_exact_search_session",
        lambda *args, **kwargs: _fake_session(),
    )
    monkeypatch.setattr(
        profiler_module,
        "evaluate_exact_candidate_pre_master_precheck",
        lambda **kwargs: {
            "triggered": False,
            "status": None,
            "boundary_port_precheck": {
                "supported": True,
                "required_count": 46,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 2,
                "unsupported_anchor_count": 0,
                "screen_pass_anchor_indices": (0, 1),
                "rebuild_anchor_indices": (0, 1),
            },
            "proof_summary": {},
        },
    )
    monkeypatch.setattr(
        profiler_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("mandatory rectangle precheck should be cap-skipped")
            )
        ),
    )

    profile = build_phase3b_pre_master_precheck_profile(
        tmp_path / "project",
        candidate="69x19",
        pre_master_mandatory_rectangle_precheck_max_anchors=1,
    )

    mandatory = profile["stages"]["mandatory_rectangle_precheck"]
    assert profile["status"]["outcome"] == "not_eliminated_by_bounded_pre_master"
    assert mandatory["status"] == "skipped"
    assert mandatory["skip_reason"] == "pre_master_anchor_cap_exceeded"
    assert mandatory["anchor_count"] == 2
    assert mandatory["pre_master_anchor_cap"] == 1


def test_pre_master_profile_default_cap_skips_large_pass_anchor_set(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        profiler_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"canonical_rules": "abc"},
    )
    monkeypatch.setattr(
        profiler_module,
        "create_exact_search_session",
        lambda *args, **kwargs: _fake_session(),
    )
    monkeypatch.setattr(
        profiler_module,
        "evaluate_exact_candidate_pre_master_precheck",
        lambda **kwargs: {
            "triggered": False,
            "status": None,
            "boundary_port_precheck": {
                "supported": True,
                "required_count": 46,
                "considered_anchor_count": 51,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 51,
                "unsupported_anchor_count": 0,
                "screen_pass_anchor_indices": tuple(range(51)),
                "rebuild_anchor_indices": tuple(range(51)),
            },
            "proof_summary": {},
        },
    )
    monkeypatch.setattr(
        profiler_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("default pre-master cap should skip 51 anchors")
            )
        ),
    )

    profile = build_phase3b_pre_master_precheck_profile(
        tmp_path / "project",
        candidate="69x19",
    )

    mandatory = profile["stages"]["mandatory_rectangle_precheck"]
    assert mandatory["status"] == "skipped"
    assert mandatory["skip_reason"] == "pre_master_anchor_cap_exceeded"
    assert mandatory["anchor_count"] == 51
    assert mandatory["pre_master_anchor_cap"] == 32


def test_pre_master_profile_records_mandatory_rectangle_elimination(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        profiler_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"canonical_rules": "abc"},
    )
    monkeypatch.setattr(
        profiler_module,
        "create_exact_search_session",
        lambda *args, **kwargs: _fake_session(),
    )
    monkeypatch.setattr(
        profiler_module,
        "evaluate_exact_candidate_pre_master_precheck",
        lambda **kwargs: {
            "triggered": False,
            "status": None,
            "boundary_port_precheck": {
                "supported": True,
                "required_count": 46,
                "considered_anchor_count": 1,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 1,
                "unsupported_anchor_count": 0,
                "screen_pass_anchor_indices": (0,),
                "rebuild_anchor_indices": (0,),
            },
            "proof_summary": {},
        },
    )

    class FakeModel:
        def evaluate_exact_candidate_mandatory_rectangle_prechecks(self, *, anchor_indices):
            assert tuple(anchor_indices) == (0,)
            return {
                "evaluated": True,
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": 1,
                "supported_group_count": 1,
                "groups": [
                    {
                        "group_id": "group::manufacturing_6x4::refining::0",
                        "facility_type": "manufacturing_6x4",
                        "operation_type": "refining",
                        "required_count": 2,
                        "oracle_class": "m6x4_mixed",
                        "oracle_mode": "m6x4_mixed",
                        "supported": True,
                        "unsupported_reason": None,
                        "considered_anchor_count": 1,
                        "screened_infeasible_anchor_count": 1,
                        "screen_pass_anchor_count": 0,
                        "unsupported_anchor_count": 0,
                        "max_packable_min": 1,
                        "max_packable_max": 1,
                        "first_infeasible_anchor_idx": 0,
                        "first_infeasible_anchor_max_packable": 1,
                    }
                ],
                "rebuild_anchor_indices": tuple(),
            }

    monkeypatch.setattr(
        profiler_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeModel()),
    )

    profile = build_phase3b_pre_master_precheck_profile(
        tmp_path / "project",
        candidate="69x19",
        pre_master_mandatory_rectangle_precheck_max_anchors=4,
    )

    assert profile["status"]["outcome"] == "pre_master_mandatory_rectangle_eliminated"
    assert profile["status"]["precheck_reason"] == (
        "mandatory_rect_group_all_anchors_infeasible"
    )
    mandatory = profile["stages"]["mandatory_rectangle_precheck"]
    assert mandatory["triggered"] is True
    assert mandatory["triggered_group"]["group_id"] == (
        "group::manufacturing_6x4::refining::0"
    )


def test_pre_master_profile_records_coordinate_validation_elimination(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        profiler_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"canonical_rules": "abc"},
    )
    monkeypatch.setattr(
        profiler_module,
        "create_exact_search_session",
        lambda *args, **kwargs: _fake_session(),
    )
    monkeypatch.setattr(
        profiler_module,
        "evaluate_exact_candidate_pre_master_precheck",
        lambda **kwargs: {
            "triggered": False,
            "status": None,
            "boundary_port_precheck": {
                "supported": True,
                "required_count": 46,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 2,
                "unsupported_anchor_count": 0,
                "screen_pass_anchor_indices": (0, 1),
                "rebuild_anchor_indices": (0, 1),
            },
            "proof_summary": {},
        },
    )
    validation_calls: list[tuple[int, float]] = []

    class FakeModel:
        def evaluate_exact_candidate_mandatory_rectangle_prechecks(self, *, anchor_indices):
            assert tuple(anchor_indices) == (0, 1)
            return {
                "evaluated": True,
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": 2,
                "supported_group_count": 0,
                "groups": [],
                "rebuild_anchor_indices": (0, 1),
            }

        def _validate_coordinate_forced_hint(
            self,
            *,
            solution_hint,
            ghost_anchor_hint_idx,
            time_limit_seconds,
            require_complete,
        ):
            assert solution_hint == {}
            assert require_complete is False
            validation_calls.append((int(ghost_anchor_hint_idx), float(time_limit_seconds)))
            return {
                "status": "INFEASIBLE",
                "accepted": False,
                "reason": "coordinate_validation_infeasible",
                "forced_slot_field_count": 3,
                "forced_ghost_anchor": True,
                "wall_time": 0.01,
                "branches": 0,
                "conflicts": 0,
            }

    monkeypatch.setattr(
        profiler_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeModel()),
    )

    profile = build_phase3b_pre_master_precheck_profile(
        tmp_path / "project",
        candidate="69x19",
        pre_master_mandatory_rectangle_precheck_max_anchors=4,
        coordinate_validation_precheck_max_anchors=2,
        coordinate_validation_precheck_seconds=0.5,
    )

    assert validation_calls == [(0, 0.5), (1, 0.5)]
    assert profile["status"]["outcome"] == "pre_master_coordinate_validation_eliminated"
    assert profile["status"]["precheck_reason"] == "coordinate_validation_infeasible"
    coordinate = profile["stages"]["coordinate_validation_precheck"]
    assert coordinate["triggered"] is True
    assert coordinate["summary"]["evaluated_anchor_count"] == 2
    assert coordinate["summary"]["infeasible_anchor_count"] == 2
    assert coordinate["summary"]["status_counts"] == {"INFEASIBLE": 2}
    assert "coordinate_validation_infeasible" in render_phase3b_pre_master_profile_text(profile)


def test_pre_master_profile_coordinate_validation_uses_ghost_domains_when_boundary_unsupported(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        profiler_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"canonical_rules": "abc"},
    )
    monkeypatch.setattr(
        profiler_module,
        "create_exact_search_session",
        lambda *args, **kwargs: _fake_session(),
    )
    monkeypatch.setattr(
        profiler_module,
        "evaluate_exact_candidate_pre_master_precheck",
        lambda **kwargs: {
            "triggered": False,
            "status": None,
            "boundary_port_precheck": {
                "supported": False,
                "required_count": 0,
                "considered_anchor_count": 0,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 0,
                "unsupported_anchor_count": 0,
                "screen_pass_anchor_indices": tuple(),
                "rebuild_anchor_indices": tuple(),
            },
            "proof_summary": {},
        },
    )
    validation_calls: list[int] = []

    class FakeModel:
        _ghost_domains = [{"anchor": {"x": 0, "y": 0}}, {"anchor": {"x": 1, "y": 0}}]

        def _validate_coordinate_forced_hint(
            self,
            *,
            solution_hint,
            ghost_anchor_hint_idx,
            time_limit_seconds,
            require_complete,
        ):
            assert solution_hint == {}
            assert require_complete is False
            validation_calls.append(int(ghost_anchor_hint_idx))
            return {
                "status": "INFEASIBLE",
                "accepted": False,
                "reason": "coordinate_validation_infeasible",
                "forced_ghost_anchor": True,
            }

    monkeypatch.setattr(
        profiler_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeModel()),
    )

    profile = build_phase3b_pre_master_precheck_profile(
        tmp_path / "project",
        candidate="69x19",
        coordinate_validation_precheck_max_anchors=2,
        coordinate_validation_precheck_seconds=0.5,
    )

    assert validation_calls == [0, 1]
    assert profile["status"]["outcome"] == "pre_master_coordinate_validation_eliminated"
    coordinate = profile["stages"]["coordinate_validation_precheck"]
    assert coordinate["anchor_source"] == "ghost_domains_boundary_unsupported"
    assert coordinate["anchor_count"] == 2
    assert coordinate["summary"]["infeasible_anchor_count"] == 2


def test_empty_hint_anchor_scan_does_not_short_circuit_or_claim_elimination(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        profiler_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"canonical_rules": "abc"},
    )
    monkeypatch.setattr(
        profiler_module,
        "create_exact_search_session",
        lambda *args, **kwargs: _fake_session(),
    )
    validation_calls: list[tuple[int, dict, bool]] = []

    class FakeModel:
        _ghost_domains = [
            {"anchor": {"x": 0, "y": 0}},
            {"anchor": {"x": 1, "y": 0}},
            {"anchor": {"x": 2, "y": 0}},
        ]

        def _validate_coordinate_forced_hint(
            self,
            *,
            solution_hint,
            ghost_anchor_hint_idx,
            time_limit_seconds,
            require_complete,
        ):
            validation_calls.append(
                (
                    int(ghost_anchor_hint_idx),
                    dict(solution_hint),
                    bool(require_complete),
                )
            )
            if int(ghost_anchor_hint_idx) == 0:
                return {
                    "attempted": True,
                    "attempted_solver": True,
                    "status": "INFEASIBLE",
                    "accepted": False,
                    "reason": "infeasible",
                    "forced_slot_field_count": 0,
                    "forced_ghost_anchor": True,
                    "branches": 4,
                    "conflicts": 1,
                    "deterministic_time": 0.25,
                    "wall_time": 0.1,
                }
            return {
                "attempted": True,
                "attempted_solver": True,
                "status": "UNKNOWN",
                "accepted": False,
                "reason": "unknown",
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": True,
                "branches": 0,
                "conflicts": 0,
                "deterministic_time": 0.5,
                "wall_time": 0.2,
            }

    monkeypatch.setattr(
        profiler_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeModel()),
    )

    scan = build_phase3b_pre_master_empty_hint_anchor_scan(
        tmp_path / "project",
        candidate="69x19",
        anchor_indices=[0, 1],
        time_limit_seconds=0.5,
    )

    assert validation_calls == [(0, {}, False), (1, {}, False)]
    assert scan["metadata"]["source"] == "phase3b_pre_master_empty_hint_anchor_scan_v1"
    assert scan["profile"]["solution_hint_mode"] == "empty"
    assert scan["profile"]["proof_source"] is False
    assert scan["profile"]["candidate_elimination_claim"] is False
    assert scan["scan"]["candidate_elimination_claim"] is False
    assert scan["scan"]["candidate_elimination_claim_reason"] == "non_exhaustive_scan"
    assert scan["scan"]["evaluated_anchor_count"] == 2
    assert scan["scan"]["status_counts"] == {"INFEASIBLE": 1, "UNKNOWN": 1}
    assert scan["scan"]["anchors"][0]["branches"] == 4
    assert scan["scan"]["anchors"][1]["deterministic_time"] == 0.5
    assert "proof_source=False" in render_phase3b_pre_master_empty_hint_anchor_scan_text(scan)
    assert all(check["status"] == "pass" for check in scan["checks"])


def test_pre_master_profile_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "project")
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "profile_phase3b_pre_master_precheck.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--candidate",
            "1x1",
            "--output-dir",
            str(output_dir),
            "--coordinate-validation-precheck-max-anchors",
            "2",
            "--coordinate-validation-precheck-seconds",
            "0.5",
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b pre-master precheck profile" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--candidate",
            "1x1",
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "pre_master_profile_json=" in write.stdout
    payload = json.loads((output_dir / "pre_master_profile_1x1.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_pre_master_precheck_profiler_v1"
    assert (output_dir / "pre_master_profile_1x1.md").exists()
    assert (output_dir / "pre_master_profile_1x1.txt").exists()
