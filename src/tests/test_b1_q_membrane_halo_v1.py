from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = PROJECT_ROOT / "docs/research/b1_q_membrane_halo_20260722"


def _load_module(name: str, filename: str) -> ModuleType:
    path = HARNESS_ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def coordinate() -> ModuleType:
    return _load_module(
        "b1_qmh_coordinate_test",
        "verify_b1_q_membrane_halo_v1.py",
    )


@pytest.fixture(scope="module")
def independent() -> ModuleType:
    return _load_module(
        "b1_qmh_independent_test",
        "recompute_b1_q_membrane_halo_independent_v1.py",
    )


@pytest.fixture(scope="module")
def agreement() -> ModuleType:
    return _load_module(
        "b1_qmh_agreement_test",
        "compare_b1_q_membrane_halo_recomputations_v1.py",
    )


@pytest.fixture(scope="module")
def encoder() -> ModuleType:
    return _load_module(
        "b1_qmh_band_encoder_test",
        "b1_q_membrane_halo_band_encoder_v1.py",
    )


@pytest.fixture(scope="module")
def translation_gate() -> ModuleType:
    return _load_module(
        "b1_qmh_band_translation_gate_test",
        "verify_b1_q_membrane_halo_band_translation_v1.py",
    )


@pytest.fixture(scope="module")
def coordinate_report(coordinate: ModuleType) -> dict[str, object]:
    report = coordinate.recompute()
    assert isinstance(report, dict)
    return report


@pytest.fixture(scope="module")
def independent_report(independent: ModuleType) -> dict[str, object]:
    instance = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    report = independent.build_report(instance)
    assert isinstance(report, dict)
    return report


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _band_paths(directory: Path) -> dict[str, Path]:
    return {
        "estimate": directory / "estimate.json",
        "opb": directory / "band.opb",
        "meta": directory / "band.meta.json",
        "var_map": directory / "band.var-map.json",
        "gate": directory / "translation-gate.json",
    }


