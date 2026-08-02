from __future__ import annotations

import base64
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
import copy
import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

from google.protobuf import text_format
from ortools.sat import cp_model_pb2
from ortools.sat.python import cp_model


ROOT = Path(__file__).resolve().parents[2]
AB16_RELATIVE = Path("docs/research/noncert_cuts_ab16_20260724")
GATE1_RELATIVE = Path("docs/research/noncert_cuts_ab_trust_gate1_v4_20260724")
T0 = "2026-08-02T23:40:00Z"
T1 = "2026-08-02T23:41:00Z"
T2 = "2026-08-02T23:42:00Z"
BOOT_ID = "11111111-2222-3333-4444-555555555555"


def _command(
    arguments: Sequence[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
) -> bytes:
    completed = subprocess.run(
        list(arguments),
        cwd=cwd,
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert completed.returncode == 0, (
        f"command failed: {arguments!r}\n"
        f"stdout={completed.stdout.decode(errors='replace')}\n"
        f"stderr={completed.stderr.decode(errors='replace')}"
    )
    return completed.stdout


def _clean_checkout(tmp_path: Path) -> Path:
    """Commit the review tree and restore its one ignored hash-pinned preregistration artifact."""

    checkout = tmp_path / "checkout"
    _command(("git", "clone", "--no-local", "--quiet", str(ROOT), str(checkout)))
    patch = _command(("git", "diff", "--binary", "HEAD", "--"), cwd=ROOT)
    if patch:
        _command(("git", "apply", "--binary", "--whitespace=nowarn", "-"), cwd=checkout, input_bytes=patch)

    # candidate_placements is the workflow's one permitted preregistration
    # supply. Repository governance deliberately omits its 54 MB from a
    # lightweight clone, so admit it only through the tracked manifest pin.
    external_manifest_path = checkout / "data/external_artifacts.json"
    external_manifest = json.loads(external_manifest_path.read_text(encoding="utf-8"))
    assert set(external_manifest) == {"artifacts", "description", "schema_version"}
    entries = [
        entry
        for entry in external_manifest["artifacts"]
        if entry.get("id") == "candidate_placements"
    ]
    assert len(entries) == 1
    entry = entries[0]
    assert set(entry) == {
        "id",
        "optional_in_lightweight_checkout",
        "path",
        "required_for",
        "restore_hints",
        "sha256",
        "size_bytes",
    }
    assert entry["path"] == "data/preprocessed/candidate_placements.json"
    assert entry["size_bytes"] == 54_467_709
    assert entry["sha256"] == "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    candidate_source = ROOT / entry["path"]
    candidate_target = checkout / entry["path"]

    def pinned_identity(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                size += len(block)
                digest.update(block)
        return size, digest.hexdigest()

    expected = (entry["size_bytes"], entry["sha256"])
    assert pinned_identity(candidate_source) == expected
    candidate_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_source, candidate_target)
    assert pinned_identity(candidate_target) == expected
    _command(("git", "add", "-A"), cwd=checkout)
    staged = subprocess.run(
        ("git", "diff", "--cached", "--quiet"),
        cwd=checkout,
        check=False,
    )
    assert staged.returncode in {0, 1}
    if staged.returncode == 1:
        _command(
            (
                "git",
                "-c",
                "user.name=AB16 R12 Sentinel",
                "-c",
                "user.email=ab16-r12-sentinel.invalid",
                "commit",
                "--quiet",
                "-m",
                "test(ab16): materialize r12 sentinel checkout",
            ),
            cwd=checkout,
        )
    tracked_candidate = subprocess.run(
        ("git", "ls-files", "--error-unmatch", entry["path"]),
        cwd=checkout,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert tracked_candidate.returncode == 1
    _command(("git", "check-ignore", "--quiet", entry["path"]), cwd=checkout)
    assert _command(("git", "status", "--porcelain=v1"), cwd=checkout) == b""
    return checkout


@contextmanager
def _load_checkout_modules(checkout: Path, temporary_root: Path) -> Iterator[SimpleNamespace]:
    """Load the clean checkout without leaking its bare module aliases to other tests."""

    bare_names = {
        "ab16_authority_v1",
        "ab16_campaign_bootstrap_v1",
        "ab16_contract_v1",
        "ab16_terminal_gate_v1",
        "baseline_admission_v1",
        "baseline_rebuild_v1",
        "campaign_authority_v4",
        "cut_free_incumbent_replay_v1",
        "organic_arm_replay_v1",
        "organic_arm_runner_v1",
        "organic_resource_lifecycle_v1",
        "organic_resource_verifier_v1",
        "organic_unit_orchestrator_v1",
    }
    displaced = {
        name: module
        for name, module in list(sys.modules.items())
        if name in bare_names or name == "src" or name.startswith("src.")
    }
    for name in displaced:
        sys.modules.pop(name, None)
    old_path = list(sys.path)
    old_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(checkout), str(checkout / AB16_RELATIVE), str(checkout / GATE1_RELATIVE)]
    try:
        bootstrap = importlib.import_module("ab16_campaign_bootstrap_v1")
        authority = importlib.import_module("ab16_authority_v1")
        admission = importlib.import_module("baseline_admission_v1")
        rebuild = importlib.import_module("baseline_rebuild_v1")
        fixed_replay = importlib.import_module("cut_free_incumbent_replay_v1")
        yield SimpleNamespace(
            admission=admission,
            authority=authority,
            bootstrap=bootstrap,
            fixed_replay=fixed_replay,
            gate1=bootstrap.authority,
            rebuild=rebuild,
        )
    finally:
        sys.path[:] = old_path
        sys.dont_write_bytecode = old_dont_write_bytecode
        for name, module in list(sys.modules.items()):
            module_file = getattr(module, "__file__", None)
            if module_file is None:
                continue
            try:
                belongs_to_test = Path(module_file).resolve().is_relative_to(temporary_root.resolve())
            except (OSError, ValueError):
                belongs_to_test = False
            if belongs_to_test:
                sys.modules.pop(name, None)
        for name in bare_names | {name for name in displaced if name == "src" or name.startswith("src.")}:
            sys.modules.pop(name, None)
        sys.modules.update(displaced)


def _load_pinned_module(identity: Mapping[str, object], label: str) -> ModuleType:
    path = Path(str(identity["path"]))
    assert path.is_file()
    name = f"_ab16_r12_sentinel_{label}_{identity['sha256']}"
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    specification = importlib.util.spec_from_loader(name, loader)
    assert specification is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def _detached(identity: Mapping[str, object]) -> dict[str, object]:
    return {field: identity[field] for field in ("path", "sha256", "size_bytes")}


def _system_tools() -> dict[str, Path]:
    selected_python = (ROOT / ".venv-uvbolt-backup/bin/python3.13").resolve(strict=True)
    result = {
        "attestor_python": selected_python,
        "busctl": Path("/usr/bin/busctl"),
        "git": Path("/usr/bin/git"),
        "python3_13": selected_python,
        "sudo": Path("/usr/bin/sudo"),
        "systemctl": Path("/usr/bin/systemctl"),
        "systemd_run": Path("/usr/bin/systemd-run"),
    }
    assert all(path.is_file() for path in result.values())
    return result


def _manager_capture(
    gate1: ModuleType,
    *,
    attestor_path: Path,
    system_tools: Mapping[str, Path],
    clock_base_ns: int,
) -> dict[str, object]:
    manager = Path("/usr/lib/systemd/systemd")
    assert manager.is_file()

    def full(path: Path) -> dict[str, object]:
        return gate1.full_identity(gate1.snapshot_regular(path))

    state: dict[str, object] = {
        "boot_id": BOOT_ID,
        "dbus_unique_owner": ":1.77",
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
    }
    attestation = {
        "manager_executable": full(manager),
        "request": {
            "boot_id": state["boot_id"],
            "dbus_unique_owner": state["dbus_unique_owner"],
            "manager_pid": state["manager_pid"],
            "manager_pid_starttime": state["manager_pid_starttime"],
        },
        "schema": gate1.ATTESTOR_SCHEMA,
        "status": "PASS",
    }
    tools = {
        "attestor": full(attestor_path),
        "python": full(system_tools["attestor_python"]),
        "sudo": full(system_tools["sudo"]),
    }
    audit = gate1.audit_attestor_source(attestor_path.read_bytes())
    invocation = {
        "argv": [
            str(system_tools["sudo"]),
            "-n",
            "--",
            str(system_tools["attestor_python"]),
            "-I",
            "-c",
            gate1._LOADER,  # noqa: SLF001 - exact public capture transcript contract
            "--pid",
            str(state["manager_pid"]),
            "--expected-starttime",
            str(state["manager_pid_starttime"]),
            "--expected-boot-id",
            str(state["boot_id"]),
            "--dbus-owner",
            str(state["dbus_unique_owner"]),
        ],
        "exit_code": 0,
        "stdin_sha256": tools["attestor"]["sha256"],
        "stdin_size_bytes": tools["attestor"]["size_bytes"],
        "stdout_base64": base64.b64encode(gate1.canonical_json(attestation)).decode("ascii"),
    }

    def probe(_: str) -> dict[str, object]:
        return copy.deepcopy(state)

    def invoke(
        expected: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        assert dict(expected) == state
        return (
            copy.deepcopy(attestation),
            copy.deepcopy(tools),
            {
                "audit": copy.deepcopy(audit),
                "invocation": copy.deepcopy(invocation),
            },
        )

    ticks = iter(clock_base_ns + offset for offset in (10, 20, 30, 40))
    return gate1.capture_manager_epoch_with_transcript(
        attestor_path=attestor_path,
        busctl_path=system_tools["busctl"],
        python_path=system_tools["attestor_python"],
        sudo_path=system_tools["sudo"],
        probe=probe,
        invoke=invoke,
        monotonic_ns=lambda: next(ticks),
    )


def _mkdir_gate1_topology(gate1: ModuleType, campaign: Path, target: Path) -> None:
    current = campaign
    for member in target.relative_to(campaign).parts:
        current /= member
        if not current.exists() and not current.is_symlink():
            gate1.mkdir_exclusive(current)


def _install_retained_gate1_precondition(
    gate1: ModuleType,
    *,
    campaign: Path,
    root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    capture: Mapping[str, object],
    attestor_path: Path,
    system_tools: Mapping[str, Path],
) -> dict[str, object]:
    """Install the retained Gate1 PASS boundary, not an R12 AB16 chain product.

    This sentinel does not re-qualify Gate1's systemd campaign. Gate1 v4 has no
    public hermetic runtime seam, and AB16 is forbidden to mint a replacement.
    The pre-existing PASS boundary is represented only inside the Gate1
    topology. Gate1's validators cover the manager checkpoint, continuation,
    and identity/path joins, and its O_EXCL writers publish every scaffold
    byte; detached replay payload semantics remain outside this AB16 test.
    """

    root_path = campaign / "campaign-root.json"
    root, selection = gate1.replay_gate1_selection(
        root_path,
        root_identity,
        selection_identity,
        current_manager_epoch=capture["manager_epoch"],
    )
    topology = root["stage_topology"]["gate1_v4"]
    replay_identities: dict[str, object] = {}
    for slot, unit in topology["units"].items():
        replay_path = Path(unit["attempt_dir"]) / "detached-replay.json"
        _mkdir_gate1_topology(gate1, campaign, replay_path.parent)
        replay_identities[slot] = gate1.write_exclusive(
            replay_path,
            gate1.canonical_json({"status": "PASS"}),
        )
        gate1.replay_detached_identity(replay_identities[slot], f"retained Gate1 {slot} replay")

    admission_capture = _manager_capture(
        gate1,
        attestor_path=attestor_path,
        system_tools=system_tools,
        clock_base_ns=100,
    )
    transcript = admission_capture["transcript"]
    selected_tools = {
        role: selection["tools"][role]
        for role in gate1.GATE_ADMISSION_CAPTURE_TOOL_ROLES
    }
    binding = gate1.sha256_bytes(
        gate1.canonical_json(
            {
                "campaign_id": root["campaign_id"],
                "capture_transcript": transcript,
                "phase": "gate-admission",
                "run_nonce": root["run_nonce"],
                "selected_tool_identities": selected_tools,
                "selection_id": selection["selection_id"],
                "unit_slot": "gate-admission",
            }
        )
    )
    checkpoint = {
        "campaign_id": root["campaign_id"],
        "capture_transcript": transcript,
        "captured_at_utc": T1,
        "captured_monotonic_ns": 150,
        "manager_epoch": admission_capture["manager_epoch"],
        "manager_epoch_digest": gate1.sha256_bytes(gate1.canonical_json(root["manager_epoch"])),
        "phase": "gate-admission",
        "run_nonce": root["run_nonce"],
        "schema_version": topology["gate_admission_epoch_schema"],
        "selected_tool_identities": selected_tools,
        "selection_id": selection["selection_id"],
        "transcript_binding_sha256": binding,
        "unit_name": f"{root['unit_namespace']}-gate-admission.authority",
        "unit_slot": "gate-admission",
    }
    gate1.validate_gate_admission_epoch_checkpoint(
        checkpoint,
        root=root,
        selection=selection,
    )
    checkpoint_path = Path(topology["gate_admission_epoch_path"])
    _mkdir_gate1_topology(gate1, campaign, checkpoint_path.parent)
    checkpoint_identity = gate1.write_exclusive(
        checkpoint_path,
        gate1.canonical_json(checkpoint),
    )
    gate_result = {
        "campaign_id": root["campaign_id"],
        "continuation_authorized": False,
        "continuation_eligible": True,
        "gate_admission_epoch_identity": checkpoint_identity,
        "manager_epoch": root["manager_epoch"],
        "mechanism_credible": True,
        "organic_arm_launch_authorized": False,
        "status": "CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS",
    }
    gate_path = Path(topology["gate_path"])
    _mkdir_gate1_topology(gate1, campaign, gate_path.parent)
    gate_identity = gate1.write_exclusive(gate_path, gate1.canonical_json(gate_result))
    continuation = gate1.make_continuation_authorization(
        root,
        campaign_root_identity=root_identity,
        gate1_selection_identity=selection_identity,
        gate_result=gate_result,
        gate_result_identity=gate_identity,
        gate_admission_epoch_identity=checkpoint_identity,
        detached_replay_identities=replay_identities,
        current_manager_epoch=root["manager_epoch"],
        created_at_utc=T2,
    )
    continuation_identity = gate1.write_continuation_authorization(
        root_path,
        root_identity,
        continuation,
    )
    gate1_root = campaign / "gate1-v4"
    prerequisite_paths = [
        Path(checkpoint_identity["path"]),
        Path(gate_identity["path"]),
        Path(continuation_identity["path"]),
        *(Path(identity["path"]) for identity in replay_identities.values()),
    ]
    assert all(path.is_relative_to(gate1_root) for path in prerequisite_paths)
    assert all(not path.is_relative_to(campaign / "prospective-ab16") for path in prerequisite_paths)
    return continuation_identity


def _tiny_baseline(
    admission: ModuleType,
) -> tuple[cp_model_pb2.CpModelProto, dict[str, object], Any, tuple[int, ...]]:
    model = cp_model.CpModel()
    ghost = model.new_bool_var("ghost__0_0_6_6")
    model.add(ghost == 1)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 2026072301
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    incumbent = {
        "ghost_pick": {
            "anchor": {"x": 0, "y": 0},
            "bound_type": "exact",
            "instance_id": "ghost_pick",
            "pose_idx": 0,
        }
    }
    proto = cp_model_pb2.CpModelProto()
    text_format.Parse(str(model.Proto()), proto)
    expectation = admission.BaselineExpectation(
        profile="r12-self-contained-chain-sentinel-v1",
        legacy_size_bytes=507_095,
        legacy_sha256="9e747c214c2108b7fc73fede1d31873b24bf765d74857cf4a846cf5178ebcff6",
        historical_model_text_sha256=admission.historical_model_text_sha256(proto),
        model_variable_count=len(proto.variables),
        model_constraint_count=len(proto.constraints),
        incumbent_sha256=admission.semantic_digest(incumbent),
        incumbent_assignment_count=len(incumbent),
    )
    return proto, incumbent, expectation, (int(solver.value(ghost)),)


class _MicroArmHooks:
    requires_model_evidence = True

    def __init__(self, runner: ModuleType, model: Any, incumbent: Mapping[str, object]) -> None:
        self.runner = runner
        self.model = model
        self.incumbent = incumbent

    def construct(self, context: object) -> object:
        return context

    def run_attach_phase(self, runtime: object, context: Any, recorder: Any) -> object:
        del runtime
        model_raw = self.model.SerializeToString(deterministic=True)
        with recorder.attach_hook(
            trigger="binding_infeasible",
            iteration=1001,
            solution=self.incumbent,
        ) as completion:
            pre_identity = self.runner._write_exclusive(  # noqa: SLF001 - real runner evidence writer
                context.attempt_dir / "runtime/r12-pre-model.bin",
                model_raw,
                label="R12 sentinel pre-attach model",
            )
            post_identity = self.runner._write_exclusive(  # noqa: SLF001 - real runner evidence writer
                context.attempt_dir / "runtime/r12-post-model.bin",
                model_raw,
                label="R12 sentinel post-attach model",
            )
            vector_identity = self.runner._write_exclusive(  # noqa: SLF001 - real runner evidence writer
                context.attempt_dir / "runtime/r12-solution-vector.json",
                self.runner.canonical_json([1]),
                label="R12 sentinel solution vector",
            )
            recorder.record_attach_model_evidence(
                completion.hook_id,
                pre_model_identity=pre_identity,
                post_model_identity=post_identity,
                solution_vector_identity=vector_identity,
            )
            completion.returned(0)
        terminal = {
            "budget_censor_evidence": {
                "internal_budget_reached": False,
                "kind": "none",
                "limit": None,
                "observed": {},
            },
            "controller_completed": True,
            "controller_status": "CERTIFIED",
            "cumulative_deterministic_time": 0.0,
            "master_last_solve": {},
            "master_solve_history": [],
            "schema_version": self.runner.CONTROLLER_TERMINAL_SCHEMA,
        }
        return self.runner.ArmOutcome(
            raw_controller_terminal=terminal,
            raw_incumbent=None,
            raw_metrics={"tiny_solver": True},
            raw_proof_summary={
                "controller_last_proof_summary": {},
                "master_last_solve": {},
            },
            raw_solution_vector=None,
            raw_solver_status="CERTIFIED",
        )


class _RunnerBackedResourceAdapter:
    """Use the real pinned runner writer inside the real resource lifecycle."""

    def __init__(
        self,
        *,
        orchestrator: ModuleType,
        lifecycle: ModuleType,
        runner: ModuleType,
        attempt_dir: Path,
        selection_path: Path,
        hooks: _MicroArmHooks,
    ) -> None:
        self.orchestrator = orchestrator
        self.lifecycle = lifecycle
        self.runner = runner
        self.attempt_dir = attempt_dir
        self.selection_path = selection_path
        self.hooks = hooks
        self.clock = 100
        self.invocation = "0123456789abcdef0123456789abcdef"
        self.keeper_pid = 4100
        self.payload_pid = 4101
        pre_run = lifecycle.strict_loads(
            lifecycle.snapshot_regular(attempt_dir / "pre-run-authority.json").raw,
            "R12 sentinel pre-run authority",
        )
        self.resource_contract = copy.deepcopy(pre_run["resource_contract"])
        self.manager_epoch = copy.deepcopy(pre_run["manager_epoch"])
        self.manager_transcript = copy.deepcopy(
            lifecycle.strict_loads(
                lifecycle.snapshot_regular(pre_run["preselection_transcript_identity"]["path"]).raw,
                "R12 sentinel manager transcript",
            )
        )

    def monotonic_ns(self) -> int:
        self.clock += 100
        return self.clock

    def observe_manager_epoch(self, phase: str) -> object:
        del phase
        return self.orchestrator.EpochCapture(
            manager_epoch=copy.deepcopy(self.manager_epoch),
            transcript=copy.deepcopy(self.manager_transcript),
        )

    def launch_and_wait_for_keeper(
        self,
        *,
        unit_name: str,
        systemd_run_argv: Sequence[str],
        payload_argv: Sequence[str],
    ) -> object:
        assert unit_name.endswith(".service")
        assert systemd_run_argv and payload_argv
        result = self.runner._run_with_hooks(  # noqa: SLF001 - selected real runner seam
            self.selection_path,
            self.hooks,
            enforce_single_process_use=False,
        )
        launch = self.orchestrator.LaunchEvidence(
            invocation_id=self.invocation,
            supervisor_pid=self.keeper_pid,
            supervisor_starttime=77,
            payload_pid=self.payload_pid,
            payload_starttime=78,
            payload_seal_monotonic_ns=300,
            payload_exit_monotonic_ns=400,
            payload_exit_code=0,
            payload_signal=0,
            payload_reaped=True,
            keeper_ready_monotonic_ns=500,
        )
        pre_run_snapshot = self.lifecycle.snapshot_regular(self.attempt_dir / "pre-run-authority.json")
        selection_snapshot = self.lifecycle.snapshot_regular(self.selection_path)
        pre_run = self.lifecycle.strict_loads(pre_run_snapshot.raw, "R12 sentinel pre-run")
        selection = self.lifecycle.strict_loads(selection_snapshot.raw, "R12 sentinel selection")
        launch_epoch_snapshot = self.lifecycle.snapshot_regular(self.attempt_dir / "manager-epoch-launch.json")
        launch_epoch = self.lifecycle.strict_loads(launch_epoch_snapshot.raw, "R12 sentinel launch epoch")
        result_snapshot = self.lifecycle.snapshot_regular(result["result_identity"]["path"])
        assert _detached(result_snapshot.identity) == result["result_identity"]
        inner = self.lifecycle.build_inner_record(
            pre_run,
            pre_run_snapshot.identity,
            selection,
            selection_snapshot.identity,
            invocation_id=launch.invocation_id,
            launch_observation=launch_epoch,
            supervisor_pid=launch.supervisor_pid,
            supervisor_starttime=launch.supervisor_starttime,
            payload_pid=launch.payload_pid,
            payload_starttime=launch.payload_starttime,
            payload_seal_monotonic_ns=launch.payload_seal_monotonic_ns,
            payload_exit_monotonic_ns=launch.payload_exit_monotonic_ns,
            payload_exit_code=launch.payload_exit_code,
            payload_signal=launch.payload_signal,
            payload_reaped=launch.payload_reaped,
            payload_result_identity=result_snapshot.identity,
            keeper_ready_monotonic_ns=launch.keeper_ready_monotonic_ns,
        )
        self.lifecycle.write_json_exclusive(self.attempt_dir / "inner-lifecycle.json", inner)
        return launch

    def capture_preterminal(self, *, unit_name: str, launch: object) -> object:
        del unit_name, launch
        self.clock = 700
        return self.orchestrator.PreterminalEvidence(
            captured_at_monotonic_ns=700,
            systemd_raw={
                "ActiveState": "active",
                "CollectMode": self.resource_contract["collect_mode"],
                "ControlGroup": "/user.slice/ab16-r12-sentinel.scope",
                "InvocationID": self.invocation,
                "KillMode": "control-group",
                "MainPID": str(self.keeper_pid),
                "MemoryHigh": str(self.resource_contract["memory_high_bytes"]),
                "MemoryMax": str(self.resource_contract["memory_max_bytes"]),
                "MemorySwapMax": str(self.resource_contract["memory_swap_max_bytes"]),
                "OOMPolicy": "continue",
                "RuntimeMaxUSec": str(self.resource_contract["runtime_max_seconds"] * 1_000_000),
                "SendSIGKILL": "yes",
                "SubState": "running",
            },
            cgroup_raw={
                "cgroup.events": "populated 1\nfrozen 0\n",
                "cgroup.procs": f"{self.keeper_pid}\n",
                "memory.current": "100",
                "memory.events": "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n",
                "memory.high": str(self.resource_contract["memory_high_bytes"]),
                "memory.max": str(self.resource_contract["memory_max_bytes"]),
                "memory.peak": "200",
                "memory.swap.current": "0",
                "memory.swap.max": str(self.resource_contract["memory_swap_max_bytes"]),
            },
            payload_current_starttime=None,
            keeper_current_starttime=77,
        )

    def release_keeper(self, *, unit_name: str, release_path: Path, launch: object) -> None:
        del unit_name, launch
        assert release_path.is_file()

    def capture_terminal(self, *, unit_name: str, invocation_id: str) -> object:
        del unit_name
        assert invocation_id == self.invocation
        self.clock = 1100
        return self.orchestrator.TerminalEvidence(
            captured_at_monotonic_ns=1100,
            systemd_raw={
                "ActiveState": "inactive",
                "ControlGroup": "",
                "ExecMainCode": "exited",
                "ExecMainStatus": "0",
                "InvocationID": self.invocation,
                "Result": "success",
                "SubState": "dead",
            },
        )

    def capture_cleanup(self, *, unit_name: str, launch: object, control_group: str) -> object:
        del launch
        self.clock = 1300
        return self.orchestrator.CleanupEvidence(
            captured_at_monotonic_ns=1300,
            payload_current_starttime=None,
            keeper_current_starttime=None,
            cgroup_path=control_group,
            cgroup_path_exists=False,
            unit_load_state="not-found",
            matching_unit_names=[],
        )

    def abort_and_capture_cleanup(
        self,
        *,
        unit_name: str,
        launch: object,
        control_group: str | None,
    ) -> object:
        del launch
        return self.orchestrator.CleanupEvidence(
            captured_at_monotonic_ns=self.monotonic_ns(),
            payload_current_starttime=None,
            keeper_current_starttime=None,
            cgroup_path=control_group or "/user.slice/ab16-r12-sentinel.scope",
            cgroup_path_exists=False,
            unit_load_state="not-found",
            matching_unit_names=[],
        )


def test_clean_checkout_and_preregistration_drive_real_bytes_through_first_arm_close(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    checkout = _clean_checkout(tmp_path)
    with _load_checkout_modules(checkout, tmp_path) as modules:
        bootstrap = modules.bootstrap
        gate1 = modules.gate1
        authority = modules.authority
        admission = modules.admission
        rebuild = modules.rebuild
        fixed_replay = modules.fixed_replay
        system_tools = _system_tools()
        strict_inputs = bootstrap._production_strict_inputs(checkout)  # noqa: SLF001
        offline_dir = tmp_path / "offline"
        campaign_parent = tmp_path / "campaigns"
        offline_dir.mkdir()
        campaign_parent.mkdir()
        campaign = campaign_parent / "run-ab16-r12-sentinel"
        candidate_path = offline_dir / "candidate.json"

        candidate = bootstrap.build_offline_candidate(
            output_path=candidate_path,
            repository_root=checkout,
            target_campaign_dir=campaign,
            strict_input_paths=strict_inputs,
            system_tool_paths=system_tools,
            created_at_utc=T0,
        )
        assert candidate["formal_campaign_created"] is False
        assert not campaign.exists()
        attestor_path = checkout / GATE1_RELATIVE / "manager_attestor_v4.py"
        capture = _manager_capture(
            gate1,
            attestor_path=attestor_path,
            system_tools=system_tools,
            clock_base_ns=0,
        )
        boot = bootstrap.bootstrap_campaign(
            campaign_dir=campaign,
            repository_root=checkout,
            offline_candidate=candidate_path,
            strict_input_paths=strict_inputs,
            system_tool_paths=system_tools,
            created_at_utc=T1,
            manager_capture=capture,
        )
        preregistration_path = Path(boot["path_preregistration_identity"]["path"])
        assert preregistration_path.is_relative_to(campaign / "campaign-authority/package/payload")
        _install_retained_gate1_precondition(
            gate1,
            campaign=campaign,
            root_identity=boot["campaign_root_identity"],
            selection_identity=boot["gate1_selection_identity"],
            capture=capture,
            attestor_path=attestor_path,
            system_tools=system_tools,
        )

        provenance = authority.prepare_baseline_provenance(
            preregistration_path,
            repository_root=checkout,
        )
        provenance_path = Path(provenance["campaign_provenance_identity"]["path"])
        preregistration, _ = authority._load_preregistration(preregistration_path)  # noqa: SLF001
        model, incumbent, expectation, solution_values = _tiny_baseline(admission)
        computation = rebuild.BaselineComputation(
            model=model,
            incumbent=incumbent,
            solution_values=solution_values,
            runner_status="OPTIMAL",
            proof_summary={"solver_status": "OPTIMAL", "test_scope": "tiny deterministic solver only"},
            wall_seconds=0.0,
        )
        monkeypatch.chdir(checkout)
        rebuild._rebuild_paths(  # noqa: SLF001 - real writer seam with injected tiny computation
            output_dir=Path(preregistration["baseline_rebuilt_model_path"]).parent,
            campaign_provenance_path=provenance_path,
            candidate_placements=checkout / "data/preprocessed/candidate_placements.json",
            canonical_rules=checkout / "rules/canonical_rules.json",
            mandatory_instances=checkout / "data/preprocessed/mandatory_exact_instances.json",
            computation=computation,
            expectation=expectation,
            run_nonce=campaign.name,
            parameters={"solver_substitution": "single constrained ghost boolean"},
            created_at_utc=T2,
        )
        fixed_receipt, fixed_identity = fixed_replay._replay_paths(  # noqa: SLF001 - real replay writer
            campaign_provenance_path=provenance_path,
            model_path=preregistration["baseline_rebuilt_model_path"],
            metadata_path=preregistration["baseline_rebuilt_metadata_path"],
            incumbent_path=preregistration["baseline_incumbent_path"],
            output_path=preregistration["baseline_fixed_replay_path"],
            expectation=expectation,
            created_at_utc=T2,
            max_time_seconds=5.0,
        )
        assert fixed_receipt["status"] == "PASS"
        assert fixed_identity["path"] == preregistration["baseline_fixed_replay_path"]
        root, _ = gate1.load_campaign_root(
            campaign / "campaign-root.json",
            boot["campaign_root_identity"],
        )
        archive_locator = root["strict_inputs"]["legacy_control_a002"]["path"]
        admission_record = admission._admit_paths(  # noqa: SLF001 - tiny immutable expectation
            campaign_provenance_path=provenance_path,
            archive_locators=archive_locator,
            rebuilt_model=preregistration["baseline_rebuilt_model_path"],
            rebuilt_metadata=preregistration["baseline_rebuilt_metadata_path"],
            fixed_assignment_replay=preregistration["baseline_fixed_replay_path"],
            created_at_utc=T2,
            expectation=expectation,
        )
        admission_identity = admission.write_exclusive(
            preregistration["baseline_admission_path"],
            admission_record,
        )
        assert admission_record["status"] == "PASS"

        materialized = authority.materialize_pre_manifest_inputs(preregistration_path)
        assert materialized["status"] == "PRE_MANIFEST_INPUTS_READY"
        assert len(materialized["arm_binding_identities"]) == 16
        manifest = authority.build_manifest(preregistration_path)
        suite = authority.create_suite_selection(preregistration_path)
        assert manifest["status"] == suite["status"] == "PASS"
        prepared = authority.prepare_attempt(
            preregistration_path,
            repository_root=checkout,
        )
        slot = prepared["slot"]
        assert slot == "region-capacity-ab-control"
        produced = authority.produce_selection(
            preregistration_path,
            slot=slot,
            attempt_ordinal=1,
            selection_nonce="r12-self-contained-sentinel-a001",
            manager_capture=copy.deepcopy(capture),
            launch_environment={
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                "HOME": str(tmp_path / "sentinel-home"),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": "/usr/bin",
                "PYTHONHASHSEED": "0",
                "TZ": "UTC",
                "XDG_RUNTIME_DIR": "/run/user/1000",
            },
        )
        bound = authority.bind_selection(
            preregistration_path,
            slot=slot,
            attempt_ordinal=1,
            selection_path=produced["selection_identity"]["path"],
        )
        assert bound["status"] == "SELECTION_BOUND"

        attempt_dir = Path(prepared["attempt_dir"])
        execution, _ = authority._load_record(  # noqa: SLF001 - read the producer's exact bytes
            attempt_dir / "attempt-execution.json",
            "R12 sentinel attempt execution",
        )
        runner = _load_pinned_module(execution["tool_identities"]["organic_arm_runner"], "runner")
        lifecycle = _load_pinned_module(
            execution["tool_identities"]["organic_resource_lifecycle"],
            "lifecycle",
        )
        orchestrator = _load_pinned_module(
            execution["tool_identities"]["organic_unit_orchestrator"],
            "orchestrator",
        )
        arithmetic = _load_pinned_module(
            execution["tool_identities"]["organic_arm_replay"],
            "arithmetic",
        )
        run_dir = Path(execution["run_dir"])
        adapter = _RunnerBackedResourceAdapter(
            orchestrator=orchestrator,
            lifecycle=lifecycle,
            runner=runner,
            attempt_dir=run_dir,
            selection_path=Path(produced["selection_identity"]["path"]),
            hooks=_MicroArmHooks(runner, model, incumbent),
        )
        resource_result = orchestrator.orchestrate_with_adapter(
            pre_run_path=produced["pre_run_authority_identity"]["path"],
            selection_path=produced["selection_identity"]["path"],
            adapter=adapter,
        )
        assert resource_result["status"] == "PASS"
        arm_result_path = run_dir / "result.json"
        arithmetic_record = arithmetic.replay_arm(
            arm_result=arm_result_path,
            cut_free_replay=preregistration["baseline_fixed_replay_path"],
            replay_tool_identity=_detached(execution["tool_identities"]["organic_arm_replay"]),
        )
        arithmetic_path = run_dir / "arithmetic-replay.json"
        arithmetic.write_exclusive(arithmetic_path, arithmetic_record)
        closed = authority.close_attempt(
            preregistration_path,
            slot=slot,
            attempt_ordinal=1,
            outcome=authority.CREDIBLE_TERMINAL,
            evidence_paths={
                "arm_result": arm_result_path,
                "arithmetic_receipt": arithmetic_path,
                "resource_preterminal": run_dir / "resource-verification.json",
                "resource_receipt": run_dir / "detached-replay.json",
            },
        )
        assert closed["outcome"] == authority.CREDIBLE_TERMINAL
        replayed_campaign = authority.replay_campaign(preregistration_path)
        assert replayed_campaign["consumption_state"]["next_index"] == 1
        assert replayed_campaign["consumption_state"]["slots"][0]["state"] == "COMPLETE"

        candidate_sources = candidate["candidate"]["planned_source_identities"]
        assert all(
            Path(identity["path"]).is_relative_to(checkout)
            for role, identity in candidate_sources.items()
            if not role.startswith("system.")
        )
        input_set, _ = authority._load_record(  # noqa: SLF001 - location assertions only
            attempt_dir / "attempt-input-set.json",
            "R12 sentinel input set",
        )
        assert all(
            Path(identity["path"]).is_relative_to(attempt_dir / "input-snapshots")
            for identity in input_set["strict_input_identities"].values()
        )
        assert all(
            Path(identity["path"]).is_relative_to(attempt_dir / "tool-snapshots")
            for identity in input_set["tool_identities"].values()
        )
        producer_identities = [
            candidate["candidate_identity"],
            candidate["path_preregistration_identity"],
            boot["campaign_root_identity"],
            boot["path_preregistration_identity"],
            provenance["campaign_provenance_identity"],
            fixed_identity,
            admission_identity,
            manifest["manifest_identity"],
            suite["selection_identity"],
            prepared["attempt_execution_identity"],
            produced["selection_identity"],
            bound["selection_binding_identity"],
            closed["attempt_result_identity"],
        ]
        assert all(Path(identity["path"]).is_relative_to(tmp_path) for identity in producer_identities)
        forbidden_artifacts = ROOT / ".artifacts"
        assert all(not Path(identity["path"]).is_relative_to(forbidden_artifacts) for identity in producer_identities)
        assert _command(("git", "status", "--porcelain=v1"), cwd=checkout) == b""
