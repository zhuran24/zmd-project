from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

from ortools.sat import cp_model_pb2
import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = ROOT / "docs/research/noncert_cuts_ab16_20260724" / "organic_arm_replay_v1.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "noncert_cuts_ab16_organic_arm_replay_v1_tested",
        TOOL_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REPLAY = _load()


@pytest.fixture(autouse=True)
def _offline_no_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise joins without starting CP-SAT under the shared resource lock."""

    def check_length(
        model: cp_model_pb2.CpModelProto,
        solution: list[int],
    ) -> None:
        if len(model.variables) != len(solution):
            raise REPLAY.ReplayError("fixture vector length drifted")

    monkeypatch.setattr(REPLAY, "_fixed_vector_feasible", check_length)


def _write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _json(path: Path, value: object) -> Path:
    return _write(path, REPLAY.canonical_json(value))


def _identity(path: Path) -> dict[str, object]:
    return dict(REPLAY.snapshot_regular(path).identity)


def _chain(
    path: Path,
    events: list[dict[str, object]],
    *,
    ledger: bool,
) -> Path:
    previous = "0" * 64
    lines: list[bytes] = []
    for sequence, source in enumerate(events):
        event = copy.deepcopy(source)
        event["schema_version"] = REPLAY.LEDGER_SCHEMA if ledger else REPLAY.JOURNAL_SCHEMA
        event["seq"] = sequence
        event["prev_event_hash" if ledger else "prev_event_sha256"] = previous
        if ledger:
            event["scope_id"] = "fixture-scope"
            event["writer_id"] = "fixture-writer"
        line = REPLAY._compact_json(event)  # noqa: SLF001
        lines.append(line)
        previous = hashlib.sha256(line).hexdigest()
    return _write(path, b"\n".join(lines) + b"\n")


def _models(directory: Path, *, applied: bool) -> tuple[Path, Path]:
    pre = cp_model_pb2.CpModelProto()
    for name in ("x", "y"):
        variable = pre.variables.add()
        variable.name = name
        variable.domain.extend((0, 1))
    post = cp_model_pb2.CpModelProto()
    post.CopyFrom(pre)
    if applied:
        constraint = post.constraints.add()
        constraint.linear.vars.extend((0, 1))
        constraint.linear.coeffs.extend((1, 1))
        constraint.linear.domain.extend((REPLAY.INT64_MIN, 0))
    return (
        _write(
            directory / "pre.pb",
            pre.SerializeToString(deterministic=True),
        ),
        _write(
            directory / "post.pb",
            post.SerializeToString(deterministic=True),
        ),
    )


def _plan() -> dict[str, object]:
    plan: dict[str, object] = {
        "digest": "",
        "family": "region_capacity",
        "model_scope": {
            "domain_fingerprint": "fixture-domain",
            "ghost_policy": "agnostic",
            "ghost_rect_digest": None,
        },
        "operation": "region_capacity_le",
        "parameters": {
            "capacity": 0,
            "group_cell_weights": {"fixture-group": 1},
        },
        "schema_version": 1,
        "semantic_fingerprint": "2" * 64,
    }
    plan["digest"], _ = REPLAY._validate_plan_projection(plan)  # noqa: SLF001
    return plan


def _compiled(plan: dict[str, object]) -> dict[str, object]:
    _, scope_digest = REPLAY._validate_plan_projection(plan)  # noqa: SLF001
    payload: dict[str, object] = {
        "compiled_digest": "",
        "cut_id": "cut-fixture-001",
        "hook_id": 0,
        "plan": plan,
        "proof_digest": "3" * 64,
        "scope_digest": scope_digest,
        "snapshot_digest": "4" * 64,
    }
    payload["compiled_digest"] = REPLAY._domain_digest(  # noqa: SLF001
        REPLAY.COMPILED_CUT_DIGEST_PREFIX,
        {
            "cut_id": payload["cut_id"],
            "plan_digest": plan["digest"],
            "proof_digest": payload["proof_digest"],
            "scope_digest": payload["scope_digest"],
            "snapshot_digest": payload["snapshot_digest"],
        },
    )
    return payload


def _cut_free(
    directory: Path,
    incumbent_identity: dict[str, object],
) -> Path:
    metadata = _json(directory / "metadata.json", {"fixture": "metadata"})
    model = _json(directory / "model.json", {"fixture": "model"})
    tool = _write(directory / "fixed-replay.py", b"# inert fixture\n")
    return _json(
        directory / "cut-free.json",
        {
            "all_fixed_equalities_added": True,
            "assignment_count": 1,
            "conflicting_assignment_count": 0,
            "created_at_utc": "2026-07-24T00:00:00Z",
            "fixed_assignment_count": 1,
            "global_claim_authorized": False,
            "incumbent_identity": incumbent_identity,
            "incumbent_sha256": incumbent_identity["sha256"],
            "legacy_control_used_as_truth_root": False,
            "metadata_identity": _identity(metadata),
            "model_constraint_count": 1,
            "model_identity": _identity(model),
            "model_validation_errors": [],
            "model_variable_count": 2,
            "purpose": "strict_ab16_incumbent_fixed_assignment_replay",
            "replay_errors": [],
            "replay_tool_identity": _identity(tool),
            "schema_version": REPLAY.CUT_FREE_SCHEMA,
            "solution_matches_fixed_assignments": True,
            "solver_status": "OPTIMAL",
            "status": "PASS",
            "unresolved_assignment_count": 0,
            "verdict": "INCUMBENT_FIXED_ASSIGNMENT_REPLAY_PASS",
        },
    )


def _fixture(tmp_path: Path, branch: str) -> dict[str, Path]:
    evidence = tmp_path / "evidence"
    solution = {"x": 1, "y": 0}
    baseline = _json(evidence / "baseline.json", solution)
    raw_incumbent = _json(evidence / "raw-incumbent.json", solution)
    final_vector = _json(evidence / "raw-solution-vector.json", [1, 0])
    pre, post = _models(evidence, applied=branch == "applied")
    hook_vector = _json(evidence / "hook-vector.json", [1, 0])
    plan = _plan()
    compiled = _compiled(plan)
    if branch == "zero":
        ledger_events = [
            {"event": "GENESIS"},
            {"event": "SEGMENT_SEAL"},
        ]
        activity = {"applied": 0, "compiled": 0, "generated": 0}
    elif branch == "no-applied":
        ledger_events = [
            {"event": "GENESIS"},
            {
                "cut_id": compiled["cut_id"],
                "event": "GENERATED",
                "family": plan["family"],
            },
            {"cut_id": compiled["cut_id"], "event": "REJECTED"},
            {"event": "SEGMENT_SEAL"},
        ]
        activity = {"applied": 0, "compiled": 0, "generated": 1}
    else:
        ledger_events = [
            {"event": "GENESIS"},
            {
                "cut_id": compiled["cut_id"],
                "event": "GENERATED",
                "family": plan["family"],
            },
            {
                "cut_id": compiled["cut_id"],
                "event": "APPLIED",
                "family": plan["family"],
                "plan_digest": plan["digest"],
                "receipt": {
                    "apply_completed": True,
                    "condition_lits": [],
                    "count_delta": 1,
                    "ghost_rect_digest": None,
                    "master_domain_family": plan["family"],
                    "rect_idx": None,
                    "snapshot_digest": compiled["snapshot_digest"],
                },
                "semantic_fingerprint": plan["semantic_fingerprint"],
            },
            {"event": "SEGMENT_SEAL"},
        ]
        activity = {"applied": 1, "compiled": 1, "generated": 1}
    journal_events: list[dict[str, object]] = [
        {"event": "GENESIS", "payload": {}},
        {
            "event": "FIRST_ATTACH_SOLUTION_VERIFIED",
            "payload": {
                "incumbent_sha256": hashlib.sha256(
                    REPLAY._compact_json(solution)  # noqa: SLF001
                ).hexdigest(),
                "solution_entry_count": len(solution),
            },
        },
        {
            "event": "ATTACH_HOOK_BEGIN",
            "payload": {
                "attach_env": "1",
                "hook_id": 0,
                "iteration": 1,
                "solution_sha256": hashlib.sha256(
                    REPLAY._compact_json(solution)  # noqa: SLF001
                ).hexdigest(),
                "trigger": "fixture",
            },
        },
    ]
    if branch == "applied":
        journal_events.append({"event": "COMPILED_CUT", "payload": compiled})
    journal_events.extend(
        [
            {
                "event": "ATTACH_MODEL_EVIDENCE",
                "payload": {
                    "hook_id": 0,
                    "post_model_identity": _identity(post),
                    "pre_model_identity": _identity(pre),
                    "solution_vector_identity": _identity(hook_vector),
                },
            },
            {
                "event": "ATTACH_HOOK_END",
                "payload": {
                    "attached_count": 1 if branch == "applied" else 0,
                    "error": None,
                    "hook_id": 0,
                    "status": "RETURNED",
                },
            },
            {"event": "JOURNAL_SEAL", "payload": {}},
        ]
    )
    ledger = _chain(evidence / "ledger.jsonl", ledger_events, ledger=True)
    journal = _chain(
        evidence / "journal.jsonl",
        journal_events,
        ledger=False,
    )
    result = _json(
        evidence / "result.json",
        {
            "arm": "treatment",
            "authority_identities": {
                "baseline_incumbent": _identity(baseline),
                "manifest": _identity(_json(evidence / "manifest.json", {"fixture": "manifest"})),
                "selection": _identity(
                    _json(
                        evidence / "selection.json",
                        {"fixture": "selection"},
                    )
                ),
            },
            "authorizations": {
                "global_claim_authorized": False,
                "mathematical_claim_authorized": False,
                "organic_runtime_effect_authorized": False,
                "production_certified_authorized": False,
            },
            "campaign_id": "1" * 64,
            "cut_activity": activity,
            "enabled_families": ["region_capacity"],
            "evidence": {
                "compile_attach_journal_identity": _identity(journal),
                "cut_ledger_identity": _identity(ledger),
                "cut_ledger_status": "complete",
                "journal_event_counts": REPLAY._event_counts(  # noqa: SLF001
                    [{"event": event["event"]} for event in journal_events]
                ),
                "ledger_event_counts": REPLAY._event_counts(  # noqa: SLF001
                    [{"event": event["event"]} for event in ledger_events]
                ),
            },
            "fresh_process_required": True,
            "incumbent_export": {
                "incumbent_identity": _identity(raw_incumbent),
                "present": True,
                "solution_vector_identity": _identity(final_vector),
            },
            "raw_metrics": {"branches": 1},
            "raw_proof_summary": {},
            "raw_solver_status": "UNKNOWN",
            "runtime_wall_monotonic_ns": 1,
            "schema_version": REPLAY.RESULT_SCHEMA,
            "selection_nonce": "selection-fixture",
            "slot": "region-capacity-ab-treatment",
            "status": "RAW_ARM_OBSERVATION_COMPLETE",
            "workers": 1,
        },
    )
    return {
        "baseline": baseline,
        "cut_free": _cut_free(evidence, _identity(raw_incumbent)),
        "journal": journal,
        "ledger": ledger,
        "result": result,
    }


@pytest.mark.parametrize(
    ("branch", "classification"),
    (
        ("zero", REPLAY.ORGANIC_NONACTIVATION),
        ("no-applied", REPLAY.NO_ORGANIC_APPLIED_CUT),
        ("applied", REPLAY.ORGANIC_APPLIED),
    ),
)
def test_replay_classifies_raw_journal_branches(
    tmp_path: Path,
    branch: str,
    classification: str,
) -> None:
    fixture = _fixture(tmp_path, branch)
    receipt = REPLAY.replay_arm(
        arm_result=fixture["result"],
        cut_free_replay=fixture["cut_free"],
        replay_tool_identity=_identity(TOOL_PATH),
    )
    assert receipt["classification"] == classification
    assert all(value is False for value in receipt["authorizations"].values())
    assert receipt["arm_incumbent_present"] is True
    assert receipt["enabled_families"] == ["region_capacity"]
    assert receipt["replay_tool_identity"] == _identity(TOOL_PATH)
    assert receipt["slot"] == "region-capacity-ab-treatment"
    if branch == "applied":
        assert receipt["applied_inequality_evaluations"][0]["violated"] is True


def test_budget_unknown_without_new_incumbent_replays_admitted_baseline(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, "zero")
    result = REPLAY._strict_json(  # noqa: SLF001
        fixture["result"].read_bytes(),
        "fixture result",
        canonical=True,
        allow_float=True,
    )
    result["incumbent_export"] = {
        "incumbent_identity": None,
        "present": False,
        "solution_vector_identity": None,
    }
    fixture["result"].write_bytes(REPLAY.canonical_json(result))
    cut_free = _cut_free(
        tmp_path / "baseline-replay",
        _identity(fixture["baseline"]),
    )
    receipt = REPLAY.replay_arm(
        arm_result=fixture["result"],
        cut_free_replay=cut_free,
        replay_tool_identity=_identity(TOOL_PATH),
    )
    assert receipt["arm_incumbent_present"] is False
    assert receipt["cut_free_replay_subject_identity"] == _identity(fixture["baseline"])


def test_generated_compiled_applied_lineage_mutations_fail_closed() -> None:
    generated = [
        {
            "cut_id": "cut-1",
            "event": "GENERATED",
            "family": "region_capacity",
        }
    ]
    compiled = [
        {
            "compiled_digest": "a" * 64,
            "cut_id": "cut-1",
            "plan": {
                "digest": "b" * 64,
                "family": "region_capacity",
                "semantic_fingerprint": "c" * 64,
            },
        }
    ]
    applied = [
        {
            "cut_id": "cut-1",
            "event": "APPLIED",
            "family": "region_capacity",
            "plan_digest": "b" * 64,
            "semantic_fingerprint": "c" * 64,
        }
    ]
    summary = REPLAY._replay_cut_lineage(  # noqa: SLF001
        ledger_events=generated,
        compiled=compiled,
        applied=applied,
        enabled_families=["region_capacity"],
    )
    assert summary["generated_uncompiled_cut_ids"] == []
    assert summary["compiled_unapplied_cut_ids"] == []

    with pytest.raises(REPLAY.ReplayError, match="GENERATED"):
        REPLAY._replay_cut_lineage(  # noqa: SLF001
            ledger_events=[
                {
                    **generated[0],
                    "family": "shape_packing_hall",
                }
            ],
            compiled=compiled,
            applied=applied,
            enabled_families=["region_capacity"],
        )
    with pytest.raises(REPLAY.ReplayError, match="COMPILED"):
        REPLAY._replay_cut_lineage(  # noqa: SLF001
            ledger_events=[
                {
                    **generated[0],
                    "cut_id": "cut-other",
                }
            ],
            compiled=compiled,
            applied=applied,
            enabled_families=["region_capacity"],
        )
    with pytest.raises(REPLAY.ReplayError, match="COMPILED"):
        REPLAY._replay_cut_lineage(  # noqa: SLF001
            ledger_events=generated,
            compiled=[compiled[0], dict(compiled[0])],
            applied=applied,
            enabled_families=["region_capacity"],
        )


def test_model_evidence_and_plan_mutations_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, "applied")
    fixture["journal"].write_bytes(fixture["journal"].read_bytes() + b"{}\n")
    with pytest.raises(REPLAY.ReplayError):
        REPLAY.replay_arm(
            arm_result=fixture["result"],
            cut_free_replay=fixture["cut_free"],
            replay_tool_identity=_identity(TOOL_PATH),
        )


def test_unknown_proto_field_and_same_fd_toctou_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pre, _ = _models(tmp_path, applied=False)
    unknown = _write(
        tmp_path / "unknown.pb",
        pre.read_bytes() + b"\xf8\x07\x01",
    )
    with pytest.raises(REPLAY.ReplayError, match="unknown protobuf fields"):
        REPLAY._parse_model(  # noqa: SLF001
            REPLAY.snapshot_regular(unknown),
            "unknown",
        )

    target = _write(tmp_path / "toctou.json", b"old-bytes")
    replacement = _write(tmp_path / "replacement.json", b"new-bytes")
    real_read = REPLAY.os.read
    switched = False

    def read_and_switch(descriptor: int, count: int) -> bytes:
        nonlocal switched
        if not switched:
            switched = True
            replacement.replace(target)
        return real_read(descriptor, count)

    monkeypatch.setattr(REPLAY.os, "read", read_and_switch)
    with pytest.raises(REPLAY.ReplayError, match="changed during read"):
        REPLAY.snapshot_regular(target)
    assert target.read_bytes() == b"new-bytes"


def test_output_no_overwrite_and_no_runner_import(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, "zero")
    receipt = REPLAY.replay_arm(
        arm_result=fixture["result"],
        cut_free_replay=fixture["cut_free"],
        replay_tool_identity=_identity(TOOL_PATH),
    )
    output = tmp_path / "receipt.json"
    REPLAY.write_exclusive(output, receipt)
    before = output.read_bytes()
    with pytest.raises(REPLAY.ReplayError, match="overwrite"):
        REPLAY.write_exclusive(output, receipt)
    assert output.read_bytes() == before
    source = TOOL_PATH.read_text(encoding="utf-8")
    assert "import organic_arm_runner_v1" not in source
    assert "import ab16_contract_v1" not in source
    assert "from src.cuts" not in source
