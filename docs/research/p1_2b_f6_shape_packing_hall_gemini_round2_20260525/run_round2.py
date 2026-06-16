#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F6 shape_packing_hall Gemini round 2 cross-check.

Verifies R1 fix correctness + pushes for round 2 new finding (v3 loop protocol).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.request


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


SRC_FILES = [
    "src/cuts/helpers/baseline_partition.py",
    "src/cuts/families/shape_packing_hall.py",
    "src/cuts/oracles/shape_packing_hall_oracle.py",
]


PROMPT = """你是 Hall's marriage theorem / combinatorial cut / soundness 审查员。Endfield 工业规划求解器 Phase 1.2 P1.2B-F6 **Round 2** cross-check (commit `9fac6d6`).

# Round 1 finding 摘要 + fix (round 2 重点 verify)

Round 1 verdict: NOT_GO. 4 finding + Gap A/B.

- **R1#1 CRITICAL fail-open**: `_validate_facility_template_match` 缺
  facility_templates 时 skip check → adversary 注 fake pose_length 绕过.
  **Fix landed**: 全 fail-closed (state.instance_to_facility_type None → unsound;
  state.facility_templates None → unsound; facility_type 不在 templates → unsound).
- **R1#2 HIGH evaluator 冗余**: v1.1 partition 只依赖 ghost+exterior 都 scope-bound,
  active cut 必 scope-match → recomputed partition byte-equal cert → 重算白干.
  **Fix landed**: evaluator O(1) (trust `cert.total_packable < cert.region_demand`,
  schema check pass after malformed payload).
- **R1#3 MEDIUM watcher region_id format**: `f"shape_packing_hall:{region_kind}"`
  → spec §8 要求 `f"{region_kind}:shape_hall"`. **Fix landed**: format 跟 spec.
- **R1#4 MEDIUM (0,0) corner overlap**: left + bottom 共 (0,0), Phase 1.5+
  multi-region union defer (spec §10 #5).

- **Gap A**: spec §5b drift (remaining_count vs group.demand) — src 跟 v1.1 intent,
  spec doc update defer.
- **Gap B CONFIRMED**: default `region_demand = min(group.demand, region_cap)` 是
  FP. **Fix landed**: Phase 1.2 default region_demand=1 (只 fully-blocked emit);
  Phase 1.5+ override 提真 region_demand; override 超 min(group_demand, region_cap)
  跳 (避免 cert validator phase 7 reject).

# Round 2 任务

按 v3 loop: round 2 重点 verify R1 fix 是否正确 + push 找新 finding (不接受
GO ritual).

1. **Verify R1#1 fail-closed**:
   - 3 layer (instance_to_facility_type / facility_templates / facility_type
     not in templates) 全 unsound — 真没漏路径?
   - 若 attacker 提交 cert 没 schema_err, validator 走到 phase 8 ↔
     facility_templates check, fail-closed. 但有没有更早 phase (e.g. phase 4
     scalars) 漏 catch 让 phase 8 不到达?
2. **Verify R1#2 evaluator O(1)**:
   - 真的 active cut 一定 scope-match 吗? evaluator 被 step_7_evaluate_cut
     从 lifecycle.py 调, 而 step_6_attach_scope_check 是 step_7 前一步 — 但
     evaluator 也可能在 propagation 中被 caller 不经 step_6 直接调? 检查
     `lifecycle.step_7_evaluate_cut` caller chain.
   - 若 cut 在 hold 状态 (e.g. ghost just changed, by_ghost_watcher 拉出),
     evaluator 可能被调时 ghost ≠ cert.ghost_rect_repr. 这时 trust cert
     return True 是 FP (cut 不该 active 但 evaluator 说还 violating).
3. **Verify R1#3 watcher format**:
   - cut store 内 by_region_watcher 看 region_id, F6 跟 spec align 现在 OK.
     但有没有其他 family 用 `family:region` 老 format, 重命名 break?
4. **Verify Gap B conservative default**:
   - region_demand=1 + total_packable=0 严格 < ⇒ emit. 真生产 ghost+exterior
     完全覆盖 baseline 是 trivial dead state — emit 是 sound 没争议. 但
     **有没有 case** ghost+exterior 完全覆盖但 master 没 boundary 需求
     (group.demand=0)? generator 已 skip group_demand<1 — verify.
5. **Round 2 new finding**: 至少 2 个 (不接 0). 任何 severity.

## Armor 同 round 1

- 不接受 vague hyperbole
- GO verdict 必先列 3 死法 + disprove
- critical claim 必 cite file:line

## Format (严格不要 think-out-loud)

```
## Round 2 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO (一行)

## R1 Fix Verify

- R1#1 fail-closed (3 layer): CORRECT / PARTIAL / WRONG / NEW_GAP — 详释
- R1#2 evaluator O(1): CORRECT / PARTIAL / WRONG / NEW_GAP — 详释 (含 active-cut 假设是否真 hold)
- R1#3 watcher format: CORRECT / PARTIAL / WRONG / NEW_GAP — 详释
- Gap B conservative default: CORRECT / PARTIAL / WRONG / NEW_GAP — 详释

## Round 2 New Findings (≥2, 任何 severity)

### Finding 1: [SEVERITY] file:line — title
≤ 200 字.

### Finding 2: ...

## Sanity (≥3 disproved hypothesis with file:line)

## 下一步建议
```
"""


def build_src_section() -> str:
    s = ["# F6 src (current, full content inline)\n\n"]
    for rel in SRC_FILES:
        s.append(f"### FILE: {rel}\n```python\n")
        s.append(read(rel))
        s.append("\n```\n\n")
    return "".join(s)


def main() -> int:
    key = os.environ.get("KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("ERROR: set KEY=<api_key> in env.", file=sys.stderr)
        return 2

    prompt_text = (
        PROMPT
        + build_src_section()
        + "\n\n# 完. 严格 format.\n"
    )

    (HERE / "prompt.txt").write_text(prompt_text, encoding="utf-8")
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": 0.3,
            "topP": 0.95,
            "maxOutputTokens": 32768,
        },
    }
    (HERE / "prompt.json").write_text(json.dumps(payload), encoding="utf-8")

    print(f"prompt length: {len(prompt_text)} chars")
    print("calling Gemini ...")
    t0 = time.monotonic()
    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            body = r.read().decode("utf-8")
    except Exception as e:
        print(f"API call failed: {e!r}", file=sys.stderr)
        return 1
    print(f"Gemini responded in {time.monotonic() - t0:.1f}s")

    (HERE / "gemini_response_raw.json").write_text(body, encoding="utf-8")
    parsed = json.loads(body)
    try:
        verdict_text = parsed["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        print("Failed to extract text:", parsed, file=sys.stderr)
        return 1
    (HERE / "gemini_response.md").write_text(verdict_text, encoding="utf-8")
    print(f"Response written ({len(verdict_text)} chars).")
    print("---")
    print(verdict_text[:3500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
