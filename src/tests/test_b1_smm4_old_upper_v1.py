from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType
from typing import Any

import pytest

from src.tests.track_b_archive_locator_v1 import resolve_archive_roots


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727"
ARCHIVE_ROOTS = resolve_archive_roots("track_b_b0_1190_20260721")
B0 = ARCHIVE_ROOTS["track_b_b0_1190_20260721"]
OLD_FORMAL = (
    B0
    / ".artifacts/track_b_b1_r4_1188_22_pb_20260723"
    / "formal-a001-20260723T091800Z-398f8725"
)
VERIPB = Path("/home/zhuran24/.cargo/bin/veripb")


def load_verifier() -> ModuleType:
    sys.path.insert(0, str(RESEARCH))
    path = RESEARCH / "verify_smm4_old_upper_v1.py"
    spec = importlib.util.spec_from_file_location("_test_smm4_old_upper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verifier() -> ModuleType:
    return load_verifier()


def historical_sources(verifier: ModuleType) -> dict[str, Path]:
    sources = {
        "old_r4_receipt": OLD_FORMAL / "authority_receipt.json",
        "old_r4_toolchain_record": OLD_FORMAL / "toolchain_record.json",
        "old_r4_raw_manifest": OLD_FORMAL / "SHA256SUMS",
        "old_r4_a004_admission": (
            B0
            / ".artifacts/track_b_r4_external_brain_handoff_20260722"
            / "responses/run-20260723T023657Z-R4resp-357f260d"
            / "admission/a004/admission.json"
        ),
        "strict_instance": (
            B0
            / "docs/research/cleanroom_rederivation_20260718"
            / "strict/external/problem_instance.json"
        ),
    }
    for filename, key in verifier.FORMAL_MEMBER_KEYS.items():
        sources[key] = OLD_FORMAL / filename
    return sources


@pytest.fixture(scope="module")
def fresh_history(
    verifier: ModuleType,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    sources = historical_sources(verifier)
    missing_history = [str(path) for path in sources.values() if not path.is_file()]
    if missing_history:
        pytest.fail(f"SMM4 immutable archive history is unavailable: {missing_history}", pytrace=False)
    if not VERIPB.is_file():
        pytest.fail(f"local VeriPB tool is unavailable: {VERIPB}", pytrace=False)
    root = tmp_path_factory.mktemp("smm4-old-upper-fresh")
    paths: dict[str, Path] = {}
    pins: dict[str, dict[str, Any]] = {}
    for index, name in enumerate(verifier.REQUIRED_INPUT_KEYS):
        output = root / f"{index:02d}-{name}.snapshot"
        shutil.copyfile(sources[name], output)
        output.chmod(int(verifier.CONTENT_ANCHORS[name]["mode_octal"], 8))
        _, identity = verifier.snapshot_regular(output, name)
        paths[name] = output
        pins[name] = {
            "identity": identity,
            "content_projection": verifier.canonical_content_projection(identity, name),
        }
    _, veripb_identity = verifier.snapshot_regular(VERIPB, "veripb")
    return {
        "root": root,
        "source_paths": sources,
        "paths": paths,
        "pins": pins,
        "veripb_identity": veripb_identity,
    }


def successful_veripb_result() -> dict[str, Any]:
    return {
        "exit_code": 0,
        "stdout": "s VERIFIED UNSATISFIABLE\n",
        "stderr": "",
        "status_lines": ["s VERIFIED UNSATISFIABLE"],
        "proof_status": "VERIFIED UNSATISFIABLE",
        "argv_shape": [
            "retained_veripb_fd",
            "--opb",
            "--stats",
            "retained_formula_fd",
            "retained_proof_fd",
        ],
        "execution": "retained_proc_self_fd_with_pass_fds",
    }


def test_independent_reconstruction_is_exact_2084_by_2192(verifier: ModuleType) -> None:
    strict_path = (
        ROOT
        / "docs/research/cleanroom_rederivation_20260718"
        / "strict/external/problem_instance.json"
    )
    payload = verifier.strict_json(strict_path.read_bytes(), "strict instance")
    reconstructed = verifier.reconstruct_old_model(payload)
    report = reconstructed["report"]
    assert report["complete_oriented_band_count"] == 2084
    assert report["selector_variables"] == 2084
    assert report["constraints"] == 2192
    assert report["full_span_forbid_constraints"] == 107
    assert report["arithmetic_survivors"] == [[17, 70], [70, 17]]
    assert report["final_survivors"] == []
    assert report["formula_sha256"] == verifier.CONTENT_ANCHORS[
        verifier.member_key("formula.opb")
    ]["sha256"]
    assert report["variable_map_sha256"] == verifier.CONTENT_ANCHORS[
        verifier.member_key("variable_map.json")
    ]["sha256"]
    assert report["conditional_on_frozen_a004_lemmas"] is True


def test_manifest_parser_requires_exact_order_set_and_syntax(verifier: ModuleType) -> None:
    manifest = "".join(
        f"{verifier.CONTENT_ANCHORS[verifier.FORMAL_MEMBER_KEYS[name]]['sha256']}  {name}\n"
        for name in verifier.FORMAL_MANIFEST_MEMBERS
    ).encode()
    entries = verifier.parse_sha256_manifest(
        manifest,
        verifier.FORMAL_MANIFEST_MEMBERS,
        "formal manifest",
    )
    assert tuple(entries) == verifier.FORMAL_MANIFEST_MEMBERS
    with pytest.raises(verifier.OldUpperVerificationError, match="ordered member set"):
        verifier.parse_sha256_manifest(
            b"".join(reversed(manifest.splitlines(keepends=True))),
            verifier.FORMAL_MANIFEST_MEMBERS,
            "formal manifest",
        )
    with pytest.raises(verifier.OldUpperVerificationError):
        verifier.parse_sha256_manifest(
            manifest.replace(b"  formula.opb\n", b" *formula.opb\n"),
            verifier.FORMAL_MANIFEST_MEMBERS,
            "formal manifest",
        )
    with pytest.raises(verifier.OldUpperVerificationError, match="terminal newline"):
        verifier.parse_sha256_manifest(
            manifest.rstrip(b"\n"),
            verifier.FORMAL_MANIFEST_MEMBERS,
            "formal manifest",
        )


def test_veripb_status_must_be_the_one_exact_terminal_line(verifier: ModuleType) -> None:
    result = verifier.parse_veripb_output(
        b"diagnostic\ns VERIFIED UNSATISFIABLE\n",
        b"",
        0,
    )
    assert result["proof_status"] == "VERIFIED UNSATISFIABLE"
    for stdout, stderr, returncode in (
        (b"s UNSATISFIABLE\n", b"", 0),
        (b"s VERIFIED UNSATISFIABLE\ns SATISFIABLE\n", b"", 0),
        (b"s VERIFIED UNSATISFIABLE\n", b"warning\n", 0),
        (b"s VERIFIED UNSATISFIABLE\n", b"", 1),
    ):
        with pytest.raises(verifier.OldUpperVerificationError):
            verifier.parse_veripb_output(stdout, stderr, returncode)


def test_retained_fd_executor_uses_proc_self_fd_and_pass_fds(
    verifier: ModuleType,
    tmp_path: Path,
) -> None:
    executable = tmp_path / "fake-veripb"
    executable.write_text("#!/bin/sh\nprintf 's VERIFIED UNSATISFIABLE\\n'\n")
    executable.chmod(0o755)
    formula = tmp_path / "formula.opb"
    proof = tmp_path / "proof.pbp"
    formula.write_bytes(b"* #variable= 0 #constraint= 0\n")
    proof.write_bytes(b"pseudo-Boolean proof version 2.0\n")
    fds = [
        os.open(executable, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)),
        os.open(formula, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)),
        os.open(proof, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)),
    ]
    try:
        result = verifier._execute_veripb(*fds, 10)
    finally:
        for fd in fds:
            os.close(fd)
    assert result["proof_status"] == "VERIFIED UNSATISFIABLE"
    assert result["execution"] == "retained_proc_self_fd_with_pass_fds"
    assert result["argv_shape"] == [
        "retained_veripb_fd",
        "--opb",
        "--stats",
        "retained_formula_fd",
        "retained_proof_fd",
    ]


