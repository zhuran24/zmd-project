from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ortools.sat import cp_model_pb2
from ortools.sat.python import cp_model


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab_trust_gate1_v3_20260723"


def _load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load("noncert_binary_selector_v3", "independent_arithmetic_check_v3.py")
EXPORT = _load("noncert_binary_export_v2", "positive_control_runner_v2.py")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _ledger(events: list[dict[str, object]]) -> bytes:
    previous = "0" * 64
    rows: list[bytes] = []
    for seq, fields in enumerate(events):
        event = {
            **fields,
            "schema_version": "cut-ledger-v1",
            "seq": seq,
            "prev_event_hash": previous,
            "writer_id": "binary-v3-fixture",
            "scope_id": "binary-v3-fixture",
            "wallclock_utc": seq,
        }
        row = _canonical(event)
        rows.append(row)
        previous = hashlib.sha256(row).hexdigest()
    return b"\n".join(rows) + b"\n"


def _contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "backend": "coordinate_exact_v1",
        "grid": {"width": 3, "height": 2},
        "ghost": {"width": 2, "height": 1},
        "anchor_filter": None,
    }


def _binary_pair(
    *,
    active_ordinal: int = 2,
) -> tuple[cp_model_pb2.CpModelProto, cp_model_pb2.CpSolverResponse, list[int]]:
    model = cp_model_pb2.CpModelProto()
    aux = model.variables.add()
    aux.name = "aux__before"
    aux.domain.extend([0, 1])
    selectors: list[int] = []
    for x in range(2):
        for y in range(2):
            selector = model.variables.add()
            selector.name = f"ghost__{x}_{y}_2_1"
            selector.domain.extend([0, 1])
            selectors.append(len(model.variables) - 1)
            separator = model.variables.add()
            separator.name = f"aux__after_{x}_{y}"
            separator.domain.extend([0, 1])
    constraint = model.constraints.add()
    constraint.name = "the_complete_ghost_selector"
    constraint.exactly_one.literals.extend(selectors)
    response = cp_model_pb2.CpSolverResponse()
    response.status = cp_model_pb2.FEASIBLE
    response.solution.extend([0] * len(model.variables))
    response.solution[selectors[active_ordinal]] = 1
    return model, response, selectors


