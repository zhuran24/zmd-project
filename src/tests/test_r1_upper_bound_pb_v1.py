from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = (
    PROJECT_ROOT
    / "docs"
    / "research"
    / "front_offset_incident_20260718"
    / "batch4_harness"
)
PROOF_LIMIT_BYTES = 5_000_000_000
MIN_FREE_BYTES = 10_737_418_240
EXPECTED_HEADER = "* #variable= 16749 #constraint= 16704 #equal= 2 intsize= 64"


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
        "r1_upper_bound_pb_encoder_v1_test",
        HARNESS_ROOT / "r1_upper_bound_pb_encoder_v1.py",
    )


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    return _load_module(
        "r1_upper_bound_pb_translation_v1_test",
        HARNESS_ROOT / "verify_r1_upper_bound_pb_translation_v1.py",
    )


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load_module(
        "r1_upper_bound_pb_toolchain_v1_test",
        HARNESS_ROOT / "run_r1_upper_bound_pb_toolchain_v1.py",
    )


def _json(path: Path) -> dict[str, object]:
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


def _encoder_paths(directory: Path) -> dict[str, Path]:
    return {
        "estimate": directory / "estimate.json",
        "opb": directory / "r1_upper_bound.opb",
        "meta": directory / "r1_upper_bound.meta.json",
        "var_map": directory / "r1_upper_bound.var_map.json",
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


def _generate_translation(
    encoder: ModuleType,
    directory: Path,
) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = _encoder_paths(directory)
    assert encoder.main(_estimate_args(paths)) == 0
    assert encoder.main(_encode_args(paths)) == 0
    return paths


@pytest.fixture(scope="module")
def complete_translation(
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Path]:
    paths = _generate_translation(encoder, tmp_path_factory.mktemp("r1_pb_translation"))
    assert gate.main(_gate_args(paths)) == 0
    return paths


def test_real_encoder_and_independent_gate_cover_the_exact_residual_band(
    gate: ModuleType,
    complete_translation: dict[str, Path],
) -> None:
    paths = complete_translation
    estimate = _json(paths["estimate"])
    metadata = _json(paths["meta"])
    variable_map = _json(paths["var_map"])
    report = _json(paths["gate"])

    assert estimate["proof_size_planning"] == {
        "basis": {
            "method": "conservative_round_up_to_512_mib_planning_envelope",
            "scratch_observed_proof_bytes": 25_496_266,
        },
        "bound_bytes": 536_870_912,
        "decision": "GO",
        "user_limit_bytes": PROOF_LIMIT_BYTES,
    }
    assert estimate["projected_outputs"] == {"opb_bytes": paths["opb"].stat().st_size}
    assert paths["opb"].read_text(encoding="ascii").splitlines()[0] == EXPECTED_HEADER

    assert metadata["counts"] == {
        "boundary_patterns": 47,
        "constraints": 16_704,
        "equality_constraints": 2,
        "nonzero_overlap_terms": 62_792,
        "oriented_dimensions": 22,
        "pattern_placement_pairs": 784_994,
        "pattern_variables": 47,
        "placement_feasibility_constraints": 16_702,
        "rectangle_placements": 16_702,
        "rectangle_variables": 16_702,
        "variables": 16_749,
    }
    assert variable_map["variable_count"] == 16_749
    assert len(variable_map["variables"]) == 16_749

    scope = metadata["claim_scope"]
    assert scope["out_of_band"] == {
        "basis": "free-cell cap lemma: 4900 - 3544 - 4 * 2 = 1348",
        "coverage": "lex-better rectangle dimensions with area greater than 1348",
        "inside_opb": False,
    }
    assert scope["residual_band"]["inside_opb"] is True
    assert "all 22 oriented lex-better dimensions" in scope["residual_band"]["coverage"]
    assert "together cover the complete strict (1326,34) upper-bound lemma" in scope["combined_statement"]
    assert metadata["proof_status"] == "translation_only_no_unsat_or_proof_claim"

    assert report["status"] == "PASS"
    assert set(report["checks"]) == gate.REQUIRED_CHECKS
    assert all(value is True for value in report["checks"].values())
    assert report["corpus_count"] == 784_994
    assert report["corpus_errors"] == []
    assert report["constraint_diff"] == {
        "missing_examples": [],
        "missing_total": 0,
        "unexpected_examples": [],
        "unexpected_total": 0,
    }
    assert report["counts"] == metadata["counts"]
    assert report["minimum_union_lower_bound"] == 1_351
    assert report["theorem_coverage"] == scope
    assert report["proof_status"] == "translation_gate_only_no_unsat_or_proof_claim"


def test_gate_rejects_resealed_constraint_tamper(
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path: Path,
) -> None:
    paths = _generate_translation(encoder, tmp_path / "tampered")
    lines = paths["opb"].read_text(encoding="ascii").splitlines()
    assert lines[2].startswith("+1 x1 ")
    lines[2] = lines[2].replace("+1 x1 ", "+2 x1 ", 1)
    paths["opb"].write_text("\n".join(lines) + "\n", encoding="ascii")

    metadata = _json(paths["meta"])
    metadata["outputs"]["opb"]["sha256"] = _sha256(paths["opb"])
    metadata["outputs"]["opb"]["size_bytes"] = paths["opb"].stat().st_size
    _write_json(paths["meta"], metadata)

    assert gate.main(_gate_args(paths)) == 1
    report = _json(paths["gate"])
    assert report["status"] == "FAIL"
    assert report["checks"]["translation_inputs_closed_and_hashed"] is True
    assert report["checks"]["constraint_multiset_exact"] is False
    assert report["constraint_diff"]["missing_total"] == 1
    assert report["constraint_diff"]["unexpected_total"] == 1
    assert report["proof_status"] == "translation_gate_only_no_unsat_or_proof_claim"


def test_translation_artifacts_are_no_overwrite(
    encoder: ModuleType,
    gate: ModuleType,
    complete_translation: dict[str, Path],
) -> None:
    paths = complete_translation
    before = {name: _sha256(path) for name, path in paths.items()}

    with pytest.raises(FileExistsError, match="exist|overwrite"):
        encoder.main(_estimate_args(paths))
    with pytest.raises(FileExistsError, match="overwrite"):
        encoder.main(_encode_args(paths))
    with pytest.raises(FileExistsError, match="overwrite"):
        gate.main(_gate_args(paths))

    assert {name: _sha256(path) for name, path in paths.items()} == before


def _write_fake_tools(directory: Path, *, solver_exit: int, complete_proof: bool) -> tuple[Path, Path]:
    roundingsat = directory / "roundingsat"
    proof_body = (
        "pseudo-Boolean proof version 2.0\\n"
        "conclusion UNSAT : 1\\n"
        "end pseudo-Boolean proof\\n"
        if complete_proof
        else "pseudo-Boolean proof version 2.0\\n"
    )
    roundingsat.write_text(
        "#!/bin/sh\n"
        "proof=\n"
        "for argument in \"$@\"; do\n"
        "  case \"$argument\" in\n"
        "    --proof-log=*) proof=${argument#--proof-log=} ;;\n"
        "  esac\n"
        "done\n"
        f"printf '{proof_body}' > \"$proof\"\n"
        "printf 's UNSATISFIABLE\\n'\n"
        f"exit {solver_exit}\n",
        encoding="utf-8",
    )
    roundingsat.chmod(0o755)

    veripb = directory / "veripb"
    veripb.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then\n"
        "  printf 'VeriPB 3.0.2\\n'\n"
        "  exit 0\n"
        "fi\n"
        "printf 's VERIFIED UNSATISFIABLE\\n'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    veripb.chmod(0o755)
    return roundingsat, veripb


def _runner_args(
    paths: dict[str, Path],
    roundingsat: Path,
    veripb: Path,
    output_dir: Path,
) -> list[str]:
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
        "--translation-gate",
        str(paths["gate"]),
        "--roundingsat",
        str(roundingsat),
        "--roundingsat-repo",
        str(PROJECT_ROOT),
        "--veripb",
        str(veripb),
        "--output-dir",
        str(output_dir),
        "--solver-time-limit",
        "1",
        "--solver-wall-timeout",
        "2",
        "--verifier-wall-timeout",
        "2",
        "--proof-limit-bytes",
        str(PROOF_LIMIT_BYTES),
        "--min-free-bytes",
        str(MIN_FREE_BYTES),
        "--monitor-interval",
        "0.01",
    ]


