from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Callable

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/r4_response_review_20260723"
AUTHORITY = ROOT / ".artifacts/track_b_r4_external_brain_handoff_20260722" / "run-20260722T084343Z-R4hP1A"
RESPONSE_RUN = (
    ROOT / ".artifacts/track_b_r4_external_brain_handoff_20260722" / "responses/run-20260723T023657Z-R4resp-357f260d"
)
A004_LEDGER = RESPONSE_RUN / "claims/a004/quantitative-claim-ledger.json"
A004_REPORTS = [
    RESPONSE_RUN / "recomputations/upper-counts-a004/report.json",
    RESPONSE_RUN / "recomputations/marked-geometry-a004/report.json",
    RESPONSE_RUN / "recomputations/w2d-audit-a004/report.json",
]
A004_VERDICT = RESPONSE_RUN / "adversarial/a004/verdict.json"
A004_ADMISSION = RESPONSE_RUN / "admission/a004/admission.json"
CANONICAL_INPUTS = {
    "response_text": ROOT / "docs/research/cleanroom_rederivation_20260718/12_r4_response_gpt_pro_verbatim.md",
    "certificate_markdown": ROOT
    / "docs/research/cleanroom_rederivation_20260718/13_r4_next_certificate_gpt_pro_verbatim.md",
    "certificate_python": ROOT
    / "docs/research/cleanroom_rederivation_20260718/14_r4_next_certificate_python_gpt_pro_verbatim.md",
}


def _load(name: str, filename: str) -> ModuleType:
    path = RESEARCH / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ledger_builder() -> ModuleType:
    return _load("r4_claim_ledger_authority_chain_test", "build_r4_claim_ledger_v2.py")


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load("r4_runner_authority_chain_test", "run_r4_local_recomputation_bundle_v2.py")


@pytest.fixture(scope="module")
def verdict_builder() -> ModuleType:
    return _load("r4_verdict_authority_chain_test", "build_r4_adversarial_verdict_v2.py")


@pytest.fixture(scope="module")
def admission() -> ModuleType:
    return _load("r4_admission_authority_chain_test", "close_r4_response_candidate_admission_v2.py")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": _sha(raw),
        "size_bytes": len(raw),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())


def _response_tree(tmp_path: Path) -> tuple[Path, Path]:
    authority = tmp_path / "handoff/run-authority"
    authority.mkdir(parents=True)
    response = tmp_path / "handoff/responses/run-response"
    response.mkdir(parents=True)
    for category in ("claims", "recomputations", "adversarial", "admission"):
        (response / category).mkdir()
    return authority, response


@pytest.fixture
def canonical_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ledger_builder: ModuleType,
) -> dict[str, Any]:
    authority, response = _response_tree(tmp_path)
    raw_dir = response / "raw"
    raw_dir.mkdir()
    inputs: list[dict[str, Any]] = []
    for input_id, source in CANONICAL_INPUTS.items():
        if not source.is_file():
            pytest.skip(f"canonical inert input is unavailable: {source}")
        raw_path = raw_dir / f"{input_id}.bin"
        raw_path.write_bytes(source.read_bytes())
        record = _record(raw_path)
        inputs.append(
            {
                "input_id": input_id,
                "raw_document": record,
                "canonical_document": record,
                "expected_identity": {
                    "sha256": record["sha256"],
                    "size_bytes": record["size_bytes"],
                },
                "raw_canonical_byte_equal": True,
                "source_identity_at_archive": record,
            }
        )
    ingest_path = response / "response-ingest.json"
    _write_json(ingest_path, {"fixture": "authority-chain"})
    provenance = {
        "authority": {"run_dir": str(authority.resolve()), "fixture": True},
        "created_at_utc": "2026-07-23T00:00:00Z",
        "input_count": 3,
        "inputs": inputs,
        "response_ingest": _record(ingest_path),
    }

    class FakeArchiver:
        @staticmethod
        def check_bundle(response_run: Path, authority_run: Path) -> dict[str, Any]:
            assert response_run == response
            assert authority_run == authority
            return copy.deepcopy(provenance)

    monkeypatch.setattr(ledger_builder, "_load_archiver", lambda: FakeArchiver)
    output = response / "claims/a004"
    ledger = ledger_builder.build_ledger(authority, response, output)
    ledger_path = output / "quantitative-claim-ledger.json"
    replayed, claims = ledger_builder.replay_claim_ledger(authority, response, ledger_path)
    assert replayed == ledger
    assert len(claims) == 17
    return {
        "authority": authority,
        "claims": claims,
        "ledger": ledger,
        "ledger_path": ledger_path,
        "provenance": provenance,
        "response": response,
    }


