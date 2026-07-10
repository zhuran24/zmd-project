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
    # After 2026-05-16 phase3b reorganization tests live under
    # src/tests/phase3b/checkpoint_free/signature_bucket/powered_support_coverer/
    # so the original substring `test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer`
    # no longer appears contiguously in path/nodeid. Match the cluster path component instead.
    (
        "signature_bucket/powered_support_coverer",
        _missing_phase3b_signature_bucket_review,
    ),
    # E class: temp_scripts module
    ("test_production_campaign_child_reports", _missing_temp_scripts_benchmark_parallelism),
)


# ---------------------------------------------------------------------------
# Heavyweight (slow) test registry (2026-06-21)
#
# The fast gate must stay seconds-fast so a failing test surfaces immediately
# instead of being masked by a multi-minute integration suite hitting a global
# timeout. Tests whose `call` phase runs >= 8s (measured from a full-suite
# --durations sweep) are tagged `slow` so the fast gate can drop them with
# `-m "not slow"` while the full suite still runs them.
#
# The set is kept here, in one place, as exact `module.py::test_name` nodeid
# suffixes (no parametrization in this batch). Marking is additive: a test that
# already carries @pytest.mark.xfail still gets @slow stacked on top. To retune,
# rerun `pytest src/tests --durations=80` and edit this set; nothing else changes.
# ---------------------------------------------------------------------------

_SLOW_TEST_NODEIDS: frozenset[str] = frozenset(
    {
        # >= 8s call-time heavyweight solver / integration tests.
        # Retuned 2026-07-04 from a serial full slow-lane --durations sweep
        # (no concurrent pytest): entries measured < 8s were dropped
        # (11x inspector 4-7s, 7x delivery_manifest 1-2s, b5a summary 3s,
        # v86/v89 precheck-only ~1s, v97 ~1s) along with two stale nodeids
        # that no longer collect. v98 stays: its call is sub-second but the
        # golden-surface fixture setup alone is ~23s.
        "test_regression.py::test_aspect_ratio_sliced_search_cannot_claim_terminal_certified",
        "test_exact_contract.py::test_certified_result_writes_canonical_optimal_blueprint",
        "test_exact_contract.py::test_toy_project_can_be_truly_certified",
        "test_exact_contract.py::test_outer_search_safe_area_upper_bound_accounts_for_fixed_required_protocol_storage_box",
        "test_regression.py::test_exact_optional_cardinality_bounds_align_with_preprocessed_artifacts",
        "test_regression.py::test_c1_default_build_shape_with_preprocessed_artifacts",
        "test_v82_oriented_candidate_domain.py::test_full_frontier_candidate_domain_keeps_oriented_dimensions",
        "test_regression.py::test_parallel_outer_search_matches_serial_on_controlled_small_frontier",
        "test_routing.py::test_routing_small_solve",
        "test_routing.py::test_routing_solver_worker_override_changes_only_solver_parameter",
        "test_parallel_scheduler.py::test_parallel_and_serial_exact_candidate_results_match_on_toy_frontier",
        "test_p1_2_sink_replay_authority.py::test_p1_2_legitimate_certified_exact_path_survives_all_sink_replays",
        "test_v98_b5a_symlink_campaign_path_authority.py::test_v98_b5a_preserves_symlink_campaign_path_until_surface_verifier",
        "test_parallel_scheduler.py::test_parallel_wave_keeps_best_certified_result_under_out_of_order_completion",
        "test_v62_candidate_frontier_contract.py::test_v65_terminal_result_is_committed_before_final_solution_export",
        "test_industrial_planner_full_demand_support_suite_inventory.py::test_support_suite_inventory_cli_detects_drift",
        "test_v62_candidate_frontier_contract.py::test_v66_terminal_export_failure_clears_terminal_state_and_artifacts",
        "test_regression.py::test_frontier_resume_reconstructs_same_next_selected_candidate",
        "test_industrial_planner_checked_artifact_suite.py::test_checked_artifact_suite_cli_exits_nonzero_on_component_drift",
        # v88 exercises the real ④b isolated replay (fresh -I subprocess
        # re-solve, ~10s). Its siblings v86/v89 monkeypatch the authority
        # validator away (precheck-only, ~1s) and left the slow set in the
        # 2026-07-04 retune.
        "test_v88_terminal_ghost_anchor_required.py::test_terminal_solution_match_ignores_candidate_record_ghost_marker",
        # P1 backlog #1 redlines: real L0 supervisor child/seal semantics.
        "test_p1_min_tcb_closure_redlines.py::test_golden_toy_supervisor_seal_semantic_digests",
        "test_p1_min_tcb_closure_redlines.py::test_malicious_fixture_fail_closed",
        "test_p1_min_tcb_closure_redlines.py::test_target_l0_child_runtime_excludes_scripts_from_snapshot",
        "test_p1_min_tcb_closure_redlines.py::test_target_l0_snapshot_manifest_is_explicit_minimal_whitelist",
    }
)


def _nodeid_matches_slow(nodeid: str) -> bool:
    """Match a collected nodeid against the slow registry.

    Registry entries are stored as `module.py::test_name` suffixes so they are
    independent of the `src/tests/...` (and phase3b subdir) path prefix pytest
    prepends. A suffix match on `::module.py::...` (or the whole nodeid for a
    top-level module) keeps the comparison anchored to a file boundary.
    """

    base = nodeid.split("[", 1)[0]
    for entry in _SLOW_TEST_NODEIDS:
        if base == entry or base.endswith("/" + entry) or base.endswith("::" + entry):
            return True
    return False


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
        if _nodeid_matches_slow(nodeid):
            item.add_marker(pytest.mark.slow)


# ---------------------------------------------------------------------------
# Centralized module-level cache reset (GPT v4 P1 #4 fix)
#
# master_model.py 有 6 个 module-level mutable cache 是性能优化（跨 instance
# 复用 power capacity 计算）, 但破坏测试 hermeticity — 顺序前跑的测试可能
# populate cache → 假定 "fresh stats == 0" 的回归测试在随机顺序下 flake.
# b4c2a03 是单点清, 但 GPT v4 指出根治应该是全套自动隔离.
#
# 本 autouse fixture 在每个测试 setup 时清掉 6 个 cache, 让任何 build()
# 拿到的 stats 都是 from-scratch. 性能影响: 每个 test ~ 0.01s init cost.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_master_model_module_caches():
    """Clear master_model module-level caches before each test to ensure hermeticity.

    只对**已 import 过** master_model 的会话生效 — 不主动 import, 避免对纯
    adapter / IP / surface 类测试引入 master_model 副作用.
    """
    _mm = sys.modules.get("src.models.master_model")
    if _mm is None:
        yield
        return
    _cache_names = (
        "_LOCAL_POWER_CAPACITY_CACHE",
        "_LOCAL_POWER_CAPACITY_COMPACT_CACHE",
        "_LOCAL_POWER_CAPACITY_NORMALIZED_RECT_CACHE",
        "_LOCAL_POWER_CAPACITY_RECT_DP_CACHE",
        "_LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE",
        "_LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE",
    )
    for name in _cache_names:
        cache = getattr(_mm, name, None)
        if cache is not None and hasattr(cache, "clear"):
            cache.clear()
    yield
