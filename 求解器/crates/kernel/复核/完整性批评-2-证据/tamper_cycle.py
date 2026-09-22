#!/usr/bin/env python3
"""完整性批评-内核-2：对 verify-cycle 做篡改负例。

只在临时目录写篡改副本，不改任何已落盘证书。每个用例是对一份真证书的一处改动；
期望全部被 verify-cycle 拒收（退出码非 0）。
"""
import copy, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path("/home/zhuran24/zmd-research-fresh/求解器")
BIN = str(ROOT / "target/release/kernel")
CFG = str(ROOT / "规格/内核配置-v1.json")

CASES = {
    "T1_period_minus_1": lambda x: x["cycle"].__setitem__("period", {"category": "算术推论", "value": "19"}),
    "T2_status_cycle_found": lambda x: x.__setitem__("status", "cycle_found"),
    "T3_rate_gt": lambda x: [r.__setitem__("comparison", "gt") for r in x["cycle"]["rates"]],
    "T4_inbound_inflated": lambda x: x["cycle"]["rates"][0].__setitem__("inbound", {"category": "算术推论", "value": "20"}),
    "T5_end_key_altered": lambda x: x["cycle"]["end_key"]["state"]["environment"].__setitem__("online", False),
    "T6_ledger_row_dropped": lambda x: x["cycle"]["ledger"].pop(),
    "T7_level_promoted": lambda x: x.__setitem__("level", "full_base"),
    "T8_start_state_inventory": lambda x: next(r for r in x["cycle"]["start_state"]["inventory"] if r["contents"])["contents"].clear(),
    "T9_end_state_inventory": lambda x: next(r for r in x["cycle"]["end_state"]["inventory"] if r["contents"])["contents"].clear(),
    "T10_start_key_state": lambda x: x["cycle"]["start_key"]["state"]["environment"].update({"online": False}),
    "T11_acceptance_false": lambda x: [p.update({"capacity_available": False}) for a in x["cycle"]["acceptance"] for p in a["products"]],
    "T12_normalization_sha": lambda x: x["cycle"]["normalization"]["definition"].update({"sha256": "0" * 64}),
    "T13_support_check_fail": lambda x: x["support_domain"]["checks"][1].update({"status": "fail"}),
    "T14_port_meeting": lambda x: x.update({"port_meeting": "closed_segment_touch"}),
    "T15_seed_reachability": lambda x: x["seed"].update({"reachability": None}),
    "T16_open_items_removed": lambda x: x.update({"open_items": []}),
    "T17_budget_completed": lambda x: x["budget"].update({"completed_ticks": 1}),
    "T18_run_record_dropped": lambda x: x.update({"run_record": None}),
    "T19_ledger_inbound_inflate": lambda x: x["cycle"]["ledger"][0]["warehouse_ledger"]["totals"][0].update({"actual_inbound": {"category": "算术推论", "value": "99"}}),
}


def main(cert):
    base = json.load(open(cert))
    r = subprocess.run([BIN, "verify-cycle", str(cert), "--config", CFG], capture_output=True, text=True)
    out = {"certificate": str(cert), "genuine_accepted": r.returncode == 0, "cases": []}
    with tempfile.TemporaryDirectory() as tmp:
        for name, mutate in CASES.items():
            x = copy.deepcopy(base)
            mutate(x)
            # 无效篡改（改动后内容与原件相同）不计入负例
            if x == base:
                out["cases"].append({"name": name, "result": "no_op_skipped"})
                continue
            p = Path(tmp) / (name + ".json")
            p.write_text(json.dumps(x, ensure_ascii=False))
            r = subprocess.run([BIN, "verify-cycle", str(p), "--config", CFG], capture_output=True, text=True)
            out["cases"].append({"name": name, "result": "rejected" if r.returncode else "ACCEPTED"})
    out["rejected"] = sum(c["result"] == "rejected" for c in out["cases"])
    out["accepted_bad"] = [c["name"] for c in out["cases"] if c["result"] == "ACCEPTED"]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 1 if out["accepted_bad"] or not out["genuine_accepted"] else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