def _generate_band(
    encoder: ModuleType,
    translation_gate: ModuleType,
    directory: Path,
) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=False)
    paths = _band_paths(directory)
    estimate_args = [
        "estimate",
        "--project-root",
        str(PROJECT_ROOT),
        "--output",
        str(paths["estimate"]),
    ]
    assert encoder.main(estimate_args) == 0
    estimate_sha = hashlib.sha256(paths["estimate"].read_bytes()).hexdigest()
    encode_args = [
        "encode",
        "--project-root",
        str(PROJECT_ROOT),
        "--estimate",
        str(paths["estimate"]),
        "--estimate-sha256",
        estimate_sha,
        "--opb-out",
        str(paths["opb"]),
        "--meta-out",
        str(paths["meta"]),
        "--var-map-out",
        str(paths["var_map"]),
    ]
    assert encoder.main(encode_args) == 0
    gate_args = [
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
    assert translation_gate.main(gate_args) == 0
    return paths


@pytest.fixture(scope="module")
def complete_band_translation(
    encoder: ModuleType,
    translation_gate: ModuleType,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Path]:
    return _generate_band(
        encoder,
        translation_gate,
        tmp_path_factory.mktemp("b1_qmh_band") / "run",
    )


def test_two_algorithms_recompute_the_same_complete_corpus(
    coordinate_report: dict[str, object],
    independent_report: dict[str, object],
) -> None:
    coordinate_metrics = coordinate_report["metrics"]
    independent_metrics = independent_report["metrics"]
    assert coordinate_metrics == {
        "pattern_placement_corpus": 203_340_800,
        "baseline_surviving_placements": 165_541_238,
        "refined_surviving_placements": 165_541_100,
        "incremental_pruned_placements": 138,
        "surviving_oriented_dimensions": 2_127,
        "old_oriented_dimensions": 2_151,
        "side_70_dimensions_removed": 24,
    }
    assert independent_metrics == {
        "total_pattern_placements": 203_340_800,
        "baseline_survivors": 165_541_238,
        "refined_survivors": 165_541_100,
        "incremental_pruned": 138,
        "refined_surviving_oriented_dimensions": 2_127,
        "baseline_surviving_oriented_dimensions": 2_151,
        "baseline_side_70_dimensions_removed": 24,
    }
    assert coordinate_report["frontier"] == {
        "objective": [1190, 34],
        "oriented_dimensions": [[34, 35], [35, 34]],
    }
    assert independent_report["frontier"]["old_upper"] == [1190, 34]
    assert independent_report["frontier"]["new_upper"] == [1190, 34]


def test_raw_providers_are_exactly_saturated_and_reports_bind_scripts(
    coordinate_report: dict[str, object],
    independent_report: dict[str, object],
) -> None:
    expected = {
        "required_outputs": 52,
        "boundary_capacity": 46,
        "protocol_core_capacity": 6,
        "identity": "52 = 46 * 1 + 6",
    }
    assert coordinate_report["ledger"]["raw_provider_saturation"] == expected
    assert independent_report["strict_ledger"]["raw_provider_saturation"] == expected
    coordinate_path = HARNESS_ROOT / "verify_b1_q_membrane_halo_v1.py"
    independent_path = HARNESS_ROOT / "recompute_b1_q_membrane_halo_independent_v1.py"
    assert coordinate_report["provenance"]["script_sha256"] == hashlib.sha256(coordinate_path.read_bytes()).hexdigest()
    assert (
        independent_report["provenance"]["script_sha256"] == hashlib.sha256(independent_path.read_bytes()).hexdigest()
    )


def test_q_e_coordinate_examples_and_rounding(coordinate: ModuleType) -> None:
    pattern = coordinate._patterns()[0]
    left = coordinate._contact_profile(pattern.left_anchors, 1, 35)
    bottom = coordinate._contact_profile(pattern.bottom_anchors, 1, 34)
    assert (left[0] + bottom[0], left[1] + bottom[1]) == (23, 1)
    assert coordinate._refined_ok(34, 35, 23, 1) is False
    assert coordinate._refined_ok(34, 35, 0, 0) is True
    for q_count in range(47):
        for endpoint_count in range(min(8, q_count) + 1):
            assert (87 - q_count - 2 * endpoint_count) // 2 == (43 - q_count // 2 - endpoint_count)


def test_encoder_and_gate_independently_rebuild_the_ceiling_band(
    encoder: ModuleType,
    translation_gate: ModuleType,
) -> None:
    model = encoder._derive_model()
    independent_band = translation_gate._derive_band()
    assert model.counts == {
        "boundary_patterns": 47,
        "rectangle_placements": 2520,
        "pattern_placement_corpus": 118_440,
        "surviving_pairs": 118_346,
        "violating_pairs": 94,
        "pattern_selector_variables": 47,
        "placement_selector_variables": 2520,
        "variables": 2567,
        "equality_constraints": 2,
        "pair_exclusion_constraints": 94,
        "constraints": 96,
    }
    assert independent_band["pattern_count"] == 47
    assert independent_band["placement_count"] == 2520
    assert independent_band["pair_corpus"] == 118_440
    assert independent_band["allowed_pairs"] == 118_346
    assert len(independent_band["forbidden"]) == 94
    assert independent_band["orientation_survivors"] == {
        "34x35": 59_173,
        "35x34": 59_173,
    }


def test_build_only_opb_and_translation_gate_close_exactly(
    encoder: ModuleType,
    complete_band_translation: dict[str, Path],
) -> None:
    paths = complete_band_translation
    estimate = _read_json(paths["estimate"])
    metadata = _read_json(paths["meta"])
    variable_map = _read_json(paths["var_map"])
    report = _read_json(paths["gate"])
    header = paths["opb"].read_text(encoding="ascii").splitlines()[0]
    assert header == "* #variable= 2567 #constraint= 96 #equal= 2 intsize= 64"
    assert estimate["projected_outputs"] == {"opb_bytes": paths["opb"].stat().st_size}
    source_sha = hashlib.sha256((HARNESS_ROOT / "b1_q_membrane_halo_band_encoder_v1.py").read_bytes()).hexdigest()
    assert estimate["encoder_script_sha256"] == source_sha
    assert metadata["encoder_script_sha256"] == source_sha
    assert variable_map["variable_count"] == 2567
    assert len(variable_map["variables"]) == 2567
    assert metadata["proof_status"] == "build_only_no_solver_or_proof"
    assert estimate["resource_contract"] == encoder.RESOURCE_CONTRACT
    assert metadata["resource_contract"] == encoder.RESOURCE_CONTRACT
    assert estimate["resource_contract"]["formal_run_authorized"] is False
    assert metadata["resource_contract"]["formal_run_authorized"] is False
    assert "formal_run_authorized" not in variable_map

    assert report["status"] == "PASS"
    assert report["corpus_errors"] == []
    assert len(report["checks"]) == 18
    assert all(value is True for value in report["checks"].values())
    assert report["constraint_diff"] == {
        "missing_examples": [],
        "missing_total": 0,
        "unexpected_examples": [],
        "unexpected_total": 0,
    }
    assert report["proof_status"] == ("translation_gate_only_no_solver_or_proof_run_no_unsat_claim")
    gate_path = HARNESS_ROOT / "verify_b1_q_membrane_halo_band_translation_v1.py"
    gate_sha = hashlib.sha256(gate_path.read_bytes()).hexdigest()
    provenance = report["gate_provenance"]
    assert provenance["source"] == {
        "path": ("docs/research/b1_q_membrane_halo_20260722/verify_b1_q_membrane_halo_band_translation_v1.py"),
        "sha256": gate_sha,
        "size_bytes": gate_path.stat().st_size,
    }
    assert provenance["encoder_source_current"]["sha256"] == source_sha
    assert provenance["project_root"] == str(PROJECT_ROOT)
    assert provenance["argv"][0].endswith("verify_b1_q_membrane_halo_band_translation_v1.py")
    assert all(item["pass"] is True for item in report["semantic_canaries"].values())


def test_resource_contract_and_claim_scope_are_dormant_build_only(
    encoder: ModuleType,
) -> None:
    gib = 1024**3
    assert encoder.RESOURCE_CONTRACT == {
        "memory_high": "35GiB",
        "memory_high_bytes": 35 * gib,
        "memory_max": "39GiB",
        "memory_max_bytes": 39 * gib,
        "memory_swap_max": "16GiB",
        "memory_swap_max_bytes": 16 * gib,
        "oom_policy": "continue",
        "worker_limit": 1,
        "proof_size_cap_bytes": 5_000_000_000,
        "disk_low_water": "10GiB",
        "disk_low_water_bytes": 10 * gib,
        "formal_run_authorized": False,
    }
    claim = encoder._claim_scope()
    rendered = json.dumps(claim, sort_keys=True)
    assert "does not establish a new upper bound" in rendered
    assert "does not provide a witness" in rendered
    assert "not production CERTIFIED evidence" in rendered


def test_translation_parser_rejects_nonlinear_duplicate_and_truncated_lines(
    translation_gate: ModuleType,
) -> None:
    with pytest.raises(translation_gate.GateError):
        translation_gate._parse_constraint("+1 x1 * x2 >= 0 ;", 1)
    with pytest.raises(translation_gate.GateError, match="duplicate"):
        translation_gate._parse_constraint("+1 x1 +1 x1 >= 0 ;", 1)
    with pytest.raises(translation_gate.GateError):
        translation_gate._parse_constraint("-1 x1 -1 x48 >= -1", 1)


def test_translation_gate_rejects_tampered_opb_and_closes_claim(
    encoder: ModuleType,
    translation_gate: ModuleType,
    tmp_path: Path,
) -> None:
    paths = _generate_band(encoder, translation_gate, tmp_path / "tampered")
    lines = paths["opb"].read_text(encoding="ascii").splitlines()
    paths["opb"].write_text("\n".join(lines[:-1]) + "\n", encoding="ascii")
    failure_output = tmp_path / "tampered-gate.json"
    result = translation_gate.main(
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
            "--output",
            str(failure_output),
        ]
    )
    assert result == 1
    failure = _read_json(failure_output)
    assert failure["status"] == "FAIL"
    assert failure["corpus_errors"]
    assert "proof" in failure["proof_status"]


