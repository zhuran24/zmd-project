from __future__ import annotations

import importlib.util
import inspect
import json
import hashlib
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"


def _load(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load("campaign_authority_v4", "campaign_authority_v4.py")
EXECUTION = _load(
    "cuts_gate1_v4_campaign_execution",
    "gate1_campaign_execution_v4.py",
)


def _identity(path: Path) -> dict[str, object]:
    return AUTH.detached_identity(AUTH.snapshot_regular(path))


def _fixture(tmp_path: Path, name: str) -> dict[str, Any]:
    campaign = tmp_path / name
    gate_dir = campaign / "gate1-v4"
    gate_dir.mkdir(parents=True)
    root_path = campaign / "campaign-root.json"
    selection_path = gate_dir / "selection-a001.json"
    root_path.write_bytes(b'{"root":"fixture"}')
    selection_path.write_bytes(b'{"selection":"fixture"}')
    positive = gate_dir / "positive-control-common"
    units: dict[str, object] = {}
    for slot in EXECUTION.UNIT_ORDER:
        attempt = gate_dir / "units" / slot
        units[slot] = {
            "attempt_dir": str(attempt),
            "raw_dir": str(attempt / "raw"),
            "terminal_dir": str(attempt / "terminal"),
            "epoch_checkpoint_paths": {
                phase: str(attempt / "authority" / f"manager-epoch-{phase}.json")
                for phase in EXECUTION.CHECKPOINT_PHASES
            },
        }
    root = {
        "campaign_id": "a" * 64,
        "run_nonce": "fixture",
        "repository_head": "3" * 40,
        "manager_epoch": {"epoch": "fixture"},
        "stage_topology": {
            "gate1_v4": {
                "gate_path": str(gate_dir / "gate-a001.json"),
                "continuation_path": str(gate_dir / "continuation-authorization-a001.json"),
                "gate_admission_epoch_path": str(gate_dir / "authority/manager-epoch-gate-admission.json"),
                "gate_admission_epoch_schema": ("noncert-cuts-gate1-v4-manager-epoch-checkpoint-v2"),
                "positive_control": {
                    "root_dir": str(positive),
                    "selection_path": str(positive / "selection.json"),
                    "common_manifest_path": str(positive / "common-prestate/manifest.json"),
                    "binding_seal_path": str(positive / "bindings/bindings-seal.json"),
                    "binding_paths": {
                        arm: str(positive / "bindings" / f"{arm}.json") for arm in ("control", "treatment")
                    },
                    "arm_dirs": {arm: str(positive / "arms" / arm) for arm in ("control", "treatment")},
                    "builder_export_dirs": {
                        arm: str(positive / "builder-exports" / arm) for arm in ("common", "control", "treatment")
                    },
                    "arithmetic_receipt_path": str(positive / "independent-arithmetic-receipt.json"),
                },
                "units": units,
            }
        },
    }
    selection = {"tools": {}, "inputs": {}}
    return {
        "campaign": campaign,
        "root": root,
        "selection": selection,
        "root_identity": _identity(root_path),
        "selection_identity": _identity(selection_path),
    }


def test_mode_boundary_and_public_formal_surface_are_exact(
    tmp_path: Path,
) -> None:
    EXECUTION._validate_mode(  # noqa: SLF001
        tmp_path / "dev-drill-a001",
        mode=EXECUTION.DISPOSABLE,
        formal_authorized=False,
    )
    EXECUTION._validate_mode(  # noqa: SLF001
        tmp_path / "run-a001",
        mode=EXECUTION.FORMAL,
        formal_authorized=True,
    )
    for path, mode, authorized in (
        (tmp_path / "run-a001", EXECUTION.DISPOSABLE, False),
        (tmp_path / "dev-drill-a001", EXECUTION.FORMAL, True),
        (tmp_path / "run-a001", EXECUTION.FORMAL, False),
        (tmp_path / "dev-drill-a001", EXECUTION.DISPOSABLE, True),
    ):
        with pytest.raises(EXECUTION.ExecutionError):
            EXECUTION._validate_mode(  # noqa: SLF001
                path,
                mode=mode,
                formal_authorized=authorized,
            )
    for function in (
        EXECUTION.prepare_formal_positive_pair,
        EXECUTION.orchestrate_gate1_units,
        EXECUTION.assemble_and_publish_formal_gate,
    ):
        parameters = set(inspect.signature(function).parameters)
        assert (
            not {
                "prepare_common",
                "orchestrate",
                "runtime_factory",
                "evaluate_gate",
                "solve_seconds",
            }
            & parameters
        )


def test_terminal_failure_archive_surface_is_passive_fixed_and_nonauthorizing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, "run-terminal-failure")
    failure_path = tmp_path / "assemble-formal.log"
    failure_path.write_text("GateError: terminal assembly failed\n", encoding="utf-8")
    failure_identity = _identity(failure_path)
    marker_path = fixture["campaign"] / "gate1-v4/authority/terminal-assembly-failure-a001.json"
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text("{}\n", encoding="utf-8")
    marker_identity = _identity(marker_path)
    observed: dict[str, object] = {}

    def archive(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return marker_identity

    monkeypatch.setattr(
        EXECUTION,
        "_load_authorities",
        lambda *_: (_ for _ in ()).throw(AssertionError("selected execution must stay unreachable")),
    )
    monkeypatch.setattr(AUTH, "archive_terminal_assembly_failure", archive)
    monkeypatch.setattr(
        AUTH,
        "replay_terminal_assembly_failure_archive",
        lambda **_: {"status": AUTH.TERMINAL_ASSEMBLY_FAILURE_STATUS},
    )
    result = EXECUTION.archive_terminal_assembly_failure(
        campaign_root_identity=fixture["root_identity"],
        selection_identity=fixture["selection_identity"],
        failure_evidence_identity=failure_identity,
    )
    assert observed["campaign_root_identity"] == fixture["root_identity"]
    assert observed["gate1_selection_identity"] == fixture["selection_identity"]
    assert observed["failure_evidence_identity"] == failure_identity
    assert set(observed["archive_tool_identities"]) == {
        "campaign_authority_v4",
        "gate1_campaign_execution_v4",
    }
    assert result == {
        "ab16_slot_attempt": False,
        "archive_identity": marker_identity,
        "continuation_authorized": False,
        "failed_package_reuse_authorized": False,
        "global_claim_authorized": False,
        "mode": "archive-only",
        "new_campaign_root_required": True,
        "organic_arm_launch_authorized": False,
        "resume_authorized": False,
        "status": AUTH.TERMINAL_ASSEMBLY_FAILURE_STATUS,
    }
    assert set(inspect.signature(EXECUTION.archive_terminal_assembly_failure).parameters) == {
        "campaign_root_identity",
        "selection_identity",
        "failure_evidence_identity",
    }
    arguments = EXECUTION._parser().parse_args(  # noqa: SLF001
        [
            "archive-terminal-failure",
            "--campaign-root",
            str(fixture["root_identity"]["path"]),
            "--campaign-root-size",
            str(fixture["root_identity"]["size_bytes"]),
            "--campaign-root-sha256",
            str(fixture["root_identity"]["sha256"]),
            "--selection",
            str(fixture["selection_identity"]["path"]),
            "--selection-size",
            str(fixture["selection_identity"]["size_bytes"]),
            "--selection-sha256",
            str(fixture["selection_identity"]["sha256"]),
            "--failure-evidence",
            str(failure_identity["path"]),
            "--failure-evidence-size",
            str(failure_identity["size_bytes"]),
            "--failure-evidence-sha256",
            str(failure_identity["sha256"]),
        ]
    )
    assert arguments.command == "archive-terminal-failure"
    assert not hasattr(arguments, "formal_authorized")
    assert not hasattr(arguments, "output")


def test_units_are_orchestrated_in_fixed_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, "dev-drill-order")
    monkeypatch.setattr(
        EXECUTION,
        "_load_authorities",
        lambda *_: (
            fixture["root"],
            fixture["selection"],
            b"root",
            b"selection",
        ),
    )
    events: list[str] = []

    def orchestrate(**kwargs: object) -> dict[str, object]:
        events.append(str(kwargs["unit_slot"]))
        return {"slot": kwargs["unit_slot"]}

    result = EXECUTION._orchestrate_units_with(  # noqa: SLF001
        campaign_root_identity=fixture["root_identity"],
        selection_identity=fixture["selection_identity"],
        runtime_factory=lambda slot: f"runtime:{slot}",
        orchestrate=orchestrate,
    )
    assert events == list(EXECUTION.UNIT_ORDER)
    assert list(result) == list(EXECUTION.UNIT_ORDER)


