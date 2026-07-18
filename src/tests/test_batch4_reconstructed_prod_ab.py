from __future__ import annotations

import ast
import hashlib
import inspect
import sys
import textwrap
from dataclasses import replace
from pathlib import Path

import pytest

from docs.research.front_offset_incident_20260718.batch4_harness import (
    run_reconstructed_prod_ab as prod_ab,
)
from docs.research.front_offset_incident_20260718.batch4_harness.run_reconstructed_prod_ab import (
    DEFAULT_BINDING_ALT_CAP,
    DEFAULT_FLOW_SECONDS,
    DEFAULT_RANDOM_SEED,
    DEFAULT_WORKERS,
    FCL_RAW_SCOPE_ATTRIBUTE,
    MASTER_BRANCHING,
    MASTER_PROBING_LEVEL,
    MASTER_SYMMETRY_LEVEL,
    RAB_CUT_COUNTER_ATTRIBUTES,
    ReconstructedProdABError,
    RunConfig,
    _atomic_write_json,
    _controlled_environment,
    _fcl_raw_scope_acceptance,
    _input_records,
    _layout_snapshot_payload,
    _prepare_output_dir,
    _source_records,
    _validate_config,
    _verify_hint,
    _worker_argv,
    launch,
    parse_config,
)


def _config(tmp_path: Path, **overrides: object) -> RunConfig:
    values: dict[str, object] = {
        "binding_alt_cap": DEFAULT_BINDING_ALT_CAP,
        "binding_seconds": 600.0,
        "experiment": "rab",
        "flow_seconds": DEFAULT_FLOW_SECONDS,
        "ghost_h": 6,
        "ghost_w": 6,
        "hint": None,
        "hint_sha256": None,
        "lift": None,
        "master_seconds": 900.0,
        "max_iterations": 6,
        "output_dir": tmp_path / "out",
        "rab": "on",
        "random_seed": DEFAULT_RANDOM_SEED,
        "routing_seconds": 600.0,
        "run_tag": "batch4_rab_on",
        "workers": DEFAULT_WORKERS,
    }
    values.update(overrides)
    return RunConfig(**values)  # type: ignore[arg-type]


def test_only_sensible_rab_and_fcl_combinations_are_accepted(
    tmp_path: Path,
) -> None:
    _validate_config(_config(tmp_path, experiment="rab", rab="off", lift=None))
    _validate_config(_config(tmp_path, experiment="fcl", rab="on", lift="off"))
    _validate_config(_config(tmp_path, experiment="fcl", rab="on", lift="on"))

    invalid = [
        _config(tmp_path, experiment="rab", lift="on"),
        _config(tmp_path, experiment="fcl", rab="off", lift="on"),
        _config(tmp_path, experiment="fcl", rab="on", lift=None),
    ]
    for config in invalid:
        with pytest.raises(ReconstructedProdABError):
            _validate_config(config)


def test_public_parser_pins_defaults_and_rejects_invalid_fcl(
    tmp_path: Path,
) -> None:
    config = parse_config(
        [
            "--experiment",
            "rab",
            "--rab",
            "off",
            "--run-tag",
            "rab_off",
            "--output-dir",
            str(tmp_path / "rab"),
        ]
    )
    assert config.random_seed == 1
    assert config.workers == 1
    assert config.binding_alt_cap == 200
    assert config.max_iterations == 6
    assert config.flow_seconds == 60.0
    assert config.hint is None

    with pytest.raises(SystemExit) as exc_info:
        parse_config(
            [
                "--experiment",
                "fcl",
                "--rab",
                "off",
                "--lift",
                "on",
                "--run-tag",
                "bad",
                "--output-dir",
                str(tmp_path / "bad"),
            ]
        )
    assert exc_info.value.code == 2


