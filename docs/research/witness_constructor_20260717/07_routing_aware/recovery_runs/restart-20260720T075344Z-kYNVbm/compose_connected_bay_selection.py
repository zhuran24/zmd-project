#!/usr/bin/env python3
"""Compose one exact connected-bay handoff from hash-pinned research rows.

This script only normalizes and joins already terminal local-search artifacts.  It
does not run a solver or router.  A successful invocation writes into a fresh,
exclusive child directory below ``composed_selections`` and re-parses the result
with ``assemble_connected_bays.parse_selection`` before publishing it.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY_ROOT = (
    PROJECT_ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
ROUTING_ROOT = RECOVERY_ROOT.parents[1]
OUTPUT_ROOT = RECOVERY_ROOT / "composed_selections"
EXPECTED_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
EXPECTED_COUNTS = {
    "manufacturing_3x3": 132,
    "manufacturing_5x5": 49,
    "manufacturing_6x4": 38,
}
EXPECTED_POSES = 219
EXPECTED_POLES = 35
SHA_RE = re.compile(r"[0-9a-f]{64}")
PLAN_SCHEMA_RE = re.compile(r"connected_bay_count_closure_plan\.v[3-9][0-9]*")
TERMINAL_SUCCESS = frozenset({"OPTIMAL", "FEASIBLE"})
TEMPLATES = tuple(EXPECTED_COUNTS)


DEFAULT_PLAN = RECOVERY_ROOT / "count_closure_plan_20260720_v3.json"
DEFAULT_PLAN_SHA256 = "1c9d42b00221436518f8e3635828bdad6261d0a5b005714f8817eca6194499e5"

# These files are immutable inputs to the v3 count closure.  Hashes are checked
# before JSON decoding, and decoded objects are retained from those exact bytes.
PINNED_INPUTS: Mapping[Path, str] = {
    RECOVERY_ROOT / "big_bays/periodic_big_bay_selection.json": (
        "1f49da3e9cf6e6e84bad3d9f873606a94f83afeb928317cbdf80bf604b2d4746"
    ),
    RECOVERY_ROOT / "big_bays/independent_periodic_big_bay_replay.json": (
        "10cd2116e9aa3681f8433a461efa950cb7092fe7c3fc5414f703b3c80eba2eea"
    ),
    RECOVERY_ROOT / "fixed_bays/recovered_fast_bays_20260720.json": (
        "2f82e1bcec5012b892da1f9362245a3bfd5aa6af4a996fdfb01f367ec76b2a16"
    ),
    RECOVERY_ROOT / "fixed_bays/recovered_heavy_bays_20260720.json": (
        "89772be8144f051b7e8d7b7b6cad518d82d75f9ce99d7f7f57f95b0660bba48a"
    ),
    RECOVERY_ROOT / "fixed_bays/pure_m3_add1_medium_20260720.json": (
        "0556c9815cc474d528b18400882f0efefdf927b88d56a32084c1d4fff5cf4f59"
    ),
    RECOVERY_ROOT / "fixed_bays/final_unchanged_bays_20260720.json": (
        "cd6c99ddb64b1c505a1d1865817d935b0436ddaf0d7df2e3f7001b97723cd64a"
    ),
    RECOVERY_ROOT / "c5/c5_direct_winner_query.json": (
        "3f1e2641e748bc7c6f2d5ad6aaf45adca3d4d15cb31d368439cc27480fb90c66"
    ),
    RECOVERY_ROOT / "c5/independent_c5_direct_winner_replay_v2.json": (
        "e062e5af4ad6063f099e7282cf2bf015212c16a3c7b998960bb364220642ef35"
    ),
}

FIXED_QUERY_INPUTS = (
    RECOVERY_ROOT / "fixed_bays/recovered_fast_bays_20260720.json",
    RECOVERY_ROOT / "fixed_bays/recovered_heavy_bays_20260720.json",
    RECOVERY_ROOT / "fixed_bays/pure_m3_add1_medium_20260720.json",
    RECOVERY_ROOT / "fixed_bays/final_unchanged_bays_20260720.json",
)

Cell = tuple[int, int]
Target = tuple[int, int, int]


class ComposeError(RuntimeError):
    """Fail-closed composition rejection."""


@dataclass(frozen=True)
class PinnedJson:
    path: Path
    sha256: str
    value: Mapping[str, Any]


@dataclass(frozen=True)
class Row:
    component: int
    origin: Cell
    target: Target
    selected: tuple[dict[str, Any], ...]
    source: PinnedJson
    coordinates: str


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ComposeError(message)


def mapping(value: object, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{label}: expected object")
    return value


def sequence(value: object, label: str) -> Sequence[Any]:
    require(isinstance(value, Sequence) and not isinstance(value, (str, bytes)), f"{label}: expected array")
    return value


def integer(value: object, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{label}: expected integer")
    return value


def cell(value: object, label: str) -> Cell:
    raw = sequence(value, label)
    require(len(raw) == 2, f"{label}: expected two coordinates")
    return integer(raw[0], f"{label}[0]"), integer(raw[1], f"{label}[1]")


def target(value: object, label: str) -> Target:
    raw = sequence(value, label)
    require(len(raw) == len(TEMPLATES), f"{label}: expected three counts")
    parsed = tuple(integer(item, f"{label}[{index}]") for index, item in enumerate(raw))
    require(all(item >= 0 for item in parsed), f"{label}: negative count")
    return parsed  # type: ignore[return-value]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def regular_non_symlink(path: Path, label: str) -> Path:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ComposeError(f"{label}: unavailable: {exc}") from exc
    require(stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode), f"{label}: bad file type")
    resolved = path.resolve(strict=True)
    require(resolved.is_relative_to(RECOVERY_ROOT), f"{label}: must remain below recovery root")
    return resolved


def load_pinned(path: Path, expected_sha256: str, label: str) -> PinnedJson:
    require(SHA_RE.fullmatch(expected_sha256) is not None, f"{label}: malformed expected sha256")
    resolved = regular_non_symlink(path, label)
    try:
        payload = resolved.read_bytes()
    except OSError as exc:
        raise ComposeError(f"{label}: read failed: {exc}") from exc
    observed = sha256_bytes(payload)
    require(observed == expected_sha256, f"{label}: hash mismatch expected={expected_sha256} observed={observed}")
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComposeError(f"{label}: invalid JSON: {exc}") from exc
    return PinnedJson(resolved, observed, mapping(decoded, label))


def parse_path_sha(value: str, label: str) -> tuple[Path, str]:
    raw_path, separator, digest = value.rpartition("=")
    require(bool(separator and raw_path), f"{label}: expected PATH=SHA256")
    require(SHA_RE.fullmatch(digest) is not None, f"{label}: malformed sha256")
    path = Path(raw_path)
    if not path.is_absolute():
        path = RECOVERY_ROOT / path
    return path, digest


def strip_pose(raw: object, *, origin: Cell, coordinates: str, label: str) -> dict[str, Any]:
    row = mapping(raw, label)
    template_name = row.get("template")
    mode = row.get("mode")
    require(template_name in TEMPLATES, f"{label}.template: unsupported value")
    require(isinstance(mode, str) and mode, f"{label}.mode: expected non-empty string")

    def normalize(field: str) -> list[list[int]]:
        parsed = [cell(item, f"{label}.{field}[{index}]") for index, item in enumerate(sequence(row.get(field), f"{label}.{field}"))]
        require(parsed and len(parsed) == len(set(parsed)), f"{label}.{field}: empty or duplicate cells")
        if coordinates == "global":
            parsed = [(x - origin[0], y - origin[1]) for x, y in parsed]
        elif coordinates != "local":
            raise ComposeError(f"{label}: unsupported coordinate convention {coordinates!r}")
        return [[x, y] for x, y in parsed]

    return {
        "template": template_name,
        "mode": mode,
        "body": normalize("body"),
        "inputs": normalize("inputs"),
        "outputs": normalize("outputs"),
    }


def validate_selected_count(selected: Sequence[Mapping[str, Any]], expected: Target, label: str) -> None:
    observed = Counter(str(row["template"]) for row in selected)
    wanted = Counter(dict(zip(TEMPLATES, expected, strict=True)))
    require(observed == wanted, f"{label}: target mismatch expected={dict(wanted)!r} observed={dict(observed)!r}")


def fixed_rows(source: PinnedJson) -> tuple[Row, ...]:
    rows: list[Row] = []
    for index, raw in enumerate(sequence(source.value.get("queries"), f"{source.path}.queries")):
        query = mapping(raw, f"{source.path}.queries[{index}]")
        if query.get("status") not in TERMINAL_SUCCESS:
            continue
        component = integer(query.get("component"), f"{source.path}.queries[{index}].component")
        origin = cell(query.get("origin"), f"{source.path}.queries[{index}].origin")
        expected = target(query.get("target"), f"{source.path}.queries[{index}].target")
        residual = integer(query.get("residual_cells"), f"{source.path}.queries[{index}].residual_cells")
        residual_main = integer(query.get("residual_main_cells"), f"{source.path}.queries[{index}].residual_main_cells")
        # A terminal local body solve can still leave a disconnected residual
        # pocket.  Such a row is valid history but is not an eligible connected
        # handoff row; omit it and let exact target selection fail if needed.
        if residual <= 0 or residual != residual_main:
            continue
        selected = tuple(
            strip_pose(pose, origin=origin, coordinates="local", label=f"{source.path}.queries[{index}].selected[{pose_index}]")
            for pose_index, pose in enumerate(sequence(query.get("selected"), f"{source.path}.queries[{index}].selected"))
        )
        validate_selected_count(selected, expected, f"{source.path}.queries[{index}]")
        rows.append(Row(component, origin, expected, selected, source, "local"))
    return tuple(rows)


def parse_plan(source: PinnedJson) -> tuple[dict[int, Target], tuple[Cell, ...]]:
    plan = source.value
    schema = plan.get("schema_version")
    require(isinstance(schema, str) and PLAN_SCHEMA_RE.fullmatch(schema) is not None, "plan: unsupported schema")
    require(plan.get("status") == "SEARCH_PLAN_ONLY", "plan: bad status")
    require(target(plan.get("global_target"), "plan.global_target") == (132, 49, 38), "plan: global target drift")

    big = mapping(plan.get("big_bay_target"), "plan.big_bay_target")
    components = tuple(integer(item, f"plan.big_bay_target.components[{index}]") for index, item in enumerate(sequence(big.get("components"), "plan.big_bay_target.components")))
    require(components == (0, 1, 2), "plan: big component order drift")
    named_rows = mapping(big.get("rows"), "plan.big_bay_target.rows")
    require(set(named_rows) == {"F", "G", "H"}, "plan: expected F/G/H big rows")
    targets: dict[int, Target] = {
        component: target(named_rows[label], f"plan.big_bay_target.rows.{label}")
        for component, label in zip(components, ("F", "G", "H"), strict=True)
    }
    expected_big_subtotal = tuple(sum(targets[c][index] for c in components) for index in range(3))
    require(target(big.get("subtotal"), "plan.big_bay_target.subtotal") == expected_big_subtotal, "plan: big subtotal drift")

    non_big = mapping(plan.get("non_big_component_targets"), "plan.non_big_component_targets")
    require(set(non_big) == {str(component) for component in range(3, 17)}, "plan: non-big component ids drift")
    for component in range(3, 17):
        targets[component] = target(non_big[str(component)], f"plan.non_big_component_targets.{component}")
    totals = tuple(sum(row[index] for row in targets.values()) for index in range(3))
    require(totals == (132, 49, 38), f"plan: component total drift {totals!r}")

    moves = mapping(plan.get("required_final_pole_moves"), "plan.required_final_pole_moves")
    removed = {cell(item, f"plan.required_final_pole_moves.remove[{index}]") for index, item in enumerate(sequence(moves.get("remove"), "plan.required_final_pole_moves.remove"))}
    added = {cell(item, f"plan.required_final_pole_moves.add[{index}]") for index, item in enumerate(sequence(moves.get("add"), "plan.required_final_pole_moves.add"))}
    require(len(removed) == len(added) == 12 and not removed & added, "plan: pole move set drift")
    baseline = {(x, y) for x in (5, 17, 29, 41, 53, 65) for y in (5, 17, 29, 41, 53, 65)} - {(65, 65)}
    require(removed <= baseline and not added & baseline, "plan: invalid pole move endpoints")
    poles = (baseline - removed) | added
    require(integer(moves.get("expected_unique_poles"), "plan.required_final_pole_moves.expected_unique_poles") == EXPECTED_POLES, "plan: pole count contract drift")
    require(len(poles) == EXPECTED_POLES, "plan: final poles are not unique")
    return targets, tuple(sorted(poles, key=lambda item: (item[1], item[0])))


def periodic_f_row(selection: PinnedJson, replay: PinnedJson, expected: Target) -> Row:
    require(selection.value.get("status") == "THREE_PERIODIC_BIG_BAYS_REPLAYED", "periodic F: bad selection status")
    require(replay.value.get("status") == "PASS", "periodic F: independent replay did not pass")
    require(replay.value.get("selection_sha256") == selection.sha256, "periodic F: replay selection hash mismatch")
    checks = mapping(replay.value.get("checks"), "periodic F replay.checks")
    require(checks and all(value is True for value in checks.values()), "periodic F: replay check false")
    bays = mapping(selection.value.get("bays"), "periodic F.bays")
    bay = mapping(bays.get("c0"), "periodic F.bays.c0")
    origin = cell(bay.get("origin"), "periodic F.bays.c0.origin")
    observed_target = target(bay.get("target"), "periodic F.bays.c0.target")
    require(observed_target == expected, f"periodic F: target drift {observed_target!r}")
    require(bay.get("all_residual_connected") is True, "periodic F: residual disconnected")
    require(integer(bay.get("residual_cells"), "periodic F residual") == integer(bay.get("residual_reachable_cells"), "periodic F reachable"), "periodic F: residual count mismatch")
    selected = tuple(
        strip_pose(pose, origin=origin, coordinates="global", label=f"periodic F.selected[{index}]")
        for index, pose in enumerate(sequence(bay.get("selected"), "periodic F.selected"))
    )
    validate_selected_count(selected, expected, "periodic F")
    return Row(0, origin, expected, selected, selection, "global")


def direct_big_row(source: PinnedJson, replay: PinnedJson, component: int, expected: Target, label: str) -> Row:
    row = source.value
    require(row.get("status") in TERMINAL_SUCCESS, f"big {label}: source not feasible")
    observed_target = target(row.get("target"), f"big {label}.target")
    require(observed_target == expected, f"big {label}: target drift {observed_target!r}")
    source_component = integer(row.get("component"), f"big {label}.component")
    require(source_component == 0, f"big {label}: expected normalized c0 source")
    source_origin = cell(row.get("origin"), f"big {label}.origin")
    require(source_origin == (13, 2), f"big {label}: c0 origin drift")
    require(row.get("all_residual_connected") is True, f"big {label}: residual disconnected")
    require(integer(row.get("residual_cells"), f"big {label}.residual_cells") == integer(row.get("residual_main_cells"), f"big {label}.residual_main_cells"), f"big {label}: residual count mismatch")

    replay_value = replay.value
    require(replay_value.get("status") in {"PASS", "BIG_BAY_ROW_INDEPENDENTLY_VERIFIED"}, f"big {label}: replay status did not pass")
    replay_hashes = replay_value.get("input_sha256")
    require(isinstance(replay_hashes, Mapping) and source.sha256 in replay_hashes.values(), f"big {label}: replay does not pin source")
    replay_target = replay_value.get("target")
    if replay_target is None and isinstance(replay_value.get("row"), Mapping):
        replay_target = mapping(replay_value["row"], f"big {label}.replay.row").get("target")
    if replay_target is not None:
        require(target(replay_target, f"big {label}.replay.target") == expected, f"big {label}: replay target drift")
    checks = replay_value.get("checks")
    if checks is not None:
        check_map = mapping(checks, f"big {label}.replay.checks")
        require(check_map and all(value is True for value in check_map.values()), f"big {label}: replay check false")

    selected = tuple(
        strip_pose(pose, origin=source_origin, coordinates="global", label=f"big {label}.selected[{index}]")
        for index, pose in enumerate(sequence(row.get("selected"), f"big {label}.selected"))
    )
    validate_selected_count(selected, expected, f"big {label}")
    final_origin = ((13, 2), (25, 2), (37, 2))[component]
    return Row(component, final_origin, expected, selected, source, "global-normalized-c0")


def c5_row(query_source: PinnedJson, replay_source: PinnedJson, expected: Target) -> Row:
    require(query_source.value.get("status") == "C5_DIRECT_QUERY_FEASIBLE", "c5: wrapper status drift")
    query = mapping(query_source.value.get("query"), "c5.query")
    require(query.get("status") in TERMINAL_SUCCESS, "c5: query not feasible")
    observed_target = target(query.get("target"), "c5.query.target")
    require(observed_target == expected, f"c5: target drift {observed_target!r}")
    origin = cell(query.get("c5_origin"), "c5.query.c5_origin")
    require(origin == (60, 2), "c5: origin drift")
    require(query.get("all_residual_connected") is True, "c5: residual disconnected")
    require(integer(query.get("residual_cells"), "c5.query.residual_cells") == integer(query.get("residual_main_cells"), "c5.query.residual_main_cells"), "c5: residual count mismatch")

    replay = replay_source.value
    require(replay.get("status") == "C5_POLE_PHASE_WINNER_INDEPENDENTLY_VERIFIED", "c5: replay status drift")
    replay_hashes = mapping(replay.get("input_sha256"), "c5.replay.input_sha256")
    require(query_source.sha256 in replay_hashes.values(), "c5: replay does not pin query")
    winner = mapping(replay.get("winner"), "c5.replay.winner")
    require(target(winner.get("target"), "c5.replay.winner.target") == expected, "c5: replay target drift")
    require(winner.get("all_residual_connected") is True and winner.get("all_weak_active_connected") is True, "c5: replay connectivity false")
    require(integer(winner.get("body_overlap_count"), "c5.replay.winner.body_overlap_count") == 0, "c5: replay body overlap")
    require(integer(winner.get("pole_count"), "c5.replay.winner.pole_count") == EXPECTED_POLES, "c5: replay pole count drift")

    selected = tuple(
        strip_pose(pose, origin=origin, coordinates="global", label=f"c5.query.selected[{index}]")
        for index, pose in enumerate(sequence(query.get("selected"), "c5.query.selected"))
    )
    validate_selected_count(selected, expected, "c5")
    return Row(5, origin, expected, selected, query_source, "global")


def repository_head() -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ComposeError(f"cannot read repository head: {exc}") from exc
    observed = completed.stdout.strip()
    require(observed == EXPECTED_HEAD, f"repository head drift expected={EXPECTED_HEAD} observed={observed}")
    return observed


def choose_fixed_rows(catalog: Sequence[Row], targets: Mapping[int, Target]) -> dict[int, Row]:
    result: dict[int, Row] = {}
    for component in range(3, 17):
        if component == 5:
            continue
        matching = [row for row in catalog if row.component == component and row.target == targets[component]]
        require(len(matching) == 1, f"component {component}: expected one feasible source for {targets[component]!r}, observed {len(matching)}")
        result[component] = matching[0]
    return result


def source_artifacts(sources: Sequence[PinnedJson]) -> list[dict[str, str]]:
    unique: dict[Path, PinnedJson] = {}
    for source in sources:
        previous = unique.setdefault(source.path, source)
        require(previous.sha256 == source.sha256, f"source hash conflict: {source.path}")
    return [
        {"path": str(path), "sha256": unique[path].sha256}
        for path in sorted(unique, key=str)
    ]


def fresh_run_directory() -> Path:
    OUTPUT_ROOT.mkdir(mode=0o755, parents=False, exist_ok=True)
    for _attempt in range(16):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        candidate = OUTPUT_ROOT / f"selection-{stamp}-{secrets.token_hex(3)}"
        try:
            candidate.mkdir(mode=0o755, parents=False, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise ComposeError("could not allocate unique output directory")


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    except OSError as exc:
        raise ComposeError(f"exclusive write failed for {path}: {exc}") from exc


def compose(
    *,
    plan_source: PinnedJson,
    pinned_inputs: Mapping[Path, PinnedJson],
    g_source: PinnedJson,
    g_replay: PinnedJson,
    h_source: PinnedJson,
    h_replay: PinnedJson,
) -> tuple[dict[str, Any], dict[str, Any]]:
    targets, poles = parse_plan(plan_source)
    periodic = pinned_inputs[RECOVERY_ROOT / "big_bays/periodic_big_bay_selection.json"]
    periodic_replay = pinned_inputs[RECOVERY_ROOT / "big_bays/independent_periodic_big_bay_replay.json"]
    rows: dict[int, Row] = {
        0: periodic_f_row(periodic, periodic_replay, targets[0]),
        1: direct_big_row(g_source, g_replay, 1, targets[1], "G"),
        2: direct_big_row(h_source, h_replay, 2, targets[2], "H"),
    }

    fixed_catalog = tuple(
        row
        for path in FIXED_QUERY_INPUTS
        for row in fixed_rows(pinned_inputs[path])
    )
    rows.update(choose_fixed_rows(fixed_catalog, targets))
    rows[5] = c5_row(
        pinned_inputs[RECOVERY_ROOT / "c5/c5_direct_winner_query.json"],
        pinned_inputs[RECOVERY_ROOT / "c5/independent_c5_direct_winner_replay_v2.json"],
        targets[5],
    )
    require(set(rows) == set(range(17)), f"component coverage drift: {sorted(rows)!r}")
    for component, row in rows.items():
        require(row.component == component and row.target == targets[component], f"component {component}: selected row drift")

    counts = Counter(pose["template"] for row in rows.values() for pose in row.selected)
    require(dict(counts) == EXPECTED_COUNTS, f"aggregate template count drift {dict(counts)!r}")
    pose_count = sum(len(row.selected) for row in rows.values())
    require(pose_count == EXPECTED_POSES, f"aggregate pose count drift {pose_count}")

    all_sources = [
        plan_source,
        *pinned_inputs.values(),
        g_source,
        g_replay,
        h_source,
        h_replay,
    ]
    selection = {
        "schema_version": "connected_bay_selection.v1",
        "status": "CONNECTED_BAY_SELECTION_READY",
        "claim_boundary": (
            "Research construction handoff only. This is not proof material, makes no optimality claim, "
            "and has no routing or six-predicate acceptance conclusion until downstream independent checks pass."
        ),
        "baseline_head": repository_head(),
        "source_artifacts": source_artifacts(all_sources),
        "pole_anchors": [[x, y] for x, y in poles],
        "components": [
            {
                "component": component,
                "origin": [rows[component].origin[0], rows[component].origin[1]],
                "selected": list(rows[component].selected),
            }
            for component in range(17)
        ],
    }

    sys.path.insert(0, str(ROUTING_ROOT))
    try:
        import assemble_connected_bays as assembler
    finally:
        sys.path.pop(0)
    parsed = assembler.parse_selection(
        selection,
        selection_parent=RECOVERY_ROOT,
        verify_source_artifacts=True,
    )
    require(len(parsed.components) == 17, "assembler parser component count drift")
    require(sum(len(component.selected) for component in parsed.components) == EXPECTED_POSES, "assembler parser pose count drift")

    report = {
        "schema_version": "connected_bay_selection_composition_report.v1",
        "status": "SELECTION_COMPOSED_AND_REPARSED",
        "claim_boundary": "Composition and exact-schema reparse only; no geometry assembly or routing conclusion.",
        "baseline_head": EXPECTED_HEAD,
        "plan_path": str(plan_source.path),
        "plan_sha256": plan_source.sha256,
        "template_counts": dict(sorted(counts.items())),
        "manufacturing_poses": pose_count,
        "pole_count": len(poles),
        "component_rows": {
            str(component): {
                "origin": list(rows[component].origin),
                "target": list(rows[component].target),
                "source_path": str(rows[component].source.path),
                "source_sha256": rows[component].source.sha256,
                "source_coordinates": rows[component].coordinates,
            }
            for component in range(17)
        },
    }
    return selection, report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--plan-sha256", default=DEFAULT_PLAN_SHA256)
    parser.add_argument("--big-g", required=True, help="G direct c0 query as PATH=SHA256")
    parser.add_argument("--big-g-replay", required=True, help="G independent replay as PATH=SHA256")
    parser.add_argument("--big-h", required=True, help="H direct c0 query as PATH=SHA256")
    parser.add_argument("--big-h-replay", required=True, help="H independent replay as PATH=SHA256")
    args = parser.parse_args(argv)

    try:
        plan_path = args.plan if args.plan.is_absolute() else RECOVERY_ROOT / args.plan
        plan_source = load_pinned(plan_path, args.plan_sha256, "plan")
        pinned_inputs = {
            path: load_pinned(path, digest, f"pinned input {path.name}")
            for path, digest in PINNED_INPUTS.items()
        }
        dynamic: dict[str, PinnedJson] = {}
        for label, raw in (
            ("big G", args.big_g),
            ("big G replay", args.big_g_replay),
            ("big H", args.big_h),
            ("big H replay", args.big_h_replay),
        ):
            path, digest = parse_path_sha(raw, label)
            dynamic[label] = load_pinned(path, digest, label)
        selection, report = compose(
            plan_source=plan_source,
            pinned_inputs=pinned_inputs,
            g_source=dynamic["big G"],
            g_replay=dynamic["big G replay"],
            h_source=dynamic["big H"],
            h_replay=dynamic["big H replay"],
        )

        run_dir = fresh_run_directory()
        selection_path = run_dir / "connected_bay_selection.json"
        report_path = run_dir / "composition_report.json"
        write_json_exclusive(selection_path, selection)
        selection_sha = sha256_bytes(selection_path.read_bytes())
        report = dict(report)
        report.update({"selection_path": str(selection_path), "selection_sha256": selection_sha})
        write_json_exclusive(report_path, report)
        with (run_dir / "SHA256SUMS").open("x", encoding="ascii", newline="\n") as handle:
            handle.write(f"{selection_sha}  connected_bay_selection.json\n")
            handle.write(f"{sha256_bytes(report_path.read_bytes())}  composition_report.json\n")
        print(
            json.dumps(
                {
                    "status": "SELECTION_COMPOSED_AND_REPARSED",
                    "run_dir": str(run_dir),
                    "selection_path": str(selection_path),
                    "selection_sha256": selection_sha,
                    "report_path": str(report_path),
                },
                sort_keys=True,
            )
        )
        return 0
    except ComposeError as exc:
        print(json.dumps({"status": "COMPOSITION_REJECTED", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