def test_runner_accepts_only_a_complete_fake_verified_chain_and_refuses_overwrite(
    runner: ModuleType,
    complete_translation: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "_free_bytes", lambda _path: MIN_FREE_BYTES)
    roundingsat, veripb = _write_fake_tools(tmp_path, solver_exit=0, complete_proof=True)
    output_dir = tmp_path / "success"
    args = _runner_args(complete_translation, roundingsat, veripb, output_dir)

    assert runner.main(args) == 0
    record_path = output_dir / "toolchain_record.json"
    record = _json(record_path)
    assert record["solver"]["exit_code"] == 0
    assert record["solver_declared_unsat"] is True
    assert record["proof_tail_complete"] is True
    assert record["verifier"]["exit_code"] == 0
    assert record["veripb_verified"] is True
    assert record["hash_stability"]["stable"] is True
    assert record["translation_gate"]["corpus_errors"] == []
    assert record["translation_gate"]["file"] == record["inputs"]["translation_gate"]
    assert record["tools_stable"] is True
    assert record["tools"]["stable"] is True
    assert record["claim_boundary"]["sealed_certified"] is False
    assert record["claim_boundary"]["historical_pb_judgments_restored"] == []
    assert record["claim"] == "machine_verified_residual_band_unsat_for_translation_gated_r1_upper_bound"

    record_sha256 = _sha256(record_path)
    assert runner.main(args) == 2
    assert _sha256(record_path) == record_sha256


