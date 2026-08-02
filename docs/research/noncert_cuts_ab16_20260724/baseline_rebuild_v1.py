#!/usr/bin/env python3
"""Rebuild the historical AB16 baseline from package-pinned strict inputs.

This is a formal-stage payload.  Importing it is side-effect free; the CLI is
only run after the self-contained campaign bootstrap.  Its output is
evidence for the independent baseline admission tool, never an admission by
itself.  Repository code is imported with ordinary Python semantics only from
the tracked-clean pinned checkout named by the canonical campaign-provenance record.
Every data input is an exact package-pinned member of that same checkout.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from typing import Any

import baseline_admission_v1 as baseline_contract
from ortools.sat import cp_model_pb2


SCHEMA = "noncert-cuts-ab16-baseline-rebuild-v1"
METADATA_SCHEMA = baseline_contract.METADATA_SCHEMA
MODEL_BACKEND = "ortools.sat.cp_model_pb2.CpModelProto"
MODEL_BINARY_FORMAT = "deterministic-protobuf-v1"
REBUILD_PURPOSE = "strict_ab16_baseline_model_rebuild"
STRICT_INPUT_ROLES = (
    "candidate_placements",
    "canonical_rules",
    "mandatory_instances",
)


class BaselineRebuildError(RuntimeError):
    """The deterministic baseline could not be rebuilt exactly."""


@dataclass(frozen=True)
class BaselineComputation:
    """Solver-produced values consumed by the one canonical rebuild writer."""

    model: cp_model_pb2.CpModelProto
    incumbent: Mapping[str, Any]
    solution_values: tuple[int, ...]
    runner_status: str
    proof_summary: Mapping[str, Any]
    wall_seconds: float


@dataclass(frozen=True)
class _RebuildContext:
    output: Path
    campaign_provenance_path: Path
    provenance: dict[str, object]
    input_identities: dict[str, dict[str, object]]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _authority_json(value: object) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _jsonable(value: object) -> object:
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def _reject_symlink_chain(
    path: Path,
    *,
    leaf_may_not_exist: bool,
) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for index, part in enumerate(absolute.parts[1:]):
        current /= part
        is_leaf = index == len(absolute.parts[1:]) - 1
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if leaf_may_not_exist and is_leaf:
                return absolute
            raise BaselineRebuildError(f"path component is missing: {current}") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise BaselineRebuildError(f"symlink path component is forbidden: {current}")
    return absolute


def _snapshot_regular(path: Path, *, limit: int) -> tuple[bytes, dict[str, object]]:
    absolute = _reject_symlink_chain(
        path,
        leaf_may_not_exist=False,
    )
    descriptor = os.open(
        absolute,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise BaselineRebuildError(f"invalid strict input: {absolute}")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1 << 20, remaining))
            if not chunk:
                raise BaselineRebuildError(f"truncated strict input: {absolute}")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise BaselineRebuildError(f"growing strict input: {absolute}")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    def signature(item: os.stat_result) -> tuple[int, ...]:
        return (
            item.st_dev,
            item.st_ino,
            item.st_mode,
            item.st_nlink,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )

    if signature(before) != signature(after):
        raise BaselineRebuildError(f"strict input changed during read: {absolute}")
    raw = b"".join(chunks)
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _campaign_provenance(path: Path) -> dict[str, object]:
    try:
        return baseline_contract.campaign_provenance(path)
    except baseline_contract.AdmissionError as exc:
        raise BaselineRebuildError(f"campaign provenance failed closed: {exc}") from exc


def _require_repository_imports(repository_root: Path) -> None:
    for name, module in tuple(sys.modules.items()):
        if name != "src" and not name.startswith("src."):
            continue
        source = getattr(module, "__file__", None)
        if type(source) is str:
            if not Path(os.path.abspath(source)).is_relative_to(repository_root):
                raise BaselineRebuildError(f"repository module imported outside pinned checkout: {name}")
            continue
        search_path = getattr(module, "__path__", None)
        if search_path is None or any(
            not Path(os.path.abspath(item)).is_relative_to(repository_root)
            for item in search_path
        ):
            raise BaselineRebuildError(f"repository package imported outside pinned checkout: {name}")


def _write_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    if path.is_symlink():
        raise BaselineRebuildError(f"symlink output rejected: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise BaselineRebuildError(f"short write: {path}")
            view = view[written:]
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    return {
        "path": str(path.resolve(strict=True)),
        "size_bytes": metadata.st_size,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _prepare_output(path: Path, campaign_provenance: Path) -> Path:
    absolute = _reject_symlink_chain(
        path,
        leaf_may_not_exist=False,
    )
    provenance = _reject_symlink_chain(
        campaign_provenance,
        leaf_may_not_exist=False,
    )
    expected_provenance = absolute / "campaign-provenance.json"
    if provenance != expected_provenance:
        raise BaselineRebuildError("campaign provenance is not the canonical output child")
    metadata = os.lstat(absolute)
    if not stat.S_ISDIR(metadata.st_mode):
        raise BaselineRebuildError("output must be the precreated non-symlink baseline directory")
    members = list(absolute.iterdir())
    if len(members) != 1 or members[0] != expected_provenance:
        raise BaselineRebuildError("output must initially contain only campaign-provenance.json")
    _snapshot_regular(expected_provenance, limit=64 << 20)
    return absolute


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--campaign-provenance", required=True, type=Path)
    parser.add_argument("--master-seconds", type=float, default=900.0)
    parser.add_argument("--binding-seconds", type=float, default=600.0)
    parser.add_argument("--routing-seconds", type=float, default=600.0)
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--binding-alt-cap", type=int, default=200)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026072301)
    parser.add_argument("--ghost-w", type=int, default=6)
    parser.add_argument("--ghost-h", type=int, default=6)
    parser.add_argument(
        "--candidate-placements",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--canonical-rules",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--mandatory-instances",
        type=Path,
        required=True,
    )
    return parser


def _validate_fixed_parameters(args: argparse.Namespace) -> None:
    expected = {
        "master_seconds": 900.0,
        "binding_seconds": 600.0,
        "routing_seconds": 600.0,
        "max_iterations": 30,
        "binding_alt_cap": 200,
        "workers": 1,
        "seed": 2026072301,
        "ghost_w": 6,
        "ghost_h": 6,
    }
    actual = {key: getattr(args, key) for key in expected}
    if actual != expected:
        raise BaselineRebuildError(f"baseline parameters drifted: expected {expected!r}, got {actual!r}")
    if not args.run_nonce or len(args.run_nonce) > 128:
        raise BaselineRebuildError("run nonce is invalid")
    if not Path(args.campaign_provenance).is_absolute():
        raise BaselineRebuildError("campaign provenance path is not absolute")
    for role in STRICT_INPUT_ROLES:
        path = Path(getattr(args, role))
        if not path.is_absolute():
            raise BaselineRebuildError(f"strict input path is not absolute for {role}")


def _validate_created_at(value: str) -> None:
    if type(value) is not str or not value.endswith("Z"):
        raise BaselineRebuildError("created_at_utc must be an explicit UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise BaselineRebuildError("created_at_utc must be an explicit UTC timestamp") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise BaselineRebuildError("created_at_utc must be an explicit UTC timestamp")


def _prepare_rebuild_context(
    *,
    output_dir: Path,
    campaign_provenance_path: Path,
    strict_inputs: Mapping[str, Path],
) -> _RebuildContext:
    if set(strict_inputs) != set(STRICT_INPUT_ROLES):
        raise BaselineRebuildError("strict input role set drifted")
    provenance_before = _campaign_provenance(campaign_provenance_path)
    repository_root = Path(str(provenance_before["repository_root"]))
    if Path.cwd() != repository_root:
        raise BaselineRebuildError("working directory is not the campaign repository root")

    supplied_inputs = {
        role: Path(os.path.abspath(strict_inputs[role]))
        for role in STRICT_INPUT_ROLES
    }
    expected_inputs = {
        "candidate_placements": repository_root / "data" / "preprocessed" / "candidate_placements.json",
        "canonical_rules": repository_root / "rules" / "canonical_rules.json",
        "mandatory_instances": repository_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
    }
    if supplied_inputs != expected_inputs:
        raise BaselineRebuildError("strict input paths are not the campaign checkout members")

    input_identities: dict[str, dict[str, object]] = {}
    for role, path in supplied_inputs.items():
        _, identity = _snapshot_regular(path, limit=1 << 30)
        input_identities[role] = identity
    if provenance_before.get("input_identities") != input_identities:
        raise BaselineRebuildError("strict input identities differ from campaign provenance")

    output = _prepare_output(output_dir, campaign_provenance_path)
    provenance_absolute = output / "campaign-provenance.json"
    if _campaign_provenance(provenance_absolute) != provenance_before:
        raise BaselineRebuildError("campaign provenance drifted before baseline rebuild")
    return _RebuildContext(
        output=output,
        campaign_provenance_path=provenance_absolute,
        provenance=provenance_before,
        input_identities=input_identities,
    )


def _validated_computation(
    computation: BaselineComputation,
    expectation: baseline_contract.BaselineExpectation,
) -> tuple[bytes, dict[str, object], dict[str, object]]:
    if not isinstance(computation, BaselineComputation):
        raise BaselineRebuildError("baseline computation has the wrong type")
    if not isinstance(computation.model, cp_model_pb2.CpModelProto):
        raise BaselineRebuildError("baseline computation model is not a CpModelProto")
    model_raw = computation.model.SerializeToString(deterministic=True)
    parsed = cp_model_pb2.CpModelProto()
    consumed = parsed.ParseFromString(model_raw)
    if consumed != len(model_raw) or parsed.SerializeToString(deterministic=True) != model_raw:
        raise BaselineRebuildError("baseline computation model is not canonical")
    without_unknown = cp_model_pb2.CpModelProto()
    without_unknown.CopyFrom(parsed)
    without_unknown.DiscardUnknownFields()
    if without_unknown.SerializeToString(deterministic=True) != model_raw:
        raise BaselineRebuildError("baseline computation model has unknown protobuf fields")

    if (
        type(computation.solution_values) is not tuple
        or any(type(value) is not int for value in computation.solution_values)
        or len(computation.solution_values) != len(parsed.variables)
    ):
        raise BaselineRebuildError("solver response length or values do not match model variables")
    if not isinstance(computation.incumbent, Mapping) or "ghost_pick" not in computation.incumbent:
        raise BaselineRebuildError("baseline computation did not retain a complete incumbent")
    incumbent_json = _jsonable(computation.incumbent)
    if not isinstance(incumbent_json, dict):
        raise BaselineRebuildError("baseline computation incumbent is not a JSON object")
    if type(computation.runner_status) is not str or not computation.runner_status:
        raise BaselineRebuildError("baseline computation runner status is invalid")
    if not isinstance(computation.proof_summary, Mapping):
        raise BaselineRebuildError("baseline computation proof summary is invalid")
    if (
        type(computation.wall_seconds) is not float
        or computation.wall_seconds < 0.0
        or computation.wall_seconds != computation.wall_seconds
        or computation.wall_seconds in (float("inf"), float("-inf"))
    ):
        raise BaselineRebuildError("baseline computation wall time is invalid")

    observed = {
        "model_proto_sha256": baseline_contract.historical_model_text_sha256(parsed),
        "model_variable_count": len(parsed.variables),
        "model_constraint_count": len(parsed.constraints),
        "incumbent_sha256": _digest(incumbent_json),
        "incumbent_assignment_count": len(incumbent_json),
    }
    expected = {
        "model_proto_sha256": expectation.historical_model_text_sha256,
        "model_variable_count": expectation.model_variable_count,
        "model_constraint_count": expectation.model_constraint_count,
        "incumbent_sha256": expectation.incumbent_sha256,
        "incumbent_assignment_count": expectation.incumbent_assignment_count,
    }
    if observed != expected:
        raise BaselineRebuildError(f"historical baseline did not reproduce: {observed!r}")
    return model_raw, incumbent_json, observed


def _publish_rebuild(
    *,
    context: _RebuildContext,
    computation: BaselineComputation,
    expectation: baseline_contract.BaselineExpectation,
    run_nonce: str,
    parameters: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    if type(run_nonce) is not str or not run_nonce or len(run_nonce) > 128:
        raise BaselineRebuildError("run nonce is invalid")
    if not isinstance(parameters, Mapping):
        raise BaselineRebuildError("baseline parameters are invalid")
    _validate_created_at(created_at_utc)
    model_raw, incumbent_json, observed = _validated_computation(computation, expectation)

    targets = {
        "model": context.output / "cut-free-model.bin",
        "incumbent": context.output / "incumbent.json",
        "metadata": context.output / "rebuilt-model-metadata.json",
        "result": context.output / "rebuild-result.json",
    }
    if any(os.path.lexists(path) for path in targets.values()):
        raise BaselineRebuildError("canonical rebuild output already exists")
    if _campaign_provenance(context.campaign_provenance_path) != context.provenance:
        raise BaselineRebuildError("campaign provenance drifted during baseline rebuild")

    model_identity = _write_exclusive(targets["model"], model_raw)
    incumbent_identity = _write_exclusive(
        targets["incumbent"],
        _authority_json(incumbent_json),
    )
    _, builder_identity = _snapshot_regular(Path(__file__), limit=64 << 20)
    metadata = {
        "schema_version": METADATA_SCHEMA,
        "status": "PASS",
        "purpose": REBUILD_PURPOSE,
        "created_at_utc": created_at_utc,
        "campaign_provenance": context.provenance,
        "model_backend": MODEL_BACKEND,
        "model_binary_format": MODEL_BINARY_FORMAT,
        "canonical_binary": True,
        "model_identity": model_identity,
        "historical_model_text_sha256": observed["model_proto_sha256"],
        "model_variable_count": observed["model_variable_count"],
        "model_constraint_count": observed["model_constraint_count"],
        "builder_identity": builder_identity,
        "input_identities": context.input_identities,
        "legacy_control_used_as_build_input": False,
        "global_claim_authorized": False,
        "errors": [],
    }
    metadata_identity = _write_exclusive(
        targets["metadata"],
        _authority_json(metadata),
    )
    record = {
        "schema_version": SCHEMA,
        "created_at_utc": created_at_utc,
        "campaign_provenance": context.provenance,
        "run_nonce": run_nonce,
        "parameters": _jsonable(parameters),
        "runner_status": computation.runner_status,
        "proof_summary": _jsonable(computation.proof_summary),
        "wall_seconds": round(computation.wall_seconds, 6),
        "observed": observed,
        "cut_free_model_identity": model_identity,
        "incumbent_identity": incumbent_identity,
        "rebuilt_metadata_identity": metadata_identity,
        "claim_boundary": {
            "authorizing": False,
            "establishes": ["deterministic baseline bytes reproduced"],
            "does_not_establish": [
                "baseline admission",
                "organic cut credibility",
                "SAT or UNSAT",
                "witness or bound",
            ],
        },
    }
    _write_exclusive(targets["result"], _authority_json(record))
    if _campaign_provenance(context.campaign_provenance_path) != context.provenance:
        raise BaselineRebuildError("campaign provenance drifted after baseline rebuild")
    return record


def _rebuild_paths(
    *,
    output_dir: Path,
    campaign_provenance_path: Path,
    candidate_placements: Path,
    canonical_rules: Path,
    mandatory_instances: Path,
    computation: BaselineComputation,
    expectation: baseline_contract.BaselineExpectation,
    run_nonce: str,
    parameters: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    """Exercise the production provenance checks and canonical writer with supplied solver output."""

    context = _prepare_rebuild_context(
        output_dir=output_dir,
        campaign_provenance_path=campaign_provenance_path,
        strict_inputs={
            "candidate_placements": candidate_placements,
            "canonical_rules": canonical_rules,
            "mandatory_instances": mandatory_instances,
        },
    )
    return _publish_rebuild(
        context=context,
        computation=computation,
        expectation=expectation,
        run_nonce=run_nonce,
        parameters=parameters,
        created_at_utc=created_at_utc,
    )


def _production_parameters(args: argparse.Namespace) -> dict[str, object]:
    return {
        "ghost_rect": [args.ghost_w, args.ghost_h],
        "master_seconds": args.master_seconds,
        "binding_seconds": args.binding_seconds,
        "routing_seconds": args.routing_seconds,
        "max_iterations": args.max_iterations,
        "binding_alt_cap": args.binding_alt_cap,
        "workers": args.workers,
        "seed": args.seed,
        "enabled_cut_families": [],
        "framework_attach_enabled": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _validate_fixed_parameters(args)
    context = _prepare_rebuild_context(
        output_dir=args.output_dir,
        campaign_provenance_path=args.campaign_provenance,
        strict_inputs={
            role: Path(getattr(args, role))
            for role in STRICT_INPUT_ROLES
        },
    )
    repository_root = Path(str(context.provenance["repository_root"]))
    if any(name == "src" or name.startswith("src.") for name in sys.modules):
        raise BaselineRebuildError("repository modules were imported before checkout activation")
    for entry in sys.path:
        candidate = Path(os.path.abspath(entry or Path.cwd()))
        if (
            candidate != repository_root
            and (candidate / "PROJECT_LOCK.md").is_file()
            and (candidate / "src").is_dir()
        ):
            raise BaselineRebuildError("ambient repository import path is forbidden")
    output = context.output
    tmp_dir = output / "tmp"
    os.mkdir(tmp_dir, 0o700)

    os.environ["TMPDIR"] = str(tmp_dir)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
    os.environ["EXACT_CP_SAT_WORKERS"] = "1"
    os.environ["EXACT_MASTER_CP_SAT_WORKERS"] = "1"
    os.environ["EXACT_MASTER_RANDOM_SEED"] = str(args.seed)
    os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = "fixed"
    os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = "3"
    os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = "3"
    os.environ["EXACT_B1_BINDING_ALT_CAP"] = str(args.binding_alt_cap)

    sys.path.insert(0, str(repository_root))
    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    _require_repository_imports(repository_root)
    started = time.perf_counter()
    session = ExactSearchSession.create(
        repository_root,
        solve_mode="certified_exact",
    )
    master = MasterPlacementModel.from_exact_core(
        session.core,
        ghost_rect=(args.ghost_w, args.ghost_h),
    )
    controller = LBBDController(
        master=master,
        cut_manager=CutManager(
            checkpoint_dir=output / "checkpoint",
            solve_mode="certified_exact",
        ),
        project_root=repository_root,
        solve_mode="certified_exact",
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        max_iterations=args.max_iterations,
        artifact_hashes=session.artifact_hashes,
        session=session,
        enabled_cut_families=(),
    )
    if os.environ.get("EXACT_CUT_FRAMEWORK_ATTACH") is not None:
        raise BaselineRebuildError("attach environment leaked into baseline build")

    status, returned_solution = controller.run_with_status()
    incumbent: Mapping[str, Any]
    if returned_solution:
        incumbent = returned_solution
    else:
        incumbent = master.extract_solution()
    if not incumbent or "ghost_pick" not in incumbent or master._solver is None:
        raise BaselineRebuildError("baseline run did not retain a complete incumbent")

    model = cp_model_pb2.CpModelProto()
    model.CopyFrom(master.model.Proto())
    computation = BaselineComputation(
        model=model,
        incumbent=incumbent,
        solution_values=tuple(int(value) for value in master._solver.ResponseProto().solution),
        runner_status=str(status),
        proof_summary=controller.last_proof_summary or {},
        wall_seconds=time.perf_counter() - started,
    )
    _publish_rebuild(
        context=context,
        computation=computation,
        expectation=baseline_contract.PRODUCTION_EXPECTATION,
        run_nonce=args.run_nonce,
        parameters=_production_parameters(args),
        created_at_utc=_utc_now(),
    )
    print(json.dumps({"status": "REBUILT_PENDING_INDEPENDENT_REPLAY"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
