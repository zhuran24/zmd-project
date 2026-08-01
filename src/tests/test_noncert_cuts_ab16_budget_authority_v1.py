from __future__ import annotations

import importlib.util
import hashlib
import os
from pathlib import Path
import stat
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "noncert_cuts_ab16_20260724"
    / "ab16_budget_authority_v1.py"
)
SPEC = importlib.util.spec_from_file_location("noncert_cuts_ab16_budget_authority_v1_tested", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
BUDGET = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BUDGET
SPEC.loader.exec_module(BUDGET)


def _broker(tmp_path: Path) -> object:
    return BUDGET.FormalBudgetBroker.create(
        tmp_path / "formal",
        category_limits={
            "normal": 128,
            "metadata": 128,
            "closeout": 128,
        },
    )


def test_root_arm_arithmetic_is_single_authority_and_nonrefundable(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        assert broker.total_bytes == 384
        arm = broker.allocate_arm(
            "arm-01",
            category_limits={"normal": 64, "metadata": 32, "closeout": 16},
        )
        assert arm["reserved_bytes"] == 112
        assert broker.remaining_by_class() == {
            "closeout": 112,
            "metadata": 96,
            "normal": 64,
        }
        with pytest.raises(BUDGET.BudgetContractError) as duplicate:
            broker.allocate_arm("arm-01", category_limits={"normal": 1})
        assert duplicate.value.code == "ARM_ALREADY_ALLOCATED"
        with pytest.raises(BUDGET.BudgetContractError) as over:
            broker.allocate_arm("arm-02", category_limits={"normal": 65})
        assert over.value.code == "ROOT_BUDGET_EXCEEDED"
        assert broker.remaining_by_class()["normal"] == 64
    finally:
        broker.close()


@pytest.mark.parametrize(
    ("scope", "publication", "expected"),
    [
        ("formal", "definitely-not-published", "markerless-incomplete"),
        ("formal", "published-or-uncertain", "formal-consumed-incomplete"),
        ("arm", "definitely-not-published", "arm-allocation-unselected-terminal"),
        ("arm", "published-or-uncertain", "arm-consumed-incomplete"),
    ],
)
def test_consumption_states_are_exact_and_non_overlapping(
    scope: str,
    publication: str,
    expected: str,
) -> None:
    assert BUDGET.classify_consumption(scope=scope, publication=publication) == expected
    assert len(BUDGET.CONSUMPTION_STATES) == 4


def test_invalid_consumption_pair_fails_closed() -> None:
    with pytest.raises(BUDGET.BudgetContractError) as raised:
        BUDGET.classify_consumption(scope="arm", publication="maybe")
    assert raised.value.code == "INVALID_CONSUMPTION_STATE"


def test_normal_metadata_closeout_use_preallocated_no_replace_publication(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        records = [
            broker.publish_bytes(
                f"{artifact_class}.bin",
                artifact_class.encode(),
                maximum_bytes=32,
                artifact_class=artifact_class,
            )
            for artifact_class in ("normal", "metadata", "closeout")
        ]
        assert [record["artifact_class"] for record in records] == ["normal", "metadata", "closeout"]
        assert broker.remaining_by_class() == {
            "closeout": 96,
            "metadata": 96,
            "normal": 96,
        }
        for record in records:
            target = broker.root / str(record["path"])
            assert target.read_bytes() == str(record["artifact_class"]).encode()
            assert stat.S_IMODE(target.stat().st_mode) == 0o444
            assert not (target.parent / str(record["staging_name"])).exists()
    finally:
        broker.close()


def test_arm_write_debits_reserved_arm_not_root_twice(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        broker.allocate_arm(
            "arm-01",
            category_limits={"normal": 64, "metadata": 16, "closeout": 16},
        )
        root_after_allocation = broker.remaining_by_class()
        broker.publish_bytes(
            "arm-output.bin",
            b"arm",
            maximum_bytes=32,
            artifact_class="normal",
            arm_slot="arm-01",
        )
        assert broker.remaining_by_class() == root_after_allocation
        assert broker.arm_account("arm-01")["category_remaining"]["normal"] == 32
    finally:
        broker.close()


def test_rename_collision_preserves_unknown_target_and_failed_staging(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        target = broker.root / "occupied.bin"
        target.write_bytes(b"unknown")
        before = broker.remaining_by_class()["normal"]
        with pytest.raises(BUDGET.BudgetContractError) as raised:
            broker.publish_bytes(
                "occupied.bin",
                b"expected",
                maximum_bytes=32,
                artifact_class="normal",
            )
        assert raised.value.code == "TARGET_EXISTS"
        assert target.read_bytes() == b"unknown"
        assert broker.remaining_by_class()["normal"] == before - 32
        stages = list(broker.root.glob(".ab16-budget-stage-*"))
        assert len(stages) == 1
        assert stages[0].read_bytes() == b"expected"
        assert stat.S_IMODE(stages[0].stat().st_mode) == 0o444
    finally:
        broker.close()


def test_preallocation_failure_strands_credit_and_keeps_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = _broker(tmp_path)
    try:
        before = broker.remaining_by_class()["metadata"]

        def fail_fallocate(descriptor: int, offset: int, length: int) -> None:
            assert descriptor >= 0
            assert offset == 0
            assert length == 24
            raise OSError("injected preallocation failure")

        monkeypatch.setattr(BUDGET.os, "posix_fallocate", fail_fallocate)
        with pytest.raises(OSError, match="injected"):
            broker.publish_bytes(
                "never-published.json",
                b"{}",
                maximum_bytes=24,
                artifact_class="metadata",
            )
        assert broker.remaining_by_class()["metadata"] == before - 24
        stages = list(broker.root.glob(".ab16-budget-stage-*"))
        assert len(stages) == 1
        assert stages[0].is_file()
        assert stat.S_IMODE(stages[0].stat().st_mode) == 0o444
        assert not (broker.root / "never-published.json").exists()
    finally:
        broker.close()


def test_uncertain_ack_never_refunds_published_extent(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        before = broker.remaining_by_class()["closeout"]

        def lose_ack(_record: dict[str, object]) -> None:
            raise RuntimeError("ack lost")

        with pytest.raises(BUDGET.BudgetContractError) as raised:
            broker.publish_bytes(
                "terminal.json",
                b'{"terminal":true}\n',
                maximum_bytes=48,
                artifact_class="closeout",
                acknowledgement=lose_ack,
            )
        assert raised.value.code == "ACKNOWLEDGEMENT_UNCERTAIN"
        assert broker.remaining_by_class()["closeout"] == before - 48
        assert (broker.root / "terminal.json").read_bytes() == b'{"terminal":true}\n'
        assert len(broker.published_artifacts()) == 1
    finally:
        broker.close()


def test_append_channel_is_a_sequence_of_immutable_segments(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        first = broker.append_segment(
            "ledger",
            0,
            b"first",
            maximum_bytes=16,
            artifact_class="normal",
        )
        second = broker.append_segment(
            "ledger",
            1,
            b"second",
            maximum_bytes=16,
            artifact_class="normal",
        )
        assert first["path"] == "channels/ledger/segment-00000000.bin"
        assert second["path"] == "channels/ledger/segment-00000001.bin"
        with pytest.raises(BUDGET.BudgetContractError) as replay:
            broker.append_segment(
                "ledger",
                1,
                b"replacement",
                maximum_bytes=16,
                artifact_class="normal",
            )
        assert replay.value.code == "SEGMENT_SEQUENCE_MISMATCH"
        assert (broker.root / str(first["path"])).read_bytes() == b"first"
    finally:
        broker.close()


def test_preverified_descriptor_is_reserved_copied_and_published_without_loading_bytes(
    tmp_path: Path,
) -> None:
    broker = _broker(tmp_path)
    source = tmp_path / "sealed-source.bin"
    raw = b"descriptor-backed-model"
    source.write_bytes(raw)
    source_fd = os.open(source, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        broker.register_directory("records")
        record = broker.publish_preverified_descriptor(
            "records/model.pb",
            source_fd,
            size_bytes=len(raw),
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            maximum_bytes=64,
            artifact_class="normal",
        )
        assert record["size_bytes"] == len(raw)
        assert record["sha256"] == hashlib.sha256(raw).hexdigest()
        assert (broker.root / "records/model.pb").read_bytes() == raw
        assert broker.remaining_by_class()["normal"] == 64
    finally:
        os.close(source_fd)
        broker.close()


def test_preverified_descriptor_rejects_bad_identity_before_budget_debit(
    tmp_path: Path,
) -> None:
    broker = _broker(tmp_path)
    source = tmp_path / "source.bin"
    source.write_bytes(b"payload")
    source_fd = os.open(source, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        broker.register_directory("records")
        before = broker.remaining_by_class()
        with pytest.raises(BUDGET.BudgetContractError) as raised:
            broker.publish_preverified_descriptor(
                "records/model.pb",
                source_fd,
                size_bytes=7,
                expected_sha256="0" * 64,
                maximum_bytes=64,
                artifact_class="normal",
            )
        assert raised.value.code == "SOURCE_DESCRIPTOR_INVALID"
        assert broker.remaining_by_class() == before
        assert list((broker.root / "records").iterdir()) == []
    finally:
        os.close(source_fd)
        broker.close()


def test_root_closure_enumerates_every_directory_regular_and_failed_stage(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        broker.register_directory("records")
        broker.publish_bytes(
            "records/one.json",
            b"one\n",
            maximum_bytes=16,
            artifact_class="metadata",
        )
        occupied = broker.root / "records" / "occupied"
        occupied.write_bytes(b"outside")
        with pytest.raises(BUDGET.BudgetContractError):
            broker.publish_bytes(
                "records/occupied",
                b"inside",
                maximum_bytes=16,
                artifact_class="normal",
            )
        closure = broker.snapshot_root_closure()
        paths = {entry["path"] for entry in closure["entries"]}
        assert "records" in paths
        assert "records/one.json" in paths
        assert "records/occupied" in paths
        assert any(str(path).startswith("records/.ab16-budget-stage-") for path in paths)
        assert len(paths) == len(closure["entries"])
        assert len(str(closure["closure_sha256"])) == 64
        assert broker.verify_root_closure(closure) == closure
        (broker.root / "late.json").write_bytes(b"late")
        with pytest.raises(BUDGET.BudgetContractError) as late:
            broker.verify_root_closure(closure)
        assert late.value.code == "ROOT_CLOSURE_MISMATCH"
    finally:
        broker.close()


def test_root_closure_rejects_symlink_and_special_node(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        os.symlink("/dev/null", broker.root / "link")
        with pytest.raises(BUDGET.BudgetContractError) as symlink:
            broker.snapshot_root_closure()
        assert symlink.value.code == "ROOT_CLOSURE_UNSAFE_NODE"
        (broker.root / "link").unlink()
        fifo = broker.root / "fifo"
        os.mkfifo(fifo)
        with pytest.raises(BUDGET.BudgetContractError) as special:
            broker.snapshot_root_closure()
        assert special.value.code == "ROOT_CLOSURE_UNSAFE_NODE"
    finally:
        broker.close()


def test_root_closure_rejects_regular_hardlinks_and_preserves_them(
    tmp_path: Path,
) -> None:
    broker = _broker(tmp_path)
    try:
        broker.register_directory("records")
        broker.publish_bytes(
            "records/one.json",
            b"one\n",
            maximum_bytes=16,
            artifact_class="metadata",
        )
        linked = broker.root / "records" / "linked.json"
        os.link(broker.root / "records" / "one.json", linked)
        with pytest.raises(BUDGET.BudgetContractError) as hardlink:
            broker.snapshot_root_closure()
        assert hardlink.value.code == "ROOT_CLOSURE_UNSAFE_NODE"
        assert linked.read_bytes() == b"one\n"
    finally:
        broker.close()


def test_root_closure_rejoins_absolute_parent_after_complete_walk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    parent = tmp_path / "authority"
    parent.mkdir()
    broker = BUDGET.FormalBudgetBroker.create(
        parent / "formal",
        category_limits={"metadata": 32},
    )
    moved = tmp_path / "authority-moved"
    original_listdir = BUDGET.os.listdir
    injected = False

    def replace_parent_after_first_enumeration(path: object) -> list[str]:
        nonlocal injected
        names = original_listdir(path)
        if not injected and isinstance(path, int):
            injected = True
            parent.rename(moved)
            parent.symlink_to(moved.name, target_is_directory=True)
        return names

    monkeypatch.setattr(
        BUDGET.os,
        "listdir",
        replace_parent_after_first_enumeration,
    )
    try:
        with pytest.raises(BUDGET.BudgetContractError) as drift:
            broker.snapshot_root_closure()
        assert drift.value.code == "ROOT_PATH_DRIFT"
        assert parent.is_symlink()
        assert (moved / "formal").is_dir()
    finally:
        broker.close()
        if parent.is_symlink():
            parent.unlink()
            moved.rename(parent)


def test_directory_component_handoff_closes_each_owned_fd_once_on_close_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    broker = _broker(tmp_path)
    broker.register_directory("records")
    original_dup = BUDGET.os.dup
    original_close = BUDGET.os.close
    duplicated_root = -1
    close_counts: dict[int, int] = {}

    def capture_dup(descriptor: int) -> int:
        nonlocal duplicated_root
        result = original_dup(descriptor)
        duplicated_root = result
        return result

    def fail_after_closing_once(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        original_close(descriptor)
        if descriptor == duplicated_root:
            raise RuntimeError("injected component close failure")

    before = len(os.listdir("/proc/self/fd"))
    monkeypatch.setattr(BUDGET.os, "dup", capture_dup)
    monkeypatch.setattr(BUDGET.os, "close", fail_after_closing_once)
    try:
        with pytest.raises(
            RuntimeError,
            match="injected component close failure",
        ):
            BUDGET._open_directory_parts(  # noqa: SLF001
                broker._root_fd,  # noqa: SLF001
                ("records",),
            )
        assert duplicated_root >= 0
        assert close_counts[duplicated_root] == 1
        assert len(os.listdir("/proc/self/fd")) == before
    finally:
        monkeypatch.setattr(BUDGET.os, "close", original_close)
        broker.close()


def test_root_and_directory_paths_are_no_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "formal"
    root.mkdir()
    with pytest.raises(BUDGET.BudgetContractError) as existing:
        BUDGET.FormalBudgetBroker.create(root, category_limits={"metadata": 16})
    assert existing.value.code == "ROOT_EXISTS"

    broker = BUDGET.FormalBudgetBroker.create(tmp_path / "fresh", category_limits={"metadata": 32})
    try:
        (broker.root / "collision").mkdir()
        with pytest.raises(BUDGET.BudgetContractError) as collision:
            broker.register_directory("collision")
        assert collision.value.code == "DIRECTORY_COLLISION"
    finally:
        broker.close()


def test_registered_read_only_directory_mode_is_bound_and_cannot_be_reopened(
    tmp_path: Path,
) -> None:
    broker = _broker(tmp_path)
    try:
        assert broker.register_directory("arm/tmp", mode=0o500) == "arm/tmp"
        metadata = os.stat(broker.root / "arm/tmp", follow_symlinks=False)
        assert stat.S_IMODE(metadata.st_mode) == 0o500
        with pytest.raises(BUDGET.BudgetContractError) as mode_drift:
            broker.register_directory("arm/tmp", mode=0o700)
        assert mode_drift.value.code == "DIRECTORY_MODE_DRIFT"
        with pytest.raises(BUDGET.BudgetContractError) as invalid:
            broker.register_directory("arm/invalid", mode=0o600)
        assert invalid.value.code == "DIRECTORY_MODE_INVALID"
    finally:
        broker.close()


def test_contract_record_carries_only_research_boundary_booleans(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        record = broker.contract_record()
        assert record["authority"] == {
            "changes_certified_exact": False,
            "changes_cut_state": False,
            "changes_lower_bound": False,
            "changes_production": False,
            "changes_upper_bound": False,
            "research_only": True,
        }
        assert "upper_bound" not in record
        assert "lower_bound" not in record
    finally:
        broker.close()


def test_closure_record_rejects_forged_digest_and_extra_fields(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    try:
        closure = broker.snapshot_root_closure()
        forged = dict(closure)
        forged["closure_sha256"] = "0" * 64
        with pytest.raises(BUDGET.BudgetContractError) as digest:
            BUDGET.validate_closure_record(forged)
        assert digest.value.code == "INVALID_CLOSURE_RECORD"

        extra = dict(closure)
        extra["authority"] = True
        with pytest.raises(BUDGET.BudgetContractError) as shape:
            BUDGET.validate_closure_record(extra)
        assert shape.value.code == "INVALID_CLOSURE_RECORD"
    finally:
        broker.close()


def test_retained_closeout_staging_is_predebit_preallocated_and_nonrefundable(
    tmp_path: Path,
) -> None:
    broker = _broker(tmp_path)
    try:
        broker.register_directory("formal-closeout")
        before = broker.remaining_by_class()["closeout"]
        reservation = broker.reserve_retained_staging(
            "formal-closeout",
            maximum_bytes=64,
            artifact_class="closeout",
            purpose="bootstrap-failure-closeout",
        )
        try:
            record = reservation.record()
            staged = broker.root / str(record["staging_path"])
            assert broker.remaining_by_class()["closeout"] == before - 64
            assert staged.is_file()
            assert staged.stat().st_size == 64
            assert stat.S_IMODE(staged.stat().st_mode) == 0o600
            assert os.fstat(reservation.fileno()).st_size == 64
        finally:
            reservation.close()
        assert staged.is_file()
        assert staged.stat().st_size == 64
        assert broker.remaining_by_class()["closeout"] == before - 64
    finally:
        broker.close()


def test_retained_closeout_staging_failure_strands_extent_and_credit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = _broker(tmp_path)
    try:
        broker.register_directory("formal-closeout")
        before = broker.remaining_by_class()["closeout"]

        def fail_after_allocation(descriptor: int) -> None:
            assert os.fstat(descriptor).st_size == 64
            raise RuntimeError("injected post-allocation failure")

        monkeypatch.setattr(BUDGET, "_verify_retained_staging", fail_after_allocation)
        with pytest.raises(RuntimeError, match="post-allocation"):
            broker.reserve_retained_staging(
                "formal-closeout",
                maximum_bytes=64,
                artifact_class="closeout",
                purpose="bootstrap-failure-closeout",
            )
        assert broker.remaining_by_class()["closeout"] == before - 64
        stages = list((broker.root / "formal-closeout").glob(".ab16-budget-stage-*"))
        assert len(stages) == 1
        assert stages[0].stat().st_size == 64
        assert stat.S_IMODE(stages[0].stat().st_mode) == 0o444
    finally:
        broker.close()


def test_broker_and_retained_staging_handoffs_transfer_ownership_exactly_once(
    tmp_path: Path,
) -> None:
    broker = BUDGET.FormalBudgetBroker.create(
        tmp_path / "formal",
        category_limits={"metadata": 128, "closeout": 128},
        owner_nonce="bootstrap-owner",
    )
    broker.register_directory("formal-closeout")
    reservation = broker.reserve_retained_staging(
        "formal-closeout",
        maximum_bytes=64,
        artifact_class="closeout",
        purpose="bootstrap-failure-closeout",
    )
    successor_reservation, reservation_handoff = reservation.transfer_ownership(
        to_owner_nonce="recovery-owner"
    )
    successor, broker_handoff = broker.transfer_ownership(
        to_owner_nonce="persistent-broker-owner"
    )
    try:
        assert reservation_handoff["from_owner_nonce"] == "bootstrap-owner"
        assert reservation_handoff["to_owner_nonce"] == "recovery-owner"
        assert broker_handoff["from_owner_nonce"] == "bootstrap-owner"
        assert broker_handoff["to_owner_nonce"] == "persistent-broker-owner"
        assert os.fstat(successor_reservation.fileno()).st_size == 64
        successor.publish_bytes(
            "after-handoff.json",
            b"{}\n",
            maximum_bytes=16,
            artifact_class="metadata",
        )
        assert (successor.root / "after-handoff.json").read_bytes() == b"{}\n"
        with pytest.raises(BUDGET.BudgetContractError) as old_reservation:
            reservation.fileno()
        assert old_reservation.value.code == "RESERVATION_CLOSED"
        with pytest.raises(BUDGET.BudgetContractError) as old_broker:
            broker.publish_bytes(
                "forbidden.json",
                b"{}\n",
                maximum_bytes=16,
                artifact_class="metadata",
            )
        assert old_broker.value.code == "BROKER_CLOSED"
        with pytest.raises(BUDGET.BudgetContractError) as second_reservation_handoff:
            reservation.transfer_ownership(to_owner_nonce="other-owner")
        assert second_reservation_handoff.value.code == "RESERVATION_CLOSED"
        with pytest.raises(BUDGET.BudgetContractError) as second_broker_handoff:
            broker.transfer_ownership(to_owner_nonce="other-owner")
        assert second_broker_handoff.value.code == "BROKER_CLOSED"
    finally:
        successor_reservation.close()
        successor.close()


def test_retained_directory_handoff_binds_identity_without_freezing_contents(
    tmp_path: Path,
) -> None:
    broker = BUDGET.FormalBudgetBroker.create(
        tmp_path / "campaign",
        category_limits={"metadata": 128},
        owner_nonce="bootstrap-owner",
    )
    broker.register_directory("formal-ab16/control")
    capability = broker.retain_directory(
        "formal-ab16/control",
        purpose="formal-control-parent",
    )
    successor = None
    try:
        before = capability.record()
        assert before["schema_version"] == BUDGET.BUDGET_RETAINED_DIRECTORY_SCHEMA
        assert before["directory_path"] == "formal-ab16/control"
        assert before["purpose"] == "formal-control-parent"
        assert before["owner_nonce"] == "bootstrap-owner"
        assert stat.S_IMODE(os.fstat(capability.fileno()).st_mode) == 0o700

        # Runtime socket creation changes directory timestamps.  The capability
        # binds the directory inode, type, mode, and owner, not mutable contents.
        transient = broker.root / "formal-ab16/control/transient"
        transient.write_bytes(b"x")
        transient.unlink()
        assert capability.record()["directory_identity"] == before["directory_identity"]

        successor, handoff = capability.transfer_ownership(
            to_owner_nonce="persistent-broker-owner"
        )
        assert handoff["schema_version"] == BUDGET.BUDGET_OWNERSHIP_HANDOFF_SCHEMA
        assert handoff["account_kind"] == "retained-directory"
        assert handoff["directory_path"] == "formal-ab16/control"
        assert handoff["from_owner_nonce"] == "bootstrap-owner"
        assert handoff["to_owner_nonce"] == "persistent-broker-owner"
        assert successor.record()["directory_identity"] == before["directory_identity"]
        with pytest.raises(BUDGET.BudgetContractError) as old_owner:
            capability.fileno()
        assert old_owner.value.code == "DIRECTORY_CAPABILITY_CLOSED"

        original = broker.root / "formal-ab16/control"
        moved = broker.root / "formal-ab16/control-moved"
        original.rename(moved)
        original.mkdir(mode=0o700)
        unknown = original / "unknown"
        unknown.write_bytes(b"keep")
        with pytest.raises(BUDGET.BudgetContractError) as replaced:
            successor.fileno()
        assert replaced.value.code == "DIRECTORY_CAPABILITY_PATH_DRIFT"
        assert unknown.read_bytes() == b"keep"
    finally:
        if successor is not None:
            successor.close()
        broker.close()


def test_retained_closeout_staging_publishes_from_same_extent_no_replace(
    tmp_path: Path,
) -> None:
    broker = _broker(tmp_path)
    try:
        broker.register_directory("formal-closeout")
        reservation = broker.reserve_retained_staging(
            "formal-closeout",
            maximum_bytes=64,
            artifact_class="closeout",
            purpose="bootstrap-failure-closeout",
        )
        staging_inode = os.fstat(reservation.fileno()).st_ino
        record = reservation.publish_bytes(
            "bootstrap-failure-closeout.json",
            b'{"status":"FAIL_CLOSED"}\n',
        )
        published = broker.root / str(record["path"])
        assert published.read_bytes() == b'{"status":"FAIL_CLOSED"}\n'
        assert published.stat().st_ino == staging_inode
        assert stat.S_IMODE(published.stat().st_mode) == 0o444
        with pytest.raises(BUDGET.BudgetContractError) as consumed:
            reservation.fileno()
        assert consumed.value.code == "RESERVATION_CLOSED"

        occupied = broker.root / "formal-closeout" / "occupied.json"
        occupied.write_bytes(b"unknown")
        second = broker.reserve_retained_staging(
            "formal-closeout",
            maximum_bytes=32,
            artifact_class="closeout",
            purpose="second-closeout",
        )
        second_stage = broker.root / str(second.record()["staging_path"])
        with pytest.raises(BUDGET.BudgetContractError) as collision:
            second.publish_bytes("occupied.json", b"expected")
        assert collision.value.code == "TARGET_EXISTS"
        assert occupied.read_bytes() == b"unknown"
        assert second_stage.exists()
        assert stat.S_IMODE(second_stage.stat().st_mode) == 0o444
    finally:
        broker.close()
