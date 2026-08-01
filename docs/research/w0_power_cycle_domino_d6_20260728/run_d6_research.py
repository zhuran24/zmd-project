#!/usr/bin/env python3
"""Run the research-only W0 D6 local joint-completion experiment.

The runner accepts only hash-pinned input bytes, creates one exclusive ignored
run root, and writes a receipt last.  It does not publish a witness, a cut, a
bound, or any production/certified-exact authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import hashlib
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
from types import ModuleType
from typing import Any, NoReturn, cast


SCRIPT_PATH = Path(__file__).resolve()
RESEARCH_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = SCRIPT_PATH.parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devtools.research_run_contract import (  # noqa: E402
    ArtifactIdentity,
    ExclusiveRunRoot,
    ResearchRunContractError,
    StableSnapshot,
    build_artifact_root_manifest,
    canonical_json_bytes,
    make_research_run_config,
    make_research_run_receipt,
    read_stable_snapshot,
    replay_identity_graph,
    require_isolated_python_process,
    verify_artifact_root_closure,
)
from src.io.strict_json import loads_strict_json  # noqa: E402


EXPERIMENT_ID = "w0_power_cycle_domino_d6"
STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
FRAMEWORK_SHA256 = "db6046cf598f9b5738b7f8950c91ea31834e8214e7e07995175b71eb04bdbb89"
SEED_SHA256 = "18c72669105f486bf54a2665bd74d1ff952ce2eeb39b28a7b30d5ce8d5d2f5f1"
EXPECTED_PROJECT_LOCK_SHA256 = (
    "a2ec971f687c04966e8329868b4eab05aaa3c9fd9ad71a96f0ab79df85b92559"
)
REJECTED_PRODUCER_SOURCE_SHA256 = (
    "295bfef9b2681193e3a9cc085c479a960f87de0131abfbdfacb676479bdb2aa5"
)
PROTOCOL_COHORT = "w0_d6_swap_v3"
CLASS_ALLOCATION_PROFILE = "d6_6b_d9_6g_swap_v1"
ANTECEDENT_SCHEMA = "w0_d6_antecedent_v2"
CONFIG_PAYLOAD_SCHEMA = "w0_d6_run_config_v3"
RECEIPT_PAYLOAD_SCHEMA = "w0_d6_receipt_payload_v3"
REPLAY_RECEIPT_SCHEMA = "w0_d6_replay_receipt_v3"

GATE_PATH = RESEARCH_DIR / "d6_joint_completion_gate.py"
REPLAYER_PATH = RESEARCH_DIR / "replay_d6_certificate.py"
COMMON_CONTRACT_PATH = PROJECT_ROOT / "devtools" / "research_run_contract.py"
PROJECT_LOCK_PATH = PROJECT_ROOT / "PROJECT_LOCK.md"
IGNORED_RUN_PARENT = PROJECT_ROOT / ".artifacts" / "research_runs"

MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_SOURCE_BYTES = 16 * 1024 * 1024

_SOURCE_PATHS: Mapping[str, Path] = {
    "runner": SCRIPT_PATH,
    "gate": GATE_PATH,
    "replayer": REPLAYER_PATH,
    "common_contract": COMMON_CONTRACT_PATH,
}
_INPUT_COPY_PATHS: Mapping[str, str] = {
    "strict_instance": "inputs/strict_instance.json",
    "framework": "inputs/framework.json",
    "seed": "inputs/seed.json",
}
_SOURCE_COPY_PATHS: Mapping[str, str] = {
    "runner": "sources/run_d6_research.py",
    "gate": "sources/d6_joint_completion_gate.py",
    "replayer": "sources/replay_d6_certificate.py",
    "common_contract": "sources/research_run_contract.py",
}


class D6RunnerError(RuntimeError):
    """Fail-closed runner contract failure."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise D6RunnerError(code, detail)


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _protocol_identity() -> dict[str, str]:
    return {
        "cohort": PROTOCOL_COHORT,
        "class_allocation_profile": CLASS_ALLOCATION_PROFILE,
        "antecedent_schema": ANTECEDENT_SCHEMA,
        "config_payload_schema": CONFIG_PAYLOAD_SCHEMA,
        "receipt_payload_schema": RECEIPT_PAYLOAD_SCHEMA,
        "replay_receipt_schema": REPLAY_RECEIPT_SCHEMA,
        "project_lock_sha256": EXPECTED_PROJECT_LOCK_SHA256,
    }


