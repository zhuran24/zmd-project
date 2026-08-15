"""Focused contracts for knowledge backfill and reasoning projections."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devtools.build_knowledge_docs import (  # noqa: E402
    AUTHORITY_BASIS_BY_AUTHORITY,
    REPRESENTATION_CLASS_MAPPING,
    KnowledgeError,
    _validate_claim_authority,
    _validate_decision_authority_source,
    _validate_decision_supersession,
    _validate_evidence,
    _validate_representation_mapping,
    _validate_validity_profile,
    check_repository,
    load_model,
    render_backfill_ledger,
)


def _census(model) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in model.knowledge_census["counts"].items()
    }


def _validity_claim(
    *,
    status: str = "current",
    supersedes: list[str] | None = None,
    event_type: str = "scope_correction",
    reuse_policy: str = "unaffected_under_premises",
    repair_state: str = "revalidated",
    basis: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": "CLAIM-TEST-VALIDITY",
        "status": status,
        "supersedes": supersedes or [],
        "validity_profile": {
            "event_type": event_type,
            "affected_layers": ["proof_argument"],
            "basis": basis or ["independent_recomputation"],
            "reuse_policy": reuse_policy,
            "repair_state": repair_state,
            "temporal_scope": "design_version",
        },
    }


def test_validity_profile_rejects_unvalidated_reuse_states() -> None:
    invalid = (
        _validity_claim(reuse_policy="current_after_repair", repair_state="pending"),
        _validity_claim(reuse_policy="revalidate_before_use", repair_state="revalidated"),
        _validity_claim(reuse_policy="unaffected_under_premises", repair_state="pending"),
        _validity_claim(
            event_type="revalidation",
            reuse_policy="historical_only",
            repair_state="revalidated",
            basis=["evidence_gap"],
        ),
        _validity_claim(
            status="refuted",
            event_type="refutation",
            reuse_policy="current_after_repair",
        ),
    )

    for claim in invalid:
        with pytest.raises(KnowledgeError):
            _validate_validity_profile(claim)


def test_refuted_superseded_and_successor_claims_require_validity_profiles() -> None:
    for claim in (
        {"id": "CLAIM-REFUTED", "status": "refuted", "supersedes": []},
        {"id": "CLAIM-SUPERSEDED", "status": "superseded", "supersedes": []},
        {"id": "CLAIM-SUCCESSOR", "status": "current", "supersedes": ["CLAIM-OLD"]},
    ):
        with pytest.raises(KnowledgeError):
            _validate_validity_profile(claim)

def test_real_repository_knowledge_projections_are_fresh() -> None:
    assert check_repository(PROJECT_ROOT) == ()


def test_open_questions_projection_is_exact_and_deduplicated() -> None:
    model = load_model(PROJECT_ROOT)
    open_claim_ids = sorted(
        str(claim["id"]) for claim in model.claims if claim["status"] == "open"
    )
    indexed_open_ids = {
        str(claim_id)
        for topic in model.topics["records"]
        for claim_id in topic["open_question_claim_ids"]
    }
    page = (PROJECT_ROOT / "docs/OPEN_QUESTIONS.md").read_text(encoding="utf-8")

    assert open_claim_ids == [
        "CLAIM-CERTIFIED-EXISTENCE-OPEN",
        "CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN",
        "CLAIM-P2-MIN-SIDE-UPPER-OPEN",
    ]
    assert indexed_open_ids == set(open_claim_ids)
    for claim_id in open_claim_ids:
        assert page.count(f'<a id="{claim_id.lower()}"></a>') == 1
        assert f"`{claim_id}`" in page
    assert "CLAIM-ZERO-SLACK-AUDIT-METHOD" not in page
    assert "100% inventory coverage" not in page


def test_active_workflow_with_current_review_counts_once_and_stays_out_of_triage() -> None:
    model = load_model(PROJECT_ROOT)
    dossier_id = "DOSSIER-SOLVER-REASONING-OUTER-LOOP-REVIEWS-20260815-D26B592E99"
    dossier = deepcopy(model.dossier_by_id[dossier_id])
    review = deepcopy(model.current_review_by_dossier[dossier_id])
    dossiers = deepcopy(model.dossiers)
    dossiers["records"] = [dossier]
    triage = deepcopy(model.backfill_triage)
    triage["groups"] = []
    fixture = replace(
        model,
        dossiers=dossiers,
        backfill_reviews=(review,),
        backfill_triage=triage,
    )

    page = render_backfill_ledger(fixture, "fixture")

    assert "- dossier 总数：`1`。" in page
    assert "- current review：`1`，其中语义审阅 `1`，availability/provenance-only `0`。" in page
    assert "- 尚无 current review、但已进入唯一 triage group：`0`。" in page
    assert "- 新写入流程中尚未关闭的 active dossier：`1`；其中已有 current review `1`；open workflow 不进入历史 triage。" in page
    assert "- inventory coverage：`1/1`。" in page
    assert "- semantic review coverage：`1/1`。" in page
    assert "| [`TRIAGE-" not in page


def test_backfill_batches_preserve_generic_propagation_evidence_boundary() -> None:
    model = load_model(PROJECT_ROOT)
    profiled = [claim for claim in model.claims if claim.get("reasoning_profile")]
    formal = [
        claim["id"] for claim in profiled if claim["reasoning_profile"]["generic_propagation_evidence"] == "formal"
    ]
    experimental = [
        claim["id"]
        for claim in profiled
        if claim["reasoning_profile"]["generic_propagation_evidence"] == "experimental_only"
    ]

    assert formal == []
    assert experimental == [
        "CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT",
        "CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT",
    ]
    assert len(profiled) == _census(model)["reasoning_profiles"]


def test_knowledge_census_is_the_single_numeric_acceptance_fixture() -> None:
    model = load_model(PROJECT_ROOT)
    census = _census(model)

    assert census["claims_total"] == len(model.claims)
    assert census["decisions_total"] == len(model.decisions)
    assert census["dossiers_total"] == len(model.dossiers["records"])
    assert census["topics_total"] == len(model.topics["records"])
    assert census["terms_total"] == len(model.terminology["records"])
    assert census["current_reviews"] + census["triaged_dossiers"] == census["dossiers_total"]
    assert (
        census["semantic_review_dossiers"] + census["availability_review_dossiers"]
        == census["current_reviews"]
    )


def test_knowledge_authority_interface_is_typed_and_executable() -> None:
    model = load_model(PROJECT_ROOT)
    claims = model.claim_by_id

    assert all(claim["schema_version"] == "zmd_claim_v2" for claim in model.claims)
    assert all(claim["representation_class"] == "AUTHORITATIVE_CURRENT" for claim in model.claims)
    assert all(
        claim["authority_basis"]["basis_type"]
        == AUTHORITY_BASIS_BY_AUTHORITY[claim["authority"]]
        for claim in model.claims
    )
    assert {claim["id"] for claim in model.claims if claim["authority"] == "machine"} == {
        "CLAIM-ACTIVE-SCOPE-SINGLE-BASE",
        "CLAIM-CERTIFIED-THEOREM-SCOPE",
        "CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS",
        "CLAIM-DURABLE-CERTIFIED-RESULT-ABSENT",
        "CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM",
    }
    for claim_id in (
        "CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY",
        "CLAIM-R4-LEX-BAND-2084-UNSAT",
        "CLAIM-SMM4-LEX-BAND-COMPOSITION-2086",
    ):
        assert claims[claim_id]["authority"] == "research_authority"
        assert "verification_id" not in claims[claim_id]["authority_basis"]

    assert model.current_state["representation_class_mapping"] == {
        key: list(values) for key, values in REPRESENTATION_CLASS_MAPPING.items()
    }
    _validate_representation_mapping(model.current_state)


def test_machine_authority_rejects_untracked_sources_and_self_asserted_verifiers() -> None:
    model = load_model(PROJECT_ROOT)
    machine_claim = deepcopy(model.claim_by_id["CLAIM-ACTIVE-SCOPE-SINGLE-BASE"])
    machine_claim["authority_basis"]["source_paths"] = [
        ".artifacts/ab16_arms_20260802/EVAL.md"
    ]
    machine_claim["evidence"].append(
        {
            "path": ".artifacts/ab16_arms_20260802/EVAL.md",
            "role": "workspace receipt",
            "storage": "workspace_untracked",
            "optional": True,
        }
    )
    with pytest.raises(KnowledgeError, match="non-tracked authority sources"):
        _validate_claim_authority(model, machine_claim)

    research_claim = deepcopy(model.claim_by_id["CLAIM-R4-LEX-BAND-2084-UNSAT"])
    research_claim["authority_basis"]["verification_id"] = "invented_verifier"
    with pytest.raises(KnowledgeError, match="non-machine authority cannot advertise"):
        _validate_claim_authority(model, research_claim)


def test_decision_supersession_requires_an_inverse_edge_and_noncurrent_target() -> None:
    model = load_model(PROJECT_ROOT)
    _validate_decision_supersession(model.decisions)

    missing_inverse = deepcopy(model.decisions)
    successor = next(
        record for record in missing_inverse
        if record["id"] == "DECISION-P1-2-RECLOSE-20260806"
    )
    successor["supersedes"] = []
    with pytest.raises(KnowledgeError, match="has no inverse supersedes edge"):
        _validate_decision_supersession(missing_inverse)

    active_target = deepcopy(model.decisions)
    target = next(
        record for record in active_target
        if record["id"] == "DECISION-P1-2-CLOSE-20260707"
    )
    target["status"] = "current"
    with pytest.raises(KnowledgeError, match="cannot supersede active decision"):
        _validate_decision_supersession(active_target)

def test_decision_register_is_non_authorizing_and_external_pointers_are_checked() -> None:
    model = load_model(PROJECT_ROOT)
    external_ids = set()
    for decision in model.decisions:
        assert decision["schema_version"] == "zmd_decision_v2"
        assert decision["non_authorizing"] is True
        assert decision["ruling_event_id"] is None
        assert decision["authority_source"]["path"] in model.tracked_paths
        external_ids.add(decision["external_decision_id"])
        _validate_decision_authority_source(model, decision)
    assert len(external_ids) == len(model.decisions) == _census(model)["decisions_total"]

    broken = deepcopy(model.decisions[0])
    broken["authority_source"]["assertions"][0]["expected"] = "definitely-not-in-source"
    with pytest.raises(KnowledgeError, match="failed against"):
        _validate_decision_authority_source(model, broken)


def test_evidence_storage_contract_separates_durability_layers() -> None:
    model = load_model(PROJECT_ROOT)
    all_evidence = [
        item
        for record in (*model.claims, *model.decisions)
        for item in record["evidence"]
    ]
    assert {item["storage"] for item in all_evidence} == {
        "external_root",
        "git_tracked",
        "workspace_untracked",
    }
    for item in all_evidence:
        if item["storage"] == "git_tracked":
            assert item["path"] in model.tracked_paths
            assert item.get("optional", False) is False
        elif item["storage"] == "workspace_untracked":
            assert item["path"] not in model.tracked_paths
            assert item["optional"] is True
        else:
            assert item["storage"] == "external_root"
            assert item["path"] not in model.tracked_paths
            assert item["optional"] is True
            assert item["note"].strip()

    with pytest.raises(KnowledgeError, match="workspace_untracked evidence must be optional"):
        _validate_evidence(
            PROJECT_ROOT,
            [{"path": ".artifacts/local-only", "role": "test", "storage": "workspace_untracked"}],
            "TEST",
            model.tracked_paths,
        )


def test_phase4_batch4_claim_successors_preserve_semantic_direction() -> None:
    claims = load_model(PROJECT_ROOT).claim_by_id

    assert claims["CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT"][
        "supersedes"
    ] == ["CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT"]
    assert claims["CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT"]["status"] == "superseded"
    assert "16 个 credible terminal arms" in claims[
        "CLAIM-AB16-CAMPAIGN-CLOSEOUT-NO-ATTRIBUTABLE-CUT-RESULT"
    ]["statement"]
    assert claims["CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT-BOUNDARY"][
        "supersedes"
    ] == ["CLAIM-ROUTING-REVERIFICATION-EXTRA-STRICT"]
    assert claims["CLAIM-DURABLE-CERTIFIED-RESULT-ABSENT"]["authority"] == "machine"
    assert "min_side >= 6" in claims[
        "CLAIM-EMPTY-RECTANGLE-MIN-SIDE-ADMISSIBILITY-SIX"
    ]["statement"]
    assert claims["CLAIM-CONNECTIVITY-QUANTIFIER-PER-COMMODITY-SOURCE-SINK"][
        "kind"
    ] == "definition"


def test_all_current_evidence_dossiers_have_an_explicit_current_review_scope() -> None:
    model = load_model(PROJECT_ROOT)
    current_evidence = {
        str(record["id"])
        for record in model.dossiers["records"]
        if record["relevance"] == "current_evidence"
    }
    current_reviews = {
        str(record["dossier_id"]): record
        for record in model.backfill_reviews
        if record["status"] == "current"
    }

    assert len(current_evidence) == _census(model)["current_evidence_dossiers"]
    assert current_evidence <= set(current_reviews)
    scoped = [current_reviews[dossier_id] for dossier_id in current_evidence]
    semantic_scoped = sum(
        review["review_scope"] != "availability_and_provenance" for review in scoped
    )
    availability_scoped = sum(
        review["review_scope"] == "availability_and_provenance" for review in scoped
    )
    assert semantic_scoped + availability_scoped == _census(model)["current_evidence_dossiers"]
    assert semantic_scoped <= _census(model)["semantic_review_dossiers"]
    assert availability_scoped <= _census(model)["availability_review_dossiers"]


def test_reasoning_profiles_keep_condition_states_queryable() -> None:
    model = load_model(PROJECT_ROOT)
    claims = model.claim_by_id

    assert claims["CLAIM-SMM-209-EXCLUDES-22X54"]["reasoning_profile"]["condition_disposition"] == "discharged"
    assert (
        claims["CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL"]["reasoning_profile"]["condition_disposition"] == "conditional"
    )
    assert claims["CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED"]["reasoning_profile"]["condition_disposition"] == "refuted"
    assert claims["CLAIM-ZERO-SLACK-AUDIT-METHOD"]["reasoning_profile"]["condition_disposition"] == "method_only"


def test_third_backfill_batch_preserves_the_mathematical_proof_graph() -> None:
    model = load_model(PROJECT_ROOT)
    claims = model.claim_by_id
    reviews = {str(review["id"]): review for review in model.backfill_reviews}

    assert len(model.claims) == _census(model)["claims_total"]
    assert len(model.backfill_reviews) == _census(model)["backfill_reviews_total"]
    assert sum(review["status"] == "current" for review in model.backfill_reviews) == _census(model)["current_reviews"]

    assert claims["CLAIM-SMM4-LEX-BAND-COMPOSITION-2086"]["dependencies"] == [
        "CLAIM-R4-LEX-BAND-2084-UNSAT",
        "CLAIM-SMM-209-EXCLUDES-22X54",
    ]
    assert claims["CLAIM-SMM-209-EXCLUDES-22X54"]["dependencies"] == [
        "CLAIM-BODY-ACCESS-BUDGET-1320",
        "CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133",
    ]
    assert claims["CLAIM-P2-AREA-BOUND-1167"]["dependencies"] == [
        "CLAIM-P2-AREA-ACCOUNTING-1356",
        "CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153",
        "CLAIM-POWER-HALO-POLE-LOWER-BOUND-NINE",
    ]
    throughput_dependencies = [
        "CLAIM-P2-AREA-BOUND-1167",
        "CLAIM-P2-MIN-SIDE-UPPER-OPEN",
        "CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015",
    ]
    assert claims["CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER"]["dependencies"] == throughput_dependencies
    assert claims["CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER"]["status"] == "superseded"
    assert claims["CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814"]["dependencies"] == throughput_dependencies
    assert claims["CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER-20260814"]["supersedes"] == [
        "CLAIM-P2-THROUGHPUT-RESEARCH-LEDGER"
    ]
    assert claims["CLAIM-SIX-PREDICATE-RESEARCH-LEDGER"]["dependencies"] == [
        "CLAIM-CERTIFIED-THEOREM-SCOPE",
        "CLAIM-SMM4-LEX-BAND-COMPOSITION-2086",
    ]

    assert claims["CLAIM-P2-AREA-ACCOUNTING-1356"]["dependencies"] == ["CLAIM-EMPTY-RECTANGLE-STRICT"]
    assert claims["CLAIM-P2-ROUTE-FOOTPRINT-LOWER-153"]["dependencies"] == ["CLAIM-P2-ROUTE-STATE-LOWER-BOUND-305"]
    assert claims["CLAIM-SMM-OUTSIDE-ACCESS-LOWER-133"]["dependencies"] == [
        "CLAIM-R4-LOCAL-WEIGHTED-ACCESS-CAPACITY-4",
        "CLAIM-R4-MARKED-INCIDENCE-TOTAL-110",
        "CLAIM-SMM-COMBINED-CAP-209",
    ]

    assert claims["CLAIM-R3-LEX-BAND-2074-UNSAT-GIVEN-GEOMETRY"]["status"] == "historical"
    assert claims["CLAIM-R4-LEX-BAND-2084-UNSAT"]["status"] == "current"
    assert claims["CLAIM-P2-MIN-SIDE-UPPER-OPEN"]["status"] == "open"
    assert (
        claims["CLAIM-P2-SINGLE-LAYER-AREA-BOUND-1015"]["reasoning_profile"]["condition_disposition"] == "conditional"
    )
    assert claims["CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE"]["reasoning_profile"]["generality"] == "frozen_instance"

    assert reviews["REVIEW-20260811-P2-AREA-BOUND"]["status"] == "superseded"
    assert reviews["REVIEW-20260811-P2-AREA-BOUND-BATCH2"]["supersedes"] == ["REVIEW-20260811-P2-AREA-BOUND"]
    assert reviews["REVIEW-20260811-SMM-FRESH-AUTHORITY"]["status"] == "superseded"
    assert reviews["REVIEW-20260811-SMM-STRICT"]["status"] == "superseded"


def test_derivation_profiles_keep_proof_roles_families_and_verification_queryable() -> None:
    model = load_model(PROJECT_ROOT)
    claims = model.claim_by_id
    derived = [claim for claim in model.claims if claim.get("derivation_profile")]

    assert len(derived) == _census(model)["derivation_profiles"]
    assert claims["CLAIM-P2-AREA-ACCOUNTING-1356"]["derivation_profile"] == {
        "role": "atomic_lemma",
        "families": ["area_accounting", "empty_rectangle_geometry"],
        "verification_modes": [
            "paper_derivation",
            "source_recomputation",
            "adversarial_review",
        ],
    }
    assert claims["CLAIM-BODY-ACCESS-BUDGET-1320"]["derivation_profile"]["role"] == "atomic_lemma"
    assert claims["CLAIM-P2-AREA-BOUND-1167"]["derivation_profile"]["role"] == "composite_theorem"
    assert claims["CLAIM-P2-MIN-SIDE-UPPER-OPEN"]["derivation_profile"]["role"] == "open_obligation"
    assert claims["CLAIM-SMM4-LEX-BAND-COMPOSITION-2086"]["derivation_profile"]["role"] == "composite_theorem"
    assert "finite_pb_proof" in claims["CLAIM-SMM4-LEX-BAND-COMPOSITION-2086"]["derivation_profile"]["families"]
    assert (
        "roundingsat_veripb"
        in claims["CLAIM-SMM4-LEX-BAND-COMPOSITION-2086"]["derivation_profile"]["verification_modes"]
    )
    assert claims["CLAIM-SIX-PREDICATE-RESEARCH-LEDGER"]["derivation_profile"]["role"] == "ledger_projection"
    assert claims["CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED"]["derivation_profile"]["role"] == "counterexample"

    reasoning = (PROJECT_ROOT / "docs/REASONING_LEDGER.md").read_text(encoding="utf-8")
    assert "## 数学推导关系" in reasoning
    assert "`derivation_profile`" in reasoning
    assert "`separation_profile`" in reasoning
    assert "## 选择、分离与消费机制" in reasoning
    assert "CLAIM-P2-AREA-ACCOUNTING-1356" in reasoning


def test_local_optional_review_can_name_a_missing_file_inside_its_dossier() -> None:
    model = load_model(PROJECT_ROOT)
    review = next(
        review for review in model.backfill_reviews if review["id"] == "REVIEW-20260811-BAND22-STRICT-HOLE-PROBE-BATCH2"
    )
    dossier = model.dossier_by_id[str(review["dossier_id"])]

    assert dossier["tracked_state"] == "local_optional"
    assert review["reviewed_paths"] == [".artifacts/band22_strict_hole_probe_20260805/PROBE_REPORT.md"]
    assert review["reviewed_paths"][0].startswith(f"{dossier['path']}/")


def test_third_backfill_batch_keeps_selection_validation_and_consumption_distinct() -> None:
    model = load_model(PROJECT_ROOT)
    claims = model.claim_by_id
    reviews = {str(review["id"]): review for review in model.backfill_reviews}
    separated = [claim for claim in model.claims if claim.get("separation_profile")]

    assert len(separated) == _census(model)["separation_profiles"]
    assert claims["CLAIM-PAIRWISE-CLOSURE-INCOMPLETE"]["separation_profile"]["completeness"] == "disproved"
    assert claims["CLAIM-PAIRWISE-CLOSURE-INCOMPLETE"]["separation_profile"]["validation_modes"] == [
        "counterexample"
    ]
    assert claims["CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN"]["separation_profile"][
        "completeness"
    ] == "open"
    assert claims["CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM"][
        "separation_profile"
    ]["candidate_source"] == "supplied_candidate"
    assert claims["CLAIM-ATTACH-SPIKES-ENGINEERING-NOT-CUT-EFFICACY"]["separation_profile"][
        "baseline_comparison"
    ] == "controlled"
    assert claims["CLAIM-RAW-ELIGIBLE-EVENTS-REQUIRED-FOR-SEPARATION-EVALUATION"][
        "separation_profile"
    ]["selection_modes"] == ["raw_event_separation"]
    assert claims["CLAIM-BUDGET-EXHAUSTION-IS-UNKNOWN-NOT-FIXED-POINT"]["separation_profile"][
        "completeness"
    ] == "open"
    assert claims["CLAIM-SOLVER-RETHINK-G03-LACKS-SEPARATION-ORACLE"]["status"] == "historical"

    assert reviews["REVIEW-20260811-RULE-SYSTEM-REDESIGN"]["status"] == "superseded"
    assert reviews["REVIEW-20260811-RULE-SYSTEM-REDESIGN-BATCH3"]["supersedes"] == [
        "REVIEW-20260811-RULE-SYSTEM-REDESIGN"
    ]
    assert reviews["REVIEW-20260811-BATCH-CE-ATTACH-HOST"]["status"] == "superseded"
    assert reviews["REVIEW-20260811-BATCH-CE-ATTACH-HOST-BATCH3"]["supersedes"] == [
        "REVIEW-20260811-BATCH-CE-ATTACH-HOST"
    ]


def test_generic_propagation_impossibility_remains_an_explicit_open_obligation() -> None:
    model = load_model(PROJECT_ROOT)
    claim = model.claim_by_id["CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN"]

    assert claim["kind"] == "open_problem"
    assert claim["status"] == "open"
    assert claim["reasoning_profile"]["generic_propagation_evidence"] == "none"
    assert "当前 formal generic-propagation evidence 计数保持为零" in claim["consequences"]
    assert "CP-SAT 一定能够得到相同结论" in claim["does_not_imply"]


def test_fourth_backfill_batch_tracks_validity_events_and_explicit_successors() -> None:
    model = load_model(PROJECT_ROOT)
    claims = model.claim_by_id
    reviews = {str(review["id"]): review for review in model.backfill_reviews}
    profiled = [claim for claim in model.claims if claim.get("validity_profile")]
    edges = [
        (str(claim["id"]), str(target))
        for claim in model.claims
        for target in claim["supersedes"]
    ]

    assert len(profiled) == _census(model)["validity_profiles"]
    assert len(edges) == _census(model)["supersession_edges"]
    assert sum(claim["status"] == "refuted" for claim in model.claims) == _census(model)["refuted_claims"]
    assert sum(claim["status"] == "superseded" for claim in model.claims) == _census(model)["superseded_claims"]

    assert claims["CLAIM-FRONT-OFFSET-PRE-0718-SUPERSEDED"]["supersedes"] == [
        "CLAIM-FRONT-OFFSET-DOUBLE-STEP-SEMANTICS-SUPERSEDED"
    ]
    assert claims["CLAIM-EMPTY-RECTANGLE-STRICT"]["supersedes"] == [
        "CLAIM-EMPTY-RECTANGLE-ROUTING-ALLOWED-SUPERSEDED"
    ]
    assert claims["CLAIM-P2-FIVE-FULL-ONE-HALF-CONDITIONAL"]["supersedes"] == [
        "CLAIM-P2-STEEL-BLOCK-17-LT-18-REFUTED"
    ]
    assert claims["CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED"]["validity_profile"][
        "event_type"
    ] == "refutation"
    assert claims["CLAIM-MIXFLOW-U01-GUARD-FORK-BENEFIT-REFUTED"]["validity_profile"][
        "event_type"
    ] == "experiment_invalidation"
    assert claims["CLAIM-MIXFLOW-DEMIX-CONCLUSION-SURVIVES-FIXTURE-CORRECTION"]["supersedes"] == []
    assert claims["CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN"]["validity_profile"][
        "reuse_policy"
    ] == "revalidate_before_use"
    assert claims["CLAIM-R1-1326-34-STRICT-UPPER-REVALIDATED"]["validity_profile"][
        "repair_state"
    ] == "revalidated"
    lazy_validity = claims["CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO"]["validity_profile"]
    assert lazy_validity["event_type"] == "route_retirement"
    assert lazy_validity["affected_layers"] == [
        "model_encoding",
        "experiment_design",
        "research_strategy",
    ]
    assert lazy_validity["reuse_policy"] == "method_only"
    assert lazy_validity["repair_state"] == "pending"
    assert claims["CLAIM-IHS-SINGLETON-CORE-COMPRESSION-PHASE0-NO-GO"]["status"] == "historical"
    assert claims["CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO"]["validity_profile"][
        "event_type"
    ] == "route_retirement"
    assert claims["CLAIM-SMT-MT-SYNTHETIC-GO-NOT-TRANSFERABLE-TO-REAL-INNER"]["validity_profile"][
        "reuse_policy"
    ] == "unaffected_under_premises"
    round45_statement = claims["CLAIM-ROUND45-CORRECTED-PROFILE-UNKNOWN-NOT-STRUCTURAL-WALL"][
        "statement"
    ]
    assert "10,816 variables、16,513 constraints" in round45_statement
    assert "不能恢复旧模型上的结构墙、不可行性或 solver 范式穷尽判断" in round45_statement
    assert claims["CLAIM-WITNESS-RESTRICTED-POLE-DOMAINS-INFEASIBLE-FULL-DOMAIN-OPEN"][
        "reasoning_profile"
    ]["condition_disposition"] == "conditional"

    assert reviews["REVIEW-20260811-FRONT-OFFSET-INCIDENT"]["status"] == "superseded"
    assert reviews["REVIEW-20260811-FRONT-OFFSET-INCIDENT-BATCH4"]["supersedes"] == [
        "REVIEW-20260811-FRONT-OFFSET-INCIDENT"
    ]
    assert reviews["REVIEW-20260811-RULES-AUDIT-BATCH4"]["status"] == "current"
    assert reviews["REVIEW-20260811-P2-SPECIALIZED-BATCH4"]["status"] == "current"
    assert reviews["REVIEW-20260811-RAB-SEP-PROMOTION-BATCH3"]["status"] == "superseded"
    assert reviews["REVIEW-20260811-RAB-SEP-PROMOTION-BATCH4"]["supersedes"] == [
        "REVIEW-20260811-RAB-SEP-PROMOTION-BATCH3"
    ]
    assert reviews["REVIEW-20260811-LAZY-POWER-PHASE0-BATCH4"]["status"] == "current"
    assert reviews["REVIEW-20260811-IHS-PHASE0-BATCH4"]["status"] == "current"
    assert reviews["REVIEW-20260811-COLUMN-GENERATION-PHASE2-BATCH4"]["status"] == "current"
    assert reviews["REVIEW-20260811-WITNESS-CONSTRUCTOR"]["status"] == "superseded"
    assert reviews["REVIEW-20260811-WITNESS-CONSTRUCTOR-BATCH4"]["supersedes"] == [
        "REVIEW-20260811-WITNESS-CONSTRUCTOR"
    ]


def test_validity_ledger_projects_event_reuse_repair_and_supersession_boundaries() -> None:
    validity = (PROJECT_ROOT / "docs/VALIDITY_LEDGER.md").read_text(encoding="utf-8")

    assert "## 有效性事件分布" in validity
    assert "## 显式换代图" in validity
    assert "## 当前相关语义审阅" in validity
    assert f"current validity review：`{_census(load_model(PROJECT_ROOT))['current_validity_review_dossiers']}` 个 dossier" in validity
    assert "`experiment_invalidation`" in validity
    assert "`current_after_repair`" in validity
    assert "CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED" in validity
    assert "CLAIM-W0-POWER-OBSTRUCTION-REQUIRES-DECLARED-HEIGHT-PURITY" in validity
    assert "CLAIM-RAB-FCL-FRONT-DEPENDENT-PERFORMANCE-WITHDRAWN" in validity
    assert "CLAIM-LAZY-POWER-INSTANCE-POSE-CUT-ROUTE-NO-GO" in validity
    assert "CLAIM-COLUMN-GENERATION-PHASE2-SCALE-ROUTE-NO-GO" in validity
    assert "`route_retirement`" in validity
    assert "`scope_correction`" in validity


def test_phase2_closure_separates_semantic_review_from_inventory_triage() -> None:
    model = load_model(PROJECT_ROOT)
    all_dossiers = {str(record["id"]) for record in model.dossiers["records"]}
    current_reviews = [
        record for record in model.backfill_reviews if record["status"] == "current"
    ]
    reviewed_ids = {str(record["dossier_id"]) for record in current_reviews}
    semantic_ids = {
        str(record["dossier_id"])
        for record in current_reviews
        if record["review_scope"] != "availability_and_provenance"
    }
    availability_ids = reviewed_ids - semantic_ids
    triaged_sequence = [
        str(dossier_id)
        for group in model.backfill_triage["groups"]
        for dossier_id in group["dossier_ids"]
    ]
    triaged_ids = set(triaged_sequence)

    assert len(all_dossiers) == _census(model)["dossiers_total"]
    assert len(reviewed_ids) == _census(model)["current_reviews"]
    assert len(semantic_ids) == _census(model)["semantic_review_dossiers"]
    assert len(availability_ids) == _census(model)["availability_review_dossiers"]
    assert len(triaged_sequence) == len(triaged_ids) == _census(model)["triaged_dossiers"]
    assert reviewed_ids.isdisjoint(triaged_ids)
    assert reviewed_ids | triaged_ids == all_dossiers
    assert model.backfill_triage["triage_is_not_semantic_review"] is True


def test_phase2_topic_and_terminology_registries_are_exhaustive() -> None:
    model = load_model(PROJECT_ROOT)
    claim_ids = {str(record["id"]) for record in model.claims}
    dossier_labels = {
        str(label)
        for dossier in model.dossiers["records"]
        for label in dossier.get("topics", [])
    }
    term_ids = {str(record["id"]) for record in model.terminology["records"]}
    indexed_claims = {
        str(claim_id)
        for topic in model.topics["records"]
        for claim_id in topic["claim_ids"]
    }
    indexed_labels = {
        str(label)
        for topic in model.topics["records"]
        for label in topic["dossier_topic_labels"]
    }
    indexed_terms = {
        str(term_id)
        for topic in model.topics["records"]
        for term_id in topic["term_ids"]
    }

    assert len(model.topics["records"]) == _census(model)["topics_total"]
    assert len(model.terminology["records"]) == _census(model)["terms_total"]
    assert claim_ids <= indexed_claims
    assert dossier_labels <= indexed_labels
    assert term_ids <= indexed_terms


def test_phase2_closure_generated_pages_preserve_the_coverage_boundary() -> None:
    model = load_model(PROJECT_ROOT)
    census = _census(model)
    backfill = (PROJECT_ROOT / "docs/BACKFILL_LEDGER.md").read_text(encoding="utf-8")
    topics = (PROJECT_ROOT / "docs/TOPIC_INDEX.md").read_text(encoding="utf-8")
    terms = (PROJECT_ROOT / "docs/TERMINOLOGY.md").read_text(encoding="utf-8")

    assert "semantic review" in backfill
    assert "availability/provenance" in backfill
    assert "inventory triage" in backfill
    assert f"`{census['dossiers_total']}`" in backfill
    assert f"`{census['semantic_review_dossiers']}`" in backfill
    assert f"`{census['triaged_dossiers']}`" in backfill
    assert "TOPIC-SIX-PREDICATE-UPPER-BOUND" in topics
    assert "TERM-BACKFILL-TRIAGE" in terms
    assert "不表示内容已经语义审阅" in terms
