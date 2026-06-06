#!/usr/bin/env python3
"""Round 35 Gemini AUDIT mode — verify Step G fix landed (round 34 P0 perf + High commodity_id).

Round 34 verdict NOT GO 后 Step G (commit 3553efb):
- P0 perf fix: lru_cache(256) on _decode_region_bitset — 500x speedup
- High commodity_id fix: 移除 schema_err 改 spec-aligned 允许 carry

Defer (Phase 1.4+):
- by_exterior_watcher (sound 不需要; efficiency 优化)
- F3 multiset 自相矛盾 / F2 cut_edges list 脆弱 (Medium/Low)

验 Step G 是否真到位 + 是否引新 critical bug + 决定 Phase 1.1 production GO.

Output: /home/zhuran24/linwin_share/gemini_round_35_step_g_verify_response.md
"""
from __future__ import annotations

import os
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
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md",
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_34_step_f_verify_NOT_GO.md",
    "src/cuts/families/region_capacity.py",
    "src/cuts/families/component_reach.py",
    "src/cuts/lifecycle.py",
    "src/cuts/store.py",
    "src/tests/cuts/test_family_component_reach.py",
]


PROMPT = """\
# Round 35 Gemini AUDIT mode — verify Step G fix (round 34 P0 perf + High)

## 工作模式声明

AUDIT mode 跟 round 33/34 一致. 任务: 验 round 34 NOT GO catch 的 P0 性能
(F1 evaluate hot path O(|Grid|)) + High 升级 (F4 commodity_id 强拒 vs spec
必填) 在 Step G (commit 3553efb) 是否真修到位 + 是否引新 critical bug.

## Audit 强制规则

1. 拒 vague hyperbole. 用具体数字 / cite.
2. 每 claim 必 cite file:line.
3. GO 必先列 3 死法 + 反驳每一种.
4. 找 1 critical 比 100 surface 价值高 10×.
5. 找不到 critical 也必列 ≥ 5 high-risk hypothesis + 优先级.

## Round 34 verdict (3 fix target)

### P0 性能: F1 hot path O(|Grid|)
4900 iter Python 循环 + base64 + json.loads per propagator call. propagator
10K calls/sec → 49M iter/sec → solver 数量级退化.

### High 升级: F4 commodity_id 强拒 vs spec 必填
spec 04 §3 line 50 commodity_id 必填. Step D schema_err on carry → Phase
1.5+ Oracle 100% Quarantine.

### High 漏修: by_exterior_watcher (Step F 未做)
仍未 implement.

## Step G 修 (commit 3553efb)

### Fix 1: lru_cache P0 性能
- region_capacity.py 加 @lru_cache(maxsize=256) on _decode_region_bitset
- cert.region_cells_bitset_b64 content-addressed (cert hash 锁) → 同 b64
  反复调 → 第一次 4900 iter, 后续 O(1) hit
- 实测: 10K calls 1.11ms (avg 0.11µs/call cached, hits=9999/10000) — 500x

### Fix 2: F4 commodity_id spec-aligned
- component_reach.py validator step 8 移除 schema_err
- spec 04 §3 line 50 commodity_id 必填 — 现允许 carry
- soundness 不依赖 (BFS connectivity 不看 commodity name); attacker fake
  不影响 src/sink_component bitset 严等 + separator_cells 验
- commodity_route verifier 真验存在 defer Phase 1.5+

### Defer (Phase 1.4 ramp)
- by_exterior_watcher: sound 不需要 (evaluate 重算保 cut sound). watcher
  是 efficiency (减 propagator evaluator 调用). Phase 1.5+ Step 8 lazy→
  hard constraint 时必须实施.
- F3 multiset 自相矛盾 / F2 cut_edges list 脆弱: Medium/Low syntax/brittle

## 任务

### 任务 A: 验 Step G 2 fix 是否 sound + 完整

cite file:line:

- Fix 1 lru_cache:
  - region_capacity.py 现 _decode_region_bitset 真加 @lru_cache(maxsize=256)?
  - cache key 是 b64 str — content-addressed 不会 stale (cert hash 锁定 →
    内容不变)?
  - 256 maxsize 真够? Phase 1.1 ramp active cut count 估?
  - 内存 leak risk? lru_cache 持 frozenset 引用 — 256 cap 上限内存?
  - thread-safe? Python 3.13 lru_cache 是否 GIL-aware (functools 实施)?
- Fix 2 F4 commodity_id:
  - component_reach.py 现 step 8 真移除 schema_err 改 ok pass-through?
  - cert.commodity_id 是 metadata 路径, 几何 soundness 由 src/sink_component
    + separator_cells 保 — 验真?
  - 攻击面: attacker fake commodity_id 不影响 sound 但可能 spread misinfo —
    metadata 进 audit trail 时被读? defer 风险评估?

### 任务 B: 找 Step G 引入新 bug 或剩余 finding 升 P0 (≥ 5)

- lru_cache(256) 在 module level — module reload (e.g. test isolation,
  pytest fixture rebuild) cache 不 clear → state pollution?
- cache 持 frozenset (FrozenSet[Cell]) 占 mem — 70x70 cell × 256 entry ≈
  4900 × 8 bytes × 256 = ~10MB upper bound. 接受?
- lru_cache key 用 hashable (b64 str + grid_size int), thread-safe via
  GIL — Phase 1.5+ multi-thread propagator 时 cache 仍 work?
- F4 commodity_id 现 pass-through — attacker 谎报 commodity_id="critical_path"
  让 quarantine audit detail 写 misleading message. 不影响 cut sound 但
  audit 信号失真?
- watcher 漏修 still 是 efficiency P1, 不 sound P0. ramp 测压力下退化是否
  acceptable (10K calls/sec × 0.11µs = 1.1ms/sec, 0.1% CPU)?

### 任务 C: Phase 1.1 production GO verdict

合并 round 33/34/35 verdict:
- Step A-G 所有 P0 + High close?
- 必修 #6 (strict registration gate default ON) #7 (spec docs align):
  Phase 1.2 P1.11 落地前必修?
- watcher 缺 acceptable defer Phase 1.4 ramp?

Verdict (3 选 1):
- "Phase 1.1 Step A-G production GO 推 Phase 1.2 — 必修 #6 #7 在 P1.11"
- "Step A-G GO 但发现新 P0 — list file:line 必修"
- "NOT GO, Step G 修不到位 — list 反例 / 漏修"

## 输出格式

3 段 A/B/C, cite file:line, ≥ 1500 字, 不准 vague.
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
    out_path = SHARE / "gemini_round_35_step_g_verify_response.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"Response written: {out_path} ({len(text):,} bytes)")
    print("\n---\n")
    print(text[:10000])
    if len(text) > 10000:
        print(f"\n... [{len(text)-10000} more bytes in file]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
