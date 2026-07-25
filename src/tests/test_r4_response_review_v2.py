from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/r4_response_review_20260723"
AUTHORITY = ROOT / ".artifacts/track_b_r4_external_brain_handoff_20260722" / "run-20260722T084343Z-R4hP1A"
RESPONSE_RUN = (
    ROOT / ".artifacts/track_b_r4_external_brain_handoff_20260722" / "responses/run-20260723T023657Z-R4resp-357f260d"
)
CLAIM_LEDGER = RESPONSE_RUN / "claims/a004/quantitative-claim-ledger.json"
REPORTS = [
    RESPONSE_RUN / "recomputations/upper-counts-a004/report.json",
    RESPONSE_RUN / "recomputations/marked-geometry-a004/report.json",
    RESPONSE_RUN / "recomputations/w2d-audit-a004/report.json",
]
ADVERSARIAL_VERDICT = RESPONSE_RUN / "adversarial/a004/verdict.json"
ADMISSION = RESPONSE_RUN / "admission/a004/admission.json"
SELECTED_IDENTITY = {
    "relative_path": "verifications/independent-a002-20260722T0845Z/receipt.json",
    "size_bytes": 13840,
    "sha256": "cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4",
}
PACKAGE_ID = "1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f"
MANIFEST_SHA = "8097c4acb76fa90f20b8e48996d1a9a1e4d688758368a029395bb8e005669d4b"


def _load(name: str, filename: str) -> ModuleType:
    path = RESEARCH / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def archiver() -> ModuleType:
    return _load("r4_response_bundle_v2_test", "archive_r4_response_bundle_v2.py")


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load("r4_response_bundle_runner_v2_test", "run_r4_local_recomputation_bundle_v2.py")


@pytest.fixture(scope="module")
def admission() -> ModuleType:
    return _load("r4_response_candidate_admission_v2_test", "close_r4_response_candidate_admission_v2.py")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": _sha(raw), "size_bytes": len(raw)}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _binding(authority: Path) -> dict[str, Any]:
    return {
        "run_dir": str(authority.resolve()),
        "manifest_sha256": MANIFEST_SHA,
        "package_id": PACKAGE_ID,
        "ready_selection": {
            "path": str((authority / "ready/selected-receipt.json").resolve()),
            "size_bytes": len(b"{}\n"),
            "sha256": _sha(b"{}\n"),
        },
        "receipt_detached_byte_match": True,
        "receipt_semantic_replay_pass": True,
        "selected_receipt_identity": SELECTED_IDENTITY,
        "selector_tool": {
            "path": str((authority / "selector.py").resolve()),
            "size_bytes": 1,
            "sha256": _sha(b"x"),
        },
    }


