"""F3 malformed cert fail-closed micro-probe — GPT 八审 V21-8F1 lock.

Verify ``_cert_literal_pairs`` 在 9 类 malformed F3 cert payload 下都
fail-closed return [] (6 类: 缺字段 / 坏 padding / 空 / list / str root;
+ GPT 第九审加的 3 类: 合法 b64 混入垃圾字符 prefix/suffix/middle), 而不是
fallback 合成 3-literal synthetic, 也不 raise AttributeError. 同时验证 3 类
non-F3 family 不受 fix 影响, fallback 合成行为保持.

Run:
    .venv/bin/python scripts/spike_prod_scale_lib/test_toy_translator_f3_malformed.py

Exit 0 = 12/12 case PASS; exit 1 = 任一 case FAIL (FATAL, do not commit).

Per [[review-pkg-data-completeness]]: fail-closed coverage 必须有 test 锁
住跟着 review-pkg 入包让 reviewer 源码级看到. 这文件 spike-only, off-limits
check 不会被 trigger (位于 scripts/spike_prod_scale_lib/ 白名单).
"""
from __future__ import annotations

import base64
import json
import sys
from typing import List, Tuple

from toy_translator import _cert_literal_pairs


# 固定 fallback pool — 用全 (`C`, `p2`), (`B`, `p1`), (`D`, `p3`) 让 non-F3
# fallback 合成时输出可预测顺序 (hash(cut_id) 决定 sample idx 的 deterministic
# 排列). pool 顺序无关 F3 fail-closed verify, 只服务 non-F3 assertion 可读.
FALLBACK_POOL: List[Tuple[str, str]] = [
    ("A", "p0"),
    ("B", "p1"),
    ("C", "p2"),
    ("D", "p3"),
    ("E", "p4"),
]


def _b64(obj) -> str:
    return base64.b64encode(json.dumps(obj).encode("utf-8")).decode("ascii")


def _make_cert(family: str, payload_obj, cut_id: str = "cut-test") -> dict:
    if payload_obj is None:
        b64 = ""
    elif isinstance(payload_obj, str) and payload_obj == "__BAD_B64__":
        b64 = "!!!not_valid_base64!!!"
    else:
        b64 = _b64(payload_obj)
    return {"family": family, "cert_payload_b64": b64, "cut_id": cut_id}


def _run_case(name: str, cert: dict, expected_kind: str, expected_value=None) -> bool:
    """expected_kind ∈ {empty, exact, fallback_3}."""
    try:
        got = _cert_literal_pairs(cert, FALLBACK_POOL)
    except Exception as e:
        print(f"  [FAIL] {name}: raised {type(e).__name__}: {e}")
        return False

    if expected_kind == "empty":
        ok = got == []
    elif expected_kind == "exact":
        ok = got == expected_value
    elif expected_kind == "fallback_3":
        # non-F3 fallback path returns deterministic 3 pairs from FALLBACK_POOL
        ok = isinstance(got, list) and len(got) == 3 and all(p in FALLBACK_POOL for p in got)
    else:
        raise RuntimeError(f"unknown expected_kind: {expected_kind}")

    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}: got={got!r}")
    return ok


