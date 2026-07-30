from __future__ import annotations

from collections.abc import Callable
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
EXPECTED_PROJECT_LOCK_SHA256 = (
    "1f5c3ce3b843ae2fcc47177ad48ac1d8867746931bcce7a1799eb45e4b4c834e"
)
CLOSED_V2_PROFILE = "closed_v2"
SWAP_V3_PROFILE = "swap_v3"
PROTOCOL_COHORT = "w0_d6_swap_v3"
CLASS_ALLOCATION_PROFILE = "d6_6b_d9_6g_swap_v1"


def _protocol_identity() -> dict[str, str]:
    return {
        "cohort": PROTOCOL_COHORT,
        "class_allocation_profile": CLASS_ALLOCATION_PROFILE,
        "antecedent_schema": "w0_d6_antecedent_v2",
        "config_payload_schema": "w0_d6_run_config_v3",
        "receipt_payload_schema": "w0_d6_receipt_payload_v3",
        "replay_receipt_schema": "w0_d6_replay_receipt_v3",
        "project_lock_sha256": EXPECTED_PROJECT_LOCK_SHA256,
    }


def _authority_boundary() -> dict[str, object]:
    return {
        "artifact_status": "research_only_local_d6",
        "proves_whole_witness": False,
        "changes_lower_bound": False,
        "changes_upper_bound": False,
        "may_emit_cut_or_rejection": False,
        "production_authority": False,
        "certified_exact_source_authority": False,
        "frozen_or_sealed_input_mutation": False,
    }


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
def replayer() -> ModuleType:
    return _load_module("_test_w0_d6_replayer_contract", REPLAYER_PATH)


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
    python_executable: str | Path = "/usr/bin/python3",
) -> subprocess.CompletedProcess[bytes]:
    argv = [
        str(python_executable),
        "-I",
        "-B",
        str(run_root / "sources" / "replay_d6_certificate.py"),
        "--run-root",
        str(run_root),
    ]
    if output is not None:
        argv.extend(("--output", str(output)))
    return subprocess.run(argv, check=False, capture_output=True)


