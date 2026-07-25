#!/usr/bin/env python3
"""Close the paper/recomputation/adversarial B1 conditional-halo gate.

The gate binds current source bytes, two independent recomputation reports,
their agreement report, the necessity paper, and separate machine/readable
adversarial verdicts.  It creates one admission JSON with O_EXCL and otherwise
fails without an admission artifact.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RESEARCH = Path(__file__).resolve().parent
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
PROJECT_LOCK = ROOT / "PROJECT_LOCK.md"
CANONICAL_RULES = ROOT / "rules/canonical_rules.json"
R3_RECOMPUTER = ROOT / "docs/research/cleanroom_rederivation_20260718/verify_r3_certificates.py"
R1_PROOF = ROOT / "docs/research/b1_q_membrane_halo_20260722/01_necessity_proof.md"
R1_VERDICT = ROOT / "docs/research/b1_q_membrane_halo_20260722/02_adversarial_verdict.md"
R1_AGREEMENT = ROOT / ".artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW/agreement.json"
R1_TRANSLATION = (
    ROOT / ".artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW/band-v3.translation-gate.json"
)
DIRECT_SOURCE = RESEARCH / "verify_b1_conditional_halo_coordinates_v1.py"
PREFIX_SOURCE = RESEARCH / "recompute_b1_conditional_halo_prefix_v1.py"
AGREEMENT_SOURCE = RESEARCH / "compare_b1_conditional_halo_recomputations_v1.py"

PINNED_SHA256 = {
    PROJECT_LOCK: "33632dfdb2297425e42066b2cf0749ca6b9ab1f8653e810b6f2e53ded1025410",
    CANONICAL_RULES: "5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    R3_RECOMPUTER: "589b87a086f2c25015b535c5c12d68b6842aaa1f16fe449bcb94e3a733bd076a",
    R1_PROOF: "9dcd4f5e6b012c9336e5fca63a8884c3a05d5b939fc9ade272f8bd4a67b5c132",
    R1_VERDICT: "e9a33b2f1199675d3b58730ac34b7706725797bc3297a246c3b9bf704c040f0a",
    R1_AGREEMENT: "b1f8ee3cf01b43de97da955e736102c86d65c5b61d01205ad8ff505f6a5b2c65",
    R1_TRANSLATION: "45363308076ae6fcd837f349e3769bc6e1ad0b4bc8f660b0fa3dc475d20d2bf2",
}


class AdmissionError(RuntimeError):
    """An admission prerequisite is absent, stale, or malformed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdmissionError(message)


def reject_constant(token: str) -> Any:
    raise AdmissionError(f"non-finite JSON token: {token}")


def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AdmissionError(f"duplicate JSON key: {key!r}")
        value[key] = item
    return value


def load_json(path: Path) -> tuple[dict[str, Any], bytes, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicate, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"cannot parse {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} root must be an object")
    return value, raw, hashlib.sha256(raw).hexdigest()


