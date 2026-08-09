from __future__ import annotations

import copy
import hashlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

from docs.research.front_offset_incident_20260718.batch4_harness.rab_front_only_historical_rejudgment import (
    EXPECTED_RECONSTRUCTED_BASELINE,
    EXPECTED_TOTALS,
    HISTORICAL_DIR_DELTA,
    HISTORICAL_FRONT_SOURCE_REVISION,
    HISTORICAL_FRONT_SOURCE_SHA256,
    OLD_CANDIDATE_SHA256,
    PINNED_LAYOUT_SHA256,
    PINNED_RFSC,
    HistoricalRejudgmentError,
    _independent_domain_is_empty,
    _independent_front_is_free,
    _historical_front_source_audit,
    _historical_plus_delta_domain_is_empty,
    _historical_plus_delta_front_is_free,
    _load_pinned_json,
    _path_provenance,
    _production_domain_is_empty,
    _source_provenance,
    _verify_layout_pose_identity,
    deterministic_json,
    write_json_exclusive,
)
from src.models.routing_binding_context import RoutingBindingContext


def _pose(
    *,
    pose_id: str = "p_x01_y02_o0_m_test",
    anchor: tuple[int, int] = (1, 2),
) -> dict[str, Any]:
    return {
        "anchor": {"x": anchor[0], "y": anchor[1]},
        "input_port_cells": [{"x": 1, "y": 1, "dir": "E"}],
        "occupied_cells": [[0, 0]],
        "output_port_cells": [{"x": 3, "y": 3, "dir": "N"}],
        "pose_id": pose_id,
    }


def _layout_entry() -> dict[str, Any]:
    return {
        "anchor": {"x": 1, "y": 2},
        "bound_type": "exact",
        "facility_type": "maker",
        "instance_id": "maker_001",
        "is_mandatory": True,
        "operation_type": "crusher_source",
        "pose_id": "p_x01_y02_o0_m_test",
        "pose_idx": 0,
    }


def _layout(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "ghost_pick": {
            "facility_type": "ghost_rect",
            "instance_id": "ghost_pick",
        },
        "maker_001": entry,
    }


def _context(blocked_cells: set[tuple[int, int]]) -> RoutingBindingContext:
    return RoutingBindingContext(
        grid_width=70,
        grid_height=70,
        occupied_cells=frozenset(blocked_cells),
        component_by_cell={},
        cells_by_component={},
        occupied_owner_by_cell={
            cell: "blocker_001" for cell in sorted(blocked_cells)
        },
    )


def test_historical_inputs_and_reconstructed_counts_are_pinned() -> None:
    assert OLD_CANDIDATE_SHA256 == (
        "a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b"
    )
    assert PINNED_RFSC == frozenset({"qiaoyu_capsule", "valley_battery"})
    assert len(PINNED_LAYOUT_SHA256) == 6
    assert set(PINNED_LAYOUT_SHA256) == set(EXPECTED_RECONSTRUCTED_BASELINE)
    assert sum(item["identity_checks"] for item in EXPECTED_RECONSTRUCTED_BASELINE.values()) == 1_757
    assert sum(item["checked"] for item in EXPECTED_RECONSTRUCTED_BASELINE.values()) == 1_314
    assert sum(item["empty"] for item in EXPECTED_RECONSTRUCTED_BASELINE.values()) == 1_214
    assert sum(item["nonempty"] for item in EXPECTED_RECONSTRUCTED_BASELINE.values()) == 100
    assert sum(item["old_empty"] for item in EXPECTED_RECONSTRUCTED_BASELINE.values()) == 1_294
    assert sum(item["old_nonempty"] for item in EXPECTED_RECONSTRUCTED_BASELINE.values()) == 20
    assert (
        sum(
            item["old_empty_to_corrected_nonempty"]
            for item in EXPECTED_RECONSTRUCTED_BASELINE.values()
        )
        == 80
    )
    assert (
        sum(
            item["old_nonempty_to_corrected_empty"]
            for item in EXPECTED_RECONSTRUCTED_BASELINE.values()
        )
        == 0
    )
    assert EXPECTED_TOTALS["old_empty"] == 1_294
    assert EXPECTED_TOTALS["old_nonempty"] == 20
    assert EXPECTED_TOTALS["old_empty_to_corrected_nonempty"] == 80
    assert EXPECTED_TOTALS["old_nonempty_to_corrected_empty"] == 0


def test_pose_index_must_resolve_to_layout_pose_id_and_anchor() -> None:
    pools = {"maker": [_pose()]}
    placements, marker_count = _verify_layout_pose_identity(
        _layout(_layout_entry()), pools
    )
    assert marker_count == 1
    assert len(placements) == 1
    assert placements[0].pose_idx == 0

    pose_id_drift = _layout_entry()
    pose_id_drift["pose_id"] = "wrong"
    with pytest.raises(HistoricalRejudgmentError, match="pose_id"):
        _verify_layout_pose_identity(_layout(pose_id_drift), pools)

    anchor_drift = _layout_entry()
    anchor_drift["anchor"] = {"x": 9, "y": 9}
    with pytest.raises(HistoricalRejudgmentError, match="anchor"):
        _verify_layout_pose_identity(_layout(anchor_drift), pools)


