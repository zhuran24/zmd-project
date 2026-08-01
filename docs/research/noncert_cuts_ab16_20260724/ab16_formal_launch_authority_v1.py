#!/usr/bin/env python3
"""Pure canonical renderer for owner-side AB16 formal launch artifacts.

The renderer has no publication, lock, unit, controller, baseline, or solver
capability.  An external owner-side actor must independently replay the
campaign, invoke this pinned renderer, validate the resulting bytes with
``ab16_formal_launch_validator_v1``, and perform the canonical O_EXCL/0444/
fsync/same-byte-readback publication.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
from pathlib import Path
import sys
from typing import Any

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import ab16_formal_launch_validator_v1 as validator


class FormalLaunchRenderError(RuntimeError):
    """A draft could not be rendered as one closed launch artifact."""


def render_admission(
    record: Mapping[str, object],
    *,
    expected_context: Mapping[str, object],
) -> bytes:
    """Return canonical admission bytes without publishing them."""

    try:
        checked = validator.validate_admission(record, expected_context=expected_context)
        return authority.canonical_json(checked)
    except Exception as exc:
        raise FormalLaunchRenderError(f"formal admission rendering failed: {exc}") from exc


def render_selection(
    record: Mapping[str, object],
    *,
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    guardian_ready: Mapping[str, object],
    guardian_ready_identity: Mapping[str, object],
    attempt_consumption: Mapping[str, object],
    attempt_consumption_identity: Mapping[str, object],
    expected_context: Mapping[str, object],
) -> bytes:
    """Return canonical selection bytes without publishing them."""

    try:
        checked = validator.validate_selection(
            record,
            admission=admission,
            admission_identity=admission_identity,
            guardian_ready=guardian_ready,
            guardian_ready_identity=guardian_ready_identity,
            attempt_consumption=attempt_consumption,
            attempt_consumption_identity=attempt_consumption_identity,
            expected_context=expected_context,
        )
        return authority.canonical_json(checked)
    except Exception as exc:
        raise FormalLaunchRenderError(f"formal selection rendering failed: {exc}") from exc


def _record(
    path: Path | str,
    label: str,
    *,
    require_published: bool = True,
) -> tuple[dict[str, Any], dict[str, object]]:
    return validator.read_canonical_record(
        path,
        expected_identity=None,
        label=label,
        require_published=require_published,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--kind", choices=("admission", "selection"), required=True)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--guardian-ready", type=Path)
    parser.add_argument("--attempt-consumption", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Render to stdout only; never create or replace an authority path."""

    args = _parser().parse_args(argv)
    try:
        context = validator.replay_formal_launch_context(authority, args.campaign_dir)
        draft, _draft_identity = _record(
            args.draft,
            "formal launch draft",
            require_published=False,
        )
        if args.kind == "admission":
            if any(value is not None for value in (args.admission, args.guardian_ready, args.attempt_consumption)):
                raise FormalLaunchRenderError("admission rendering received selection-only inputs")
            raw = render_admission(draft, expected_context=context)
        else:
            if args.admission is None or args.guardian_ready is None or args.attempt_consumption is None:
                raise FormalLaunchRenderError("selection rendering lacks prerequisite paths")
            admission, admission_identity = _record(args.admission, "formal launch admission")
            guardian, guardian_identity = _record(args.guardian_ready, "outer guardian ready")
            consumption, consumption_identity = _record(
                args.attempt_consumption,
                "formal attempt consumption",
            )
            raw = render_selection(
                draft,
                admission=admission,
                admission_identity=admission_identity,
                guardian_ready=guardian,
                guardian_ready_identity=guardian_identity,
                attempt_consumption=consumption,
                attempt_consumption_identity=consumption_identity,
                expected_context=context,
            )
    except Exception as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