@pytest.mark.parametrize(
    "mutator",
    [
        pytest.param(
            lambda value: value["claims"].__setitem__(
                slice(0, 2),
                list(reversed(value["claims"][:2])),
            ),
            id="claims-reordered",
        ),
        pytest.param(
            lambda value: value["claim_ledger_builder_tool"].__setitem__("path", "/forged/builder.py"),
            id="builder-path-changed",
        ),
        pytest.param(
            lambda value: value["claim_ledger_builder_tool"].__setitem__("size_bytes", 1),
            id="builder-size-changed",
        ),
        pytest.param(
            lambda value: value["claim_ledger_builder_tool"].__setitem__("sha256", "0" * 64),
            id="builder-sha-changed",
        ),
    ],
)
def test_claim_ledger_replay_rejects_complete_semantic_mutations(
    canonical_ledger: dict[str, Any],
    ledger_builder: ModuleType,
    mutator: Callable[[dict[str, Any]], Any],
) -> None:
    ledger_path = canonical_ledger["ledger_path"]
    tampered = copy.deepcopy(canonical_ledger["ledger"])
    mutator(tampered)
    _write_json(ledger_path, tampered)
    with pytest.raises(ledger_builder.LedgerError):
        ledger_builder.replay_claim_ledger(
            canonical_ledger["authority"],
            canonical_ledger["response"],
            ledger_path,
        )


@pytest.mark.parametrize("claim_index", range(17))
@pytest.mark.parametrize("mutation", ["delete", "expected-result"])
def test_each_fixed_claim_is_canonically_required(
    canonical_ledger: dict[str, Any],
    ledger_builder: ModuleType,
    claim_index: int,
    mutation: str,
) -> None:
    ledger_path = canonical_ledger["ledger_path"]
    tampered = copy.deepcopy(canonical_ledger["ledger"])
    if mutation == "delete":
        tampered["claims"].pop(claim_index)
    else:
        tampered["claims"][claim_index]["expected_result"] = {"forged": claim_index}
    _write_json(ledger_path, tampered)
    with pytest.raises(ledger_builder.LedgerError):
        ledger_builder.replay_claim_ledger(
            canonical_ledger["authority"],
            canonical_ledger["response"],
            ledger_path,
        )


