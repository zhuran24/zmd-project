#!/usr/bin/env python3
"""Independently verify a sealed R4 handoff package and append a receipt."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Any
import uuid
import zipfile


RECEIPT_SCHEMA = "r4_handoff_package_verification_receipt_v1"
MANIFEST_SCHEMA = "r4_handoff_package_manifest_v1"
SOURCE_SCHEMA = "r4_handoff_source_identities_v1"
BUILD_SCHEMA = "r4_handoff_build_record_v1"
ATTACHMENT_SCHEMA = "r4_handoff_attachment_list_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_PYTHON_PATH = PROJECT_ROOT / ".venv/bin/python"
W2D_ROOT = Path("/home/zhuran24/zmd-pj-codex-baselines/witness-ea407fa-20260720")
W2D_FORBIDDEN_ROOT = Path("/home/zhuran24/zmd-pj-codex-worktrees/witness-ea407fa-20260720")
W2D_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
STRICT_DIR = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external"
METHODOLOGY = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718/strict/internal/R3_methodology_brief.md"
STATUS_BRIEF = PROJECT_ROOT / "docs/research/r4_external_brain_handoff_20260722/02_current_status_brief.md"
CORE_PLAN = Path("/home/zhuran24/zmd-pj-codex/核心计划书.md")
R3_DIR = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718"
B0_RUN = PROJECT_ROOT / ".artifacts/track_b_b0_1190_34/formal-a001-20260721T221107Z-398f8725"
B1_R1_RUN = PROJECT_ROOT / ".artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW"
B1_R2_RUN = (
    PROJECT_ROOT
    / ".artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF"
    / "scan/diagnostic-corpus-v2"
)
W2D_REPORT_DIR = W2D_ROOT / "docs/research/witness_constructor_20260717/07_routing_aware"
EXPECTED_PACKAGE_MEMBERS = frozenset(
    {
        "attachments/strict-trio.zip",
        "attachments/methodology-brief.md",
        "attachments/current-status-brief.md",
        "operator/r4-questions.md",
        "operator/SUBMISSION_CHECKLIST.md",
        "control/source-identities.json",
        "control/build-record.json",
        "control/attachment-list.json",
    }
)
EXPECTED_DIRS = frozenset({"attachments", "operator", "control"})
EXPECTED_SHA = {
    "core_plan": "0987d2d0a22da57b72ee94e3eb4d232a7389461f2ed031764d938a0789157422",
    "strict.problem": "c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f",
    "strict.instance": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    "strict.schema": "5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23",
    "methodology_brief": "30e759cca8aad7a86dc6d59c1827cfa13bf3013b60822ee6828aea7791cd1080",
    "r3.response_09": "f0670a76fbd57cabcd41d50823421921d336b50fd36da61e6ab5b2f408c4a700",
    "r3.adversarial_verdict_11": "d48ba75040c61d042d091a893f0331b837ebc994d2b18ad429bcb9fef4856da0",
    "r3.recomputation_tool": "589b87a086f2c25015b535c5c12d68b6842aaa1f16fe449bcb94e3a733bd076a",
    "b0.artifact_manifest": "9901f793201391eb7473c5035034b94847292c35fb367cab32a2c09cb557620c",
    "b0.formula": "cd578dd972dd1bf7609e5190aff2649c3ffdce0d123b7815c81ac63f6e5346e3",
    "b0.proof": "a6a7df1cedaabeee7271fa624f8627e5f666c9c77859df4d697577eec305fe4f",
    "b0.translation_recheck": "8ed3b07a8eedd208960c49abec7b3f0bd5ed3c8cacde3305d29d221153476417",
    "b0.toolchain_record": "0d18e112ca4b55ba2a01ba36139f86a5bc163cd3001e189002aa2623c0c77b06",
    "b1_r1.coordinate": "0fa96587f4eb1043b02924e4fced8a682b0da0c09278d7b4aeb704aa74c8a254",
    "b1_r1.independent": "9164064e201ac2d3128fbd7b1e0bc154b7cd1d0fd3f5588d3b51a6d575f6b952",
    "b1_r1.agreement": "b1f8ee3cf01b43de97da955e736102c86d65c5b61d01205ad8ff505f6a5b2c65",
    "b1_r1.estimate": "2fe8ca7a0b3b2ecd71e56a3bed1034db03a67d6eb47a07c08c3fb22319f66a95",
    "b1_r1.opb": "0c5a2ea2dd0a978de07cf91120cd81d79e39169e01757da9268b0f044afeef1b",
    "b1_r1.metadata": "c0f5fabcfadecd035f291e2e32375af916f0594be665f4ea6e0363422cfde7dc",
    "b1_r1.var_map": "97b03894b69f6d51df2d25e2543aac3989a0495342f050ecb8e092b8977d4c1f",
    "b1_r1.translation_gate": "45363308076ae6fcd837f349e3769bc6e1ad0b4bc8f660b0fa3dc475d20d2bf2",
    "b1_r2.batch_identity": "b84372559710eb137556206555bfcaa383603134543b593cfd47556a5b634622",
    "b1_r2.run_index": "bc526250e939bbf515f4329b85337a30407b19c0e487252519acea42bd473236",
    "b1_r2.completion": "00087d6024ec516452282719f335f7ee966de2d4198c5bb7730ba9c08f2685f2",
    "b1_r2.complete_event": "2da5ef745c0163989ca982f5d15255d9955765669386f0642db8806f6dbdbc39",
    "w2d.report_markdown": "664547dfffb0c05213d21908f0a66dab70c6029797a9a714464e72bbf1fd4bc9",
    "w2d.report_json": "8dc19571cdf5ff0912346a3acbdb4a885d2e092d1a7a74d6db01a8f3a64507e0",
}
DYNAMIC_ROLES = frozenset({"status_brief_source", "package_builder_tool", "b0.readme", "b1_r1.readme", "b1_r2.readme"})
EXPECTED_PATH = {
    "core_plan": CORE_PLAN,
    "strict.problem": STRICT_DIR / "problem.md",
    "strict.instance": STRICT_DIR / "problem_instance.json",
    "strict.schema": STRICT_DIR / "problem_instance.schema.json",
    "methodology_brief": METHODOLOGY,
    "r3.response_09": R3_DIR / "09_r3_response_gpt_pro_verbatim.md",
    "r3.adversarial_verdict_11": R3_DIR / "11_r3_adversarial_verdict_20260720.md",
    "r3.recomputation_tool": R3_DIR / "verify_r3_certificates.py",
    "b0.artifact_manifest": B0_RUN / "SHA256SUMS",
    "b0.formula": B0_RUN / "formula.opb",
    "b0.proof": B0_RUN / "roundingsat.proof.pbp",
    "b0.translation_recheck": B0_RUN / "translation_gate.recheck.json",
    "b0.toolchain_record": B0_RUN / "toolchain_record.json",
    "b1_r1.coordinate": B1_R1_RUN / "coordinate.json",
    "b1_r1.independent": B1_R1_RUN / "independent.json",
    "b1_r1.agreement": B1_R1_RUN / "agreement.json",
    "b1_r1.estimate": B1_R1_RUN / "band-estimate-v2.json",
    "b1_r1.opb": B1_R1_RUN / "band-v2.opb",
    "b1_r1.metadata": B1_R1_RUN / "band-v2.meta.json",
    "b1_r1.var_map": B1_R1_RUN / "band-v2.var-map.json",
    "b1_r1.translation_gate": B1_R1_RUN / "band-v3.translation-gate.json",
    "b1_r2.batch_identity": B1_R2_RUN / "batch-identity.json",
    "b1_r2.run_index": B1_R2_RUN / "run-index.json",
    "b1_r2.completion": B1_R2_RUN / "diagnostic-completion.json",
    "b1_r2.complete_event": B1_R2_RUN / "status-events/status-1784701903920514022.json",
    "w2d.report_markdown": W2D_REPORT_DIR / "08_track_w_w2d_failure_report_20260721.md",
    "w2d.report_json": W2D_REPORT_DIR / "08_track_w_w2d_failure_report_20260721.json",
    "status_brief_source": STATUS_BRIEF,
    "package_builder_tool": Path(__file__).with_name("build_r4_handoff_package_v1.py"),
    "b0.readme": PROJECT_ROOT / "docs/research/r3_upper_bound_pb_20260722/README.md",
    "b1_r1.readme": PROJECT_ROOT / "docs/research/b1_q_membrane_halo_20260722/README.md",
    "b1_r2.readme": PROJECT_ROOT / "docs/research/b1_conditional_halo_20260722/README.md",
}

QUESTION_1 = (
    "Produce the next certificate: push the upper bound strictly below (1190,34). "
    "Requirement: every quantitative claim must be verifiable by a standalone "
    "script of <200 lines that we can run against the instance JSON."
)
QUESTION_2 = (
    "Given this construction stuck-point: the current fixed-x67 campaign keeps "
    "a protected 6x7 rectangle at (7,34) and a 17-component/35-pole skeleton. "
    "Its composer enumerated exactly two exact count-closure manifests, both "
    "requiring c3 target (12,4,3). In the pinned local sound-cut model, the "
    "decisive run imported 7,156 sound cuts, added 12 (7,168 total), used no "
    "candidate no-good, and returned INFEASIBLE / SOUND_CUT_MODEL_INFEASIBLE; "
    "c0, c1, c2, and x67 c5 remain UNKNOWN, and assembly, routing, layout "
    "acceptance, and a witness lower bound were never reached. This closes only "
    "this fixed skeleton and these two manifests, not other constructions or "
    "global feasibility, propose the single most promising unblocking move."
)
QUESTIONS_BYTES = (f"# R4 questions\n\n1. {QUESTION_1}\n\n2. {QUESTION_2}\n").encode()
CHECKLIST_BYTES = b"""# Manual submission checklist

