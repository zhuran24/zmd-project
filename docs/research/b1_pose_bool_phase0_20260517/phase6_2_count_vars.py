"""Quick: build only 27×15 anchor (22,28) with port_active=1, print build_stats."""
from __future__ import annotations
import os, sys, time, json
from pathlib import Path
from typing import cast, Mapping, List, Dict, Any
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
os.environ["EXACT_USE_PORT_ACTIVE"] = "1"

from src.search.benders_loop import ExactSearchSession
from src.models.master_model import MasterPlacementModel, infer_exact_required_pose_optional_counts

project_root = Path(".")
es = ExactSearchSession.create(project_root, solve_mode="certified_exact")
inferred = infer_exact_required_pose_optional_counts(
    es.core.rules, es.core.generic_io_requirements
)

t0 = time.perf_counter()
master = MasterPlacementModel(
    list(es.core.source_instances),
    cast(Mapping[str, List[Dict[str, Any]]], es.core.facility_pools),
    es.core.rules,
    ghost_rect=(27, 15),
    skip_power_coverage=False,
    enable_symmetry_breaking=False,
    generic_io_requirements=es.core.generic_io_requirements,
    exact_required_pose_optional_counts=inferred,
    solve_mode="certified_exact",
    ghost_anchor_filter={(22, 28)},
)
master.build()
build_elapsed = time.perf_counter() - t0
print(f"\nbuild: {build_elapsed:.2f}s")
pbm = master.build_stats.get("pose_bool_master", {})
print(f"pose_bool_master stats:\n  {json.dumps(pbm, indent=2)}")

# count CP-SAT model size
proto = master.model.Proto()
print(f"\nCP-SAT proto vars: {len(proto.variables)}")
print(f"CP-SAT proto constraints: {len(proto.constraints)}")