@pytest.mark.parametrize(
    ("name", "mode", "schema", "purpose", "eligible", "entrypoint"),
    (
        (
            "dev-drill-prepare",
            EXECUTION.DISPOSABLE,
            EXECUTION.DRILL_SELECTION_SCHEMA,
            EXECUTION.DRILL_PURPOSE,
            False,
            "prepare_disposable_positive_common",
        ),
        (
            "run-prepare",
            EXECUTION.FORMAL,
            EXECUTION.FORMAL_SELECTION_SCHEMA,
            EXECUTION.FORMAL_PURPOSE,
            True,
            "prepare_formal_positive_common",
        ),
    ),
)
def test_prepare_uses_profile_specific_purpose_before_arms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    mode: str,
    schema: str,
    purpose: str,
    eligible: bool,
    entrypoint: str,
) -> None:
    fixture = _fixture(tmp_path, name)
    monkeypatch.setattr(
        EXECUTION,
        "_load_authorities",
        lambda *_: (
            fixture["root"],
            fixture["selection"],
            b"root",
            b"selection",
        ),
    )
    positive = fixture["root"]["stage_topology"]["gate1_v4"]["positive_control"]

    def prepare(root: Path, **kwargs: object) -> dict[str, object]:
        pair = json.loads((root / "selection.json").read_bytes())
        assert pair == {
            "campaign_id": "a" * 64,
            "gate1_formal_eligible": eligible,
            "manager_epoch_digest": hashlib.sha256(AUTH.canonical_json(fixture["root"]["manager_epoch"])).hexdigest(),
            "purpose": purpose,
            "repository_head": "3" * 40,
            "run_nonce": "fixture",
            "schema": schema,
        }
        assert kwargs["solve_seconds"] == EXECUTION.FORMAL_SOLVE_SECONDS
        (root / "common-prestate").mkdir()
        (root / "bindings").mkdir()
        for path in (
            Path(positive["common_manifest_path"]),
            Path(positive["binding_seal_path"]),
            Path(positive["binding_paths"]["control"]),
            Path(positive["binding_paths"]["treatment"]),
        ):
            path.write_text("{}\n", encoding="utf-8")
        return {"post_attach_solve_performed": False}

    namespaces = {entrypoint: prepare}
    monkeypatch.setattr(
        EXECUTION,
        "_positive_namespaces",
        lambda _: ({}, namespaces),
    )
    if mode == EXECUTION.DISPOSABLE:
        result = EXECUTION.prepare_disposable_positive_pair(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
        )
    else:
        result = EXECUTION.prepare_formal_positive_pair(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            formal_authorized=True,
        )
    assert result["both_bindings_sealed_before_arms"] is True
    assert result["formal_publication_authorized"] is eligible
    with pytest.raises(EXECUTION.ExecutionError, match="already exists"):
        if mode == EXECUTION.DISPOSABLE:
            EXECUTION.prepare_disposable_positive_pair(
                campaign_root_identity=fixture["root_identity"],
                selection_identity=fixture["selection_identity"],
            )
        else:
            EXECUTION.prepare_formal_positive_pair(
                campaign_root_identity=fixture["root_identity"],
                selection_identity=fixture["selection_identity"],
                formal_authorized=True,
            )