- Upload exactly `attachments/strict-trio.zip`.
- Upload exactly `attachments/methodology-brief.md`.
- Upload exactly `attachments/current-status-brief.md`.
- Paste `operator/r4-questions.md` verbatim.
- Do not upload `control/`, `package-manifest.json`, or `SHA256SUMS`.
- Do not alter the questions, attachments, gates, or claim boundary.
- Stop after manual submission and preserve the raw response as inert bytes.
"""


class VerificationError(RuntimeError):
    """The package or receipt failed closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes, label: str) -> Mapping[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise VerificationError("INVALID_JSON", f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise VerificationError("INVALID_JSON", f"{label}: non-finite number {value}")

    try:
        value = json.loads(data.decode(), object_pairs_hook=pairs, parse_constant=reject)
    except VerificationError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError("INVALID_JSON", f"{label}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise VerificationError("INVALID_JSON", f"{label}: root is not an object")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _safe_relative(raw: str) -> PurePosixPath:
    pure = PurePosixPath(raw)
    if (
        not raw
        or pure.is_absolute()
        or raw != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or "\\" in raw
    ):
        raise VerificationError("UNSAFE_PATH", f"unsafe path: {raw!r}")
    return pure


def _read_regular(path: Path, label: str) -> bytes:
    try:
        mode = path.lstat().st_mode
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise VerificationError("MISSING_OR_NONREGULAR", f"{label}: {exc}") from exc
    if path.absolute() != resolved or stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise VerificationError("MISSING_OR_NONREGULAR", f"{label}: not a canonical regular file")
    return path.read_bytes()


def _record(path: Path) -> dict[str, Any]:
    data = _read_regular(path, str(path))
    return {"path": str(path.absolute()), "sha256": _sha(data), "size_bytes": len(data)}


def _git_identity(root: Path, *, w2d: bool = False) -> dict[str, Any]:
    def run(*args: str, allowed: frozenset[int] = frozenset({0})) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if result.returncode not in allowed:
            raise VerificationError("REPOSITORY_IDENTITY", f"git {' '.join(args)} failed")
        return result

    top = run("rev-parse", "--show-toplevel").stdout.strip()
    head = run("rev-parse", "HEAD").stdout.strip()
    symbolic = run("symbolic-ref", "-q", "HEAD", allowed=frozenset({0, 1}))
    identity = {"detached_head": symbolic.returncode == 1, "head": head, "root": str(root)}
    if Path(top) != root:
        raise VerificationError("REPOSITORY_IDENTITY", f"unexpected Git top-level for {root}")
    if w2d and (root == W2D_FORBIDDEN_ROOT or head != W2D_HEAD or not identity["detached_head"]):
        raise VerificationError("REPOSITORY_IDENTITY", "W2d fixed detached authority mismatch")
    return identity


def _parse_sha_file(data: bytes) -> dict[str, str]:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise VerificationError("PARTIAL_SEAL", f"SHA256SUMS is not ASCII: {exc}") from exc
    entries: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\x00\r\n]+)", line)
        if match is None:
            raise VerificationError("PARTIAL_SEAL", f"malformed checksum line {number}")
        digest, raw = match.groups()
        _safe_relative(raw)
        if raw == "SHA256SUMS" or raw in entries:
            raise VerificationError("PARTIAL_SEAL", f"cyclic/duplicate checksum path: {raw}")
        entries[raw] = digest
    if not entries or list(entries) != sorted(entries):
        raise VerificationError("PARTIAL_SEAL", "checksum paths are empty or unsorted")
    return entries


def _package_files(package: Path) -> tuple[dict[str, bytes], set[str]]:
    files: dict[str, bytes] = {}
    directories: set[str] = set()
    for path in sorted(package.rglob("*"), key=lambda item: item.relative_to(package).as_posix()):
        relative = path.relative_to(package).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise VerificationError("PACKAGE_CONTENT", f"symlink in package: {relative}")
        if stat.S_ISDIR(mode):
            directories.add(relative)
        elif stat.S_ISREG(mode):
            files[relative] = path.read_bytes()
        else:
            raise VerificationError("PACKAGE_CONTENT", f"non-regular package object: {relative}")
    return files, directories


def _strict_zip_from_current() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True) as archive:
        for name in sorted(("problem.md", "problem_instance.json", "problem_instance.schema.json")):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.extra = b""
            info.comment = b""
            archive.writestr(info, _read_regular(STRICT_DIR / name, name))
        archive.comment = b""
    return stream.getvalue()


