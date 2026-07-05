# P3.0b 第二轮独立审查归档（2026-07-05）

**对象**：`formal/ZmdFormal/CutFamilies.lean`（17 条）+ `FrameworkLemmas.lean`
（9 条）的陈述保真。三路：对抗审 CutFamilies（双会话）、对抗审
FrameworkLemmas（双会话）、盲形式化对拼（26 条独立陈述）。

**回收结论**：三方高度收敛——盲方在未见我方 Lean 的情况下独立做出的
关键抽象选择（F3 用 multiset、F6 fire 用跨侧组合、F5 用删整类前提 +
非 G-不变反例、frontier 加 certified witness 限定）恰好命中对抗审的
全部主要发现。修订（7 条陈述改 + 8 条新增 + 3 处 docstring 强化）见
`formal/README.md` 的「外审回收修订记录」节；补丁均未盲 apply，
全部本地重写 + 重编译 + 公理审计（68/68 干净）。

## 文件清单

| 文件 | 内容 |
|---|---|
| `framework_audit_session1.md` | FrameworkLemmas 对抗审会话 1 全文（3 忠实/3 BLOCK/3 CONCERN） |
| `framework_audit_session2_summary.md` / `_report.md` / `_patches.lean.txt` | 同任务会话 2（2 忠实/4 BLOCK/3 CONCERN；结论与会话 1 收敛） |
| `cutfamilies_audit_session1_summary.md` / `_report.md` / `_patches.lean.txt` | CutFamilies 对抗审会话 1（10 忠实/5 CONCERN/2 BLOCK） |
| `cutfamilies_audit_session2_summary.md` / `_report.md` / `_patches.lean.txt` | 同任务会话 2（8 忠实/7 CONCERN/2 BLOCK；BLOCK 与会话 1 同点） |
| `blind_formalization_statements.lean.txt` / `blind_formalization_notes.md` | 盲形式化交付：26 条独立陈述（含我方未做的 TP7-S T1-T6 必要性 lifting，未来素材）+ 抽象选择说明 |

`.lean.txt` 后缀 = 归档为文本、不进构建。审计正文原件是 owner 会话
导出的 txt，归档时仅改名，未改内容。

## 未消化残余（登记）

- 盲方 T1-T6 必要性 lifting（TP7-S 六约束的"周期平均语义 ⇒ 约束"定理族）
  是我方 9 条框架层之外的增量——列为未来砖（TP7-D 验收语义的前置）。
- Framework 会话 2 建议的 `eq_key_violated_iff_inter`（无 `A ⊆ U` 时只得
  投影等式）未做——当前 def 已内置全集约束，投影版仅当未来有人绕过
  def 直接写违反条件时才需要。
- 会话 1 对 `f5_compound_safety` 结论的"类内全体未被 cut"更强形态
  （会话 2 补丁方向）未采纳——当前类局部结论（代表存活）已忠实于
  原文文本；更强形态等 P1.3 接入时按需要加。
