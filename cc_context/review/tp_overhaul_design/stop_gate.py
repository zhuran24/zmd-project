#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stop hook — 任务推进出口门 (zmd / zhuran24) · 修正版 v2

定位 (据对抗审查 RETHINK 收敛):
  这是一个【低召回、绝不误拦】的硬违规提醒器, 只拦【带明确请示句式标志】的
  收尾(由你定 / 要不要我X / 需要你确认…发吗 / 节奏你来 / 你给X我就Y /
  我可以…吗 / 我现在去做X然后停)。它【不】负责抓纯语义类违规(自己能查却问、
  没核就断言、会错意、宣布收敛)—— 那类没有句式标志, 正则原理上抓不到, 真根治
  在知识结构侧(理解 why 内化), hook 只兜住可机械识别的一档, 是 fallback。

落地: ~/.claude/settings.json 的 hooks.Stop (Stop 事件无 matcher, 全局):
  {"hooks": {"Stop": [{"hooks": [
     {"type": "command", "timeout": 10,
      "command": "\"C:/Program Files/Python313/python.exe\" \"C:/Users/22957/.claude/hooks/stop_gate.py\""}
  ]}]}}

契约 (Claude Code Stop hook, 官方文档 code.claude.com/docs/en/hooks 核实):
  - stdin: JSON {session_id, transcript_path, cwd, permission_mode,
                 hook_event_name, stop_hook_active}
    注意: Stop stdin 【没有】 last_assistant_message 字段 —— 取 CC 最后回复
    必须读 transcript_path 解析 JSONL。
  - 放行: 退出码 0, stdout 空 (不输出 decision)
  - 拦截: 退出码 0, stdout 输出 {"decision":"block","reason":"..."}
          reason 回灌给模型, 驱动它继续干活
  - stop_hook_active=true 时必须放行(防无限循环, 官方硬约束)

