#!/usr/bin/env python3
"""Round 32 Gemini AUDIT mode — verify Gap 11-14 fix landed (round 31 NOT GO → GO).

Same audit-mode prompt 模式 — 真数据 inline + armor + 反 GO 章.
任务: 验 round 31 catch 的 5 个 (Gap 11+12+13+14, Gap 15 defer) 是否真修.

Output: /home/zhuran24/linwin_share/gemini_round_32_gap_fix_verify_round2_response.md
"""
from __future__ import annotations

import collections
import json
import time
import urllib.request
from pathlib import Path

API_KEY = "[REDACTED_GCP_API_KEY]"
MODEL = "gemini-3.1-pro-preview"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

REPO = Path("/home/zhuran24/claude-pj/zmd")
SHARE = Path("/home/zhuran24/linwin_share")

DOC_PATHS = [
    "rules/canonical_rules.json",
    "data/preprocessed/generic_io_requirements.json",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md",
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
    # 修后 src
    "src/cuts/lifecycle.py",
    "src/cuts/helpers/canonical_rules.py",
    "src/cuts/helpers/candidate_placements.py",
    "src/cuts/families/region_capacity.py",
    "src/cuts/oracles/region_capacity_oracle.py",
    "src/cuts/families/port_exposure.py",
    "src/cuts/assumptions/verifiers.py",
    # round 30 + 31 verdict (历史 finding)
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_30_gap6_audit_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_31_gap_fix_verify_NOT_GO.md",
]


def _build_data_aggregate() -> str:
    parts = []
    with (REPO / "data/preprocessed/mandatory_exact_instances.json").open() as f:
        mei = json.load(f)
    op_counts = collections.Counter(i["operation_type"] for i in mei)
    op_to_ft = {}
    for i in mei:
        op_to_ft.setdefault(i["operation_type"], i["facility_type"])

    parts.append("### 真数据: mandatory_exact_instances 266 instances\n")
    parts.append("operation_type → count + facility_type:\n")
    for op, c in sorted(op_counts.items(), key=lambda x: -x[1]):
        parts.append(f"- {op}: {c}  (ft={op_to_ft[op]})\n")

    cp_path = REPO / "data/examples/industrial_planner/current_delivery/viewer/candidate_placements.json"
    with cp_path.open() as f:
        cp = json.load(f)
    parts.append("\n### candidate_placements sample pose (含 N/S/E/W direction)\n```\n")
    for ft, poses in cp["facility_pools"].items():
        if poses:
            parts.append(f"\n{ft} first pose:\n")
            parts.append(json.dumps(poses[0], indent=2, ensure_ascii=False))
            parts.append("\n")
    parts.append("```\n")
    return "".join(parts)


