"""Unit tests for the dispatch backend-conversation reducer (GPT_DISPATCH_BACKEND_READ).

``_reduce_backend_assistant`` turns the slim ``/backend-api/conversation`` payload into
the same ``{count, text, slug}`` shape ``_last_assistant`` returns from the DOM, so the
env-gated backend-read collect path can fail-safe fall back to DOM parsing.  The backend
read exists because background/inactive tabs freeze DOM rendering under concurrent
collect (chatgpt-throttled-tab-render); the backend JSON keeps the full reply regardless.
These tests pin the pure reduction (visible-text-replies only, last-by-create_time, parts
join, slug, defensive empties) without needing a live browser.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DISPATCH_DIR = (
    Path(__file__).resolve().parents[2] / "cc_context" / "review" / "gpt_dispatch"
)
if str(_DISPATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_DISPATCH_DIR))

from dispatch_gpt_task import _reduce_backend_assistant  # noqa: E402


def _asst(create_time, parts, slug="", content_type="text"):
    return {
        "role": "assistant",
        "create_time": create_time,
        "content_type": content_type,
        "parts": parts,
        "slug": slug,
    }


def test_picks_last_text_reply_by_create_time_and_joins_parts() -> None:
    payload = {
        "ok": True,
        "nodes": [
            {"role": "user", "create_time": 1.0, "content_type": "text", "parts": ["q"], "slug": ""},
            _asst(2.0, ["first"], "gpt-5-5-pro"),
            _asst(5.0, ["line A", "line B"], "gpt-5-5-pro"),
            _asst(3.0, ["middle"], "gpt-5-5-pro"),
        ],
    }
    out = _reduce_backend_assistant(payload)
    assert out["count"] == 3
    assert out["text"] == "line A\nline B"
    assert out["slug"] == "gpt-5-5-pro"


def test_unordered_create_time_still_picks_latest() -> None:
    payload = {"ok": True, "nodes": [_asst(9.0, ["latest"], "s9"), _asst(1.0, ["oldest"], "s1")]}
    out = _reduce_backend_assistant(payload)
    assert out["text"] == "latest"
    assert out["slug"] == "s9"


def test_trailing_reasoning_node_is_ignored() -> None:
    # A reasoning/thoughts node can arrive AFTER the visible reply with a larger
    # create_time; it must not be picked as "the last reply" nor inflate the count.
    payload = {
        "ok": True,
        "nodes": [
            _asst(2.0, ["the visible answer"], "gpt-5-5-pro"),
            _asst(9.0, ["internal chain of thought"], "gpt-5-5-pro", content_type="thoughts"),
        ],
    }
    out = _reduce_backend_assistant(payload)
    assert out["count"] == 1
    assert out["text"] == "the visible answer"


def test_non_string_parts_are_filtered() -> None:
    # Generated-image asset pointers and other non-string parts must not corrupt the text.
    payload = {"ok": True, "nodes": [_asst(1.0, ["text", {"asset_pointer": "x"}, 42, "more"])]}
    out = _reduce_backend_assistant(payload)
    assert out["text"] == "text\nmore"
    assert out["count"] == 1


def test_not_ok_payload_returns_empty() -> None:
    empty = {"count": 0, "text": "", "slug": ""}
    assert _reduce_backend_assistant({"ok": False, "status": 403}) == empty
    assert _reduce_backend_assistant({}) == empty
    assert _reduce_backend_assistant(None) == empty  # type: ignore[arg-type]


def test_no_text_reply_returns_empty() -> None:
    payload = {
        "ok": True,
        "nodes": [
            {"role": "user", "create_time": 1.0, "content_type": "text", "parts": ["q"], "slug": ""},
            _asst(2.0, ["only reasoning"], "s", content_type="thoughts"),
        ],
    }
    assert _reduce_backend_assistant(payload) == {"count": 0, "text": "", "slug": ""}


def test_missing_create_time_treated_as_zero() -> None:
    payload = {
        "ok": True,
        "nodes": [
            {"role": "assistant", "content_type": "text", "parts": ["no time"], "slug": "a"},
            _asst(4.0, ["has time"], "b"),
        ],
    }
    out = _reduce_backend_assistant(payload)
    assert out["text"] == "has time"
    assert out["slug"] == "b"