def _case() -> dict[str, Any]:
    model, response, selectors = _binary_pair()
    model_raw = model.SerializeToString(deterministic=True)
    response_raw = response.SerializeToString(deterministic=True)
    truth = CHECKER.derive_ghost_truth(model, response, _contract())
    group = "group::machine::op::0"
    mandatory = [
        {
            "instance_id": "i1",
            "facility_type": "machine",
            "operation_type": "op",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    candidates = {
        "facility_pools": {
            "machine": [
                {
                    "pose_id": "p0",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0], [1, 0]],
                }
            ]
        }
    }
    ghost = {
        "pose_id": "ghost_anchor::1,0",
        "pose_idx": 2,
        "anchor": {"x": 1, "y": 0},
    }
    incumbent = {
        "i1": {
            "instance_id": "i1",
            "facility_type": "machine",
            "operation_type": "op",
            "pose_id": "p0",
            "pose_idx": 0,
            "anchor": {"x": 0, "y": 0},
        },
        "ghost_pick": ghost,
    }
    prestate_sha = _digest(incumbent)
    arm_result = {
        "arm": "treatment",
        "authority": {"repository_head": CHECKER.EXPECTED_HEAD},
        "prestate": {
            "incumbent": incumbent,
            "incumbent_sha256": prestate_sha,
            "model_binary_sha256": hashlib.sha256(model_raw).hexdigest(),
            "response_binary_sha256": hashlib.sha256(response_raw).hexdigest(),
            "model_variable_count": len(model.variables),
            "model_constraint_count": len(model.constraints),
            "ghost_pick": ghost,
        },
    }
    parameters = {
        "capacity": 0,
        "group_id": group,
        "region_kind": "left_baseline",
    }
    compiled = {
        "cut_id": "cut-1",
        "family": "shape_packing_hall",
        "operation": "shape_packing_hall_le",
        "parameters": parameters,
        "model_scope": {
            "ghost_policy": "bound",
            "ghost_rect_digest": truth.rectangle_digest,
        },
    }
    literal = {
        "index": truth.active_variable_index,
        "name": truth.active_variable_name,
    }
    sample = {
        "cut_id": "cut-1",
        "family": "shape_packing_hall",
        "operation": "shape_packing_hall_le",
        "parameters": parameters,
        "enforcement_literals": [{**literal, "value": 1}],
        "enforcement_values": [1],
        "contributions": [
            {
                "label": group,
                "selected_count": 1,
                "weight": 1,
                "value": 1,
            }
        ],
        "lhs": 1,
        "rhs": 0,
        "active": True,
        "violated": True,
    }
    applied = {
        "event": "APPLIED",
        "cut_id": "cut-1",
        "family": "shape_packing_hall",
        "receipt": {
            "apply_completed": True,
            "count_delta": 1,
            "rect_idx": truth.active_rect_idx,
            "ghost_rect_digest": truth.rectangle_digest,
            "condition_lits": [literal],
        },
    }
    ledger_raw = _ledger(
        [
            {"event": "GENESIS"},
            {
                "event": "GENERATED",
                "cut_id": "cut-1",
                "family": "shape_packing_hall",
            },
            applied,
            {"event": "SEGMENT_SEAL"},
        ]
    )
    ledger_replay = CHECKER.replay_ledger(ledger_raw)
    arm_result.update(
        {
            "injection": {
                "compiled_observed": 1,
                "compiled_records": [compiled],
                "arithmetic_sample_count": 1,
            },
            "ledger": {
                "path": "/synthetic/binary-v3-ledger.jsonl",
                "status": "complete",
                "event_count": ledger_replay["event_count"],
                "event_counts": ledger_replay["event_counts"],
                "tail_hash": ledger_replay["tail_hash"],
                "generated": 1,
                "applied": 1,
            },
        }
    )
    assignment = {
        "schema_version": 1,
        "prestate_sha256": prestate_sha,
        "literals": [{**literal, "value": 1}],
    }
    return {
        "model": model,
        "response": response,
        "selectors": selectors,
        "model_raw": model_raw,
        "response_raw": response_raw,
        "contract": _contract(),
        "arm_result": arm_result,
        "compiled_record": compiled,
        "sample": sample,
        "ledger_raw": ledger_raw,
        "frozen_assignment": assignment,
        "mandatory_instances": mandatory,
        "candidate_placements": candidates,
    }


def _verify(case: dict[str, Any]) -> dict[str, object]:
    return CHECKER.verify_applied_inequality(
        model_raw=case["model_raw"],
        response_raw=case["response_raw"],
        selector_contract=case["contract"],
        arm_result=case["arm_result"],
        compiled_record=case["compiled_record"],
        sample=case["sample"],
        ledger_raw=case["ledger_raw"],
        frozen_assignment=case["frozen_assignment"],
        mandatory_instances=case["mandatory_instances"],
        candidate_placements=case["candidate_placements"],
    )


def _replace_ledger(case: dict[str, Any], events: list[dict[str, Any]]) -> None:
    stripped = [
        {
            key: value
            for key, value in event.items()
            if key
            not in {
                "schema_version",
                "seq",
                "prev_event_hash",
                "writer_id",
                "scope_id",
                "wallclock_utc",
            }
        }
        for event in events
    ]
    case["ledger_raw"] = _ledger(stripped)
    replay = CHECKER.replay_ledger(case["ledger_raw"])
    case["arm_result"]["ledger"]["tail_hash"] = replay["tail_hash"]
    case["arm_result"]["ledger"]["event_counts"] = replay["event_counts"]
    case["arm_result"]["ledger"]["event_count"] = replay["event_count"]


def _refresh_binary(case: dict[str, Any]) -> None:
    case["model_raw"] = case["model"].SerializeToString(deterministic=True)
    case["response_raw"] = case["response"].SerializeToString(deterministic=True)
    prestate = case["arm_result"]["prestate"]
    prestate["model_binary_sha256"] = hashlib.sha256(case["model_raw"]).hexdigest()
    prestate["response_binary_sha256"] = hashlib.sha256(case["response_raw"]).hexdigest()
    prestate["model_variable_count"] = len(case["model"].variables)
    prestate["model_constraint_count"] = len(case["model"].constraints)