PROMPT = """\
# Round 32 Gemini AUDIT mode — verify Gap 11-14 fix landed (round 2)

## 工作模式声明

跟 round 30 一样 AUDIT mode, **不是 GO 章 ritual**. 任务: 验 round 30 verdict
NOT GO 后我做的 fix 是否真到位, 跟真数据 + spec 一致.

## Audit 强制规则

1. **拒 vague hyperbole** (完美 / 完全一致 / 绝佳 等不准说).
2. **每 claim 必 cite file:line** + 跟真数据具体 key/value 对比.
3. **GO 必先列 3 死法 + 反驳每一种**.
4. **找 1 critical 比 100 surface 价值高 10×**.
5. **找不到 critical 也必列 ≥ 5 high-risk hypothesis**.

## Round 31 5 finding fix 情况

Round 31 audit verify Gap 6-10 修后, 再 catch 5 critical/high-risk:
- Gap 11: DIRECTION_OFFSETS 假设 N=(-1,0) 错; 真数据 verify N=(0,-1)
- Gap 12: selected_poses spec 要 List[PoseId] 我写 List[Tuple] crash
- Gap 13: cut_family_specs/01 fixture drift 跟 src 不同步
- Gap 14: find_pose O(N) linear scan 1s timeout risk
- Gap 15: cells_per_pose=w×h 矩形假设 (defer Phase 1.5+, 当前真数据 OK)

我按 round 31 verdict 修了 (commit a82c97e):

### Gap 11 fix
- helpers/candidate_placements.py DIRECTION_OFFSETS: N=(0,-1), S=(0,1),
  E=(1,0), W=(-1,0). 实测真 pose verify pass.
- test_family_port_exposure.py fixture 重设计: port (10,10) W → front (9, 10)
  outside facility.

### Gap 12 fix
- lifecycle.py GroupState.selected_poses: List[PoseId] (spec 一致)
- evaluate_literal_multiset: `for pose_id in selected_poses` (替 unpack tuple)
- Tests batch update: selected_poses=[("g", "p7")] → ["p7"]

### Gap 13 fix
- cut_family_specs/01 line 478-510 fixture update: region_kind=
  "left_or_bottom_union", cap=137, demand=138, gid="boundary_io".

### Gap 14 fix
- helpers/candidate_placements.py find_pose 加 _POSE_CACHE_KEY lazy-built
  dict[(ft, pose_id), pose], O(1) lookup.

### Gap 15 (defer)
- 不修 (当前数据矩形全 OK).

### Gap 6 数学 (round 30 我 recommend → 你确认 a Union region)
- 修: `oracles/region_capacity_oracle.py` enumerate 只 `("left_or_bottom_union",)`,
  废 per-side. region_kind 加 "left_or_bottom_union" (139 cells).
- 修: `families/region_capacity.py` _PLACEMENT_RULE_REGIONS map
  "left_or_bottom_boundary" → ONLY {"left_or_bottom_union"} (不再 per-side).
- 修: `compute_region_cells("left_or_bottom_union", ...)` 算 70+70-1 union.

### Gap 7 遍历 (oracle.py:65 旧 → 现 ~85)
- 修: `_enumerate_contributing_groups` 改遍历 `state.groups` (真 operation_type),
  经 `helpers.canonical_rules.placement_rule_for_group(state, gid)` 查.

### Gap 8 schema (canonical_rules KeyError)
- 新建: `src/cuts/helpers/canonical_rules.py` — facility_type_for_group /
  cells_per_pose_for_group / placement_rule_for_group / port_rule_for_group /
  facility_template_for_group. 全经 state.instance_to_facility_type +
  state.facility_templates 映射.
- BState 加 `facility_templates: Optional[Dict]` + `instance_to_facility_type:
  Optional[Dict]` field.
- families/region_capacity + oracles/region_capacity + assumptions/verifiers
  全改用 helper, 不直接 canonical_rules[gid].

### Gap 9 ports lookup (port_exposure.py:101 ports_by_pose 虚构)
- 新建: `src/cuts/helpers/candidate_placements.py` — find_pose / pose_ports /
  direction_offset (N/S/E/W cardinal).
- BState 加 `candidate_placements: Optional[Dict]`.
- families/port_exposure 改用 helper, direction encoding N/S/E/W (替 up/down/
  left/right per 真数据).

### Gap 10 PoseId 类型
- lifecycle.py `PoseId = str` (替 int).
- GroupState.pose_domain / selected_poses 类型 follow.

Tests: src/tests/cuts/ 139/139 PASS. Full src/tests/ no regression.
ruff + mypy: all pass.

## 任务

### 任务 A: 验 Gap 11-14 修是否 sound + 完整

逐个 verify, **cite 修后的 file:line**:
- Gap 11 direction: 新 DIRECTION_OFFSETS (N=(0,-1) 等) 在所有 facility_type
  (manufacturing_3x3/5x5/6x4, boundary_storage_port w=1×h=3) 真 pose 上验证.
  抽 ≥ 3 sample pose verify front_cell outside occupied.
- Gap 12 schema: GroupState.selected_poses=List[PoseId] 跟 spec 严格一致?
  evaluate_literal_multiset 用 outer-loop gid 正确组合 Counter key?
- Gap 13 spec doc: cut_family_specs/01 fixture 跟 src 完整一致 (region_kind/
  cap/demand/gid/cells_per_pose 字段)?
- Gap 14 cache: _POSE_CACHE_KEY 实施 thread-safe 吗 (Phase 1.5+ multi-thread
  risk)? cache invalidation 哪步 trigger (state.candidate_placements 改
  时)? 当前 lazy-built + 不 invalidate 可能 stale.

### 任务 B: 找 fix 引入的新 bug 或漏修

每个 Gap fix 都可能引新隐患. 找 ≥ 5 个:
- 比如 Gap 6 union region 跟 spec §9 F1 反例 fixture (line 478-510) 现在还
  match 吗? 如果不 match, spec doc 是否需要更新?
- Gap 8 helper "free" 默认 vs "unknown" fallback — facility_template 没
  placement_rule 字段时 default "free" 对吗 (canonical_rules.json 大多
  template 都没此字段)?
- Gap 9 direction N/S/E/W 假设 — viewer pose 真用 N/S/E/W 但有没有 NE/SE
  等非 cardinal? 看真数据 sample.
- Gap 10 PoseId=str — JSON serialize 时 `cells_per_pose_map` key 仍 group_id
  str OK, 但 cert.contributing_groups 数 type 变了 (PoC fixture 用 int 仍 work
  因 demand_R 是 int).
- helpers/candidate_placements.find_pose 是 O(N) linear scan — 266 instance ×
  4 facility_type 平均 N=66 — 单 validator call O(66). 多 cut × N 大. P1.4 ramp
  会爆?

### 任务 C: Phase 1.1 真数据 production GO 还是仍 NOT GO?

- 若 5 Gap 全修 + 没新 critical bug + fixtures 全 PASS + helper chain sound →
  "Phase 1.1 production GO, 可推 Phase 1.2 (P1.11-P1.15)"
- 若仍有 critical → list file:line 必修 + 不准跳进 Phase 1.2

## 输出格式

3 段 A/B/C, cite file:line, ≥ 1500 字, 不准 vague.
"""


def fetch_doc(path: str) -> str:
    p = REPO / path
    if not p.exists():
        return f"[MISSING: {path}]"
    return p.read_text(encoding="utf-8")


def build_prompt() -> str:
    parts = [PROMPT, "\n\n## 真数据 inline aggregate\n\n"]
    parts.append(_build_data_aggregate())
    parts.append("\n\n## Reference Materials\n")
    for dp in DOC_PATHS:
        content = fetch_doc(dp)
        parts.append(f"\n\n### --- {dp} ---\n\n{content}\n")
    return "".join(parts)


def call_gemini(prompt: str) -> dict:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 16384},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def extract_text(resp: dict) -> str:
    try:
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        return f"[parse error: {e}]\n\n{json.dumps(resp, ensure_ascii=False, indent=2)[:4000]}"


def main() -> int:
    SHARE.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt()
    print(f"Prompt size: {len(prompt):,} bytes, ~{len(prompt)//4:,} tokens (est)")
    t0 = time.monotonic()
    try:
        resp = call_gemini(prompt)
    except Exception as e:
        print(f"FAIL: {e}")
        return 1
    elapsed = time.monotonic() - t0
    print(f"Gemini response in {elapsed:.1f}s")
    text = extract_text(resp)
    out_path = SHARE / "gemini_round_32_gap_fix_verify_round2_response.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"Response written: {out_path} ({len(text):,} bytes)")
    print("\n---\n")
    print(text[:10000])
    if len(text) > 10000:
        print(f"\n... [{len(text)-10000} more bytes in file]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
