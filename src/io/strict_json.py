"""Strict JSON helpers for proof-surface artifacts.

The standard library JSON decoder accepts duplicate object keys via last-write-wins
and accepts non-finite constants (NaN/Infinity).  Both are unsafe for generated or
consumed artifacts whose meaning is defined by exact source files.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
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


def _parse_json_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - json has already tokenized the number.
        raise ValueError(f"invalid JSON number: {value}") from exc
    try:
        float_value = float(parsed)
    except OverflowError as exc:
        raise ValueError(f"non-finite JSON number: {value}") from exc
    if not parsed.is_finite() or not math.isfinite(float_value):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def loads_strict_json(text: str, *, exact_decimal: bool = False) -> Any:
    """Decode JSON while rejecting duplicate keys and non-finite values.

    Args:
        text: JSON source text.
        exact_decimal: When true, parse JSON floating-point tokens as ``Decimal``
            so downstream exact-rational code can consume the original decimal
            lexeme instead of a binary float approximation.  The default remains
            the historical float-parsing behavior.
    """

    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
        parse_float=_parse_json_decimal if exact_decimal else _parse_json_float,
    )


def load_strict_json(path: Path | str, *, exact_decimal: bool = False) -> Any:
    """Read and strictly decode a JSON file."""

    return loads_strict_json(Path(path).read_text(encoding="utf-8"), exact_decimal=exact_decimal)


def load_strict_json_exact_decimal(path: Path | str) -> Any:
    """Read strict JSON while preserving floating-point source tokens as Decimal."""

    return load_strict_json(path, exact_decimal=True)
