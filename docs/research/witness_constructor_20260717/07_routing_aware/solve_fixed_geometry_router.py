"""Thin process boundary for one supervised fixed-geometry routing attempt.

The outer launcher owns locking, run-directory creation, and the systemd
cgroup.  This module only binds an immutable geometry snapshot to the exact
worker entry, writes one new result file, and exits normally for either a
feasible result or a structured rejection.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import importlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


_BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_PROJECT_ROOT))

_MODULE_PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
fixed_geometry_router = importlib.import_module(f"{_MODULE_PREFIX}.fixed_geometry_router")

PROJECT_ROOT = _BOOTSTRAP_PROJECT_ROOT
WORKER_COUNT_ENV = "EXACT_ROUTING_CP_SAT_WORKERS"

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SAFE_UNIT_RE = re.compile(r"[A-Za-z0-9_.@:-]+\.service")


class FixedRouterCliError(RuntimeError):
    """The process-boundary contract could not produce a trustworthy file."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _resolve_project_root(project_root: Path) -> Path:
    candidate = Path(project_root)
    if not candidate.is_absolute():
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", str(candidate))
    try:
        root = candidate.resolve(strict=True)
    except OSError as exc:
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", str(exc)) from exc
    marker = root / ".git"
    if (
        not root.is_dir()
        or marker.is_symlink()
        or not (marker.is_dir() or marker.is_file())
    ):
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", f"not a Git working tree: {root}")

    git_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "rev-parse",
                "--is-inside-work-tree",
                "--show-toplevel",
                "--absolute-git-dir",
            ],
            check=True,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=5.0,
            env=git_env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", f"Git probe failed for {root}: {exc}") from exc

    fields = completed.stdout.splitlines()
    if len(fields) != 3 or fields[0] != "true":
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", f"invalid Git probe for {root}")
    try:
        reported_root = Path(fields[1]).resolve(strict=True)
        reported_git_dir = Path(fields[2]).resolve(strict=True)
    except OSError as exc:
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", f"invalid Git paths for {root}: {exc}") from exc
    if reported_root != root or not reported_git_dir.is_dir():
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", f"Git top-level mismatch for {root}")

    try:
        if marker.is_dir():
            marker_git_dir = marker.resolve(strict=True)
        else:
            raw_marker = marker.read_bytes()
            if not raw_marker.endswith(b"\n") or raw_marker.count(b"\n") != 1 or len(raw_marker) > 4096:
                raise ValueError("malformed linked-worktree marker")
            marker_line = raw_marker[:-1].decode("utf-8", errors="strict")
            if not marker_line.startswith("gitdir: ") or not marker_line[8:]:
                raise ValueError("malformed linked-worktree marker")
            marker_target = Path(marker_line[8:])
            if not marker_target.is_absolute():
                marker_target = marker.parent / marker_target
            marker_git_dir = marker_target.resolve(strict=True)

            backlink = marker_git_dir / "gitdir"
            if backlink.is_symlink() or not backlink.is_file():
                raise ValueError("linked-worktree backlink is missing")
            raw_backlink = backlink.read_bytes()
            if not raw_backlink.endswith(b"\n") or raw_backlink.count(b"\n") != 1 or len(raw_backlink) > 4096:
                raise ValueError("malformed linked-worktree backlink")
            backlink_target = Path(raw_backlink[:-1].decode("utf-8", errors="strict"))
            if not backlink_target.is_absolute():
                backlink_target = backlink.parent / backlink_target
            if backlink_target.resolve(strict=True) != marker.resolve(strict=True):
                raise ValueError("linked-worktree backlink mismatch")

            commondir = marker_git_dir / "commondir"
            if commondir.is_symlink() or not commondir.is_file():
                raise ValueError("linked-worktree commondir is missing")
            raw_commondir = commondir.read_bytes()
            if not raw_commondir.endswith(b"\n") or raw_commondir.count(b"\n") != 1 or len(raw_commondir) > 4096:
                raise ValueError("malformed linked-worktree commondir")
            common_target = Path(raw_commondir[:-1].decode("utf-8", errors="strict"))
            if not common_target.is_absolute():
                common_target = commondir.parent / common_target
            common_git_dir = common_target.resolve(strict=True)
            if (
                not common_git_dir.is_dir()
                or marker_git_dir.parent.resolve(strict=True)
                != (common_git_dir / "worktrees").resolve(strict=True)
            ):
                raise ValueError("linked-worktree admin directory mismatch")
    except (OSError, UnicodeError, ValueError) as exc:
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", f"invalid .git marker for {root}: {exc}") from exc
    if marker_git_dir != reported_git_dir:
        raise FixedRouterCliError("PROJECT_ROOT_INVALID", f"Git directory mismatch for {root}")
    return root


def _strict_json_copy(value: object) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FixedRouterCliError("WORKER_RESULT_NOT_JSON", str(exc)) from exc


