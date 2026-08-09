#!/usr/bin/env python3
"""Round 33 Gemini AUDIT mode — verify Step A-E fix landed (GPT pro round 2 P0 #1-4).

工作背景:
- GPT pro Phase 1.1 audit round 1 + round 2 verdict 一致 NOT GO
- 2 P0 + 7 必修 (refs:
  docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_audit_round2_NOT_GO.md)
- Step A-E (commit 3d35a62, 45c44d2, eaed85c, 5c06dff, 8a38401) land 4 critical fix
- 本次 audit verify 4 fix 是否 sound + 完整 + 是否引新 bug

Audit 重点 (跟 GPT pro 反例):
- Step A: `python -O` 删 assert 防线 — explicit `if ... return schema_err`
- Step B: F3 validator 加 cert ↔ literal multiset 绑定 (slot anonymity)
- Step C: F2 validator 加 partition enclosure check + cut_edges canonical 完整
- Step D: F4 validator 加 cert.src/sink_component == recomputed BFS + commodity_id
  fail-closed
- Step E: F1 oracle + validator 加 strict P(g) ⊆ R (boundary_io 14/54 反例 mirror)

Output: /home/zhuran24/linwin_share/gemini_round_33_gpt_pro_fix_verify_response.md
"""
from __future__ import annotations

import os
import collections
import json
import time
import urllib.request
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
if not API_KEY:
    raise SystemExit("Set GEMINI_API_KEY to run this Gemini cross-check script.")
MODEL = "gemini-3.1-pro-preview"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

REPO = Path("/home/zhuran24/claude-pj/zmd")
SHARE = Path("/home/zhuran24/linwin_share")

