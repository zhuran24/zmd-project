#!/usr/bin/env python3
"""Round 27 Gemini cross-check — P1.1 src/cuts/lifecycle.py 跟 v3.2.2 spec 一致性.

Per /goal v3: "任何决策性输出必 Gemini 审查 (算法/数学/schema 层)".

P1.1 是 spec→src 翻译, 不引入新 algorithm. cross-check 验:
1. CutScope.exterior_blocks_hash 字段 + Step 3 dispatch 跟 cut_lifecycle_v2 v3.2.2 一致?
2. 9-family map 跟 PHASE_0_CLOSE final state 一致?
3. Step 2 / Step 8 stub 措辞合理 (有明确 defer pointer)?
4. __post_init__ schema-first 强制 (XOR + family map + scope/cert 必填) 严不严?
5. Step 5 validator 跟 Family 1 v1.2 spec 一致?

Output: /home/zhuran24/linwin_share/gemini_round_27_p1_1_src_response.md
"""
from __future__ import annotations

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
    # spec — v3.2.2 dispatch + 9 family final
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
    "docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md",
    # src 实施
    "src/cuts/lifecycle.py",
    "src/tests/cuts/test_lifecycle.py",
    # plan ref
    "docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md",
]


PROMPT = """\
# Round 27 Gemini cross-check — P1.1 src 跟 v3.2.2 spec 一致性

## 背景

之前 26 round Gemini cross-check 把 B Design v2 Phase 0 (9-family + cut_lifecycle
v3.2.2 + state_machine_v2 + 5 fixture + PROJECT_LOCK §2B/§3A/§4) 全 verify 完,
round 26 verdict "Phase 1 编码 GO, 不再 cross-check 此层".

现在 Phase 1.0 P1.1 起步: 把 docs/research/.../poc/b_core_lifecycle_poc.py
(PoC 14/14 PASS) 迁到 src/cuts/lifecycle.py + 加 production 调整:

1. 9-family map (vs PoC 8-family with symmetry_lift). symmetry_lift 删,
   加 power_grid_reach (F8) + density_envelope (F9) (PHASE_0_CLOSE final).
2. CutScope.exterior_blocks_hash 新加字段 (v3.2.2 round 21 fix).
   Step 3 (attach-scope check) GHOST_AGNOSTIC dispatch:
   - GHOST_AGNOSTIC cut: verify exterior_blocks_hash only (cut 跨 ghost 复用)
   - ghost-bound cut: verify full blocked_cells_hash
3. __post_init__ schema-first 强制: literals XOR geometric_payload + 9-family
   map check + scope/cert 必填.
4. Step 2 (minimize) / Step 8 (apply-to-master) stub: NotImplementedError +
   defer pointer (Phase 1.1 P1.11 / Phase 1.3 P1.21).

Tests: 17/17 PASS, 覆盖 schema + 全 9 步 lifecycle + v3.2.2 dispatch 双分支.
Full pytest src/tests/: 2254 passed, 60 skipped (无 regression).

## 任务

任务 A: 验 src 跟 v3.2.2 spec 严格一致

1. **CutScope.exterior_blocks_hash 字段** + Step 3 dispatch (step_6_attach_scope_check)
   跟 cut_lifecycle_v2 v3.2.2 §4 一致吗? 漏 edge case?
   - GHOST_AGNOSTIC 路径不 check blocked_cells_hash 而 check exterior_blocks_hash 对吗?
   - ghost-bound 路径 check 完整 blocked_cells_hash 对吗?

2. **9-family map** (_FAMILY_MODE_MAP) 跟 PHASE_0_CLOSE final state 一致?
   - F1 region_capacity / F2 cutset / F3 port_exposure / F4 component_reach /
     F5 pattern_nogood / F6 shape_packing_hall / F7 power_hitting_set /
     F8 power_grid_reach / F9 density_envelope
   - 每个 family 的 mode (literal/geometric) 跟 spec 标注一致?

3. **__post_init__ schema-first 强制** 严不严?
   - literals XOR geometric_payload OK?
   - family in 9-family map OK?
   - scope + cert 必填 OK?

4. **Step 5 F1 validator** (step_5_validate_region_capacity) 跟 Family 1 v1.2
   spec §7 一致? cap_R static + cells_per_pose source-of-truth + witness check?

5. **Step 2 / Step 8 stub** 措辞 OK? defer pointer 清晰?
   - Step 2: "Phase 1.1 P1.11 (F5 pattern_nogood)"
   - Step 8: "Phase 1.3 P1.21 (benders_loop integration)"

## 任务 B: 找 Phase 1 实施盲区

P1.1 落地后, Phase 1.0 P1.2 (CutStore + 6 维 watcher) / P1.3 (replay 6 步) /
P1.4 (helpers + ASSUMPTION_VERIFIERS) 还有哪些 spec → src 翻译盲区?

如:
- AnonymousSlotRef + group_id/slot_index 在 src 跟 state_machine_v2 §2 schema 一致?
- ASSUMPTION_VERIFIERS dispatch 留了 stub (return True), Phase 1.4 实施时盲区?
- run_lifecycle helper 在 P1.2+ store 接 add_cut 后是不是应该 deprecate?

## 任务 C: P1.1 verdict

如 P1.1 完全跟 spec 一致 + 测试覆盖够 + 没找到 Phase 1 实施盲区 → 写 "P1.1 PASS,
继续 P1.2". 如有任何 finding (致命 / non-critical / 工程提示) → 列详细.

## 输出格式

按 3 段 A/B/C 输出, 每段开头标 **段名**. 中文优先. 找不到 finding 写 "无 finding,
P1.1 GO" 不要硬找凑数 (round 14-22 已多次扫, 不再期望大发现).
"""


def fetch_doc(path: str) -> str:
    p = REPO / path
    if not p.exists():
        return f"[MISSING: {path}]"
    return p.read_text(encoding="utf-8")


def build_prompt() -> str:
    parts = [PROMPT, "\n\n## Reference Materials\n"]
    for dp in DOC_PATHS:
        content = fetch_doc(dp)
        parts.append(f"\n\n### --- {dp} ---\n\n{content}\n")
    return "".join(parts)


def call_gemini(prompt: str) -> dict:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 16384,
        },
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
    out_path = SHARE / "gemini_round_27_p1_1_src_response.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"Response written: {out_path} ({len(text):,} bytes)")
    print("\n---\n")
    print(text[:3000])
    if len(text) > 3000:
        print(f"\n... [{len(text)-3000} more bytes in file]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
