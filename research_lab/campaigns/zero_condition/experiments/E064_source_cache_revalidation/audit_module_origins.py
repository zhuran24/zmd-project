#!/usr/bin/env python3
"""Record the code-object origins loaded for E057-E062 runner modules."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
RUNNERS = {
    "E057": ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E057_qiaoyu_external_body_relation/run_e057.py",
    "E058": ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E058_all6x4_terminal_signature_frontier/run_e058.py",
    "E059": ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E059_two_zero_tradeoff_certificate/run_e059.py",
    "E060": ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E060_generic_qiaoyu_sink_correction/run_e060.py",
    "E061": ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E061_all_one_object_signature_frontier/run_e061.py",
    "E062": ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E062_one_object_tradeoff_atlas/run_e062.py",
}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def import_runner(label: str, path: Path) -> Any:
    module_name = f"zmd_e064_origin_{label.lower()}_{os.getpid()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def audit_runner(label: str, path: Path) -> dict[str, Any]:
    module = import_runner(label, path)
    source_path = path.resolve()
    functions: list[dict[str, Any]] = []
    for name, value in sorted(module.__dict__.items()):
        if not inspect.isfunction(value):
            continue
        origin = Path(value.__code__.co_filename).resolve()
        functions.append(
            {
                "name": name,
                "origin": str(origin),
                "first_line": int(value.__code__.co_firstlineno),
                "matches_requested_source": origin == source_path,
            }
        )
    foreign = [row for row in functions if not row["matches_requested_source"]]
    return {
        "label": label,
        "requested_source": str(source_path),
        "requested_source_sha256": sha256_file(path),
        "module_file": str(Path(module.__file__).resolve()),
        "function_count": len(functions),
        "foreign_function_count": len(foreign),
        "foreign_functions": foreign,
        "functions": functions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run from research root: {Path.cwd()}")
    audits = [audit_runner(label, path) for label, path in RUNNERS.items()]
    result = {
        "schema": "zmd_zero_condition_e064_module_origin_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "label": str(args.label),
        "python_executable": sys.executable,
        "python_cache_prefix": os.environ.get("PYTHONPYCACHEPREFIX"),
        "runner_count": len(audits),
        "foreign_function_count": sum(
            int(row["foreign_function_count"]) for row in audits
        ),
        "audits": audits,
        "ledger_effect": "none",
    }
    dump_exclusive(args.output, result)
    print(
        json.dumps(
            {
                "label": result["label"],
                "foreign_function_count": result["foreign_function_count"],
                "output": str(args.output),
                "sha256": sha256_file(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
