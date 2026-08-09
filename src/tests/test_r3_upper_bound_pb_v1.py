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

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = PROJECT_ROOT / "docs" / "research" / "r3_upper_bound_pb_20260722"
PROOF_LIMIT_BYTES = 5_000_000_000
MIN_FREE_BYTES = 10_737_418_240
EXPECTED_HEADER = "* #variable= 2074 #constraint= 2075 #equal= 1 intsize= 64"


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
        "r3_upper_bound_pb_encoder_v1_test",
        HARNESS_ROOT / "r3_upper_bound_pb_encoder_v1.py",
    )


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    return _load_module(
        "r3_upper_bound_pb_translation_v1_test",
        HARNESS_ROOT / "verify_r3_upper_bound_pb_translation_v1.py",
    )


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load_module(
        "r3_upper_bound_pb_toolchain_v1_test",
        HARNESS_ROOT / "run_r3_upper_bound_pb_toolchain_v1.py",
    )


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _problem_payload() -> dict[str, object]:
    path = (
        PROJECT_ROOT
        / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    )
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


def _paths(directory: Path) -> dict[str, Path]:
    return {
        "estimate": directory / "estimate.json",
        "opb": directory / "r3_upper_bound.opb",
        "meta": directory / "r3_upper_bound.meta.json",
        "var_map": directory / "r3_upper_bound.var_map.json",
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
    paths = _generate(encoder, tmp_path_factory.mktemp("r3_pb_translation"))
    assert gate.main(_gate_args(paths)) == 0
    return paths


def test_independent_math_and_complete_oriented_band(
    encoder: ModuleType,
    gate: ModuleType,
) -> None:
    instance_path = (
        PROJECT_ROOT
        / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    )
    payload = json.loads(instance_path.read_text(encoding="utf-8"))
    encoder_model = encoder.derive_model(payload)
    gate_facts = gate._derive(payload)

    assert encoder_model.counts == {
        "constraints": 2075,
        "dimension_implication_constraints": 2074,
        "equality_constraints": 1,
        "oriented_dimensions": 2074,
        "satisfying_dimensions": 0,
        "selector_variables": 2074,
        "variables": 2074,
    }
    assert gate_facts["strict_sentinels"]["physical_port_specs"] == 1804
    assert gate_facts["strict_sentinels"]["total_active_terminals"] == 628
    assert gate_facts["dimensions"] == [
        (item.width, item.height) for item in encoder_model.variables
    ]
    assert gate_facts["minimum_lhs"] == 1322
    assert gate_facts["minimizers"] == [(19, 63), (63, 19)]
    assert gate_facts["area_ties"] == [(17, 70), (34, 35), (35, 34), (70, 17)]
    assert gate_facts["satisfying"] == []
    assert gate_facts["halo"]["total_weight"] == 396
    assert gate_facts["halo"]["placement_count"] == 840
    assert gate_facts["halo"]["minimum_poles"] == 9


def test_encoder_and_gate_close_the_exact_opb(
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
    expected_bound = max(512 * 1024**2, 1024 * paths["opb"].stat().st_size)
    assert estimate["proof_size_planning"]["bound_bytes"] == expected_bound
    assert estimate["proof_size_planning"]["decision"] == "GO"
    assert metadata["counts"]["variables"] == 2074
    assert metadata["counts"]["constraints"] == 2075
    assert variable_map["variable_count"] == 2074
    assert len(variable_map["variables"]) == 2074

    assert report["status"] == "PASS"
    assert set(report["checks"]) == gate.REQUIRED_CHECKS
    assert all(value is True for value in report["checks"].values())
    assert report["corpus_count"] == 2074
    assert report["corpus_errors"] == []
    assert report["minimum_lhs"] == 1322
    assert report["minimum_lhs_dimensions"] == [[19, 63], [63, 19]]
    assert report["constraint_diff"] == {
        "missing_examples": [],
        "missing_total": 0,
        "unexpected_examples": [],
        "unexpected_total": 0,
    }
    assert all(item["pass"] is True for item in report["semantic_canaries"].values())
    assert metadata["claim_scope"]["given_geometric_lemmas"]["inside_opb"] is False
    assert metadata["claim_scope"]["arithmetic_band"]["inside_opb"] is True
    assert metadata["proof_status"] == "translation_only_no_unsat_or_proof_claim"


def test_gate_has_no_encoder_or_r3_script_import() -> None:
    source = (HARNESS_ROOT / "verify_r3_upper_bound_pb_translation_v1.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any("r3_upper_bound_pb_encoder" in name for name in imports)
    assert not any("verify_r3_certificates" in name for name in imports)


def test_gate_rejects_resealed_constraint_tamper(
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path: Path,
) -> None:
    paths = _generate(encoder, tmp_path / "tampered")
    lines = paths["opb"].read_text(encoding="ascii").splitlines()
    target = next(index for index, line in enumerate(lines) if line.startswith("-"))
    first = lines[target]
    coefficient, remainder = first.split(" ", 1)
    lines[target] = f"{int(coefficient) - 1:+d} {remainder}"
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


def test_gate_rejects_bool_as_integer_variable_id(
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path: Path,
) -> None:
    paths = _generate(encoder, tmp_path / "bool_id")
    variable_map = _json(paths["var_map"])
    variables = variable_map["variables"]
    assert isinstance(variables, list) and isinstance(variables[0], dict)
    variables[0]["id"] = True
    _write_json(paths["var_map"], variable_map)

    metadata = _json(paths["meta"])
    assert isinstance(metadata["outputs"], dict)
    assert isinstance(metadata["outputs"]["var_map"], dict)
    metadata["outputs"]["var_map"]["sha256"] = _sha256(paths["var_map"])
    metadata["outputs"]["var_map"]["size_bytes"] = paths["var_map"].stat().st_size
    _write_json(paths["meta"], metadata)

    assert gate.main(_gate_args(paths)) == 1
    report = _json(paths["gate"])
    assert report["checks"]["translation_inputs_closed_and_hashed"] is True
    assert report["checks"]["variable_map_dense"] is False
    assert report["checks"]["variable_map_exact"] is False


def test_gate_rejects_planning_basis_and_git_snapshot_mutations(
    encoder: ModuleType,
    gate: ModuleType,
    tmp_path: Path,
) -> None:
    planning_paths = _generate(encoder, tmp_path / "planning_basis")
    planning = _json(planning_paths["estimate"])
    planning["proof_size_planning"]["basis"]["opb_multiplier"] = 1023
    _write_json(planning_paths["estimate"], planning)
    planning_meta = _json(planning_paths["meta"])
    planning_meta["estimate"]["sha256"] = _sha256(planning_paths["estimate"])
    planning_meta["estimate"]["size_bytes"] = planning_paths["estimate"].stat().st_size
    _write_json(planning_paths["meta"], planning_meta)
    assert gate.main(_gate_args(planning_paths)) == 1
    planning_report = _json(planning_paths["gate"])
    assert planning_report["checks"]["estimate_reconstruction_match"] is False

    git_paths = _generate(encoder, tmp_path / "git_snapshot")
    git_estimate = _json(git_paths["estimate"])
    git_metadata = _json(git_paths["meta"])
    for payload in (git_estimate, git_metadata):
        payload["git_snapshot"]["head"] = "0" * 40
    _write_json(git_paths["estimate"], git_estimate)
    git_metadata["estimate"]["sha256"] = _sha256(git_paths["estimate"])
    git_metadata["estimate"]["size_bytes"] = git_paths["estimate"].stat().st_size
    _write_json(git_paths["meta"], git_metadata)
    assert gate.main(_gate_args(git_paths)) == 1
    git_report = _json(git_paths["gate"])
    assert git_report["checks"]["encoder_provenance_match"] is False


def test_gate_rejects_geometry_capacity_boundary_and_direction_mutations(
    gate: ModuleType,
) -> None:
    geometry = copy.deepcopy(_problem_payload())
    geometry["facility_templates"]["manufacturing_3x3"]["modes"][0]["ports"][0][
        "body_cell"
    ]["y"] = 1
    with pytest.raises(gate.GateError, match="declared body edge"):
        gate._derive(geometry)

    capacity = copy.deepcopy(_problem_payload())
    capacity["operation_groups"][0]["port_needs"]["inputs"] = 99
    with pytest.raises(gate.GateError, match="physical input capacity"):
        gate._derive(capacity)

    boundary = copy.deepcopy(_problem_payload())
    boundary["facility_templates"]["boundary_storage_port"]["placement_rule"] = "free"
    with pytest.raises(gate.GateError, match="boundary storage placement rule"):
        gate._derive(boundary)

    directions = copy.deepcopy(_problem_payload())
    directions["coordinate_system"]["directions"] = ["N", "E", "S", "NW"]
    with pytest.raises(gate.GateError, match="cardinal directions"):
        gate._derive(directions)


def test_gate_band_ceil_and_halo_mutation_canaries(gate: ModuleType) -> None:
    band = gate._band_for_bounds(6, 70)
    assert len(band) == 2074
    assert not any(width * height == 1190 for width, height in band)
    assert gate._ceil_div(1, 4) == 1
    assert gate._ceil_div(-1, 4) == 0
    assert gate._ceil_div(-5, 4) == -1

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
    assert len(mutated_halo["violations"]) == 24
    assert mutated_halo["minimum_slack2"] == -2


def test_translation_outputs_refuse_overwrite(
    encoder: ModuleType,
    gate: ModuleType,
    complete_translation: dict[str, Path],
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


def test_runner_pins_formal_tools_and_resource_contract(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
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
    assert runner._expected_unit_is_cgroup_leaf(
        "/user.slice/app.slice/b0-r3.service", "b0-r3.service"
    )
    assert not runner._expected_unit_is_cgroup_leaf(
        "/user.slice/app.slice/not-b0-r3.service-extra", "b0-r3.service"
    )
    permissive_ancestor = {
        "memory_high": "max",
        "memory_max": str(40 * 1024**3),
        "memory_swap_max": str(16 * 1024**3),
    }
    restrictive_ancestor = {
        **permissive_ancestor,
        "memory_high": str(34 * 1024**3),
    }
    assert runner._ancestor_limits_allow_contract([permissive_ancestor])
    assert not runner._ancestor_limits_allow_contract([restrictive_ancestor])
    kernel_root = {
        "path": "/sys/fs/cgroup",
        "memory_high": None,
        "memory_max": None,
        "memory_swap_max": None,
    }
    missing_nonroot = {**kernel_root, "path": "/sys/fs/cgroup/user.slice"}
    assert runner._ancestor_limits_allow_contract([permissive_ancestor, kernel_root])
    assert not runner._ancestor_limits_allow_contract([permissive_ancestor, missing_nonroot])

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


def test_runner_rejects_truncated_or_ambiguous_proof_status(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    proof = tmp_path / "proof.pbp"
    proof.write_text("pseudo-Boolean proof version 2.0\n", encoding="utf-8")
    assert runner._proof_tail(proof)["complete"] is False
    proof.write_text(
        "pseudo-Boolean proof version 2.0\n"
        "conclusion UNSAT : 1\n"
        "end pseudo-Boolean proof\n",
        encoding="utf-8",
    )
    assert runner._proof_tail(proof)["complete"] is True

    stdout = tmp_path / "stdout.txt"
    stderr = tmp_path / "stderr.txt"
    stdout.write_text("s UNSATISFIABLE\ns SATISFIABLE\n", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    assert runner._status_lines(stdout, stderr) == ["s UNSATISFIABLE", "s SATISFIABLE"]
    stdout.write_text("", encoding="utf-8")
    stderr.write_text("s UNSATISFIABLE\n", encoding="utf-8")
    assert runner._stdout_status_exact(stdout, stderr, "s UNSATISFIABLE") is False
    stdout.write_text("s UNSATISFIABLE\n", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    assert runner._stdout_status_exact(stdout, stderr, "s UNSATISFIABLE") is True
    stderr.write_text("panic: unsupported proof step\n", encoding="utf-8")
    assert runner._error_markers(stdout, stderr) == ["panic: unsupported proof step"]


def test_runner_exact_runtime_contract_and_child_proof_cap(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    args = argparse.Namespace(
        proof_limit_bytes=runner.FORMAL_PROOF_LIMIT_BYTES - 1,
        min_free_bytes=runner.FORMAL_MIN_FREE_BYTES,
        solver_time_limit=runner.FORMAL_SOLVER_TIME_LIMIT_SECONDS,
        solver_wall_timeout=runner.FORMAL_SOLVER_WALL_TIMEOUT_SECONDS,
        verifier_wall_timeout=runner.FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS,
        monitor_interval=runner.FORMAL_MONITOR_INTERVAL_SECONDS,
        require_cgroup_contract=True,
        expected_systemd_unit="test.service",
    )
    with pytest.raises(runner.ToolchainError) as caught:
        runner._validate_exact_runtime_contract(args)
    assert caught.value.code == "runtime_contract_mismatch"

    output_dir = tmp_path / "child_cap"
    output_dir.mkdir()
    proof = output_dir / "proof.pbp"
    result = runner._run_child(
        [
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(proof)!r}).write_bytes(b'x'*9)",
        ],
        stdout_path=output_dir / "stdout.txt",
        stderr_path=output_dir / "stderr.txt",
        wall_timeout=10.0,
        monitor_interval=0.01,
        output_dir=output_dir,
        resources=[],
        phase="proof_cap_test",
        min_free_bytes=1,
        proof_path=proof,
        proof_limit_bytes=8,
    )
    assert result["termination_reason"] in {
        "proof_size_limit_exceeded",
        "proof_size_limit_exceeded_at_completion",
    }
    assert result["process_group_clean"] is True
    assert proof.stat().st_mtime_ns >= result["started_wall_time_ns"]


def test_runner_timeout_terminates_descendant_process_group(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "descendant_timeout"
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
        f"Path({str(grandchild_pid_path)!r}).write_text(str(child.pid), encoding='ascii')\n"
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
    assert grandchild_sigterm_path.is_file()
    assert grandchild_sigterm_path.read_text(encoding="ascii") == "SIGTERM\n"
    assert not (Path("/proc") / str(grandchild_pid)).exists()


def test_runner_manifest_and_closed_failure_classification(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "manifest"
    output_dir.mkdir()
    (output_dir / "formula.opb").write_text("* formula\n", encoding="ascii")
    (output_dir / "roundingsat.stdout.txt").write_text(
        "s UNSATISFIABLE\n", encoding="ascii"
    )
    (output_dir / "toolchain_record.json").write_text("{}\n", encoding="ascii")
    manifest = output_dir / "SHA256SUMS"
    report = runner._write_checksum_manifest(output_dir, manifest)
    assert report["covered_files"] == ["formula.opb", "roundingsat.stdout.txt"]
    assert report["excluded_to_avoid_hash_cycle"] == [
        "SHA256SUMS",
        "toolchain_record.json",
    ]
    assert "toolchain_record.json" not in manifest.read_text(encoding="ascii")
    assert runner._checksum_manifest_stable(output_dir, manifest, report)
    (output_dir / "formula.opb").write_text("* changed\n", encoding="ascii")
    assert not runner._checksum_manifest_stable(output_dir, manifest, report)
    with pytest.raises(FileExistsError):
        runner._write_checksum_manifest(output_dir, manifest)

    failures: list[str] = []
    runner._add_child_failures(
        failures,
        {
            "spawn_error": None,
            "termination_reason": None,
            "exit_code": 0,
            "process_group_clean": False,
        },
        "child",
    )
    assert failures == ["child_process_group_not_clean"]

    solver_failures: list[str] = []
    runner._add_child_failures(
        solver_failures,
        {
            "spawn_error": None,
            "termination_reason": None,
            "exit_code": 1,
            "process_group_clean": True,
        },
        "solver",
        accepted_exit_codes=frozenset({0, 1}),
    )
    assert solver_failures == []


def test_runner_formal_attempt_reservation_is_persistent_and_no_overwrite(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setattr(runner, "ARTIFACT_ROOT", artifact_root)
    context = {
        "output_dir": artifact_root / "formal-a001",
        "git_snapshots": {"runner": {"head": "1" * 40}},
    }
    marker = runner._reserve_formal_attempt(context, ["runner", "--formal"])
    assert marker.is_file()
    assert context["output_dir"].is_dir()
    with pytest.raises(runner.ToolchainError) as caught:
        runner._reserve_formal_attempt(context, ["runner", "--formal"])
    assert caught.value.code == "formal_attempt_already_consumed"

    second_root = tmp_path / "second-artifacts"
    monkeypatch.setattr(runner, "ARTIFACT_ROOT", second_root)
    existing_output = second_root / "already-exists"
    existing_output.mkdir(parents=True)
    second_context = {
        "output_dir": existing_output,
        "git_snapshots": {"runner": {"head": "2" * 40}},
    }
    with pytest.raises(FileExistsError):
        runner._reserve_formal_attempt(second_context, ["runner", "--formal"])
    assert (second_root / runner.ATTEMPT_MARKER_NAME).is_file()


def test_runner_gate_replay_mismatch_never_starts_solver(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "formal-artifacts"
    output_dir = artifact_root / "formal-a001"
    input_dir = tmp_path / "formal-inputs"
    input_dir.mkdir()
    input_paths = {
        "opb": input_dir / "formula.opb",
        "meta": input_dir / "meta.json",
        "var_map": input_dir / "var-map.json",
        "estimate": input_dir / "estimate.json",
        "translation_gate": input_dir / "gate.json",
    }
    input_paths["opb"].write_text("* formula\n", encoding="ascii")
    for name in ("meta", "var_map", "estimate"):
        input_paths[name].write_text("{}\n", encoding="ascii")
    input_paths["translation_gate"].write_text(
        '{"status":"PASS","checks":{},"corpus_errors":[]}\n',
        encoding="ascii",
    )
    input_records = {
        name: runner._file_record(path, PROJECT_ROOT)
        for name, path in input_paths.items()
    }
    source_paths = {
        "encoder": HARNESS_ROOT / "r3_upper_bound_pb_encoder_v1.py",
        "gate": HARNESS_ROOT / "verify_r3_upper_bound_pb_translation_v1.py",
        "runner": HARNESS_ROOT / "run_r3_upper_bound_pb_toolchain_v1.py",
    }
    sources = {
        name: runner._file_record(path, PROJECT_ROOT)
        for name, path in source_paths.items()
    }
    source_snapshot = {"head": "1" * 40, "surface": "stable"}
    cgroup_state = {
        "contract_pass": True,
        "cgroup_path": "/fake.slice/b0-test.service",
        "cgroup_directory": "/sys/fs/cgroup/fake.slice/b0-test.service",
        "systemd_properties": {"contract": "exact"},
        "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
    }
    context = {
        "root": PROJECT_ROOT,
        "output_dir": output_dir,
        "paths": {
            **input_paths,
            "roundingsat": tmp_path / "must-not-run-roundingsat",
            "roundingsat_repo": tmp_path / "must-not-read-roundingsat-repo",
            "veripb": tmp_path / "must-not-run-veripb",
        },
        "gate": {"status": "PASS", "corpus_errors": [], "checks": {}},
        "inputs": input_records,
        "strict_inputs": {},
        "evidence": {},
        "sources": sources,
        "git_snapshots": {
            "encoder": source_snapshot,
            "gate": source_snapshot,
            "runner": source_snapshot,
            "source_surface_start": source_snapshot,
        },
        "cgroup_start": cgroup_state,
        "tools_start": {"tools": "stable"},
        "proof_bound_bytes": 1,
        "preflight_free_bytes": 100_000_000_000,
    }
    monkeypatch.setattr(runner, "ARTIFACT_ROOT", artifact_root)
    monkeypatch.setattr(runner, "_preflight", lambda _args: context)
    monkeypatch.setattr(runner, "_source_snapshot", lambda _root: source_snapshot)
    monkeypatch.setattr(
        runner,
        "_tool_records_now",
        lambda _paths, _root: context["tools_start"],
    )
    monkeypatch.setattr(
        runner,
        "_cgroup_state",
        lambda _unit, _required: cgroup_state,
    )

    def fake_sample(
        resources: list[dict[str, object]],
        _output: Path,
        phase: str,
        _proof: Path | None,
        *,
        telemetry_path: Path | None = None,
        **_kwargs: object,
    ) -> None:
        sample = {
            "phase": phase,
            "free_bytes": 100_000_000_000,
            "proof_size_bytes": 0,
            "cgroup": {"cgroup_procs": []},
        }
        resources.append(sample)
        assert telemetry_path is not None
        runner._append_jsonl(telemetry_path, sample)

    child_calls: list[list[str]] = []

    def fake_child(
        command: list[str],
        *,
        stdout_path: Path,
        stderr_path: Path,
        **_kwargs: object,
    ) -> dict[str, object]:
        child_calls.append(command)
        stdout_path.write_text("gate replay mismatch\n", encoding="ascii")
        stderr_path.write_text("", encoding="ascii")
        replay_path = Path(command[command.index("--output") + 1])
        replay_path.write_text('{"status":"FAIL"}\n', encoding="ascii")
        return {
            "argv": command,
            "exit_code": 0,
            "termination_reason": None,
            "spawn_error": None,
            "process_group_clean": True,
            "stdout": runner._file_record(stdout_path, PROJECT_ROOT),
            "stderr": runner._file_record(stderr_path, PROJECT_ROOT),
        }

    monkeypatch.setattr(runner, "_sample", fake_sample)
    monkeypatch.setattr(runner, "_run_child", fake_child)
    args = argparse.Namespace(
        proof_limit_bytes=runner.FORMAL_PROOF_LIMIT_BYTES,
        min_free_bytes=runner.FORMAL_MIN_FREE_BYTES,
        solver_time_limit=runner.FORMAL_SOLVER_TIME_LIMIT_SECONDS,
        solver_wall_timeout=runner.FORMAL_SOLVER_WALL_TIMEOUT_SECONDS,
        verifier_wall_timeout=runner.FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS,
        monitor_interval=runner.FORMAL_MONITOR_INTERVAL_SECONDS,
        expected_systemd_unit="b0-test.service",
    )
    assert runner._execute(args, ["runner", "--formal-test"]) == 1
    assert len(child_calls) == 1
    assert child_calls[0][1].endswith("verify_r3_upper_bound_pb_translation_v1.py")
    record = _json(output_dir / "toolchain_record.json")
    assert record["claim"] == "none"
    assert "translation_gate_recheck_mismatch" in record["failure_codes"]


def test_runner_plans_gate_recheck_and_checksum_artifacts(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    planned = runner._planned_paths(tmp_path)
    assert planned["gate_recheck"].name == "translation_gate.recheck.json"
    assert planned["gate_recheck_stdout"].name.endswith("stdout.txt")
    assert planned["gate_recheck_stderr"].name.endswith("stderr.txt")
    assert planned["checksums"].name == "SHA256SUMS"


def test_expected_constraint_multiset_has_one_equality(gate: ModuleType) -> None:
    payload = json.loads(
        (
            PROJECT_ROOT
            / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
        ).read_text(encoding="utf-8")
    )
    expected = gate._build_expected(gate._derive(payload))
    relations = Counter(key[0] for key in expected["constraints"].elements())
    assert relations == {"=": 1, ">=": 2074}