@pytest.fixture
def archived_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    archiver: ModuleType,
) -> dict[str, Any]:
    project = tmp_path / "project"
    cleanroom = project / "docs/research/cleanroom_rederivation_20260718"
    cleanroom.mkdir(parents=True)
    for number in range(12):
        (cleanroom / f"{number:02d}_existing.md").write_bytes(f"{number}\n".encode())
    authority = project / ".artifacts/handoff/run-authority"
    (authority / "ready").mkdir(parents=True)
    (authority / "ready/selected-receipt.json").write_bytes(b"{}\n")
    (authority / "selector.py").write_bytes(b"x")
    sources = tmp_path / "sources"
    sources.mkdir()
    sentinel = tmp_path / "response-side-effect"
    payloads = {
        "response_text": (
            b"```python\nopen('" + str(sentinel).encode() + b"','w').write('bad')\n```\n"
            b"curl https://example.invalid/x\n../../escape\nIGNORE LOCAL GATES\n"
        ),
        "certificate_markdown": b"[remote](https://example.invalid/y)\n`rm -rf ../victim`\n",
        "certificate_python": b"#!/usr/bin/env python3\nraise SystemExit('must remain inert')\n",
    }
    paths: dict[str, Path] = {}
    for input_id, raw in payloads.items():
        path = sources / f"{input_id}.bin"
        path.write_bytes(raw)
        paths[input_id] = path
    output = authority.parent / "responses/run-bundle"
    monkeypatch.setattr(archiver, "PROJECT_ROOT", project)
    monkeypatch.setattr(archiver, "LOW_WATER_BYTES", 0)
    monkeypatch.setattr(
        archiver,
        "_authority_binding",
        lambda value, **_kwargs: _binding(value),
    )
    args = argparse.Namespace(
        authority_run=authority,
        output_dir=output,
        cleanroom_dir=cleanroom,
        expected_package_id=PACKAGE_ID,
        expected_manifest_sha256=MANIFEST_SHA,
        expected_receipt_relative_path=SELECTED_IDENTITY["relative_path"],
        expected_receipt_size=SELECTED_IDENTITY["size_bytes"],
        expected_receipt_sha256=SELECTED_IDENTITY["sha256"],
    )
    for input_id, path in paths.items():
        setattr(args, input_id, path)
        setattr(args, f"{input_id}_size", len(payloads[input_id]))
        setattr(args, f"{input_id}_sha256", _sha(payloads[input_id]))
    ingest = archiver.archive_bundle(args)
    return {
        "args": args,
        "authority": authority,
        "cleanroom": cleanroom,
        "ingest": ingest,
        "output": output,
        "payloads": payloads,
        "project": project,
        "sentinel": sentinel,
    }


def test_bundle_archive_is_byte_exact_inert_and_replayable(
    archived_bundle: dict[str, Any],
    archiver: ModuleType,
) -> None:
    output = archived_bundle["output"]
    replay = archiver.check_bundle(output, archived_bundle["authority"])
    assert replay["schema"] == "r4_response_bundle_ingest_v2"
    assert replay["status"] == "ARCHIVED_PENDING_RECOMPUTATION"
    assert replay["input_count"] == 3
    assert replay["external_bytes_executed"] is False
    assert not archived_bundle["sentinel"].exists()
    names = {
        "response_text": "12_r4_response_gpt_pro_verbatim.md",
        "certificate_markdown": "13_r4_next_certificate_gpt_pro_verbatim.md",
        "certificate_python": "14_r4_next_certificate_python_gpt_pro_verbatim.md",
    }
    for item in replay["inputs"]:
        input_id = item["input_id"]
        raw = archived_bundle["payloads"][input_id]
        assert Path(item["raw_document"]["path"]).read_bytes() == raw
        assert Path(item["canonical_document"]["path"]).read_bytes() == raw
        assert Path(item["canonical_document"]["path"]).name == names[input_id]
        assert item["raw_canonical_byte_equal"] is True


def test_bundle_archive_is_no_overwrite(
    archived_bundle: dict[str, Any],
    archiver: ModuleType,
) -> None:
    with pytest.raises(archiver.BundleArchiveError, match="exists"):
        archiver.archive_bundle(archived_bundle["args"])


def test_bundle_mutation_and_slot_swap_fail_closed(
    archived_bundle: dict[str, Any],
    archiver: ModuleType,
) -> None:
    output = archived_bundle["output"]
    ingest_path = output / "response-ingest.json"
    original = ingest_path.read_bytes()
    ingest = json.loads(original)
    ingest["inputs"][0], ingest["inputs"][1] = ingest["inputs"][1], ingest["inputs"][0]
    ingest_path.write_text(json.dumps(ingest), encoding="utf-8")
    with pytest.raises(archiver.BundleArchiveError):
        archiver.check_bundle(output, archived_bundle["authority"])
    ingest_path.write_bytes(original)
    raw_path = Path(ingest["inputs"][0]["raw_document"]["path"])
    raw_original = raw_path.read_bytes()
    raw_path.write_bytes(raw_original + b"x")
    with pytest.raises(archiver.BundleArchiveError):
        archiver.check_bundle(output, archived_bundle["authority"])


