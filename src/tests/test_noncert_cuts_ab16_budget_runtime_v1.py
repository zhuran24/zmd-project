from __future__ import annotations

from collections.abc import Mapping
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import shutil
import socket
import stat
import sys
import tempfile
from types import ModuleType
from typing import cast

import pytest

from src.tests.test_noncert_cuts_ab16_formal_connector_v1 import (
    _formal_fixture,
)


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
sys.path.insert(0, str(RESEARCH))
try:
    import ab16_budget_authority_v1 as budget
    import ab16_budget_broker_v1 as broker
    import ab16_campaign_bootstrap_v2 as bootstrap
    import ab16_closure_actor_v1 as closure
    import ab16_final_release_actor_v1 as final_release_actor
    import ab16_formal_campaign_v1 as formal_campaign
    import ab16_formal_orchestrator_v1 as formal_orchestrator
    import ab16_native_budget_helper_v1 as native
    import ab16_outer_guardian_v1 as guardian
    import ab16_recovery_closeout_v1 as recovery
    import ab16_resource_admission_v1 as resource_admission
    import replay_ab16_formal_root_alt_v1 as formal_root_replay_alt
    import replay_ab16_formal_root_v1 as formal_root_replay
finally:
    sys.path.pop(0)


ROOT_LIMITS = {
    "closeout": 512 * 1024,
    "metadata": 1024 * 1024,
    "model": 128 * 1024,
    "normal": 128 * 1024,
}


