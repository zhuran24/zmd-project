from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
RUNNER_PATH = RESEARCH / "ab16_resource_calibration_runner_v1.py"
PROTOCOL_PATH = RESEARCH / "ab16_resource_calibration_v1.py"
PACKAGE_PATH = RESEARCH / "ab16_resource_calibration_package_v1.py"
OBSERVER_PATH = RESEARCH / "ab16_resource_calibration_harness_v1.py"
ADMISSION_PATH = RESEARCH / "ab16_resource_admission_v1.py"
AGGREGATOR_PATH = RESEARCH / "ab16_resource_calibration_aggregator_v1.py"
REPLAY_A = RESEARCH / "replay_ab16_resource_calibration_v1.py"
REPLAY_B = RESEARCH / "replay_ab16_resource_calibration_alt_v1.py"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load(RUNNER_PATH, "_test_ab16_calibration_controller")
PROTOCOL = _load(PROTOCOL_PATH, "_test_ab16_calibration_controller_protocol")
PACKAGE = _load(PACKAGE_PATH, "_test_ab16_calibration_controller_package")
ADMISSION = _load(ADMISSION_PATH, "_test_ab16_calibration_controller_admission")
VALIDATOR = _load(REPLAY_A, "_test_ab16_calibration_controller_validator")
AGGREGATOR = _load(
    AGGREGATOR_PATH,
    "_test_ab16_calibration_controller_aggregator",
)


