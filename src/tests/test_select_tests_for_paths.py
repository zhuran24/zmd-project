from __future__ import annotations

from scripts import select_tests_for_paths


def _affected(*tests: str) -> select_tests_for_paths.AffectedQuery:
    return select_tests_for_paths.AffectedQuery(tests=tests)


def test_lock_file_triggers_full() -> None:
    result = select_tests_for_paths.decide_tests_for_paths(["PROJECT_LOCK.md"], {})

    assert result.mode == select_tests_for_paths.FULL_MODE
    assert any("PROJECT_LOCK.md" in reason for reason in result.reasons)


def test_conftest_triggers_full() -> None:
    result = select_tests_for_paths.decide_tests_for_paths(["src/tests/conftest.py"], {})

    assert result.mode == select_tests_for_paths.FULL_MODE
    assert any("conftest.py" in reason for reason in result.reasons)


def test_routing_subproblem_selects_routing_tests() -> None:
    result = select_tests_for_paths.decide_tests_for_paths(
        ["src/models/routing_subproblem.py"],
        {
            "src/models/routing_subproblem.py": _affected("src/tests/test_routing.py"),
        },
    )

    assert result.mode == select_tests_for_paths.SELECTED_MODE
    assert result.selected_tests == ("src/tests/test_routing.py",)


def test_empty_affected_results_trigger_full() -> None:
    result = select_tests_for_paths.decide_tests_for_paths(
        ["src/models/routing_subproblem.py"],
        {
            "src/models/routing_subproblem.py": _affected(),
        },
    )

    assert result.mode == select_tests_for_paths.FULL_MODE
    assert any("no src/tests" in reason for reason in result.reasons)


def test_changed_test_file_is_selected_directly() -> None:
    result = select_tests_for_paths.decide_tests_for_paths(
        ["src/tests/test_routing.py"],
        {},
    )

    assert result.mode == select_tests_for_paths.SELECTED_MODE
    assert result.selected_tests == ("src/tests/test_routing.py",)
