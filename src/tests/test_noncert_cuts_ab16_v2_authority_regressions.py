from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import ModuleType
from typing import Mapping
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"
NATIVE_HELPER = TOOLS / "ab16_native_budget_helper_x86_64_v1.so"
BLOCKED_BUDGET_PROFILE = (
    TOOLS / "ab16_resource_budget_profile_phase2_blocked_v1.json"
)
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = _load(
    "noncert_cuts_ab16_campaign_bootstrap_v2_regression",
    TOOLS / "ab16_campaign_bootstrap_v2.py",
)
V4_AUTHORITY = _load(
    "noncert_cuts_ab16_campaign_authority_v4_regression",
    (
        ROOT
        / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
        / "campaign_authority_v4.py"
    ),
)
AUTHORITY = _load(
    "noncert_cuts_ab16_authority_v2_regression",
    TOOLS / "ab16_authority_v2.py",
)
FORMAL_LAUNCH_VALIDATOR = _load(
    "noncert_cuts_ab16_formal_launch_validator_v1_epoch_regression",
    TOOLS / "ab16_formal_launch_validator_v1.py",
)
RESOURCE = _load(
    "noncert_cuts_ab16_resource_verifier_v2_regression",
    TOOLS / "organic_resource_verifier_v2.py",
)
RESOURCE_LIFECYCLE = _load(
    "noncert_cuts_ab16_resource_lifecycle_v2_regression",
    TOOLS / "organic_resource_lifecycle_v2.py",
)
RESOURCE_ADMISSION = _load(
    "noncert_cuts_ab16_resource_admission_v1_regression",
    TOOLS / "ab16_resource_admission_v1.py",
)
FORMAL_SUCCESS = _load(
    "noncert_cuts_ab16_formal_success_verifier_v1_regression",
    TOOLS / "ab16_formal_success_verifier_v1.py",
)
TERMINAL = _load(
    "noncert_cuts_ab16_terminal_gate_v2_regression",
    TOOLS / "ab16_terminal_gate_v2.py",
)
TERMINAL_V1_FIXTURE = _load(
    "noncert_cuts_ab16_terminal_gate_v1_fixture_regression",
    ROOT / "src/tests/test_noncert_cuts_ab16_terminal_gate_v1.py",
)


def _launch_ready_budget_profile(tmp_path: Path) -> Path:
    value = json.loads(BLOCKED_BUDGET_PROFILE.read_bytes())
    value["launch_ready"] = True
    value["profile_id"] = "synthetic-v2-authority-regression-profile-v1"
    value["bootstrap"]["failure_closeout_reserve"]["target_name"] = (
        "bootstrap-package-failure-closeout.json"
    )
    value["formal_root"]["fixed_purpose_reservations"] = [
        {
            "purpose": purpose,
            **dict(specification),
        }
        for purpose, specification in sorted(
            BOOTSTRAP._FORMAL_FIXED_RESERVATION_CONTRACT.items(),  # noqa: SLF001
            key=lambda item: item[0].encode("utf-8"),
        )
    ]
    added_outside_replay_reserve = 2 * 4 * 1024 * 1024
    value["formal_root"]["fixed_overhead_category_limits"][
        "closeout"
    ] += added_outside_replay_reserve
    value["formal_root"]["category_limits"][
        "closeout"
    ] += added_outside_replay_reserve
    value["profile_sha256"] = BOOTSTRAP._budget_digest_without(  # noqa: SLF001
        value,
        "profile_sha256",
    )
    path = tmp_path / "resource-budget-profile.json"
    path.write_bytes(BOOTSTRAP._budget_canonical_json(value))  # noqa: SLF001
    path.chmod(0o444)
    return path


def _resource_calibration_paths(tmp_path: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for index, stage in enumerate(
        BOOTSTRAP.RESOURCE_CALIBRATION_STAGES,
        start=1,
    ):
        path = tmp_path / f"resource-calibration-{index}.json"
        path.write_bytes(
            BOOTSTRAP._budget_canonical_json(  # noqa: SLF001
                {"fixture": stage, "stage": stage}
            )
        )
        path.chmod(0o444)
        result[stage] = path
    return result


def test_authority_unterminated_record_requires_exact_unterminated_canonical_json(
    tmp_path: Path,
) -> None:
    value = {"schema_version": "fixture-v1", "status": "PASS"}
    path = tmp_path / "receipt.json"
    path.write_bytes(AUTHORITY.canonical_json(value)[:-1])
    assert AUTHORITY._unterminated_record(  # noqa: SLF001
        AUTHORITY.snapshot_regular(path),
        "fixture receipt",
    ) == value

    for name, raw in (
        ("terminated.json", AUTHORITY.canonical_json(value)),
        ("spaced.json", json.dumps(value, sort_keys=True).encode("utf-8")),
    ):
        drifted = tmp_path / name
        drifted.write_bytes(raw)
        with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
            AUTHORITY._unterminated_record(  # noqa: SLF001
                AUTHORITY.snapshot_regular(drifted),
                "fixture receipt",
            )
        assert exc_info.value.code == "JSON_NOT_CANONICAL"


def test_gate_approval_replay_uses_unterminated_parser_for_both_full_preflights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ParserReached(RuntimeError):
        pass

    gate_a_keys = set(
        "approval_id arm_launch_authorized created_at_utc decision disposable_authority_ready_identity "
        "disposable_detached_replay_identity formal_campaign_creation_authorized full_preflight_receipt_identity "
        "gate history_freeze_replay_identity manager_epoch offline_candidate_only planned_source_set_digest "
        "purpose reference_capability_identity reference_capability_transcript_identity repository_head "
        "repository_root run_nonce schema_version target_campaign_dir".split()
    )
    gate_a = {key: None for key in gate_a_keys}
    planned = {
        role: {
            "mode": 0o555,
            "path": f"/fixture/{role}",
            "sha256": "a" * 64,
            "size_bytes": 1,
        }
        for role in (
            "input.preflight_gate",
            "script.ab16_campaign_bootstrap_v2",
            "script.ab16_gate_b_qualification_v1",
            "script.ab16_preflight_qualification_v1",
            "script.ab16_pytest_collection_plugin_v1",
            "script.ab16_pytest_collection_protocol_v1",
            "script.ab16_resource_admission_v1",
            "script.gate_a_validation_v2",
            "script.package_independent_verifier_v1",
            "system.python3_13",
        )
    }
    candidate = {"planned_source_identities": planned}
    gate_b: dict[str, object] = {"created_at_utc": "2026-07-31T00:00:00Z"}
    final = {
        field: {}
        for field in (
            "authority_ready_identity",
            "detached_replay_identity",
            "pre_run_authority_identity",
            "qualification_runner_identity",
            "preflight_script_identity",
            "pytest_collection_plugin_identity",
            "pytest_collection_protocol_identity",
            "python_identity",
            "runner_tool_identity",
            "stderr_identity",
            "stdout_identity",
        )
    }
    final["command"] = {"argv": [], "execution_strategy": "fixture", "loader_identity": {}}
    source_roles = (
        "input.ab16_gate_a_receipt.json",
        "input.ab16_offline_candidate.json",
        "input.ab16_gate_b_approval.json",
        "input.ab16_gate_b_final_full_preflight.json",
        "input.ab16_gate_b_epoch_observation.json",
        "input.ab16_gate_b_pre_full_resource_gate.json",
        "input.ab16_gate_b_pre_publication_resource_gate.json",
    )
    sources = {
        role: {
            "source_identity": {
                "mode": 0o444,
                "path": f"/fixture/{role}",
                "sha256": hashlib.sha256(role.encode()).hexdigest(),
                "size_bytes": 1,
            }
        }
        for role in source_roles
    }
    records = {
        "AB16 Gate-A": gate_a,
        "AB16 offline candidate": candidate,
        "AB16 Gate-B": gate_b,
        "AB16 Gate-B final full preflight": final,
        "AB16 Gate-A full preflight": final,
    }
    monkeypatch.setattr(
        AUTHORITY,
        "_source_snapshot",
        lambda _files, _sources, role: role,
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_record",
        lambda _snapshot, label, **_kwargs: records[label],
    )
    monkeypatch.setattr(AUTHORITY, "_exact_keys", lambda value, *_args: value)
    monkeypatch.setattr(
        AUTHORITY,
        "_detached_from_source",
        lambda identity: {
            key: identity[key]
            for key in ("path", "sha256", "size_bytes")
        },
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_replay_identity_with_optional_mode",
        lambda _value, label: (
            "gate-a-full-snapshot"
            if label == "AB16 Gate-A full preflight"
            else "fixture-snapshot"
        ),
    )
    seen: list[str] = []

    def parser(snapshot: object, label: str) -> object:
        seen.append(label)
        if label == "AB16 Gate-B final full preflight":
            return final
        assert snapshot == "gate-a-full-snapshot"
        assert label == "AB16 Gate-A full preflight"
        raise ParserReached

    monkeypatch.setattr(AUTHORITY, "_unterminated_record", parser, raising=False)

    class CampaignModule:
        @staticmethod
        def validate_manager_epoch(_epoch: object) -> None:
            return None

    with pytest.raises(ParserReached):
        AUTHORITY._validate_gate_approvals(  # noqa: SLF001
            {
                "campaign_module": CampaignModule,
                "files": {},
                "sources": sources,
            }
        )
    assert seen == [
        "AB16 Gate-B final full preflight",
        "AB16 Gate-A full preflight",
    ]


def _top_level_literal(path: Path, name: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path.name} does not define literal {name}")


def test_project_lock_registers_one_exact_ab16_formal_cohort() -> None:
    lock = (ROOT / "PROJECT_LOCK.md").read_text(encoding="utf-8")
    section = lock.split(
        "### 3C. AB16 Gate-B and formal-campaign research-only authority boundary",
        1,
    )[1].split("## 4. Forbidden Changes", 1)[0]
    qualification = TOOLS / "ab16_gate_b_qualification_v1.py"
    launch = TOOLS / "ab16_formal_launch_validator_v1.py"
    success = TOOLS / "ab16_formal_success_verifier_v1.py"
    closeout = TOOLS / "ab16_outer_closeout_state_v1.py"
    accepted = {
        BOOTSTRAP.GATE_A_SCHEMA,
        BOOTSTRAP.CANDIDATE_SCHEMA,
        BOOTSTRAP.FINAL_FULL_PREFLIGHT_SCHEMA,
        BOOTSTRAP.GATE_B_SCHEMA,
        BOOTSTRAP.GATE_B_EPOCH_SCHEMA,
        BOOTSTRAP.CAPTURE_SCHEMA,
        BOOTSTRAP.RESULT_SCHEMA,
        BOOTSTRAP.PATH_PREREGISTRATION_SCHEMA,
        BOOTSTRAP.REPOSITORY_SNAPSHOT_SCHEMA,
        BOOTSTRAP.SNAPSHOT_MATERIALIZATION_SCHEMA,
        BOOTSTRAP.EXTERNAL_PLATFORM_SCHEMA,
        RESOURCE.HISTORY_FREEZE_SCHEMA,
        RESOURCE.HISTORY_REPLAY_SCHEMA,
        RESOURCE_ADMISSION.RESOURCE_ADMISSION_SCHEMA,
        RESOURCE_ADMISSION.PROFILE_SET_ID,
        _top_level_literal(qualification, "QUALIFICATION_SCHEMA"),
        _top_level_literal(qualification, "RESOURCE_GATE_SCHEMA"),
        _top_level_literal(qualification, "OWNER_REQUEST_SCHEMA"),
        _top_level_literal(qualification, "OWNER_RESPONSE_SCHEMA"),
        _top_level_literal(qualification, "OWNER_RELEASE_SCHEMA"),
        _top_level_literal(qualification, "HANDOFF_REQUEST_SCHEMA"),
        _top_level_literal(qualification, "HANDOFF_RESPONSE_SCHEMA"),
        _top_level_literal(launch, "FORMAL_CONTEXT_SCHEMA"),
        _top_level_literal(launch, "FORMAL_ADMISSION_SCHEMA"),
        _top_level_literal(launch, "FORMAL_SELECTION_SCHEMA_V3"),
        _top_level_literal(launch, "GUARDIAN_READY_SCHEMA"),
        _top_level_literal(launch, "ATTEMPT_CONSUMPTION_SCHEMA"),
        AUTHORITY.CONTINUATION_SCHEMA,
        AUTHORITY.BASELINE_ADMISSION_SCHEMA,
        AUTHORITY.COMMON_PRESTATE_SCHEMA,
        AUTHORITY.MANIFEST_SCHEMA,
        AUTHORITY.SUITE_SELECTION_SCHEMA,
        AUTHORITY.ARM_BINDING_SCHEMA,
        AUTHORITY.PRE_RUN_AUTHORITY_SCHEMA,
        AUTHORITY.ARM_SELECTION_SCHEMA,
        AUTHORITY.ARM_CONSUMPTION_SCHEMA,
        AUTHORITY.CAMPAIGN_STOP_SCHEMA,
        FORMAL_SUCCESS.PHASE_SCHEMAS["outer_prelaunch"],
        FORMAL_SUCCESS.PHASE_SCHEMAS["outer_start"],
        FORMAL_SUCCESS.ARM_PRELAUNCH_SCHEMA,
        FORMAL_SUCCESS.CONTROLLER_RESULT_SCHEMA,
        _top_level_literal(success, "SUCCESS_RECEIPT_SCHEMA"),
        _top_level_literal(success, "INCOMPLETE_RECEIPT_SCHEMA"),
        _top_level_literal(success, "FAILURE_RELEASE_SCHEMA"),
        _top_level_literal(success, "FAILURE_TERMINAL_RELEASE_SCHEMA"),
        _top_level_literal(success, "GUARDIAN_LOCK_CLOSE_SCHEMA"),
        _top_level_literal(success, "CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA"),
        _top_level_literal(closeout, "MARKERLESS_SCHEMA"),
        _top_level_literal(closeout, "INCOMPLETE_SCHEMA"),
        _top_level_literal(closeout, "REFERENCE_SCHEMA"),
        _top_level_literal(closeout, "HOLD_SCHEMA"),
        _top_level_literal(closeout, "HOLD_CLEAR_SCHEMA"),
        _top_level_literal(closeout, "LOCK_RELEASE_SCHEMA"),
    }
    missing = sorted(schema for schema in accepted if f"`{schema}`" not in section)
    assert missing == []
    assert "Schema names cannot be independently selected, relabeled, or mixed" in section
    assert "cannot be coerced into this cohort" in section
    assert "`noncert-cuts-ab16-formal-outer-prelaunch-v2`" in section
    assert "`noncert-cuts-ab16-formal-outer-start-v2`" in section
    assert "`noncert-cuts-ab16-formal-arm-prelaunch-v2`" in section
    assert "`noncert-cuts-ab16-formal-controller-result-v2`" in section
    assert "The main checkout is a control plane" in section
    assert "Tracked state remains `U=(1188,18)` and" in section
    assert "`L=absent`" in section


def test_project_lock_pins_terminal_reference_history_archive_bridge() -> None:
    lock = (ROOT / "PROJECT_LOCK.md").read_text(encoding="utf-8")
    section = lock.split(
        "### 3C. AB16 Gate-B and formal-campaign research-only authority boundary",
        1,
    )[1].split("## 4. Forbidden Changes", 1)[0]
    history_row = next(
        line
        for line in section.splitlines()
        if line.startswith("  | Gate-A terminal-reference history |")
    )
    assert f"`{RESOURCE.HISTORY_FREEZE_SCHEMA}`" in history_row
    assert f"`{RESOURCE.HISTORY_REPLAY_SCHEMA}`" in history_row
    assert (
        "`noncert-cuts-ab16-terminal-reference-history-replay-v1`"
        not in history_row
    )
    for fixed_identity in (
        RESOURCE.HISTORY_FREEZE_MANIFEST_SHA256,
        RESOURCE.HISTORY_FREEZE_HEAD,
        RESOURCE.HISTORY_SOURCE_COMMIT,
        RESOURCE.HISTORY_SOURCE_TREE,
    ):
        assert f"`{fixed_identity}`" in section
    for fixed_count in (
        f"`{RESOURCE.HISTORY_ARTIFACT_COUNT + RESOURCE.HISTORY_SOURCE_COUNT}`",
        f"`{RESOURCE.HISTORY_ARTIFACT_COUNT}`",
        f"`{RESOURCE.HISTORY_SOURCE_COUNT}`",
    ):
        assert fixed_count in section
    assert "whose sole parent is the" in section
    assert "`v1_source_glob` is not re-expanded" in section
    assert "is not accepted by the fresh cohort" in section
    assert "grants no new experiment," in section


def test_formal_orchestrator_outer_module_entry_is_cache_free() -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    # This is the ordinary developer-facing ``python -m`` smoke test.  The
    # safe-path selected-loader authority route has separate exact E2E
    # coverage and must not be conflated with this entry point.
    environment.pop("PYTHONSAFEPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            (
                "docs.research.noncert_cuts_ab16_20260724."
                "ab16_formal_orchestrator_v1"
            ),
            "--help",
        ],
        check=False,
        cwd=ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert completed.returncode == 0
    assert b"--campaign-dir" in completed.stdout
    assert completed.stderr == b""


