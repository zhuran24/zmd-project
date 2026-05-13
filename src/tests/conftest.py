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
