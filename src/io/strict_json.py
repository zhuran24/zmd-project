"""Strict JSON helpers for proof-surface artifacts.

The standard library JSON decoder accepts duplicate object keys via last-write-wins
and accepts non-finite constants (NaN/Infinity).  Both are unsafe for generated or
consumed artifacts whose meaning is defined by exact source files.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _parse_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def loads_strict_json(text: str) -> Any:
    """Decode JSON while rejecting duplicate keys and non-finite values."""

    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
        parse_float=_parse_json_float,
    )


def load_strict_json(path: Path | str) -> Any:
    """Read and strictly decode a JSON file."""

    return loads_strict_json(Path(path).read_text(encoding="utf-8"))
