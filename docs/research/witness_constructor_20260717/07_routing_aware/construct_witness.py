"""No-overwrite CLI for the routing-aware research witness.

The command has two deliberately narrow modes:

* ``run`` reconciles the pinned inputs, tries the declared 0/1/2-box schedule,
  invokes the sole deterministic witness builder, and accepts only the pinned
  independent checker plus an exact exhaustive-objective agreement;
* ``verify`` reruns the exhaustive body-only objective audit and the same pinned
  checker on an existing layout.

Every run and attempt directory is created exclusively.  Published artifacts
are content addressed.  The resulting claim is only that one concrete layout
is feasible with its recomputed objective score.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence


_BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_PROJECT_ROOT))

_MODULE_PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
objective_audit = importlib.import_module(f"{_MODULE_PREFIX}.objective_audit")
run_supervisor = importlib.import_module(f"{_MODULE_PREFIX}.run_supervisor")
shelf_constructor = importlib.import_module(f"{_MODULE_PREFIX}.shelf_constructor")
strict_contract = importlib.import_module(f"{_MODULE_PREFIX}.strict_contract")
witness_campaign = importlib.import_module(f"{_MODULE_PREFIX}.witness_campaign")
witness_io = importlib.import_module(f"{_MODULE_PREFIX}.witness_io")


PROJECT_ROOT = _BOOTSTRAP_PROJECT_ROOT
RESEARCH_ROOT = Path(__file__).resolve().parent
DEFAULT_RUN_ROOT = RESEARCH_ROOT / "runs"
DEFAULT_PUBLISH_ROOT = RESEARCH_ROOT / "artifacts"
EXPECTED_BASELINE_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
BOX_SCHEDULE = (0, 1, 2)
CLAIM_BOUNDARY = "feasible_layout_lower_bound_only"
RUN_SCHEMA = "routing_aware_witness_run.v1"
ATTEMPT_SCHEMA = "routing_aware_witness_attempt.v1"
VERIFY_SCHEMA = "routing_aware_witness_verification.v1"

_FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")


class ConstructWitnessError(RuntimeError):
    """A campaign or verification lifecycle invariant failed closed."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class CampaignOutcome:
    accepted: bool
    run_dir: Path
    summary_path: Path
    accepted_attempt: int | None
    layout_path: Path | None
    manifest_path: Path | None


