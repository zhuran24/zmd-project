#!/usr/bin/env python3
"""Static validator for IndustrialPlanner v2 blueprint JSON files.

Validates:
  - Connectivity: every port (machine input/output, belt I/O) is wired to
    something or explicitly an endpoint.
  - Direction: belt output points to a downstream input edge.
  - Item type flow: starting from unloaders / hub outputs, propagate the
    itemId through the belt network and check each processor's input ports
    receive items that any of its recipes accepts.

Does NOT simulate tick-by-tick. This is a static check — runs in seconds
even for 1000+ device blueprints.

Usage:
  python3 scripts/ip_v2_blueprint_validator.py <blueprint.json> [--spec <ip_v2_device_specs.json>]

The spec JSON is produced by .upstream_clones/industrial_planner_v2/.temp/dump_device_specs.mjs
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

DEFAULT_SPEC_PATH = str(Path(tempfile.gettempdir()) / "ip_v2_device_specs.json")

# Match IP v2 geometry.ts
EDGE_DELTA: Dict[str, Tuple[int, int]] = {
    "N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0),
}
OPPOSITE_EDGE: Dict[str, str] = {"N": "S", "S": "N", "W": "E", "E": "W"}
EDGE_ORDER = ["N", "E", "S", "W"]


def rotate_point(x: int, y: int, w: int, h: int, rot: int) -> Tuple[int, int]:
    rot = int(rot) % 360
    if rot == 0:
        return (x, y)
    if rot == 90:
        return (h - 1 - y, x)
    if rot == 180:
        return (w - 1 - x, h - 1 - y)
    if rot == 270:
        return (y, w - 1 - x)
    raise ValueError(f"unsupported rotation {rot}")


def rotate_edge(edge: str, rot: int) -> str:
    steps = (int(rot) // 90) % 4
    return EDGE_ORDER[(EDGE_ORDER.index(edge) + steps) % 4]


# Per-port info after world-space resolution
class WorldPort(dict):
    """Keys: world_cell, edge, direction, port_id, allowed_items,
    allowed_types, device_idx, device_typeId."""
    pass


def resolve_world_ports(
    device: Dict[str, Any], device_idx: int, device_types: Dict[str, Any]
) -> List[WorldPort]:
    typeId = device["typeId"]
    spec = device_types.get(typeId)
    if not spec:
        return []
    size = spec.get("size", {})
    w = int(size.get("width", 1))
    h = int(size.get("height", 1))
    rot = int(device.get("rotation", 0))
    ox = int(device["origin"]["x"])
    oy = int(device["origin"]["y"])
    out: List[WorldPort] = []
    for p in spec.get("ports0", []) or []:
        rx, ry = rotate_point(
            int(p["localCellX"]), int(p["localCellY"]), w, h, rot
        )
        wedge = rotate_edge(p["edge"], rot)
        wp = WorldPort()
        wp["world_cell"] = (ox + rx, oy + ry)
        wp["edge"] = wedge
        wp["direction"] = p["direction"]
        wp["port_id"] = p["id"]
        wp["allowed_items"] = p.get("allowedItems", {})
        wp["allowed_types"] = p.get("allowedTypes", {})
        wp["device_idx"] = device_idx
        wp["device_typeId"] = typeId
        out.append(wp)
    return out


def device_occupied_cells(
    device: Dict[str, Any], device_types: Dict[str, Any]
) -> Set[Tuple[int, int]]:
    typeId = device["typeId"]
    spec = device_types.get(typeId, {})
    size = spec.get("size", {})
    w = int(size.get("width", 1))
    h = int(size.get("height", 1))
    rot = int(device.get("rotation", 0))
    ox = int(device["origin"]["x"])
    oy = int(device["origin"]["y"])
    out: Set[Tuple[int, int]] = set()
    for lx in range(w):
        for ly in range(h):
            rx, ry = rotate_point(lx, ly, w, h, rot)
            out.add((ox + rx, oy + ry))
    return out


def build_recipe_indices(recipes: List[Dict[str, Any]]) -> Tuple[
    Dict[str, Set[str]], Dict[str, Set[str]]
]:
    """Returns (input_items_by_machine, output_items_by_machine)."""
    inputs = defaultdict(set)
    outputs = defaultdict(set)
    for r in recipes:
        mt = r["machineType"]
        for inp in r.get("inputs", []) or []:
            inputs[mt].add(inp["itemId"])
        for out in r.get("outputs", []) or []:
            outputs[mt].add(out["itemId"])
    return dict(inputs), dict(outputs)


def port_allowed_items(
    port: WorldPort,
    recipe_inputs_by_machine: Dict[str, Set[str]],
    recipe_outputs_by_machine: Dict[str, Set[str]],
    all_recipe_items: Set[str],
) -> Optional[Set[str]]:
    """Return the set of itemIds this port accepts, or None for 'any'."""
    allowed = port.get("allowed_items", {})
    mode = allowed.get("mode", "any")
    if mode == "any":
        return None
    if mode == "recipe_inputs":
        return recipe_inputs_by_machine.get(port["device_typeId"], set())
    if mode == "recipe_outputs":
        return recipe_outputs_by_machine.get(port["device_typeId"], set())
    if mode == "recipe_items":
        return all_recipe_items
    if mode == "whitelist":
        return set(allowed.get("whitelist", []))
    return None  # unknown → conservative: any


# --- Connection graph -----------------------------------------------------

class Connection(dict):
    """Keys: src_device_idx, src_port_id, src_cell, src_edge,
    dst_device_idx, dst_port_id, dst_cell, dst_edge."""
    pass


def build_connections(
    devices: List[Dict[str, Any]],
    device_types: Dict[str, Any],
) -> Tuple[List[Connection], List[WorldPort], Dict[int, List[WorldPort]]]:
    """Resolve all world ports, match outputs to inputs across the (cell, edge)
    boundary. Returns (connections, all_ports, ports_by_device_idx)."""
    all_ports: List[WorldPort] = []
    ports_by_device: Dict[int, List[WorldPort]] = defaultdict(list)
    for di, dev in enumerate(devices):
        ps = resolve_world_ports(dev, di, device_types)
        all_ports.extend(ps)
        ports_by_device[di].extend(ps)

    input_index: Dict[Tuple[Tuple[int, int], str], List[WorldPort]] = defaultdict(list)
    for p in all_ports:
        if p["direction"] == "Input":
            input_index[(p["world_cell"], p["edge"])].append(p)

    connections: List[Connection] = []
    for p in all_ports:
        if p["direction"] != "Output":
            continue
        cx, cy = p["world_cell"]
        dx, dy = EDGE_DELTA[p["edge"]]
        target_cell = (cx + dx, cy + dy)
        target_edge = OPPOSITE_EDGE[p["edge"]]
        matches = input_index.get((target_cell, target_edge), [])
        for q in matches:
            conn = Connection()
            conn["src_device_idx"] = p["device_idx"]
            conn["src_port_id"] = p["port_id"]
            conn["src_cell"] = p["world_cell"]
            conn["src_edge"] = p["edge"]
            conn["dst_device_idx"] = q["device_idx"]
            conn["dst_port_id"] = q["port_id"]
            conn["dst_cell"] = q["world_cell"]
            conn["dst_edge"] = q["edge"]
            connections.append(conn)
    return connections, all_ports, dict(ports_by_device)


# --- Item type flow propagation ------------------------------------------

def propagate_item_flow(
    devices: List[Dict[str, Any]],
    device_types: Dict[str, Any],
    connections: List[Connection],
    recipes: List[Dict[str, Any]],
    port_inputs_out: Optional[Dict[Tuple[int, str], Set[str]]] = None,
) -> Dict[int, Set[str]]:
    """BFS itemId through the network.

    Source seeds: unloader.pickupItemId, protocol hub config.protocolHubOutputs.
    Passthrough (belt/splitter/converger/connector/storage_box): forward item
    unchanged to all downstream connections.
    Processor: record item as received input. Then check which recipes become
    'satisfiable' (all input items now present). For each satisfied recipe,
    inject its output items downstream from this device's output ports.

    Returns map device_idx → set of itemIds received at its inputs.
    """
    out_conns_by_device: Dict[int, List[Connection]] = defaultdict(list)
    for c in connections:
        out_conns_by_device[c["src_device_idx"]].append(c)
    # incoming connections by (dst_device_idx, dst_port_id)
    in_conns_by_port: Dict[Tuple[int, str], List[Connection]] = defaultdict(list)
    for c in connections:
        in_conns_by_port[(c["dst_device_idx"], c["dst_port_id"])].append(c)

    # group recipes by machine type
    recipes_by_machine: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in recipes:
        recipes_by_machine[r["machineType"]].append(r)

    inputs_received: Dict[int, Set[str]] = defaultdict(set)
    outputs_emitted: Dict[int, Set[str]] = defaultdict(set)

    PASSTHROUGH = {
        "belt_straight_1x1", "belt_turn_cw_1x1", "belt_turn_ccw_1x1",
        "item_log_splitter", "item_log_converger", "item_log_connector",
        # storage_box is a buffer — pass through
        "item_port_storager_1",
    }
    SOURCE = {"item_port_unloader_1", "item_port_sp_hub_1"}

    # queue items: (dst_device_idx, dst_port_id_or_None, itemId)
    queue: deque[Tuple[int, Optional[str], str]] = deque()

    def enqueue_downstream(src_di: int, itemId: str) -> None:
        for c in out_conns_by_device.get(src_di, []):
            queue.append((c["dst_device_idx"], c["dst_port_id"], itemId))

    # Seed sources
    for di, dev in enumerate(devices):
        typeId = dev["typeId"]
        cfg = dev.get("config", {}) or {}
        if typeId == "item_port_unloader_1":
            pick = cfg.get("pickupItemId")
            if pick:
                outputs_emitted[di].add(pick)
                enqueue_downstream(di, pick)
        elif typeId == "item_port_sp_hub_1":
            for entry in cfg.get("protocolHubOutputs", []) or []:
                itemId = entry.get("itemId")
                if itemId:
                    outputs_emitted[di].add(itemId)
                    enqueue_downstream(di, itemId)
        for pre in cfg.get("preloadInputs", []) or []:
            itemId = pre.get("itemId")
            if itemId:
                queue.append((di, None, itemId))

    while queue:
        di, dst_port_id, item = queue.popleft()
        typeId = devices[di]["typeId"]

        if port_inputs_out is not None and dst_port_id is not None:
            port_inputs_out.setdefault((di, dst_port_id), set()).add(item)

        if typeId in PASSTHROUGH:
            if item in outputs_emitted[di]:
                continue
            outputs_emitted[di].add(item)
            enqueue_downstream(di, item)
            continue

        if typeId in SOURCE:
            continue

        if item in inputs_received[di]:
            continue
        inputs_received[di].add(item)
        machine_recipes = recipes_by_machine.get(typeId, [])
        for r in machine_recipes:
            need = {inp["itemId"] for inp in r.get("inputs", []) or []}
            if need and need.issubset(inputs_received[di]):
                for outent in r.get("outputs", []) or []:
                    oitem = outent["itemId"]
                    if oitem in outputs_emitted[di]:
                        continue
                    outputs_emitted[di].add(oitem)
                    enqueue_downstream(di, oitem)

    return dict(inputs_received)


# --- Validation reports --------------------------------------------------

def validate(
    devices: List[Dict[str, Any]],
    device_types: Dict[str, Any],
    recipes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    connections, all_ports, ports_by_device = build_connections(devices, device_types)

    # connected port set
    connected_outputs: Set[Tuple[int, str]] = {
        (c["src_device_idx"], c["src_port_id"]) for c in connections
    }
    connected_inputs: Set[Tuple[int, str]] = {
        (c["dst_device_idx"], c["dst_port_id"]) for c in connections
    }

    issues = {
        "isolated_devices": [],
        "machine_input_unconnected": [],
        "machine_output_unconnected": [],
        "belt_orphan_input": [],
        "belt_orphan_output": [],
        "type_mismatch_at_machine_input": [],
        "unloader_missing_pickupItemId": [],
    }

    processor_types = {tid for tid, d in device_types.items() if d.get("runtimeKind") == "processor"}
    storage_types = {tid for tid, d in device_types.items() if d.get("runtimeKind") == "storage"}
    conveyor_types = {tid for tid, d in device_types.items() if d.get("runtimeKind") == "conveyor"}
    junction_types = {tid for tid, d in device_types.items() if d.get("runtimeKind") == "junction"}

    recipe_inputs_by_machine, recipe_outputs_by_machine = build_recipe_indices(recipes)

    port_inputs: Dict[Tuple[int, str], Set[str]] = {}
    inputs_received = propagate_item_flow(
        devices, device_types, connections, recipes,
        port_inputs_out=port_inputs,
    )

    for di, dev in enumerate(devices):
        typeId = dev["typeId"]
        ports = ports_by_device.get(di, [])
        port_ids = {p["port_id"] for p in ports}

        # unloader must have pickupItemId
        if typeId == "item_port_unloader_1":
            cfg = dev.get("config", {}) or {}
            if not cfg.get("pickupItemId"):
                issues["unloader_missing_pickupItemId"].append({
                    "device_idx": di,
                    "origin": dev.get("origin"),
                })

        # processor unconnected ports
        if typeId in processor_types:
            has_input_ports = any(p["direction"] == "Input" for p in ports)
            has_output_ports = any(p["direction"] == "Output" for p in ports)
            has_any_input_connected = any(
                p["direction"] == "Input" and (di, p["port_id"]) in connected_inputs
                for p in ports
            )
            has_any_output_connected = any(
                p["direction"] == "Output" and (di, p["port_id"]) in connected_outputs
                for p in ports
            )
            if has_input_ports and not has_any_input_connected:
                issues["machine_input_unconnected"].append({
                    "device_idx": di, "typeId": typeId,
                    "origin": dev.get("origin"), "rotation": dev.get("rotation"),
                })
            if has_output_ports and not has_any_output_connected:
                issues["machine_output_unconnected"].append({
                    "device_idx": di, "typeId": typeId,
                    "origin": dev.get("origin"), "rotation": dev.get("rotation"),
                })

        # conveyor belt: each port must connect (it's the whole point)
        if typeId in conveyor_types:
            for p in ports:
                if p["direction"] == "Input":
                    if (di, p["port_id"]) not in connected_inputs:
                        issues["belt_orphan_input"].append({
                            "device_idx": di, "typeId": typeId,
                            "origin": dev.get("origin"), "rotation": dev.get("rotation"),
                            "port_id": p["port_id"],
                            "world_cell": p["world_cell"], "edge": p["edge"],
                        })
                else:
                    if (di, p["port_id"]) not in connected_outputs:
                        issues["belt_orphan_output"].append({
                            "device_idx": di, "typeId": typeId,
                            "origin": dev.get("origin"), "rotation": dev.get("rotation"),
                            "port_id": p["port_id"],
                            "world_cell": p["world_cell"], "edge": p["edge"],
                        })

    # type mismatch: every processor's received items must be in recipe inputs.
    # Skip machine types with no recipes (hard-coded special consumers like
    # power_sta eating batteries) — validator can't reason about those.
    for di, recvd in inputs_received.items():
        typeId = devices[di]["typeId"]
        if typeId not in processor_types:
            continue
        recipe_in = recipe_inputs_by_machine.get(typeId, set())
        if not recipe_in:
            continue  # special hard-coded consumer
        bad = recvd - recipe_in
        if bad:
            # Attribute each mismatching item to specific input port
            # port_id like "in_s_0" → number = 0 (default-rotation left-to-right index)
            port_detail = []
            for p in ports_by_device.get(di, []):
                if p["direction"] != "Input":
                    continue
                pid = p["port_id"]
                pitems = port_inputs.get((di, pid), set())
                bad_at_port = pitems & bad
                if not bad_at_port:
                    continue
                # extract numeric index from port_id (e.g. "in_s_3" → 3)
                num = None
                parts = pid.rsplit("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    num = int(parts[1])
                port_detail.append({
                    "port_id": pid,
                    "port_num_default_orientation": num,
                    "mismatching_items": sorted(bad_at_port),
                    "all_items_at_port": sorted(pitems),
                })
            issues["type_mismatch_at_machine_input"].append({
                "device_idx": di, "typeId": typeId,
                "origin": devices[di].get("origin"),
                "rotation": devices[di].get("rotation"),
                "received": sorted(recvd),
                "recipe_inputs": sorted(recipe_in),
                "mismatching": sorted(bad),
                "port_detail": port_detail,
            })

    # also flag processors that received NO item at all
    no_input_processors = []
    for di, dev in enumerate(devices):
        if dev["typeId"] in processor_types:
            if di not in inputs_received or not inputs_received[di]:
                # only flag if it has at least one connected input
                if any(
                    p["direction"] == "Input" and (di, p["port_id"]) in connected_inputs
                    for p in ports_by_device.get(di, [])
                ):
                    no_input_processors.append({
                        "device_idx": di, "typeId": dev["typeId"],
                        "origin": dev.get("origin"),
                    })
    issues["processor_received_no_items_despite_connected_input"] = no_input_processors

    summary = {
        "blueprint_device_count": len(devices),
        "connection_count": len(connections),
        "processor_count": sum(1 for d in devices if d["typeId"] in processor_types),
        "conveyor_count": sum(1 for d in devices if d["typeId"] in conveyor_types),
        "junction_count": sum(1 for d in devices if d["typeId"] in junction_types),
        "storage_count": sum(1 for d in devices if d["typeId"] in storage_types),
        "processors_reached_by_items": len([d for d in inputs_received.values() if d]),
    }
    return {"summary": summary, "issues": issues, "connection_count": len(connections)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("blueprint", help="IP v2 blueprint JSON path")
    parser.add_argument("--spec", default=DEFAULT_SPEC_PATH,
                        help=f"IP v2 device spec JSON path (default {DEFAULT_SPEC_PATH})")
    parser.add_argument("--verbose", action="store_true",
                        help="Print every issue, not just counts")
    parser.add_argument("--json", action="store_true", help="Emit full JSON report")
    args = parser.parse_args()

    spec = json.load(open(args.spec))
    bp = json.load(open(args.blueprint))
    device_types = {d["id"]: d for d in spec["device_types"]}
    recipes = spec["recipes"]
    devices = bp["devices"]

    report = validate(devices, device_types, recipes)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # Pretty print
    print(f"=== Blueprint: {bp.get('name', '<unnamed>')} ===")
    print(f"  baseId: {bp.get('baseId')}")
    s = report["summary"]
    print(f"  devices: {s['blueprint_device_count']} "
          f"(processor {s['processor_count']} / conveyor {s['conveyor_count']} / "
          f"junction {s['junction_count']} / storage {s['storage_count']})")
    print(f"  port connections: {s['connection_count']}")
    print(f"  processors reached by items: {s['processors_reached_by_items']}")
    print()
    print("=== Issues ===")
    issues = report["issues"]
    total = 0
    for k, v in issues.items():
        if v:
            total += len(v)
            print(f"  ✗ {k}: {len(v)}")
            if args.verbose:
                for entry in v[:50]:
                    print(f"      {entry}")
                if len(v) > 50:
                    print(f"      ... and {len(v)-50} more")
        else:
            print(f"  ✓ {k}: 0")
    print()
    if total == 0:
        print("✅ No issues found.")
    else:
        print(f"⚠ Total {total} issue entries (use --verbose for details, --json for full report).")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
