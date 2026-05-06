from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_mandatory_rectangle_precheck_profiler as profiler_module
from src.search.phase3b_mandatory_rectangle_precheck_profiler import (
    build_phase3b_mandatory_rectangle_precheck_profile,
    render_phase3b_mandatory_rectangle_precheck_profile_markdown,
    render_phase3b_mandatory_rectangle_precheck_profile_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _toy_project(project_root: Path) -> Path:
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
        core=SimpleNamespace(build_stats={}, candidate_precheck_artifacts={}),
        core_build_seconds=1.0,
        master_search_profile="exact_coordinate_guided_branching_v4",
    )


def test_mandatory_rectangle_profile_records_boundary_elimination(
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
            "triggered": True,
            "boundary_port_precheck": {
                "supported": True,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 2,
                "screen_pass_anchor_count": 0,
            },
        },
    )

    report = build_phase3b_mandatory_rectangle_precheck_profile(
        tmp_path / "project",
        candidate="69x19",
    )

    assert report["metadata"]["source"] == (
        "phase3b_mandatory_rectangle_precheck_profiler_v1"
    )
    assert report["status"]["outcome"] == "boundary_port_eliminated"
    assert report["boundary_port_precheck"]["triggered"] is True
    assert report["groups"] == []


def test_mandatory_rectangle_profile_records_group_anchor_timings(
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
            "boundary_port_precheck": {
                "supported": True,
                "considered_anchor_count": 3,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 3,
                "screen_pass_anchor_indices": (0, 1, 2),
                "rebuild_anchor_indices": (0, 1, 2),
            },
        },
    )

    class FakeModel:
        build_stats = {
            "search_guidance": {"ghost_literals": 3},
            "exact_core_reuse": {"used": True},
        }
        u_vars = {0: object(), 1: object(), 2: object()}
        _ghost_domains = [
            {"cells": []},
            {"cells": [(0, 0)]},
            {"cells": [(1, 0)]},
        ]
        _mandatory_groups = [
            {
                "group_id": "group::boundary_storage_port::boundary_io::0",
                "facility_type": "boundary_storage_port",
                "operation_type": "boundary_io",
                "count": 1,
            },
            {
                "group_id": "group::manufacturing_3x3::craft::1",
                "facility_type": "manufacturing_3x3",
                "operation_type": "craft",
                "count": 2,
            },
        ]

        def _candidate_pose_indices_for_group(self, group):
            return [0, 1, 2]

        def _exact_candidate_mandatory_pool_support_info(self, tpl, candidate_indices):
            return {
                "supported": True,
                "oracle_class": "uniform_3x3",
                "oracle_mode": "uniform_3x3",
                "unsupported_reason": None,
            }

        def _pose_cells(self, tpl, pose_idx):
            return {(int(pose_idx), 0)}

        def _compact_signature_for_pose_indices(self, tpl, pose_indices):
            return tuple((int(idx), 0, 0) for idx in pose_indices)

        def _normalize_rectangle_frontier_signature(self, tpl, compact_signature):
            return tuple((int(idx), 0, 3, 3) for idx, _dy, _shape in compact_signature)

        def _find_mandatory_rectangle_precheck_witness(
            self,
            tpl,
            pose_indices,
            required_count,
        ):
            return None

        def _solve_exact_local_power_capacity_from_compact(self, tpl, compact_signature):
            return len(compact_signature)

    monkeypatch.setattr(
        profiler_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeModel()),
    )

    report = build_phase3b_mandatory_rectangle_precheck_profile(
        tmp_path / "project",
        candidate="69x19",
        anchor_offset=1,
        anchor_limit=2,
        group_limit=4,
    )

    assert report["status"]["outcome"] == "profile_built"
    assert report["sample"]["available_anchor_count"] == 3
    assert report["sample"]["sampled_anchor_indices"] == [1, 2]
    assert report["sample"]["sampled_group_count"] == 1
    group = report["groups"][0]
    assert group["oracle_mode"] == "uniform_3x3"
    assert group["considered_anchor_count"] == 2
    assert group["screen_pass_anchor_count"] == 2
    assert len(group["anchor_timings"]) == 2

    markdown = render_phase3b_mandatory_rectangle_precheck_profile_markdown(report)
    text = render_phase3b_mandatory_rectangle_precheck_profile_text(report)
    assert "Mandatory-Rectangle Precheck Profile" in markdown
    assert "precheck_profiler_not_proof_source" in text


def test_mandatory_rectangle_profile_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = _toy_project(tmp_path / "project")
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "profile_phase3b_mandatory_rectangle_precheck.py"

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
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b mandatory-rectangle precheck profile" in no_write.stdout
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

    assert "mandatory_rectangle_precheck_profile_json=" in write.stdout
    payload = json.loads(
        (output_dir / "mandatory_rectangle_precheck_1x1.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == (
        "phase3b_mandatory_rectangle_precheck_profiler_v1"
    )
    assert (output_dir / "mandatory_rectangle_precheck_1x1.md").exists()
    assert (output_dir / "mandatory_rectangle_precheck_1x1.txt").exists()
