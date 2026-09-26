#!/usr/bin/env python3
"""Replay the saved witness actions independently of paused_witness.py."""
from pathlib import Path
from fractions import Fraction as F
import json

HERE = Path(__file__).resolve().parent


def main():
    doc = json.loads((HERE / "paused_witness.json").read_text())
    machine = {n: dict(stock=0, out=0, done=None, paused=None, complete=False, on=True) for n in ("Y", "X")}
    belts = {"ore": None, "block": None}
    counts = {"ore_export": 0, "Y_start": 0, "Y_complete": 0, "X_start": 0, "X_complete": 0}
    now = F(0)
    for event in doc["witness"]["events"]:
        t = F(event["time"])
        assert t >= now
        now = t
        a = event["action"]
        if ":" in a:
            n, op = a.split(":")
            m = machine[n]
            if op == "start":
                assert m["on"] and m["stock"] >= 1 and m["done"] is None and not m["complete"] and m["paused"] is None
                m["stock"] -= 1
                m["done"] = t+1
                counts[n+"_start"] += 1
            elif op == "complete":
                assert m["on"] and m["done"] == t and m["paused"] is None
                m["complete"] = True
                m["done"] = None
                counts[n+"_complete"] += 1
            elif op == "batch_to_output":
                assert m["complete"] and m["out"] < 50
                m["complete"] = False
                m["out"] += 1
            elif op == "switch_off":
                assert n == "Y" and m["on"] and m["done"] > t
                m["paused"] = m["done"]-t
                m["done"] = None
                m["on"] = False
            else:
                raise AssertionError(op)
        elif a == "warehouse->ore_belt":
            assert belts["ore"] is None
            belts["ore"] = t
            counts["ore_export"] += 1
        elif a in ("ore_belt->Y", "block_belt->X"):
            b, n = ("ore", "Y") if a.startswith("ore") else ("block", "X")
            assert belts[b] is not None and t-belts[b] >= 1 and machine[n]["stock"] < 50
            belts[b] = None
            machine[n]["stock"] += 1
        elif a == "Y->block_belt":
            assert machine["Y"]["out"] > 0 and belts["block"] is None
            machine["Y"]["out"] -= 1
            belts["block"] = t
        else:
            raise AssertionError(a)
        assert all(0 <= m["stock"] <= 50 and 0 <= m["out"] <= 50 for m in machine.values())
    # All possible successful moves and manufacturing steps are permanently disabled.
    assert machine["Y"] == dict(stock=50, out=0, done=None, paused=F(1, 2), complete=False, on=False)
    assert machine["X"] == dict(stock=0, out=6, done=None, paused=None, complete=False, on=True)
    assert belts["ore"] == 57 and belts["block"] is None
    assert now == 57 and counts == dict(ore_export=58, Y_start=7, Y_complete=6, X_start=6, X_complete=6)
    assert counts["ore_export"] == 50+1+6+1  # Y stock, unfinished batch, X products, belt.
    out = dict(actions_replayed=len(doc["witness"]["events"]), replay_pass=True,
        dwell_and_batch_checks_pass=True, material_balance_pass=True,
        permanent_fixed_state_pass=True, counts=counts,
        periodic_state_after=58, stable_period="any positive real number")
    (HERE / "witness_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