def test_child_environment_is_closed_and_all_experiment_knobs_are_explicit(
    tmp_path: Path,
) -> None:
    config = _config(
        tmp_path,
        experiment="fcl",
        rab="on",
        lift="off",
        random_seed=7,
        workers=2,
        binding_alt_cap=123,
    )
    env = _controlled_environment(
        config,
        inherited={
            "EXACT_STALE_TOGGLE": "1",
            "EXACT_FLOW_SECONDS": "999",
            "HOME": "/safe/home",
            "PATH": "/safe/bin",
            "SECRET_TOKEN": "must-not-leak",
        },
    )

    assert "EXACT_STALE_TOGGLE" not in env
    assert "EXACT_FLOW_SECONDS" not in env
    assert "SECRET_TOKEN" not in env
    assert env["HOME"] == "/safe/home"
    assert env["PYTHONHASHSEED"] == "0"
    assert env["EXACT_MASTER_RANDOM_SEED"] == "7"
    assert env["EXACT_MASTER_RANDOM_SEED_BASE"] == "7"
    assert env["EXACT_CP_SAT_WORKERS"] == "2"
    assert env["EXACT_MASTER_CP_SAT_WORKERS"] == "2"
    assert env["OMP_NUM_THREADS"] == "2"
    assert env["OPENBLAS_NUM_THREADS"] == "2"
    assert env["EXACT_MASTER_SEARCH_BRANCHING"] == MASTER_BRANCHING
    assert env["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] == str(
        MASTER_PROBING_LEVEL
    )
    assert env["EXACT_MASTER_SYMMETRY_LEVEL"] == str(
        MASTER_SYMMETRY_LEVEL
    )
    assert env["EXACT_B1_BINDING_ALT_CAP"] == "123"
    assert env["EXACT_B1_ROUTING_AWARE_BINDING"] == "1"
    assert env["EXACT_MASTER_FRONT_CLEAR_LIFT"] == "0"


def test_worker_argv_records_every_budget_and_fixed_knob(tmp_path: Path) -> None:
    config = _config(tmp_path, rab="off")
    argv = _worker_argv(config, tmp_path / "result.json")
    joined = " ".join(argv)
    expected_python = str(Path(sys.executable).absolute())

    assert argv[0] == expected_python
    assert prod_ab._system_info()["python_executable"] == expected_python

    for expected in (
        "--experiment rab",
        "--rab off",
        "--lift none",
        "--master-seconds 900.0",
        "--binding-seconds 600.0",
        "--routing-seconds 600.0",
        "--flow-seconds 60.0",
        "--max-iterations 6",
        "--workers 1",
        "--binding-alt-cap 200",
        "--random-seed 1",
    ):
        assert expected in joined


def test_main_preserves_invoked_venv_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr(prod_ab, "parse_config", lambda _argv: config)

    def fake_launch(
        received_config: RunConfig,
        *,
        launcher_argv: list[str],
    ) -> int:
        captured["config"] = received_config
        captured["launcher_argv"] = launcher_argv
        return 0

    monkeypatch.setattr(prod_ab, "launch", fake_launch)

    assert prod_ab.main(["--test-placeholder"]) == 0
    assert captured["config"] is config
    assert captured["launcher_argv"] == [
        str(Path(sys.executable).absolute()),
        str(Path(prod_ab.__file__).resolve()),
        "--test-placeholder",
    ]


def test_worker_passes_all_four_time_budgets_explicitly_to_controller() -> None:
    tree = ast.parse(textwrap.dedent(inspect.getsource(prod_ab._worker_run)))
    controller_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "LBBDController"
    ]
    assert len(controller_calls) == 1
    keyword_values = {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in controller_calls[0].keywords
        if keyword.arg is not None
    }
    expected = {
        "master_seconds": "config.master_seconds",
        "binding_seconds": "config.binding_seconds",
        "routing_seconds": "config.routing_seconds",
        "flow_seconds": "config.flow_seconds",
    }
    assert expected.items() <= keyword_values.items()


def test_optional_hint_is_pairwise_required_and_sha_pinned(
    tmp_path: Path,
) -> None:
    hint = tmp_path / "hint.json"
    raw = b'{"solution":{}}\n'
    hint.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()

    valid = _config(tmp_path, hint=hint, hint_sha256=digest)
    _validate_config(valid)
    record = _verify_hint(valid)
    assert record is not None
    assert record["sha256"] == digest

    with pytest.raises(ReconstructedProdABError, match="supplied together"):
        _validate_config(replace(valid, hint_sha256=None))
    with pytest.raises(ReconstructedProdABError, match="mismatch"):
        _verify_hint(replace(valid, hint_sha256="0" * 64))


def test_output_directory_and_atomic_json_are_write_once_at_run_scope(
    tmp_path: Path,
) -> None:
    output_dir = _prepare_output_dir(tmp_path / "new")
    assert output_dir.is_dir()
    with pytest.raises(FileExistsError):
        _prepare_output_dir(output_dir)

    record_path = output_dir / "run_record.json"
    _atomic_write_json(record_path, {"z": 2, "a": 1})
    first = record_path.read_bytes()
    _atomic_write_json(record_path, {"z": 3, "a": 1})
    assert first != record_path.read_bytes()
    assert record_path.read_text(encoding="utf-8").endswith("\n")