def test_formal_orchestrator_is_one_package_and_loader_authority_source() -> None:
    assert (
        BOOTSTRAP.AB16_SCRIPT_TOOL_FILES["ab16_formal_orchestrator_v1"]
        == "ab16_formal_orchestrator_v1.py"
    )
    assert "tool.ab16_formal_orchestrator_v1.py" in AUTHORITY.REQUIRED_PACKAGE_ROLES
    assert "tool.ab16_final_release_actor_v1.py" in AUTHORITY.REQUIRED_PACKAGE_ROLES
    assert {
        "input.resource_calibration_formal_organic_arm.json",
        "input.resource_calibration_full_preflight.json",
        "input.resource_calibration_gate_b_qualification.json",
    } <= AUTHORITY.REQUIRED_PACKAGE_ROLES
    assert AUTHORITY.FORMAL_ROLE_SOURCES["formal-orchestrator"] == (
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_orchestrator_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_orchestrator_v1.py",
    )


def test_formal_launch_context_projects_gate_b_epoch_to_detached_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    snapshot_root = tmp_path / "snapshot"
    snapshot_root.mkdir()
    gate1_identity = _regular(tmp_path / "gate1-selection.json", b"{}\n")
    tool_identity = _regular(tmp_path / "tool.py", b"pass\n")
    detached_tool = {
        field: tool_identity[field]
        for field in ("path", "sha256", "size_bytes")
    }
    epoch_with_mode = _regular(tmp_path / "gate-b-epoch.json", b"{}\n")
    expected_epoch = {
        field: epoch_with_mode[field]
        for field in ("path", "sha256", "size_bytes")
    }
    message_identity = {"sha256": "a" * 64, "size_bytes": 1}
    paths = {
        "arm_prelaunch_paths": {},
        "child_audit_path": str(campaign / "child-audit.json"),
        "formal_admission_path": str(campaign / "formal-admission.json"),
        "formal_artifact_root": str(campaign / "formal-ab16/artifacts"),
        "formal_attempt_dir": str(campaign / "formal-attempt-a001"),
        "formal_selection_path": str(campaign / "formal-selection.json"),
        "gate1_prelaunch_ownership_path": str(campaign / "gate1-prelaunch.json"),
        "guardian_control_socket_path": str(campaign / "guardian.sock"),
        "guardian_control_retired_socket_path": str(
            campaign / "guardian.sock.retired"
        ),
        "guardian_ready_path": str(campaign / "guardian-ready.json"),
        "outer_barrier_path": str(campaign / "outer-barrier"),
        "outer_receipt_paths": {},
    }

    class CampaignModule:
        @staticmethod
        def replay_gate1_selection(*_args: object, **_kwargs: object) -> None:
            return None

    context = {
        "campaign_module": CampaignModule,
        "directory": campaign,
        "files": {},
        "repository_snapshot": {
            "external_platform": {
                "formal_launch_owner_driver": message_identity,
                "mechanical_oexcl_publisher": message_identity,
            },
            "materialization_identity": detached_tool,
            "repository_root": str(snapshot_root),
        },
        "root_identity": detached_tool,
        "root": {
            "manager_epoch": {"schema": "fixture-manager-epoch"},
            "package": {
                "manifest_identity": detached_tool,
                "package_id": "b" * 64,
                "seal_identity": detached_tool,
            },
            "repository_head": HEAD,
            "stage_topology": {
                "gate1_v4": {
                    "selection_path": gate1_identity["path"],
                },
            },
            "unit_namespace": "ab16-fixture",
        },
        "sources": {},
    }
    monkeypatch.setattr(AUTHORITY, "_campaign_context", lambda _campaign: context)
    monkeypatch.setattr(
        AUTHORITY,
        "_validate_gate_approvals",
        lambda _context: {
            "gate_b_epoch_identity": epoch_with_mode,
            "gate_b_identity": detached_tool,
        },
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_path_preregistration",
        lambda _context: (paths, detached_tool),
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_root_tool_identity",
        lambda *_args: detached_tool,
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_root_tool_identity_with_mode",
        lambda *_args: tool_identity,
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_root_input_identity",
        lambda *_args: detached_tool,
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_bootstrap_literal_values",
        lambda *_args: {"SELECTED_BYTE_LAUNCH_V2": "pass"},
    )
    selected_roles = {
        role: {
            "descriptor": 20 + ordinal,
            "mode": tool_identity["mode"],
            "package_path": package_path,
            "proc_fd_path": f"/proc/101/fd/{20 + ordinal}",
            "sha256": tool_identity["sha256"],
            "size_bytes": tool_identity["size_bytes"],
        }
        for ordinal, (role, package_path) in enumerate(
            sorted(
                {
                    "authority": "payload/tool.ab16_authority_v2.py",
                    "loader": "payload/tool.ab16_formal_loader_v1.py",
                    "native_helper": "payload/system.native_budget_helper.bin",
                    "native_helper_wrapper": (
                        "payload/tool.ab16_native_budget_helper_v1.py"
                    ),
                    "python": "payload/system.python3_13.bin",
                }.items()
            )
        )
    }
    monkeypatch.setattr(
        AUTHORITY,
        "_bootstrap_selected_transport",
        lambda *_args, **_kwargs: {
            "bootstrap_budget_terminal_identity": detached_tool,
            "budget_broker_endpoint_identity": {
                "device": 1,
                "inode": 2,
                "mode": 0o600,
                "path": str(campaign / "formal-ab16/budget-broker.sock"),
                "uid": os.getuid(),
            },
            "formal_budget_runtime": {},
            "resource_budget_profile_identity": detached_tool,
            "resource_calibration_authorization_bundles": {},
            "calibration_tool_content_identities": {},
            "selected_fd_transport": {
                "owner": {
                    "pid": 101,
                    "pid_starttime": 202,
                    "uid": os.getuid(),
                },
                "roles": selected_roles,
                "schema_version": (
                    "noncert-cuts-ab16-package-selected-fd-transport-v1"
                ),
            },
        },
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_formal_receipt_budget_bindings",
        lambda **_kwargs: {},
    )

    replay = AUTHORITY.replay_formal_launch_context(campaign_dir=campaign)

    assert replay["gate_b_epoch_observation_identity"] == expected_epoch
    assert set(replay["gate_b_epoch_observation_identity"]) == {
        "path",
        "sha256",
        "size_bytes",
    }
    assert FORMAL_LAUNCH_VALIDATOR._identity(
        replay["gate_b_epoch_observation_identity"],
        "formal context gate_b_epoch_observation_identity",
    ) == expected_epoch
    assert replay["bootstrap_budget_terminal_identity"] == detached_tool
    assert replay["selected_fd_transport"]["owner"] == {
        "pid": 101,
        "pid_starttime": 202,
        "uid": os.getuid(),
    }
    for spec_name in ("outer_spec", "guardian_spec"):
        assert (
            replay[spec_name]["selected_fd_transport"]
            == replay["selected_fd_transport"]
        )
        assert (
            replay[spec_name]["budget_broker_endpoint_identity"]
            == replay["budget_broker_endpoint_identity"]
        )
        selected = json.loads(replay[spec_name]["selected_byte_argv"][6])
        assert set(selected) == {
            "authority",
            "loader",
            "native_helper",
            "native_helper_wrapper",
            "python",
        }
        assert selected["native_helper_wrapper"] == tool_identity
        assert selected["native_helper"] == tool_identity


def _regular(path: Path, raw: bytes, *, mode: int = 0o444) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(mode)
    snapshot = BOOTSTRAP.authority.snapshot_regular(path)
    return {
        "mode": stat.S_IMODE(snapshot.stat_result.st_mode),
        **BOOTSTRAP.authority.detached_identity(snapshot),
    }