def test_binary_selector_v3_positive_fixture_replays_applied_violation() -> None:
    result = _verify(_case())
    assert result["status"] == "PASS_APPLIED_VIOLATION"
    assert result["binary_truth"]["active_rect_idx"] == 2
    assert result["binary_truth"]["active_variable_index"] == 5
    assert result["binary_truth"]["active_variable_name"] == "ghost__1_0_2_1"
    assert result["selected"]["lhs"] == 1
    assert result["selected"]["rhs"] == 0


def test_coordinated_wrong_literal_mutation_cannot_forge_binary_truth() -> None:
    case = _case()
    wrong = {"index": 999_999, "name": "coordinated_wrong_literal"}
    case["sample"]["enforcement_literals"] = [{**wrong, "value": 1}]
    events = CHECKER.replay_ledger(case["ledger_raw"])["events"]
    events[2]["receipt"]["condition_lits"] = [wrong]
    _replace_ledger(case, events)
    case["frozen_assignment"]["literals"] = [{**wrong, "value": 1}]
    with pytest.raises(ValueError, match="binary truth"):
        _verify(case)


def test_coordinated_other_real_selector_mutation_cannot_forge_active_selector() -> None:
    case = _case()
    other_index = case["selectors"][1]
    other = {
        "index": other_index,
        "name": case["model"].variables[other_index].name,
    }
    case["sample"]["enforcement_literals"] = [{**other, "value": 1}]
    events = CHECKER.replay_ledger(case["ledger_raw"])["events"]
    events[2]["receipt"]["condition_lits"] = [other]
    _replace_ledger(case, events)
    case["frozen_assignment"]["literals"] = [{**other, "value": 1}]
    with pytest.raises(ValueError, match="binary truth"):
        _verify(case)


def _varint(value: int) -> bytes:
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            output.append(byte | 0x80)
        else:
            output.append(byte)
            return bytes(output)


@pytest.mark.parametrize("kind", ["unknown", "duplicate", "truncated"])
def test_noncanonical_or_damaged_protobuf_is_rejected(kind: str) -> None:
    case = _case()
    if kind == "unknown":
        case["model_raw"] += _varint((999 << 3) | 0) + b"\x01"
        match = "unknown, duplicate, or noncanonical"
    elif kind == "duplicate":
        case["response_raw"] += b"\x08\x02"
        match = "unknown, duplicate, or noncanonical"
    else:
        case["model_raw"] = case["model_raw"][:-1]
        match = "truncated or malformed"
    with pytest.raises(ValueError, match=match):
        _verify(case)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("solution_length", "full model solution vector"),
        ("status", "status is not FEASIBLE or OPTIMAL"),
        ("zero_active", "exactly one ghost selector"),
        ("two_active", "exactly one ghost selector"),
        ("domain", "non-Boolean domain"),
        ("exactly_one_missing", "exactly one complete ghost"),
        ("exactly_one_duplicate", "exactly one complete ghost"),
        ("exactly_one_partial", "drifted exactly-one set"),
        ("grid", "must occur exactly once"),
        ("backend", "unsupported or drifted selector backend"),
    ],
)
def test_binary_truth_fail_closed_canaries(mutation: str, match: str) -> None:
    case = _case()
    if mutation == "solution_length":
        del case["response"].solution[-1]
    elif mutation == "status":
        case["response"].status = cp_model_pb2.UNKNOWN
    elif mutation == "zero_active":
        case["response"].solution[case["selectors"][2]] = 0
    elif mutation == "two_active":
        case["response"].solution[case["selectors"][1]] = 1
    elif mutation == "domain":
        case["model"].variables[case["selectors"][0]].domain[:] = [0, 2]
    elif mutation == "exactly_one_missing":
        del case["model"].constraints[:]
    elif mutation == "exactly_one_duplicate":
        duplicate = case["model"].constraints.add()
        duplicate.exactly_one.literals.extend(case["selectors"])
    elif mutation == "exactly_one_partial":
        case["model"].constraints[0].exactly_one.literals.pop()
    elif mutation == "grid":
        case["contract"]["grid"]["width"] = 4
    elif mutation == "backend":
        case["contract"]["backend"] = "pose_bool"
    _refresh_binary(case)
    with pytest.raises(ValueError, match=match):
        _verify(case)


