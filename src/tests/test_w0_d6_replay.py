from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest

from devtools.research_run_contract import (
    ArtifactIdentity,
    ExclusiveRunRoot,
    canonical_json_bytes,
    make_research_run_config,
    make_research_run_receipt,
    read_stable_snapshot,
    replay_identity_graph,
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
def replayer() -> ModuleType:
    return _load_module("_test_w0_d6_independent_replayer", REPLAYER_PATH)


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
            "schema": "w0_d6_run_config_v1",
            "attachment_scope": "seed_narrow",
            "solver": {"workers": 2, "random_seed": 0, "max_time_seconds": 3600},
            "runtime": {
                "python_version": "fixture",
                "python_implementation": "fixture",
                "python_executable": "/fixture/python",
                "ortools_distribution_version": "fixture",
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
    receipt = make_research_run_receipt(
        experiment_id="w0_power_cycle_domino_d6",
        config_identity=config_identity,
        artifacts=artifacts,
        payload={
            "schema": "w0_d6_receipt_payload_v1",
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
            "claim_boundary": _claim_boundary(status),
            "replay": {"argv_template": replay_template},
        },
    )
    run_root.write_json("receipt.json", receipt)
    return run_root.path


@pytest.mark.parametrize("status", ["UNKNOWN", "INFEASIBLE"])
def test_independent_replay_accepts_only_the_exact_nonfeasible_receipt_scope(
    tmp_path: Path,
    gate: ModuleType,
    replayer: ModuleType,
    input_paths: dict[str, Path],
    status: str,
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status=status)

    replay = replayer.replay_run(run_root)

    assert replay["status"] == "PASS"
    assert replay["producer_status"] == status
    assert replay["antecedent_recomputation"]["verified"] is True
    assert replay["semantic_verification"] == {"performed": False, "summary": None}
    if status == "UNKNOWN":
        assert replay["conclusion"] is None
    else:
        assert replay["conclusion"]["kind"] == "exact_d6_antecedent_infeasible_only"


def test_byte_tamper_fails_before_any_local_conclusion(
    tmp_path: Path,
    gate: ModuleType,
    replayer: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    with (run_root / "result.json").open("ab") as handle:
        handle.write(b" ")

    with pytest.raises(replayer.ReplayError) as exc_info:
        replayer.replay_run(run_root)

    assert exc_info.value.code == "IDENTITY_MISMATCH"


def test_invalid_feasible_configuration_never_becomes_a_certificate(
    tmp_path: Path,
    gate: ModuleType,
    replayer: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(
        tmp_path,
        gate,
        input_paths,
        status="FEASIBLE",
        invalid_feasible=True,
    )

    with pytest.raises(replayer.ReplayError) as exc_info:
        replayer.replay_run(run_root)

    assert exc_info.value.code in {
        "BODY_CLASS_COUNT_MISMATCH",
        "BODY_TILE_TYPE_COUNT_MISMATCH",
        "ACTIVE_PORT_TOTAL_MISMATCH",
    }


def test_cli_replay_is_stdlib_only_and_output_is_no_overwrite(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    output = tmp_path / "replay" / "replay_receipt.json"
    output.parent.mkdir()
    argv = [
        "/usr/bin/python3",
        "-I",
        str(REPLAYER_PATH),
        "--run-root",
        str(run_root),
        "--output",
        str(output),
    ]

    first = subprocess.run(argv, check=False, capture_output=True)
    second = subprocess.run(argv, check=False, capture_output=True)

    assert first.returncode == 0, first.stderr.decode()
    receipt = json.loads(output.read_bytes())
    assert receipt["schema"] == "w0_d6_replay_receipt_v1"
    assert receipt["producer_status"] == "UNKNOWN"
    assert receipt["conclusion"] is None
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
