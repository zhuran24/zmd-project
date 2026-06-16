"""Strict parsing helpers for CP-SAT solution hints.

Solution hints are search guidance only, but every public hint ingress should
share the same fail-closed type policy: only real ``int`` values are accepted.
In particular, ``bool`` is rejected even though it subclasses ``int`` in Python,
and floats / numeric strings are not truncated or coerced.
"""

from __future__ import annotations

from typing import Any, Optional


def parse_strict_int_hint_value(value: Any) -> Optional[int]:
    """Return ``value`` as int only when it is exactly an ``int`` instance."""

    if type(value) is int:
        return int(value)
    return None
