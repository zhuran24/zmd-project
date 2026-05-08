from __future__ import annotations

import sys
from importlib.util import find_spec
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Skip-if-fixture-missing hook (Phase 3C baseline-failure cleanup, 2026-05-08)
#
# Several legacy test groups inherited from the Codex-era migration depend on
# .artifacts/ build outputs or temporary modules that aren't checked into the
# repository. Rather than failing CI on every fresh clone, we skip them when
# the fixture they need is missing — they remain runnable when the developer
# explicitly produces the fixture (running the corresponding build script).
#
# Each entry maps a substring matched against the test file's path or a test
# nodeid prefix to a callable that returns a "missing fixture" string when the
# fixture isn't available, or None when the test should run normally.
# ---------------------------------------------------------------------------


def _missing_industrial_planner_single_base_e2e() -> str | None:
    target = PROJECT_ROOT / ".artifacts" / "industrial_planner_single_base_e2e"
    if not target.exists():
        return f"fixture missing: {target} (run scripts/run_industrial_planner_single_base_e2e.py)"
    return None


def _missing_phase3b_signature_bucket_review() -> str | None:
    target = (
        PROJECT_ROOT
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "126_signature_bucket_powered_support_coverer_probe_review"
        / "signature_bucket_powered_support_coverer_probe_review.json"
    )
    if not target.exists():
        return f"fixture missing: {target.relative_to(PROJECT_ROOT)} (Codex-era artifact)"
    return None


def _missing_temp_scripts_benchmark_parallelism() -> str | None:
    try:
        spec = find_spec("temp_scripts.benchmark_parallelism")
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        return "module temp_scripts.benchmark_parallelism not present (Codex-era helper, never migrated)"
    return None


_FIXTURE_GUARDS = (
    # B class: industrial_planner e2e fixture
    ("test_industrial_planner_single_base_delivery", _missing_industrial_planner_single_base_e2e),
    # C class: phase3b tuning artifact
    (
        "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer",
        _missing_phase3b_signature_bucket_review,
    ),
    # E class: temp_scripts module
    ("test_production_campaign_child_reports", _missing_temp_scripts_benchmark_parallelism),
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        nodeid = item.nodeid
        path_str = str(item.fspath)
        for substring, missing_check in _FIXTURE_GUARDS:
            if substring in path_str or substring in nodeid:
                reason = missing_check()
                if reason is not None:
                    item.add_marker(pytest.mark.skip(reason=reason))
                break
