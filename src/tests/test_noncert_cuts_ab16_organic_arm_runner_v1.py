from __future__ import annotations

import ast
import ctypes
import fcntl
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import textwrap
from types import ModuleType
from typing import Any, Callable

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724" / "organic_arm_runner_v1.py"
CONTRACT_PATH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724" / "ab16_contract_v1.py"
LIFECYCLE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "noncert_cuts_ab16_20260724"
    / "organic_resource_lifecycle_v2.py"
)
GIT_PATH = Path(shutil.which("git") or "").resolve(strict=True)
REPOSITORY_HEAD = subprocess.check_output(
    [str(GIT_PATH), "-C", str(ROOT), "rev-parse", "--verify", "HEAD^{commit}"],
    text=True,
).strip()


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = _load(RUNNER_PATH, "noncert_cuts_ab16_organic_arm_runner_v1")
CONTRACT = _load(CONTRACT_PATH, "noncert_cuts_ab16_contract_for_runner_test")
LIFECYCLE = _load(LIFECYCLE_PATH, "noncert_cuts_ab16_lifecycle_for_runner_test")


def _write(path: Path, raw: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _authority(path: Path, value: object) -> dict[str, object]:
    return _write(path, RUNNER.canonical_json(value))


def _detached(identity: dict[str, object]) -> dict[str, object]:
    return {key: identity[key] for key in ("path", "sha256", "size_bytes")}


def _existing_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _existing_identity_with_mode(path: Path) -> dict[str, object]:
    return {
        "mode": stat.S_IMODE(path.stat().st_mode),
        **_existing_identity(path),
    }


def _incumbent() -> dict[str, object]:
    return {
        "ghost_pick": {
            "anchor": {"x": 0, "y": 0},
            "height": 6,
            "width": 6,
        },
        "machine_001": {
            "anchor": {"x": 7, "y": 8},
            "instance_id": "machine_001",
            "pose_id": "pose-1",
            "pose_idx": 3,
        },
    }


def _compiled_cut(index: int = 1) -> object:
    import src.cuts.typed_platform as typed

    character = format(index % 16, "x")
    scope = typed.ModelScope(
        ghost_policy="agnostic",
        ghost_rect_digest=None,
        domain_fingerprint=f"fixture-domain-{index}",
    )
    plan = typed.ConstraintPlan(
        family="region_capacity",
        schema_version=1,
        semantic_fingerprint=character * 64,
        model_scope=scope,
        operation="region_capacity_le",
        parameters={
            "capacity": index,
            "group_cell_weights": {"group-1": 1},
        },
    )
    return typed.CompiledCut(
        cut_id=f"fixture-cut-{index}",
        proof_digest=format((index + 1) % 16, "x") * 64,
        scope_digest=format((index + 2) % 16, "x") * 64,
        snapshot_digest=format((index + 3) % 16, "x") * 64,
        plan=plan,
        _construction_token=typed._COMPILED_CUT_CONSTRUCTION_TOKEN,
    )


class FakeHooks:
    def __init__(
        self,
        incumbent: dict[str, object],
        *,
        cuts: tuple[object, ...] = (),
        wrong_solution: bool = False,
        attach_rounds: int = 1,
        export_solution: bool = True,
    ) -> None:
        self.incumbent = incumbent
        self.cuts = cuts
        self.wrong_solution = wrong_solution
        self.attach_rounds = attach_rounds
        self.export_solution = export_solution
        self.constructed = False
        self.construct_env: str | None = "unobserved"
        self.attach_env: str | None = "unobserved"
        self.enabled_families: tuple[str, ...] | None = None
        self.repository_root: Path | None = None
        self.workers: int | None = None

    def construct(self, context: object) -> object:
        self.constructed = True
        self.construct_env = os.environ.get(RUNNER.ATTACH_ENV)
        self.enabled_families = context.enabled_families
        self.repository_root = context.repository_root
        self.workers = context.workers
        return context

    def _attach_solution(self) -> dict[str, object]:
        if not self.wrong_solution:
            return self.incumbent
        changed = json.loads(json.dumps(self.incumbent))
        changed["machine_001"]["pose_idx"] = 99
        return changed

    def run_attach_phase(
        self,
        runtime: object,
        context: object,
        recorder: object,
    ) -> object:
        del runtime
        self.attach_env = os.environ.get(RUNNER.ATTACH_ENV)
        for round_index in range(self.attach_rounds):
            round_cuts = self.cuts[round_index :: self.attach_rounds]
            with recorder.attach_hook(
                trigger="binding_infeasible",
                iteration=1001 + round_index,
                solution=self._attach_solution(),
            ) as completion:
                for compiled in round_cuts:
                    context.ledger.append(
                        "GENERATED",
                        {
                            "cut_id": compiled.cut_id,
                            "family": compiled.plan.family,
                        },
                    )
                    recorder.record_compiled_cut(compiled)
                    context.ledger.append(
                        "APPLIED",
                        {
                            "cut_id": compiled.cut_id,
                            "family": compiled.plan.family,
                            "plan_digest": compiled.plan.digest,
                            "semantic_fingerprint": (compiled.plan.semantic_fingerprint),
                        },
                    )
                completion.returned(len(round_cuts))
        return RUNNER.ArmOutcome(
            raw_controller_terminal={
                "budget_censor_evidence": {
                    "internal_budget_reached": False,
                    "kind": "none",
                    "limit": None,
                    "observed": {},
                },
                "controller_completed": True,
                "controller_status": "UNKNOWN",
                "cumulative_deterministic_time": 0.0,
                "master_last_solve": {},
                "master_solve_history": [],
                "schema_version": RUNNER.CONTROLLER_TERMINAL_SCHEMA,
            },
            raw_incumbent=self.incumbent if self.export_solution else None,
            raw_metrics={
                "best_bound": 123,
                "branches": 45,
                "generated": len(self.cuts),
            },
            raw_proof_summary={
                "attach_calls": 1,
                "fixture_only": True,
            },
            raw_solution_vector=[0, 1] if self.export_solution else None,
            raw_solver_status="UNKNOWN",
        )


class EvidenceRequiredHooks(FakeHooks):
    requires_model_evidence = True


class _BudgetBackend:
    def __init__(self, fixture: dict[str, Any]) -> None:
        self.records: list[dict[str, object]] = []
        self.sequences: dict[str, int] = {}
        allocation_sha256 = hashlib.sha256(b"arm-allocation").hexdigest()
        self._binding = {
            "arm_allocation_id": allocation_sha256,
            "arm_allocation_identity": {
                "sha256": allocation_sha256,
                "size_bytes": len(b"arm-allocation"),
            },
            "arm_slot": fixture["selection"]["slot"],
            "broker_nonce": "broker-nonce",
            "broker_socket_fd": 91,
            "filesystem_write_confinement": RUNNER.BUDGET_WORKER_CONFINEMENT,
            "formal_budget_authority_identity": _existing_identity(
                fixture["selection_path"]
            ),
            "next_sequence": 1,
        }

    @property
    def authority_binding(self) -> dict[str, object]:
        return dict(self._binding)

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int:
        assert label
        assert artifact_class in {
            "closeout",
            "ledger",
            "metadata",
            "model",
            "publication",
        }
        return 4 * 1024 * 1024

    def publish_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
    ) -> dict[str, object]:
        assert len(raw) <= maximum_bytes
        record = {
            "artifact_class": artifact_class,
            "label": label,
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        self.records.append(record)
        return record

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> dict[str, object]:
        assert len(raw) <= maximum_bytes
        assert sequence == self.sequences.get(channel, 0)
        self.sequences[channel] = sequence + 1
        record = {
            "arm_slot": arm_slot,
            "artifact_class": artifact_class,
            "path": f"channels/{channel}/segment-{sequence:08d}.bin",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        self.records.append(record)
        return record

    def export_model_to_sealed_memfd(
        self,
        model: object,
        path: Path,
        *,
        maximum_bytes: int,
        label: str,
    ) -> dict[str, object]:
        del model, path, maximum_bytes, label
        raise AssertionError("fixture hooks must not export an OR-Tools model")


class _ModelBudgetBackend:
    def __init__(self, result: object) -> None:
        self.result = result

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int:
        assert label == "attach model evidence"
        assert artifact_class == "model"
        return 1024

    def export_model_to_sealed_memfd(
        self,
        model: object,
        path: Path,
        *,
        maximum_bytes: int,
        label: str,
    ) -> object:
        del model, path, maximum_bytes, label
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class _NativeMemfdHelper:
    final_seal_mask = (
        getattr(fcntl, "F_SEAL_WRITE", 0x0008)
        | getattr(fcntl, "F_SEAL_GROW", 0x0004)
        | getattr(fcntl, "F_SEAL_SHRINK", 0x0002)
        | getattr(fcntl, "F_SEAL_SEAL", 0x0001)
        | getattr(fcntl, "F_SEAL_FUTURE_WRITE", 0x0010)
    )

    def create_memfd(self, name: str) -> int:
        function = ctypes.CDLL(None, use_errno=True).memfd_create
        function.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        descriptor = int(function(name.encode("ascii"), 0x0001 | 0x0002))
        if descriptor < 0:
            raise OSError(ctypes.get_errno(), "libc memfd_create failed")
        return descriptor

    def has_writable_mapping(self, descriptor: int) -> bool:
        del descriptor
        return False

    def install_final_seals(self, descriptor: int) -> int:
        fcntl.fcntl(
            descriptor,
            getattr(fcntl, "F_ADD_SEALS", 1033),
            self.final_seal_mask,
        )
        return self.get_seals(descriptor)

    @staticmethod
    def get_seals(descriptor: int) -> int:
        return int(fcntl.fcntl(descriptor, getattr(fcntl, "F_GET_SEALS", 1034)))


class _BrokerResponse:
    def __init__(self, result: dict[str, object]) -> None:
        self.record = {"result": result}


class _BrokerClient:
    def __init__(self, helper: _NativeMemfdHelper) -> None:
        self.connection, self._peer = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET,
        )
        self.native_helper = helper
        self.nonce = "broker-nonce"
        self.sequence = 0
        self.published: list[bytes] = []

    def publish_descriptor(
        self,
        payload: dict[str, object],
        *,
        descriptor: int,
        publication_boundary: Callable[[], None] | None = None,
    ) -> _BrokerResponse:
        self.sequence += 1
        if publication_boundary is not None:
            publication_boundary()
        size = int(payload["size_bytes"])
        raw = os.pread(descriptor, size, 0)
        assert hashlib.sha256(raw).hexdigest() == payload["expected_sha256"]
        assert self.native_helper.get_seals(descriptor) == (
            self.native_helper.final_seal_mask
        )
        self.published.append(raw)
        return _BrokerResponse(
            {
                "artifact_class": payload["artifact_class"],
                "maximum_bytes": payload["maximum_bytes"],
                "path": payload["relative_path"],
                "sha256": payload["expected_sha256"],
                "size_bytes": size,
                "source_seal_mask": self.native_helper.final_seal_mask,
            }
        )

    def close(self) -> None:
        self.connection.close()
        self._peer.close()


class _OTruncModel:
    @staticmethod
    def export_to_file(path: str) -> bool:
        with open(path, "wb") as handle:
            handle.write(b"tiny-model")
        return True


def _fixture(
    tmp_path: Path,
    *,
    configuration: str = "region-capacity",
    order: str = "ab",
    arm: str = "treatment",
) -> dict[str, Any]:
    root = tmp_path / "campaign"
    prospective = root / "prospective-ab16"
    arms_parent = prospective / "arms"
    arms_parent.mkdir(parents=True)
    incumbent = _incumbent()
    incumbent_identity = _authority(
        root / "baseline" / "incumbent.json",
        incumbent,
    )
    common_identity = _authority(
        root / "baseline" / "common-prestate.json",
        {
            "incumbent_identity": incumbent_identity,
            "schema_version": "fixture-common-prestate-v1",
        },
    )
    arithmetic_tool_identity = _write(
        root / "tools" / "independent-arithmetic-formal.py",
        b"# independently pinned formal arithmetic verifier fixture\n",
    )
    per_arm_tools = {}
    for role in sorted(RUNNER.PER_ARM_TOOL_ROLES):
        raw = f"# pinned {role} fixture\n".encode()
        if role == "resource_lifecycle":
            raw = textwrap.dedent(
                """
                def validate_pre_run_authority(value):
                    if value.get("status") != "PASS":
                        raise ValueError("pre-run authority did not pass")
                    return value

                def validate_runner_selection(
                    value,
                    *,
                    pre_run_authority,
                    pre_run_authority_identity,
                ):
                    if value.get("pre_run_authority_identity") != pre_run_authority_identity:
                        raise ValueError("pre-run identity mismatch")
                    if pre_run_authority.get("slot") != value.get("slot"):
                        raise ValueError("pre-run slot mismatch")
                    return value
                """
            ).encode()
        per_arm_tools[role] = _write(root / "tools" / f"{role}.py", raw)
    package_manifest_identity = _authority(
        root / "authority" / "package-manifest.json",
        {"schema_version": "fixture-package-manifest-v1"},
    )
    package_seal_identity = _write(
        root / "authority" / "SHA256SUMS",
        b"fixture immutable package seal\n",
    )
    runner_relative = "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py"
    snapshot_root = root / "campaign-authority/source-snapshot-a001/repository"
    snapshot_runner = snapshot_root / runner_relative
    snapshot_runner.parent.mkdir(parents=True)
    snapshot_runner_identity = _write(snapshot_runner, RUNNER_PATH.read_bytes())
    snapshot_runner.chmod(0o444)
    snapshot_runner_identity = _existing_identity_with_mode(snapshot_runner)
    snapshot_member = {
        "git_blob_oid": "1" * 40,
        "git_mode": "100644",
        "materialized_mode": 0o444,
        "path": runner_relative,
        "raw_sha256": snapshot_runner_identity["sha256"],
        "size_bytes": snapshot_runner_identity["size_bytes"],
        "source_kind": "git_blob",
    }
    snapshot_manifest_identity = _authority(
        root / "authority/package/payload/input.ab16_repository_snapshot.json",
        {
            "archive_descriptor": {
                "package_role": "input.ab16_repository_snapshot.zip",
                "sha256": "2" * 64,
                "size_bytes": 1,
            },
            "authority_scope": "AB16_RESEARCH_ONLY",
            "import_mode": "ordinary_pathfinder",
            "member_count": 1,
            "members": [snapshot_member],
            "ordered_member_digest": hashlib.sha256(RUNNER.canonical_json([snapshot_member])).hexdigest(),
            "repository_head": REPOSITORY_HEAD,
            "repository_tree": "3" * 40,
            "schema_version": RUNNER.SNAPSHOT_MANIFEST_SCHEMA,
            "total_bytes": snapshot_runner_identity["size_bytes"],
        },
    )
    snapshot_receipt_identity = _authority(
        root / "campaign-authority/source-snapshot-a001/materialization-receipt.json",
        {
            "authority_scope": "AB16_RESEARCH_ONLY",
            "candidate_identity": common_identity,
            "created_at_utc": "2026-07-27T00:00:00Z",
            "import_mode": "ordinary_pathfinder",
            "member_count": 1,
            "ordered_member_digest": hashlib.sha256(RUNNER.canonical_json([snapshot_member])).hexdigest(),
            "package_id": package_seal_identity["sha256"],
            "repository_head": REPOSITORY_HEAD,
            "repository_tree": "3" * 40,
            "schema_version": RUNNER.SNAPSHOT_MATERIALIZATION_SCHEMA,
            "snapshot_archive_identity": {
                "path": str(root / "authority/package/payload/input.ab16_repository_snapshot.zip"),
                "sha256": "2" * 64,
                "size_bytes": 1,
            },
            "snapshot_manifest_identity": snapshot_manifest_identity,
            "snapshot_root": str(snapshot_root),
            "status": "PASS",
            "total_bytes": snapshot_runner_identity["size_bytes"],
        },
    )
    selected_python_identity = _existing_identity_with_mode(Path(sys.executable).resolve())
    selected_loader_path = root / "authority/package/payload/tool.ab16_formal_loader_v1.py"
    _write(selected_loader_path, b"# fixture formal loader\n")
    selected_loader_path.chmod(0o444)
    selected_loader_identity = _existing_identity_with_mode(selected_loader_path)
    selected_authority_path = root / "authority/package/payload/tool.ab16_authority_v2.py"
    _write(selected_authority_path, b"# fixture package-pinned authority\n")
    selected_authority_path.chmod(0o444)
    selected_authority_identity = _existing_identity_with_mode(selected_authority_path)
    selected_literal = "fixture-selected-byte-launch-v1"
    authority_chain = {
        "campaign_root_identity": _authority(
            root / "authority" / "campaign-root.json",
            {"schema_version": "fixture-campaign-root-v1"},
        ),
        "continuation_identity": _authority(
            root / "authority" / "continuation.json",
            {"schema_version": "fixture-continuation-v1"},
        ),
        "manager_epoch_authority_identity": _authority(
            root / "authority" / "manager-epoch.json",
            {"schema_version": "fixture-manager-epoch-v1"},
        ),
        "package": {
            "manifest_identity": package_manifest_identity,
            "package_id": package_seal_identity["sha256"],
            "seal_identity": package_seal_identity,
        },
    }
    admission = {
        "admission_tool_identity": _write(
            root / "tools" / "baseline-admission.py",
            b"# baseline admission fixture\n",
        ),
        "authorizations": {
            "baseline_inputs_admitted": True,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        },
        "created_at_utc": "2026-07-24T01:00:00Z",
        "expectation_profile": "small-fixture-v1",
        "expected_baseline": {
            "incumbent_assignment_count": len(incumbent),
            "incumbent_sha256": RUNNER.semantic_digest(incumbent),
            "model_constraint_count": 1,
            "historical_model_text_sha256": "1" * 64,
            "model_variable_count": 2,
        },
        "fixed_assignment_replay": {
            "incumbent_identity": incumbent_identity,
            "receipt_identity": _write(
                root / "baseline" / "fixed-replay-receipt.json",
                b"fixture replay receipt\n",
            ),
            "replay_tool_identity": _write(
                root / "tools" / "fixed-replay.py",
                b"# fixed replay fixture\n",
            ),
            "solver_status": "OPTIMAL",
            "status": "PASS",
            "verdict": "INCUMBENT_FIXED_ASSIGNMENT_REPLAY_PASS",
        },
        "legacy_control": {},
        "rebuilt_model": {},
        "schema_version": RUNNER.BASELINE_ADMISSION_SCHEMA,
        "status": "PASS",
        "verdict": RUNNER.BASELINE_ADMISSION_VERDICT,
    }
    admission_identity = _authority(
        root / "baseline" / "admission.json",
        admission,
    )
    bindings = {
        slot: _authority(
            root / "bindings" / f"{slot}.json",
            {
                "common_prestate_identity": common_identity,
                "schema_version": "fixture-arm-binding-v1",
                "slot": slot,
            },
        )
        for slot in RUNNER.ARM_SEQUENCE
    }
    attempts = {slot: str((arms_parent / slot).resolve()) for slot in RUNNER.ARM_SEQUENCE}
    unit_names = {slot: f"cuts-fixture-ab16-{slot}.service" for slot in RUNNER.ARM_SEQUENCE}
    manifest = {
        "arithmetic_verifier": {
            "purpose": RUNNER.FORMAL_ARITHMETIC_PURPOSE,
            "tool_identity": arithmetic_tool_identity,
        },
        "arm_binding_identities": bindings,
        "arm_sequence": list(RUNNER.ARM_SEQUENCE),
        "attempt_dirs": attempts,
        "authority_chain": authority_chain,
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": True,
            "production_certified_authorized": False,
        },
        "baseline_admission_identity": admission_identity,
        "baseline_incumbent_identity": incumbent_identity,
        "campaign_id": "a" * 64,
        "classification_contract_identity": _existing_identity(CONTRACT_PATH),
        "common_prestate_identity": common_identity,
        "configuration_families": {key: list(value) for key, value in RUNNER.CONFIGURATION_FAMILIES.items()},
        "experiment_contract": RUNNER.EXPERIMENT_CONTRACT,
        "forbidden_families": list(RUNNER.FORBIDDEN_FAMILIES),
        "live_source_provenance_root": str(ROOT),
        "per_arm_tool_identities": per_arm_tools,
        "purpose": RUNNER.MANIFEST_PURPOSE,
        "repository_git_tool_identity": _existing_identity_with_mode(GIT_PATH),
        "repository_head": REPOSITORY_HEAD,
        "repository_root": str(ROOT),
        "run_nonce": "fixture-run-a001",
        "runner_tool_identity": _existing_identity(RUNNER_PATH),
        "runtime_parameters": {
            "attach_iteration": 1001,
            "attach_trigger": "binding_infeasible",
            "binding_alt_cap": 200,
            "binding_seconds": 600,
            "ghost_rect": [6, 6],
            "master_seconds": 900,
            "max_iterations": 30,
            "post_attach_seconds": 120,
            "routing_seconds": 600,
        },
        "schema_version": RUNNER.FORMAL_MANIFEST_SCHEMA,
        "sealed_snapshot_execution_root": str(snapshot_root),
        "seed": 2026072301,
        "snapshot_manifest_identity": _detached(snapshot_manifest_identity),
        "snapshot_materialization_receipt_identity": _detached(snapshot_receipt_identity),
        "unit_names": unit_names,
        "workers": 1,
    }
    manifest_path = prospective / "manifest-a001.json"
    manifest_identity = _authority(manifest_path, manifest)
    slot = f"{configuration}-{order}-{arm}"
    enabled = [] if arm == "control" else list(RUNNER.CONFIGURATION_FAMILIES[configuration])
    attempt_dir = Path(attempts[slot])
    attempt_dir.mkdir()
    pre_run_path = attempt_dir / "pre-run-authority.json"
    selection_path = attempt_dir / "selection.json"
    execution_source = LIFECYCLE.build_sealed_execution_source(
        live_source_provenance_root=str(ROOT),
        sealed_snapshot_execution_root=str(snapshot_root),
        snapshot_manifest_identity=_detached(snapshot_manifest_identity),
        snapshot_materialization_receipt_identity=_detached(snapshot_receipt_identity),
        package_id=str(package_seal_identity["sha256"]),
        literal_identity={
            "sha256": hashlib.sha256(selected_literal.encode()).hexdigest(),
            "size_bytes": len(selected_literal.encode()),
        },
        python_identity=selected_python_identity,
        loader_identity=selected_loader_identity,
        authority_identity=selected_authority_identity,
        native_helper_wrapper_identity=None,
        native_helper_identity=None,
        selected_byte_schema=LIFECYCLE.SELECTED_BYTE_LAUNCH_SCHEMA_V1,
        runner_snapshot_relative_path=runner_relative,
        runner_snapshot_member_identity=snapshot_runner_identity,
        runner_package_tool_identity=_existing_identity_with_mode(RUNNER_PATH),
        initial_working_directory=str(root),
        pre_run_authority_path=str(pre_run_path),
        runner_selection_path=str(selection_path),
        module_origin_receipt_path=str(attempt_dir / "module-origin-receipt.json"),
        tmpdir=str(attempt_dir / "tmp"),
    )
    pre_run_authority_identity = _authority(
        pre_run_path,
        {
            "attempt_dir": str(attempt_dir),
            "authorizations": {
                "organic_arm_launch_authorized": False,
                "solver_run_authorized": False,
            },
            "launch": {
                "execution_source": execution_source,
            },
            "package": authority_chain["package"],
            "pre_run_authority_path": str(pre_run_path),
            "purpose": "fixture-nonauthorizing-pre-run-authority",
            "repository_head": REPOSITORY_HEAD,
            "repository_root": str(ROOT),
            "runner_selection_path": str(selection_path),
            "schema_version": "fixture-pre-run-authority-v1",
            "slot": slot,
            "status": "PASS",
        },
    )
    selection = {
        "arm": arm,
        "arm_binding_identity": bindings[slot],
        "attempt_dir": attempts[slot],
        "authority_chain": authority_chain,
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": True,
            "production_certified_authorized": False,
            "solver_run_authorized": True,
        },
        "baseline_admission_identity": admission_identity,
        "baseline_incumbent_sha256": RUNNER.semantic_digest(incumbent),
        "campaign_id": manifest["campaign_id"],
        "common_prestate_identity": common_identity,
        "configuration": configuration,
        "enabled_families": enabled,
        "execution_class": "FORMAL_AB16",
        "expected_payload_status": {
            "exit_code": 0,
            "expectation": "SUCCESS",
            "signal": 0,
        },
        "fresh_process_required": True,
        "live_source_provenance_root": manifest["live_source_provenance_root"],
        "manifest_identity": manifest_identity,
        "order": order,
        "pre_run_authority_identity": pre_run_authority_identity,
        "purpose": RUNNER.SELECTION_PURPOSE,
        "repository_git_tool_identity": manifest["repository_git_tool_identity"],
        "repository_head": manifest["repository_head"],
        "repository_root": manifest["repository_root"],
        "run_nonce": manifest["run_nonce"],
        "schema_version": RUNNER.SELECTION_SCHEMA,
        "sealed_snapshot_execution_root": manifest[
            "sealed_snapshot_execution_root"
        ],
        "seed": manifest["seed"],
        "selection_nonce": f"selection-{slot}",
        "snapshot_manifest_identity": manifest["snapshot_manifest_identity"],
        "snapshot_materialization_receipt_identity": manifest[
            "snapshot_materialization_receipt_identity"
        ],
        "slot": slot,
        "unit_name": unit_names[slot],
        "workers": 1,
    }
    _authority(selection_path, selection)
    return {
        "attempt_dir": attempt_dir,
        "bindings": bindings,
        "common_path": Path(common_identity["path"]),
        "execution_source": execution_source,
        "incumbent": incumbent,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "selection": selection,
        "selection_path": selection_path,
        "snapshot_root": snapshot_root,
        "snapshot_runner": snapshot_runner,
    }