def test_translation_gate_rejects_current_encoder_byte_drift(
    translation_gate: ModuleType,
    complete_band_translation: dict[str, Path],
    tmp_path: Path,
) -> None:
    strict_relative = Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json")
    encoder_relative = Path("docs/research/b1_q_membrane_halo_20260722/b1_q_membrane_halo_band_encoder_v1.py")
    strict_target = tmp_path / strict_relative
    encoder_target = tmp_path / encoder_relative
    strict_target.parent.mkdir(parents=True)
    encoder_target.parent.mkdir(parents=True)
    strict_target.write_bytes((PROJECT_ROOT / strict_relative).read_bytes())
    encoder_target.write_bytes((PROJECT_ROOT / encoder_relative).read_bytes() + b"\n# drift canary\n")
    paths = complete_band_translation
    with pytest.raises(
        translation_gate.GateError,
        match="encoder harness-source provenance",
    ):
        translation_gate.verify(
            project_root=tmp_path,
            opb_path=paths["opb"],
            meta_path=paths["meta"],
            var_map_path=paths["var_map"],
            estimate_path=paths["estimate"],
            argv_record=["drift-canary"],
        )


def test_band_artifact_writers_refuse_overwrite(
    encoder: ModuleType,
    translation_gate: ModuleType,
    complete_band_translation: dict[str, Path],
) -> None:
    paths = complete_band_translation
    with pytest.raises(FileExistsError):
        encoder.main(
            [
                "estimate",
                "--project-root",
                str(PROJECT_ROOT),
                "--output",
                str(paths["estimate"]),
            ]
        )
    with pytest.raises(FileExistsError):
        translation_gate.main(
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
                "--output",
                str(paths["gate"]),
            ]
        )


