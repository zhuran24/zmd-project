"""Build the current PreprocessContext JSON and a frozen-artifact parity report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.interchange.preprocess_context import build_template_mapping, load_preprocess_context_from_paths
from src.io.strict_json import load_strict_json
from src.preprocess.demand_solver import (
    generate_ceil_machine_counts,
    generate_generic_io_requirements,
    generate_port_budget,
    normalize_json_numbers,
    solve_demands,
)
from src.preprocess.instance_builder import (
    build_boundary_ports,
    build_core_instance,
    build_exploratory_optional_instances,
    build_manufacturing_instances,
)
from src.preprocess.operation_profiles import aggregate_port_slots, count_operations


def _canonicalize(value: Any) -> Any:
    value = normalize_json_numbers(value)
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(subvalue)
            for key, subvalue in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _load_json(path: Path) -> Any:
    return load_strict_json(path)


def _fsync_directory(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        dir_fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def _atomic_write_json_strict(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-",
        suffix=".json",
        dir=str(path.parent),
    )
    tmp_path = Path(raw_tmp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp_path), str(path))
        _fsync_directory(path.parent)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _diff_entry(*, name: str, regenerated: Any, frozen: Any) -> dict[str, Any]:
    canonical_regenerated = _canonicalize(regenerated)
    canonical_frozen = _canonicalize(frozen)
    matches = canonical_regenerated == canonical_frozen
    entry = {
        "name": name,
        "matches_frozen": bool(matches),
    }
    if not matches:
        entry["regenerated"] = canonical_regenerated
        entry["frozen"] = canonical_frozen
    return entry


def build_diff_report(project_root: Path, *, context_payload: Mapping[str, Any]) -> dict[str, Any]:
    del context_payload
    context = load_preprocess_context_from_paths(
        rules_path=project_root / "rules" / "canonical_rules.json",
        plan_path=project_root / "rules" / "preprocess_plan.json",
    )
    flows, fractional = solve_demands(context=context)
    machine_counts = generate_ceil_machine_counts(fractional)
    port_budget = generate_port_budget(flows, context=context)
    generic_io = generate_generic_io_requirements(flows, port_budget, context=context)
    template_mapping = build_template_mapping(context)
    mandatory_exact_instances = (
        build_manufacturing_instances(machine_counts, template_mapping=template_mapping)
        + build_core_instance()
        + build_boundary_ports(46)
    )
    all_facility_instances = mandatory_exact_instances + build_exploratory_optional_instances()
    slot_summary = aggregate_port_slots(count_operations(all_facility_instances, mandatory_only=True))

    preprocessed_dir = project_root / "data" / "preprocessed"
    comparisons = [
        _diff_entry(
            name="commodity_demands.json",
            regenerated=flows,
            frozen=_load_json(preprocessed_dir / "commodity_demands.json"),
        ),
        _diff_entry(
            name="machine_counts.json",
            regenerated=machine_counts,
            frozen=_load_json(preprocessed_dir / "machine_counts.json"),
        ),
        _diff_entry(
            name="port_budget.json",
            regenerated=port_budget,
            frozen=_load_json(preprocessed_dir / "port_budget.json"),
        ),
        _diff_entry(
            name="generic_io_requirements.json",
            regenerated=generic_io,
            frozen=_load_json(preprocessed_dir / "generic_io_requirements.json"),
        ),
        _diff_entry(
            name="mandatory_exact_instances.json",
            regenerated=mandatory_exact_instances,
            frozen=_load_json(preprocessed_dir / "mandatory_exact_instances.json"),
        ),
        _diff_entry(
            name="all_facility_instances.json",
            regenerated=all_facility_instances,
            frozen=_load_json(preprocessed_dir / "all_facility_instances.json"),
        ),
    ]
    return {
        "metadata": {
            "artifact_type": "preprocess_context_diff_report",
            "generated_by": "scripts/build_current_preprocess_context.py",
        },
        "summary": {
            "all_match": all(entry["matches_frozen"] for entry in comparisons),
            "matched_count": sum(1 for entry in comparisons if entry["matches_frozen"]),
            "total_count": len(comparisons),
            "mandatory_exact_instance_count": len(mandatory_exact_instances),
            "all_instance_count": len(all_facility_instances),
            "generic_output_slots": slot_summary["generic_output_slots"],
            "generic_input_slots": slot_summary["generic_input_slots"],
        },
        "comparisons": comparisons,
    }


def render_diff_report_markdown(diff_report: Mapping[str, Any]) -> str:
    lines = [
        "# Preprocess Context Diff Report",
        "",
        f"- all_match: `{diff_report['summary']['all_match']}`",
        f"- matched_count: `{diff_report['summary']['matched_count']}/{diff_report['summary']['total_count']}`",
        f"- mandatory_exact_instance_count: `{diff_report['summary']['mandatory_exact_instance_count']}`",
        f"- all_instance_count: `{diff_report['summary']['all_instance_count']}`",
        f"- generic_output_slots: `{diff_report['summary']['generic_output_slots']}`",
        f"- generic_input_slots: `{diff_report['summary']['generic_input_slots']}`",
        "",
        "## Artifact Comparisons",
        "",
    ]
    for entry in diff_report["comparisons"]:
        status = "MATCH" if entry["matches_frozen"] else "DIFF"
        lines.append(f"- `{entry['name']}`: **{status}**")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the current PreprocessContext and a frozen-artifact diff report.")
    parser.add_argument("--rules", default="rules/canonical_rules.json", help="Path to canonical_rules.json")
    parser.add_argument("--plan", default="rules/preprocess_plan.json", help="Path to preprocess_plan.json")
    parser.add_argument(
        "--output",
        default="data/solutions/current_preprocess_context.json",
        help="Output JSON path for the current PreprocessContext payload.",
    )
    parser.add_argument(
        "--diff-json",
        default="data/solutions/preprocess_context_diff_report.json",
        help="Output JSON path for the parity report.",
    )
    parser.add_argument(
        "--diff-md",
        default="data/solutions/preprocess_context_diff_report.md",
        help="Output Markdown path for the parity report.",
    )
    args = parser.parse_args()

    context = load_preprocess_context_from_paths(
        rules_path=Path(args.rules),
        plan_path=Path(args.plan),
    )
    context_payload = context.to_dict()
    _atomic_write_json_strict(Path(args.output), context_payload)

    diff_report = build_diff_report(PROJECT_ROOT, context_payload=context_payload)
    _atomic_write_json_strict(Path(args.diff_json), diff_report)
    diff_md_path = Path(args.diff_md)
    diff_md_path.parent.mkdir(parents=True, exist_ok=True)
    diff_md_path.write_text(render_diff_report_markdown(diff_report), encoding="utf-8")

    print(f"preprocess context written: {args.output}")
    print(f"diff report written: {args.diff_json}")
    print(f"diff markdown written: {args.diff_md}")


if __name__ == "__main__":
    main()
