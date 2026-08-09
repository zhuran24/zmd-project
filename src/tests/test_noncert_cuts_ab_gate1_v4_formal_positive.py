from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
import stat
from pathlib import Path
from typing import Any, Callable

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab_trust_gate1_v4_20260724"
PACKAGE_HEAD = "1" * 40
EXECUTION_HEAD = "2" * 40


def _load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FORMAL = _load(
    "noncert_cuts_gate1_v4_formal_positive",
    "positive_control_formal_v4.py",
)
CHECKER = _load(
    "noncert_cuts_gate1_v4_formal_arithmetic",
    "independent_arithmetic_v4.py",
)


def _packaged_checker(tmp_path: Path) -> Any:
    source_path = RESEARCH / "independent_arithmetic_v4.py"
    source_raw = source_path.read_bytes()
    package_dir = tmp_path / "checker-package"
    checker_path = package_dir / "payload" / "tool.independent_arithmetic_v4.py"
    checker_path.parent.mkdir(parents=True)
    checker_path.write_bytes(source_raw)
    source_stat = source_path.stat()
    source_mode = stat.S_IMODE(source_stat.st_mode)
    checker_digest = hashlib.sha256(source_raw).hexdigest()
    manifest = {
        "authorization_semantics": "byte qualification only; package PASS cannot launch any child",
        "external_sources": [
            {
                "package_path": "payload/tool.independent_arithmetic_v4.py",
                "parse_json": False,
                "role": "tool.independent_arithmetic_v4.py",
                "source_identity": {
                    "device": source_stat.st_dev,
                    "inode": source_stat.st_ino,
                    "mode": source_mode,
                    "mode_octal": f"{source_mode:04o}",
                    "path": str(source_path),
                    "sha256": checker_digest,
                    "size_bytes": len(source_raw),
                },
            }
        ],
        "manager_epoch": {"fixture": "sealed-checker-birth"},
        "package_members": [
            {
                "path": "payload/tool.independent_arithmetic_v4.py",
                "sha256": checker_digest,
                "size_bytes": len(source_raw),
            }
        ],
        "repository_head": PACKAGE_HEAD,
        "run_nonce": "formal-checker-package-fixture",
        "schema": CHECKER.PACKAGE_MANIFEST_SCHEMA,
        "seal_contract": {
            "package_id": "sha256(SHA256SUMS exact bytes)",
            "sha256sums_domain": "all regular files below package except SHA256SUMS",
            "writes_after_seal": "forbidden",
        },
    }
    manifest_raw = CHECKER.canonical_json(manifest) + b"\n"
    manifest_path = package_dir / "package-manifest.json"
    manifest_path.write_bytes(manifest_raw)
    seal_raw = (
        f"{hashlib.sha256(manifest_raw).hexdigest()}  package-manifest.json\n"
        f"{checker_digest}  payload/tool.independent_arithmetic_v4.py\n"
    ).encode("ascii")
    (package_dir / "SHA256SUMS").write_bytes(seal_raw)
    return _load(
        f"noncert_cuts_gate1_v4_packaged_arithmetic_{tmp_path.name}",
        str(checker_path),
    )


def _selection(
    root: Path,
    *,
    profile: str = FORMAL.FORMAL_PROFILE,
    purpose: str | None = None,
    repository_head: str = EXECUTION_HEAD,
) -> None:
    root.mkdir()
    if profile == FORMAL.FORMAL_PROFILE:
        schema = FORMAL.FORMAL_SELECTION_SCHEMA
        selected_purpose = purpose or FORMAL.FORMAL_PURPOSE
        formal_eligible = True
    elif profile == FORMAL.PRODUCTION_DRILL_PROFILE:
        schema = FORMAL.PRODUCTION_DRILL_SELECTION_SCHEMA
        selected_purpose = purpose or FORMAL.PRODUCTION_DRILL_PURPOSE
        formal_eligible = False
    else:
        raise AssertionError(f"unknown fixture profile: {profile}")
    FORMAL._SUPPORT._write_json_exclusive(  # noqa: SLF001
        root / "selection.json",
        {
            "schema": schema,
            "purpose": selected_purpose,
            "campaign_id": "disposable-gate1-v4-formal-schema-drill",
            "run_nonce": "disposable-run-nonce",
            "manager_epoch_digest": "disposable-manager-epoch",
            "gate1_formal_eligible": formal_eligible,
            "repository_head": repository_head,
        },
    )