def test_agreement_gate_accepts_current_reports_and_rejects_stale_sha(
    agreement: ModuleType,
    coordinate_report: dict[str, object],
    independent_report: dict[str, object],
    tmp_path: Path,
) -> None:
    coordinate_path = tmp_path / "coordinate.json"
    independent_path = tmp_path / "independent.json"
    _write_json(coordinate_path, coordinate_report)
    _write_json(independent_path, independent_report)
    report = agreement.compare(coordinate_path, independent_path)
    assert report["status"] == "PASS"
    assert report["corpus_errors"] == []
    assert report["frontier"]["old"] == report["frontier"]["new"] == [1190, 34]

    stale = json.loads(json.dumps(coordinate_report))
    stale["provenance"]["script_sha256"] = "0" * 64
    _write_json(tmp_path / "stale.json", stale)
    with pytest.raises(agreement.AgreementError, match="provenance"):
        agreement.compare(tmp_path / "stale.json", independent_path)


def test_strict_json_parsers_reject_duplicate_keys(
    coordinate: ModuleType,
    independent: ModuleType,
    agreement: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"status":"PASS","status":"PASS"}\n', encoding="utf-8")
    digest = hashlib.sha256(duplicate.read_bytes()).hexdigest()
    monkeypatch.setattr(coordinate, "EXPECTED_STRICT_SHA256", digest)
    monkeypatch.setattr(independent, "EXPECTED_STRICT_SHA256", digest)
    with pytest.raises(coordinate.RecomputeError, match="duplicate JSON key"):
        coordinate._load_strict(duplicate)
    with pytest.raises(independent.RecomputeError, match="duplicate JSON key"):
        independent.load_strict_instance(duplicate)
    with pytest.raises(agreement.AgreementError, match="duplicate JSON key"):
        agreement._load(duplicate)