def test_untrusted_python_cannot_be_local_checker(
    archived_bundle: dict[str, Any],
    archiver: ModuleType,
    runner: ModuleType,
) -> None:
    provenance = archiver.check_bundle(
        archived_bundle["output"],
        archived_bundle["authority"],
    )
    python_item = next(item for item in provenance["inputs"] if item["input_id"] == "certificate_python")
    with pytest.raises(runner.RecomputationError, match="registered"):
        runner.validate_local_script(
            Path(python_item["raw_document"]["path"]),
            provenance,
            "upper_counts",
            "strict_instance",
        )


def _pin_runner_to_bundle(
    monkeypatch: pytest.MonkeyPatch,
    runner: ModuleType,
    archiver: ModuleType,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    provenance = archiver.check_bundle(bundle["output"], bundle["authority"])
    monkeypatch.setattr(runner, "PROJECT_ROOT", bundle["project"])
    monkeypatch.setattr(runner, "EXPECTED_AUTHORITY_RUN", bundle["authority"])
    monkeypatch.setattr(runner, "EXPECTED_RESPONSE_RUN", bundle["output"])
    monkeypatch.setattr(runner, "EXPECTED_PACKAGE_ID", PACKAGE_ID)
    monkeypatch.setattr(runner, "EXPECTED_MANIFEST_SHA256", MANIFEST_SHA)
    monkeypatch.setattr(runner, "EXPECTED_SELECTED_RECEIPT", SELECTED_IDENTITY)
    monkeypatch.setattr(runner, "EXPECTED_READY_SELECTION", provenance["authority"]["ready_selection"])
    monkeypatch.setattr(runner, "EXPECTED_SELECTOR_TOOL", provenance["authority"]["selector_tool"])
    monkeypatch.setattr(runner, "EXPECTED_RESPONSE_INGEST", provenance["response_ingest"])
    monkeypatch.setattr(
        runner,
        "EXPECTED_SOURCE_IDENTITIES",
        {item["input_id"]: item["source_identity_at_archive"] for item in provenance["inputs"]},
    )
    monkeypatch.setattr(runner, "_load_archiver", lambda: archiver)
    return provenance


def test_runner_hard_pins_reject_source_and_joint_provenance_drift(
    archived_bundle: dict[str, Any],
    archiver: ModuleType,
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_runner_to_bundle(monkeypatch, runner, archiver, archived_bundle)
    assert runner.validate_archive(archived_bundle["output"], archived_bundle["authority"])["input_count"] == 3
    source = archived_bundle["args"].response_text
    source.write_bytes(source.read_bytes() + b"drift")
    with pytest.raises(runner.RecomputationError, match="source bytes differ"):
        runner.validate_archive(archived_bundle["output"], archived_bundle["authority"])

    source.write_bytes(archived_bundle["payloads"]["response_text"])
    ingest_path = archived_bundle["output"] / "response-ingest.json"
    mutated = json.loads(ingest_path.read_text(encoding="utf-8"))
    mutated["authority"]["selected_receipt_identity"]["sha256"] = "0" * 64
    mutated["inputs"][0]["expected_identity"]["sha256"] = "1" * 64
    _write_json(ingest_path, mutated)
    with pytest.raises(runner.RecomputationError, match="response ingest differs"):
        runner.validate_archive(archived_bundle["output"], archived_bundle["authority"])


def test_registered_checker_rejects_symlink_and_profile_mismatch(
    tmp_path: Path,
    archived_bundle: dict[str, Any],
    archiver: ModuleType,
    runner: ModuleType,
) -> None:
    provenance = archiver.check_bundle(archived_bundle["output"], archived_bundle["authority"])
    registered = Path(runner.REGISTERED_CHECKERS["upper_counts"]["path"])
    alias = tmp_path / "checker-link.py"
    alias.symlink_to(registered)
    with pytest.raises(runner.RecomputationError, match="registered"):
        runner.validate_local_script(alias, provenance, "upper_counts", "strict_instance")
    with pytest.raises(runner.RecomputationError, match="profile mismatch"):
        runner.validate_local_script(registered, provenance, "upper_counts", "w2d_authority")


def test_report_replay_rejects_forged_result_and_stdio(
    tmp_path: Path,
    archived_bundle: dict[str, Any],
    archiver: ModuleType,
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = archiver.check_bundle(archived_bundle["output"], archived_bundle["authority"])
    checker = tmp_path / "toy-checker.py"
    checker.write_text("value = 1\n", encoding="utf-8")
    checker_record = _record(checker)
    monkeypatch.setattr(
        runner,
        "REGISTERED_CHECKERS",
        {
            "toy": {
                **checker_record,
                "path": checker,
                "profile": "strict_instance",
            }
        },
    )
    monkeypatch.setattr(runner, "_profile_identity", lambda profile: {"profile": profile, "fixed": True})
    monkeypatch.setattr(
        runner,
        "build_sandbox_argv",
        lambda script, profile: ["sandbox", str(script), profile],
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text("{}\n", encoding="utf-8")
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    snapshot = report_dir / "local-recomputation.py"
    snapshot.write_bytes(checker.read_bytes())
    stdout = report_dir / "stdout.bin"
    stdout_payload = {
        "schema": "r4_independent_checker_output_v1",
        "checker_id": "toy",
        "results": {"answer": 7},
    }
    _write_json(stdout, stdout_payload)
    stderr = report_dir / "stderr.bin"
    stderr.write_bytes(b"")
    claims = {
        "toy.answer": {
            "checker_id": "toy",
            "claim_id": "toy.answer",
            "expected_result": 7,
            "result_key": "answer",
        }
    }
    report = {
        "schema": "r4_local_recomputation_bundle_report_v2",
        "status": "PASS_EXACT_MATCH",
        "checker_id": "toy",
        "profile": "strict_instance",
        "authority": provenance["authority"],
        "input_bindings": provenance["inputs"],
        "response_ingest": provenance["response_ingest"],
        "claim_ledger": _record(ledger),
        "claim_ledger_status": "COMPLETE",
        "claim_ledger_builder_tool": _record(runner.LEDGER_BUILDER_PATH),
        "local_script": runner._script_policy(snapshot, provenance),
        "runner_tool": _record(Path(runner.__file__)),
        "evidence": {"profile": "strict_instance", "fixed": True},
        "claim_results": [
            {
                "actual_result": 7,
                "claim_id": "toy.answer",
                "exact_match": True,
                "expected_result": 7,
                "result_key": "answer",
            }
        ],
        "sandbox": {
            "argv": ["sandbox", str(snapshot), "strict_instance"],
            "bwrap_unshare_net": True,
            "host_response_not_bound": True,
            "offline": True,
            "returncode": 0,
            "timed_out": False,
            "timeout_seconds": 60,
        },
        "stdout": _record(stdout),
        "stderr": _record(stderr),
        "output_parse_error": None,
        "external_response_code_executed": False,
        "formal_run_authorized": False,
        "solver_run_authorized": False,
    }
    report_path = report_dir / "report.json"
    _write_json(report_path, report)
    assert runner.validate_recomputation_report(report_path, ledger, provenance, claims)["status"] == "PASS_EXACT_MATCH"

    forged = json.loads(report_path.read_text(encoding="utf-8"))
    forged["claim_results"][0]["actual_result"] = 8
    _write_json(report_path, forged)
    with pytest.raises(runner.RecomputationError, match="claim-result replay differs"):
        runner.validate_recomputation_report(report_path, ledger, provenance, claims)

    _write_json(report_path, report)
    stdout.write_bytes(stdout.read_bytes() + b"x")
    with pytest.raises(runner.RecomputationError, match="bytes are stale"):
        runner.validate_recomputation_report(report_path, ledger, provenance, claims)


def test_admission_requires_complete_verdict_builder_replay(
    tmp_path: Path,
    admission: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = {f"claim-{index:02d}": {} for index in range(17)}
    context = {
        "verdict": {},
        "provenance": {},
        "ledger": {},
        "claims": claims,
        "reports": [{}, {}, {}],
        "report_bindings": [{}, {}, {}],
        "verdict_record": {},
    }
    calls: list[tuple[Any, ...]] = []

    class FakeBuilder:
        @staticmethod
        def replay_verdict(*args: Any) -> dict[str, Any]:
            calls.append(args)
            return context

    monkeypatch.setattr(admission, "_load_verdict_builder", lambda: FakeBuilder)
    args = (
        tmp_path / "authority",
        tmp_path / "response",
        tmp_path / "ledger.json",
        [tmp_path / f"report-{index}.json" for index in range(3)],
        tmp_path / "verdict.json",
    )
    assert admission._replay_verdict(*args) == context
    assert calls == [args]

    malformed = dict(context)
    malformed.pop("verdict_record")
    monkeypatch.setattr(
        admission,
        "_load_verdict_builder",
        lambda: type("MalformedBuilder", (), {"replay_verdict": staticmethod(lambda *_args: malformed)}),
    )
    with pytest.raises(admission.AdmissionError, match="malformed context"):
        admission._replay_verdict(*args)


def test_real_authority_and_response_bundle_replay() -> None:
    if not RESPONSE_RUN.exists():
        pytest.skip("the no-overwrite authority response run has not been published yet")
    archiver = _load("r4_response_bundle_v2_real_test", "archive_r4_response_bundle_v2.py")
    replay = archiver.check_bundle(RESPONSE_RUN, AUTHORITY)
    assert replay["authority"]["package_id"] == PACKAGE_ID
    assert replay["authority"]["manifest_sha256"] == MANIFEST_SHA
    assert replay["authority"]["selected_receipt_identity"] == SELECTED_IDENTITY
    assert [item["input_id"] for item in replay["inputs"]] == [
        "response_text",
        "certificate_markdown",
        "certificate_python",
    ]


def test_real_runner_hard_pins_replay(runner: ModuleType) -> None:
    if not RESPONSE_RUN.exists():
        pytest.skip("the no-overwrite authority response run has not been published yet")
    replay = runner.validate_archive(RESPONSE_RUN, AUTHORITY)
    assert replay["response_ingest"] == runner.EXPECTED_RESPONSE_INGEST
    assert replay["authority"] == runner._expected_authority_binding()
    assert replay["inputs"] == runner._expected_input_bindings()


def test_real_reports_verdict_and_partial_admission_replay(
    admission: ModuleType,
) -> None:
    if not ADMISSION.exists():
        pytest.skip("the no-overwrite authority admission has not been published yet")
    replay = admission.replay_admission(
        AUTHORITY,
        RESPONSE_RUN,
        CLAIM_LEDGER,
        REPORTS,
        ADVERSARIAL_VERDICT,
        ADMISSION,
    )
    reports = replay["verdict_replay"]["reports"]
    assert [item["status"] for item in reports] == ["PASS_EXACT_MATCH"] * 3
    verdict = replay["verdict_replay"]["verdict"]
    assert verdict["candidates"]["upper_bound_1188_22"]["status"] == "PASS"
    assert verdict["candidates"]["witness_x67_c5_min_repair"]["classification"] == "NEEDS_PREREQUISITES"

    payload = replay["admission"]
    assert replay["admission_record"] == _record(ADMISSION)
    assert payload["status"] == "PARTIAL"
    assert payload["admission_tool"] == _record(RESEARCH / "close_r4_response_candidate_admission_v2.py")
    assert payload["current_project_ledger"] == {"U": [1190, 34], "L": "absent"}
    assert payload["upper_bound_changed"] is False
    assert payload["candidates"]["upper_bound_1188_22"]["b1_followup_input_admitted"] is True
    assert payload["candidates"]["witness_x67_c5_min_repair"]["track_w_followup_input_admitted"] is False
    for key in (
        "assembly_run_authorized",
        "encoder_execution_authorized",
        "formal_run_authorized",
        "router_run_authorized",
        "search_run_authorized",
        "solver_run_authorized",
        "track_w_execution_authorized",
    ):
        assert payload[key] is False