def test_independent_oracle_uses_stored_coordinate_without_direction_step() -> None:
    port = {"x": 1, "y": 1, "dir": "E"}
    assert not _independent_front_is_free(port, frozenset({(1, 1)}))
    assert _independent_front_is_free(port, frozenset({(2, 1)}))


def test_historical_comparison_uses_literal_delta_and_self_exemption() -> None:
    port = {"x": 1, "y": 1, "dir": "E"}
    assert HISTORICAL_DIR_DELTA["E"] == (1, 0)
    assert not _historical_plus_delta_front_is_free(
        port,
        _context({(2, 1)}),
        "maker_001",
    )
    self_occupied_context = _context({(2, 1)})
    self_occupied_context.occupied_owner_by_cell[(2, 1)] = "maker_001"
    assert _historical_plus_delta_front_is_free(
        port,
        self_occupied_context,
        "maker_001",
    )
    assert _historical_plus_delta_front_is_free(
        port,
        _context({(1, 1)}),
        "maker_001",
    )


def test_historical_comparison_domain_is_not_the_corrected_oracle() -> None:
    pose = _pose()
    context = _context({(2, 1)})
    assert _historical_plus_delta_domain_is_empty(
        "crusher_source", pose, context, "maker_001"
    )
    corrected_empty, _detail = _independent_domain_is_empty(
        "crusher_source", pose, frozenset({(2, 1)})
    )
    assert corrected_empty is False


def test_historical_source_audit_is_hash_pinned() -> None:
    """把一份历史源码钉在 revision + sha256 上，防止叙事漂移。

    2026-08-09 起在本 checkout 里可能跳过：git 版本库被空白重建（旧库连同 820 个
    commit 备份在仓库外），`HISTORICAL_FRONT_SOURCE_REVISION` 指向的 commit 不在
    新历史里，`git show` 只能报 128。CLAUDE.md 早把这种情形写成本仓库的已知现实
    ——「交付副本，git 历史被重建过，README 里引用的 commit hash 均不可解析，只能
    当叙事线索」——所以这不是回归，而是那段话描述的状态到达了这条测试。

    skip 而不是删：钉子留在原处，历史一旦接回来就自动重新生效；删掉则等于让这份
    证据无声退休，而下一个读者不会知道它存在过。
    """
    try:
        audit = _historical_front_source_audit()
    except subprocess.CalledProcessError as exc:
        pytest.skip(
            f"历史 revision {HISTORICAL_FRONT_SOURCE_REVISION[:12]} 在本 checkout 不可解析"
            f"（git 退出码 {exc.returncode}）——版本库于 2026-08-09 空白重建；"
            "接回原历史后这枚 hash 钉子自动复活"
        )
    assert audit["git_revision"] == HISTORICAL_FRONT_SOURCE_REVISION
    assert audit["sha256"] == HISTORICAL_FRONT_SOURCE_SHA256
    assert audit["behavior_confirmed_from_source"] == {
        "front_coordinate": "stored (x,y) plus literal direction delta",
        "self_occupied_cell_exemption": True,
        "unknown_direction_fallback_delta": [0, 0],
    }


@pytest.mark.parametrize(
    ("blocked_cells", "expected_empty"),
    [
        ({(1, 1)}, True),
        ({(2, 1)}, False),
    ],
)
def test_current_production_arm_matches_independent_identity_oracle(
    blocked_cells: set[tuple[int, int]],
    expected_empty: bool,
) -> None:
    pose = _pose()
    production_empty = _production_domain_is_empty(
        "crusher_source",
        pose,
        _context(blocked_cells),
        "maker_001",
    )
    oracle_empty, _detail = _independent_domain_is_empty(
        "crusher_source",
        pose,
        frozenset(blocked_cells),
    )
    assert production_empty is expected_empty
    assert oracle_empty is expected_empty


def test_pinned_loader_rejects_wrong_sha(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_text('{"a":1}\n', encoding="utf-8")
    with pytest.raises(HistoricalRejudgmentError, match="SHA-256 mismatch"):
        _load_pinned_json(
            path,
            expected_sha256="0" * 64,
            label="fixture",
        )


def test_provenance_hashes_harness_and_current_front_sources() -> None:
    sources = _source_provenance()
    assert set(sources) == {
        "harness",
        "port_binding",
        "routing_binding_context",
    }
    for item in sources.values():
        path = Path(str(item["absolute_path"]))
        assert path.is_file()
        assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert item["project_relative_path"]


def test_path_provenance_records_absolute_and_project_relative_paths() -> None:
    path = Path(
        "docs/research/front_offset_incident_20260718/"
        "batch4_harness/rab_front_only_historical_rejudgment.py"
    )
    provenance = _path_provenance(path)
    assert provenance["absolute_path"] == str(path.resolve())
    assert provenance["project_relative_path"] == path.as_posix()


def test_deterministic_writer_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    payload = {"z": 2, "a": {"二": 1}}
    expected = deterministic_json(payload).encode("utf-8")
    observed_sha256 = write_json_exclusive(output, payload)

    assert output.read_bytes() == expected
    assert observed_sha256 == hashlib.sha256(expected).hexdigest()

    changed = copy.deepcopy(payload)
    changed["z"] = 3
    with pytest.raises(FileExistsError):
        write_json_exclusive(output, changed)
    assert output.read_bytes() == expected