def test_disposable_terminal_publishes_replay_bytes_not_formal_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, "dev-drill-terminal")
    monkeypatch.setattr(
        EXECUTION,
        "_load_authorities",
        lambda *_: (
            fixture["root"],
            fixture["selection"],
            b"root",
            b"selection",
        ),
    )
    monkeypatch.setattr(EXECUTION, "_collect_lifecycle", lambda _: ({}, {}, {}))
    monkeypatch.setattr(
        EXECUTION,
        "_collect_positive",
        lambda **_: (
            {"fixture": True},
            {
                "status": "PASS_DISPOSABLE_PRODUCTION_MECHANISM_POSITIVE_CONTROL",
                "receipt_identity": {
                    "path": str(tmp_path / "receipt.json"),
                    "size_bytes": 1,
                    "sha256": "0" * 64,
                },
                "common_prestate_id": "1" * 64,
            },
        ),
    )
    monkeypatch.setattr(
        EXECUTION,
        "_selected_execution_namespaces",
        lambda _: {},
    )
    gate_epoch_identity = {
        "path": str(fixture["campaign"] / "gate1-v4/authority/manager-epoch-gate-admission.json"),
        "size_bytes": 1,
        "sha256": "2" * 64,
    }
    monkeypatch.setattr(
        EXECUTION,
        "_capture_gate_admission_epoch",
        lambda **_: {
            "raw": b"{}",
            "identity": gate_epoch_identity,
            "value": {"manager_epoch": fixture["root"]["manager_epoch"]},
        },
    )
    monkeypatch.setattr(
        EXECUTION,
        "_evaluate_disposable_replay",
        lambda **_: {
            "schema_version": EXECUTION.OBSERVATION_RESULT_SCHEMA,
            "status": "DEV_DRILL_FULL_REPLAY_PASS_NO_AUTHORITY",
            "mechanism_credible_authorized": False,
        },
    )
    result = EXECUTION.assemble_disposable_observation(
        campaign_root_identity=fixture["root_identity"],
        selection_identity=fixture["selection_identity"],
    )
    gate_dir = fixture["campaign"] / "gate1-v4"
    assert result["gate_written"] is False
    assert not (gate_dir / "gate-a001.json").exists()
    assert not (gate_dir / "continuation-authorization-a001.json").exists()
    replay_path = gate_dir / "dev-drill-replay-result-a001.json"
    observation = json.loads((gate_dir / "dev-drill-observation-a001.json").read_bytes())
    assert observation["replay_result_identity"] == _identity(replay_path)
    assert observation["gate_admission_epoch_identity"] == gate_epoch_identity
    assert observation["continuation_authorized"] is False
    assert observation["global_claim_authorized"] is False
    with pytest.raises(Exception):
        EXECUTION.assemble_disposable_observation(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
        )