def _run_git(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
        shell=False,
        close_fds=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        _fail("GIT_QUERY_FAILED", f"git {' '.join(arguments)}: {detail}")
    return completed.stdout


def _git_identity() -> dict[str, object]:
    observed_root = _absolute(_run_git(("rev-parse", "--show-toplevel")).strip())
    if observed_root != PROJECT_ROOT:
        _fail("PROJECT_ROOT_MISMATCH", f"{observed_root} != {PROJECT_ROOT}")
    head = _run_git(("rev-parse", "--verify", "HEAD")).strip()
    status_text = _run_git(
        ("status", "--porcelain=v1", "--untracked-files=all")
    )
    if status_text:
        _fail("DIRTY_WORKTREE", status_text.rstrip("\n"))
    return {
        "project_root": str(PROJECT_ROOT),
        "head": head,
        "status_porcelain_v1": status_text,
        "clean": True,
    }


def _require_real_directory(path: Path, *, create: bool) -> None:
    try:
        item = os.lstat(path)
    except FileNotFoundError:
        if not create:
            _fail("RUN_PARENT_MISSING", str(path))
        try:
            os.mkdir(path, 0o700)
        except OSError as exc:
            _fail("RUN_PARENT_CREATE_FAILED", f"{path}: {exc}")
        item = os.lstat(path)
    if stat.S_ISLNK(item.st_mode) or not stat.S_ISDIR(item.st_mode):
        _fail("RUN_PARENT_INVALID", str(path))


def _prepare_run_parent(run_root: Path) -> None:
    if run_root.parent != IGNORED_RUN_PARENT:
        _fail(
            "RUN_ROOT_OUTSIDE_IGNORED_PARENT",
            f"run root must be a direct child of {IGNORED_RUN_PARENT}",
        )
    _require_real_directory(PROJECT_ROOT / ".artifacts", create=True)
    _require_real_directory(IGNORED_RUN_PARENT, create=True)
    relative_probe = (
        IGNORED_RUN_PARENT.relative_to(PROJECT_ROOT) / ".w0-d6-ignore-probe"
    )
    completed = subprocess.run(
        ["git", "check-ignore", "-q", "--", str(relative_probe)],
        cwd=PROJECT_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        close_fds=True,
    )
    if completed.returncode != 0:
        _fail("RUN_PARENT_NOT_IGNORED", str(IGNORED_RUN_PARENT))


def _parse_strict_object(snapshot: StableSnapshot, label: str) -> dict[str, Any]:
    try:
        text = snapshot.data.decode("utf-8")
        value = loads_strict_json(text)
    except (UnicodeDecodeError, ValueError) as exc:
        _fail("INPUT_JSON_INVALID", f"{label}: {exc}")
    if type(value) is not dict:
        _fail("INPUT_JSON_ROOT_INVALID", f"{label}: root must be an object")
    return cast(dict[str, Any], value)


def _snapshot_inputs(
    strict_path: Path,
    framework_path: Path,
    seed_path: Path,
) -> dict[str, StableSnapshot]:
    return {
        "strict_instance": read_stable_snapshot(
            strict_path,
            expected_sha256=STRICT_SHA256,
            max_bytes=MAX_INPUT_BYTES,
        ),
        "framework": read_stable_snapshot(
            framework_path,
            expected_sha256=FRAMEWORK_SHA256,
            max_bytes=MAX_INPUT_BYTES,
        ),
        "seed": read_stable_snapshot(
            seed_path,
            expected_sha256=SEED_SHA256,
            max_bytes=MAX_INPUT_BYTES,
        ),
    }


def _snapshot_sources() -> dict[str, StableSnapshot]:
    return {
        label: read_stable_snapshot(path, max_bytes=MAX_SOURCE_BYTES)
        for label, path in _SOURCE_PATHS.items()
    }


def _copy_snapshots(
    run_root: ExclusiveRunRoot,
    snapshots: Mapping[str, StableSnapshot],
    relative_paths: Mapping[str, str],
) -> dict[str, ArtifactIdentity]:
    return {
        label: run_root.write_bytes(relative_paths[label], snapshots[label].data)
        for label in sorted(snapshots)
    }


def _load_gate_module(copied_gate_snapshot: StableSnapshot) -> ModuleType:
    module_name = "_w0_d6_joint_completion_gate_run"
    copied_gate_path = copied_gate_snapshot.path
    spec = importlib.util.spec_from_file_location(module_name, copied_gate_path)
    if spec is None or spec.loader is None:
        _fail("GATE_IMPORT_FAILED", copied_gate_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        code = compile(
            copied_gate_snapshot.data,
            copied_gate_path,
            "exec",
            dont_inherit=True,
        )
        exec(code, module.__dict__)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        _fail("GATE_IMPORT_FAILED", f"{copied_gate_path}: {type(exc).__name__}: {exc}")
    return module


def _gate_callable(module: ModuleType, name: str) -> Callable[..., dict[str, Any]]:
    candidate = getattr(module, name, None)
    if not callable(candidate):
        _fail("GATE_API_INVALID", name)
    return cast(Callable[..., dict[str, Any]], candidate)


def _rejected_producer_claims(
    seed: Mapping[str, Any],
    *,
    actual_seed_sha256: str,
) -> list[dict[str, object]]:
    summary = seed.get("validation_summary")
    claim = summary.get("source_sha256") if isinstance(summary, Mapping) else None
    if claim is None:
        return []
    record: dict[str, object] = {
        "claim_path": "seed.validation_summary.source_sha256",
        "accepted_as_binding": False,
        "actual_seed_sha256": actual_seed_sha256,
        "reason": (
            "producer-reported source identity is not an independent binding "
            "to the snapshotted seed bytes"
        ),
    }
    if type(claim) is str:
        record["claimed_sha256"] = claim
        record["matches_known_unbound_claim"] = (
            claim == REJECTED_PRODUCER_SOURCE_SHA256
        )
    else:
        record["claimed_value_type"] = type(claim).__name__
    return [record]


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


def _runtime_identity() -> dict[str, object]:
    try:
        ortools_version = importlib.metadata.version("ortools")
    except importlib.metadata.PackageNotFoundError:
        _fail("SOLVER_RUNTIME_MISSING", "ortools distribution")
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": str(Path(sys.executable).resolve()),
        "ortools_distribution_version": ortools_version,
    }


def _claim_boundary(status: str) -> str:
    if status == "FEASIBLE":
        return "feasible_only_for_the_exact_local_d6_antecedent"
    if status == "INFEASIBLE":
        return "infeasible_only_for_the_exact_local_d6_antecedent"
    return "unknown_no_rejection_cut_or_global_conclusion"


def _validate_gate_result(
    value: object,
    *,
    expected_antecedent_sha256: str,
) -> dict[str, Any]:
    if type(value) is not dict:
        _fail("GATE_RESULT_INVALID", "root must be an object")
    result = cast(dict[str, Any], value)
    expected_keys = {
        "schema",
        "status",
        "status_detail",
        "claim_boundary",
        "antecedent_sha256",
        "solver_statistics",
        "configuration",
        "certificate",
    }
    if set(result) != expected_keys:
        _fail("GATE_RESULT_INVALID", "key set differs")
    if result.get("schema") != "w0_d6_gate_result_v1":
        _fail("GATE_RESULT_INVALID", "schema differs")
    status_value = result.get("status")
    if status_value not in {"FEASIBLE", "INFEASIBLE", "UNKNOWN"}:
        _fail("GATE_RESULT_INVALID", f"status={status_value!r}")
    status = cast(str, status_value)
    if type(result["status_detail"]) is not str or not result["status_detail"]:
        _fail("GATE_RESULT_INVALID", "status_detail must be non-empty text")
    if result["claim_boundary"] != _claim_boundary(status):
        _fail("GATE_RESULT_INVALID", "claim_boundary differs")
    if result["antecedent_sha256"] != expected_antecedent_sha256:
        _fail("GATE_RESULT_INVALID", "antecedent_sha256 differs")
    if type(result["solver_statistics"]) is not dict:
        _fail("GATE_RESULT_INVALID", "solver_statistics must be an object")
    configuration = result.get("configuration")
    certificate = result.get("certificate")
    if status == "FEASIBLE":
        if type(configuration) is not dict or type(certificate) is not dict:
            _fail("GATE_RESULT_INVALID", "FEASIBLE requires configuration and certificate")
        expected_configuration_keys = {
            "schema",
            "antecedent_sha256",
            "claim_boundary",
            "bodies",
            "transport",
            "cycle_roles",
            "flows",
        }
        if (
            set(configuration) != expected_configuration_keys
            or configuration.get("schema") != "w0_d6_configuration_v1"
            or configuration.get("antecedent_sha256") != expected_antecedent_sha256
            or configuration.get("claim_boundary") != result["claim_boundary"]
        ):
            _fail("GATE_RESULT_INVALID", "configuration binding differs")
        expected_certificate_keys = {
            "schema",
            "antecedent_sha256",
            "configuration_sha256",
            "status",
            "claim_boundary",
        }
        if set(certificate) != expected_certificate_keys:
            _fail("GATE_RESULT_INVALID", "certificate key set differs")
        configuration_sha256 = hashlib.sha256(
            canonical_json_bytes(configuration)
        ).hexdigest()
        if (
            certificate["schema"] != "w0_d6_local_certificate_v1"
            or certificate["antecedent_sha256"] != expected_antecedent_sha256
            or certificate["configuration_sha256"] != configuration_sha256
            or certificate["status"] != "FEASIBLE"
            or certificate["claim_boundary"] != result["claim_boundary"]
        ):
            _fail("GATE_RESULT_INVALID", "certificate binding differs")
    elif configuration is not None or certificate is not None:
        _fail("GATE_RESULT_INVALID", f"{status} must not carry configuration/certificate")
    canonical_json_bytes(result)
    return result


def _unknown_gate_observation(detail: str) -> dict[str, object]:
    return {
        "schema": "w0_d6_gate_execution_observation_v1",
        "status": "UNKNOWN",
        "status_detail": detail,
        "claim_boundary": _claim_boundary("UNKNOWN"),
        "solver_statistics": {},
    }


def _revalidate_snapshots(snapshots: Mapping[str, StableSnapshot]) -> None:
    for snapshot in snapshots.values():
        read_stable_snapshot(
            snapshot.path,
            expected_sha256=snapshot.sha256,
            expected_size_bytes=snapshot.size_bytes,
            max_bytes=max(snapshot.size_bytes, 1),
        )


def _identity_records(
    original: Mapping[str, StableSnapshot],
    copied: Mapping[str, ArtifactIdentity],
) -> dict[str, object]:
    return {
        label: {
            "external" if label in _INPUT_COPY_PATHS else "working_tree": (
                original[label].identity.as_dict()
            ),
            "run_copy": copied[label].as_dict(),
        }
        for label in sorted(original)
    }


def _receipt_artifacts(
    *,
    config_identity: ArtifactIdentity,
    antecedent_identity: ArtifactIdentity,
    result_identity: ArtifactIdentity,
    input_copies: Mapping[str, ArtifactIdentity],
    source_copies: Mapping[str, ArtifactIdentity],
    configuration_identity: ArtifactIdentity | None,
    certificate_identity: ArtifactIdentity | None,
) -> dict[str, ArtifactIdentity]:
    artifacts = {
        "config": config_identity,
        "antecedent": antecedent_identity,
        "result": result_identity,
        **{
            f"inputs.{label}": identity
            for label, identity in input_copies.items()
        },
        **{
            f"sources.{label}": identity
            for label, identity in source_copies.items()
        },
    }
    if configuration_identity is not None:
        artifacts["configuration"] = configuration_identity
    if certificate_identity is not None:
        artifacts["certificate"] = certificate_identity
    return artifacts


def _validate_manifest_artifact_bijection(
    run_root: ExclusiveRunRoot,
    manifest: Mapping[str, object],
    artifacts: Mapping[str, ArtifactIdentity],
) -> None:
    raw_entries = manifest.get("entries")
    if type(raw_entries) is not list:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", "entries must be an array")
    manifest_files: set[str] = set()
    manifest_directories: set[str] = set()
    for index, raw_entry in enumerate(raw_entries):
        if type(raw_entry) is not dict:
            _fail(
                "ARTIFACT_ROOT_MANIFEST_INVALID",
                f"entries[{index}] must be an object",
            )
        entry = cast(dict[str, object], raw_entry)
        path = entry.get("path")
        node_type = entry.get("type")
        if type(path) is not str or node_type not in {"regular_file", "directory"}:
            _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"entries[{index}]")
        if node_type == "regular_file":
            manifest_files.add(path)
        else:
            manifest_directories.add(path)
    artifact_files: set[str] = set()
    for label, identity in artifacts.items():
        path = _absolute(identity.path)
        if str(path) != identity.path:
            _fail("ARTIFACT_PATH_INVALID", f"{label}: path is not canonical")
        try:
            relative = path.relative_to(run_root.path).as_posix()
        except ValueError:
            _fail("ARTIFACT_PATH_INVALID", f"{label}: outside run root")
        if relative in artifact_files:
            _fail("ARTIFACT_PATH_ALIAS", relative)
        artifact_files.add(relative)
    if manifest_files != artifact_files:
        _fail(
            "ARTIFACT_ROOT_ARTIFACT_SET_MISMATCH",
            (
                f"manifest_only={sorted(manifest_files - artifact_files)!r}; "
                f"artifacts_only={sorted(artifact_files - manifest_files)!r}"
            ),
        )
    expected_directories = {
        "/".join(relative.split("/")[:depth])
        for relative in artifact_files
        for depth in range(1, len(relative.split("/")))
    }
    if manifest_directories != expected_directories:
        _fail(
            "ARTIFACT_ROOT_DIRECTORY_SET_MISMATCH",
            (
                f"manifest_only={sorted(manifest_directories - expected_directories)!r}; "
                f"required_only={sorted(expected_directories - manifest_directories)!r}"
            ),
        )


