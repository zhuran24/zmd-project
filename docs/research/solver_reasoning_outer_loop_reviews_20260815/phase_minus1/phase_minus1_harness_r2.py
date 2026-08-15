#!/usr/bin/env python3
"""Observation-hardened Phase -1 harness.

The frozen experiment protocol is unchanged.  This harness differs from r1 only
by writing an atomic progress receipt after every expensive stage so a parent
watchdog can preserve truthful partial telemetry instead of a blank censored
record.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import phase_minus1_harness as base  # noqa: E402

HARNESS_REVISION = "r2_progress_receipts_v1"


def _progress_payload(
    *,
    layout: base.LayoutInput,
    stage: str,
    started: float,
    counters: Mapping[str, int],
    timings: Mapping[str, float],
    events: Sequence[Mapping[str, Any]],
    feedback_receipts: Sequence[Mapping[str, Any]],
    binding_summary: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_progress_v1",
        "research_only": True,
        "harness_revision": HARNESS_REVISION,
        "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
        "layout_id": layout.record["id"],
        "stratum": layout.record["stratum"],
        "split": layout.record["role"],
        "normalized_sha256": layout.normalized_sha256,
        "stage": stage,
        "elapsed_wall_seconds": time.perf_counter() - started,
        "counters": dict(counters),
        "timings": dict(timings),
        "events": list(events),
        "d2_organic_receipts": list(feedback_receipts),
    }
    if binding_summary is not None:
        payload["binding_summary"] = dict(binding_summary)
    if extra:
        payload["stage_details"] = dict(extra)
    return payload


def _write_progress(
    path: Path,
    *,
    layout: base.LayoutInput,
    stage: str,
    started: float,
    counters: Mapping[str, int],
    timings: Mapping[str, float],
    events: Sequence[Mapping[str, Any]],
    feedback_receipts: Sequence[Mapping[str, Any]],
    binding_summary: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> None:
    base._write_json(
        path,
        _progress_payload(
            layout=layout,
            stage=stage,
            started=started,
            counters=counters,
            timings=timings,
            events=events,
            feedback_receipts=feedback_receipts,
            binding_summary=binding_summary,
            extra=extra,
        ),
    )


def _run_layout(
    layout: base.LayoutInput,
    frozen: base.FrozenInputs,
    progress_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    events: list[dict[str, Any]] = []
    feedback_receipts: list[dict[str, Any]] = []
    counters = {
        "binding_proposals": 0,
        "binding_solves": 0,
        "routing_prechecks": 0,
        "routing_solves": 0,
        "binding_routing_round_trips": 0,
    }
    timings = {
        "occupancy_build_seconds": 0.0,
        "binding_build_seconds": 0.0,
        "binding_solve_seconds": 0.0,
        "routing_precheck_seconds": 0.0,
        "routing_build_seconds": 0.0,
        "routing_solve_seconds": 0.0,
    }

    _write_progress(
        progress_path,
        layout=layout,
        stage="occupancy_build_started",
        started=started,
        counters=counters,
        timings=timings,
        events=events,
        feedback_receipts=feedback_receipts,
    )
    stage_started = time.perf_counter()
    core = base._occupied_core(layout, frozen)
    timings["occupancy_build_seconds"] += time.perf_counter() - stage_started
    _write_progress(
        progress_path,
        layout=layout,
        stage="binding_build_started",
        started=started,
        counters=counters,
        timings=timings,
        events=events,
        feedback_receipts=feedback_receipts,
    )
    stage_started = time.perf_counter()
    model = base._new_binding_model(layout, frozen)
    timings["binding_build_seconds"] += time.perf_counter() - stage_started
    last_binding_summary: Mapping[str, Any] = model.extract_conflict_summary()
    _write_progress(
        progress_path,
        layout=layout,
        stage="binding_build_finished",
        started=started,
        counters=counters,
        timings=timings,
        events=events,
        feedback_receipts=feedback_receipts,
        binding_summary=last_binding_summary,
    )

    terminal_status = "UNKNOWN"
    censor_status = "UNCENSORED"
    final_reason = "unknown_other"
    pending_receipt: MutableMapping[str, Any] | None = None

    while True:
        _write_progress(
            progress_path,
            layout=layout,
            stage="binding_solve_started",
            started=started,
            counters=counters,
            timings=timings,
            events=events,
            feedback_receipts=feedback_receipts,
            binding_summary=last_binding_summary,
            extra={"solve_index": counters["binding_solves"] + 1},
        )
        solve_started = time.perf_counter()
        binding_status = base._binding_status_name(model.solve(base.BINDING_SECONDS))
        timings["binding_solve_seconds"] += time.perf_counter() - solve_started
        counters["binding_solves"] += 1
        last_binding_summary = model.extract_conflict_summary()
        if pending_receipt is not None:
            next_selection = model.extract_selection() if binding_status == "FEASIBLE" else None
            base._complete_feedback_receipt(
                pending_receipt,
                next_status=binding_status,
                next_selection=next_selection,
            )
            pending_receipt = None
        _write_progress(
            progress_path,
            layout=layout,
            stage="binding_solve_finished",
            started=started,
            counters=counters,
            timings=timings,
            events=events,
            feedback_receipts=feedback_receipts,
            binding_summary=last_binding_summary,
            extra={"binding_status": binding_status},
        )

        if binding_status == "FEASIBLE":
            counters["binding_proposals"] += 1
            selection = model.extract_selection()
            port_specs = model.extract_port_specs()
            counters["routing_prechecks"] += 1
            _write_progress(
                progress_path,
                layout=layout,
                stage="routing_precheck_started",
                started=started,
                counters=counters,
                timings=timings,
                events=events,
                feedback_receipts=feedback_receipts,
                binding_summary=last_binding_summary,
                extra={
                    "binding_selection_digest": base._selection_digest(selection),
                    "port_count": len(port_specs),
                },
            )
            pre_started = time.perf_counter()
            precheck = base.run_exact_routing_precheck(
                placement_core=core,
                port_specs=port_specs,
            )
            replay = base.run_exact_routing_precheck(
                placement_core=core,
                port_specs=port_specs,
            )
            timings["routing_precheck_seconds"] += time.perf_counter() - pre_started
            projection = base._precheck_projection(precheck)
            replay_projection = base._precheck_projection(replay)
            replay_status = (
                "REPLAYED_IDENTICAL" if projection == replay_projection else "REPLAY_MISMATCH"
            )
            precheck_status = str(precheck.get("status", ""))
            _write_progress(
                progress_path,
                layout=layout,
                stage="routing_precheck_finished",
                started=started,
                counters=counters,
                timings=timings,
                events=events,
                feedback_receipts=feedback_receipts,
                binding_summary=last_binding_summary,
                extra={
                    "precheck": projection,
                    "diagnostic_replay_status": replay_status,
                },
            )

            if precheck_status in base.ROUTING_DOMAIN_PROOF_REJECT_STATUSES:
                if not bool(precheck.get("binding_selection_safe_reject", False)):
                    raise base.ProtocolViolation(
                        f"precheck {precheck_status} did not authorize binding-selection reject"
                    )
                reason = (
                    "routing_front_blocked"
                    if precheck_status == "front_blocked"
                    else "routing_relaxed_disconnected"
                )
                conflict_set = list(precheck.get("placement_level_conflict_set", []))
                events.append(
                    base._event(
                        reason=reason,
                        gate_side="routing_precheck",
                        feedback_form="binding_selection_family",
                        support_core_status=(
                            "AVAILABLE_NOT_REPLAYED" if conflict_set else "UNAVAILABLE"
                        ),
                        diagnostic_replay_status=replay_status,
                        details=projection,
                    )
                )
                receipt = base._apply_feedback(
                    model,
                    layout=layout,
                    selection=selection,
                    producer=f"routing_precheck:{precheck_status}",
                    diagnostics=projection,
                )
                feedback_receipts.append(receipt)
                pending_receipt = receipt
                counters["binding_routing_round_trips"] += 1
                _write_progress(
                    progress_path,
                    layout=layout,
                    stage="organic_feedback_applied",
                    started=started,
                    counters=counters,
                    timings=timings,
                    events=events,
                    feedback_receipts=feedback_receipts,
                    binding_summary=last_binding_summary,
                    extra={"producer": f"routing_precheck:{precheck_status}"},
                )
                continue

            if precheck_status != base.ROUTING_DOMAIN_STATUS_FEASIBLE:
                raise base.ProtocolViolation(
                    f"unexpected routing precheck status: {precheck_status!r}"
                )

            commodities = sorted(
                {
                    str(spec["commodity"])
                    for spec in port_specs
                    if str(spec.get("commodity", ""))
                }
            )
            _write_progress(
                progress_path,
                layout=layout,
                stage="routing_build_started",
                started=started,
                counters=counters,
                timings=timings,
                events=events,
                feedback_receipts=feedback_receipts,
                binding_summary=last_binding_summary,
                extra={"commodity_count": len(commodities)},
            )
            route_model = base.RoutingSubproblem.from_placement_core(
                core,
                port_specs,
                commodities,
                domain_analysis=precheck["_analysis"],
            )
            route_build_started = time.perf_counter()
            route_model.build()
            timings["routing_build_seconds"] += time.perf_counter() - route_build_started
            _write_progress(
                progress_path,
                layout=layout,
                stage="routing_build_finished",
                started=started,
                counters=counters,
                timings=timings,
                events=events,
                feedback_receipts=feedback_receipts,
                binding_summary=last_binding_summary,
                extra={"routing_build_stats": route_model.build_stats},
            )
            counters["routing_solves"] += 1
            _write_progress(
                progress_path,
                layout=layout,
                stage="routing_solve_started",
                started=started,
                counters=counters,
                timings=timings,
                events=events,
                feedback_receipts=feedback_receipts,
                binding_summary=last_binding_summary,
            )
            route_solve_started = time.perf_counter()
            routing_status = str(route_model.solve(base.ROUTING_SECONDS))
            timings["routing_solve_seconds"] += time.perf_counter() - route_solve_started
            _write_progress(
                progress_path,
                layout=layout,
                stage="routing_solve_finished",
                started=started,
                counters=counters,
                timings=timings,
                events=events,
                feedback_receipts=feedback_receipts,
                binding_summary=last_binding_summary,
                extra={
                    "routing_status": routing_status,
                    "routing_build_stats": route_model.build_stats,
                },
            )

            if routing_status == "FEASIBLE":
                terminal_status = "FEASIBLE"
                final_reason = "layout_feasible"
                events.append(
                    base._event(
                        reason="layout_feasible",
                        gate_side="terminal",
                        feedback_form="none",
                        details={
                            "route_count": len(route_model.extract_routes()),
                            "routing_build_stats": route_model.build_stats,
                        },
                    )
                )
                break

            if routing_status == "INFEASIBLE":
                event_details = {
                    "precheck": projection,
                    "routing_build_stats": route_model.build_stats,
                }
                events.append(
                    base._event(
                        reason="routing_model_infeasible",
                        gate_side="routing_solve",
                        feedback_form="point_nogood",
                        details=event_details,
                    )
                )
                receipt = base._apply_feedback(
                    model,
                    layout=layout,
                    selection=selection,
                    producer="routing_solve:INFEASIBLE",
                    diagnostics=event_details,
                )
                feedback_receipts.append(receipt)
                pending_receipt = receipt
                counters["binding_routing_round_trips"] += 1
                _write_progress(
                    progress_path,
                    layout=layout,
                    stage="organic_feedback_applied",
                    started=started,
                    counters=counters,
                    timings=timings,
                    events=events,
                    feedback_receipts=feedback_receipts,
                    binding_summary=last_binding_summary,
                    extra={"producer": "routing_solve:INFEASIBLE"},
                )
                continue

            terminal_status = "UNKNOWN"
            censor_status = "SOLVER_TIMEOUT_ROUTING"
            final_reason = (
                "routing_connectivity_guard_timeout"
                if str(route_model.build_stats.get("last_solve", {}).get("status", ""))
                == "CONNECTIVITY_GUARD_TIMEOUT"
                else "routing_solver_timeout"
            )
            break

        if binding_status == "INFEASIBLE":
            terminal_status = "INFEASIBLE"
            empty_domains = model.extract_empty_binding_domain_instances()
            final_reason = "binding_empty_domain" if empty_domains else "binding_exhausted"
            events.append(
                base._event(
                    reason=final_reason,
                    gate_side="binding_solve",
                    feedback_form="none",
                    support_core_status=(
                        "AVAILABLE_NOT_REPLAYED" if empty_domains else "UNAVAILABLE"
                    ),
                    details={
                        "empty_binding_domain_instances": empty_domains,
                        "binding_summary": last_binding_summary,
                    },
                )
            )
            break
        if binding_status == "INVALID_INPUT":
            terminal_status = "UNKNOWN"
            censor_status = "INVALID_INPUT"
            final_reason = "binding_invalid_input"
            break
        terminal_status = "UNKNOWN"
        censor_status = "SOLVER_TIMEOUT_BINDING"
        final_reason = "unknown_other"
        break

    result = {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v1",
        "research_only": True,
        "harness_revision": HARNESS_REVISION,
        "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
        "repository_head": base._git("rev-parse", "HEAD"),
        "layout_id": layout.record["id"],
        "stratum": layout.record["stratum"],
        "split": layout.record["role"],
        "normalized_sha256": layout.normalized_sha256,
        "pose_id_remaps": layout.pose_id_remaps,
        "ghost_rect": list(layout.ghost_rect),
        "ghost_source_receipt": layout.ghost_source_receipt,
        "source_identity_receipt": layout.source_identity_receipt,
        "terminalStatus": terminal_status,
        "censorStatus": censor_status,
        "finalReason": final_reason,
        "counters": counters,
        "timings": timings,
        "total_wall_seconds": time.perf_counter() - started,
        "events": events,
        "d2_organic_receipts": feedback_receipts,
        "binding_summary": last_binding_summary,
        "solver_contract": {
            "binding_seconds": base.BINDING_SECONDS,
            "routing_seconds": base.ROUTING_SECONDS,
            "binding_workers": base.BINDING_WORKERS,
            "routing_workers": base.ROUTING_WORKERS,
            "cp_sat_random_seed": base.CP_SAT_RANDOM_SEED,
            "alternative_count_cap": None,
        },
    }
    _write_progress(
        progress_path,
        layout=layout,
        stage="terminal_receipt_ready",
        started=started,
        counters=counters,
        timings=timings,
        events=events,
        feedback_receipts=feedback_receipts,
        binding_summary=last_binding_summary,
        extra={
            "terminalStatus": terminal_status,
            "censorStatus": censor_status,
            "finalReason": final_reason,
        },
    )
    return result


def _timeout_from_progress(
    *,
    record: Mapping[str, Any],
    progress_path: Path,
) -> dict[str, Any]:
    if progress_path.is_file():
        partial = base._read_json(progress_path)
        if not isinstance(partial, Mapping):
            partial = {}
    else:
        partial = {}
    result = dict(partial)
    result.update(
        {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v1",
            "research_only": True,
            "harness_revision": HARNESS_REVISION,
            "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
            "repository_head": base._git("rev-parse", "HEAD"),
            "layout_id": record["id"],
            "stratum": record["stratum"],
            "split": record["role"],
            "terminalStatus": "UNKNOWN",
            "censorStatus": "WALL_TIMEOUT_END_TO_END",
            "finalReason": "unknown_other",
            "total_wall_seconds": base.LAYOUT_WATCHDOG_SECONDS,
            "watchdog": {
                "seconds": base.LAYOUT_WATCHDOG_SECONDS,
                "action": "child_terminated",
                "last_observed_stage": partial.get("stage"),
                "partial_progress_preserved": bool(partial),
            },
        }
    )
    return result


def _run_injected(
    layout: base.LayoutInput,
    frozen: base.FrozenInputs,
    progress_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    base._write_json(
        progress_path,
        {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_progress_v1",
            "layout_id": layout.record["id"],
            "stage": "binding_build_started",
            "elapsed_wall_seconds": 0.0,
        },
    )
    model = base._new_binding_model(layout, frozen)
    base._write_json(
        progress_path,
        {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_progress_v1",
            "layout_id": layout.record["id"],
            "stage": "first_binding_solve_started",
            "elapsed_wall_seconds": time.perf_counter() - started,
        },
    )
    first_status = str(model.solve(base.BINDING_SECONDS))
    if first_status != "FEASIBLE":
        return {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v1",
            "harness_revision": HARNESS_REVISION,
            "layout_id": layout.record["id"],
            "producer": "injected_selection_nogood",
            "first_status": first_status,
            "reachabilityFailureClass": "NOT_REACHED",
            "terminalOutcome": None,
            "wall_seconds": time.perf_counter() - started,
        }
    first_selection = model.extract_selection()
    receipt = base._apply_feedback(
        model,
        layout=layout,
        selection=first_selection,
        producer="injected_selection_nogood",
        diagnostics={"purpose": "D2 injected consumer canary"},
    )
    base._write_json(
        progress_path,
        {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_progress_v1",
            "layout_id": layout.record["id"],
            "stage": "feedback_applied",
            "elapsed_wall_seconds": time.perf_counter() - started,
            "receipt": receipt,
        },
    )
    second_status = str(model.solve(base.BINDING_SECONDS))
    second_selection = model.extract_selection() if second_status == "FEASIBLE" else None
    base._complete_feedback_receipt(
        receipt,
        next_status=second_status,
        next_selection=second_selection,
    )
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v1",
        "harness_revision": HARNESS_REVISION,
        "layout_id": layout.record["id"],
        "producer": "injected_selection_nogood",
        "first_status": first_status,
        "second_status": second_status,
        "receipt": receipt,
        "wall_seconds": time.perf_counter() - started,
    }


def _run_layout_command(layout_id: str, output: Path, progress: Path) -> int:
    manifest = base._load_manifest()
    frozen = base._load_frozen_inputs(manifest)
    base._assert_protocol_ancestor()
    base._assert_clean_environment()
    record = base._record_by_id(manifest, layout_id)
    try:
        layout = base._load_layout(record, manifest, frozen)
        result = _run_layout(layout, frozen, progress)
    except base.IneligibleInput as exc:
        result = {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v1",
            "research_only": True,
            "harness_revision": HARNESS_REVISION,
            "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
            "repository_head": base._git("rev-parse", "HEAD"),
            "layout_id": layout_id,
            "stratum": record["stratum"],
            "split": record["role"],
            "terminalStatus": "UNKNOWN",
            "censorStatus": "INELIGIBLE_INPUT",
            "finalReason": "unknown_other",
            "events": [],
            "d2_organic_receipts": [],
            "error": str(exc),
        }
    except base.ProtocolViolation:
        raise
    except Exception as exc:  # noqa: BLE001
        result = base._synthetic_error_result(record, f"{type(exc).__name__}: {exc}")
        result["harness_revision"] = HARNESS_REVISION
        result["traceback"] = traceback.format_exc()
    base._write_json(output, result)
    print(json.dumps({"layout_id": layout_id, "receipt": str(output)}, ensure_ascii=False))
    return 0


def _run_injected_command(layout_id: str, output: Path, progress: Path) -> int:
    manifest = base._load_manifest()
    frozen = base._load_frozen_inputs(manifest)
    base._assert_protocol_ancestor()
    base._assert_clean_environment()
    record = base._record_by_id(manifest, layout_id)
    try:
        layout = base._load_layout(record, manifest, frozen)
        result = _run_injected(layout, frozen, progress)
    except Exception as exc:  # noqa: BLE001
        result = {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v1",
            "harness_revision": HARNESS_REVISION,
            "layout_id": layout_id,
            "producer": "injected_selection_nogood",
            "reachabilityFailureClass": "NOT_REACHED",
            "terminalOutcome": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    base._write_json(output, result)
    print(json.dumps({"layout_id": layout_id, "receipt": str(output)}, ensure_ascii=False))
    return 0


def _augment_aggregate_with_censored_observations(
    output_dir: Path,
    manifest: Mapping[str, Any],
) -> None:
    results = []
    for record in manifest["records"]:
        path = output_dir / "layouts" / f"{record['id']}.json"
        if path.is_file():
            payload = base._read_json(path)
            if isinstance(payload, Mapping):
                results.append(payload)

    family_layouts: dict[str, set[str]] = {}
    family_strata: dict[str, set[str]] = {}
    family_splits: dict[str, set[str]] = {}
    family_censors: dict[str, set[str]] = {}
    family_replays: dict[str, set[str]] = {}
    last_stage_counts: dict[str, int] = {}
    for result in results:
        last_stage = str(
            result.get("watchdog", {}).get("last_observed_stage")
            or result.get("stage")
            or "terminal_receipt"
        )
        last_stage_counts[last_stage] = last_stage_counts.get(last_stage, 0) + 1
        seen_in_layout: set[str] = set()
        for event in result.get("events", []):
            if not isinstance(event, Mapping):
                continue
            key = str(event.get("familyKey", ""))
            if not key or key in seen_in_layout:
                continue
            seen_in_layout.add(key)
            family_layouts.setdefault(key, set()).add(str(result["layout_id"]))
            family_strata.setdefault(key, set()).add(str(result["stratum"]))
            family_splits.setdefault(key, set()).add(str(result["split"]))
            family_censors.setdefault(key, set()).add(str(result.get("censorStatus")))
            replay = event.get("diagnosticReplayStatus")
            if replay:
                family_replays.setdefault(key, set()).add(str(replay))

    observed_families = []
    for key in sorted(family_layouts):
        reason, gate_side, feedback_form, event_censor = key.split("|", 3)
        observed_families.append(
            {
                "familyKey": key,
                "reason": reason,
                "gateSide": gate_side,
                "feedbackForm": feedback_form,
                "eventCensorStatus": event_censor,
                "layout_ids": sorted(family_layouts[key]),
                "layout_count": len(family_layouts[key]),
                "strata": sorted(family_strata[key]),
                "strata_count": len(family_strata[key]),
                "splits": sorted(family_splits[key]),
                "terminal_censor_statuses": sorted(family_censors[key]),
                "diagnostic_replay_statuses": sorted(family_replays.get(key, set())),
                "eligible_for_d3": False,
                "eligibility_note": "Observed event only; D3 eligibility remains restricted to uncensored terminal layouts.",
            }
        )

    spectrum_path = output_dir / "D1_DEATH_SPECTRUM.json"
    spectrum = base._read_json(spectrum_path)
    if not isinstance(spectrum, Mapping):
        raise RuntimeError("D1 spectrum must be an object before r2 augmentation")
    updated = dict(spectrum)
    updated["harness_revision"] = HARNESS_REVISION
    updated["observed_families_all"] = observed_families
    updated["last_observed_stage_counts"] = dict(sorted(last_stage_counts.items()))
    updated["censored_layouts_with_observed_events"] = sum(
        result.get("censorStatus") != "UNCENSORED" and bool(result.get("events"))
        for result in results
    )
    base._write_json(spectrum_path, updated)

    summary_path = output_dir / "BATCH_SUMMARY.md"
    with summary_path.open("a", encoding="utf-8") as handle:
        handle.write("\n## Censored progress observations\n\n")
        handle.write(
            f"- Censored layouts retaining at least one event: "
            f"`{updated['censored_layouts_with_observed_events']}`.\n"
        )
        handle.write(f"- Last observed stages: `{updated['last_observed_stage_counts']}`.\n")
        handle.write(
            "- These observations are telemetry only and do not satisfy the uncensored D3 gate.\n"
        )
        for family in observed_families:
            handle.write(
                f"- `{family['familyKey']}`: {family['layout_count']} layouts / "
                f"{family['strata_count']} strata; terminal censors "
                f"`{family['terminal_censor_statuses']}`.\n"
            )


def _run_batch(output_dir: Path) -> int:
    manifest = base._load_manifest()
    frozen = base._load_frozen_inputs(manifest)
    base._assert_protocol_ancestor()
    base._assert_clean_environment()
    excluded_receipts = base._validate_excluded_candidates(manifest, frozen)

    admission = []
    normalized_seen: set[str] = set()
    for record in manifest["records"]:
        try:
            layout = base._load_layout(record, manifest, frozen)
            if layout.normalized_sha256 in normalized_seen:
                raise base.IneligibleInput(
                    f"duplicate normalized digest in admitted corpus: {layout.normalized_sha256}"
                )
            normalized_seen.add(layout.normalized_sha256)
            admission.append(
                {
                    "layout_id": record["id"],
                    "status": "ADMITTED",
                    "normalized_sha256": layout.normalized_sha256,
                }
            )
        except Exception as exc:  # noqa: BLE001
            admission.append(
                {
                    "layout_id": record["id"],
                    "status": "INELIGIBLE_INPUT",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    base._write_json(
        output_dir / "CORPUS_ADMISSION.json",
        {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_admission_v1",
            "protocol_freeze_commit": base.PROTOCOL_FREEZE_COMMIT,
            "harness_revision": HARNESS_REVISION,
            "admitted_records": admission,
            "excluded_records": excluded_receipts,
        },
    )
    if any(item["status"] != "ADMITTED" for item in admission):
        return 2

    layout_dir = output_dir / "layouts"
    progress_dir = output_dir / "progress"
    log_dir = output_dir / "layout_logs"
    for directory in (layout_dir, progress_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)
    environment = base._child_environment()
    script = Path(__file__).resolve()

    for record in manifest["records"]:
        layout_id = str(record["id"])
        output_path = layout_dir / f"{layout_id}.json"
        progress_path = progress_dir / f"{layout_id}.progress.json"
        log_path = log_dir / f"{layout_id}.log"
        command = [
            sys.executable,
            str(script),
            "layout",
            "--layout-id",
            layout_id,
            "--output",
            str(output_path),
            "--progress",
            str(progress_path),
        ]
        started = time.perf_counter()
        with log_path.open("w", encoding="utf-8") as log_handle:
            log_handle.write(f"command={command!r}\n")
            log_handle.flush()
            try:
                completed = subprocess.run(
                    command,
                    cwd=base.ROOT,
                    env=environment,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=base.LAYOUT_WATCHDOG_SECONDS,
                    text=True,
                )
            except subprocess.TimeoutExpired:
                base._write_json(
                    output_path,
                    _timeout_from_progress(record=record, progress_path=progress_path),
                )
                log_handle.write(
                    f"watchdog_timeout_seconds={base.LAYOUT_WATCHDOG_SECONDS}\n"
                )
            else:
                log_handle.write(f"child_exit_code={completed.returncode}\n")
                if completed.returncode != 0 and not output_path.is_file():
                    base._write_json(
                        output_path,
                        base._synthetic_error_result(
                            record,
                            f"child exited {completed.returncode} without receipt",
                        ),
                    )
            log_handle.write(f"parent_wall_seconds={time.perf_counter() - started:.6f}\n")

    injection_path = output_dir / "D2_INJECTED.json"
    injection_progress_path = output_dir / "D2_INJECTED.progress.json"
    injection_log = output_dir / "D2_INJECTED.log"
    injection_command = [
        sys.executable,
        str(script),
        "inject",
        "--layout-id",
        "POSTMEM-00",
        "--output",
        str(injection_path),
        "--progress",
        str(injection_progress_path),
    ]
    with injection_log.open("w", encoding="utf-8") as log_handle:
        try:
            completed = subprocess.run(
                injection_command,
                cwd=base.ROOT,
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=base.INJECTED_WATCHDOG_SECONDS,
                text=True,
            )
        except subprocess.TimeoutExpired:
            partial = (
                base._read_json(injection_progress_path)
                if injection_progress_path.is_file()
                else {}
            )
            receipt = partial.get("receipt") if isinstance(partial, Mapping) else None
            reached_consumer = isinstance(receipt, Mapping)
            base._write_json(
                injection_path,
                {
                    "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v1",
                    "harness_revision": HARNESS_REVISION,
                    "layout_id": "POSTMEM-00",
                    "producer": "injected_selection_nogood",
                    "reachabilityFailureClass": (
                        "REACHED_NO_EFFECT" if reached_consumer else "NOT_REACHED"
                    ),
                    "terminalOutcome": None,
                    "censorStatus": "WALL_TIMEOUT_END_TO_END",
                    "last_observed_stage": (
                        partial.get("stage") if isinstance(partial, Mapping) else None
                    ),
                    "receipt": receipt,
                },
            )
        else:
            log_handle.write(f"child_exit_code={completed.returncode}\n")

    base._aggregate(output_dir, manifest)
    _augment_aggregate_with_censored_observations(output_dir, manifest)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")

    layout = subparsers.add_parser("layout")
    layout.add_argument("--layout-id", required=True)
    layout.add_argument("--output", type=Path, required=True)
    layout.add_argument("--progress", type=Path, required=True)

    inject = subparsers.add_parser("inject")
    inject.add_argument("--layout-id", required=True)
    inject.add_argument("--output", type=Path, required=True)
    inject.add_argument("--progress", type=Path, required=True)

    batch = subparsers.add_parser("batch")
    batch.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        return base._validate_corpus()
    if args.command == "layout":
        return _run_layout_command(
            args.layout_id,
            args.output.resolve(),
            args.progress.resolve(),
        )
    if args.command == "inject":
        return _run_injected_command(
            args.layout_id,
            args.output.resolve(),
            args.progress.resolve(),
        )
    if args.command == "batch":
        return _run_batch(args.output_dir.resolve())
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
