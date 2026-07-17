"""front 错位事故批 2 哨兵 — cut 层禁止 front 方向步进（identity 语义）。

历史（保留作史料，勿删）：pre-M2 cut-helper 方向表 N/S 反转（"roadmap I7
latent landmine"），M2 batch C（2026-07-08）曾把它对齐 canonical DIR_DELTA
并在本文件钉了 N/S pin。2026-07-18 front 错位 P0 事故定谳（owner 游戏实测）：
**stored 口坐标本身就是带子格（front）**，整个 "front = port + delta" 公式
是错位语义——方向表连同 ``direction_offset()`` 从 cut 层整体删除。
本文件从"方向表 pin"反转为"不复活"哨兵 + F3 identity 端到端回归。
见 docs/research/front_offset_incident_20260718/00 与
docs/research/rules_audit_20260718/00。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Tuple

import pytest


def test_cut_layer_direction_stepping_stays_deleted() -> None:
    """DIRECTION_OFFSETS / direction_offset 不得在 cut helper 层复活。

    若未来有人重新引入 "port+delta=front" 的方向几何，本哨兵先红。
    identity 语义下 cut 层唯一合法的方向消费是字面合法性校验(N/S/E/W)。
    """
    import src.cuts.helpers.candidate_placements as helpers

    assert not hasattr(helpers, "DIRECTION_OFFSETS")
    assert not hasattr(helpers, "direction_offset")


def test_f3_validator_rejects_old_offset_front_cell() -> None:
    """旧语义 cert（front = port + delta）必须被 validator 判 unsound。

    这是错位公式的反向哨兵：N 口 port_cell=(11,13) 配 front_cell=(11,14)
    （旧 +delta 结果）→ unsound；identity front_cell=(11,13) → 通过该关。
    """
    from src.cuts.families.port_exposure import _validate_front_cell_math

    bad = _validate_front_cell_math((11, 13), "N", (11, 14), 0.0)
    assert bad is not None
    assert bad.kind == "unsound"

    ok = _validate_front_cell_math((11, 13), "N", (11, 13), 0.0)
    assert ok is None

    schema_err = _validate_front_cell_math((11, 13), "NE", (11, 13), 0.0)
    assert schema_err is not None
    assert schema_err.kind == "schema_err"


def test_f3_north_port_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """N-direction port blocked by another facility: oracle emits, validator ok.

    identity 反转（批 2）：口沿 dir 前移一格——crusher 体占 y∈[10..12]，
    N 口 stored 坐标即体外第 1 格 (11,13)（旧 fixture 写体上格 (11,12)、
    front 推 (11,13)）；front 几何逐字保留 = (11,13)，被 y=13 的 refinery
    行占住 → oracle 发 cut，cert 的 front_cell 必须等于 port_cell。
    """
    from src.cuts.families.port_exposure import validate_port_exposure
    from src.cuts.lifecycle import BState, Cell, GroupState
    from src.cuts.oracles.port_exposure_oracle import (
        ORACLE_NAME,
        generate_port_exposure_cuts,
    )

    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")

    candidate_placements: Dict[str, Any] = {
        "facility_pools": {
            "manufacturing_3x3": [
                {
                    "pose_id": "pn",
                    "anchor": {"x": 10, "y": 10},
                    "occupied_cells": [
                        [10, 10], [11, 10], [12, 10],
                        [10, 11], [11, 11], [12, 11],
                        [10, 12], [11, 12], [12, 12],
                    ],
                    "input_port_cells": [],
                    "output_port_cells": [
                        {"x": 11, "y": 13, "dir": "N", "commodity": "test"},
                    ],
                },
                {
                    "pose_id": "p_above",
                    "anchor": {"x": 10, "y": 13},
                    "occupied_cells": [
                        [10, 13], [11, 13], [12, 13],
                        [10, 14], [11, 14], [12, 14],
                        [10, 15], [11, 15], [12, 15],
                    ],
                    "input_port_cells": [],
                    "output_port_cells": [],
                },
            ],
        },
    }
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12)]:
        cell_owner[c] = ("crusher", 0)
    for c in [(10, 13), (11, 13), (12, 13)]:
        cell_owner[c] = ("refinery", 0)

    state = BState(
        groups={
            "crusher": GroupState(
                "crusher", demand=1, pose_domain=frozenset(), selected_poses=["pn"],
            ),
            "refinery": GroupState(
                "refinery", demand=1, pose_domain=frozenset(),
                selected_poses=["p_above"],
            ),
        },
        cell_owner=cell_owner,
        ghost_rect=(40, 40, 5, 5),
        ghost_cells=frozenset(),
        exterior_blocks=frozenset(),
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({ORACLE_NAME}),
        canonical_rules={
            "crusher": {"placement_rule": "free", "cells_per_pose": 9},
            "refinery": {"placement_rule": "free", "cells_per_pose": 9},
        },
        facility_templates={"manufacturing_3x3": {"dimensions": {"w": 3, "h": 3}}},
        instance_to_facility_type={
            "crusher": "manufacturing_3x3",
            "refinery": "manufacturing_3x3",
        },
        candidate_placements=candidate_placements,
    )

    cuts = generate_port_exposure_cuts(state, iter_index=1)
    assert len(cuts) == 1
    cert = json.loads(cuts[0].cert.cert_payload)
    assert cert["port_cell"] == [11, 13]
    assert cert["port_direction"] == "N"
    assert cert["front_cell"] == [11, 13]
    assert cert["blocking_facility"] == ["refinery", 0, "p_above"]

    result = validate_port_exposure(
        cuts[0],
        state,
        {
            "crusher": {"placement_rule": "free", "cells_per_pose": 9},
            "refinery": {"placement_rule": "free", "cells_per_pose": 9},
        },
    )
    assert result.kind == "ok", result.reason
