#!/usr/bin/env python3
"""Rebuild the historical AB16 baseline from package-pinned strict inputs.

This is a formal-stage payload.  Importing it is side-effect free; the CLI is
only run after the separately authorized Gate B selection.  Its output is
evidence for the independent baseline admission tool, never an admission by
itself.  The repository root and every data input are explicit arguments:
later authority replay must join their full byte identities to the selected
campaign package rather than trusting this payload's source-file location.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from typing import Any

from ortools.sat import cp_model_pb2


EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
EXPECTED_REPOSITORY_ROOT = Path("/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723")
EXPECTED_MODEL_PROTO_SHA256 = "3a9be08dcca722fc4bf7dfc9bcf7be4a1213af14ded9ec7b769909a029904d32"
EXPECTED_INCUMBENT_SHA256 = "13f88404d7f5e4fde86929f82997a2b9850fa1cc4791d710c0363ed3e072f223"
EXPECTED_VARIABLE_COUNT = 37_760
EXPECTED_CONSTRAINT_COUNT = 95_136
SCHEMA = "noncert-cuts-ab16-baseline-rebuild-v1"
METADATA_SCHEMA = "noncert-cuts-ab16-rebuilt-model-metadata-v1"
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


def _prepare_output(path: Path) -> Path:
    absolute = _reject_symlink_chain(
        path,
        leaf_may_not_exist=True,
    )
    if os.path.lexists(absolute):
        raise BaselineRebuildError(f"output already exists: {absolute}")
    parent = absolute.parent
    if not parent.is_dir():
        raise BaselineRebuildError("output parent must be a non-symlink directory")
    os.mkdir(absolute, 0o700)
    return absolute


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--repository-root", required=True, type=Path)
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
    repository_root = Path(os.path.abspath(args.repository_root))
    if repository_root != EXPECTED_REPOSITORY_ROOT:
        raise BaselineRebuildError("repository root differs from the campaign's fixed worktree")
    if not repository_root.is_dir() or repository_root.is_symlink():
        raise BaselineRebuildError("repository root must be an existing non-symlink directory")
    for role in STRICT_INPUT_ROLES:
        path = Path(getattr(args, role))
        if not path.is_absolute():
            raise BaselineRebuildError(f"strict input path is not absolute for {role}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _validate_fixed_parameters(args)
    output = _prepare_output(args.output_dir)
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

    repository_root = Path(os.path.abspath(args.repository_root))
    strict_inputs = {role: Path(os.path.abspath(getattr(args, role))) for role in STRICT_INPUT_ROLES}
    input_identities: dict[str, dict[str, object]] = {}
    for role, path in strict_inputs.items():
        _, identity = _snapshot_regular(path, limit=1 << 30)
        input_identities[role] = identity

    sys.path.insert(0, str(repository_root))
    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

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

    solution_values = [int(value) for value in master._solver.ResponseProto().solution]
    if len(solution_values) != len(master.model.Proto().variables):
        raise BaselineRebuildError("solver response length does not match model variables")

    incumbent_json = _jsonable(incumbent)
    model_text = str(master.model.Proto()).encode("utf-8")
    observed = {
        "model_proto_sha256": hashlib.sha256(model_text).hexdigest(),
        "model_variable_count": len(master.model.Proto().variables),
        "model_constraint_count": len(master.model.Proto().constraints),
        "incumbent_sha256": _digest(incumbent_json),
    }
    expected = {
        "model_proto_sha256": EXPECTED_MODEL_PROTO_SHA256,
        "model_variable_count": EXPECTED_VARIABLE_COUNT,
        "model_constraint_count": EXPECTED_CONSTRAINT_COUNT,
        "incumbent_sha256": EXPECTED_INCUMBENT_SHA256,
    }
    if observed != expected:
        raise BaselineRebuildError(f"historical baseline did not reproduce: {observed!r}")

    model_path = output / "cut-free-model.bin"
    if os.path.lexists(model_path) or not master.model.export_to_file(str(model_path)):
        raise BaselineRebuildError("official binary model export failed")
    model_raw, model_identity = _snapshot_regular(model_path, limit=1 << 30)
    parsed = cp_model_pb2.CpModelProto()
    consumed = parsed.ParseFromString(model_raw)
    if consumed != len(model_raw) or parsed.SerializeToString(deterministic=True) != model_raw:
        raise BaselineRebuildError("binary model export is not canonical")
    model_identity = {
        "path": str(model_path.resolve(strict=True)),
        "size_bytes": len(model_raw),
        "sha256": hashlib.sha256(model_raw).hexdigest(),
    }
    incumbent_identity = _write_exclusive(
        output / "incumbent.json",
        _authority_json(incumbent_json),
    )
    _, builder_identity = _snapshot_regular(Path(__file__), limit=64 << 20)
    metadata = {
        "schema_version": METADATA_SCHEMA,
        "status": "PASS",
        "purpose": REBUILD_PURPOSE,
        "created_at_utc": _utc_now(),
        "repository_head": EXPECTED_HEAD,
        "model_backend": MODEL_BACKEND,
        "model_binary_format": MODEL_BINARY_FORMAT,
        "canonical_binary": True,
        "model_identity": model_identity,
        "historical_model_text_sha256": observed["model_proto_sha256"],
        "model_variable_count": observed["model_variable_count"],
        "model_constraint_count": observed["model_constraint_count"],
        "builder_identity": builder_identity,
        "input_identities": input_identities,
        "legacy_control_used_as_build_input": False,
        "global_claim_authorized": False,
        "errors": [],
    }
    metadata_identity = _write_exclusive(
        output / "rebuilt-model-metadata.json",
        _authority_json(metadata),
    )
    record = {
        "schema_version": SCHEMA,
        "created_at_utc": _utc_now(),
        "repository_head": EXPECTED_HEAD,
        "run_nonce": args.run_nonce,
        "parameters": {
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
        },
        "runner_status": str(status),
        "proof_summary": _jsonable(controller.last_proof_summary or {}),
        "wall_seconds": round(time.perf_counter() - started, 6),
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
    _write_exclusive(output / "rebuild-result.json", _authority_json(record))
    print(json.dumps({"status": "REBUILT_PENDING_INDEPENDENT_REPLAY"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
