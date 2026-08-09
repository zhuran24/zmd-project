from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab_trust_gate1_v3_20260723"
HEAD = "a" * 40
NONCE = "gate1-v3-synthetic"


def _load(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load("noncert_gate1_v3_builder", "build_qualification_package_v1.py")
VERIFIER = _load("noncert_gate1_v3_verifier", "verify_qualification_package_v1.py")
GATE = _load("noncert_gate1_v3_gate", "positive_control_gate_v3.py")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"path": str(path.absolute()), "sha256": _sha(raw), "size_bytes": len(raw)}


def _package_snapshot(run: Path) -> dict[str, bytes]:
    package = run / "package"
    return {path.relative_to(package).as_posix(): path.read_bytes() for path in package.rglob("*") if path.is_file()}


def _sources(tmp_path: Path) -> tuple[list[Any], dict[str, Path]]:
    paths = {
        "checker": tmp_path / "sources/checker.py",
        "resource_verifier": tmp_path / "sources/resource_verifier.py",
        "gate_v2": tmp_path / "sources/gate_v2.py",
        "gate_v3": tmp_path / "sources/gate_v3.py",
        "observer": tmp_path / "sources/launch_selection_observer_v1.py",
        "positive_control_gate_v3": RESEARCH / "positive_control_gate_v3.py",
        "mandatory": tmp_path / "sources/mandatory.json",
        "candidates": tmp_path / "sources/candidates.json",
    }
    for role, path in paths.items():
        if role == "positive_control_gate_v3":
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            _write_json(path, {"role": role, "rows": [1, 2, 3]})
        else:
            path.write_text(f"# {role}\nVALUE = {role!r}\n", encoding="utf-8")
    specs = [
        BUILDER.SourceSpec(role=role, path=path, parse_json=path.suffix == ".json") for role, path in paths.items()
    ]
    return specs, paths


def _qualified(tmp_path: Path) -> dict[str, Any]:
    specs, paths = _sources(tmp_path)
    run = tmp_path / "qualification"
    built = BUILDER.build_package(
        run,
        specs,
        repository_head=HEAD,
        run_nonce=NONCE,
        argv=("build_qualification_package_v1.py",),
    )
    receipt_result = VERIFIER.create_pass_receipt(run, "verification-a001")
    receipt_path = run / str(receipt_result["receipt_relative_path"])
    receipt = json.loads(receipt_path.read_bytes())
    return {
        "build": built,
        "inputs": {role: _identity(paths[role]) for role in ("mandatory", "candidates")},
        "paths": paths,
        "receipt": receipt,
        "receipt_identity": _identity(receipt_path),
        "receipt_path": receipt_path,
        "run": run,
        "tools": {
            role: _identity(paths[role])
            for role in (
                "checker",
                "resource_verifier",
                "gate_v2",
                "gate_v3",
                "positive_control_gate_v3",
                "observer",
            )
        },
    }


def _historical_selection(qualified: dict[str, Any]) -> dict[str, object]:
    return GATE.make_historical_selection(
        package_id=str(qualified["build"]["package_id"]),
        run_nonce=NONCE,
        created_at_utc="2026-07-23T00:00:00Z",
        repository_head=HEAD,
        qualification_receipt_identity=qualified["receipt_identity"],
        tools=qualified["tools"],
        inputs=qualified["inputs"],
        historical_overlay={
            "gate": "closeout-a001/gate-a002.json",
            "purpose": "read-only replay",
        },
    )


def _paired_arms(tmp_path: Path) -> dict[str, dict[str, object]]:
    arms: dict[str, dict[str, object]] = {}
    for label in ("control", "treatment"):
        attempt = (tmp_path / f"future/{label}").absolute()
        arms[label] = {
            "arm": label,
            "attempt_dir": str(attempt),
            "raw_output_path": str(attempt / "resource/inner.jsonl"),
            "recorder_tool_role": "resource_verifier",
            "result_path": str(attempt / "result.json"),
            "runner_tool_role": "checker",
            "terminal_envelope_path": str(attempt / "resource/terminal.json"),
            "unit_name": f"future-{label}.service",
        }
    return arms


