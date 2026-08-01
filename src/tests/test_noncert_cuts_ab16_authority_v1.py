from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = PROJECT_ROOT / "docs/research/noncert_cuts_ab16_20260724"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load(RESEARCH_DIR / "ab16_authority_v1.py", "ab16_retry_authority_tested")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", ".")
    _git(
        repository,
        "-c",
        "user.name=AB16 Test",
        "-c",
        "user.email=ab16@example.invalid",
        "commit",
        "-m",
        message,
    )
    return _git(repository, "rev-parse", "HEAD")


def _fixture(tmp_path: Path) -> dict[str, object]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")
    tracked = repository / "tracked.txt"
    repairable_tool = repository / "repairable_tool.py"
    tracked.write_text("initial\n", encoding="utf-8")
    repairable_tool.write_text("VERSION = 1\n", encoding="utf-8")
    first_head = _commit(repository, "initial")

    campaign = tmp_path / "run-ab16-test"
    campaign.mkdir()
    (campaign / "prospective-ab16").mkdir()
    preregistration = AUTH.bootstrap._path_preregistration(campaign)  # noqa: SLF001
    preregistration_path = campaign / "scientific-preregistration.json"
    _write(preregistration_path, preregistration)

    scientific_paths = AUTH._scientific_source_paths(  # noqa: SLF001
        preregistration_path,
        preregistration,
        AUTH.contract.ARM_SEQUENCE[0],
    )
    all_paths = set(scientific_paths.values())
    all_paths.update(Path(path) for path in preregistration["binding_paths"].values())
    for index, path in enumerate(sorted(all_paths, key=os.fspath)):
        if path == preregistration_path:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fixed-scientific-input-{index}\n".encode())

    return {
        "campaign": campaign,
        "first_head": first_head,
        "preregistration": preregistration,
        "preregistration_path": preregistration_path,
        "repairable_tool": repairable_tool,
        "repository": repository,
        "tracked": tracked,
    }


def _prepare(fixture: dict[str, object], *, slot: str | None = None) -> dict[str, object]:
    return AUTH.prepare_attempt(
        fixture["preregistration_path"],
        repository_root=fixture["repository"],
        slot=slot,
        additional_execution_tools={"repairable_fixture": fixture["repairable_tool"]},
    )


def _selection(attempt_dir: Path) -> tuple[Path, dict[str, object]]:
    path = attempt_dir / "work" / "selection.json"
    _write(path, {"purpose": "test selection", "schema_version": "test-selection-v1"})
    _raw, identity = AUTH._snapshot(path)  # noqa: SLF001
    return path, identity


def _credible_gate(attempt_dir: Path, *, slot: str, selection_identity: dict[str, object]) -> Path:
    path = attempt_dir / "work" / "arm-gate.json"
    _write(
        path,
        {
            "authorizations": {
                "family_global_soundness_authorized": False,
                "global_claim_authorized": False,
                "mathematical_claim_authorized": False,
                "production_certified_authorized": False,
                "runtime_effect_authorized": False,
                "stage_b_promotion_authorized": False,
            },
            "credibility_status": "PASS",
            "schema_version": "noncert-cuts-ab16-arm-credibility-gate-v1",
            "selection_identity": selection_identity,
            "slot": slot,
            "status": "PASS",
        },
    )
    return path


def _assert_false_authorizations(value: object) -> None:
    if type(value) is dict:
        for key, member in value.items():
            if "authoriz" in key:
                if type(member) is dict:
                    assert member
                    assert all(item is False for item in member.values())
                else:
                    assert member is False
            _assert_false_authorizations(member)
    elif type(value) is list:
        for member in value:
            _assert_false_authorizations(member)


