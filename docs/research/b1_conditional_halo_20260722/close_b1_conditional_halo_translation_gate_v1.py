#!/usr/bin/env python3
"""Close the geometry/corpus/paired-translation admission for one R2 case."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA = "b1_conditional_halo_translation_admission_v1"
GEOMETRY_SCHEMA = "b1_conditional_halo_geometry_admission_v1"
CORPUS_SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
META_SCHEMA = "b1_conditional_halo_fixed_rectangle_metadata_v1"
GATE_SCHEMA = "b1_conditional_halo_translation_gate_v1"
CANARY_SCHEMA = "b1_conditional_halo_encoder_canaries_v1"
CANARY_RUNNER_NAME = "run_b1_conditional_halo_encoder_canaries_v1.py"
TRANSLATION_GATE_NAME = "verify_b1_conditional_halo_translation_v1.py"


class CloseError(ValueError):
    """The translation-admission closure failed closed."""


def _reject(value: str) -> Any:
    raise CloseError(f"non-finite JSON number forbidden: {value}")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise CloseError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load(path: Path, field: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.resolve(strict=True).read_bytes(), object_pairs_hook=_pairs, parse_constant=_reject)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloseError(f"{field} parse failure: {exc}") from exc
    if not isinstance(value, Mapping):
        raise CloseError(f"{field} root must be object")
    return value


def _record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    raw = resolved.read_bytes()
    try:
        display = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        display = str(resolved)
    return {"path": display, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)


def _main(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    root = args.project_root.resolve(strict=True)
    geometry = _load(args.geometry_admission, "geometry admission")
    corpus = _load(args.corpus, "corpus")
    gate = _load(args.translation_gate, "translation gate")
    canaries = _load(args.canaries, "canaries")
    control_meta = _load(args.control_meta, "control metadata")
    treatment_meta = _load(args.treatment_meta, "treatment metadata")
    if (
        geometry.get("schema_version") != GEOMETRY_SCHEMA
        or geometry.get("status") != "PASS"
        or geometry.get("corpus_errors") != []
    ):
        raise CloseError("geometry admission is not PASS")
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA
        or corpus.get("status") != "PASS"
        or corpus.get("case_count") != 512
        or corpus.get("corpus_errors") != []
    ):
        raise CloseError("diagnostic corpus is not PASS/512")
    if (
        gate.get("schema_version") != GATE_SCHEMA
        or gate.get("status") != "PASS"
        or gate.get("missing") != []
        or gate.get("unexpected") != []
        or gate.get("corpus_errors") != []
    ):
        raise CloseError("translation gate is not a clean PASS")
    checks = gate.get("checks")
    if not isinstance(checks, Mapping) or not checks or any(value is not True for value in checks.values()):
        raise CloseError("translation-gate checks are not all true")
    paired = gate.get("paired_diff")
    if (
        not isinstance(paired, Mapping)
        or paired.get("exactly_one_conditional_halo") is not True
        or paired.get("removed") != []
        or len(paired.get("added", [])) != 1
    ):
        raise CloseError("translation gate did not close the exact one-constraint diff")
    if (
        canaries.get("schema_version") != CANARY_SCHEMA
        or canaries.get("status") != "PASS"
        or canaries.get("all_killed") is not True
    ):
        raise CloseError("encoder canaries are not all killed")
    expected_canaries = {"deletion_unsealed", "deletion_resealed", "wrong_rhs", "arm_contamination"}
    canary_results = canaries.get("canaries")
    if (
        not isinstance(canary_results, Mapping)
        or set(canary_results) != expected_canaries
        or canaries.get("canary_names") != sorted(expected_canaries)
        or any(not isinstance(value, Mapping) or value.get("killed") is not True for value in canary_results.values())
    ):
        raise CloseError("canary result corpus is incomplete")
    pair_id = gate.get("paired_generation_sha256")
    case_index = gate.get("case_index")
    model_scope = gate.get("model_scope")
    cases = corpus.get("cases")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)) or len(cases) != 512:
        raise CloseError("diagnostic corpus cases are not an exact 512-array")
    if type(case_index) is not int or not 0 <= case_index < len(cases):
        raise CloseError("translation gate case index is malformed")
    corpus_case = cases[case_index]
    if not isinstance(corpus_case, Mapping):
        raise CloseError("selected corpus case is not an object")
    logical_pair_id = corpus_case.get("pair_id")
    transpose_group_id = corpus_case.get("transpose_group_id")
    case_id = corpus_case.get("case_id")
    if (
        corpus_case.get("case_index") != case_index
        or case_id != f"case_{case_index:03d}"
        or type(logical_pair_id) is not str
        or not logical_pair_id
        or type(transpose_group_id) is not str
        or not transpose_group_id
    ):
        raise CloseError("selected corpus case identity is malformed")
    gate_case = gate.get("case")
    if not isinstance(gate_case, Mapping):
        raise CloseError("translation gate case binding is missing")
    gate_case_expected = {key: value for key, value in corpus_case.items() if key != "selection_reasons"}
    if dict(gate_case) != gate_case_expected:
        raise CloseError("translation gate case does not match the selected corpus case")
    for arm, metadata in (("control", control_meta), ("treatment", treatment_meta)):
        metadata_case = metadata.get("case")
        if (
            metadata.get("schema_version") != META_SCHEMA
            or metadata.get("status") != "PASS"
            or metadata.get("arm") != arm
            or metadata.get("paired_generation_sha256") != pair_id
            or metadata.get("model_scope") != model_scope
            or not isinstance(metadata_case, Mapping)
            or dict(metadata_case) != dict(corpus_case)
        ):
            raise CloseError(f"{arm} metadata does not bind the admitted pair")
    paired_model_inputs = {
        "geometry_admission": _record(args.geometry_admission, root),
        "corpus_manifest": _record(args.corpus, root),
        "control_opb": _record(args.control_opb, root),
        "control_metadata": _record(args.control_meta, root),
        "control_var_map": _record(args.control_var_map, root),
        "treatment_opb": _record(args.treatment_opb, root),
        "treatment_metadata": _record(args.treatment_meta, root),
        "treatment_var_map": _record(args.treatment_var_map, root),
    }
    if (
        canaries.get("case_index") != case_index
        or canaries.get("case_id") != case_id
        or canaries.get("pair_id") != logical_pair_id
        or canaries.get("transpose_group_id") != transpose_group_id
        or canaries.get("model_scope") != model_scope
        or canaries.get("paired_generation_sha256") != pair_id
        or canaries.get("inputs") != paired_model_inputs
        or canaries.get("runner_source") != _record(Path(__file__).with_name(CANARY_RUNNER_NAME), root)
        or canaries.get("gate_source") != _record(Path(__file__).with_name(TRANSLATION_GATE_NAME), root)
        or canaries.get("proof_status") != "mutation_testing_only_no_solver_or_proof_run"
    ):
        raise CloseError("canaries are not byte-bound to this exact paired model")
    inputs = {
        **paired_model_inputs,
        "translation_gate": _record(args.translation_gate, root),
        "encoder_canaries": _record(args.canaries, root),
    }
    payload = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "case_index": case_index,
        "case_id": case_id,
        "pair_id": logical_pair_id,
        "transpose_group_id": transpose_group_id,
        "model_scope": model_scope,
        "paired_generation_sha256": pair_id,
        "closer_source": _record(Path(__file__), root),
        "argv": [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)],
        "inputs": inputs,
        "checks": {
            "geometry_admission_pass": True,
            "corpus_manifest_512_pass": True,
            "paired_model_bytes_bound": True,
            "corpus_case_pair_identity_bound": True,
            "translation_gate_clean_pass": True,
            "exact_one_constraint_diff": True,
            "all_mutation_canaries_killed": True,
            "canary_pair_identity_and_all_model_bytes_bound": True,
        },
        "corpus_errors": [],
        "proof_status": "translation_admission_only_no_solver_or_proof_no_sat_or_unsat_claim",
        "claim_boundary": [
            "admits translation fidelity for one paired diagnostic only",
            "does not assert either arm SAT or UNSAT",
            "does not establish a new upper bound, witness, attainability, or optimality",
            "research artifact; not production CERTIFIED evidence",
        ],
    }
    _write(args.output.resolve(), payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "case_index": case_index,
                "model_scope": model_scope,
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    for arm in ("control", "treatment"):
        parser.add_argument(f"--{arm}-opb", type=Path, required=True)
        parser.add_argument(f"--{arm}-meta", type=Path, required=True)
        parser.add_argument(f"--{arm}-var-map", type=Path, required=True)
    parser.add_argument("--translation-gate", type=Path, required=True)
    parser.add_argument("--canaries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return _main(_parser().parse_args(argv), argv)


if __name__ == "__main__":
    raise SystemExit(main())
