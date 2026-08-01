#!/usr/bin/env python3
"""Recover the old ``(1188, 22)`` conditional upper authority from fresh snapshots.

The verifier never follows a path embedded in a historical JSON document.  It
opens only caller-supplied, fresh-authority snapshot paths, joins each retained
file descriptor to an exact full-seven-field identity and its canonical content
projection, closes the historical receipt/manifest/hash graph, independently
reconstructs the complete 2,084-selector OPB and variable map, and replays
VeriPB through retained ``/proc/self/fd`` paths.

PASS is conditional on the immutable A004-admitted geometric lemmas.  This
component is deliberately not a ledger-update receipt and always emits
``upper_bound_update_authorized=false``.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Mapping, Sequence

from identity_contract_v1 import (
    IdentityContractError,
    assert_identity_join,
    canonical_content_projection,
    validate_full_identity,
    validate_projection,
)


SCHEMA = "b1_smm4_old_upper_snapshot_verification_v1"
PINS_SCHEMA = "b1_smm4_old_upper_snapshot_pins_v1"
SEMANTICS = (
    "b1_r4_1188_22_complete_oriented_lex_better_band_"
    "given_a004_admitted_lemmas_v1"
)
RECEIPT_SCHEMA = "b1_r4_1188_22_pb_authority_receipt_v1"
TOOLCHAIN_SCHEMA = "b1_r4_1188_22_pb_toolchain_run_v1"
BUILD_RECORD_SCHEMA = "b1_r4_1188_22_pb_build_record_v1"
TRANSLATION_GATE_SCHEMA = "b1_r4_1188_22_pb_translation_gate_v1"
MODEL_SCHEMA = "b1_r4_1188_22_pb_v1"
VARIABLE_MAP_SCHEMA = "b1_r4_1188_22_pb_var_map_v1"
HARNESS = "b1_r4_1188_22_pb_encoder_v1"

TARGET_AREA = 1_188
TARGET_MIN_SIDE = 22
FROZEN_A004_ORDINARY_NUMERATOR = 580
FROZEN_A004_MARKED_NUMERATOR = 678
FROZEN_A004_INCIDENCE_CAP = 4
FROZEN_A004_MINIMUM_POLES = 9
FROZEN_A004_MARKED_MINIMUM_SIDE = 9
EXPECTED_VARIABLES = 2_084
EXPECTED_CONSTRAINTS = 2_192
EXPECTED_FULL_SPAN = 107

FORMAL_MANIFEST_MEMBERS = (
    "build_authority.SHA256SUMS",
    "build_authority.record.json",
    "encoder.meta.json",
    "estimate.json",
    "formal_attempt.reservation.json",
    "formula.opb",
    "resource_monitor.jsonl",
    "roundingsat.proof.pbp",
    "roundingsat.stderr.txt",
    "roundingsat.stdout.txt",
    "toolchain_started.json",
    "translation_gate.json",
    "translation_gate.recheck.json",
    "translation_gate.recheck.stderr.txt",
    "translation_gate.recheck.stdout.txt",
    "variable_map.json",
    "veripb.stderr.txt",
    "veripb.stdout.txt",
    "veripb.version.stderr.txt",
    "veripb.version.stdout.txt",
)


def member_key(filename: str) -> str:
    """Return the authority key for one exact formal-manifest member name."""

    return "old_r4_member_" + filename.replace(".", "_").replace("-", "_")


FORMAL_MEMBER_KEYS = {filename: member_key(filename) for filename in FORMAL_MANIFEST_MEMBERS}
REQUIRED_INPUT_KEYS = (
    "old_r4_receipt",
    "old_r4_toolchain_record",
    "old_r4_raw_manifest",
    *(FORMAL_MEMBER_KEYS[name] for name in FORMAL_MANIFEST_MEMBERS),
    "old_r4_a004_admission",
    "strict_instance",
)

# Immutable historical byte identities.  Fresh paths and physical object
# identity are supplied by the no-overwrite SMM4 authority and joined below.
CONTENT_ANCHORS: dict[str, dict[str, Any]] = {
    "old_r4_receipt": {
        "size_bytes": 2613,
        "sha256": "0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2",
        "mode_octal": "0644",
    },
    "old_r4_toolchain_record": {
        "size_bytes": 154545,
        "sha256": "b99c9dd62b9be3c06de93d125bd2feaadc761f9eb541eb3d39a72070f33314f3",
        "mode_octal": "0644",
    },
    "old_r4_raw_manifest": {
        "size_bytes": 1795,
        "sha256": "8049f487106735c5d133d8c5998bd669eedca46e28dd4bef46714aac88d2c8ca",
        "mode_octal": "0644",
    },
    "old_r4_a004_admission": {
        "size_bytes": 10273,
        "sha256": "2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff",
        "mode_octal": "0644",
    },
    "strict_instance": {
        "size_bytes": 92201,
        "sha256": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
        "mode_octal": "0644",
    },
    member_key("build_authority.SHA256SUMS"): {
        "size_bytes": 942,
        "sha256": "652a7bdf5bab1488e40fa1bce6eab18e59437f038acef0d7b3f39b197c74771a",
        "mode_octal": "0644",
    },
    member_key("build_authority.record.json"): {
        "size_bytes": 11982,
        "sha256": "4f8124c582d0c4134538abd2574f2f2ebb3fb5eeb56f0aba7fb1d760fc72f886",
        "mode_octal": "0644",
    },
    member_key("encoder.meta.json"): {
        "size_bytes": 15390,
        "sha256": "f304342bd6b1ac51b8be5dc0c4c6d439dfde06b667fec3c8fd7928f714d73c3d",
        "mode_octal": "0644",
    },
    member_key("estimate.json"): {
        "size_bytes": 13231,
        "sha256": "0a8bdfd6a3b38e9aa4085942788240087a7db335d05583447a7d02004521786b",
        "mode_octal": "0644",
    },
    member_key("formal_attempt.reservation.json"): {
        "size_bytes": 2682,
        "sha256": "9710e9bb99cd82562791a2d6f66319356bca7eaf028299933a23571a65df0ab6",
        "mode_octal": "0644",
    },
    member_key("formula.opb"): {
        "size_bytes": 56881,
        "sha256": "9ce8f110757ecf87af888ed7fd2fbc334eecaf2e1a9be784a8a1b5dc8f3435d8",
        "mode_octal": "0644",
    },
    member_key("resource_monitor.jsonl"): {
        "size_bytes": 6773,
        "sha256": "cb241cffe7b79d57b9d2d6f3f89e1e5b632f5e459d224986d8280c48e8c4e2c5",
        "mode_octal": "0600",
    },
    member_key("roundingsat.proof.pbp"): {
        "size_bytes": 39446,
        "sha256": "54c4b9c61f7a4505808e8cad895c863ca8579400e3df83e7e7c8d269d0504531",
        "mode_octal": "0644",
    },
    member_key("roundingsat.stderr.txt"): {
        "size_bytes": 0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "mode_octal": "0644",
    },
    member_key("roundingsat.stdout.txt"): {
        "size_bytes": 2371,
        "sha256": "fc741e3db09b4297f880d6ebfc24bca9b1b045c0137cca9950d91c41303d01d1",
        "mode_octal": "0644",
    },
    member_key("toolchain_started.json"): {
        "size_bytes": 39128,
        "sha256": "a1b35570ceb8740cecaedae4099df0f9a3bc659829c53593cb6bebde395f6e2e",
        "mode_octal": "0644",
    },
    member_key("translation_gate.json"): {
        "size_bytes": 10332,
        "sha256": "0146770cdad317f80523f6d05e4a59997209a28b2cb657e844fd458e8af79602",
        "mode_octal": "0644",
    },
    member_key("translation_gate.recheck.json"): {
        "size_bytes": 10332,
        "sha256": "0146770cdad317f80523f6d05e4a59997209a28b2cb657e844fd458e8af79602",
        "mode_octal": "0644",
    },
    member_key("translation_gate.recheck.stderr.txt"): {
        "size_bytes": 0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "mode_octal": "0644",
    },
    member_key("translation_gate.recheck.stdout.txt"): {
        "size_bytes": 208,
        "sha256": "2d2a61e2138147b711500a31ae4774d9008eef82f11ec5876b56206c2a17a8c2",
        "mode_octal": "0644",
    },
    member_key("variable_map.json"): {
        "size_bytes": 967694,
        "sha256": "877fe9ee63e96bb616761b8c1719fde40d5fe14a9eaf852adce747275830c028",
        "mode_octal": "0644",
    },
    member_key("veripb.stderr.txt"): {
        "size_bytes": 0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "mode_octal": "0644",
    },
    member_key("veripb.stdout.txt"): {
        "size_bytes": 183,
        "sha256": "e99277368076972906e135c4a443a361b6ddbdaa5c596a1118326d6b2776c09f",
        "mode_octal": "0644",
    },
    member_key("veripb.version.stderr.txt"): {
        "size_bytes": 0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "mode_octal": "0644",
    },
    member_key("veripb.version.stdout.txt"): {
        "size_bytes": 42,
        "sha256": "179a3be6a120ee0f76ec97355197e605b3a7217584d3c344af9949d0248a4e86",
        "mode_octal": "0644",
    },
}

VERIPB_ANCHOR = {
    "size_bytes": 3317320,
    "sha256": "a0c72df075b924af3b698ae808f86d3b55067168534397a0cc3d49594777b971",
    "mode_octal": "0755",
}

BUILD_MANIFEST_MEMBERS = (
    "encode.stderr.txt",
    "encode.stdout.txt",
    "encoder.meta.json",
    "estimate.json",
    "estimate.stderr.txt",
    "estimate.stdout.txt",
    "formula.opb",
    "translation_gate.json",
    "translation_gate.stderr.txt",
    "translation_gate.stdout.txt",
    "variable_map.json",
)
BUILD_MANIFEST_HASHES = {
    "encode.stderr.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "encode.stdout.txt": "00d90f29673adb620aae8c796ba63ced3452f9f18b5a20eb6c9b7f3eed96f495",
    "encoder.meta.json": "f304342bd6b1ac51b8be5dc0c4c6d439dfde06b667fec3c8fd7928f714d73c3d",
    "estimate.json": "0a8bdfd6a3b38e9aa4085942788240087a7db335d05583447a7d02004521786b",
    "estimate.stderr.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "estimate.stdout.txt": "c41ca74f71fc81160ae4bf988c6d3cf4b5f48b0fd4b9cac0d0b3a5a3e921112f",
    "formula.opb": "9ce8f110757ecf87af888ed7fd2fbc334eecaf2e1a9be784a8a1b5dc8f3435d8",
    "translation_gate.json": "0146770cdad317f80523f6d05e4a59997209a28b2cb657e844fd458e8af79602",
    "translation_gate.stderr.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "translation_gate.stdout.txt": "7c2c183197b3b1a5beedf2e518453fa99c60037ec8d4d8672d0937db9edbd096",
    "variable_map.json": "877fe9ee63e96bb616761b8c1719fde40d5fe14a9eaf852adce747275830c028",
}

REQUIRED_GATE_CHECKS = {
    "a004_admission_replay_pass",
    "access_cell_enumeration_exact",
    "boundary_packing_exact",
    "complete_band_corpus_unsat",
    "constraint_multiset_exact",
    "encoder_provenance_match",
    "estimate_reconstruction_match",
    "lex_better_band_exact",
    "marked_membrane_exact",
    "marked_terminal_census_exact",
    "metadata_reconstruction_match",
    "opb_header_exact",
    "ordinary_membrane_exact",
    "power_halo_exact",
    "semantic_canaries_pass",
    "strict_bundle_closed_and_hashed",
    "strict_sentinels_exact",
    "translation_inputs_closed_and_hashed",
    "variable_map_dense",
    "variable_map_exact",
}

STRICT_INSTANCE_KEYS = {
    "benchmark_id",
    "commodities",
    "coordinate_system",
    "facility_templates",
    "generic_requirements",
    "grid",
    "objective",
    "operation_groups",
    "power",
    "repeatable_auxiliaries",
    "required_instances",
    "routing",
    "schema_version",
    "sentinels",
}
RECEIPT_KEYS = {
    "build_manifest",
    "build_record",
    "claim",
    "created_at_utc",
    "formal_attempt",
    "formula",
    "output_directory",
    "production_certified",
    "proof",
    "proof_status",
    "raw_manifest",
    "reservation_copy",
    "reservation_source",
    "schema_version",
    "semantics",
    "status",
    "toolchain_record",
    "upper_bound_update_authorized",
}
REFERENCE_KEYS = {"path", "sha256", "size_bytes"}
PIN_KEYS = {"identity", "content_projection"}
SHA256_LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)")


class OldUpperVerificationError(RuntimeError):
    """Raised when the historical conditional authority cannot be recovered."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OldUpperVerificationError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    require(type(value) is dict, f"{label}: expected object")
    require(set(value) == keys, f"{label}: key set mismatch")
    return value


