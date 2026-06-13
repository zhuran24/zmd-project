"""Phase 3C P1 #7e prep — master hint 跨 wave 持久化的 IO 层。

ε-Certified 三阶段 168h split 需要把上一波 master 求出的解作为下一波
master 的初始 hint，让 search 不用从零重建。CP-SAT 公开的 API 是
`model.add_hint(var, value) + use_optimization_hints + repair_hint=True`。

本模块只做 IO（写 / 读 / 清理 hint json），不做模型集成。集成到
master_model.build() 是 P1 #7 主体阶段的事。

文件位置约定:
    {project_root}/data/checkpoints/master_hints/{candidate_key}.json

文件 schema:
    {
        "candidate_key": "70x70",
        "schema_version": 1,
        "saved_at": "2026-05-10T00:00:00Z",
        "var_values": {"<var_name>": <int_value>, ...}
    }

env 开关 (未来主体阶段使用):
    EXACT_MASTER_HINT_PERSISTENCE=1  启用读写
    默认 off (prep 阶段)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.models.solution_hint_parser import parse_strict_int_hint_value


HINT_PERSISTENCE_ENV = "EXACT_MASTER_HINT_PERSISTENCE"
HINT_DIR_NAME = "master_hints"
HINT_SCHEMA_VERSION = 1


def is_enabled() -> bool:
    """Whether hint persistence is opt-in via env."""
    return os.environ.get(
        HINT_PERSISTENCE_ENV, ""
    ).strip().lower() in {"1", "true", "yes", "on"}


def hint_dir(project_root: Path) -> Path:
    return Path(project_root) / "data" / "checkpoints" / HINT_DIR_NAME


def hint_path(project_root: Path, candidate_key: str) -> Path:
    safe_key = _sanitize_candidate_key(candidate_key)
    return hint_dir(project_root) / f"{safe_key}.json"


def _sanitize_candidate_key(key: str) -> str:
    """Reject path separators / special chars; fail loud on bad input."""
    if not isinstance(key, str) or not key:
        raise ValueError(f"candidate_key must be non-empty str, got {key!r}")
    if any(ch in key for ch in ("/", "\\", "..", "\0")):
        raise ValueError(f"candidate_key contains forbidden chars: {key!r}")
    return key


def write_master_hints(
    project_root: Path,
    candidate_key: str,
    var_values: Mapping[str, int],
) -> Path:
    """Write {var_name: int_value} dict to disk for the given candidate.

    Atomic write via tmp file + os.replace. Overwrites existing hint.
    """
    target = hint_path(project_root, candidate_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized_var_values: Dict[str, int] = {}
    for key, value in var_values.items():
        parsed_value = parse_strict_int_hint_value(value)
        if parsed_value is None:
            raise TypeError(
                "master hint value for "
                f"{key!r} must be exactly int, got {type(value).__name__}"
            )
        normalized_var_values[str(key)] = int(parsed_value)
    payload: Dict[str, Any] = {
        "candidate_key": candidate_key,
        "schema_version": HINT_SCHEMA_VERSION,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "var_values": normalized_var_values,
    }
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)
    return target


def load_master_hints(
    project_root: Path,
    candidate_key: str,
) -> Optional[Dict[str, int]]:
    """Load var_values dict from disk; None if file missing/invalid.

    Defensive: any read/parse failure returns None rather than raising —
    a bad hint file should not break the campaign, just lose the hint.
    """
    path = hint_path(project_root, candidate_key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("schema_version", -1)) != HINT_SCHEMA_VERSION:
        return None
    var_values = payload.get("var_values")
    if not isinstance(var_values, dict):
        return None
    normalized_var_values: Dict[str, int] = {}
    for key, value in var_values.items():
        parsed_value = parse_strict_int_hint_value(value)
        if parsed_value is None:
            return None
        normalized_var_values[str(key)] = int(parsed_value)
    return normalized_var_values


def clear_master_hints(project_root: Path, candidate_key: str) -> bool:
    """Remove hint file for the given candidate. Returns True if removed."""
    path = hint_path(project_root, candidate_key)
    if not path.exists():
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False