def test_runner_rejects_nonzero_child_and_truncated_proof(
    runner: ModuleType,
    complete_translation: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "_free_bytes", lambda _path: MIN_FREE_BYTES)
    roundingsat, veripb = _write_fake_tools(tmp_path, solver_exit=4, complete_proof=False)
    output_dir = tmp_path / "failure"

    assert runner.main(_runner_args(complete_translation, roundingsat, veripb, output_dir)) == 1
    record = _json(output_dir / "toolchain_record.json")
    assert record["solver"]["exit_code"] == 4
    assert record["proof_tail_complete"] is False
    assert record["verifier"]["exit_code"] is None
    assert record["veripb_verified"] is False
    assert record["claim"] == "none"


def test_runner_rejects_preflight_below_formal_disk_minimum(
    runner: ModuleType,
    complete_translation: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "_free_bytes", lambda _path: MIN_FREE_BYTES - 1)
    roundingsat, veripb = _write_fake_tools(tmp_path, solver_exit=0, complete_proof=True)
    output_dir = tmp_path / "disk-no-go"

    assert runner.main(_runner_args(complete_translation, roundingsat, veripb, output_dir)) == 2
    assert output_dir.is_dir()
    assert list(output_dir.iterdir()) == []


def test_child_completion_sample_enforces_the_proof_cap(runner: ModuleType, tmp_path: Path) -> None:
    proof = tmp_path / "oversized.proof"
    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    resources: list[dict[str, object]] = []
    command = [
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(proof)!r}).write_bytes(b'xx')",
    ]

    result = runner._run_child(
        command,
        stdout_path=stdout,
        stderr_path=stderr,
        wall_timeout=2.0,
        monitor_interval=0.5,
        output_dir=tmp_path,
        resources=resources,
        phase="completion_cap_test",
        min_free_bytes=1,
        proof_path=proof,
        proof_limit_bytes=1,
    )

    assert result["exit_code"] == 0
    assert result["termination_reason"] in {
        "proof_size_limit_exceeded",
        "proof_size_limit_exceeded_at_completion",
    }
    assert resources[-1]["proof_size_bytes"] == 2
