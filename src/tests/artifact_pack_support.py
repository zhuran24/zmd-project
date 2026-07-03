"""Shared accessors for large repository artifact packs used by tests."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.io.strict_json import loads_strict_json

REPO_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_PLACEMENTS_PATH = (
    REPO_ROOT / "data" / "preprocessed" / "candidate_placements.json"
)

_candidate_placements_text_cache: str | None = None
_candidate_placements_payload_cache: Dict[str, Any] | None = None


def get_repo_candidate_placements_text() -> str:
    """Return the repository candidate_placements.json text."""

    global _candidate_placements_text_cache
    if _candidate_placements_text_cache is None:
        _candidate_placements_text_cache = CANDIDATE_PLACEMENTS_PATH.read_text(
            encoding="utf-8"
        )
    return _candidate_placements_text_cache


def _repo_candidate_placements_payload() -> Dict[str, Any]:
    global _candidate_placements_payload_cache
    if _candidate_placements_payload_cache is None:
        payload = loads_strict_json(get_repo_candidate_placements_text())
        if not isinstance(payload, dict):
            raise TypeError("candidate_placements.json must be a JSON object")
        _candidate_placements_payload_cache = payload
    return _candidate_placements_payload_cache


def get_repo_candidate_placements_payload() -> Dict[str, Any]:
    """Return a deep-copied strict-loaded candidate placements payload."""

    return copy.deepcopy(_repo_candidate_placements_payload())


def get_repo_candidate_placements_payload_readonly() -> Dict[str, Any]:
    """Return the cached payload for read-only test consumers; do not mutate it."""

    return _repo_candidate_placements_payload()


def get_repo_facility_pools() -> Dict[str, List[Dict[str, Any]]]:
    """Return a deep-copied facility_pools mapping from the shared payload cache."""

    payload = _repo_candidate_placements_payload()
    pools = payload["facility_pools"]
    if not isinstance(pools, dict):
        raise TypeError("candidate_placements.json facility_pools must be an object")
    return copy.deepcopy(pools)


def get_repo_facility_pools_readonly() -> Dict[str, List[Dict[str, Any]]]:
    """Return cached facility_pools for read-only test consumers; do not mutate it."""

    payload = _repo_candidate_placements_payload()
    pools = payload["facility_pools"]
    if not isinstance(pools, dict):
        raise TypeError("candidate_placements.json facility_pools must be an object")
    return pools


def load_project_instances_and_rules(
    project_root: Path,
    solve_mode: str = "certified_exact",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load project instances and canonical rules without placement pools.

    Test-only light loader: instances/rules 逻辑测试不需要解析 45MB 的
    candidate_placements.json。刻意放在 src/tests/(而不是 master_model.py)——
    master_model.py 是 close-kernel sealed 文件,生产侧加任何函数都触发 reseal 连锁;
    真正依赖 facility_pools 的路径仍走生产 load_project_data 的三工件合同。
    """

    from src.models.master_model import (
        _load_all_facility_instances,
        _load_json,
        _load_mandatory_exact_instances,
        _normalize_solve_mode,
    )

    solve_mode = _normalize_solve_mode(solve_mode)
    data_dir = project_root / "data" / "preprocessed"

    if solve_mode == "certified_exact":
        instances = _load_mandatory_exact_instances(data_dir)
    else:
        instances = _load_all_facility_instances(data_dir)

    rules = dict(_load_json(project_root / "rules" / "canonical_rules.json"))
    return instances, rules