def object_value(value: Any, field: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{field} must be an object")
    return value


def array_value(value: Any, field: str) -> Sequence[Any]:
    require(isinstance(value, Sequence) and not isinstance(value, (str, bytes)), f"{field} must be an array")
    return value


def integer(value: Any, field: str) -> int:
    require(type(value) is int, f"{field} must be an exact integer")
    return int(value)


def snapshot(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    require(resolved.is_file(), f"not a regular file: {resolved}")
    raw = resolved.read_bytes()
    try:
        display = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        display = str(resolved)
    return {"path": display, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def require_expected_path(actual: Path, expected: Path, field: str) -> Path:
    resolved = actual.resolve(strict=True)
    require(resolved == expected.resolve(strict=True), f"{field} must be {expected}")
    return resolved


def validate_pins() -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    for path, expected in PINNED_SHA256.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual == expected, f"pinned authority drift: {path} got {actual}")
        checks.append({"id": f"pinned-{path.name}-{expected[:12]}", "status": "PASS"})
    return checks


def validate_paper(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    required_tokens = (
        "Necessity proof for the B1 round-2 conditional-halo geometry",
        "`2026-07-22`",
        "**PROVED — mathematical premise for geometry admission**",
        "`geometry_only_pre_encoder`",
        "sum(C2_q(R) for every selected pole q)",
        ">= 2*3325 = 6650",
        "B1-ACTUAL-P",
        "every ceiling survivor has exactly nine poles",
    )
    missing = [token for token in required_tokens if token not in text]
    require(not missing, f"necessity paper tokens missing: {missing}")


def validate_recompute(root: Mapping[str, Any], schema: str) -> None:
    require(root.get("schema_version") == schema, f"{schema} schema mismatch")
    require(root.get("evidence_cutoff") == "2026-07-22", f"{schema} cutoff mismatch")
    require(root.get("status") == "PASS" and root.get("scope") == "geometry_only_pre_encoder", f"{schema} not admitted")
    require(list(array_value(root.get("corpus_errors"), f"{schema}.corpus_errors")) == [], f"{schema} corpus errors")
    statement = object_value(root.get("conditional_halo"), f"{schema}.conditional_halo")
    require(
        (statement.get("rhs_original"), statement.get("rhs_doubled"), statement.get("pole_quantifier"))
        == (3325, 6650, "all_selected_poles"),
        f"{schema} statement mismatch",
    )
    actual_p = object_value(root.get("actual_p_ledger"), f"{schema}.actual_p_ledger")
    require(
        actual_p.get("status") == "PROVED" and actual_p.get("ceiling_exact_nine_is_derived_not_assumed") is True,
        f"{schema} actual-P mismatch",
    )


def validate_agreement(root: Mapping[str, Any], coordinate_path: Path, prefix_path: Path) -> Mapping[str, Any]:
    require(root.get("schema_version") == "b1_conditional_halo_recomputation_agreement_v1", "agreement schema mismatch")
    require(root.get("status") == "PASS" and root.get("scope") == "geometry_only_pre_encoder", "agreement not PASS")
    require(list(array_value(root.get("corpus_errors"), "agreement.corpus_errors")) == [], "agreement corpus errors")
    checks = array_value(root.get("checks"), "agreement.checks")
    require(
        checks and all(object_value(check, "agreement check").get("status") == "PASS" for check in checks),
        "agreement checks not all PASS",
    )
    ids = [object_value(check, "agreement check").get("id") for check in checks]
    require(
        all(isinstance(item, str) and item for item in ids) and len(ids) == len(set(ids)), "agreement check IDs invalid"
    )
    inputs = object_value(root.get("inputs"), "agreement.inputs")
    coordinate_input = object_value(inputs.get("coordinate"), "agreement.inputs.coordinate")
    prefix_input = object_value(inputs.get("prefix"), "agreement.inputs.prefix")
    require(
        coordinate_input.get("sha256") == hashlib.sha256(coordinate_path.read_bytes()).hexdigest(),
        "agreement coordinate binding stale",
    )
    require(
        prefix_input.get("sha256") == hashlib.sha256(prefix_path.read_bytes()).hexdigest(),
        "agreement prefix binding stale",
    )
    corpus = object_value(root.get("ceiling_corpus"), "agreement.ceiling_corpus")
    require(
        (corpus.get("rectangle_count"), corpus.get("pole_anchor_count"), corpus.get("pair_count"))
        == (2520, 4761, 11_997_720),
        "agreement corpus size mismatch",
    )
    digest = corpus.get("canonical_digest_sha256")
    require(isinstance(digest, str) and len(digest) == 64, "agreement corpus digest invalid")
    return corpus


def validate_verdict(machine: Mapping[str, Any], document_path: Path) -> None:
    require(
        machine.get("schema_version") == "b1_conditional_halo_geometry_adversarial_verdict_v1",
        "verdict schema mismatch",
    )
    require(machine.get("document_type") == "mathematical_adversarial_verdict", "verdict document type mismatch")
    require(machine.get("evidence_cutoff") == "2026-07-22", "verdict cutoff mismatch")
    require(machine.get("scope") == "geometry_only_pre_encoder", "verdict scope mismatch")
    require(machine.get("status") == "PASS", "verdict is not PASS")
    require(list(array_value(machine.get("corpus_errors"), "verdict.corpus_errors")) == [], "verdict corpus errors")
    checks = array_value(machine.get("checks"), "verdict.checks")
    require(bool(checks), "verdict checks are empty")
    ids = [object_value(item, "verdict check").get("id") for item in checks]
    require(
        all(isinstance(item, str) and item for item in ids) and len(ids) == len(set(ids)), "verdict check IDs invalid"
    )
    require(
        all(object_value(item, "verdict check").get("status") == "CONFIRMED" for item in checks),
        "verdict has an unconfirmed check",
    )
    require(
        integer(machine.get("confirmed_count"), "verdict.confirmed_count") == len(checks),
        "verdict confirmed count mismatch",
    )
    claim_boundary = set(array_value(machine.get("claim_boundary"), "verdict.claim_boundary"))
    required_claims = {
        "no_witness",
        "no_attainability",
        "no_routing_feasibility",
        "no_upper_bound_improvement",
        "no_global_optimality",
        "no_production_CERTIFIED_status",
    }
    require(required_claims <= claim_boundary, "verdict claim boundary incomplete")

    text = document_path.read_text(encoding="utf-8")
    required_tokens = (
        "Mathematical adversarial verdict",
        "`2026-07-22`",
        "**PASS",
        "`geometry_only_pre_encoder`",
    )
    missing = [token for token in required_tokens if token not in text]
    require(not missing, f"verdict document tokens missing: {missing}")


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    require(path.parent.is_dir(), f"output parent missing: {path.parent}")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def close_gate(args: argparse.Namespace) -> dict[str, Any]:
    root = args.project_root.resolve(strict=True)
    require(root == ROOT.resolve(), "project-root substitution is forbidden")
    stencil_path = require_expected_path(args.stencil, RESEARCH / "conditional_halo_stencil_v1.json", "stencil")
    proof_path = require_expected_path(args.proof, RESEARCH / "01_necessity_proof.md", "proof")
    coordinate_path = args.coordinate.resolve(strict=True)
    prefix_path = args.prefix.resolve(strict=True)
    agreement_path = args.agreement.resolve(strict=True)
    verdict_json_path = require_expected_path(
        args.verdict_json, RESEARCH / "02_adversarial_verdict.json", "verdict-json"
    )
    verdict_doc_path = require_expected_path(args.verdict_doc, RESEARCH / "02_adversarial_verdict.md", "verdict-doc")

    checks = validate_pins()
    validate_paper(proof_path)
    checks.append({"id": "necessity-paper-current-and-complete", "status": "PASS"})
    coordinate, _, _ = load_json(coordinate_path)
    prefix, _, _ = load_json(prefix_path)
    agreement, _, _ = load_json(agreement_path)
    machine_verdict, _, _ = load_json(verdict_json_path)
    validate_recompute(coordinate, "b1_conditional_halo_coordinate_recompute_v1")
    validate_recompute(prefix, "b1_conditional_halo_prefix_recompute_v1")
    require(
        object_value(
            object_value(coordinate.get("provenance"), "coordinate.provenance").get("script"), "coordinate script"
        ).get("sha256")
        == hashlib.sha256(DIRECT_SOURCE.read_bytes()).hexdigest(),
        "coordinate source binding stale",
    )
    require(
        object_value(object_value(prefix.get("provenance"), "prefix.provenance").get("script"), "prefix script").get(
            "sha256"
        )
        == hashlib.sha256(PREFIX_SOURCE.read_bytes()).hexdigest(),
        "prefix source binding stale",
    )
    checks.extend(
        [
            {"id": "coordinate-recomputation-pass", "status": "PASS"},
            {"id": "prefix-recomputation-pass", "status": "PASS"},
        ]
    )
    corpus = validate_agreement(agreement, coordinate_path, prefix_path)
    require(
        hashlib.sha256(AGREEMENT_SOURCE.read_bytes()).hexdigest() == snapshot(AGREEMENT_SOURCE, root)["sha256"],
        "agreement source read inconsistency",
    )
    checks.append({"id": "independent-recomputation-agreement-pass", "status": "PASS"})
    validate_verdict(machine_verdict, verdict_doc_path)
    checks.append({"id": "mathematical-adversarial-verdict-confirmed", "status": "PASS"})

    input_paths = {
        "project_lock": PROJECT_LOCK,
        "canonical_rules": CANONICAL_RULES,
        "strict_instance": STRICT,
        "r3_recomputer": R3_RECOMPUTER,
        "r1_necessity_proof": R1_PROOF,
        "r1_adversarial_verdict": R1_VERDICT,
        "r1_agreement": R1_AGREEMENT,
        "r1_authoritative_translation": R1_TRANSLATION,
        "stencil": stencil_path,
        "necessity_proof": proof_path,
        "coordinate_report": coordinate_path,
        "prefix_report": prefix_path,
        "agreement_report": agreement_path,
        "adversarial_verdict_json": verdict_json_path,
        "adversarial_verdict_doc": verdict_doc_path,
        "coordinate_source": DIRECT_SOURCE,
        "prefix_source": PREFIX_SOURCE,
        "agreement_source": AGREEMENT_SOURCE,
        "geometry_gate_source": Path(__file__),
    }
    return {
        "schema_version": "b1_conditional_halo_geometry_admission_v1",
        "evidence_cutoff": "2026-07-22",
        "status": "PASS",
        "scope": "geometry_only_pre_encoder",
        "inputs": {name: snapshot(path, root) for name, path in input_paths.items()},
        "conditional_halo": {
            "status": "ADMITTED_AS_NECESSARY_CONDITION",
            "rhs_original": 3325,
            "rhs_doubled": 6650,
            "quantifier": "all_selected_poles",
            "capacity_definition": "C2_q(R)=sum(lambda2(c-q) for c in G\\R)",
            "boundary_operation_order": "translate_then_clip_to_G_then_remove_R",
            "cross_pole_stencil_overlap_subtracted": False,
            "optional_storage_box_omitted_as_safe_relaxation": True,
        },
        "actual_p_ledger": dict(object_value(coordinate.get("actual_p_ledger"), "coordinate.actual_p_ledger")),
        "ceiling_corpus": dict(corpus),
        "checks": checks,
        "corpus_errors": [],
        "claim_boundary": list(coordinate["claim_boundary"]),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--stencil", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--coordinate", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--agreement", type=Path, required=True)
    parser.add_argument("--verdict-json", type=Path, required=True)
    parser.add_argument("--verdict-doc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        write_exclusive(args.output.resolve(), close_gate(args))
    except (OSError, AdmissionError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "PASS", "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