def test_genuine_production_f1_pair_passes_formal_checker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    root = tmp_path / "pair"
    _selection(root)

    result = FORMAL.build_formal_positive_pair(
        root,
        export_dir=tmp_path / "exports",
        solve_seconds=3.0,
    )
    packaged_checker = _packaged_checker(tmp_path)
    assert list(inspect.signature(packaged_checker.verify_formal_bundle).parameters) == ["bundle"]
    receipt = packaged_checker.verify_formal_bundle(CHECKER.load_fixture(root))
    with pytest.raises(ValueError, match="disposable production drill selection"):
        CHECKER.verify_production_drill_bundle(CHECKER.load_fixture(root))

    assert receipt["status"] == "PASS_FORMAL_MECHANISM_POSITIVE_CONTROL"
    assert receipt["repository_head"] == PACKAGE_HEAD
    assert receipt["repository_head"] != EXECUTION_HEAD
    assert receipt["control"] == {"generated": 0, "compiled": 0, "applied": 0}
    assert receipt["treatment"] == {
        "generated": 1,
        "compiled": 1,
        "applied": 1,
    }
    assert receipt["selected"]["lhs"] == FORMAL.MANDATORY_COUNT
    assert receipt["selected"]["rhs"] == FORMAL.EXPECTED_CAPACITY
    assert receipt["selected"]["active"] is True
    assert receipt["selected"]["violated"] is True
    assert result["post_attach_solve_performed"] is False
    assert not (root / "arms" / "treatment" / "post-injection-response.pb").exists()

    treatment_ledger = (root / "arms" / "treatment" / "ledger.jsonl").read_bytes()
    assert b'"event":"GENERATED"' in treatment_ledger
    assert b'"event":"APPLIED"' in treatment_ledger
    assert b'"trigger":"binding_infeasible"' in treatment_ledger
    assert b'"count_delta":1' in treatment_ledger


def test_disposable_production_pair_uses_strict_nonformal_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    root = tmp_path / "pair"
    _selection(root, profile=FORMAL.PRODUCTION_DRILL_PROFILE)

    result = FORMAL.build_disposable_positive_pair(
        root,
        export_dir=tmp_path / "exports",
        solve_seconds=3.0,
    )
    bundle = CHECKER.load_fixture(root)
    receipt = CHECKER.verify_production_drill_bundle(bundle)

    assert receipt["schema"] == CHECKER.PRODUCTION_DRILL_RECEIPT_SCHEMA
    assert receipt["status"] == "PASS_DISPOSABLE_PRODUCTION_MECHANISM_POSITIVE_CONTROL"
    assert receipt["profile"] == FORMAL.PRODUCTION_DRILL_PROFILE
    assert receipt["formal_eligible"] is False
    assert receipt["control"] == {"generated": 0, "compiled": 0, "applied": 0}
    assert receipt["treatment"] == {"generated": 1, "compiled": 1, "applied": 1}
    assert receipt["selected"]["lhs"] == FORMAL.MANDATORY_COUNT
    assert receipt["selected"]["rhs"] == FORMAL.EXPECTED_CAPACITY
    assert result["post_attach_solve_performed"] is False
    packaged_checker = _packaged_checker(tmp_path)
    with pytest.raises(ValueError, match="formal campaign selection"):
        packaged_checker.verify_formal_bundle(bundle)


def test_common_and_both_bindings_are_sealed_before_per_arm_callbacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    root = tmp_path / "pair"
    _selection(root)
    (tmp_path / "exports").mkdir()
    prepared = FORMAL.prepare_formal_positive_common(
        root,
        export_dir=tmp_path / "exports/common",
        solve_seconds=3.0,
    )

    assert prepared["claim_boundary"] == "common_prestate_and_bindings_only"
    assert (root / "common-prestate/manifest.json").is_file()
    assert (root / "bindings/control.json").is_file()
    assert (root / "bindings/treatment.json").is_file()
    assert (root / "bindings/bindings-seal.json").is_file()
    assert not (root / "arms").exists()

    control = FORMAL.materialize_formal_positive_arm(
        root,
        arm="control",
        export_dir=tmp_path / "exports/control",
    )
    assert control["injection"] == {
        "enabled": False,
        "provider": "empty_control_provider",
        "generated": 0,
        "compiled": 0,
        "applied": 0,
        "compiled_records": [],
    }
    assert not (root / "arms/treatment").exists()
    treatment = FORMAL.materialize_formal_positive_arm(
        root,
        arm="treatment",
        export_dir=tmp_path / "exports/treatment",
    )
    assert treatment["injection"]["generated"] == 1
    assert treatment["injection"]["compiled"] == 1
    assert treatment["injection"]["applied"] == 1
    packaged_checker = _packaged_checker(tmp_path)
    assert (
        packaged_checker.verify_formal_bundle(CHECKER.load_fixture(root))["status"]
        == "PASS_FORMAL_MECHANISM_POSITIVE_CONTROL"
    )