class _PackageRoleGate:
    def __init__(
        self,
        *,
        accepted: bool = True,
        retained_descriptors: tuple[int, ...] = (),
    ) -> None:
        self.accepted = accepted
        self.calls: list[str] = []
        self._retained_descriptors = retained_descriptors
        self._role_descriptors: dict[str, int] = {}
        self._closed = False

    def require_verified_role(self, role: str) -> None:
        self.calls.append(role)
        if not self.accepted:
            raise RuntimeError("package verifier result is not PASS")

    def _ensure_role_descriptors(self) -> None:
        if self._closed:
            raise RuntimeError("package role gate is closed")
        if self._role_descriptors:
            return
        paths = {
            broker.PACKAGE_ROLE: RESEARCH / "ab16_budget_broker_v1.py",
            recovery.PACKAGE_ROLE: RESEARCH / "ab16_recovery_closeout_v1.py",
            closure.PACKAGE_ROLE: RESEARCH / "ab16_closure_actor_v1.py",
            final_release_actor.PACKAGE_ROLE: (
                RESEARCH / "ab16_final_release_actor_v1.py"
            ),
            "replay-ab16-formal-root-alt-v1": (
                RESEARCH / "replay_ab16_formal_root_alt_v1.py"
            ),
            "replay-ab16-formal-root-v1": (
                RESEARCH / "replay_ab16_formal_root_v1.py"
            ),
            "ab16-formal-orchestrator-v1": (
                RESEARCH / "ab16_formal_orchestrator_v1.py"
            ),
        }
        self._role_descriptors = {
            role: os.open(
                path,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            for role, path in paths.items()
        }

    def retained_descriptors(self) -> tuple[int, ...]:
        self._ensure_role_descriptors()
        return (
            *self._role_descriptors.values(),
            *self._retained_descriptors,
        )

    def role_descriptors(self) -> dict[str, int]:
        self._ensure_role_descriptors()
        return dict(self._role_descriptors)

    def load_verified_role(self, role: str) -> ModuleType:
        self.require_verified_role(role)
        modules = {
            broker.PACKAGE_ROLE: broker,
            recovery.PACKAGE_ROLE: recovery,
            closure.PACKAGE_ROLE: closure,
            final_release_actor.PACKAGE_ROLE: final_release_actor,
            "replay-ab16-formal-root-alt-v1": formal_root_replay_alt,
            "replay-ab16-formal-root-v1": formal_root_replay,
            "ab16-formal-orchestrator-v1": formal_orchestrator,
        }
        return modules[role]

    def selected_fd_transport(self) -> dict[str, object]:
        self._ensure_role_descriptors()
        descriptor = self._role_descriptors[broker.PACKAGE_ROLE]
        observed = os.fstat(descriptor)
        raw = os.pread(descriptor, observed.st_size, 0)
        identity = {
            "descriptor": descriptor,
            "mode": stat.S_IMODE(observed.st_mode),
            "package_path": "sources/ab16_budget_broker_v1.py",
            "proc_fd_path": f"/proc/{os.getpid()}/fd/{descriptor}",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        return {
            "owner": broker.process_identity(),
            "roles": {
                "authority": dict(identity),
                "loader": dict(identity),
                "native-binary": dict(identity),
                "native-wrapper": dict(identity),
                "python": dict(identity),
            },
            "schema_version": (
                "noncert-cuts-ab16-package-selected-fd-transport-v1"
            ),
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for descriptor in (
            *self._role_descriptors.values(),
            *self._retained_descriptors,
        ):
            os.close(descriptor)
        self._role_descriptors.clear()


class _NativeHelperAuthorization:
    def __init__(
        self,
        helper: native.NativeBudgetHelper,
        descriptor: int,
        *,
        close_error: BaseException | None = None,
    ) -> None:
        self._helper = helper
        self._descriptor = descriptor
        self._signature = self._fd_signature(os.fstat(descriptor))
        self._close_error = close_error
        self._closed = False
        self.close_count = 0

    @staticmethod
    def _fd_signature(value: os.stat_result) -> tuple[int, ...]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_uid,
            value.st_gid,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    @property
    def helper(self) -> native.NativeBudgetHelper:
        if self._closed:
            raise RuntimeError("native-helper authorization is closed")
        return self._helper

    def retained_descriptors(self) -> tuple[int, ...]:
        if self._closed:
            raise RuntimeError("native-helper authorization is closed")
        if self._fd_signature(os.fstat(self._descriptor)) != self._signature:
            raise RuntimeError("native-helper retained FD drifted")
        return (self._descriptor,)

    def close(self) -> None:
        if self._closed:
            return
        self.close_count += 1
        self._closed = True
        primary: BaseException | None = None
        try:
            if self._fd_signature(os.fstat(self._descriptor)) != self._signature:
                raise RuntimeError("native-helper retained FD drifted")
        except BaseException as exc:
            primary = exc
        try:
            os.close(self._descriptor)
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "native-helper retained FD close also failed: "
                    f"{type(exc).__name__}: {exc}"
                )
        if primary is None and self._close_error is not None:
            primary = self._close_error
        if primary is not None:
            raise primary


def _transferred_runtime_account(
    tmp_path: Path,
    *,
    extra_directories: tuple[str, ...] = (),
    formal_contract_record: Mapping[str, object] | None = None,
    formal_root: Path | None = None,
    owner_nonce: str,
    root_limits: Mapping[str, int] = ROOT_LIMITS,
) -> tuple[
    budget.FormalBudgetBroker,
    dict[str, object],
    dict[str, budget.RetainedStagingReservation],
    dict[str, dict[str, object]],
    budget.RetainedDirectoryCapability,
    dict[str, object],
    Path,
    dict[str, object],
    Path,
]:
    creator = budget.FormalBudgetBroker.create(
        tmp_path / "formal-persistent"
        if formal_root is None
        else formal_root,
        category_limits=root_limits,
        owner_nonce="bootstrap-owner",
    )
    for relative in (
        "arms",
        "arms/arm-01",
        "channels",
        "channels/budget-journal",
        "closeout",
        "formal-closure",
        "locks",
        *extra_directories,
    ):
        creator.register_directory(relative)
    contract_publication = creator.publish_bytes(
        "formal-root-budget-contract.json",
        broker.canonical_json_bytes(
            {
                "schema_version": (
                    "noncert-cuts-ab16-zero-authority-formal-contract-v1"
                )
            }
            if formal_contract_record is None
            else dict(formal_contract_record)
        ),
        maximum_bytes=4096,
        artifact_class="metadata",
    )
    contract_identity = {
        "path": str(
            creator.root / str(contract_publication["path"])
        ),
        "sha256": contract_publication["sha256"],
        "size_bytes": contract_publication["size_bytes"],
    }
    reservations: dict[str, budget.RetainedStagingReservation] = {}
    handoffs: dict[str, dict[str, object]] = {}
    for purpose, spec in sorted(broker.FIXED_PURPOSE_SPECS.items()):
        initial = creator.reserve_retained_staging(
            spec.parent_path,
            maximum_bytes=(
                spec.exact_maximum_bytes
                if spec.exact_maximum_bytes is not None
                else 16 * 1024
            ),
            artifact_class=spec.artifact_class,
            purpose=purpose,
        )
        successor, reservation_handoff = initial.transfer_ownership(
            to_owner_nonce=owner_nonce,
        )
        reservations[purpose] = successor
        handoffs[purpose] = reservation_handoff
    account, account_handoff = creator.transfer_ownership(
        to_owner_nonce=owner_nonce
    )
    control_root = budget.FormalBudgetBroker.create(
        tmp_path / "control-container",
        category_limits=ROOT_LIMITS,
        owner_nonce="bootstrap-owner",
    )
    control_root.register_directory("formal-ab16/control")
    initial_control = control_root.retain_directory(
        "formal-ab16/control",
        purpose="formal-control-parent",
    )
    control, control_handoff = initial_control.transfer_ownership(
        to_owner_nonce=owner_nonce,
    )
    endpoint = (
        control_root.root
        / "formal-ab16/control/budget-broker.sock"
    )
    control_root.close()
    return (
        account,
        account_handoff,
        reservations,
        handoffs,
        control,
        control_handoff,
        endpoint,
        contract_identity,
        tmp_path / "bootstrap-package-failure-closeout.json",
    )


def _persistent_spawn_bindings(
    *,
    contract_identity: Mapping[str, object],
    failure_path: Path,
    owner_nonce: str,
) -> dict[str, object]:
    final_release_parent = (
        failure_path.parent
        / broker.OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
    )
    final_release_parent.parent.mkdir(mode=0o700, parents=True)
    final_release_parent.mkdir(mode=0o700)
    parent_fd = os.open(
        final_release_parent,
        os.O_RDONLY
        | os.O_CLOEXEC
        | os.O_DIRECTORY
        | os.O_NOFOLLOW,
    )
    extent_descriptors: dict[str, int] = {}
    try:
        extent_records: dict[str, dict[str, object]] = {}
        for purpose, target_name in sorted(
            broker.OUTSIDE_FINAL_RELEASE_SPECS.items()
        ):
            staging_name = f".{target_name}.fixture-staging"
            descriptor = os.open(
                staging_name,
                os.O_RDWR
                | os.O_CLOEXEC
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            extent_descriptors[purpose] = descriptor
            os.posix_fallocate(
                descriptor,
                0,
                broker.OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES,
            )
            os.fsync(descriptor)
            extent_records[purpose] = broker.PreparedExtent(
                artifact_class="closeout",
                maximum_bytes=(
                    broker.OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES
                ),
                parent_identity=broker._parent_identity(  # noqa: SLF001
                    parent_fd
                ),
                parent_path=(
                    broker.OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
                ),
                staging_name=staging_name,
                target_name=target_name,
                staging_identity=broker._identity(  # noqa: SLF001
                    descriptor
                ),
            ).as_record()
        capability = broker.FinalReleaseParentCapability(
            descriptor=parent_fd,
            directory_path=(
                broker.OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
            ),
            path=final_release_parent,
            purpose="outside-formal-root-final-release-parent",
            owner_nonce=owner_nonce,
            identity=broker._parent_identity(parent_fd),  # noqa: SLF001
            extent_descriptors=extent_descriptors,
            extent_records=extent_records,
        )
    except BaseException:
        for descriptor in extent_descriptors.values():
            os.close(descriptor)
        os.close(parent_fd)
        raise
    final_release_handoff = {
        "directory_handoff": {
            "directory_path": (
                broker.OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
            ),
            "path": str(final_release_parent),
            "to_owner_nonce": owner_nonce,
        },
        "reservation_handoffs": {
            purpose: {
                "parent_path": str(final_release_parent),
                "purpose": purpose,
                "shared_parent_fd": True,
                "to_owner_nonce": owner_nonce,
            }
            for purpose in sorted(
                broker.OUTSIDE_FINAL_RELEASE_SPECS
            )
        },
        "schema_version": broker.FINAL_RELEASE_PARENT_HANDOFF_SCHEMA,
        "to_owner_nonce": owner_nonce,
    }
    calibration_record: dict[str, object] = {}
    calibration_raw = broker.canonical_json_bytes(calibration_record)
    calibration_identity = {
        "path": str(contract_identity["path"]),
        "sha256": hashlib.sha256(calibration_raw).hexdigest(),
        "size_bytes": len(calibration_raw),
    }
    calibration_bundles = {
        stage: {
            "identity": dict(calibration_identity),
            "record": dict(calibration_record),
        }
        for stage in (
            "FULL_PREFLIGHT",
            "GATE_B_QUALIFICATION",
            "FORMAL_ORGANIC_ARM",
        )
    }
    calibration_tools = {
        role: {
            "sha256": hashlib.sha256(role.encode("ascii")).hexdigest(),
            "size_bytes": len(role),
        }
        for role in broker.CALIBRATION_TOOL_ROLES
    }

    def fixed_cap(
        artifact_class: str,
        path: str,
        *,
        branch: str = "success",
        maximum_bytes: int = 64 * 1024,
    ) -> dict[str, object]:
        return {
            "artifact_class": artifact_class,
            "branch": branch,
            "maximum_bytes": maximum_bytes,
            "maximum_publications": 1,
            "multiplicity_source": {
                "kind": "terminal-branch-fixed-path",
                "maximum_fixed_publications": 1,
                "terminal_branch": branch,
            },
            "path_contract": {
                "kind": "fixed",
                "root": "formal-root",
                "root_relative_path": path,
            },
        }

    arm_contracts = {
        broker.ARM_MANIFEST_BUDGET_LABEL: fixed_cap(
            broker.ARM_MANIFEST_ARTIFACT_CLASS,
            "arms/arm-01/attempt-artifact-manifest.json",
        ),
        broker.ARM_TERMINAL_BUDGET_LABEL: fixed_cap(
            broker.ARM_TERMINAL_ARTIFACT_CLASS,
            "budget/arm-terminals/arm-01.json",
        ),
        broker.ARM_REPLAY_BUDGET_LABEL: fixed_cap(
            broker.ARM_REPLAY_ARTIFACT_CLASS,
            "replays/arm-attempt-roots/arm-01.json",
        ),
        broker.ARM_CONSUMPTION_BUDGET_LABEL: fixed_cap(
            broker.ARM_CONSUMPTION_ARTIFACT_CLASS,
            "prospective/consumptions/arm-01.json",
        ),
        "test arm result": fixed_cap(
            "normal",
            "arms/arm-01/result.json",
            maximum_bytes=4096,
        ),
        "test supervisor origin": fixed_cap(
            "normal",
            "arms/arm-01/supervisor-origin.json",
            maximum_bytes=64,
        ),
    }
    return {
        "bootstrap_failure_closeout_path": failure_path,
        "final_release_parent_capability": capability,
        "final_release_parent_handoff": final_release_handoff,
        "bootstrap_handoff_spec": {
            "artifact_class": "metadata",
            "maximum_bytes": 16 * 1024,
            "relative_path": "formal-root-budget-handoff.json",
        },
        "formal_root_budget_contract_identity": dict(
            contract_identity
        ),
        "formal_resource_calibration_bundle_identity": calibration_identity,
        "resource_budget_profile_identity": {
            "mode": 0o444,
            **dict(contract_identity),
        },
        "resource_calibration_authorization_bundles": calibration_bundles,
        "calibration_tool_content_identities": calibration_tools,
        "formal_artifact_contracts": (),
        "formal_append_contracts": (
            {
                "artifact_class": "metadata",
                "channel": "budget-journal",
                "label": "AB16 formal budget journal segment",
                "maximum_bytes": 4096,
                "maximum_segments": 16_384,
                "multiplicity_derivation": {
                    "basis": (
                        "profile-derived data-plane maxima plus explicit "
                        "temporary control-plane allowances"
                    ),
                    "bootstrap_and_formal_control_allowance": 2048,
                    "derived_minimum_actions": 12_320,
                    "evidence_status": "unmeasured-temporary",
                    "exhaustion": (
                        "fail before the next broker-journal append; "
                        "formal-consumed-incomplete"
                    ),
                    "formal_arm_count": 16,
                    "maximum_segment_bytes": 4096,
                    "per_arm_append_maximum": 479,
                    "per_arm_control_allowance": 64,
                    "per_arm_fixed_publication_branch_maximum": 99,
                    "retained_allocation_bytes": 67_108_864,
                    "result_maximum_segments": 16_384,
                    "segment_cap_basis": (
                        "policy-defined canonical action-record cap pending "
                        "comparable calibration"
                    ),
                    "segment_count_rounding": (
                        "next power of two above derived minimum actions"
                    ),
                    "sufficiency_claim": False,
                },
                "parent_path": "channels/budget-journal",
            },
        ),
        "arm_artifact_contracts": {"arm-01": arm_contracts},
        "arm_append_contracts": {"arm-01": ()},
        "package_id": "2" * 64,
        "campaign_run_nonce": "run-zero-authority-budget-test",
    }


def test_publication_policy_enforces_label_path_count_branch_and_segments() -> None:
    def fixed(*, branch: str, path: str) -> dict[str, object]:
        return {
            "artifact_class": "publication",
            "branch": branch,
            "maximum_bytes": 64,
            "maximum_publications": 1,
            "multiplicity_source": {
                "kind": "terminal-branch-fixed-path",
                "maximum_fixed_publications": 1,
                "terminal_branch": branch,
            },
            "path_contract": {
                "kind": "fixed",
                "root": "formal-root",
                "root_relative_path": path,
            },
        }

    policy = broker._PublicationPolicyState(  # noqa: SLF001
        formal_artifacts=(),
        formal_channels=(),
        arm_artifacts={
            "arm-01": {
                "failure": fixed(
                    branch="failure",
                    path="arms/arm-01/failure.json",
                ),
                "compile attach journal segment": {
                    "artifact_class": "ledger",
                    "branch": "common",
                    "maximum_bytes": 16,
                    "maximum_publications": 0,
                    "multiplicity_source": {
                        "kind": "append-channel-only",
                        "maximum_fixed_publications": 0,
                    },
                    "path_contract": {
                        "channel": "arm-01-compile-journal",
                        "kind": "append-channel",
                        "root": "formal-root",
                    },
                },
                "success": fixed(
                    branch="success",
                    path="arms/arm-01/success.json",
                ),
            }
        },
        arm_channels={
            "arm-01": (
                {
                    "artifact_class": "ledger",
                    "channel": "arm-01-compile-journal",
                    "label": "compile attach journal segment",
                    "maximum_bytes": 16,
                    "maximum_segments": 221,
                    "multiplicity_derivation": {
                        "formula": (
                            "3 genesis/seal records + 3 records per attach hook "
                            "+ at most one compiled-cut record per generated cut"
                        ),
                        "maximum_attach_hooks": 30,
                        "maximum_generated_cuts": 128,
                        "result_maximum_segments": 221,
                    },
                    "parent_path": "arms/arm-01/compile-journal",
                },
            )
        },
    )
    policy.authorize(
        arm_slot="arm-01",
        artifact_class="publication",
        channel=None,
        label="success",
        maximum_bytes=64,
        relative_path="arms/arm-01/success.json",
        sequence=None,
    )
    for label, path, maximum in (
        ("success", "arms/arm-01/success.json", 64),
        ("failure", "arms/arm-01/failure.json", 64),
        ("unknown", "arms/arm-01/unknown.json", 64),
        ("success", "arms/arm-01/other.json", 64),
        ("success", "arms/arm-01/success.json", 63),
    ):
        with pytest.raises(
            broker.BrokerProtocolError,
            match="PUBLICATION_(POLICY_DRIFT|BRANCH_CONFLICT)",
        ):
            policy.authorize(
                arm_slot="arm-01",
                artifact_class="publication",
                channel=None,
                label=label,
                maximum_bytes=maximum,
                relative_path=path,
                sequence=None,
            )
    policy.authorize(
        arm_slot="arm-01",
        artifact_class="ledger",
        channel="arm-01-compile-journal",
        label="compile attach journal segment",
        maximum_bytes=16,
        relative_path="arms/arm-01/compile-journal/segment-00000000.bin",
        sequence=0,
    )
    with pytest.raises(
        broker.BrokerProtocolError,
        match="PUBLICATION_POLICY_DRIFT",
    ):
        policy.authorize(
            arm_slot="arm-01",
            artifact_class="ledger",
            channel="arm-01-compile-journal",
            label="compile attach journal segment",
            maximum_bytes=16,
            relative_path="arms/arm-01/compile-journal/segment-00000221.bin",
            sequence=221,
        )


def test_publication_policy_hook_paths_are_exactly_zero_through_twenty_nine() -> None:
    policy = broker._PublicationPolicyState(  # noqa: SLF001
        formal_artifacts=(),
        formal_channels=(),
        arm_artifacts={
            "arm-01": {
                "attach solution-vector evidence": {
                    "artifact_class": "publication",
                    "branch": "common",
                    "maximum_bytes": 64,
                    "maximum_publications": 30,
                    "multiplicity_source": {
                        "kind": "attach-hook",
                        "maximum_attach_hooks": 30,
                        "publications_per_hook": 1,
                    },
                    "path_contract": {
                        "index_maximum": 29,
                        "index_minimum": 0,
                        "index_name": "hook_id",
                        "kind": "indexed-template",
                        "root": "formal-root",
                        "root_relative_path_template": (
                            "arms/arm-01/runtime/"
                            "hook-{hook_id:04d}-solution-vector.json"
                        ),
                    },
                },
            },
        },
        arm_channels={"arm-01": ()},
    )
    for hook_id in (0, 29):
        policy.authorize(
            arm_slot="arm-01",
            artifact_class="publication",
            channel=None,
            label="attach solution-vector evidence",
            maximum_bytes=64,
            relative_path=(
                f"arms/arm-01/runtime/"
                f"hook-{hook_id:04d}-solution-vector.json"
            ),
            sequence=None,
        )
    with pytest.raises(
        broker.BrokerProtocolError,
        match="PUBLICATION_POLICY_DRIFT",
    ):
        policy.authorize(
            arm_slot="arm-01",
            artifact_class="publication",
            channel=None,
            label="attach solution-vector evidence",
            maximum_bytes=64,
            relative_path=(
                "arms/arm-01/runtime/hook-0030-solution-vector.json"
            ),
            sequence=None,
        )


def _fd_count() -> int:
    return len(
        [
            name
            for name in os.listdir("/proc/self/fd")
            if name.isdecimal() and Path(f"/proc/self/fd/{name}").exists()
        ]
    )


def _probe_worker_stdio_contract(
    tmp_path: Path,
    *,
    writable_regular_descriptor: int | None,
) -> dict[str, object]:
    report_read, report_write = os.pipe2(os.O_CLOEXEC)
    pid = os.fork()
    if pid == 0:
        os.close(report_read)
        try:
            stdin_fd = os.open(
                "/dev/null",
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            stdout_fd = os.open(
                "/dev/null",
                os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            stderr_fd = os.open(
                "/dev/null",
                os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            for target, source in (
                (0, stdin_fd),
                (1, stdout_fd),
                (2, stderr_fd),
            ):
                os.dup2(source, target)
            for descriptor in (stdin_fd, stdout_fd, stderr_fd):
                if descriptor > 2:
                    os.close(descriptor)
            if writable_regular_descriptor is not None:
                regular_fd = os.open(
                    tmp_path / f"stdio-{writable_regular_descriptor}.log",
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    0o600,
                )
                os.dup2(regular_fd, writable_regular_descriptor)
                if regular_fd > 2:
                    os.close(regular_fd)
            try:
                contract = broker.validate_worker_stdio_contract()
            except broker.BrokerProtocolError as exc:
                result: dict[str, object] = {
                    "code": exc.code,
                    "status": "FAIL_CLOSED",
                }
            else:
                result = {"contract": contract, "status": "PASS"}
            os.write(report_write, broker.canonical_json_bytes(result))
            os._exit(0)
        except BaseException as exc:
            os.write(
                report_write,
                broker.canonical_json_bytes(
                    {
                        "detail": f"{type(exc).__name__}: {exc}",
                        "status": "INTERNAL_ERROR",
                    }
                ),
            )
            os._exit(2)
    os.close(report_write)
    raw = bytearray()
    while True:
        chunk = os.read(report_read, 4096)
        if not chunk:
            break
        raw.extend(chunk)
    os.close(report_read)
    waited, status = os.waitpid(pid, 0)
    assert waited == pid
    assert os.waitstatus_to_exitcode(status) == 0
    return json.loads(bytes(raw))


@pytest.mark.parametrize("descriptor", [1, 2])
def test_worker_stdio_contract_rejects_inherited_writable_regular_output(
    tmp_path: Path,
    descriptor: int,
) -> None:
    result = _probe_worker_stdio_contract(
        tmp_path,
        writable_regular_descriptor=descriptor,
    )
    assert result == {
        "code": "WORKER_STDIO_WRITABLE_PATH_FORBIDDEN",
        "status": "FAIL_CLOSED",
    }
    assert (tmp_path / f"stdio-{descriptor}.log").exists()


def test_worker_stdio_contract_accepts_explicit_null_transport(
    tmp_path: Path,
) -> None:
    result = _probe_worker_stdio_contract(
        tmp_path,
        writable_regular_descriptor=None,
    )
    assert result["status"] == "PASS"
    assert [
        (item["descriptor"], item["access"], item["kind"])
        for item in result["contract"]
    ] == [
        (0, "read-only", "null-character-device"),
        (1, "write-only", "null-character-device"),
        (2, "write-only", "null-character-device"),
    ]


def _native_helper() -> tuple[native.NativeBudgetHelper, int]:
    path = RESEARCH / "ab16_native_budget_helper_x86_64_v1.so"
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        helper = native.NativeBudgetHelper(
            descriptor,
            expected_identity=native.expected_package_identity(),
        )
    except BaseException:
        os.close(descriptor)
        raise
    return helper, descriptor


def _spawn_broker(
    tmp_path: Path,
    *,
    native_helper: native.NativeBudgetHelper | None = None,
    arm_directories: tuple[dict[str, object], ...] | None = None,
) -> broker.BrokerProcess:
    return broker.spawn_broker_for_test(
        tmp_path / "formal",
        category_limits=ROOT_LIMITS,
        native_helper=native_helper,
        arm_directories={
            "arm-01": (
                arm_directories
                if arm_directories is not None
                else (
                    {"mode_octal": "0700", "path": "models"},
                    {"mode_octal": "0500", "path": "tmp"},
                )
            )
        },
    )


def _prepare_recovery(
    process: broker.BrokerProcess,
) -> tuple[dict[str, object], tuple[int, ...]]:
    frame = process.request(
        "PREPARE_RECOVERY",
        {"closeout_maximum_bytes": 16 * 1024},
        expected_fd_counts=frozenset({3}),
    )
    return dict(frame.record["result"]), frame.descriptors


def _prepare_closure(
    process: broker.BrokerProcess,
) -> tuple[dict[str, object], tuple[int, ...]]:
    frame = process.request(
        "PREPARE_CLOSURE",
        {
            "budget_terminal_maximum_bytes": 64 * 1024,
            "formal_manifest_maximum_bytes": 128 * 1024,
            "recovery_terminal_maximum_bytes": 16 * 1024,
        },
        expected_fd_counts=frozenset({5}),
    )
    return dict(frame.record["result"]), frame.descriptors


def _seal_fixed_closure_for_test(frame: broker.ReceivedFrame) -> None:
    result = frame.record["result"]
    assert result["schema_version"] == "noncert-cuts-ab16-prepared-closure-v2"
    reservations = result["reservations"]
    descriptors = frame.descriptors
    staging_by_purpose = {
        "formal-closure-consumption": descriptors[2],
        "recovery-disarm-terminal": descriptors[3],
        "formal-budget-terminal": descriptors[4],
        "formal-manifest": descriptors[5],
        "success-dual-lock-release": descriptors[6],
        "failure-terminal-release": descriptors[7],
    }
    try:
        for purpose, descriptor in staging_by_purpose.items():
            broker.consume_once_extent(
                reservations[purpose]["extent"],
                descriptor=descriptor,
                record={
                    "schema_version": (
                        "noncert-cuts-ab16-zero-authority-closure-fixture-v1"
                    ),
                    "purpose": purpose,
                    "state": "SEALED_TEST_FIXTURE",
                },
            )
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def _wait_and_close_broker(process: broker.BrokerProcess, *, expected: set[int]) -> None:
    if not process._waited:  # noqa: SLF001
        result = process.wait()
        assert result in expected
    assert broker.pidfd_reports_exit(process.pidfd)
    process.close()


def _wait_and_close_recovery(process: recovery.RecoveryProcess, *, expected: set[int]) -> None:
    if not process._waited:  # noqa: SLF001
        result = process.wait()
        assert result in expected
    assert broker.pidfd_reports_exit(process.pidfd)
    process.close()


def _wait_and_close_closure(process: closure.ClosureProcess, *, expected: set[int]) -> None:
    if not process._waited:  # noqa: SLF001
        result = process.wait()
        assert result in expected
    assert broker.pidfd_reports_exit(process.pidfd)
    process.close()


def _kill_broker(process: broker.BrokerProcess) -> None:
    os.kill(process.pid, signal.SIGKILL)
    assert process.wait() == 128 + signal.SIGKILL
    assert broker.pidfd_reports_exit(process.pidfd)
    process.connection.close()


def _normal_exit(process: broker.BrokerProcess) -> dict[str, object]:
    result = dict(process.request("EXIT", {}).record["result"])
    assert result["state"] == "BROKER_EXIT_ACCEPTED"
    inventory = result["root_inventory"]
    assert inventory["schema_version"] == broker.ROOT_INVENTORY_SCHEMA
    assert type(inventory["expected_path_types"]) is list
    assert process.wait() == 0
    assert broker.pidfd_reports_exit(process.pidfd)
    return dict(inventory)


def _disarm(
    process: recovery.RecoveryProcess | recovery.DetachedRecoveryProcess,
) -> dict[str, object]:
    intent = {
        "schema_version": "noncert-cuts-ab16-recovery-disarm-intent-v1",
        "state": "FINAL_TERMINAL_JOINED",
    }
    result = process.terminal(
        "DISARM",
        {"disarm_intent_sha256": recovery.disarm_intent_sha256(intent)},
    )
    if isinstance(process, recovery.DetachedRecoveryProcess):
        process.prove_exit()
    else:
        assert process.wait() == 0
        assert broker.pidfd_reports_exit(process.pidfd)
    return result


def test_broker_uses_canonical_seqpacket_and_durable_journal(tmp_path: Path) -> None:
    process = _spawn_broker(tmp_path)
    try:
        assert process.actor["pid"] == process.pid
        assert process.actor["pid_starttime"] == broker.process_starttime(process.pid)
        assert process.pidfd_method in {"python-os.pidfd_open", "libc-pidfd_open"}
        allocation = process.request(
            "ALLOCATE_ARM",
            {
                "arm_slot": "arm-01",
                "category_limits": {
                    "closeout": 4096,
                    "metadata": 4096,
                    "normal": 4096,
                },
            },
        )
        assert allocation.record["journal"]["path"] == "channels/budget-journal/segment-00000000.bin"
        journal_path = tmp_path / "formal" / str(allocation.record["journal"]["path"])
        event = json.loads(journal_path.read_bytes())
        assert event["action"] == "ALLOCATE_ARM"
        assert event["request_sha256"]
        assert event["result"] == _journal_result_projection(
            allocation.record["result"]
        )
        assert stat_mode(tmp_path / "formal" / "models") == 0o700
        assert stat_mode(tmp_path / "formal" / "tmp") == 0o500
        assert stat_mode(journal_path) == 0o444
        _normal_exit(process)
    finally:
        _wait_and_close_broker(process, expected={0, 2})


def test_broker_journal_hash_joins_large_result_without_exceeding_segment(
    tmp_path: Path,
) -> None:
    directories = tuple(
        {
            "mode_octal": "0700",
            "path": f"retained-directory-{index:03d}",
        }
        for index in range(160)
    )
    process = _spawn_broker(
        tmp_path,
        arm_directories=directories,
    )
    try:
        allocation = process.request(
            "ALLOCATE_ARM",
            {
                "arm_slot": "arm-01",
                "category_limits": {
                    "closeout": 4096,
                    "metadata": 4096,
                    "normal": 4096,
                },
            },
        )
        result_raw = broker.canonical_json_bytes(
            allocation.record["result"]
        )
        assert len(result_raw) > broker.JOURNAL_MAX_BYTES
        journal_path = (
            tmp_path
            / "formal"
            / str(allocation.record["journal"]["path"])
        )
        journal_raw = journal_path.read_bytes()
        assert len(journal_raw) <= broker.JOURNAL_MAX_BYTES
        event = json.loads(journal_raw)
        assert event["result"] == _journal_result_projection(
            allocation.record["result"]
        )
        _normal_exit(process)
    finally:
        _wait_and_close_broker(process, expected={0, 2})


def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o7777


def _journal_result_projection(
    result: object,
) -> dict[str, object]:
    assert type(result) is dict
    raw = broker.canonical_json_bytes(result)
    projection: dict[str, object] = {
        "result_sha256": hashlib.sha256(raw).hexdigest(),
        "result_size_bytes": len(raw),
    }
    for key in ("schema_version", "state", "status"):
        value = result.get(key)
        if type(value) is str:
            projection[key] = value
    return projection


def test_noncanonical_frame_fails_before_budget_mutation(tmp_path: Path) -> None:
    process = _spawn_broker(tmp_path)
    try:
        raw = (
            '{"schema_version": "noncert-cuts-ab16-budget-broker-request-v1",'
            f'"action":"STATUS","nonce":"{process.nonce}","payload":{{}},"sequence":1}}\n'
        ).encode()
        assert process.connection.send(raw) == len(raw)
        response = broker.receive_frame(process.connection)
        assert response.record["status"] == "FAIL_CLOSED"
        assert response.record["code"] == "NONCANONICAL_FRAME"
        assert process.wait() == 2
        assert not (tmp_path / "formal" / "channels").exists()
    finally:
        _wait_and_close_broker(process, expected={2})


def test_ack_loss_after_journal_never_refunds_or_retries(tmp_path: Path) -> None:
    process = _spawn_broker(tmp_path)
    try:
        raw = b"ack-lost"
        broker.send_frame(
            process.connection,
            {
                "schema_version": broker.REQUEST_SCHEMA,
                "action": "PUBLISH",
                "nonce": process.nonce,
                "payload": {
                    "arm_slot": None,
                    "artifact_class": "normal",
                    "maximum_bytes": 4096,
                    "payload_hex": raw.hex(),
                    "relative_path": "ack-lost.bin",
                },
                "sequence": 1,
            },
        )
        process.connection.close()
        assert process.wait() in {0, 2}
        target = tmp_path / "formal" / "ack-lost.bin"
        assert target.read_bytes() == raw
        journals = sorted((tmp_path / "formal" / "channels" / "budget-journal").glob("segment-*.bin"))
        assert len(journals) == 1
        event = json.loads(journals[0].read_bytes())
        assert event["action"] == "PUBLISH"
        assert set(event["result"]) == {
            "result_sha256",
            "result_size_bytes",
            "schema_version",
        }
        assert type(event["result"]["schema_version"]) is str
        assert event["result"]["result_size_bytes"] > 0
        assert not list((tmp_path / "formal").glob(".ab16-budget-stage-*"))
    finally:
        _wait_and_close_broker(process, expected={0, 2})


def test_arm_manifest_seal_requires_same_session_successor_acceptance(
    tmp_path: Path,
) -> None:
    owner_nonce = "7" * 64
    supervisor_credential = "8" * 64
    root_limits = {
        **ROOT_LIMITS,
        "publication": 128 * 1024,
    }
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        extra_directories=(
            "budget",
            "budget/arm-terminals",
            "prospective",
            "prospective/consumptions",
            "replays",
            "replays/arm-attempt-roots",
        ),
        owner_nonce=owner_nonce,
        root_limits=root_limits,
    )
    helper, helper_fd = _native_helper()
    package_gate = _PackageRoleGate()
    native_authorization = _NativeHelperAuthorization(helper, helper_fd)
    spawn_bindings = _persistent_spawn_bindings(
        contract_identity=contract_identity,
        failure_path=failure_path,
        owner_nonce=owner_nonce,
    )
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=package_gate,
        native_helper_authorization=native_authorization,
        **spawn_bindings,
        supervisor_credential=supervisor_credential,
        expected_supervisor_peer=broker.process_identity(),
        formal_directories=(
            {"mode_octal": "0700", "path": "arms"},
            {"mode_octal": "0700", "path": "budget"},
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {"mode_octal": "0700", "path": "locks"},
            {"mode_octal": "0700", "path": "prospective"},
            {"mode_octal": "0700", "path": "replays"},
            {"mode_octal": "0700", "path": "arms/arm-01"},
            {
                "mode_octal": "0700",
                "path": "budget/arm-terminals",
            },
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
            {
                "mode_octal": "0700",
                "path": "prospective/consumptions",
            },
            {
                "mode_octal": "0700",
                "path": "replays/arm-attempt-roots",
            },
        ),
        arm_directories={
            "arm-01": (
                {"mode_octal": "0700", "path": "arms/arm-01"},
            ),
        },
    )
    supervisor = process.connect(
        credential=supervisor_credential,
        role="supervisor",
    )
    descriptor = -1
    try:
        allocation = supervisor.request(
            "ALLOCATE_ARM",
            {
                "arm_slot": "arm-01",
                "category_limits": {
                    "closeout": 192 * 1024,
                    "publication": 64 * 1024,
                },
            },
        ).record["result"]
        assert allocation["schema_version"] == broker.ARM_ALLOCATION_SCHEMA
        assert allocation["allocation_state"] == "ACTIVE"
        before = supervisor.request("STATUS", {}).record["result"][
            "contract"
        ]
        assert before["arms"]["arm-01"]["allocation_state"] == "ACTIVE"
        path_types_before = supervisor.request("STATUS", {}).record[
            "result"
        ]["root_closure"]["entries"]
        expected_path_types_before = [
            {"path": item["path"], "type": item["type"]}
            for item in path_types_before
        ]
        expected_path_types_before.sort(
            key=lambda item: (item["path"], item["type"])
        )
        manifest_path = "arms/arm-01/attempt-artifact-manifest.json"
        arm_inventory = [{"path": manifest_path, "type": "regular"}]
        arm_inventory_sha256 = hashlib.sha256(
            broker.canonical_json_bytes(arm_inventory)
        ).hexdigest()
        manifest = {
            "arm_attempt_prefix": "arms/arm-01",
            "arm_slot": "arm-01",
            "authority_scope": "AB16_RESEARCH_ONLY",
            "authorizations": dict(broker.ARM_FALSE_AUTHORIZATIONS),
            "bindings": {},
            "entries": [],
            "inventory": {
                "schema_version": broker.ROOT_INVENTORY_SCHEMA,
                "arm_expected_path_types_sha256": (
                    arm_inventory_sha256
                ),
            },
            "schema_version": (
                "noncert-cuts-ab16-organic-attempt-artifact-manifest-v1"
            ),
            "status": "CLOSED_NO_GLOBAL_AUTHORITY",
            "terminal_self_exclusion": {
                "manifest_contains_own_sha256": False,
                "manifest_contains_own_size": False,
                "manifest_path": "attempt-artifact-manifest.json",
                "manifest_path_excluded_from_entries": True,
            },
        }
        raw = broker.canonical_json_bytes(manifest)
        descriptor = helper.create_memfd("ab16-arm-seal-test")
        assert os.pwrite(descriptor, raw, 0) == len(raw)
        os.fsync(descriptor)
        assert (
            helper.install_final_seals(descriptor)
            == helper.final_seal_mask
        )
        sealed = supervisor.publish_arm_manifest_and_seal(
            {
                "arm_allocation_identity": allocation[
                    "allocation_identity"
                ],
                "arm_attempt_prefix": "arms/arm-01",
                "arm_slot": "arm-01",
                "expected_path_types_before": (
                    expected_path_types_before
                ),
                "manifest_expected_sha256": hashlib.sha256(
                    raw
                ).hexdigest(),
                "manifest_maximum_bytes": 64 * 1024,
                "manifest_size_bytes": len(raw),
                "replay_maximum_bytes": 64 * 1024,
                "consumption_maximum_bytes": 64 * 1024,
                "terminal_maximum_bytes": 64 * 1024,
            },
            descriptor=descriptor,
        )
        terminal = sealed.record["result"]["terminal"]
        assert terminal["status"] == "SEAL_DURABLE_PENDING_ACK"
        assert terminal["allocation_state"] == "SEALED_PENDING_ACK"
        intent_path = (
            tmp_path
            / "formal-persistent"
            / sealed.record["journal"]["path"]
        )
        intent = json.loads(intent_path.read_bytes())
        assert intent["action"] == "PUBLISH_ARM_MANIFEST_AND_SEAL"
        assert intent["result"]["state"] == "SEALING"
        with pytest.raises(
            broker.BrokerProtocolError,
            match="PRIOR_RESPONSE_UNACKNOWLEDGED",
        ):
            supervisor.request("STATUS", {})
        accepted = supervisor.accept_prior_arm_seal_response(
            continuation="formal-finalize",
            successor_arm_slot=None,
        )
        assert accepted.record["result"]["state"] == (
            "PRIOR_RESPONSE_ACCEPTED"
        )
        accepted_path = (
            tmp_path
            / "formal-persistent"
            / accepted.record["journal"]["path"]
        )
        accepted_event = json.loads(accepted_path.read_bytes())
        assert accepted_event["action"] == "PRIOR_RESPONSE_ACCEPTED"
        assert accepted_event["result"] == _journal_result_projection(
            accepted.record["result"]
        )
        accepted_identity = {
            "path": str(accepted_path),
            "sha256": accepted.record["journal"]["sha256"],
            "size_bytes": accepted.record["journal"]["size_bytes"],
        }
        os.close(descriptor)
        descriptor = -1
        replay_raw = broker.canonical_json_bytes(
            {"status": "REPLAY_ACCEPTED_NO_GLOBAL_AUTHORITY"}
        )
        descriptor = helper.create_memfd("ab16-arm-replay-test")
        assert os.pwrite(descriptor, replay_raw, 0) == len(replay_raw)
        os.fsync(descriptor)
        assert (
            helper.install_final_seals(descriptor)
            == helper.final_seal_mask
        )
        replay = supervisor.publish_accepted_arm_replay(
            {
                "allocation_identity": allocation[
                    "allocation_identity"
                ],
                "arm_slot": "arm-01",
                "expected_sha256": hashlib.sha256(
                    replay_raw
                ).hexdigest(),
                "maximum_bytes": 64 * 1024,
                "prerequisite_identity": None,
                "prior_response_accepted_identity": accepted_identity,
                "relative_path": (
                    "replays/arm-attempt-roots/arm-01.json"
                ),
                "size_bytes": len(replay_raw),
            },
            descriptor=descriptor,
        )
        replay_identity = replay.record["result"][
            "publication_identity"
        ]
        os.close(descriptor)
        descriptor = -1
        consumption_raw = broker.canonical_json_bytes(
            {"outcome": "CREDIBLE_TERMINAL"}
        )
        descriptor = helper.create_memfd("ab16-arm-consumption-test")
        assert os.pwrite(descriptor, consumption_raw, 0) == len(
            consumption_raw
        )
        os.fsync(descriptor)
        assert (
            helper.install_final_seals(descriptor)
            == helper.final_seal_mask
        )
        consumed = supervisor.publish_arm_consumption(
            {
                "allocation_identity": allocation[
                    "allocation_identity"
                ],
                "arm_slot": "arm-01",
                "expected_sha256": hashlib.sha256(
                    consumption_raw
                ).hexdigest(),
                "maximum_bytes": 64 * 1024,
                "prerequisite_identity": replay_identity,
                "prior_response_accepted_identity": accepted_identity,
                "relative_path": (
                    "prospective/consumptions/arm-01.json"
                ),
                "size_bytes": len(consumption_raw),
            },
            descriptor=descriptor,
        )
        assert consumed.record["result"]["state"] == "ARM_CLOSED"
        status = supervisor.request("STATUS", {}).record["result"]
        assert status["contract"]["arms"]["arm-01"][
            "allocation_state"
        ] == "CLOSED"
        journals = sorted(
            (
                tmp_path
                / "formal-persistent/channels/budget-journal"
            ).glob("segment-*.bin")
        )
        assert len(journals) == 5
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            supervisor.close()
        except BaseException:
            pass
        if not process._waited:  # noqa: SLF001
            os.kill(process.pid, signal.SIGKILL)
            assert process.wait() == 128 + signal.SIGKILL
        process.close()


def test_broker_death_allows_only_strict_once_consumed_incomplete(
    tmp_path: Path,
) -> None:
    before = _fd_count()
    process = _spawn_broker(tmp_path)
    recovered: recovery.RecoveryProcess | None = None
    recovery_result: dict[str, object] | None = None
    try:
        recovery_result, descriptors = _prepare_recovery(process)
        lock_extent = recovery_result["lock_extent"]
        lock_path = (
            tmp_path
            / "formal"
            / str(lock_extent["parent_path"])
            / str(lock_extent["staging_name"])
        )
        competing = os.open(lock_path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(competing)

        recovered = recovery.spawn_recovery_for_test(
            broker_process=process,
            prepared_result=recovery_result,
            descriptors=descriptors,
        )
        _kill_broker(process)
        assert recovered.wait() == 0
        terminal = tmp_path / "formal/closeout/formal-consumed-incomplete.json"
        terminal_record = json.loads(terminal.read_bytes())
        assert terminal_record["schema_version"] == recovery.TAKEOVER_CLOSEOUT_SCHEMA
        assert terminal_record["consumption_state"] == budget.FORMAL_CONSUMED_INCOMPLETE
        assert terminal_record["reason"].endswith("(before-terminal-request)")

        lock_descriptor = os.open(lock_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            with pytest.raises(broker.BrokerProtocolError) as duplicate:
                broker.consume_once_extent(
                    lock_extent,
                    descriptor=lock_descriptor,
                    record={"state": "DUPLICATE_TAKEOVER"},
                )
            assert duplicate.value.code == "ONCE_LOCK_CONSUMED"
        finally:
            os.close(lock_descriptor)
    finally:
        if recovered is not None:
            _wait_and_close_recovery(recovered, expected={0, 2})
        _wait_and_close_broker(process, expected={0, 2, 128 + signal.SIGKILL})
    assert _fd_count() == before


def test_disarm_ack_control_loss_then_broker_death_forces_takeover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    process = _spawn_broker(tmp_path)
    recovered: recovery.RecoveryProcess | None = None
    recovery_result: dict[str, object] | None = None
    helper_fd = -1
    try:
        recovery_result, descriptors = _prepare_recovery(process)
        helper, helper_fd = _native_helper()
        package_gate = _PackageRoleGate()
        recovered = recovery.spawn_persistent_recovery(
            broker_process=process,
            prepared_result=recovery_result,
            descriptors=descriptors,
            package_authorization=package_gate,
            native_helper=helper,
        )
        assert package_gate.calls == [recovery.PACKAGE_ROLE]
        real_send_frame = broker.send_frame
        send_count = 0

        def lose_disarm_ack(
            connection: socket.socket,
            record: Mapping[str, object],
            *,
            descriptors: tuple[int, ...] = (),
        ) -> None:
            nonlocal send_count
            send_count += 1
            if send_count == 2:
                connection.close()
                raise OSError("deterministic DISARM acknowledgement loss")
            real_send_frame(
                connection,
                record,
                descriptors=descriptors,
            )

        monkeypatch.setattr(broker, "send_frame", lose_disarm_ack)
        intent = {
            "schema_version": recovery.DISARM_INTENT_SCHEMA,
            "state": "FINAL_TERMINAL_JOINED",
        }
        with pytest.raises(OSError, match="acknowledgement loss"):
            recovered.terminal(
                "DISARM",
                {
                    "disarm_intent_sha256": (
                        recovery.disarm_intent_sha256(intent)
                    ),
                },
            )
        assert send_count == 2
        with pytest.raises(recovery.RecoveryProtocolError) as duplicate:
            recovered.terminal(
                "DISARM",
                {
                    "disarm_intent_sha256": (
                        recovery.disarm_intent_sha256(intent)
                    ),
                },
            )
        assert duplicate.value.code == "TERMINAL_ALREADY_ATTEMPTED"
        assert send_count == 2
        assert not (
            tmp_path
            / "formal/closeout/formal-consumed-incomplete.json"
        ).exists()
        lock_extent = recovery_result["lock_extent"]
        lock_path = (
            tmp_path
            / "formal"
            / str(lock_extent["parent_path"])
            / str(lock_extent["staging_name"])
        )
        retained_lock = os.open(
            lock_path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(
                    retained_lock,
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
        finally:
            os.close(retained_lock)
        closeout_extent = recovery_result["closeout_extent"]
        closeout_staging = (
            tmp_path
            / "formal"
            / str(closeout_extent["parent_path"])
            / str(closeout_extent["staging_name"])
        )
        assert stat.S_IMODE(closeout_staging.stat().st_mode) == 0o600
        assert closeout_staging.stat().st_size == int(
            closeout_extent["maximum_bytes"]
        )

        _kill_broker(process)
        assert recovered.wait() == 0
        terminal = (
            tmp_path
            / "formal/closeout/formal-consumed-incomplete.json"
        )
        terminal_record = json.loads(terminal.read_bytes())
        assert terminal_record["schema_version"] == (
            recovery.TAKEOVER_CLOSEOUT_SCHEMA
        )
        assert terminal_record["consumption_state"] == (
            budget.FORMAL_CONSUMED_INCOMPLETE
        )
        assert terminal_record["reason"].endswith(
            "(after-disarm-prepare)"
        )

        lock_descriptor = os.open(
            lock_path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            fcntl.flock(
                lock_descriptor,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
            with pytest.raises(broker.BrokerProtocolError) as duplicate:
                broker.consume_once_extent(
                    lock_extent,
                    descriptor=lock_descriptor,
                    record={"state": "DUPLICATE_TAKEOVER"},
                )
            assert duplicate.value.code == "ONCE_LOCK_CONSUMED"
        finally:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
            os.close(lock_descriptor)
    finally:
        if recovered is not None:
            _wait_and_close_recovery(recovered, expected={0, 2})
        _wait_and_close_broker(
            process,
            expected={0, 2, 128 + signal.SIGKILL},
        )
        if helper_fd >= 0:
            os.close(helper_fd)
    assert _fd_count() == before


def test_completed_disarm_seals_unused_extent_without_takeover(
    tmp_path: Path,
) -> None:
    before = _fd_count()
    process = _spawn_broker(tmp_path)
    recovered: recovery.RecoveryProcess | None = None
    try:
        recovery_result, descriptors = _prepare_recovery(process)
        recovered = recovery.spawn_recovery_for_test(
            broker_process=process,
            prepared_result=recovery_result,
            descriptors=descriptors,
        )
        result = _disarm(recovered)
        assert result["state"] == "DISARMED_WITHOUT_TAKEOVER"
        unused_identity = result["unused_closeout_identity"]
        unused_path = tmp_path / "formal" / str(unused_identity["path"])
        assert json.loads(unused_path.read_bytes())["state"] == (
            "UNUSED_CLOSEOUT_SEALED"
        )
        assert not (
            tmp_path
            / "formal/closeout/formal-consumed-incomplete.json"
        ).exists()

        _kill_broker(process)
        assert json.loads(unused_path.read_bytes())["state"] == (
            "UNUSED_CLOSEOUT_SEALED"
        )
        assert not (
            tmp_path
            / "formal/closeout/formal-consumed-incomplete.json"
        ).exists()
    finally:
        if recovered is not None:
            _wait_and_close_recovery(recovered, expected={0, 2})
        _wait_and_close_broker(
            process,
            expected={0, 2, 128 + signal.SIGKILL},
        )
    assert _fd_count() == before


def test_package_recovery_closes_extra_fd_and_preserves_unknown_sibling(
    tmp_path: Path,
) -> None:
    before = _fd_count()
    process = _spawn_broker(tmp_path)
    recovered: recovery.RecoveryProcess | None = None
    helper_fd = -1
    extra_fd = -1
    try:
        recovery_result, descriptors = _prepare_recovery(process)
        extra_path = tmp_path / "ambient-writable.bin"
        extra_fd = os.open(
            extra_path,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
        )
        extra_identity = os.fstat(extra_fd)
        helper, helper_fd = _native_helper()
        package_gate = _PackageRoleGate()
        recovered = recovery.spawn_persistent_recovery(
            broker_process=process,
            prepared_result=recovery_result,
            descriptors=descriptors,
            package_authorization=package_gate,
            native_helper=helper,
        )
        assert package_gate.calls == [recovery.PACKAGE_ROLE]

        retained: list[os.stat_result] = []
        for name in os.listdir(f"/proc/{recovered.pid}/fd"):
            if not name.isdecimal():
                continue
            try:
                retained.append(
                    os.stat(
                        f"/proc/{recovered.pid}/fd/{name}",
                        follow_symlinks=True,
                    )
                )
            except FileNotFoundError:
                continue
        assert len(retained) == 5
        assert all(
            (observed.st_dev, observed.st_ino)
            != (extra_identity.st_dev, extra_identity.st_ino)
            for observed in retained
        )

        unknown = tmp_path / "formal/closeout/unknown-retained.bin"
        unknown.write_bytes(b"must-not-be-touched")
        unknown.chmod(0o444)
        _kill_broker(process)
        assert recovered.wait() == 0
        assert unknown.read_bytes() == b"must-not-be-touched"
        assert (
            tmp_path
            / "formal/closeout/formal-consumed-incomplete.json"
        ).exists()
    finally:
        if recovered is not None:
            _wait_and_close_recovery(recovered, expected={0, 2})
        _wait_and_close_broker(
            process,
            expected={0, 2, 128 + signal.SIGKILL},
        )
        if extra_fd >= 0:
            os.close(extra_fd)
        if helper_fd >= 0:
            os.close(helper_fd)
    assert _fd_count() == before


def test_recovery_rejects_nonfixed_closeout_target_before_fork(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _spawn_broker(tmp_path)
    descriptors: tuple[int, ...] = ()
    try:
        recovery_result, descriptors = _prepare_recovery(process)
        recovery_result["closeout_extent"] = {
            **dict(recovery_result["closeout_extent"]),
            "target_name": "attacker-selected.json",
        }
        monkeypatch.setattr(
            recovery.os,
            "fork",
            lambda: (_ for _ in ()).throw(
                AssertionError("purpose validation must precede fork")
            ),
        )
        with pytest.raises(recovery.RecoveryProtocolError) as blocked:
            recovery.spawn_recovery_for_test(
                broker_process=process,
                prepared_result=recovery_result,
                descriptors=descriptors,
            )
        assert blocked.value.code == "RECOVERY_EXTENT_PURPOSE_DRIFT"
        assert not (
            tmp_path / "formal/closeout/attacker-selected.json"
        ).exists()
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
        _kill_broker(process)
        _wait_and_close_broker(
            process,
            expected={128 + signal.SIGKILL},
        )


def test_recovery_takeover_preserves_unknown_canonical_target(
    tmp_path: Path,
) -> None:
    before = _fd_count()
    process = _spawn_broker(tmp_path)
    recovered: recovery.RecoveryProcess | None = None
    try:
        recovery_result, descriptors = _prepare_recovery(process)
        recovered = recovery.spawn_recovery_for_test(
            broker_process=process,
            prepared_result=recovery_result,
            descriptors=descriptors,
        )
        canonical = (
            tmp_path
            / "formal/closeout/formal-consumed-incomplete.json"
        )
        canonical.write_bytes(b"unknown-canonical-occupant")
        canonical.chmod(0o444)
        _kill_broker(process)
        assert recovered.wait() == 2
        assert canonical.read_bytes() == b"unknown-canonical-occupant"
        staging_name = str(
            recovery_result["closeout_extent"]["staging_name"]
        )
        staging = tmp_path / "formal/closeout" / staging_name
        retained = json.loads(staging.read_bytes())
        assert retained["schema_version"] == (
            recovery.TAKEOVER_CLOSEOUT_SCHEMA
        )
        assert retained["consumption_state"] == (
            budget.FORMAL_CONSUMED_INCOMPLETE
        )
    finally:
        if recovered is not None:
            _wait_and_close_recovery(recovered, expected={0, 2})
        _wait_and_close_broker(
            process,
            expected={0, 2, 128 + signal.SIGKILL},
        )
    assert _fd_count() == before


def test_package_pinned_recovery_takes_over_after_persistent_broker_sigkill(
    tmp_path: Path,
) -> None:
    before = _fd_count()
    owner_nonce = "7" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    package_gate = _PackageRoleGate()
    native_authorization = _NativeHelperAuthorization(
        helper,
        helper_fd,
    )
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=package_gate,
        native_helper_authorization=native_authorization,
        **_persistent_spawn_bindings(
            contract_identity=contract_identity,
            failure_path=failure_path,
            owner_nonce=owner_nonce,
        ),
        formal_directories=(
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
        ),
    )
    admin: broker.BrokerSessionClient | None = None
    recovery_pidfd = -1
    try:
        admin = process.connect_bootstrap_admin()
        observation = dict(
            admin.request("PREPARE_RECOVERY", {}).record["result"]
        )
        recovery_actor = observation["actor"]
        assert type(recovery_actor) is dict
        recovery_pid = int(recovery_actor["pid"])
        recovery_pidfd, _recovery_pidfd_method = broker.open_pidfd(
            recovery_pid
        )
        assert observation["role"] == recovery.PACKAGE_ROLE
        assert package_gate.calls == [
            broker.PACKAGE_ROLE,
        ]
        admin.close()
        admin = None

        os.kill(process.pid, signal.SIGKILL)
        assert process.wait() == 128 + signal.SIGKILL
        poller = select.poll()
        poller.register(recovery_pidfd, select.POLLIN | select.POLLHUP)
        assert poller.poll(5000)

        terminal = (
            tmp_path
            / "formal-persistent/closeout/formal-consumed-incomplete.json"
        )
        terminal_record = json.loads(terminal.read_bytes())
        assert terminal_record["schema_version"] == (
            recovery.TAKEOVER_CLOSEOUT_SCHEMA
        )
        assert terminal_record["consumption_state"] == (
            budget.FORMAL_CONSUMED_INCOMPLETE
        )
        assert terminal_record["broker_actor"] == process.actor
        assert terminal_record["recovery_actor"] == recovery_actor

        lock_members = list(
            (tmp_path / "formal-persistent/locks").iterdir()
        )
        assert len(lock_members) == 2
        recovery_locks: list[Path] = []
        for path in lock_members:
            try:
                record = json.loads(path.read_bytes())
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if (
                record.get("schema_version")
                == recovery.LOCK_CONSUMPTION_SCHEMA
            ):
                recovery_locks.append(path)
        assert len(recovery_locks) == 1
        lock_descriptor = os.open(
            recovery_locks[0],
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            fcntl.flock(
                lock_descriptor,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
            assert stat.S_IMODE(os.fstat(lock_descriptor).st_mode) == 0o444
        finally:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
            os.close(lock_descriptor)
    finally:
        if admin is not None:
            admin.close()
        if not process._waited:  # noqa: SLF001
            try:
                os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        process.close()
        if recovery_pidfd >= 0:
            os.close(recovery_pidfd)
    assert _fd_count() == before


def test_markerless_recovery_request_fails_without_publishing_closeout(tmp_path: Path) -> None:
    process = _spawn_broker(tmp_path)
    recovered: recovery.RecoveryProcess | None = None
    try:
        recovery_result, descriptors = _prepare_recovery(process)
        recovered = recovery.spawn_recovery_for_test(
            broker_process=process,
            prepared_result=recovery_result,
            descriptors=descriptors,
        )
        broker.send_frame(
            recovered.connection,
            {
                "schema_version": recovery.REQUEST_SCHEMA,
                "action": "TAKEOVER",
                "nonce": recovered.nonce,
                "payload": {
                    "consumption_state": budget.FORMAL_MARKERLESS_INCOMPLETE,
                    "reason": "formal marker absent",
                },
                "sequence": 1,
            },
        )
        response = broker.receive_frame(recovered.connection)
        assert response.record["status"] == "FAIL_CLOSED"
        assert response.record["code"] == "RECOVERY_STATE_FORBIDDEN"
        assert recovered.wait() == 2
        assert not (tmp_path / "formal/closeout/formal-consumed-incomplete.json").exists()
        _kill_broker(process)
    finally:
        if recovered is not None:
            _wait_and_close_recovery(recovered, expected={2})
        _wait_and_close_broker(
            process,
            expected={0, 2, 128 + signal.SIGKILL},
        )


def _successful_preclosure(
    tmp_path: Path,
    *,
    additional_allowed_processes: tuple[Mapping[str, int], ...] = (),
) -> tuple[
    broker.BrokerProcess,
    recovery.RecoveryProcess,
    dict[str, object],
    dict[str, object],
    tuple[int, ...],
    dict[str, object],
]:
    same_uid_baseline = _zero_authority_closure_process_baseline(
        allowed_processes=(
            {
                "pid": os.getpid(),
                "starttime": broker.process_starttime(os.getpid()),
            },
            *additional_allowed_processes,
        ),
    )
    process = _spawn_broker(tmp_path)
    recovery_result, recovery_descriptors = _prepare_recovery(process)
    recovered = recovery.spawn_recovery_for_test(
        broker_process=process,
        prepared_result=recovery_result,
        descriptors=recovery_descriptors,
    )
    closure_result, closure_descriptors = _prepare_closure(process)
    contract = dict(process.request("STATUS", {}).record["result"]["contract"])
    disarm = _disarm(recovered)
    root_inventory = _normal_exit(process)
    return (
        process,
        recovered,
        recovery_result,
        closure_result,
        closure_descriptors,
        {
            "contract": contract,
            "disarm": disarm,
            "root_inventory": root_inventory,
            "same_uid_process_baseline": same_uid_baseline,
            "same_uid_process_baseline_sha256": (
                resource_admission._canonical_sha256(  # noqa: SLF001
                    same_uid_baseline
                )
            ),
        },
    )


def _zero_authority_closure_process_baseline(
    *,
    allowed_processes: tuple[Mapping[str, int], ...],
) -> dict[str, object]:
    """Keep closure tests independent of the live launch-admission verdict.

    The production scanner still identifies and rejects competing or
    unclassifiable processes.  These zero-authority tests exercise the later
    identity/root-writer join, so they snapshot stable PID/starttime identities
    directly without making the fixture depend on host launch eligibility.
    An empty cmdline is retained as the SHA-256 of empty bytes; it grants no
    authority and may only occur in this test-only baseline.
    """

    allowed = resource_admission._validate_allowed_process_identities(  # noqa: SLF001
        allowed_processes
    )
    allowed_by_identity = {
        (item["pid"], item["starttime"]): item for item in allowed
    }
    observed_allowed: set[tuple[int, int]] = set()
    ancestors = resource_admission._ancestor_pids(Path("/proc"))  # noqa: SLF001
    processes: list[dict[str, object]] = []
    for item in tuple(Path("/proc").iterdir()):
        if not item.name.isdecimal():
            continue
        pid = int(item.name)
        observation = resource_admission._process_observation(  # noqa: SLF001
            item,
            pid=pid,
        )
        if observation is None or observation["uid"] != os.getuid():
            continue
        replay = resource_admission._process_observation(  # noqa: SLF001
            item,
            pid=pid,
        )
        if replay is None or replay != observation:
            continue
        identity = (pid, int(observation["starttime"]))
        if identity in allowed_by_identity:
            classification = "ALLOWED_CAMPAIGN_ACTOR"
            observed_allowed.add(identity)
        elif pid in ancestors:
            classification = "RESOURCE_GATE_ANCESTOR"
        else:
            classification = "NONCONFLICTING_AMBIENT"
        command = str(observation["command"])
        processes.append(
            {
                "classification": classification,
                "command_sha256": hashlib.sha256(
                    command.encode("utf-8")
                ).hexdigest(),
                "pid": pid,
                "starttime": identity[1],
            }
        )
    assert observed_allowed == set(allowed_by_identity)
    processes.sort(key=lambda item: (item["pid"], item["starttime"]))
    return resource_admission._same_uid_process_baseline(  # noqa: SLF001
        processes,
        mode=resource_admission.SAME_UID_BASELINE_LIVE_MODE,
    )


def _model_isolated_host_for_writer_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exclude only processes present before the controlled test actors exist."""

    preexisting_same_uid: set[int] = set()
    for name in os.listdir("/proc"):
        if not name.isdecimal():
            continue
        try:
            if os.stat(f"/proc/{name}").st_uid == os.getuid():
                preexisting_same_uid.add(int(name))
        except FileNotFoundError:
            continue
    real_scan = closure.writable_root_descriptors

    def isolated_scan(
        root: Path | str,
        *,
        excluded_pids: frozenset[int] = frozenset(),
    ) -> list[dict[str, object]]:
        return real_scan(
            root,
            excluded_pids=excluded_pids | frozenset(preexisting_same_uid),
        )

    monkeypatch.setattr(closure, "writable_root_descriptors", isolated_scan)


def _closure_payload(
    evidence: Mapping[str, object],
    *,
    terminal_join_sha256: str,
) -> dict[str, object]:
    return {
        "budget_contract": evidence["contract"],
        "disarm_observation": evidence["disarm"],
        "root_inventory": evidence["root_inventory"],
        "same_uid_process_baseline": evidence[
            "same_uid_process_baseline"
        ],
        "same_uid_process_baseline_sha256": evidence[
            "same_uid_process_baseline_sha256"
        ],
        "terminal_join_sha256": terminal_join_sha256,
    }


def _final_release_actor_record(pid: int) -> dict[str, object]:
    return {
        "schema_version": closure.FINAL_RELEASE_ACTOR_SCHEMA,
        **broker.process_identity(pid),
    }


def _closure_final_release_handoffs(
    actor: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    final_handoff = {
        "actor": dict(actor),
        "alternate_replay_source_identity": {
            "sha256": "d" * 64,
            "size_bytes": 1,
        },
        "broker_actor": {
            "schema_version": broker.ACTOR_SCHEMA,
            **broker.process_identity(),
        },
        "control_descriptor_identity": {
            "device": 1,
            "inode": 2,
            "mode_octal": "0777",
            "size_bytes": 0,
            "uid": os.getuid(),
        },
        "formal_root_path": "/formal-root",
        "nonce": "a" * 64,
        "pidfd_method": "python-os.pidfd_open",
        "prepared_release_identity": {
            "sha256": "e" * 64,
            "size_bytes": 1,
        },
        "primary_replay_source_identity": {
            "sha256": "f" * 64,
            "size_bytes": 1,
        },
        "ready_handshake_identity": {
            "sha256": "b" * 64,
            "size_bytes": 1,
        },
        "release_root_path": "/outside-final-release",
        "role": final_release_actor.PACKAGE_ROLE,
        "role_source_identity": {
            "sha256": "c" * 64,
            "size_bytes": 1,
        },
        "schema_version": final_release_actor.HANDOFF_SCHEMA,
    }
    closure_handoff = {
        "final_release_actor": dict(actor),
        "final_release_handoff_identity": (
            formal_campaign._canonical_message_identity(  # noqa: SLF001
                final_handoff
            )
        ),
        "final_release_pidfd_method": "python-os.pidfd_open",
    }
    return closure_handoff, final_handoff


def test_closure_final_release_authority_join_binds_full_handoff() -> None:
    actor = _final_release_actor_record(os.getpid())
    closure_handoff, final_handoff = (
        _closure_final_release_handoffs(actor)
    )
    pidfd, method = broker.open_pidfd(os.getpid())
    final_handoff["pidfd_method"] = method
    closure_handoff["final_release_pidfd_method"] = method
    closure_handoff["final_release_handoff_identity"] = (
        formal_campaign._canonical_message_identity(  # noqa: SLF001
            final_handoff
        )
    )
    try:
        assert formal_campaign._validate_closure_final_release_join(  # noqa: SLF001
            closure_handoff,
            final_handoff,
            final_release_pidfd=pidfd,
        ) == {
            "final_release_actor": actor,
            "final_release_handoff_identity": (
                formal_campaign._canonical_message_identity(  # noqa: SLF001
                    final_handoff
                )
            ),
            "final_release_pidfd_method": method,
            "state": "FINAL_RELEASE_ACTOR_PIDFD_JOINED",
        }
    finally:
        os.close(pidfd)


@pytest.mark.parametrize(
    "mutation",
    ("unbound", "wrong-schema", "wrong-starttime", "substituted"),
)
def test_closure_final_release_authority_join_rejects_drift(
    mutation: str,
) -> None:
    actor = _final_release_actor_record(os.getpid())
    closure_handoff, final_handoff = (
        _closure_final_release_handoffs(actor)
    )
    if mutation == "unbound":
        closure_handoff.pop("final_release_actor")
    elif mutation == "wrong-schema":
        drifted = {
            **actor,
            "schema_version": "wrong-final-release-actor-schema",
        }
        closure_handoff, final_handoff = (
            _closure_final_release_handoffs(drifted)
        )
    elif mutation == "wrong-starttime":
        drifted = {
            **actor,
            "pid_starttime": cast(int, actor["pid_starttime"]) + 1,
        }
        closure_handoff, final_handoff = (
            _closure_final_release_handoffs(drifted)
        )
    else:
        substituted = {
            "schema_version": closure.FINAL_RELEASE_ACTOR_SCHEMA,
            **broker.process_identity(os.getppid()),
        }
        closure_handoff["final_release_actor"] = substituted
    pidfd, _method = broker.open_pidfd(os.getpid())
    try:
        with pytest.raises(
            formal_campaign.IrreversibleFormalFailure,
            match="closure/final-release actor",
        ):
            formal_campaign._validate_closure_final_release_join(  # noqa: SLF001
                closure_handoff,
                final_handoff,
                final_release_pidfd=pidfd,
            )
    finally:
        os.close(pidfd)


def test_closure_final_release_authority_join_rejects_dead_actor() -> None:
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    pid = os.fork()
    if pid == 0:
        os.close(release_write)
        os.read(release_read, 1)
        os.close(release_read)
        os._exit(0)
    os.close(release_read)
    actor = _final_release_actor_record(pid)
    pidfd, _method = broker.open_pidfd(pid)
    closure_handoff, final_handoff = (
        _closure_final_release_handoffs(actor)
    )
    os.close(release_write)
    assert os.waitpid(pid, 0) == (pid, 0)
    try:
        with pytest.raises(
            formal_campaign.IrreversibleFormalFailure,
            match="closure/final-release actor",
        ):
            formal_campaign._validate_closure_final_release_join(  # noqa: SLF001
                closure_handoff,
                final_handoff,
                final_release_pidfd=pidfd,
            )
    finally:
        os.close(pidfd)


def _spawn_final_release_holder(
    *,
    writable_path: Path | None = None,
) -> tuple[int, int, str, dict[str, object], int]:
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
    pid = os.fork()
    if pid == 0:
        os.close(release_write)
        os.close(ready_read)
        writable_fd = -1
        try:
            if writable_path is not None:
                writable_fd = os.open(
                    writable_path,
                    os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
                )
            broker.close_unlisted_descriptors(
                {
                    release_read,
                    ready_write,
                    *(() if writable_fd < 0 else (writable_fd,)),
                }
            )
            os.write(ready_write, b"1")
            os.read(release_read, 1)
        finally:
            if writable_fd >= 0:
                os.close(writable_fd)
            os.close(release_read)
            os.close(ready_write)
        os._exit(0)
    os.close(release_read)
    os.close(ready_write)
    assert os.read(ready_read, 1) == b"1"
    os.close(ready_read)
    pidfd, method = broker.open_pidfd(pid)
    return (
        pid,
        pidfd,
        method,
        _final_release_actor_record(pid),
        release_write,
    )


def test_closure_rejects_bound_final_release_actor_with_root_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _model_isolated_host_for_writer_scan(monkeypatch)
    (
        process,
        recovered,
        recovery_result,
        closure_result,
        closure_descriptors,
        evidence,
    ) = _successful_preclosure(tmp_path)
    writable_stage = (
        tmp_path
        / "formal"
        / str(closure_result["extents"][0]["parent_path"])
        / str(closure_result["extents"][0]["staging_name"])
    )
    (
        holder_pid,
        holder_pidfd,
        holder_pidfd_method,
        holder_actor,
        holder_release,
    ) = (
        _spawn_final_release_holder(writable_path=writable_stage)
    )
    closer: closure.ClosureProcess | None = None
    try:
        closer = closure.spawn_closure_for_test(
            root=tmp_path / "formal",
            broker_actor=process.actor,
            broker_pidfd=process.pidfd,
            recovery_actor=recovered.actor,
            recovery_pidfd=recovered.pidfd,
            recovery_lock_extent=recovery_result["lock_extent"],
            prepared_result=closure_result,
            descriptors=closure_descriptors,
            final_release_actor=holder_actor,
            final_release_pidfd=holder_pidfd,
            final_release_pidfd_method=holder_pidfd_method,
            final_release_handoff_identity={
                "sha256": "d" * 64,
                "size_bytes": 1,
            },
        )
        with pytest.raises(closure.ClosureProtocolError) as blocked:
            closer.close_root(
                _closure_payload(
                    evidence,
                    terminal_join_sha256="e" * 64,
                )
            )
        assert blocked.value.code == "FOREIGN_ROOT_WRITER_RETAINED"
        assert closer.wait() == 2
        assert writable_stage.exists()
        assert not broker.pidfd_reports_exit(holder_pidfd)
    finally:
        if closer is not None:
            _wait_and_close_closure(closer, expected={2})
        os.write(holder_release, b"1")
        os.close(holder_release)
        assert os.waitpid(holder_pid, 0) == (holder_pid, 0)
        os.close(holder_pidfd)
        _wait_and_close_recovery(recovered, expected={0})
        _wait_and_close_broker(process, expected={0})


def test_closure_binds_live_final_release_actor_at_initial_and_final_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _model_isolated_host_for_writer_scan(monkeypatch)
    (
        process,
        recovered,
        recovery_result,
        closure_result,
        closure_descriptors,
        evidence,
    ) = _successful_preclosure(tmp_path)
    (
        holder_pid,
        holder_pidfd,
        holder_pidfd_method,
        holder_actor,
        holder_release,
    ) = _spawn_final_release_holder()
    handoff_identity = {
        "sha256": "d" * 64,
        "size_bytes": 1,
    }
    closer: closure.ClosureProcess | None = None
    try:
        closer = closure.spawn_closure_for_test(
            root=tmp_path / "formal",
            broker_actor=process.actor,
            broker_pidfd=process.pidfd,
            recovery_actor=recovered.actor,
            recovery_pidfd=recovered.pidfd,
            recovery_lock_extent=recovery_result["lock_extent"],
            prepared_result=closure_result,
            descriptors=closure_descriptors,
            final_release_actor=holder_actor,
            final_release_pidfd=holder_pidfd,
            final_release_pidfd_method=holder_pidfd_method,
            final_release_handoff_identity=handoff_identity,
        )
        result = closer.close_root(
            _closure_payload(
                evidence,
                terminal_join_sha256="e" * 64,
            )
        )
        assert result["final_release_binding"] == {
            "actor": holder_actor,
            "handoff_identity": handoff_identity,
            "phase": "FINAL_CLOSURE_SCOPE",
            "pidfd_method": holder_pidfd_method,
            "state": "LIVE_EXACT_FINAL_RELEASE_ACTOR_BOUND",
        }
        assert closer.wait() == 0
        manifest = json.loads(
            (
                tmp_path
                / "formal/formal-closure/formal-manifest.json"
            ).read_bytes()
        )
        assert manifest["writer_capability_closure"][
            "final_release_binding"
        ] == {
            "actor": holder_actor,
            "handoff_identity": handoff_identity,
            "phase": "INITIAL_CLOSURE_SCOPE",
            "pidfd_method": holder_pidfd_method,
            "state": "LIVE_EXACT_FINAL_RELEASE_ACTOR_BOUND",
        }
        assert not broker.pidfd_reports_exit(holder_pidfd)
    finally:
        if closer is not None:
            _wait_and_close_closure(closer, expected={0, 2})
        os.write(holder_release, b"1")
        os.close(holder_release)
        assert os.waitpid(holder_pid, 0) == (holder_pid, 0)
        os.close(holder_pidfd)
        _wait_and_close_recovery(recovered, expected={0})
        _wait_and_close_broker(process, expected={0})


def test_closure_final_release_pidfd_close_failure_is_exact_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = 987_654
    calls = 0

    def fail_close(descriptor: int) -> None:
        nonlocal calls
        assert descriptor == sentinel
        calls += 1
        raise OSError("deterministic final-release pidfd close failure")

    server = object.__new__(closure.ClosureServer)
    server.final_release_pidfd = sentinel
    monkeypatch.setattr(closure.os, "close", fail_close)
    with pytest.raises(closure.ClosureProtocolError) as blocked:
        server._release_final_release_pidfd()  # noqa: SLF001
    assert blocked.value.code == "OWNERSHIP_RELEASE_UNCERTAIN"
    assert server.final_release_pidfd is None
    assert calls == 1
    server._release_final_release_pidfd()  # noqa: SLF001
    assert calls == 1


def test_closure_process_close_attempts_control_and_pidfd_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingConnection:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1
            raise RuntimeError("deterministic closure control close failure")

    sentinel = 987_656
    pidfd_close_count = 0

    def tracked_close(descriptor: int) -> None:
        nonlocal pidfd_close_count
        assert descriptor == sentinel
        pidfd_close_count += 1

    connection = FailingConnection()
    process = closure.ClosureProcess(
        pid=os.getpid(),
        pidfd=sentinel,
        pidfd_method="python-os.pidfd_open",
        connection=cast(object, connection),  # type: ignore[arg-type]
        nonce="a" * 64,
        actor={
            "schema_version": closure.ACTOR_SCHEMA,
            **broker.process_identity(),
        },
    )
    monkeypatch.setattr(closure.os, "close", tracked_close)
    with pytest.raises(closure.ClosureProtocolError) as blocked:
        process.close()
    assert blocked.value.code == "OWNERSHIP_RELEASE_UNCERTAIN"
    assert connection.close_count == 1
    assert pidfd_close_count == 1
    assert process.pidfd == -1
    process.close()
    assert connection.close_count == 1
    assert pidfd_close_count == 1


def test_disarm_broker_exit_then_single_use_manifest_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    _model_isolated_host_for_writer_scan(monkeypatch)
    (
        process,
        recovered,
        recovery_result,
        closure_result,
        closure_descriptors,
        evidence,
    ) = _successful_preclosure(tmp_path)
    closer: closure.ClosureProcess | None = None
    try:
        closer = closure.spawn_closure_for_test(
            root=tmp_path / "formal",
            broker_actor=process.actor,
            broker_pidfd=process.pidfd,
            recovery_actor=recovered.actor,
            recovery_pidfd=recovered.pidfd,
            recovery_lock_extent=recovery_result["lock_extent"],
            prepared_result=closure_result,
            descriptors=closure_descriptors,
        )
        result = closer.close_root(
            _closure_payload(
                evidence,
                terminal_join_sha256=hashlib.sha256(
                    b"terminal-join"
                ).hexdigest(),
            )
        )
        assert result["state"] == "ROOT_CLOSED_NO_WRITERS"
        assert closer.wait() == 0
        manifest_path = tmp_path / "formal/formal-closure/formal-manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        paths = {entry["path"] for entry in manifest["entries"]}
        assert "formal-closure/recovery-disarm-terminal.json" in paths
        assert "formal-closure/budget-terminal.json" in paths
        assert "formal-closure/formal-manifest.json" not in paths
        assert manifest["excluded_terminal_path"] == "formal-closure/formal-manifest.json"
        assert closure.writable_root_descriptors(tmp_path / "formal") == []
    finally:
        if closer is not None:
            _wait_and_close_closure(closer, expected={0, 2})
        _wait_and_close_recovery(recovered, expected={0})
        _wait_and_close_broker(process, expected={0})
    assert _fd_count() == before


def test_closure_rejects_same_uid_baseline_identity_tamper(
    tmp_path: Path,
) -> None:
    (
        process,
        recovered,
        recovery_result,
        closure_result,
        closure_descriptors,
        evidence,
    ) = _successful_preclosure(tmp_path)
    closer: closure.ClosureProcess | None = None
    try:
        closer = closure.spawn_closure_for_test(
            root=tmp_path / "formal",
            broker_actor=process.actor,
            broker_pidfd=process.pidfd,
            recovery_actor=recovered.actor,
            recovery_pidfd=recovered.pidfd,
            recovery_lock_extent=recovery_result["lock_extent"],
            prepared_result=closure_result,
            descriptors=closure_descriptors,
        )
        baseline = evidence["same_uid_process_baseline"]
        assert isinstance(baseline, Mapping)
        forged_baseline = dict(baseline)
        forged_baseline["policy_id"] = "forged-policy"
        forged_evidence = {
            **evidence,
            "same_uid_process_baseline": forged_baseline,
        }
        with pytest.raises(closure.ClosureProtocolError) as blocked:
            closer.close_root(
                _closure_payload(
                    forged_evidence,
                    terminal_join_sha256="d" * 64,
                )
            )
        assert blocked.value.code == "RESOURCE_SAME_UID_BASELINE_INVALID"
        assert closer.wait() == 2
        assert not (
            tmp_path / "formal/formal-closure/formal-manifest.json"
        ).exists()
    finally:
        if closer is not None:
            _wait_and_close_closure(closer, expected={2})
        _wait_and_close_recovery(recovered, expected={0})
        _wait_and_close_broker(process, expected={0})


def test_new_same_uid_writer_consumes_closure_attempt_and_preserves_unknown_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _model_isolated_host_for_writer_scan(monkeypatch)
    (
        process,
        recovered,
        recovery_result,
        closure_result,
        closure_descriptors,
        evidence,
    ) = _successful_preclosure(tmp_path)
    closer: closure.ClosureProcess | None = None
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
    holder_pid: int | None = None
    try:
        closer = closure.spawn_closure_for_test(
            root=tmp_path / "formal",
            broker_actor=process.actor,
            broker_pidfd=process.pidfd,
            recovery_actor=recovered.actor,
            recovery_pidfd=recovered.pidfd,
            recovery_lock_extent=recovery_result["lock_extent"],
            prepared_result=closure_result,
            descriptors=closure_descriptors,
        )
        holder_pid = os.fork()
        if holder_pid == 0:
            os.close(release_write)
            os.close(ready_read)
            descriptor = os.open(
                tmp_path / "formal" / "unknown-writer.bin",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o600,
            )
            os.write(ready_write, b"1")
            os.read(release_read, 1)
            os.close(descriptor)
            os._exit(0)
        os.close(release_read)
        release_read = -1
        os.close(ready_write)
        ready_write = -1
        assert os.read(ready_read, 1) == b"1"
        with pytest.raises(closure.ClosureProtocolError) as blocked:
            closer.close_root(
                _closure_payload(
                    evidence,
                    terminal_join_sha256=hashlib.sha256(
                        b"terminal-join"
                    ).hexdigest(),
                )
            )
        assert blocked.value.code == "RESOURCE_SAME_UID_SCOPE_DRIFT"
        assert closer.wait() == 2
        unknown = tmp_path / "formal/unknown-writer.bin"
        assert unknown.exists()
        assert not (tmp_path / "formal/formal-closure/formal-manifest.json").exists()
        lock_extent = closure_result["lock_extent"]
        lock_path = (
            tmp_path
            / "formal"
            / str(lock_extent["parent_path"])
            / str(lock_extent["staging_name"])
        )
        assert lock_path.stat().st_size < int(lock_extent["maximum_bytes"])
        assert lock_path.read_bytes()
    finally:
        if release_write >= 0:
            try:
                os.write(release_write, b"x")
            except OSError:
                pass
            os.close(release_write)
        if release_read >= 0:
            os.close(release_read)
        if ready_read >= 0:
            os.close(ready_read)
        if ready_write >= 0:
            os.close(ready_write)
        if holder_pid is not None:
            os.waitpid(holder_pid, 0)
        if closer is not None:
            _wait_and_close_closure(closer, expected={2})
        _wait_and_close_recovery(recovered, expected={0})
        _wait_and_close_broker(process, expected={0})


def test_baseline_actor_retaining_writable_root_fd_fails_before_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    _model_isolated_host_for_writer_scan(monkeypatch)
    open_read, open_write = os.pipe2(os.O_CLOEXEC)
    ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    holder_pid = os.fork()
    if holder_pid == 0:
        os.close(open_write)
        os.close(ready_read)
        os.close(release_write)
        try:
            os.read(open_read, 1)
            descriptor = os.open(
                tmp_path / "formal" / "baseline-writer.bin",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o600,
            )
            os.write(ready_write, b"1")
            os.read(release_read, 1)
            os.close(descriptor)
        finally:
            os.close(open_read)
            os.close(ready_write)
            os.close(release_read)
        os._exit(0)

    os.close(open_read)
    open_read = -1
    os.close(ready_write)
    ready_write = -1
    os.close(release_read)
    release_read = -1
    process: broker.PersistentBrokerProcess | None = None
    recovered: recovery.RecoveryProcess | None = None
    closer: closure.ClosureProcess | None = None
    try:
        (
            process,
            recovered,
            recovery_result,
            closure_result,
            closure_descriptors,
            evidence,
        ) = _successful_preclosure(
            tmp_path,
            additional_allowed_processes=(
                {
                    "pid": holder_pid,
                    "starttime": broker.process_starttime(holder_pid),
                },
            ),
        )
        closer = closure.spawn_closure_for_test(
            root=tmp_path / "formal",
            broker_actor=process.actor,
            broker_pidfd=process.pidfd,
            recovery_actor=recovered.actor,
            recovery_pidfd=recovered.pidfd,
            recovery_lock_extent=recovery_result["lock_extent"],
            prepared_result=closure_result,
            descriptors=closure_descriptors,
        )
        os.write(open_write, b"1")
        os.close(open_write)
        open_write = -1
        assert os.read(ready_read, 1) == b"1"
        with pytest.raises(closure.ClosureProtocolError) as blocked:
            closer.close_root(
                _closure_payload(
                    evidence,
                    terminal_join_sha256=hashlib.sha256(
                        b"terminal-join"
                    ).hexdigest(),
                )
            )
        assert blocked.value.code == "FOREIGN_ROOT_WRITER_RETAINED"
        assert closer.wait() == 2
        unknown = tmp_path / "formal/baseline-writer.bin"
        assert unknown.exists()
        assert not (
            tmp_path / "formal/formal-closure/formal-manifest.json"
        ).exists()
    finally:
        if open_write >= 0:
            try:
                os.write(open_write, b"x")
            except OSError:
                pass
            os.close(open_write)
        if ready_read >= 0:
            os.close(ready_read)
        if release_write >= 0:
            try:
                os.write(release_write, b"x")
            except OSError:
                pass
            os.close(release_write)
        if ready_write >= 0:
            os.close(ready_write)
        if release_read >= 0:
            os.close(release_read)
        os.waitpid(holder_pid, 0)
        if closer is not None:
            _wait_and_close_closure(closer, expected={2})
        if recovered is not None:
            _wait_and_close_recovery(recovered, expected={0})
        if process is not None:
            _wait_and_close_broker(process, expected={0})
    assert _fd_count() == before


@pytest.mark.parametrize("inspection_surface", ("pid-fd", "fdinfo"))
def test_new_same_uid_writer_fails_scope_without_global_fd_inspection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inspection_surface: str,
) -> None:
    _model_isolated_host_for_writer_scan(monkeypatch)
    (
        process,
        recovered,
        recovery_result,
        closure_result,
        closure_descriptors,
        evidence,
    ) = _successful_preclosure(tmp_path)
    closer: closure.ClosureProcess | None = None
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
    holder_pid: int | None = None
    try:
        holder_pid = os.fork()
        if holder_pid == 0:
            os.close(release_write)
            os.close(ready_read)
            descriptor = os.open(
                tmp_path / "formal" / "uninspectable-writer.bin",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o600,
            )
            os.write(ready_write, str(descriptor).encode("ascii"))
            os.read(release_read, 1)
            os.close(descriptor)
            os._exit(0)
        os.close(release_read)
        release_read = -1
        os.close(ready_write)
        ready_write = -1
        assert int(os.read(ready_read, 32).decode("ascii")) >= 0

        if inspection_surface == "pid-fd":
            real_listdir = closure.os.listdir
            denied_path = f"/proc/{holder_pid}/fd"

            def guarded_listdir(path: object) -> list[str]:
                if path == denied_path:
                    raise PermissionError("deterministic same-UID fd denial")
                return real_listdir(path)  # type: ignore[arg-type,return-value]

            monkeypatch.setattr(closure.os, "listdir", guarded_listdir)
        else:
            real_read_text = closure.Path.read_text
            denied_parent = Path(f"/proc/{holder_pid}/fdinfo")

            def guarded_read_text(
                path: Path,
                *args: object,
                **kwargs: object,
            ) -> str:
                if path.parent == denied_parent:
                    raise PermissionError("deterministic same-UID fdinfo denial")
                return real_read_text(  # type: ignore[arg-type]
                    path,
                    *args,
                    **kwargs,
                )

            monkeypatch.setattr(closure.Path, "read_text", guarded_read_text)

        closer = closure.spawn_closure_for_test(
            root=tmp_path / "formal",
            broker_actor=process.actor,
            broker_pidfd=process.pidfd,
            recovery_actor=recovered.actor,
            recovery_pidfd=recovered.pidfd,
            recovery_lock_extent=recovery_result["lock_extent"],
            prepared_result=closure_result,
            descriptors=closure_descriptors,
        )
        with pytest.raises(closure.ClosureProtocolError) as blocked:
            closer.close_root(
                _closure_payload(
                    evidence,
                    terminal_join_sha256=hashlib.sha256(
                        b"terminal-join"
                    ).hexdigest(),
                )
            )
        assert blocked.value.code == "RESOURCE_SAME_UID_SCOPE_DRIFT"
        assert closer.wait() == 2
        unknown = tmp_path / "formal/uninspectable-writer.bin"
        assert unknown.exists()
        assert not (
            tmp_path / "formal/formal-closure/formal-manifest.json"
        ).exists()
        lock_extent = closure_result["lock_extent"]
        lock_path = (
            tmp_path
            / "formal"
            / str(lock_extent["parent_path"])
            / str(lock_extent["staging_name"])
        )
        assert stat.S_IMODE(lock_path.stat().st_mode) == 0o444
        assert json.loads(lock_path.read_bytes())["state"] == (
            "CLOSURE_ACTOR_CONSUMED"
        )
    finally:
        if release_write >= 0:
            try:
                os.write(release_write, b"x")
            except OSError:
                pass
            os.close(release_write)
        if release_read >= 0:
            os.close(release_read)
        if ready_read >= 0:
            os.close(ready_read)
        if ready_write >= 0:
            os.close(ready_write)
        if holder_pid is not None:
            os.waitpid(holder_pid, 0)
        if closer is not None:
            _wait_and_close_closure(closer, expected={2})
        _wait_and_close_recovery(recovered, expected={0})
        _wait_and_close_broker(process, expected={0})


@pytest.mark.parametrize("node_kind", ("regular", "directory"))
def test_closed_unknown_root_member_fails_inventory_and_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    node_kind: str,
) -> None:
    _model_isolated_host_for_writer_scan(monkeypatch)
    (
        process,
        recovered,
        recovery_result,
        closure_result,
        closure_descriptors,
        evidence,
    ) = _successful_preclosure(tmp_path)
    unknown = tmp_path / "formal" / f"unknown-{node_kind}"
    if node_kind == "regular":
        unknown.write_bytes(b"unregistered")
        unknown.chmod(0o444)
    else:
        unknown.mkdir(mode=0o700)
    closer: closure.ClosureProcess | None = None
    try:
        closer = closure.spawn_closure_for_test(
            root=tmp_path / "formal",
            broker_actor=process.actor,
            broker_pidfd=process.pidfd,
            recovery_actor=recovered.actor,
            recovery_pidfd=recovered.pidfd,
            recovery_lock_extent=recovery_result["lock_extent"],
            prepared_result=closure_result,
            descriptors=closure_descriptors,
        )
        with pytest.raises(closure.ClosureProtocolError) as blocked:
            closer.close_root(
                _closure_payload(
                    evidence,
                    terminal_join_sha256="e" * 64,
                )
            )
        assert blocked.value.code == "ROOT_INVENTORY_MISMATCH"
        assert closer.wait() == 2
        assert unknown.exists()
        assert not (
            tmp_path / "formal/formal-closure/formal-manifest.json"
        ).exists()
    finally:
        if closer is not None:
            _wait_and_close_closure(closer, expected={2})
        _wait_and_close_recovery(recovered, expected={0})
        _wait_and_close_broker(process, expected={0})


def test_closure_snapshot_rejects_regular_hardlink_and_preserves_both_names(
    tmp_path: Path,
) -> None:
    root = tmp_path / "formal"
    root.mkdir()
    first = root / "first.json"
    second = root / "second.json"
    first.write_bytes(b"retained-evidence")
    os.link(first, second)

    with pytest.raises(
        closure.ClosureProtocolError,
        match="external or duplicate hardlinks",
    ) as caught:
        closure.snapshot_root_entries(root)

    assert caught.value.code == "UNSAFE_ROOT_NODE"
    assert first.read_bytes() == b"retained-evidence"
    assert second.read_bytes() == b"retained-evidence"
    assert first.stat().st_ino == second.stat().st_ino


def test_closure_root_join_rejects_absolute_path_replacement(
    tmp_path: Path,
) -> None:
    root = tmp_path / "formal"
    moved = tmp_path / "formal-moved"
    root.mkdir()
    retained_root_fd = budget._open_absolute_directory_no_symlinks(root)  # noqa: SLF001
    server = object.__new__(closure.ClosureServer)
    server.root = root
    server.root_fd = retained_root_fd
    server.root_identity = budget._path_identity(os.fstat(retained_root_fd))  # noqa: SLF001
    try:
        root.rename(moved)
        root.mkdir()
        (root / "unknown-replacement").write_bytes(b"preserve")

        with pytest.raises(closure.ClosureProtocolError) as caught:
            server._require_root_join()  # noqa: SLF001

        assert caught.value.code == "ROOT_PATH_DRIFT"
        assert (root / "unknown-replacement").read_bytes() == b"preserve"
        assert moved.is_dir()
    finally:
        os.close(retained_root_fd)


def test_prepare_extent_anchors_root_when_absolute_ancestor_is_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "formal"
    moved = tmp_path / "formal-retained"
    external = tmp_path / "external"
    account = budget.FormalBudgetBroker.create(
        root,
        category_limits=ROOT_LIMITS,
        owner_nonce="prepared-extent-owner",
    )
    account.register_directory("closeout")
    original_register = budget.FormalBudgetBroker.register_directory
    swapped = False
    external.mkdir()
    (external / "closeout").mkdir()
    sentinel = external / "closeout/unknown"
    sentinel.write_bytes(b"must-remain-unchanged")
    sentinel_before = os.stat(sentinel, follow_symlinks=False)

    def register_then_replace(
        target: budget.FormalBudgetBroker,
        relative_path: str,
    ) -> None:
        nonlocal swapped
        original_register(target, relative_path)
        if target is account and not swapped:
            swapped = True
            root.rename(moved)
            root.symlink_to(external, target_is_directory=True)

    monkeypatch.setattr(
        budget.FormalBudgetBroker,
        "register_directory",
        register_then_replace,
    )
    parent_fd = -1
    staging_fd = -1
    try:
        extent, parent_fd, staging_fd = broker._prepare_extent(  # noqa: SLF001
            account,
            parent_path="closeout",
            target_name="terminal.json",
            maximum_bytes=4096,
            artifact_class="closeout",
        )
        assert swapped is True
        assert sentinel.read_bytes() == b"must-remain-unchanged"
        sentinel_after = os.stat(sentinel, follow_symlinks=False)
        assert (
            sentinel_after.st_dev,
            sentinel_after.st_ino,
            sentinel_after.st_size,
        ) == (
            sentinel_before.st_dev,
            sentinel_before.st_ino,
            sentinel_before.st_size,
        )
        assert sorted(path.name for path in (external / "closeout").iterdir()) == [
            "unknown"
        ]
        retained_staging = moved / "closeout" / extent.staging_name
        assert retained_staging.stat().st_ino == os.fstat(staging_fd).st_ino
        assert retained_staging.stat().st_size == 4096
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        if parent_fd >= 0:
            os.close(parent_fd)
        account.close()


def test_persistent_wait_rejects_post_exit_endpoint_parent_replacement(
    tmp_path: Path,
) -> None:
    control_root = tmp_path / "r"
    moved_root = tmp_path / "m"
    parent = control_root
    parent.mkdir()
    retired_path = parent / "s"
    listener = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    listener.bind(str(retired_path))
    retired_path.chmod(0o600)
    retired = os.stat(retired_path, follow_symlinks=False)
    child_pid = os.fork()
    if child_pid == 0:
        os._exit(0)
    pidfd, pidfd_method = broker.open_pidfd(child_pid)
    process = broker.PersistentBrokerProcess(
        pid=child_pid,
        pidfd=pidfd,
        pidfd_method=pidfd_method,
        actor={
            "schema_version": broker.ACTOR_SCHEMA,
            **broker.process_identity(child_pid),
        },
        endpoint_identity={
            "device": retired.st_dev,
            "inode": retired.st_ino,
            "mode": 0o600,
            "path": str(parent / "e"),
            "uid": os.getuid(),
        },
        retired_endpoint_path=str(retired_path),
        selected_fd_transport={},
        nonce="7" * 64,
        native_helper=None,
    )
    try:
        control_root.rename(moved_root)
        parent.mkdir(parents=True)
        replacement_marker = parent / "u"
        replacement_marker.write_bytes(b"preserve")
        (moved_root / "s").rename(retired_path)

        with pytest.raises(broker.BrokerProtocolError) as caught:
            process.wait()

        assert caught.value.code == "ENDPOINT_RETIREMENT_FAILED"
        assert replacement_marker.read_bytes() == b"preserve"
        assert os.stat(retired_path, follow_symlinks=False).st_ino == retired.st_ino
    finally:
        listener.close()
        if not process._waited:  # noqa: SLF001
            os.kill(child_pid, signal.SIGKILL)
            process.wait()
        process.close()


def _unattached_broker_process(
    tmp_path: Path,
) -> tuple[broker.PersistentBrokerProcess, int]:
    control = tmp_path / "unattached-control"
    control.mkdir()
    child_pid = os.fork()
    if child_pid == 0:
        signal.pause()
        os._exit(99)
    pidfd, pidfd_method = broker.open_pidfd(child_pid)
    return (
        broker.PersistentBrokerProcess(
            pid=child_pid,
            pidfd=pidfd,
            pidfd_method=pidfd_method,
            actor={
                "schema_version": broker.ACTOR_SCHEMA,
                **broker.process_identity(child_pid),
            },
            endpoint_identity={
                "device": 0,
                "inode": 0,
                "mode": 0o600,
                "path": str(control / "budget-broker.sock"),
                "uid": os.getuid(),
            },
            retired_endpoint_path=str(
                control / "budget-broker.sock.retired"
            ),
            selected_fd_transport={},
            nonce="8" * 64,
            native_helper=None,
        ),
        child_pid,
    )


def test_terminate_unattached_reaps_exact_child_and_closes_fds(
    tmp_path: Path,
) -> None:
    before = _fd_count()
    process, child_pid = _unattached_broker_process(tmp_path)

    result = process.terminate_unattached()

    assert result["state"] == "UNATTACHED_BROKER_TERMINATED_AND_REAPED"
    assert result["pid"] == child_pid
    assert result["pidfd_exit_proved"] is True
    assert process.pidfd == -1
    assert process._retired_parent_fd == -1  # noqa: SLF001
    with pytest.raises(ChildProcessError):
        os.waitpid(child_pid, os.WNOHANG)
    assert _fd_count() == before


def test_terminate_unattached_signal_failure_still_reaps_and_closes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    process, child_pid = _unattached_broker_process(tmp_path)

    def fail_pidfd_signal(_descriptor: int, _signum: int) -> str:
        raise RuntimeError("injected pidfd signal failure")

    monkeypatch.setattr(broker, "pidfd_send_signal", fail_pidfd_signal)
    with pytest.raises(
        RuntimeError,
        match="injected pidfd signal failure",
    ):
        process.terminate_unattached()

    assert process.pidfd == -1
    assert process._retired_parent_fd == -1  # noqa: SLF001
    with pytest.raises(ChildProcessError):
        os.waitpid(child_pid, os.WNOHANG)
    assert _fd_count() == before


def test_terminate_unattached_poll_failure_still_reaps_and_closes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    process, child_pid = _unattached_broker_process(tmp_path)

    class FaultPoll:
        def register(self, _descriptor: int, _events: int) -> None:
            return None

        def poll(self, _timeout: int) -> list[tuple[int, int]]:
            raise RuntimeError("injected pidfd poll failure")

    monkeypatch.setattr(select, "poll", FaultPoll)
    with pytest.raises(
        RuntimeError,
        match="injected pidfd poll failure",
    ):
        process.terminate_unattached()

    assert process.pidfd == -1
    assert process._retired_parent_fd == -1  # noqa: SLF001
    with pytest.raises(ChildProcessError):
        os.waitpid(child_pid, os.WNOHANG)
    assert _fd_count() == before


def test_runtime_roles_are_research_only_and_do_not_import_solver_surface() -> None:
    for module_path in (
        RESEARCH / "ab16_budget_broker_v1.py",
        RESEARCH / "ab16_recovery_closeout_v1.py",
        RESEARCH / "ab16_closure_actor_v1.py",
    ):
        source = module_path.read_text(encoding="utf-8")
        assert "CpSolver" not in source
        assert "systemd-run" not in source
        assert "subprocess" not in source
    assert {
        broker.PACKAGE_ROLE,
        recovery.PACKAGE_ROLE,
        closure.PACKAGE_ROLE,
    } == {
        "ab16-budget-broker-v1",
        "ab16-recovery-closeout-v1",
        "ab16-closure-actor-v1",
    }


def test_broker_accepts_only_fully_sealed_memfd_and_publishes_inside_reserved_extent(
    tmp_path: Path,
) -> None:
    helper, helper_fd = _native_helper()
    process = _spawn_broker(tmp_path, native_helper=helper)
    descriptor = helper.create_memfd("ab16-test-model")
    raw = b"tiny-model-proto"
    try:
        allocation = process.request(
            "ALLOCATE_ARM",
            {
                "arm_slot": "arm-01",
                "category_limits": {"model": 64 * 1024},
            },
        )
        assert allocation.record["result"]["arm_slot"] == "arm-01"
        assert os.pwrite(descriptor, raw, 0) == len(raw)
        os.ftruncate(descriptor, len(raw))
        assert not helper.has_writable_mapping(descriptor)
        assert helper.install_final_seals(descriptor) == helper.final_seal_mask
        response = process.publish_descriptor(
            {
                "arm_slot": "arm-01",
                "artifact_class": "model",
                "expected_sha256": hashlib.sha256(raw).hexdigest(),
                "maximum_bytes": 64 * 1024,
                "relative_path": "models/arm-01.pb",
                "size_bytes": len(raw),
            },
            descriptor=descriptor,
        )
        result = response.record["result"]
        assert result["source_seal_mask"] == helper.final_seal_mask
        assert result["sha256"] == hashlib.sha256(raw).hexdigest()
        assert (tmp_path / "formal/models/arm-01.pb").read_bytes() == raw
        _normal_exit(process)
    finally:
        os.close(descriptor)
        os.close(helper_fd)
        _wait_and_close_broker(process, expected={0})


def test_broker_rejects_unsealed_memfd_without_publishing_target(
    tmp_path: Path,
) -> None:
    helper, helper_fd = _native_helper()
    process = _spawn_broker(tmp_path, native_helper=helper)
    descriptor = helper.create_memfd("ab16-unsealed-model")
    raw = b"unsealed"
    try:
        assert os.pwrite(descriptor, raw, 0) == len(raw)
        os.ftruncate(descriptor, len(raw))
        with pytest.raises(broker.BrokerProtocolError):
            process.publish_descriptor(
                {
                    "arm_slot": None,
                    "artifact_class": "model",
                    "expected_sha256": hashlib.sha256(raw).hexdigest(),
                    "maximum_bytes": 64 * 1024,
                    "relative_path": "unsealed.pb",
                    "size_bytes": len(raw),
                },
                descriptor=descriptor,
            )
        assert process.wait() == 2
        assert not (tmp_path / "formal/unsealed.pb").exists()
    finally:
        os.close(descriptor)
        os.close(helper_fd)
        _wait_and_close_broker(process, expected={2})


def test_persistent_descriptor_client_crosses_boundary_only_before_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)

    class Helper:
        @staticmethod
        def send_fd(_socket_fd: int, _descriptor: int) -> None:
            raise AssertionError("send_fd ran after injected send-frame loss")

    client = broker.BrokerSessionClient(
        connection=left,
        nonce="a" * 64,
        actor={},
        grant=None,  # type: ignore[arg-type] - not read by descriptor publication
        native_helper=Helper(),
    )
    events: list[str] = []
    try:
        client.closed = True
        with pytest.raises(broker.BrokerProtocolError) as closed:
            client.publish_descriptor(
                {},
                descriptor=0,
                publication_boundary=lambda: events.append("boundary"),
            )
        assert closed.value.code == "SESSION_CLOSED"
        assert events == []

        client.closed = False

        def fail_after_boundary(
            _connection: socket.socket,
            _record: Mapping[str, object],
            *,
            descriptors: tuple[int, ...] = (),
        ) -> None:
            assert descriptors == ()
            assert events == ["boundary"]
            raise OSError("injected request send uncertainty")

        monkeypatch.setattr(broker, "send_frame", fail_after_boundary)
        with pytest.raises(OSError, match="send uncertainty"):
            client.publish_descriptor(
                {},
                descriptor=0,
                publication_boundary=lambda: events.append("boundary"),
            )
        assert events == ["boundary"]
        assert client.sequence == 1
    finally:
        left.close()
        right.close()


def test_persistent_transferred_broker_authenticates_supervisor_and_arm_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _model_isolated_host_for_writer_scan(monkeypatch)
    same_uid_baseline = _zero_authority_closure_process_baseline(
        allowed_processes=(
            {
                "pid": os.getpid(),
                "starttime": broker.process_starttime(os.getpid()),
            },
        ),
    )
    same_uid_baseline_sha256 = (
        resource_admission._canonical_sha256(  # noqa: SLF001
            same_uid_baseline
        )
    )
    owner_nonce = "a" * 64
    supervisor_credential = "b" * 64
    arm_credential = "c" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = (
        _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
        )
    )
    helper, helper_fd = _native_helper()
    package_gate = _PackageRoleGate()
    native_authorization = _NativeHelperAuthorization(helper, helper_fd)
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=package_gate,
        native_helper_authorization=native_authorization,
        **_persistent_spawn_bindings(
            contract_identity=contract_identity,
            failure_path=failure_path,
            owner_nonce=owner_nonce,
        ),
        supervisor_credential=supervisor_credential,
        expected_supervisor_peer=broker.process_identity(),
        formal_directories=(
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {"mode_octal": "0700", "path": "channels/budget-journal"},
        ),
        arm_directories={
            "arm-01": (
                {"mode_octal": "0700", "path": "arms"},
                {"mode_octal": "0700", "path": "arms/arm-01"},
            )
        },
    )
    assert native_authorization.close_count == 1
    supervisor: broker.BrokerSessionClient | None = None
    closer: closure.DetachedClosureProcess | None = None
    final_releaser: final_release_actor.FinalReleaseProcess | None = None
    child_pid: int | None = None
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    result_read, result_write = os.pipe2(os.O_CLOEXEC)
    try:
        assert package_gate.calls == [broker.PACKAGE_ROLE]
        assert process.endpoint_identity["mode"] == 0o600
        assert process.selected_fd_transport["owner"] == {
            key: process.actor[key]
            for key in ("pid", "pid_starttime", "uid")
        }
        supervisor = process.connect(
            credential=supervisor_credential,
            role="supervisor",
        )
        prepared = supervisor.request(
            "PREPARE_RECOVERY",
            {},
            expected_fd_counts=frozenset({0}),
        )
        prepared_result = dict(prepared.record["result"])
        assert prepared.descriptors == ()
        assert prepared_result["state"] == "BROKER_RETAINED_CONTROL"
        assert prepared_result["control_owner"] == (
            "persistent-budget-broker"
        )
        assert package_gate.calls == [
            broker.PACKAGE_ROLE,
        ]
        selection_identity = {
            "path": str((tmp_path / "formal-selection.json").absolute()),
            "sha256": "d" * 64,
            "size_bytes": 41,
        }
        assert supervisor.request(
            "BIND_SELECTION",
            {"selection_identity": selection_identity},
        ).record["result"]["selection_identity"] == selection_identity
        allocation = supervisor.request(
            "ALLOCATE_ARM",
            {
                "arm_slot": "arm-01",
                "category_limits": {"normal": 4096},
            },
        ).record["result"]
        allocation_identity = allocation["allocation_identity"]

        child_pid = os.fork()
        if child_pid == 0:
            os.close(release_write)
            os.close(result_read)
            try:
                if os.read(release_read, 1) != b"1":
                    raise AssertionError("arm grant release was absent")
                arm = process.connect(
                    credential=arm_credential,
                    role="arm",
                    arm_slot="arm-01",
                    selection_identity=selection_identity,
                    allocation_identity=allocation_identity,
                )
                try:
                    arm.request(
                        "PUBLISH",
                        {
                            "arm_slot": "arm-01",
                            "artifact_class": "normal",
                            "channel": None,
                            "label": "test arm result",
                            "maximum_bytes": 4096,
                            "payload_hex": b"arm-result".hex(),
                            "relative_path": "arms/arm-01/result.json",
                            "sequence": None,
                        },
                    )
                    arm.close_session()
                    os.write(result_write, b"PASS")
                finally:
                    arm.close()
            except BaseException as exc:
                os.write(
                    result_write,
                    f"FAIL:{type(exc).__name__}:{exc}".encode(),
                )
            finally:
                os.close(release_read)
                os.close(result_write)
            os._exit(0)
        os.close(release_read)
        release_read = -1
        os.close(result_write)
        result_write = -1
        arm_peer = broker.process_identity(child_pid)
        arm_pidfd, _arm_pidfd_method = broker.open_pidfd(child_pid)
        try:
            registered = supervisor.register_bound_arm_grant(
                {
                    "allocation_identity": allocation_identity,
                    "arm_slot": "arm-01",
                    "credential": arm_credential,
                    "expected_peer": arm_peer,
                    "role": "arm",
                    "selection_identity": selection_identity,
                },
                pidfd=arm_pidfd,
            ).record["result"]
        finally:
            os.close(arm_pidfd)
        assert registered["expected_peer"] == arm_peer
        assert registered["selection_identity"] == selection_identity
        assert registered["allocation_identity"] == allocation_identity
        os.write(release_write, b"1")
        os.close(release_write)
        release_write = -1
        assert os.read(result_read, 4096) == b"PASS"
        os.close(result_read)
        result_read = -1
        assert os.waitpid(child_pid, 0) == (child_pid, 0)
        child_pid = None
        assert (
            tmp_path / "formal-persistent/arms/arm-01/result.json"
        ).read_bytes() == b"arm-result"
        closure_frame = supervisor.request(
            "PREPARE_CLOSURE",
            {},
            expected_fd_counts=frozenset({4}),
        )
        closure_transfer = dict(closure_frame.record["result"])
        assert closure_transfer["schema_version"] == (
            "noncert-cuts-ab16-closure-control-transfer-v1"
        )
        closer = closure.attach_broker_forked_closure(
            closure_transfer["closure_handoff"],
            closure_frame.descriptors[:2],
        )
        final_releaser = (
            final_release_actor.attach_broker_forked_final_release(
                closure_transfer["final_release_handoff"],
                closure_frame.descriptors[2:],
            )
        )
        intent = supervisor.request(
            "PUBLISH_DISARM_INTENT",
            {"terminal_join_sha256": "f" * 64},
        ).record["result"]
        assert intent["state"] == "RECOVERY_DISARM_INTENT_PUBLISHED"
        assert intent["terminal_join_sha256"] == "f" * 64
        disarmed = supervisor.request(
            "DISARM_RECOVERY",
            {
                "disarm_intent_sha256": broker._message_identity(  # noqa: SLF001
                    intent
                )["sha256"]
            },
        ).record["result"]
        assert disarmed["terminal"]["terminal_result"]["state"] == (
            "DISARMED_WITHOUT_TAKEOVER"
        )
        assert disarmed["lock_release"]["state"] == (
            "RECOVERY_TAKEOVER_LOCK_RELEASED"
        )
        exit_result = dict(
            supervisor.request("EXIT", {}).record["result"]
        )
        assert exit_result["state"] == "BROKER_EXIT_ACCEPTED"
        assert (
            exit_result["root_inventory"]["schema_version"]
            == broker.ROOT_INVENTORY_SCHEMA
        )
        supervisor.close()
        supervisor = None
        assert process.wait() == 0
        assert not Path(str(process.endpoint_identity["path"])).exists()
        assert Path(process.retired_endpoint_path).exists()
        # The formal cleanup owner retires and then removes the verified
        # broker endpoint before transferring final closure.  This
        # zero-authority harness performs the same final absence transition.
        Path(process.retired_endpoint_path).unlink()
        closed = closer.close_root(
            {
                "budget_contract": {
                    "research_only": True,
                    "schema_version": (
                        "noncert-cuts-ab16-zero-authority-budget-v1"
                    ),
                },
                "disarm_observation": disarmed,
                "root_inventory": exit_result["root_inventory"],
                "same_uid_process_baseline": same_uid_baseline,
                "same_uid_process_baseline_sha256": (
                    same_uid_baseline_sha256
                ),
                "terminal_join_sha256": "f" * 64,
            }
        )
        assert closed["state"] == "ROOT_CLOSED_NO_WRITERS"
        closer.prove_exit()
        closer.close()
        closer = None
        final_releaser.connection.close()
        final_releaser.prove_exit()
        final_releaser.close()
        final_releaser = None
    finally:
        for descriptor in (
            release_read,
            release_write,
            result_read,
            result_write,
        ):
            if descriptor >= 0:
                os.close(descriptor)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(child_pid, 0)
        if supervisor is not None:
            supervisor.close()
        if closer is not None:
            if not closer._exit_proved:  # noqa: SLF001
                try:
                    os.kill(closer.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    closer.prove_exit()
                except closure.ClosureProtocolError:
                    pass
            closer.close()
        if final_releaser is not None:
            final_releaser.connection.close()
            if not final_releaser._exit_proved:  # noqa: SLF001
                try:
                    final_releaser.prove_exit()
                except final_release_actor.FinalReleaseProtocolError:
                    pass
            final_releaser.close()
        if not process._waited:  # noqa: SLF001
            try:
                os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        process.close()


def test_bootstrap_admin_pidfd_binds_future_worker_exactly_once(
    tmp_path: Path,
) -> None:
    """Bootstrap need not know a later selected worker's PID or credential."""

    owner_nonce = "4" * 64
    worker_credential = "5" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    package_gate = _PackageRoleGate()
    native_authorization = _NativeHelperAuthorization(helper, helper_fd)
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=package_gate,
        native_helper_authorization=native_authorization,
        **_persistent_spawn_bindings(
            contract_identity=contract_identity,
            failure_path=failure_path,
            owner_nonce=owner_nonce,
        ),
        formal_directories=(
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
        ),
    )
    assert native_authorization.close_count == 1
    admin: broker.BrokerSessionClient | None = None
    child_pid: int | None = None
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    result_read, result_write = os.pipe2(os.O_CLOEXEC)
    try:
        admin = process.connect_bootstrap_admin()
        with pytest.raises(broker.BrokerProtocolError) as consumed:
            process.connect_bootstrap_admin()
        assert consumed.value.code == (
            "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN"
        )

        child_pid = os.fork()
        if child_pid == 0:
            os.close(release_write)
            os.close(result_read)
            admin.close()
            try:
                if os.read(release_read, 1) != b"1":
                    raise AssertionError("worker grant release was absent")
                endpoint_parent = (
                    broker._open_absolute_directory_no_symlinks(  # noqa: SLF001
                        endpoint_path.parent
                    )
                )
                connection = socket.socket(
                    socket.AF_UNIX,
                    socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
                )
                try:
                    connection.connect(
                        f"/proc/self/fd/{endpoint_parent}/"
                        f"{endpoint_path.name}"
                    )
                finally:
                    os.close(endpoint_parent)
                worker = broker.attach_registered_nonarm_session(
                    connection.detach(),
                    broker_actor=process.actor,
                    broker_nonce=process.nonce,
                    credential=worker_credential,
                    role="formal-worker",
                    native_helper=helper,
                )
                try:
                    status = worker.request("STATUS", {}).record["result"]
                    worker.close_session()
                    os.write(
                        result_write,
                        (
                            "PASS:"
                            + str(
                                status["contract"]["authority"][
                                    "research_only"
                                ]
                            )
                        ).encode(),
                    )
                finally:
                    worker.close()
            except BaseException as exc:
                os.write(
                    result_write,
                    f"FAIL:{type(exc).__name__}:{exc}".encode(),
                )
            finally:
                os.close(release_read)
                os.close(result_write)
            os._exit(0)

        os.close(release_read)
        release_read = -1
        os.close(result_write)
        result_write = -1
        pidfd, _method = broker.open_pidfd(child_pid)
        try:
            expected_peer = broker.process_identity(child_pid)
            registered = admin.register_bound_nonarm_grant(
                {
                    "credential": worker_credential,
                    "expected_peer": expected_peer,
                    "role": "formal-worker",
                },
                pidfd=pidfd,
            ).record["result"]
            assert registered["expected_peer"] == expected_peer
            assert registered["role"] == "formal-worker"
        finally:
            os.close(pidfd)

        os.write(release_write, b"1")
        os.close(release_write)
        release_write = -1
        assert os.read(result_read, 4096) == b"PASS:True"
        os.close(result_read)
        result_read = -1
        assert os.waitpid(child_pid, 0) == (child_pid, 0)
        child_pid = None
        admin.close_session()
        admin = None

        with pytest.raises(broker.BrokerProtocolError) as replayed:
            process.connect(
                credential=worker_credential,
                role="formal-worker",
            )
        assert replayed.value.code == (
            "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN"
        )
        assert process.wait() == 2
    finally:
        for descriptor in (
            release_read,
            release_write,
            result_read,
            result_write,
        ):
            if descriptor >= 0:
                os.close(descriptor)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(child_pid, 0)
        if admin is not None:
            admin.close()
        if not process._waited:  # noqa: SLF001
            try:
                os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        process.close()


def test_bound_arm_grant_rejects_stale_claim_wrong_pidfd_and_exited_peer(
    tmp_path: Path,
) -> None:
    supervisor = broker.build_session_grant(
        credential="1" * 64,
        expected_peer=broker.process_identity(),
        role="supervisor",
    )
    runtime = broker._SharedBrokerRuntime(  # noqa: SLF001
        actor={
            "schema_version": broker.ACTOR_SCHEMA,
            **broker.process_identity(),
        },
        nonce="2" * 64,
        supervisor_grant=supervisor,
        bootstrap_handoff_spec={
            "artifact_class": "metadata",
            "maximum_bytes": 4096,
            "relative_path": "formal-root-budget-handoff.json",
        },
        bootstrap_handoff_base={},
        bootstrap_failure_closeout_path=(
            tmp_path / "bootstrap-failure.json"
        ).absolute(),
        control_endpoint_path=(
            tmp_path / "control/budget-broker.sock"
        ).absolute(),
            retired_endpoint_path=(
                tmp_path / "control/budget-broker.sock.retired"
            ).absolute(),
            formal_artifact_contracts=(),
            formal_append_contracts=(),
            arm_artifact_contracts={},
            arm_append_contracts={},
        )
    selection = {
        "path": str((tmp_path / "selection.json").absolute()),
        "sha256": "3" * 64,
        "size_bytes": 1,
    }
    runtime.bind_selection(selection)
    allocation = runtime.remember_allocation(
        "arm-01",
        {"slot": "arm-01"},
    )
    child_pid = os.fork()
    if child_pid == 0:
        signal.pause()
        os._exit(0)
    child_pidfd, _method = broker.open_pidfd(child_pid)
    self_pidfd, _self_method = broker.open_pidfd(os.getpid())
    peer = broker.process_identity(child_pid)

    def payload(
        *,
        credential: str,
        expected_peer: Mapping[str, object] = peer,
    ) -> dict[str, object]:
        return {
            "allocation_identity": allocation,
            "arm_slot": "arm-01",
            "credential": credential,
            "expected_peer": dict(expected_peer),
            "role": "arm",
            "selection_identity": selection,
        }

    try:
        stale = {
            **peer,
            "pid_starttime": peer["pid_starttime"] + 1,
        }
        with pytest.raises(broker.BrokerProtocolError) as stale_error:
            runtime.register_bound_arm_grant(
                payload(credential="4" * 64, expected_peer=stale),
                pidfd=child_pidfd,
            )
        assert stale_error.value.code == "PIDFD_IDENTITY_DRIFT"

        with pytest.raises(broker.BrokerProtocolError) as wrong_target:
            runtime.register_bound_arm_grant(
                payload(credential="5" * 64),
                pidfd=self_pidfd,
            )
        assert wrong_target.value.code == "PIDFD_IDENTITY_DRIFT"

        os.kill(child_pid, signal.SIGKILL)
        assert os.waitpid(child_pid, 0)[0] == child_pid
        child_pid = -1
        assert broker.pidfd_reports_exit(child_pidfd)
        with pytest.raises(broker.BrokerProtocolError) as exited:
            runtime.register_bound_arm_grant(
                payload(credential="6" * 64),
                pidfd=child_pidfd,
            )
        assert exited.value.code == "PIDFD_IDENTITY_DRIFT"
    finally:
        os.close(self_pidfd)
        os.close(child_pidfd)
        if child_pid > 0:
            os.kill(child_pid, signal.SIGKILL)
            os.waitpid(child_pid, 0)


def test_bootstrap_admin_publishes_exact_live_handoff_once(
    tmp_path: Path,
) -> None:
    owner_nonce = "6" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    package_gate = _PackageRoleGate()
    native_authorization = _NativeHelperAuthorization(helper, helper_fd)
    spawn_bindings = _persistent_spawn_bindings(
        contract_identity=contract_identity,
        failure_path=failure_path,
        owner_nonce=owner_nonce,
    )
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=package_gate,
        native_helper_authorization=native_authorization,
        **spawn_bindings,
        formal_directories=(
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
        ),
    )
    admin = process.connect_bootstrap_admin()
    try:
        recovery_observation = admin.request(
            "PREPARE_RECOVERY",
            {},
        ).record["result"]
        handoff_record = {
            "authority": dict(broker.FALSE_AUTHORITY_BOUNDARY),
            "broker_actor": dict(process.actor),
            "broker_endpoint_identity": dict(
                process.endpoint_identity
            ),
            "formal_account_handoff": handoff,
            "formal_control_parent_handoff": control_handoff,
            "formal_final_release_parent_handoff": spawn_bindings[
                "final_release_parent_handoff"
            ],
            "formal_reservation_handoffs": reservation_handoffs,
            "formal_root_budget_contract_identity": contract_identity,
            "formal_resource_calibration_bundle_identity": (
                spawn_bindings[
                    "formal_resource_calibration_bundle_identity"
                ]
            ),
            "resource_budget_profile_identity": spawn_bindings[
                "resource_budget_profile_identity"
            ],
            "resource_calibration_authorization_bundles": spawn_bindings[
                "resource_calibration_authorization_bundles"
            ],
            "calibration_tool_content_identities": spawn_bindings[
                "calibration_tool_content_identities"
            ],
            "package_id": "2" * 64,
            "recovery_owner_observation": recovery_observation,
            "run_nonce": "run-zero-authority-budget-test",
            "schema_version": broker.BOOTSTRAP_HANDOFF_SCHEMA,
            "selected_fd_transport": process.selected_fd_transport,
            "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
            "status": "PASS",
        }
        result = admin.request(
            "PUBLISH_BOOTSTRAP_HANDOFF",
            handoff_record,
        ).record["result"]
        handoff_path = (
            tmp_path
            / "formal-persistent/formal-root-budget-handoff.json"
        )
        assert result["handoff_identity"] == {
            "path": str(handoff_path),
            "sha256": hashlib.sha256(
                broker.canonical_json_bytes(handoff_record)
            ).hexdigest(),
            "size_bytes": len(
                broker.canonical_json_bytes(handoff_record)
            ),
        }
        assert json.loads(handoff_path.read_bytes()) == handoff_record
        with pytest.raises(broker.BrokerProtocolError) as repeated:
            admin.request(
                "PUBLISH_BOOTSTRAP_HANDOFF",
                handoff_record,
            )
        assert repeated.value.code == (
            "BOOTSTRAP_HANDOFF_ALREADY_ATTEMPTED"
        )
        assert process.wait() == 2
    finally:
        admin.close()
        if not process._waited:  # noqa: SLF001
            os.kill(process.pid, signal.SIGKILL)
            process.wait()
        process.close()


def test_bootstrap_abort_is_markerless_and_reaps_retained_recovery(
    tmp_path: Path,
) -> None:
    owner_nonce = "7" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    failure_raw = broker.canonical_json_bytes(
        {
            "schema_version": (
                "noncert-cuts-ab16-zero-authority-bootstrap-failure-v1"
            ),
            "state": "markerless-incomplete",
        }
    )
    failure_path.write_bytes(failure_raw)
    failure_path.chmod(0o444)
    failure_identity = {
        "path": str(failure_path),
        "sha256": hashlib.sha256(failure_raw).hexdigest(),
        "size_bytes": len(failure_raw),
    }
    helper, helper_fd = _native_helper()
    native_authorization = _NativeHelperAuthorization(helper, helper_fd)
    spawn_bindings = _persistent_spawn_bindings(
        contract_identity=contract_identity,
        failure_path=failure_path,
        owner_nonce=owner_nonce,
    )
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=_PackageRoleGate(),
        native_helper_authorization=native_authorization,
        **spawn_bindings,
    )
    admin = process.connect_bootstrap_admin()
    try:
        recovery_observation = admin.request(
            "PREPARE_RECOVERY",
            {},
        ).record["result"]
        recovery_pid = recovery_observation["actor"]["pid"]
        admin.request(
            "PUBLISH_BOOTSTRAP_HANDOFF",
            {
                "authority": dict(broker.FALSE_AUTHORITY_BOUNDARY),
                "broker_actor": dict(process.actor),
                "broker_endpoint_identity": dict(
                    process.endpoint_identity
                ),
                "formal_account_handoff": handoff,
                "formal_control_parent_handoff": control_handoff,
                "formal_final_release_parent_handoff": spawn_bindings[
                    "final_release_parent_handoff"
                ],
                "formal_reservation_handoffs": reservation_handoffs,
                "formal_root_budget_contract_identity": contract_identity,
                "formal_resource_calibration_bundle_identity": (
                    spawn_bindings[
                        "formal_resource_calibration_bundle_identity"
                    ]
                ),
                "resource_budget_profile_identity": spawn_bindings[
                    "resource_budget_profile_identity"
                ],
                "resource_calibration_authorization_bundles": (
                    spawn_bindings[
                        "resource_calibration_authorization_bundles"
                    ]
                ),
                "calibration_tool_content_identities": spawn_bindings[
                    "calibration_tool_content_identities"
                ],
                "package_id": "2" * 64,
                "recovery_owner_observation": recovery_observation,
                "run_nonce": "run-zero-authority-budget-test",
                "schema_version": broker.BOOTSTRAP_HANDOFF_SCHEMA,
                "selected_fd_transport": process.selected_fd_transport,
                "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
                "status": "PASS",
            },
        )
        result = admin.request(
            "ABORT_BOOTSTRAP_INCOMPLETE",
            {
                "bootstrap_failure_identity": failure_identity,
                "reason_sha256": hashlib.sha256(
                    b"bootstrap failure"
                ).hexdigest(),
                "state": "markerless-incomplete",
            },
        ).record["result"]
        assert result["state"] == "MARKERLESS_BOOTSTRAP_ABORTED"
        assert result["prior_handoff_state"] == "PUBLISHED"
        assert result["bootstrap_failure_identity"] == failure_identity
        assert result["recovery_terminal"]["state"] == (
            "DISARMED_AND_EXIT_PROVED"
        )
        assert not Path(f"/proc/{recovery_pid}").exists()
        admin.close()
        assert process.wait() == 2
        assert not endpoint_path.exists()
        assert Path(process.retired_endpoint_path).is_socket()
    finally:
        admin.close()
        if not process._waited:  # noqa: SLF001
            os.kill(process.pid, signal.SIGKILL)
            process.wait()
        process.close()


def test_persistent_broker_requires_package_pass_before_process_or_endpoint(
    tmp_path: Path,
) -> None:
    owner_nonce = "e" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = (
        _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
        )
    )
    gate = _PackageRoleGate(accepted=False)
    helper, helper_fd = _native_helper()
    native_authorization = _NativeHelperAuthorization(helper, helper_fd)
    spawn_bindings = _persistent_spawn_bindings(
        contract_identity=contract_identity,
        failure_path=failure_path,
        owner_nonce=owner_nonce,
    )
    try:
        with pytest.raises(RuntimeError, match="not PASS"):
            broker.spawn_persistent_broker_from_transfer(
                account=account,
                ownership_handoff=handoff,
                fixed_purpose_reservations=reservations,
                fixed_purpose_handoffs=reservation_handoffs,
                control_parent_capability=control_parent,
                control_parent_handoff=control_handoff,
                endpoint_path=endpoint_path,
                owner_nonce=owner_nonce,
                package_authorization=gate,
                native_helper_authorization=native_authorization,
                **spawn_bindings,
                supervisor_credential="f" * 64,
                expected_supervisor_peer=broker.process_identity(),
            )
        assert gate.calls == [broker.PACKAGE_ROLE]
        assert not (
            tmp_path / "formal-persistent/control/budget-broker.sock"
        ).exists()
        assert account.contract_record()["authority"]["research_only"] is True
    finally:
        spawn_bindings["final_release_parent_capability"].close()
        native_authorization.close()
        account.close()
        control_parent.close()


def test_persistent_transfer_native_helper_close_failure_is_exact_once(
    tmp_path: Path,
) -> None:
    owner_nonce = "0" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    package_gate = _PackageRoleGate()
    injected = RuntimeError("injected native-helper authorization close failure")
    native_authorization = _NativeHelperAuthorization(
        helper,
        helper_fd,
        close_error=injected,
    )

    with pytest.raises(RuntimeError) as caught:
        broker.spawn_persistent_broker_from_transfer(
            account=account,
            ownership_handoff=handoff,
            fixed_purpose_reservations=reservations,
            fixed_purpose_handoffs=reservation_handoffs,
            control_parent_capability=control_parent,
            control_parent_handoff=control_handoff,
            endpoint_path=endpoint_path,
            owner_nonce=owner_nonce,
            package_authorization=package_gate,
            native_helper_authorization=native_authorization,
            **_persistent_spawn_bindings(
                contract_identity=contract_identity,
                failure_path=failure_path,
                owner_nonce=owner_nonce,
            ),
            supervisor_credential="1" * 64,
            expected_supervisor_peer=broker.process_identity(),
        )

    assert caught.value is injected
    assert native_authorization.close_count == 1
    with pytest.raises(OSError):
        os.fstat(helper_fd)
    assert endpoint_path.is_socket()


def test_manager_openfile_session_waits_for_mainpid_pidfd_binding(
    tmp_path: Path,
) -> None:
    owner_nonce = "8" * 64
    supervisor_credential = "9" * 64
    unit_credential = "a" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    package_gate = _PackageRoleGate()
    native_authorization = _NativeHelperAuthorization(helper, helper_fd)
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=package_gate,
        native_helper_authorization=native_authorization,
        **_persistent_spawn_bindings(
            contract_identity=contract_identity,
            failure_path=failure_path,
            owner_nonce=owner_nonce,
        ),
        supervisor_credential=supervisor_credential,
        expected_supervisor_peer=broker.process_identity(),
        formal_directories=(
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
        ),
    )
    assert native_authorization.close_count == 1
    supervisor = process.connect(
        credential=supervisor_credential,
        role="supervisor",
    )
    selection = {
        "path": str((tmp_path / "selection.json").absolute()),
        "sha256": "b" * 64,
        "size_bytes": 1,
    }
    attempt = {
        "path": str((tmp_path / "attempt.json").absolute()),
        "sha256": "c" * 64,
        "size_bytes": 1,
    }
    guardian_ready = {
        "path": str((tmp_path / "guardian-ready.json").absolute()),
        "sha256": "d" * 64,
        "size_bytes": 1,
    }
    manager_epoch = {"sha256": "e" * 64, "size_bytes": 1}
    preregistered = supervisor.request(
        "PREREGISTER_MANAGER_OPENFILE_GRANT",
        {
            "attempt_consumption_identity": attempt,
            "credential": unit_credential,
            "manager_epoch_identity": manager_epoch,
            "selection_path": selection["path"],
            "unit_name": "ab16-formal-fixture.service",
        },
    ).record["result"]
    assert preregistered["state"] == "UNBOUND"
    prepared_binding = supervisor.bind_manager_openfile_selection(
        {
            "credential": unit_credential,
            "selection_identity": selection,
        }
    ).record["result"]
    assert prepared_binding["state"] == "PREPARED_SELECTION_BOUND"
    assert prepared_binding["selection_identity"] == selection
    manager_connection = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    endpoint_parent = broker._open_absolute_directory_no_symlinks(  # noqa: SLF001
        endpoint_path.parent
    )
    try:
        manager_connection.connect(
            f"/proc/self/fd/{endpoint_parent}/{endpoint_path.name}"
        )
    finally:
        os.close(endpoint_parent)
    result_read, result_write = os.pipe2(os.O_CLOEXEC)
    child_pid = os.fork()
    if child_pid == 0:
        os.close(result_read)
        supervisor.close()
        try:
            selected = broker.attach_manager_openfile_supervisor(
                manager_connection.detach(),
                broker_actor=process.actor,
                broker_nonce=process.nonce,
                credential=unit_credential,
                manager_epoch_identity=manager_epoch,
                selection_identity=selection,
                attempt_consumption_identity=attempt,
                unit_name="ab16-formal-fixture.service",
                native_helper=helper,
            )
            status = selected.request("STATUS", {}).record["result"]
            selected.close_session()
            os.write(
                result_write,
                b"PASS:"
                + str(
                    status["contract"]["authority"]["research_only"]
                ).encode(),
            )
        except BaseException as exc:
            os.write(
                result_write,
                f"FAIL:{type(exc).__name__}:{exc}".encode(),
            )
        finally:
            os.close(result_write)
        os._exit(0)
    manager_connection.close()
    os.close(result_write)
    pidfd, pidfd_method = broker.open_pidfd(child_pid)
    try:
        bound = supervisor.bind_manager_openfile_grant(
            {
                "application_peer": broker.process_identity(child_pid),
                "attempt_consumption_identity": attempt,
                "credential": unit_credential,
                "guardian_ready_identity": guardian_ready,
                "pidfd_method": pidfd_method,
                "selection_identity": selection,
            },
            pidfd=pidfd,
        ).record["result"]
        assert bound["state"] == "BOUND"
    finally:
        os.close(pidfd)
    assert os.read(result_read, 4096) == b"PASS:True"
    os.close(result_read)
    assert os.waitpid(child_pid, 0) == (child_pid, 0)
    supervisor.close()
    os.kill(process.pid, signal.SIGKILL)
    assert process.wait() == 128 + signal.SIGKILL
    process.close()


def test_bootstrap_admin_hands_off_exact_formal_owner_and_closeout_grants(
    tmp_path: Path,
) -> None:
    """Exercise the later-owner path without publishing campaign authority."""

    owner_nonce = "b" * 64
    owner_credential = "c" * 64
    closeout_credential = "d" * 64
    manager_credential = "e" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=_PackageRoleGate(),
        native_helper_authorization=_NativeHelperAuthorization(
            helper,
            helper_fd,
        ),
        **_persistent_spawn_bindings(
            contract_identity=contract_identity,
            failure_path=failure_path,
            owner_nonce=owner_nonce,
        ),
        formal_directories=(
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
        ),
    )

    def connected_descriptor() -> int:
        parent_fd = broker._open_absolute_directory_no_symlinks(  # noqa: SLF001
            endpoint_path.parent
        )
        connection = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
        )
        try:
            connection.connect(
                f"/proc/self/fd/{parent_fd}/{endpoint_path.name}"
            )
            return connection.detach()
        finally:
            os.close(parent_fd)
            connection.close()

    admin = process.connect_bootstrap_admin()
    owner: broker.BrokerSessionClient | None = None
    closeout: broker.BrokerSessionClient | None = None
    try:
        self_peer = broker.process_identity()
        self_pidfd, _method = broker.open_pidfd(os.getpid())
        try:
            owner_grant = admin.register_bound_nonarm_grant(
                {
                    "credential": owner_credential,
                    "expected_peer": self_peer,
                    "role": "formal-launch-owner",
                },
                pidfd=self_pidfd,
            ).record["result"]
        finally:
            os.close(self_pidfd)
        assert owner_grant["role"] == "formal-launch-owner"
        owner = broker.attach_registered_nonarm_session(
            connected_descriptor(),
            broker_actor=process.actor,
            broker_nonce=process.nonce,
            credential=owner_credential,
            role="formal-launch-owner",
            native_helper=helper,
        )
        # The bootstrap authority can now release its one-shot admin while the
        # exact later owner remains authenticated on a distinct connection.
        admin.close_session()

        selection = {
            "path": str((tmp_path / "selection.json").absolute()),
            "sha256": "1" * 64,
            "size_bytes": 123,
        }
        attempt = {
            "path": str((tmp_path / "attempt.json").absolute()),
            "sha256": "2" * 64,
            "size_bytes": 123,
        }
        manager_epoch = {"sha256": "3" * 64, "size_bytes": 123}
        preregistered = owner.request(
            "PREREGISTER_MANAGER_OPENFILE_GRANT",
            {
                "attempt_consumption_identity": attempt,
                "credential": manager_credential,
                "manager_epoch_identity": manager_epoch,
                "selection_path": selection["path"],
                "unit_name": "ab16-formal-fixture.service",
            },
        ).record["result"]
        assert preregistered["owner_credential_sha256"] == (
            owner.grant.credential_sha256
        )
        assert preregistered["owner_peer"] == self_peer
        bound_selection = owner.bind_manager_openfile_selection(
            {
                "credential": manager_credential,
                "selection_identity": selection,
            }
        ).record["result"]
        assert bound_selection["state"] == "PREPARED_SELECTION_BOUND"

        closeout_pidfd, _method = broker.open_pidfd(os.getpid())
        try:
            closeout_grant = owner.register_bound_nonarm_grant(
                {
                    "credential": closeout_credential,
                    "expected_peer": self_peer,
                    "role": "formal-closeout-owner",
                },
                pidfd=closeout_pidfd,
            ).record["result"]
        finally:
            os.close(closeout_pidfd)
        assert closeout_grant["role"] == "formal-closeout-owner"
        assert (
            closeout_grant["credential_sha256"]
            != owner_grant["credential_sha256"]
        )
        closeout = broker.attach_registered_nonarm_session(
            connected_descriptor(),
            broker_actor=process.actor,
            broker_nonce=process.nonce,
            credential=closeout_credential,
            role="formal-closeout-owner",
            native_helper=helper,
        )
        assert closeout.request("STATUS", {}).record["status"] == "PASS"
    finally:
        if closeout is not None:
            closeout.close()
        if owner is not None:
            owner.close()
        admin.close()
        os.kill(process.pid, signal.SIGKILL)
        assert process.wait() == 128 + signal.SIGKILL
        process.close()


def test_package_role_delayed_formal_owner_retains_broker_session_before_admin_close(
    tmp_path: Path,
) -> None:
    """Start the exact package role, consume its pidfd grant, then drop admin."""

    owner_nonce = "6" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=_PackageRoleGate(),
        native_helper_authorization=_NativeHelperAuthorization(
            helper,
            helper_fd,
        ),
        **_persistent_spawn_bindings(
            contract_identity=contract_identity,
            failure_path=failure_path,
            owner_nonce=owner_nonce,
        ),
        formal_directories=(
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
        ),
    )
    admin = process.connect_bootstrap_admin()
    try:
        start_response = admin.request(
            "START_FORMAL_LAUNCH_OWNER",
            {"session_id": "formal-owner-session-a001"},
            expected_fd_counts=frozenset({1}),
        )
        handoff_result = start_response.record["result"]
        assert len(start_response.descriptors) == 1
        claim_descriptor = start_response.descriptors[0]
        assert handoff_result["state"] == "PREREGISTERED_LIVE_OWNER"
        assert (
            handoff_result["context_state"]
            == "AWAITING_DELAYED_CONTEXT"
        )
        assert (
            handoff_result["registration_confirmation"]["state"]
            == "EXACT_OWNER_SESSION_LIVE"
        )
        assert (
            handoff_result["ready"]["status"]
            == "BROKER_SESSION_RETAINED"
        )
        assert handoff_result["grant"]["role"] == "formal-launch-owner"
        assert (
            handoff_result["grant"]["credential_sha256"]
            == handoff_result["ready"]["broker_grant"][
                "credential_sha256"
            ]
        )
        assert "credential" not in handoff_result
        assert "broker_nonce" not in handoff_result
        assert handoff_result["claim_identity"]["size_bytes"] == 64
        assert handoff_result["claim_identity"]["seal_mask"] == (
            helper.final_seal_mask
        )
        owner_pid = handoff_result["owner_actor"]["pid"]
        assert broker.process_starttime(owner_pid) == (
            handoff_result["owner_actor"]["starttime"]
        )
        claimant_pidfd, _method = broker.open_pidfd(os.getpid())
        try:
            registration = admin.register_formal_launch_claimant(
                {
                    "claim_identity": handoff_result[
                        "claim_identity"
                    ],
                    "expected_peer": broker.process_identity(),
                },
                pidfd=claimant_pidfd,
            ).record["result"]
        finally:
            os.close(claimant_pidfd)
        assert registration["state"] == "CLAIMANT_REGISTERED"
        admin.close_session()
        # The package actor remains live after the one bootstrap-admin grant
        # is gone; no publication or authority record was created.
        assert broker.process_starttime(owner_pid) == (
            handoff_result["owner_actor"]["starttime"]
        )
        parent_descriptor = os.open(
            endpoint_path.parent,
            os.O_RDONLY
            | os.O_CLOEXEC
            | os.O_DIRECTORY
            | os.O_NOFOLLOW,
        )
        claimed: formal_orchestrator.ClaimedOwnerSession | None = None
        try:
            claimed = (
                formal_orchestrator.claim_delayed_formal_launch_owner(
                    broker_module=broker,
                    broker_parent_descriptor=parent_descriptor,
                    broker_endpoint_name=endpoint_path.name,
                    broker_actor={
                        "schema_version": broker.ACTOR_SCHEMA,
                        **process.actor,
                    },
                    broker_nonce=process.nonce,
                    claim_descriptor=claim_descriptor,
                    claim_identity=handoff_result["claim_identity"],
                    native_helper=helper,
                )
            )
            assert claimed.actor == handoff_result["owner_actor"]
            assert claimed.claim_identity == handoff_result[
                "claim_identity"
            ]
        finally:
            os.close(parent_descriptor)
            os.close(claim_descriptor)
            if claimed is not None:
                claimed.close()
        assert process.wait() == 2
    finally:
        admin.close()
        if not process._waited:  # noqa: SLF001
            os.kill(process.pid, signal.SIGKILL)
            assert process.wait() == 128 + signal.SIGKILL
        process.close()


def test_claimed_package_owner_publishes_admission_and_bound_selection(
    tmp_path: Path,
) -> None:
    """One package actor owns admission and selection PREPARE/BIND/COMMIT."""

    owner_nonce = "7" * 64
    formal_root = tmp_path / "campaign/formal-ab16/artifacts"
    formal_root.parent.mkdir(parents=True)
    profile_record = {
        "launch_ready": True,
        "profile_sha256": "9" * 64,
    }
    profile_raw = broker.canonical_json_bytes(profile_record)
    profile_path = tmp_path / "campaign/resource-budget-profile.json"
    profile_path.write_bytes(profile_raw)
    profile_path.chmod(0o444)
    profile_identity = {
        "mode": 0o444,
        "path": str(profile_path),
        "sha256": hashlib.sha256(profile_raw).hexdigest(),
        "size_bytes": len(profile_raw),
    }
    formal_contract_record = {
        "authority": dict(broker.FALSE_AUTHORITY_BOUNDARY),
        "budget_profile_identity": dict(profile_identity),
        "budget_profile_sha256": profile_record["profile_sha256"],
        "category_limits": dict(ROOT_LIMITS),
        "fixed_overhead_category_limits": {
            category: 0 for category in ROOT_LIMITS
        },
        "root_path": str(formal_root),
        "run_nonce": "campaign",
        "schema_version": (
            "noncert-cuts-ab16-formal-root-budget-contract-v1"
        ),
    }
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        extra_directories=("formal-attempt-a001",),
        formal_contract_record=formal_contract_record,
        formal_root=formal_root,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    bindings = _persistent_spawn_bindings(
        contract_identity=contract_identity,
        failure_path=failure_path,
        owner_nonce=owner_nonce,
    )
    bindings["formal_artifact_contracts"] = (
        {
            "artifact_class": "metadata",
            "label": "formal launch admission",
            "maximum_bytes": 64 * 1024,
            "path": "formal-launch-admission-a001.json",
            "required_on_success": True,
        },
        {
            "artifact_class": "metadata",
            "label": "formal selection",
            "maximum_bytes": 64 * 1024,
            "path": "formal-attempt-a001/selection.json",
            "required_on_success": True,
        },
    )
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=_PackageRoleGate(),
        native_helper_authorization=_NativeHelperAuthorization(
            helper,
            helper_fd,
        ),
        **bindings,
            formal_directories=(
                {"mode_octal": "0700", "path": "channels"},
                {
                    "mode_octal": "0700",
                    "path": "formal-attempt-a001",
                },
                {
                    "mode_octal": "0700",
                    "path": "channels/budget-journal",
                },
            ),
    )
    fixture = _formal_fixture(
        tmp_path,
        formal_root_contract_identity=contract_identity,
        resource_budget_profile_identity=profile_identity,
    )
    assert (
        formal_orchestrator.launch_validator.validate_formal_context(
            fixture.context
        )
        == fixture.context
    )
    admin = process.connect_bootstrap_admin()
    claim_descriptor = -1
    parent_descriptor = -1
    claimed: formal_orchestrator.ClaimedOwnerSession | None = None
    try:
        started = admin.request(
            "START_FORMAL_LAUNCH_OWNER",
            {"session_id": "formal-owner-session-a001"},
            expected_fd_counts=frozenset({1}),
        )
        handoff_result = started.record["result"]
        claim_descriptor = started.descriptors[0]
        claimant_pidfd, _method = broker.open_pidfd(os.getpid())
        try:
            admin.register_formal_launch_claimant(
                {
                    "claim_identity": handoff_result[
                        "claim_identity"
                    ],
                    "expected_peer": broker.process_identity(),
                },
                pidfd=claimant_pidfd,
            )
        finally:
            os.close(claimant_pidfd)
        admin.close_session()
        parent_descriptor = os.open(
            endpoint_path.parent,
            os.O_RDONLY
            | os.O_CLOEXEC
            | os.O_DIRECTORY
            | os.O_NOFOLLOW,
        )
        transport = formal_orchestrator.FormalLaunchClaimTransport(
            broker_module=broker,
            broker_parent_descriptor=parent_descriptor,
            broker_endpoint_name=endpoint_path.name,
            broker_actor={
                "schema_version": broker.ACTOR_SCHEMA,
                **process.actor,
            },
            broker_nonce=process.nonce,
            claim_descriptor=claim_descriptor,
            claim_identity=handoff_result["claim_identity"],
            native_helper=helper,
        )
        claimed = transport.claim()
        assert transport.consumed is True
        assert claimed.actor == handoff_result["owner_actor"]
        claimed.deliver_context(fixture.context)

        admission_draft = formal_orchestrator.build_admission_draft(
            fixture.context,
            claimed.actor,
        )
        admission_response = claimed.request(
            sequence=1,
            kind="admission",
            draft=admission_draft,
        )
        admission, admission_identity = (
            formal_orchestrator.launch_validator.read_canonical_record(
                formal_root / "formal-launch-admission-a001.json",
                expected_identity=admission_response[
                    "artifact_identity"
                ],
                label="formal launch admission",
            )
        )
        supervisor_pidfd, _supervisor_pidfd_method = broker.open_pidfd(
            os.getpid()
        )
        try:
            supervisor_session = claimed.register_formal_supervisor(
                {
                    "expected_peer": broker.process_identity(),
                    "package_id": fixture.context["package_id"],
                },
                pidfd=supervisor_pidfd,
            )
        finally:
            os.close(supervisor_pidfd)
        assert supervisor_session["package_id"] == fixture.context["package_id"]
        assert supervisor_session["expected_peer"] == broker.process_identity()
        guardian_ready = dict(fixture.guardian_ready)
        guardian_ready["formal_admission_identity"] = (
            admission_identity
        )
        prepared = claimed.prepare_bound_selection(
            admission=admission,
            admission_identity=admission_identity,
            guardian_ready=guardian_ready,
            guardian_ready_identity=fixture.guardian_ready_identity,
            attempt_consumption=fixture.attempt_consumption,
            attempt_consumption_identity=(
                fixture.attempt_consumption_identity
            ),
        )
        committed = claimed.commit_bound_selection(
            prepared_selection_identity=prepared[
                "artifact_identity"
            ],
        )
        selection_path = formal_root / "formal-attempt-a001/selection.json"
        selection, selection_identity = (
            formal_orchestrator.launch_validator.read_canonical_record(
                selection_path,
                expected_identity=committed["artifact_identity"],
                label="formal selection",
            )
        )
        assert selection_identity == committed["artifact_identity"]
        assert selection["publisher"]["actor"] == claimed.actor
        assert admission["publisher"]["actor"] == claimed.actor
        assert b'"credential"' not in selection_path.read_bytes()
        assert '"credential":' not in json.dumps(
            prepared,
            sort_keys=True,
        )
        assert '"credential":' not in json.dumps(
            committed,
            sort_keys=True,
        )
        claimed.complete_handoff()
    finally:
        if claimed is not None:
            claimed.close()
        if parent_descriptor >= 0:
            os.close(parent_descriptor)
        if claim_descriptor >= 0:
            os.close(claim_descriptor)
        admin.close()
        os.kill(process.pid, signal.SIGKILL)
        assert process.wait() == 128 + signal.SIGKILL
        process.close()


def test_selected_loader_fd8_fd9_reaches_same_owner_bound_selection(
    tmp_path: Path,
) -> None:
    """Exercise the real selected loader and orchestrator main with no mock."""

    # AF_UNIX names are capped at 108 bytes; pytest's descriptive basetemp can
    # exceed that before the fixed broker suffix is appended.
    pytest_tmp_path = tmp_path
    tmp_path = Path(tempfile.mkdtemp(prefix="ab16-e2e-", dir="/tmp"))

    def file_identity(path: Path, *, mode: int | None = None) -> dict[str, object]:
        raw = path.read_bytes()
        observed_mode = stat.S_IMODE(
            os.stat(path, follow_symlinks=False).st_mode
        )
        return {
            "mode": observed_mode if mode is None else mode,
            "path": str(path.absolute()),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }

    def publish_readonly(path: Path, raw: bytes, *, mode: int = 0o444) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            mode,
        )
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                assert written > 0
                view = view[written:]
            os.fsync(descriptor)
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    owner_nonce = "8" * 64
    campaign = tmp_path / "campaign"
    formal_root = campaign / "formal-ab16/artifacts"
    formal_root.parent.mkdir(parents=True)
    snapshot_root = campaign / "campaign-authority/repository-snapshot"
    snapshot_research = (
        snapshot_root / "docs/research/noncert_cuts_ab16_20260724"
    )
    payload = campaign / "campaign-authority/package/payload"
    snapshot_research.mkdir(parents=True)
    payload.mkdir(parents=True)
    (snapshot_root / "src").mkdir()
    for relative in (Path("docs/__init__.py"), Path("docs/research/__init__.py")):
        source = ROOT / relative
        if source.exists():
            target = snapshot_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    (snapshot_root / "PROJECT_LOCK.md").write_bytes(
        (ROOT / "PROJECT_LOCK.md").read_bytes()
    )
    for source in sorted(RESEARCH.glob("*.py")):
        target = snapshot_research / source.name
        target.write_bytes(source.read_bytes())

    bounded_supervisor_source = b'''\
from __future__ import annotations
import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time

@dataclass(frozen=True)
class SelectedDirectResult:
    returncode: int
    stderr: bytes
    stdout: bytes

def _canonical(value):
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\\n"
    ).encode("utf-8")

def _identity(path):
    target = Path(path)
    raw = target.read_bytes()
    return {
        "path": str(target),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }

def _process_identity():
    pid = os.getpid()
    raw = Path(f"/proc/{pid}/stat").read_text("ascii")
    closing = raw.rfind(")")
    if closing < 0:
        raise RuntimeError("bounded supervisor process identity is malformed")
    fields = raw[closing + 2 :].split()
    if len(fields) < 20:
        raise RuntimeError("bounded supervisor process identity is truncated")
    return {
        "pid": pid,
        "pid_starttime": int(fields[19]),
        "uid": os.getuid(),
    }

def _open_pidfd(pid):
    primitive = getattr(os, "pidfd_open", None)
    if primitive is not None:
        return primitive(pid, 0)
    libc = ctypes.CDLL(None, use_errno=True)
    primitive = getattr(libc, "pidfd_open", None)
    if primitive is None:
        raise RuntimeError("bounded supervisor lacks pidfd_open")
    primitive.argtypes = [ctypes.c_int, ctypes.c_uint]
    primitive.restype = ctypes.c_int
    descriptor = int(primitive(pid, 0))
    if descriptor < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return descriptor

def _publish(path, value):
    raw = _canonical(value)
    target = Path(path)
    descriptor = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short bounded fixture publication")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return _identity(target)

def run_selected_direct_result(
    *,
    context,
    role,
    role_argv,
    timeout_seconds,
    cancel_requested=None,
    formal_launch_claimant_registrar=None,
    **_forbidden,
):
    if (
        role != "formal-supervisor"
        or tuple(role_argv)
        != ("--campaign-dir", str(context["campaign_dir"]))
        or formal_launch_claimant_registrar is None
        or not callable(
            getattr(
                formal_launch_claimant_registrar,
                "register_formal_supervisor",
                None,
            )
        )
        or _forbidden
    ):
        raise RuntimeError("bounded supervisor invocation drifted")
    expected_peer = _process_identity()
    pidfd = _open_pidfd(os.getpid())
    try:
        session = formal_launch_claimant_registrar.register_formal_supervisor(
            {
                "expected_peer": expected_peer,
                "package_id": context["package_id"],
            },
            pidfd=pidfd,
        )
    finally:
        os.close(pidfd)
    if (
        session.get("expected_peer") != expected_peer
        or session.get("package_id") != context["package_id"]
    ):
        raise RuntimeError("bounded supervisor session binding drifted")
    campaign = Path(context["campaign_dir"])
    templates = json.loads(
        (campaign / "bounded-supervisor-inputs.json").read_text("utf-8")
    )
    admission_path = Path(context["formal_admission_path"])
    deadline = time.monotonic() + min(float(timeout_seconds), 10.0)
    while not admission_path.exists():
        if cancel_requested is not None and cancel_requested():
            raise RuntimeError("bounded supervisor was cancelled")
        if time.monotonic() >= deadline:
            raise RuntimeError("bounded supervisor admission wait expired")
        time.sleep(0.01)
    guardian = dict(templates["guardian_ready"])
    guardian["formal_admission_identity"] = _identity(admission_path)
    _publish(context["guardian_ready_path"], guardian)
    attempt_path = (
        Path(context["formal_attempt_dir"]) / "attempt-consumption.json"
    )
    _publish(attempt_path, templates["attempt_consumption"])
    selection_path = Path(context["formal_selection_path"])
    while not selection_path.exists():
        if cancel_requested is not None and cancel_requested():
            raise RuntimeError("bounded supervisor was cancelled")
        if time.monotonic() >= deadline:
            raise RuntimeError("bounded supervisor selection wait expired")
        time.sleep(0.01)
    result = {
        "formal_selection_identity": _identity(selection_path),
        "outcome": "INCOMPLETE",
    }
    return SelectedDirectResult(
        returncode=2,
        stderr=b"",
        stdout=_canonical(result),
    )
'''
    bounded_supervisor_path = snapshot_research / "ab16_formal_campaign_v1.py"
    bounded_supervisor_path.write_bytes(bounded_supervisor_source)
    bounded_supervisor_identity = file_identity(
        bounded_supervisor_path
    )

    selected_loader = payload / "tool.ab16_formal_loader_v1.py"
    selected_authority = payload / "tool.ab16_authority_v2.py"
    selected_wrapper = payload / "tool.ab16_native_budget_helper_v1.py"
    selected_helper = payload / "system.native_budget_helper.bin"
    selected_loader.write_bytes(
        (RESEARCH / "ab16_formal_loader_v1.py").read_bytes()
    )
    selected_loader.chmod(0o600)
    selected_wrapper.write_bytes(
        (RESEARCH / "ab16_native_budget_helper_v1.py").read_bytes()
    )
    selected_wrapper.chmod(0o600)
    selected_helper.write_bytes(
        (RESEARCH / "ab16_native_budget_helper_x86_64_v1.so").read_bytes()
    )
    selected_helper.chmod(0o555)
    authority_source = b'''\
from __future__ import annotations
import hashlib
import json
from pathlib import Path

class AuthorityError(RuntimeError):
    pass

class Snapshot:
    def __init__(self, path, data, metadata):
        self.path = Path(path)
        self.data = data
        self.device = metadata.st_dev
        self.inode = metadata.st_ino
        self.mode = metadata.st_mode & 0o7777
        self.size_bytes = len(data)
        self.sha256 = hashlib.sha256(data).hexdigest()

def canonical_json(value):
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\\n"
    ).encode("utf-8")

def strict_loads(raw, label):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AuthorityError(f"{label}: duplicate key")
            result[key] = value
        return result
    value = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda token: (_ for _ in ()).throw(
            AuthorityError(f"{label}: invalid constant {token}")
        ),
    )
    if canonical_json(value) != raw:
        raise AuthorityError(f"{label}: noncanonical JSON")
    return value

def snapshot_regular(path):
    target = Path(path).absolute()
    return Snapshot(target, target.read_bytes(), target.stat())

def detached_identity(snapshot):
    return {
        "path": str(snapshot.path),
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size_bytes,
    }

def validate_formal_budget_runtime(value, *, replay_artifacts):
    if not replay_artifacts or type(value) is not dict:
        raise AuthorityError("formal budget runtime replay drifted")
    return dict(value)

def _context(campaign_dir):
    path = Path(campaign_dir) / "bounded-formal-context.json"
    return strict_loads(path.read_bytes(), "bounded formal context")

def replay_formal_launch_context(*, campaign_dir):
    return _context(campaign_dir)

def replay_loader_context(
    *,
    campaign_dir,
    role,
    role_module,
    role_path,
):
    context = _context(campaign_dir)
    source = Path(context["snapshot_root"]) / role_path
    return {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "campaign_dir": str(Path(campaign_dir).absolute()),
        "campaign_root_identity": context["campaign_root_identity"],
        "package_id": context["package_id"],
        "package_manifest_identity": context["package_manifest_identity"],
        "package_seal_identity": context["package_seal_identity"],
        "repository_head": context["repository_head"],
        "repository_tree": "f" * 40,
        "role": role,
        "role_module": role_module,
        "role_source_identity": detached_identity(snapshot_regular(source)),
        "schema_version": "noncert-cuts-ab16-formal-loader-context-v1",
        "snapshot_materialization_identity": (
            context["snapshot_materialization_identity"]
        ),
        "snapshot_root": context["snapshot_root"],
        "status": "PASS",
    }
'''
    selected_authority.write_bytes(authority_source)
    selected_authority.chmod(0o600)

    python_path = Path(sys.executable).resolve(strict=True)
    selected_identities = {
        "authority": file_identity(selected_authority),
        "loader": file_identity(selected_loader),
        "native_helper": file_identity(selected_helper),
        "native_helper_wrapper": file_identity(selected_wrapper),
        "python": file_identity(python_path),
    }
    retained_selected = {
        role: os.open(
            str(identity["path"]),
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        for role, identity in selected_identities.items()
    }

    profile_record = {
        "launch_ready": True,
        "profile_sha256": "9" * 64,
    }
    profile_raw = broker.canonical_json_bytes(profile_record)
    profile_path = campaign / "resource-budget-profile.json"
    publish_readonly(profile_path, profile_raw)
    profile_identity = file_identity(profile_path)
    formal_contract_record = {
        "authority": dict(broker.FALSE_AUTHORITY_BOUNDARY),
        "budget_profile_identity": dict(profile_identity),
        "budget_profile_sha256": profile_record["profile_sha256"],
        "category_limits": dict(ROOT_LIMITS),
        "fixed_overhead_category_limits": {
            category: 0 for category in ROOT_LIMITS
        },
        "root_path": str(formal_root),
        "run_nonce": "campaign",
        "schema_version": (
            "noncert-cuts-ab16-formal-root-budget-contract-v1"
        ),
    }
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        extra_directories=("formal-attempt-a001",),
        formal_contract_record=formal_contract_record,
        formal_root=formal_root,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    bindings = _persistent_spawn_bindings(
        contract_identity=contract_identity,
        failure_path=failure_path,
        owner_nonce=owner_nonce,
    )
    bindings["formal_artifact_contracts"] = (
        {
            "artifact_class": "metadata",
            "label": "formal launch admission",
            "maximum_bytes": 64 * 1024,
            "path": "formal-launch-admission-a001.json",
            "required_on_success": True,
        },
        {
            "artifact_class": "metadata",
            "label": "formal selection",
            "maximum_bytes": 64 * 1024,
            "path": "formal-attempt-a001/selection.json",
            "required_on_success": True,
        },
    )
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=_PackageRoleGate(
            retained_descriptors=tuple(retained_selected.values()),
        ),
        native_helper_authorization=_NativeHelperAuthorization(
            helper,
            helper_fd,
        ),
        **bindings,
        formal_directories=(
            {"mode_octal": "0700", "path": "channels"},
            {
                "mode_octal": "0700",
                "path": "formal-attempt-a001",
            },
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
        ),
    )
    fixture = _formal_fixture(
        tmp_path,
        formal_root_contract_identity=contract_identity,
        resource_budget_profile_identity=profile_identity,
    )
    endpoint_metadata = os.stat(endpoint_path, follow_symlinks=False)
    broker_actor = {
        "pid": process.actor["pid"],
        "pid_starttime": process.actor["pid_starttime"],
        "uid": process.actor["uid"],
    }
    endpoint_identity = {
        "device": endpoint_metadata.st_dev,
        "inode": endpoint_metadata.st_ino,
        "mode": stat.S_IMODE(endpoint_metadata.st_mode),
        "path": str(endpoint_path),
        "uid": endpoint_metadata.st_uid,
    }
    selected_transport = {
        "owner": dict(broker_actor),
        "roles": {
            role: {
                "descriptor": retained_selected[role],
                "mode": selected_identities[role]["mode"],
                "package_path": (
                    formal_orchestrator.launch_validator.
                    SELECTED_FD_TRANSPORT_PACKAGE_PATHS[role]
                ),
                "proc_fd_path": (
                    f"/proc/{broker_actor['pid']}/fd/"
                    f"{retained_selected[role]}"
                ),
                "sha256": selected_identities[role]["sha256"],
                "size_bytes": selected_identities[role]["size_bytes"],
            }
            for role in sorted(selected_identities)
        },
        "schema_version": (
            formal_orchestrator.launch_validator.SELECTED_FD_TRANSPORT_SCHEMA
        ),
    }
    context = dict(fixture.context)
    context["snapshot_root"] = str(snapshot_root)
    context["formal_orchestrator_identity"] = {
        key: value
        for key, value in file_identity(
            snapshot_research / "ab16_formal_orchestrator_v1.py"
        ).items()
        if key != "mode"
    }
    context["formal_loader_identity"] = {
        key: value
        for key, value in selected_identities["loader"].items()
        if key != "mode"
    }
    context["python_identity"] = {
        key: value
        for key, value in selected_identities["python"].items()
        if key != "mode"
    }
    context["native_helper_identity"] = {
        key: value
        for key, value in selected_identities["native_helper"].items()
        if key != "mode"
    }
    context["native_helper_wrapper_identity"] = {
        key: value
        for key, value in selected_identities[
            "native_helper_wrapper"
        ].items()
        if key != "mode"
    }
    snapshot_plan = snapshot_root / "bounded-snapshot-plan.json"
    publish_readonly(
        snapshot_plan,
        broker.canonical_json_bytes(
            {
                "formal_campaign_identity": (
                    bounded_supervisor_identity
                ),
                "status": "PLANNED_FIXTURE",
            }
        ),
    )
    context["snapshot_materialization_identity"] = {
        key: value
        for key, value in file_identity(snapshot_plan).items()
        if key != "mode"
    }
    literal = bootstrap.SELECTED_BYTE_LAUNCH_V2
    literal_raw = literal.encode("utf-8")
    context["selected_byte_launch_identity"] = {
        "sha256": hashlib.sha256(literal_raw).hexdigest(),
        "size_bytes": len(literal_raw),
    }
    context["selected_fd_transport"] = selected_transport
    context["budget_broker_endpoint_identity"] = endpoint_identity
    runtime = dict(context["formal_budget_runtime"])
    runtime["broker_actor_identity"] = dict(broker_actor)
    runtime["broker_endpoint_identity"] = dict(endpoint_identity)
    runtime["broker_nonce"] = process.nonce
    context["formal_budget_runtime"] = runtime
    selected_argument = json.dumps(
        selected_identities,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    for field in ("outer_spec", "guardian_spec"):
        spec = dict(context[field])
        argv = list(spec["selected_byte_argv"])
        argv[4] = literal
        argv[6] = selected_argument
        spec["selected_byte_argv"] = argv
        spec["selected_fd_transport"] = selected_transport
        spec["budget_broker_endpoint_identity"] = endpoint_identity
        spec["working_directory"] = str(snapshot_root)
        if field == "outer_spec":
            spec["loader_identity"] = context["formal_loader_identity"]
            spec["python_identity"] = context["python_identity"]
        context[field] = spec
    context_path = campaign / "bounded-formal-context.json"
    publish_readonly(
        context_path,
        broker.canonical_json_bytes(context),
    )
    publish_readonly(
        campaign / "bounded-supervisor-inputs.json",
        broker.canonical_json_bytes(
            {
                "attempt_consumption": fixture.attempt_consumption,
                "guardian_ready": fixture.guardian_ready,
            }
        ),
    )

    admin = process.connect_bootstrap_admin()
    claim_descriptor = -1
    try:
        started = admin.request(
            "START_FORMAL_LAUNCH_OWNER",
            {"session_id": "formal-owner-session-a001"},
            expected_fd_counts=frozenset({1}),
        )
        handoff_result = started.record["result"]
        claim_descriptor = started.descriptors[0]
        before = {
            path.relative_to(campaign).as_posix()
            for path in campaign.rglob("*")
            if path.is_file()
        }
        result = formal_campaign.run_selected_direct_result(
            context=context,
            role="formal-orchestrator",
            role_argv=(
                "--selected",
                "--campaign-dir",
                str(campaign),
            ),
            timeout_seconds=20.0,
            formal_launch_claim_descriptor=claim_descriptor,
            formal_launch_claim_identity=handoff_result[
                "claim_identity"
            ],
            formal_launch_claimant_registrar=admin,
        )
        admin.close_session()
        assert result.returncode == 2
        assert result.stderr == b""
        parsed = json.loads(result.stdout)
        assert broker.canonical_json_bytes(parsed) == result.stdout
        assert parsed["status"] == "INCOMPLETE"
        assert parsed["owner_handoff_complete"] is True
        admission_path = formal_root / "formal-launch-admission-a001.json"
        selection_path = formal_root / "formal-attempt-a001/selection.json"
        admission_raw = admission_path.read_bytes()
        selection_raw = selection_path.read_bytes()
        admission = json.loads(admission_raw)
        selection = json.loads(selection_raw)
        assert broker.canonical_json_bytes(admission) == admission_raw
        assert broker.canonical_json_bytes(selection) == selection_raw
        assert admission["publisher"]["actor"] == selection["publisher"]["actor"]
        assert admission["publisher"]["actor"] == parsed["owner_actor"]
        after = {
            path.relative_to(campaign).as_posix()
            for path in campaign.rglob("*")
            if path.is_file()
        }
        created = after - before
        expected_records = {
            "formal-ab16/artifacts/formal-attempt-a001/"
            "attempt-consumption.json",
            "formal-ab16/artifacts/formal-attempt-a001/selection.json",
            "formal-ab16/artifacts/formal-launch-admission-a001.json",
            "formal-ab16/artifacts/outer-guardian-ready-a001.json",
        }
        assert expected_records <= created
        assert all(
            relative in expected_records
            or relative.startswith(
                "formal-ab16/artifacts/channels/budget-journal/"
                "segment-"
            )
            for relative in created
        )
        assert not any(
            token in relative
            for relative in created
            for token in ("gate-b", "solver", "systemd", "unit-")
        )
    finally:
        if claim_descriptor >= 0:
            os.close(claim_descriptor)
        admin.close()
        os.kill(process.pid, signal.SIGKILL)
        assert process.wait() == 128 + signal.SIGKILL
        process.close()
        for descriptor in retained_selected.values():
            try:
                os.close(descriptor)
            except OSError:
                pass
        shutil.rmtree(tmp_path)
        assert pytest_tmp_path.exists()


def test_socket_descriptor_adoption_consumes_both_fds_when_socket_wrap_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    left, right = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    descriptor = left.detach()
    before = len(os.listdir("/proc/self/fd"))

    def fail_socket_wrap(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected socket wrapper failure")

    monkeypatch.setattr(broker.socket, "socket", fail_socket_wrap)
    try:
        with pytest.raises(
            RuntimeError,
            match="injected socket wrapper failure",
        ):
            broker._consume_socket_descriptor(  # noqa: SLF001
                descriptor,
                label="fault-injected broker socket",
            )
        with pytest.raises(OSError):
            os.fstat(descriptor)
        assert len(os.listdir("/proc/self/fd")) == before - 1
    finally:
        right.close()


def test_manager_openfile_arm_session_is_allocation_bound(
    tmp_path: Path,
) -> None:
    owner_nonce = "1" * 64
    supervisor_credential = "2" * 64
    unit_credential = "3" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
    )
    helper, helper_fd = _native_helper()
    process = broker.spawn_persistent_broker_from_transfer(
        account=account,
        ownership_handoff=handoff,
        fixed_purpose_reservations=reservations,
        fixed_purpose_handoffs=reservation_handoffs,
        control_parent_capability=control_parent,
        control_parent_handoff=control_handoff,
        endpoint_path=endpoint_path,
        owner_nonce=owner_nonce,
        package_authorization=_PackageRoleGate(),
        native_helper_authorization=_NativeHelperAuthorization(
            helper,
            helper_fd,
        ),
        **_persistent_spawn_bindings(
            contract_identity=contract_identity,
            failure_path=failure_path,
            owner_nonce=owner_nonce,
        ),
        supervisor_credential=supervisor_credential,
        expected_supervisor_peer=broker.process_identity(),
        formal_directories=(
            {"mode_octal": "0700", "path": "arms"},
            {"mode_octal": "0700", "path": "channels"},
            {"mode_octal": "0700", "path": "closeout"},
            {"mode_octal": "0700", "path": "formal-closure"},
            {"mode_octal": "0700", "path": "arms/arm-01"},
            {
                "mode_octal": "0700",
                "path": "channels/budget-journal",
            },
        ),
        arm_directories={
            "arm-01": (
                {"mode_octal": "0700", "path": "arms/arm-01"},
            ),
        },
    )
    supervisor = process.connect(
        credential=supervisor_credential,
        role="supervisor",
    )
    selection = {
        "path": str((tmp_path / "formal-selection.json").absolute()),
        "sha256": "4" * 64,
        "size_bytes": 1,
    }
    supervisor.request(
        "BIND_SELECTION",
        {"selection_identity": selection},
    )
    allocation = supervisor.request(
        "ALLOCATE_ARM",
        {
            "arm_slot": "arm-01",
            "category_limits": {"normal": 64 * 1024},
        },
    ).record["result"]["allocation_identity"]
    attempt = {
        "path": str((tmp_path / "attempt.json").absolute()),
        "sha256": "5" * 64,
        "size_bytes": 1,
    }
    guardian_ready = {
        "path": str((tmp_path / "guardian-ready.json").absolute()),
        "sha256": "6" * 64,
        "size_bytes": 1,
    }
    manager_epoch = {"sha256": "7" * 64, "size_bytes": 1}
    preregistered = supervisor.preregister_manager_openfile_arm_grant(
        {
            "allocation_identity": allocation,
            "arm_slot": "arm-01",
            "attempt_consumption_identity": attempt,
            "credential": unit_credential,
            "manager_epoch_identity": manager_epoch,
            "selection_identity": selection,
            "unit_name": "ab16-organic-arm-01.service",
        }
    ).record["result"]
    assert preregistered == {
        "schema_version": broker.MANAGER_OPENFILE_ARM_GRANT_SCHEMA,
        "allocation_identity": allocation,
        "arm_slot": "arm-01",
        "attempt_consumption_identity": attempt,
        "credential_sha256": hashlib.sha256(
            unit_credential.encode("ascii")
        ).hexdigest(),
        "manager_epoch_identity": manager_epoch,
        "selection_identity": selection,
        "state": "UNBOUND",
        "unit_name": "ab16-organic-arm-01.service",
    }
    manager_connection = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    endpoint_parent = broker._open_absolute_directory_no_symlinks(  # noqa: SLF001
        endpoint_path.parent
    )
    try:
        manager_connection.connect(
            f"/proc/self/fd/{endpoint_parent}/{endpoint_path.name}"
        )
    finally:
        os.close(endpoint_parent)
    result_read, result_write = os.pipe2(os.O_CLOEXEC)
    child_pid = os.fork()
    if child_pid == 0:
        os.close(result_read)
        supervisor.close()
        try:
            selected = broker.attach_manager_openfile_arm_supervisor(
                manager_connection.detach(),
                broker_actor=process.actor,
                broker_nonce=process.nonce,
                credential=unit_credential,
                manager_epoch_identity=manager_epoch,
                selection_identity=selection,
                allocation_identity=allocation,
                arm_slot="arm-01",
                attempt_consumption_identity=attempt,
                unit_name="ab16-organic-arm-01.service",
                native_helper=helper,
            )
            selected.request("STATUS", {})
            published = selected.request(
                "PUBLISH",
                {
                    "arm_slot": "arm-01",
                    "artifact_class": "normal",
                    "channel": None,
                    "label": "test supervisor origin",
                    "maximum_bytes": 64,
                    "payload_hex": b"supervisor-origin".hex(),
                    "relative_path": (
                        "arms/arm-01/supervisor-origin.json"
                    ),
                    "sequence": None,
                },
            ).record["result"]
            try:
                selected.request(
                    "ALLOCATE_ARM",
                    {
                        "arm_slot": "arm-01",
                        "category_limits": {"normal": 1},
                    },
                )
            except broker.BrokerProtocolError as exc:
                denied = exc.code
            else:
                denied = "NOT_DENIED"
            os.write(
                result_write,
                (
                    f"PASS:{selected.grant.role}:"
                    f"{selected.grant.arm_slot}:"
                    f"{published['sha256']}:{denied}"
                ).encode(),
            )
            selected.close()
        except BaseException as exc:
            os.write(
                result_write,
                f"FAIL:{type(exc).__name__}:{exc}".encode(),
            )
        finally:
            os.close(result_write)
        os._exit(0)
    manager_connection.close()
    os.close(result_write)
    pidfd, pidfd_method = broker.open_pidfd(child_pid)
    try:
        bound = supervisor.bind_manager_openfile_arm_grant(
            {
                "allocation_identity": allocation,
                "application_peer": broker.process_identity(child_pid),
                "arm_slot": "arm-01",
                "attempt_consumption_identity": attempt,
                "credential": unit_credential,
                "guardian_ready_identity": guardian_ready,
                "pidfd_method": pidfd_method,
                "selection_identity": selection,
            },
            pidfd=pidfd,
        ).record["result"]
        assert bound["schema_version"] == (
            broker.MANAGER_OPENFILE_ARM_GRANT_SCHEMA
        )
        assert bound["state"] == "BOUND"
    finally:
        os.close(pidfd)
    expected_digest = hashlib.sha256(b"supervisor-origin").hexdigest()
    assert os.read(result_read, 4096) == (
        f"PASS:arm-supervisor:arm-01:{expected_digest}:"
        "ACTION_NOT_AUTHORIZED"
    ).encode()
    assert (
        account.root / "arms/arm-01/supervisor-origin.json"
    ).read_bytes() == b"supervisor-origin"
    os.close(result_read)
    assert os.waitpid(child_pid, 0) == (child_pid, 0)
    supervisor.close()
    os.kill(process.pid, signal.SIGKILL)
    assert process.wait() == 128 + signal.SIGKILL
    process.close()


def test_persistent_broker_endpoint_collision_preserves_unknown_node(
    tmp_path: Path,
) -> None:
    owner_nonce = "1" * 64
    (
        account,
        handoff,
        reservations,
        reservation_handoffs,
        control_parent,
        control_handoff,
        endpoint_path,
        contract_identity,
        failure_path,
    ) = (
        _transferred_runtime_account(
        tmp_path,
        owner_nonce=owner_nonce,
        )
    )
    collision = endpoint_path
    collision.write_bytes(b"unknown-endpoint")
    collision.chmod(0o600)
    helper, helper_fd = _native_helper()
    native_authorization = _NativeHelperAuthorization(helper, helper_fd)
    with pytest.raises(broker.BrokerProtocolError):
        broker.spawn_persistent_broker_from_transfer(
            account=account,
            ownership_handoff=handoff,
            fixed_purpose_reservations=reservations,
            fixed_purpose_handoffs=reservation_handoffs,
            control_parent_capability=control_parent,
            control_parent_handoff=control_handoff,
            endpoint_path=endpoint_path,
            owner_nonce=owner_nonce,
            package_authorization=_PackageRoleGate(),
            native_helper_authorization=native_authorization,
            **_persistent_spawn_bindings(
                contract_identity=contract_identity,
                failure_path=failure_path,
                owner_nonce=owner_nonce,
            ),
            supervisor_credential="2" * 64,
            expected_supervisor_peer=broker.process_identity(),
        )
    assert native_authorization.close_count == 1
    assert collision.read_bytes() == b"unknown-endpoint"


def test_broker_endpoint_adapter_rejects_final_join_canonical_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_descriptors = set(os.listdir("/proc/self/fd"))
    control_root = budget.FormalBudgetBroker.create(
        tmp_path / "adapter-canonical",
        category_limits=ROOT_LIMITS,
    )
    control_root.register_directory("control")
    control_parent = control_root.retain_directory(
        "control",
        purpose="formal-control-parent",
    )
    canonical = control_root.root / "control/budget-broker.sock"
    retired = control_root.root / "control/budget-broker.sock.retired"
    endpoint = broker._BoundBrokerEndpoint(  # noqa: SLF001
        control_parent=control_parent,
        absolute_path=canonical,
        retired_absolute_path=retired,
    )
    real_join = guardian._require_directory_join  # noqa: SLF001
    join_count = 0

    def replace_after_final_join(
        absolute: Path,
        anchored_descriptor: int,
    ) -> os.stat_result:
        nonlocal join_count
        join_count += 1
        result = real_join(absolute, anchored_descriptor)
        if join_count == 3:
            canonical.write_bytes(b"broker-final-join-replacement")
        return result

    monkeypatch.setattr(
        guardian,
        "_require_directory_join",
        replace_after_final_join,
    )
    try:
        with pytest.raises(
            broker.BrokerProtocolError,
            match="retirement failed closed",
        ):
            endpoint.retire()
        assert canonical.read_bytes() == b"broker-final-join-replacement"
        assert stat.S_ISSOCK(os.lstat(retired).st_mode)
    finally:
        control_root.close()
    assert set(os.listdir("/proc/self/fd")) == before_descriptors


def test_broker_endpoint_adapter_rejects_final_join_parent_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_descriptors = set(os.listdir("/proc/self/fd"))
    control_root = budget.FormalBudgetBroker.create(
        tmp_path / "adapter-parent",
        category_limits=ROOT_LIMITS,
    )
    control_root.register_directory("control")
    control_parent = control_root.retain_directory(
        "control",
        purpose="formal-control-parent",
    )
    control = control_root.root / "control"
    moved = control_root.root / "control-moved"
    endpoint = broker._BoundBrokerEndpoint(  # noqa: SLF001
        control_parent=control_parent,
        absolute_path=control / "budget-broker.sock",
        retired_absolute_path=control / "budget-broker.sock.retired",
    )
    canonical = control / "budget-broker.sock"
    real_join = guardian._require_directory_join  # noqa: SLF001
    join_count = 0

    def replace_parent_after_final_join(
        absolute: Path,
        anchored_descriptor: int,
    ) -> os.stat_result:
        nonlocal join_count
        join_count += 1
        result = real_join(absolute, anchored_descriptor)
        if join_count == 3:
            control.rename(moved)
            control.mkdir(mode=0o700)
            canonical.write_bytes(b"broker-parent-replacement")
        return result

    monkeypatch.setattr(
        guardian,
        "_require_directory_join",
        replace_parent_after_final_join,
    )
    try:
        with pytest.raises(
            broker.BrokerProtocolError,
            match="retirement failed closed",
        ):
            endpoint.retire()
        assert canonical.read_bytes() == b"broker-parent-replacement"
        assert stat.S_ISSOCK(
            os.lstat(moved / "budget-broker.sock.retired").st_mode
        )
    finally:
        control_root.close()
    assert set(os.listdir("/proc/self/fd")) == before_descriptors


def test_persistent_recovery_rejection_precedes_fork_and_fd_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _spawn_broker(tmp_path)
    descriptors: tuple[int, ...] = ()
    try:
        prepared_result, descriptors = _prepare_recovery(process)
        identities = [os.fstat(descriptor) for descriptor in descriptors]
        gate = _PackageRoleGate(accepted=False)
        monkeypatch.setattr(
            recovery.os,
            "fork",
            lambda: (_ for _ in ()).throw(
                AssertionError("recovery fork preceded package authorization")
            ),
        )
        with pytest.raises(RuntimeError, match="not PASS"):
            recovery.spawn_persistent_recovery(
                broker_process=process,
                prepared_result=prepared_result,
                descriptors=descriptors,
                package_authorization=gate,
            )
        assert gate.calls == [recovery.PACKAGE_ROLE]
        assert [os.fstat(descriptor) for descriptor in descriptors] == identities
        exit_result = process.request("EXIT", {}).record["result"]
        assert exit_result["state"] == "BROKER_EXIT_ACCEPTED"
        assert (
            exit_result["root_inventory"]["schema_version"]
            == broker.ROOT_INVENTORY_SCHEMA
        )
        assert process.wait() == 0
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
        _wait_and_close_broker(process, expected={0, 2})
