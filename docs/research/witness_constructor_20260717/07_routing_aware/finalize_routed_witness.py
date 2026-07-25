"""Fail-closed publication path for a feasible fixed-geometry router result.

This module never runs a solver.  It consumes one hash-pinned router result,
repeats the cheap structural/reachability/objective audits, invokes the pinned
independent layout checker, and publishes only content-addressed research
artifacts.  The resulting statement is a feasible-layout lower bound only.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import stat
import sys
from typing import Any, Mapping, Sequence


_BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_PROJECT_ROOT))

_MODULE_PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
construct_witness = importlib.import_module(f"{_MODULE_PREFIX}.construct_witness")
run_supervisor = importlib.import_module(f"{_MODULE_PREFIX}.run_supervisor")
strict_contract = importlib.import_module(f"{_MODULE_PREFIX}.strict_contract")
witness_campaign = importlib.import_module(f"{_MODULE_PREFIX}.witness_campaign")
witness_io = importlib.import_module(f"{_MODULE_PREFIX}.witness_io")


PROJECT_ROOT = _BOOTSTRAP_PROJECT_ROOT
RESEARCH_ROOT = Path(__file__).resolve().parent
DEFAULT_RUN_ROOT = RESEARCH_ROOT / "runs"
DEFAULT_PUBLISH_ROOT = RESEARCH_ROOT / "artifacts"
EXPECTED_BASELINE_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
CLAIM_BOUNDARY = "feasible_layout_lower_bound_only"
RESULT_SCHEMA = "routed_witness_finalization.v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_UNIT_RE = re.compile(r"zmd-witness-fixed-router-[0-9]{8}T[0-9]{6}Z\.service")

_LAUNCH_HEADER_SCHEMA = "fixed_geometry_router_launch.v1"
_LAUNCH_CLASSIFICATION_SCHEMA = "fixed_geometry_router_classification.v1"
_LAUNCH_HEADER_KEYS = {
    "schema_version",
    "created_utc",
    "baseline_head",
    "observed_head",
    "unit_name",
    "dry_run",
    "pid",
    "active_units",
    "active_processes",
    "sources",
    "geometry",
    "result_path",
    "time_limit_seconds",
    "workers",
    "wait_contract",
    "lock_path",
}
_LAUNCH_CLASSIFICATION_KEYS = {
    "schema_version",
    "dry_run",
    "classification",
    "route_ready",
    "launch_error",
    "process",
    "geometry",
    "result",
}
_GEOMETRY_RECORD_KEYS = {
    "source_path",
    "snapshot_path",
    "sha256",
    "size_bytes",
    "required_placement_count",
    "pole_count",
}
_FILE_RECORD_KEYS = {"path", "sha256", "size_bytes"}
_ROUTER_SOURCE_NAMES = {
    "cgroup_telemetry",
    "fixed_geometry_router",
    "launcher",
    "run_supervisor",
    "worker",
}


class FinalizationError(RuntimeError):
    """A finalization or publication invariant failed closed."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class FinalizationOutcome:
    accepted: bool
    run_dir: Path
    layout_path: Path | None
    manifest_path: Path | None
    summary_path: Path


@dataclass(frozen=True)
class LauncherEvidence:
    """Pinned launch evidence plus the exact source/input bytes it names."""

    header_payload: bytes
    classification_payload: bytes
    unit_name: str
    geometry_sha256: str
    geometry_payload: bytes
    source_payloads: Mapping[str, bytes]


@dataclass(frozen=True)
class PreparedPublication:
    """Content-addressed files whose acceptance is inert until manifest commit."""

    publications: Mapping[str, run_supervisor.PublishRecord]
    manifest: Mapping[str, Any]
    manifest_payload: bytes
    manifest_path: Path
    manifest_sha256: str

    def record(self) -> dict[str, Any]:
        return {
            "status": "CONTENT_ADDRESSED_PUBLICATION_PREPARED",
            "claim_boundary": CLAIM_BOUNDARY,
            "files": {
                name: record.as_dict()
                for name, record in sorted(self.publications.items())
            },
            "manifest": dict(self.manifest),
            "manifest_artifact": {
                "path": str(self.manifest_path),
                "sha256": self.manifest_sha256,
                "size_bytes": len(self.manifest_payload),
                "commit_marker_required": True,
            },
        }


def _fail(code: str, message: str) -> None:
    raise FinalizationError(code, message)


