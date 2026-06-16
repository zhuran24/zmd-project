from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterator, Mapping, MutableMapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase3b.checkpoint_free.master.build_proto_inventory import _model_inventory  # noqa: E402
from src.models.master_model import MasterPlacementModel  # noqa: E402
from src.runtime.sensitive_path_audit import (  # noqa: E402
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)
from src.runtime.phase3b_artifact_guards import (  # noqa: E402
    resolve_artifact_namespace,
    safe_child_artifact_dir,
    validate_artifact_run_id,
)
from src.search.benders_loop import (  # noqa: E402
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    create_exact_search_session,
    evaluate_exact_candidate_pre_master_precheck,
)
from src.search.exact_campaign import atomic_write_json, now_iso  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_STRATEGY = ARTIFACT_ROOT / "35_overlay_timing_strategy" / "overlay_timing_strategy.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "35_overlay_timing_strategy"
DEFAULT_RUN_ID = "local_hotspot_42x32_overlay_timing_probe_001"
OVERLAY_TIMING_NAMESPACE = "35_overlay_timing_strategy"
ALLOWED_OVERLAY_TIMING_RUN_IDS = frozenset(
    {
        "local_hotspot_42x32_overlay_timing_probe_001",
        "local_hotspot_42x32_overlay_timing_probe_plan_001",
        "local_hotspot_42x32_signature_bucket_compact_item_batched_counter_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_compact_item_detail_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_compact_item_opt_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_fallback_reason_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_model_shell_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_outer_overlay_subphase_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_payload_footprint_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_port_profile_cache_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_powered_support_coverer_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_region_counting_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_residual_overlay_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_template_footprint_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_template_footprint_support_gap_inst_no_solve_001",
        "local_hotspot_42x32_signature_bucket_visibility_inst_no_solve_001",
    }
)

SessionFactory = Callable[..., Any]
PrecheckFactory = Callable[..., Mapping[str, Any]]
ModelFactory = Callable[..., Any]

