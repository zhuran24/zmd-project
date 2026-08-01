from __future__ import annotations

import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Callable, Mapping, cast

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUTHORITY = _load(
    "noncert_cuts_ab16_authority_budget_join_v1",
    TOOLS / "ab16_authority_v2.py",
)
RUNNER = _load(
    "noncert_cuts_ab16_runner_budget_join_v1",
    TOOLS / "organic_arm_runner_v1.py",
)
LIFECYCLE = _load(
    "noncert_cuts_ab16_lifecycle_budget_join_v1",
    TOOLS / "organic_resource_lifecycle_v2.py",
)
VERIFIER = _load(
    "noncert_cuts_ab16_verifier_budget_join_v1",
    TOOLS / "organic_resource_verifier_v2.py",
)


def _identity(path: Path, marker: bytes) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(marker).hexdigest(),
        "size_bytes": len(marker),
    }


def _write_identity(path: Path, marker: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(marker)
    return _identity(path, marker)


def _runtime(formal_root: Path) -> dict[str, object]:
    return {
        "broker_actor_identity": {
            "pid": 101,
            "pid_starttime": 202,
            "uid": os.getuid(),
        },
        "broker_endpoint_identity": {
            "device": 1,
            "inode": 2,
            "mode": 0o600,
            "path": str(formal_root.parent / "control/budget-broker.sock"),
            "uid": os.getuid(),
        },
        "broker_nonce": "a" * 64,
        "formal_budget_handoff_identity": _identity(
            formal_root / "budget-handoff.json",
            b"handoff",
        ),
        "formal_root_contract_identity": _identity(
            formal_root / "formal-root-budget-contract.json",
            b"contract",
        ),
        "package_independent_replay_identity": _identity(
            formal_root.parent / "package-independent-replay.json",
            b"package-replay",
        ),
        "recovery_actor_identity": {
            "pid": 303,
            "pid_starttime": 404,
            "uid": os.getuid(),
        },
        "recovery_extent_identity": {
            "sha256": hashlib.sha256(b"recovery-extent").hexdigest(),
            "size_bytes": len(b"recovery-extent"),
        },
    }


class _Lifecycle:
    @staticmethod
    def validate_formal_budget_handoff(
        value: object,
        *,
        expected_attempt_root: Path,
        expected_arm_slot: str,
    ) -> Mapping[str, object]:
        assert isinstance(expected_attempt_root, Path)
        assert expected_arm_slot
        assert isinstance(value, dict)
        return value


def _handoff(
    formal_root: Path,
    attempt: Path,
    runtime: Mapping[str, object],
) -> dict[str, object]:
    broker_actor = cast(Mapping[str, object], runtime["broker_actor_identity"])
    broker_endpoint = cast(
        Mapping[str, object],
        runtime["broker_endpoint_identity"],
    )
    root_contract = cast(
        Mapping[str, object],
        runtime["formal_root_contract_identity"],
    )
    relative = attempt.relative_to(formal_root).as_posix()
    maxima = {
        label: {
            "artifact_class": artifact_class,
            "maximum_bytes": 1 << 20,
        }
        for label, artifact_class in (
            AUTHORITY.PROSPECTIVE_AUTHORITY_PUBLICATIONS.items()
        )
        if label not in {"organic campaign manifest", "organic suite selection"}
    }
    return {
        "arm_allocation_id": "b" * 64,
        "broker_actor_identity": dict(broker_actor),
        "broker_nonce": runtime["broker_nonce"],
        "broker_socket_path": broker_endpoint["path"],
        "fixed_directory_layout": {
            "attempt_root": str(attempt),
            "channel_directories": {
                "cut-ledger": f"{relative}/ledger/cut-ledger",
            },
            "directories": [
                {"mode": 0o700, "path": relative},
                {"mode": 0o700, "path": f"{relative}/ledger"},
                {
                    "mode": 0o700,
                    "path": f"{relative}/ledger/cut-ledger",
                },
                {"mode": 0o700, "path": f"{relative}/replays"},
            ],
            "formal_root": str(formal_root),
        },
        "fixed_maxima": maxima,
        "formal_budget_authority_identity": {
            "mode": 0o444,
            **dict(root_contract),
        },
        "native_helper_package_identity": {
            "mode": 0o555,
            **_identity(formal_root.parent / "native-helper.so", b"helper"),
        },
    }


class _Backend:
    def __init__(
        self,
        *,
        runtime: Mapping[str, object],
        handoff: Mapping[str, object],
    ) -> None:
        self._runtime = dict(runtime)
        self._handoff = handoff
        self.calls: list[tuple[str, str, int, str]] = []
        self.raise_after_write = False
        self.return_path_drift = False
        self.maximum_override: int | None = None
        self.post_seal_replay_identity: dict[str, object] | None = None

    @property
    def formal_budget_runtime(self) -> Mapping[str, object]:
        return self._runtime

    @property
    def authority_binding(self) -> Mapping[str, object]:
        return {
            "arm_allocation_id": self._handoff["arm_allocation_id"],
            "arm_allocation_identity": {
                "sha256": self._handoff["arm_allocation_id"],
                "size_bytes": 128,
            },
            "arm_slot": "region-capacity-ab-control",
            "broker_nonce": self._runtime["broker_nonce"],
            "broker_socket_fd": 71,
            "filesystem_write_confinement": (
                "not-applicable-persistent-supervisor-v1"
            ),
            "formal_budget_authority_identity": self._handoff[
                "formal_budget_authority_identity"
            ],
            "next_sequence": 1,
        }

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int:
        maxima = cast(
            Mapping[str, Mapping[str, object]],
            self._handoff["fixed_maxima"],
        )
        maximum = maxima[label]
        assert maximum["artifact_class"] == artifact_class
        if self.maximum_override is not None:
            return self.maximum_override
        maximum_bytes = maximum["maximum_bytes"]
        assert type(maximum_bytes) is int
        return maximum_bytes

    def publish_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
    ) -> Mapping[str, object]:
        self.calls.append((str(path), label, maximum_bytes, artifact_class))
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.write(descriptor, raw)
            os.fsync(descriptor)
            os.fchmod(descriptor, 0o444)
        finally:
            os.close(descriptor)
        if self.raise_after_write:
            raise RuntimeError("ACK lost")
        return {
            "path": str(path.parent / "wrong")
            if self.return_path_drift
            else str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }

    def publish_bytes_with_publication_boundary(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        publication_boundary: Callable[[], None],
    ) -> Mapping[str, object]:
        publication_boundary()
        return self.publish_bytes(
            path,
            raw,
            maximum_bytes=maximum_bytes,
            artifact_class=artifact_class,
            label=label,
        )

    def publish_arm_consumption(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        label: str,
        replay_identity: Mapping[str, object],
    ) -> Mapping[str, object]:
        self.post_seal_replay_identity = dict(replay_identity)
        return self.publish_bytes(
            path,
            raw,
            maximum_bytes=maximum_bytes,
            artifact_class="closeout",
            label=label,
        )


