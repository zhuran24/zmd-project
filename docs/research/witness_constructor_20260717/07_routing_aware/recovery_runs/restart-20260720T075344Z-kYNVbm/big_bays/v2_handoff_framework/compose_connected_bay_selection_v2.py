#!/usr/bin/env python3
"""Compose then bind a connected-bay handoff to an explicit geometry bundle.

The row-composition implementation is hash-pinned and imported read-only.  This
adapter upgrades its in-memory v1 result to ``connected_bay_selection.v2`` only
after a complete ``routing_geometry_bundle.v2`` passes strict structural,
semantic, and recursive source-hash checks.  No solver or router is run.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import secrets
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY_ROOT = (
    PROJECT_ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
ROUTING_ROOT = RECOVERY_ROOT.parents[1]
HERE = RECOVERY_ROOT / "big_bays/v2_handoff_framework"
OUTPUT_ROOT = HERE / "composed_v2"
LEGACY_COMPOSER = RECOVERY_ROOT / "compose_connected_bay_selection.py"
LOCAL_CONTRACT = HERE / "connected_bay_selection_v2_contract.py"
ASSEMBLER = ROUTING_ROOT / "assemble_connected_bays.py"
EXPECTED = {
    LEGACY_COMPOSER: "90f54dc441aa25702ff05f283497806011ce7600dc12b572f043a5782885065e",
    LOCAL_CONTRACT: "b13cab670ed592ff04fda1f669151cbe8ccfdf70f6540210eb5a3a9f1a1b2285",
    ASSEMBLER: "47927d4892b905a7b806a1e5916e58ecf4b1cfdf0cbc5a547fe065bc64fdedd5",
}
BUNDLE_SCHEMA = "routing_geometry_bundle.v2"
BUNDLE_READY_STATUS = "ROUTING_GEOMETRY_BUNDLE_READY"
SELECTION_SCHEMA = "connected_bay_selection.v2"
EXPECTED_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
GRID_SIZE = 70
VERTICAL_LANES = (1, 12, 24, 36, 48, 59)
HORIZONTAL_LANES = (1, 36, 59)
AFFECTED_BAYS = (4, 5, 9, 10, 11)
Cell = tuple[int, int]


class V2ComposeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V2ComposeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


for pinned_path, expected_digest in EXPECTED.items():
    require(pinned_path.is_file(), f"missing pinned framework input: {pinned_path}")
    require(sha256(pinned_path) == expected_digest, f"framework hash drift: {pinned_path}")

sys.path.insert(0, str(RECOVERY_ROOT))
legacy = importlib.import_module("compose_connected_bay_selection")
sys.path.pop(0)
sys.path.insert(0, str(HERE))
contract = importlib.import_module("connected_bay_selection_v2_contract")
sys.path.pop(0)


@dataclass(frozen=True)
class GeometryBundle:
    source: Any
    pole_anchors: tuple[Cell, ...]
    protected_rectangle: tuple[int, int, int, int]
    recursive_sources: tuple[Any, ...]


def mapping(value: object, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping) and all(type(key) is str for key in value), f"{label}: expected object")
    return value


def sequence(value: object, label: str) -> Sequence[Any]:
    require(isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)), f"{label}: expected array")
    return value


def integer(value: object, label: str) -> int:
    require(type(value) is int, f"{label}: expected integer")
    return value


def cell(value: object, label: str) -> Cell:
    raw = sequence(value, label)
    require(len(raw) == 2, f"{label}: expected two coordinates")
    return integer(raw[0], f"{label}[0]"), integer(raw[1], f"{label}[1]")


def cells(value: object, label: str) -> set[Cell]:
    raw = sequence(value, label)
    parsed = {cell(item, f"{label}[{index}]") for index, item in enumerate(raw)}
    require(len(parsed) == len(raw), f"{label}: duplicate cells")
    return parsed


def rect(anchor: Cell, width: int, height: int) -> set[Cell]:
    return {(x, y) for x in range(anchor[0], anchor[0] + width) for y in range(anchor[1], anchor[1] + height)}


def backbone_cells() -> set[Cell]:
    core = rect((60, 60), 9, 9)
    core_ring = rect((59, 59), 11, 11) - core
    return (
        {(x, y) for x in VERTICAL_LANES for y in range(1, GRID_SIZE)}
        | {(x, y) for y in HORIZONTAL_LANES for x in range(1, GRID_SIZE)}
        | core_ring
    ) - core


def bundle_required_fields() -> set[str]:
    result = {
        "schema_version",
        "status",
        "claim_boundary",
        "baseline_head",
        "all_35_pole_anchors",
        "protected_rect",
        "protected_cells",
        "protected_backbone_overlap_cells",
        "protected_new_body_forbidden_cells",
        "fixed_semantics",
    }
    for component in AFFECTED_BAYS:
        result.update(
            {
                f"c{component}_result_path",
                f"c{component}_result_sha256",
                f"c{component}_independent_replay_path",
                f"c{component}_independent_replay_sha256",
            }
        )
    return result


def resolve_bundle_path(raw: object, label: str) -> Path:
    text = raw if isinstance(raw, str) else None
    require(bool(text), f"{label}: expected path string")
    path = Path(str(text))
    if not path.is_absolute():
        path = RECOVERY_ROOT / path
    resolved = legacy.regular_non_symlink(path, label)
    require(resolved.is_relative_to(RECOVERY_ROOT), f"{label}: outside recovery root")
    return resolved


def parse_geometry_bundle(source: Any) -> GeometryBundle:
    value = mapping(source.value, "geometry bundle")
    missing = bundle_required_fields() - set(value)
    require(not missing, f"geometry bundle missing fields: {sorted(missing)!r}")
    require(value.get("schema_version") == BUNDLE_SCHEMA, "geometry bundle schema")
    require(value.get("status") == BUNDLE_READY_STATUS, "geometry bundle status")
    require(value.get("baseline_head") == EXPECTED_HEAD, "geometry bundle baseline head")
    require(isinstance(value.get("claim_boundary"), str) and value["claim_boundary"], "geometry bundle claim boundary")

    poles = tuple(sorted(cells(value.get("all_35_pole_anchors"), "all_35_pole_anchors"), key=lambda item: (item[1], item[0])))
    require(len(poles) == 35, "geometry bundle requires 35 unique poles")
    pole_bodies: set[Cell] = set()
    for anchor in poles:
        body = rect(anchor, 2, 2)
        require(len(body) == 4 and all(0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE for x, y in body), f"pole out of grid {anchor}")
        require(not body & pole_bodies, f"pole body overlap {anchor}")
        pole_bodies |= body

    protected_row = mapping(value.get("protected_rect"), "protected_rect")
    require(set(protected_row) == {"anchor", "width", "height"}, "protected_rect exact fields")
    anchor = cell(protected_row.get("anchor"), "protected_rect.anchor")
    width = integer(protected_row.get("width"), "protected_rect.width")
    height = integer(protected_row.get("height"), "protected_rect.height")
    require((width, height) == (6, 7), "protected_rect shape")
    protected = rect(anchor, width, height)
    require(len(protected) == 42 and all(0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE for x, y in protected), "protected_rect grid")
    require(cells(value.get("protected_cells"), "protected_cells") == protected, "protected_cells mismatch")
    require(not protected & pole_bodies, "protected rectangle intersects pole body")
    backbone = backbone_cells()
    require(
        cells(value.get("protected_backbone_overlap_cells"), "protected_backbone_overlap_cells") == protected & backbone,
        "protected backbone overlap mismatch",
    )
    require(
        cells(value.get("protected_new_body_forbidden_cells"), "protected_new_body_forbidden_cells")
        == protected - backbone,
        "protected new body-forbidden mismatch",
    )

    semantics = mapping(value.get("fixed_semantics"), "fixed_semantics")
    required_semantics = {
        "grid_size",
        "vertical_backbone_lanes",
        "horizontal_backbone_lanes",
        "core_anchor",
        "core_size",
        "boundary_left_and_bottom",
        "protected_may_overlap_backbone",
        "protected_may_not_overlap_facility_or_aux_body",
    }
    require(required_semantics <= set(semantics), "fixed_semantics missing fields")
    require(integer(semantics.get("grid_size"), "fixed_semantics.grid_size") == GRID_SIZE, "grid size drift")
    require(tuple(integer(item, "vertical lane") for item in sequence(semantics.get("vertical_backbone_lanes"), "vertical lanes")) == VERTICAL_LANES, "vertical lanes drift")
    require(tuple(integer(item, "horizontal lane") for item in sequence(semantics.get("horizontal_backbone_lanes"), "horizontal lanes")) == HORIZONTAL_LANES, "horizontal lanes drift")
    require(cell(semantics.get("core_anchor"), "fixed_semantics.core_anchor") == (60, 60), "core anchor drift")
    require(cell(semantics.get("core_size"), "fixed_semantics.core_size") == (9, 9), "core size drift")
    require(semantics.get("protected_may_overlap_backbone") is True, "protected/backbone semantic drift")
    require(semantics.get("protected_may_not_overlap_facility_or_aux_body") is True, "protected/body semantic drift")
    require(semantics.get("boundary_left_and_bottom") is not None, "boundary semantic missing")

    recursive = []
    for component in AFFECTED_BAYS:
        for kind in ("result", "independent_replay"):
            path_key = f"c{component}_{kind}_path"
            sha_key = f"c{component}_{kind}_sha256"
            path = resolve_bundle_path(value.get(path_key), path_key)
            digest = value.get(sha_key)
            require(isinstance(digest, str), f"{sha_key}: expected digest")
            recursive.append(legacy.load_pinned(path, digest, f"geometry bundle {path_key}"))
    return GeometryBundle(source, poles, (anchor[0], anchor[1], width, height), tuple(recursive))


def merged_source_artifacts(sources: Sequence[Any]) -> list[dict[str, str]]:
    unique: dict[Path, str] = {}
    for source in sources:
        previous = unique.setdefault(source.path, source.sha256)
        require(previous == source.sha256, f"source hash conflict {source.path}")
    return [{"path": str(path), "sha256": unique[path]} for path in sorted(unique, key=str)]


def upgrade_selection(
    legacy_selection: Mapping[str, Any],
    geometry: GeometryBundle,
    *,
    inherited_sources: Sequence[Any],
) -> dict[str, Any]:
    expected_v1_fields = {
        "schema_version",
        "status",
        "claim_boundary",
        "baseline_head",
        "source_artifacts",
        "pole_anchors",
        "components",
    }
    require(set(legacy_selection) == expected_v1_fields, "legacy selection field drift")
    require(legacy_selection.get("schema_version") == "connected_bay_selection.v1", "legacy selection schema")
    selection_poles = tuple(sorted((cell(raw, "legacy pole") for raw in sequence(legacy_selection.get("pole_anchors"), "legacy poles")), key=lambda item: (item[1], item[0])))
    require(selection_poles == geometry.pole_anchors, "selection/geometry pole mismatch")
    sources = [*inherited_sources, geometry.source, *geometry.recursive_sources]
    upgraded = dict(legacy_selection)
    upgraded["schema_version"] = SELECTION_SCHEMA
    upgraded["source_artifacts"] = merged_source_artifacts(sources)
    upgraded["protected_rectangle"] = list(geometry.protected_rectangle)
    parsed = contract.parse_selection(
        upgraded,
        selection_parent=RECOVERY_ROOT,
        source_root=RECOVERY_ROOT,
        verify_sources=True,
    )
    require(parsed.pole_anchors == geometry.pole_anchors, "local parser pole drift")
    require(parsed.protected_rectangle == geometry.protected_rectangle, "local parser protected drift")

    bootstrap = (PROJECT_ROOT, ROUTING_ROOT)
    for path in bootstrap:
        sys.path.insert(0, str(path))
    try:
        assembler = importlib.import_module("assemble_connected_bays")
    finally:
        for path in reversed(bootstrap):
            sys.path.remove(str(path))
    assembler_parsed = assembler.parse_selection(upgraded, selection_parent=RECOVERY_ROOT, verify_source_artifacts=True)
    require(assembler_parsed.protected_rectangle == geometry.protected_rectangle, "assembler protected drift")
    require(assembler_parsed.pole_anchors == geometry.pole_anchors, "assembler pole drift")
    return upgraded


def fresh_run_directory() -> Path:
    OUTPUT_ROOT.mkdir(mode=0o755, parents=True, exist_ok=True)
    for _attempt in range(16):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        candidate = OUTPUT_ROOT / f"selection-v2-{stamp}-{secrets.token_hex(3)}"
        try:
            candidate.mkdir(mode=0o755, parents=False, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise V2ComposeError("could not allocate unique v2 output directory")


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-bundle", required=True, help="PATH=SHA256")
    parser.add_argument("--plan", type=Path, default=legacy.DEFAULT_PLAN)
    parser.add_argument("--plan-sha256", default=legacy.DEFAULT_PLAN_SHA256)
    parser.add_argument("--big-g", required=True)
    parser.add_argument("--big-g-replay", required=True)
    parser.add_argument("--big-h", required=True)
    parser.add_argument("--big-h-replay", required=True)
    args = parser.parse_args(argv)
    try:
        bundle_path, bundle_sha = legacy.parse_path_sha(args.geometry_bundle, "geometry bundle")
        bundle_source = legacy.load_pinned(bundle_path, bundle_sha, "geometry bundle")
        geometry = parse_geometry_bundle(bundle_source)
        plan_path = args.plan if args.plan.is_absolute() else RECOVERY_ROOT / args.plan
        plan_source = legacy.load_pinned(plan_path, args.plan_sha256, "plan")
        pinned_inputs = {
            path: legacy.load_pinned(path, digest, f"pinned input {path.name}")
            for path, digest in legacy.PINNED_INPUTS.items()
        }
        dynamic = {}
        for label, raw in (
            ("big G", args.big_g),
            ("big G replay", args.big_g_replay),
            ("big H", args.big_h),
            ("big H replay", args.big_h_replay),
        ):
            path, digest = legacy.parse_path_sha(raw, label)
            dynamic[label] = legacy.load_pinned(path, digest, label)
        legacy_selection, legacy_report = legacy.compose(
            plan_source=plan_source,
            pinned_inputs=pinned_inputs,
            g_source=dynamic["big G"],
            g_replay=dynamic["big G replay"],
            h_source=dynamic["big H"],
            h_replay=dynamic["big H replay"],
        )
        inherited_sources = [plan_source, *pinned_inputs.values(), *dynamic.values()]
        selection = upgrade_selection(legacy_selection, geometry, inherited_sources=inherited_sources)
        run_dir = fresh_run_directory()
        selection_path = run_dir / "connected_bay_selection.v2.json"
        report_path = run_dir / "composition_report.v2.json"
        write_json_exclusive(selection_path, selection)
        selection_sha = sha256(selection_path)
        report = {
            "schema_version": "connected_bay_selection_v2_composition_report.v1",
            "status": "SELECTION_V2_COMPOSED_AND_REPARSED",
            "claim_boundary": "Schema composition and exact reparse only; no geometry assembly or routing conclusion.",
            "selection_path": str(selection_path),
            "selection_sha256": selection_sha,
            "geometry_bundle_path": str(geometry.source.path),
            "geometry_bundle_sha256": geometry.source.sha256,
            "protected_rectangle": list(geometry.protected_rectangle),
            "legacy_report": legacy_report,
        }
        write_json_exclusive(report_path, report)
        with (run_dir / "SHA256SUMS").open("x", encoding="ascii", newline="\n") as handle:
            handle.write(f"{selection_sha}  connected_bay_selection.v2.json\n")
            handle.write(f"{sha256(report_path)}  composition_report.v2.json\n")
        print(json.dumps({"status": report["status"], "run_dir": str(run_dir), "selection_sha256": selection_sha}, sort_keys=True))
        return 0
    except (V2ComposeError, legacy.ComposeError, contract.ContractError) as exc:
        print(json.dumps({"status": "SELECTION_V2_COMPOSITION_REJECTED", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