def test_closed_stage_terminal_follows_waitpid_echild_closure() -> None:
    tree = ast.parse(
        textwrap.dedent(inspect.getsource(RUNNER.run_declared_calibration_sample))
    )
    closure_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_require_waitpid_echild"
    ]
    closed_terminal_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_publish_stage_terminal"
        and any(
            keyword.arg == "status"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "CLOSED_NO_AUTHORITY"
            for keyword in node.keywords
        )
    ]
    assert len(closure_lines) == len(closed_terminal_lines) == 1
    assert closure_lines[0] < closed_terminal_lines[0]


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _identity(path: Path, value: object) -> dict[str, object]:
    raw = _canonical(value)
    return {
        "path": str(path.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _file_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _content_identity(path: Path) -> dict[str, object]:
    result = _file_identity(path)
    result.pop("path")
    return result


def _tool_identities() -> dict[str, dict[str, object]]:
    return {
        "aggregator": _file_identity(AGGREGATOR_PATH),
        "alternate_replayer": _file_identity(REPLAY_B),
        "fd_loader": _file_identity(
            RESEARCH / "ab16_resource_calibration_fd_loader_v1.py"
        ),
        "observer_harness": _file_identity(OBSERVER_PATH),
        "package_verifier": _file_identity(PACKAGE_PATH),
        "primary_replayer": _file_identity(REPLAY_A),
        "protocol": _file_identity(PROTOCOL_PATH),
        "resource_admission": _file_identity(ADMISSION_PATH),
        "runner": _file_identity(RUNNER_PATH),
        "workload": _file_identity(
            RESEARCH / "ab16_resource_calibration_workloads_v1.py"
        ),
    }


def _portable_closure(
    package_receipt_identity: dict[str, object],
    *,
    package_receipt: dict[str, object],
) -> dict[str, object]:
    host_content = {
        label: {
            "sha256": identity["sha256"],
            "size_bytes": identity["size_bytes"],
        }
        for label, identity in sorted(
            cast(
                dict[str, dict[str, object]],
                package_receipt["host_runtime_identities"],
            ).items()
        )
    }
    return {
        "host_runtime_content_sha256": hashlib.sha256(
            _canonical(host_content)
        ).hexdigest(),
        "layout": package_receipt["layout"],
        "package_receipt_identity": package_receipt_identity,
        "package_schema_version": package_receipt["schema_version"],
        "source_sets_sha256": hashlib.sha256(
            _canonical(package_receipt["source_sets"])
        ).hexdigest(),
    }


def _fake_package_receipt(
    *,
    layout: str = "PORTABLE_CANDIDATE_V1",
) -> dict[str, object]:
    return {
        "authorizations": {"all-package-authority": False},
        "host_runtime_identities": {},
        "layout": layout,
        "schema_version": (
            "noncert-cuts-ab16-resource-calibration-package-v2"
        ),
        "source_sets": {"test-source-set": {"kind": "TEST_ONLY"}},
    }


def _build_focused_package(
    tmp_path: Path,
) -> tuple[
    Path,
    dict[str, object],
    dict[str, dict[str, object]],
]:
    fixture_root = tmp_path / "fixture-sources"
    fixture_root.mkdir()
    fixtures: dict[str, Path] = {}
    for stage, name in (
        ("FORMAL_ORGANIC_ARM", "formal.json"),
        ("FULL_PREFLIGHT", "full.json"),
        ("GATE_B_QUALIFICATION", "gate-b.json"),
    ):
        path = fixture_root / name
        path.write_bytes(_canonical({"stage": stage}))
        fixtures[stage] = path
    member_sources = {
        "devtools/research_run_contract.py": (
            ROOT / "devtools/research_run_contract.py"
        ),
        "fixtures/formal.json": fixtures["FORMAL_ORGANIC_ARM"],
        "fixtures/full.json": fixtures["FULL_PREFLIGHT"],
        "fixtures/gate-b.json": fixtures["GATE_B_QUALIFICATION"],
        "roles/calibration-aggregator.py": AGGREGATOR_PATH,
        "roles/calibration-loader.py": (
            RESEARCH / "ab16_resource_calibration_fd_loader_v1.py"
        ),
        "roles/calibration-observer.py": OBSERVER_PATH,
        "roles/calibration-package.py": PACKAGE_PATH,
        "roles/calibration-protocol.py": PROTOCOL_PATH,
        "roles/calibration-replay-alt.py": REPLAY_B,
        "roles/calibration-replay.py": REPLAY_A,
        "roles/calibration-runner.py": RUNNER_PATH,
        "roles/calibration-workload.py": (
            RESEARCH / "ab16_resource_calibration_workloads_v1.py"
        ),
    }
    roles = {
        "calibration-aggregator": "roles/calibration-aggregator.py",
        "calibration-alternate-replay": "roles/calibration-replay-alt.py",
        "calibration-fd-loader": "roles/calibration-loader.py",
        "calibration-observer": "roles/calibration-observer.py",
        "calibration-package-verifier": "roles/calibration-package.py",
        "calibration-primary-replay": "roles/calibration-replay.py",
        "calibration-protocol": "roles/calibration-protocol.py",
        "calibration-runner": "roles/calibration-runner.py",
        "calibration-workload": "roles/calibration-workload.py",
    }
    package_root = (tmp_path / "focused-package").absolute()
    receipt = PACKAGE.build_calibration_package(
        package_root,
        members=member_sources,
        roles=roles,
        stage_fixtures={
            "FORMAL_ORGANIC_ARM": "fixtures/formal.json",
            "FULL_PREFLIGHT": "fixtures/full.json",
            "GATE_B_QUALIFICATION": "fixtures/gate-b.json",
        },
    )
    identities = cast(
        dict[str, dict[str, object]],
        receipt["member_identities"],
    )
    tool_roles = {
        "aggregator": "calibration-aggregator",
        "alternate_replayer": "calibration-alternate-replay",
        "fd_loader": "calibration-fd-loader",
        "observer_harness": "calibration-observer",
        "package_verifier": "calibration-package-verifier",
        "primary_replayer": "calibration-primary-replay",
        "protocol": "calibration-protocol",
        "runner": "calibration-runner",
        "workload": "calibration-workload",
    }
    absolute_tools: dict[str, dict[str, object]] = {}
    for label, role in tool_roles.items():
        relative = roles[role]
        identity = identities[relative]
        absolute_tools[label] = {
            "path": str(package_root / relative),
            "sha256": identity["sha256"],
            "size_bytes": identity["size_bytes"],
        }
    absolute_tools["resource_admission"] = _file_identity(ADMISSION_PATH)
    return package_root, receipt, absolute_tools


def _plan(
    tmp_path: Path,
    *,
    action: str = "RUN_THREE_SAMPLE_COHORT",
    package_receipt_identity: dict[str, object] | None = None,
    package_layout: str = "PORTABLE_CANDIDATE_V1",
    package_receipt: dict[str, object] | None = None,
    tools: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    controller_root = (tmp_path / "controller").absolute()
    cohort_root = (tmp_path / "cohort").absolute()
    tools = _tool_identities() if tools is None else tools
    package_receipt_identity = (
        {
            "path": str((tmp_path / "package/receipt.json").absolute()),
            "sha256": "a" * 64,
            "size_bytes": 123,
        }
        if package_receipt_identity is None
        else package_receipt_identity
    )
    package_receipt = (
        _fake_package_receipt(layout=package_layout)
        if package_receipt is None
        else package_receipt
    )
    profile = ADMISSION._validated_prospective_profile(  # noqa: SLF001
        "FULL_PREFLIGHT",
        enforced_budget_profile=None,
        enforced_budget_profile_identity=None,
    )
    profile_identity = _identity(cohort_root / "installed-profile.json", profile)
    members = {
        "calibration_aggregator": tools["aggregator"],
        "calibration_observer": tools["observer_harness"],
        "calibration_protocol": tools["protocol"],
        "calibration_runner": tools["runner"],
        "preflight_gate": _file_identity(ROOT / "scripts/preflight_gate.py"),
        "python_interpreter": _file_identity(Path(sys.executable).resolve()),
        "resource_admission": tools["resource_admission"],
    }
    surface = PROTOCOL.build_execution_surface(
        stage="FULL_PREFLIGHT",
        command=[
            str(Path(sys.executable).resolve()),
            "scripts/preflight_gate.py",
            "--full",
        ],
        working_directory=str(ROOT.absolute()),
        test_inventory_count=1,
        test_inventory_sha256=hashlib.sha256(b"one-test").hexdigest(),
        xdist_available=False,
        worker_mode="pytest-serial",
        worker_count=1,
        member_identities=members,
        control_plane_identities={
            "code_assets": _file_identity(
                ROOT / "data/repository_governance/code_assets.json"
            ),
            "profile": profile_identity,
            "project_lock": _file_identity(ROOT / "PROJECT_LOCK.md"),
        },
        portable_package=_portable_closure(
            package_receipt_identity,
            package_receipt=package_receipt,
        ),
        workload_fidelity_class="EXACT_FULL_PREFLIGHT",
        launch_admissible=action != "INSPECT_NO_AUTHORITY",
    )
    declaration = PROTOCOL.build_declaration(
        declaration_id="calibration-controller-declaration-0001",
        cohort_id="calibration-controller-cohort-0001",
        execution_surface=surface,
        harness_identity=tools["runner"],
        observer_identity=tools["observer_harness"],
        installed_profile_identity=profile_identity,
    )
    lock_identities = [
        {
            "device": index + 1,
            "inode": index + 100,
            "path": path,
            "uid": os.getuid(),
        }
        for index, path in enumerate(ADMISSION.LOCK_PATHS)
    ]
    return {
        "action": action,
        "authority_scope": RUNNER.AUTHORITY_SCOPE,
        "authorizations": dict(RUNNER.FALSE_AUTHORIZATIONS),
        "cohort_root": str(cohort_root),
        "controller_root": str(controller_root),
        "declaration": declaration,
        "delegated_cgroup_parent": str((tmp_path / "cgroups").absolute()),
        "installed_profile": profile,
        "outside_replay_outputs": {
            "alternate": str((tmp_path / "outside-replay-b.json").absolute()),
            "primary": str((tmp_path / "outside-replay-a.json").absolute()),
        },
        "package_receipt_identity": package_receipt_identity,
        "resource_admission": (
            {
                "allowed_same_uid_processes": [],
                "cgroup_parent_contract": {
                    "delegation": "CGROUP_V2_USER_DELEGATED_PARENT",
                    "parent_path": str((tmp_path / "cgroups").absolute()),
                    "required_controllers": ["io", "memory"],
                    "requires_owned_writable_parent": True,
                    "transient_child_per_sample": True,
                },
                "enforced_budget_profile": None,
                "enforced_budget_profile_identity": None,
                "lock_acquisition": "RETAINED_LOCK_FD_TRANSFER",
                "lock_identities": lock_identities,
                "lock_identity_format": ADMISSION.FORMAL_LOCK_IDENTITY_FORMAT,
                "observation_context": {
                    "disk_path": str(tmp_path.absolute()),
                    "kind": "GATE_A_FULL_PREFLIGHT",
                    "label": "calibration-controller-test",
                    "sequence": 1,
                },
            }
            if action != "INSPECT_NO_AUTHORITY"
            else None
        ),
        "sample_runs": [
            {
                "cgroup_name": f"ab16-calibration-{index}",
                "sample_id": f"ab16-calibration-sample-{index:04d}",
                "stage_root": str((tmp_path / f"stage-{index}").absolute()),
            }
            for index in range(
                1,
                2 if action == "RUN_ONE_ACCEPTANCE" else 4,
            )
        ],
        "schema_version": RUNNER.CONTROLLER_PLAN_SCHEMA,
        "status": "PLANNED_NO_AUTHORITY",
        "timeout_seconds": 60,
    }


class _FakeLocks:
    def __init__(self, identities: list[dict[str, object]]) -> None:
        self._identities = identities

    def identities(self) -> list[dict[str, object]]:
        return [dict(item) for item in self._identities]


def _observer(
    *,
    stage_root: Path,
    cgroup_name: str,
    index: int,
) -> dict[str, object]:
    return {
        "authority_scope": PROTOCOL.AUTHORITY_SCOPE,
        "authorizations": dict(PROTOCOL.FALSE_AUTHORIZATIONS),
        "cgroup": {
            "disappeared_after_peak_read": True,
            "identity": {
                "device": 100,
                "inode": 1000 + index,
                "mode": 0o40700,
                "path": f"/test-cgroup/{cgroup_name}",
                "uid": os.getuid(),
            },
            "peak_read_before_disappearance": True,
        },
        "cgroup_limits": dict(
            RUNNER.CALIBRATION_CGROUP_LIMITS["FULL_PREFLIGHT"]
        ),
        "disk": {
            "after_bytes": 4096,
            "before_bytes": 0,
            "cgroup_io": {
                "rows_after": [{"device": "8:0", "wbytes": 4096}],
                "wbytes_after": 4096,
                "wbytes_before": 0,
                "wbytes_delta": 4096,
            },
            "growth_peak_bytes": 4096,
            "measurement_rule": (
                "MAX_RETAINED_TREE_POLLING_AND_CGROUP_IO_WBYTES"
            ),
            "peak_bytes": 4096,
            "polling_growth_peak_bytes": 4096,
            "target_identity": {
                "device": 200,
                "inode": 2000 + index,
                "mode": 0o40700,
                "path": str(stage_root),
                "uid": os.getuid(),
            },
        },
        "memory_peak_bytes": 8192 + index,
        "observer_process_identity": {
            "pid": 3000 + index,
            "starttime": 4000 + index,
        },
        "sample_count": 2,
        "schema_version": PROTOCOL.OBSERVER_RESULT_SCHEMA,
        "status": "PEAKS_CAPTURED_BEFORE_CGROUP_DISAPPEARANCE",
        "swap_peak_bytes": index,
    }


def _fake_admission(
    _path: Path,
    *,
    stage: str,
    **_kwargs: object,
) -> dict[str, object]:
    return {
        "authorizations": dict(ADMISSION.PROSPECTIVE_FALSE_AUTHORIZATIONS),
        "schema_version": (
            "noncert-cuts-ab16-calibration-prelaunch-resource-admission-v1"
        ),
        "stage": stage,
        "status": "PASS_NO_LAUNCH_AUTHORITY",
    }


def test_controller_runs_three_fresh_samples_and_emits_replay_ready_root(
    tmp_path: Path,
) -> None:
    (tmp_path / "cgroups").mkdir()
    plan = _plan(tmp_path)
    hook_count = 0

    def sample_executor(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        nonlocal hook_count
        hook = cast(object, kwargs["_prelaunch_check"])
        assert callable(hook)
        hook()
        hook_count += 1
        stage_root = cast(Path, kwargs["stage_disk_root"])
        stage_root.mkdir()
        (stage_root / "receipt.json").write_bytes(b"stage-closed\n")
        index = hook_count
        observer = _observer(
            stage_root=stage_root,
            cgroup_name=cast(str, kwargs["cgroup_name"]),
            index=index,
        )
        sample = PROTOCOL.build_sample(
            declaration=cast(dict[str, object], kwargs["declaration"]),
            declaration_identity=cast(
                dict[str, object],
                kwargs["declaration_identity"],
            ),
            sample_id=cast(str, kwargs["sample_id"]),
            observer_result=observer,
            observer_result_identity=_identity(
                cast(Path, kwargs["observer_result_path"]),
                observer,
            ),
            workload_process_identity={
                "pid": 5000 + index,
                "starttime": 6000 + index,
            },
            workload_exit_code=0,
        )
        return observer, sample

    receipt = RUNNER.run_calibration_controller(
        plan,
        protocol=PROTOCOL,
        package_receipt=_fake_package_receipt(),
        package_receipt_identity=cast(
            dict[str, object],
            plan["package_receipt_identity"],
        ),
        expected_tool_identities={
            label: {
                "sha256": identity["sha256"],
                "size_bytes": identity["size_bytes"],
            }
            for label, identity in _tool_identities().items()
            if label != "resource_admission"
        },
        absolute_tool_identities=_tool_identities(),
        resource_admission_module=ADMISSION,
        validator_module=VALIDATOR,
        aggregator_module=AGGREGATOR,
        held_resource_locks=_FakeLocks(
            cast(
                list[dict[str, object]],
                cast(dict[str, object], plan["resource_admission"])[
                    "lock_identities"
                ],
            )
        ),
        _sample_executor=sample_executor,
        _admission_evaluator=_fake_admission,
    )
    assert hook_count == 3
    assert receipt["status"] == "CLOSED_NO_LAUNCH_AUTHORITY"
    assert all(value is False for value in receipt["authorizations"].values())
    controller = Path(cast(str, plan["controller_root"]))
    cohort = Path(cast(str, plan["cohort_root"]))
    assert sorted(
        path.name for path in (controller / "resource-admission").iterdir()
    ) == [
        "initial.json",
        "sample-01.json",
        "sample-02.json",
        "sample-03.json",
    ]
    for script, output, slot in (
        (REPLAY_A, tmp_path / "outside-replay-a.json", "replay-a"),
        (REPLAY_B, tmp_path / "outside-replay-b.json", "replay-b"),
    ):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(script),
                "--root",
                str(cohort),
                "--output",
                str(output),
                "--slot",
                slot,
                "--expected-source-sha256",
                hashlib.sha256(script.read_bytes()).hexdigest(),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert not any("a039" in str(path).lower() for path in tmp_path.rglob("*"))


def test_controller_run_one_acceptance_uses_same_internal_gate_and_closes(
    tmp_path: Path,
) -> None:
    (tmp_path / "cgroups").mkdir()
    plan = _plan(tmp_path, action="RUN_ONE_ACCEPTANCE")
    hook_count = 0

    def sample_executor(
        **kwargs: object,
    ) -> tuple[dict[str, object], dict[str, object]]:
        nonlocal hook_count
        hook = kwargs["_prelaunch_check"]
        assert callable(hook)
        hook()
        hook_count += 1
        stage_root = cast(Path, kwargs["stage_disk_root"])
        stage_root.mkdir()
        (stage_root / "receipt.json").write_bytes(b"stage-closed\n")
        observer = _observer(
            stage_root=stage_root,
            cgroup_name=cast(str, kwargs["cgroup_name"]),
            index=1,
        )
        sample = PROTOCOL.build_sample(
            declaration=cast(dict[str, object], kwargs["declaration"]),
            declaration_identity=cast(
                dict[str, object],
                kwargs["declaration_identity"],
            ),
            sample_id=cast(str, kwargs["sample_id"]),
            observer_result=observer,
            observer_result_identity=_identity(
                cast(Path, kwargs["observer_result_path"]),
                observer,
            ),
            workload_process_identity={"pid": 5001, "starttime": 6001},
            workload_exit_code=0,
        )
        return observer, sample

    receipt = RUNNER.run_calibration_controller(
        plan,
        protocol=PROTOCOL,
        package_receipt=_fake_package_receipt(
            layout="PORTABLE_CANDIDATE_V1",
        ),
        package_receipt_identity=cast(
            dict[str, object],
            plan["package_receipt_identity"],
        ),
        expected_tool_identities={
            label: {
                "sha256": identity["sha256"],
                "size_bytes": identity["size_bytes"],
            }
            for label, identity in _tool_identities().items()
            if label != "resource_admission"
        },
        absolute_tool_identities=_tool_identities(),
        resource_admission_module=ADMISSION,
        validator_module=VALIDATOR,
        aggregator_module=AGGREGATOR,
        held_resource_locks=_FakeLocks(
            cast(
                list[dict[str, object]],
                cast(dict[str, object], plan["resource_admission"])[
                    "lock_identities"
                ],
            )
        ),
        _sample_executor=sample_executor,
        _admission_evaluator=_fake_admission,
    )
    assert hook_count == 1
    assert receipt["status"] == "CLOSED_NO_LAUNCH_AUTHORITY"
    assert receipt["replay_contract"] is None
    acceptance = json.loads(
        (Path(cast(str, plan["cohort_root"])) / "receipt.json").read_bytes()
    )
    assert acceptance["schema_version"] == RUNNER.ACCEPTANCE_TERMINAL_SCHEMA
    assert acceptance["status"] == "CLOSED_NO_LAUNCH_AUTHORITY"
    assert all(value is False for value in acceptance["authorizations"].values())
    assert not (Path(cast(str, plan["cohort_root"])) / "validations").exists()


def test_retained_fd_inspection_executes_package_runner_without_authority_or_output(
    tmp_path: Path,
) -> None:
    package_root, package_receipt, package_tools = _build_focused_package(
        tmp_path
    )
    package_receipt_identity = _file_identity(package_root / "receipt.json")
    plan = _plan(
        tmp_path,
        action="INSPECT_NO_AUTHORITY",
        package_receipt_identity=package_receipt_identity,
        package_layout=PACKAGE.FOCUSED_FIXTURE_LAYOUT,
        package_receipt=package_receipt,
        tools=package_tools,
    )
    plan_path = tmp_path / "controller-plan.json"
    plan_raw = _canonical(plan)
    plan_path.write_bytes(plan_raw)
    roles = cast(dict[str, str], package_receipt["roles"])
    opened = [
        os.open(
            package_root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        ),
        os.open(
            package_root / roles["calibration-package-verifier"],
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        ),
        os.open(
            package_root / roles["calibration-runner"],
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        ),
        os.open(
            package_root / "devtools/research_run_contract.py",
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        ),
        os.open(plan_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW),
    ]
    root_fd, verifier_fd, runner_fd, contract_fd, plan_fd = opened
    bootstrap = (
        "import importlib.machinery,importlib.util,sys,types;"
        "pkg=types.ModuleType('devtools');pkg.__path__=[];"
        "sys.modules['devtools']=pkg;"
        f"p='/proc/self/fd/{contract_fd}';"
        "s=importlib.util.spec_from_file_location("
        "'devtools.research_run_contract',p,loader="
        "importlib.machinery.SourceFileLoader("
        "'devtools.research_run_contract',p));"
        "m=importlib.util.module_from_spec(s);"
        "sys.modules['devtools.research_run_contract']=m;"
        "s.loader.exec_module(m);"
        f"p='/proc/self/fd/{runner_fd}';"
        "s=importlib.util.spec_from_file_location("
        "'__main__',p,loader="
        "importlib.machinery.SourceFileLoader('__main__',p));"
        "m=importlib.util.module_from_spec(s);"
        "sys.modules['__main__']=m;s.loader.exec_module(m)"
    )
    verifier_identity = package_tools["package_verifier"]
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                bootstrap,
                "--package-root-fd",
                str(root_fd),
                "--package-root-path",
                str(package_root),
                "--package-receipt-sha256",
                cast(str, package_receipt_identity["sha256"]),
                "--package-receipt-size",
                str(package_receipt_identity["size_bytes"]),
                "--package-verifier-fd",
                str(verifier_fd),
                "--package-verifier-sha256",
                cast(str, verifier_identity["sha256"]),
                "--executing-runner-fd",
                str(runner_fd),
                "--plan-fd",
                str(plan_fd),
                "--plan-sha256",
                hashlib.sha256(plan_raw).hexdigest(),
                "--plan-size",
                str(len(plan_raw)),
            ],
            check=False,
            capture_output=True,
            text=True,
            pass_fds=tuple(opened),
            cwd=tmp_path,
        )
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)
    assert result.returncode == 0, result.stdout + result.stderr
    inspection = json.loads(result.stdout)
    assert inspection["status"] == "PASS_NO_OUTPUT"
    assert all(value is False for value in inspection["authorizations"].values())
    assert all(
        value is False for value in inspection["package_authorizations"].values()
    )
    for key in (
        "controller_root",
        "cohort_root",
    ):
        assert not Path(cast(str, plan[key])).exists()
    assert not any(
        path.exists()
        for path in map(
            Path,
            cast(
                dict[str, str],
                plan["outside_replay_outputs"],
            ).values(),
        )
    )
    assert not any(
        Path(cast(str, run["stage_root"])).exists()
        for run in cast(list[dict[str, object]], plan["sample_runs"])
    )
    assert not any("a039" in str(path).lower() for path in tmp_path.rglob("*"))


def test_retained_fd_module_loader_preserves_executing_source_identity() -> None:
    descriptor = os.open(
        AGGREGATOR_PATH,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    module_name = "_test_ab16_retained_aggregator_identity"
    try:
        module = RUNNER._load_module_from_fd(  # noqa: SLF001
            descriptor,
            module_name=module_name,
        )
        assert module.__file__ == f"/proc/self/fd/{descriptor}"
        assert os.stat(cast(str, module.__file__)).st_ino == os.fstat(
            descriptor
        ).st_ino
        assert hashlib.sha256(Path(cast(str, module.__file__)).read_bytes()).hexdigest() == (
            hashlib.sha256(AGGREGATOR_PATH.read_bytes()).hexdigest()
        )
    finally:
        sys.modules.pop(module_name, None)
        os.close(descriptor)


def test_package_controller_lock_owner_acquires_exact_three_locks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_paths = tuple(
        str((tmp_path / f"controller-{index}.lock").absolute())
        for index in range(3)
    )
    monkeypatch.setattr(ADMISSION, "LOCK_PATHS", lock_paths)
    held = ADMISSION.HeldResourceLocks.acquire(
        identity_format=ADMISSION.FORMAL_LOCK_IDENTITY_FORMAT,
    )
    try:
        identities = held.identities()
        assert [identity["path"] for identity in identities] == list(lock_paths)
        with pytest.raises(
            ADMISSION.ResourceAdmissionError,
            match="RESOURCE_LOCK_ACQUISITION_FAILED",
        ):
            ADMISSION.HeldResourceLocks.acquire(
                identity_format=ADMISSION.FORMAL_LOCK_IDENTITY_FORMAT,
            )
    finally:
        released = held.release_once()
    assert released == identities
    assert held.released is True
    reacquired = ADMISSION.HeldResourceLocks.acquire(
        identity_format=ADMISSION.FORMAL_LOCK_IDENTITY_FORMAT,
    )
    reacquired.release_once()


def test_controller_failure_closes_incomplete_without_fake_cohort(
    tmp_path: Path,
) -> None:
    (tmp_path / "cgroups").mkdir()
    plan = _plan(tmp_path)

    def failed_executor(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        hook = kwargs["_prelaunch_check"]
        assert callable(hook)
        hook()
        stage_root = cast(Path, kwargs["stage_disk_root"])
        stage_root.mkdir()
        raise RuntimeError("deterministic workload failure")

    with pytest.raises(RuntimeError, match="deterministic workload failure"):
        RUNNER.run_calibration_controller(
            plan,
            protocol=PROTOCOL,
            package_receipt=_fake_package_receipt(),
            package_receipt_identity=cast(
                dict[str, object],
                plan["package_receipt_identity"],
            ),
            expected_tool_identities={},
            absolute_tool_identities=_tool_identities(),
            resource_admission_module=ADMISSION,
            validator_module=VALIDATOR,
            aggregator_module=AGGREGATOR,
            held_resource_locks=_FakeLocks(
                cast(
                    list[dict[str, object]],
                    cast(dict[str, object], plan["resource_admission"])[
                        "lock_identities"
                    ],
                )
            ),
            _sample_executor=failed_executor,
            _admission_evaluator=_fake_admission,
        )
    controller_terminal = json.loads(
        (Path(cast(str, plan["controller_root"])) / "terminal-incomplete.json").read_bytes()
    )
    cohort_terminal = json.loads(
        (Path(cast(str, plan["cohort_root"])) / "receipt.json").read_bytes()
    )
    assert controller_terminal["status"] == "INCOMPLETE_NO_AUTHORITY"
    assert controller_terminal["failure"]["conclusion"] is None
    assert cohort_terminal["status"] == "INCOMPLETE_NO_AUTHORITY"
    assert cohort_terminal["conclusion"] is None


def test_controller_rejects_colliding_roots_and_cgroup_names(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    cast(list[dict[str, object]], plan["sample_runs"])[1]["cgroup_name"] = cast(
        list[dict[str, object]],
        plan["sample_runs"],
    )[0]["cgroup_name"]
    with pytest.raises(
        RUNNER.CalibrationPublicationError,
        match="CALIBRATION_CONTROLLER_PLAN_INVALID",
    ):
        RUNNER.validate_calibration_controller_plan(
            plan,
            protocol=PROTOCOL,
            package_receipt=_fake_package_receipt(),
            package_receipt_identity=cast(
                dict[str, object],
                plan["package_receipt_identity"],
            ),
            absolute_tool_identities=_tool_identities(),
        )
    plan = _plan(tmp_path)
    Path(cast(str, plan["cohort_root"])).mkdir()
    with pytest.raises(
        RUNNER.CalibrationPublicationError,
        match="CALIBRATION_CONTROLLER_NO_OVERWRITE",
    ):
        RUNNER.validate_calibration_controller_plan(
            plan,
            protocol=PROTOCOL,
            package_receipt=_fake_package_receipt(),
            package_receipt_identity=cast(
                dict[str, object],
                plan["package_receipt_identity"],
            ),
            absolute_tool_identities=_tool_identities(),
        )


def test_controller_rejects_plan_selected_same_uid_exemptions(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    admission = cast(dict[str, object], plan["resource_admission"])
    admission["allowed_same_uid_processes"] = [
        {
            "pid": os.getpid(),
            "starttime": 1,
            "uid": os.getuid(),
        }
    ]

    with pytest.raises(
        RUNNER.CalibrationPublicationError,
        match="CALIBRATION_CONTROLLER_PLAN_INVALID",
    ):
        RUNNER.validate_calibration_controller_plan(
            plan,
            protocol=PROTOCOL,
            package_receipt=_fake_package_receipt(),
            package_receipt_identity=cast(
                dict[str, object],
                plan["package_receipt_identity"],
            ),
            absolute_tool_identities=_tool_identities(),
        )


def test_controller_cleanup_failure_cannot_leave_a_preceding_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_raw = _canonical({"action": "INSPECT_NO_AUTHORITY"})
    paths = [tmp_path / f"controller-owned-{index}.bin" for index in range(4)]
    for index, path in enumerate(paths):
        path.write_bytes(plan_raw if index == 3 else f"owned-{index}\n".encode())
    descriptors = [
        os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        for path in paths
    ]
    package_root_fd, verifier_fd, runner_fd, plan_fd = descriptors
    arguments = SimpleNamespace(
        acquire_fixed_locks=False,
        executing_runner_fd=runner_fd,
        lock_fd=[],
        package_receipt_sha256="a" * 64,
        package_receipt_size=1,
        package_root_fd=package_root_fd,
        package_root_path=tmp_path,
        package_verifier_fd=verifier_fd,
        package_verifier_sha256="b" * 64,
        plan_fd=plan_fd,
        plan_sha256=hashlib.sha256(plan_raw).hexdigest(),
        plan_size=len(plan_raw),
    )
    output = bytearray()

    class _Output:
        def write(self, raw: bytes) -> int:
            output.extend(raw)
            return len(raw)

    real_close = os.close
    failed_descriptor = verifier_fd
    failed_once = False

    def close_with_failure(descriptor: int) -> None:
        nonlocal failed_once
        if descriptor == failed_descriptor and not failed_once:
            failed_once = True
            raise RuntimeError("deterministic owned-FD cleanup failure")
        real_close(descriptor)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(
                RUNNER,
                "_controller_parser",
                lambda: SimpleNamespace(parse_args=lambda _argv: arguments),
            )
            patch.setattr(
                RUNNER,
                "_verify_retained_controller_package",
                lambda **_kwargs: ({}, SimpleNamespace(), None, None, None, {}, {}),
            )
            patch.setattr(
                RUNNER,
                "run_calibration_controller",
                lambda *_args, **_kwargs: {"status": "PASS_NO_OUTPUT"},
            )
            patch.setattr(RUNNER.sys, "stdout", SimpleNamespace(buffer=_Output()))
            patch.setattr(RUNNER.os, "close", close_with_failure)
            return_code = RUNNER.calibration_controller_main([])
    finally:
        if failed_once:
            real_close(failed_descriptor)

    assert return_code == 2
    terminal = json.loads(bytes(output))
    assert terminal == {
        "authority_scope": RUNNER.AUTHORITY_SCOPE,
        "authorizations": dict(RUNNER.FALSE_AUTHORIZATIONS),
        "code": "RuntimeError",
        "conclusion": None,
        "status": "FAIL_CLOSED",
    }