设计铁律: 保守优先 —— 任何不确定一律 ALLOW; 宁可漏拦, 绝不误拦把用户卡住。
一键停: env ZMD_STOP_GATE_DISABLE=1 或 flag 文件 (见 kill_switch_on)。
默认睡着: 还需 ZMD_STOP_GATE_GOAL_ACTIVE=1 或 goal flag 才咬合。
"""
import json
import os
import re
import sys
from pathlib import Path

# ---------------- helpers: 永远不抛, 出错即放行 ----------------

def _allow():
    # stdout 空 = 放行
    sys.exit(0)


def _block(reason: str):
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason},
                                ensure_ascii=False))
    sys.exit(0)


def _truthy_env(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _home() -> Path:
    try:
        return Path(os.path.expanduser("~"))
    except Exception:
        return Path(".")


# ---------------- kill switch / goal-active gate ----------------

def kill_switch_on(cwd: Path) -> bool:
    if _truthy_env("ZMD_STOP_GATE_DISABLE"):
        return True
    for p in (_home() / ".claude" / "zmd_stop_gate.off",
              _home() / "zmd_stop_gate.off",
              cwd / ".zmd_stop_gate.off"):
        try:
            if p.exists():
                return True
        except Exception:
            return True  # 连判断都出错 → 倒向停用
    return False


def goal_active(cwd: Path) -> bool:
    if _truthy_env("ZMD_STOP_GATE_GOAL_ACTIVE"):
        return True
    for p in (_home() / ".claude" / "zmd_active_goal",
              cwd / ".zmd_active_goal"):
        try:
            if p.exists() and p.stat().st_size > 0:
                return True
        except Exception:
            pass
    return False


# ---------------- transcript 读取 ----------------

def last_assistant(transcript_path: str):
    """返回 (text:str, has_tool_use:bool) 或 None.

    Stop stdin 无 last_assistant_message 字段(官方文档核实), 只能读 transcript。
    每行一条 JSON, 通常 {message:{role,content}, ...} 包装; content 是 str 或
    block 列表(text / tool_use / thinking)。从尾部向前找首条 assistant。
    """
    try:
        p = Path(transcript_path)
        if not p.exists():
            return None
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        msg = rec.get("message", rec) if isinstance(rec, dict) else None
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        text_parts, has_tool = [], False
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for blk in content:
                if not isinstance(blk, dict):
                    continue
                t = blk.get("type")
                if t == "text" and isinstance(blk.get("text"), str):
                    text_parts.append(blk["text"])
                elif t in ("tool_use", "server_tool_use"):
                    has_tool = True
        return ("\n".join(text_parts), has_tool)
    return None


# ---------------- 句法判定 ----------------

_SENT_SEP = "。!?！？；;\n"


def tail_segment(text: str) -> str:
    """取结尾段: 末尾 ~200 字符窗口里的最后 1-2 句.

    切句【保留句末标点】(捕获组切, 标点粘回句尾) —— 否则末尾问号被吃掉,
    所有 `[?？]\\s*$` 锚定的请示分支(要不要…吗 / 发吗?)会全部失效漏拦。
    """
    t = text.rstrip()
    if not t:
        return ""
    window = t[-200:]
    toks = re.split(r"([" + _SENT_SEP + r"])", window)
    sents, buf = [], ""
    for tok in toks:
        buf += tok
        if tok in _SENT_SEP:
            if buf.strip():
                sents.append(buf)
            buf = ""
    if buf.strip():
        sents.append(buf)
    return "".join(sents[-2:]) if sents else window


# 合法终态豁免 (只在结尾段判, 不扫全文 —— 修 adversary: 中段一句『已跑完』
# 不能放行整条;『等你确认/等待你确认』是踢回不是外部等待, 已从词表剔除并不在此豁免)。
EXEMPT = {
    "WAITING_EXTERNAL": re.compile(
        # 必须是『在等一个外部产出/进程/人的回复』的进行态, 不含『等你拍板』
        r"(正在等|在等待|还在等|跑完后|后台(运行|跑着|在跑)|已在后台|"
        r"完成后(会)?(唤醒|通知|汇报)|等[^。\n]{0,8}(GPT|CI|交付|回包|结果|"
        r"跑完|完成|这批)|run_in_background|尚未跑完|还在跑|等它(跑|生成))"),
    "BLOCKED_USER_ONLY": re.compile(
        # 三要素结构 (A): 已完成X … 只剩Z是只有你能定 (顺序敏感的『已做完+只剩』)
        r"((已(完成|做完|跑完|改完|推送|落地|准备好)|我已经)[^。\n]{0,80}"
        r"(只剩|仅剩|唯一(只有|得)你|这点(只有|得)你))|"
        # (B) ②类纯偏好上交: 已做完能做的 + 把『真偏好选择』交上去 (顺序不敏感,
        #     接住『三个面都准备好了, 你想先审哪个』这类合法②类残余, 防 you_decide 误拦)
        r"((都准备好|已准备好|已完成|我这边[^。\n]{0,12}(都|已))[^。\n]{0,80}"
        r"(你想先(审|做|跑|看)[^。\n]{0,4}哪个|是你的(资源|节奏|优先级)?[^。\n]{0,4}偏好|"
        r"没有(明显)?(优先级|先后)))|"
        r"(你想先(审|做|跑|看)[^。\n]{0,4}哪个[^。\n]{0,40}(都准备好|你定了我(就|立刻|马上)))|"
        # 其余明确窄口径
        r"外部账目|手动计数|仓库外(手动)?(计数|维护)|"
        r"(不可逆[^。\n]{0,12}(高风险|你拍板|你确认))|客服回执"),
    "TECHNICAL_HANDOFF": re.compile(
        r"(需要你(手动)?(重启|在BIOS|在系统里|插拔|手动点|手动操作|手动恢复|"
        r"从外部恢复|restore)|权限(被拒|不足|不够)|无权(自动)?写入|工具(报错|失败|"
        r"不可用)|环境(限制|边界)|harness\s*限制|只能你手动|无法自行(继续|完成))"),
}

# 元讨论豁免 —— 收紧(修 adversary 最大后门): 删掉 hook/规则 这类高频项目名词,
# 只在结尾段【明显是引用/复述 CLAUDE.md 原文片段】时豁免(带书名号引用 + 含
# CLAUDE.md / 记忆树 这种少见的元文档词)。普通讨论项目 hook 不再获免死金牌。
META = re.compile(r"(「[^」]{4,}」.{0,30}(判据|原话|原文))|CLAUDE\.md 原文|记忆树原文")

# 非法模式 (只在结尾段上跑)。每条都锚『我/你 + 请示动词』的紧凑结构。
ILLEGAL = [
    # 要不要我X / 需不需要 / 我可以…吗 / 需要你…确认…吗 (补『你』作动作主体)
    ("trailing_question_offer", re.compile(
        r"((要不要|需不需要|要我|需要我|用不用|是否需要|是否(要|希望我)|"
        r"我可以(帮你|帮您)?[^。\n]{0,12}吗)[^。\n]{0,40}[?？]?\s*$)|"
        r"(需要你[^。\n]{0,12}(确认|点头|拍板|告诉我|定|发话)[^。\n]{0,16}[?？]\s*$)|"
        r"(请你(确认|看一下|点个头)[^。\n]{0,12}[?？]\s*$)|"
        r"(你(要不要|是否)[^。\n]{0,16}[?？]\s*$)")),
    # 你定 / 由你定 / 你的call / 等你裁决 / 只有你能定 (容许中间字, 接住 case2)
    ("you_decide", re.compile(
        r"(你来定|你定|由你定|你说了(算|不算)|你的\s*call|看你的\s*call|"
        r"你.{0,2}定(吧|了)?\s*$|只有你(能|可以)?定|(这|得)你(来)?(拍板|拍个板|"
        r"点头|决定|定夺)|等你(裁决|定夺|拍板|决定|确认|指示|发话)|"
        r"看你(的)?(意思|想法)|听你的|你裁决|(请|辛苦)你(拍板|拍个板|点头))")),
    # 节奏/额度/并发…你来/是你的 (踢回既定授权的节奏)
    ("pace_kicked_back", re.compile(
        r"(节奏|进度|排程|额度|并发|批次|批量|要发几个|发几条|什么时候发|"
        r"频率|现在还是等会|快慢)[^。\n]{0,16}"
        r"(你来|你定|由你|你说|是你的|交给你|你决定|你把控|你拿捏)")),
    # 你给X我就Y / 等你确认我就 (条件式回踢)
    ("conditional_kickback", re.compile(
        r"(你(给|说|确认|批|点头|发话|同意|定)[^。\n]{0,20}"
        r"我(就|再|来|会|马上|立刻))|"
        r"(等你(确认|点头|发话|说一声|定)[^。\n]{0,12}我(就|再|马上))")),
    # 我现在去做X / 接下来我做Y (CLAUDE.md 白纸黑字点名的『宣布下一步当句号』,
    # 仅字面命中, 不扩成祈使式全集以免抬高误拦)
    ("announce_next_no_action", re.compile(
        r"(我现在(就)?(去|来|开始)|接下来我(去|来|会|要|处理|做|改|跑|发|写|查)|"
        r"下一步我(去|来|会|要|处理|做)|我这就(去|来)|那我(去|来|开始))"
        r"[^。\n]{0,30}")),
    # 保险起见…先发/先做… (放宽邻接: 风控类词 + 自设限词共现于结尾段即命中)
    ("self_imposed_conservatism", re.compile(
        r"((保险起见|稳妥起见|稳一点|稳妥点|谨慎起见|为了安全|怕(触发)?风控|"
        r"可能触发(风控|限制))[^。\n]{0,40}"
        r"(先(发|做|跑|试|来)|只(发|做|跑)|小批|分批|错开(发)?|限并发|"
        r"一个一个|逐个|发\s*\d+\s*个|发[一二两三]个))|"
        r"((小批|分批|错开发|限并发|发\s*\d+\s*个|先发[一二两三]个)[^。\n]{0,30}"
        r"(稳|保险|看看|再发|风控))")),
    # 我可以开始了吗 / 这样行吗 / 然后呢 (请求继续许可)
    ("permission_to_proceed", re.compile(
        r"(我可以(开始|继续|动手|往下)了?吗|这样(可以|行|对)吗|可以了吗|"
        r"行不行[?？]?\s*$|然后呢[?？]?\s*$|接下来呢[?？]?\s*$|"
        r"你看(这样)?(行不行|可以吗|如何|怎么样))\s*[?？]?\s*$")),
]

FEEDBACK_TAIL = (
    "active goal 未完成且你还有自己能执行的 next action —— 当场做掉, "
    "不准以请示/宣告下一步收尾。若真在等外部结果或只剩用户能定的残余, "
    "请显式说清在等什么 / 只剩哪点是用户的(已完成 X、Y, 只剩 Z 是你的)。")


# ---------------- 主流程 ----------------

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        _allow()
    if not isinstance(data, dict):
        _allow()

    ev = data.get("hook_event_name")
    if ev and ev != "Stop":
        _allow()

    # 防死循环硬闸 (官方: 上一次已 block 过, 再 block 会无限循环)
    if data.get("stop_hook_active"):
        _allow()

    try:
        cwd = Path(data.get("cwd") or os.getcwd())
    except Exception:
        cwd = Path(".")

    if kill_switch_on(cwd):
        _allow()

    # 门默认睡着: 没有明确 active goal 信号就放行
    if not goal_active(cwd):
        _allow()

    tp = data.get("transcript_path")
    if not tp:
        _allow()
    got = last_assistant(tp)
    if got is None:
        _allow()
    text, has_tool = got

    # 还在调工具收尾 = 在干活
    if has_tool:
        _allow()
    if not text or not text.strip():
        _allow()

    tail = tail_segment(text)
    if not tail:
        _allow()

    # 合法终态宽豁免 (只在结尾段, 修 adversary: 不扫全文)
    for rgx in EXEMPT.values():
        if rgx.search(tail):
            _allow()

    # 元讨论豁免 (收紧: 仅明显引用 CLAUDE.md 原文片段)
    if META.search(tail):
        _allow()

    hits = [name for name, rgx in ILLEGAL if rgx.search(tail)]
    if not hits:
        _allow()

    reason = ("检测到回合以这类请示/宣告模式收尾: " + ", ".join(hits) + "。"
              + FEEDBACK_TAIL)
    _block(reason)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # 任何意外 → 放行, 绝不卡用户
        _allow()