def test_bootstrap_selected_transport_replays_terminal_and_package_bytes(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    package_id = "b" * 64
    actor = {
        "pid": 101,
        "pid_starttime": 202,
        "uid": os.getuid(),
    }
    endpoint = {
        "device": 1,
        "inode": 2,
        "mode": 0o600,
        "path": str(campaign / "formal-ab16/budget-broker.sock"),
        "uid": os.getuid(),
    }
    package_paths = {
        "authority": "payload/tool.ab16_authority_v2.py",
        "loader": "payload/tool.ab16_formal_loader_v1.py",
        "native_helper": "payload/system.native_budget_helper.bin",
        "native_helper_wrapper": "payload/tool.ab16_native_budget_helper_v1.py",
        "python": "payload/system.python3_13.bin",
    }
    selected_identities = {
        role: _regular(
            campaign / "package" / relative_path,
            f"{role}\n".encode(),
            mode=0o555 if role in {"native_helper", "python"} else 0o444,
        )
        for role, relative_path in package_paths.items()
    }
    owner_package_role = "payload/tool.ab16_formal_orchestrator_v1.py"
    owner_source = _regular(
        campaign / "package" / owner_package_role,
        b"formal launch owner fixture\n",
    )
    owner_content_identity = {
        field: owner_source[field]
        for field in ("sha256", "size_bytes")
    }
    profile_path = _launch_ready_budget_profile(campaign)
    profile_snapshot = AUTHORITY.snapshot_regular(profile_path)
    profile_identity = {
        "mode": profile_snapshot.mode,
        **AUTHORITY.detached_identity(profile_snapshot),
    }
    calibration_envelopes: dict[str, dict[str, object]] = {}
    for stage, path in _resource_calibration_paths(campaign).items():
        snapshot = AUTHORITY.snapshot_regular(path)
        calibration_envelopes[stage] = {
            "identity": AUTHORITY.detached_identity(snapshot),
            "record": json.loads(snapshot.data),
        }
    calibration_tool_identities = {
        role: {
            "sha256": hashlib.sha256(role.encode("utf-8")).hexdigest(),
            "size_bytes": len(role.encode("utf-8")),
        }
        for role in AUTHORITY.CALIBRATION_TOOL_ROLES
    }
    selected_transport = {
        "owner": actor,
        "roles": {
            role: {
                "descriptor": 20 + ordinal,
                "mode": selected_identities[role]["mode"],
                "package_path": relative_path,
                "proc_fd_path": f"/proc/{actor['pid']}/fd/{20 + ordinal}",
                "sha256": selected_identities[role]["sha256"],
                "size_bytes": selected_identities[role]["size_bytes"],
            }
            for ordinal, (role, relative_path) in enumerate(
                sorted(package_paths.items())
            )
        },
        "schema_version": BOOTSTRAP.PACKAGE_SELECTED_FD_TRANSPORT_SCHEMA,
    }
    formal_contract = _regular(
        campaign / "formal-root-budget-contract.json",
        b"formal contract\n",
    )
    package_replay = _regular(
        campaign / "package-independent-replay.json",
        b"package replay\n",
    )
    recovery_extent = {
        "sha256": hashlib.sha256(b"recovery extent\n").hexdigest(),
        "size_bytes": len(b"recovery extent\n"),
    }
    recovery_observation = {
        "actor": {
            **actor,
            "schema_version": "fixture-recovery-actor-v1",
        },
        "broker_actor": actor,
        "control_owner": "persistent-budget-broker",
        "pidfd_method": "fixture",
        "prepared_recovery_identity": recovery_extent,
        "role": "ab16-recovery-closeout-v1",
        "role_source_identity": {},
        "schema_version": "fixture-recovery-observation-v1",
        "state": "BROKER_RETAINED_CONTROL",
    }
    final_release_handoff = {
        "directory_handoff": {},
        "reservation_handoffs": {},
        "schema_version": "fixture-final-release-parent-handoff-v1",
        "to_owner_nonce": "fixture-owner",
    }
    owner_observation = {
        "context_state": "AWAITING_DELAYED_CONTEXT",
        "credential_sha256": "d" * 64,
        "grant": {},
        "owner_actor": {
            "pid": 303,
            "role": "AB16_OWNER_FORMAL_LAUNCH_PUBLISHER_V1",
            "session_id": "fixture-owner-session",
            "starttime": 404,
        },
        "owner_pidfd_method": "fixture",
        "owner_role_source_identity": owner_content_identity,
        "ready": {},
        "registration_confirmation": {},
        "schema_version": (
            "noncert-cuts-ab16-formal-launch-owner-broker-handoff-v1"
        ),
        "state": "BROKER_HOSTED_OWNER_RETAINED",
    }
    run_nonce = campaign.name
    formal_handoff_record = {
        "authority": dict(AUTHORITY.BUDGET_FALSE_AUTHORITY),
        "calibration_tool_content_identities": calibration_tool_identities,
        "formal_account_handoff": {},
        "formal_control_parent_handoff": {},
        "formal_final_release_parent_handoff": final_release_handoff,
        "formal_reservation_handoffs": {},
        "formal_resource_calibration_bundle_identity": (
            calibration_envelopes["FORMAL_ORGANIC_ARM"]["identity"]
        ),
        "formal_root_budget_contract_identity": {
            field: formal_contract[field]
            for field in ("path", "sha256", "size_bytes")
        },
        "package_id": package_id,
        "recovery_owner_observation": recovery_observation,
        "resource_budget_profile_identity": profile_identity,
        "resource_calibration_authorization_bundles": (
            calibration_envelopes
        ),
        "run_nonce": run_nonce,
        "schema_version": BOOTSTRAP.FORMAL_ROOT_BUDGET_HANDOFF_SCHEMA,
        "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
        "status": "PASS",
    }
    formal_handoff_path = campaign / "formal-root-budget-handoff.json"
    formal_handoff_path.write_bytes(
        AUTHORITY.canonical_json(formal_handoff_record)
    )
    formal_handoff_path.chmod(0o444)
    formal_handoff = _full(formal_handoff_path)
    terminal = {
        "authority": {},
        "bootstrap_writer_release_contract": {},
        "campaign_dir": str(campaign),
        "package_id": package_id,
        "persistent_budget_runtime": {
            "authority": {},
            "broker_actor": actor,
            "broker_endpoint_identity": endpoint,
            "broker_nonce": "c" * 64,
            "broker_pidfd_method": "fixture",
            "formal_account_handoff": {},
            "formal_control_parent_handoff": {},
            "formal_final_release_parent_handoff": final_release_handoff,
            "formal_launch_owner_observation": owner_observation,
            "formal_reservation_handoffs": {},
            "formal_root_budget_handoff_identity": {
                field: formal_handoff[field]
                for field in ("path", "sha256", "size_bytes")
            },
            "recovery_owner_observation": recovery_observation,
            "schema_version": BOOTSTRAP.BOOTSTRAP_BROKER_RUNTIME_SCHEMA,
            "selected_fd_transport": selected_transport,
            "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
        },
        "schema_version": BOOTSTRAP.BOOTSTRAP_BUDGET_TERMINAL_SCHEMA,
        "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
        "status": "PASS",
        "unused_failure_closeout_identity": {},
    }
    terminal_path = campaign / "bootstrap-budget-terminal.json"
    terminal_path.write_bytes(AUTHORITY.canonical_json(terminal))
    terminal_path.chmod(0o444)

    class CampaignModule:
        BOOTSTRAP_BROKER_RUNTIME_SCHEMA = (
            BOOTSTRAP.BOOTSTRAP_BROKER_RUNTIME_SCHEMA
        )
        BOOTSTRAP_BUDGET_TERMINAL_SCHEMA = (
            BOOTSTRAP.BOOTSTRAP_BUDGET_TERMINAL_SCHEMA
        )
        FORMAL_ROOT_BUDGET_HANDOFF_SCHEMA = (
            BOOTSTRAP.FORMAL_ROOT_BUDGET_HANDOFF_SCHEMA
        )
        PACKAGE_SELECTED_FD_TRANSPORT_SCHEMA = (
            BOOTSTRAP.PACKAGE_SELECTED_FD_TRANSPORT_SCHEMA
        )

    result = AUTHORITY._bootstrap_selected_transport(  # noqa: SLF001
        {
            "campaign_module": CampaignModule,
            "directory": campaign,
            "files": {
                owner_package_role: AUTHORITY.snapshot_regular(
                    owner_source["path"]
                ),
            },
            "root": {
                "authority_tools": {
                    "ab16_formal_orchestrator_v1": {
                        field: owner_source[field]
                        for field in ("path", "sha256", "size_bytes")
                    },
                },
                "package": {"package_id": package_id},
                "run_nonce": run_nonce,
                "strict_inputs": {
                    "ab16_package_independent_replay": {
                        field: package_replay[field]
                        for field in ("path", "sha256", "size_bytes")
                    },
                },
            },
            "sources": {
                "tool.ab16_formal_orchestrator_v1.py": {
                    "package_path": owner_package_role,
                    "source_identity": {
                        field: owner_source[field]
                        for field in ("path", "sha256", "size_bytes")
                    },
                },
            },
        },
        paths={
            "bootstrap_budget_terminal_path": str(terminal_path),
            "budget_broker_control_socket_path": endpoint["path"],
            "formal_root_budget_contract_identity": {
                field: formal_contract[field]
                for field in ("path", "sha256", "size_bytes")
            },
            "formal_root_budget_handoff_path": str(formal_handoff_path),
            "resource_budget_profile_identity": profile_identity,
        },
        selected_identities=selected_identities,
    )

    assert result["budget_broker_endpoint_identity"] == endpoint
    assert result["selected_fd_transport"] == selected_transport
    assert result["formal_budget_runtime"]["broker_actor_identity"] == actor


def _full(path: Path) -> dict[str, object]:
    return dict(BOOTSTRAP.authority.full_identity(BOOTSTRAP.authority.snapshot_regular(path)))


def _manager_epoch(tmp_path: Path) -> dict[str, object]:
    manager = Path(
        _regular(
            tmp_path / "tools/systemd",
            b"fixture systemd manager\n",
            mode=0o755,
        )["path"]
    )
    python = Path(
        _regular(
            tmp_path / "tools/python3.13",
            b"fixture Python\n",
            mode=0o755,
        )["path"]
    )
    sudo = Path(
        _regular(
            tmp_path / "tools/sudo",
            b"fixture sudo\n",
            mode=0o755,
        )["path"]
    )
    busctl = Path(
        _regular(
            tmp_path / "tools/busctl",
            b"fixture busctl\n",
            mode=0o755,
        )["path"]
    )
    attestor = BOOTSTRAP.V4_RESEARCH_DIR / "manager_attestor_v4.py"
    value = {
        "attestation_toolchain": {
            "attestor": _full(attestor),
            "python": _full(python),
            "sudo": _full(sudo),
        },
        "attestor_ast_audit": V4_AUTHORITY.audit_attestor_source(
            attestor.read_bytes()
        ),
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.77",
        "manager_executable": _full(manager),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": _full(busctl)},
        "schema": V4_AUTHORITY.MANAGER_EPOCH_SCHEMA,
    }
    V4_AUTHORITY.validate_manager_epoch(value)
    return value


def _gate_a_record(
    tmp_path: Path,
    *,
    campaign_dir: Path,
    planned_digest: str,
    manager_epoch: dict[str, object],
) -> tuple[dict[str, object], dict[str, Path]]:
    evidence_paths: dict[str, Path] = {}
    evidence: dict[str, dict[str, object]] = {}
    for field in (
        "disposable_authority_ready_identity",
        "disposable_detached_replay_identity",
        "full_preflight_receipt_identity",
        "history_freeze_replay_identity",
        "reference_capability_identity",
        "reference_capability_transcript_identity",
    ):
        path = tmp_path / "gate-a-evidence" / f"{field}.json"
        evidence_paths[field] = path
        evidence[field] = _regular(
            path,
            json.dumps({"field": field}, sort_keys=True).encode(),
        )
    record: dict[str, object] = {
        "approval_id": "gate-a-fixture-v2",
        "arm_launch_authorized": False,
        "created_at_utc": "2026-07-24T00:00:00Z",
        "decision": "PASS",
        **evidence,
        "formal_campaign_creation_authorized": False,
        "gate": "A",
        "manager_epoch": manager_epoch,
        "offline_candidate_only": True,
        "planned_source_set_digest": planned_digest,
        "purpose": BOOTSTRAP.GATE_A_PURPOSE,
        "repository_head": HEAD,
        "repository_root": str(tmp_path / "repository"),
        "run_nonce": campaign_dir.name,
        "schema_version": BOOTSTRAP.GATE_A_SCHEMA,
        "target_campaign_dir": str(campaign_dir),
    }
    BOOTSTRAP._validate_gate_a(record)  # noqa: SLF001
    return record, evidence_paths


def _planned_sources(
    tmp_path: Path,
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, Path],
    dict[str, Path],
    dict[str, Path],
]:
    planned: dict[str, dict[str, object]] = {}
    scripts: dict[str, Path] = {}
    systems: dict[str, Path] = {}
    strict: dict[str, Path] = {}
    for role in BOOTSTRAP.SCRIPT_TOOL_FILES:
        path = tmp_path / "planned/scripts" / f"{role}.py"
        _regular(path, f"# {role}\n".encode(), mode=0o444)
        scripts[role] = path
        planned[f"script.{role}"] = _full(path)
    for role in BOOTSTRAP.SYSTEM_TOOL_ROLES:
        path = (
            NATIVE_HELPER
            if role == "native_budget_helper"
            else tmp_path / "planned/system" / role
        )
        if role != "native_budget_helper":
            _regular(path, f"{role}\n".encode(), mode=0o755)
        systems[role] = path
        planned[f"system.{role}"] = {
            **_full(path),
            "requested_path": str(path),
        }
    for role in BOOTSTRAP.STRICT_INPUT_ROLES:
        path = tmp_path / "planned/inputs" / role
        _regular(path, f"{role}\n".encode(), mode=0o444)
        strict[role] = path
        planned[f"input.{role}"] = _full(path)
    return planned, scripts, systems, strict


def _write_authority_json(path: Path, value: object) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    return BOOTSTRAP.authority.write_exclusive(
        path,
        BOOTSTRAP.authority.canonical_json(value),
    )


def _gate_b_publisher(
    output_path: Path,
    *,
    sequence: int = 2,
    session_id: str = "a" * 64,
) -> dict[str, object]:
    return BOOTSTRAP._gate_b_publisher_for_parent(  # noqa: SLF001
        output_path,
        sequence=sequence,
        session_id=session_id,
    )


def _directory_identity(path: Path) -> dict[str, int]:
    metadata = path.stat(follow_symlinks=False)
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
    }


def _v6_full_preflight_publication(
    tmp_path: Path,
) -> tuple[
    Path,
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, dict[str, object]],
]:
    repository = tmp_path / "repository"
    repository.mkdir()
    output = repository / "full-preflight"
    output.mkdir(mode=0o700)
    output.chmod(0o700)
    scratch = output / BOOTSTRAP.FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME
    scratch.mkdir(mode=0o700)
    scratch.chmod(0o700)
    basetemp = scratch / BOOTSTRAP.FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME
    basetemp.mkdir(mode=0o700)
    basetemp.chmod(0o700)
    stdout_identity = _regular(output / "stdout.log", b"fixture stdout\n")
    stderr_identity = _regular(output / "stderr.log", b"")

    authority_ready = _regular(tmp_path / "authority-ready.json", b"authority ready\n")
    detached_replay = _regular(tmp_path / "detached-replay.json", b"detached replay\n")
    pre_run_authority = _regular(tmp_path / "pre-run-authority.json", b"pre-run authority\n")
    preflight = _regular(tmp_path / "tools/preflight_gate.py", b"# preflight fixture\n")
    qualification = _regular(
        tmp_path / "tools/ab16_preflight_qualification_v1.py",
        b"# qualification fixture\n",
    )
    protocol = _regular(
        tmp_path / "tools/ab16_pytest_collection_protocol_v1.py",
        b"# collection protocol fixture\n",
    )
    plugin = _regular(
        tmp_path / "tools/ab16_pytest_collection_plugin_v1.py",
        b"# collection plugin fixture\n",
    )
    runner = _regular(tmp_path / "tools/gate_a_validation_v2.py", b"# runner fixture\n")
    python = _regular(tmp_path / "tools/python3.13", b"fixture Python\n", mode=0o755)
    resource_admission_source = _full(TOOLS / "ab16_resource_admission_v1.py")
    resource_admission_source_projection = {
        field: resource_admission_source[field]
        for field in ("mode", "path", "sha256", "size_bytes")
    }
    planned = {
        "input.preflight_gate": dict(preflight),
        "script.ab16_preflight_qualification_v1": dict(qualification),
        "script.ab16_pytest_collection_protocol_v1": dict(protocol),
        "script.ab16_pytest_collection_plugin_v1": dict(plugin),
        "script.ab16_resource_admission_v1": resource_admission_source,
        "script.gate_a_validation_v2": dict(runner),
        "system.python3_13": dict(python),
    }
    repository_root = str(repository)
    planned_digest = "b" * 64
    output_root_identity = _directory_identity(output)
    collection = {
        "collection_count": 1,
        "collection_sha256": "d" * 64,
        "manifest_sha256": "e" * 64,
        "markexpr": "not slow",
        "schema_version": "noncert-cuts-ab16-pytest-collection-binding-v1",
        "stage_module_origin_count": 1,
        "stage_sha256": "f" * 64,
        "terminal_module_origin_count": 1,
        "terminal_sha256": "0" * 64,
        "workflow": "full",
    }
    lock_identities = [
        {
            "device": 100 + index,
            "inode": 200 + index,
            "mode": 0o600,
            "nlink": 1,
            "path": path,
            "uid": os.getuid(),
        }
        for index, path in enumerate(RESOURCE_ADMISSION.LOCK_PATHS)
    ]
    resource_receipt = RESOURCE_ADMISSION.evaluate_resource_admission(
        repository,
        stage=RESOURCE_ADMISSION.FULL_PREFLIGHT,
        lock_identities=lock_identities,
        lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        observation_context={
            "authority_id": pre_run_authority["sha256"],
            "disk_path": repository_root,
            "kind": "GATE_A_FULL_PREFLIGHT",
            "ordinal": 0,
            "scope_id": planned_digest,
            "sequence": 1,
            "slot": "",
            "target": str(output),
        },
        meminfo={
            "MemAvailable": 64 * RESOURCE_ADMISSION.GIB,
            "SwapFree": 64 * RESOURCE_ADMISSION.GIB,
        },
        disk_free=64 * RESOURCE_ADMISSION.GIB,
        conflicts=[],
        observed_at_utc="2026-07-24T00:00:00Z",
    )
    record: dict[str, object] = {
        "authority_ready_identity": authority_ready,
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        },
        "command": {
            "argv": [
                python["path"],
                "-I",
                "-B",
                qualification["path"],
                "--repository-root",
                repository_root,
                "--basetemp",
                str(basetemp),
                "--basetemp-relative",
                basetemp.relative_to(repository).as_posix(),
                "--expected-count",
                str(collection["collection_count"]),
                "--expected-sha256",
                collection["collection_sha256"],
                "--preflight-source",
                preflight["path"],
                "--collection-protocol-source",
                protocol["path"],
                "--collection-plugin-source",
                plugin["path"],
                "--full",
            ],
            "execution_strategy": BOOTSTRAP.FINAL_FULL_PREFLIGHT_EXECUTION_STRATEGY,
            "loader_identity": {
                "sha256": "c" * 64,
                "size_bytes": 1,
            },
        },
        "detached_replay_identity": detached_replay,
        "duration_monotonic_ns": 1,
        "exit_code": 0,
        "finished_at_utc": "2026-07-24T00:00:01Z",
        "output_root_identity": output_root_identity,
        "planned_source_set_digest": planned_digest,
        "pre_run_authority_identity": pre_run_authority,
        "qualification_runner_identity": qualification,
        "preflight_script_identity": preflight,
        "preflight_timeout_scale": BOOTSTRAP.FINAL_FULL_PREFLIGHT_TIMEOUT_SCALE,
        "purpose": BOOTSTRAP.FINAL_FULL_PREFLIGHT_PURPOSE,
        "pytest_collection": collection,
        "pytest_collection_plugin_identity": plugin,
        "pytest_collection_protocol_identity": protocol,
        "pytest_scratch": {
            "basetemp_identity": _directory_identity(basetemp),
            "basetemp_path": str(basetemp),
            "initial_identity": _directory_identity(scratch),
            "path": str(scratch),
            "policy": BOOTSTRAP.FINAL_FULL_PREFLIGHT_SCRATCH_POLICY,
            "retention_policy": "failed",
            "status": "CLOSED_EMPTY_BASETEMP_RETAINED_AFTER_PASS",
        },
        "python_identity": python,
        "resource_admission": resource_receipt,
        "resource_admission_source_identity": resource_admission_source_projection,
        "resource_lock_release_identities": lock_identities,
        "repository_head": HEAD,
        "repository_root": repository_root,
        "runner_tool_identity": runner,
        "schema_version": BOOTSTRAP.FINAL_FULL_PREFLIGHT_SCHEMA,
        "started_at_utc": "2026-07-24T00:00:00Z",
        "status": "PASS",
        "stderr_identity": stderr_identity,
        "stdout_identity": stdout_identity,
        "timed_out": False,
    }
    receipt_identity = _regular(
        output / "receipt.json",
        BOOTSTRAP.authority.canonical_json(record)[:-1],
    )
    _regular(
        output / "receipt.commit.json",
        BOOTSTRAP.authority.canonical_json(
            {
                "output_root_identity": output_root_identity,
                "receipt_identity": receipt_identity,
                "schema_version": BOOTSTRAP.FINAL_FULL_PREFLIGHT_PUBLICATION_COMMIT_SCHEMA,
                "status": "COMMITTED",
            }
        )[:-1],
    )
    gate_a = {
        "disposable_authority_ready_identity": authority_ready,
        "disposable_detached_replay_identity": detached_replay,
        "full_preflight_receipt_identity": receipt_identity,
        "planned_source_set_digest": planned_digest,
        "repository_head": HEAD,
        "repository_root": repository_root,
    }
    return output, record, receipt_identity, gate_a, planned


