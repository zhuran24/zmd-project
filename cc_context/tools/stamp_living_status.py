#!/usr/bin/env python3
r"""实例/分身 transclusion 引擎 (CC 记忆树单一真相源).

架构 (用户 2026-06-02 提出): 把记忆树做成「单一真相源 + transclusion」——
- **实例 (instance)** = 某个**可推导事实**的唯一权威值, context-independent (一处真值,
  不被任意情景重新指定)。在下面 INSTANCES 注册表里, 每个实例 = 一个 resolver()->渲染字符串。
- **分身 (projection)** = 任意 memory 节点里的 `<!-- INSTANCE:id -->…<!-- /INSTANCE:id -->`
  槽, 它**引用**实例而非 copy。
- 本 pass (pre-commit 每 commit 调) 把每个实例当前值 render 进它所有分身槽 → **重复的可推导值
  结构上不可能 drift** (改实例 = 改 resolver/源, 一刷全分身同步)。

为什么 (根因, 见 memory-currency-protocol rule#7 + github-backup): 现状/重复值漏更反复复发, 不是
知识缺口, 是这些值散在多节点、没有强制函数。记规则 (被动文本) 治不住没上锁的动作。本引擎 = 强制函数。

**只治「可推导值」** (sha / git HEAD / phase / repo url ...)。**规则/判断类不在此 transclude** ——
逐字副本满树 = clutter; 规则靠 wikilink 链接 + 连通纪律 (见 memory-tree-structural-health)。

**护栏** (blast radius 大, 严): fail-soft (任何错只 warn + exit 0, 绝不阻断 commit);
只改 `INSTANCE:id` 槽**内**文本, 绝不碰其它; 幂等; resolver 失败 (返回空) 时**保留槽内旧值不 blank**;
逐文件 try/except (一个坏文件不影响其它)。

**扩展**: 新增实例 → 往 INSTANCES 加一个 resolver; 新增分身 → 在任意 memory .md 插
`<!-- INSTANCE:id -->占位<!-- /INSTANCE:id -->`。(文件名沿用 stamp_living_status 仅为 hook/引用稳定;
职责已泛化为全树 transclude。)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

MEM = Path.home() / ".claude" / "projects" / "D-----zmd" / "memory"
REPO = Path(__file__).resolve().parents[2]
LIVING_SOURCE = MEM / "handoff_windows_ninth_review_pending.md"  # 单一 living 现状源
SPIKE_BRANCH = "spike/prod_scale_master_integration_20260526"
LATEST_PACKAGE = REPO / "cc_context" / "review" / "LATEST_PACKAGE.json"

# SLOT: 槽 interior 用负向先行 `(?!<!-- /?INSTANCE:)` 限定**不能跨任何 INSTANCE open/close marker** ——
# 这样不平衡/错配的 marker (悬空 open + 后面孤立 close / 错 id close) 不会让 `.*?` 跨行吞掉中间文本
# (engine-adversarial 镜头实测的唯一损坏向量: 旧的裸 `.*?` 会 swallow KEEP_ME)。不平衡 → 不匹配 → 留原样。
SLOT = re.compile(
    r"<!-- INSTANCE:([a-z0-9_]+) -->(?:(?!<!-- /?INSTANCE:).)*?<!-- /INSTANCE:\1 -->",
    re.DOTALL,
)
OPEN = re.compile(r"<!-- INSTANCE:[a-z0-9_]+ -->")  # 用于 orphan/unbalanced 检测


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(REPO), *args],
                           capture_output=True, text=True, encoding="utf-8", timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _r_latest_review_package() -> str:
    d = json.loads(LATEST_PACKAGE.read_text(encoding="utf-8"))
    v, s = str(d.get("version", "")).strip(), str(d.get("sha256", ""))[:12]
    return f"{v} (sha `{s}…`)" if v else ""


def _r_spike_head() -> str:
    return _git("rev-parse", "--short", SPIKE_BRANCH)


def _r_current_phase() -> str:
    for ln in (REPO / "CLAUDE.md").read_text(encoding="utf-8").splitlines():
        if ln.startswith("## Current Phase:"):
            return ln[len("## Current Phase:"):].strip()
    return ""


def _r_repo_url() -> str:
    u = _git("remote", "get-url", "origin")
    m = re.search(r"github\.com[/:]([^/]+/[^/.]+)", u)
    return m.group(1) if m else u


# 实例注册表: id -> resolver()->渲染串。只放可推导值。
INSTANCES = {
    "latest_review_package": _r_latest_review_package,
    "spike_head": _r_spike_head,
    "current_phase": _r_current_phase,
    "repo_url": _r_repo_url,
}


def main() -> int:
    try:
        # 1. resolve 每个实例一次 (resolver 自身失败 → 空串, 后面遇到就保留旧槽值)
        values: dict[str, str] = {}
        for iid, fn in INSTANCES.items():
            try:
                values[iid] = (fn() or "").strip()
            except Exception:
                values[iid] = ""

        # 2. 扫全树, 填所有分身槽
        changed = slots = 0
        unknown: set[str] = set()

        def render(m: "re.Match[str]") -> str:
            nonlocal slots
            iid = m.group(1)
            if iid not in INSTANCES:
                unknown.add(iid)
                return m.group(0)
            val = values.get(iid, "")
            if not val:
                return m.group(0)  # resolver 失败 → 保留旧值, 不 blank
            slots += 1
            return f"<!-- INSTANCE:{iid} -->{val}<!-- /INSTANCE:{iid} -->"

        for f in sorted(MEM.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            if "<!-- INSTANCE:" not in text:
                continue
            n_open, n_slot = len(OPEN.findall(text)), len(SLOT.findall(text))
            if n_open != n_slot:
                sys.stderr.write(
                    f"⚠️  [instances] {f.name}: INSTANCE open marker 数({n_open}) ≠ 完整槽数({n_slot}) "
                    f"—— 疑有不平衡/孤立 marker。已 fail-safe (不吞文本, 该槽不填), 但请检查 authoring。\n"
                )
            new = SLOT.sub(render, text)
            if new != text:
                try:
                    f.write_text(new, encoding="utf-8")
                    changed += 1
                except Exception:
                    pass

        # 3. living 现状源「判断散文」lag warn (判断类推不出来, 只能 warn 提示人改)
        ver = str(values.get("latest_review_package", "")).split(" ", 1)[0]
        if ver and LIVING_SOURCE.exists():
            prose = SLOT.sub("", LIVING_SOURCE.read_text(encoding="utf-8"))
            if ver not in prose:
                sys.stderr.write(
                    f"\n⚠️  [instances] 最新 review 包 {ver}, 但 {LIVING_SOURCE.name} 的判断散文没提到它 —— "
                    f"现状叙述可能 stale, 请手动更新 `## 最新状态` 块 (可推导槽已自动 transclude)。\n\n"
                )
        if unknown:
            sys.stderr.write(f"⚠️  [instances] 未知实例 id (无 resolver, 槽未填): {sorted(unknown)}\n")
        if "--verbose" in sys.argv:
            sys.stderr.write(f"[instances] 填了 {slots} 个分身槽, 改了 {changed} 个文件; 实例值: {values}\n")
    except Exception as exc:  # fail-soft: 绝不阻断 commit
        sys.stderr.write(f"[instances] transclude 跳过 (非致命): {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
