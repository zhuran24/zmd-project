#!/usr/bin/env python3
"""完整性批评-内核-2：独立按受限转移定义§6.2的字段表重写生产键，核证书自洽。

本脚本不读 cycle.rs，只读 受限转移定义.md §6.2 的规定；用于检验证书里的
start_key/end_key 是否真的由 start_state/end_state 按该表算出，以及两键是否相等。
"""
import json, sys
from fractions import Fraction
from pathlib import Path

ORES = ["源矿", "蓝铁矿"]
PRODUCTS = ["高容谷地电池", "精选荞愈胶囊"]


def rational(s):
    f = Fraction(s)
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def normalize(v):
    """§6.2：Quantity 去 category 并约分；Decision 去 basis。"""
    if isinstance(v, list):
        return [normalize(x) for x in v]
    if isinstance(v, dict):
        if len(v) == 2 and "value" in v and "category" in v:
            return {"value": rational(v["value"])}
        o = {k: x for k, x in v.items()}
        if "status" in o:
            o.pop("basis", None)
        return {k: normalize(x) for k, x in o.items()}
    return v


def instant(t):
    return int(Fraction(t["value"]["value"]))


def tv(n):
    return {"kind": "rational", "value": {"category": "算术推论", "value": str(n)}}


def key(state):
    s = json.loads(json.dumps(state))
    t = instant(s["environment"]["time"])
    jc = s["semantic_context"]["judgment_context"]["value"]
    assert jc["phase"] == "after_closure" and jc["order_scope"] == "global", jc
    assert jc.get("next_event") is None and "continuation" not in jc, jc
    assert s["semantic_context"]["arbitration"]["warehouse_empty_slot_order"] == []
    # 仓库：两成品整行移出；两矿 quantity → sufficient；按 slot 排序
    slots = [r for r in s["warehouse"]["slots"]
             if (r.get("item") or (r.get("empty_identity") or {}).get("value")) not in PRODUCTS]
    for r in slots:
        if r.get("item") in ORES:
            r["quantity"] = {"value": "sufficient"}
    s["warehouse"]["slots"] = sorted(slots, key=lambda r: r["slot"])
    # 库存：entered_at → age；contents 按 (item, entered_at) 排序；行按 slot 排序
    for row in s["inventory"]:
        for c in row["contents"]:
            if c.get("entered_at") is not None:
                c["entered_at"] = {"age": {"value": str(t - instant(c["entered_at"]))}}
        row["contents"].sort(key=lambda c: (c["item"], json.dumps(c["entered_at"], sort_keys=True,
                                                                 ensure_ascii=False)))
    s["inventory"].sort(key=lambda r: r["slot"])
    for row in s["progress"]:
        row["candidate_recipes"].sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        row["cooldowns"].sort(key=lambda r: (r["slot"] is not None, r["slot"] or ""))
    s["progress"].sort(key=lambda r: r["unit"])
    lg = s["logistics"]
    for k in ("active_channels", "blocked_channels"):
        lg[k].sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    sides = lg["poll_memory"]["value"]["sides"]
    sides.sort(key=lambda r: (r["unit"], r["side"]))
    for r in sides:
        r["levels"].sort(key=lambda x: x["id"])            # members 的接通环原序不排序
    for r in lg["gate_counters"]:
        r["blocked_reasons"].sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        if r.get("window_started_at") is not None:
            r["window_started_at"] = {"elapsed": {"value": str(t - instant(r["window_started_at"]))}}
    lg["gate_counters"].sort(key=lambda r: r["unit"])
    s["environment"]["time"] = tv(0)
    sc = s["semantic_context"]
    sc["parameter_values"].sort(key=lambda r: r["axis"])
    sc["judgment_context"]["value"] = {"instant": tv(0), "phase": "after_closure",
                                       "order_scope": "global"}
    for r in sc["pending_events"]["value"]:
        assert set(r["trigger"]) == {"kind", "value"} and r["trigger"]["kind"] == "at_time"
        assert r["predecessors"] == [] and r["status"] == "waiting"
        assert r["operation"] in ("manufacture_complete", "gate_window_expiry")
        rem = instant(r["trigger"]["value"]) - t
        r["event"] = [r["operation"], r["target"], str(rem)]
        r["trigger"]["value"] = tv(rem)
    sc["pending_events"]["value"].sort(
        key=lambda r: (json.dumps(r["operation"], ensure_ascii=False),
                       json.dumps(r["target"], ensure_ascii=False),
                       json.dumps(r["trigger"]["value"]["value"]["value"], ensure_ascii=False)))
    tc = sc["tick_context"]["value"]
    for k in ("window_start", "window_end"):
        tc[k] = tv(instant(tc[k]) - t)
    assert instant(tc["window_start"]) == 0 and instant(tc["window_end"]) == 1
    tc["port_usage"] = sorted([r for r in tc["port_usage"]
                               if Fraction(r["quantity"]["value"]) != 0],
                              key=lambda r: r["port"])
    tc.pop("movements", None)
    tc.pop("internal_passages", None)
    return {"schema": "production-cycle-key-v1", "domain": "production_v1",
            "state": normalize(s),
            "product_acceptance": [{"item": i, "state": "under_capacity"} for i in PRODUCTS]}