def _rewrite_unterminated_readonly(path: Path, value: object, *, mode: int = 0o444) -> None:
    path.chmod(0o600)
    path.write_bytes(BOOTSTRAP.authority.canonical_json(value)[:-1])
    path.chmod(mode)


def _validate_v6_publication_with_consumer(
    module: ModuleType,
    *,
    output: Path,
    record: dict[str, object],
    receipt_identity: dict[str, object],
) -> None:
    module._validate_preflight_publication_commit(  # noqa: SLF001
        receipt_identity=receipt_identity,
        output_root_identity=record["output_root_identity"],
        label="fixture full-preflight receipt",
    )
    module._validate_preflight_output_root(  # noqa: SLF001
        record["output_root_identity"],
        receipt_directory=output,
        label="fixture full-preflight receipt",
    )
    module._validate_closed_preflight_scratch(  # noqa: SLF001
        record["pytest_scratch"],
        receipt_directory=output,
        label="fixture full-preflight receipt",
    )


@pytest.mark.parametrize("module", [BOOTSTRAP, AUTHORITY], ids=["bootstrap", "authority"])
def test_v6_full_preflight_consumers_accept_exact_committed_tree(
    tmp_path: Path,
    module: ModuleType,
) -> None:
    output, record, receipt_identity, _gate_a, _planned = _v6_full_preflight_publication(tmp_path)
    _validate_v6_publication_with_consumer(
        module,
        output=output,
        record=record,
        receipt_identity=receipt_identity,
    )


@pytest.mark.parametrize("module", [BOOTSTRAP, AUTHORITY], ids=["bootstrap", "authority"])
@pytest.mark.parametrize(
    "mutation",
    [
        "extra-key",
        "schema-drift",
        "status-drift",
        "receipt-identity-drift",
        "output-root-identity-drift",
        "staged-mode",
    ],
)
def test_v6_full_preflight_consumers_reject_commit_marker_mutation(
    tmp_path: Path,
    module: ModuleType,
    mutation: str,
) -> None:
    output, record, receipt_identity, _gate_a, _planned = _v6_full_preflight_publication(tmp_path)
    marker_path = output / "receipt.commit.json"
    marker = json.loads(marker_path.read_bytes())
    marker_mode = 0o444
    if mutation == "extra-key":
        marker["extra"] = False
    elif mutation == "schema-drift":
        marker["schema_version"] = "stale-schema"
    elif mutation == "status-drift":
        marker["status"] = "STAGED"
    elif mutation == "receipt-identity-drift":
        marker["receipt_identity"]["sha256"] = "d" * 64
    elif mutation == "output-root-identity-drift":
        marker["output_root_identity"]["inode"] += 1
    elif mutation == "staged-mode":
        marker_mode = 0o600
    else:
        raise AssertionError(f"unknown mutation: {mutation}")
    _rewrite_unterminated_readonly(marker_path, marker, mode=marker_mode)

    error_type = module.BootstrapError if module is BOOTSTRAP else module.AuthorityError
    with pytest.raises(error_type):
        _validate_v6_publication_with_consumer(
            module,
            output=output,
            record=record,
            receipt_identity=receipt_identity,
        )


@pytest.mark.parametrize("module", [BOOTSTRAP, AUTHORITY], ids=["bootstrap", "authority"])
@pytest.mark.parametrize("mutation", ["extra-root-member", "late-basetemp-child"])
def test_v6_full_preflight_consumers_reject_closed_tree_mutation(
    tmp_path: Path,
    module: ModuleType,
    mutation: str,
) -> None:
    output, record, receipt_identity, _gate_a, _planned = _v6_full_preflight_publication(tmp_path)
    if mutation == "extra-root-member":
        unknown = output / "unknown-member"
    else:
        unknown = (
            output
            / BOOTSTRAP.FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME
            / BOOTSTRAP.FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME
            / "late-child"
        )
    unknown.write_bytes(b"unknown retained bytes\n")

    error_type = module.BootstrapError if module is BOOTSTRAP else module.AuthorityError
    with pytest.raises(error_type):
        _validate_v6_publication_with_consumer(
            module,
            output=output,
            record=record,
            receipt_identity=receipt_identity,
        )
    assert unknown.read_bytes() == b"unknown retained bytes\n"


def test_bootstrap_final_full_preflight_rejects_rebound_v5_receipt(
    tmp_path: Path,
) -> None:
    output, record, receipt_identity, gate_a, planned = _v6_full_preflight_publication(tmp_path)
    stale_record = copy.deepcopy(record)
    stale_record["schema_version"] = "noncert-cuts-ab16-gate-a-full-preflight-receipt-v5"
    receipt_path = output / "receipt.json"
    _rewrite_unterminated_readonly(receipt_path, stale_record)
    stale_receipt_identity = {
        "mode": 0o444,
        **BOOTSTRAP.authority.detached_identity(
            BOOTSTRAP.authority.snapshot_regular(receipt_path)
        ),
    }
    gate_a["full_preflight_receipt_identity"] = stale_receipt_identity
    _rewrite_unterminated_readonly(
        output / "receipt.commit.json",
        {
            "output_root_identity": record["output_root_identity"],
            "receipt_identity": stale_receipt_identity,
            "schema_version": BOOTSTRAP.FINAL_FULL_PREFLIGHT_PUBLICATION_COMMIT_SCHEMA,
            "status": "COMMITTED",
        },
    )

    with pytest.raises(BOOTSTRAP.BootstrapError, match="no longer joins Gate A"):
        BOOTSTRAP._validate_final_full_preflight(  # noqa: SLF001
            stale_record,
            gate_a=gate_a,
            planned=planned,
            receipt_identity=stale_receipt_identity,
        )


def test_bootstrap_v6_full_preflight_rejects_protocol_plugin_cross_binding(
    tmp_path: Path,
) -> None:
    _output, record, receipt_identity, gate_a, planned = _v6_full_preflight_publication(tmp_path)
    assert (
        BOOTSTRAP._validate_final_full_preflight(  # noqa: SLF001
            record,
            gate_a=gate_a,
            planned=planned,
            receipt_identity=receipt_identity,
        )
        == record
    )

    tampered = copy.deepcopy(record)
    tampered["pytest_collection_protocol_identity"] = copy.deepcopy(
        record["pytest_collection_plugin_identity"]
    )
    command = tampered["command"]
    assert isinstance(command, dict)
    argv = command["argv"]
    assert isinstance(argv, list)
    protocol_path_index = argv.index("--collection-protocol-source") + 1
    plugin_identity = record["pytest_collection_plugin_identity"]
    assert isinstance(plugin_identity, dict)
    argv[protocol_path_index] = plugin_identity["path"]

    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="exact current-HEAD PASS",
    ):
        BOOTSTRAP._validate_final_full_preflight(  # noqa: SLF001
            tampered,
            gate_a=gate_a,
            planned=planned,
            receipt_identity=receipt_identity,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "resource-measurement",
        "resource-source",
        "release-identity",
        "observation-output-root",
        "repository-disk-identity",
    ),
)
def test_bootstrap_v6_full_preflight_replays_resource_closure(
    tmp_path: Path,
    mutation: str,
) -> None:
    _output, record, receipt_identity, gate_a, planned = (
        _v6_full_preflight_publication(tmp_path)
    )
    tampered = copy.deepcopy(record)
    resource_record = tampered["resource_admission"]
    assert isinstance(resource_record, dict)
    if mutation == "resource-measurement":
        resource_record["measurements"]["mem_available_bytes"] += 1
    elif mutation == "resource-source":
        tampered["resource_admission_source_identity"]["sha256"] = "0" * 64
    elif mutation == "release-identity":
        tampered["resource_lock_release_identities"][0]["inode"] += 1
    elif mutation == "observation-output-root":
        resource_record["observation_context"]["target"] = str(tmp_path / "replacement")
        resource_record["observation_context_sha256"] = (
            RESOURCE_ADMISSION._canonical_sha256(  # noqa: SLF001
                resource_record["observation_context"]
            )
        )
    elif mutation == "repository-disk-identity":
        resource_record["disk_target"]["inode"] += 1
    else:
        raise AssertionError(f"unknown mutation: {mutation}")

    with pytest.raises(BOOTSTRAP.BootstrapError, match="resource"):
        BOOTSTRAP._validate_final_full_preflight(  # noqa: SLF001
            tampered,
            gate_a=gate_a,
            planned=planned,
            receipt_identity=receipt_identity,
        )


@pytest.mark.parametrize(
    "field",
    (
        "resource_admission",
        "resource_admission_source_identity",
        "resource_lock_release_identities",
    ),
)
def test_bootstrap_v6_full_preflight_rejects_missing_resource_contract_field(
    tmp_path: Path,
    field: str,
) -> None:
    _output, record, receipt_identity, gate_a, planned = (
        _v6_full_preflight_publication(tmp_path)
    )
    incomplete = copy.deepcopy(record)
    incomplete.pop(field)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="key set drifted"):
        BOOTSTRAP._validate_final_full_preflight(  # noqa: SLF001
            incomplete,
            gate_a=gate_a,
            planned=planned,
            receipt_identity=receipt_identity,
        )