def test_exact_authority_cohort_versions_and_mixed_versions_fail_closed() -> None:
    assert (
        AUTHORITY._cohort_version(  # noqa: SLF001
            manifest=AUTHORITY.MANIFEST_SCHEMA,
            suite=AUTHORITY.SUITE_SELECTION_SCHEMA,
            pre_run=AUTHORITY.PRE_RUN_AUTHORITY_SCHEMA,
            arm_selection=AUTHORITY.ARM_SELECTION_SCHEMA,
            arm_consumption=AUTHORITY.ARM_CONSUMPTION_SCHEMA,
            immediate_stop=AUTHORITY.CAMPAIGN_STOP_SCHEMA,
        )
        == "prospective-v3"
    )
    assert (
        AUTHORITY._cohort_version(  # noqa: SLF001
            manifest=AUTHORITY.LEGACY_MANIFEST_SCHEMA,
            suite=AUTHORITY.LEGACY_SUITE_SELECTION_SCHEMA,
            pre_run=AUTHORITY.LEGACY_PRE_RUN_AUTHORITY_SCHEMA,
            arm_selection=AUTHORITY.LEGACY_ARM_SELECTION_SCHEMA,
            arm_consumption=AUTHORITY.LEGACY_ARM_CONSUMPTION_SCHEMA,
            immediate_stop=AUTHORITY.LEGACY_CAMPAIGN_STOP_SCHEMA,
        )
        == "legacy-v2"
    )
    assert RUNNER.PROSPECTIVE_FORMAL_MANIFEST_SCHEMA == AUTHORITY.MANIFEST_SCHEMA
    assert RUNNER.FORMAL_SELECTION_SCHEMA == AUTHORITY.ARM_SELECTION_SCHEMA
    assert (
        LIFECYCLE.FORMAL_PRE_RUN_AUTHORITY_SCHEMA
        == VERIFIER.FORMAL_PRE_RUN_SCHEMA
        == AUTHORITY.PRE_RUN_AUTHORITY_SCHEMA
    )
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._cohort_version(  # noqa: SLF001
            manifest=AUTHORITY.MANIFEST_SCHEMA,
            suite=AUTHORITY.LEGACY_SUITE_SELECTION_SCHEMA,
        )
    assert exc_info.value.code == "AB16_COHORT_MIXED"


