#!/usr/bin/env python3
"""Build one immutable, research-only R4 external-brain handoff package.

The package authority is deliberately acyclic: external byte identities feed
immutable payload/control files, then ``package-manifest.json``, and finally
``SHA256SUMS``.  The checksum file is the seal.  This program never writes
under ``package/`` after that seal exists, and it never invokes a solver,
proof tool, browser, or network client.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator, Mapping, Sequence
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
from typing import Any
import uuid
import zipfile


SCHEMA = "r4_handoff_package_manifest_v1"
SOURCE_SCHEMA = "r4_handoff_source_identities_v1"
BUILD_SCHEMA = "r4_handoff_build_record_v1"
ATTACHMENT_SCHEMA = "r4_handoff_attachment_list_v1"
MIN_FREE_BYTES = 10_737_418_240

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_DIR = PROJECT_ROOT / "docs/research/r4_external_brain_handoff_20260722"
STATUS_BRIEF = RESEARCH_DIR / "02_current_status_brief.md"
CORE_PLAN = Path("/home/zhuran24/zmd-pj-codex/核心计划书.md")
W2D_ROOT = Path("/home/zhuran24/zmd-pj-codex-baselines/witness-ea407fa-20260720")
W2D_FORBIDDEN_ROOT = Path("/home/zhuran24/zmd-pj-codex-worktrees/witness-ea407fa-20260720")
W2D_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
W2D_REPORT_DIR = W2D_ROOT / "docs/research/witness_constructor_20260717/07_routing_aware"

STRICT_DIR = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718/strict"
STRICT_EXTERNAL = STRICT_DIR / "external"
STRICT_TRIO = (
    "problem.md",
    "problem_instance.json",
    "problem_instance.schema.json",
)
METHODOLOGY = STRICT_DIR / "internal/R3_methodology_brief.md"
R3_DIR = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718"
B0_RUN = PROJECT_ROOT / ".artifacts/track_b_b0_1190_34/formal-a001-20260721T221107Z-398f8725"
B1_R1_RUN = PROJECT_ROOT / ".artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW"
B1_R2_RUN = (
    PROJECT_ROOT
    / ".artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF"
    / "scan/diagnostic-corpus-v2"
)

EXPECTED_STATIC_SOURCES: tuple[tuple[str, Path, str], ...] = (
    (
        "core_plan",
        CORE_PLAN,
        "0987d2d0a22da57b72ee94e3eb4d232a7389461f2ed031764d938a0789157422",
    ),
    (
        "strict.problem",
        STRICT_EXTERNAL / "problem.md",
        "c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f",
    ),
    (
        "strict.instance",
        STRICT_EXTERNAL / "problem_instance.json",
        "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    ),
    (
        "strict.schema",
        STRICT_EXTERNAL / "problem_instance.schema.json",
        "5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23",
    ),
    (
        "methodology_brief",
        METHODOLOGY,
        "30e759cca8aad7a86dc6d59c1827cfa13bf3013b60822ee6828aea7791cd1080",
    ),
    (
        "r3.response_09",
        R3_DIR / "09_r3_response_gpt_pro_verbatim.md",
        "f0670a76fbd57cabcd41d50823421921d336b50fd36da61e6ab5b2f408c4a700",
    ),
    (
        "r3.adversarial_verdict_11",
        R3_DIR / "11_r3_adversarial_verdict_20260720.md",
        "d48ba75040c61d042d091a893f0331b837ebc994d2b18ad429bcb9fef4856da0",
    ),
    (
        "r3.recomputation_tool",
        R3_DIR / "verify_r3_certificates.py",
        "589b87a086f2c25015b535c5c12d68b6842aaa1f16fe449bcb94e3a733bd076a",
    ),
    (
        "b0.artifact_manifest",
        B0_RUN / "SHA256SUMS",
        "9901f793201391eb7473c5035034b94847292c35fb367cab32a2c09cb557620c",
    ),
    (
        "b0.formula",
        B0_RUN / "formula.opb",
        "cd578dd972dd1bf7609e5190aff2649c3ffdce0d123b7815c81ac63f6e5346e3",
    ),
    (
        "b0.proof",
        B0_RUN / "roundingsat.proof.pbp",
        "a6a7df1cedaabeee7271fa624f8627e5f666c9c77859df4d697577eec305fe4f",
    ),
    (
        "b0.translation_recheck",
        B0_RUN / "translation_gate.recheck.json",
        "8ed3b07a8eedd208960c49abec7b3f0bd5ed3c8cacde3305d29d221153476417",
    ),
    (
        "b0.toolchain_record",
        B0_RUN / "toolchain_record.json",
        "0d18e112ca4b55ba2a01ba36139f86a5bc163cd3001e189002aa2623c0c77b06",
    ),
    (
        "b1_r1.coordinate",
        B1_R1_RUN / "coordinate.json",
        "0fa96587f4eb1043b02924e4fced8a682b0da0c09278d7b4aeb704aa74c8a254",
    ),
    (
        "b1_r1.independent",
        B1_R1_RUN / "independent.json",
        "9164064e201ac2d3128fbd7b1e0bc154b7cd1d0fd3f5588d3b51a6d575f6b952",
    ),
    (
        "b1_r1.agreement",
        B1_R1_RUN / "agreement.json",
        "b1f8ee3cf01b43de97da955e736102c86d65c5b61d01205ad8ff505f6a5b2c65",
    ),
    (
        "b1_r1.estimate",
        B1_R1_RUN / "band-estimate-v2.json",
        "2fe8ca7a0b3b2ecd71e56a3bed1034db03a67d6eb47a07c08c3fb22319f66a95",
    ),
    (
        "b1_r1.opb",
        B1_R1_RUN / "band-v2.opb",
        "0c5a2ea2dd0a978de07cf91120cd81d79e39169e01757da9268b0f044afeef1b",
    ),
    (
        "b1_r1.metadata",
        B1_R1_RUN / "band-v2.meta.json",
        "c0f5fabcfadecd035f291e2e32375af916f0594be665f4ea6e0363422cfde7dc",
    ),
    (
        "b1_r1.var_map",
        B1_R1_RUN / "band-v2.var-map.json",
        "97b03894b69f6d51df2d25e2543aac3989a0495342f050ecb8e092b8977d4c1f",
    ),
    (
        "b1_r1.translation_gate",
        B1_R1_RUN / "band-v3.translation-gate.json",
        "45363308076ae6fcd837f349e3769bc6e1ad0b4bc8f660b0fa3dc475d20d2bf2",
    ),
    (
        "b1_r2.batch_identity",
        B1_R2_RUN / "batch-identity.json",
        "b84372559710eb137556206555bfcaa383603134543b593cfd47556a5b634622",
    ),
    (
        "b1_r2.run_index",
        B1_R2_RUN / "run-index.json",
        "bc526250e939bbf515f4329b85337a30407b19c0e487252519acea42bd473236",
    ),
    (
        "b1_r2.completion",
        B1_R2_RUN / "diagnostic-completion.json",
        "00087d6024ec516452282719f335f7ee966de2d4198c5bb7730ba9c08f2685f2",
    ),
    (
        "b1_r2.complete_event",
        B1_R2_RUN / "status-events/status-1784701903920514022.json",
        "2da5ef745c0163989ca982f5d15255d9955765669386f0642db8806f6dbdbc39",
    ),
    (
        "w2d.report_markdown",
        W2D_REPORT_DIR / "08_track_w_w2d_failure_report_20260721.md",
        "664547dfffb0c05213d21908f0a66dab70c6029797a9a714464e72bbf1fd4bc9",
    ),
    (
        "w2d.report_json",
        W2D_REPORT_DIR / "08_track_w_w2d_failure_report_20260721.json",
        "8dc19571cdf5ff0912346a3acbdb4a885d2e092d1a7a74d6db01a8f3a64507e0",
    ),
)

DYNAMIC_SOURCES: tuple[tuple[str, Path], ...] = (
    ("status_brief_source", STATUS_BRIEF),
    ("package_builder_tool", Path(__file__).resolve()),
    ("b0.readme", PROJECT_ROOT / "docs/research/r3_upper_bound_pb_20260722/README.md"),
    ("b1_r1.readme", PROJECT_ROOT / "docs/research/b1_q_membrane_halo_20260722/README.md"),
    ("b1_r2.readme", PROJECT_ROOT / "docs/research/b1_conditional_halo_20260722/README.md"),
)

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

PACKAGE_MEMBER_PATHS = frozenset(
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


class BuildError(RuntimeError):
    """The package could not be sealed without weakening its authority."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strict_json_bytes(data: bytes, label: str) -> Mapping[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise BuildError("INVALID_JSON", f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise BuildError("INVALID_JSON", f"{label}: non-finite number {value}")

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except BuildError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BuildError("INVALID_JSON", f"{label}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise BuildError("INVALID_JSON", f"{label}: root is not an object")
    return value


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _read_regular(path: Path, label: str) -> bytes:
    try:
        absolute = path.absolute()
        resolved = path.resolve(strict=True)
        mode = path.lstat().st_mode
    except OSError as exc:
        raise BuildError("INPUT_MISSING_OR_NONREGULAR", f"{label}: {exc}") from exc
    if resolved != absolute or stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise BuildError(
            "INPUT_MISSING_OR_NONREGULAR",
            f"{label}: path is not a canonical regular file: {path}",
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise BuildError("INPUT_MISSING_OR_NONREGULAR", f"{label}: {exc}") from exc


def _file_record(role: str, path: Path, data: bytes) -> dict[str, Any]:
    return {
        "path": str(path.absolute()),
        "role": role,
        "sha256": _sha256_bytes(data),
        "size_bytes": len(data),
    }


def _git(root: Path, *arguments: str, allowed: frozenset[int] = frozenset({0})) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if completed.returncode not in allowed:
        raise BuildError(
            "AUTHORITY_MISMATCH",
            f"git {' '.join(arguments)} failed at {root}: {completed.stderr.strip()}",
        )
    return completed


def _repository_identity(root: Path, *, exact_head: str | None = None, detached: bool = False) -> dict[str, Any]:
    top = _git(root, "rev-parse", "--show-toplevel").stdout.strip()
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    symbolic = _git(root, "symbolic-ref", "-q", "HEAD", allowed=frozenset({0, 1}))
    is_detached = symbolic.returncode == 1
    if Path(top) != root or (exact_head is not None and head != exact_head) or (detached and not is_detached):
        raise BuildError(
            "AUTHORITY_MISMATCH",
            f"repository identity mismatch at {root}: top={top!r}, head={head!r}, detached={is_detached}",
        )
    if root == W2D_FORBIDDEN_ROOT or Path(top) == W2D_FORBIDDEN_ROOT:
        raise BuildError("AUTHORITY_MISMATCH", "forbidden W2d fallback root resolved")
    return {
        "detached_head": is_detached,
        "head": head,
        "root": str(root),
    }


def _iter_embedded_file_records(value: Any, pointer: str = "") -> Iterator[tuple[str, str, str]]:
    if isinstance(value, Mapping):
        path = value.get("path")
        digest = value.get("sha256")
        if isinstance(path, str) and isinstance(digest, str) and path.startswith("recovery_runs/"):
            yield pointer or "/", path, digest
        for key, item in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            yield from _iter_embedded_file_records(item, f"{pointer}/{token}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            yield from _iter_embedded_file_records(item, f"{pointer}/{index}")


def _safe_w2d_relative(raw: str) -> Path:
    pure = PurePosixPath(raw)
    if (
        pure.is_absolute()
        or pure.as_posix() != raw
        or any(part in {"", ".", ".."} for part in pure.parts)
        or "\\" in raw
    ):
        raise BuildError("AUTHORITY_MISMATCH", f"unsafe W2d embedded path: {raw!r}")
    path = W2D_REPORT_DIR.joinpath(*pure.parts)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BuildError("AUTHORITY_MISMATCH", f"missing W2d embedded path {raw!r}: {exc}") from exc
    if not resolved.is_relative_to(W2D_ROOT) or resolved != path.absolute():
        raise BuildError("AUTHORITY_MISMATCH", f"W2d embedded path escaped fixed root: {raw!r}")
    return path


def _verify_b0_manifest(data: bytes) -> None:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise BuildError("AUTHORITY_MISMATCH", f"B0 SHA256SUMS is not ASCII: {exc}") from exc
    if len(lines) != 17:
        raise BuildError("AUTHORITY_MISMATCH", f"B0 SHA256SUMS has {len(lines)} entries, expected 17")
    seen: set[str] = set()
    for line_number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if match is None:
            raise BuildError("AUTHORITY_MISMATCH", f"malformed B0 checksum line {line_number}")
        digest, name = match.groups()
        if name in seen:
            raise BuildError("AUTHORITY_MISMATCH", f"duplicate B0 checksum member: {name}")
        seen.add(name)
        member = _read_regular(B0_RUN / name, f"B0 manifest member {name}")
        if _sha256_bytes(member) != digest:
            raise BuildError("AUTHORITY_MISMATCH", f"B0 checksum mismatch: {name}")


def _verify_status_brief(data: bytes, r3_response: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise BuildError("AUTHORITY_MISMATCH", f"status brief is not UTF-8: {exc}") from exc
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
    missing = [item for item in required if item not in text]
    if missing:
        raise BuildError("AUTHORITY_MISMATCH", f"status brief lacks locked facts: {missing}")
    start = r3_response.find(b"## 2.2 Certificate A")
    end = r3_response.find(b"## 2.4", start)
    if start < 0 or end < 0 or r3_response.find(b"## 2.2 Certificate A", start + 1) >= 0:
        raise BuildError("AUTHORITY_MISMATCH", "R3 response lacks a unique section 2.2--2.3 span")
    excerpt = r3_response[start:end]
    if data.count(excerpt) != 1:
        raise BuildError("AUTHORITY_MISMATCH", "status brief lacks exactly one verbatim R3 section 2.2--2.3 annex")


def _strict_zip(source_bytes: Mapping[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True) as archive:
        for name in sorted(STRICT_TRIO):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.extra = b""
            info.comment = b""
            archive.writestr(info, source_bytes[name])
        archive.comment = b""
    return stream.getvalue()


def _member_record(relative: str, data: bytes) -> dict[str, Any]:
    return {"path": relative, "sha256": _sha256_bytes(data), "size_bytes": len(data)}


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_bytes(run_dir: Path, target: Path, data: bytes) -> None:
    if (run_dir / "package/SHA256SUMS").exists():
        raise BuildError("NO_OVERWRITE_COLLISION", "package seal already exists; package is immutable")
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = run_dir / f".pending-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise
        os.link(pending, target)
        _fsync_directory(target.parent)
    except FileExistsError as exc:
        raise BuildError("NO_OVERWRITE_COLLISION", f"refusing to overwrite {target}") from exc
    finally:
        try:
            pending.unlink()
            _fsync_directory(run_dir)
        except FileNotFoundError:
            pass


def _source_snapshot() -> tuple[dict[str, bytes], dict[str, Any]]:
    if W2D_ROOT == W2D_FORBIDDEN_ROOT:
        raise BuildError("AUTHORITY_MISMATCH", "W2d fixed root equals forbidden fallback")
    project_repo = _repository_identity(PROJECT_ROOT)
    w2d_repo = _repository_identity(W2D_ROOT, exact_head=W2D_HEAD, detached=True)
    data_by_role: dict[str, bytes] = {}
    records: list[dict[str, Any]] = []
    for role, path, expected in EXPECTED_STATIC_SOURCES:
        data = _read_regular(path, role)
        digest = _sha256_bytes(data)
        if digest != expected:
            raise BuildError(
                "AUTHORITY_MISMATCH",
                f"{role} SHA-256 mismatch: expected {expected}, got {digest}",
            )
        data_by_role[role] = data
        records.append(_file_record(role, path, data))
    for role, path in DYNAMIC_SOURCES:
        data = _read_regular(path, role)
        data_by_role[role] = data
        records.append(_file_record(role, path, data))
    _verify_b0_manifest(data_by_role["b0.artifact_manifest"])
    report = _strict_json_bytes(data_by_role["w2d.report_json"], "W2d report")
    if report.get("baseline_head") != W2D_HEAD:
        raise BuildError("AUTHORITY_MISMATCH", "W2d report baseline_head drifted")
    embedded_seen: set[str] = set()
    for pointer, relative, expected in _iter_embedded_file_records(report):
        if pointer in embedded_seen:
            raise BuildError("AUTHORITY_MISMATCH", f"duplicate W2d JSON pointer: {pointer}")
        embedded_seen.add(pointer)
        path = _safe_w2d_relative(relative)
        data = _read_regular(path, f"W2d embedded {pointer}")
        if _sha256_bytes(data) != expected:
            raise BuildError("AUTHORITY_MISMATCH", f"W2d embedded SHA mismatch at {pointer}")
        role = f"w2d.embedded{pointer}"
        data_by_role[role] = data
        records.append(_file_record(role, path, data))
    _verify_status_brief(data_by_role["status_brief_source"], data_by_role["r3.response_09"])
    records.sort(key=lambda item: str(item["role"]))
    if len({str(item["role"]) for item in records}) != len(records):
        raise BuildError("AUTHORITY_MISMATCH", "source roles are not unique")
    return data_by_role, {
        "repository_identities": {
            "package_worktree": project_repo,
            "w2d_independent_detached_repository": w2d_repo,
        },
        "schema_version": SOURCE_SCHEMA,
        "sources": records,
        "w2d_authority_kind": "dirty_untracked_byte_authority_in_independent_detached_repository",
        "w2d_forbidden_fallback": str(W2D_FORBIDDEN_ROOT),
    }


def _assert_snapshot_unchanged(source_identity: Mapping[str, Any]) -> None:
    sources = source_identity.get("sources")
    if not isinstance(sources, Sequence):
        raise BuildError("STALE_INPUT", "source identity list is malformed")
    for raw in sources:
        if not isinstance(raw, Mapping):
            raise BuildError("STALE_INPUT", "source identity entry is malformed")
        path = Path(str(raw.get("path")))
        data = _read_regular(path, str(raw.get("role")))
        if len(data) != raw.get("size_bytes") or _sha256_bytes(data) != raw.get("sha256"):
            raise BuildError("STALE_INPUT", f"source changed during build: {path}")
    if _repository_identity(PROJECT_ROOT) != source_identity["repository_identities"]["package_worktree"]:
        raise BuildError("STALE_INPUT", "package worktree Git identity changed during build")
    if (
        _repository_identity(W2D_ROOT, exact_head=W2D_HEAD, detached=True)
        != source_identity["repository_identities"]["w2d_independent_detached_repository"]
    ):
        raise BuildError("STALE_INPUT", "W2d repository identity changed during build")


def _parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="new no-overwrite authority run root")
    return parser.parse_args(argv)


def build_package(output_dir: Path, *, argv: Sequence[str] | None = None) -> dict[str, Any]:
    """Build and seal one package in a previously nonexistent run directory."""

    run_dir = output_dir.absolute()
    if run_dir.exists() or run_dir.is_symlink():
        raise BuildError("NO_OVERWRITE_COLLISION", f"output directory already exists: {run_dir}")
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    free_before = shutil.disk_usage(run_dir.parent).free
    if free_before < MIN_FREE_BYTES:
        raise BuildError(
            "INSUFFICIENT_PERSISTENT_SPACE",
            f"free bytes {free_before} below {MIN_FREE_BYTES}",
        )
    data_by_role, source_identity = _source_snapshot()
    try:
        run_dir.mkdir(mode=0o755)
    except FileExistsError as exc:
        raise BuildError("NO_OVERWRITE_COLLISION", f"output directory raced into existence: {run_dir}") from exc
    package_dir = run_dir / "package"
    for relative in ("attachments", "operator", "control"):
        (package_dir / relative).mkdir(parents=True, exist_ok=False)

    strict_bytes = {
        name: data_by_role[
            f"strict.{ {'problem.md': 'problem', 'problem_instance.json': 'instance', 'problem_instance.schema.json': 'schema'}[name] }"
        ]
        for name in STRICT_TRIO
    }
    payloads: dict[str, bytes] = {
        "attachments/strict-trio.zip": _strict_zip(strict_bytes),
        "attachments/methodology-brief.md": data_by_role["methodology_brief"],
        "attachments/current-status-brief.md": data_by_role["status_brief_source"],
        "operator/r4-questions.md": QUESTIONS_BYTES,
        "operator/SUBMISSION_CHECKLIST.md": CHECKLIST_BYTES,
    }
    attachment_list = {
        "attachment_count": 3,
        "attachments": [
            {"path": "attachments/strict-trio.zip", "role": "strict_trio_zip"},
            {"path": "attachments/methodology-brief.md", "role": "methodology_brief"},
            {"path": "attachments/current-status-brief.md", "role": "current_status_brief"},
        ],
        "operator_files_are_not_attachments": [
            "operator/r4-questions.md",
            "operator/SUBMISSION_CHECKLIST.md",
        ],
        "schema_version": ATTACHMENT_SCHEMA,
    }
    payloads["control/source-identities.json"] = _canonical_json(source_identity)
    payloads["control/attachment-list.json"] = _canonical_json(attachment_list)
    build_record = {
        "argv": list(sys.argv if argv is None else argv),
        "builder": next(record for record in source_identity["sources"] if record["role"] == "package_builder_tool"),
        "free_bytes_before_build": free_before,
        "output_dir": str(run_dir),
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "schema_version": BUILD_SCHEMA,
        "state": "PAYLOAD_PLAN_BEFORE_SEAL",
    }
    payloads["control/build-record.json"] = _canonical_json(build_record)
    if set(payloads) != PACKAGE_MEMBER_PATHS:
        raise BuildError("MANIFEST_INCOMPLETE", "internal payload path set drifted")
    for relative in sorted(payloads):
        _publish_bytes(run_dir, package_dir / relative, payloads[relative])

    manifest = {
        "claim_boundary": {
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
        },
        "excluded_from_manifest_domain": [
            "package-manifest.json",
            "SHA256SUMS",
            "../verifications/",
            "../ready/",
            "package_id",
            "selected_receipt_identity",
        ],
        "external_sources": source_identity["sources"],
        "package_members": [_member_record(path, payloads[path]) for path in sorted(payloads)],
        "repository_identities": source_identity["repository_identities"],
        "schema_version": SCHEMA,
        "seal_contract": {
            "package_id_definition": "sha256(SHA256SUMS exact bytes)",
            "sha256sums_covers": "all regular files under package except SHA256SUMS itself",
            "writes_after_sha256sums": "forbidden",
        },
    }
    manifest_bytes = _canonical_json(manifest)
    _publish_bytes(run_dir, package_dir / "package-manifest.json", manifest_bytes)
    _assert_snapshot_unchanged(source_identity)
    free_before_seal = shutil.disk_usage(run_dir).free
    if free_before_seal < MIN_FREE_BYTES:
        raise BuildError(
            "INSUFFICIENT_PERSISTENT_SPACE",
            f"free bytes before seal {free_before_seal} below {MIN_FREE_BYTES}",
        )
    sealed_files: dict[str, bytes] = {}
    for path in sorted(package_dir.rglob("*"), key=lambda item: item.relative_to(package_dir).as_posix()):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise BuildError("MANIFEST_INCOMPLETE", f"non-regular package object: {path}")
        if path.is_file():
            relative = path.relative_to(package_dir).as_posix()
            sealed_files[relative] = path.read_bytes()
    expected_sealed = PACKAGE_MEMBER_PATHS | {"package-manifest.json"}
    if set(sealed_files) != expected_sealed:
        raise BuildError("MANIFEST_INCOMPLETE", "pre-seal package file set is not exact")
    sha_bytes = "".join(f"{_sha256_bytes(sealed_files[path])}  {path}\n" for path in sorted(sealed_files)).encode(
        "ascii"
    )
    _publish_bytes(run_dir, package_dir / "SHA256SUMS", sha_bytes)
    package_id = _sha256_bytes(sha_bytes)
    result = {
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "package_id": package_id,
        "run_dir": str(run_dir),
        "sha256sums_sha256": package_id,
        "status": "SEALED_AWAITING_INDEPENDENT_VERIFICATION",
    }
    return result


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    try:
        result = build_package(arguments.output_dir, argv=sys.argv if argv is None else argv)
    except BuildError as exc:
        print(json.dumps({"error_code": exc.code, "message": str(exc), "status": "FAIL"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