def test_full_fresh_snapshot_recovery_is_conditional_and_never_authorizes_update(
    verifier: ModuleType,
    fresh_history: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_execute(veripb_fd: int, formula_fd: int, proof_fd: int, timeout: int) -> dict[str, Any]:
        observed["fds"] = (veripb_fd, formula_fd, proof_fd)
        observed["timeout"] = timeout
        assert all(Path(f"/proc/self/fd/{fd}").exists() for fd in observed["fds"])
        return successful_veripb_result()

    monkeypatch.setattr(verifier, "_execute_veripb", fake_execute)
    report = verifier.verify_old_upper(
        fresh_history["paths"],
        fresh_history["pins"],
        VERIPB,
        fresh_history["veripb_identity"],
        verifier_timeout_seconds=17,
    )
    assert report["status"] == "PASS"
    assert report["decision"] == "OLD_R4_COMPLETE_BAND_AUTHORITY_RECOVERED_FROM_FRESH_SNAPSHOTS"
    assert report["upper_bound_update_authorized"] is False
    assert report["receipt_and_manifest_graph"]["historical_receipt_upper_bound_update_authorized"] is True
    assert report["independent_reconstruction"]["complete_oriented_band_count"] == 2084
    assert report["detached_veripb"]["proof_status"] == "VERIFIED UNSATISFIABLE"
    assert report["claim_boundary"]["ledger_upper_remains"] == [1188, 22]
    assert report["claim_boundary"]["lower_remains"] == "absent"
    assert report["claim_boundary"]["attainability"] is False
    assert report["claim_boundary"]["optimality"] is False
    assert report["claim_boundary"]["whole_instance_infeasibility"] is False
    assert report["claim_boundary"]["production_certified"] is False
    assert observed["timeout"] == 17
    fresh_root = str(fresh_history["root"])
    assert all(value["identity"]["path"].startswith(fresh_root + os.sep) for value in report["inputs"].values())
    old_paths = {str(path) for path in fresh_history["source_paths"].values()}
    assert all(value["identity"]["path"] not in old_paths for value in report["inputs"].values())


@pytest.mark.parametrize(
    "mutation",
    (
        "identity_extra",
        "projection_missing",
        "projection_hash_drift",
        "identity_path_drift",
        "top_level_extra",
    ),
)
def test_snapshot_pin_schema_and_join_fail_closed(
    verifier: ModuleType,
    fresh_history: dict[str, Any],
    mutation: str,
) -> None:
    pins = copy.deepcopy(fresh_history["pins"])
    target = pins[verifier.member_key("formula.opb")]
    if mutation == "identity_extra":
        target["identity"]["ignored"] = True
    elif mutation == "projection_missing":
        del target["content_projection"]["mode_octal"]
    elif mutation == "projection_hash_drift":
        target["content_projection"]["sha256"] = "0" * 64
    elif mutation == "identity_path_drift":
        target["identity"]["path"] += ".alias"
    else:
        target["unexpected"] = True
    with pytest.raises((verifier.IdentityContractError, verifier.OldUpperVerificationError)):
        verifier.verify_old_upper(
            fresh_history["paths"],
            pins,
            VERIPB,
            fresh_history["veripb_identity"],
        )


def test_self_consistent_replacement_pin_cannot_replace_historical_anchor(
    verifier: ModuleType,
    fresh_history: dict[str, Any],
    tmp_path: Path,
) -> None:
    paths = dict(fresh_history["paths"])
    pins = copy.deepcopy(fresh_history["pins"])
    name = verifier.member_key("formula.opb")
    changed = tmp_path / "changed-formula.snapshot"
    changed.write_bytes(paths[name].read_bytes() + b"* unauthorized replacement\n")
    changed.chmod(0o644)
    _, identity = verifier.snapshot_regular(changed, "changed formula")
    paths[name] = changed
    pins[name] = {
        "identity": identity,
        "content_projection": verifier.canonical_content_projection(identity, "changed formula"),
    }
    with pytest.raises(verifier.OldUpperVerificationError, match="immutable content anchor"):
        verifier.verify_old_upper(
            paths,
            pins,
            VERIPB,
            fresh_history["veripb_identity"],
        )
