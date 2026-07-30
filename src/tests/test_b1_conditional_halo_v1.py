from __future__ import annotations

import ast
from collections import Counter, defaultdict
from copy import deepcopy
import errno
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from textwrap import dedent
from types import ModuleType, SimpleNamespace
import sys
import tempfile
import time
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH = PROJECT_ROOT / "docs/research/b1_conditional_halo_20260722"
STENCIL = RESEARCH / "conditional_halo_stencil_v1.json"
STRICT = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"


def _load_module(name: str, filename: str) -> ModuleType:
    path = RESEARCH / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def coordinate() -> ModuleType:
    return _load_module("b1_r2_coordinate_test", "verify_b1_conditional_halo_coordinates_v1.py")


@pytest.fixture(scope="module")
def prefix() -> ModuleType:
    return _load_module("b1_r2_prefix_test", "recompute_b1_conditional_halo_prefix_v1.py")


@pytest.fixture(scope="module")
def agreement() -> ModuleType:
    return _load_module("b1_r2_agreement_test", "compare_b1_conditional_halo_recomputations_v1.py")


@pytest.fixture(scope="module")
def corpus_builder() -> ModuleType:
    return _load_module("b1_r2_corpus_test", "build_b1_conditional_halo_diagnostic_corpus_v1.py")


@pytest.fixture(scope="module")
def encoder() -> ModuleType:
    return _load_module("b1_r2_encoder_test", "b1_conditional_halo_fixed_rectangle_encoder_v1.py")


@pytest.fixture(scope="module")
def translation() -> ModuleType:
    return _load_module("b1_r2_translation_test", "verify_b1_conditional_halo_translation_v1.py")


@pytest.fixture(scope="module")
def geometry_closer() -> ModuleType:
    return _load_module("b1_r2_geometry_closer_test", "close_b1_conditional_halo_geometry_gate_v1.py")


@pytest.fixture(scope="module")
def canary_runner() -> ModuleType:
    return _load_module("b1_r2_canary_test", "run_b1_conditional_halo_encoder_canaries_v1.py")


@pytest.fixture(scope="module")
def translation_closer() -> ModuleType:
    return _load_module("b1_r2_translation_closer_test", "close_b1_conditional_halo_translation_gate_v1.py")


@pytest.fixture(scope="module")
def sat_checker() -> ModuleType:
    return _load_module("b1_r2_sat_checker_test", "check_b1_conditional_halo_sat_assignment_v1.py")


@pytest.fixture(scope="module")
def constructor() -> ModuleType:
    return _load_module("b1_r2_constructor_test", "construct_b1_conditional_halo_sat_assignment_v1.py")


@pytest.fixture(scope="module")
def batch_orchestrator() -> ModuleType:
    return _load_module(
        "b1_r2_batch_orchestrator_test",
        "run_b1_conditional_halo_diagnostic_corpus_v1.py",
    )


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load_module("b1_r2_runner_test", "run_b1_conditional_halo_scan_v1.py")


@pytest.fixture(scope="module")
def manifest_verifier() -> ModuleType:
    return _load_module("b1_r2_manifest_test", "verify_b1_conditional_halo_run_manifest_v1.py")