FORBIDDEN_ARG_EXACT = {
    "--resume-campaign",
    "--import-checkpoint",
    "--write-checkpoint",
    "--checkpoint-output",
    "--checkpoint-dir",
    "--proof-source",
    "--release",
    "--viewer",
    "--frontdoor",
    "--preflight",
}
FORBIDDEN_ARG_TEXT = ("168h",)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _guard_forbidden_cli_args(argv)
    args = _parse_args(argv)
    payload = build_or_run_overlay_timing_probe(
        project_root=PROJECT_ROOT,
        strategy_path=_resolve_path(PROJECT_ROOT, args.strategy),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        candidate_key=str(args.candidate_key),
        execute_no_solve=bool(args.execute_no_solve),
        no_write=bool(args.no_write),
    )
    print("phase3b checkpoint-free overlay timing probe")
    print(f"status={payload['status']}")
    print(f"execute_no_solve={payload['execute_no_solve']}")
    print(f"candidate_key={payload['target']['candidate_key']}")
    print(f"artifact_dir={_display_path(PROJECT_ROOT, Path(payload['artifact_dir']))}")
    return 0 if payload["status"] in {"planned_only", "completed"} else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a checkpoint-free, no-solve wrapper timing probe for the 42x32 master overlay."
    )
    parser.add_argument("--strategy", type=Path, default=DEFAULT_STRATEGY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--candidate-key", default="42x32")
    parser.add_argument(
        "--execute-no-solve",
        action="store_true",
        help="Construct the 42x32 master overlay with runtime wrappers, but do not call CpSolver.Solve.",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_or_run_overlay_timing_probe(
    *,
    project_root: Path,
    strategy_path: Path,
    output_dir: Path,
    run_id: str = DEFAULT_RUN_ID,
    candidate_key: str = "42x32",
    execute_no_solve: bool = False,
    no_write: bool = False,
    session_factory: SessionFactory = create_exact_search_session,
    precheck_factory: PrecheckFactory = evaluate_exact_candidate_pre_master_precheck,
    model_factory: ModelFactory = MasterPlacementModel.from_exact_core,
    use_runtime_wrappers: bool = True,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    strategy_path = _resolve_path(project_root, strategy_path)
    output_dir = resolve_artifact_namespace(project_root, output_dir, OVERLAY_TIMING_NAMESPACE)
    run_id = _validate_allowed_overlay_timing_run_id(run_id)
    if str(candidate_key) != "42x32":
        raise ValueError("overlay timing probe V0 only allows candidate_key=42x32")
    strategy = _load_json(strategy_path)
    target = _target_from_strategy(strategy)
    if target.get("candidate_key") != "42x32":
        raise ValueError("overlay timing strategy must target candidate_key=42x32")
    artifact_dir = safe_child_artifact_dir(output_dir, run_id)
    paths = _paths(artifact_dir)
    plan = _base_payload(
        project_root=project_root,
        strategy_path=strategy_path,
        artifact_dir=artifact_dir,
        run_id=run_id,
        target=target,
        execute_no_solve=execute_no_solve,
    )
    before = build_sensitive_path_fingerprint(project_root)
    if not execute_no_solve:
        if not no_write:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(paths["plan"], plan)
            atomic_write_json(paths["sensitive_before"], before)
        after = build_sensitive_path_fingerprint(project_root)
        comparison = compare_sensitive_path_fingerprints(before, after)
        status = "planned_only" if comparison.get("changed") is False else "disqualified_sensitive_path_mutation"
        payload = {**plan, "status": status, "sensitive_path_comparison": comparison}
        if not no_write:
            atomic_write_json(paths["sensitive_after"], after)
            atomic_write_json(paths["sensitive_comparison"], comparison)
            atomic_write_json(paths["probe"], payload)
            paths["markdown"].write_text(render_overlay_timing_probe_markdown(payload), encoding="utf-8")
        return payload

    _assert_strategy_ready_for_execute(strategy)
    started = time.perf_counter()
    status = "completed"
    error: str | None = None
    inventory: dict[str, Any] = {}
    timing: dict[str, Any] = {}
    try:
        session = session_factory(
            project_root,
            solve_mode="certified_exact",
            master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        )
        precheck = precheck_factory(
            ghost_w=int(target["ghost_rect"]["w"]),
            ghost_h=int(target["ghost_rect"]["h"]),
            exact_session=session,
            master_search_profile=str(
                getattr(session, "master_search_profile", DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE)
            ),
        )
        boundary = dict(
            _mapping(precheck).get(
                "boundary_port_precheck",
                MasterPlacementModel._default_exact_candidate_boundary_port_feasibility_payload(),
            )
        )
        recorder = OverlayTimingRecorder()
        context = _patch_runtime_timing_wrappers(recorder) if use_runtime_wrappers else contextlib.nullcontext()
        with context:
            model_started = time.perf_counter()
            model = model_factory(
                getattr(session, "core"),
                ghost_rect=(int(target["ghost_rect"]["w"]), int(target["ghost_rect"]["h"])),
                master_search_profile=str(
                    getattr(session, "master_search_profile", DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE)
                ),
                precomputed_boundary_port_feasibility=boundary,
            )
            from_exact_core_total = time.perf_counter() - model_started
        inventory = _model_inventory(
            model=model,
            session=session,
            precheck=precheck,
            model_build_seconds=from_exact_core_total,
        )
        timing = _timing_summary(
            recorder=recorder,
            from_exact_core_total_seconds=from_exact_core_total,
            inventory=inventory,
        )
    except Exception as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"

    after = build_sensitive_path_fingerprint(project_root)
    comparison = compare_sensitive_path_fingerprints(before, after)
    if comparison.get("changed"):
        status = "disqualified_sensitive_path_mutation"
    payload = {
        **plan,
        "status": status,
        "error": error,
        "finished_at": now_iso(),
        "elapsed_seconds": float(time.perf_counter() - started),
        "inventory": inventory,
        "timing": timing,
        "sensitive_path_comparison": comparison,
    }
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(paths["plan"], plan)
        atomic_write_json(paths["sensitive_before"], before)
        atomic_write_json(paths["sensitive_after"], after)
        atomic_write_json(paths["sensitive_comparison"], comparison)
        atomic_write_json(paths["probe"], payload)
        paths["markdown"].write_text(render_overlay_timing_probe_markdown(payload), encoding="utf-8")
    return payload


def render_overlay_timing_probe_markdown(payload: Mapping[str, Any]) -> str:
    target = _mapping(payload.get("target"))
    timing = _mapping(payload.get("timing"))
    lines = [
        "# Phase3B Overlay Timing Probe",
        "",
        f"- Run id: `{payload.get('run_id')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Execute no-solve: `{payload.get('execute_no_solve')}`",
        f"- Candidate: `{target.get('candidate_key')}`",
        f"- Ghost rect: `{target.get('ghost_rect')}`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Source/model mutation: `false`",
        "",
        "## Timing",
        "",
        f"- From exact core total seconds: `{_fmt(timing.get('from_exact_core_total_seconds'))}`",
        f"- Recorded phase seconds sum: `{_fmt(timing.get('recorded_phase_seconds_sum'))}`",
        f"- Ghost anchor interval and outer residual seconds: `{_fmt(timing.get('ghost_anchor_interval_and_outer_residual_seconds'))}`",
        "",
        "| Phase | Calls | Seconds |",
        "|---|---:|---:|",
    ]
    for phase in list(timing.get("phases", []) or []):
        phase_map = _mapping(phase)
        lines.append(
            f"| `{phase_map.get('phase')}` | {phase_map.get('calls')} | {_fmt(phase_map.get('total_seconds'))} |"
        )
    lines.extend(
        [
            "",
            "This probe is local, no-solve, checkpoint-free evidence only. It is not proof input or scheduler input.",
            "",
        ]
    )
    return "\n".join(lines)


@dataclass
class PhaseTiming:
    calls: int = 0
    total_seconds: float = 0.0
    max_seconds: float = 0.0


@dataclass
class OverlayTimingRecorder:
    phases: MutableMapping[str, PhaseTiming] = field(default_factory=dict)

    def measure(self, phase: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - started
            bucket = self.phases.setdefault(str(phase), PhaseTiming())
            bucket.calls += 1
            bucket.total_seconds += float(elapsed)
            bucket.max_seconds = max(bucket.max_seconds, float(elapsed))

    def snapshot(self) -> list[dict[str, Any]]:
        rows = []
        for phase in sorted(self.phases):
            timing = self.phases[phase]
            rows.append(
                {
                    "phase": phase,
                    "calls": int(timing.calls),
                    "total_seconds": float(timing.total_seconds),
                    "max_seconds": float(timing.max_seconds),
                }
            )
        return rows


@contextlib.contextmanager
def _patch_runtime_timing_wrappers(
    recorder: OverlayTimingRecorder,
    *,
    delegate_cls: Any | None = None,
    master_module: ModuleType | Any | None = None,
    cp_model_cls: Any | None = None,
) -> Iterator[None]:
    if delegate_cls is None:
        from src.models.exact_coordinate_master import CoordinateExactMasterDelegate

        delegate_cls = CoordinateExactMasterDelegate
    if master_module is None:
        from src.models import master_model as master_module
    if cp_model_cls is None:
        from ortools.sat.python import cp_model

        cp_model_cls = cp_model.CpModel

    originals: list[tuple[Any, str, Any]] = []

    def wrap(owner: Any, attr: str, phase: str) -> None:
        original = getattr(owner, attr, None)
        if not callable(original):
            return

        def wrapped(*args: Any, __original: Callable[..., Any] = original, __phase: str = phase, **kwargs: Any) -> Any:
            return recorder.measure(__phase, __original, *args, **kwargs)

        originals.append((owner, attr, original))
        setattr(owner, attr, wrapped)

    wrap(delegate_cls, "_add_ghost_constraints", "CoordinateExactMasterDelegate._add_ghost_constraints")
    wrap(
        delegate_cls,
        "_apply_ghost_anchor_power_capacity_screen",
        "CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen",
    )
    wrap(
        delegate_cls,
        "_apply_ghost_anchor_signature_bucket_tightening",
        "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening",
    )
    wrap(
        delegate_cls,
        "_apply_ghost_anchor_residual_signature_bucket_tightening",
        "CoordinateExactMasterDelegate._apply_ghost_anchor_residual_signature_bucket_tightening",
    )
    wrap(master_module, "_rebuild_exact_core_overlay_search_guidance", "_rebuild_exact_core_overlay_search_guidance")
    wrap(cp_model_cls, "AddExactlyOne", "CpModel.AddExactlyOne")
    wrap(cp_model_cls, "AddNoOverlap2D", "CpModel.AddNoOverlap2D")
    try:
        yield
    finally:
        for owner, attr, original in reversed(originals):
            setattr(owner, attr, original)


def _timing_summary(
    *,
    recorder: OverlayTimingRecorder,
    from_exact_core_total_seconds: float,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phases = recorder.snapshot()
    by_phase = {str(row["phase"]): row for row in phases}
    ghost_total = _phase_seconds(by_phase, "CoordinateExactMasterDelegate._add_ghost_constraints")
    known_ghost = sum(
        _phase_seconds(by_phase, phase)
        for phase in (
            "CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen",
            "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening",
            "CoordinateExactMasterDelegate._apply_ghost_anchor_residual_signature_bucket_tightening",
            "CpModel.AddExactlyOne",
            "CpModel.AddNoOverlap2D",
        )
    )
    residual = max(0.0, ghost_total - known_ghost) if ghost_total else None
    build_stats = _mapping(_mapping(inventory.get("build_stats_summary")).get("exact_core_reuse"))
    return {
        "from_exact_core_total_seconds": float(from_exact_core_total_seconds),
        "recorded_phase_seconds_sum": float(sum(float(row["total_seconds"]) for row in phases)),
        "ghost_anchor_interval_and_outer_residual_seconds": residual,
        "build_stats_exact_core_reuse": {
            "overlay_build_seconds": _float(build_stats.get("overlay_build_seconds")),
            "ghost_constraint_seconds": _float(build_stats.get("ghost_constraint_seconds")),
            "rebuilt_search_strategy_count": _float(build_stats.get("rebuilt_search_strategy_count")),
        },
        "phases": phases,
        "coverage": {
            "wrapper_level_only": True,
            "source_model_mutation": False,
            "missing_if_zero_call": [
                phase
                for phase in (
                    "CoordinateExactMasterDelegate._add_ghost_constraints",
                    "_rebuild_exact_core_overlay_search_guidance",
                    "CpModel.AddNoOverlap2D",
                )
                if phase not in by_phase
            ],
        },
    }


def _phase_seconds(by_phase: Mapping[str, Mapping[str, Any]], phase: str) -> float:
    return float(_mapping(by_phase.get(phase)).get("total_seconds") or 0.0)


def _base_payload(
    *,
    project_root: Path,
    strategy_path: Path,
    artifact_dir: Path,
    run_id: str,
    target: Mapping[str, Any],
    execute_no_solve: bool,
) -> dict[str, Any]:
    return {
        "schema": "phase3b-checkpoint-free-overlay-timing-probe/v0",
        "generated_at": now_iso(),
        "project_root": str(project_root),
        "strategy_path": str(strategy_path),
        "artifact_dir": str(artifact_dir),
        "run_id": str(run_id),
        "target": dict(target),
        "execute_no_solve": bool(execute_no_solve),
        "no_solve": True,
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "runtime_execution_performed": False,
        "production_profile_changed": False,
    }


def _assert_strategy_ready_for_execute(strategy: Mapping[str, Any]) -> None:
    interpretation = _mapping(strategy.get("interpretation"))
    recommendation = _mapping(strategy.get("recommendation"))
    if interpretation.get("classification") != "broader_overlay_timing_required":
        raise ValueError("overlay timing strategy is not ready for execute-no-solve")
    if recommendation.get("action") != "run_single_42x32_wrapper_no_solve_overlay_timing_probe":
        raise ValueError("overlay timing strategy action does not allow execute-no-solve")


def _target_from_strategy(strategy: Mapping[str, Any]) -> dict[str, Any]:
    target = _mapping(strategy.get("target"))
    ghost_rect = _mapping(target.get("ghost_rect"))
    return {
        "candidate_key": str(target.get("candidate_key", "42x32")),
        "candidate_tuple": list(target.get("candidate_tuple", [1344, 42, 32]) or [1344, 42, 32]),
        "ghost_rect": {
            "w": int(ghost_rect.get("w", 42)),
            "h": int(ghost_rect.get("h", 32)),
            "area": int(ghost_rect.get("area", 1344)),
        },
    }


def _paths(artifact_dir: Path) -> dict[str, Path]:
    return {
        "plan": artifact_dir / "overlay_timing_probe_plan.json",
        "probe": artifact_dir / "overlay_timing_probe.json",
        "markdown": artifact_dir / "overlay_timing_probe.md",
        "sensitive_before": artifact_dir / "sensitive_path_before.json",
        "sensitive_after": artifact_dir / "sensitive_path_after.json",
        "sensitive_comparison": artifact_dir / "sensitive_path_comparison.json",
    }


def _guard_forbidden_cli_args(argv: Sequence[str]) -> None:
    for token in argv:
        text = str(token).strip().lower()
        if text in FORBIDDEN_ARG_EXACT or any(item in text for item in FORBIDDEN_ARG_TEXT):
            raise ValueError(f"forbidden checkpoint-free overlay timing probe argument: {token}")


def _assert_probe_namespace(path: Path) -> None:
    resolve_artifact_namespace(PROJECT_ROOT, path, OVERLAY_TIMING_NAMESPACE)


def _validate_allowed_overlay_timing_run_id(run_id: str) -> str:
    safe_run_id = validate_artifact_run_id(run_id)
    if safe_run_id not in ALLOWED_OVERLAY_TIMING_RUN_IDS:
        raise ValueError(
            "overlay timing probe run_id is not in ALLOWED_OVERLAY_TIMING_RUN_IDS: "
            f"{safe_run_id}"
        )
    return safe_run_id


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any, *, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value: Any) -> str:
    number = _float(value)
    return "null" if number is None else f"{number:.6f}"


if __name__ == "__main__":
    raise SystemExit(main())
