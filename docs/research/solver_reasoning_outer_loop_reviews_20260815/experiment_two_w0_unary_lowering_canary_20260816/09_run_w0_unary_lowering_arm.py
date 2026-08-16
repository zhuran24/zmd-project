#!/usr/bin/env python3
"""Run one isolated arm of the W0 unary-lowering canary."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from typing import Any, Mapping

from endpoint_metrics import (
    capture_identity_snapshot,
    endpoint_neutral_transaction,
    marginal_domain_envelope,
    resource_snapshot,
)
from w0_canary_receipt_contract import (
    ReceiptContractError,
    dump_receipt,
    make_receipt,
    sha256_file,
    validate_receipt,
)
from w0_unary_lowering import (
    LoweringError,
    apply_w0_unary_lowering,
    load_lowering_spec,
    trigger_is_active,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST_PATH = HERE / "03_CANARY_MANIFEST.json"
ENDPOINT_PROTOCOL_PATH = HERE / "02_ENDPOINT_METRICS_PROTOCOL_V1.json"
SPEC_PATH = HERE / "04_W0_UNARY_LOWERING_SPEC.json"
ARMS = ("A_BASELINE", "B_OBSERVER_NOOP", "C_UNARY_LOWERING")
TARGET_INSTANCE_ID = "boundary_port_041"
TARGET_FRONT = [1, 53]


class ArmError(RuntimeError):
    """An arm cannot honor the frozen canary contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ArmError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArmError(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ArmError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> float:
    started = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    with path.open("ab") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return time.perf_counter() - started


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_phase_modules() -> tuple[Any, Any]:
    phase_dir = ROOT / "docs/research/solver_reasoning_outer_loop_reviews_20260815/phase_minus1"
    sys.path.insert(0, str(phase_dir))
    try:
        base = importlib.import_module("phase_minus1_harness")
        r3 = importlib.import_module("phase_minus1_harness_r3")
    finally:
        sys.path.pop(0)
    return base, r3


def verify_prerequisite_receipt(path: Path, *, kind: str) -> dict[str, Any]:
    payload = read_json(path)
    validate_receipt(payload)
    require(payload["result_kind"] == kind, f"wrong prerequisite result kind: {path}")
    require(payload["outcome"] == "PASS", f"prerequisite did not PASS: {path}")
    return payload


def verify_runtime_and_inputs(manifest: Mapping[str, Any]) -> None:
    import ortools

    runtime = manifest["runtime_identity"]
    require(
        str(Path(sys.executable).resolve())
        == str(Path(runtime["python_executable"]).resolve()),
        "wrong Python interpreter",
    )
    require(sys.version.split()[0] == runtime["python_version"], "Python version drift")
    require(str(ortools.__version__) == runtime["ortools_version"], "OR-Tools version drift")
    for relative, record in manifest["frozen_inputs"].items():
        path = ROOT / str(relative)
        require(path.is_file(), f"missing frozen input: {relative}")
        require(sha256_file(path) == record["sha256"], f"frozen input SHA drift: {relative}")
        require(path.stat().st_size == int(record["size_bytes"]), f"frozen input size drift: {relative}")
    for group in ("production_source_identities", "research_adapter_identities"):
        for relative, expected in manifest[group].items():
            require(sha256_file(ROOT / relative) == expected, f"source SHA drift: {relative}")


def run_theorem_checker(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    checker = ROOT / str(manifest["theorem_identity"]["checker_path"])
    result = subprocess.run(
        [sys.executable, str(checker), "--coverage", "off"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    require(result.returncode == 0, f"theorem checker failed: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    require(payload.get("status") == "PASS", "theorem checker did not PASS")
    require(payload.get("coverage") is None, "theorem checker consumed observation journal")
    return payload, time.perf_counter() - started


def load_w0(base: Any) -> tuple[Any, Any, Any, Any]:
    corpus = base._load_manifest()
    frozen = base._load_frozen_inputs(corpus)
    record = base._record_by_id(corpus, "W0-ALIGNMENT")
    layout = base._load_layout(record, corpus, frozen)
    core = base._occupied_core(layout, frozen)
    model = base._new_binding_model(layout, frozen)
    return model, layout, core, frozen


def target_blocked_record(precheck: Mapping[str, Any]) -> dict[str, Any]:
    matches = [
        dict(item)
        for item in precheck.get("blocked_ports", [])
        if isinstance(item, Mapping)
        and str(item.get("instance_id")) == TARGET_INSTANCE_ID
        and list(item.get("front_cell", [])) == TARGET_FRONT
    ]
    require(len(matches) == 1, f"target blocked-port record count is {len(matches)}")
    return matches[0]


def target_active_port_spec_count(port_specs: list[Mapping[str, Any]]) -> int:
    return sum(str(spec.get("instance_id")) == TARGET_INSTANCE_ID for spec in port_specs)


def selection_sequence_sha256(digests: list[str]) -> str:
    return hashlib.sha256("".join(f"{value}\n" for value in digests).encode("utf-8")).hexdigest()


def output_surface_snapshot() -> dict[str, dict[str, Any]]:
    paths = (
        "data/solutions/final_solution.json",
        "data/blueprints/optimal_blueprint.json",
        "data/solutions/certified_delivery_manifest.json",
    )
    result: dict[str, dict[str, Any]] = {}
    for relative in paths:
        path = ROOT / relative
        result[relative] = {
            "exists": path.is_file(),
            "sha256": sha256_file(path) if path.is_file() else None,
        }
    return result


def generic_output_envelope(model: Any, *, treatment: bool) -> dict[str, Any]:
    raw_sizes = [len(values) for values in model.generic_output_vars.values()]
    effective_sizes = list(raw_sizes)
    if treatment:
        target_index = [slot["slot_id"] for slot in model.generic_output_slots].index(
            "boundary_port_041:out:0"
        )
        effective_sizes[target_index] = 1
    raw = marginal_domain_envelope(raw_sizes)
    effective = marginal_domain_envelope(effective_sizes)
    return {
        "evidence_type": "BOX_DOMAIN",
        "raw": raw,
        "effective_after_compiled_restriction": effective,
        "literal_count": sum(raw_sizes),
        "target_effective_domain_cardinality": 1 if treatment else 3,
        "target_effective_active_value_count": 0 if treatment else 2,
    }


def arm_watchdog_seconds(manifest: Mapping[str, Any], arm: str) -> float:
    parameters = manifest["run_parameters"]
    key = {
        "A_BASELINE": "minimal_baseline_arm_watchdog_seconds",
        "B_OBSERVER_NOOP": "observation_noop_arm_watchdog_seconds",
        "C_UNARY_LOWERING": "treatment_arm_watchdog_seconds",
    }[arm]
    return float(parameters[key])


def compact_event(
    *,
    arm: str,
    index: int,
    selection_digest: str,
    precheck: Mapping[str, Any],
    replay_identical: bool,
    literal_count: int,
    trigger_active: bool | None,
    active_port_count: int | None,
    r3_event: Mapping[str, Any] | None,
) -> dict[str, Any]:
    target = target_blocked_record(precheck)
    value: dict[str, Any] = {
        "schema_version": "zmd_w0_unary_canary_event_v1",
        "record_type": "binding_precheck_reject",
        "arm": arm,
        "event_index": index,
        "selection_digest": selection_digest,
        "precheck_status": str(precheck.get("status")),
        "precheck_replay_identical": replay_identical,
        "target_instance_id": TARGET_INSTANCE_ID,
        "target_front_cell": TARGET_FRONT,
        "target_commodity": str(target.get("commodity", "")),
        "point_nogood_literal_count": literal_count,
        "routing_solve_reached": False,
    }
    if trigger_active is not None:
        value["j_trigger_active"] = trigger_active
    if active_port_count is not None:
        value["target_active_port_spec_count"] = active_port_count
    if r3_event is not None:
        value["local_signature_digest"] = r3_event["local_signature_digest"]
        value["local_signature_counts"] = r3_event["local_signature_counts"]
        value["blocked_port_count"] = r3_event["blocked_port_count"]
    return value


def run_arm(
    *,
    arm: str,
    run_id: str,
    arm_dir: Path,
    contract_receipt: Mapping[str, Any],
    sensitivity_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    manifest = read_json(MANIFEST_PATH)
    endpoint_protocol = read_json(ENDPOINT_PROTOCOL_PATH)
    spec = load_lowering_spec(SPEC_PATH)
    verify_runtime_and_inputs(manifest)
    base, r3 = load_phase_modules()
    base._assert_clean_environment()

    before_endpoint = capture_identity_snapshot(
        ROOT,
        [*endpoint_protocol["current_endpoint_sources"], *endpoint_protocol["protected_surfaces"]],
    )
    before_outputs = output_surface_snapshot()
    theorem_receipt, theorem_seconds = run_theorem_checker(manifest)

    build_started = time.perf_counter()
    model, layout, core, _frozen = load_w0(base)
    binding_build_seconds = time.perf_counter() - build_started
    require(layout.normalized_sha256 == manifest["fixed_context"]["normalized_layout_sha256"], "W0 normalized identity drift")
    require(list(layout.ghost_rect) == manifest["fixed_context"]["ghost_rect"], "W0 ghost rect drift")

    lowering_receipt: Mapping[str, Any] | None = None
    if arm == "C_UNARY_LOWERING":
        lowering_receipt = apply_w0_unary_lowering(model, spec)
    envelope = generic_output_envelope(model, treatment=arm == "C_UNARY_LOWERING")
    proto = model.model.Proto()
    model_snapshot = {
        "proto_variable_count": len(proto.variables),
        "proto_constraint_count": len(proto.constraints),
        "generic_output_envelope": envelope,
    }

    event_path = arm_dir / "events.jsonl"
    progress_path = arm_dir / "progress.json"
    selection_digests: list[str] = []
    counters: dict[str, int] = {
        "binding_solve_calls": 0,
        "binding_proposals": 0,
        "routing_prechecks": 0,
        "routing_builds": 0,
        "routing_solves": 0,
        "point_nogoods": 0,
        "point_nogood_literals": 0,
        "j_trigger_true": 0,
        "j_trigger_false": 0,
        "target_active_port_specs": 0,
    }
    timings: dict[str, float] = {
        "theorem_checker_seconds": theorem_seconds,
        "binding_build_seconds": binding_build_seconds,
        "binding_solve_seconds": 0.0,
        "routing_precheck_seconds": 0.0,
        "routing_build_seconds": 0.0,
        "routing_solve_seconds": 0.0,
        "trigger_evaluator_seconds": 0.0,
        "journal_seconds": 0.0,
    }
    terminal_status = "UNKNOWN"
    censor_status = "UNCENSORED"
    final_reason = "unknown_other"
    event_cap = int(manifest["run_parameters"]["baseline_target_complete_events"])
    deadline = started_wall + arm_watchdog_seconds(manifest, arm)

    while True:
        if time.perf_counter() >= deadline:
            terminal_status = "UNKNOWN"
            censor_status = "CENSORED"
            final_reason = "arm_watchdog_elapsed"
            break

        solve_started = time.perf_counter()
        binding_status = str(
            model.solve(float(manifest["run_parameters"]["per_binding_solve_timeout_seconds"]))
        )
        timings["binding_solve_seconds"] += time.perf_counter() - solve_started
        counters["binding_solve_calls"] += 1

        if binding_status == "INFEASIBLE":
            terminal_status = "INFEASIBLE"
            final_reason = "binding_infeasible"
            break
        if binding_status != "FEASIBLE":
            terminal_status = "UNKNOWN"
            censor_status = "CENSORED"
            final_reason = f"binding_{binding_status.lower()}"
            break

        counters["binding_proposals"] += 1
        selection = model.extract_selection()
        digest = base._selection_digest(selection)
        require(digest not in set(selection_digests), "duplicate selection digest")
        selection_digests.append(digest)
        port_specs = model.extract_port_specs()

        trigger_active: bool | None = None
        active_port_count: int | None = None
        if arm != "A_BASELINE":
            trigger_started = time.perf_counter()
            trigger_active = trigger_is_active(selection, spec)
            active_port_count = target_active_port_spec_count(port_specs)
            timings["trigger_evaluator_seconds"] += time.perf_counter() - trigger_started
            counters["j_trigger_true" if trigger_active else "j_trigger_false"] += 1
            counters["target_active_port_specs"] += active_port_count

        counters["routing_prechecks"] += 1
        precheck_started = time.perf_counter()
        precheck = base.run_exact_routing_precheck(placement_core=core, port_specs=port_specs)
        replay = base.run_exact_routing_precheck(placement_core=core, port_specs=port_specs)
        timings["routing_precheck_seconds"] += time.perf_counter() - precheck_started
        replay_identical = base._precheck_projection(precheck) == base._precheck_projection(replay)
        require(replay_identical, "routing precheck replay mismatch")
        status = str(precheck.get("status", ""))

        if status in base.ROUTING_DOMAIN_PROOF_REJECT_STATUSES:
            require(bool(precheck.get("binding_selection_safe_reject", False)), "precheck did not authorize selection reject")
            require(status == "front_blocked", f"unexpected precheck reject family: {status}")
            if arm == "A_BASELINE":
                # A does not evaluate the theorem trigger from the selection. The
                # already-produced exact precheck witness nevertheless certifies
                # that the target active port is present in this observed event.
                counters["j_trigger_true"] += 1

            feedback = base._apply_feedback(
                model,
                layout=layout,
                selection=selection,
                producer="w0_unary_canary:routing_precheck",
                diagnostics=base._precheck_projection(precheck),
            )
            literal_count = int(feedback["literal_count"])
            require(literal_count == int(manifest["run_parameters"]["expected_point_nogood_literal_count_each"]), "point nogood literal count drift")
            counters["point_nogoods"] += 1
            counters["point_nogood_literals"] += literal_count
            r3_event = None
            if arm != "A_BASELINE":
                r3_event = r3._compact_blocked_precheck(
                    layout=layout,
                    selection=selection,
                    precheck=precheck,
                    replay=replay,
                    event_index=counters["binding_proposals"],
                )
            event = compact_event(
                arm=arm,
                index=counters["binding_proposals"],
                selection_digest=digest,
                precheck=precheck,
                replay_identical=True,
                literal_count=literal_count,
                trigger_active=trigger_active,
                active_port_count=active_port_count,
                r3_event=r3_event,
            )
            timings["journal_seconds"] += append_jsonl(event_path, event)
            if counters["binding_proposals"] % 50 == 0:
                write_json_atomic(
                    progress_path,
                    {
                        "arm": arm,
                        "run_id": run_id,
                        "binding_proposals": counters["binding_proposals"],
                        "selection_sequence_sha256": selection_sequence_sha256(selection_digests),
                        "elapsed_wall_seconds": time.perf_counter() - started_wall,
                        "progress_is_lower_bound": True,
                    },
                )
            if arm in {"A_BASELINE", "B_OBSERVER_NOOP"} and counters["binding_proposals"] >= event_cap:
                terminal_status = "EVENT_CAP_REACHED"
                final_reason = "1007_complete_target_events"
                break
            continue

        require(status == base.ROUTING_DOMAIN_STATUS_FEASIBLE, f"unexpected routing precheck status: {status}")
        counters["routing_builds"] += 1
        route_build_started = time.perf_counter()
        commodities = sorted(
            {
                str(port_spec["commodity"])
                for port_spec in port_specs
                if str(port_spec.get("commodity", ""))
            }
        )
        route_model = base.RoutingSubproblem.from_placement_core(
            core,
            port_specs,
            commodities,
            domain_analysis=precheck["_analysis"],
        )
        route_model.build()
        timings["routing_build_seconds"] += time.perf_counter() - route_build_started
        counters["routing_solves"] += 1
        route_solve_started = time.perf_counter()
        routing_status = str(
            route_model.solve(float(manifest["run_parameters"]["per_routing_solve_timeout_seconds"]))
        )
        timings["routing_solve_seconds"] += time.perf_counter() - route_solve_started
        terminal_status = routing_status
        final_reason = f"routing_{routing_status.lower()}"
        if routing_status == "TIMEOUT":
            censor_status = "CENSORED"
        break

    after_endpoint = capture_identity_snapshot(
        ROOT,
        [*endpoint_protocol["current_endpoint_sources"], *endpoint_protocol["protected_surfaces"]],
    )
    after_outputs = output_surface_snapshot()
    require(before_outputs == after_outputs, "certified/public output surface changed")
    endpoint_transaction = endpoint_neutral_transaction(
        before_sources=before_endpoint,
        after_sources=after_endpoint,
        lower_bound_absent=True,
    )

    total_wall = time.perf_counter() - started_wall
    total_cpu = time.process_time() - started_cpu
    peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    stage_costs: dict[str, float | str] = dict(timings)
    if counters["routing_builds"] == 0:
        stage_costs["routing_build_seconds"] = "NOT_REACHED"
    if counters["routing_solves"] == 0:
        stage_costs["routing_solve_seconds"] = "NOT_REACHED"
    resources = resource_snapshot(stage_costs=stage_costs, total_cost=total_wall)

    if arm == "A_BASELINE":
        arm_outcome = "ARM_TRACE_COMPLETE" if terminal_status == "EVENT_CAP_REACHED" else "CENSORED"
    elif arm == "B_OBSERVER_NOOP":
        arm_outcome = "ARM_TRACE_COMPLETE" if terminal_status == "EVENT_CAP_REACHED" else "CENSORED"
    else:
        arm_outcome = "ARM_TERMINAL_INFEASIBLE" if terminal_status == "INFEASIBLE" else "NO_EFFECT"

    receipt = make_receipt(
        result_kind="canary_arm_run",
        outcome=arm_outcome,
        subject_identity={
            "run_id": run_id,
            "arm": arm,
            "layout_id": layout.record["id"],
            "normalized_layout_sha256": layout.normalized_sha256,
            "implementation_head": git("rev-parse", "HEAD"),
        },
        verified_scope={
            "binding_proposals": counters["binding_proposals"],
            "routing_prechecks": counters["routing_prechecks"],
            "routing_solves": counters["routing_solves"],
            "endpoint_sources_unchanged": True,
            "public_output_surfaces_unchanged": True,
        },
        granted_effects=["may_be_consumed_only_by_the_frozen_three_arm_aggregator"],
        details={
            "schema_version": "zmd_w0_unary_canary_arm_receipt_v1",
            "status": "PASS" if arm_outcome in {"ARM_TRACE_COMPLETE", "ARM_TERMINAL_INFEASIBLE"} else "NON_PASS",
            "arm": arm,
            "terminal_status": terminal_status,
            "censor_status": censor_status,
            "final_reason": final_reason,
            "counters": counters,
            "timings": timings,
            "resource_vector": {
                "wall_seconds": total_wall,
                "cpu_seconds": total_cpu,
                "peak_rss_bytes": peak_rss,
                "stage_costs": resources,
            },
            "model_snapshot_S2": model_snapshot,
            "selection_sequence": {
                "count": len(selection_digests),
                "sha256": selection_sequence_sha256(selection_digests),
            },
            "event_journal": {
                "path": str(event_path),
                "exists": event_path.is_file(),
                "sha256": sha256_file(event_path) if event_path.is_file() else None,
                "size_bytes": event_path.stat().st_size if event_path.is_file() else 0,
            },
            "theorem_checker": {
                "status": theorem_receipt["status"],
                "contextHash": theorem_receipt["proof"]["contextHash"],
                "wall_seconds": theorem_seconds,
            },
            "lowering_application": lowering_receipt,
            "endpoint_transaction": endpoint_transaction,
            "endpoint_identity_before": before_endpoint,
            "endpoint_identity_after": after_endpoint,
            "output_surfaces_before": before_outputs,
            "output_surfaces_after": after_outputs,
            "prerequisites": {
                "contract_outcome": contract_receipt["outcome"],
                "sensitivity_outcome": sensitivity_receipt["outcome"],
            },
        },
        contract_extra={
            "arm_script_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "arm_script_sha256": sha256_file(Path(__file__).resolve()),
            "lowering_module_sha256": sha256_file(HERE / "w0_unary_lowering.py"),
        },
    )
    return receipt


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--contract-receipt", type=Path, required=True)
    parser.add_argument("--sensitivity-receipt", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    arm_dir = args.run_dir.resolve() / args.arm
    arm_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = arm_dir / "arm_receipt.json"
    try:
        contract_receipt = verify_prerequisite_receipt(
            args.contract_receipt.resolve(), kind="lowering_contract_check"
        )
        sensitivity_receipt = verify_prerequisite_receipt(
            args.sensitivity_receipt.resolve(), kind="endpoint_metric_sensitivity_check"
        )
        receipt = run_arm(
            arm=args.arm,
            run_id=args.run_id,
            arm_dir=arm_dir,
            contract_receipt=contract_receipt,
            sensitivity_receipt=sensitivity_receipt,
        )
        text = dump_receipt(receipt, receipt_path)
        sys.stdout.write(text)
        sys.stdout.flush()
        os._exit(0 if receipt["outcome"] in {"ARM_TRACE_COMPLETE", "ARM_TERMINAL_INFEASIBLE"} else 2)
    except (
        ArmError,
        LoweringError,
        ReceiptContractError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
    ) as exc:
        receipt = make_receipt(
            result_kind="canary_arm_run",
            outcome="PROTOCOL_VIOLATION",
            subject_identity={"run_id": args.run_id, "arm": args.arm, "layout_id": "W0-ALIGNMENT"},
            verified_scope={"completed": False, "failure_stage": "arm_execution"},
            granted_effects=["blocks_aggregate_pass"],
            details={
                "schema_version": "zmd_w0_unary_canary_arm_receipt_v1",
                "status": "FAIL",
                "error": str(exc),
            },
        )
        text = dump_receipt(receipt, receipt_path)
        sys.stdout.write(text)
        sys.stdout.flush()
        os._exit(1)


if __name__ == "__main__":
    main()
