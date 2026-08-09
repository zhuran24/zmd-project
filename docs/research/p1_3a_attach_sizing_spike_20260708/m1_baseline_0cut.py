"""M1 attach spike — 基线测量 #0: coordinate exact master 的 build 成本与规模.

只读消费生产数据与生产 build 入口 (load_project_data / build_exact_core /
from_exact_core), 不写任何仓库文件, 不 solve. 输出 JSON 到 stdout.

目的: 旧 spike 设计 (2026-05, MERGER.md) 的 sizing 数字全部基于已被换掉的
PoseBoolExactMaster (81K BoolVar); P1.3 的 attach spike 必须先在现役
CoordinateExactMasterDelegate 上重建 0-cut 基线, 才能设计 cut 注入挡位.
"""
import json
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path(r"C:\claude pj\zmd-pj")
sys.path.insert(0, str(PROJECT_ROOT))


def rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        return -1.0


def main() -> None:
    out: dict = {"schema": "m1_baseline_0cut_v1"}
    t0 = time.perf_counter()
    from src.models.master_model import (
        MasterPlacementModel,
        load_generic_io_requirements_artifact,
        load_project_data,
    )

    out["import_seconds"] = round(time.perf_counter() - t0, 3)

    t = time.perf_counter()
    instances, facility_pools, rules = load_project_data(
        PROJECT_ROOT, "certified_exact"
    )
    gio = load_generic_io_requirements_artifact(PROJECT_ROOT)
    out["load_seconds"] = round(time.perf_counter() - t, 3)
    out["instance_count"] = len(instances)
    out["facility_pool_types"] = len(facility_pools)
    out["rss_after_load_mb"] = round(rss_mb(), 1)

    t = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        instances,
        facility_pools,
        rules,
        generic_io_requirements=gio,
    )
    out["build_exact_core_seconds"] = round(time.perf_counter() - t, 3)
    prof = dict(core.build_stats.get("exact_core_packaging_profile", {}))
    out["proto_variable_count"] = prof.get("proto_variable_count")
    out["proto_constraint_count"] = prof.get("proto_constraint_count")
    out["proto_capture_seconds"] = prof.get("proto_capture_seconds")
    out["packaging_seconds"] = prof.get("packaging_seconds")
    try:
        out["proto_byte_size"] = int(core.proto.ByteSize())
    except Exception:
        out["proto_byte_size"] = None
    out["master_representation"] = getattr(core, "master_representation", None)
    out["rss_after_core_mb"] = round(rss_mb(), 1)

    ghost_timings: dict = {}
    for ghost in [(8, 8), (12, 10), (20, 16)]:
        t = time.perf_counter()
        model = MasterPlacementModel.from_exact_core(core, ghost)
        ghost_timings["%dx%d" % ghost] = round(time.perf_counter() - t, 3)
        del model
    out["from_exact_core_seconds"] = ghost_timings
    out["rss_after_clones_mb"] = round(rss_mb(), 1)

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