def _b0_manifest_replay_exact() -> bool:
    """Recheck every current member named by the pinned B0 checksum manifest."""

    try:
        lines = _read_regular(B0_RUN / "SHA256SUMS", "B0 SHA256SUMS").decode("ascii").splitlines()
    except (UnicodeError, VerificationError):
        return False
    if len(lines) != 17:
        return False
    seen: set[str] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if match is None:
            return False
        digest, name = match.groups()
        if name in seen:
            return False
        seen.add(name)
        try:
            if _sha(_read_regular(B0_RUN / name, f"B0 manifest member {name}")) != digest:
                return False
        except VerificationError:
            return False
    return True


def _embedded_w2d_records(value: Any, pointer: str = "") -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    if isinstance(value, Mapping):
        path, digest = value.get("path"), value.get("sha256")
        if isinstance(path, str) and isinstance(digest, str) and path.startswith("recovery_runs/"):
            result[f"w2d.embedded{pointer or '/'}"] = (path, digest)
        for key, item in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            result.update(_embedded_w2d_records(item, f"{pointer}/{token}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            result.update(_embedded_w2d_records(item, f"{pointer}/{index}"))
    return result


def _contains_forbidden_key(value: Any, forbidden: frozenset[str]) -> bool:
    if isinstance(value, Mapping):
        return bool(forbidden.intersection(value)) or any(
            _contains_forbidden_key(item, forbidden) for item in value.values()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False


def _status_brief_exact(data: bytes) -> bool:
    try:
        text = data.decode()
        response = _read_regular(R3_DIR / "09_r3_response_gpt_pro_verbatim.md", "R3 response")
    except (UnicodeError, VerificationError):
        return False
    required = (
        "c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f",
        "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
        "5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23",
        "30e759cca8aad7a86dc6d59c1827cfa13bf3013b60822ee6828aea7791cd1080",
        "formal-a001-20260721T221107Z-398f8725",
        "run-20260722T0902-nGEfoW",
        "run-20260722T015946Z-zkMRiF",
        "664547dfffb0c05213d21908f0a66dab70c6029797a9a714464e72bbf1fd4bc9",
        "8dc19571cdf5ff0912346a3acbdb4a885d2e092d1a7a74d6db01a8f3a64507e0",
        "Track B/B1: STOP",
        "U=(1190,34)",
        "L=absent",
    )
    start, end = response.find(b"## 2.2 Certificate A"), response.find(b"## 2.4")
    return all(item in text for item in required) and 0 <= start < end and data.count(response[start:end]) == 1


def _source_replay(source_payload: Mapping[str, Any]) -> tuple[bool, list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    current: list[dict[str, Any]] = []
    raw_sources = source_payload.get("sources")
    if (
        set(source_payload)
        != {
            "repository_identities",
            "schema_version",
            "sources",
            "w2d_authority_kind",
            "w2d_forbidden_fallback",
        }
        or source_payload.get("schema_version") != SOURCE_SCHEMA
        or source_payload.get("w2d_authority_kind")
        != "dirty_untracked_byte_authority_in_independent_detached_repository"
        or source_payload.get("w2d_forbidden_fallback") != str(W2D_FORBIDDEN_ROOT)
        or not isinstance(raw_sources, Sequence)
    ):
        return False, current, ["source_identity_schema"]
    roles: dict[str, Mapping[str, Any]] = {}
    for raw in raw_sources:
        if not isinstance(raw, Mapping) or set(raw) != {"path", "role", "sha256", "size_bytes"}:
            errors.append("source_record_shape")
            continue
        role = raw.get("role")
        if not isinstance(role, str) or role in roles:
            errors.append("source_role_duplicate_or_invalid")
            continue
        roles[role] = raw
        try:
            record = _record(Path(str(raw["path"]))) | {"role": role}
        except (OSError, VerificationError):
            errors.append(f"source_unreadable:{role}")
            continue
        current.append(record)
        if record != dict(raw):
            errors.append(f"source_drift:{role}")
    required = set(EXPECTED_SHA) | DYNAMIC_ROLES
    embedded = {role for role in roles if role.startswith("w2d.embedded/")}
    if set(roles) != required | embedded or not embedded:
        errors.append("source_role_set")
    for role, digest in EXPECTED_SHA.items():
        raw = roles.get(role)
        if raw is None or raw.get("sha256") != digest:
            errors.append(f"pinned_sha:{role}")
    for role, path in EXPECTED_PATH.items():
        if roles.get(role, {}).get("path") != str(path.absolute()):
            errors.append(f"pinned_path:{role}")
    try:
        report = _json(_read_regular(EXPECTED_PATH["w2d.report_json"], "W2d report"), "W2d report")
        expected_embedded = _embedded_w2d_records(report)
    except VerificationError as exc:
        errors.append(f"w2d_report:{exc.code}")
        expected_embedded = {}
    if embedded != set(expected_embedded):
        errors.append("w2d_embedded_role_set")
    for role, (relative, digest) in expected_embedded.items():
        raw = roles.get(role, {})
        expected_path = W2D_REPORT_DIR.joinpath(*PurePosixPath(relative).parts)
        if raw.get("path") != str(expected_path) or raw.get("sha256") != digest:
            errors.append(f"w2d_embedded_identity:{role}")
    current.sort(key=lambda item: str(item["role"]))
    try:
        project_identity = _git_identity(PROJECT_ROOT)
        w2d_identity = _git_identity(W2D_ROOT, w2d=True)
    except VerificationError as exc:
        errors.append(exc.code)
    else:
        expected_repositories = {
            "package_worktree": project_identity,
            "w2d_independent_detached_repository": w2d_identity,
        }
        if source_payload.get("repository_identities") != expected_repositories:
            errors.append("repository_identity_drift")
    return not errors, current, errors


def _verification_payload(run_dir: Path, verification_id: str) -> dict[str, Any]:
    run = run_dir.resolve(strict=True)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", verification_id):
        raise VerificationError("INVALID_VERIFICATION_ID", "verification id is not canonical")
    checks = {
        "attachment_replay_exact": False,
        "b0_manifest_replay_exact": False,
        "build_record_preseal_only": False,
        "current_source_identities_exact": False,
        "manifest_domain_exact": False,
        "package_tree_exact": False,
        "sha_seal_exact": False,
        "source_schema_exact": False,
        "w2d_fixed_detached_authority_exact": False,
    }
    errors: list[str] = []
    package_id: str | None = None
    manifest_sha: str | None = None
    sha_sha: str | None = None
    current_sources: list[dict[str, Any]] = []
    try:
        package = run / "package"
        files, directories = _package_files(package)
        checks["package_tree_exact"] = directories == EXPECTED_DIRS and set(files) == (
            EXPECTED_PACKAGE_MEMBERS | {"package-manifest.json", "SHA256SUMS"}
        )
        if not checks["package_tree_exact"]:
            errors.append("package_tree_exact")
        sha_data = files["SHA256SUMS"]
        sha_sha = package_id = _sha(sha_data)
        entries = _parse_sha_file(sha_data)
        covered = set(files) - {"SHA256SUMS"}
        checks["sha_seal_exact"] = set(entries) == covered and all(
            _sha(files[path]) == digest for path, digest in entries.items()
        )
        if not checks["sha_seal_exact"]:
            errors.append("sha_seal_exact")
        manifest_data = files["package-manifest.json"]
        manifest_sha = _sha(manifest_data)
        manifest = _json(manifest_data, "package manifest")
        source_payload = _json(files["control/source-identities.json"], "source identities")
        checks["source_schema_exact"] = source_payload.get("schema_version") == SOURCE_SCHEMA
        source_ok, current_sources, source_errors = _source_replay(source_payload)
        checks["b0_manifest_replay_exact"] = _b0_manifest_replay_exact()
        if not checks["b0_manifest_replay_exact"]:
            errors.append("b0_manifest_replay_exact")
        checks["current_source_identities_exact"] = source_ok
        checks["w2d_fixed_detached_authority_exact"] = not any(
            "w2d" in item.lower() or "repository" in item.lower() for item in source_errors
        )
        errors.extend(source_errors)
        members = manifest.get("package_members")
        expected_members = [
            {"path": path, "sha256": _sha(files[path]), "size_bytes": len(files[path])}
            for path in sorted(EXPECTED_PACKAGE_MEMBERS)
        ]
        manifest_keys = {
            "claim_boundary",
            "excluded_from_manifest_domain",
            "external_sources",
            "package_members",
            "repository_identities",
            "schema_version",
            "seal_contract",
        }
        expected_claim_boundary = {
            "b0_scope": "arithmetic UNSAT only given separately reviewed R3 geometry lemmas",
            "b1_scope": "two diagnostic rounds left U=(1190,34) and triggered process STOP",
            "lower_bound_ledger": "absent",
            "not_established": [
                "a new upper bound",
                "a witness or attainability",
                "global optimality or infeasibility",
                "production CERTIFIED evidence",
            ],
            "r4_scope": "local package ready for manual external submission only",
            "w2d_scope": "the fixed x67 campaign and its two exact count-closure manifests only",
        }
        expected_exclusions = [
            "package-manifest.json",
            "SHA256SUMS",
            "../verifications/",
            "../ready/",
            "package_id",
            "selected_receipt_identity",
        ]
        expected_seal_contract = {
            "package_id_definition": "sha256(SHA256SUMS exact bytes)",
            "sha256sums_covers": "all regular files under package except SHA256SUMS itself",
            "writes_after_sha256sums": "forbidden",
        }
        checks["manifest_domain_exact"] = (
            set(manifest) == manifest_keys
            and manifest.get("schema_version") == MANIFEST_SCHEMA
            and manifest.get("claim_boundary") == expected_claim_boundary
            and manifest.get("excluded_from_manifest_domain") == expected_exclusions
            and manifest.get("seal_contract") == expected_seal_contract
            and members == expected_members
            and manifest.get("external_sources") == source_payload.get("sources")
            and manifest.get("repository_identities") == source_payload.get("repository_identities")
            and "package-manifest.json" not in {item.get("path") for item in members if isinstance(item, Mapping)}
            and not _contains_forbidden_key(
                manifest,
                frozenset({"package_id", "selected_receipt_identity", "receipt_path"}),
            )
        )
        if not checks["manifest_domain_exact"]:
            errors.append("manifest_domain_exact")
        build = _json(files["control/build-record.json"], "build record")
        forbidden = {
            "package_id",
            "manifest_sha256",
            "sha256sums_sha256",
            "receipt",
            "selected_receipt_identity",
            "status",
        }
        source_by_role = {
            item.get("role"): item
            for item in source_payload.get("sources", [])
            if isinstance(item, Mapping) and isinstance(item.get("role"), str)
        }
        python_record = build.get("python")
        checks["build_record_preseal_only"] = (
            set(build)
            == {
                "argv",
                "builder",
                "free_bytes_before_build",
                "output_dir",
                "python",
                "schema_version",
                "state",
            }
            and build.get("schema_version") == BUILD_SCHEMA
            and build.get("state") == "PAYLOAD_PLAN_BEFORE_SEAL"
            and build.get("builder") == source_by_role.get("package_builder_tool")
            and build.get("output_dir") == str(run)
            and isinstance(build.get("argv"), list)
            and all(isinstance(item, str) for item in build.get("argv", []))
            and type(build.get("free_bytes_before_build")) is int
            and build.get("free_bytes_before_build", 0) >= 10_737_418_240
            and isinstance(python_record, Mapping)
            and set(python_record) == {"executable", "version"}
            and python_record.get("executable") == str(EXPECTED_PYTHON_PATH)
            and isinstance(python_record.get("version"), str)
            and python_record.get("version", "").startswith("3.13.")
            and not _contains_forbidden_key(build, frozenset(forbidden))
        )
        if not checks["build_record_preseal_only"]:
            errors.append("build_record_preseal_only")
        attachments = _json(files["control/attachment-list.json"], "attachment list")
        attachments_ok = (
            set(attachments)
            == {
                "attachment_count",
                "attachments",
                "operator_files_are_not_attachments",
                "schema_version",
            }
            and attachments.get("schema_version") == ATTACHMENT_SCHEMA
            and attachments.get("attachment_count") == 3
            and attachments.get("attachments")
            == [
                {"path": "attachments/strict-trio.zip", "role": "strict_trio_zip"},
                {"path": "attachments/methodology-brief.md", "role": "methodology_brief"},
                {"path": "attachments/current-status-brief.md", "role": "current_status_brief"},
            ]
            and attachments.get("operator_files_are_not_attachments")
            == [
                "operator/r4-questions.md",
                "operator/SUBMISSION_CHECKLIST.md",
            ]
        )
        try:
            status_current = _read_regular(STATUS_BRIEF, "status brief")
            methodology_current = _read_regular(METHODOLOGY, "methodology")
            zip_current = _strict_zip_from_current()
        except VerificationError:
            attachments_ok = False
        else:
            attachments_ok = attachments_ok and (
                files["attachments/current-status-brief.md"] == status_current
                and files["attachments/methodology-brief.md"] == methodology_current
                and files["attachments/strict-trio.zip"] == zip_current
                and files["operator/r4-questions.md"] == QUESTIONS_BYTES
                and files["operator/SUBMISSION_CHECKLIST.md"] == CHECKLIST_BYTES
                and _status_brief_exact(status_current)
            )
        checks["attachment_replay_exact"] = attachments_ok
        if not attachments_ok:
            errors.append("attachment_replay_exact")
    except (KeyError, OSError, VerificationError, ValueError) as exc:
        errors.append(f"{getattr(exc, 'code', type(exc).__name__)}:{exc}")
    errors = sorted(set(errors))
    status_value = "PASS" if all(checks.values()) and not errors else "FAIL"
    tool_data = _read_regular(Path(__file__).resolve(), "verifier tool")
    return {
        "checks": checks,
        "claim_boundary": [
            "package readiness for manual external submission only",
            "no upper-bound, witness, optimality, or production CERTIFIED claim",
        ],
        "corpus_errors": errors,
        "current_input_identities": current_sources,
        "manifest_sha256": manifest_sha,
        "package_id": package_id,
        "receipt_relative_path": f"verifications/{verification_id}/receipt.json",
        "schema_version": RECEIPT_SCHEMA,
        "sha256sums_sha256": sha_sha,
        "status": status_value,
        "verification_id": verification_id,
        "verifier_tool_sha256": _sha(tool_data),
    }


def _publish_receipt(path: Path, data: bytes) -> None:
    receipt_root = path.parent.parent
    receipt_root.mkdir(exist_ok=True)
    if receipt_root.is_symlink() or receipt_root.resolve() != receipt_root.absolute():
        raise VerificationError("NO_OVERWRITE_COLLISION", "verification root is not canonical")
    try:
        path.parent.mkdir()
    except FileExistsError as exc:
        raise VerificationError("NO_OVERWRITE_COLLISION", f"verification directory exists: {path.parent}") from exc
    pending = path.parent / f".pending-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(pending, path)
    except FileExistsError as exc:
        raise VerificationError("NO_OVERWRITE_COLLISION", f"receipt exists: {path}") from exc
    finally:
        pending.unlink(missing_ok=True)


def create_receipt(run_dir: Path, verification_id: str) -> dict[str, Any]:
    payload = _verification_payload(run_dir, verification_id)
    _publish_receipt(run_dir.resolve(strict=True) / payload["receipt_relative_path"], _canonical(payload))
    return payload


def check_receipt_semantics(receipt_path: Path) -> dict[str, Any]:
    """Read-only exact semantic replay for one sibling receipt."""

    receipt = receipt_path.absolute()
    _read_regular(receipt, "receipt")
    if receipt.name != "receipt.json" or receipt.parent.parent.name != "verifications":
        raise VerificationError("RECEIPT_PATH", "receipt is not at RUN/verifications/<id>/receipt.json")
    run_dir = receipt.parents[2]
    relative = receipt.relative_to(run_dir).as_posix()
    expected = _verification_payload(run_dir, receipt.parent.name)
    actual = _json(_read_regular(receipt, "receipt"), "receipt")
    if relative != expected["receipt_relative_path"] or dict(actual) != expected:
        raise VerificationError("RECEIPT_REPLAY_MISMATCH", "receipt fields do not match current semantic replay")
    if expected["status"] != "PASS":
        raise VerificationError("RECEIPT_NOT_PASS", "receipt replay is not a corpus-clean PASS")
    return dict(actual)


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verification-id")
    group.add_argument("--check-receipt", type=Path)
    parser.add_argument("--run-dir", type=Path, help="required when creating a receipt")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        if args.check_receipt is not None:
            payload = check_receipt_semantics(args.check_receipt)
            result = {"package_id": payload["package_id"], "receipt_semantic_replay": True, "status": "PASS"}
        else:
            if args.run_dir is None:
                raise VerificationError("MISSING_RUN_DIR", "--run-dir is required with --verification-id")
            payload = create_receipt(args.run_dir, args.verification_id)
            result = payload
    except (OSError, VerificationError) as exc:
        print(
            json.dumps(
                {"error_code": getattr(exc, "code", type(exc).__name__), "message": str(exc), "status": "FAIL"},
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
