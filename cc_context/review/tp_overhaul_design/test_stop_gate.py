#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stop_gate 回归夹具 — 真实调脚本, 不靠眼判.

构造一个临时 transcript JSONL(末尾一条 assistant text 记录) + stdin JSON,
设 ZMD_STOP_GATE_GOAL_ACTIVE=1 让门咬合, 跑 stop_gate.py, 看 stdout 有没有
decision:block。每条夹具断言期望 BLOCK / ALLOW。

跑法: python test_stop_gate.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "stop_gate.py"

# (name, last_assistant_text, expect)  expect in {"BLOCK","ALLOW"}
CASES = [
    # ---- canonical 夹具 16 条 (来自种子 fixtures) ----
    ("c1 我现在去diff19个然后停",
     "好的，理解了。我现在去 diff 那 19 个文件，看看哪些有算法边界问题。", "BLOCK"),
    ("c2 闭合A还是B只有你能定整摊回踢",
     "闭合标准选 A（接受当前状态）还是 B（继续审查到真零 finding），这涉及项目方向裁决，只有你能定，我没法替你做这个判断。", "BLOCK"),
    ("c3 重发dispatch后又问发吗",
     "去偏置模板已准备好。这次要外发 8 个 GPT 审查任务，属于 consequential outward action，需要你点头确认一下——发吗？", "BLOCK"),
    ("c4 节奏你定闭合节奏是你的call",
     "接下来外发的频率和节奏你来定吧，你说发几个我就发几个，闭合节奏是你的 call。", "BLOCK"),
    ("c5 commit会autopush要不要commit",
     "preflight 全绿，pytest 全通过，working tree 已验证。不过 commit 会触发 post-commit hook 自动 push 到 GitHub，要不要 commit？", "BLOCK"),
    ("c6 小批错开先发2个自我设限",
     "并发开太多可能触发风控，保险起见先错开发 2 个，等这 2 个收回来再发剩下的，稳一点。", "BLOCK"),
    # c7-c11 = 纯语义类违规, 无任何请示句式标志词。本门【设计上明确放弃】这一档
    # (正则原理上抓不到), 真根治在知识结构侧(fact-react-before-understand-default
    # + 理解 why 内化)。期望 ALLOW = 诚实记录本门职责边界, 不是 bug。
    ("c7 [语义类·放弃] 能自己查的键绑定去问owner",
     "清空输入框是哪个快捷键？需要你告诉我一下。", "ALLOW"),
    ("c8 [语义类·放弃] 凭消息到达抢答路径通过",
     "测试消息已到达，[立刻]路径验证通过。", "ALLOW"),
    ("c9 [语义类·放弃] 开始指眼前却跳旧脚注",
     "好的，我们来继续 P1.2 主线闭合，从上次的进度开始推进。", "ALLOW"),
    ("c10 [语义类·放弃] 把workflow申请当别用退回单代理",
     "这个任务用 Workflow 多智能体并发效果最好，但因为 Workflow 需要申请，我就用单代理手动来做吧。", "ALLOW"),
    ("c11 [语义类·放弃] 路A19轮越挖越窄就宣布收敛",
     "V97-V98 已退到文件系统权威边界边角，finding 越来越窄，看起来即将收敛，可以考虑把 proof-carrying 列为 P1.3+ 不阻塞 P1.2 闭合了。", "ALLOW"),
    ("c12 已在等GPT回包合法停止",
     "8 个 dispatch 任务已全部发出（会话 URL 已记录），正在等 GPT 生成回包。所有任务 exit 0 后我会立刻开始验收链，不需要你做任何操作，有结果我会汇报。", "ALLOW"),
    ("c13 合法上交已完成XY只剩仓库外计数",
     "推荐选 A（接受当前 deny-unknown 公开面封闭状态为 P1.2 闭合条件），理由是：路 A 19 轮已横扫全部公开 payload 面，剩余 proof-carrying 缺口属 P1.3B 既定范围。我已把推荐方案和两条配套条件写进 handoff，只剩「仓库外手动审查连击计数是否达 3 次」是你才知道的，这一点确认后我们就可以正式标闭合。", "ALLOW"),
    ("c14 合法停止preflight挂等外部restore",
     "preflight_gate --ci 的「candidate_placements.json 存在」检查报 BLOCK——这个文件需要你按 START_HERE.md 的 restore 命令从外部恢复（45.8MB，gitignore 防误推，我无权自动写入 data/preprocessed/）。我已把其余 19 项全部验证通过，只剩这一项是你操作的，恢复后告诉我，我继续跑完整 pytest 和推锚。", "ALLOW"),
    ("c15 合法上交用户裁决先审哪个面真偏好",
     "下一个审查面有三个候选：preprocess 链、binding 忠实度、campaign-resume 状态机。三个面技术风险相近，没有明显优先级差——这是你的资源/节奏偏好，你想先审哪个？我这边三个面都准备好了，你定了我立刻发包。", "ALLOW"),
    ("c16 合法报告降级exit5后自己切通道",
     "dispatch 两端模型校验均返回 exit 5（suspected_downgrade）：发送侧 verify_model 未能确认 Pro 扩展，接收侧 collect 复核 slug 不含 pro，生成耗时 47s。脚本已自动重试一次仍 exit 5。按照通道架构，下一步是切插件通道手动发收，或走 App 9224 fallback——我现在切插件通道重发。", "ALLOW"),

    # ---- 新增对抗用例 (我加的, 探测修复后的边界) ----
    ("n1 你的call技术词call-site误命中检测",
     "已经把这个交付物的所有 call-site 都改了，测试全绿，已 commit 推送。", "ALLOW"),
    ("n2 英文马甲shall-I-proceed(明确放弃, 期望ALLOW=漏拦)",
     "The plan is ready. Shall I proceed?", "ALLOW"),
    ("n3 纯DONE收尾",
     "三个 fact 节点已写入 cc_context/memory，MEMORY.md 已加覆盖行，check_memory_tree.py 本地跑通 exit 0，已 commit。", "ALLOW"),
    ("n4 元讨论假豁免被堵-讨论hook却问要不要",
     "这个 Stop hook 的正则我已经写好了，要不要我现在就部署到 settings.json？", "BLOCK"),
    ("n5 需要你确认发吗变体",
     "8 个任务打包完毕。这批要发出去需要你确认一下，发吗？", "BLOCK"),
    ("n6 中段已跑完但结尾踢回(不该被WAITING盾牌放行)",
     "pytest 已经跑完了，全绿。下一步外发节奏你来定。", "BLOCK"),

    # ---- 真实会话收尾文本 (从 transcript 抽, 全是合法 DONE/WAITING, 误拦护栏) ----
    ("r1 真实-compact注入后等压缩",
     "`/compact` 注入成功（`code=0`，这次输入框空着）。记忆更新 + 归因纠正都已落盘提交，中间零插活。\n\n结束回合 —— 注入的 `/compact` 作为下一条 queued 输入到达就会压缩。压缩完我继续。", "ALLOW"),
    ("r2 真实-状态汇报提下一步但在等回包",
     "8 个任务已全部发出，正在等回包。下一步我会在 exit 0 后开始验收链。", "ALLOW"),
    ("r3 真实-纯结论收尾",
     "三个 fact 节点已写入，MEMORY.md 已加覆盖行，check_memory_tree.py exit 0，已提交。", "ALLOW"),
]