DOC_PATHS = [
    "rules/canonical_rules.json",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md",
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
    "docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_audit_round2_NOT_GO.md",
    # 修后 src — Step A-E 涉及文件
    "src/cuts/lifecycle.py",
    "src/cuts/helpers/canonical_rules.py",
    "src/cuts/helpers/candidate_placements.py",
    "src/cuts/families/region_capacity.py",
    "src/cuts/families/cutset.py",
    "src/cuts/families/port_exposure.py",
    "src/cuts/families/component_reach.py",
    "src/cuts/oracles/region_capacity_oracle.py",
    "src/cuts/replay.py",
    # 测试 regression
    "src/tests/cuts/test_family_region_capacity.py",
    "src/tests/cuts/test_family_cutset.py",
    "src/tests/cuts/test_family_port_exposure.py",
    "src/tests/cuts/test_family_component_reach.py",
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

    cp_path = REPO / "data/preprocessed/candidate_placements.json"
    if not cp_path.exists():
        cp_path = REPO / "data/examples/industrial_planner/current_delivery/viewer/candidate_placements.json"
    with cp_path.open() as f:
        cp = json.load(f)

    # boundary_storage_port pose scan — Step E 反例验证关键
    parts.append("\n### boundary_storage_port pose 占格分布 (Step E P(g)⊆R verify)\n")
    union_cells = {(x, 0) for x in range(70)} | {(0, y) for y in range(70)}  # left ∪ bottom
    bsp = cp["facility_pools"].get("boundary_storage_port", [])
    n_in, n_out, n_mixed = 0, 0, 0
    out_samples = []
    for pose in bsp:
        cells = [tuple(c) for c in pose.get("occupied_cells", [])]
        in_count = sum(1 for c in cells if c in union_cells)
        if in_count == len(cells):
            n_in += 1
        elif in_count == 0:
            n_out += 1
            if len(out_samples) < 3:
                out_samples.append((pose["pose_id"], cells))
        else:
            n_mixed += 1
    parts.append(f"- total boundary_storage_port pose: {len(bsp)}\n")
    parts.append(f"- wholly inside union: {n_in}\n")
    parts.append(f"- wholly outside union: {n_out}\n")
    parts.append(f"- mixed (partial): {n_mixed}\n")
    parts.append("- outside sample pose:\n")
    for pid, cells in out_samples:
        parts.append(f"  - {pid}: {cells}\n")

    parts.append("\n### candidate_placements sample pose (含 N/S/E/W direction)\n```\n")
    for ft, poses in cp["facility_pools"].items():
        if poses:
            parts.append(f"\n{ft} first pose:\n")
            parts.append(json.dumps(poses[0], indent=2, ensure_ascii=False))
            parts.append("\n")
    parts.append("```\n")
    return "".join(parts)


PROMPT = """\
# Round 33 Gemini AUDIT mode — verify GPT pro round 2 P0 fix (Step A-E)

## 工作模式声明

跟 round 30/32 一样 AUDIT mode, **不是 GO 章 ritual**. 任务: 验 GPT pro Phase 1.1
audit round 2 verdict NOT GO 后我做的 5 step fix 是否真到位, sound, 完整, 跟真
数据 + spec 一致, 没有引新 critical bug.

## Audit 强制规则

1. **拒 vague hyperbole** (完美 / 完全一致 / 绝佳 等不准说). 用具体数字 / cite.
2. **每 claim 必 cite file:line** + 跟真数据具体 key/value 对比.
3. **GO 必先列 3 死法 + 反驳每一种**. 不准只说"看着对就 GO".
4. **找 1 critical 比 100 surface 价值高 10×**.
5. **找不到 critical 也必列 ≥ 5 high-risk hypothesis** + 优先级标注.

## GPT pro round 2 7 必修 (历史 context)

Round 2 audit catch 2 P0 + 6 必修:
1. P0-1: F1 demand_R 不满足 P(g)⊆R 严格 — boundary_io 真数据 14/54 pose 在
   left∪bottom union 外, cert 假证可剪合法.
2. P0-2: F3 validator 不绑 cert ↔ literal — attacker 同 group 不同 pose mismatch
   可走过.
3. python -O 删 F3 assert (port_exposure.py:127) — schema check 失效, 一元
   literal cut 通过假证.
4. F2 cert.cut_edges 集合验缺 (spec §3 schema 必填).
5. F4 commodity_id 不验存在.
6. strict registration gate (Phase 1.2 前 F1-F9 全注册).
7. spec ↔ src ↔ data align (state_machine_v2 PoseId int→str 已修, 但 cut_lifecycle_v2
   9 family list / F2-F4 spec drift 待修).

## 我做的 Step A-E fix

### Step A (commit 3d35a62): assert → fail-closed 全 validator
- families/{region_capacity, cutset, port_exposure, component_reach}.py validator
  入口 `assert cut.geometric_payload is not None` 改 explicit `if ... return
  schema_err`. evaluator hot path 同样改 fail-safe.
- families/port_exposure.py: 加 explicit `if cut.literals is None or len < 2:
  return schema_err` (替原 `assert len >= 2` line 127, 解决 python -O 反例).
- lifecycle.py: step_5_validate_region_capacity 同改.
- 新 regression test: test_validate_port_exposure_one_literal_schema_err_python_O_safe
  (普通 + python -O 模式都 pass).

### Step B (commit 45c44d2): F3 cert↔literal multiset 绑定
- port_exposure.py 加 multiset check (在 ports lookup 前):
  - expected = Counter([(facility_group, facility_pose_id),
                         (blocking_group, blocking_pose_id)])
  - actual = Counter((lit.slot_ref.group_id, lit.pose_id) for lit in cut.literals)
  - 不等 → unsound
- slot_index 不参与 binding (state_machine_v2 §5 slot anonymity).
- 新 regression: cert_literal_multiset_mismatch + slot_anonymity_in_binding

### Step C (commit eaed85c): F2 partition enclosure + cut_edges 集合验
- cutset.py 加 3 步 check:
  - partition cells ⊆ free_cells (attacker 不能塞 ghost/cell_owner 进 partition)
  - _has_patch_escape: A∪B 没相邻 patch 外 free cell (spec §1a partition (A,B) of V)
  - cert.cut_edges canonical sorted (sorted([sorted([list(e[0]), list(e[1])])
    for e in cut_edges])) byte-equal recomputed
- cert schema: cut_edges 改必填. F2 oracle 是 stub (Phase 1.5+ patch_routing_core).
- 4 新 negative test + test fixture refactor 用 _make_enclosed_state(patch).

### Step D (commit 5c06dff): F4 cert.src/sink_component == recomputed BFS
- component_reach.py 加 frozenset 严等 check on src + sink BFS bitset.
- commodity_id 出现 → schema_err (Phase 1.5+ commodity registry verifier 落地
  前不准 carry).
- 3 新 negative test + fixture 自动 recompute BFS (state 参数).

### Step E (commit 8a38401): F1 demand_R 真 P(g)⊆R strict
- helpers/candidate_placements.py 新加 all_poses_in_region(state, gid, region_cells)
  → True/False/None (fail-closed).
- families/region_capacity.py validator step 2b 加 strict P(g)⊆R check (替原仅
  placement_rule 必要 check).
- oracles/region_capacity_oracle.py _enumerate_contributing_groups 同步加 strict
  check — boundary_io 14 pose 在 union 外 → 整 group fail-closed.
- 2 新 negative test + test fixture 加 mock candidate_placements.

测试: src/tests/cuts/ 153/153 pass (Step A 12 → Step B 14 → C 17 → D 15 → E 17).
全 cuts 测试 pass python -O 模式 (Step A 反例).

## 任务

### 任务 A: 验 Step A-E 每个 fix 是否 sound + 完整

逐 step verify, **cite 修后的 file:line**:

- **Step A**: 所有 validator 入口的 `assert ... is not None` 是否都改成 explicit?
  search `src/cuts/families/*.py` + `src/cuts/lifecycle.py` 的所有 `assert` 是否
  还有 prod path 在 python -O 下走会出 bug?
- **Step B**: cert ↔ literal multiset 是否 sound?  blocking_slot index in cert
  (line 63 `blocking_group, blocking_slot, blocking_pose_id = cert_dict["blocking_facility"]`)
  vs literal slot_ref.slot_index — slot index 怎么对? 是否真 anonymous?
- **Step C**: _has_patch_escape 算法是否数学 sound? 反例: patch={(0,0),(0,2)} 上下
  分离两 cell, free=patch ∪ {(0,1)}. (0,1) 是 patch 外 free. (0,0)→(0,1)→(0,2) 流
  可绕过 partition cut. _has_patch_escape catches 吗 (yes, (0,1) is adjacent to
  (0,0) ∈ patch but ∉ patch). 验.
- **Step D**: frozenset 比较是 deterministic 的, BFS 4-neighborhood 也是 deterministic.
  但 cert bitset b64 解码后 dimensionality vs state grid 是否一致 (70x70 hardcoded
  in _decode_bitset)? Step D 引入的 commodity_id 出现 → schema_err 是不是 fail-closed
  太硬 (production data 可能 carry; if so 应 verify 不 reject)?
- **Step E**: all_poses_in_region 处理 pose_domain 空 (无 pose info) 返 None,
  调用方 fail-closed (返 False 不当 contributing). 但 Phase 1.1 测 fixture 都
  没 carry candidate_placements 真数据 — replay test / region_capacity test
  fixture 都 mock. 真生产 candidate_placements **是否** carry boundary_io 全 54
  pose 真数据? 若 carry, oracle 会真严格 P(g)⊆R fail-closed → F1 Phase 1.1 不发
  cut (sound but zero useful). 检查 fixture vs 真 production data 一致性.

### 任务 B: 找 fix 引入的新 bug 或漏修 (≥ 5)

每个 step 都可能引新隐患. ≥ 5 个 high-risk hypothesis:

- Step A 改 assert → if/return, 但 lifecycle.step_3_serialize 还用 `assert cut.scope
  is not None and cut.cert is not None`. python -O 下序列化路径假 cut 走?
- Step B multiset Counter 比较: cert.blocking_pose_id 来自 cert tuple (group, slot,
  pose_id) — slot 是 anonymous 不进 multiset. 但 cert validator 怎么验 cert slot index
  跟 literal slot index 是否 anonymous-consistent (literal slot_ref.slot_index 任
  意, cert blocking_slot 也任意)?
- Step C cert.cut_edges canonical sorted 形式 — `sorted([sorted([list(e[0]),
  list(e[1])]) for e in cut_edges])`. 若 e[0] e[1] 类型不 hashable (list 在 Python
  里 unhashable), sorted 走 list 排序 (字典序), OK. 但 cert format vs 真 oracle
  Phase 1.5+ 产的 format 一致吗 (cert spec 写 Tuple[Tuple[Cell, Cell], ...] —
  python tuple, JSON serialize 后变 list)?
- Step D BFS 加 fail-safe (commodity_id != None → schema_err) — 但 cert spec
  04_component_reach.md 写 commodity_id 是 required 字段? 若是, 现 fail-closed
  跟 spec 抵触.
- Step E _all_poses_in_region_strict 调 helper, helper 返 None 时调用方 strict 返
  False → group 不 contributing. 但若 candidate_placements 在某 path 下确实 None
  (e.g. Phase 1.0 framework, P1.4 ramp 前 inject 还没完整), oracle 会 silent skip
  所有 group → F1 cut 完全不发. 这是 fail-closed 但 OFF switch 太硬 — 应该 fail-loud
  (raise 让 ramp catch)?

### 任务 C: GPT pro round 2 P0 + 必修 verdict

GPT pro round 2 列了 2 P0 + 7 必修. Step A-E 覆盖了哪些?
- 我 Step A 覆盖 必修 #3 (python -O 防线). ✓?
- 我 Step B 覆盖 P0-2 (F3 cert↔literal). ✓?
- 我 Step C 覆盖 必修 #4 (F2 cut_edges 集合验). ✓?
- 我 Step D 覆盖 必修 #5 (F4 commodity_id 不验存在). ✓ partially (我 fail-closed,
  不是 verify; 但 sound).
- 我 Step E 覆盖 P0-1 (F1 demand_R 真 P(g)⊆R). ✓?

未覆盖:
- 必修 #6: strict registration gate default ON (Phase 1.2 前 F1-F9 全注册).
  当前 `EXACT_FAMILY_VALIDATOR_STRICT` 默认 0, 在 P1.4 ramp 启动时设 1.
- 必修 #7: spec docs align (state_machine_v2 PoseId int→str / cut_lifecycle_v2
  9 family list / F2-F4 spec drift).

Verdict (3 选 1):
- "Phase 1.1 Step A-E production GO 推 Phase 1.2 — 必修 #6 #7 在 Phase 1.2 P1.11
  落地"
- "Step A-E GO 但发现新 critical (≥ 1) — 列 file:line 必修"
- "NOT GO, Step A-E 修不到位 — list 反例 / 漏修"

## 输出格式

3 段 A/B/C, cite file:line, ≥ 2000 字, 不准 vague.
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
    out_path = SHARE / "gemini_round_33_gpt_pro_fix_verify_response.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"Response written: {out_path} ({len(text):,} bytes)")
    print("\n---\n")
    print(text[:10000])
    if len(text) > 10000:
        print(f"\n... [{len(text)-10000} more bytes in file]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