def _historical_result(
    qualified: dict[str, Any],
    selection: dict[str, object],
    selection_identity: dict[str, object],
) -> dict[str, object]:
    return GATE.evaluate_gate(
        selection=selection,
        selection_identity=selection_identity,
        expected_selection_identity=selection_identity,
        qualification_receipt=qualified["receipt"],
        qualification_receipt_identity=qualified["receipt_identity"],
        semantic_replay=None,
        arm_results=None,
        inner_raw_results=None,
        terminal_envelopes=None,
        model_binary_identities=None,
        response_binary_identities=None,
    )


def test_package_one_way_seal_and_derived_pass_receipt_never_authorize(tmp_path: Path) -> None:
    qualified = _qualified(tmp_path)
    run = qualified["run"]
    package = run / "package"
    files = _package_snapshot(run)
    sha_lines = files["SHA256SUMS"].decode("ascii").splitlines()
    entries = {line[66:]: line[:64] for line in sha_lines}
    assert set(entries) == set(files) - {"SHA256SUMS"}
    assert entries["package-manifest.json"] == _sha(files["package-manifest.json"])
    assert all(entries[path] == _sha(files[path]) for path in entries)
    assert _sha(files["SHA256SUMS"]) == qualified["build"]["package_id"]

    manifest = json.loads(files["package-manifest.json"])
    assert "package-manifest.json" not in {row["path"] for row in manifest["package_members"]}
    assert "SHA256SUMS" not in {row["path"] for row in manifest["package_members"]}
    receipt = qualified["receipt"]
    assert receipt["status"] == "PASS"
    assert receipt["authorization_root"] is False
    assert receipt["arm_launch_authorized"] is False
    assert receipt["classification_authorized"] is False
    assert qualified["receipt_path"].is_relative_to(run / "verifications")
    assert not qualified["receipt_path"].is_relative_to(package)

    before = _package_snapshot(run)
    second = VERIFIER.create_pass_receipt(run, "verification-a002")
    assert second["status"] == "PASS"
    assert _package_snapshot(run) == before
    with pytest.raises(BUILDER.QualificationBuildError, match="immutable"):
        BUILDER._publish_package(run, "payload/late", b"forbidden")


def test_package_pass_alone_cannot_authorize_launch_or_verdict(tmp_path: Path) -> None:
    qualified = _qualified(tmp_path)
    result = GATE.evaluate_gate(
        selection=None,
        selection_identity=None,
        expected_selection_identity=None,
        qualification_receipt=qualified["receipt"],
        qualification_receipt_identity=qualified["receipt_identity"],
        semantic_replay={"status": "PASS"},
        arm_results=None,
        inner_raw_results=None,
        terminal_envelopes=None,
        model_binary_identities=None,
        response_binary_identities=None,
    )
    assert result["qualification_receipt_is_authorization_root"] is False
    assert result["selection_is_direct_authority_root"] is False
    assert result["arm_launch_authorized"] is False
    assert result["experiment_verdict"] is False
    assert result["classification_complete"] is False
    assert result["semantic_replay_gate_owned"] is False
    assert "qualification_package_missing" in result["missing_gates"]
    assert "paired_arm_launch_authority_missing" in result["missing_gates"]


def test_historical_selection_is_permanently_non_launching_and_purpose_flip_fails(
    tmp_path: Path,
) -> None:
    qualified = _qualified(tmp_path)
    historical = _historical_selection(qualified)
    assert historical["purpose"] == GATE.HISTORICAL_PURPOSE
    assert historical["arm_launch"] is False
    selection_path = tmp_path / "selection/historical.json"
    selection_path.parent.mkdir()
    identity = GATE.write_launch_selection(selection_path, historical)
    assert identity == _identity(selection_path)
    with pytest.raises(GATE.GateV3Error, match="overwrite"):
        GATE.write_launch_selection(selection_path, historical)

    flipped = copy.deepcopy(historical)
    flipped["purpose"] = GATE.PAIRED_PURPOSE
    with pytest.raises(GATE.GateV3Error):
        GATE.validate_selection_payload(flipped)

    armed = copy.deepcopy(historical)
    armed["arm_launch"] = True
    armed_body = dict(armed)
    armed_body.pop("selection_id")
    armed["selection_id"] = GATE._sha256(GATE._canonical_digest_bytes(armed_body))
    with pytest.raises(GATE.GateV3Error, match="arm_launch=false"):
        GATE.validate_selection_payload(armed)


