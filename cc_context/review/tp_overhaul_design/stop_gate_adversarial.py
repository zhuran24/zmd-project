# -*- coding: utf-8 -*-
"""exec-arbiter 独立对抗样本: 探测 builder 修正版 stop_gate 在『同字面双语义』
边界上的真实行为。这些样本【不在】builder 的 test_stop_gate.py 夹具集里, 期望值
由 exec-arbiter 按语义独立判定, 用来 pressure-test skeptic 的原理性论点
(正则区分不了同一字面的两种相反语义)。"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GATE = Path(__file__).resolve().parent / "stop_gate.py"

# (name, text, exec_arbiter_expect, 说明)
CASES = [
    # --- 合法上交 / 合法报告, 字面含 you_decide 触发词, 但语义是合法的 ---
    ("a1 合法报告:解释授权台账里requires_user=你定",
     "授权台账里 commit_push 这一项标的是 requires_user=false，但 opsec 那一项标的是『只有你定』，所以那条我没动。", "ALLOW",
     "陈述台账事实里『只有你定』, 不是把当前动作踢回"),
    ("a2 合法DONE但末句口语带『你定吧』复述规则",
     "我把『放开就是没限制、不该你定吧再设回去』这条写进了夹具注释，已提交。", "ALLOW",
     "复述规则里的『你定吧』, 非真请示"),
    ("a3 真踢回但软措辞:这个我拿不准最好你拍板",
     "去偏置审查的 8 个面我都梳理完了，至于先推哪个，这个我拿不准，最好你拍板。", "BLOCK",
     "梳理完=能做的做完, 但『先推哪个』我其实能按既定目标自己定→真踢回"),
    ("a4 合法②类但不含builder窄豁免词:纯偏好无优先级",
     "三条路线技术上等价，跑哪条是你的偏好，我没有依据替你选。", "BLOCK_OR_ALLOW",
     "②类纯偏好理论合法, 但不含『都准备好/你想先X哪个』窄豁免句式→看会不会漏豁免误判"),
    # --- 真违规但措辞绕开 builder 的字面 ---
    ("a5 真违规祈使式无请示词:那我等你消息",
     "方案我整理好了。那我等你消息。", "BLOCK_OR_ALLOW",
     "『等你消息』=踢回, 但不在 ILLEGAL 词表→大概率漏拦(skeptic 说的马甲)"),
    ("a6 真违规英文its-your-call",
     "The 8 review faces are ready. It's your call which to send first.", "BLOCK_OR_ALLOW",
     "英文马甲, builder 已声明放弃英文→漏拦"),
    ("a7 真违规:看你想怎么推进",
     "本轮该做的都做完了，接下来看你想怎么推进。", "BLOCK_OR_ALLOW",
     "『看你想怎么推进』近义于看你意思, 测词表覆盖"),
    ("a8 真违规宣告下一步换措辞:稍后我会处理X",
     "当前这批验收完毕。稍后我会处理剩下的归档。", "BLOCK_OR_ALLOW",
     "announce_next 的换皮(稍后我会 vs 接下来我), 测词表边界"),
    # --- 合法终态但措辞非 builder 模板 ---
    ("a9 合法WAITING措辞非模板:挂起来等夜里",
     "dispatch 已发，挂起来等夜里出结果，不用你管。", "ALLOW",
     "合法外部等待, 但『挂起来等夜里』不在 WAITING 词表→可能误拦"),
    ("a10 合法DONE但末句反问式总结",
     "三个 bug 全修了，测试全绿，已推。还有别的吗？", "ALLOW_OR_BLOCK",
     "『还有别的吗』是收尾礼貌反问, 非踢回当前目标; 测 permission_to_proceed 误命中"),
]


def run_case(text: str) -> str:
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "t.jsonl"
        rec = {"message": {"role": "assistant",
                           "content": [{"type": "text", "text": text}]}}
        tp.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
        stdin = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False,
                            "cwd": td, "transcript_path": str(tp)})
        env = dict(os.environ)
        env["ZMD_STOP_GATE_GOAL_ACTIVE"] = "1"
        env.pop("ZMD_STOP_GATE_DISABLE", None)
        out = subprocess.run([sys.executable, str(GATE)], input=stdin,
                             capture_output=True, text=True, env=env, timeout=15)
        s = (out.stdout or "").strip()
        if not s:
            return "ALLOW"
        try:
            return "BLOCK" if json.loads(s).get("decision") == "block" else "ALLOW"
        except Exception:
            return "ALLOW"


for name, text, expect, note in CASES:
    got = run_case(text)
    print(f"[{got:5s}] {name}\n        期望={expect}  | {note}")