def _load_pinned_json_source(
    path: Path,
    expected_sha256: str,
    *,
    label: str,
    code_prefix: str,
) -> tuple[bytes, Mapping[str, Any], Path]:
    if not isinstance(expected_sha256, str) or _SHA256_RE.fullmatch(expected_sha256) is None:
        _fail(f"{code_prefix}_HASH_INVALID", repr(expected_sha256))
    unresolved = Path(path)
    try:
        metadata = unresolved.lstat()
        source = unresolved.resolve(strict=True)
    except OSError as exc:
        _fail(f"{code_prefix}_SOURCE_INVALID", str(exc))
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        _fail(f"{code_prefix}_SOURCE_INVALID", "source must be a regular non-symlink file")
    snapshot = run_supervisor._read_stable_snapshot(source)
    if snapshot.sha256 != expected_sha256:
        _fail(
            f"{code_prefix}_HASH_MISMATCH",
            f"expected {expected_sha256}, observed {snapshot.sha256}",
        )
    parsed = strict_contract.strict_json_loads(snapshot.payload, label=label)
    if not isinstance(parsed, Mapping):
        _fail(f"{code_prefix}_SHAPE", f"{label} root must be an object")
    return snapshot.payload, parsed, source


def _load_pinned_source(path: Path, expected_sha256: str) -> tuple[bytes, Mapping[str, Any]]:
    payload, parsed, _source = _load_pinned_json_source(
        path,
        expected_sha256,
        label="router result",
        code_prefix="ROUTER_RESULT",
    )
    return payload, parsed


def _require_mapping(value: Any, *, code: str, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(code, f"{label} must be an object with string keys")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    *,
    code: str,
    label: str,
) -> None:
    if set(value) != expected:
        _fail(
            code,
            f"{label}: missing={sorted(expected - set(value))}, extra={sorted(set(value) - expected)}",
        )


