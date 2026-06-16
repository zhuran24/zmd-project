"""Regression tests for strict-JSON exact-decimal parsing (F-BIND-R11-01).

The certified proof surface consumes recipe rates from ``canonical_rules.json`` /
``preprocess_plan.json`` through ``load_strict_json_exact_decimal`` so that decimal
source lexemes survive as exact ``Decimal`` values instead of binary-float
approximations.  Round-2 deferred F-BIND-R11-01 because ``strict_json`` still
collapsed every float token to a binary ``float``; round-3 landed the
``exact_decimal`` path.  These tests pin that behavior so it cannot silently
regress back to lossy binary parsing while keeping the duplicate-key and
non-finite rejections that the strict reader already guaranteed.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.io.strict_json import (
    load_strict_json,
    load_strict_json_exact_decimal,
    loads_strict_json,
)


def test_exact_decimal_preserves_source_lexeme_not_binary_float() -> None:
    # 0.1 has no exact binary-float representation. Exact-decimal parsing must
    # yield the source decimal value, not the binary expansion -- this is the
    # whole point of F-BIND-R11-01.
    payload = loads_strict_json('{"rate": 0.1}', exact_decimal=True)
    value = payload["rate"]
    assert isinstance(value, Decimal)
    assert value == Decimal("0.1")
    # Decimal(0.1) is 0.1000000000000000055..., the binary-float expansion the
    # exact path must NOT reproduce. If exact_decimal regressed to float parsing,
    # value would be a float and this discrimination would fail.
    assert value != Decimal(0.1)


def test_default_mode_returns_binary_float() -> None:
    payload = loads_strict_json('{"rate": 0.1}')
    value = payload["rate"]
    assert isinstance(value, float)
    assert value == 0.1


def test_exact_decimal_preserves_trailing_zero_scale() -> None:
    # A trailing-zero lexeme like 0.30 collapses under float() but Decimal keeps
    # the source scale, which matters for exact-rational downstream consumers.
    payload = loads_strict_json('{"rate": 0.30}', exact_decimal=True)
    assert payload["rate"] == Decimal("0.30")
    assert str(payload["rate"]) == "0.30"


@pytest.mark.parametrize("exact_decimal", [False, True])
def test_non_finite_constants_rejected_in_both_modes(exact_decimal: bool) -> None:
    for token in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ValueError, match="invalid JSON constant"):
            loads_strict_json(f'{{"rate": {token}}}', exact_decimal=exact_decimal)


@pytest.mark.parametrize("exact_decimal", [False, True])
def test_overflowing_number_token_rejected_in_both_modes(exact_decimal: bool) -> None:
    # 1e400 is a finite lexeme but overflows IEEE double -> non-finite. Both the
    # float path and the decimal path must reject it rather than admit inf.
    with pytest.raises(ValueError, match="non-finite JSON number"):
        loads_strict_json('{"rate": 1e400}', exact_decimal=exact_decimal)


@pytest.mark.parametrize("exact_decimal", [False, True])
def test_duplicate_keys_rejected_in_both_modes(exact_decimal: bool) -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        loads_strict_json('{"rate": 1, "rate": 2}', exact_decimal=exact_decimal)


def test_load_strict_json_exact_decimal_roundtrips_file(tmp_path) -> None:
    path = tmp_path / "rates.json"
    path.write_text('{"a": 0.1, "b": 1.05}', encoding="utf-8")
    payload = load_strict_json_exact_decimal(path)
    assert isinstance(payload["a"], Decimal)
    assert payload["a"] == Decimal("0.1")
    assert payload["b"] == Decimal("1.05")
    assert payload["a"] != Decimal(0.1)


def test_load_strict_json_default_mode_file_is_binary_float(tmp_path) -> None:
    path = tmp_path / "rates.json"
    path.write_text('{"a": 0.1}', encoding="utf-8")
    payload = load_strict_json(path)
    assert isinstance(payload["a"], float)
