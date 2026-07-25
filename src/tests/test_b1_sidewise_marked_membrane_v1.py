from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH = PROJECT_ROOT / "docs/research/b1_sidewise_marked_membrane_20260724"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def primary() -> ModuleType:
    return _load(
        "b1_sidewise_marked_membrane_primary_test",
        RESEARCH / "sidewise_marked_membrane_v1.py",
    )


@pytest.fixture(scope="module")
def independent() -> ModuleType:
    return _load(
        "b1_sidewise_marked_membrane_independent_test",
        RESEARCH / "independent_sidewise_marked_membrane_v1.py",
    )


@pytest.fixture(scope="module")
def bootstrap() -> ModuleType:
    return _load(
        "b1_sidewise_marked_membrane_bootstrap_test",
        RESEARCH / "authority_bootstrap_v1.py",
    )


def _fixture(name: str) -> Path:
    return RESEARCH / "fixtures" / name


def _independent_result(module: ModuleType, path: Path) -> tuple[int, int, list[str]]:
    capacities, free_score, target_score, occurrences = module._parse(path.read_bytes())
    maximum, trace, _leaves = module._solve(capacities, free_score, occurrences)
    return maximum, target_score, trace


def test_control_and_ceiling_threshold_are_exact(primary: ModuleType) -> None:
    assert primary.aggregate_control() == {
        "terminal_inside_cap": 124,
        "marked_inside_cap": 88,
        "combined_inside_cap": 212,
    }
    admitted = primary.ceiling_consequence(209)
    assert admitted == {
        "inside_cap": 209,
        "outside_incidences": 529,
        "outside_cells": 133,
        "area": 1188,
        "left_hand_side": 1321,
        "available_nonbody_cells": 1320,
        "ceiling_excluded": True,
    }
    boundary = primary.ceiling_consequence(210)
    assert boundary["outside_incidences"] == 528
    assert boundary["outside_cells"] == 132
    assert boundary["left_hand_side"] == 1320
    assert boundary["ceiling_excluded"] is False


@pytest.mark.parametrize(
    ("name", "expected_maximum", "target_reached"),
    [
        ("core_face_exclusivity.json", 6, False),
        ("endpoint_capacity.json", 7, True),
    ],
)
def test_primary_and_independent_agree_on_synthetic_fixtures(
    primary: ModuleType,
    independent: ModuleType,
    name: str,
    expected_maximum: int,
    target_reached: bool,
) -> None:
    path = _fixture(name)
    model = primary.load_model(path)
    first = primary.solve_exact_fixture(model)
    second_maximum, target, _trace = _independent_result(independent, path)
    assert first.maximum_score == second_maximum == expected_maximum
    assert (expected_maximum >= target) is target_reached


def test_core_face_double_count_canary_changes_the_answer(primary: ModuleType) -> None:
    payload = json.loads(_fixture("core_face_exclusivity.json").read_text())
    payload["groups"][0]["multiplicity"] = 2
    mutated = primary.parse_model_bytes(json.dumps(payload).encode())
    assert primary.solve_exact_fixture(mutated).maximum_score == 12


def test_endpoint_and_capacity_are_both_enforced(primary: ModuleType) -> None:
    payload = {
        "schema_version": primary.MODEL_SCHEMA,
        "side_capacities": [3, 1, 1, 1],
        "free_score": 1,
        "target_score": 5,
        "groups": [
            {
                "name": "partials",
                "multiplicity": 2,
                "faces": [
                    {
                        "name": "face",
                        "contacts": [
                            {
                                "name": "left",
                                "length": 2,
                                "active": 2,
                                "marks": 1,
                                "endpoint": "left",
                            },
                            {
                                "name": "right",
                                "length": 2,
                                "active": 2,
                                "marks": 1,
                                "endpoint": "right",
                            },
                        ],
                    }
                ],
            }
        ],
    }
    model = primary.parse_model_bytes(json.dumps(payload).encode())
    assert primary.solve_exact_fixture(model).maximum_score == 4


def test_closed_schema_and_exact_types_fail_closed(primary: ModuleType) -> None:
    raw = _fixture("core_face_exclusivity.json").read_bytes()
    with pytest.raises(primary.ModelError, match="duplicate JSON key"):
        primary.parse_model_bytes(raw.replace(b'"free_score": 0,', b'"free_score": 0, "free_score": 0,'))
    payload = json.loads(raw)
    payload["groups"][0]["faces"][0]["contacts"][0]["marks"] = 4
    with pytest.raises(primary.ModelError, match="marks cannot exceed active"):
        primary.parse_model_bytes(json.dumps(payload).encode())
    payload = json.loads(raw)
    payload["free_score"] = True
    with pytest.raises(primary.ModelError, match="free_score"):
        primary.parse_model_bytes(json.dumps(payload).encode())


def test_lightweight_state_limit_fails_closed(primary: ModuleType) -> None:
    model = primary.load_model(_fixture("endpoint_capacity.json"))
    with pytest.raises(primary.StateLimitExceeded):
        primary.solve_exact_fixture(model, state_limit=1)


def test_strict_entry_stops_at_game_pause(primary: ModuleType, capsys) -> None:
    strict = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718" / "strict/external/problem_instance.json"
    assert primary.main(["--strict-instance", str(strict)]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PAUSE_FOR_USER_GAME_END"
    assert payload["mode"] == "strict_instance_not_executed"
    assert payload["claim_boundary"] == ("no_strict_recomputation_no_geometry_admission_no_upper_update")


def test_independent_checker_caps_fixture_size(independent: ModuleType) -> None:
    payload = json.loads(_fixture("core_face_exclusivity.json").read_text())
    payload["groups"][0]["multiplicity"] = 13
    with pytest.raises(independent.CheckError, match="fixture cap"):
        independent._parse(json.dumps(payload).encode())


def test_bootstrap_same_fd_reader_rejects_symlink(
    bootstrap: ModuleType,
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap._read_same_fd(link, "test symlink")


def test_bootstrap_output_is_no_overwrite(
    bootstrap: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setattr(bootstrap, "ARTIFACT_ROOT", artifact_root)
    output = artifact_root / "run-20260724T000000Z-Test"
    prepared, child = bootstrap._prepare_output(output)
    assert prepared == output
    assert child == output / "bootstrap-a001"
    with pytest.raises(bootstrap.BootstrapError, match="already exists"):
        bootstrap._prepare_output(output)


def test_reader_facing_status_and_claim_boundary_are_consistent() -> None:
    readme = (RESEARCH / "README.md").read_text()
    proof = (RESEARCH / "01_necessity_proof.md").read_text()
    record = (RESEARCH / "03_execution_record.md").read_text()
    assert "PAUSE_FOR_USER_GAME_END" in readme
    assert "U=(1188,22)" in readme
    assert "L=absent" in readme
    assert "U=(1188,18)" in proof
    assert "尚未准入" in proof
    assert "未运行" in record
    assert "production `CERTIFIED`" in readme
