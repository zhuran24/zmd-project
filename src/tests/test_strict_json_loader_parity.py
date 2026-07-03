"""Parity: master/binding local JSON loaders match the shared strict loader.

Regression for the loader-parity gap. Before this, ``master_model`` and
``binding_subproblem`` each had a local ``json.loads``-based loader that lacked
the ``parse_float`` guard, so overflow literals like ``1e400`` (which Python's
``float()`` turns into ``inf``) were silently accepted — unlike the shared
strict loader in ``src.io.strict_json``. All three entrypoints must now reject
the same malformed inputs identically, and still accept valid finite JSON.
"""

from __future__ import annotations

import pytest

from src.io.strict_json import loads_strict_json
from src.models import binding_subproblem, master_model

_MALFORMED_JSON = [
    pytest.param('{"x": 1e400}', id="overflow-1e400"),
    pytest.param('{"x": NaN}', id="nan"),
    pytest.param('{"x": Infinity}', id="infinity"),
    pytest.param('{"x": -Infinity}', id="neg-infinity"),
    pytest.param('{"a": 1, "a": 2}', id="duplicate-key"),
]


@pytest.mark.parametrize("text", _MALFORMED_JSON)
def test_local_text_loaders_reject_like_shared_strict(text: str) -> None:
    """The shared strict loader and both local text entrypoints reject alike."""
    with pytest.raises(ValueError):
        loads_strict_json(text)
    with pytest.raises(ValueError):
        master_model._loads_strict_json(text)
    with pytest.raises(ValueError):
        binding_subproblem._loads_strict_json(text)


def test_local_file_loaders_reject_overflow(tmp_path) -> None:
    """The local file loaders reject overflow the same way (regression: 1e400)."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"x": 1e400}', encoding="utf-8")
    with pytest.raises(ValueError):
        master_model._load_json(bad)
    with pytest.raises(ValueError):
        binding_subproblem._load_strict_json(bad)


def test_local_loaders_accept_valid_finite_json() -> None:
    """Valid finite JSON stays accepted and equal across all three entrypoints."""
    text = '{"x": 1.5, "y": 100, "z": "ok"}'
    expected = {"x": 1.5, "y": 100, "z": "ok"}
    assert loads_strict_json(text) == expected
    assert master_model._loads_strict_json(text) == expected
    assert binding_subproblem._loads_strict_json(text) == expected