def test_baseline_publication_classes_match_fixed_broker_contract() -> None:
    expected = {
        "AB16 baseline admission": "publication",
        "AB16 baseline fixed replay": "publication",
        "AB16 baseline incumbent": "normal",
        "AB16 baseline rebuild result": "publication",
        "AB16 baseline rebuilt metadata": "metadata",
        "AB16 baseline rebuilt model": "model",
        "AB16 baseline cut segment": "ledger",
    }
    assert {
        label: AUTHORITY.PROSPECTIVE_AUTHORITY_PUBLICATIONS[label]
        for label in expected
    } == expected
    assert (
        AUTHORITY.PROSPECTIVE_FORMAL_ROOT_PUBLICATIONS
        & expected.keys()
        == expected.keys()
    )


def test_formal_runtime_handoff_layout_maxima_and_backend_join(
    tmp_path: Path,
) -> None:
    formal_root = tmp_path / "formal/artifacts"
    attempt = formal_root / "prospective/arms/region-capacity-ab-control"
    runtime = _runtime(formal_root)
    handoff = _handoff(formal_root, attempt, runtime)
    checked = AUTHORITY._validate_budget_handoff_join(  # noqa: SLF001
        handoff,
        formal_budget_runtime=runtime,
        expected_attempt_root=attempt,
        expected_slot="region-capacity-ab-control",
        lifecycle=_Lifecycle,
    )
    assert checked["arm_allocation_id"] == "b" * 64
    backend = _Backend(runtime=runtime, handoff=handoff)
    AUTHORITY._validate_arm_budget_backend(  # noqa: SLF001
        backend,
        formal_budget_runtime=runtime,
        budget_handoff=checked,
        slot="region-capacity-ab-control",
    )

    for mutation, detail in (
        (
            lambda value: value["fixed_directory_layout"]["directories"][-1].update(
                {"mode": 0o500}
            ),
            "replays",
        ),
        (
            lambda value: value["fixed_maxima"][
                "cut-free incumbent replay receipt"
            ].update({"artifact_class": "metadata"}),
            "cut-free",
        ),
    ):
        drifted = copy.deepcopy(handoff)
        mutation(drifted)
        with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
            AUTHORITY._validate_budget_handoff_join(  # noqa: SLF001
                drifted,
                formal_budget_runtime=runtime,
                expected_attempt_root=attempt,
                expected_slot="region-capacity-ab-control",
                lifecycle=_Lifecycle,
            )
        assert exc_info.value.code == "ARM_BUDGET_HANDOFF_INVALID"
        assert detail in exc_info.value.detail

    inside_runtime = copy.deepcopy(runtime)
    inside_runtime["broker_endpoint_identity"]["path"] = str(
        formal_root / "control/budget-broker.sock"
    )
    inside_handoff = copy.deepcopy(handoff)
    inside_handoff["broker_socket_path"] = inside_runtime[
        "broker_endpoint_identity"
    ]["path"]
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._validate_budget_handoff_join(  # noqa: SLF001
            inside_handoff,
            formal_budget_runtime=inside_runtime,
            expected_attempt_root=attempt,
            expected_slot="region-capacity-ab-control",
            lifecycle=_Lifecycle,
        )
    assert exc_info.value.code == "ARM_BUDGET_HANDOFF_INVALID"
    assert "manifest-closed" in exc_info.value.detail

    backend._handoff = {
        **handoff,
        "arm_allocation_id": "c" * 64,
    }
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._validate_arm_budget_backend(  # noqa: SLF001
            backend,
            formal_budget_runtime=runtime,
            budget_handoff=handoff,
            slot="region-capacity-ab-control",
        )
    assert exc_info.value.code == "BUDGET_BACKEND_IDENTITY_INVALID"