def _rewrite_authority(path: Path, value: object) -> dict[str, object]:
    path.write_bytes(RUNNER.canonical_json(value))
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def test_treatment_records_every_compiled_cut_and_attach_hook(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    hooks = FakeHooks(
        fixture["incumbent"],
        cuts=(_compiled_cut(1), _compiled_cut(2)),
        attach_rounds=2,
    )
    result = RUNNER._run_with_hooks(
        fixture["selection_path"],
        hooks,
        enforce_single_process_use=False,
    )
    assert hooks.construct_env is None
    assert hooks.attach_env == "1"
    assert hooks.enabled_families == ("region_capacity",)
    assert hooks.repository_root == fixture["snapshot_root"]
    assert hooks.workers == 1
    assert result["cut_activity"] == {
        "applied": 2,
        "compiled": 2,
        "generated": 2,
    }
    assert result["schema_version"] == RUNNER.RESULT_SCHEMA
    assert result["evidence"]["journal_event_counts"] == {
        "ATTACH_HOOK_BEGIN": 2,
        "ATTACH_HOOK_END": 2,
        "COMPILED_CUT": 2,
        "FIRST_ATTACH_SOLUTION_VERIFIED": 1,
        "GENESIS": 1,
        "JOURNAL_SEAL": 1,
    }
    events, _identity = RUNNER._read_journal(fixture["attempt_dir"] / "compile-attach-journal.jsonl")
    compiled = [event["payload"] for event in events if event["event"] == "COMPILED_CUT"]
    assert [item["cut_id"] for item in compiled] == [
        "fixture-cut-1",
        "fixture-cut-2",
    ]
    assert result["raw_metrics"]["branches"] == 45
    assert result["raw_proof_summary"]["fixture_only"] is True
    assert result["incumbent_export"]["present"] is True
    incumbent_path = Path(result["incumbent_export"]["incumbent_identity"]["path"])
    vector_path = Path(result["incumbent_export"]["solution_vector_identity"]["path"])
    assert json.loads(incumbent_path.read_text(encoding="utf-8")) == fixture["incumbent"]
    assert json.loads(vector_path.read_text(encoding="utf-8")) == [0, 1]
    assert result["authorizations"] == {
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_runtime_effect_authorized": False,
        "production_certified_authorized": False,
    }
    assert CONTRACT.classify_cut_activity(result["cut_activity"])["activation_class"] == CONTRACT.ORGANIC_APPLIED


def test_budgeted_arm_uses_only_immutable_backend_outputs(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    for suffix, mode in RUNNER.BUDGET_ARM_DIRECTORY_SUFFIX_MODES:
        path = fixture["attempt_dir"] / suffix
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(mode)
    backend = _BudgetBackend(fixture)
    result = RUNNER._run_with_hooks(
        fixture["selection_path"],
        FakeHooks(
            fixture["incumbent"],
            cuts=(_compiled_cut(1),),
        ),
        enforce_single_process_use=False,
        budget_backend=backend,
    )
    assert result["cut_activity"] == {
        "applied": 1,
        "compiled": 1,
        "generated": 1,
    }
    assert result["schema_version"] == RUNNER.FORMAL_RESULT_SCHEMA
    assert result["budget_authority_binding"] == backend.authority_binding
    assert result["evidence"]["cut_ledger_identity"]["schema_version"] == (
        RUNNER.BUDGET_SEGMENT_BUNDLE_SCHEMA
    )
    assert result["evidence"]["compile_attach_journal_identity"]["schema_version"] == (
        RUNNER.BUDGET_SEGMENT_BUNDLE_SCHEMA
    )
    assert set(path.name for path in fixture["attempt_dir"].iterdir()) == {
        "checkpoint",
        "ledger",
        "pre-run-authority.json",
        "replays",
        "runtime",
        "selection.json",
        "tmp",
    }
    assert backend.sequences
    assert all(record["size_bytes"] >= 0 for record in backend.records)


def test_budgeted_arm_rejects_writable_tmp_before_any_publication(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    for suffix, mode in RUNNER.BUDGET_ARM_DIRECTORY_SUFFIX_MODES:
        path = fixture["attempt_dir"] / suffix
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700 if suffix == "tmp" else mode)
    backend = _BudgetBackend(fixture)
    with pytest.raises(RUNNER.RunnerError, match="tmp mode/identity drifted"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            FakeHooks(fixture["incumbent"]),
            enforce_single_process_use=False,
            budget_backend=backend,
        )
    assert backend.records == []


@pytest.mark.parametrize(
    "backend_result",
    [
        RuntimeError("O_TRUNC export failed"),
        RuntimeError("RLIMIT_FSIZE exceeded"),
        RuntimeError("final memfd seal failed"),
        {
            "path": "/wrong/model.pb",
            "sha256": "0" * 64,
            "size_bytes": 1,
        },
    ],
)
def test_budgeted_model_export_failures_never_fall_back_to_path_write(
    tmp_path: Path,
    backend_result: object,
) -> None:
    target = tmp_path / "model.pb"
    with pytest.raises(RUNNER.RunnerError, match="failed closed|receipt differs"):
        RUNNER.ProductionArmHooks._export_model(
            object(),
            target,
            budget_backend=_ModelBudgetBackend(backend_result),
        )
    assert not target.exists()


def test_broker_process_backend_uses_sealed_descriptor_for_all_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formal = tmp_path / "formal"
    attempt = formal / "arms" / "arm-01"
    attempt.mkdir(parents=True)
    helper = _NativeMemfdHelper()
    broker = _BrokerClient(helper)
    allocation_sha256 = hashlib.sha256(b"allocation").hexdigest()
    binding = {
        "arm_allocation_id": allocation_sha256,
        "arm_allocation_identity": {
            "sha256": allocation_sha256,
            "size_bytes": len(b"allocation"),
        },
        "arm_slot": "arm-01",
        "broker_nonce": broker.nonce,
        "broker_socket_fd": broker.connection.fileno(),
        "filesystem_write_confinement": RUNNER.BUDGET_WORKER_CONFINEMENT,
        "formal_budget_authority_identity": _write(
            tmp_path / "budget-authority.json",
            b"authority",
        ),
        "next_sequence": 1,
    }
    maxima = {
        label: {
            "artifact_class": artifact_class,
            "branch": "common",
            "maximum_bytes": 4096,
            "maximum_publications": (
                0 if label.endswith("segment") else 1
            ),
            "multiplicity_source": {},
            "path_contract": {},
        }
        for label, artifact_class in RUNNER.BUDGET_ARTIFACT_CLASS_BY_LABEL.items()
    }
    maxima["organic arm result"]["path_contract"] = {
        "kind": "fixed",
        "root": "formal-root",
        "root_relative_path": "arms/arm-01/result.json",
    }
    maxima["AB16 immediate stop"]["path_contract"] = {
        "kind": "fixed",
        "root": "formal-root",
        "root_relative_path": "prospective/immediate-stop-a001.json",
    }
    backend = RUNNER.BrokerProcessArmBudgetBackend(
        broker_client=broker,
        native_helper=helper,
        formal_root=formal,
        attempt_root=attempt,
        expected_calibration_tool_identities={
            role: {
                "sha256": hashlib.sha256(role.encode("ascii")).hexdigest(),
                "size_bytes": len(role),
            }
            for role in RUNNER.CALIBRATION_TOOL_ROLES
        },
        authority_binding=binding,
        fixed_maxima=maxima,
        channel_contracts={
            "arm-arm-01-compile-journal": {
                "artifact_class": "ledger",
                "label": "compile attach journal segment",
                "maximum_bytes": 4096,
                "maximum_segments": 221,
                "relative_path": (
                    "arms/arm-01/ledger/compile-attach-journal"
                ),
            },
            "arm-arm-01-cut-ledger": {
                "artifact_class": "ledger",
                "label": "cut ledger segment",
                "maximum_bytes": 4096,
                "maximum_segments": 258,
                "relative_path": "arms/arm-01/ledger/cut-ledger",
            },
            "arm-arm-01-runtime-cuts": {
                "artifact_class": "ledger",
                "label": "runtime cut segment",
                "maximum_bytes": 4096,
                "maximum_segments": 0,
                "relative_path": "arms/arm-01/checkpoint/runtime-cuts",
            },
        },
    )
    try:
        publication = backend.publish_bytes(
            attempt / "result.json",
            b'{"status":"fixture"}\n',
            maximum_bytes=4096,
            artifact_class="publication",
            label="organic arm result",
        )
        immediate_stop = backend.publish_bytes(
            formal / "prospective/immediate-stop-a001.json",
            b'{"status":"STOP"}\n',
            maximum_bytes=4096,
            artifact_class="closeout",
            label="AB16 immediate stop",
        )
        with pytest.raises(
            RUNNER.RunnerError,
            match="differs from its fixed target",
        ):
            backend.publish_bytes(
                attempt / "immediate-stop-a001.json",
                b'{"status":"STOP"}\n',
                maximum_bytes=4096,
                artifact_class="closeout",
                label="AB16 immediate stop",
            )
        segment = backend.append_segment(
            "arm-arm-01-cut-ledger",
            0,
            b'{"event":"GENESIS"}\n',
            maximum_bytes=4096,
            artifact_class="ledger",
            arm_slot="arm-01",
        )
        limit_updates: list[tuple[int, int]] = []
        monkeypatch.setattr(
            RUNNER.resource,
            "getrlimit",
            lambda _kind: (16_384, 65_536),
        )
        monkeypatch.setattr(
            RUNNER.resource,
            "setrlimit",
            lambda _kind, limits: limit_updates.append(limits),
        )
        model = backend.export_model_to_sealed_memfd(
            _OTruncModel(),
            attempt / "runtime" / "model.pb",
            maximum_bytes=4096,
            label="attach model evidence",
        )
    finally:
        broker.close()
    assert publication["path"] == str(attempt / "result.json")
    assert immediate_stop["path"] == str(
        formal / "prospective/immediate-stop-a001.json"
    )
    assert segment["path"].endswith("/ledger/cut-ledger/segment-00000000.bin")
    assert model["path"] == str(attempt / "runtime" / "model.pb")
    assert broker.published == [
        b'{"status":"fixture"}\n',
        b'{"status":"STOP"}\n',
        b'{"event":"GENESIS"}\n',
        b"tiny-model",
    ]
    assert limit_updates == [(4096, 65_536), (16_384, 65_536)]


def test_broker_process_backend_rejects_nonfixed_channel_layout(
    tmp_path: Path,
) -> None:
    formal = tmp_path / "formal"
    attempt = formal / "arms" / "arm-01"
    attempt.mkdir(parents=True)
    helper = _NativeMemfdHelper()
    broker = _BrokerClient(helper)
    allocation_sha256 = hashlib.sha256(b"allocation").hexdigest()
    binding = {
        "arm_allocation_id": allocation_sha256,
        "arm_allocation_identity": {
            "sha256": allocation_sha256,
            "size_bytes": len(b"allocation"),
        },
        "arm_slot": "arm-01",
        "broker_nonce": broker.nonce,
        "broker_socket_fd": broker.connection.fileno(),
        "filesystem_write_confinement": RUNNER.BUDGET_WORKER_CONFINEMENT,
        "formal_budget_authority_identity": _write(
            tmp_path / "budget-authority.json",
            b"authority",
        ),
        "next_sequence": 1,
    }
    maxima = {
        label: {
            "artifact_class": artifact_class,
            "branch": "common",
            "maximum_bytes": 4096,
            "maximum_publications": (
                0 if label.endswith("segment") else 1
            ),
            "multiplicity_source": {},
            "path_contract": {},
        }
        for label, artifact_class in RUNNER.BUDGET_ARTIFACT_CLASS_BY_LABEL.items()
    }
    try:
        with pytest.raises(
            RUNNER.RunnerError,
            match="differs from fixed arm layout",
        ):
            RUNNER.BrokerProcessArmBudgetBackend(
                broker_client=broker,
                native_helper=helper,
                formal_root=formal,
                attempt_root=attempt,
                expected_calibration_tool_identities={
                    role: {
                        "sha256": hashlib.sha256(
                            role.encode("ascii")
                        ).hexdigest(),
                        "size_bytes": len(role),
                    }
                    for role in RUNNER.CALIBRATION_TOOL_ROLES
                },
                authority_binding=binding,
                fixed_maxima=maxima,
                channel_contracts={
                    "arm-arm-01-cut-ledger": {
                        "artifact_class": "ledger",
                        "label": "cut ledger segment",
                        "maximum_bytes": 4096,
                        "maximum_segments": 258,
                        "relative_path": (
                            "arms/arm-01/ledger/cut-ledger"
                        ),
                    },
                },
            )
    finally:
        broker.close()


def test_production_adapter_observes_natural_runtime_without_manual_attach() -> None:
    construct_source = inspect.getsource(RUNNER.ProductionArmHooks.construct)
    run_source = inspect.getsource(RUNNER.ProductionArmHooks.run_attach_phase)
    assert "run_with_status" not in construct_source
    assert "run_with_status()" in run_source
    tree = ast.parse(textwrap.dedent(run_source))
    protected_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_maybe_attach_framework_cuts"
    ]
    assert protected_calls == []
    assert "attach_trigger" not in run_source
    assert "attach_iteration" not in run_source


def test_control_also_opens_attach_with_empty_family_set(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, arm="control")
    hooks = FakeHooks(fixture["incumbent"])
    result = RUNNER._run_with_hooks(
        fixture["selection_path"],
        hooks,
        enforce_single_process_use=False,
    )
    assert hooks.construct_env is None
    assert hooks.attach_env == "1"
    assert hooks.enabled_families == ()
    assert result["enabled_families"] == []
    assert result["cut_activity"] == {
        "applied": 0,
        "compiled": 0,
        "generated": 0,
    }
    assert CONTRACT.classify_cut_activity(result["cut_activity"])["activation_class"] == CONTRACT.ORGANIC_NONACTIVATION


def _lineage_fixture() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    plan = {
        "digest": "1" * 64,
        "family": "region_capacity",
        "semantic_fingerprint": "2" * 64,
    }
    ledger = [
        {
            "cut_id": "cut-1",
            "event": "GENERATED",
            "family": "region_capacity",
        },
        {
            "cut_id": "cut-1",
            "event": "APPLIED",
            "family": "region_capacity",
            "plan_digest": plan["digest"],
            "semantic_fingerprint": plan["semantic_fingerprint"],
        },
    ]
    journal = [
        {
            "event": "COMPILED_CUT",
            "payload": {
                "cut_id": "cut-1",
                "plan": plan,
            },
        },
    ]
    return ledger, journal


def test_runner_lineage_rejects_self_consistent_wrong_family() -> None:
    ledger, journal = _lineage_fixture()
    ledger[0]["family"] = "power_hitting_set"
    ledger[1]["family"] = "power_hitting_set"
    journal[0]["payload"]["plan"]["family"] = "power_hitting_set"
    with pytest.raises(RUNNER.RunnerError, match="enabled families"):
        RUNNER._join_ledger_and_journal(  # noqa: SLF001
            ledger,
            journal,
            enabled_families=["region_capacity"],
        )


def test_runner_lineage_rejects_compiled_without_generated_join() -> None:
    ledger, journal = _lineage_fixture()
    ledger.pop(0)
    with pytest.raises(RUNNER.RunnerError, match="GENERATED join"):
        RUNNER._join_ledger_and_journal(  # noqa: SLF001
            ledger,
            journal,
            enabled_families=["region_capacity"],
        )


def test_runner_lineage_rejects_duplicate_applied_consumption() -> None:
    ledger, journal = _lineage_fixture()
    ledger.append(dict(ledger[-1]))
    with pytest.raises(RUNNER.RunnerError, match="unique allowed COMPILED"):
        RUNNER._join_ledger_and_journal(  # noqa: SLF001
            ledger,
            journal,
            enabled_families=["region_capacity"],
        )


def test_formal_hook_without_raw_model_evidence_fails_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, arm="control")
    hooks = EvidenceRequiredHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="lacks raw model evidence"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is True