def test_disposable_common_prestate_join_uses_delegated_result() -> None:
    common_id = "1" * 64
    payloads = {
        slot: {
            "common_prestate_id": "2" * 64,
            "delegated_result": {"common_prestate_id": common_id},
        }
        for slot in ("forced-control", "forced-treatment")
    }
    EXECUTION._join_disposable_payload_common_prestate(  # noqa: SLF001
        payload_results=payloads,
        common_prestate_id=common_id,
    )
    payloads["forced-treatment"]["delegated_result"]["common_prestate_id"] = "3" * 64
    with pytest.raises(EXECUTION.ExecutionError, match="do not join"):
        EXECUTION._join_disposable_payload_common_prestate(  # noqa: SLF001
            payload_results=payloads,
            common_prestate_id=common_id,
        )


def test_terminal_docs_pin_authority_and_claim_boundary() -> None:
    readme = (RESEARCH / "README.md").read_text(encoding="utf-8")
    execution = (RESEARCH / "01_execution_record.md").read_text(encoding="utf-8")
    for required in (
        "CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS / MECHANISM_CREDIBLE",
        "run-20260723T231223Z-0067f7",
        "0b5d1c97f0d09cd3605e86d5861f300cbd2826bb393ae1d5461c4a0083a944ec",
        "eb9d569d88578827d46c8209ef5b69eab3c7762ae1edc1ba0ac90f2d8433132b",
        "organic_arm_launch_authorized=false",
        "This establishes mechanism reachability and exclusion power",
        "does not establish",
    ):
        assert required in readme
    for required in (
        "history-freeze-a001/manifest.json",
        "dev-drill-20260723T231057Z-36fd7f",
        "run-20260723T231223Z-0067f7",
        "assemble-formal",
        "No organic A/B arm",
    ):
        assert required in execution


def test_formal_publication_requires_explicit_authorization(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, "run-formal")
    with pytest.raises(EXECUTION.ExecutionError, match="lacks authorization"):
        EXECUTION.assemble_and_publish_formal_gate(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            formal_authorized=False,
        )
    with pytest.raises(EXECUTION.ExecutionError, match="lacks authorization"):
        EXECUTION.prepare_formal_positive_pair(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            formal_authorized=False,
        )
