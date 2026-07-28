from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import ModuleType

import pytest

from devtools.research_run_contract import (
    ArtifactIdentity,
    ExclusiveRunRoot,
    build_artifact_root_manifest,
    canonical_json_bytes,
    make_research_run_config,
    make_research_run_receipt,
    read_stable_snapshot,
    replay_identity_graph,
    verify_artifact_root_closure,
)


pytestmark = pytest.mark.replay

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = PROJECT_ROOT / "docs" / "research" / "w0_power_cycle_domino_d6_20260728"
GATE_PATH = RESEARCH_DIR / "d6_joint_completion_gate.py"
RUNNER_PATH = RESEARCH_DIR / "run_d6_research.py"
REPLAYER_PATH = RESEARCH_DIR / "replay_d6_certificate.py"
COMMON_PATH = PROJECT_ROOT / "devtools" / "research_run_contract.py"
STRICT_PATH = (
    PROJECT_ROOT
    / "docs"
    / "research"
    / "cleanroom_rederivation_20260718"
    / "strict"
    / "external"
    / "problem_instance.json"
)
FRAMEWORK_PATH = Path("/home/zhuran24/下载/w0回复/1/W0_power_cycle_domino_framework_v1.json")
SEED_PATH = Path("/home/zhuran24/下载/w0回复/1/W0_geometry_only_seed_v1.json")

STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
FRAMEWORK_SHA256 = "db6046cf598f9b5738b7f8950c91ea31834e8214e7e07995175b71eb04bdbb89"
SEED_SHA256 = "18c72669105f486bf54a2665bd74d1ff952ce2eeb39b28a7b30d5ce8d5d2f5f1"
LEGACY_UNBOUND_SHA256 = "295bfef9b2681193e3a9cc085c479a960f87de0131abfbdfacb676479bdb2aa5"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    return _load_module("_test_w0_d6_replay_gate", GATE_PATH)


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load_module("_test_w0_d6_replay_runner", RUNNER_PATH)