def test_paired_selection_must_precede_both_arm_directories(tmp_path: Path) -> None:
    qualified = _qualified(tmp_path)
    control = tmp_path / "arms/control"
    treatment = tmp_path / "arms/treatment"
    selection = GATE.make_paired_selection(
        package_id=str(qualified["build"]["package_id"]),
        run_nonce=NONCE,
        created_at_utc="2026-07-23T00:00:00Z",
        repository_head=HEAD,
        qualification_receipt_identity=qualified["receipt_identity"],
        tools=qualified["tools"],
        inputs=qualified["inputs"],
        arms={
            **_paired_arms(tmp_path),
            "control": {
                **_paired_arms(tmp_path)["control"],
                "attempt_dir": str(control.absolute()),
                "raw_output_path": str(control.absolute() / "resource/inner.jsonl"),
                "result_path": str(control.absolute() / "result.json"),
                "terminal_envelope_path": str(control.absolute() / "resource/terminal.json"),
            },
            "treatment": {
                **_paired_arms(tmp_path)["treatment"],
                "attempt_dir": str(treatment.absolute()),
                "raw_output_path": str(treatment.absolute() / "resource/inner.jsonl"),
                "result_path": str(treatment.absolute() / "result.json"),
                "terminal_envelope_path": str(treatment.absolute() / "resource/terminal.json"),
            },
        },
        terminal_observer_tool_role="observer",
    )
    control.mkdir(parents=True)
    output = tmp_path / "selection/paired.json"
    output.parent.mkdir()
    with pytest.raises(GATE.GateV3Error, match="predate arm directory"):
        GATE.write_launch_selection(output, selection)
    assert not output.exists()


def test_old_a002_historical_overlay_lists_every_common_missing_gate(tmp_path: Path) -> None:
    qualified = _qualified(tmp_path)
    selection = _historical_selection(qualified)
    selection_path = tmp_path / "selection/historical.json"
    selection_path.parent.mkdir()
    selection_identity = GATE.write_launch_selection(selection_path, selection)
    result = _historical_result(qualified, selection, selection_identity)
    assert result["status"] == "CREDIBILITY_INCOMPLETE"
    assert result["reason"] == "resource_authority_missing"
    assert result["missing_gates"] == list(GATE.COMMON_MISSING_GATES)
    assert result["overlay"] is True
    assert result["historical_overlay"] is True
    assert result["experiment_verdict"] is False
    assert result["classification_complete"] is False
    assert result["advance_authorized"] is False
    assert result["claim_boundary"]["established"] == []
    assert GATE.exit_code(result) == 2


def test_historical_cli_overlay_exits_two_without_error_field(tmp_path: Path) -> None:
    qualified = _qualified(tmp_path)
    selection = _historical_selection(qualified)
    selection_path = tmp_path / "selection/historical.json"
    selection_path.parent.mkdir()
    selection_identity = GATE.write_launch_selection(selection_path, selection)
    evidence_path = tmp_path / "evidence.json"
    _write_json(
        evidence_path,
        {
            "arms": None,
            "positive_treatment": None,
            "resource": None,
            "schema": GATE.EVIDENCE_PATHS_SCHEMA,
        },
    )
    output = tmp_path / "gate-a003.json"
    code = GATE.main(
        [
            "--selection",
            str(selection_path),
            "--expected-selection-size",
            str(selection_identity["size_bytes"]),
            "--expected-selection-sha256",
            str(selection_identity["sha256"]),
            "--qualification-receipt",
            str(qualified["receipt_path"]),
            "--evidence",
            str(evidence_path),
            "--output",
            str(output),
        ]
    )
    record = json.loads(output.read_bytes())
    assert code == 2
    assert "error" not in record
    assert record["status"] == "CREDIBILITY_INCOMPLETE"
    assert record["reason"] == "resource_authority_missing"
    assert record["missing_gates"] == list(GATE.COMMON_MISSING_GATES)


