# -*- coding: utf-8 -*-
"""独立复现: 用 16 条 canonical 夹具实测 draft_script 的判定 (ALLOW/BLOCK),
对比 adversary 声称的 9/16 判错。skeptic 不裸信单一来源的'实测'断言。"""
import json
import os
import subprocess
import sys
import tempfile

PY = r"C:\Program Files\Python313\python.exe"
GATE = r"C:\Users\22957\stop_gate_test.py"
FIX = r"C:\Users\22957\stop_gate_fixtures.json"

cases = json.load(open(FIX, encoding="utf-8"))


def make_transcript(text):
    """构造一个最小 JSONL transcript, 末条是带该 text 的 assistant 消息。"""
    rec = {"message": {"role": "assistant",
                       "content": [{"type": "text", "text": text}]}}
    fd, path = tempfile.mkstemp(suffix=".jsonl", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"message": {"role": "user", "content": "go"}}, ensure_ascii=False) + "\n")
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def run_gate(text):
    """开 goal flag (env), stop_hook_active=false, 喂 stdin, 收 stdout 判 decision。"""
    tp = make_transcript(text)
    stdin = json.dumps({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tp,
        "cwd": tempfile.gettempdir(),
    }, ensure_ascii=False)
    env = dict(os.environ)
    env["ZMD_STOP_GATE_GOAL_ACTIVE"] = "1"      # 门咬合
    env.pop("ZMD_STOP_GATE_DISABLE", None)
    p = subprocess.run([PY, GATE], input=stdin, capture_output=True,
                       text=True, encoding="utf-8", env=env)
    os.unlink(tp)
    sout = (p.stdout or "").strip()
    if not sout:
        return "ALLOW"
    try:
        dec = json.loads(sout).get("decision")
        return "BLOCK" if dec == "block" else "ALLOW"
    except Exception:
        return "PARSE_ERR:" + sout[:80]


wrong = 0
for i, c in enumerate(cases, 1):
    got = run_gate(c["last_assistant_text"])
    exp = c["expect"]
    ok = (got == exp)
    if not ok:
        wrong += 1
    flag = "OK  " if ok else "WRONG"
    print(f"{flag} case{i:2d} exp={exp:5s} got={got:5s}  {c['name'][:34]}")

print(f"\n判错 {wrong}/{len(cases)}")