def test_incomplete_attempt_can_retry_after_clean_code_fix(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]

    first = _prepare(fixture, slot=slot)
    first_attempt = Path(first["attempt_dir"])
    first_input_bytes = (first_attempt / "attempt-input-set.json").read_bytes()
    first_preregistration_sha = first["preregistration_sha256"]
    assert first["attempt_ordinal"] == 1
    assert first["repository_head"] == fixture["first_head"]

    closed = AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="EXECUTION_TOOL_BUG",
    )
    assert closed["retry_disposition"] == "SAME_SLOT_RETRY_ALLOWED"

    fixture["repairable_tool"].write_text("VERSION = 2\n", encoding="utf-8")
    fixture["tracked"].write_text("repair\n", encoding="utf-8")
    second_head = _commit(fixture["repository"], "repair")
    second = _prepare(fixture, slot=slot)
    second_attempt = Path(second["attempt_dir"])

    assert second["attempt_ordinal"] == 2
    assert second["repository_head"] == second_head != first["repository_head"]
    assert second["preregistration_sha256"] == first_preregistration_sha
    assert second["input_set_sha256"] != first["input_set_sha256"]
    assert (first_attempt / "attempt-input-set.json").read_bytes() == first_input_bytes

    selection_path, selection_identity = _selection(second_attempt)
    AUTH.bind_selection(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=2,
        selection_path=selection_path,
    )
    gate_path = _credible_gate(second_attempt, slot=slot, selection_identity=selection_identity)
    credible = AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=2,
        outcome=AUTH.CREDIBLE_TERMINAL,
        evidence_paths={"arm_gate": gate_path},
    )
    assert credible["retry_disposition"] == "SLOT_CLOSED"

    replay = AUTH.replay_campaign(fixture["preregistration_path"])
    assert replay["consumption_state"]["next_index"] == 1
    assert [attempt["outcome"] for attempt in replay["attempts"]] == [
        AUTH.CREDIBILITY_INCOMPLETE,
        AUTH.CREDIBLE_TERMINAL,
    ]
    next_slot = AUTH.contract.ARM_SEQUENCE[1]
    third = _prepare(fixture, slot=next_slot)
    assert third["slot"] == next_slot
    assert third["attempt_ordinal"] == 1

    for path in (
        first_attempt / "attempt-input-set.json",
        first_attempt / "attempt-result.json",
        second_attempt / "attempt-input-set.json",
        second_attempt / "attempt-result.json",
    ):
        _assert_false_authorizations(json.loads(path.read_text(encoding="utf-8")))


def test_unresolved_attempt_blocks_retry_and_records_are_no_overwrite(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture)
    attempt_dir = Path(prepared["attempt_dir"])

    with pytest.raises(AUTH.AuthorityError, match="must close"):
        _prepare(fixture)

    selection_path, _selection_identity = _selection(attempt_dir)
    AUTH.bind_selection(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        selection_path=selection_path,
    )
    with pytest.raises(AUTH.AuthorityError, match="no-overwrite"):
        AUTH.bind_selection(
            fixture["preregistration_path"],
            slot=slot,
            attempt_ordinal=1,
            selection_path=selection_path,
        )
    AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="RUN_FAILED",
    )
    with pytest.raises(AUTH.AuthorityError, match="only the active"):
        AUTH.close_attempt(
            fixture["preregistration_path"],
            slot=slot,
            attempt_ordinal=1,
            outcome=AUTH.CREDIBILITY_INCOMPLETE,
            failure_code="REWRITE",
        )


@pytest.mark.parametrize("case", ["unknown", "symlink", "gap", "future"])
def test_slot_topology_fails_closed(tmp_path: Path, case: str) -> None:
    fixture = _fixture(tmp_path)
    preregistration = fixture["preregistration"]
    first_root = Path(preregistration["slot_roots"][AUTH.contract.ARM_SEQUENCE[0]])
    first_root.mkdir(parents=True)
    if case == "unknown":
        (first_root / "notes.txt").write_text("unexpected\n", encoding="utf-8")
    elif case == "symlink":
        target = tmp_path / "target"
        target.mkdir()
        (first_root / "attempt-0001").symlink_to(target, target_is_directory=True)
    elif case == "gap":
        (first_root / "attempt-0002").mkdir()
    else:
        future_root = Path(preregistration["slot_roots"][AUTH.contract.ARM_SEQUENCE[1]])
        (future_root / "attempt-0001").mkdir(parents=True)
    with pytest.raises(AUTH.AuthorityError):
        AUTH.replay_campaign(fixture["preregistration_path"])


