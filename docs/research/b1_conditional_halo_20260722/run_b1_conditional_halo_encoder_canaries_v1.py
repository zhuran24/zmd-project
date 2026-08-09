#!/usr/bin/env python3
"""Run fail-closed mutation canaries against one paired R2 translation."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCHEMA = "b1_conditional_halo_encoder_canaries_v1"
GATE = "verify_b1_conditional_halo_translation_v1.py"
CORPUS_SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
GEOMETRY_SCHEMA = "b1_conditional_halo_geometry_admission_v1"
META_SCHEMA = "b1_conditional_halo_fixed_rectangle_metadata_v1"
VAR_MAP_SCHEMA = "b1_conditional_halo_fixed_rectangle_var_map_v1"


class CanaryError(ValueError):
    """A canary fixture or expected rejection failed closed."""


def _reject(value: str) -> Any:
    raise CanaryError(f"non-finite JSON number forbidden: {value}")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise CanaryError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.resolve(strict=True).read_bytes(), object_pairs_hook=_pairs, parse_constant=_reject)
    if not isinstance(value, Mapping):
        raise CanaryError("metadata root must be object")
    return value


def _write_json(path: Path, payload: Any) -> None:
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)


def _write_bytes(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)


def _record(path: Path, root: Path) -> dict[str, Any]:
    raw = path.resolve(strict=True).read_bytes()
    try:
        display = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        display = str(path.resolve())
    return {"path": display, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _reseal_meta(source: Path, output: Path, opb: Path, root: Path) -> None:
    payload = dict(_load(source))
    outputs = dict(payload["outputs"])
    outputs["opb"] = _record(opb, root)
    resolved_output = output.resolve()
    try:
        display_output = resolved_output.relative_to(root.resolve()).as_posix()
    except ValueError:
        # Mutated canary fixtures are disposable and may live on another
        # filesystem.  Their retained result still binds every authoritative
        # input byte; the temporary absolute path is only replay metadata.
        display_output = str(resolved_output)
    outputs["metadata"] = {"path": display_output}
    payload["outputs"] = outputs
    _write_json(output, payload)


def _decrement_header(lines: list[str]) -> None:
    marker = "#constraint= "
    before, tail = lines[0].split(marker, 1)
    count_text, after = tail.split(" ", 1)
    lines[0] = f"{before}{marker}{int(count_text) - 1} {after}"


def _increment_header(lines: list[str]) -> None:
    marker = "#constraint= "
    before, tail = lines[0].split(marker, 1)
    count_text, after = tail.split(" ", 1)
    lines[0] = f"{before}{marker}{int(count_text) + 1} {after}"


def _run_gate(
    args: argparse.Namespace, root: Path, mutation: Mapping[str, Path], output: Path
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(Path(__file__).with_name(GATE)),
        "--project-root",
        str(root),
        "--geometry-admission",
        str(args.geometry_admission),
        "--corpus",
        str(args.corpus),
        "--case-index",
        str(args.case_index),
        "--model-scope",
        args.model_scope,
        "--control-opb",
        str(mutation.get("control_opb", args.control_opb)),
        "--control-meta",
        str(mutation.get("control_meta", args.control_meta)),
        "--control-var-map",
        str(args.control_var_map),
        "--treatment-opb",
        str(mutation.get("treatment_opb", args.treatment_opb)),
        "--treatment-meta",
        str(mutation.get("treatment_meta", args.treatment_meta)),
        "--treatment-var-map",
        str(args.treatment_var_map),
        "--output",
        str(output),
    ]
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _main(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    root = args.project_root.resolve(strict=True)
    geometry = _load(args.geometry_admission)
    corpus = _load(args.corpus)
    control_meta = _load(args.control_meta)
    treatment_meta = _load(args.treatment_meta)
    control_var_map = _load(args.control_var_map)
    treatment_var_map = _load(args.treatment_var_map)
    if (
        geometry.get("schema_version") != GEOMETRY_SCHEMA
        or geometry.get("status") != "PASS"
        or geometry.get("corpus_errors") != []
    ):
        raise CanaryError("geometry admission is not a clean PASS")
    cases = corpus.get("cases")
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA
        or corpus.get("status") != "PASS"
        or corpus.get("case_count") != 512
        or corpus.get("corpus_errors") != []
        or not isinstance(cases, Sequence)
        or isinstance(cases, (str, bytes))
        or len(cases) != 512
        or not 0 <= args.case_index < 512
    ):
        raise CanaryError("diagnostic corpus is not a clean ordered 512-case PASS")
    case = cases[args.case_index]
    if not isinstance(case, Mapping):
        raise CanaryError("selected corpus case is not an object")
    case_id = case.get("case_id")
    logical_pair_id = case.get("pair_id")
    transpose_group_id = case.get("transpose_group_id")
    if (
        case.get("case_index") != args.case_index
        or case_id != f"case_{args.case_index:03d}"
        or type(logical_pair_id) is not str
        or not logical_pair_id
        or type(transpose_group_id) is not str
        or not transpose_group_id
    ):
        raise CanaryError("selected corpus case identity is malformed")
    input_records = {
        "geometry_admission": _record(args.geometry_admission, root),
        "corpus_manifest": _record(args.corpus, root),
        "control_opb": _record(args.control_opb, root),
        "control_metadata": _record(args.control_meta, root),
        "control_var_map": _record(args.control_var_map, root),
        "treatment_opb": _record(args.treatment_opb, root),
        "treatment_metadata": _record(args.treatment_meta, root),
        "treatment_var_map": _record(args.treatment_var_map, root),
    }
    paired_generation_sha256 = control_meta.get("paired_generation_sha256")
    if (
        type(paired_generation_sha256) is not str
        or len(paired_generation_sha256) != 64
        or any(character not in "0123456789abcdef" for character in paired_generation_sha256)
    ):
        raise CanaryError("paired-generation SHA256 is malformed")
    for arm, metadata, var_map in (
        ("control", control_meta, control_var_map),
        ("treatment", treatment_meta, treatment_var_map),
    ):
        outputs = metadata.get("outputs")
        if (
            metadata.get("schema_version") != META_SCHEMA
            or metadata.get("status") != "PASS"
            or metadata.get("arm") != arm
            or metadata.get("model_scope") != args.model_scope
            or metadata.get("paired_generation_sha256") != paired_generation_sha256
            or metadata.get("case") != dict(case)
            or metadata.get("geometry_admission") != input_records["geometry_admission"]
            or metadata.get("corpus_manifest") != input_records["corpus_manifest"]
            or not isinstance(outputs, Mapping)
            or outputs.get("opb") != input_records[f"{arm}_opb"]
            or outputs.get("var_map") != input_records[f"{arm}_var_map"]
            or var_map.get("schema_version") != VAR_MAP_SCHEMA
            or var_map.get("status") != "PASS"
            or var_map.get("model_scope") != args.model_scope
            or var_map.get("paired_generation_sha256") != paired_generation_sha256
            or var_map.get("case") != dict(case)
        ):
            raise CanaryError(f"{arm} model bytes/metadata/variable-map binding drifted")
    if control_var_map != treatment_var_map:
        raise CanaryError("paired variable maps are not byte-equivalent objects")
    work = args.output_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    control_lines = args.control_opb.resolve(strict=True).read_text(encoding="ascii").splitlines()
    treatment_lines = args.treatment_opb.resolve(strict=True).read_text(encoding="ascii").splitlines()
    if len(control_lines) < 4 or len(treatment_lines) != len(control_lines) + 1:
        raise CanaryError("paired OPB line counts do not have a one-constraint treatment delta")
    halo_line = treatment_lines[-1]
    fixtures: dict[str, dict[str, Path]] = {}

    lines = [*control_lines[:-1]]
    opb = work / "deletion_unsealed.control.opb"
    _write_bytes(opb, ("\n".join(lines) + "\n").encode("ascii"))
    meta = work / "deletion_unsealed.control.meta.json"
    _reseal_meta(args.control_meta, meta, opb, root)
    fixtures["deletion_unsealed"] = {"control_opb": opb, "control_meta": meta}

    lines = [*control_lines[:-1]]
    _decrement_header(lines)
    opb = work / "deletion_resealed.control.opb"
    _write_bytes(opb, ("\n".join(lines) + "\n").encode("ascii"))
    meta = work / "deletion_resealed.control.meta.json"
    _reseal_meta(args.control_meta, meta, opb, root)
    fixtures["deletion_resealed"] = {"control_opb": opb, "control_meta": meta}

    if ">= 6650 ;" not in halo_line:
        raise CanaryError("treatment final line is not the expected halo RHS")
    lines = [*treatment_lines[:-1], halo_line.replace(">= 6650 ;", ">= 6651 ;")]
    opb = work / "wrong_rhs.treatment.opb"
    _write_bytes(opb, ("\n".join(lines) + "\n").encode("ascii"))
    meta = work / "wrong_rhs.treatment.meta.json"
    _reseal_meta(args.treatment_meta, meta, opb, root)
    fixtures["wrong_rhs"] = {"treatment_opb": opb, "treatment_meta": meta}

    lines = [*control_lines, halo_line]
    _increment_header(lines)
    opb = work / "arm_contamination.control.opb"
    _write_bytes(opb, ("\n".join(lines) + "\n").encode("ascii"))
    meta = work / "arm_contamination.control.meta.json"
    _reseal_meta(args.control_meta, meta, opb, root)
    fixtures["arm_contamination"] = {"control_opb": opb, "control_meta": meta}

    results = {}
    for name, mutation in fixtures.items():
        gate_output = work / f"{name}.gate.json"
        completed = _run_gate(args, root, mutation, gate_output)
        killed = completed.returncode != 0
        results[name] = {
            "killed": killed,
            "exit_code": completed.returncode,
            "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
            "gate_output_created": gate_output.exists(),
        }
        if not killed:
            raise CanaryError(f"mutation canary survived: {name}")
    payload = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "case_index": args.case_index,
        "case_id": case_id,
        "pair_id": logical_pair_id,
        "transpose_group_id": transpose_group_id,
        "model_scope": args.model_scope,
        "paired_generation_sha256": paired_generation_sha256,
        "inputs": input_records,
        "all_killed": True,
        "canaries": results,
        "canary_names": sorted(results),
        "runner_source": _record(Path(__file__), root),
        "gate_source": _record(Path(__file__).with_name(GATE), root),
        "argv": [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)],
        "proof_status": "mutation_testing_only_no_solver_or_proof_run",
        "claim_boundary": [
            "mutation canaries are byte-bound to one paired diagnostic model",
            "does not assert either arm SAT or UNSAT",
            "does not establish a new upper bound, witness, attainability, or optimality",
            "research artifact; not production CERTIFIED evidence",
        ],
    }
    _write_json(args.output.resolve(), payload)
    print(json.dumps({"status": "PASS", "all_killed": True, "output": str(args.output.resolve())}, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--case-index", type=int, required=True)
    parser.add_argument(
        "--model-scope", choices=("diagnostic_fixed_pattern", "band_any_pattern"), default="diagnostic_fixed_pattern"
    )
    for arm in ("control", "treatment"):
        parser.add_argument(f"--{arm}-opb", type=Path, required=True)
        parser.add_argument(f"--{arm}-meta", type=Path, required=True)
        parser.add_argument(f"--{arm}-var-map", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return _main(_parser().parse_args(argv), argv)


if __name__ == "__main__":
    raise SystemExit(main())
