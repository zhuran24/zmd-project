#!/usr/bin/env python3
r"""自动给「单一 living 现状源」(handoff) 刷新可推导的现状字段 + 对人写的判断散文做 staleness warn。

由 pre-commit 钩子调用 (也可手跑)。**fail-soft: 任何错都只打 warn、exit 0, 绝不阻断 commit。**
只改 handoff 里 `<!-- AUTO-STATUS:BEGIN/END -->` 之间的块 (机器生成), **绝不碰人写的散文**。

为什么存在: 「现状记忆一直被忘记更新」的根因 = 它是项目里唯一没有强制函数、不挂在任何产物
完成定义上的关键动作 (commit/push/memory-sync/链接/测试 都有钩子或会大声报错, 唯独 handoff
现状散文没有)。光记规则 (被动文本) 治不住一个「没上锁」的动作。所以:
  - **可推导字段** (最新 review 包版本/sha、spike HEAD、CLAUDE.md Current Phase) → 每 commit
    自动 stamp, 根本不可能 stale (强制函数的极致 = 把手动步骤删掉)。
  - **不可推导的判断散文** (下一步/在等什么) → 没法自动生成, 但若它没提到最新包版本就**大声 warn**
    (把「静默漂移」变成「响亮漂移」, 这就是缺的那个强制信号)。
覆盖局限 (诚实交代): 判断散文里纯叙述/判断的漂移 (例如「等第四轮」其实已回来) 不是文件事实,
无法自动推导, 只能靠 warn 提示 + 人改; 但实践中状态变更几乎总伴随一次 build/commit, 故绑包版本
的 warn 能抓住绝大多数真实漏更。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# 单一 living 现状源 (per memory-currency-protocol)。若改名, 改这里。
LIVING_SOURCE = Path.home() / ".claude" / "projects" / "D-----zmd" / "memory" / "handoff_windows_ninth_review_pending.md"
REPO = Path(__file__).resolve().parents[2]
LATEST_PACKAGE = REPO / "cc_context" / "review" / "LATEST_PACKAGE.json"
SPIKE_BRANCH = "spike/prod_scale_master_integration_20260526"

BEGIN = "<!-- AUTO-STATUS:BEGIN — 由 pre-commit stamp_living_status.py 自动重生成, 别手改这块 -->"
END = "<!-- AUTO-STATUS:END -->"


def _git_short(ref: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", ref],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else "?"
    except Exception:
        return "?"


def _claude_md_phase() -> str:
    try:
        for line in (REPO / "CLAUDE.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("## Current Phase:"):
                return line[len("## Current Phase:"):].strip()
    except Exception:
        pass
    return "?"


def _latest_package() -> dict:
    try:
        return json.loads(LATEST_PACKAGE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_block() -> tuple[str, str]:
    """Return (block_text, latest_pkg_version_or_empty)."""
    pkg = _latest_package()
    ver = str(pkg.get("version", "")).strip()
    sha = str(pkg.get("sha256", ""))[:12]
    pkg_line = f"{ver} (sha `{sha}…`)" if ver else "(无 LATEST_PACKAGE.json 记录)"
    spike = _git_short(SPIKE_BRANCH)
    phase = _claude_md_phase()
    body = (
        f"{BEGIN}\n"
        f"**自动现状标记** (机器每 commit 刷新, 可推导字段不可能 stale; 人写的判断散文见下方各 `##` 块):\n"
        f"- 最新 review 包: {pkg_line}\n"
        f"- spike 分支 HEAD: `{spike}`\n"
        f"- CLAUDE.md Current Phase: {phase}\n"
        f"{END}"
    )
    return body, ver


def main() -> int:
    try:
        if not LIVING_SOURCE.exists():
            return 0  # 换机/源不在 → 跳过, 不阻断
        text = LIVING_SOURCE.read_text(encoding="utf-8")
        block, ver = build_block()

        if BEGIN in text and END in text:
            new_text = re.sub(
                re.escape(BEGIN) + r".*?" + re.escape(END),
                lambda _m: block,
                text,
                count=1,
                flags=re.DOTALL,
            )
        else:
            # 首次: 插在 frontmatter 后第一个 `## ` 标题之前。
            m = re.search(r"(?m)^## ", text)
            if m:
                new_text = text[:m.start()] + block + "\n\n" + text[m.start():]
            else:
                new_text = text.rstrip() + "\n\n" + block + "\n"

        if new_text != text:
            LIVING_SOURCE.write_text(new_text, encoding="utf-8")

        # staleness warn: 判断散文 (去掉 auto-block 后的正文) 是否提到了最新包版本。
        if ver:
            prose = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", new_text, flags=re.DOTALL)
            if ver not in prose:
                sys.stderr.write(
                    f"\n⚠️  [living-status] 最新 review 包是 {ver}, 但 handoff 的判断散文没提到它 —— "
                    f"现状叙述可能 stale, 请手动更新 handoff 的 `## 最新状态` 块 (可推导字段已自动 stamp)。\n\n"
                )
    except Exception as exc:  # fail-soft: 绝不阻断 commit
        sys.stderr.write(f"[living-status] stamp 跳过 (非致命): {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
