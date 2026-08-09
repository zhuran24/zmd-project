from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import textwrap
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724" / "organic_arm_runner_v1.py"
CONTRACT_PATH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724" / "ab16_contract_v1.py"
GATE_PATH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724" / "ab16_terminal_gate_v1.py"
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
GATE = _load(GATE_PATH, "noncert_cuts_ab16_terminal_gate_for_runner_test")


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


def _authority_compact(path: Path, value: object) -> dict[str, object]:
    return _write(path, RUNNER._canonical_compact(value))


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
        self.workers: int | None = None

    def construct(self, context: object) -> object:
        self.constructed = True
        self.construct_env = os.environ.get(RUNNER.ATTACH_ENV)
        self.enabled_families = context.enabled_families
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


class FakeProductionMaster:
    def __init__(
        self,
        incumbent: dict[str, object],
        *,
        solve_status: str,
        solve_wall_time: float,
        solution_vector: list[int],
    ) -> None:
        self._incumbent = incumbent
        self._solve_status = solve_status
        self._solve_wall_time = solve_wall_time
        self._solver = SimpleNamespace(
            ResponseProto=lambda: SimpleNamespace(
                best_objective_bound=0.0,
                deterministic_time=1.25,
                num_binary_propagations=11,
                num_booleans=2,
                num_branches=13,
                num_conflicts=17,
                num_integer_propagations=19,
                objective_value=0.0,
                solution=list(solution_vector),
                user_time=solve_wall_time,
                wall_time=solve_wall_time,
            )
        )
        self.model = SimpleNamespace(
            Proto=lambda: SimpleNamespace(variables=[object() for _item in solution_vector]),
            export_to_file=self._export_model,
        )
        self.build_stats: dict[str, object] = {}

    @staticmethod
    def _export_model(path: str) -> bool:
        Path(path).write_bytes(b"fixture production model")
        return True

    def solve(self, *, time_limit_seconds: float, **_kwargs: object) -> str:
        self.build_stats["last_solve"] = {
            "binary_propagations": 11,
            "branches": 13,
            "conflicts": 17,
            "deterministic_time": 1.25,
            "integer_propagations": 19,
            "status": self._solve_status,
            "user_time": self._solve_wall_time,
            "wall_time": self._solve_wall_time,
        }
        assert time_limit_seconds == 900
        return self._solve_status

    def extract_solution(self) -> dict[str, object]:
        return self._incumbent


