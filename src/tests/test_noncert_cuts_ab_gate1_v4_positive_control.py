from __future__ import annotations

import copy
import hashlib
import importlib.util
import os
from pathlib import Path
from typing import Any

import pytest
from ortools.sat import cp_model_pb2


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab_trust_gate1_v4_20260724"


def _load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POSITIVE = _load("noncert_cuts_gate1_v4_positive", "positive_control_v4.py")
CHECKER = _load("noncert_cuts_gate1_v4_arithmetic", "independent_arithmetic_v4.py")


def _fixture(tmp_path: Path, name: str = "fixture") -> tuple[Path, dict[str, object]]:
    root = tmp_path / name
    POSITIVE.build_tiny_offline_fixture(root)
    return root, CHECKER.load_fixture(root)


def _replace_json_member(member: dict[str, object], value: object) -> None:
    raw = CHECKER.canonical_json(value) + b"\n"
    identity = member["identity"]
    assert isinstance(identity, dict)
    member["raw"] = raw
    member["identity"] = {
        **identity,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _replace_binary_member(member: dict[str, object], raw: bytes) -> None:
    identity = member["identity"]
    assert isinstance(identity, dict)
    member["raw"] = raw
    member["identity"] = {
        **identity,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _sync_arm_identity(
    arm: dict[str, object],
    role: str,
    evidence_key: str,
) -> None:
    members = arm["members"]
    evidence = arm["evidence"]
    assert isinstance(members, dict) and isinstance(evidence, dict)
    member = members[role]
    assert isinstance(member, dict)
    evidence[evidence_key] = member["identity"]


def test_tiny_pair_passes_independent_replay_without_solver_or_systemd(
    tmp_path: Path,
) -> None:
    root, bundle = _fixture(tmp_path)

    result = CHECKER.verify_bundle(bundle)

    assert result["status"] == "PASS_MECHANISM_POSITIVE_CONTROL"
    assert result["control"] == {"generated": 0, "compiled": 0, "applied": 0}
    assert result["treatment"] == {"generated": 1, "compiled": 1, "applied": 1}
    assert result["selected"]["lhs"] == 2
    assert result["selected"]["rhs"] == 1
    assert result["common_prestate"]["post_solve_performed"] is False
    for arm in ("control", "treatment"):
        evidence = bundle["arms"][arm]["evidence"]
        assert evidence["post_solve_performed"] is False
        assert evidence["post_response_present"] is False
        assert not (root / "arms" / arm / "post-injection-response.pb").exists()


def test_drill_and_formal_verifier_purposes_are_strictly_disjoint(
    tmp_path: Path,
) -> None:
    _root, drill = _fixture(tmp_path)
    assert CHECKER.verify_bundle(drill)["schema"] == CHECKER.DRILL_RECEIPT_SCHEMA

    relabelled = copy.deepcopy(drill)
    relabelled["selection"]["schema"] = CHECKER.FORMAL_SELECTION_SCHEMA
    relabelled["selection"]["purpose"] = CHECKER.FORMAL_PURPOSE
    relabelled["selection"]["gate1_formal_eligible"] = True

    with pytest.raises(ValueError, match="offline fixture selection"):
        CHECKER.verify_bundle(relabelled)
    with pytest.raises(ValueError, match="manual (?:drill arm|fixture) schema"):
        CHECKER.verify_formal_bundle(relabelled)


def test_formal_verifier_rejects_drill_eligibility_and_manual_provider(
    tmp_path: Path,
) -> None:
    _root, bundle = _fixture(tmp_path)
    with pytest.raises(ValueError, match="formal campaign selection"):
        CHECKER.verify_formal_bundle(bundle)

    relabelled = copy.deepcopy(bundle)
    relabelled["selection"]["schema"] = CHECKER.FORMAL_SELECTION_SCHEMA
    relabelled["selection"]["purpose"] = CHECKER.FORMAL_PURPOSE
    relabelled["selection"]["gate1_formal_eligible"] = True
    for arm in ("control", "treatment"):
        evidence = relabelled["arms"][arm]["evidence"]
        evidence["schema"] = CHECKER.FORMAL_ARM_SCHEMA
        evidence["phase"] = "formal_post_injection_clone"
        evidence["production_attach"] = {}
        for record in evidence["injection"]["compiled_records"]:
            record["schema"] = CHECKER.FORMAL_COMPILED_SCHEMA

    with pytest.raises(ValueError, match="manual non-proof provider"):
        CHECKER.verify_formal_bundle(relabelled)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("purpose", "gate1_v4_e2e_drill"),
        ("gate1_formal_eligible", False),
        ("schema", CHECKER.SELECTION_SCHEMA),
    ],
)
def test_formal_selection_mutations_fail_before_arithmetic(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    _root, bundle = _fixture(tmp_path)
    bundle["selection"]["schema"] = CHECKER.FORMAL_SELECTION_SCHEMA
    bundle["selection"]["purpose"] = CHECKER.FORMAL_PURPOSE
    bundle["selection"]["gate1_formal_eligible"] = True
    bundle["selection"][field] = value

    with pytest.raises(ValueError, match="formal campaign selection"):
        CHECKER.verify_formal_bundle(bundle)


def test_common_prestate_and_both_bindings_must_precede_any_clone(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ordered"
    os.mkdir(root)
    selection = {
        "schema": POSITIVE.SELECTION_SCHEMA,
        "purpose": "gate1_v4_e2e_drill",
        "campaign_id": "campaign",
        "run_nonce": "nonce",
        "manager_epoch_digest": "epoch",
        "gate1_formal_eligible": False,
    }
    selection_identity = POSITIVE._write_json_exclusive(  # noqa: SLF001
        root / "selection.json",
        selection,
    )
    values = POSITIVE.tiny_inputs()
    POSITIVE.seal_common_prestate(
        root,
        **values,
        selection_identity=selection_identity,
        campaign_id="campaign",
        run_nonce="nonce",
        manager_epoch_digest="epoch",
    )
    assert not (root / "bindings").exists()
    assert not (root / "arms").exists()
    with pytest.raises((FileNotFoundError, ValueError)):
        POSITIVE.materialize_arm(root, "control")

    POSITIVE.create_arm_bindings(root)
    assert (root / "bindings" / "control.json").is_file()
    assert (root / "bindings" / "treatment.json").is_file()
    assert (root / "bindings" / "bindings-seal.json").is_file()
    assert not (root / "arms").exists()

    POSITIVE.materialize_arm(root, "control")
    POSITIVE.materialize_arm(root, "treatment")
    assert CHECKER.verify_fixture(root)["status"] == "PASS_MECHANISM_POSITIVE_CONTROL"


def test_control_clone_is_identical_and_treatment_is_exactly_one_constraint(
    tmp_path: Path,
) -> None:
    _root, bundle = _fixture(tmp_path)
    pre_raw = bundle["common_artifacts"]["pre_model"]["raw"]
    control_raw = bundle["arms"]["control"]["members"]["post_model"]["raw"]
    treatment_raw = bundle["arms"]["treatment"]["members"]["post_model"]["raw"]

    assert control_raw == pre_raw
    post = cp_model_pb2.CpModelProto()
    post.ParseFromString(treatment_raw)
    stripped = cp_model_pb2.CpModelProto()
    stripped.CopyFrom(post)
    del stripped.constraints[-1]
    assert stripped.SerializeToString(deterministic=True) == pre_raw
    assert post.constraints[-1].WhichOneof("constraint") == "linear"


def test_no_overwrite_and_symlink_parent_are_rejected(tmp_path: Path) -> None:
    root, _bundle = _fixture(tmp_path)
    with pytest.raises(FileExistsError):
        POSITIVE.build_tiny_offline_fixture(root)

    real_parent = tmp_path / "real"
    real_parent.mkdir()
    link_parent = tmp_path / "link"
    link_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        POSITIVE.build_tiny_offline_fixture(link_parent / "fixture")


def test_common_response_solution_drift_is_rejected(tmp_path: Path) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    solution = [1, 0, 1, 0]
    member = mutated["common_artifacts"]["solution"]
    _replace_json_member(member, solution)
    mutated["common"]["artifacts"]["solution"] = member["identity"]
    common = mutated["common"]
    common["common_prestate_id"] = CHECKER.digest_json(
        {
            "campaign_id": common["campaign_id"],
            "run_nonce": common["run_nonce"],
            "manager_epoch_digest": common["manager_epoch_digest"],
            "selection_identity": mutated["selection_identity"],
            "artifacts": common["artifacts"],
            "phase": "pre_injection",
        }
    )

    with pytest.raises(ValueError, match="solution differs"):
        CHECKER.verify_bundle(mutated)


def test_noncanonical_or_unknown_binary_prestate_is_rejected(tmp_path: Path) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    member = mutated["common_artifacts"]["pre_model"]
    _replace_binary_member(member, member["raw"] + b"\xa0\x06\x01")
    mutated["common"]["artifacts"]["pre_model"] = member["identity"]
    common = mutated["common"]
    common["common_prestate_id"] = CHECKER.digest_json(
        {
            "campaign_id": common["campaign_id"],
            "run_nonce": common["run_nonce"],
            "manager_epoch_digest": common["manager_epoch_digest"],
            "selection_identity": mutated["selection_identity"],
            "artifacts": common["artifacts"],
            "phase": "pre_injection",
        }
    )

    with pytest.raises(ValueError, match="unknown, duplicate, or noncanonical"):
        CHECKER.verify_bundle(mutated)


def test_binding_or_selection_byte_identity_drift_is_rejected(tmp_path: Path) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    mutated["bindings"]["control"]["value"]["selection_identity"]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="binding selection"):
        CHECKER.verify_bundle(mutated)


@pytest.mark.parametrize(
    ("arm", "field", "value", "message"),
    [
        ("control", "applied", 1, "control injection evidence"),
        ("treatment", "generated", 0, "treatment injection evidence"),
        ("treatment", "compiled", 0, "treatment injection evidence"),
        ("treatment", "applied", 0, "treatment injection evidence"),
    ],
)
def test_arm_count_drift_is_rejected(
    tmp_path: Path,
    arm: str,
    field: str,
    value: int,
    message: str,
) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    mutated["arms"][arm]["evidence"]["injection"][field] = value

    with pytest.raises(ValueError, match=message):
        CHECKER.verify_bundle(mutated)


@pytest.mark.parametrize("field", ["post_solve_performed", "post_response_present"])
def test_post_attach_solve_or_response_claim_is_rejected(
    tmp_path: Path,
    field: str,
) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    mutated["arms"]["treatment"]["evidence"][field] = True

    with pytest.raises(ValueError, match="evidence schema/provenance"):
        CHECKER.verify_bundle(mutated)


def test_post_model_constraint_mutation_is_rejected_even_when_resealed(
    tmp_path: Path,
) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    treatment = mutated["arms"]["treatment"]
    member = treatment["members"]["post_model"]
    model = cp_model_pb2.CpModelProto()
    model.ParseFromString(member["raw"])
    model.constraints[-1].linear.domain[-1] = 2
    _replace_binary_member(member, model.SerializeToString(deterministic=True))
    _sync_arm_identity(treatment, "post_model", "post_model_identity")

    with pytest.raises(ValueError, match="post-model inequality"):
        CHECKER.verify_bundle(mutated)


def test_assignment_mutation_is_rejected_even_when_resealed(tmp_path: Path) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    treatment = mutated["arms"]["treatment"]
    member = treatment["members"]["assignment"]
    assignment = CHECKER._parse_json_member(member, label="assignment")  # noqa: SLF001
    assignment["variables"][0]["value"] = 0
    assignment["variables"][1]["value"] = 1
    _replace_json_member(member, assignment)
    _sync_arm_identity(treatment, "assignment", "assignment_identity")

    with pytest.raises(ValueError, match="assignment differs"):
        CHECKER.verify_bundle(mutated)


def test_ledger_join_mutation_is_rejected_even_with_valid_hash_chain(
    tmp_path: Path,
) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    treatment = mutated["arms"]["treatment"]
    ledger = CHECKER.replay_ledger(treatment["members"]["ledger"]["raw"])
    cores = [CHECKER._event_core(event) for event in ledger["events"]]  # noqa: SLF001
    cores[-2]["receipt"]["constraint_index"] = 99
    raw, summary = POSITIVE._ledger(  # noqa: SLF001
        cores,
        scope_id=f"{mutated['common']['run_nonce']}-treatment",
    )
    _replace_binary_member(treatment["members"]["ledger"], raw)
    _sync_arm_identity(treatment, "ledger", "ledger_identity")
    treatment["evidence"]["ledger"] = summary

    with pytest.raises(ValueError, match="ledger events"):
        CHECKER.verify_bundle(mutated)


def test_joint_wrong_literal_model_assignment_sample_and_ledger_is_rejected(
    tmp_path: Path,
) -> None:
    _root, bundle = _fixture(tmp_path)
    mutated = copy.deepcopy(bundle)
    treatment = mutated["arms"]["treatment"]
    evidence = treatment["evidence"]
    compiled = evidence["injection"]["compiled_records"][0]
    wrong_literal = {"index": 1, "name": "ghost__1_0_2_1"}
    compiled["condition_literals"] = [wrong_literal]
    compiled["post_constraint"]["enforcement_literals"] = [1]

    post_member = treatment["members"]["post_model"]
    post = cp_model_pb2.CpModelProto()
    post.ParseFromString(post_member["raw"])
    post.constraints[-1].enforcement_literal[0] = 1
    _replace_binary_member(post_member, post.SerializeToString(deterministic=True))
    _sync_arm_identity(treatment, "post_model", "post_model_identity")

    sample_member = treatment["members"]["samples"]
    sample_corpus = CHECKER._parse_json_member(sample_member, label="samples")  # noqa: SLF001
    sample_corpus["samples"][0]["enforcement_literals"] = [{**wrong_literal, "value": 1}]
    _replace_json_member(sample_member, sample_corpus)
    _sync_arm_identity(treatment, "samples", "sample_corpus_identity")

    assignment_member = treatment["members"]["assignment"]
    assignment = CHECKER._parse_json_member(assignment_member, label="assignment")  # noqa: SLF001
    assignment["variables"][0]["value"] = 0
    assignment["variables"][1]["value"] = 1
    _replace_json_member(assignment_member, assignment)
    _sync_arm_identity(treatment, "assignment", "assignment_identity")

    ledger = CHECKER.replay_ledger(treatment["members"]["ledger"]["raw"])
    cores = [CHECKER._event_core(event) for event in ledger["events"]]  # noqa: SLF001
    cores[-2]["receipt"]["condition_lits"] = [wrong_literal]
    ledger_raw, summary = POSITIVE._ledger(  # noqa: SLF001
        cores,
        scope_id=f"{mutated['common']['run_nonce']}-treatment",
    )
    _replace_binary_member(treatment["members"]["ledger"], ledger_raw)
    _sync_arm_identity(treatment, "ledger", "ledger_identity")
    evidence["ledger"] = summary

    with pytest.raises(ValueError, match="post-model inequality"):
        CHECKER.verify_bundle(mutated)
