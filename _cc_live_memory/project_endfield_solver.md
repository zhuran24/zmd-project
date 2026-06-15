---
name: endfield-solver
index_summary: "终末地 70×70 工业规划器精确求解器身份根 (稳定身份+PROJECT_LOCK+依赖). 现状见交接条. 范式 = cut-family LBBD."
description: 明日方舟终末地70x70工业规划器精确求解器项目身份根 (稳定身份 + PROJECT_LOCK + 依赖)，从Codex(GPT)迁移到Claude Code。现状/phase 不在本条，见 handoff-windows-ninth-review-pending。范式演进史: Phase 3B tuning → 27 lever 全死 → B1 → B-design v2 cut-family LBBD (当前 phase/是否闭合一律见 living 源, 不在本条)。
type: project
originSessionId: 8ac66da5-49ee-4b7b-85e4-523f02bbc9e3
---
项目是明日方舟：终末地(Arknights: Endfield)的IndustrialPlanner精确求解器，在70×70网格上放置266个强制设施并找最大合法空矩形。

> ⚠️ **现状已演进, 本条只保留稳定身份 (项目是什么 / PROJECT_LOCK 边界 / 依赖), 不再作当前 phase 真相来源** (per [[memory-currency-protocol]])。当前 phase/交接状态见单一 living 源 [[windows-ninth-review-pending]]。
> **范式反转链 (历史演进, 非现状判断)**: 早期 Phase 3B tuning paradigm (latency-bound master 解不动 + 软优化全死) 经 **27 lever 全死** → **B1 pose-bool master** → **B Design v2 cut-family LBBD** 重写 → Phase 1.1 GO → Phase 1.2 spike (2026-05-27 GO_WITH_MINOR 进入 spike)。**当前是否闭合 / 处于哪个 phase 一律见 living 源 [[windows-ninth-review-pending]]** —— 注意 CLAUDE.md 明确 P1.2 spike close **未正式关闭** (V50 owner-count gate 在 force); 旧 CC memory 称的「P1.3A 主体」= 项目书 P1.3B, owner 没显式开就**未启动**, 别把本链读成「现处 P1.3A」。历史进度细节见归档 `cc_context/memory_archive/project_phase_1_2_progress.md` 与 [[paradigm-death-timeline-27-lever]]。

**Why:** 用户之前用Codex(GPT)开发，因GPT呆板迁移到Claude Code。

**How to apply:**
- 稳定身份: 70×70 网格 / 266 强制设施 / 最大合法空矩形; certified_exact vs exploratory 严格隔离, 改动必须尊重 `PROJECT_LOCK.md` 的冻结边界; 核心求解 (search/models/) 是证明源, adapters/render/ 是后处理, 不可混淆。
- **主入口 = 仓库根 `main.py`** (`python main.py --campaign-hours 168.0 --parallel-processes 4`, 默认 certified_exact mode, 以 CLAUDE.md 为准); 旧 Codex 嵌套布局 `endfield_phase3b_project_current/main.py` 已迁移废弃, 该目录不存在。
- prod 跑用 4 进程并行 (`--parallel-processes 4`); prod-scale 收敛只 Linux 主机跑 (见 [[windows-handoff-env]])。
- (历史) Phase 3A 产品化已完成 (release r20260416); 早期加速调优计划 `docs/phase3b_repair5_acceleration_tuning_ai_plan.md` 属 Phase 3B tuning paradigm, 已被 cut-family LBBD 重写取代。
- 依赖：ortools, pydantic, numpy, matplotlib, psutil, pandas

## 链 (补连 2026-06-01)
- [[user-profile]] — 用户画像
