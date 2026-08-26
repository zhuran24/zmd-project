#!/usr/bin/env python3
"""Freeze the E031 best bounded-assignment shared-optimum face."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
OUT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/OPTIMUM_FACE_AUDIT.json"
)
FAILURE = OUT.with_name("OPTIMUM_FACE_AUDIT_FAILURE.json")
BEST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/BEST_ASSIGNMENT.json"
)
RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/RESULT.json"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E004_component_mismatch_atlas/run_e004.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E015_shared_binding_gradient/run_e015.py"
)
FACE_AUDIT = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E015_shared_binding_gradient/audit_optimum_face.py"
)

EXPECTED_HASHES = {
    BEST_ASSIGNMENT: "f34bcc394835730ac3a6925fcb7ac415d2cc57f79680af0372e4f4ab394b4dcf",
    RESULT: "a6efad78e382133b0b5b2492bbb048e6e15726294ec3940c0a777bceecd791b2",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    FACE_AUDIT: "466d775cdce4272435e7e07c003b8413ecb24b39592af428037a7311196be542",
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("PYTHONHASHSEED must be 0")
    if os.environ.get("EXACT_BINDING_CP_SAT_WORKERS") != "4":
        raise RuntimeError("EXACT_BINDING_CP_SAT_WORKERS must be 4")
    e001 = import_module("zmd_e031face_e001", E001_RUNNER)
    e004 = import_module("zmd_e031face_e004", E004_RUNNER)
    e015 = import_module("zmd_e031face_e015", E015_RUNNER)
    audit = import_module("zmd_e031face_audit", FACE_AUDIT)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    solution = load_json(BEST_ASSIGNMENT)["solution"]
    result = load_json(RESULT)
    face = audit.profile_optimum_face(
        label="E031_BEST_BOUNDED_ASSIGNMENT",
        solution=solution,
        optimum=int(result["best_child"]["objective"]),
        inputs=inputs,
        e004=e004,
        e015=e015,
    )
    return {
        "schema": "zmd_zero_condition_e031_optimum_face_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": {
            "checked_hashes": checked,
            "runner_sha256": sha256_file(Path(__file__).resolve()),
        },
        "face": face,
        "verdict": "BOUNDED_ASSIGNMENT_OPTIMUM_FACE_EXACT",
        "truth_boundary": (
            "Exact per-commodity ranges over the fixed E031 best-assignment "
            "shared-objective optimum face only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if OUT.exists() or FAILURE.exists():
        raise FileExistsError("refusing to overwrite E031 optimum-face audit")
    try:
        result = run()
        dump_exclusive(OUT, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "varying": result["face"]["varying_commodities"],
                    "constant_pair_sum": result["face"]["blue_source_ore_sum"],
                    "result_path": str(OUT),
                    "result_sha256": sha256_file(OUT),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e031_optimum_face_audit_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not FAILURE.exists():
            dump_exclusive(FAILURE, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