def run(args: argparse.Namespace) -> tuple[str, bool, ArtifactIdentity]:
    process_contract = require_isolated_python_process()
    run_path = _absolute(args.run_root)
    project_lock_snapshot = read_stable_snapshot(
        PROJECT_LOCK_PATH,
        expected_sha256=EXPECTED_PROJECT_LOCK_SHA256,
        max_bytes=MAX_SOURCE_BYTES,
    )
    input_snapshots = _snapshot_inputs(
        _absolute(args.strict),
        _absolute(args.framework),
        _absolute(args.seed),
    )
    parsed_inputs = {
        label: _parse_strict_object(snapshot, label)
        for label, snapshot in input_snapshots.items()
    }
    source_snapshots = _snapshot_sources()
    git_identity = _git_identity()

    _prepare_run_parent(run_path)
    run_root = ExclusiveRunRoot.create(run_path)
    run_root.mkdir("inputs")
    run_root.mkdir("sources")
    input_copies = _copy_snapshots(
        run_root,
        input_snapshots,
        _INPUT_COPY_PATHS,
    )
    source_copies = _copy_snapshots(
        run_root,
        source_snapshots,
        _SOURCE_COPY_PATHS,
    )

    copied_gate_snapshot = read_stable_snapshot(
        source_copies["gate"].path,
        expected_sha256=source_copies["gate"].sha256,
        expected_size_bytes=source_copies["gate"].size_bytes,
        max_bytes=MAX_SOURCE_BYTES,
    )
    gate_module = _load_gate_module(copied_gate_snapshot)
    build_antecedent = _gate_callable(gate_module, "build_d6_antecedent")
    solve_gate = _gate_callable(gate_module, "solve_d6_joint_completion")
    antecedent = build_antecedent(
        parsed_inputs["strict_instance"],
        parsed_inputs["framework"],
        parsed_inputs["seed"],
        attachment_scope=args.attachment_scope,
    )
    if (
        type(antecedent) is not dict
        or antecedent.get("schema") != ANTECEDENT_SCHEMA
        or antecedent.get("protocol") != _protocol_identity()
    ):
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            "gate antecedent does not match the complete v3 protocol",
        )
    antecedent_identity = run_root.write_json("antecedent.json", antecedent)

    replayer_copy_path = source_copies["replayer"].path
    replay_argv_template = [
        "<python3>",
        "-I",
        "-B",
        replayer_copy_path,
        "--run-root",
        str(run_root.path),
    ]
    config = make_research_run_config(
        experiment_id=EXPERIMENT_ID,
        payload={
            "schema": CONFIG_PAYLOAD_SCHEMA,
            "protocol": _protocol_identity(),
            "attachment_scope": args.attachment_scope,
            "solver": {
                "workers": args.workers,
                "random_seed": args.random_seed,
                "max_time_seconds": args.max_time_seconds,
            },
            "runtime": _runtime_identity(),
            "process_contract": process_contract,
            "git": git_identity,
            "inputs": _identity_records(input_snapshots, input_copies),
            "sources": _identity_records(source_snapshots, source_copies),
            "antecedent": antecedent_identity.as_dict(),
            "rejected_producer_claims": _rejected_producer_claims(
                parsed_inputs["seed"],
                actual_seed_sha256=input_snapshots["seed"].sha256,
            ),
            "authority_boundary": _authority_boundary(),
            "replay": {"argv_template": replay_argv_template},
        },
    )
    config_identity = run_root.write_json("config.json", config)

    interrupted = False
    try:
        raw_gate_result: object = solve_gate(
            parsed_inputs["strict_instance"],
            parsed_inputs["framework"],
            parsed_inputs["seed"],
            antecedent=antecedent,
            attachment_scope=args.attachment_scope,
            workers=args.workers,
            random_seed=args.random_seed,
            max_time_seconds=args.max_time_seconds,
        )
        gate_result = _validate_gate_result(
            raw_gate_result,
            expected_antecedent_sha256=antecedent_identity.sha256,
        )
        status = cast(str, gate_result["status"])
        gate_observation: dict[str, Any] = {
            key: value
            for key, value in gate_result.items()
            if key not in {"configuration", "certificate"}
        }
        interrupted = (
            status == "UNKNOWN"
            and gate_observation.get("status_detail") == "interrupted"
        )
        configuration = gate_result.get("configuration")
        certificate = gate_result.get("certificate")
    except KeyboardInterrupt:
        interrupted = True
        status = "UNKNOWN"
        gate_observation = _unknown_gate_observation(
            "interrupted_before_a_gate_result"
        )
        configuration = None
        certificate = None
    except Exception as exc:
        status = "UNKNOWN"
        gate_observation = _unknown_gate_observation(
            f"gate_exception_without_verdict:{type(exc).__name__}:{exc}"
        )
        configuration = None
        certificate = None

    _revalidate_snapshots(input_snapshots)
    _revalidate_snapshots(source_snapshots)
    if _git_identity() != git_identity:
        _fail("GIT_IDENTITY_DRIFT", "HEAD or status changed during the run")

    configuration_identity: ArtifactIdentity | None = None
    certificate_identity: ArtifactIdentity | None = None
    if status == "FEASIBLE":
        configuration_identity = run_root.write_json(
            "configuration.json",
            configuration,
        )
        certificate_identity = run_root.write_json(
            "certificate.json",
            certificate,
        )

    claim_boundary = _claim_boundary(status)
    result = {
        "schema": "w0_d6_result_v1",
        "status": status,
        "antecedent_sha256": antecedent_identity.sha256,
        "configuration_sha256": (
            None
            if configuration_identity is None
            else configuration_identity.sha256
        ),
        "certificate_sha256": (
            None
            if certificate_identity is None
            else certificate_identity.sha256
        ),
        "claim_boundary": claim_boundary,
        "gate_observation": gate_observation,
    }
    result_identity = run_root.write_json("result.json", result)
    artifacts = _receipt_artifacts(
        config_identity=config_identity,
        antecedent_identity=antecedent_identity,
        result_identity=result_identity,
        input_copies=input_copies,
        source_copies=source_copies,
        configuration_identity=configuration_identity,
        certificate_identity=certificate_identity,
    )
    identity_graph = replay_identity_graph(
        artifacts,
        max_bytes_per_artifact=MAX_INPUT_BYTES,
    )
    artifact_root_manifest = build_artifact_root_manifest(run_root)
    _validate_manifest_artifact_bijection(
        run_root,
        artifact_root_manifest,
        artifacts,
    )
    verify_artifact_root_closure(
        run_root,
        artifact_root_manifest,
        receipt_present=False,
    )
    _revalidate_snapshots({"project_lock": project_lock_snapshot})
    receipt = make_research_run_receipt(
        experiment_id=EXPERIMENT_ID,
        config_identity=config_identity,
        artifacts=artifacts,
        payload={
            "schema": RECEIPT_PAYLOAD_SCHEMA,
            "protocol": _protocol_identity(),
            "status": status,
            "attachment_scope": args.attachment_scope,
            "antecedent_sha256": antecedent_identity.sha256,
            "result_sha256": result_identity.sha256,
            "configuration_sha256": result["configuration_sha256"],
            "certificate_sha256": result["certificate_sha256"],
            "identity_graph_sha256": identity_graph.graph_sha256,
            "artifact_root_manifest": artifact_root_manifest,
            "claim_boundary": claim_boundary,
            "authority_boundary": _authority_boundary(),
            "replay": {"argv_template": replay_argv_template},
        },
    )
    receipt_identity = run_root.write_json("receipt.json", receipt)
    verify_artifact_root_closure(
        run_root,
        artifact_root_manifest,
        receipt_present=True,
    )
    final_identity_graph = replay_identity_graph(
        artifacts,
        max_bytes_per_artifact=MAX_INPUT_BYTES,
    )
    if final_identity_graph.graph_sha256 != identity_graph.graph_sha256:
        _fail("ARTIFACT_GRAPH_CHANGED", "artifact graph changed after receipt write")
    receipt_snapshot = read_stable_snapshot(
        receipt_identity.path,
        expected_sha256=receipt_identity.sha256,
        expected_size_bytes=receipt_identity.size_bytes,
        max_bytes=MAX_INPUT_BYTES,
    )
    verify_artifact_root_closure(
        run_root,
        artifact_root_manifest,
        receipt_present=True,
    )
    return status, interrupted, receipt_snapshot.identity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the hash-pinned, research-only W0 D6 local joint-completion gate"
        )
    )
    parser.add_argument("--strict", type=Path, required=True)
    parser.add_argument("--framework", type=Path, required=True)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument(
        "--protocol-cohort",
        choices=(PROTOCOL_COHORT,),
        required=True,
    )
    parser.add_argument(
        "--class-allocation-profile",
        choices=(CLASS_ALLOCATION_PROFILE,),
        required=True,
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--max-time-seconds", type=int, default=3600)
    parser.add_argument(
        "--attachment-scope",
        choices=("all_legal_d6_slots",),
        required=True,
    )
    return parser


def _validate_arguments(args: argparse.Namespace) -> None:
    if (
        args.protocol_cohort != PROTOCOL_COHORT
        or args.class_allocation_profile != CLASS_ALLOCATION_PROFILE
        or args.attachment_scope != "all_legal_d6_slots"
    ):
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            "runner arguments do not select the complete v3 protocol",
        )
    if args.workers <= 0:
        _fail("ARGUMENT_INVALID", "--workers must be positive")
    if args.random_seed < 0:
        _fail("ARGUMENT_INVALID", "--random-seed must be non-negative")
    if args.max_time_seconds <= 0:
        _fail("ARGUMENT_INVALID", "--max-time-seconds must be positive")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        _validate_arguments(args)
        status, interrupted, receipt_identity = run(args)
    except (D6RunnerError, ResearchRunContractError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        error = {
            "schema": "w0_d6_runner_error_v1",
            "d6_status": None,
            "error_code": code,
            "detail": str(exc),
            "claim_boundary": "no_d6_verdict",
        }
        sys.stderr.buffer.write(canonical_json_bytes(error))
        return 2
    except Exception as exc:
        error = {
            "schema": "w0_d6_runner_error_v1",
            "d6_status": None,
            "error_code": "UNEXPECTED_RUNNER_ERROR",
            "detail": f"{type(exc).__name__}: {exc}",
            "claim_boundary": "no_d6_verdict",
        }
        sys.stderr.buffer.write(canonical_json_bytes(error))
        return 2
    canonical_summary = {
        "schema": "w0_d6_runner_summary_v1",
        "status": status,
        "interrupted": interrupted,
        "claim_boundary": _claim_boundary(status),
        "run_root": str(_absolute(args.run_root)),
        "receipt": str(_absolute(args.run_root) / "receipt.json"),
        "receipt_identity": receipt_identity.as_dict(),
        "artifact_root_closed": True,
    }
    sys.stdout.buffer.write(canonical_json_bytes(canonical_summary))
    return 130 if interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())
