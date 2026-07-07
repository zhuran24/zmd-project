#!/usr/bin/env python3
"""Production supervisor certify entrypoint — PR2 #7 "last wiring".

Drives an already-committed ``CANDIDATE_PROPOSED`` proposal (produced by a normal
``certified_exact`` solve, which writes the ``*.proposal_ready.json`` marker)
through the *independent* supervisor path so a durable, campaign-level
``CERTIFIED`` checkpoint is minted by ``ExactCampaign.supervisor_seal()``.

This is the machine-condition entry that ``PROJECT_LOCK.md`` §1C (C5) records as
missing: "受支持的生产命令/launcher 必须从 proposal-ready marker 驱动独立
supervisor;当前仓库尚无该入口". A normal ``main.py`` completion stops at
``CANDIDATE_PROPOSED`` and must NOT be treated as a seal.

HARD BOUNDARIES (do not relax — enforced by PROJECT_LOCK + close-kernel + tests):
  * It only satisfies the "supervisor executable entry" machine condition. It
    does **not** publish public delivery artifacts and does **not** touch the
    P1.2 owner manual gate.
  * A successful seal only makes the *campaign checkpoint* durably ``CERTIFIED``.
    Public delivery (``final_solution.json`` / ``optimal_blueprint.json`` /
    ``certified_delivery_manifest.json``) is governed by
    ``resolve_p1_2_publish_open_gate()`` against the authoritative owner gate
    file. A seal here is **never** the owner close action and **never**
    authorizes publishing by itself.
  * It calls ``ExactCampaign.supervisor_seal()`` with **no** caller-supplied
    authority args (no proposal bytes, marker path, campaign_instance_id, or
    dependency-floor overrides). All proof re-verification runs inside the
    isolated L0 child; the checkpoint is written atomically by the L0 parent.
  * Any missing / mismatched / non-``CANDIDATE_PROPOSED`` state fails closed
    (non-zero exit) and leaves the proposal untouched. It never falls back to
    ``mark_campaign_stopped(..., "CERTIFIED")`` or writes a forged terminal
    checkpoint (both are hard-blocked by anti-bypass guards anyway).

Exit codes: 0 = sealed to durable campaign CERTIFIED; 1 = supervisor_seal ran
but rejected (proposal preserved); 2 = precondition missing (no proposal to
seal).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_EXIT_SEALED = 0
_EXIT_SEAL_REJECTED = 1
_EXIT_PRECONDITION_MISSING = 2


def _parse_args(argv: "list[str] | None") -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_supervisor_seal",
        description=(
            "Independent production supervisor: seal an already-committed "
            "CANDIDATE_PROPOSED proposal into a durable campaign-level CERTIFIED "
            "checkpoint via ExactCampaign.supervisor_seal(). Does NOT publish and "
            "does NOT open the P1.2 owner gate."
        ),
    )
    parser.add_argument(
        "--project-root",
        default=str(_REPO_ROOT),
        help="Project root containing data/checkpoints (default: repository root).",
    )
    # Deliberately NO --marker-path / --campaign-instance-id / --proposal-bytes
    # overrides: the marker and instance id are derived from and re-verified
    # against the on-disk checkpoint by supervisor_seal()/L0.
    return parser.parse_args(argv)


def main(argv: "list[str] | None" = None) -> int:
    args = _parse_args(argv)
    project_root = Path(args.project_root).resolve()

    from src.search.exact_campaign import (
        CANDIDATE_PROPOSED_STATUS,
        DEFAULT_CAMPAIGN_FILENAME,
        ExactCampaign,
        SUPERVISOR_PROPOSAL_STATE_KEY,
        proposal_ready_marker_path_for_campaign,
    )

    campaign_path = project_root / "data" / "checkpoints" / DEFAULT_CAMPAIGN_FILENAME
    marker_path = proposal_ready_marker_path_for_campaign(campaign_path)

    # Precondition existence check up front, for a clear operator message. The
    # authoritative binding (marker <-> checkpoint sha, run_id, instance_id) is
    # still re-verified inside supervisor_seal()/L0 regardless.
    if not campaign_path.is_file():
        print(
            f"precondition_missing: no campaign checkpoint at {campaign_path}; "
            "run a certified_exact solve to produce a CANDIDATE_PROPOSED proposal first",
            file=sys.stderr,
        )
        return _EXIT_PRECONDITION_MISSING
    if not marker_path.is_file():
        print(
            f"precondition_missing: no proposal-ready marker at {marker_path}; "
            "the checkpoint is not an independently sealable proposal",
            file=sys.stderr,
        )
        return _EXIT_PRECONDITION_MISSING

    # resume=True: load the existing proposal; never resume=False (that would
    # reset the checkpoint and unlink the marker). A forged/invalid proposal is
    # demoted here (proposal state cleared + marker unlinked), which the
    # CANDIDATE_PROPOSED assertion below then catches as fail-closed.
    campaign = ExactCampaign.load_or_create(project_root, resume=True)

    final_status = campaign.state.get("final_status")
    if final_status != CANDIDATE_PROPOSED_STATUS:
        print(
            "precondition_missing: campaign is not CANDIDATE_PROPOSED "
            f"(final_status={final_status!r}); nothing independently sealable "
            "(already sealed, demoted, or not a proposal)",
            file=sys.stderr,
        )
        return _EXIT_PRECONDITION_MISSING
    if SUPERVISOR_PROPOSAL_STATE_KEY not in campaign.state:
        print(
            "precondition_missing: checkpoint has no supervisor_proposal record; "
            "not a producer-committed proposal",
            file=sys.stderr,
        )
        return _EXIT_PRECONDITION_MISSING

    try:
        campaign.supervisor_seal()
    except Exception as exc:  # noqa: BLE001 — report and fail closed; proposal preserved
        print(
            f"supervisor_seal_rejected: {type(exc).__name__}: {exc}\n"
            "  the proposal checkpoint is preserved (CANDIDATE_PROPOSED); "
            "re-produce the proposal if inputs changed",
            file=sys.stderr,
        )
        return _EXIT_SEAL_REJECTED

    print("supervisor_seal_ok: campaign minted a durable CERTIFIED checkpoint")
    print(f"  campaign_path = {campaign_path}")
    print(f"  final_status  = {campaign.state.get('final_status')}")
    print(
        "  NOTE: this is a campaign-level CERTIFIED checkpoint ONLY. It is NOT "
        "an owner gate action and does NOT publish any public delivery surface. "
        "Public delivery is governed by the P1.2 owner manual gate "
        "(resolve_p1_2_publish_open_gate) against "
        "data/review_gates/phase_1_2_spike_close.json; only an explicit owner "
        "decision recorded there authorizes publication."
    )
    return _EXIT_SEALED


if __name__ == "__main__":
    raise SystemExit(main())
