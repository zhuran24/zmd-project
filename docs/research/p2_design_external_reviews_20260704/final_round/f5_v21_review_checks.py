#!/usr/bin/env python3
"""F5 v2.1 final-review checks.

Run from any directory:
    python3 f5_v21_review_checks.py /path/to/repo/root

The script intentionally treats a missing candidate_placements.json as UNKNOWN rather
than PASS, because P-HOM is not closed until the runtime pose pool artifact is audited.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

INSTANCE_FIELD_NAMES = {"instance_id", "slot", "slot_index", "instance", "solution_id"}
INSTANCE_FIELD_FRAGMENTS = ("instance_id", "slot_index", "solution_id", "per_instance")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def canonical_json_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def iter_key_paths(value: Any, prefix: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for k, v in value.items():
            path = (*prefix, str(k))
            yield path, v
            yield from iter_key_paths(v, path)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from iter_key_paths(v, (*prefix, f"[{i}]"))


def check_mandatory(root: Path) -> dict[str, Any]:
    path = root / "data" / "preprocessed" / "mandatory_exact_instances.json"
    records = load_json(path)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        groups[(str(record.get("facility_type")), str(record.get("operation_type")))].append(record)
    violations: list[dict[str, Any]] = []
    for key, items in groups.items():
        base = {k: v for k, v in items[0].items() if k != "instance_id"}
        for idx, item in enumerate(items[1:], start=1):
            comp = {k: v for k, v in item.items() if k != "instance_id"}
            if comp != base:
                violations.append({"group": key, "index": idx, "base": base, "actual": comp})
    manufacturing = [r for r in records if r.get("facility_type") == "manufacturing_3x3"]
    manufacturing_counts = collections.Counter(str(r["operation_type"]) for r in manufacturing)
    all_group_counts = [len(v) for v in groups.values()]
    return {
        "records": len(records),
        "groups": len(groups),
        "violations_mod_instance_id": len(violations),
        "manufacturing_3x3_counts": dict(sorted(manufacturing_counts.items())),
        "manufacturing_3x3_total": sum(manufacturing_counts.values()),
        "log10_factorial_product_manufacturing_3x3": sum(math.lgamma(n + 1) / math.log(10) for n in manufacturing_counts.values()),
        "log10_factorial_product_all_mandatory_groups": sum(math.lgamma(n + 1) / math.log(10) for n in all_group_counts),
    }


def check_counts() -> dict[str, Any]:
    falling = 1
    for x in range(34, 26, -1):
        falling *= x
    return {"falling_factorial_34_8": falling}


def check_candidate_placements(root: Path) -> dict[str, Any]:
    candidates = [
        root / "data" / "preprocessed" / "candidate_placements.json",
        root / "data" / "candidate_placements.json",
        root / "candidate_placements.json",
    ]
    found = next((p for p in candidates if p.exists()), None)
    if found is None:
        return {"status": "UNKNOWN_MISSING_ARTIFACT", "checked_paths": [str(p) for p in candidates]}
    data = load_json(found)
    facility_pools = data.get("facility_pools") if isinstance(data, dict) else None
    suspicious: list[str] = []
    for path, _ in iter_key_paths(facility_pools):
        joined = ".".join(path).lower()
        leaf = path[-1].lower() if path else ""
        if leaf in INSTANCE_FIELD_NAMES or any(fragment in joined for fragment in INSTANCE_FIELD_FRAGMENTS):
            suspicious.append(".".join(path))
    return {
        "status": "PASS" if not suspicious else "FAIL_INSTANCE_DIMENSION_KEY",
        "path": str(found),
        "suspicious_keys": suspicious[:50],
        "facility_pool_digest": canonical_json_digest(facility_pools),
    }


def check_source_refs(root: Path) -> dict[str, Any]:
    required_for_v21_audit = [
        "src/placement/placement_generator.py",
        "src/subproblems/binding_subproblem.py",
        "src/subproblems/routing_subproblem.py",
    ]
    # Accept alternate names if the repo has flattened modules.
    alternates = {
        "src/subproblems/binding_subproblem.py": ["src/binding_subproblem.py", "src/models/binding_subproblem.py"],
        "src/subproblems/routing_subproblem.py": ["src/routing_subproblem.py", "src/models/routing_subproblem.py"],
    }
    result: dict[str, Any] = {}
    for rel in required_for_v21_audit:
        paths = [root / rel] + [root / alt for alt in alternates.get(rel, [])]
        result[rel] = {"present": any(p.exists() for p in paths), "checked": [str(p.relative_to(root)) for p in paths]}
    return result


def check_current_f5_code_shape(root: Path) -> dict[str, Any]:
    pattern = (root / "src" / "cuts" / "families" / "pattern_nogood.py").read_text(encoding="utf-8")
    oracle = (root / "src" / "cuts" / "oracles" / "pattern_nogood_oracle.py").read_text(encoding="utf-8")
    minimizer = (root / "src" / "cuts" / "helpers" / "bounded_core_minimizer.py").read_text(encoding="utf-8")
    cert_schema = (root / "src" / "cuts" / "cert_schema.py").read_text(encoding="utf-8")
    return {
        "validator_has_seen_slots": "seen_slots" in pattern,
        "validator_has_seen_group_pose_check": "seen_group_pose" in pattern or "seen_poses" in pattern,
        "oracle_protocol_still_takes_state": "state: BState" in oracle and "def query_liftable" not in oracle,
        "canonical_sort_only_sort_dedup": "dict.fromkeys" in minimizer and "canonical_relabel" not in minimizer,
        "cert_schema_has_orbit_homogeneity_digest": "orbit_homogeneity_digest" in cert_schema,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = {
        "root": str(root),
        "mandatory": check_mandatory(root),
        "counts": check_counts(),
        "candidate_placements": check_candidate_placements(root),
        "source_refs": check_source_refs(root),
        "current_f5_code_shape": check_current_f5_code_shape(root),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    hard_fail = report["mandatory"]["violations_mod_instance_id"] != 0
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
