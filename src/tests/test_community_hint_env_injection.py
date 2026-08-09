"""Verify env-gated community hint loading is robust to bad input.

The loader lives inline in benders_loop._run_certified_exact (around line 3565)
and the unit test here drives just the JSON-parse + merge logic without the
heavy BendersLoop setup.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

from src.models.solution_hint_parser import parse_strict_int_hint_value


def _merge_community_hint_into_greedy(
    community_path: str,
    greedy_hint: Dict[str, int],
) -> Dict[str, Any]:
    """Mirror of benders_loop._run_certified_exact lines 3565-3604 logic.

    Returns dict with: greedy_hint (mutated), overrides count, additions count,
    error (None or string).
    """
    overrides = 0
    additions = 0
    error = None
    if not community_path.strip():
        return {
            "greedy_hint": greedy_hint,
            "overrides": overrides,
            "additions": additions,
            "error": error,
        }
    try:
        community_raw = json.loads(Path(community_path).read_text())
    except FileNotFoundError:
        return {
            "greedy_hint": greedy_hint,
            "overrides": overrides,
            "additions": additions,
            "error": "FileNotFoundError",
        }
    except json.JSONDecodeError:
        return {
            "greedy_hint": greedy_hint,
            "overrides": overrides,
            "additions": additions,
            "error": "JSONDecodeError",
        }
    for inst_id, pose_idx in dict(community_raw or {}).items():
        pose_idx_int = parse_strict_int_hint_value(pose_idx)
        if pose_idx_int is None:
            continue
        key = str(inst_id)
        if key in greedy_hint:
            if greedy_hint[key] != pose_idx_int:
                overrides += 1
        else:
            additions += 1
        greedy_hint[key] = pose_idx_int
    return {
        "greedy_hint": greedy_hint,
        "overrides": overrides,
        "additions": additions,
        "error": error,
    }


def test_empty_path_is_noop() -> None:
    greedy = {"inst_001": 5}
    out = _merge_community_hint_into_greedy("", dict(greedy))
    assert out["error"] is None
    assert out["additions"] == 0
    assert out["overrides"] == 0
    assert out["greedy_hint"] == greedy


def test_whitespace_path_is_noop() -> None:
    greedy = {"inst_001": 5}
    out = _merge_community_hint_into_greedy("   ", dict(greedy))
    assert out["error"] is None
    assert out["greedy_hint"] == greedy


def test_missing_file_is_skipped_gracefully() -> None:
    greedy = {"inst_001": 5}
    out = _merge_community_hint_into_greedy("/tmp/__nonexistent_xyz_zmd.json", dict(greedy))
    assert out["error"] == "FileNotFoundError"
    assert out["greedy_hint"] == greedy


def test_malformed_json_is_skipped_gracefully(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not { valid json")
    greedy = {"inst_001": 5}
    out = _merge_community_hint_into_greedy(str(bad), dict(greedy))
    assert out["error"] == "JSONDecodeError"
    assert out["greedy_hint"] == greedy


def test_overrides_existing_greedy_when_value_differs(tmp_path: Path) -> None:
    community = tmp_path / "hint.json"
    community.write_text(json.dumps({"inst_001": 99}))
    greedy = {"inst_001": 5}
    out = _merge_community_hint_into_greedy(str(community), dict(greedy))
    assert out["overrides"] == 1
    assert out["additions"] == 0
    assert out["greedy_hint"]["inst_001"] == 99


def test_same_value_not_counted_as_override(tmp_path: Path) -> None:
    community = tmp_path / "hint.json"
    community.write_text(json.dumps({"inst_001": 5}))
    greedy = {"inst_001": 5}
    out = _merge_community_hint_into_greedy(str(community), dict(greedy))
    assert out["overrides"] == 0
    assert out["additions"] == 0


def test_additions_for_new_instances(tmp_path: Path) -> None:
    community = tmp_path / "hint.json"
    community.write_text(json.dumps({"inst_001": 99, "inst_new": 42}))
    greedy = {"inst_001": 5}
    out = _merge_community_hint_into_greedy(str(community), dict(greedy))
    assert out["overrides"] == 1
    assert out["additions"] == 1
    assert out["greedy_hint"]["inst_new"] == 42


def test_invalid_pose_idx_values_skipped(tmp_path: Path) -> None:
    community = tmp_path / "hint.json"
    community.write_text(
        json.dumps({"a": "string", "b": 42, "c": None, "d": 3.14, "e": True})
    )
    greedy: Dict[str, int] = {}
    out = _merge_community_hint_into_greedy(str(community), greedy)
    assert "a" not in out["greedy_hint"]
    assert out["greedy_hint"]["b"] == 42
    assert "c" not in out["greedy_hint"]
    assert "d" not in out["greedy_hint"]
    assert "e" not in out["greedy_hint"]


def test_realistic_blueprint_hint_merge() -> None:
    """Smoke test against the actual generated hint file (if present)."""
    actual_hint_path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "hints"
        / "blueprint_2026_05_13_master_hint.json"
    )
    if not actual_hint_path.exists():
        import pytest
        pytest.skip("actual blueprint hint not generated yet")
    fake_greedy = {f"inst_{i:03d}": i % 10 for i in range(266)}
    out = _merge_community_hint_into_greedy(str(actual_hint_path), dict(fake_greedy))
    assert out["error"] is None
    assert out["additions"] + out["overrides"] > 0