def _require_nonnegative_integer(value: Any, *, code: str, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(code, f"{label} must be a nonnegative integer")
    return value


def _file_record_from_json(value: Any, *, label: str) -> run_supervisor.FileRecord:
    record = _require_mapping(value, code="LAUNCH_SOURCE_RECORD_INVALID", label=label)
    _require_exact_keys(
        record,
        _FILE_RECORD_KEYS,
        code="LAUNCH_SOURCE_RECORD_INVALID",
        label=label,
    )
    path = record.get("path")
    sha256 = record.get("sha256")
    size_bytes = record.get("size_bytes")
    if type(path) is not str or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        _fail("LAUNCH_SOURCE_RECORD_INVALID", f"{label}.path is not a safe relative path")
    if type(sha256) is not str or _SHA256_RE.fullmatch(sha256) is None:
        _fail("LAUNCH_SOURCE_RECORD_INVALID", f"{label}.sha256 is malformed")
    size = _require_nonnegative_integer(
        size_bytes,
        code="LAUNCH_SOURCE_RECORD_INVALID",
        label=f"{label}.size_bytes",
    )
    return run_supervisor.FileRecord(path=path, sha256=sha256, size_bytes=size)


def _require_live_file_record(
    project_root: Path,
    expected: run_supervisor.FileRecord,
    *,
    code: str,
) -> bytes:
    source = project_root / expected.path
    try:
        resolved = source.resolve(strict=True)
    except OSError as exc:
        _fail(code, str(exc))
    if resolved != project_root and project_root not in resolved.parents:
        _fail(code, f"source leaves project root: {resolved}")
    snapshot = run_supervisor._read_stable_snapshot(resolved)
    if snapshot.sha256 != expected.sha256 or snapshot.size_bytes != expected.size_bytes:
        _fail(code, f"live source differs from launch record: {expected.path}")
    return snapshot.payload


def _validate_geometry_record(value: Any) -> Mapping[str, Any]:
    record = _require_mapping(value, code="LAUNCH_GEOMETRY_INVALID", label="launch geometry")
    _require_exact_keys(
        record,
        _GEOMETRY_RECORD_KEYS,
        code="LAUNCH_GEOMETRY_INVALID",
        label="launch geometry",
    )
    sha256 = record.get("sha256")
    if type(sha256) is not str or _SHA256_RE.fullmatch(sha256) is None:
        _fail("LAUNCH_GEOMETRY_INVALID", "geometry SHA-256 is malformed")
    _require_nonnegative_integer(
        record.get("size_bytes"),
        code="LAUNCH_GEOMETRY_INVALID",
        label="geometry.size_bytes",
    )
    if record.get("required_placement_count") != 266:
        _fail("LAUNCH_GEOMETRY_INVALID", "geometry required placement count differs")
    poles = _require_nonnegative_integer(
        record.get("pole_count"),
        code="LAUNCH_GEOMETRY_INVALID",
        label="geometry.pole_count",
    )
    if poles < 9:
        _fail("LAUNCH_GEOMETRY_INVALID", f"geometry has only {poles} poles")
    if type(record.get("snapshot_path")) is not str or not record["snapshot_path"]:
        _fail("LAUNCH_GEOMETRY_INVALID", "geometry snapshot path is missing")
    if type(record.get("source_path")) is not str or not record["source_path"]:
        _fail("LAUNCH_GEOMETRY_INVALID", "geometry source path is missing")
    return record


def _validate_launcher_evidence(
    *,
    project_root: Path,
    router_result_source: Path,
    router_result_sha256: str,
    router_result_size_bytes: int,
    router_result: Mapping[str, Any],
    header_payload: bytes,
    header: Mapping[str, Any],
    classification_payload: bytes,
    classification: Mapping[str, Any],
) -> LauncherEvidence:
    _require_exact_keys(
        header,
        _LAUNCH_HEADER_KEYS,
        code="LAUNCH_HEADER_FIELDS",
        label="launcher header",
    )
    if header.get("schema_version") != _LAUNCH_HEADER_SCHEMA or header.get("dry_run") is not False:
        _fail("LAUNCH_HEADER_INVALID", "launcher header schema/dry-run state differs")
    if (
        header.get("baseline_head") != EXPECTED_BASELINE_HEAD
        or header.get("observed_head") != EXPECTED_BASELINE_HEAD
    ):
        _fail("LAUNCH_HEADER_INVALID", "launcher header repository identity differs")
    if header.get("active_units") != [] or header.get("active_processes") != []:
        _fail("LAUNCH_HEADER_INVALID", "launcher header contains a busy preflight")
    unit_name = header.get("unit_name")
    if type(unit_name) is not str or _UNIT_RE.fullmatch(unit_name) is None:
        _fail("LAUNCH_HEADER_INVALID", repr(unit_name))
    raw_header_result_path = Path(str(header.get("result_path")))
    if not raw_header_result_path.is_absolute():
        _fail("LAUNCH_RESULT_PATH_INVALID", "launcher result path must be absolute")
    try:
        header_result_path = raw_header_result_path.resolve(strict=True)
    except OSError as exc:
        _fail("LAUNCH_RESULT_PATH_INVALID", str(exc))
    if header_result_path != router_result_source:
        _fail("LAUNCH_RESULT_PATH_MISMATCH", f"header names {header_result_path}")

    geometry = _validate_geometry_record(header.get("geometry"))
    geometry_path = Path(str(geometry["snapshot_path"]))
    if not geometry_path.is_absolute():
        _fail("LAUNCH_GEOMETRY_SNAPSHOT_INVALID", "geometry snapshot path must be absolute")
    try:
        geometry_snapshot = run_supervisor._read_stable_snapshot(geometry_path)
    except run_supervisor.SupervisorError as exc:
        _fail("LAUNCH_GEOMETRY_SNAPSHOT_INVALID", str(exc))
    if (
        geometry_snapshot.sha256 != geometry["sha256"]
        or geometry_snapshot.size_bytes != geometry["size_bytes"]
    ):
        _fail("LAUNCH_GEOMETRY_SNAPSHOT_INVALID", "live geometry snapshot differs from launcher header")

    sources = _require_mapping(
        header.get("sources"),
        code="LAUNCH_SOURCES_INVALID",
        label="launcher sources",
    )
    if set(sources) != _ROUTER_SOURCE_NAMES:
        _fail("LAUNCH_SOURCES_INVALID", f"unexpected source names {sorted(sources)}")
    source_payloads: dict[str, bytes] = {}
    for name in sorted(sources):
        expected = _file_record_from_json(sources[name], label=f"launcher sources.{name}")
        source_payloads[name] = _require_live_file_record(
            project_root,
            expected,
            code="LAUNCH_SOURCE_DRIFT",
        )

    _require_exact_keys(
        classification,
        _LAUNCH_CLASSIFICATION_KEYS,
        code="LAUNCH_CLASSIFICATION_FIELDS",
        label="launcher classification",
    )
    if (
        classification.get("schema_version") != _LAUNCH_CLASSIFICATION_SCHEMA
        or classification.get("dry_run") is not False
        or classification.get("route_ready") is not True
        or classification.get("launch_error") is not None
        or classification.get("geometry") != geometry
    ):
        _fail("LAUNCH_CLASSIFICATION_INVALID", "launcher terminal state is not route-ready")
    terminal = _require_mapping(
        classification.get("classification"),
        code="LAUNCH_CLASSIFICATION_INVALID",
        label="launcher classification.classification",
    )
    if set(terminal) != {"code", "successful", "detail"} or terminal.get("code") != run_supervisor.SUCCESS:
        _fail("LAUNCH_CLASSIFICATION_INVALID", "launcher classification is not CLEAN_RESULT")
    if terminal.get("successful") is not True or terminal.get("detail") != "STRICT_ROUTES_INDEPENDENTLY_REACHABLE":
        _fail("LAUNCH_CLASSIFICATION_INVALID", "launcher success detail differs")
    process = _require_mapping(
        classification.get("process"),
        code="LAUNCH_CLASSIFICATION_INVALID",
        label="launcher classification.process",
    )
    if set(process) != {"timed_out", "returncode"} or process != {"timed_out": False, "returncode": 0}:
        _fail("LAUNCH_CLASSIFICATION_INVALID", "launcher process did not exit cleanly")
    result = _require_mapping(
        classification.get("result"),
        code="LAUNCH_CLASSIFICATION_INVALID",
        label="launcher classification.result",
    )
    expected_result_keys = {
        "present",
        "parse_valid",
        "schema_valid",
        "integrity_valid",
        "worker_status",
        "worker_classification",
        "oom_attribution",
        "sha256",
        "size_bytes",
        "errors",
    }
    _require_exact_keys(
        result,
        expected_result_keys,
        code="LAUNCH_CLASSIFICATION_INVALID",
        label="launcher classification.result",
    )
    if any(result.get(key) is not True for key in ("present", "parse_valid", "schema_valid", "integrity_valid")):
        _fail("LAUNCH_CLASSIFICATION_INVALID", "launcher result gates did not all pass")
    if (
        result.get("worker_status") != "FEASIBLE"
        or result.get("worker_classification") != "STRICT_ROUTES_INDEPENDENTLY_REACHABLE"
        or result.get("oom_attribution") != "NO_CGROUP_OOM"
        or result.get("sha256") != router_result_sha256
        or result.get("size_bytes") != router_result_size_bytes
        or result.get("errors") != []
    ):
        _fail("LAUNCH_RESULT_IDENTITY_MISMATCH", "launcher result identity differs")

    telemetry = _require_mapping(
        router_result.get("telemetry"),
        code="ROUTER_RESULT_TELEMETRY_INVALID",
        label="router result telemetry",
    )
    input_snapshot = _require_mapping(
        telemetry.get("input_snapshot"),
        code="ROUTER_RESULT_TELEMETRY_INVALID",
        label="router result telemetry.input_snapshot",
    )
    if input_snapshot.get("geometry_sha256") != geometry["sha256"]:
        _fail("LAUNCH_GEOMETRY_RESULT_MISMATCH", "router result geometry differs from launcher header")
    cgroup = _require_mapping(
        telemetry.get("cgroup"),
        code="ROUTER_RESULT_TELEMETRY_INVALID",
        label="router result telemetry.cgroup",
    )
    if cgroup.get("expected_unit_name") != unit_name or cgroup.get("oom_attribution") != "NO_CGROUP_OOM":
        _fail("LAUNCH_CGROUP_RESULT_MISMATCH", "router cgroup evidence differs from launcher header")

    return LauncherEvidence(
        header_payload=header_payload,
        classification_payload=classification_payload,
        unit_name=unit_name,
        geometry_sha256=str(geometry["sha256"]),
        geometry_payload=geometry_snapshot.payload,
        source_payloads=source_payloads,
    )


def _checker_record(checker: Any, *, checker_inputs: Mapping[str, Any]) -> dict[str, Any]:
    source_identity = checker.checker_source_identity
    rendered_identity = None
    if source_identity is not None:
        rendered_identity = {
            "device": source_identity[0],
            "inode": source_identity[1],
            "mode": source_identity[2],
            "link_count": source_identity[3],
            "size_bytes": source_identity[4],
            "mtime_ns": source_identity[5],
            "ctime_ns": source_identity[6],
        }
    return {
        "classification": checker.classification,
        "exit_code": checker.exit_code,
        "status": checker.status,
        "signal_number": checker.signal_number,
        "checker_trusted": checker.checker_trusted,
        "checker_sha256": checker.checker_sha256,
        "expected_checker_sha256": witness_io.EXPECTED_CHECKER_SHA256,
        "checker_source_path": checker.checker_source_path,
        "checker_source_identity": rendered_identity,
        "checker_snapshot_size_bytes": checker.checker_snapshot_size_bytes,
        "checker_python_executable": checker.checker_python_executable,
        "checker_execution_mode": checker.checker_execution_mode,
        "accepted": checker.accepted,
        "stderr": checker.stderr,
        "stdout": checker.stdout,
        "report": checker.report,
        "checker_inputs": dict(checker_inputs),
    }


def _prepare_publication(
    sources: Mapping[str, tuple[Path, str, run_supervisor.FileRecord]],
    publish_root: Path,
) -> PreparedPublication:
    """Publish inert content files and deterministically prepare the last marker."""

    for name, (path, _logical_name, expected) in sources.items():
        observed = run_supervisor.file_record(path)
        if observed != expected:
            _fail("PREPUBLICATION_SOURCE_DRIFT", f"{name}: expected={expected!r}, observed={observed!r}")
    publications: dict[str, run_supervisor.PublishRecord] = {}
    for name, (path, logical_name, expected) in sources.items():
        publication = run_supervisor.publish_content_addressed(
            path,
            publish_root,
            logical_name=logical_name,
        )
        if publication.sha256 != expected.sha256 or publication.size_bytes != expected.size_bytes:
            _fail("PUBLISHED_SOURCE_DRIFT", f"{name} differs from its checked FileRecord")
        if run_supervisor.file_record(path) != expected:
            _fail("PUBLICATION_SOURCE_DRIFT", f"{name} changed while it was published")
        publications[name] = publication
    for name, (path, _logical_name, expected) in sources.items():
        if run_supervisor.file_record(path) != expected:
            _fail("PREMANIFEST_SOURCE_DRIFT", f"{name} changed before manifest commit")

    verified = run_supervisor._verify_content_addressed_publications(
        publications,
        publish_dir=publish_root,
        relative_to=publish_root,
    )
    manifest = run_supervisor._manifest_from_file_records(verified)
    manifest_payload = run_supervisor.canonical_json_bytes(manifest)
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    manifest_path = Path(publish_root).resolve(strict=True) / f"manifest.{manifest_sha256}.json"
    return PreparedPublication(
        publications=publications,
        manifest=manifest,
        manifest_payload=manifest_payload,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha256,
    )


def _exact_manifest_marker_exists(prepared: PreparedPublication) -> bool:
    """Return whether the authoritative marker is already exposed byte-exactly."""

    try:
        snapshot = run_supervisor._read_stable_snapshot(prepared.manifest_path)
    except (OSError, run_supervisor.SupervisorError):
        return False
    return (
        snapshot.sha256 == prepared.manifest_sha256
        and snapshot.payload == prepared.manifest_payload
    )


def _commit_prepared_publication(prepared: PreparedPublication, publish_root: Path) -> Path:
    """Expose the manifest as the final authority, with no rejecting action after it.

    The supervisor fsyncs the directory after linking the marker.  If that final
    durability call reports an error after the exact marker became visible, the
    transaction is already externally committed; treating it as rejected would
    create two contradictory terminal states.  Exact marker presence therefore
    resolves that narrow ambiguous-return case as committed.
    """

    try:
        run_supervisor.publish_verified_manifest_content_addressed(
            prepared.publications,
            publish_root,
            relative_to=publish_root,
        )
    except Exception:  # noqa: BLE001 - reconcile an ambiguous commit return
        if _exact_manifest_marker_exists(prepared):
            return prepared.manifest_path
        raise
    return prepared.manifest_path


def _snapshot_bytes_exclusive(
    attempt_dir: Path,
    *,
    stem: str,
    suffix: str,
    payload: bytes,
    expected_sha256: str | None = None,
) -> tuple[Path, run_supervisor.FileRecord]:
    digest = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        _fail("SNAPSHOT_INPUT_HASH_MISMATCH", f"{stem}: expected {expected_sha256}, observed {digest}")
    path = attempt_dir / f"{stem}.{digest}{suffix}"
    run_supervisor.write_bytes_exclusive(path, payload)
    record = run_supervisor.file_record(path)
    if record.sha256 != digest or record.size_bytes != len(payload):
        _fail("SNAPSHOT_WRITE_DRIFT", stem)
    return path, record


def finalize_router_result(
    router_result_path: Path,
    *,
    expected_router_result_sha256: str,
    launcher_header_path: Path,
    expected_launcher_header_sha256: str,
    launcher_classification_path: Path,
    expected_launcher_classification_sha256: str,
    project_root: Path = PROJECT_ROOT,
    run_root: Path = DEFAULT_RUN_ROOT,
    publish_root: Path = DEFAULT_PUBLISH_ROOT,
    checker_timeout_seconds: float = 60.0,
) -> FinalizationOutcome:
    """Finalize one explicit router result; never discover or reuse ``latest``."""

    root = Path(project_root).resolve(strict=True)
    head = construct_witness._repository_head(root)
    if head != EXPECTED_BASELINE_HEAD:
        _fail("BASELINE_HEAD_MISMATCH", f"expected {EXPECTED_BASELINE_HEAD}, observed {head}")
    if (
        isinstance(checker_timeout_seconds, bool)
        or not isinstance(checker_timeout_seconds, (int, float))
        or not math.isfinite(float(checker_timeout_seconds))
        or checker_timeout_seconds <= 0
    ):
        _fail("CHECKER_TIMEOUT_INVALID", repr(checker_timeout_seconds))
    payload, router_result, router_result_source = _load_pinned_json_source(
        router_result_path,
        expected_router_result_sha256,
        label="router result",
        code_prefix="ROUTER_RESULT",
    )
    header_payload, launcher_header, _header_source = _load_pinned_json_source(
        launcher_header_path,
        expected_launcher_header_sha256,
        label="launcher header",
        code_prefix="LAUNCH_HEADER",
    )
    classification_payload, launcher_classification, _classification_source = _load_pinned_json_source(
        launcher_classification_path,
        expected_launcher_classification_sha256,
        label="launcher classification",
        code_prefix="LAUNCH_CLASSIFICATION",
    )
    bundle, reconciliation = strict_contract.load_and_reconcile(root)
    evidence = _validate_launcher_evidence(
        project_root=root,
        router_result_source=router_result_source,
        router_result_sha256=expected_router_result_sha256,
        router_result_size_bytes=len(payload),
        router_result=router_result,
        header_payload=header_payload,
        header=launcher_header,
        classification_payload=classification_payload,
        classification=launcher_classification,
    )

    run_dir = run_supervisor.create_run_directory(Path(run_root), head[:7])
    attempt_dir = run_supervisor.create_attempt_directory(run_dir, 1)
    failure_summary_path = run_dir / "summary.json"
    result_path = attempt_dir / "result.json"
    phase = "snapshot_inputs"
    try:
        router_snapshot, router_snapshot_record = _snapshot_bytes_exclusive(
            attempt_dir,
            stem="router_result",
            suffix=".json",
            payload=payload,
            expected_sha256=expected_router_result_sha256,
        )
        launcher_header_snapshot, launcher_header_record = _snapshot_bytes_exclusive(
            attempt_dir,
            stem="launcher_header",
            suffix=".json",
            payload=evidence.header_payload,
            expected_sha256=expected_launcher_header_sha256,
        )
        launcher_classification_snapshot, launcher_classification_record = _snapshot_bytes_exclusive(
            attempt_dir,
            stem="launcher_classification",
            suffix=".json",
            payload=evidence.classification_payload,
            expected_sha256=expected_launcher_classification_sha256,
        )
        router_geometry_snapshot, router_geometry_record = _snapshot_bytes_exclusive(
            attempt_dir,
            stem="router_geometry",
            suffix=".json",
            payload=evidence.geometry_payload,
            expected_sha256=evidence.geometry_sha256,
        )
        router_source_snapshots: dict[str, tuple[Path, run_supervisor.FileRecord]] = {}
        for name, source_payload in sorted(evidence.source_payloads.items()):
            router_source_snapshots[name] = _snapshot_bytes_exclusive(
                attempt_dir,
                stem=f"router_source_{name}",
                suffix=".py",
                payload=source_payload,
            )
        instance_payload = witness_campaign._instance_payload(bundle)
        instance_snapshot, instance_record = _snapshot_bytes_exclusive(
            attempt_dir,
            stem="strict_instance",
            suffix=".json",
            payload=instance_payload,
            expected_sha256=bundle.strict_instance.sha256,
        )

        phase = "build_routed_witness"
        built = witness_campaign.build_routed_witness(router_result, bundle=bundle)
        diagnostics_path = attempt_dir / "router_diagnostics.json"
        run_supervisor.write_json_exclusive(
            diagnostics_path,
            {
                **built.diagnostics(),
                "router_result_sha256": expected_router_result_sha256,
                "launcher_header_sha256": expected_launcher_header_sha256,
                "launcher_classification_sha256": expected_launcher_classification_sha256,
                "router_geometry_sha256": evidence.geometry_sha256,
                "repository_head": head,
                "input_sha256": dict(sorted(bundle.hashes.items())),
            },
        )
        diagnostics_record = run_supervisor.file_record(diagnostics_path)
        objective_path = attempt_dir / "objective_audit.json"
        run_supervisor.write_json_exclusive(objective_path, built.objective.as_dict())

        phase = "serialize_and_audit_layout"
        layout_payload = witness_io.canonical_json_bytes(built.witness)
        layout_sha256 = hashlib.sha256(layout_payload).hexdigest()
        layout_path = attempt_dir / f"layout.{layout_sha256}.json"
        run_supervisor.write_bytes_exclusive(layout_path, layout_payload)
        serialized_audit = construct_witness._audit_layout_file(bundle, layout_path)
        if serialized_audit != built.objective:
            _fail("SERIALIZED_OBJECTIVE_DRIFT", "serialized layout changed the exhaustive objective")
        layout_record = run_supervisor.file_record(layout_path)
        if layout_record.sha256 != layout_sha256 or layout_record.size_bytes != len(layout_payload):
            _fail("SERIALIZED_LAYOUT_IDENTITY", "serialized layout differs from its canonical bytes")
        objective_record = run_supervisor.file_record(objective_path)
        checker_inputs = {
            "schema_version": "routed_witness_checker_inputs.v1",
            "instance": instance_record.as_dict(),
            "layout": layout_record.as_dict(),
        }
        checker_inputs_path = attempt_dir / "checker_inputs.json"
        run_supervisor.write_json_exclusive(checker_inputs_path, checker_inputs)
        checker_inputs_record = run_supervisor.file_record(checker_inputs_path)

        phase = "independent_checker"
        checker = witness_io.run_independent_checker(
            instance_snapshot,
            layout_path,
            timeout_seconds=checker_timeout_seconds,
        )
        if run_supervisor.file_record(instance_snapshot) != instance_record:
            _fail("INSTANCE_DRIFT_AFTER_CHECKER", "checker instance snapshot changed during verification")
        if run_supervisor.file_record(layout_path) != layout_record:
            _fail("LAYOUT_DRIFT_AFTER_CHECKER", "checker layout snapshot changed during verification")
        checker_process_path = attempt_dir / "checker_process.json"
        checker_report_path = attempt_dir / "checker_report.json"
        run_supervisor.write_json_exclusive(
            checker_process_path,
            _checker_record(checker, checker_inputs=checker_inputs),
        )
        run_supervisor.write_json_exclusive(
            checker_report_path,
            checker.report
            if checker.report is not None
            else {
                "status": "CHECKER_REPORT_UNAVAILABLE",
                "classification": checker.classification,
            },
        )
        phase = "independent_acceptance"
        witness_campaign.accept_independent_checker(built, checker)
        acceptance = construct_witness._require_exact_checker_agreement(serialized_audit, checker)
        acceptance.update(
            {
                "schema_version": RESULT_SCHEMA,
                "repository_head": head,
                "router_result_sha256": expected_router_result_sha256,
                "launcher_header_sha256": expected_launcher_header_sha256,
                "launcher_classification_sha256": expected_launcher_classification_sha256,
                "router_geometry_sha256": evidence.geometry_sha256,
                "layout_sha256": layout_sha256,
                "checker_inputs": checker_inputs,
            }
        )
        acceptance_path = attempt_dir / "acceptance.json"
        run_supervisor.write_json_exclusive(acceptance_path, acceptance)
        acceptance_record = run_supervisor.file_record(acceptance_path)
        checker_process_record = run_supervisor.file_record(checker_process_path)
        checker_report_record = run_supervisor.file_record(checker_report_path)

        phase = "prepare_publication"
        finalization_summary = {
            "schema_version": RESULT_SCHEMA,
            "status": "LAYOUT_ACCEPTED",
            "claim_boundary": CLAIM_BOUNDARY,
            "repository_head": head,
            "router_result_sha256": expected_router_result_sha256,
            "launcher_header_sha256": expected_launcher_header_sha256,
            "launcher_classification_sha256": expected_launcher_classification_sha256,
            "router_geometry_sha256": evidence.geometry_sha256,
            "layout_sha256": layout_sha256,
            "checker_inputs_sha256": checker_inputs_record.sha256,
            "objective": asdict(serialized_audit.computed),
            "feasible_lower_bound": acceptance["feasible_lower_bound"],
            "input_reconciliation": {
                "counts": reconciliation.counts(),
                "input_sha256": dict(sorted(reconciliation.hashes.items())),
            },
            "commit_authority": {
                "rule": "effective_only_when_named_by_exact_manifest_commit",
                "manifest_logical_name": "finalization_summary",
            },
        }
        finalization_summary_path = attempt_dir / "finalization_summary.json"
        run_supervisor.write_json_exclusive(finalization_summary_path, finalization_summary)
        finalization_summary_record = run_supervisor.file_record(finalization_summary_path)

        publish_sources: dict[str, tuple[Path, str, run_supervisor.FileRecord]] = {
            "acceptance": (acceptance_path, "acceptance.json", acceptance_record),
            "checker_inputs": (checker_inputs_path, "checker_inputs.json", checker_inputs_record),
            "checker_process": (checker_process_path, "checker_process.json", checker_process_record),
            "checker_report": (checker_report_path, "checker_report.json", checker_report_record),
            "finalization_summary": (
                finalization_summary_path,
                "finalization_summary.json",
                finalization_summary_record,
            ),
            "layout": (layout_path, "layout.json", layout_record),
            "launcher_classification": (
                launcher_classification_snapshot,
                "launcher_classification.json",
                launcher_classification_record,
            ),
            "launcher_header": (launcher_header_snapshot, "launcher_header.json", launcher_header_record),
            "objective_audit": (objective_path, "objective_audit.json", objective_record),
            "router_diagnostics": (diagnostics_path, "router_diagnostics.json", diagnostics_record),
            "router_geometry": (router_geometry_snapshot, "router_geometry.json", router_geometry_record),
            "router_result": (router_snapshot, "router_result.json", router_snapshot_record),
            "strict_instance": (instance_snapshot, "strict_instance.json", instance_record),
        }
        for name, (source_path, source_record) in sorted(router_source_snapshots.items()):
            publish_sources[f"router_source_{name}"] = (
                source_path,
                f"router_source_{name}.py",
                source_record,
            )

        prepared = _prepare_publication(
            publish_sources,
            Path(publish_root),
        )
        run_supervisor.write_json_exclusive(attempt_dir / "publication.json", prepared.record())
        outcome = FinalizationOutcome(
            True,
            run_dir,
            layout_path,
            prepared.manifest_path,
            prepared.publications["finalization_summary"].path,
        )
        phase = "manifest_commit"
        _commit_prepared_publication(prepared, Path(publish_root))
        return outcome
    except Exception as exc:
        raw_code = getattr(exc, "code", None)
        failure = {
            "schema_version": RESULT_SCHEMA,
            "status": "FINALIZATION_REJECTED",
            "classification": raw_code if isinstance(raw_code, str) and raw_code else "UNEXPECTED_EXCEPTION",
            "exception_type": type(exc).__name__,
            "phase": phase,
            "message": str(exc),
            "claim_boundary": CLAIM_BOUNDARY,
        }
        if not result_path.exists():
            run_supervisor.write_json_exclusive(result_path, failure)
        if not failure_summary_path.exists():
            run_supervisor.write_json_exclusive(failure_summary_path, failure)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("router_result", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--launcher-header", type=Path, required=True)
    parser.add_argument("--launcher-header-sha256", required=True)
    parser.add_argument("--launcher-classification", type=Path, required=True)
    parser.add_argument("--launcher-classification-sha256", required=True)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--publish-root", type=Path, default=DEFAULT_PUBLISH_ROOT)
    parser.add_argument("--checker-timeout-seconds", type=float, default=60.0)
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        run_root = construct_witness._require_cli_output_scope(args.run_root)
        publish_root = construct_witness._require_cli_output_scope(args.publish_root)
        outcome = finalize_router_result(
            args.router_result,
            expected_router_result_sha256=args.expected_sha256,
            launcher_header_path=args.launcher_header,
            expected_launcher_header_sha256=args.launcher_header_sha256,
            launcher_classification_path=args.launcher_classification,
            expected_launcher_classification_sha256=args.launcher_classification_sha256,
            project_root=args.project_root,
            run_root=run_root,
            publish_root=publish_root,
            checker_timeout_seconds=args.checker_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - CLI classification boundary
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "accepted": outcome.accepted,
                "run_dir": str(outcome.run_dir),
                "layout": str(outcome.layout_path),
                "manifest": str(outcome.manifest_path),
                "claim_boundary": CLAIM_BOUNDARY,
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()


__all__ = [
    "CLAIM_BOUNDARY",
    "FinalizationError",
    "FinalizationOutcome",
    "finalize_router_result",
    "run_cli",
]