@pytest.mark.parametrize("kind", ["tool", "input"])
def test_selection_bound_tool_and_input_drift_fail_closed(tmp_path: Path, kind: str) -> None:
    qualified = _qualified(tmp_path)
    selection = _historical_selection(qualified)
    selection_path = tmp_path / "selection/historical.json"
    selection_path.parent.mkdir()
    selection_identity = GATE.write_launch_selection(selection_path, selection)
    role = "checker" if kind == "tool" else "mandatory"
    qualified["paths"][role].write_bytes(qualified["paths"][role].read_bytes() + b"\n")
    result = _historical_result(qualified, selection, selection_identity)
    assert result["classification_complete"] is False
    assert f"{kind}_identity_drift" in result["missing_gates"]


def _future_evidence(
    tmp_path: Path,
    qualified: dict[str, Any],
    selection: dict[str, object],
    selection_identity: dict[str, object],
) -> dict[str, object]:
    arms: dict[str, dict[str, object]] = {}
    model: dict[str, dict[str, object]] = {}
    response: dict[str, dict[str, object]] = {}
    inner: dict[str, dict[str, object]] = {}
    terminal: dict[str, dict[str, object]] = {}
    selected_arms = selection["arms"]
    assert isinstance(selected_arms, dict)
    for label in ("control", "treatment"):
        selected = selected_arms[label]
        attempt = Path(str(selected["attempt_dir"]))
        attempt.mkdir(parents=True)
        result_path = attempt / "result.json"
        _write_json(result_path, {"arm": label, "status": "ARM_COMPLETE"})
        model_path = attempt / "model.bin"
        response_path = attempt / "response.bin"
        model_path.write_bytes(f"model-{label}".encode())
        response_path.write_bytes(f"response-{label}".encode())
        result_identity = _identity(result_path)
        model_identity = _identity(model_path)
        response_identity = _identity(response_path)
        model[label] = model_identity
        response[label] = response_identity
        arms[label] = {
            "launch_selection": {
                "arm": label,
                "attempt_dir": str(attempt),
                "package_id": selection["package_id"],
                "run_nonce": selection["run_nonce"],
                "selection_id": selection["selection_id"],
                "selection_identity": selection_identity,
                "unit_name": selected["unit_name"],
            },
            "model_binary_identity": model_identity,
            "response_binary_identity": response_identity,
            "result_identity": result_identity,
        }
        inner[label] = {"arm_result_identity": result_identity, "status": "PASS"}
        terminal[label] = {"arm_result_identity": result_identity, "status": "PASS"}
    return {
        "arm_results": arms,
        "inner_raw_results": inner,
        "model_binary_identities": model,
        "response_binary_identities": response,
        "terminal_envelopes": terminal,
    }