@pytest.fixture(scope="module")
def input_paths() -> dict[str, Path]:
    paths = {
        "strict_instance": STRICT_PATH,
        "framework": FRAMEWORK_PATH,
        "seed": SEED_PATH,
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        pytest.skip(f"external W0 D6 research inputs unavailable: {missing}")
    expected = {
        "strict_instance": STRICT_SHA256,
        "framework": FRAMEWORK_SHA256,
        "seed": SEED_SHA256,
    }
    for name, path in paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[name]
    return paths


def _claim_boundary(status: str) -> str:
    return {
        "FEASIBLE": "feasible_only_for_the_exact_local_d6_antecedent",
        "INFEASIBLE": "infeasible_only_for_the_exact_local_d6_antecedent",
        "UNKNOWN": "unknown_no_rejection_cut_or_global_conclusion",
    }[status]


def _replay_command(
    run_root: Path,
    *,
    output: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    argv = [
        "/usr/bin/python3",
        "-I",
        "-B",
        str(run_root / "sources" / "replay_d6_certificate.py"),
        "--run-root",
        str(run_root),
    ]
    if output is not None:
        argv.extend(("--output", str(output)))
    return subprocess.run(argv, check=False, capture_output=True)


def _decode_cli_json(raw: bytes) -> dict[str, object]:
    value = json.loads(raw)
    assert type(value) is dict
    return value


def _artifact_tree_snapshot(root: Path) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        item = path.lstat()
        if stat.S_ISDIR(item.st_mode):
            snapshot[relative] = {"type": "directory"}
        elif stat.S_ISREG(item.st_mode):
            raw = path.read_bytes()
            snapshot[relative] = {
                "type": "regular_file",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        elif stat.S_ISLNK(item.st_mode):
            snapshot[relative] = {
                "type": "symlink",
                "target": os.readlink(path),
            }
        else:
            snapshot[relative] = {"type": "special", "mode": item.st_mode}
    return snapshot


def _copy_snapshots(
    run_root: ExclusiveRunRoot,
    paths: dict[str, Path],
    relative_paths: dict[str, str],
) -> tuple[dict[str, object], dict[str, ArtifactIdentity]]:
    snapshots = {name: read_stable_snapshot(path) for name, path in paths.items()}
    copies = {
        name: run_root.write_bytes(relative_paths[name], snapshot.data)
        for name, snapshot in snapshots.items()
    }
    return snapshots, copies


def _make_run(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
    *,
    status: str,
    invalid_feasible: bool = False,
) -> Path:
    run_root = ExclusiveRunRoot.create(tmp_path / f"producer-{status.lower()}")
    run_root.mkdir("inputs")
    run_root.mkdir("sources")
    input_snapshots, input_copies = _copy_snapshots(
        run_root,
        input_paths,
        {
            "strict_instance": "inputs/strict_instance.json",
            "framework": "inputs/framework.json",
            "seed": "inputs/seed.json",
        },
    )
    source_paths = {
        "runner": RUNNER_PATH,
        "gate": GATE_PATH,
        "replayer": REPLAYER_PATH,
        "common_contract": COMMON_PATH,
    }
    source_snapshots, source_copies = _copy_snapshots(
        run_root,
        source_paths,
        {
            "runner": "sources/run_d6_research.py",
            "gate": "sources/d6_joint_completion_gate.py",
            "replayer": "sources/replay_d6_certificate.py",
            "common_contract": "sources/research_run_contract.py",
        },
    )
    decoded = {
        name: json.loads(snapshot.data)
        for name, snapshot in input_snapshots.items()
    }
    antecedent = gate.build_d6_antecedent(
        decoded["strict_instance"],
        decoded["framework"],
        decoded["seed"],
        attachment_scope="seed_narrow",
    )
    antecedent_identity = run_root.write_json("antecedent.json", antecedent)
    replay_template = [
        "<python3>",
        "-I",
        "-B",
        source_copies["replayer"].path,
        "--run-root",
        str(run_root.path),
    ]
    git_head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    config = make_research_run_config(
        experiment_id="w0_power_cycle_domino_d6",
        payload={
            "schema": "w0_d6_run_config_v2",
            "attachment_scope": "seed_narrow",
            "solver": {"workers": 2, "random_seed": 0, "max_time_seconds": 3600},
            "runtime": {
                "python_version": "fixture",
                "python_implementation": "fixture",
                "python_executable": "/fixture/python",
                "ortools_distribution_version": "fixture",
            },
            "process_contract": {
                "schema": "isolated_python_process_contract_v1",
                "required_argv_flags": ["-I", "-B"],
                "observed": {
                    "isolated": 1,
                    "ignore_environment": 1,
                    "no_user_site": 1,
                    "safe_path": True,
                    "dont_write_bytecode_flag": 1,
                    "dont_write_bytecode_runtime": True,
                },
            },
            "git": {
                "project_root": str(PROJECT_ROOT),
                "head": git_head,
                "status_porcelain_v1": "",
                "clean": True,
            },
            "inputs": {
                name: {
                    "external": input_snapshots[name].identity.as_dict(),
                    "run_copy": input_copies[name].as_dict(),
                }
                for name in sorted(input_snapshots)
            },
            "sources": {
                name: {
                    "working_tree": source_snapshots[name].identity.as_dict(),
                    "run_copy": source_copies[name].as_dict(),
                }
                for name in sorted(source_snapshots)
            },
            "antecedent": antecedent_identity.as_dict(),
            "rejected_producer_claims": [
                {
                    "claim_path": "seed.validation_summary.source_sha256",
                    "accepted_as_binding": False,
                    "actual_seed_sha256": SEED_SHA256,
                    "reason": (
                        "producer-reported source identity is not an independent binding "
                        "to the snapshotted seed bytes"
                    ),
                    "claimed_sha256": LEGACY_UNBOUND_SHA256,
                    "matches_known_unbound_claim": True,
                }
            ],
            "authority_boundary": {
                "artifact_status": "research_only_local_d6",
                "proves_whole_witness": False,
                "changes_lower_bound": False,
                "changes_upper_bound": False,
                "may_emit_cut_or_rejection": False,
                "production_authority": False,
                "certified_exact_source_authority": False,
                "frozen_or_sealed_input_mutation": False,
            },
            "replay": {"argv_template": replay_template},
        },
    )
    config_identity = run_root.write_json("config.json", config)

    configuration_identity: ArtifactIdentity | None = None
    certificate_identity: ArtifactIdentity | None = None
    if status == "FEASIBLE":
        assert invalid_feasible
        configuration = {
            "schema": "w0_d6_configuration_v1",
            "antecedent_sha256": antecedent_identity.sha256,
            "claim_boundary": _claim_boundary(status),
            "bodies": [],
            "transport": [],
            "cycle_roles": [],
            "flows": {
                "OUT": {
                    "arcs": [],
                    "terminal_emissions": [],
                    "cycle_absorptions": [],
                    "reachability": [],
                },
                "IN": {
                    "arcs": [],
                    "cycle_emissions": [],
                    "terminal_absorptions": [],
                    "reachability": [],
                },
            },
        }
        configuration_identity = run_root.write_json("configuration.json", configuration)
        certificate = {
            "schema": "w0_d6_local_certificate_v1",
            "antecedent_sha256": antecedent_identity.sha256,
            "configuration_sha256": configuration_identity.sha256,
            "status": "FEASIBLE",
            "claim_boundary": _claim_boundary(status),
        }
        certificate_identity = run_root.write_json("certificate.json", certificate)

    if status == "UNKNOWN":
        gate_observation = {
            "schema": "w0_d6_gate_execution_observation_v1",
            "status": status,
            "status_detail": "synthetic_unknown_without_verdict",
            "claim_boundary": _claim_boundary(status),
            "solver_statistics": {},
        }
    else:
        gate_observation = {
            "schema": "w0_d6_gate_result_v1",
            "status": status,
            "status_detail": "synthetic_status_for_replay_contract",
            "claim_boundary": _claim_boundary(status),
            "antecedent_sha256": antecedent_identity.sha256,
            "solver_statistics": {
                "wall_time_ms": 1,
                "num_conflicts": 0,
                "num_branches": 0,
                "response_stats": "synthetic fixture",
                "workers": 2,
                "random_seed": 0,
                "max_time_ms": 3_600_000,
            },
        }
    result = {
        "schema": "w0_d6_result_v1",
        "status": status,
        "antecedent_sha256": antecedent_identity.sha256,
        "configuration_sha256": (
            None if configuration_identity is None else configuration_identity.sha256
        ),
        "certificate_sha256": (
            None if certificate_identity is None else certificate_identity.sha256
        ),
        "claim_boundary": _claim_boundary(status),
        "gate_observation": gate_observation,
    }
    result_identity = run_root.write_json("result.json", result)
    artifacts = {
        "config": config_identity,
        "antecedent": antecedent_identity,
        "result": result_identity,
        **{f"inputs.{name}": identity for name, identity in input_copies.items()},
        **{f"sources.{name}": identity for name, identity in source_copies.items()},
    }
    if configuration_identity is not None:
        artifacts["configuration"] = configuration_identity
    if certificate_identity is not None:
        artifacts["certificate"] = certificate_identity
    graph = replay_identity_graph(artifacts)
    artifact_root_manifest = build_artifact_root_manifest(run_root)
    verify_artifact_root_closure(
        run_root,
        artifact_root_manifest,
        receipt_present=False,
    )
    receipt = make_research_run_receipt(
        experiment_id="w0_power_cycle_domino_d6",
        config_identity=config_identity,
        artifacts=artifacts,
        payload={
            "schema": "w0_d6_receipt_payload_v2",
            "status": status,
            "attachment_scope": "seed_narrow",
            "antecedent_sha256": antecedent_identity.sha256,
            "result_sha256": result_identity.sha256,
            "configuration_sha256": (
                None if configuration_identity is None else configuration_identity.sha256
            ),
            "certificate_sha256": (
                None if certificate_identity is None else certificate_identity.sha256
            ),
            "identity_graph_sha256": graph.graph_sha256,
            "artifact_root_manifest": artifact_root_manifest,
            "claim_boundary": _claim_boundary(status),
            "replay": {"argv_template": replay_template},
        },
    )
    run_root.write_json("receipt.json", receipt)
    verify_artifact_root_closure(
        run_root,
        artifact_root_manifest,
        receipt_present=True,
    )
    return run_root.path


@pytest.mark.parametrize("status", ["UNKNOWN", "INFEASIBLE"])
def test_independent_replay_accepts_only_the_exact_nonfeasible_receipt_scope(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
    status: str,
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status=status)

    completed = _replay_command(run_root)
    assert completed.returncode == 0, completed.stderr.decode()
    replay = _decode_cli_json(completed.stdout)

    assert replay["status"] == "PASS"
    assert replay["producer_status"] == status
    assert replay["artifact_root"]["verified"] is True
    assert replay["antecedent_recomputation"]["verified"] is True
    assert replay["semantic_verification"] == {"performed": False, "summary": None}
    if status == "UNKNOWN":
        assert replay["conclusion"] is None
    else:
        assert replay["conclusion"]["kind"] == "exact_d6_antecedent_infeasible_only"


def test_byte_tamper_fails_before_any_local_conclusion(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    with (run_root / "result.json").open("ab") as handle:
        handle.write(b" ")

    completed = _replay_command(run_root)
    assert completed.returncode == 2
    assert _decode_cli_json(completed.stderr)["error_code"] == "IDENTITY_MISMATCH"


def test_invalid_feasible_configuration_never_becomes_a_certificate(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(
        tmp_path,
        gate,
        input_paths,
        status="FEASIBLE",
        invalid_feasible=True,
    )

    completed = _replay_command(run_root)
    assert completed.returncode == 2
    assert _decode_cli_json(completed.stderr)["error_code"] in {
        "BODY_CLASS_COUNT_MISMATCH",
        "BODY_TILE_TYPE_COUNT_MISMATCH",
        "ACTIVE_PORT_TOTAL_MISMATCH",
    }


@pytest.mark.parametrize(
    "pollution_kind",
    ["regular_file", "empty_directory", "pycache", "symlink", "fifo"],
)
def test_unregistered_root_descendants_fail_before_status_interpretation(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
    pollution_kind: str,
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    if pollution_kind == "regular_file":
        (run_root / "unregistered.txt").write_bytes(b"pollution")
    elif pollution_kind == "empty_directory":
        (run_root / "unregistered-directory").mkdir()
    elif pollution_kind == "pycache":
        cache = run_root / "sources" / "__pycache__"
        cache.mkdir()
        (cache / "replay_d6_certificate.cpython-999.pyc").write_bytes(b"cache")
    elif pollution_kind == "symlink":
        (run_root / "unregistered-link").symlink_to(run_root / "config.json")
    else:
        os.mkfifo(run_root / "unregistered-fifo")

    completed = _replay_command(run_root)

    assert completed.returncode == 2
    error = _decode_cli_json(completed.stderr)
    expected = {
        "symlink": "ARTIFACT_ROOT_SYMLINK_REJECTED",
        "fifo": "ARTIFACT_ROOT_SPECIAL_NODE_REJECTED",
    }.get(pollution_kind, "ARTIFACT_ROOT_CLOSURE_MISMATCH")
    assert error["error_code"] == expected
    assert error["conclusion"] is None


def test_registered_empty_directory_is_not_a_valid_d6_artifact_layout(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    extra = run_root / "registered-but-unowned"
    extra.mkdir()
    receipt_path = run_root / "receipt.json"
    receipt = _decode_cli_json(receipt_path.read_bytes())
    payload = receipt["payload"]
    assert type(payload) is dict
    manifest = payload["artifact_root_manifest"]
    assert type(manifest) is dict
    entries = manifest["entries"]
    assert type(entries) is list
    entries.append({"path": extra.name, "type": "directory"})
    entries.sort(key=lambda entry: entry["path"])
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    completed = _replay_command(run_root)

    assert completed.returncode == 2
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] == "ARTIFACT_ROOT_DIRECTORY_SET_MISMATCH"
    assert error["conclusion"] is None


def test_runner_rejects_a_pre_manifest_empty_directory(
    tmp_path: Path,
    runner: ModuleType,
) -> None:
    run_root = ExclusiveRunRoot.create(tmp_path / "producer-with-empty-directory")
    config_identity = run_root.write_json("config.json", {"synthetic": True})
    run_root.mkdir("unowned-empty-directory")
    manifest = build_artifact_root_manifest(run_root)

    with pytest.raises(runner.D6RunnerError) as exc_info:
        runner._validate_manifest_artifact_bijection(
            run_root,
            manifest,
            {"config": config_identity},
        )

    assert exc_info.value.code == "ARTIFACT_ROOT_DIRECTORY_SET_MISMATCH"
    assert not (run_root.path / "receipt.json").exists()


def test_runner_rejects_pre_receipt_import_bytecode(
    tmp_path: Path,
    runner: ModuleType,
) -> None:
    run_root = ExclusiveRunRoot.create(tmp_path / "producer-with-import-cache")
    run_root.mkdir("sources")
    gate_identity = run_root.write_bytes(
        "sources/d6_joint_completion_gate.py",
        GATE_PATH.read_bytes(),
    )
    probe = tmp_path / "unsafe_pre_receipt_import.py"
    probe.write_text(
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('_unsafe_pre_receipt', sys.argv[1])\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n",
        encoding="utf-8",
    )
    imported = subprocess.run(
        [sys.executable, str(probe), gate_identity.path],
        env={},
        check=False,
        capture_output=True,
    )
    assert imported.returncode == 0, imported.stderr.decode()
    assert list((run_root.path / "sources").rglob("*.pyc"))
    manifest = build_artifact_root_manifest(run_root)

    with pytest.raises(runner.D6RunnerError) as exc_info:
        runner._validate_manifest_artifact_bijection(
            run_root,
            manifest,
            {"sources.gate": gate_identity},
        )

    assert exc_info.value.code == "ARTIFACT_ROOT_ARTIFACT_SET_MISMATCH"
    assert not (run_root.path / "receipt.json").exists()


def test_pollution_added_after_a_clean_replay_is_rejected(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    clean = _replay_command(run_root)
    assert clean.returncode == 0, clean.stderr.decode()

    (run_root / "post-replay-pollution").write_bytes(b"late")
    polluted = _replay_command(run_root)

    assert polluted.returncode == 2
    assert _decode_cli_json(polluted.stderr)["error_code"] == (
        "ARTIFACT_ROOT_CLOSURE_MISMATCH"
    )


@pytest.mark.parametrize("receipt_kind", ["missing", "directory", "symlink"])
def test_fixed_terminal_receipt_must_exist_as_one_regular_file(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
    receipt_kind: str,
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    receipt_path = run_root / "receipt.json"
    receipt_path.unlink()
    if receipt_kind == "directory":
        receipt_path.mkdir()
    elif receipt_kind == "symlink":
        receipt_path.symlink_to(run_root / "config.json")

    completed = _replay_command(run_root)

    assert completed.returncode == 2
    assert _decode_cli_json(completed.stderr)["error_code"] in {
        "ARTIFACT_NOT_REGULAR",
        "PATH_COMPONENT_MISSING",
        "SYMLINK_REJECTED",
    }


def test_receipt_manifest_cannot_register_the_receipt_itself(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    receipt_path = run_root / "receipt.json"
    receipt = _decode_cli_json(receipt_path.read_bytes())
    payload = receipt["payload"]
    assert type(payload) is dict
    manifest = payload["artifact_root_manifest"]
    assert type(manifest) is dict
    entries = manifest["entries"]
    assert type(entries) is list
    entries.append({"path": "receipt.json", "type": "regular_file"})
    entries.sort(key=lambda item: item["path"])
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    completed = _replay_command(run_root)

    assert completed.returncode == 2
    assert _decode_cli_json(completed.stderr)["error_code"] == (
        "ARTIFACT_ROOT_RECEIPT_RESERVED"
    )


def test_historical_v1_receipt_is_rejected_before_artifact_or_status_replay(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    receipt_path = run_root / "receipt.json"
    receipt = _decode_cli_json(receipt_path.read_bytes())
    payload = receipt["payload"]
    assert type(payload) is dict
    payload["schema"] = "w0_d6_receipt_payload_v1"
    payload.pop("artifact_root_manifest")
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    completed = _replay_command(run_root)

    assert completed.returncode == 2
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] == "ROOT_CLOSURE_CONTRACT_MISSING"
    assert error["conclusion"] is None


def test_runner_rejects_missing_interpreter_flags_before_creating_run_root(
    tmp_path: Path,
    input_paths: dict[str, Path],
) -> None:
    run_root = tmp_path / "must-not-exist"
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER_PATH),
            "--strict",
            str(input_paths["strict_instance"]),
            "--framework",
            str(input_paths["framework"]),
            "--seed",
            str(input_paths["seed"]),
            "--run-root",
            str(run_root),
        ],
        env={"PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert _decode_cli_json(completed.stderr)["error_code"] == (
        "PYTHON_PROCESS_CONTRACT_INVALID"
    )
    assert not run_root.exists()


def test_actual_runner_writes_a_cache_free_closed_root_without_calling_solver(
    tmp_path: Path,
    input_paths: dict[str, Path],
) -> None:
    run_root = tmp_path / "synthetic-producer-root"
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    probe = tmp_path / "synthetic_runner_probe.py"
    probe.write_text(
        "import hashlib, importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('_synthetic_runner', sys.argv[1])\n"
        "runner = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = runner\n"
        "spec.loader.exec_module(runner)\n"
        "runner._prepare_run_parent = lambda _path: None\n"
        "runner._git_identity = lambda: {\n"
        "    'project_root': str(runner.PROJECT_ROOT),\n"
        "    'head': sys.argv[6],\n"
        "    'status_porcelain_v1': '',\n"
        "    'clean': True,\n"
        "}\n"
        "original_gate_callable = runner._gate_callable\n"
        "def synthetic_solve(*_args, **kwargs):\n"
        "    antecedent_sha = hashlib.sha256(\n"
        "        runner.canonical_json_bytes(kwargs['antecedent'])\n"
        "    ).hexdigest()\n"
        "    return {\n"
        "        'schema': 'w0_d6_gate_result_v1',\n"
        "        'status': 'UNKNOWN',\n"
        "        'status_detail': 'synthetic_without_solver',\n"
        "        'claim_boundary': 'unknown_no_rejection_cut_or_global_conclusion',\n"
        "        'antecedent_sha256': antecedent_sha,\n"
        "        'solver_statistics': {\n"
        "            'wall_time_ms': 0,\n"
        "            'num_conflicts': 0,\n"
        "            'num_branches': 0,\n"
        "            'response_stats': 'synthetic without solver',\n"
        "            'workers': 2,\n"
        "            'random_seed': 0,\n"
        "            'max_time_ms': 3600000,\n"
        "        },\n"
        "        'configuration': None,\n"
        "        'certificate': None,\n"
        "    }\n"
        "def gate_callable(module, name):\n"
        "    if name == 'solve_d6_joint_completion':\n"
        "        return synthetic_solve\n"
        "    return original_gate_callable(module, name)\n"
        "runner._gate_callable = gate_callable\n"
        "raise SystemExit(runner.main([\n"
        "    '--strict', sys.argv[2],\n"
        "    '--framework', sys.argv[3],\n"
        "    '--seed', sys.argv[4],\n"
        "    '--run-root', sys.argv[5],\n"
        "]))\n",
        encoding="utf-8",
    )
    produced = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(probe),
            str(RUNNER_PATH),
            str(input_paths["strict_instance"]),
            str(input_paths["framework"]),
            str(input_paths["seed"]),
            str(run_root),
            head,
        ],
        env={},
        check=False,
        capture_output=True,
    )

    assert produced.returncode == 0, produced.stderr.decode()
    summary = _decode_cli_json(produced.stdout)
    assert summary["status"] == "UNKNOWN"
    assert summary["artifact_root_closed"] is True
    assert type(summary["receipt_identity"]) is dict
    receipt_snapshot = read_stable_snapshot(run_root / "receipt.json")
    assert summary["receipt_identity"] == receipt_snapshot.identity.as_dict()
    producer_receipt = _decode_cli_json(receipt_snapshot.data)
    assert "receipt" not in producer_receipt["artifacts"]
    payload = producer_receipt["payload"]
    assert type(payload) is dict
    manifest = payload["artifact_root_manifest"]
    assert type(manifest) is dict
    entries = manifest["entries"]
    assert type(entries) is list
    assert all(entry["path"] != "receipt.json" for entry in entries)
    assert list(run_root.rglob("__pycache__")) == []
    assert list(run_root.rglob("*.pyc")) == []

    replayed = _replay_command(run_root)
    assert replayed.returncode == 0, replayed.stderr.decode()
    replay = _decode_cli_json(replayed.stdout)
    assert replay["producer_status"] == "UNKNOWN"
    assert replay["artifact_root"]["verified"] is True
    assert replay["artifact_root"]["producer_receipt_observed_identity"] == (
        receipt_snapshot.identity.as_dict()
    )


def test_gate_import_under_required_flags_leaves_no_run_root_cache(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "producer-root"
    source_dir = run_root / "sources"
    source_dir.mkdir(parents=True)
    copied_gate = source_dir / "d6_joint_completion_gate.py"
    copied_gate.write_bytes(GATE_PATH.read_bytes())
    probe = tmp_path / "load_gate_probe.py"
    probe.write_text(
        "import importlib.util, pathlib, sys\n"
        "spec = importlib.util.spec_from_file_location('_runner_probe', sys.argv[1])\n"
        "runner = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = runner\n"
        "spec.loader.exec_module(runner)\n"
        "runner._load_gate_module(pathlib.Path(sys.argv[2]))\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(probe),
            str(RUNNER_PATH),
            str(copied_gate),
        ],
        env={},
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr.decode()
    assert list(run_root.rglob("__pycache__")) == []
    assert list(run_root.rglob("*.pyc")) == []


def test_real_import_generated_pyc_is_rejected_as_post_receipt_pollution(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    copied_gate = run_root / "sources" / "d6_joint_completion_gate.py"
    probe = tmp_path / "unsafe_import_probe.py"
    probe.write_text(
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('_unsafe_gate_import', sys.argv[1])\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n",
        encoding="utf-8",
    )
    imported = subprocess.run(
        [sys.executable, str(probe), str(copied_gate)],
        env={},
        check=False,
        capture_output=True,
    )
    assert imported.returncode == 0, imported.stderr.decode()
    assert list((run_root / "sources").rglob("*.pyc"))

    replayed = _replay_command(run_root)

    assert replayed.returncode == 2
    assert _decode_cli_json(replayed.stderr)["error_code"] == (
        "ARTIFACT_ROOT_CLOSURE_MISMATCH"
    )


def test_cli_replay_is_stdlib_only_and_output_is_no_overwrite(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    output = tmp_path / "replay" / "replay_receipt.json"
    output.parent.mkdir()
    root_tree_before = _artifact_tree_snapshot(run_root)
    first = _replay_command(run_root, output=output)
    second = _replay_command(run_root, output=output)

    assert first.returncode == 0, first.stderr.decode()
    receipt = json.loads(output.read_bytes())
    assert receipt["schema"] == "w0_d6_replay_receipt_v2"
    assert receipt["producer_status"] == "UNKNOWN"
    assert receipt["conclusion"] is None
    assert receipt["artifact_root"]["verified"] is True
    assert receipt["replayer_process_contract"]["required_argv_flags"] == ["-I", "-B"]
    assert second.returncode == 2
    error = json.loads(second.stderr)
    assert error["error_code"] == "NO_OVERWRITE_COLLISION"

    source = REPLAYER_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "from ortools",
        "import ortools",
        "from devtools",
        "from src",
        "import d6_joint_completion_gate",
        "import run_d6_research",
    ):
        assert forbidden not in source
    assert canonical_json_bytes(receipt) == output.read_bytes()
    root_tree_after = _artifact_tree_snapshot(run_root)
    assert root_tree_after == root_tree_before
    assert list(run_root.rglob("__pycache__")) == []
    assert list(run_root.rglob("*.pyc")) == []


def test_replay_output_cannot_pollute_the_closed_producer_root(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    output = run_root / "post-receipt-output.json"

    completed = _replay_command(run_root, output=output)

    assert completed.returncode == 2
    assert _decode_cli_json(completed.stderr)["error_code"] == (
        "OUTPUT_INSIDE_ARTIFACT_ROOT"
    )
    assert not output.exists()
    clean = _replay_command(run_root)
    assert clean.returncode == 0, clean.stderr.decode()
