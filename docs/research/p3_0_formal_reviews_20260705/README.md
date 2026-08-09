# 2026-07-05 P3.0 形式化头启动首轮独立审查归档（三会话）

**性质**：HISTORICAL_OR_PLAN 审计档案，`formal/` 首批定理与 P3.0 设计稿 v1 的
三路独立审查产物，v2 修订的输入证据。补丁未盲 apply（lean 补丁经本地重编译 +
公理审计后采纳；一处 API 修复：Lean core 无 `Function.Bijective`，双射前提改双侧逆）。

| 文件 | 会话 | 内容 |
|---|---|---|
| `p3_0_certside_route_research_gpt.md` | 证书侧路线深研（联网） | v1 轴 B 六处事实修正 + 工具对照表（带来源/日期）+ 四条旁路路径工作量估计 + 七阶段接入方案；关键新事实 or-tools#5141、PB 证明工件量级 |
| `formalization_gap_audit_report.md` / `0001_formalization_gap_fixes.patch` | 陈述保真对抗审 | 1 BLOCK（定理 2 覆盖面夸大）+ 4 CONCERN + 4 NOTE，判定"修后可"；补丁含 5 条新定理（已采纳进 formal/） |
| `ZmdDesignStatements.lean` / `README_ZmdDesignStatements.md` / `zmd_design_formalization_statements.patch` | 盲形式化对拼 | 独立 mathlib 陈述（sorry 形态）：与本方全部抽象选择收敛、零矛盾；含 anon_lift_sound 完整分解设计（P3.0b 施工蓝图）+ 12 条陈述精化建议 |

对应主稿：`../p3_0_formal_verification_head_start_design_v1.md`（v2）与 `formal/`（14 条定理）。