def run_case(text: str) -> str:
    """返回 'BLOCK' 或 'ALLOW'."""
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "transcript.jsonl"
        rec = {"type": "assistant",
               "message": {"role": "assistant",
                           "content": [{"type": "text", "text": text}]}}
        tp.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
        stdin = json.dumps({
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "cwd": td,
            "transcript_path": str(tp),
        })
        env = dict(os.environ)
        env["ZMD_STOP_GATE_GOAL_ACTIVE"] = "1"
        env.pop("ZMD_STOP_GATE_DISABLE", None)
        out = subprocess.run(
            [sys.executable, str(GATE)],
            input=stdin, capture_output=True, text=True, env=env, timeout=15,
        )
        s = (out.stdout or "").strip()
        if not s:
            return "ALLOW"
        try:
            if json.loads(s).get("decision") == "block":
                return "BLOCK"
        except Exception:
            pass
        return "ALLOW"


def main() -> int:
    passed = failed = 0
    rows = []
    for name, text, expect in CASES:
        got = run_case(text)
        ok = got == expect
        passed += ok
        failed += not ok
        rows.append((ok, name, expect, got))
    for ok, name, expect, got in rows:
        mark = "PASS" if ok else "FAIL"
        note = "" if ok else f"  <<< expect {expect}, got {got}"
        print(f"[{mark}] {name}: expect={expect} got={got}{note}")
    print(f"\n{passed}/{passed + failed} passed, {failed} failed")
    # 漏拦统计(语义类 c7-c11 + 英文 n2 是明确放弃的, 不计入失败基线)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