def test_snapshot_read_uses_one_fd_and_rejects_toctou(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "authority.pb"
    path.write_bytes(b"stable bytes")
    real_open = os.open
    real_fstat = os.fstat
    calls = {"open": 0, "fstat": 0}

    def counted_open(*args: Any, **kwargs: Any) -> int:
        calls["open"] += 1
        return real_open(*args, **kwargs)

    def changed_fstat(fd: int) -> object:
        calls["fstat"] += 1
        current = real_fstat(fd)
        if calls["fstat"] == 1:
            return current
        return SimpleNamespace(
            st_mode=current.st_mode,
            st_dev=current.st_dev,
            st_ino=current.st_ino,
            st_size=current.st_size,
            st_mtime_ns=current.st_mtime_ns + 1,
            st_ctime_ns=current.st_ctime_ns,
        )

    monkeypatch.setattr(CHECKER.os, "open", counted_open)
    monkeypatch.setattr(CHECKER.os, "fstat", changed_fstat)
    with pytest.raises(ValueError, match="changed during snapshot"):
        CHECKER.read_snapshot(path)
    assert calls == {"open": 1, "fstat": 2}


def test_snapshot_read_rejects_path_replacement_after_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "authority.pb"
    path.write_bytes(b"stable bytes")
    real_lstat = os.lstat

    def swapped_lstat(candidate: os.PathLike[str] | str) -> object:
        current = real_lstat(candidate)
        if Path(candidate) != path:
            return current
        return SimpleNamespace(
            st_mode=current.st_mode,
            st_dev=current.st_dev,
            st_ino=current.st_ino + 1,
        )

    monkeypatch.setattr(CHECKER.os, "lstat", swapped_lstat)
    with pytest.raises(ValueError, match="pathname was replaced"):
        CHECKER.read_snapshot(path)


def _file_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _launch_selection(tmp_path: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
    receipt = tmp_path / "qualification-receipt.json"
    arm_runner = tmp_path / "positive-control-entrypoint.py"
    recorder = tmp_path / "recorder.py"
    observer = tmp_path / "observer.py"
    receipt.write_text('{"status":"PASS"}\n', encoding="utf-8")
    arm_runner.write_text("# immutable positive-control entrypoint\n", encoding="utf-8")
    recorder.write_text("# recorder\n", encoding="utf-8")
    observer.write_text("# observer\n", encoding="utf-8")
    arms = {
        label: {
            "arm": label,
            "attempt_dir": str((tmp_path / label).absolute()),
            "unit_name": f"gate1-{label}.service",
            "result_path": str((tmp_path / label / "result.json").absolute()),
            "raw_output_path": str((tmp_path / label / "resource.jsonl").absolute()),
            "terminal_envelope_path": str((tmp_path / label / "terminal.json").absolute()),
            "runner_tool_role": "runner",
            "recorder_tool_role": "recorder",
        }
        for label in ("control", "treatment")
    }
    selection: dict[str, object] = {
        "schema": EXPORT._SELECTION_SCHEMA,
        "created_at_utc": "2026-07-23T00:00:00Z",
        "purpose": EXPORT._PAIRED_PURPOSE,
        "run_nonce": "runner-binary-fixture",
        "package_id": "c" * 64,
        "selection_id": "0" * 64,
        "repository_head": "a" * 40,
        "contract": dict(EXPORT._CONTRACT),
        "qualification_receipt_identity": _file_identity(receipt),
        "tools": {
            "runner": _file_identity(arm_runner),
            "positive_control_runner_v2": _file_identity(RESEARCH / "positive_control_runner_v2.py"),
            "recorder": _file_identity(recorder),
            "observer": _file_identity(observer),
        },
        "inputs": {"fixture": _file_identity(receipt)},
        "arm_directories_absent_at_creation": True,
        "arm_launch": True,
        "terminal_observer_tool_role": "observer",
        "arms": arms,
    }
    body = dict(selection)
    body.pop("selection_id")
    selection["selection_id"] = hashlib.sha256(EXPORT._canonical_bytes(body)).hexdigest()
    path = tmp_path / "launch-selection.json"
    path.write_text(json.dumps(selection, sort_keys=True) + "\n", encoding="utf-8")
    return path, _file_identity(path), selection


def test_binary_export_helper_is_library_only_and_no_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = cp_model.CpModel()
    selectors = [model.new_bool_var(f"ghost__0_{y}_1_1") for y in range(2)]
    model.add_exactly_one(selectors)
    response = cp_model_pb2.CpSolverResponse(
        status=cp_model_pb2.FEASIBLE,
        solution=[1, 0],
    )
    selection_path, selection_identity, selection = _launch_selection(tmp_path)
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    def forbid_read_bytes(_path: Path) -> bytes:
        raise AssertionError("export helper must not reopen generated bytes")

    monkeypatch.setattr(Path, "read_bytes", forbid_read_bytes)
    record = EXPORT.export_binary_prestate(
        model=model,
        solver_response_text=str(response),
        output_parent=control_dir,
        attempt_name="binary-a001",
        arm="control",
        unit_name="gate1-control.service",
        selection_path=selection_path,
        expected_selection_identity=selection_identity,
    )
    assert record["phase"] == "pre_injection"
    assert record["arm"] == "control"
    assert record["paired_arm_launch"]["selection_id"] == selection["selection_id"]
    assert record["paired_arm_launch"]["selection_identity"] == selection_identity
    assert record["paired_arm_launch"]["runner_tool_role"] == "runner"
    assert record["paired_arm_launch"]["runner_identity"] == selection["tools"]["runner"]
    assert record["paired_arm_launch"]["binary_helper_tool_role"] == "positive_control_runner_v2"
    assert Path(record["model"]["path"]).suffix == ".pb"
    assert Path(record["response"]["path"]).suffix == ".pb"
    with pytest.raises(FileExistsError, match="refusing to reuse"):
        EXPORT.export_binary_prestate(
            model=model,
            solver_response_text=str(response),
            output_parent=control_dir,
            attempt_name="binary-a001",
            arm="control",
            unit_name="gate1-control.service",
            selection_path=selection_path,
            expected_selection_identity=selection_identity,
        )
    source = (RESEARCH / "positive_control_runner_v2.py").read_text(encoding="utf-8")
    assert ".Solve(" not in source
    assert ".solve(" not in source


def test_binary_export_rejects_ad_hoc_wrapper(tmp_path: Path) -> None:
    wrapper = tmp_path / "wrapper.json"
    wrapper.write_text(
        json.dumps(
            {
                "purpose": "paired_arm_launch",
                "arm_launch": True,
                "arm": "control",
                "launch_selection_id": "a" * 64,
                "identity": {"path": "/fake", "size_bytes": 1, "sha256": "b" * 64},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="key set drifted"):
        EXPORT._require_launch_selection(
            wrapper,
            expected_identity=_file_identity(wrapper),
            expected_arm="control",
            expected_unit_name="gate1-control.service",
        )


def test_binary_export_rejects_launch_selection_arm_mismatch(tmp_path: Path) -> None:
    selection_path, identity, _selection = _launch_selection(tmp_path)
    with pytest.raises(ValueError, match="arm/unit binding drifted"):
        EXPORT._require_launch_selection(
            selection_path,
            expected_identity=identity,
            expected_arm="control",
            expected_unit_name="gate1-treatment.service",
        )


def _reseal_selection(path: Path, selection: dict[str, object]) -> dict[str, object]:
    body = dict(selection)
    body.pop("selection_id")
    selection["selection_id"] = hashlib.sha256(EXPORT._canonical_bytes(body)).hexdigest()
    path.write_text(json.dumps(selection, sort_keys=True) + "\n", encoding="utf-8")
    return _file_identity(path)


def test_binary_export_rejects_missing_binary_helper_identity(tmp_path: Path) -> None:
    selection_path, _identity, selection = _launch_selection(tmp_path)
    del selection["tools"]["positive_control_runner_v2"]
    identity = _reseal_selection(selection_path, selection)
    with pytest.raises(ValueError, match="helper tool identity must appear exactly once"):
        EXPORT._require_launch_selection(
            selection_path,
            expected_identity=identity,
            expected_arm="control",
            expected_unit_name="gate1-control.service",
        )


def test_binary_export_rejects_helper_masquerading_as_arm_runner(
    tmp_path: Path,
) -> None:
    selection_path, _identity, selection = _launch_selection(tmp_path)
    selection["arms"]["control"]["runner_tool_role"] = "positive_control_runner_v2"
    identity = _reseal_selection(selection_path, selection)
    with pytest.raises(ValueError, match="helper cannot masquerade"):
        EXPORT._require_launch_selection(
            selection_path,
            expected_identity=identity,
            expected_arm="control",
            expected_unit_name="gate1-control.service",
        )