def _normalize_worker_result(value: object) -> dict[str, Any]:
    """Apply the minimum process-boundary schema before exclusive writing."""

    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise FixedRouterCliError("WORKER_RESULT_SHAPE", "worker result must be an object")
    result = _strict_json_copy(value)
    if result.get("schema_version") != fixed_geometry_router.OUTPUT_SCHEMA_VERSION:
        raise FixedRouterCliError("WORKER_RESULT_SCHEMA", "unexpected result schema version")
    status = result.get("status")
    if status not in {"FEASIBLE", "REJECTED"}:
        raise FixedRouterCliError("WORKER_RESULT_STATUS", repr(status))
    classification = result.get("classification")
    if type(classification) is not str or not classification:
        raise FixedRouterCliError("WORKER_RESULT_CLASSIFICATION", repr(classification))
    components = result.get("route_components")
    if isinstance(components, (str, bytes, bytearray)) or not isinstance(components, Sequence):
        raise FixedRouterCliError("WORKER_RESULT_ROUTES", "route_components must be an array")
    if status == "REJECTED" and components:
        raise FixedRouterCliError(
            "WORKER_REJECTION_CARRIES_ROUTES",
            "a rejected result must not retain route components",
        )
    if not isinstance(result.get("telemetry"), Mapping):
        raise FixedRouterCliError("WORKER_RESULT_TELEMETRY", "telemetry must be an object")
    return result


def _rejected_result(exc: Exception, *, geometry_sha256: str) -> dict[str, Any]:
    telemetry: dict[str, Any] = {}
    if _SHA256_RE.fullmatch(geometry_sha256) is not None:
        telemetry["input_snapshot"] = {
            "geometry_sha256": geometry_sha256,
            "worker_cli_fail_closed": True,
        }
    result: dict[str, Any] = {
        "schema_version": fixed_geometry_router.OUTPUT_SCHEMA_VERSION,
        "status": "REJECTED",
        "classification": "FAIL_CLOSED_WORKER_CLI_EXCEPTION",
        "phase": "worker_cli",
        "message": type(exc).__name__,
        "route_components": [],
        "telemetry": telemetry,
    }
    code = getattr(exc, "code", None)
    if type(code) is str and code:
        result["error_code"] = code
    return result


def _validate_controls(
    *,
    project_root: Path,
    geometry_path: Path,
    out_path: Path,
    expected_geometry_sha256: str,
    expected_unit_name: str,
    time_limit_seconds: float,
    workers: int,
) -> Path:
    root = _resolve_project_root(project_root)
    if not geometry_path.is_absolute():
        raise FixedRouterCliError("GEOMETRY_PATH_INVALID", "geometry path must be absolute")
    if _SHA256_RE.fullmatch(expected_geometry_sha256) is None:
        raise FixedRouterCliError("GEOMETRY_HASH_INVALID", repr(expected_geometry_sha256))
    if _SAFE_UNIT_RE.fullmatch(expected_unit_name) is None:
        raise FixedRouterCliError("UNIT_NAME_INVALID", repr(expected_unit_name))
    if (
        isinstance(time_limit_seconds, bool)
        or not isinstance(time_limit_seconds, (int, float))
        or not math.isfinite(float(time_limit_seconds))
        or float(time_limit_seconds) <= 0.0
    ):
        raise FixedRouterCliError("TIME_LIMIT_INVALID", repr(time_limit_seconds))
    if type(workers) is not int or not 1 <= workers <= 64:
        raise FixedRouterCliError("WORKER_COUNT_INVALID", repr(workers))
    if not out_path.is_absolute() or not out_path.parent.is_dir() or out_path.exists():
        raise FixedRouterCliError(
            "RESULT_PATH_INVALID",
            "result path must be a new absolute file in an existing attempt directory",
        )
    return root


def run_worker(
    *,
    project_root: Path,
    geometry_path: Path,
    out_path: Path,
    expected_geometry_sha256: str,
    expected_unit_name: str,
    time_limit_seconds: float,
    workers: int,
) -> dict[str, Any]:
    """Run once and exclusively persist either the result or a fail-closed rejection."""

    geometry = Path(geometry_path)
    target = Path(out_path)
    root = _validate_controls(
        project_root=Path(project_root),
        geometry_path=geometry,
        out_path=target,
        expected_geometry_sha256=expected_geometry_sha256,
        expected_unit_name=expected_unit_name,
        time_limit_seconds=time_limit_seconds,
        workers=workers,
    )

    previous_worker_count = os.environ.get(WORKER_COUNT_ENV)
    try:
        os.environ[WORKER_COUNT_ENV] = str(workers)
        try:
            raw_result = fixed_geometry_router.run_supervised_fixed_geometry_router(
                geometry,
                expected_geometry_sha256=expected_geometry_sha256,
                project_root=root,
                config=fixed_geometry_router.WorkerConfig(
                    time_limit_seconds=float(time_limit_seconds),
                    minimum_poles=9,
                    required_grid=(70, 70),
                    require_cgroup=True,
                    expected_unit_name=expected_unit_name,
                ),
            )
            result = _normalize_worker_result(raw_result)
        except Exception as exc:  # noqa: BLE001 - process boundary must emit a rejection
            result = _rejected_result(exc, geometry_sha256=expected_geometry_sha256)
    finally:
        if previous_worker_count is None:
            os.environ.pop(WORKER_COUNT_ENV, None)
        else:
            os.environ[WORKER_COUNT_ENV] = previous_worker_count

    fixed_geometry_router.write_result_exclusive(target, result)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--geometry-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-unit", required=True)
    parser.add_argument("--time-limit-seconds", type=float, required=True)
    parser.add_argument("--workers", type=int, default=8)
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = run_worker(
            project_root=args.project_root,
            geometry_path=args.geometry,
            out_path=args.out,
            expected_geometry_sha256=args.geometry_sha256,
            expected_unit_name=args.expected_unit,
            time_limit_seconds=args.time_limit_seconds,
            workers=args.workers,
        )
    except (FixedRouterCliError, fixed_geometry_router.FixedGeometryRouterError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "out": str(args.out),
                "status": result["status"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
