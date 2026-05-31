# 终末地 IndustrialPlanner Exact Solver — 项目交接包

> 交接日期: 2026-05-30 · 交接人 zhuran24 → 朋友接手
> 本包目标: 体积最小 (~15MB) 但**完整可接手** —— 含全 git 历史 + 全部源码/数据 +
> Claude Code (CC) 上下文 (memory + CLAUDE.md)。

---

## 0. 这是什么项目 (一句话)

70×70 网格上 266 个固定设施的 **certified-exact 最大空矩形求解器** (终末地
Arknights: Endfield 工业规划器)。目标 `max_lex(area, min_side)`，用 OR-Tools
CP-SAT + LBBD (Benders) 分解: master → binding → routing → flow。

当前阶段细节见 §5「当前项目状态」。

---

## 1. 包内容 (manifest)

| 路径 | 是什么 | 体积 |
|---|---|---|
| `repo.bundle` | **完整 git 仓库** (master + main + spike 三分支, 全历史) | 15MB |
| `cc_context/memory/` | CC 项目记忆 (117 文件, 项目所有非显然知识/决策史) | 780K |
| `cc_context/global_CLAUDE.md` | zhuran24 的全局 CC 配置 (工作风格参考, 见 §4) | 18K |
| `cc_context/README_CC_HANDOFF.md` | **CC 上下文接入说明 (memory 重定位是关键, 务必读)** | — |
| `setup.sh` | **一键接手脚本** (clone + venv + 接 memory + 自检) | — |
| `HANDOFF.md` | 本文件 | — |

> 项目级 `CLAUDE.md` **已在 `repo.bundle` 里** (git tracked)，clone 出来 CC 打开
> 项目自动读。`.claude/settings.json` 也在 bundle 里，已清空 hooks (原来那个心跳
> hook 是 zhuran24 机器专属、且已暂停，交接前移除了，clone 出来不会报错)。
>
> 注: zhuran24 个人的**全局 skills/commands/agents** (academic-research 等) **没**
> 随包 —— 它们是跨项目的个人 CC 工具、跟本项目无关 (且是指向另一个仓库的符号
> 链接)。接手者用自己的全局 CC 配置即可。

---

## 2. 快速上手 —— 一条命令全自动