def test_gate_b_renderer_uses_live_planned_identity_and_joins_staged_bytes(
    tmp_path: Path,
) -> None:
    raw = b"print('selected Gate-B renderer')\n"
    planned = {
        "mode": 0o644,
        "path": str(tmp_path / "live/ab16_campaign_bootstrap_v2.py"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    staged = {
        "device": 1,
        "inode": 2,
        "mode": 0o444,
        "path": str(tmp_path / "package-source-staging/script.ab16_campaign_bootstrap_v2.py"),
        "sha256": planned["sha256"],
        "size_bytes": planned["size_bytes"],
    }
    assert AUTHORITY._join_gate_b_renderer_identity(planned, staged) == planned  # noqa: SLF001

    for field, replacement in (("sha256", "f" * 64), ("size_bytes", len(raw) + 1)):
        drifted = copy.deepcopy(staged)
        drifted[field] = replacement
        with pytest.raises(
            AUTHORITY.AuthorityError,
            match="live/staged renderer identity drifted",
        ):
            AUTHORITY._join_gate_b_renderer_identity(planned, drifted)  # noqa: SLF001


def _manager_candidate_fixture(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    repository = tmp_path / "repository"
    repository.mkdir()
    planned, _, _, _ = _planned_sources(tmp_path)
    manager_path = (
        repository
        / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724/manager_attestor_v4.py"
    )
    _regular(manager_path, b"# selected live manager attestor\n", mode=0o644)
    planned["script.manager_attestor_v4"] = _full(manager_path)
    history_path = (
        repository
        / ".artifacts/noncert_cuts_ab16_20260724/"
        "gate-a-terminal-reference-history-freeze-a001/manifest.json"
    )
    _regular(history_path, b'{"fixture":"history-freeze"}\n', mode=0o400)
    planned["input.history_freeze_manifest"] = _full(history_path)
    root = {
        "repository_head": HEAD,
        "run_nonce": "run-manager-source-join-fixture",
    }
    candidate: dict[str, object] = {
        "arm_launch_authorized": False,
        "candidate_id": "",
        "candidate_only": True,
        "created_at_utc": "2026-07-24T00:00:00Z",
        "formal_campaign_creation_authorized": False,
        "gate_a_receipt_identity": {
            "path": str(tmp_path / "gate-a.json"),
            "sha256": "a" * 64,
            "size_bytes": 1,
        },
        "native_budget_helper_source_identity": dict(
            planned["system.native_budget_helper"]
        ),
        "package_verifier_source_identity": dict(
            planned["script.package_independent_verifier_v1"]
        ),
        "path_preregistration_identity": {
            "path": str(tmp_path / "preregistration.json"),
            "sha256": "b" * 64,
            "size_bytes": 1,
        },
        "planned_source_identities": planned,
        "planned_source_set_digest": hashlib.sha256(
            AUTHORITY.canonical_json(planned)
        ).hexdigest(),
        "purpose": "AB16_OFFLINE_NONAUTHORIZING_CANDIDATE",
        "repository_head": HEAD,
        "repository_root": str(repository),
        "run_nonce": root["run_nonce"],
        "schema_version": "noncert-cuts-ab16-bootstrap-offline-candidate-v4",
        "target_campaign_dir": str(tmp_path / "campaigns" / str(root["run_nonce"])),
    }
    without_id = dict(candidate)
    without_id.pop("candidate_id")
    candidate["candidate_id"] = hashlib.sha256(
        AUTHORITY.canonical_json(without_id)
    ).hexdigest()
    return candidate, root, planned["script.manager_attestor_v4"]


def _manager_source_join_fixture(
    tmp_path: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    candidate, root_base, planned = _manager_candidate_fixture(tmp_path)
    planned_sources = AUTHORITY._candidate_planned_source_identities(  # noqa: SLF001
        candidate,
        directory=Path(str(candidate["target_campaign_dir"])),
        root=root_base,
    )
    planned = planned_sources["script.manager_attestor_v4"]
    epoch_attestor = {
        **planned,
        "requested_path": planned["path"],
    }
    root = {
        **root_base,
        "manager_epoch": {
            "attestation_toolchain": {
                "attestor": epoch_attestor,
            },
        },
    }
    selected = {
        field: planned[field]
        for field in ("path", "sha256", "size_bytes")
    }
    staged = {
        "path": str(tmp_path / "staging/script.manager_attestor_v4.py"),
        "sha256": planned["sha256"],
        "size_bytes": planned["size_bytes"],
    }
    packaged = {
        "path": str(tmp_path / "package/payload/tool.manager_attestor_v4.py"),
        "sha256": planned["sha256"],
        "size_bytes": planned["size_bytes"],
    }
    return root, selected, staged, packaged, dict(planned)


def _root_source_join_fixture(
    tmp_path: Path,
) -> tuple[
    Path,
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    candidate, root_base, _ = _manager_candidate_fixture(tmp_path)
    directory = Path(str(candidate["target_campaign_dir"]))
    planned = candidate["planned_source_identities"]
    script_package_roles = {
        "campaign_authority_v4": "campaign_authority_v4.py",
        **{
            role.removeprefix("tool.").removesuffix(".py"): role
            for role in AUTHORITY.REQUIRED_PACKAGE_ROLES
            if role.startswith("tool.")
            and role.endswith(".py")
            and role != "tool.ab16_gate_b_qualification_v1.py"
        },
    }
    system_package_roles = {
        role.removeprefix("system.").removesuffix(".bin"): role
        for role in AUTHORITY.REQUIRED_PACKAGE_ROLES
        if role.startswith("system.") and role.endswith(".bin")
    }
    input_package_roles: dict[str, str] = {}
    for package_role in AUTHORITY.REQUIRED_PACKAGE_ROLES:
        if not package_role.startswith("input."):
            continue
        root_role = package_role.removeprefix("input.")
        if root_role == "ab16_repository_snapshot.zip":
            root_role = "ab16_repository_snapshot_archive"
        else:
            root_role = root_role.removesuffix(".json").removesuffix(".txt")
        input_package_roles[root_role] = package_role
    source_roles = {
        **script_package_roles,
        **system_package_roles,
        **input_package_roles,
    }
    files: dict[str, object] = {}
    sources: dict[str, object] = {}
    tools: dict[str, object] = {}
    inputs: dict[str, object] = {}
    snapshot_paths = {
        "candidate_placements": "data/preprocessed/candidate_placements.json",
        "canonical_rules": "rules/canonical_rules.json",
        "cuts_mandatory_schedule": (
            "docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/"
            "04_cuts_mandatory_schedule.md"
        ),
        "mandatory_instances": "data/preprocessed/mandatory_exact_instances.json",
        "preflight_gate": "scripts/preflight_gate.py",
        "project_lock": "PROJECT_LOCK.md",
    }
    materialized: dict[str, object] = {}
    for root_role, package_role in source_roles.items():
        if package_role == "input.ab16_offline_candidate.json":
            raw = AUTHORITY.canonical_json(candidate)
        else:
            if package_role == "campaign_authority_v4.py":
                planned_role = "script.campaign_authority_v4"
            elif package_role.startswith("tool."):
                planned_role = f"script.{root_role}"
            elif package_role.startswith("system."):
                planned_role = f"system.{root_role}"
            else:
                planned_role = f"input.{root_role}"
            planned_identity = planned.get(planned_role)
            raw = (
                Path(str(planned_identity["path"])).read_bytes()
                if planned_identity is not None
                else f"{package_role}\n".encode()
            )
        source_path = tmp_path / "staging" / package_role
        package_path = f"payload/{package_role}"
        packaged_path = tmp_path / "package" / package_path
        _regular(source_path, raw)
        _regular(packaged_path, raw)
        source_snapshot = AUTHORITY.snapshot_regular(source_path)
        packaged_snapshot = AUTHORITY.snapshot_regular(packaged_path)
        files[package_path] = packaged_snapshot
        sources[package_role] = {
            "package_path": package_path,
            "source_identity": AUTHORITY.full_identity(source_snapshot),
        }
        selected = AUTHORITY.detached_identity(packaged_snapshot)
        if root_role == "manager_attestor_v4":
            manager = planned["script.manager_attestor_v4"]
            selected = {
                field: manager[field]
                for field in ("path", "sha256", "size_bytes")
            }
        elif root_role == "history_freeze_manifest":
            history = planned["input.history_freeze_manifest"]
            selected = {
                field: history[field]
                for field in ("path", "sha256", "size_bytes")
            }
        elif root_role in snapshot_paths:
            materialized_path = tmp_path / "materialized" / snapshot_paths[root_role]
            _regular(materialized_path, raw)
            selected = AUTHORITY.detached_identity(
                AUTHORITY.snapshot_regular(materialized_path)
            )
            materialized[snapshot_paths[root_role]] = selected
        if root_role in script_package_roles or root_role in system_package_roles:
            tools[root_role] = selected
        else:
            inputs[root_role] = selected
    materialization_path = tmp_path / "materialization.json"
    _regular(materialization_path, b'{"status":"PASS"}\n')
    materialization_identity = AUTHORITY.detached_identity(
        AUTHORITY.snapshot_regular(materialization_path)
    )
    inputs["ab16_repository_snapshot_materialization"] = materialization_identity
    inputs["ab16_package_independent_replay"] = {
        "path": str(tmp_path / "package-independent-replay.json"),
        "sha256": "c" * 64,
        "size_bytes": 1,
    }
    manager = planned["script.manager_attestor_v4"]
    root = {
        **root_base,
        "authority_tools": tools,
        "manager_epoch": {
            "attestation_toolchain": {
                "attestor": {
                    **manager,
                    "requested_path": manager["path"],
                },
            },
        },
        "strict_inputs": inputs,
    }
    repository_snapshot = {
        "materialization_identity": materialization_identity,
        "member_identities": materialized,
    }
    return directory, root, files, sources, repository_snapshot, planned


def test_root_source_join_wiring_accepts_only_two_exact_live_roles(
    tmp_path: Path,
) -> None:
    directory, root, files, sources, repository_snapshot, planned = _root_source_join_fixture(
        tmp_path
    )
    AUTHORITY._validate_root_source_joins(  # noqa: SLF001
        directory,
        root,
        files,
        sources,
        repository_snapshot,
    )

    ordinary = planned["script.ab16_authority_v1"]
    root["authority_tools"]["ab16_authority_v1"] = {
        field: ordinary[field]
        for field in ("path", "sha256", "size_bytes")
    }
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._validate_root_source_joins(  # noqa: SLF001
            directory,
            root,
            files,
            sources,
            repository_snapshot,
        )
    assert exc_info.value.code == "CAMPAIGN_ROOT_INVALID"
    assert exc_info.value.detail == "source join ab16_authority_v1"


@pytest.mark.parametrize("mutation", ["absent", "tampered"])
def test_root_source_join_binds_ab16_budgeted_writer_adapter(
    tmp_path: Path,
    mutation: str,
) -> None:
    directory, root, files, sources, repository_snapshot, _planned = (
        _root_source_join_fixture(tmp_path)
    )
    tools = root["authority_tools"]
    assert isinstance(tools, dict)
    if mutation == "absent":
        tools.pop("ab16_budgeted_writers_v1")
    else:
        identity = tools["ab16_budgeted_writers_v1"]
        assert isinstance(identity, dict)
        identity["sha256"] = "0" * 64

    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._validate_root_source_joins(  # noqa: SLF001
            directory,
            root,
            files,
            sources,
            repository_snapshot,
        )
    assert exc_info.value.code == "CAMPAIGN_ROOT_INVALID"
    expected_detail = (
        "required AB16 root roles absent"
        if mutation == "absent"
        else "source join ab16_budgeted_writers_v1"
    )
    assert exc_info.value.detail == expected_detail


def test_campaign_context_closes_gate_approvals_before_live_source_joins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign = tmp_path / "run-context-gate-order"
    campaign.mkdir()
    root = {
        "manager_epoch": {"schema": "fixture"},
        "package": {
            "manifest_identity": {"fixture": "manifest"},
            "package_dir": str(tmp_path / "package"),
            "package_id": "a" * 64,
            "seal_identity": {"fixture": "seal"},
        },
        "repository_head": HEAD,
        "run_nonce": campaign.name,
        "stage_topology": {
            "gate1_v4": {
                "positive_control": {
                    "binding_paths": {},
                    "binding_seal_path": "/fixture/seal",
                    "common_artifact_paths": {},
                    "common_manifest_path": "/fixture/manifest",
                },
            },
        },
    }
    root_path = campaign / "campaign-root.json"
    root_path.write_bytes(AUTHORITY.canonical_json(root))
    root_snapshot = AUTHORITY.snapshot_regular(root_path)
    package_manifest = {
        "manager_epoch": root["manager_epoch"],
        "repository_head": HEAD,
        "run_nonce": campaign.name,
    }

    class CampaignTool:
        @staticmethod
        def validate_campaign_root(value: object, *, campaign_dir: Path) -> None:
            assert value == root
            assert campaign_dir == campaign

        @staticmethod
        def verify_package(
            package_dir: str,
            *,
            expected_manager_epoch: object,
            replay_external: bool,
        ) -> dict[str, object]:
            assert package_dir == root["package"]["package_dir"]
            assert expected_manager_epoch == root["manager_epoch"]
            assert replay_external is True
            return {
                field: root["package"][field]
                for field in ("manifest_identity", "package_id", "seal_identity")
            }

    monkeypatch.setattr(
        AUTHORITY,
        "_package_sources",
        lambda _path: ({}, package_manifest, {}),
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_source_snapshot",
        lambda _files, _sources, _role: root_snapshot,
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_load_module",
        lambda _snapshot, _name: CampaignTool,
    )
    repository_snapshot = {
        "materialization_identity": {"fixture": "materialization"},
        "member_identities": {},
    }
    monkeypatch.setattr(
        AUTHORITY,
        "_replay_repository_snapshot",
        lambda **_kwargs: repository_snapshot,
    )
    order: list[str] = []
    monkeypatch.setattr(
        AUTHORITY,
        "_validate_gate_approvals",
        lambda _context: order.append("gate-approvals"),
    )

    def source_joins(*_args: object) -> None:
        assert order == ["gate-approvals"]
        order.append("source-joins")

    monkeypatch.setattr(AUTHORITY, "_validate_root_source_joins", source_joins)

    context = AUTHORITY._campaign_context(campaign)  # noqa: SLF001
    assert order == ["gate-approvals", "source-joins"]
    assert context["directory"] == campaign


def test_manager_attestor_source_join_accepts_only_candidate_and_epoch_bound_live_path(
    tmp_path: Path,
) -> None:
    root, selected, staged, packaged, planned = _manager_source_join_fixture(tmp_path)
    assert len({selected["path"], staged["path"], packaged["path"]}) == 3
    assert {
        (selected["sha256"], selected["size_bytes"]),
        (staged["sha256"], staged["size_bytes"]),
        (packaged["sha256"], packaged["size_bytes"]),
    } == {(planned["sha256"], planned["size_bytes"])}

    AUTHORITY._validate_manager_attestor_source_join(  # noqa: SLF001
        root=root,
        selected=selected,
        source_identity=staged,
        packaged_identity=packaged,
        planned_identity=planned,
    )


@pytest.mark.parametrize(
    ("target", "field", "replacement"),
    (
        ("selected", "path", "/different/live/manager_attestor_v4.py"),
        ("selected", "sha256", "f" * 64),
        ("selected", "size_bytes", 999),
        ("epoch", "path", "/different/epoch/manager_attestor_v4.py"),
        ("epoch", "requested_path", "/different/requested/manager_attestor_v4.py"),
        ("staged", "sha256", "e" * 64),
        ("packaged", "size_bytes", 998),
        ("planned", "device", 0),
        ("planned", "inode", 0),
        ("planned", "mode", 0o600),
    ),
)
def test_manager_attestor_source_join_rejects_identity_drift(
    tmp_path: Path,
    target: str,
    field: str,
    replacement: object,
) -> None:
    root, selected, staged, packaged, planned = _manager_source_join_fixture(tmp_path)
    records = {
        "selected": selected,
        "epoch": root["manager_epoch"]["attestation_toolchain"]["attestor"],
        "staged": staged,
        "packaged": packaged,
        "planned": planned,
    }
    records[target][field] = replacement

    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._validate_manager_attestor_source_join(  # noqa: SLF001
            root=root,
            selected=selected,
            source_identity=staged,
            packaged_identity=packaged,
            planned_identity=planned,
        )
    assert exc_info.value.code == "CAMPAIGN_ROOT_INVALID"
    assert exc_info.value.detail == "source join manager_attestor_v4"


def test_manager_attestor_candidate_rejects_resealed_alternate_live_path(
    tmp_path: Path,
) -> None:
    candidate, root, original = _manager_candidate_fixture(tmp_path)
    alternate_path = tmp_path / "alternate/manager_attestor_v4.py"
    _regular(
        alternate_path,
        Path(str(original["path"])).read_bytes(),
        mode=int(original["mode"]),
    )
    planned = candidate["planned_source_identities"]
    planned["script.manager_attestor_v4"] = _full(alternate_path)
    candidate["planned_source_set_digest"] = hashlib.sha256(
        AUTHORITY.canonical_json(planned)
    ).hexdigest()
    without_id = dict(candidate)
    without_id.pop("candidate_id")
    candidate["candidate_id"] = hashlib.sha256(
        AUTHORITY.canonical_json(without_id)
    ).hexdigest()

    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._candidate_planned_source_identities(  # noqa: SLF001
            candidate,
            directory=Path(str(candidate["target_campaign_dir"])),
            root=root,
        )
    assert exc_info.value.code == "CAMPAIGN_ROOT_INVALID"
    assert exc_info.value.detail == "candidate planned source binding script.manager_attestor_v4"


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("schema_version", "noncert-cuts-ab16-bootstrap-offline-candidate-v1"),
        ("candidate_only", False),
        ("formal_campaign_creation_authorized", True),
        ("candidate_id", "f" * 64),
        ("planned_source_set_digest", "e" * 64),
    ),
)
def test_manager_attestor_candidate_rejects_semantic_or_self_digest_drift(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    candidate, root, _ = _manager_candidate_fixture(tmp_path)
    candidate[field] = replacement
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._candidate_planned_source_identities(  # noqa: SLF001
            candidate,
            directory=Path(str(candidate["target_campaign_dir"])),
            root=root,
        )
    assert exc_info.value.code == "CAMPAIGN_ROOT_INVALID"
    assert exc_info.value.detail == "candidate planned source binding"


def test_history_freeze_candidate_rejects_resealed_alternate_live_path(
    tmp_path: Path,
) -> None:
    candidate, root, _ = _manager_candidate_fixture(tmp_path)
    planned = candidate["planned_source_identities"]
    original = planned["input.history_freeze_manifest"]
    alternate_path = tmp_path / "alternate/history-freeze-manifest.json"
    _regular(
        alternate_path,
        Path(str(original["path"])).read_bytes(),
        mode=int(original["mode"]),
    )
    planned["input.history_freeze_manifest"] = _full(alternate_path)
    candidate["planned_source_set_digest"] = hashlib.sha256(
        AUTHORITY.canonical_json(planned)
    ).hexdigest()
    without_id = dict(candidate)
    without_id.pop("candidate_id")
    candidate["candidate_id"] = hashlib.sha256(
        AUTHORITY.canonical_json(without_id)
    ).hexdigest()

    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._candidate_planned_source_identities(  # noqa: SLF001
            candidate,
            directory=Path(str(candidate["target_campaign_dir"])),
            root=root,
        )
    assert exc_info.value.code == "CAMPAIGN_ROOT_INVALID"
    assert exc_info.value.detail == "candidate planned source binding input.history_freeze_manifest"


def test_manager_attestor_source_join_rejects_live_replacement(
    tmp_path: Path,
) -> None:
    root, selected, staged, packaged, planned = _manager_source_join_fixture(tmp_path)
    live = Path(str(planned["path"]))
    live.chmod(0o644)
    live.write_bytes(b"# replaced live manager attestor\n")

    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._validate_manager_attestor_source_join(  # noqa: SLF001
            root=root,
            selected=selected,
            source_identity=staged,
            packaged_identity=packaged,
            planned_identity=planned,
        )
    assert exc_info.value.code == "CAMPAIGN_ROOT_INVALID"
    assert exc_info.value.detail == "source join manager_attestor_v4"


def test_history_freeze_source_join_accepts_only_candidate_bound_live_path(
    tmp_path: Path,
) -> None:
    candidate, root, _ = _manager_candidate_fixture(tmp_path)
    planned = AUTHORITY._candidate_planned_source_identities(  # noqa: SLF001
        candidate,
        directory=Path(str(candidate["target_campaign_dir"])),
        root=root,
    )["input.history_freeze_manifest"]
    selected = {
        field: planned[field]
        for field in ("path", "sha256", "size_bytes")
    }
    staged = {
        "path": str(tmp_path / "staging/input.history_freeze_manifest"),
        "sha256": planned["sha256"],
        "size_bytes": planned["size_bytes"],
    }
    packaged = {
        "path": str(tmp_path / "package/payload/input.history_freeze_manifest.json"),
        "sha256": planned["sha256"],
        "size_bytes": planned["size_bytes"],
    }

    AUTHORITY._validate_live_planned_source_join(  # noqa: SLF001
        root_role="history_freeze_manifest",
        selected=selected,
        source_identity=staged,
        packaged_identity=packaged,
        planned_identity=planned,
    )
    selected["path"] = str(tmp_path / "alternate/history-freeze.json")
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._validate_live_planned_source_join(  # noqa: SLF001
            root_role="history_freeze_manifest",
            selected=selected,
            source_identity=staged,
            packaged_identity=packaged,
            planned_identity=planned,
        )
    assert exc_info.value.code == "CAMPAIGN_ROOT_INVALID"
    assert exc_info.value.detail == "source join history_freeze_manifest"


def test_gate_a_evidence_mutation_fails_before_campaign_creation(
    tmp_path: Path,
) -> None:
    (tmp_path / "campaigns").mkdir()
    (tmp_path / "repository").mkdir()
    campaign = tmp_path / "campaigns/run-gate-a-mutation-v2"
    epoch = _manager_epoch(tmp_path)
    gate_a, evidence_paths = _gate_a_record(
        tmp_path,
        campaign_dir=campaign,
        planned_digest="a" * 64,
        manager_epoch=epoch,
    )
    gate_a_path = tmp_path / "gate-a.json"
    _write_authority_json(gate_a_path, gate_a)

    mutated = evidence_paths["disposable_detached_replay_identity"]
    mutated.chmod(0o644)
    mutated.write_bytes(b'{"field":"mutated"}')
    mutated.chmod(0o444)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="bytes drifted"):
        BOOTSTRAP.build_gate_a_candidate(
            output_path=tmp_path / "candidate.json",
            gate_a_receipt=gate_a_path,
            repository_root=tmp_path / "repository",
            target_campaign_dir=campaign,
            resource_budget_profile=_launch_ready_budget_profile(tmp_path),
            resource_calibration_bundle_paths=(
                _resource_calibration_paths(tmp_path)
            ),
            strict_input_paths={},
            system_tool_paths={},
        )
    assert not campaign.exists()
    assert not (tmp_path / "candidate.json").exists()


def test_current_manager_epoch_drift_fails_before_campaign_mkdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "campaigns").mkdir()
    (tmp_path / "repository").mkdir()
    campaign = tmp_path / "campaigns/run-manager-drift-v2"
    planned, scripts, systems, strict = _planned_sources(tmp_path)
    digest = BOOTSTRAP._source_set_digest(planned)  # noqa: SLF001
    epoch = _manager_epoch(tmp_path)
    gate_a, _ = _gate_a_record(
        tmp_path,
        campaign_dir=campaign,
        planned_digest=digest,
        manager_epoch=epoch,
    )
    gate_a_path = tmp_path / "gate-a.json"
    gate_a_identity = _write_authority_json(gate_a_path, gate_a)
    resource_budget_profile = _launch_ready_budget_profile(tmp_path)
    resource_calibration_paths = _resource_calibration_paths(tmp_path)

    monkeypatch.setattr(
        BOOTSTRAP,
        "_planned_source_identities",
        lambda **_kwargs: (planned, scripts, systems, strict),
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_observe_repository_head",
        lambda *_args, **_kwargs: HEAD,
    )
    candidate_result = BOOTSTRAP.build_gate_a_candidate(
        output_path=tmp_path / "candidate.json",
        gate_a_receipt=gate_a_path,
        repository_root=tmp_path / "repository",
        target_campaign_dir=campaign,
        resource_budget_profile=resource_budget_profile,
        resource_calibration_bundle_paths=resource_calibration_paths,
        strict_input_paths={},
        system_tool_paths={},
    )
    final_identity = _regular(
        tmp_path / "gate-b-final.json",
        BOOTSTRAP.authority.canonical_json({})[:-1],
    )
    epoch_path = tmp_path / "gate-b-epoch.json"
    epoch_identity = _regular(
        epoch_path,
        BOOTSTRAP.authority.canonical_json(
            {
                "manager_epoch": epoch,
                "publisher": _gate_b_publisher(epoch_path, sequence=1),
            }
        ),
    )
    pre_full_resource_identity = _regular(
        tmp_path / "gate-b-resource-before-full.json",
        b"{}\n",
    )
    pre_publication_resource_identity = _regular(
        tmp_path / "gate-b-resource-before-publication.json",
        b"{}\n",
    )
    gate_b_path = tmp_path / "gate-b.json"
    gate_b = {
        "approval_id": "gate-b-fixture-v2",
        "arm_launch_authorized": False,
        "bootstrap_budget_contract_identity": candidate_result["candidate"][
            "bootstrap_budget_contract_identity"
        ],
        "candidate_identity": candidate_result["candidate_identity"],
        "created_at_utc": "2026-07-24T00:01:00Z",
        "decision": "APPROVED",
        "final_full_preflight_receipt_identity": final_identity,
        "formal_campaign_creation_authorized": True,
        "formal_root_budget_contract_identity": candidate_result["candidate"][
            "formal_root_budget_contract_identity"
        ],
        "gate": "B",
        "gate_a_receipt_identity": gate_a_identity,
        "gate_b_epoch_observation_identity": epoch_identity,
        "native_budget_helper_source_identity": dict(
            planned["system.native_budget_helper"]
        ),
        "package_verifier_source_identity": dict(
            planned["script.package_independent_verifier_v1"]
        ),
        "planned_source_set_digest": digest,
        "pre_full_resource_gate_identity": pre_full_resource_identity,
        "pre_publication_resource_gate_identity": pre_publication_resource_identity,
        "publisher": _gate_b_publisher(gate_b_path),
        "purpose": BOOTSTRAP.GATE_B_PURPOSE,
        "repository_head": HEAD,
        "repository_root": str(tmp_path / "repository"),
        "resource_budget_profile_identity": candidate_result["candidate"][
            "resource_budget_profile_identity"
        ],
        "resource_calibration_bundle_identities": candidate_result[
            "candidate"
        ]["resource_calibration_bundle_identities"],
        "run_nonce": campaign.name,
        "schema_version": BOOTSTRAP.GATE_B_SCHEMA,
        "target_campaign_dir": str(campaign),
    }
    _write_authority_json(gate_b_path, gate_b)
    drifted_epoch = copy.deepcopy(epoch)
    drifted_epoch["boot_id"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_kwargs: {
            "manager_epoch": drifted_epoch,
            "transcript": {},
        },
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_check_epoch_toolchain",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_validate_final_full_preflight",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_validate_gate_b_epoch_observation",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_read_gate_b_resource_gate",
        lambda identity_value, **_kwargs: ({"status": "PASS"}, identity_value),
    )
    closure_replays: list[Mapping[str, Mapping[str, object]] | None] = []
    monkeypatch.setattr(
        BOOTSTRAP,
        "_replay_prepackage_closure",
        lambda *, planned=None: closure_replays.append(planned),
    )

    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="current manager/boot epoch differs",
    ):
        BOOTSTRAP.bootstrap_campaign(
            campaign_dir=campaign,
            repository_root=tmp_path / "repository",
            gate_a_receipt=gate_a_path,
            offline_candidate=tmp_path / "candidate.json",
            gate_b_approval=gate_b_path,
            resource_budget_profile=resource_budget_profile,
            resource_calibration_bundle_paths=resource_calibration_paths,
            strict_input_paths={},
            system_tool_paths={},
        )
    assert closure_replays == [None, None]
    assert not campaign.exists()


def _gate_b_record(tmp_path: Path) -> dict[str, object]:
    campaign = tmp_path / "campaigns/run-gate-b-evidence-v2"
    approval_path = tmp_path / "gate-b/approval.json"
    candidate = _regular(tmp_path / "gate-b/candidate.json", b"{}\n")
    gate_a = _regular(tmp_path / "gate-b/gate-a.json", b"{}\n")
    return {
        "approval_id": "gate-b-evidence-v2", "arm_launch_authorized": False,
        "bootstrap_budget_contract_identity": {
            key: value
            for key, value in _regular(
                tmp_path
                / "campaigns/run-gate-b-evidence-v2/bootstrap-authority/bootstrap-budget-contract.json",
                b"{}\n",
            ).items()
            if key != "mode"
        },
        "candidate_identity": {key: candidate[key] for key in ("path", "sha256", "size_bytes")},
        "created_at_utc": "2026-07-24T00:01:00Z", "decision": "APPROVED",
        "final_full_preflight_receipt_identity": _regular(tmp_path / "gate-b/final.json", b"{}\n"),
        "formal_campaign_creation_authorized": True, "gate": "B",
        "formal_root_budget_contract_identity": {
            key: value
            for key, value in _regular(
                tmp_path
                / "campaigns/run-gate-b-evidence-v2/formal-ab16/artifacts/formal-root-budget-contract.json",
                b"{}\n",
            ).items()
            if key != "mode"
        },
        "gate_a_receipt_identity": {key: gate_a[key] for key in ("path", "sha256", "size_bytes")},
        "gate_b_epoch_observation_identity": _regular(tmp_path / "gate-b/epoch.json", b"{}\n"),
        "native_budget_helper_source_identity": BOOTSTRAP.authority.snapshot_tool(
            NATIVE_HELPER
        )[1],
        "package_verifier_source_identity": {
            "device": 1,
            "inode": 1,
            "mode": 0o644,
            "mode_octal": "0644",
            "path": str(tmp_path / "repository/package_independent_verifier_v1.py"),
            "sha256": "b" * 64,
            "size_bytes": 1,
        },
        "planned_source_set_digest": "a" * 64,
        "pre_full_resource_gate_identity": _regular(
            tmp_path / "gate-b/resource-before-full.json",
            b"{}\n",
        ),
        "pre_publication_resource_gate_identity": _regular(
            tmp_path / "gate-b/resource-before-publication.json",
            b"{}\n",
        ),
        "publisher": _gate_b_publisher(approval_path),
        "purpose": BOOTSTRAP.GATE_B_PURPOSE,
        "repository_head": HEAD, "repository_root": str(tmp_path / "repository"),
        "resource_budget_profile_identity": _regular(
            tmp_path / "gate-b/resource-budget-profile.json",
            b"{}\n",
        ),
        "resource_calibration_bundle_identities": {
            stage: {
                key: value
                for key, value in _regular(
                    tmp_path / f"gate-b/calibration-{index}.json",
                    BOOTSTRAP._budget_canonical_json(  # noqa: SLF001
                        {"stage": stage}
                    ),
                ).items()
                if key != "mode"
            }
            for index, stage in enumerate(
                BOOTSTRAP.RESOURCE_CALIBRATION_STAGES,
                start=1,
            )
        },
        "run_nonce": campaign.name, "schema_version": BOOTSTRAP.GATE_B_SCHEMA,
        "target_campaign_dir": str(campaign),
    }


@pytest.mark.parametrize(
    ("field", "mutation"),
    [
        ("final_full_preflight_receipt_identity", "missing"),
        ("gate_b_epoch_observation_identity", "missing"),
        ("pre_full_resource_gate_identity", "missing"),
        ("pre_publication_resource_gate_identity", "missing"),
        ("final_full_preflight_receipt_identity", "drift"),
        ("gate_b_epoch_observation_identity", "drift"),
        ("pre_full_resource_gate_identity", "drift"),
        ("pre_publication_resource_gate_identity", "drift"),
    ],
)
def test_gate_b_independent_evidence_identity_is_fail_closed(
    tmp_path: Path,
    field: str,
    mutation: str,
) -> None:
    record = _gate_b_record(tmp_path)
    if mutation == "missing":
        record.pop(field)
    else:
        identity = dict(record[field])
        identity["sha256"] = "f" * 64
        record[field] = identity
    with pytest.raises(BOOTSTRAP.BootstrapError):
        BOOTSTRAP._validate_gate_b(record)  # noqa: SLF001


def test_gate_b_v7_publisher_identity_and_schema_are_strict(
    tmp_path: Path,
) -> None:
    record = _gate_b_record(tmp_path)
    assert BOOTSTRAP._validate_gate_b(record) == record  # noqa: SLF001

    mutations: list[dict[str, object]] = []
    old_schema = copy.deepcopy(record)
    old_schema["schema_version"] = (
        "noncert-cuts-ab16-bootstrap-gate-b-approval-v6"
    )
    mutations.append(old_schema)
    missing = copy.deepcopy(record)
    missing.pop("publisher")
    mutations.append(missing)
    extra = copy.deepcopy(record)
    extra["unexpected"] = False
    mutations.append(extra)
    actor_drift = copy.deepcopy(record)
    actor_drift["publisher"]["actor"]["role"] = "AB16_FORMAL_SUPERVISOR"
    mutations.append(actor_drift)
    renderer_drift = copy.deepcopy(record)
    renderer_drift["publisher"]["renderer_source"]["sha256"] = "f" * 64
    mutations.append(renderer_drift)
    for changed in mutations:
        with pytest.raises(BOOTSTRAP.BootstrapError):
            BOOTSTRAP._validate_gate_b(changed)  # noqa: SLF001


def test_gate_b_epoch_v4_joins_one_live_owner_and_rejects_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    epoch = _manager_epoch(tmp_path)
    campaign = tmp_path / "campaigns/run-gate-b-epoch-v2"
    gate_a_identity = {
        key: value
        for key, value in _regular(tmp_path / "gate-b-epoch/gate-a.json", b"{}\n").items()
        if key in {"path", "sha256", "size_bytes"}
    }
    candidate_identity = {
        key: value
        for key, value in _regular(tmp_path / "gate-b-epoch/candidate.json", b"{}\n").items()
        if key in {"path", "sha256", "size_bytes"}
    }
    final_identity = _regular(tmp_path / "gate-b-epoch/final-full.json", b"{}\n")
    pre_full_resource_identity = _regular(
        tmp_path / "gate-b-epoch/resource-before-full.json",
        b"{}\n",
    )
    gate_a = {
        "manager_epoch": epoch,
        "planned_source_set_digest": "a" * 64,
        "repository_head": HEAD,
        "repository_root": str(tmp_path / "repository"),
        "run_nonce": campaign.name,
        "target_campaign_dir": str(campaign),
    }
    epoch_path = tmp_path / "gate-b-epoch/observation.json"
    record: dict[str, object] = {
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        },
        "candidate_identity": candidate_identity,
        "capture_transcript": {"fixture": "validated-by-focused-stub"},
        "created_at_utc": "2026-07-27T00:00:00Z",
        "final_full_preflight_receipt_identity": final_identity,
        "gate_a_receipt_identity": gate_a_identity,
        "manager_epoch": epoch,
        "planned_source_set_digest": gate_a["planned_source_set_digest"],
        "pre_full_resource_gate_identity": pre_full_resource_identity,
        "publisher": _gate_b_publisher(epoch_path, sequence=1),
        "purpose": BOOTSTRAP.GATE_B_EPOCH_PURPOSE,
        "repository_head": gate_a["repository_head"],
        "repository_root": gate_a["repository_root"],
        "run_nonce": gate_a["run_nonce"],
        "schema_version": BOOTSTRAP.GATE_B_EPOCH_SCHEMA,
        "status": "PASS",
        "target_campaign_dir": gate_a["target_campaign_dir"],
    }
    monkeypatch.setattr(
        BOOTSTRAP.authority,
        "validate_manager_epoch_capture_transcript",
        lambda value, *, expected_epoch: (
            value,
            expected_epoch,
        ),
    )
    assert (
        BOOTSTRAP._validate_gate_b_epoch_observation(  # noqa: SLF001
            record,
            gate_a=gate_a,
            gate_a_identity=gate_a_identity,
            candidate_identity=candidate_identity,
            final_full_preflight_identity=final_identity,
            pre_full_resource_gate_identity=pre_full_resource_identity,
        )
        == record
    )
    approval = _gate_b_record(tmp_path / "same-owner")
    assert approval["publisher"]["actor"] == record["publisher"]["actor"]
    assert (
        approval["publisher"]["qualification_session"]["session_id"]
        == record["publisher"]["qualification_session"]["session_id"]
    )

    mutations: list[dict[str, object]] = []
    old_schema = copy.deepcopy(record)
    old_schema["schema_version"] = "noncert-cuts-ab16-gate-b-epoch-observation-v3"
    mutations.append(old_schema)
    missing = copy.deepcopy(record)
    missing.pop("publisher")
    mutations.append(missing)
    extra = copy.deepcopy(record)
    extra["unexpected"] = False
    mutations.append(extra)
    actor_drift = copy.deepcopy(record)
    actor_drift["publisher"]["actor"]["pid_starttime"] = "1"
    mutations.append(actor_drift)
    upstream_drift = copy.deepcopy(record)
    upstream_drift["candidate_identity"]["sha256"] = "f" * 64
    mutations.append(upstream_drift)
    for changed in mutations:
        with pytest.raises(BOOTSTRAP.BootstrapError):
            BOOTSTRAP._validate_gate_b_epoch_observation(  # noqa: SLF001
                changed,
                gate_a=gate_a,
                gate_a_identity=gate_a_identity,
                candidate_identity=candidate_identity,
                final_full_preflight_identity=final_identity,
                pre_full_resource_gate_identity=pre_full_resource_identity,
            )


