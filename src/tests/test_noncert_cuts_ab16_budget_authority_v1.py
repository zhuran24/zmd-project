from __future__ import annotations

import importlib.util
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