def test_selected_per_arm_entrypoint_requires_selected_support_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    root = tmp_path / "pair"
    manager_epoch = {"fixture": "epoch"}
    manager_digest = hashlib.sha256(FORMAL.canonical_json(manager_epoch) + b"\n").hexdigest()
    root.mkdir()
    FORMAL._SUPPORT._write_json_exclusive(  # noqa: SLF001
        root / "selection.json",
        {
            "schema": FORMAL.FORMAL_SELECTION_SCHEMA,
            "purpose": FORMAL.FORMAL_PURPOSE,
            "campaign_id": "campaign",
            "run_nonce": "nonce",
            "manager_epoch_digest": manager_digest,
            "gate1_formal_eligible": True,
            "repository_head": EXECUTION_HEAD,
        },
    )
    (root / "builder-exports").mkdir()
    FORMAL.prepare_formal_positive_common(
        root,
        export_dir=root / "builder-exports/common",
        solve_seconds=3.0,
    )
    formal_identity = {
        "path": str(RESEARCH / "positive_control_formal_v4.py"),
        "size_bytes": 1,
        "sha256": "1" * 64,
    }
    support_identity = {
        "path": str(RESEARCH / "positive_control_v4.py"),
        "size_bytes": 2,
        "sha256": "2" * 64,
    }
    campaign_root = {
        "campaign_id": "campaign",
        "run_nonce": "nonce",
        "manager_epoch": manager_epoch,
        "stage_topology": {
            "gate1_v4": {
                "positive_control": {
                    "root_dir": str(root),
                    "arm_dirs": {
                        "control": str(root / "arms/control"),
                        "treatment": str(root / "arms/treatment"),
                    },
                    "builder_export_dirs": {
                        arm: str(root / "builder-exports" / arm) for arm in ("common", "control", "treatment")
                    },
                }
            }
        },
    }
    selection = {
        "tools": {
            "positive_control_formal_v4": formal_identity,
            "positive_control_v4": support_identity,
        }
    }
    monkeypatch.setattr(FORMAL, "_SUPPORT_SELECTED_IDENTITY", None)
    with pytest.raises(ValueError, match="toolchain identity"):
        FORMAL.run_forced_payload_v4(
            campaign_root=campaign_root,
            campaign_root_identity={
                "path": str(tmp_path / "run-formal-test/campaign-root.json"),
            },
            selection=selection,
            selection_identity={},
            unit_slot="forced-control",
            selected_tool_identity=formal_identity,
        )
    monkeypatch.setattr(
        FORMAL,
        "_SUPPORT_SELECTED_IDENTITY",
        copy.deepcopy(support_identity),
    )
    result = FORMAL.run_forced_payload_v4(
        campaign_root=campaign_root,
        campaign_root_identity={
            "path": str(tmp_path / "run-formal-test/campaign-root.json"),
        },
        selection=selection,
        selection_identity={},
        unit_slot="forced-control",
        selected_tool_identity=formal_identity,
    )
    assert result["profile"] == FORMAL.FORMAL_PROFILE
    assert result["arm"] == "control"
    assert result["support_tool_identity"] == support_identity
    assert result["generated"] == result["compiled"] == result["applied"] == 0