def _repository_manifest(tmp_path: Path) -> dict[str, object]:
    tracked = b"from __future__ import annotations\n"
    candidate = b'{"placements":[]}\n'
    members: list[dict[str, object]] = [
        {
            "git_blob_oid": "1" * 40, "git_mode": "100644", "materialized_mode": 0o444,
            "path": "pkg/module.py", "raw_sha256": hashlib.sha256(tracked).hexdigest(),
            "size_bytes": len(tracked), "source_kind": "git_blob",
        },
        {
            "materialized_mode": 0o444, "package_role": "input.candidate_placements.json",
            "path": "data/preprocessed/candidate_placements.json",
            "raw_sha256": hashlib.sha256(candidate).hexdigest(), "size_bytes": len(candidate),
            "source_kind": "package_overlay",
        },
    ]
    return {
        "archive_descriptor": {
            "package_role": "input.ab16_repository_snapshot.zip",
            "sha256": "2" * 64,
            "size_bytes": 10,
        },
        "authority_scope": "AB16_RESEARCH_ONLY", "import_mode": "ordinary_pathfinder",
        "member_count": len(members), "members": members,
        "ordered_member_digest": hashlib.sha256(AUTHORITY.canonical_json(members)).hexdigest(),
        "repository_head": HEAD, "repository_tree": "3" * 40,
        "schema_version": AUTHORITY.REPOSITORY_SNAPSHOT_SCHEMA,
        "total_bytes": sum(member["size_bytes"] for member in members),
    }


