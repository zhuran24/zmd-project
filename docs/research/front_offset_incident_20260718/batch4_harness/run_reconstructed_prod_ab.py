"""Reproducible current-production RAB/FCL A/B launcher for Batch 4.

This launcher does not replay the invalid historical front geometry.  It runs
the current production code under the semantic label reconstructed_new_baseline
and isolates each arm in a fresh child process with a closed, recorded
environment.  Its scope is one fixed ghost rectangle through the current inner
LBBD chain; it is not the ``main.py`` outer-search/campaign entry point.

Public combinations:

* --experiment rab --rab on|off, with no --lift;
* --experiment fcl --rab on --lift on|off.

The output directory must not exist.  The launcher creates result.json,
stdout.txt, stderr.txt, and run_record.json.  FCL arms additionally capture
each extracted layout under layouts/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import resource
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCHEMA_VERSION = "batch4_reconstructed_prod_ab_v1"
SEMANTIC_LABEL = "reconstructed_new_baseline"
MASTER_BRANCHING = "fixed"
MASTER_PROBING_LEVEL = 3
MASTER_SYMMETRY_LEVEL = 3
DEFAULT_RANDOM_SEED = 1
DEFAULT_WORKERS = 1
DEFAULT_BINDING_ALT_CAP = 200
DEFAULT_MAX_ITERATIONS = 6
DEFAULT_MASTER_SECONDS = 900.0
DEFAULT_BINDING_SECONDS = 600.0
DEFAULT_ROUTING_SECONDS = 600.0
DEFAULT_FLOW_SECONDS = 60.0
EXECUTION_SCOPE = "fixed_ghost_current_production_inner_lbbd"
EXECUTION_LIMITATIONS = (
    "Does not invoke main.py or run_outer_search; campaign rectangle search, "
    "production readiness gating, and freeze monitoring are outside this harness.",
    "Uses a fresh temporary CutManager checkpoint and does not replay historical "
    "campaign cuts.",
)
RAB_CUT_COUNTER_ATTRIBUTES = (
    "_fine_grained_exact_safe_cut_count",
    "_binding_domain_empty_cut_count",
)
FCL_RAW_SCOPE_ATTRIBUTE = "_front_clear_raw_empty_by_iteration"

SAFE_INHERITED_ENV_NAMES = frozenset(
    {
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LD_LIBRARY_PATH",
        "PATH",
        "TMPDIR",
        "TZ",
        "XDG_CACHE_HOME",
    }
)

SOURCE_RELATIVE_PATHS = (
    "docs/research/front_offset_incident_20260718/batch4_harness/"
    "run_reconstructed_prod_ab.py",
    "src/models/binding_subproblem.py",
    "src/models/exact_coordinate_master.py",
    "src/models/master_model.py",
    "src/models/port_binding.py",
    "src/models/routing_binding_context.py",
    "src/search/benders_loop.py",
)


class ReconstructedProdABError(ValueError):
    """Raised when a launcher invariant or pinned input check fails."""


@dataclass(frozen=True)
class RunConfig:
    experiment: str
    rab: str
    lift: str | None
    ghost_w: int
    ghost_h: int
    master_seconds: float
    binding_seconds: float
    routing_seconds: float
    flow_seconds: float
    max_iterations: int
    workers: int
    binding_alt_cap: int
    random_seed: int
    run_tag: str
    output_dir: Path
    hint: Path | None = None
    hint_sha256: str | None = None


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _layout_snapshot_payload(
    solution: Any,
) -> tuple[bytes, str]:
    encoded = json.dumps(
        solution,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return encoded, _sha256(encoded)


def _fcl_raw_scope_acceptance(
    lift: str,
    raw_iterations: Sequence[Mapping[str, Any]],
) -> str:
    if lift == "off":
        return "NOT_APPLICABLE_OFF_ARM"
    if lift != "on":
        raise ReconstructedProdABError("FCL acceptance requires lift on or off")
    if not raw_iterations:
        return "NOT_EVALUATED"
    return (
        "PASS"
        if all(
            int(item.get("raw_lift_scope", -1)) == 0
            for item in raw_iterations
        )
        else "FAIL"
    )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _json_text(payload)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp.",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _path_record(path: Path) -> dict[str, str | None]:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        relative = None
    return {
        "absolute_path": str(resolved),
        "project_relative_path": relative,
    }


def _file_record(path: Path) -> dict[str, str | None]:
    record = _path_record(path)
    record["sha256"] = _sha256(path.read_bytes())
    return record


def _hash_named_files(
    paths: Sequence[Path],
) -> dict[str, dict[str, str | None]]:
    records: dict[str, dict[str, str | None]] = {}
    for path in sorted(paths, key=lambda item: str(item.resolve())):
        resolved = path.resolve(strict=True)
        try:
            name = resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
        except ValueError:
            name = str(resolved)
        records[name] = _file_record(resolved)
    return records


def _source_records() -> dict[str, dict[str, str | None]]:
    return _hash_named_files(
        [PROJECT_ROOT / relative for relative in SOURCE_RELATIVE_PATHS]
    )


def _input_records() -> dict[str, dict[str, str | None]]:
    paths = list((PROJECT_ROOT / "data/preprocessed").glob("*.json"))
    paths.extend(
        [
            PROJECT_ROOT / "data/preprocessed/candidate_placements.json",
            PROJECT_ROOT / "rules/canonical_rules.json",
            PROJECT_ROOT / "rules/canonical_rules.schema.json",
            PROJECT_ROOT / "rules/preprocess_plan.json",
            PROJECT_ROOT / "rules/preprocess_plan.schema.json",
        ]
    )
    unique = {path.resolve(strict=True): path for path in paths}
    return _hash_named_files(list(unique))


def _git_command(args: Sequence[str], *, binary: bool = False) -> str | bytes:
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="strict").rstrip("\n")


def _git_snapshot() -> dict[str, Any]:
    status = str(
        _git_command(
            ["status", "--porcelain=v1", "--untracked-files=normal"],
        )
    )
    tracked_diff = _git_command(
        ["diff", "--binary", "--no-ext-diff", "HEAD", "--"],
        binary=True,
    )
    assert isinstance(tracked_diff, bytes)
    return {
        "branch": str(_git_command(["branch", "--show-current"])),
        "dirty": bool(status),
        "head": str(_git_command(["rev-parse", "HEAD"])),
        "status_porcelain_v1": status.splitlines(),
        "tracked_diff_sha256": _sha256(tracked_diff),
    }


def _read_text_if_present(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def _python_executable() -> str:
    """Preserve the invoked venv entrypoint instead of resolving through it."""

    return str(Path(sys.executable).absolute())


def _system_info() -> dict[str, Any]:
    uname = platform.uname()
    affinity: list[int] | None = None
    if hasattr(os, "sched_getaffinity"):
        try:
            affinity = sorted(os.sched_getaffinity(0))
        except OSError:
            affinity = None
    meminfo: dict[str, str] = {}
    raw_meminfo = _read_text_if_present(Path("/proc/meminfo"))
    if raw_meminfo:
        for line in raw_meminfo.splitlines():
            key, separator, value = line.partition(":")
            if separator and key in {"MemTotal", "SwapTotal"}:
                meminfo[key] = value.strip()
    return {
        "cpu_affinity": affinity,
        "cpu_count": os.cpu_count(),
        "hostname": uname.node,
        "machine": uname.machine,
        "meminfo": meminfo,
        "platform": platform.platform(),
        "processor": uname.processor,
        "python_executable": _python_executable(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "release": uname.release,
        "system": uname.system,
    }


def _limit_value(value: int) -> int | str:
    return "infinity" if value == resource.RLIM_INFINITY else int(value)


def _rlimits() -> dict[str, dict[str, int | str]]:
    names = (
        "RLIMIT_AS",
        "RLIMIT_CORE",
        "RLIMIT_CPU",
        "RLIMIT_DATA",
        "RLIMIT_FSIZE",
        "RLIMIT_NOFILE",
        "RLIMIT_RSS",
        "RLIMIT_STACK",
    )
    result: dict[str, dict[str, int | str]] = {}
    for name in names:
        limit_id = getattr(resource, name, None)
        if limit_id is None:
            continue
        soft, hard = resource.getrlimit(limit_id)
        result[name] = {
            "hard": _limit_value(hard),
            "soft": _limit_value(soft),
        }
    return result


def _cgroup_limits() -> dict[str, Any]:
    raw_cgroup = _read_text_if_present(Path("/proc/self/cgroup"))
    if not raw_cgroup:
        return {"detected": False}
    unified_path: str | None = None
    for line in raw_cgroup.splitlines():
        hierarchy, controllers, relative = line.split(":", 2)
        if hierarchy == "0" and controllers == "":
            unified_path = relative
            break
    if unified_path is None:
        return {
            "detected": True,
            "mode": "non_unified_or_unknown",
            "proc_self_cgroup": raw_cgroup.splitlines(),
        }

    cgroup_dir = Path("/sys/fs/cgroup") / unified_path.lstrip("/")
    values: dict[str, str] = {}
    for filename in (
        "cpu.max",
        "memory.high",
        "memory.max",
        "memory.swap.max",
        "pids.max",
    ):
        value = _read_text_if_present(cgroup_dir / filename)
        if value is not None:
            values[filename] = value
    return {
        "detected": True,
        "mode": "cgroup_v2",
        "path": str(cgroup_dir),
        "values": values,
    }


def _resource_limits() -> dict[str, Any]:
    return {
        "cgroup": _cgroup_limits(),
        "rlimit": _rlimits(),
    }


def _normalize_sha256(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ReconstructedProdABError(
            f"{label} must be a lowercase 64-hex SHA-256 digest"
        )
    return normalized


def _validate_config(config: RunConfig) -> None:
    if config.experiment not in {"rab", "fcl"}:
        raise ReconstructedProdABError("experiment must be rab or fcl")
    if config.rab not in {"on", "off"}:
        raise ReconstructedProdABError("rab must be on or off")
    if config.experiment == "rab" and config.lift is not None:
        raise ReconstructedProdABError(
            "RAB experiment forbids --lift; RAB is the sole A/B variable"
        )
    if config.experiment == "fcl":
        if config.rab != "on":
            raise ReconstructedProdABError(
                "FCL experiment requires --rab on"
            )
        if config.lift not in {"on", "off"}:
            raise ReconstructedProdABError(
                "FCL experiment requires --lift on|off"
            )
    if not 1 <= config.ghost_w <= 70 or not 1 <= config.ghost_h <= 70:
        raise ReconstructedProdABError("ghost dimensions must be in [1, 70]")
    for label, value in (
        ("master-seconds", config.master_seconds),
        ("binding-seconds", config.binding_seconds),
        ("routing-seconds", config.routing_seconds),
        ("flow-seconds", config.flow_seconds),
    ):
        if value <= 0:
            raise ReconstructedProdABError(f"{label} must be > 0")
    for label, value in (
        ("max-iterations", config.max_iterations),
        ("workers", config.workers),
        ("binding-alt-cap", config.binding_alt_cap),
    ):
        if value <= 0:
            raise ReconstructedProdABError(f"{label} must be > 0")
    if config.random_seed < 0:
        raise ReconstructedProdABError("random-seed must be >= 0")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", config.run_tag):
        raise ReconstructedProdABError(
            "run-tag must match [A-Za-z0-9_.-]+"
        )
    if (config.hint is None) != (config.hint_sha256 is None):
        raise ReconstructedProdABError(
            "--hint and --hint-sha256 must be supplied together"
        )
    if config.hint_sha256 is not None:
        _normalize_sha256(config.hint_sha256, label="hint-sha256")


def _verify_hint(config: RunConfig) -> dict[str, str | None] | None:
    if config.hint is None:
        return None
    assert config.hint_sha256 is not None
    expected = _normalize_sha256(config.hint_sha256, label="hint-sha256")
    record = _file_record(config.hint)
    observed = str(record["sha256"])
    if observed != expected:
        raise ReconstructedProdABError(
            f"hint SHA-256 mismatch: expected {expected}, observed {observed}"
        )
    return record


def _controlled_environment(
    config: RunConfig,
    *,
    inherited: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if inherited is None else inherited
    env = {
        key: value
        for key, value in source.items()
        if key in SAFE_INHERITED_ENV_NAMES or key.startswith("LC_")
    }
    env.setdefault("PATH", os.defpath)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONNOUSERSITE"] = "1"
    env["MKL_NUM_THREADS"] = str(config.workers)
    env["NUMEXPR_NUM_THREADS"] = str(config.workers)
    env["OMP_NUM_THREADS"] = str(config.workers)
    env["OPENBLAS_NUM_THREADS"] = str(config.workers)
    env["EXACT_CP_SAT_WORKERS"] = str(config.workers)
    env["EXACT_MASTER_CP_SAT_WORKERS"] = str(config.workers)
    env["EXACT_MASTER_RANDOM_SEED"] = str(config.random_seed)
    env["EXACT_MASTER_RANDOM_SEED_BASE"] = str(config.random_seed)
    env["EXACT_MASTER_SEARCH_BRANCHING"] = MASTER_BRANCHING
    env["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = str(MASTER_PROBING_LEVEL)
    env["EXACT_MASTER_SYMMETRY_LEVEL"] = str(MASTER_SYMMETRY_LEVEL)
    env["EXACT_B1_BINDING_ALT_CAP"] = str(config.binding_alt_cap)
    env["EXACT_B1_ROUTING_AWARE_BINDING"] = (
        "1" if config.rab == "on" else "0"
    )
    env["EXACT_MASTER_FRONT_CLEAR_LIFT"] = (
        "1" if config.lift == "on" else "0"
    )
    return dict(sorted(env.items()))


def _worker_argv(config: RunConfig, result_path: Path) -> list[str]:
    argv = [
        _python_executable(),
        str(Path(__file__).resolve()),
        "--_worker",
        "--experiment",
        config.experiment,
        "--rab",
        config.rab,
        "--lift",
        config.lift or "none",
        "--ghost-w",
        str(config.ghost_w),
        "--ghost-h",
        str(config.ghost_h),
        "--master-seconds",
        str(config.master_seconds),
        "--binding-seconds",
        str(config.binding_seconds),
        "--routing-seconds",
        str(config.routing_seconds),
        "--flow-seconds",
        str(config.flow_seconds),
        "--max-iterations",
        str(config.max_iterations),
        "--workers",
        str(config.workers),
        "--binding-alt-cap",
        str(config.binding_alt_cap),
        "--random-seed",
        str(config.random_seed),
        "--run-tag",
        config.run_tag,
        "--result",
        str(result_path.resolve()),
    ]
    if config.hint is not None:
        assert config.hint_sha256 is not None
        argv.extend(
            [
                "--hint",
                str(config.hint.resolve()),
                "--hint-sha256",
                config.hint_sha256,
            ]
        )
    return argv


def _config_json(config: RunConfig) -> dict[str, Any]:
    result = asdict(config)
    result["output_dir"] = str(config.output_dir.resolve())
    result["hint"] = None if config.hint is None else str(config.hint.resolve())
    result.update(
        {
            "master_branching": MASTER_BRANCHING,
            "master_probing_level": MASTER_PROBING_LEVEL,
            "master_symmetry_level": MASTER_SYMMETRY_LEVEL,
            "pythonhashseed": 0,
        }
    )
    return result


def _prepare_output_dir(output_dir: Path) -> Path:
    resolved = output_dir.resolve()
    resolved.mkdir(parents=True, exist_ok=False)
    return resolved


def _build_public_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=["rab", "fcl"], required=True)
    parser.add_argument("--rab", choices=["on", "off"], required=True)
    parser.add_argument("--lift", choices=["on", "off"])
    parser.add_argument("--ghost-w", type=int, default=6)
    parser.add_argument("--ghost-h", type=int, default=6)
    parser.add_argument(
        "--master-seconds", type=float, default=DEFAULT_MASTER_SECONDS
    )
    parser.add_argument(
        "--binding-seconds", type=float, default=DEFAULT_BINDING_SECONDS
    )
    parser.add_argument(
        "--routing-seconds", type=float, default=DEFAULT_ROUTING_SECONDS
    )
    parser.add_argument(
        "--flow-seconds", type=float, default=DEFAULT_FLOW_SECONDS
    )
    parser.add_argument(
        "--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument(
        "--binding-alt-cap", type=int, default=DEFAULT_BINDING_ALT_CAP
    )
    parser.add_argument(
        "--random-seed", type=int, default=DEFAULT_RANDOM_SEED
    )
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--hint",
        type=Path,
        help="Optional current-semantics witness JSON; default is no hint.",
    )
    parser.add_argument(
        "--hint-sha256",
        help="Required exact SHA-256 when --hint is supplied.",
    )
    return parser


def parse_config(argv: Sequence[str] | None = None) -> RunConfig:
    parser = _build_public_parser()
    args = parser.parse_args(argv)
    config = RunConfig(
        experiment=args.experiment,
        rab=args.rab,
        lift=args.lift,
        ghost_w=args.ghost_w,
        ghost_h=args.ghost_h,
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        flow_seconds=args.flow_seconds,
        max_iterations=args.max_iterations,
        workers=args.workers,
        binding_alt_cap=args.binding_alt_cap,
        random_seed=args.random_seed,
        run_tag=args.run_tag,
        output_dir=args.output_dir,
        hint=args.hint,
        hint_sha256=args.hint_sha256,
    )
    try:
        _validate_config(config)
    except ReconstructedProdABError as exc:
        parser.error(str(exc))
    return config


def _child_rusage() -> dict[str, float | int]:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "major_page_faults": int(usage.ru_majflt),
        "max_rss_kib": int(usage.ru_maxrss),
        "system_seconds": round(float(usage.ru_stime), 6),
        "user_seconds": round(float(usage.ru_utime), 6),
    }


def _result_fallback(
    *,
    config: RunConfig,
    exit_code: int,
) -> dict[str, Any]:
    return {
        "arm": _arm_name(config),
        "execution_scope": EXECUTION_SCOPE,
        "experiment": config.experiment,
        "limitations": list(EXECUTION_LIMITATIONS),
        "result_label": (
            f"{config.experiment}_current_production_ab / {SEMANTIC_LABEL}"
        ),
        "schema_version": SCHEMA_VERSION,
        "semantic_label": SEMANTIC_LABEL,
        "status": "WORKER_EXITED_WITHOUT_RESULT",
        "worker_exit_code": exit_code,
    }


def _arm_name(config: RunConfig) -> str:
    if config.experiment == "rab":
        return f"rab_{config.rab}"
    return f"fcl_lift_{config.lift}"


def launch(config: RunConfig, *, launcher_argv: Sequence[str]) -> int:
    _validate_config(config)
    if config.output_dir.exists():
        raise ReconstructedProdABError(
            f"refusing existing output directory: {config.output_dir}"
        )
    hint_record = _verify_hint(config)
    output_dir = config.output_dir.resolve()
    result_path = output_dir / "result.json"
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    run_record_path = output_dir / "run_record.json"
    worker_argv = _worker_argv(config, result_path)
    child_env = _controlled_environment(config)
    inputs = _input_records()
    if hint_record is not None:
        inputs["witness_hint"] = hint_record
    git_snapshot = _git_snapshot()
    resource_limits = _resource_limits()
    source_records = _source_records()
    system_info = _system_info()

    output_dir = _prepare_output_dir(config.output_dir)
    run_record: dict[str, Any] = {
        "arm": _arm_name(config),
        "configuration": _config_json(config),
        "environment_policy": (
            "closed safe inherited allowlist; all inherited EXACT_* removed "
            "before the recorded experiment values are set"
        ),
        "execution_scope": EXECUTION_SCOPE,
        "limitations": list(EXECUTION_LIMITATIONS),
        "experiment": config.experiment,
        "git": git_snapshot,
        "inputs": inputs,
        "invocation": {
            "cwd": str(Path.cwd().resolve()),
            "launcher_argv": list(launcher_argv),
            "worker_argv": worker_argv,
        },
        "outputs": {
            "result": str(result_path),
            "run_record": str(run_record_path),
            "stderr": str(stderr_path),
            "stdout": str(stdout_path),
        },
        "resource_limits": resource_limits,
        "schema_version": SCHEMA_VERSION,
        "semantic_label": SEMANTIC_LABEL,
        "sources": source_records,
        "started_at_utc": _utc_now(),
        "status": "RUNNING",
        "subprocess_environment": child_env,
        "system": system_info,
    }
    _atomic_write_json(run_record_path, run_record)

    exit_code = 125
    try:
        with stdout_path.open("xb") as stdout_handle, stderr_path.open(
            "xb"
        ) as stderr_handle:
            completed = subprocess.run(
                worker_argv,
                cwd=PROJECT_ROOT,
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                check=False,
            )
            exit_code = int(completed.returncode)
    except BaseException as exc:
        run_record["launcher_exception"] = f"{type(exc).__name__}: {exc}"
        run_record["status"] = "LAUNCHER_EXCEPTION"
        raise
    finally:
        if not result_path.exists():
            _atomic_write_json(
                result_path,
                _result_fallback(config=config, exit_code=exit_code),
            )
        run_record["child_resource_usage"] = _child_rusage()
        run_record["finished_at_utc"] = _utc_now()
        if "launcher_exception" not in run_record:
            run_record["status"] = (
                "COMPLETED" if exit_code == 0 else "WORKER_FAILED"
            )
        run_record["worker_exit_code"] = exit_code
        run_record["output_sha256"] = {
            "result": _sha256(result_path.read_bytes()),
            "stderr": (
                _sha256(stderr_path.read_bytes()) if stderr_path.exists() else None
            ),
            "stdout": (
                _sha256(stdout_path.read_bytes()) if stdout_path.exists() else None
            ),
        }
        _atomic_write_json(run_record_path, run_record)
    return exit_code if exit_code >= 0 else 128 - exit_code


def _build_worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--experiment", choices=["rab", "fcl"], required=True)
    parser.add_argument("--rab", choices=["on", "off"], required=True)
    parser.add_argument("--lift", choices=["none", "on", "off"], required=True)
    parser.add_argument("--ghost-w", type=int, required=True)
    parser.add_argument("--ghost-h", type=int, required=True)
    parser.add_argument("--master-seconds", type=float, required=True)
    parser.add_argument("--binding-seconds", type=float, required=True)
    parser.add_argument("--routing-seconds", type=float, required=True)
    parser.add_argument("--flow-seconds", type=float, required=True)
    parser.add_argument("--max-iterations", type=int, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--binding-alt-cap", type=int, required=True)
    parser.add_argument("--random-seed", type=int, required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--hint", type=Path)
    parser.add_argument("--hint-sha256")
    return parser


def _worker_config(args: argparse.Namespace) -> RunConfig:
    config = RunConfig(
        experiment=args.experiment,
        rab=args.rab,
        lift=None if args.lift == "none" else args.lift,
        ghost_w=args.ghost_w,
        ghost_h=args.ghost_h,
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        flow_seconds=args.flow_seconds,
        max_iterations=args.max_iterations,
        workers=args.workers,
        binding_alt_cap=args.binding_alt_cap,
        random_seed=args.random_seed,
        run_tag=args.run_tag,
        output_dir=args.result.parent,
        hint=args.hint,
        hint_sha256=args.hint_sha256,
    )
    _validate_config(config)
    return config


def _assert_worker_environment(config: RunConfig) -> None:
    expected = {
        key: value
        for key, value in _controlled_environment(config, inherited={}).items()
        if (
            key.startswith("EXACT_")
            or key.startswith("PYTHON")
            or key.endswith("_NUM_THREADS")
        )
    }
    observed = {key: os.environ.get(key) for key in expected}
    if observed != expected:
        raise ReconstructedProdABError(
            f"worker environment mismatch: expected {expected}, observed {observed}"
        )


def _apply_hint(
    *,
    config: RunConfig,
    master: Any,
) -> dict[str, Any] | None:
    if config.hint is None:
        return None
    _verify_hint(config)
    hint_payload = json.loads(config.hint.read_text(encoding="utf-8"))
    solution_payload = hint_payload.get("solution")
    if not isinstance(solution_payload, Mapping):
        raise ReconstructedProdABError(
            "witness hint must contain a solution object"
        )
    hint_map: dict[str, int] = {}
    for instance_id, raw_entry in solution_payload.items():
        if not isinstance(raw_entry, Mapping):
            raise ReconstructedProdABError(
                f"hint solution entry {instance_id!r} must be an object"
            )
        pose_idx = raw_entry.get("pose_idx")
        if isinstance(pose_idx, bool) or not isinstance(pose_idx, int):
            raise ReconstructedProdABError(
                f"hint solution entry {instance_id!r}.pose_idx must be an integer"
            )
        hint_map[str(instance_id)] = pose_idx
    delegate = getattr(master, "_coordinate_delegate", None)
    if delegate is None or not hasattr(delegate, "apply_solution_hint"):
        raise ReconstructedProdABError(
            "coordinate delegate does not expose apply_solution_hint"
        )
    stats = delegate.apply_solution_hint(
        hint_map,
        hint_inactive_residual_optionals=False,
    )
    return {
        "hint_entries": len(hint_map),
        **{
            str(key): value
            for key, value in dict(stats).items()
            if isinstance(value, (str, int, float, bool)) or value is None
        },
    }


def _worker_run(config: RunConfig, result_path: Path) -> int:
    _assert_worker_environment(config)
    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    result: dict[str, Any] = {
        "arm": _arm_name(config),
        "configuration": _config_json(config),
        "experiment": config.experiment,
        "execution_scope": EXECUTION_SCOPE,
        "layout_snapshots": [],
        "limitations": list(EXECUTION_LIMITATIONS),
        "result_label": (
            f"{config.experiment}_current_production_ab / {SEMANTIC_LABEL}"
        ),
        "schema_version": SCHEMA_VERSION,
        "semantic_label": SEMANTIC_LABEL,
        "status": "RUNNING",
    }

    def dump() -> None:
        _atomic_write_json(result_path, result)

    dump()
    try:
        started = time.perf_counter()
        session = ExactSearchSession.create(
            PROJECT_ROOT,
            solve_mode="certified_exact",
        )
        result["session_build_seconds"] = round(
            time.perf_counter() - started, 3
        )
        result["session_artifact_hashes"] = dict(
            sorted(session.artifact_hashes.items())
        )
        dump()

        started = time.perf_counter()
        master = MasterPlacementModel.from_exact_core(
            session.core,
            ghost_rect=(config.ghost_w, config.ghost_h),
        )
        result["master_build_seconds"] = round(
            time.perf_counter() - started, 3
        )
        result["master_interval_count"] = master.build_stats.get(
            "master_interval_count"
        )
        result["front_clear_lift_stats"] = {
            str(key): value
            for key, value in dict(
                master.build_stats.get("front_clear_lift", {})
            ).items()
            if key != "demands_by_operation"
        }
        result["solution_hint_stats"] = _apply_hint(
            config=config,
            master=master,
        )
        dump()

        if config.experiment == "fcl":
            corpus_dir = result_path.parent / "layouts"
            corpus_dir.mkdir(exist_ok=False)
            original_extract = master.extract_solution

            def capturing_extract(*extract_args: Any, **extract_kwargs: Any) -> Any:
                solution = original_extract(*extract_args, **extract_kwargs)
                try:
                    encoded, digest = _layout_snapshot_payload(solution)
                    sequence = len(result["layout_snapshots"])
                    filename = (
                        f"layout_{sequence:03d}_{digest[:12]}.json"
                    )
                    layout_path = corpus_dir / filename
                    with layout_path.open("xb") as handle:
                        handle.write(encoded)
                    result["layout_snapshots"].append(
                        {
                            "filename": filename,
                            "sequence": sequence,
                            "sha256": digest,
                        }
                    )
                    dump()
                except Exception as exc:  # noqa: BLE001
                    result.setdefault("corpus_errors", []).append(
                        f"{type(exc).__name__}: {exc}"
                    )
                    dump()
                return solution

            master.extract_solution = capturing_extract

        with tempfile.TemporaryDirectory(
            prefix=f"batch4_{config.experiment}_"
        ) as scratch_name:
            controller = LBBDController(
                master=master,
                cut_manager=CutManager(
                    checkpoint_dir=Path(scratch_name),
                    solve_mode="certified_exact",
                ),
                project_root=PROJECT_ROOT,
                solve_mode="certified_exact",
                master_seconds=config.master_seconds,
                binding_seconds=config.binding_seconds,
                routing_seconds=config.routing_seconds,
                flow_seconds=config.flow_seconds,
                max_iterations=config.max_iterations,
                artifact_hashes=session.artifact_hashes,
                session=session,
            )
            started = time.perf_counter()
            run_exception: Exception | None = None
            try:
                status, solution = controller.run_with_status()
                result["lbbd_status"] = str(status)
                result["lbbd_has_solution"] = solution is not None
            except Exception as exc:  # noqa: BLE001
                run_exception = exc
                result["lbbd_status"] = "HARNESS_EXCEPTION"
                result["lbbd_exception"] = f"{type(exc).__name__}: {exc}"
            result["lbbd_wall_seconds"] = round(
                time.perf_counter() - started, 3
            )

        last_solve = dict(master.build_stats.get("last_solve", {}) or {})
        result["master_last_solve_scalars"] = {
            str(key): value
            for key, value in last_solve.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        for attribute in RAB_CUT_COUNTER_ATTRIBUTES:
            value = getattr(controller, attribute, None)
            result[attribute.lstrip("_")] = (
                value if not callable(value) else None
            )
        proof_summary = getattr(controller, "last_proof_summary", None)
        if isinstance(proof_summary, Mapping):
            result["last_proof_summary_scalars"] = {
                str(key): value
                for key, value in proof_summary.items()
                if isinstance(value, (str, int, float, bool)) or value is None
            }

        if config.experiment == "fcl":
            raw_iterations = getattr(
                controller,
                FCL_RAW_SCOPE_ATTRIBUTE,
                None,
            )
            if callable(raw_iterations) or raw_iterations is None:
                raw_iterations = []
            result["front_clear_raw_empty_by_iteration"] = raw_iterations
            assert config.lift is not None
            result["acceptance_raw_scope_zero"] = (
                _fcl_raw_scope_acceptance(config.lift, raw_iterations)
            )

        result["status"] = (
            "HARNESS_EXCEPTION" if run_exception is not None else "COMPLETED"
        )
        dump()
        print(
            json.dumps(
                {
                    "acceptance": result.get("acceptance_raw_scope_zero"),
                    "arm": result["arm"],
                    "empty_domain_cuts": result.get(
                        "binding_domain_empty_cut_count"
                    ),
                    "layout_snapshots": len(result["layout_snapshots"]),
                    "lbbd_status": result.get("lbbd_status"),
                    "raw_by_iteration": result.get(
                        "front_clear_raw_empty_by_iteration"
                    ),
                    "wall": result.get("lbbd_wall_seconds"),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 2 if run_exception is not None else 0
    except Exception as exc:  # noqa: BLE001
        result["status"] = "HARNESS_EXCEPTION"
        result["exception"] = f"{type(exc).__name__}: {exc}"
        dump()
        raise


def _worker_main(argv: Sequence[str]) -> int:
    parser = _build_worker_parser()
    args = parser.parse_args(argv)
    try:
        config = _worker_config(args)
        return _worker_run(config, args.result)
    except Exception as exc:  # noqa: BLE001
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    config = parse_config(effective_argv)
    launcher_argv = [
        _python_executable(),
        str(Path(__file__).resolve()),
        *effective_argv,
    ]
    try:
        return launch(config, launcher_argv=launcher_argv)
    except ReconstructedProdABError as exc:
        _build_public_parser().error(str(exc))
    return 2


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--_worker":
        raise SystemExit(_worker_main(sys.argv[2:]))
    raise SystemExit(main())