def test_snapshot_tamper_fails_replay_but_source_code_repair_does_not(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    prepared = _prepare(fixture)
    attempt_dir = Path(prepared["attempt_dir"])
    input_record = json.loads((attempt_dir / "attempt-input-set.json").read_text(encoding="utf-8"))
    tool_snapshot = Path(input_record["tool_identities"]["repairable_fixture"]["path"])

    fixture["repairable_tool"].write_text("VERSION = 99\n", encoding="utf-8")
    fixture["tracked"].write_text("new source\n", encoding="utf-8")
    _commit(fixture["repository"], "later repair")
    assert AUTH.replay_campaign(fixture["preregistration_path"])["active_attempt"] is not None

    tool_snapshot.write_text("tampered snapshot\n", encoding="utf-8")
    with pytest.raises(AUTH.AuthorityError, match="drifted"):
        AUTH.replay_campaign(fixture["preregistration_path"])


def test_scientific_input_drift_is_rejected_before_allocating_retry(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    first = _prepare(fixture)
    AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="RETRY",
    )
    preregistration = fixture["preregistration"]
    Path(preregistration["baseline_incumbent_path"]).write_text("changed science\n", encoding="utf-8")
    with pytest.raises(AUTH.AuthorityError, match="scientific inputs changed"):
        _prepare(fixture)
    slot_root = Path(preregistration["slot_roots"][slot])
    assert sorted(path.name for path in slot_root.iterdir()) == ["attempt-0001"]
    assert Path(first["attempt_dir"]).is_dir()


def test_tracked_dirty_repository_is_rejected_without_consuming_attempt(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["tracked"].write_text("dirty\n", encoding="utf-8")
    with pytest.raises(AUTH.AuthorityError, match="not clean"):
        _prepare(fixture)
    slot_root = Path(fixture["preregistration"]["slot_roots"][AUTH.contract.ARM_SEQUENCE[0]])
    assert not slot_root.exists()


def test_credible_gate_must_join_selection_and_keep_authority_false(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture)
    attempt_dir = Path(prepared["attempt_dir"])
    selection_path, selection_identity = _selection(attempt_dir)
    AUTH.bind_selection(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        selection_path=selection_path,
    )
    gate_path = _credible_gate(attempt_dir, slot=slot, selection_identity=selection_identity)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["authorizations"]["runtime_effect_authorized"] = True
    _write(gate_path, gate)
    with pytest.raises(AUTH.AuthorityError, match="research-only PASS"):
        AUTH.close_attempt(
            fixture["preregistration_path"],
            slot=slot,
            attempt_ordinal=1,
            outcome=AUTH.CREDIBLE_TERMINAL,
            evidence_paths={"arm_gate": gate_path},
        )


def test_preregistration_and_result_hash_tampering_fail_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    slot = AUTH.contract.ARM_SEQUENCE[0]
    prepared = _prepare(fixture)
    AUTH.close_attempt(
        fixture["preregistration_path"],
        slot=slot,
        attempt_ordinal=1,
        outcome=AUTH.CREDIBILITY_INCOMPLETE,
        failure_code="EXPECTED",
    )
    result_path = Path(prepared["attempt_dir"]) / "attempt-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["failure_code"] = "TAMPERED"
    _write(result_path, result)
    with pytest.raises(AUTH.AuthorityError, match="envelope"):
        AUTH.replay_campaign(fixture["preregistration_path"])

    preregistration_path = fixture["preregistration_path"]
    original = preregistration_path.read_bytes()
    preregistration_path.write_bytes(original + b"\n")
    with pytest.raises(AUTH.AuthorityError, match="canonical"):
        AUTH.replay_campaign(preregistration_path)


def test_source_contains_no_permanent_freeze_or_hostile_same_uid_mechanism() -> None:
    source = (RESEARCH_DIR / "ab16_authority_v1.py").read_text(encoding="utf-8")
    retired_terms = (
        "immediate-stop",
        "CAMPAIGN_IMMEDIATE_STOPPED",
        "renameat2",
        "AF_UNIX",
        "PathFinder",
        "same-UID",
        ".chmod(",
        "os.chmod(",
    )
    assert all(term not in source for term in retired_terms)


def test_attempt_input_digest_recomputes_from_snapshots(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    prepared = _prepare(fixture)
    input_path = Path(prepared["attempt_dir"]) / "attempt-input-set.json"
    record = json.loads(input_path.read_text(encoding="utf-8"))
    assert record["input_set_sha256"] == AUTH.contract.attempt_input_set_sha256(
        preregistration_sha256=record["preregistration_sha256"],
        repository_head=record["repository_head"],
        strict_input_identities=record["strict_input_identities"],
        tool_identities=record["tool_identities"],
    )
    assert hashlib.sha256(Path(record["preregistration_identity"]["path"]).read_bytes()).hexdigest() == record[
        "preregistration_sha256"
    ]
