# Endfield IndustrialPlanner — 70×70 certified-exact 求解器

《明日方舟：终末地》基地排布的**精确最大空矩形求解器**：在 70×70 网格、266 个强制设施实例约束下，求 `max_lex(area, min_side)`（先最大化面积、再最大化短边）的**可证明最优**空地矩形。OR-Tools CP-SAT + Benders/LBBD 分解（master → binding → routing → flow）。

> **当前主线（范式 = cut-family LBBD）**
>
> 项目范式已从早期 tuning / Phase-3B 转为 **cut-family LBBD 重设计**：9 个 cut family **F1–F9** 当 Benders cut 收紧 master。当前阶段 = **Phase 1.2 spike close**（cut-family validator soundness 闭关）→ **P1.3B**（真 `PoseBoolExactMaster` 接 LBBD 真 master 集成 + 多轮收敛；P1.3A attach spike 已先验）。⚠️ 此处用 doc-tree 命名（P1.3B = 真 master 集成）≠ CC memory 口径的"P1.3A 主体"，见 `CLAUDE.md` 命名错位提示。
>
> **现状 / phase 的权威源不在本 README**——见：
>
> - **`CLAUDE.md`** — 求解器架构 + 当前 Phase + commands + runbook（单一操作手册）
> - **`PROJECT_LOCK.md`** — 精确性宪法 + 禁条 + accepted invariants（exact 边界冻结）
> - **`docs/项目说明/06_current_status.md`** — 现状细则；`docs/项目说明/`（21 篇）= overview / 数学基础 / 死路 baseline / 设计不变量 / 各 phase plan / glossary
> - **`specs/`（01–23）** — certified 路径的形式规格
> - **`docs/research/p1_2_spike_sizing_gate_20260601/authoritative_numbers.json`** — 评审/文档权威数字的单一来源（cuts 测试计数等；别在散文里另抄会漂的数）

## 跑求解器

```powershell
# certified_exact 模式（默认）
python main.py --campaign-hours 168.0 --parallel-processes 4
# 测试
python -m pytest src/tests/ -q
# 可视化
python main.py --vis
```

（Linux 生产启动须用 wrapper，单跑 `python main.py` 会丢调优；见 `CLAUDE.md` 的 Commands / Maintenance scripts 段。）

## 精确性边界（摘要，权威见 `PROJECT_LOCK.md`）

- `certified_exact` 与 `exploratory` 是**严格分离**的两条路径，绝不混用。
- exact 目标 = `max_lex(area, min_side)`；`min_side >= 6` 是候选 admissibility，不是 tie-break。
- exact 模式**无**硬 `50 供电桩 + 10 协议箱` cap —— 该数字仅 exploratory-only guidance（供电桩 residual-optional / 协议箱 demand 驱动）。
- 全 70×70 exact `CERTIFIED` 仍诚实标 `open`（spike close 阶段）。

## IndustrialPlanner 交付面（postprocess / adapter 线，release `r20260416` 冻结）

> **注**：本节是 **postprocess-only** 的产品化 / 交付线（把求解产物导出成 IndustrialPlanner 蓝图 + 消费面），**不是当前活动主线**，也**不重定义任何 solve schema**（见 `PROJECT_LOCK.md` 的 Source of Truth）。当前主线是上面的 cut-family LBBD。

当前唯一 active 的 IndustrialPlanner 线 = `valley4_protocol_core`（70×70）；其余 base 与 outer-deployment 均保留为 `future_scope`、不在默认 active gate。checked-in 入口与详细 artifact map / release pointers / 再生成命令见：

- `data/examples/industrial_planner/README.md` — 交付面 artifact map + release pointers + regeneration commands（交付面的权威索引）
- `data/examples/industrial_planner/index.html` — 交付面入口页（browse-first / download-first）
- `data/examples/industrial_planner/active_single_base_delivery_entrypoints.json` — 聚合 machine-readable entrypoints manifest（含 surface health 快照）

单基地端到端 / 交付面 promotion / no-drift audit / health snapshot 等脚本：

```bash
# 单基地 e2e
python scripts/run_industrial_planner_single_base_e2e.py \
  --run-dir .artifacts/industrial_planner_single_base_e2e
# 交付面 release promotion（刷新 release/viewer/landing/bundle/frontdoor + no-drift audit）
python scripts/build_industrial_planner_single_base_delivery_release.py --help
```

其余交付面脚本（standalone no-drift audit / health snapshot 等）见 `data/examples/industrial_planner/README.md` 与 `CLAUDE.md`。
