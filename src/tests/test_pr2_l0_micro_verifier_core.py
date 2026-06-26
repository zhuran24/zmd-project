from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from src.search import pr2_l0_micro_verifier_core as l0


def _import_roots(source: str) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_l0_stage1_ast_imports_are_stdlib_only() -> None:
    source_path = Path(l0.__file__).resolve()
    module_roots = _import_roots(source_path.read_text(encoding="utf-8"))
    bootstrap_roots = _import_roots(l0.CHILD_BOOTSTRAP_SOURCE)
    allowed = set(sys.stdlib_module_names) | {"__future__"}

    assert module_roots <= allowed
    assert bootstrap_roots <= allowed
    assert "src" not in module_roots | bootstrap_roots


def test_l0_round_trip_seals_through_snapshot_loader() -> None:
    verdict = l0.run_l0_micro_verifier_round_trip({"action": "ack"})

    assert verdict.status == l0.SEALED
    assert verdict.response["stage_trace"] == [
        "floor_verified",
        "loader_installed",
        "verifier_imported",
        "verifier_ran",
    ]


def test_l0_loader_ignores_sys_path_shadow(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow" / "src" / "search"
    shadow.mkdir(parents=True)
    (shadow / "pr2_l0_trivial_child.py").write_text(
        "def verify(_request):\n"
        "    return {'verdict': 'REJECTED', 'nonce': 'shadow', 'reason': 'shadow'}\n",
        encoding="utf-8",
    )

    verdict = l0.run_l0_micro_verifier_round_trip(
        {"action": "ack"},
        poison_sys_path=shadow.parents[1],
    )

    assert verdict.status == l0.SEALED
    assert verdict.reason == "trivial_ack"


def test_l0_loader_rejects_snapshot_external_project_import() -> None:
    verdict = l0.run_l0_micro_verifier_round_trip(
        {"action": "probe_import", "module": "src.search.exact_campaign"}
    )

    assert verdict.status == l0.REJECTED


def test_l0_bootstrap_is_two_stage_ordered() -> None:
    verdict = l0.run_l0_micro_verifier_round_trip({"action": "ack"})

    assert verdict.status == l0.SEALED
    assert verdict.response["stage_trace"].index("floor_verified") < verdict.response[
        "stage_trace"
    ].index("loader_installed")
    assert verdict.response["stage_trace"].index("loader_installed") < verdict.response[
        "stage_trace"
    ].index("verifier_imported")


def test_l0_binary_nonce_verdicts_fail_closed() -> None:
    good = l0.run_l0_micro_verifier_round_trip({"action": "ack"})
    bad_nonce = l0.run_l0_micro_verifier_round_trip({"action": "wrong_nonce"})
    missing = l0.run_l0_micro_verifier_round_trip(
        {"action": "ack"},
        omit_snapshot_modules=(l0.DEFAULT_VERIFIER_MODULE,),
    )
    timeout = l0.run_l0_micro_verifier_round_trip(
        {"action": "sleep", "seconds": 2.0},
        timeout_seconds=0.1,
    )

    assert good.status == l0.SEALED
    assert bad_nonce.status == l0.REJECTED
    assert missing.status == l0.REJECTED
    assert timeout.status == l0.REJECTED
    assert {good.status, bad_nonce.status, missing.status, timeout.status} <= {
        l0.SEALED,
        l0.REJECTED,
    }


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e400}'])
def test_l0_strict_json_rejects_duplicate_nan_and_overflow(text: str) -> None:
    with pytest.raises(ValueError):
        l0.loads_l0_strict_json(text)
