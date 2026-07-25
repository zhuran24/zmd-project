#!/usr/bin/env python3
"""Close the fixed 512-pair B1 conditional-halo diagnostic corpus.

This completion gate consumes a canonical run-index JSON; it never discovers
arbitrary result files.  Every one of the 512 control/treatment pairs must
have a clean independent manifest verification and two terminal arms.  The
gate reports diagnostic attribution counts but deliberately leaves the global
upper bound at ``(1190, 34)`` because this corpus is sampled, not a full band.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


SCHEMA = "b1_conditional_halo_diagnostic_completion_v1"
CORPUS_SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
TRANSLATION_ADMISSION_SCHEMA = "b1_conditional_halo_translation_admission_v1"
RUN_INDEX_SCHEMA = "b1_conditional_halo_run_index_v1"
RUN_SCHEMA = "b1_conditional_halo_pair_run_v1"
MANIFEST_VERIFICATION_SCHEMA = "b1_conditional_halo_run_manifest_verification_v1"
MANIFEST_NAME = "SHA256SUMS.recursive"
RUN_RECORD_NAME = "pair_run.json"
EXPECTED_PAIRS = 512
EXPECTED_ARMS = 1024
UNCHANGED_BOUND = [1190, 34]
REQUIRED_MANIFEST_CHECKS = frozenset(
    {
        "recursive_file_set_exact",
        "recursive_hashes_exact",
        "run_schema_exact",
        "case_index_exact_integer",
        "case_id_canonical",
        "pair_id_present",
        "transpose_group_id_present",
        "paired_generation_sha256_well_formed",
        "arm_set_exact",
        "arm_records_are_objects",
        "arm_statuses_known",
        "arm_labels_exact",
        "arm_pair_bindings_match",
        "attribution_exact",
        "run_status_exact",
        "diagnostic_bound_unchanged",
        "claim_boundary_present",
        "dual_checked_sat_evidence_independently_validated",
        "run_record_manifest_binding_exact",
    }
)


class CompletionError(ValueError):
    """The diagnostic corpus is incomplete, stale, or contradictory."""


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise CompletionError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise CompletionError(f"non-finite JSON number forbidden: {value}")


def _load(path: Path, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(
            path.resolve(strict=True).read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except CompletionError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompletionError(f"cannot load {label}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise CompletionError(f"{label} root must be an object")
    return payload


def _array(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CompletionError(f"{label} must be an array")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise CompletionError(f"not a regular provenance file: {resolved}")
    return {
        "path": _display(resolved, root),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _record_path(value: Any, root: Path, label: str) -> Path:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "size_bytes"}:
        raise CompletionError(f"{label} is not an exact file record")
    raw = value.get("path")
    if type(raw) is not str or not raw:
        raise CompletionError(f"{label}.path malformed")
    candidate = Path(raw)
    path = candidate if candidate.is_absolute() else root / candidate
    try:
        actual = _record(path, root)
    except OSError as exc:
        raise CompletionError(f"cannot resolve {label}: {exc}") from exc
    if actual != dict(value):
        raise CompletionError(f"{label} is stale")
    return path.resolve(strict=True)


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _pass_gate(path: Path, root: Path, schema: str, label: str) -> tuple[Mapping[str, Any], dict[str, Any]]:
    value = _load(path, label)
    checks = value.get("checks")
    if (
        value.get("schema_version") != schema
        or value.get("status") != "PASS"
        or value.get("corpus_errors") != []
        or not isinstance(checks, Mapping)
        or not checks
        or any(result is not True for result in checks.values())
    ):
        raise CompletionError(f"{label} is not a corpus-clean all-true PASS")
    return value, _record(path, root)


def _corpus(path: Path, root: Path) -> tuple[Mapping[str, Any], dict[str, Any], Sequence[Any]]:
    corpus = _load(path, "diagnostic corpus")
    cases = _array(corpus.get("cases"), "corpus.cases")
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA
        or corpus.get("status") != "PASS"
        or corpus.get("manifest_state") != "BUILT_BEFORE_RESULTS"
        or corpus.get("solver_results_included") is not False
        or corpus.get("case_count") != EXPECTED_PAIRS
        or len(cases) != EXPECTED_PAIRS
        or corpus.get("corpus_errors") != []
    ):
        raise CompletionError("diagnostic corpus contract drifted")
    for index, raw in enumerate(cases):
        if not isinstance(raw, Mapping):
            raise CompletionError(f"corpus case {index} is not an object")
        if raw.get("case_index") != index or raw.get("case_id") != f"case_{index:03d}":
            raise CompletionError(f"corpus case {index} identity/order drifted")
    pair_ids = [raw.get("pair_id") for raw in cases]
    if any(type(pair_id) is not str or not pair_id for pair_id in pair_ids) or len(set(pair_ids)) != EXPECTED_PAIRS:
        raise CompletionError("corpus does not contain 512 unique pair_id values")
    transpose_groups: dict[str, set[str]] = {}
    for raw in cases:
        group_id = raw.get("transpose_group_id")
        variant = raw.get("variant")
        if type(group_id) is not str or not group_id or variant not in {"original", "transpose"}:
            raise CompletionError("corpus transpose-group identity is malformed")
        transpose_groups.setdefault(group_id, set()).add(str(variant))
    if len(transpose_groups) != 256 or any(
        variants != {"original", "transpose"} for variants in transpose_groups.values()
    ):
        raise CompletionError("corpus is not partitioned into 256 original/transpose groups")
    return corpus, _record(path, root), cases


def _manifest_entries(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CompletionError(f"cannot read recursive manifest: {exc}") from exc
    if not lines:
        raise CompletionError("recursive manifest is empty")
    entries: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\x00\r\n]+)", line)
        if match is None:
            raise CompletionError(f"malformed recursive manifest line {line_number}")
        digest, relative = match.groups()
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or relative != pure.as_posix()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or relative in {MANIFEST_NAME, RUN_RECORD_NAME}
            or relative in entries
            or "\\" in relative
        ):
            raise CompletionError(f"unsafe/duplicate manifest path: {relative!r}")
        entries[relative] = digest
    if list(entries) != sorted(entries):
        raise CompletionError("recursive manifest is not sorted")
    return entries


def _rebuild_manifest(run_dir: Path, manifest: Path) -> dict[str, str]:
    expected = _manifest_entries(manifest)
    actual: dict[str, str] = {}
    for path in sorted(run_dir.rglob("*"), key=lambda item: item.relative_to(run_dir).as_posix()):
        relative = path.relative_to(run_dir).as_posix()
        if path.is_symlink():
            raise CompletionError(f"symlink in run directory: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise CompletionError(f"non-regular run object: {relative}")
        if relative not in {MANIFEST_NAME, RUN_RECORD_NAME}:
            actual[relative] = _sha256(path)
    if not actual or actual != expected:
        raise CompletionError("recursive run manifest does not match current bytes")
    return actual


def _expected_attribution(control: str, treatment: str) -> tuple[str, str]:
    if (control, treatment) == ("CHECKED_SAT", "CHECKED_SAT"):
        return "treatment_survivor", "COMPLETE"
    return "incomplete", "INCOMPLETE"


def _validate_entry(
    entry: Mapping[str, Any],
    case: Mapping[str, Any],
    root: Path,
) -> tuple[str, dict[str, Any]]:
    index = case["case_index"]
    if set(entry) != {
        "case_index",
        "case_id",
        "pair_id",
        "transpose_group_id",
        "pair_run",
        "run_manifest",
        "manifest_verification",
    }:
        raise CompletionError(f"run-index entry {index} key set drifted")
    if (
        entry.get("case_index") != index
        or entry.get("case_id") != case["case_id"]
        or entry.get("pair_id") != case["pair_id"]
        or entry.get("transpose_group_id") != case["transpose_group_id"]
    ):
        raise CompletionError(f"run-index entry {index} identity mismatch")
    run_record_path = _record_path(entry.get("pair_run"), root, f"entry[{index}].pair_run")
    manifest_path = _record_path(entry.get("run_manifest"), root, f"entry[{index}].run_manifest")
    verification_path = _record_path(entry.get("manifest_verification"), root, f"entry[{index}].manifest_verification")
    run_dir = run_record_path.parent
    if manifest_path != run_dir / MANIFEST_NAME or run_record_path.name != RUN_RECORD_NAME:
        raise CompletionError(f"entry {index} run paths are not canonical")
    rebuilt = _rebuild_manifest(run_dir, manifest_path)
    verification = _load(verification_path, f"entry {index} manifest verification")
    verification_checks = verification.get("checks")
    if (
        verification.get("schema_version") != MANIFEST_VERIFICATION_SCHEMA
        or verification.get("status") != "PASS"
        or verification.get("corpus_errors") != []
        or not isinstance(verification_checks, Mapping)
        or set(verification_checks) != REQUIRED_MANIFEST_CHECKS
        or any(result is not True for result in verification_checks.values())
        or verification.get("inputs")
        != {"manifest": _record(manifest_path, root), "pair_run": _record(run_record_path, root)}
        or verification.get("case_index") != index
        or verification.get("case_id") != case["case_id"]
        or verification.get("pair_id") != case["pair_id"]
        or verification.get("transpose_group_id") != case["transpose_group_id"]
    ):
        raise CompletionError(f"entry {index} independent manifest verification is not a bound PASS")
    record = _load(run_record_path, f"entry {index} pair run")
    if record.get("schema_version") != RUN_SCHEMA or record.get("status") != "COMPLETE":
        raise CompletionError(f"entry {index} pair run is not COMPLETE")
    if (
        record.get("case_index") != index
        or record.get("case_id") != case["case_id"]
        or record.get("pair_id") != case["pair_id"]
        or record.get("transpose_group_id") != case["transpose_group_id"]
    ):
        raise CompletionError(f"entry {index} pair run case binding mismatch")
    if record.get("case") != dict(case):
        raise CompletionError(f"entry {index} pair run geometry/corpus binding mismatch")
    source_inputs = record.get("inputs")
    copied_inputs = record.get("input_copies")
    if not isinstance(source_inputs, Mapping) or not isinstance(copied_inputs, Mapping):
        raise CompletionError(f"entry {index} input provenance maps are missing")
    source_admission = source_inputs.get("translation_admission")
    copied_admission = copied_inputs.get("translation_admission")
    copied_admission_path = _record_path(
        copied_admission,
        root,
        f"entry[{index}].input_copies.translation_admission",
    )
    if (
        not isinstance(source_admission, Mapping)
        or source_admission.get("sha256") != copied_admission.get("sha256")
        or source_admission.get("size_bytes") != copied_admission.get("size_bytes")
    ):
        raise CompletionError(f"entry {index} copied translation-admission bytes drifted")
    admission = _load(copied_admission_path, f"entry {index} copied translation admission")
    admission_checks = admission.get("checks")
    if (
        admission.get("schema_version") != TRANSLATION_ADMISSION_SCHEMA
        or admission.get("status") != "PASS"
        or admission.get("case_index") != index
        or admission.get("case_id") != case["case_id"]
        or admission.get("pair_id") != case["pair_id"]
        or admission.get("transpose_group_id") != case["transpose_group_id"]
        or admission.get("model_scope") != "diagnostic_fixed_pattern"
        or admission.get("paired_generation_sha256") != record.get("paired_generation_sha256")
        or admission.get("corpus_errors") != []
        or admission.get("proof_status") != "translation_admission_only_no_solver_or_proof_no_sat_or_unsat_claim"
        or not isinstance(admission_checks, Mapping)
        or not admission_checks
        or any(result is not True for result in admission_checks.values())
    ):
        raise CompletionError(f"entry {index} copied per-case translation admission is not PASS")
    arms = record.get("arms")
    if not isinstance(arms, Mapping) or set(arms) != {"control", "treatment"}:
        raise CompletionError(f"entry {index} arm set drifted")
    control = arms["control"]
    treatment = arms["treatment"]
    if not isinstance(control, Mapping) or not isinstance(treatment, Mapping):
        raise CompletionError(f"entry {index} arm records malformed")
    control_status = control.get("terminal_status")
    treatment_status = treatment.get("terminal_status")
    if (control_status, treatment_status) != ("CHECKED_SAT", "CHECKED_SAT"):
        raise CompletionError(f"entry {index} lacks the exact two CHECKED_SAT arms required by diagnostic v1")
    attribution, required_status = _expected_attribution(str(control_status), str(treatment_status))
    if required_status != "COMPLETE" or record.get("attribution") != attribution:
        raise CompletionError(f"entry {index} attribution is contradictory or stale")
    ledger = record.get("bound_ledger")
    if not isinstance(ledger, Mapping) or dict(ledger) != {
        "control_upper_bound": UNCHANGED_BOUND,
        "global_update_authorized": False,
        "inherited_upper_bound": UNCHANGED_BOUND,
        "treatment_upper_bound": UNCHANGED_BOUND,
    }:
        raise CompletionError(f"entry {index} improperly changes the global bound")
    manifest_record = record.get("artifact_manifest")
    if not isinstance(manifest_record, Mapping) or manifest_record.get("entries") != rebuilt:
        raise CompletionError(f"entry {index} run-record manifest binding mismatch")
    return attribution, {
        "case_index": index,
        "case_id": case["case_id"],
        "pair_id": case["pair_id"],
        "transpose_group_id": case["transpose_group_id"],
        "paired_generation_sha256": record.get("paired_generation_sha256"),
        "control": control_status,
        "treatment": treatment_status,
        "attribution": attribution,
        "pair_run": dict(entry["pair_run"]),
        "run_manifest": dict(entry["run_manifest"]),
        "manifest_verification": dict(entry["manifest_verification"]),
    }


def complete(
    root: Path,
    corpus_path: Path,
    run_index_path: Path,
) -> dict[str, Any]:
    corpus, corpus_record, cases = _corpus(corpus_path, root)
    run_index = _load(run_index_path, "canonical run index")
    entries = _array(run_index.get("entries"), "run_index.entries")
    if (
        run_index.get("schema_version") != RUN_INDEX_SCHEMA
        or run_index.get("status") != "PASS"
        or run_index.get("corpus_errors") != []
        or run_index.get("pair_count") != EXPECTED_PAIRS
        or run_index.get("arm_count") != EXPECTED_ARMS
        or len(entries) != EXPECTED_PAIRS
        or run_index.get("corpus_manifest") != corpus_record
    ):
        raise CompletionError("canonical run-index contract drifted")
    results: list[dict[str, Any]] = []
    attributions: Counter[str] = Counter()
    seen_pairs: set[str] = set()
    for index, raw in enumerate(entries):
        if not isinstance(raw, Mapping):
            raise CompletionError(f"run-index entry {index} is not an object")
        attribution, summary = _validate_entry(raw, cases[index], root)
        pair_sha = summary["paired_generation_sha256"]
        if type(pair_sha) is not str or re.fullmatch(r"[0-9a-f]{64}", pair_sha) is None:
            raise CompletionError(f"entry {index} paired-generation hash malformed")
        if pair_sha in seen_pairs:
            raise CompletionError(f"entry {index} duplicate paired-generation identity")
        seen_pairs.add(pair_sha)
        attributions[attribution] += 1
        results.append(summary)
    if len(results) != EXPECTED_PAIRS or sum(attributions.values()) != EXPECTED_PAIRS:
        raise CompletionError("diagnostic pair accounting is not exact")
    return {
        "schema_version": SCHEMA,
        "status": "PASS",
        "project_root": str(root),
        "inputs": {
            "corpus_manifest": corpus_record,
            "run_index": _record(run_index_path, root),
        },
        "completion_contract": {
            "required_pairs": EXPECTED_PAIRS,
            "required_arms": EXPECTED_ARMS,
            "actual_pairs": len(results),
            "actual_arms": 2 * len(results),
            "unknown_arms": 0,
            "monotonicity_contradictions": 0,
            "unique_pair_ids": EXPECTED_PAIRS,
            "transpose_groups": 256,
        },
        "attribution_counts": {key: attributions.get(key, 0) for key in ("treatment_survivor",)},
        "paired_results": results,
        "bound_ledger": {
            "old_upper_bound": UNCHANGED_BOUND,
            "control_upper_bound": UNCHANGED_BOUND,
            "treatment_upper_bound": UNCHANGED_BOUND,
            "new_upper_bound": UNCHANGED_BOUND,
            "global_update_authorized": False,
            "reason": "sampled 512-case diagnostic is not a full lex-better band scan",
        },
        "surviving_band": {
            "scope": "diagnostic_sample_only",
            "global_band": "unchanged_not_rescanned",
            "sample_treatment_survivors": attributions.get("treatment_survivor", 0),
        },
        "corpus_errors": [],
        "proof_status": "diagnostic_completion_only_no_global_unsat_or_upper_bound_upgrade",
        "claim_boundary": [
            "all 512 sampled control/treatment pairs have independently rechecked complete assignments",
            "diagnostic v1 accepts only exact dual CHECKED_SAT pair evidence",
            "sample results do not lower U or establish full-band UNSAT",
            "does not prove a witness, attainability, routing feasibility, or global optimality",
            "research artifact; not production CERTIFIED evidence",
        ],
        "next_round_candidate": {
            "candidate": "full_band_or_second_weapon_only_after_adversarial_review",
            "reason": "diagnostic attribution must be reviewed before any broader encoder/band claim",
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--run-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        print("FAIL: output already exists", file=sys.stderr)
        return 2
    try:
        root = args.project_root.resolve(strict=True)
        payload = complete(root, args.corpus, args.run_index)
    except (CompletionError, OSError) as exc:
        payload = {
            "schema_version": SCHEMA,
            "status": "INCOMPLETE",
            "project_root": str(args.project_root.resolve(strict=False)),
            "completion_contract": {
                "required_pairs": EXPECTED_PAIRS,
                "required_arms": EXPECTED_ARMS,
                "actual_pairs": 0,
                "actual_arms": 0,
            },
            "bound_ledger": {
                "old_upper_bound": UNCHANGED_BOUND,
                "new_upper_bound": UNCHANGED_BOUND,
                "global_update_authorized": False,
            },
            "corpus_errors": [f"{type(exc).__name__}: {exc}"],
            "claim_boundary": ["diagnostic completion failed closed; no claim is authorized"],
        }
    try:
        _exclusive_json(output, payload)
    except OSError as exc:
        print(f"FAIL: cannot write completion record: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": payload["status"], "output": str(output)}, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
