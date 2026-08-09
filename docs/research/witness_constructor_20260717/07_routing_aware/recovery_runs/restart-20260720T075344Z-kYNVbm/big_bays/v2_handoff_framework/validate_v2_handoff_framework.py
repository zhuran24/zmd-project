#!/usr/bin/env python3
"""Run positive and mutation-negative checks for the v2 handoff framework."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import secrets
import sys
from typing import Any, Callable, Mapping


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
HERE = RECOVERY / "big_bays/v2_handoff_framework"
OUTPUT_ROOT = HERE / "framework_validation"
sys.path.insert(0, str(HERE))
composer = importlib.import_module("compose_connected_bay_selection_v2")
contract = importlib.import_module("connected_bay_selection_v2_contract")
sys.path.pop(0)


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def fresh_run() -> Path:
    OUTPUT_ROOT.mkdir(mode=0o755, parents=True, exist_ok=True)
    for _attempt in range(16):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        candidate = OUTPUT_ROOT / f"validation-{stamp}-{secrets.token_hex(3)}"
        try:
            candidate.mkdir(mode=0o755, parents=False, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise ValidationError("cannot allocate validation run")


def fixture_poles() -> list[list[int]]:
    return [
        [x, y]
        for x, y in sorted(
            ({(x, y) for x in (5, 17, 29, 41, 53, 65) for y in (5, 17, 29, 41, 53, 65)} - {(65, 65)}),
            key=lambda item: (item[1], item[0]),
        )
    ]


def fixture_bundle(dummy_path: Path, dummy_sha: str) -> dict[str, Any]:
    anchor = (20, 20)
    protected = composer.rect(anchor, 6, 7)
    backbone = composer.backbone_cells()
    value: dict[str, Any] = {
        "schema_version": composer.BUNDLE_SCHEMA,
        "status": composer.BUNDLE_READY_STATUS,
        "claim_boundary": "Synthetic framework fixture only.",
        "baseline_head": composer.EXPECTED_HEAD,
        "all_35_pole_anchors": fixture_poles(),
        "protected_rect": {"anchor": list(anchor), "width": 6, "height": 7},
        "protected_cells": [list(cell) for cell in sorted(protected)],
        "protected_backbone_overlap_cells": [list(cell) for cell in sorted(protected & backbone)],
        "protected_new_body_forbidden_cells": [list(cell) for cell in sorted(protected - backbone)],
        "fixed_semantics": {
            "grid_size": 70,
            "vertical_backbone_lanes": list(composer.VERTICAL_LANES),
            "horizontal_backbone_lanes": list(composer.HORIZONTAL_LANES),
            "core_anchor": [60, 60],
            "core_size": [9, 9],
            "boundary_left_and_bottom": "fixed gap pattern",
            "protected_may_overlap_backbone": True,
            "protected_may_not_overlap_facility_or_aux_body": True,
        },
    }
    for component in composer.AFFECTED_BAYS:
        value[f"c{component}_result_path"] = str(dummy_path)
        value[f"c{component}_result_sha256"] = dummy_sha
        value[f"c{component}_independent_replay_path"] = str(dummy_path)
        value[f"c{component}_independent_replay_sha256"] = dummy_sha
    return value


def fixture_legacy_selection(dummy_path: Path, dummy_sha: str) -> dict[str, Any]:
    poles = fixture_poles()
    pole_bodies = {
        (x, y)
        for anchor_x, anchor_y in (tuple(anchor) for anchor in poles)
        for x in range(anchor_x, anchor_x + 2)
        for y in range(anchor_y, anchor_y + 2)
    }
    protected = composer.rect((20, 20), 6, 7)
    available = [
        (x, y)
        for y in range(70)
        for x in range(70)
        if (x, y) not in pole_bodies | protected
    ]
    templates = ["manufacturing_3x3"] * 132 + ["manufacturing_5x5"] * 49 + ["manufacturing_6x4"] * 38
    components = [{"component": index, "origin": [0, 0], "selected": []} for index in range(17)]
    for pose_index, template in enumerate(templates):
        x, y = available[pose_index]
        components[pose_index % 17]["selected"].append(
            {
                "template": template,
                "mode": "north_to_south",
                "body": [[x, y]],
                "inputs": [[x, y]],
                "outputs": [[x, y]],
            }
        )
    return {
        "schema_version": "connected_bay_selection.v1",
        "status": contract.READY_STATUS,
        "claim_boundary": "Synthetic framework fixture only.",
        "baseline_head": contract.EXPECTED_HEAD,
        "source_artifacts": [{"path": str(dummy_path), "sha256": dummy_sha}],
        "pole_anchors": poles,
        "components": components,
    }


def expect_reject(name: str, action: Callable[[], object], expected_fragment: str) -> dict[str, str]:
    try:
        action()
    except Exception as exc:  # validation intentionally crosses three local exception types
        text = str(exc)
        require(expected_fragment in text, f"{name}: wrong rejection {text!r}")
        return {"name": name, "status": "REJECTED", "reason": text}
    raise ValidationError(f"{name}: mutation was accepted")


def main() -> int:
    run = fresh_run()
    dummy = run / "dummy_source.json"
    write_exclusive(dummy, {"schema_version": "framework_dummy.v1", "status": "DUMMY"})
    dummy_sha = sha256(dummy)
    bundle_value = fixture_bundle(dummy, dummy_sha)
    bundle_path = run / "geometry_bundle_fixture.json"
    write_exclusive(bundle_path, bundle_value)
    bundle_source = composer.legacy.load_pinned(bundle_path, sha256(bundle_path), "fixture bundle")
    geometry = composer.parse_geometry_bundle(bundle_source)
    legacy_selection = fixture_legacy_selection(dummy, dummy_sha)
    upgraded = composer.upgrade_selection(
        legacy_selection,
        geometry,
        inherited_sources=(composer.legacy.load_pinned(dummy, dummy_sha, "fixture source"),),
    )
    parsed = contract.parse_selection(
        upgraded,
        selection_parent=RECOVERY,
        source_root=RECOVERY,
        verify_sources=True,
    )
    require(parsed.pose_count == 219 and parsed.protected_rectangle == (20, 20, 6, 7), "positive parse drift")

    selection_negatives = []

    def reject_selection(name: str, mutate: Callable[[dict[str, Any]], None], fragment: str) -> None:
        candidate = deepcopy(upgraded)
        mutate(candidate)
        selection_negatives.append(
            expect_reject(
                name,
                lambda: contract.parse_selection(
                    candidate,
                    selection_parent=RECOVERY,
                    source_root=RECOVERY,
                    verify_sources=True,
                ),
                fragment,
            )
        )

    reject_selection("missing protected_rectangle", lambda row: row.pop("protected_rectangle"), "SCHEMA_FIELDS")
    reject_selection("extra root field", lambda row: row.__setitem__("unexpected", True), "SCHEMA_FIELDS")
    reject_selection("legacy schema with v2 field", lambda row: row.__setitem__("schema_version", "connected_bay_selection.v1"), "SCHEMA_VERSION")
    reject_selection("protected wrong shape", lambda row: row.__setitem__("protected_rectangle", [20, 20, 7, 6]), "PROTECTED_RECTANGLE")
    reject_selection("protected outside grid", lambda row: row.__setitem__("protected_rectangle", [69, 69, 6, 7]), "PROTECTED_RECTANGLE")
    reject_selection("duplicate pole", lambda row: row["pole_anchors"].__setitem__(1, row["pole_anchors"][0]), "POLE_COUNT")
    reject_selection("source hash mismatch", lambda row: row["source_artifacts"][0].__setitem__("sha256", "0" * 64), "SOURCE_HASH_MISMATCH")

    def overlap_protected(row: dict[str, Any]) -> None:
        row["components"][0]["selected"][0]["body"] = [[20, 20]]

    reject_selection("body overlaps protected", overlap_protected, "BODY_PROTECTED_OVERLAP")

    bundle_negatives = []

    def reject_bundle(name: str, mutate: Callable[[dict[str, Any]], None], fragment: str) -> None:
        candidate = deepcopy(bundle_value)
        mutate(candidate)
        path = run / f"negative_bundle_{len(bundle_negatives):02d}.json"
        write_exclusive(path, candidate)
        source = composer.legacy.load_pinned(path, sha256(path), name)
        bundle_negatives.append(expect_reject(name, lambda: composer.parse_geometry_bundle(source), fragment))

    reject_bundle("bundle bad schema", lambda row: row.__setitem__("schema_version", "routing_geometry_bundle.v1"), "geometry bundle schema")
    reject_bundle("bundle nonterminal status", lambda row: row.__setitem__("status", "UNKNOWN"), "geometry bundle status")
    reject_bundle("bundle missing required", lambda row: row.pop("protected_cells"), "missing fields")
    reject_bundle("bundle protected cell mismatch", lambda row: row["protected_cells"].pop(), "protected_cells mismatch")
    reject_bundle("bundle overlap mismatch", lambda row: row["protected_backbone_overlap_cells"].append([0, 0]), "protected backbone overlap mismatch")
    reject_bundle("bundle new forbidden mismatch", lambda row: row["protected_new_body_forbidden_cells"].pop(), "protected new body-forbidden mismatch")
    reject_bundle("bundle recursive hash mismatch", lambda row: row.__setitem__("c4_result_sha256", "0" * 64), "hash mismatch")

    report = {
        "schema_version": "connected_bay_selection_v2_framework_validation.v1",
        "status": "PASS",
        "classification": "research_schema_framework_validation_no_solver_no_router",
        "claim_boundary": "Synthetic schema and mutation checks only; no formal selection, geometry assembly, or routing conclusion.",
        "framework_sha256": {
            "contract": sha256(HERE / "connected_bay_selection_v2_contract.py"),
            "composer": sha256(HERE / "compose_connected_bay_selection_v2.py"),
            "validator": sha256(Path(__file__)),
        },
        "positive": {
            "schema_version": contract.SCHEMA_VERSION,
            "pose_count": parsed.pose_count,
            "template_counts": dict(parsed.template_counts),
            "pole_count": len(parsed.pole_anchors),
            "protected_rectangle": list(parsed.protected_rectangle),
            "source_count": parsed.source_count,
            "local_contract_reparse": True,
            "read_only_assembler_reparse": True,
        },
        "negative_cases": selection_negatives + bundle_negatives,
        "negative_count": len(selection_negatives) + len(bundle_negatives),
        "formal_selection_files_written": 0,
    }
    require(report["negative_count"] == 15, "negative case count")
    report_path = run / "framework_validation_report.json"
    write_exclusive(report_path, report)
    with (run / "SHA256SUMS").open("x", encoding="ascii", newline="\n") as handle:
        handle.write(f"{dummy_sha}  dummy_source.json\n")
        handle.write(f"{sha256(bundle_path)}  geometry_bundle_fixture.json\n")
        handle.write(f"{sha256(report_path)}  framework_validation_report.json\n")
    print(json.dumps({"status": "PASS", "run_dir": str(run), "report": str(report_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