def test_formal_root_writers_fail_before_any_path_without_broker(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY.prepare_baseline_output(campaign)
    assert exc_info.value.code == "PROSPECTIVE_BUDGET_AUTHORITY_MISSING"
    assert not campaign.exists()

    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY.build_manifest(campaign)
    assert exc_info.value.code == "PROSPECTIVE_BUDGET_AUTHORITY_MISSING"
    assert not campaign.exists()


def test_budget_publication_rejects_label_limit_and_identity_drift(
    tmp_path: Path,
) -> None:
    formal_root = tmp_path / "formal/artifacts"
    attempt = formal_root / "prospective/arms/region-capacity-ab-control"
    runtime = _runtime(formal_root)
    handoff = _handoff(formal_root, attempt, runtime)
    backend = _Backend(runtime=runtime, handoff=handoff)
    output = attempt / "replays/arithmetic.json"
    identity = AUTHORITY._budget_publish(  # noqa: SLF001
        backend,
        output,
        b"{}\n",
        label="independent arithmetic replay receipt",
    )
    assert identity["path"] == str(output)
    assert len(backend.calls) == 1

    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._budget_publish(  # noqa: SLF001
            backend,
            attempt / "unknown.json",
            b"{}\n",
            label="unknown",
        )
    assert exc_info.value.code == "BUDGET_PUBLICATION_CONTRACT_MISSING"

    small = _Backend(runtime=runtime, handoff=handoff)
    small.maximum_override = 1
    pre_send_boundary: list[str] = []
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._budget_publish(  # noqa: SLF001
            small,
            attempt / "too-large.json",
            b"{}\n",
            label="independent arithmetic replay receipt",
            publication_boundary=lambda: pre_send_boundary.append("crossed"),
        )
    assert exc_info.value.code == "BUDGET_PUBLICATION_LIMIT_INVALID"
    assert small.calls == []
    assert pre_send_boundary == []

    drifted = _Backend(runtime=runtime, handoff=handoff)
    drifted.return_path_drift = True
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._budget_publish(  # noqa: SLF001
            drifted,
            attempt / "drifted.json",
            b"{}\n",
            label="independent arithmetic replay receipt",
        )
    assert exc_info.value.code == "BUDGET_PUBLICATION_IDENTITY_DRIFT"
    assert len(drifted.calls) == 1


def test_ack_uncertainty_is_single_attempt_and_arm_stop_branches_are_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formal_root = tmp_path / "formal/artifacts"
    attempt = formal_root / "prospective/arms/region-capacity-ab-control"
    runtime = _runtime(formal_root)
    handoff = _handoff(formal_root, attempt, runtime)
    backend = _Backend(runtime=runtime, handoff=handoff)
    backend.raise_after_write = True
    output = attempt / "replays/ack-lost.json"
    publication_boundary: list[str] = []
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._budget_publish(  # noqa: SLF001
            backend,
            output,
            b"{}\n",
            label="independent arithmetic replay receipt",
            publication_boundary=lambda: publication_boundary.append(
                "crossed"
            ),
        )
    assert exc_info.value.code == "BUDGET_PUBLICATION_ACK_UNCERTAIN"
    assert output.exists()
    assert len(backend.calls) == 1
    assert publication_boundary == ["crossed"]

    unselected = AUTHORITY._arm_stop_branch(  # noqa: SLF001
        "DEFINITELY_NOT_PUBLISHED"
    )
    consumed = AUTHORITY._arm_stop_branch("PUBLISHED")  # noqa: SLF001
    uncertain = AUTHORITY._arm_stop_branch("UNCERTAIN")  # noqa: SLF001
    assert unselected == {
        "arm_slot_consumed": False,
        "branch": "ARM_UNSELECTED",
        "terminal_schema": AUTHORITY.ARM_UNSELECTED_TERMINAL_SCHEMA,
    }
    assert consumed == uncertain == {
        "arm_slot_consumed": True,
        "branch": "ARM_CONSUMED_INCOMPLETE",
        "terminal_schema": AUTHORITY.ARM_CONSUMED_INCOMPLETE_SCHEMA,
    }
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY._arm_stop_branch("RETRY")  # noqa: SLF001
    assert exc_info.value.code == "ARM_STOP_BRANCH_INVALID"

    terminal_identity = _identity(
        attempt / "arm-unselected-terminal.json",
        b"terminal",
    )
    unselected_stop = {
        "arm_allocation_id": handoff["arm_allocation_id"],
        "arm_slot_consumed": False,
        "branch": "ARM_UNSELECTED",
        "campaign_id": "c" * 64,
        "code": "AB16_PRESELECTION_FAIL_CLOSED",
        "failed_slot": "region-capacity-ab-control",
        "failure_code": "FIXTURE",
        "partial_output_identities": {},
        "phase": "PRESELECTION",
        "purpose": "AB16_IMMEDIATE_STOP",
        "run_nonce": "fixture",
        "schema_version": AUTHORITY.CAMPAIGN_STOP_SCHEMA,
        "selection_created": False,
        "terminal_identity": terminal_identity,
    }
    assert (
        AUTHORITY.validate_arm_immediate_stop(
            unselected_stop,
            manifest_schema=AUTHORITY.MANIFEST_SCHEMA,
            expected_slot="region-capacity-ab-control",
            expected_arm_allocation_id=str(handoff["arm_allocation_id"]),
        )
        == unselected_stop
    )
    mixed = dict(unselected_stop)
    mixed["schema_version"] = AUTHORITY.LEGACY_CAMPAIGN_STOP_SCHEMA
    with pytest.raises(AUTHORITY.AuthorityError) as exc_info:
        AUTHORITY.validate_arm_immediate_stop(
            mixed,
            manifest_schema=AUTHORITY.MANIFEST_SCHEMA,
            expected_slot="region-capacity-ab-control",
            expected_arm_allocation_id=str(handoff["arm_allocation_id"]),
        )
    assert exc_info.value.code == "AB16_COHORT_MIXED"

    stop_path = formal_root / "prospective/immediate-stop-a001.json"
    selection_path = attempt / "selection.json"
    monkeypatch.setattr(
        AUTHORITY,
        "_campaign_context",
        lambda _campaign: {
            "root": {
                "campaign_id": "c" * 64,
                "package": {"package_id": "package-fixture"},
                "run_nonce": "fixture",
            }
        },
    )
    monkeypatch.setattr(
        AUTHORITY,
        "_path_preregistration",
        lambda _context: (
            {
                "arm_selection_paths": {
                    "region-capacity-ab-control": str(selection_path)
                },
                "attempt_dirs": {
                    "region-capacity-ab-control": str(attempt)
                },
                "immediate_stop_path": str(stop_path),
            },
            {},
        ),
    )
    backend.raise_after_write = False
    consumed_stop_identity = AUTHORITY._publish_selection_attempt_stop(  # noqa: SLF001
        tmp_path / "campaign",
        slot="region-capacity-ab-control",
        failure=AUTHORITY.AuthorityError(
            "BUDGET_PUBLICATION_ACK_UNCERTAIN",
            "selection",
        ),
        budget_handoff=handoff,
        budget_backend=backend,
    )
    assert consumed_stop_identity is not None
    terminal = AUTHORITY._record(  # noqa: SLF001
        AUTHORITY.snapshot_regular(
            attempt / "arm-consumed-incomplete.json"
        ),
        "arm consumed-incomplete terminal",
    )
    assert terminal["selection_publication_state"] == "UNCERTAIN"
    assert terminal["selection_identity"] is None
    stop = AUTHORITY._record(  # noqa: SLF001
        AUTHORITY.snapshot_regular(stop_path),
        "arm immediate stop",
    )
    assert stop["branch"] == "ARM_CONSUMED_INCOMPLETE"
    assert stop["phase"] == "SELECTION_PUBLICATION_ATTEMPTED"
    assert stop["selection_publication_state"] == "UNCERTAIN"
    assert stop["selection_identity"] is None
    assert stop["consumption_identity"] == stop["terminal_identity"]
    assert (
        AUTHORITY.validate_arm_immediate_stop(
            stop,
            manifest_schema=AUTHORITY.MANIFEST_SCHEMA,
            expected_slot="region-capacity-ab-control",
            expected_arm_allocation_id=str(
                handoff["arm_allocation_id"]
            ),
            expected_consumption_identity=cast(
                Mapping[str, object],
                stop["terminal_identity"],
            ),
        )
        == stop
    )


def test_prospective_consumption_uses_only_post_seal_outside_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slot = "region-capacity-ab-control"
    formal_root = tmp_path / "formal/artifacts"
    attempt = formal_root / f"prospective/arms/{slot}"
    runtime = _runtime(formal_root)
    handoff = _handoff(formal_root, attempt, runtime)
    backend = _Backend(runtime=runtime, handoff=handoff)
    selection_identity = _write_identity(
        attempt / "selection.json",
        b"selection\n",
    )
    evidence = {
        "arm_gate_identity": _write_identity(
            attempt / "arm-gate.json",
            b"gate\n",
        ),
        "arm_result_identity": _write_identity(
            attempt / "result.json",
            b"result\n",
        ),
        "arithmetic_receipt_identity": _write_identity(
            attempt / "arithmetic.json",
            b"arithmetic\n",
        ),
        "resource_preterminal_identity": _write_identity(
            attempt / "resource.json",
            b"resource\n",
        ),
        "resource_replay_identity": _write_identity(
            attempt / "resource-replay.json",
            b"resource-replay\n",
        ),
        "resource_terminal_identity": _write_identity(
            attempt / "detached.json",
            b"detached\n",
        ),
    }
    arm_closure = {
        "arm_attempt_manifest_identity": _write_identity(
            attempt / "attempt-artifact-manifest.json",
            b"manifest\n",
        ),
        "arm_attempt_replay_identity": _write_identity(
            formal_root / f"replays/arm-attempt-roots/{slot}.json",
            b"attempt-replay\n",
        ),
        "arm_budget_terminal_identity": _write_identity(
            formal_root / f"budget/arm-terminals/{slot}.json",
            b"budget-terminal\n",
        ),
        "prior_response_accepted_identity": _write_identity(
            formal_root / "channels/budget-journal/segment-00000003.bin",
            b"accepted\n",
        ),
        "seal_response_authentication": {
            "nonce": "c" * 64,
            "response_sequence": 3,
            "response_sha256": "d" * 64,
        },
    }
    monkeypatch.setattr(
        AUTHORITY,
        "_launch_plan",
        lambda _root: [{"slot": slot}],
    )
    result = AUTHORITY._write_arm_consumption(  # noqa: SLF001
        {
            "root": {
                "campaign_id": "e" * 64,
                "run_nonce": "run-fixture",
            }
        },
        preregistration={"attempt_dirs": {slot: str(attempt)}},
        slot=slot,
        outcome="CREDIBLE_TERMINAL",
        selection_identity=selection_identity,
        evidence=evidence,
        failure_code="",
        suite_terminal_identity=_write_identity(
            formal_root / "terminal-classification.json",
            b"suite\n",
        ),
        manifest={
            "formal_budget_runtime": runtime,
            "schema_version": AUTHORITY.MANIFEST_SCHEMA,
        },
        pre_run={
            "budget_handoff": handoff,
            "schema_version": AUTHORITY.PRE_RUN_AUTHORITY_SCHEMA,
        },
        budget_backend=backend,
        arm_closure=arm_closure,
    )
    outside = formal_root / f"prospective/consumptions/{slot}.json"
    assert result["consumption_identity"]["path"] == str(outside)
    assert outside.exists()
    assert not (attempt / "consumption.json").exists()
    assert result["immediate_stop_identity"] is None
    assert result["consumption"]["arm_closure"] == arm_closure
    assert backend.post_seal_replay_identity == arm_closure[
        "arm_attempt_replay_identity"
    ]
