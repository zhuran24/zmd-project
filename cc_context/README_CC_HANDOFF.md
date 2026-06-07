# CC (Claude Code) 上下文接入说明

目标: 让接手者打开 CC 时，**自动带上本项目的全部记忆**，立刻能接手。

---

> **CC-era handoff note, not the current project front door.**
>
> This document explains how the 2026-05-30 Claude Code handoff attached memory
> to a local CC installation. For the current lightweight GitHub checkout, use
> `START_HERE.md` and `CLAUDE.md` first. The repo-native memory mirror is
> `cc_context/memory/`, and `_cc_live_memory/` is checked only as a byte-identical
> mirror when present. GPT-side work does not need to install CC memory.

## 推荐: 一键脚本已经帮你做好了

如果你跑过包根目录的 `setup.sh`，**memory 已经自动接到正确位置了，这份文档
你只需要在出问题时排查用**。直接 `cd zmd && claude` 即可。

下面是手动 / 原理说明。

---

## memory 接入的关键: slug 路径

CC 把每个项目的记忆存在:

```
~/.claude/projects/<SLUG>/memory/
```

`<SLUG>` = 项目的**绝对路径**把每个 `/` 换成 `-`。

例: 项目在 `/home/bob/claude-pj/zmd` → SLUG = `-home-bob-claude-pj-zmd` →
memory 要放到 `~/.claude/projects/-home-bob-claude-pj-zmd/memory/`。

> 所以 memory 的落点**取决于你把项目 clone 到哪**。CC 在哪个目录 `claude`，
> 就按那个目录的绝对路径算 slug。

## 手动接入 (3 行)

在 clone 出来的项目根目录里跑:

```bash
PROJ="$(pwd)"                                   # 必须在项目根目录里
SLUG="$(printf '%s' "$PROJ" | sed 's#/#-#g')"
DEST="$HOME/.claude/projects/$SLUG"
mkdir -p "$DEST"
cp -r <本包路径>/cc_context/memory "$DEST/memory"
```

之后 `cd $PROJ && claude`，CC 会自动加载 `memory/MEMORY.md` (索引)，再按需读
各条记忆。

## 验证接入成功

```bash
ls "$HOME/.claude/projects/$(printf '%s' "$(pwd)" | sed 's#/#-#g')/memory/MEMORY.md"
# 能列出来 = 接好了
```

开 CC 后，问它「读一下 mem 和项目状态」，它应该能复述出 Phase 1.2 / F3 /
27 lever 等内容 —— 说明记忆生效了。

---

## memory 里有什么 (接手最该先读的几条)

`memory/` 共 117 个文件，`MEMORY.md` 是自动加载的索引。重点:

| 文件 | 内容 |
|---|---|
| `MEMORY.md` | 全部记忆的一行式索引 (CC 每次会话自动读) |
| `project_phase_1_2_progress.md` | 当前阶段 (Phase 1.2 spike close + F3 special-case phase) 全过程 |
| `project_paradigm_death_timeline_27_lever.md` | **27 条求解 paradigm 死路史 + 死因分类 (接手前必读, 防重踩)** |
| `project_endfield_solver.md` | 项目总览 |
| `user_profile.md` | zhuran24 是谁 / 怎么沟通 |
| `feedback_*.md` | zhuran24 给 CC 的工作方式偏好 (懒狗模式 / 不问要不要 / 审查策略 等) |
| `reference_*.md` | 外部资源指针 (Gemini 数学 consultant key / 硬件 / 备份 等) |

> 注意: 部分 `reference_*` / 全局 CLAUDE.md 里的**磁盘路径、硬件备忘、备份位置**
> 是 zhuran24 那台机器专属的，换机器不适用，CC 读到当背景即可，别照搬。

---

## global_CLAUDE.md (zhuran24 全局 CC 配置)

`global_CLAUDE.md` 是 zhuran24 的全局 `~/.claude/CLAUDE.md`。它定义了 zhuran24
希望 CC 怎么协作 (伙伴关系 / 中文大白话 / 子代理用 opus / 知识持久化 / 不无谓
盖章 等)。**接手者可以挑工作风格那几段并进自己的全局 CLAUDE.md**，但:

- 不要整份覆盖你自己的 `~/.claude/CLAUDE.md`。
- 「磁盘使用策略 / 本机环境备忘 / 心跳维护 / CachyOS 调优」整段都是 zhuran24
  主机专属，跳过。

> zhuran24 个人的全局 skills/commands/agents (academic-research 等) 没随包 ——
> 它们是跨项目的个人 CC 工具、跟本项目无关。接手者用自己的全局配置即可。
