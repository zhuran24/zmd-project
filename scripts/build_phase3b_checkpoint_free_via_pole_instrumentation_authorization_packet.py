from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_SPEC = (
    ARTIFACT_ROOT
    / "31_via_pole_shape_instrumentation_patch_spec"
    / "via_pole_shape_instrumentation_patch_spec.json"
)
DEFAULT_NEXT_DECISION = (
    ARTIFACT_ROOT / "09_checkpoint_free_scoreboard" / "checkpoint_free_next_decision.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "32_via_pole_instrumentation_authorization_packet"

from src.runtime.sensitive_path_audit import (  # noqa: E402
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    packet = build_via_pole_instrumentation_authorization_packet(
        spec_path=_resolve_path(PROJECT_ROOT, args.spec),
        next_decision_path=_resolve_path(PROJECT_ROOT, args.next_decision),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b via-pole instrumentation authorization packet")
    print(f"status={packet['status']}")
    print(f"authorization_required={packet['authorization']['authorization_required']}")
    print(f"implementation_allowed_now={packet['authorization']['implementation_allowed_now']}")
    if not args.no_write:
        print(f"packet_json={_display_path(PROJECT_ROOT, Path(packet['packet_path']))}")
    return 0 if packet["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a review/authorization packet for the via-pole instrumentation source patch."
    )
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--next-decision", type=Path, default=DEFAULT_NEXT_DECISION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_via_pole_instrumentation_authorization_packet(
    *,
    spec_path: Path,
    next_decision_path: Path,
    output_dir: Path,
    no_write: bool = False,
) -> dict[str, Any]:
    output_dir = _resolve_path(PROJECT_ROOT, output_dir)
    _assert_packet_namespace(output_dir)
    spec_path = _resolve_path(PROJECT_ROOT, spec_path)
    next_decision_path = _resolve_path(PROJECT_ROOT, next_decision_path)
    spec = _load_json(spec_path)
    next_decision = _load_json(next_decision_path) if next_decision_path.exists() else {}
    before = build_sensitive_path_fingerprint(PROJECT_ROOT)
    spec_interpretation = _mapping(spec.get("interpretation"))
    spec_patch = _mapping(spec.get("patch_spec"))
    recommendation = _mapping(spec.get("recommendation"))
    ready = (
        spec_interpretation.get("classification") == "patch_spec_ready_source_mutation_still_blocked"
        and spec_interpretation.get("implementation_allowed_now") is False
        and spec_interpretation.get("source_mutation_authorized_by_this_artifact") is False
        and spec.get("source_mutation_performed") is False
        and recommendation.get("action")
        == "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
    )
    after = build_sensitive_path_fingerprint(PROJECT_ROOT)
    sensitive_comparison = compare_sensitive_path_fingerprints(before, after)
    status = "completed" if ready and not sensitive_comparison.get("changed") else "blocked"
    packet = {
        "schema": "phase3b-via-pole-instrumentation-authorization-packet/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "packet_kind": "source_patch_authorization_readiness_only",
        "project_root": str(PROJECT_ROOT),
        "spec_path": str(spec_path),
        "next_decision_path": str(next_decision_path),
        "output_dir": str(output_dir),
        "packet_path": str(output_dir / "via_pole_instrumentation_authorization_packet.json"),
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "authorization": {
            "authorization_required": True,
            "implementation_allowed_now": False,
            "authorization_source": "human_user_or_external_review_required",
            "current_next_decision_action": _mapping(next_decision.get("recommendation")).get("action"),
            "current_next_decision_global_block_reason": _mapping(
                next_decision.get("recommendation")
            ).get("global_block_reason"),
            "proposed_authorization_text": _authorization_text(spec_patch),
        },
        "patch_scope": {
            "target_file": spec_patch.get("target_file"),
            "target_method": spec_patch.get("target_method"),
            "env_var": spec_patch.get("env_var"),
            "default_behavior": spec_patch.get("default_behavior"),
            "diagnostic_behavior": spec_patch.get("diagnostic_behavior"),
            "non_goals": list(spec_patch.get("non_goals", []) or []),
        },
        "validation_plan": list(spec.get("validation_plan", []) or []),
        "blocked_actions": list(recommendation.get("blocked_actions", []) or []),
        "sensitive_path_comparison": sensitive_comparison,
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output_dir / "sensitive_path_before.json", before)
        atomic_write_json(output_dir / "sensitive_path_after.json", after)
        atomic_write_json(output_dir / "sensitive_path_comparison.json", sensitive_comparison)
        atomic_write_json(output_dir / "via_pole_instrumentation_authorization_packet.json", packet)
        (output_dir / "via_pole_instrumentation_authorization_packet.md").write_text(
            render_via_pole_instrumentation_authorization_packet_markdown(packet),
            encoding="utf-8",
        )
    return packet


def render_via_pole_instrumentation_authorization_packet_markdown(packet: Mapping[str, Any]) -> str:
    authorization = _mapping(packet.get("authorization"))
    scope = _mapping(packet.get("patch_scope"))
    lines = [
        "# Phase3B Via-Pole Instrumentation Authorization Packet",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Authorization required: `{authorization.get('authorization_required')}`",
        f"- Implementation allowed now: `{authorization.get('implementation_allowed_now')}`",
        f"- Current next decision: `{authorization.get('current_next_decision_action')}`",
        f"- Global block reason: `{authorization.get('current_next_decision_global_block_reason')}`",
        "- Source mutation performed: `false`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Proposed Authorization Text",
        "",
        "```text",
        str(authorization.get("proposed_authorization_text") or ""),
        "```",
        "",
        "## Patch Scope",
        "",
        f"- Target file: `{scope.get('target_file')}`",
        f"- Target method: `{scope.get('target_method')}`",
        f"- Env var: `{scope.get('env_var')}`",
        f"- Default behavior: `{scope.get('default_behavior')}`",
        f"- Diagnostic behavior: `{scope.get('diagnostic_behavior')}`",
        "",
        "## Validation Plan",
        "",
    ]
    for item in list(packet.get("validation_plan", []) or []):
        lines.append(f"- `{item.get('id')}`: {item.get('check')}")
    lines.extend(
        [
            "",
            "This packet does not authorize or perform source mutation. It only makes the authorization boundary explicit and reviewable.",
            "",
        ]
    )
    return "\n".join(lines)


def _authorization_text(patch: Mapping[str, Any]) -> str:
    return (
        "I explicitly authorize Codex to implement the default-off via-pole shape "
        "instrumentation patch described by "
        ".artifacts/phase3b_local_13900ks_tuning_20260430/"
        "31_via_pole_shape_instrumentation_patch_spec/"
        "via_pole_shape_instrumentation_patch_spec.json. Scope is limited to "
        f"{patch.get('target_file')}::{patch.get('target_method')} and focused tests. "
        f"The new env var {patch.get('env_var')} must default to disabled and must not change "
        "production behavior when unset. This does not authorize final 168h runs, true "
        "production long runs, canonical checkpoint write/import/backfill, runtime "
        "elimination, proof/preflight/release/viewer/frontdoor mutation, or production "
        "default changes."
    )


def _assert_packet_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "32_via_pole_instrumentation_authorization_packet" not in normalized
    ):
        raise ValueError(f"Refusing to write outside via-pole instrumentation authorization packet namespace: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
