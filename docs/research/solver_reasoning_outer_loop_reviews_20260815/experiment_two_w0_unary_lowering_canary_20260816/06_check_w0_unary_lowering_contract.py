#!/usr/bin/env python3
"""Independently audit the W0 unary lowering contract and mutation canaries."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

from ortools.sat.python import cp_model

from w0_canary_receipt_contract import (
    PRELAUNCH_REVISION_COMMIT,
    ReceiptContractError,
    dump_receipt,
    make_receipt,
)
from w0_unary_lowering import (
    LoweringError,
    apply_w0_unary_lowering,
    load_lowering_spec,
    protobuf_sha256,
    target_domain_envelope,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST_PATH = HERE / "03_CANARY_MANIFEST.json"
SPEC_PATH = HERE / "04_W0_UNARY_LOWERING_SPEC.json"
CANONICAL_PROTOCOL = HERE / "01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md"
PRELAUNCH_ADDENDUM = HERE / "03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md"
RECEIPT_SCHEMA = HERE / "03B_RECEIPT_ENVELOPE_SCHEMA_V1.json"


class ContractError(RuntimeError):
    """The lowering contract, identity, or mutation sensitivity failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise ContractError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest(), size


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ContractError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def verify_runtime(manifest: Mapping[str, Any]) -> dict[str, Any]:
    import ortools

    runtime = manifest["runtime_identity"]
    executable = str(Path(sys.executable).resolve())
    expected_executable = str(Path(runtime["python_executable"]).resolve())
    require(executable == expected_executable, f"wrong interpreter: {executable}")
    require(
        sys.version.split()[0] == str(runtime["python_version"]),
        f"Python version drift: {sys.version.split()[0]}",
    )
    require(
        str(ortools.__version__) == str(runtime["ortools_version"]),
        f"OR-Tools version drift: {ortools.__version__}",
    )
    return {
        "python_executable": executable,
        "python_version": sys.version.split()[0],
        "ortools_version": str(ortools.__version__),
    }


def verify_file_identities(manifest: Mapping[str, Any]) -> dict[str, Any]:
    checked: list[dict[str, Any]] = []

    theorem = manifest["theorem_identity"]
    theorem_specs = [
        ("judgment", theorem["judgment_path"], theorem["judgment_sha256"], None),
        ("proof", theorem["proof_path"], theorem["proof_sha256"], None),
        ("checker", theorem["checker_path"], theorem["checker_sha256"], None),
    ]
    for role, relative, expected_sha, expected_size in theorem_specs:
        actual_sha, actual_size = sha256_file(ROOT / str(relative))
        require(actual_sha == expected_sha, f"{role} SHA drift: {relative}")
        if expected_size is not None:
            require(actual_size == expected_size, f"{role} size drift: {relative}")
        checked.append({"role": role, "path": relative, "sha256": actual_sha, "size": actual_size})

    for relative, spec in manifest["frozen_inputs"].items():
        actual_sha, actual_size = sha256_file(ROOT / str(relative))
        require(actual_sha == spec["sha256"], f"frozen input SHA drift: {relative}")
        require(actual_size == int(spec["size_bytes"]), f"frozen input size drift: {relative}")
        checked.append({"role": "frozen_input", "path": relative, "sha256": actual_sha, "size": actual_size})

    for group_name in ("production_source_identities", "research_adapter_identities"):
        for relative, expected_sha in manifest[group_name].items():
            actual_sha, actual_size = sha256_file(ROOT / str(relative))
            require(actual_sha == expected_sha, f"{group_name} SHA drift: {relative}")
            checked.append({"role": group_name, "path": relative, "sha256": actual_sha, "size": actual_size})

    return {"checked_count": len(checked), "files": checked}