def _zip_bytes(path: str, raw: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(path, raw)
    return output.getvalue()


def test_repository_snapshot_manifest_exact_member_and_overlay_contract(
    tmp_path: Path,
) -> None:
    record = _repository_manifest(tmp_path)
    assert AUTHORITY.validate_repository_snapshot_manifest(record) == record

    missing = copy.deepcopy(record)
    missing.pop("member_count")
    extra = copy.deepcopy(record)
    extra["unexpected"] = True
    no_overlay = copy.deepcopy(record)
    no_overlay["members"].pop()
    no_overlay.update(member_count=1, total_bytes=no_overlay["members"][0]["size_bytes"])
    no_overlay["ordered_member_digest"] = hashlib.sha256(AUTHORITY.canonical_json(no_overlay["members"])).hexdigest()
    mutations = [missing, extra, no_overlay]
    for field, replacement in (
        ("path", "data/preprocessed/other.json"),
        ("materialized_mode", 0o400),
    ):
        changed = copy.deepcopy(record)
        changed["members"][-1][field] = replacement
        changed["ordered_member_digest"] = hashlib.sha256(AUTHORITY.canonical_json(changed["members"])).hexdigest()
        mutations.append(changed)
    forbidden_overlay_source = copy.deepcopy(record)
    forbidden_overlay_source["members"][-1]["source_identity"] = {
        "mode": 0o444,
        "path": str(tmp_path / "candidate-source.json"),
        "sha256": "e" * 64,
        "size_bytes": 1,
    }
    forbidden_overlay_source["ordered_member_digest"] = hashlib.sha256(
        AUTHORITY.canonical_json(forbidden_overlay_source["members"])
    ).hexdigest()
    mutations.append(forbidden_overlay_source)
    for changed in mutations:
        with pytest.raises(AUTHORITY.AuthorityError):
            AUTHORITY.validate_repository_snapshot_manifest(changed)


def test_bootstrap_materializer_rejects_manifest_without_candidate_overlay(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "run-bootstrap-materializer-v1"
    payload = campaign / "campaign-authority/package/payload"
    payload.mkdir(parents=True)
    raw = b"tracked\n"
    archive_path = payload / BOOTSTRAP.SNAPSHOT_ARCHIVE_PACKAGE_ROLE
    archive_path.write_bytes(_zip_bytes("tracked.txt", raw))
    archive_path.chmod(0o444)
    candidate_path = payload / "input.candidate_placements.json"
    candidate_path.write_bytes(b"{}\n")
    candidate_path.chmod(0o444)
    members = [
        {
            "git_blob_oid": "1" * 40, "git_mode": "100644", "materialized_mode": 0o444,
            "path": "tracked.txt",
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw), "source_kind": "git_blob",
        }
    ]
    manifest = {
        **_repository_manifest(tmp_path),
        "archive_descriptor": {
            "package_role": BOOTSTRAP.SNAPSHOT_ARCHIVE_PACKAGE_ROLE,
            "sha256": BOOTSTRAP.authority.snapshot_regular(archive_path).sha256,
            "size_bytes": BOOTSTRAP.authority.snapshot_regular(archive_path).size,
        },
        "member_count": 1, "members": members,
        "ordered_member_digest": hashlib.sha256(BOOTSTRAP.authority.canonical_json(members)).hexdigest(),
        "total_bytes": len(raw),
    }
    manifest_path = payload / BOOTSTRAP.SNAPSHOT_MANIFEST_PACKAGE_ROLE
    manifest_path.write_bytes(BOOTSTRAP.authority.canonical_json(manifest))
    manifest_path.chmod(0o444)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="candidate overlay"):
        BOOTSTRAP._materialize_repository_snapshot(  # noqa: SLF001
            campaign_dir=campaign,
            package_dir=payload.parent,
            package_id="4" * 64,
            created_at_utc="2026-07-27T00:00:00Z",
        )


