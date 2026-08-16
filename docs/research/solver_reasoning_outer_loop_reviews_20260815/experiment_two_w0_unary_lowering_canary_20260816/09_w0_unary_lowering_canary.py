#!/usr/bin/env python3
"""Run one isolated arm of the W0 unary-lowering canary.

The implementation lives entirely in the research dossier. It imports the
existing exact binding/routing models without modifying them, loads W0 through
the frozen Phase -1 adapter, and writes research-only journals and receipts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from types import ModuleType
from typing import Any, Mapping, MutableMapping, Sequence


ARMS = {"A_BASELINE", "B_OBSERVER_NOOP", "C_UNARY_LOWERING"}
PROTOCOL_FREEZE_COMMIT = "0339c745b6c7f498fc989398de380a78578fc785"


class CanaryError(RuntimeError):
    """The frozen canary contract cannot be honored."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CanaryError(message)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value)]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CanaryError(f"cannot read JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise CanaryError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        _json_safe(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git(code_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=code_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CanaryError(f"cannot create import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class JsonlJournal:
    """Append compact JSON records with one write per line."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        self.count = 0
        self.seconds = 0.0

    def append(self, payload: Mapping[str, Any]) -> None:
        started = time.perf_counter()
        encoded = (
            json.dumps(
                _json_safe(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        written = os.write(self._fd, encoded)
        if written != len(encoded):
            raise OSError(f"short journal write: expected {len(encoded)}, wrote {written}")
        self.count += 1
        self.seconds += time.perf_counter() - started

    def close(self) -> None:
        if self._fd >= 0:
            os.fsync(self._fd)
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> JsonlJournal:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb
        self.close()


def _verify_file_identity(root: Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    relative = str(spec["path"])
    path = root / relative
    _require(path.is_file(), f"missing pinned file: {relative}")
    actual = _sha256(path)
    expected = str(spec["sha256"])
    _require(actual == expected, f"SHA-256 mismatch for {relative}: {actual}")
    return {"path": relative, "sha256": actual, "size_bytes": path.stat().st_size}


def _assert_manifest_identity(
    *,
    code_root: Path,
    evidence_root: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PROTOCOL_FREEZE_COMMIT, "HEAD"],
        cwd=code_root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _require(completed.returncode == 0, "protocol freeze commit is not an ancestor of code HEAD")
    _require(
        manifest.get("protocol_freeze_commit") == PROTOCOL_FREEZE_COMMIT,
        "canary manifest protocol commit mismatch",
    )
    code_receipts = [
        _verify_file_identity(code_root, spec) for spec in manifest["code_root_files"]
    ]
    evidence_receipts = [
        _verify_file_identity(evidence_root, spec) for spec in manifest["evidence_root_files"]
    ]
    contaminated = {
        str(name): os.environ[str(name)]
        for name in manifest["forbidden_nonempty_env"]
        if os.environ.get(str(name), "").strip()
    }
    _require(not contaminated, f"forbidden research environment is set: {contaminated}")
    parameters = manifest["run_parameters"]
    os.environ["EXACT_BINDING_CP_SAT_WORKERS"] = str(parameters["binding_workers"])
    os.environ["EXACT_ROUTING_CP_SAT_WORKERS"] = str(parameters["routing_workers"])
    return {
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "code_head": _git(code_root, "rev-parse", "HEAD"),
        "code_files": code_receipts,
        "evidence_files": evidence_receipts,
        "forbidden_env": "CLEAR",
    }


def _run_theorem_checker(
    *,
    python: Path,
    code_root: Path,
    evidence_root: Path,
) -> tuple[dict[str, Any], float]:
    checker = code_root / (
        "docs/research/solver_reasoning_outer_loop_reviews_20260815/"
        "experiment_one_w0_ghost_front_offline_certificate_20260815/"
        "03_check_w0_ghost_front_certificate.py"
    )
    started = time.perf_counter()
    completed = subprocess.run(
        [
            str(python),
            str(checker),
            "--repo-root",
            str(evidence_root),
            "--coverage",
            "off",
        ],
        cwd=code_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(code_root)},
        timeout=120,
    )
    elapsed = time.perf_counter() - started
    _require(completed.returncode == 0, f"W0 theorem checker failed: {completed.stderr}")
    try:
        receipt = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CanaryError(f"W0 theorem checker returned invalid JSON: {exc}") from exc
    _require(receipt.get("status") == "PASS", "W0 theorem checker did not PASS")
    _require(
        receipt.get("proof", {}).get("judgment_id") == "J-W0-GHOST-FRONT-BOUNDARY-041-V1",
        "W0 theorem checker returned another Judgment",
    )
    return receipt, elapsed


def _constraint_kind(constraint: Any) -> str:
    kinds = (
        "linear",
        "exactly_one",
        "at_most_one",
        "bool_or",
        "bool_and",
        "bool_xor",
        "all_diff",
        "table",
        "automaton",
        "element",
        "circuit",
        "routes",
        "inverse",
        "reservoir",
        "int_div",
        "int_mod",
        "int_prod",
        "lin_max",
        "interval",
        "no_overlap",
        "no_overlap_2d",
        "cumulative",
        "dummy_constraint",
    )
    matches = [kind for kind in kinds if getattr(constraint, f"has_{kind}")()]
    _require(len(matches) == 1, f"constraint has ambiguous/unknown kind: {matches}")
    return matches[0]


def _model_snapshot(model: Any) -> dict[str, Any]:
    proto = model.model.Proto()
    variables = [
        {
            "index": index,
            "name": str(variable.name),
            "domain": [int(value) for value in variable.domain],
        }
        for index, variable in enumerate(proto.variables)
    ]
    constraints: list[dict[str, Any]] = []
    for index, constraint in enumerate(proto.constraints):
        kind = _constraint_kind(constraint)
        item: dict[str, Any] = {
            "index": index,
            "name": str(constraint.name),
            "kind": kind,
            "enforcement_literals": [int(value) for value in constraint.enforcement_literal],
        }
        if kind == "linear":
            item["linear"] = {
                "vars": [int(value) for value in constraint.linear.vars],
                "coeffs": [int(value) for value in constraint.linear.coeffs],
                "domain": [int(value) for value in constraint.linear.domain],
            }
        elif kind == "exactly_one":
            item["exactly_one"] = {
                "literals": [int(value) for value in constraint.exactly_one.literals]
            }
        else:
            item["payload_text"] = str(getattr(constraint, kind))
        constraints.append(item)
    return {
        "schema_version": "zmd_cp_model_snapshot_v1",
        "model_name": str(proto.name),
        "variables": variables,
        "constraints": constraints,
        "search_strategy": [str(value) for value in proto.search_strategy],
        "has_objective": bool(proto.has_objective()),
        "objective_text": str(proto.objective) if proto.has_objective() else "",
        "assumptions": [int(value) for value in proto.assumptions],
        "solution_hint_text": str(proto.solution_hint) if proto.has_solution_hint() else "",
        "symmetry_text": str(proto.symmetry) if proto.has_symmetry() else "",
    }


def _target_metadata(model: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    slot_id = str(target["slot_id"])
    _require(slot_id in model.generic_output_vars, f"target slot is absent: {slot_id}")
    variables = model.generic_output_vars[slot_id]
    labels = list(variables)
    unused_label = str(target["unused_label"])
    _require(unused_label in variables, "target slot lacks __unused__")
    indexes = {str(label): int(var.Index()) for label, var in variables.items()}
    names = {str(label): str(var.Name()) for label, var in variables.items()}
    return {
        "slot_id": slot_id,
        "domain_labels": labels,
        "domain_variable_indexes": list(indexes.values()),
        "domain_variable_names": names,
        "unused_label": unused_label,
        "unused_variable_index": indexes[unused_label],
        "active_labels": [label for label in labels if label != unused_label],
        "active_variable_indexes": [
            indexes[label] for label in labels if label != unused_label
        ],
    }


def _selection_target_value(selection: Mapping[str, Any], slot_id: str) -> str | None:
    outputs = selection.get("generic_outputs", {})
    if not isinstance(outputs, Mapping):
        return None
    value = outputs.get(slot_id)
    return None if value is None else str(value)


def _is_triggered(value: str | None, unused_label: str) -> bool:
    return value is not None and value != unused_label


def _active_target_port_spec_count(port_specs: Sequence[Mapping[str, Any]]) -> int:
    return sum(
        1
        for spec in port_specs
        if str(spec.get("instance_id", "")) == "boundary_port_041"
        and str(spec.get("type", "")) == "out"
    )


def _typed_seconds(value: float, reached: bool) -> float | str:
    return float(value) if reached else "NOT_REACHED"


def _resource_snapshot() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return int(usage.ru_maxrss) * 1024


def _write_progress(path: Path, payload: Mapping[str, Any]) -> None:
    _write_json(path, payload)


def _run_arm(args: argparse.Namespace) -> dict[str, Any]:
    arm = str(args.arm)
    _require(arm in ARMS, f"unknown arm: {arm}")
    code_root = args.code_root.resolve()
    evidence_root = args.evidence_root.resolve()
    output_dir = args.output_dir.resolve()
    _require(not output_dir.exists(), f"arm output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    manifest = _load_json(args.manifest)
    contract = _load_json(args.contract)
    parameters = manifest["run_parameters"]
    identity = _assert_manifest_identity(
        code_root=code_root,
        evidence_root=evidence_root,
        manifest=manifest,
    )

    if str(code_root) not in sys.path:
        sys.path.insert(0, str(code_root))
    phase_dir = code_root / (
        "docs/research/solver_reasoning_outer_loop_reviews_20260815/phase_minus1"
    )
    base = _load_module("phase_minus1_harness", phase_dir / "phase_minus1_harness.py")
    compact = _load_module(
        "phase_minus1_harness_r3", phase_dir / "phase_minus1_harness_r3.py"
    )
    base.ROOT = evidence_root

    theorem_receipt, checker_seconds = _run_theorem_checker(
        python=args.python,
        code_root=code_root,
        evidence_root=evidence_root,
    )

    total_started = time.perf_counter()
    cpu_started = time.process_time()
    input_started = time.perf_counter()
    corpus = base._load_manifest()
    frozen = base._load_frozen_inputs(corpus)
    record = base._record_by_id(corpus, str(manifest["layout_id"]))
    layout = base._load_layout(record, corpus, frozen)
    _require(
        layout.normalized_sha256 == manifest["normalized_layout_sha256"],
        "normalized W0 layout identity mismatch",
    )
    core = base._occupied_core(layout, frozen)
    input_seconds = time.perf_counter() - input_started

    build_started = time.perf_counter()
    model = base._new_binding_model(layout, frozen)
    target = _target_metadata(model, contract)
    baseline_snapshot = _model_snapshot(model)
    baseline_digest = _canonical_digest(baseline_snapshot)
    baseline_constraint_count = len(baseline_snapshot["constraints"])
    treatment_enabled = arm == "C_UNARY_LOWERING"
    if treatment_enabled:
        unused_var = model.generic_output_vars[target["slot_id"]][target["unused_label"]]
        model.model.Add(unused_var == 1).WithName(str(contract["lowering"]["constraint_name"]))
    model_snapshot = _model_snapshot(model)
    model_snapshot_digest = _canonical_digest(model_snapshot)
    build_seconds = time.perf_counter() - build_started
    _write_json(output_dir / "model_snapshot.json", model_snapshot)

    target_domain_size = len(target["domain_labels"])
    target_effective_values = 1 if treatment_enabled else target_domain_size
    generic_domain_sizes = [
        len(values) for values in model.generic_output_vars.values()
    ]
    s2_envelope = {
        "evidence_type": "MODEL_SIZE_AND_BOX_DOMAIN",
        "variable_count": len(model_snapshot["variables"]),
        "constraint_count": len(model_snapshot["constraints"]),
        "generic_output_slot_count": len(model.generic_output_vars),
        "generic_output_domain_cardinality_sum": sum(generic_domain_sizes),
        "generic_output_box_bits": math.fsum(
            math.log2(size) for size in generic_domain_sizes if size > 0
        ),
        "target_slot_id": target["slot_id"],
        "target_slot_domain_labels": list(target["domain_labels"]),
        "target_slot_model_domain_cardinality": target_domain_size,
        "target_slot_effective_allowed_value_count": target_effective_values,
        "treatment_added_constraint_count": len(model_snapshot["constraints"])
        - baseline_constraint_count,
    }

    event_path = output_dir / "events.jsonl"
    feedback_path = output_dir / "feedback.jsonl"
    progress_path = output_dir / "progress.json"
    counters: Counter[str] = Counter()
    precheck_statuses: Counter[str] = Counter()
    signature_digests: Counter[str] = Counter()
    signature_atoms: Counter[str] = Counter()
    selection_digests: list[str] = []
    target_values: Counter[str] = Counter()
    posthoc_trigger_count = 0
    runtime_trigger_count = 0
    runtime_trigger_evaluated = arm != "A_BASELINE"
    active_target_port_spec_total = 0
    active_target_port_spec_proposals = 0
    first_non_j_event_index: int | None = None
    first_routing_build_event_index: int | None = None
    first_routing_solve_event_index: int | None = None
    pending_feedback: MutableMapping[str, Any] | None = None
    terminal_status = "UNKNOWN"
    censor_status = "UNCENSORED"
    final_reason = "unknown_other"
    trigger_seconds = 0.0
    binding_solve_seconds = 0.0
    routing_precheck_seconds = 0.0
    routing_build_seconds = 0.0
    routing_solve_seconds = 0.0
    routing_build_reached = False
    routing_solve_reached = False
    event_cap = int(parameters["event_cap"])
    watchdog = float(parameters["arm_watchdog_seconds"])
    binding_cap = float(parameters["binding_solve_cap_seconds"])
    routing_cap = float(parameters["routing_solve_cap_seconds"])
    progress_every = int(parameters["progress_every_events"])

    with JsonlJournal(event_path) as event_journal, JsonlJournal(feedback_path) as feedback_journal:
        while True:
            elapsed = time.perf_counter() - total_started
            if elapsed >= watchdog:
                terminal_status = "UNKNOWN"
                censor_status = "WALL_TIMEOUT_END_TO_END"
                final_reason = "arm_watchdog"
                break

            solve_started = time.perf_counter()
            binding_status = str(model.solve(min(binding_cap, max(0.01, watchdog - elapsed))))
            binding_solve_seconds += time.perf_counter() - solve_started
            counters["binding_solve_calls"] += 1

            if pending_feedback is not None:
                next_selection = (
                    model.extract_selection() if binding_status == "FEASIBLE" else None
                )
                outcome = {
                    "schema_version": "zmd_w0_canary_feedback_v1",
                    "record_type": "feedback_outcome",
                    "event_index": int(pending_feedback["event_index"]),
                    "arm": arm,
                    "effect": (
                        next_selection is None
                        or base._selection_digest(next_selection)
                        != pending_feedback["selection_digest"]
                    ),
                    "next_status": binding_status,
                    "next_selection_digest": (
                        base._selection_digest(next_selection)
                        if next_selection is not None
                        else None
                    ),
                    "terminal_outcome": (
                        binding_status if binding_status != "FEASIBLE" else None
                    ),
                }
                feedback_journal.append(outcome)
                counters["feedback_outcomes"] += 1
                pending_feedback = None

            if binding_status == "FEASIBLE":
                counters["binding_proposals"] += 1
                event_index = int(counters["binding_proposals"])
                selection = model.extract_selection()
                selection_digest = base._selection_digest(selection)
                selection_digests.append(selection_digest)
                target_value = _selection_target_value(selection, target["slot_id"])
                target_values[str(target_value)] += 1
                posthoc_trigger = _is_triggered(target_value, target["unused_label"])
                posthoc_trigger_count += int(posthoc_trigger)
                if not posthoc_trigger and first_non_j_event_index is None:
                    first_non_j_event_index = event_index
                runtime_trigger: bool | None = None
                if runtime_trigger_evaluated:
                    trigger_started = time.perf_counter()
                    runtime_trigger = _is_triggered(target_value, target["unused_label"])
                    trigger_seconds += time.perf_counter() - trigger_started
                    runtime_trigger_count += int(runtime_trigger)

                port_specs = model.extract_port_specs()
                active_specs = _active_target_port_spec_count(port_specs)
                active_target_port_spec_total += active_specs
                active_target_port_spec_proposals += int(active_specs > 0)

                pre_started = time.perf_counter()
                precheck = base.run_exact_routing_precheck(
                    placement_core=core,
                    port_specs=port_specs,
                )
                replay = base.run_exact_routing_precheck(
                    placement_core=core,
                    port_specs=port_specs,
                )
                routing_precheck_seconds += time.perf_counter() - pre_started
                counters["routing_prechecks"] += 1
                status = str(precheck.get("status", ""))
                precheck_statuses[status] += 1

                if status in base.ROUTING_DOMAIN_PROOF_REJECT_STATUSES:
                    _require(
                        bool(precheck.get("binding_selection_safe_reject", False)),
                        f"routing precheck {status} did not authorize selection reject",
                    )
                    event = compact._compact_blocked_precheck(
                        layout=layout,
                        selection=selection,
                        precheck=precheck,
                        replay=replay,
                        event_index=event_index,
                    )
                    event.update(
                        {
                            "arm": arm,
                            "target_slot_id": target["slot_id"],
                            "target_assignment": target_value,
                            "posthoc_j_trigger": posthoc_trigger,
                            "runtime_j_trigger": runtime_trigger,
                            "target_active_port_spec_count": active_specs,
                        }
                    )
                    event_journal.append(event)
                    signature_digest = str(event.get("local_signature_digest", ""))
                    if signature_digest:
                        signature_digests[signature_digest] += 1
                    for signature, count in event.get("local_signature_counts", {}).items():
                        signature_atoms[str(signature)] += int(count)
                    literal_count = int(base._selection_literal_count(model, selection))
                    model.add_nogood_cut(selection)
                    applied = {
                        "schema_version": "zmd_w0_canary_feedback_v1",
                        "record_type": "feedback_applied",
                        "event_index": event_index,
                        "arm": arm,
                        "selection_digest": selection_digest,
                        "producer": f"routing_precheck:{status}",
                        "consumer": "PortBindingModel.add_nogood_cut",
                        "feedback_form": "point_nogood",
                        "literal_count": literal_count,
                    }
                    feedback_journal.append(applied)
                    pending_feedback = applied
                    counters["point_nogoods"] += 1
                    counters["point_nogood_literals"] += literal_count
                    counters["binding_routing_round_trips"] += 1
                elif status == base.ROUTING_DOMAIN_STATUS_FEASIBLE:
                    if first_routing_build_event_index is None:
                        first_routing_build_event_index = event_index
                    commodities = sorted(
                        {
                            str(spec["commodity"])
                            for spec in port_specs
                            if str(spec.get("commodity", ""))
                        }
                    )
                    route_model = base.RoutingSubproblem.from_placement_core(
                        core,
                        port_specs,
                        commodities,
                        domain_analysis=precheck["_analysis"],
                    )
                    route_build_started = time.perf_counter()
                    route_model.build()
                    routing_build_seconds += time.perf_counter() - route_build_started
                    routing_build_reached = True
                    if first_routing_solve_event_index is None:
                        first_routing_solve_event_index = event_index
                    route_solve_started = time.perf_counter()
                    routing_status = str(route_model.solve(routing_cap))
                    routing_solve_seconds += time.perf_counter() - route_solve_started
                    routing_solve_reached = True
                    counters["routing_solves"] += 1
                    common_event = {
                        "arm": arm,
                        "target_slot_id": target["slot_id"],
                        "target_assignment": target_value,
                        "posthoc_j_trigger": posthoc_trigger,
                        "runtime_j_trigger": runtime_trigger,
                        "target_active_port_spec_count": active_specs,
                    }
                    if routing_status == "FEASIBLE":
                        event_journal.append(
                            {
                                "schema_version": "zmd_w0_canary_event_v1",
                                "record_type": "terminal_routing",
                                "event_index": event_index,
                                "layout_id": layout.record["id"],
                                "status": "FEASIBLE",
                                "route_count": len(route_model.extract_routes()),
                                **common_event,
                            }
                        )
                        terminal_status = "FEASIBLE"
                        final_reason = "layout_feasible"
                        break
                    event = compact._compact_routing_event(
                        layout=layout,
                        selection=selection,
                        routing_status=routing_status,
                        event_index=event_index,
                        route_model=route_model,
                    )
                    event.update(common_event)
                    event_journal.append(event)
                    if routing_status == "INFEASIBLE":
                        literal_count = int(base._selection_literal_count(model, selection))
                        model.add_nogood_cut(selection)
                        applied = {
                            "schema_version": "zmd_w0_canary_feedback_v1",
                            "record_type": "feedback_applied",
                            "event_index": event_index,
                            "arm": arm,
                            "selection_digest": selection_digest,
                            "producer": "routing_solve:INFEASIBLE",
                            "consumer": "PortBindingModel.add_nogood_cut",
                            "feedback_form": "point_nogood",
                            "literal_count": literal_count,
                        }
                        feedback_journal.append(applied)
                        pending_feedback = applied
                        counters["point_nogoods"] += 1
                        counters["point_nogood_literals"] += literal_count
                        counters["binding_routing_round_trips"] += 1
                    else:
                        terminal_status = "UNKNOWN"
                        censor_status = "SOLVER_TIMEOUT_ROUTING"
                        final_reason = "routing_solver_timeout"
                        break
                else:
                    raise CanaryError(f"unexpected routing precheck status: {status!r}")

                if event_index % progress_every == 0:
                    _write_progress(
                        progress_path,
                        {
                            "schema_version": "zmd_w0_canary_progress_v1",
                            "arm": arm,
                            "event_index": event_index,
                            "elapsed_wall_seconds": time.perf_counter() - total_started,
                            "binding_proposals": int(counters["binding_proposals"]),
                            "j_trigger_true_posthoc": posthoc_trigger_count,
                            "routing_solves": int(counters["routing_solves"]),
                            "last_precheck_status": status,
                        },
                    )
                if event_index >= event_cap:
                    terminal_status = "UNKNOWN"
                    censor_status = "EVENT_CAP_REACHED"
                    final_reason = "frozen_event_cap"
                    break
                continue

            if binding_status == "INFEASIBLE":
                terminal_status = "INFEASIBLE"
                empty_domains = model.extract_empty_binding_domain_instances()
                final_reason = "binding_empty_domain" if empty_domains else "binding_exhausted"
                event_journal.append(
                    {
                        "schema_version": "zmd_w0_canary_event_v1",
                        "record_type": "terminal_binding",
                        "arm": arm,
                        "event_index": int(counters["binding_proposals"]) + 1,
                        "status": "INFEASIBLE",
                        "reason": final_reason,
                        "empty_binding_domain_instances": empty_domains,
                    }
                )
                break
            if binding_status == "INVALID_INPUT":
                terminal_status = "UNKNOWN"
                censor_status = "INVALID_INPUT"
                final_reason = "binding_invalid_input"
                break
            terminal_status = "UNKNOWN"
            censor_status = "SOLVER_TIMEOUT_BINDING"
            final_reason = "binding_solver_timeout"
            break

        event_record_count = event_journal.count
        feedback_record_count = feedback_journal.count
        journal_seconds = event_journal.seconds + feedback_journal.seconds

    total_wall = time.perf_counter() - total_started
    process_cpu = time.process_time() - cpu_started
    distinct_selection_count = len(set(selection_digests))
    ordered_selection_digest_hash = hashlib.sha256(
        "\n".join(selection_digests).encode("ascii")
    ).hexdigest()
    stage_numeric = {
        "input_load": input_seconds,
        "binding_build": build_seconds,
        "binding_solve": binding_solve_seconds,
        "routing_precheck": routing_precheck_seconds,
        "trigger_evaluator": trigger_seconds,
        "theorem_checker": checker_seconds,
        "journal": journal_seconds,
    }
    if routing_build_reached:
        stage_numeric["routing_build"] = routing_build_seconds
    if routing_solve_reached:
        stage_numeric["routing_solve"] = routing_solve_seconds
    denominator = math.fsum(stage_numeric.values())
    stage_shares = {
        key: (value / denominator if denominator > 0 else 0.0)
        for key, value in stage_numeric.items()
    }

    summary = {
        "schema_version": "zmd_w0_unary_lowering_canary_arm_v1",
        "research_only": True,
        "arm": arm,
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "identity": identity,
        "theorem_checker": {
            "status": theorem_receipt["status"],
            "judgment_id": theorem_receipt["proof"]["judgment_id"],
            "wall_seconds": checker_seconds,
        },
        "layout_id": layout.record["id"],
        "normalized_layout_sha256": layout.normalized_sha256,
        "lowering": {
            "enabled": treatment_enabled,
            "constraint_name": (
                contract["lowering"]["constraint_name"] if treatment_enabled else None
            ),
            "baseline_snapshot_digest": baseline_digest,
            "model_snapshot_digest": model_snapshot_digest,
            "target": target,
        },
        "s2_envelope": s2_envelope,
        "counters": dict(counters),
        "selection": {
            "selection_count": len(selection_digests),
            "distinct_selection_count": distinct_selection_count,
            "ordered_selection_digest_hash": ordered_selection_digest_hash,
            "target_assignment_distribution": dict(sorted(target_values.items())),
            "posthoc_j_trigger_true_count": posthoc_trigger_count,
            "posthoc_j_trigger_false_count": len(selection_digests)
            - posthoc_trigger_count,
            "runtime_trigger_evaluated": runtime_trigger_evaluated,
            "runtime_j_trigger_true_count": (
                runtime_trigger_count if runtime_trigger_evaluated else "NOT_EVALUATED"
            ),
            "first_non_j_event_index": first_non_j_event_index,
            "target_active_port_spec_total": active_target_port_spec_total,
            "target_active_port_spec_proposals": active_target_port_spec_proposals,
        },
        "failure_spectrum": {
            "precheck_status_distribution": dict(sorted(precheck_statuses.items())),
            "local_signature_digest_distribution": dict(sorted(signature_digests.items())),
            "local_signature_atom_distribution": dict(sorted(signature_atoms.items())),
            "first_routing_build_event_index": first_routing_build_event_index,
            "first_routing_solve_event_index": first_routing_solve_event_index,
        },
        "terminalStatus": terminal_status,
        "censorStatus": censor_status,
        "finalReason": final_reason,
        "resources": {
            "total_wall_seconds": total_wall,
            "process_cpu_seconds": process_cpu,
            "peak_rss_bytes": _resource_snapshot(),
            "input_load_seconds": input_seconds,
            "binding_build_seconds": build_seconds,
            "binding_solve_seconds": binding_solve_seconds,
            "binding_solve_calls": int(counters["binding_solve_calls"]),
            "binding_proposals": int(counters["binding_proposals"]),
            "routing_precheck_seconds": routing_precheck_seconds,
            "routing_prechecks": int(counters["routing_prechecks"]),
            "routing_build_seconds": _typed_seconds(
                routing_build_seconds, routing_build_reached
            ),
            "routing_solve_seconds": _typed_seconds(
                routing_solve_seconds, routing_solve_reached
            ),
            "routing_solves": (
                int(counters["routing_solves"])
                if routing_solve_reached
                else "NOT_REACHED"
            ),
            "trigger_evaluator_seconds": (
                trigger_seconds if runtime_trigger_evaluated else "NOT_REACHED"
            ),
            "theorem_checker_seconds": checker_seconds,
            "journal_seconds": journal_seconds,
            "stage_share_over_measured_components": stage_shares,
        },
        "journals": {
            "events": {
                "path": str(event_path),
                "record_count": event_record_count,
                "sha256": _sha256(event_path),
                "size_bytes": event_path.stat().st_size,
            },
            "feedback": {
                "path": str(feedback_path),
                "record_count": feedback_record_count,
                "sha256": _sha256(feedback_path),
                "size_bytes": feedback_path.stat().st_size,
            },
            "pending_feedback_at_stop": pending_feedback is not None,
        },
        "solver_contract": {
            "event_cap": event_cap,
            "watchdog_seconds": watchdog,
            "binding_solve_cap_seconds": binding_cap,
            "routing_solve_cap_seconds": routing_cap,
            "binding_workers": int(parameters["binding_workers"]),
            "routing_workers": int(parameters["routing_workers"]),
            "alternative_cap": None,
            "overload_separation": False,
        },
    }
    _write_json(output_dir / "summary.json", summary)
    _write_json(
        output_dir / "model_metadata.json",
        {
            "schema_version": "zmd_w0_arm_model_metadata_v1",
            "arm": arm,
            "target": target,
            "baseline_snapshot_digest": baseline_digest,
            "model_snapshot_digest": model_snapshot_digest,
            "variable_count": len(model_snapshot["variables"]),
            "constraint_count": len(model_snapshot["constraints"]),
            "baseline_constraint_count": baseline_constraint_count,
        },
    )
    return summary


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=sorted(ARMS), required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        summary = _run_arm(args)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        failure = {
            "schema_version": "zmd_w0_unary_lowering_canary_arm_v1",
            "status": "HARNESS_ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "wall_seconds": time.perf_counter() - started,
        }
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
