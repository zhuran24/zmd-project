from __future__ import annotations

import argparse
import ast
from collections import Counter
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = PROJECT_ROOT / "docs" / "research" / "b1_r4_1188_22_pb_20260723"
R4_REVIEW_ROOT = PROJECT_ROOT / "docs" / "research" / "r4_response_review_20260723"
AUTHORITY_RUN = (
    PROJECT_ROOT / ".artifacts" / "track_b_r4_external_brain_handoff_20260722" / "run-20260722T084343Z-R4hP1A"
)
RESPONSE_RUN = (
    PROJECT_ROOT
    / ".artifacts"
    / "track_b_r4_external_brain_handoff_20260722"
    / "responses"
    / "run-20260723T023657Z-R4resp-357f260d"
)
A004_LEDGER = RESPONSE_RUN / "claims/a004/quantitative-claim-ledger.json"
A004_REPORTS = [
    RESPONSE_RUN / "recomputations/upper-counts-a004/report.json",
    RESPONSE_RUN / "recomputations/marked-geometry-a004/report.json",
    RESPONSE_RUN / "recomputations/w2d-audit-a004/report.json",
]
A004_VERDICT = RESPONSE_RUN / "adversarial/a004/verdict.json"
A004_ADMISSION = RESPONSE_RUN / "admission/a004/admission.json"
A003_ADMISSION = RESPONSE_RUN / "admission/a003/admission.json"
STRICT_ROOT = PROJECT_ROOT / "docs" / "research" / "cleanroom_rederivation_20260718" / "strict" / "external"
STRICT_PATHS = {
    "problem_instance": STRICT_ROOT / "problem_instance.json",
    "problem_instance_schema": STRICT_ROOT / "problem_instance.schema.json",
    "problem_md": STRICT_ROOT / "problem.md",
    "sha256s": STRICT_ROOT / "SHA256SUMS",
}
STRICT_IDENTITIES = {
    "problem_instance": (
        92_201,
        "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    ),
    "problem_instance_schema": (
        12_695,
        "5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23",
    ),
    "problem_md": (
        4_036,
        "c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f",
    ),
    "sha256s": (
        339,
        "8810d5d6a80d92438628b7694216d3b3c6c1be50543072ec9c3bcf510d9c4d70",
    ),
}
PROOF_LIMIT_BYTES = 5_000_000_000
MIN_FREE_BYTES = 10_737_418_240
EXPECTED_HEADER = "* #variable= 2084 #constraint= 2192 #equal= 1 intsize= 64"
EXPECTED_SEMANTICS = "b1_r4_1188_22_complete_oriented_lex_better_band_given_a004_admitted_lemmas_v1"
BUILD_AUTHORITY = (
    PROJECT_ROOT / ".artifacts" / "track_b_b1_r4_1188_22_pb_20260723" / "build-a001-20260723T091353Z-398f8725"
)
FORMAL_AUTHORITY = (
    PROJECT_ROOT / ".artifacts" / "track_b_b1_r4_1188_22_pb_20260723" / "formal-a001-20260723T091800Z-398f8725"
)
FORMAL_RESERVATION = (
    PROJECT_ROOT / ".artifacts" / "track_b_b1_r4_1188_22_pb_20260723" / "formal_attempt_a001.reservation.json"
)
AUTHORITY_RECEIPT_IDENTITY = {
    "path": (
        ".artifacts/track_b_b1_r4_1188_22_pb_20260723/formal-a001-20260723T091800Z-398f8725/authority_receipt.json"
    ),
    "size_bytes": 2_613,
    "sha256": "0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2",
}


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def encoder() -> ModuleType:
    return _load_module(
        "b1_r4_1188_22_pb_encoder_v1_test",
        RESEARCH_ROOT / "b1_r4_1188_22_pb_encoder_v1.py",
    )


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    return _load_module(
        "b1_r4_1188_22_pb_translation_v1_test",
        RESEARCH_ROOT / "verify_b1_r4_1188_22_pb_translation_v1.py",
    )


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load_module(
        "b1_r4_1188_22_pb_toolchain_v1_test",
        RESEARCH_ROOT / "run_b1_r4_1188_22_pb_toolchain_v1.py",
    )


@pytest.fixture(scope="module")
def admission_closer() -> ModuleType:
    return _load_module(
        "b1_r4_1188_22_a004_admission_replay_test",
        R4_REVIEW_ROOT / "close_r4_response_candidate_admission_v2.py",
    )


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _problem_payload() -> dict[str, Any]:
    return _json(STRICT_PATHS["problem_instance"])


def _paths(directory: Path) -> dict[str, Path]:
    return {
        "estimate": directory / "estimate.json",
        "opb": directory / "b1_r4_1188_22.opb",
        "meta": directory / "b1_r4_1188_22.meta.json",
        "var_map": directory / "b1_r4_1188_22.var_map.json",
        "gate": directory / "translation_gate.json",
    }


def _estimate_args(paths: dict[str, Path]) -> list[str]:
    return [
        "estimate",
        "--project-root",
        str(PROJECT_ROOT),
        "--output",
        str(paths["estimate"]),
        "--proof-limit-bytes",
        str(PROOF_LIMIT_BYTES),
    ]


def _encode_args(paths: dict[str, Path]) -> list[str]:
    return [
        "encode",
        "--project-root",
        str(PROJECT_ROOT),
        "--estimate",
        str(paths["estimate"]),
        "--opb-out",
        str(paths["opb"]),
        "--meta-out",
        str(paths["meta"]),
        "--var-map-out",
        str(paths["var_map"]),
    ]


def _gate_args(paths: dict[str, Path]) -> list[str]:
    return [
        "--project-root",
        str(PROJECT_ROOT),
        "--opb",
        str(paths["opb"]),
        "--meta",
        str(paths["meta"]),
        "--var-map",
        str(paths["var_map"]),
        "--estimate",
        str(paths["estimate"]),
        "--output",
        str(paths["gate"]),
    ]


def _generate(encoder: ModuleType, directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = _paths(directory)
    assert encoder.main(_estimate_args(paths)) == 0
    assert encoder.main(_encode_args(paths)) == 0
    return paths


@pytest.fixture(scope="module")
def complete_translation(
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Path]:
    paths = _generate(encoder, tmp_path_factory.mktemp("b1_r4_1188_22_pb"))
    assert gate.main(_gate_args(paths)) == 0
    return paths


def _replay_a004(admission_closer: ModuleType) -> dict[str, Any]:
    return admission_closer.replay_admission(
        AUTHORITY_RUN,
        RESPONSE_RUN,
        A004_LEDGER,
        A004_REPORTS,
        A004_VERDICT,
        A004_ADMISSION,
    )


def _reseal_opb_in_metadata(paths: dict[str, Path]) -> None:
    metadata = _json(paths["meta"])
    outputs = metadata["outputs"]
    assert isinstance(outputs, dict)
    opb = outputs["opb"]
    assert isinstance(opb, dict)
    opb["sha256"] = _sha256(paths["opb"])
    opb["size_bytes"] = paths["opb"].stat().st_size
    _write_json(paths["meta"], metadata)


def _reseal_var_map_in_metadata(paths: dict[str, Path]) -> None:
    metadata = _json(paths["meta"])
    outputs = metadata["outputs"]
    assert isinstance(outputs, dict)
    var_map = outputs["var_map"]
    assert isinstance(var_map, dict)
    var_map["sha256"] = _sha256(paths["var_map"])
    var_map["size_bytes"] = paths["var_map"].stat().st_size
    _write_json(paths["meta"], metadata)


def test_target_schemas_and_a004_complete_replay(
    encoder: ModuleType,
    gate: ModuleType,
    runner: ModuleType,
    admission_closer: ModuleType,
) -> None:
    assert encoder.MODEL_SCHEMA == "b1_r4_1188_22_pb_v1"
    assert encoder.METADATA_SCHEMA == "b1_r4_1188_22_pb_metadata_v1"
    assert encoder.VAR_MAP_SCHEMA == "b1_r4_1188_22_pb_var_map_v1"
    assert encoder.ESTIMATE_SCHEMA == "b1_r4_1188_22_pb_estimate_v1"
    assert encoder.SEMANTICS == EXPECTED_SEMANTICS
    assert gate.GATE_SCHEMA == "b1_r4_1188_22_pb_translation_gate_v1"
    assert gate.SEMANTICS == EXPECTED_SEMANTICS
    assert runner.MODEL_SCHEMA == encoder.MODEL_SCHEMA
    assert runner.METADATA_SCHEMA == encoder.METADATA_SCHEMA
    assert runner.VAR_MAP_SCHEMA == encoder.VAR_MAP_SCHEMA
    assert runner.ESTIMATE_SCHEMA == encoder.ESTIMATE_SCHEMA
    assert runner.GATE_SCHEMA == gate.GATE_SCHEMA
    assert runner.SEMANTICS == EXPECTED_SEMANTICS

    replay = _replay_a004(admission_closer)
    assert replay["admission_record"] == {
        "path": str(A004_ADMISSION.resolve()),
        "sha256": "2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff",
        "size_bytes": 10_273,
    }
    admission = replay["admission"]
    assert admission["status"] == "PARTIAL"
    assert admission["current_project_ledger"] == {
        "L": "absent",
        "U": [1190, 34],
    }
    assert admission["upper_bound_changed"] is False
    assert admission["candidates"]["upper_bound_1188_22"] == {
        "b1_followup_input_admitted": True,
        "proposed_upper_ledger": [1188, 22],
        "research_followup_admitted": True,
        "verdict": "PASS",
    }
    assert len(replay["verdict_replay"]["claims"]) == 17
    assert [item["status"] for item in replay["verdict_replay"]["reports"]] == ["PASS_EXACT_MATCH"] * 3
    assert replay["verdict_replay"]["verdict"]["status"] == "COMPLETE"
    for key in (
        "encoder_execution_authorized",
        "formal_run_authorized",
        "solver_run_authorized",
        "search_run_authorized",
        "assembly_run_authorized",
        "router_run_authorized",
        "track_w_execution_authorized",
    ):
        assert admission[key] is False


def test_a004_replay_rejects_a003_and_byte_or_field_tamper(
    admission_closer: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with pytest.raises(admission_closer.AdmissionError):
        admission_closer.replay_admission(
            AUTHORITY_RUN,
            RESPONSE_RUN,
            A004_LEDGER,
            A004_REPORTS,
            A004_VERDICT,
            A003_ADMISSION,
        )

    verdict_replay = admission_closer._replay_verdict(
        AUTHORITY_RUN,
        RESPONSE_RUN,
        A004_LEDGER,
        A004_REPORTS,
        A004_VERDICT,
    )
    monkeypatch.setattr(
        admission_closer,
        "_replay_verdict",
        lambda *_args, **_kwargs: verdict_replay,
    )

    tampered = _json(A004_ADMISSION)
    tampered["candidates"]["upper_bound_1188_22"]["proposed_upper_ledger"] = [
        1188,
        21,
    ]
    field_path = tmp_path / "field-tamper.json"
    _write_json(field_path, tampered)
    monkeypatch.setattr(
        admission_closer,
        "_artifact_file",
        lambda *_args, **_kwargs: field_path,
    )
    with pytest.raises(admission_closer.AdmissionError, match="canonical semantics"):
        admission_closer.replay_admission(
            AUTHORITY_RUN,
            RESPONSE_RUN,
            A004_LEDGER,
            A004_REPORTS,
            A004_VERDICT,
            field_path,
        )

    byte_path = tmp_path / "byte-tamper.json"
    byte_path.write_bytes(A004_ADMISSION.read_bytes() + b" ")
    monkeypatch.setattr(
        admission_closer,
        "_artifact_file",
        lambda *_args, **_kwargs: byte_path,
    )
    with pytest.raises(admission_closer.AdmissionError, match="canonical serialization"):
        admission_closer.replay_admission(
            AUTHORITY_RUN,
            RESPONSE_RUN,
            A004_LEDGER,
            A004_REPORTS,
            A004_VERDICT,
            byte_path,
        )


def test_strict_four_and_strict_parser_mutation_canaries(gate: ModuleType) -> None:
    for name, path in STRICT_PATHS.items():
        size, digest = STRICT_IDENTITIES[name]
        assert path.stat().st_size == size
        assert _sha256(path) == digest

    with pytest.raises(gate.GateError, match="duplicate"):
        gate._strict_json(b'{"x":1,"x":2}', "duplicate")
    with pytest.raises(gate.GateError, match="non-finite"):
        gate._strict_json(b'{"x":NaN}', "nonfinite")
    with pytest.raises(gate.GateError, match="floating"):
        gate._strict_json(b'{"x":1.5}', "float")

    inputs = {name: path.read_bytes() for name, path in STRICT_PATHS.items() if name != "sha256s"}
    assert gate._verify_sha256_manifest(
        STRICT_PATHS["sha256s"].read_bytes(),
        inputs,
    )
    mutated_manifest = (
        STRICT_PATHS["sha256s"]
        .read_bytes()
        .replace(
            b"e08a163336edf73e",
            b"0000000000000000",
            1,
        )
    )
    assert not gate._verify_sha256_manifest(mutated_manifest, inputs)
    with pytest.raises(gate.GateError, match="duplicate"):
        gate._verify_sha256_manifest(
            STRICT_PATHS["sha256s"].read_bytes() + STRICT_PATHS["sha256s"].read_bytes().splitlines(keepends=True)[0],
            inputs,
        )


def test_independent_math_complete_band_and_survivors(
    encoder: ModuleType,
    gate: ModuleType,
) -> None:
    payload = _problem_payload()
    model = encoder.derive_model(payload)
    gate_expected = gate._build_expected(gate._derive(payload))
    facts = model.derived_facts

    assert model.counts == {
        "oriented_dimensions": 2084,
        "selector_variables": 2084,
        "variables": 2084,
        "equality_constraints": 1,
        "arithmetic_implication_constraints": 2084,
        "full_span_forbid_constraints": 107,
        "constraints": 2192,
        "arithmetic_survivors": 2,
        "final_survivors": 0,
        "positive_arithmetic_coefficients": 2,
        "negative_arithmetic_coefficients": 2082,
        "zero_arithmetic_coefficients": 0,
    }
    assert facts["strict_sentinels"]["required_instances"] == 266
    assert facts["strict_sentinels"]["manufacturing_instances"] == 219
    assert facts["strict_sentinels"]["required_body_area"] == 3544
    assert facts["strict_sentinels"]["powered_manufacturing_area"] == 3325
    assert facts["strict_sentinels"]["total_active_terminals"] == 628
    assert facts["ordinary_membrane"]["class_table"] == [
        {"side_span": 3, "active_side_cap": 1, "multiplicity": 155},
        {"side_span": 3, "active_side_cap": 2, "multiplicity": 12},
        {"side_span": 3, "active_side_cap": 3, "multiplicity": 11},
        {"side_span": 5, "active_side_cap": 1, "multiplicity": 32},
        {"side_span": 5, "active_side_cap": 2, "multiplicity": 17},
        {"side_span": 6, "active_side_cap": 3, "multiplicity": 32},
        {"side_span": 6, "active_side_cap": 4, "multiplicity": 3},
        {"side_span": 6, "active_side_cap": 5, "multiplicity": 3},
    ]
    assert facts["marked_terminals"]["class_table"] == [
        {"side_span": 3, "marks": 0, "multiplicity": 253},
        {"side_span": 3, "marks": 1, "multiplicity": 57},
        {"side_span": 5, "marks": 0, "multiplicity": 98},
        {"side_span": 6, "marks": 0, "multiplicity": 38},
        {"side_span": 6, "marks": 1, "multiplicity": 32},
        {"side_span": 6, "marks": 2, "multiplicity": 3},
        {"side_span": 6, "marks": 3, "multiplicity": 3},
        {"side_span": 9, "marks": 3, "multiplicity": 2},
    ]
    assert facts["marked_terminals"]["manufacturing_marks"] == 58
    assert facts["marked_terminals"]["raw_noncorner_marks"] == 52
    assert facts["marked_terminals"]["total_marks"] == 110
    assert facts["access_cell_enumeration"] == {
        "port_occurrences": 178,
        "enumeration": {
            "3": {
                "combinations_checked": 352440,
                "nonoverlap_combinations": 30080,
                "maximum_noncorner_marks": 1,
            },
            "4": {
                "combinations_checked": 3920400,
                "nonoverlap_combinations": 8192,
                "maximum_noncorner_marks": 0,
            },
        },
        "inequality": "t(z)+m(z)<=4",
    }
    assert facts["marked_membrane"]["interval_checks"] == 381680
    assert facts["marked_membrane"]["endpoint_pair_checks"] == 81900
    assert facts["marked_membrane"]["directed_side_count"] == 4
    assert facts["marked_membrane"]["endpoints_per_directed_side"] == 2
    assert facts["marked_membrane"]["directed_endpoint_count"] == 8
    assert facts["marked_membrane"]["maximum_body_disjoint_crossers_per_endpoint"] == 1
    assert facts["marked_membrane"]["maximum_marks_per_partial_contact"] == 3
    assert facts["marked_membrane"]["maximum_partial_contacts"] == 8
    assert facts["power_halo"]["total_weight"] == 396
    assert facts["power_halo"]["placement_count"] == 840
    assert facts["power_halo"]["minimum_poles"] == 9
    assert facts["free_cell_cap"]["value"] == 1320
    assert facts["boundary_packing"]["anchors_per_supported_boundary"] == 68
    assert facts["boundary_packing"]["maximum_per_supported_boundary"] == 23
    assert facts["boundary_packing"]["forced_distribution"] == [23, 23]
    assert facts["boundary_packing"]["occupied_cells_per_supported_boundary"] == 69

    dimensions = [(item["width"], item["height"]) for item in model.variables]
    assert len(dimensions) == 2084
    assert sum(width * height > 1188 for width, height in dimensions) == 2080
    assert [pair for pair in dimensions if pair[0] * pair[1] == 1188] == [
        (27, 44),
        (33, 36),
        (36, 33),
        (44, 27),
    ]
    assert sum(70 in pair for pair in dimensions) == 107
    band = facts["lex_better_band"]
    assert band["arithmetic_survivors"] == [[17, 70], [70, 17]]
    assert band["final_survivors"] == []
    assert band["minimum_non_full_total"] == 1322
    assert band["minimum_non_full_dimensions"] == [[27, 44], [44, 27]]
    assert dimensions == [(item["width"], item["height"]) for item in gate_expected["variables"]]


def test_encoder_gate_and_opb_exact_closure(
    gate: ModuleType,
    complete_translation: dict[str, Path],
) -> None:
    paths = complete_translation
    estimate = _json(paths["estimate"])
    metadata = _json(paths["meta"])
    variable_map = _json(paths["var_map"])
    report = _json(paths["gate"])

    assert paths["opb"].read_text(encoding="ascii").splitlines()[0] == EXPECTED_HEADER
    assert estimate["projected_outputs"] == {"opb_bytes": paths["opb"].stat().st_size}
    assert estimate["proof_size_planning"]["bound_bytes"] == max(
        512 * 1024**2,
        1024 * paths["opb"].stat().st_size,
    )
    assert estimate["proof_size_planning"]["decision"] == "GO"
    assert metadata["counts"]["variables"] == 2084
    assert metadata["counts"]["constraints"] == 2192
    assert variable_map["variable_count"] == 2084
    assert len(variable_map["variables"]) == 2084
    assert report["status"] == "PASS"
    assert set(report["checks"]) == gate.REQUIRED_CHECKS
    assert all(value is True for value in report["checks"].values())
    assert report["corpus_count"] == 2084
    assert report["arithmetic_survivors"] == [[17, 70], [70, 17]]
    assert report["full_span_rejections_of_arithmetic_survivors"] == [
        [17, 70],
        [70, 17],
    ]
    assert report["corpus_errors"] == []
    assert report["minimum_non_full_span_lhs"] == 1322
    assert report["minimum_non_full_span_lhs_dimensions"] == [
        [27, 44],
        [44, 27],
    ]
    assert report["constraint_diff"] == {
        "missing_examples": [],
        "missing_total": 0,
        "unexpected_examples": [],
        "unexpected_total": 0,
    }
    assert all(item["pass"] is True for item in report["semantic_canaries"].values())
    assert metadata["proof_status"] == "translation_only_no_unsat_or_proof_claim"
    assert report["proof_status"] == "translation_gate_only_no_unsat_or_proof_claim"
    assert report["model_schema_version"] == "b1_r4_1188_22_pb_v1"
    assert report["metadata_schema_version"] == "b1_r4_1188_22_pb_metadata_v1"
    assert report["variable_map_schema_version"] == "b1_r4_1188_22_pb_var_map_v1"
    assert report["strict_inputs"] == metadata["inputs"]
    assert report["translation_inputs"]["opb"] == metadata["outputs"]["opb"]
    assert report["encoder_git_snapshot"] == metadata["git_snapshot"]
    assert metadata["claim_scope"]["given_geometric_lemmas"]["inside_opb"] is False
    assert metadata["claim_scope"]["arithmetic_band"]["inside_opb"] is True


def test_gate_has_no_forbidden_math_imports() -> None:
    source = (RESEARCH_ROOT / "verify_b1_r4_1188_22_pb_translation_v1.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = (
        "b1_r4_1188_22_pb_encoder",
        "r3_upper_bound_pb_encoder",
        "verify_r3_upper_bound_pb_translation",
        "verify_r3_certificates",
        "independent_r4_upper_counts",
        "independent_r4_marked_geometry",
        "independent_r4_w2d_audit",
        "build_r4_claim_ledger",
        "build_r4_adversarial_verdict",
        "run_r4_local_recomputation",
    )
    assert not any(any(fragment in name for fragment in forbidden) for name in imports)


def test_band_ceil_halo_and_mutation_canaries(gate: ModuleType) -> None:
    band = gate._band_for_bounds(6, 70)
    assert len(band) == 2084
    assert len(gate._band_for_bounds(6, 69)) != 2084
    assert min(min(pair) for pair in band) == 17
    assert gate._ceil_div(1, 4) == 1
    assert gate._ceil_div(-1, 4) == 0
    assert gate._ceil_div(-5, 4) == -1
    factor_pairs = [(width, height) for width in range(6, 71) for height in range(6, 71) if width * height == 1188]
    assert factor_pairs == [
        (18, 66),
        (22, 54),
        (27, 44),
        (33, 36),
        (36, 33),
        (44, 27),
        (54, 22),
        (66, 18),
    ]
    assert [pair for pair in factor_pairs if pair in band] == [
        (27, 44),
        (33, 36),
        (36, 33),
        (44, 27),
    ]

    mutated_weights = dict(gate.HALO_DOUBLED_WEIGHTS)
    mutated_weights[(3, 3)] -= 1
    mutated_halo = gate._derive_halo(
        coverage=(-5, 6, -5, 6),
        body_dimensions=[(3, 3), (4, 6), (5, 5), (6, 4)],
        powered_area=3325,
        pole_body_dimensions=(2, 2),
        weights=mutated_weights,
    )
    assert mutated_halo["total_weight2"] != 792
    assert mutated_halo["violations"]
    assert mutated_halo["minimum_slack2"] < 0

    boundary = copy.deepcopy(_problem_payload())
    boundary["facility_templates"]["boundary_storage_port"]["placement_rule"] = "free"
    with pytest.raises(gate.GateError, match="boundary"):
        gate._derive(boundary)
    raw_slots = copy.deepcopy(_problem_payload())
    raw_slots["generic_requirements"]["raw_outputs"]["source_ore"] += 1
    with pytest.raises(gate.GateError, match="raw|slot|sentinel"):
        gate._derive(raw_slots)


@pytest.mark.parametrize(
    "mutation",
    [
        "arithmetic",
        "full_span",
        "exactly_one",
        "header",
        "zero_term",
        "duplicate_cancel",
    ],
)
def test_gate_rejects_resealed_opb_mutations(
    mutation: str,
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path: Path,
) -> None:
    paths = _generate(encoder, tmp_path / mutation)
    lines = paths["opb"].read_text(encoding="ascii").splitlines()
    variable_map = _json(paths["var_map"])
    variables = variable_map["variables"]
    assert isinstance(variables, list)

    if mutation == "header":
        lines[0] = lines[0].replace("#constraint= 2192", "#constraint= 2191")
    elif mutation in {"zero_term", "duplicate_cancel"}:
        index = next(i for i, line in enumerate(lines) if line.rstrip().endswith("= 1 ;"))
        suffix = "+0 x1" if mutation == "zero_term" else "+1 x1 -1 x1"
        lines[index] = lines[index].replace(" = 1 ;", f" {suffix} = 1 ;")
    elif mutation == "exactly_one":
        index = next(i for i, line in enumerate(lines) if line.rstrip().endswith("= 1 ;"))
        lines[index] = lines[index].replace("= 1 ;", "= 2 ;")
    elif mutation == "full_span":
        survivor = next(item for item in variables if item["width"] == 17 and item["height"] == 70)
        variable_id = survivor["id"]
        index = next(i for i, line in enumerate(lines) if line.strip() == f"-1 x{variable_id} >= 0 ;")
        lines[index] = f"-2 x{variable_id} >= 0 ;"
    else:
        index = next(i for i, line in enumerate(lines) if line.startswith("-") and " >= 0 ;" in line)
        coefficient, remainder = lines[index].split(" ", 1)
        lines[index] = f"{int(coefficient) - 1:+d} {remainder}"

    paths["opb"].write_text("\n".join(lines) + "\n", encoding="ascii")
    _reseal_opb_in_metadata(paths)
    assert gate.main(_gate_args(paths)) == 1
    report = _json(paths["gate"])
    assert report["status"] == "FAIL"
    assert report["checks"]["translation_inputs_closed_and_hashed"] is True
    if mutation == "header":
        assert report["checks"]["opb_header_exact"] is False
    else:
        assert report["checks"]["constraint_multiset_exact"] is False
    if mutation in {"zero_term", "duplicate_cancel"}:
        assert report["opb_parse_errors"]


@pytest.mark.parametrize(
    ("field_path", "replacement"),
    [
        (("counts", "equality_constraints"), True),
        (
            (
                "upstream_authority",
                "replay_summary",
                "false_fields",
                "formal_run_authorized",
            ),
            0,
        ),
        (
            (
                "claim_scope",
                "given_geometric_lemmas",
                "inside_opb",
            ),
            0,
        ),
    ],
)
def test_gate_rejects_json_bool_integer_type_confusion(
    field_path: tuple[str, ...],
    replacement: object,
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path: Path,
) -> None:
    paths = _generate(encoder, tmp_path / "-".join(field_path))
    metadata = _json(paths["meta"])
    cursor: dict[str, Any] = metadata
    for key in field_path[:-1]:
        value = cursor[key]
        assert isinstance(value, dict)
        cursor = value
    cursor[field_path[-1]] = replacement
    _write_json(paths["meta"], metadata)
    assert gate.main(_gate_args(paths)) == 1
    report = _json(paths["gate"])
    assert report["status"] == "FAIL"
    assert report["checks"]["metadata_reconstruction_match"] is False


def test_gate_rejects_variable_map_orientation_or_bool_id(
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path: Path,
) -> None:
    paths = _generate(encoder, tmp_path / "var-map")
    variable_map = _json(paths["var_map"])
    variables = variable_map["variables"]
    assert isinstance(variables, list)
    assert isinstance(variables[0], dict)
    variables[0]["id"] = True
    second = variables[1]
    assert isinstance(second, dict)
    second["width"], second["height"] = second["height"], second["width"]
    _write_json(paths["var_map"], variable_map)
    _reseal_var_map_in_metadata(paths)
    assert gate.main(_gate_args(paths)) == 1
    report = _json(paths["gate"])
    assert report["checks"]["translation_inputs_closed_and_hashed"] is True
    assert report["checks"]["variable_map_dense"] is False
    assert report["checks"]["variable_map_exact"] is False


def test_translation_outputs_refuse_overwrite_and_symlink(
    encoder: ModuleType,
    gate: ModuleType,
    complete_translation: dict[str, Path],
    tmp_path: Path,
) -> None:
    paths = complete_translation
    before = {name: _sha256(path) for name, path in paths.items()}
    with pytest.raises(FileExistsError, match="exist|overwrite"):
        encoder.main(_estimate_args(paths))
    with pytest.raises(FileExistsError, match="exist|overwrite"):
        encoder.main(_encode_args(paths))
    with pytest.raises(FileExistsError, match="exist|overwrite"):
        gate.main(_gate_args(paths))
    assert {name: _sha256(path) for name, path in paths.items()} == before

    symlink_paths = _paths(tmp_path / "symlink")
    symlink_paths["estimate"].parent.mkdir()
    target = tmp_path / "outside-estimate.json"
    target.write_text("sentinel\n", encoding="ascii")
    symlink_paths["estimate"].symlink_to(target)
    with pytest.raises((FileExistsError, ValueError), match="exist|overwrite|symlink"):
        encoder.main(_estimate_args(symlink_paths))
    assert target.read_text(encoding="ascii") == "sentinel\n"


def test_build_attempt_is_lowest_fresh_direct_child_and_sealed(
    encoder: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    monkeypatch.setattr(encoder, "ARTIFACT_ROOT", artifact_root)

    attempt = encoder._prepare_build_attempt(artifact_root / "build-a001-20260723T170000Z-398f8725")
    payload = attempt / "formula.opb"
    payload.write_text("* formula\n", encoding="ascii")
    manifest = encoder._write_build_manifest(
        attempt,
        expected_names=frozenset({"formula.opb"}),
    )
    assert manifest["covered_files"] == ["formula.opb"]
    assert manifest["excluded_to_avoid_hash_cycle"] == [
        "SHA256SUMS",
        "build_record.json",
    ]
    assert (attempt / "SHA256SUMS").read_text(encoding="ascii") == (f"{_sha256(payload)}  formula.opb\n")
    with pytest.raises(FileExistsError):
        encoder._write_build_manifest(
            attempt,
            expected_names=frozenset({"formula.opb"}),
        )

    invocation, resolved = encoder._fixed_python()
    assert invocation == Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13")
    assert invocation.is_symlink()
    assert resolved.is_file()

    with pytest.raises(encoder.EncoderError, match="lowest unused"):
        encoder._prepare_build_attempt(artifact_root / "build-a003-20260723T170001Z-398f8725")
    with pytest.raises(encoder.EncoderError, match="direct child"):
        encoder._prepare_build_attempt(tmp_path / "build-a002-20260723T170001Z-398f8725")


def test_build_authority_is_required_and_semantically_replayed(
    encoder: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    monkeypatch.setattr(encoder, "ARTIFACT_ROOT", artifact_root)
    monkeypatch.setattr(runner, "ARTIFACT_ROOT", artifact_root)
    attempt = artifact_root / "build-a001-20260723T171500Z-398f8725"
    gate_source = RESEARCH_ROOT / "verify_b1_r4_1188_22_pb_translation_v1.py"
    build_argv = [
        "build",
        "--project-root",
        str(PROJECT_ROOT),
        "--gate-script",
        str(gate_source),
        "--output-dir",
        str(attempt),
        "--proof-limit-bytes",
        str(PROOF_LIMIT_BYTES),
    ]
    assert encoder.main(build_argv) == 0
    paths = {
        "estimate": attempt / "estimate.json",
        "opb": attempt / "formula.opb",
        "meta": attempt / "encoder.meta.json",
        "var_map": attempt / "variable_map.json",
        "translation_gate": attempt / "translation_gate.json",
        "build_record": attempt / "build_record.json",
        "build_manifest": attempt / "SHA256SUMS",
    }
    authority = runner._validate_build_authority(paths, PROJECT_ROOT)
    assert authority["status"] == "PASS"
    assert set(authority["payload"]) == encoder.BUILD_PAYLOAD_NAMES

    raw_record = paths["build_record"].read_bytes()
    tampered_record = _json(paths["build_record"])
    tampered_record["formal_run_authorized"] = 0
    _write_json(paths["build_record"], tampered_record)
    with pytest.raises(runner.ToolchainError) as caught:
        runner._validate_build_authority(paths, PROJECT_ROOT)
    assert caught.value.code == "build_authority_failure"
    paths["build_record"].write_bytes(raw_record)

    raw_manifest = paths["build_manifest"].read_bytes()
    paths["build_manifest"].write_bytes(b"".join(raw_manifest.splitlines(keepends=True)[1:]))
    with pytest.raises(runner.ToolchainError) as caught:
        runner._validate_build_authority(paths, PROJECT_ROOT)
    assert caught.value.code == "build_authority_failure"

    parser = runner._parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--project-root",
                str(PROJECT_ROOT),
                "--opb",
                str(paths["opb"]),
                "--meta",
                str(paths["meta"]),
                "--var-map",
                str(paths["var_map"]),
                "--estimate",
                str(paths["estimate"]),
                "--translation-gate",
                str(paths["translation_gate"]),
            ]
        )


def test_runner_pins_tools_python_and_resource_contract(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    assert runner.SCHEMA_VERSION == "b1_r4_1188_22_pb_toolchain_run_v1"
    assert runner.EXPECTED_MEMORY_HIGH == 35 * 1024**3
    assert runner.EXPECTED_MEMORY_MAX == 39 * 1024**3
    assert runner.EXPECTED_SWAP_MAX == 16 * 1024**3
    assert runner.EXPECTED_OOM_POLICY == "continue"
    assert runner.EXPECTED_KILL_MODE == "control-group"
    assert runner.EXPECTED_SEND_SIGKILL == "yes"
    assert runner.FORMAL_PROOF_LIMIT_BYTES == PROOF_LIMIT_BYTES
    assert runner.FORMAL_MIN_FREE_BYTES == MIN_FREE_BYTES
    assert runner.FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES == MIN_FREE_BYTES + PROOF_LIMIT_BYTES
    assert runner.SINGLETON_LOCK_NAME == "zmd_pj_prod_scale_solver.lock"
    assert runner.BUILD_OUTPUT_RE.fullmatch("build-a001-20260723T171500Z-398f8725")
    assert not runner.BUILD_OUTPUT_RE.fullmatch("build-a000-20260723T171500Z-398f8725")
    assert not runner.BUILD_OUTPUT_RE.fullmatch("build-a002-20260723T171500Z-398f8725")
    assert runner.EXPECTED_PYTHON_PATH == Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13")
    assert runner.EXPECTED_PYTHON_SHA256 == "74fceb0fdd29c31cf066ac8d92465975ea4ac8592308d7c888e26a70092d8eeb"
    assert runner.EXPECTED_ROUNDINGSAT_SHA256 == "08bb2542bcf09d99366f35e6fcfc7c79e002eca360ab9da027944c719fa3f8bf"
    assert runner.EXPECTED_VERIPB_SHA256 == "a0c72df075b924af3b698ae808f86d3b55067168534397a0cc3d49594777b971"

    permissive = {
        "memory_high": "max",
        "memory_max": str(40 * 1024**3),
        "memory_swap_max": str(16 * 1024**3),
    }
    restrictive = {**permissive, "memory_high": str(34 * 1024**3)}
    assert runner._ancestor_limits_allow_contract([permissive])
    assert not runner._ancestor_limits_allow_contract([restrictive])

    fake_solver = tmp_path / "roundingsat"
    fake_verifier = tmp_path / "veripb"
    fake_repo = tmp_path / "repo"
    fake_solver.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_verifier.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_solver.chmod(0o755)
    fake_verifier.chmod(0o755)
    fake_repo.mkdir()
    with pytest.raises(runner.ToolchainError) as caught:
        runner._validate_tool_paths(
            {
                "roundingsat": fake_solver,
                "roundingsat_repo": fake_repo,
                "veripb": fake_verifier,
            },
            PROJECT_ROOT,
        )
    assert caught.value.code == "tool_identity_drift"


def test_runner_status_tail_cap_and_failure_classification(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    proof = tmp_path / "proof.pbp"
    proof.write_text("pseudo-Boolean proof version 2.0\n", encoding="utf-8")
    assert runner._proof_tail(proof)["complete"] is False
    proof.write_text(
        "pseudo-Boolean proof version 2.0\nconclusion UNSAT : 1\nend pseudo-Boolean proof\n",
        encoding="utf-8",
    )
    assert runner._proof_tail(proof)["complete"] is True

    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stderr.write_text("", encoding="ascii")
    for status in ("s SATISFIABLE", "s UNKNOWN"):
        stdout.write_text(status + "\n", encoding="ascii")
        assert not runner._stdout_status_exact(
            stdout,
            stderr,
            "s UNSATISFIABLE",
        )
    stdout.write_text("s VERIFIED\n", encoding="ascii")
    assert not runner._stdout_status_exact(
        stdout,
        stderr,
        "s VERIFIED UNSATISFIABLE",
    )
    stdout.write_text("s UNSATISFIABLE\ns SATISFIABLE\n", encoding="ascii")
    assert runner._status_lines(stdout, stderr) == [
        "s UNSATISFIABLE",
        "s SATISFIABLE",
    ]

    output_dir = tmp_path / "proof-cap"
    output_dir.mkdir()
    capped_proof = output_dir / "proof.pbp"
    result = runner._run_child(
        [
            sys.executable,
            "-c",
            (f"from pathlib import Path;Path({str(capped_proof)!r}).write_bytes(b'x'*9)"),
        ],
        stdout_path=output_dir / "stdout.txt",
        stderr_path=output_dir / "stderr.txt",
        wall_timeout=10.0,
        monitor_interval=0.01,
        output_dir=output_dir,
        resources=[],
        phase="proof_cap_test",
        min_free_bytes=1,
        proof_path=capped_proof,
        proof_limit_bytes=8,
    )
    assert result["termination_reason"] in {
        "proof_size_limit_exceeded",
        "proof_size_limit_exceeded_at_completion",
    }
    assert result["process_group_clean"] is True
    assert "elapsed_nanoseconds" in result
    assert type(result["elapsed_nanoseconds"]) is int
    assert "elapsed_seconds" not in result
    assert isinstance(
        runner._strict_json_loads(
            json.dumps(result, sort_keys=True),
            "child result",
        ),
        dict,
    )
    runner._closed_child_run(
        result,
        field="test.child",
        stdout_path=output_dir / "stdout.txt",
        stderr_path=output_dir / "stderr.txt",
        root=PROJECT_ROOT,
    )
    for mutation in ("delete_elapsed", "boolean_to_integer"):
        altered = copy.deepcopy(result)
        if mutation == "delete_elapsed":
            del altered["elapsed_nanoseconds"]
        else:
            altered["process_group_clean"] = 1
        with pytest.raises(runner.ToolchainError, match="child|closed expected"):
            runner._closed_child_run(
                altered,
                field="test.child",
                stdout_path=output_dir / "stdout.txt",
                stderr_path=output_dir / "stderr.txt",
                root=PROJECT_ROOT,
            )

    failures: list[str] = []
    runner._add_child_failures(
        failures,
        {
            "spawn_error": None,
            "termination_reason": "disk_free_below_minimum",
            "exit_code": -15,
            "process_group_clean": True,
        },
        "solver",
    )
    assert "solver_disk_free_below_minimum" in failures
    assert runner._event_deltas(
        {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
        {"oom": 1, "oom_kill": 0, "oom_group_kill": 0},
    ) == {"oom": 1, "oom_group_kill": 0, "oom_kill": 0}

    execute_source = (RESEARCH_ROOT / "run_b1_r4_1188_22_pb_toolchain_v1.py").read_text(encoding="utf-8")
    for code in (
        "solver_non_unsat_status",
        "verifier_non_verified_status",
        "oom_cgroup_event",
        "disk_low_water",
        "formula_or_proof_hash_drift",
        "artifact_manifest_critical_hash_mismatch",
    ):
        assert code in execute_source


def test_runner_nested_cgroup_telemetry_and_started_records_fail_closed(
    runner: ModuleType,
) -> None:
    unit = "b1-r4-1188-22-formal-a001-20260723T180000Z.service"
    relative = f"/user.slice/{unit}"
    expected_properties = {
        "MemoryHigh": str(runner.EXPECTED_MEMORY_HIGH),
        "MemoryMax": str(runner.EXPECTED_MEMORY_MAX),
        "MemorySwapMax": str(runner.EXPECTED_SWAP_MAX),
        "OOMPolicy": runner.EXPECTED_OOM_POLICY,
        "KillMode": runner.EXPECTED_KILL_MODE,
        "SendSIGKILL": runner.EXPECTED_SEND_SIGKILL,
    }
    checks = {
        "unified_cgroup_found": True,
        "expected_unit_is_cgroup_leaf": True,
        "memory_high_exact": True,
        "memory_max_exact": True,
        "memory_swap_max_exact": True,
        "memory_events_readable": True,
        "systemd_memory_high_exact": True,
        "systemd_memory_max_exact": True,
        "systemd_memory_swap_max_exact": True,
        "oom_policy_exact": True,
        "kill_mode_exact": True,
        "send_sigkill_exact": True,
        "ancestor_limits_allow_contract": True,
    }
    cgroup = {
        "required": True,
        "expected_systemd_unit": unit,
        "self": {
            "pid": 123,
            "raw": [f"0::{relative}"],
            "unified_path": relative,
        },
        "cgroup_path": relative,
        "cgroup_directory": f"/sys/fs/cgroup/{relative.lstrip('/')}",
        "leaf_values": {
            "memory.high": str(runner.EXPECTED_MEMORY_HIGH),
            "memory.max": str(runner.EXPECTED_MEMORY_MAX),
            "memory.swap.max": str(runner.EXPECTED_SWAP_MAX),
            "memory.current": "1",
            "memory.peak": "2",
        },
        "memory_events": {
            "low": 0,
            "high": 0,
            "max": 0,
            "oom": 0,
            "oom_kill": 0,
            "oom_group_kill": 0,
        },
        "cgroup_procs": ["123"],
        "ancestor_limits": [
            {
                "path": "/sys/fs/cgroup",
                "memory_high": None,
                "memory_max": None,
                "memory_swap_max": None,
            }
        ],
        "systemd_properties": {
            name: {
                "argv": [
                    "systemctl",
                    "--user",
                    "show",
                    unit,
                    f"--property={name}",
                    "--value",
                ],
                "exit_code": 0,
                "stdout": f"{value}\n",
                "stderr": "",
                "value": value,
            }
            for name, value in expected_properties.items()
        },
        "checks": checks,
        "contract_pass": True,
    }
    runner._closed_cgroup_state(
        cgroup,
        field="test.cgroup",
        expected_unit=unit,
        required=True,
    )
    reduced_checks = copy.deepcopy(cgroup)
    del reduced_checks["checks"]["oom_policy_exact"]
    with pytest.raises(runner.ToolchainError, match="closed expected"):
        runner._closed_cgroup_state(
            reduced_checks,
            field="test.cgroup",
            expected_unit=unit,
            required=True,
        )
    type_confused = copy.deepcopy(cgroup)
    type_confused["required"] = 1
    with pytest.raises(runner.ToolchainError, match="cgroup contract"):
        runner._closed_cgroup_state(
            type_confused,
            field="test.cgroup",
            expected_unit=unit,
            required=True,
        )

    telemetry = {
        "timestamp_utc": "2026-07-23T18:00:00+00:00",
        "monotonic_nanoseconds": 1,
        "phase": "pre_children",
        "free_bytes": runner.FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES,
        "proof_size_bytes": None,
        "active_child": None,
        "cgroup": {
            "memory_current": "1",
            "memory_peak": "2",
            "memory_swap_current": "0",
            "memory_swap_peak": "0",
            "memory_events": cgroup["memory_events"],
            "cgroup_procs": ["123"],
        },
    }
    runner._closed_telemetry_sample(
        telemetry,
        field="test.telemetry",
        expected_cgroup_path=relative,
    )
    float_telemetry = copy.deepcopy(telemetry)
    float_telemetry["monotonic_nanoseconds"] = 1.0
    with pytest.raises(runner.ToolchainError, match="telemetry"):
        runner._closed_telemetry_sample(
            float_telemetry,
            field="test.telemetry",
            expected_cgroup_path=relative,
        )

    record = {
        "started_at_utc": "2026-07-23T18:00:00+00:00",
        "argv": ["runner", "--fixed"],
    }
    started = {
        "schema_version": runner.SCHEMA_VERSION,
        "semantics": runner.SEMANTICS,
        "formal_attempt": "a001",
        "started_at_utc": record["started_at_utc"],
        "argv": record["argv"],
        "inputs": {"input": 1},
        "input_copies": {"copy": 2},
        "strict_inputs": {"strict": 3},
        "a004_authority": {"a004": 4},
        "build_authority": {"build": 5},
        "reservation": {"source": {"s": 6}, "copy": {"c": 7}},
        "sources": {"source": 8},
        "git_snapshots": {"git": 9},
        "tools_before_execution": {"tool": 10},
        "limits": {"limit": 11},
        "cgroup": cgroup,
        "claim_at_start": "none",
    }
    started_kwargs = {
        "record": record,
        "inputs": started["inputs"],
        "input_copies": started["input_copies"],
        "strict_inputs": started["strict_inputs"],
        "a004_authority": started["a004_authority"],
        "build_authority": started["build_authority"],
        "reservation_source": started["reservation"]["source"],
        "reservation_copy": started["reservation"]["copy"],
        "sources": started["sources"],
        "git_snapshots": started["git_snapshots"],
        "tools": started["tools_before_execution"],
        "execution": started["limits"],
        "cgroup": cgroup,
    }
    runner._replay_started_record(started, **started_kwargs)
    missing_started_field = copy.deepcopy(started)
    del missing_started_field["strict_inputs"]
    with pytest.raises(runner.ToolchainError, match="closed expected"):
        runner._replay_started_record(
            missing_started_field,
            **started_kwargs,
        )
    changed_started_semantics = copy.deepcopy(started)
    changed_started_semantics["claim_at_start"] = "publish"
    with pytest.raises(runner.ToolchainError, match="toolchain_started semantics"):
        runner._replay_started_record(
            changed_started_semantics,
            **started_kwargs,
        )


def test_runner_timeout_reaches_descendant_process_group(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "descendant-timeout"
    output_dir.mkdir()
    grandchild_pid_path = output_dir / "grandchild.pid"
    grandchild_ready_path = output_dir / "grandchild.ready"
    grandchild_sigterm_path = output_dir / "grandchild.sigterm"
    grandchild_program = (
        "import signal,time\n"
        "from pathlib import Path\n"
        f"ready=Path({str(grandchild_ready_path)!r})\n"
        f"sentinel=Path({str(grandchild_sigterm_path)!r})\n"
        "def stop(signum, _frame):\n"
        "    sentinel.write_text('SIGTERM\\n', encoding='ascii')\n"
        "    raise SystemExit(128 + signum)\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        "ready.write_text('ready\\n', encoding='ascii')\n"
        "while True:\n"
        "    time.sleep(1)\n"
    )
    child_program = (
        "import signal,subprocess,time\n"
        "from pathlib import Path\n"
        "child=None\n"
        "def stop(signum, _frame):\n"
        "    if child is not None:\n"
        "        child.wait(timeout=2)\n"
        "    raise SystemExit(128 + signum)\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        f"child=subprocess.Popen([{sys.executable!r},'-c',{grandchild_program!r}])\n"
        f"ready=Path({str(grandchild_ready_path)!r})\n"
        "deadline=time.monotonic() + 5\n"
        "while not ready.is_file():\n"
        "    if child.poll() is not None:\n"
        "        raise RuntimeError('grandchild exited before readiness')\n"
        "    if time.monotonic() >= deadline:\n"
        "        raise TimeoutError('grandchild readiness timeout')\n"
        "    time.sleep(0.01)\n"
        f"Path({str(grandchild_pid_path)!r}).write_text(str(child.pid),encoding='ascii')\n"
        "while True:\n"
        "    time.sleep(1)\n"
    )
    result = runner._run_child(
        [sys.executable, "-c", child_program],
        stdout_path=output_dir / "stdout.txt",
        stderr_path=output_dir / "stderr.txt",
        wall_timeout=1.0,
        monitor_interval=0.01,
        output_dir=output_dir,
        resources=[],
        phase="descendant_timeout_test",
        min_free_bytes=1,
    )
    assert result["termination_reason"] == "wall_timeout"
    assert result["process_group_clean"] is True
    grandchild_pid = int(grandchild_pid_path.read_text(encoding="ascii"))
    assert grandchild_sigterm_path.read_text(encoding="ascii") == "SIGTERM\n"
    assert not (Path("/proc") / str(grandchild_pid)).exists()


def test_runner_reservation_manifest_and_gate_mismatch_contract(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    monkeypatch.setattr(runner, "ARTIFACT_ROOT", artifact_root)
    context = {
        "output_dir": (artifact_root / "formal-a001-20260723T000000Z-398f8725"),
        "git_snapshots": {"runner": {"head": "1" * 40}},
    }
    marker = runner._reserve_formal_attempt(context, ["runner", "--formal"])
    assert marker.is_file()
    second_context = {
        **context,
        "output_dir": (artifact_root / "formal-a001-20260723T000001Z-398f8725"),
    }
    with pytest.raises(runner.ToolchainError) as caught:
        runner._reserve_formal_attempt(second_context, ["runner", "--formal"])
    assert caught.value.code == "formal_attempt_already_consumed"

    output_dir = tmp_path / "manifest"
    output_dir.mkdir()
    formula = output_dir / "formula.opb"
    formula.write_text("* formula\n", encoding="ascii")
    (output_dir / "toolchain_record.json").write_text("{}\n", encoding="ascii")
    manifest_path = output_dir / "SHA256SUMS"
    manifest = runner._write_checksum_manifest(output_dir, manifest_path)
    assert manifest["covered_files"] == ["formula.opb"]
    assert runner._checksum_manifest_stable(output_dir, manifest_path, manifest)
    formula.write_text("* changed\n", encoding="ascii")
    assert not runner._checksum_manifest_stable(output_dir, manifest_path, manifest)
    formula.write_text("* formula\n", encoding="ascii")
    assert runner._checksum_manifest_stable(output_dir, manifest_path, manifest)
    unexpected_dir = output_dir / "unexpected"
    unexpected_dir.mkdir()
    assert not runner._checksum_manifest_stable(
        output_dir,
        manifest_path,
        manifest,
    )
    unexpected_dir.rmdir()
    broken = output_dir / "broken"
    broken.symlink_to(output_dir / "missing")
    assert not runner._checksum_manifest_stable(
        output_dir,
        manifest_path,
        manifest,
    )

    source = (RESEARCH_ROOT / "run_b1_r4_1188_22_pb_toolchain_v1.py").read_text(encoding="utf-8")
    assert "translation_gate_recheck_mismatch" in source
    planned = runner._planned_paths(tmp_path / "planned")
    assert planned["gate_recheck"].name == "translation_gate.recheck.json"
    assert planned["checksums"].name == "SHA256SUMS"
    assert planned["receipt"].name == "authority_receipt.json"
    assert planned["reservation"].name == "formal_attempt.reservation.json"


def test_authority_receipt_requires_detached_byte_identity(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "formal"
    output_dir.mkdir()
    formula = output_dir / "formula.opb"
    formula.write_text("* formula\n", encoding="ascii")
    reservation_source = tmp_path / "formal_attempt_a001.reservation.json"
    reservation_source.write_text('{"attempt":"a001"}\n', encoding="ascii")
    reservation_copy = output_dir / "formal_attempt.reservation.json"
    reservation_copy.write_bytes(reservation_source.read_bytes())
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    build_record = build_dir / "build_record.json"
    build_manifest = build_dir / "SHA256SUMS"
    build_record.write_text('{"status":"PASS"}\n', encoding="ascii")
    build_manifest.write_text("", encoding="ascii")

    manifest_path = output_dir / "SHA256SUMS"
    manifest = runner._write_checksum_manifest(output_dir, manifest_path)
    record_path = output_dir / "toolchain_record.json"
    _write_json(
        record_path,
        {
            "artifact_manifest": manifest,
            "claim": "none",
            "verified_result_candidate": "none",
            "failure_codes": ["unit_test_fail_closed"],
            "proof_tail_complete": False,
            "solver_declared_unsat": False,
            "veripb_verified": False,
        },
    )
    monkeypatch.setattr(
        runner,
        "_replay_toolchain_record_semantics",
        lambda *_args, **_kwargs: False,
    )
    receipt_path = output_dir / "authority_receipt.json"
    _write_json(
        receipt_path,
        {
            "schema_version": runner.AUTHORITY_RECEIPT_SCHEMA,
            "semantics": runner.SEMANTICS,
            "created_at_utc": "2026-07-23T00:00:00Z",
            "formal_attempt": "a001",
            "status": "FAIL_CLOSED",
            "claim": "none",
            "proof_status": "NO_MACHINE_VERIFIED_UNSAT_CLAIM",
            "upper_bound_update_authorized": False,
            "production_certified": False,
            "output_directory": str(output_dir),
            "raw_manifest": runner._file_record(manifest_path, PROJECT_ROOT),
            "toolchain_record": runner._file_record(record_path, PROJECT_ROOT),
            "reservation_source": runner._file_record(
                reservation_source,
                PROJECT_ROOT,
            ),
            "reservation_copy": runner._file_record(
                reservation_copy,
                PROJECT_ROOT,
            ),
            "build_record": runner._file_record(build_record, PROJECT_ROOT),
            "build_manifest": runner._file_record(
                build_manifest,
                PROJECT_ROOT,
            ),
            "formula": runner._file_record(formula, PROJECT_ROOT),
            "proof": None,
        },
    )
    identity = runner._file_record(receipt_path, PROJECT_ROOT)
    replay = runner._replay_authority_receipt(
        output_dir,
        reservation_source,
        build_record,
        build_manifest,
        PROJECT_ROOT,
        identity,
    )
    assert replay["status"] == "FAIL_CLOSED"

    original_receipt = receipt_path.read_bytes()
    receipt_path.write_text(
        json.dumps(_json(receipt_path), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert receipt_path.read_bytes() != original_receipt
    with pytest.raises(runner.ToolchainError, match="detached byte identity"):
        runner._replay_authority_receipt(
            output_dir,
            reservation_source,
            build_record,
            build_manifest,
            PROJECT_ROOT,
            identity,
        )
    receipt_path.write_bytes(original_receipt)

    record_path.write_bytes(record_path.read_bytes() + b" ")
    with pytest.raises(runner.ToolchainError, match="toolchain_record bytes"):
        runner._replay_authority_receipt(
            output_dir,
            reservation_source,
            build_record,
            build_manifest,
            PROJECT_ROOT,
            identity,
        )


def test_authoritative_verified_receipt_and_reader_documents(
    runner: ModuleType,
) -> None:
    replay = runner._replay_authority_receipt(
        FORMAL_AUTHORITY,
        FORMAL_RESERVATION,
        BUILD_AUTHORITY / "build_record.json",
        BUILD_AUTHORITY / "SHA256SUMS",
        PROJECT_ROOT,
        AUTHORITY_RECEIPT_IDENTITY,
    )
    assert replay["status"] == "VERIFIED"
    assert replay["claim"] == ("machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas")
    assert replay["payload"]["proof_status"] == "VERIFIED UNSATISFIABLE"
    assert replay["payload"]["upper_bound_update_authorized"] is True
    assert replay["payload"]["production_certified"] is False

    readme = (RESEARCH_ROOT / "README.md").read_text(encoding="utf-8")
    execution = (RESEARCH_ROOT / "03_execution_record.md").read_text(encoding="utf-8")
    for text in (readme, execution):
        assert "2026-07-23" in text
        assert "U: (1190,34) -> (1188,22)" in text
        assert "L: absent" in text
        assert AUTHORITY_RECEIPT_IDENTITY["sha256"] in text
        assert "production `CERTIFIED`" in text
    assert "2,084" in readme
    assert "2,192" in readme
    assert "attainability" in readme
    assert "global optimality" in readme
    assert "--solver-time-limit 3600" in execution
    assert "--solver-wall-timeout 3900" in execution
    assert "--verifier-wall-timeout 3600" in execution
    assert "MemoryHigh=37580963840" in execution
    assert "MemoryMax=41875931136" in execution
    assert "MemorySwapMax=17179869184" in execution


def test_toolchain_record_replay_rejects_deleted_or_partial_schema(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    with pytest.raises(runner.ToolchainError, match="closed expected object"):
        runner._replay_toolchain_record_semantics(
            {
                "claim": "none",
                "verified_result_candidate": "none",
                "failure_codes": ["partial"],
            },
            tmp_path,
            tmp_path / "reservation.json",
            tmp_path / "build_record.json",
            tmp_path / "SHA256SUMS",
            PROJECT_ROOT,
        )


def test_expected_constraint_multiset_shape(gate: ModuleType) -> None:
    expected = gate._build_expected(gate._derive(_problem_payload()))
    relations = Counter(key[0] for key in expected["constraints"].elements())
    assert relations == {"=": 1, ">=": 2191}
    assert len(expected["variables"]) == 2084
    coefficients = Counter(
        "positive" if item["coefficient"] > 0 else "zero" if item["coefficient"] == 0 else "negative"
        for item in expected["variables"]
    )
    assert coefficients == {"positive": 2, "negative": 2082}
    positive = [
        (item["width"], item["height"], item["coefficient"])
        for item in expected["variables"]
        if item["coefficient"] > 0
    ]
    assert positive == [(17, 70, 4), (70, 17, 4)]