@pytest.fixture(scope="module")
def completion() -> ModuleType:
    return _load_module("b1_r2_completion_test", "close_b1_conditional_halo_diagnostic_completion_v1.py")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _record(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    raw = resolved.read_bytes()
    try:
        display = resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        display = str(resolved)
    return {
        "path": display,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


@pytest.fixture(scope="module")
def geometry_reports(
    coordinate: ModuleType,
    prefix: ModuleType,
    agreement: ModuleType,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    direct = coordinate.build_report(PROJECT_ROOT, STENCIL)
    independent = prefix.make_report(PROJECT_ROOT, STENCIL)
    directory = tmp_path_factory.mktemp("b1-r2-full-geometry")
    direct_path = directory / "coordinate.json"
    independent_path = directory / "prefix.json"
    _write_json(direct_path, direct)
    _write_json(independent_path, independent)
    compared = agreement.compare(direct_path, independent_path)
    return {"direct": direct, "independent": independent, "agreement": compared}


@pytest.fixture(scope="module")
def diagnostic_cases(corpus_builder: ModuleType) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed = hashlib.sha256(b"b1-r2-test-deterministic-seed").digest()
    first = corpus_builder._build_cases(seed)
    second = corpus_builder._build_cases(seed)
    assert first == second
    return first


def test_strict_stencil_local_certificate_and_full_coordinate_agreement(
    geometry_reports: dict[str, Any],
) -> None:
    direct = geometry_reports["direct"]
    independent = geometry_reports["independent"]
    agreed = geometry_reports["agreement"]
    expected_ledger = {
        "grid_area": 4_900,
        "required_instance_count": 266,
        "required_body_area": 3_544,
        "powered_mandatory_count": 219,
        "powered_mandatory_area": 3_325,
        "power_pole_body_area": 4,
        "powered_oriented_shapes": [[3, 3], [4, 6], [5, 5], [6, 4]],
    }
    expected_stencil = {
        "orbit_count": 14,
        "support_cell_count": 96,
        "support_dx": [-8, 9],
        "support_dy": [-8, 9],
        "total_weight2": 792,
        "total_weight": 396,
    }
    expected_local = {
        "placement_counts": {"3x3": 180, "4x6": 220, "5x5": 220, "6x4": 220},
        "placement_total": 840,
        "minimum_doubled_slack": 0,
    }
    assert direct["strict_ledger"] == independent["strict_ledger"] == expected_ledger
    assert direct["stencil"] == independent["stencil"] == expected_stencil
    assert direct["local_halo_certificate"] == independent["local_halo_certificate"] == expected_local
    assert direct["conditional_halo"] == independent["conditional_halo"]
    assert direct["conditional_halo"]["pole_quantifier"] == "all_selected_poles"
    assert direct["conditional_halo"]["rhs_doubled"] == 6_650
    assert direct["actual_p_ledger"] == independent["actual_p_ledger"]
    assert direct["actual_p_ledger"]["ceiling_minimum_lhs_at_P9"] == 1_318
    assert direct["actual_p_ledger"]["ceiling_minimum_lhs_at_P10"] == 1_322

    direct_corpus = direct["ceiling_corpus"]
    independent_corpus = independent["ceiling_corpus"]
    assert direct_corpus == independent_corpus
    assert direct_corpus["rectangle_count"] == 2_520
    assert direct_corpus["pole_anchor_count"] == 4_761
    assert direct_corpus["pair_count"] == 11_997_720
    assert direct_corpus["canonical_digest_sha256"] == (
        "fe8da9696c2c7604f1153e4691ccdfe8e35b67a30adf54d301b421b113d096b2"
    )
    assert direct_corpus["body_intersection_pairs"] == 3_170_162
    assert direct_corpus["nonzero_removed_pairs"] == 5_936_612
    assert direct_corpus["nonzero_deficit_pairs"] == 9_568_548
    assert agreed["status"] == "PASS"
    assert agreed["corpus_errors"] == []
    assert all(item["status"] == "PASS" for item in agreed["checks"])


def test_direct_and_prefix_stencil_algorithms_expand_the_same_14_orbits(
    coordinate: ModuleType,
    prefix: ModuleType,
) -> None:
    stencil = json.loads(STENCIL.read_text(encoding="utf-8"))
    direct_support, direct_summary = coordinate.derive_stencil(stencil)
    prefix_support, prefix_summary = prefix.expand_stencil(stencil)
    assert sorted(direct_support) == sorted(prefix_support)
    assert direct_summary == prefix_summary
    assert coordinate.check_local_certificate(direct_support)["placement_total"] == 840
    assert prefix.local_check(prefix_support)["placement_total"] == 840


def test_geometry_implementations_do_not_import_each_other_or_the_encoder() -> None:
    forbidden = {
        "verify_b1_conditional_halo_coordinates_v1",
        "recompute_b1_conditional_halo_prefix_v1",
        "b1_conditional_halo_fixed_rectangle_encoder_v1",
        "verify_r3_certificates",
    }
    for filename in (
        "verify_b1_conditional_halo_coordinates_v1.py",
        "recompute_b1_conditional_halo_prefix_v1.py",
        "compare_b1_conditional_halo_recomputations_v1.py",
    ):
        tree = ast.parse((RESEARCH / filename).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(any(token in name for token in forbidden) for name in imported)


def test_diagnostic_corpus_is_deterministic_complete_and_transpose_closed(
    diagnostic_cases: tuple[list[dict[str, Any]], dict[str, Any]],
    corpus_builder: ModuleType,
) -> None:
    cases, selection = diagnostic_cases
    assert selection == {
        "r1_eligible_34x35_universe": 59_173,
        "delta_strata": 47,
        "nonempty_margin_bin_pairs": 9,
        "nonempty_contact_bin_pairs": 4,
        "deduplicated_base_cases": 256,
        "final_cases": 512,
        "control_treatment_pairs": 512,
        "transpose_symmetry_groups": 256,
    }
    assert len(cases) == 512
    assert len({case["case_id"] for case in cases}) == 512
    assert len({case["pair_id"] for case in cases}) == 512
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, case in enumerate(cases):
        assert case["case_index"] == index
        assert case["case_id"] == f"case_{index:03d}"
        groups[case["transpose_group_id"]].append(case)
    assert len(groups) == 256
    patterns = {item["delta"]: item for item in corpus_builder._patterns()}
    by_gaps = {(item["left_gap"], item["bottom_gap"]): item["delta"] for item in patterns.values()}
    for members in groups.values():
        assert {member["variant"] for member in members} == {"original", "transpose"}
        original = next(member for member in members if member["variant"] == "original")
        transposed = next(member for member in members if member["variant"] == "transpose")
        pattern = patterns[original["delta"]]
        assert (transposed["w"], transposed["h"], transposed["x"], transposed["y"]) == (
            original["h"],
            original["w"],
            original["y"],
            original["x"],
        )
        assert transposed["delta"] == by_gaps[(pattern["bottom_gap"], pattern["left_gap"])]
        assert (transposed["a_delta"], transposed["e_delta"]) == (
            original["a_delta"],
            original["e_delta"],
        )


def test_diagnostic_selection_covers_predeclared_delta_margin_and_contact_strata(
    diagnostic_cases: tuple[list[dict[str, Any]], dict[str, Any]],
) -> None:
    cases, _ = diagnostic_cases
    reasons = [reason for case in cases if case["variant"] == "original" for reason in case["selection_reasons"]]
    assert {reason for reason in reasons if reason.startswith("delta:")} == {f"delta:{delta}" for delta in range(47)}
    assert sum(reason.startswith("margin:") for reason in reasons) == 18
    assert sum(reason.startswith("contact:") for reason in reasons) == 8


@pytest.fixture(scope="module")
def model_builds(
    diagnostic_cases: tuple[list[dict[str, Any]], dict[str, Any]],
    encoder: ModuleType,
) -> dict[str, Any]:
    cases, _ = diagnostic_cases
    stencil, _ = encoder._stencil(STENCIL)
    return {
        scope: encoder._build(cases[0], stencil, scope) for scope in ("diagnostic_fixed_pattern", "band_any_pattern")
    }


@pytest.mark.parametrize(
    ("scope", "expected_equal"),
    [("diagnostic_fixed_pattern", 4), ("band_any_pattern", 3)],
)
def test_fixed_rectangle_common_ir_and_exact_one_halo_row(
    scope: str,
    expected_equal: int,
    model_builds: dict[str, Any],
) -> None:
    variables, control, halo, counts = model_builds[scope]
    assert len(variables) == 4_841
    count_variables = [item for item in variables if item["kind"] == "pole_count"]
    assert [item["count"] for item in count_variables] == list(range(9, 42))
    assert counts["pole_count_min"] == 9
    assert counts["pole_count_max"] == 41
    assert counts["pole_overlap_edges"] == 18_632
    assert counts["control_constraints"] == len(control)
    assert counts["treatment_constraints"] == len(control) + 1
    assert sum(item.relation == "=" for item in control) == expected_equal
    assert Counter(item.category for item in control)["pole_pair_overlap"] == 18_632
    link = next(item for item in control if item.category == "pole_count_link")
    assert link.relation == "=" and link.rhs == 0
    assert Counter(coefficient for _, coefficient in link.terms)[1] == 4_761
    assert {coefficient for _, coefficient in link.terms if coefficient < 0} == set(range(-41, -8))
    assert halo.category == "conditional_halo"
    assert halo.relation == ">=" and halo.rhs == 6_650
    assert all(coefficient > 0 for _, coefficient in halo.terms)
    assert not any(item.category == "conditional_halo" for item in control)
    assert [*control, halo][:-1] == control


def test_independent_translation_rebuilds_both_model_scopes(
    diagnostic_cases: tuple[list[dict[str, Any]], dict[str, Any]],
    model_builds: dict[str, Any],
    translation: ModuleType,
) -> None:
    cases, _ = diagnostic_cases
    stencil = translation._stencil(STENCIL)
    for scope, (variables, constraints, halo, counts) in model_builds.items():
        rebuilt_variables, rebuilt_constraints, rebuilt_halo, rebuilt_counts = translation._expected(
            cases[0], stencil, scope
        )
        assert rebuilt_variables == variables
        assert Counter(item.key() for item in rebuilt_constraints) == Counter(item.key() for item in constraints)
        assert rebuilt_halo.key() == halo.key()
        assert rebuilt_counts == counts


def _synthetic_geometry_admission(directory: Path) -> Path:
    roles = {
        "necessity_proof",
        "coordinate_report",
        "prefix_report",
        "agreement_report",
        "adversarial_verdict_json",
        "adversarial_verdict_doc",
    }
    inputs: dict[str, Any] = {"stencil": _record(STENCIL)}
    for role in sorted(roles):
        path = directory / f"{role}.txt"
        path.write_text(f"synthetic {role}\n", encoding="utf-8")
        inputs[role] = _record(path)
    path = directory / "geometry-admission.json"
    _write_json(
        path,
        {
            "schema_version": "b1_conditional_halo_geometry_admission_v1",
            "status": "PASS",
            "scope": "geometry_only_pre_encoder",
            "inputs": inputs,
            "conditional_halo": {
                "rhs_original": 3_325,
                "rhs_doubled": 6_650,
                "quantifier": "all_selected_poles",
            },
            "checks": [{"id": "synthetic-math-gate", "status": "PASS"}],
            "corpus_errors": [],
        },
    )
    return path


@pytest.fixture(scope="module")
def paired_fixture(
    corpus_builder: ModuleType,
    encoder: ModuleType,
    translation: ModuleType,
    canary_runner: ModuleType,
    translation_closer: ModuleType,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    directory = tmp_path_factory.mktemp("b1-r2-paired")
    r1_gate = directory / "r1-translation-gate.json"
    _write_json(
        r1_gate,
        {
            "schema_version": "b1_q_membrane_halo_band_translation_gate_v1",
            "status": "PASS",
            "corpus_errors": [],
        },
    )
    r1_sha = hashlib.sha256(r1_gate.read_bytes()).hexdigest()
    seed = hashlib.sha256(
        corpus_builder.LABEL + bytes.fromhex(corpus_builder.STRICT_SHA256) + bytes.fromhex(r1_sha)
    ).digest()
    cases, selection = corpus_builder._build_cases(seed)
    corpus = directory / "corpus.json"
    _write_json(
        corpus,
        {
            "schema_version": corpus_builder.SCHEMA,
            "status": "PASS",
            "manifest_state": "BUILT_BEFORE_RESULTS",
            "solver_results_included": False,
            "strict_instance": _record(STRICT),
            "r1_authoritative_translation_gate": _record(r1_gate),
            "selection": selection,
            "case_count": 512,
            "cases": cases,
            "corpus_errors": [],
        },
    )
    admission = _synthetic_geometry_admission(directory)
    paths: dict[str, Path] = {
        "directory": directory,
        "r1_gate": r1_gate,
        "corpus": corpus,
        "geometry_admission": admission,
        "control_opb": directory / "control.opb",
        "control_meta": directory / "control.meta.json",
        "control_var_map": directory / "control.var-map.json",
        "treatment_opb": directory / "treatment.opb",
        "treatment_meta": directory / "treatment.meta.json",
        "treatment_var_map": directory / "treatment.var-map.json",
        "translation_gate": directory / "translation-gate.json",
        "canaries": directory / "canaries.json",
        "translation_admission": directory / "translation-admission.json",
    }
    encoder_args = [
        "--project-root",
        str(PROJECT_ROOT),
        "--geometry-admission",
        str(admission),
        "--corpus",
        str(corpus),
        "--case-index",
        "0",
        "--model-scope",
        "diagnostic_fixed_pattern",
        "--control-opb",
        str(paths["control_opb"]),
        "--control-meta",
        str(paths["control_meta"]),
        "--control-var-map",
        str(paths["control_var_map"]),
        "--treatment-opb",
        str(paths["treatment_opb"]),
        "--treatment-meta",
        str(paths["treatment_meta"]),
        "--treatment-var-map",
        str(paths["treatment_var_map"]),
    ]
    assert encoder.main(encoder_args) == 0
    gate_args = [
        "--project-root",
        str(PROJECT_ROOT),
        "--geometry-admission",
        str(admission),
        "--corpus",
        str(corpus),
        "--case-index",
        "0",
        "--model-scope",
        "diagnostic_fixed_pattern",
        *[
            value
            for arm in ("control", "treatment")
            for value in (
                f"--{arm}-opb",
                str(paths[f"{arm}_opb"]),
                f"--{arm}-meta",
                str(paths[f"{arm}_meta"]),
                f"--{arm}-var-map",
                str(paths[f"{arm}_var_map"]),
            )
        ],
        "--output",
        str(paths["translation_gate"]),
    ]
    assert translation.main(gate_args) == 0
    canary_args = [
        *gate_args[:-2],
        "--output-dir",
        str(directory / "canary-work"),
        "--output",
        str(paths["canaries"]),
    ]
    assert canary_runner.main(canary_args) == 0
    close_args = [
        "--project-root",
        str(PROJECT_ROOT),
        "--geometry-admission",
        str(admission),
        "--corpus",
        str(corpus),
        *[
            value
            for arm in ("control", "treatment")
            for value in (
                f"--{arm}-opb",
                str(paths[f"{arm}_opb"]),
                f"--{arm}-meta",
                str(paths[f"{arm}_meta"]),
                f"--{arm}-var-map",
                str(paths[f"{arm}_var_map"]),
            )
        ],
        "--translation-gate",
        str(paths["translation_gate"]),
        "--canaries",
        str(paths["canaries"]),
        "--output",
        str(paths["translation_admission"]),
    ]
    assert translation_closer.main(close_args) == 0
    return {
        "paths": paths,
        "cases": cases,
        "encoder_args": encoder_args,
        "gate_args": gate_args,
        "close_args": close_args,
    }


def test_translation_gate_canaries_and_split_admissions_close_one_pair(
    paired_fixture: dict[str, Any],
) -> None:
    paths = paired_fixture["paths"]
    geometry = _read_json(paths["geometry_admission"])
    gate = _read_json(paths["translation_gate"])
    canaries = _read_json(paths["canaries"])
    admission = _read_json(paths["translation_admission"])
    assert geometry["scope"] == "geometry_only_pre_encoder"
    assert "translation_gate" not in geometry["inputs"]
    assert gate["status"] == "PASS" and gate["corpus_errors"] == []
    assert gate["missing"] == [] and gate["unexpected"] == []
    assert gate["paired_diff"]["exactly_one_conditional_halo"] is True
    assert len(gate["paired_diff"]["added"]) == 1 and gate["paired_diff"]["removed"] == []
    assert canaries["status"] == "PASS" and canaries["all_killed"] is True
    assert set(canaries["canaries"]) == {
        "arm_contamination",
        "deletion_resealed",
        "deletion_unsealed",
        "wrong_rhs",
    }
    assert all(item["killed"] is True for item in canaries["canaries"].values())
    assert admission["status"] == "PASS"
    assert admission["case_index"] == 0
    assert admission["paired_generation_sha256"] == gate["paired_generation_sha256"]
    assert all(admission["checks"].values())
    assert admission["proof_status"] == "translation_admission_only_no_solver_or_proof_no_sat_or_unsat_claim"


def test_translation_admission_rejects_same_case_scope_canaries_from_another_pair_generation(
    paired_fixture: dict[str, Any],
    translation_closer: ModuleType,
    tmp_path: Path,
) -> None:
    paths = paired_fixture["paths"]
    substituted = deepcopy(_read_json(paths["canaries"]))
    assert substituted["case_index"] == 0
    assert substituted["model_scope"] == "diagnostic_fixed_pattern"
    substituted["paired_generation_sha256"] = "f" * 64
    substituted_path = tmp_path / "same-case-scope-other-generation-canaries.json"
    _write_json(substituted_path, substituted)
    close_args = [*paired_fixture["close_args"]]
    close_args[close_args.index("--canaries") + 1] = str(substituted_path)
    output = tmp_path / "translation-admission.json"
    close_args[close_args.index("--output") + 1] = str(output)
    with pytest.raises(translation_closer.CloseError, match="not byte-bound to this exact paired model"):
        translation_closer.main(close_args)
    assert not output.exists()


def test_canary_mutant_metadata_supports_disposable_external_workspace(
    paired_fixture: dict[str, Any],
    canary_runner: ModuleType,
) -> None:
    paths = paired_fixture["paths"]
    with tempfile.TemporaryDirectory(prefix="b1-r2-external-canary-") as temporary:
        output = Path(temporary) / "mutant.meta.json"
        canary_runner._reseal_meta(
            paths["control_meta"],
            output,
            paths["control_opb"],
            PROJECT_ROOT,
        )
        payload = _read_json(output)
        assert payload["outputs"]["metadata"] == {"path": str(output.resolve())}
        assert payload["outputs"]["opb"] == _record(paths["control_opb"])


def test_runner_accepts_the_geometry_admission_list_check_schema(
    paired_fixture: dict[str, Any],
    runner: ModuleType,
) -> None:
    admission, record = runner._geometry_admission(
        paired_fixture["paths"]["geometry_admission"],
        PROJECT_ROOT,
    )
    assert admission["status"] == "PASS"
    assert admission["checks"] == [{"id": "synthetic-math-gate", "status": "PASS"}]
    assert record == runner._record(paired_fixture["paths"]["geometry_admission"], PROJECT_ROOT)

    paths = paired_fixture["paths"]
    context = runner._validate_inputs(
        SimpleNamespace(
            project_root=PROJECT_ROOT,
            corpus=paths["corpus"],
            case_index=0,
            geometry_admission=paths["geometry_admission"],
            translation_admission=paths["translation_admission"],
            translation_gate=paths["translation_gate"],
            control_opb=paths["control_opb"],
            control_meta=paths["control_meta"],
            control_var_map=paths["control_var_map"],
            treatment_opb=paths["treatment_opb"],
            treatment_meta=paths["treatment_meta"],
            treatment_var_map=paths["treatment_var_map"],
        )
    )
    assert context["case_index"] == 0
    assert context["pair_id"] == paired_fixture["cases"][0]["pair_id"]
    assert context["transpose_group_id"] == paired_fixture["cases"][0]["transpose_group_id"]
    assert context["records"]["translation_admission"] == runner._record(paths["translation_admission"], PROJECT_ROOT)


def test_geometry_and_translation_admissions_fail_closed_and_do_not_overwrite(
    paired_fixture: dict[str, Any],
    encoder: ModuleType,
    translation_closer: ModuleType,
    tmp_path: Path,
) -> None:
    paths = paired_fixture["paths"]
    bad = deepcopy(_read_json(paths["geometry_admission"]))
    bad["conditional_halo"]["quantifier"] = "any_nine_poles"
    bad_path = tmp_path / "bad-geometry.json"
    _write_json(bad_path, bad)
    with pytest.raises(encoder.EncoderError, match="halo statement drifted"):
        encoder._validate_admission(bad_path, PROJECT_ROOT)
    with pytest.raises(FileExistsError):
        encoder.main(paired_fixture["encoder_args"])
    with pytest.raises(FileExistsError):
        translation_closer.main(paired_fixture["close_args"])


def test_geometry_closer_uses_exclusive_creation(
    geometry_closer: ModuleType,
    tmp_path: Path,
) -> None:
    output = tmp_path / "geometry.json"
    geometry_closer.write_exclusive(output, {"status": "PASS"})
    with pytest.raises(FileExistsError):
        geometry_closer.write_exclusive(output, {"status": "PASS"})


def _low_halo_assignment(
    paired_fixture: dict[str, Any],
    sat_checker: ModuleType,
    arm: str,
) -> tuple[dict[str, Any], int]:
    paths = paired_fixture["paths"]
    metadata = _read_json(paths[f"{arm}_meta"])
    var_map = _read_json(paths[f"{arm}_var_map"])
    case = metadata["case"]
    rectangle = {
        (x, y) for x in range(case["x"], case["x"] + case["w"]) for y in range(case["y"], case["y"] + case["h"])
    }
    pattern = sat_checker._patterns()[case["delta"]]
    forbidden = pattern["body"] | pattern["q"]
    stencil = sat_checker._stencil(STENCIL)
    candidates: list[tuple[int, tuple[int, int], int]] = []
    for variable in var_map["variables"]:
        if variable["kind"] != "pole_anchor":
            continue
        anchor = (variable["x"], variable["y"])
        body = {(anchor[0] + dx, anchor[1] + dy) for dx in range(2) for dy in range(2)}
        if body & rectangle or body & forbidden:
            continue
        capacity = sum(
            weight
            for (dx, dy), weight in stencil.items()
            if 0 <= anchor[0] + dx < 70
            and 0 <= anchor[1] + dy < 70
            and (anchor[0] + dx, anchor[1] + dy) not in rectangle
        )
        candidates.append((capacity, anchor, variable["id"]))
    selected: list[tuple[int, tuple[int, int], int]] = []
    for candidate in sorted(candidates):
        if all(abs(candidate[1][0] - other[1][0]) > 1 or abs(candidate[1][1] - other[1][1]) > 1 for other in selected):
            selected.append(candidate)
            if len(selected) == 9:
                break
    assert len(selected) == 9
    halo_lhs2 = sum(item[0] for item in selected)
    assert halo_lhs2 < 6_650
    values = [0] * 4_841
    values[case["delta"]] = 1
    for _, _, variable_id in selected:
        values[variable_id - 1] = 1
    count_nine = next(
        item["id"] for item in var_map["variables"] if item["kind"] == "pole_count" and item["count"] == 9
    )
    values[count_nine - 1] = 1
    return {
        "schema_version": "b1_conditional_halo_full_assignment_v1",
        "opb_sha256": hashlib.sha256(paths[f"{arm}_opb"].read_bytes()).hexdigest(),
        "values": values,
    }, halo_lhs2


def _sat_args(paired_fixture: dict[str, Any], arm: str, assignment: Path, output: Path) -> list[str]:
    paths = paired_fixture["paths"]
    return [
        "--project-root",
        str(PROJECT_ROOT),
        "--geometry-admission",
        str(paths["geometry_admission"]),
        "--arm",
        arm,
        "--opb",
        str(paths[f"{arm}_opb"]),
        "--metadata",
        str(paths[f"{arm}_meta"]),
        "--var-map",
        str(paths[f"{arm}_var_map"]),
        "--assignment",
        str(assignment),
        "--output",
        str(output),
    ]


def test_sat_checker_accepts_control_but_rejects_malformed_and_halo_failure(
    paired_fixture: dict[str, Any],
    sat_checker: ModuleType,
    tmp_path: Path,
) -> None:
    control, halo_lhs2 = _low_halo_assignment(paired_fixture, sat_checker, "control")
    control_path = tmp_path / "control-assignment.json"
    control_output = tmp_path / "control-check.json"
    _write_json(control_path, control)
    assert sat_checker.main(_sat_args(paired_fixture, "control", control_path, control_output)) == 0
    checked = _read_json(control_output)
    assert checked["assignment_status"] == "CHECKED_SAT"
    assert checked["semantic_checks"]["halo_lhs2"] == halo_lhs2
    assert checked["semantic_checks"]["halo_rhs2"] is None

    malformed = deepcopy(control)
    malformed["values"] = malformed["values"][:-1]
    malformed_path = tmp_path / "malformed-assignment.json"
    _write_json(malformed_path, malformed)
    with pytest.raises(sat_checker.AssignmentError, match="full 4841-bit"):
        sat_checker.main(_sat_args(paired_fixture, "control", malformed_path, tmp_path / "bad-check.json"))

    treatment, _ = _low_halo_assignment(paired_fixture, sat_checker, "treatment")
    treatment_path = tmp_path / "treatment-assignment.json"
    _write_json(treatment_path, treatment)
    with pytest.raises(sat_checker.AssignmentError, match="conditional-halo constraint failed"):
        sat_checker.main(_sat_args(paired_fixture, "treatment", treatment_path, tmp_path / "treatment-check.json"))


def _constructor_args(
    paired_fixture: dict[str, Any],
    arm: str,
    output: Path,
) -> list[str]:
    paths = paired_fixture["paths"]
    return [
        "--project-root",
        str(PROJECT_ROOT),
        "--geometry-admission",
        str(paths["geometry_admission"]),
        "--stencil",
        str(STENCIL),
        "--corpus",
        str(paths["corpus"]),
        "--case-index",
        "0",
        "--arm",
        arm,
        "--opb",
        str(paths[f"{arm}_opb"]),
        "--metadata",
        str(paths[f"{arm}_meta"]),
        "--var-map",
        str(paths[f"{arm}_var_map"]),
        "--output",
        str(output),
        "--node-limit",
        "250000",
    ]


def test_constructor_is_deterministic_and_both_arms_are_independently_checked_sat(
    paired_fixture: dict[str, Any],
    constructor: ModuleType,
    sat_checker: ModuleType,
    tmp_path: Path,
) -> None:
    assignments: dict[str, dict[str, Any]] = {}
    for arm in ("control", "treatment"):
        assignment = tmp_path / f"{arm}.assignment.json"
        assert constructor.main(_constructor_args(paired_fixture, arm, assignment)) == 0
        assignments[arm] = _read_json(assignment)
        checked = tmp_path / f"{arm}.checked.json"
        assert sat_checker.main(_sat_args(paired_fixture, arm, assignment, checked)) == 0
        checked_payload = _read_json(checked)
        assert checked_payload["assignment_status"] == "CHECKED_SAT"
        assert checked_payload["semantic_checks"]["halo_lhs2"] >= 6_650
        assert checked_payload["semantic_checks"]["actual_p"] == 9

    assert assignments["control"]["values"] == assignments["treatment"]["values"]
    repeated = tmp_path / "treatment-repeat.assignment.json"
    assert constructor.main(_constructor_args(paired_fixture, "treatment", repeated)) == 0
    assert _read_json(repeated)["values"] == assignments["treatment"]["values"]


def test_constructor_unknown_binding_and_no_overwrite_fail_closed(
    paired_fixture: dict[str, Any],
    constructor: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    malformed = _constructor_args(paired_fixture, "treatment", tmp_path / "malformed.json")
    metadata_index = malformed.index("--metadata") + 1
    malformed[metadata_index] = str(paired_fixture["paths"]["control_meta"])
    assert constructor.main(malformed) == 2
    assert not (tmp_path / "malformed.json").exists()

    existing = tmp_path / "existing.json"
    existing.write_text("keep\n", encoding="utf-8")
    assert constructor.main(_constructor_args(paired_fixture, "control", existing)) == 2
    assert existing.read_text(encoding="utf-8") == "keep\n"

    monkeypatch.setattr(
        constructor,
        "_construct",
        lambda _case, _var_map, _stencil, node_limit: (
            None,
            {
                "candidate_count": 0,
                "search_method": "synthetic_exhaustion",
                "bounded_search_node_limit": node_limit,
                "bounded_search_nodes": node_limit,
                "bounded_search_limit_reached": True,
                "required_poles": 9,
                "halo_rhs2": 6_650,
            },
        ),
    )
    unknown = tmp_path / "unknown.json"
    assert constructor.main(_constructor_args(paired_fixture, "control", unknown)) == constructor.UNKNOWN_EXIT
    payload = _read_json(unknown)
    assert payload["status"] == "UNKNOWN"
    assert payload["values"] is None
    assert payload["case_index"] == 0
    assert payload["arm"] == "control"


def test_attribution_matrix_is_identical_across_runner_manifest_and_completion(
    runner: ModuleType,
    manifest_verifier: ModuleType,
    completion: ModuleType,
) -> None:
    runner_expected = {
        ("CHECKED_SAT", "CHECKED_SAT"): ("treatment_survivor", "COMPLETE"),
        ("CHECKED_SAT", "VERIFIED_UNSAT"): ("halo_pruned", "COMPLETE"),
        ("VERIFIED_UNSAT", "VERIFIED_UNSAT"): ("control_pruned", "COMPLETE"),
        ("VERIFIED_UNSAT", "CHECKED_SAT"): ("monotonicity_contradiction", "FAIL"),
        ("UNKNOWN", "CHECKED_SAT"): ("incomplete", "INCOMPLETE"),
    }
    for statuses, wanted in runner_expected.items():
        assert runner._attribution(*statuses) == wanted
    assert manifest_verifier._expected_attribution("CHECKED_SAT", "CHECKED_SAT") == (
        "treatment_survivor",
        "COMPLETE",
    )
    assert completion._expected_attribution("CHECKED_SAT", "CHECKED_SAT") == (
        "treatment_survivor",
        "COMPLETE",
    )
    for statuses in (
        ("CHECKED_SAT", "VERIFIED_UNSAT"),
        ("VERIFIED_UNSAT", "VERIFIED_UNSAT"),
        ("VERIFIED_UNSAT", "CHECKED_SAT"),
        ("UNKNOWN", "CHECKED_SAT"),
    ):
        assert manifest_verifier._expected_attribution(*statuses) == ("incomplete", "INCOMPLETE")
        assert completion._expected_attribution(*statuses) == ("incomplete", "INCOMPLETE")


def test_runner_disk_gate_is_inclusive_at_exact_threshold_and_no_go_one_byte_low(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = {
        "root": PROJECT_ROOT,
        "paths": {},
        "case": {"case_index": 0},
        "case_index": 0,
        "case_id": "case_000",
        "pair_id": "pair_000",
        "transpose_group_id": "transpose_000",
        "paired_generation_sha256": "a" * 64,
        "records": {},
        "added_constraint": json.dumps(
            {"terms": [[48, 792]], "relation": ">=", "rhs": 6_650},
            sort_keys=True,
            separators=(",", ":"),
        ),
    }
    args = SimpleNamespace(
        control_checked_sat=None,
        treatment_checked_sat=None,
        preflight_only=True,
    )
    monkeypatch.setattr(runner, "_snapshot_inputs", lambda _context, _output: {})
    runtime_calls: list[bool] = []

    def fake_runtime(_args: Any, _root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        runtime_calls.append(True)
        return {"identity": "synthetic"}, {"contract_pass": True}

    monkeypatch.setattr(runner, "_validate_runtime", fake_runtime)
    threshold = runner.FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES

    exact = tmp_path / "exact"
    exact.mkdir()
    monkeypatch.setattr(runner, "_free_bytes", lambda _path: threshold)
    exact_record, exact_exit = runner._execute(args, context, exact, ["synthetic"])
    assert exact_exit == 1
    assert exact_record["preflight"]["decision"] == "GO"
    assert exact_record["preflight"]["formal_child_spawned"] is False
    assert [arm["terminal_status"] for arm in exact_record["arms"].values()] == ["NOT_RUN", "NOT_RUN"]
    assert runtime_calls == [True]

    low = tmp_path / "one-byte-low"
    low.mkdir()
    monkeypatch.setattr(runner, "_free_bytes", lambda _path: threshold - 1)
    low_record, low_exit = runner._execute(args, context, low, ["synthetic"])
    assert low_exit == 3
    assert low_record["status"] == "NO_GO"
    assert low_record["preflight"]["decision"] == "NO_GO"
    assert low_record["preflight"]["formal_child_spawned"] is False
    assert [arm["terminal_status"] for arm in low_record["arms"].values()] == ["NO_GO", "NO_GO"]
    assert runtime_calls == [True]
    assert low_record["mcp_ownership"] == {
        "mcp_processes_started_by_runner": [],
        "cleanup_required": False,
        "note": "runner invokes only pinned local proof tools and starts no MCP server",
    }


def test_runner_hard_link_snapshot_mutation_after_initial_validation_cannot_reseal(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.opb"
    source.write_bytes(b"* #variable= 1 #constraint= 1\n+1 x1 >= 1 ;\n")
    run = tmp_path / "run"
    run.mkdir()
    destination = run / "inputs" / "control.opb"

    source_record = runner._record(source, PROJECT_ROOT)
    record = runner._copy(source, destination, PROJECT_ROOT, source_record)
    assert set(record) == {"path", "sha256", "size_bytes"}
    assert destination.read_bytes() == source.read_bytes()
    assert (destination.stat().st_dev, destination.stat().st_ino) == (
        source.stat().st_dev,
        source.stat().st_ino,
    )
    assert source.resolve(strict=True).is_file()
    assert destination.resolve(strict=True).is_file()

    source.write_bytes(b"tampered after manifest\n")
    assert destination.read_bytes() == source.read_bytes()
    with pytest.raises(runner.ScanError, match="protected snapshot changed while sealing"):
        runner._manifest(run, PROJECT_ROOT, [record])


def test_runner_snapshot_rejects_source_drift_against_pre_snapshot_record(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(b'{"stable":true}\n')
    destination = tmp_path / "run" / "inputs" / "source.json"

    expected = runner._record(source, PROJECT_ROOT)
    source.write_bytes(b'{"stable":false}\n')
    with pytest.raises(runner.ScanError, match="source bytes drifted"):
        runner._copy(source, destination, PROJECT_ROOT, expected)


def test_runner_snapshot_uses_exclusive_copy_only_on_exdev(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(b'{"stable":true}\n')
    destination = tmp_path / "run" / "inputs" / "source.json"

    def cross_device(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.EXDEV, "synthetic cross-device link")

    monkeypatch.setattr(runner.os, "link", cross_device)
    record = runner._copy(source, destination, PROJECT_ROOT, runner._record(source, PROJECT_ROOT))
    assert set(record) == {"path", "sha256", "size_bytes"}
    assert destination.read_bytes() == source.read_bytes()
    assert (destination.stat().st_dev, destination.stat().st_ino) != (
        source.stat().st_dev,
        source.stat().st_ino,
    )


def test_runner_snapshot_rejects_unsafe_sources_existing_destination_and_copy_failure(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.opb"
    source.write_bytes(b"source\n")
    symlink = tmp_path / "source-link.opb"
    symlink.symlink_to(source)
    with pytest.raises(runner.ScanError, match="not a regular file"):
        runner._copy(symlink, tmp_path / "symlink-snapshot.opb", PROJECT_ROOT)
    with pytest.raises(runner.ScanError, match="not a regular file"):
        runner._copy(tmp_path, tmp_path / "directory-snapshot", PROJECT_ROOT)

    existing = tmp_path / "existing.opb"
    existing.write_bytes(b"keep me\n")
    with pytest.raises(runner.ScanError, match="already exists"):
        runner._copy(source, existing, PROJECT_ROOT)
    assert existing.read_bytes() == b"keep me\n"

    denied = tmp_path / "denied.opb"

    def permission_denied(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.EACCES, "synthetic permission denial")

    monkeypatch.setattr(runner.os, "link", permission_denied)
    with pytest.raises(runner.ScanError, match="cannot hard-link snapshot"):
        runner._copy(source, denied, PROJECT_ROOT)
    assert not denied.exists()


def _make_checked_pair_run(
    directory: Path,
    paired_fixture: dict[str, Any],
    constructor: ModuleType,
    sat_checker: ModuleType,
    runner: ModuleType,
    request: pytest.FixtureRequest,
) -> Path:
    evidence = directory / "evidence"
    evidence.mkdir(parents=True)
    checked_paths: dict[str, Path] = {}
    for arm in ("control", "treatment"):
        assignment = evidence / f"{arm}.assignment.json"
        checked = evidence / f"{arm}.checked.json"
        assert constructor.main(_constructor_args(paired_fixture, arm, assignment)) == 0
        assert sat_checker.main(_sat_args(paired_fixture, arm, assignment, checked)) == 0
        checked_paths[arm] = checked
    paths = paired_fixture["paths"]
    context = runner._validate_inputs(
        SimpleNamespace(
            project_root=PROJECT_ROOT,
            corpus=paths["corpus"],
            case_index=0,
            geometry_admission=paths["geometry_admission"],
            translation_admission=paths["translation_admission"],
            translation_gate=paths["translation_gate"],
            control_opb=paths["control_opb"],
            control_meta=paths["control_meta"],
            control_var_map=paths["control_var_map"],
            treatment_opb=paths["treatment_opb"],
            treatment_meta=paths["treatment_meta"],
            treatment_var_map=paths["treatment_var_map"],
        )
    )
    run = directory / "pair-run"
    run.mkdir()

    def remove_pair_run() -> None:
        if run.exists():
            shutil.rmtree(run)
        assert not run.exists()

    request.addfinalizer(remove_pair_run)
    payload, exit_code = runner._execute(
        SimpleNamespace(
            control_checked_sat=checked_paths["control"],
            treatment_checked_sat=checked_paths["treatment"],
            preflight_only=False,
        ),
        context,
        run,
        ["synthetic-dual-checked-sat-run"],
    )
    assert exit_code == 0
    assert payload["status"] == "COMPLETE"
    assert payload["pre_seal_revalidation"]["copy_strategy"] == ("hard_link_same_filesystem_exclusive_copy_on_exdev")
    return run


def test_recursive_manifest_independently_rechecks_dual_sat_and_rejects_symlinks(
    manifest_verifier: ModuleType,
    paired_fixture: dict[str, Any],
    constructor: ModuleType,
    sat_checker: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    run = _make_checked_pair_run(tmp_path, paired_fixture, constructor, sat_checker, runner, request)
    manifest = run / manifest_verifier.MANIFEST_NAME
    record = run / manifest_verifier.RUN_RECORD_NAME
    result = manifest_verifier.verify(run, manifest, record, PROJECT_ROOT)
    assert result["status"] == "PASS"
    assert result["corpus_errors"] == []
    assert result["checks"]["dual_checked_sat_evidence_independently_validated"] is True
    (run / "unexpected-link").symlink_to(run / "run_started.json")
    with pytest.raises(manifest_verifier.ManifestError, match="symlink forbidden"):
        manifest_verifier.verify(run, manifest, record, PROJECT_ROOT)


def test_manifest_verifier_rejects_status_only_missing_evidence_and_swapped_model_canaries(
    manifest_verifier: ModuleType,
    paired_fixture: dict[str, Any],
    constructor: ModuleType,
    sat_checker: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    run = _make_checked_pair_run(tmp_path, paired_fixture, constructor, sat_checker, runner, request)
    manifest = run / manifest_verifier.MANIFEST_NAME
    record = run / manifest_verifier.RUN_RECORD_NAME
    original_record = record.read_bytes()
    payload = _read_json(record)

    del payload["arms"]["control"]["checked_sat"]
    _write_json(record, payload)
    with pytest.raises(manifest_verifier.ManifestError, match="snapshot record is missing"):
        manifest_verifier.verify(run, manifest, record, PROJECT_ROOT)
    record.write_bytes(original_record)

    payload = _read_json(record)
    for role in ("assignment", "checker"):
        evidence = Path(payload["arms"]["control"]["checked_sat"]["copied"][role]["path"])
        evidence = evidence if evidence.is_absolute() else PROJECT_ROOT / evidence
        held = evidence.with_name(f"{evidence.name}.held")
        evidence.rename(held)
        with pytest.raises(manifest_verifier.ManifestError):
            manifest_verifier.verify(run, manifest, record, PROJECT_ROOT)
        held.rename(evidence)

    control_model = Path(payload["input_copies"]["control_opb"]["path"])
    treatment_model = Path(payload["input_copies"]["treatment_opb"]["path"])
    control_model = control_model if control_model.is_absolute() else PROJECT_ROOT / control_model
    treatment_model = treatment_model if treatment_model.is_absolute() else PROJECT_ROOT / treatment_model
    control_bytes, treatment_bytes = control_model.read_bytes(), treatment_model.read_bytes()
    control_model.unlink()
    treatment_model.unlink()
    control_model.write_bytes(treatment_bytes)
    treatment_model.write_bytes(control_bytes)
    manifest.unlink()
    payload["artifact_manifest"] = runner._manifest(run, PROJECT_ROOT)
    _write_json(record, payload)
    with pytest.raises(manifest_verifier.ManifestError, match="input_copies.control_opb is stale"):
        manifest_verifier.verify(run, manifest, record, PROJECT_ROOT)


def test_completion_requires_the_bound_strict_independent_evidence_check_set(
    completion: ModuleType,
    manifest_verifier: ModuleType,
    paired_fixture: dict[str, Any],
    constructor: ModuleType,
    sat_checker: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    run = _make_checked_pair_run(tmp_path, paired_fixture, constructor, sat_checker, runner, request)
    manifest = run / manifest_verifier.MANIFEST_NAME
    record = run / manifest_verifier.RUN_RECORD_NAME
    verification_path = tmp_path / "manifest-verification.json"
    verification = manifest_verifier.verify(run, manifest, record, PROJECT_ROOT)
    _write_json(verification_path, verification)
    case = paired_fixture["cases"][0]
    entry = {
        "case_index": 0,
        "case_id": case["case_id"],
        "pair_id": case["pair_id"],
        "transpose_group_id": case["transpose_group_id"],
        "pair_run": completion._record(record, PROJECT_ROOT),
        "run_manifest": completion._record(manifest, PROJECT_ROOT),
        "manifest_verification": completion._record(verification_path, PROJECT_ROOT),
    }
    attribution, summary = completion._validate_entry(entry, case, PROJECT_ROOT)
    assert attribution == "treatment_survivor"
    assert summary["control"] == summary["treatment"] == "CHECKED_SAT"

    verification["checks"].pop("dual_checked_sat_evidence_independently_validated")
    _write_json(verification_path, verification)
    entry["manifest_verification"] = completion._record(verification_path, PROJECT_ROOT)
    with pytest.raises(completion.CompletionError, match="independent manifest verification"):
        completion._validate_entry(entry, case, PROJECT_ROOT)


def test_diagnostic_completion_requires_exactly_512_pairs_and_1024_terminal_arms(
    completion: ModuleType,
    paired_fixture: dict[str, Any],
    tmp_path: Path,
) -> None:
    paths = paired_fixture["paths"]
    run_index = tmp_path / "incomplete-run-index.json"
    _write_json(
        run_index,
        {
            "schema_version": completion.RUN_INDEX_SCHEMA,
            "status": "PASS",
            "pair_count": 512,
            "arm_count": 1_024,
            "corpus_manifest": completion._record(paths["corpus"], PROJECT_ROOT),
            "entries": [],
            "corpus_errors": [],
        },
    )
    output = tmp_path / "completion.json"
    assert (
        completion.main(
            [
                "--project-root",
                str(PROJECT_ROOT),
                "--corpus",
                str(paths["corpus"]),
                "--run-index",
                str(run_index),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    result = _read_json(output)
    assert result["status"] == "INCOMPLETE"
    assert result["completion_contract"] == {
        "required_pairs": 512,
        "required_arms": 1_024,
        "actual_pairs": 0,
        "actual_arms": 0,
    }
    assert result["bound_ledger"]["global_update_authorized"] is False
    assert (
        completion.main(
            [
                "--project-root",
                str(PROJECT_ROOT),
                "--corpus",
                str(paths["corpus"]),
                "--run-index",
                str(run_index),
                "--output",
                str(output),
            ]
        )
        == 2
    )


def test_diagnostic_completion_counts_all_pairs_and_fails_closed_on_unknown(
    completion: ModuleType,
    paired_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = paired_fixture["paths"]
    entries = [
        {
            "case_index": index,
            "case_id": f"case_{index:03d}",
            "pair_id": paired_fixture["cases"][index]["pair_id"],
            "transpose_group_id": paired_fixture["cases"][index]["transpose_group_id"],
        }
        for index in range(512)
    ]
    run_index = tmp_path / "complete-run-index.json"
    _write_json(
        run_index,
        {
            "schema_version": completion.RUN_INDEX_SCHEMA,
            "status": "PASS",
            "pair_count": 512,
            "arm_count": 1_024,
            "corpus_manifest": completion._record(paths["corpus"], PROJECT_ROOT),
            "entries": entries,
            "corpus_errors": [],
        },
    )

    def terminal_entry(entry: dict[str, Any], case: dict[str, Any], _root: Path) -> tuple[str, dict[str, Any]]:
        assert entry["case_index"] == case["case_index"]
        index = case["case_index"]
        return "treatment_survivor", {
            "case_index": index,
            "paired_generation_sha256": f"{index:064x}",
        }

    monkeypatch.setattr(completion, "_validate_entry", terminal_entry)
    result = completion.complete(PROJECT_ROOT, paths["corpus"], run_index)
    assert result["status"] == "PASS"
    assert result["completion_contract"] == {
        "required_pairs": 512,
        "required_arms": 1_024,
        "actual_pairs": 512,
        "actual_arms": 1_024,
        "unknown_arms": 0,
        "monotonicity_contradictions": 0,
        "unique_pair_ids": 512,
        "transpose_groups": 256,
    }
    assert result["attribution_counts"] == {"treatment_survivor": 512}
    assert result["bound_ledger"]["global_update_authorized"] is False

    def unknown_entry(entry: dict[str, Any], case: dict[str, Any], root: Path) -> tuple[str, dict[str, Any]]:
        if case["case_index"] == 7:
            raise completion.CompletionError("entry 7 has UNKNOWN/nonterminal arm")
        return terminal_entry(entry, case, root)

    monkeypatch.setattr(completion, "_validate_entry", unknown_entry)
    with pytest.raises(completion.CompletionError, match="UNKNOWN/nonterminal"):
        completion.complete(PROJECT_ROOT, paths["corpus"], run_index)


def test_runner_rejects_duplicate_pair_ids_and_incomplete_transpose_groups(
    runner: ModuleType,
    paired_fixture: dict[str, Any],
    tmp_path: Path,
) -> None:
    corpus = deepcopy(_read_json(paired_fixture["paths"]["corpus"]))
    corpus["cases"][1]["pair_id"] = corpus["cases"][0]["pair_id"]
    duplicate = tmp_path / "duplicate-pair.json"
    _write_json(duplicate, corpus)
    with pytest.raises(runner.ScanError, match="512 unique"):
        runner._corpus(duplicate, PROJECT_ROOT, 0)

    corpus = deepcopy(_read_json(paired_fixture["paths"]["corpus"]))
    corpus["cases"][1]["transpose_group_id"] = "orphan-group"
    orphan = tmp_path / "orphan-transpose.json"
    _write_json(orphan, corpus)
    with pytest.raises(runner.ScanError, match="256 transpose groups"):
        runner._corpus(orphan, PROJECT_ROOT, 0)


def test_resource_contract_and_no_go_constants_are_exact(runner: ModuleType) -> None:
    assert runner.FORMAL_PROOF_LIMIT_BYTES == 5_000_000_000
    assert runner.FORMAL_MIN_FREE_BYTES == 10_737_418_240
    assert runner.FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES == 15_737_418_240
    assert runner.EXPECTED_MEMORY_HIGH == 35 * 1024**3
    assert runner.EXPECTED_MEMORY_MAX == 39 * 1024**3
    assert runner.EXPECTED_SWAP_MAX == 16 * 1024**3
    assert runner.EXPECTED_OOM_POLICY == "continue"
    assert runner.EXPECTED_KILL_MODE == "control-group"
    assert runner.EXPECTED_SEND_SIGKILL == "yes"
    assert runner.FORMAL_SOLVER_TIME_LIMIT_SECONDS == 3_600
    assert runner.FORMAL_SOLVER_WALL_TIMEOUT_SECONDS == 3_900
    assert runner.FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS == 3_600


def test_batch_identity_pins_512_pairs_1024_arms_and_forbids_formal_tools(
    batch_orchestrator: ModuleType,
    paired_fixture: dict[str, Any],
    tmp_path: Path,
) -> None:
    scripts = batch_orchestrator._script_paths()
    python = Path(sys.executable).resolve(strict=True)
    identity = batch_orchestrator._identity_payload(
        PROJECT_ROOT,
        tmp_path / "locked-batch",
        paired_fixture["paths"]["corpus"],
        paired_fixture["paths"]["geometry_admission"],
        STENCIL,
        scripts,
        python,
        250_000,
    )
    assert identity["status"] == "LOCKED_BEFORE_RESULTS"
    assert identity["contract"] == {
        "case_count": 512,
        "arm_count": 1_024,
        "canonical_order": "case_index_0_through_511",
        "model_scope": "diagnostic_fixed_pattern",
        "constructor_node_limit": 250_000,
        "child_wall_timeout_seconds": 300,
        "artifact_low_water_bytes": 10 * 1024**3,
        "formal_tools_authorized": False,
        "proof_fallback_authorized": False,
        "no_overwrite": True,
    }
    assert set(scripts) == set(batch_orchestrator.SCRIPT_NAMES)
    for script in scripts.values():
        child_argv = batch_orchestrator._command(python, script, "--synthetic-contract-probe")
        lowered = " ".join(child_argv).lower()
        assert "roundingsat" not in lowered
        assert "veripb" not in lowered


def test_batch_output_resume_is_exact_no_overwrite_and_rejects_symlink_alias(
    batch_orchestrator: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scan_root = tmp_path / "scan"
    scan_root.mkdir()
    monkeypatch.setattr(batch_orchestrator, "AUTHORITY_SCAN_ROOT", scan_root)
    output = scan_root / "batch-a"
    identity = {
        "schema_version": batch_orchestrator.IDENTITY_SCHEMA,
        "status": "LOCKED_BEFORE_RESULTS",
        "output_directory": str(output),
    }
    created = batch_orchestrator._prepare_output(SimpleNamespace(output_dir=output, resume=False), identity)
    assert created == output
    assert _read_json(output / "batch-identity.json") == identity
    with pytest.raises(batch_orchestrator.OrchestrationError, match="already exists"):
        batch_orchestrator._prepare_output(SimpleNamespace(output_dir=output, resume=False), identity)
    assert batch_orchestrator._prepare_output(SimpleNamespace(output_dir=output, resume=True), identity) == output

    with pytest.raises(batch_orchestrator.OrchestrationError, match="identity or source bytes drifted"):
        batch_orchestrator._prepare_output(
            SimpleNamespace(output_dir=output, resume=True),
            {**identity, "status": "DRIFTED"},
        )
    alias = scan_root / "batch-alias"
    alias.symlink_to(output, target_is_directory=True)
    with pytest.raises(batch_orchestrator.OrchestrationError, match="must not be a symlink"):
        batch_orchestrator._prepare_output(SimpleNamespace(output_dir=alias, resume=True), identity)


def test_batch_provenance_rejects_symlink_sources(
    batch_orchestrator: ModuleType,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    source.write_text('{"fixed":true}\n', encoding="utf-8")
    alias = tmp_path / "source-link.json"
    alias.symlink_to(source)
    with pytest.raises(batch_orchestrator.OrchestrationError, match="symlink forbidden as provenance input"):
        batch_orchestrator._record(alias, PROJECT_ROOT)


def test_batch_low_water_boundary_is_inclusive_and_one_byte_low_is_incomplete(
    batch_orchestrator: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    threshold = batch_orchestrator.ARTIFACT_LOW_WATER_BYTES
    monkeypatch.setattr(batch_orchestrator, "_free_bytes", lambda _path: threshold)
    assert batch_orchestrator._ensure_space(tmp_path, 17, "exact") == threshold
    monkeypatch.setattr(batch_orchestrator, "_free_bytes", lambda _path: threshold - 1)
    with pytest.raises(batch_orchestrator.IncompleteRun, match="artifact_low_water:one_byte_low") as caught:
        batch_orchestrator._ensure_space(tmp_path, 17, "one_byte_low")
    assert caught.value.case_index == 17


def test_batch_checkpoint_gap_rejected_and_constructor_unknown_maps_to_incomplete(
    batch_orchestrator: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    checkpoint_root = tmp_path / "checkpoint-gap"
    (checkpoint_root / "checkpoints").mkdir(parents=True)
    _write_json(checkpoint_root / "checkpoints/case-001.json", {"synthetic": True})
    cases = [
        {"case_index": index, "case_id": f"case_{index:03d}", "pair_id": f"pair_{index:03d}"} for index in range(2)
    ]
    monkeypatch.setattr(batch_orchestrator, "_validate_checkpoint", lambda *_args: {"synthetic": True})
    with pytest.raises(batch_orchestrator.OrchestrationError, match="canonical-order gap"):
        batch_orchestrator._existing_entries(checkpoint_root, cases, PROJECT_ROOT)

    authority = tmp_path / "authority"
    corpus = authority / "diagnostic-corpus/ceiling-diagnostic-corpus-v2.json"
    geometry = authority / "geometry/geometry-admission.json"
    stencil = tmp_path / "stencil.json"
    for path in (corpus, geometry, stencil):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "batch"
    (output / "status-events").mkdir(parents=True)
    synthetic_cases = [
        {
            "case_index": index,
            "case_id": f"case_{index:03d}",
            "pair_id": f"pair_{index:03d}",
            "transpose_group_id": f"transpose_{index // 2:03d}",
        }
        for index in range(512)
    ]
    monkeypatch.setattr(batch_orchestrator, "AUTHORITY_RUN_ROOT", authority)
    monkeypatch.setattr(batch_orchestrator, "_validate_python", lambda: Path(sys.executable).resolve())
    monkeypatch.setattr(batch_orchestrator, "_script_paths", lambda: {})
    monkeypatch.setattr(batch_orchestrator, "_validate_corpus", lambda _path: ({}, synthetic_cases))
    monkeypatch.setattr(
        batch_orchestrator,
        "_sha256",
        lambda path: (
            batch_orchestrator.LOCKED_GEOMETRY_ADMISSION_SHA256
            if Path(path) == geometry
            else batch_orchestrator.LOCKED_STENCIL_SHA256
        ),
    )
    monkeypatch.setattr(batch_orchestrator, "_identity_payload", lambda *_args: {"locked": True})
    monkeypatch.setattr(batch_orchestrator, "_prepare_output", lambda *_args: output)
    monkeypatch.setattr(batch_orchestrator, "_existing_entries", lambda *_args: [])
    monkeypatch.setattr(
        batch_orchestrator,
        "_run_case",
        lambda **_kwargs: (_ for _ in ()).throw(batch_orchestrator.IncompleteRun("constructor_unknown:treatment", 0)),
    )
    monkeypatch.setattr(batch_orchestrator.signal, "signal", lambda *_args: None)
    exit_code = batch_orchestrator.main(
        [
            "--project-root",
            str(PROJECT_ROOT),
            "--corpus",
            str(corpus),
            "--geometry-admission",
            str(geometry),
            "--stencil",
            str(stencil),
            "--output-dir",
            str(output),
        ]
    )
    assert exit_code == 3
    events = list((output / "status-events").glob("status-*.json"))
    assert len(events) == 1
    event = _read_json(events[0])
    assert event["status"] == "INCOMPLETE"
    assert event["reason"] == "constructor_unknown:treatment"
    assert event["completed_pairs"] == 0
    assert event["global_update_authorized"] is False


def test_batch_source_manifest_persists_canary_and_translation_admission(
    batch_orchestrator: ModuleType,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "encoder-canaries.json").write_text('{"status":"PASS"}\n', encoding="utf-8")
    (source / "translation-admission.json").write_text('{"status":"PASS"}\n', encoding="utf-8")
    manifest = batch_orchestrator._tree_manifest(source, batch_orchestrator.SOURCE_MANIFEST_NAME)
    batch_orchestrator._verify_tree_manifest(manifest, batch_orchestrator.SOURCE_MANIFEST_NAME)
    entries = manifest.read_text(encoding="ascii")
    assert "encoder-canaries.json" in entries
    assert "translation-admission.json" in entries
    implementation = (RESEARCH / "run_b1_conditional_halo_diagnostic_corpus_v1.py").read_text(encoding="utf-8")
    assert 'canaries = source / "encoder-canaries.json"' in implementation
    assert 'admission = source / "translation-admission.json"' in implementation


def _write_process_group_fixture(directory: Path, *, parent_waits: bool) -> tuple[Path, Path, Path]:
    sentinel = directory / "grandchild-sigterm.sentinel"
    ready = directory / "grandchild.ready"
    grandchild = directory / "grandchild.py"
    grandchild.write_text(
        dedent(
            """\
            import signal
            import sys
            import time
            from pathlib import Path

            sentinel = Path(sys.argv[1])
            ready = Path(sys.argv[2])

            def handle_sigterm(_signum, _frame):
                sentinel.write_text("grandchild received group SIGTERM\\n", encoding="utf-8")
                raise SystemExit(0)

            signal.signal(signal.SIGTERM, handle_sigterm)
            ready.write_text("ready\\n", encoding="utf-8")
            while True:
                time.sleep(1)
            """
        ),
        encoding="utf-8",
    )
    parent = directory / "parent.py"
    tail = (
        dedent(
            """\
            def handle_sigterm(_signum, _frame):
                child.wait(timeout=5)
                raise SystemExit(0)

            signal.signal(signal.SIGTERM, handle_sigterm)
            print(child.pid, flush=True)
            while True:
                time.sleep(1)
            """
        )
        if parent_waits
        else "print(child.pid, flush=True)\n"
    )
    parent.write_text(
        dedent(
            f"""\
            import signal
            import subprocess
            import sys
            import time
            from pathlib import Path

            ready = Path({str(ready)!r})
            child = subprocess.Popen(
                [sys.executable, {str(grandchild)!r}, {str(sentinel)!r}, str(ready)]
            )
            deadline = time.monotonic() + 5
            while not ready.exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError("grandchild did not become ready")
                time.sleep(0.01)
            """
        )
        + tail,
        encoding="utf-8",
    )
    return parent, sentinel, ready


def _assert_proc_absent(pid: int) -> None:
    deadline = time.monotonic() + 3
    while Path(f"/proc/{pid}").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not Path(f"/proc/{pid}").exists()


def test_batch_invoke_cleans_descendant_group_after_normal_parent_exit(
    batch_orchestrator: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    parent, sentinel, _ = _write_process_group_fixture(tmp_path, parent_waits=False)
    monkeypatch.setattr(batch_orchestrator, "_ensure_space", lambda *_args: 10 * 1024**3)
    logs = tmp_path / "logs-normal"
    completed = batch_orchestrator._invoke(
        label="normal_parent_with_descendant",
        argv=[sys.executable, str(parent)],
        log_dir=logs,
        root=PROJECT_ROOT,
        low_water_path=tmp_path,
        case_index=0,
        wall_timeout_seconds=5,
    )
    grandchild_pid = int(completed.stdout.strip())
    record = _read_json(logs / "normal_parent_with_descendant.json")
    assert completed.returncode == 0
    assert sentinel.read_text(encoding="utf-8") == "grandchild received group SIGTERM\n"
    assert record["termination_reason"] == "descendant_cleanup_after_parent_exit"
    assert record["descendant_cleanup_performed"] is True
    assert record["process_group_clean"] is True
    assert record["wall_timeout_seconds"] == 5
    _assert_proc_absent(grandchild_pid)


def test_batch_invoke_timeout_signals_entire_owned_group_and_records_cleanup(
    batch_orchestrator: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    parent, sentinel, _ = _write_process_group_fixture(tmp_path, parent_waits=True)
    parent_source = parent.read_text(encoding="utf-8")
    assert "child.terminate" not in parent_source and "child.kill" not in parent_source
    monkeypatch.setattr(batch_orchestrator, "_ensure_space", lambda *_args: 10 * 1024**3)
    logs = tmp_path / "logs-timeout"
    with pytest.raises(batch_orchestrator.OrchestrationError, match="wall timeout"):
        batch_orchestrator._invoke(
            label="timed_parent_with_descendant",
            argv=[sys.executable, str(parent)],
            log_dir=logs,
            root=PROJECT_ROOT,
            low_water_path=tmp_path,
            case_index=0,
            wall_timeout_seconds=0.25,
        )
    stdout = (logs / "timed_parent_with_descendant.stdout").read_text(encoding="utf-8")
    grandchild_pid = int(stdout.strip())
    record = _read_json(logs / "timed_parent_with_descendant.json")
    assert sentinel.read_text(encoding="utf-8") == "grandchild received group SIGTERM\n"
    assert record["termination_reason"] == "wall_timeout"
    assert record["interrupted"] is True
    assert record["descendant_cleanup_performed"] is True
    assert record["process_group_clean"] is True
    assert record["wall_timeout_seconds"] == 0.25
    _assert_proc_absent(grandchild_pid)
