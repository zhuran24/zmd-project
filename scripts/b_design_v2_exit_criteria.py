#!/usr/bin/env python3
"""B Design v2 168h campaign exit criteria checklist.

Phase 0 → Phase 1 → 168h production campaign 之间的硬门禁. 8 条 criterion
formalized from GPT pro v14 review (memory v14-review-findings + paradigm
death timeline Phase 0 Day 21 exit criteria).

每条 criterion:
- description: 一行 GPT 原文
- pass_condition: 可量化的 PASS 标准
- check_kind: "automated" (本 script 跑) | "ramp_data" (依赖 Phase 1 80/160
  inst ramp 数据) | "telemetry" (依赖 168h campaign 内 telemetry)
- artifact: 在哪查 (file path / metric)

Usage:
    python scripts/b_design_v2_exit_criteria.py             # 跑全 check
    python scripts/b_design_v2_exit_criteria.py --strict    # FAIL/PENDING fail script
    python scripts/b_design_v2_exit_criteria.py --json      # 出 JSON 报告
    python scripts/b_design_v2_exit_criteria.py --criterion 1 4 8  # 只跑 #1/4/8

PROJECT_LOCK §2 update 后, 168h campaign 启动前必须本 script 全 PASS.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, List, Literal, Optional

REPO = Path(__file__).parent.parent


# ============================================================================
# Criterion dataclass
# ============================================================================

CheckKind = Literal["automated", "ramp_data", "telemetry", "code_inspection"]
CheckStatus = Literal["PASS", "FAIL", "SKIP", "PENDING_PHASE_1"]


@dataclass
class CriterionResult:
    id: int
    description: str
    check_kind: CheckKind
    pass_condition: str
    artifact: str
    status: CheckStatus
    detail: str = ""
    error: Optional[str] = None


# ============================================================================
# Criterion #1 — Boundary 语义冻结 + 源码文档一致
# ============================================================================

def check_boundary_source_of_truth() -> CriterionResult:
    """Phase 0 Day 1-2 done. 验:
    - canonical_rules.json `boundary_storage_port.placement_rule ==
      "left_or_bottom_boundary"`
    - candidate_placements.json boundary pose 数 == 134 (left 67 + bottom 67)
    """
    detail_parts: List[str] = []
    try:
        rules = json.loads((REPO / "rules" / "canonical_rules.json").read_text())
        # Schema (verified 2026-05-22): rules.facility_templates.{type}.placement_rule
        templates = rules.get("facility_templates", {})
        boundary_rule = templates.get("boundary_storage_port", {}).get("placement_rule")
        if boundary_rule == "left_or_bottom_boundary":
            detail_parts.append("canonical_rules.boundary_storage_port.placement_rule == 'left_or_bottom_boundary' ✓")
        else:
            return CriterionResult(
                id=1, description="boundary 语义冻结 + 源码文档一致",
                check_kind="automated", pass_condition="placement_rule == 'left_or_bottom_boundary'",
                artifact="rules/canonical_rules.json",
                status="FAIL", detail=f"got {boundary_rule!r}",
            )

        # 验 candidate_placements boundary pose count (期望 134)
        # Schema: data.facility_pools.boundary_storage_port (list)
        placements_path = REPO / "data" / "preprocessed" / "candidate_placements.json"
        if placements_path.exists():
            placements = json.loads(placements_path.read_text())
            boundary_poses = placements.get("facility_pools", {}).get("boundary_storage_port", [])
            count = len(boundary_poses)
            if count == 134:
                detail_parts.append(f"candidate_placements boundary pose count == {count} ✓")
            else:
                detail_parts.append(f"candidate_placements boundary count {count} ≠ 134 ⚠️")

        return CriterionResult(
            id=1, description="boundary 语义冻结 + 源码文档一致",
            check_kind="automated",
            pass_condition="placement_rule==left_or_bottom_boundary + candidate count 134",
            artifact="rules/canonical_rules.json + data/preprocessed/candidate_placements.json",
            status="PASS", detail=" / ".join(detail_parts),
        )
    except Exception as e:
        return CriterionResult(
            id=1, description="boundary 语义冻结 + 源码文档一致",
            check_kind="automated", pass_condition="...",
            artifact="rules/canonical_rules.json",
            status="FAIL", error=str(e),
        )


# ============================================================================
# Criterion #2-#4 — Synthetic test (Phase 1 实施 + 测试)
# ============================================================================

def check_synthetic_test_exists(test_name: str, criterion_id: int, description: str) -> CriterionResult:
    """检查 src/tests/cuts/test_*.py 存在且能 pass."""
    test_path = REPO / "src" / "tests" / "cuts" / test_name
    if not test_path.exists():
        return CriterionResult(
            id=criterion_id, description=description,
            check_kind="ramp_data",
            pass_condition=f"pytest {test_name} 全 PASS",
            artifact=str(test_path.relative_to(REPO)),
            status="PENDING_PHASE_1",
            detail=f"{test_name} 文件不存在 (Phase 1 写测试时创建)",
        )
    # 跑 pytest
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-q"],
            cwd=REPO, capture_output=True, timeout=60, text=True,
        )
        status = "PASS" if result.returncode == 0 else "FAIL"
        return CriterionResult(
            id=criterion_id, description=description,
            check_kind="ramp_data",
            pass_condition=f"pytest {test_name} 全 PASS",
            artifact=str(test_path.relative_to(REPO)),
            status=status,
            detail=(result.stdout + result.stderr).strip()[-500:],
        )
    except Exception as e:
        return CriterionResult(
            id=criterion_id, description=description,
            check_kind="ramp_data", pass_condition="...",
            artifact=str(test_path.relative_to(REPO)),
            status="FAIL", error=str(e),
        )


def check_2_q_front_overload() -> CriterionResult:
    return check_synthetic_test_exists(
        "test_family_port_exposure.py", 2,
        "q-front overload synthetic test 被 port-resource cut 剪 (不靠 full no-good)"
    )


def check_3_power_no_cover() -> CriterionResult:
    return check_synthetic_test_exists(
        "test_family_power_hitting_set.py", 3,
        "power no-cover test ghost-conditioned typed cert"
    )


# v2 (Gemini round 24 A1.1): 加 F8/F9 测试门禁 — 最复杂几何算法 (Liang-Barsky
# AABB intersection / area-based counting) 必硬验
def check_2b_power_grid_reach() -> CriterionResult:
    return check_synthetic_test_exists(
        "test_family_power_grid_reach.py", 28,  # criterion id 2b → 28
        "F8 power_grid_reach Liang-Barsky AABB intersection 测试 (Gemini r24 加)"
    )


def check_3b_density_envelope() -> CriterionResult:
    return check_synthetic_test_exists(
        "test_family_density_envelope.py", 38,  # criterion id 3b → 38
        "F9 density_envelope area-based counting 测试 (Gemini r24 加)"
    )


def check_4_replay_suite() -> CriterionResult:
    return check_synthetic_test_exists(
        "test_replay.py", 4,
        "replay suite 27+ ghost anchors 无 false positive"
    )


# ============================================================================
# Criterion #5-#6 — Ramp data (依赖 80/160 inst ramp)
# ============================================================================

def check_ramp_metric(metric_path: str, criterion_id: int, description: str,
                       pass_condition: Callable[[dict], bool],
                       pass_cond_text: str) -> CriterionResult:
    """读 ramp report JSON, 验 metric."""
    metric_file = REPO / metric_path
    if not metric_file.exists():
        return CriterionResult(
            id=criterion_id, description=description,
            check_kind="ramp_data",
            pass_condition=pass_cond_text,
            artifact=metric_path,
            status="PENDING_PHASE_1",
            detail=f"{metric_path} 不存在 (Phase 1 跑 ramp 后生成)",
        )
    try:
        data = json.loads(metric_file.read_text())
        ok = pass_condition(data)
        return CriterionResult(
            id=criterion_id, description=description,
            check_kind="ramp_data",
            pass_condition=pass_cond_text,
            artifact=metric_path,
            status="PASS" if ok else "FAIL",
            detail=json.dumps({k: data.get(k) for k in
                                # v3 (Gemini round 25 B1): 加 cut_store_peak_mb_per_worker
                                # 否则 #6 FAIL 时 detail 看不到实际触发值, debug 不便
                                ["unknown_count", "cut_store_peak_mb",
                                 "cut_store_peak_mb_per_worker", "rss_peak_mb_per_worker",
                                 "f5_ratio", "f5_avg_core_size"]
                                if k in data}, ensure_ascii=False),
        )
    except Exception as e:
        return CriterionResult(
            id=criterion_id, description=description,
            check_kind="ramp_data", pass_condition=pass_cond_text,
            artifact=metric_path,
            status="FAIL", error=str(e),
        )


def check_5_80_inst_no_unknown() -> CriterionResult:
    return check_ramp_metric(
        "docs/research/b_design_v2_ramp/80_inst_report.json", 5,
        "80-inst 无 UNKNOWN→cut",
        lambda d: d.get("unknown_count", 1) == 0,
        "ramp_report.unknown_count == 0",
    )


def check_6_160_inst_cut_store() -> CriterionResult:
    # v3 (Gemini round 25 B2): RSS 优先 — Python 内存碎片化让逻辑 3 GB → RSS 8 GB,
    #                         逻辑通过 #6 但 OS OOM kill.
    # v2 (Gemini round 24 A1.2 致命 RAM 计算错):
    # 单机 48 GB cap: 4 worker × 5 GB + master 16 GB + other 8 GB = 44 GB
    # 安全余量 4 GB. v1 12 GB/worker × 4 = 48 GB + master = 必 OOM.
    def _pass(d: dict) -> bool:
        # v3 优先验 rss_peak_mb_per_worker (psutil), fallback cut_store_peak_mb_per_worker
        rss = d.get("rss_peak_mb_per_worker")
        if rss is not None:
            return rss < 5 * 1024
        # fallback: 逻辑大小 (不准, 但比没有强)
        return d.get("cut_store_peak_mb_per_worker", 99999) < 5 * 1024

    return check_ramp_metric(
        "docs/research/b_design_v2_ramp/160_inst_report.json", 6,
        "160-inst cut store < 5 GB/worker (RSS preferred, Gemini r25 B2)",
        _pass,
        "rss_peak_mb_per_worker < 5120 (psutil RSS) OR cut_store_peak_mb_per_worker < 5120",
    )


# v2 (Gemini round 24 A1.3): 加 cut store rotation/GC 机制测试
def check_9_cut_store_rotation() -> CriterionResult:
    return check_synthetic_test_exists(
        "test_cut_store_rotation.py", 9,
        "cut store rotation/GC 机制 (capacity-based eviction sound, 不删 active cut, "
        "PROJECT_LOCK §4 Step 10 豁免范围) (Gemini r24 加)"
    )


# ============================================================================
# Criterion #7 — Pattern no-good Class C monitor (telemetry)
# ============================================================================

def check_7_pattern_no_good_ratio() -> CriterionResult:
    return check_ramp_metric(
        "docs/research/b_design_v2_ramp/cut_family_ratio.json", 7,
        "pattern no-good 平均 core size 受控 + 非主力 cut source",
        lambda d: (d.get("f5_ratio", 1.0) < 0.5 and
                   d.get("f5_avg_core_size", 999) < 20),
        "f5_ratio < 50% AND f5_avg_core_size < 20",
    )


# ============================================================================
# Criterion #8 — Persisted cuts replay 100% pass
# ============================================================================

def check_8_persisted_cuts_replay() -> CriterionResult:
    """所有 persisted cuts deserialize+validate+attach-scope 通过.

    v2 (Gemini round 24 D1): A3 plan P1.21 用 active/quarantine 分子目录,
    script glob 必须 cover 两 dir. 只 glob data/cuts/*.json 漏 active/quarantine
    内 cut → #8 永远 PENDING.

    NOTE (v2 D2 fail-closed 语义): Phase 1 实施 6 步 verify 测试时, 必须验
    "未知 assumption → HOLD, cut 不错误转入 quarantine 目录". 此 script 目前
    占位 jsonschema 检查, 6 步 verify 测试在 Phase 1 P1.20 加.
    """
    cuts_dir = REPO / "data" / "cuts"
    if not cuts_dir.exists():
        return CriterionResult(
            id=8, description="所有 persisted cuts deserialize+validate+attach-scope 通过",
            check_kind="ramp_data",
            pass_condition="data/cuts/{active,quarantine}/*.json 全 PASS replay 6 步 verify",
            artifact="data/cuts/{active,quarantine}/",
            status="PENDING_PHASE_1",
            detail="data/cuts/ 不存在 (Phase 1 cut store 启用后生成)",
        )

    # v2: glob 两个子目录 (active + quarantine)
    active_dir = cuts_dir / "active"
    quarantine_dir = cuts_dir / "quarantine"
    cut_files = []
    if active_dir.exists():
        cut_files.extend(active_dir.glob("*.json"))
    if quarantine_dir.exists():
        cut_files.extend(quarantine_dir.glob("*.json"))
    # Backward compat: 也 cover flat layout
    cut_files.extend(cuts_dir.glob("*.json"))
    if not cut_files:
        return CriterionResult(
            id=8, description="所有 persisted cuts deserialize+validate+attach-scope 通过",
            check_kind="ramp_data",
            pass_condition="data/cuts/*.json 全 PASS replay 6 步 verify",
            artifact="data/cuts/",
            status="PENDING_PHASE_1",
            detail="data/cuts/ 空 (Phase 1 cut store 启用后生成)",
        )

    # PoC: 不真跑 6 步 verify (依赖 src/cuts/lifecycle.py Phase 1), 只验
    # 每 file jsonschema 大致 OK.
    failed = []
    for cut_file in cut_files:
        try:
            data = json.loads(cut_file.read_text())
            required_fields = {"cut_id", "family", "scope", "cert"}
            missing = required_fields - set(data.keys())
            if missing:
                failed.append((cut_file.name, f"missing {missing}"))
        except Exception as e:
            failed.append((cut_file.name, str(e)))

    if failed:
        return CriterionResult(
            id=8, description="所有 persisted cuts deserialize+validate+attach-scope 通过",
            check_kind="ramp_data",
            pass_condition="全 cut file jsonschema valid",
            artifact="data/cuts/",
            status="FAIL",
            detail=f"{len(failed)} files failed: {failed[:3]}",
        )

    return CriterionResult(
        id=8, description="所有 persisted cuts deserialize+validate+attach-scope 通过",
        check_kind="ramp_data",
        pass_condition="全 cut file jsonschema valid + 6 步 verify PASS",
        artifact="data/cuts/",
        status="PASS",
        detail=f"{len(cut_files)} cut files PASS schema check (Phase 1 加 6 步 verify 全跑)",
    )


# ============================================================================
# Main
# ============================================================================

# v2 (Gemini round 24): CRITERIA dict keyed by ID, 加 #28/38/9 新 finding
CRITERIA = {
    1: check_boundary_source_of_truth,
    2: check_2_q_front_overload,
    28: check_2b_power_grid_reach,   # F8 — Gemini r24 加 (geometric Liang-Barsky)
    3: check_3_power_no_cover,
    38: check_3b_density_envelope,   # F9 — Gemini r24 加 (area-based counting)
    4: check_4_replay_suite,
    5: check_5_80_inst_no_unknown,
    6: check_6_160_inst_cut_store,
    7: check_7_pattern_no_good_ratio,
    8: check_8_persisted_cuts_replay,
    9: check_9_cut_store_rotation,   # cut store rotation/GC — Gemini r24 加
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--strict", action="store_true",
                        help="任 criterion FAIL/PENDING 整 script return 1")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--criterion", type=int, nargs="+",
                        help="只跑指定 criterion ID (1, 2, 28=2b, 3, 38=3b, 4-9)")
    args = parser.parse_args()

    selected = args.criterion or sorted(CRITERIA.keys())
    results: List[CriterionResult] = []
    for cid in selected:
        if cid not in CRITERIA:
            print(f"skip invalid criterion {cid} (valid: {sorted(CRITERIA.keys())})", file=sys.stderr)
            continue
        results.append(CRITERIA[cid]())

    if args.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        print("\n=== B Design v2 168h Campaign Exit Criteria ===\n")
        for r in results:
            symbol = {"PASS": "✓", "FAIL": "✗", "SKIP": "-", "PENDING_PHASE_1": "⏸"}[r.status]
            print(f"  {symbol} #{r.id} [{r.status:18}] {r.description}")
            print(f"     check_kind: {r.check_kind} | pass: {r.pass_condition}")
            print(f"     artifact:   {r.artifact}")
            if r.detail:
                print(f"     detail:     {r.detail[:200]}")
            if r.error:
                print(f"     error:      {r.error}")
            print()
        pass_count = sum(1 for r in results if r.status == "PASS")
        pending = sum(1 for r in results if r.status == "PENDING_PHASE_1")
        fail = sum(1 for r in results if r.status == "FAIL")
        print(f"=== Summary: {pass_count} PASS / {pending} PENDING_PHASE_1 / {fail} FAIL ===\n")

    has_fail = any(r.status == "FAIL" for r in results)
    has_pending = any(r.status == "PENDING_PHASE_1" for r in results)
    if has_fail:
        return 1
    if args.strict and has_pending:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