def canon(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def main(path):
    d = json.load(open(path))
    c = d["cycle"]
    out = {"certificate": str(path), "status": d["status"], "level": d["level"],
           "period": c["period"]["value"]}
    ks, ke = key(c["start_state"]), key(c["end_state"])
    out["start_key_matches_recomputed"] = canon(ks) == canon(c["start_key"])
    out["end_key_matches_recomputed"] = canon(ke) == canon(c["end_key"])
    out["start_key_equals_end_key"] = canon(c["start_key"]) == canon(c["end_key"])
    out["start_time"] = instant(c["start_time"])
    out["end_time"] = instant(c["end_time"])
    out["period_matches_times"] = (out["end_time"] - out["start_time"]
                                   == int(c["period"]["value"]))
    out["ledger_rows"] = len(c["ledger"])
    out["ledger_rows_match_period"] = len(c["ledger"]) == int(c["period"]["value"])
    # 台账复算：周期内逐刻逐物种求和，与 totals 比较
    agg = {}
    for row in c["ledger"]:
        for tot in row["warehouse_ledger"]["totals"]:
            a = agg.setdefault(tot["item"], {})
            for f in ("actual_inbound", "core_inbound", "wireless_inbound",
                      "external_supply", "port_outbound", "player_withdrawal",
                      "representative_adjustment"):
                a[f] = a.get(f, Fraction(0)) + Fraction(tot[f]["value"])
    mismatch = []
    for tot in c["totals"]:
        a = agg.get(tot["item"], {})
        for f, v in a.items():
            if Fraction(tot[f]["value"]) != v:
                mismatch.append((tot["item"], f, tot[f]["value"], str(v)))
        if a.get("actual_inbound") != a.get("core_inbound", 0) + a.get("wireless_inbound", 0):
            mismatch.append((tot["item"], "actual=core+wireless", None, None))
    out["ledger_totals_mismatch"] = mismatch
    # 率复算
    rates = []
    for r in c["rates"]:
        inb = Fraction(r["inbound"]["value"])
        per = Fraction(r["period"]["value"])
        tgt = Fraction(r["target"]["value"])
        cmp = "lt" if inb / per < tgt else ("eq" if inb / per == tgt else "gt")
        rates.append({"item": r["item"], "declared": r["comparison"], "recomputed": cmp,
                      "average_ok": Fraction(r["average"]["value"]) == inb / per,
                      "inbound_matches_totals":
                          inb == agg.get(r["item"], {}).get("actual_inbound", Fraction(0))})
    out["rates"] = rates
    out["all_pass"] = (out["start_key_matches_recomputed"] and out["end_key_matches_recomputed"]
                       and out["start_key_equals_end_key"] and out["period_matches_times"]
                       and out["ledger_rows_match_period"] and not mismatch
                       and all(r["declared"] == r["recomputed"] and r["average_ok"]
                               and r["inbound_matches_totals"] for r in rates))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