def test_layout_snapshot_and_fcl_acceptance_telemetry_canaries() -> None:
    solution = {"b": {"pose_idx": 2}, "a": {"pose_idx": 1}}
    first, first_sha = _layout_snapshot_payload(solution)
    second, second_sha = _layout_snapshot_payload(solution)
    assert first == second
    assert first_sha == second_sha == hashlib.sha256(first).hexdigest()

    assert _fcl_raw_scope_acceptance("off", []) == "NOT_APPLICABLE_OFF_ARM"
    assert _fcl_raw_scope_acceptance("on", []) == "NOT_EVALUATED"
    assert (
        _fcl_raw_scope_acceptance("on", [{"raw_lift_scope": 0}])
        == "PASS"
    )
    assert (
        _fcl_raw_scope_acceptance("on", [{"raw_lift_scope": 1}])
        == "FAIL"
    )
    assert RAB_CUT_COUNTER_ATTRIBUTES == (
        "_fine_grained_exact_safe_cut_count",
        "_binding_domain_empty_cut_count",
    )
    assert FCL_RAW_SCOPE_ATTRIBUTE == "_front_clear_raw_empty_by_iteration"


def test_source_records_pin_runner_and_current_production_consumers() -> None:
    records = _source_records()
    assert len(records) == 7
    assert any(path.endswith("run_reconstructed_prod_ab.py") for path in records)
    assert any(path.endswith("routing_binding_context.py") for path in records)
    assert any(path.endswith("port_binding.py") for path in records)
    for record in records.values():
        path = Path(str(record["absolute_path"]))
        assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_input_records_include_current_candidate_and_certified_inputs() -> None:
    records = _input_records()
    required = {
        "data/preprocessed/candidate_placements.json",
        "data/preprocessed/generic_io_requirements.json",
        "data/preprocessed/mandatory_exact_instances.json",
        "rules/canonical_rules.json",
        "rules/preprocess_plan.json",
    }
    assert required <= set(records)
    for name in required:
        record = records[name]
        assert record["project_relative_path"] == name
        assert len(str(record["sha256"])) == 64


def test_launcher_writes_four_provenance_artifacts_without_real_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    monkeypatch.setattr(prod_ab, "_input_records", lambda: {"input": {}})
    monkeypatch.setattr(prod_ab, "_git_snapshot", lambda: {"head": "a" * 40})
    monkeypatch.setattr(prod_ab, "_resource_limits", lambda: {"cgroup": {}})
    monkeypatch.setattr(prod_ab, "_source_records", lambda: {"source": {}})
    monkeypatch.setattr(prod_ab, "_system_info", lambda: {"system": "test"})
    monkeypatch.setattr(
        prod_ab,
        "_child_rusage",
        lambda: {"max_rss_kib": 1},
    )

    def fake_run(argv: list[str], **kwargs: object) -> object:
        result_path = Path(argv[argv.index("--result") + 1])
        _atomic_write_json(result_path, {"status": "COMPLETED"})
        kwargs["stdout"].write(b"worker stdout\n")  # type: ignore[union-attr]
        return prod_ab.subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(prod_ab.subprocess, "run", fake_run)
    exit_code = launch(
        config,
        launcher_argv=["python", "run_reconstructed_prod_ab.py"],
    )

    assert exit_code == 0
    output_dir = config.output_dir
    assert {path.name for path in output_dir.iterdir()} == {
        "result.json",
        "run_record.json",
        "stderr.txt",
        "stdout.txt",
    }
    run_record = prod_ab.json.loads(
        (output_dir / "run_record.json").read_text(encoding="utf-8")
    )
    assert run_record["semantic_label"] == "reconstructed_new_baseline"
    assert run_record["status"] == "COMPLETED"
    assert run_record["configuration"]["flow_seconds"] == 60.0
    assert run_record["execution_scope"] == (
        "fixed_ghost_current_production_inner_lbbd"
    )
    assert any("main.py" in item for item in run_record["limitations"])
    assert run_record["subprocess_environment"]["PYTHONHASHSEED"] == "0"
    assert run_record["invocation"]["launcher_argv"] == [
        "python",
        "run_reconstructed_prod_ab.py",
    ]
    assert run_record["output_sha256"]["stdout"] == hashlib.sha256(
        b"worker stdout\n"
    ).hexdigest()

    with pytest.raises(ReconstructedProdABError, match="existing"):
        launch(config, launcher_argv=["again"])