def _replay_command_from_source(
    run_root: Path,
    replayer_path: Path,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            str(replayer_path),
            "--run-root",
            str(run_root),
        ],
        check=False,
        capture_output=True,
    )


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
    profile: str = SWAP_V3_PROFILE,
) -> Path:
    if profile not in {CLOSED_V2_PROFILE, SWAP_V3_PROFILE}:
        raise AssertionError(f"unsupported synthetic protocol profile: {profile}")
    attachment_scope = (
        "seed_narrow"
        if profile == CLOSED_V2_PROFILE
        else "all_legal_d6_slots"
    )
    run_root = ExclusiveRunRoot.create(
        tmp_path / f"producer-{profile}-{status.lower()}"
    )
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
        attachment_scope="all_legal_d6_slots",
    )
    if profile == CLOSED_V2_PROFILE:
        antecedent = dict(antecedent)
        antecedent["schema"] = "w0_d6_antecedent_v1"
        antecedent.pop("protocol")
        antecedent.pop("class_transfer")
        antecedent.pop("class_ledger")
        antecedent["class_counts"] = {
            "3L": 7,
            "3O3": 3,
            "5L": 2,
            "5O2": 2,
            "6B": 1,
            "6G": 2,
        }
        antecedent["expected_totals"] = {
            "bodies": 17,
            "active_inputs": 25,
            "active_outputs": 25,
        }
        antecedent["attachment_scope"] = "seed_narrow"
        cycle = dict(antecedent["cycle"])
        cycle["attachment_slots"] = [
            {"cycle": [x, 29], "branch": [x, 30]}
            for x in (23, 24, 25, 30, 31, 32, 33, 34, 35, 36, 37)
        ]
        antecedent["cycle"] = cycle
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
    config_payload: dict[str, object] = {
            "schema": (
                "w0_d6_run_config_v2"
                if profile == CLOSED_V2_PROFILE
                else "w0_d6_run_config_v3"
            ),
            "attachment_scope": attachment_scope,
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
            "authority_boundary": _authority_boundary(),
            "replay": {"argv_template": replay_template},
    }
    if profile == SWAP_V3_PROFILE:
        config_payload["protocol"] = _protocol_identity()
    config = make_research_run_config(
        experiment_id="w0_power_cycle_domino_d6",
        payload=config_payload,
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
    receipt_payload: dict[str, object] = {
            "schema": (
                "w0_d6_receipt_payload_v2"
                if profile == CLOSED_V2_PROFILE
                else "w0_d6_receipt_payload_v3"
            ),
            "status": status,
            "attachment_scope": attachment_scope,
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
    }
    if profile == SWAP_V3_PROFILE:
        receipt_payload["protocol"] = _protocol_identity()
        receipt_payload["authority_boundary"] = _authority_boundary()
    receipt = make_research_run_receipt(
        experiment_id="w0_power_cycle_domino_d6",
        config_identity=config_identity,
        artifacts=artifacts,
        payload=receipt_payload,
    )
    run_root.write_json("receipt.json", receipt)
    verify_artifact_root_closure(
        run_root,
        artifact_root_manifest,
        receipt_present=True,
    )
    return run_root.path


def _rewrite_config_binding(
    run_root: Path,
    mutate_payload: Callable[[dict[str, object]], None],
) -> None:
    config_path = run_root / "config.json"
    receipt_path = run_root / "receipt.json"
    config = _decode_cli_json(config_path.read_bytes())
    payload = config["payload"]
    assert type(payload) is dict
    mutate_payload(payload)
    config_path.write_bytes(canonical_json_bytes(config))
    config_identity = read_stable_snapshot(config_path).identity

    receipt = _decode_cli_json(receipt_path.read_bytes())
    artifacts = receipt["artifacts"]
    receipt_payload = receipt["payload"]
    assert type(artifacts) is dict
    assert type(receipt_payload) is dict
    receipt["config_identity"] = config_identity.as_dict()
    artifacts["config"] = config_identity.as_dict()
    receipt_payload["identity_graph_sha256"] = replay_identity_graph(
        artifacts
    ).graph_sha256
    receipt_path.write_bytes(canonical_json_bytes(receipt))


def _rewrite_antecedent_binding(
    run_root: Path,
    mutate_antecedent: Callable[[dict[str, object]], None],
    *,
    receipt_status: object,
) -> None:
    antecedent_path = run_root / "antecedent.json"
    config_path = run_root / "config.json"
    receipt_path = run_root / "receipt.json"

    antecedent = _decode_cli_json(antecedent_path.read_bytes())
    mutate_antecedent(antecedent)
    antecedent_path.write_bytes(canonical_json_bytes(antecedent))
    antecedent_identity = read_stable_snapshot(antecedent_path).identity

    config = _decode_cli_json(config_path.read_bytes())
    config_payload = config["payload"]
    assert type(config_payload) is dict
    config_payload["antecedent"] = antecedent_identity.as_dict()
    config_path.write_bytes(canonical_json_bytes(config))
    config_identity = read_stable_snapshot(config_path).identity

    receipt = _decode_cli_json(receipt_path.read_bytes())
    artifacts = receipt["artifacts"]
    receipt_payload = receipt["payload"]
    assert type(artifacts) is dict
    assert type(receipt_payload) is dict
    receipt["config_identity"] = config_identity.as_dict()
    artifacts["config"] = config_identity.as_dict()
    artifacts["antecedent"] = antecedent_identity.as_dict()
    receipt_payload["antecedent_sha256"] = antecedent_identity.sha256
    receipt_payload["identity_graph_sha256"] = replay_identity_graph(
        artifacts
    ).graph_sha256
    receipt_payload["status"] = receipt_status
    receipt_path.write_bytes(canonical_json_bytes(receipt))


@pytest.mark.parametrize("status", ["UNKNOWN", "INFEASIBLE"])
@pytest.mark.parametrize("profile", [CLOSED_V2_PROFILE, SWAP_V3_PROFILE])
def test_independent_replay_accepts_only_the_exact_nonfeasible_receipt_scope(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
    status: str,
    profile: str,
) -> None:
    run_root = _make_run(
        tmp_path,
        gate,
        input_paths,
        status=status,
        profile=profile,
    )

    completed = _replay_command(run_root)
    assert completed.returncode == 0, completed.stderr.decode()
    replay = _decode_cli_json(completed.stdout)

    assert replay["status"] == "PASS"
    assert replay["producer_status"] == status
    assert replay["artifact_root"]["verified"] is True
    assert replay["antecedent_recomputation"]["verified"] is True
    assert replay["semantic_verification"] == {"performed": False, "summary": None}
    if profile == CLOSED_V2_PROFILE:
        assert replay["schema"] == "w0_d6_replay_receipt_v2"
        assert "protocol" not in replay
    else:
        assert replay["schema"] == "w0_d6_replay_receipt_v3"
        assert replay["protocol"] == _protocol_identity()
        assert replay["authority_boundary"] == _authority_boundary()
    if status == "UNKNOWN":
        assert replay["conclusion"] is None
    else:
        assert replay["conclusion"]["kind"] == "exact_d6_antecedent_infeasible_only"


def test_synthetic_fixture_accepts_only_two_atomic_profiles(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    with pytest.raises(AssertionError, match="unsupported synthetic protocol profile"):
        _make_run(
            tmp_path,
            gate,
            input_paths,
            status="UNKNOWN",
            profile="mixed_or_future",
        )
    assert list(tmp_path.iterdir()) == []


def test_replayer_rebuild_dispatches_profile_specific_active_totals(
    replayer: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    strict_instance = json.loads(input_paths["strict_instance"].read_bytes())
    framework = json.loads(input_paths["framework"].read_bytes())
    seed = json.loads(input_paths["seed"].read_bytes())
    closed_v2 = replayer.rebuild_d6_antecedent(
        strict_instance,
        framework,
        seed,
        protocol_profile=CLOSED_V2_PROFILE,
        attachment_scope="seed_narrow",
    )
    swap_v3 = replayer.rebuild_d6_antecedent(
        strict_instance,
        framework,
        seed,
        protocol_profile=SWAP_V3_PROFILE,
        attachment_scope="all_legal_d6_slots",
    )

    assert closed_v2["schema"] == "w0_d6_antecedent_v1"
    assert closed_v2["expected_totals"] == {
        "bodies": 17,
        "active_inputs": 25,
        "active_outputs": 25,
    }
    assert swap_v3["schema"] == "w0_d6_antecedent_v2"
    assert swap_v3["protocol"] == _protocol_identity()
    assert swap_v3["expected_totals"] == {
        "bodies": 17,
        "active_inputs": 23,
        "active_outputs": 25,
    }

    forged = json.loads(json.dumps(swap_v3))
    forged["expected_totals"]["active_inputs"] = 25
    with pytest.raises(replayer.ReplayError) as exc_info:
        replayer._parse_antecedent(
            forged,
            protocol_profile=SWAP_V3_PROFILE,
        )
    assert exc_info.value.code == "ANTECEDENT_D6_DRIFT"


def test_v3_rebuild_rejects_insufficient_strict_6g_supply(
    replayer: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    strict_instance = json.loads(input_paths["strict_instance"].read_bytes())
    framework = json.loads(input_paths["framework"].read_bytes())
    seed = json.loads(input_paths["seed"].read_bytes())
    matching = []
    for group in strict_instance["operation_groups"]:
        inputs = sum(group["port_needs"]["inputs"].values())
        outputs = sum(group["port_needs"]["outputs"].values())
        if (
            group["template"] == "manufacturing_6x4"
            and inputs == 3
            and outputs == 1
        ):
            matching.append(group)
    assert len(matching) == 3
    strict_instance["operation_groups"].remove(matching[0])
    for group in matching[1:]:
        group["count"] = 1

    with pytest.raises(replayer.ReplayError) as exc_info:
        replayer.rebuild_d6_antecedent(
            strict_instance,
            framework,
            seed,
            protocol_profile=SWAP_V3_PROFILE,
            attachment_scope="all_legal_d6_slots",
        )
    assert exc_info.value.code == "ANTECEDENT_INPUT_INVALID"


def test_v3_rebuild_rejects_non_d6_d9_allocation_drift(
    replayer: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    strict_instance = json.loads(input_paths["strict_instance"].read_bytes())
    framework = json.loads(input_paths["framework"].read_bytes())
    seed = json.loads(input_paths["seed"].read_bytes())
    framework["macrocell_class_allocation_seed"]["D1"]["3L"] += 1

    with pytest.raises(replayer.ReplayError) as exc_info:
        replayer.rebuild_d6_antecedent(
            strict_instance,
            framework,
            seed,
            protocol_profile=SWAP_V3_PROFILE,
            attachment_scope="all_legal_d6_slots",
        )
    assert exc_info.value.code == "ANTECEDENT_INPUT_INVALID"


@pytest.mark.parametrize("receipt_profile", [CLOSED_V2_PROFILE, SWAP_V3_PROFILE])
def test_config_and_receipt_protocol_rows_cannot_be_mixed(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
    receipt_profile: str,
) -> None:
    run_root = _make_run(
        tmp_path,
        gate,
        input_paths,
        status="UNKNOWN",
        profile=receipt_profile,
    )

    def cross_row(payload: dict[str, object]) -> None:
        if receipt_profile == SWAP_V3_PROFILE:
            payload["schema"] = "w0_d6_run_config_v2"
            payload.pop("protocol")
        else:
            payload["schema"] = "w0_d6_run_config_v3"
            payload["protocol"] = _protocol_identity()

    _rewrite_config_binding(run_root, cross_row)
    completed = _replay_command(run_root)

    assert completed.returncode == 2
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] == "ARTIFACT_PROTOCOL_COHORT_MISMATCH"
    assert error["conclusion"] is None

    missing_manifest_root = tmp_path / "receipt-missing-manifest"
    missing_manifest_root.mkdir()
    missing_manifest_run_root = _make_run(
        missing_manifest_root,
        gate,
        input_paths,
        status="UNKNOWN",
        profile=receipt_profile,
    )
    missing_manifest_receipt_path = missing_manifest_run_root / "receipt.json"
    missing_manifest_receipt = _decode_cli_json(
        missing_manifest_receipt_path.read_bytes()
    )
    missing_manifest_payload = missing_manifest_receipt["payload"]
    assert type(missing_manifest_payload) is dict
    missing_manifest_payload.pop("artifact_root_manifest")
    missing_manifest_payload["status"] = "STATUS_MUST_NOT_BE_INTERPRETED"
    missing_manifest_receipt_path.write_bytes(
        canonical_json_bytes(missing_manifest_receipt)
    )

    missing_manifest_completed = _replay_command(missing_manifest_run_root)

    assert missing_manifest_completed.returncode == 2
    missing_manifest_error = _decode_cli_json(missing_manifest_completed.stderr)
    assert missing_manifest_error["error_code"] == (
        "ARTIFACT_PROTOCOL_COHORT_MISMATCH"
    )
    assert missing_manifest_error["conclusion"] is None

    if receipt_profile == CLOSED_V2_PROFILE:
        for case_name, mutation in (
            (
                "config-unknown-extra-field",
                lambda payload: payload.__setitem__(
                    "unexpected_cohort_field",
                    "must fail as a cohort mismatch",
                ),
            ),
            (
                "config-missing-required-field",
                lambda payload: payload.__delitem__("replay"),
            ),
        ):
            case_root = tmp_path / case_name
            case_root.mkdir()
            contaminated_run_root = _make_run(
                case_root,
                gate,
                input_paths,
                status="UNKNOWN",
                profile=CLOSED_V2_PROFILE,
            )
            _rewrite_config_binding(contaminated_run_root, mutation)
            receipt_path = contaminated_run_root / "receipt.json"
            receipt = _decode_cli_json(receipt_path.read_bytes())
            receipt_payload = receipt["payload"]
            assert type(receipt_payload) is dict
            receipt_payload["status"] = "STATUS_MUST_NOT_BE_INTERPRETED"
            receipt_path.write_bytes(canonical_json_bytes(receipt))

            contaminated_completed = _replay_command(contaminated_run_root)

            assert contaminated_completed.returncode == 2
            contaminated_error = _decode_cli_json(contaminated_completed.stderr)
            assert contaminated_error["error_code"] == (
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH"
            )
            assert contaminated_error["conclusion"] is None

        def add_v3_authority_boundary(payload: dict[str, object]) -> None:
            payload["authority_boundary"] = _authority_boundary()

        def add_unknown_field(payload: dict[str, object]) -> None:
            payload["unexpected_cohort_field"] = "must fail as a cohort mismatch"

        def remove_required_field(payload: dict[str, object]) -> None:
            payload.pop("replay")

        for case_name, mutation in (
            ("v3-authority-boundary", add_v3_authority_boundary),
            ("unknown-extra-field", add_unknown_field),
            ("missing-required-field", remove_required_field),
        ):
            case_root = tmp_path / case_name
            case_root.mkdir()
            contaminated_run_root = _make_run(
                case_root,
                gate,
                input_paths,
                status="UNKNOWN",
                profile=CLOSED_V2_PROFILE,
            )
            receipt_path = contaminated_run_root / "receipt.json"
            receipt = _decode_cli_json(receipt_path.read_bytes())
            receipt_payload = receipt["payload"]
            assert type(receipt_payload) is dict
            mutation(receipt_payload)
            receipt_payload["status"] = "STATUS_MUST_NOT_BE_INTERPRETED"
            receipt_path.write_bytes(canonical_json_bytes(receipt))

            contaminated_completed = _replay_command(contaminated_run_root)

            assert contaminated_completed.returncode == 2
            contaminated_error = _decode_cli_json(contaminated_completed.stderr)
            assert contaminated_error["error_code"] == (
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH"
            )
            assert contaminated_error["conclusion"] is None
        return

    def remove_transfer(antecedent: dict[str, object]) -> None:
        antecedent.pop("class_transfer")

    def remove_ledger(antecedent: dict[str, object]) -> None:
        antecedent.pop("class_ledger")

    def select_closed_v2_antecedent_row(antecedent: dict[str, object]) -> None:
        antecedent["schema"] = "w0_d6_antecedent_v1"
        antecedent.pop("protocol")
        antecedent.pop("class_transfer")
        antecedent.pop("class_ledger")

    for case_name, mutation in (
        ("missing-transfer", remove_transfer),
        ("missing-ledger", remove_ledger),
        ("cross-row", select_closed_v2_antecedent_row),
    ):
        case_root = tmp_path / case_name
        case_root.mkdir()
        partial_run_root = _make_run(
            case_root,
            gate,
            input_paths,
            status="UNKNOWN",
            profile=SWAP_V3_PROFILE,
        )
        _rewrite_antecedent_binding(
            partial_run_root,
            mutation,
            receipt_status="STATUS_MUST_NOT_BE_INTERPRETED",
        )

        partial_completed = _replay_command(partial_run_root)

        assert partial_completed.returncode == 2
        partial_error = _decode_cli_json(partial_completed.stderr)
        assert partial_error["error_code"] == "ARTIFACT_PROTOCOL_COHORT_MISMATCH"
        assert partial_error["conclusion"] is None


@pytest.mark.parametrize(
    "field",
    [
        "proves_whole_witness",
        "changes_lower_bound",
        "changes_upper_bound",
        "may_emit_cut_or_rejection",
        "production_authority",
        "certified_exact_source_authority",
        "frozen_or_sealed_input_mutation",
    ],
)
def test_v3_receipt_rejects_any_authority_boolean_flip(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
    field: str,
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    receipt_path = run_root / "receipt.json"
    receipt = _decode_cli_json(receipt_path.read_bytes())
    payload = receipt["payload"]
    assert type(payload) is dict
    authority = payload["authority_boundary"]
    assert type(authority) is dict
    authority[field] = True
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    completed = _replay_command(run_root)

    assert completed.returncode == 2
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] == "AUTHORITY_BOUNDARY_INVALID"
    assert error["conclusion"] is None


@pytest.mark.parametrize("location", ["config", "receipt"])
def test_v3_authority_boundary_is_mandatory(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
    location: str,
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    if location == "config":
        _rewrite_config_binding(
            run_root,
            lambda payload: payload.__delitem__("authority_boundary"),
        )
    else:
        receipt_path = run_root / "receipt.json"
        receipt = _decode_cli_json(receipt_path.read_bytes())
        payload = receipt["payload"]
        assert type(payload) is dict
        payload.pop("authority_boundary")
        receipt_path.write_bytes(canonical_json_bytes(receipt))

    completed = _replay_command(run_root)

    assert completed.returncode == 2
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] == "ARTIFACT_PROTOCOL_COHORT_MISMATCH"
    assert error["conclusion"] is None


def test_real_closed_v2_evidence_must_use_its_root_pinned_replayer(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(
        tmp_path,
        gate,
        input_paths,
        status="UNKNOWN",
        profile=CLOSED_V2_PROFILE,
    )

    completed = _replay_command_from_source(run_root, REPLAYER_PATH)

    assert completed.returncode == 2
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] == "REPLAYER_SOURCE_MISMATCH"
    assert error["conclusion"] is None


def test_byte_tamper_fails_before_any_local_conclusion(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(
        tmp_path,
        gate,
        input_paths,
        status="UNKNOWN",
        profile=CLOSED_V2_PROFILE,
    )
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
        "ARTIFACT_OPEN_FAILED",
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
    run_root = _make_run(
        tmp_path,
        gate,
        input_paths,
        status="UNKNOWN",
        profile=CLOSED_V2_PROFILE,
    )
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
            "--protocol-cohort",
            PROTOCOL_COHORT,
            "--class-allocation-profile",
            CLASS_ALLOCATION_PROFILE,
            "--attachment-scope",
            "all_legal_d6_slots",
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
        "    '--protocol-cohort', 'w0_d6_swap_v3',\n"
        "    '--class-allocation-profile', 'd6_6b_d9_6g_swap_v1',\n"
        "    '--attachment-scope', 'all_legal_d6_slots',\n"
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
        "snapshot = runner.read_stable_snapshot(pathlib.Path(sys.argv[2]))\n"
        "runner._load_gate_module(snapshot)\n",
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


def test_gate_loader_executes_stable_snapshot_bytes_after_path_swap(
    tmp_path: Path,
    runner: ModuleType,
) -> None:
    copied_gate = tmp_path / "d6_joint_completion_gate.py"
    copied_gate.write_bytes(GATE_PATH.read_bytes())
    snapshot = read_stable_snapshot(copied_gate)
    copied_gate.write_text(
        "raise RuntimeError('swapped gate path was executed')\n",
        encoding="utf-8",
    )

    module = runner._load_gate_module(snapshot)

    assert callable(module.build_d6_antecedent)
    assert module.ANTECEDENT_SCHEMA == "w0_d6_antecedent_v2"


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
    coherent_output = tmp_path / "replay-coherent" / "replay_receipt.json"
    heterogeneous_output = tmp_path / "replay-stdlib" / "replay_receipt.json"
    coherent_output.parent.mkdir()
    heterogeneous_output.parent.mkdir()
    root_tree_before = _artifact_tree_snapshot(run_root)
    coherent = _replay_command(
        run_root,
        output=coherent_output,
        python_executable=sys.executable,
    )
    heterogeneous = _replay_command(run_root, output=heterogeneous_output)
    second = _replay_command(run_root, output=coherent_output)

    assert coherent.returncode == 0, coherent.stderr.decode()
    assert heterogeneous.returncode == 0, heterogeneous.stderr.decode()
    assert coherent_output.read_bytes() == heterogeneous_output.read_bytes()
    assert hashlib.sha256(coherent_output.read_bytes()).digest() == hashlib.sha256(
        heterogeneous_output.read_bytes()
    ).digest()
    receipt = json.loads(coherent_output.read_bytes())
    assert receipt["schema"] == "w0_d6_replay_receipt_v3"
    assert receipt["protocol"] == _protocol_identity()
    assert receipt["authority_boundary"] == _authority_boundary()
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
    assert canonical_json_bytes(receipt) == coherent_output.read_bytes()
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


@pytest.mark.parametrize(
    ("pollution_kind", "relative_marker"),
    [
        ("regular_file", "late-regular-file"),
        ("directory", "late-directory"),
        ("symlink", "late-symlink"),
        ("fifo", "late-fifo"),
        ("pyc", "__pycache__/late.cpython-999.pyc"),
    ],
)
def test_stdlib_walker_rejects_persistent_injection_into_completed_sibling(
    tmp_path: Path,
    pollution_kind: str,
    relative_marker: str,
) -> None:
    artifact_root = tmp_path / f"walker-race-{pollution_kind}"
    early = artifact_root / "aaa-completed-early"
    trigger = artifact_root / "zzz-scanned-later"
    early.mkdir(parents=True)
    trigger.mkdir()
    (early / "original.txt").write_bytes(b"early")
    (trigger / "original.txt").write_bytes(b"later")
    probe = tmp_path / f"walker_race_probe_{pollution_kind}.py"
    probe.write_text(
        """\
import importlib.util
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("_walker_race_replayer", sys.argv[1])
assert spec is not None and spec.loader is not None
replayer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = replayer
spec.loader.exec_module(replayer)

artifact_root = Path(sys.argv[2])
early = artifact_root / "aaa-completed-early"
trigger = artifact_root / "zzz-scanned-later"
pollution_kind = sys.argv[3]
real_scandir = os.scandir
injected = False

def attacked_scandir(path):
    global injected
    if isinstance(path, int):
        scanned_path = Path(os.readlink(f"/proc/self/fd/{path}"))
    else:
        scanned_path = Path(path)
    if not injected and scanned_path == trigger:
        if pollution_kind == "regular_file":
            (early / "late-regular-file").write_bytes(b"persistent")
        elif pollution_kind == "directory":
            (early / "late-directory").mkdir()
        elif pollution_kind == "symlink":
            (early / "late-symlink").symlink_to(early / "original.txt")
        elif pollution_kind == "fifo":
            os.mkfifo(early / "late-fifo")
        elif pollution_kind == "pyc":
            cache = early / "__pycache__"
            cache.mkdir()
            (cache / "late.cpython-999.pyc").write_bytes(b"persistent bytecode")
        else:
            raise AssertionError(pollution_kind)
        injected = True
    return real_scandir(path)

replayer.os.scandir = attacked_scandir
try:
    replayer._artifact_root_entries(artifact_root)
except replayer.ReplayError as exc:
    if not injected:
        raise AssertionError("walker rejected before deterministic injection")
    sys.stderr.buffer.write(
        replayer.canonical_json_bytes(
            {
                "status": "ERROR",
                "error_code": exc.code,
                "conclusion": None,
            }
        )
    )
    raise SystemExit(2)
if not injected:
    raise AssertionError("deterministic injection hook was not reached")
sys.stdout.buffer.write(
    replayer.canonical_json_bytes(
        {
            "status": "ACCEPTED",
            "conclusion": None,
        }
    )
)
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            str(probe),
            str(REPLAYER_PATH),
            str(artifact_root),
            pollution_kind,
        ],
        env={},
        check=False,
        capture_output=True,
    )

    assert os.path.lexists(early / relative_marker), "the injected node must persist"
    assert completed.returncode == 2, completed.stdout.decode()
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] in {
        "ARTIFACT_ROOT_CHANGED",
        "ARTIFACT_ROOT_CLOSURE_MISMATCH",
        "ARTIFACT_ROOT_SYMLINK_REJECTED",
        "ARTIFACT_ROOT_SPECIAL_NODE_REJECTED",
    }
    assert error["conclusion"] is None


def test_artifact_root_ancestor_swap_between_precheck_and_open_is_rejected(
    tmp_path: Path,
) -> None:
    switch_parent = tmp_path / "ancestor-swap"
    live_ancestor = switch_parent / "live"
    external_ancestor = switch_parent / "external"
    artifact_root = live_ancestor / "run"
    artifact_root.mkdir(parents=True)
    (artifact_root / "artifact.txt").write_bytes(b"same inode after relocation")
    probe = tmp_path / "ancestor_swap_probe.py"
    probe.write_text(
        """\
import importlib.util
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("_ancestor_swap_replayer", sys.argv[1])
assert spec is not None and spec.loader is not None
replayer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = replayer
spec.loader.exec_module(replayer)

artifact_root = Path(sys.argv[2])
live_ancestor = Path(sys.argv[3])
external_ancestor = Path(sys.argv[4])
expected_root_signature = replayer._stat_signature(os.lstat(artifact_root))
real_open = os.open
swapped = False

def attacked_open(path, flags, mode=0o777, *, dir_fd=None):
    global swapped
    old_full_path_open = (
        dir_fd is None
        and Path(os.path.abspath(os.fspath(path))) == artifact_root
    )
    component_open = (
        dir_fd is not None
        and os.fspath(path) == live_ancestor.name
    )
    if not swapped and (old_full_path_open or component_open):
        os.rename(live_ancestor, external_ancestor)
        os.symlink(
            str(external_ancestor),
            str(live_ancestor),
            target_is_directory=True,
        )
        swapped = True
    return real_open(path, flags, mode, dir_fd=dir_fd)

replayer.os.open = attacked_open
try:
    replayer._artifact_root_entries(
        artifact_root,
        expected_root_signature=expected_root_signature,
    )
except replayer.ReplayError as exc:
    if not swapped:
        raise AssertionError("root walker rejected before deterministic ancestor swap")
    sys.stderr.buffer.write(
        replayer.canonical_json_bytes(
            {
                "status": "ERROR",
                "error_code": exc.code,
                "conclusion": None,
            }
        )
    )
    raise SystemExit(2)
if not swapped:
    raise AssertionError("deterministic ancestor-swap hook was not reached")
sys.stdout.buffer.write(
    replayer.canonical_json_bytes(
        {
            "status": "ACCEPTED",
            "conclusion": None,
        }
    )
)
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            str(probe),
            str(REPLAYER_PATH),
            str(artifact_root),
            str(live_ancestor),
            str(external_ancestor),
        ],
        env={},
        check=False,
        capture_output=True,
    )

    assert live_ancestor.is_symlink(), "the swapped ancestor must remain a symlink"
    assert (external_ancestor / "run" / "artifact.txt").read_bytes() == (
        b"same inode after relocation"
    )
    assert completed.returncode == 2, completed.stdout.decode()
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] in {
        "ARTIFACT_ROOT_OPEN_FAILED",
        "ARTIFACT_ROOT_CHANGED",
        "SYMLINK_REJECTED",
    }
    assert error["conclusion"] is None


@pytest.mark.parametrize(
    "fault_mode",
    ["oserror", "runtimeerror", "runtimeerror_close_failure"],
)
def test_stdlib_replayer_root_fstat_failure_is_stable_and_fd_neutral(
    tmp_path: Path,
    fault_mode: str,
) -> None:
    artifact_root = tmp_path / f"root-fstat-failure-{fault_mode}"
    artifact_root.mkdir()
    probe = tmp_path / f"root_fstat_failure_probe_{fault_mode}.py"
    probe.write_text(
        """\
import errno
import importlib.util
import json
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("_root_fstat_failure_replayer", sys.argv[1])
assert spec is not None and spec.loader is not None
replayer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = replayer
spec.loader.exec_module(replayer)

artifact_root = Path(sys.argv[2])
fault_mode = sys.argv[3]
real_fstat = os.fstat
real_close = os.close
fault_count = 0
close_count = 0
target_descriptor = None
injected_runtime_error = RuntimeError("injected artifact-root fstat failure")

def failing_fstat(descriptor):
    global fault_count, target_descriptor
    try:
        descriptor_target = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
    except OSError:
        descriptor_target = None
    if fault_count == 0 and descriptor_target == artifact_root:
        fault_count += 1
        target_descriptor = descriptor
        if fault_mode == "oserror":
            raise OSError(errno.EIO, "injected artifact-root fstat failure")
        raise injected_runtime_error
    return real_fstat(descriptor)

def tracking_close(descriptor):
    global close_count
    if descriptor == target_descriptor:
        close_count += 1
        if fault_mode == "runtimeerror_close_failure":
            raise OSError(errno.EIO, "injected descriptor close failure")
    real_close(descriptor)

before = len(os.listdir("/proc/self/fd"))
replayer.os.fstat = failing_fstat
replayer.os.close = tracking_close
try:
    return_code = replayer.main(["--run-root", str(artifact_root)])
finally:
    replayer.os.fstat = real_fstat
    replayer.os.close = real_close
delta_before_manual_cleanup = len(os.listdir("/proc/self/fd")) - before
if fault_mode == "runtimeerror_close_failure" and target_descriptor is not None:
    real_close(target_descriptor)
fd_delta = len(os.listdir("/proc/self/fd")) - before

sys.stdout.write(
    json.dumps(
        {
            "close_count": close_count,
            "delta_before_manual_cleanup": delta_before_manual_cleanup,
            "fault_count": fault_count,
            "fd_delta": fd_delta,
            "runtime_error_notes": getattr(
                injected_runtime_error,
                "__notes__",
                [],
            ),
            "return_code": return_code,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
)
raise SystemExit(return_code)
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            str(probe),
            str(REPLAYER_PATH),
            str(artifact_root),
            fault_mode,
        ],
        env={},
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 2, completed.stdout.decode()
    error = _decode_cli_json(completed.stderr)
    if fault_mode == "oserror":
        assert error["error_code"] == "ARTIFACT_ROOT_OPEN_FAILED"
    else:
        assert error["error_code"] == "INTERNAL_REPLAY_ERROR"
        assert error["detail"] == (
            "RuntimeError: injected artifact-root fstat failure"
        )
    assert error["conclusion"] is None
    result = _decode_cli_json(completed.stdout)
    expected_delta_before_cleanup = (
        1 if fault_mode == "runtimeerror_close_failure" else 0
    )
    assert result == {
        "close_count": 1,
        "delta_before_manual_cleanup": expected_delta_before_cleanup,
        "fault_count": 1,
        "fd_delta": 0,
        "runtime_error_notes": (
            [
                (
                    "descriptor close failed: OSError: "
                    "[Errno 5] injected descriptor close failure"
                )
            ]
            if fault_mode == "runtimeerror_close_failure"
            else []
        ),
        "return_code": 2,
    }


@pytest.mark.parametrize(
    "fault_site",
    ["child_fstat", "root_finalization_signature"],
)
def test_stdlib_replayer_closure_runtime_errors_are_fd_neutral(
    tmp_path: Path,
    fault_site: str,
) -> None:
    artifact_root = tmp_path / f"closure-runtime-{fault_site}"
    artifact_root.mkdir()
    if fault_site == "child_fstat":
        (artifact_root / "child").mkdir()
    probe = tmp_path / f"closure_runtime_probe_{fault_site}.py"
    probe.write_text(
        """\
import importlib.util
import json
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("_closure_runtime_replayer", sys.argv[1])
assert spec is not None and spec.loader is not None
replayer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = replayer
spec.loader.exec_module(replayer)

artifact_root = Path(sys.argv[2])
fault_site = sys.argv[3]
target_path = artifact_root / "child" if fault_site == "child_fstat" else artifact_root
real_fstat = os.fstat
real_close = os.close
real_signature = replayer._stat_signature
target_descriptor = None
target_fstat_calls = 0
signature_calls = 0
fault_count = 0
close_count = 0
injected = RuntimeError(f"injected closure {fault_site} failure")

def descriptor_path(descriptor):
    try:
        return Path(os.readlink(f"/proc/self/fd/{descriptor}"))
    except OSError:
        return None

def failing_fstat(descriptor):
    global fault_count, target_descriptor, target_fstat_calls
    if descriptor_path(descriptor) == target_path:
        target_descriptor = descriptor
        target_fstat_calls += 1
        if fault_site == "child_fstat" and fault_count == 0:
            fault_count += 1
            raise injected
    return real_fstat(descriptor)

def failing_signature(item):
    global fault_count, signature_calls
    signature_calls += 1
    if (
        fault_site == "root_finalization_signature"
        and signature_calls == 2
        and fault_count == 0
    ):
        fault_count += 1
        raise injected
    return real_signature(item)

def tracking_close(descriptor):
    global close_count
    if descriptor == target_descriptor:
        close_count += 1
    real_close(descriptor)

before = len(os.listdir("/proc/self/fd"))
replayer.os.fstat = failing_fstat
replayer.os.close = tracking_close
replayer._stat_signature = failing_signature
try:
    try:
        replayer._artifact_root_entries(artifact_root)
    except RuntimeError as exc:
        if exc is not injected:
            raise
    else:
        raise AssertionError("deterministic closure fault was not raised")
finally:
    replayer.os.fstat = real_fstat
    replayer.os.close = real_close
    replayer._stat_signature = real_signature
after = len(os.listdir("/proc/self/fd"))

sys.stdout.write(
    json.dumps(
        {
            "close_count": close_count,
            "fault_count": fault_count,
            "fd_delta": after - before,
            "target_fstat_calls": target_fstat_calls,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
)
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            str(probe),
            str(REPLAYER_PATH),
            str(artifact_root),
            fault_site,
        ],
        env={},
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr.decode()
    result = _decode_cli_json(completed.stdout)
    assert result["close_count"] == 1
    assert result["fault_count"] == 1
    assert result["fd_delta"] == 0
    assert result["target_fstat_calls"] == (
        1 if fault_site == "child_fstat" else 2
    )


def test_fixed_artifact_labels_reject_a_coherently_relocated_byte_graph(
    tmp_path: Path,
    gate: ModuleType,
    input_paths: dict[str, Path],
) -> None:
    run_root = _make_run(tmp_path, gate, input_paths, status="UNKNOWN")
    receipt_path = run_root / "receipt.json"
    config_path = run_root / "config.json"
    receipt = _decode_cli_json(receipt_path.read_bytes())
    config = _decode_cli_json(config_path.read_bytes())
    raw_artifacts = receipt["artifacts"]
    assert type(raw_artifacts) is dict
    relocated_relative_paths = {
        "antecedent": "relocated-antecedent.json",
        "result": "relocated-result.json",
        "inputs.strict_instance": "inputs/relocated-strict-instance.json",
        "inputs.framework": "inputs/relocated-framework.json",
        "inputs.seed": "inputs/relocated-seed.json",
        "sources.runner": "sources/relocated-runner.py",
        "sources.gate": "sources/relocated-gate.py",
        "sources.replayer": "sources/relocated-replayer.py",
        "sources.common_contract": "sources/relocated-common-contract.py",
    }
    original_content_identities = {
        label: (
            raw_artifacts[label]["sha256"],
            raw_artifacts[label]["size_bytes"],
        )
        for label in relocated_relative_paths
    }
    old_to_new_relative: dict[str, str] = {}
    relocated_paths: dict[str, Path] = {}
    for label, new_relative in relocated_relative_paths.items():
        identity = raw_artifacts[label]
        assert type(identity) is dict
        old_path = Path(identity["path"])
        old_relative = old_path.relative_to(run_root).as_posix()
        new_path = run_root / new_relative
        old_path.rename(new_path)
        old_to_new_relative[old_relative] = new_relative
        relocated_paths[label] = new_path

    config_payload = config["payload"]
    assert type(config_payload) is dict
    config_inputs = config_payload["inputs"]
    config_sources = config_payload["sources"]
    assert type(config_inputs) is dict
    assert type(config_sources) is dict
    for name in ("strict_instance", "framework", "seed"):
        label = f"inputs.{name}"
        pair = config_inputs[name]
        assert type(pair) is dict
        pair["run_copy"] = read_stable_snapshot(
            relocated_paths[label]
        ).identity.as_dict()
    for name in ("runner", "gate", "replayer", "common_contract"):
        label = f"sources.{name}"
        pair = config_sources[name]
        assert type(pair) is dict
        pair["run_copy"] = read_stable_snapshot(
            relocated_paths[label]
        ).identity.as_dict()
    config_payload["antecedent"] = read_stable_snapshot(
        relocated_paths["antecedent"]
    ).identity.as_dict()
    replay_template = [
        "<python3>",
        "-I",
        "-B",
        str(relocated_paths["sources.replayer"]),
        "--run-root",
        str(run_root),
    ]
    config_replay = config_payload["replay"]
    assert type(config_replay) is dict
    config_replay["argv_template"] = replay_template
    config_path.write_bytes(canonical_json_bytes(config))

    actual_paths = {
        "config": config_path,
        **relocated_paths,
    }
    actual_identities = {
        label: read_stable_snapshot(path).identity
        for label, path in actual_paths.items()
    }
    receipt["config_identity"] = actual_identities["config"].as_dict()
    receipt["artifacts"] = {
        label: actual_identities[label].as_dict()
        for label in sorted(actual_identities)
    }
    receipt_payload = receipt["payload"]
    assert type(receipt_payload) is dict
    receipt_replay = receipt_payload["replay"]
    assert type(receipt_replay) is dict
    receipt_replay["argv_template"] = replay_template
    manifest = receipt_payload["artifact_root_manifest"]
    assert type(manifest) is dict
    entries = manifest["entries"]
    assert type(entries) is list
    for entry in entries:
        assert type(entry) is dict
        path = entry["path"]
        if path in old_to_new_relative:
            entry["path"] = old_to_new_relative[path]
    entries.sort(key=lambda entry: entry["path"])
    receipt_payload["identity_graph_sha256"] = replay_identity_graph(
        actual_identities
    ).graph_sha256
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    for label, expected_content_identity in original_content_identities.items():
        observed = read_stable_snapshot(relocated_paths[label]).identity
        assert (observed.sha256, observed.size_bytes) == expected_content_identity
    manifest_regular_paths = {
        entry["path"]
        for entry in entries
        if entry["type"] == "regular_file"
    }
    artifact_relative_paths = {
        Path(identity.path).relative_to(run_root).as_posix()
        for identity in actual_identities.values()
    }
    assert artifact_relative_paths == manifest_regular_paths
    verify_artifact_root_closure(
        run_root,
        manifest,
        receipt_present=True,
    )

    completed = _replay_command_from_source(
        run_root,
        relocated_paths["sources.replayer"],
    )

    assert completed.returncode == 2, completed.stdout.decode()
    error = _decode_cli_json(completed.stderr)
    assert error["error_code"] == "ARTIFACT_FIXED_PATH_MISMATCH"
    assert error["conclusion"] is None