class FakeProductionController:
    def __init__(
        self,
        master: FakeProductionMaster,
        *,
        controller_status: str,
        proof_summary: dict[str, object],
        attach_solution: dict[str, object] | None = None,
    ) -> None:
        self.master = master
        self.controller_status = controller_status
        self.proof_summary = proof_summary
        self.attach_solution = attach_solution
        self.last_proof_summary: dict[str, object] | None = None

    @staticmethod
    def _maybe_attach_framework_cuts(
        *,
        trigger: str,
        iteration: int,
        solution: dict[str, object],
    ) -> int:
        del trigger, iteration, solution
        return 0

    def run_with_status(self) -> tuple[str, dict[str, object] | None]:
        self.master.solve(time_limit_seconds=900)
        if self.attach_solution is not None:
            self._maybe_attach_framework_cuts(
                trigger="binding_infeasible",
                iteration=1,
                solution=self.attach_solution,
            )
        self.last_proof_summary = dict(self.proof_summary)
        return self.controller_status, None


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
    execution_tools: dict[str, dict[str, object]] = {}
    input_tools: dict[str, dict[str, object]] = {}
    code_roles = {
        "ab16_contract",
        "ab16_terminal_gate",
        "organic_arm_replay",
        "organic_arm_runner",
        "organic_resource_lifecycle",
        "organic_resource_verifier",
        "organic_unit_orchestrator",
    }
    for role in sorted(RUNNER.EXECUTION_TOOL_ROLES):
        if role == "organic_arm_runner":
            path = RUNNER_PATH
        else:
            raw = f"# pinned {role} fixture\n".encode()
            if role == "organic_resource_lifecycle":
                raw = textwrap.dedent(
                    """
                    def validate_pre_run_authority(value, **kwargs):
                        del kwargs
                        if value.get("status") != "PASS":
                            raise ValueError("pre-run authority did not pass")
                        return value

                    def validate_runner_selection(
                        value,
                        *,
                        pre_run_authority,
                        pre_run_authority_identity,
                        **kwargs,
                    ):
                        del kwargs
                        if value.get("pre_run_authority_identity") != pre_run_authority_identity:
                            raise ValueError("pre-run identity mismatch")
                        if pre_run_authority.get("slot") != value.get("slot"):
                            raise ValueError("pre-run slot mismatch")
                        return value
                    """
                ).encode()
            path = root / "tools" / f"{role}.py"
            _write(path, raw)
        execution_tools[role] = _existing_identity_with_mode(path)
        if role in code_roles:
            input_tools[role] = execution_tools[role]
    package_manifest_identity = _authority(
        root / "authority" / "package-manifest.json",
        {"schema_version": "fixture-package-manifest-v1"},
    )
    package_seal_identity = _write(
        root / "authority" / "SHA256SUMS",
        b"fixture immutable package seal\n",
    )
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
    campaign_provenance = {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "campaign_root_identity": authority_chain["campaign_root_identity"],
        "git_identity": _existing_identity(GIT_PATH),
        "import_mode": "tracked_clean_pinned_checkout",
        "input_identities": {},
        "package": authority_chain["package"],
        "repository_head": REPOSITORY_HEAD,
        "repository_root": str(ROOT),
        "repository_tree": "b" * 40,
        "schema_version": "noncert-cuts-ab16-tracked-clean-checkout-provenance-v1",
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
        "campaign_provenance": campaign_provenance,
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
            "campaign_provenance": campaign_provenance,
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
        "rebuilt_model": {
            "canonical_binary": True,
            "identity": {},
            "metadata": {"campaign_provenance": campaign_provenance},
            "model_backend": "CpModelProto",
            "model_binary_format": "deterministic-protobuf-v1",
        },
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
    preregistration_path = prospective / "path-preregistration.json"
    preregistration_identity = _authority(
        preregistration_path,
        {"schema_version": "fixture-preregistration-v1"},
    )
    preregistration_identity_with_mode = _existing_identity_with_mode(preregistration_path)
    scientific_input_set_sha256 = "7" * 64
    scientific_materialization_sha256 = "8" * 64
    manifest = {
        "arm_sequence": list(RUNNER.ARM_SEQUENCE),
        "configuration_families": {key: list(value) for key, value in RUNNER.CONFIGURATION_FAMILIES.items()},
        "experiment_contract": RUNNER.EXPERIMENT_CONTRACT,
        "forbidden_families": list(RUNNER.FORBIDDEN_FAMILIES),
        "preregistration_sha256": preregistration_identity["sha256"],
        "purpose": RUNNER.MANIFEST_PURPOSE,
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
        "schema_version": RUNNER.MANIFEST_SCHEMA,
        "scientific_input_set_sha256": scientific_input_set_sha256,
        "scientific_materialization_sha256": scientific_materialization_sha256,
        "seed": 2026072301,
        "workers": 1,
    }
    manifest_path = prospective / "manifest-a001.json"
    manifest_identity = _authority_compact(manifest_path, manifest)
    suite_selection = {
        "arm_sequence": list(RUNNER.ARM_SEQUENCE),
        "authorizations": {
            "cut_authorized": False,
            "family_global_soundness_authorized": False,
            "global_claim_authorized": False,
            "lower_bound_authorized": False,
            "mathematical_claim_authorized": False,
            "optimality_authorized": False,
            "production_certified_authorized": False,
            "stage_b_promotion_authorized": False,
            "upper_bound_authorized": False,
            "witness_authorized": False,
        },
        "manifest_identity": manifest_identity,
        "preregistration_sha256": preregistration_identity["sha256"],
        "purpose": "AB16_SUITE_SELECTION_NO_ARM_LAUNCH",
        "schema_version": RUNNER.SUITE_SELECTION_SCHEMA,
        "scientific_input_set_sha256": scientific_input_set_sha256,
        "scientific_materialization_sha256": scientific_materialization_sha256,
        "selection_id": "",
        "status": "PASS",
    }
    suite_selection["selection_id"] = hashlib.sha256(RUNNER._canonical_compact(suite_selection)).hexdigest()
    suite_selection_path = prospective / "selection-a001.json"
    suite_selection_identity = _authority_compact(suite_selection_path, suite_selection)
    slot = f"{configuration}-{order}-{arm}"
    enabled = [] if arm == "control" else list(RUNNER.CONFIGURATION_FAMILIES[configuration])
    authority_attempt_dir = arms_parent / slot / "attempt-0001"
    attempt_dir = authority_attempt_dir / "run"
    support_dir = authority_attempt_dir / "support"
    attempt_dir.mkdir(parents=True)
    support_dir.mkdir()
    strict_inputs = {
        "baseline_admission": _existing_identity_with_mode(Path(admission_identity["path"])),
        "baseline_incumbent": _existing_identity_with_mode(Path(incumbent_identity["path"])),
        "common_prestate": _existing_identity_with_mode(Path(common_identity["path"])),
        "scientific_manifest": _existing_identity_with_mode(manifest_path),
        "suite_selection": _existing_identity_with_mode(suite_selection_path),
        f"arm_binding.{slot}": _existing_identity_with_mode(Path(bindings[slot]["path"])),
    }
    input_set_sha256 = RUNNER._attempt_input_set_digest(
        preregistration_sha256=preregistration_identity["sha256"],
        repository_head=REPOSITORY_HEAD,
        strict_inputs=strict_inputs,
        tools=input_tools,
    )
    research_only = dict(suite_selection["authorizations"])
    input_set_path = authority_attempt_dir / "attempt-input-set.json"
    _authority_compact(
        input_set_path,
        {
            "authorizations": research_only,
            "input_set_sha256": input_set_sha256,
            "preregistration_identity": preregistration_identity_with_mode,
            "preregistration_sha256": preregistration_identity["sha256"],
            "repository_head": REPOSITORY_HEAD,
            "schema_version": RUNNER.INPUT_SET_SCHEMA,
            "scientific_input_set_sha256": scientific_input_set_sha256,
            "scientific_materialization_sha256": scientific_materialization_sha256,
            "source_strict_input_identities": strict_inputs,
            "source_tool_identities": input_tools,
            "strict_input_identities": strict_inputs,
            "tool_identities": input_tools,
        },
    )
    unit_name = f"cuts-fixture-ab16-{slot}-a0001.service"
    execution = {
        "attempt_ordinal": 1,
        "authorizations": research_only,
        "authority_attempt_dir": str(authority_attempt_dir.resolve()),
        "authority_chain": authority_chain,
        "campaign_id": "a" * 64,
        "campaign_root_identity": authority_chain["campaign_root_identity"],
        "continuation_identity": authority_chain["continuation_identity"],
        "input_set_identity": _existing_identity_with_mode(input_set_path),
        "input_set_sha256": input_set_sha256,
        "manager_epoch": {
            "attestation_toolchain": {"python": execution_tools["attestor_python"]},
            "fixture": "manager-epoch",
        },
        "manifest_identity": manifest_identity,
        "package": authority_chain["package"],
        "pre_run_authority_path": str((attempt_dir / "pre-run-authority.json").resolve()),
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_git_tool_identity": _existing_identity_with_mode(GIT_PATH),
        "repository_head": REPOSITORY_HEAD,
        "repository_root": str(ROOT),
        "run_dir": str(attempt_dir.resolve()),
        "run_nonce": "fixture-run-a001",
        "schema_version": RUNNER.ATTEMPT_EXECUTION_SCHEMA,
        "scientific_input_set_sha256": scientific_input_set_sha256,
        "scientific_materialization_sha256": scientific_materialization_sha256,
        "selection_path": str((attempt_dir / "selection.json").resolve()),
        "slot": slot,
        "status": "READY",
        "suite_selection_identity": suite_selection_identity,
        "support_dir": str(support_dir.resolve()),
        "tool_identities": execution_tools,
        "unit_name": unit_name,
    }
    execution_path = authority_attempt_dir / "attempt-execution.json"
    execution_identity = _authority_compact(execution_path, execution)
    pre_run_authority_identity = _authority_compact(
        attempt_dir / "pre-run-authority.json",
        {
            "attempt_execution_identity": execution_identity,
            "attempt_ordinal": 1,
            "authorizations": {
                "organic_arm_launch_authorized": False,
                "solver_run_authorized": False,
            },
            "epoch_observation_paths": {
                "launch": str((attempt_dir / "manager-epoch-launch.json").resolve()),
            },
            "epoch_transcript_paths": {
                "launch": str((attempt_dir / "manager-transcript-launch.json").resolve()),
            },
            "preregistration_sha256": preregistration_identity["sha256"],
            "purpose": "fixture-nonauthorizing-pre-run-authority",
            "schema_version": RUNNER.PRE_RUN_SCHEMA,
            "slot": slot,
            "status": "PASS",
        },
    )
    selection = {
        "arm": arm,
        "arm_binding_identity": bindings[slot],
        "attempt_execution_identity": execution_identity,
        "attempt_dir": str(attempt_dir.resolve()),
        "attempt_ordinal": 1,
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
        "campaign_id": execution["campaign_id"],
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
        "manifest_identity": manifest_identity,
        "order": order,
        "pre_run_authority_identity": pre_run_authority_identity,
        "preregistration_sha256": preregistration_identity["sha256"],
        "purpose": RUNNER.SELECTION_PURPOSE,
        "repository_git_tool_identity": execution["repository_git_tool_identity"],
        "repository_head": execution["repository_head"],
        "repository_root": execution["repository_root"],
        "run_nonce": execution["run_nonce"],
        "schema_version": RUNNER.SELECTION_SCHEMA,
        "seed": manifest["seed"],
        "selection_nonce": f"selection-{slot}",
        "slot": slot,
        "unit_name": unit_name,
        "workers": 1,
    }
    selection_path = attempt_dir / "selection.json"
    _authority_compact(selection_path, selection)
    _authority_compact(attempt_dir / "manager-epoch-launch.json", {"phase": "launch"})
    _authority_compact(attempt_dir / "manager-transcript-launch.json", {"phase": "launch"})
    return {
        "attempt_dir": attempt_dir,
        "bindings": bindings,
        "common_path": Path(common_identity["path"]),
        "execution": execution,
        "execution_path": execution_path,
        "incumbent": incumbent,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "selection": selection,
        "selection_path": selection_path,
    }


def _rewrite_authority(path: Path, value: object) -> dict[str, object]:
    path.write_bytes(RUNNER._canonical_compact(value))
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
    assert hooks.workers == 1
    assert result["cut_activity"] == {
        "applied": 2,
        "compiled": 2,
        "generated": 2,
    }
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


def test_baseline_admission_joins_source_identity_to_relocated_attempt_snapshot(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    admission_path = Path(fixture["selection"]["baseline_admission_identity"]["path"])
    admission = json.loads(admission_path.read_text(encoding="utf-8"))
    source_identity = admission["fixed_assignment_replay"]["incumbent_identity"]
    source_path = Path(source_identity["path"])
    relocated_path = tmp_path / "attempt-snapshot" / "baseline-incumbent.json"
    relocated_identity = _write(relocated_path, source_path.read_bytes())

    assert RUNNER._validate_baseline_admission(  # noqa: SLF001
        admission,
        baseline_incumbent_identity=relocated_identity,
        baseline_incumbent_source_identity=_existing_identity_with_mode(source_path),
        selection=fixture["selection"],
    ) == fixture["selection"]["baseline_incumbent_sha256"]

    alternate_source = tmp_path / "alternate-source" / "baseline-incumbent.json"
    _write(alternate_source, source_path.read_bytes())
    with pytest.raises(RUNNER.RunnerError, match="source input"):
        RUNNER._validate_baseline_admission(  # noqa: SLF001
            admission,
            baseline_incumbent_identity=relocated_identity,
            baseline_incumbent_source_identity=_existing_identity_with_mode(alternate_source),
            selection=fixture["selection"],
        )

    drifted_identity = _authority(
        tmp_path / "drifted-snapshot" / "baseline-incumbent.json",
        {"not": "the admitted incumbent"},
    )
    with pytest.raises(RUNNER.RunnerError, match="source bytes"):
        RUNNER._validate_baseline_admission(  # noqa: SLF001
            admission,
            baseline_incumbent_identity=drifted_identity,
            baseline_incumbent_source_identity=_existing_identity_with_mode(source_path),
            selection=fixture["selection"],
        )


@pytest.mark.parametrize("mutation", ("missing", "replay", "metadata"))
def test_baseline_admission_requires_one_campaign_provenance_join(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = _fixture(tmp_path)
    admission_path = Path(fixture["selection"]["baseline_admission_identity"]["path"])
    admission = json.loads(admission_path.read_text(encoding="utf-8"))
    source_path = Path(admission["fixed_assignment_replay"]["incumbent_identity"]["path"])
    if mutation == "missing":
        admission.pop("campaign_provenance")
        message = "exact key set"
    elif mutation == "replay":
        admission["fixed_assignment_replay"]["campaign_provenance"] = {"drifted": True}
        message = "provenance join"
    else:
        admission["rebuilt_model"]["metadata"]["campaign_provenance"] = {"drifted": True}
        message = "provenance join"
    with pytest.raises(RUNNER.RunnerError, match=message):
        RUNNER._validate_baseline_admission(  # noqa: SLF001
            admission,
            baseline_incumbent_identity=_existing_identity(source_path),
            baseline_incumbent_source_identity=_existing_identity_with_mode(source_path),
            selection=fixture["selection"],
        )


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


@pytest.mark.parametrize(
    ("proof_summary", "expected_evidence"),
    (
        pytest.param(
            {
                "binding_alternative_cap": 200,
                "binding_status": "ALT_CAP_REACHED",
                "master_status": "FEASIBLE",
                "routing_status": "PRECHECK_FRONT_BLOCKED",
            },
            {
                "internal_budget_reached": True,
                "kind": "binding_alt_cap",
                "limit": 200,
                "observed": {
                    "binding_alternative_cap": 200,
                    "binding_status": "ALT_CAP_REACHED",
                },
            },
            id="exact-contract-cap",
        ),
        pytest.param(
            {
                "binding_alternative_cap": 200,
                "binding_status": "ALT_CAP_REACHED",
                "master_status": "FEASIBLE",
                "routing_status": "INFEASIBLE",
            },
            {
                "internal_budget_reached": True,
                "kind": "binding_alt_cap",
                "limit": 200,
                "observed": {
                    "binding_alternative_cap": 200,
                    "binding_status": "ALT_CAP_REACHED",
                },
            },
            id="exact-cap-independent-of-routing-status",
        ),
        pytest.param(
            {
                "binding_alternative_cap": 199,
                "binding_status": "ALT_CAP_REACHED",
                "routing_status": "TIMEOUT",
            },
            {
                "internal_budget_reached": False,
                "kind": "none",
                "limit": None,
                "observed": {},
            },
            id="drifted-cap-does-not-fall-through",
        ),
        pytest.param(
            {
                "binding_alternative_cap": 200.0,
                "binding_status": "ALT_CAP_REACHED",
                "routing_status": "TIMEOUT",
            },
            {
                "internal_budget_reached": False,
                "kind": "none",
                "limit": None,
                "observed": {},
            },
            id="float-cap-does-not-fall-through",
        ),
        pytest.param(
            {
                "binding_alternative_cap": "200",
                "binding_status": "ALT_CAP_REACHED",
            },
            {
                "internal_budget_reached": False,
                "kind": "none",
                "limit": None,
                "observed": {},
            },
            id="string-cap",
        ),
        pytest.param(
            {
                "binding_alternative_cap": True,
                "binding_status": "ALT_CAP_REACHED",
            },
            {
                "internal_budget_reached": False,
                "kind": "none",
                "limit": None,
                "observed": {},
            },
            id="boolean-cap",
        ),
        pytest.param(
            {"binding_status": "ALT_CAP_REACHED"},
            {
                "internal_budget_reached": False,
                "kind": "none",
                "limit": None,
                "observed": {},
            },
            id="missing-cap",
        ),
    ),
)
def test_binding_alt_cap_censor_requires_exact_contract_integer(
    proof_summary: dict[str, object],
    expected_evidence: dict[str, object],
) -> None:
    terminal = RUNNER._controller_terminal_record(  # noqa: SLF001
        controller_status="UNKNOWN",
        proof_summary=proof_summary,
        master_last_solve={},
        master_solve_history=[],
    )

    assert terminal["budget_censor_evidence"] == expected_evidence


def test_binding_alt_cap_runner_output_passes_independent_terminal_gate() -> None:
    proof_summary = {
        "binding_alternative_cap": 200,
        "binding_status": "ALT_CAP_REACHED",
        "master_status": "FEASIBLE",
    }
    terminal = RUNNER._controller_terminal_record(  # noqa: SLF001
        controller_status="UNKNOWN",
        proof_summary=proof_summary,
        master_last_solve={},
        master_solve_history=[],
    )

    replayed = GATE._controller_terminal(  # noqa: SLF001
        terminal,
        experiment_contract=RUNNER.EXPERIMENT_CONTRACT,
        controller_proof_summary=proof_summary,
    )

    assert replayed["credibility_status"] == GATE.CREDIBILITY_PASS
    assert replayed["failure_reasons"] == []
    assert replayed["solver_terminal_class"] == GATE.BUDGET_CENSORED_UNKNOWN


def test_generic_unknown_remains_uncensored_in_runner() -> None:
    terminal = RUNNER._controller_terminal_record(  # noqa: SLF001
        controller_status="UNKNOWN",
        proof_summary={"master_status": "FEASIBLE"},
        master_last_solve={},
        master_solve_history=[],
    )

    assert terminal["budget_censor_evidence"] == {
        "internal_budget_reached": False,
        "kind": "none",
        "limit": None,
        "observed": {},
    }


@pytest.mark.parametrize(
    ("kind", "proof_summary", "master_solve_history", "expected_observed"),
    (
        (
            "binding_seconds",
            {"binding_status": "TIMEOUT"},
            [],
            {"binding_status": "TIMEOUT"},
        ),
        (
            "routing_seconds",
            {"routing_status": "TIMEOUT"},
            [],
            {"routing_status": "TIMEOUT"},
        ),
        (
            "max_iterations",
            {"benders_iterations": 30, "master_status": "MAX_ITERATIONS"},
            [],
            {"benders_iterations": 30, "master_status": "MAX_ITERATIONS"},
        ),
        (
            "master_seconds",
            {"master_status": "UNKNOWN"},
            [
                {
                    "binary_propagations": 0,
                    "branches": 0,
                    "conflicts": 0,
                    "deterministic_time": 0.0,
                    "integer_propagations": 0,
                    "ordinal": 1,
                    "requested_time_limit_seconds": 900.0,
                    "status": "UNKNOWN",
                    "user_time": 900.0,
                    "wall_time": 900.0,
                }
            ],
            {
                "master_status": "UNKNOWN",
                "solver_status": "UNKNOWN",
                "wall_time": 900.0,
            },
        ),
    ),
)
def test_existing_controller_budget_censors_are_unchanged(
    kind: str,
    proof_summary: dict[str, object],
    master_solve_history: list[dict[str, object]],
    expected_observed: dict[str, object],
) -> None:
    terminal = RUNNER._controller_terminal_record(  # noqa: SLF001
        controller_status="UNKNOWN",
        proof_summary=proof_summary,
        master_last_solve={},
        master_solve_history=master_solve_history,
    )
    expected_limits = {
        "binding_seconds": 600,
        "master_seconds": 900,
        "max_iterations": 30,
        "routing_seconds": 600,
    }

    assert terminal["budget_censor_evidence"] == {
        "internal_budget_reached": True,
        "kind": kind,
        "limit": expected_limits[kind],
        "observed": expected_observed,
    }


@pytest.mark.parametrize(
    (
        "terminal_stage",
        "controller_status",
        "master_status",
        "proof_summary",
        "solve_wall_time",
        "solution_vector",
        "expected_budget_kind",
    ),
    (
        (
            "master-infeasible",
            "INFEASIBLE",
            "INFEASIBLE",
            {"benders_iterations": 1, "master_status": "INFEASIBLE"},
            2.0,
            [],
            "none",
        ),
        (
            "master-budget",
            "UNKNOWN",
            "UNKNOWN",
            {"benders_iterations": 1, "master_status": "UNKNOWN"},
            900.0,
            [],
            "master_seconds",
        ),
        (
            "binding-budget",
            "UNKNOWN",
            "FEASIBLE",
            {
                "benders_iterations": 1,
                "binding_status": "TIMEOUT",
                "master_status": "FEASIBLE",
            },
            3.0,
            [0, 1],
            "binding_seconds",
        ),
        (
            "binding-alt-cap-budget",
            "UNKNOWN",
            "FEASIBLE",
            {
                "benders_iterations": 1,
                "binding_alternative_cap": 200,
                "binding_status": "ALT_CAP_REACHED",
                "master_status": "FEASIBLE",
                "routing_status": "INFEASIBLE",
            },
            3.0,
            [0, 1],
            "binding_alt_cap",
        ),
        (
            "routing-budget",
            "UNKNOWN",
            "FEASIBLE",
            {
                "benders_iterations": 1,
                "binding_status": "FEASIBLE",
                "master_status": "FEASIBLE",
                "routing_status": "TIMEOUT",
            },
            4.0,
            [0, 1],
            "routing_seconds",
        ),
        (
            "routing-certified",
            "CERTIFIED",
            "FEASIBLE",
            {
                "benders_iterations": 1,
                "binding_status": "FEASIBLE",
                "master_status": "FEASIBLE",
                "routing_status": "FEASIBLE",
            },
            5.0,
            [0, 1],
            "none",
        ),
    ),
)
def test_production_zero_hook_controller_terminals_publish_complete_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal_stage: str,
    controller_status: str,
    master_status: str,
    proof_summary: dict[str, object],
    solve_wall_time: float,
    solution_vector: list[int],
    expected_budget_kind: str,
) -> None:
    fixture = _fixture(tmp_path, arm="control")
    master = FakeProductionMaster(
        fixture["incumbent"],
        solve_status=master_status,
        solve_wall_time=solve_wall_time,
        solution_vector=solution_vector,
    )
    runtime = RUNNER._ProductionRuntime(  # noqa: SLF001
        controller=FakeProductionController(
            master,
            controller_status=controller_status,
            proof_summary=proof_summary,
        ),
        master=master,
    )
    hooks = RUNNER.ProductionArmHooks()
    monkeypatch.setattr(hooks, "construct", lambda _context: runtime)

    result = RUNNER._run_with_hooks(  # noqa: SLF001
        fixture["selection_path"],
        hooks,
        enforce_single_process_use=False,
    )

    assert result["raw_solver_status"] == controller_status
    terminal = result["controller_terminal"]
    assert terminal["controller_status"] == controller_status
    assert terminal["master_solve_history"] == [
        {
            "binary_propagations": 11,
            "branches": 13,
            "conflicts": 17,
            "deterministic_time": 1.25,
            "integer_propagations": 19,
            "ordinal": 1,
            "requested_time_limit_seconds": 900.0,
            "status": master_status,
            "user_time": solve_wall_time,
            "wall_time": solve_wall_time,
        }
    ]
    assert terminal["budget_censor_evidence"]["kind"] == expected_budget_kind
    assert result["incumbent_export"]["present"] is bool(solution_vector)
    if solution_vector:
        incumbent_path = Path(result["incumbent_export"]["incumbent_identity"]["path"])
        vector_path = Path(result["incumbent_export"]["solution_vector_identity"]["path"])
        assert json.loads(incumbent_path.read_text(encoding="utf-8")) == fixture["incumbent"]
        assert json.loads(vector_path.read_text(encoding="utf-8")) == solution_vector
    else:
        assert result["incumbent_export"] == {
            "incumbent_identity": None,
            "present": False,
            "solution_vector_identity": None,
        }
    published = json.loads((fixture["attempt_dir"] / "result.json").read_text(encoding="utf-8"))
    assert published["raw_solver_status"] == controller_status
    assert published["controller_terminal"] == terminal
    assert published["incumbent_export"] == result["incumbent_export"]
    assert not (fixture["attempt_dir"] / "failure.json").exists()

    journal_events, _identity = RUNNER._read_journal(  # noqa: SLF001
        fixture["attempt_dir"] / "compile-attach-journal.jsonl"
    )
    assert [event["event"] for event in journal_events] == [
        "GENESIS",
        "JOURNAL_SEAL",
    ], terminal_stage
    assert journal_events[-1]["payload"]["event_counts_before_seal"] == {"GENESIS": 1}
    ledger_path = next((fixture["attempt_dir"] / "ledger").rglob("segment_*.jsonl"))
    ledger_seal = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[-1])
    assert ledger_seal["event"] == "SEGMENT_SEAL"
    assert ledger_seal["attach_hook_count"] == 0
    assert ledger_seal["first_attach_solution_authorized"] is False
    assert ledger_seal["runner_completed"] is True


def test_production_first_real_attach_still_requires_baseline_incumbent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    wrong_solution = json.loads(json.dumps(fixture["incumbent"]))
    wrong_solution["machine_001"]["pose_idx"] = 99
    master = FakeProductionMaster(
        fixture["incumbent"],
        solve_status="FEASIBLE",
        solve_wall_time=2.0,
        solution_vector=[0, 1],
    )
    runtime = RUNNER._ProductionRuntime(  # noqa: SLF001
        controller=FakeProductionController(
            master,
            controller_status="UNKNOWN",
            proof_summary={"binding_status": "INFEASIBLE", "master_status": "FEASIBLE"},
            attach_solution=wrong_solution,
        ),
        master=master,
    )
    hooks = RUNNER.ProductionArmHooks()
    monkeypatch.setattr(hooks, "construct", lambda _context: runtime)

    with pytest.raises(RUNNER.RunnerError, match="first attach solution differs"):
        RUNNER._run_with_hooks(  # noqa: SLF001
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )

    journal = (fixture["attempt_dir"] / "compile-attach-journal.jsonl").read_text(encoding="utf-8")
    assert "FIRST_ATTACH_SOLUTION_VERIFIED" not in journal
    assert "ATTACH_HOOK_BEGIN" not in journal


def test_production_hooked_terminal_records_authorized_join_in_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    master = FakeProductionMaster(
        fixture["incumbent"],
        solve_status="FEASIBLE",
        solve_wall_time=2.0,
        solution_vector=[0, 1],
    )
    runtime = RUNNER._ProductionRuntime(  # noqa: SLF001
        controller=FakeProductionController(
            master,
            controller_status="UNKNOWN",
            proof_summary={"binding_status": "INFEASIBLE", "master_status": "FEASIBLE"},
            attach_solution=fixture["incumbent"],
        ),
        master=master,
    )
    hooks = RUNNER.ProductionArmHooks()
    monkeypatch.setattr(hooks, "construct", lambda _context: runtime)

    result = RUNNER._run_with_hooks(  # noqa: SLF001
        fixture["selection_path"],
        hooks,
        enforce_single_process_use=False,
    )

    assert result["evidence"]["journal_event_counts"]["FIRST_ATTACH_SOLUTION_VERIFIED"] == 1
    assert result["evidence"]["journal_event_counts"]["ATTACH_HOOK_BEGIN"] == 1
    journal_events, _identity = RUNNER._read_journal(  # noqa: SLF001
        fixture["attempt_dir"] / "compile-attach-journal.jsonl"
    )
    assert [event["event"] for event in journal_events] == [
        "GENESIS",
        "FIRST_ATTACH_SOLUTION_VERIFIED",
        "ATTACH_HOOK_BEGIN",
        "ATTACH_MODEL_EVIDENCE",
        "ATTACH_HOOK_END",
        "JOURNAL_SEAL",
    ]
    ledger_path = next((fixture["attempt_dir"] / "ledger").rglob("segment_*.jsonl"))
    ledger_seal = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[-1])
    assert ledger_seal["attach_hook_count"] == 1
    assert ledger_seal["first_attach_solution_authorized"] is True
    assert ledger_seal["runner_completed"] is True


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
        "manager-epoch-launch.json",
        "manager-transcript-launch.json",
        "pre-run-authority.json",
        "selection.json",
    }