def test_all_report_writers_refuse_overwrite(
    coordinate: ModuleType,
    independent: ModuleType,
    agreement: ModuleType,
    coordinate_report: dict[str, object],
    independent_report: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinate_output = tmp_path / "coordinate.json"
    monkeypatch.setattr(coordinate, "recompute", lambda: coordinate_report)
    assert coordinate.main(["--output", str(coordinate_output)]) == 0
    with pytest.raises(FileExistsError):
        coordinate.main(["--output", str(coordinate_output)])

    independent_output = tmp_path / "independent.json"
    monkeypatch.setattr(
        independent,
        "build_report",
        lambda _path: independent_report,
    )
    assert independent.main(["--output", str(independent_output)]) == 0
    assert independent.main(["--output", str(independent_output)]) == 1

    agreement_output = tmp_path / "agreement.json"
    coordinate_input = tmp_path / "coordinate-input.json"
    independent_input = tmp_path / "independent-input.json"
    _write_json(coordinate_input, coordinate_report)
    _write_json(independent_input, independent_report)
    args = [
        "--coordinate",
        str(coordinate_input),
        "--independent",
        str(independent_input),
        "--output",
        str(agreement_output),
    ]
    assert agreement.main(args) == 0
    with pytest.raises(FileExistsError):
        agreement.main(args)


def test_independent_tools_do_not_import_each_other_or_an_encoder() -> None:
    forbidden = {
        "verify_b1_q_membrane_halo_v1",
        "recompute_b1_q_membrane_halo_independent_v1",
        "b1_q_membrane_halo_band_encoder_v1",
        "verify_r3_certificates",
    }
    for filename in (
        "verify_b1_q_membrane_halo_v1.py",
        "recompute_b1_q_membrane_halo_independent_v1.py",
        "compare_b1_q_membrane_halo_recomputations_v1.py",
    ):
        tree = ast.parse((HARNESS_ROOT / filename).read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        assert not any(any(name in item for name in forbidden) for item in imports)

    gate_source = (HARNESS_ROOT / "verify_b1_q_membrane_halo_band_translation_v1.py").read_text(encoding="utf-8")
    for forbidden_text in (
        "verify_b1_q_membrane_halo_v1",
        "recompute_b1_q_membrane_halo_independent_v1",
        "compare_b1_q_membrane_halo_recomputations_v1",
        "verify_r3_certificates",
        "r3_upper_bound_pb_encoder",
        "importlib",
        "runpy",
        "subprocess",
    ):
        assert forbidden_text not in gate_source


def test_paper_states_the_exact_claim_boundary() -> None:
    paper = (HARNESS_ROOT / "01_necessity_proof.md").read_text(encoding="utf-8")
    verdict = (HARNESS_ROOT / "02_adversarial_verdict.md").read_text(encoding="utf-8")
    assert "46 boundary ports * 1 + 6 protocol-core outputs = 52" in paper
    assert "floor(q/2)+e)/4)<=1320" in paper.replace(" ", "")
    assert "double-counts" in paper
    assert "11/11 CONFIRMED" in verdict
    assert "no new UNSAT claim" in verdict


def test_delivery_docs_are_terminal_and_bind_the_core_plan_next_direction() -> None:
    readme = (HARNESS_ROOT / "README.md").read_text(encoding="utf-8")
    verdict = (HARNESS_ROOT / "02_adversarial_verdict.md").read_text(encoding="utf-8")
    authoritative_run = ".artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW/"

    assert "| Document nature | Current-state research round report |" in readme
    assert "| Document nature | Adversarial judgment archive" in verdict
    for document in (readme, verdict):
        assert "| Evidence cutoff | `2026-07-22` |" in document
        assert f"| Authoritative run | `{authoritative_run}` |" in document
    assert "| Status | **COMPLETE**" in readme
    assert "| Status | **PASS — 11/11 CONFIRMED** |" in verdict

    lowered = readme.lower()
    for editorial_phrase in (
        "changed during review",
        "first pass",
        "both recomputers now",
        "a new exclusive run was then made",
    ):
        assert editorial_phrase not in lowered
    assert " now " not in f" {lowered} "

    compact = " ".join(readme.split())
    assert "**core-plan candidate 2: conditional halo**" in readme
    assert "Σ_q C_q(R) ≥ 3325" in readme
    assert "Survivor diagnostics and possible prerequisite lemmas" in readme
    assert "3×3` storage box costs nine cells" in compact
    assert "they are not a separate next-round candidate" in readme
    assert "preferred next candidate" not in lowered
    assert "positive-area protocol box" not in lowered

    assert (
        "Only `band-estimate-v2.json` and `band-v2.meta.json` carry `resource_contract.formal_run_authorized=false`."
    ) in compact
    assert "`proof_status=translation_gate_only_no_solver_or_proof_run_no_unsat_claim`" in readme
