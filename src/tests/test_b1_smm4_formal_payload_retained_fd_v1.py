from __future__ import annotations

import copy
import fcntl
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727"


def _load(filename: str) -> ModuleType:
    path = RESEARCH / filename
    spec = importlib.util.spec_from_file_location(f"_test_smm4_retained_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def payload() -> ModuleType:
    contract = _load("identity_contract_v1.py")
    module = _load("run_smm4_formal_payload_v1.py")
    module._activate_identity_contract(contract)
    return module


def _identity(payload: ModuleType, path: Path) -> dict[str, Any]:
    _, identity = payload.snapshot_regular(path.resolve(), path.name, collect=False)
    return identity


def _write_regular(path: Path, raw: bytes, *, mode: int = 0o644) -> Path:
    path.write_bytes(raw)
    path.chmod(mode)
    return path.resolve()


def _pin_executable(payload: ModuleType, path: Path) -> dict[str, Any]:
    _write_regular(path, b"#!/bin/sh\nexit 0\n", mode=0o755)
    return payload.pin_executable(_identity(payload, path), path.name)


@pytest.mark.parametrize(
    "mutation",
    ("missing", "extra", "path", "size", "hash", "mode", "device", "inode", "link_count"),
)
def test_retained_input_rejects_malformed_or_drifted_full_identity(
    payload: ModuleType,
    tmp_path: Path,
    mutation: str,
) -> None:
    source = _write_regular(tmp_path / "source.bin", b"authority-pinned-bytes")
    expected = _identity(payload, source)
    changed = copy.deepcopy(expected)
    if mutation == "missing":
        changed.pop("sha256")
    elif mutation == "extra":
        changed["extra"] = "forbidden"
    elif mutation == "path":
        alias = _write_regular(tmp_path / "other.bin", source.read_bytes())
        changed["path"] = str(alias)
    elif mutation == "size":
        changed["size_bytes"] += 1
    elif mutation == "hash":
        changed["sha256"] = "0" * 64
    elif mutation == "mode":
        changed["mode_octal"] = "0600" if expected["mode_octal"] != "0600" else "0644"
    elif mutation == "device":
        changed["device"] += 1
    elif mutation == "inode":
        changed["inode"] += 1
    else:
        changed["link_count"] = 2

    with pytest.raises(payload.PayloadError):
        payload.pin_retained_regular(changed, f"changed {mutation}")


@pytest.mark.parametrize("mutation", ("missing", "extra"))
def test_retained_record_requires_exact_internal_fields(
    payload: ModuleType,
    tmp_path: Path,
    mutation: str,
) -> None:
    source = _write_regular(tmp_path / "source.bin", b"fixed")
    _, retained = payload.pin_retained_regular(_identity(payload, source), "source")
    try:
        changed = dict(retained)
        if mutation == "missing":
            changed.pop("fd_path")
        else:
            changed["extra"] = False
        with pytest.raises(payload.PayloadError, match="exact retained-FD record key set"):
            payload.snapshot_retained_regular(changed, "changed")
    finally:
        payload.close_retained_regular(retained)


def test_retained_input_detects_same_inode_content_and_mode_drift(
    payload: ModuleType,
    tmp_path: Path,
) -> None:
    source = _write_regular(tmp_path / "source.bin", b"AAAA")
    expected = _identity(payload, source)
    _, retained = payload.pin_retained_regular(expected, "source")
    try:
        source.write_bytes(b"BBBB")
        with pytest.raises(payload.PayloadError, match="identity mismatch"):
            payload.verify_retained_unchanged(retained, expected, "source")

        source.write_bytes(b"AAAA")
        source.chmod(0o600)
        with pytest.raises(payload.PayloadError, match="anchor drifted|path binding drifted"):
            payload.verify_retained_unchanged(retained, expected, "source")
    finally:
        payload.close_retained_regular(retained)


def test_retained_input_detects_path_replacement_without_reopening_content(
    payload: ModuleType,
    tmp_path: Path,
) -> None:
    source = _write_regular(tmp_path / "source.bin", b"trusted")
    expected = _identity(payload, source)
    _, retained = payload.pin_retained_regular(expected, "source")
    try:
        moved = tmp_path / "moved.bin"
        source.rename(moved)
        _write_regular(source, b"hostile")
        assert os.pread(retained["fd"], len(b"trusted"), 0) == b"trusted"
        with pytest.raises(payload.PayloadError, match="path binding drifted"):
            payload.verify_retained_unchanged(retained, expected, "source")
    finally:
        payload.close_retained_regular(retained)


def test_retained_input_detects_new_hardlink(
    payload: ModuleType,
    tmp_path: Path,
) -> None:
    source = _write_regular(tmp_path / "source.bin", b"trusted")
    expected = _identity(payload, source)
    _, retained = payload.pin_retained_regular(expected, "source")
    try:
        os.link(source, tmp_path / "second-name.bin")
        with pytest.raises(payload.PayloadError, match="anchor drifted|path binding drifted"):
            payload.verify_retained_unchanged(retained, expected, "source")
    finally:
        payload.close_retained_regular(retained)


def test_proof_is_exclusive_read_write_retained_fd_and_same_fd_snapshot(
    payload: ModuleType,
    tmp_path: Path,
) -> None:
    proof_path = (tmp_path / "proof.pbp").resolve()
    proof = payload.create_retained_output(proof_path, "proof")
    try:
        flags = fcntl.fcntl(proof["fd"], fcntl.F_GETFL)
        assert flags & os.O_ACCMODE == os.O_RDWR
        assert proof["identity"]["size_bytes"] == 0
        assert proof["identity"]["sha256"] == payload.sha256(b"")
        os.write(proof["fd"], b"proof bytes")
        assert payload.proof_size(proof) == len(b"proof bytes")
        raw, final_identity = payload.snapshot_retained_regular(proof, "proof")
        assert raw == b"proof bytes"
        assert final_identity["inode"] == proof["identity"]["inode"]
        with pytest.raises(payload.PayloadError, match="exclusive retained output create failed"):
            payload.create_retained_output(proof_path, "duplicate proof")
    finally:
        payload.close_retained_regular(proof)


def test_fd_invocations_use_only_proc_self_fd_and_pass_every_retained_fd(
    payload: ModuleType,
    tmp_path: Path,
) -> None:
    executable = _pin_executable(payload, tmp_path / "tool")
    formula_path = _write_regular(tmp_path / "formula.opb", b"* formula\n")
    tool_path = _write_regular(tmp_path / "translation.py", b"raise SystemExit(0)\n")
    _, formula = payload.pin_retained_regular(_identity(payload, formula_path), "formula")
    _, translation_tool = payload.pin_retained_regular(
        _identity(payload, tool_path),
        "translation tool",
    )
    proof = payload.create_retained_output((tmp_path / "proof.pbp").resolve(), "proof")
    try:
        solver_argv, solver_fds = payload.roundingsat_fd_invocation(
            executable,
            formula,
            proof,
        )
        assert solver_argv == [
            executable["fd_path"],
            f"--proof-log={proof['fd_path']}",
            f"--time-limit={payload.ROUNDINGSAT_SECONDS}",
            formula["fd_path"],
        ]
        assert solver_fds == (executable["fd"], formula["fd"], proof["fd"])

        verifier_argv, verifier_fds = payload.veripb_fd_invocation(
            executable,
            formula,
            proof,
            proof["identity"],
        )
        assert verifier_argv == [
            executable["fd_path"],
            "--opb",
            "--stats",
            formula["fd_path"],
            proof["fd_path"],
        ]
        assert verifier_fds == (executable["fd"], formula["fd"], proof["fd"])

        translation_argv, translation_fds = payload.translation_fd_invocation(
            executable,
            translation_tool,
            ["--fixture", "value"],
        )
        assert translation_argv[:4] == [
            executable["fd_path"],
            "-I",
            "-c",
            payload.TRANSLATION_FD_BOOTSTRAP,
        ]
        assert translation_argv[4] == str(translation_tool["fd"])
        assert json.loads(translation_argv[5]) == translation_tool["identity"]
        assert translation_argv[6:] == ["--fixture", "value"]
        assert translation_fds == (executable["fd"], translation_tool["fd"])
        assert str(formula_path) not in solver_argv
        assert str(tool_path) not in translation_argv[:5]

        malformed = dict(formula)
        malformed.pop("fd_path")
        with pytest.raises(payload.PayloadError, match="exact retained-FD record key set"):
            payload.veripb_fd_invocation(executable, malformed, proof, proof["identity"])
    finally:
        payload.close_retained_regular(proof)
        payload.close_retained_regular(translation_tool)
        payload.close_retained_regular(formula)
        payload.close_pinned_executable(executable)


def test_retained_fd_provenance_is_exact_and_rejects_identity_drift(
    payload: ModuleType,
    tmp_path: Path,
) -> None:
    formula_path = _write_regular(tmp_path / "formula.opb", b"* formula\n")
    tool_path = _write_regular(tmp_path / "translation.py", b"raise SystemExit(0)\n")
    formula_identity = _identity(payload, formula_path)
    tool_identity = _identity(payload, tool_path)
    proof = payload.create_retained_output((tmp_path / "proof.pbp").resolve(), "proof")
    try:
        seed_identity = copy.deepcopy(proof["identity"])
        os.write(proof["fd"], b"proof")
        _, proof_identity = payload.snapshot_retained_regular(proof, "proof", collect=False)
        provenance = payload.retained_fd_provenance(
            formula_write_identity=formula_identity,
            formula_final_identity=formula_identity,
            proof_seed_identity=seed_identity,
            proof_final_identity=proof_identity,
            translation_tool_identity=tool_identity,
            translation_tool_final_identity=tool_identity,
        )
        assert set(provenance) == {
            "schema_version",
            "formula",
            "proof",
            "translation_tool",
            "content_reopened_by_path_after_retained_validation",
        }
        assert provenance["schema_version"] == payload.RETAINED_FD_PROVENANCE_SCHEMA
        assert provenance["proof"]["created_with_o_excl"] is True
        assert provenance["proof"]["size_monitor_source"] == "same_retained_fd_fstat"
        assert provenance["proof"]["post_solver_read_source"] == "same_retained_fd_pread"
        assert provenance["formula"]["same_parent_fd_retained_through_both_processes"] is True
        assert provenance["translation_tool"]["executed_from_validated_source_fd"] is True
        assert provenance["translation_tool"]["child_full7_revalidation"] is True
        assert (
            provenance["translation_tool"]["self_identity_read_redirected_to_same_retained_fd"]
            is True
        )
        assert provenance["content_reopened_by_path_after_retained_validation"] is False

        missing = copy.deepcopy(proof_identity)
        missing.pop("sha256")
        with pytest.raises(payload.PayloadError, match="provenance identity failed"):
            payload.retained_fd_provenance(
                formula_write_identity=formula_identity,
                formula_final_identity=formula_identity,
                proof_seed_identity=seed_identity,
                proof_final_identity=missing,
                translation_tool_identity=tool_identity,
                translation_tool_final_identity=tool_identity,
            )

        drifted = copy.deepcopy(formula_identity)
        drifted["sha256"] = "0" * 64
        with pytest.raises(payload.PayloadError, match="formula identity drifted"):
            payload.retained_fd_provenance(
                formula_write_identity=formula_identity,
                formula_final_identity=drifted,
                proof_seed_identity=seed_identity,
                proof_final_identity=proof_identity,
                translation_tool_identity=tool_identity,
                translation_tool_final_identity=tool_identity,
            )
    finally:
        payload.close_retained_regular(proof)


def test_translation_bootstrap_executes_and_self_reads_only_retained_tool_fd(
    payload: ModuleType,
    tmp_path: Path,
) -> None:
    executable_path = Path(sys.executable).resolve(strict=True)
    python_pin = payload.pin_executable(
        _identity(payload, executable_path),
        "fixture Python",
    )
    tool_source = b"""\
import hashlib
import os
from pathlib import Path

fd = os.open(
    Path(__file__).absolute(),
    os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
)
try:
    raw = os.read(fd, 1 << 20)
finally:
    os.close(fd)
print(__file__)
print(hashlib.sha256(raw).hexdigest())
"""
    tool_path = _write_regular(tmp_path / "self_reading_tool.py", tool_source)
    _, tool_pin = payload.pin_retained_regular(
        _identity(payload, tool_path),
        "self-reading translation tool",
    )
    try:
        argv, pass_fds = payload.translation_fd_invocation(
            python_pin,
            tool_pin,
            [],
        )
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            pass_fds=pass_fds,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr.decode(errors="replace")
        assert completed.stdout.decode().splitlines() == [
            str(tool_path),
            payload.sha256(tool_source),
        ]
        payload.verify_retained_unchanged(
            tool_pin,
            tool_pin["identity"],
            "self-reading translation tool final",
        )
    finally:
        payload.close_retained_regular(tool_pin)
        payload.close_pinned_executable(python_pin)


def test_fake_roundingsat_then_veripb_share_retained_formula_and_proof_fds(
    payload: ModuleType,
    tmp_path: Path,
) -> None:
    fake_roundingsat_source = b"""\
#!/usr/bin/env python3
import hashlib
import sys

proof_path = next(
    value.split("=", 1)[1]
    for value in sys.argv[1:]
    if value.startswith("--proof-log=")
)
formula_path = sys.argv[-1]
with open(formula_path, "rb") as handle:
    formula = handle.read()
proof = b"proof-sha256:" + hashlib.sha256(formula).hexdigest().encode("ascii") + b"\\n"
with open(proof_path, "wb") as handle:
    handle.write(proof)
print("s UNSATISFIABLE")
"""
    fake_veripb_source = b"""\
#!/usr/bin/env python3
import hashlib
import sys

if sys.argv[1:3] != ["--opb", "--stats"]:
    raise SystemExit("unexpected VeriPB option shape")
formula_path, proof_path = sys.argv[-2:]
with open(formula_path, "rb") as handle:
    formula = handle.read()
with open(proof_path, "rb") as handle:
    proof = handle.read()
expected = b"proof-sha256:" + hashlib.sha256(formula).hexdigest().encode("ascii") + b"\\n"
if proof != expected:
    raise SystemExit("proof/formula retained-FD join failed")
print("s VERIFIED UNSATISFIABLE")
"""
    roundingsat_path = _write_regular(
        tmp_path / "fake-roundingsat",
        fake_roundingsat_source,
        mode=0o755,
    )
    veripb_path = _write_regular(
        tmp_path / "fake-veripb",
        fake_veripb_source,
        mode=0o755,
    )
    roundingsat_pin = payload.pin_executable(
        _identity(payload, roundingsat_path),
        "fake RoundingSat",
    )
    veripb_pin = payload.pin_executable(
        _identity(payload, veripb_path),
        "fake VeriPB",
    )
    trusted_formula = b"* trusted retained formula\n"
    hostile_formula = b"* hostile replacement formula\n"
    formula_path = _write_regular(tmp_path / "formula.opb", trusted_formula)
    formula_identity = _identity(payload, formula_path)
    _, formula_pin = payload.pin_retained_regular(
        formula_identity,
        "integration formula",
    )
    proof_pin = payload.create_retained_output(
        (tmp_path / "roundingsat.proof.pbp").resolve(),
        "integration proof",
    )
    moved_formula = tmp_path / "formula.opb.retained-original"
    try:
        solver_argv, solver_pass_fds = payload.roundingsat_fd_invocation(
            roundingsat_pin,
            formula_pin,
            proof_pin,
        )

        formula_path.rename(moved_formula)
        _write_regular(formula_path, hostile_formula)
        assert formula_path.read_bytes() == hostile_formula
        assert os.pread(formula_pin["fd"], len(trusted_formula), 0) == trusted_formula

        solver_stdout = tmp_path / "roundingsat.stdout.txt"
        solver_stderr = tmp_path / "roundingsat.stderr.txt"
        solver_exit, _, solver_stop = payload.run_roundingsat(
            solver_argv,
            solver_stdout,
            solver_stderr,
            proof_pin,
            pass_fds=solver_pass_fds,
        )
        assert solver_exit == 0
        assert solver_stop is None
        assert solver_stdout.read_text(encoding="utf-8").splitlines() == [
            "s UNSATISFIABLE"
        ]
        expected_proof = (
            b"proof-sha256:" + payload.sha256(trusted_formula).encode("ascii") + b"\n"
        )
        hostile_proof = (
            b"proof-sha256:" + payload.sha256(hostile_formula).encode("ascii") + b"\n"
        )
        proof_raw, proof_identity = payload.snapshot_retained_regular(
            proof_pin,
            "integration proof after fake RoundingSat",
        )
        assert proof_raw == expected_proof
        assert proof_raw != hostile_proof

        formula_path.unlink()
        moved_formula.rename(formula_path)
        formula_after_solver = payload.verify_retained_unchanged(
            formula_pin,
            formula_identity,
            "integration formula after path restoration",
        )
        assert formula_after_solver == formula_identity

        verifier_argv, verifier_pass_fds = payload.veripb_fd_invocation(
            veripb_pin,
            formula_pin,
            proof_pin,
            proof_identity,
        )
        verifier_stdout = tmp_path / "veripb.stdout.txt"
        verifier_stderr = tmp_path / "veripb.stderr.txt"
        verifier_exit, _ = payload.run_timed(
            verifier_argv,
            verifier_stdout,
            verifier_stderr,
            10,
            pass_fds=verifier_pass_fds,
        )
        assert verifier_exit == 0
        verifier_lines = verifier_stdout.read_text(encoding="utf-8").splitlines()
        assert verifier_lines == ["s VERIFIED UNSATISFIABLE"]
        assert sum(line.startswith("s ") for line in verifier_lines) == 1
        assert verifier_stderr.read_bytes() == b""

        formula_final = payload.verify_retained_unchanged(
            formula_pin,
            formula_identity,
            "integration formula final",
        )
        proof_final = payload.verify_retained_unchanged(
            proof_pin,
            proof_identity,
            "integration proof final",
        )
        assert formula_final == formula_identity
        assert proof_final == proof_identity
        assert formula_final["path"] == str(formula_path)
        assert formula_final["inode"] == formula_pin["before"].st_ino
        assert proof_final["path"] == proof_pin["logical_path"]
        assert proof_final["inode"] == proof_pin["before"].st_ino
    finally:
        if moved_formula.exists():
            if formula_path.exists():
                formula_path.unlink()
            moved_formula.rename(formula_path)
        payload.close_retained_regular(proof_pin)
        payload.close_retained_regular(formula_pin)
        payload.close_pinned_executable(veripb_pin)
        payload.close_pinned_executable(roundingsat_pin)


def test_roundingsat_monitor_reads_size_from_retained_fd(payload: ModuleType) -> None:
    source = inspect.getsource(payload.proof_size)
    assert "current = os.fstat(retained[\"fd\"])" in source
    assert "return current.st_size" in source
    run_source = inspect.getsource(payload.run_roundingsat)
    assert "proof_size(proof_record)" in run_source
    assert "proof_path" not in run_source


def test_formal_main_keeps_formula_proof_and_translation_tool_pinned(
    payload: ModuleType,
) -> None:
    source = inspect.getsource(payload.main)
    assert 'pin_retained_regular(\n            formula_identity,' in source
    assert "proof_pin = create_retained_output(" in source
    assert "translation_argv, translation_pass_fds = translation_fd_invocation(" in source
    assert "solver_argv, solver_pass_fds = roundingsat_fd_invocation(" in source
    assert "verifier_argv, verifier_pass_fds = veripb_fd_invocation(" in source
    assert "snapshot_regular(\n            proof_path" not in source