def test_scientific_manifest_contains_no_attempt_topology(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    assert RUNNER.validate_manifest(fixture["manifest"]) == fixture["manifest"]
    assert not {
        "attempt_dirs",
        "unit_names",
        "repository_head",
        "repository_root",
        "authority_chain",
        "per_arm_tool_identities",
    } & set(fixture["manifest"])


def test_resource_contract_mutation_is_rejected_before_arm(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    changed = json.loads(json.dumps(RUNNER.EXPERIMENT_CONTRACT))
    changed["resource_contract"]["memory_max_bytes"] -= 1
    fixture["manifest"]["experiment_contract"] = changed
    with pytest.raises(RUNNER.RunnerError, match="experiment contract"):
        RUNNER.validate_manifest(fixture["manifest"])


def test_runtime_guard_is_exactly_one_hour() -> None:
    assert RUNNER.EXPERIMENT_CONTRACT["budget"]["arm_hard_guard_seconds"] == 3600
    assert RUNNER.EXPERIMENT_CONTRACT["resource_contract"]["runtime_max_sec"] == 3600


def test_experiment_contract_canonical_digest_is_locked() -> None:
    assert (
        hashlib.sha256(RUNNER.canonical_json(RUNNER.EXPERIMENT_CONTRACT)).hexdigest()
        == "24b45e110952505e6ffa92d3ddfdf33874cc3cb4503397e993898e79174ded9e"
    )


def test_resource_verifier_tool_drift_is_rejected_before_arm(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    verifier = Path(fixture["execution"]["tool_identities"]["organic_resource_verifier"]["path"])
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


def test_missing_orchestrator_launch_receipt_is_rejected_before_arm(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    (fixture["attempt_dir"] / "manager-epoch-launch.json").unlink()
    hooks = FakeHooks(fixture["incumbent"])
    with pytest.raises(RUNNER.RunnerError, match="prelaunch contents drifted"):
        RUNNER._run_with_hooks(
            fixture["selection_path"],
            hooks,
            enforce_single_process_use=False,
        )
    assert hooks.constructed is False


def test_isolated_python_installs_replayed_repository_before_src_import() -> None:
    program = textwrap.dedent(
        f"""
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("isolated_ab16_runner", {str(RUNNER_PATH)!r})
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module._install_repository_import_root({str(ROOT)!r})
        from src.cuts.ledger import CutLedgerWriter
        assert CutLedgerWriter.__name__ == "CutLedgerWriter"
        """
    )
    completed = subprocess.run(
        (sys.executable, "-I", "-c", program),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    run_source = inspect.getsource(RUNNER._run_with_hooks)
    assert run_source.index("_install_repository_import_root") < run_source.index("from src.cuts.ledger")


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
        "manager-epoch-launch.json",
        "manager-transcript-launch.json",
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
    with pytest.raises(RUNNER.RunnerError, match="exact key set"):
        RUNNER.validate_manifest(fixture["manifest"])


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


def test_zero_hook_finalization_rejects_pre_authorized_solution(
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
        require_model_evidence=False,
    )
    recorder.authorize_first_attach_solution(incumbent)
    with pytest.raises(RUNNER.RunnerError, match="authorized without an attach hook"):
        recorder.finalize()
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
