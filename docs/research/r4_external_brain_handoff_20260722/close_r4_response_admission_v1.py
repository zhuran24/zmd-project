#!/usr/bin/env python3
"""Close R4 response admission only after archive, recomputation, and review."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
SELECTOR_PATH = RESEARCH_DIR / "select_r4_ready_receipt_v1.py"
RECOMPUTATION_RUNNER_PATH = RESEARCH_DIR / "run_r4_local_recomputation_v1.py"
STRICT_INSTANCE_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
IDENTITY_KEYS = {"relative_path", "size_bytes", "sha256"}
FILE_RECORD_KEYS = {"path", "size_bytes", "sha256"}


class AdmissionError(RuntimeError):
    """Fail-closed R4 admission error."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise AdmissionError(f"symlink is not a provenance file: {path}")
    resolved = path.resolve(strict=True)
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise AdmissionError(f"not a regular provenance file: {resolved}")
    return {"path": str(resolved), "size_bytes": resolved.stat().st_size, "sha256": _sha256(resolved)}


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise AdmissionError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise AdmissionError(f"non-finite JSON value in {path}: {value}")

    try:
        value = json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"cannot parse local control JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AdmissionError(f"local control JSON is not an object: {path}")
    return value


def _strict_json_value(raw: bytes, label: str) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise AdmissionError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise AdmissionError(f"non-finite JSON value in {label}: {value}")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"cannot parse checker JSON output {label}: {exc}") from exc


def _identity(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != IDENTITY_KEYS:
        raise AdmissionError(f"{label} is not an exact selected receipt identity")
    relative, size, digest = value.get("relative_path"), value.get("size_bytes"), value.get("sha256")
    if type(relative) is not str or not relative:
        raise AdmissionError(f"{label}.relative_path is malformed")
    path = Path(relative)
    if path.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in path.parts):
        raise AdmissionError(f"{label}.relative_path is not normalized")
    if type(size) is not int or size < 0:
        raise AdmissionError(f"{label}.size_bytes is malformed")
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise AdmissionError(f"{label}.sha256 is malformed")
    return {"relative_path": relative, "size_bytes": size, "sha256": digest}