def _materialized_snapshot_fixture(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object], Path]:
    campaign = tmp_path / "run-snapshot-replay-v1"
    payload = campaign / "campaign-authority/package/payload"
    repository = campaign / "campaign-authority/source-snapshot-a001/repository"
    payload.mkdir(parents=True)
    (repository / "pkg").mkdir(parents=True)
    (repository / "data/preprocessed").mkdir(parents=True)
    tracked = b"from __future__ import annotations\n"
    candidate = b'{"placements":[]}\n'
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("pkg/module.py", tracked)
    archive_path = payload / "input.ab16_repository_snapshot.zip"
    candidate_path = payload / "input.candidate_placements.json"
    python_path = Path(os.path.realpath(sys.executable))
    for path, raw, mode in (
        (archive_path, archive_buffer.getvalue(), 0o444),
        (candidate_path, candidate, 0o444),
        (repository / "pkg/module.py", tracked, 0o444),
        (repository / "data/preprocessed/candidate_placements.json", candidate, 0o444),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(mode)
    manifest = _repository_manifest(tmp_path)
    archive_snapshot = AUTHORITY.snapshot_regular(archive_path)
    manifest["archive_descriptor"] = {
        "package_role": "input.ab16_repository_snapshot.zip",
        "sha256": archive_snapshot.sha256,
        "size_bytes": archive_snapshot.size_bytes,
    }
    manifest["ordered_member_digest"] = hashlib.sha256(AUTHORITY.canonical_json(manifest["members"])).hexdigest()
    manifest_path = payload / "input.ab16_repository_snapshot.json"
    manifest_path.write_bytes(AUTHORITY.canonical_json(manifest))
    manifest_path.chmod(0o444)
    platform = BOOTSTRAP._external_platform_record(  # noqa: SLF001
        native_helper_identity=BOOTSTRAP.authority.snapshot_tool(NATIVE_HELPER)[1],
        repository_head=HEAD,
        python_identity=_full(python_path),
    )
    platform_path = payload / "input.ab16_external_platform_assumptions.json"
    platform_path.write_bytes(AUTHORITY.canonical_json(platform))
    platform_path.chmod(0o444)
    package_id = "4" * 64
    receipt = {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "candidate_identity": AUTHORITY.detached_identity(AUTHORITY.snapshot_regular(candidate_path)),
        "created_at_utc": "2026-07-27T00:00:00Z",
        "import_mode": "ordinary_pathfinder",
        "member_count": manifest["member_count"],
        "ordered_member_digest": manifest["ordered_member_digest"],
        "package_id": package_id,
        "repository_head": HEAD,
        "repository_tree": manifest["repository_tree"],
        "schema_version": AUTHORITY.SNAPSHOT_MATERIALIZATION_SCHEMA,
        "snapshot_archive_identity": AUTHORITY.detached_identity(
            AUTHORITY.snapshot_regular(archive_path)
        ),
        "snapshot_manifest_identity": AUTHORITY.detached_identity(AUTHORITY.snapshot_regular(manifest_path)),
        "snapshot_root": str(repository),
        "status": "PASS",
        "total_bytes": manifest["total_bytes"],
    }
    receipt_path = repository.parent / "materialization-receipt.json"
    receipt_path.write_bytes(AUTHORITY.canonical_json(receipt))
    receipt_path.chmod(0o444)
    for directory in sorted((path for path in repository.rglob("*") if path.is_dir()), reverse=True):
        directory.chmod(0o555)
    repository.chmod(0o555)
    bootstrap_source = TOOLS / "ab16_campaign_bootstrap_v2.py"
    bootstrap_payload = payload / "tool.ab16_campaign_bootstrap_v2.py"
    bootstrap_payload.write_bytes(bootstrap_source.read_bytes())
    bootstrap_payload.chmod(0o444)
    native_payload = payload / "system.native_budget_helper.bin"
    native_payload.write_bytes(NATIVE_HELPER.read_bytes())
    native_payload.chmod(0o444)
    files = {
        path.name: AUTHORITY.snapshot_regular(path)
        for path in (
            archive_path,
            bootstrap_payload,
            candidate_path,
            manifest_path,
            native_payload,
            platform_path,
        )
    }
    sources = {
        "input.ab16_repository_snapshot.zip": {"package_path": archive_path.name},
        "input.ab16_repository_snapshot.json": {"package_path": manifest_path.name},
        "input.ab16_external_platform_assumptions.json": {"package_path": platform_path.name},
        "input.candidate_placements.json": {"package_path": candidate_path.name},
        "tool.ab16_campaign_bootstrap_v2.py": {
            "package_path": bootstrap_payload.name,
            "source_identity": _full(bootstrap_source),
        },
        "system.native_budget_helper.bin": {
            "package_path": native_payload.name,
            "source_identity": BOOTSTRAP.authority.snapshot_tool(
                NATIVE_HELPER
            )[1],
        },
    }
    root = {
        "authority_tools": {
            "native_budget_helper": AUTHORITY.detached_identity(
                AUTHORITY.snapshot_regular(NATIVE_HELPER)
            ),
            "python3_13": AUTHORITY.detached_identity(
                AUTHORITY.snapshot_regular(python_path)
            ),
        },
        "package": {"package_id": package_id},
        "repository_head": HEAD,
        "strict_inputs": {
            "ab16_external_platform_assumptions": AUTHORITY.detached_identity(files[platform_path.name]),
            "ab16_repository_snapshot": AUTHORITY.detached_identity(files[manifest_path.name]),
            "ab16_repository_snapshot_archive": AUTHORITY.detached_identity(files[archive_path.name]),
            "ab16_repository_snapshot_materialization": AUTHORITY.detached_identity(
                AUTHORITY.snapshot_regular(receipt_path)
            ),
        },
    }
    return {"directory": campaign, "root": root, "files": files, "sources": sources}, manifest, repository


@pytest.mark.parametrize(
    "mutation",
    [
        "legacy-schema",
        "legacy-two-fd",
        "selected-literal",
        "owner-driver",
        "dual-holder",
        "extra",
    ],
)
def test_external_platform_v2_rejects_legacy_and_identity_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    kwargs, _manifest, repository = _materialized_snapshot_fixture(tmp_path)
    platform_role = "ab16_external_platform_assumptions"
    platform_path = Path(kwargs["root"]["strict_inputs"][platform_role]["path"])
    try:
        replay = AUTHORITY._replay_repository_snapshot(**kwargs)  # noqa: SLF001
        platform = copy.deepcopy(replay["external_platform"])
        if mutation == "legacy-schema":
            platform["schema_version"] = "noncert-cuts-ab16-external-platform-assumptions-v1"
        elif mutation == "legacy-two-fd":
            platform["selected_byte_launch"]["direct_fd_map"] = {
                "loader": 4,
                "python": 3,
            }
            platform["selected_byte_launch"]["systemd_fd_map"] = {
                "loader": 4,
                "python": 3,
            }
            platform["selected_byte_launch"]["systemd_fd_names"] = [
                "ab16-python",
                "ab16-loader",
            ]
        elif mutation == "selected-literal":
            platform["selected_byte_launch"]["literal_identity"]["sha256"] = "f" * 64
        elif mutation == "owner-driver":
            platform["formal_launch_owner_driver"]["sha256"] = "f" * 64
        elif mutation == "dual-holder":
            platform["dual_holder_survival"]["single_holder_death_must_be_contained"] = False
        else:
            platform["unexpected"] = False
        platform_path.chmod(0o644)
        platform_path.write_bytes(AUTHORITY.canonical_json(platform))
        platform_path.chmod(0o444)
        snapshot = AUTHORITY.snapshot_regular(platform_path)
        kwargs["files"][platform_path.name] = snapshot
        kwargs["root"]["strict_inputs"][platform_role] = AUTHORITY.detached_identity(
            snapshot
        )
        with pytest.raises(AUTHORITY.AuthorityError):
            AUTHORITY._replay_repository_snapshot(**kwargs)  # noqa: SLF001
    finally:
        for current, dirnames, _filenames in os.walk(repository):
            Path(current).chmod(0o755)
            for dirname in dirnames:
                (Path(current) / dirname).chmod(0o755)


@pytest.mark.parametrize(
    "mutation",
    ["extra", "missing", "path", "mode", "hash", "symlink", "hardlink", "identity"],
)
def test_materialized_repository_snapshot_replay_is_fail_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    kwargs, _manifest, repository = _materialized_snapshot_fixture(tmp_path)
    target = repository / "pkg/module.py"
    if mutation in {"extra", "symlink", "hardlink"}:
        repository.chmod(0o755)
        path = repository / ("extra.py" if mutation == "extra" else f"{mutation}.py")
        if mutation == "extra":
            path.write_bytes(b"extra\n")
        elif mutation == "symlink":
            path.symlink_to(target)
        else:
            path.hardlink_to(target)
        repository.chmod(0o555)
    elif mutation in {"missing", "path"}:
        target.parent.chmod(0o755)
        target.unlink() if mutation == "missing" else target.rename(target.with_name("renamed.py"))
        target.parent.chmod(0o555)
    elif mutation == "mode":
        target.chmod(0o400)
    elif mutation == "hash":
        target.chmod(0o644)
        target.write_bytes(b"drift\n")
        target.chmod(0o444)
    else:
        kwargs["root"]["strict_inputs"]["ab16_repository_snapshot"]["sha256"] = "f" * 64
    try:
        with pytest.raises(AUTHORITY.AuthorityError):
            AUTHORITY._replay_repository_snapshot(**kwargs)  # noqa: SLF001
    finally:
        for current, dirnames, _filenames in os.walk(repository):
            Path(current).chmod(0o755)
            for dirname in dirnames:
                (Path(current) / dirname).chmod(0o755)


def _history_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, object]]:
    repository = tmp_path / "history-repository"
    repository.mkdir()
    git_path = Path("/usr/bin/git")

    def git(*arguments: str) -> str:
        return subprocess.run(
            [str(git_path), "-C", str(repository), *arguments],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    git("init", "--quiet")
    git("config", "user.email", "ab16-history-fixture@example.invalid")
    git("config", "user.name", "AB16 history fixture")
    git("-c", "commit.gpgSign=false", "commit", "--quiet", "--allow-empty", "-m", "history head")
    history_head = git("rev-parse", "--verify", "HEAD^{commit}")
    source_relative = (
        "docs/research/noncert_cuts_ab16_20260724/"
        "history_role_fixture_v1.py"
    )
    source_path = repository / source_relative
    archived_source = b"ARCHIVED_FIXTURE = True\n"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(archived_source)
    git("add", "--", source_relative)
    git("-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "archive source")
    source_commit = git("rev-parse", "--verify", "HEAD^{commit}")
    source_tree = git("rev-parse", "--verify", "HEAD^{tree}")
    source_blob = git("rev-parse", "--verify", f"HEAD:{source_relative}")
    source_path.write_bytes(b"LIVE_FIXTURE = True\n")
    git("add", "--", source_relative)
    git("-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "advance live source")
    current_head = git("rev-parse", "--verify", "HEAD^{commit}")

    frozen_root = ".artifacts/noncert_cuts_ab16_fixture/history-frozen"
    artifact_relative = f"{frozen_root}/member.txt"
    artifact_identity = _regular(
        repository / artifact_relative,
        b"immutable history\n",
    )
    sealed_snapshot_root = tmp_path / "sealed-history-snapshot"
    sealed_snapshot_root.mkdir()
    snapshot_manifest_full = _regular(
        tmp_path / "history-snapshot-manifest-identity.json",
        RESOURCE.canonical_json_bytes(
            {"schema_version": "fixture-history-snapshot-manifest-v1"}
        ),
    )
    snapshot_receipt_full = _regular(
        tmp_path / "history-snapshot-materialization-identity.json",
        RESOURCE.canonical_json_bytes(
            {"schema_version": "fixture-history-snapshot-materialization-v1"}
        ),
    )
    snapshot_manifest_identity = {
        key: snapshot_manifest_full[key]
        for key in ("path", "sha256", "size_bytes")
    }
    snapshot_receipt_identity = {
        key: snapshot_receipt_full[key]
        for key in ("path", "sha256", "size_bytes")
    }
    manifest = {
        "created_at_utc": "2026-07-24T00:00:00Z",
        "file_count": 2,
        "files": sorted(
            [
            {
                    **artifact_identity,
                    "path": artifact_relative,
                },
                {
                    "mode": 0o644,
                    "path": source_relative,
                    "sha256": hashlib.sha256(archived_source).hexdigest(),
                    "size_bytes": len(archived_source),
                },
            ],
            key=lambda item: str(item["path"]).encode("utf-8"),
        ),
        "frozen_roots": [frozen_root],
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_FREEZE",
        "repository_head": history_head,
        "repository_root": str(repository),
        "schema_version": ("noncert-cuts-ab16-terminal-reference-history-freeze-v1"),
        "v1_source_glob": "docs/research/noncert_cuts_ab16_20260724/*_v1.py",
    }
    manifest_path = repository / ".artifacts/history-freeze/manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(
        RESOURCE.canonical_json_bytes(manifest) + b"\n"
    )
    manifest_path.chmod(0o400)
    _raw, manifest_identity = RESOURCE.snapshot_bytes(manifest_path)
    source_records = [
        {
            "git_blob_oid": source_blob,
            "git_mode": "100644",
            "mode": 0o644,
            "path": source_relative,
            "sha256": hashlib.sha256(archived_source).hexdigest(),
            "size_bytes": len(archived_source),
        }
    ]
    source_member_digest = hashlib.sha256(
        RESOURCE.canonical_json_bytes(source_records) + b"\n"
    ).hexdigest()
    contract = {
        "HISTORY_FREEZE_HEAD": history_head,
        "HISTORY_FREEZE_MANIFEST_MODE": manifest_identity["mode"],
        "HISTORY_FREEZE_MANIFEST_PATH": manifest_identity["path"],
        "HISTORY_FREEZE_MANIFEST_SHA256": manifest_identity["sha256"],
        "HISTORY_FREEZE_MANIFEST_SIZE": manifest_identity["size_bytes"],
        "HISTORY_SOURCE_COMMIT": source_commit,
        "HISTORY_SOURCE_TREE": source_tree,
        "HISTORY_SOURCE_GLOB": manifest["v1_source_glob"],
        "HISTORY_ARTIFACT_COUNT": 1,
        "HISTORY_SOURCE_COUNT": 1,
        "HISTORY_REPOSITORY_ROOT": repository,
        "HISTORY_FROZEN_ROOTS": (frozen_root,),
    }
    for name, value in contract.items():
        monkeypatch.setattr(RESOURCE, name, value)
    receipt = {
        "artifact_file_count": 1,
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
        },
        "file_count": 2,
        "manifest_identity": manifest_identity,
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY",
        "schema_version": ("noncert-cuts-ab16-terminal-reference-history-replay-v2"),
        "source_file_count": 1,
        "source_materialization": {
            "commit": source_commit,
            "file_count": 1,
            "manifest_head_parent": history_head,
            "member_digest": source_member_digest,
            "tree": source_tree,
        },
        "status": "PASS",
        "verdict": "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS",
    }
    receipt_path = tmp_path / "history-receipt.json"
    receipt_path.write_bytes(RESOURCE.canonical_json_bytes(receipt))
    receipt_path.chmod(0o444)
    _raw, receipt_identity = RESOURCE.snapshot_bytes(receipt_path)
    _raw, git_identity = RESOURCE.snapshot_bytes(git_path)
    pre_run = {
        "history_freeze_replay_identity": receipt_identity,
        "repository_git_tool_identity": git_identity,
        "repository_head": current_head,
        "repository_root": str(repository),
        "live_source_provenance_root": str(repository),
        "sealed_snapshot_execution_root": str(sealed_snapshot_root),
        "snapshot_manifest_identity": snapshot_manifest_identity,
        "snapshot_materialization_receipt_identity": snapshot_receipt_identity,
    }
    return pre_run, manifest_identity


@pytest.mark.parametrize(
    ("execution_class", "manifest_role"),
    [
        ("DISPOSABLE_LIVE_DRILL", "input.history_freeze_manifest"),
        ("FORMAL_AB16", "history_freeze_manifest"),
    ],
)
def test_history_freeze_role_is_execution_class_specific_and_source_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    execution_class: str,
    manifest_role: str,
) -> None:
    pre_run, manifest_identity = _history_authority(tmp_path, monkeypatch)
    pre_run["execution_class"] = execution_class
    RESOURCE._replay_history_freeze(  # noqa: SLF001
        pre_run=pre_run,
        strict_inputs={manifest_role: manifest_identity},
    )

    wrong_role = "history_freeze_manifest" if manifest_role.startswith("input.") else "input.history_freeze_manifest"
    with pytest.raises(
        RESOURCE.VerificationError,
        match="history freeze strict input identity",
    ):
        RESOURCE._replay_history_freeze(  # noqa: SLF001
            pre_run=pre_run,
            strict_inputs={wrong_role: manifest_identity},
        )

    source = Path(str(manifest_identity["path"]))
    copied = tmp_path / "copied-history-manifest.json"
    copied.write_bytes(source.read_bytes())
    copied.chmod(0o444)
    _raw, copied_identity = RESOURCE.snapshot_bytes(copied)
    with pytest.raises(
        RESOURCE.VerificationError,
        match="receipt semantics drifted",
    ):
        RESOURCE._replay_history_freeze(  # noqa: SLF001
            pre_run=pre_run,
            strict_inputs={manifest_role: copied_identity},
        )


def _snapshot_identity(tmp_path: Path, name: str) -> dict[str, object]:
    path = tmp_path / "resource-identities" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(RESOURCE.canonical_json_bytes({"name": name}))
    path.chmod(0o444)
    _raw, identity = RESOURCE.snapshot_bytes(path)
    return identity


def _terminal_inputs(tmp_path: Path) -> dict[str, object]:
    values = TERMINAL_V1_FIXTURE._arm_inputs()  # noqa: SLF001
    preterminal_identity = _snapshot_identity(tmp_path, "preterminal-receipt")
    terminal_identity = _snapshot_identity(tmp_path, "terminal-receipt")
    verifier_identity = _snapshot_identity(tmp_path, "resource-verifier")
    reference_acquisition = _snapshot_identity(
        tmp_path,
        "reference-acquisition",
    )
    reference_release = _snapshot_identity(tmp_path, "reference-release")
    values["resource_preterminal_identity"] = dict(preterminal_identity)
    values["resource_receipt_identity"] = dict(terminal_identity)
    values["resource_verifier_tool_identity"] = dict(verifier_identity)
    for receipt_name in (
        "resource_preterminal_receipt",
        "replayed_resource_preterminal_receipt",
    ):
        receipt = values[receipt_name]
        assert isinstance(receipt, dict)
        receipt["schema_version"] = TERMINAL.RESOURCE_PRETERMINAL_SCHEMA
        receipt["verifier_tool_identity"] = dict(verifier_identity)
    for receipt_name in (
        "resource_receipt",
        "replayed_resource_receipt",
    ):
        receipt = values[receipt_name]
        assert isinstance(receipt, dict)
        receipt["schema_version"] = TERMINAL.RESOURCE_SCHEMA
        receipt["resource_verification_identity"] = dict(preterminal_identity)
        receipt["reference_acquisition_identity"] = dict(reference_acquisition)
        receipt["reference_release_identity"] = dict(reference_release)
        receipt["verifier_tool_identity"] = dict(verifier_identity)
    return values


def test_terminal_gate_accepts_mode_bearing_snapshot_and_rejects_drift(
    tmp_path: Path,
) -> None:
    values = _terminal_inputs(tmp_path)
    result = TERMINAL.build_arm_gate(**values)
    assert result["status"] == "PASS"
    assert result["resource_preterminal_identity"]["mode"] == 0o444
    assert result["resource_receipt_identity"]["mode"] == 0o444

    for field, replacement in (("mode", 0o400), ("sha256", "f" * 64)):
        drifted = copy.deepcopy(values)
        outer = dict(drifted["resource_preterminal_identity"])
        outer[field] = replacement
        drifted["resource_preterminal_identity"] = outer
        with pytest.raises(
            TERMINAL.GateError,
            match="identity chain failed",
        ):
            TERMINAL.build_arm_gate(**drifted)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function not found: {name}")


def _assigned_literal(
    function: ast.FunctionDef,
    name: str,
) -> object:
    for node in ast.walk(function):
        target: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"assignment not found: {name}")


def test_formal_pre_run_v2_shape_preregisters_and_replays_references() -> None:
    source = (TOOLS / "ab16_authority_v2.py").read_text()
    tree = ast.parse(source)
    expected_tools = _function(tree, "_expected_pre_run_tools")
    tool_roles = _assigned_literal(expected_tools, "tool_roles")
    assert isinstance(tool_roles, dict)
    assert tool_roles["attestor_python"] == "attestor_python"
    assert tool_roles["python3_13"] == "python3_13"
    assert tool_roles["attestor_python"] != tool_roles["python3_13"]
    assert set(tool_roles) | {"manager_epoch_authority"} == set(
        RESOURCE_LIFECYCLE.FORMAL_TOOL_ROLES_V2
    )
    assert set(tool_roles) | {"manager_epoch_authority"} == (
        RESOURCE.FORMAL_TOOL_ROLES_V2
    )

    builder = _function(tree, "_build_pre_run_candidate_unprotected")
    output_names = _assigned_literal(builder, "output_names")
    assert isinstance(output_names, dict)
    assert {
        "abort_reference_release",
        "reference_acquisition",
        "reference_release",
    }.issubset(output_names)
    phases = _assigned_literal(builder, "phases")
    assert phases == (
        "launch",
        "preterminal",
        "reference-acquire",
        "release",
        "terminal-first",
        "terminal-stable",
        "reference-release",
        "cleanup",
        "detached-replay",
    )

    record_keys: set[str] | None = None
    for node in ast.walk(builder):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "record"
            and isinstance(node.value, ast.Dict)
        ):
            record_keys = {
                key.value for key in node.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            break
    assert record_keys is not None
    assert {
        "history_freeze_replay_identity",
        "reference_capability_identity",
        "reference_capability_transcript_identity",
        "reference_contract",
    }.issubset(record_keys)

    replay = _function(tree, "_replay_selected_arm_evidence")
    detached_calls = [
        node
        for node in ast.walk(replay)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "verify_detached"
    ]
    assert len(detached_calls) == 1
    keywords = {keyword.arg for keyword in detached_calls[0].keywords}
    assert {"reference_acquisition", "reference_release"}.issubset(keywords)