def _rechain_formal_ledger(
    path: Path,
    mutate: Callable[[list[dict[str, object]]], None],
) -> None:
    events = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(events)
    previous = "0" * 64
    lines: list[bytes] = []
    for sequence, event in enumerate(events):
        event["seq"] = sequence
        event["prev_event_hash"] = previous
        raw = CHECKER.canonical_json(event)
        lines.append(raw)
        previous = hashlib.sha256(raw).hexdigest()
    path.write_bytes(b"\n".join(lines) + b"\n")
    evidence_path = path.parent / "evidence.json"
    evidence = json.loads(evidence_path.read_bytes())
    evidence["ledger_identity"] = {
        "path": str(path.absolute()),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    evidence["ledger"] = {
        "event_count": len(lines),
        "tail_hash": previous,
    }
    evidence_path.write_bytes(CHECKER.canonical_json(evidence) + b"\n")


@pytest.mark.parametrize("field", ["trigger", "iteration"])
def test_formal_checker_rejects_self_consistent_production_ledger_field_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    root = tmp_path / "pair"
    _selection(root)
    FORMAL.build_formal_positive_pair(
        root,
        export_dir=tmp_path / "exports",
        solve_seconds=3.0,
    )

    def mutate(events: list[dict[str, object]]) -> None:
        value: object
        if field == "trigger":
            value = "routing_exhausted"
        elif field == "iteration":
            value = 1002
        events[1][field] = value
        events[2][field] = value

    _rechain_formal_ledger(
        root / "arms/treatment/ledger.jsonl",
        mutate,
    )
    packaged_checker = _packaged_checker(tmp_path)
    with pytest.raises(ValueError, match="formal GENERATED"):
        packaged_checker.verify_formal_bundle(CHECKER.load_fixture(root))


def test_formal_checker_rejects_malformed_epoch_instance_even_with_valid_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    root = tmp_path / "pair"
    _selection(root)
    FORMAL.build_formal_positive_pair(
        root,
        export_dir=tmp_path / "exports",
        solve_seconds=3.0,
    )

    def mutate(events: list[dict[str, object]]) -> None:
        events[1]["epoch_instance_id"] = "epoch-forged"
        events[2]["epoch_instance_id"] = "epoch-forged"

    _rechain_formal_ledger(
        root / "arms/treatment/ledger.jsonl",
        mutate,
    )
    packaged_checker = _packaged_checker(tmp_path)
    with pytest.raises(ValueError, match="formal GENERATED"):
        packaged_checker.verify_formal_bundle(CHECKER.load_fixture(root))


def test_formal_pair_is_no_overwrite_and_preserves_first_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    root = tmp_path / "pair"
    exports = tmp_path / "exports"
    _selection(root)
    FORMAL.build_formal_positive_pair(root, export_dir=exports, solve_seconds=3.0)
    evidence = root / "arms" / "treatment" / "evidence.json"
    before = evidence.read_bytes()
    before_digest = hashlib.sha256(before).hexdigest()

    with pytest.raises(FileExistsError):
        FORMAL.build_formal_positive_pair(
            root,
            export_dir=exports,
            solve_seconds=3.0,
        )

    assert evidence.read_bytes() == before
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == before_digest


def test_wrong_purpose_fails_before_export_or_solver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    root = tmp_path / "pair"
    exports = tmp_path / "exports"
    _selection(root, purpose="gate1_v4_e2e_drill")

    with pytest.raises(ValueError, match="selection drifted"):
        FORMAL.build_formal_positive_pair(
            root,
            export_dir=exports,
            solve_seconds=3.0,
        )

    assert not exports.exists()
    assert not (root / "common-prestate").exists()


def test_formal_and_disposable_builders_reject_each_others_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH", raising=False)
    drill_root = tmp_path / "drill-pair"
    _selection(drill_root, profile=FORMAL.PRODUCTION_DRILL_PROFILE)
    with pytest.raises(ValueError, match="formal campaign positive selection"):
        FORMAL.prepare_formal_positive_common(
            drill_root,
            export_dir=tmp_path / "formal-on-drill",
            solve_seconds=3.0,
        )
    assert not (tmp_path / "formal-on-drill").exists()

    formal_root = tmp_path / "formal-pair"
    _selection(formal_root)
    with pytest.raises(
        ValueError,
        match="disposable production drill positive selection",
    ):
        FORMAL.prepare_disposable_positive_common(
            formal_root,
            export_dir=tmp_path / "drill-on-formal",
            solve_seconds=3.0,
        )
    assert not (tmp_path / "drill-on-formal").exists()


@pytest.mark.parametrize(
    ("parent", "expected"),
    [
        ("run-authority", FORMAL.FORMAL_PROFILE),
        ("dev-drill-authority", FORMAL.PRODUCTION_DRILL_PROFILE),
    ],
)
def test_campaign_root_parent_strictly_selects_payload_profile(
    tmp_path: Path,
    parent: str,
    expected: str,
) -> None:
    assert (
        FORMAL._campaign_profile(  # noqa: SLF001
            {"path": str(tmp_path / parent / "campaign-root.json")}
        )
        == expected
    )


@pytest.mark.parametrize(
    "path",
    [
        "campaign-root.json",
        "/tmp/campaign/campaign-root.json",
        "/tmp/run-/campaign-root.json",
        "/tmp/dev-drill-/campaign-root.json",
        "/tmp/run-ok/not-campaign-root.json",
    ],
)
def test_campaign_root_parent_rejects_ambiguous_payload_profile(
    path: str,
) -> None:
    with pytest.raises(ValueError, match="campaign root identity"):
        FORMAL._campaign_profile({"path": path})  # noqa: SLF001


def test_attach_must_be_absent_before_common_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pair"
    _selection(root)
    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH", "1")

    with pytest.raises(ValueError, match="absent"):
        FORMAL.build_formal_positive_pair(
            root,
            export_dir=tmp_path / "exports",
            solve_seconds=3.0,
        )

    assert not (root / "common-prestate").exists()