> **环境前提**: `setup.sh` 需要 **bash** + git + Python 3.13。
> - **Linux / macOS**: 直接 `bash setup.sh` (mac 自带 bash 够用)。
> - **Windows**: 在 **WSL2** 或 **Git-Bash** 里跑，别在 PowerShell/cmd 里跑
>   (脚本是 bash + 用 `.venv/bin/` 布局；原生 Windows venv 是 `.venv\Scripts\`，
>   激活用 `.venv\Scripts\activate`)。最省事是用 WSL2。
> - 没 Python 3.13 也能先 clone + 接 memory (脚本会 warn 后继续)，之后自己装
>   3.13 补 venv。**别用 3.14** (有 json stdlib 坑，项目踩过)。

解压本包后，在**包根目录**里跑:

```bash
bash setup.sh
```

它会全自动做完: ① clone 出完整 git 仓库 (→ `./zmd`) ② 建 Python venv + 装
精确版依赖 ③ **把 CC memory 自动接到正确的 slug 路径** ④ 冒烟自检。

跑完按它最后提示的两行走，就能**直接开 CC 接手**:

```bash
cd zmd
source .venv/bin/activate
claude                  # CC 自动加载项目 CLAUDE.md + memory, 直接能问项目状态
```

开 CC 后第一句可以问「读一下 mem 和项目状态」，它会复述出当前阶段 / F3 /
27 lever 等 —— 说明上下文全接上了。

> `setup.sh` 选项: `--target DIR` (clone 到别处) · `--no-venv` (跳过 Python 环境)
> · `--no-memory` (跳过 CC memory 接入)。

### 手动版 (脚本跑不动时的兜底)

```bash
# ① 解仓库 (完整独立 git 仓库, 全历史; 默认 checkout master)
git clone repo.bundle zmd && cd zmd
git branch -a     # master / main / spike/prod_scale_master_integration_20260526

# ② Python 3.13 环境 (ortools 是大头)
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock.txt        # 精确锁版本 (ortools==9.15.6755)

# ③ 接 CC memory (slug = 项目绝对路径把 / 换成 -, 详见 cc_context/README_CC_HANDOFF.md)
PROJ="$(pwd)"; SLUG="$(printf '%s' "$PROJ" | sed 's#/#-#g')"
mkdir -p "$HOME/.claude/projects/$SLUG"
cp -r ../cc_context/memory "$HOME/.claude/projects/$SLUG/memory"

# ④ 验证
python -m pytest src/tests/cuts/ -q          # 应 414 passed
python main.py --help                         # 看入口参数
# python main.py                              # 真跑求解 (省略 --vis); --vis 是"只画图不解题"
```

> ⚠️ commit SHA 与 memory/docs 里引用的 SHA **一一对应**，别 rebase/重写历史。
> ⚠️ `ortools==9.15.6755` 是验证过的版本，换大版本 CP-SAT 行为可能漂移；
> Python 用 **3.13** (3.14 有 json stdlib 坑，项目踩过)。
> 更多命令见仓库内 `CLAUDE.md` 的 "Commands" 段。

---

## 3. 哪些**没**打进来 + 怎么再生 (都是可再生/缓存, 不丢东西)

为了体积，所有 **gitignored 的可再生产物**没打包。需要时本地再生:

| 没打包的 | 体积 | 怎么再生 |
|---|---|---|
| `.venv/` | 755M | `pip install -r requirements.lock.txt` (见 §2 手动版) |
| `.upstream_clones/` | 277M | 离线浏览用的上游全 clone，可选; `cd .upstream_clones/industrial_planner_v2 && git pull` 或重新 clone (仓库 CLAUDE.md 有说明) |
| `.codex_test_logs/` | 69M | 历史测试日志，不需要 |
| `.mypy_cache/` `.ruff_cache/` `.pytest_cache/` | ~16M | 跑 mypy/ruff/pytest 时自动生成 |
| `.artifacts/` | 3.3M | 旧交付 baseline 产物，gitignored，不需要 |
| `_codex_archive/` | 7.3M | Codex (GPT) 历史工作区，只读参考，接手不需要 |
| `data/checkpoints/` `data/telemetry/` | ~10M | campaign 运行时生成的 checkpoint/遥测，gitignored |

**核心数据 (53MB `candidate_placements.json` 等) 是 tracked 的，已在 bundle 里
(git 压缩进 15MB 了)，不用再生。** 这是 source of truth，preflight 有 hash 校验。

---

## 4. CC (Claude Code) 上下文接入 —— 务必读 `cc_context/README_CC_HANDOFF.md`

朋友那边也有 CC，要让 CC 接手时带上**全部项目记忆**，关键是把
`cc_context/memory/` 放到 CC 能自动加载的位置 (路径有讲究)。**详细步骤 +
slug 计算在 `cc_context/README_CC_HANDOFF.md`。**

简版:
```bash
# 在 clone 出来的项目目录里跑:
PROJ="$(pwd)"
SLUG="$(printf '%s' "$PROJ" | sed 's#/#-#g')"
DEST="$HOME/.claude/projects/$SLUG"
mkdir -p "$DEST"
cp -r /path/to/cc_context/memory "$DEST/memory"
# 之后 CC 打开这个项目, 会自动加载 memory/MEMORY.md 索引 + 按需读各条
```

`global_CLAUDE.md` 是 zhuran24 的全局 CC 配置 (工作风格/沟通偏好/子代理选型/
知识持久化规则)。**接手者可挑着参考工作风格那几段**；里面「磁盘策略 / 硬件备忘
/ 心跳维护」是 zhuran24 那台 CachyOS 主机专属的，换机器不适用，忽略即可。

> zhuran24 个人的全局 skills/commands/agents (academic-research 等跨项目工具)
> **没**随包 —— 跟本项目无关，接手者用自己的即可。

---

## 5. 当前项目状态 (接手者最该先知道的)

> 这是 2026-05-30 交接时的状态。更细的演进史全在 `cc_context/memory/` (尤其
> `MEMORY.md` 索引 + `project_phase_1_2_progress.md` + `project_paradigm_death_timeline_27_lever.md`)。

- **阶段**: Phase 1.2 spike close **已收尾**，正要进 P1.3A 主体。
- **Cut framework**: 9 个 cut family (F1-F9) 全部实施 + Gemini 逐 commit cross-check
  通过。最后一个 **F3 port_exposure** 走了独立的 "special-case phase" 补齐
  (之前是 stub，现已实现: commit `c768806`/`b5860bc`/`c639063`)。
- **在哪个分支干**: **从 `master` 起** (F3 generator + 全 9 family 都在 master，
  master 是工作主线)。`spike/prod_scale_master_integration_20260526` 分支是
  **throw-away 的 spike 验证脚手架 + review 数据** (PR #1 verdict-only style)，
  **P1.3A 走 N=8 parallel design 重新做，不要 cherry-pick spike 分支的代码**
  (详见 memory `feedback_design_phase_n_parallel_agents.md` +
  `feedback_main_merger_scope_creep_bias.md`)。
- **进行中的事 (接手第一件该知道的)**: spike close 经 GPT pro **v14(一审)→v22(八审)
  共 8 轮**外部审查逐 finding 修。**当前 = v22 包已构建、在等 GPT 九审最终
  CLEAN GO 确认** (八审两个 reviewer 给 GO_WITH_MINOR/PATCH_REQUIRED，v22 已把
  finding 修掉)。v22 sha `72a04545...`，历史 review 包已归档到外盘
  `/mnt/wd_external/zmd_review_archive/` (不在本交接包里，是 review artifact)。
  审查方法论 + 每轮 finding 全记在 memory (`external-review-prompt-template` /
  `review-pkg-data-completeness` / `review-pkg-no-prompt-inside` 等)。
- **下一步**: P1.3A 主体设计 (真 `PoseBoolExactMaster` 接入 + multi-iter LBBD +
  收敛 / adversarial robustness)。spike 留了 5 项 Layer 2 risk 进 P1.3A risk
  register (含 G6a SOFT: toy master 180s wall，real master 不可假设单次 solve 收敛)。
- **27 lever paradigm 死路史**: 项目试过 27 条求解 paradigm 大多 NOT_GO，死因
  分类全在 `memory/project_paradigm_death_timeline_27_lever.md` +
  `docs/项目说明/03_paradigm_death_baseline.md`。**接手前强烈建议先扫一遍**，
  别重踩。

不可碰的红线 (exactness constitution) 在 `PROJECT_LOCK.md`，改 exact 边界必须
同步更新 lock/spec/test。

---

## 6. 接手者注意事项

- **硬编码路径**: `scripts/build_*review*.py` 和 `scripts/gemini_cross_check_*.py`
  里有约 33 个文件、共 ~75 处硬编码 `/home/zhuran24/...` —— 这些是**一次性
  review 打包 / 外部 cross-check 脚本，接手日常用不到**。核心运行路径
  (`main.py` + `src/`) **没有**硬编码绝对路径，clone 到任何位置都能跑。
- **Gemini cross-check key**: `scripts/gemini_cross_check_*.py` 和
  `memory/reference_gemini_math_consultant.md` 里有个 Gemini free-tier API key
  (zhuran24 授权随包给你)。它是免费额度、可能快到期，跑不通就自己申请一个
  Google AI Studio key 换上。
- **预提交门禁**: 仓库有 preflight gate hook (`.claude/` + `scripts/`)，commit 前
  自动跑 hash 校验 / mypy / ruff / 核心 pytest。第一次 commit 若 hook 报错多半是
  环境没配好 (venv / 依赖)。
- **测试基线**: 主分支有 ~29 个 Codex 时期的 baseline failure (全量 pytest 时)，
  不是你引入的。日常只跑 `src/tests/cuts/` (414 passed) 就够。详见
  memory `feedback_full_pytest_after_vendor_refresh.md`。

---

## 7. 一句话给接手者的 CC

> 「先读 `cc_context/README_CC_HANDOFF.md` 把 memory 接进来，再读 memory 里的
> `MEMORY.md` 索引 + `project_phase_1_2_progress.md` + 27-lever 死路史，就能接上
> 全部上下文。项目根的 `CLAUDE.md` 是运行/约定手册。」