def test_no_incumbent_exports_explicit_none_branch(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, arm="control")
    result = RUNNER._run_with_hooks(
        fixture["selection_path"],
        FakeHooks(fixture["incumbent"], export_solution=False),
        enforce_single_process_use=False,
    )
    assert result["incumbent_export"] == {
        "incumbent_identity": None,
        "present": False,
        "solution_vector_identity": None,
    }
    assert not (fixture["attempt_dir"] / "raw-incumbent.json").exists()
    assert not (fixture["attempt_dir"] / "raw-solution-vector.json").exists()


def test_first_attach_solution_must_match_baseline_before_hook(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    hooks = FakeHooks(fixture["incumbent"], wrong_solution=True)
    with pytest.raises(
        RUNNER.RunnerError,
        match="first attach solution differs",
    ):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    journal = (fixture["attempt_dir"] / "compile-attach-journal.jsonl").read_text(encoding="utf-8")
    assert "ATTACH_HOOK_BEGIN" not in journal
    failure = json.loads((fixture["attempt_dir"] / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "CREDIBILITY_INCOMPLETE"
    assert failure["authorizations"]["mathematical_claim_authorized"] is False


def test_pattern_nogood_or_nonexact_treatment_set_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["selection"]["enabled_families"] = [
        "region_capacity",
        "pattern_nogood",
    ]
    _rewrite_authority(fixture["selection_path"], fixture["selection"])
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="enabled family set"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False
    assert {path.name for path in fixture["attempt_dir"].iterdir()} == {
        "pre-run-authority.json",
        "selection.json",
    }


def test_formal_arithmetic_purpose_cannot_be_replaced_by_drill(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["manifest"]["arithmetic_verifier"]["purpose"] = "gate1_v4_disposable_drill_arithmetic"
    manifest_identity = _rewrite_authority(
        fixture["manifest_path"],
        fixture["manifest"],
    )
    fixture["selection"]["manifest_identity"] = manifest_identity
    _rewrite_authority(fixture["selection_path"], fixture["selection"])
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="formal arithmetic-verifier"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False


def test_resource_contract_mutation_is_rejected_before_arm(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    changed = json.loads(json.dumps(RUNNER.EXPERIMENT_CONTRACT))
    changed["resource_contract"]["memory_max_bytes"] -= 1
    fixture["manifest"]["experiment_contract"] = changed
    manifest_identity = _rewrite_authority(
        fixture["manifest_path"],
        fixture["manifest"],
    )
    fixture["selection"]["manifest_identity"] = manifest_identity
    _rewrite_authority(fixture["selection_path"], fixture["selection"])
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="experiment contract"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False


def test_runtime_guard_is_exactly_one_hour() -> None:
    assert RUNNER.EXPERIMENT_CONTRACT["budget"]["arm_hard_guard_seconds"] == 3600
    assert RUNNER.EXPERIMENT_CONTRACT["resource_contract"]["runtime_max_sec"] == 3600


def test_resource_verifier_tool_drift_is_rejected_before_arm(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    verifier = Path(fixture["manifest"]["per_arm_tool_identities"]["resource_verifier"]["path"])
    verifier.write_bytes(verifier.read_bytes() + b"# drift\n")
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="identity replay failed"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False


def test_pre_run_authority_identity_drift_is_rejected_before_arm(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    pre_run = Path(fixture["selection"]["pre_run_authority_identity"]["path"])
    pre_run.write_bytes(pre_run.read_bytes() + b" ")
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="identity replay failed"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False


def test_self_consistent_but_failed_pre_run_authority_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    pre_run = Path(fixture["selection"]["pre_run_authority_identity"]["path"])
    value = json.loads(pre_run.read_text(encoding="utf-8"))
    value["status"] = "FAIL_CLOSED"
    pre_run_identity = _rewrite_authority(pre_run, value)
    fixture["selection"]["pre_run_authority_identity"] = pre_run_identity
    _rewrite_authority(fixture["selection_path"], fixture["selection"])
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="selection replay failed"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False


def test_unregistered_prelaunch_file_is_rejected_before_arm(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    (fixture["attempt_dir"] / "unexpected").write_text("drift", encoding="utf-8")
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="prelaunch contents drifted"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False


def test_selection_purpose_must_be_formal_not_drill(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["selection"]["purpose"] = "disposable_drill"
    _rewrite_authority(fixture["selection_path"], fixture["selection"])
    with pytest.raises(RUNNER.RunnerError, match="scalar semantics"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            FakeHooks(fixture["incumbent"]),
            enforce_single_process_use=False,
        )


def test_attach_env_leak_fails_before_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    hooks = FakeHooks(fixture["incumbent"])
    monkeypatch.setenv(RUNNER.ATTACH_ENV, "1")
    with pytest.raises(RUNNER.RunnerError, match="absent before construction"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False


def test_binding_drift_fails_before_runner_owned_attempt_outputs(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    binding = Path(fixture["selection"]["arm_binding_identity"]["path"])
    binding.write_bytes(binding.read_bytes() + b" ")
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="identity replay failed"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False
    assert {path.name for path in fixture["attempt_dir"].iterdir()} == {
        "pre-run-authority.json",
        "selection.json",
    }


def test_symlink_authority_is_rejected(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"{}\n")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(RUNNER.RunnerError, match="no-symlink input"):
        RUNNER.snapshot_regular(link, label="fixture link")


def test_attempt_directory_is_no_overwrite(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, arm="control")
    first = FakeHooks(fixture["incumbent"])
    RUNNER._run_with_hooks(
        fixture["selection_path"],
        first,
        enforce_single_process_use=False,
    )
    before = {
        path.relative_to(fixture["attempt_dir"]): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in fixture["attempt_dir"].rglob("*")
        if path.is_file()
    }
    second = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="prelaunch contents drifted"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            second,
            enforce_single_process_use=False,
        )
    after = {
        path.relative_to(fixture["attempt_dir"]): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in fixture["attempt_dir"].rglob("*")
        if path.is_file()
    }
    assert before == after
    assert second.constructed is False


def test_strict_manifest_extra_key_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["manifest"]["unexpected"] = False
    manifest_identity = _rewrite_authority(
        fixture["manifest_path"],
        fixture["manifest"],
    )
    fixture["selection"]["manifest_identity"] = manifest_identity
    _rewrite_authority(fixture["selection_path"], fixture["selection"])
    with pytest.raises(RUNNER.RunnerError, match="exact key set"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            FakeHooks(fixture["incumbent"]),
            enforce_single_process_use=False,
        )


def test_noncanonical_selection_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    value = fixture["selection"]
    fixture["selection_path"].write_text(
        json.dumps(value, indent=2),
        encoding="utf-8",
    )
    with pytest.raises(RUNNER.RunnerError, match="not canonical"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            FakeHooks(fixture["incumbent"]),
            enforce_single_process_use=False,
        )


def test_compiled_observation_outside_attach_hook_fails_closed(
    tmp_path: Path,
) -> None:
    journal = RUNNER.HashChainJournal(
        tmp_path / "journal.jsonl",
        genesis={"fixture": True},
    )
    recorder = RUNNER.CompileAttachRecorder(
        journal,
        expected_solution_digest=RUNNER.semantic_digest(_incumbent()),
        require_model_evidence=False,
    )
    recorder.authorize_first_attach_solution(_incumbent())
    with pytest.raises(RUNNER.RunnerError, match="outside an attach hook"):
        recorder.record_compiled_cut(_compiled_cut())
    journal.abort()


def test_required_raw_model_evidence_joins_one_open_hook(
    tmp_path: Path,
) -> None:
    journal = RUNNER.HashChainJournal(
        tmp_path / "journal.jsonl",
        genesis={"fixture": True},
    )
    incumbent = _incumbent()
    recorder = RUNNER.CompileAttachRecorder(
        journal,
        expected_solution_digest=RUNNER.semantic_digest(incumbent),
        require_model_evidence=True,
    )
    with recorder.attach_hook(
        trigger="binding_infeasible",
        iteration=1001,
        solution=incumbent,
    ) as completion:
        pre = _write(tmp_path / "pre.pb", b"pre-model")
        post = _write(tmp_path / "post.pb", b"post-model")
        vector = _authority(tmp_path / "solution.json", [0, 1])
        recorder.record_attach_model_evidence(
            completion.hook_id,
            pre_model_identity=pre,
            post_model_identity=post,
            solution_vector_identity=vector,
        )
        completion.returned(0)
    recorder.finalize()
    journal.seal()
    events, _ = RUNNER._read_journal(journal.path)
    evidence = [event for event in events if event["event"] == "ATTACH_MODEL_EVIDENCE"]
    assert len(evidence) == 1
    assert evidence[0]["payload"]["pre_model_identity"] == pre
    assert evidence[0]["payload"]["post_model_identity"] == post
    assert evidence[0]["payload"]["solution_vector_identity"] == vector


def test_public_entry_is_single_use_per_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, arm="control")
    hooks = FakeHooks(fixture["incumbent"])
    monkeypatch.setattr(RUNNER, "_PUBLIC_RUN_STARTED", False)
    RUNNER._run_with_hooks(
        fixture["selection_path"],
        hooks,
        enforce_single_process_use=True,
    )
    with pytest.raises(RUNNER.RunnerError, match="fresh process"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            FakeHooks(fixture["incumbent"]),
            enforce_single_process_use=True,
        )


def _clear_src_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(sys.modules):
        if name == "src" or name.startswith("src."):
            monkeypatch.delitem(sys.modules, name, raising=False)


def test_initial_import_boundary_rejects_preloaded_and_live_checkout_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, arm="control")
    source = fixture["execution_source"]
    snapshot_root = fixture["snapshot_root"]
    monkeypatch.chdir(snapshot_root)
    monkeypatch.setattr(RUNNER, "__file__", str(fixture["snapshot_runner"]))
    _clear_src_modules(monkeypatch)
    monkeypatch.setattr(
        sys,
        "path",
        [str(snapshot_root), "/usr/lib/python3.13"],
    )
    RUNNER._assert_initial_import_boundary(source)

    ambient = ModuleType("src.ambient")
    ambient.__file__ = str(ROOT / "src/ambient.py")
    monkeypatch.setitem(sys.modules, "src.ambient", ambient)
    with pytest.raises(RUNNER.RunnerError, match="preloaded"):
        RUNNER._assert_initial_import_boundary(source)
    monkeypatch.delitem(sys.modules, "src.ambient")

    monkeypatch.setattr(
        sys,
        "path",
        [str(snapshot_root), str(ROOT), "/usr/lib/python3.13"],
    )
    with pytest.raises(RUNNER.RunnerError, match="live checkout"):
        RUNNER._assert_initial_import_boundary(source)


def test_module_origin_audit_rejects_outside_file_and_package_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, arm="control")
    source = fixture["execution_source"]
    snapshot_src = fixture["snapshot_root"] / "src"
    snapshot_src.mkdir()
    good_path = snapshot_src / "good.py"
    good_path.write_text("# sealed fixture\n", encoding="utf-8")
    _clear_src_modules(monkeypatch)
    package = ModuleType("src")
    package.__path__ = [str(snapshot_src)]
    good = ModuleType("src.good")
    good.__file__ = str(good_path)
    monkeypatch.setitem(sys.modules, "src", package)
    monkeypatch.setitem(sys.modules, "src.good", good)
    observations = RUNNER._audit_src_module_origins(source)
    assert {item["module"] for item in observations} == {"src", "src.good"}

    bad = ModuleType("src.bad")
    bad.__file__ = str(ROOT / "src/bad.py")
    monkeypatch.setitem(sys.modules, "src.bad", bad)
    with pytest.raises(RUNNER.RunnerError, match="outside the sealed snapshot"):
        RUNNER._audit_src_module_origins(source)