def _file_record(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != FILE_RECORD_KEYS:
        raise AdmissionError(f"{label} is not an exact file record")
    path_value = value.get("path")
    if type(path_value) is not str or not Path(path_value).is_absolute():
        raise AdmissionError(f"{label}.path must be absolute")
    expected = {"path": path_value, "size_bytes": value.get("size_bytes"), "sha256": value.get("sha256")}
    if _record(Path(path_value)) != expected:
        raise AdmissionError(f"{label} bytes are stale")
    return expected


def _selector() -> ModuleType:
    if not SELECTOR_PATH.is_file() or SELECTOR_PATH.is_symlink():
        raise AdmissionError(f"local READY selector is unavailable: {SELECTOR_PATH}")
    name = "_r4_ready_selector_for_response_admission"
    spec = importlib.util.spec_from_file_location(name, SELECTOR_PATH)
    if spec is None or spec.loader is None:
        raise AdmissionError("cannot load local READY selector")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _recomputation_runner() -> ModuleType:
    if not RECOMPUTATION_RUNNER_PATH.is_file() or RECOMPUTATION_RUNNER_PATH.is_symlink():
        raise AdmissionError(f"local recomputation runner is unavailable: {RECOMPUTATION_RUNNER_PATH}")
    name = "_r4_local_recomputation_for_response_admission"
    spec = importlib.util.spec_from_file_location(name, RECOMPUTATION_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise AdmissionError("cannot load local recomputation runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _check_selected(authority_run: Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    checker = getattr(_selector(), "check_selected_receipt", None)
    if not callable(checker):
        raise AdmissionError("local READY selector lacks check_selected_receipt")
    try:
        result = checker(authority_run, expected_identity=dict(identity))
    except Exception as exc:
        raise AdmissionError(f"selected receipt failed semantic/byte replay: {exc}") from exc
    if not isinstance(result, Mapping):
        raise AdmissionError("selected receipt checker returned a malformed result")
    return dict(result)


def _validate_archive(response_run: Path, authority_run: Path) -> dict[str, Any]:
    intent = _strict_json(response_run / "canonical-intent.json")
    ingest = _strict_json(response_run / "response-ingest.json")
    if intent.get("schema") != "r4_canonical_intent_v1":
        raise AdmissionError("canonical intent schema is invalid")
    if ingest.get("schema") != "r4_response_ingest_v1" or ingest.get("status") != "ARCHIVED_PENDING_RECOMPUTATION":
        raise AdmissionError("response ingest is not terminally archived")
    identity = _identity(ingest.get("selected_receipt_identity"), "response_ingest.selected_receipt_identity")
    if _identity(intent.get("selected_receipt_identity"), "canonical_intent.selected_receipt_identity") != identity:
        raise AdmissionError("canonical intent selected receipt identity differs")
    selection = _check_selected(authority_run, identity)
    raw = _file_record(ingest.get("raw_response"), "response_ingest.raw_response")
    canonical = _file_record(ingest.get("canonical_document"), "response_ingest.canonical_document")
    if _file_record(intent.get("raw_response"), "canonical_intent.raw_response") != raw:
        raise AdmissionError("canonical intent raw response differs")
    if intent.get("canonical_target") != canonical["path"]:
        raise AdmissionError("canonical intent target differs")
    if (raw["size_bytes"], raw["sha256"]) != (canonical["size_bytes"], canonical["sha256"]):
        raise AdmissionError("raw and canonical response bytes differ")
    if ingest.get("raw_canonical_byte_equal") is not True:
        raise AdmissionError("response ingest did not close raw/canonical equality")
    package_id = ingest.get("package_id")
    if type(package_id) is not str or package_id != intent.get("package_id"):
        raise AdmissionError("response package identity is absent or inconsistent")
    if selection.get("package_id") not in {None, package_id}:
        raise AdmissionError("selected receipt package identity differs from response ingest")
    return {
        "selected_receipt_identity": identity,
        "package_id": package_id,
        "raw_response": raw,
        "canonical_document": canonical,
    }


def _validate_ledger(path: Path, provenance: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger = _strict_json(path)
    if ledger.get("schema") != "r4_quantitative_claim_ledger_v1":
        raise AdmissionError("claim ledger schema is invalid")
    if ledger.get("status") != "COMPLETE" or ledger.get("quantitative_claims_complete") is not True:
        raise AdmissionError("quantitative claim ledger is incomplete")
    if (
        _identity(ledger.get("selected_receipt_identity"), "claim_ledger.selected_receipt_identity")
        != provenance["selected_receipt_identity"]
    ):
        raise AdmissionError("claim ledger selected receipt identity differs")
    if ledger.get("package_id") != provenance["package_id"]:
        raise AdmissionError("claim ledger package identity differs")
    if _file_record(ledger.get("raw_response"), "claim_ledger.raw_response") != provenance["raw_response"]:
        raise AdmissionError("claim ledger raw response binding differs")
    if (
        _file_record(ledger.get("canonical_document"), "claim_ledger.canonical_document")
        != provenance["canonical_document"]
    ):
        raise AdmissionError("claim ledger canonical document binding differs")
    if ledger.get("raw_canonical_byte_equal") is not True:
        raise AdmissionError("claim ledger did not close raw/canonical equality")
    claims = ledger.get("claims")
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
        raise AdmissionError("claim ledger claims must be an array")
    by_id: dict[str, dict[str, Any]] = {}
    raw_size = provenance["raw_response"]["size_bytes"]
    for item in claims:
        if not isinstance(item, Mapping) or type(item.get("claim_id")) is not str:
            raise AdmissionError("claim ledger contains a malformed claim")
        claim_id = item["claim_id"]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", claim_id) is None:
            raise AdmissionError(f"claim ledger contains an invalid claim_id: {claim_id}")
        if claim_id in by_id:
            raise AdmissionError(f"duplicate claim_id: {claim_id}")
        span = item.get("source_byte_span")
        if not isinstance(span, Mapping) or set(span) != {"start", "end"}:
            raise AdmissionError(f"claim {claim_id} has an invalid source byte span")
        start, end = span.get("start"), span.get("end")
        if type(start) is not int or type(end) is not int or not (0 <= start < end <= raw_size):
            raise AdmissionError(f"claim {claim_id} source byte span is out of range")
        if "expected_result" not in item:
            raise AdmissionError(f"claim {claim_id} lacks expected_result")
        by_id[claim_id] = dict(item)
    runner = _recomputation_runner()
    ledger_checker = getattr(runner, "validate_claim_ledger", None)
    if not callable(ledger_checker):
        raise AdmissionError("local recomputation runner lacks validate_claim_ledger")
    try:
        replayed_ledger, replayed_claims = ledger_checker(path, provenance)
    except Exception as exc:
        raise AdmissionError(f"claim ledger runner replay failed: {exc}") from exc
    if replayed_ledger != ledger or replayed_claims != by_id:
        raise AdmissionError("claim ledger differs from local recomputation runner replay")
    return ledger, by_id


def _validate_reports(
    report_paths: Sequence[Path],
    ledger_path: Path,
    claims: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger_record = _record(ledger_path)
    runner_record = _record(RECOMPUTATION_RUNNER_PATH)
    runner = _recomputation_runner()
    script_checker = getattr(runner, "validate_local_script", None)
    argv_builder = getattr(runner, "build_sandbox_argv", None)
    if not callable(script_checker) or not callable(argv_builder):
        raise AdmissionError("local recomputation runner lacks policy replay helpers")
    reports: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in report_paths:
        resolved = path.resolve(strict=True)
        report = _strict_json(resolved)
        if report.get("schema") != "r4_local_recomputation_report_v1" or report.get("status") != "PASS_EXACT_MATCH":
            raise AdmissionError(f"recomputation report is not PASS_EXACT_MATCH: {resolved}")
        claim_id = report.get("claim_id")
        if type(claim_id) is not str or claim_id not in claims or claim_id in seen:
            raise AdmissionError(f"recomputation report claim binding is invalid: {claim_id}")
        seen.add(claim_id)
        if (
            _identity(report.get("selected_receipt_identity"), f"report[{claim_id}].selected_receipt_identity")
            != provenance["selected_receipt_identity"]
        ):
            raise AdmissionError(f"recomputation report {claim_id} selected receipt identity differs")
        if report.get("package_id") != provenance["package_id"]:
            raise AdmissionError(f"recomputation report {claim_id} package identity differs")
        if _file_record(report.get("raw_response"), f"report[{claim_id}].raw_response") != provenance["raw_response"]:
            raise AdmissionError(f"recomputation report {claim_id} raw response binding differs")
        if (
            _file_record(report.get("canonical_document"), f"report[{claim_id}].canonical_document")
            != provenance["canonical_document"]
        ):
            raise AdmissionError(f"recomputation report {claim_id} canonical document binding differs")
        if _file_record(report.get("claim_ledger"), f"report[{claim_id}].claim_ledger") != ledger_record:
            raise AdmissionError(f"recomputation report {claim_id} claim ledger binding differs")
        if _file_record(report.get("runner_tool"), f"report[{claim_id}].runner_tool") != runner_record:
            raise AdmissionError(f"recomputation report {claim_id} runner tool binding differs")
        if report.get("claim_ledger_status") != "COMPLETE":
            raise AdmissionError(f"recomputation report {claim_id} did not bind a complete claim ledger")
        if report.get("source_byte_span") != claims[claim_id].get("source_byte_span"):
            raise AdmissionError(f"recomputation report {claim_id} source byte span differs")
        if report.get("expected_result") != claims[claim_id].get("expected_result") or type(
            report.get("expected_result")
        ) is not type(claims[claim_id].get("expected_result")):
            raise AdmissionError(f"recomputation report {claim_id} expected result differs")
        local_script = report.get("local_script")
        sandbox = report.get("sandbox")
        if (
            not isinstance(local_script, Mapping)
            or local_script.get("locally_rederived_from_claim_only") is not True
            or local_script.get("less_than_200_lines") is not True
            or local_script.get("ast_policy") != "PASS"
            or type(local_script.get("physical_line_count")) is not int
            or not 0 < local_script["physical_line_count"] < 200
        ):
            raise AdmissionError(f"recomputation report {claim_id} local-script policy is invalid")
        script_path = local_script.get("path")
        if type(script_path) is not str:
            raise AdmissionError(f"recomputation report {claim_id} local-script path is malformed")
        embedded_script_record = {
            "path": script_path,
            "size_bytes": local_script.get("size_bytes"),
            "sha256": local_script.get("sha256"),
        }
        if _file_record(embedded_script_record, f"report[{claim_id}].local_script") != embedded_script_record:
            raise AdmissionError(f"recomputation report {claim_id} local checker bytes differ")
        try:
            current_policy = script_checker(Path(script_path))
        except Exception as exc:
            raise AdmissionError(f"recomputation report {claim_id} local checker policy replay failed: {exc}") from exc
        for key, value in current_policy.items():
            if local_script.get(key) != value:
                raise AdmissionError(f"recomputation report {claim_id} local checker policy differs at {key}")
        if (
            not isinstance(sandbox, Mapping)
            or sandbox.get("offline") is not True
            or sandbox.get("bwrap_unshare_net") is not True
            or sandbox.get("host_response_not_bound") is not True
            or sandbox.get("timed_out") is not False
            or sandbox.get("returncode") != 0
            or sandbox.get("timeout_seconds") != 60
        ):
            raise AdmissionError(f"recomputation report {claim_id} sandbox result is invalid")
        if (
            report.get("receipt_semantic_replay_pass") is not True
            or report.get("receipt_detached_byte_match") is not True
            or report.get("raw_canonical_byte_equal") is not True
            or report.get("output_parse_error") is not None
        ):
            raise AdmissionError(f"recomputation report {claim_id} provenance gate flags are invalid")
        strict_instance = _file_record(report.get("strict_instance"), f"report[{claim_id}].strict_instance")
        if strict_instance["sha256"] != STRICT_INSTANCE_SHA256:
            raise AdmissionError(f"recomputation report {claim_id} strict instance differs")
        try:
            expected_argv = argv_builder(Path(script_path), Path(strict_instance["path"]))
        except Exception as exc:
            raise AdmissionError(f"recomputation report {claim_id} sandbox argv replay failed: {exc}") from exc
        if sandbox.get("argv") != expected_argv:
            raise AdmissionError(f"recomputation report {claim_id} sandbox argv differs")
        stdout_record = _file_record(report.get("stdout"), f"report[{claim_id}].stdout")
        _file_record(report.get("stderr"), f"report[{claim_id}].stderr")
        actual = _strict_json_value(Path(stdout_record["path"]).read_bytes(), f"report[{claim_id}].stdout")
        expected = claims[claim_id].get("expected_result")
        if (
            actual != expected
            or type(actual) is not type(expected)
            or report.get("actual_result") != actual
            or type(report.get("actual_result")) is not type(actual)
        ):
            raise AdmissionError(f"recomputation report {claim_id} exact result replay differs")
        reports.append(report)
        bindings.append({"claim_id": claim_id, "report": _record(resolved)})
    if seen != set(claims):
        raise AdmissionError(
            f"recomputation coverage differs: missing={sorted(set(claims) - seen)}, extra={sorted(seen - set(claims))}"
        )
    bindings.sort(key=lambda item: item["claim_id"])
    return reports, bindings


def _validate_verdict(
    path: Path,
    ledger_path: Path,
    report_bindings: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    verdict = _strict_json(path)
    if verdict.get("schema") != "r4_adversarial_verdict_v1" or verdict.get("status") != "PASS":
        raise AdmissionError("adversarial verdict is not PASS")
    if (
        verdict.get("quantitative_recomputation_status") != "PASS"
        or verdict.get("adversarial_review_started_after_recomputation") is not True
    ):
        raise AdmissionError("adversarial verdict does not bind the completed recomputation gate")
    if (
        _identity(verdict.get("selected_receipt_identity"), "adversarial_verdict.selected_receipt_identity")
        != provenance["selected_receipt_identity"]
    ):
        raise AdmissionError("adversarial verdict selected receipt identity differs")
    if verdict.get("package_id") != provenance["package_id"]:
        raise AdmissionError("adversarial verdict package identity differs")
    if _file_record(verdict.get("raw_response"), "adversarial_verdict.raw_response") != provenance["raw_response"]:
        raise AdmissionError("adversarial verdict raw response binding differs")
    if (
        _file_record(verdict.get("canonical_document"), "adversarial_verdict.canonical_document")
        != provenance["canonical_document"]
    ):
        raise AdmissionError("adversarial verdict canonical document binding differs")
    if _file_record(verdict.get("claim_ledger"), "adversarial_verdict.claim_ledger") != _record(ledger_path):
        raise AdmissionError("adversarial verdict claim ledger binding differs")
    if verdict.get("recomputation_reports") != list(report_bindings):
        raise AdmissionError("adversarial verdict recomputation report multiset differs")
    return verdict


def _publish_json(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    if path.exists() or path.is_symlink():
        raise AdmissionError(f"no-overwrite target exists: {path}")
    pending = path.with_name(f".{path.name}.pending-{os.getpid():010d}")
    with pending.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.link(pending, path, follow_symlinks=False)
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    try:
        pending.unlink()
    except OSError:
        pass


def close_admission(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    report_paths: Sequence[Path],
    adversarial_verdict_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    authority_run = authority_run.resolve(strict=True)
    response_run = response_run.resolve(strict=True)
    ledger_path = ledger_path.resolve(strict=True)
    provenance = _validate_archive(response_run, authority_run)
    _ledger, claims = _validate_ledger(ledger_path, provenance)
    _reports, bindings = _validate_reports(report_paths, ledger_path, claims, provenance)
    verdict_path = adversarial_verdict_path.resolve(strict=True)
    _validate_verdict(verdict_path, ledger_path, bindings, provenance)
    _check_selected(authority_run, provenance["selected_receipt_identity"])
    output_dir = output_dir.absolute()
    output_dir.mkdir(parents=True, exist_ok=False)
    admission = {
        "schema": "r4_response_admission_v1",
        "created_at_utc": _utc_now(),
        "status": "ADMITTED_FOR_B1_ENCODER_DESIGN",
        "claim_boundary": "paper-proof-and-encoder-funnel-only; no bound change or formal-run authorization",
        "package_id": provenance["package_id"],
        "selected_receipt_identity": provenance["selected_receipt_identity"],
        "receipt_semantic_replay_pass": True,
        "receipt_detached_byte_match": True,
        "raw_response": provenance["raw_response"],
        "canonical_document": provenance["canonical_document"],
        "raw_canonical_byte_equal": True,
        "claim_ledger": _record(ledger_path),
        "recomputation_reports": bindings,
        "adversarial_verdict": _record(verdict_path),
        "gates": {
            "verbatim_archive": "PASS",
            "all_quantitative_claims_independently_recomputed": "PASS",
            "adversarial_review": "PASS",
        },
        "upper_bound_changed": False,
        "witness_established": False,
        "optimality_established": False,
        "formal_run_authorized": False,
    }
    _publish_json(output_dir / "admission.json", admission)
    return admission


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-run", type=Path, required=True)
    parser.add_argument("--response-run", type=Path, required=True)
    parser.add_argument("--claim-ledger", type=Path, required=True)
    parser.add_argument("--recomputation-report", type=Path, action="append", default=[])
    parser.add_argument("--adversarial-verdict", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="new no-overwrite admission directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = close_admission(
            args.authority_run,
            args.response_run,
            args.claim_ledger,
            args.recomputation_report,
            args.adversarial_verdict,
            args.output_dir,
        )
    except (AdmissionError, FileExistsError, OSError) as exc:
        print(f"R4_RESPONSE_ADMISSION_FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