@dataclass(frozen=True)
class VerificationOutcome:
    accepted: bool
    run_dir: Path
    report_path: Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repository_head(project_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConstructWitnessError("GIT_HEAD_UNAVAILABLE", str(exc)) from exc
    head = completed.stdout.strip()
    if _FULL_SHA_RE.fullmatch(head) is None:
        raise ConstructWitnessError("GIT_HEAD_INVALID", repr(head))
    return head


def _resolve_project_root(project_root: Path) -> Path:
    try:
        resolved = Path(project_root).resolve(strict=True)
    except OSError as exc:
        raise ConstructWitnessError("PROJECT_ROOT_INVALID", str(exc)) from exc
    if not resolved.is_dir():
        raise ConstructWitnessError("PROJECT_ROOT_INVALID", f"not a directory: {resolved}")
    return resolved


def _require_cli_output_scope(path: Path) -> Path:
    """Keep CLI writes inside this approved research-only subtree."""

    resolved = Path(path).resolve()
    research_root = RESEARCH_ROOT.resolve(strict=True)
    try:
        resolved.relative_to(research_root)
    except ValueError as exc:
        raise ConstructWitnessError(
            "OUTPUT_SCOPE_VIOLATION",
            f"CLI output must remain under {research_root}: {resolved}",
        ) from exc
    return resolved


def _exception_record(exc: Exception, *, phase: str) -> dict[str, Any]:
    raw_code = getattr(exc, "code", None)
    code = raw_code if isinstance(raw_code, str) and raw_code else "UNEXPECTED_EXCEPTION"
    return {
        "status": "ATTEMPT_FAILED",
        "phase": phase,
        "classification": code,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _reconciliation_record(reconciliation: Any) -> dict[str, Any]:
    return {
        "counts": reconciliation.counts(),
        "candidate_counts": dict(sorted(reconciliation.candidate_counts.items())),
        "input_sha256": dict(sorted(reconciliation.hashes.items())),
    }


def _candidate_record(candidate: Any, built: Any) -> dict[str, Any]:
    protected = candidate.protected_rect
    boundary = candidate.boundary_pattern
    return {
        "status": "CANDIDATE_ASSEMBLED",
        "claim_boundary": CLAIM_BOUNDARY,
        "boundary_pattern": {
            "left_gap": int(boundary.left_gap),
            "bottom_gap": int(boundary.bottom_gap),
        },
        "protected_body_empty_rectangle": {
            "x": int(protected.x),
            "y": int(protected.y),
            "width": int(protected.width),
            "height": int(protected.height),
        },
        "constructor_diagnostics": dict(candidate.diagnostics),
        "built_witness_diagnostics": built.diagnostics(),
    }


def _checker_record(checker: Any) -> dict[str, Any]:
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
        "expected_checker_source_path": str(witness_io.EXPECTED_CHECKER_PATH),
        "checker_source_identity": rendered_identity,
        "checker_snapshot_size_bytes": checker.checker_snapshot_size_bytes,
        "checker_python_executable": checker.checker_python_executable,
        "checker_execution_mode": checker.checker_execution_mode,
        "expected_checker_execution_mode": witness_io.PINNED_CHECKER_EXECUTION_MODE,
        "accepted": checker.accepted,
        "stderr": checker.stderr,
        "stdout": checker.stdout,
        "report": checker.report,
    }


def _load_strict_layout(path: Path) -> Mapping[str, Any]:
    try:
        payload = Path(path).read_bytes()
    except OSError as exc:
        raise ConstructWitnessError("LAYOUT_READ_FAILED", str(exc)) from exc
    parsed = strict_contract.strict_json_loads(payload, label=str(path))
    if not isinstance(parsed, Mapping):
        raise ConstructWitnessError("LAYOUT_SHAPE_INVALID", "layout root must be an object")
    return parsed


def _audit_layout_file(bundle: Any, layout_path: Path) -> Any:
    witness = _load_strict_layout(layout_path)
    instance = bundle.strict_instance.value
    if not isinstance(instance, Mapping):
        raise ConstructWitnessError("INSTANCE_SHAPE_INVALID", "strict instance root must be an object")
    return objective_audit.audit_witness_objective(instance, witness)


def _require_file_identity(
    path: Path,
    *,
    sha256: str,
    size_bytes: int,
    code: str,
) -> run_supervisor.FileRecord:
    """Re-read one stable snapshot and reject any byte/identity drift."""

    record = run_supervisor.file_record(path)
    if record.sha256 != sha256 or record.size_bytes != size_bytes:
        raise ConstructWitnessError(
            code,
            (
                f"expected sha256/size {sha256}/{size_bytes}, "
                f"observed {record.sha256}/{record.size_bytes}"
            ),
        )
    return record


def _require_exact_checker_agreement(audit: Any, checker: Any) -> dict[str, Any]:
    if not checker.accepted or checker.report is None:
        raise ConstructWitnessError(
            "INDEPENDENT_CHECKER_REJECTED",
            f"checker classification={checker.classification!r}",
        )
    expected = asdict(audit.computed)
    observed = checker.report.get("recomputed_objective")
    if observed != expected:
        raise ConstructWitnessError(
            "OBJECTIVE_AUDIT_DISAGREEMENT",
            f"checker={observed!r}, exhaustive={expected!r}",
        )
    return {
        "status": "INDEPENDENT_ACCEPTANCE_OK",
        "checker_status": checker.status,
        "checker_sha256": checker.checker_sha256,
        "recomputed_objective": expected,
        "feasible_lower_bound": {
            "area": int(audit.computed.area),
            "min_side": int(audit.computed.min_side),
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _publish_accepted_attempt(
    *,
    attempt_dir: Path,
    publish_root: Path,
    layout_path: Path,
    checker_report_path: Path,
    checker_process_path: Path,
    objective_path: Path,
    candidate_path: Path,
    acceptance_path: Path,
    geometry_result_path: Path,
    expected_layout_sha256: str,
    expected_layout_size_bytes: int,
) -> tuple[dict[str, Any], Path]:
    sources = {
        "layout": (layout_path, "layout.json"),
        "checker_report": (checker_report_path, "checker_report.json"),
        "checker_process": (checker_process_path, "checker_process.json"),
        "objective_audit": (objective_path, "objective_audit.json"),
        "candidate_diagnostics": (candidate_path, "candidate_diagnostics.json"),
        "acceptance": (acceptance_path, "acceptance.json"),
        "geometry_result": (geometry_result_path, "geometry_result.json"),
    }
    publications = {
        logical_name: run_supervisor.publish_content_addressed(
            source,
            publish_root,
            logical_name=publish_name,
        )
        for logical_name, (source, publish_name) in sources.items()
    }
    published_layout = publications["layout"]
    if (
        published_layout.sha256 != expected_layout_sha256
        or published_layout.size_bytes != expected_layout_size_bytes
    ):
        raise ConstructWitnessError(
            "PUBLISHED_LAYOUT_DRIFT",
            "published layout bytes differ from the bytes independently checked",
        )
    manifest, manifest_record = run_supervisor.publish_verified_manifest_content_addressed(
        publications,
        publish_root,
        relative_to=publish_root,
    )
    publication = {
        "status": "CONTENT_ADDRESSED_PUBLICATION_OK",
        "claim_boundary": CLAIM_BOUNDARY,
        "files": {name: record.as_dict() for name, record in sorted(publications.items())},
        "manifest": manifest,
        "manifest_artifact": manifest_record.as_dict(),
    }
    run_supervisor.write_json_exclusive(attempt_dir / "publication.json", publication)
    return publication, manifest_record.path


def _unsupported_box_record(box_count: int) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA,
        "status": "ATTEMPT_NOT_RUN",
        "classification": "UNSUPPORTED_BOX_GEOMETRY",
        "box_count": box_count,
        "message": "the current deterministic shelf candidate has no storage-box geometry adapter",
        "schedule_interpretation": "unsupported is not evidence that the box-count branch has no layout",
        "claim_boundary": CLAIM_BOUNDARY,
    }


def run_campaign(
    *,
    geometry_result: Path,
    project_root: Path = PROJECT_ROOT,
    run_root: Path = DEFAULT_RUN_ROOT,
    publish_root: Path = DEFAULT_PUBLISH_ROOT,
    checker_timeout_seconds: float = 120.0,
) -> CampaignOutcome:
    """Execute one no-overwrite 0/1/2-box witness campaign.

    This function does not start a subprocess or service for the geometry
    constructor.  Operators must invoke it inside the separately supervised
    resource envelope when the constructor uses a production-scale solver.
    """

    root = _resolve_project_root(project_root)
    head = _repository_head(root)
    if _FULL_SHA_RE.fullmatch(head) is None:
        raise ConstructWitnessError("GIT_HEAD_INVALID", repr(head))
    if head != EXPECTED_BASELINE_HEAD:
        raise ConstructWitnessError(
            "BASELINE_HEAD_MISMATCH",
            f"expected {EXPECTED_BASELINE_HEAD}, observed {head}",
        )
    if checker_timeout_seconds <= 0:
        raise ConstructWitnessError("CHECKER_TIMEOUT_INVALID", repr(checker_timeout_seconds))
    try:
        geometry_source = Path(geometry_result).resolve(strict=True)
    except OSError as exc:
        raise ConstructWitnessError("GEOMETRY_RESULT_PATH_INVALID", str(exc)) from exc
    if not geometry_source.is_file():
        raise ConstructWitnessError(
            "GEOMETRY_RESULT_PATH_INVALID",
            f"not a file: {geometry_source}",
        )
    geometry_source_record = run_supervisor.file_record(geometry_source)

    run_dir = run_supervisor.create_run_directory(Path(run_root), head[:7])
    summary_path = run_dir / "run_summary.json"
    attempts: list[dict[str, Any]] = []
    try:
        bundle, reconciliation = strict_contract.load_and_reconcile(root)
    except Exception as exc:
        failure = _exception_record(exc, phase="input_reconciliation")
        summary = {
            "schema_version": RUN_SCHEMA,
            "status": "RUN_FAILED",
            "repository_head": head,
            "box_schedule": list(BOX_SCHEDULE),
            "attempts": [],
            "failure": failure,
            "geometry_result_source": geometry_source_record.as_dict(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
        run_supervisor.write_json_exclusive(summary_path, summary)
        return CampaignOutcome(False, run_dir, summary_path, None, None, None)

    run_header = {
        "schema_version": RUN_SCHEMA,
        "status": "RUN_STARTED",
        "started_at_utc": _utc_now(),
        "project_root": str(root),
        "repository_head": head,
        "box_schedule": list(BOX_SCHEDULE),
        "stop_policy": "stop_after_first_independent_acceptance",
        "input_reconciliation": _reconciliation_record(reconciliation),
        "geometry_result_source": geometry_source_record.as_dict(),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    run_supervisor.write_json_exclusive(run_dir / "run_header.json", run_header)

    for ordinal, box_count in enumerate(BOX_SCHEDULE, 1):
        attempt_dir = run_supervisor.create_attempt_directory(run_dir, ordinal)
        if box_count:
            record = _unsupported_box_record(box_count)
            run_supervisor.write_json_exclusive(attempt_dir / "attempt_result.json", record)
            attempts.append({"ordinal": ordinal, **record})
            continue

        phase = "geometry_result_snapshot"
        checker: Any | None = None
        attempt_result_path = attempt_dir / "attempt_result.json"
        try:
            geometry_snapshot = run_supervisor.publish_content_addressed(
                geometry_source,
                attempt_dir,
                logical_name="geometry_result.json",
            )
            if (
                geometry_snapshot.sha256 != geometry_source_record.sha256
                or geometry_snapshot.size_bytes != geometry_source_record.size_bytes
            ):
                raise ConstructWitnessError(
                    "GEOMETRY_RESULT_SOURCE_DRIFT",
                    "worker result changed between run preflight and attempt snapshot",
                )
            attempt_header = {
                "schema_version": ATTEMPT_SCHEMA,
                "status": "ATTEMPT_STARTED",
                "ordinal": ordinal,
                "box_count": box_count,
                "repository_head": head,
                "input_sha256": dict(sorted(bundle.hashes.items())),
                "geometry_result_source": geometry_source_record.as_dict(),
                "geometry_result_snapshot": geometry_snapshot.as_dict(),
                "claim_boundary": CLAIM_BOUNDARY,
            }
            run_supervisor.write_json_exclusive(attempt_dir / "attempt_header.json", attempt_header)

            phase = "geometry_construction"
            candidate = shelf_constructor.construct_shelf_candidate(
                project_root=root,
                result_path=geometry_snapshot.path,
            )
            replay_after = run_supervisor.file_record(geometry_snapshot.path)
            if (
                replay_after.sha256 != geometry_snapshot.sha256
                or replay_after.size_bytes != geometry_snapshot.size_bytes
            ):
                raise ConstructWitnessError(
                    "GEOMETRY_RESULT_REPLAY_DRIFT",
                    "attempt snapshot changed while geometry was assembled",
                )
            phase = "witness_assembly"
            built = witness_campaign.build_witness(candidate, bundle=bundle)
            candidate_path = attempt_dir / "candidate_diagnostics.json"
            run_supervisor.write_json_exclusive(candidate_path, _candidate_record(candidate, built))

            phase = "layout_serialization"
            layout_payload = witness_io.canonical_json_bytes(built.witness)
            layout_sha256 = hashlib.sha256(layout_payload).hexdigest()
            layout_size_bytes = len(layout_payload)
            # The only checker input is content named by its own digest.  Every
            # later phase rechecks that identity, so a mutable staging filename
            # can never become the accepted or published witness.
            layout_path = attempt_dir / f"layout.{layout_sha256}.json"
            run_supervisor.write_bytes_exclusive(layout_path, layout_payload)
            phase = "objective_audit"
            serialized_audit = _audit_layout_file(bundle, layout_path)
            _require_file_identity(
                layout_path,
                sha256=layout_sha256,
                size_bytes=layout_size_bytes,
                code="LAYOUT_DRIFT_AFTER_OBJECTIVE_AUDIT",
            )
            if serialized_audit != built.objective:
                raise ConstructWitnessError(
                    "SERIALIZED_OBJECTIVE_DRIFT",
                    f"built={built.objective.as_dict()!r}, serialized={serialized_audit.as_dict()!r}",
                )
            objective_path = attempt_dir / "objective_audit.json"
            run_supervisor.write_json_exclusive(objective_path, serialized_audit.as_dict())

            phase = "independent_checker"
            checker = witness_io.run_independent_checker(
                bundle.strict_instance.path,
                layout_path,
                timeout_seconds=checker_timeout_seconds,
            )
            _require_file_identity(
                layout_path,
                sha256=layout_sha256,
                size_bytes=layout_size_bytes,
                code="LAYOUT_DRIFT_AFTER_INDEPENDENT_CHECKER",
            )
            checker_process_path = attempt_dir / "checker_process.json"
            run_supervisor.write_json_exclusive(checker_process_path, _checker_record(checker))
            checker_report_path = attempt_dir / "checker_report.json"
            if checker.report is None:
                run_supervisor.write_json_exclusive(
                    checker_report_path,
                    {
                        "status": "CHECKER_REPORT_UNAVAILABLE",
                        "classification": checker.classification,
                    },
                )
            else:
                run_supervisor.write_json_exclusive(checker_report_path, checker.report)

            # Both calls are intentional: the campaign layer checks its own
            # in-memory result, while this runner checks the serialized bytes.
            phase = "independent_acceptance"
            witness_campaign.accept_independent_checker(built, checker)
            acceptance = _require_exact_checker_agreement(serialized_audit, checker)
            acceptance.update(
                {
                    "schema_version": ATTEMPT_SCHEMA,
                    "ordinal": ordinal,
                    "box_count": box_count,
                    "repository_head": head,
                    "input_sha256": dict(sorted(bundle.hashes.items())),
                }
            )
            acceptance_path = attempt_dir / "acceptance.json"
            run_supervisor.write_json_exclusive(acceptance_path, acceptance)
            phase = "content_addressed_publication"
            publication, manifest_path = _publish_accepted_attempt(
                attempt_dir=attempt_dir,
                publish_root=Path(publish_root),
                layout_path=layout_path,
                checker_report_path=checker_report_path,
                checker_process_path=checker_process_path,
                objective_path=objective_path,
                candidate_path=candidate_path,
                acceptance_path=acceptance_path,
                geometry_result_path=geometry_snapshot.path,
                expected_layout_sha256=layout_sha256,
                expected_layout_size_bytes=layout_size_bytes,
            )
            attempt_result = {
                "schema_version": ATTEMPT_SCHEMA,
                "status": "ATTEMPT_ACCEPTED",
                "ordinal": ordinal,
                "box_count": box_count,
                "checker_classification": checker.classification,
                "geometry_result_sha256": geometry_snapshot.sha256,
                "objective": asdict(serialized_audit.computed),
                "feasible_lower_bound": acceptance["feasible_lower_bound"],
                "publication_manifest": publication["manifest_artifact"],
                "claim_boundary": CLAIM_BOUNDARY,
            }
            run_supervisor.write_json_exclusive(attempt_result_path, attempt_result)
            attempts.append(attempt_result)
            summary = {
                "schema_version": RUN_SCHEMA,
                "status": "LAYOUT_ACCEPTED",
                "repository_head": head,
                "box_schedule": list(BOX_SCHEDULE),
                "stop_policy": "stop_after_first_independent_acceptance",
                "accepted_attempt": ordinal,
                "attempts": attempts,
                "input_reconciliation": _reconciliation_record(reconciliation),
                "geometry_result_source": geometry_source_record.as_dict(),
                "feasible_lower_bound": acceptance["feasible_lower_bound"],
                "claim_boundary": CLAIM_BOUNDARY,
            }
            run_supervisor.write_json_exclusive(summary_path, summary)
            return CampaignOutcome(
                True,
                run_dir,
                summary_path,
                ordinal,
                layout_path,
                manifest_path,
            )
        except Exception as exc:
            if attempt_result_path.exists():
                # Never rewrite a terminal record.  If a later filesystem
                # operation fails, preserve both facts in a distinct artifact.
                terminal_failure = {
                    "schema_version": ATTEMPT_SCHEMA,
                    "ordinal": ordinal,
                    "box_count": box_count,
                    **_exception_record(exc, phase=phase),
                }
                run_supervisor.write_json_exclusive(
                    attempt_dir / "post_result_failure.json",
                    terminal_failure,
                )
                raise
            failure = {
                "schema_version": ATTEMPT_SCHEMA,
                "ordinal": ordinal,
                "box_count": box_count,
                **_exception_record(exc, phase=phase),
            }
            if checker is not None:
                failure["checker_classification"] = checker.classification
                failure["checker_sha256"] = checker.checker_sha256
                failure["checker_stderr"] = checker.stderr
            run_supervisor.write_json_exclusive(attempt_result_path, failure)
            attempts.append(failure)

    summary = {
        "schema_version": RUN_SCHEMA,
        "status": "NO_ACCEPTED_LAYOUT",
        "repository_head": head,
        "box_schedule": list(BOX_SCHEDULE),
        "attempts": attempts,
        "unsupported_box_counts": [
            record["box_count"]
            for record in attempts
            if record.get("classification") == "UNSUPPORTED_BOX_GEOMETRY"
        ],
        "schedule_interpretation": "unsupported branches carry no feasibility conclusion",
        "input_reconciliation": _reconciliation_record(reconciliation),
        "geometry_result_source": geometry_source_record.as_dict(),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    run_supervisor.write_json_exclusive(summary_path, summary)
    return CampaignOutcome(False, run_dir, summary_path, None, None, None)


def verify_layout(
    layout_path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    run_root: Path = DEFAULT_RUN_ROOT,
    checker_timeout_seconds: float = 120.0,
) -> VerificationOutcome:
    """Rerun both independent acceptance layers on an existing layout."""

    root = _resolve_project_root(project_root)
    head = _repository_head(root)
    if _FULL_SHA_RE.fullmatch(head) is None:
        raise ConstructWitnessError("GIT_HEAD_INVALID", repr(head))
    if head != EXPECTED_BASELINE_HEAD:
        raise ConstructWitnessError(
            "BASELINE_HEAD_MISMATCH",
            f"expected {EXPECTED_BASELINE_HEAD}, observed {head}",
        )
    if checker_timeout_seconds <= 0:
        raise ConstructWitnessError("CHECKER_TIMEOUT_INVALID", repr(checker_timeout_seconds))
    try:
        source = Path(layout_path).resolve(strict=True)
    except OSError as exc:
        raise ConstructWitnessError("LAYOUT_PATH_INVALID", str(exc)) from exc
    if not source.is_file():
        raise ConstructWitnessError("LAYOUT_PATH_INVALID", f"not a file: {source}")
    source_record = run_supervisor.file_record(source)
    bundle, reconciliation = strict_contract.load_and_reconcile(root)
    run_dir = run_supervisor.create_run_directory(Path(run_root), head[:7])
    attempt_dir = run_supervisor.create_attempt_directory(run_dir, 1)
    report_path = attempt_dir / "verification_report.json"
    checked_snapshot = run_supervisor.publish_content_addressed(
        source,
        attempt_dir,
        logical_name="layout.json",
    )
    if (
        checked_snapshot.sha256 != source_record.sha256
        or checked_snapshot.size_bytes != source_record.size_bytes
    ):
        raise ConstructWitnessError(
            "LAYOUT_SOURCE_DRIFT",
            "layout changed between verification preflight and stable snapshot",
        )
    checked_layout = checked_snapshot.path

    audit: Any | None = None
    audit_failure: dict[str, Any] | None = None
    try:
        audit = _audit_layout_file(bundle, checked_layout)
        _require_file_identity(
            checked_layout,
            sha256=checked_snapshot.sha256,
            size_bytes=checked_snapshot.size_bytes,
            code="LAYOUT_DRIFT_AFTER_OBJECTIVE_AUDIT",
        )
    except Exception as exc:
        audit_failure = _exception_record(exc, phase="objective_audit")

    checker = witness_io.run_independent_checker(
        bundle.strict_instance.path,
        checked_layout,
        timeout_seconds=checker_timeout_seconds,
    )
    try:
        _require_file_identity(
            checked_layout,
            sha256=checked_snapshot.sha256,
            size_bytes=checked_snapshot.size_bytes,
            code="LAYOUT_DRIFT_AFTER_INDEPENDENT_CHECKER",
        )
    except Exception as exc:
        checker = witness_io.CheckerProcessResult(
            classification=getattr(exc, "code", "LAYOUT_DRIFT_AFTER_INDEPENDENT_CHECKER"),
            exit_code=None,
            status=None,
            report=None,
            stdout=checker.stdout,
            stderr=str(exc),
            checker_trusted=checker.checker_trusted,
            checker_sha256=checker.checker_sha256,
            checker_source_path=checker.checker_source_path,
            checker_source_identity=checker.checker_source_identity,
            checker_snapshot_size_bytes=checker.checker_snapshot_size_bytes,
            checker_python_executable=checker.checker_python_executable,
            checker_execution_mode=checker.checker_execution_mode,
        )
    acceptance: dict[str, Any] | None = None
    acceptance_failure: dict[str, Any] | None = None
    if audit is not None:
        try:
            acceptance = _require_exact_checker_agreement(audit, checker)
        except Exception as exc:
            acceptance_failure = _exception_record(exc, phase="independent_acceptance")

    accepted = acceptance is not None and audit_failure is None
    report = {
        "schema_version": VERIFY_SCHEMA,
        "status": "LAYOUT_ACCEPTED" if accepted else "LAYOUT_REJECTED",
        "repository_head": head,
        "layout_source": source_record.as_dict(),
        "checked_layout_snapshot": checked_snapshot.as_dict(),
        "input_reconciliation": _reconciliation_record(reconciliation),
        "objective_audit": audit.as_dict() if audit is not None else None,
        "objective_audit_failure": audit_failure,
        "checker": _checker_record(checker),
        "acceptance": acceptance,
        "acceptance_failure": acceptance_failure,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    run_supervisor.write_json_exclusive(report_path, report)
    return VerificationOutcome(accepted, run_dir, report_path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or recheck a routing-aware research witness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="build and independently check one fresh witness run")
    run_parser.add_argument(
        "--geometry-result",
        type=Path,
        required=True,
        help="explicit geometry worker JSON to replay; no latest-result discovery is performed",
    )
    run_parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    run_parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    run_parser.add_argument("--publish-root", type=Path, default=DEFAULT_PUBLISH_ROOT)
    run_parser.add_argument("--checker-timeout-seconds", type=float, default=120.0)

    verify_parser = subparsers.add_parser("verify", help="recheck an existing strict layout")
    verify_parser.add_argument("layout", type=Path)
    verify_parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    verify_parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    verify_parser.add_argument("--checker-timeout-seconds", type=float, default=120.0)
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        run_root = _require_cli_output_scope(args.run_root)
        if args.command == "run":
            publish_root = _require_cli_output_scope(args.publish_root)
            outcome = run_campaign(
                geometry_result=args.geometry_result,
                project_root=args.project_root,
                run_root=run_root,
                publish_root=publish_root,
                checker_timeout_seconds=args.checker_timeout_seconds,
            )
            print(
                json.dumps(
                    {
                        "accepted": outcome.accepted,
                        "run_dir": str(outcome.run_dir),
                        "summary": str(outcome.summary_path),
                        "manifest": str(outcome.manifest_path) if outcome.manifest_path else None,
                        "claim_boundary": CLAIM_BOUNDARY,
                    },
                    sort_keys=True,
                )
            )
            return 0 if outcome.accepted else 1

        outcome = verify_layout(
            args.layout,
            project_root=args.project_root,
            run_root=run_root,
            checker_timeout_seconds=args.checker_timeout_seconds,
        )
        print(
            json.dumps(
                {
                    "accepted": outcome.accepted,
                    "run_dir": str(outcome.run_dir),
                    "report": str(outcome.report_path),
                    "claim_boundary": CLAIM_BOUNDARY,
                },
                sort_keys=True,
            )
        )
        return 0 if outcome.accepted else 1
    except (ConstructWitnessError, run_supervisor.SupervisorError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()


__all__ = [
    "BOX_SCHEDULE",
    "CLAIM_BOUNDARY",
    "CampaignOutcome",
    "ConstructWitnessError",
    "VerificationOutcome",
    "run_campaign",
    "run_cli",
    "verify_layout",
]