def test_runner_claim_ledger_validation_delegates_to_builder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: ModuleType,
) -> None:
    authority, response = _response_tree(tmp_path)
    ledger_path = response / "claims/a004/quantitative-claim-ledger.json"
    ledger_path.parent.mkdir()
    ledger_path.write_bytes(b"{}\n")
    provenance = {
        "authority": {"run_dir": str(authority.resolve())},
        "input_count": 3,
        "inputs": [{"input_id": str(index)} for index in range(3)],
        "response_ingest": {"path": str(response / "response-ingest.json")},
    }
    claims = {f"claim-{index:02d}": {"claim_id": f"claim-{index:02d}"} for index in range(17)}
    ledger = {
        "authority": provenance["authority"],
        "claim_count": 17,
        "claims": list(claims.values()),
        "input_bindings": provenance["inputs"],
        "response_ingest": provenance["response_ingest"],
    }
    calls: list[tuple[Path, Path, Path]] = []

    def replay(authority_run: Path, response_run: Path, path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        calls.append((authority_run, response_run, path))
        return ledger, claims

    monkeypatch.setattr(runner, "EXPECTED_AUTHORITY_RUN", authority)
    monkeypatch.setattr(runner, "EXPECTED_RESPONSE_RUN", response)
    monkeypatch.setattr(
        runner,
        "_load_ledger_builder",
        lambda: SimpleNamespace(replay_claim_ledger=replay),
    )
    assert runner.validate_claim_ledger(ledger_path, provenance) == (ledger, claims)
    assert calls == [(authority, response, ledger_path)]


def test_joint_ledger_and_downstream_refresh_fails_at_canonical_ledger(
    canonical_ledger: dict[str, Any],
    ledger_builder: ModuleType,
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger_path = canonical_ledger["ledger_path"]
    tampered = copy.deepcopy(canonical_ledger["ledger"])
    tampered["claims"][0]["expected_result"] = {"forged": True}
    _write_json(ledger_path, tampered)
    refreshed_ledger_record = _record(ledger_path)
    for relative in (
        "recomputations/forged/report.json",
        "adversarial/forged/verdict.json",
        "admission/forged/admission.json",
    ):
        path = canonical_ledger["response"] / relative
        path.parent.mkdir()
        _write_json(
            path,
            {
                "claim_ledger": refreshed_ledger_record,
                "expected_result": {"forged": True},
                "formal_run_authorized": True,
            },
        )
    monkeypatch.setattr(runner, "EXPECTED_AUTHORITY_RUN", canonical_ledger["authority"])
    monkeypatch.setattr(runner, "EXPECTED_RESPONSE_RUN", canonical_ledger["response"])
    monkeypatch.setattr(runner, "_load_ledger_builder", lambda: ledger_builder)
    with pytest.raises(runner.RecomputationError, match="canonical claim ledger replay failed"):
        runner.validate_claim_ledger(
            ledger_path,
            canonical_ledger["provenance"],
        )


@pytest.fixture
def canonical_verdict(
    canonical_ledger: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    verdict_builder: ModuleType,
) -> dict[str, Any]:
    response = canonical_ledger["response"]
    claims = canonical_ledger["claims"]
    checker_ids = ("upper_counts", "marked_geometry", "w2d_audit")
    report_paths: list[Path] = []
    reports_by_path: dict[Path, dict[str, Any]] = {}
    for checker_id in checker_ids:
        report_dir = response / "recomputations" / f"{checker_id.replace('_', '-')}-a004"
        report_dir.mkdir()
        report_path = report_dir / "report.json"
        report_path.write_bytes(b"{}\n")
        selected = [{"claim_id": claim_id} for claim_id, claim in claims.items() if claim["checker_id"] == checker_id]
        reports_by_path[report_path] = {
            "checker_id": checker_id,
            "claim_results": selected,
            "created_at_utc": "2026-07-23T00:00:00Z",
            "status": "PASS_EXACT_MATCH",
        }
        report_paths.append(report_path)

    fake_runner = SimpleNamespace(
        REGISTERED_CHECKERS={checker_id: {} for checker_id in checker_ids},
        validate_archive=lambda response_run, authority_run: copy.deepcopy(canonical_ledger["provenance"]),
        validate_claim_ledger=lambda ledger_path, provenance: (
            copy.deepcopy(canonical_ledger["ledger"]),
            copy.deepcopy(claims),
        ),
        validate_recomputation_report=lambda path, ledger_path, provenance, replay_claims: copy.deepcopy(
            reports_by_path[path]
        ),
    )
    monkeypatch.setattr(verdict_builder, "_load_runner", lambda: fake_runner)
    output = response / "adversarial/a004"
    verdict = verdict_builder.build_verdict(
        canonical_ledger["authority"],
        response,
        canonical_ledger["ledger_path"],
        report_paths,
        output,
    )
    verdict_path = output / "verdict.json"
    replay = verdict_builder.replay_verdict(
        canonical_ledger["authority"],
        response,
        canonical_ledger["ledger_path"],
        report_paths,
        verdict_path,
    )
    assert replay["verdict"] == verdict
    assert set(replay) == {
        "claims",
        "ledger",
        "provenance",
        "report_bindings",
        "reports",
        "verdict",
        "verdict_record",
    }
    return {
        **canonical_ledger,
        "report_paths": report_paths,
        "replay": replay,
        "verdict": verdict,
        "verdict_path": verdict_path,
    }


@pytest.mark.parametrize(
    "mutator",
    [
        pytest.param(
            lambda value: value["candidates"]["upper_bound_1188_22"].__setitem__("status", "FAIL"),
            id="upper-candidate-decision",
        ),
        pytest.param(
            lambda value: value["candidates"]["upper_bound_1188_22"].__setitem__(
                "research_disposition",
                "PRODUCTION_CERTIFIED",
            ),
            id="upper-candidate-disposition",
        ),
        pytest.param(
            lambda value: value["candidates"]["upper_bound_1188_22"].__setitem__(
                "proposed_upper_ledger",
                [1188, 21],
            ),
            id="upper-candidate-proposed-ledger",
        ),
        pytest.param(
            lambda value: value["candidates"]["witness_x67_c5_min_repair"].__setitem__(
                "classification",
                "EXECUTABLE_CANDIDATE",
            ),
            id="witness-candidate-decision",
        ),
        pytest.param(
            lambda value: value["candidates"]["witness_x67_c5_min_repair"].__setitem__(
                "guarded_cut_soundness_complete",
                True,
            ),
            id="witness-candidate-soundness",
        ),
        pytest.param(
            lambda value: value["candidates"]["witness_x67_c5_min_repair"].__setitem__(
                "prerequisites",
                [],
            ),
            id="witness-candidate-prerequisites",
        ),
        pytest.param(
            lambda value: (
                value.__setitem__("current_project_ledger", {"U": [1188, 22], "L": "present"}),
                value.__setitem__("upper_bound_changed", True),
            ),
            id="global-ledger-fields",
        ),
        pytest.param(
            lambda value: (
                value.__setitem__("formal_run_authorized", True),
                value.__setitem__("solver_run_authorized", True),
                value.__setitem__("track_w_execution_authorized", True),
            ),
            id="joint-authorizations",
        ),
        pytest.param(
            lambda value: (
                value["candidates"]["upper_bound_1188_22"].__setitem__(
                    "research_disposition",
                    "PRODUCTION_CERTIFIED",
                ),
                value.__setitem__("production_certified", True),
                value.__setitem__("optimality_established", True),
                value.__setitem__("global_infeasibility_established", True),
            ),
            id="joint-candidate-and-global-safety",
        ),
    ],
)
def test_verdict_replay_rejects_candidate_global_and_authorization_tampering(
    canonical_verdict: dict[str, Any],
    verdict_builder: ModuleType,
    mutator: Callable[[dict[str, Any]], Any],
) -> None:
    tampered = copy.deepcopy(canonical_verdict["verdict"])
    mutator(tampered)
    _write_json(canonical_verdict["verdict_path"], tampered)
    with pytest.raises(verdict_builder.VerdictError):
        verdict_builder.replay_verdict(
            canonical_verdict["authority"],
            canonical_verdict["response"],
            canonical_verdict["ledger_path"],
            canonical_verdict["report_paths"],
            canonical_verdict["verdict_path"],
        )


@pytest.mark.parametrize(
    "field",
    [
        "upper_bound_changed",
        "external_response_code_executed",
        "formal_run_authorized",
        "solver_run_authorized",
        "search_run_authorized",
        "track_w_execution_authorized",
        "witness_established",
        "attainability_established",
        "optimality_established",
        "global_infeasibility_established",
        "production_certified",
    ],
)
def test_verdict_replay_rejects_each_global_safety_or_authorization_flip(
    canonical_verdict: dict[str, Any],
    verdict_builder: ModuleType,
    field: str,
) -> None:
    tampered = copy.deepcopy(canonical_verdict["verdict"])
    assert tampered[field] is False
    tampered[field] = True
    _write_json(canonical_verdict["verdict_path"], tampered)
    with pytest.raises(verdict_builder.VerdictError):
        verdict_builder.replay_verdict(
            canonical_verdict["authority"],
            canonical_verdict["response"],
            canonical_verdict["ledger_path"],
            canonical_verdict["report_paths"],
            canonical_verdict["verdict_path"],
        )


def _spy_verdict_builder(
    verdict_builder: ModuleType,
    calls: list[tuple[Any, ...]],
) -> SimpleNamespace:
    def replay(*args: Any) -> dict[str, Any]:
        calls.append(args)
        return verdict_builder.replay_verdict(*args)

    return SimpleNamespace(replay_verdict=replay)


def test_admission_close_and_replay_both_invoke_full_verdict_replay(
    canonical_verdict: dict[str, Any],
    verdict_builder: ModuleType,
    admission: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        admission,
        "_load_verdict_builder",
        lambda: _spy_verdict_builder(verdict_builder, calls),
    )
    output = canonical_verdict["response"] / "admission/a004"
    payload = admission.close_admission(
        canonical_verdict["authority"],
        canonical_verdict["response"],
        canonical_verdict["ledger_path"],
        canonical_verdict["report_paths"],
        canonical_verdict["verdict_path"],
        output,
    )
    admission_path = output / "admission.json"
    assert payload["status"] == "PARTIAL"
    assert len(calls) == 2

    replay = admission.replay_admission(
        canonical_verdict["authority"],
        canonical_verdict["response"],
        canonical_verdict["ledger_path"],
        canonical_verdict["report_paths"],
        canonical_verdict["verdict_path"],
        admission_path,
    )
    assert replay["admission"] == payload
    assert len(calls) == 3


def test_admission_rejects_joint_verdict_tampering_before_publication(
    canonical_verdict: dict[str, Any],
    verdict_builder: ModuleType,
    admission: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        admission,
        "_load_verdict_builder",
        lambda: _spy_verdict_builder(verdict_builder, calls),
    )
    tampered = copy.deepcopy(canonical_verdict["verdict"])
    tampered["candidates"]["upper_bound_1188_22"]["status"] = "FAIL"
    tampered["current_project_ledger"] = {"U": [1188, 22], "L": "present"}
    tampered["upper_bound_changed"] = True
    tampered["formal_run_authorized"] = True
    tampered["production_certified"] = True
    _write_json(canonical_verdict["verdict_path"], tampered)
    output = canonical_verdict["response"] / "admission/a004"
    with pytest.raises(admission.AdmissionError):
        admission.close_admission(
            canonical_verdict["authority"],
            canonical_verdict["response"],
            canonical_verdict["ledger_path"],
            canonical_verdict["report_paths"],
            canonical_verdict["verdict_path"],
            output,
        )
    assert len(calls) == 1
    assert not output.exists()


@pytest.mark.parametrize(
    "mutator",
    [
        pytest.param(
            lambda value: value.__setitem__("solver_run_authorized", True),
            id="solver-authorization",
        ),
        pytest.param(
            lambda value: value.__setitem__("production_certified", True),
            id="production-certified",
        ),
        pytest.param(
            lambda value: value["candidates"]["upper_bound_1188_22"].__setitem__(
                "b1_followup_input_admitted",
                False,
            ),
            id="upper-candidate-admission",
        ),
        pytest.param(
            lambda value: (
                value.__setitem__("current_project_ledger", {"U": [1188, 22], "L": "present"}),
                value.__setitem__("upper_bound_changed", True),
                value.__setitem__("formal_run_authorized", True),
            ),
            id="joint-global-fields",
        ),
    ],
)
def test_admission_replay_rejects_candidate_and_global_safety_tampering(
    canonical_verdict: dict[str, Any],
    verdict_builder: ModuleType,
    admission: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    mutator: Callable[[dict[str, Any]], Any],
) -> None:
    monkeypatch.setattr(
        admission,
        "_load_verdict_builder",
        lambda: SimpleNamespace(replay_verdict=verdict_builder.replay_verdict),
    )
    output = canonical_verdict["response"] / "admission/a004"
    admission.close_admission(
        canonical_verdict["authority"],
        canonical_verdict["response"],
        canonical_verdict["ledger_path"],
        canonical_verdict["report_paths"],
        canonical_verdict["verdict_path"],
        output,
    )
    admission_path = output / "admission.json"
    tampered = json.loads(admission_path.read_bytes())
    mutator(tampered)
    _write_json(admission_path, tampered)
    with pytest.raises(admission.AdmissionError):
        admission.replay_admission(
            canonical_verdict["authority"],
            canonical_verdict["response"],
            canonical_verdict["ledger_path"],
            canonical_verdict["report_paths"],
            canonical_verdict["verdict_path"],
            admission_path,
        )


@pytest.mark.parametrize(
    "field",
    [
        "upper_bound_changed",
        "formal_run_authorized",
        "encoder_execution_authorized",
        "solver_run_authorized",
        "search_run_authorized",
        "assembly_run_authorized",
        "router_run_authorized",
        "track_w_execution_authorized",
        "external_response_code_executed",
        "witness_established",
        "attainability_established",
        "optimality_established",
        "global_infeasibility_established",
        "production_certified",
    ],
)
def test_admission_replay_rejects_each_global_safety_or_authorization_flip(
    canonical_verdict: dict[str, Any],
    verdict_builder: ModuleType,
    admission: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    monkeypatch.setattr(
        admission,
        "_load_verdict_builder",
        lambda: SimpleNamespace(replay_verdict=verdict_builder.replay_verdict),
    )
    output = canonical_verdict["response"] / "admission/a004"
    admission.close_admission(
        canonical_verdict["authority"],
        canonical_verdict["response"],
        canonical_verdict["ledger_path"],
        canonical_verdict["report_paths"],
        canonical_verdict["verdict_path"],
        output,
    )
    admission_path = output / "admission.json"
    tampered = json.loads(admission_path.read_bytes())
    assert tampered[field] is False
    tampered[field] = True
    _write_json(admission_path, tampered)
    with pytest.raises(admission.AdmissionError):
        admission.replay_admission(
            canonical_verdict["authority"],
            canonical_verdict["response"],
            canonical_verdict["ledger_path"],
            canonical_verdict["report_paths"],
            canonical_verdict["verdict_path"],
            admission_path,
        )


def _producer_guard(
    producer: str,
    request: pytest.FixtureRequest,
) -> tuple[Callable[[Path, Path], Path], str, str, type[Exception]]:
    if producer == "ledger":
        module = request.getfixturevalue("ledger_builder")
        return module._create_claim_output_dir, "claims", "a004", module.LedgerError
    if producer == "runner":
        module = request.getfixturevalue("runner")
        return (
            lambda response, output: module._prepare_output_dir(
                response,
                output,
                checker_id="upper_counts",
            ),
            "recomputations",
            "upper-counts-a004",
            module.RecomputationError,
        )
    module = request.getfixturevalue("verdict_builder" if producer == "verdict" else "admission")
    category = "adversarial" if producer == "verdict" else "admission"
    error = module.VerdictError if producer == "verdict" else module.AdmissionError
    return (
        lambda response, output: module._create_output_dir(response, category, output),
        category,
        "a004",
        error,
    )


@pytest.mark.parametrize("producer", ["ledger", "runner", "verdict", "admission"])
def test_producer_output_guard_creates_only_fresh_direct_child(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    producer: str,
) -> None:
    _authority, response = _response_tree(tmp_path)
    guard, category, name, _error = _producer_guard(producer, request)
    output = response / category / name
    assert guard(response, output) == output
    assert output.is_dir()
    assert not output.is_symlink()


@pytest.mark.parametrize("producer", ["ledger", "runner", "verdict", "admission"])
@pytest.mark.parametrize(
    "attack",
    [
        "outside",
        "wrong-category",
        "nested",
        "dotdot-alias",
        "invalid-name",
        "existing",
        "target-symlink",
        "parent-symlink",
    ],
)
def test_producer_output_guard_rejects_escape_overwrite_and_symlinks(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    producer: str,
    attack: str,
) -> None:
    _authority, response = _response_tree(tmp_path)
    guard, category, name, error = _producer_guard(producer, request)
    output = response / category / name
    preexisting = False
    if attack == "outside":
        outside = tmp_path / "outside"
        outside.mkdir()
        output = outside / name
    elif attack == "wrong-category":
        wrong = "admission" if category != "admission" else "claims"
        output = response / wrong / name
    elif attack == "nested":
        nested = response / category / "nested"
        nested.mkdir()
        output = nested / name
    elif attack == "dotdot-alias":
        output = response / category / "nested" / ".." / name
    elif attack == "invalid-name":
        output = response / category / "not-an-attempt"
    elif attack == "existing":
        output.mkdir()
        preexisting = True
    elif attack == "target-symlink":
        target = tmp_path / "target"
        target.mkdir()
        output.symlink_to(target, target_is_directory=True)
        preexisting = True
    elif attack == "parent-symlink":
        category_path = response / category
        category_path.rmdir()
        target = tmp_path / "category-target"
        target.mkdir()
        category_path.symlink_to(target, target_is_directory=True)
        output = category_path / name

    with pytest.raises(error):
        guard(response, output)
    if not preexisting:
        assert not output.exists()


def test_real_a004_authority_chain_full_replay(
    ledger_builder: ModuleType,
    runner: ModuleType,
    verdict_builder: ModuleType,
    admission: ModuleType,
) -> None:
    required = [A004_LEDGER, *A004_REPORTS, A004_VERDICT, A004_ADMISSION]
    if not all(path.is_file() for path in required):
        pytest.skip("the immutable a004 authority chain has not been published yet")
    ledger, claims = ledger_builder.replay_claim_ledger(AUTHORITY, RESPONSE_RUN, A004_LEDGER)
    assert ledger["claim_count"] == 17
    assert len(claims) == 17
    provenance = runner.validate_archive(RESPONSE_RUN, AUTHORITY)
    assert runner.validate_claim_ledger(A004_LEDGER, provenance) == (ledger, claims)
    verdict_replay = verdict_builder.replay_verdict(
        AUTHORITY,
        RESPONSE_RUN,
        A004_LEDGER,
        A004_REPORTS,
        A004_VERDICT,
    )
    assert verdict_replay["verdict"]["status"] == "COMPLETE"
    replay = admission.replay_admission(
        AUTHORITY,
        RESPONSE_RUN,
        A004_LEDGER,
        A004_REPORTS,
        A004_VERDICT,
        A004_ADMISSION,
    )
    assert replay["admission"]["status"] == "PARTIAL"
    assert replay["admission"]["current_project_ledger"] == {
        "L": "absent",
        "U": [1190, 34],
    }