def exact_int(value: Any, label: str, *, minimum: int | None = None) -> int:
    require(type(value) is int, f"{label}: expected exact integer")
    if minimum is not None:
        require(value >= minimum, f"{label}: value is below {minimum}")
    return value


def strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OldUpperVerificationError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise OldUpperVerificationError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OldUpperVerificationError(f"{label}: malformed JSON: {exc}") from exc


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
        value.st_nlink,
    )


def _read_all(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        block = os.read(fd, 1 << 20)
        if not block:
            return b"".join(chunks)
        chunks.append(block)


@dataclass(slots=True)
class RetainedSnapshot:
    """One stable regular-file snapshot whose descriptor remains open."""

    label: str
    path: Path
    fd: int
    raw: bytes
    identity: dict[str, Any]
    signature: tuple[int, ...]

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def check_stable(self, *, rehash: bool = False) -> None:
        require(self.fd >= 0, f"{self.label}: retained descriptor is closed")
        require(
            _stat_signature(os.fstat(self.fd)) == self.signature,
            f"{self.label}: file changed while descriptor was retained",
        )
        if rehash:
            replay = _read_all(self.fd)
            require(replay == self.raw, f"{self.label}: retained-FD bytes drifted")


def _canonical_regular_path(path: Path, label: str) -> Path:
    raw = os.fspath(path)
    require(os.path.isabs(raw), f"{label}: path must be absolute")
    normalized = os.path.normpath(raw)
    require(raw == normalized, f"{label}: path is not normalized")
    require(os.path.realpath(raw) == normalized, f"{label}: path contains a symlink or alias")
    return Path(normalized)


def _normalize_pin(value: Mapping[str, Any], label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    pin = exact_object(dict(value), PIN_KEYS, label)
    identity = validate_full_identity(pin["identity"], f"{label}.identity")
    projection = validate_projection(pin["content_projection"], f"{label}.content_projection")
    require(
        canonical_content_projection(identity, f"{label}.identity") == projection,
        f"{label}: identity/content projection mismatch",
    )
    return identity, projection


def _normalize_veripb_pin(value: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    copied = dict(value)
    if set(copied) == PIN_KEYS:
        return _normalize_pin(copied, "veripb pin")
    identity = validate_full_identity(copied, "veripb logical identity")
    return identity, canonical_content_projection(identity, "veripb logical identity")


def _open_retained(
    path: Path,
    expected_identity: Mapping[str, Any],
    expected_projection: Mapping[str, Any],
    anchor: Mapping[str, Any],
    label: str,
) -> RetainedSnapshot:
    canonical = _canonical_regular_path(path, label)
    fd = os.open(
        canonical,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), f"{label}: not a regular file")
        require(before.st_nlink == 1, f"{label}: link_count must equal 1")
        raw = _read_all(fd)
        after = os.fstat(fd)
        require(
            _stat_signature(before) == _stat_signature(after),
            f"{label}: file changed during retained-FD read",
        )
        require(len(raw) == before.st_size, f"{label}: retained-FD short read")
        actual = {
            "path": str(canonical),
            "size_bytes": len(raw),
            "sha256": sha256(raw),
            "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
            "device": before.st_dev,
            "inode": before.st_ino,
            "link_count": before.st_nlink,
        }
        projection = assert_identity_join(
            dict(expected_identity),
            dict(expected_projection),
            actual,
            label,
        )
        require(
            {field: actual[field] for field in ("size_bytes", "sha256", "mode_octal")}
            == dict(anchor),
            f"{label}: immutable content anchor mismatch",
        )
        require(
            projection == {field: actual[field] for field in ("path", "size_bytes", "sha256", "mode_octal")},
            f"{label}: canonical projection join mismatch",
        )
        return RetainedSnapshot(
            label=label,
            path=canonical,
            fd=fd,
            raw=raw,
            identity=actual,
            signature=_stat_signature(before),
        )
    except Exception:
        os.close(fd)
        raise


def snapshot_regular(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    """Read a canonical regular file once and return bytes plus exact full7 identity."""

    canonical = _canonical_regular_path(path, label)
    fd = os.open(
        canonical,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), f"{label}: not a regular file")
        require(before.st_nlink == 1, f"{label}: link_count must equal 1")
        raw = _read_all(fd)
        after = os.fstat(fd)
        require(_stat_signature(before) == _stat_signature(after), f"{label}: file changed during read")
        require(len(raw) == before.st_size, f"{label}: short read")
        identity = {
            "path": str(canonical),
            "size_bytes": len(raw),
            "sha256": sha256(raw),
            "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
            "device": before.st_dev,
            "inode": before.st_ino,
            "link_count": before.st_nlink,
        }
        return raw, validate_full_identity(identity, label)
    finally:
        os.close(fd)


def parse_pins(raw: bytes) -> dict[str, Any]:
    """Parse the strict standalone CLI pin bundle."""

    value = exact_object(strict_json(raw, "old-upper pins"), {"schema_version", "inputs", "veripb"}, "pins")
    require(value["schema_version"] == PINS_SCHEMA, "pins: schema mismatch")
    inputs = exact_object(value["inputs"], set(REQUIRED_INPUT_KEYS), "pins.inputs")
    validated: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_INPUT_KEYS:
        identity, projection = _normalize_pin(inputs[name], f"pins.inputs.{name}")
        validated[name] = {"identity": identity, "content_projection": projection}
    veripb_identity, veripb_projection = _normalize_pin(value["veripb"], "pins.veripb")
    return {
        "inputs": validated,
        "veripb": {
            "identity": veripb_identity,
            "content_projection": veripb_projection,
        },
    }


def parse_sha256_manifest(raw: bytes, expected_names: tuple[str, ...], label: str) -> dict[str, str]:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise OldUpperVerificationError(f"{label}: non-ASCII bytes") from exc
    require(text.endswith("\n"), f"{label}: missing terminal newline")
    lines = text.splitlines()
    require(len(lines) == len(expected_names), f"{label}: line count mismatch")
    entries: dict[str, str] = {}
    observed_names: list[str] = []
    for index, line in enumerate(lines, start=1):
        match = SHA256_LINE.fullmatch(line)
        require(match is not None, f"{label}: malformed line {index}")
        digest, name = match.groups()
        require(name not in entries, f"{label}: duplicate member {name!r}")
        entries[name] = digest
        observed_names.append(name)
    require(tuple(observed_names) == expected_names, f"{label}: ordered member set mismatch")
    return entries


def _reference(value: Any, label: str) -> dict[str, Any]:
    result = exact_object(value, REFERENCE_KEYS, label)
    require(type(result["path"]) is str and result["path"], f"{label}: path malformed")
    exact_int(result["size_bytes"], f"{label}.size_bytes", minimum=0)
    require(
        type(result["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", result["sha256"]) is not None,
        f"{label}: sha256 malformed",
    )
    return result


def _assert_reference(value: Any, anchor: Mapping[str, Any], label: str) -> None:
    reference = _reference(value, label)
    require(
        reference["size_bytes"] == anchor["size_bytes"] and reference["sha256"] == anchor["sha256"],
        f"{label}: byte reference mismatch",
    )


def verify_a004_admission(value: Any) -> dict[str, Any]:
    admission = exact_object(
        value,
        {
            "admission_tool",
            "adversarial_verdict",
            "assembly_run_authorized",
            "attainability_established",
            "authority",
            "candidates",
            "claim_boundary",
            "claim_ledger",
            "claim_ledger_builder_tool",
            "created_at_utc",
            "current_project_ledger",
            "cutoff_date",
            "encoder_execution_authorized",
            "external_response_code_executed",
            "formal_run_authorized",
            "global_infeasibility_established",
            "input_bindings",
            "optimality_established",
            "production_certified",
            "recomputation_reports",
            "recomputation_runner_tool",
            "response_ingest",
            "router_run_authorized",
            "schema",
            "search_run_authorized",
            "solver_run_authorized",
            "status",
            "track_w_execution_authorized",
            "upper_bound_changed",
            "verdict_replay_tool",
            "witness_established",
        },
        "A004 admission",
    )
    require(
        admission["schema"] == "r4_response_candidate_admission_v2"
        and admission["status"] == "PARTIAL"
        and admission["claim_boundary"]
        == "research follow-up admission only; project ledgers and execution authorizations are unchanged",
        "A004 admission: boundary/status mismatch",
    )
    false_fields = (
        "assembly_run_authorized",
        "attainability_established",
        "encoder_execution_authorized",
        "external_response_code_executed",
        "formal_run_authorized",
        "global_infeasibility_established",
        "optimality_established",
        "production_certified",
        "router_run_authorized",
        "search_run_authorized",
        "solver_run_authorized",
        "track_w_execution_authorized",
        "upper_bound_changed",
        "witness_established",
    )
    require(all(admission[field] is False for field in false_fields), "A004 admission: false boundary drifted")
    require(
        admission["current_project_ledger"] == {"L": "absent", "U": [1190, 34]},
        "A004 admission: historical ledger context drifted",
    )
    candidates = admission["candidates"]
    require(type(candidates) is dict and "upper_bound_1188_22" in candidates, "A004 admission: candidate missing")
    require(
        candidates["upper_bound_1188_22"]
        == {
            "b1_followup_input_admitted": True,
            "proposed_upper_ledger": [1188, 22],
            "research_followup_admitted": True,
            "verdict": "PASS",
        },
        "A004 admission: upper candidate semantics drifted",
    )
    return {
        "schema": admission["schema"],
        "status": admission["status"],
        "upper_candidate": candidates["upper_bound_1188_22"],
        "geometric_lemmas_treated_as_frozen_assumptions": True,
        "attainability_established": False,
        "optimality_established": False,
        "whole_instance_infeasibility_established": False,
        "production_certified": False,
    }


def verify_receipt_graph(
    receipt: Any,
    toolchain: Any,
    build_record: Any,
    translation_gate: Any,
    a004_admission: Any,
    raw_manifest_entries: Mapping[str, str],
    build_manifest_entries: Mapping[str, str],
) -> dict[str, Any]:
    receipt = exact_object(receipt, RECEIPT_KEYS, "old R4 receipt")
    require(
        receipt["schema_version"] == RECEIPT_SCHEMA
        and receipt["semantics"] == SEMANTICS
        and receipt["formal_attempt"] == "a001"
        and receipt["status"] == "VERIFIED"
        and receipt["proof_status"] == "VERIFIED UNSATISFIABLE"
        and receipt["claim"]
        == "machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas"
        and receipt["upper_bound_update_authorized"] is True
        and receipt["production_certified"] is False,
        "old R4 receipt: terminal semantics mismatch",
    )
    receipt_edges = {
        "build_manifest": member_key("build_authority.SHA256SUMS"),
        "build_record": member_key("build_authority.record.json"),
        "formula": member_key("formula.opb"),
        "proof": member_key("roundingsat.proof.pbp"),
        "raw_manifest": "old_r4_raw_manifest",
        "reservation_copy": member_key("formal_attempt.reservation.json"),
        "reservation_source": member_key("formal_attempt.reservation.json"),
        "toolchain_record": "old_r4_toolchain_record",
    }
    for edge, key in receipt_edges.items():
        _assert_reference(receipt[edge], CONTENT_ANCHORS[key], f"old R4 receipt.{edge}")

    build_record = exact_object(
        build_record,
        {
            "argv",
            "attempt",
            "claim",
            "created_at_utc",
            "formal_run_authorized",
            "git_head",
            "manifest",
            "outputs",
            "project_root",
            "proof_status",
            "runs",
            "schema_version",
            "semantics",
            "sources",
            "status",
        },
        "build record",
    )
    require(
        build_record["schema_version"] == BUILD_RECORD_SCHEMA
        and build_record["semantics"] == SEMANTICS
        and build_record["attempt"] == "build-a001-20260723T091353Z-398f8725"
        and build_record["status"] == "PASS"
        and build_record["claim"] == "none"
        and build_record["formal_run_authorized"] is False
        and build_record["proof_status"] == "build_and_translation_only_no_unsat_or_proof_claim",
        "build record: semantics/status mismatch",
    )
    manifest = exact_object(
        build_record["manifest"],
        {"covered_files", "entries", "excluded_to_avoid_hash_cycle", "file"},
        "build record.manifest",
    )
    require(manifest["covered_files"] == list(BUILD_MANIFEST_MEMBERS), "build record: covered set mismatch")
    require(
        manifest["excluded_to_avoid_hash_cycle"] == ["SHA256SUMS", "build_record.json"],
        "build record: manifest exclusions mismatch",
    )
    entries = manifest["entries"]
    require(type(entries) is list and len(entries) == len(BUILD_MANIFEST_MEMBERS), "build record: entries mismatch")
    reconstructed_entries: dict[str, str] = {}
    for index, raw_entry in enumerate(entries):
        entry = exact_object(raw_entry, {"path", "sha256", "size_bytes"}, f"build record entry {index}")
        name = entry["path"]
        require(type(name) is str and name not in reconstructed_entries, "build record: duplicate entry")
        reconstructed_entries[name] = entry["sha256"]
    require(reconstructed_entries == dict(build_manifest_entries), "build record: manifest hash graph mismatch")
    _assert_reference(
        manifest["file"],
        CONTENT_ANCHORS[member_key("build_authority.SHA256SUMS")],
        "build record.manifest.file",
    )
    output_edges = {
        "estimate": "estimate.json",
        "gate": "translation_gate.json",
        "meta": "encoder.meta.json",
        "opb": "formula.opb",
        "var_map": "variable_map.json",
    }
    outputs = exact_object(build_record["outputs"], set(output_edges), "build record.outputs")
    for output_name, filename in output_edges.items():
        _assert_reference(
            outputs[output_name],
            CONTENT_ANCHORS[member_key(filename)],
            f"build record.outputs.{output_name}",
        )

    gate = translation_gate
    require(type(gate) is dict, "translation gate: expected object")
    require(
        gate.get("schema_version") == TRANSLATION_GATE_SCHEMA
        and gate.get("semantics") == SEMANTICS
        and gate.get("status") == "PASS"
        and gate.get("proof_status") == "translation_gate_only_no_unsat_or_proof_claim"
        and gate.get("model_schema_version") == MODEL_SCHEMA
        and gate.get("variable_map_schema_version") == VARIABLE_MAP_SCHEMA
        and gate.get("corpus_count") == EXPECTED_VARIABLES
        and gate.get("corpus_errors") == []
        and gate.get("opb_parse_errors") == []
        and gate.get("minimum_non_full_span_lhs") == 1322,
        "translation gate: semantic closure mismatch",
    )
    checks = gate.get("checks")
    require(
        type(checks) is dict
        and set(checks) == REQUIRED_GATE_CHECKS
        and all(value is True for value in checks.values()),
        "translation gate: check set/result mismatch",
    )
    constraint_diff = gate.get("constraint_diff")
    require(
        constraint_diff
        == {
            "missing_examples": [],
            "missing_total": 0,
            "unexpected_examples": [],
            "unexpected_total": 0,
        },
        "translation gate: constraint diff is nonzero",
    )

    toolchain = toolchain
    require(type(toolchain) is dict, "toolchain record: expected object")
    require(
        toolchain.get("schema_version") == TOOLCHAIN_SCHEMA
        and toolchain.get("semantics") == SEMANTICS
        and toolchain.get("formal_attempt") == "a001"
        and toolchain.get("claim") == "none"
        and toolchain.get("solver_declared_unsat") is True
        and toolchain.get("veripb_verified") is True
        and toolchain.get("proof_tail_complete") is True
        and toolchain.get("inputs_stable") is True
        and toolchain.get("failure_codes") == []
        and toolchain.get("verified_result_candidate")
        == "machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas"
        and toolchain.get("upper_bound_update_authorized") is False
        and toolchain.get("publication_status") == "requires_successful_detached_authority_receipt_replay",
        "toolchain record: staged semantics mismatch",
    )
    artifact_manifest = toolchain.get("artifact_manifest")
    require(type(artifact_manifest) is dict, "toolchain record: artifact manifest missing")
    require(
        artifact_manifest.get("covered_files") == list(FORMAL_MANIFEST_MEMBERS)
        and artifact_manifest.get("entries") == dict(raw_manifest_entries)
        and artifact_manifest.get("excluded_to_avoid_hash_cycle")
        == ["SHA256SUMS", "authority_receipt.json", "toolchain_record.json"]
        and artifact_manifest.get("critical_hashes_match") is True
        and artifact_manifest.get("stable_recheck") is True,
        "toolchain record: formal manifest closure mismatch",
    )
    _assert_reference(
        artifact_manifest.get("file"),
        CONTENT_ANCHORS["old_r4_raw_manifest"],
        "toolchain record.artifact_manifest.file",
    )

    expected_input_edges = {
        "build_manifest": "build_authority.SHA256SUMS",
        "build_record": "build_authority.record.json",
        "estimate": "estimate.json",
        "meta": "encoder.meta.json",
        "opb": "formula.opb",
        "translation_gate": "translation_gate.json",
        "var_map": "variable_map.json",
    }
    for group_name in ("inputs", "input_copies", "inputs_after_execution"):
        group = toolchain.get(group_name)
        require(
            type(group) is dict and set(group) == set(expected_input_edges),
            f"toolchain {group_name}: set mismatch",
        )
        for edge, filename in expected_input_edges.items():
            _assert_reference(
                group[edge],
                CONTENT_ANCHORS[member_key(filename)],
                f"toolchain {group_name}.{edge}",
            )
    strict_inputs = toolchain.get("strict_inputs")
    require(type(strict_inputs) is dict and "problem_instance" in strict_inputs, "toolchain strict input missing")
    _assert_reference(
        strict_inputs["problem_instance"],
        CONTENT_ANCHORS["strict_instance"],
        "toolchain strict_inputs.problem_instance",
    )

    proof = toolchain.get("proof")
    require(type(proof) is dict, "toolchain proof missing")
    _assert_reference(proof.get("file"), CONTENT_ANCHORS[member_key("roundingsat.proof.pbp")], "toolchain proof")
    require(
        proof.get("fresh_for_solver") is True
        and proof.get("sha256_before_verifier") == CONTENT_ANCHORS[member_key("roundingsat.proof.pbp")]["sha256"]
        and proof.get("sha256_after_verifier") == CONTENT_ANCHORS[member_key("roundingsat.proof.pbp")]["sha256"]
        and proof.get("tail")
        == {
            "complete": True,
            "conclusion_line": "conclusion UNSAT : 4278",
            "end_line": "end pseudo-Boolean proof",
            "nonempty": True,
        },
        "toolchain proof: stability/tail mismatch",
    )
    solver = toolchain.get("solver")
    verifier = toolchain.get("verifier")
    require(
        type(solver) is dict
        and solver.get("declared_unsat") is True
        and solver.get("status_lines") == ["s UNSATISFIABLE"]
        and solver.get("error_markers") == [],
        "toolchain solver: terminal status mismatch",
    )
    require(
        type(verifier) is dict
        and verifier.get("verified_unsat") is True
        and verifier.get("status_lines") == ["s VERIFIED UNSATISFIABLE"]
        and verifier.get("error_markers") == [],
        "toolchain verifier: terminal status mismatch",
    )
    verifier_run = verifier.get("run")
    require(type(verifier_run) is dict, "toolchain verifier run missing")
    _assert_reference(
        verifier_run.get("stdout"),
        CONTENT_ANCHORS[member_key("veripb.stdout.txt")],
        "toolchain verifier stdout",
    )
    _assert_reference(
        verifier_run.get("stderr"),
        CONTENT_ANCHORS[member_key("veripb.stderr.txt")],
        "toolchain verifier stderr",
    )
    require(
        verifier_run.get("exit_code") == 0
        and verifier_run.get("timed_out") is False
        and verifier_run.get("termination_reason") is None
        and verifier_run.get("process_group_clean") is True,
        "toolchain verifier: execution cleanup mismatch",
    )

    translation = toolchain.get("translation_gate")
    require(
        type(translation) is dict
        and translation.get("status") == "PASS"
        and translation.get("recheck_byte_exact") is True
        and translation.get("checks") == checks
        and translation.get("corpus_errors") == [],
        "toolchain translation recheck mismatch",
    )
    _assert_reference(
        translation.get("file"),
        CONTENT_ANCHORS[member_key("translation_gate.json")],
        "toolchain translation file",
    )
    _assert_reference(
        translation.get("recheck_file"),
        CONTENT_ANCHORS[member_key("translation_gate.recheck.json")],
        "toolchain translation recheck",
    )

    hash_stability = toolchain.get("hash_stability")
    formula_hash = CONTENT_ANCHORS[member_key("formula.opb")]["sha256"]
    proof_hash = CONTENT_ANCHORS[member_key("roundingsat.proof.pbp")]["sha256"]
    require(
        hash_stability
        == {
            "formula_after_solver": formula_hash,
            "formula_after_verifier": formula_hash,
            "formula_before_solver": formula_hash,
            "formula_before_verifier": formula_hash,
            "proof_after_verifier": proof_hash,
            "proof_before_verifier": proof_hash,
            "stable": True,
        },
        "toolchain hash stability mismatch",
    )
    reservation = toolchain.get("reservation")
    require(type(reservation) is dict and reservation.get("stable") is True, "toolchain reservation unstable")
    for name in (
        "after_translation_gate",
        "after_veripb",
        "before_final_claim",
        "before_roundingsat",
        "copy",
        "source_at_reservation",
    ):
        _assert_reference(
            reservation.get(name),
            CONTENT_ANCHORS[member_key("formal_attempt.reservation.json")],
            f"toolchain reservation.{name}",
        )
    monitor = toolchain.get("resource_monitor")
    require(
        type(monitor) is dict
        and monitor.get("schema_version") == "b1_r4_1188_22_pb_resource_monitor_v1"
        and monitor.get("oom_clean") is True
        and monitor.get("cgroup_stable") is True
        and monitor.get("sample_count") == 11
        and monitor.get("maximum_proof_bytes_observed") == 39446
        and type(monitor.get("memory_event_deltas")) is dict
        and all(value == 0 for value in monitor["memory_event_deltas"].values()),
        "toolchain resource/cleanup evidence mismatch",
    )
    _assert_reference(
        monitor.get("file"),
        CONTENT_ANCHORS[member_key("resource_monitor.jsonl")],
        "toolchain resource monitor file",
    )

    a004 = toolchain.get("a004_authority")
    require(type(a004) is dict and a004.get("stable") is True, "toolchain A004 authority unstable")
    for phase in (
        "preflight",
        "after_translation_gate",
        "before_roundingsat",
        "after_roundingsat",
        "after_veripb",
        "before_final_claim",
    ):
        replay = a004.get(phase)
        require(
            type(replay) is dict and replay.get("status") == "PASS" and replay.get("admission") == a004_admission,
            f"toolchain A004 {phase}: replay mismatch",
        )
        _assert_reference(
            replay.get("admission_record"),
            CONTENT_ANCHORS["old_r4_a004_admission"],
            f"toolchain A004 {phase}.admission_record",
        )

    tools = toolchain.get("tools")
    require(
        type(tools) is dict
        and tools.get("stable") is True
        and tools.get("veripb_version_exact") is True,
        "toolchain tool stability mismatch",
    )
    for phase in ("before", "after"):
        phase_tools = tools.get(phase)
        require(type(phase_tools) is dict and "veripb" in phase_tools, f"toolchain tools.{phase} missing")
        historical_veripb = phase_tools["veripb"]
        require(
            type(historical_veripb) is dict and historical_veripb.get("expected_version") == "3.0.2",
            f"toolchain tools.{phase}.veripb version mismatch",
        )
        _assert_reference(
            historical_veripb.get("file"),
            VERIPB_ANCHOR,
            f"toolchain tools.{phase}.veripb",
        )

    return {
        "receipt_schema": RECEIPT_SCHEMA,
        "receipt_status": "VERIFIED",
        "receipt_proof_status": "VERIFIED UNSATISFIABLE",
        "historical_receipt_upper_bound_update_authorized": True,
        "toolchain_staged_upper_bound_update_authorized": False,
        "semantics": SEMANTICS,
        "formal_attempt": "a001",
        "formal_manifest_member_count": len(raw_manifest_entries),
        "build_manifest_member_count": len(build_manifest_entries),
        "formula_hash": formula_hash,
        "proof_hash": proof_hash,
        "a004_authority_stable": True,
        "resource_and_cleanup_evidence_closed": True,
    }


def _ceil_div(numerator: int, denominator: int) -> int:
    require(denominator > 0, "ceil divisor must be positive")
    return -((-numerator) // denominator)


def reconstruct_old_model(strict_instance: Any) -> dict[str, Any]:
    """Independently rebuild the exact old-band variable map and OPB bytes."""

    instance = exact_object(strict_instance, STRICT_INSTANCE_KEYS, "strict instance")
    require(
        instance["schema_version"] == 1
        and instance["benchmark_id"] == "factory_layout_optimality_benchmark_v1",
        "strict instance: schema/benchmark mismatch",
    )
    grid = exact_object(instance["grid"], {"height", "width"}, "strict instance.grid")
    grid_width = exact_int(grid["width"], "strict instance.grid.width", minimum=1)
    grid_height = exact_int(grid["height"], "strict instance.grid.height", minimum=1)
    objective = exact_object(
        instance["objective"],
        {"body_cells_only", "kind", "minimum_side"},
        "strict instance.objective",
    )
    minimum_side = exact_int(objective["minimum_side"], "strict instance.objective.minimum_side", minimum=1)
    require(
        (grid_width, grid_height, minimum_side) == (70, 70, 6)
        and objective["body_cells_only"] is True
        and objective["kind"] == "max_lex_area_min_side",
        "strict instance: grid/objective contract mismatch",
    )

    templates = instance["facility_templates"]
    required_instances = instance["required_instances"]
    require(type(templates) is dict and type(required_instances) is list, "strict instance: body inputs malformed")
    template_areas: dict[str, int] = {}
    for template_name, template in templates.items():
        require(type(template_name) is str and type(template) is dict, "strict instance: template malformed")
        modes = template.get("modes")
        require(type(modes) is list and modes, f"strict instance: {template_name} modes missing")
        areas: set[int] = set()
        for mode in modes:
            require(type(mode) is dict and type(mode.get("body")) is dict, f"strict instance: {template_name} body")
            body = mode["body"]
            width = exact_int(body.get("width"), f"strict instance: {template_name} body width", minimum=1)
            height = exact_int(body.get("height"), f"strict instance: {template_name} body height", minimum=1)
            areas.add(width * height)
        require(len(areas) == 1, f"strict instance: {template_name} mode area drifted")
        template_areas[template_name] = next(iter(areas))
    required_body_area = 0
    for index, required in enumerate(required_instances):
        require(type(required) is dict, f"strict instance: required instance {index} malformed")
        template_name = required.get("template")
        require(type(template_name) is str and template_name in template_areas, "strict instance: unknown template")
        required_body_area += template_areas[template_name]
    power = instance["power"]
    require(type(power) is dict and type(power.get("pole_template")) is str, "strict instance: power malformed")
    pole_area = template_areas.get(power["pole_template"])
    require(required_body_area == 3544 and pole_area == 4, "strict instance: body/pole area drifted")
    free_cell_cap = (
        grid_width * grid_height
        - required_body_area
        - FROZEN_A004_MINIMUM_POLES * pole_area
    )
    require(free_cell_cap == 1320, "strict instance/A004: free-cell cap drifted")

    dimensions = [
        (width, height)
        for width in range(minimum_side, grid_width + 1)
        for height in range(minimum_side, grid_height + 1)
        if width * height > TARGET_AREA
        or (width * height == TARGET_AREA and min(width, height) > TARGET_MIN_SIDE)
    ]
    variables: list[dict[str, Any]] = []
    for variable_id, (width, height) in enumerate(dimensions, start=1):
        side_sum = width + height
        ordinary = _ceil_div(FROZEN_A004_ORDINARY_NUMERATOR - side_sum, FROZEN_A004_INCIDENCE_CAP)
        marked = _ceil_div(
            FROZEN_A004_MARKED_NUMERATOR - 2 * side_sum,
            FROZEN_A004_INCIDENCE_CAP,
        )
        access = max(ordinary, marked)
        total = width * height + access
        variables.append(
            {
                "id": variable_id,
                "name": f"dimension__w_{width:02d}__h_{height:02d}",
                "kind": "oriented_dimension_selector",
                "width": width,
                "height": height,
                "area": width * height,
                "minimum_side": min(width, height),
                "side_sum": side_sum,
                "marked_bound_applicable": min(width, height) >= FROZEN_A004_MARKED_MINIMUM_SIDE,
                "ordinary_access_lower_bound": ordinary,
                "marked_access_lower_bound": marked,
                "access_lower_bound": access,
                "total_required_cells": total,
                "coefficient": free_cell_cap - total,
                "full_span": width == grid_width or height == grid_height,
            }
        )
    full_span = [variable for variable in variables if variable["full_span"]]
    positive = [variable for variable in variables if variable["coefficient"] > 0]
    negative = [variable for variable in variables if variable["coefficient"] < 0]
    zero = [variable for variable in variables if variable["coefficient"] == 0]
    arithmetic_survivors = [
        [variable["width"], variable["height"]]
        for variable in variables
        if variable["coefficient"] >= 0
    ]
    require(
        len(variables) == EXPECTED_VARIABLES
        and len(full_span) == EXPECTED_FULL_SPAN
        and len(positive) == 2
        and len(negative) == 2082
        and not zero
        and arithmetic_survivors == [[17, 70], [70, 17]]
        and all(variable["full_span"] for variable in positive),
        "independent old-band arithmetic census mismatch",
    )

    variable_map = {
        "schema_version": VARIABLE_MAP_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "semantics": SEMANTICS,
        "variable_count": len(variables),
        "variables": variables,
    }
    variable_map_raw = json_bytes(variable_map)

    constraints = 1 + len(variables) + len(full_span)
    lines = [
        (
            f"* #variable= {len(variables)} #constraint= {constraints} "
            "#equal= 1 intsize= 64"
        ),
        (
            f"* model={MODEL_SCHEMA} generated_by={HARNESS} semantics={SEMANTICS} "
            "target=1188,22 "
            "given_inequality=wh+max(ceil((580-w-h)/4),"
            "ceil((678-2w-2h)/4))<=1320 "
            "full_span_forbidden=true"
        ),
        " ".join(f"+1 x{variable['id']}" for variable in variables) + " = 1 ;",
    ]
    for variable in variables:
        coefficient = variable["coefficient"]
        lines.append(f"{'+' if coefficient >= 0 else ''}{coefficient} x{variable['id']} >= 0 ;")
    for variable in full_span:
        lines.append(f"-1 x{variable['id']} >= 0 ;")
    formula_raw = ("\n".join(lines) + "\n").encode("ascii")
    require(constraints == EXPECTED_CONSTRAINTS, "independent OPB constraint count mismatch")
    require(
        len(variable_map_raw) == CONTENT_ANCHORS[member_key("variable_map.json")]["size_bytes"]
        and sha256(variable_map_raw) == CONTENT_ANCHORS[member_key("variable_map.json")]["sha256"],
        "independent variable-map byte reconstruction mismatch",
    )
    require(
        len(formula_raw) == CONTENT_ANCHORS[member_key("formula.opb")]["size_bytes"]
        and sha256(formula_raw) == CONTENT_ANCHORS[member_key("formula.opb")]["sha256"],
        "independent OPB byte reconstruction mismatch",
    )
    return {
        "formula_raw": formula_raw,
        "variable_map_raw": variable_map_raw,
        "report": {
            "grid": [grid_width, grid_height],
            "strict_required_body_area": required_body_area,
            "strict_pole_body_area": pole_area,
            "frozen_a004_minimum_poles": FROZEN_A004_MINIMUM_POLES,
            "free_cell_cap": free_cell_cap,
            "old_upper": [TARGET_AREA, TARGET_MIN_SIDE],
            "complete_oriented_band_count": len(dimensions),
            "selector_variables": len(variables),
            "constraints": constraints,
            "full_span_forbid_constraints": len(full_span),
            "positive_arithmetic_coefficients": len(positive),
            "negative_arithmetic_coefficients": len(negative),
            "arithmetic_survivors": arithmetic_survivors,
            "final_survivors": [],
            "formula_size_bytes": len(formula_raw),
            "formula_sha256": sha256(formula_raw),
            "variable_map_size_bytes": len(variable_map_raw),
            "variable_map_sha256": sha256(variable_map_raw),
            "exact_bytes_reconstructed": True,
            "conditional_on_frozen_a004_lemmas": True,
        },
    }


def parse_veripb_output(stdout: bytes, stderr: bytes, returncode: int) -> dict[str, Any]:
    try:
        stdout_text = stdout.decode("utf-8")
        stderr_text = stderr.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OldUpperVerificationError(f"VeriPB output is not UTF-8: {exc}") from exc
    status_lines = [
        line.strip()
        for line in (*stdout_text.splitlines(), *stderr_text.splitlines())
        if line.strip().startswith("s ")
    ]
    require(returncode == 0, f"VeriPB exited with {returncode}")
    require(stderr_text == "", "VeriPB wrote stderr")
    require(status_lines == ["s VERIFIED UNSATISFIABLE"], "VeriPB exact status line mismatch")
    return {
        "exit_code": returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "status_lines": status_lines,
        "proof_status": "VERIFIED UNSATISFIABLE",
    }


def _execute_veripb(
    veripb_fd: int,
    formula_fd: int,
    proof_fd: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Execute the retained verifier against retained formula/proof descriptors."""

    require(type(timeout_seconds) is int and timeout_seconds > 0, "VeriPB timeout must be a positive exact integer")
    fd_paths = {
        "veripb": f"/proc/self/fd/{veripb_fd}",
        "formula": f"/proc/self/fd/{formula_fd}",
        "proof": f"/proc/self/fd/{proof_fd}",
    }
    try:
        completed = subprocess.run(
            [
                fd_paths["veripb"],
                "--opb",
                "--stats",
                fd_paths["formula"],
                fd_paths["proof"],
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            pass_fds=(veripb_fd, formula_fd, proof_fd),
            close_fds=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise OldUpperVerificationError(f"VeriPB timed out after {timeout_seconds}s") from exc
    result = parse_veripb_output(completed.stdout, completed.stderr, completed.returncode)
    result["argv_shape"] = [
        "retained_veripb_fd",
        "--opb",
        "--stats",
        "retained_formula_fd",
        "retained_proof_fd",
    ]
    result["execution"] = "retained_proc_self_fd_with_pass_fds"
    return result


def verify_old_upper(
    snapshot_paths: Mapping[str, Path],
    pinned_inputs: Mapping[str, Mapping[str, Any]],
    veripb_path: Path,
    veripb_pin: Mapping[str, Any],
    *,
    verifier_timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Verify the old complete-band authority using only supplied fresh snapshots.

    ``snapshot_paths`` and ``pinned_inputs`` must contain exactly
    :data:`REQUIRED_INPUT_KEYS`.  Every input pin is the exact
    ``{"identity", "content_projection"}`` join object.  ``veripb_pin`` may be
    that join object or the direct full7 logical identity stored at
    ``authority["binaries"]["veripb"]``.
    """

    require(set(snapshot_paths) == set(REQUIRED_INPUT_KEYS), "snapshot path key set mismatch")
    require(set(pinned_inputs) == set(REQUIRED_INPUT_KEYS), "snapshot pin key set mismatch")
    normalized_pins = {
        name: _normalize_pin(pinned_inputs[name], f"pinned input {name}")
        for name in REQUIRED_INPUT_KEYS
    }
    veripb_identity, veripb_projection = _normalize_veripb_pin(veripb_pin)

    with ExitStack() as stack:
        snapshots: dict[str, RetainedSnapshot] = {}
        for name in REQUIRED_INPUT_KEYS:
            expected_identity, expected_projection = normalized_pins[name]
            snapshot = _open_retained(
                Path(snapshot_paths[name]),
                expected_identity,
                expected_projection,
                CONTENT_ANCHORS[name],
                name,
            )
            stack.callback(snapshot.close)
            snapshots[name] = snapshot
        veripb = _open_retained(
            veripb_path,
            veripb_identity,
            veripb_projection,
            VERIPB_ANCHOR,
            "veripb",
        )
        stack.callback(veripb.close)

        paths = [snapshot.identity["path"] for snapshot in snapshots.values()]
        objects = [(snapshot.identity["device"], snapshot.identity["inode"]) for snapshot in snapshots.values()]
        require(len(paths) == len(set(paths)), "snapshot paths are not unique")
        require(len(objects) == len(set(objects)), "snapshot files are aliases of one physical object")

        raw_manifest = parse_sha256_manifest(
            snapshots["old_r4_raw_manifest"].raw,
            FORMAL_MANIFEST_MEMBERS,
            "old R4 formal manifest",
        )
        for filename, digest in raw_manifest.items():
            key = FORMAL_MEMBER_KEYS[filename]
            require(
                digest == snapshots[key].identity["sha256"],
                f"old R4 formal manifest: {filename} hash mismatch",
            )
        build_manifest = parse_sha256_manifest(
            snapshots[member_key("build_authority.SHA256SUMS")].raw,
            BUILD_MANIFEST_MEMBERS,
            "old R4 build manifest",
        )
        require(build_manifest == BUILD_MANIFEST_HASHES, "old R4 build manifest: immutable graph mismatch")

        a004_payload = strict_json(snapshots["old_r4_a004_admission"].raw, "A004 admission")
        a004_report = verify_a004_admission(a004_payload)
        receipt_payload = strict_json(snapshots["old_r4_receipt"].raw, "old R4 receipt")
        toolchain_payload = strict_json(snapshots["old_r4_toolchain_record"].raw, "old R4 toolchain")
        build_payload = strict_json(
            snapshots[member_key("build_authority.record.json")].raw,
            "old R4 build record",
        )
        gate_payload = strict_json(
            snapshots[member_key("translation_gate.json")].raw,
            "old R4 translation gate",
        )
        gate_recheck_payload = strict_json(
            snapshots[member_key("translation_gate.recheck.json")].raw,
            "old R4 translation gate recheck",
        )
        require(gate_payload == gate_recheck_payload, "translation gate recheck bytes/semantics drifted")
        graph_report = verify_receipt_graph(
            receipt_payload,
            toolchain_payload,
            build_payload,
            gate_payload,
            a004_payload,
            raw_manifest,
            build_manifest,
        )

        reconstruction = reconstruct_old_model(
            strict_json(snapshots["strict_instance"].raw, "strict instance")
        )
        require(
            reconstruction["formula_raw"] == snapshots[member_key("formula.opb")].raw,
            "fresh formula snapshot differs from independent exact reconstruction",
        )
        require(
            reconstruction["variable_map_raw"] == snapshots[member_key("variable_map.json")].raw,
            "fresh variable-map snapshot differs from independent exact reconstruction",
        )

        historical_status = parse_veripb_output(
            snapshots[member_key("veripb.stdout.txt")].raw,
            snapshots[member_key("veripb.stderr.txt")].raw,
            0,
        )
        formula = snapshots[member_key("formula.opb")]
        proof = snapshots[member_key("roundingsat.proof.pbp")]
        formula.check_stable(rehash=True)
        proof.check_stable(rehash=True)
        veripb.check_stable(rehash=True)
        detached_veripb = _execute_veripb(
            veripb.fd,
            formula.fd,
            proof.fd,
            verifier_timeout_seconds,
        )
        formula.check_stable(rehash=True)
        proof.check_stable(rehash=True)
        veripb.check_stable(rehash=True)
        for snapshot in snapshots.values():
            snapshot.check_stable()

        checks = {
            "fresh_snapshot_key_sets_exact": True,
            "full7_and_canonical_projection_join_exact": True,
            "immutable_content_anchors_exact": True,
            "formal_manifest_all_20_members_closed": len(raw_manifest) == 20,
            "build_manifest_and_record_graph_closed": True,
            "receipt_toolchain_formula_proof_graph_closed": True,
            "a004_admission_frozen_and_stable": graph_report["a004_authority_stable"] is True,
            "complete_2084_band_independently_enumerated": (
                reconstruction["report"]["complete_oriented_band_count"] == EXPECTED_VARIABLES
            ),
            "exact_2084_variable_map_reconstructed": (
                reconstruction["report"]["selector_variables"] == EXPECTED_VARIABLES
            ),
            "exact_2192_constraint_opb_reconstructed": (
                reconstruction["report"]["constraints"] == EXPECTED_CONSTRAINTS
            ),
            "historical_veripb_status_exact": historical_status["proof_status"] == "VERIFIED UNSATISFIABLE",
            "detached_veripb_status_exact": detached_veripb["proof_status"] == "VERIFIED UNSATISFIABLE",
            "formula_proof_veripb_same_fd_stable": True,
            "resource_and_cleanup_evidence_closed": graph_report["resource_and_cleanup_evidence_closed"] is True,
        }
        require(all(checks.values()), "old upper verification checks did not all pass")
        detached_veripb_report = {
            "exit_code": detached_veripb["exit_code"],
            "status_lines": detached_veripb["status_lines"],
            "proof_status": detached_veripb["proof_status"],
            "stderr_empty": detached_veripb["stderr"] == "",
            "argv_shape": detached_veripb["argv_shape"],
            "execution": detached_veripb["execution"],
        }
        bindings = {
            name: {
                "identity": snapshots[name].identity,
                "content_projection": canonical_content_projection(
                    snapshots[name].identity,
                    f"report input {name}",
                ),
            }
            for name in REQUIRED_INPUT_KEYS
        }
        return {
            "schema_version": SCHEMA,
            "status": "PASS",
            "decision": "OLD_R4_COMPLETE_BAND_AUTHORITY_RECOVERED_FROM_FRESH_SNAPSHOTS",
            "inputs": bindings,
            "veripb": {
                "identity": veripb.identity,
                "content_projection": canonical_content_projection(
                    veripb.identity,
                    "report veripb",
                ),
            },
            "a004_admission": a004_report,
            "receipt_and_manifest_graph": graph_report,
            "independent_reconstruction": reconstruction["report"],
            "historical_veripb": {
                "proof_status": historical_status["proof_status"],
                "status_lines": historical_status["status_lines"],
            },
            # Do not persist VeriPB's timing/statistics text: the exact terminal
            # status is checked above, while omitting volatile timing keeps
            # detached report bytes reproducible.
            "detached_veripb": detached_veripb_report,
            "checks": checks,
            "upper_bound_update_authorized": False,
            "claim_boundary": {
                "establishes_only": (
                    "the complete 2084-orientation lex-better band above (1188,22) "
                    "is machine-verified UNSAT conditional on the frozen A004-admitted "
                    "geometric lemmas"
                ),
                "ledger_upper_remains": [1188, 22],
                "lower_remains": "absent",
                "requires_smm4_composition_formal_attempt_and_detached_receipt": True,
                "attainability": False,
                "optimality": False,
                "whole_instance_infeasibility": False,
                "production_certified": False,
            },
        }


def write_once(path: Path, raw: bytes) -> None:
    raw_path = os.fspath(path)
    raw_parent = os.fspath(path.parent)
    require(
        os.path.isabs(raw_path) and os.path.normpath(raw_path) == raw_path,
        "output: path must be canonical absolute",
    )
    require(os.path.realpath(raw_parent) == raw_parent, "output: parent contains alias")
    require(path.parent.is_dir() and not path.parent.is_symlink(), "output: parent is not a real directory")
    require(not path.exists() and not path.is_symlink(), "output: already exists")
    fd = os.open(
        raw_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            require(written > 0, "output: short write")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verifier-timeout-seconds", type=int, default=300)
    arguments = parser.parse_args(argv)
    try:
        pins_raw, _ = snapshot_regular(arguments.pins, "old-upper pins")
        pins = parse_pins(pins_raw)
        paths = {
            name: Path(pins["inputs"][name]["identity"]["path"])
            for name in REQUIRED_INPUT_KEYS
        }
        report = verify_old_upper(
            paths,
            pins["inputs"],
            Path(pins["veripb"]["identity"]["path"]),
            pins["veripb"],
            verifier_timeout_seconds=arguments.verifier_timeout_seconds,
        )
        output_raw = json_bytes(report)
        write_once(arguments.output, output_raw)
    except (IdentityContractError, OldUpperVerificationError, OSError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "decision": report["decision"],
                "output": str(arguments.output),
                "size_bytes": len(output_raw),
                "sha256": sha256(output_raw),
                "upper_bound_update_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
