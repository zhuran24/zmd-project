#!/usr/bin/env python3
"""Round 34 Gemini AUDIT mode — verify Step F fix landed (round 33 P0 + High).

Round 33 verdict NOT GO 后我做 Step F (commit e0ec660):
- P0 fix: F1 evaluate_geometric_region_capacity 真重算 cap_R 不无条件 True
- High fix: F4 validator 加 separator_cells ∈ free_cells → unsound check

验 Step F 是否真到位 + 是否引新 bug + 剩 Medium/Low finding (Step D commodity_id /
F2 cut_edges list 脆弱性 / F3 multiset 矛盾 cut) 是否影响 production GO.

Output: /home/zhuran24/linwin_share/gemini_round_34_step_f_verify_response.md
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
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md",
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_audit_round2_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_33_gpt_pro_fix_verify_NOT_GO.md",
    # Step F 修后 src
    "src/cuts/families/region_capacity.py",
    "src/cuts/families/component_reach.py",
    "src/cuts/families/cutset.py",
    "src/cuts/families/port_exposure.py",
    "src/cuts/oracles/region_capacity_oracle.py",
    "src/cuts/helpers/candidate_placements.py",
    "src/cuts/store.py",
    "src/cuts/replay.py",
    "src/cuts/lifecycle.py",
    # 测试
    "src/tests/cuts/test_family_region_capacity.py",
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

    union_cells = {(x, 0) for x in range(70)} | {(0, y) for y in range(70)}
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
    parts.append(f"\n### boundary_storage_port pose: total={len(bsp)} in={n_in} out={n_out} mixed={n_mixed}\n")
    return "".join(parts)


PROMPT = """\
# Round 34 Gemini AUDIT mode — verify Step F fix (round 33 P0 + High)

## 工作模式声明

AUDIT mode 跟 round 33 一致 — 不是 GO 章 ritual. 任务: 验 round 33 NOT GO catch
的 P0 (F1 evaluate 永返 True 不 sound) + High (F4 separator_cells 漏验) 在 Step F
(commit e0ec660) 是否真修到位 + 是否引新 critical bug.

## Audit 强制规则

1. **拒 vague hyperbole** (完美 / 完全一致 / 绝佳 等不准说). 用具体数字 / cite.
2. **每 claim 必 cite file:line** + 跟真数据具体 key/value 对比.
3. **GO 必先列 3 死法 + 反驳每一种**. 不准只说"看着对就 GO".
4. **找 1 critical 比 100 surface 价值高 10×**.
5. **找不到 critical 也必列 ≥ 5 high-risk hypothesis** + 优先级标注.

## Round 33 verdict (2 fix target)

### P0: F1 evaluate_geometric_region_capacity 永返 True (Unsound)
死法:
1. 初始 exterior_blocks=2, oracle 产 F1 cut (cap_R=137 < demand=138)
2. master 回溯移除 2 exterior_blocks → cap_R 恢复 139 ≥ demand=138
3. cut 已 attach, propagator 调 evaluate_geometric_region_capacity
4. 永返 True → emit constraint → 假剪合法 state

### High: F4 漏验 separator_cells (spec 04 line 148)
spec 明定 "验 separator_cells 全在 (cell_owner ∪ ghost) (不是 free)".
Step D validator 完全跳过.

## Step F 修 (commit e0ec660)

### Fix 1: F1 evaluate 真重算
src/cuts/families/region_capacity.py evaluate_geometric_region_capacity:
- 解 cert.geometric_payload 拿 region_cells_bitset
- decode region_cells (FrozenSet[Cell])
- current_cap = compute_static_capacity(region_cells, state)
- return cert.demand_R > current_cap (不 violate 则 False)

Regression test: test_evaluate_recomputes_cap_R_after_exterior_blocks_removed
- 验 exterior_blocks=2 → True / exterior_blocks=0 → False

### Fix 2: F4 separator_cells check
src/cuts/families/component_reach.py validator step 7:
- 遍历 cert.separator_cells, 若 sep_cell ∈ free_cells → unsound

Regression: test_validator_unsound_separator_cell_in_free / test_validator_ok_separator_in_ghost_or_owner

156 cuts test pass.

## 任务

### 任务 A: 验 Step F 2 fix sound + 完整

逐 fix verify cite file:line:

- Fix 1 F1 evaluate 重算:
  - region_capacity.py 现 evaluate_geometric_region_capacity 实施验真重算 cap_R?
  - compute_static_capacity 公式跟 oracle 一致 (|R| - |(ghost ∪ exterior) ∩ R|)?
  - cert.demand_R 锁定 oracle 时 — 但 cert.demand_R 跟 state.groups[gid].demand
    × cpp 不变是否成立? 若 master 改 group.demand (e.g. instance pruning), demand_R
    跟 cert 偏离, evaluate 还 sound 吗?
  - exception handling fail-safe 返 False — propagator skip — 合理?
- Fix 2 F4 separator_cells:
  - validator step 7 真遍历 cert.separator_cells + 判 sep_cell ∈ free_cells?
  - spec 04 line 148 wording 跟 src 一致?
  - cert.separator_cells field 默认 [] 时不 trigger check (back-compat)?

### 任务 B: 找 Step F 引入新 bug 或 round 33 剩 Medium/Low 是否升级 (≥ 5)

- Step F 引新 bug: evaluate 重算时 region_cells 用 _decode_region_bitset(70x70)
  hardcoded — grid_size mismatch 会 silent corruption?
- F1 evaluator 现 O(|R|) per call (70x70 = 4900 cell decode + ghost set intersection).
  propagator hot path 调多频, performance impact ramp 测?
- round 33 Medium 1 (F3 multiset 自相矛盾 cut, lifecycle.py:610): 这 cert syntax
  允许同 slot 不同 pose. 实际是否 sound (cert claim "slot=0 既 p1 又 p2" 不可
  解但 cert 内 multiset 仍 catch 客观几何冲突)?
- round 33 Medium 2 (F4 commodity_id 强拒 vs spec 必填字段): Phase 1.5+ Oracle
  按 spec 上线 100% F4 cut Quarantine 风险还在? 现在该升 P0 吗?
- round 33 Low (F2 cut_edges list 脆弱) — JSON schema 如果改 dict 静默 hash 碰撞,
  defer 是否合理?

### 任务 C: GPT pro round 2 + 此轮 Phase 1.1 production verdict

- Phase 1.1 Step A-F 是否所有 P0 + High 都 close?
- 必修 #6 (strict registration gate default ON) 跟 #7 (spec docs align) 未做 — 是否
  Phase 1.2 P1.11 落地前必须先做?
- F4 commodity_id (round 33 Medium 2) 是 Phase 1.5+ schema drift, defer?

Verdict (3 选 1):
- "Phase 1.1 Step F GO 推 Phase 1.2 — 剩 Medium/Low 在 Phase 1.2 P1.11 同步修"
- "Step F GO 但 round 33 Medium 升级 P0 (e.g. F4 commodity_id) 必修"
- "NOT GO, Step F 修不到位 / 新 P0 出现 — list file:line 必修"

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
    out_path = SHARE / "gemini_round_34_step_f_verify_response.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"Response written: {out_path} ({len(text):,} bytes)")
    print("\n---\n")
    print(text[:10000])
    if len(text) > 10000:
        print(f"\n... [{len(text)-10000} more bytes in file]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