def verify_protocol_freeze(spec: Mapping[str, Any]) -> dict[str, Any]:
    expected = str(spec["protocol_freeze_commit"])
    observed = git("log", "-1", "--format=%H", "--", str(CANONICAL_PROTOCOL.relative_to(ROOT)))
    require(observed == expected, f"protocol freeze commit drift: {observed}")
    diff = subprocess.run(
        ["git", "diff", "--quiet", expected, "--", *[
            str((HERE / name).relative_to(ROOT))
            for name in (
                "00_OWNER_AUTHORIZATION_20260816.md",
                "00_OWNER_SIGNAL_AND_BOUNDARY.md",
                "01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md",
                "02_ENDPOINT_METRICS_PROTOCOL_V1.md",
                "02_ENDPOINT_METRICS_PROTOCOL_V1.json",
                "03_CANARY_MANIFEST.json",
            )
        ]],
        cwd=ROOT,
        check=False,
    )
    require(diff.returncode == 0, "a v1 frozen protocol file changed after the freeze commit")

    expected_prelaunch = str(spec["prelaunch_revision_commit"])
    require(
        expected_prelaunch == PRELAUNCH_REVISION_COMMIT,
        "lowering spec prelaunch revision identity is stale",
    )
    observed_prelaunch = git(
        "log",
        "-1",
        "--format=%H",
        "--",
        str(PRELAUNCH_ADDENDUM.relative_to(ROOT)),
    )
    require(
        observed_prelaunch == expected_prelaunch,
        f"prelaunch revision commit drift: {observed_prelaunch}",
    )
    prelaunch_diff = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            expected_prelaunch,
            "--",
            str(PRELAUNCH_ADDENDUM.relative_to(ROOT)),
            str(RECEIPT_SCHEMA.relative_to(ROOT)),
        ],
        cwd=ROOT,
        check=False,
    )
    require(
        prelaunch_diff.returncode == 0,
        "a prelaunch v1.1 contract file changed after the revision commit",
    )
    return {
        "protocol_freeze_commit": observed,
        "prelaunch_revision_commit": observed_prelaunch,
        "frozen_files_unchanged": True,
    }