@pytest.mark.parametrize(
    ("treatment_status", "expected_status", "advance"),
    [
        ("PASS_APPLIED_VIOLATION", "INJECTED_MECHANISM_POSITIVE_CONTROL", True),
        ("NO_APPLIED_CUT", "POSITIVE_CONTROL_NEGATIVE", False),
    ],
)
def test_future_complete_classification_requires_prospective_pair_and_all_binary_gates(
    tmp_path: Path,
    treatment_status: str,
    expected_status: str,
    advance: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualified = _qualified(tmp_path)
    arms = _paired_arms(tmp_path)
    selection = GATE.make_paired_selection(
        package_id=str(qualified["build"]["package_id"]),
        run_nonce=NONCE,
        created_at_utc="2026-07-23T00:00:00Z",
        repository_head=HEAD,
        qualification_receipt_identity=qualified["receipt_identity"],
        tools=qualified["tools"],
        inputs=qualified["inputs"],
        arms=arms,
        terminal_observer_tool_role="observer",
    )
    selection_path = tmp_path / "selection/paired.json"
    selection_path.parent.mkdir()
    selection_identity = GATE.write_launch_selection(selection_path, selection)
    evidence = _future_evidence(tmp_path, qualified, selection, selection_identity)
    resource_report = {
        "arms": {
            label: {"result_identity": evidence["arm_results"][label]["result_identity"]}
            for label in ("control", "treatment")
        },
        "claim": "resource_evidence_only",
        "contract": {},
        "receipt_id": "a" * 64,
        "receipt_identity": {},
        "run_nonce": NONCE,
        "schema_version": GATE.RESOURCE_VERIFICATION_SCHEMA,
        "selection_identity": selection_identity,
        "status": "PASS",
    }

    def replay_resource(*_args: object, **_kwargs: object) -> dict[str, object]:
        return resource_report

    def replay_arm(manifest: Mapping[str, object], _selection: Mapping[str, object]) -> dict[str, object]:
        label = str(manifest["arm"])
        counts = (
            {"generated": 0, "compiled": 0, "applied": 0}
            if label == "control" or treatment_status == "NO_APPLIED_CUT"
            else {"generated": 1, "compiled": 1, "applied": 1}
        )
        return {
            "arm_result": {"launch_selection": evidence["arm_results"][label]["launch_selection"]},
            "counts": counts,
            "exact_environment": {"PAIR": "same"},
            "ledger_identity": _identity(Path(evidence["arm_results"][label]["result_identity"]["path"])),
            "model_binary_identity": evidence["model_binary_identities"][label],
            "response_binary_identity": evidence["response_binary_identities"][label],
            "result_identity": evidence["arm_results"][label]["result_identity"],
        }

    monkeypatch.setattr(GATE, "_resource_replay", replay_resource)
    monkeypatch.setattr(GATE, "_arm_replay", replay_arm)
    monkeypatch.setattr(
        GATE,
        "_checker_positive_replay",
        lambda *_args: {
            "checker": "independent_arithmetic_check_v3",
            "schema_version": 3,
            "status": "PASS_APPLIED_VIOLATION",
        },
    )
    semantic_replay = GATE._replay_exact_path_manifest(
        {
            "arms": {
                "control": {"arm": "control"},
                "treatment": {"arm": "treatment"},
            },
            "positive_treatment": ({"fixture": "path"} if treatment_status == "PASS_APPLIED_VIOLATION" else None),
            "resource": {"fixture": "path"},
            "schema": GATE.EVIDENCE_PATHS_SCHEMA,
        },
        selection,
        selection_path,
    )
    result = GATE.evaluate_gate(
        selection=selection,
        selection_identity=selection_identity,
        expected_selection_identity=selection_identity,
        qualification_receipt=qualified["receipt"],
        qualification_receipt_identity=qualified["receipt_identity"],
        semantic_replay=semantic_replay,
        **evidence,
    )
    assert result["missing_gates"] == []
    assert result["classification_complete"] is True
    assert result["experiment_verdict"] is True
    assert result["status"] == expected_status
    assert result["advance_authorized"] is advance
    assert GATE.exit_code(result) == 0

    caller_claimed_pass = GATE.evaluate_gate(
        selection=selection,
        selection_identity=selection_identity,
        expected_selection_identity=selection_identity,
        qualification_receipt=qualified["receipt"],
        qualification_receipt_identity=qualified["receipt_identity"],
        semantic_replay={
            "checker_classification": expected_status,
            "resource_report": {
                "arms": {},
                "claim": "resource_evidence_only",
                "status": "PASS",
            },
        },
        **evidence,
    )
    assert caller_claimed_pass["classification_complete"] is False
    assert caller_claimed_pass["semantic_replay_gate_owned"] is False
    assert "resource_authority_missing" in caller_claimed_pass["missing_gates"]
    assert "checker_semantics_missing" in caller_claimed_pass["missing_gates"]


@pytest.mark.parametrize(
    "mutation",
    ["manifest", "seal", "partial_seal", "extra_member", "symlink"],
)
def test_manifest_seal_extra_member_and_symlink_canaries_fail_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    specs, _paths = _sources(tmp_path)
    run = tmp_path / "qualification"
    BUILDER.build_package(run, specs, repository_head=HEAD, run_nonce=NONCE)
    package = run / "package"
    if mutation == "manifest":
        manifest = package / "package-manifest.json"
        manifest.write_bytes(manifest.read_bytes().replace(BUILDER.PACKAGE_SCHEMA.encode(), b"tampered", 1))
    elif mutation == "seal":
        seal = package / "SHA256SUMS"
        seal.write_bytes(seal.read_bytes().replace(b"a", b"b", 1))
    elif mutation == "partial_seal":
        seal = package / "SHA256SUMS"
        seal.write_bytes(b"\n".join(seal.read_bytes().splitlines()[:-1]) + b"\n")
    elif mutation == "extra_member":
        (package / "payload/extra").write_bytes(b"extra")
    elif mutation == "symlink":
        (package / "payload/link").symlink_to(package / "payload/checker")
    result = VERIFIER.verify_package(run, verification_id=f"canary-{mutation}")
    assert result["status"] == "FAIL"
    assert result["corpus_errors"]


def test_single_fd_snapshot_detects_path_inode_toctou_in_builder_and_verifier(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"old")

    def replace(path: Path) -> None:
        replacement = path.with_suffix(".replacement")
        replacement.write_bytes(b"new")
        replacement.replace(path)

    with pytest.raises(
        BUILDER.QualificationBuildError,
        match="changed during descriptor read|inode changed",
    ):
        BUILDER.snapshot_regular(source, after_read=replace)

    source.write_bytes(b"old-again")
    with pytest.raises(
        VERIFIER.QualificationVerificationError,
        match="changed during descriptor read|inode changed",
    ):
        VERIFIER.snapshot_regular(source, after_read=replace)


def test_gate_snapshot_rejects_same_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "gate-input.json"
    source.write_bytes(b'{"stable":true}\n')
    real_read = GATE.os.read
    swapped = False

    def swapping_read(fd: int, count: int) -> bytes:
        nonlocal swapped
        chunk = real_read(fd, count)
        if chunk and not swapped:
            replacement = source.with_suffix(".replacement")
            replacement.write_bytes(b'{"stable":false}\n')
            replacement.replace(source)
            swapped = True
        return chunk

    monkeypatch.setattr(GATE.os, "read", swapping_read)
    with pytest.raises(
        GATE.GateV3Error,
        match=r"(input changed during read|path inode changed)",
    ):
        GATE._snapshot_regular(source)


def test_source_symlink_and_output_collisions_are_rejected(tmp_path: Path) -> None:
    specs, paths = _sources(tmp_path)
    link = tmp_path / "sources/checker-link"
    link.symlink_to(paths["checker"])
    with pytest.raises(BUILDER.QualificationBuildError, match="symlink"):
        BUILDER.build_package(
            tmp_path / "symlink-run",
            [BUILDER.SourceSpec(role="checker", path=link)],
            repository_head=HEAD,
            run_nonce=NONCE,
        )

    run = tmp_path / "qualification"
    BUILDER.build_package(run, specs, repository_head=HEAD, run_nonce=NONCE)
    with pytest.raises(BUILDER.QualificationBuildError, match="already exists"):
        BUILDER.build_package(run, specs, repository_head=HEAD, run_nonce=NONCE)
    VERIFIER.create_pass_receipt(run, "verification-a001")
    with pytest.raises(VERIFIER.QualificationVerificationError, match="already exists"):
        VERIFIER.create_pass_receipt(run, "verification-a001")