def main() -> int:
    print("F3 malformed micro-probe (GPT 八审 V21-8F1 lock)")
    print("=" * 70)

    results = []

    # ----- F3 family: 6 case -----
    print("\n[F3 port_exposure family]")

    # 1) valid_f3 — 完整合规 payload, expect 2-literal exact
    valid_payload = {
        "facility_group": "facA",
        "facility_pose_id": "poseA",
        "blocking_facility": ["facB", "unused_idx_1", "poseB"],
    }
    results.append(_run_case(
        "valid_f3",
        _make_cert("port_exposure", valid_payload),
        "exact",
        [("facA", "poseA"), ("facB", "poseB")],
    ))

    # 2) invalid_f3_missing — F3 family 但 field 全缺, expect []
    results.append(_run_case(
        "invalid_f3_missing",
        _make_cert("port_exposure", {"some_other_field": 42}),
        "empty",
    ))

    # 3) invalid_f3_bad_b64 — base64 decode fail, expect [] (不 fallback)
    results.append(_run_case(
        "invalid_f3_bad_b64",
        _make_cert("port_exposure", "__BAD_B64__"),
        "empty",
    ))

    # 4) root_null — payload b64 empty string → _decode_cert_b64 → None
    results.append(_run_case(
        "root_null",
        _make_cert("port_exposure", None),
        "empty",
    ))

    # 5) root_list — payload 是 list 不是 dict, _decode 应 isinstance guard 走
    #    return None → F3 → []
    results.append(_run_case(
        "root_list",
        _make_cert("port_exposure", [1, 2, 3]),
        "empty",
    ))

    # 6) root_string — payload 是 str 不是 dict, 同样 isinstance guard 拦
    results.append(_run_case(
        "root_string",
        _make_cert("port_exposure", "i_am_a_string_payload"),
        "empty",
    ))

    # 7-9) F3 + 合法 b64 中混入非 alphabet 垃圾字符 (prefix/suffix/middle)。
    #      GPT 第九审 finding: 不带 validate=True 的 b64decode 会静默丢弃这些字符,
    #      于是 "看起来坏但仍能解码" 的 payload 不 fail-closed。修后 validate=True
    #      → 任何垃圾字符 raise → None → F3 return []。
    _valid_b64 = _b64(valid_payload)
    for _name, _bad in [
        ("f3_garbage_prefix", "!!!!" + _valid_b64),
        ("f3_garbage_suffix", _valid_b64 + "!!!!"),
        ("f3_garbage_middle", _valid_b64[:8] + "!!!!" + _valid_b64[8:]),
    ]:
        results.append(_run_case(
            _name,
            {"family": "port_exposure", "cert_payload_b64": _bad, "cut_id": "cut-test"},
            "empty",
        ))

    # ----- Non-F3 family: 3 case (verify fix 不破 fallback) -----
    print("\n[Non-F3 families — fallback path must keep working]")

    # 7) non_f3_witness — pattern_nogood + valid oracle_assignment_witness,
    #    应走 Strategy 1 parse witness 不进 fallback
    witness_payload = {
        "oracle_assignment_witness": [["G1", "P1"], ["G2", "P2"]],
    }
    results.append(_run_case(
        "non_f3_witness",
        _make_cert("pattern_nogood", witness_payload, cut_id="cw-1"),
        "exact",
        [("G1", "P1"), ("G2", "P2")],
    ))

    # 8) non_f3_bad_b64 — pattern_nogood + bad b64 → payload=None → 走
    #    fallback synthesize 3-literal (non-F3 family OK 合成)
    results.append(_run_case(
        "non_f3_bad_b64",
        _make_cert("pattern_nogood", "__BAD_B64__", cut_id="cn-bad-2"),
        "fallback_3",
    ))

    # 9) non_f3_list — pattern_nogood + payload 是 list → 现在 isinstance
    #    guard 也 return None → 走 fallback synthesize 3-literal (non-F3
    #    family 行为不变, fix 兼容)
    results.append(_run_case(
        "non_f3_list",
        _make_cert("pattern_nogood", [9, 8, 7], cut_id="cn-list-3"),
        "fallback_3",
    ))

    # ----- Summary -----
    n_pass = sum(results)
    n_total = len(results)
    print("\n" + "=" * 70)
    print(f"Summary: {n_pass}/{n_total} PASS")
    if n_pass == n_total:
        print(f"Verdict: {n_pass}/{n_total} PASS — F3 fail-closed contract intact, fallback unaffected.")
        return 0
    print("Verdict: FAIL — F3 fail-closed contract broken, DO NOT COMMIT.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