def verify_spec_identity(spec: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    theorem = manifest["theorem_identity"]
    judgment = spec["judgment"]
    require(judgment["id"] == theorem["judgment_id"], "Judgment ID mismatch")
    for field in ("problemHash", "objectiveHash", "contextHash"):
        require(judgment[field] == theorem[field], f"spec {field} mismatch")
    context = manifest["fixed_context"]
    scope = spec["scope"]
    require(scope["layout_id"] == context["layout_id"], "layout ID mismatch")
    require(
        scope["normalized_layout_sha256"] == context["normalized_layout_sha256"],
        "normalized layout hash mismatch",
    )
    require(scope["ghost_rect"] == context["ghost_rect"], "ghost rect mismatch")
    require(spec["trigger"]["slot_id"] == context["target_slot_id"], "target slot mismatch")
    require(
        sorted(spec["trigger"]["expected_baseline_domain"])
        == sorted(context["target_baseline_values"]),
        "target baseline domain mismatch",
    )


def run_theorem_checker(manifest: Mapping[str, Any]) -> dict[str, Any]:
    checker = ROOT / str(manifest["theorem_identity"]["checker_path"])
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(checker), "--coverage", "off"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    require(result.returncode == 0, f"W0 theorem checker failed: {result.stderr.strip()}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError(f"W0 theorem checker emitted invalid JSON: {exc}") from exc
    require(payload.get("status") == "PASS", "W0 theorem checker did not PASS")
    require(payload.get("coverage") is None, "coverage-off theorem check unexpectedly used observations")
    return {
        "status": "PASS",
        "wall_seconds": time.perf_counter() - started,
        "proof_step_count": payload["proof"]["proof_step_count"],
        "contextHash": payload["proof"]["contextHash"],
    }


def load_phase_minus1_module() -> Any:
    phase_dir = ROOT / "docs/research/solver_reasoning_outer_loop_reviews_20260815/phase_minus1"
    sys.path.insert(0, str(phase_dir))
    try:
        return importlib.import_module("phase_minus1_harness")
    finally:
        sys.path.pop(0)


def build_w0_model(base: Any) -> tuple[Any, Any, Any]:
    corpus = base._load_manifest()
    frozen = base._load_frozen_inputs(corpus)
    record = base._record_by_id(corpus, "W0-ALIGNMENT")
    layout = base._load_layout(record, corpus, frozen)
    model = base._new_binding_model(layout, frozen)
    return model, layout, frozen


def _proto_nonconstraint_projection(proto: Any) -> dict[str, Any]:
    objective_present = bool(proto.has_objective())
    floating_objective_present = bool(proto.has_floating_point_objective())
    solution_hint_present = bool(proto.has_solution_hint())
    symmetry_present = bool(proto.has_symmetry())
    return {
        "name": str(proto.name),
        "variables": [str(value) for value in proto.variables],
        "objective_present": objective_present,
        "objective": str(proto.objective) if objective_present else None,
        "floating_objective_present": floating_objective_present,
        "floating_objective": (
            str(proto.floating_point_objective)
            if floating_objective_present
            else None
        ),
        "search_strategy": [str(value) for value in proto.search_strategy],
        "solution_hint_present": solution_hint_present,
        "solution_hint": str(proto.solution_hint) if solution_hint_present else None,
        "assumptions": list(proto.assumptions),
        "symmetry_present": symmetry_present,
        "symmetry": str(proto.symmetry) if symmetry_present else None,
    }


def audit_proto_delta(
    baseline_model: Any,
    treatment_model: Any,
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = baseline_model.model.Proto()
    treatment = treatment_model.model.Proto()
    expected_new = int(spec["lowering"]["expected_new_constraint_count"])
    require(
        len(treatment.constraints) - len(baseline.constraints) == expected_new,
        "treatment constraint-count delta is not exactly one",
    )
    require(
        _proto_nonconstraint_projection(treatment)
        == _proto_nonconstraint_projection(baseline),
        "proto changed outside the constraint list",
    )
    baseline_constraints = [str(value) for value in baseline.constraints]
    treatment_prefix = [
        str(treatment.constraints[index]) for index in range(len(baseline.constraints))
    ]
    require(
        treatment_prefix == baseline_constraints,
        "an existing constraint changed before the appended unary constraint",
    )

    new_constraint = treatment.constraints[len(treatment.constraints) - 1]
    require(new_constraint.has_linear(), "new constraint is not linear")
    constraint_type = "linear"
    target_slot = str(spec["lowering"]["slot_id"])
    forced_value = str(spec["lowering"]["forced_value"])
    target_var = treatment_model.generic_output_vars[target_slot][forced_value]
    require(
        list(new_constraint.linear.vars) == [int(target_var.Index())],
        "unit constraint targets wrong variable",
    )
    require(
        list(new_constraint.linear.coeffs)
        == [int(spec["lowering"]["expected_coefficient"])],
        "unit constraint coefficient drift",
    )
    require(
        list(new_constraint.linear.domain) == list(spec["lowering"]["expected_domain"]),
        "unit constraint domain drift",
    )
    return {
        "baseline_proto_sha256": protobuf_sha256(baseline),
        "treatment_proto_sha256": protobuf_sha256(treatment),
        "variable_count": len(baseline.variables),
        "baseline_constraint_count": len(baseline.constraints),
        "treatment_constraint_count": len(treatment.constraints),
        "new_constraint_type": constraint_type,
        "target_variable_index": int(target_var.Index()),
        "target_variable_name": str(target_var.Name()),
        "new_constraint_sha256": protobuf_sha256(new_constraint),
        "existing_constraint_prefix_equal": True,
        "nonconstraint_projection_equal": True,
    }


def truth_table(spec: Mapping[str, Any]) -> dict[str, str]:
    labels = sorted(str(value) for value in spec["trigger"]["expected_baseline_domain"])
    inactive = str(spec["trigger"]["inactive_value"])
    outcomes: dict[str, str] = {}
    for selected_label in labels:
        model = cp_model.CpModel()
        variables = {label: model.NewBoolVar(f"v_{label}") for label in labels}
        model.AddExactlyOne(list(variables.values()))
        model.Add(variables[inactive] == 1)
        model.Add(variables[selected_label] == 1)
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        status = solver.Solve(model)
        outcomes[selected_label] = solver.StatusName(status)
    require(outcomes[inactive] in {"OPTIMAL", "FEASIBLE"}, "inactive value is not allowed")
    for label in labels:
        if label != inactive:
            require(outcomes[label] == "INFEASIBLE", f"active value survived truth table: {label}")
    return outcomes


MUTATION_NAMES = (
    "wrong_slot",
    "wrong_forced_value",
    "extra_constraint",
    "stale_context",
)


def run_single_mutation_probe(name: str) -> dict[str, Any]:
    manifest = read_json(MANIFEST_PATH)
    spec = load_lowering_spec(SPEC_PATH)
    base = load_phase_minus1_module()
    try:
        if name == "wrong_slot":
            mutated = copy.deepcopy(spec)
            mutated["lowering"]["slot_id"] = "boundary_port_042:out:0"
            apply_w0_unary_lowering(object(), mutated)
        elif name == "wrong_forced_value":
            mutated = copy.deepcopy(spec)
            mutated["lowering"]["forced_value"] = "source_ore"
            apply_w0_unary_lowering(object(), mutated)
        elif name == "extra_constraint":
            baseline, _layout, _frozen = build_w0_model(base)
            treatment, _layout2, _frozen2 = build_w0_model(base)
            apply_w0_unary_lowering(treatment, spec)
            slot = str(spec["lowering"]["slot_id"])
            treatment.model.Add(
                treatment.generic_output_vars[slot]["source_ore"] == 0
            )
            audit_proto_delta(baseline, treatment, spec)
        elif name == "stale_context":
            mutated = copy.deepcopy(spec)
            mutated["judgment"]["contextHash"] = "0" * 64
            verify_spec_identity(mutated, manifest)
        else:  # pragma: no cover - argparse owns the enum
            raise ContractError(f"unsupported mutation probe: {name}")
    except (ContractError, LoweringError, KeyError, TypeError, ValueError, IndexError) as exc:
        return {"name": name, "killed": True, "error": str(exc)}
    raise ContractError(f"mutation canary survived: {name}")


def run_full_proto_probe() -> dict[str, Any]:
    spec = load_lowering_spec(SPEC_PATH)
    base = load_phase_minus1_module()
    baseline_model, layout, _frozen = build_w0_model(base)
    treatment_model, treatment_layout, _frozen2 = build_w0_model(base)
    require(
        layout.normalized_sha256 == treatment_layout.normalized_sha256,
        "arm layout identity mismatch",
    )
    baseline_envelope = target_domain_envelope(baseline_model, spec)
    application = apply_w0_unary_lowering(treatment_model, spec)
    proto_audit = audit_proto_delta(baseline_model, treatment_model, spec)
    table = truth_table(spec)
    return {
        "layout_id": layout.record["id"],
        "normalized_layout_sha256": layout.normalized_sha256,
        "target_domain": baseline_envelope,
        "application_receipt": application,
        "proto_audit": proto_audit,
        "truth_table": table,
    }


def run_full_proto_probe_child() -> dict[str, Any]:
    child = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--full-proto-probe"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    require(
        child.returncode == 0,
        "full proto child failed: "
        f"rc={child.returncode}; stderr={child.stderr.strip()!r}",
    )
    try:
        payload = json.loads(child.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError(f"full proto child emitted invalid JSON: {exc}") from exc
    require(payload.get("proto_audit", {}).get("new_constraint_type") == "linear", "full proto audit did not close")
    return payload


def run_mutation_canaries() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name in MUTATION_NAMES:
        child = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--mutation-probe", name],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        require(
            child.returncode == 0,
            f"mutation child failed for {name}: rc={child.returncode}; "
            f"stderr={child.stderr.strip()!r}",
        )
        try:
            payload = json.loads(child.stdout)
        except json.JSONDecodeError as exc:
            raise ContractError(
                f"mutation child emitted invalid JSON for {name}: {exc}"
            ) from exc
        require(payload.get("name") == name, f"mutation child identity drift: {name}")
        require(payload.get("killed") is True, f"mutation canary survived: {name}")
        results.append(payload)
    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--mutation-probe", choices=MUTATION_NAMES, default=None)
    parser.add_argument("--full-proto-probe", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.full_proto_probe:
        try:
            payload = run_full_proto_probe()
            sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            sys.stdout.flush()
            os._exit(0)
        except (ContractError, LoweringError, OSError, KeyError, TypeError, ValueError, IndexError) as exc:
            sys.stdout.write(
                json.dumps(
                    {"status": "FAIL", "error": str(exc)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            sys.stdout.flush()
            os._exit(1)

    if args.mutation_probe is not None:
        try:
            payload = run_single_mutation_probe(args.mutation_probe)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0
        except (ContractError, LoweringError, OSError, KeyError, TypeError, ValueError, IndexError) as exc:
            print(
                json.dumps(
                    {"name": args.mutation_probe, "killed": False, "error": str(exc)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 1

    started = time.perf_counter()
    try:
        manifest = read_json(MANIFEST_PATH)
        require(manifest.get("status") == "FROZEN_BEFORE_IMPLEMENTATION", "manifest is not frozen")
        spec = load_lowering_spec(SPEC_PATH)
        runtime = verify_runtime(manifest)
        identities = verify_file_identities(manifest)
        freeze = verify_protocol_freeze(spec)
        verify_spec_identity(spec, manifest)
        theorem = run_theorem_checker(manifest)

        proto_probe = run_full_proto_probe_child()
        baseline_envelope = proto_probe["target_domain"]
        application = proto_probe["application_receipt"]
        proto_audit = proto_probe["proto_audit"]
        table = proto_probe["truth_table"]
        mutations = run_mutation_canaries()

        receipt = make_receipt(
            result_kind="lowering_contract_check",
            outcome="PASS",
            subject_identity={
                "judgment_id": spec["judgment"]["id"],
                "layout_id": proto_probe["layout_id"],
                "normalized_layout_sha256": proto_probe["normalized_layout_sha256"],
                "lowering_spec_path": str(SPEC_PATH.relative_to(ROOT)),
            },
            verified_scope={
                "theorem_currency": "PASS",
                "file_identity_count": identities["checked_count"],
                "proto_delta_exact": True,
                "truth_table_complete": True,
                "mutation_canary_count": len(mutations),
            },
            granted_effects=[
                "permits_endpoint_metric_sensitivity_check",
                "marks_W0_unary_lowering_as_contract_validated_for_this_pinned_context",
            ],
            details={
                "schema_version": "zmd_w0_unary_lowering_contract_receipt_v1",
                "status": "PASS",
                "research_only": True,
                "runtime": runtime,
                "file_identities": identities,
                "protocol_freeze": freeze,
                "theorem_checker": theorem,
                "target_domain": baseline_envelope,
                "application_receipt": application,
                "proto_audit": proto_audit,
                "truth_table": table,
                "mutation_canaries": mutations,
                "wall_seconds": time.perf_counter() - started,
            },
            contract_extra={
                "lowering_spec_path": str(SPEC_PATH.relative_to(ROOT)),
                "lowering_spec_sha256": sha256_file(SPEC_PATH)[0],
            },
        )
        text = dump_receipt(receipt, args.output)
        print(text, end="")
        return 0
    except (
        ContractError,
        LoweringError,
        ReceiptContractError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
    ) as exc:
        receipt = make_receipt(
            result_kind="lowering_contract_check",
            outcome="FAIL_SOUNDNESS",
            subject_identity={
                "judgment_id": "J-W0-GHOST-FRONT-BOUNDARY-041-V1",
                "lowering_spec_path": str(SPEC_PATH.relative_to(ROOT)),
            },
            verified_scope={
                "completed": False,
                "failure_stage": "contract_check",
            },
            granted_effects=["blocks_true_canary_arms"],
            details={
                "schema_version": "zmd_w0_unary_lowering_contract_receipt_v1",
                "status": "FAIL",
                "error": str(exc),
                "wall_seconds": time.perf_counter() - started,
            },
        )
        text = dump_receipt(receipt, args.output)
        print(text, end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
