"""Run corrected short witness constructors as a reconstructed Batch 4 baseline.

This wrapper does not edit or claim to replay the 2026-07-17 historical scripts.
Each arm runs in a fresh Python process.  Immediately before ``runpy`` loads the
selected historical script, that process replaces the imported construction-side
``_DIR_DELTA`` mapping with zero deltas.  Consequently, stored port ``(x, y)``
coordinates are used as front cells, while the current production
``port_front_status`` implementation remains the audit implementation.

Example::

    python docs/research/front_offset_incident_20260718/batch4_harness/\
run_reconstructed_witness.py \
        --arm greedy \
        --output-dir .artifacts/batch4_20260718/witness/greedy_seed0

The output directory must not already exist.  Binding is skipped unless
``--with-binding`` is supplied explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[4]
_HISTORICAL_ROOT = PROJECT_ROOT / "docs" / "research" / "witness_constructor_20260717"
_IDENTITY_DELTA = {"N": (0, 0), "S": (0, 0), "E": (0, 0), "W": (0, 0)}
_RUN_RECORD_SCHEMA = "batch4.reconstructed_witness_run_record.v1"
_RUN_RECORD_SOURCE = "reconstructed_new_baseline"


@dataclass(frozen=True)
class ArmSpec:
    script_name: str
    ghost_x: int
    ghost_y: int
    ghost_w: int = 6
    ghost_h: int = 7
    supports_seed: bool = False
    # cpsat 臂：ghost 位置是模型自由变量，脚本不接受 --ghost-x/-y；
    # extra_argv 携带该臂的固定历史配方（如 --maximize）。
    takes_ghost_anchor: bool = True
    extra_argv: tuple[str, ...] = ()


ARM_SPECS: Mapping[str, ArmSpec] = {
    "greedy": ArmSpec(
        script_name="witness_greedy_v0.py",
        ghost_x=8,
        ghost_y=8,
        supports_seed=True,
    ),
    "comb": ArmSpec(
        script_name="witness_comb_v1.py",
        ghost_x=1,
        ghost_y=1,
    ),
    "skyline": ArmSpec(
        script_name="witness_skyline_v1.py",
        ghost_x=62,
        ghost_y=2,
        supports_seed=True,
    ),
    # WIT-04 maximize 臂（历史 cpsat v5 配方=TB-only+maximize；构造日志
    # 01_construction_log §2 收官行）。ghost_x/y 仅占位（不入 argv）。
    "cpsat_max": ArmSpec(
        script_name="witness_cpsat_v1.py",
        ghost_x=-1,
        ghost_y=-1,
        takes_ghost_anchor=False,
        extra_argv=("--maximize",),
    ),
}

_INPUT_PATHS = (
    Path("data/preprocessed/candidate_placements.json"),
    Path("data/preprocessed/mandatory_exact_instances.json"),
    Path("data/preprocessed/generic_io_requirements.json"),
    Path("rules/canonical_rules.json"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_record(path: Path, *, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        display_path = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        display_path = str(resolved)
    return {
        "path": display_path,
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _records_by_path(paths: Sequence[Path], *, root: Path = PROJECT_ROOT) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in paths:
        record = _path_record(path, root=root)
        records[str(record["path"])] = {
            "sha256": record["sha256"],
            "size_bytes": record["size_bytes"],
        }
    return records


def _git_revision(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        "commit": commit,
        "dirty": bool(status.strip()),
        "dirty_snapshot_taken_before_output_creation": True,
    }


def _resolved_arm_values(
    *,
    arm: str,
    ghost_x: int | None,
    ghost_y: int | None,
    ghost_w: int | None,
    ghost_h: int | None,
    seed: int | None,
) -> dict[str, int | None]:
    spec = ARM_SPECS[arm]
    if seed is not None and not spec.supports_seed:
        raise ValueError(f"arm {arm!r} does not accept --seed")
    return {
        "ghost_x": spec.ghost_x if ghost_x is None else ghost_x,
        "ghost_y": spec.ghost_y if ghost_y is None else ghost_y,
        "ghost_w": spec.ghost_w if ghost_w is None else ghost_w,
        "ghost_h": spec.ghost_h if ghost_h is None else ghost_h,
        "seed": (0 if seed is None else seed) if spec.supports_seed else None,
    }


def _build_historical_argv(
    *,
    arm: str,
    result_path: Path,
    ghost_x: int | None = None,
    ghost_y: int | None = None,
    ghost_w: int | None = None,
    ghost_h: int | None = None,
    seed: int | None = None,
    with_binding: bool = False,
) -> tuple[list[str], int | None]:
    """Map wrapper options to only the CLI options supported by one old arm."""

    values = _resolved_arm_values(
        arm=arm,
        ghost_x=ghost_x,
        ghost_y=ghost_y,
        ghost_w=ghost_w,
        ghost_h=ghost_h,
        seed=seed,
    )
    spec = ARM_SPECS[arm]
    historical_argv = []
    if spec.takes_ghost_anchor:
        historical_argv.extend(
            ("--ghost-x", str(values["ghost_x"]), "--ghost-y", str(values["ghost_y"]))
        )
    historical_argv.extend(
        ("--ghost-w", str(values["ghost_w"]), "--ghost-h", str(values["ghost_h"]))
    )
    historical_argv.extend(spec.extra_argv)
    if spec.supports_seed:
        historical_argv.extend(("--seed", str(values["seed"])))
    if not with_binding:
        historical_argv.append("--skip-binding")
    historical_argv.extend(("--out", str(result_path)))
    return historical_argv, values["seed"]


def _validate_new_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(
            f"refusing to reuse output directory (remove or choose a new run name): {output_dir}"
        )


def _output_record(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {"filename": path.name, "exists": path.is_file()}
    if path.is_file():
        record.update({"sha256": _sha256(path), "size_bytes": path.stat().st_size})
    else:
        record.update({"sha256": None, "size_bytes": None})
    return record


def _build_run_record(
    *,
    arm: str,
    revision: Mapping[str, Any],
    command: Sequence[str],
    historical_argv: Sequence[str],
    source_sha256s: Mapping[str, Mapping[str, Any]],
    input_sha256s: Mapping[str, Mapping[str, Any]],
    seed: int | None,
    hash_seed: int,
    with_binding: bool,
    wall_seconds: float,
    exit_code: int | None,
    outputs: Mapping[str, Mapping[str, Any]],
    launch_error: str | None = None,
) -> dict[str, Any]:
    execution: dict[str, Any] = {
        "command": list(command),
        "cwd": str(PROJECT_ROOT),
        "exit_code": exit_code,
        "historical_argv": list(historical_argv),
        "stderr_filename": "stderr.txt",
        "stdout_filename": "stdout.txt",
        "wall_seconds": round(float(wall_seconds), 6),
    }
    if launch_error is not None:
        execution["launch_error"] = launch_error
    return {
        "arm": arm,
        "binding_enabled": bool(with_binding),
        "execution": execution,
        "front_semantics": {
            "construction": "stored_port_coordinate_identity_via_runtime_zero_delta",
            "audit": "current_src.models.routing_binding_context.port_front_status",
        },
        "hash_seed": int(hash_seed),
        "input_sha256s": dict(input_sha256s),
        "outputs": dict(outputs),
        "revision": dict(revision),
        "schema": _RUN_RECORD_SCHEMA,
        "seed": seed,
        "source": _RUN_RECORD_SOURCE,
        "source_sha256s": dict(source_sha256s),
    }


def _write_canonical_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _install_identity_delta() -> None:
    # Import before runpy: the historical ``from ... import _DIR_DELTA`` then
    # captures this process-local mapping.  The production source is untouched.
    import src.models.routing_binding_context as routing_binding_context

    routing_binding_context._DIR_DELTA = dict(_IDENTITY_DELTA)


def _child_main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--hash-seed", type=int, required=True)
    parser.add_argument("historical_argv", nargs=argparse.REMAINDER)
    args = parser.parse_args(list(argv))

    expected_hash_seed = str(args.hash_seed)
    if os.environ.get("PYTHONHASHSEED") != expected_hash_seed:
        raise RuntimeError("child PYTHONHASHSEED does not match the recorded value")

    script = args.script.resolve()
    allowed_scripts = {
        (_HISTORICAL_ROOT / spec.script_name).resolve() for spec in ARM_SPECS.values()
    }
    if script not in allowed_scripts:
        raise ValueError(f"unsupported historical witness script: {script}")

    historical_argv = list(args.historical_argv)
    if historical_argv[:1] == ["--"]:
        historical_argv.pop(0)

    sys.path.insert(0, str(PROJECT_ROOT))
    _install_identity_delta()
    sys.argv = [str(script), *historical_argv]
    runpy.run_path(str(script), run_name="__main__")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=tuple(ARM_SPECS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ghost-x", type=int)
    parser.add_argument("--ghost-y", type=int)
    parser.add_argument("--ghost-w", type=int)
    parser.add_argument("--ghost-h", type=int)
    parser.add_argument("--seed", type=int, help="greedy/skyline only; their default is 0")
    parser.add_argument(
        "--hash-seed",
        type=int,
        default=0,
        help="PYTHONHASHSEED for the fresh child process (default: 0)",
    )
    parser.add_argument(
        "--with-binding",
        action="store_true",
        help="explicitly opt in to the historical arm's binding build",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        help="cpsat_max only: solver wall budget seconds (arm script default 120)",
    )
    parser.add_argument(
        "--hint-from",
        type=Path,
        help="cpsat_max only: warm-hint result.json from another arm run",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not 0 <= args.hash_seed <= 4_294_967_295:
        parser.error("--hash-seed must be between 0 and 4294967295")

    output_dir = args.output_dir.expanduser().resolve()
    try:
        _validate_new_output_dir(output_dir)
        if (args.time_limit is not None or args.hint_from is not None) and (
            args.arm != "cpsat_max"
        ):
            raise ValueError("--time-limit/--hint-from are cpsat_max-only options")
        historical_argv, effective_seed = _build_historical_argv(
            arm=args.arm,
            result_path=output_dir / "result.json",
            ghost_x=args.ghost_x,
            ghost_y=args.ghost_y,
            ghost_w=args.ghost_w,
            ghost_h=args.ghost_h,
            seed=args.seed,
            with_binding=args.with_binding,
        )
        if args.time_limit is not None:
            historical_argv[-2:-2] = ["--time-limit", str(args.time_limit)]
        if args.hint_from is not None:
            hint_path = args.hint_from.expanduser().resolve()
            if not hint_path.is_file():
                raise ValueError(f"--hint-from not found: {hint_path}")
            historical_argv[-2:-2] = ["--hint-from", str(hint_path)]
    except (FileExistsError, KeyError, ValueError) as exc:
        parser.error(str(exc))

    spec = ARM_SPECS[args.arm]
    historical_script = (_HISTORICAL_ROOT / spec.script_name).resolve()
    runner_script = Path(__file__).resolve()
    routing_source = PROJECT_ROOT / "src/models/routing_binding_context.py"
    source_sha256s = _records_by_path(
        (runner_script, historical_script, routing_source)
    )
    input_sha256s = _records_by_path(tuple(PROJECT_ROOT / path for path in _INPUT_PATHS))
    revision = _git_revision()

    # Keep the invoking virtual-environment entry point.  Resolving this symlink
    # can bypass its ``pyvenv.cfg`` and silently select a different environment.
    python_executable = str(Path(sys.executable).absolute())
    command = [
        python_executable,
        str(runner_script),
        "_child",
        "--script",
        str(historical_script),
        "--hash-seed",
        str(args.hash_seed),
        "--",
        *historical_argv,
    ]

    output_dir.mkdir(parents=True, exist_ok=False)
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    result_path = output_dir / "result.json"
    run_record_path = output_dir / "run_record.json"

    child_env = os.environ.copy()
    child_env["PYTHONHASHSEED"] = str(args.hash_seed)
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.perf_counter()
    exit_code: int | None = None
    launch_error: str | None = None
    try:
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                env=child_env,
                stdout=stdout_handle,
                stderr=stderr_handle,
                check=False,
            )
        exit_code = completed.returncode
    except OSError as exc:
        launch_error = f"{type(exc).__name__}: {exc}"
    wall_seconds = time.perf_counter() - started

    outputs = {
        "result": _output_record(result_path),
        "stderr": _output_record(stderr_path),
        "stdout": _output_record(stdout_path),
    }
    run_record = _build_run_record(
        arm=args.arm,
        revision=revision,
        command=command,
        historical_argv=historical_argv,
        source_sha256s=source_sha256s,
        input_sha256s=input_sha256s,
        seed=effective_seed,
        hash_seed=args.hash_seed,
        with_binding=args.with_binding,
        wall_seconds=wall_seconds,
        exit_code=exit_code,
        outputs=outputs,
        launch_error=launch_error,
    )
    _write_canonical_json(run_record_path, run_record)

    if launch_error is not None:
        print(f"child launch failed; see {run_record_path}", file=sys.stderr)
        return 1
    if exit_code != 0:
        print(f"witness arm exited {exit_code}; see {run_record_path}", file=sys.stderr)
        return int(exit_code or 1)
    if not result_path.is_file():
        print(f"witness arm produced no result.json; see {run_record_path}", file=sys.stderr)
        return 3
    print(run_record_path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "_child":
        raise SystemExit(_child_main(sys.argv[2:]))
    raise SystemExit(main())
